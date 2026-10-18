import type { CaseRecord } from './types'
import { actionTitle, agentOutcome, resolveLink } from './workflow'

export function AgentInvestigation({ record, onLink, onReport }: { record: CaseRecord; onLink: (id: string) => void; onReport: () => void }) {
  return <div className="page agent-business-page"><div className="page-head"><div><span className="eyebrow">受控调查 · 工具与证据可追溯</span><h1>Agent 调查工作台</h1><p>{record.run.isExample ? '概念演示 / 模拟运行，非真实模型调查结果' : '真实历史执行记录；浏览过程不会再次调用模型。'}</p></div></div>
    <section className="analysis-theme"><span className="eyebrow">当前调查目标</span><h2>{record.question}</h2><p>目标是提出并核验解释；调查问题本身不是经营原因结论。</p></section>
    <div className="agent-status panel-card"><div><h2>{agentOutcome(record)}</h2><p>{record.explanations.length ? '当前案例已有候选内容，支持范围以各条原始记录为准。' : '尚未形成经核验的最终经营解释。财务事实和年报原文仍可独立查看。'}</p></div><button className="btn secondary" onClick={onReport}>查看阶段性分析与证据 →</button></div>
    <div className="execution-counts"><span>执行轮数 <strong>{record.agentSummary?.rounds ?? '未提供'}</strong></span><span>工具调用 <strong>{record.agentSummary?.tool_calls ?? '未提供'}</strong></span><span>真实模型请求 <strong>{record.agentSummary?.real_request_attempts ?? '未提供'}</strong></span></div>
    <div className="timeline business-timeline">{record.steps.map((step,i) => <article className="timeline-item" key={`${step.round}-${step.action}-${i}`}><div className="timeline-marker"><span>{step.round}</span></div><div className="step-card">
      <span className="eyebrow">第 {step.round} 轮 · {step.action === 'error' ? '未形成有效工具动作' : `实际工具：${step.action}`}</span><h2>{actionTitle(step)}</h2>
      <p>{step.action === 'error' ? step.result : step.summary}</p>
      {step.links.map((id) => {
        const evidence = record.evidence.find((e) => e.id === id)
        const type = resolveLink(record,id)
        return <div className="agent-source" key={id}>{type === 'missing' ? <span>{id} · 未提供关联记录</span> : <button className="data-link" onClick={() => onLink(id)}>{id} · {evidence ? '查看年报原文' : type === 'metric' ? '查看财务详情' : '查看候选内容'}</button>}{evidence && <p>{evidence.fileName} · 印刷 {evidence.printPage} / PDF {evidence.pdfPage}<br/>{step.action === 'search' ? '检索返回的来源，不代表已读取并支持经营解释。' : '记录中的原文读取结果，不代表已形成因果结论。'}</p>}</div>
      })}
      {!step.links.length && step.action !== 'error' && <p>未提供关联记录。</p>}
      <p className="actual-next">{record.steps[i+1] ? `下一条实际记录：第 ${record.steps[i+1].round} 轮 · ${actionTitle(record.steps[i+1])}` : '历史记录到此结束；不补写后续动作。'}</p>
      <details className="audit-details"><summary>查看该步技术执行详情</summary><p>原始动作：{step.action} · {step.label}</p><p>参数：<code>{step.params}</code></p><p>返回记录：{step.result}</p><p>原始摘要：{step.summary}</p><p>错误：{step.error ?? '未记录错误'}</p></details>
    </div></article>)}</div>
    {!record.steps.length && <div className="empty"><strong>未提供调查轨迹</strong><p>没有对应记录，不用模拟步骤补充。</p></div>}
    <details className="audit-details panel-card"><summary>查看原始审计信息（允许公开的字段）</summary><p>运行：{record.run.id}</p><p>状态：{record.run.status} · {record.run.statusLabel}</p><p>失败原因：{record.agentSummary?.errors.join('、') ?? '未提供'}</p><p>停止原因：{record.agentSummary?.stop_reason ?? '未提供'}</p><p>simulation: {String(record.agentSummary?.simulation ?? record.run.isExample)} · llm_called: {record.agentSummary ? String(record.agentSummary.llm_called) : '未提供'}</p></details>
    <p className="business-boundary">在线发起新调查尚未接入。本页不展示未记录的决策理由，也不把失败包装成合理完成。</p>
  </div>
}
