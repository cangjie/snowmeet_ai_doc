"""Bounded-memory import packages; no uncompressed staging DB on the server."""
import gzip,hashlib,json,sqlite3
from contextlib import closing
from pathlib import Path
from load import ORDER,info,rows
from staging import js,sha_file

class Result:
    def __init__(self,values):self.values=iter(values)
    def __iter__(self):return self.values
    def fetchone(self):return next(self.values,None)

class StreamStage:
    def __init__(self,manifest,local_dir=None,s3_client=None):
        self.manifest=manifest;self.local_dir=Path(local_dir) if local_dir else None;self.client=s3_client
    def execute(self,sql,params=()):
        if sql.startswith('SELECT value FROM info'):return Result([(js(self.manifest['info'][params[0]]),)])
        if "json_extract(payload,'$.state')" in sql:return Result([('validated',1)])
        if sql.startswith('SELECT payload FROM staged'):
            return Result((line,) for line in self.lines(params[0]))
        raise ValueError('Unsupported streaming-stage query')
    def lines(self,table):
        entry=self.manifest['tables'][table]
        if self.local_dir:
            handle=(self.local_dir/entry['file']).open('rb')
        else:handle=self.client.get_object(Bucket=self.manifest['bucket'],Key=entry['object_key'])['Body']
        with closing(handle):
            with gzip.GzipFile(fileobj=handle) as stream:
                for line in stream:
                    if line.strip():yield line.decode('utf-8')
    def close(self):pass

def build(stage_path,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    stage=sqlite3.connect(stage_path);fingerprint=info(stage,'source_fingerprint')
    manifest={'bucket':'snowmeet-uploads-673751646617-cn-northwest-1-an','info':{k:info(stage,k) for k in ['source_fingerprint','parser_version','counts']},'tables':{}}
    plan=[]
    for i,short in enumerate(ORDER,1):
        table='qsm_'+short;path=output/(table+'.jsonl.gz')
        with path.open('wb') as file:
            with gzip.GzipFile(fileobj=file,mode='wb',mtime=0,compresslevel=5) as out:
                for r in rows(stage,table):
                    if table=='qsm_raw_record':r.pop('payload_json',None)
                    out.write((js(r)+'\n').encode())
        object_key='private/qisemi/datasets/'+fingerprint+'/import/'+info(stage,'parser_version')+'/'+path.name
        entry={'id':i,'source':str(path.resolve()),'relative_path':path.name,'object_key':object_key,'sha256':sha_file(path),'bytes':path.stat().st_size}
        plan.append(entry);manifest['tables'][table]={'file':path.name,'object_key':object_key,'sha256':entry['sha256'],'bytes':entry['bytes']}
    (output/'stream-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (output/'summary.json').write_text(js({'dataset_hash':fingerprint}),encoding='utf-8')
    (output/'file-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    print(js({'stage':'stream_package_built','files':len(plan),'bytes':sum(x['bytes'] for x in plan)}),flush=True)
    stage.close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();build(a.stage,a.output_dir)
