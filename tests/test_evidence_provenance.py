"""Actual historical requests replayed unchanged; successful variants are synthetic."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tracelab.agent import investigate
from tracelab.qwen_decider import QwenDecider,ReplayTransport,ExportScope,Budget
from test_qwen_decider import reply

ROOT=Path('outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation')
class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.payload=json.loads((ROOT/'input.json').read_text(encoding='utf-8'))
        self.plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
        self.actions=[json.loads((ROOT/f'decisions/{i:02d}.json').read_text(encoding='utf-8'))['action'] for i in range(1,4)]
        self.scope=ExportScope(frozenset(f['fact_id'] for f in self.payload['facts']),frozenset(e['evidence_id'] for e in self.payload['evidence']),'offline_only')

    def run_actions(self,actions):
        responses=[reply(a) for a in actions]
        if actions is self.actions:
            responses=[]
            for i in range(1,4):
                saved=json.loads((ROOT/f'decisions/{i:02d}.json').read_text(encoding='utf-8'))
                responses.append(dict(usage={'prompt_tokens':saved['usage']['input_tokens'],'completion_tokens':saved['usage']['output_tokens']},choices=[dict(finish_reason=saved['response']['finish_reason'],message={'content':saved['response']['messages'][0]['text']})]))
        d=QwenDecider(self.payload,self.scope,ReplayTransport(responses),budget=Budget(max_requests=5),initial_fact_ids=tuple(self.scope.fact_ids))
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('no network')),patch('tracelab.bailian.configuration',side_effect=AssertionError('no key')):
            r=investigate(self.payload,self.plan,d,Path(tmp)/'run',5,4)
            p=Path(tmp)/'run/evidence_precheck.json'
            check=json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
        return r,d,check

    def clean_explain(self):
        evidence={e['evidence_id']:e for e in self.payload['evidence']}
        return dict(action='explain',arguments={'analysis':dict(claims=[dict(kind='hypothesis',statement='待验证：利润与现金流变化是否存在经营关联',metric_ids=['net_profit','operating_cashflow'],citations=[dict(evidence_id=k,quote=evidence[k]['text']) for k in ('F_net_profit','F_operating_cashflow')],amounts=[],accounting_links=[],comparison_basis='yoy',support_limit='仅确认相关事实，不能证明经营因果')],questions=['是否存在支持经营原因的进一步披露？'])})

    def test_historical_context_catalog_is_not_original_text(self):
        for i in range(1,4):
            d=json.loads((ROOT/f'decisions/{i:02d}.json').read_text(encoding='utf-8'));c=json.loads(d['request']['messages'][1]['content'])
            self.assertNotIn('F_net_profit',d['request']['messages'][0]['content'])
            self.assertIn('F_net_profit',[e['evidence_id'] for e in c['evidence_catalog']])
            self.assertNotIn('F_net_profit',[e['evidence_id'] for e in c['queried_evidence']])
            self.assertEqual(next(f for f in c['initial_facts'] if f['fact_id']=='net_profit')['retrieved_source_quotes'],[])

    def test_unchanged_historical_replay_rejected_before_validation(self):
        r,d,c=self.run_actions(self.actions)
        self.assertEqual(r['status'],'validation_failed')
        self.assertEqual(r['errors'],['explain_evidence_precheck_failed'])
        self.assertIn('F_net_profit',c['ineligible_citation_ids'])
        self.assertEqual(c['missing_core_metric_ids'],['net_profit'])
        context=json.loads(d.records[2]['request']['messages'][1]['content'])
        self.assertEqual(context['evidence_progress']['provided_evidence_ids'],[])
        self.assertNotEqual(context['progress']['next_step'],'explain_or_stop')
        self.assertEqual(d.attempts,3)

    def test_fetch_missing_core_then_full_validation_success(self):
        steps=self.actions[:2]+[dict(action='get',arguments={'evidence_id':'F_net_profit'}),self.clean_explain()]
        r,d,c=self.run_actions(steps)
        self.assertTrue(c['ready']);self.assertEqual(r['status'],'pending_human_review')
        self.assertTrue(r['manual_review']);self.assertEqual(r['tool_calls'],3)
        context=json.loads(d.records[-1]['request']['messages'][1]['content'])
        self.assertIn('F_net_profit',context['evidence_progress']['visible_evidence_ids'])
        self.assertEqual(context['evidence_progress']['provided_evidence_ids'],[])
        self.assertIn('F_net_profit',r['retrieved_evidence_ids'])

    def test_search_net_profit_also_grants_eligibility(self):
        steps=self.actions[:2]+[dict(action='search',arguments={'metric_id':'net_profit'}),self.clean_explain()]
        r,_,c=self.run_actions(steps)
        self.assertTrue(c['ready']);self.assertEqual(r['status'],'pending_human_review')

    def test_missing_cashflow_blocks_even_if_claim_omits_it(self):
        a=self.clean_explain();a['arguments']['analysis']['claims'][0]['metric_ids']=['net_profit'];a['arguments']['analysis']['claims'][0]['citations']=a['arguments']['analysis']['claims'][0]['citations'][:1]
        r,_,c=self.run_actions([dict(action='get',arguments={'evidence_id':'F_net_profit'}),a])
        self.assertEqual(c['missing_core_metric_ids'],['operating_cashflow']);self.assertEqual(r['status'],'validation_failed')

    def test_unauthorized_citation_rejected(self):
        a=self.clean_explain();a['arguments']['analysis']['claims'][0]['citations'][0]['evidence_id']='OUTSIDE'
        r,_,_=self.run_actions(self.actions[:2]+[a]);self.assertIn('unauthorized_evidence',r['errors'])

    def test_missing_core_stop_keeps_gap_and_audit(self):
        r,_,_=self.run_actions(self.actions[:2]+[dict(action='stop',arguments={'reason':'已检索现金流并读取披露，仍缺少净利润原文证据。'})])
        self.assertEqual(r['status'],'insufficient_evidence');self.assertIn('净利润',r['evidence_gap'])
        self.assertEqual(r['evidence_progress']['missing_core_metric_ids'],['net_profit'])

    def test_initial_fact_source_never_becomes_provided_or_retrieved(self):
        r,d,c=self.run_actions([self.clean_explain()])
        ctx=json.loads(d.records[0]['request']['messages'][1]['content'])
        self.assertEqual(ctx['evidence_progress']['provided_evidence_ids'],[])
        self.assertEqual(r['retrieved_evidence_ids'],[])
        self.assertFalse(c['ready'])

    def test_source_hash_tampering_still_rejected(self):
        self.payload['evidence'][0]['text']+='tampered'
        with self.assertRaisesRegex(ValueError,'unknown_or_unverified_fact'):self.run_actions(self.actions)
