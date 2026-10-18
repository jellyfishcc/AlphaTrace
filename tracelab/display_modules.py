"""Read-only projections of existing offline results; no model calls."""
from pathlib import Path
import csv
from .stage3_input import read, sha
from .report_check import check_claim
from .pdf_extract import extract_pdf, compare


def section(kind, title, columns, rows, notices, run_id, hashes):
    return dict(kind=kind, title=title, columns=columns, rows=rows, notices=notices,
                runId=run_id, hashes=hashes)


def row(cells, links=()):
    return dict(cells=['未提供' if c is None or c == '' else str(c) for c in cells], evidenceIds=list(links))


def report_section(folder, snapshot, payload, audit):
    folder = Path(folder)
    result = read(folder/'result.json')
    source = result.get('source_audit', {})
    for key in ('source_run', 'input_hashes', 'extension_hashes'):
        if source.get(key) != audit.get(key): raise ValueError('report_snapshot_mismatch')
    expected = check_claim(result['claim'], payload, simulation=False)
    if {k:v for k,v in result.items() if k != 'source_audit'} != expected:
        raise ValueError('report_result_mismatch')
    claim = result['claim']
    example = read(Path(__file__).resolve().parents[1]/'examples/report_check/gree_direction_error.json')
    if claim != example: raise ValueError('unsupported_claim_origin')
    links = [s['evidence_id'] for s in result['sources']]
    rows = [row(['核查状态',result['status']], links), row(['原始陈述',claim['original_text']])]
    rows += [row([k,v]) for k,v in claim.items() if k != 'original_text']
    rows += [row(['错误类型', '、'.join(result['errors']) or '未发现可确定错误']), row(['纠错建议',result['correction']],links)]
    rows += [row(['可信事实 '+k,v],links) for k,v in result.get('expected',{}).items()]
    rows += [row(['核验过程',v]) for v in result['process']]
    return section('report','结构化研报纠错',['字段','后端结果'],rows,
        ['人为构造的错误陈述，不是真实已发表研报。','离线结果回放；仅支持结构化陈述，原文转写、复杂语义和经营因果需要人工复核。'],folder.name,{'result.json':sha(folder/'result.json')})


def pdf_section(folder, snapshot, payload):
    folder = Path(folder)
    rows, audit, comparisons = [read(folder/f) for f in ('extracted_financial.json','extraction_audit.json','comparison.json')]
    if Path(audit['source_run']).resolve() != snapshot.resolve(): raise ValueError('pdf_snapshot_mismatch')
    if audit['records'] != rows or audit['extracted_json_sha256_before_comparison'] != sha(folder/'extracted_financial.json'):
        raise ValueError('pdf_output_hash_mismatch')
    sources = [s for s in read(snapshot/'inventory.json') if s['key']=='2025']
    if len(sources)!=1 or Path(sources[0]['file']).name!=sources[0]['file']: raise ValueError('pdf_source_mismatch')
    source=sources[0]
    fresh, fresh_audit = extract_pdf(snapshot/'inputs'/source['file'],source['sha256'])
    if fresh != rows or fresh_audit['page_text_sha256'] != audit['page_text_sha256']:
        raise ValueError('pdf_reextraction_mismatch')
    if compare(rows,payload) != comparisons: raise ValueError('pdf_comparison_mismatch')
    display=[]
    for r,c in zip(rows,comparisons):
        display.append(row([r['metric_name'],r['fiscal_year'],r['value'],c['trusted_value'],r['unit'],
            r['source_file'],r['pdf_page'],r['printed_page'],r['extraction_status'],c['status'],r['raw_row_text'],r['source_hash']],c.get('evidence_ids',[])))
    return section('pdf','PDF 原文提取 → 金额结构化 → 来源核验 → 财务分析',
        ['科目','年份','PDF 提取值','可信事实值','单位','来源','PDF 页','印刷页','提取状态','核对状态','原始行','来源 SHA256'],display,
        ['离线结果回放；指定格力年报合并利润表、页码及科目映射，金额来自 PDF 文本。',
         '两期均采用 2025 年报比较列；同源一致性核对不是独立第三方审计。不支持任意 PDF、OCR 或在线上传。'],folder.name,
        {f:sha(folder/f) for f in ('extracted_financial.json','comparison.json','extraction_audit.json')})


