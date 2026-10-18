import type { ActionStep, CaseRecord, Metric, ViewId } from './types'

// Navigation order only, never an execution pipeline or completion state.
export const workflow = [
  { id: 'overview', label: '业绩分析', hint: '发现财务变化' },
  { id: 'investigation', label: 'Agent 调查', hint: '调查变化原因' },
  { id: 'review', label: '核验报告与证据', hint: '查看阶段性结果与支持边界' },
] as const

export const viewLabels: Record<ViewId, string> = {
  intro: '产品介绍',
  overview: '业绩分析', investigation: 'Agent 调查', review: '核验报告与证据',
  financials: '财务计算详情', evidence: '证据原文', pdf: 'PDF 提取详情', report: '结构化研报纠错', cases: '研究档案',
}

// The opening example must be this real case, never the currently selected mock.
export function openingCase(records: CaseRecord[]): CaseRecord | undefined {
  return records.find((r) => !r.run.isExample && r.run.mode === 'qwen_real'
    && ['珠海格力电器股份有限公司', '格力电器'].includes(r.run.company)
    && r.run.basePeriod === '2024' && r.run.currentPeriod === '2025')
}

export function preparedSourceFiles(record: CaseRecord): string[] {
  return [...new Set(record.evidence.map((e) => e.fileName))].sort()
}

// The freshly adapted bundle must still describe the case the user selected.
export function verifyPreparedCase(selected: CaseRecord, loaded: CaseRecord): CaseRecord {
  if (!openingCase([loaded]) || selected.id !== loaded.id || selected.run.id !== loaded.run.id
    || selected.run.materialVersion !== loaded.run.materialVersion
    || JSON.stringify(preparedSourceFiles(selected)) !== JSON.stringify(preparedSourceFiles(loaded))) {
    throw new Error('案例或资料版本已变化，请关闭窗口并刷新页面后重新选择。')
  }
  return loaded
}

export function primaryView(view: ViewId): ViewId {
  return view === 'investigation' || view === 'review' ? view : 'overview'
}

export function coreMetrics(record: CaseRecord): Metric[] {
  const all = [...record.metrics, ...record.cashMetrics]
  return ['revenue','net_profit','parent_profit','operating_profit','operating_cashflow']
    .map((id) => all.find((m) => m.id === id || (id === 'operating_cashflow' && m.id === 'operating_cash')))
    .filter((m): m is Metric => m !== undefined)
}

export function linkedEvidence(record: CaseRecord, metric: Metric) {
  const direct = record.evidence.filter((e) => metric.source.split(', ').includes(e.id))
  return direct.length ? direct : record.evidence.filter((e) => e.metrics.includes(metric.id))
}

export function agentOutcome(record: CaseRecord) {
  if (record.run.isExample) return '概念演示 / 模拟运行，非真实模型调查结果'
  return record.run.status === 'validation_failed' ? '自主调查未完成' : '调查状态以原始记录为准'
}

export function actionTitle(step: ActionStep) {
  if (step.error === 'incomplete_response') return '响应不完整，未形成有效动作'
  const labels: Partial<Record<ActionStep['action'],string>> = {
    search:'检索相关年报证据', get:'读取已定位的证据原文', facts_list:'查看可用财务事实',
    fact_get:'读取财务事实', list:'查看可用证据', error:'动作未通过校验',
  }
  return labels[step.action] ?? step.label
}

export function resolveLink(record: CaseRecord, id: string): 'evidence' | 'metric' | 'explanation' | 'missing' {
  if (record.evidence.some((e) => e.id === id)) return 'evidence'
  if ([...record.metrics,...record.cashMetrics].some((m) => m.id === id)) return 'metric'
  if (record.explanations.some((e) => e.id === id)) return 'explanation'
  return 'missing'
}

export function adjacent(view: ViewId, direction: -1 | 1): ViewId | undefined {
  const index = workflow.findIndex((step) => step.id === view)
  return index < 0 ? undefined : workflow[index + direction]?.id
}

// Read the existing export's labelled rows. Never calculate or infer a verdict.
export function claimSummary(record: CaseRecord) {
  const section = record.modules?.sections.find((s) => s.kind === 'report')
  const value = (label: string) => section?.rows.find((row) => row.cells[0] === label)?.cells[1] ?? '未提供'
  return {
    statement: value('原始陈述'), status: value('核查状态'), error: value('错误类型'),
    correction: value('纠错建议'), metric: value('metric_name'),
    evidenceIds: section?.rows.find((row) => row.cells[0] === '核查状态')?.evidenceIds ?? [],
  }
}
