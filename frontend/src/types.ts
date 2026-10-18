export type ViewId = 'intro' | 'cases' | 'overview' | 'financials' | 'investigation' | 'evidence' | 'review' | 'report' | 'pdf'

export interface OfflineSection {
  kind: 'report' | 'pdf' | 'profit' | 'cash' | 'verification'
  title: string
  columns: string[]
  rows: { cells: string[]; evidenceIds: string[] }[]
  notices: string[]
  runId: string
  hashes: Record<string, string>
}

export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'purple'

export interface RunContext {
  id: string
  label: string
  company: string
  ticker: string
  basePeriod: string
  currentPeriod: string
  scope: string
  materialVersion: string
  source: string
  mode: 'preset_mock' | 'qwen_replay' | 'qwen_real'
  status: string
  statusLabel: string
  importedAt: string
  backendRunAt: string
  isExample: boolean
}

export interface Metric {
  id: string
  name: string
  level: number
  base: string
  current: string
  delta: string
  yoy: string
  impact: string
  relation: string
  residual: string
  status: string
  source: string
  expandable?: boolean
  parent?: string
  rawAmounts?: { base: string | null; current: string | null; change: string | null }
}

export interface Evidence {
  id: string
  fileName: string
  quote: string
  summary: string
  printPage: string
  pdfPage: string
  metrics: string[]
  basis: string
  verification: string
  supportLimit: string
}

export interface Explanation {
  id: string
  statement: string
  kind: 'accounting_fact' | 'disclosure_explanation' | 'hypothesis'
  metrics: string[]
  citations: string[]
  amounts: string[]
  supportLimit: string
  comparisonBasis: string
  accountingLinks: string
  checkStatus: string
}

export interface ActionStep {
  round: number
  action: 'facts_list' | 'fact_get' | 'list' | 'search' | 'get' | 'explain' | 'stop' | 'error'
  label: string
  summary: string
  params: string
  result: string
  links: string[]
  error?: string
}

export interface CaseRecord {
  modules?: { snapshotId: string; sections: OfflineSection[] }
  id: string
  run: RunContext
  question: string
  pendingCount: number
  metrics: Metric[]
  cashMetrics: Metric[]
  evidence: Evidence[]
  explanations: Explanation[]
  steps: ActionStep[]
  agentSummary?: {
    simulation: boolean
    llm_called: boolean
    real_request_attempts: number
    rounds: number
    tool_calls: number
    errors: string[]
    stop_reason: string
  }
  notices?: string[]
}

export interface ImportedBundle {
  record: CaseRecord
  files: File[]
  notices: string[]
}
