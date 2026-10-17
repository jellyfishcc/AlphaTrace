"""All API responses here are synthetic; tests never contact a model service."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from tracelab.bailian import Config, configuration, chat_body, as_response
from tracelab.connectivity import run
from tracelab.stage3 import call_api, visible_response, SCHEMA

BASE='https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'


class BailianTests(unittest.TestCase):
    def config(self):
        return Config('synthetic-secret',BASE,'qwen-plus',{'key':'test','base_url':'test'})

    def test_windows_fallback_no_environment_mutation(self):
        values={'DASHSCOPE_API_KEY':'fake','DASHSCOPE_BASE_URL':BASE}
        with patch.dict('os.environ',{},clear=True), patch('tracelab.bailian.user_environment',side_effect=lambda n:values.get(n,'')):
            cfg=configuration()
            self.assertEqual(cfg.key,'fake')
            self.assertEqual(cfg.endpoint,BASE+'/chat/completions')
            self.assertEqual(cfg.model,'qwen-plus')
            self.assertEqual(cfg.sources['base_url'],'windows_user')
            self.assertNotIn('fake',repr(cfg))

    def test_process_config_and_model_override(self):
        with patch.dict('os.environ',{'DASHSCOPE_API_KEY':'fake','DASHSCOPE_BASE_URL':BASE,'DASHSCOPE_MODEL':'qwen-plus'}), patch('tracelab.bailian.user_environment',return_value=''):
            self.assertEqual(configuration('test-model').model,'test-model')
            self.assertEqual(configuration().sources['base_url'],'process')

    def test_bad_base_never_falls_back_to_another_region(self):
        for base in ('','http://host/compatible-mode/v1','https://secret@host/compatible-mode/v1',BASE+'?key=secret'):
            with self.assertRaises(ValueError):
                _=Config('',base,'qwen-plus',{}).endpoint

    def test_json_object_adapts_schema_without_responses_fields(self):
        body=chat_body('qwen-plus','prompt','input',3000,SCHEMA)
        self.assertEqual(body['response_format'],{'type':'json_object'})
        self.assertIn('JSON',body['messages'][0]['content'])
        self.assertFalse(body['enable_thinking'])
        self.assertNotIn('text',body)
        self.assertNotIn('max_output_tokens',body)

    def test_final_only_and_truncation(self):
        raw={'choices':[{'finish_reason':'length','message':{'content':'连接','reasoning_content':'hidden'}}]}
        safe=visible_response(as_response(raw))
        self.assertEqual(safe['status'],'incomplete')
        self.assertNotIn('hidden',json.dumps(safe))

    def test_dry_run_zero_requests(self):
        with tempfile.TemporaryDirectory() as d, patch('tracelab.connectivity.configuration',return_value=self.config()), patch('tracelab.connectivity.call_api') as api:
            p,s=run(d)
            api.assert_not_called()
            self.assertEqual(s['status'],'not_called')
            self.assertIsNone(s['usage'])
            self.assertFalse((p/'response.json').exists())

    def test_one_mock_success_and_usage(self):
        raw={'model':'qwen-plus','usage':{'prompt_tokens':20,'completion_tokens':2},
             'choices':[{'finish_reason':'stop','message':{'content':'连接成功'}}]}
        with tempfile.TemporaryDirectory() as d, patch('tracelab.connectivity.configuration',return_value=self.config()), patch('tracelab.connectivity.call_api',return_value=(raw,'mock-request')) as api:
            p,s=run(d,execute=True)
            api.assert_called_once()
            self.assertEqual(api.call_args.kwargs['timeout'],30)
            self.assertEqual(api.call_args.args[0]['max_tokens'],16)
            self.assertEqual(s['status'],'connected')
            self.assertEqual(s['usage'],raw['usage'])
            self.assertNotIn('synthetic-secret',''.join(f.read_text(encoding='utf-8') for f in p.iterdir()))

    def test_failure_no_retry_and_secret_not_logged(self):
        with tempfile.TemporaryDirectory() as d, patch('tracelab.connectivity.configuration',return_value=self.config()), patch('tracelab.connectivity.call_api',side_effect=HTTPError(BASE,401,'synthetic-secret',{},None)) as api:
            p,s=run(d,execute=True)
            api.assert_called_once()
            self.assertEqual(s['http_status'],401)
            self.assertEqual(s['status'],'failed')
            self.assertNotIn('synthetic-secret',''.join(f.read_text(encoding='utf-8') for f in p.iterdir()))

    def test_transport_exact_endpoint_and_timeout(self):
        result=MagicMock()
        result.__enter__.return_value=result
        result.read.return_value=b'{"choices": []}'
        result.headers.get.return_value='mock-id'
        opener=MagicMock()
        opener.open.return_value=result
        with patch('tracelab.stage3.request.build_opener',return_value=opener):
            call_api({'model':'qwen-plus'},'synthetic-secret',BASE+'/chat/completions',30)
        opener.open.assert_called_once()
        self.assertEqual(opener.open.call_args.args[0].full_url,BASE+'/chat/completions')
        self.assertEqual(opener.open.call_args.kwargs['timeout'],30)

    def test_stage3_bailian_reuses_existing_validator(self):
        from tracelab.stage3 import run as stage3_run
        raw={'model':'qwen-plus','choices':[{'finish_reason':'stop','message':{
            'content':'{"claims": [], "questions": []}'}}]}
        with tempfile.TemporaryDirectory() as d, patch('tracelab.stage3.configuration',return_value=self.config()), \
             patch('tracelab.stage3.prepare',return_value=({'facts':[],'evidence':[]},{'source_run':'synthetic'})), \
             patch('tracelab.stage3.deliver'), patch('tracelab.stage3.call_api',return_value=(raw,'mock-id')) as api:
            folder,state=stage3_run(Path(d),Path(d)/'out',True,'bailian')
            self.assertEqual(state['status'],'validation_failed')
            self.assertEqual(api.call_args.kwargs['endpoint'],BASE+'/chat/completions')
            self.assertEqual(api.call_args.args[0]['response_format']['type'],'json_object')
