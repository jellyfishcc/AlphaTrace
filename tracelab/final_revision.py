"""Incremental acceptance for the supplied revision; reuse verified calculations."""
import argparse
import copy
import difflib
import json
import re
import shutil
import uuid
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from .source_io import read_xlsx,read_docx
from .stage3_input import read,sha
from .stage1 import write_json
from .final_release import CORE,pair,WORD,EXCEL,load_agent_payload
from .stage2 import cell,num
from .accounting import bridge

NEW_WORD=WORD.replace('.docx','(1).docx')
NEW_EXCEL=EXCEL.replace('.xlsx','(1).xlsx')


def changes(old,new):
    result=[]
    for sheet in sorted(set(old)|set(new)):
        for row in sorted(set(old.get(sheet,{}))|set(new.get(sheet,{}))):
            a=old.get(sheet,{}).get(row,{});b=new.get(sheet,{}).get(row,{})
            for address in sorted(set(a)|set(b)):
                if a.get(address)!=b.get(address):result.append(dict(sheet=sheet,cell=address,old=a.get(address),new=b.get(address)))
    return result


def run(source,previous,output):
    from pypdf import PdfReader
    source,previous,output=map(Path,(source,previous,output))
    for name in (NEW_WORD,NEW_EXCEL):
        if not (source/name).is_file():raise FileNotFoundError(source/name)
    for name,h in read(previous/'release_hashes.json').items():
        if sha(previous/name)!=h:raise ValueError('parent_snapshot_changed')
    old=read_xlsx(previous/'inputs'/EXCEL);new=read_xlsx(source/NEW_EXCEL)
    doc=read_docx(source/NEW_WORD);old_doc=read_docx(previous/'inputs'/WORD)
    delta=changes(old,new)
    metrics=read(previous/'metrics.json');by_id={m['item_id']:m for m in metrics}
    for key,(sheet,row) in CORE.items():
        if pair(new,sheet,row)!=tuple(num(by_id[key][k]) for k in ('base_amount','current_amount')):
            raise ValueError('unexpected_core_change:'+key)
    for row in range(2,17):
        if pair(new,'经营现金流',row)!=pair(old,'经营现金流',row):raise ValueError('unexpected_direct_cash_change')
    allowed={('经营现金流',c) for c in ('B26','C26','B27','C27')}
    for d in delta:
        if (d['sheet'],d['cell']) in allowed:continue
        for v in (d['old'],d['new']):
            if v and (v.get('formula') or v.get('kind')=='n'):
                raise ValueError('unexpected_numeric_or_formula_change')
    inventory=read(previous/'inventory.json');name=next(i['file'] for i in inventory if i['key']=='2025')
    pdf=PdfReader(previous/'inputs'/name);cache={}
    def page(p):
        if p not in cache:
            t=pdf.pages[p].extract_text() or ''
            if str(p) not in [l.strip() for l in t.splitlines()[:6]]:raise ValueError('page_identity_changed')
            cache[p]=t
        return cache[p]
    layout=pdf.pages[176].extract_text(extraction_mode='layout')
    paid=layout[layout.index('支付的其他'):]
    header=next(l for l in paid.splitlines() if '本期发生额' in l and '上期发生额' in l)
    midpoint=(header.index('本期发生额')+header.index('上期发生额'))/2
    source_records=[];resolutions=[]
    plain=json.dumps(doc,ensure_ascii=False)
    for c in read(previous/'conflicts.json'):
        r=copy.deepcopy(c);ok=False;basis=[]
        if c['kind']=='period_conflict':
            row=int(re.search(r'B(\d+)',c['location']).group(1));amount=c['observed'][0]
            formatted=f'{Decimal(amount):,.2f}'
            line=next(l for l in paid.splitlines() if formatted in l)
            ok=pair(new,'经营现金流',row)==(Decimal(amount),None) and line.index(formatted)>midpoint
            basis=[dict(source_file=name,printed_page='176',pdf_page=177,text=line,period='2024',current=None)]
        elif c['kind']=='word_display_conflict':
            values=next(row for table in doc['tables'] for row in table if len(row)>2 and row[0]=='公允价值变动收益' and re.fullmatch(r'-?\d+\.\d+',row[1]))
            col=1 if 'col2' in c['location'] else 2
            metric=by_id['fair_value_income'];field='base_yi' if col==1 else 'current_yi'
            ok=num(values[col])==num(metric[field])
            raw=[metric['base_amount'],metric['current_amount']]
            ok=ok and all(f'{Decimal(v):,.2f}' in page(174) for v in raw)
            basis=[dict(source_file=name,printed_page='174',pdf_page=175,raw_yuan=raw,display=values[col])]
        elif c['kind']=='source_locator':
            topic=c['location']
            rules={
                '所得税费用明细':('所得税',2,'F','176',176,'当期所得税费用'),
                '其他经营收付款明细':('经营现金流',18,'F','176',176,'收到的其他与经营活动有关的现金'),
                '票据保证金间接法说明':('经营现金流',29,'F','179',179,'15,667,164,024.70'),
                '应收账款附注编号':('证据追踪',12,'D','五、4',130,'4、 应收账款'),
                '存货附注编号':('收益及减值',7,'F','五、10',137,'10、 存货')}
            sheet,row,col,token,p,anchor=rules[topic]
            raw=cell(new,sheet,row,col)
            # Match amount despite PDF's character spacing in the indirect-method note.
            source_ok=anchor.replace(' ','') in page(p).replace(' ','')
            ok=token in raw and source_ok
            if topic=='应收账款附注编号':ok=ok and '130—132' in raw and '五、4' in plain
            if topic=='存货附注编号':ok=ok and '五、10' in plain
            if topic=='其他经营收付款明细':ok=ok and '176' in cell(new,'经营现金流',23,'F')
            word_tokens={'所得税费用明细':'附注五、69，印刷页176','其他经营收付款明细':'支付明细见附注五、70（1），印刷页176',
                '票据保证金间接法说明':'附注五、71，页179','应收账款附注编号':'附注五、4，印刷页130—132','存货附注编号':'存货附注五、10，印刷页138'}
            ok=ok and word_tokens[topic] in plain.replace(' ','')
            basis=[dict(source_file=name,printed_page=str(p),pdf_page=p+1,anchor=anchor,revised_locator=raw)]
        r.update(status='resolved' if ok else 'unresolved',verification=basis)
        resolutions.append(r);source_records.extend(basis)
    # Reuse original bridge engine and compare to saved outputs, without new formulas.
    detail_checks=[]
    cash={m['item_id']:m for m in read(previous/'cash_metrics.json')}
    for rows,target in [(range(19,23),'cash_6'),(range(24,29),'cash_14')]:
        for col,field in [('B','base_amount'),('C','current_amount')]:
            items=[(r,num(cell(new,'经营现金流',r,col))) for r in rows]
            total=sum((v for _,v in items if v is not None),Decimal(0))
            expected=num(cash[target][field])
            if total!=expected:raise ValueError('other_cash_detail_mismatch')
            detail_checks.append(dict(target=target,period='2024' if col=='B' else '2025',listed_sum=str(total),
                reported_total=str(expected),blank_rows=[r for r,v in items if v is None],status='exact',
                boundary='仅已列示金额求和核对；空白仍为空白，不推断其为零或计算该行同比'))
    recomputed=[]
    for filename,rows in [('bridges.json',metrics),('cash_bridges.json',read(previous/'cash_metrics.json'))]:
        values={m['item_id']:(num(m['base_amount']),num(m['current_amount'])) for m in rows}
        for b in read(previous/filename):
            actual=bridge(values,b['target'],b['terms'],b['relation_status'])
            if any(actual[k]!=b[k] for k in ('base','current','change_residual','math_status')):raise ValueError('bridge_regression')
            recomputed.append(dict(file=filename,target=b['target'],math_status=actual['math_status']))
    out=output/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10])
    shutil.copytree(previous,out,ignore=shutil.ignore_patterns('release_hashes.json'))
    shutil.copy2(previous/'release_hashes.json',out/'parent_release_hashes.json')
    for key,filename in [('revision_word',NEW_WORD),('revision_excel',NEW_EXCEL)]:
        shutil.copy2(source/filename,out/'inputs'/filename)
        inventory.append(dict(key=key,file=filename,sha256=sha(source/filename),path=str((source/filename).resolve())))
    write_json(out/'inventory.json',inventory)
    write_json(out/'conflicts.json',resolutions)
    word_checks=read(previous/'word_checks.json');write_json(out/'parent_word_checks.json',word_checks)
    for check in word_checks:
        if check['item']=='公允价值变动收益' and check['status']=='conflict':
            r=next(r for r in resolutions if r['location']==check['location'])
            if r['status']=='resolved':check.update(reported=r['verification'][0]['display'],status='exact_display')
    write_json(out/'word_checks.json',word_checks)
    write_json(out/'revision_cells.json',delta)
    write_json(out/'source_text/revision_workbook.json',new);write_json(out/'source_text/revision_word.json',doc)
    (out/'revision_word.diff').write_text('\n'.join(difflib.unified_diff(json.dumps(old_doc,ensure_ascii=False,indent=1).splitlines(),json.dumps(doc,ensure_ascii=False,indent=1).splitlines())),encoding='utf8')
    write_json(out/'revision_checks.json',dict(core_count=31,core_unchanged=True,cash_unchanged=True,bridges=recomputed,
        resolved=sum(r['status']=='resolved' for r in resolutions),unresolved=sum(r['status']!='resolved' for r in resolutions),
        sources=source_records,other_cash_details=detail_checks,
        blank_details=[dict(item_id=f'cash_{r}',base=str(pair(new,'经营现金流',r)[0]),current=None,change=None,status='unavailable_not_zero') for r in (26,27)],
        file_versions=[dict(old_file=a,old_sha256=sha(previous/'inputs'/a),new_file=b,new_sha256=sha(source/b)) for a,b in [(WORD,NEW_WORD),(EXCEL,NEW_EXCEL)]]))
    old_manifest=read(previous/'manifest.json')
    write_json(out/'parent_manifest.json',old_manifest)
    write_json(out/'manifest.json',dict(run_id=out.name,source_revision='final_revision_1',previous_run=str(previous.resolve()),
        original_stage2_run=old_manifest['previous_run'],llm_called=False,core_count=31,conflict_count=sum(r['status']!='resolved' for r in resolutions)))
    (out/'pending_questions.md').write_text('# 当前待处理\n\n'+('\n'.join(r['location'] for r in resolutions if r['status']!='resolved') or '原9条附件冲突均已核验解决。')+'\n经营因果仍需人工复核；两项付款本期空白，不计算变化，不开放为同比事实。\n',encoding='utf8')
    write_json(out/'release_hashes.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
    payload,_=load_agent_payload(out) # rebuild source trust from this version, never inherit receipts
    return out,len(payload['facts'])


def main():
    p=argparse.ArgumentParser(description='修订版增量核验，不调用模型')
    p.add_argument('--source',type=Path,required=True);p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('outputs/final_revision'))
    a=p.parse_args();out,count=run(a.source,a.previous,a.output);print(json.dumps({'output':str(out.resolve()),'facts':count},ensure_ascii=False))

if __name__=='__main__':main()
