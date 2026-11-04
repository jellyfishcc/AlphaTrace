"""Conservative, finite assertion checks; NOT general natural-language inference."""
import re
from .source_contract import digest, verified_evidence

# Distinct levels already used by LocalFacts/report_check; aliases do not merge IDs.
PARENT=r'(?:归属于母公司股东的净利润|归母净利润)'
NET=r'净利润'
ASSERTION=r'(?:同比)?(?:下降|增长|增加|减少|为|是|金额)'
TOTAL=r'(?:覆盖全部|完全解释|完整解释|全部解释|完整定量贡献|全部定量贡献|完整贡献)'


def stance(clause, start, end):
    """Classify only local denial/reporting forms; ambiguity is never auto-approved."""
    before=clause[:start];after=clause[end:]
    if re.match(r'(?:尚未|未获|未经|仍待|有待|无法)(?:核实|验证|证实|确认)',after):return 'denied'
    if re.search(r'(?:不能|无法|并未|并非|而非|而不是|不是|不等于|不应|不得|不代表|不意味着|尚未|未能|不)(?:认定为|视为|证明|认定|证明其|说明其)?$',before):
        return 'denied'
    if re.search(r'(?:不能|无法|尚不能)(?:证明|认定|认为)(?:该解释|这些项目|其)?$',before):return 'denied'
    if re.search(r'(?:的)?(?:说法|观点|结论|表述)(?:没有|缺乏|缺少|尚无|无)(?:充分)?(?:证据|依据|支持)',after):
        return 'denied'
    if re.search(r'是否|能否|如果|假如|待验证|可能|据称|有人|所谓|相比|相较|对比|不同于|区别|[“”「」?？]',clause):
        return 'ambiguous'
    return 'asserted'


def check_semantic_boundary(claim, payload, label):
    errors=[];review=[]
    facts={f['fact_id']:f for f in payload['facts']
           if payload.get('source_contract',{}).get('facts',{}).get(f['fact_id'])==digest(f)}
    ids=set(claim['metric_ids'])
    levels=ids & {'net_profit','parent_profit'}
    names={k:facts[k]['name'] for k in levels if k in facts}
    evidence={e['evidence_id']:e for e in payload['evidence']}
    limited=any(e and verified_evidence(e,payload) and '主要系' in e['text']
                for q in claim['citations'] for e in [evidence.get(q['evidence_id'])])
    verified_net_relation=any(r.get('verified') is True and r.get('target')=='operating_cashflow'
        for r in payload.get('analysis_contract',{}).get('accounting_relations',[]))
    texts=[('statement',claim['statement']),('support_limit',claim['support_limit'])]
    for field,text in texts:
        for clause in re.split(r'[，,。；;！!\n]|但是|然而|但',text):
            path=label+'.'+field
            # A lone known level with another level positively asserted is a conflict.
            wrong=None
            if levels=={'net_profit'} and names.get('net_profit')=='净利润':wrong=PARENT
            elif levels=={'parent_profit'} and names.get('parent_profit') in ('归母净利润','归属于母公司股东的净利润'):
                # Avoid matching the suffix of a correct parent label.
                clause=re.sub(PARENT,'本指标',clause);wrong=NET
            if wrong:
                for m in re.finditer(wrong,clause):
                    s=stance(clause,m.start(),m.end())
                    direct=(re.match(ASSERTION,clause[m.end():]) or re.search(r'(?:为|是|等同于|替换为|视为|即)$',clause[:m.start()]))
                    if s=='asserted' and direct:
                        errors.append(path+'：metric_scope_conflict，正文指标口径与可信事实名称不一致')
                    else:review.append(path+'：指标对比、否定或指代需人工确认，不构成口径替换授权')
            elif len(levels)>1 and re.search(PARENT,clause):
                review.append(path+'：多利润指标的文字与金额归属需逐项人工确认')
            for m in re.finditer(TOTAL,clause):
                s=stance(clause,m.start(),m.end())
                cash_context='operating_cashflow' in ids or '现金流' in clause or '净额' in clause
                direct_total=(not m[0].endswith('贡献') or re.search(r'(?:构成|等于|就是|是|作为|为)(?:净额增长的)?$',clause[:m.start()]))
                if s=='asserted' and direct_total and cash_context and limited and not verified_net_relation:
                    errors.append(path+'：support_scope_overreach，主要原因披露不支持净额完整定量归因')
                else:review.append(path+'：完整贡献表述的否定、归属或支持程度需人工复核')
    # Preserve exact original quote checks; add a diagnostic for mislabelled source rows.
    for q in claim['citations']:
        for fid in levels:
            f=facts.get(fid)
            if f and fid=='net_profit' and f['name']=='净利润' and q['evidence_id'] in f['evidence_ids']:
                if re.match(PARENT,q['quote']):
                    errors.append(label+'.citations：metric_scope_conflict，净利润来源被改称归母净利润')
    review.append(label+'：语义检查仅覆盖明确句式；未命中不证明指标指代或经营因果正确，仍需人工复核')
    return list(dict.fromkeys(errors)),list(dict.fromkeys(review))
