"""Gree case adapter. Reads supplied originals; no networking or LLM calls."""
import argparse
import hashlib
import json
import platform
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from pathlib import Path

from . import stage1
from .accounting import YI, bridge, decimal_text, display_yi, growth
from .source_io import read_docx, read_xlsx
from .investigation import prepare_investigation
from .review_status import write_review

FILES = {
    'xlsx': '格力电器金融组核验整理材料及部分归因分析_数据底稿.xlsx',
    'latest': '格力电器金融组核验整理材料及部分归因分析(1).docx',
    'early': '1.docx', 'interface': '数据接口建议.docx',
    '2024': '格力2024 年年度报告.pdf', '2025': '格力2025年年度报告.pdf',
}
REVISED_FILES = FILES | {
    'xlsx': '格力电器金融组核验整理材料及部分归因分析_数据底稿_修订版.xlsx',
    'latest': '格力电器金融组核验整理材料及部分归因分析_修订版.docx',
}


def select_files(source_dir, revision='auto'):
    if revision not in ('auto', 'original', 'revised'):
        raise ValueError('未知资料版本')
    present = [(Path(source_dir)/REVISED_FILES[k]).exists() for k in ('xlsx', 'latest')]
    if revision == 'auto' and any(present) and not all(present):
        raise ValueError('修订版 Word 与 Excel 必须成对提供，不能混用版本')
    selected = 'revised' if revision == 'revised' or (revision == 'auto' and all(present)) else 'original'
    return dict(REVISED_FILES if selected == 'revised' else FILES), selected
COMPANY = '珠海格力电器股份有限公司'
NAMES = ['营业总收入', '营业收入', '利息收入', '手续费及佣金收入', '营业总成本',
         '营业成本', '利息支出', '手续费及佣金支出', '税金及附加', '销售费用',
         '管理费用', '研发费用', '财务费用', '其他收益', '投资收益', '公允价值变动收益',
         '信用减值损失', '资产减值损失', '资产处置收益', '营业利润', '营业外收入',
         '营业外支出', '利润总额', '所得税费用', '净利润', '持续经营净利润', '终止经营净利润',
         '归属于母公司股东的净利润', '少数股东损益', '经营活动产生的现金流量净额', '归母净利润（扣非）']
IDS = ['total_revenue', 'revenue', 'interest_income', 'fee_income', 'total_cost',
       'operating_cost', 'interest_expense', 'fee_expense', 'tax_surcharges', 'selling_expense',
       'administrative_expense', 'rd_expense', 'finance_expense', 'other_income', 'investment_income',
       'fair_value_income', 'credit_impairment', 'asset_impairment', 'disposal_income', 'operating_profit',
       'nonoperating_income', 'nonoperating_expense', 'pretax_profit', 'income_tax', 'net_profit',
       'continuing_profit', 'discontinued_profit', 'parent_profit', 'minority_profit', 'operating_cashflow', 'adjusted_parent_profit']
MAPPING = dict(zip(NAMES, IDS))
MONEY = re.compile(r'-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}(?![0-9])')


def compact(text):
    return re.sub(r'\s+', '', text)


def cell(sheets, sheet, row, column):
    return sheets[sheet].get(row, {}).get(f'{column}{row}', {}).get('value')


def num(text):
    if text is None or not str(text).strip():
        return None
    result = Decimal(str(text).replace(',', '').replace('%', '').strip())
    if not result.is_finite():
        raise ValueError('非有限数值')
    return result


def find_page(pages, heading):
    found = [p for p in pages if re.search(r'(?m)^\s*'+re.escape(heading)+r'\s*$', p['text'])]
    if len(found) != 1:
        raise ValueError(f'无法唯一定位 {heading}：{len(found)} 页')
    return found[0]


def extract_pair(page, name, year):
    """Case-specific row locator, stops at row end; never fills a blank with zero."""
    lines = page['text'].splitlines()
    pattern = re.compile(r'^(?:(?:[一二三四五六七八九十0-9]+[、.])|其中：|加：|减：)?'+re.escape(name)+r'(?:\s|（|$)')
    for i, line in enumerate(lines):
        if not pattern.search(line.strip()):
            continue
        excerpt = line
        values = MONEY.findall(excerpt)
        if not values and i+1 < len(lines):
            # Parent profit label wraps in the 2024 report; continue only through
            # its closing label, never into another named financial row.
            for next_line in lines[i+1:i+4]:
                if next_line.strip().startswith(('列）', '（元）')) or MONEY.match(next_line.strip()):
                    excerpt += '\n'+next_line
                    values = MONEY.findall(excerpt)
                    if values:
                        break
                else:
                    break
        parsed = [num(v) for v in values]
        if len(parsed) >= 2:
            return (parsed[1], parsed[0]) if year == 2025 else (parsed[0], None), excerpt
        if name == '手续费及佣金收入' and year == 2025 and len(parsed) == 1:
            # Column position has been visually verified in the supplied report.
            return (parsed[0], None), excerpt
        return (None, None), excerpt
    return (None, None), ''


