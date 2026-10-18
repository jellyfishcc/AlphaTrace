import { OfflineResults } from './OfflineResults'
import { useEffect, useMemo, useRef, useState } from 'react'
import { adaptLocalFiles, loadDisplayBundle } from '@/data/adapter'
import { exampleCases } from '@/data/example'
import type { CaseRecord, Evidence, Explanation, Metric, StatusTone, ViewId } from '@/types'

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

const nav: { id: ViewId; label: string; icon: IconName; index: string }[] = [
  { id: 'cases', label: '研究档案', icon: 'cases', index: '01' },
  { id: 'overview', label: '调查工作台', icon: 'overview', index: '02' },
  { id: 'review', label: '核验与交付', icon: 'review', index: '03' },
]

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
  const [view, setView] = useState<ViewId>('overview')
  const [panelOpen, setPanelOpen] = useState(true)
  const [selectedMetricId, setSelectedMetricId] = useState('operating_profit')
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('E12_A')
  const [selectedExplanationId, setSelectedExplanationId] = useState('EXP-02')
  const [traceOpen, setTraceOpen] = useState(false)
  const [loadNotice, setLoadNotice] = useState('正在加载真实案例展示包…')
  const fileRef = useRef<HTMLInputElement>(null)
  const record = records.find((item) => item.id === selectedId) ?? records[0]

  useEffect(() => {
    let active = true
    loadDisplayBundle().then((real) => {
      if (!active) return
      setRecords([real, ...exampleCases]); setSelectedId(real.id); setLoadNotice('')
    }).catch(() => { if (active) setLoadNotice('真实展示包缺失或校验失败；当前仅有明确标注的交互示例。请先运行 Python display_export。') })
    return () => { active = false }
  }, [])
  useEffect(() => {
    setSelectedMetricId(record.metrics[0]?.id ?? '')
    setSelectedEvidenceId(record.evidence[0]?.id ?? '')
    setSelectedExplanationId(record.explanations[0]?.id ?? '')
    setTraceOpen(false)
  }, [selectedId])

  const goMetric = (id: string) => { setSelectedMetricId(id); setView('financials'); setTraceOpen(false); setPanelOpen(true) }
  const goEvidence = (id: string) => { setSelectedEvidenceId(id); setView('evidence'); setTraceOpen(false); setPanelOpen(true) }
  const goExplanation = (id: string) => { setSelectedExplanationId(id); setView('evidence'); setTraceOpen(false); setPanelOpen(true) }

  const handleImport = async (files: FileList | null) => {
    if (!files?.length) return
    try {
      const bundle = await adaptLocalFiles(Array.from(files))
      setRecords((current) => [bundle.record, ...current.filter((r) => r.id !== bundle.record.id)])
      setSelectedId(bundle.record.id); setView('overview'); setLoadNotice('')
    } catch (error) {
      setLoadNotice(error instanceof Error ? error.message : '展示包导入失败')
    }
    if (fileRef.current) fileRef.current.value = ''
  }

  const renderView = () => {
    if (view === 'cases') return <CasesPage records={records} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setView('overview') }} onImport={() => fileRef.current?.click()}/>
    if (view === 'review') return <ReviewPage record={record} importedFiles={[]}/>
    return <>
      <WorkbenchNav view={view} traceOpen={traceOpen} onView={(next) => { setView(next); setTraceOpen(false) }} onTrace={() => setTraceOpen((open) => !open)}/>
      {traceOpen
        ? <InvestigationPage key={record.id} record={record} embedded onClose={() => setTraceOpen(false)} onLink={(id) => id.startsWith('EXP') ? goExplanation(id) : record.evidence.some((e) => e.id === id) ? goEvidence(id) : goMetric(id)}/>
        : view === 'report' || view === 'pdf'
          ? <div className="page"><OfflineResults record={record} kind={view} onEvidence={goEvidence}/></div>
        : view === 'financials'
          ? <FinancialsPage onEvidence={goEvidence} key={record.id + selectedMetricId} record={record} selectedId={selectedMetricId} onSelect={(id) => { setSelectedMetricId(id); setPanelOpen(true) }}/>
          : view === 'evidence'
            ? <EvidencePage key={record.id} record={record} selectedEvidenceId={selectedEvidenceId} selectedExplanationId={selectedExplanationId} onEvidence={setSelectedEvidenceId} onExplanation={setSelectedExplanationId} onMetric={goMetric}/>
            : <OverviewPage record={record} onMetric={goMetric} onInvestigation={() => setTraceOpen(true)} onExplanation={goExplanation} importNotices={record.notices ?? []}/>
      }
    </>
  }

  return (
    <div className="app-shell">
      <input ref={fileRef} className="sr-only" type="file" accept=".json" onChange={(event) => handleImport(event.target.files)}/>
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><span/><span/><span/></div><div><strong>TraceLab</strong><small>业绩调查工作台</small></div></div>
        <div className="case-mini"><span>当前案例</span><strong>{record.run.company}</strong><small>{record.run.currentPeriod} vs {record.run.basePeriod}</small></div>
        <nav>
          <p className="nav-title">研究空间</p>
          {nav.map((item) => {
            const active = item.id === 'overview' ? !['cases', 'review'].includes(view) : view === item.id
            return <button key={item.id} className={active ? 'nav-item active' : 'nav-item'} onClick={() => { setView(item.id); setTraceOpen(false) }}><span className="nav-index">{item.index}</span><Icon name={item.icon}/><span>{item.label}</span>{item.id === 'review' && record.pendingCount > 0 ? <em>{record.pendingCount}</em> : null}</button>
          })}
        </nav>
        <div className="sidebar-foot"><div className="principle-line"/><p>“从数字到原因，<br/>中间不能跳步。”</p><span>TraceLab research protocol</span></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="top-case">
            <span className="eyebrow">当前运行上下文</span>
            <div className="top-case-title"><strong>{record.run.company}</strong><span>{record.run.ticker}</span><Badge tone={record.run.isExample ? 'neutral' : 'info'}>{record.run.isExample ? '交互示例，非真实运行' : '本地导入'}</Badge></div>
          </div>
          <div className="top-fields">
            <div><span>比较期间</span><strong>{record.run.basePeriod} → {record.run.currentPeriod}</strong></div>
            <div><span>报表口径</span><strong>{record.run.scope}</strong></div>
            <div><span>资料版本</span><strong>{record.run.materialVersion}</strong></div>
          </div>
          <div className="run-control">
            <span>运行</span>
            <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{records.map((item) => <option key={item.id} value={item.id}>{item.run.id} · {item.run.label}</option>)}</select>
            <Badge tone={record.run.mode === 'qwen_replay' ? 'info' : 'warning'}>{modeLabel[record.run.mode]}</Badge>
          </div>
          <button className={`icon-button ${panelOpen ? 'active' : ''}`} aria-label="切换详情面板" onClick={() => setPanelOpen((value) => !value)}><Icon name="panel"/></button>
        </header>

        <main className={panelOpen ? 'main-grid panel-visible' : 'main-grid'}>
          <div className="content-area">{loadNotice && <div className="import-note" role="status">{loadNotice}</div>}{renderView()}</div>
          {panelOpen && <ContextPanel record={record} view={traceOpen ? 'investigation' : view} metricId={selectedMetricId} evidenceId={selectedEvidenceId} explanationId={selectedExplanationId} onClose={() => setPanelOpen(false)}/>}
        </main>
      </section>
    </div>
  )
}

