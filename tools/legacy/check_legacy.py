"""检查小程序里的「旧版演示」分包（只读，不改任何文件）。

    py check_legacy.py            # 生成或修改后检查
    py check_legacy.py --removed  # 删除旧版后检查

默认模式检查三类问题，有任何一条不通过就以退出码 1 结束：
1. 新版零改动：legacy/ 以外只允许 app.json 插入的 legacy 分包配置、admin.wxml / admin.js 里
   「legacy-demo begin … legacy-demo end」之间的插入；把这些插入去掉后，三个文件与 HEAD 逐字节相同（不比较换行符）。
2. 隔离：legacy/ 里的引用都能找到目标，目标只在 legacy/ 或主包（不在新版其他分包）；跳转都指向 legacy 页面；
   没有 getApp()、裸 Page()、写 storage、写文件、给 wx.* 赋值、未经记账的全局资源调用；没有遗漏的接口旧域名。
3. 共用的主包单元都仍被新版使用（删除旧版后不会留下没人用的文件）；输出各包的估算体积。

删除旧版：
1. 删除 snowmeet_wechat_mini/legacy/；
2. 删掉 app.json 里 root 为 legacy 的分包配置（就是生成器插入的那一块）；
3. 删掉 pages/admin/admin.wxml、pages/admin/admin.js 里 legacy-demo begin/end 之间的内容（含这两行）；
4. 运行 py check_legacy.py --removed。
"""
import json
import os
import posixpath
import re
import sys
from pathlib import Path

from legacy_lib import (LEGACY_ROOT, MINI_DIR, GitTree, Plan, Walk, WorkTree, git, load_app_json, min_size, subpackages)
from build_legacy import TRACKED_WX, remove_app_json_block

sys.stdout.reconfigure(encoding="utf-8")

ENTRY_FILES = ["pages/admin/admin.wxml", "pages/admin/admin.js"]
errors = []


def err(msg):
    errors.append(msg)


def norm(s):
    return s.replace("\r\n", "\n")


def strip_markers(s):
    """去掉 legacy-demo begin … end 之间的插入（含这两行）。"""
    return re.sub(r"[^\n]*legacy-demo begin[^\n]*\n.*?[^\n]*legacy-demo end[^\n]*\n", "", s, flags=re.S)


def head_text(p):
    try:
        return norm(git("show", "HEAD:" + p).decode("utf-8"))
    except RuntimeError:
        return None


def check_zero_change(removed):
    status = git("status", "--porcelain", "--untracked-files=all").decode("utf-8").splitlines()
    allowed = {"app.json"} | set(ENTRY_FILES)
    for line in status:
        path = line[3:].strip().strip('"')
        if path.startswith(LEGACY_ROOT + "/"):
            if removed:
                err("删除后仍有 legacy 文件：%s" % path)
            continue
        if path not in allowed:
            err("legacy/ 以外有其他改动：%s（%s）" % (path, line[:2]))
    work = norm((MINI_DIR / "app.json").read_text(encoding="utf-8"))
    base = head_text("app.json")
    has_block = remove_app_json_block(work) != work
    if removed and has_block:
        err("app.json 里还有 legacy 分包配置")
    if not removed and not has_block:
        err("app.json 里没有 legacy 分包配置")
    if remove_app_json_block(work) != remove_app_json_block(base):
        err("app.json 去掉 legacy 分包配置后与 HEAD 不同（有插入以外的改动）")
    for p in ENTRY_FILES:
        work = norm((MINI_DIR / p).read_text(encoding="utf-8"))
        base = head_text(p)
        if removed and "legacy-demo" in work:
            err("%s 里还有 legacy-demo 插入" % p)
        if not removed and "legacy-demo begin" not in work:
            err("%s 里没有 legacy-demo 入口" % p)
        if strip_markers(work) != strip_markers(base):
            err("%s 去掉 legacy-demo 插入后与 HEAD 不同（有插入以外的改动）" % p)
    # legacy/ 以外不允许再有别处引用 legacy
    for dirpath, dirnames, filenames in os.walk(MINI_DIR):
        rel = Path(dirpath).relative_to(MINI_DIR).as_posix()
        if rel == ".":
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", LEGACY_ROOT, "miniprogram_npm")]
        for f in filenames:
            p = f if rel == "." else rel + "/" + f
            if not p.endswith((".js", ".json", ".wxml", ".wxss", ".wxs")) or p in ("project.config.json", "project.private.config.json"):
                continue
            s = (Path(dirpath) / f).read_text(encoding="utf-8", errors="replace")
            if p == "app.json":
                s = remove_app_json_block(norm(s))
            elif p in ENTRY_FILES:
                s = strip_markers(norm(s))
            if re.search(r"""['"/]%s/""" % LEGACY_ROOT, s):
                err("新版文件引用了 legacy：%s" % p)


