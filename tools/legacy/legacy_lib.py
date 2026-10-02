"""旧版演示（legacy 分包）生成器与检查器共用的分析代码。

旧版 = snowmeet_wechat_mini 的 origin/master 最后一次提交（OLD_REV）；新版 = 小程序工作区（不含 legacy/ 和 app.json 里的 legacy 分包）。
按小程序的引用关系（app.json 页面 → json usingComponents → js require/import → wxml import/include/wxs/src → wxss @import/url → 图片路径）
从页面出发遍历，得出旧版实际会打进包的文件，再按「单元」（同名的 js/json/wxml/wxss/wxs 算一个组件或页面）判定：
- 共用：与新版字节相同、新版主包也在用、自身不连服务器（不读 getApp 的域名/登录态、不发请求、不写死 http 地址）、依赖也全部可共用；
- 复制：其余全部，连同旧版 112 个页面，复制进 legacy/。
"""
import collections
import json
import os
import posixpath
import re
import subprocess
from pathlib import Path

OLD_REV = "584b9466"            # origin/master 最后一次提交（2026-03-30 temp order search）
LEGACY_ROOT = "legacy"          # 分包根目录，同时是 app.json 里的分包 root/name
DEMO_DOMAIN = "mini.snowmeet.com"
HERE = Path(__file__).resolve().parent
MINI_DIR = HERE.parents[2] / "snowmeet_wechat_mini"   # 与 snowmeet_ai_doc 同级
TEXT_EXT = (".js", ".json", ".wxml", ".wxss", ".wxs")
UNIT_EXT = (".js", ".json", ".wxml", ".wxss", ".wxs")
ASSET_RE = r"(?:png|jpe?g|gif|svg|webp|ttf|woff2?|mp3|mp4|wav)"
# 新版精简过的打印码表（518 KB → 146 KB，保留打印用的 gb18030），旧版直接用新的
ALLOW_NEW = {"utils/ble_label_printer/encoding-indexes"}
# 工作区里不属于小程序代码包的目录
WORKTREE_SKIP = {".git", "node_modules", "tests", LEGACY_ROOT, ".claude"}


def git(*args, cwd=MINI_DIR):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("git %s 失败：%s" % (" ".join(args), r.stderr.decode("utf-8", "replace")))
    return r.stdout


class GitTree:
    """某个提交里的文件。"""

    def __init__(self, rev):
        self.rev = rev
        self.files = {}
        for line in git("ls-tree", "-r", "-l", rev).decode("utf-8", "replace").splitlines():
            meta, path = line.split("\t", 1)
            parts = meta.split()
            self.files[path] = int(parts[3]) if parts[3] != "-" else 0
        self._cache = {}

    def read_bytes(self, p):
        if p not in self._cache:
            self._cache[p] = git("show", "%s:%s" % (self.rev, p))
        return self._cache[p]

    def read(self, p):
        return self.read_bytes(p).decode("utf-8", "replace").replace("\r\n", "\n")


class WorkTree:
    """小程序工作区（新版），跳过 legacy/ 等不属于新版代码包的目录。node_modules 只收被直接引用的 linq。"""

    def __init__(self, root=MINI_DIR):
        self.root = Path(root)
        self.files = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            rel = Path(dirpath).relative_to(self.root).as_posix()
            if rel == ".":
                dirnames[:] = [d for d in dirnames if d not in WORKTREE_SKIP]
                rel = ""
            for f in filenames:
                p = (rel + "/" + f) if rel else f
                self.files[p] = (Path(dirpath) / f).stat().st_size
        linq = "node_modules/linq/linq.min.js"
        if (self.root / linq).exists():
            self.files[linq] = (self.root / linq).stat().st_size

    def read_bytes(self, p):
        return (self.root / p).read_bytes()

    def read(self, p):
        return self.read_bytes(p).decode("utf-8", "replace").replace("\r\n", "\n")


def strip_json_comments(s):
    return re.sub(r"(?m)^\s*//.*$", "", s)


def load_app_json(tree, drop_legacy=True):
    app = json.loads(strip_json_comments(tree.read("app.json")))
    if drop_legacy:
        key = "subPackages" if "subPackages" in app else "subpackages"
        app[key] = [s for s in app.get(key, []) if s.get("root", "").rstrip("/") != LEGACY_ROOT]
    return app


def subpackages(app):
    return app.get("subPackages") or app.get("subpackages") or []


