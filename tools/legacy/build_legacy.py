"""生成小程序里的「旧版演示」分包 snowmeet_wechat_mini/legacy/。

旧版 = origin/master 最后一次提交（legacy_lib.OLD_REV），作为独立演示运行：接口和上传改连 mini.snowmeet.com，
登录态、全局资源与新版隔离。可以反复运行：会先删掉上次生成的 legacy/ 再重建，app.json 里的 legacy 分包配置也会原样替换。

对新版只做一处改动：在 app.json 的 subPackages 末尾插入 legacy 分包配置（纯插入，不重排其余内容）。
后台首页的入口（admin.wxml / admin.js 里带 legacy-demo 标记的两段）是手工加的，不由本脚本维护。
运行后用 check_legacy.py 检查。删除旧版的步骤见 check_legacy.py 的说明。
"""
import json
import posixpath
import re
import shutil
import sys

from legacy_lib import (ASSET_RE, DEMO_DOMAIN, LEGACY_ROOT, MINI_DIR, OLD_REV, Plan, TEXT_EXT, HERE, min_size, strip_json_comments, unit_of)

sys.stdout.reconfigure(encoding="utf-8")

MARK = "由 snowmeet_ai_doc/tools/legacy/build_legacy.py 生成"
# legacy_app.js 里旧版 globalData 引用的图片（旧版 app.js 不复制，其引用由这里补上）
EXTRA_ASSETS = ["images/icons/icon_maintain_white.jpg"]
# 注入「返回新版」条的页面
EXIT_BAR_PAGES = ["pages/admin/admin", "pages/index/index"]
EXIT_BAR = ('<!-- legacy-demo：旧版演示的返回条（build_legacy.py 注入） -->\n'
            '<view style="background:#fff3cd;color:#8a6d3b;padding:20rpx 24rpx;font-size:28rpx;text-align:center;" '
            'bindtap="__legacyExit">【演示】当前为旧版，点此返回新版</view>\n')
# 经 legacy_app.lwx 记账的全局资源 API
TRACKED_WX = ("openBluetoothAdapter", "startBluetoothDevicesDiscovery", "createBLEConnection",
              "onKeyboardHeightChange", "connectSocket")
API_HOSTS = r"(?:mini\.snowmeet\.top|snowmeet\.wanlonghuaxue\.com|xuexiaotupian\.wanlonghuaxue\.com)"

warnings = []


