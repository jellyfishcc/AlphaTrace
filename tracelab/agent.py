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


class LocalFacts:
    """Only the loader's verified allowlist; no paths, mutation, or arithmetic."""
    def __init__(self,payload):
        from .source_contract import digest, verified_evidence
        bounded(payload)
        self.rows={}
        evidence={e['evidence_id']:e for e in payload['evidence']}
        registry=payload.get('source_contract',{}).get('facts',{})
        levels={'operating_profit':'营业利润','pretax_profit':'利润总额','net_profit':'净利润',
                'parent_profit':'归母净利润','minority_profit':'净利润至归母净利润衔接',
                'income_tax':'利润总额至净利润衔接','nonoperating_income':'营业利润至利润总额衔接',
                'nonoperating_expense':'营业利润至利润总额衔接','operating_cashflow':'经营现金流净额',
                'bill_deposits':'本期现金流补充资料调节项'}
        levels.update({k:'营业利润列示项目' for k in ('total_revenue','total_cost','other_income','investment_income','credit_impairment','asset_impairment','disposal_income')})
        levels.update({k:'营业总成本明细' for k in ('operating_cost','interest_expense','fee_expense','tax_surcharges','selling_expense','administrative_expense','rd_expense','finance_expense')})
        levels.update(revenue='营业总收入明细',interest_income='营业总收入明细',continuing_profit='净利润分类',discontinued_profit='净利润分类',adjusted_parent_profit='扣非归母净利润；非会计桥接组成')
        relations=payload.get('analysis_contract',{}).get('accounting_relations',[])
        for f in payload['facts']:
            key=f['fact_id']
            if key in self.rows: raise ValueError('duplicate_fact_id')
            if registry.get(key)!=digest(f): continue
            if any(eid not in evidence or not verified_evidence(evidence[eid],payload) for eid in f['evidence_ids']): continue
            row=copy.deepcopy(f)
            row['financial_level']=levels.get(key,'经营现金流直接法分项' if key.startswith('cash_') else '财务报表项目；层级关系见单独核验记录')
            row['relation_targets']=[r['target'] for r in relations if any(c['component']==key for c in r['components'])]
            row['source_status']='verified_local_annual_report'
            row['source_run']=payload['source_contract'].get('source_run')
            row['periods']=copy.deepcopy(payload.get('periods',[]))
            row['availability']={field:('available' if field in f['amounts'] else 'unavailable_not_zero') for field in ('base','current','change')}
            row['original_unit']='元'
            self.rows[key]=row

    def list(self):
        return [dict(fact_id=k,name=v['name'],financial_level=v['financial_level'],source_status=v['source_status']) for k,v in self.rows.items()]

    def get(self,fact_id):
        if not isinstance(fact_id,str) or len(fact_id)>100: raise ValueError('invalid_fact_id')
        if fact_id not in self.rows: raise ValueError('unknown_or_unverified_fact')
        return copy.deepcopy(self.rows[fact_id])


class FactEvidenceMockDecider:
    """Demonstrate tool wiring only; intentionally makes no causal conclusion."""
    def decide(self,state):
        history=state['history']
        if not history: return {'action':'facts_list','arguments':{}}
        if len(history)==1:
            rows=history[-1]['result']
            if not rows: return {'action':'stop','arguments':{'reason':'没有可用事实'}}
            key=next((r['fact_id'] for r in rows if r['fact_id']=='operating_cashflow'),rows[0]['fact_id'])
            return {'action':'fact_get','arguments':{'fact_id':key}}
        if len(history)==2: return {'action':'search','arguments':{'metric_id':history[-1]['result']['fact_id']}}
        if len(history)==3:
            rows=history[-1]['result']
            if not rows: return {'action':'stop','arguments':{'reason':'未找到相关原文'}}
            # A preset coverage heuristic, not an assertion about causal relevance.
            return {'action':'get','arguments':{'evidence_id':max(rows,key=lambda e:len(e['text']))['evidence_id']}}
        return MockDecider().decide(state)


