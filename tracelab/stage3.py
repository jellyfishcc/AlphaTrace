"""One bounded Responses API call, or an explicitly uncalled request package."""
import argparse
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib import request, error

from .stage3_input import prepare, read, sha
from .bailian import configuration, chat_body, as_response
from .analysis_contract import check_contract

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://api.openai.com/v1/responses'
PROMPT_VERSION = 'evidence_v3'


def obj(fields):
    return dict(type='object', properties=fields, required=list(fields), additionalProperties=False)


def arr(item):
    return dict(type='array', items=item)


STR = {'type':'string'}
SCHEMA = obj({'claims':arr(obj({
    'kind':{'type':'string','enum':['accounting_fact','disclosure_explanation','hypothesis']},
    'statement':STR, 'metric_ids':arr(STR),
    'citations':arr(obj({'evidence_id':STR,'quote':STR})),
    'amounts':arr(obj({'fact_id':STR,'field':{'type':'string','enum':['base','current','change']},
                       'unit':{'type':'string','enum':['元','亿元']},'value':STR})),
    'support_limit':STR})), 'questions':arr(STR)})

# Versioned extension: legacy saved responses still use SCHEMA unchanged.
SCHEMA_V2 = obj({'claims':arr(obj({**SCHEMA['properties']['claims']['items']['properties'],
    'accounting_links':arr(obj({'target':STR,'component':STR,
        'effect':{'type':'string','enum':['increase','decrease','unchanged']}})),
    'comparison_basis':{'type':'string','enum':['yoy','current_period','none']}})), 'questions':arr(STR)})


def schema_errors(value, schema, path='response'):
    kind=schema['type']
    if kind=='object':
        if not isinstance(value,dict): return [path+': expected object']
        if set(value)!=set(schema['properties']): return [path+': incorrect fields']
        return [e for k,s in schema['properties'].items() for e in schema_errors(value[k],s,path+'.'+k)]
    if kind=='array':
        if not isinstance(value,list): return [path+': expected array']
        return [e for i,v in enumerate(value) for e in schema_errors(v,schema['items'],f'{path}[{i}]')]
    return [] if isinstance(value,str) and ('enum' not in schema or value in schema['enum']) else [path+': invalid string']


def validate(response, payload):
    modern=payload.get('analysis_contract',{}).get('version')=='v2'
    errors=schema_errors(response,SCHEMA_V2 if modern else SCHEMA)
    review=[]
    if errors: return dict(status='failed',errors=errors,manual_review=review)
    facts={f['fact_id']:f for f in payload['facts']}
    evidence={e['evidence_id']:e for e in payload['evidence']}
    if not 1<=len(response['claims'])<=6: errors.append('需要一至六条结论')
    if not response['questions']: errors.append('缺少仍需确认的问题')
    for i,c in enumerate(response['claims'],1):
        label=f'结论{i}'
        if not c['statement'].strip() or not c['support_limit'].strip(): errors.append(label+'缺少解释或支持边界')
        if not c['metric_ids'] or any(k not in facts for k in c['metric_ids']): errors.append(label+'引用未知财务项目')
        if not c['citations']: errors.append(label+'缺少证据')
        cited=[]
        for citation in c['citations']:
            e=evidence.get(citation['evidence_id'])
            if e is None: errors.append(label+'引用不存在的证据'); continue
            cited.append(e)
            if not citation['quote'].strip() or citation['quote'] not in e['text']: errors.append(label+'引文与原文不一致')
        for k in c['metric_ids']:
            if k in facts and not any(k in e['related_facts'] for e in cited): errors.append(label+'财务项目缺少相关证据')
        for a in c['amounts']:
            expected=facts.get(a['fact_id'],{}).get('amounts',{}).get(a['field'],{}).get(a['unit'])
            try:
                n=Decimal(a['value'])
                equal=expected is not None and n.is_finite() and n==Decimal(expected)
            except InvalidOperation:
                equal=False
            if not equal: errors.append(label+'金额、期间或单位与输入不一致')
            if a['fact_id'] not in c['metric_ids']: errors.append(label+'金额未关联该条财务项目')
        if c['kind']=='hypothesis' and ('待验证' not in c['statement'] or re.search('确定|必然|唯一原因|证明了|就是原因',c['statement'])):
            errors.append(label+'可能将假设写为确定原因')
        if c['kind']=='accounting_fact' and re.search('由于|导致|造成|因为|主要原因',c['statement']):
            review.append(label+'会计事实含因果措辞，需人工复核')
        if c['kind']=='disclosure_explanation':
            from .source_contract import disclosure_errors
            errors.extend(label+e for e in disclosure_errors(c,cited,payload))
            if '年报' not in c['statement']: review.append(label+'应明确解释来自年报披露')
        review.append(label+'：人工检查引文是否实际支持结论、有无扩大因果范围及混淆本期与同比')
    free=[q for q in response['questions']]+[c[k] for c in response['claims'] for k in ('statement','support_limit')]
    if any(re.search(r'\d|[零一二三四五六七八九十百千万亿两]+(?:元|亿元|%|％|百分之)',t) for t in free):
        errors.append('自由文本含未结构化数字，金额必须放入amounts供精确核验')
    if modern:
        extra,manual=check_contract(response,payload)
        errors.extend(extra)
        review.extend(manual)
    return dict(status='failed' if errors else 'needs_human_review', errors=errors, manual_review=review,
                boundary='自动检查仅验证结构、数值、引用与部分措辞，不能证明经营因果或代替金融组验收')