def unit_of(p):
    """同名的 js/json/wxml/wxss/wxs 归为一个单元；根目录的 app.* 各自单独算（app.wxss 可以共用，app.js 不行）。"""
    if "/" not in p and p.startswith("app."):
        return p
    for e in UNIT_EXT:
        if p.endswith(e):
            return p[: -len(e)]
    return p


class Walk:
    """从 app.json 的页面出发，按引用关系遍历一棵树。"""

    def __init__(self, tree, app):
        self.tree, self.app = tree, app
        self.roots = [s["root"].rstrip("/") for s in subpackages(app)]
        self.edges = collections.defaultdict(set)
        self.seen = set()
        self.pages = list(app["pages"]) + [s["root"].rstrip("/") + "/" + pg for s in subpackages(app) for pg in s["pages"]]
        self.globals = {}
        for tag, v in (app.get("usingComponents") or {}).items():
            r = self.resolve("", v, (".json",))
            self.globals[tag] = (v, r[:-5] if r else None)
        for p in ("app.js", "app.json", "app.wxss", app.get("sitemapLocation", "sitemap.json")):
            if p in tree.files:
                self.add(p)
        self.pagefiles = set()
        self.pageunits = {}
        for pg in self.pages:
            fs = self.unit_files(pg)
            self.pageunits[pg] = fs
            for f in fs:
                self.pagefiles.add(f)
                self.add(f)

    def exists(self, p):
        return p in self.tree.files

    def unit_files(self, base):
        return [base + e for e in UNIT_EXT if self.exists(base + e)]

    def resolve(self, d, spec, exts):
        """返回引用指向的真实文件路径（相对小程序根），找不到返回 None。"""
        spec = spec.split("?")[0].split("#")[0]
        if not spec:
            return None
        if spec.startswith("/"):
            cands = [spec[1:]]
        elif spec.startswith("."):
            cands = [posixpath.normpath(posixpath.join(d, spec))]
        else:
            cands = [posixpath.normpath(posixpath.join(d, spec)), spec, "miniprogram_npm/" + spec]
        for c in cands:
            for e in exts:
                for cc in (c + e, c + "/index" + e):
                    if self.exists(cc):
                        return cc
        return None

    def add(self, p, frm=None):
        if frm:
            self.edges[frm].add(p)
        if p in self.seen:
            return
        self.seen.add(p)
        d = posixpath.dirname(p)
        s = self.tree.read(p) if p.endswith(TEXT_EXT) else ""
        if p.endswith(".json"):
            try:
                j = json.loads(strip_json_comments(s))
            except ValueError:
                j = {}
            for v in (j.get("usingComponents") or {}).values():
                if v.startswith("plugin://"):
                    continue
                r = self.resolve(d, v, (".json",))
                if r:
                    for f in self.unit_files(r[:-5]):
                        self.add(f, p)
        if p.endswith((".js", ".wxs")):
            for spec in module_specs(s):
                r = self.resolve(d, spec, ("", ".js", ".wxs"))
                if r:
                    self.add(r, p)
        if p.endswith(".wxml"):
            for spec in re.findall(r"""<(?:import|include|wxs)\b[^>]*\bsrc\s*=\s*['"]([^'"{}]+)['"]""", s):
                r = self.resolve(d, spec, ("", ".wxml", ".wxs"))
                if r:
                    self.add(r, p)
        if p.endswith(".wxss"):
            for spec in re.findall(r"""@import\s+['"]([^'"]+)['"]""", s):
                r = self.resolve(d, spec, ("", ".wxss"))
                if r:
                    self.add(r, p)
        if p.endswith((".js", ".wxml", ".wxss", ".wxs")):
            for spec in re.findall(r"""['"(]\s*((?:\.{1,2}/|/)?[\w\-./]+\.""" + ASSET_RE + r""")\s*['")]""", s):
                c = spec[1:] if spec.startswith("/") else posixpath.normpath(posixpath.join(d, spec))
                if self.exists(c):
                    self.add(c, p)

    def pkg(self, p):
        for r in self.roots:
            if p.startswith(r + "/"):
                return r
        return "(main)"


def module_specs(s):
    return re.findall(r"""require(?:\.async)?\s*\(\s*['"]([^'"]+)['"]\s*\)""", s) + \
        re.findall(r"""(?:^|[;\s])import\s+(?:[^'";]+?\s+from\s+)?['"]([^'"]+)['"]""", s)


