-- 食材管理建表结果只读核对。仅查询当前数据库的系统目录和 fnb_unit，不修改业务数据。
-- 在执行建表脚本的同一个业务数据库运行。第二个结果集为各类计数；第三个结果集若为空，表示本脚本覆盖的检查项全部匹配。
SET NOCOUNT ON;
DECLARE @check TABLE (category NVARCHAR(30), item NVARCHAR(200), is_ok BIT, detail NVARCHAR(300));
SELECT DB_NAME() AS database_name,
       CONVERT(VARCHAR(30), SERVERPROPERTY('ProductVersion')) AS server_version,
       CONVERT(VARCHAR(128), DATABASEPROPERTYEX(DB_NAME(), 'Collation')) AS database_collation;

;WITH expected(table_name, column_count) AS (
    SELECT * FROM (VALUES
    (N'fnb_unit', 6),
    (N'fnb_material_category', 13),
    (N'fnb_shelf_life_rule', 10),
    (N'fnb_material_item', 12),
    (N'fnb_material_batch_stock', 25),
    (N'fnb_dish_spec', 11),
    (N'fnb_recipe', 13),
    (N'fnb_recipe_line', 6),
    (N'fnb_channel_shop', 11),
    (N'fnb_channel_dish_map', 12),
    (N'fnb_order', 21),
    (N'fnb_order_line', 17),
    (N'fnb_order_import', 14),
    (N'fnb_stock_document', 19),
    (N'fnb_stock_document_line', 17),
    (N'fnb_stock_movement', 13),
    (N'fnb_stocktake_line', 15)
    ) AS x(table_name, column_count)
)
INSERT INTO @check(category,item,is_ok,detail)
SELECT N'表', e.table_name,
       CASE WHEN t.object_id IS NOT NULL AND (SELECT COUNT(*) FROM sys.columns AS c WHERE c.object_id=t.object_id)=e.column_count THEN 1 ELSE 0 END,
       CASE WHEN t.object_id IS NULL THEN N'缺少表' ELSE N'字段总数应为 '+CONVERT(NVARCHAR(12),e.column_count)+N'，实际 '+CONVERT(NVARCHAR(12),(SELECT COUNT(*) FROM sys.columns AS c WHERE c.object_id=t.object_id)) END
FROM expected AS e
LEFT JOIN sys.tables AS t ON t.schema_id=SCHEMA_ID(N'dbo') AND t.name=e.table_name;

