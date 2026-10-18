import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

// Render the real TSX components in memory, with the project's existing dependencies.
const require = createRequire(import.meta.url)
const root = fileURLToPath(new URL('../src/', import.meta.url))
const cache = new Map()
function load(name) {
  const filename = ['.tsx','.ts'].map(ext => path.join(root,name+ext)).find(fs.existsSync)
  if (cache.has(filename)) return cache.get(filename)
  const code = ts.transpileModule(fs.readFileSync(filename,'utf8'), { compilerOptions: { module:ts.ModuleKind.CommonJS, jsx:ts.JsxEmit.ReactJSX, target:ts.ScriptTarget.ES2022 } }).outputText
  const module = {exports:{}}
  const localRequire = id => id.startsWith('.') ? load(path.relative(root,path.resolve(path.dirname(filename),id))) : require(id)
  new Function('require','module','exports',code)(localRequire,module,module.exports)
  cache.set(filename,module.exports)
  return module.exports
}
const {ResearchTask} = load('ResearchTask')
const {AgentInvestigation} = load('AgentInvestigation')
const {AnalysisReport} = load('AnalysisReport')
const {resolveLink,agentOutcome,coreMetrics} = load('workflow')
const {exampleCases} = load('data/example')
const render = (Component,record) => renderToStaticMarkup(React.createElement(Component,{record,onInvestigate(){},onMetric(){},onEvidence(){},onView(){},onLink(){},onReport(){},onExplanation(){},onInvestigation(){}}))
const outsideDetails = html => {
  let depth=0, visible=''
  for (const part of html.split(/(<\/?details\b[^>]*>)/g)) {
    if (part.startsWith('<details')) depth++
    else if (part.startsWith('</details')) depth--
    else if (depth===0) visible+=part
  }
  return visible
}
const realPath = new URL('../public/data/gree-display.json',import.meta.url)
const real = fs.existsSync(realPath) ? JSON.parse(fs.readFileSync(realPath,'utf8')).record : undefined

test('empty case does not synthesize metrics, explanations or investigation',()=>{
  const empty=exampleCases[1]
  assert.deepEqual(coreMetrics(empty),[])
  assert.match(render(ResearchTask,empty),/未提供可展示的财务金额/)
  assert.match(render(AgentInvestigation,empty),/未提供调查轨迹/)
  assert.match(render(AnalysisReport,empty),/尚未形成经核验的最终经营解释/)
})
test('links resolve only within the selected case',()=>{
  assert.equal(resolveLink(exampleCases[0],'E12_A'),'evidence')
  assert.equal(resolveLink(exampleCases[0],'net_profit'),'metric')
  assert.equal(resolveLink(exampleCases[0],'EXP-02'),'explanation')
  assert.equal(resolveLink(exampleCases[1],'E12_A'),'missing')
  assert.equal(resolveLink(exampleCases[0],'F_net_profit'),'missing')
})
test('mock results retain a prominent simulation label on all three pages',()=>{
  for(const component of [ResearchTask,AgentInvestigation,AnalysisReport]) {
    const html=render(component,exampleCases[0])
    assert.match(html,/概念演示 \/ 模拟运行/)
    assert.doesNotMatch(html,/28862746016\.16|F_net_profit/)
  }
})
test('real homepage leads with financial facts, not correction or internal errors',{skip:!real},()=>{
  const html=outsideDetails(render(ResearchTask,real))
  assert.match(html,/业绩分析工作台/)
  for(const metric of coreMetrics(real)) for(const field of ['base','current','delta']) assert.ok(html.includes(metric[field]))
  assert.match(html,/查看该财务信号的历史调查过程/)
  assert.doesNotMatch(html,/增长35\.0832|结构化研报纠错|validation_failed|incomplete_response/)
})
test('real Agent presents actual search/get/error and keeps technical failure intact',{skip:!real},()=>{
  const before=structuredClone(real), html=render(AgentInvestigation,real)
  assert.equal(agentOutcome(real),'自主调查未完成')
  assert.match(html,/检索相关年报证据/); assert.match(html,/读取已定位的证据原文/)
  assert.match(html,/响应不完整，未形成有效动作/)
  assert.match(html,/validation_failed/); assert.match(html,/incomplete_response/)
  assert.doesNotMatch(outsideDetails(html),/validation_failed|incomplete_response/)
  assert.doesNotMatch(html,/调查成功|已完成归因|等待人工审核最终解释/)
  assert.deepEqual(real,before)
})
test('real report has no fabricated explanation or internal approval cards',{skip:!real},()=>{
  const html=render(AnalysisReport,real), visible=outsideDetails(html)
  assert.match(visible,/尚未形成经核验的最终经营解释/)
  assert.match(visible,/61.*不等于.*61/)
  assert.doesNotMatch(visible,/等待人工复核|人工业务复核|文件已读取|validation_failed|EXP-02|加强回款管理/)
  assert.match(visible,/-1256986374\.01/)
  assert.match(html,/F_net_profit/)
})