def adjusted_pair(page, year):
    text = page['text']
    label = '归属于上市公司股东的扣除非经常性损益的净利润（元）'
    match = re.search(r'\s*'.join(re.escape(c) for c in label), text)
    if match is None:
        return (None, None), ''
    excerpt = text[match.start():match.end()+150]
    values = [num(v) for v in MONEY.findall(text[match.end():match.end()+150])]
    if len(values) < 2:
        return (None, None), excerpt
    return ((values[1], values[0]) if year == 2025 else (values[0], None)), excerpt


def segment_lines(pages, name):
    # Two adjacent monetary columns distinguish revenue/cost from the other
    # table's revenue/percentage/prior-year-revenue layout.
    pattern=re.compile('^'+re.escape(name)+r'\s+'+MONEY.pattern+r'\s+'+MONEY.pattern+r'\s+')
    return [(p,line) for p in pages for line in p['text'].splitlines() if pattern.search(line)]


def run(source_dir, output_root, revision='auto'):
    from pypdf import PdfReader, __version__ as pdf_version
    source_dir = Path(source_dir)
    files, selected_revision = select_files(source_dir, revision)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:12]
    out = Path(output_root)/run_id
    out.mkdir(parents=True, exist_ok=False)
    (out/'inputs').mkdir()
    (out/'source_text').mkdir()
    conflicts, events, inventory, docs, pages = [], [], [], {}, {}

    def event(name, **data):
        events.append(dict(time=datetime.now(timezone.utc).isoformat(), event=name, **data))

    def conflict(kind, source, location, reported, observed, message):
        conflicts.append(dict(kind=kind, source=source, location=location,
                              reported=str(reported), observed=str(observed),
                              message=message, business_status='待金融组确认'))

    event('start', run_id=run_id)
    try:
        for key, filename in files.items():
            path = source_dir/filename
            raw = path.read_bytes()
            snapshot = out/'inputs'/filename
            snapshot.write_bytes(raw)
            item = dict(key=key, file=filename, path=str(path.resolve()), bytes=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest())
            if filename.endswith('.docx'):
                docs[key] = read_docx(snapshot)
                item.update(tables=len(docs[key]['tables']), paragraphs=len(docs[key]['paragraphs']))
                stage1.write_json(out/'source_text'/f'{key}.json', docs[key])
            elif filename.endswith('.xlsx'):
                sheets = read_xlsx(snapshot)
                item['sheets'] = list(sheets)
                stage1.write_json(out/'source_text'/'workbook_cells.json', sheets)
            else:
                reader = PdfReader(snapshot)
                pages[key] = []
                for index, page in enumerate(reader.pages):
                    text = page.extract_text() or ''
                    # Both supplied PDFs have a standalone printed page number
                    # within their first few extracted lines; no guessed offset.
                    label = next((s.strip() for s in text.splitlines()[:6] if s.strip().isdigit()), None)
                    pages[key].append(dict(pdf_page=index+1, printed_page=label, text=text))
                item['pages'] = len(pages[key])
                item['empty_pages'] = [p['pdf_page'] for p in pages[key] if not p['text'].strip()]
                if item['empty_pages']:
                    conflict('EMPTY_PDF_PAGES', filename, 'PDF', item['empty_pages'], '', '未执行OCR；空白/扫描页需确认')
                stage1.write_json(out/'source_text'/f'pdf_{key}.json', pages[key])
            inventory.append(item)
            event('source_read', **item)
        stage1.write_json(out/'inventory.json', inventory)
        income = {y: find_page(pages[y], '合并利润表') for y in ('2024', '2025')}
        cash = {y: find_page(pages[y], '合并现金流量表') for y in ('2024', '2025')}
        main = {y: next(p for p in pages[y] if '六、主要会计数据和财务指标' in p['text']) for y in ('2024', '2025')}
        for y in ('2024', '2025'):
            context = compact(income[y]['text'])
            if COMPANY not in context or '单位：人民币元' not in context or f'{y}年度' not in context:
                raise ValueError(f'{y}合并利润表主体/单位/期间不符合已确认输入')
            if not any('股票代码000651' in compact(p['text']) for p in pages[y][:10]):
                raise ValueError(f'{y}报告无法核实股票代码000651')
        base_meta = dict(company=COMPANY, currency='CNY', statement_scope='合并财务报表',
                         profit_basis='归属于母公司股东的净利润',
                         data_version='2025年报比较列，主要指标披露无需追溯调整；逐项交叉核对另列')
        metadata = dict(dataset_id='gree-2024-2025', data_kind='real', stock_code='000651',
                        comparability_confirmed=True,
                        comparability_basis='用户确认按披露的两期合并报表比较；非恒定合并范围比较',
                        base=base_meta | dict(period_start='2024-01-01', period_end='2024-12-31'),
                        current=base_meta | dict(period_start='2025-01-01', period_end='2025-12-31'))
        source_rows, checks, normalized, extended, values, pdf_values = [], [], [], [], {}, {}
        expected_headers = ['指标名称','2024年度（元）','2025年度（元）','2024年度（亿元）',
                            '2025年度（亿元）','变化额（亿元）','同比变化','来源定位','说明']
        if [cell(sheets,'财务原始数据',1,c) for c in 'ABCDEFGHI'] != expected_headers:
            raise ValueError('Excel 财务原始数据表头改变，需检查适配映射')
        names = [cell(sheets,'财务原始数据',r,'A') for r in sheets['财务原始数据'] if r > 1]
        duplicate = {n for n,c in Counter(names).items() if c > 1}
        for r in sorted(sheets['财务原始数据']):
            if r == 1:
                continue
            name = cell(sheets,'财务原始数据',r,'A')
            if name not in MAPPING:
                conflict('UNMAPPED_METRIC',files['xlsx'],f'财务原始数据!A{r}',name,'', '未猜测字段映射')
                continue
            key = MAPPING[name]
            if name in duplicate:
                conflict('DUPLICATE_METRIC',files['xlsx'],f'财务原始数据!A{r}',name,'', '重复行均不可作为计算输入')
            vals = []
            for col in 'BC':
                c = sheets['财务原始数据'][r].get(f'{col}{r}', {})
                try:
                    if c.get('kind') != 'n' or c.get('formula'):
                        raise ValueError('原始金额必须为数值常量，不能用公式缓存或文本代替')
                    val = num(c.get('value'))
                    if val is None:
                        raise ValueError('缺失金额')
                except (ValueError, InvalidOperation) as exc:
                    val = None
                    conflict('AMOUNT_TYPE',files['xlsx'],f'财务原始数据!{col}{r}',c,'',str(exc))
                vals.append(val)
            a,b = vals
            original_pair = tuple(vals)
            section = '合并利润表'
            pp = income
            if key == 'operating_cashflow':
                pp, section = cash, '合并现金流量表'
            elif key == 'adjusted_parent_profit':
                pp, section = main, '主要会计数据和财务指标'
            pair25, excerpt25 = adjusted_pair(pp['2025'],2025) if key == 'adjusted_parent_profit' else extract_pair(pp['2025'],name,2025)
            pair24, excerpt24 = adjusted_pair(pp['2024'],2024) if key == 'adjusted_parent_profit' else extract_pair(pp['2024'],name,2024)
            pdf_values[key] = pair25
            for year, actual, expected, excerpt, page in [
                    (2024,a,pair25[0],excerpt25,pp['2025']),
                    (2025,b,pair25[1],excerpt25,pp['2025']),
                    (2024,a,pair24[0],excerpt24,pp['2024'])]:
                source_year = '2024' if page is pp['2024'] else '2025'
                status = ('exact_match' if actual is not None and actual == expected else
                          'both_missing_not_zero' if actual is None and expected is None and excerpt else
                          'pending_blank_or_mismatch')
                checks.append(dict(metric_name=name, fiscal_year=year, excel_cell=f'财务原始数据!{("B" if year==2024 else "C")}{r}',
                                   excel_yuan=decimal_text(actual), pdf_yuan=decimal_text(expected), source_file=files[source_year],
                                   source_section=section, printed_page=page['printed_page'], pdf_page=page['pdf_page'],
                                   original_text=excerpt, status=status))
                if status == 'pending_blank_or_mismatch':
                    conflict('PDF_VALUE_CHECK',files['xlsx'],checks[-1]['excel_cell'],decimal_text(actual),
                             f'{files[source_year]} 印刷页{page["printed_page"]}: {decimal_text(expected) or "空白/未提取"}',
                             f'{name} {year}：不使用推算数字消除冲突')
                    # Preserve differing numeric Excel values and expose their
                    # residuals. A missing PDF value is not evidence of zero.
                    if expected is None:
                        if year == 2024: a=None
                        else: b=None
            if name in duplicate: a=b=None
            values[key]=(a,b)
            cited = cell(sheets,'财务原始数据',r,'H') or ''
            if '印刷页86' in cited and pp is income:
                conflict('PAGE_LOCATOR',files['xlsx'],f'财务原始数据!H{r}',cited,
                         f'2025印刷页{income["2025"]["printed_page"]}/PDF{income["2025"]["pdf_page"]}', '保留原出处并另存核实定位')
            sources = {side:f'{files["2025"]} | {section} | 印刷页{pp["2025"]["printed_page"]} | PDF第{pp["2025"]["pdf_page"]}页 | {year}列; Excel {col}{r}'
                       for side,year,col in [('base',2024,'B'),('current',2025,'C')]}
            normalized.append(dict(item_id=key,item_name=name,base_amount=decimal_text(a),current_amount=decimal_text(b),
                                   base_unit='元',current_unit='元',base_definition=f'合并报表/{name}',current_definition=f'合并报表/{name}',
                                   base_source=sources['base'],current_source=sources['current']))
            source_rows.append(dict(item_id=key,metric_name=name,excel_row=r,excel_base=decimal_text(original_pair[0]),
                                    excel_current=decimal_text(original_pair[1]),original_source=cited,
                                    source_section=section,printed_page=pp['2025']['printed_page'],pdf_page=pp['2025']['pdf_page']))
            for year,val,col in [(2024,a,'B'),(2025,b,'C')]:
                extended.append(dict(company=COMPANY,stock_code='000651',fiscal_year=year,currency='CNY',unit='元',
                                     statement_scope='合并',metric_name=name,standard_metric=key,metric_value=decimal_text(val),
                                     display_value_yi=display_yi(val) if val is not None else '',source_file=files['2025'],
                                     source_section=section,printed_page=pp['2025']['printed_page'],pdf_page=pp['2025']['pdf_page'],
                                     excel_cell=f'财务原始数据!{col}{r}',evidence_id='E06' if key=='adjusted_parent_profit' else 'E01' if key=='operating_cashflow' else 'E05',
                                     formula='Excel原始存储元金额；展示=元/100000000',
                                     verification_status=('pending' if val is None else 'exact_pdf_match'
                                         if val==pair25[0 if year==2024 else 1] and (year!=2024 or val==pair24[0]) else 'numeric_source_difference_pending')))
        for name in set(NAMES)-set(names):
            conflict('MISSING_METRIC',files['xlsx'],'财务原始数据',name,'缺失','不补零')
        stage1.write_json(out/'field_mapping.json',source_rows)
        stage1.write_json(out/'source_checks.json',checks)
        stage1.write_json(out/'financial_records.json',extended)
        (out/'normalized').mkdir()
        stage1.write_csv(out/'normalized/financial.csv',stage1.COLUMNS,normalized)
        stage1.write_json(out/'normalized/metadata.json',metadata)
        # Reuse existing validation, Decimal subtraction, snapshots and logs.
        stage1_folder, stage1_manifest = stage1.run(out/'normalized/financial.csv',out/'normalized/metadata.json',out/'stage1')
        first=json.loads((stage1_folder/'results.json').read_text(encoding='utf-8'))['results']
        metrics=[]
        for row in first:
            a,b=values[row['item_id']]
            rate, reason=growth(a,b)
            delta=num(row['difference'])
            metrics.append(dict(row,base_yi=display_yi(a) if a is not None else '',current_yi=display_yi(b) if b is not None else '',
                                difference_yi=display_yi(delta) if delta is not None else '',
                                yoy=decimal_text(rate),yoy_percent=decimal_text((rate*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if rate is not None else '',
                                yoy_status=reason,change_direction='unknown' if delta is None else 'increase' if delta>0 else 'decrease' if delta<0 else 'unchanged'))
        stage1.write_json(out/'metrics.json',metrics)
        stage1.write_csv(out/'metrics.csv',list(metrics[0]),metrics)
        investigation = prepare_investigation(metrics)
        stage1.write_json(out/'investigation_plan.json', investigation)
        event('stage1_reused',path=str(stage1_folder),status=stage1_manifest['status'])
        # Three user-confirmed relations; extra checks are explicitly provisional.
        specs=[('pretax_profit',[('operating_profit',1),('nonoperating_income',1),('nonoperating_expense',-1)],'user_confirmed_formula'),
               ('net_profit',[('pretax_profit',1),('income_tax',-1)],'user_confirmed_formula'),
               ('parent_profit',[('net_profit',1),('minority_profit',-1)],'user_confirmed_formula'),
               ('operating_profit',[(k,-1 if k=='total_cost' else 1) for k in ['total_revenue','total_cost','other_income','investment_income','fair_value_income','credit_impairment','asset_impairment','disposal_income']],'selected_reported_aggregates_not_full_bridge'),
               ('total_cost',[(k,1) for k in ['operating_cost','interest_expense','fee_expense','tax_surcharges','selling_expense','administrative_expense','rd_expense','finance_expense']],'report_structure_check_pending_acceptance'),
               ('total_revenue',[(k,1) for k in ['revenue','interest_income','fee_income']],'report_structure_check_pending_blank_policy')]
        bridges=[bridge(values,*spec) for spec in specs]
        pdf_bridges=[bridge(pdf_values,*spec) for spec in specs[:3]]
        for br in pdf_bridges:
            br['amount_basis']='separately_extracted_original_PDF; does_not_replace_Excel'
        stage1.write_json(out/'pdf_reference_bridges.json',pdf_bridges)
        impacts=[]
        for br in bridges:
            for key,sign in br['terms']:
                a,b=values.get(key,(None,None))
                delta=b-a if a is not None and b is not None else None
                impacts.append(dict(level=br['target'],item_id=key,metric_name=dict(zip(IDS,NAMES))[key],
                                    base=decimal_text(a),current=decimal_text(b),change=decimal_text(delta),sign=sign,
                                    signed_change=decimal_text(delta*sign) if delta is not None else '',
                                    formula=f'{sign} * (current - base)',relation_status=br['relation_status'],
                                    source=next(r['current_source'] for r in normalized if r['item_id']==key),
                                    business_status='待金融组确认'))
        stage1.write_json(out/'bridges.json',bridges)
        bridge_rows=[]
        for basis,collection in [('Excel原始存储金额',bridges),('PDF原始披露金额（单独参考）',pdf_bridges)]:
            for br in collection:
                bridge_rows.append(dict(amount_basis=basis,target=br['target'],
                    formula=' + '.join(f'{sign}*{key}' for key,sign in br['terms']),
                    base_reported=br['base']['actual'],base_calculated=br['base']['calculated'],base_residual=br['base']['residual'],
                    current_reported=br['current']['actual'],current_calculated=br['current']['calculated'],current_residual=br['current']['residual'],
                    change_residual=br['change_residual'],math_status=br['math_status'],
                    relation_status=br['relation_status'],business_status=br['business_status'],unit='元'))
        stage1.write_csv(out/'bridge_checks.csv',list(bridge_rows[0]),bridge_rows)
        stage1.write_csv(out/'directional_impacts.csv',list(impacts[0]),impacts)
        comparisons = compare_references(sheets,docs,metrics,bridges,impacts,conflict,files)
        cost_comparisons = [r for r in comparisons if r['location'].startswith('营业总成本分项!')]
        stage1.write_json(out/'cost_detail_checks.json', cost_comparisons)
        cost_impacts = []
        for row in impacts:
            if row['level'] == 'total_cost':
                cost_impacts.append(dict(row, level='operating_profit_via_total_cost', sign=-1,
                    signed_change=decimal_text(-num(row['change'])) if row['change'] else '',
                    formula='-(current - base)',
                    note='营业总成本的展开明细，不能与营业总成本总额重复计入营业利润桥接'))
        stage1.write_json(out/'cost_directional_impacts.json', cost_impacts)
        stage1.write_json(out/'human_comparison.json',comparisons)
        stage1.write_csv(out/'human_comparison.csv',list(comparisons[0]),comparisons)
        evidence=prepare_evidence(sheets,pages['2025'],income['2025'],conflict,files)
        stage1.write_json(out/'evidence.json',evidence)
        for task in investigation['investigation_tasks']:
            if task['id'] == 'profit_cashflow_reconciliation' and any(e['evidence_id']=='E07' for e in evidence):
                task['available_evidence_ids'] = ['E07']
                task['questions'].insert(0, '核验年报对收现增加、受限资金到期收回的披露；区分现金流同比变化与本期利润现金流差额。')
        stage1.write_json(out/'investigation_plan.json', investigation)
        segment_checks=[]
        segment_pages=[p for p in pages['2025'] if p['printed_page'] in ('23','24')]
        for r in range(2,6):
            name=cell(sheets,'分产品与地区',r,'A')
            matching=segment_lines(segment_pages,name)
            for col,index in [('B',0),('C',1)]:
                expected=num(cell(sheets,'分产品与地区',r,col))
                actual=num(MONEY.findall(matching[0][1])[index]) if len(matching)==1 else None
                segment_checks.append(dict(name=name,excel_cell=f'分产品与地区!{col}{r}',excel_value=decimal_text(expected),
                                           pdf_value=decimal_text(actual),status='exact_match' if expected==actual and actual is not None else 'pending',
                                           printed_page=matching[0][0]['printed_page'] if len(matching)==1 else '',
                                           original_text=matching[0][1] if len(matching)==1 else ''))
                if actual is None or expected!=actual:
                    conflict('SEGMENT_CHECK',files['xlsx'],f'分产品与地区!{col}{r}',expected,actual,'未自动推算分部数据')
        stage1.write_json(out/'segment_checks.json',segment_checks)
        # Explicitly preserve narrative contradictions; never overwrite originals.
        note=cell(sheets,'利润归因桥接',30,'A') or ''
        if '存在差额' in note:
            conflict('INTERNAL_REFERENCE_CONTRADICTION',files['xlsx'],'利润归因桥接!A30 vs E13',note,
                     f'E13={cell(sheets,"利润归因桥接",13,"E")}; 程序选定总额残差={bridges[3]["change_residual"]}',
                     '文字与数值不一致；数学闭合不代表完整桥接已验收')
        for i, paragraph in enumerate(docs['latest']['paragraphs'],1):
            if '合并利润表' in paragraph and ('印刷页86' in paragraph or '印刷页112' in paragraph):
                conflict('PAGE_LOCATOR',files['latest'],f'Paragraph {i}',paragraph,
                         f'2024印刷页{income["2024"]["printed_page"]}；2025印刷页{income["2025"]["printed_page"]}', '请更新金融组来源定位')
        scope_page=next((p for p in pages['2025'] if p['printed_page']=='24'),None)
        if scope_page and '合并范围的变更' in scope_page['text']:
            conflict('SCOPE_CAVEAT',files['2025'],'印刷页24/合并范围变动', '两期均为合并报表',
                     '报告披露合并范围发生变动，附注六说明', '允许披露口径差额计算；恒定主体范围经营归因仍待确认')
        conflicts = write_review(out, conflicts, selected_revision=='revised')
        blank_note = ('修订版已明确空白不填零；继续阻断该项目，无需重复确认。'
                      if selected_revision=='revised' else '空白项目不按零计算。')
        summary=dict(run_id=run_id,status='completed_with_pending_confirmation',input_files=len(inventory),
                     source_revision=selected_revision, selected_files=files,
                     cost_detail_checks=len(cost_comparisons),
                     metric_count=len(metrics),calculated=sum(m['status']=='calculated' for m in metrics),
                     blocked=sum(m['status']=='blocked' for m in metrics),pdf_checks=dict(Counter(c['status'] for c in checks)),
                     comparison_counts=dict(Counter(c['status'] for c in comparisons)),evidence_records=len(evidence),
                     conflict_count=len(conflicts),bridge_status=[{'target':b['target'],'math_status':b['math_status'],'change_residual':b['change_residual']} for b in bridges],
                     pdf_reference_bridge_status=[{'target':b['target'],'math_status':b['math_status'],'change_residual':b['change_residual']} for b in pdf_bridges],
                     business_acceptance='pending',llm_called=False,python=platform.python_version(),pypdf=pdf_version,
                     code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
                     note='第二阶段基础能力完成，完整桥接仍待金融组确认')
        stage1.write_json(out/'manifest.json',summary)
        (out/'summary.md').write_text('# 第二阶段运行结果\n\n'+summary['note']+'。\n\n'+
            '分析顺序：营业利润 → 利润总额 → 净利润 → 少数股东损益核对 → 归母净利润。\n\n'+
            '实际信号：'+('；'.join(s['description'] for s in investigation['signals']) or '未识别到利润下降且经营现金流增长的组合；仍保留逐层利润调查')+'。\n\n'+
            '调查准备见 investigation_plan.json；尚未执行 Agent 或经营因果分析。\n\n'+
            f'读取{len(inventory)}个附件；{len(metrics)}个项目，{summary["calculated"]}个已计算，{summary["blocked"]}个阻断。\n\n'+
            f'资料版本：{selected_revision}；成本明细核对{len(cost_comparisons)}项；证据{len(evidence)}条。{blank_note}\n\n'+
            '\n'.join(f'- {b["target"]}: {b["math_status"]}；2024残差={b["base"]["residual"]}元；2025残差={b["current"]["residual"]}元；变化残差={b["change_residual"]}元；业务待确认。' for b in bridges)+
            '\n\n详细核对：human_comparison.csv；冲突：conflicts.csv；原文：evidence.json；待办：pending_questions.md。\n',encoding='utf-8')
        event('finished',**summary)
        return out,summary
    except Exception as exc:
        stage1.write_json(out/'failure.json',dict(status='failed',error=str(exc),inputs_read=inventory))
        event('failed',error=str(exc))
        raise
    finally:
        (out/'events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events),encoding='utf-8')


def compare_references(sheets,docs,metrics,bridges,impacts,conflict,files=None):
    files = files or FILES
    by_name={m['item_name']:m for m in metrics}
    output=[]

    def add(name,field,actual,ref,source,location,unit,precision=None,note=''):
        a=num(actual) if actual not in (None,'') else None
        try:
            b=num(ref)
        except InvalidOperation:
            b=None
        diff=a-b if a is not None and b is not None else None
        rounded=a.quantize(Decimal(1).scaleb(-precision),rounding=ROUND_HALF_UP) if a is not None and precision is not None else a
        rounded_ref=b.quantize(Decimal(1).scaleb(-precision),rounding=ROUND_HALF_UP) if b is not None and precision is not None else b
        status=('not_numerically_comparable' if a is None or b is None else 'exact_match' if diff==0 else
                'display_rounding_match' if precision is not None and rounded==rounded_ref else 'difference_pending')
        output.append(dict(metric_name=name,field=field,program_value=decimal_text(a),human_value=str(ref or ''),
                           difference=decimal_text(diff),program_rounded=decimal_text(rounded),human_rounded=decimal_text(rounded_ref),unit=unit,
                           reference_precision=precision,status=status,source_file=source,location=location,
                           note=note,business_status='待金融组确认'))
        if status=='difference_pending':
            conflict('REFERENCE_DIFFERENCE',source,location,ref,decimal_text(a),f'{name}/{field}；保留差异，不修改人工答案')

    for r in sheets['财务原始数据']:
        name=cell(sheets,'财务原始数据',r,'A')
        if name not in by_name: continue
        m=by_name[name]
        for col,field in [('B','base_amount'),('C','current_amount'),('D','base_yi'),('E','current_yi'),('F','difference_yi'),('G','yoy')]:
            sourcefield={'base_yi':'base_amount','current_yi':'current_amount','difference_yi':'difference'}.get(field,field)
            actual=m[sourcefield]
            if field.endswith('_yi') and actual: actual=decimal_text(Decimal(actual)/YI)
            add(name,field,actual,cell(sheets,'财务原始数据',r,col),files['xlsx'],f'财务原始数据!{col}{r}',
                '亿元' if field.endswith('_yi') else 'ratio' if field=='yoy' else '元',6 if field.endswith('_yi') else None,
                '原金额与适配值核对非独立验收' if col in 'BC' else '普通同比在非正基数/跨符号时不计算' if col=='G' else '')
    # Latest Word table amounts and rates; table 4 is intentionally included to expose its unit errors.
    aliases={'归母净利润':'归属于母公司股东的净利润','扣非归母净利润':'归母净利润（扣非）'}
    for version,table_ids in [('latest',[1,2,3,7,8]),('early',[1,2,3])]:
        for ti in table_ids:
            for ri,row in enumerate(docs[version]['tables'][ti][1:],2):
                label=re.sub(r'^(加：|减：)','',row[0])
                name=aliases.get(label,label)
                if name not in by_name: continue
                m=by_name[name]
                fields=[(1,'base_amount'),(2,'current_amount')]
                if ti in (1,2,3,7) and version=='latest': fields.append((3,'difference'))
                if version=='early' and ti in (2,3): fields.append((3,'difference'))
                for ci,field in fields:
                    reference=row[ci].replace(',','').strip()
                    if not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?',reference):
                        if version=='latest' and ti==3 and field=='difference':
                            number=re.match(r'[+-]?[0-9]+(?:\.[0-9]+)?',reference)
                            if number: reference=number.group()
                            else:
                                add(name,field,None,reference,files[version],f'Table 4 R{ri} C{ci+1}','亿元',None,'仅解释/方向，无精确数值可验收')
                                continue
                        else: continue
                    yuan=version=='early' and ti==1
                    actual=num(m[field]); actual=actual if yuan or actual is None else actual/YI
                    places=len(reference.split('.')[1]) if '.' in reference else 0
                    add(name,field,actual,reference,files[version],f'Table {ti+1} R{ri} C{ci+1}',
                        '元' if yuan else '亿元',places,'早期版本仅比较，不覆盖最新版' if version=='early' else '')
                if ti==2:
                    add(name,'yoy_percent',num(m['yoy'])*100 if m['yoy'] else None,row[4],files[version],f'Table 3 R{ri} C5','%',2)
    # Excel's selected contributions are explicit numeric human references.
    imap={i['metric_name']:i for i in impacts if i['level']=='operating_profit'}
    for r in range(3,11):
        name=cell(sheets,'利润归因桥接',r,'A')
        if name in imap:
            actual=num(imap[name]['signed_change'])
            add(name,'selected_operating_profit_impact',actual/YI if actual is not None else None,
                cell(sheets,'利润归因桥接',r,'E'),files['xlsx'],f'利润归因桥接!E{r}','亿元',None,
                '选定总额方向性贡献，非全量业务验收')
    for br in bridges:
        if br['target']=='operating_profit':
            add('营业利润','selected_change_residual',num(br['change_residual'])/YI if br['change_residual'] else None,
                cell(sheets,'利润归因桥接',13,'E'),files['xlsx'],'利润归因桥接!E13','亿元',None)
    for r in range(17,26):
        name=cell(sheets,'利润归因桥接',r,'A')
        name=aliases.get(name,name)
        if name not in by_name: continue
        for col,field in [('B','base_amount'),('C','current_amount'),('D','difference')]:
            actual=num(by_name[name][field])
            add(name,field,actual/YI if actual is not None else None,cell(sheets,'利润归因桥接',r,col),
                files['xlsx'],f'利润归因桥接!{col}{r}','亿元',None,'Excel桥接表原始存储精度；不预设容差')
    if '营业总成本分项' in sheets:
        sheet = '营业总成本分项'
        cost_bridge = next(b for b in bridges if b['target']=='total_cost')
        cost_names = {dict(zip(IDS,NAMES))[key] for key,_ in cost_bridge['terms']}
        labels = [cell(sheets,sheet,r,'A') for r in sheets[sheet] if r>1]
        counts = Counter(labels)
        for name in cost_names:
            if counts[name] != 1:
                conflict('COST_DETAIL_STRUCTURE',files['xlsx'],sheet,name,counts[name], '成本明细必须唯一且完整，不能重复相加')
        for r in sheets[sheet]:
            label = cell(sheets,sheet,r,'A')
            if label not in cost_names | {'分项合计','营业总成本（年报）'}: continue
            name = '营业总成本' if label in ('分项合计','营业总成本（年报）') else label
            m = by_name[name]
            a,b = num(m['base_amount']),num(m['current_amount'])
            if label=='分项合计':
                a,b = num(cost_bridge['base']['calculated']),num(cost_bridge['current']['calculated'])
            delta = b-a if a is not None and b is not None else None
            entries=[('B','base_amount',a,'元'),('C','current_amount',b,'元'),
                     ('D','base_yi',a/YI if a is not None else None,'亿元'),
                     ('E','current_yi',b/YI if b is not None else None,'亿元'),
                     ('F','difference_yi',delta/YI if delta is not None else None,'亿元'),
                     ('G','operating_profit_impact',-delta/YI if delta is not None else None,'亿元')]
            for col,field,actual,unit in entries:
                add(label,field,actual,cell(sheets,sheet,r,col),files['xlsx'],f'{sheet}!{col}{r}',unit,
                    None,'明细与总额不可重复计入桥接；保留Excel原始存储尾差')
        for r in sheets[sheet]:
            if cell(sheets,sheet,r,'A')=='分项与年报总额差异（亿元）':
                residual=num(cost_bridge['change_residual'])
                add('营业总成本','detail_change_minus_reported',-residual/YI if residual is not None else None,
                    cell(sheets,sheet,r,'F'),files['xlsx'],f'{sheet}!F{r}','亿元',None)
    return output


def prepare_evidence(sheets,pages,income,conflict,files=None):
    files = files or FILES
    by_print={p['printed_page']:p for p in pages if p['printed_page']}
    records=[]
    page_ids={'E01':['9'],'E02':['9'],'E03':['9'],'E04':['23','24'],'E05':[income['printed_page']],'E06':['6','7','8'],
              'E07':['28','29','178','179']}
    ranges={'E01':('2025 年，公司实现','57.93%。'),
            'E02':('2025 年，家电行业整体承压','同比下降 3.9%。'),
            'E03':('根据产业在线数据，2025 年中国家用空调行业','市场需求回落等因素影响。')}
    related={'E01':['total_revenue','parent_profit','operating_cashflow'],'E02':['revenue'],
             'E03':['revenue'],'E04':['revenue','operating_cost'],'E05':['operating_profit','parent_profit','income_tax','other_income'],
             'E06':['adjusted_parent_profit','parent_profit'],'E07':['net_profit','operating_cashflow']}
    seen = set()
    for r in sorted(sheets['证据台账']):
        if r==1: continue
        eid=cell(sheets,'证据台账',r,'A')
        if not eid: continue
        if eid not in page_ids or eid in seen:
            conflict('EVIDENCE_ID',files['xlsx'],f'证据台账!A{r}',eid,'','未适配或重复的证据ID，不能静默忽略')
            continue
        seen.add(eid)
        chunks=[]
        for printed in page_ids[eid]:
            page=by_print.get(printed)
            if not page:
                conflict('EVIDENCE_PAGE_MISSING',files['2025'],eid,printed,'','需人工定位')
                continue
            excerpt=page['text']
            if eid in ranges:
                start,end=ranges[eid]
                a=excerpt.find(start); b=excerpt.find(end,a)
                if a<0 or b<0:
                    conflict('EVIDENCE_ANCHOR',files['2025'],eid,start,end,'锚点未找到，保留完整页待复核')
                else: excerpt=excerpt[a:b+len(end)]
            chunks.append(dict(printed_page=printed,pdf_page=page['pdf_page'],original_text=excerpt,
                               excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest()))
        records.append(dict(evidence_id=eid,company=COMPANY,stock_code='000651',fiscal_year=2025,
                            source_file=files['2025'],source_section='合并利润表' if eid=='E05' else cell(sheets,'证据台账',r,'C'),
                            printed_page=[c['printed_page'] for c in chunks],pdf_page=[c['pdf_page'] for c in chunks],
                            reported_location=cell(sheets,'证据台账',r,'C'),
                            actual_location=[{'printed_page':c['printed_page'],'pdf_page':c['pdf_page']} for c in chunks],
                            chunks=chunks,related_metrics=related[eid],question=cell(sheets,'证据台账',r,'B'),
                            finance_summary_not_quote=cell(sheets,'证据台账',r,'D'),
                            support_boundary=cell(sheets,'证据台账',r,'E'),
                            verification_status='original_pdf_text_extracted; causal_assessment_not_performed',
                            note='PDF提取换行可能与排版不同；摘要不能替代原文'))
        if eid=='E07':
            text = compact('\n'.join(c['original_text'] for c in chunks if c['printed_page']=='179'))
            amount = re.search(r'票据保证金等净减少额('+MONEY.pattern+r')元',text)
            amount_value = num(amount.group(1)) if amount else None
            records[-1]['disclosed_amount'] = dict(metric='票据保证金等净减少额', fiscal_year=2025,
                value_yuan=decimal_text(amount_value), printed_page='179',
                nature='本期调节项目的组成金额；不是经营现金流同比增量',
                status='extracted' if amount else 'pending')
            if not amount:
                conflict('EVIDENCE_AMOUNT',files['2025'],'E07/印刷页179','票据保证金等净减少额','','金额未唯一提取')
            conflict('PAGE_LOCATOR',files['xlsx'],f'证据台账!C{r}',cell(sheets,'证据台账',r,'C'),
                     '同比说明印刷28/PDF29；净利润差异说明印刷29/PDF30；补充表印刷178/PDF179；保证金注释印刷179/PDF180',
                     '现金流解释和保证金金额跨页，需补全原始定位')
    return records


def main(argv=None):
    parser=argparse.ArgumentParser(description='TraceLab 第二阶段格力案例（不调用LLM）')
    parser.add_argument('--source-dir',required=True,type=Path)
    parser.add_argument('--output',default=Path('outputs/stage2'),type=Path)
    parser.add_argument('--revision', choices=('auto','original','revised'), default='auto',
                        help='默认成对优先选择修订版；original 可复现旧资料')
    args=parser.parse_args(argv)
    try:
        folder,summary=run(args.source_dir,args.output,args.revision)
    except (ValueError,OSError,KeyError,InvalidOperation) as exc:
        print(f'第二阶段失败：{exc}')
        return 1
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(f'output={folder.resolve()}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
