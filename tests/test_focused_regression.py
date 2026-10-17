"""Real failure stays immutable; all edited answers below are synthetic test variants."""
import copy
import json
import unittest
from pathlib import Path
from tracelab.stage3 import validate


class FocusedRegressionTests(unittest.TestCase):
    def setUp(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/qwen_focused_validation_failure.json').read_text(encoding='utf-8'))
        self.answer=fixture['analysis']
        self.payload=fixture['input']
        # Synthetic loader receipt for these existing validator-only variants.
        # The immutable historical fixture is NOT retroactively marked verified.
        from tracelab.source_contract import digest
        self.payload['source_contract']={'evidence':{
            e['evidence_id']:{'source_kind':'annual_report','file_sha256':'0'*64,
                'evidence_sha256':digest(e),'allowed_bases':[e['comparison_basis']]}
            for e in self.payload['evidence']}}

    def corrected_variant(self):
        answer=copy.deepcopy(self.answer)
        answer['claims'][0]['metric_ids'].append('bill_deposits')
        answer['claims'][1]['statement']='年报披露经营现金流同比增长，主要系销售商品收款及其他经营现金增加。'
        return answer

    def test_original_failure_reproduced(self):
        result=validate(self.answer,self.payload)
        self.assertEqual(result['status'],'failed')
        self.assertIn('金额未关联',''.join(result['errors']))
        self.assertIn('自由文本',''.join(result['errors']))

    def test_amount_association_required(self):
        answer=self.corrected_variant()
        answer['claims'][0]['metric_ids'].remove('bill_deposits')
        self.assertIn('金额未关联',''.join(validate(answer,self.payload)['errors']))

    def test_corrected_variant_requires_human_review(self):
        result=validate(self.corrected_variant(),self.payload)
        self.assertEqual(result['errors'],[])
        self.assertEqual(result['status'],'needs_human_review')

    def test_free_text_percentage_blocked(self):
        answer=self.corrected_variant()
        answer['claims'][1]['statement']=self.answer['claims'][1]['statement']
        self.assertIn('自由文本',''.join(validate(answer,self.payload)['errors']))

    def test_percentage_in_exact_quote_allowed(self):
        answer=self.corrected_variant()
        self.assertIn('57.93%',answer['claims'][1]['citations'][0]['quote'])
        self.assertEqual(validate(answer,self.payload)['errors'],[])

    def test_current_evidence_cannot_be_yoy_disclosure(self):
        answer=self.corrected_variant()
        answer['claims'][0]['comparison_basis']='yoy'
        self.assertIn('比较口径',''.join(validate(answer,self.payload)['errors']))

    def test_current_only_amount_cannot_quantify_yoy_hypothesis(self):
        answer=self.corrected_variant()
        answer['claims'][0].update(kind='hypothesis',statement='待验证：受限资金变动是否影响同比现金流',comparison_basis='yoy')
        self.assertIn('仅有本期金额',''.join(validate(answer,self.payload)['errors']))

    def test_rule_not_hardcoded_to_deposits(self):
        answer=self.corrected_variant()
        for f in self.payload['facts']:
            if f['fact_id']=='bill_deposits': f['fact_id']='other_adjustment'
        for e in self.payload['evidence']:
            e['related_facts']=['other_adjustment' if k=='bill_deposits' else k for k in e['related_facts']]
        c=answer['claims'][0]
        c['metric_ids']=['other_adjustment' if k=='bill_deposits' else k for k in c['metric_ids']]
        c['amounts'][0]['fact_id']='other_adjustment'
        c.update(kind='hypothesis',statement='待验证：本期项目是否影响同比变化',comparison_basis='yoy')
        self.assertIn('仅有本期金额',''.join(validate(answer,self.payload)['errors']))
