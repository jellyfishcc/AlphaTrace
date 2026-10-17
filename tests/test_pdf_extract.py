"""All fixtures are explicitly synthetic except the optional local PDF test."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tracelab.pdf_extract import COMPANY, amount, compare, extract_pdf, parse_page, run
from tracelab.source_contract import digest

FIXTURE = Path(__file__).parent/'fixtures/pdf_income_synthetic.txt'
SNAPSHOT = Path(__file__).resolve().parents[1]/'outputs/final_revision/20261017T093152-d80de1cefa'


def parse(text=None):
    return parse_page(FIXTURE.read_text(encoding='utf-8') if text is None else text, 'synthetic.pdf', 'a'*64)


def synthetic_contract(rows):
    """Test-only registered fixture; never used by CLI or represented as real."""
    facts, evidence, registry = [], [], {}
    for r in rows[::2]:
        other = next(x for x in rows if x['metric_id']==r['metric_id'] and x['fiscal_year']==2025)
        eid = 'synthetic_' + r['metric_id']
        f = dict(fact_id=r['metric_id'], name=r['metric_name'], evidence_ids=[eid],
                 amounts={'base':{'元':r['value']},'current':{'元':other['value']}})
        e = dict(evidence_id=eid,source_type='公开年报披露',source_file='synthetic.pdf',
                 pdf_page=88,printed_page='87',text=r['raw_row_text'],related_facts=[r['metric_id']])
        facts.append(f); evidence.append(e)
        registry[eid] = dict(source_kind='annual_report',file_sha256='a'*64,evidence_sha256=digest(e))
    return dict(company=COMPANY, periods=['2024','2025'],currency='CNY',
        scope='披露口径的合并报表；合并范围变动，非恒定主体比较', facts=facts,evidence=evidence,
        source_contract={'facts':{f['fact_id']:digest(f) for f in facts},'evidence':registry})


class PdfExtractTests(unittest.TestCase):
    def test_normal_two_years(self):
        rows,audit=parse()
        self.assertEqual(len(rows),10)
        self.assertTrue(all(r['extraction_status']=='extracted' for r in rows))
        self.assertEqual([r['value'] for r in rows[:2]],['2345.67','1234.56'])
        self.assertEqual(audit['year_columns'],[2025,2024])

    def test_reversed_header_maps_cells(self):
        text=FIXTURE.read_text(encoding='utf-8').replace('2025 年度 2024 年度','2024 年度 2025 年度')
        rows,_=parse(text)
        self.assertEqual([r['value'] for r in rows[:2]],['1234.56','2345.67'])

    def test_decimal_negative_and_grouping(self):
        self.assertEqual(amount('-1,234.50','元'),'-1234.50')
        self.assertEqual(amount('(1,234.50)','元'),'-1234.50')
        self.assertEqual(amount('−0.01','元'),'-0.01')
        self.assertEqual(parse()[0][3]['value'],'-100.01')
        with self.assertRaises(ValueError): amount('1,23.00','元')

    def test_unit_conversion(self):
        for unit,expected in [('万元','12345600.00'),('亿元','123456000000.00')]:
            rows,_=parse(FIXTURE.read_text(encoding='utf-8').replace('人民币元','人民币'+unit))
            self.assertEqual(rows[1]['value'],expected)
            self.assertEqual(rows[1]['unit'],'元')
            self.assertEqual(rows[1]['source_unit'],unit)

    def test_explicit_blank_not_zero(self):
        rows,_=parse(FIXTURE.read_text(encoding='utf-8').replace('1,234.56','—'))
        self.assertIsNone(rows[1]['value'])
        self.assertEqual(rows[1]['reason'],'blank_cell')
        self.assertEqual(rows[0]['value'],'2345.67')

    def test_absent_column_blocks_both_years(self):
        rows,_=parse(FIXTURE.read_text(encoding='utf-8').replace('1,234.56 ',''))
        self.assertTrue(all(r['value'] is None for r in rows[:2]))
        self.assertEqual(rows[0]['reason'],'ambiguous_or_missing_cells')

    def test_duplicate_subject_blocked(self):
        for duplicate in ('三、营业利润 1.00 2.00', '三、营业利润'):
            text=FIXTURE.read_text(encoding='utf-8')
            text=text.replace('法定代表人：',duplicate+'\n法定代表人：')
            rows,_=parse(text)
            self.assertEqual(rows[0]['reason'],'duplicate_subject')
            self.assertIsNone(rows[1]['value'])

    def test_ambiguous_columns_blocked(self):
        rows,audit=parse(FIXTURE.read_text(encoding='utf-8').replace('2024 年度','2025 年度'))
        self.assertIn('ambiguous_year_columns',audit['errors'])
        self.assertTrue(all(r['value'] is None for r in rows))

    def test_provenance(self):
        rows,_=parse()
        r=rows[0]
        self.assertEqual((r['pdf_page'],r['printed_page'],r['source_file']),(88,87,'synthetic.pdf'))
        self.assertEqual(r['source_hash'],'a'*64)
        self.assertEqual(r['raw_row_sha256'],hashlib.sha256(r['raw_row_text'].encode()).hexdigest())
        self.assertEqual(r['source_line'],7)

    def test_wrong_page_and_scope_blocked(self):
        text=FIXTURE.read_text(encoding='utf-8')
        for changed in (text.replace('\n87\n','\n88\n'),text.replace('合并利润表','母公司利润表'),text.replace('人民币元','美元')):
            self.assertTrue(all(r['value'] is None for r in parse(changed)[0]))
        self.assertTrue(parse_page(text,'synthetic.pdf','a'*64,89)[1]['errors'])

    def test_unsupported_layout_not_success(self):
        for text in ('', '扫描件无文字层', FIXTURE.read_text(encoding='utf-8').replace('法定代表人：','签名：')):
            rows,audit=parse(text)
            self.assertTrue(audit['errors'])
            self.assertTrue(all(r['extraction_status']=='missing' for r in rows))

    def test_matches_registered_facts(self):
        rows,_=parse()
        results=compare(rows,synthetic_contract(rows))
        self.assertEqual([c['status'] for c in results],['matched']*10)

    def test_mismatch_keeps_both_values(self):
        rows,_=parse(); payload=synthetic_contract(rows)
        rows[0]['value']='9.99'
        result=compare(rows,payload)[0]
        self.assertEqual(result['status'],'mismatch')
        self.assertEqual((result['extracted_value'],result['trusted_value']),('9.99','2345.67'))
        self.assertEqual(rows[0]['value'],'9.99')

    def test_missing_and_unverified_source(self):
        rows,_=parse(); payload=synthetic_contract(rows)
        rows[0].update(extraction_status='missing',value=None,reason='blank_cell')
        rows[1]['source_hash']='b'*64
        result=compare(rows,payload)
        self.assertEqual([c['status'] for c in result[:2]],['missing','unverifiable'])

    def test_scope_company_and_year_mismatch(self):
        rows,_=parse()
        for field,value in [('company','其他公司'),('scope','母公司'),('currency','USD')]:
            payload=synthetic_contract(rows); payload[field]=value
            self.assertTrue(all(c['status']=='mismatch' for c in compare(rows,payload)))
        payload=synthetic_contract(rows); payload['periods']=['2025','2024']
        self.assertTrue(all(c['status']=='unverifiable' for c in compare(rows,payload)))

    def test_changed_fact_fails_existing_registry(self):
        rows,_=parse(); payload=synthetic_contract(rows)
        payload['facts'][0]['amounts']['base']['元']='9.99'
        self.assertEqual(compare(rows,payload)[0]['status'],'unverifiable')

    def test_generated_native_text_pdf(self):
        # Public synthetic PDF, created with existing pypdf (no private data).
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, ArrayObject, TextStringObject, NumberObject
        writer=PdfWriter()
        for _ in range(88): writer.add_blank_page(width=600,height=800)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),
            NameObject('/Subtype'):NameObject('/Type0'),NameObject('/BaseFont'):NameObject('/STSong-Light'),
            NameObject('/Encoding'):NameObject('/UniGB-UCS2-H')})
        font[NameObject('/DescendantFonts')]=ArrayObject([DictionaryObject({
            NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/CIDFontType0'),
            NameObject('/BaseFont'):NameObject('/STSong-Light'),
            NameObject('/CIDSystemInfo'):DictionaryObject({NameObject('/Registry'):TextStringObject('Adobe'),
                NameObject('/Ordering'):TextStringObject('GB1'),NameObject('/Supplement'):NumberObject(4)})})])
        page=writer.pages[-1]
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        commands=['BT /F1 10 Tf 12 TL 20 780 Td']
        for line in FIXTURE.read_text(encoding='utf-8').splitlines():
            commands.append('<'+line.encode('utf-16-be').hex()+'> Tj T*')
        commands.append('ET')
        stream=DecodedStreamObject(); stream.set_data('\n'.join(commands).encode('ascii'))
        page[NameObject('/Contents')]=stream
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.pdf'; writer.write(path)
            rows,audit=extract_pdf(path)
            self.assertEqual(audit['errors'],[])
            self.assertEqual(rows[1]['value'],'1234.56')
            self.assertEqual(rows[0]['source_hash'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_parent_profit_not_net_profit(self):
        rows,_=parse(); keyed={(r['metric_id'],r['fiscal_year']):r['value'] for r in rows}
        self.assertEqual(keyed['net_profit',2025],'90.01')
        self.assertEqual(keyed['parent_profit',2025],'80.01')

    def test_extraction_persisted_before_fact_loading(self):
        rows,audit=parse()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); (folder/'inventory.json').write_text(json.dumps([dict(key='2025',file='synthetic.pdf',sha256='a'*64)]))
            def load(_):
                files=list((folder/'out').glob('*/extracted_financial.json'))
                self.assertEqual(len(files),1)
                self.assertEqual(json.loads(files[0].read_text(encoding='utf-8')),rows)
                return synthetic_contract(rows),{}
            with patch('tracelab.pdf_extract.extract_pdf',return_value=(rows,audit)),patch('tracelab.final_release.load_agent_payload',side_effect=load):
                out,code=run(folder,folder/'out')
            self.assertEqual(code,0)
            self.assertEqual(len(list(out.iterdir())),5)

    def test_pdf_hash_rejected_before_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.pdf'; path.write_bytes(b'not a PDF')
            with self.assertRaisesRegex(ValueError,'hash mismatch'): extract_pdf(path,'a'*64)

    @unittest.skipUnless((SNAPSHOT/'inventory.json').exists(),'private local snapshot absent')
    def test_real_local_pdf_and_independent_source_contract(self):
        from tracelab.final_release import load_agent_payload
        inventory=json.loads((SNAPSHOT/'inventory.json').read_text(encoding='utf-8'))
        source=next(i for i in inventory if i['key']=='2025')
        rows,audit=extract_pdf(SNAPSHOT/'inputs'/source['file'],source['sha256'])
        self.assertEqual(audit['errors'],[])
        payload,_=load_agent_payload(SNAPSHOT)
        self.assertEqual([c['status'] for c in compare(rows,payload)],['matched']*10)


if __name__=='__main__': unittest.main()
