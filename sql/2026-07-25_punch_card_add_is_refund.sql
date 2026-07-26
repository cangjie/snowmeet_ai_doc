-- 2026-07-25 次卡退款：punch_card 增加「已退款」标志位
--
-- 背景：顾客在「我的次卡 → 某张卡」详情页，若这张卡一次都没核销过，可以自助申请退款。
--      退款成功后置 is_refund=1，该卡在所有核销入口一律不可用，界面上置灰显示「已退款」。
--
-- 为什么用标志位而不是删行/置 valid=0：
--      punch_card 没有 valid 列，且这张卡的销售记录（retail）与退款记录（payment_refund）
--      都要留痕，卡本身也要在「我的次卡」里能看到「已退款」状态，不能凭空消失。
--
-- 兼容性：NOT NULL DEFAULT 0，存量卡全部视为未退款，无需回填。
--
-- ⚠️ 执行顺序：必须先在生产库执行本脚本，再 publish SnowmeetApi。
--    EF 加了字段后所有 punch_card 查询都会 SELECT 该列，不先加列会让次卡相关查询全部报错
--    （同 punch_card.total 可空化 / order_payment.customer_open_date 的既往教训）。

ALTER TABLE punch_card ADD is_refund BIT NOT NULL DEFAULT 0;
GO

-- 验证：应返回一行，DATA_TYPE = bit，IS_NULLABLE = NO
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'punch_card' AND COLUMN_NAME = 'is_refund';
GO

-- 验证：存量卡应全部为 0（未退款）
SELECT is_refund, COUNT(*) AS cnt FROM punch_card GROUP BY is_refund;
GO
