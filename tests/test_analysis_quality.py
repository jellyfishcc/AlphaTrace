"""Offline financial-contract regression tests; no real API calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tracelab.stage3 import validate, run, visible_response
from tracelab.bailian import Config, as_response
from tracelab.analysis_contract import configure


class QualityTests(unittest.TestCase):
    def setUp(self):
        keys=('net_profit','income_tax','minority_profit','parent_profit','operating_profit',
              'nonoperating_income','operating_cashflow','bill_deposits')
        self.payload={'facts':[{'fact_id':k,'evidence_ids':['F_'+k],'amounts':{'change':{'元':'10.00'}}} for k in keys],
                      'evidence':[{'evidence_id':'F_'+k,'text':'已披露的变化','related_facts':[k]} for k in keys],
                      'analysis_contract':{'version':'v2','mode':'focused','max_claims':2,'ratios_allowed':False,
                       'accounting_relations':[
                        {'target':'net_profit','verified':True,'components':[{'component':'income_tax','effect':'decrease'}]},
                        {'target':'parent_profit','verified':True,'components':[{'component':'minority_profit','effect':'decrease'}]}]}}
        self.answer={'claims':[{'kind':'hypothesis','statement':'待验证：经营原因尚缺证据',
                     'metric_ids':['net_profit'],'citations':[{'evidence_id':'F_net_profit','quote':'已披露的变化'}],
                     'amounts':[],'support_limit':'需要更多经营披露','accounting_links':[],
                     'comparison_basis':'none'}],'questions':['是否有可以支持原因的公开披露？']}

    def link(self,target,component,effect):
        c=self.answer['claims'][0]
        c['metric_ids']=[target,component]
        c['citations']=[{'evidence_id':'F_'+k,'quote':'已披露的变化'} for k in c['metric_ids']]
        c['accounting_links']=[dict(target=target,component=component,effect=effect)]

    def test_wrong_tax_direction_rejected(self):
        self.link('net_profit','income_tax','increase')
        self.assertIn('会计影响方向',''.join(validate(self.answer,self.payload)['errors']))

    def test_correct_tax_direction_still_manual(self):
        self.link('net_profit','income_tax','decrease')
        self.assertEqual(validate(self.answer,self.payload)['status'],'needs_human_review')

    def test_minority_wrong_level_rejected(self):
        self.link('net_profit','minority_profit','decrease')
        self.assertIn('会计层级',''.join(validate(self.answer,self.payload)['errors']))

    def test_nonoperating_wrong_level_rejected(self):
        self.link('operating_profit','nonoperating_income','increase')
        self.assertIn('会计层级',''.join(validate(self.answer,self.payload)['errors']))

    def test_deposit_ratio_rejected(self):
        self.answer['claims'][0]['statement']='保证金占现金流同比增量92.1%'
        self.assertEqual(validate(self.answer,self.payload)['status'],'failed')

    def test_disclosure_period_mismatch_rejected(self):
        self.payload['evidence'].append(dict(evidence_id='E07_29',text='受限资金收回',
                                           related_facts=['net_profit'],comparison_basis='current_period'))
        self.answer['claims'][0].update(kind='disclosure_explanation',statement='年报披露受限资金收回',comparison_basis='yoy',
                 citations=[dict(evidence_id='E07_29',quote='受限资金收回')])
        self.assertIn('比较口径',''.join(validate(self.answer,self.payload)['errors']))

    def test_semantic_prose_never_automatically_accepted(self):
        for text in ('所得税增加推动净利润增长','少数股东损益解释净利润缺口',
                     '营业外收入是营业利润组成','保证金是现金流同比增长核心驱动'):
            self.answer['claims'][0].update(kind='accounting_fact',statement=text)
            result=validate(self.answer,self.payload)
            self.assertEqual(result['status'],'needs_human_review')
            self.assertTrue(any('文字是否与结构化' in r for r in result['manual_review']))

    def test_invalid_evidence_and_quote(self):
        for citation in ({'evidence_id':'fake','quote':'已披露的变化'},
                         {'evidence_id':'F_net_profit','quote':'虚构原文'}):
            self.answer['claims'][0]['citations']=[citation]
            self.assertEqual(validate(self.answer,self.payload)['status'],'failed')

    def test_amount_period_unit_rejected(self):
        for field,unit,value in [('change','元','11'),('base','元','10'),('change','亿元','10')]:
            self.answer['claims'][0]['amounts']=[dict(fact_id='net_profit',field=field,unit=unit,value=value)]
            self.assertEqual(validate(self.answer,self.payload)['status'],'failed')

    def test_insufficient_evidence_hypothesis_retained(self):
        self.assertEqual(validate(self.answer,self.payload)['status'],'needs_human_review')

    def test_focused_claim_limit(self):
        self.answer['claims']*=3
        self.assertEqual(validate(self.answer,self.payload)['status'],'failed')

    def mock_run(self,raw,execute=True):
        cfg=Config('synthetic-secret','https://example.test/compatible-mode/v1','qwen-plus',{})
        with tempfile.TemporaryDirectory() as d, patch('tracelab.stage3.configuration',return_value=cfg), \
             patch('tracelab.stage3.prepare',return_value=(self.payload,{'source_run':'synthetic'})), \
             patch('tracelab.stage3.deliver'),patch('tracelab.stage3.call_api',return_value=(raw,'synthetic')) as api:
            out,state=run(Path(d),Path(d)/'out',execute,'bailian',timeout_seconds=180,analysis_mode='focused')
            if execute: api.assert_called_once()
            else: api.assert_not_called()
            body=json.loads((out/'request.json').read_text(encoding='utf-8'))
            self.assertEqual(body['max_tokens'],3000)
            self.assertEqual(body['response_format'],{'type':'json_object'})
            return state

    def test_focused_mock_valid(self):
        raw={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(self.answer)}}]}
        self.assertEqual(self.mock_run(raw)['status'],'completed_pending_human_review')

    def test_focused_dry_run_no_network(self):
        self.assertEqual(self.mock_run(None,False)['status'],'not_called')

    def test_real_truncation_fixture_never_repaired(self):
        saved=json.loads((Path(__file__).parent/'fixtures/qwen_truncated_response.json').read_text(encoding='utf-8'))
        text=saved['messages'][0]['text']
        with self.assertRaises(json.JSONDecodeError): json.loads(text)
        for reason,expected in [('length','response_failed'),('stop','validation_failed')]:
            raw={'choices':[{'finish_reason':reason,'message':{'content':text}}]}
            self.assertEqual(self.mock_run(raw)['status'],expected)
        self.assertIn('92.1%',text)
        self.assertIn('-22.5134 + 12.5699',text)

    def test_finish_reason_preserved(self):
        result=visible_response(as_response({'choices':[{'finish_reason':'length','message':{'content':'{'}}]}))
        self.assertEqual(result['finish_reason'],'length')
        self.assertEqual(result['incomplete_reason'],'length')

    def test_contract_selection_preserves_text_and_amounts(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            (folder/'bridges.json').write_text('[]',encoding='utf-8')
            (folder/'directional_impacts.csv').write_text('level,item_id\n',encoding='utf-8')
            result,_=configure(self.payload,folder,'focused')
        self.assertEqual({f['fact_id'] for f in result['facts']},{'net_profit','operating_cashflow','bill_deposits'})
        for fact in result['facts']: self.assertIn(fact,self.payload['facts'])
        for e in result['evidence']:
            original=next(x for x in self.payload['evidence'] if x['evidence_id']==e['evidence_id'])
            self.assertEqual(original['text'],e['text'])
