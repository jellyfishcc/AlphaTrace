"""Build a small public-disclosure-only payload from verified stage-two facts."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from .accounting import display_yi

SELECTED = {'revenue', 'operating_profit', 'pretax_profit', 'income_tax', 'net_profit',
            'minority_profit', 'parent_profit', 'operating_cashflow', 'total_cost', 'other_income'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def prepare(folder):
    from pypdf import PdfReader
    folder = Path(folder)
    if read(folder/'verification.json')['status'] != 'passed':
        raise ValueError('第二阶段核验未通过')
    meta = read(folder/'normalized/metadata.json')
    if not meta['comparability_confirmed'] or meta['data_kind'] != 'real':
        raise ValueError('需要已确认披露比较口径的真实输入')
    inventory = read(folder/'inventory.json')
    readers = {}
    for item in inventory:
        snapshot = folder/'inputs'/item['file']
        if sha(snapshot) != item['sha256']:
            raise ValueError('第二阶段原始快照哈希改变')
        if item['key'] in ('2024', '2025'):
            readers[item['file']] = PdfReader(snapshot)
    pages = {}

    def source_text(filename, page):
        key = filename, page
        if key not in pages:
            pages[key] = readers[filename].pages[page-1].extract_text() or ''
        return pages[key]

    metrics = read(folder/'metrics.json')
    checks = read(folder/'source_checks.json')
    records = read(folder/'financial_records.json')
    evidence = []
    facts = []
    excluded = []
    for m in metrics:
        key = m['item_id']
        matching = [c for c in checks if c['metric_name']==m['item_name']]
        verified = (m['status']=='calculated' and len(matching)==3 and
                    all(c['status']=='exact_match' for c in matching))
        if not verified or key not in SELECTED:
            excluded.append(dict(item_id=key, reason='阻断或未与年报精确匹配' if not verified else '本次有限分析不需要'))
            continue
        for c in matching:
            if not c['original_text'] or c['original_text'] not in source_text(c['source_file'],c['pdf_page']):
                raise ValueError('数值出处未在原始PDF页找到')
            field = 'base_amount' if c['fiscal_year']==2024 else 'current_amount'
            if Decimal(m[field]) != Decimal(c['pdf_yuan']):
                raise ValueError('计算输入与已核验披露值不同')
        a,b = Decimal(m['base_amount']), Decimal(m['current_amount'])
        if b-a != Decimal(m['difference']):
            raise ValueError('差额复算失败')
        matched_records = [r for r in records if r['standard_metric']==key]
        if len(matched_records)!=2 or any(r['verification_status']!='exact_pdf_match' for r in matched_records):
            raise ValueError('两期字段核验不完整')
        c = next(c for c in matching if c['fiscal_year']==2025)
        eid = 'F_'+key
        evidence.append(dict(evidence_id=eid, source_type='公开年报披露', source_file=c['source_file'],
                             printed_page=c['printed_page'], pdf_page=c['pdf_page'], text=c['original_text'],
                             related_facts=[key], origin='第二阶段数值原文检查'))
        facts.append(dict(fact_id=key, name=m['item_name'], evidence_ids=[eid],
                          amounts={f:{'元':v, '亿元':display_yi(Decimal(v))} for f,v in
                                   [('base',m['base_amount']),('current',m['current_amount']),('change',m['difference'])]}))
    if {f['fact_id'] for f in facts} != SELECTED:
        raise ValueError('有限分析所需指标未全部通过精确核验')
    original = next(e for e in read(folder/'evidence.json') if e['evidence_id']=='E07')
    # Deliberately omit finance-group summaries, grades, hypotheses, and full pages.
    excerpts = [('28','1.经营活动产生的现金流量净额同比变动','的现金增加所致。'),
                ('29','报告期内公司经营活动产生的现金净流量与本年度净利润存在重大差异的原因说明','现金流量表补充资料。'),
                ('179','票 据 保 证 金 等 净 减 少 额','15,667,164,024.70 元')]
    for printed,start,end in excerpts:
        chunk = next(c for c in original['chunks'] if c['printed_page']==printed)
        text = chunk['original_text']
        if hashlib.sha256(text.encode()).hexdigest()!=chunk['excerpt_sha256'] or text not in source_text(original['source_file'],chunk['pdf_page']):
            raise ValueError('证据原文或哈希核验失败')
        i=text.find(start); j=text.find(end,i)
        if i<0 or j<0:
            raise ValueError('E07摘录锚点改变，需人工复核')
        evidence.append(dict(evidence_id='E07_'+printed, parent_evidence_id='E07', source_type='公开年报披露',
                             source_file=original['source_file'], printed_page=printed, pdf_page=chunk['pdf_page'],
                             text=text[i:j+len(end)], related_facts=['net_profit','operating_cashflow']))
    amount=original['disclosed_amount']['value_yuan']
    if format(Decimal(amount),',.2f') not in evidence[-1]['text']:
        raise ValueError('保证金金额未匹配原文')
    facts.append(dict(fact_id='bill_deposits', name='本期票据保证金等净减少额', evidence_ids=['E07_179'],
                      amounts={'current':{'元':amount,'亿元':display_yi(Decimal(amount))}}))
    evidence[-1]['related_facts'].append('bill_deposits')
    payload=dict(company=meta['base']['company'], periods=['2024','2025'], currency='CNY',
                 scope='披露口径的合并报表；合并范围变动，非恒定主体比较',
                 question='逐层说明利润变化，并核验利润下降、经营现金流增长的披露解释。',
                 limits=['未输入营业外收入：Excel存储值与PDF不精确一致，不能补算完整利润总额桥接。',
                         '手续费及佣金收入本期为空，不当零。',
                         '金额均由Python计算；模型只引用，不新增数字。',
                         '保证金金额是本期调节项组成金额，不是经营现金流同比增量。',
                         '原始年报由用户提供；仅作本地文件与计算核验，未另行联网认证报告来源。'],
                 facts=facts,evidence=evidence)
    names=['manifest.json','inventory.json','metrics.json','source_checks.json','financial_records.json',
           'evidence.json','verification.json','normalized/metadata.json','normalized/financial.csv']
    audit=dict(source_run=folder.name, input_hashes={name:sha(folder/name) for name in names},
               source_snapshots=[{'file':i['file'],'sha256':i['sha256']} for i in inventory],
               excluded=excluded, external_content='仅通过核验的公开年报数值及必要原文；金融组内部文档和摘要不外发')
    return payload,audit
