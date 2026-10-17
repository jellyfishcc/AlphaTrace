"""Offline transport diagnostics; every network opener is mocked."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from tracelab.stage3 import call_api, run, SCHEMA
from tracelab.bailian import Config, chat_body


class TransportTests(unittest.TestCase):
    def response(self):
        response=MagicMock()
        response.__enter__.return_value=response
        response.status=200
        response.headers={'x-request-id':'synthetic-request'}
        response.read.return_value=b'{}'
        return response

    def test_timeout_before_headers(self):
        opener=MagicMock()
        opener.open.side_effect=TimeoutError('secret')
        diagnostic={}
        with patch('tracelab.stage3.request.build_opener',return_value=opener):
            with self.assertRaises(TimeoutError):
                call_api({},'secret',timeout=180,diagnostics=diagnostic)
        self.assertEqual(diagnostic['phase'],'connect_or_wait_headers')
        self.assertIsNone(diagnostic['request_id'])
        opener.open.assert_called_once()
        self.assertEqual(opener.open.call_args.kwargs['timeout'],180)

    def test_body_timeout_preserves_headers(self):
        response=self.response()
        response.read.side_effect=TimeoutError('secret')
        diagnostic={}
        with patch('tracelab.stage3.request.build_opener') as factory:
            factory.return_value.open.return_value=response
            with self.assertRaises(TimeoutError):
                call_api({},'secret',diagnostics=diagnostic)
        self.assertEqual(diagnostic,dict(phase='read_body',http_status=200,request_id='synthetic-request'))

    def test_decode_phase_and_success(self):
        for body,phase in ((b'invalid','decode_json'),(b'{}','complete')):
            response=self.response()
            response.read.return_value=body
            diagnostic={}
            with patch('tracelab.stage3.request.build_opener') as factory:
                factory.return_value.open.return_value=response
                if phase=='decode_json':
                    with self.assertRaises(ValueError): call_api({},'secret',diagnostics=diagnostic)
                else:
                    self.assertEqual(call_api({},'secret',diagnostics=diagnostic),({},'synthetic-request'))
            self.assertEqual(diagnostic['phase'],phase)

    def test_http_error_id_preserved(self):
        diagnostic={}
        with patch('tracelab.stage3.request.build_opener') as factory:
            factory.return_value.open.side_effect=HTTPError('https://example.test',429,'secret',{'x-request-id':'synthetic'},None)
            with self.assertRaises(HTTPError): call_api({},'secret',diagnostics=diagnostic)
        self.assertEqual(diagnostic,dict(phase='http_error',http_status=429,request_id='synthetic'))

    def test_run_failure_logs_safe_diagnostics_without_retry(self):
        def fail(*args,**kwargs):
            self.assertEqual(kwargs['timeout'],180)
            kwargs['diagnostics'].update(phase='read_body',http_status=200,request_id='synthetic')
            raise TimeoutError('synthetic-secret')
        cfg=Config('synthetic-secret','https://example.test/compatible-mode/v1','qwen-plus',{})
        with tempfile.TemporaryDirectory() as folder, \
             patch('tracelab.stage3.configuration',return_value=cfg), \
             patch('tracelab.stage3.prepare',return_value=({'facts':[],'evidence':[]},{'source_run':'synthetic'})), \
             patch('tracelab.stage3.deliver'),patch('tracelab.stage3.call_api',side_effect=fail) as api:
            out,state=run(Path(folder),Path(folder)/'out',True,'bailian',timeout_seconds=180)
            api.assert_called_once()
            self.assertEqual(state['status'],'call_failed')
            self.assertEqual(state['http_status'],200)
            self.assertEqual(state['request_id'],'synthetic')
            self.assertEqual(json.loads((out/'checks.json').read_text(encoding='utf-8'))['status'],'not_run')
            self.assertNotIn('synthetic-secret',''.join(p.read_text(encoding='utf-8') for p in out.iterdir()))

    def test_compact_schema_keeps_exact_structure(self):
        body=chat_body('qwen-plus','prompt','{}',3000,SCHEMA)
        self.assertEqual(json.loads(body['messages'][0]['content'].split('\n')[-1]),SCHEMA)

    def test_invalid_timeout_rejected_before_work(self):
        for timeout in (0,301):
            with self.assertRaises(ValueError): run('unused','unused',timeout_seconds=timeout)
