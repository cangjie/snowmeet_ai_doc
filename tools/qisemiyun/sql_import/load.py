"""Initial additive SQL import, atomic publication, verification, and safe replay."""
import gzip,hashlib,json,re,sqlite3,time
from pathlib import Path
from schema import TABLES,ddl
from staging import js,utcnow
from connection import connect_config,drain

ORDER=['source','import_batch','import_module','file','export_sheet','raw_record','branch','unit','category','warehouse','warehouse_position','product_sku','product_style','style_sku','sku_attribute','sku_unit','partner','account','employee','role','project','document','document_version','document_line','document_relation','settlement_line','writeoff_line','stock_total','stock_snapshot','stock_movement','sales_report_line','file_ref','retail_sku_map','retail_warehouse_map','retail_sale_link','data_issue','change_log']

def log(stage,**kw):print(js(dict(stage=stage,**kw)),flush=True)
def info(stage,k):return json.loads(stage.execute('SELECT value FROM info WHERE key=?',(k,)).fetchone()[0])

def check_schema(db):
    actual={r[0]:set() for r in db.execute("SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo') AND name LIKE 'qsm[_]%'")}
    if set(actual)!=set(TABLES):raise ValueError('Unexpected qsm table set; no data changed')
    for table in actual:
        actual[table]={r[0] for r in db.execute('SELECT name FROM sys.columns WHERE object_id=OBJECT_ID(?)','dbo.'+table)}
        if actual[table]!=set(TABLES[table]):raise ValueError('Schema drift: '+table)

def rows(stage,table):
    for (p,) in stage.execute('SELECT payload FROM staged WHERE table_name=? ORDER BY id',(table,)):yield json.loads(p)

def batches(values,max_rows=1000,max_chars=4_000_000):
    batch=[];size=0
    for r in values:
        n=len(js(r))
        if batch and (len(batch)>=max_rows or size+n>max_chars):yield batch;batch=[];size=0
        batch.append(r);size+=n
    if batch:yield batch

def wire(value):return gzip.compress(js(value).encode('utf-16-le'),compresslevel=3,mtime=0)

def insert_table(db,stage,table,asset_receipt=None,checkpoint=True):
    cols={k:v for k,v in TABLES[table].items() if k!='row_version' and not(table=='qsm_raw_record' and k=='payload_json')}
    col_names=','.join('['+k+']' for k in cols)
    declarations=[];selects=[]
    for k,v in cols.items():
        typ=v.split(' ',1)[0]
        if typ.startswith(('binary','varbinary')):
            declarations.append('['+k+'] varchar(max)');selects.append(f'CONVERT({typ},[{k}],2)')
        else:declarations.append('['+k+'] '+typ);selects.append('['+k+']')
    sql=f"DECLARE @j nvarchar(max)=CONVERT(nvarchar(max),DECOMPRESS(CONVERT(varbinary(max),?))); INSERT INTO [dbo].[{table}] ({col_names}) SELECT {','.join(selects)} FROM OPENJSON(@j) WITH ({','.join(declarations)});"
    expected=info(stage,'counts').get(table,0)
    prefix=db.execute('SELECT COUNT_BIG(*),MIN(id),MAX(id) FROM dbo.['+table+']').fetchone()
    loaded=int(prefix[0])
    if loaded>expected or (loaded and (prefix[1]!=1 or prefix[2]!=loaded)):raise RuntimeError('Unrecognized partial table: '+table)
    deferred=[]
    def records():
        for r in rows(stage,table):
            if 'parent_id' in r and r['parent_id'] is not None:deferred.append({'id':r['id'],'parent_id':r['parent_id']});r['parent_id']=None
            if table=='qsm_document':r['current_version_id']=None
            if table=='qsm_import_batch':
                r['state']='staging'
                verification=json.loads(r['verification_json']);verification['sql_migration_assets']=asset_receipt
                r['verification_json']=js(verification)
            if table=='qsm_file' and asset_receipt and asset_receipt.get('storage_provider')=='s3':
                r['storage_provider']='s3';r['object_key']=r['object_key'] if r['object_key'].startswith('private/qisemi/') else 'private/qisemi/'+r['object_key']
            if r['id']<=loaded:continue
            yield {k:r[k] for k in cols}
    count=loaded;progress=count//10000
    db.execute(f'SET IDENTITY_INSERT [dbo].[{table}] ON')
    try:
        for batch in batches(records()):
            drain(db.cursor().execute(sql,wire(batch)));count+=len(batch)
            if checkpoint:db.execute('CHECKPOINT')
            if count//10000>progress:log('insert_progress',table=table,rows=count);progress=count//10000
    finally:db.execute(f'SET IDENTITY_INSERT [dbo].[{table}] OFF')
    if deferred:
        sql=f'DECLARE @j nvarchar(max)=CONVERT(nvarchar(max),DECOMPRESS(CONVERT(varbinary(max),?))); UPDATE t SET parent_id=j.parent_id FROM [dbo].[{table}] t JOIN OPENJSON(@j) WITH(id bigint,parent_id bigint) j ON t.id=j.id WHERE t.source_id=1;'
        for batch in batches(deferred):
            drain(db.cursor().execute(sql,wire(batch)))
            if checkpoint:db.execute('CHECKPOINT')
    log('inserted',table=table,rows=count)

