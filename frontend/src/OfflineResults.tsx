import type { CaseRecord, OfflineSection } from './types'

export function OfflineResults({ record, kind, onEvidence }: {
  record: CaseRecord; kind: OfflineSection['kind']; onEvidence?: (id: string) => void
}) {
  const sections = record.modules?.sections.filter((s) => s.kind === kind) ?? []
  if (!sections.length) return <section className="panel-card"><h2>未提供离线结果</h2><p>当前案例没有导入此项结果；不会用其他案例或模拟数据补充。</p></section>
  return <div className="offline-results">{sections.map((section, index) => <section className="panel-card" key={section.kind + index}>
    <h2>{section.title}</h2>
    {section.notices.map((notice) => <p className="technical-hint" key={notice}>{notice}</p>)}
    <p className="technical-hint">离线运行：{section.runId} · 快照：{record.modules?.snapshotId}</p>
    <div className="table-shell"><table><thead><tr>{section.columns.map((name) => <th key={name}>{name}</th>)}<th>年报证据</th></tr></thead>
      <tbody>{section.rows.map((row, i) => <tr key={i}>{row.cells.map((cell,j) => <td key={j}>{cell}</td>)}<td>{row.evidenceIds.length ? row.evidenceIds.map((id) => onEvidence ? <button key={id} className="text-button" onClick={() => onEvidence(id)}>{id}</button> : <span key={id}>{id} </span>) : '未提供'}</td></tr>)}</tbody>
    </table></div>
    <details><summary>输出文件校验摘要</summary>{Object.entries(section.hashes).map(([name,hash]) => <p key={name}>{name}：{hash}</p>)}</details>
  </section>)}</div>
}
