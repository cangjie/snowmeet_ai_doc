"""Private local staging, exact numeric checks, and lossless raw JSON preservation."""
import collections
from datetime import datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
import gzip,hashlib,json,re,sqlite3,uuid
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from schema import TABLES

def js(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),default=lambda x:format(x,'f') if isinstance(x,Decimal) else str(x))

def utcnow():return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='milliseconds')

def key(value):
    if value is None or str(value).strip() in ('','null','None','00000000-0000-0000-0000-000000000000'):return None
    s=str(value).strip()
    try:return str(uuid.UUID(s))
    except ValueError:return s

def get(row,*keys):
    folded={k.lower():v for k,v in row.items()}
    return next((folded[k.lower()] for k in keys if folded.get(k.lower()) is not None),None)

def bit(v):
    if v in (True,1,'1','true','True'):return 1
    if v in (False,0,'0','false','False'):return 0
    return None

def number(v,scale=6):
    if v is None or v=='':return None
    try:d=Decimal(str(v).replace(',',''))
    except InvalidOperation:return None
    if not d.is_finite():raise ValueError('Nonfinite source numeric value')
    q=d.quantize(Decimal(1).scaleb(-scale))
    if abs(d-q)>Decimal('0.000000000001'):raise ValueError('Source number exceeds target precision')
    if abs(q)>=Decimal(10)**(19-scale):raise ValueError('Source number exceeds target range')
    return format(q,'f')

def dt(value,utc=False):
    if value is None or value in ('','null'):return None
    try:
        if isinstance(value,(int,float)) or re.fullmatch(r'\d{13}',str(value)):
            d=datetime.fromtimestamp(float(value)/1000,timezone.utc)
            d=d if utc else d.astimezone(timezone(timedelta(hours=8)))
        else:
            s=str(value).strip().replace('/','-')
            d=datetime.fromisoformat(s.replace('Z','+00:00'))
            if utc:
                if d.tzinfo is None:d=d.replace(tzinfo=timezone(timedelta(hours=8)))
                d=d.astimezone(timezone.utc)
        return d.replace(tzinfo=None).isoformat(timespec='milliseconds')
    except (ValueError,OverflowError,OSError):return None

def safe_url(value):
    p=urlsplit(value)
    denied={'token','access_token','authorization','auth','signature','x-amz-signature','x-amz-credential','x-amz-security-token'}
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k.lower() not in denied]),p.fragment))

def scrub(value):
    denied={'password','pwd','access_token','accesstoken','refresh_token','refreshtoken','authorization','cookie','set-cookie','sessiontoken','sessionid','logintoken'}
    if isinstance(value,dict):return {k:scrub(v) for k,v in value.items() if k.lower() not in denied}
    if isinstance(value,list):return [scrub(v) for v in value]
    if isinstance(value,str) and value.startswith(('https://','http://')):return safe_url(value)
    return value

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

