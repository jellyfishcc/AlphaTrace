"""Synthetic replay paths and a redacted historical failure, never model success."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_stage4b1 as fixtures
from test_qwen_decider import reply
from tracelab.agent import investigate
from tracelab.qwen_decider import QwenDecider, ReplayTransport, ExportScope, Budget, DecisionFailure
from tracelab.source_contract import digest


class ProgressTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.InterfaceTests();f.setUp()
        self.payload=f.payload;self.analysis=f.answer
        self.scope=ExportScope(frozenset({'operating_cashflow'}),frozenset({'NEW'}),'synthetic_only')
        self.state=dict(goal='核查现金流',questions=[],history=[],remaining=dict(rounds=5,tool_calls=4))
        self.search=dict(action='search',arguments={'metric_id':'operating_cashflow'})
        self.get=dict(action='get',arguments={'evidence_id':'NEW'})
        self.stop=dict(action='stop',arguments={'reason':'已检索现金流证据并读取原文，但缺少足以量化经营原因的明细。'})

    def decider(self,actions=(),initial=('operating_cashflow',),budget=None):
        return QwenDecider(self.payload,self.scope,ReplayTransport([reply(a) for a in actions]),
                           initial_fact_ids=initial,budget=budget or Budget(max_requests=5))

    def run_path(self,actions,initial=('operating_cashflow',)):
        d=self.decider(actions,initial)
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('network forbidden')), \
             patch('tracelab.bailian.configuration',side_effect=AssertionError('key forbidden')), \
             patch('tracelab.stage3.call_api',side_effect=AssertionError('API forbidden')):
            r=investigate(self.payload,{'signals':[]},d,Path(tmp)/'run',5,4)
        return r,d

    def test_path_a_initial_search_get_explain(self):
        r,d=self.run_path([self.search,self.get,dict(action='explain',arguments={'analysis':self.analysis})])
        self.assertEqual(r['status'],'pending_human_review');self.assertTrue(r['manual_review'])
        self.assertEqual(r['tool_calls'],2);self.assertEqual(r['model_requests'],3)
        self.assertTrue(r['simulation']);self.assertFalse(r['llm_called'])
        contexts=[json.loads(r['request']['messages'][1]['content']) for r in d.records]
        self.assertEqual([c['progress']['next_step'] for c in contexts],['search_or_stop','get_or_stop','explain_or_stop'])
        self.assertEqual(contexts[0]['progress']['fact_get_allowed_ids'],[])
        self.assertEqual(contexts[1]['history'][0]['result_evidence_ids'],['NEW'])

    def test_path_b_initial_search_get_stop_gap(self):
        r,_=self.run_path([self.search,self.get,self.stop])
        self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(r['errors'],[])
        self.assertEqual([a['action'] for a in r['retrieval_audit']],['search','get'])
        self.assertEqual(r['retrieval_audit'][0]['arguments'],self.search['arguments'])
        self.assertIn('缺少',r['evidence_gap'])

    def test_empty_search_scope_preserved(self):
        search=dict(action='search',arguments={'query':'no_such_disclosure','metric_id':'operating_cashflow'})
        r,d=self.run_path([search,self.stop])
        self.assertEqual(r['retrieval_audit'][0]['evidence_ids'],[])
        c=json.loads(d.records[1]['request']['messages'][1]['content'])
        self.assertEqual(c['history'][0]['result_count'],0)
        self.assertEqual(c['progress']['searches'][0]['arguments'],search['arguments'])

    def test_initial_fact_requery_fails_not_success_or_retry(self):
        r,d=self.run_path([dict(action='fact_get',arguments={'fact_id':'operating_cashflow'}),self.stop])
        self.assertEqual(r['status'],'validation_failed');self.assertEqual(r['errors'],['fact_already_available'])
        self.assertEqual(r['tool_calls'],0);self.assertEqual(d.attempts,1)
        with self.assertRaisesRegex(DecisionFailure,'failed_run_no_retry'):d.decide(self.state)

    def test_missing_necessary_fact_can_be_queried(self):
        r,_=self.run_path([dict(action='fact_get',arguments={'fact_id':'operating_cashflow'}),self.search,self.get,self.stop],initial=())
        self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(r['tool_calls'],3)

    def test_reserve_tool_and_decision_capacity(self):
        for remaining in (dict(rounds=5,tool_calls=2),dict(rounds=3,tool_calls=4)):
            d=self.decider(initial=());state=copy.deepcopy(self.state);state['remaining']=remaining
            with self.assertRaisesRegex(DecisionFailure,'evidence_budget_reserved'):
                d.check_action(dict(action='fact_get',arguments={'fact_id':'operating_cashflow'}),state)
        for remaining,code in [(dict(rounds=1,tool_calls=2),'terminal_decision_required'),
                               (dict(rounds=3,tool_calls=0),'tool_budget_exhausted')]:
            d=self.decider();state=copy.deepcopy(self.state);state['remaining']=remaining
            with self.assertRaisesRegex(DecisionFailure,code):d.check_action(self.search,state)
            self.assertEqual(d.check_action(self.stop,state),self.stop)

    def test_ledger_survives_detail_and_history_truncation(self):
        original=self.payload['facts'][0]
        ids=['operating_cashflow','cash_2','cash_6','net_profit']
        self.payload['facts']=[dict(copy.deepcopy(original),fact_id=k) for k in ids]
        self.payload['evidence'][0]['related_facts']=ids
        self.payload['source_contract']['facts']={f['fact_id']:digest(f) for f in self.payload['facts']}
        self.payload['source_contract']['evidence']['NEW']['evidence_sha256']=digest(self.payload['evidence'][0])
        self.scope=ExportScope(frozenset(ids),frozenset({'NEW'}),'synthetic_only')
        self.state['history']=[dict(action='fact_get',arguments={'fact_id':k},result={}) for k in ids]
        self.state['history'] += [dict(action='list',arguments={},result=[]) for _ in range(6)]
        c=self.decider(initial=()).context(self.state)
        self.assertEqual(set(c['progress']['queried_fact_ids']),set(ids))
        self.assertEqual(c['progress']['fact_get_allowed_ids'],[])
        self.assertEqual(len(c['queried_facts']),2)
        self.assertTrue(all(h['action']=='list' for h in c['history']))

    def test_historical_trace_documents_existing_facts_and_lost_details(self):
        data=json.loads(Path('tests/fixtures/agent_repeated_fact_failure.json').read_text(encoding='utf-8'))
        rounds=data['rounds']
        self.assertEqual([r['action']['arguments']['fact_id'] for r in rounds],['cash_2','cash_6','net_profit','operating_cashflow','cash_2'])
        self.assertTrue(all(len(r['initial_fact_ids'])==4 for r in rounds))
        self.assertEqual(rounds[-1]['queried_fact_ids'],['net_profit','operating_cashflow'])
        self.assertEqual(rounds[-1]['remaining']['tool_calls'],0)
        self.assertEqual(rounds[-1]['error'],'repeated_action')

    def test_repeated_and_unauthorized_actions_still_fail(self):
        for actions,code in [([self.get,self.get],'repeated_action'),
                ([dict(action='fact_get',arguments={'fact_id':'not_authorized'})],'unauthorized_fact'),
                ([dict(action='exec',arguments={})],'invalid_action_or_arguments')]:
            r,_=self.run_path(actions)
            self.assertEqual(r['status'],'validation_failed');self.assertIn(code,r['errors'])

    def test_bad_amount_and_unretrieved_quote_still_fail(self):
        answer=copy.deepcopy(self.analysis)
        answer['claims'][0]['amounts']=[dict(fact_id='operating_cashflow',field='change',unit='元',value='999')]
        for actions in ([self.get,dict(action='explain',arguments={'analysis':answer})],
                        [dict(action='explain',arguments={'analysis':self.analysis})]):
            r,_=self.run_path(actions)
            self.assertEqual(r['status'],'validation_failed');self.assertTrue(r['errors'])
