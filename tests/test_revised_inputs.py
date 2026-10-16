import tempfile
import unittest
from pathlib import Path

from tracelab.stage2 import FILES, REVISED_FILES, select_files, prepare_evidence


class RevisedInputTests(unittest.TestCase):
    def test_revision_pair_and_original_override(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(select_files(folder), (FILES, 'original'))
            (Path(folder)/REVISED_FILES['xlsx']).touch()
            with self.assertRaises(ValueError):
                select_files(folder)
            self.assertEqual(select_files(folder,'original'), (FILES,'original'))
            (Path(folder)/REVISED_FILES['latest']).touch()
            self.assertEqual(select_files(folder), (REVISED_FILES,'revised'))
            self.assertEqual(FILES['latest'], '格力电器金融组核验整理材料及部分归因分析(1).docx')

    def test_evidence_rows_are_not_limited_to_six(self):
        rows = {1:{}, 12:{'A12':{'value':'E07'}}}
        pages = [dict(printed_page=p, pdf_page=int(p)+1,
                      text='票 据 保 证 金 等 净 减 少 额\n15,667,164,024.70 元' if p=='179' else '原文')
                 for p in ('28','29','178','179')]
        records=prepare_evidence({'证据台账':rows},pages,{'printed_page':'87'},lambda *a:None)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['disclosed_amount']['value_yuan'],'15667164024.70')
        self.assertEqual(records[0]['printed_page'],['28','29','178','179'])

    def test_unknown_or_duplicate_evidence_is_reported(self):
        rows={2:{'A2':{'value':'E08'}},3:{'A3':{'value':'E07'}},4:{'A4':{'value':'E07'}}}
        problems=[]
        result=prepare_evidence({'证据台账':rows},[],{'printed_page':'87'},lambda *a:problems.append(a))
        self.assertEqual(len(result),1)
        self.assertEqual(sum(p[0]=='EVIDENCE_ID' for p in problems),2)
        self.assertEqual(result[0]['disclosed_amount']['status'],'pending')
