# -*- coding: utf-8 -*-
"""
小程序孤儿页面 / 孤儿组件扫描（生成 unreachable_pages.md 的依据）

用法：
    py snowmeet_ai_doc/scan_unreachable_pages.py [小程序目录] [后端目录]
    默认 D:/source/snowmeet/ai/snowmeet_wechat_mini 与 .../SnowmeetApi

判定口径（踩过坑之后定下来的，改之前先读注释）：

【页面可达】
  把每个活文件里的**所有字符串字面量**取出来，按三种方式尝试解析成注册页面路径：
    · 绝对        '/pages/admin/member/member_list'
    · 相对本文件目录  admin.js 里的 'rent/new_rent_list' -> pages/admin/rent/new_rent_list
    · 截断 query   'recept_member_info?memberId=' -> recept_member_info
  只有**精确解析到某个已注册页面**才算入口。
  - 只搜全路径会漏判：本项目大量相对跳转，admin.js 还是先 `path = 'rent/xxx'` 再 navigateTo
  - 只搜 basename 会太松：名字在注释里出现一次就被当成"被调用"

【组件可达】
  被某个活文件的 usingComponents 注册，**且它的标签真的出现在那个文件的 wxml 里**。
  app.json 里的全局注册：标签出现在任意活 wxml 里即可。
  （只看注册会漏掉一大批"注册了从来不用"的死组件——2026-07-27 删掉的 5 个全是这种）

【迭代】
  删掉的东西可能让别的东西变孤儿，所以反复算到不动点。

【KEEP_PAGES】
  有些页面的入口在**代码之外**（公众平台「扫普通链接二维码打开小程序」规则），
  静态分析永远看不到。这类页面必须钉成"活的"，否则它们依赖的组件会被连带误判
  （实测：把 pages/register/reg 当死页，components/user_info/auth_cell 立刻被误报成孤儿）。
"""
import json, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')

MINI = sys.argv[1] if len(sys.argv) > 1 else r'D:\source\snowmeet\ai\snowmeet_wechat_mini'
API = sys.argv[2] if len(sys.argv) > 2 else r'D:\source\snowmeet\ai\SnowmeetApi'

SKIP = {'node_modules', 'miniprogram_npm', '.git'}
# 这些文件里出现页面路径只是"注册/配置"，不是"调用"
NOT_CALLER = {'app.json', 'project.config.json', 'project.private.config.json'}

# 入口在代码之外、必须保留的页面（改动前先去公众平台核对扫码规则列表）
KEEP_PAGES = {
    'pages/order/payment_entry',        # mapp/order_payment 扫码落地
    'pages/order/identity_verify',      # mapp/order_verify 扫码落地
    'pages/mine/ticket/ticket_bind',    # 疑似扫券码入口，待核实
    'pages/register/reg',
    'pages/register/out_reg',
}


def walk(root, exts):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            if os.path.splitext(f)[1].lower() in exts:
                yield os.path.join(dp, f)


