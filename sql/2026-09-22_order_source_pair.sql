-- 仅为 dbo.[order] 补充平台订单来源字段；不创建来源字段 CHECK 约束。
-- 完整食材系统请执行 2026-09-21_fnb_inventory_schema_review.sql。
-- 请在业务数据库中直接执行本 .sql 文件。旧订单的两列均保持 NULL。
SET XACT_ABORT ON;

IF DB_NAME() IN (N'master', N'model', N'msdb', N'tempdb')
BEGIN
    RAISERROR(N'请先选择业务数据库。', 16, 1);
    RETURN;
END;

IF OBJECT_ID(N'dbo.[order]', N'U') IS NULL
BEGIN
    RAISERROR(N'当前数据库不存在 dbo.[order] 表。', 16, 1);
    RETURN;
END;

DECLARE @existing_count INT;
SELECT @existing_count = COUNT(*)
FROM sys.columns
WHERE object_id = OBJECT_ID(N'dbo.[order]', N'U')
  AND name IN (N'order_source', N'source_order_no');

IF @existing_count = 2
BEGIN
    IF (SELECT COUNT(*) FROM sys.columns
        WHERE object_id = OBJECT_ID(N'dbo.[order]', N'U')
          AND ((name = N'order_source' AND system_type_id = 231 AND max_length = 64)
            OR (name = N'source_order_no' AND system_type_id = 231 AND max_length = 256))
          AND is_nullable = 1
          AND collation_name = N'Latin1_General_100_BIN2') <> 2
    BEGIN
        RAISERROR(N'来源字段已存在，但类型、长度、排序规则或可空性与预期不符；请检查表结构。', 16, 1);
        RETURN;
    END;

    PRINT N'来源字段已存在，无需重复执行。';
    RETURN;
END;

IF @existing_count <> 0
BEGIN
    RAISERROR(N'来源字段只存在一列；请检查表结构。', 16, 1);
    RETURN;
END;

BEGIN TRANSACTION;

ALTER TABLE [dbo].[order] ADD
    [order_source] NVARCHAR(32) COLLATE Latin1_General_100_BIN2 NULL,
    [source_order_no] NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NULL;

COMMIT TRANSACTION;
PRINT N'来源字段添加完成。';
