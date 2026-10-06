-- 食材管理 v4 完整后端扩展，2026-10-06。仅增加新表及索引。
-- 先执行第一期重建 SQL；本脚本不改变已有表、字段、视图或数据。可重复执行。
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRY
BEGIN TRANSACTION;
IF OBJECT_ID(N'dbo.fnb_v4_batch',N'U') IS NULL
 THROW 51000,N'请先执行第一期 v4 建表脚本。',1;

IF OBJECT_ID(N'dbo.fnb_v4_request',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_request] (
    [shop_id] int NOT NULL,
    [action] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [request_id] uniqueidentifier NOT NULL,
    [payload_hash] varchar(64) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [response_json] varchar(max) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [staff_id] int NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    CONSTRAINT [PK_fnb_v4_request] PRIMARY KEY ([shop_id], [action], [request_id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_request',N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_request',N'action') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_request',N'request_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_request',N'payload_hash') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_request',N'response_json') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_request',N'staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_request',N'created_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_request 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_area',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_area] (
    [id] int NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [parent_id] int NULL,
    [name] varchar(100) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [area_type] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [sort] int NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_area] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_area_fnb_v4_area_parent_id] FOREIGN KEY ([parent_id]) REFERENCES [dbo].[fnb_v4_area] ([id]),
    CONSTRAINT [FK_fnb_v4_area_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_area',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'parent_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'area_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'sort') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area',N'updated_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_area 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_check_sheet',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_check_sheet] (
    [id] bigint NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [business_date] date NOT NULL,
    [status] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [fingerprint] varchar(64) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [started_by] int NOT NULL,
    [started_at] datetime2(3) NOT NULL,
    [saved_at] datetime2(3) NULL,
    [submitted_by] int NULL,
    [submitted_at] datetime2(3) NULL,
    [confirmed_by] int NULL,
    [confirmed_at] datetime2(3) NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_check_sheet] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_check_sheet_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'business_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'fingerprint') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'started_by') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'started_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'saved_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'submitted_by') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'submitted_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'confirmed_by') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'confirmed_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_sheet',N'row_version') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_check_sheet 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_area_image',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_area_image] (
    [area_id] int NOT NULL,
    [upload_id] int NOT NULL,
    [staff_id] int NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    CONSTRAINT [PK_fnb_v4_area_image] PRIMARY KEY ([area_id], [upload_id]),
    CONSTRAINT [FK_fnb_v4_area_image_fnb_v4_area_area_id] FOREIGN KEY ([area_id]) REFERENCES [dbo].[fnb_v4_area] ([id]),
    CONSTRAINT [FK_fnb_v4_area_image_mini_upload_upload_id] FOREIGN KEY ([upload_id]) REFERENCES [dbo].[mini_upload] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_area_image',N'area_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area_image',N'upload_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area_image',N'staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_area_image',N'created_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_area_image 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_supply',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_supply] (
    [id] int NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [name] varchar(200) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [supply_type] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [spec] varchar(200) COLLATE Chinese_PRC_CI_AS NULL,
    [pack_label] varchar(40) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [pack_size] int NOT NULL,
    [area_id] int NULL,
    [quantity] decimal(19,6) NOT NULL,
    [last_receipt_qty] decimal(19,6) NOT NULL,
    [low_stock_ratio] decimal(19,6) NULL,
    [low_stock_qty] decimal(19,6) NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [created_at] datetime2(3) NOT NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_supply] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_supply_value] CHECK (pack_size > 0 AND quantity >= 0 AND last_receipt_qty >= 0 AND supply_type IN ('disposable','reusable') AND (low_stock_ratio IS NULL OR low_stock_qty IS NULL)),
    CONSTRAINT [FK_fnb_v4_supply_fnb_v4_area_area_id] FOREIGN KEY ([area_id]) REFERENCES [dbo].[fnb_v4_area] ([id]),
    CONSTRAINT [FK_fnb_v4_supply_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_supply',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'supply_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'spec') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'pack_label') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'pack_size') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'area_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'quantity') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'last_receipt_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'low_stock_ratio') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'low_stock_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply',N'row_version') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_supply 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_tool',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_tool] (
    [id] int NOT NULL IDENTITY,
    [shop_id] int NOT NULL,
    [name] varchar(200) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [asset_no] varchar(64) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [spec] varchar(200) COLLATE Chinese_PRC_CI_AS NULL,
    [quantity] int NOT NULL,
    [area_id] int NULL,
    [status] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [owner_staff_id] int NULL,
    [daily_check] bit NOT NULL,
    [last_check_date] date NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [created_at] datetime2(3) NOT NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_tool] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_tool_value] CHECK (quantity > 0 AND status IN ('normal','missing','damaged','repairing','disposed')),
    CONSTRAINT [FK_fnb_v4_tool_fnb_v4_area_area_id] FOREIGN KEY ([area_id]) REFERENCES [dbo].[fnb_v4_area] ([id]),
    CONSTRAINT [FK_fnb_v4_tool_shop_list_shop_id] FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_tool',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'shop_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'asset_no') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'spec') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'quantity') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'area_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'owner_staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'daily_check') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'last_check_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'created_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool',N'row_version') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_tool 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_supply_movement',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_supply_movement] (
    [id] bigint NOT NULL IDENTITY,
    [supply_id] int NOT NULL,
    [request_id] uniqueidentifier NOT NULL,
    [movement_type] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [input_qty] decimal(19,6) NOT NULL,
    [quantity] decimal(19,6) NOT NULL,
    [balance_qty] decimal(19,6) NOT NULL,
    [reason] varchar(600) COLLATE Chinese_PRC_CI_AS NULL,
    [cancelled] bit NOT NULL,
    [staff_id] int NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    CONSTRAINT [PK_fnb_v4_supply_movement] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_supply_movement_value] CHECK (quantity > 0 AND balance_qty >= 0 AND movement_type IN ('in','out','waste')),
    CONSTRAINT [FK_fnb_v4_supply_movement_fnb_v4_supply_supply_id] FOREIGN KEY ([supply_id]) REFERENCES [dbo].[fnb_v4_supply] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'supply_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'request_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'movement_type') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'input_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'quantity') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'balance_qty') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'reason') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'cancelled') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_supply_movement',N'created_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_supply_movement 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_check_item',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_check_item] (
    [id] int NOT NULL IDENTITY,
    [area_id] int NOT NULL,
    [name] varchar(200) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [kind] varchar(20) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [method] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [required] bit NOT NULL,
    [photo_suggested] bit NOT NULL,
    [unit] varchar(40) COLLATE Chinese_PRC_CI_AS NULL,
    [minimum] decimal(19,6) NULL,
    [maximum] decimal(19,6) NULL,
    [tool_id] int NULL,
    [supply_id] int NULL,
    [valid] bit NOT NULL DEFAULT CAST(1 AS bit),
    [updated_at] datetime2(3) NOT NULL,
    CONSTRAINT [PK_fnb_v4_check_item] PRIMARY KEY ([id]),
    CONSTRAINT [CK_fnb_v4_check_item_value] CHECK (method IN ('yes_no','number','photo') AND (minimum IS NULL OR maximum IS NULL OR minimum <= maximum)),
    CONSTRAINT [FK_fnb_v4_check_item_fnb_v4_area_area_id] FOREIGN KEY ([area_id]) REFERENCES [dbo].[fnb_v4_area] ([id]),
    CONSTRAINT [FK_fnb_v4_check_item_fnb_v4_supply_supply_id] FOREIGN KEY ([supply_id]) REFERENCES [dbo].[fnb_v4_supply] ([id]),
    CONSTRAINT [FK_fnb_v4_check_item_fnb_v4_tool_tool_id] FOREIGN KEY ([tool_id]) REFERENCES [dbo].[fnb_v4_tool] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_check_item',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'area_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'name') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'kind') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'method') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'required') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'photo_suggested') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'unit') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'minimum') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'maximum') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'tool_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'supply_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'valid') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_item',N'updated_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_check_item 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_tool_log',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_tool_log] (
    [id] bigint NOT NULL IDENTITY,
    [tool_id] int NOT NULL,
    [from_status] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [to_status] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [from_area_id] int NULL,
    [to_area_id] int NULL,
    [remark] varchar(600) COLLATE Chinese_PRC_CI_AS NULL,
    [staff_id] int NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    CONSTRAINT [PK_fnb_v4_tool_log] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_tool_log_fnb_v4_tool_tool_id] FOREIGN KEY ([tool_id]) REFERENCES [dbo].[fnb_v4_tool] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_tool_log',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'tool_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'from_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'to_status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'from_area_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'to_area_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'remark') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_tool_log',N'created_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_tool_log 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_check_line',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_check_line] (
    [id] bigint NOT NULL IDENTITY,
    [sheet_id] bigint NOT NULL,
    [item_id] int NOT NULL,
    [snapshot_json] varchar(4000) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [active] bit NOT NULL,
    [result] varchar(16) COLLATE Chinese_PRC_CI_AS NULL,
    [value] decimal(19,6) NULL,
    [reason] varchar(1000) COLLATE Chinese_PRC_CI_AS NULL,
    [upload_id] int NULL,
    [bulk] bit NOT NULL,
    [staff_id] int NULL,
    [updated_at] datetime2(3) NULL,
    CONSTRAINT [PK_fnb_v4_check_line] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_check_line_fnb_v4_check_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_v4_check_item] ([id]),
    CONSTRAINT [FK_fnb_v4_check_line_fnb_v4_check_sheet_sheet_id] FOREIGN KEY ([sheet_id]) REFERENCES [dbo].[fnb_v4_check_sheet] ([id]),
    CONSTRAINT [FK_fnb_v4_check_line_mini_upload_upload_id] FOREIGN KEY ([upload_id]) REFERENCES [dbo].[mini_upload] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_check_line',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'sheet_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'item_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'snapshot_json') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'active') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'result') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'value') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'reason') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'upload_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'bulk') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_line',N'updated_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_check_line 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_alert_delivery',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_alert_delivery] (
    [batch_id] int NOT NULL,
    [business_date] date NOT NULL,
    [status] varchar(16) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [attempted_at] datetime2(3) NOT NULL,
    [receivers] varchar(1000) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [message_id] varchar(200) COLLATE Chinese_PRC_CI_AS NULL,
    [error] varchar(1000) COLLATE Chinese_PRC_CI_AS NULL,
    [row_version] rowversion NOT NULL,
    CONSTRAINT [PK_fnb_v4_alert_delivery] PRIMARY KEY ([batch_id], [business_date]),
    CONSTRAINT [FK_fnb_v4_alert_delivery_fnb_v4_batch_batch_id] FOREIGN KEY ([batch_id]) REFERENCES [dbo].[fnb_v4_batch] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'business_date') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'status') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'attempted_at') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'receivers') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'message_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'error') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_alert_delivery',N'row_version') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_alert_delivery 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_batch_detail',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_batch_detail] (
    [batch_id] int NOT NULL,
    [area_id] int NULL,
    [open_storage] varchar(20) COLLATE Chinese_PRC_CI_AS NULL,
    [open_days] int NULL,
    CONSTRAINT [PK_fnb_v4_batch_detail] PRIMARY KEY ([batch_id]),
    CONSTRAINT [FK_fnb_v4_batch_detail_fnb_v4_area_area_id] FOREIGN KEY ([area_id]) REFERENCES [dbo].[fnb_v4_area] ([id]),
    CONSTRAINT [FK_fnb_v4_batch_detail_fnb_v4_batch_batch_id] FOREIGN KEY ([batch_id]) REFERENCES [dbo].[fnb_v4_batch] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_batch_detail',N'batch_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch_detail',N'area_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch_detail',N'open_storage') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_batch_detail',N'open_days') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_batch_detail 结构不完整，停止且不覆盖。',1;

