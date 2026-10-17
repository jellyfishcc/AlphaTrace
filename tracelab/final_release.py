"""Versioned final-material reconciliation; no model calls or financial engine changes."""
import argparse
import copy
import csv
import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from . import stage1
from .accounting import bridge, growth, display_yi, decimal_text
from .source_io import read_xlsx, read_docx
from .stage2 import cell, num, extract_pair, adjusted_pair, NAMES, IDS
from .stage3_input import read, sha
from .investigation import prepare_investigation

WORD='格力电器金融组核验分析报告_最终版.docx'
EXCEL='格力电器金融组核验分析底稿_最终版.xlsx'
CORE={k:('核心指标',r) for k,r in zip(['total_revenue','revenue','operating_profit','pretax_profit',
      'income_tax','net_profit','parent_profit','operating_cashflow','adjusted_parent_profit','fee_income'],range(2,12))}
CORE.update({k:('利润桥接',r) for k,r in zip(['total_cost','other_income','investment_income','fair_value_income',
             'credit_impairment','asset_impairment','disposal_income'],range(3,10))})
CORE.update({k:('成本费用与金融收益',r) for k,r in zip(IDS[5:13],range(2,10))})
CORE.update(nonoperating_income=('利润桥接',12),nonoperating_expense=('利润桥接',13))
CASH_NAMES={'经营现金流入小计':'经营活动现金流入小计','经营现金流出小计':'经营活动现金流出小计',
            '经营活动现金流净额':'经营活动产生的现金流量净额'}


def pair(sheets,sheet,row):
    return tuple(num(cell(sheets,sheet,row,col)) for col in ('B','C'))


def cache_comparison(actual,expected):
    if actual is None or expected is None: return 'both_blank' if actual is expected else 'conflict'
    if actual==expected: return 'exact'
    return 'formula_cache_rounding' if actual.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)==expected.quantize(Decimal('.01'),rounding=ROUND_HALF_UP) else 'conflict'


