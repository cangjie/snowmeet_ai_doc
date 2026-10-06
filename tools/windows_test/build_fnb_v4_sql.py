"""只读离线 EF 建表脚本，生成供人工审阅的增量 v4 SQL；不连接任何数据库。"""
import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parents[1] / "sql" / "2026-10-06_fnb_v4_rebuild.sql"


def build(ef):
    tables = [(m.group(1), m.group(0)) for m in re.finditer(r"CREATE TABLE \[(\w+)\] \(.*?^\);", ef, re.S | re.M)
              if m.group(1) == "fnb_unit" or m.group(1).startswith("fnb_v4_")]
    if len(tables) != 19:
        raise ValueError(f"预期 19 个 v4/单位表，实际 {len(tables)}；请核对 EF 结构")
    parts = ["""-- 食材管理 v4，第 1 期，2026-10-06。只新增，不迁移、不覆盖旧食材数据。
-- 原来的 fnb_* 业务表、product、[order] 的结构和数据全部保留。
-- 新系统使用 fnb_v4_* 空表；fnb_unit 共用，只补缺失种子。
-- 可重复执行：已有表、索引、视图和种子不会重建。上线由用户审阅后手动执行。
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRY
BEGIN TRANSACTION;
IF OBJECT_ID(N'dbo.shop_list', N'U') IS NULL OR OBJECT_ID(N'dbo.staff', N'U') IS NULL
 OR OBJECT_ID(N'dbo.mini_upload', N'U') IS NULL OR OBJECT_ID(N'dbo.product', N'U') IS NULL
 THROW 51000, N'缺少共享表，停止；本脚本不会创建或修改业务共享表。', 1;
"""]
    for name, ddl in tables:
        ddl = ddl.replace(f"CREATE TABLE [{name}]", f"CREATE TABLE [dbo].[{name}]")
        ddl = re.sub(r"REFERENCES \[(\w+)\]", r"REFERENCES [dbo].[\1]", ddl)
        columns = re.findall(r"^    \[(\w+)\] ", ddl, re.M)
        missing = " OR ".join(f"COL_LENGTH(N'dbo.{name}', N'{c}') IS NULL" for c in columns)
        parts.append(f"IF OBJECT_ID(N'dbo.{name}', N'U') IS NULL\nBEGIN\n{ddl}\nEND\nELSE IF {missing}\n THROW 51001, N'已有表 {name} 结构不完整，请人工核对；脚本不覆盖。', 1;\n")
    parts.append("""-- 只插入缺失单位，不更新已有单位行。
INSERT INTO dbo.fnb_unit (code,name,dimension,factor_to_base,valid,sort)
SELECT s.code,s.name,s.dimension,s.factor,1,s.sort
FROM (VALUES ('g','克',1,1,10),('kg','千克',1,1000,11),('ml','毫升',2,1,20),
 ('l','升',2,1000,21),('piece','个',3,1,30)) AS s(code,name,dimension,factor,sort)
WHERE NOT EXISTS (SELECT 1 FROM dbo.fnb_unit u WHERE u.code = s.code);
IF EXISTS (SELECT 1 FROM dbo.fnb_unit WHERE code IN ('g','ml','piece') AND
 (valid <> 1 OR factor_to_base <> 1 OR dimension <> CASE code WHEN 'g' THEN 1 WHEN 'ml' THEN 2 ELSE 3 END))
 THROW 51002, N'已有基本单位不符合约定，请人工核对；不会更新已有数据。', 1;
""")
    for match in re.finditer(r"CREATE (?:UNIQUE )?INDEX \[(\w+)\] ON \[(fnb_v4_\w+|fnb_unit)\].*?;", ef, re.S):
        index, table = match.group(1), match.group(2)
        statement = match.group(0).replace(f"ON [{table}]", f"ON [dbo].[{table}]")
        parts.append(f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.{table}') AND name = N'{index}')\n{statement}\n")
    views = {
        "vw_fnb_v4_stock": """SELECT b.shop_id,b.item_id,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state='final' AND b.dispose_status IS NULL
  AND b.effective_expire >= CONVERT(date,SYSUTCDATETIME() AT TIME ZONE 'UTC' AT TIME ZONE 'China Standard Time')
  AND (b.ready_at IS NULL OR b.ready_at <= SYSUTCDATETIME()) THEN b.quantity ELSE 0 END)) AS available_qty,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state='staged' AND b.dispose_status IS NULL THEN b.quantity ELSE 0 END)) AS staged_qty,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state='sealed' AND b.dispose_status IS NULL THEN b.quantity ELSE 0 END)) AS sealed_qty,
 CONVERT(decimal(19,6),SUM(b.quantity)) AS total_qty,CONVERT(decimal(19,6),SUM(b.amount)) AS total_amount,
 CONVERT(decimal(19,6),SUM(b.amount)/NULLIF(SUM(b.quantity),0)) AS average_unit_cost
FROM dbo.fnb_v4_batch b GROUP BY b.shop_id,b.item_id""",
        "vw_fnb_v4_loss": """SELECT m.id AS source_id,d.document_type AS source_type,m.shop_id,m.item_id,d.business_date,
 CONVERT(decimal(19,6),-m.delta_qty) AS loss_qty,CONVERT(decimal(19,6),-m.delta_amount) AS loss_amount
FROM dbo.fnb_v4_stock_movement m
JOIN dbo.fnb_v4_stock_document_line l ON l.id=m.document_line_id
JOIN dbo.fnb_v4_stock_document d ON d.id=l.document_id
WHERE d.status='posted' AND d.document_type IN ('waste','destroy','stocktake')
UNION ALL
SELECT o.id,'op',d.shop_id,o.item_id,d.business_date,o.loss_base_qty,
 CONVERT(decimal(19,6),o.loss_base_qty * COALESCE(c.amount/NULLIF(c.qty,0),0))
FROM dbo.fnb_v4_stock_operation o JOIN dbo.fnb_v4_stock_document d ON d.id=o.document_id
OUTER APPLY (SELECT SUM(m.amount) AS amount,SUM(m.quantity) AS qty
 FROM dbo.fnb_v4_stock_movement m JOIN dbo.fnb_v4_stock_document_line l ON l.id=m.document_line_id
 WHERE l.document_id=o.document_id AND m.batch_id=o.source_batch_id AND m.direction=-1) c
WHERE d.status='posted'"""
    }
    for name, query in views.items():
        create = f"CREATE VIEW dbo.{name} AS\n{query}".replace("'", "''")
        parts.append(f"IF OBJECT_ID(N'dbo.{name}', N'V') IS NULL\n EXEC(N'{create}');\n")
    parts.append("COMMIT TRANSACTION;\nEND TRY\nBEGIN CATCH\n IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;\n THROW;\nEND CATCH;\n")
    output = "\n".join(parts)
    if re.search(r"\b(DROP|DELETE|UPDATE|TRUNCATE|MERGE|ALTER)\b", output, re.I):
        raise ValueError("脚本含非新增操作，拒绝生成")
    return output


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--check", action="store_true")
    opts = args.parse_args()
    output = build((HERE / "ef_create.sql").read_text(encoding="utf-8-sig"))
    if opts.check:
        if TARGET.read_text(encoding="utf-8") != output:
            raise SystemExit("SQL 与 EF 模型不同，请重新生成并审阅")
    else:
        TARGET.write_text(output, encoding="utf-8")
    print("v4 SQL: 18 new tables, 2 views; existing food data unchanged; " + ("checked" if opts.check else "written"))
