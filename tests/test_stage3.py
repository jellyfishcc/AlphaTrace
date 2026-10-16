"""Synthetic validator/transport tests only; these are not model responses."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tracelab.stage3 import validate, visible_response, redact, run


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        self.payload={'facts':[{'fact_id':'net','amounts':{'change':{'元':'-10.00'}}}],
                      'evidence':[{'evidence_id':'F_net','text':'净利润下降','related_facts':['net']}]}
        self.answer={'claims':[{'kind':'accounting_fact','statement':'净利润下降','metric_ids':['net'],
                                'citations':[{'evidence_id':'F_net','quote':'净利润下降'}],
                                'amounts':[{'fact_id':'net','field':'change','unit':'元','value':'-10.00'}],
                                'support_limit':'只能说明会计变化'}], 'questions':['仍需核查经营原因']}

    def test_valid_still_requires_human(self):
        self.assertEqual(validate(self.answer,self.payload)['status'],'needs_human_review')

    def test_number_period_unit_and_nonfinite_rejected(self):
        for field,value in [('value','-11'),('field','current'),('unit','亿元'),('value','NaN')]:
            a=copy.deepcopy(self.answer); a['claims'][0]['amounts'][0][field]=value
            self.assertEqual(validate(a,self.payload)['status'],'failed')

    def test_false_quote_unknown_evidence_and_missing_evidence(self):
        for citations in ([{'evidence_id':'invented','quote':'净利润下降'}],
                          [{'evidence_id':'F_net','quote':'价格战导致下降'}],[]):
            a=copy.deepcopy(self.answer); a['claims'][0]['citations']=citations
            self.assertEqual(validate(a,self.payload)['status'],'failed')

    def test_hypothesis_and_unstructured_money_fail(self):
        for text,kind in [('价格战就是原因','hypothesis'),('下降十亿元','accounting_fact'),('下降10元','accounting_fact')]:
            a=copy.deepcopy(self.answer); a['claims'][0].update(statement=text,kind=kind)
            self.assertEqual(validate(a,self.payload)['status'],'failed')

    def test_schema_extra_fields_and_empty_claims(self):
        a=copy.deepcopy(self.answer); a['reasoning']='must not be requested'
        self.assertEqual(validate(a,self.payload)['status'],'failed')
        self.assertEqual(validate({'claims':[],'questions':[]},self.payload)['status'],'failed')

    def test_reasoning_never_saved(self):
        raw={'status':'completed','output':[{'type':'reasoning','summary':['private']},
             {'type':'message','role':'assistant','content':[{'type':'output_text','text':'{}'}]}]}
        self.assertNotIn('private',json.dumps(visible_response(raw)))

    def test_secret_redaction(self):
        self.assertEqual(redact({'error':'token123 and sk-example'},'token123'),{'error':'[REDACTED] and [REDACTED]'})

    def test_no_credentials_never_calls_api(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{},clear=True), \
             patch('tracelab.stage3.prepare',return_value=(self.payload,{'source_run':'synthetic_test'})), \
             patch('tracelab.stage3.deliver'), patch('tracelab.stage3.call_api') as api:
            out,m=run(Path(d),Path(d)/'out',True)
            api.assert_not_called()
            self.assertEqual(m['status'],'not_called')
            self.assertFalse((out/'response.json').exists())

    def test_http_error_logged_without_credentials(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{'OPENAI_API_KEY':'secret-for-test','TRACELAB_MODEL':'test-model'}), \
             patch('tracelab.stage3.prepare',return_value=(self.payload,{'source_run':'synthetic_test'})), \
             patch('tracelab.stage3.deliver'), \
             patch('tracelab.stage3.call_api',side_effect=HTTPError('https://api.openai.com',401,'secret-for-test',{},None)):
            out,m=run(Path(d),Path(d)/'out',True)
            self.assertEqual(m['status'],'call_failed')
            self.assertNotIn('secret-for-test',''.join(p.read_text(encoding='utf-8') for p in out.iterdir() if p.is_file()))
