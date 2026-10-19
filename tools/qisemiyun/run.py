"""Repeatable Qisemi exports. Every run starts in a new, empty snapshot folder."""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import getpass
import gzip
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import zipfile
from pathlib import Path
from platform_support import data_home, physical_adapters, http_connection, file_lock, SessionStore

BASE=Path(__file__).resolve().parent
TZ=dt.timezone(dt.timedelta(hours=8))
HOME=data_home()
CONFIGS=['config/modules.json']

def now():return dt.datetime.now(TZ)
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
def runtime_paths():
    if sys.version_info < (3,11):raise RuntimeError('需要 Python 3.11 或更新版本。')
    return Path(sys.executable)

def public_get(url,address,interface=None):
    for _ in range(4):
        parts=urllib.parse.urlsplit(url)
        if parts.scheme!='https' or not parts.hostname or not (parts.hostname=='qisemiyun.com' or parts.hostname.endswith('.qisemiyun.com')):
            raise ValueError('拒绝非七色米 HTTPS 公共资源地址')
        connection=http_connection(parts.hostname,timeout=12,source_ip=address,interface=interface)
        try:
            path=urllib.parse.quote(parts.path or '/',safe='/%:@')+('?'+parts.query if parts.query else '')
            connection.request('GET',path,headers={'User-Agent':'Mozilla/5.0'})
            response=connection.getresponse();body=response.read(25*1024*1024+1)
            if len(body)>25*1024*1024:raise RuntimeError('公共资源超出大小限制')
            if response.status in [301,302,303,307,308] and response.getheader('Location'):
                url=urllib.parse.urljoin(url,response.getheader('Location'));continue
            if response.status!=200:raise RuntimeError('公共资源 HTTP '+str(response.status))
            return gzip.decompress(body) if response.getheader('Content-Encoding')=='gzip' else body
        finally:connection.close()
    raise RuntimeError('公共资源重定向过多')

def application_asset(html):
    class Scripts(HTMLParser):
        def __init__(self):super().__init__();self.sources=[]
        def handle_starttag(self,tag,attributes):
            if tag=='script':
                source=dict(attributes).get('src','')
                if re.search(r'/js/app\.[^/?]+\.js(?:\?.*)?$',source):self.sources.append(source)
    parser=Scripts();parser.feed(html)
    if not parser.sources:raise RuntimeError('未能识别网站当前应用脚本')
    return urllib.parse.urljoin('https://web.qisemiyun.com/login',parser.sources[0])

def network(args):
    explicit=getattr(args,'source_interface',None)
    if args.source_ip:
        address=str(ipaddress.IPv4Address(args.source_ip));interface=explicit
        if sys.platform=='darwin' and not interface:
            interface=next((v['interface'] for v in physical_adapters() if v['address']==address),None)
        adapters=[{'address':address,'interface':interface}]
    else:adapters=physical_adapters()
    errors=[]
    for adapter in adapters:
        address=adapter['address'];interface=adapter.get('interface')
        try:
            html=public_get('https://web.qisemiyun.com/login',address,interface).decode('utf-8')
            script=public_get(application_asset(html),address,interface)
            app=HOME/'runtime'/('public-app-'+hashlib.sha256(script).hexdigest()[:16]+'.js')
            app.parent.mkdir(parents=True,exist_ok=True)
            if not app.exists():
                temporary=app.with_suffix('.'+str(os.getpid())+'.tmp');temporary.write_bytes(script);temporary.replace(app)
            os.environ.update(QISE_SOURCE_IP=address,QISE_SOURCE_IFACE=interface or '',QISE_PUBLIC_APP=str(app))
            import client
            client.SOURCE_IP=address;client.PUBLIC_APP=app
            client.Client()
            return address
        except Exception as error:errors.append(address+': '+str(error))
    raise RuntimeError('物理网卡直连失败；可用 --source-ip/--source-interface 指定本机网卡。'+'; '.join(errors))

def login_interactive():
    if not sys.stdin.isatty():raise RuntimeError('需要交互登录。请先在终端运行：python run.py login')
    from client import Client
    username=input('七色米用户名：').strip();password=getpass.getpass('密码（不回显、不保存密码）：')
    try:
        client=Client();result=client.login(username,password)
    finally:password=None
    if not result.get('IsSuccess') or not client.session.get('Token'):
        raise RuntimeError('登录未完成：'+str(result.get('Message') or result.get('RequestState')))
    print('登录成功。仅保存当前系统用户的受保护会话。',flush=True)
    return client

def authenticated(args):
    from client import Client
    try:client=Client.load()
    except FileNotFoundError:client=None
    if client is not None:
        result=client.post('/V1/User/Warehouse/QueryWarehouseList',{'Page':1,'Rp':1,'LoginClientType':1})
        if result.get('IsSuccess'):return client
    if args.non_interactive:raise RuntimeError('会话不存在或已过期。请手动执行 login 后重试。')
    return login_interactive()