def investigate(payload, plan, decider, out, max_rounds=6, max_tools=4):
    """Pure local orchestration; caller supplies a decision implementation."""
    if not 1<=max_rounds<=20 or not 1<=max_tools<=20: raise ValueError('invalid_limits')
    bounded(payload); bounded(plan)
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    if hasattr(decider,'attach_run'): decider.attach_run(out)
    tools=LocalEvidence(payload)
    facts_tool=LocalFacts(payload)
    tasks=plan.get('investigation_tasks',[])
    signals=plan.get('signals',[])
    matching=[t for t in tasks if t.get('reason') in {s['id'] for s in signals}]
    selected=matching or tasks
    questions=[q for t in selected for q in t.get('questions',[])]
    goal='；'.join(s['description'] for s in signals) or '核查已计算的利润变化及其披露依据'
    state=dict(goal=goal,questions=questions,facts=copy.deepcopy(payload['facts']),
               analysis_contract=copy.deepcopy(payload.get('analysis_contract',{})),history=[])
    runtime=lambda: (decider.runtime_status() if hasattr(decider,'runtime_status') else
                     dict(simulation=True,llm_called=False,decision_mode='preset_mock',model_requests=0))
    result=dict(status='insufficient_evidence',**runtime(),
                decision_source=type(decider).__name__,goal=goal,errors=[],manual_review=[],
                stop_reason='round_limit',tool_calls=0,max_rounds=max_rounds,max_tools=max_tools)
    seen=set()
    def log(event):
        event['time']=datetime.now(timezone.utc).isoformat()
        with (out/'events.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(event,ensure_ascii=False)+'\n')
    write(out/'input.json',payload); write(out/'plan.json',plan)
    log({'event':'started',**runtime(),'goal':goal})
    for index in range(max_rounds):
        try:
            bounded(state,500000)
            state['remaining']={'rounds':max_rounds-index,'tool_calls':max_tools-result['tool_calls']}
            decision=decider.decide(copy.deepcopy(state))
            if hasattr(decider,'runtime_status'): log({'event':'model_decision','round':index+1,**runtime()})
            bounded(decision,30000)
            log({'event':'decision','round':index+1,'decision':decision})
            if not isinstance(decision,dict) or set(decision)!={'action','arguments'}:
                raise ValueError('invalid_decision_structure')
            action,args=decision['action'],decision['arguments']
            if not isinstance(args,dict): raise ValueError('invalid_arguments')
            allowed={'list':set(),'search':{'query','metric_id','question_index'},'get':{'evidence_id'},
                     'facts_list':set(),'fact_get':{'fact_id'},
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
            elif action=='facts_list': value=facts_tool.list()
            elif action=='fact_get': value=facts_tool.get(args.get('fact_id'))
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
            from .qwen_decider import DecisionFailure
            # Record type, not arbitrary exception text from a future decider.
            reason=str(exc) if isinstance(exc,DecisionFailure) else str(exc) if type(exc)==ValueError and str(exc) in {
                'unknown_evidence_id','invalid_decision_structure','invalid_arguments','invalid_action_or_arguments',
                'missing_analysis','missing_stop_reason','invalid_evidence_id','invalid_search','unknown_question',
                'input_size_limit','empty_search','query_size_limit','invalid_fact_id','unknown_or_unverified_fact'} else type(exc).__name__
            result['errors'].append(reason)
            result.update(status='validation_failed',stop_reason='invalid_decision_or_tool_error')
            log({'event':'error','round':index+1,'error':reason,**runtime()}); break
    result.update(runtime())
    result['rounds']=index+1
    result['retrieved_evidence_ids']=sorted(seen)
    result['retrieval_audit']=[dict(action=h['action'],arguments=h['arguments'],
        evidence_ids=[e['evidence_id'] for e in h['result']] if h['action']=='search' else [h['result']['evidence_id']])
        for h in state['history'] if h['action'] in ('search','get')]
    result['evidence_gap']=result['stop_reason'] if result['status']=='insufficient_evidence' else None
    write(out/'result.json',result)
    write(out/'manifest.json',dict(run_id=out.name,**runtime(),status=result['status'],
          decision_source=type(decider).__name__,code_sha256=sha(__file__)))
    log({'event':'finished','result':result})
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='仅本地Mock调查，无真实模型入口')
    parser.add_argument('--stage2-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('outputs/agent'))
    parser.add_argument('--max-rounds',type=int,default=6)
    parser.add_argument('--max-tools',type=int,default=4)
    parser.add_argument('--final-evidence',action='store_true',help='显式加载最终版独立快照中的扩充证据，仍仅Mock')
    parser.add_argument('--mock-facts',action='store_true',help='模拟事实查询与证据工具联合流程；无模型调用')
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
    result=investigate(payload,plan,FactEvidenceMockDecider() if args.mock_facts else MockDecider(),out,args.max_rounds,args.max_tools)
    write(out/'manifest.json',dict(run_id=run_id,simulation=result['simulation'],llm_called=result['llm_called'],
          decision_mode=result['decision_mode'],model_requests=result['model_requests'],
          source_audit=audit,plan_sha256=sha(args.stage2_run/'investigation_plan.json'),
          code_sha256=sha(__file__),status=result['status']))
    print(json.dumps({'output':str(out.resolve()),'status':result['status'],'simulation':True,'llm_called':False},ensure_ascii=False))
    return 1 if result['status']=='validation_failed' else 0


if __name__=='__main__':
    raise SystemExit(main())
