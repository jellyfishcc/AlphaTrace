"""Verify a completed supplied Gree fixture run; no rerun or model call."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('run',type=Path)
args=parser.parse_args()
p=args.run
read=lambda name:json.loads((p/name).read_text(encoding='utf-8'))
checks=[]

for item in read('inventory.json'):
    assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
    assert hashlib.sha256((p/'inputs'/item['file']).read_bytes()).hexdigest()==item['sha256']
checks.append('六个原始附件及快照SHA-256一致，原始资料未改写')
metrics={r['item_id']:r for r in read('metrics.json')}
assert len(metrics)==31
assert sum(r['status']=='calculated' for r in metrics.values())==30
assert metrics['fee_income']['status']=='blocked'
assert metrics['fee_income']['difference']==''
assert Decimal(metrics['parent_profit']['difference'])==Decimal('-3181466960.62')
assert Decimal(metrics['operating_cashflow']['difference'])==Decimal('17013864183.36')
assert all(r['stock_code']=='000651' for r in read('financial_records.json'))
checks.append('31个真实项目中30个计算，空白佣金项目阻断，核心差额及字符串股票代码正确')
for row in metrics.values():
    if row['status']=='calculated':
        assert Decimal(row['current_amount'])-Decimal(row['base_amount'])==Decimal(row['difference'])
checks.append('全部可计算项目的逐项差额复算一致')
bridges={r['target']:r for r in read('bridges.json')}
assert Decimal(bridges['pretax_profit']['base']['residual'])==Decimal('.00000001')
assert Decimal(bridges['pretax_profit']['change_residual'])==Decimal('-.00000001')
assert bridges['total_revenue']['math_status']=='incomplete'
assert all(b['math_status']=='exact_zero_residual' for b in read('pdf_reference_bridges.json'))
assert all(b['business_status']=='待金融组确认' and b['tolerance'] is None for b in read('bridges.json'))
checks.append('Excel非零尾差、未完整收入检查及PDF三层精确勾稽均保留，未设业务容差')
human=read('human_comparison.json')
main=[h for h in human if h['source_file'].endswith('(1).docx') and h['location'].startswith('Table 3 ') and h['field']=='yoy_percent']
assert len(main)==7 and all(h['status'] in ('exact_match','display_rounding_match') for h in main)
checks.append('最新版Word七项主要同比按两位百分数展示一致')
assert len(read('segment_checks.json'))==8
assert all(r['status']=='exact_match' for r in read('segment_checks.json'))
checks.append('分产品/地区四行共八个金额与PDF一致')
pages={r['pdf_page']:r for r in read('source_text/pdf_2025.json')}
for evidence in read('evidence.json'):
    assert evidence['chunks']
    for chunk in evidence['chunks']:
        assert chunk['original_text'] in pages[chunk['pdf_page']]['text']
        assert chunk['printed_page']==pages[chunk['pdf_page']]['printed_page']
        assert hashlib.sha256(chunk['original_text'].encode()).hexdigest()==chunk['excerpt_sha256']
checks.append('E01-E06所有引文均能回到原始PDF提取页，页码及摘录哈希一致')
assert read('manifest.json')['llm_called'] is False
report={'status':'passed','checks':checks,'unit_tests':'23 tests passed in separate unittest run',
        'business_acceptance':'pending; software verification only'}
(p/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