def financial_sections(snapshot, payload):
    names=['bridges.json','cash_bridges.json','directional_impacts.csv','revision_checks.json','conflicts.json']
    hashes=read(snapshot/'release_hashes.json')
    for name in names:
        if hashes.get(name)!=sha(snapshot/name): raise ValueError('financial_display_hash_mismatch')
    metrics={m['item_id']:m for f in ('metrics.json','cash_metrics.json') for m in read(snapshot/f)}
    with (snapshot/'directional_impacts.csv').open(encoding='utf-8-sig',newline='') as stream:
        impacts={(r['level'],r['item_id']):r for r in csv.DictReader(stream)}
    facts={f['fact_id']:f for f in payload['facts']}
    def links(key): return facts.get('operating_cashflow' if key=='cash_16' else key,{}).get('evidence_ids',[])
    result=[]
    revision=read(snapshot/'revision_checks.json')
    for name,kind in [('bridges.json','profit'),('cash_bridges.json','cash')]:
        for bridge in read(snapshot/name):
            target=bridge['target']; m=metrics[target]
            if not any(b['file']==name and b['target']==target and b['math_status']==bridge['math_status'] for b in revision['bridges']):
                raise ValueError('bridge_revision_mismatch')
            rows=[row(['目标：'+m['item_name'],m['base_amount'],m['current_amount'],m['difference'],None,'目标',bridge['math_status']],links(target))]
            for key,sign in bridge['terms']:
                item=metrics[key]; impact=impacts.get((target,key),{})
                if kind=='profit' and str(sign)!=impact.get('sign'): raise ValueError('impact_relation_mismatch')
                rows.append(row([item['item_name'],item['base_amount'],item['current_amount'],item['difference'],impact.get('signed_change'),str(sign),'组成项'],links(key)))
            rows += [row(['后端组成项合计',bridge['base']['calculated'],bridge['current']['calculated'],None,None,None,None]),
                     row(['残差（披露目标 − 组成项）',bridge['base']['residual'],bridge['current']['residual'],bridge['change_residual'],None,None,bridge['math_status']])]
            result.append(section(kind,m['item_name']+' · '+bridge['math_status'],
                ['项目','基期（元）','本期（元）','自身变化（元）','对本目标影响（元）','会计符号','状态'],rows,
                ['逐个目标展示，父子项目不重复加总。金额及残差直接取自后端，网页不计算。',
                 '现金流贡献未提供时保持缺失；闭合不证明经营因果。缺失项：'+', '.join(bridge['current']['missing'])],snapshot.name,{name:hashes[name],'directional_impacts.csv':hashes['directional_impacts.csv']}))
    conflicts=read(snapshot/'conflicts.json')
    resolved=sum(c['status']=='resolved' for c in conflicts)
    if resolved!=revision['resolved'] or len(conflicts)-resolved!=revision['unresolved']: raise ValueError('conflict_revision_mismatch')
    rows=[row(['核心输入',revision['core_count'],'未改变' if revision['core_unchanged'] else '已改变',None,None,None]),
          row(['历史冲突已解决',resolved,'resolved',None,None,None]),row(['当前未解决',revision['unresolved'],'当前修订快照',None,None,None])]
    for c in conflicts:
        for v in c['verification']:
            rows.append(row(['历史 '+c['kind'],None,c['status'],v['source_file'],v['pdf_page'],v['printed_page']]))
    result.append(section('verification','财务来源核验及历史冲突',['项目','数量或年份','状态','公开来源','PDF 页','印刷页'],rows,
        ['历史冲突采用最终修订状态，不复用旧的待修正说明；内部原文不导出。',
         '经营因果仍需人工复核；cash_26、cash_27 本期空白，不计算变化，不开放为同比事实。'],snapshot.name,{n:hashes[n] for n in names}))
    return result
