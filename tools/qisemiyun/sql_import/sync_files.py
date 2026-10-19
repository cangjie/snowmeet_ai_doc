"""Stream verified media/workbooks to a private directory, without a remote archive copy."""
import argparse,base64,io,json,shlex,subprocess,tarfile
from pathlib import Path
from staging import sha_file

REMOTE_SCRIPT=r'''
import hashlib,json,os,pathlib,sys,tarfile
root=pathlib.Path(sys.argv[1]).resolve()
if str(root)!='/home/ubuntu/data/qisemi':raise SystemExit('Unexpected private storage root')
root.mkdir(parents=True,exist_ok=True,mode=0o700)
os.umask(0o077)
archive=tarfile.open(fileobj=sys.stdin.buffer,mode='r|')
members=iter(archive);member=next(members);manifest=json.load(archive.extractfile(member))
fingerprint=manifest['dataset_hash']
if len(fingerprint)!=64 or any(c not in '0123456789abcdef' for c in fingerprint):raise SystemExit('Invalid dataset hash')
prefix='datasets/'+fingerprint+'/'
expected={x['object_key']:x for x in manifest['files']}
seen=set();total=0
for member in members:
    if not member.isfile() or member.name not in expected or not member.name.startswith(prefix):raise SystemExit('Unexpected archive member')
    relative=pathlib.PurePosixPath(member.name)
    if relative.is_absolute() or '..' in relative.parts:raise SystemExit('Unsafe archive member')
    dest=(root/str(relative)).resolve()
    if not dest.is_relative_to(root):raise SystemExit('Storage path escapes root')
    entry=expected[member.name]
    if member.size!=entry['bytes']:raise SystemExit('File length mismatch')
    dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=dest.with_name(dest.name+'.qsm-part')
    h=hashlib.sha256();n=0
    with archive.extractfile(member) as source,temp.open('wb') as target:
        for block in iter(lambda:source.read(1024*1024),b''):target.write(block);h.update(block);n+=len(block)
    if h.hexdigest()!=entry['sha256'] or n!=entry['bytes']:
        temp.unlink();raise SystemExit('Checksum mismatch')
    os.chmod(temp,0o600);os.replace(temp,dest);seen.add(member.name);total+=n
if seen!=set(expected):raise SystemExit('Incomplete file set')
receipt=root/'datasets'/fingerprint/'file-receipt.json'
receipt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');os.chmod(receipt,0o600)
print(json.dumps({'dataset_hash':fingerprint,'files':len(seen),'bytes':total,'verified':True,'storage_root':str(root)}))
'''

def sync(prepared,host,port,output):
    prepared=Path(prepared);summary=json.loads((prepared/'summary.json').read_text(encoding='utf-8'));plan=json.loads((prepared/'file-plan.json').read_text(encoding='utf-8'))
    # Preserve only destination metadata in the remote receipt; no local paths.
    manifest={'dataset_hash':summary['dataset_hash'],'files':[{k:v for k,v in r.items() if k not in ('source','relative_path')} for r in plan]}
    encoded=base64.b64encode(REMOTE_SCRIPT.encode()).decode()
    command='python3 -c '+shlex.quote('import base64;exec(base64.b64decode('+repr(encoded)+'))')+' /home/ubuntu/data/qisemi'
    proc=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-p',str(port),host,command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdin,mode='w|') as archive:
            body=json.dumps(manifest,ensure_ascii=False).encode();m=tarfile.TarInfo('manifest.json');m.size=len(body);m.mode=0o600;archive.addfile(m,io.BytesIO(body))
            for i,r in enumerate(plan,1):
                p=Path(r['source'])
                if p.stat().st_size!=r['bytes'] or sha_file(p)!=r['sha256']:raise ValueError('Source file changed since preparation')
                archive.add(p,arcname=r['object_key'],recursive=False)
                if i%500==0:print(json.dumps({'stage':'file_transfer','files':i,'total':len(plan)}),flush=True)
        proc.stdin.close();proc.stdin=None
        stdout,stderr=proc.communicate()
        if proc.returncode:raise RuntimeError('Private file transfer failed: '+stderr.decode(errors='replace')[:2000])
        result=json.loads(stdout)
        if not result.get('verified') or result['files']!=len(plan) or result['dataset_hash']!=summary['dataset_hash']:raise ValueError('Remote receipt mismatch')
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
        return result
    except BaseException:
        proc.kill();proc.wait();raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--ssh-host',required=True);p.add_argument('--ssh-port',type=int,default=2222);p.add_argument('--report',required=True)
    args=p.parse_args();sync(args.prepared,args.ssh_host,args.ssh_port,args.report)
