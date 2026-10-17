"""Explicit, single-use live investigation entry; default is offline preparation."""
import argparse
import copy
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agent import LocalFacts, investigate
from .agent_preflight import FACTS, EVIDENCE, configuration_presence
from .final_release import load_agent_payload
from .qwen_decider import Budget, ExportScope, LiveBailianTransport, QwenDecider, PROMPT
from .stage3 import write
from .stage3_input import read, sha

GOAL='格力电器2024—2025年净利润下降，但经营活动现金流量净额增长。根据已核验财务事实和公开年报原始披露，调查可能的解释及其证据边界。'
BUDGET=Budget(max_requests=5,max_output_tokens=1200,total_tokens=60000,timeout_seconds=90,max_input_bytes=16000)


def project(payload, fact_ids, evidence_ids):
    """Reduce tool visibility without rewriting trusted facts or source receipts."""
    result=copy.deepcopy(payload)
    result['facts']=[f for f in result['facts'] if f['fact_id'] in fact_ids]
    result['evidence']=[e for e in result['evidence'] if e['evidence_id'] in evidence_ids]
    for key,ids in [('facts',fact_ids),('evidence',evidence_ids)]:
        result['source_contract'][key]={k:v for k,v in result['source_contract'][key].items() if k in ids}
    result['analysis_contract']['accounting_relations']=[r for r in result['analysis_contract']['accounting_relations']
        if r['target'] in fact_ids and all(c['component'] in fact_ids for c in r['components'])]
    if {r['fact_id'] for r in LocalFacts(result).list()}!=set(fact_ids):
        raise ValueError('scoped_facts_not_verified')
    if {e['evidence_id'] for e in result['evidence']}!=set(evidence_ids):
        raise ValueError('scoped_evidence_missing')
    return result


def prepare(source, preflight, scope_file):
    source=Path(source).resolve();preflight=Path(preflight);scope_file=Path(scope_file)
    report=read(preflight);scope=read(scope_file)
    if report['status']!='ready_pending_authorization' or Path(report['source_run']).resolve()!=source:
        raise ValueError('preflight_source_mismatch')
    if scope['source_run']!=source.name or scope['source_manifest_sha256']!=sha(source/'manifest.json'):
        raise ValueError('scope_snapshot_changed')
    for item in (report,scope):
        if set(item['fact_ids'])!=set(FACTS) or set(item['evidence_ids'])!=set(EVIDENCE):
            raise ValueError('authorization_scope_mismatch')
    if report['budget']!=vars(BUDGET) or report['max_rounds']!=5 or report['max_tools']!=4 or report['retries']!=0:
        raise ValueError('preflight_budget_mismatch')
    payload,audit=load_agent_payload(source)
    if audit!=report['source_audit']:raise ValueError('source_audit_changed')
    conflicts=read(source/'conflicts.json')
    if len(conflicts)!=9 or any(c.get('status')!='resolved' for c in conflicts):
        raise ValueError('unresolved_source_conflict')
    if len(LocalFacts(payload).list())!=45:raise ValueError('trusted_fact_count_changed')
    config=configuration_presence()
    if not config['ready'] or config['endpoint']!=report['configuration']['endpoint']:
        raise ValueError('endpoint_or_configuration_changed')
    scoped=project(payload,FACTS,EVIDENCE)
    return scoped,dict(source_audit=audit,source_path=str(source),preflight_sha256=sha(preflight),
        scope_file_sha256=sha(scope_file),source_manifest_sha256=sha(source/'manifest.json'),
        release_hashes=read(source/'release_hashes.json'),configuration=config)


def claim_once(root, authorization_id, record):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',authorization_id):raise ValueError('invalid_authorization_id')
    folder=Path(root)/'authorizations';folder.mkdir(parents=True,exist_ok=True)
    # Exclusive create persists even on timeout/crash. Never auto-clear or retry.
    with (folder/(authorization_id+'.json')).open('x',encoding='utf-8') as f:
        json.dump(record,f,ensure_ascii=False,indent=2)


def main(argv=None):
    parser=argparse.ArgumentParser(description='默认仅预备；--execute-real 显式开启一次已授权调查')
    parser.add_argument('--stage2-run',type=Path,required=True)
    parser.add_argument('--preflight',type=Path,required=True)
    parser.add_argument('--scope',type=Path,required=True)
    parser.add_argument('--execute-real',action='store_true')
    parser.add_argument('--authorization-id')
    parser.add_argument('--output',type=Path,default=Path('outputs/agent_live'))
    args=parser.parse_args(argv)
    payload,audit=prepare(args.stage2_run,args.preflight,args.scope)
    if not args.execute_real:
        print(json.dumps(dict(status='ready_not_called',llm_called=False,fact_ids=FACTS,evidence_ids=EVIDENCE),ensure_ascii=False))
        return 0
    if not args.authorization_id:parser.error('--execute-real requires --authorization-id')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10]
    out=args.output/run_id
    authorization=dict(id=args.authorization_id,time=datetime.now(timezone.utc).isoformat(),run_id=run_id,
        goal=GOAL,fact_ids=list(FACTS),evidence_ids=list(EVIDENCE),budget=vars(BUDGET),
        max_rounds=5,max_tools=4,retries=0,max_investigations=1,simulation=False,
        source_manifest_sha256=audit['source_manifest_sha256'])
    decider=QwenDecider(payload,ExportScope(frozenset(FACTS),frozenset(EVIDENCE),args.authorization_id),
        LiveBailianTransport(authorized=True,expected_endpoint=audit['configuration']['endpoint']),
        budget=BUDGET,model='qwen-plus',initial_fact_ids=FACTS)
    claim_once(args.output,args.authorization_id,authorization)
    out.mkdir(parents=True,exist_ok=False)
    write(out/'authorization.json',authorization)
    write(out/'source_audit.json',audit)
    write(out/'code_hashes.json',{str(p):sha(p) for p in [Path(__file__),PROMPT,
        Path('tracelab/agent.py'),Path('tracelab/qwen_decider.py'),Path('tracelab/stage3.py'),Path('tracelab/bailian.py')]})
    print(json.dumps({'output':str(out.resolve()),'status':'starting_authorized_investigation'},ensure_ascii=False),flush=True)
    plan={'signals':[{'id':'authorized_goal','description':GOAL}], 'investigation_tasks':[]}
    result=investigate(payload,plan,decider,out/'investigation',max_rounds=5,max_tools=4)
    print(json.dumps({'output':str(out.resolve()),**result},ensure_ascii=False))
    return 1 if result['status']=='validation_failed' else 0


if __name__=='__main__':raise SystemExit(main())
