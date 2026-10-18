import type { CaseRecord, ImportedBundle } from '../types'

const unsafe = /[a-z]:[\\/]|\\\\|\/(?:Users|home|tmp|etc|mnt)\/|sk-[a-z0-9_-]{8,}|Bearer\s|api[_-]?key|authorization|微信|Wechat|金融组|\.docx|\.xlsx/i
const identifier = /^[A-Za-z0-9_-]{1,100}$/
const money = /^-?\d+(?:\.\d+)? 元$|^未提供$/

function assert(condition: unknown): asserts condition {
  if (!condition) throw new Error('展示包字段不完整或不受支持；请使用 Python display_export 导出。')
}
function object(value: unknown): Record<string, unknown> {
  assert(value && typeof value === 'object' && !Array.isArray(value))
  return value as Record<string, unknown>
}
function strings(obj: Record<string, unknown>, keys: string[]) {
  keys.forEach((key) => assert(typeof obj[key] === 'string'))
}
function onlyKeys(obj: Record<string, unknown>, allowed: string[]) {
  assert(Object.keys(obj).every((key) => allowed.includes(key)))
}
function array(value: unknown): unknown[] { assert(Array.isArray(value)); return value }
function stringArray(value: unknown): string[] {
  const items = array(value); assert(items.every((x) => typeof x === 'string')); return items as string[]
}
function safe(value: unknown): void {
  if (typeof value === 'string') assert(!unsafe.test(value))
  else if (Array.isArray(value)) value.forEach(safe)
  else if (value && typeof value === 'object') Object.entries(value).forEach(([k,v]) => { safe(k); safe(v) })
}

