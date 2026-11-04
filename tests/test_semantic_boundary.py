"""Finite semantic boundaries, synthetic variants plus immutable historical replay."""
import copy
import unittest
import test_cashflow_relationship as fixtures
from tracelab.stage3 import validate
from tracelab.source_contract import digest

class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.CashflowTests();self.f.setUp();self.p=self.f.payload
    def fact(self,text='净利润下降',fid='net_profit'):
        e=next(e for e in self.p['evidence'] if e['evidence_id']=='F_net_profit')
        c=dict(kind='accounting_fact',statement=text,metric_ids=[fid],citations=[dict(evidence_id=e['evidence_id'],quote=e['text'])],amounts=[],support_limit='仅为财务事实',accounting_links=[],comparison_basis='yoy')
        return dict(claims=[c],questions=['仍需核查什么经营证据？'])
    def disclosure(self,text='年报披露现金流增长主要系相关收款增加',limit='主要原因已披露，完整贡献尚未核实'):
        r=self.fact();c=r['claims'][0];e=self.f.evidence['E07_28']
        c.update(kind='disclosure_explanation',statement=text,metric_ids=['operating_cashflow'],citations=[dict(evidence_id='E07_28',quote=e['text'])],support_limit=limit)
        return r
    def check(self,r):return validate(r,self.p)
    def test_correct_net(self):self.assertEqual(self.check(self.fact())['errors'],[])
    def test_wrong_parent_statement_correct_quote(self):
        for name in ('归母净利润','归属于母公司股东的净利润'):
            self.assertTrue(any('metric_scope_conflict' in e for e in self.check(self.fact(name+'下降'))['errors']))
    def test_equal_amount_not_equivalent(self):
        r=self.fact('本项金额等同于归母净利润');f=next(f for f in self.p['facts'] if f['fact_id']=='net_profit')
        r['claims'][0]['amounts']=[dict(fact_id='net_profit',field='current',unit='元',value=f['amounts']['current']['元'])]
        self.assertTrue(any('metric_scope_conflict' in e for e in self.check(r)['errors']))
    def test_correct_parent_own_synthetic_source(self):
        # Explicit synthetic equal-value parent fixture, no real facts are rewritten.
        f=copy.deepcopy(next(f for f in self.p['facts'] if f['fact_id']=='net_profit'));f.update(fact_id='parent_profit',name='归母净利润',evidence_ids=['PARENT'])
        e=copy.deepcopy(self.f.evidence['F_net_profit']);e.update(evidence_id='PARENT',text='归母净利润原文',related_facts=['parent_profit'])
        self.p['facts'].append(f);self.p['evidence'].append(e)
        self.p['source_contract']['facts']['parent_profit']=digest(f)
        receipt=copy.deepcopy(self.p['source_contract']['evidence']['F_net_profit']);receipt['evidence_sha256']=digest(e)
        self.p['source_contract']['evidence']['PARENT']=receipt
        r=self.fact('归母净利润下降','parent_profit');r['claims'][0]['citations']=[dict(evidence_id='PARENT',quote=e['text'])]
        self.assertEqual(self.check(r)['errors'],[])
    def test_negation_comparison_not_rejected(self):
        for text in ('净利润不是归母净利润','本项为净利润而非归母净利润','净利润与归母净利润口径不同','相比归母净利润下降，净利润口径另行核实'):
            with self.subTest(text=text):self.assertEqual(self.check(self.fact(text))['errors'],[])
    def test_qualified_disclosure_passes(self):self.assertEqual(self.check(self.disclosure())['errors'],[])
    def test_full_coverage_rejected(self):
        for text in ('该解释覆盖全部现金流量净额变动幅度','现金流入增加额构成净额增长的完整定量贡献'):
            self.assertTrue(any('support_scope_overreach' in e for e in self.check(self.disclosure(limit=text))['errors']))
    def test_negative_scope_passes(self):
        for text in ('该解释不能覆盖全部净额变化','不能证明该解释覆盖全部净额变化','“覆盖全部净额变化”的说法缺乏证据'):
            with self.subTest(text=text):self.assertEqual(self.check(self.disclosure(limit=text))['errors'],[])
    def test_negation_does_not_exempt_later_assertion(self):
        r=self.disclosure(limit='不能覆盖全部净额变化，但该解释覆盖全部净额变化')
        self.assertTrue(any('support_scope_overreach' in e for e in self.check(r)['errors']))
    def test_ambiguous_cause_manual_review(self):
        r=self.disclosure(text='收款结构与经营现金流变化可能存在复杂联系')
        result=self.check(r);self.assertEqual(result['status'],'needs_human_review')
        self.assertTrue(any('未命中不证明' in t for t in result['manual_review']))
    def test_kind_change_not_bypass(self):
        r=self.disclosure(limit='该解释覆盖全部净额变化');r['claims'][0]['kind']='accounting_fact'
        self.assertTrue(any('support_scope_overreach' in e for e in self.check(r)['errors']))
    def test_historical_isolated_diagnostics_and_replay(self):
        before=copy.deepcopy(self.f.original);result=self.check(self.f.original)
        self.assertTrue(any('metric_scope_conflict' in e for e in result['errors']))
        self.assertTrue(any('support_scope_overreach' in e for e in result['errors']))
        self.assertEqual(self.f.original,before)
        r,d,c=self.f.fixture.run_actions(self.f.fixture.actions)
        self.assertEqual(r['status'],'validation_failed');self.assertEqual(d.attempts,3)
