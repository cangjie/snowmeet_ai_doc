"""Supplement observed, read-only document APIs; preserve every returned field."""
import json
import sqlite3
import time
from pathlib import Path
from client import Client, ROOT, redact

DATA = ROOT / 'data'

def rows(name):
    return [json.loads(line) for line in (DATA / (name + '.jsonl')).read_text(encoding='utf-8').splitlines() if line]

def main():
    client = Client.load()
    jobs = []
    for module, field, client_type in [('receipts','ReceiveId','1'),('payments','PaymentId','2')]:
        for row in rows(module):
            jobs.append((module+'_details', row[field], '/V1/User/ReceiveAndPay/ReceivePayDetail', {'ClientType':client_type,'Id':row[field]}))
    for row in rows('sales'):
        if row.get('IsMultiAccount'):
            jobs.append(('sales_multi_account_details',row['SaleId'],'/V1/User/Sale/QuerySaleById',{'SaleId':row['SaleId']}))
    for row in rows('sales_drafts'):
        jobs.append(('sales_draft_details',row['SaleId'],'/V1/User/BillDraft/QueryById',{'DraftId':row['SaleId']}))
    for row in rows('sales_orders'):
        jobs.append(('sales_order_details',row['SaleId'],'/V1/User/SaleOrder/QuerySaleOrderById',{'IsShowTurnWriteBack':1,'SaleId':row['SaleId']}))
    for row in rows('outbound'):
        jobs.append(('outbound_details',row['IOId'],'/V1/User/IO/QueryIOOUTDetail',{'IOState':'1','IOId':row['IOId']}))
    for source in ['loans_in','loans_out']:
        for row in rows(source):
            for linked in row.get('RelationLendReturnList') or []:
                jobs.append((source+'_return_details',linked['ReturnId'],'/V1/User/LendReturn/QueryDetailById',{'ReturnId':linked['ReturnId']}))
    movement_status = json.loads((DATA/'status/stock_movements.json').read_text(encoding='utf-8'))
    if movement_status.get('state') == 'complete':
        purchase_ids={str(row['BuyId']).lower() for row in rows('purchases')}
        for row in rows('stock_movements'):
            kind=int(row.get('BuinessType') or 0)
            if kind in [10,11] and row.get('BuinessId'):
                jobs.append(('loans_in_return_details' if kind==10 else 'loans_out_return_details',row['BuinessId'],
                             '/V1/User/LendReturn/QueryDetailById',{'ReturnId':row['BuinessId']}))
            if kind==1 and str(row.get('BuinessId')).lower() not in purchase_ids:
                jobs.append(('purchases_history_details',row['BuinessId'],'/V1/User/Buy/QueryBuyById',{'BuyId':row['BuinessId']}))
    jobs = list({(job[0],str(job[1])):job for job in jobs}.values())
    db = sqlite3.connect(DATA / 'qisemiyun.sqlite3', timeout=30)
    db.execute('PRAGMA busy_timeout=30000')
    modules = {name:[] for name in ['receipts_details','payments_details','sales_multi_account_details',
               'sales_draft_details','sales_order_details','outbound_details','loans_in_return_details',
               'loans_out_return_details','purchases_history_details']}
    for module, identity, endpoint, payload in jobs:
        cache = DATA / 'pages' / module / (str(identity)+'.json')
        cache.parent.mkdir(parents=True,exist_ok=True)
        result = json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else client.post(endpoint,payload)
        if not result.get('IsSuccess'): raise RuntimeError(module+': '+str(result.get('Message')))
        result = redact(result)
        cache.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        row = {'SourceId':identity,'Data':result.get('Data')}
        modules.setdefault(module,[]).append(row)
        db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',(module,str(identity),json.dumps(row,ensure_ascii=False)))
        db.commit()
        time.sleep(.2)
    for module, values in modules.items():
        (DATA / (module+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in values),encoding='utf-8')
        status = {'module':module,'state':'complete','count':len(values),'expected_count':len(values)}
        (DATA/'status'/(module+'.json')).write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(status,ensure_ascii=False),flush=True)
    db.close()
    configs = [dict(name='other_outbound',label='其他出库单',path='/V1/User/OtherWarehouseIO/QueryList',id_field='Id',payload={'StartBusiDate':'','EndBusiDate':'','IsShowWriteBack':'0','IOType':1,'BusiType':20,'SearchKey':''}),
               dict(name='other_inbound',label='其他入库单',path='/V1/User/OtherWarehouseIO/QueryList',id_field='Id',payload={'StartBusiDate':'','EndBusiDate':'','IsShowWriteBack':'0','IOType':0,'BusiType':21,'SearchKey':''})]
    (ROOT/'modules-augment.json').write_text(json.dumps(configs,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__ == '__main__': main()
