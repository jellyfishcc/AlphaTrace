"""Synthetic responses only. Assert sends, not only arithmetic."""
import unittest
from price_clock import fixed_price_clock
from decimal import Decimal
from unittest.mock import Mock,patch
from tracelab.cost_budget import CostLedger,guarded_send,price,ENDPOINT,check_live_price
from tracelab.qwen_decider import LiveBailianTransport,DecisionFailure
from tracelab.bailian import Config

class CostTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(fixed_price_clock())
    def send(self,ledger,a=100,b=20,bound=100):
        callback=Mock(return_value=({'usage':{'prompt_tokens':a,'completion_tokens':b}},'synthetic-id'))
        result=guarded_send(ledger,{'max_tokens':1200},callback,bound)
        self.assertEqual(callback.call_count,1)
        return result

    def test_below_budget_and_usage(self):
        l=CostLedger();self.send(l)
        self.assertEqual(l.rows[0]['accounted_cny'],str(price(100,20)))
        self.assertEqual(l.rows[0]['request_id'],'synthetic-id')

    def test_exact_boundary_then_block(self):
        l=CostLedger(str(price(100,1200)));self.send(l,b=1200)
        call=Mock()
        with self.assertRaisesRegex(ValueError,'cost_budget'):guarded_send(l,{'max_tokens':1200},call,100)
        call.assert_not_called()

    def test_over_budget_before_send(self):
        call=Mock()
        with self.assertRaisesRegex(ValueError,'cost_budget'):guarded_send(CostLedger('0.001'),{'max_tokens':1200},call,100)
        call.assert_not_called()

    def test_thirty_already_accounted_blocks(self):
        l=CostLedger();self.send(l);l.rows[0]['accounted_cny']='30.00' # synthetic exhausted ledger
        call=Mock()
        with self.assertRaisesRegex(ValueError,'cost_budget'):guarded_send(l,{'max_tokens':1200},call,100)
        call.assert_not_called()

    def test_input_token_budget(self):
        call=Mock()
        with self.assertRaisesRegex(ValueError,'token_budget'):guarded_send(CostLedger(),{'max_tokens':1200},call,60000)
        call.assert_not_called()

    def test_output_1200_recorded(self):
        l=CostLedger();self.send(l,b=1200);self.assertEqual(l.rows[0]['output_tokens'],1200)

    def test_five_requests_loop_sixth_blocked(self):
        l=CostLedger()
        for _ in range(5):self.send(l)
        call=Mock()
        for _ in range(3):
            with self.assertRaisesRegex(ValueError,'request_budget'):guarded_send(l,{'max_tokens':1200},call,100)
        call.assert_not_called()

    def test_timeout_preserves_reserve_no_retry(self):
        l=CostLedger();call=Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):guarded_send(l,{'max_tokens':1200},call,100)
        self.assertEqual(l.rows[0]['accounted_cny'],l.rows[0]['reserved_cny'])
        with self.assertRaisesRegex(ValueError,'cost_unknown'):guarded_send(l,{'max_tokens':1200},call,100)
        self.assertEqual(call.call_count,1)

    def test_missing_usage_blocks_followup(self):
        l=CostLedger();call=Mock(return_value=({},'synthetic-id'))
        with self.assertRaisesRegex(ValueError,'usage_unknown'):guarded_send(l,{'max_tokens':1200},call,100)
        with self.assertRaisesRegex(ValueError,'cost_unknown'):guarded_send(l,{'max_tokens':1200},call,100)
        self.assertEqual(call.call_count,1)

    def test_bound_violation_stops(self):
        l=CostLedger();call=Mock(return_value=({'usage':{'prompt_tokens':101,'completion_tokens':1}},'id'))
        with self.assertRaisesRegex(ValueError,'bound_violated'):guarded_send(l,{'max_tokens':1200},call,100)
        self.assertTrue(l.unknown);self.assertEqual(call.call_count,1)

    def test_live_no_reliable_request_bound_no_send(self):
        body=dict(model='qwen-plus',max_tokens=1200,enable_thinking=False,stream=False)
        with patch('tracelab.cost_budget.VERIFIED_DATE','2026-11-02'),patch('tracelab.bailian.configuration',return_value=Config('synthetic',ENDPOINT.removesuffix('/chat/completions'),'qwen-plus',{})),patch('tracelab.stage3.call_api') as call:
            with self.assertRaisesRegex(DecisionFailure,'token_budget_exhausted'):
                LiveBailianTransport(authorized=True,expected_endpoint=ENDPOINT).send(body,90,{})
            call.assert_not_called()

    def test_missing_price_and_model_endpoint(self):
        body=dict(model='qwen-plus',max_tokens=1200,enable_thinking=False,stream=False)
        with patch('tracelab.cost_budget.VERIFIED_DATE',None):
            with self.assertRaisesRegex(ValueError,'price_reverification'):check_live_price(body,ENDPOINT)
        for model,endpoint in [('other',ENDPOINT),('qwen-plus','https://example.test')]:
            with patch('tracelab.bailian.configuration',return_value=Config('synthetic',endpoint.removesuffix('/chat/completions') if endpoint==ENDPOINT else 'https://example.test/compatible-mode/v1',model,{})),patch('tracelab.stage3.call_api') as call:
                with self.assertRaisesRegex(DecisionFailure,'cost_model_endpoint_mismatch'):
                    LiveBailianTransport(authorized=True).send(dict(body,model=model),90,{})
                call.assert_not_called()

    def test_cache_discount_not_assumed_and_tiers(self):
        self.assertEqual(price(100000,1200),Decimal('0.0824'))
        self.assertEqual(price(200000,1200),Decimal('0.504'))
        self.assertEqual(price(997952,1200),Decimal('4.8477696'))

    def test_five_model_capacity_reservations_below_thirty(self):
        from tracelab.cost_budget import MODEL_INPUT_CEILING
        self.assertEqual(MODEL_INPUT_CEILING,997952)
        self.assertEqual(price(MODEL_INPUT_CEILING,1200)*5,Decimal('24.238848'))
        self.assertLess(price(MODEL_INPUT_CEILING,1200)*5,Decimal('30'))
