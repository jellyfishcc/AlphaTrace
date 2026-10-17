import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'

const source=fs.readFileSync(new URL('../src/data/adapter.ts',import.meta.url),'utf8')
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}})
const {adaptDisplayBundle,adaptLocalFiles}=await import('data:text/javascript;base64,'+Buffer.from(outputText).toString('base64'))
function fixture() {
  return {schema:'alphatrace-display-v1',provenance:{snapshotId:'snapshot',agentRunId:'run',financialSha256:'a'.repeat(64),cashSha256:'b'.repeat(64),eventsSha256:'c'.repeat(64),resultSha256:'d'.repeat(64)},
    record:{id:'synthetic',question:'合成测试',pendingCount:1,
      run:{id:'run',label:'合成测试',company:'合成公司',ticker:'未提供',basePeriod:'2024',currentPeriod:'2025',scope:'合并',materialVersion:'snapshot',source:'合成测试',mode:'qwen_real',status:'validation_failed',statusLabel:'错误标题不能覆盖失败状态',importedAt:'未提供',backendRunAt:'未提供',isExample:false},
      metrics:[{id:'net_profit',name:'净利润',level:0,base:'9007199254740993.10 元',current:'9007199254740994.20 元',delta:'1.10 元',yoy:'未提供',impact:'未提供',relation:'未提供',residual:'未提供',status:'合成测试',source:'F_test',rawAmounts:{base:'9007199254740993.10',current:'9007199254740994.20',change:'1.10'}}],
      cashMetrics:[],evidence:[],explanations:[],steps:[{round:1,action:'error',label:'失败',summary:'incomplete_response',params:'{}',result:'未执行',links:[],error:'incomplete_response'}],
      agentSummary:{simulation:false,llm_called:true,real_request_attempts:1,rounds:1,tool_calls:0,errors:['incomplete_response'],stop_reason:'invalid_decision_or_tool_error'},notices:[]}}
}
test('decimal strings never round via Number',()=>{
  const f=fixture(),r=adaptDisplayBundle(f)
  assert.deepEqual(r.metrics,f.record.metrics)
  assert.equal(r.run.statusLabel,'真实调查失败 · incomplete_response')
  assert.equal(f.record.run.statusLabel,'错误标题不能覆盖失败状态')
})
test('missing field fails rather than using example values',()=>{
  const f=fixture(); delete f.record.metrics[0].base
  assert.throws(()=>adaptDisplayBundle(f))
})
test('wrong amount representation is rejected',()=>{
  const f=fixture(); f.record.metrics[0].base='1.00 元'
  assert.throws(()=>adaptDisplayBundle(f))
})
test('mock and success cannot enter real failed schema',()=>{
  for(const mutate of [f=>f.record.run.isExample=true,f=>f.record.run.status='success',f=>f.record.agentSummary.simulation=true]) {
    const f=fixture(); mutate(f); assert.throws(()=>adaptDisplayBundle(f))
  }
})
test('sensitive paths and unknown raw fields rejected',()=>{
  for(const mutate of [f=>f.record.question='D:\\private\\file',f=>f.record.raw_response='synthetic hidden log']) {
    const f=fixture(); mutate(f); assert.throws(()=>adaptDisplayBundle(f))
  }
})
test('unlinked citation and invented explanation rejected',()=>{
  const f=fixture(); f.record.steps[0].links=['E_fake']; assert.throws(()=>adaptDisplayBundle(f))
  const g=fixture(); g.record.explanations=[{statement:'fake success'}]; assert.throws(()=>adaptDisplayBundle(g))
})
test('raw file import rejected before reading bytes',async()=>{
  let read=false
  await assert.rejects(adaptLocalFiles([{name:'input.json',text:async()=>{read=true;return '{}'}}]))
  assert.equal(read,false)
})
test('valid local import has no raw log download',async()=>{
  const r=await adaptLocalFiles([{name:'test-display.json',size:100,text:async()=>JSON.stringify(fixture())}])
  assert.equal(r.record.run.status,'validation_failed'); assert.deepEqual(r.files,[])
})
const realPath=new URL('../public/data/gree-display.json',import.meta.url)
test('local real export maps every amount unchanged',{skip:!fs.existsSync(realPath)},()=>{
  const f=JSON.parse(fs.readFileSync(realPath,'utf8')),r=adaptDisplayBundle(f)
  assert.deepEqual(r.metrics,f.record.metrics); assert.deepEqual(r.cashMetrics,f.record.cashMetrics)
  assert.deepEqual(r.evidence,f.record.evidence); assert.deepEqual(r.steps,f.record.steps)
  assert.equal(r.explanations.length,0)
})