class Files:
    def __init__(self):
        self.all = set()
        for dirpath, dirnames, filenames in os.walk(MINI_DIR):
            rel = Path(dirpath).relative_to(MINI_DIR).as_posix()
            if rel == ".":
                dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
                rel = ""
            for f in filenames:
                self.all.add((rel + "/" + f) if rel else f)
        self.all.add("node_modules/linq/linq.min.js")

    def resolve(self, d, spec, exts):
        spec = spec.split("?")[0].split("#")[0]
        if spec.startswith("/"):
            cands = [spec[1:]]
        elif spec.startswith("."):
            cands = [posixpath.normpath(posixpath.join(d, spec))]
        else:
            cands = [posixpath.normpath(posixpath.join(d, spec)), spec, "miniprogram_npm/" + spec]
        for c in cands:
            for e in exts:
                for cc in (c + e, c + "/index" + e):
                    if cc in self.all:
                        return cc
        return None


def check_isolation():
    legacy = MINI_DIR / LEGACY_ROOT
    if not legacy.exists():
        err("没有 legacy/ 目录")
        return
    app = load_app_json(WorkTree(), drop_legacy=False)
    sub = next((s for s in subpackages(app) if s["root"].rstrip("/") == LEGACY_ROOT), None)
    if not sub:
        err("app.json 里没有 legacy 分包")
        return
    pages = set(LEGACY_ROOT + "/" + p for p in sub["pages"])
    banner = "legacy-demo：旧版演示的返回条（build_legacy.py 注入）"
    page_wxml = {pg + ".wxml" for pg in pages}
    for wxml in page_wxml:
        path = legacy / wxml[len(LEGACY_ROOT) + 1:]
        if not path.is_file() or path.read_text(encoding="utf-8", errors="replace").count(banner) != 1:
            err("旧版页面缺少唯一的返回新版提示：%s" % wxml)
    for path in legacy.rglob("*.wxml"):
        rel = path.relative_to(MINI_DIR).as_posix()
        if rel not in page_wxml and banner in path.read_text(encoding="utf-8", errors="replace"):
            err("返回新版提示不应注入非页面 WXML：%s" % rel)
    other_roots = [s["root"].rstrip("/") for s in subpackages(app) if s["root"].rstrip("/") != LEGACY_ROOT]
    F = Files()
    for pg in pages:
        for e in (".js", ".wxml"):     # 页面的 json、wxss 可以没有
            if pg + e not in F.all:
                err("legacy 页面缺文件：%s%s" % (pg, e))
    unregistered = []

    def target_ok(src, spec, t):
        if t is None:
            return
        if not t.startswith(LEGACY_ROOT + "/") and any(t.startswith(r + "/") for r in other_roots):
            err("%s 引用了新版其他分包里的文件：%s" % (src, spec))

    forbidden = [
        (r"\bgetApp\s*\(", "getApp()"),
        (r"(?<![.\w$])Page\s*\(", "未包装的 Page()"),
        (r"wx\.(set|remove|clear)Storage", "写 storage"),
        (r"\.(writeFile|appendFile|unlink|rmdir|mkdir|rename|copyFile|saveFile)(Sync)?\s*\(", "写文件"),
        (r"(?<![.\w$])wx\.[A-Za-z_$]+\s*=(?!=)", "给 wx.* 赋值"),
        (r"(?<![.\w$])wx\.(%s)\s*\(" % "|".join(TRACKED_WX), "未经记账的全局资源调用"),
        (r"(?<![.\w$])(setInterval|setTimeout)\s*\(", "未经记账的定时器"),
        (r"https://(mini\.snowmeet\.top|snowmeet\.wanlonghuaxue\.com|xuexiaotupian\.wanlonghuaxue\.com)/(api|core)/", "接口旧域名"),
    ]
    for f in sorted(legacy.rglob("*")):
        if not f.is_file():
            continue
        p = f.relative_to(MINI_DIR).as_posix()
        d = posixpath.dirname(p)
        if not p.endswith((".js", ".json", ".wxml", ".wxss", ".wxs")):
            continue
        s = f.read_text(encoding="utf-8", errors="replace")
        if p.endswith(".js") and p != LEGACY_ROOT + "/legacy_app.js":
            code = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
            code = re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", code)
            for rx, what in forbidden:
                m = re.search(rx, code)
                if m:
                    err("%s：%s（%s）" % (p, what, m.group(0)))
        if p.endswith((".js", ".wxs")):
            for spec in re.findall(r"""require(?:\.async)?\s*\(\s*['"]([^'"]+)['"]\s*\)""", s) + \
                    re.findall(r"""(?:^|[;\s])import\s+(?:[^'";]+?\s+from\s+)?['"]([^'"]+)['"]""", s):
                t = F.resolve(d, spec, ("", ".js", ".wxs"))
                if t is None:
                    err("%s：找不到模块 %s" % (p, spec))
                target_ok(p, spec, t)
        if p.endswith(".json"):
            j = json.loads(s)
            for tag, v in (j.get("usingComponents") or {}).items():
                if v.startswith(("plugin://", "weui-miniprogram/")):
                    continue
                t = F.resolve(d, v, (".json",))
                if t is None:
                    err("%s：找不到组件 %s" % (p, v))
                target_ok(p, v, t)
        if p.endswith(".wxml"):
            for spec in re.findall(r"""<(?:import|include|wxs)\b[^>]*\bsrc\s*=\s*['"]([^'"{}]+)['"]""", s):
                t = F.resolve(d, spec, ("", ".wxml", ".wxs"))
                if t is None:
                    err("%s：找不到 %s" % (p, spec))
                target_ok(p, spec, t)
        if p.endswith(".wxss"):
            for spec in re.findall(r"""@import\s+['"]([^'"]+)['"]""", s):
                t = F.resolve(d, spec, ("", ".wxss"))
                if t is None:
                    err("%s：找不到样式 %s" % (p, spec))
                target_ok(p, spec, t)
        if p.endswith((".js", ".wxml")):
            # legacy_app.js 的「返回新版」和非管理员拦截是有意跳回新版的
            if p != LEGACY_ROOT + "/legacy_app.js" and re.search(r"""['"`]/pages/""", s):
                err("%s：还有跳转到新版页面的 /pages/ 路径" % p)
            for m in re.finditer(r"""['"`](/%s/pages/[\w\-/]+)""" % LEGACY_ROOT, s):
                path = m.group(1)[1:]
                if not path.endswith("/") and path not in pages:
                    unregistered.append("%s → %s" % (p, path))
            for m in re.finditer(r"""['"(]\s*((?:\.{1,2}/|/)[\w\-./]+\.(?:png|jpe?g|gif|svg|webp))\s*['")]""", s):
                spec = m.group(1)
                t = F.resolve(d, spec, ("",))
                target_ok(p, spec, t)
    if unregistered:
        # 旧版 app.json 里本来就没注册这些页面（菜单指向已删页面），点了会报页面不存在，与旧版一致
        print("  提示：%d 处跳转指向旧版本来就没注册的页面，例如 %s" % (len(unregistered), unregistered[0]))


