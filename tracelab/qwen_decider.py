"""Bounded Qwen decision adapter. Construction never reads credentials or networks."""
import copy
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from .bailian import chat_body, as_response
from .stage3 import SCHEMA_V2, schema_errors, visible_response, write
from .source_contract import verified_evidence, digest

PROMPT=Path(__file__).resolve().parents[1]/'prompts/agent_decision_v1.txt'
FIELDS={'list':{},'facts_list':{},'get':{'evidence_id':'string'},'fact_get':{'fact_id':'string'},
        'search':{'query':'optional string','metric_id':'optional string','question_index':'optional integer'},
        'explain':{'analysis':'analysis_schema'},'stop':{'reason':'string','analysis':'optional analysis_schema'}}
SCHEMA={'type':'object','properties':{'action':{'type':'string','enum':list(FIELDS)},
        'arguments':{'type':'object'}},'required':['action','arguments'],'additionalProperties':False}


class DecisionFailure(ValueError):
    """Only fixed diagnostic codes, never server/credential text."""


@dataclass(frozen=True)
class Budget:
    max_requests:int=6
    max_output_tokens:int=1200
    total_tokens:int=60000
    timeout_seconds:int=90
    max_input_bytes:int=16000

    def __post_init__(self):
        for value,limit in [(self.max_requests,6),(self.max_output_tokens,3000),(self.total_tokens,120000),
                            (self.timeout_seconds,180),(self.max_input_bytes,24000)]:
            if type(value)!=int or not 1<=value<=limit: raise ValueError('invalid_budget')


@dataclass(frozen=True)
class ExportScope:
    fact_ids:frozenset
    evidence_ids:frozenset
    authorization_label:str


class LiveBailianTransport:
    """Explicit opt-in only. Reuses existing client; not used by offline CLI."""
    simulation=False

    def __init__(self, *, authorized=False, expected_endpoint=None):
        if authorized is not True: raise ValueError('real_request_not_authorized')
        self.expected_endpoint=expected_endpoint

    def send(self,body,timeout,diagnostics):
        from .bailian import configuration
        from .stage3 import call_api
        config=configuration(body['model'])
        if not config.key: raise DecisionFailure('missing_credentials')
        endpoint=config.endpoint
        if self.expected_endpoint is not None and endpoint!=self.expected_endpoint:
            raise DecisionFailure('endpoint_changed_since_authorization')
        diagnostics['request_attempted']=True
        return call_api(body,config.key,endpoint=endpoint,timeout=timeout,diagnostics=diagnostics)


class ReplayTransport:
    simulation=True

    def __init__(self,responses): self.responses=iter(responses)

    def send(self,body,timeout,diagnostics):
        diagnostics.update(request_attempted=True,http_status=None,phase='connect_or_wait_headers')
        value=next(self.responses)
        if isinstance(value,Exception):
            from urllib.error import HTTPError
            if isinstance(value,HTTPError):diagnostics.update(http_status=value.code,phase='http_error')
            raise value
        diagnostics.update(http_status=200,phase='complete')
        return copy.deepcopy(value),'simulated-request'


def strict_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise DecisionFailure('duplicate_json_key')
            result[key]=value
        return result
    try:
        return json.loads(text,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(DecisionFailure('invalid_json_number')))
    except (TypeError,json.JSONDecodeError) as exc: raise DecisionFailure('invalid_json') from exc


