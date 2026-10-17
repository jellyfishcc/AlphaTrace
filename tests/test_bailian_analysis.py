"""Synthetic structured chat completions; never real model evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from tracelab.bailian import Config
from tracelab.stage3 import run


class BailianAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.payload={'facts':[{'fact_id':'net','amounts':{'change':{'元':'-10.00'}}}],
                      'evidence':[{'evidence_id':'F_net','text':'净利润下降','related_facts':['net']}]}
        self.valid={'claims':[{'kind':'accounting_fact','statement':'净利润下降','metric_ids':['net'],
                    'citations':[{'evidence_id':'F_net','quote':'净利润下降'}],
                    'amounts':[{'fact_id':'net','field':'change','unit':'元','value':'-10.00'}],
                    'support_limit':'仅说明会计变化'}],'questions':['经营原因仍待核查']}

    def check_run(self,raw,expected,exception=None):
        config=Config('test-secret','https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1','qwen-plus',{})
        with tempfile.TemporaryDirectory() as d, patch('tracelab.stage3.configuration',return_value=config), \
             patch('tracelab.stage3.prepare',return_value=(self.payload,{'source_run':'synthetic'})), \
             patch('tracelab.stage3.deliver'), \
             patch('tracelab.stage3.call_api',return_value=(raw,'mock-id'),side_effect=exception) as api:
            folder,state=run(Path(d),Path(d)/'runs',True,'bailian','qwen-plus')
            api.assert_called_once()
            self.assertEqual(state['status'],expected)
            self.assertNotIn('test-secret',''.join(p.read_text(encoding='utf-8') for p in folder.iterdir()))
            return state if expected=='call_failed' else json.loads((folder/'checks.json').read_text(encoding='utf-8'))

    def response(self,text):
        return {'model':'qwen-plus','choices':[{'finish_reason':'stop','message':{'content':text,'reasoning_content':'not_saved'}}]}

    def test_valid_json_through_chat_and_existing_validator(self):
        result=self.check_run(self.response(json.dumps(self.valid,ensure_ascii=False)),'completed_pending_human_review')
        self.assertEqual(result['status'],'needs_human_review')

    def test_invalid_json_or_structure_fails(self):
        for text in ('```json {} ```','[]','{"claims":[],"questions":[]}'):
            self.check_run(self.response(text),'validation_failed')

    def test_invalid_amount_and_reference_fail(self):
        for field,value in [('amount','-11'),('evidence','invented')]:
            changed=json.loads(json.dumps(self.valid))
            if field=='amount': changed['claims'][0]['amounts'][0]['value']=value
            else: changed['claims'][0]['citations'][0]['evidence_id']=value
            self.check_run(self.response(json.dumps(changed)),'validation_failed')

    def test_bad_envelope_safely_logged(self):
        for raw in ({'choices':[None]},{'choices':[{'message':['unexpected']}]},[]):
            self.check_run(raw,'call_failed')

    def test_http_error_safely_logged(self):
        result=self.check_run(None,'call_failed',HTTPError('https://example.invalid',429,'test-secret',{},None))
        self.assertEqual(result['http_status'],429)
