"""Historical rejection replay; all changed variants are synthetic offline cases."""
import copy
import json
import unittest
import test_evidence_provenance as provenance
ROOT=provenance.ROOT
from tracelab.stage3 import validate
from tracelab.qwen_decider import QwenDecider, ReplayTransport, ExportScope

class CashflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture=provenance.EvidenceTests();self.fixture.setUp()
        self.payload=self.fixture.payload
        self.original=json.loads((ROOT/'analysis.json').read_text(encoding='utf-8'))
        self.evidence={e['evidence_id']:e for e in self.payload['evidence']}

    def response(self):
        c=copy.deepcopy(self.original['claims'][1])
        c.update(kind='accounting_fact',statement='现金流入分项增加',support_limit='仅为分项变动，不证明净额贡献',
                 metric_ids=['cash_2','cash_6'],accounting_links=[],
                 citations=[dict(evidence_id=k,quote=self.evidence[k]['text']) for k in ('F_FINAL_cash_2','F_FINAL_cash_6')])
        return dict(claims=[c],questions=['其他收支如何变化？'])

    def errors(self,r):return validate(r,self.payload)['errors']

    def test_original_replay_unchanged(self):
        result,d,check=self.fixture.run_actions(self.fixture.actions)
        self.assertEqual(result['status'],'validation_failed')
        self.assertEqual(d.attempts,3)
        errors=self.errors(self.original)
        self.assertIn('结论2金额未关联该条财务项目',errors)
        self.assertIn('结论2金额缺少同条结论中经核验的事实原始来源',errors)

    def test_only_metric_ids_fixed_still_rejected(self):
        r=copy.deepcopy(self.original);r['claims'][1]['metric_ids']+=['cash_2','cash_6']
        self.assertIn('结论2金额缺少同条结论中经核验的事实原始来源',self.errors(r))

    def test_correct_sources_and_change_pass(self):
        r=self.response()
        for a in r['claims'][0]['amounts']:
            self.assertFalse(any(a['value'] in q['quote'].replace(',','') for q in r['claims'][0]['citations']))
        self.assertEqual(self.errors(r),[])

    def test_qualified_amounts_through_agent(self):
        steps=self.fixture.actions[:2]+[dict(action='get',arguments={'evidence_id':'F_net_profit'}),
            dict(action='explain',arguments={'analysis':self.response()})]
        r,d,c=self.fixture.run_actions(steps)
        self.assertEqual(r['status'],'pending_human_review');self.assertTrue(c['ready'])

    def test_empty_relations_reject_links(self):
        r=self.response();r['claims'][0]['accounting_links']=[dict(target='operating_cashflow',component='cash_2',effect='increase')]
        self.assertIn('结论1会计层级或关系未获输入核验支持',self.errors(r))

    def test_qualitative_disclosure_without_links_passes(self):
        r=self.response();c=r['claims'][0]
        c.update(kind='disclosure_explanation',statement='年报披露经营现金流增长主要系相关现金流入增加',
                 metric_ids=['operating_cashflow'],amounts=[],citations=[dict(evidence_id='E07_28',quote=self.evidence['E07_28']['text'])])
        self.assertEqual(self.errors(r),[])

    def test_unverified_wrong_component_effect_or_missing_metric(self):
        # Synthetic contract tests only: never added to real input or treated as financial truth.
        rel=dict(target='cash_6',verified=True,components=[dict(component='cash_2',sign='1',effect='increase')])
        self.payload['analysis_contract']['accounting_relations']=[rel]
        for mode in ('unverified','component','effect','metric'):
            with self.subTest(mode=mode):
                rel['verified']=mode!='unverified'
                r=self.response();c=r['claims'][0]
                c['accounting_links']=[dict(target='cash_6',component='cash_2',effect='increase')]
                if mode=='component':c['accounting_links'][0]['component']='operating_cashflow'
                if mode=='effect':c['accounting_links'][0]['effect']='decrease'
                if mode=='metric':c['metric_ids']=['cash_2']
                self.assertTrue(any('会计' in e for e in self.errors(r)))

    def context(self):
        d=QwenDecider(self.payload,self.fixture.scope,ReplayTransport([]))
        return d.context(dict(goal='调查现金流',history=[],remaining={}))

    def test_context_explicit_empty(self):
        self.assertEqual(self.context()['accounting_relations'],[])

    def test_context_verified_authorized_only_no_closure(self):
        def relation(t,c,v=True):return dict(target=t,verified=v,components=[dict(component=c,sign='1',effect='increase')])
        self.payload['analysis_contract']['accounting_relations']=[relation('net_profit','cash_2'),relation('cash_2','cash_6'),
            relation('operating_cashflow','cash_6',False),relation('cash_16','cash_6'),relation('operating_cashflow','cash_7')]
        rel=self.context()['accounting_relations']
        self.assertEqual([(r['target'],r['components'][0]['component']) for r in rel],[('net_profit','cash_2'),('cash_2','cash_6')])
        self.assertTrue(all(r['verified'] is True for r in rel))

    def test_cash16_alias_rejected(self):
        r=self.response();r['claims'][0]['metric_ids'].append('cash_16')
        r['claims'][0]['amounts'][0]['fact_id']='cash_16'
        self.assertIn('结论1引用未知财务项目',self.errors(r))

    def test_source_or_fact_hash_tampering_rejected(self):
        for mode in ('fact','evidence'):
            with self.subTest(mode=mode):
                p=copy.deepcopy(self.payload)
                if mode=='fact':next(f for f in p['facts'] if f['fact_id']=='cash_2')['name']='tampered'
                else:next(e for e in p['evidence'] if e['evidence_id']=='F_FINAL_cash_2')['text']+='tampered'
                self.assertIn('结论1金额缺少同条结论中经核验的事实原始来源',validate(self.response(),p)['errors'])

    def test_related_facts_alone_not_amount_source(self):
        r=self.response();r['claims'][0]['citations']=[dict(evidence_id='E18',quote=self.evidence['E18']['text'])]
        self.assertIn('结论1金额缺少同条结论中经核验的事实原始来源',self.errors(r))

    def test_wrong_amount_still_rejected(self):
        r=self.response();r['claims'][0]['amounts'][0]['value']='1'
        self.assertIn('结论1金额、期间或单位与输入不一致',self.errors(r))

    def test_no_transitive_accounting_link(self):
        self.payload['analysis_contract']['accounting_relations']=[
            dict(target='operating_cashflow',verified=True,components=[dict(component='cash_6',sign='1',effect='increase')]),
            dict(target='cash_6',verified=True,components=[dict(component='cash_2',sign='1',effect='increase')])]
        r=self.response();c=r['claims'][0];c['metric_ids'].append('operating_cashflow')
        c['accounting_links']=[dict(target='operating_cashflow',component='cash_2',effect='increase')]
        self.assertIn('结论1会计层级或关系未获输入核验支持',self.errors(r))

    def test_related_tag_even_verified_does_not_replace_fact_source(self):
        from tracelab.source_contract import digest
        e=self.evidence['E07_28'];e['related_facts']+=['cash_2','cash_6']
        self.payload['source_contract']['evidence']['E07_28']['evidence_sha256']=digest(e)
        r=self.response();r['claims'][0]['citations']=[dict(evidence_id='E07_28',quote=e['text'])]
        errors=self.errors(r)
        self.assertNotIn('结论1财务项目缺少相关证据',errors)
        self.assertIn('结论1金额缺少同条结论中经核验的事实原始来源',errors)
