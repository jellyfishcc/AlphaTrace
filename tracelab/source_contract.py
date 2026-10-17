"""Local provenance boundary. Models may read this contract, never create it.

Digests detect changes after loading; they are not signatures or online report
authentication. Rebuild from trusted local snapshots, never from model output.
"""
import hashlib
import json
from pathlib import Path
from decimal import Decimal


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def bind_sources(payload, folder):
    from .stage3_input import read, sha
    from pypdf import PdfReader
    folder=Path(folder)
    reports={}
    for row in read(folder/'inventory.json'):
        if row['key'] not in ('2024','2025'): continue
        name=row['file']
        if Path(name).name!=name: raise ValueError('invalid_report_path')
        path=folder/'inputs'/name
        if sha(path)!=row['sha256']: raise ValueError('report_hash_mismatch')
        reports[name]=(PdfReader(path),row['sha256'])
    records={}
    for e in payload['evidence']:
        if e['evidence_id'] in records: raise ValueError('duplicate_evidence_id')
        if e.get('source_type')!='公开年报披露' or e.get('source_file') not in reports:
            raise ValueError('unverified_report_source')
        reader,file_hash=reports[e['source_file']]
        page=e.get('pdf_page')
        if type(page)!=int or not 1<=page<=len(reader.pages): raise ValueError('invalid_report_page')
        text=reader.pages[page-1].extract_text() or ''
        if not e.get('text') or e['text'] not in text: raise ValueError('unverified_excerpt')
        if str(e['printed_page']) not in [line.strip() for line in text.splitlines()[:6]]:
            raise ValueError('unverified_printed_page')
        basis=e.get('comparison_basis')
        if basis not in ('yoy','current_period','both_periods'): raise ValueError('unverified_comparison_basis')
        records[e['evidence_id']]={'source_kind':'annual_report','file_sha256':file_hash,
            'evidence_sha256':digest(e),'allowed_bases':(['yoy','current_period'] if basis=='both_periods' else [basis])}
    payload['source_contract']={'version':'v1','source_run':folder.name,'evidence':records,'facts':{}}
    by_id={e['evidence_id']:e for e in payload['evidence']}
    for f in payload['facts']:
        if f['fact_id'] in payload['source_contract']['facts']: raise ValueError('duplicate_fact_id')
        if not f.get('evidence_ids') or any(eid not in records for eid in f['evidence_ids']):
            raise ValueError('fact_source_missing')
        if any(f['fact_id'] not in by_id[eid]['related_facts'] for eid in f['evidence_ids']):
            raise ValueError('fact_source_identity_mismatch')
        for field,units in f['amounts'].items():
            if field not in ('base','current','change') or not units: raise ValueError('invalid_fact_field')
            if any(not Decimal(v).is_finite() for v in units.values()): raise ValueError('invalid_fact_amount')
        # This binds already checked amounts. Never adds or calculates missing fields.
        payload['source_contract']['facts'][f['fact_id']]=digest(f)
    return payload


def verified_evidence(e, payload):
    r=payload.get('source_contract',{}).get('evidence',{}).get(e['evidence_id'],{})
    return (r.get('source_kind')=='annual_report' and len(r.get('file_sha256',''))==64
            and r.get('evidence_sha256')==digest(e) and e.get('source_type')=='公开年报披露')


def disclosure_errors(claim, cited, payload):
    errors=[]
    if not cited or any(not verified_evidence(e,payload) for e in cited):
        errors.append('披露解释缺少经本地来源核验的原始年报证据')
    basis=claim.get('comparison_basis')
    for e in cited:
        allowed=payload.get('source_contract',{}).get('evidence',{}).get(e['evidence_id'],{}).get('allowed_bases',[])
        if basis not in allowed: errors.append('披露比较口径与引文不一致；请分开本期差异与同比解释')
        if not set(claim['metric_ids']) & set(e['related_facts']): errors.append('引文未关联本条财务项目')
    return errors
