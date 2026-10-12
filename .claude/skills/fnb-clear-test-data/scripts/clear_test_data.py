"""Soft-delete the food v4 test data. Default: preview. No implicit connection.

Scope (user, 2026-10-12): only dbo tables whose name starts with fnb_v4_. Nothing is
physically deleted: rows get valid=0 and a fresh update timestamp. Tables without a valid
column are left exactly as they are and only reported.

Python 3.10+; pyodbc for SQL Server.
Never imports application startup or reads config.sqlServer.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

PREFIX = "fnb_v4_"
# The v4 tables call it updated_at (UTC, the way the API writes it); update_date is honoured too.
STAMP_COLUMNS = ("updated_at", "update_date")
VALID_TYPES = frozenset(("bit", "tinyint", "smallint", "int"))
LIVE = "([valid] IS NULL OR [valid]<>0)"
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


def literal(text):
    return "N'" + text.replace("'", "''") + "'"


def save_manifest(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if os.name != "nt":
        os.chmod(temp, 0o600)
    temp.replace(path)


@dataclass
class Table:
    name: str
    oid: int
    columns: dict[str, str] = field(default_factory=dict)
    keys: list[str] = field(default_factory=list)

    @property
    def sql(self):
        return "[dbo]." + quote(self.name)

    @property
    def stamps(self):
        return [c for c in STAMP_COLUMNS if c in self.columns]


def catalog(cur):
    """The fnb_v4_ tables, with the columns this script acts on and their primary keys."""
    tables = {}
    for schema, name, oid in cur.execute("SELECT s.name,t.name,t.object_id FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE t.is_ms_shipped=0 AND LEFT(t.name,?)=?", len(PREFIX), PREFIX).fetchall():
        if schema != "dbo":
            raise ValueError("Unreviewed v4 table outside dbo: " + schema + "." + name)
        tables[oid] = Table(name, oid)
    wanted = ("valid",) + STAMP_COLUMNS
    for oid, column, kind in cur.execute(f"SELECT c.object_id,c.name,ty.name FROM sys.columns c JOIN sys.types ty ON ty.user_type_id=c.user_type_id WHERE c.name IN ({','.join('?' for _ in wanted)})", *wanted).fetchall():
        if oid in tables:
            tables[oid].columns[column.lower()] = kind
    for oid, column in cur.execute("SELECT i.object_id,c.name FROM sys.indexes i JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id WHERE i.is_primary_key=1 ORDER BY i.object_id,ic.key_ordinal").fetchall():
        if oid in tables:
            tables[oid].keys.append(column)
    ordered = sorted(tables.values(), key=lambda t: t.name)
    triggered = {oid for oid, in cur.execute("SELECT DISTINCT parent_id FROM sys.triggers WHERE parent_class=1 AND is_disabled=0").fetchall()}
    for t in ordered:
        if "valid" not in t.columns:
            continue
        if t.columns["valid"] not in VALID_TYPES:
            raise ValueError("Unexpected valid column type: " + t.name)
        if t.oid in triggered:
            raise ValueError("Enabled DML trigger: " + t.name)
    return ordered


def invalidate(cur, targets, expected, stamp):
    """valid=0 plus a fresh timestamp for every live row. Never a DELETE."""
    done = {}
    for t in targets:
        if not expected[t.name]:
            done[t.name] = {"count": 0, "keys": []}
            continue
        sets = ["[valid]=0"] + [quote(c) + "=CONVERT(datetime2(3),?,121)" for c in t.stamps]
        output = " OUTPUT " + ",".join("inserted." + quote(k) for k in t.keys) if t.keys else ""
        cur.execute(f"UPDATE {t.sql} SET {','.join(sets)}{output} WHERE {LIVE}", *([stamp] * len(t.stamps)))
        if t.keys:
            keys = [r[0] if len(t.keys) == 1 else list(r) for r in cur.fetchall()]
            count = len(keys)
        else:
            keys, count = None, cur.rowcount
        if count != expected[t.name]:
            raise ValueError("Row count changed during cleanup: " + t.name)
        done[t.name] = {"count": count, "keys": keys}
    if targets:
        check = " UNION ALL ".join(f"SELECT {literal(t.name)},COUNT_BIG(*) FROM {t.sql} WHERE {LIVE}" for t in targets)
        for name, remaining in cur.execute(check).fetchall():
            if remaining:
                raise ValueError("Remaining valid rows: " + name)
    return done


def run(connection, database, manifest_path, execute=False):
    require_testing()
    cur = connection.cursor()
    if cur.execute("SELECT DB_NAME()").fetchval() != database:
        raise ValueError("Unexpected database; nothing changed")
    if cur.execute("SELECT @@TRANCOUNT").fetchval():
        raise ValueError("An outer transaction is already active")
    cur.execute("SET XACT_ABORT ON; SET LOCK_TIMEOUT 15000; SET TRANSACTION ISOLATION LEVEL SERIALIZABLE; BEGIN TRANSACTION;")
    try:
        tables = catalog(cur)
        targets = [t for t in tables if "valid" in t.columns]
        # One statement both freezes the tables that will change and counts every v4 table.
        # Tables without valid are only counted for the report and are not held.
        parts = [f"SELECT {literal(t.name)},COUNT_BIG(*),ISNULL(SUM(CASE WHEN {LIVE} THEN 1 ELSE 0 END),0) FROM {t.sql} WITH (TABLOCKX,HOLDLOCK)"
                 if "valid" in t.columns else
                 f"SELECT {literal(t.name)},COUNT_BIG(*),NULL FROM {t.sql} WITH (READCOMMITTED)" for t in tables]
        counted = {name: (int(total), live) for name, total, live in cur.execute(" UNION ALL ".join(parts)).fetchall()} if parts else {}
        stamp = cur.execute("SELECT CONVERT(varchar(23),SYSUTCDATETIME(),121)").fetchval()
        expected = {t.name: int(counted[t.name][1]) for t in targets}
        manifest = {"version": 2, "mode": "soft-delete", "database": database, "database_state": "preview",
                    "prefix": PREFIX, "stamp_utc": stamp,
                    "tables": {t.name: {"rows": counted[t.name][0], "to_invalidate": expected[t.name], "stamp_columns": t.stamps} for t in targets},
                    "skipped_no_valid": {t.name: counted[t.name][0] for t in tables if "valid" not in t.columns}}
        if not execute:
            cur.execute("ROLLBACK TRANSACTION")
            save_manifest(manifest_path, manifest)
            return manifest
        # The record of what is about to change is written before anything changes.
        manifest["database_state"] = "prepared"
        save_manifest(manifest_path, manifest)
        require_testing()
        manifest["invalidated"] = invalidate(cur, targets, expected, stamp)
        require_testing()
        cur.execute("COMMIT TRANSACTION")
        manifest["database_state"] = "committed"
        save_manifest(manifest_path, manifest)
    except Exception:
        if cur.execute("SELECT @@TRANCOUNT").fetchval():
            cur.execute("ROLLBACK TRANSACTION")
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description="食材 v4 测试数据逻辑删除：默认只预览，不自动读取生产配置")
    parser.add_argument("--database", default="snowmeet_new")
    parser.add_argument("--dsn-env", default="SNOWMEET_FNB_CLEAR_DSN", help="含完整 ODBC 连接串的环境变量名")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--execute", action="store_true", help="把 fnb_v4_ 表中有效的行置为 valid=0 并刷新更新时间")
    action.add_argument("--status", action="store_true", help="查看临时 skill 状态，不连接数据库")
    action.add_argument("--retire", action="store_true", help="正式上线后永久作废，不连接数据库")
    parser.add_argument("--manifest", type=Path, help="新的结果清单，不覆盖已有清单")
    args = parser.parse_args()
    if args.retire or args.status:
        print(json.dumps(retire_skill() if args.retire else lifecycle(), ensure_ascii=False))
        return
    require_testing()
    if not args.manifest:
        parser.error("--manifest is required for preview and execution")
    if args.manifest.exists():
        raise ValueError("Manifest already exists; choose a new file")
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        raise ValueError("Missing connection environment variable: " + args.dsn_env)
    import pyodbc
    with pyodbc.connect(dsn, autocommit=True, timeout=15) as connection:
        result = run(connection, args.database, args.manifest, args.execute)
    summary = {"database_state": result["database_state"], "stamp_utc": result["stamp_utc"],
               "to_invalidate": {name: t["to_invalidate"] for name, t in result["tables"].items() if t["to_invalidate"]},
               "skipped_no_valid": {name: rows for name, rows in result["skipped_no_valid"].items() if rows}}
    if "invalidated" in result:
        summary["invalidated"] = {name: t["count"] for name, t in result["invalidated"].items() if t["count"]}
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except Exception as error:
        # Driver exceptions can include server/connection details; avoid printing secrets.
        print(str(error) if isinstance(error, ValueError) else "清理失败（" + type(error).__name__ + "），数据库事务已回滚；检查清单状态。", file=sys.stderr)
        raise SystemExit(1)