def verify(db,stage,published=True,asset_receipt=None):
    expected=info(stage,'counts');counts={}
    for table in TABLES:
        actual=int(db.execute('SELECT COUNT_BIG(*) FROM [dbo].['+table+']').fetchval());counts[table]=actual
        if actual!=expected.get(table,0):raise RuntimeError('Count mismatch '+table)
    bad=db.execute("SELECT COUNT_BIG(*) FROM dbo.qsm_raw_record WHERE payload_hash<>HASHBYTES('SHA2_256',CONVERT(varchar(max),payload_json COLLATE Latin1_General_100_BIN2_UTF8)) OR ISJSON(payload_json)<>1").fetchval()
    if bad:raise RuntimeError('Lossless raw JSON hash mismatch: '+str(bad))
    stock=db.execute("SELECT COUNT_BIG(*) FROM dbo.qsm_stock_total t LEFT JOIN (SELECT batch_id,sku_id,SUM(quantity_main) q FROM dbo.qsm_stock_snapshot WHERE valid=1 GROUP BY batch_id,sku_id) s ON s.batch_id=t.batch_id AND s.sku_id=t.sku_id WHERE ABS(t.quantity_main-COALESCE(s.q,0))>0.000001").fetchval()
    if stock:raise RuntimeError('Warehouse reconciliation differs')
    files={r[0]:(bytes(r[1]).hex(),int(r[2]),r[3],r[4]) for r in db.execute('SELECT id,content_sha256,byte_length,storage_provider,object_key FROM dbo.qsm_file')}
    for r in rows(stage,'qsm_file'):
        provider='s3' if asset_receipt and asset_receipt.get('storage_provider')=='s3' else r['storage_provider']
        object_key=r['object_key']
        if provider=='s3' and not object_key.startswith('private/qisemi/'):object_key='private/qisemi/'+object_key
        if files[r['id']]!=(r['content_sha256'],r['byte_length'],provider,object_key):raise RuntimeError('File metadata differs from verified asset plan')
    if db.execute("SELECT COUNT(*) FROM sys.foreign_keys WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE name LIKE 'qsm[_]%') AND (is_disabled=1 OR is_not_trusted=1)").fetchval():raise RuntimeError('Foreign keys not validated')
    if published:
        row=db.execute("SELECT s.current_full_batch_id,s.current_inventory_batch_id,b.state,b.verification_passed FROM dbo.qsm_source s JOIN dbo.qsm_import_batch b ON b.source_id=s.id AND b.id=s.current_full_batch_id WHERE s.valid=1").fetchone()
        if not row or tuple(row)!=(1,1,'published',True):raise RuntimeError('Published pointer mismatch')
    result={'database':db.execute('SELECT DB_NAME()').fetchval(),'tables':counts,'raw_payload_hash_mismatches':int(bad),'stock_reconciliation_differences':int(stock),'trusted_foreign_keys':True,'dataset_hash':info(stage,'source_fingerprint'),'published':published}
    log('verified',raw_records=counts['qsm_raw_record'],stock_skus=counts['qsm_stock_total'],warehouse_rows=counts['qsm_stock_snapshot'])
    return result

