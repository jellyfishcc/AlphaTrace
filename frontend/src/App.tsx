import { workflow, adjacent, primaryView, viewLabels, resolveLink, agentOutcome, linkedEvidence, openingCase, verifyPreparedCase } from './workflow'
import { ResearchTask } from './ResearchTask'
import { IntroPage } from './IntroPage'
import { ResearchMaterialsDialog } from './ResearchMaterialsDialog'
import { AgentInvestigation } from './AgentInvestigation'
import { AnalysisReport } from './AnalysisReport'
import { OfflineResults } from './OfflineResults'
import { useEffect, useRef, useState } from 'react'
import { adaptLocalFiles, loadDisplayBundle } from '@/data/adapter'
import { exampleCases } from '@/data/example'
import type { CaseRecord, Evidence, Explanation, StatusTone, ViewId } from '@/types'

type IconName = 'cases' | 'overview' | 'chart' | 'route' | 'evidence' | 'review' | 'chevron' | 'panel' | 'search' | 'upload' | 'lock' | 'arrow' | 'file' | 'check' | 'alert' | 'play' | 'close' | 'download'

const icons: Record<IconName, React.ReactNode> = {
  cases: <><path d="M4 7.5h16v11H4z"/><path d="M8 7.5V5h8v2.5M4 12h16"/></>,
  overview: <><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></>,
  chart: <><path d="M5 20V10m7 10V4m7 16v-7"/><path d="M3 20h18"/></>,
  route: <><circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h4a3 3 0 0 1 3 3v6a3 3 0 0 0 3 3"/></>,
  evidence: <><path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h7M9 16h5"/></>,
  review: <><path d="M9 4h6l1 2h3v15H5V6h3z"/><path d="m9 14 2 2 4-5"/></>,
  chevron: <path d="m9 7 5 5-5 5"/>,
  panel: <><path d="M4 5h16v14H4z"/><path d="M15 5v14"/></>,
  search: <><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></>,
  upload: <><path d="M12 16V4m-4 4 4-4 4 4"/><path d="M5 14v6h14v-6"/></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>,
  arrow: <><path d="M5 12h14m-5-5 5 5-5 5"/></>,
  file: <><path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  alert: <><path d="M12 4 3 20h18z"/><path d="M12 9v5m0 3v.01"/></>,
  play: <path d="m9 6 9 6-9 6z"/>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
  download: <><path d="M12 4v12m-4-4 4 4 4-4"/><path d="M5 19h14"/></>,
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[name]}</svg>
}

const modeLabel = { preset_mock: '预设模拟', qwen_replay: '模拟响应回放', qwen_real: '真实模型历史记录' }
const kindLabel = { accounting_fact: '财务 / 会计事实', disclosure_explanation: '披露解释', hypothesis: '待验证假设' }

function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: StatusTone }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty"><div className="empty-icon"><Icon name="file" size={22}/></div><strong>{title}</strong><p>{detail}</p></div>
}

