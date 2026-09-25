-- 2026-09-24 食材管理：二级分类只保留「名称 + 建议储存方式」，
-- 计量单位、临期提前提醒、封装品开封后默认、未开封保质期规则全部下沉到具体食材。
-- 原因：同一个二级分类下的食材包装规格各不相同（如速冻饺子有散装、有成袋），这些属性属于食材而不是分类。
--
-- 执行顺序：先在业务库执行本脚本，再立即部署同版本 SnowmeetApi。
--   本脚本删除 fnb_material_category 的 4 列，旧版 SnowmeetApi 查询分类会失败；新版 SnowmeetApi 依赖本脚本新增的列。
-- 由用户审阅后手动执行；可重复检查：已执行过会直接报错退出，不会重复改动。
--
-- 数据迁移：
--   1. fnb_material_item 新增 warn_days / default_open_storage / default_open_days，取值复制自所属二级分类；
--   2. fnb_shelf_life_rule 新增 item_id，category_id 改为可空；每条启用中的分类规则复制给该分类下的每个食材，
--      原分类规则置为停用（不删除：已入库批次的 shelf_life_rule_id 仍引用它们）；
--   3. fnb_material_category 删除 default_unit_code / warn_days / default_open_storage / default_open_days。
--   fnb_material_batch_stock.expiry_source 的取值 'category' 保持不变，含义改为「按食材保质期规则计算」。
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
    IF OBJECT_ID(N'dbo.fnb_material_item', N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_shelf_life_rule', N'U') IS NULL
        THROW 51001, N'食材管理表不存在，请先执行 2026-09-22_fnb_inventory_other_tables.sql。', 1;
    IF COL_LENGTH(N'dbo.fnb_material_item', N'warn_days') IS NOT NULL
        THROW 51002, N'本脚本已执行过：fnb_material_item.warn_days 已存在。', 1;

    BEGIN TRANSACTION;

    -- 1. 食材档案新增三列（后续语句引用新列，须用动态 SQL，避免整批编译时列尚不存在）
    ALTER TABLE [dbo].[fnb_material_item] ADD
        [warn_days] INT NOT NULL CONSTRAINT [DF_fnb_material_item_warn_days] DEFAULT (1), -- 临期提前提醒天数；入库时复制到批次
        [default_open_storage] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL, -- 封装品开封后默认储存：ambient/chilled/frozen；空=入库时再选
        [default_open_days] INT NULL; -- 封装品开封后默认天数；0=开封当日到期，空=没有默认值

    EXEC (N'ALTER TABLE [dbo].[fnb_material_item] ADD
        CONSTRAINT [CK_fnb_material_item_3] CHECK (warn_days >= 0),
        CONSTRAINT [CK_fnb_material_item_4] CHECK (default_open_storage IS NULL OR default_open_storage IN (''ambient'',''chilled'',''frozen'')),
        CONSTRAINT [CK_fnb_material_item_5] CHECK (default_open_days IS NULL OR default_open_days >= 0);');

    EXEC (N'UPDATE i
        SET warn_days = ISNULL(c.warn_days, 1),
            default_open_storage = c.default_open_storage,
            default_open_days = c.default_open_days,
            updated_at = SYSUTCDATETIME()
        FROM [dbo].[fnb_material_item] AS i
        JOIN [dbo].[fnb_material_category] AS c ON c.id = i.category_id;');

    -- 2. 保质期规则改挂食材：category_id 所在的唯一索引和外键须先移除，才能改为可空
    DROP INDEX [IX_fnb_shelf_life_rule_active_rule] ON [dbo].[fnb_shelf_life_rule];
    ALTER TABLE [dbo].[fnb_shelf_life_rule] DROP CONSTRAINT [FK_fnb_shelf_life_rule_1];
    ALTER TABLE [dbo].[fnb_shelf_life_rule] ALTER COLUMN [category_id] INT NULL; -- 仅历史分类规则有值
    ALTER TABLE [dbo].[fnb_shelf_life_rule] ADD [item_id] INT NULL; -- 食材 ID；新规则只挂食材
    ALTER TABLE [dbo].[fnb_shelf_life_rule] WITH CHECK ADD CONSTRAINT [FK_fnb_shelf_life_rule_1]
        FOREIGN KEY ([category_id]) REFERENCES [dbo].[fnb_material_category] ([id]);

    EXEC (N'ALTER TABLE [dbo].[fnb_shelf_life_rule] WITH CHECK ADD CONSTRAINT [FK_fnb_shelf_life_rule_2]
        FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_material_item] ([id]);');
    EXEC (N'ALTER TABLE [dbo].[fnb_shelf_life_rule] WITH CHECK ADD CONSTRAINT [CK_fnb_shelf_life_rule_5]
        CHECK ((item_id IS NOT NULL AND category_id IS NULL) OR (item_id IS NULL AND category_id IS NOT NULL));');

    EXEC (N'INSERT INTO [dbo].[fnb_shelf_life_rule]
            ([item_id], [category_id], [storage_type], [production_month], [shelf_life_value], [shelf_life_unit], [remark], [valid])
        SELECT i.id, NULL, r.storage_type, r.production_month, r.shelf_life_value, r.shelf_life_unit, r.remark, 1
        FROM [dbo].[fnb_shelf_life_rule] AS r
        JOIN [dbo].[fnb_material_item] AS i ON i.category_id = r.category_id
        WHERE r.valid = 1 AND r.category_id IS NOT NULL;');

    EXEC (N'UPDATE [dbo].[fnb_shelf_life_rule]
        SET valid = 0, updated_at = SYSUTCDATETIME()
        WHERE category_id IS NOT NULL AND valid = 1;');

    EXEC (N'CREATE UNIQUE INDEX [IX_fnb_shelf_life_rule_active_item_rule] ON [dbo].[fnb_shelf_life_rule]
        ([item_id], [storage_type], [production_month]) WHERE valid = 1 AND item_id IS NOT NULL;');

    -- 3. 二级分类只保留建议储存方式
    ALTER TABLE [dbo].[fnb_material_category] DROP CONSTRAINT [CK_fnb_material_category_3];
    ALTER TABLE [dbo].[fnb_material_category] DROP CONSTRAINT [CK_fnb_material_category_4];
    ALTER TABLE [dbo].[fnb_material_category] DROP CONSTRAINT [CK_fnb_material_category_5];
    ALTER TABLE [dbo].[fnb_material_category] DROP CONSTRAINT [FK_fnb_material_category_2];
    ALTER TABLE [dbo].[fnb_material_category] DROP COLUMN [default_unit_code], [warn_days], [default_open_storage], [default_open_days];
    ALTER TABLE [dbo].[fnb_material_category] WITH CHECK ADD CONSTRAINT [CK_fnb_material_category_3]
        CHECK ((level = 1 AND default_storage IS NULL) OR (level = 2 AND default_storage IS NOT NULL AND default_storage IN ('ambient','chilled','frozen')));

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

-- 4. 核对（只读；同样用动态 SQL，整批编译时新列尚不存在）
EXEC (N'SELECT COUNT(*) AS item_count,
       SUM(CASE WHEN default_open_days IS NOT NULL THEN 1 ELSE 0 END) AS items_with_open_days
FROM [dbo].[fnb_material_item];');
EXEC (N'SELECT CASE WHEN item_id IS NOT NULL THEN ''item'' ELSE ''category'' END AS owner, valid, COUNT(*) AS rule_count
FROM [dbo].[fnb_shelf_life_rule]
GROUP BY CASE WHEN item_id IS NOT NULL THEN ''item'' ELSE ''category'' END, valid;');
