import type { CaseRecord } from './types'
import { openingCase } from './workflow'

export function IntroPage({ records, notice, onChoose, onArchive }: {
  records: CaseRecord[]; notice: string; onChoose: () => void; onArchive: () => void
}) {
  const record = openingCase(records)
  const metrics = record ? [...record.metrics, ...record.cashMetrics] : []
  return <main className="intro-page">
    <header className="intro-header"><div className="intro-brand">TraceLab <span>盈迹</span></div><span>财务变化驱动的上市公司业绩归因与证据验证智能体</span><button className="text-link" onClick={onArchive}>研究档案与导入</button></header>
    <div className="intro-content">
      <section className="intro-hero">
        <div><span className="eyebrow">从财务变化发现问题，以可信证据追溯原因</span><h1>利润下降，<br/>现金流却在增长。<br/><em>为什么？</em></h1><p>以格力电器 2024—2025 年为例，<br/>从会计变化出发，寻找经营解释的证据。</p><span className="intro-question-label">研究问题 · 尚非经营原因结论</span></div>
        <div className="intro-comparison"><div className="intro-comparison-head"><strong>格力电器</strong><span>2025 年较 2024 年 · 合并报表</span></div>
          {[['net_profit','净利润'],['operating_cashflow','经营活动现金流量净额']].map(([id,label]) => {
            const metric = metrics.find((m) => m.id === id)
            const yoy = metric?.yoy && /^-?\d+(\.\d+)?%$/.test(metric.yoy) ? metric.yoy : '未提供'
            return <article className={`intro-metric ${id === 'net_profit' ? 'profit' : 'cash'}`} key={id}><span>{label}</span><strong>{yoy}</strong><small>同比变化 · 后端核验结果</small><p>金额变化：{metric?.delta ?? '未提供'}</p></article>
          })}
          <p className="intro-data-note">{record ? `真实财务数据 · ${record.run.scope}` : '真实案例数据尚不可用；不以模拟数据代替。'}</p>
        </div>
      </section>
      <section className="intro-questions" aria-label="三个研究问题">{['净利润究竟发生了多大变化？','哪些会计项目形成了利润变化？','经营解释有年报证据支持吗？'].map((q,i) => <div key={q}><span>0{i+1}</span><h2>{q}</h2></div>)}</section>
      <section className="intro-method" aria-label="产品方法与当前能力"><div><strong>财务计算</strong><span>核对两期金额与会计贡献</span></div><div><strong>Agent 调查</strong><span>真实历史：检索与原文读取</span></div><div><strong>证据验证</strong><span>来源可追溯，经营解释仍待完善</span></div><div><strong>分析报告</strong><span>展示已核验事实与支持边界</span></div></section>
      <div className="intro-entry"><button className="btn primary" onClick={onChoose}>选择研究资料 →</button><p>选择已准备案例，载入已有分析结果<br/>不上传 PDF，不启动新调查</p></div>
      {notice && <p className="import-note" role="status">{notice}</p>}
      <details className="audit-details intro-capabilities"><summary>核心能力与当前边界</summary><p>已有后端能力：CSV / Excel 读取与口径校验、Decimal 精确计算、利润层级桥接、现金流勾稽、来源与页码追溯。前端展示既有结果。</p><p>辅助工具：已适配格力指定合并利润表的 PDF 提取；结构化陈述确定性纠错（人为构造示例）。不支持任意 PDF 在线分析或任意研报全文理解。</p><p>真实 Qwen 历史调用已完成 search / get。完整经营解释与自主调查闭环尚未完成；规划能力不计入本次真实成果。</p></details>
    </div>
  </main>
}
