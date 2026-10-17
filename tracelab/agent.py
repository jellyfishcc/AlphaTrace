"""Bounded local investigation. CLI is mock-only and never reads model credentials."""
import argparse
import copy
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .stage3_input import prepare, read, sha
from .stage3 import validate, write
from .investigation import prepare_investigation


def bounded(value, limit=100000):
    if len(json.dumps(value,ensure_ascii=False).encode('utf-8'))>limit:
        raise ValueError('input_size_limit')


class Decider(Protocol):
    def decide(self, state: dict) -> dict:
        """Return one action; evidence is data, never executable instructions."""


class LocalEvidence:
    def __init__(self, payload):
        bounded(payload)
        self.rows={e['evidence_id']:copy.deepcopy(e) for e in payload['evidence']}
        if len(self.rows)!=len(payload['evidence']): raise ValueError('duplicate_evidence_id')

    def list(self):
        return [{k:e[k] for k in ('evidence_id','related_facts','source_file','printed_page','pdf_page')}
                for e in self.rows.values()]

    def search(self, query='', metric_id=''):
        if not query and not metric_id: raise ValueError('empty_search')
        if len(query)>300 or len(metric_id)>100: raise ValueError('query_size_limit')
        tokens=re.findall(r'[a-zA-Z_]+|[\u4e00-\u9fff]{2}',query.lower())
        hits=[]
        for e in self.rows.values():
            if metric_id and metric_id not in e['related_facts']: continue
            text=e['text'].lower()
            score=sum(t in text for t in tokens)
            if query and not score and query.lower() not in text: continue
            hits.append((score,e))
        # Local lexical matching, not semantic or model ranking.
        return [copy.deepcopy(e) for _,e in sorted(hits,key=lambda pair:-pair[0])][:20]

    def get(self, evidence_id):
        if evidence_id not in self.rows: raise ValueError('unknown_evidence_id')
        return copy.deepcopy(self.rows[evidence_id])


class MockDecider:
    """Preset demonstration policy, not autonomous LLM reasoning."""
    def decide(self,state):
        history=state['history']
        if not history: return {'action':'list','arguments':{}}
        if len(history)==1:
            return {'action':'search','arguments':{'question_index':0}}
        if len(history)==2:
            hits=history[-1]['result']
            if not hits: return {'action':'stop','arguments':{'reason':'模拟检索未找到证据'}}
            return {'action':'get','arguments':{'evidence_id':hits[0]['evidence_id']}}
        evidence=history[-1]['result']
        available={f['fact_id'] for f in state['facts']}
        related=[k for k in evidence['related_facts'] if k in available]
        if not related: return {'action':'stop','arguments':{'reason':'模拟证据未关联已核实项目'}}
        answer={'claims':[{'kind':'hypothesis','statement':'待验证：相关披露是否足以解释调查目标中的变化',
                 'metric_ids':related,'citations':[{'evidence_id':evidence['evidence_id'],'quote':evidence['text']}],
                 'amounts':[],'support_limit':'仅发现相关原文，尚不足以确认经营因果；需要金融组复核',
                 'accounting_links':[],'comparison_basis':'none'}],
                 'questions':['是否有可支持该解释及排除其他原因的公开披露？']}
        return {'action':'explain','arguments':{'analysis':answer}}


