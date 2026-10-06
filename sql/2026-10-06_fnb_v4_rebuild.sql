-- 食材管理 v4，第 1 期，2026-10-06。只新增，不迁移、不覆盖旧食材数据。
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

IF OBJECT_ID(N'dbo.fnb_unit', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_unit] (
    [code] varchar(32) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [name] varchar(40) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [dimension] tinyint NOT NULL,
    [factor_to_base] decimal(18,6) NOT NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [sort] int NOT NULL,
    CONSTRAINT [PK_fnb_unit] PRIMARY KEY ([code]),
    CONSTRAINT [CK_fnb_unit_unit] CHECK (dimension IN (1,2,3) AND factor_to_base > 0)
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_unit', N'code') IS NULL OR COL_LENGTH(N'dbo.fnb_unit', N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_unit', N'dimension') IS NULL OR COL_LENGTH(N'dbo.fnb_unit', N'factor_to_base') IS NULL OR COL_LENGTH(N'dbo.fnb_unit', N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_unit', N'sort') IS NULL
 THROW 51001, N'已有表 fnb_unit 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_category', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_category] (
    [id] int NOT NULL IDENTITY,
    [parent_id] int NULL,
    [level] tinyint NOT NULL,
    [name] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [batch_code] varchar(16) COLLATE Chinese_PRC_CI_AS NULL,
    [measure_type] varchar(10) COLLATE Chinese_PRC_CI_AS NULL,
    [default_storage] varchar(20) COLLATE Chinese_PRC_CI_AS NULL,
    [warn_days] int NULL,
    [open_days] int NULL,
    [is_prepared] bit NOT NULL,
    [sort] int NOT NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_category] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_category_days] CHECK ((warn_days IS NULL OR warn_days >= 0) AND (open_days IS NULL OR open_days >= 0)),
    CONSTRAINT [CK_fnb_v4_category_tree] CHECK ((level = 1 AND parent_id IS NULL AND batch_code IS NULL AND measure_type IS NULL AND default_storage IS NULL AND warn_days IS NULL AND open_days IS NULL AND is_prepared = 0) OR (level = 2 AND parent_id IS NOT NULL AND batch_code IS NOT NULL AND measure_type IS NOT NULL AND default_storage IS NOT NULL AND measure_type IN ('weight','volume','count') AND default_storage IN ('ambient','chilled','frozen'))),
    CONSTRAINT [FK_fnb_v4_category_fnb_v4_category_parent_id] FOREIGN KEY ([parent_id]) REFERENCES [dbo].[fnb_v4_category] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_category', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'parent_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'level') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'batch_code') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'measure_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'default_storage') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'warn_days') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'open_days') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'is_prepared') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'sort') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_category', N'updated_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_category 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_item', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_item] (
    [id] int NOT NULL IDENTITY,
    [category_id] int NOT NULL,
    [name] varchar(200) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [item_type] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [base_unit_code] varchar(32) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [warn_days] int NULL,
    [open_days] int NULL,
    [low_stock_ratio] decimal(5,4) NULL,
    [low_stock_qty] decimal(18,6) NULL,
    [image_id] int NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_item] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_item_defaults] CHECK ((warn_days IS NULL OR warn_days >= 0) AND (open_days IS NULL OR open_days >= 0) AND (low_stock_ratio IS NULL OR (low_stock_ratio > 0 AND low_stock_ratio <= 1)) AND (low_stock_qty IS NULL OR low_stock_qty >= 0) AND (low_stock_ratio IS NULL OR low_stock_qty IS NULL)),
    CONSTRAINT [CK_fnb_v4_item_type] CHECK (item_type IN ('raw','prepared') AND base_unit_code IN ('g','ml','piece')),
    CONSTRAINT [FK_fnb_v4_item_fnb_unit_base_unit_code] FOREIGN KEY ([base_unit_code]) REFERENCES [dbo].[fnb_unit] ([code]),
    CONSTRAINT [FK_fnb_v4_item_fnb_v4_category_category_id] FOREIGN KEY ([category_id]) REFERENCES [dbo].[fnb_v4_category] ([id]),
    CONSTRAINT [FK_fnb_v4_item_mini_upload_image_id] FOREIGN KEY ([image_id]) REFERENCES [dbo].[mini_upload] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_item', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'category_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'item_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'base_unit_code') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'warn_days') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'open_days') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'low_stock_ratio') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'low_stock_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'image_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item', N'updated_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_item 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_order', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_order] (
    [id] bigint NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [source_type] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [sales_order_id] int NULL,
    [channel_shop_id] int NULL,
    [external_order_no] varchar(256) COLLATE Chinese_PRC_CI_AS NULL,
    [display_no] varchar(128) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [business_date] date NOT NULL,
    [ordered_at] datetime2(3) NOT NULL,
    [table_no] varchar(100) COLLATE Chinese_PRC_CI_AS NULL,
    [order_status] varchar(24) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [platform_status] varchar(100) COLLATE Chinese_PRC_CI_AS NULL,
    [refund_status] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [total_amount] decimal(19,6) NULL,
    [refund_amount] decimal(19,6) NULL,
    [review_status] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [remark] varchar(2000) COLLATE Chinese_PRC_CI_AS NULL,
    [source_updated_at] datetime2(3) NULL,
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_order] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_order_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_order', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'source_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'sales_order_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'channel_shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'external_order_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'display_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'business_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'ordered_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'table_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'order_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'platform_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'refund_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'total_amount') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'refund_amount') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'review_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'remark') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'source_updated_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'updated_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order', N'row_version') IS NULL
 THROW 51001, N'已有表 fnb_v4_order 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_dish_spec', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_dish_spec] (
    [id] int NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [product_id] int NOT NULL,
    [spec_code] varchar(64) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [name] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [sale_price] decimal(19,6) NULL,
    [legacy_product_id] int NULL,
    [is_default] bit NOT NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_dish_spec] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_dish_spec_product_product_id] FOREIGN KEY ([product_id]) REFERENCES [dbo].[product] ([id]),
    CONSTRAINT [FK_fnb_v4_dish_spec_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'product_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'spec_code') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'sale_price') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'legacy_product_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'is_default') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_dish_spec', N'updated_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_dish_spec 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_item_form', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_item_form] (
    [id] int NOT NULL IDENTITY,
    [item_id] int NOT NULL,
    [seq] int NOT NULL,
    [name] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [unit_name] varchar(40) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [per_base] decimal(19,6) NOT NULL,
    [storage_type] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [shelf_after_op_days] int NULL,
    [form_code] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [in_op_name] varchar(100) COLLATE Chinese_PRC_CI_AS NULL,
    [in_op_ratio] decimal(19,6) NULL,
    [in_op_yield] decimal(19,6) NULL,
    [in_op_hours] decimal(19,6) NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_item_form] PRIMARY KEY ([id]),
    CONSTRAINT [AK_fnb_v4_item_form_id_item_id] UNIQUE ([id], [item_id]),
    CONSTRAINT [CK_fnb_v4_item_form_operation] CHECK ((seq = 0 AND in_op_name IS NULL AND in_op_ratio IS NULL AND in_op_yield IS NULL AND in_op_hours IS NULL) OR (seq > 0 AND in_op_name IS NOT NULL AND in_op_ratio IS NOT NULL AND in_op_ratio > 0 AND in_op_yield IS NOT NULL AND in_op_yield > 0 AND in_op_yield <= 1 AND in_op_hours IS NOT NULL AND in_op_hours >= 0)),
    CONSTRAINT [CK_fnb_v4_item_form_value] CHECK (seq >= 0 AND per_base > 0 AND storage_type IN ('ambient','chilled','frozen') AND (shelf_after_op_days IS NULL OR shelf_after_op_days >= 0)),
    CONSTRAINT [FK_fnb_v4_item_form_fnb_v4_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_v4_item] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_item_form', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'seq') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'unit_name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'per_base') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'storage_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'shelf_after_op_days') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'form_code') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'in_op_name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'in_op_ratio') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'in_op_yield') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'in_op_hours') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_item_form', N'updated_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_item_form 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_shelf_life_rule', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_shelf_life_rule] (
    [id] int NOT NULL IDENTITY,
    [item_id] int NULL,
    [category_id] int NULL,
    [storage_type] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [season] varchar(8) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [days] int NOT NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_shelf_life_rule] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_shelf_life_rule_owner] CHECK ((category_id IS NULL AND item_id IS NOT NULL) OR (category_id IS NOT NULL AND item_id IS NULL)),
    CONSTRAINT [CK_fnb_v4_shelf_life_rule_value] CHECK (season IN ('all','warm','cold') AND days > 0 AND storage_type IN ('ambient','chilled','frozen')),
    CONSTRAINT [FK_fnb_v4_shelf_life_rule_fnb_v4_category_category_id] FOREIGN KEY ([category_id]) REFERENCES [dbo].[fnb_v4_category] ([id]),
    CONSTRAINT [FK_fnb_v4_shelf_life_rule_fnb_v4_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_v4_item] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'category_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'storage_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'season') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'days') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_shelf_life_rule', N'updated_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_shelf_life_rule 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_order_import', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_order_import] (
    [id] bigint NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [source_method] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [dedupe_key] varchar(256) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [order_id] bigint NULL,
    [process_status] varchar(24) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [reviewed_by_staff_id] int NULL,
    [captured_at] datetime2(3) NOT NULL,
    [processed_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_order_import] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_order_import_fnb_v4_order_order_id] FOREIGN KEY ([order_id]) REFERENCES [dbo].[fnb_v4_order] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_order_import', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'source_method') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'dedupe_key') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'order_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'process_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'reviewed_by_staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'captured_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_import', N'processed_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_order_import 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_recipe', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_recipe] (
    [id] bigint NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [recipe_type] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [dish_spec_id] int NULL,
    [output_item_id] int NULL,
    [output_qty] decimal(19,6) NOT NULL,
    [version_no] int NOT NULL,
    [status] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [remark] varchar(1000) COLLATE Chinese_PRC_CI_AS NULL,
    [created_by_staff_id] int NULL,
    [created_at] datetime2(3) NOT NULL,
    [published_at] datetime2(3) NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_recipe] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_recipe_owner] CHECK (((recipe_type = 'prep' AND output_item_id IS NOT NULL AND dish_spec_id IS NULL) OR (recipe_type = 'dish' AND dish_spec_id IS NOT NULL AND output_item_id IS NULL)) AND output_qty > 0 AND version_no > 0 AND status IN ('draft','published','retired')),
    CONSTRAINT [FK_fnb_v4_recipe_fnb_v4_dish_spec_dish_spec_id] FOREIGN KEY ([dish_spec_id]) REFERENCES [dbo].[fnb_v4_dish_spec] ([id]),
    CONSTRAINT [FK_fnb_v4_recipe_fnb_v4_item_output_item_id] FOREIGN KEY ([output_item_id]) REFERENCES [dbo].[fnb_v4_item] ([id]),
    CONSTRAINT [FK_fnb_v4_recipe_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_recipe', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'recipe_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'dish_spec_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'output_item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'output_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'version_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'remark') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'created_by_staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'published_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe', N'row_version') IS NULL
 THROW 51001, N'已有表 fnb_v4_recipe 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_purchase_spec', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_purchase_spec] (
    [id] int NOT NULL IDENTITY,
    [item_id] int NOT NULL,
    [entry_form_id] int NOT NULL,
    [name] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [brand] varchar(100) COLLATE Chinese_PRC_CI_AS NULL,
    [pack_desc] varchar(200) COLLATE Chinese_PRC_CI_AS NULL,
    [barcode] varchar(100) COLLATE Chinese_PRC_CI_AS NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [sort] int NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_purchase_spec] PRIMARY KEY ([id]),
    CONSTRAINT [AK_fnb_v4_purchase_spec_id_item_id] UNIQUE ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_purchase_spec_fnb_v4_item_form_entry_form_id_item_id] FOREIGN KEY ([entry_form_id], [item_id]) REFERENCES [dbo].[fnb_v4_item_form] ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_purchase_spec_fnb_v4_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_v4_item] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'entry_form_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'brand') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'pack_desc') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'barcode') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'sort') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_purchase_spec', N'updated_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_purchase_spec 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_order_line', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_order_line] (
    [id] bigint NOT NULL IDENTITY,
    [order_id] bigint NOT NULL,
    [shop_id] int NOT NULL,
    [line_key] varchar(256) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [parent_line_id] bigint NULL,
    [legacy_fd_order_id] int NULL,
    [option_key] varchar(256) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [item_name] varchar(300) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [spec_name] varchar(200) COLLATE Chinese_PRC_CI_AS NULL,
    [options_text] varchar(2000) COLLATE Chinese_PRC_CI_AS NULL,
    [quantity] decimal(19,6) NOT NULL,
    [cancelled_qty] decimal(19,6) NOT NULL,
    [is_inventory_line] bit NOT NULL,
    [dish_spec_id] int NULL,
    [recipe_id] bigint NULL,
    [remark] varchar(1000) COLLATE Chinese_PRC_CI_AS NULL,
    CONSTRAINT [PK_fnb_v4_order_line] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_order_line_fnb_v4_dish_spec_dish_spec_id] FOREIGN KEY ([dish_spec_id]) REFERENCES [dbo].[fnb_v4_dish_spec] ([id]),
    CONSTRAINT [FK_fnb_v4_order_line_fnb_v4_order_order_id] FOREIGN KEY ([order_id]) REFERENCES [dbo].[fnb_v4_order] ([id]),
    CONSTRAINT [FK_fnb_v4_order_line_fnb_v4_recipe_recipe_id] FOREIGN KEY ([recipe_id]) REFERENCES [dbo].[fnb_v4_recipe] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_order_line', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'order_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'line_key') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'parent_line_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'legacy_fd_order_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'option_key') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'item_name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'spec_name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'options_text') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'quantity') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'cancelled_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'is_inventory_line') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'dish_spec_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'recipe_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_order_line', N'remark') IS NULL
 THROW 51001, N'已有表 fnb_v4_order_line 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_recipe_line', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_recipe_line] (
    [id] bigint NOT NULL IDENTITY,
    [recipe_id] bigint NOT NULL,
    [item_id] int NOT NULL,
    [quantity] decimal(19,6) NOT NULL,
    [sort] int NOT NULL,
    [remark] varchar(600) COLLATE Chinese_PRC_CI_AS NULL,
    CONSTRAINT [PK_fnb_v4_recipe_line] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_recipe_line_quantity] CHECK (quantity > 0),
    CONSTRAINT [FK_fnb_v4_recipe_line_fnb_v4_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_v4_item] ([id]),
    CONSTRAINT [FK_fnb_v4_recipe_line_fnb_v4_recipe_recipe_id] FOREIGN KEY ([recipe_id]) REFERENCES [dbo].[fnb_v4_recipe] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_recipe_line', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe_line', N'recipe_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe_line', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe_line', N'quantity') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe_line', N'sort') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_recipe_line', N'remark') IS NULL
 THROW 51001, N'已有表 fnb_v4_recipe_line 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_stock_document', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_stock_document] (
    [id] bigint NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [document_no] varchar(80) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [document_type] varchar(32) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [status] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [request_id] uniqueidentifier NOT NULL,
    [source_client] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [business_date] date NOT NULL,
    [occurred_at] datetime2(3) NOT NULL,
    [order_id] bigint NULL,
    [recipe_id] bigint NULL,
    [reason_code] varchar(32) COLLATE Chinese_PRC_CI_AS NULL,
    [reference_no] varchar(200) COLLATE Chinese_PRC_CI_AS NULL,
    [remark] varchar(2000) COLLATE Chinese_PRC_CI_AS NULL,
    [created_by_staff_id] int NULL,
    [posted_by_staff_id] int NULL,
    [created_at] datetime2(3) NOT NULL,
    [posted_at] datetime2(3) NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_stock_document] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_stock_document_type] CHECK (document_type IN ('receipt','op','prep','serve','waste','destroy','stocktake') AND source_client IN ('mini','wecom') AND status IN ('draft','posted','cancelled')),
    CONSTRAINT [FK_fnb_v4_stock_document_fnb_v4_order_order_id] FOREIGN KEY ([order_id]) REFERENCES [dbo].[fnb_v4_order] ([id]),
    CONSTRAINT [FK_fnb_v4_stock_document_fnb_v4_recipe_recipe_id] FOREIGN KEY ([recipe_id]) REFERENCES [dbo].[fnb_v4_recipe] ([id]),
    CONSTRAINT [FK_fnb_v4_stock_document_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_stock_document', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'document_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'document_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'request_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'source_client') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'business_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'occurred_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'order_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'recipe_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'reason_code') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'reference_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'remark') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'created_by_staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'posted_by_staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'posted_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document', N'row_version') IS NULL
 THROW 51001, N'已有表 fnb_v4_stock_document 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_batch', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_batch] (
    [id] int NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [item_id] int NOT NULL,
    [form_id] int NOT NULL,
    [batch_no] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [state] varchar(12) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [quantity] decimal(19,6) NOT NULL,
    [amount] decimal(19,6) NOT NULL,
    [pack_size] decimal(19,6) NULL,
    [pack_label] varchar(40) COLLATE Chinese_PRC_CI_AS NULL,
    [storage_type] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [production_date] date NULL,
    [expire_date] date NOT NULL,
    [op_date] date NULL,
    [op_expire_date] date NULL,
    [effective_expire] AS CASE WHEN [op_expire_date] IS NOT NULL AND [op_expire_date] < [expire_date] THEN [op_expire_date] ELSE [expire_date] END PERSISTED,
    [expiry_source] varchar(24) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [parent_batch_id] int NULL,
    [ready_at] datetime2(3) NULL,
    [spec_id] int NULL,
    [received_at] datetime2(3) NOT NULL,
    [dispose_status] varchar(20) COLLATE Chinese_PRC_CI_AS NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_batch] PRIMARY KEY ([id]),
    CONSTRAINT [AK_fnb_v4_batch_id_shop_id_item_id] UNIQUE ([id], [shop_id], [item_id]),
    CONSTRAINT [CK_fnb_v4_batch_dates] CHECK ((production_date IS NULL OR production_date <= expire_date) AND (op_expire_date IS NULL OR op_date IS NOT NULL)),
    CONSTRAINT [CK_fnb_v4_batch_disposal] CHECK (dispose_status IS NULL OR (dispose_status IN ('used_up','wasted','destroyed') AND quantity = 0 AND amount = 0)),
    CONSTRAINT [CK_fnb_v4_batch_pack] CHECK ((state = 'sealed' AND pack_size IS NOT NULL AND pack_size > 0 AND pack_label IS NOT NULL AND quantity % pack_size = 0) OR (state <> 'sealed' AND pack_size IS NULL AND pack_label IS NULL)),
    CONSTRAINT [CK_fnb_v4_batch_value] CHECK (state IN ('sealed','staged','final') AND quantity >= 0 AND amount >= 0 AND storage_type IN ('ambient','chilled','frozen')),
    CONSTRAINT [FK_fnb_v4_batch_fnb_v4_batch_parent_batch_id_shop_id_item_id] FOREIGN KEY ([parent_batch_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_v4_batch] ([id], [shop_id], [item_id]),
    CONSTRAINT [FK_fnb_v4_batch_fnb_v4_item_form_form_id_item_id] FOREIGN KEY ([form_id], [item_id]) REFERENCES [dbo].[fnb_v4_item_form] ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_batch_fnb_v4_purchase_spec_spec_id_item_id] FOREIGN KEY ([spec_id], [item_id]) REFERENCES [dbo].[fnb_v4_purchase_spec] ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_batch_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_batch', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'form_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'batch_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'state') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'quantity') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'amount') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'pack_size') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'pack_label') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'storage_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'production_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'expire_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'op_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'op_expire_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'effective_expire') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'expiry_source') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'parent_batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'ready_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'spec_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'received_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'dispose_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch', N'row_version') IS NULL
 THROW 51001, N'已有表 fnb_v4_batch 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_stocktake_line', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_stocktake_line] (
    [id] bigint NOT NULL IDENTITY,
    [document_id] bigint NOT NULL,
    [shop_id] int NOT NULL,
    [item_id] int NOT NULL,
    [system_qty] decimal(19,6) NOT NULL,
    [counted_qty] decimal(19,6) NULL,
    [difference_qty] AS CONVERT(decimal(19,6),[counted_qty] - [system_qty]) PERSISTED,
    [snapshot_at] datetime2(3) NOT NULL,
    [snapshot_last_movement_id] bigint NULL,
    [snapshot_fingerprint] varbinary(max) NOT NULL,
    [adjustment_line_id] bigint NULL,
    [counted_by_staff_id] int NULL,
    [counted_at] datetime2(3) NULL,
    [remark] varchar(1000) COLLATE Chinese_PRC_CI_AS NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_stocktake_line] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_stocktake_line_quantity] CHECK (system_qty >= 0 AND (counted_qty IS NULL OR counted_qty >= 0)),
    CONSTRAINT [FK_fnb_v4_stocktake_line_fnb_v4_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_v4_item] ([id]),
    CONSTRAINT [FK_fnb_v4_stocktake_line_fnb_v4_stock_document_document_id] FOREIGN KEY ([document_id]) REFERENCES [dbo].[fnb_v4_stock_document] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'document_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'system_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'counted_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'difference_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'snapshot_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'snapshot_last_movement_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'snapshot_fingerprint') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'adjustment_line_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'counted_by_staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'counted_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'remark') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stocktake_line', N'row_version') IS NULL
 THROW 51001, N'已有表 fnb_v4_stocktake_line 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_batch_image', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_batch_image] (
    [batch_id] int NOT NULL,
    [upload_id] int NOT NULL,
    CONSTRAINT [PK_fnb_v4_batch_image] PRIMARY KEY ([batch_id], [upload_id]),
    CONSTRAINT [FK_fnb_v4_batch_image_fnb_v4_batch_batch_id] FOREIGN KEY ([batch_id]) REFERENCES [dbo].[fnb_v4_batch] ([id]),
    CONSTRAINT [FK_fnb_v4_batch_image_mini_upload_upload_id] FOREIGN KEY ([upload_id]) REFERENCES [dbo].[mini_upload] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_batch_image', N'batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch_image', N'upload_id') IS NULL
 THROW 51001, N'已有表 fnb_v4_batch_image 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_stock_document_line', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_stock_document_line] (
    [id] bigint NOT NULL IDENTITY,
    [document_id] bigint NOT NULL,
    [shop_id] int NOT NULL,
    [line_no] int NOT NULL,
    [item_id] int NOT NULL,
    [item_name] varchar(200) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [direction] smallint NOT NULL,
    [input_qty] decimal(19,6) NOT NULL,
    [input_unit_name] varchar(40) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [input_to_base] decimal(19,6) NOT NULL,
    [planned_qty] AS CONVERT(decimal(19,6),[input_qty] * [input_to_base]) PERSISTED,
    [actual_qty] decimal(19,6) NOT NULL,
    [shortage_qty] AS CONVERT(decimal(19,6),CASE WHEN [input_qty]*[input_to_base] > [actual_qty] THEN [input_qty]*[input_to_base]-[actual_qty] ELSE 0 END) PERSISTED,
    [input_unit_price] decimal(19,6) NULL,
    [actual_amount] decimal(19,6) NOT NULL,
    [specified_batch_id] int NULL,
    [spec_id] int NULL,
    [form_id] int NULL,
    [remark] varchar(1000) COLLATE Chinese_PRC_CI_AS NULL,
    CONSTRAINT [PK_fnb_v4_stock_document_line] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_stock_document_line_quantity] CHECK (direction IN (-1,1) AND input_qty >= 0 AND input_to_base > 0 AND actual_qty >= 0 AND actual_amount >= 0),
    CONSTRAINT [FK_fnb_v4_stock_document_line_fnb_v4_batch_specified_batch_id_shop_id_item_id] FOREIGN KEY ([specified_batch_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_v4_batch] ([id], [shop_id], [item_id]),
    CONSTRAINT [FK_fnb_v4_stock_document_line_fnb_v4_item_form_form_id_item_id] FOREIGN KEY ([form_id], [item_id]) REFERENCES [dbo].[fnb_v4_item_form] ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_stock_document_line_fnb_v4_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_v4_item] ([id]),
    CONSTRAINT [FK_fnb_v4_stock_document_line_fnb_v4_purchase_spec_spec_id_item_id] FOREIGN KEY ([spec_id], [item_id]) REFERENCES [dbo].[fnb_v4_purchase_spec] ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_stock_document_line_fnb_v4_stock_document_document_id] FOREIGN KEY ([document_id]) REFERENCES [dbo].[fnb_v4_stock_document] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'document_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'line_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'item_name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'direction') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'input_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'input_unit_name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'input_to_base') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'planned_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'actual_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'shortage_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'input_unit_price') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'actual_amount') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'specified_batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'spec_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'form_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_document_line', N'remark') IS NULL
 THROW 51001, N'已有表 fnb_v4_stock_document_line 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_stock_operation', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_stock_operation] (
    [id] bigint NOT NULL IDENTITY,
    [document_id] bigint NOT NULL,
    [item_id] int NOT NULL,
    [from_form_id] int NOT NULL,
    [to_form_id] int NOT NULL,
    [source_batch_id] int NOT NULL,
    [output_batch_id] int NOT NULL,
    [op_name] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [input_qty] decimal(19,6) NOT NULL,
    [std_ratio] decimal(19,6) NOT NULL,
    [std_yield] decimal(19,6) NOT NULL,
    [expected_qty] decimal(19,6) NOT NULL,
    [actual_qty] decimal(19,6) NOT NULL,
    [loss_base_qty] decimal(19,6) NOT NULL,
    [duration_hours] decimal(19,6) NOT NULL,
    [ready_at] datetime2(3) NULL,
    [status] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [completed_at] datetime2(3) NULL,
    [staff_id] int NOT NULL,
    CONSTRAINT [PK_fnb_v4_stock_operation] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_stock_operation_value] CHECK (input_qty > 0 AND std_ratio > 0 AND std_yield > 0 AND std_yield <= 1 AND expected_qty >= 0 AND actual_qty >= 0 AND loss_base_qty >= 0 AND duration_hours >= 0 AND status IN ('running','done')),
    CONSTRAINT [FK_fnb_v4_stock_operation_fnb_v4_batch_output_batch_id] FOREIGN KEY ([output_batch_id]) REFERENCES [dbo].[fnb_v4_batch] ([id]),
    CONSTRAINT [FK_fnb_v4_stock_operation_fnb_v4_batch_source_batch_id] FOREIGN KEY ([source_batch_id]) REFERENCES [dbo].[fnb_v4_batch] ([id]),
    CONSTRAINT [FK_fnb_v4_stock_operation_fnb_v4_item_form_from_form_id_item_id] FOREIGN KEY ([from_form_id], [item_id]) REFERENCES [dbo].[fnb_v4_item_form] ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_stock_operation_fnb_v4_item_form_to_form_id_item_id] FOREIGN KEY ([to_form_id], [item_id]) REFERENCES [dbo].[fnb_v4_item_form] ([id], [item_id]),
    CONSTRAINT [FK_fnb_v4_stock_operation_fnb_v4_stock_document_document_id] FOREIGN KEY ([document_id]) REFERENCES [dbo].[fnb_v4_stock_document] ([id]),
    CONSTRAINT [FK_fnb_v4_stock_operation_staff_staff_id] FOREIGN KEY ([staff_id]) REFERENCES [dbo].[staff] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'document_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'from_form_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'to_form_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'source_batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'output_batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'op_name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'input_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'std_ratio') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'std_yield') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'expected_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'actual_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'loss_base_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'duration_hours') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'ready_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'completed_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_operation', N'staff_id') IS NULL
 THROW 51001, N'已有表 fnb_v4_stock_operation 结构不完整，请人工核对；脚本不覆盖。', 1;

