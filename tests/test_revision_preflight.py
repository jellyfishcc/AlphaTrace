"""Revision acceptance and bounded preflight; no actual credentials or network."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tracelab.final_release import load_agent_payload
from tracelab.source_io import read_xlsx
from tracelab.stage3_input import read,sha
from tracelab.agent import LocalFacts
from tracelab.stage3 import validate
from tracelab.agent_preflight import FACTS,EVIDENCE,prepare,configuration_presence
from tracelab.qwen_decider import QwenDecider,ReplayTransport,ExportScope


class ConfigMetadataTests(unittest.TestCase):
    def test_presence_never_reads_key(self):
        class NamesOnly:
            def __iter__(self):return iter(['DASHSCOPE_API_KEY'])
            def __getitem__(self,key):raise AssertionError('key read forbidden')
        with patch('tracelab.agent_preflight.os.environ',NamesOnly()),patch('tracelab.agent_preflight.os.name','posix'),patch('tracelab.agent_preflight.setting',return_value=('https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1','test')) as setting:
            result=configuration_presence()
        self.assertTrue(result['ready']);self.assertFalse(result['key_value_read'])
        setting.assert_called_once_with('DASHSCOPE_BASE_URL')

    def test_wrong_region_blocks(self):
        with patch('tracelab.agent_preflight.os.name','posix'),patch('tracelab.agent_preflight.setting',return_value=('https://example.com/compatible-mode/v1','test')):
            self.assertFalse(configuration_presence()['ready'])


class RevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folders=sorted(Path('outputs/final_revision').glob('*/release_hashes.json'))
        if not folders:raise unittest.SkipTest('Local revision snapshot missing')
        cls.folder=folders[-1].parent
        with patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('tracelab.bailian.configuration',side_effect=AssertionError('key forbidden')):
            cls.payload,cls.audit=load_agent_payload(cls.folder)

    def test_actual_revision_files_and_hashes(self):
        for v in read(self.folder/'revision_checks.json')['file_versions']:
            self.assertNotEqual(v['old_sha256'],v['new_sha256'])
            self.assertEqual(sha(self.folder/'inputs'/v['new_file']),v['new_sha256'])

    def test_all_nine_resolutions_have_sources(self):
        rows=read(self.folder/'conflicts.json');self.assertEqual(len(rows),9)
        self.assertTrue(all(r['status']=='resolved' and r['verification'] for r in rows))

    def test_core_cash_and_bridges_unchanged(self):
        parent=Path(read(self.folder/'manifest.json')['previous_run'])
        for name in ('metrics.json','cash_metrics.json','bridges.json','cash_bridges.json'):
            self.assertEqual(sha(self.folder/name),sha(parent/name))
        checks=read(self.folder/'revision_checks.json')
        self.assertTrue(all(c['status']=='exact' for c in checks['other_cash_details']))
        self.assertEqual(len(checks['other_cash_details']),4)

    def test_blank_correct_year_not_zero(self):
        x=read_xlsx(next((self.folder/'inputs').glob('*底稿*版(1).xlsx')))['经营现金流']
        for row,amount in [(26,'950809072.53'),(27,'21684919.23')]:
            self.assertEqual(x[row][f'B{row}']['value'],amount)
            self.assertIsNone(x[row][f'C{row}']['value'])
            with self.assertRaises(ValueError):LocalFacts(self.payload).get(f'cash_{row}')

    def test_restored_fact_verified_and_quote_valid(self):
        tool=LocalFacts(self.payload);self.assertEqual(len(tool.list()),45)
        fact=tool.get('fair_value_income')
        self.assertEqual(fact['amounts']['current']['元'],'164255550.24')
        e=next(e for e in self.payload['evidence'] if e['evidence_id']=='E11')
        a={'claims':[dict(kind='disclosure_explanation',statement='年报披露公允价值变动情况',metric_ids=['fair_value_income'],
           citations=[dict(evidence_id='E11',quote=e['text'])],amounts=[],support_limit='仅限原文披露，原因仍需核验',
           accounting_links=[],comparison_basis='yoy')],'questions':['是否有进一步经营原因证据？']}
        self.assertEqual(validate(a,self.payload)['status'],'needs_human_review')
        a['claims'][0]['citations'][0]['quote']='虚构原文'
        self.assertEqual(validate(a,self.payload)['status'],'failed')

    def test_unresolved_display_still_blocked(self):
        # Change only the loader's conflict view in a test double; immutable files untouched.
        from tracelab import final_release
        original=final_release.read
        def read_conflicts(path):
            result=original(path)
            if Path(path).name=='conflicts.json':
                for row in result:
                    if row['kind']=='word_display_conflict':row['status']='unresolved'
            return result
        with patch('tracelab.final_release.read',side_effect=read_conflicts):p,_=load_agent_payload(self.folder)
        with self.assertRaises(ValueError):LocalFacts(p).get('fair_value_income')

    def test_scope_initial_facts_cannot_expand(self):
        scope=ExportScope(frozenset(FACTS),frozenset(EVIDENCE),'offline_test')
        with self.assertRaises(ValueError):QwenDecider(self.payload,scope,ReplayTransport([]),initial_fact_ids=['fair_value_income'])
        d=QwenDecider(self.payload,scope,ReplayTransport([]),initial_fact_ids=FACTS)
        c=d.context({'goal':'调查','questions':[],'history':[]})
        self.assertEqual(len(c['initial_facts']),4)
        self.assertTrue(all(not f['retrieved_source_quotes'] for f in c['initial_facts']))

    def test_preflight_scope_budget_and_exact_request(self):
        with tempfile.TemporaryDirectory() as d,patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('tracelab.bailian.configuration',side_effect=AssertionError('key forbidden')),patch('tracelab.agent_preflight.load_agent_payload',return_value=(copy.deepcopy(self.payload),self.audit)):
            out,r=prepare(self.folder,Path(d),config_check=lambda:{'ready':True,'key_value_read':False})
            self.assertEqual(r['status'],'ready_pending_authorization');self.assertFalse(r['real_api_called'])
            self.assertEqual(r['budget']['max_requests'],5);self.assertEqual(r['max_rounds'],5)
            self.assertEqual(r['replay_requests'],3);self.assertIsNone(r['estimated_cny'])
            request=read(out/'first_request_not_called.json')
            self.assertEqual(request,read(out/'offline_replay/decisions/01.json')['request'])
            final_context=json.loads(read(out/'offline_replay/decisions/03.json')['request']['messages'][1]['content'])
            net=next(f for f in final_context['initial_facts'] if f['fact_id']=='net_profit')
            self.assertTrue(net['retrieved_source_quotes'])
            self.assertNotIn('conflicts.json',json.dumps(request));self.assertNotIn('.docx',json.dumps(request))