function App() {
  const [records, setRecords] = useState<CaseRecord[]>(exampleCases)
  const [selectedId, setSelectedId] = useState(exampleCases[0].id)
  const [view, setView] = useState<ViewId>('intro')
  const [materialsOpen, setMaterialsOpen] = useState(false)
  const [materialsLoading, setMaterialsLoading] = useState(false)
  const [materialsError, setMaterialsError] = useState('')
  const materialsRequest = useRef(0)
  const [panelOpen, setPanelOpen] = useState(false)
  const [selectedMetricId, setSelectedMetricId] = useState('operating_profit')
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('E12_A')
  const [selectedExplanationId, setSelectedExplanationId] = useState('EXP-02')
  const [evidenceOrigin, setEvidenceOrigin] = useState<ViewId>('overview')
  const [dataReady, setDataReady] = useState(false)
  const [detailOrigin, setDetailOrigin] = useState<ViewId>('overview')
  const [loadNotice, setLoadNotice] = useState('正在加载真实案例展示包…')
  const fileRef = useRef<HTMLInputElement>(null)
  const record = records.find((item) => item.id === selectedId) ?? records[0]

  useEffect(() => {
    let active = true
    loadDisplayBundle().then((real) => {
      if (!active) return
      setRecords([real, ...exampleCases]); setSelectedId(real.id); setLoadNotice(''); setDataReady(true)
    }).catch(() => { if (active) setLoadNotice('真实展示包缺失或校验失败；当前仅有明确标注的交互示例。请先运行 Python display_export。') })
    return () => { active = false }
  }, [])
  useEffect(() => {
    setSelectedMetricId(record.metrics[0]?.id ?? '')
    setSelectedEvidenceId(record.evidence[0]?.id ?? '')
    setSelectedExplanationId(record.explanations[0]?.id ?? '')
    setView((current) => current === 'intro' ? 'intro' : 'overview'); setEvidenceOrigin('overview'); setDetailOrigin('overview'); setPanelOpen(false)
  }, [selectedId])

  const goMetric = (id: string) => { setDetailOrigin(primaryView(view === 'evidence' ? evidenceOrigin : view)); setSelectedMetricId(id); setView('financials'); setPanelOpen(false); window.scrollTo({top:0}) }
  const goEvidence = (id: string) => { if (view !== 'evidence') setEvidenceOrigin(view); setSelectedEvidenceId(id); setView('evidence'); setPanelOpen(false); window.scrollTo({top:0}) }

  const goExplanation = (id: string) => { setSelectedExplanationId(id); if (view !== 'evidence') setEvidenceOrigin(view); setView('evidence'); setPanelOpen(false) }
  const openLink = (id: string) => { const type=resolveLink(record,id); if(type==='evidence') goEvidence(id); else if(type==='metric') goMetric(id); else if(type==='explanation') goExplanation(id) }

  const handleImport = async (files: FileList | null) => {
    if (!files?.length) return
    try {
      const bundle = await adaptLocalFiles(Array.from(files))
      setRecords((current) => [bundle.record, ...current.filter((r) => r.id !== bundle.record.id)])
      setSelectedId(bundle.record.id); setView('overview'); setLoadNotice(''); setDataReady(true)
    } catch (error) {
      setLoadNotice(error instanceof Error ? error.message : '展示包导入失败')
    }
    if (fileRef.current) fileRef.current.value = ''
  }

  const navigate = (next: ViewId) => { setView(next); setPanelOpen(false); window.scrollTo({ top: 0 }) }
  const closeMaterials = () => { materialsRequest.current++; setMaterialsOpen(false); setMaterialsLoading(false); setMaterialsError('') }
  const loadPrepared = async (selected: CaseRecord) => {
    if (materialsLoading) return
    const request = ++materialsRequest.current
    setMaterialsLoading(true); setMaterialsError('')
    try {
      const real = verifyPreparedCase(selected, await loadDisplayBundle())
      if (request !== materialsRequest.current) return
      setRecords((current) => [real, ...current.filter((item) => item.id !== real.id)])
      setSelectedId(real.id); setDataReady(true); setLoadNotice('')
      setSelectedMetricId(real.metrics[0]?.id ?? ''); setSelectedEvidenceId(real.evidence[0]?.id ?? ''); setSelectedExplanationId('')
      closeMaterials(); navigate('overview')
    } catch {
      if (request === materialsRequest.current) setMaterialsError('展示包读取或校验失败，未进入分析。请检查 gree-display.json；若资料版本发生变化，请关闭窗口并刷新后重新选择。')
    } finally {
      if (request === materialsRequest.current) setMaterialsLoading(false)
    }
  }
  const originView = view === 'evidence' ? evidenceOrigin : view
  const activeView = primaryView(originView === 'financials' ? detailOrigin : originView)
  const stepIndex = workflow.findIndex((step) => step.id === activeView)
  const renderView = () => {
    if (view === 'cases') return <CasesPage records={records} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setDataReady(true); navigate('overview') }} onImport={() => fileRef.current?.click()}/>
    if (view === 'review') return <AnalysisReport record={record} onMetric={goMetric} onEvidence={goEvidence} onExplanation={goExplanation} onInvestigation={() => navigate('investigation')}/>
    if (view === 'investigation') return <AgentInvestigation key={record.id} record={record} onLink={openLink} onReport={() => navigate('review')}/>
    if (view === 'report' || view === 'pdf') return <div className="page"><PageHead eyebrow={view === 'report' ? '研究陈述核查' : '数据来源'} title={view === 'report' ? '陈述与可信事实逐项对照' : '从年报表格读取两期金额'} description={view === 'report' ? '人为构造陈述的确定性核查结果；不是已发表研报，也不是网页实时分析。' : '指定合并利润表的受限提取；金额来自原始 PDF，同源一致性核对不是独立审计。'}/><OfflineResults record={record} kind={view} onEvidence={goEvidence}/></div>
    if (view === 'financials') return <FinancialsPage onEvidence={goEvidence} key={record.id + selectedMetricId} record={record} selectedId={selectedMetricId} onSelect={(id) => { setSelectedMetricId(id); setPanelOpen(true) }}/>
    if (view === 'evidence') return <EvidencePage key={record.id} record={record} selectedEvidenceId={selectedEvidenceId} selectedExplanationId={selectedExplanationId} onEvidence={setSelectedEvidenceId} onExplanation={setSelectedExplanationId} onMetric={goMetric}/>
    return <ResearchTask record={record} onInvestigate={() => navigate('investigation')} onMetric={goMetric} onEvidence={goEvidence} onView={navigate}/>
  }

  if (view === 'intro') return <><IntroPage records={records} notice={loadNotice} onChoose={() => { setMaterialsError(''); setMaterialsOpen(true) }} onArchive={() => navigate('cases')}/>{materialsOpen && <ResearchMaterialsDialog record={openingCase(records)} loading={materialsLoading} error={materialsError} onClose={closeMaterials} onLoad={loadPrepared}/>}</>

  return (
    <div className="app-shell">
      <input ref={fileRef} className="sr-only" type="file" accept=".json" onChange={(event) => handleImport(event.target.files)}/>
      <aside className="sidebar">
        <button className="brand brand-home" onClick={() => navigate('intro')} aria-label="TraceLab（盈迹）返回产品介绍"><div className="brand-mark"><span/><span/><span/></div><div><strong>TraceLab <span>盈迹</span></strong><small>业绩归因与证据验证</small></div></button>
        <div className="case-mini"><span>当前案例</span><strong>{record.run.company}</strong><small>{record.run.currentPeriod} vs {record.run.basePeriod}</small></div>
        <nav aria-label="核心业务导航">
          <p className="nav-title">研究工作空间</p>
          {workflow.map((step, index) => <button key={step.id} aria-current={activeView === step.id ? 'page' : undefined} className={activeView === step.id ? 'nav-item active' : 'nav-item'} onClick={() => navigate(step.id)}><span className="nav-index">{String(index + 1).padStart(2,'0')}</span><span>{step.label}</span></button>)}
        </nav>
        <button className="nav-item archive-nav" onClick={() => navigate('cases')}><Icon name="cases"/>研究档案与导入</button>
        <div className="sidebar-foot"><div className="principle-line"/><p>“发现变化，<br/>以证据追溯原因。”</p><span>TraceLab research protocol</span></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="top-case">
            <span className="eyebrow">当前研究任务</span>
            <div className="top-case-title"><strong>{record.run.company}</strong><span>{record.run.ticker}</span><Badge tone={record.run.isExample ? 'neutral' : 'info'}>{record.run.isExample ? '概念演示 / 模拟运行' : '真实财务 · 历史结果'}</Badge></div>
          </div>
          <div className="top-fields">
            <div><span>比较期间</span><strong>{record.run.basePeriod} → {record.run.currentPeriod}</strong></div>
            <div><span>报表口径</span><strong>{record.run.scope}</strong></div>

          </div>
          <div className="run-control">
            <span>选择案例</span>
            <select aria-label="选择案例" value={dataReady ? selectedId : ''} onChange={(event) => { setSelectedId(event.target.value); setDataReady(true) }}>{!dataReady && <option value="" disabled>请选择已有案例</option>}{records.map((item) => <option key={item.id} value={item.id}>{item.run.company} · {item.run.isExample ? '交互模拟' : '真实资料离线案例'} · {item.run.basePeriod}—{item.run.currentPeriod}{item.run.isExample ? ` · ${item.run.label}` : ''}</option>)}</select>

          </div>
          <button className={`icon-button ${panelOpen ? 'active' : ''}`} aria-label="技术详情" title="技术详情（运行编号、状态与审计上下文）" onClick={() => setPanelOpen((value) => !value)}><Icon name="panel"/></button>
        </header>

        <main className={panelOpen ? 'main-grid panel-visible' : 'main-grid'}>
          <div className="content-area">
            {loadNotice && <div className="import-note" role="status">{loadNotice}</div>}
            {dataReady || view === 'cases' ? <>
              {view !== 'cases' && <div className="flow-position"><strong>{viewLabels[view]}</strong><span>{['overview','investigation','review'].includes(view) ? workflow[stepIndex]?.hint : '辅助资料 · 保持当前案例上下文'}</span>{!['overview','investigation','review'].includes(view) && <button className="btn secondary" onClick={() => navigate(view === 'evidence' ? evidenceOrigin : view === 'financials' ? detailOrigin : 'overview')}>返回{viewLabels[view === 'evidence' ? evidenceOrigin : view === 'financials' ? detailOrigin : 'overview']}</button>}</div>}
              {renderView()}
              {workflow.some((step) => step.id === view) && <div className="flow-footer"><button className="btn secondary" disabled={!adjacent(view,-1)} onClick={() => {const next=adjacent(view,-1); if(next) navigate(next)}}>返回上一页</button><span>发现财务变化 → 调查变化原因 → 核对证据与结果</span>{adjacent(view,1) && <button className="btn primary" onClick={() => {const next=adjacent(view,1); if(next) navigate(next)}}>查看{viewLabels[adjacent(view,1)!]} →</button>}</div>}
            </> : <div className="page"><Empty title="真实分析数据尚不可用" detail="正在加载或展示包校验失败。不会使用模拟金额代替真实结果；可在顶部明确选择概念案例，或导入可信展示包。"/><button className="btn secondary" onClick={() => fileRef.current?.click()}>导入白名单展示包</button></div>}
          </div>
          {panelOpen && <ContextPanel record={record} view={view} metricId={selectedMetricId} evidenceId={selectedEvidenceId} explanationId={selectedExplanationId} onClose={() => setPanelOpen(false)}/>}
        </main>
      </section>
    </div>
  )
}