class Builder:
    def __init__(self, plan):
        self.P = plan
        self.old = plan.old
        self.copy = set(plan.copy_files)
        for a in EXTRA_ASSETS:
            if a in self.old.files:
                self.copy.add(a)
        self.stats = {"module": 0, "path": 0, "nav": 0, "host": 0, "getApp": 0, "Page": 0, "tracked": 0, "inject": 0}

    def new_path(self, old_path):
        return LEGACY_ROOT + "/" + old_path if old_path in self.copy else old_path

    def rewrite_spec(self, spec, src, kind):
        """把旧版文件 src 里的一个路径引用改成在 legacy/ 下仍然指向正确文件的写法；无需改动返回 None。"""
        if spec.startswith(("/" + LEGACY_ROOT + "/", "//", "http:", "https:", "wss:", "data:", "wxfile:")) or "{{" in spec:
            return None
        base, sep, query = re.match(r"([^?#]*)([?#]?)(.*)", spec, re.S).groups()
        if kind != "module" and base.startswith("/pages/"):
            self.stats["nav"] += 1
            return "/" + LEGACY_ROOT + spec
        if kind != "module" and not base.startswith(("/", "./", "../")):
            return None
        exts = {"module": ("", ".js", ".wxs"), "wxml": ("", ".wxml", ".wxs"), "wxss": ("", ".wxss"), "asset": ("",)}[kind]
        d = posixpath.dirname(src)
        target = self.P.O.resolve(d, base, exts)
        if not target:
            if kind == "module" or re.search(r"\." + ASSET_RE + "$", base):
                warnings.append("找不到引用目标：%s 里的 %s" % (src, spec))
            return None
        if target not in self.copy and target not in self.P.reuse_files and target not in self.P.new.files:
            warnings.append("引用目标既没复制也不在新版：%s 里的 %s → %s" % (src, spec, target))
            return None
        dest = self.new_path(target)
        if base.startswith("/"):
            norm = base[1:]
            out = "/" + dest
        else:
            # 相对路径和 npm 模块名都改成从 legacy/ 下的新位置出发的相对路径
            norm = posixpath.normpath(posixpath.join(d, base)) if base.startswith(".") else None
            out = posixpath.relpath(dest, posixpath.dirname(LEGACY_ROOT + "/" + src))
            if not out.startswith("."):
                out = "./" + out
        # 保持原来的写法：解析时补上的扩展名去掉（补上的 /index 保留，避免依赖目录解析）
        if norm is not None:
            appended = target[len(norm):] if target.startswith(norm) else ""
        else:
            k = target.rfind(base)
            appended = target[k + len(base):] if k >= 0 else ""
        if appended.startswith("/index"):
            appended = appended[len("/index"):]
        if appended and out.endswith(appended):
            out = out[: -len(appended)]
        new = out + sep + query
        if new == spec:
            return None
        self.stats["module" if kind == "module" else "path"] += 1
        return new

    # ---- 各类文件 ----
    def js(self, src, s):
        is_page = unit_of(src) in self.P.pageunits and src.endswith(".js")
        if src.endswith(".js"):
            s = self.code_rewrites(s, is_page)

        def repl(m):
            prefix, q, body = m.group(1) or "", m.group(2), m.group(3)
            kind = "module" if prefix else "asset"
            new = self.rewrite_spec(body, src, kind)
            return prefix + q + (new if new is not None else body) + q

        s = re.sub(r"""(require(?:\.async)?\s*\(\s*|\bfrom\s+|\bimport\s+)?(['"`])([^'"`\n]*)\2""", repl, s)
        s = self.hosts(s)
        if src.endswith(".js") and "__L" in s:
            rel = posixpath.relpath(LEGACY_ROOT + "/legacy_app.js", posixpath.dirname(LEGACY_ROOT + "/" + src))
            if not rel.startswith("."):
                rel = "./" + rel
            s = "var __L = require('%s') // legacy-demo：旧版演示的独立 App\n" % rel + s
        return s

    def code_rewrites(self, s, is_page):
        s, n = re.subn(r"\bgetApp\s*\(\s*\)", "__L", s)
        self.stats["getApp"] += n
        if is_page:
            s, n = re.subn(r"(?<![.\w$])Page\s*\(", "__L.Page(", s)
            self.stats["Page"] += n
            if n != 1:
                warnings.append("页面里 Page( 出现 %d 次" % n)
        s, n = re.subn(r"(?<![.\w$])wx\.(%s)\s*\(" % "|".join(TRACKED_WX), r"__L.lwx.\1(", s)
        self.stats["tracked"] += n
        s, n = re.subn(r"(?<![.\w$])(setInterval|setTimeout)\s*\(", r"__L.lwx.\1(", s)
        self.stats["tracked"] += n
        return s

    def hosts(self, s):
        s, n = re.subn(r"https://%s/(api|core)/" % API_HOSTS, r"https://%s/\1/" % DEMO_DOMAIN, s)
        self.stats["host"] += n
        return s

    def wxml(self, src, s):
        def repl(m):
            q, body = m.group(1), m.group(2)
            new = self.rewrite_spec(body, src, "wxml")
            return q + (new if new is not None else body) + q

        s = re.sub(r"""(['"])((?:\.{1,2}/|/)[^'"\n]*?)\1""", repl, s)
        s = self.hosts(s)
        if unit_of(src) in EXIT_BAR_PAGES:
            s = EXIT_BAR + s
        return s

    def wxss(self, src, s):
        def imp(m):
            new = self.rewrite_spec(m.group(3), src, "wxss")
            return m.group(1) + m.group(2) + (new if new is not None else m.group(3)) + m.group(2)

        s = re.sub(r"""(@import\s+)(['"])([^'"]+)\2""", imp, s)

        def url(m):
            new = self.rewrite_spec(m.group(2), src, "asset")
            return "url(" + m.group(1) + (new if new is not None else m.group(2)) + m.group(1) + ")"

        return re.sub(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", url, s)

    def json_(self, src, s):
        j = json.loads(strip_json_comments(s))
        uc = j.get("usingComponents")
        d = posixpath.dirname(src)
        if isinstance(uc, dict):
            for tag, v in list(uc.items()):
                uc[tag] = self.component_ref(d, v, src)
        # 旧版 app.json 的全局组件：本单元 wxml 用到、又没在本地声明的，补进本地 usingComponents
        wxml = unit_of(src) + ".wxml"
        if wxml in self.old.files:
            w = self.old.read(wxml)
            for tag, (v, _) in self.P.O.globals.items():
                if (uc is None or tag not in uc) and re.search(r"<" + re.escape(tag) + r"[\s/>]", w):
                    if uc is None:
                        uc = j["usingComponents"] = {}
                    uc[tag] = self.component_ref("", v, "app.json")
                    self.stats["inject"] += 1
        return json.dumps(j, ensure_ascii=False, indent=2) + "\n"

    def component_ref(self, d, v, src):
        if v.startswith("plugin://"):
            return v
        r = self.P.O.resolve(d, v, (".json",))
        if not r:
            if not v.startswith("weui-miniprogram/"):
                warnings.append("找不到组件：%s 里的 %s" % (src, v))
            return v
        unit = r[:-5]
        if r not in self.copy and r not in self.P.reuse_files:
            warnings.append("组件既没复制也不共用：%s 里的 %s" % (src, v))
        return "/" + (LEGACY_ROOT + "/" + unit if r in self.copy else unit)

    def transform(self, p):
        if not p.endswith(TEXT_EXT):
            return self.old.read_bytes(p)
        s = self.old.read(p)
        if p.endswith(".json"):
            out = self.json_(p, s)
        elif p.endswith((".js", ".wxs")):
            out = self.js(p, s)
        elif p.endswith(".wxml"):
            out = self.wxml(p, s)
        else:
            out = self.wxss(p, s)
        return out.encode("utf-8")


def insert_app_json(pages):
    """在 app.json 的 subPackages 末尾插入（或原样替换）legacy 分包配置，其余字节不动。"""
    path = MINI_DIR / "app.json"
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    raw = remove_app_json_block(raw)
    m = re.search(r'"subPackages"\s*:\s*\[', raw)
    if not m:
        raise SystemExit("app.json 里没有 subPackages")
    i, depth, in_str = m.end(), 1, False
    while depth:
        c = raw[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
    close = i - 1                       # subPackages 的 ]
    last = raw.rfind("}", 0, close) + 1    # 最后一个分包对象的 }
    block = (",%s    {%s      \"root\": \"%s\",%s      \"name\": \"%s\",%s      \"pages\": [%s"
             % (nl, nl, LEGACY_ROOT, nl, LEGACY_ROOT, nl, nl)) + \
        ("," + nl).join('        "%s"' % p for p in pages) + "%s      ]%s    }" % (nl, nl)
    new = raw[:last] + block + raw[last:]
    json.loads(new)
    path.write_bytes(new.encode("utf-8"))
    return block


def remove_app_json_block(raw):
    """去掉之前插入的 legacy 分包配置（插入时的原样文本）。"""
    m = re.search(r',\r?\n    \{\r?\n      "root": "%s",\r?\n      "name": "%s",\r?\n      "pages": \[.*?\]\r?\n    \}'
                  % (LEGACY_ROOT, LEGACY_ROOT), raw, flags=re.S)
    return raw[:m.start()] + raw[m.end():] if m else raw


def main():
    target = MINI_DIR / LEGACY_ROOT
    if target.exists():
        marker = target / "legacy_app.js"
        if not marker.exists() or MARK not in marker.read_text(encoding="utf-8"):
            raise SystemExit("%s 已存在且不是本脚本生成的，不覆盖" % target)
        shutil.rmtree(target)
    plan = Plan()
    b = Builder(plan)
    for p in sorted(b.copy):
        out = MINI_DIR / LEGACY_ROOT / p
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b.transform(p))
    tpl = (HERE / "legacy_app.template.js").read_text(encoding="utf-8")
    tpl = tpl.replace("__OLD_REV__", OLD_REV).replace("__DEMO_DOMAIN__", DEMO_DOMAIN)
    (target / "legacy_app.js").write_text(tpl, encoding="utf-8", newline="\n")
    pages = plan.legacy_pages()
    insert_app_json(pages)

    src_kb = sum(plan.old.files[p] for p in b.copy) / 1024
    min_kb = sum(min_size(plan.old, p) for p in b.copy) / 1024
    print("旧版 %s → %s/" % (OLD_REV, target))
    print("  页面 %d 个；复制单元 %d 个（其中页面 %d），文件 %d 个，源码 %.0f KB，估算压缩后 %.0f KB"
          % (len(pages), len(plan.copy_units), len(plan.copy_units & plan.pageunits), len(b.copy), src_kb, min_kb))
    print("  共用新版主包单元 %d 个（文件 %d 个）" % (len(plan.used_reuse_units), len(plan.reuse_files)))
    print("  改写：模块引用 %(module)d，路径 %(path)d，页面跳转 %(nav)d，接口域名 %(host)d，getApp %(getApp)d，Page %(Page)d，"
          "全局资源记账 %(tracked)d，注入旧版全局组件 %(inject)d" % b.stats)
    print("  app.json：已插入 legacy 分包（%d 个页面）" % len(pages))
    left = {}
    for f in (target).rglob("*"):
        if f.is_file() and f.suffix in (".js", ".wxml", ".wxss", ".json"):
            for h in re.findall(r"(?:https?|wss)://([\w.\-]+)", f.read_text(encoding="utf-8", errors="replace")):
                left[h] = left.get(h, 0) + 1
    print("  legacy/ 里剩余写死的域名：", sorted(left.items(), key=lambda x: -x[1]))
    print("  警告 %d 条" % len(warnings))
    for w in warnings:
        print("    -", w)


if __name__ == "__main__":
    main()
