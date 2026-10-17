"""No-data connectivity probe. Default is local preparation only."""
import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from .bailian import configuration, as_response
from .stage3 import call_api, visible_response, redact, write

PROMPT='请只回复“连接成功”，不要输出其他内容。'


def run(output, execute=False, model=None):
    cfg=configuration(model)
    endpoint=cfg.endpoint
    now=lambda:datetime.now(timezone.utc).isoformat()
    folder=Path(output)/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    body=dict(model=cfg.model,messages=[{'role':'user','content':PROMPT}],
              max_tokens=16,stream=False,enable_thinking=False)
    state=dict(started_at=now(),status='not_called',llm_called=False,model=cfg.model,endpoint=endpoint,
               configuration_sources=cfg.sources,key_present=bool(cfg.key),max_requests=1,retries=0,
               timeout_seconds=30,latency_seconds=None,usage=None,http_status=None,
               budget_cny=20,budget_enforced=False,
               budget_note='仅限制本进程一次请求和16输出Token，无法保证账户累计费用上限；实际以云端账单为准。')
    write(folder/'request.json',body,cfg.key)
    if execute and cfg.key:
        state.update(llm_called=True,request_started_at=now())
        start=time.monotonic()
        try:
            raw,request_id=call_api(body,cfg.key,endpoint=endpoint,timeout=30)
            state['http_status']=200
            safe=redact(visible_response(as_response(raw)),cfg.key)
            state.update(usage=safe['usage'],request_id=redact(request_id,cfg.key),returned_model=safe['model'])
            write(folder/'response.json',safe,cfg.key)
            text=''.join(c['text'] for c in safe['messages'] if c['type']=='output_text').strip()
            state['status']='connected' if safe['status']=='completed' and text=='连接成功' else 'response_needs_review'
        except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,KeyError) as exc:
            state.update(status='failed',http_status=getattr(exc,'code',state['http_status']))
            write(folder/'error.json',{'type':type(exc).__name__,'http_status':state['http_status'],
                                       'message':'请求失败，未保存可能包含凭证的服务端正文或请求头。'})
        finally:
            state['latency_seconds']=round(time.monotonic()-start,3)
    else:
        state['reason']='等待本次真实调用许可' if cfg.key else '缺少DASHSCOPE_API_KEY'
    state['finished_at']=now()
    write(folder/'manifest.json',state,cfg.key)
    (folder/'events.jsonl').write_text(json.dumps(redact(state,cfg.key),ensure_ascii=False)+'\n',encoding='utf-8')
    return folder,state


def main():
    p=argparse.ArgumentParser(description='百炼最小连通性检查，默认仅本地准备；许可后才使用--execute')
    p.add_argument('--execute',action='store_true')
    p.add_argument('--model',default=None)
    p.add_argument('--output',type=Path,default=Path('outputs/connectivity'))
    args=p.parse_args()
    try:
        folder,state=run(args.output,args.execute,args.model)
    except (ValueError,OSError):
        print('本地配置或目录不可用；检查环境变量及写入权限。未显示敏感值。')
        return 1
    print(json.dumps({'status':state['status'],'model':state['model'],'key_present':state['key_present'],
                      'output':str(folder.resolve())},ensure_ascii=False))
    return 0 if state['status'] in ('not_called','connected') else 1


if __name__=='__main__':
    raise SystemExit(main())
