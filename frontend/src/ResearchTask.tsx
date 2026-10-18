import type { CaseRecord, ViewId } from './types'
import { coreMetrics } from './workflow'
import { FinancialHighlights, ProfitContribution } from './FinancialHighlights'
import { OfflineResults } from './OfflineResults'

export function ResearchTask({ record, onInvestigate, onMetric, onEvidence, onView }: {
  record: CaseRecord; onInvestigate: () => void; onMetric: (id: string) => void; onEvidence: (id: string) => void; onView: (view: ViewId) => void
}) {
  const metrics = coreMetrics(record)
  const profit = metrics.find((m) => m.id === 'net_profit')
  const cash = metrics.find((m) => ['operating_cashflow','operating_cash'].includes(m.id))
  return <div className="page performance-page">
    <div className="page-head"><div><span className="eyebrow">财务变化驱动的业绩归因与证据验证</span><h1>业绩分析工作台</h1><p>{record.run.company} · {record.run.basePeriod} → {record.run.currentPeriod}</p></div></div>
    <section className="analysis-theme"><span className="badge badge-info">{record.run.isExample ? '概念演示 / 模拟运行，非真实模型调查结果' : '真实财务结果 · 既有历史分析'}</span><h2>{record.question}</h2><p>报表口径：{record.run.scope}</p></section>
    <div className="section-head"><div><span>财务变化事实</span><h2>公司业绩发生了什么变化？</h2></div><small>金额沿用后端原始字符串</small></div>
    <FinancialHighlights record={record} onMetric={onMetric} onEvidence={onEvidence}/>
    <ProfitContribution record={record} onEvidence={onEvidence}/>
    <section className="investigation-signal panel-card"><span className="eyebrow">值得调查的财务信号 · 不是已证实经营原因</span><h2>利润变化与经营现金流变化应如何解释？</h2>
      <div className="signal-amounts"><p>净利润变化：<strong>{profit?.delta ?? '未提供'}</strong></p><p>经营现金流变化：<strong>{cash?.delta ?? '未提供'}</strong></p></div>
      <p>这是当前案例的调查主题；方向差异本身不构成财务错误、风险或盈利质量结论。</p>
      {record.steps.length ? <button className="btn primary" onClick={onInvestigate}>{record.run.isExample ? '查看模拟调查过程' : '查看 Agent 调查过程'} →</button> : <p>未提供关联调查记录。</p>}
      <p className="business-boundary">打开已有记录，不启动新的模型请求。完整自主归因仍是产品目标。</p>
    </section>
    <details className="audit-details panel-card"><summary>展开利润层级桥接与现金流勾稽</summary><OfflineResults record={record} kind="profit" onEvidence={onEvidence}/><OfflineResults record={record} kind="cash" onEvidence={onEvidence}/></details>
    <details className="audit-details panel-card"><summary>资料与辅助核查工具</summary><p>以下为支撑分析的已有离线能力；不支持网页在线上传或调用模型。</p><div className="support-links"><button className="btn secondary" onClick={() => onView('pdf')}>查看指定 PDF 表格提取</button><button className="btn secondary" onClick={() => onView('report')}>查看结构化研报纠错示例</button><button className="btn secondary" onClick={() => onView('financials')}>查看全部财务计算</button></div><p>纠错示例使用人为构造陈述，并非已发表研报。</p></details>
  </div>
}
