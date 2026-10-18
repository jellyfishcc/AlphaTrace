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
const {IntroPage} = load('IntroPage')
const {ResearchMaterialsDialog} = load('ResearchMaterialsDialog')
const {preparedSourceFiles, verifyPreparedCase} = load('workflow')
const {openingCase, workflow, adjacent} = load('workflow')
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
  assert.match(html,/查看 Agent 调查过程/)
  assert.doesNotMatch(html,/增长35\.0832|结构化研报纠错|validation_failed|incomplete_response/)
})
test('real Agent presents actual search/get/error and keeps technical failure intact',{skip:!real},()=>{
  const before=structuredClone(real), html=render(AgentInvestigation,real)
  assert.equal(agentOutcome(real),'自主调查未完成')
  assert.match(html,/检索相关年报证据/); assert.match(html,/读取已定位的证据原文/)
  assert.match(html,/响应不完整，未形成有效动作/)
  assert.match(html,/validation_failed/); assert.match(html,/incomplete_response/)
  assert.doesNotMatch(outsideDetails(html),/validation_failed|incomplete_response|响应不完整，未形成有效动作|第 3 轮/)
  assert.equal((outsideDetails(html).match(/class="step-card actual-tool"/g) ?? []).length,2)
  assert.match(outsideDetails(html),/规划能力 \/ 尚未完成/)
  assert.match(outsideDetails(html),/完整经营解释尚未通过校验/)
  for (const step of real.steps) {
    assert.ok(html.includes(step.result))
    for(const id of step.links) assert.ok(html.includes(id))
  }
  assert.doesNotMatch(html,/调查成功|已完成归因|等待人工审核最终解释/)
  assert.deepEqual(real,before)
})

const intro = records => renderToStaticMarkup(React.createElement(IntroPage,{records,notice:'',onChoose(){},onArchive(){}}))
test('opening page excludes mock or wrong-period records without substituting amounts',()=>{
  const mock={...exampleCases[0],run:{...exampleCases[0].run,company:'格力电器',basePeriod:'2024',currentPeriod:'2025'}}
  assert.equal(openingCase([mock]),undefined)
  assert.match(intro([mock]),/真实案例数据尚不可用/)
  assert.match(intro([mock]),/选择研究资料/)
  assert.doesNotMatch(intro([mock]),/10\.84%|57\.93%|0\.00%/)
  const wrong={...mock,run:{...mock.run,isExample:false,mode:'qwen_real',currentPeriod:'2023'}}
  assert.equal(openingCase([wrong]),undefined)
})
test('opening remains separate from the three main pages',()=>{
  assert.deepEqual(workflow.map(s=>s.id),['overview','investigation','review'])
  assert.equal(adjacent('intro',1),undefined)
  assert.equal(adjacent('overview',1),'investigation')
  assert.equal(adjacent('investigation',1),'review')
  assert.equal(adjacent('review',-1),'investigation')
})
test('opening entry requests selection rather than directly opening analysis',()=>{
  let chosen=0
  const elements = node => Array.isArray(node) ? node.flatMap(elements) : node && typeof node==='object' ? [node,...elements(node.props?.children)] : []
  const tree=IntroPage({records:exampleCases,notice:'',onChoose:()=>chosen++,onArchive(){}})
  const entry=elements(tree).find(e=>e.type==='button' && e.props.children==='选择研究资料 →')
  entry.props.onClick()
  assert.equal(chosen,1)
})
test('real opening reads exact exported percentages and never manufactures missing values',{skip:!real},()=>{
  assert.equal(openingCase([...exampleCases,real]),real)
  const html=intro([...exampleCases,real])
  for(const id of ['net_profit','operating_cashflow']) {
    const m=[...real.metrics,...real.cashMetrics].find(m=>m.id===id)
    assert.ok(html.includes(m.yoy)); assert.ok(html.includes(m.delta))
  }
  assert.match(html,/TraceLab/); assert.doesNotMatch(html,/AlphaTrace|validation_failed|incomplete_response/)
  const missing={...real,metrics:[],cashMetrics:[]}
  assert.match(intro([missing]),/未提供/)
  assert.doesNotMatch(intro([missing]),/10\.84%|57\.93%|0\.00%/)
})
test('Agent does not fabricate an executed action from absent, rejected or malformed calls',()=>{
  const original=exampleCases[0]
  const record={...original,steps:[{round:1,action:'search',params:'not JSON',summary:'原始摘要',result:'未提供',links:['missing-id']},{round:2,action:'get',params:'{}',summary:'被阻断',result:'被阻断',links:[],error:'unauthorized'}]}
  const html=render(AgentInvestigation,record),visible=outsideDetails(html)
  assert.match(visible,/实际检索内容.*未提供/)
  assert.match(visible,/missing-id · 未提供关联记录/)
  assert.doesNotMatch(visible,/第 2 轮/)
  assert.match(html,/unauthorized/)
  assert.equal((visible.match(/class="step-card actual-tool"/g) ?? []).length,1)
})
test('real report has no fabricated explanation or internal approval cards',{skip:!real},()=>{
  const html=render(AnalysisReport,real), visible=outsideDetails(html)
  assert.match(visible,/尚未形成经核验的最终经营解释/)
  assert.match(visible,/61.*不等于.*61/)
  assert.doesNotMatch(visible,/等待人工复核|人工业务复核|文件已读取|validation_failed|EXP-02|加强回款管理/)
  assert.match(visible,/-1256986374\.01/)
  assert.match(html,/F_net_profit/)
})

const materials = (record,extra={}) => renderToStaticMarkup(React.createElement(ResearchMaterialsDialog,{record,loading:false,error:'',onClose(){},onLoad(){},...extra}))
test('material dialog blocks missing and unselected cases and preserves close controls',()=>{
  const html=materials(undefined)
  assert.match(html,/真实案例资料暂不可用/)
  assert.match(html,/<button[^>]*disabled=""[^>]*>载入已核验案例/)
  assert.match(html,/关闭资料选择/); assert.match(html,/返回介绍页/)
  assert.doesNotMatch(html,/type="file"/)
})
test('material source names come only from the selected public evidence',{skip:!real},()=>{
  const before=structuredClone(real),html=materials(real)
  const names=[...new Set(real.evidence.map(e=>e.fileName))].sort()
  assert.deepEqual(preparedSourceFiles(real),names)
  for(const name of names) assert.ok(html.includes(name))
  assert.doesNotMatch(html,/格力2024 年年度报告.pdf|格力2024年年度报告.pdf/)
  assert.match(html,/2024 年报独立文件未在展示包中关联/)
  assert.match(html,/已有两期金额、会计桥接与来源/)
  assert.match(html,/<button[^>]*disabled=""[^>]*>载入已核验案例/)
  assert.deepEqual(real,before)
})
test('fresh loading rejects changed case, snapshot or file association',{skip:!real},()=>{
  assert.equal(verifyPreparedCase(real,real),real)
  for(const change of [r=>r.id='other',r=>r.run.id='other',r=>r.run.materialVersion='other',r=>r.run.isExample=true,r=>r.run.currentPeriod='2023',r=>r.evidence[0].fileName='other.pdf']) {
    const changed=structuredClone(real);change(changed)
    assert.throws(()=>verifyPreparedCase(real,changed))
  }
})
test('dialog shows only actual reading or validation error states',()=>{
  assert.match(materials(undefined,{error:'展示包读取或校验失败'}),/role="alert"[^>]*>展示包读取或校验失败/)
  assert.match(materials(undefined,{loading:true}),/正在读取展示包…/)
  assert.doesNotMatch(materials(undefined),/解析完成|计算完成|调查成功/)
})
