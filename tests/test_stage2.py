import tempfile
import unittest
import zipfile
from decimal import Decimal as D
from pathlib import Path

from tracelab.accounting import bridge, display_yi, growth
from tracelab.source_io import read_xlsx
from tracelab.stage2 import extract_pair, adjusted_pair, segment_lines


class Stage2Tests(unittest.TestCase):
    def test_growth_boundaries(self):
        self.assertEqual(growth(D('100'),D('90')), (D('-.1'),'ordinary_yoy'))
        self.assertEqual(growth(D('100'),D('0')), (D('-1'),'ordinary_yoy'))
        for base,current,reason in [('0','10','nonpositive_base'),('-10','-20','nonpositive_base'),
                                    ('-10','10','nonpositive_base'),('10','-1','sign_crossing')]:
            self.assertEqual(growth(D(base),D(current)), (None,reason))
        self.assertIsNone(growth(None,D('1'))[0])

    def test_units_rounding(self):
        self.assertEqual(display_yi(D('123456789.12')), '1.2346')
        self.assertEqual(display_yi(D('-123456789.12')), '-1.2346')
        self.assertEqual(display_yi(D('5000')), '0.0001')

    def test_bridge_sign_and_negative_minority(self):
        values={'net':(D('100'),D('90')),'minority':(D('5'),D('-3')),'parent':(D('95'),D('93'))}
        b=bridge(values,'parent',[('net',1),('minority',-1)],'confirmed')
        self.assertEqual(b['math_status'],'exact_zero_residual')
        self.assertEqual(D(b['change_residual']),0)
        self.assertEqual(b['business_status'],'待金融组确认')
        self.assertIsNone(b['tolerance'])

    def test_bridge_residual_not_silenced(self):
        values={'a':(D('10.00'),D('12.00')),'t':(D('10.01'),D('12.03'))}
        b=bridge(values,'t',[('a',1)],'confirmed')
        self.assertEqual(b['base']['residual'],'0.01')
        self.assertEqual(b['current']['residual'],'0.03')
        self.assertEqual(b['change_residual'],'0.02')
        self.assertEqual(b['math_status'],'nonzero_residual')

    def test_missing_never_zero_in_bridge(self):
        b=bridge({'a':(D('1'),None),'t':(D('1'),D('1'))},'t',[('a',1)],'confirmed')
        self.assertEqual(b['math_status'],'incomplete')
        self.assertEqual(b['change_residual'],'')
        self.assertIn('a',b['current']['missing'])

    def test_duplicate_bridge_rejected(self):
        with self.assertRaises(ValueError):
            bridge({},'t',[('a',1),('a',-1)],'confirmed')
        with self.assertRaises(ValueError):
            bridge({},'t',[('t',1)],'confirmed')

    def test_pdf_blank_fee_preserved(self):
        page={'text':'手续费及佣金收入 83.29\n二、营业总成本 100.00 120.00'}
        pair,text=extract_pair(page,'手续费及佣金收入',2025)
        self.assertEqual(pair,(D('83.29'),None))
        self.assertNotIn('100.00',text)

    def test_pdf_rows_not_confused(self):
        page={'text':'一、营业总收入 200.00 300.00\n其中：营业收入 五、54 190.00 280.00\n五、净利润（净亏损） 10.00 20.00\n1、归属于母公司股东的净利润（净亏损以“-”号填\n列）\n 9.00 18.00'}
        self.assertEqual(extract_pair(page,'营业收入',2025)[0],(D('280'),D('190')))
        self.assertEqual(extract_pair(page,'净利润',2025)[0],(D('20'),D('10')))
        self.assertEqual(extract_pair(page,'归属于母公司股东的净利润',2024)[0],(D('9'),None))

    def test_adjacent_main_indicator_numbers_keep_separators(self):
        page={'text':'归属于上市公司股东的扣除非\n经常性损益的净利润（元） 27,706,292,436.94 30,099,760,382.99 -7.95% 27,565,461,117.79'}
        self.assertEqual(adjusted_pair(page,2025)[0],(D('30099760382.99'),D('27706292436.94')))

    def test_segment_cost_table_not_revenue_history_table(self):
        page={'text':'产品 100.00 78.06% 120.00 78.54% -10.44%\n产品 100.00 60.00 40.00% -10.44% -10.94% 0.37'}
        matches=segment_lines([page],'产品')
        self.assertEqual(len(matches),1)
        self.assertIn('100.00 60.00',matches[0][1])

    def test_ooxml_raw_decimal_and_leading_zero_text(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'minimal.xlsx'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="test" r:id="rId1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><v>123456789012345.67</v></c><c r="B1" t="inlineStr"><is><t>000651</t></is></c><c r="C1"><f>A1*2</f><v>2</v></c></row></sheetData></worksheet>')
            row=read_xlsx(path)['test'][1]
            self.assertEqual(row['A1']['value'],'123456789012345.67')
            self.assertEqual(row['B1']['value'],'000651')
            self.assertEqual(row['C1']['formula'],'A1*2')


if __name__=='__main__':
    unittest.main()
