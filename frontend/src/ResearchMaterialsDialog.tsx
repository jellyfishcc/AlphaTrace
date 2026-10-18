import { useEffect, useRef, useState } from 'react'
import type { CaseRecord } from './types'
import { preparedSourceFiles } from './workflow'

export function ResearchMaterialsDialog({ record, loading, error, onClose, onLoad }: {
  record?: CaseRecord; loading: boolean; error: string; onClose: () => void; onLoad: (record: CaseRecord) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [selected, setSelected] = useState(false)
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => { element?.close() }
  }, [])
  const files = record ? preparedSourceFiles(record) : []
  return <dialog ref={dialog} className="materials-dialog" aria-labelledby="materials-title" aria-describedby="materials-description" onCancel={(event) => { event.preventDefault(); onClose() }}>
    <div className="materials-heading"><div><span className="eyebrow">TraceLab（盈迹） · 已准备的研究资料</span><h2 id="materials-title">选择研究资料</h2></div><button className="icon-button" aria-label="关闭资料选择" onClick={onClose}>×</button></div>
    <p id="materials-description">选择已有案例，载入已核验的财务分析结果。</p>
    {record ? <label className={`prepared-case ${selected ? 'selected' : ''}`}><div className="prepared-case-heading"><input type="radio" name="prepared-case" checked={selected} disabled={loading} onChange={() => setSelected(true)}/><div><strong>{record.run.company}</strong><span>{record.run.basePeriod}—{record.run.currentPeriod} · 真实资料离线案例</span></div><span className="badge badge-info">资料已准备</span></div>
      <ul className="prepared-files">{files.map((name) => <li key={name}><span className="prepared-file-icon">PDF</span><span>{name}<small>已关联的年报来源记录 · 原始文件不载入浏览器</small></span></li>)}
        <li><span className="prepared-file-icon">数据</span><span>已核验的结构化财务数据<small>已有两期金额、会计桥接与来源 · JSON 展示包</small></span></li></ul>
      {!files.some((name) => name.includes('2024')) && <p className="materials-note">2024 年报独立文件未在展示包中关联；两期财务金额以现有核验结果为准。</p>}
    </label> : <div className="empty"><strong>真实案例资料暂不可用</strong><p>展示包尚未加载或未通过校验。请关闭窗口，检查展示包后刷新页面。</p></div>}
    <p className="materials-boundary">本次仅载入既有结果，不上传 PDF、不重新计算，也不调用 Qwen。</p>
    {error && <p className="materials-error" role="alert">{error}</p>}
    <div className="materials-actions"><button className="btn secondary" onClick={onClose}>返回介绍页</button><button className="btn primary" disabled={!record || !selected || loading} onClick={() => { if(record && selected && !loading) onLoad(record) }}>{loading ? '正在读取展示包…' : '载入已核验案例'}</button></div>
  </dialog>
}
