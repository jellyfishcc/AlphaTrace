"""Offline final-source acceptance tests; snapshots stay local and out of Git."""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from tracelab.final_release import cache_comparison, load_agent_payload
from tracelab.stage3_input import prepare, sha
from tracelab.agent import LocalEvidence, MockDecider, investigate


class PrecisionTests(unittest.TestCase):
    def test_cache_tail_is_not_raw_amount_replacement(self):
        self.assertEqual(cache_comparison(Decimal('83.29000000000001'), Decimal('83.29')), 'formula_cache_rounding')

    def test_real_difference_is_conflict(self):
        self.assertEqual(cache_comparison(Decimal('83.31'), Decimal('83.29')), 'conflict')

    def test_blank_is_not_zero(self):
        self.assertEqual(cache_comparison(None, Decimal('0')), 'conflict')


class FinalSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folders=sorted(Path('outputs/final_release').glob('*/release_hashes.json'))
        if not folders:
            raise unittest.SkipTest('Private source snapshots are not distributed; run final_release first')
        cls.folder=folders[-1].parent
        cls.read=staticmethod(lambda name: json.loads((cls.folder/name).read_text(encoding='utf-8')))
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            cls.payload,cls.audit=load_agent_payload(cls.folder)
        cls.metrics={m['item_id']:m for m in cls.read('metrics.json')}

    def test_core_31_and_original_precision(self):
        self.assertEqual(len(self.metrics),31)
        self.assertEqual(self.metrics['fee_income']['base_amount'],'83.29')
        self.assertEqual(self.metrics['nonoperating_income']['base_amount'],'72190967.82')
        self.assertEqual(self.read('manifest.json')['comparison_counts'],{'same':29,'corrected':2,'conflict':0})

    def test_blank_fee_not_calculated(self):
        m=self.metrics['fee_income']
        self.assertFalse(m['current_amount'])
        self.assertFalse(m['difference'])
        self.assertNotEqual(m['status'],'calculated')

    def test_profit_layers_and_complete_listed_bridge(self):
        bridges=self.read('bridges.json')
        for b in bridges[:5]:
            self.assertEqual(b['math_status'],'exact_zero_residual')
            for year in ('base','current'):
                self.assertEqual(Decimal(b[year]['residual']),0)
        cost=next(b for b in bridges if b['target']=='total_cost')
        self.assertEqual(len(cost['terms']),8)

    def test_cash_direct_components(self):
        for b in self.read('cash_bridges.json'):
            self.assertEqual(b['math_status'],'exact_zero_residual')
        cash={m['item_id']:m for m in self.read('cash_metrics.json')}
        self.assertEqual(Decimal(cash['cash_16']['difference']),Decimal('17013864183.36'))
        self.assertEqual(Decimal(cash['cash_7']['difference']),Decimal('22390475050.08'))
        self.assertEqual(Decimal(cash['cash_15']['difference']),Decimal('5376610866.72'))

    def test_conflicting_periods_and_word_display_retained(self):
        rows=self.read('conflicts.json')
        self.assertEqual(sum(r['kind']=='period_conflict' for r in rows),2)
        self.assertEqual(sum(r['kind']=='word_display_conflict' for r in rows),2)
        ids={f['fact_id'] for f in self.payload['facts']}
        self.assertFalse({'cash_26','cash_27','fair_value_income','fee_income'} & ids)

    def test_year_headers_excluded_tax_cross_year_located(self):
        rows=self.read('supplemental_source_checks.json')
        self.assertFalse(any(r['raw']==['2024','2025'] for r in rows))
        tax=[r for r in rows if r['sheet']=='所得税' and 5<=r['row']<=9]
        self.assertEqual(len(tax),5)
        for r in tax:
            self.assertEqual(r['status'],'original_row_located')
            self.assertEqual({m['fiscal_year'] for m in r['matches']},{'2024','2025'})

    def test_historical_evidence_unchanged(self):
        previous=Path(self.read('manifest.json')['previous_run'])
        self.assertEqual(sha(previous/'evidence.json'),sha(self.folder/'evidence.json'))
        ids=[e['evidence_id'] for e in self.payload['evidence']]
        self.assertEqual(len(ids),len(set(ids)))

    def test_new_evidence_search_and_page_trace(self):
        tool=LocalEvidence(self.payload)
        self.assertIn('E14_B',{r['evidence_id'] for r in tool.search(query='格力钛')})
        for e in self.read('verified_evidence.json'):
            actual=tool.get(e['evidence_id'])
            self.assertEqual(actual['text'],e['text'])
            self.assertTrue(actual['printed_page'])
            self.assertGreater(actual['pdf_page'],0)

    def test_full_and_focused_compatibility(self):
        for mode in ('full','focused'):
            payload,_=prepare(self.folder,mode=mode)
            self.assertTrue(payload['facts'])
            self.assertTrue(payload['evidence'])

    def test_mock_no_network_or_credentials(self):
        with tempfile.TemporaryDirectory() as tmp, patch('socket.socket',side_effect=AssertionError('network forbidden')), patch('tracelab.bailian.configuration',side_effect=AssertionError('credentials forbidden')):
            result=investigate(self.payload,self.read('investigation_plan.json'),MockDecider(),Path(tmp)/'run')
            self.assertEqual(result['status'],'pending_human_review')
            self.assertFalse(result['llm_called'])
            self.assertTrue(result['simulation'])
            self.assertTrue((Path(tmp)/'run/events.jsonl').exists())
