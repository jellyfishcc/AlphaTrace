"""Offline display boundary tests; no live model transport."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tracelab.display_export import build, financial_rows, investigation, public_only
from tracelab.source_contract import digest
from tracelab.stage3_input import sha

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOT=ROOT/'outputs/final_revision/20261017T093152-d80de1cefa'
AGENT=ROOT/'outputs/agent_live/20261017T151343-d0d3b954f5'


def fixture():
    e=dict(evidence_id='F_test',source_type='公开年报披露',source_file='synthetic.pdf',
        printed_page='1',pdf_page=2,text='合成样本 净利润 1.20 1.10',related_facts=['net_profit'],comparison_basis='both_periods')
    f=dict(fact_id='net_profit',name='净利润',evidence_ids=['F_test'],
        amounts={'base':{'元':'1.10'},'current':{'元':'1.20'},'change':{'元':'0.10'}})
    p=dict(company='合成公司',periods=['2024','2025'],currency='CNY',scope='合并',facts=[f],evidence=[e],
        source_contract={'facts':{'net_profit':digest(f)},'evidence':{'F_test':{
            'source_kind':'annual_report','file_sha256':'a'*64,'evidence_sha256':digest(e)}}})
    m=dict(item_id='net_profit',base_amount='1.10',current_amount='1.20',difference='0.10',yoy_percent='9.09')
    return p,[m]


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')


def disk_fixture(tmp):
    payload,metrics=fixture()
    snapshot=Path(tmp)/'snapshot'; agent=Path(tmp)/'run-1'
    save(snapshot/'manifest.json',{'id':'synthetic'})
    save(snapshot/'metrics.json',metrics); save(snapshot/'cash_metrics.json',[])
    result=dict(status='validation_failed',simulation=False,llm_called=True,decision_mode='qwen_real',
        errors=['incomplete_response'],tool_calls=1,rounds=2,real_request_attempts=2,
        stop_reason='invalid_decision_or_tool_error',goal='合成问题')
    events=[dict(event='started',time='2026-01-01T00:00:00Z'),
        dict(event='tool_result',round=1,action='get',arguments={'evidence_id':'F_test'},result=payload['evidence'][0]),
        dict(event='error',round=2,error='incomplete_response'),dict(event='finished',result=result)]
    save(agent/'investigation/input.json',payload)
    save(agent/'investigation/result.json',result); save(agent/'investigation/manifest.json',result)
    save(agent/'source_audit.json',{'source_manifest_sha256':sha(snapshot/'manifest.json'),'source_path':'D:/private/synthetic'})
    (agent/'investigation/events.jsonl').write_text('\n'.join(json.dumps(e,ensure_ascii=False) for e in events),encoding='utf-8')
    names=['investigation/input.json','investigation/result.json','investigation/manifest.json','investigation/events.jsonl','source_audit.json']
    save(agent/'audit_files_sha256.json',{n:sha(agent/n) for n in names})
    return payload,snapshot,agent


class DisplayExportTests(unittest.TestCase):
    def test_exact_strings_without_recalculation(self):
        p,m=fixture(); rows,_=financial_rows(p,m,[])
        self.assertEqual(rows[0]['base'],'1.10 元')
        self.assertEqual(rows[0]['delta'],'0.10 元')
        self.assertEqual(rows[0]['yoy'],'9.09%')
        self.assertEqual(rows[0]['impact'],'未提供')

    def test_missing_not_zero_or_bare_percent(self):
        p,m=fixture(); m[0]['yoy_percent']=''; m[0]['base_amount']=None
        rows,_=financial_rows(p,m,[])
        self.assertEqual(rows[0]['base'],'未提供')
        self.assertEqual(rows[0]['yoy'],'未提供')

    def test_wrong_amount_blocked(self):
        p,m=fixture(); m[0]['current_amount']='9.99'
        with self.assertRaisesRegex(ValueError,'amount_not_verified'): financial_rows(p,m,[])

    def test_duplicate_blocked(self):
        p,m=fixture()
        with self.assertRaisesRegex(ValueError,'duplicate'): financial_rows(p,m,m)

    def test_unverified_fact_not_exposed(self):
        p,m=fixture(); p['facts'][0]['amounts']['current']['元']='9.99'
        self.assertEqual(financial_rows(p,m,[]),[[],[]])

    def test_private_text_rejected(self):
        for value in ('D:\\private\\file','/home/alice/file','Bearer synthetic-token','api_key','金融组底稿.xlsx'):
            with self.subTest(value=value),self.assertRaises(ValueError): public_only({'text':value})

    def test_whitelisted_export_and_failure_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload,snapshot,agent=disk_fixture(tmp)
            before={p:sha(p) for p in agent.rglob('*') if p.is_file()}
            with patch('tracelab.display_export.load_agent_payload',return_value=(payload,{})):
                bundle=build(snapshot,agent)
            r=bundle['record']; self.assertEqual(r['run']['status'],'validation_failed')
            self.assertEqual([s['action'] for s in r['steps']],['get','error'])
            self.assertEqual(r['explanations'],[])
            self.assertNotIn('source_path',json.dumps(bundle))
            self.assertNotIn('D:/private',json.dumps(bundle))
            self.assertEqual(before,{p:sha(p) for p in before})

    def test_modified_agent_log_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,s,a=disk_fixture(tmp)
            with (a/'investigation/events.jsonl').open('a') as stream: stream.write('\n{}')
            with self.assertRaisesRegex(ValueError,'audit_hash'): investigation(a,p,s)

    def test_different_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,s,a=disk_fixture(tmp); save(s/'manifest.json',{'id':'different'})
            with self.assertRaisesRegex(ValueError,'snapshot_mismatch'): investigation(a,p,s)

    def test_mock_cannot_be_labelled_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,s,a=disk_fixture(tmp)
            result=json.loads((a/'investigation/result.json').read_text(encoding='utf-8')); result['simulation']=True
            save(a/'investigation/result.json',result)
            hashes=json.loads((a/'audit_files_sha256.json').read_text()); hashes['investigation/result.json']=sha(a/'investigation/result.json')
            save(a/'audit_files_sha256.json',hashes)
            with self.assertRaisesRegex(ValueError,'inconsistent_agent_run'): investigation(a,p,s)

    @unittest.skipUnless((SNAPSHOT/'inventory.json').exists() and (AGENT/'audit_files_sha256.json').exists(),'private local runs absent')
    def test_real_export_every_amount_and_source(self):
        from tracelab.final_release import load_agent_payload
        bundle=build(SNAPSHOT,AGENT); r=bundle['record']
        originals={m['item_id']:m for name in ('metrics.json','cash_metrics.json') for m in json.loads((SNAPSHOT/name).read_text(encoding='utf-8'))}
        for m in r['metrics']+r['cashMetrics']:
            for field,key in [('base','base_amount'),('current','current_amount'),('change','difference')]:
                self.assertEqual(m['rawAmounts'][field],originals[m['id']].get(key))
        payload,_=load_agent_payload(SNAPSHOT)
        sources={e['evidence_id']:e for e in payload['evidence']}
        for e in r['evidence']:
            original=sources[e['id']]
            self.assertEqual((e['quote'],e['pdfPage'],e['printPage']),
                (original['text'],str(original['pdf_page']),str(original['printed_page'])))
        self.assertEqual([s['action'] for s in r['steps']],['search','get','error'])
        self.assertEqual(r['agentSummary']['real_request_attempts'],3)
        self.assertEqual(r['agentSummary']['tool_calls'],2)
        self.assertEqual(r['agentSummary']['errors'],['incomplete_response'])
        public_only(bundle)


if __name__=='__main__': unittest.main()