def check_reuse_and_size():
    plan = Plan()
    N = plan.N
    orphan = [u for u in plan.used_reuse_units if not any(f in N.seen for f in plan.units[u])]
    for u in orphan:
        err("共用单元 %s 已不被新版使用，删除旧版后会变成没人用的文件" % u)
    work = plan.new
    main_now = sum(min_size(work, p) for p in N.seen if N.pkg(p) == "(main)")
    head = GitTree("HEAD")
    H = Walk(head, load_app_json(head))
    main_head = sum(min_size(head, p) for p in H.seen if H.pkg(p) == "(main)")
    legacy_files = [f for f in (MINI_DIR / LEGACY_ROOT).rglob("*") if f.is_file()]
    legacy_src = sum(f.stat().st_size for f in legacy_files)
    lt = WorkTree()
    legacy_min = 0
    for f in legacy_files:
        p = f.relative_to(MINI_DIR).as_posix()
        lt.files[p] = f.stat().st_size
        legacy_min += min_size(lt, p)
    print("体积（估算压缩后，以开发者工具「本地代码」为准）：")
    print("  主包：HEAD %.0f KB → 现在 %.0f KB（%+.1f KB）" % (main_head / 1024, main_now / 1024, (main_now - main_head) / 1024))
    print("  legacy 分包：%d 个文件，源码 %.0f KB，估算 %.0f KB" % (len(legacy_files), legacy_src / 1024, legacy_min / 1024))
    print("  共用主包单元：%d 个，全部仍被新版使用" % len(plan.used_reuse_units) if not orphan else "")
    if legacy_min > 1.8 * 1024 * 1024:
        err("legacy 分包估算超过 1.8 MB，接近 2M 上限")


def main():
    removed = "--removed" in sys.argv
    print("检查 %s（%s）" % (MINI_DIR, "删除后" if removed else "生成后"))
    check_zero_change(removed)
    if removed:
        if (MINI_DIR / LEGACY_ROOT).exists():
            err("legacy/ 目录还在")
    else:
        check_isolation()
        check_reuse_and_size()
    if errors:
        print("不通过（%d 条）：" % len(errors))
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
