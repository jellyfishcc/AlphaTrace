"""No network/real credentials. Qwen responses below are explicitly synthetic."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_stage4b1 as fixtures
from tracelab.agent import investigate
from tracelab.qwen_decider import QwenDecider,ReplayTransport,LiveBailianTransport,ExportScope,Budget,DecisionFailure


def reply(action=None,*,content=None,finish='stop',usage=True,refusal=None):
    raw={'model':'qwen-plus','choices':[{'finish_reason':finish,'message':{'content':content if content is not None else json.dumps(action,ensure_ascii=False)}}]}
    if usage:raw['usage']={'prompt_tokens':100,'completion_tokens':20}
    if refusal:raw['choices'][0]['message']['refusal']=refusal
    return raw


class QwenTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.InterfaceTests();f.setUp();self.payload=f.payload;self.analysis=f.answer
        self.scope=ExportScope(frozenset({'operating_cashflow'}),frozenset({'NEW'}),'offline_test_only')
        self.state={'goal':'调查现金流变化','questions':['现金流发生什么变化？'],'history':[],
                    'remaining':{'rounds':6,'tool_calls':4}}
        self.stop={'action':'stop','arguments':{'reason':'证据不足，无法进一步解释'}}

    def decider(self,responses,**kw):return QwenDecider(self.payload,self.scope,ReplayTransport(responses),**kw)

    def run_agent(self,responses,**kw):
        decider=self.decider(responses,**kw)
        with tempfile.TemporaryDirectory() as d,patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('tracelab.bailian.configuration',side_effect=AssertionError('real credentials forbidden')):
            out=Path(d)/'run';result=investigate(self.payload,{'signals':[],'investigation_tasks':[]},decider,out)
            manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            events=[json.loads(s) for s in (out/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        return result,decider,manifest,events

    def test_legal_fact_and_search_actions(self):
        actions=[{'action':'fact_get','arguments':{'fact_id':'operating_cashflow'}},
                 {'action':'search','arguments':{'metric_id':'operating_cashflow'}},self.stop]
        result,d,_,_=self.run_agent([reply(a) for a in actions])
        self.assertEqual(result['status'],'insufficient_evidence');self.assertEqual(d.attempts,3)
        context=json.loads(d.records[1]['request']['messages'][1]['content'])
        self.assertEqual(context['queried_facts'][0]['amounts']['change']['元'],'1.01')
        self.assertEqual(context['history'][0]['action'],'fact_get')
        self.assertEqual(context['remaining']['tool_calls'],3)

    def test_invalid_json_and_duplicate_keys(self):
        for content in ('{"action":','[]','{"action":"list","action":"stop","arguments":{}}','```json\n{}\n```'):
            result,d,_,_=self.run_agent([reply(content=content)])
            self.assertEqual(result['status'],'validation_failed');self.assertEqual(d.attempts,1)

    def test_unknown_tool_types_fields_and_paths(self):
        for action in [{'action':'exec','arguments':{'code':'print(1)'}},
                       {'action':'get','arguments':{'evidence_id':'../../file'}},
                       {'action':'fact_get','arguments':{'fact_id':123}},
                       {'action':'facts_list','arguments':{'skip_validation':True}},
                       {'action':'search','arguments':{'question_index':True}},
                       {'action':'get','arguments':{}},
                       {'action':'stop','arguments':{'reason':' '}}]:
            r,d,_,_=self.run_agent([reply(action)])
            self.assertEqual(r['status'],'validation_failed');self.assertEqual(r['tool_calls'],0)

    def test_disputed_and_unapproved_projects(self):
        for key in ('cash_26','cash_27','fair_value_income','fee_income','net_profit'):
            r,_,_,_=self.run_agent([reply({'action':'fact_get','arguments':{'fact_id':key}})])
            self.assertIn('unauthorized_fact',r['errors'])
        with self.assertRaises(ValueError):QwenDecider(self.payload,ExportScope(frozenset({'fake'}),frozenset(),'test'),ReplayTransport([]))

    def test_repeat_tool_stops_without_third_request(self):
        action={'action':'get','arguments':{'evidence_id':'NEW'}}
        r,d,_,_=self.run_agent([reply(action),reply(action),reply(self.stop)])
        self.assertIn('repeated_action',r['errors']);self.assertEqual(d.attempts,2);self.assertEqual(r['tool_calls'],1)

    def test_timeout_no_retry_unknown_cost(self):
        r,d,m,events=self.run_agent([TimeoutError('sensitive internal text'),reply(self.stop)])
        self.assertEqual(d.attempts,1);self.assertFalse(r['usage_known']);self.assertIsNone(r['actual_total_tokens'])
        self.assertIsNone(r['cost']);self.assertFalse(r['llm_called']);self.assertTrue(m['simulation'])
        self.assertNotIn('sensitive internal text',json.dumps(d.records))
        with self.assertRaisesRegex(DecisionFailure,'no_retry'):d.decide(self.state)

    def test_refusal_and_truncation(self):
        for response in (reply(refusal='不能回答'),reply(content='{"action":',finish='length')):
            r,d,_,_=self.run_agent([response]);self.assertEqual(r['status'],'validation_failed');self.assertEqual(d.attempts,1)

    def test_request_and_token_budgets(self):
        action={'action':'list','arguments':{}}
        r,d,_,_=self.run_agent([reply(action),reply(self.stop)],budget=Budget(max_requests=1))
        self.assertEqual(d.attempts,1);self.assertIn('request_budget_exhausted',r['errors'])
        for budget in (Budget(total_tokens=1),Budget(max_input_bytes=1)):
            r,d,_,_=self.run_agent([reply(self.stop)],budget=budget)
            self.assertEqual(d.attempts,0);self.assertFalse(r['llm_called'])

    def test_actual_usage_over_budget_and_missing_usage(self):
        raw=reply(self.stop);raw['usage']['prompt_tokens']=120001
        r,_,_,_=self.run_agent([raw]);self.assertIn('actual_token_budget_exceeded',r['errors'])
        action={'action':'list','arguments':{}}
        r,d,_,_=self.run_agent([reply(action,usage=False),reply(self.stop)])
        self.assertEqual(d.attempts,1);self.assertIn('unknown_usage_stop',r['errors'])

    def test_explain_still_checks_amount_quote_and_retrieval(self):
        get={'action':'get','arguments':{'evidence_id':'NEW'}}
        for error in ('amount','quote','unretrieved'):
            answer=copy.deepcopy(self.analysis)
            if error=='amount':answer['claims'][0]['amounts']=[{'fact_id':'operating_cashflow','field':'change','unit':'元','value':'999'}]
            if error=='quote':answer['claims'][0]['citations'][0]['quote']='伪造引用'
            steps=[] if error=='unretrieved' else [reply(get)]
            r,_,_,_=self.run_agent(steps+[reply({'action':'explain','arguments':{'analysis':answer}})])
            self.assertEqual(r['status'],'validation_failed')

    def test_valid_explain_only_pending_human(self):
        steps=[reply({'action':'get','arguments':{'evidence_id':'NEW'}}),reply({'action':'explain','arguments':{'analysis':self.analysis}})]
        r,_,_,_=self.run_agent(steps)
        self.assertEqual(r['status'],'pending_human_review');self.assertTrue(r['manual_review'])

    def test_stop_and_mode_logs(self):
        r,d,m,events=self.run_agent([reply(self.stop)])
        self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(r['decision_mode'],'qwen_replay')
        self.assertFalse(m['llm_called']);self.assertEqual(r['reported_total_tokens'],120)
        self.assertIsNone(r['actual_total_tokens'])
        self.assertTrue(any(e['event']=='model_decision' for e in events))

    def test_input_scope_no_internal_or_all_amounts(self):
        d=self.decider([reply(self.stop)])
        self.state['private_document']='INTERNAL_DO_NOT_EXPORT';self.state['facts']=self.payload['facts']
        context=d.context(self.state)
        self.assertNotIn('INTERNAL_DO_NOT_EXPORT',json.dumps(context))
        self.assertEqual(context['queried_facts'],[])
        self.assertNotIn('amounts',json.dumps(context['fact_catalog']))
        self.assertNotIn('source_contract',context)

    def test_omissions_are_visible(self):
        d=self.decider([]);d.evidence['NEW']['text']='原文'*2000
        self.state['history']=[{'action':'get','arguments':{'evidence_id':'NEW'},'result':self.payload['evidence'][0]}]
        context=d.context(self.state)
        self.assertGreater(context['queried_evidence'][0]['omitted_characters'],0)

    def test_payload_immutable_and_hard_budget_limits(self):
        before=copy.deepcopy(self.payload)
        self.run_agent([reply(self.stop)])
        self.assertEqual(self.payload,before)
        for kwargs in ({'max_requests':7},{'max_output_tokens':3001},{'timeout_seconds':181},{'total_tokens':True}):
            with self.assertRaises(ValueError):Budget(**kwargs)

    def test_live_transport_reuses_client_only_with_synthetic_config(self):
        from tracelab.bailian import Config
        with self.assertRaises(ValueError):LiveBailianTransport()
        diagnostics={}
        with patch('tracelab.bailian.configuration',return_value=Config('synthetic-test','https://example.test/compatible-mode/v1','qwen-plus',{})),patch('tracelab.stage3.call_api',return_value=(reply(self.stop),'fake-id')) as call:
            LiveBailianTransport(authorized=True).send({'model':'qwen-plus'},90,diagnostics)
        self.assertTrue(diagnostics['request_attempted']);call.assert_called_once()

    def test_real_flags_without_network_in_test_double(self):
        class SyntheticLiveFailure:
            simulation=False # Test state reporting only, never real transport.
            def send(self,body,timeout,diagnostics):
                diagnostics.update(request_attempted=True,phase='connect_or_wait_headers')
                raise TimeoutError()
        d=QwenDecider(self.payload,self.scope,SyntheticLiveFailure())
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('network forbidden')):
            r=investigate(self.payload,{'signals':[],'investigation_tasks':[]},d,Path(tmp)/'run')
            self.assertFalse(r['simulation']);self.assertTrue(r['llm_called']);self.assertEqual(r['real_request_attempts'],1)
            self.assertIsNone(r['cost']);self.assertFalse(r['usage_known'])

    def test_rate_limit_safe_failure(self):
        from urllib.error import HTTPError
        r,d,_,_=self.run_agent([HTTPError('https://example.test',429,'private',{},None)])
        self.assertEqual(d.attempts,1);self.assertIn('HTTPError',r['errors'])
        self.assertEqual(d.records[0]['transport']['http_status'],429)
