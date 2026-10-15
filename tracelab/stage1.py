"""CSV input -> validation -> current minus base. No attribution or LLM."""

import argparse
import csv
import hashlib
import io
import json
import platform
import re
import sys
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

from . import __version__

COLUMNS = (
    "item_id", "item_name", "base_amount", "current_amount", "base_unit",
    "current_unit", "base_definition", "current_definition", "base_source",
    "current_source",
)
RESULT_COLUMNS = ("row", "data_kind", *COLUMNS, "difference", "status")
ISSUE_COLUMNS = ("severity", "code", "row", "field", "message")
UNKNOWN = {"", "待确认", "待填写", "未知", "unknown", "tbd", "n/a", "null"}
AMOUNT = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")


def issue(issues, severity, code, field, message, row=None):
    issues.append(dict(severity=severity, code=code, row=row,
                       field=field, message=message))


def known_text(value):
    return isinstance(value, str) and value.strip().lower() not in UNKNOWN


def strict_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"JSON 重复键：{key}")
        obj[key] = value
    return obj


def invalid_constant(value):
    raise ValueError(f"JSON 不允许非有限数字：{value}")


def validate_metadata(meta, issues):
    if not isinstance(meta, dict):
        issue(issues, "ERROR", "METADATA_TYPE", "metadata", "元数据必须是 JSON 对象")
        return
    for field in ("dataset_id",):
        if not known_text(meta.get(field)):
            issue(issues, "PENDING", "METADATA_MISSING", field, "请金融组填写")
    if meta.get("data_kind") not in ("real", "simulated"):
        issue(issues, "PENDING", "DATA_KIND", "data_kind", "必须明确 real 或 simulated")
    if meta.get("comparability_confirmed") is not True:
        issue(issues, "PENDING", "COMPARABILITY_UNCONFIRMED", "comparability_confirmed",
              "需金融组确认期间、重述版本、报表范围和各项目定义可比；不能由程序猜测")
    sections = {}
    dates = {}
    for side in ("base", "current"):
        section = meta.get(side)
        if not isinstance(section, dict):
            issue(issues, "ERROR", "PERIOD_METADATA", side, "必须提供两期元数据对象")
            continue
        sections[side] = section
        for field in ("company", "currency", "statement_scope", "profit_basis",
                      "data_version", "period_start", "period_end"):
            value = section.get(field)
            if not known_text(value):
                issue(issues, "PENDING", "METADATA_MISSING", f"{side}.{field}", "请金融组填写")
                continue
            if field.startswith("period_"):
                try:
                    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                        raise ValueError("非 ISO 日期")
                    dates[(side, field)] = date.fromisoformat(value)
                except ValueError:
                    issue(issues, "ERROR", "DATE_FORMAT", f"{side}.{field}", "须为有效 YYYY-MM-DD 日期")
        start, end = dates.get((side, "period_start")), dates.get((side, "period_end"))
        if start and end and start > end:
            issue(issues, "ERROR", "DATE_ORDER", side, "报告期开始日期不能晚于结束日期")
    if len(sections) == 2:
        for field in ("company", "currency", "statement_scope", "profit_basis"):
            a, b = sections["base"].get(field), sections["current"].get(field)
            if known_text(a) and known_text(b) and a.strip() != b.strip():
                issue(issues, "ERROR", "METADATA_MISMATCH", field,
                      "两期填写值不一致；不自动转换或推断等价口径")
        a, b = dates.get(("base", "period_end")), dates.get(("current", "period_end"))
        if a and b and a >= b:
            issue(issues, "ERROR", "PERIOD_ORDER", "period_end", "本期结束日期须晚于基期")


def read_rows(content, issues):
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, [])
        if len(header) != len(set(header)):
            issue(issues, "ERROR", "DUPLICATE_HEADER", "header", "CSV 表头存在重复列")
        missing = set(COLUMNS) - set(header)
        extra = set(header) - set(COLUMNS)
        if missing:
            issue(issues, "ERROR", "MISSING_COLUMNS", "header", "缺少列：" + ", ".join(sorted(missing)))
        if extra:
            issue(issues, "ERROR", "UNKNOWN_COLUMNS", "header", "不支持的列：" + ", ".join(sorted(extra)))
        if issues:
            return []
        rows = []
        for cells in reader:
            if not cells:  # Blank physical lines are not financial records.
                continue
            line = reader.line_num
            if len(cells) != len(header):
                issue(issues, "ERROR", "ROW_WIDTH", "csv", "行列数与表头不一致", line)
                continue
            rows.append((line, dict(zip(header, cells))))
        if not rows:
            issue(issues, "ERROR", "NO_DATA", "csv", "没有可读取的数据行")
        return rows
    except (UnicodeError, csv.Error) as exc:
        issue(issues, "ERROR", "CSV_FORMAT", "csv", f"CSV 必须是有效 UTF-8：{exc}")
        return []


def parse_amount(value, field, row, issues):
    value = value.strip()
    if not value or value.lower() in UNKNOWN or value in ("-", "—", "--"):
        issue(issues, "ERROR", "MISSING_AMOUNT", field, "金额缺失，不能当作零", row)
        return None
    if len(value) > 128 or not AMOUNT.fullmatch(value):
        issue(issues, "ERROR", "NUMBER_FORMAT", field,
              "须为不超过128字符的普通十进制数字；不接受千分位、括号、科学计数法或非有限值", row)
        return None
    return Decimal(value)


