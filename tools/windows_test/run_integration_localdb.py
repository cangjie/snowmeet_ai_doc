"""只在本机随机 LocalDB 临时库验证 v4 增量 SQL 和接口；不读生产配置。

先构建 SnowmeetApi.Tests；本运行器对测试工程使用 --no-build。
efschema.dll 只生成元数据 SQL，不启动 SnowmeetApi，也不连接数据库。
"""
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_DIR = HERE.parents[2] / "SnowmeetApi"
SQL_DIR = HERE.parents[1] / "sql"
DOTNET = r"C:\Program Files\dotnet\dotnet.exe"
LOCALDB = r"C:\Program Files\Microsoft SQL Server\150\Tools\Binn\SqlLocalDB.exe"
# 2026-10-12 后补 valid 的 21 张表（去掉 fnb_v4_ 前缀），以及随之加上 valid 条件的 5 个唯一索引。
LATE_VALID = ["alert_delivery", "area_image", "batch", "batch_detail", "batch_image", "check_handling", "check_line", "check_sheet",
              "order", "order_import", "order_line", "recipe", "recipe_line", "request", "stock_document", "stock_document_line",
              "stock_movement", "stock_operation", "stocktake_line", "supply_movement", "tool_log"]
LATE_FILTERS = [("([shop_id], [batch_no]) WHERE [valid] = 1;", "([shop_id], [batch_no]);"),
                ("([shop_id], [business_date]) WHERE [valid] = 1;", "([shop_id], [business_date]);"),
                ("([shop_id], [source_type], [external_order_no]) WHERE [valid] = 1 AND [external_order_no] IS NOT NULL;", "([shop_id], [source_type], [external_order_no]) WHERE [external_order_no] IS NOT NULL;"),
                ("([shop_id], [source_method], [dedupe_key]) WHERE [valid] = 1;", "([shop_id], [source_method], [dedupe_key]);"),
                ("([shop_id], [asset_no]) WHERE [valid] = 1;", "([shop_id], [asset_no]);")]
SHARED = ["shop_list", "staff", "mini_upload", "category", "product", "order", "member",
          "member_social_account", "social_account_for_job", "staff_social_account", "mini_session"]


def run_script(cur, text):
    cur.execute(text)
    while cur.nextset():
        pass


