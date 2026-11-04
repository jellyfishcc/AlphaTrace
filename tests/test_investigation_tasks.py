"""Task contracts on read-only historical inputs; no live requests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_evidence_provenance as fixtures
from tracelab.investigation import prepare_scoped_investigation,select_tasks
from tracelab.evidence_progress import investigation_task_progress
from tracelab.agent import LocalEvidence,investigate
from tracelab import agent_live
from tracelab.qwen_decider import QwenDecider,ReplayTransport
from test_qwen_decider import reply

class TaskTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.EvidenceTests();self.f.setUp();self.p=self.f.payload
        self.plan=prepare_scoped_investigation(self.p,agent_live.GOAL)
    def history(self,*ids):
        tool=LocalEvidence(self.p)
        return [dict(action='get',arguments={'evidence_id':k},result=tool.get(k)) for k in ids]
    def progress(self,*ids,**kw):
        return investigation_task_progress(self.p,select_tasks(self.plan),self.history(*ids),**kw)
    def test_nonempty_scoped_planner(self):
        before=copy.deepcopy(self.p)
        self.assertEqual(len(self.plan['investigation_tasks']),5)
        self.assertIn('profit_down_cashflow_up',self.plan['detected_signal_ids'])
        self.assertEqual(self.p,before)
        self.assertNotIn('profit_chain',self.plan)
    def test_authorized_signal_matches(self):
        self.assertEqual(len(select_tasks(self.plan)),5)
        self.assertTrue(all(t['reason']=='authorized_goal' for t in select_tasks(self.plan)))
    def test_required_fact_survives_anomaly_filter(self):
        self.plan['signals']=[dict(id='profit_down_cashflow_up')]
        self.plan['investigation_tasks'][3]['reason']='profit_down_cashflow_up'
        self.assertEqual(len(select_tasks(self.plan)),5)
    def test_unretrieved_never_answered(self):
        r=self.progress();self.assertEqual(r['tasks'][0]['status'],'pending');self.assertFalse(r['complete'])
    def test_bound_fact_source_answers_fact_only(self):
        r=self.progress('F_net_profit');t=r['tasks'][0]
        self.assertEqual(t['status'],'answered');self.assertEqual(t['answer']['name'],'净利润')
        self.assertEqual(t['answer']['periods'],['2024','2025']);self.assertFalse(r['complete'])
    def test_cash_and_disclosure_do_not_answer_divergence(self):
        r=self.progress('F_operating_cashflow','E07_28')
        self.assertEqual(r['tasks'][1]['status'],'answered')
        self.assertEqual(r['tasks'][2]['status'],'answered')
        self.assertIn('主要系',r['tasks'][2]['answer']['quote'])
        self.assertEqual(r['tasks'][3]['status'],'evidence_gap')
    def test_empty_relations_unchanged(self):
        self.progress('F_net_profit','F_operating_cashflow','E07_28')
        self.assertEqual(self.p['analysis_contract']['accounting_relations'],[])
    def test_empty_plan_not_complete(self):
        r=investigation_task_progress(self.p,[],[])
        self.assertTrue(r['planning_gap']);self.assertFalse(r['complete'])
    def test_budget_does_not_complete_pending(self):
        r=self.progress(budget_exhausted=True)
        self.assertTrue(all(t['status']=='evidence_gap' for t in r['tasks']))
        self.assertTrue(all(t['budget_exhausted'] for t in r['tasks']))
    def test_three_states_and_gap_reasons(self):
        r=self.progress('F_net_profit')
        self.assertEqual({t['status'] for t in r['tasks']},{'pending','answered','evidence_gap'})
        self.assertTrue(r['tasks'][4]['unresolved_questions'])
    def test_identity_tamper_not_answered(self):
        next(f for f in self.p['facts'] if f['fact_id']=='net_profit')['name']='归母净利润'
        self.assertEqual(self.progress('F_net_profit')['tasks'][0]['status'],'evidence_gap')
    def test_actual_replay_writes_task_ledger_and_preserves_stop(self):
        actions=[dict(action='get',arguments={'evidence_id':'F_net_profit'}),dict(action='stop',arguments={'reason':'已核实净利润，仍缺现金流背离解释'})]
        d=QwenDecider(self.p,self.f.scope,ReplayTransport([reply(a) for a in actions]),budget=agent_live.BUDGET,initial_fact_ids=agent_live.FACTS)
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('no network')):
            out=Path(tmp)/'run';r=investigate(self.p,self.plan,d,out,5,4)
            ledger=json.loads((out/'task_progress.json').read_text(encoding='utf-8'))
        self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(d.attempts,2)
        self.assertEqual(ledger['tasks'][0]['status'],'answered');self.assertFalse(ledger['complete'])
    def test_live_entry_uses_scoped_plan_without_real_transport(self):
        audit=dict(configuration={'endpoint':'offline'},source_manifest_sha256='offline')
        with tempfile.TemporaryDirectory() as tmp,patch('tracelab.agent_live.prepare',return_value=(self.p,audit)),patch('tracelab.agent_live.check_free_tier_confirmation',create=True),patch('tracelab.cost_budget.check_free_tier_confirmation'),patch('tracelab.agent_live.LiveBailianTransport'),patch('tracelab.agent_live.QwenDecider'),patch('tracelab.agent_live.investigate',return_value={'status':'insufficient_evidence'}) as run,patch('socket.socket',side_effect=AssertionError('no network')):
            agent_live.main(['--stage2-run','unused','--preflight','unused','--scope','unused','--execute-real','--authorization-id','synthetic-offline','--confirm-free-tier-workspace','--output',tmp])
            plan=run.call_args.args[1]
            self.assertEqual(len(select_tasks(plan)),5)
            self.assertEqual(run.call_args.kwargs,dict(max_rounds=5,max_tools=4))

    def test_budget_exhaustion_in_actual_orchestrator_keeps_gap(self):
        actions=[dict(action='get',arguments={'evidence_id':eid}) for eid in ('F_net_profit','F_operating_cashflow','E07_28','E18','F_FINAL_cash_2')]
        d=QwenDecider(self.p,self.f.scope,ReplayTransport([reply(a) for a in actions]),budget=agent_live.BUDGET,initial_fact_ids=agent_live.FACTS)
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('no network')):
            r=investigate(self.p,self.plan,d,Path(tmp)/'run',5,4)
        self.assertLessEqual(d.attempts,5);self.assertEqual(r['tool_calls'],4)
        self.assertFalse(r['investigation_task_progress']['complete'])
        self.assertTrue(r['investigation_task_progress']['tasks'][3]['budget_exhausted'])
