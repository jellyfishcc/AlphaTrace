"""Immutable historical response replay; mutations are explicit negative test cases."""
import copy
import unittest
import test_evidence_provenance as provenance
from tracelab.source_contract import quote_matches,digest
from tracelab.stage3 import validate

class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.f=provenance.EvidenceTests();self.f.setUp()
        self.p=self.f.payload
        self.e=next(e for e in self.p['evidence'] if e['evidence_id']=='E07_28')
        self.a=self.f.actions[-1]['arguments']['analysis']
        self.q=self.a['claims'][1]['citations'][0]['quote']

    def test_historical_soft_break_only(self):
        before=copy.deepcopy((self.p,self.a))
        self.assertEqual(self.e['text'].replace('\n',''),self.q)
        self.assertTrue(quote_matches(self.q,self.e,self.p))
        self.assertEqual((self.p,self.a),before)

    def test_exact_original(self):self.assertTrue(quote_matches(self.e['text'],self.e,self.p))

    def test_substantive_changes_rejected(self):
        for q in (self.q.replace('57.93','57.94'),self.q.replace('经营活动','投资活动'),
                  self.q.replace('、','；'),self.q.replace('主要系','仅系'),self.q.replace('主要系',''),
                  self.q.replace('增加所致','减少所致')):
            with self.subTest(q=q):self.assertFalse(quote_matches(q,self.e,self.p))

    def test_whitespace_not_globally_removed(self):
        self.assertFalse(quote_matches(self.q.replace(' ',''),self.e,self.p))
        self.assertFalse(quote_matches(self.q.replace('现金','现 金'),self.e,self.p))

    def test_unknown_break_stays_strict(self):
        e=copy.deepcopy(self.e);e['text']=e['text'].replace('主要系','主要\n系')
        self.p['source_contract']['evidence']['E07_28']['evidence_sha256']=digest(e)
        self.assertFalse(quote_matches(self.q,e,self.p))

    def test_wrong_id_rejected(self):
        a=copy.deepcopy(self.a);a['claims'][1]['citations'][0]['evidence_id']='E18'
        self.assertIn('结论2引文与原文不一致',validate(a,self.p)['errors'])

    def test_hash_mismatch_rejected(self):
        self.p['source_contract']['evidence']['E07_28']['evidence_sha256']='0'*64
        self.assertFalse(quote_matches(self.q,self.e,self.p))
        self.assertTrue(any('来源核验' in e for e in validate(self.a,self.p)['errors']))

    def test_different_pdf_receipt_rejected(self):
        self.p['source_contract']['evidence']['E07_28']['file_sha256']='0'*64
        self.assertFalse(quote_matches(self.q,self.e,self.p))

    def test_historical_other_errors_remain(self):
        errors=validate(self.a,self.p)['errors']
        self.assertNotIn('结论2引文与原文不一致',errors)
        for part in ('金额未关联','金额缺少','会计层级','自由文本'):
            self.assertTrue(any(part in e for e in errors))

    def test_unchanged_real_replay_still_rejected(self):
        r,d,c=self.f.run_actions(self.f.actions)
        self.assertEqual(r['status'],'validation_failed')
        self.assertIn('F_net_profit',c['ineligible_citation_ids'])
        self.assertEqual(d.attempts,3)

    def test_unretrieved_evidence_still_rejected(self):
        r,d,c=self.f.run_actions([self.f.actions[-1]])
        self.assertEqual(r['status'],'validation_failed')
        self.assertIn('E07_28',c['ineligible_citation_ids'])