def strip_js_comments(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", s)


def domain_dep(tree, p):
    """会不会读新版全局 app 的域名/登录态、发请求或写死 http 地址——会的就不能共用（共用的话会连到新服务器）。"""
    if not p.endswith((".js", ".wxs")):
        return None
    s = strip_js_comments(tree.read(p))
    if re.search(r"\bapp\.(globalData|loginPromise|getDomain|setDomain)|getApp\s*\(\s*\)\s*\.", s):
        return "getApp"
    if re.search(r"wx\.(request|uploadFile|downloadFile|connectSocket)\b", s):
        return "network"
    if re.search(r"https?://", s):
        return "url"
    return None


def min_size(tree, p):
    """去掉注释和多余空白后的大小，近似开发者工具压缩后的体积。"""
    if not p.endswith(TEXT_EXT):
        return tree.files[p]
    s = tree.read(p)
    if p.endswith((".js", ".wxs")):
        s = strip_js_comments(s)
    elif p.endswith(".wxss"):
        s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    elif p.endswith(".wxml"):
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return len(re.sub(r"\s+", " ", s).encode("utf-8"))


class Plan:
    """算出旧版哪些单元复制进 legacy/、哪些直接用新版主包里的。"""

    def __init__(self, new_tree=None):
        self.old = GitTree(OLD_REV)
        self.new = new_tree or WorkTree()
        self.O = Walk(self.old, load_app_json(self.old, drop_legacy=False))
        self.N = Walk(self.new, load_app_json(self.new))
        O, N = self.O, self.N
        self.units = collections.defaultdict(set)
        for p in O.seen:
            self.units[unit_of(p)].add(p)
        self.uedges = collections.defaultdict(set)
        for p in O.seen:
            for q in O.edges.get(p, ()):
                if unit_of(q) != unit_of(p):
                    self.uedges[unit_of(p)].add(unit_of(q))
        self.pageunits = set(O.pageunits)

        def same(f):
            return f in N.seen and N.pkg(f) == "(main)" and f in self.new.files and \
                self.new.read_bytes(f).replace(b"\r\n", b"\n") == self.old.read_bytes(f).replace(b"\r\n", b"\n")

        self.why = {}
        reuse = set()
        for u, fs in self.units.items():
            if u in self.pageunits or u in ("app.js", "app.json", "sitemap"):
                continue
            if u in ALLOW_NEW:
                reuse.add(u)
                continue
            if not all(same(f) for f in fs):
                self.why[u] = "新版已修改/删除/不再使用"
                continue
            dep = next((domain_dep(self.old, f) for f in fs if domain_dep(self.old, f)), None)
            if dep:
                self.why[u] = "会连服务器（%s）" % dep
                continue
            reuse.add(u)
        changed = True
        while changed:
            changed = False
            for u in list(reuse):
                if u in ALLOW_NEW:
                    continue
                bad = [v for v in self.uedges.get(u, ()) if v not in reuse]
                if bad:
                    reuse.discard(u)
                    self.why[u] = "依赖了要复制的 %s" % bad[0]
                    changed = True
        # 从旧版页面出发，遇到可共用的单元就停（它在主包里）
        copy = set()
        stack = list(self.pageunits)
        while stack:
            u = stack.pop()
            if u in copy or u in reuse:
                continue
            copy.add(u)
            stack += list(self.uedges.get(u, ()))
        # 旧版 app.json 的全局组件：按旧版 wxml 实际用到的标签补进来
        self.tags_used = collections.Counter()
        for u in list(copy):
            for f in self.units[u]:
                if f.endswith(".wxml"):
                    s = self.old.read(f)
                    for tag in O.globals:
                        if re.search(r"<" + re.escape(tag) + r"[\s/>]", s):
                            self.tags_used[tag] += 1
        stack = [O.globals[t][1] for t in self.tags_used if O.globals[t][1]]
        while stack:
            u = stack.pop()
            if u in copy or u in reuse:
                continue
            copy.add(u)
            stack += list(self.uedges.get(u, ()))
        copy -= {"app.js", "app.json", "sitemap"}
        self.copy_units = copy
        self.reuse_units = reuse
        self.copy_files = {f for u in copy for f in self.units[u]}
        used = set()
        stack = [v for u in copy for v in self.uedges.get(u, ()) if v in reuse] + \
            [O.globals[t][1] for t in self.tags_used if O.globals[t][1] in reuse]
        while stack:
            u = stack.pop()
            if u in used:
                continue
            used.add(u)
            stack += [v for v in self.uedges.get(u, ()) if v in reuse]
        self.used_reuse_units = used
        self.reuse_files = {f for u in used for f in self.units[u]}

    def legacy_pages(self):
        """旧版全部页面，路径相对 legacy 分包根。"""
        return list(self.O.pages)