def apply(db,stage_path,apply_schema=False,asset_receipt=None):
    stage=stage_path if hasattr(stage_path,'execute') else sqlite3.connect(stage_path)
    ready=stage.execute("SELECT json_extract(payload,'$.state'),json_extract(payload,'$.verification_passed') FROM staged WHERE table_name='qsm_import_batch' AND id=1").fetchone()
    if not ready or tuple(ready)!=('validated',1):raise ValueError('A completed validated local stage is required')
    info(stage,'counts')
    if asset_receipt and (not asset_receipt.get('verified') or asset_receipt.get('dataset_hash')!=info(stage,'source_fingerprint') or asset_receipt.get('files')!=info(stage,'counts').get('qsm_file')):raise ValueError('Asset receipt does not match prepared snapshot')
    if apply_schema:drain(db.cursor().execute(ddl()))
    check_schema(db)
    db.execute('SET NOCOUNT ON; SET XACT_ABORT ON; SET LOCK_TIMEOUT 30000;')
    try:
        lock=db.execute("DECLARE @r int; EXEC @r=sys.sp_getapplock @Resource=N'qsm-initial-migration',@LockMode='Exclusive',@LockOwner='Session',@LockTimeout=30000; SELECT @r").fetchval()
        if lock<0:raise RuntimeError('Migration lock unavailable')
        existing=db.execute('SELECT dataset_hash,parser_version,state FROM dbo.qsm_import_batch').fetchall()
        fingerprint=info(stage,'source_fingerprint');version=info(stage,'parser_version')
        if existing:
            if len(existing)==1 and bytes(existing[0][0]).hex()==fingerprint and existing[0][1]==version and existing[0][2]=='published':
                result=verify(db,stage,asset_receipt=asset_receipt);result['replay_noop']=True;return result
            if not(len(existing)==1 and bytes(existing[0][0]).hex()==fingerprint and existing[0][1]==version and existing[0][2] in ('staging','failed','validated')):raise RuntimeError('Initial importer refuses a different existing snapshot; no overwrite')
            pointers=db.execute('SELECT current_full_batch_id,current_inventory_batch_id FROM dbo.qsm_source WHERE id=1').fetchone()
            if not pointers or any(x is not None for x in pointers):raise RuntimeError('Partial import has unexpected published pointers')
            db.execute("UPDATE dbo.qsm_import_batch SET state='staging',error_summary=NULL WHERE id=1")
        else:
            for table in TABLES:
                if db.execute('SELECT TOP(1) 1 FROM dbo.['+table+']').fetchone():raise RuntimeError('Initial import requires empty qsm tables')
            db.execute('BEGIN TRANSACTION;')
            insert_table(db,stage,'qsm_source',asset_receipt,False);insert_table(db,stage,'qsm_import_batch',asset_receipt,False)
            db.execute('COMMIT TRANSACTION; CHECKPOINT;')
        for short in ORDER[2:]:insert_table(db,stage,'qsm_'+short,asset_receipt)
        result=verify(db,stage,False,asset_receipt)
        db.execute('BEGIN TRANSACTION;')
        for batch in batches({'id':r['id'],'version':r['current_version_id']} for r in rows(stage,'qsm_document')):
            drain(db.cursor().execute('DECLARE @j nvarchar(max)=CONVERT(nvarchar(max),DECOMPRESS(CONVERT(varbinary(max),?))); UPDATE d SET current_version_id=j.version FROM dbo.qsm_document d JOIN OPENJSON(@j) WITH(id bigint,version bigint) j ON d.id=j.id WHERE d.source_id=1;',wire(batch)))
        now=utcnow()
        db.execute("UPDATE dbo.qsm_import_batch SET state='published',published_at=?,import_finished_at=?,updated_at=? WHERE id=1 AND source_id=1 AND valid=1 AND verification_passed=1",now,now,now)
        db.execute('UPDATE dbo.qsm_source SET current_full_batch_id=1,current_inventory_batch_id=1,updated_at=? WHERE id=1 AND valid=1',now)
        db.execute("UPDATE dbo.qsm_change_log SET action='publish',after_json=?,updated_at=? WHERE id=1",js({'state':'published','dataset_hash':fingerprint}),now)
        db.execute('COMMIT TRANSACTION; CHECKPOINT;');result['published']=True
        result['publication_time_utc']=now;result['replay_noop']=False
        return result
    except BaseException:
        try:db.execute('IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;')
        except Exception:pass
        raise
    finally:
        try:db.execute("EXEC sys.sp_releaseapplock @Resource=N'qsm-initial-migration',@LockOwner='Session'")
        except Exception:pass
        stage.close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--expected-database',required=True);p.add_argument('--stage',required=True);p.add_argument('--apply-schema',action='store_true');p.add_argument('--report',required=True);p.add_argument('--tunnel-server');p.add_argument('--asset-receipt')
    args=p.parse_args()
    db=connect_config(args.config,args.expected_database,args.tunnel_server)
    try:result=apply(db,args.stage,args.apply_schema,json.loads(Path(args.asset_receipt).read_text()) if args.asset_receipt else None)
    finally:db.close()
    Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');log('complete',database=result['database'],published=result['published'],replay_noop=result['replay_noop'])
