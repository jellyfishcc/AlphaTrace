"""Read OOXML without converting stored decimal numbers to binary floats."""
import posixpath
import zipfile
import xml.etree.ElementTree as ET

S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def read_xlsx(path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f'损坏的 ZIP 成员：{bad}')
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(x.itertext()) for x in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        relations = {r.attrib['Id']: r.attrib['Target'] for r in
                      ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(archive.read('xl/workbook.xml')).find(S+'sheets'):
            target = relations[sheet.attrib[R+'id']]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows = {}
            for row in ET.fromstring(archive.read(target)).iter(S+'row'):
                cells = {}
                for c in row.findall(S+'c'):
                    v = c.find(S+'v')
                    raw = v.text if v is not None else None
                    kind = c.get('t', 'n')
                    if kind == 's':
                        raw = shared[int(raw)]
                    elif kind == 'inlineStr':
                        raw = ''.join(t.text or '' for t in c.iter(S+'t'))
                    formula = c.find(S+'f')
                    cells[c.attrib['r']] = dict(value=raw, kind=kind,
                                               formula=formula.text if formula is not None else None)
                rows[int(row.attrib['r'])] = cells
            result[sheet.attrib['name']] = rows
        return result


def read_docx(path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f'损坏的 ZIP 成员：{bad}')
        body = ET.fromstring(archive.read('word/document.xml')).find(W+'body')
        text = lambda node: ''.join(t.text or '' for t in node.iter(W+'t'))
        return dict(paragraphs=[text(p) for p in body.findall(W+'p')],
                    tables=[[[text(c) for c in row.findall(W+'tc')] for row in t.findall(W+'tr')]
                            for t in body.findall(W+'tbl')])
