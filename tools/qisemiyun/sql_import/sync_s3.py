"""Upload to the existing Snowmeet private S3 prefix; IAM secrets stay on EC2."""
import argparse,base64,concurrent.futures,gzip,hashlib,http.client,json,mimetypes,shlex,subprocess,sys,time,uuid
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from platform_support import physical_adapters,http_connection

REMOTE=r'''
import base64,concurrent.futures,gzip,hashlib,json,sys,urllib.request,urllib.error,uuid
import botocore.session
from botocore.config import Config
request=json.loads(gzip.decompress(sys.stdin.buffer.read()))
bucket='snowmeet-uploads-673751646617-cn-northwest-1-an'
region='cn-northwest-1'
client=botocore.session.get_session().create_client('s3',region_name=region,config=Config(signature_version='s3v4',max_pool_connections=24))
action=request['action']
if action=='probe':
    key='private/qisemi/probes/'+request.get('dataset_hash',str(uuid.uuid4()))+'.txt';body=b'Qisemi private storage probe'
    client.put_object(Bucket=bucket,Key=key,Body=body,ContentMD5=base64.b64encode(hashlib.md5(body).digest()).decode())
    states=[]
    try:
        for url in ['https://'+bucket+'.s3.'+region+'.amazonaws.com.cn/'+key,'https://img.snowmeet.top/'+key]:
            try:
                with urllib.request.urlopen(url,timeout=30) as response:states.append(response.status)
            except urllib.error.HTTPError as e:states.append(e.code)
        result={'bucket':bucket,'region':region,'anonymous_statuses':states,'private_verified':all(x in (403,404) for x in states)}
    finally:pass  # The application IAM role deliberately has no physical-delete permission.
elif action=='sign':
    signed=[]
    for f in request['files']:
        key=f['object_key']
        if not key.startswith('private/qisemi/datasets/') or '..' in key.split('/'):raise ValueError('Unexpected private prefix')
        params={'Bucket':bucket,'Key':key,'ContentMD5':f['md5'],'Metadata':{'sha256':f['sha256']},'ContentType':f['mime_type'],'CacheControl':'private, no-store'}
        signed.append({'id':f['id'],'url':client.generate_presigned_url('put_object',Params=params,ExpiresIn=3600)})
    result={'signed':signed}
elif action=='verify':
    def check(f):
        r=client.head_object(Bucket=bucket,Key=f['object_key'])
        return r['ContentLength']==f['bytes'] and r.get('Metadata',{}).get('sha256')==f['sha256']
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:ok=list(pool.map(check,request['files']))
    result={'verified':all(ok),'files':len(ok),'bytes':sum(x['bytes'] for x in request['files']),'bucket':bucket,'region':region,'storage_provider':'s3','prefix':'private/qisemi/datasets/','dataset_hash':request['dataset_hash'],'failed_count':sum(not x for x in ok)}
else:raise ValueError('Unknown action')
sys.stdout.buffer.write(gzip.compress(json.dumps(result).encode()))
'''

def remote(host,port,request):
    code='import base64;exec(base64.b64decode('+repr(base64.b64encode(REMOTE.encode()).decode())+'))'
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-p',str(port),host,'python3 -c '+shlex.quote(code)],input=gzip.compress(json.dumps(request).encode()),capture_output=True,timeout=240)
    if p.returncode:raise RuntimeError('Private S3 operation failed: '+p.stderr.decode(errors='replace')[:2000])
    return json.loads(gzip.decompress(p.stdout))

def sync(prepared,host,port,report,workers=12):
    prepared=Path(prepared);summary=json.loads((prepared/'summary.json').read_text(encoding='utf-8'));plan=json.loads((prepared/'file-plan.json').read_text(encoding='utf-8'))
    probe=remote(host,port,{'action':'probe','dataset_hash':summary['dataset_hash']})
    if not probe.get('private_verified'):raise RuntimeError('Anonymous access probe did not confirm private storage')
    print(json.dumps({'stage':'s3_private_verified','anonymous_statuses':probe['anonymous_statuses']}),flush=True)
    descriptors=[]
    for f in plan:
        body=Path(f['source']).read_bytes()
        if len(body)!=f['bytes'] or hashlib.sha256(body).hexdigest()!=f['sha256']:raise ValueError('Source file changed')
        key=f['object_key'];key=key if key.startswith('private/qisemi/') else 'private/qisemi/'+key
        descriptors.append({'id':f['id'],'object_key':key,'sha256':f['sha256'],'bytes':f['bytes'],'md5':base64.b64encode(hashlib.md5(body).digest()).decode(),'mime_type':mimetypes.guess_type(f['source'])[0] or 'application/octet-stream'})
    signed=remote(host,port,{'action':'sign','files':descriptors})
    urls={r['id']:r['url'] for r in signed['signed']}
    network=physical_adapters()[0]
    def upload(pair):
        f,d=pair;parts=urlsplit(urls[f['id']]);body=Path(f['source']).read_bytes()
        for attempt in range(3):
            conn=None
            try:
                conn=http_connection(parts.hostname,timeout=90,source_ip=network['address'],interface=network.get('interface'))
                conn.request('PUT',parts.path+'?'+parts.query,body=body,headers={'Content-Length':str(len(body)),'Content-MD5':d['md5'],'Content-Type':d['mime_type'],'Cache-Control':'private, no-store','x-amz-meta-sha256':d['sha256']})
                response=conn.getresponse();response.read()
                if response.status!=200:raise RuntimeError('S3 upload HTTP '+str(response.status))
                return f['id']
            except Exception:
                if attempt==2:raise RuntimeError('Private object upload failed for file id '+str(f['id'])) from None
                time.sleep(attempt+1)
            finally:
                if conn:conn.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(upload,pair) for pair in zip(plan,descriptors)]
        for i,future in enumerate(concurrent.futures.as_completed(futures),1):
            future.result()
            if i%250==0:print(json.dumps({'stage':'s3_upload','files':i,'total':len(plan)}),flush=True)
    result=remote(host,port,{'action':'verify','files':descriptors,'dataset_hash':summary['dataset_hash']})
    if not result.get('verified'):raise RuntimeError('Private S3 verification failed')
    result['anonymous_statuses']=probe['anonymous_statuses']
    Path(report).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--ssh-host',required=True);p.add_argument('--ssh-port',type=int,default=2222);p.add_argument('--report',required=True);p.add_argument('--workers',type=int,default=12)
    a=p.parse_args();sync(a.prepared,a.ssh_host,a.ssh_port,a.report,a.workers)
