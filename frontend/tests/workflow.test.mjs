import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'

const source = fs.readFileSync(new URL('../src/workflow.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { workflow, adjacent, claimSummary } = await import('data:text/javascript;base64,' + Buffer.from(outputText).toString('base64'))

test('three business pages form a reversible route; evidence remains auxiliary', () => {
  assert.deepEqual(workflow.map(s => s.id), ['overview','investigation','review'])
  assert.equal(adjacent('overview', -1), undefined)
  assert.equal(adjacent('review', 1), undefined)
  assert.equal(adjacent('evidence', 1), undefined)
  let view = 'overview'
  for (const step of workflow.slice(1)) { view = adjacent(view, 1); assert.equal(view, step.id) }
  for (const step of workflow.slice(0,-1).reverse()) { view = adjacent(view, -1); assert.equal(view, step.id) }
})

test('missing claim never substitutes the Gree example', () => {
  const claim = claimSummary({ run: { isExample: true } })
  assert.equal(claim.statement, '未提供')
  assert.equal(claim.correction, '未提供')
  assert.deepEqual(claim.evidenceIds, [])
})

test('summary preserves unknown/unverifiable states and exact strings without deriving a verdict', () => {
  for (const status of ['发现错误','一致','无法核实']) {
    const record = { modules: { sections: [{ kind:'report', rows:[
      { cells:['核查状态',status], evidenceIds:['synthetic'] },
      { cells:['原始陈述','合成陈述'], evidenceIds:[] },
      { cells:['纠错建议','9007199254740993.123456 元'], evidenceIds:[] },
    ] }] } }
    const before = structuredClone(record)
    const summary = claimSummary(record)
    assert.equal(summary.status,status)
    assert.equal(summary.correction,'9007199254740993.123456 元')
    assert.deepEqual(record,before)
  }
})

const realPath = new URL('../public/data/gree-display.json', import.meta.url)
test('real task summary reads the existing correction and Agent remains failed', { skip: !fs.existsSync(realPath) }, () => {
  const {record} = JSON.parse(fs.readFileSync(realPath,'utf8'))
  const summary = claimSummary(record)
  assert.equal(summary.status,'发现错误')
  assert.equal(summary.error,'方向错误')
  assert.match(summary.statement,/增长35\.0832/)
  assert.match(summary.correction,/下降 35\.0832/)
  assert.deepEqual(summary.evidenceIds,['F_net_profit'])
  assert.equal(record.run.status,'validation_failed')
  assert.ok(record.agentSummary.errors.includes('incomplete_response'))
})
