import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tracelab.stage1 import COLUMNS, calculate, main, read_rows, run, validate_metadata

ROOT = Path(__file__).resolve().parents[1]


class Stage1Tests(unittest.TestCase):
    def setUp(self):
        self.meta = json.loads((ROOT / "examples/simulated/metadata.json").read_text(encoding="utf-8"))
        self.row = dict(zip(COLUMNS, ["x", "模拟项目", "0.10", "0.30", "元", "元",
                                      "相同定义", "相同定义", "模拟出处A", "模拟出处B"]))

    def evaluate(self, **changes):
        issues = []
        row = self.row | changes
        result = calculate([(2, row)], self.meta, False, issues)[0]
        return result, issues

    def test_exact_decimal_and_negative_and_zero(self):
        for a, b, expected in [("0.10", "0.30", "0.20"), ("-10.00", "-7.50", "2.50"),
                               ("10", "7", "-3"), ("0.00", "0.00", "0.00"),
                               ("99999999999999999999999999999.99", "100000000000000000000000000000.00", "0.01")]:
            with self.subTest(a=a, b=b):
                result, issues = self.evaluate(base_amount=a, current_amount=b)
                self.assertEqual(result["difference"], expected)
                self.assertEqual(issues, [])

    def test_invalid_or_missing_amount_never_zero(self):
        for value in ("", "-", "—", "NaN", "Infinity", "1e3", "1,000", "(100)", "12%", "=1+2", "9" * 129):
            with self.subTest(value=value):
                result, issues = self.evaluate(base_amount=value)
                self.assertEqual(result["difference"], "")
                self.assertEqual(result["status"], "blocked")
                self.assertTrue(issues)

    def test_units_and_definitions_must_match(self):
        for change in ({"current_unit": "万元"}, {"current_definition": "另一个口径"}):
            result, issues = self.evaluate(**change)
            self.assertEqual(result["difference"], "")
            self.assertTrue(any(i["code"].endswith("MISMATCH") for i in issues))

    def test_missing_source_is_pending(self):
        result, issues = self.evaluate(base_source="待确认")
        self.assertEqual(result["difference"], "")
        self.assertEqual(issues[0]["severity"], "PENDING")

    def test_all_duplicates_are_blocked(self):
        for row in (self.row.copy(), self.row | {"item_id": "another"}):
            issues = []
            results = calculate([(2, self.row), (3, row)], self.meta, False, issues)
            self.assertTrue(all(r["status"] == "blocked" for r in results))
            self.assertTrue(issues)

    def test_metadata_mismatch_and_unknown(self):
        for field in ("company", "currency", "statement_scope", "profit_basis"):
            with self.subTest(field=field):
                meta = copy.deepcopy(self.meta)
                meta["current"][field] = "different"
                issues = []
                validate_metadata(meta, issues)
                self.assertIn("METADATA_MISMATCH", [i["code"] for i in issues])
        for value in (None, False, "true", 1):
            issues = []
            validate_metadata(self.meta | {"comparability_confirmed": value}, issues)
            self.assertIn("COMPARABILITY_UNCONFIRMED", [i["code"] for i in issues])

    def test_dates_and_metadata_type(self):
        for value in ("2025-02-30", "20250101"):
            meta = copy.deepcopy(self.meta)
            meta["base"]["period_start"] = value
            issues = []
            validate_metadata(meta, issues)
            self.assertIn("DATE_FORMAT", [i["code"] for i in issues])
        issues = []
        validate_metadata([], issues)
        self.assertIn("METADATA_TYPE", [i["code"] for i in issues])

    def test_missing_duplicate_and_extra_headers(self):
        for content in (b"item_id\nx\n", b"item_id,item_id\nx,x\n",
                        (",".join(COLUMNS) + ",extra\n").encode()):
            issues = []
            self.assertEqual(read_rows(content, issues), [])
            self.assertTrue(issues)

    def test_bom_empty_and_bad_width(self):
        issues = []
        text = ",".join(COLUMNS) + "\n" + ",".join(self.row.values()) + "\n"
        rows = read_rows(text.encode("utf-8-sig"), issues)
        self.assertEqual(len(rows), 1)
        self.assertEqual(issues, [])
        for text in (",".join(COLUMNS) + "\n", ",".join(COLUMNS) + "\nx,y\n"):
            issues = []
            read_rows(text.encode(), issues)
            self.assertTrue(issues)

    def test_full_run_snapshots_and_no_overwrite(self):
        source = ROOT / "examples/simulated/financial.csv"
        meta = ROOT / "examples/simulated/metadata.json"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            folder, manifest = run(source, meta, temp)
            second, _ = run(source, meta, temp)
            self.assertNotEqual(folder, second)
            self.assertEqual(manifest["status"], "ok")
            self.assertFalse(manifest["llm_called"])
            self.assertEqual(manifest["human_reconciliation"], "not_performed")
            self.assertEqual(manifest["inputs"]["financial.csv"]["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual((folder / "inputs/financial.csv").read_bytes(), before)
            data = json.loads((folder / "results.json").read_text(encoding="utf-8"))
            self.assertEqual([r["difference"] for r in data["results"]], ["20.25", "2.50", "0.00"])
            with (folder / "results.csv").open(encoding="utf-8-sig", newline="") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 3)
            events = [json.loads(x) for x in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events[-1]["event"], "finished")
        self.assertEqual(source.read_bytes(), before)

    def test_bad_metadata_blocks_all_and_writes_issues(self):
        for content in ('[]', '{broken', '{"a":1,"a":2}', '{"a":NaN}', '{}'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temp:
                meta = Path(temp) / "meta.json"
                meta.write_text(content, encoding="utf-8")
                folder, manifest = run(ROOT / "examples/simulated/financial.csv", meta, Path(temp) / "out")
                self.assertNotEqual(manifest["status"], "ok")
                results = json.loads((folder / "results.json").read_text(encoding="utf-8"))["results"]
                self.assertTrue(all(r["difference"] == "" for r in results))

    def test_missing_files_and_cli_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, manifest = run(Path(temp) / "missing.csv", Path(temp) / "missing.json", Path(temp) / "out")
            self.assertEqual(manifest["status"], "error")
            self.assertTrue((folder / "issues.json").exists())
            self.assertEqual(main(["--input", str(ROOT / "templates/financial.csv"),
                                   "--metadata", str(ROOT / "templates/metadata.json"),
                                   "--output", str(Path(temp) / "cli")]), 1)


if __name__ == "__main__":
    unittest.main()
