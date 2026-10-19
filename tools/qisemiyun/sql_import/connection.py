"""Read an explicitly selected existing .NET SQL config without logging credentials."""
from pathlib import Path
import re

def connect_config(path,expected_database,tunnel_server=None):
    import pyodbc
    values={}
    # Supports the repository's existing simple config format. Fail closed on ambiguous syntax.
    for part in Path(path).read_text(encoding='utf-8-sig').strip().split(';'):
        if not part.strip():continue
        if '=' not in part:raise ValueError('Unsupported connection configuration')
        k,v=part.split('=',1);values[k.strip().lower()]=v.strip()
    def pick(*keys):return next((values[k] for k in keys if values.get(k)),None)
    database=pick('database','initial catalog')
    if not expected_database or database!=expected_database:raise ValueError('Database does not match --expected-database')
    driver=next((d for d in ['ODBC Driver 18 for SQL Server','ODBC Driver 17 for SQL Server','SQL Server'] if d in pyodbc.drivers()),None)
    if not driver:raise RuntimeError('Install a SQL Server ODBC driver')
    q=lambda v:'{'+str(v).replace('}','}}')+'}'
    if tunnel_server and not re.fullmatch(r'127\.0\.0\.1,\d{1,5}',tunnel_server):raise ValueError('SSH tunnel must bind IPv4 loopback')
    fields={'DRIVER':driver,'SERVER':tunnel_server or pick('server','data source'),'DATABASE':database,'UID':pick('user id','uid'),'PWD':pick('password','pwd'),'Encrypt':'no' if tunnel_server else 'yes','TrustServerCertificate':pick('trustservercertificate') or 'yes'}
    if not all(fields.values()):raise ValueError('Incomplete SQL configuration')
    db=pyodbc.connect(';'.join(k+'='+q(v) for k,v in fields.items()),timeout=20,autocommit=True)
    db.timeout=120
    if db.cursor().execute('SELECT DB_NAME()').fetchval()!=expected_database:
        db.close();raise RuntimeError('Unexpected live database')
    return db

def drain(cursor):
    while cursor.nextset():pass
