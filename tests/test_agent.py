"""Mock-only orchestration tests, with network and credential access denied."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tracelab.agent import LocalEvidence, MockDecider, investigate
from tracelab.investigation import prepare_investigation


class Script:
    def __init__(self, decisions): self.decisions=iter(decisions)
    def decide(self,state): return next(self.decisions)


class AgentTests(unittest.TestCase):
    def setUp(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/qwen_focused_validation_failure.json').read_text(encoding='utf-8'))
        self.payload=fixture['input']
        self.plan=prepare_investigation([
            {'item_id':'net_profit','difference':'-10','status':'calculated'},
            {'item_id':'operating_cashflow','difference':'20','status':'calculated'}])
        self.answer=fixture['analysis']
        self.answer['claims'][0]['metric_ids'].append('bill_deposits')
        self.answer['claims'][1]['statement']='年报披露经营现金流同比增长，主要系销售回款和其他经营收款增加。'

    def run_script(self,decider,**limits):
        with tempfile.TemporaryDirectory() as d, patch('socket.socket',side_effect=AssertionError('network forbidden')), \
             patch('tracelab.bailian.configuration',side_effect=AssertionError('credentials forbidden')), \
             patch('tracelab.stage3.call_api',side_effect=AssertionError('API forbidden')):
            folder=Path(d)/'run'
            result=investigate(self.payload,self.plan,decider,folder,**limits)
            events=[json.loads(line) for line in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
            return result,events

    def test_mock_workflow_and_complete_logs_no_network(self):
        result,events=self.run_script(MockDecider())
        self.assertEqual(result['status'],'pending_human_review')
        self.assertTrue(result['simulation']); self.assertFalse(result['llm_called'])
        self.assertEqual([e['action'] for e in events if e['event']=='tool_result'],['list','search','get'])
        self.assertEqual(len([e for e in events if e['event']=='decision']),4)
        self.assertEqual(events[-1]['event'],'finished')
        self.assertIn('走势分化',result['goal'])

    def test_local_tools_by_metric_keyword_and_id(self):
        tools=LocalEvidence(self.payload)
        self.assertEqual(len(tools.list()),5)
        self.assertTrue(tools.search(metric_id='bill_deposits'))
        self.assertTrue(tools.search(query='受限资金'))
        e=tools.get('E07_29')
        self.assertEqual(e['printed_page'],'29')
        self.assertTrue(e['text']); self.assertTrue(e['source_file'])
        e['text']='mutated'
        self.assertNotEqual(tools.get('E07_29')['text'],'mutated')

    def test_unknown_evidence_rejected(self):
        result,events=self.run_script(Script([{'action':'get','arguments':{'evidence_id':'fake'}}]))
        self.assertEqual(result['status'],'validation_failed')
        self.assertIn('unknown_evidence_id',result['errors'])
        self.assertTrue(any(e['event']=='error' for e in events))

    def test_insufficient_stops(self):
        result,_=self.run_script(Script([{'action':'stop','arguments':{'reason':'没有足够证据'}}]))
        self.assertEqual(result['status'],'insufficient_evidence')

    def test_round_limit(self):
        result,_=self.run_script(MockDecider(),max_rounds=1)
        self.assertEqual(result['status'],'insufficient_evidence')
        self.assertEqual(result['stop_reason'],'round_limit')

    def test_tool_limit(self):
        result,_=self.run_script(MockDecider(),max_tools=1)
        self.assertEqual(result['tool_calls'],1)
        self.assertEqual(result['stop_reason'],'tool_limit')

    def test_illegal_action_rejected(self):
        result,_=self.run_script(Script([{'action':'exec','arguments':{'code':'print(1)'}}]))
        self.assertEqual(result['status'],'validation_failed')

    def test_unretrieved_citation_rejected(self):
        result,_=self.run_script(Script([{'action':'explain','arguments':{'analysis':self.answer}}]))
        self.assertEqual(result['status'],'validation_failed')
        self.assertIn('不存在的证据',''.join(result['errors']))

    def test_bad_amount_and_quote_preserve_all_errors_even_on_stop(self):
        answer=copy.deepcopy(self.answer)
        answer['claims'][0]['amounts'][0]['value']='1'
        answer['claims'][1]['citations'][0]['quote']='虚构原文'
        result,_=self.run_script(Script([
            {'action':'search','arguments':{'metric_id':'operating_cashflow'}},
            {'action':'stop','arguments':{'reason':'证据不足','analysis':answer}}]))
        self.assertEqual(result['status'],'validation_failed')
        self.assertIn('金额、期间或单位',''.join(result['errors']))
        self.assertIn('引文与原文',''.join(result['errors']))

    def test_size_limit_blocks_decision(self):
        result,_=self.run_script(Script([{'action':'stop','arguments':{'reason':'x'*30001}}]))
        self.assertEqual(result['status'],'validation_failed')
        self.assertIn('input_size_limit',result['errors'])

    def test_unknown_question(self):
        result,_=self.run_script(Script([{'action':'search','arguments':{'question_index':999}}]))
        self.assertIn('unknown_question',result['errors'])

    def test_malformed_decision(self):
        for decision in ([],{'action':'get'}, {'action':'get','arguments':[]}):
            result,_=self.run_script(Script([decision]))
            self.assertEqual(result['status'],'validation_failed')
