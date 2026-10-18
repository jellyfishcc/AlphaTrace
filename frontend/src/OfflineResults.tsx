import type { CaseRecord, OfflineSection } from './types'
import { claimSummary } from './workflow'

export function OfflineResults({ record, kind, onEvidence }: {
  record: CaseRecord; kind: OfflineSection['kind']; onEvidence?: (id: string) => void
}) {
  const sections = record.modules?.sections.filter((s) => s.kind === kind) ?? []
  if (!sections.length) return <section className="panel-card"><h2>未提供离线结果</h2><p>当前案例没有导入此项结果；不会用其他案例或模拟数据补充。</p></section>
  const claim = claimSummary(record)
  const table = (section: OfflineSection, compact = false) => {
    const columns = section.columns.map((name, index) => ({ name, index })).filter(({ name }) => !compact || !['原始行','来源 SHA256','提取状态'].includes(name))
    return <div className="table-shell"><table><thead><tr>{columns.map(({ name }) => <th key={name}>{name}</th>)}<th>年报证据</th></tr></thead>
      <tbody>{section.rows.map((row, i) => <tr key={i}>{columns.map(({ index }) => <td key={index}>{row.cells[index]}</td>)}<td>{row.evidenceIds.length ? row.evidenceIds.map((id) => onEvidence ? <button key={id} className="data-link" onClick={() => onEvidence(id)}>{id}</button> : <span key={id}>{id} </span>) : '未提供'}</td></tr>)}</tbody>
    </table></div>
  }
  const content = (section: OfflineSection) => <>
    {section.notices.map((notice) => <p className="technical-hint" key={notice}>{notice}</p>)}
    {kind === 'report' ? <>
      <div className="task-grid"><div className="task-statement"><span className="eyebrow">构造的待核查陈述</span><h3>{claim.statement}</h3></div><div className="result-card"><span className="eyebrow">后端确定性核查结果</span><h2>{claim.status === '一致' ? '未发现可确定错误' : claim.status} · {claim.error}</h2><p className="correction-copy">{claim.correction}</p>{claim.evidenceIds.map((id) => <button key={id} className="data-link" onClick={() => onEvidence?.(id)}>{id} · 查看证据原文</button>)}</div></div>
      <details className="audit-details"><summary>结构化核查对象、正确财务事实与完整核验过程</summary>{table(section)}</details>
    </> : table(section, kind === 'pdf')}
    <details className="audit-details"><summary>技术溯源：运行编号、原始字段与校验摘要</summary><p>离线运行：{section.runId} · 快照：{record.modules?.snapshotId}</p>{kind === 'pdf' && table(section)}{Object.entries(section.hashes).map(([name,hash]) => <p key={name}>{name}：{hash}</p>)}</details>
  </>
  return <div className="offline-results">{sections.map((section, index) => kind === 'profit' || kind === 'cash'
    ? <details className="panel-card bridge-detail" key={section.kind + index}><summary>{section.title.replace('exact_zero_residual', '已闭合 · 残差为零').replace('incomplete', '数据不完整 · 未确认闭合')}</summary>{content(section)}</details>
    : <section className="panel-card" key={section.kind + index}><h2>{section.title}</h2>{content(section)}</section>)}</div>
}
