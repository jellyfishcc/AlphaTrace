"""No real network or credential reads; send counts are asserted."""
import io
import json
import unittest
from price_clock import fixed_price_clock
from unittest.mock import patch,Mock
from urllib.error import HTTPError
from tracelab.qwen_decider import LiveBailianTransport,DecisionFailure,Budget
from tracelab.bailian import Config
from tracelab.cost_budget import ENDPOINT,CostLedger,guarded_send,check_free_tier_confirmation
import test_qwen_decider as qwen_tests
from test_qwen_decider import reply

class FreeTierTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(fixed_price_clock())
        self.body=dict(model='qwen-plus',max_tokens=1200,stream=False,enable_thinking=False)
        self.config=Config('synthetic',ENDPOINT.removesuffix('/chat/completions'),'qwen-plus',{})
        self.stop=dict(action='stop',arguments={'reason':'已检索但缺少原因披露'})
        self.q=qwen_tests.QwenTests();self.q.setUp()

    def live(self):
        return LiveBailianTransport(authorized=True,expected_endpoint=ENDPOINT,free_tier_workspace_confirmed=True)

    def test_correct_model_region_and_free_tier_send_once(self):
        t=self.live()
        with patch('tracelab.bailian.configuration',return_value=self.config),patch('tracelab.stage3.call_api',return_value=(reply(self.stop),'synthetic-id')) as call:
            t.send(self.body,90,{})
        call.assert_called_once();self.assertEqual(call.call_args.args[0]['model'],'qwen-plus')
        self.assertEqual(call.call_args.args[0]['max_tokens'],1200)
        self.assertEqual(t.cost_ledger.rows[0]['input_tokens'],100)

    def test_model_region_and_key_mismatch_zero_sends(self):
        for kind in ('model','region','key'):
            c=Config('' if kind=='key' else 'synthetic','https://example.test/compatible-mode/v1' if kind=='region' else self.config.base_url,'qwen-plus',{})
            body=dict(self.body,model='qwen-plus-latest' if kind=='model' else 'qwen-plus')
            with patch('tracelab.bailian.configuration',return_value=c),patch('tracelab.stage3.call_api') as call:
                with self.assertRaises(DecisionFailure):self.live().send(body,90,{})
                call.assert_not_called()

    def test_free_tier_403_fixed_code_and_no_retry(self):
        for payload in ({'error':{'code':'AllocationQuota.FreeTierOnly','message':'DO_NOT_LOG'}},{'code':'AllocationQuota.FreeTierOnly'}):
            error=HTTPError(ENDPOINT,403,'private',{},io.BytesIO(json.dumps(payload).encode()))
            r,d,_,_=self.q.run_agent([error,reply(self.stop)])
            self.assertEqual(r['errors'],['free_tier_exhausted']);self.assertEqual(d.attempts,1)
            self.assertNotIn('DO_NOT_LOG',json.dumps(d.records))
            with self.assertRaisesRegex(DecisionFailure,'no_retry'):d.decide(self.q.state)

    def test_unrelated_403_not_mislabeled(self):
        error=HTTPError(ENDPOINT,403,'private',{},io.BytesIO(b'{"error":{"code":"Other"}}'))
        r,d,_,_=self.q.run_agent([error]);self.assertEqual(r['errors'],['HTTPError'])
        self.assertEqual(d.attempts,1)

    def test_timeout_or_missing_usage_preserves_reserve_and_stops(self):
        for response in (TimeoutError(),(reply(self.stop,usage=False),'id')):
            t=self.live()
            with patch('tracelab.bailian.configuration',return_value=self.config),patch('tracelab.stage3.call_api',side_effect=response if isinstance(response,Exception) else None,return_value=response) as call:
                with self.assertRaises((TimeoutError,DecisionFailure)):t.send(self.body,90,{})
                with self.assertRaisesRegex(DecisionFailure,'cost_unknown'):t.send(self.body,90,{})
                self.assertEqual(call.call_count,1)
            self.assertEqual(t.cost_ledger.rows[0]['accounted_cny'],t.cost_ledger.rows[0]['reserved_cny'])

    def test_usage_accumulation_target_boundary_no_sixth_or_followup(self):
        d=self.q.decider([reply(self.stop) for _ in range(6)],budget=Budget(max_requests=5))
        for _ in range(5):d.decide(self.q.state)
        self.assertEqual(d.actual_input,500);self.assertEqual(d.actual_output,100)
        with self.assertRaisesRegex(DecisionFailure,'request_budget'):d.decide(self.q.state)
        self.assertEqual(d.attempts,5)

    def test_sixty_thousand_stops_after_response(self):
        raw=reply(self.stop);raw['usage']=dict(prompt_tokens=58800,completion_tokens=1200)
        d=self.q.decider([raw,reply(self.stop)])
        d.decide(self.q.state)
        self.assertEqual(d.actual_input+d.actual_output,60000)
        with self.assertRaisesRegex(DecisionFailure,'token_budget'):d.decide(self.q.state)
        self.assertEqual(d.attempts,1)

    def test_one_request_overshoot_recorded_then_failure(self):
        raw=reply(self.stop);raw['usage']=dict(prompt_tokens=60000,completion_tokens=1200)
        r,d,_,_=self.q.run_agent([raw,reply(self.stop)])
        self.assertEqual(r['errors'],['actual_token_budget_exceeded'])
        self.assertEqual(r['known_input_tokens']+r['known_output_tokens'],61200)
        self.assertEqual(d.attempts,1)

    def test_byte_estimate_is_not_send_budget(self):
        d=self.q.decider([reply(self.stop)])
        d.charged=60000 # historical rough estimates must not masquerade as usage
        d.decide(self.q.state);self.assertEqual(d.attempts,1)
        self.assertFalse(d.context(self.q.state)['remaining']['input_token_bound_known'])

    def test_auxiliary_thirty_yuan_and_usage_mode(self):
        l=CostLedger(token_mode='usage_target');call=Mock(return_value=({'usage':dict(prompt_tokens=58800,completion_tokens=1200)},'id'))
        guarded_send(l,self.body,call,997952)
        with self.assertRaisesRegex(ValueError,'token_budget'):guarded_send(l,self.body,call,997952)
        self.assertEqual(call.call_count,1)
        l=CostLedger('1',token_mode='usage_target');call=Mock()
        with self.assertRaisesRegex(ValueError,'cost_budget'):guarded_send(l,self.body,call,997952)
        call.assert_not_called()

    def test_workspace_confirmation_required(self):
        with self.assertRaisesRegex(ValueError,'workspace_unconfirmed'):check_free_tier_confirmation(False)
        check_free_tier_confirmation(True)

    def test_expired_price_blocks_before_reservation_and_send(self):
        from datetime import datetime
        from price_clock import BEIJING
        with fixed_price_clock(datetime(2026,11,3,0,tzinfo=BEIJING)), patch('tracelab.bailian.configuration',return_value=self.config), patch('tracelab.stage3.call_api') as call:
            t=self.live()
            with self.assertRaisesRegex(DecisionFailure,'price_reverification_required'):t.send(self.body,90,{})
            call.assert_not_called();self.assertEqual(t.cost_ledger.rows,[])

    def test_beijing_date_not_utc_date_controls_send(self):
        from datetime import datetime,timezone
        # Both instants are Nov 2 UTC; Beijing switches to Nov 3 at 16:00 UTC.
        for hour,allowed in ((15,True),(16,False)):
            with self.subTest(hour=hour), fixed_price_clock(datetime(2026,11,2,hour,59,tzinfo=timezone.utc)), patch('tracelab.bailian.configuration',return_value=self.config), patch('tracelab.stage3.call_api',return_value=(reply(self.stop),'synthetic')) as call:
                if allowed:self.live().send(self.body,90,{})
                else:
                    with self.assertRaisesRegex(DecisionFailure,'price_reverification_required'):self.live().send(self.body,90,{})
                self.assertEqual(call.call_count,int(allowed))

    def test_unsupported_billing_features_never_send(self):
        for fields,code in (({'enable_thinking':True},'unsupported_billing_mode'),({'stream':True},'unsupported_billing_mode'),({'enable_search':True},'unsupported_billable_feature')):
            with self.subTest(fields=fields), patch('tracelab.bailian.configuration',return_value=self.config), patch('tracelab.stage3.call_api') as call:
                with self.assertRaisesRegex(DecisionFailure,code):self.live().send(dict(self.body,**fields),90,{})
                call.assert_not_called()

    def test_expired_free_tier_still_blocks_with_valid_price_date(self):
        with patch('tracelab.cost_budget.FREE_TIER',dict(expires='2026-11-02')), patch('tracelab.bailian.configuration',return_value=self.config), patch('tracelab.stage3.call_api') as call:
            with self.assertRaisesRegex(DecisionFailure,'free_tier_confirmation_expired'):self.live().send(self.body,90,{})
            call.assert_not_called()