def configured(session):
    modules={}
    for name in CONFIGS:
        for module in json.loads((BASE/name).read_text(encoding='utf-8')):modules[module['name']]=module
    def replace(value):
        if isinstance(value,str) and value.startswith('@session:'):
            key=value.split(':',1)[1]
            if not session.get(key):raise RuntimeError('登录会话缺少字段：'+key)
            return session[key]
        if isinstance(value,list):return [replace(x) for x in value]
        if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
        return value
    return replace(list(modules.values())),replace(json.loads((BASE/'config/native-jobs.json').read_text(encoding='utf-8')))

@contextlib.contextmanager
def run_lock():
    with file_lock(HOME/'collector.lock'):yield

def plan(scope,root,python):
    steps=[('商品与业务列表',[python,BASE/'export_lists.py',root/'modules-effective.json']),
           ('各仓库存及核对',[python,BASE/'warehouse_stock.py'])]
    if scope=='full':
        steps += [('库存流水',[python,BASE/'stock_movements.py']),('分类及盘点详情',[python,BASE/'supplemental.py']),
                  ('收付款及关联单据详情',[python,BASE/'augment.py']),('历史销售版本',[python,BASE/'sales_history.py'])]
    steps += [('原生 Excel',[python,BASE/'native_export.py','products_all','stock'] if scope=='inventory' else
               [python,BASE/'native_export.py','purchases_with_details','sales_with_details','transfers_with_details',
                'purchase_returns_with_details','sales_returns_with_details','purchase_orders_with_details',
                'loans_out_with_details','loans_in_with_details','products_all','clients','suppliers','stock'])]
    if scope=='full':steps += [('收付款 CSV',[python,BASE/'write_finance.py']),
                             ('图片与附件',[python,BASE/'media_export.py']),('图片索引',[python,BASE/'build_media_index.py']),
                             ('数据校验与合并',[python,BASE/'finalize.py','--verify-only']),('压缩及校验',[python,BASE/'package_final.py'])]
    return [(label,[str(v) for v in command]) for label,command in steps]

