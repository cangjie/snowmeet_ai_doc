-- 2026-09-26 食材管理：用量预警（库存低提醒）。
-- 规则：可用量（未开封 + 已开封 + 散装 + 自制，不含过期、已报损、已处理）降到预警线及以下时提醒。
--   预警线默认 = 最近一次入库或制作的数量 × 10%；每种食材可改比例（low_stock_ratio），或直接填数量（low_stock_qty，基本单位 g / ml / 个）。
--   两列都为空 = 默认 10%；两列不同时有值。
--
-- 执行顺序：在 2026-09-25_fnb_category_prepared.sql 之后执行本脚本，再部署同版本 SnowmeetApi。
--   新版 SnowmeetApi 读写这两列，先部署会导致食材查询失败。
-- 由用户审阅后手动执行；已执行过会直接报错退出，不会重复改动。
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET NUMERIC_ROUNDABORT OFF;

BEGIN TRY
    IF DB_NAME() IN (N'master', N'model', N'msdb', N'tempdb')
        THROW 51000, N'请先选择业务数据库，不能在系统数据库执行。', 1;
    IF COL_LENGTH(N'dbo.fnb_material_category', N'is_prepared') IS NULL
        THROW 51001, N'请先执行 2026-09-25_fnb_category_prepared.sql。', 1;
    IF COL_LENGTH(N'dbo.fnb_material_item', N'low_stock_ratio') IS NOT NULL
        THROW 51002, N'本脚本已执行过：fnb_material_item.low_stock_ratio 已存在。', 1;

    BEGIN TRANSACTION;

    ALTER TABLE [dbo].[fnb_material_item] ADD
        [low_stock_ratio] DECIMAL(5, 4) NULL,   -- 预警比例（0 < 比例 <= 1），乘最近一次入库或制作的数量；空且未填数量 = 默认 0.1
        [low_stock_qty] DECIMAL(18, 6) NULL;    -- 预警数量（基本单位，>= 0）；填了就不按比例

    -- 约束引用新列，须用动态 SQL，避免整批编译时列尚不存在
    EXEC (N'ALTER TABLE [dbo].[fnb_material_item] ADD CONSTRAINT [CK_fnb_material_item_low_stock] CHECK (
        (low_stock_ratio IS NULL OR (low_stock_ratio > 0 AND low_stock_ratio <= 1))
        AND (low_stock_qty IS NULL OR low_stock_qty >= 0)
        AND (low_stock_ratio IS NULL OR low_stock_qty IS NULL));');

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

-- 核对（只读）：新列存在，且现有食材全部按默认 10%
EXEC (N'SELECT COUNT(*) AS item_count,
    SUM(CASE WHEN low_stock_ratio IS NULL AND low_stock_qty IS NULL THEN 1 ELSE 0 END) AS default_count
FROM [dbo].[fnb_material_item];');
