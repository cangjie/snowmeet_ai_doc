-- 食材管理 v4：给原本没有 valid 列的 21 张表补上 valid，2026-10-12。
-- 用户决定 v4 全部表都能逻辑删除。本脚本只新增列，默认值 1，已有行全部为有效；
-- 不改已有列、索引、视图或数据，不删除任何对象。可重复执行。
-- 先执行 2026-10-06 的两份 v4 建表脚本。唯一索引和视图是否只看有效行，随接口改动另行处理。
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRY
BEGIN TRANSACTION;
IF OBJECT_ID(N'dbo.fnb_v4_alert_delivery',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_area_image',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_batch',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_batch_detail',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_batch_image',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_check_handling',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_check_line',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_check_sheet',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_order',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_order_import',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_order_line',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_recipe',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_recipe_line',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_request',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_stock_document',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_stock_document_line',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_stock_movement',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_stock_operation',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_stocktake_line',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_supply_movement',N'U') IS NULL OR OBJECT_ID(N'dbo.fnb_v4_tool_log',N'U') IS NULL
 THROW 51000,N'v4 表不完整，请先执行 2026-10-06 的两份 v4 建表脚本。',1;

IF COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_alert_delivery] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_area_image',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_area_image] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_batch',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_batch] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_batch_detail',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_batch_detail] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_batch_image',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_batch_image] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_check_handling',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_check_handling] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_check_line',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_check_line] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_check_sheet] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_order',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_order] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_order_import',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_order_import] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_order_line',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_order_line] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_recipe',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_recipe] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_recipe_line',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_recipe_line] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_request',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_request] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_stock_document',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_stock_document] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_stock_document_line',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_stock_document_line] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_stock_movement',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_stock_movement] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_stock_operation',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_stock_operation] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_stocktake_line',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_stocktake_line] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_supply_movement] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

IF COL_LENGTH(N'dbo.fnb_v4_tool_log',N'valid') IS NULL
 ALTER TABLE [dbo].[fnb_v4_tool_log] ADD [valid] bit NOT NULL DEFAULT CAST(1 AS bit);

COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