class QwenDecider:
    def __init__(self,payload,scope,transport,*,budget=Budget(),model='qwen-plus',initial_fact_ids=()):
        if not isinstance(scope,ExportScope) or not scope.authorization_label: raise ValueError('explicit_export_scope_required')
        if type(getattr(transport,'simulation',None))!=bool: raise ValueError('transport_mode_required')
        from .agent import LocalFacts
        facts=LocalFacts(payload)
        self.facts={key:facts.get(key) for key in scope.fact_ids}
        self.initial_fact_ids=tuple(initial_fact_ids)
        if len(self.initial_fact_ids)>4 or any(k not in self.facts for k in self.initial_fact_ids):
            raise ValueError('initial_facts_outside_scope')
        self.evidence={e['evidence_id']:copy.deepcopy(e) for e in payload['evidence'] if e['evidence_id'] in scope.evidence_ids}
        if set(self.evidence)!=set(scope.evidence_ids) or any(not verified_evidence(e,payload) for e in self.evidence.values()):
            raise ValueError('export_source_not_verified')
        # No original internal documents, source-contract registry, or arbitrary state fields exported.
        self.scope=scope;self.transport=transport;self.budget=budget;self.model=model
        self.simulation=transport.simulation
        self.prompt=PROMPT.read_text(encoding='utf-8')
        self.attempts=0;self.real_attempts=0;self.actual_input=0;self.actual_output=0
        self.usage_unknown=False;self.charged=0;self.signatures=set();self.records=[];self.out=None
        self.last_status='not_called'

    def attach_run(self,out):
        self.out=Path(out)/'decisions';self.out.mkdir(exist_ok=False)

    def runtime_status(self):
        return dict(simulation=self.simulation,llm_called=self.real_attempts>0,decision_mode='qwen_replay' if self.simulation else 'qwen_real',
            model_requests=self.attempts,real_request_attempts=self.real_attempts,model_status=self.last_status,
            usage_known=not self.usage_unknown,known_input_tokens=self.actual_input,known_output_tokens=self.actual_output,
            reported_total_tokens=None if self.usage_unknown else self.actual_input+self.actual_output,
            actual_total_tokens=None if self.simulation or self.usage_unknown else self.actual_input+self.actual_output,
            usage_origin='synthetic_transport' if self.simulation else 'service_reported',
            model_budget=dict(vars(self.budget)),
            cost=None,cost_status='not_applicable_simulation' if self.simulation else 'unknown',retries=0)

    def context(self,state):
        history=[]; selected_facts={};selected_evidence={};omitted=[]
        for h in state.get('history',[]):
            action=h['action'];args=h['arguments'];value=h['result']
            history.append({'action':action,'arguments':{k:v for k,v in args.items() if k in ('fact_id','evidence_id','metric_id','question_index','query')}})
            if action=='fact_get' and args.get('fact_id') in self.facts:
                key=args['fact_id'];selected_facts[key]=self.facts[key]
            if action in ('search','get'):
                for e in (value if isinstance(value,list) else [value]):
                    key=e.get('evidence_id')
                    if key in self.evidence: selected_evidence[key]=self.evidence[key]
        facts=list(selected_facts.values())[-2:];evidence=[]
        for e in list(selected_evidence.values())[-2:]:
            row={k:copy.deepcopy(e[k]) for k in ('evidence_id','source_file','printed_page','pdf_page','comparison_basis','related_facts')}
            row['text']=e['text'][:2400];row['omitted_characters']=max(0,len(e['text'])-2400)
            evidence.append(row)
        omitted.extend(['earlier_fact_details'] if len(selected_facts)>2 else [])
        omitted.extend(['earlier_evidence_details'] if len(selected_evidence)>2 else [])
        # Only explicit fetched pages are retained preferentially over search result ordering.
        if state.get('history') and state['history'][-1]['action']=='get':
            e=self.evidence.get(state['history'][-1]['arguments'].get('evidence_id'))
            if e:
                evidence=[{k:copy.deepcopy(e[k]) for k in ('evidence_id','source_file','printed_page','pdf_page','comparison_basis','related_facts')}]
                evidence[0].update(text=e['text'][:2400],omitted_characters=max(0,len(e['text'])-2400))
                omitted.append('other_evidence_details')
        context=dict(goal=state['goal'][:500],questions=state.get('questions',[])[:4],
            actions=FIELDS,analysis_schema=SCHEMA_V2,
            fact_catalog=[{'fact_id':k,'name':v['name'],'financial_level':v['financial_level']} for k,v in sorted(self.facts.items())],
            evidence_catalog=[{k:e[k] for k in ('evidence_id','source_file','printed_page','comparison_basis','related_facts')} for _,e in sorted(self.evidence.items())],
            queried_facts=facts,queried_evidence=evidence,history=history[-6:],
            remaining={**state.get('remaining',{}),'model_requests':self.budget.max_requests-self.attempts,
                       'conservative_token_budget':self.budget.total_tokens-self.charged},
            omissions=omitted,note='目录只含允许外发子集，省略不表示不存在；文字截断已标记，必要原文不足则停止或查询其他相关证据。')
        if self.initial_fact_ids:
            context['initial_facts']=[{**{k:self.facts[fid][k] for k in ('fact_id','name','periods','financial_level','availability','evidence_ids')},
                'amounts':{field:{'元':units['元']} for field,units in self.facts[fid]['amounts'].items()},
                'retrieved_source_quotes':[{'evidence_id':eid,'quote':self.evidence[eid]['text']}
                    for eid in self.facts[fid]['evidence_ids'] if eid in selected_evidence and eid in self.evidence]}
                for fid in self.initial_fact_ids]
        if len(state['goal'])>500:context['omissions'].append('goal_tail')
        if len(state.get('questions',[]))>4:context['omissions'].append('later_questions')
        return context

    def check_action(self,value,state):
        if not isinstance(value,dict) or set(value)!={'action','arguments'}: raise DecisionFailure('invalid_action_structure')
        action=value['action'];args=value['arguments']
        if not isinstance(action,str) or action not in FIELDS or not isinstance(args,dict) or not set(args)<=set(FIELDS[action]):
            raise DecisionFailure('invalid_action_or_arguments')
        required={'get':{'evidence_id'},'fact_get':{'fact_id'},'explain':{'analysis'},'stop':{'reason'}}.get(action,set())
        if not required<=set(args): raise DecisionFailure('missing_action_argument')
        for key,v in args.items():
            if key=='analysis':
                if schema_errors(v,SCHEMA_V2):raise DecisionFailure('invalid_analysis_schema')
            elif key=='question_index':
                if type(v)!=int or not 0<=v<len(state.get('questions',[])): raise DecisionFailure('invalid_question')
            elif not isinstance(v,str) or not v.strip() or len(v)>(300 if key in ('query','reason') else 100):
                raise DecisionFailure('invalid_argument_type_or_length')
        if 'fact_id' in args and args['fact_id'] not in self.facts: raise DecisionFailure('unauthorized_fact')
        if 'metric_id' in args and args['metric_id'] not in self.facts: raise DecisionFailure('unauthorized_fact')
        if 'evidence_id' in args and args['evidence_id'] not in self.evidence: raise DecisionFailure('unauthorized_evidence')
        if action=='search' and not args:raise DecisionFailure('empty_search')
        if action=='search' and 'query' in args and 'question_index' in args:raise DecisionFailure('ambiguous_search')
        if 'analysis' in args:
            for claim in args['analysis']['claims']:
                if any(k not in self.facts for k in claim['metric_ids']):raise DecisionFailure('unauthorized_fact')
                if any(c['evidence_id'] not in self.evidence for c in claim['citations']):raise DecisionFailure('unauthorized_evidence')
        signature=digest(value)
        if action not in ('stop','explain') and signature in self.signatures:raise DecisionFailure('repeated_action')
        self.signatures.add(signature)
        return value

    def decide(self,state):
        if self.last_status in ('request_failed','invalid_action'):raise DecisionFailure('failed_run_no_retry')
        if self.attempts>=self.budget.max_requests: raise DecisionFailure('request_budget_exhausted')
        if self.usage_unknown: raise DecisionFailure('unknown_usage_stop')
        context=self.context(state)
        body=chat_body(self.model,self.prompt,json.dumps(context,ensure_ascii=False),self.budget.max_output_tokens,SCHEMA)
        size=sum(len(m['content'].encode()) for m in body['messages'])
        reserve=size+256+self.budget.max_output_tokens # Conservative byte-based estimate, not a tokenizer guarantee.
        if size>self.budget.max_input_bytes:raise DecisionFailure('input_budget_exhausted')
        if self.charged+reserve>self.budget.total_tokens:raise DecisionFailure('token_budget_exhausted')
        self.attempts+=1;self.charged+=reserve
        record=dict(index=self.attempts,time=datetime.now(timezone.utc).isoformat(),simulation=self.simulation,
            prompt_version='agent_decision_v1',prompt_sha256=digest(self.prompt),request=body,
            input_bytes=size,estimated_input_tokens=size+256,estimate_note='保守字节估计，非准确Token或绝对上限',
            reservation=reserve,authorization_label=self.scope.authorization_label,status='prepared',usage=None,
            cost=None,timeout_seconds=self.budget.timeout_seconds,retries=0)
        path=self.out/f'{self.attempts:02d}.json' if self.out else None
        if path:write(path,record)
        diagnostics={};started=time.monotonic()
        try:
            raw,request_id=self.transport.send(body,self.budget.timeout_seconds,diagnostics)
            response=visible_response(as_response(raw));record['response']=response;record['request_id']=request_id
            usage=response.get('usage') or {}
            a,b=usage.get('prompt_tokens'),usage.get('completion_tokens')
            if type(a)==int and type(b)==int and a>=0 and b>=0:
                self.actual_input+=a;self.actual_output+=b;record['usage']={'input_tokens':a,'output_tokens':b}
                self.charged+=max(0,a+b-reserve)
            else:self.usage_unknown=True
            if self.usage_unknown:raise DecisionFailure('unknown_usage_stop')
            if any(m['type']=='refusal' for m in response['messages']):raise DecisionFailure('model_refusal')
            if response['finish_reason']!='stop':raise DecisionFailure('incomplete_response')
            if self.actual_input+self.actual_output>self.budget.total_tokens:raise DecisionFailure('actual_token_budget_exceeded')
            messages=response['messages']
            if len(messages)!=1 or messages[0]['type']!='output_text':raise DecisionFailure('invalid_message')
            value=self.check_action(strict_json(messages[0]['text']),state)
            record['status']='valid_action';record['action']=value
            self.last_status='valid_action'
            return value
        except Exception as exc:
            code=str(exc) if isinstance(exc,DecisionFailure) else type(exc).__name__
            self.last_status='invalid_action' if isinstance(exc,DecisionFailure) and code not in ('missing_credentials','model_refusal','incomplete_response','actual_token_budget_exceeded') else 'request_failed'
            record.update(status='failed',error=code)
            if record['usage'] is None:self.usage_unknown=True
            raise DecisionFailure(code) from None
        finally:
            if diagnostics.get('request_attempted') and not self.simulation:self.real_attempts+=1
            record['transport']={k:diagnostics.get(k) for k in ('request_attempted','phase','http_status','request_id')}
            record['latency_seconds']=round(time.monotonic()-started,3)
            self.records.append(record)
            if path:write(path,record)