def enrich(rows):
    result=[]
    for row in rows:
        a,b=num(row['base_amount']),num(row['current_amount'])
        rate,reason=growth(a,b)
        d=num(row['difference'])
        result.append(dict(row,base_yi=display_yi(a) if a is not None else '',
            current_yi=display_yi(b) if b is not None else '',difference_yi=display_yi(d) if d is not None else '',
            yoy=decimal_text(rate),yoy_percent=decimal_text((rate*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if rate is not None else '',
            yoy_status=reason))
    return result


def run(source,previous,output):
    from pypdf import PdfReader
    source,previous,output=map(Path,(source,previous,output))
    for name in (WORD,EXCEL):
        if not (source/name).is_file(): raise FileNotFoundError(source/name)
    out=output/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10])
    out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','normalized','source_text'): (out/name).mkdir()
    inventory=[]; pages={}; files={}
    for item in read(previous/'inventory.json'):
        if sha(previous/'inputs'/item['file'])!=item['sha256']: raise ValueError('旧快照哈希改变')
        shutil.copy2(previous/'inputs'/item['file'],out/'inputs'/item['file'])
        inventory.append(dict(item))
        if item['key'] in ('2024','2025'):
            files[item['key']]=item['file']
            pages[item['key']]=[]
            for index,page in enumerate(PdfReader(out/'inputs'/item['file']).pages):
                text=page.extract_text() or ''
                label=next((s.strip() for s in text.splitlines()[:6] if s.strip().isdigit()),None)
                pages[item['key']].append(dict(pdf_page=index+1,printed_page=label,text=text))
    for key,name in [('final_word',WORD),('final_excel',EXCEL)]:
        shutil.copy2(source/name,out/'inputs'/name)
        inventory.append(dict(key=key,file=name,sha256=sha(out/'inputs'/name),path=str((source/name).resolve())))
    sheets=read_xlsx(out/'inputs'/EXCEL); doc=read_docx(out/'inputs'/WORD)
    stage1.write_json(out/'source_text/final_workbook.json',sheets)
    stage1.write_json(out/'source_text/final_word.json',doc)
    stage1.write_json(out/'inventory.json',inventory)
    def page(year,printed): return next(p for p in pages[year] if p['printed_page']==str(printed))
    old=read(previous/'metrics.json'); old_by={r['item_id']:r for r in old}
    normalized=[]; values={}; comparisons=[]; checks=[]; records=[]; conflicts=[]
    for key,name in zip(IDS,NAMES):
        baseline=old_by[key]
        candidate=tuple(num(baseline[c]) for c in ('base_amount','current_amount'))
        location='旧版已核实输入＋最终确认；最终Excel未单列原始行'
        if key in CORE:
            sheet,row=CORE[key];candidate=pair(sheets,sheet,row);location=f'{sheet}!B{row}:C{row}'
        p25=page('2025',88 if key=='operating_cashflow' else 6 if key=='adjusted_parent_profit' else 87)
        p24=next(p for p in pages['2024'] if re.search(r'(?m)^\s*合并现金流量表\s*$',p['text'])) if key=='operating_cashflow' else page('2024',113)
        if key=='adjusted_parent_profit': p24=next(p for p in pages['2024'] if '主要会计数据和财务指标' in p['text'] and '归属于上市公司股东' in p['text'])
        expected,excerpt=(adjusted_pair(p25,2025) if key=='adjusted_parent_profit' else extract_pair(p25,name,2025))
        prior,prior_excerpt=(adjusted_pair(p24,2024) if key=='adjusted_parent_profit' else extract_pair(p24,name,2024))
        ok=candidate==expected and candidate[0]==prior[0]
        comparisons.append(dict(item_id=key,name=name,location=location,old=[baseline['base_amount'],baseline['current_amount']],
             final=[decimal_text(v) for v in candidate],pdf=[decimal_text(v) for v in expected],
             status='same' if ok and candidate==tuple(num(baseline[c]) for c in ('base_amount','current_amount')) else 'corrected' if ok else 'conflict'))
        if not ok: conflicts.append(dict(kind='core_amount',location=location,reported=str(candidate),observed=str(expected),item_id=key))
        accepted=candidate if ok else (None,None)
        values[key]=accepted
        for year,value,pdfval,excerpt0,p in [(2024,candidate[0],expected[0],excerpt,p25),(2025,candidate[1],expected[1],excerpt,p25),(2024,candidate[0],prior[0],prior_excerpt,p24)]:
            filename=files['2025'] if p is p25 else files['2024']
            checks.append(dict(metric_name=name,fiscal_year=year,source_file=filename,pdf_page=p['pdf_page'],printed_page=p['printed_page'],
                original_text=excerpt0,pdf_yuan=decimal_text(pdfval),excel_yuan=decimal_text(value),excel_cell=location,
                status='exact_match' if value is not None and value==pdfval else 'both_missing_not_zero' if value is pdfval is None else 'pending_blank_or_mismatch'))
        row=dict(item_id=key,item_name=name,base_amount=decimal_text(accepted[0]),current_amount=decimal_text(accepted[1]),
            base_unit='元',current_unit='元',base_definition=f'合并报表/{name}',current_definition=f'合并报表/{name}',
            base_source=f'{files["2025"]} 印刷页{p25["printed_page"]} 2024列；{location}',
            current_source=f'{files["2025"]} 印刷页{p25["printed_page"]} 2025列；{location}')
        normalized.append(row)
        for year,v in zip((2024,2025),accepted):
            records.append(dict(standard_metric=key,fiscal_year=year,metric_value=decimal_text(v),
                                verification_status='exact_pdf_match' if ok and v is not None else 'pending'))
    metadata=read(previous/'normalized/metadata.json')
    stage1.write_json(out/'normalized/metadata.json',metadata)
    stage1.write_csv(out/'normalized/financial.csv',stage1.COLUMNS,normalized)
    stage1out,_=stage1.run(out/'normalized/financial.csv',out/'normalized/metadata.json',out/'stage1')
    metrics=enrich(read(stage1out/'results.json')['results'])
    stage1.write_json(out/'metrics.json',metrics)
    stage1.write_json(out/'source_checks.json',checks);stage1.write_json(out/'financial_records.json',records)
    stage1.write_json(out/'comparison.json',comparisons)
    stage1.write_csv(out/'comparison.csv',list(comparisons[0]),comparisons)
    bridges=[];impacts=[]
    for prior in read(previous/'bridges.json'):
        confirmed=prior['target']!='total_revenue'
        b=bridge(values,prior['target'],prior['terms'],'user_confirmed_formula' if confirmed else prior['relation_status'])
        b['business_status']='金融组最终确认' if confirmed else '空白保持，明细不强行求和'
        bridges.append(b)
        for key,sign in b['terms']:
            m=next(m for m in metrics if m['item_id']==key); delta=num(m['difference'])
            impacts.append(dict(level=b['target'],item_id=key,base=m['base_amount'],current=m['current_amount'],change=m['difference'],
                sign=sign,signed_change=decimal_text(delta*sign) if delta is not None else '',relation_status=b['relation_status']))
    stage1.write_json(out/'bridges.json',bridges)
    stage1.write_csv(out/'directional_impacts.csv',list(impacts[0]),impacts)
    stage1.write_json(out/'investigation_plan.json',prepare_investigation(metrics))
    shutil.copy2(previous/'evidence.json',out/'evidence.json') # E01-E07 meanings and text retained.
    # Formula caches are comparison material, never original input amounts.
    formula_checks=[]
    for key,(sheet,r) in CORE.items():
        m=next(m for m in metrics if m['item_id']==key)
        formula_checks.append(dict(location=f'{sheet}!D{r}',cached=cell(sheets,sheet,r,'D'),
            python=m['difference'],status=cache_comparison(num(cell(sheets,sheet,r,'D')),num(m['difference']))))
    # Direct cash-flow components: reuse stage1 subtraction and accounting.bridge.
    cash_rows=[];cash_refs=[]
    for r in range(2,17):
        name=cell(sheets,'经营现金流',r,'A'); label=CASH_NAMES.get(name,name)
        expected,text=extract_pair(page('2025',88),label,2025)
        raw=pair(sheets,'经营现金流',r)
        statuses=[]
        for col,value,exp in zip(('B','C'),raw,expected):
            formula=sheets['经营现金流'][r][f'{col}{r}']['formula']
            status=cache_comparison(value,exp) if formula else ('exact' if value==exp and value is not None else 'conflict')
            statuses.append(status)
        ok='conflict' not in statuses and all(v is not None for v in expected)
        if not ok: conflicts.append(dict(kind='cash_amount',location=f'经营现金流!B{r}:C{r}',reported=str(raw),observed=str(expected)))
        a,b=expected if ok else (None,None)
        key='cash_'+str(r)
        cash_rows.append(dict(item_id=key,item_name=name,base_amount=decimal_text(a),current_amount=decimal_text(b),
            base_unit='元',current_unit='元',base_definition='合并现金流/'+name,current_definition='合并现金流/'+name,
            base_source=files['2025']+' 印刷页88 2024列',current_source=files['2025']+' 印刷页88 2025列'))
        cash_refs.append(dict(item_id=key,location=f'经营现金流!B{r}:C{r}',reported=[decimal_text(v) for v in raw],
            pdf=[decimal_text(v) for v in expected],status=statuses,text=text,pdf_page=89,printed_page='88'))
    stage1.write_csv(out/'normalized/cash.csv',stage1.COLUMNS,cash_rows)
    cashout,_=stage1.run(out/'normalized/cash.csv',out/'normalized/metadata.json',out/'cash_stage1')
    cash_metrics=enrich(read(cashout/'results.json')['results'])
    cash_values={m['item_id']:(num(m['base_amount']),num(m['current_amount'])) for m in cash_metrics}
    cash_bridges=[bridge(cash_values,'cash_7',[(f'cash_{r}',1) for r in range(2,7)],'user_confirmed_formula'),
                  bridge(cash_values,'cash_15',[(f'cash_{r}',1) for r in range(8,15)],'user_confirmed_formula'),
                  bridge(cash_values,'cash_16',[('cash_7',1),('cash_15',-1)],'user_confirmed_formula')]
    stage1.write_json(out/'cash_metrics.json',cash_metrics);stage1.write_json(out/'cash_checks.json',cash_refs)
    for b in cash_bridges: b['business_status']='金融组最终确认的直接法勾稽'
    stage1.write_json(out/'cash_bridges.json',cash_bridges)
    # Additional financial-group clues: locate both raw amounts together in an original row.
    # This is a source cross-check ledger, not automatic causal acceptance or model answers.
    supplemental=[]
    for sheet,rows in sheets.items():
        if sheet in ('阅读说明','原因证据索引'): continue
        for r,cells in rows.items():
            if r==1: continue
            cols=('C','D') if sheet=='收入拆分' else ('B','C')
            cs=[cells.get(f'{col}{r}',{}) for col in cols]
            if any(c.get('formula') for c in cs): continue
            try: raw=tuple(num(c.get('value')) for c in cs)
            except Exception: continue
            if any(v is None for v in raw): continue
            if raw == (Decimal('2024'), Decimal('2025')): continue  # repeated year headers
            candidates=[]
            for p in pages['2025']:
                for line in p['text'].splitlines():
                    from .stage2 import MONEY
                    amounts=[num(v) for v in MONEY.findall(line)]
                    if raw[0] in amounts and raw[1] in amounts:
                        candidates.append(dict(source_file=files['2025'],printed_page=p['printed_page'],pdf_page=p['pdf_page'],text=line))
            if not candidates and sheet=='所得税' and 5 <= r <= 9:
                # Reconciliation tables disclose one year only. Keep each year's original row.
                cross_year=[]
                for year,printed,amount in [('2024','203',raw[0]),('2025','176',raw[1])]:
                    p=page(year,printed)
                    matches=[line for line in p['text'].splitlines() if amount in [num(v) for v in MONEY.findall(line)]]
                    if len(matches)==1:
                        cross_year.append(dict(source_file=files[year],fiscal_year=year,printed_page=printed,pdf_page=p['pdf_page'],text=matches[0]))
                if len(cross_year)==2: candidates=cross_year
            supplemental.append(dict(sheet=sheet,row=r,name=cell(sheets,sheet,r,'B' if sheet=='收入拆分' else 'A'),
                raw=[decimal_text(v) for v in raw],status='original_row_located' if candidates else 'needs_source_check',
                matches=candidates,boundary='金额同列定位，不自动证明经营因果；复用原文证据需审核项目标签和口径'))
    stage1.write_json(out/'supplemental_source_checks.json',supplemental)
    # Confirmed by visual inspection of report printed page 176: both are PRIOR-year columns.
    for r,amount in [(26,'950809072.53'),(27,'21684919.23')]:
        conflicts.append(dict(kind='period_conflict',location=f'经营现金流!B{r}:C{r}',reported=[decimal_text(v) for v in pair(sheets,'经营现金流',r)],
            observed=[amount,''],source=f'{files["2025"]} 印刷页176/PDF177',resolution='不选择版本；金额不接入Agent，待金融组修正期间'))
    for topic,reported,observed in [('所得税费用明细','175','176'),('其他经营收付款明细','177','176'),
             ('票据保证金间接法说明','178','179'),('应收账款附注编号','五、11','五、4'),('存货附注编号','五、13','五、10')]:
        conflicts.append(dict(kind='source_locator',location=topic,reported=reported,observed=observed,
                              resolution='保留最终版原文，新增年报核验定位，不回写附件'))
    # Small, exact original-report sections; no finance-team reasoning is exported.
    specs=[('E08','23','（1）营业收入构成','（2）占公司营业收入',['revenue'],'both_periods'),
      ('E09','174','61、 其他收益','62、 投资收益',['other_income'],'both_periods'),
      ('E10','174','62、 投资收益','63、 公允价值变动收益',['investment_income'],'both_periods'),
      ('E11','174','63、 公允价值变动收益','64、 信用减值损失',['fair_value_income'],'both_periods'),
      ('E12_A','174','64、 信用减值损失',None,['credit_impairment'],'both_periods'),
      ('E12_B','175','项目 本期发生额 上期发生额','65、 资产减值损失',['credit_impairment'],'both_periods'),
      ('E13','132','类别 期初余额','（4）本期实际核销',['credit_impairment'],'current_period'),
      ('E14_A','153','（3）本期计提在建工程减值准备情况',None,['asset_impairment'],'current_period'),
      ('E14_B','154','项目 期初余额',None,['asset_impairment'],'current_period'),
      ('E15','175','65、 资产减值损失','66、 资产处置收益',['asset_impairment'],'both_periods'),
      ('E16','176','项目 本期发生额 上期发生额','（2）会计利润',['income_tax'],'both_periods'),
      ('E17','176','（2）会计利润','70、 现金流量表项目',['income_tax'],'current_period'),
      ('E18','88','一、经营活动产生的现金流量：','二、投资活动产生的现金流量：',['operating_cashflow'],'both_periods'),
      ('E19','176','70、 现金流量表项目','（2）与投资活动有关的现金',['operating_cashflow','bill_deposits'],'current_period')]
    evidence=[]
    for eid,printed,start,end,related,basis in specs:
        p=page('2025',printed);i=p['text'].index(start);j=p['text'].index(end,i) if end else len(p['text'])
        text=p['text'][i:j].strip()
        evidence.append(dict(evidence_id=eid,source_type='公开年报披露',source_file=files['2025'],printed_page=printed,pdf_page=p['pdf_page'],
            text=text,excerpt_sha256=hashlib.sha256(text.encode()).hexdigest(),related_facts=related,comparison_basis=basis,
            support_limit='仅限原文披露口径；不得将汇总行拆为未经披露的原因或把本期金额解释为同比贡献'))
    stage1.write_json(out/'verified_evidence.json',evidence)
    stage1.write_json(out/'blank_items.json',[
        dict(item='手续费及佣金收入',base=decimal_text(values['fee_income'][0]),current=decimal_text(values['fee_income'][1]),change='',policy='空白不填零'),
        dict(item='净敞口套期收益',base='',current='',change='',source='合并利润表印刷页87',policy='未列示项目不加入已列示项目求和，不宣称其金额为零'),
        dict(item='以摊余成本计量的金融资产终止确认收益',base='',current='',change='',source='合并利润表印刷页87',policy='未列示项目保留空白'),
        dict(item='买入返售业务减值损失',base=decimal_text(pair(sheets,'收益及减值',6)[0]),current=decimal_text(pair(sheets,'收益及减值',6)[1]),change='',source='印刷页175',policy='空白不计算变化')])
    # Compare Word table displayed values using the existing exact results, not rounded subtraction.
    word_checks=[]
    lookup={m['item_name']:m for m in metrics+cash_metrics}
    lookup['归母净利润']=next(m for m in metrics if m['item_id']=='parent_profit')
    for ti,table in enumerate(doc['tables']):
        if not table or len(table[0])<4 or '2024' not in table[0][1]: continue
        for ri,row in enumerate(table[1:],2):
            if len(row)<4 or row[0] not in lookup: continue
            m=lookup[row[0]]
            for ci,field in [(1,'base_yi'),(2,'current_yi'),(3,'difference_yi')]:
                try: actual=num(row[ci])
                except Exception: continue
                if actual is None: continue
                expected=num(m[field])
                word_checks.append(dict(location=f'Word table{ti+1} row{ri} col{ci+1}',item=row[0],reported=row[ci],
                    python=m[field],status='exact_display' if actual==expected else 'conflict'))
    stage1.write_json(out/'word_checks.json',word_checks)
    for c in word_checks:
        if c['status']=='conflict':
            conflicts.append(dict(kind='word_display_conflict',location=c['location'],item=c['item'],
                reported=c['reported'],observed=c['python'],unit='亿元',
                resolution='Word与Excel/年报不一致；保留双方，受影响项目不新增为Agent结构化事实'))
    stage1.write_json(out/'formula_checks.json',formula_checks)
    stage1.write_json(out/'conflicts.json',conflicts)
    stage1.write_json(out/'verification.json',{'status':'passed' if all(c['status']!='conflict' for c in comparisons) else 'failed',
        'scope':'仅31项核心输入；其他冲突单列且不接入已核实数值'})
    stage1.write_json(out/'manifest.json',dict(run_id=out.name,source_revision='final',previous_run=str(previous.resolve()),
        llm_called=False,core_count=len(metrics),comparison_counts={s:sum(c['status']==s for c in comparisons) for s in ('same','corrected','conflict')},
        new_evidence_count=len(evidence),conflict_count=len(conflicts),code_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}))
    (out/'pending_questions.md').write_text('# 最终版真正待处理事项\n\n'
        '- 最终Excel经营现金流第26、27行年度列与年报印刷页176相反，请修正附件或解释期间依据。\n'
        '- 最终Word公允价值变动收益两期亿元展示与Excel/年报不一致，见word_checks.json。\n'
        '- 更新所得税、经营收付款及保证金说明页码与应收账款/存货附注编号，见conflicts.json。\n'
        '- 经营因果、合并范围变动的可比影响以及汇总行内部原因仍需具体证据；不把金额勾稽当作经营因果。\n\n'
        '已确认：原始元计算、先算后展示、空白不填零、同比边界、利润层级、营业利润列示项目及成本八项方向，不再重复询问。\n',encoding='utf-8')
    stage1.write_json(out/'release_hashes.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
    return out


def load_agent_payload(folder):
    """Explicit local-only expanded collection; never implicitly widens stage3 focused input."""
    from .stage3_input import prepare
    folder=Path(folder)
    for name,digest in read(folder/'release_hashes.json').items():
        if sha(folder/name)!=digest: raise ValueError('最终版快照内容改变')
    payload,audit=prepare(folder,mode='full')
    inventory=read(folder/'inventory.json')
    from pypdf import PdfReader
    filename=next(i['file'] for i in inventory if i['key']=='2025')
    pdf=PdfReader(folder/'inputs'/filename)
    extra=read(folder/'verified_evidence.json')
    for e in extra:
        text=pdf.pages[e['pdf_page']-1].extract_text() or ''
        if e['text'] not in text or hashlib.sha256(e['text'].encode()).hexdigest()!=e['excerpt_sha256']:
            raise ValueError('新增证据核验失败')
        if str(e['printed_page']) not in [s.strip() for s in text.splitlines()[:6]]:
            raise ValueError('页码核验失败')
    payload['evidence'].extend(extra)
    # Add only exact-verified core metrics; reuse original source-check excerpts.
    existing={f['fact_id'] for f in payload['facts']}
    disputed={c.get('item') for c in read(folder/'conflicts.json') if c['kind']=='word_display_conflict' and c.get('status')!='resolved'}
    for m in read(folder/'metrics.json'):
        if m['item_id'] in existing or m['status']!='calculated' or m['item_name'] in disputed: continue
        checks=[c for c in read(folder/'source_checks.json') if c['metric_name']==m['item_name']]
        if len(checks)!=3 or any(c['status']!='exact_match' for c in checks): continue
        c=next(c for c in checks if c['fiscal_year']==2025)
        for check in checks:
            field='base_amount' if check['fiscal_year']==2024 else 'current_amount'
            if num(m[field])!=num(check['pdf_yuan']): raise ValueError('新增事实金额与来源不符')
        if num(m['current_amount'])-num(m['base_amount'])!=num(m['difference']): raise ValueError('新增事实差额不符')
        if c['original_text'] not in (pdf.pages[c['pdf_page']-1].extract_text() or ''): raise ValueError('新增事实原文不符')
        eid='F_FINAL_'+m['item_id']
        payload['evidence'].append(dict(evidence_id=eid,text=c['original_text'],related_facts=[m['item_id']],
            source_file=filename,printed_page=c['printed_page'],pdf_page=c['pdf_page'],source_type='公开年报披露',comparison_basis='both_periods'))
        payload['facts'].append(dict(fact_id=m['item_id'],name=m['item_name'],evidence_ids=[eid],amounts={
            field:{'元':m[value],'亿元':display_yi(num(m[value]))} for field,value in
            [('base','base_amount'),('current','current_amount'),('change','difference')]}))
    for m in read(folder/'cash_metrics.json'):
        if m['status']!='calculated' or m['item_id']=='cash_16': continue
        c=next(c for c in read(folder/'cash_checks.json') if c['item_id']==m['item_id'])
        if [num(m[k]) for k in ('base_amount','current_amount')]!=[num(v) for v in c['pdf']]:
            raise ValueError('现金流事实金额与来源不符')
        if num(m['current_amount'])-num(m['base_amount'])!=num(m['difference']): raise ValueError('现金流差额不符')
        if 'conflict' in c['status'] or c['text'] not in (pdf.pages[c['pdf_page']-1].extract_text() or ''):
            raise ValueError('现金流分项未获核验')
        eid='F_FINAL_'+m['item_id']
        payload['evidence'].append(dict(evidence_id=eid,text=c['text'],related_facts=[m['item_id'],'operating_cashflow'],
            source_file=filename,printed_page=c['printed_page'],pdf_page=c['pdf_page'],source_type='公开年报披露',comparison_basis='both_periods'))
        payload['facts'].append(dict(fact_id=m['item_id'],name=m['item_name'],evidence_ids=[eid],amounts={
            field:{'元':m[value],'亿元':display_yi(num(m[value]))} for field,value in
            [('base','base_amount'),('current','current_amount'),('change','difference')]}))
    audit['extension_hashes']={name:sha(folder/name) for name in ('verified_evidence.json','cash_metrics.json','cash_checks.json')}
    from .source_contract import bind_sources
    bind_sources(payload,folder)
    return payload,audit


def main(argv=None):
    p=argparse.ArgumentParser(description='最终版离线核对与独立快照；无模型调用')
    p.add_argument('--source',type=Path,required=True);p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('outputs/final_release'))
    a=p.parse_args(argv);out=run(a.source,a.previous,a.output)
    print(out.resolve())


if __name__=='__main__': main()