IF OBJECT_ID(N'dbo.fnb_v4_stock_movement', N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_stock_movement] (
    [id] bigint NOT NULL IDENTITY,
    [document_line_id] bigint NOT NULL,
    [shop_id] int NOT NULL,
    [item_id] int NOT NULL,
    [batch_id] int NOT NULL,
    [direction] smallint NOT NULL,
    [quantity] decimal(19,6) NOT NULL,
    [amount] decimal(19,6) NOT NULL,
    [delta_qty] AS CONVERT(decimal(19,6),[direction] * [quantity]) PERSISTED,
    [delta_amount] AS CONVERT(decimal(19,6),[direction] * [amount]) PERSISTED,
    [balance_qty] decimal(19,6) NOT NULL,
    [balance_amount] decimal(19,6) NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    CONSTRAINT [PK_fnb_v4_stock_movement] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_stock_movement_quantity] CHECK (direction IN (-1,1) AND quantity >= 0 AND amount >= 0 AND balance_qty >= 0 AND balance_amount >= 0),
    CONSTRAINT [FK_fnb_v4_stock_movement_fnb_v4_batch_batch_id_shop_id_item_id] FOREIGN KEY ([batch_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_v4_batch] ([id], [shop_id], [item_id]),
    CONSTRAINT [FK_fnb_v4_stock_movement_fnb_v4_stock_document_line_document_line_id] FOREIGN KEY ([document_line_id]) REFERENCES [dbo].[fnb_v4_stock_document_line] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'document_line_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'direction') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'quantity') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'amount') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'delta_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'delta_amount') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'balance_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'balance_amount') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_stock_movement', N'created_at') IS NULL
 THROW 51001, N'已有表 fnb_v4_stock_movement 结构不完整，请人工核对；脚本不覆盖。', 1;