IF OBJECT_ID(N'dbo.fnb_v4_check_handling',N'U') IS NULL
BEGIN
CREATE TABLE [dbo].[fnb_v4_check_handling] (
    [id] bigint NOT NULL IDENTITY,
    [line_id] bigint NOT NULL,
    [remark] varchar(1000) COLLATE Chinese_PRC_CI_AS NOT NULL,
    [staff_id] int NOT NULL,
    [created_at] datetime2(3) NOT NULL,
    CONSTRAINT [PK_fnb_v4_check_handling] PRIMARY KEY ([id]),
    CONSTRAINT [FK_fnb_v4_check_handling_fnb_v4_check_line_line_id] FOREIGN KEY ([line_id]) REFERENCES [dbo].[fnb_v4_check_line] ([id])
);
END
ELSE IF COL_LENGTH(N'dbo.fnb_v4_check_handling',N'id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_handling',N'line_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_handling',N'remark') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_handling',N'staff_id') IS NULL OR COL_LENGTH(N'dbo.fnb_v4_check_handling',N'created_at') IS NULL
 THROW 51001,N'已有扩展表 fnb_v4_check_handling 结构不完整，停止且不覆盖。',1;

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_area') AND name=N'IX_fnb_v4_area_parent_id')
CREATE INDEX [IX_fnb_v4_area_parent_id] ON [dbo].[fnb_v4_area] ([parent_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_area') AND name=N'IX_fnb_v4_area_shop_id_parent_id_name')
CREATE UNIQUE INDEX [IX_fnb_v4_area_shop_id_parent_id_name] ON [dbo].[fnb_v4_area] ([shop_id], [parent_id], [name]) WHERE [valid] = 1;

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_area_image') AND name=N'IX_fnb_v4_area_image_upload_id')
CREATE INDEX [IX_fnb_v4_area_image_upload_id] ON [dbo].[fnb_v4_area_image] ([upload_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_batch_detail') AND name=N'IX_fnb_v4_batch_detail_area_id')
CREATE INDEX [IX_fnb_v4_batch_detail_area_id] ON [dbo].[fnb_v4_batch_detail] ([area_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_handling') AND name=N'IX_fnb_v4_check_handling_line_id')
CREATE INDEX [IX_fnb_v4_check_handling_line_id] ON [dbo].[fnb_v4_check_handling] ([line_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_item') AND name=N'IX_fnb_v4_check_item_area_id')
CREATE INDEX [IX_fnb_v4_check_item_area_id] ON [dbo].[fnb_v4_check_item] ([area_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_item') AND name=N'IX_fnb_v4_check_item_supply_id')
CREATE INDEX [IX_fnb_v4_check_item_supply_id] ON [dbo].[fnb_v4_check_item] ([supply_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_item') AND name=N'IX_fnb_v4_check_item_tool_id')
CREATE INDEX [IX_fnb_v4_check_item_tool_id] ON [dbo].[fnb_v4_check_item] ([tool_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_line') AND name=N'IX_fnb_v4_check_line_item_id')
CREATE INDEX [IX_fnb_v4_check_line_item_id] ON [dbo].[fnb_v4_check_line] ([item_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_line') AND name=N'IX_fnb_v4_check_line_sheet_id_item_id')
CREATE UNIQUE INDEX [IX_fnb_v4_check_line_sheet_id_item_id] ON [dbo].[fnb_v4_check_line] ([sheet_id], [item_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_line') AND name=N'IX_fnb_v4_check_line_upload_id')
CREATE INDEX [IX_fnb_v4_check_line_upload_id] ON [dbo].[fnb_v4_check_line] ([upload_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_check_sheet') AND name=N'IX_fnb_v4_check_sheet_shop_id_business_date')
CREATE UNIQUE INDEX [IX_fnb_v4_check_sheet_shop_id_business_date] ON [dbo].[fnb_v4_check_sheet] ([shop_id], [business_date]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_supply') AND name=N'IX_fnb_v4_supply_area_id')
CREATE INDEX [IX_fnb_v4_supply_area_id] ON [dbo].[fnb_v4_supply] ([area_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_supply') AND name=N'IX_fnb_v4_supply_shop_id_name')
CREATE UNIQUE INDEX [IX_fnb_v4_supply_shop_id_name] ON [dbo].[fnb_v4_supply] ([shop_id], [name]) WHERE [valid] = 1;

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_supply_movement') AND name=N'IX_fnb_v4_supply_movement_supply_id_request_id')
CREATE UNIQUE INDEX [IX_fnb_v4_supply_movement_supply_id_request_id] ON [dbo].[fnb_v4_supply_movement] ([supply_id], [request_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_tool') AND name=N'IX_fnb_v4_tool_area_id')
CREATE INDEX [IX_fnb_v4_tool_area_id] ON [dbo].[fnb_v4_tool] ([area_id]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_tool') AND name=N'IX_fnb_v4_tool_shop_id_asset_no')
CREATE UNIQUE INDEX [IX_fnb_v4_tool_shop_id_asset_no] ON [dbo].[fnb_v4_tool] ([shop_id], [asset_no]);

IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.fnb_v4_tool_log') AND name=N'IX_fnb_v4_tool_log_tool_id')
CREATE INDEX [IX_fnb_v4_tool_log_tool_id] ON [dbo].[fnb_v4_tool_log] ([tool_id]);

COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
