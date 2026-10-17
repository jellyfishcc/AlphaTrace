"""Offline allowlist export for the existing UI; never copies raw logs/attachments.

This first integration supports audited, failed real Qwen investigations. It is
not an Agent runner and never imports model credentials or calls a transport.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .agent import LocalFacts
from .final_release import load_agent_payload
from .stage3_input import read, sha
from .source_contract import digest, verified_evidence

SCHEMA = 'alphatrace-display-v1'
MISSING = '未提供'
UNSAFE = re.compile(r'(?i)([a-z]:[\\/]|\\\\|/(?:Users|home|tmp|etc|mnt)/|sk-[a-z0-9_-]{8,}|Bearer\s|api[_-]?key|authorization|微信|Wechat|金融组|\.docx|\.xlsx)')


def public_only(value):
    """Fail closed; do not silently redact a financial amount or evidence quote."""
    if isinstance(value, str) and UNSAFE.search(value): raise ValueError('unsafe_display_text')
    if isinstance(value, dict):
        for key, item in value.items(): public_only(key); public_only(item)
    if isinstance(value, list):
        for item in value: public_only(item)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('invalid_public_identifier')
    return value


def financial_rows(payload, metrics, cash_metrics):
    verified = LocalFacts(payload)
    groups = [[], []]
    seen = set()
    for group, originals in zip(groups, (metrics, cash_metrics)):
        for original in originals:
            key = original['item_id']
            if key not in verified.rows: continue
            if key in seen: raise ValueError('duplicate_display_metric')
            seen.add(key)
            fact = verified.get(key)
            raw = {}
            for field, column in [('base','base_amount'),('current','current_amount'),('change','difference')]:
                value = original.get(column)
                trusted = fact['amounts'].get(field, {}).get('元')
                if value is not None and (not isinstance(value,str) or trusted is None
                    or not Decimal(value).is_finite() or Decimal(value) != Decimal(trusted)):
                    raise ValueError('display_amount_not_verified:' + key)
                raw[field] = value
            group.append(dict(id=key, name=fact['name'], level=0,
                base=raw['base']+' 元' if raw['base'] is not None else MISSING,
                current=raw['current']+' 元' if raw['current'] is not None else MISSING,
                delta=raw['change']+' 元' if raw['change'] is not None else MISSING,
                yoy=original['yoy_percent']+'%' if original.get('yoy_percent') not in (None,'') else MISSING,
                impact=MISSING, relation=MISSING, residual=MISSING,
                status='后端来源核验通过', source=', '.join(fact['evidence_ids']), rawAmounts=raw))
    return groups


def investigation(folder, payload, snapshot):
    folder = Path(folder)
    hashes = read(folder/'audit_files_sha256.json')
    names = ['investigation/result.json','investigation/manifest.json',
             'investigation/input.json','investigation/events.jsonl','source_audit.json']
    for name in names:
        if hashes.get(name) != sha(folder/name): raise ValueError('agent_audit_hash_mismatch')
    source = read(folder/'source_audit.json')
    if source['source_manifest_sha256'] != sha(Path(snapshot)/'manifest.json'):
        raise ValueError('agent_snapshot_mismatch')
    result = read(folder/'investigation/result.json')
    manifest = read(folder/'investigation/manifest.json')
    original = read(folder/'investigation/input.json')
    if any(original.get(k) != payload.get(k) for k in ('company','periods','currency','scope')):
        raise ValueError('agent_context_mismatch')
    facts = {f['fact_id']:f for f in payload['facts']}
    for f in original['facts']:
        if digest(f) != digest(facts.get(f['fact_id'])): raise ValueError('agent_fact_mismatch')
    for key, expected in [('simulation',False),('llm_called',True),('decision_mode','qwen_real'),('status','validation_failed')]:
        if result.get(key) != expected or manifest.get(key) != expected:
            raise ValueError('unsupported_or_inconsistent_agent_run')
    events = [json.loads(line) for line in (folder/'investigation/events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    if not events or events[-1].get('event') != 'finished' or events[-1]['result'] != result:
        raise ValueError('agent_final_event_mismatch')
    evidence = {e['evidence_id']:e for e in payload['evidence']}
    steps = []
    for event in events:
        kind = event.get('event')
        if kind not in ('tool_result','error'): continue
        action = event.get('action','error')
        if action not in ('facts_list','fact_get','list','search','get','error'):
            raise ValueError('unsupported_display_action')
        args = event.get('arguments', {})
        allowed = {k:v for k,v in args.items() if k in ('query','metric_id','fact_id','evidence_id')}
        links = []
        if action in ('search','get','list'):
            returned = event.get('result', [])
            returned = returned if isinstance(returned,list) else [returned]
            for item in returned:
                eid = item['evidence_id']
                if eid not in evidence or digest(item)!=digest(evidence[eid]):
                    raise ValueError('agent_evidence_mismatch')
                links.append(eid)
        if action == 'fact_get': links = [identifier(args['fact_id'])]
        error = event.get('error')
        if error: identifier(error)
        steps.append(dict(round=event['round'],action=action,
            label='响应被阻断，未形成有效动作' if kind=='error' else '执行 '+action,
            summary=error or ('返回来源编号：'+', '.join(links) if links else '工具执行记录已保存'),
            params=json.dumps(allowed,ensure_ascii=False),
            result='未执行工具；没有合规解释提交' if kind=='error' else ', '.join(links) or '返回内容未纳入展示',
            links=links, **({'error':error} if error else {})))
    if sum(e.get('event')=='tool_result' for e in events)!=result['tool_calls']:
        raise ValueError('agent_tool_count_mismatch')
    summary = {key:result.get(key) for key in ('simulation','llm_called','real_request_attempts','rounds','tool_calls','errors','stop_reason')}
    return result, steps, summary, events[0].get('time', MISSING)


def build(snapshot, agent_run):
    snapshot, agent_run = Path(snapshot), Path(agent_run)
    payload,_ = load_agent_payload(snapshot)
    metrics,cash = financial_rows(payload,read(snapshot/'metrics.json'),read(snapshot/'cash_metrics.json'))
    result,steps,summary,run_at = investigation(agent_run,payload,snapshot)
    evidence = []
    metric_ids = {r['id'] for r in metrics+cash}
    for e in payload['evidence']:
        if not verified_evidence(e,payload): raise ValueError('unverified_display_evidence')
        if not metric_ids.intersection(e['related_facts']): continue
        filename = e['source_file']
        if '/' in filename or '\\' in filename or not filename.endswith('.pdf'):
            raise ValueError('invalid_public_source_filename')
        evidence.append(dict(id=e['evidence_id'],fileName=filename,quote=e['text'],
            summary=MISSING,printPage=str(e['printed_page']),pdfPage=str(e['pdf_page']),
            metrics=e['related_facts'],basis=e['comparison_basis'],verification='后端本地年报来源核验通过',
            supportLimit='仅为来源核验通过的披露原文；不代表 Agent 已读取或因果解释成立。'))
    record = dict(id='real-'+identifier(agent_run.name),
        run=dict(id=identifier(agent_run.name),label='格力真实调查 · 验证失败',company=payload['company'],ticker=MISSING,
            basePeriod=payload['periods'][0],currentPeriod=payload['periods'][1],scope=payload['scope'],
            materialVersion=identifier(snapshot.name),source='本地 Python 白名单展示包',mode='qwen_real',
            status=result['status'],statusLabel='真实调查失败 · '+', '.join(result['errors']),
            importedAt=datetime.now(timezone.utc).isoformat(),backendRunAt=run_at,isExample=False),
        question=result['goal'],pendingCount=len(result['errors']),metrics=metrics,cashMetrics=cash,
        evidence=evidence,explanations=[],steps=steps,agentSummary=summary,
        notices=['真实历史调查记录；浏览页面不会调用模型。',
            '仅展示通过现有来源验证且具有后端金额输出的记录；没有调用模型补值。',
            '没有通过验收的最终解释；响应截断片段不作为解释展示。',
            '会计影响、桥接残差和资料冲突详情本轮未接入，缺失字段保持未提供。'])
    bundle=dict(schema=SCHEMA,record=record,provenance=dict(snapshotId=snapshot.name,agentRunId=agent_run.name,
        financialSha256=sha(snapshot/'metrics.json'),cashSha256=sha(snapshot/'cash_metrics.json'),
        eventsSha256=sha(agent_run/'investigation/events.jsonl'),resultSha256=sha(agent_run/'investigation/result.json')))
    public_only(bundle)
    return bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage2-run',required=True)
    parser.add_argument('--agent-run',required=True)
    parser.add_argument('--output',required=True,help='new display JSON; existing files never overwritten')
    args=parser.parse_args()
    bundle=build(args.stage2_run,args.agent_run)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as stream:
        json.dump(bundle,stream,ensure_ascii=False,indent=2); stream.write('\n')
    print(json.dumps(dict(metrics=len(bundle['record']['metrics']),cash_metrics=len(bundle['record']['cashMetrics']),
        evidence=len(bundle['record']['evidence']),steps=len(bundle['record']['steps']),status=bundle['record']['run']['status']),ensure_ascii=False))


if __name__=='__main__': main()
