"""Bounded native-text income-statement extraction. No model or OCR calls.

Amounts enter only through PDF text. Verified snapshot facts are loaded AFTER
the extracted files have been written, solely for independent comparison.
"""
import argparse
import csv
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

from .accounting import decimal_text
from .stage3_input import sha

# Manual layout/label configuration; deliberately contains no financial amounts.
COMPANY = '珠海格力电器股份有限公司'
PDF_PAGE, PRINTED_PAGE = 88, 87
METRICS = {
    'operating_profit': '营业利润', 'pretax_profit': '利润总额',
    'net_profit': '净利润', 'income_tax': '所得税费用',
    'parent_profit': '归属于母公司股东的净利润',
}
SCALES = {'元': Decimal(1), '万元': Decimal(10000), '亿元': Decimal(100000000)}
NUMBER = re.compile(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\Z')


def amount(raw, unit):
    """Explicit blank symbols are missing, never zero; reject unknown syntax."""
    if raw in ('', '-', '—', '–'): return None
    token = raw.replace('−', '-')
    if token.startswith('(') and token.endswith(')'):
        token = '-' + token[1:-1]
    if not NUMBER.fullmatch(token): raise ValueError('unsupported_amount:' + raw)
    with localcontext() as ctx:
        ctx.prec = max(50, len(token) + 12)
        return decimal_text(Decimal(token.replace(',', '')) * SCALES[unit])


def parse_page(text, source_file, source_hash, pdf_page=PDF_PAGE):
    """Accept one configured annual consolidated statement with two clear cells.

    A missing column without an explicit placeholder is ambiguous: both annual
    values of that row are withheld. Wrapped/duplicate rows also fail closed.
    """
    lines = text.splitlines()
    compact = [re.sub(r'\s+', '', line) for line in lines]
    errors = []
    titles = [i for i, line in enumerate(compact) if line == '合并利润表']
    ends = [i for i, line in enumerate(compact) if line.startswith('法定代表人：')]
    headers = [i for i, line in enumerate(compact) if line.startswith('项目附注')]
    years = []
    if len(headers) == 1:
        h = compact[headers[0]]
        match = re.fullmatch(r'项目附注(202[45])年度(202[45])年度', h)
        if match: years = [int(x) for x in match.groups()]
    if sorted(years) != [2024, 2025]: errors.append('ambiguous_year_columns')
    if len(titles) != 1 or len(ends) != 1 or len(headers) != 1:
        errors.append('unsupported_table_boundaries')
    elif not titles[0] < headers[0] < ends[0]: errors.append('invalid_table_order')
    if '2025年1-12月' not in compact: errors.append('annual_period_unconfirmed')
    if str(PRINTED_PAGE) not in [s.strip() for s in lines[:6]]:
        errors.append('printed_page_unconfirmed')
    if pdf_page != PDF_PAGE: errors.append('unexpected_pdf_page')
    units = re.findall(r'编制单位：([^\s]+)\s*单位：人民币(亿元|万元|元)\s*$', text, re.M)
    company, unit = units[0] if len(units) == 1 else (None, None)
    if company != COMPANY: errors.append('company_unconfirmed')
    if unit not in SCALES: errors.append('currency_or_unit_unconfirmed')
    rows = []
    for key, name in METRICS.items():
        candidates = []
        if not errors:
            for index in range(headers[0] + 1, ends[0]):
                # Anchor full subject, never confuse net profit with parent profit.
                pattern = r'^\s*(?:(?:[一二三四五六七八九十0-9]+、)|(?:减：))?\s*' + re.escape(name) + r'(?:[（(][^）)]*[）)])?(?:\s+(.*)|\s*)$'
                m = re.match(pattern, lines[index])
                if m: candidates.append((index, lines[index], m.group(1) or ''))
        reason = ';'.join(errors)
        cells = []
        raw_row = '\n'.join(c[1] for c in candidates)
        if not reason:
            if len(candidates) != 1: reason = 'duplicate_subject' if candidates else 'subject_not_found'
            else:
                suffix = re.sub(r'^[一二三四五六七八九十]+、\s*\d+\s+', '', candidates[0][2])
                cells = suffix.split()
                if len(cells) != 2: reason = 'ambiguous_or_missing_cells'
        for year in (2024, 2025):
            raw, value, row_reason = None, None, reason
            if not row_reason:
                raw = cells[years.index(year)]
                try:
                    value = amount(raw, unit)
                    if value is None: row_reason = 'blank_cell'
                except ValueError as exc: row_reason = str(exc)
            rows.append(dict(company=company, metric_id=key, standard_metric=key,
                metric_name=name, fiscal_year=year, period=f'{year}-01-01/{year}-12-31',
                scope='合并' if not errors else None, statement_scope='合并' if not errors else None,
                currency='CNY' if unit else None, unit='元', source_unit=unit,
                value=value, metric_value=value, raw_amount=raw,
                source_file=source_file, pdf_page=pdf_page,
                printed_page=PRINTED_PAGE if 'printed_page_unconfirmed' not in errors else None,
                source_hash=source_hash, raw_row_text=raw_row,
                raw_row_sha256=hashlib.sha256(raw_row.encode()).hexdigest(),
                source_line=candidates[0][0]+1 if len(candidates)==1 else None,
                extraction_status='extracted' if not row_reason else 'missing', reason=row_reason))
    return rows, dict(errors=errors, year_columns=years, company=company,
        source_unit=unit, page_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        raw_page_text=text, metric_mapping=METRICS, amount_input='PDF text only')


def extract_pdf(path, expected_hash=None):
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
    path = Path(path)
    digest = sha(path)
    if expected_hash and digest != expected_hash: raise ValueError('PDF inventory hash mismatch')
    try:
        reader = PdfReader(path)
        if len(reader.pages) < PDF_PAGE: raise ValueError('configured PDF page absent')
        text = reader.pages[PDF_PAGE-1].extract_text() or ''
    except PyPdfError as exc:
        raise ValueError('unsupported_or_invalid_pdf:' + str(exc)) from exc
    if sha(path) != digest: raise ValueError('PDF changed during extraction')
    return parse_page(text, path.name, digest)


def compare(rows, payload):
    from .agent import LocalFacts
    from .source_contract import verified_evidence
    facts = LocalFacts(payload)
    evidence = {e['evidence_id']: e for e in payload['evidence']}
    results = []
    for r in rows:
        result = dict(metric_id=r['metric_id'], fiscal_year=r['fiscal_year'],
                      extracted_value=r['value'], trusted_value=None, status='unverifiable', evidence_ids=[])
        if r['extraction_status'] != 'extracted':
            result.update(status='missing', reason=r['reason'])
        else:
            try:
                f = facts.get(r['metric_id'])
                periods = payload.get('periods')
                if periods != ['2024', '2025']: raise ValueError('trusted_year_mapping_unconfirmed')
                field = 'base' if r['fiscal_year'] == 2024 else 'current'
                result['trusted_value'] = f['amounts'][field]['元']
                if (r['company'] != payload['company'] or r['currency'] != payload['currency']
                    or r['scope'] != '合并' or r['unit'] != '元'
                    or payload.get('scope') != '披露口径的合并报表；合并范围变动，非恒定主体比较'):
                    result.update(status='mismatch', reason='company_currency_scope_or_unit_mismatch')
                else:
                    linked = [evidence[eid] for eid in f['evidence_ids']]
                    linked = [e for e in linked if verified_evidence(e, payload)
                        and e['source_file'] == r['source_file'] and e['pdf_page'] == r['pdf_page']
                        and str(e['printed_page']) == str(r['printed_page'])
                        and payload['source_contract']['evidence'][e['evidence_id']]['file_sha256'] == r['source_hash']
                        and r['raw_row_text'] in e['text']]
                    if not linked: raise ValueError('matching_verified_source_row_missing')
                    result['evidence_ids'] = [e['evidence_id'] for e in linked]
                    result['status'] = 'matched' if Decimal(r['value']) == Decimal(result['trusted_value']) else 'mismatch'
                    result['reason'] = 'exact_decimal_comparison'
            except (KeyError, ValueError) as exc: result['reason'] = str(exc)
        results.append(result)
    return results


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(folder, output_root='outputs/pdf_extract'):
    folder = Path(folder)
    out = Path(output_root) / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:10])
    out.mkdir(parents=True, exist_ok=False)
    rows, audit, comparisons = [], {}, []
    try:
        inventory = json.loads((folder/'inventory.json').read_text(encoding='utf-8'))
        candidates = [i for i in inventory if i['key'] == '2025']
        if len(candidates) != 1: raise ValueError('unique 2025 PDF required')
        source = candidates[0]
        if Path(source['file']).name != source['file']: raise ValueError('invalid PDF filename')
        rows, audit = extract_pdf(folder/'inputs'/source['file'], source['sha256'])
        save(out/'extracted_financial.json', rows)
        with (out/'extracted_financial.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        audit['extracted_json_sha256_before_comparison'] = sha(out/'extracted_financial.json')
        # Existing source loader revalidates the snapshot and PDF independently.
        from .final_release import load_agent_payload
        try:
            payload, _ = load_agent_payload(folder)
            comparisons = compare(rows, payload)
        except (ValueError, KeyError, OSError) as exc:
            audit['comparison_error'] = str(exc)
            comparisons = [dict(metric_id=r['metric_id'], fiscal_year=r['fiscal_year'],
                extracted_value=r['value'], trusted_value=None,
                status='missing' if r['extraction_status']!='extracted' else 'unverifiable',
                reason=str(exc)) for r in rows]
    except (ValueError, KeyError, OSError) as exc:
        audit['fatal_error'] = str(exc)
        save(out/'extracted_financial.json', rows)
        (out/'extracted_financial.csv').write_text('metric_id,fiscal_year,value,extraction_status\n', encoding='utf-8')
    counts = {s: sum(c['status']==s for c in comparisons) for s in ('matched','mismatch','missing','unverifiable')}
    audit.update(source_run=str(folder.resolve()), records=rows, comparison_counts=counts)
    save(out/'extraction_audit.json', audit); save(out/'comparison.json', comparisons)
    report = ['# PDF 合并利润表受限提取', '', '金额来自本次 PDF 文本读取；人工仅配置表格、页码及科目映射。无模型调用。',
              '2024 数值为 2025 年报比较列；披露合并口径不等于恒定合并范围。', '',
              '|科目|年份|金额（元）|PDF/印刷页|提取|核验|', '|---|---|---|---|---|---|']
    by_key = {(c['metric_id'],c['fiscal_year']):c for c in comparisons}
    for r in rows:
        c = by_key.get((r['metric_id'],r['fiscal_year']), {})
        report.append(f"|{r['metric_name']}|{r['fiscal_year']}|{r['value'] or '缺失'}|{r['pdf_page']}/{r['printed_page']}|{r['extraction_status']}|{c.get('status','unverifiable')}|")
    report += ['', '核验计数：' + json.dumps(counts, ensure_ascii=False),
               '错误：' + json.dumps({k:v for k,v in audit.items() if k in ('errors','fatal_error','comparison_error')}, ensure_ascii=False),
               '', '逐项原文、精确金额、证据编号及失败原因见 extraction_audit.json / comparison.json。',
               '仅支持已配置的原生文字单页表格，不支持 OCR、跨页或缺失列的推断；结果不自动写入可信事实。']
    (out/'report.md').write_text('\n'.join(report)+'\n', encoding='utf-8')
    extracted = sum(r['extraction_status']=='extracted' for r in rows)
    ok = extracted == 10 and counts['matched'] == 10 and not audit.get('fatal_error')
    print(json.dumps(dict(extracted_fields=extracted, **counts, failed_fields=10-counts['matched'], output=str(out.resolve())), ensure_ascii=False))
    return out, 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage2-run', required=True, help='existing final_revision/final_release snapshot with inventory and verified facts')
    args = parser.parse_args()
    _, code = run(args.stage2_run)
    return code


if __name__ == '__main__': raise SystemExit(main())
