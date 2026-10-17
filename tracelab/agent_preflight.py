"""Offline-only preparation. Inspect key presence metadata, never key values."""
import argparse
import json
import os
import uuid
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from .stage3_input import read,sha
from .stage3 import write
from .bailian import setting,Config,chat_body
from .final_release import load_agent_payload
from .qwen_decider import QwenDecider,ExportScope,ReplayTransport,Budget,SCHEMA
from .agent import investigate

FACTS=('net_profit','operating_cashflow','cash_2','cash_6')
EVIDENCE=('F_net_profit','F_operating_cashflow','F_FINAL_cash_2','F_FINAL_cash_6','E07_28','E18')


def configuration_presence():
    # Iterate process variable NAMES only. Query registry size/type without reading lpData.
    process_present='DASHSCOPE_API_KEY' in list(os.environ)
    user_present=False
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        api=ctypes.WinDLL('advapi32',use_last_error=True)
        handle=wintypes.HKEY();size=wintypes.DWORD();kind=wintypes.DWORD()
        api.RegOpenKeyExW.argtypes=[wintypes.HKEY,wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(wintypes.HKEY)]
        api.RegQueryValueExW.argtypes=[wintypes.HKEY,wintypes.LPCWSTR,ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD)]
        api.RegCloseKey.argtypes=[wintypes.HKEY]
        if api.RegOpenKeyExW(wintypes.HKEY(-2147483647),'Environment',0,1,ctypes.byref(handle))==0:
            try:user_present=api.RegQueryValueExW(handle,'DASHSCOPE_API_KEY',None,ctypes.byref(kind),None,ctypes.byref(size))==0 and size.value>2
            finally:api.RegCloseKey(handle)
    base,origin=setting('DASHSCOPE_BASE_URL') # nonsecret URL only
    from urllib.parse import urlsplit
    try:
        endpoint=Config('',base,'qwen-plus',{}).endpoint
        valid=urlsplit(base).hostname=='ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com'
    except ValueError:endpoint=None;valid=False
    return dict(base_url=base,base_source=origin,endpoint=endpoint,beijing_workspace_match=valid,
        key_name_present_in_process=process_present,key_nonempty_metadata_in_user_registry=user_present,
        key_value_read=False,ready=valid and (process_present or user_present),
        note='仅检查变量名/注册表值大小；不验证密钥内容、权限、余额或接口连通性')


def prepare(source,output,config_check=configuration_presence):
    source,output=Path(source),Path(output)
    with patch('socket.socket',side_effect=RuntimeError('offline_network_blocked')), \
         patch('tracelab.bailian.configuration',side_effect=RuntimeError('key_read_blocked')), \
         patch('tracelab.stage3.call_api',side_effect=RuntimeError('real_api_blocked')):
        payload,audit=load_agent_payload(source)
        config=config_check()
        scope=ExportScope(frozenset(FACTS),frozenset(EVIDENCE),'prepared_only_requires_separate_user_authorization')
        budget=Budget(max_requests=5,max_output_tokens=1200,timeout_seconds=90,total_tokens=60000)
        evidence={e['evidence_id']:e for e in payload['evidence']}
        analysis={'claims':[
            dict(kind='accounting_fact',statement='净利润下降',metric_ids=['net_profit'],
                 citations=[dict(evidence_id='F_net_profit',quote=evidence['F_net_profit']['text'])],amounts=[],
                 support_limit='仅确认会计变化，尚未解释经营原因',accounting_links=[],comparison_basis='yoy'),
            dict(kind='hypothesis',statement='待验证：经营收付款变化是否足以解释现金流走势',metric_ids=['operating_cashflow'],
                 citations=[dict(evidence_id='E18',quote=evidence['E18']['text'][:200])],amounts=[],
                 support_limit='需要结合分项和披露复核，不推断盈利质量改善',accounting_links=[],comparison_basis='yoy')],
                 'questions':['是否存在尚未获得披露支持的经营影响？']}
        actions=[dict(action='search',arguments={'metric_id':'net_profit'}),dict(action='get',arguments={'evidence_id':'E18'}),
                 dict(action='explain',arguments={'analysis':analysis})]
        responses=[dict(model='qwen-plus',usage={'prompt_tokens':100,'completion_tokens':50},
                   choices=[dict(finish_reason='stop',message={'content':json.dumps(a,ensure_ascii=False)})]) for a in actions]
        decider=QwenDecider(payload,scope,ReplayTransport(responses),budget=budget,initial_fact_ids=FACTS)
        out=output/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10]);out.mkdir(parents=True)
        state={'goal':'格力电器2024—2025年净利润下降，但经营活动现金流净额增加。','questions':[],
               'history':[],'remaining':{'rounds':5,'tool_calls':4}}
        body=chat_body('qwen-plus',decider.prompt,json.dumps(decider.context(state),ensure_ascii=False),1200,SCHEMA)
        write(out/'export_scope.json',dict(fact_ids=list(FACTS),evidence_ids=list(EVIDENCE),initial_fact_ids=list(FACTS),
            authorization='not_granted',source_run=source.name,source_manifest_sha256=sha(source/'manifest.json')))
        result=investigate(payload,read(source/'investigation_plan.json'),decider,out/'offline_replay',max_rounds=5,max_tools=4)
        body=decider.records[0]['request'] if decider.records else body
        write(out/'first_request_not_called.json',body) # Exact replay request, never sent to a real provider.
        unresolved=[c for c in read(source/'conflicts.json') if c.get('status')!='resolved']
        # Scope is prepared, not granted; readiness is technical, never authorization.
        report=dict(status='ready_pending_authorization' if config['ready'] and not unresolved and result['status']=='pending_human_review' else 'blocked',
            real_api_called=False,configuration=config,source_run=str(source.resolve()),source_audit=audit,
            local_fact_count=len(payload['facts']),resolved=9-len(unresolved),unresolved=len(unresolved),
            fact_ids=list(FACTS),evidence_ids=list(EVIDENCE),max_investigations=1,max_rounds=5,max_tools=4,
            budget=vars(budget),retries=0,expected_requests='3—5，可能提前停止',
            pricing_basis=None,estimated_cny=None,cny_cap_guaranteed=False,
            pricing_note='项目未配置可确认的当前单价；实际费用未知。字节估计不是准确Token，不能保证人民币绝对上限。',
            replay_status=result['status'],replay_requests=result['model_requests'],replay_usage='synthetic_only',
            first_request_bytes=sum(len(m['content'].encode()) for m in body['messages']),
            safety=['只允许明确白名单；内部文件不外发','本期受限资金不作为同比贡献','未知用量停止，异常零重试','经营因果待人工复核'])
        write(out/'preflight.json',report)
        return out,report


def main():
    p=argparse.ArgumentParser(description='真实调查预检，仅离线；不读取密钥内容')
    p.add_argument('--stage2-run',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('outputs/agent_preflight'))
    a=p.parse_args();out,r=prepare(a.stage2_run,a.output);print(json.dumps({'output':str(out.resolve()),'status':r['status'],'real_api_called':False},ensure_ascii=False))

if __name__=='__main__':main()
