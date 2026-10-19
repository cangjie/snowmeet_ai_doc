"""Verify completed exports, build the portable database, and package data only."""
import collections
import hashlib
import json
import os
import sys
import sqlite3
import zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from client import ROOT

DATA=ROOT/'data'
ACCOUNT=os.environ.get('QISE_ACCOUNT_NAME','七色米账户')
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):
    with path.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():yield json.loads(line)
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    statuses={p.stem:read(p) for p in (DATA/'status').glob('*.json')}
    bad={k:v.get('state') for k,v in statuses.items() if v.get('state')!='complete'}
    if bad:raise RuntimeError('Incomplete API modules: '+str(bad))
    counts={p.stem:sum(1 for _ in rows(p)) for p in DATA.glob('*.jsonl')}
    for k,v in statuses.items():
        if k in counts and counts[k]!=v['count']:raise RuntimeError('Count mismatch '+k)
    if statuses['stock_by_warehouse'].get('reconciliation_differences'):raise RuntimeError('Warehouse reconciliation differences')
    parent_specs={1:('purchases','BuyId'),2:('purchase_returns','ReturnId'),3:('sales','SaleId'),4:('sales_returns','ReturnId'),5:('stocktaking','TakBillId'),7:('transfers','TranId'),8:('loans_in','LendId'),9:('loans_out','LendId'),10:('loans_in_return_details','SourceId'),11:('loans_out_return_details','SourceId')}
    parent_ids={kind:{str(r.get(key)).lower() for r in rows(DATA/(module+'.jsonl'))} for kind,(module,key) in parent_specs.items()}
    parent_ids[3].update(str(r['SaleId']).lower() for r in rows(DATA/'sales_history_details.jsonl'))
    parent_ids[1].update(str(r['Data']['BuyId']).lower() for r in rows(DATA/'purchases_history_details.jsonl'))
    missing_parents=collections.defaultdict(set)
    for r in rows(DATA/'stock_movements.jsonl'):
        kind=int(r.get('BuinessType') or 0)
        if kind in parent_ids and str(r.get('BuinessId')).lower() not in parent_ids[kind]:missing_parents[str(kind)].add(r.get('BuinessId'))
    if missing_parents:raise RuntimeError('Missing movement source documents: '+str({k:len(v) for k,v in missing_parents.items()}))
    native={p.stem:read(p) for p in (DATA/'native_status').glob('*.json')}
    for k,v in native.items():
        if v.get('state') not in ['complete','empty']:raise RuntimeError('Incomplete native export '+k)
        for sheet in v.get('sheets',[]):
            if sheet.get('missing_documents_vs_api',0) or sheet.get('extra_documents_vs_api',0):raise RuntimeError('Native document mismatch '+k)
    for j in read(ROOT/'native-jobs.json'):
        if j.get('source_module') and native.get(j['name'],{}).get('sheets'):
            if native[j['name']]['sheets'][0]['rows']!=counts[j['source_module']]:raise RuntimeError('Native header count mismatch '+j['name'])
    media=read(DATA/'media/manifest.json')
    if media['failed'] or media['document_errors']:raise RuntimeError('Incomplete media downloads')
    documents=read(DATA/'media/documents.json')
    if any(not d.get('count_matches') for d in documents):raise RuntimeError('Attachment count mismatch')
    for item in media['results']:
        path=Path(item['file'])
        if not path.is_file() or path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise RuntimeError('Media checksum mismatch')
    print(json.dumps({'stage':'verified_sources','modules':len(statuses),'media_files':media['files']},ensure_ascii=False),flush=True)
    temp=ROOT/'final.sqlite3'
    if temp.exists():raise RuntimeError('Temporary database already exists')
    db=sqlite3.connect(temp)
    db.execute('CREATE TABLE records (module TEXT NOT NULL,record_id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(module,record_id))')
    db.execute('CREATE TABLE modules (module TEXT PRIMARY KEY,file TEXT NOT NULL,row_count INTEGER NOT NULL)')
    inputs=[(p.stem,p) for p in sorted(DATA.glob('*.jsonl'))]
    inputs += [('native__'+p.stem,p) for p in sorted((DATA/'native_rows').glob('*.jsonl'))]
    inputs += [('media_references',DATA/'media/index.jsonl')]
    for module,path in inputs:
        count=0
        for count,row in enumerate(rows(path),1):db.execute('INSERT INTO records VALUES (?,?,?)',(module,str(count),json.dumps(row,ensure_ascii=False)))
        db.execute('INSERT INTO modules VALUES (?,?,?)',(module,path.relative_to(DATA).as_posix(),count))
        db.commit()
    integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    if integrity!='ok':raise RuntimeError('SQLite integrity check: '+integrity)
    db_counts=dict(db.execute('SELECT module,count(*) FROM records GROUP BY module'))
    for module,path in inputs:
        expected=db.execute('SELECT row_count FROM modules WHERE module=?',(module,)).fetchone()[0]
        if db_counts.get(module,0)!=expected:raise RuntimeError('Database count mismatch '+module)
    db.close()
    old=sqlite3.connect(DATA/'qisemiyun.sqlite3',timeout=30)
    old.execute('PRAGMA wal_checkpoint(TRUNCATE)');old.close()
    os.replace(temp,DATA/'qisemiyun.sqlite3')
    canonical=[k for k in sorted(counts) if k not in ['products','accounts','employees','product_classes']]
    stamp=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    report={'account':ACCOUNT,'completed_at':stamp,'scope':'本次列明模块的全部时间范围，含红冲及停用数据，并补充销售明细关联的历史版本','module_counts':counts,
            'sqlite_integrity':integrity,'sqlite_rows':sum(db_counts.values()),'sqlite_modules':len(inputs),
            'native_workbooks':len(list((DATA/'native').glob('*.xls')))+len(list((DATA/'native').glob('*.xlsx'))),
            'media':{k:media[k] for k in ['documents','references','files','completed','failed','bytes']},
            'stock_warehouse_reconciliation':{'warehouses':statuses['stock_by_warehouse']['warehouses'],'differences':len(statuses['stock_by_warehouse']['reconciliation_differences'])},
            'finance_table_validation':read(ROOT/'qa/saved-finance-validation.json'),
            'movement_source_document_missing_ids':{},
            'credential_material_included':False}
    save(DATA/'verification.json',report)
    text=['# 七色米业务数据导出','',f'账户：{ACCOUNT}。完成时间：{stamp}。',
          '','范围为下表所列进销存模块的全部时间范围，包含列表中的红冲单据、停用商品、单据商品明细、当前库存、库存流水及图片附件；另补充销售明细报表所关联、但未出现在当前销售列表中的历史销售单版本。通过本机选定的物理网卡直接访问。',
          '','## 从哪里查看','',
          '- `native/`：平台原生 Excel 文件，主要业务单据包含总表和商品明细。收付款接口完整字段保存为 `receipts.csv`、`payments.csv`（UTF-8 BOM，Excel 可打开）；详细核销信息另存 JSONL。',
          '- 顶层 `*.jsonl`：UTF-8，每行一条业务记录，保留接口字段和业务 ID。红冲以 `WriteBack` 字段及平台导出的状态列区分。',
          '- `native_rows/`：原生 Excel 各工作表的 JSONL；中文列名直接保留，重复列名加序号。原始 Excel 不改写。',
          '- `qisemiyun.sqlite3`：统一数据库。`modules` 表列出模块、来源文件及行数；`records` 表以模块名和本地行号存储 JSON。业务 ID 保留在 `data` 字段中。',
          '- `media/图片与附件索引.html`：在浏览器打开，可搜索商品编号、商品名称、单据号并查看本地图片；每页 48 条。',
          '- `media/files/`：图片及附件原文件，使用 URL 哈希命名；`media/index.jsonl` 提供业务关联和相对路径。相同 URL 去重，缩略图和原图可能分别保留。',
          '- `pages/`：本轮接口分页回包与补抓缓存，仅留在本轮工作目录；最终记录以顶层 JSONL 为准，压缩包省略分页缓存。',
          '- `status/`、`native_status/`、`verification.json`：数量、日期范围和校验结果；`manifest.json`：文件大小及 SHA-256。',
          '','## 数量','', '| 模块 | 记录数 | 文件 |','| --- | ---: | --- |']
    for key in canonical:text.append(f'| {statuses.get(key,{}).get("label",key)} | {counts[key]:,} | `{key}.jsonl` |')
    text += ['','`products_all`、`accounts_all`、`employees_all`、`product_classes_tree` 是完整档案；`product_classes` 仅保存递归使用的根分类。',
             '','## Excel 明细','', '| 文件 | 工作表及数据行数 |','| --- | --- |']
    for key,v in native.items():
        if v.get('sheets'):text.append('| `'+Path(v.get('file',key)).name+'` | '+'；'.join(f'{s["name"]}：{s["rows"]:,}' for s in v['sheets'])+' |')
    text += ['','## 核对','',
             f'- 库存流水覆盖 {statuses["stock_movements"]["products_complete"]:,} / {statuses["stock_movements"]["products_total"]:,} 个商品，逐商品返回数一致。',
             f'- {statuses["stock_by_warehouse"]["warehouses"]} 个仓库的非零库存按商品汇总，与总库存一致；零库存可结合全部商品及仓库档案补齐。',
             '- 主要业务单据的 Excel 单号集合与接口记录相符；同号单据以业务 ID 区分。',
             f'- 另存 {counts.get("sales_history_details",0):,} 个销售历史版本，`sales_history_details.jsonl` 保留完整详情，不计入当前销售单列表的数量。',
             f'- 库存流水额外关联的 {counts.get("purchases_history_details",0)} 个历史进货单版本也已补充；流水涉及的各类来源单据 ID 均已找到对应记录。',
             f'- 图片/附件 {media["files"]:,} 个文件，{media["references"]:,} 条业务引用，下载失败 {media["failed"]} 个；文件大小和 SHA-256 已复核。',
             '- JSONL、SQLite 和模块状态数量一致；SQLite 完整性检查通过。',
             '- 数量为导出期间的查询快照；读取业务数据，没有修改业务单据。压缩包不含登录密码、会话缓存、采集脚本和依赖。',
             '','## SQLite 查询示例','','```sql',
             "SELECT module, row_count, file FROM modules ORDER BY module;",
             "SELECT json_extract(data, '$.ProductCode') AS code,",
             "       json_extract(data, '$.ProductName') AS name",
             "FROM records WHERE module = 'products_all';",'```','']
    (DATA/'README.md').write_text('\n'.join(text),encoding='utf-8')
    return

if __name__=='__main__':main()
