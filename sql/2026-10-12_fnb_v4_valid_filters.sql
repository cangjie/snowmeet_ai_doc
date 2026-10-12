-- 食材管理 v4：唯一索引和视图只看有效行，2026-10-12。配合接口对后补 valid 的表做逻辑删除。
-- 先执行 2026-10-12_fnb_v4_add_valid.sql。本脚本只做两件事，不改表、列和数据，可重复执行：
--   1. 重建 5 个唯一索引，加上 valid = 1 条件：批号、检查单日期、外部订单号、订单导入去重键、工具资产编号。
--      这些键在逻辑删除后可以重新使用；其余唯一索引都以上级记录的 id 开头，上级重建后 id 不同，不需要改。
--   2. 更新 vw_fnb_v4_stock、vw_fnb_v4_loss 两个视图，统计时排除 valid = 0 的行。
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRY
BEGIN TRANSACTION;
IF COL_LENGTH(N'dbo.fnb_v4_batch',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation',N'valid') IS NULL
 THROW 51000,N'请先执行 2026-10-12_fnb_v4_add_valid.sql。',1;

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_batch') AND name=N'IX_fnb_v4_batch_shop_id_batch_no' AND has_filter=1)
BEGIN
 IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_batch') AND name=N'IX_fnb_v4_batch_shop_id_batch_no')
  DROP INDEX [IX_fnb_v4_batch_shop_id_batch_no] ON [dbo].[fnb_v4_batch];
 EXEC(N'CREATE UNIQUE INDEX [IX_fnb_v4_batch_shop_id_batch_no] ON [dbo].[fnb_v4_batch] ([shop_id], [batch_no]) WHERE [valid] = 1');
END

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_sheet') AND name=N'IX_fnb_v4_check_sheet_shop_id_business_date' AND has_filter=1)
BEGIN
 IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_sheet') AND name=N'IX_fnb_v4_check_sheet_shop_id_business_date')
  DROP INDEX [IX_fnb_v4_check_sheet_shop_id_business_date] ON [dbo].[fnb_v4_check_sheet];
 EXEC(N'CREATE UNIQUE INDEX [IX_fnb_v4_check_sheet_shop_id_business_date] ON [dbo].[fnb_v4_check_sheet] ([shop_id], [business_date]) WHERE [valid] = 1');
END

-- 这个索引原来就有 external_order_no IS NOT NULL 条件，所以按条件内容判断是否已更新。
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_order') AND name=N'IX_fnb_v4_order_shop_id_source_type_external_order_no' AND filter_definition LIKE N'%valid%')
BEGIN
 IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_order') AND name=N'IX_fnb_v4_order_shop_id_source_type_external_order_no')
  DROP INDEX [IX_fnb_v4_order_shop_id_source_type_external_order_no] ON [dbo].[fnb_v4_order];
 EXEC(N'CREATE UNIQUE INDEX [IX_fnb_v4_order_shop_id_source_type_external_order_no] ON [dbo].[fnb_v4_order] ([shop_id], [source_type], [external_order_no]) WHERE [valid] = 1 AND [external_order_no] IS NOT NULL');
END

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_order_import') AND name=N'IX_fnb_v4_order_import_shop_id_source_method_dedupe_key' AND has_filter=1)
BEGIN
 IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_order_import') AND name=N'IX_fnb_v4_order_import_shop_id_source_method_dedupe_key')
  DROP INDEX [IX_fnb_v4_order_import_shop_id_source_method_dedupe_key] ON [dbo].[fnb_v4_order_import];
 EXEC(N'CREATE UNIQUE INDEX [IX_fnb_v4_order_import_shop_id_source_method_dedupe_key] ON [dbo].[fnb_v4_order_import] ([shop_id], [source_method], [dedupe_key]) WHERE [valid] = 1');
END

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_tool') AND name=N'IX_fnb_v4_tool_shop_id_asset_no' AND has_filter=1)
BEGIN
 IF EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_tool') AND name=N'IX_fnb_v4_tool_shop_id_asset_no')
  DROP INDEX [IX_fnb_v4_tool_shop_id_asset_no] ON [dbo].[fnb_v4_tool];
 EXEC(N'CREATE UNIQUE INDEX [IX_fnb_v4_tool_shop_id_asset_no] ON [dbo].[fnb_v4_tool] ([shop_id], [asset_no]) WHERE [valid] = 1');
END

EXEC(N'CREATE OR ALTER VIEW dbo.vw_fnb_v4_stock AS
SELECT b.shop_id,b.item_id,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state=''final'' AND b.dispose_status IS NULL
  AND b.effective_expire >= CONVERT(date,SYSUTCDATETIME() AT TIME ZONE ''UTC'' AT TIME ZONE ''China Standard Time'')
  AND (b.ready_at IS NULL OR b.ready_at <= SYSUTCDATETIME()) THEN b.quantity ELSE 0 END)) AS available_qty,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state=''staged'' AND b.dispose_status IS NULL THEN b.quantity ELSE 0 END)) AS staged_qty,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state=''sealed'' AND b.dispose_status IS NULL THEN b.quantity ELSE 0 END)) AS sealed_qty,
 CONVERT(decimal(19,6),SUM(b.quantity)) AS total_qty,CONVERT(decimal(19,6),SUM(b.amount)) AS total_amount,
 CONVERT(decimal(19,6),SUM(b.amount)/NULLIF(SUM(b.quantity),0)) AS average_unit_cost
FROM dbo.fnb_v4_batch b WHERE b.valid=1 GROUP BY b.shop_id,b.item_id');

EXEC(N'CREATE OR ALTER VIEW dbo.vw_fnb_v4_loss AS
SELECT m.id AS source_id,d.document_type AS source_type,m.shop_id,m.item_id,d.business_date,
 CONVERT(decimal(19,6),-m.delta_qty) AS loss_qty,CONVERT(decimal(19,6),-m.delta_amount) AS loss_amount
FROM dbo.fnb_v4_stock_movement m
JOIN dbo.fnb_v4_stock_document_line l ON l.id=m.document_line_id
JOIN dbo.fnb_v4_stock_document d ON d.id=l.document_id
WHERE d.status=''posted'' AND d.document_type IN (''waste'',''destroy'',''stocktake'') AND m.valid=1 AND l.valid=1 AND d.valid=1
UNION ALL
SELECT o.id,''op'',d.shop_id,o.item_id,d.business_date,o.loss_base_qty,
 CONVERT(decimal(19,6),o.loss_base_qty * COALESCE(c.amount/NULLIF(c.qty,0),0))
FROM dbo.fnb_v4_stock_operation o JOIN dbo.fnb_v4_stock_document d ON d.id=o.document_id
OUTER APPLY (SELECT SUM(m.amount) AS amount,SUM(m.quantity) AS qty
 FROM dbo.fnb_v4_stock_movement m JOIN dbo.fnb_v4_stock_document_line l ON l.id=m.document_line_id
 WHERE l.document_id=o.document_id AND m.batch_id=o.source_batch_id AND m.direction=-1 AND m.valid=1 AND l.valid=1) c
WHERE d.status=''posted'' AND o.valid=1 AND d.valid=1');

COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
