"""Prepare questions from computed signals; never infer operating causes."""
from decimal import Decimal


def prepare_investigation(metrics):
    by_id = {row['item_id']: row for row in metrics}

    def change(key):
        row = by_id.get(key, {})
        value = row.get('difference')
        return Decimal(value) if row.get('status') == 'calculated' and value not in (None, '') else None

    layers = [
        ('operating_profit', '营业利润', ['total_revenue', 'total_cost', 'other_income', 'investment_income', 'fair_value_income', 'credit_impairment', 'asset_impairment', 'disposal_income'], '选定总额核对；全量映射待确认'),
        ('pretax_profit', '利润总额', ['operating_profit', 'nonoperating_income', 'nonoperating_expense'], '利润总额 = 营业利润 + 营业外收入 - 营业外支出'),
        ('net_profit', '净利润', ['pretax_profit', 'income_tax'], '净利润 = 利润总额 - 所得税费用'),
        ('minority_profit', '少数股东损益', [], '单独核对少数股东损益变化及其在归属分配中的影响'),
        ('parent_profit', '归母净利润', ['net_profit', 'minority_profit'], '归母净利润 = 净利润 - 少数股东损益'),
    ]
    chain = [dict(item_id=key, name=name, difference=by_id.get(key, {}).get('difference', ''),
                  status=by_id.get(key, {}).get('status', 'missing'), components=components, relation=relation)
             for key, name, components, relation in layers]
    signals = []
    net, cash = change('net_profit'), change('operating_cashflow')
    if net is not None and cash is not None and net < 0 < cash:
        signals.append(dict(id='profit_down_cashflow_up', profit_basis='net_profit',
                            profit_difference=str(net), cashflow_difference=str(cash),
                            description='净利润下降、经营活动现金流量净额增长，两者走势分化'))
    tasks = [dict(id='layered_profit_analysis', reason='所有案例均先进行利润层级拆解，无须预设异常触发',
                  questions=['营业利润各组成项发生了什么变化？', '营业外收支与所得税如何影响后续利润层级？',
                             '少数股东损益变化如何影响净利润向归母净利润的归属分配？'])]
    if signals:
        tasks.append(dict(id='profit_cashflow_reconciliation', reason='profit_down_cashflow_up',
                          questions=['现金流量表和补充资料如何解释净利润与经营现金流的变化？',
                                     '营运资本、非现金项目及其他调节项中，哪些有原文和数值支持？',
                                     '合并范围变化是否影响两期比较？'],
                          required_sources=['合并现金流量表', '现金流量表补充资料', '相关附注与合并范围说明']))
    return dict(status='questions_prepared_not_executed',
                entry_policy='先查看业绩变化，再根据实际信号选择调查；不以特定异常作为入口门槛',
                materiality='重要性阈值待金融组确认；当前仅报告计算事实，不判定显著异常或优先级',
                profit_chain=chain, signals=signals, investigation_tasks=tasks,
                boundary='会计变化不是经营因果；现金流增长不自动证明盈利质量改善；不同利润层级不重复相加',
                agent_executed=False, llm_called=False)
