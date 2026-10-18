"""Offline boundary tests, using synthetic records and mocked existing verifiers."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tracelab.display_modules import report_section, pdf_section, row
from tracelab.stage3_input import sha


class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def save(self,name,value):
        (self.root/name).write_text(json.dumps(value),encoding='utf-8')

    def test_blank_is_not_zero(self):
        self.assertEqual(row([None,'','0.00'])['cells'],['未提供','未提供','0.00'])

    def report(self, status='发现错误'):
        claim=json.loads((Path(__file__).resolve().parents[1]/'examples/report_check/gree_direction_error.json').read_text(encoding='utf-8'))
        audit={'source_run':'synthetic','input_hashes':{},'extension_hashes':{}}
        result=dict(claim=claim,status=status,errors=[],sources=[],correction=None,process=[],simulation=False,llm_called=False)
        self.save('result.json',dict(result,source_audit=audit))
        return result,audit

    def test_statuses_preserved(self):
        for status in ['发现错误','一致','无法核实']:
            result,audit=self.report(status)
            with patch('tracelab.display_modules.check_claim',return_value=result):
                actual=report_section(self.root,self.root,{},audit)
            self.assertEqual(actual['rows'][0]['cells'][1],status)

    def test_report_tamper_rejected(self):
        result,audit=self.report()
        result=copy.deepcopy(result);result['status']='一致'
        with patch('tracelab.display_modules.check_claim',return_value=result),self.assertRaisesRegex(ValueError,'result_mismatch'):
            report_section(self.root,self.root,{},audit)

    def test_report_wrong_snapshot_rejected(self):
        _,audit=self.report();audit['source_run']='another'
        with self.assertRaisesRegex(ValueError,'snapshot_mismatch'):report_section(self.root,self.root,{},audit)

    def pdf(self):
        self.save('extracted_financial.json',[])
        self.save('comparison.json',[])
        audit=dict(source_run=str(self.root),records=[],extracted_json_sha256_before_comparison=sha(self.root/'extracted_financial.json'),page_text_sha256='a')
        self.save('extraction_audit.json',audit)
        self.save('inventory.json',[dict(key='2025',file='synthetic.pdf',sha256='a'*64)])
        return audit

    def test_pdf_wrong_snapshot_rejected(self):
        audit=self.pdf();audit['source_run']=str(self.root/'other');self.save('extraction_audit.json',audit)
        with self.assertRaisesRegex(ValueError,'snapshot_mismatch'):pdf_section(self.root,self.root,{})

    def test_pdf_changed_rows_rejected(self):
        self.pdf();self.save('extracted_financial.json',[{'value':'123'}])
        with self.assertRaisesRegex(ValueError,'hash_mismatch'):pdf_section(self.root,self.root,{})

    def test_pdf_changed_comparison_rejected(self):
        self.pdf()
        with patch('tracelab.display_modules.extract_pdf',return_value=([],{'page_text_sha256':'a'})),patch('tracelab.display_modules.compare',return_value=[{'status':'mismatch'}]),self.assertRaisesRegex(ValueError,'comparison_mismatch'):
            pdf_section(self.root,self.root,{})
