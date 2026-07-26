-- 2026-07-25 次卡/季卡商品：使用规则改为后台可编辑
--
-- 背景：顾客端次卡详情页「使用规则」卡片原本是写死在小程序里的三条文案
--      （N 次核销 / 无使用期限 / 本人专属），后台改不了。改为在商品维护页
--      （pages/admin/rent/punchcard_products/punchcard_product_detail）用富文本编辑，
--      存进 product.usage_rules，顾客端 rich-text 渲染。
--
-- 兼容性：新列可空。存量商品该列为 NULL，顾客端自动回退到原来那三条默认规则，
--        不会显示空白，因此本次迁移不需要回填任何数据。
--
-- ⚠️ 执行顺序：必须先在生产库执行本脚本，再 publish SnowmeetApi。
--    EF 加了字段后所有 product 查询都会 SELECT 该列，不先加列会让商品相关查询全部报错
--    （同 punch_card / order_payment.customer_open_date 的既往教训）。

ALTER TABLE product ADD usage_rules NVARCHAR(MAX) NULL;
GO

-- 验证：应返回一行，DATA_TYPE = nvarchar，IS_NULLABLE = YES
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'product' AND COLUMN_NAME = 'usage_rules';
GO