def redact(value, secret=''):
    if isinstance(value,dict): return {k:redact(v,secret) for k,v in value.items()}
    if isinstance(value,list): return [redact(v,secret) for v in value]
    if isinstance(value,str):
        if secret: value=value.replace(secret,'[REDACTED]')
        return re.sub(r'\bsk-[A-Za-z0-9_-]+','[REDACTED]',value)
    return value


def write(path, data, secret=''):
    path.write_text(json.dumps(redact(data,secret),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def call_api(body,key,endpoint=ENDPOINT,timeout=55,diagnostics=None):
    diagnostics=diagnostics if diagnostics is not None else {}
    diagnostics.update(phase='connect_or_wait_headers',http_status=None,request_id=None)
    req=request.Request(endpoint,data=json.dumps(body,ensure_ascii=False).encode(),
                        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with request.build_opener(NoRedirect).open(req,timeout=timeout) as result:
            status=getattr(result,'status',None)
            diagnostics.update(phase='read_body',http_status=status if isinstance(status,int) else None,
                               request_id=result.headers.get('x-request-id'))
            content=result.read()
            diagnostics['phase']='decode_json'
            parsed=json.loads(content)
            diagnostics['phase']='complete'
            return parsed,diagnostics['request_id']
    except error.HTTPError as exc:
        diagnostics.update(phase='http_error',http_status=exc.code,
                           request_id=exc.headers.get('x-request-id') if exc.headers else None)
        raise


def visible_response(raw):
    # Whitelist final assistant messages. Never serialize reasoning items.
    messages=[]
    for item in raw.get('output',[]):
        if item.get('type')=='message' and item.get('role')=='assistant':
            for c in item.get('content',[]):
                if c.get('type')=='output_text': messages.append({'type':'output_text','text':c.get('text','')})
                elif c.get('type')=='refusal': messages.append({'type':'refusal','text':c.get('refusal','')})
    return dict(id=raw.get('id'),status=raw.get('status'),model=raw.get('model'),
                usage=raw.get('usage'),messages=messages,
                finish_reason=raw.get('finish_reason'),
                incomplete_reason=(raw.get('incomplete_details') or {}).get('reason'),
                incomplete=raw.get('incomplete_details') is not None)


def deliver(out, source, manifest):
    bundle=out/'delivery'
    bundle.mkdir()
    for name in ('tracelab','templates','prompts','docs','scripts','tests'):
        shutil.copytree(ROOT/name,bundle/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('README.md','requirements-stage2.txt'):
        shutil.copy2(ROOT/name,bundle/name)
    shutil.copytree(source,bundle/'stage2_results')
    shutil.copytree(out,bundle/'stage3_results',ignore=shutil.ignore_patterns('delivery'))
    (bundle/'交付说明.md').write_text(
        '# 今日交付\n\n本目录仅供本地团队交接，包含金融组原始附件；不要将整个目录发给模型。\n\n'
        'templates为填写模板；stage2_results/normalized为本次真实输入；inputs为原始快照。\n'
        'stage2_results包含计算、核对、原文和日志；stage3_results包含筛选后输入、请求和调用状态。\n'
        '运行说明见docs/stage3.md。当前状态：'+manifest['status']+'。\n'
        '数据整理、金融组口径确认及命令启动仍需人工，尚非全自动系统。\n',encoding='utf-8')
    index={str(p.relative_to(bundle)):sha(p) for p in bundle.rglob('*') if p.is_file()}
    write(bundle/'file_hashes.json',index)


def run(source, output, execute=False, provider='openai', model_override=None, timeout_seconds=55,
        analysis_mode='full', max_output_tokens=3000):
    if not 1<=timeout_seconds<=300:
        raise ValueError('timeout_seconds必须在1至300秒之间')
    if analysis_mode not in ('full','focused') or not 1<=max_output_tokens<=6000:
        raise ValueError('分析模式无效或输出上限不在1至6000之间')
    started=datetime.now(timezone.utc)
    run_id=started.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10]
    out=Path(output)/run_id
    out.mkdir(parents=True)
    key=os.environ.get('OPENAI_API_KEY','').strip()
    model=os.environ.get('TRACELAB_MODEL',os.environ.get('OPENAI_MODEL','')).strip()
    endpoint=ENDPOINT
    config=None
    if provider=='bailian':
        config=configuration(model_override) if model_override else configuration()
        key,model,endpoint=config.key,config.model,config.endpoint
    elif provider!='openai':
        raise ValueError('未知模型服务')
    elif model_override:
        model=model_override
    events=[]
    manifest=dict(run_id=run_id,started_at=started.isoformat(),
                  local_date=started.astimezone(timezone(timedelta(hours=8))).date().isoformat(),
                  status='preparing',llm_called=False,model=model or None, endpoint=endpoint,provider=provider,
                  prompt_version=PROMPT_VERSION,analysis_mode=analysis_mode,latency_seconds=None,usage=None,
                  max_requests=1,retries=0,timeout_seconds=timeout_seconds,http_status=None,
                  code_hashes={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')})
    def event(name,**data):
        events.append(dict(time=datetime.now(timezone.utc).isoformat(),event=name,**data))
    try:
        payload,audit=prepare(source) if analysis_mode=='full' else prepare(source,mode=analysis_mode)
        schema=SCHEMA_V2 if payload.get('analysis_contract',{}).get('version')=='v2' else SCHEMA
        write(out/'input.json',payload)
        write(out/'input_audit.json',audit)
        prompt=(ROOT/'prompts'/f'{PROMPT_VERSION}.txt').read_text(encoding='utf-8')
        (out/'prompt.txt').write_text(prompt,encoding='utf-8')
        body=dict(model=model or '<待配置模型>',store=False,max_output_tokens=max_output_tokens,
                  instructions=prompt,input=json.dumps(payload,ensure_ascii=False),
                  text={'format':{'type':'json_schema','name':'tracelab_evidence','strict':True,'schema':schema}})
        if provider=='bailian':
            body=chat_body(model,prompt,json.dumps(payload,ensure_ascii=False,separators=(',',':')),max_output_tokens,schema)
            prompt_bytes=sum(len(m['content'].encode('utf-8')) for m in body['messages'])
            if prompt_bytes>32000:
                raise ValueError('百炼有限分析输入超过32000字节，需缩小范围后复核')
            manifest.update(input_utf8_bytes=prompt_bytes,input_byte_limit=32000,
                            input_token_estimate_note='字节限制不是精确Token计数；实际用量由服务返回')
        write(out/'request.json',body,key)
        manifest.update(input_sha256=sha(out/'input.json'),prompt_sha256=sha(out/'prompt.txt'),
                        request_sha256=sha(out/'request.json'),source_run=audit['source_run'],parameters={'store':False,'max_output_tokens':max_output_tokens})
        missing=[name for name,value in [('OPENAI_API_KEY',key),('TRACELAB_MODEL',model)] if not value]
        if provider=='bailian':
            missing=[] if key else ['DASHSCOPE_API_KEY']
            manifest['parameters']={'max_tokens':max_output_tokens,'stream':False,'enable_thinking':False,'response_format':'json_object'}
        event('input_verified',fact_count=len(payload['facts']),evidence_count=len(payload['evidence']))
        if not execute or missing:
            manifest.update(status='not_called',missing_configuration=missing,
                            reason='未调用：缺少配置' if missing else '未调用：本次仅准备请求')
            write(out/'response_status.json',{'status':'not_called','reason':manifest['reason'],'missing':missing})
            write(out/'checks.json',{'status':'not_run','reason':'没有真实模型输出'})
            event('not_called',missing=missing)
        else:
            manifest['llm_called']=True
            event('request_started')
            before=time.monotonic()
            transport={}
            try:
                if provider=='bailian':
                    raw,request_id=call_api(body,key,endpoint=endpoint,timeout=timeout_seconds,diagnostics=transport)
                    manifest['http_status']=200
                    raw=as_response(raw)
                else:
                    raw,request_id=call_api(body,key,timeout=timeout_seconds,diagnostics=transport)
                    manifest['http_status']=200
                safe=redact(visible_response(raw),key)
                del raw
                manifest.update(usage=safe['usage'],returned_model=safe['model'],request_id=redact(request_id,key),
                                finish_reason=safe['finish_reason'],incomplete_reason=safe['incomplete_reason'])
                write(out/'response.json',safe,key)
                texts=[m['text'] for m in safe['messages'] if m['type']=='output_text']
                if safe['status']!='completed' or any(m['type']=='refusal' for m in safe['messages']) or not texts:
                    manifest['status']='response_failed'
                    write(out/'checks.json',{'status':'failed','errors':['响应未完成、拒绝或无可用文本'],
                                            'finish_reason':safe['finish_reason'],'incomplete_reason':safe['incomplete_reason']})
                else:
                    try:
                        parsed=json.loads(''.join(texts))
                    except json.JSONDecodeError:
                        manifest['status']='validation_failed'
                        write(out/'checks.json',{'status':'failed','errors':['模型返回内容不是JSON']})
                    else:
                        write(out/'analysis.json',parsed,key)
                        checked=validate(parsed,payload)
                        write(out/'checks.json',checked,key)
                        manifest['status']='validation_failed' if checked['status']=='failed' else 'completed_pending_human_review'
            except (error.HTTPError,error.URLError,TimeoutError,OSError,ValueError) as exc:
                manifest['status']='call_failed'
                manifest['http_status']=getattr(exc,'code',manifest['http_status'])
                # Never persist provider error bodies or exception text (may echo credentials).
                write(out/'error.json',{'type':type(exc).__name__,'http_status':getattr(exc,'code',None),
                                       'message':'调用失败；未记录服务端正文或请求头，以免回显凭证。'})
                write(out/'checks.json',{'status':'not_run','reason':'调用未取得可核验的模型输出'})
            finally:
                manifest['latency_seconds']=round(time.monotonic()-before,3)
                if transport:
                    manifest.update(transport_phase=transport.get('phase'),
                                    http_status=transport.get('http_status'),
                                    request_id=redact(transport.get('request_id'),key))
                write(out/'transport.json',transport,key)
            event('request_finished',status=manifest['status'])
    except (ValueError,KeyError,StopIteration,OSError) as exc:
        manifest.update(status='input_failed',error_type=type(exc).__name__)
        write(out/'error.json',{'type':type(exc).__name__,'message':'输入核验或读取失败，未发送请求。'})
        event('input_failed',error_type=type(exc).__name__)
    manifest['finished_at']=datetime.now(timezone.utc).isoformat()
    write(out/'manifest.json',manifest,key)
    (out/'events.jsonl').write_text(''.join(json.dumps(redact(e,key),ensure_ascii=False)+'\n' for e in events),encoding='utf-8')
    (out/'人工复核清单.md').write_text(
        '# 人工复核\n\n调用状态：'+manifest['status']+'。未调用时以下各项均未验收。\n\n'
        '- [ ] 核对利润层级、期间、单位、合并范围及少数股东损益符号。\n'
        '- [ ] 逐条确认引文真的支持解释，而非仅词语相关。\n'
        '- [ ] 确认本期保证金调节额未被当作现金流同比增量。\n'
        '- [ ] 区分年报直接披露、会计关系与待验证假设，检查确定性措辞。\n'
        '- [ ] 确认未从现金流增长直接推断盈利质量改善。\n'
        '- [ ] 检查证据缺口与反证，金融组签署可用结论及未解决问题。\n',encoding='utf-8')
    if manifest['status']!='input_failed': deliver(out,Path(source),manifest)
    return out,manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description='TraceLab单次证据分析；默认只准备，--execute尝试一次真实调用')
    parser.add_argument('--stage2-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('outputs/stage3'))
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--provider',choices=('openai','bailian'),default='openai')
    parser.add_argument('--model',default=None,help='显式指定模型；未指定时沿用环境配置')
    parser.add_argument('--timeout-seconds',type=int,default=55,help='套接字操作超时，1至300秒；不是总耗时上限')
    parser.add_argument('--analysis-mode',choices=('full','focused'),default='full')
    parser.add_argument('--max-output-tokens',type=int,default=3000,help='输出上限1至6000，不允许无上限')
    args=parser.parse_args(argv)
    out,manifest=run(args.stage2_run,args.output,args.execute,args.provider,args.model,args.timeout_seconds,
                     args.analysis_mode,args.max_output_tokens)
    print(json.dumps({'status':manifest['status'],'llm_called':manifest['llm_called'],'output':str(out.resolve())},ensure_ascii=False))
    return 0 if manifest['status'] in ('not_called','completed_pending_human_review') else 1


if __name__=='__main__':
    raise SystemExit(main())
