"""Build the approved-scope UI prototype only; no network or business services."""
import argparse
import base64
import html
import json
import mimetypes
from pathlib import Path

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='生成七色米交互原型；不连接业务接口和数据库。')
parser.add_argument('--output',type=Path,default=ROOT/'out/index.html')
parser.add_argument('--fragment-output',type=Path)
parser.add_argument('--image',type=Path,help='可选的本机演示商品图片；不经网络下载')
args=parser.parse_args()
modules=json.loads((ROOT/'modules.json').read_text(encoding='utf-8'))
fragment=(ROOT/'inventory.html').read_text(encoding='utf-8')+'\n'+(ROOT/'data-browser.html').read_text(encoding='utf-8')
fragment=fragment.replace('__QISEMI_MODULES__',json.dumps(modules,ensure_ascii=False,separators=(',',':')))
image=''
if args.image:
    data=args.image.read_bytes();mime=mimetypes.guess_type(args.image.name)[0]
    if mime not in ['image/png','image/jpeg','image/webp'] or len(data)>150_000:raise ValueError('演示图片需为不超过150KB的PNG/JPEG/WebP')
    image='data:'+mime+';base64,'+base64.b64encode(data).decode('ascii')
fragment=fragment.replace('__QISEMI_BOOT_IMAGE__',image)
if len(fragment.encode('utf-8'))>=1_000_000:raise ValueError('原型超过1MB')
if args.fragment_output:
    args.fragment_output.parent.mkdir(parents=True,exist_ok=True)
    args.fragment_output.write_text(fragment,encoding='utf-8')
prefix='<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>七色米 · 全业务数据原型</title><style>body{margin:0;padding:12px 0;background:#e4e8f0}</style></head><body>\n'
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(prefix+fragment+'\n</body></html>\n',encoding='utf-8')
print(str(args.output.resolve()))
if args.fragment_output:print(str(args.fragment_output.resolve()))
