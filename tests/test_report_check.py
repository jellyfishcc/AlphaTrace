"""Synthetic receipts are test-only; real CLI always rebuilds PDF provenance."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tracelab.report_check import check_claim, main, render
from tracelab.source_contract import digest


class ReportCheckTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(Path('examples/report_check/simulated.json').read_text(encoding='utf-8'))
        self.claim, self.payload = fixture['claim'], fixture['payload']
        self.claim['direction'] = '下降'
        self.e = self.payload['evidence'][0]
        self.e.update(source_type='公开年报披露', related_facts=['net_profit'],
                      comparison_basis='both_periods', printed_page='1', pdf_page=1)
        self.bind()

    def bind(self):
        self.payload['source_contract'] = dict(facts={f['fact_id']: digest(f) for f in self.payload['facts']},
            evidence={self.e['evidence_id']: dict(source_kind='annual_report', file_sha256='0'*64,
                       evidence_sha256=digest(self.e), allowed_bases=['yoy'])})

    def check(self, **changes):
        with patch('socket.socket', side_effect=AssertionError('no network')), \
             patch('tracelab.bailian.configuration', side_effect=AssertionError('no credentials')):
            return check_claim(self.claim | changes, self.payload)

    def test_correct_statement(self):
        r = self.check()
        self.assertEqual(r['status'], '一致')
        self.assertFalse(r['llm_called'])
        self.assertEqual(r['sources'][0]['evidence_id'], 'SIM_ONLY')

    def test_wrong_direction(self):
        r = self.check(direction='增长')
        self.assertEqual(r['errors'], ['方向错误'])
        self.assertIn('下降', r['correction'])
        self.assertIn('PDF页 1', render(r))

    def test_wrong_amount(self):
        self.assertEqual(self.check(value='0.3000')['errors'], ['数值错误'])

    def test_wrong_unit(self):
        self.assertEqual(self.check(unit='万元')['errors'], ['数值或单位错误'])

    def test_current_value_and_display_precision(self):
        self.assertEqual(self.check(value_kind='current', value='0.8')['status'], '一致')
        self.assertEqual(self.check(value='0.20')['status'], '一致')
        self.assertEqual(self.check(value='0.2001')['status'], '发现错误')

    def test_identity_and_basis_mismatch(self):
        for change in [dict(company='其他公司'), dict(period='2026'), dict(base_period='2023'),
                       dict(metric_name='归母净利润'), dict(scope='母公司'), dict(comparison_basis='current_period')]:
            with self.subTest(change=change):
                self.assertEqual(self.check(**change)['status'], '无法核实')

    def test_missing_fact_or_amount(self):
        self.assertEqual(self.check(metric_id='missing')['status'], '无法核实')
        del self.payload['facts'][0]['amounts']['base']
        self.bind()
        self.assertEqual(self.check()['status'], '无法核实')

    def test_tampered_fact_or_source(self):
        self.payload['facts'][0]['amounts']['current']['元'] = '999'
        self.assertEqual(self.check()['status'], '无法核实')
        self.setUp()
        self.e['text'] = 'altered'
        self.assertEqual(self.check()['status'], '无法核实')

    def test_source_basis_and_identity(self):
        for field, value in [('comparison_basis', 'current_period'), ('related_facts', ['parent_profit'])]:
            self.setUp()
            self.e[field] = value
            self.bind()
            self.assertEqual(self.check()['status'], '无法核实')

    def test_invalid_numbers_and_schema(self):
        for value in ('NaN', 'Infinity', '-0.2', '2e-1', 'nonsense', '0.123456789', '0.2_0'):
            self.assertEqual(self.check(value=value)['status'], '无法核实')
        self.assertEqual(self.check(unit='美元')['status'], '无法核实')
        self.assertEqual(check_claim({}, self.payload)['status'], '无法核实')
        self.assertIn('无法核实', render(check_claim([], self.payload)))

    def test_inconsistent_amounts_unknown(self):
        self.payload['facts'][0]['amounts']['change']['元'] = '-1'
        self.bind()
        self.assertEqual(self.check()['status'], '无法核实')

    def test_simulated_cli_no_external_dependencies(self):
        with tempfile.TemporaryDirectory() as d, patch('socket.socket', side_effect=AssertionError('no network')):
            self.assertEqual(main(['--simulated-demo', '--output', d]), 0)
            result = json.loads(next(Path(d).glob('*/result.json')).read_text(encoding='utf-8'))
            self.assertTrue(result['simulation'])
            self.assertEqual(result['status'], '发现错误')

    def test_missing_snapshot_unknown_with_report(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(['--stage2-run', str(Path(d)/'missing'), '--claim',
                                  'examples/report_check/gree_direction_error.json', '--output', d]), 2)
            result = json.loads(next(Path(d).glob('*/result.json')).read_text(encoding='utf-8'))
            self.assertEqual(result['status'], '无法核实')
            self.assertEqual(result['sources'], [])


class LocalGreeCheckTests(unittest.TestCase):
    def test_verified_gree_direction_example(self):
        folder = Path('outputs/final_revision/20261017T093152-d80de1cefa')
        if not folder.exists():
            self.skipTest('private Gree snapshot missing; synthetic tests remain available')
        from tracelab.final_release import load_agent_payload
        with patch('socket.socket', side_effect=AssertionError('no network')):
            payload, _ = load_agent_payload(folder)
            claim = json.loads(Path('examples/report_check/gree_direction_error.json').read_text(encoding='utf-8'))
            result = check_claim(claim, payload)
        self.assertEqual(result['errors'], ['方向错误'])
        self.assertEqual(result['expected']['change_yuan'], '-3508323271.19')
        self.assertEqual(result['sources'][0]['pdf_page'], 88)
        self.assertEqual(check_claim(claim | {'direction': '下降'}, payload)['status'], '一致')
