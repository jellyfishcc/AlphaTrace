"""Prompt presence and synthetic offline contracts, not live model behavior."""
import json
import unittest
from pathlib import Path
import test_investigation_flow as flow
import test_semantic_boundary as semantic
from tracelab.stage3 import validate

class OutputContractTests(unittest.TestCase):
    def setUp(self):
        self.prompt=Path('prompts/agent_decision_v1.txt').read_text(encoding='utf-8')
        self.f=flow.FlowTests();self.f.setUp()
        self.s=semantic.SemanticTests();self.s.setUp()
    def rules(self,*words):
        for w in words:self.assertIn(w,self.prompt)
    def test_name_rules(self):self.rules('canonical','net_profit是净利润','parent_profit是归母净利润','金额相等也不等价')
    def test_amount_rules(self):self.rules('fact_id、field、unit及期间','不自行补算或重算change','amounts仅列')
    def test_ratio_rules(self):self.rules('ratios_allowed=false','真实比例仅可留在原文quote','不授权正文声明')
    def test_candidate_rules(self):self.rules('candidate_evidence_ids只是候选','eligible_evidence_ids可引用','指定PDF换行交核验器')
    def test_relation_rules(self):self.rules('空清单时必须输出空数组','不得由cash_2、cash_6增量推导','主要原因不能表述为完整覆盖')
    def test_task_rules(self):self.rules('pending尚未回答','evidence_gap不是验证成功','不要求五类全answered','questions保留unresolved_questions')
    def test_compact_rules(self):self.rules('remaining.max_output_tokens','连续、逐字','不提交半截analysis','Validator有最终核验权')
    def test_context_names_and_candidates(self):
        r,d,_=self.f.run_steps([dict(action='stop',arguments={'reason':'缺少本轮净利润来源'})])
        c=json.loads(d.records[0]['request']['messages'][1]['content'])
        fact=next(f for f in c['initial_facts'] if f['fact_id']=='net_profit')
        self.assertEqual((fact['name'],fact['financial_level']),('净利润','净利润'))
        self.assertIn('F_net_profit',c['investigation_task_progress']['candidate_evidence_ids'])
        self.assertNotIn('F_net_profit',c['evidence_progress']['eligible_evidence_ids'])
        self.assertEqual(c['accounting_relations'],[])
    def test_quote_ratio_and_body_ratio(self):
        r=self.s.disclosure();self.assertFalse(self.s.p['analysis_contract']['ratios_allowed'])
        self.assertIn('57.93%',r['claims'][0]['citations'][0]['quote'])
        self.assertEqual(validate(r,self.s.p)['errors'],[])
        r['claims'][0]['statement']+='增长57.93%'
        self.assertTrue(any('自由文本' in e for e in validate(r,self.s.p)['errors']))
    def test_wrong_name_rejected(self):
        self.assertTrue(any('metric_scope_conflict' in e for e in self.s.check(self.s.fact('归母净利润下降'))['errors']))
    def test_wrong_amount_rejected(self):
        r=self.s.fact();r['claims'][0]['amounts']=[dict(fact_id='net_profit',field='current',unit='元',value='1')]
        self.assertTrue(any('金额、期间或单位' in e for e in self.s.check(r)['errors']))
    def test_overclaim_rejected(self):
        self.assertTrue(any('support_scope_overreach' in e for e in self.s.check(self.s.disclosure(limit='该解释覆盖全部净额变化'))['errors']))
    def test_illegal_citation_and_original_history(self):
        self.f.test_historical_responses_unchanged_still_rejected()
        r,_,_=self.f.run_steps([self.f.f.clean_explain()])
        self.assertEqual(r['status'],'validation_failed')
    def test_synthetic_limited_explain_and_byte_budget(self):
        r,d,_=self.f.run_steps(self.f.ready()+[self.f.f.clean_explain()])
        self.assertEqual(r['status'],'pending_human_review');self.assertTrue(r['manual_review'])
        for rec in d.records:
            self.assertLessEqual(sum(len(m['content'].encode()) for m in rec['request']['messages']),d.budget.max_input_bytes)
            self.assertEqual(rec['request']['max_tokens'],1200)
        self.assertEqual(d.budget.max_requests,5);self.assertEqual(d.budget.total_tokens,60000)
    def test_stop_and_tool_request_guards(self):
        self.f.test_stop_preserves_missing_tasks()
        self.f.test_budget_stop_preserves_unresolved()
        self.f.test_duplicate_tool_still_rejected()
