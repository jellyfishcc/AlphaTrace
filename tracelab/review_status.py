"""Separate outstanding decisions from supplied facts and historical references."""
from collections import Counter

from . import stage1


def classify(conflicts, revised):
    result=[]
    for source in conflicts:
        row=dict(source)
        status,action='待确认','核对本行原值、程序值及适用口径'
        if row['source']=='1.docx':
            status,action='历史参考','旧版差异留档，不要求金融组重复修订旧文件'
        elif row['kind']=='PAGE_LOCATOR':
            status,action='定位已核实，待文档同步','按observed所列页码更新材料，不需要重新提供财报或确认页码'
        elif row['kind']=='SCOPE_CAVEAT':
            status,action='已知比较边界','已按披露合并口径比较；后续若做恒定范围经营归因再专项核查'
        elif (revised and row['kind']=='AMOUNT_TYPE' and row['location']=='财务原始数据!C5'
              and row['message']=='缺失金额' and "'value': None" in row['reported']):
            status,action='处理已明确','修订版明确空白不填零；继续阻断该项目，不再询问是否按零处理'
        elif row['kind']=='PDF_VALUE_CHECK':
            action='同一Excel单元格对照不同年份报告的记录合并处理；确认存储精度处理方式，不重交来源'
        elif row['kind']=='REFERENCE_DIFFERENCE':
            action='核对差额或舍入；同类存储尾差统一确认规则，不逐条重复询问'
        row.update(review_status=status,next_action=action,business_status=status)
        result.append(row)
    return result


def write_review(folder, conflicts, revised):
    rows=classify(conflicts,revised)
    stage1.write_json(folder/'conflicts.json',rows)
    stage1.write_csv(folder/'conflicts.csv',list(rows[0]) if rows else
                     ['kind','source','location','reported','observed','message','business_status','review_status','next_action'],rows)
    counts=dict(Counter(r['review_status'] for r in rows))
    stage1.write_json(folder/'review_status.json',dict(counts=counts,
        note='记录数量不是独立问题数；仅review_status=待确认进入业务待办，其余保留追溯'))
    pending=[]
    if any(r['review_status']=='待确认' and r['kind'] in ('PDF_VALUE_CHECK','REFERENCE_DIFFERENCE') for r in rows):
        pending.append('金额精度与参考差额统一核对：Excel存储尾差如何规范、参考结果采用何种舍入/验收规则。'
                       '原始资料已收到，不需要再次提供。具体位置筛选conflicts.csv中review_status=待确认。')
    pending.append('完整营业利润桥接的剩余口径：仅确认尚未明确的空白项目（如净敞口套期收益）和全量字段映射。'
                   '八项成本分项已提供且核对完成，不再要求重新拆分营业总成本。' if revised else
                   '确认完整营业利润桥接映射与空白字段处理；沿用当前已核实部分。')
    resolved=(['手续费及佣金收入本期保留空白、不按零处理；该项不能计算不等于仍需确认处理方式。',
               '修订版Word利润金额数量级问题和Excel桥接文字矛盾已修正。',
               '八项成本分项已收到并核对，成本总额展开已完成。',
               'E07现金流解释及票据保证金金额已提供，原文已定位；不再要求重新提供这项证据。'] if revised else [])
    resolved += ['分析顺序及格力演示方向已确认：逐层利润拆解，调查利润下降与经营现金流增长。',
                 '按披露合并报表比较已明确；合并范围变动保留为解释边界。',
                 '来源页码已技术核实，材料同步属于编辑待办；早期Word差异仅历史留档。']
    text='# 当前待确认问题\n\n已收到的资料和已明确的处理方式不重复列为问题。\n\n'
    text+='## 金融组仍需确认\n\n'+'\n'.join(f'{i}. {q}' for i,q in enumerate(pending,1))
    text+='\n\n## 已提供或已处理，无需重复确认\n\n'+'\n'.join('- '+q for q in resolved)
    text+='\n\n## 文档同步与后续工作\n\n'
    text+='- 来源页码按冲突表observed列同步；原始附件保留，不需要重交。\n'
    if revised:
        text+='- 当前修订版Word表4营业外支出变化仍写−0.4869亿元，按原金额计算并保留四位应为−0.4870亿元；请同步或说明舍入依据。\n'
    text+='- 现金流补充表其余调节项的结构化录入属于后续技术工作，不等于E07资料未提供。\n'
    text+='- 模型凭证、服务选择及真实调用属于技术侧待办，不要求金融组补交财务资料。\n'
    text+='- 真正生成模型回答后，再逐条复核因果措辞和证据支持程度。\n'
    text+='\n## 如何使用冲突表\n\n筛选review_status=待确认处理金额问题；'
    text+='定位已核实的记录只需同步文档；处理已明确、历史参考和已知比较边界均不再重复提问。'
    text+='原值、程序值和来源均保留；分类不等于批准修改原始金额或设定容差。\n'
    (folder/'pending_questions.md').write_text(text,encoding='utf-8')
    return rows
