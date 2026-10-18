import type { ActionStep, CaseRecord } from './types'
import { actionTitle, resolveLink } from './workflow'

function callObject(step: ActionStep): string {
  try {
    const params: unknown = JSON.parse(step.params)
    if (params && typeof params === 'object') {
      const value = (params as Record<string, unknown>)[step.action === 'search' ? 'query' : 'evidence_id']
      if (typeof value === 'string') return value
    }
  } catch { /* Preserve malformed or missing parameters in the audit, never infer them. */ }
  return '未提供'
}

export function AgentInvestigation({ record, onLink, onReport }: { record: CaseRecord; onLink: (id: string) => void; onReport: () => void }) {
  const tools = record.steps.filter((step) => !step.error && ['search', 'get'].includes(step.action))
  const sources = (step: ActionStep) => step.links.map((id) => {
    const evidence = record.evidence.find((e) => e.id === id)
    const type = resolveLink(record,id)
    return <div className="agent-source" key={id}>{type === 'missing' ? <span>{id} · 未提供关联记录</span> : <button className="data-link" onClick={() => onLink(id)}>{id} · {evidence ? '查看年报原文' : type === 'metric' ? '查看财务详情' : '查看候选内容'}</button>}{evidence && <p>{evidence.fileName} · 印刷 {evidence.printPage} / PDF {evidence.pdfPage}<br/>相关项目：{evidence.metrics.map((metricId) => record.metrics.concat(record.cashMetrics).find((m) => m.id === metricId)?.name ?? metricId).join('、') || '未提供'}</p>}</div>
  })
  return <div className="page agent-business-page"><div className="page-head"><div><span className="eyebrow">受控调查 · 工具与证据可追溯</span><h1>Agent 调查工作台</h1><p>{record.run.isExample ? '概念演示 / 模拟运行，非真实模型调查结果' : '真实历史执行记录 · 离线回放；浏览过程不会再次调用模型。'}</p></div><button className="btn secondary" onClick={onReport}>查看业绩分析与证据报告 →</button></div>
    <section className="analysis-theme"><span className="eyebrow">当前调查目标</span><h2>{record.question}</h2><p>调查问题本身不是经营原因结论。</p></section>
    <div className="section-head"><h2>{record.run.isExample ? '模拟工具调用展示' : '已发生的真实工具调用'}</h2><span className="badge badge-info">{record.run.isExample ? '交互示例' : '历史记录'}</span></div>
    <div className="agent-tool-grid">{tools.map((step,i) => <article className="step-card actual-tool" key={`${step.round}-${step.action}-${i}`}>
      <span className="eyebrow">第 {step.round} 轮 · 实际工具：{step.action}</span><h2>{actionTitle(step)}</h2>
      <p>{step.action === 'search' ? '实际检索内容' : '实际读取对象'}：<strong>{callObject(step)}</strong></p><p>{step.summary}</p>
      {sources(step)}{!step.links.length && <p>未提供关联记录。</p>}
      <p className="business-boundary">{step.action === 'search' ? '检索返回可定位资料；是否支持解释仍需阅读核验。' : '读取有明确出处的原文；不代表已完成经营因果判断。'}</p>
    </article>)}</div>
    {!record.steps.length && <div className="empty"><strong>未提供调查轨迹</strong><p>没有对应记录，不用模拟步骤补充。</p></div>}
    {!!record.steps.length && !tools.length && <p>未提供可展示的 search / get 记录；其他原始动作见执行详情。</p>}
    <section className="planned-capability"><span className="badge badge-neutral">规划能力 / 尚未完成</span><h2>经营解释生成与证据校验</h2><p>继续完善经营解释生成、证据交叉核验和自主调查闭环，形成有明确支持范围的业绩归因结论。</p><small>产品目标，不是本次执行的第三步或已完成结果。</small></section>
    <p className="business-boundary">{record.run.isExample ? '模拟内容仅用于交互演示。' : record.explanations.length ? '候选内容与支持范围以原始记录为准。' : '完整经营解释尚未通过校验。'} 在线发起新调查尚未接入。</p>
    <details className="audit-details panel-card execution-audit"><summary>{record.run.isExample ? '模拟执行详情' : '真实执行详情'} · 完整历史与技术审计</summary>
      <div className="execution-counts"><span>执行轮数 <strong>{record.agentSummary?.rounds ?? '未提供'}</strong></span><span>工具调用 <strong>{record.agentSummary?.tool_calls ?? '未提供'}</strong></span><span>真实模型请求 <strong>{record.agentSummary?.real_request_attempts ?? '未提供'}</strong></span></div>
      <p>运行：{record.run.id}</p><p>状态：{record.run.status} · {record.run.statusLabel}</p><p>失败原因：{record.agentSummary?.errors.join('、') ?? '未提供'}</p><p>停止原因：{record.agentSummary?.stop_reason ?? '未提供'}</p><p>simulation: {String(record.agentSummary?.simulation ?? record.run.isExample)} · llm_called: {record.agentSummary ? String(record.agentSummary.llm_called) : '未提供'}</p>
      {record.steps.map((step,i) => <article className="audit-step" key={`${step.round}-${i}`}><h3>第 {step.round} 轮 · {actionTitle(step)}</h3><p>原始动作：{step.action} · {step.label}</p><p>参数：<code>{step.params}</code></p><p>返回记录：{step.result}</p><p>原始摘要：{step.summary}</p><p>错误：{step.error ?? '未记录错误'}</p>{sources(step)}</article>)}
      <p>保留全部实际动作与失败记录。失败不等于合理停止，不补写解释或后续工具调用。</p>
    </details>
  </div>
}
