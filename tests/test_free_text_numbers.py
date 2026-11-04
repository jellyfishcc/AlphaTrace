"""Synthetic variants and unchanged real replay; no model calls."""
import copy
import unittest
import test_cashflow_relationship as cash
from tracelab.stage3 import validate,free_text_number_errors

class NumberTests(unittest.TestCase):
    def setUp(self):
        self.f=cash.CashflowTests();self.f.setUp();self.p=self.f.payload;self.r=self.f.response()
    def scan(self,text):
        self.r['claims'][0]['statement']=text
        return free_text_number_errors(self.r,self.p)
    def test_authorized_years(self):
        self.assertEqual(self.scan('比较2024年与2025年的现金流变化'),[])
        self.assertEqual(self.scan('2024年—2025年现金流变化'),[])
    def test_year_like_amounts_and_unauthorized_periods(self):
        for text in ('2024元','2024','2023年','12024年','2024.2025年','-2024年','2024年万元','2024—2025年'):
            with self.subTest(text=text):self.assertTrue(self.scan(text))
    def test_amounts_and_ratios_rejected(self):
        for text in ('增加8,215,480,840.42元','增长57.93%','增长百分之五十','增加十亿元'):
            with self.subTest(text=text):self.assertTrue(self.scan(text))
    def test_all_three_amount_fields_pass(self):
        c=self.r['claims'][0];c['statement']='比较2024年与2025年现金流入分项'
        c['amounts']=[dict(fact_id=f['fact_id'],field=k,unit='元',value=v['元']) for f in self.p['facts'] if f['fact_id'] in c['metric_ids'] for k,v in f['amounts'].items()]
        self.assertEqual(validate(self.r,self.p)['errors'],[])
    def test_missing_change_does_not_authorize_prose_delta(self):
        c=self.r['claims'][0];c['amounts']=[];c['statement']='增加8215480840.42元'
        self.assertTrue(free_text_number_errors(self.r,self.p))
    def test_tampered_value_field_metric_rejected(self):
        for key,value in (('value','1'),('field','base'),('fact_id','operating_cashflow')):
            r=copy.deepcopy(self.r);r['claims'][0]['amounts'][0][key]=value
            self.assertEqual(validate(r,self.p)['status'],'failed')
    def test_original_quote_ratio_preserved(self):
        r=copy.deepcopy(self.f.original);before=copy.deepcopy(r)
        self.assertIn('57.93%',r['claims'][1]['citations'][0]['quote'])
        errors=validate(r,self.p)['errors'];self.assertEqual(r,before)
        self.assertTrue(any('自由文本' in e for e in errors))
        r['claims']=r['claims'][1:];c=r['claims'][0]
        c.update(statement='年报披露现金流增长主要系相关现金流入增加',support_limit='仅为披露解释',amounts=[],accounting_links=[])
        self.assertEqual(validate(r,self.p)['errors'],[])
        self.assertFalse(self.p['analysis_contract']['ratios_allowed'])
    def test_historical_replay_still_rejected(self):
        r,d,c=self.f.fixture.run_actions(self.f.fixture.actions)
        self.assertEqual(r['status'],'validation_failed')
    def test_ratio_contract_remains_false(self):
        self.assertFalse(self.p['analysis_contract']['ratios_allowed'])
    def test_questions_and_limits_scanned(self):
        for field in ('questions','support_limit'):
            r=copy.deepcopy(self.r)
            if field=='questions':r[field]=['增长57.93%吗？']
            else:r['claims'][0][field]='第28页'
            self.assertTrue(free_text_number_errors(r,self.p))