def main():
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    # 可选的工作区驱动安装位置；普通机器直接使用已安装的 pyodbc。
    deps = API_DIR.parent / ".local" / "fnb-v4" / "deps"
    if deps.exists():
        sys.path.insert(0, str(deps))
    import pyodbc
    from build_fnb_v4_sql import build, build_operations

    ddl_path = HERE / "ef_create.sql"
    if not ddl_path.exists():
        project = HERE / "efschema" / "efschema.csproj"
        subprocess.run([DOTNET, "build", str(project), "--no-restore", "--nologo", "-clp:ErrorsOnly"], check=True)
        subprocess.run([DOTNET, str(HERE / "efschema/bin/Debug/net9.0/efschema.dll"), str(ddl_path)], check=True)
    ef = ddl_path.read_text(encoding="utf-8-sig")
    sql = (SQL_DIR / "2026-10-06_fnb_v4_rebuild.sql").read_text(encoding="utf-8")
    extension = (SQL_DIR / "2026-10-06_fnb_v4_operations.sql").read_text(encoding="utf-8")
    # 2026-10-12：全部 v4 表补 valid，唯一索引和视图只看有效行。这两份在原有两份之后执行，原有两份保持不变。
    later = [(SQL_DIR / name).read_text(encoding="utf-8") for name in ("2026-10-12_fnb_v4_add_valid.sql", "2026-10-12_fnb_v4_valid_filters.sql", "2026-10-13_fnb_v4_enabled.sql")]
    # 原有两份脚本是 10-06 交付时的结构；之后补的列和索引条件在 later 里，比较前先从 EF 输出里去掉。
    baseline = re.sub(r"^    \[enabled\] bit NOT NULL DEFAULT CAST\(1 AS bit\),\n", "", ef, flags=re.M)
    baseline = re.sub(r"^    \[valid\] bit NOT NULL DEFAULT CAST\(1 AS bit\),\n(?=(?:    \[row_version\][^\n]*\n)?    CONSTRAINT \[PK_fnb_v4_(?:%s)\])" % "|".join(LATE_VALID), "", baseline, flags=re.M)
    for late_filter, original in LATE_FILTERS:
        baseline = baseline.replace(late_filter, original)
    if extension != build_operations(baseline):
        raise RuntimeError("扩展 SQL 与 EF 模型不一致")
    if sql != build(baseline):
        raise RuntimeError("SQL 与 EF 模型不一致，请先重新生成并审阅 SQL")
    if re.search(r"\b(DROP|DELETE|UPDATE|TRUNCATE|MERGE|ALTER)\b", sql + extension, re.I):
        raise RuntimeError("v4 SQL 含非新增操作，禁止执行")
    started = subprocess.run([LOCALDB, "start", "MSSQLLocalDB"], capture_output=True, text=True)
    if started.returncode:
        raise RuntimeError("本机 LocalDB 启动失败：" + started.stdout + started.stderr)
    info = subprocess.run([LOCALDB, "info", "MSSQLLocalDB"], capture_output=True, text=True, check=True).stdout
    match = re.search(r"np:(\\\\\.\\pipe\\LOCALDB#[^\s]+)", info, re.I)
    if not match:
        raise RuntimeError("未取得本机 LocalDB 管道；拒绝使用其他 SQL Server")
    pipe = match.group(1)
    database = "snowmeet_fnb_test_" + uuid.uuid4().hex[:12]

    def connect(name):
        if name not in ("master", database):
            raise RuntimeError("仅允许本运行器创建的临时库")
        return pyodbc.connect("DRIVER={SQL Server};SERVER=%s;Network=dbnmpntw;DATABASE=%s;Trusted_Connection=yes" % (pipe, name), autocommit=True, timeout=15)

    blocks = {m.group(1): m.group(0) for m in re.finditer(r"CREATE TABLE \[(\w+)\] \(.*?^\);", ef, re.S | re.M)}

    def shared_ddl(name):
        # 测试身份关联使用真实字段，忽略非 fnb 的其他外键以缩小夹具。
        lines = [line for line in blocks[name].splitlines() if "FOREIGN KEY" not in line]
        return re.sub(r",\s*\n\);", "\n);", "\n".join(lines))

    master = connect("master")
    master.execute(f"CREATE DATABASE [{database}] COLLATE Chinese_PRC_CI_AS")
    connection = None
    code = 1
    try:
        connection = connect(database)
        cur = connection.cursor()
        for name in SHARED:
            cur.execute(shared_ddl(name))
        # 身份夹具也保留 EF 索引，避免复用店员多层关联查询在 LocalDB 等待内存授予。
        for index in re.finditer(r"CREATE (?:UNIQUE )?INDEX \[\w+\] ON \[(\w+)\].*?;", ef, re.S):
            if index.group(1) in SHARED:
                cur.execute(index.group(0))
        cur.execute(blocks["fnb_unit"])
        cur.execute("INSERT INTO fnb_unit(code,name,dimension,factor_to_base,valid,sort) VALUES ('legacy_unit',N'历史单位',1,5,0,99)")
        legacy = ["fnb_material_category", "fnb_material_item", "fnb_material_batch", "fnb_material_batch_stock", "fnb_material_alert_log"]
        for name in legacy:
            cur.execute(f"CREATE TABLE [{name}] (id int PRIMARY KEY, proof varchar(32) NOT NULL)")
            cur.execute(f"INSERT INTO [{name}] VALUES (1,'legacy-preserved')")
        run_script(cur, sql)
        run_script(cur, extension)
        # 第一遍生成的 v4 数据也必须在第二遍执行后保留。
        cur.execute("INSERT INTO fnb_v4_category(level,name,is_prepared,sort,valid,created_at) VALUES (1,N'重跑保留',0,0,1,SYSUTCDATETIME())")
        run_script(cur, sql)
        run_script(cur, extension)
        for _ in range(2):
            for script in later:
                run_script(cur, script)
        for name in legacy:
            assert [tuple(row) for row in cur.execute(f"SELECT id,proof FROM [{name}]")] == [(1, "legacy-preserved")], name
        unit = cur.execute("SELECT name,dimension,factor_to_base,valid,sort FROM fnb_unit WHERE code='legacy_unit'").fetchone()
        assert tuple(unit) == ("历史单位", 1, 5, False, 99), unit
        assert cur.execute("SELECT COUNT(*) FROM fnb_v4_category WHERE name=N'重跑保留'").fetchval() == 1
        print("增量 SQL 重复执行：旧表数据、已有单位与已有 v4 数据全部保留")
        mismatches = []
        for name in sorted(k for k in blocks if k == "fnb_unit" or k.startswith("fnb_v4_")):
            expected = set(re.findall(r"^    \[(\w+)\] ", blocks[name], re.M))
            actual = {r[0] for r in cur.execute("SELECT name FROM sys.columns WHERE object_id=OBJECT_ID(?)", name)}
            if expected != actual:
                mismatches.append((name, sorted(expected - actual), sorted(actual - expected)))
        if mismatches:
            raise RuntimeError("EF/SQL 字段不一致：" + str(mismatches))
        print("EF 模型与全部 v4/单位表字段一致；两份脚本均不含非新增操作")
        if "--verify-drop-legacy-fnb" in sys.argv:
            from verify_drop_legacy_fnb import verify
            verify(connection, (SQL_DIR / "2026-10-06_fnb_drop_legacy_objects.sql").read_text(encoding="utf-8"))
            return 0
        if "--verify-clear-test-data" in sys.argv:
            from verify_clear_food_test_data import verify
            verify(connection, ef)
            return 0
        env = os.environ.copy()
        env["SNOWMEET_FNB_TEST_SQLSERVER"] = rf"Server=(localdb)\MSSQLLocalDB;Database={database};Trusted_Connection=True;TrustServerCertificate=True;Connect Timeout=30"
        # 测试输出实时显示；只运行测试程序集，不运行生产 Startup/读取 config.sqlServer。
        with subprocess.Popen([DOTNET, "test", "SnowmeetApi.Tests/SnowmeetApi.Tests.csproj", "--no-build", "--nologo",
                               "--filter", "FullyQualifiedName~FnbSqlServerIntegrationTests|FullyQualifiedName~FnbV4WorkflowIntegrationTests", "--logger", "console;verbosity=normal"],
                              cwd=API_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace") as process:
            for line in process.stdout:
                if re.search(r"Passed |Failed |Skipped |Total tests|Passed!|Failed!|error|Error Message|Assert|Exception|Stack Trace| at |code=|Expected:|Actual:", line):
                    print(line.rstrip())
            code = process.wait()
    finally:
        if connection is not None:
            connection.close()
        # 只清理本运行器创建的随机临时数据库；不属于交付的增量 SQL。
        master.execute(f"ALTER DATABASE [{database}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        master.execute(f"DROP DATABASE [{database}]")
        master.close()
        print("已删除临时 LocalDB 数据库", database)
    return code


if __name__ == "__main__":
    sys.exit(main())