// Validation only: no arithmetic, synthesized conclusions, or example fallback.
export function adaptDisplayBundle(value: unknown): CaseRecord {
  safe(value)
  const bundle = object(value)
  onlyKeys(bundle, ['schema','record','provenance'])
  assert(bundle.schema === 'alphatrace-display-v1')
  const record = object(bundle.record)
  onlyKeys(record, ['id','run','question','pendingCount','metrics','cashMetrics','evidence','explanations','steps','agentSummary','notices','modules'])
  strings(record, ['id','question'])
  assert(identifier.test(String(record.id)))
  const run = object(record.run)
  onlyKeys(run, ['id','label','company','ticker','basePeriod','currentPeriod','scope','materialVersion','source','mode','status','statusLabel','importedAt','backendRunAt','isExample'])
  strings(run, ['id','label','company','ticker','basePeriod','currentPeriod','scope','materialVersion','source','status','statusLabel','importedAt','backendRunAt'])
  assert(run.isExample === false && run.mode === 'qwen_real' && run.status === 'validation_failed')
  assert(Number.isInteger(record.pendingCount) && Number(record.pendingCount) >= 0)
  const ids = new Set<string>()
  for (const metric of [...array(record.metrics), ...array(record.cashMetrics)]) {
    const m = object(metric)
    onlyKeys(m, ['id','name','level','base','current','delta','yoy','impact','relation','residual','status','source','rawAmounts'])
    strings(m, ['id','name','base','current','delta','yoy','impact','relation','residual','status','source'])
    assert(identifier.test(String(m.id)) && !ids.has(String(m.id))); ids.add(String(m.id))
    assert(Number.isInteger(m.level) && ['base','current','delta'].every((key) => money.test(String(m[key]))))
    const raw = object(m.rawAmounts)
    onlyKeys(raw,['base','current','change'])
    for (const [key,display] of [['base','base'],['current','current'],['change','delta']]) {
      assert(raw[key] === null || typeof raw[key] === 'string')
      assert(m[display] === (raw[key] === null ? '未提供' : `${raw[key]} 元`))
    }
  }
  const evidenceIds = new Set<string>()
  for (const item of array(record.evidence)) {
    const e = object(item)
    onlyKeys(e, ['id','fileName','quote','summary','printPage','pdfPage','basis','verification','supportLimit','metrics'])
    strings(e, ['id','fileName','quote','summary','printPage','pdfPage','basis','verification','supportLimit'])
    assert(identifier.test(String(e.id)) && !evidenceIds.has(String(e.id))); evidenceIds.add(String(e.id))
    assert(/^[^/\\]+\.pdf$/.test(String(e.fileName)))
    assert(/^\d+$/.test(String(e.pdfPage)) && /^\d+$/.test(String(e.printPage)))
    stringArray(e.metrics)
  }
  assert(array(record.explanations).length === 0)
  for (const item of array(record.steps)) {
    const s = object(item)
    onlyKeys(s,['round','action','label','summary','params','result','links','error'])
    strings(s, ['action','label','summary','params','result'])
    assert(['facts_list','fact_get','list','search','get','error'].includes(String(s.action)))
    assert(Number.isInteger(s.round) && Number(s.round) > 0)
    stringArray(s.links).forEach((id) => assert(ids.has(id) || evidenceIds.has(id)))
    if (s.error !== undefined) assert(typeof s.error === 'string')
  }
  const summary = object(record.agentSummary)
  onlyKeys(summary,['simulation','llm_called','real_request_attempts','rounds','tool_calls','errors','stop_reason'])
  assert(summary.simulation === false && summary.llm_called === true)
  for (const key of ['rounds','tool_calls','real_request_attempts']) assert(Number.isInteger(summary[key]) && Number(summary[key]) >= 0)
  stringArray(summary.errors); strings(summary,['stop_reason']); stringArray(record.notices)
  const provenance = object(bundle.provenance)
  onlyKeys(provenance,['snapshotId','agentRunId','financialSha256','cashSha256','eventsSha256','resultSha256'])
  assert(provenance.snapshotId === run.materialVersion && provenance.agentRunId === run.id)
  for (const key of ['financialSha256','cashSha256','eventsSha256','resultSha256']) assert(/^[a-f0-9]{64}$/.test(String(provenance[key])))
  if (record.modules !== undefined) {
    const modules = object(record.modules)
    onlyKeys(modules, ['snapshotId','sections'])
    assert(modules.snapshotId === run.materialVersion)
    for (const value of array(modules.sections)) {
      const section = object(value)
      onlyKeys(section, ['kind','title','columns','rows','notices','runId','hashes'])
      strings(section,['kind','title','runId'])
      assert(['report','pdf','profit','cash','verification'].includes(String(section.kind)))
      assert(identifier.test(String(section.runId)))
      if (['profit','cash','verification'].includes(String(section.kind))) assert(section.runId === modules.snapshotId)
      const columns = stringArray(section.columns)
      assert(columns.length > 0)
      stringArray(section.notices)
      const hashes = object(section.hashes)
      assert(Object.keys(hashes).length > 0)
      Object.entries(hashes).forEach(([name,hash]) => {
        assert(/^[a-z_]+\.(json|csv)$/.test(name) && /^[a-f0-9]{64}$/.test(String(hash)))
      })
      for (const value of array(section.rows)) {
        const row = object(value)
        onlyKeys(row,['cells','evidenceIds'])
        assert(stringArray(row.cells).length === columns.length)
        stringArray(row.evidenceIds).forEach((id) => assert(evidenceIds.has(id)))
      }
    }
  }
  const output = structuredClone(record) as unknown as CaseRecord
  output.run.statusLabel = '真实调查失败 · ' + stringArray(summary.errors).join(', ')
  output.run.label = '格力真实调查 · 验证失败'
  return output
}

export async function loadDisplayBundle(): Promise<CaseRecord> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/gree-display.json`, { cache: 'no-store' })
  if (!response.ok) throw new Error('未找到真实展示包；仅显示明确标注的交互示例。')
  return adaptDisplayBundle(await response.json())
}

export async function adaptLocalFiles(files: File[]): Promise<ImportedBundle> {
  if (files.length !== 1 || !files[0].name.endsWith('-display.json')) {
    throw new Error('仅支持单个 *-display.json 脱敏展示包。请先运行 Python 导出，不要导入原始日志或附件。')
  }
  if (files[0].size > 2_000_000) throw new Error('展示包超过 2 MB 限制。')
  const record = adaptDisplayBundle(JSON.parse(await files[0].text()))
  return { record, files: [], notices: record.notices ?? [] }
}
