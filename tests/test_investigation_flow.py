"""Phase 3 offline flow tests. Success responses are explicitly synthetic."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_evidence_provenance as fixtures
from tracelab.agent import investigate
from tracelab.investigation import prepare_scoped_investigation
from tracelab.agent_live import GOAL, BUDGET, FACTS
from tracelab.qwen_decider import QwenDecider, ReplayTransport
from test_qwen_decider import reply

class FlowTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.EvidenceTests();self.f.setUp()
        self.p=self.f.payload;self.plan=prepare_scoped_investigation(self.p,GOAL)
    def get(self,eid):return dict(action='get',arguments={'evidence_id':eid})
    def ready(self):return [self.get(e) for e in ('F_net_profit','F_operating_cashflow','E07_28')]
    def run_steps(self,steps,responses=None):
        d=QwenDecider(self.p,self.f.scope,ReplayTransport(responses or [reply(a) for a in steps]),budget=BUDGET,initial_fact_ids=FACTS)
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('no network')),patch('tracelab.bailian.configuration',side_effect=AssertionError('no key')):
            out=Path(tmp)/'run';r=investigate(self.p,self.plan,d,out,5,4)
            pre=json.loads((out/'evidence_precheck.json').read_text(encoding='utf-8')) if (out/'evidence_precheck.json').exists() else None
        return r,d,pre
    def test_early_explain_blocks_without_retry(self):
        r,d,p=self.run_steps([self.f.clean_explain()])
        self.assertEqual(d.attempts,1);self.assertFalse(p['ready']);self.assertEqual(r['termination_category'],'explain_precheck_rejected')
    def test_progress_guides_finite_continued_investigation(self):
        r,d,p=self.run_steps(self.ready()+[self.f.clean_explain()])
        c=json.loads(d.records[1]['request']['messages'][1]['content'])['investigation_task_progress']
        self.assertEqual(c['next_step'],'investigate_or_stop');self.assertNotIn('F_net_profit',c['candidate_evidence_ids'])
        self.assertEqual(d.attempts,4);self.assertTrue(p['ready'])
    def test_fact_updates_after_source(self):
        r,_,_=self.run_steps([self.get('F_net_profit'),dict(action='stop',arguments={'reason':'仍缺现金流证据'})])
        self.assertEqual(r['investigation_task_progress']['tasks'][0]['status'],'answered')
    def test_two_facts_not_divergence(self):
        r,_,p=self.run_steps(self.ready()[:2]+[self.f.clean_explain()])
        self.assertFalse(p['ready']);self.assertEqual(r['investigation_task_progress']['tasks'][3]['status'],'evidence_gap')
    def test_limited_explain_enters_validator_and_review(self):
        r,_,_=self.run_steps(self.ready()+[self.f.clean_explain()])
        self.assertEqual(r['status'],'pending_human_review');self.assertEqual(r['termination_category'],'human_review_required');self.assertTrue(r['manual_review'])
    def test_divergence_gap_not_permanent_explain_block(self):
        r,_,p=self.run_steps(self.ready()+[self.f.clean_explain()])
        self.assertTrue(p['ready']);self.assertEqual(r['investigation_task_progress']['tasks'][3]['status'],'evidence_gap')
    def test_gap_task_need_not_answered(self):
        r,_,_=self.run_steps(self.ready()+[self.f.clean_explain()])
        self.assertEqual(r['investigation_task_progress']['tasks'][4]['status'],'evidence_gap');self.assertFalse(r['investigation_task_progress']['complete'])
    def test_stop_preserves_missing_tasks(self):
        r,_,_=self.run_steps([dict(action='stop',arguments={'reason':'授权范围内缺少解释背离的证据'})])
        self.assertEqual(r['termination_category'],'insufficient_evidence');self.assertTrue(r['task_evidence_gaps'])
    def test_missing_questions_blocks_limited_explain(self):
        a=self.f.clean_explain();a['arguments']['analysis']['questions']=[]
        r,_,p=self.run_steps(self.ready()+[a]);self.assertFalse(p['ready']);self.assertEqual(r['status'],'validation_failed')
    def test_validator_error_kept_separate_from_gap(self):
        a=self.f.clean_explain();a['arguments']['analysis']['claims'][0]['citations'][0]['quote']='伪造原文'
        r,_,p=self.run_steps(self.ready()+[a]);self.assertTrue(p['ready']);self.assertEqual(r['termination_category'],'validator_rejected');self.assertTrue(r['errors']);self.assertIsNone(r['evidence_gap'])
    def test_budget_stop_preserves_unresolved(self):
        r,d,_=self.run_steps(self.ready()+[self.get('F_FINAL_cash_2'),self.get('F_FINAL_cash_6')])
        self.assertEqual(r['termination_category'],'budget_exhausted');self.assertEqual(r['tool_calls'],4);self.assertLessEqual(d.attempts,5)
        self.assertTrue(r['investigation_task_progress']['tasks'][3]['budget_exhausted'])
    def test_malformed_response_is_not_business_stop(self):
        response=reply(self.f.clean_explain());response['choices'][0]['message']['content']='not json'
        r,d,_=self.run_steps([],responses=[response]);self.assertEqual(d.attempts,1);self.assertEqual(r['termination_category'],'system_or_decision_error')
    def test_duplicate_tool_still_rejected(self):
        r,d,_=self.run_steps([self.get('F_net_profit'),self.get('F_net_profit')])
        self.assertIn('repeated_action',r['errors']);self.assertEqual(r['tool_calls'],1)
    def test_historical_responses_unchanged_still_rejected(self):
        responses=[]
        for i in range(1,4):
            s=json.loads((fixtures.ROOT/f'decisions/{i:02d}.json').read_text(encoding='utf-8'))
            responses.append(dict(usage={'prompt_tokens':s['usage']['input_tokens'],'completion_tokens':s['usage']['output_tokens']},choices=[dict(finish_reason=s['response']['finish_reason'],message={'content':s['response']['messages'][0]['text']})]))
        r,d,p=self.run_steps([],responses=responses)
        self.assertEqual(r['status'],'validation_failed');self.assertEqual(d.attempts,3);self.assertIn('net_profit',p['missing_core_metric_ids'])
    def test_empty_tasks_cannot_admit_explain(self):
        self.plan['investigation_tasks']=[]
        r,_,p=self.run_steps(self.ready()+[self.f.clean_explain()])
        self.assertTrue(p['planning_gap']);self.assertEqual(r['termination_category'],'explain_precheck_rejected')
    def test_unavailable_source_guidance_is_stop(self):
        for t in self.plan['investigation_tasks']:t['candidate_evidence_ids']=[]
        r,d,_=self.run_steps([dict(action='stop',arguments={'reason':'缺少可继续取得的合格来源'})])
        ctx=json.loads(d.records[0]['request']['messages'][1]['content'])
        self.assertEqual(ctx['progress']['next_step'],'stop_with_evidence_gap')
        self.assertTrue(r['task_evidence_gaps'])
    def test_success_at_last_request_is_not_budget_stop(self):
        r,d,_=self.run_steps(self.ready()+[self.get('F_FINAL_cash_2'),self.f.clean_explain()])
        self.assertEqual(d.attempts,5);self.assertEqual(r['termination_category'],'human_review_required')
        self.assertFalse(r['investigation_task_progress']['tasks'][3]['budget_exhausted'])
