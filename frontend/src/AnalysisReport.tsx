import type { CaseRecord } from './types'
import { FinancialHighlights, ProfitContribution } from './FinancialHighlights'
import { OfflineResults } from './OfflineResults'

export function AnalysisReport({ record, onMetric, onEvidence, onExplanation, onInvestigation }: {
  record: CaseRecord; onMetric: (id: string) => void; onEvidence: (id: string) => void; onExplanation: (id: string) => void; onInvestigation: () => void
}) {
  return <div className="page analysis-report"><div className="page-head"><div><span className="eyebrow">核验报告与证据链 · 阶段性分析结果</span><h1>业绩分析与证据报告</h1><p>{record.run.company} · {record.run.basePeriod} → {record.run.currentPeriod}</p></div></div>
    <div className="import-note">{record.run.isExample ? '概念演示 / 模拟运行，非真实模型调查结果' : '以下财务事实、会计贡献与公开年报来源来自已有核验结果；经营归因未完成。'}</div>
    <h2 className="business-section-title">财务变化摘要</h2><FinancialHighlights record={record} onMetric={onMetric} onEvidence={onEvidence}/>
    <ProfitContribution record={record} onEvidence={onEvidence}/>
    <section className="panel-card explanation-results"><h2>经营解释及证据支持情况</h2>
      {!record.explanations.length ? <><h3>尚未形成经核验的最终经营解释</h3><p>当前报告可追溯财务变化与披露原文，但无法据此确定净利润和经营现金流变化的经营原因。</p><p>没有待确认的 AI 最终解释报告；不能将独立来源证据自动拼接为因果证据链。</p></> : record.explanations.map((e) => <article className="reported-explanation" key={e.id}><span className="badge badge-neutral">{e.kind === 'accounting_fact' ? '会计关系' : e.kind === 'hypothesis' ? '待验证假设' : '披露解释（原记录分类）'}</span><h3>{e.statement}</h3><p>证据限制：{e.supportLimit}</p><p>关联财务问题：{e.metrics.map((id) => record.metrics.concat(record.cashMetrics).find((m) => m.id === id)?.name ?? id).join('、')}</p><div className="link-chips">{e.citations.map((id) => { const source=record.evidence.find((item) => item.id===id); return source ? <button key={id} onClick={() => onEvidence(id)}>{id} · {source.fileName} · 印刷 {source.printPage} / PDF {source.pdfPage}</button> : <span key={id}>{id} · 未提供关联记录</span> })}{!e.citations.length && <span>未提供可定位引文，不认定为经营结论。</span>}</div><button className="text-link" onClick={() => onExplanation(e.id)}>查看完整候选内容与原始状态</button></article>)}
      <button className="btn secondary" onClick={onInvestigation}>返回调查过程</button>
    </section>
    <section className="panel-card evidence-catalog"><h2>可追溯的年报证据</h2><p>{record.evidence.length} 条来源记录，不等于 {record.evidence.length} 条经营解释证据链，也不代表 Agent 已逐条读取。</p>
      <details><summary>展开来源目录，选择原文</summary>{record.evidence.map((e) => <button className="catalog-source" key={e.id} onClick={() => onEvidence(e.id)}><strong>{e.id}</strong><span>{e.fileName} · 印刷 {e.printPage} / PDF {e.pdfPage}</span></button>)}{!record.evidence.length && <p>未提供来源记录。</p>}</details>
    </section>
    <section className="panel-card research-boundaries"><h2>目前无法确定的事项</h2><p>{record.explanations.length ? '候选内容的证据限制按原记录保留，不提升为已确认结论。' : '尚不能给出经核验的经营原因归因；财务变化方向本身不证明盈利质量或风险。'}</p><p>合并口径及两期比较范围以资料披露为准；特定表格的一致性核对不是独立第三方审计。</p></section>
    <details className="audit-details panel-card"><summary>资料版本、历史差异及技术执行状态</summary><OfflineResults record={record} kind="verification"/><p>运行：{record.run.id} · 资料版本：{record.run.materialVersion}</p><p>Agent 原始状态：{record.run.status} · {record.agentSummary?.errors.join('、') ?? '未提供失败原因'}</p><p>来源核验与经营解释核验分别记录，未产生合规解释时不存在等待签核的最终解释。</p></details>
  </div>
}
