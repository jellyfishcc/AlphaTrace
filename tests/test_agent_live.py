"""Offline safety checks: real transport and credential access are blocked."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tracelab import agent_live
from tracelab.agent import LocalEvidence, LocalFacts, investigate
from tracelab.qwen_decider import QwenDecider, ReplayTransport, ExportScope, LiveBailianTransport, DecisionFailure
from tracelab.bailian import Config

SOURCE=Path('outputs/final_revision/20261017T093152-d80de1cefa')
PREFLIGHT=Path('outputs/agent_preflight/20261017T093813-c22073fa16/preflight.json')
SCOPE=PREFLIGHT.with_name('export_scope.json')


class LiveEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():raise unittest.SkipTest('private revised snapshot unavailable')
        with patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('tracelab.bailian.configuration',side_effect=AssertionError('key read forbidden')):
            cls.payload,cls.audit=agent_live.prepare(SOURCE,PREFLIGHT,SCOPE)

    def test_scoped_tools_preserve_trust_and_reject_other_ids(self):
        facts=LocalFacts(self.payload);evidence=LocalEvidence(self.payload)
        self.assertEqual({f['fact_id'] for f in facts.list()},set(agent_live.FACTS))
        self.assertEqual({e['evidence_id'] for e in evidence.list()},set(agent_live.EVIDENCE))
        for fid in ('fair_value_income','cash_26','cash_27','bill_deposits'):
            with self.assertRaises(ValueError):facts.get(fid)
        with self.assertRaises(ValueError):evidence.get('E19')
        self.assertTrue({e['evidence_id'] for e in evidence.search(metric_id='operating_cashflow')}<=set(agent_live.EVIDENCE))
        f=facts.get('net_profit');f['amounts'].clear()
        self.assertTrue(facts.get('net_profit')['amounts'])

    def test_default_entry_never_creates_transport(self):
        with patch.object(agent_live,'prepare',return_value=(self.payload,self.audit)),patch.object(agent_live,'LiveBailianTransport',side_effect=AssertionError('live forbidden')):
            self.assertEqual(agent_live.main(['--stage2-run',str(SOURCE),'--preflight',str(PREFLIGHT),'--scope',str(SCOPE)]),0)

    def test_authorization_claim_is_single_use(self):
        with tempfile.TemporaryDirectory() as d:
            agent_live.claim_once(d,'offline-test',{'simulation':True})
            with self.assertRaises(FileExistsError):agent_live.claim_once(d,'offline-test',{})
            with self.assertRaises(ValueError):agent_live.claim_once(d,'../path',{})

    def test_changed_snapshot_rejected_before_loading(self):
        scope=json.loads(SCOPE.read_text(encoding='utf-8'));scope['source_manifest_sha256']='bad'
        with tempfile.TemporaryDirectory() as d,patch.object(agent_live,'load_agent_payload',side_effect=AssertionError('must reject first')):
            p=Path(d)/'scope.json';p.write_text(json.dumps(scope),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'snapshot_changed'):agent_live.prepare(SOURCE,PREFLIGHT,p)

    def test_endpoint_change_never_sends(self):
        fake=Config('synthetic','https://example.com/compatible-mode/v1','qwen-plus',{})
        with patch('tracelab.bailian.configuration',return_value=fake),patch('tracelab.stage3.call_api',side_effect=AssertionError('must not send')):
            with self.assertRaisesRegex(DecisionFailure,'endpoint_changed'):
                LiveBailianTransport(authorized=True,expected_endpoint='https://different.example/chat/completions').send({'model':'qwen-plus'},90,{})

    def test_replay_scoped_context_and_safe_stop(self):
        actions=[{'action':'search','arguments':{'metric_id':'operating_cashflow'}},
                 {'action':'stop','arguments':{'reason':'模拟证据不足'}}]
        replies=[{'model':'qwen-plus','usage':{'prompt_tokens':100,'completion_tokens':20},
            'choices':[{'finish_reason':'stop','message':{'content':json.dumps(a,ensure_ascii=False)}}]} for a in actions]
        decider=QwenDecider(self.payload,ExportScope(frozenset(agent_live.FACTS),frozenset(agent_live.EVIDENCE),'offline'),ReplayTransport(replies),budget=agent_live.BUDGET,initial_fact_ids=agent_live.FACTS)
        with tempfile.TemporaryDirectory() as d,patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('tracelab.bailian.configuration',side_effect=AssertionError('key read forbidden')):
            result=investigate(self.payload,{'signals':[{'id':'goal','description':agent_live.GOAL}]},decider,Path(d)/'run',5,4)
        self.assertEqual(result['status'],'insufficient_evidence');self.assertTrue(result['simulation']);self.assertFalse(result['llm_called'])
        self.assertEqual(result['model_requests'],2)
        context=json.loads(decider.records[1]['request']['messages'][1]['content'])
        self.assertEqual({f['fact_id'] for f in context['initial_facts']},set(agent_live.FACTS))
        self.assertTrue({e['evidence_id'] for e in context['queried_evidence']}<=set(agent_live.EVIDENCE))
        self.assertNotIn('conflicts.json',json.dumps(context));self.assertNotIn('.docx',json.dumps(context))


if __name__=='__main__':unittest.main()
