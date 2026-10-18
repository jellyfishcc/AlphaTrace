import type { CaseRecord } from './types'
import { coreMetrics, linkedEvidence } from './workflow'

export function FinancialHighlights({ record, onMetric, onEvidence }: { record: CaseRecord; onMetric: (id: string) => void; onEvidence: (id: string) => void }) {
  const metrics = coreMetrics(record)
  if (!metrics.length) return <div className="empty"><strong>未提供可展示的财务金额</strong><p>当前案例没有对应记录，不使用其他案例补充。</p></div>
  return <div className="financial-highlights">{metrics.map((m) => <section className="panel-card financial-highlight" key={m.id}>
    <button className="metric-title" onClick={() => onMetric(m.id)}>{m.name} <span>查看计算与来源 →</span></button>
    <dl><div><dt>{record.run.basePeriod}</dt><dd>{m.base}</dd></div><div><dt>{record.run.currentPeriod}</dt><dd>{m.current}</dd></div></dl>
    <p className="metric-change"><span>同比变化</span><strong>{m.delta}</strong></p><p className="metric-yoy">同比：{m.yoy}</p>
    <div className="link-chips">{linkedEvidence(record,m).map((e) => <button key={e.id} onClick={() => onEvidence(e.id)}>{e.id}</button>)}{!linkedEvidence(record,m).length && <span>未提供关联记录</span>}</div>
    <details className="audit-details"><summary>金额来源状态</summary><p>{m.status} · {m.source}</p></details>
  </section>)}</div>
}

export function ProfitContribution({ record, onEvidence }: { record: CaseRecord; onEvidence: (id: string) => void }) {
  const metric = record.metrics.find((m) => m.id === 'net_profit')
  const bridge = metric && record.modules?.sections.find((s) => s.kind === 'profit' && s.rows[0]?.cells[0] === `目标：${metric.name}`)
  if (!bridge) return <div className="panel-card"><h3>净利润会计贡献未提供</h3><p>当前案例缺少对应层级桥接，不能从当期金额推算贡献。</p></div>
  const index = (name: string) => bridge.columns.indexOf(name)
  const rows = bridge.rows.filter((r) => r.cells[index('状态')] === '组成项')
  const residual = bridge.rows.find((r) => r.cells[0] === '残差（披露目标 − 组成项）')
  return <section className="panel-card contribution-summary"><h2>净利润变化由哪些会计项目形成？</h2><p>目标变化：<strong>{metric.delta}</strong>。以下仅为净利润层级的会计关系，不代表经营原因已查明。</p>
    <div className="table-shell"><table><thead><tr><th>组成项</th><th>项目自身变化（元）</th><th>对净利润影响（元）</th><th>来源</th></tr></thead><tbody>{rows.map((r,i) => <tr key={i}><td>{r.cells[0]}</td><td>{r.cells[index('自身变化（元）')] ?? '未提供'}</td><td>{r.cells[index('对本目标影响（元）')] ?? '未提供'}</td><td>{r.evidenceIds.map((id) => <button className="data-link" key={id} onClick={() => onEvidence(id)}>{id}</button>)}</td></tr>)}</tbody></table></div>
    <p>变化残差（元）：{residual?.cells[index('自身变化（元）')] ?? '未提供'} · {bridge.rows[0]?.cells[index('状态')] === 'exact_zero_residual' ? '该层级已闭合' : '闭合状态需查看明细'}</p><p className="business-boundary">父层与子层不重复加总；其他层级的缺失及未闭合状态仍保留在计算详情。</p>
  </section>
}