def execute(command,env,log):
    process=subprocess.Popen(command,cwd=BASE,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    try:
        for line in process.stdout:print(line,end='',flush=True);log.write(line);log.flush()
        code=process.wait()
    except BaseException:
        process.terminate();process.wait();raise
    if code:raise RuntimeError(f'步骤失败，退出码 {code}：{Path(command[1]).name}')

def check_statuses(root):
    for p in (root/'data/status').glob('*.json'):
        status=json.loads(p.read_text(encoding='utf-8'))
        if status.get('state')!='complete':raise RuntimeError('数据模块未完整：'+p.stem)
    for p in (root/'data/native_status').glob('*.json'):
        status=json.loads(p.read_text(encoding='utf-8'))
        if status.get('state') not in ['complete','empty']:raise RuntimeError('Excel 导出未完成：'+p.stem)

def finish_inventory(root):
    data=root/'data';check_statuses(root)
    status=json.loads((data/'status/stock_by_warehouse.json').read_text(encoding='utf-8'))
    if status['reconciliation_differences']:raise RuntimeError('仓库库存与总库存不一致')
    db=sqlite3.connect(data/'qisemiyun.sqlite3')
    db.execute('CREATE TABLE IF NOT EXISTS modules (module TEXT PRIMARY KEY,file TEXT,row_count INTEGER)')
    counts={}
    for p in sorted(data.glob('*.jsonl')):
        with p.open(encoding='utf-8') as source:count=sum(1 for l in source if l.strip())
        counts[p.stem]=count
        actual=db.execute('SELECT count(*) FROM records WHERE module=?',(p.stem,)).fetchone()[0]
        if actual!=count:raise RuntimeError('SQLite 数量不符：'+p.stem)
        db.execute('INSERT OR REPLACE INTO modules VALUES (?,?,?)',(p.stem,p.name,count))
    db.commit();integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    if integrity!='ok':raise RuntimeError('SQLite 完整性检查失败')
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.execute('PRAGMA journal_mode=DELETE');db.close()
    report={'completed_at':now().isoformat(timespec='seconds'),'scope':'商品档案、总库存及各仓库存新快照',
            'counts':counts,'sqlite_integrity':integrity,'warehouses':status['warehouses'],'reconciliation_differences':0}
    save(data/'verification.json',report)
    (data/'README.md').write_text('# 七色米库存快照\n\n完成时间：'+report['completed_at']+
        '\n\n本轮重新查询全部商品、仓库、门店、总库存和各仓非零库存；各仓汇总与总库存一致。\n'+
        '\nJSONL 保留接口字段；qisemiyun.sqlite3 可用 SQL 查询；native/ 是原生商品和库存 Excel。零库存未单列各仓明细，可结合商品和仓库档案补齐。\n'+
        '\n本模式只更新档案及当前库存，历史单据、库存流水和图片附件由 full 模式抓取。\n'+
        '\n```sql\nSELECT module, row_count FROM modules;\n```\n',encoding='utf-8')
    files=[p for p in data.rglob('*') if p.is_file() and 'pages' not in p.relative_to(data).parts and not p.name.endswith(('-wal','-shm','.tmp'))]
    entries=[{'path':p.relative_to(data).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
    save(data/'manifest.json',{'files':entries,'completed_at':report['completed_at']});files.append(data/'manifest.json')
    archive=root/('七色米-库存-'+now().strftime('%Y%m%d-%H%M%S')+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in files:z.write(p,p.relative_to(data).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise RuntimeError('ZIP 校验失败')
    save(root/'package-verification.json',{'archive':str(archive),'verified':True,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})

def collect(args):
    python=runtime_paths()
    root=HOME/'runs'/now().strftime('%Y%m%d-%H%M%S-%f')
    steps=plan(args.scope,root,python)
    if args.dry_run:
        print(json.dumps({'scope':args.scope,'fresh_snapshot':str(root),'network_requests':False,'steps':[{'label':k,'command':v} for k,v in steps]},ensure_ascii=False,indent=2));return
    with run_lock():
        address=network(args);client=authenticated(args)
        modules,jobs=configured(client.session)
        if args.scope=='inventory':modules=[m for m in modules if m['name'] in ['products_all','warehouses','branches','stock']]
        root.mkdir(parents=True,exist_ok=False)
        save(root/'modules-effective.json',modules);save(root/'native-jobs.json',jobs)
        env=os.environ.copy();env.update(QISE_OUTPUT_ROOT=str(root),QISE_CAPTURE_DATE=now().strftime('%Y-%m-%d'),QISE_ACCOUNT_NAME=str(client.session.get('ContactName') or '七色米账户'),PYTHONUTF8='1',PYTHONUNBUFFERED='1')
        state={'state':'running','scope':args.scope,'started_at':now().isoformat(timespec='seconds'),'source_ip':address,'output':str(root)}
        save(root/'run.json',state);print('新快照目录：'+str(root),flush=True)
        try:
            with (root/'run.log').open('w',encoding='utf-8') as log:
                for label,command in steps:
                    print('\n执行：'+label,flush=True)
                    execute(command,env,log)
                    check_statuses(root)
            if args.scope=='inventory':finish_inventory(root)
            state.update(state='complete',finished_at=now().isoformat(timespec='seconds'))
            save(root/'run.json',state)
            save(HOME/('latest-'+args.scope+'.json'),state)
            package=json.loads((root/'package-verification.json').read_text(encoding='utf-8'))
            print('完成：'+package['archive'],flush=True)
        except BaseException as error:
            state.update(state='failed',finished_at=now().isoformat(timespec='seconds'),error=str(error))
            save(root/'run.json',state);raise

def main():
    for stream in [sys.stdout,sys.stderr]:
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='七色米定期抓取：新快照、加密会话、物理网卡直连、防重复运行。')
    sub=parser.add_subparsers(dest='action',required=True)
    for name in ['login','doctor','run']:
        p=sub.add_parser(name);p.add_argument('--source-ip',help='指定物理网卡 IPv4；默认自动检测');p.add_argument('--source-interface',help='macOS 物理网卡名称，例如 en0')
        if name=='doctor':p.add_argument('--network',action='store_true',help='检测直连及当前公共签名格式，不登录')
        if name=='run':
            p.add_argument('--scope',choices=['inventory','full'],default='full')
            p.add_argument('--non-interactive',action='store_true',help='会话失效时直接失败，适合任务计划程序')
            p.add_argument('--dry-run',action='store_true',help='仅显示执行计划，不登录、不抓取、不创建快照')
    args=parser.parse_args()
    try:
        if args.action=='run':collect(args)
        elif args.action=='login':
            with run_lock():network(args);login_interactive()
        else:
            runtime_paths()
            import openpyxl,xlrd
            if sys.platform=='darwin':SessionStore().backend
            result={'python':sys.executable,'openpyxl':openpyxl.__version__,'xlrd':xlrd.__version__,
                    'platform':sys.platform,'data_home':str(HOME),'session_storage':'DPAPI' if sys.platform=='win32' else 'macOS Keychain'}
            if args.network:result['direct_source_ip']=network(args)
            print(json.dumps(result,ensure_ascii=False,indent=2))
    except (RuntimeError,OSError,ValueError,subprocess.CalledProcessError) as error:
        print('错误：'+str(error),file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