;WITH expected(table_name,column_name,max_length,collation_name) AS (
    SELECT * FROM (VALUES
    (N'fnb_unit', N'code', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_unit', N'name', 40, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_category', N'name', 100, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_category', N'default_storage', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_category', N'default_unit_code', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_category', N'default_open_storage', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_shelf_life_rule', N'storage_type', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_shelf_life_rule', N'shelf_life_unit', 10, N'Chinese_PRC_CI_AS'),
    (N'fnb_shelf_life_rule', N'remark', 600, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_item', N'code', 64, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_item', N'name', 200, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_item', N'item_type', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_item', N'base_unit_code', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_item', N'default_input_unit_code', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_item', N'remark', 1000, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_batch_stock', N'stock_form', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_batch_stock', N'storage_type', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_batch_stock', N'storage_location', 200, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_batch_stock', N'pack_unit_name', 40, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_batch_stock', N'open_storage_type', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_batch_stock', N'expiry_source', 24, N'Chinese_PRC_CI_AS'),
    (N'fnb_material_batch_stock', N'expiry_note', 1000, N'Chinese_PRC_CI_AS'),
    (N'fnb_dish_spec', N'spec_code', 64, N'Chinese_PRC_CI_AS'),
    (N'fnb_dish_spec', N'name', 100, N'Chinese_PRC_CI_AS'),
    (N'fnb_recipe', N'recipe_type', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_recipe', N'status', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_recipe', N'remark', 1000, N'Chinese_PRC_CI_AS'),
    (N'fnb_recipe_line', N'remark', 600, N'Chinese_PRC_CI_AS'),
    (N'fnb_channel_shop', N'platform', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_channel_shop', N'external_shop_id', 128, N'Chinese_PRC_BIN2'),
    (N'fnb_channel_shop', N'external_shop_name', 200, N'Chinese_PRC_CI_AS'),
    (N'fnb_channel_shop', N'preferred_method', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_channel_shop', N'last_error', 1000, N'Chinese_PRC_CI_AS'),
    (N'fnb_channel_dish_map', N'external_sku_key', 256, N'Chinese_PRC_BIN2'),
    (N'fnb_channel_dish_map', N'option_key', 256, N'Chinese_PRC_BIN2'),
    (N'fnb_channel_dish_map', N'external_name', 300, N'Chinese_PRC_CI_AS'),
    (N'fnb_channel_dish_map', N'options_text', 2000, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'source_type', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'external_order_no', 256, N'Chinese_PRC_BIN2'),
    (N'fnb_order', N'display_no', 128, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'table_no', 100, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'order_status', 24, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'platform_status', 100, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'refund_status', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'review_status', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_order', N'remark', 2000, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_line', N'line_key', 256, N'Chinese_PRC_BIN2'),
    (N'fnb_order_line', N'external_sku_key', 256, N'Chinese_PRC_BIN2'),
    (N'fnb_order_line', N'option_key', 256, N'Chinese_PRC_BIN2'),
    (N'fnb_order_line', N'item_name', 300, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_line', N'spec_name', 200, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_line', N'options_text', 2000, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_line', N'remark', 1000, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_import', N'source_method', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_import', N'dedupe_key', 256, N'Chinese_PRC_BIN2'),
    (N'fnb_order_import', N'raw_content', -1, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_import', N'parsed_content', -1, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_import', N'process_status', 24, N'Chinese_PRC_CI_AS'),
    (N'fnb_order_import', N'error_message', 2000, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document', N'document_no', 80, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document', N'document_type', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document', N'status', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document', N'source_client', 20, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document', N'reason_code', 32, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document', N'reference_no', 200, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document', N'remark', 2000, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document_line', N'item_name', 200, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document_line', N'input_unit_name', 40, N'Chinese_PRC_CI_AS'),
    (N'fnb_stock_document_line', N'remark', 1000, N'Chinese_PRC_CI_AS'),
    (N'fnb_stocktake_line', N'remark', 1000, N'Chinese_PRC_CI_AS')
    ) AS x(table_name,column_name,max_length,collation_name)
)
INSERT INTO @check(category,item,is_ok,detail)
SELECT N'VARCHAR字段', e.table_name+N'.'+e.column_name,
       CASE WHEN c.system_type_id=167 AND c.max_length=e.max_length AND c.collation_name=e.collation_name THEN 1 ELSE 0 END,
       CASE WHEN c.column_id IS NULL THEN N'缺少字段' ELSE N'应为 VARCHAR('+CASE WHEN e.max_length=-1 THEN N'MAX' ELSE CONVERT(NVARCHAR(12),e.max_length) END+N') COLLATE '+e.collation_name+N'；实际 type_id='+CONVERT(NVARCHAR(12),c.system_type_id)+N', max_length='+CONVERT(NVARCHAR(12),c.max_length)+N', collation='+ISNULL(c.collation_name,N'NULL') END
FROM expected AS e
LEFT JOIN sys.tables AS t ON t.schema_id=SCHEMA_ID(N'dbo') AND t.name=e.table_name
LEFT JOIN sys.columns AS c ON c.object_id=t.object_id AND c.name=e.column_name;

;WITH expected(table_name,constraint_name) AS (
    SELECT * FROM (VALUES
    (N'fnb_material_category', N'FK_fnb_material_category_1'),
    (N'fnb_material_category', N'FK_fnb_material_category_2'),
    (N'fnb_shelf_life_rule', N'FK_fnb_shelf_life_rule_1'),
    (N'fnb_material_item', N'FK_fnb_material_item_1'),
    (N'fnb_material_item', N'FK_fnb_material_item_2'),
    (N'fnb_material_item', N'FK_fnb_material_item_3'),
    (N'fnb_material_item', N'FK_fnb_material_item_4'),
    (N'fnb_material_batch_stock', N'FK_fnb_material_batch_stock_1'),
    (N'fnb_material_batch_stock', N'FK_fnb_material_batch_stock_2'),
    (N'fnb_material_batch_stock', N'FK_fnb_material_batch_stock_3'),
    (N'fnb_material_batch_stock', N'FK_fnb_material_batch_stock_4'),
    (N'fnb_material_batch_stock', N'FK_fnb_material_batch_stock_5'),
    (N'fnb_dish_spec', N'FK_fnb_dish_spec_1'),
    (N'fnb_dish_spec', N'FK_fnb_dish_spec_2'),
    (N'fnb_dish_spec', N'FK_fnb_dish_spec_3'),
    (N'fnb_recipe', N'FK_fnb_recipe_1'),
    (N'fnb_recipe', N'FK_fnb_recipe_2'),
    (N'fnb_recipe', N'FK_fnb_recipe_3'),
    (N'fnb_recipe', N'FK_fnb_recipe_4'),
    (N'fnb_recipe_line', N'FK_fnb_recipe_line_1'),
    (N'fnb_recipe_line', N'FK_fnb_recipe_line_2'),
    (N'fnb_channel_shop', N'FK_fnb_channel_shop_1'),
    (N'fnb_channel_dish_map', N'FK_fnb_channel_dish_map_1'),
    (N'fnb_channel_dish_map', N'FK_fnb_channel_dish_map_2'),
    (N'fnb_channel_dish_map', N'FK_fnb_channel_dish_map_3'),
    (N'fnb_order', N'FK_fnb_order_1'),
    (N'fnb_order', N'FK_fnb_order_2'),
    (N'fnb_order', N'FK_fnb_order_3'),
    (N'fnb_order_line', N'FK_fnb_order_line_1'),
    (N'fnb_order_line', N'FK_fnb_order_line_2'),
    (N'fnb_order_line', N'FK_fnb_order_line_3'),
    (N'fnb_order_line', N'FK_fnb_order_line_4'),
    (N'fnb_order_line', N'FK_fnb_order_line_5'),
    (N'fnb_order_import', N'FK_fnb_order_import_1'),
    (N'fnb_order_import', N'FK_fnb_order_import_2'),
    (N'fnb_order_import', N'FK_fnb_order_import_3'),
    (N'fnb_order_import', N'FK_fnb_order_import_4'),
    (N'fnb_order_import', N'FK_fnb_order_import_5'),
    (N'fnb_stock_document', N'FK_fnb_stock_document_1'),
    (N'fnb_stock_document', N'FK_fnb_stock_document_2'),
    (N'fnb_stock_document', N'FK_fnb_stock_document_3'),
    (N'fnb_stock_document', N'FK_fnb_stock_document_4'),
    (N'fnb_stock_document', N'FK_fnb_stock_document_5'),
    (N'fnb_stock_document_line', N'FK_fnb_stock_document_line_1'),
    (N'fnb_stock_document_line', N'FK_fnb_stock_document_line_2'),
    (N'fnb_stock_document_line', N'FK_fnb_stock_document_line_3'),
    (N'fnb_stock_movement', N'FK_fnb_stock_movement_1'),
    (N'fnb_stock_movement', N'FK_fnb_stock_movement_2'),
    (N'fnb_stocktake_line', N'FK_fnb_stocktake_line_1'),
    (N'fnb_stocktake_line', N'FK_fnb_stocktake_line_2'),
    (N'fnb_stocktake_line', N'FK_fnb_stocktake_line_3'),
    (N'fnb_stocktake_line', N'FK_fnb_stocktake_line_4'),
    (N'fnb_stocktake_line', N'FK_fnb_stocktake_line_5')
    ) AS x(table_name,constraint_name)
)
INSERT INTO @check(category,item,is_ok,detail)
SELECT N'外键', e.constraint_name,
       CASE WHEN k.object_id IS NOT NULL AND k.is_disabled=0 AND k.is_not_trusted=0 THEN 1 ELSE 0 END,
       CASE WHEN k.object_id IS NULL THEN N'缺少约束' WHEN k.is_disabled=1 THEN N'约束已禁用' WHEN k.is_not_trusted=1 THEN N'约束未受信任' ELSE N'正常' END
FROM expected AS e
LEFT JOIN sys.tables AS t ON t.schema_id=SCHEMA_ID(N'dbo') AND t.name=e.table_name
LEFT JOIN sys.foreign_keys AS k ON k.parent_object_id=t.object_id AND k.name=e.constraint_name;

;WITH expected(table_name,constraint_name) AS (
    SELECT * FROM (VALUES
    (N'fnb_unit', N'CK_fnb_unit_1'),
    (N'fnb_unit', N'CK_fnb_unit_2'),
    (N'fnb_material_category', N'CK_fnb_material_category_1'),
    (N'fnb_material_category', N'CK_fnb_material_category_2'),
    (N'fnb_material_category', N'CK_fnb_material_category_3'),
    (N'fnb_material_category', N'CK_fnb_material_category_4'),
    (N'fnb_material_category', N'CK_fnb_material_category_5'),
    (N'fnb_shelf_life_rule', N'CK_fnb_shelf_life_rule_1'),
    (N'fnb_shelf_life_rule', N'CK_fnb_shelf_life_rule_2'),
    (N'fnb_shelf_life_rule', N'CK_fnb_shelf_life_rule_3'),
    (N'fnb_shelf_life_rule', N'CK_fnb_shelf_life_rule_4'),
    (N'fnb_material_item', N'CK_fnb_material_item_1'),
    (N'fnb_material_item', N'CK_fnb_material_item_2'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_1'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_2'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_3'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_4'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_5'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_6'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_7'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_8'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_9'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_10'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_11'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_12'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_13'),
    (N'fnb_material_batch_stock', N'CK_fnb_material_batch_stock_14'),
    (N'fnb_dish_spec', N'CK_fnb_dish_spec_1'),
    (N'fnb_recipe', N'CK_fnb_recipe_1'),
    (N'fnb_recipe', N'CK_fnb_recipe_2'),
    (N'fnb_recipe', N'CK_fnb_recipe_3'),
    (N'fnb_recipe', N'CK_fnb_recipe_4'),
    (N'fnb_recipe_line', N'CK_fnb_recipe_line_1'),
    (N'fnb_channel_shop', N'CK_fnb_channel_shop_1'),
    (N'fnb_channel_shop', N'CK_fnb_channel_shop_2'),
    (N'fnb_order', N'CK_fnb_order_1'),
    (N'fnb_order', N'CK_fnb_order_2'),
    (N'fnb_order', N'CK_fnb_order_3'),
    (N'fnb_order', N'CK_fnb_order_4'),
    (N'fnb_order', N'CK_fnb_order_5'),
    (N'fnb_order', N'CK_fnb_order_6'),
    (N'fnb_order_line', N'CK_fnb_order_line_1'),
    (N'fnb_order_line', N'CK_fnb_order_line_2'),
    (N'fnb_order_line', N'CK_fnb_order_line_3'),
    (N'fnb_order_line', N'CK_fnb_order_line_4'),
    (N'fnb_order_import', N'CK_fnb_order_import_1'),
    (N'fnb_order_import', N'CK_fnb_order_import_2'),
    (N'fnb_order_import', N'CK_fnb_order_import_3'),
    (N'fnb_order_import', N'CK_fnb_order_import_4'),
    (N'fnb_order_import', N'CK_fnb_order_import_5'),
    (N'fnb_order_import', N'CK_fnb_order_import_6'),
    (N'fnb_stock_document', N'CK_fnb_stock_document_1'),
    (N'fnb_stock_document', N'CK_fnb_stock_document_2'),
    (N'fnb_stock_document', N'CK_fnb_stock_document_3'),
    (N'fnb_stock_document', N'CK_fnb_stock_document_4'),
    (N'fnb_stock_document', N'CK_fnb_stock_document_5'),
    (N'fnb_stock_document', N'CK_fnb_stock_document_6'),
    (N'fnb_stock_document', N'CK_fnb_stock_document_7'),
    (N'fnb_stock_document_line', N'CK_fnb_stock_document_line_1'),
    (N'fnb_stock_document_line', N'CK_fnb_stock_document_line_2'),
    (N'fnb_stock_document_line', N'CK_fnb_stock_document_line_3'),
    (N'fnb_stock_document_line', N'CK_fnb_stock_document_line_4'),
    (N'fnb_stock_document_line', N'CK_fnb_stock_document_line_5'),
    (N'fnb_stock_document_line', N'CK_fnb_stock_document_line_6'),
    (N'fnb_stock_document_line', N'CK_fnb_stock_document_line_7'),
    (N'fnb_stock_movement', N'CK_fnb_stock_movement_1'),
    (N'fnb_stock_movement', N'CK_fnb_stock_movement_2'),
    (N'fnb_stock_movement', N'CK_fnb_stock_movement_3'),
    (N'fnb_stocktake_line', N'CK_fnb_stocktake_line_1'),
    (N'fnb_stocktake_line', N'CK_fnb_stocktake_line_2'),
    (N'fnb_stocktake_line', N'CK_fnb_stocktake_line_3')
    ) AS x(table_name,constraint_name)
)
INSERT INTO @check(category,item,is_ok,detail)
SELECT N'CHECK', e.constraint_name,
       CASE WHEN k.object_id IS NOT NULL AND k.is_disabled=0 AND k.is_not_trusted=0 THEN 1 ELSE 0 END,
       CASE WHEN k.object_id IS NULL THEN N'缺少约束' WHEN k.is_disabled=1 THEN N'约束已禁用' WHEN k.is_not_trusted=1 THEN N'约束未受信任' ELSE N'正常' END
FROM expected AS e
LEFT JOIN sys.tables AS t ON t.schema_id=SCHEMA_ID(N'dbo') AND t.name=e.table_name
LEFT JOIN sys.check_constraints AS k ON k.parent_object_id=t.object_id AND k.name=e.constraint_name;

;WITH expected(table_name,index_name,is_unique) AS (
    SELECT * FROM (VALUES
    (N'fnb_unit', N'PK_fnb_unit', 1),
    (N'fnb_material_category', N'PK_fnb_material_category', 1),
    (N'fnb_shelf_life_rule', N'PK_fnb_shelf_life_rule', 1),
    (N'fnb_material_item', N'PK_fnb_material_item', 1),
    (N'fnb_material_item', N'UQ_fnb_material_item_1', 1),
    (N'fnb_material_batch_stock', N'PK_fnb_material_batch_stock', 1),
    (N'fnb_material_batch_stock', N'UQ_fnb_material_batch_stock_1', 1),
    (N'fnb_dish_spec', N'PK_fnb_dish_spec', 1),
    (N'fnb_dish_spec', N'UQ_fnb_dish_spec_1', 1),
    (N'fnb_dish_spec', N'UQ_fnb_dish_spec_2', 1),
    (N'fnb_recipe', N'PK_fnb_recipe', 1),
    (N'fnb_recipe', N'UQ_fnb_recipe_1', 1),
    (N'fnb_recipe', N'UQ_fnb_recipe_2', 1),
    (N'fnb_recipe_line', N'PK_fnb_recipe_line', 1),
    (N'fnb_recipe_line', N'UQ_fnb_recipe_line_1', 1),
    (N'fnb_channel_shop', N'PK_fnb_channel_shop', 1),
    (N'fnb_channel_shop', N'UQ_fnb_channel_shop_1', 1),
    (N'fnb_channel_shop', N'UQ_fnb_channel_shop_2', 1),
    (N'fnb_channel_dish_map', N'PK_fnb_channel_dish_map', 1),
    (N'fnb_channel_dish_map', N'UQ_fnb_channel_dish_map_1', 1),
    (N'fnb_order', N'PK_fnb_order', 1),
    (N'fnb_order', N'UQ_fnb_order_1', 1),
    (N'fnb_order_line', N'PK_fnb_order_line', 1),
    (N'fnb_order_line', N'UQ_fnb_order_line_1', 1),
    (N'fnb_order_line', N'UQ_fnb_order_line_2', 1),
    (N'fnb_order_import', N'PK_fnb_order_import', 1),
    (N'fnb_order_import', N'UQ_fnb_order_import_1', 1),
    (N'fnb_stock_document', N'PK_fnb_stock_document', 1),
    (N'fnb_stock_document', N'UQ_fnb_stock_document_1', 1),
    (N'fnb_stock_document', N'UQ_fnb_stock_document_2', 1),
    (N'fnb_stock_document', N'UQ_fnb_stock_document_3', 1),
    (N'fnb_stock_document_line', N'PK_fnb_stock_document_line', 1),
    (N'fnb_stock_document_line', N'UQ_fnb_stock_document_line_1', 1),
    (N'fnb_stock_document_line', N'UQ_fnb_stock_document_line_2', 1),
    (N'fnb_stock_document_line', N'UQ_fnb_stock_document_line_3', 1),
    (N'fnb_stock_movement', N'PK_fnb_stock_movement', 1),
    (N'fnb_stock_movement', N'UQ_fnb_stock_movement_1', 1),
    (N'fnb_stock_movement', N'UQ_fnb_stock_movement_2', 1),
    (N'fnb_stocktake_line', N'PK_fnb_stocktake_line', 1),
    (N'fnb_stocktake_line', N'UQ_fnb_stocktake_line_1', 1),
    (N'fnb_material_category', N'IX_fnb_material_category_sibling_name', 1),
    (N'fnb_shelf_life_rule', N'IX_fnb_shelf_life_rule_active_rule', 1),
    (N'fnb_material_item', N'IX_fnb_material_item_category', 0),
    (N'fnb_material_batch_stock', N'IX_fnb_material_batch_stock_stock_lookup', 0),
    (N'fnb_material_batch_stock', N'IX_fnb_material_batch_stock_opened_day', 1),
    (N'fnb_dish_spec', N'IX_fnb_dish_spec_default_spec', 1),
    (N'fnb_dish_spec', N'IX_fnb_dish_spec_legacy_product', 1),
    (N'fnb_recipe', N'IX_fnb_recipe_dish_version', 1),
    (N'fnb_recipe', N'IX_fnb_recipe_prep_version', 1),
    (N'fnb_recipe', N'IX_fnb_recipe_published_dish', 1),
    (N'fnb_recipe', N'IX_fnb_recipe_published_prep', 1),
    (N'fnb_order', N'IX_fnb_order_external_order', 1),
    (N'fnb_order', N'IX_fnb_order_sales_order', 1),
    (N'fnb_order', N'IX_fnb_order_kitchen_list', 0),
    (N'fnb_order_line', N'IX_fnb_order_line_legacy_line', 1),
    (N'fnb_order_import', N'IX_fnb_order_import_pending', 0),
    (N'fnb_stock_document', N'IX_fnb_stock_document_served_once', 1),
    (N'fnb_stock_document', N'IX_fnb_stock_document_business_date', 0),
    (N'fnb_stock_movement', N'IX_fnb_stock_movement_item_history', 0),
    (N'fnb_stock_movement', N'IX_fnb_stock_movement_batch_history', 0)
    ) AS x(table_name,index_name,is_unique)
)
INSERT INTO @check(category,item,is_ok,detail)
SELECT N'索引', e.index_name,
       CASE WHEN i.index_id IS NOT NULL AND i.is_disabled=0 AND i.is_unique=e.is_unique THEN 1 ELSE 0 END,
       CASE WHEN i.index_id IS NULL THEN N'缺少索引' WHEN i.is_disabled=1 THEN N'索引已禁用' WHEN i.is_unique<>e.is_unique THEN N'唯一性不符' ELSE N'正常' END
FROM expected AS e
LEFT JOIN sys.tables AS t ON t.schema_id=SCHEMA_ID(N'dbo') AND t.name=e.table_name
LEFT JOIN sys.indexes AS i ON i.object_id=t.object_id AND i.name=e.index_name;

;WITH expected(view_name) AS (
    SELECT * FROM (VALUES
    (N'vw_fnb_material_stock'),
    (N'vw_fnb_material_loss')
    ) AS x(view_name)
)
INSERT INTO @check(category,item,is_ok,detail)
SELECT N'视图', e.view_name, CASE WHEN v.object_id IS NOT NULL THEN 1 ELSE 0 END,
       CASE WHEN v.object_id IS NULL THEN N'缺少视图' ELSE N'正常' END
FROM expected AS e
LEFT JOIN sys.views AS v ON v.schema_id=SCHEMA_ID(N'dbo') AND v.name=e.view_name;

INSERT INTO @check(category,item,is_ok,detail)
SELECT N'订单前置', e.column_name, CASE WHEN c.column_id IS NOT NULL THEN 1 ELSE 0 END,
       CASE WHEN c.column_id IS NULL THEN N'缺少 dbo.[order] 来源字段' ELSE N'存在' END
FROM (VALUES(N'order_source'),(N'source_order_no')) AS e(column_name)
LEFT JOIN sys.columns AS c ON c.object_id=OBJECT_ID(N'dbo.[order]',N'U') AND c.name=e.column_name;

DECLARE @seed_count INT = 0;
IF OBJECT_ID(N'dbo.fnb_unit',N'U') IS NOT NULL
BEGIN
    EXEC sys.sp_executesql N'SELECT @n=COUNT(*) FROM [dbo].[fnb_unit] AS u WHERE
        (u.code=''g'' AND u.name=N''克'' AND u.dimension=1 AND u.factor_to_base=1) OR
        (u.code=''kg'' AND u.name=N''千克'' AND u.dimension=1 AND u.factor_to_base=1000) OR
        (u.code=''ml'' AND u.name=N''毫升'' AND u.dimension=2 AND u.factor_to_base=1) OR
        (u.code=''l'' AND u.name=N''升'' AND u.dimension=2 AND u.factor_to_base=1000) OR
        (u.code=''piece'' AND u.name=N''个'' AND u.dimension=3 AND u.factor_to_base=1);',
        N'@n INT OUTPUT', @n=@seed_count OUTPUT;
END;
INSERT INTO @check(category,item,is_ok,detail)
VALUES(N'基础单位',N'5个基础计量单位',CASE WHEN @seed_count=5 THEN 1 ELSE 0 END,
       N'应为 5 项，匹配 '+CONVERT(NVARCHAR(12),@seed_count)+N' 项');

SELECT category, COUNT(*) AS expected_count,
       SUM(CONVERT(INT,is_ok)) AS matched_count,
       COUNT(*)-SUM(CONVERT(INT,is_ok)) AS mismatch_count
FROM @check GROUP BY category ORDER BY category;
SELECT category,item,detail FROM @check WHERE is_ok=0 ORDER BY category,item;
SELECT CASE WHEN OBJECT_ID(N'dbo.[order]',N'U') IS NULL THEN N'dbo.[order] 不存在'
            WHEN EXISTS(SELECT 1 FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID(N'dbo.[order]',N'U') AND name=N'CK_order_source_pair') THEN N'CK_order_source_pair 存在'
            ELSE N'CK_order_source_pair 不存在' END AS order_source_pair_check_status;
