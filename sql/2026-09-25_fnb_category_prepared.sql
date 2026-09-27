-- 2026-09-25 食材管理：分类可标为「半成品分类」。
-- 原因：半成品由多种食材制作，但本身也是食材，应能单独成类。新增或编辑分类时选择「原料 / 半成品」；
-- 一级分类选了半成品，其下所有二级分类都算半成品分类。食材的类型（raw/prepared）由所在分类决定，不再单独选择。
--
-- 执行顺序：在 2026-09-24_fnb_item_expiry_settings.sql 之后执行本脚本，再部署同版本 SnowmeetApi。
--   新版 SnowmeetApi 读写 fnb_material_category.is_prepared，先部署会导致分类查询失败。
-- 由用户审阅后手动执行；已执行过会直接报错退出，不会重复改动。
--
-- 数据迁移：已有有效食材、且这些食材全部是半成品的二级分类，标为半成品分类；
--   混有原料和半成品的分类保持原料分类，其中的半成品食材类型不变（编辑时保留原类型）。
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
    IF COL_LENGTH(N'dbo.fnb_material_item', N'warn_days') IS NULL
        THROW 51001, N'请先执行 2026-09-24_fnb_item_expiry_settings.sql。', 1;
    IF COL_LENGTH(N'dbo.fnb_material_category', N'is_prepared') IS NOT NULL
        THROW 51002, N'本脚本已执行过：fnb_material_category.is_prepared 已存在。', 1;

    BEGIN TRANSACTION;

    ALTER TABLE [dbo].[fnb_material_category] ADD
        [is_prepared] BIT NOT NULL CONSTRAINT [DF_fnb_material_category_is_prepared] DEFAULT (0); -- 1=半成品分类；一级分类为 1 时其下二级分类都算半成品

    -- 后续语句引用新列，须用动态 SQL，避免整批编译时列尚不存在
    EXEC (N'UPDATE c
        SET is_prepared = 1, updated_at = SYSUTCDATETIME()
        FROM [dbo].[fnb_material_category] AS c
        WHERE c.level = 2
          AND EXISTS (SELECT 1 FROM [dbo].[fnb_material_item] AS i WHERE i.category_id = c.id AND i.valid = 1)
          AND NOT EXISTS (SELECT 1 FROM [dbo].[fnb_material_item] AS i WHERE i.category_id = c.id AND i.valid = 1 AND i.item_type <> ''prepared'');');

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

-- 核对（只读）：各分类类型数量，以及原料分类里仍有的半成品食材（历史数据，类型保持不变）
EXEC (N'SELECT level, is_prepared, COUNT(*) AS category_count
FROM [dbo].[fnb_material_category] WHERE valid = 1 GROUP BY level, is_prepared;');
EXEC (N'SELECT i.id, i.name, c.name AS category_name
FROM [dbo].[fnb_material_item] AS i
JOIN [dbo].[fnb_material_category] AS c ON c.id = i.category_id
LEFT JOIN [dbo].[fnb_material_category] AS p ON p.id = c.parent_id
WHERE i.valid = 1 AND i.item_type = ''prepared'' AND c.is_prepared = 0 AND ISNULL(p.is_prepared, 0) = 0;');
