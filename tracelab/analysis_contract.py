"""Presentation and validation contract; reuse stage-two results, never calculate bridges."""
import copy
import csv
from decimal import Decimal
from pathlib import Path
from .stage3_input import read, sha


def configure(payload, source, mode):
    if mode not in ('full','focused'):
        raise ValueError('未知分析模式')
    payload=copy.deepcopy(payload)
    source=Path(source)
    bridges=read(source/'bridges.json')
    with (source/'directional_impacts.csv').open(encoding='utf-8-sig',newline='') as stream:
        impacts=list(csv.DictReader(stream))
    all_facts={f['fact_id']:f for f in payload['facts']}
    relations=[]
    for bridge in bridges:
        target=bridge['target']
        if target not in all_facts: continue
        verified=(bridge['relation_status']=='user_confirmed_formula' and
                  bridge['math_status']=='exact_zero_residual' and
                  all(k in all_facts for k,_ in bridge['terms']))
        if verified:
            for period in ('base','current'):
                if Decimal(bridge[period]['actual'])!=Decimal(all_facts[target]['amounts'][period]['元']):
                    raise ValueError('桥接目标与已核实事实不一致')
        components=[]
        for component,sign in bridge['terms']:
            effect='unavailable'
            if verified:
                rows=[r for r in impacts if r['level']==target and r['item_id']==component]
                if len(rows)!=1: raise ValueError('方向记录缺失或重复')
                row=rows[0]
                amounts=all_facts[component]['amounts']
                if int(row['sign'])!=sign or any(Decimal(row[a])!=Decimal(amounts[b]['元']) for a,b in
                                              [('base','base'),('current','current'),('change','change')]):
                    raise ValueError('已有方向记录与事实不一致')
                signed=Decimal(row['signed_change'])
                effect='increase' if signed>0 else 'decrease' if signed<0 else 'unchanged'
            components.append(dict(component=component,sign=str(sign),effect=effect))
        relations.append(dict(target=target,components=components,verified=verified,
                              math_status=bridge['math_status'],relation_status=bridge['relation_status']))
    if mode=='focused':
        selected={'net_profit','operating_cashflow','bill_deposits'}
        payload['facts']=[f for f in payload['facts'] if f['fact_id'] in selected]
        ids={eid for f in payload['facts'] for eid in f['evidence_ids']} | {'E07_28','E07_29','E07_179'}
        payload['evidence']=[e for e in payload['evidence'] if e['evidence_id'] in ids]
        payload['question']='仅调查净利润下降与经营现金流增长的分化；不生成利润桥接或完整报告。'
        relations=[]  # No unseen financial components or amounts in the focused request.
    payload['analysis_contract']=dict(version='v2',mode=mode,max_claims=2 if mode=='focused' else 4,
                                     ratios_allowed=False,accounting_relations=relations)
    for evidence in payload['evidence']:
        # Scope labels describe the existing excerpts; original text stays untouched.
        evidence['comparison_basis']={'E07_28':'yoy','E07_29':'current_period',
                                      'E07_179':'current_period'}.get(evidence['evidence_id'],'both_periods')
    return payload,{name:sha(source/name) for name in ('bridges.json','directional_impacts.csv')}


def check_contract(response,payload):
    contract=payload['analysis_contract']
    errors=[]
    review=[]
    if not 1<=len(response['claims'])<=contract['max_claims']:
        errors.append('结论数量超过分析模式限制')
    if not 1<=len(response['questions'])<=2 or any(len(q)>80 for q in response['questions']):
        errors.append('调查问题必须简短且为一至两条')
    relations={r['target']:r for r in contract['accounting_relations']}
    evidence={e['evidence_id']:e for e in payload['evidence']}
    facts={f['fact_id']:f for f in payload['facts']}
    for index,claim in enumerate(response['claims'],1):
        label=f'结论{index}'
        if claim['comparison_basis']=='yoy':
            for amount in claim['amounts']:
                fields=facts.get(amount['fact_id'],{}).get('amounts',{})
                if amount['field']=='current' and 'current' in fields and 'base' not in fields and 'change' not in fields:
                    errors.append(label+'仅有本期金额的项目不能作为同比解释的量化依据')
        if len(claim['statement'])>100 or len(claim['support_limit'])>140:
            errors.append(label+'解释或支持边界过长')
        for link in claim['accounting_links']:
            relation=relations.get(link['target'])
            component=next((c for c in (relation or {}).get('components',[]) if c['component']==link['component']),None)
            if not relation or not relation['verified'] or component is None:
                errors.append(label+'会计层级或关系未获输入核验支持')
            elif link['effect']!=component['effect']:
                errors.append(label+'会计影响方向与Python已核验结果不一致')
            if link['component'] not in claim['metric_ids'] or link['target'] not in claim['metric_ids']:
                errors.append(label+'会计关系未关联所引用项目')
        # Source provenance and comparison scope are checked centrally by stage3.
        review.append(label+'：核对文字是否与结构化会计关系一致；空accounting_links不证明文字没有会计错误')
        review.append(label+'：核对假设、因果强度及保证金口径；不允许未经Python核验的贡献率')
    return errors,review