def calculate(rows, meta, global_blocked, issues):
    counts = Counter(r["item_id"].strip() for _, r in rows)
    names = Counter(r["item_name"].strip() for _, r in rows)
    results = []
    for line, raw in rows:
        start = len(issues)
        values = {k: v.strip() for k, v in raw.items()}
        for field in COLUMNS:
            if field.endswith("_amount"):
                continue
            if not known_text(values[field]):
                severity = "ERROR" if field in ("item_id", "item_name") else "PENDING"
                issue(issues, severity, "FIELD_MISSING", field, "必填信息缺失或待确认", line)
        if values["item_id"] and counts[values["item_id"]] > 1:
            issue(issues, "ERROR", "DUPLICATE_ITEM", "item_id", "重复项目标识；所有重复行均不计算", line)
        if values["item_name"] and names[values["item_name"]] > 1:
            issue(issues, "ERROR", "DUPLICATE_NAME", "item_name", "重复项目名称；请确认是否重复或细分名称", line)
        for field in ("unit", "definition"):
            a, b = values[f"base_{field}"], values[f"current_{field}"]
            if known_text(a) and known_text(b) and a != b:
                issue(issues, "ERROR", f"{field.upper()}_MISMATCH", field,
                      "两期单位或项目定义不一致，禁止直接相减；请金融组核对", line)
        a = parse_amount(values["base_amount"], "base_amount", line, issues)
        b = parse_amount(values["current_amount"], "current_amount", line, issues)
        blocked = global_blocked or len(issues) != start
        difference = ""
        if not blocked:
            # Inputs have <=128 characters each; 256 significant digits covers
            # the complete integer/fraction alignment plus subtraction carry.
            with localcontext() as ctx:
                ctx.prec = 256
                delta = b - a
                if delta == 0:
                    delta = abs(delta)
                difference = format(delta, "f")
        results.append(dict(row=line, data_kind=meta.get("data_kind", "unknown"),
                            **raw, difference=difference,
                            status="blocked" if blocked else "calculated"))
    return results


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path, columns, rows):
    # These are machine-readable CSV files, not executable spreadsheet formulas.
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(csv_path, metadata_path, output_root):
    csv_path, metadata_path, output_root = map(Path, (csv_path, metadata_path, output_root))
    # Unique directory per run: never overwrite source material or earlier runs.
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    folder = output_root / run_id
    folder.mkdir(parents=True, exist_ok=False)
    issues, inputs, contents = [], {}, {}
    events = []

    def log(event, **data):
        events.append(dict(time=datetime.now(timezone.utc).isoformat(), run_id=run_id,
                           event=event, **data))

    log("started", stage="input_and_difference_only")
    for name, path in (("financial.csv", csv_path), ("metadata.json", metadata_path)):
        try:
            content = path.read_bytes()
            contents[name] = content
            snapshot = folder / "inputs" / name
            snapshot.parent.mkdir(exist_ok=True)
            snapshot.write_bytes(content)
            inputs[name] = dict(path=str(path.resolve()), sha256=hashlib.sha256(content).hexdigest())
            log("input_read", name=name, **inputs[name])
        except OSError as exc:
            issue(issues, "ERROR", "INPUT_READ", name, str(exc))
            log("input_read_failed", name=name, message=str(exc))
    meta = {}
    if "metadata.json" in contents:
        try:
            meta = json.loads(contents["metadata.json"].decode("utf-8-sig"),
                              object_pairs_hook=strict_object, parse_constant=invalid_constant)
            validate_metadata(meta, issues)
        except (ValueError, UnicodeError) as exc:
            issue(issues, "ERROR", "METADATA_FORMAT", "metadata", str(exc))
    global_blocked = bool(issues)
    csv_issues = []
    rows = read_rows(contents["financial.csv"], csv_issues) if "financial.csv" in contents else []
    # Structural CSV errors invalidate the dataset, avoiding apparent partial success.
    global_blocked = global_blocked or bool(csv_issues)
    issues.extend(csv_issues)
    meta_dict = meta if isinstance(meta, dict) else {}
    results = calculate(rows, meta_dict, global_blocked, issues)
    status = "error" if any(i["severity"] == "ERROR" for i in issues) else "pending" if issues else "ok"
    log("validated", status=status, issue_count=len(issues))
    log("differences_calculated", calculated=sum(r["status"] == "calculated" for r in results),
        blocked=sum(r["status"] == "blocked" for r in results), formula="current_amount - base_amount")
    write_csv(folder / "results.csv", RESULT_COLUMNS, results)
    write_csv(folder / "issues.csv", ISSUE_COLUMNS, issues)
    write_json(folder / "issues.json", issues)
    write_json(folder / "results.json", dict(metadata=meta, results=results))
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(Path(__file__).parent.glob("*.py"))}
    manifest = dict(run_id=run_id, status=status, data_kind=meta_dict.get("data_kind", "unknown"),
                    package_version=__version__, python=platform.python_version(),
                    inputs=inputs, code_sha256=source_hashes, row_count=len(results),
                    issue_count=len(issues), formula="current_amount - base_amount",
                    amount_encoding="decimal string; no rounding or unit conversion",
                    human_reconciliation="not_performed", llm_called=False,
                    limitations=["项目差额不是净利润贡献，未构造利润桥接",
                                 "仅检查填写信息，不验证披露文件真实性或语义等价性"])
    write_json(folder / "manifest.json", manifest)
    log("finished", status=status)
    (folder / "events.jsonl").write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    return folder, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="TraceLab 第一阶段：校验 CSV 并计算本期减基期")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/stage1"))
    args = parser.parse_args(argv)
    try:
        folder, manifest = run(args.input, args.metadata, args.output)
    except OSError as exc:
        print(f"输出或文件操作失败：{exc}", file=sys.stderr)
        return 2
    print(f"status={manifest['status']}; rows={manifest['row_count']}; issues={manifest['issue_count']}")
    print(f"output={folder.resolve()}")
    return {"ok": 0, "error": 1, "pending": 1}[manifest["status"]]
