"""Clear only the user's food test data. Default: preview. No implicit connection.

Python 3.10+; pyodbc for SQL Server; boto3 only for actual S3 file deletion.
Never imports application startup or reads config.sqlServer.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit, unquote

FOOD_TABLES = frozenset("""fnb_unit fnb_material_category fnb_material_item
fnb_material_batch fnb_material_batch_stock fnb_material_alert_log fnb_shelf_life_rule
fnb_dish_spec fnb_recipe fnb_recipe_line fnb_channel_shop fnb_channel_dish_map
fnb_order fnb_order_line fnb_order_import fnb_stock_document fnb_stock_document_line
fnb_stock_movement fnb_stocktake_line
fnb_v4_category fnb_v4_item fnb_v4_item_form fnb_v4_purchase_spec fnb_v4_shelf_life_rule
fnb_v4_batch fnb_v4_batch_image fnb_v4_stock_operation fnb_v4_dish_spec fnb_v4_recipe
fnb_v4_recipe_line fnb_v4_order fnb_v4_order_line fnb_v4_order_import fnb_v4_stock_document
fnb_v4_stock_document_line fnb_v4_stock_movement fnb_v4_stocktake_line""".split())
SHARED_TARGETS = frozenset("""category category_property category_property_option product
product_image product_property product_stock fd_order order order_payment payment_refund
order_payment_share payment_share order_share discount retail retail_image
order_online order_online_detail order_online_temp wepay_order mini_upload""".split())
ALLOWED = FOOD_TABLES | SHARED_TARGETS
PROTECTED = frozenset("""staff staff_social_account staff_bind_code social_account_for_job
member member_social_account mini_session shop_list wepay_key alipay_mch_id
order_share_relation share_relation_bind""".split())
BUCKET = "snowmeet-uploads-673751646617-cn-northwest-1-an"
REGION = "cn-northwest-1"
PUBLIC_HOSTS = frozenset(("img.snowmeet.top", "mini.snowmeet.top"))
LIFECYCLE_PATH = Path(__file__).resolve().parent.parent / "lifecycle.json"


def lifecycle():
    try:
        state = json.loads(LIFECYCLE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("Skill lifecycle missing or invalid; cleanup disabled") from error
    if not isinstance(state, dict) or state.get("version") != 1 or state.get("status") not in ("testing", "retired"):
        raise ValueError("Skill lifecycle invalid; cleanup disabled")
    return state


def require_testing():
    if lifecycle()["status"] != "testing":
        raise ValueError("Skill retired after formal launch; cleanup disabled")


def retire_skill():
    state = lifecycle()
    if state["status"] == "testing":
        state.update(status="retired", retired_at=datetime.now(timezone.utc).isoformat(),
                     reason="食材管理系统正式上线，测试数据清理 skill 永久作废")
        save_manifest(LIFECYCLE_PATH, state)
    return state


def quote(name):
    return "[" + name.replace("]", "]]") + "]"


@dataclass
class Table:
    schema: str
    name: str
    oid: int
    columns: set[str]
    keys: list[str]

    @property
    def sql(self):
        return quote(self.schema) + "." + quote(self.name)

    @property
    def temp(self):
        return "#food_clear_" + str(self.oid)


@dataclass
class Link:
    child: int
    parent: int
    pairs: list[tuple[str, str]]


def catalog(cur):
    tables = {}
    for schema, name, oid in cur.execute("SELECT s.name,t.name,t.object_id FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE t.is_ms_shipped=0"):
        tables[oid] = Table(schema, name, oid, set(), [])
    for oid, column in cur.execute("SELECT object_id,name FROM sys.columns"):
        if oid in tables:
            tables[oid].columns.add(column)
    for oid, column in cur.execute("SELECT i.object_id,c.name FROM sys.indexes i JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id WHERE i.is_primary_key=1 ORDER BY i.object_id,ic.key_ordinal"):
        if oid in tables:
            tables[oid].keys.append(column)
    links = {}
    for fk, child, parent, c, p in cur.execute("SELECT fk.object_id,fk.parent_object_id,fk.referenced_object_id,cc.name,pc.name FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fc ON fc.constraint_object_id=fk.object_id JOIN sys.columns cc ON cc.object_id=fc.parent_object_id AND cc.column_id=fc.parent_column_id JOIN sys.columns pc ON pc.object_id=fc.referenced_object_id AND pc.column_id=fc.referenced_column_id ORDER BY fk.object_id,fc.constraint_column_id"):
        links.setdefault(fk, Link(child, parent, [])).pairs.append((c, p))
    return tables, list(links.values())


def key_join(table, left, right):
    return " AND ".join(f"{left}.{quote(k)}={right}.{quote(k)}" for k in table.keys)


class Scope:
    def __init__(self, cur):
        self.cur = cur
        self.tables, self.links = catalog(cur)
        self.names = {t.name: t for t in self.tables.values() if t.schema == "dbo"}
        unknown = sorted(t.name for t in self.tables.values() if t.name.startswith("fnb_") and (t.schema != "dbo" or t.name not in FOOD_TABLES))
        if unknown:
            raise ValueError("Unreviewed food tables: " + ", ".join(unknown))
        for name in ("staff", "product", "category", "order", "mini_upload", "fnb_unit"):
            if name not in self.names:
                raise ValueError("Missing shared table: " + name)
        self.targets = {t.oid: t for t in self.names.values() if t.name in ALLOWED}
        for t in self.targets.values():
            if not t.keys:
                raise ValueError("No primary key: " + t.name)
            # UNION prevents SELECT INTO from inheriting an identity column.
            cols = ",".join(map(quote, t.keys))
            cur.execute(f"SELECT TOP (0) {cols} INTO {t.temp} FROM {t.sql} UNION ALL SELECT TOP (0) {cols} FROM {t.sql}")
            cur.execute(f"CREATE UNIQUE CLUSTERED INDEX ix_scope ON {t.temp} ({','.join(map(quote,t.keys))})")

    def add(self, name, where="1=1", params=()):
        if name not in self.names or self.names[name].oid not in self.targets:
            return 0
        t = self.names[name]
        cols = ",".join("a." + quote(k) for k in t.keys)
        self.cur.execute(f"INSERT INTO {t.temp} ({','.join(map(quote,t.keys))}) SELECT {cols} FROM {t.sql} a WHERE ({where}) AND NOT EXISTS (SELECT 1 FROM {t.temp} b WHERE {key_join(t,'a','b')})", *params)
        return self.cur.execute("SELECT @@ROWCOUNT").fetchval()

    def selected(self, name, alias="p"):
        t = self.names[name]
        return f"{t.sql} {alias} JOIN {t.temp} s ON {key_join(t,alias,'s')}"

    def seed(self):
        for name in sorted(FOOD_TABLES):
            self.add(name)
        self.add("category", "LTRIM(RTRIM(a.biz_type))=?", ("餐饮",))
        self.add("product", f"LTRIM(RTRIM(a.type))=? OR EXISTS (SELECT 1 FROM {self.selected('category')} WHERE p.id=a.category_id)", ("餐饮",))
        for name in ("fnb_dish_spec", "fnb_v4_dish_spec"):
            if name in self.names:
                for col in ("product_id", "legacy_product_id"):
                    if col in self.names[name].columns:
                        self.add("product", f"a.id IN (SELECT {quote(col)} FROM {self.names[name].sql})")
        self.add("order", "LTRIM(RTRIM(a.type))=?", ("餐饮",))
        for name in ("fnb_order", "fnb_v4_order"):
            if name in self.names and "sales_order_id" in self.names[name].columns:
                self.add("order", f"a.id IN (SELECT sales_order_id FROM {self.names[name].sql})")
        if "fd_order" in self.names:
            self.add("order", f"a.id IN (SELECT d.order_id FROM dbo.fd_order d JOIN {self.names['product'].temp} p ON p.id=d.product_id)")
        if "order_online" in self.names and "type" in self.names["order_online"].columns:
            self.add("order_online", "LTRIM(RTRIM(a.type))=?", ("餐饮",))
            if "order_online_detail" in self.names:
                self.add("order_online", f"a.id IN (SELECT d.order_online_id FROM dbo.order_online_detail d JOIN {self.names['product'].temp} p ON p.id=d.product_id)")
        self.add("mini_upload", "a.purpose LIKE ? OR a.purpose LIKE ? OR a.purpose LIKE ?", ("食材%", "餐饮%", "fnb%"))
        for name, col in (("fnb_material_item", "image_id"), ("fnb_v4_item", "image_id"), ("fnb_order_import", "upload_id"), ("fnb_v4_batch_image", "upload_id")):
            if name in self.names and col in self.names[name].columns:
                self.add("mini_upload", f"a.id IN (SELECT {quote(col)} FROM {self.names[name].sql})")
        if "fnb_material_batch" in self.names and "image_ids" in self.names["fnb_material_batch"].columns:
            ids = set()
            for row in self.cur.execute("SELECT image_ids FROM dbo.fnb_material_batch WHERE image_ids IS NOT NULL"):
                for value in row[0].split(","):
                    if value.strip():
                        if not re.fullmatch(r"\d+", value.strip()):
                            raise ValueError("Malformed legacy image_ids")
                        ids.add(int(value))
            for value in ids:
                self.add("mini_upload", "a.id=?", (value,))

    def propagate(self):
        # Add missing conventions as well: several old tables have no physical FK.
        links = list(self.links)
        seen = {(l.child, l.parent, tuple(l.pairs)) for l in links}
        conventions = {"product_id": "product", "category_id": "category", "category_property_id": "category_property",
                       "order_id": "order", "order_online_id": "order_online", "online_order_id": "order_online",
                       "upload_id": "mini_upload", "payment_id": "order_payment", "order_payment_id": "order_payment"}
        for t in self.targets.values():
            if t.name in FOOD_TABLES or t.name in ("order", "product", "category", "mini_upload"):
                continue
            for col, parent in conventions.items():
                if col in t.columns and parent in self.names:
                    p = self.names[parent]
                    token = (t.oid, p.oid, ((col, "id"),))
                    if token not in seen:
                        links.append(Link(t.oid, p.oid, [(col, "id")]))
                        seen.add(token)
        while True:
            changed = 0
            for l in links:
                if l.child not in self.targets or l.parent not in self.targets or l.child == l.parent:
                    continue
                c, p = self.tables[l.child], self.tables[l.parent]
                if p.name == "mini_upload":
                    # A selected photo never authorizes deleting someone else's use of it.
                    continue
                match = " AND ".join(f"a.{quote(cc)}=p.{quote(pc)}" for cc, pc in l.pairs)
                changed += self.add(c.name, f"EXISTS (SELECT 1 FROM {self.selected(p.name)} WHERE {match})")
            if "product_image" in self.names:
                changed += self.add("mini_upload", f"a.id IN (SELECT p.upload_id FROM {self.selected('product_image')} WHERE p.upload_id IS NOT NULL)")
            if not changed:
                break
        self.delete_links = links

    def rows(self, name, cols):
        t = self.names[name]
        cols = [c for c in cols if c in t.columns]
        if not cols:
            return []
        return [dict(zip(cols, row)) for row in self.cur.execute(f"SELECT {','.join('a.'+quote(c) for c in cols)} FROM {self.selected(name,'a')}")]

    def counts(self):
        return {t.name: self.cur.execute(f"SELECT COUNT_BIG(*) FROM {t.temp}").fetchval() for t in self.targets.values()}

    def validate(self):
        # Employee and other business rows can never be pulled in by a reference.
        for l in self.links:
            if l.parent not in self.targets:
                continue
            c, p = self.tables[l.child], self.tables[l.parent]
            match = " AND ".join(f"a.{quote(cc)}=p.{quote(pc)}" for cc, pc in l.pairs)
            outside = ""
            if c.oid in self.targets:
                outside = f" AND NOT EXISTS (SELECT 1 FROM {c.temp} s WHERE {key_join(c,'a','s')})"
            if self.cur.execute(f"SELECT TOP(1) 1 FROM {c.sql} a WHERE EXISTS (SELECT 1 FROM {self.selected(p.name)} WHERE {match}){outside}").fetchone():
                raise ValueError("Unscoped reference: " + c.schema + "." + c.name + " -> " + p.name)
        # Mixed orders must not make another business's product disappear.
        for name in ("fd_order", "retail", "order_online_detail"):
            if name in self.names and "product_id" in self.names[name].columns:
                if self.cur.execute(f"SELECT TOP(1) 1 FROM {self.selected(name,'a')} WHERE a.product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {self.names['product'].temp} p WHERE p.id=a.product_id)").fetchone():
                    raise ValueError("Mixed food/non-food order: " + name)
        # Historical EF can map payment.order_id to both order namespaces. Refuse a
        # selected payment if its physical FK also identifies an unselected online order.
        if "order_payment" in self.names and "order_online" in self.names:
            c, p = self.names["order_payment"], self.names["order_online"]
            for link in self.links:
                if link.child == c.oid and link.parent == p.oid:
                    match = " AND ".join(f"a.{quote(cc)}=p.{quote(pc)}" for cc, pc in link.pairs)
                    if self.cur.execute(f"SELECT TOP(1) 1 FROM {self.selected(c.name,'a')} JOIN {p.sql} p ON {match} WHERE NOT EXISTS (SELECT 1 FROM {p.temp} k WHERE {key_join(p,'p','k')})").fetchone():
                        raise ValueError("Ambiguous payment order namespace")
        selected = {oid for oid, t in self.targets.items() if self.cur.execute(f"SELECT TOP(1) 1 FROM {t.temp}").fetchone()}
        for oid, in self.cur.execute("SELECT DISTINCT parent_id FROM sys.triggers WHERE parent_class=1 AND is_disabled=0"):
            if oid in selected:
                raise ValueError("Enabled DML trigger: " + self.tables[oid].name)
        for oid in selected:
            if self.tables[oid].name in PROTECTED:
                raise ValueError("Protected target")
        order = []
        pending = set(selected)
        while pending:
            ready = sorted((oid for oid in pending if not any(l.parent == oid and l.child in pending and l.child != oid for l in self.delete_links)), key=lambda oid: self.tables[oid].name)
            if not ready:
                raise ValueError("Cyclic dependencies: " + ",".join(sorted(self.tables[x].name for x in pending)))
            for oid in ready:
                pending.remove(oid)
                order.append(self.tables[oid])
        return order

    def files(self):
        candidates = set()
        for row in self.rows("mini_upload", ("file_path_name", "thumb", "is_web")):
            for col in ("file_path_name", "thumb"):
                if row.get(col):
                    candidates.add(normalize_path(row[col], bool(row.get("is_web", 1))))
        if "product_image" in self.names:
            for row in self.rows("product_image", ("image_url",)):
                if row.get("image_url"):
                    candidates.add(normalize_path(row["image_url"], True))
        # Detect shared files, including free-text URL/image lists in personal/other rows.
        for t in self.tables.values():
            textcols = [r[0] for r in self.cur.execute("SELECT name FROM sys.columns WHERE object_id=? AND system_type_id IN (35,99,167,175,231,239)", t.oid)
                        if re.search(r"image|img|picture|file|path|photo|avatar|attachment|thumb", r[0], re.I)
                        or r[0].lower() in ("content", "intro", "memo", "images", "certificate")]
            if not textcols:
                continue
            outside = f"NOT EXISTS (SELECT 1 FROM {t.temp} s WHERE {key_join(t,'a','s')})" if t.oid in self.targets else "1=1"
            for key in candidates:
                relative = "/" + key.removeprefix("private/")
                # CHARINDEX gives literal matching, unlike a LIKE pattern with %/_ escapes.
                condition = " OR ".join(f"CHARINDEX(?,CONVERT(nvarchar(max),a.{quote(c)}))>0" for c in textcols)
                if self.cur.execute(f"SELECT TOP(1) 1 FROM {t.sql} a WHERE ({outside}) AND ({condition})", *([relative] * len(textcols))).fetchone():
                    raise ValueError("File also used outside food data: " + t.name + " " + relative)
        return sorted(candidates)

    def clear(self, order):
        result = {}
        for t in order:
            self.cur.execute(f"DELETE a FROM {t.sql} a JOIN {t.temp} s ON {key_join(t,'a','s')}")
            result[t.name] = self.cur.execute("SELECT @@ROWCOUNT").fetchval()
        for t in self.targets.values():
            if self.cur.execute(f"SELECT TOP(1) 1 FROM {t.sql} a JOIN {t.temp} s ON {key_join(t,'a','s')}").fetchone():
                raise ValueError("Remaining scoped rows: " + t.name)
        return result


def normalize_path(value, is_web):
    value = value.strip()
    if re.match(r"^https?://", value, re.I):
        url = urlsplit(value)
        if url.hostname not in PUBLIC_HOSTS or url.query or url.fragment or url.username or url.password:
            raise ValueError("Unowned or ambiguous file URL")
        value = unquote(url.path)
    elif "?" in value or "#" in value:
        raise ValueError("Ambiguous file path")
    if "\\" in value or "%" in value or "\x00" in value or not value.startswith("/upload/"):
        raise ValueError("Unsafe file path: " + value)
    key = value[1:]
    if any(x in ("", ".", "..") for x in key.split("/")) or len(PurePosixPath(key).parts) < 3:
        raise ValueError("Unsafe file path")
    return key if is_web else "private/" + key


def save_manifest(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.name != "nt":
        os.chmod(temp, 0o600)
    temp.replace(path)


def local_target(root, key):
    base = Path(root).resolve()
    if key.startswith("private/"):
        target = base / key.removeprefix("private/")
    else:
        target = base / "wwwroot" / key
    # Match UploadPaths.LocalFilePath: private files are app/upload, public are
    # app/wwwroot/upload. Resolve before unlink, including symlinks in parent paths.
    if target.is_symlink() or not target.resolve().is_relative_to(base) or target.exists() and not target.is_file():
        raise ValueError("Unsafe local upload copy")
    return target


def remove_files(manifest, path, *, s3=None):
    require_testing()
    if manifest["database_state"] != "committed":
        raise ValueError("File deletion requires a recorded successful database commit")
    keys = manifest["file_keys"]
    expected = hashlib.sha256("\n".join(keys).encode()).hexdigest()
    if expected != manifest["file_keys_sha256"] or manifest["bucket"] != BUCKET:
        raise ValueError("Invalid file manifest")
    if keys and s3 is None:
        import boto3
        s3 = boto3.client("s3", region_name=REGION)
    for key in keys:
        require_testing()
        normalized = normalize_path("/" + key.removeprefix("private/"), not key.startswith("private/"))
        if key != normalized:
            raise ValueError("Invalid object key")
        if key in manifest["files_done"]:
            continue
        # Remove versions and delete markers for this exact key, never its prefix neighbors.
        paginator = s3.get_paginator("list_object_versions")
        versions = []
        for page in paginator.paginate(Bucket=BUCKET, Prefix=key):
            for item in page.get("Versions", []) + page.get("DeleteMarkers", []):
                if item["Key"] == key:
                    versions.append(item["VersionId"])
        for version in versions:
            s3.delete_object(Bucket=BUCKET, Key=key, VersionId=version)
        if not versions:
            s3.delete_object(Bucket=BUCKET, Key=key)
        root = manifest.get("local_app_root")
        if root:
            target = local_target(root, key)
            if target.exists():
                target.unlink()
        manifest["files_done"].append(key)
        save_manifest(path, manifest)
    manifest["files_state"] = "complete"
    save_manifest(path, manifest)


def run(connection, database, manifest_path, execute=False, local_app_root=None, file_remover=remove_files):
    require_testing()
    cur = connection.cursor()
    if cur.execute("SELECT DB_NAME()").fetchval() != database:
        raise ValueError("Unexpected database; no deletion")
    if cur.execute("SELECT @@TRANCOUNT").fetchval():
        raise ValueError("An outer transaction is already active")
    cur.execute("SET XACT_ABORT ON; SET LOCK_TIMEOUT 15000; SET TRANSACTION ISOLATION LEVEL SERIALIZABLE; BEGIN TRANSACTION;")
    try:
        # Freeze reviewed business tables while selecting and clearing; read other tables
        # under Serializable to detect references without any writes to personal records.
        tables, _ = catalog(cur)
        for t in sorted(tables.values(), key=lambda x: (x.schema, x.name)):
            if t.schema == "dbo" and t.name in ALLOWED:
                cur.execute(f"SELECT COUNT_BIG(*) FROM {t.sql} WITH (TABLOCKX,HOLDLOCK)").fetchval()
        scope = Scope(cur)
        scope.seed()
        scope.propagate()
        order = scope.validate()
        keys = scope.files()
        s3 = None
        if execute and file_remover is remove_files and keys:
            # Missing dependencies or bucket-version read permissions fail before SQL deletion.
            import boto3
            s3 = boto3.client("s3", region_name=REGION)
            s3.list_object_versions(Bucket=BUCKET, Prefix=keys[0], MaxKeys=1)
        if local_app_root:
            for key in keys:
                local_target(local_app_root, key)
        manifest = {"version": 1, "database": database, "database_state": "preview", "counts": scope.counts(),
                    "delete_order": [t.name for t in order], "file_keys": keys,
                    "file_keys_sha256": hashlib.sha256("\n".join(keys).encode()).hexdigest(),
                    "bucket": BUCKET, "region": REGION, "local_app_root": local_app_root,
                    "files_done": [], "files_state": "pending"}
        if not execute:
            cur.execute("ROLLBACK TRANSACTION")
            save_manifest(manifest_path, manifest)
            return manifest
        # Durable retry list precedes deletion. It cannot authorize files before commit.
        manifest["database_state"] = "prepared"
        save_manifest(manifest_path, manifest)
        require_testing()
        manifest["deleted"] = scope.clear(order)
        require_testing()
        cur.execute("COMMIT TRANSACTION")
        manifest["database_state"] = "committed"
        save_manifest(manifest_path, manifest)
    except Exception:
        if cur.execute("SELECT @@TRANCOUNT").fetchval():
            cur.execute("ROLLBACK TRANSACTION")
        raise
    if file_remover is remove_files:
        file_remover(manifest, manifest_path, s3=s3)
    else:
        file_remover(manifest, manifest_path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="食材测试数据清理：默认只预览，不自动读取生产配置")
    parser.add_argument("--database", default="snowmeet_new")
    parser.add_argument("--dsn-env", default="SNOWMEET_FNB_CLEAR_DSN", help="含完整 ODBC 连接串的环境变量名")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--execute", action="store_true")
    action.add_argument("--resume-files", action="store_true", help="仅重试清单中的文件，不再连接数据库")
    action.add_argument("--status", action="store_true", help="查看临时 skill 状态，不连接数据库或 S3")
    action.add_argument("--retire", action="store_true", help="正式上线后永久作废，不连接数据库或 S3")
    parser.add_argument("--manifest", type=Path, help="新的清理结果/文件重试清单，不覆盖已有清单")
    parser.add_argument("--local-app-root", help="同时删除历史本机副本，传 API 项目绝对路径，涵盖公开及私有上传")
    args = parser.parse_args()
    if args.retire or args.status:
        print(json.dumps(retire_skill() if args.retire else lifecycle(), ensure_ascii=False))
        return
    require_testing()
    if not args.manifest:
        parser.error("--manifest is required for preview, execution and file retry")
    if args.resume_files:
        remove_files(json.loads(args.manifest.read_text(encoding="utf-8")), args.manifest)
        print("文件清理完成")
        return
    if args.manifest.exists():
        raise ValueError("Manifest already exists; choose a new file or --resume-files")
    if args.local_app_root:
        base = Path(args.local_app_root)
        if not base.is_absolute() or not base.is_dir():
            raise ValueError("local-app-root must be an existing absolute directory")
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        raise ValueError("Missing connection environment variable: " + args.dsn_env)
    import pyodbc
    with pyodbc.connect(dsn, autocommit=True, timeout=15) as connection:
        result = run(connection, args.database, args.manifest, args.execute, args.local_app_root)
    print(json.dumps({"database_state": result["database_state"], "counts": result["counts"],
                      "file_count": len(result["file_keys"]), "files_state": result["files_state"]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except Exception as error:
        # Driver exceptions can include server/connection details; avoid printing secrets.
        print(str(error) if isinstance(error, ValueError) else "清理失败（" + type(error).__name__ + "），数据库阶段已回滚或文件待重试；检查清单状态。", file=sys.stderr)
        raise SystemExit(1)
