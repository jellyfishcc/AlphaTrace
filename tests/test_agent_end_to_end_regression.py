"""Cross-file offline acceptance. Historical responses immutable; positives synthetic."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_evidence_provenance as fixtures
from test_qwen_decider import reply
from tracelab.agent import investigate
from tracelab.investigation import prepare_scoped_investigation
from tracelab.agent_live import GOAL,BUDGET,FACTS
from tracelab.qwen_decider import QwenDecider,ReplayTransport

class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.EvidenceTests();self.f.setUp();self.p=self.f.payload
    def run_audit(self,label,responses):
        root=Path(tempfile.mkdtemp(prefix='phase5-'+label+'-',dir='tmp'))
        plan=prepare_scoped_investigation(self.p,GOAL)
        d=QwenDecider(self.p,self.f.scope,ReplayTransport(responses),budget=BUDGET,initial_fact_ids=FACTS)
        with patch('socket.socket',side_effect=AssertionError('offline only')),patch('tracelab.bailian.configuration',side_effect=AssertionError('no credentials')):
            r=investigate(self.p,plan,d,root/'investigation',5,4)
        out=root/'investigation'
        read=lambda n:json.loads((out/n).read_text(encoding='utf-8'))
        ledger=read('task_progress.json');events=[json.loads(l) for l in (out/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(r,read('result.json'));self.assertEqual(ledger,r['investigation_task_progress'])
        self.assertEqual([t['id'] for t in read('plan.json')['investigation_tasks']],[t['task_id'] for t in ledger['tasks']])
        self.assertEqual(len(ledger['tasks']),5)
        self.assertEqual(events[-1]['result'],r)
        tool_events=[e for e in events if e['event']=='tool_result']
        self.assertEqual(len(tool_events),r['tool_calls'])
        self.assertEqual(sorted({eid for a in r['retrieval_audit'] for eid in a['evidence_ids']}),r['retrieved_evidence_ids'])
        records=[read(str(p.relative_to(out))) for p in sorted((out/'decisions').glob('*.json'))]
        self.assertEqual(records,d.records);self.assertEqual(len(records),r['model_requests'])
        self.assertTrue(r['simulation']);self.assertFalse(r['llm_called']);self.assertEqual(r['retries'],0)
        self.assertIsNone(r['actual_total_tokens']);self.assertIsNone(r['cost']);self.assertEqual(r['cost_status'],'not_applicable_simulation')
        self.assertEqual(sum(x['usage']['input_tokens']+x['usage']['output_tokens'] for x in records),r['reported_total_tokens'])
        self.assertTrue(r['unresolved_task_ids']);self.assertTrue(r['task_evidence_gaps'])
        self.assertEqual(read('input.json'),self.p)
        self.assertEqual(self.p['analysis_contract']['accounting_relations'],[])
        (root/'fixture.json').write_text(json.dumps(dict(label=label,simulation=True,historical_source=str(fixtures.ROOT),status=r['status']),ensure_ascii=False),encoding='utf-8')
        with Path('tmp/phase5-artifact-index.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(label=label,path=str(root.resolve()),status=r['status']))+'\n')
        return r,read,out
    def searches(self):
        return [dict(action='search',arguments={'metric_id':m}) for m in ('net_profit','operating_cashflow')]
    def test_historical_response_and_failure_audit(self):
        responses=[];saved=[]
        for i in range(1,4):
            s=json.loads((fixtures.ROOT/f'decisions/{i:02d}.json').read_text(encoding='utf-8'));saved.append(s)
            responses.append(dict(usage={'prompt_tokens':s['usage']['input_tokens'],'completion_tokens':s['usage']['output_tokens']},choices=[dict(finish_reason=s['response']['finish_reason'],message={'content':s['response']['messages'][0]['text']})]))
        r,read,out=self.run_audit('historical-original',responses)
        self.assertEqual(r['status'],'validation_failed');self.assertEqual(r['termination_category'],'explain_precheck_rejected')
        self.assertEqual((r['model_requests'],r['tool_calls']),(3,2));self.assertEqual(len(r['retrieval_audit'][0]['evidence_ids']),5)
        self.assertIn('F_net_profit',r['evidence_gap']['ineligible_citation_ids'])
        self.assertEqual(r['investigation_task_progress']['tasks'][0]['status'],'pending')
        self.assertFalse((out/'checks.json').exists()) # Validator was not reached; never fabricate checks.
        for i,s in enumerate(saved,1):
            record=read(f'decisions/{i:02d}.json');self.assertEqual(record['action'],s['action']);self.assertEqual(record['response']['messages'],s['response']['messages'])
    def test_synthetic_searches_limited_explain_audit(self):
        actions=self.searches()+[dict(action='get',arguments={'evidence_id':'E07_28'}),self.f.clean_explain()]
        r,read,out=self.run_audit('synthetic-limited-success',[reply(a) for a in actions])
        self.assertEqual(r['status'],'pending_human_review');self.assertEqual(r['termination_category'],'human_review_required')
        self.assertTrue(read('evidence_precheck.json')['ready']);self.assertEqual(read('checks.json')['errors'],[])
        self.assertEqual([t['status'] for t in r['investigation_task_progress']['tasks']],['answered']*3+['evidence_gap']*2)
        self.assertEqual(read('analysis.json'),actions[-1]['arguments']['analysis']);self.assertTrue(r['manual_review'])
    def test_synthetic_validator_rejection_audit(self):
        bad=self.f.clean_explain();bad['arguments']['analysis']['claims'][0]['citations'][0]['quote']='伪造净利润引文'
        actions=self.searches()+[dict(action='get',arguments={'evidence_id':'E07_28'}),bad]
        r,read,out=self.run_audit('synthetic-invalid-quote',[reply(a) for a in actions])
        self.assertTrue(read('evidence_precheck.json')['ready']);self.assertEqual(r['termination_category'],'validator_rejected')
        self.assertEqual(r['status'],'validation_failed');self.assertEqual(r['errors'],read('checks.json')['errors'])
        self.assertTrue(any('引文与原文不一致' in e for e in r['errors']));self.assertIsNone(r['evidence_gap'])