def investigate(payload, plan, decider, out, max_rounds=6, max_tools=4):
    """Pure local orchestration; caller supplies a decision implementation."""
    if not 1<=max_rounds<=20 or not 1<=max_tools<=20: raise ValueError('invalid_limits')
    bounded(payload); bounded(plan)
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    tools=LocalEvidence(payload)
    tasks=plan.get('investigation_tasks',[])
    signals=plan.get('signals',[])
    matching=[t for t in tasks if t.get('reason') in {s['id'] for s in signals}]
    selected=matching or tasks
    questions=[q for t in selected for q in t.get('questions',[])]
    goal='；'.join(s['description'] for s in signals) or '核查已计算的利润变化及其披露依据'
    state=dict(goal=goal,questions=questions,facts=copy.deepcopy(payload['facts']),
               analysis_contract=copy.deepcopy(payload.get('analysis_contract',{})),history=[])
    result=dict(status='insufficient_evidence',simulation=True,llm_called=False,
                decision_source=type(decider).__name__,goal=goal,errors=[],manual_review=[],
                stop_reason='round_limit',tool_calls=0,max_rounds=max_rounds,max_tools=max_tools)
    seen=set()
    def log(event):
        event['time']=datetime.now(timezone.utc).isoformat()
        with (out/'events.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(event,ensure_ascii=False)+'\n')
    write(out/'input.json',payload); write(out/'plan.json',plan)
    log({'event':'started','simulation':True,'goal':goal})
    for index in range(max_rounds):
        try:
            bounded(state,500000)
            decision=decider.decide(copy.deepcopy(state))
            bounded(decision,30000)
            log({'event':'decision','round':index+1,'decision':decision})
            if not isinstance(decision,dict) or set(decision)!={'action','arguments'}:
                raise ValueError('invalid_decision_structure')
            action,args=decision['action'],decision['arguments']
            if not isinstance(args,dict): raise ValueError('invalid_arguments')
            allowed={'list':set(),'search':{'query','metric_id','question_index'},'get':{'evidence_id'},
                     'explain':{'analysis'},'stop':{'reason','analysis'}}
            if not isinstance(action,str) or action not in allowed or not set(args)<=allowed[action]:
                raise ValueError('invalid_action_or_arguments')
            if action in ('explain','stop'):
                if action=='explain' and 'analysis' not in args: raise ValueError('missing_analysis')
                if action=='stop' and (not isinstance(args.get('reason'),str) or not args['reason'].strip()):
                    raise ValueError('missing_stop_reason')
                if 'analysis' in args:
                    # Only retrieved evidence may support a conclusion, not unseen inventory.
                    check_payload=copy.deepcopy(payload)
                    check_payload['evidence']=[e for e in payload['evidence'] if e['evidence_id'] in seen]
                    checks=validate(args['analysis'],check_payload)
                    write(out/'analysis.json',args['analysis']); write(out/'checks.json',checks)
                    result['errors'].extend(checks['errors'])
                    result['manual_review'].extend(checks['manual_review'])
                result['status']=('validation_failed' if result['errors'] else
                                  'pending_human_review' if action=='explain' else 'insufficient_evidence')
                result['stop_reason']=args.get('reason','explanation_submitted')
                break
            if result['tool_calls']>=max_tools:
                result['stop_reason']='tool_limit'; break
            result['tool_calls']+=1
            if action=='list': value=tools.list()
            elif action=='get':
                if not isinstance(args.get('evidence_id'),str): raise ValueError('invalid_evidence_id')
                value=tools.get(args['evidence_id']); seen.add(value['evidence_id'])
            else:
                query=args.get('query',''); metric=args.get('metric_id','')
                if not isinstance(query,str) or not isinstance(metric,str): raise ValueError('invalid_search')
                if 'question_index' in args:
                    q=args['question_index']
                    if type(q)!=int or not 0<=q<len(questions): raise ValueError('unknown_question')
                    query=questions[q]
                value=tools.search(query,metric)
                seen.update(e['evidence_id'] for e in value)
            bounded(value)
            entry={'action':action,'arguments':args,'result':value}
            state['history'].append(entry)
            log({'event':'tool_result','round':index+1,**entry})
        except Exception as exc:
            # Record type, not arbitrary exception text from a future decider.
            reason=str(exc) if type(exc)==ValueError and str(exc) in {
                'unknown_evidence_id','invalid_decision_structure','invalid_arguments','invalid_action_or_arguments',
                'missing_analysis','missing_stop_reason','invalid_evidence_id','invalid_search','unknown_question',
                'input_size_limit','empty_search','query_size_limit'} else type(exc).__name__
            result['errors'].append(reason)
            result.update(status='validation_failed',stop_reason='invalid_decision_or_tool_error')
            log({'event':'error','round':index+1,'error':reason}); break
    result['rounds']=index+1
    result['retrieved_evidence_ids']=sorted(seen)
    write(out/'result.json',result)
    log({'event':'finished','result':result})
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='仅本地Mock调查，无真实模型入口')
    parser.add_argument('--stage2-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('outputs/agent'))
    parser.add_argument('--max-rounds',type=int,default=6)
    parser.add_argument('--max-tools',type=int,default=4)
    parser.add_argument('--final-evidence',action='store_true',help='显式加载最终版独立快照中的扩充证据，仍仅Mock')
    args=parser.parse_args(argv)
    if args.final_evidence:
        from .final_release import load_agent_payload
        payload,audit=load_agent_payload(args.stage2_run)
    else:
        payload,audit=prepare(args.stage2_run,mode='focused')
    plan=read(args.stage2_run/'investigation_plan.json')
    computed=prepare_investigation(read(args.stage2_run/'metrics.json'))
    if plan['signals']!=computed['signals']: raise ValueError('调查信号与现有计算结果不一致')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10]
    out=args.output/run_id
    result=investigate(payload,plan,MockDecider(),out,args.max_rounds,args.max_tools)
    write(out/'manifest.json',dict(run_id=run_id,simulation=True,llm_called=False,
          source_audit=audit,plan_sha256=sha(args.stage2_run/'investigation_plan.json'),
          code_sha256=sha(__file__),status=result['status']))
    print(json.dumps({'output':str(out.resolve()),'status':result['status'],'simulation':True,'llm_called':False},ensure_ascii=False))
    return 1 if result['status']=='validation_failed' else 0


if __name__=='__main__':
    raise SystemExit(main())