class Stage:
    def __init__(self,path,resume_raw=False):
        self.path=Path(path)
        existing=self.path.exists()
        if existing and not resume_raw:raise ValueError('Stage already exists; select a new output directory')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=NORMAL')
        if not existing:
            self.db.execute('CREATE TABLE staged(table_name TEXT,id INTEGER,payload TEXT NOT NULL,PRIMARY KEY(table_name,id))')
            self.db.execute('CREATE TABLE raw_index(module TEXT,ordinal INTEGER,id INTEGER,source_key TEXT,PRIMARY KEY(module,ordinal))')
            self.db.execute('CREATE INDEX raw_lookup ON raw_index(module,source_key)')
            self.db.execute('CREATE TABLE info(key TEXT PRIMARY KEY,value TEXT)')
        else:
            if self.get('import_batch',1)['state']!='staging':raise ValueError('Only an unpublished unfinished stage can resume')
            # Only discard derived records in the explicitly chosen local staging DB.
            self.db.execute("DELETE FROM staged WHERE table_name NOT IN ('qsm_source','qsm_import_batch','qsm_import_module','qsm_raw_record','qsm_file','qsm_file_ref','qsm_export_sheet')")
            self.db.execute("DELETE FROM staged WHERE table_name='qsm_file_ref' AND json_extract(payload,'$.reference_kind')<>'export'")
            self.db.commit()
        self.seq=collections.Counter(dict(self.db.execute('SELECT table_name,MAX(id) FROM staged GROUP BY table_name')));self.now=utcnow()

    def add(self,t,**values):
        t=t if t.startswith('qsm_') else 'qsm_'+t
        self.seq[t]+=1
        row={}
        values=dict(values,id=self.seq[t],created_by='qisemi-import',updated_by='qisemi-import')
        if 'source_id' in TABLES[t]:values.setdefault('source_id',1)
        for c,spec in TABLES[t].items():
            if c=='row_version':continue
            v=values.get(c)
            if c not in values:
                if ' DEFAULT ' in spec:
                    default=spec.split(' DEFAULT ',1)[1]
                    v=self.now if default=='SYSUTCDATETIME()' else default.removeprefix('N').strip("'") if default.startswith(("'","N'")) else int(default)
                else:v=None
            if v is None and ' NOT NULL' in spec:raise ValueError(f'Missing required field {t}.{c}')
            if v is not None:
                if spec.startswith(('nvarchar','varchar')):
                    v=str(v);m=re.match(r'n?varchar\((\d+)\)',spec)
                    if m and len(v.encode('utf-16-le'))//2>int(m[1]):raise ValueError(f'Overlong {t}.{c}: {len(v)}')
                elif spec.startswith('decimal'):v=number(v,int(re.search(r',(\d+)\)',spec)[1]))
                elif spec.startswith(('bigint','int','bit')):v=int(v)
                elif isinstance(v,bytes):v=v.hex()
            row[c]=v
        extra=set(values)-set(TABLES[t])
        if extra:raise ValueError(f'Unknown columns {t}: {sorted(extra)}')
        self.db.execute('INSERT INTO staged VALUES(?,?,?)',(t,row['id'],js(row)))
        return row['id']

    def update(self,t,id,**fields):
        t=t if t.startswith('qsm_') else 'qsm_'+t
        r=self.get(t,id);r.update(fields)
        self.db.execute('UPDATE staged SET payload=? WHERE table_name=? AND id=?',(js(r),t,id))

    def get(self,t,id):
        t=t if t.startswith('qsm_') else 'qsm_'+t
        return json.loads(self.db.execute('SELECT payload FROM staged WHERE table_name=? AND id=?',(t,id)).fetchone()[0])

    def rows(self,t):
        t=t if t.startswith('qsm_') else 'qsm_'+t
        for (p,) in self.db.execute('SELECT payload FROM staged WHERE table_name=? ORDER BY id',(t,)):yield json.loads(p)

    def raw(self,module):
        for rid,ordinal,p in self.db.execute("SELECT r.id,r.ordinal,s.payload FROM raw_index r JOIN staged s ON s.table_name='qsm_raw_record' AND s.id=r.id WHERE r.module=? ORDER BY r.ordinal",(module,)):
            yield rid,ordinal,json.loads(json.loads(p)['payload_json'])

    def add_raw(self,module,module_id,batch_id,row_ordinal,value,source_key=None,parent_key=None,sheet_id=None,duplicate=1):
        p=js(scrub(value));h=hashlib.sha256(p.encode()).hexdigest()
        rid=self.add('raw_record',batch_id=batch_id,module_id=module_id,row_ordinal=row_ordinal,source_entity_key=key(source_key),parent_source_key=key(parent_key),payload_json=p,payload_gzip=gzip.compress(p.encode('utf-16-le'),compresslevel=5,mtime=0).hex(),payload_hash=h,duplicate_ordinal=duplicate,sheet_id=sheet_id)
        self.db.execute('INSERT INTO raw_index VALUES(?,?,?,?)',(module,row_ordinal,rid,key(source_key)))
        return rid

    def info(self,k,v):self.db.execute('INSERT OR REPLACE INTO info VALUES(?,?)',(k,js(v)))
    def finish(self):self.db.commit();self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)');self.db.close()
