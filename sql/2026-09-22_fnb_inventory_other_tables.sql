-- 食材管理其他表建表脚本（VARCHAR 版），SQL Server 2012+。
-- 已单独处理 dbo.[order] 来源字段时，在目标业务数据库执行本文件；不要再执行完整建表脚本。
-- 创建 17 张新表、外键、索引和 2 个视图；初始化 5 个基础计量单位。
-- 不修改旧表的字符列，不修改 dbo.[order]，不创建 CK_order_source_pair。
-- 新表 VARCHAR 使用简体中文代码页排序规则；长度按字节计，原 NVARCHAR(n) 改为 VARCHAR(2n)。
-- 字段说明：../docs/superpowers/specs/2026-09-21-fnb-inventory-schema-review.md
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
    IF ISNULL(COLLATIONPROPERTY(N'Chinese_PRC_CI_AS', N'CodePage'), 0) <> 936
       OR ISNULL(COLLATIONPROPERTY(N'Chinese_PRC_BIN2', N'CodePage'), 0) <> 936
        THROW 51005, N'当前 SQL Server 不支持本脚本所需的简体中文 VARCHAR 排序规则／代码页 936。', 1;

    -- 前置依赖：旧表已存在，id 为 INT 且具有单列唯一键。
    IF OBJECT_ID(N'dbo.fnb_material_batch', N'U') IS NULL OR NOT EXISTS (
        SELECT 1 FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.fnb_material_batch') AND c.name = N'id' AND c.system_type_id = 56
          AND EXISTS (SELECT 1 FROM sys.indexes AS ix
              JOIN sys.index_columns AS ic ON ic.object_id = ix.object_id AND ic.index_id = ix.index_id
              WHERE ix.object_id = c.object_id AND ix.is_unique = 1 AND ix.has_filter = 0
                AND ic.column_id = c.column_id AND ic.key_ordinal = 1
                AND NOT EXISTS (SELECT 1 FROM sys.index_columns AS ic2
                    WHERE ic2.object_id = ix.object_id AND ic2.index_id = ix.index_id AND ic2.key_ordinal > 1)))
        THROW 51001, N'前置依赖 dbo.fnb_material_batch 不存在或 id 类型／唯一键不符合预期；请核查实际数据库结构。', 1;
    IF OBJECT_ID(N'dbo.shop_list', N'U') IS NULL OR NOT EXISTS (
        SELECT 1 FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.shop_list') AND c.name = N'id' AND c.system_type_id = 56
          AND EXISTS (SELECT 1 FROM sys.indexes AS ix
              JOIN sys.index_columns AS ic ON ic.object_id = ix.object_id AND ic.index_id = ix.index_id
              WHERE ix.object_id = c.object_id AND ix.is_unique = 1 AND ix.has_filter = 0
                AND ic.column_id = c.column_id AND ic.key_ordinal = 1
                AND NOT EXISTS (SELECT 1 FROM sys.index_columns AS ic2
                    WHERE ic2.object_id = ix.object_id AND ic2.index_id = ix.index_id AND ic2.key_ordinal > 1)))
        THROW 51001, N'前置依赖 dbo.shop_list 不存在或 id 类型／唯一键不符合预期；请核查实际数据库结构。', 1;
    IF OBJECT_ID(N'dbo.staff', N'U') IS NULL OR NOT EXISTS (
        SELECT 1 FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.staff') AND c.name = N'id' AND c.system_type_id = 56
          AND EXISTS (SELECT 1 FROM sys.indexes AS ix
              JOIN sys.index_columns AS ic ON ic.object_id = ix.object_id AND ic.index_id = ix.index_id
              WHERE ix.object_id = c.object_id AND ix.is_unique = 1 AND ix.has_filter = 0
                AND ic.column_id = c.column_id AND ic.key_ordinal = 1
                AND NOT EXISTS (SELECT 1 FROM sys.index_columns AS ic2
                    WHERE ic2.object_id = ix.object_id AND ic2.index_id = ix.index_id AND ic2.key_ordinal > 1)))
        THROW 51001, N'前置依赖 dbo.staff 不存在或 id 类型／唯一键不符合预期；请核查实际数据库结构。', 1;
    IF OBJECT_ID(N'dbo.mini_upload', N'U') IS NULL OR NOT EXISTS (
        SELECT 1 FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.mini_upload') AND c.name = N'id' AND c.system_type_id = 56
          AND EXISTS (SELECT 1 FROM sys.indexes AS ix
              JOIN sys.index_columns AS ic ON ic.object_id = ix.object_id AND ic.index_id = ix.index_id
              WHERE ix.object_id = c.object_id AND ix.is_unique = 1 AND ix.has_filter = 0
                AND ic.column_id = c.column_id AND ic.key_ordinal = 1
                AND NOT EXISTS (SELECT 1 FROM sys.index_columns AS ic2
                    WHERE ic2.object_id = ix.object_id AND ic2.index_id = ix.index_id AND ic2.key_ordinal > 1)))
        THROW 51001, N'前置依赖 dbo.mini_upload 不存在或 id 类型／唯一键不符合预期；请核查实际数据库结构。', 1;
    IF OBJECT_ID(N'dbo.product', N'U') IS NULL OR NOT EXISTS (
        SELECT 1 FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.product') AND c.name = N'id' AND c.system_type_id = 56
          AND EXISTS (SELECT 1 FROM sys.indexes AS ix
              JOIN sys.index_columns AS ic ON ic.object_id = ix.object_id AND ic.index_id = ix.index_id
              WHERE ix.object_id = c.object_id AND ix.is_unique = 1 AND ix.has_filter = 0
                AND ic.column_id = c.column_id AND ic.key_ordinal = 1
                AND NOT EXISTS (SELECT 1 FROM sys.index_columns AS ic2
                    WHERE ic2.object_id = ix.object_id AND ic2.index_id = ix.index_id AND ic2.key_ordinal > 1)))
        THROW 51001, N'前置依赖 dbo.product 不存在或 id 类型／唯一键不符合预期；请核查实际数据库结构。', 1;
    IF OBJECT_ID(N'dbo.order', N'U') IS NULL OR NOT EXISTS (
        SELECT 1 FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.order') AND c.name = N'id' AND c.system_type_id = 56
          AND EXISTS (SELECT 1 FROM sys.indexes AS ix
              JOIN sys.index_columns AS ic ON ic.object_id = ix.object_id AND ic.index_id = ix.index_id
              WHERE ix.object_id = c.object_id AND ix.is_unique = 1 AND ix.has_filter = 0
                AND ic.column_id = c.column_id AND ic.key_ordinal = 1
                AND NOT EXISTS (SELECT 1 FROM sys.index_columns AS ic2
                    WHERE ic2.object_id = ix.object_id AND ic2.index_id = ix.index_id AND ic2.key_ordinal > 1)))
        THROW 51001, N'前置依赖 dbo.order 不存在或 id 类型／唯一键不符合预期；请核查实际数据库结构。', 1;
    IF OBJECT_ID(N'dbo.fd_order', N'U') IS NULL OR NOT EXISTS (
        SELECT 1 FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.fd_order') AND c.name = N'id' AND c.system_type_id = 56
          AND EXISTS (SELECT 1 FROM sys.indexes AS ix
              JOIN sys.index_columns AS ic ON ic.object_id = ix.object_id AND ic.index_id = ix.index_id
              WHERE ix.object_id = c.object_id AND ix.is_unique = 1 AND ix.has_filter = 0
                AND ic.column_id = c.column_id AND ic.key_ordinal = 1
                AND NOT EXISTS (SELECT 1 FROM sys.index_columns AS ic2
                    WHERE ic2.object_id = ix.object_id AND ic2.index_id = ix.index_id AND ic2.key_ordinal > 1)))
        THROW 51001, N'前置依赖 dbo.fd_order 不存在或 id 类型／唯一键不符合预期；请核查实际数据库结构。', 1;
    IF OBJECT_ID(N'dbo.fnb_unit') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_unit 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_material_category') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_material_category 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_shelf_life_rule') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_shelf_life_rule 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_material_item') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_material_item 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_material_batch_stock') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_material_batch_stock 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_dish_spec') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_dish_spec 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_recipe') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_recipe 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_recipe_line') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_recipe_line 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_channel_shop') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_channel_shop 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_channel_dish_map') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_channel_dish_map 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_order') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_order 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_order_line') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_order_line 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_order_import') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_order_import 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_stock_document') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_stock_document 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_stock_document_line') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_stock_document_line 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_stock_movement') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_stock_movement 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.fnb_stocktake_line') IS NOT NULL
        THROW 51002, N'目标对象 dbo.fnb_stocktake_line 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.vw_fnb_material_stock') IS NOT NULL
        THROW 51002, N'目标对象 dbo.vw_fnb_material_stock 已存在；本审阅稿不覆盖已有对象。', 1;
    IF OBJECT_ID(N'dbo.vw_fnb_material_loss') IS NOT NULL
        THROW 51002, N'目标对象 dbo.vw_fnb_material_loss 已存在；本审阅稿不覆盖已有对象。', 1;

    BEGIN TRANSACTION;

    -- 01. fnb_unit：计量单位
    -- 定义录入单位与基本单位的换算；首版仅初始化克、千克、毫升、升、个。
    CREATE TABLE [dbo].[fnb_unit] (
        [code] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 单位编码：g、kg、ml、l、piece；主键
        [name] VARCHAR(40) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 显示名称：克、千克、毫升、升、个
        [dimension] TINYINT NOT NULL, -- 计量维度：1=重量，2=体积，3=个数；不同维度不能自动换算
        [factor_to_base] DECIMAL(18,6) NOT NULL, -- 1 个本单位对应的基本单位数量；kg=1000g，l=1000ml
        [valid] BIT NOT NULL DEFAULT (1), -- 是否启用；已被使用的换算比例不允许直接修改
        [sort] INT NOT NULL DEFAULT (0), -- 显示顺序
        CONSTRAINT [PK_fnb_unit] PRIMARY KEY ([code]),
        CONSTRAINT [CK_fnb_unit_1] CHECK (dimension IN (1,2,3)),
        CONSTRAINT [CK_fnb_unit_2] CHECK (factor_to_base > 0)
    );

    -- 02. fnb_material_category：食材两级分类
    -- 独立于销售商品分类；二级分类承载食材储存、提醒与计量默认值。
    CREATE TABLE [dbo].[fnb_material_category] (
        [id] INT IDENTITY(1,1) NOT NULL, -- 分类主键
        [parent_id] INT NULL, -- 一级分类为空；二级分类指向一级分类
        [level] TINYINT NOT NULL, -- 1=一级分类，2=二级分类；父级必须为一级，由应用校验
        [name] VARCHAR(100) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 分类名称
        [default_storage] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL, -- 二级分类建议储存：ambient=常温，chilled=冷藏，frozen=冷冻
        [default_unit_code] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NULL, -- 二级分类默认录入单位，关联 fnb_unit.code
        [warn_days] INT NULL, -- 二级分类默认提前预警天数；复制到批次后可单独调整
        [default_open_storage] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL, -- 默认开封后储存方式；实际值在入库时确认并保存在批次扩展表
        [default_open_days] INT NULL, -- 默认开封后天数；0=开封当日到期，空=没有默认值
        [sort] INT NOT NULL DEFAULT (0), -- 显示顺序
        [valid] BIT NOT NULL DEFAULT (1), -- 启用标记；停用不删除历史关系
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [updated_at] DATETIME2(3) NULL, -- 最后修改时间，UTC
        CONSTRAINT [PK_fnb_material_category] PRIMARY KEY ([id]),
        CONSTRAINT [CK_fnb_material_category_1] CHECK ((level = 1 AND parent_id IS NULL) OR (level = 2 AND parent_id IS NOT NULL)),
        CONSTRAINT [CK_fnb_material_category_2] CHECK (parent_id IS NULL OR parent_id <> id),
        CONSTRAINT [CK_fnb_material_category_3] CHECK ((level = 1 AND default_storage IS NULL AND default_unit_code IS NULL AND warn_days IS NULL AND default_open_storage IS NULL AND default_open_days IS NULL) OR (level = 2 AND default_storage IS NOT NULL AND default_storage IN ('ambient','chilled','frozen') AND default_unit_code IS NOT NULL AND warn_days IS NOT NULL AND warn_days >= 0)),
        CONSTRAINT [CK_fnb_material_category_4] CHECK (default_open_storage IS NULL OR default_open_storage IN ('ambient','chilled','frozen')),
        CONSTRAINT [CK_fnb_material_category_5] CHECK (default_open_days IS NULL OR default_open_days >= 0)
    );

    -- 03. fnb_shelf_life_rule：分类保质期规则
    -- 一行表示一个二级分类、储存方式和生产月份，避免跨年月份区间重叠。
    CREATE TABLE [dbo].[fnb_shelf_life_rule] (
        [id] INT IDENTITY(1,1) NOT NULL, -- 规则主键
        [category_id] INT NOT NULL, -- 二级分类 ID；应用校验 level=2
        [storage_type] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL, -- ambient=常温，chilled=冷藏，frozen=冷冻
        [production_month] TINYINT NOT NULL, -- 生产月份，1～12；不分季节时配置 12 行相同规则
        [shelf_life_value] INT NOT NULL, -- 默认保质期数值，必须大于 0
        [shelf_life_unit] VARCHAR(10) COLLATE Chinese_PRC_CI_AS NOT NULL, -- day=天，month=月；写入旧批次字段时映射为中文天／月
        [remark] VARCHAR(600) COLLATE Chinese_PRC_CI_AS NULL, -- 规则依据及说明；本脚本不预设实际食材保质期
        [valid] BIT NOT NULL DEFAULT (1), -- 当前是否启用；批次保存自己的效期快照
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [updated_at] DATETIME2(3) NULL, -- 修改时间，UTC
        CONSTRAINT [PK_fnb_shelf_life_rule] PRIMARY KEY ([id]),
        CONSTRAINT [CK_fnb_shelf_life_rule_1] CHECK (storage_type IN ('ambient','chilled','frozen')),
        CONSTRAINT [CK_fnb_shelf_life_rule_2] CHECK (production_month BETWEEN 1 AND 12),
        CONSTRAINT [CK_fnb_shelf_life_rule_3] CHECK (shelf_life_value > 0),
        CONSTRAINT [CK_fnb_shelf_life_rule_4] CHECK (shelf_life_unit IN ('day','month'))
    );

    -- 04. fnb_material_item：食材品种档案
    -- 一个品种对应多个库存批次；包含原料和半成品。与销售 product 分开。
    CREATE TABLE [dbo].[fnb_material_item] (
        [id] INT IDENTITY(1,1) NOT NULL, -- 食材品种主键
        [code] VARCHAR(64) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 系统食材编码，唯一且稳定
        [name] VARCHAR(200) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 食材名称，例如高筋面粉、Pizza 面团
        [category_id] INT NOT NULL, -- 所属二级食材分类
        [item_type] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL, -- raw=原料，prepared=半成品
        [base_unit_code] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 唯一库存基本单位：g、ml、piece；有库存或流水后不可修改
        [default_input_unit_code] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 默认录入／显示单位，例如库存用 g、界面默认显示 kg
        [image_id] INT NULL, -- 档案参考图片，关联现有 mini_upload.id；不能替代入库现场照片
        [remark] VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL, -- 食材说明
        [valid] BIT NOT NULL DEFAULT (1), -- 是否启用；历史食材只能停用
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [updated_at] DATETIME2(3) NULL, -- 修改时间，UTC
        CONSTRAINT [PK_fnb_material_item] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_material_item_1] UNIQUE ([code]),
        CONSTRAINT [CK_fnb_material_item_1] CHECK (item_type IN ('raw','prepared')),
        CONSTRAINT [CK_fnb_material_item_2] CHECK (base_unit_code IN ('g','ml','piece'))
    );

    -- 05. fnb_material_batch_stock：批次库存扩展
    -- 以 batch_id 与现有 fnb_material_batch 一对一关联；原有批次 ID、效期、照片、提醒和二维码继续使用。
    CREATE TABLE [dbo].[fnb_material_batch_stock] (
        [batch_id] INT NOT NULL, -- 主键，同时关联 fnb_material_batch.id；本表不另发批次 ID
        [shop_id] INT NOT NULL, -- 库存所属门店，关联 shop_list.id
        [item_id] INT NOT NULL, -- 食材品种，关联 fnb_material_item.id
        [stock_form] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL, -- bulk=散装，sealed=未开封，opened=已开封，prepared=制作半成品
        [storage_type] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 本批次当前储存方式：ambient／chilled／frozen
        [storage_location] VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL, -- 储位文字，例如冷藏柜 A 层；首版不单建库位表
        [quantity] DECIMAL(18,6) NOT NULL DEFAULT (0), -- 在库数量，始终使用食材基本单位；封装也保存全部净含量
        [stock_amount] DECIMAL(19,6) NOT NULL DEFAULT (0), -- 本批次在库成本金额，人民币元；与流水同事务更新
        [pack_size] DECIMAL(18,6) NULL, -- sealed 必填：每件净含量，单位为该食材基本单位；其他形态为空
        [pack_unit_name] VARCHAR(40) COLLATE Chinese_PRC_CI_AS NULL, -- sealed 必填：瓶／袋／盒等包装单位，仅用于显示
        [sealed_pack_count] AS (CASE WHEN stock_form = 'sealed' THEN CONVERT(DECIMAL(18,6), quantity / NULLIF(pack_size, 0)) ELSE NULL END) PERSISTED, -- 计算列：未开封件数；约束保证是整件
        [parent_batch_id] INT NULL, -- opened 必填：来源未开封批次；与当前批次门店、食材一致
        [opened_date] DATE NULL, -- opened 必填：上海时区的开封日期，用于同日合并与效期计算
        [original_expire_date] DATE NOT NULL, -- 原包装／开封前到期日快照；手工确认的效期也写入此列
        [opened_expire_date] DATE NULL, -- opened 必填：开封日期加开封后天数计算出的到期日
        [open_storage_type] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL, -- sealed／opened 必填：确认的开封后储存方式快照
        [open_shelf_life_days] INT NULL, -- sealed／opened 必填：确认的开封后天数，允许 0 表示当日到期
        [shelf_life_rule_id] INT NULL, -- 计算参考的分类规则；手填或无对应规则时可为空
        [calculated_expire_date] DATE NULL, -- 根据生产日期与保质期推算的参考到期日，用于显示与手填值的差异
        [expiry_source] VARCHAR(24) COLLATE Chinese_PRC_CI_AS NOT NULL, -- manual=手填，package=包装／OCR确认，category=分类规则，estimated=折算参考，opened=开封计算
        [expiry_note] VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL, -- 效期来源、折算依据、人工确认或冲突说明
        [is_destroyed] BIT NOT NULL DEFAULT (0), -- 是否已确认销毁；为 1 时数量与成本必须为 0，业务上不可恢复
        [received_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 本批次进入库存时间，UTC；开封子批次记录其生成时间
        [updated_at] DATETIME2(3) NULL, -- 最近数量、成本或批次配置更新时间，UTC
        [row_version] ROWVERSION NOT NULL, -- 并发版本号，不是时间；更新库存时用于冲突检测
        CONSTRAINT [PK_fnb_material_batch_stock] PRIMARY KEY ([batch_id]),
        CONSTRAINT [UQ_fnb_material_batch_stock_1] UNIQUE ([batch_id], [shop_id], [item_id]),
        CONSTRAINT [CK_fnb_material_batch_stock_1] CHECK (stock_form IN ('bulk','sealed','opened','prepared')),
        CONSTRAINT [CK_fnb_material_batch_stock_2] CHECK (storage_type IN ('ambient','chilled','frozen')),
        CONSTRAINT [CK_fnb_material_batch_stock_3] CHECK (quantity >= 0 AND stock_amount >= 0),
        CONSTRAINT [CK_fnb_material_batch_stock_4] CHECK (quantity > 0 OR stock_amount = 0),
        CONSTRAINT [CK_fnb_material_batch_stock_5] CHECK (is_destroyed = 0 OR (quantity = 0 AND stock_amount = 0)),
        CONSTRAINT [CK_fnb_material_batch_stock_6] CHECK ((stock_form = 'sealed' AND pack_size IS NOT NULL AND pack_size > 0 AND pack_unit_name IS NOT NULL AND quantity % NULLIF(pack_size, 0) = 0) OR (stock_form <> 'sealed' AND pack_size IS NULL AND pack_unit_name IS NULL)),
        CONSTRAINT [CK_fnb_material_batch_stock_7] CHECK ((stock_form = 'opened' AND parent_batch_id IS NOT NULL AND opened_date IS NOT NULL AND opened_expire_date IS NOT NULL AND expiry_source = 'opened') OR (stock_form <> 'opened' AND parent_batch_id IS NULL AND opened_date IS NULL AND opened_expire_date IS NULL AND expiry_source <> 'opened')),
        CONSTRAINT [CK_fnb_material_batch_stock_8] CHECK (parent_batch_id IS NULL OR parent_batch_id <> batch_id),
        CONSTRAINT [CK_fnb_material_batch_stock_9] CHECK ((stock_form IN ('sealed','opened') AND open_storage_type IS NOT NULL AND open_shelf_life_days IS NOT NULL AND open_shelf_life_days >= 0) OR (stock_form IN ('bulk','prepared') AND open_storage_type IS NULL AND open_shelf_life_days IS NULL)),
        CONSTRAINT [CK_fnb_material_batch_stock_10] CHECK (open_storage_type IS NULL OR open_storage_type IN ('ambient','chilled','frozen')),
        CONSTRAINT [CK_fnb_material_batch_stock_11] CHECK (stock_form <> 'opened' OR storage_type = open_storage_type),
        CONSTRAINT [CK_fnb_material_batch_stock_12] CHECK (stock_form <> 'opened' OR opened_expire_date = DATEADD(day, open_shelf_life_days, opened_date)),
        CONSTRAINT [CK_fnb_material_batch_stock_13] CHECK (expiry_source IN ('manual','package','category','estimated','opened')),
        CONSTRAINT [CK_fnb_material_batch_stock_14] CHECK (expiry_source <> 'estimated' OR (expiry_note IS NOT NULL AND LEN(expiry_note) > 0))
    );

    -- 06. fnb_dish_spec：菜品规格
    -- 复用现有 product 作为菜品档案，一道菜有多个规格，每个规格独立维护配方。
    CREATE TABLE [dbo].[fnb_dish_spec] (
        [id] INT IDENTITY(1,1) NOT NULL, -- 规格主键
        [shop_id] INT NOT NULL, -- 规格所属门店；应用校验与 product.shop_id 一致
        [product_id] INT NOT NULL, -- 对应现有菜品 product.id；应用校验属于餐饮业务
        [spec_code] VARCHAR(64) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 菜品内部规格编码，例如 standard／large
        [name] VARCHAR(100) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 规格名称，例如标准份、大份
        [sale_price] DECIMAL(19,4) NULL, -- 规格参考售价，元；空时沿用 product.sale_price，不参与支付结算
        [legacy_product_id] INT NULL, -- 旧餐饮系统每个规格作为独立商品时，对应旧 product.id；用于旧 fd_order 映射
        [is_default] BIT NOT NULL DEFAULT (0), -- 是否默认规格；同一菜品最多一个启用的默认规格
        [valid] BIT NOT NULL DEFAULT (1), -- 是否启用
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [updated_at] DATETIME2(3) NULL, -- 修改时间，UTC
        CONSTRAINT [PK_fnb_dish_spec] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_dish_spec_1] UNIQUE ([id], [shop_id]),
        CONSTRAINT [UQ_fnb_dish_spec_2] UNIQUE ([product_id], [spec_code]),
        CONSTRAINT [CK_fnb_dish_spec_1] CHECK (sale_price IS NULL OR sale_price >= 0)
    );

    -- 07. fnb_recipe：配方版本
    -- 菜品规格配方与半成品制作配方共用；已发布版本不直接修改，变更创建新版本。
    CREATE TABLE [dbo].[fnb_recipe] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 配方版本主键
        [shop_id] INT NOT NULL, -- 配方所属门店
        [recipe_type] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL, -- dish=出餐配方，prep=半成品制作配方
        [dish_spec_id] INT NULL, -- dish 必填：菜品规格 ID；prep 为空
        [output_item_id] INT NULL, -- prep 必填：产出半成品食材 ID；dish 为空
        [output_qty] DECIMAL(18,6) NOT NULL, -- 一次配方的基准产量：dish 固定 1 份，prep 为产出食材基本单位数量
        [version_no] INT NOT NULL, -- 版本号，从 1 开始，在同一规格／半成品与门店下递增
        [status] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('draft'), -- draft=草稿，published=当前发布，retired=历史版本
        [remark] VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL, -- 配方说明
        [created_by_staff_id] INT NULL, -- 创建员工，关联 staff.id
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [published_at] DATETIME2(3) NULL, -- 发布时间，UTC；发布后记录保留
        [row_version] ROWVERSION NOT NULL, -- 配方编辑并发版本号
        CONSTRAINT [PK_fnb_recipe] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_recipe_1] UNIQUE ([id], [shop_id]),
        CONSTRAINT [UQ_fnb_recipe_2] UNIQUE ([id], [dish_spec_id], [shop_id]),
        CONSTRAINT [CK_fnb_recipe_1] CHECK ((recipe_type = 'dish' AND dish_spec_id IS NOT NULL AND output_item_id IS NULL AND output_qty = 1) OR (recipe_type = 'prep' AND dish_spec_id IS NULL AND output_item_id IS NOT NULL AND output_qty > 0)),
        CONSTRAINT [CK_fnb_recipe_2] CHECK (version_no > 0),
        CONSTRAINT [CK_fnb_recipe_3] CHECK (status IN ('draft','published','retired')),
        CONSTRAINT [CK_fnb_recipe_4] CHECK (status = 'draft' OR published_at IS NOT NULL)
    );

    -- 08. fnb_recipe_line：配方用料
    -- 配方关联食材品种，不直接绑定某个库存批次；实际扣料时再按 FEFO 选择可用批次。
    CREATE TABLE [dbo].[fnb_recipe_line] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 配方用料行主键
        [recipe_id] BIGINT NOT NULL, -- 配方版本 ID
        [item_id] INT NOT NULL, -- 原料或已有半成品的食材 ID
        [quantity] DECIMAL(18,6) NOT NULL, -- 完成 recipe.output_qty 产量所需的基本单位用量
        [sort] INT NOT NULL DEFAULT (0), -- 用料显示顺序
        [remark] VARCHAR(600) COLLATE Chinese_PRC_CI_AS NULL, -- 用料说明
        CONSTRAINT [PK_fnb_recipe_line] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_recipe_line_1] UNIQUE ([recipe_id], [item_id]),
        CONSTRAINT [CK_fnb_recipe_line_1] CHECK (quantity > 0)
    );

    -- 09. fnb_channel_shop：外卖门店映射
    -- 把平台门店映射到系统门店；API、网页与截图共用该映射，不按采集方式另建门店。
    CREATE TABLE [dbo].[fnb_channel_shop] (
        [id] INT IDENTITY(1,1) NOT NULL, -- 平台门店映射主键
        [shop_id] INT NOT NULL, -- 系统 shop_list.id
        [platform] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL, -- meituan=美团，eleme=饿了么／淘宝闪购
        [external_shop_id] VARCHAR(128) COLLATE Chinese_PRC_BIN2 NOT NULL, -- 平台门店 ID，按原始字符串保存，不转数字
        [external_shop_name] VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL, -- 平台门店名称快照
        [preferred_method] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL, -- api／web／ocr；仅方案配置，不代表接口已开通或采集已实现
        [valid] BIT NOT NULL DEFAULT (1), -- 是否启用同步
        [last_success_at] DATETIME2(3) NULL, -- 最近成功同步时间，UTC；用于识别同步中断
        [last_error] VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL, -- 最近同步错误摘要，不保存密钥、Cookie 或验证码
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [updated_at] DATETIME2(3) NULL, -- 修改时间，UTC
        CONSTRAINT [PK_fnb_channel_shop] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_channel_shop_1] UNIQUE ([id], [shop_id]),
        CONSTRAINT [UQ_fnb_channel_shop_2] UNIQUE ([platform], [external_shop_id]),
        CONSTRAINT [CK_fnb_channel_shop_1] CHECK (platform IN ('meituan','eleme')),
        CONSTRAINT [CK_fnb_channel_shop_2] CHECK (preferred_method IS NULL OR preferred_method IN ('api','web','ocr'))
    );

    -- 10. fnb_channel_dish_map：平台菜品规格映射
    -- 平台 SKU 与规范化选项组合映射到本店菜品规格；套餐、加料由订单适配器拆为可核销明细。
    CREATE TABLE [dbo].[fnb_channel_dish_map] (
        [id] INT IDENTITY(1,1) NOT NULL, -- 映射主键
        [shop_id] INT NOT NULL, -- 系统门店 ID，用复合外键保证两侧同店
        [channel_shop_id] INT NOT NULL, -- 平台门店映射 ID
        [external_sku_key] VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL, -- 平台商品／SKU 稳定标识；网页或 OCR 无标识时，人工确认后使用规范化业务键
        [option_key] VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL DEFAULT (''), -- 规格及选项的规范化键；无选项用空串，避免只按菜名误配
        [external_name] VARCHAR(300) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 平台菜品名称，用于核对与展示
        [options_text] VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL, -- 平台规格与加料描述，供人工核对
        [dish_spec_id] INT NOT NULL, -- 本系统菜品规格 ID
        [valid] BIT NOT NULL DEFAULT (1), -- 是否启用；停用记录不再自动匹配
        [confirmed_by_staff_id] INT NULL, -- 人工确认映射的员工 ID
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [updated_at] DATETIME2(3) NULL, -- 修改时间，UTC
        CONSTRAINT [PK_fnb_channel_dish_map] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_channel_dish_map_1] UNIQUE ([channel_shop_id], [external_sku_key], [option_key])
    );

    -- 11. fnb_order：厨房订单主表
    -- 统一承接现有系统餐饮单、导入的外卖单和人工单；供出餐核销使用。
    CREATE TABLE [dbo].[fnb_order] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 厨房订单主键
        [shop_id] INT NOT NULL, -- 所属门店
        [source_type] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL, -- internal=本站餐饮订单，external=平台订单，manual=人工厨房单
        [sales_order_id] INT NULL, -- internal/external 必填：现有 dbo.[order].id；manual 可为空
        [channel_shop_id] INT NULL, -- external 必填：平台门店映射 ID
        [external_order_no] VARCHAR(256) COLLATE Chinese_PRC_BIN2 NULL, -- external 必填：平台完整订单号；不能用每天重复的小票流水号替代
        [display_no] VARCHAR(128) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 展示单号／取餐号；不作为外卖去重依据
        [business_date] DATE NOT NULL, -- 上海时区营业日期，由服务端确定
        [ordered_at] DATETIME2(3) NOT NULL, -- 下单时间，UTC；导入时从平台时区转换
        [table_no] VARCHAR(100) COLLATE Chinese_PRC_CI_AS NULL, -- 堂食桌号或取餐位置
        [order_status] VARCHAR(24) COLLATE Chinese_PRC_CI_AS NOT NULL, -- pending=待接，accepted=已接，completed=平台完成，cancelled=取消；与库存出餐过账状态分开
        [platform_status] VARCHAR(100) COLLATE Chinese_PRC_CI_AS NULL, -- 平台原始状态文本／编码，便于适配及追溯
        [refund_status] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('none'), -- none=无退款，partial=部分退款，full=全额退款；不直接代表应恢复库存
        [total_amount] DECIMAL(19,4) NULL, -- 来源订单金额快照，元；仅展示，不用于本系统收款结算
        [refund_amount] DECIMAL(19,4) NULL, -- 来源退款金额快照，元；部分来源缺失时为空
        [review_status] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('pending'), -- pending=待核对，verified=已核对；完整可信 API 数据可由系统核对
        [remark] VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL, -- 订单制作备注，例如不要葱
        [source_updated_at] DATETIME2(3) NULL, -- 平台最后更新时间，UTC；用于防止旧消息覆盖新状态
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 首次进入本系统的时间，UTC
        [updated_at] DATETIME2(3) NULL, -- 本系统最后处理时间，UTC
        [row_version] ROWVERSION NOT NULL, -- 并发更新版本号
        CONSTRAINT [PK_fnb_order] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_order_1] UNIQUE ([id], [shop_id]),
        CONSTRAINT [CK_fnb_order_1] CHECK ((source_type = 'internal' AND sales_order_id IS NOT NULL AND channel_shop_id IS NULL AND external_order_no IS NULL) OR (source_type = 'external' AND sales_order_id IS NOT NULL AND channel_shop_id IS NOT NULL AND external_order_no IS NOT NULL AND LEN(external_order_no) > 0) OR (source_type = 'manual' AND sales_order_id IS NULL AND channel_shop_id IS NULL AND external_order_no IS NULL)),
        CONSTRAINT [CK_fnb_order_2] CHECK (order_status IN ('pending','accepted','completed','cancelled')),
        CONSTRAINT [CK_fnb_order_3] CHECK (refund_status IN ('none','partial','full')),
        CONSTRAINT [CK_fnb_order_4] CHECK (review_status IN ('pending','verified')),
        CONSTRAINT [CK_fnb_order_5] CHECK (total_amount IS NULL OR total_amount >= 0),
        CONSTRAINT [CK_fnb_order_6] CHECK (refund_amount IS NULL OR refund_amount >= 0)
    );

    -- 12. fnb_order_line：厨房订单明细
    -- 保存菜品、规格与数量快照；套餐容器行不核销，拆出的实际菜品／加料行才关联配方。
    CREATE TABLE [dbo].[fnb_order_line] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 订单明细主键
        [order_id] BIGINT NOT NULL, -- 厨房订单 ID
        [shop_id] INT NOT NULL, -- 门店，用复合外键约束订单与规格同店
        [line_key] VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL, -- 单内稳定明细键；有平台明细 ID 时使用该 ID，否则由适配器规范化生成
        [parent_line_id] BIGINT NULL, -- 套餐／加料的父行 ID，必须属于同一订单
        [legacy_fd_order_id] INT NULL, -- 原有餐饮明细 fd_order.id，用于内部订单关联
        [external_sku_key] VARCHAR(256) COLLATE Chinese_PRC_BIN2 NULL, -- 平台菜品／SKU 标识
        [option_key] VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL DEFAULT (''), -- 规范化规格与选项键
        [item_name] VARCHAR(300) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 菜品名称快照
        [spec_name] VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL, -- 规格名称快照
        [options_text] VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL, -- 加料、套餐组成与选项说明
        [quantity] DECIMAL(18,6) NOT NULL, -- 本行总数量；套餐子行必须展开为整单实际总数量，不再重复乘父行数量
        [cancelled_qty] DECIMAL(18,6) NOT NULL DEFAULT (0), -- 未制作前已取消数量；退款数量不能未经核对直接写入
        [is_inventory_line] BIT NOT NULL DEFAULT (1), -- 1=需配方核销的食物行；0=套餐容器、包装费等非核销行
        [dish_spec_id] INT NULL, -- 匹配到的本店规格；未匹配时为空并阻止自动出餐核销
        [recipe_id] BIGINT NULL, -- 出餐时锁定的配方版本；后续改配方不影响已扣料记录
        [remark] VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL, -- 单行制作备注
        CONSTRAINT [PK_fnb_order_line] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_order_line_1] UNIQUE ([id], [order_id]),
        CONSTRAINT [UQ_fnb_order_line_2] UNIQUE ([order_id], [line_key]),
        CONSTRAINT [CK_fnb_order_line_1] CHECK (quantity > 0 AND cancelled_qty >= 0 AND cancelled_qty <= quantity),
        CONSTRAINT [CK_fnb_order_line_2] CHECK (parent_line_id IS NULL OR parent_line_id <> id),
        CONSTRAINT [CK_fnb_order_line_3] CHECK (recipe_id IS NULL OR (dish_spec_id IS NOT NULL AND is_inventory_line = 1)),
        CONSTRAINT [CK_fnb_order_line_4] CHECK (is_inventory_line = 1 OR (dish_spec_id IS NULL AND recipe_id IS NULL))
    );

    -- 13. fnb_order_import：订单采集与核对记录
    -- 承接 API 通知、网页采集和截图 OCR；无法确认订单号或明细的数据先留在这里待核对。
    CREATE TABLE [dbo].[fnb_order_import] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 采集记录主键
        [shop_id] INT NOT NULL, -- 目标门店
        [channel_shop_id] INT NULL, -- 外卖平台门店；内部导入可为空
        [source_method] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL, -- api、web、ocr、internal
        [dedupe_key] VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL, -- 本次事件／采集内容的规范化去重键；同一原始通知重试保持一致
        [order_id] BIGINT NULL, -- 成功匹配／创建的厨房订单；待核对或解析失败时可为空
        [upload_id] INT NULL, -- OCR 截图关联 mini_upload.id；多张截图分别记录，再匹配同一订单
        [raw_content] VARCHAR(MAX) COLLATE Chinese_PRC_CI_AS NULL, -- 经必要裁剪的原始订单数据／OCR 文本；不保存登录凭证和无关顾客信息
        [parsed_content] VARCHAR(MAX) COLLATE Chinese_PRC_CI_AS NULL, -- 待核对的结构化解析结果，JSON 文本；SQL Server 2012 下由应用校验格式
        [process_status] VARCHAR(24) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('pending'), -- pending=待处理，accepted=已导入，review=待人工核对，failed=失败，ignored=重复或旧消息
        [error_message] VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL, -- 失败原因、字段缺失或冲突说明
        [reviewed_by_staff_id] INT NULL, -- 人工核对员工
        [captured_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 采集时间，UTC
        [processed_at] DATETIME2(3) NULL, -- 最后处理时间，UTC
        CONSTRAINT [PK_fnb_order_import] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_order_import_1] UNIQUE ([shop_id], [channel_shop_id], [source_method], [dedupe_key]),
        CONSTRAINT [CK_fnb_order_import_1] CHECK (source_method IN ('api','web','ocr','internal')),
        CONSTRAINT [CK_fnb_order_import_2] CHECK (process_status IN ('pending','accepted','review','failed','ignored')),
        CONSTRAINT [CK_fnb_order_import_3] CHECK (source_method <> 'ocr' OR upload_id IS NOT NULL),
        CONSTRAINT [CK_fnb_order_import_4] CHECK (source_method = 'internal' OR channel_shop_id IS NOT NULL),
        CONSTRAINT [CK_fnb_order_import_5] CHECK (process_status <> 'accepted' OR (order_id IS NOT NULL AND processed_at IS NOT NULL)),
        CONSTRAINT [CK_fnb_order_import_6] CHECK (LEN(dedupe_key) > 0)
    );

    -- 14. fnb_stock_document：库存业务单据
    -- 入库、开封、制作、出餐、报损、盘点、期初接管统一使用单据头；一项业务一次原子过账。
    CREATE TABLE [dbo].[fnb_stock_document] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 库存单据主键
        [shop_id] INT NOT NULL, -- 业务门店
        [document_no] VARCHAR(80) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 系统库存单号，同店唯一；与包装上可重复的 batch_no 不同
        [document_type] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL, -- receipt=入库，open=开封，prep=制作，serve=出餐，waste=报损／销毁，stocktake=盘点，opening_balance=旧批次期初接管
        [status] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('draft'), -- draft=未过账，posted=已过账，void=未过账作废；已过账单不可直接改为作废
        [request_id] UNIQUEIDENTIFIER NOT NULL, -- 调用方同一次操作固定的请求 ID；重试不得生成新值
        [source_client] VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL, -- mini=小程序，wecom=企业微信，system=系统处理
        [business_date] DATE NOT NULL, -- 上海时区营业日期，由服务端确定
        [occurred_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 实际操作时间，UTC
        [order_id] BIGINT NULL, -- serve 必填：厨房订单 ID；同一订单仅允许一张已过账出餐单
        [recipe_id] BIGINT NULL, -- prep 必填：半成品配方版本 ID
        [reason_code] VARCHAR(32) COLLATE Chinese_PRC_CI_AS NULL, -- waste 必填：expiry=过期销毁，near_expiry=临期报损，damage=损坏，other=其他
        [reference_no] VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL, -- 入库送货单号或其他人工外部凭据
        [remark] VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL, -- 单据说明；零成本入库、盘盈成本和效期依据在此说明
        [created_by_staff_id] INT NULL, -- 发起员工；系统自动任务可为空
        [posted_by_staff_id] INT NULL, -- 确认过账员工；人工单过账时必填
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 创建时间，UTC
        [posted_at] DATETIME2(3) NULL, -- 成功过账时间，UTC；与批次更新、流水写入同事务
        [row_version] ROWVERSION NOT NULL, -- 单据并发版本号
        CONSTRAINT [PK_fnb_stock_document] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_stock_document_1] UNIQUE ([id], [shop_id]),
        CONSTRAINT [UQ_fnb_stock_document_2] UNIQUE ([shop_id], [document_no]),
        CONSTRAINT [UQ_fnb_stock_document_3] UNIQUE ([shop_id], [document_type], [request_id]),
        CONSTRAINT [CK_fnb_stock_document_1] CHECK (document_type IN ('receipt','open','prep','serve','waste','stocktake','opening_balance')),
        CONSTRAINT [CK_fnb_stock_document_2] CHECK (status IN ('draft','posted','void')),
        CONSTRAINT [CK_fnb_stock_document_3] CHECK (source_client IN ('mini','wecom','system')),
        CONSTRAINT [CK_fnb_stock_document_4] CHECK ((document_type = 'serve' AND order_id IS NOT NULL AND recipe_id IS NULL) OR (document_type = 'prep' AND recipe_id IS NOT NULL AND order_id IS NULL) OR (document_type NOT IN ('serve','prep') AND order_id IS NULL AND recipe_id IS NULL)),
        CONSTRAINT [CK_fnb_stock_document_5] CHECK ((document_type = 'waste' AND reason_code IS NOT NULL AND reason_code IN ('expiry','near_expiry','damage','other')) OR (document_type <> 'waste' AND reason_code IS NULL)),
        CONSTRAINT [CK_fnb_stock_document_6] CHECK ((status = 'posted' AND posted_at IS NOT NULL) OR (status <> 'posted' AND posted_at IS NULL)),
        CONSTRAINT [CK_fnb_stock_document_7] CHECK (source_client = 'system' OR (created_by_staff_id IS NOT NULL AND (status <> 'posted' OR posted_by_staff_id IS NOT NULL)))
    );

    -- 15. fnb_stock_document_line：库存单据用料／产出明细
    -- 记录每项业务计划量、实际量和成本；一行可由多个批次流水分摊。出餐按食材汇总，欠料保留在本表。
    CREATE TABLE [dbo].[fnb_stock_document_line] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 单据明细主键
        [document_id] BIGINT NOT NULL, -- 库存单据 ID
        [shop_id] INT NOT NULL, -- 门店，与单据和批次保持一致
        [line_no] INT NOT NULL, -- 单内行号
        [item_id] INT NOT NULL, -- 食材 ID
        [item_name] VARCHAR(200) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 发生业务时的食材名称快照
        [direction] SMALLINT NOT NULL, -- 1=库存增加，-1=库存减少；开封和制作同时有入、出两类行
        [input_qty] DECIMAL(18,6) NOT NULL, -- 用户／计算输入数量，例如 10 瓶、0.4 千克
        [input_unit_name] VARCHAR(40) COLLATE Chinese_PRC_CI_AS NOT NULL, -- 输入单位快照，例如瓶、千克、克
        [input_to_base] DECIMAL(18,6) NOT NULL, -- 1 个输入单位对应多少基本单位；10瓶×1000毫升=10000毫升
        [planned_qty] AS (CONVERT(DECIMAL(18,6), input_qty * input_to_base)) PERSISTED, -- 计算列：计划增加／减少数量，食材基本单位
        [actual_qty] DECIMAL(18,6) NOT NULL DEFAULT (0), -- 已实际执行数量，基本单位；为本行批次流水数量之和
        [shortage_qty] AS (CONVERT(DECIMAL(18,6), input_qty * input_to_base) - actual_qty) PERSISTED, -- 计算列：计划与实际差；仅已过账出餐出库行允许大于 0
        [input_unit_price] DECIMAL(19,6) NULL, -- 入库时每个输入单位的价格，元；制作／开封／出餐由实际成本计算
        [actual_amount] DECIMAL(19,6) NOT NULL DEFAULT (0), -- 已实际执行成本金额，元；为本行批次流水金额之和
        [specified_batch_id] INT NULL, -- 入库、开封、销毁等指定批次；出餐／盘亏可空，由 FEFO 分配
        [remark] VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL, -- 用料、欠料或价格说明
        CONSTRAINT [PK_fnb_stock_document_line] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_stock_document_line_1] UNIQUE ([document_id], [line_no]),
        CONSTRAINT [UQ_fnb_stock_document_line_2] UNIQUE ([id], [shop_id], [item_id], [direction]),
        CONSTRAINT [UQ_fnb_stock_document_line_3] UNIQUE ([id], [document_id], [shop_id], [item_id]),
        CONSTRAINT [CK_fnb_stock_document_line_1] CHECK (line_no > 0),
        CONSTRAINT [CK_fnb_stock_document_line_2] CHECK (direction IN (-1,1)),
        CONSTRAINT [CK_fnb_stock_document_line_3] CHECK (input_qty > 0 AND input_to_base > 0),
        CONSTRAINT [CK_fnb_stock_document_line_4] CHECK (CONVERT(DECIMAL(18,6), input_qty * input_to_base) > 0),
        CONSTRAINT [CK_fnb_stock_document_line_5] CHECK (actual_qty >= 0 AND actual_qty <= CONVERT(DECIMAL(18,6), input_qty * input_to_base)),
        CONSTRAINT [CK_fnb_stock_document_line_6] CHECK (actual_amount >= 0 AND (actual_qty > 0 OR actual_amount = 0)),
        CONSTRAINT [CK_fnb_stock_document_line_7] CHECK (input_unit_price IS NULL OR input_unit_price >= 0)
    );

    -- 16. fnb_stock_movement：批次库存流水
    -- 每个实际批次变动一行，是数量与成本追溯依据；过账后不可修改或删除。
    CREATE TABLE [dbo].[fnb_stock_movement] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 流水主键；可用于盘点快照后的变更检测
        [document_line_id] BIGINT NOT NULL, -- 库存单据明细 ID
        [shop_id] INT NOT NULL, -- 门店，与单据明细和批次的复合外键一致
        [item_id] INT NOT NULL, -- 食材 ID，与单据明细和批次一致
        [batch_id] INT NOT NULL, -- 实际发生变化的批次 ID
        [direction] SMALLINT NOT NULL, -- 1=增加，-1=减少；复合外键保证与单据明细方向一致
        [quantity] DECIMAL(18,6) NOT NULL, -- 本次变动数量的绝对值，使用食材基本单位，必须大于 0
        [amount] DECIMAL(19,6) NOT NULL, -- 本次变动成本绝对值，元；无成本时须显式写 0
        [delta_qty] AS (CONVERT(DECIMAL(18,6), direction * quantity)) PERSISTED, -- 计算列：带正负号的数量变化
        [delta_amount] AS (CONVERT(DECIMAL(19,6), direction * amount)) PERSISTED, -- 计算列：带正负号的成本变化
        [balance_qty] DECIMAL(18,6) NOT NULL, -- 本次操作后的批次数量快照，不能为负
        [balance_amount] DECIMAL(19,6) NOT NULL, -- 本次操作后的批次成本快照，不能为负；数量清零时成本也清零
        [created_at] DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME()), -- 流水写入时间，UTC；业务时间看单据 occurred_at
        CONSTRAINT [PK_fnb_stock_movement] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_stock_movement_1] UNIQUE ([document_line_id], [batch_id]),
        CONSTRAINT [UQ_fnb_stock_movement_2] UNIQUE ([id], [shop_id], [item_id]),
        CONSTRAINT [CK_fnb_stock_movement_1] CHECK (direction IN (-1,1) AND quantity > 0 AND amount >= 0),
        CONSTRAINT [CK_fnb_stock_movement_2] CHECK (balance_qty >= 0 AND balance_amount >= 0 AND (balance_qty > 0 OR balance_amount = 0)),
        CONSTRAINT [CK_fnb_stock_movement_3] CHECK (balance_qty - direction * quantity >= 0 AND balance_amount - direction * amount >= 0)
    );

    -- 17. fnb_stocktake_line：盘点快照与实盘数
    -- 保存盘点时点的系统可用量与实盘量；与盘点单据共用头表，差异通过库存明细和流水落实到批次。
    CREATE TABLE [dbo].[fnb_stocktake_line] (
        [id] BIGINT IDENTITY(1,1) NOT NULL, -- 盘点明细主键
        [document_id] BIGINT NOT NULL, -- 库存单据 ID；应用校验 document_type=stocktake
        [shop_id] INT NOT NULL, -- 盘点门店
        [item_id] INT NOT NULL, -- 盘点食材，基本单位由食材档案决定
        [system_qty] DECIMAL(18,6) NOT NULL, -- 快照时可用量；不含未开封及已过期、已销毁批次
        [counted_qty] DECIMAL(18,6) NULL, -- 实盘量，基本单位；未填写为空，确实没有库存填 0
        [difference_qty] AS (counted_qty - system_qty) PERSISTED, -- 计算列：正数盘盈、负数盘亏、0 无差异
        [snapshot_at] DATETIME2(3) NOT NULL, -- 取系统库存快照时间，UTC
        [snapshot_last_movement_id] BIGINT NULL, -- 快照时该门店该食材的最新流水 ID；无流水时空
        [snapshot_fingerprint] BINARY(32) NOT NULL, -- 服务端生成的 SHA-256 快照摘要，覆盖批次集合、版本、数量、效期、处置状态和营业日期；提交时重算比较
        [adjustment_line_id] BIGINT NULL, -- 盘点差异生成的库存单据明细；无差异时空，必须同单同店同食材
        [counted_by_staff_id] INT NULL, -- 实盘员工
        [counted_at] DATETIME2(3) NULL, -- 实盘记录时间，UTC
        [remark] VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL, -- 盘点差异说明；新建盘盈批次的效期与成本须另行确认
        [row_version] ROWVERSION NOT NULL, -- 盘点编辑并发版本号；不能代替库存快照校验
        CONSTRAINT [PK_fnb_stocktake_line] PRIMARY KEY ([id]),
        CONSTRAINT [UQ_fnb_stocktake_line_1] UNIQUE ([document_id], [item_id]),
        CONSTRAINT [CK_fnb_stocktake_line_1] CHECK (system_qty >= 0 AND (counted_qty IS NULL OR counted_qty >= 0)),
        CONSTRAINT [CK_fnb_stocktake_line_2] CHECK ((counted_qty IS NULL AND counted_at IS NULL AND counted_by_staff_id IS NULL) OR (counted_qty IS NOT NULL AND counted_at IS NOT NULL AND counted_by_staff_id IS NOT NULL)),
        CONSTRAINT [CK_fnb_stocktake_line_3] CHECK (adjustment_line_id IS NULL OR (counted_qty IS NOT NULL AND counted_qty <> system_qty))
    );

    -- 外键全部采用 NO ACTION；不使用级联删除，保留库存与订单追溯关系。
    ALTER TABLE [dbo].[fnb_material_category] WITH CHECK ADD CONSTRAINT [FK_fnb_material_category_1]
        FOREIGN KEY ([parent_id]) REFERENCES [dbo].[fnb_material_category] ([id]);
    ALTER TABLE [dbo].[fnb_material_category] WITH CHECK ADD CONSTRAINT [FK_fnb_material_category_2]
        FOREIGN KEY ([default_unit_code]) REFERENCES [dbo].[fnb_unit] ([code]);
    ALTER TABLE [dbo].[fnb_shelf_life_rule] WITH CHECK ADD CONSTRAINT [FK_fnb_shelf_life_rule_1]
        FOREIGN KEY ([category_id]) REFERENCES [dbo].[fnb_material_category] ([id]);
    ALTER TABLE [dbo].[fnb_material_item] WITH CHECK ADD CONSTRAINT [FK_fnb_material_item_1]
        FOREIGN KEY ([category_id]) REFERENCES [dbo].[fnb_material_category] ([id]);
    ALTER TABLE [dbo].[fnb_material_item] WITH CHECK ADD CONSTRAINT [FK_fnb_material_item_2]
        FOREIGN KEY ([base_unit_code]) REFERENCES [dbo].[fnb_unit] ([code]);
    ALTER TABLE [dbo].[fnb_material_item] WITH CHECK ADD CONSTRAINT [FK_fnb_material_item_3]
        FOREIGN KEY ([default_input_unit_code]) REFERENCES [dbo].[fnb_unit] ([code]);
    ALTER TABLE [dbo].[fnb_material_item] WITH CHECK ADD CONSTRAINT [FK_fnb_material_item_4]
        FOREIGN KEY ([image_id]) REFERENCES [dbo].[mini_upload] ([id]);
    ALTER TABLE [dbo].[fnb_material_batch_stock] WITH CHECK ADD CONSTRAINT [FK_fnb_material_batch_stock_1]
        FOREIGN KEY ([batch_id]) REFERENCES [dbo].[fnb_material_batch] ([id]);
    ALTER TABLE [dbo].[fnb_material_batch_stock] WITH CHECK ADD CONSTRAINT [FK_fnb_material_batch_stock_2]
        FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id]);
    ALTER TABLE [dbo].[fnb_material_batch_stock] WITH CHECK ADD CONSTRAINT [FK_fnb_material_batch_stock_3]
        FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_material_item] ([id]);
    ALTER TABLE [dbo].[fnb_material_batch_stock] WITH CHECK ADD CONSTRAINT [FK_fnb_material_batch_stock_4]
        FOREIGN KEY ([parent_batch_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_material_batch_stock] ([batch_id], [shop_id], [item_id]);
    ALTER TABLE [dbo].[fnb_material_batch_stock] WITH CHECK ADD CONSTRAINT [FK_fnb_material_batch_stock_5]
        FOREIGN KEY ([shelf_life_rule_id]) REFERENCES [dbo].[fnb_shelf_life_rule] ([id]);
    ALTER TABLE [dbo].[fnb_dish_spec] WITH CHECK ADD CONSTRAINT [FK_fnb_dish_spec_1]
        FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id]);
    ALTER TABLE [dbo].[fnb_dish_spec] WITH CHECK ADD CONSTRAINT [FK_fnb_dish_spec_2]
        FOREIGN KEY ([product_id]) REFERENCES [dbo].[product] ([id]);
    ALTER TABLE [dbo].[fnb_dish_spec] WITH CHECK ADD CONSTRAINT [FK_fnb_dish_spec_3]
        FOREIGN KEY ([legacy_product_id]) REFERENCES [dbo].[product] ([id]);
    ALTER TABLE [dbo].[fnb_recipe] WITH CHECK ADD CONSTRAINT [FK_fnb_recipe_1]
        FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id]);
    ALTER TABLE [dbo].[fnb_recipe] WITH CHECK ADD CONSTRAINT [FK_fnb_recipe_2]
        FOREIGN KEY ([dish_spec_id], [shop_id]) REFERENCES [dbo].[fnb_dish_spec] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_recipe] WITH CHECK ADD CONSTRAINT [FK_fnb_recipe_3]
        FOREIGN KEY ([output_item_id]) REFERENCES [dbo].[fnb_material_item] ([id]);
    ALTER TABLE [dbo].[fnb_recipe] WITH CHECK ADD CONSTRAINT [FK_fnb_recipe_4]
        FOREIGN KEY ([created_by_staff_id]) REFERENCES [dbo].[staff] ([id]);
    ALTER TABLE [dbo].[fnb_recipe_line] WITH CHECK ADD CONSTRAINT [FK_fnb_recipe_line_1]
        FOREIGN KEY ([recipe_id]) REFERENCES [dbo].[fnb_recipe] ([id]);
    ALTER TABLE [dbo].[fnb_recipe_line] WITH CHECK ADD CONSTRAINT [FK_fnb_recipe_line_2]
        FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_material_item] ([id]);
    ALTER TABLE [dbo].[fnb_channel_shop] WITH CHECK ADD CONSTRAINT [FK_fnb_channel_shop_1]
        FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id]);
    ALTER TABLE [dbo].[fnb_channel_dish_map] WITH CHECK ADD CONSTRAINT [FK_fnb_channel_dish_map_1]
        FOREIGN KEY ([channel_shop_id], [shop_id]) REFERENCES [dbo].[fnb_channel_shop] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_channel_dish_map] WITH CHECK ADD CONSTRAINT [FK_fnb_channel_dish_map_2]
        FOREIGN KEY ([dish_spec_id], [shop_id]) REFERENCES [dbo].[fnb_dish_spec] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_channel_dish_map] WITH CHECK ADD CONSTRAINT [FK_fnb_channel_dish_map_3]
        FOREIGN KEY ([confirmed_by_staff_id]) REFERENCES [dbo].[staff] ([id]);
    ALTER TABLE [dbo].[fnb_order] WITH CHECK ADD CONSTRAINT [FK_fnb_order_1]
        FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id]);
    ALTER TABLE [dbo].[fnb_order] WITH CHECK ADD CONSTRAINT [FK_fnb_order_2]
        FOREIGN KEY ([sales_order_id]) REFERENCES [dbo].[order] ([id]);
    ALTER TABLE [dbo].[fnb_order] WITH CHECK ADD CONSTRAINT [FK_fnb_order_3]
        FOREIGN KEY ([channel_shop_id], [shop_id]) REFERENCES [dbo].[fnb_channel_shop] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_order_line] WITH CHECK ADD CONSTRAINT [FK_fnb_order_line_1]
        FOREIGN KEY ([order_id], [shop_id]) REFERENCES [dbo].[fnb_order] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_order_line] WITH CHECK ADD CONSTRAINT [FK_fnb_order_line_2]
        FOREIGN KEY ([parent_line_id], [order_id]) REFERENCES [dbo].[fnb_order_line] ([id], [order_id]);
    ALTER TABLE [dbo].[fnb_order_line] WITH CHECK ADD CONSTRAINT [FK_fnb_order_line_3]
        FOREIGN KEY ([legacy_fd_order_id]) REFERENCES [dbo].[fd_order] ([id]);
    ALTER TABLE [dbo].[fnb_order_line] WITH CHECK ADD CONSTRAINT [FK_fnb_order_line_4]
        FOREIGN KEY ([dish_spec_id], [shop_id]) REFERENCES [dbo].[fnb_dish_spec] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_order_line] WITH CHECK ADD CONSTRAINT [FK_fnb_order_line_5]
        FOREIGN KEY ([recipe_id], [dish_spec_id], [shop_id]) REFERENCES [dbo].[fnb_recipe] ([id], [dish_spec_id], [shop_id]);
    ALTER TABLE [dbo].[fnb_order_import] WITH CHECK ADD CONSTRAINT [FK_fnb_order_import_1]
        FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id]);
    ALTER TABLE [dbo].[fnb_order_import] WITH CHECK ADD CONSTRAINT [FK_fnb_order_import_2]
        FOREIGN KEY ([channel_shop_id], [shop_id]) REFERENCES [dbo].[fnb_channel_shop] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_order_import] WITH CHECK ADD CONSTRAINT [FK_fnb_order_import_3]
        FOREIGN KEY ([order_id], [shop_id]) REFERENCES [dbo].[fnb_order] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_order_import] WITH CHECK ADD CONSTRAINT [FK_fnb_order_import_4]
        FOREIGN KEY ([upload_id]) REFERENCES [dbo].[mini_upload] ([id]);
    ALTER TABLE [dbo].[fnb_order_import] WITH CHECK ADD CONSTRAINT [FK_fnb_order_import_5]
        FOREIGN KEY ([reviewed_by_staff_id]) REFERENCES [dbo].[staff] ([id]);
    ALTER TABLE [dbo].[fnb_stock_document] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_1]
        FOREIGN KEY ([shop_id]) REFERENCES [dbo].[shop_list] ([id]);
    ALTER TABLE [dbo].[fnb_stock_document] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_2]
        FOREIGN KEY ([order_id], [shop_id]) REFERENCES [dbo].[fnb_order] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_stock_document] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_3]
        FOREIGN KEY ([recipe_id], [shop_id]) REFERENCES [dbo].[fnb_recipe] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_stock_document] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_4]
        FOREIGN KEY ([created_by_staff_id]) REFERENCES [dbo].[staff] ([id]);
    ALTER TABLE [dbo].[fnb_stock_document] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_5]
        FOREIGN KEY ([posted_by_staff_id]) REFERENCES [dbo].[staff] ([id]);
    ALTER TABLE [dbo].[fnb_stock_document_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_line_1]
        FOREIGN KEY ([document_id], [shop_id]) REFERENCES [dbo].[fnb_stock_document] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_stock_document_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_line_2]
        FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_material_item] ([id]);
    ALTER TABLE [dbo].[fnb_stock_document_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_document_line_3]
        FOREIGN KEY ([specified_batch_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_material_batch_stock] ([batch_id], [shop_id], [item_id]);
    ALTER TABLE [dbo].[fnb_stock_movement] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_movement_1]
        FOREIGN KEY ([document_line_id], [shop_id], [item_id], [direction]) REFERENCES [dbo].[fnb_stock_document_line] ([id], [shop_id], [item_id], [direction]);
    ALTER TABLE [dbo].[fnb_stock_movement] WITH CHECK ADD CONSTRAINT [FK_fnb_stock_movement_2]
        FOREIGN KEY ([batch_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_material_batch_stock] ([batch_id], [shop_id], [item_id]);
    ALTER TABLE [dbo].[fnb_stocktake_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stocktake_line_1]
        FOREIGN KEY ([document_id], [shop_id]) REFERENCES [dbo].[fnb_stock_document] ([id], [shop_id]);
    ALTER TABLE [dbo].[fnb_stocktake_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stocktake_line_2]
        FOREIGN KEY ([item_id]) REFERENCES [dbo].[fnb_material_item] ([id]);
    ALTER TABLE [dbo].[fnb_stocktake_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stocktake_line_3]
        FOREIGN KEY ([snapshot_last_movement_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_stock_movement] ([id], [shop_id], [item_id]);
    ALTER TABLE [dbo].[fnb_stocktake_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stocktake_line_4]
        FOREIGN KEY ([adjustment_line_id], [document_id], [shop_id], [item_id]) REFERENCES [dbo].[fnb_stock_document_line] ([id], [document_id], [shop_id], [item_id]);
    ALTER TABLE [dbo].[fnb_stocktake_line] WITH CHECK ADD CONSTRAINT [FK_fnb_stocktake_line_5]
        FOREIGN KEY ([counted_by_staff_id]) REFERENCES [dbo].[staff] ([id]);

    -- 唯一索引用于规则生效、订单身份、重复过账及开封同日合并。
    CREATE UNIQUE INDEX [IX_fnb_material_category_sibling_name] ON [dbo].[fnb_material_category] ([parent_id], [name]);
    CREATE UNIQUE INDEX [IX_fnb_shelf_life_rule_active_rule] ON [dbo].[fnb_shelf_life_rule] ([category_id], [storage_type], [production_month]) WHERE valid = 1;
    CREATE INDEX [IX_fnb_material_item_category] ON [dbo].[fnb_material_item] ([category_id], [valid]) INCLUDE ([name], [item_type], [base_unit_code]);
    CREATE INDEX [IX_fnb_material_batch_stock_stock_lookup] ON [dbo].[fnb_material_batch_stock] ([shop_id], [item_id], [stock_form]) INCLUDE ([quantity], [stock_amount], [is_destroyed], [storage_type]);
    CREATE UNIQUE INDEX [IX_fnb_material_batch_stock_opened_day] ON [dbo].[fnb_material_batch_stock] ([parent_batch_id], [opened_date], [storage_type]) WHERE stock_form = 'opened' AND is_destroyed = 0;
    CREATE UNIQUE INDEX [IX_fnb_dish_spec_default_spec] ON [dbo].[fnb_dish_spec] ([product_id]) WHERE is_default = 1 AND valid = 1;
    CREATE UNIQUE INDEX [IX_fnb_dish_spec_legacy_product] ON [dbo].[fnb_dish_spec] ([legacy_product_id]) WHERE legacy_product_id IS NOT NULL;
    CREATE UNIQUE INDEX [IX_fnb_recipe_dish_version] ON [dbo].[fnb_recipe] ([dish_spec_id], [version_no]) WHERE dish_spec_id IS NOT NULL;
    CREATE UNIQUE INDEX [IX_fnb_recipe_prep_version] ON [dbo].[fnb_recipe] ([shop_id], [output_item_id], [version_no]) WHERE output_item_id IS NOT NULL;
    CREATE UNIQUE INDEX [IX_fnb_recipe_published_dish] ON [dbo].[fnb_recipe] ([dish_spec_id]) WHERE dish_spec_id IS NOT NULL AND status = 'published';
    CREATE UNIQUE INDEX [IX_fnb_recipe_published_prep] ON [dbo].[fnb_recipe] ([shop_id], [output_item_id]) WHERE output_item_id IS NOT NULL AND status = 'published';
    CREATE UNIQUE INDEX [IX_fnb_order_external_order] ON [dbo].[fnb_order] ([channel_shop_id], [external_order_no]) WHERE external_order_no IS NOT NULL;
    CREATE UNIQUE INDEX [IX_fnb_order_sales_order] ON [dbo].[fnb_order] ([sales_order_id]) WHERE sales_order_id IS NOT NULL;
    CREATE INDEX [IX_fnb_order_kitchen_list] ON [dbo].[fnb_order] ([shop_id], [business_date], [order_status]) INCLUDE ([review_status], [display_no]);
    CREATE UNIQUE INDEX [IX_fnb_order_line_legacy_line] ON [dbo].[fnb_order_line] ([legacy_fd_order_id]) WHERE legacy_fd_order_id IS NOT NULL;
    CREATE INDEX [IX_fnb_order_import_pending] ON [dbo].[fnb_order_import] ([shop_id], [process_status], [captured_at]);
    CREATE UNIQUE INDEX [IX_fnb_stock_document_served_once] ON [dbo].[fnb_stock_document] ([order_id]) WHERE order_id IS NOT NULL AND status = 'posted';
    CREATE INDEX [IX_fnb_stock_document_business_date] ON [dbo].[fnb_stock_document] ([shop_id], [business_date], [document_type], [status]);
    CREATE INDEX [IX_fnb_stock_movement_item_history] ON [dbo].[fnb_stock_movement] ([shop_id], [item_id], [id]) INCLUDE ([batch_id], [direction], [quantity], [amount]);
    CREATE INDEX [IX_fnb_stock_movement_batch_history] ON [dbo].[fnb_stock_movement] ([batch_id], [id]);

    -- 只初始化计量单位，不写入分类示例、真实食材、门店、员工、订单或保质期规则。
    INSERT INTO [dbo].[fnb_unit] ([code], [name], [dimension], [factor_to_base], [sort]) VALUES
        ('g', N'克', 1, 1, 10), ('kg', N'千克', 1, 1000, 20),
        ('ml', N'毫升', 2, 1, 30), ('l', N'升', 2, 1000, 40), ('piece', N'个', 3, 1, 50);

    -- 按门店、食材汇总实物库存、可用库存、过期库存与加权平均成本
    -- 使用独立动态批次创建视图，使建表与视图创建处于同一事务。
    EXEC (N'CREATE VIEW [dbo].[vw_fnb_material_stock]
AS
SELECT s.shop_id, s.item_id, i.name AS item_name, i.category_id, i.base_unit_code,
       SUM(s.quantity) AS total_qty,
       SUM(s.stock_amount) AS total_amount,
       SUM(CASE WHEN s.stock_form = ''sealed'' THEN s.quantity ELSE CONVERT(DECIMAL(18,6), 0) END) AS sealed_qty,
       SUM(CASE WHEN b.valid = 1 AND s.stock_form <> ''sealed'' AND b.expire_date >= CONVERT(DATE, SWITCHOFFSET(SYSDATETIMEOFFSET(), ''+08:00''))
                AND b.dispose_status IS NULL AND s.is_destroyed = 0 THEN s.quantity ELSE CONVERT(DECIMAL(18,6), 0) END) AS available_qty,
       SUM(CASE WHEN b.expire_date < CONVERT(DATE, SWITCHOFFSET(SYSDATETIMEOFFSET(), ''+08:00'')) THEN s.quantity ELSE CONVERT(DECIMAL(18,6), 0) END) AS expired_qty,
       CONVERT(DECIMAL(19,6), SUM(s.stock_amount) / NULLIF(SUM(s.quantity), 0)) AS average_unit_cost,
       SUM(CASE WHEN s.quantity > 0 AND (b.valid = 0 OR b.dispose_status IS NOT NULL) THEN 1 ELSE 0 END) AS inconsistent_batch_count
FROM [dbo].[fnb_material_batch_stock] AS s
JOIN [dbo].[fnb_material_batch] AS b ON b.id = s.batch_id
JOIN [dbo].[fnb_material_item] AS i ON i.id = s.item_id
GROUP BY s.shop_id, s.item_id, i.name, i.category_id, i.base_unit_code;');

    -- 损耗与盘盈台账；保留带方向数量和成本，盘盈不当作损耗
    -- 使用独立动态批次创建视图，使建表与视图创建处于同一事务。
    EXEC (N'CREATE VIEW [dbo].[vw_fnb_material_loss]
AS
SELECT m.id AS movement_id, d.id AS document_id, d.document_no, d.shop_id, d.business_date,
       CASE WHEN d.document_type = ''stocktake'' AND m.direction = -1 THEN ''stocktake_loss''
            WHEN d.document_type = ''stocktake'' AND m.direction = 1 THEN ''stocktake_gain''
            ELSE d.reason_code END AS reason_code,
       m.item_id, l.item_name, m.batch_id, b.batch_no, i.base_unit_code,
       m.delta_qty, m.delta_amount, d.posted_by_staff_id, d.posted_at, d.remark
FROM [dbo].[fnb_stock_movement] AS m
JOIN [dbo].[fnb_stock_document_line] AS l ON l.id = m.document_line_id
JOIN [dbo].[fnb_stock_document] AS d ON d.id = l.document_id
JOIN [dbo].[fnb_material_batch] AS b ON b.id = m.batch_id
JOIN [dbo].[fnb_material_item] AS i ON i.id = m.item_id
WHERE d.status = ''posted'' AND d.document_type IN (''waste'',''stocktake'');');

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