def read(p):
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            with open(p, encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ''


def rel(p):
    return os.path.relpath(p, MINI).replace('\\', '/')


appj = json.loads(read(os.path.join(MINI, 'app.json')))
pages = [p.strip('/') for p in appj.get('pages', [])]
main_cnt = len(pages)
for k in ('subPackages', 'subpackages'):
    for sp in appj.get(k, []) or []:
        r = sp.get('root', '').strip('/')
        pages += [(r + '/' + p).strip('/') for p in sp.get('pages', [])]
pageset = set(pages)

comps = []
for f in walk(os.path.join(MINI, 'components'), {'.json'}):
    try:
        if json.loads(read(f)).get('component') is True:
            comps.append(rel(f).rsplit('.', 1)[0])
    except Exception:
        pass
compset = set(comps)
GLOBAL_UC = appj.get('usingComponents', {}) or {}


def resolve_uc(value, from_dir):
    v = str(value).strip()
    # 外部包（vant / weui 扩展库 / vtabs）不在扫描范围
    if v.startswith('@') or v.startswith('weui-miniprogram') or v.startswith('miniprogram_npm'):
        return None
    if v.startswith('/'):
        return v.lstrip('/')
    return os.path.normpath(os.path.join(from_dir, v)).replace('\\', '/')


LITERAL = re.compile(r"""['"`]([^'"`\n]{2,160})['"`]""")

api_routes = set()
if os.path.isdir(API):
    for f in walk(API, {'.cs', '.html', '.js'}):
        for m in re.finditer(r"mapp/([A-Za-z0-9_\-/]+)", read(f)):
            api_routes.add(m.group(1))
            api_routes.add('pages/' + m.group(1))

dead_pages, dead_comps = set(), set()
for rnd in range(1, 12):
    live_units = [p for p in pages if p not in dead_pages] + \
                 [c for c in comps if c not in dead_comps]
    text = {}
    for u in live_units:
        for ext in ('.js', '.wxml', '.json', '.wxs'):
            p = os.path.join(MINI, u.replace('/', os.sep) + ext)
            if os.path.exists(p):
                text[u + ext] = read(p)
    app_js = os.path.join(MINI, 'app.js')
    if os.path.exists(app_js):
        text['app.js'] = read(app_js)
    all_wxml = '\n'.join(v for k, v in text.items() if k.endswith('.wxml'))

    page_reach, comp_reach = {}, {}
    for k, txt in text.items():
        if os.path.basename(k) in NOT_CALLER:
            continue
        d, self_route = os.path.dirname(k), k.rsplit('.', 1)[0]
        for m in LITERAL.finditer(txt):
            s = m.group(1).split('?')[0].strip()
            if not s or ' ' in s:
                continue
            cands = [s.lstrip('/')] if s.startswith('/') else \
                    [os.path.normpath(os.path.join(d, s)).replace('\\', '/'), s]
            for c in cands:
                if c in pageset and c != self_route and c not in dead_pages:
                    page_reach.setdefault(c, set()).add(k)
    for r in api_routes:
        if r in pageset:
            page_reach.setdefault(r, set()).add('SnowmeetApi')

    for tag, val in GLOBAL_UC.items():
        c = resolve_uc(val, '')
        if c in compset and re.search(r'<' + re.escape(tag) + r'[\s/>]', all_wxml):
            comp_reach.setdefault(c, set()).add('app.json(全局)')
    for u in live_units:
        j = text.get(u + '.json')
        if not j:
            continue
        try:
            uc = (json.loads(j).get('usingComponents') or {})
        except Exception:
            continue
        wx = text.get(u + '.wxml', '')
        for tag, val in uc.items():
            c = resolve_uc(val, os.path.dirname(u))
            if c in compset and re.search(r'<' + re.escape(tag) + r'[\s/>]', wx):
                comp_reach.setdefault(c, set()).add(u)

    nd_p = {p for p in pages if p not in dead_pages and p not in page_reach} - KEEP_PAGES
    nd_c = {c for c in comps if c not in dead_comps and c not in comp_reach}
    if not (nd_p - dead_pages) and not (nd_c - dead_comps):
        print('第 %d 轮：无新增孤儿，收敛' % rnd)
        break
    print('第 %d 轮新增  页面 %d / 组件 %d' % (rnd, len(nd_p), len(nd_c)))
    for x in sorted(nd_p):
        print('    [页] ' + x)
    for x in sorted(nd_c):
        print('    [组] ' + x)
    dead_pages |= nd_p
    dead_comps |= nd_c

print('\n' + '=' * 70)
print('注册页面 %d（主包 %d + 分包 %d） / 自定义组件 %d'
      % (len(pages), main_cnt, len(pages) - main_cnt, len(comps)))
print('孤儿页面 %d，孤儿组件 %d' % (len(dead_pages), len(dead_comps)))
print('\n[无代码入口但按 KEEP_PAGES 保留]')
for p in sorted(KEEP_PAGES):
    if p in pageset and p not in page_reach:
        print('  ' + p)
if dead_pages:
    print('\n[孤儿页面]')
    for p in sorted(dead_pages):
        print('  ' + p)
if dead_comps:
    print('\n[孤儿组件]')
    for c in sorted(dead_comps):
        print('  ' + c)
