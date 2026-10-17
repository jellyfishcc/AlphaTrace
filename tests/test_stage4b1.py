"""Offline source boundary and fact tools; simulated receipts are test-only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tracelab.source_contract import bind_sources,digest
from tracelab.stage3 import validate
from tracelab.agent import LocalFacts,LocalEvidence,investigate,FactEvidenceMockDecider
from tracelab.final_release import load_agent_payload


class Script:
    def __init__(self,steps): self.steps=iter(steps)
    def decide(self,state): return next(self.steps)


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.payload={'periods':['2024','2025'],'facts':[{'fact_id':'operating_cashflow','name':'现金流',
            'amounts':{'base':{'元':'1.01'},'current':{'元':'2.02'},'change':{'元':'1.01'}},'evidence_ids':['NEW']}],
            'evidence':[{'evidence_id':'NEW','text':'年报披露收款增长。','source_type':'公开年报披露',
                'source_file':'report.pdf','pdf_page':1,'printed_page':'1','comparison_basis':'both_periods',
                'related_facts':['operating_cashflow']}],
            'analysis_contract':{'version':'v2','max_claims':2,'accounting_relations':[]}}
        self.bind_mock(self.payload)
        self.answer={'claims':[{'kind':'disclosure_explanation','statement':'年报披露收款增长。',
            'metric_ids':['operating_cashflow'],'citations':[{'evidence_id':'NEW','quote':'年报披露收款增长。'}],
            'amounts':[],'support_limit':'仅限披露，经营因果仍需复核','comparison_basis':'yoy','accounting_links':[]}],
            'questions':['是否存在其他影响？']}

    @staticmethod
    def bind_mock(payload):
        # Simulate the original-PDF reader, not production provenance bypass.
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'inputs').mkdir();(root/'inputs/report.pdf').write_bytes(b'synthetic PDF')
            (root/'inventory.json').write_text(json.dumps([{'key':'2025','file':'report.pdf','sha256':hashlib.sha256(b'synthetic PDF').hexdigest()}]))
            class Page:
                def extract_text(self): return '1\n年报披露收款增长。'
            class Reader:
                def __init__(self,path): self.pages=[Page()]
            with patch('pypdf.PdfReader',Reader): bind_sources(payload,root)

    def test_new_id_source_based_acceptance(self):
        self.assertEqual(validate(self.answer,self.payload)['status'],'needs_human_review')

    def test_unknown_id_rejected(self):
        self.answer['claims'][0]['citations'][0]['evidence_id']='fake'
        self.assertEqual(validate(self.answer,self.payload)['status'],'failed')

    def test_unverified_label_and_copied_receipt_rejected(self):
        for field,value in [('source_type','金融组内部报告'),('source_file','internal.docx'),('text','伪造'),('printed_page','2'),('related_facts',['net_profit'])]:
            p=copy.deepcopy(self.payload);p['evidence'][0][field]=value
            self.assertEqual(validate(self.answer,p)['status'],'failed')
        p=copy.deepcopy(self.payload);p.pop('source_contract');p['evidence'][0]['verified']=True
        self.assertEqual(validate(self.answer,p)['status'],'failed')

    def test_loader_rejects_forged_pdf_source_page_and_excerpt(self):
        for field,value in [('source_file','internal.docx'),('printed_page','2'),('text','伪造'),('source_type','内部报告')]:
            p=copy.deepcopy(self.payload);p['evidence'][0][field]=value
            with self.assertRaises(ValueError): self.bind_mock(p)

    def test_wrong_basis_and_quote(self):
        self.payload['evidence'][0]['comparison_basis']='current_period'
        self.bind_mock(self.payload)
        self.assertIn('比较口径',''.join(validate(self.answer,self.payload)['errors']))
        self.answer['claims'][0]['comparison_basis']='current_period'
        self.answer['claims'][0]['citations'][0]['quote']='年报没有的文字'
        self.assertIn('引文与原文',''.join(validate(self.answer,self.payload)['errors']))

    def test_model_cannot_declare_source_verified(self):
        self.answer['claims'][0]['source_contract']={'verified':True}
        self.assertEqual(validate(self.answer,self.payload)['status'],'failed')

    def test_wrong_fact_identity_cannot_be_bound(self):
        self.payload['facts'][0]['fact_id']='net_profit'
        with self.assertRaisesRegex(ValueError,'identity'): self.bind_mock(self.payload)

    def test_decider_cannot_mutate_authoritative_state(self):
        class Mutator:
            def decide(self,state):
                state['facts'][0]['amounts']['base']['元']='999'
                return {'action':'stop','arguments':{'reason':'模拟停止'}}
        self.run_agent(Mutator())
        self.assertEqual(self.payload['facts'][0]['amounts']['base']['元'],'1.01')

    def test_exact_amount_unit_and_immutable_tool(self):
        tool=LocalFacts(self.payload)
        row=tool.get('operating_cashflow')
        self.assertEqual(row['amounts']['base'],{'元':'1.01'})
        self.assertEqual(row['financial_level'],'经营现金流净额')
        row['amounts']['base']['元']='999'
        self.assertEqual(tool.get('operating_cashflow')['amounts']['base']['元'],'1.01')
        e=LocalEvidence(self.payload);e.get('NEW')['text']='changed'
        self.assertEqual(e.get('NEW')['text'],'年报披露收款增长。')

    def test_unknown_path_and_unverified_fact(self):
        for key in ('fake','../../secret','D:/data'):
            with self.assertRaises(ValueError): LocalFacts(self.payload).get(key)
        self.payload['facts'][0]['amounts']['base']['元']='999'
        self.assertEqual(LocalFacts(self.payload).list(),[])

    def test_unavailable_not_zero(self):
        f=self.payload['facts'][0];del f['amounts']['base'];del f['amounts']['change']
        self.bind_mock(self.payload)
        row=LocalFacts(self.payload).get(f['fact_id'])
        self.assertNotIn('base',row['amounts'])
        self.assertEqual(row['availability']['change'],'unavailable_not_zero')

    def run_agent(self,decider,**kwargs):
        with tempfile.TemporaryDirectory() as d, patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('tracelab.bailian.configuration',side_effect=AssertionError('credentials forbidden')):
            result=investigate(self.payload,{'signals':[],'investigation_tasks':[]},decider,Path(d)/'run',**kwargs)
            events=[json.loads(l) for l in (Path(d)/'run/events.jsonl').read_text(encoding='utf-8').splitlines()]
        return result,events

    def test_joint_mock_workflow_no_api(self):
        result,events=self.run_agent(FactEvidenceMockDecider())
        self.assertEqual(result['status'],'pending_human_review')
        self.assertEqual([e['action'] for e in events if e['event']=='tool_result'],['facts_list','fact_get','search','get'])
        self.assertFalse(result['llm_called'])

    def test_new_tools_limits_and_mutation_rejection(self):
        for kwargs,reason in [({'max_tools':1},'tool_limit'),({'max_rounds':1},'round_limit')]:
            result,_=self.run_agent(FactEvidenceMockDecider(),**kwargs)
            self.assertEqual(result['stop_reason'],reason)
        for decision in [{'action':'fact_get','arguments':{'fact_id':'operating_cashflow','value':'9'}},
                         {'action':'fact_set','arguments':{}},
                         {'action':'fact_get','arguments':{'fact_id':'x'*30001}}]:
            result,_=self.run_agent(Script([decision]))
            self.assertEqual(result['status'],'validation_failed')

    def test_fact_output_and_payload_size_limits(self):
        self.payload['facts'][0]['name']='x'*100001
        with self.assertRaises(ValueError): LocalFacts(self.payload)
        with patch.object(LocalFacts,'get',return_value={'large':'x'*100001}):
            # Reset the payload to isolate the output-size guard.
            self.setUp()
            result,_=self.run_agent(Script([{'action':'fact_get','arguments':{'fact_id':'operating_cashflow'}}]))
            self.assertIn('input_size_limit',result['errors'])


class RealSnapshotInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths=sorted(Path('outputs/final_release').glob('*/release_hashes.json'))
        if not paths: raise unittest.SkipTest('Local private final snapshot missing')
        cls.folder=paths[-1].parent
        with patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('tracelab.bailian.configuration',side_effect=AssertionError('credentials forbidden')):
            cls.payload,_=load_agent_payload(cls.folder)

    def test_old_and_new_disclosures_source_checks(self):
        facts={f['fact_id'] for f in self.payload['facts']}
        count=0
        for e in self.payload['evidence']:
            if not (e['evidence_id'].startswith('E07_') or e['evidence_id'] in {v['evidence_id'] for v in json.loads((self.folder/'verified_evidence.json').read_text(encoding='utf-8'))}): continue
            metrics=list(set(e['related_facts']) & facts)
            if not metrics: continue # E11 remains quarantined with its disputed fact.
            answer={'claims':[{'kind':'disclosure_explanation','statement':'年报披露相关项目情况。','metric_ids':metrics,
                'citations':[{'evidence_id':e['evidence_id'],'quote':e['text']}],'amounts':[],
                'support_limit':'仅检验来源与口径，具体经营因果仍需人工复核','accounting_links':[],
                'comparison_basis':'yoy' if e['comparison_basis']=='both_periods' else e['comparison_basis']}],
                'questions':['是否足以支持经营解释？']}
            self.assertEqual(validate(answer,self.payload)['errors'],[],e['evidence_id'])
            count+=1
        self.assertEqual(count,16)

    def test_conflicts_excluded_and_cash_amounts_match(self):
        tool=LocalFacts(self.payload)
        for key in ('cash_26','cash_27','fair_value_income','fee_income'):
            with self.assertRaises(ValueError): tool.get(key)
        for m in json.loads((self.folder/'cash_metrics.json').read_text(encoding='utf-8')):
            if m['item_id']=='cash_16': continue
            row=tool.get(m['item_id'])
            self.assertEqual(row['amounts']['base']['元'],m['base_amount'])
            self.assertEqual(row['amounts']['current']['元'],m['current_amount'])
            self.assertEqual(row['amounts']['change']['元'],m['difference'])
        row=tool.get('bill_deposits')
        self.assertEqual(row['availability']['base'],'unavailable_not_zero')
        self.assertEqual(len(json.loads((self.folder/'conflicts.json').read_text(encoding='utf-8'))),9)
