"""Run on the verified application server, streaming private S3 tables into localhost SQL."""
import argparse,json,sys
from pathlib import Path
from load import apply
from stream_package import StreamStage
from schema import TABLES

class Cursor:
    def __init__(self,cursor):self.cursor=cursor
    def execute(self,sql,*params):
        if params:self.cursor.execute(sql.replace('?','%s'),params)
        else:self.cursor.execute(sql)
        return self
    def fetchone(self):return self.cursor.fetchone()
    def fetchall(self):return self.cursor.fetchall()
    def fetchval(self):
        r=self.fetchone();return r[0] if r else None
    def nextset(self):return self.cursor.nextset()
    def __iter__(self):return iter(self.cursor)

class Database:
    def __init__(self,connection):self.connection=connection
    def cursor(self):return Cursor(self.connection.cursor())
    def execute(self,sql,*params):return self.cursor().execute(sql,*params)
    def close(self):self.connection.close()

def connect(config,expected_database,expected_identity):
    import pymssql
    values={k.strip().lower():v.strip() for p in Path(config).read_text().strip().split(';') if '=' in p for k,v in [p.split('=',1)]}
    database=values.get('database') or values.get('initial catalog')
    if database!=expected_database:raise ValueError('Unexpected application database config')
    c=pymssql.connect(server='127.0.0.1',port=1433,database=database,user=values.get('user id') or values.get('uid'),password=values.get('password') or values.get('pwd'),autocommit=True,login_timeout=20,timeout=300,charset='UTF-8')
    db=Database(c)
    identity=db.execute("SELECT CONVERT(varchar(50),service_broker_guid) FROM sys.databases WHERE name=DB_NAME()").fetchval()
    if identity.lower()!=expected_identity.lower():db.close();raise ValueError('Local SQL database identity differs from the verified configured target')
    return db

if __name__=='__main__':
    import botocore.session
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--asset-receipt',required=True);p.add_argument('--config',required=True);p.add_argument('--expected-database',required=True);p.add_argument('--expected-identity',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();manifest=json.loads(Path(a.manifest).read_text());assets=json.loads(Path(a.asset_receipt).read_text())
    client=botocore.session.get_session().create_client('s3',region_name='cn-northwest-1')
    for table,entry in manifest['tables'].items():
        if table not in TABLES or not entry['object_key'].startswith('private/qisemi/datasets/'+manifest['info']['source_fingerprint']+'/import/'):raise ValueError('Invalid import object scope')
        head=client.head_object(Bucket=manifest['bucket'],Key=entry['object_key'])
        if head['ContentLength']!=entry['bytes'] or head.get('Metadata',{}).get('sha256')!=entry['sha256']:raise ValueError('Unverified import package')
    db=connect(a.config,a.expected_database,a.expected_identity)
    try:result=apply(db,StreamStage(manifest,s3_client=client),True,assets)
    finally:db.close()
    Path(a.report).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'stage':'remote_complete','published':result['published'],'replay_noop':result['replay_noop']}),flush=True)