function PageHead({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) {
  return <div className="page-head"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</div>
}

function WorkbenchNav({ view, traceOpen, onView, onTrace }: { view: ViewId; traceOpen: boolean; onView: (view: ViewId) => void; onTrace: () => void }) {
  return <div className="workbench-nav">
    <div><span>调查工作台</span>
      <button className={view === 'report' && !traceOpen ? 'active' : ''} onClick={() => onView('report')}>研报纠错</button>
      <button className={view === 'pdf' && !traceOpen ? 'active' : ''} onClick={() => onView('pdf')}>PDF 提取</button>
      <button className={view === 'overview' && !traceOpen ? 'active' : ''} onClick={() => onView('overview')}>概览</button>
      <button className={view === 'financials' && !traceOpen ? 'active' : ''} onClick={() => onView('financials')}>财务拆解</button>
      <button className={view === 'evidence' && !traceOpen ? 'active' : ''} onClick={() => onView('evidence')}>原因与证据</button>
    </div>
    <button className={`trace-toggle ${traceOpen ? 'active' : ''}`} onClick={onTrace}><Icon name="route" size={16}/>{traceOpen ? '收起调查轨迹' : '查看调查轨迹'}</button>
  </div>
}

function CasesPage({ records, selectedId, onSelect, onImport }: { records: CaseRecord[]; selectedId: string; onSelect: (id: string) => void; onImport: () => void }) {
  return <div className="page">
    <PageHead eyebrow="案例资料库" title="研究案例" description="浏览明确加载的示例或本地导入记录。这里没有连接远程项目数据库。" actions={<><button className="btn secondary" disabled title="后端尚未提供浏览器可调用的业务 API"><Icon name="lock"/> 新建在线调查 · 待接入</button><button className="btn primary" onClick={onImport}><Icon name="upload"/> 导入运行结果</button></>}/>
    <div className="import-note"><Icon name="alert"/><p><strong>本地导入说明</strong> 仅导入 Python 导出的 *-display.json 展示包，不上传服务器。不要选择原始附件、input.json 或完整日志。浏览器不重新认证来源。</p></div>
    <div className="case-list-head"><span>{records.length} 个运行记录</span><div className="search-static"><Icon name="search"/><span>按公司、问题或运行编号筛选</span></div></div>
    <div className="case-cards">{records.map((item) => <button key={item.id} className={`case-card ${item.id === selectedId ? 'selected' : ''}`} onClick={() => onSelect(item.id)}>
      <div className="case-card-top"><div><span className="case-ticker">{item.run.ticker}</span><h2>{item.run.company}</h2></div><Badge tone={item.run.status === 'validation_failed' ? 'danger' : 'warning'}>{item.run.statusLabel}</Badge></div>
      <p className="case-question">{item.question}</p>
      <div className="case-meta"><div><span>比较期间</span><strong>{item.run.basePeriod} → {item.run.currentPeriod}</strong></div><div><span>资料版本</span><strong>{item.run.materialVersion}</strong></div><div><span>导入时间</span><strong>{item.run.importedAt}</strong></div><div><span>后端运行时间</span><strong>{item.run.backendRunAt}</strong></div></div>
      <div className="case-card-foot"><Badge tone={item.run.isExample ? 'neutral' : 'info'}>{item.run.isExample ? '交互示例，非真实运行' : '浏览器本地记录'}</Badge><span>{item.pendingCount} 项待处理 <Icon name="arrow" size={15}/></span></div>
    </button>)}</div>
  </div>
}

function OverviewPage({ record, onMetric, onInvestigation, onExplanation, importNotices }: { record: CaseRecord; onMetric: (id: string) => void; onInvestigation: () => void; onExplanation: (id: string) => void; importNotices: string[] }) {
  const headline = ['operating_profit', 'pretax_profit', 'profit_total', 'net_profit', 'minority_profit', 'minority', 'parent_profit', 'operating_cashflow', 'operating_cash'].map((id) => [...record.metrics, ...record.cashMetrics].find((item) => item.id === id)).filter(Boolean) as Metric[]
  if (!record.run.isExample && record.metrics.length === 0) return <div className="page"><PageHead eyebrow="案例概览" title={record.question} description="本地结果已载入；缺失字段保持“未提供”，不会自动补入示例内容。"/><div className="notice-stack">{importNotices.map((notice) => <div className="import-note" key={notice}><Icon name="alert"/><p>{notice}</p></div>)}</div><Empty title="暂无可展示的统一财务数据" detail="适配入口已识别文件和运行上下文。需要后端技术人员按数据契约补充对应版本的字段映射。"/></div>
  return <div className="page">
    <PageHead eyebrow="案例概览" title={record.question} description="从财务变化出发，追查原因，再回到证据。"/>
    <div className="import-note"><Badge tone={record.run.status === 'validation_failed' ? 'danger' : 'warning'}>{record.run.statusLabel}</Badge><span>{record.run.status}</span></div>
    {importNotices.map((notice) => <p className="technical-hint" key={notice}>{notice}</p>)}
    <section className="goal-card"><div className="goal-number">01</div><div><span>调查目标</span><h2>解释利润与现金流变化的形成路径，并区分已确认事实、受支持解释与尚待验证问题。</h2></div><button className="text-link" onClick={onInvestigation}>查看实际调查轨迹 <Icon name="arrow" size={15}/></button></section>
    <div className="section-head"><div><span>核心变化</span><h2>最相关的财务指标</h2></div><small>后端字段原样展示，前端未重算</small></div>
    <div className="metric-ledger">
      <div className="metric-ledger-head"><span>项目</span><span>基期</span><span>本期</span><span>项目变化</span><span>同比</span><span>来源状态</span><span/></div>
      {headline.map((item) => <button key={item.id} onClick={() => onMetric(item.id)}>
        <strong>{item.name}</strong><span>{item.base}</span><span>{item.current}</span><b className={/^[-−]/.test(item.delta) ? 'negative' : item.delta === '未提供' ? '' : 'positive'}>{item.delta}</b><span>{item.yoy}</span><Badge tone={item.status.includes('待') ? 'warning' : 'neutral'}>{item.status}</Badge><Icon name="chevron" size={15}/>
      </button>)}
    </div>
    <div className="overview-columns">
      <section className="panel-card">{record.run.isExample ? <><div className="panel-card-title"><div><span>调查信号</span><h2>值得继续追查的方向</h2></div><Badge tone="warning">3 项</Badge></div>
        <button className="signal" onClick={() => onMetric('operating_cash')}><i>01</i><div><strong>利润与经营现金流走势分化</strong><p>归母净利润下降，经营现金流净额增长；方向差异本身不构成盈利质量结论。</p></div><Icon name="chevron"/></button>
        <button className="signal" onClick={() => onMetric('admin_expense')}><i>02</i><div><strong>管理费用逆向增加</strong><p>费用项目对营业利润形成负向影响，存在可定位披露。</p></div><Icon name="chevron"/></button>
        <button className="signal" onClick={onInvestigation}><i>03</i><div><strong>收入下降原因仍待查明</strong><p>当前候选假设缺少可定位原文，不可作为结论。</p></div><Icon name="chevron"/></button>
        </> : <><div className="panel-card-title"><h2>真实调查状态</h2><Badge tone="danger">{record.run.status}</Badge></div><p>{record.run.statusLabel}</p><p>财务事实来源核验与 Agent 最终解释验收分开呈现。</p><button className="text-link" onClick={onInvestigation}>查看实际工具调用与失败原因</button></>}
      </section>
      <section className="panel-card"><div className="panel-card-title"><div><span>当前结果</span><h2>候选解释与检查</h2></div><button className="text-link" onClick={() => onExplanation(record.explanations[0]?.id)}>查看全部</button></div>
        {record.explanations.map((item) => <button className="explanation-row" key={item.id} onClick={() => onExplanation(item.id)}><div><Badge tone={item.kind === 'hypothesis' ? 'warning' : 'info'}>{kindLabel[item.kind]}</Badge><Badge tone={item.checkStatus.includes('不足') ? 'danger' : 'neutral'}>{item.checkStatus}</Badge></div><p>{item.statement}</p><span>{item.citations.length ? `${item.citations.length} 条引文` : '无引文'} <Icon name="arrow" size={14}/></span></button>)}
        {!record.explanations.length && <Empty title="未提供合规最终解释" detail="真实调查失败；不展示截断片段，不使用示例解释补充。"/>}
      </section>
    </div>
  </div>
}

function FinancialsPage({ record, selectedId, onSelect, onEvidence }: { record: CaseRecord; selectedId: string; onSelect: (id: string) => void; onEvidence: (id: string) => void }) {
  const [tab, setTab] = useState<'profit' | 'cash'>(record.cashMetrics.some((m) => m.id === selectedId) ? 'cash' : 'profit')
  const [expanded, setExpanded] = useState<string[]>(['total_cost', 'cash_in', 'cash_out'])
  const source = tab === 'profit' ? record.metrics : record.cashMetrics
  const visible = source.filter((item) => !item.parent || expanded.includes(item.parent))
  return <div className="page">
    <PageHead eyebrow="财务追踪" title="从结果反向追溯会计形成路径" description="项目变化与对上层目标的会计影响分列展示；父项与子项不重复加总。"/>
    <div className="tabs"><button className={tab === 'profit' ? 'active' : ''} onClick={() => setTab('profit')}>利润链</button><button className={tab === 'cash' ? 'active' : ''} onClick={() => setTab('cash')}>经营现金流</button></div>
    <OfflineResults record={record} kind={tab} onEvidence={onEvidence}/><div className="trace-summary">
      <div><span>{tab === 'profit' ? '追溯目标' : '研究入口'}</span><strong>{tab === 'profit' ? `归母净利润变化 ${record.metrics.find((m) => m.id === 'parent_profit')?.delta ?? '未提供'}` : '经营现金流披露金额'}</strong></div><Icon name="arrow"/><div><span>当前边界</span><strong>{record.run.isExample ? '交互示例' : '桥接闭合状态见各目标；不推断经营因果'}</strong></div><Badge tone="warning">不可据此生成经营结论</Badge>
    </div>
    <div className="table-shell">
      <table><thead><tr><th>财务项目 / 关系</th><th>基期</th><th>本期</th><th>项目变化</th><th>对目标影响</th><th>数据来源</th><th>核验状态</th><th/></tr></thead>
      <tbody>{visible.map((item) => <tr key={item.id} className={selectedId === item.id ? 'selected-row' : ''} onClick={() => onSelect(item.id)}>
        <td><div className={`tree-cell level-${item.level}`}>{item.expandable ? <button className={`expand ${expanded.includes(item.id) ? 'open' : ''}`} onClick={(event) => { event.stopPropagation(); setExpanded((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id]) }}><Icon name="chevron" size={14}/></button> : <span className="tree-dot"/>}<div><strong>{item.name}</strong><small>{item.relation}</small></div></div></td>
        <td className="number">{item.base}</td><td className="number">{item.current}</td><td className="number">{item.delta}</td><td className="number">{item.impact}</td><td><span className="source-name">{item.source}</span></td><td><Badge tone={item.status.includes('待') || item.status.includes('部分') ? 'warning' : 'neutral'}>{item.status}</Badge></td><td><Icon name="chevron" size={15}/></td>
      </tr>)}</tbody></table>
    </div>
    <p className="table-caption"><Icon name="alert" size={15}/> 当前仅呈现后端提供的组成项，不添加“其他”项目自动补平。金额保持后端提供的字符串。</p>
  </div>
}

function InvestigationPage({ record, onLink, embedded = false, onClose }: { record: CaseRecord; onLink: (id: string) => void; embedded?: boolean; onClose?: () => void }) {
  const totalRounds = record.agentSummary?.rounds ?? Math.max(0, ...record.steps.map((s) => s.round))
  const [visibleRound, setVisibleRound] = useState(totalRounds)
  const [openStep, setOpenStep] = useState<number | null>(2)
  const steps = record.steps.filter((step) => step.round <= visibleRound)
  return <div className={`page ${embedded ? 'trace-page' : ''}`}>
    <PageHead eyebrow="可展开轨迹" title="已记录的调查步骤" description="仅浏览后端保存的执行记录，不产生实时日志，也不展示隐藏思维链。" actions={<>{embedded && <button className="btn secondary" onClick={onClose}><Icon name="close"/> 返回工作台</button>}<button className="btn secondary" disabled><Icon name="lock"/> 启动调查 · 待接入</button></>}/>
    <div className="replay-banner"><div><Badge tone={record.run.isExample ? 'info' : 'danger'}>{record.run.isExample ? '模拟响应回放' : '真实历史记录 · validation_failed'}</Badge><strong>{record.run.id}</strong><span>simulation: {String(record.agentSummary?.simulation ?? true)} · llm_called: {String(record.agentSummary?.llm_called ?? false)} · real_request_attempts: {record.agentSummary?.real_request_attempts ?? 0}</span></div><div className="replay-controls"><button onClick={() => setVisibleRound((r) => Math.max(1, r - 1))}>上一步</button><span>查看至第 {visibleRound} / {totalRounds} 轮</span><button onClick={() => setVisibleRound((r) => Math.min(totalRounds, r + 1))}><Icon name="play" size={14}/> 下一步</button></div></div>
    <div className="investigation-layout">
      <div className="timeline">
        {steps.map((step, index) => <div className="timeline-item" key={`${step.round}-${step.action}-${index}`}><div className="timeline-marker"><span>{step.round}</span></div><div className="step-card">
          <button className="step-head" onClick={() => setOpenStep(openStep === index ? null : index)}><div><span>第 {step.round} 轮 · 记录 {index + 1}</span><h3>{step.label}</h3></div><Badge tone={step.error ? 'danger' : 'info'}>{step.error ? '失败 / 未执行' : '已记录'}</Badge><Icon name="chevron" size={16}/></button>
          <p>{step.summary}</p>
          {step.links.length > 0 && <div className="link-chips">{step.links.map((link) => <button key={link} onClick={() => onLink(link)}>{link} <Icon name="arrow" size={12}/></button>)}</div>}
          {openStep === index && <div className="step-detail"><dl><div><dt>工具名称</dt><dd><code>{step.action}</code></dd></div><div><dt>实际参数</dt><dd><code>{step.params}</code></dd></div><div><dt>返回内容</dt><dd>{step.result}</dd></div><div><dt>错误</dt><dd>{step.error ?? '未记录错误'}</dd></div></dl></div>}
        </div></div>)}
      </div>
      <aside className="run-stats"><span>运行使用量</span><h3>{record.run.isExample ? '示例记录' : '真实记录'}</h3><div className="stat"><strong>{totalRounds}</strong><span>已用轮数</span></div><div className="stat"><strong>{record.agentSummary?.tool_calls ?? '未提供'}</strong><span>工具调用</span></div><div className="stat"><strong>{record.agentSummary?.real_request_attempts ?? 0}</strong><span>真实模型请求</span></div><hr/><p><Icon name="alert" size={16}/>{record.run.statusLabel}</p><p>{record.agentSummary?.errors.join(', ') ?? '示例轨迹；非真实请求'}</p><p>{record.agentSummary?.stop_reason ?? '未提供停止原因码'}</p></aside>
    </div>
  </div>
}

function EvidencePage({ record, selectedEvidenceId, selectedExplanationId, onEvidence, onExplanation, onMetric }: { record: CaseRecord; selectedEvidenceId: string; selectedExplanationId: string; onEvidence: (id: string) => void; onExplanation: (id: string) => void; onMetric: (id: string) => void }) {
  const [filter, setFilter] = useState<'all' | Explanation['kind']>('all')
  const explanations = record.explanations.filter((item) => filter === 'all' || item.kind === filter)
  const selectedExplanation = record.explanations.find((item) => item.id === selectedExplanationId) ?? explanations[0]
  const selectedEvidence = record.evidence.find((item) => item.id === selectedEvidenceId) ?? record.evidence.find((item) => selectedExplanation?.citations.includes(item.id)) ?? record.evidence[0]
  return <div className="page evidence-page">
    <PageHead eyebrow="证据与解释" title="解释、引文与原文相互定位" description="来源核验是后端记录，不等于浏览器重新核验，也不等于因果关系成立。"/>
    <label className="import-note">证据目录（{record.evidence.length} 条）<select aria-label="选择证据" value={selectedEvidence?.id ?? ''} onChange={(event) => onEvidence(event.target.value)}>{record.evidence.map((e) => <option key={e.id} value={e.id}>{e.id} · 印刷 {e.printPage} / PDF {e.pdfPage}</option>)}</select></label>
    <div className="filter-row"><button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>全部 {record.explanations.length}</button><button className={filter === 'accounting_fact' ? 'active' : ''} onClick={() => setFilter('accounting_fact')}>财务事实</button><button className={filter === 'disclosure_explanation' ? 'active' : ''} onClick={() => setFilter('disclosure_explanation')}>披露解释</button><button className={filter === 'hypothesis' ? 'active' : ''} onClick={() => setFilter('hypothesis')}>待验证假设</button></div>
    <div className="evidence-workbench">
      <section className="explanation-list"><div className="column-label">候选解释</div>{explanations.map((item) => <button key={item.id} className={`explanation-card ${selectedExplanation?.id === item.id ? 'selected' : ''}`} onClick={() => { onExplanation(item.id); if (item.citations[0]) onEvidence(item.citations[0]) }}>
        <div><Badge tone={item.kind === 'hypothesis' ? 'warning' : 'info'}>{kindLabel[item.kind]}</Badge><span>{item.id}</span></div><p>{item.statement}</p><small>{item.checkStatus}</small>
      </button>)}</section>
      <section className="explanation-detail">{selectedExplanation ? <><div className="column-label">解释结构</div><div className="detail-title"><Badge tone={selectedExplanation.kind === 'hypothesis' ? 'warning' : 'info'}>{kindLabel[selectedExplanation.kind]}</Badge><Badge tone={selectedExplanation.checkStatus.includes('不足') ? 'danger' : 'success'}>{selectedExplanation.checkStatus}</Badge></div><h2>{selectedExplanation.statement}</h2>
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

function ReviewPage({ record, importedFiles }: { record: CaseRecord; importedFiles: File[] }) {
  const downloads = useMemo(() => importedFiles.map((file) => ({ file, url: URL.createObjectURL(file) })), [importedFiles])
  return <div className="page">
    <PageHead eyebrow="核验与交付" title="分开判断完成、检查与人工复核" description="不使用单一“成功”状态概括运行结果、软件检查和人工业务确认。"/>
    <div className="status-triad">
      <div><span className="status-index">01</span><div><small>运行记录</small><h2>{record.run.isExample ? '模拟回放已结束' : '结果文件已读取'}</h2><Badge tone="neutral">{record.run.isExample ? '未发起真实模型请求' : '以导入记录为准'}</Badge></div><Icon name="check"/></div>
      <div><span className="status-index">02</span><div><small>Agent 最终输出验收</small><h2>{record.run.statusLabel}</h2><Badge tone={record.run.status === 'validation_failed' ? 'danger' : 'warning'}>{record.run.status}</Badge></div><Icon name="alert"/></div>
      <div><span className="status-index">03</span><div><small>人工业务复核</small><h2>尚未确认</h2><Badge tone="warning">等待人工复核</Badge></div><Icon name="review"/></div>
    </div>
    <p className="technical-hint">内部状态码与运行模式保留在右侧“上下文详情”，不作为主要业务状态展示。</p>
    {record.run.isExample ? <div className="review-grid">
      <section className="panel-card conflicts"><div className="panel-card-title"><div><span>资料冲突</span><h2>未解决冲突</h2></div><Badge tone="danger">1 项</Badge></div><div className="conflict"><div><Badge tone="danger">待处理</Badge><strong>营业成本附注版本不一致</strong></div><dl><div><dt>来源 A</dt><dd>示例年度报告_2023.pdf · 第 86 页</dd></div><div><dt>来源 B</dt><dd>示例财务报表附注_v2.pdf · 第 84 页</dd></div><div><dt>期间</dt><dd>2023 年度</dd></div><div><dt>差异</dt><dd>分类口径描述一致，但文件版本号与页码不同，需确认最终版来源。</dd></div></dl></div><div className="missing-row"><Icon name="alert"/><span><strong>comparison.json</strong> 未导入</span><Badge tone="neutral">未导入</Badge></div></section>
      <section className="panel-card delivery"><div className="panel-card-title"><div><span>交付分组</span><h2>当前可交付内容</h2></div></div>
        {[['可确认的财务事实','2','success'],['可供人工复核的解释','2','info'],['待验证假设','1','warning'],['未解决冲突','1','danger'],['待确认问题','4','warning']].map(([label,count,tone]) => <div className="delivery-row" key={label}><span>{label}</span><Badge tone={tone as StatusTone}>{count} 项</Badge><Icon name="chevron" size={15}/></div>)}
      </section>
    </div> : <div className="review-grid"><section className="panel-card"><OfflineResults record={record} kind="verification"/><h3>Agent 失败原因</h3>{record.agentSummary?.errors.map((error) => <p key={error}>{error}</p>)}</section><section className="panel-card"><h2>已加载的后端结果</h2><p>{record.metrics.length + record.cashMetrics.length} 项财务记录 · {record.evidence.length} 条来源证据</p><p>{record.explanations.length} 条合规最终解释 · 人工业务复核未确认</p><p>来源核验通过不等于 Agent 分析通过。</p></section></div>}
    <section className="files-section"><div className="section-head"><div><span>运行记录和文件目录</span><h2>文件交付边界</h2></div></div>
      {downloads.length ? <div className="file-list">{downloads.map(({ file, url }) => <a key={file.name} href={url} download={file.name}><Icon name="file"/><div><strong>{file.name}</strong><span>{Math.ceil(file.size / 1024)} KB · 浏览器本地文件</span></div><Icon name="download"/></a>)}</div> : <div className="file-list disabled"><div><Icon name="file"/><div><strong>未提供原始附件与完整日志下载</strong><span>当前只读取白名单展示包；私有资料保留在 Python 工作区。</span></div><Badge tone="neutral">未导入</Badge></div></div>}
      <div className="future-actions"><button disabled><Icon name="lock"/> 导出 PDF / Word · 待接入</button><button disabled><Icon name="lock"/> 提交复核意见 · 待接入</button><button disabled><Icon name="lock"/> 签字审批 · 待接入</button></div>
    </section>
  </div>
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