-- 只插入缺失单位，不更新已有单位行。
INSERT INTO dbo.fnb_unit (code,name,dimension,factor_to_base,valid,sort)
SELECT s.code,s.name,s.dimension,s.factor,1,s.sort
FROM (VALUES ('g','克',1,1,10),('kg','千克',1,1000,11),('ml','毫升',2,1,20),
 ('l','升',2,1000,21),('piece','个',3,1,30)) AS s(code,name,dimension,factor,sort)
WHERE NOT EXISTS (SELECT 1 FROM dbo.fnb_unit u WHERE u.code = s.code);
IF EXISTS (SELECT 1 FROM dbo.fnb_unit WHERE code IN ('g','ml','piece') AND
 (valid <> 1 OR factor_to_base <> 1 OR dimension <> CASE code WHEN 'g' THEN 1 WHEN 'ml' THEN 2 ELSE 3 END))
 THROW 51002, N'已有基本单位不符合约定，请人工核对；不会更新已有数据。', 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_batch') AND name = N'IX_fnb_v4_batch_form_id_item_id')
CREATE INDEX [IX_fnb_v4_batch_form_id_item_id] ON [dbo].[fnb_v4_batch] ([form_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_batch') AND name = N'IX_fnb_v4_batch_parent_batch_id_shop_id_item_id')
CREATE INDEX [IX_fnb_v4_batch_parent_batch_id_shop_id_item_id] ON [dbo].[fnb_v4_batch] ([parent_batch_id], [shop_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_batch') AND name = N'IX_fnb_v4_batch_shop_id_batch_no')
CREATE UNIQUE INDEX [IX_fnb_v4_batch_shop_id_batch_no] ON [dbo].[fnb_v4_batch] ([shop_id], [batch_no]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_batch') AND name = N'IX_fnb_v4_batch_shop_id_item_id_form_id')
CREATE INDEX [IX_fnb_v4_batch_shop_id_item_id_form_id] ON [dbo].[fnb_v4_batch] ([shop_id], [item_id], [form_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_batch') AND name = N'IX_fnb_v4_batch_spec_id_item_id')
CREATE INDEX [IX_fnb_v4_batch_spec_id_item_id] ON [dbo].[fnb_v4_batch] ([spec_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_batch_image') AND name = N'IX_fnb_v4_batch_image_upload_id')
CREATE INDEX [IX_fnb_v4_batch_image_upload_id] ON [dbo].[fnb_v4_batch_image] ([upload_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_category') AND name = N'IX_fnb_v4_category_batch_code')
CREATE UNIQUE INDEX [IX_fnb_v4_category_batch_code] ON [dbo].[fnb_v4_category] ([batch_code]) WHERE [valid] = 1 AND [level] = 2;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_category') AND name = N'IX_fnb_v4_category_parent_id_name')
CREATE UNIQUE INDEX [IX_fnb_v4_category_parent_id_name] ON [dbo].[fnb_v4_category] ([parent_id], [name]) WHERE [valid] = 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_dish_spec') AND name = N'IX_fnb_v4_dish_spec_product_id_name')
CREATE UNIQUE INDEX [IX_fnb_v4_dish_spec_product_id_name] ON [dbo].[fnb_v4_dish_spec] ([product_id], [name]) WHERE [valid] = 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_dish_spec') AND name = N'IX_fnb_v4_dish_spec_shop_id')
CREATE INDEX [IX_fnb_v4_dish_spec_shop_id] ON [dbo].[fnb_v4_dish_spec] ([shop_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_item') AND name = N'IX_fnb_v4_item_base_unit_code')
CREATE INDEX [IX_fnb_v4_item_base_unit_code] ON [dbo].[fnb_v4_item] ([base_unit_code]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_item') AND name = N'IX_fnb_v4_item_category_id_name')
CREATE UNIQUE INDEX [IX_fnb_v4_item_category_id_name] ON [dbo].[fnb_v4_item] ([category_id], [name]) WHERE [valid] = 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_item') AND name = N'IX_fnb_v4_item_image_id')
CREATE INDEX [IX_fnb_v4_item_image_id] ON [dbo].[fnb_v4_item] ([image_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_item_form') AND name = N'IX_fnb_v4_item_form_item_id_form_code')
CREATE UNIQUE INDEX [IX_fnb_v4_item_form_item_id_form_code] ON [dbo].[fnb_v4_item_form] ([item_id], [form_code]) WHERE [valid] = 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_item_form') AND name = N'IX_fnb_v4_item_form_item_id_seq')
CREATE UNIQUE INDEX [IX_fnb_v4_item_form_item_id_seq] ON [dbo].[fnb_v4_item_form] ([item_id], [seq]) WHERE [valid] = 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_order') AND name = N'IX_fnb_v4_order_shop_id_source_type_external_order_no')
CREATE UNIQUE INDEX [IX_fnb_v4_order_shop_id_source_type_external_order_no] ON [dbo].[fnb_v4_order] ([shop_id], [source_type], [external_order_no]) WHERE [external_order_no] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_order_import') AND name = N'IX_fnb_v4_order_import_order_id')
CREATE INDEX [IX_fnb_v4_order_import_order_id] ON [dbo].[fnb_v4_order_import] ([order_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_order_import') AND name = N'IX_fnb_v4_order_import_shop_id_source_method_dedupe_key')
CREATE UNIQUE INDEX [IX_fnb_v4_order_import_shop_id_source_method_dedupe_key] ON [dbo].[fnb_v4_order_import] ([shop_id], [source_method], [dedupe_key]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_order_line') AND name = N'IX_fnb_v4_order_line_dish_spec_id')
CREATE INDEX [IX_fnb_v4_order_line_dish_spec_id] ON [dbo].[fnb_v4_order_line] ([dish_spec_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_order_line') AND name = N'IX_fnb_v4_order_line_order_id_line_key_option_key')
CREATE UNIQUE INDEX [IX_fnb_v4_order_line_order_id_line_key_option_key] ON [dbo].[fnb_v4_order_line] ([order_id], [line_key], [option_key]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_order_line') AND name = N'IX_fnb_v4_order_line_recipe_id')
CREATE INDEX [IX_fnb_v4_order_line_recipe_id] ON [dbo].[fnb_v4_order_line] ([recipe_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_purchase_spec') AND name = N'IX_fnb_v4_purchase_spec_barcode')
CREATE UNIQUE INDEX [IX_fnb_v4_purchase_spec_barcode] ON [dbo].[fnb_v4_purchase_spec] ([barcode]) WHERE [valid] = 1 AND [barcode] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_purchase_spec') AND name = N'IX_fnb_v4_purchase_spec_entry_form_id_item_id')
CREATE INDEX [IX_fnb_v4_purchase_spec_entry_form_id_item_id] ON [dbo].[fnb_v4_purchase_spec] ([entry_form_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_purchase_spec') AND name = N'IX_fnb_v4_purchase_spec_item_id')
CREATE INDEX [IX_fnb_v4_purchase_spec_item_id] ON [dbo].[fnb_v4_purchase_spec] ([item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_recipe') AND name = N'IX_fnb_v4_recipe_dish_spec_id')
CREATE INDEX [IX_fnb_v4_recipe_dish_spec_id] ON [dbo].[fnb_v4_recipe] ([dish_spec_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_recipe') AND name = N'IX_fnb_v4_recipe_output_item_id')
CREATE INDEX [IX_fnb_v4_recipe_output_item_id] ON [dbo].[fnb_v4_recipe] ([output_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_recipe') AND name = N'IX_fnb_v4_recipe_shop_id_dish_spec_id_version_no')
CREATE UNIQUE INDEX [IX_fnb_v4_recipe_shop_id_dish_spec_id_version_no] ON [dbo].[fnb_v4_recipe] ([shop_id], [dish_spec_id], [version_no]) WHERE [dish_spec_id] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_recipe') AND name = N'IX_fnb_v4_recipe_shop_id_output_item_id_version_no')
CREATE UNIQUE INDEX [IX_fnb_v4_recipe_shop_id_output_item_id_version_no] ON [dbo].[fnb_v4_recipe] ([shop_id], [output_item_id], [version_no]) WHERE [output_item_id] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_recipe_line') AND name = N'IX_fnb_v4_recipe_line_item_id')
CREATE INDEX [IX_fnb_v4_recipe_line_item_id] ON [dbo].[fnb_v4_recipe_line] ([item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_recipe_line') AND name = N'IX_fnb_v4_recipe_line_recipe_id_item_id')
CREATE UNIQUE INDEX [IX_fnb_v4_recipe_line_recipe_id_item_id] ON [dbo].[fnb_v4_recipe_line] ([recipe_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_shelf_life_rule') AND name = N'IX_fnb_v4_shelf_life_rule_category_id_storage_type_season')
CREATE UNIQUE INDEX [IX_fnb_v4_shelf_life_rule_category_id_storage_type_season] ON [dbo].[fnb_v4_shelf_life_rule] ([category_id], [storage_type], [season]) WHERE [valid] = 1 AND [category_id] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_shelf_life_rule') AND name = N'IX_fnb_v4_shelf_life_rule_item_id_storage_type_season')
CREATE UNIQUE INDEX [IX_fnb_v4_shelf_life_rule_item_id_storage_type_season] ON [dbo].[fnb_v4_shelf_life_rule] ([item_id], [storage_type], [season]) WHERE [valid] = 1 AND [item_id] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document') AND name = N'IX_fnb_v4_stock_document_order_id')
CREATE INDEX [IX_fnb_v4_stock_document_order_id] ON [dbo].[fnb_v4_stock_document] ([order_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document') AND name = N'IX_fnb_v4_stock_document_recipe_id')
CREATE INDEX [IX_fnb_v4_stock_document_recipe_id] ON [dbo].[fnb_v4_stock_document] ([recipe_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document') AND name = N'IX_fnb_v4_stock_document_shop_id_document_no')
CREATE UNIQUE INDEX [IX_fnb_v4_stock_document_shop_id_document_no] ON [dbo].[fnb_v4_stock_document] ([shop_id], [document_no]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document') AND name = N'IX_fnb_v4_stock_document_shop_id_document_type_request_id')
CREATE UNIQUE INDEX [IX_fnb_v4_stock_document_shop_id_document_type_request_id] ON [dbo].[fnb_v4_stock_document] ([shop_id], [document_type], [request_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document_line') AND name = N'IX_fnb_v4_stock_document_line_document_id_line_no')
CREATE UNIQUE INDEX [IX_fnb_v4_stock_document_line_document_id_line_no] ON [dbo].[fnb_v4_stock_document_line] ([document_id], [line_no]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document_line') AND name = N'IX_fnb_v4_stock_document_line_form_id_item_id')
CREATE INDEX [IX_fnb_v4_stock_document_line_form_id_item_id] ON [dbo].[fnb_v4_stock_document_line] ([form_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document_line') AND name = N'IX_fnb_v4_stock_document_line_item_id')
CREATE INDEX [IX_fnb_v4_stock_document_line_item_id] ON [dbo].[fnb_v4_stock_document_line] ([item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document_line') AND name = N'IX_fnb_v4_stock_document_line_spec_id_item_id')
CREATE INDEX [IX_fnb_v4_stock_document_line_spec_id_item_id] ON [dbo].[fnb_v4_stock_document_line] ([spec_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_document_line') AND name = N'IX_fnb_v4_stock_document_line_specified_batch_id_shop_id_item_id')
CREATE INDEX [IX_fnb_v4_stock_document_line_specified_batch_id_shop_id_item_id] ON [dbo].[fnb_v4_stock_document_line] ([specified_batch_id], [shop_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_movement') AND name = N'IX_fnb_v4_stock_movement_batch_id_shop_id_item_id')
CREATE INDEX [IX_fnb_v4_stock_movement_batch_id_shop_id_item_id] ON [dbo].[fnb_v4_stock_movement] ([batch_id], [shop_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_movement') AND name = N'IX_fnb_v4_stock_movement_document_line_id')
CREATE INDEX [IX_fnb_v4_stock_movement_document_line_id] ON [dbo].[fnb_v4_stock_movement] ([document_line_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_operation') AND name = N'IX_fnb_v4_stock_operation_document_id')
CREATE UNIQUE INDEX [IX_fnb_v4_stock_operation_document_id] ON [dbo].[fnb_v4_stock_operation] ([document_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_operation') AND name = N'IX_fnb_v4_stock_operation_from_form_id_item_id')
CREATE INDEX [IX_fnb_v4_stock_operation_from_form_id_item_id] ON [dbo].[fnb_v4_stock_operation] ([from_form_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_operation') AND name = N'IX_fnb_v4_stock_operation_output_batch_id')
CREATE INDEX [IX_fnb_v4_stock_operation_output_batch_id] ON [dbo].[fnb_v4_stock_operation] ([output_batch_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_operation') AND name = N'IX_fnb_v4_stock_operation_source_batch_id')
CREATE INDEX [IX_fnb_v4_stock_operation_source_batch_id] ON [dbo].[fnb_v4_stock_operation] ([source_batch_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_operation') AND name = N'IX_fnb_v4_stock_operation_staff_id')
CREATE INDEX [IX_fnb_v4_stock_operation_staff_id] ON [dbo].[fnb_v4_stock_operation] ([staff_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stock_operation') AND name = N'IX_fnb_v4_stock_operation_to_form_id_item_id')
CREATE INDEX [IX_fnb_v4_stock_operation_to_form_id_item_id] ON [dbo].[fnb_v4_stock_operation] ([to_form_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stocktake_line') AND name = N'IX_fnb_v4_stocktake_line_document_id_item_id')
CREATE UNIQUE INDEX [IX_fnb_v4_stocktake_line_document_id_item_id] ON [dbo].[fnb_v4_stocktake_line] ([document_id], [item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.fnb_v4_stocktake_line') AND name = N'IX_fnb_v4_stocktake_line_item_id')
CREATE INDEX [IX_fnb_v4_stocktake_line_item_id] ON [dbo].[fnb_v4_stocktake_line] ([item_id]);

IF OBJECT_ID(N'dbo.vw_fnb_v4_stock', N'V') IS NULL
 EXEC(N'CREATE VIEW dbo.vw_fnb_v4_stock AS
SELECT b.shop_id,b.item_id,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state=''final'' AND b.dispose_status IS NULL
  AND b.effective_expire >= CONVERT(date,SYSUTCDATETIME() AT TIME ZONE ''UTC'' AT TIME ZONE ''China Standard Time'')
  AND (b.ready_at IS NULL OR b.ready_at <= SYSUTCDATETIME()) THEN b.quantity ELSE 0 END)) AS available_qty,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state=''staged'' AND b.dispose_status IS NULL THEN b.quantity ELSE 0 END)) AS staged_qty,
 CONVERT(decimal(19,6),SUM(CASE WHEN b.state=''sealed'' AND b.dispose_status IS NULL THEN b.quantity ELSE 0 END)) AS sealed_qty,
 CONVERT(decimal(19,6),SUM(b.quantity)) AS total_qty,CONVERT(decimal(19,6),SUM(b.amount)) AS total_amount,
 CONVERT(decimal(19,6),SUM(b.amount)/NULLIF(SUM(b.quantity),0)) AS average_unit_cost
FROM dbo.fnb_v4_batch b GROUP BY b.shop_id,b.item_id');

IF OBJECT_ID(N'dbo.vw_fnb_v4_loss', N'V') IS NULL
 EXEC(N'CREATE VIEW dbo.vw_fnb_v4_loss AS
SELECT m.id AS source_id,d.document_type AS source_type,m.shop_id,m.item_id,d.business_date,
 CONVERT(decimal(19,6),-m.delta_qty) AS loss_qty,CONVERT(decimal(19,6),-m.delta_amount) AS loss_amount
FROM dbo.fnb_v4_stock_movement m
JOIN dbo.fnb_v4_stock_document_line l ON l.id=m.document_line_id
JOIN dbo.fnb_v4_stock_document d ON d.id=l.document_id
WHERE d.status=''posted'' AND d.document_type IN (''waste'',''destroy'',''stocktake'')
UNION ALL
SELECT o.id,''op'',d.shop_id,o.item_id,d.business_date,o.loss_base_qty,
 CONVERT(decimal(19,6),o.loss_base_qty * COALESCE(c.amount/NULLIF(c.qty,0),0))
FROM dbo.fnb_v4_stock_operation o JOIN dbo.fnb_v4_stock_document d ON d.id=o.document_id
OUTER APPLY (SELECT SUM(m.amount) AS amount,SUM(m.quantity) AS qty
 FROM dbo.fnb_v4_stock_movement m JOIN dbo.fnb_v4_stock_document_line l ON l.id=m.document_line_id
 WHERE l.document_id=o.document_id AND m.batch_id=o.source_batch_id AND m.direction=-1) c
WHERE d.status=''posted''');

COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
