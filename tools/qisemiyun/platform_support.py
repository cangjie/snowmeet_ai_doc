"""Local storage, native sessions, file locks, and physical-network connections."""
from __future__ import annotations
import contextlib
import ctypes
import hashlib
import http.client
import json
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path

CODE_ROOT=Path(__file__).resolve().parent
REPO_ROOT=CODE_ROOT.parents[1]

def data_home(platform=None,environ=None,home=None):
    platform=platform or sys.platform;environ=os.environ if environ is None else environ;home=Path(home or Path.home())
    if environ.get('QISE_HOME'):result=Path(environ['QISE_HOME']).expanduser()
    elif platform=='win32':result=Path(environ.get('LOCALAPPDATA',home/'AppData/Local'))/'Snowmeet/qisemiyun'
    elif platform=='darwin':result=home/'Library/Application Support/Snowmeet/qisemiyun'
    else:result=Path(environ.get('XDG_DATA_HOME',home/'.local/share'))/'snowmeet/qisemiyun'
    result=result.resolve()
    if result.is_relative_to(REPO_ROOT):raise RuntimeError('QISE_HOME 必须位于 Git 仓库之外，用于保存本机业务数据和会话。')
    return result

def dpapi(data,decrypt=False):
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    if decrypt:ok=ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:ok=ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    if not ok:raise ctypes.WinError()
    try:return ctypes.string_at(target.pbData,target.cbData)
    finally:ctypes.windll.kernel32.LocalFree(target.pbData)

class SessionStore:
    service='Snowmeet.QisemiCollector'
    def __init__(self,home=None,platform=None,backend=None):
        self.home=Path(home or data_home());self.platform=platform or sys.platform
        self.path=self.home/'session.dpapi'
        self.account=hashlib.sha256(str(self.home.resolve()).encode()).hexdigest()[:24]
        self._backend=backend
    @property
    def backend(self):
        if self._backend is None:
            if self.platform!='darwin':raise RuntimeError('仅支持 Windows DPAPI 和 macOS 系统钥匙串。')
            try:
                from keyring.backends.macOS import Keyring
                self._backend=Keyring()
            except (ImportError,OSError) as e:raise RuntimeError('macOS 钥匙串不可用，请在当前虚拟环境安装 requirements.txt。') from e
        return self._backend
    def load(self):
        if self.platform=='win32':raw=dpapi(self.path.read_bytes(),decrypt=True).decode('utf-8')
        elif self.platform=='darwin':
            try:raw=self.backend.get_password(self.service,self.account)
            except Exception as error:raise RuntimeError('无法读取 macOS 钥匙串，请确认当前用户钥匙串已解锁并允许访问。') from error
            if raw is None:raise FileNotFoundError('登录会话不存在，请先执行 login。')
        else:raise RuntimeError('登录会话只支持 Windows 和 macOS。')
        return json.loads(raw)
    def save(self,value):
        raw=json.dumps(value,ensure_ascii=False)
        if self.platform=='win32':
            self.home.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            temporary.write_bytes(dpapi(raw.encode('utf-8')));temporary.replace(self.path)
        elif self.platform=='darwin':
            try:self.backend.set_password(self.service,self.account,raw)
            except Exception as error:raise RuntimeError('无法保存到 macOS 钥匙串，请确认当前用户钥匙串已解锁并允许访问。') from error
        else:raise RuntimeError('登录会话只支持 Windows 和 macOS。')

def physical_adapters():
    if sys.platform=='win32':
        command="""$ErrorActionPreference='Stop'; @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | ForEach-Object {
          $qiseConfig=Get-NetIPConfiguration -InterfaceIndex $_.ifIndex
          if($qiseConfig.IPv4DefaultGateway){foreach($qiseAddress in $qiseConfig.IPv4Address){
            [pscustomobject]@{address=$qiseAddress.IPAddress;interface=$_.Name;metric=$qiseConfig.NetIPv4Interface.InterfaceMetric}
          }}
        }) | ConvertTo-Json -Compress"""
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
        values=json.loads(result.stdout or '[]');values=[values] if isinstance(values,dict) else values
        return sorted(values,key=lambda v:v.get('metric') or 0)
    if sys.platform=='darwin':
        result=[]
        for _,name in socket.if_nameindex():
            if not name.startswith('en'):continue
            probe=subprocess.run(['/usr/sbin/ipconfig','getifaddr',name],capture_output=True,text=True)
            address=probe.stdout.strip()
            if probe.returncode==0 and address:result.append({'address':address,'interface':name})
        return result
    raise RuntimeError('自动选择物理网卡目前只支持 Windows 和 macOS。')

def bound_socket(address,timeout,source_address,interface):
    """Darwin IP_BOUND_IF selects physical egress even with a VPN default route."""
    errors=[]
    for family,kind,protocol,_,remote in socket.getaddrinfo(address[0],address[1],socket.AF_INET,socket.SOCK_STREAM):
        sock=socket.socket(family,kind,protocol)
        try:
            sock.settimeout(timeout)
            # Apple xnu bsd/netinet/in.h defines IP_BOUND_IF = 25.
            # https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/in.h
            sock.setsockopt(socket.IPPROTO_IP,getattr(socket,'IP_BOUND_IF',25),socket.if_nametoindex(interface))
            sock.bind(source_address);sock.connect(remote);return sock
        except OSError as error:sock.close();errors.append(error)
    if errors:raise errors[-1]
    raise OSError('目标域名没有 IPv4 地址')

def http_connection(host,port=None,*,secure=True,timeout=35,source_ip=None,interface=None):
    source_ip=source_ip or os.environ.get('QISE_SOURCE_IP')
    interface=interface or os.environ.get('QISE_SOURCE_IFACE')
    if not source_ip:raise RuntimeError('尚未选择直连网卡，请通过 run.py 执行抓取。')
    cls=http.client.HTTPSConnection if secure else http.client.HTTPConnection
    connection=cls(host,port=port,timeout=timeout,source_address=(source_ip,0))
    if sys.platform=='darwin':
        if not interface:raise RuntimeError('macOS 直连需要物理网卡名称，例如 --source-interface en0。')
        connection._create_connection=lambda target,timeout,source_address:bound_socket(target,timeout,source_address,interface)
    return connection

@contextlib.contextmanager
def file_lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as lock:
        if os.name=='nt':
            import msvcrt
            lock.seek(0,2)
            if lock.tell()==0:lock.write(b'0');lock.flush()
            lock.seek(0)
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('已有一个抓取任务在运行，请等它完成。') from None
        else:
            import fcntl
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError('已有一个抓取任务在运行，请等它完成。') from None
        try:yield
        finally:
            if os.name=='nt':lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)
