"""Recover sale document details referenced by historical item rows."""
import concurrent.futures
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from client import Client,ROOT,redact

DATA=ROOT/'data'
def read_rows(name):return [json.loads(l) for l in (DATA/(name+'.jsonl')).open(encoding='utf-8')]
def main():
    current={str(r['SaleId']).lower() for r in read_rows('sales')}
    missing={}
    for row in read_rows('sales_line_items'):
        if int(row['BusiType'])==3 and str(row['SaleId']).lower() not in current:missing.setdefault(str(row['SaleId']),row)
    folder=DATA/'pages/sales_history_details';folder.mkdir(parents=True,exist_ok=True)
    def fetch(key):
        p=folder/(key+'.json');result=None
        for attempt in range(3):
            try:
                result=json.loads(p.read_text(encoding='utf-8')) if p.exists() else Client.load().post('/V1/User/Sale/QuerySaleById',{'SaleId':key})
                if result.get('IsSuccess'):
                    result=redact(result);p.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                    break
            except Exception as e:result={'Message':str(e)}
            time.sleep(.7)
        time.sleep(.25)
        return key,result
    values=[];errors=[];db=sqlite3.connect(DATA/'qisemiyun.sqlite3',timeout=30);db.execute('PRAGMA busy_timeout=30000')
    status_path=DATA/'status/sales_history_details.json'
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for index,(key,result) in enumerate(pool.map(fetch,missing),1):
            if not result.get('IsSuccess'):errors.append({'id':key,'message':result.get('Message')})
            else:
                record={'RequestedSaleId':key,'SourceReference':'sales_line_items','InCurrentSalesList':False,**result['Data']}
                values.append(record);db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',('sales_history_details',key,json.dumps(record,ensure_ascii=False)));db.commit()
            if index%100==0:
                status={'module':'sales_history_details','label':'明细中关联的历史销售单版本','state':'running','processed':index,'expected':len(missing),'count':len(values)}
                status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(status,ensure_ascii=False),flush=True)
    output=DATA/'sales_history_details.jsonl';output.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in values),encoding='utf-8')
    status={'module':'sales_history_details','label':'明细中关联的历史销售单版本','state':'complete' if len(values)==len(missing) and not errors else 'incomplete',
            'expected':len(missing),'count':len(values),'errors':errors,'file':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'scope':'Additional sale IDs referenced by the sale detail report but absent from the current full sale list; retained separately, not added to current business totals.'}
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(status,ensure_ascii=False),flush=True);db.close()

if __name__=='__main__':main()
