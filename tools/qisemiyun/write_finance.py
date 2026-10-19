"""Portable, Excel-readable CSV fallback for receipt/payment API records."""
import csv
import hashlib
import json
from pathlib import Path
from client import ROOT

def cell(value):
    if value is None:return ''
    if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
    if isinstance(value,str) and value.startswith(('=','+','-','@')):return "'"+value
    return str(value)

def main():
    reports=[]
    for module,identity in [('receipts','ReceiveId'),('payments','PaymentId')]:
        with (ROOT/'data'/(module+'.jsonl')).open(encoding='utf-8') as source:rows=[json.loads(line) for line in source if line.strip()]
        keys=list(dict.fromkeys(k for row in rows for k in row)) or [identity,'BusiDate','WriteBack']
        target=ROOT/'data/native'/(module+'.csv');target.parent.mkdir(parents=True,exist_ok=True)
        expected=[{k:cell(row.get(k)) for k in keys} for row in rows]
        with target.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(expected)
        with target.open(encoding='utf-8-sig',newline='') as stream:actual=list(csv.DictReader(stream))
        if actual!=expected:raise RuntimeError(module+' CSV 校验失败')
        status={'name':module,'state':'complete','method':'source_api_to_csv','count':len(rows),'columns':len(keys),
                'file':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        folder=ROOT/'data/native_status';folder.mkdir(parents=True,exist_ok=True)
        (folder/(module+'.json')).write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
        reports.append({'module':module,'rows':len(rows),'columns':len(keys),'mismatches':0,'format':'CSV (UTF-8 BOM)'})
    folder=ROOT/'qa';folder.mkdir(parents=True,exist_ok=True)
    (folder/'saved-finance-validation.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'finance_validation':'passed','tables':reports},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
