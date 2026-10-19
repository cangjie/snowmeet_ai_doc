"""Package the verified deliverables; leave duplicate request caches locally."""
import hashlib
import json
import zipfile
from pathlib import Path
from client import ROOT

DATA=ROOT/'data'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    verification=json.loads((DATA/'verification.json').read_text(encoding='utf-8'))
    assert verification['sqlite_integrity']=='ok' and not verification['movement_source_document_missing_ids']
    media=json.loads((DATA/'media/manifest.json').read_text(encoding='utf-8'))
    assert media['failed']==0 and not media['document_errors']
    readme=DATA/'README.md';s=readme.read_text(encoding='utf-8')
    s=s.replace('- `pages/`：接口分页回包与补抓缓存。最终记录以顶层 JSONL 为准，缓存保留了部分较早的过滤条件快照。',
                '- 接口分页回包及采集缓存保留在本机原目录 `data/pages/`。压缩包提供顶层 JSONL 完整记录、业务附件关联及校验清单。')
    readme.write_text(s,encoding='utf-8')
    files=[p for p in DATA.iterdir() if p.is_file() and p.name!='manifest.json' and p.suffix in ['.jsonl','.sqlite3','.md','.json']]
    for folder in ['native','native_rows','status','native_status']:
        files += [p for p in (DATA/folder).iterdir() if p.is_file() and not p.name.endswith('.inspect.ndjson')]
    files += [DATA/'media'/n for n in ['manifest.json','documents.json','references.json','index.jsonl','图片与附件索引.html']]
    known={}
    for item in media['results']:
        p=Path(item['file']);assert p.stat().st_size==item['bytes'];files.append(p);known[p.resolve()]=item['sha256']
    files=sorted(set(files));entries=[]
    for i,p in enumerate(files,1):
        entries.append({'path':p.relative_to(DATA).as_posix(),'bytes':p.stat().st_size,'sha256':known.get(p.resolve()) or sha(p)})
        if i%1000==0:print(json.dumps({'stage':'manifest','processed':i,'total':len(files)}),flush=True)
    manifest={'account':verification['account'],'completed_at':verification['completed_at'],'files':entries,'total_bytes':sum(x['bytes'] for x in entries),
              'source_media_hashes':'All media content hashes were verified before the database was built; unchanged files reuse those verified hashes.'}
    (DATA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    files.append(DATA/'manifest.json')
    archive=ROOT/('七色米-全部业务数据-'+verification['completed_at'][:19].replace('-','').replace(':','').replace('T','-')+'.zip')
    print(json.dumps({'stage':'packaging','files':len(files),'uncompressed_bytes':manifest['total_bytes']},ensure_ascii=False),flush=True)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as z:
        for i,p in enumerate(files,1):
            compression=zipfile.ZIP_STORED if p.parent.name=='files' else zipfile.ZIP_DEFLATED
            z.write(p,p.relative_to(DATA).as_posix(),compress_type=compression)
            if i%1000==0:print(json.dumps({'stage':'packaging','processed':i,'total':len(files)}),flush=True)
    print(json.dumps({'stage':'zip_crc_verification','bytes':archive.stat().st_size}),flush=True)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        assert not any('session.dpapi' in n or 'node_modules' in n or n.endswith('.inspect.ndjson') for n in z.namelist())
    result={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'entries':len(files),'verified':True}
    (ROOT/'package-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
