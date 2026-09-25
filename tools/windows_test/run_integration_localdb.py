"""本机 Windows + LocalDB 跑 SnowmeetApi 食材集成测试（先在 SnowmeetApi 目录 dotnet build SnowmeetApi.Tests）：旧表按 EF 模型建（不读生产库），再执行 09-22 建表 + 09-24 迁移，
核对 EF 模型与迁移后表结构，然后跑 FnbSqlServerIntegrationTests，结束删库。"""
import os, re, subprocess, sys, uuid, pyodbc
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

LOCALDB = r"C:\Program Files\Microsoft SQL Server\150\Tools\Binn\SqlLocalDB.exe"
subprocess.run([LOCALDB, "start", "MSSQLLocalDB"], capture_output=True)
_info = subprocess.run([LOCALDB, "info", "MSSQLLocalDB"], capture_output=True, text=True).stdout
PIPE = re.search(r"np:(\\\\\.\\pipe\\\S+)", _info).group(1)
HERE = Path(__file__).resolve().parent
SQL_DIR = HERE.parents[1] / "sql"                 # snowmeet_ai_doc/sql
API_DIR = HERE.parents[2] / "SnowmeetApi"         # 与 snowmeet_ai_doc 同级
DOTNET = r"C:\Program Files\dotnet\dotnet.exe"
# 旧表（shop_list、staff 等）按 EF 模型建：没有 ef_create.sql 就先用 efschema 生成（只生成脚本，不连库）
if not (HERE / "ef_create.sql").exists():
    subprocess.run([DOTNET, "run", "--project", str(HERE / "efschema"), "--", str(HERE / "ef_create.sql")], check=True)
DB = "snowmeet_fnb_test_" + uuid.uuid4().hex[:12]
OLD = ["shop_list", "staff", "mini_upload", "category", "product", "order", "fd_order", "fnb_material_batch", "fnb_material_alert_log"]


def connect(database):
    return pyodbc.connect("DRIVER={SQL Server};SERVER=%s;Network=dbnmpntw;DATABASE=%s;Trusted_Connection=yes" % (PIPE, database), autocommit=True)


def run_script(cur, text):
    cur.execute(text)
    while cur.nextset():
        pass


ef = (HERE / "ef_create.sql").read_text(encoding="utf-8-sig")
blocks = {m.group(1): m.group(0) for m in re.finditer(r"CREATE TABLE \[(\w+)\] \((.*?)\n\);", ef, re.S)}


def old_table_ddl(name):
    lines = [l for l in blocks[name].split("\n") if "FOREIGN KEY" not in l and "REFERENCES" not in l and "ON DELETE" not in l]
    body = "\n".join(lines)
    return re.sub(r",\s*\n\);", "\n);", body)


def ef_columns(name):
    return set(re.findall(r"^\s+\[(\w+)\] ", blocks[name], re.M))


master = connect("master")
master.execute("CREATE DATABASE [%s] COLLATE Chinese_PRC_CI_AS" % DB)
code = 1
try:
    cur = connect(DB).cursor()
    for t in OLD:
        cur.execute(old_table_ddl(t))
    for script in ["2026-09-22_fnb_inventory_other_tables.sql", "2026-09-24_fnb_item_expiry_settings.sql"]:
        run_script(cur, (SQL_DIR / script).read_text(encoding="utf-8"))
    mismatches = []
    for t in sorted(k for k in blocks if k.startswith("fnb_") and k not in OLD):
        actual = {r[0] for r in cur.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID(?)", t).fetchall()}
        if not actual:
            mismatches.append((t, "表不存在"))
            continue
        missing = ef_columns(t) - actual
        if missing:
            mismatches.append((t, "EF 有而库里没有：" + ", ".join(sorted(missing))))
        extra = actual - ef_columns(t)
        if extra:
            print("  提示：%s 库里多出（EF 未映射）：%s" % (t, ", ".join(sorted(extra))))
    print("EF 模型 ↔ 迁移后结构：" + ("全部一致" if not mismatches else "不一致 %s" % mismatches))
    if mismatches:
        raise SystemExit(1)
    env = os.environ.copy()
    env["SNOWMEET_FNB_TEST_SQLSERVER"] = r"Server=(localdb)\MSSQLLocalDB;Database=%s;Trusted_Connection=True;TrustServerCertificate=True;Connect Timeout=30" % DB
    result = subprocess.run([DOTNET, "test", r"SnowmeetApi.Tests\SnowmeetApi.Tests.csproj", "--no-build", "--nologo",
                             "--filter", "FullyQualifiedName~FnbSqlServerIntegrationTests", "--logger", "console;verbosity=normal"],
                            cwd=API_DIR, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = result.stdout + result.stderr
    lines = [l for l in out.splitlines() if re.search(r"Passed |Failed |Skipped |Total tests|Passed!|Failed!|error|Error Message|Assert|Exception", l)]
    print("\n".join(lines[-60:]))
    code = result.returncode
finally:
    master.execute("ALTER DATABASE [%s] SET SINGLE_USER WITH ROLLBACK IMMEDIATE" % DB)
    master.execute("DROP DATABASE [%s]" % DB)
    print("已删除临时库", DB)
sys.exit(code)