function PageHead({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) {
  return <div className="page-head"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</div>
}

function CasesPage({ records, selectedId, onSelect, onImport }: { records: CaseRecord[]; selectedId: string; onSelect: (id: string) => void; onImport: () => void }) {
  return <div className="page">
    <PageHead eyebrow="案例资料库" title="研究案例" description="浏览明确加载的示例或本地导入记录。这里没有连接远程项目数据库。" actions={<><button className="btn secondary" disabled title="后端尚未提供浏览器可调用的业务 API"><Icon name="lock"/> 新建在线调查 · 待接入</button><button className="btn primary" onClick={onImport}><Icon name="upload"/> 导入运行结果</button></>}/>
    <div className="import-note"><Icon name="alert"/><p><strong>本地导入说明</strong> 仅导入 Python 导出的 *-display.json 展示包，不上传服务器。不要选择原始附件、input.json 或完整日志。浏览器不重新认证来源。</p></div>
    <div className="case-list-head"><span>{records.length} 个运行记录</span><span>选择已有案例或导入白名单展示包</span></div>
    <div className="case-cards">{records.map((item) => <button key={item.id} className={`case-card ${item.id === selectedId ? 'selected' : ''}`} onClick={() => onSelect(item.id)}>
      <div className="case-card-top"><div><span className="case-ticker">{item.run.ticker}</span><h2>{item.run.company}</h2></div><Badge tone={item.run.status === 'validation_failed' ? 'danger' : 'warning'}>{agentOutcome(item)}</Badge></div>
      <p className="case-question">{item.question}</p>
      <div className="case-meta"><div><span>比较期间</span><strong>{item.run.basePeriod} → {item.run.currentPeriod}</strong></div><div><span>资料版本</span><strong>{item.run.materialVersion}</strong></div><div><span>导入时间</span><strong>{item.run.importedAt}</strong></div><div><span>后端运行时间</span><strong>{item.run.backendRunAt}</strong></div></div>
      <div className="case-card-foot"><Badge tone={item.run.isExample ? 'neutral' : 'info'}>{item.run.isExample ? '交互示例，非真实运行' : '浏览器本地记录'}</Badge><span>查看该案例 <Icon name="arrow" size={15}/></span></div>
    </button>)}</div>
  </div>
}

function FinancialsPage({ record, selectedId, onSelect, onEvidence }: { record: CaseRecord; selectedId: string; onSelect: (id: string) => void; onEvidence: (id: string) => void }) {
  const [tab, setTab] = useState<'profit' | 'cash'>(record.cashMetrics.some((m) => m.id === selectedId) ? 'cash' : 'profit')
  const [expanded, setExpanded] = useState<string[]>(['total_cost', 'cash_in', 'cash_out'])
  const source = tab === 'profit' ? record.metrics : record.cashMetrics
  const visible = source.filter((item) => !item.parent || expanded.includes(item.parent))
  return <div className="page">
    <PageHead eyebrow="真实财务计算结果 · 离线展示" title="先确认财务变化，再展开会计形成路径" description="项目变化与对上层目标的会计影响分列展示；父项与子项不重复加总。"/>
    {(() => { const metric=record.metrics.concat(record.cashMetrics).find((m) => m.id === selectedId); return metric ? <section className="panel-card selected-financial"><h2>{metric.name}</h2><p>{record.run.basePeriod}：{metric.base} · {record.run.currentPeriod}：{metric.current}</p><p>自身变化：{metric.delta} · 同比：{metric.yoy}</p><p>{metric.status}；对目标的会计影响须结合下方对应桥接层级阅读。</p><div className="link-chips">{linkedEvidence(record,metric).map((e) => <button key={e.id} onClick={() => onEvidence(e.id)}>{e.id} · {e.fileName} · 印刷 {e.printPage} / PDF {e.pdfPage}</button>)}{!linkedEvidence(record,metric).length && <span>未提供关联记录</span>}</div></section> : <Empty title="未提供关联财务记录" detail="当前案例中不存在该指标，不从其他案例补充。"/> })()}
    <div className="tabs"><button className={tab === 'profit' ? 'active' : ''} onClick={() => setTab('profit')}>利润链</button><button className={tab === 'cash' ? 'active' : ''} onClick={() => setTab('cash')}>经营现金流</button></div>
    <OfflineResults record={record} kind={tab} onEvidence={onEvidence}/><div className="trace-summary">
      <div><span>{tab === 'profit' ? '追溯目标' : '研究入口'}</span><strong>{tab === 'profit' ? `归母净利润变化 ${record.metrics.find((m) => m.id === 'parent_profit')?.delta ?? '未提供'}` : '经营现金流披露金额'}</strong></div><Icon name="arrow"/><div><span>当前边界</span><strong>{record.run.isExample ? '交互示例' : '桥接闭合状态见各目标；不推断经营因果'}</strong></div><Badge tone="warning">不可据此生成经营结论</Badge>
    </div>
    <details className="audit-details"><summary>全部财务项目、来源与原始金额</summary><div className="table-shell">
      <table><thead><tr><th>财务项目 / 关系</th><th>基期</th><th>本期</th><th>项目变化</th><th>对目标影响</th><th>数据来源</th><th>核验状态</th><th/></tr></thead>
      <tbody>{visible.map((item) => <tr key={item.id} className={selectedId === item.id ? 'selected-row' : ''} onClick={() => onSelect(item.id)}>
        <td><div className={`tree-cell level-${item.level}`}>{item.expandable ? <button className={`expand ${expanded.includes(item.id) ? 'open' : ''}`} onClick={(event) => { event.stopPropagation(); setExpanded((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id]) }}><Icon name="chevron" size={14}/></button> : <span className="tree-dot"/>}<div><strong>{item.name}</strong><small>{item.relation}</small></div></div></td>
        <td className="number">{item.base}</td><td className="number">{item.current}</td><td className="number">{item.delta}</td><td className="number">{item.impact}</td><td><span className="source-name">{record.evidence.filter((e) => e.metrics.includes(item.id)).slice(0,3).map((e) => <button className="data-link" key={e.id} onClick={(event) => { event.stopPropagation(); onEvidence(e.id) }}>{e.id}</button>)}{!record.evidence.some((e) => e.metrics.includes(item.id)) && item.source}</span></td><td><Badge tone={item.status.includes('待') || item.status.includes('部分') ? 'warning' : 'neutral'}>{item.status}</Badge></td><td><Icon name="chevron" size={15}/></td>
      </tr>)}</tbody></table>
    </div>
    </details><p className="table-caption"><Icon name="alert" size={15}/> 当前仅呈现后端提供的组成项，不添加“其他”项目自动补平。金额保持后端提供的字符串。</p>
  </div>
}

function EvidencePage({ record, selectedEvidenceId, selectedExplanationId, onEvidence, onExplanation, onMetric }: { record: CaseRecord; selectedEvidenceId: string; selectedExplanationId: string; onEvidence: (id: string) => void; onExplanation: (id: string) => void; onMetric: (id: string) => void }) {
  const [filter, setFilter] = useState<'all' | Explanation['kind']>('all')
  const explanations = record.explanations.filter((item) => filter === 'all' || item.kind === filter)
  const selectedExplanation = record.explanations.find((item) => item.id === selectedExplanationId) ?? explanations[0]
  const selectedEvidence = record.evidence.find((item) => item.id === selectedEvidenceId) ?? record.evidence.find((item) => selectedExplanation?.citations.includes(item.id)) ?? record.evidence[0]
  return <div className="page evidence-page">
    <PageHead eyebrow="关联证据" title="核对年报原文与来源页码" description="来源核验是后端记录，不等于浏览器重新核验，也不等于因果关系成立。"/>
    <label className="import-note">证据目录（{record.evidence.length} 条）<select aria-label="选择证据" value={selectedEvidence?.id ?? ''} onChange={(event) => onEvidence(event.target.value)}>{record.evidence.map((e) => <option key={e.id} value={e.id}>{e.id} · 印刷 {e.printPage} / PDF {e.pdfPage}</option>)}</select></label>
    <div className={`filter-row ${record.explanations.length ? "" : "no-explanations"}`}><button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>全部 {record.explanations.length}</button><button className={filter === 'accounting_fact' ? 'active' : ''} onClick={() => setFilter('accounting_fact')}>财务事实</button><button className={filter === 'disclosure_explanation' ? 'active' : ''} onClick={() => setFilter('disclosure_explanation')}>披露解释</button><button className={filter === 'hypothesis' ? 'active' : ''} onClick={() => setFilter('hypothesis')}>待验证假设</button></div>
    <div className={`evidence-workbench ${record.explanations.length ? "" : "source-only"}`}>
      <section className="explanation-list"><div className="column-label">候选解释</div>{explanations.map((item) => <button key={item.id} className={`explanation-card ${selectedExplanation?.id === item.id ? 'selected' : ''}`} onClick={() => { onExplanation(item.id); if (item.citations[0]) onEvidence(item.citations[0]) }}>
        <div><Badge tone={item.kind === 'hypothesis' ? 'warning' : 'info'}>{kindLabel[item.kind]}</Badge><span>{item.id}</span></div><p>{item.statement}</p><small>{item.supportLimit}</small>
      </button>)}</section>
      <section className="explanation-detail">{selectedExplanation ? <><div className="column-label">解释结构</div><div className="detail-title"><Badge tone={selectedExplanation.kind === 'hypothesis' ? 'warning' : 'info'}>{kindLabel[selectedExplanation.kind]}</Badge><details className="audit-details"><summary>原始检查状态</summary>{selectedExplanation.checkStatus}</details></div><h2>{selectedExplanation.statement}</h2>
        <InfoBlock label="关联财务项目">{selectedExplanation.metrics.map((id) => <button className="data-link" key={id} onClick={() => onMetric(id)}>{record.metrics.concat(record.cashMetrics).find((m) => m.id === id)?.name ?? id}<Icon name="arrow" size={12}/></button>)}</InfoBlock>
        <InfoBlock label="关联金额">{selectedExplanation.amounts.map((amount) => <code key={amount}>{amount}</code>)}</InfoBlock>
        <InfoBlock label="会计关系"><p>{selectedExplanation.accountingLinks}</p></InfoBlock>
        <InfoBlock label="比较口径"><p>{selectedExplanation.comparisonBasis}</p></InfoBlock>
        <InfoBlock label="支持边界"><p>{selectedExplanation.supportLimit}</p></InfoBlock>
        <InfoBlock label="引文定位">{selectedExplanation.citations.length ? selectedExplanation.citations.map((id) => <button className="citation" key={id} onClick={() => onEvidence(id)}>[{id}] 查看原文 <Icon name="arrow" size={12}/></button>) : <span className="missing">缺少引文对应原文，不补写</span>}</InfoBlock>
      </> : <Empty title="未提供合规最终解释" detail="可单独查看来源证据；不存在的解释和引文不会用模拟内容补充。"/>}</section>
      <section className="source-reader"><div className="column-label">证据原文</div>{selectedEvidence ? <EvidenceReader evidence={selectedEvidence} onMetric={onMetric}/> : <Empty title="没有可定位原文" detail="当前解释缺少引文，或对应证据文件未导入。"/>}</section>
    </div>
  </div>
}

function InfoBlock({ label, children }: { label: string; children: React.ReactNode }) { return <div className="info-block"><span>{label}</span><div>{children}</div></div> }
function EvidenceReader({ evidence, onMetric }: { evidence: Evidence; onMetric: (id: string) => void }) {
  return <div className="reader"><div className="reader-head"><div><Badge tone="info">{evidence.id}</Badge><strong>{evidence.fileName}</strong></div><span>印刷 {evidence.printPage} · PDF {evidence.pdfPage}</span></div><div className="verification"><Icon name="check" size={15}/>{evidence.verification}</div><div className="quote"><span>逐字原文</span><blockquote>“{evidence.quote}”</blockquote></div><InfoBlock label="摘要"><p>{evidence.summary}</p></InfoBlock><InfoBlock label="支持边界"><p>{evidence.supportLimit}</p></InfoBlock><InfoBlock label="相关项目">{evidence.metrics.map((id) => <button className="data-link" key={id} onClick={() => onMetric(id)}>{id}<Icon name="arrow" size={12}/></button>)}</InfoBlock><div className="source-disabled"><Icon name="file"/><div><strong>原文件未嵌入前端</strong><p>仅展示后端记录的文件名与页码，不制作虚假 PDF 预览。</p></div></div></div>
}

function ContextPanel({ record, view, metricId, evidenceId, explanationId, onClose }: { record: CaseRecord; view: ViewId; metricId: string; evidenceId: string; explanationId: string; onClose: () => void }) {
  const metric = record.metrics.concat(record.cashMetrics).find((item) => item.id === metricId)
  const evidence = record.evidence.find((item) => item.id === evidenceId)
  const explanation = record.explanations.find((item) => item.id === explanationId)
  return <aside className="context-panel"><div className="context-head"><div><span>上下文详情</span><strong>{view === 'financials' && metric ? metric.name : view === 'evidence' && explanation ? explanation.id : record.run.id}</strong></div><button className="icon-button" onClick={onClose}><Icon name="close"/></button></div>
    {view === 'financials' && metric ? <><div className="context-section"><span>展示金额</span><div className="amount-pair"><div><small>基期</small><strong>{metric.base}</strong></div><div><small>本期</small><strong>{metric.current}</strong></div></div></div><ContextRow label="项目变化" value={metric.delta}/><ContextRow label="对目标影响" value={metric.impact}/><ContextRow label="比较口径" value={`${record.run.currentPeriod} 较 ${record.run.basePeriod}`}/><ContextRow label="来源" value={metric.source}/><ContextRow label="原始元金额" value={metric.rawAmounts ? ('基期 ' + (metric.rawAmounts.base ?? '未提供') + '；本期 ' + (metric.rawAmounts.current ?? '未提供') + ' 元') : '未在示例展示层提供'}/><div className="context-section"><span>关联证据</span>{record.evidence.filter((e) => e.metrics.includes(metric.id)).map((e) => <div className="mini-source" key={e.id}><Badge tone="info">{e.id}</Badge><p>{e.summary}</p></div>)}{!record.evidence.some((e) => e.metrics.includes(metric.id)) && <p>未查询到关联证据。</p>}</div></> :
    view === 'evidence' && evidence ? <><ContextRow label="证据编号" value={evidence.id}/><ContextRow label="原始文件名" value={evidence.fileName}/><ContextRow label="来源定位" value={`${evidence.printPage} · ${evidence.pdfPage}`}/><ContextRow label="比较口径" value={evidence.basis}/><ContextRow label="后端来源核验" value={evidence.verification}/><div className="context-section"><span>技术字段</span><code>{`metric_ids: ${JSON.stringify(evidence.metrics)}`}</code></div></> :
    <><ContextRow label="运行编号" value={record.run.id}/><ContextRow label="后端运行时间" value={record.run.backendRunAt}/><ContextRow label="导入时间" value={record.run.importedAt}/><ContextRow label="数据来源" value={record.run.source}/><ContextRow label="运行模式" value={`${modeLabel[record.run.mode]} (${record.run.mode})`}/><ContextRow label="原始状态码" value={record.run.status}/><div className="context-section"><span>边界说明</span><p>当前界面不连接业务 API，不执行模型调用，也不在浏览器配置模型密钥。</p></div></>}
    <div className="context-footer"><span>数据隔离</span><p>切换运行会同步切换整套上下文，避免混用不同版本的结果。</p></div>
  </aside>
}

function ContextRow({ label, value }: { label: string; value: string }) { return <div className="context-row"><span>{label}</span><strong>{value}</strong></div> }

export default App
