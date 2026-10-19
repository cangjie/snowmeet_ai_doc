"""Build portable file mappings and a local, searchable image/attachment index."""
import html
import json
import os
from pathlib import Path
from client import ROOT

DATA=ROOT/'data'
MEDIA=DATA/'media'

def main():
    source={}
    for name in ['products_all','sales','sales_history_details','purchases','purchases_history_details','sales_returns','purchase_returns','transfers','receipts','payments','stocktaking']:
        id_fields=['ProductId','SaleId','BuyId','ReturnId','TranId','ReceiveId','PaymentId','TakBillId']
        source[name]={}
        for line in (DATA/(name+'.jsonl')).open(encoding='utf-8'):
            row=json.loads(line)
            if isinstance(row.get('Data'),dict) and 'SourceId' in row:row=row['Data']
            identity=next((row[k] for k in id_fields if row.get(k)),None)
            source[name][str(identity)]=row
    manifest=json.loads((MEDIA/'manifest.json').read_text(encoding='utf-8'))
    files={r['url']:r for r in manifest['results']}
    refs=json.loads((MEDIA/'references.json').read_text(encoding='utf-8'))
    index=[]
    for ref in refs:
        receipt=files[ref['url']]
        row=source.get(ref['module'],{}).get(str(ref['id']),{})
        document=next((row[k] for k in ['SaleNo','BuyNo','ReturnNo','TranNo','ReceiveNo','PaymentNo','TakBillNo'] if row.get(k)),'')
        entry={**ref,'state':receipt['state'],'file':Path(receipt['file']).relative_to(MEDIA).as_posix() if receipt.get('file') else None,
               'sha256':receipt.get('sha256'),'bytes':receipt.get('bytes'),'product_code':row.get('ProductCode',''),
               'product_name':row.get('ProductName',''),'document_number':document,
               'business_date':next((row[k] for k in ['SaleDate','BuyDate','BusiDate','TransferDate','TakingDate','ReturnDate'] if row.get(k)),'')}
        index.append(entry)
    (MEDIA/'index.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in index),encoding='utf-8')
    serialized=json.dumps(index,ensure_ascii=False).replace('<','\\u003c')
    template=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>七色米图片与附件索引</title><style>body{font:15px system-ui;margin:24px;background:#f4f6f8;color:#203548}h1{font-size:24px}input,select,button{padding:10px;border:1px solid #b6c4cf;border-radius:6px}input{width:340px;max-width:80%}.tools{display:flex;gap:10px;flex-wrap:wrap;align-items:center}#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;margin:18px 0}.card{background:white;border-radius:8px;padding:12px;border:1px solid #dce2e7;overflow-wrap:anywhere}.card img{width:100%;height:180px;object-fit:contain;background:#f8fafb}.card p{margin:5px 0}.muted{font-size:12px;color:#687b8a}a{color:#1c648d}nav{display:flex;gap:15px;align-items:center}</style>
<h1>七色米图片与附件索引</h1><p>__ACCOUNT__ · 本地导出 · 按商品编号、商品名称或单据号搜索；点击图片可打开原文件。</p>
<div class="tools"><input id="query" placeholder="搜索商品或单据"><select id="category"><option value="">全部类型</option><option value="product_image">商品图片</option><option value="attachment">单据附件</option><option value="document_signature">单据签名</option></select><span id="count"></span></div><div id="grid"></div><nav><button id="prev">上一页</button><span id="page"></span><button id="next">下一页</button></nav>
<script>const data=__DATA__;let page=0,filtered=data;const size=48,$=id=>document.getElementById(id);const names={products_all:'商品',sales:'销售单',sales_history_details:'历史销售单',purchases:'进货单',purchases_history_details:'历史进货单',transfers:'调拨单',receipts:'收款单',payments:'付款单',stocktaking:'盘点单',sales_returns:'销售退货单',purchase_returns:'进货退货单'};
function draw(){const grid=$('grid');grid.replaceChildren();$('count').textContent=filtered.length+' 条文件引用';const pages=Math.max(1,Math.ceil(filtered.length/size));page=Math.max(0,Math.min(page,pages-1));$('page').textContent=(page+1)+' / '+pages;$('prev').disabled=page===0;$('next').disabled=page>=pages-1;for(const r of filtered.slice(page*size,(page+1)*size)){const card=document.createElement('div');card.className='card';const a=document.createElement('a');if(r.file){a.href=r.file;a.target='_blank';a.rel='noopener';if(/\.(jpe?g|png|webp|gif|bmp)$/i.test(r.file)){const img=document.createElement('img');img.src=r.file;img.loading='lazy';img.alt=r.product_name||r.name||'附件';a.append(img);}else a.textContent='打开附件';}else a.textContent='文件未下载';card.append(a);for(const text of [r.product_name||r.document_number||r.name||r.id,r.product_code||r.business_date,(names[r.module]||r.module)+' · '+r.name]){const p=document.createElement('p');p.textContent=text;card.append(p);}grid.append(card);}}
function filter(){const q=$('query').value.trim().toLowerCase(),c=$('category').value;filtered=data.filter(r=>(!c||r.category===c)&&(!q||[r.product_code,r.product_name,r.document_number,r.name,r.id].join(' ').toLowerCase().includes(q)));page=0;draw();}$('query').oninput=filter;$('category').onchange=filter;$('prev').onclick=()=>{page--;draw()};$('next').onclick=()=>{page++;draw()};draw();</script></html>'''
    (MEDIA/'图片与附件索引.html').write_text(template.replace('__ACCOUNT__',html.escape(os.environ.get('QISE_ACCOUNT_NAME','七色米账户'))).replace('__DATA__',serialized),encoding='utf-8')
    print(json.dumps({'references':len(index),'index':'media/图片与附件索引.html'},ensure_ascii=False))

if __name__=='__main__':main()
