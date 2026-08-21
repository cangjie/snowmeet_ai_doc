-- 2026-08-21  员工发券途径之三：固定二维码扫码领券
--
-- ⚠️ **必须先于后端新版本部署**（改 EF 映射的两张表）。
--
-- 设计：复用 ticket_share_batch，share_type = 'qrcode'。
--   一个 (staff_id, template_id, channel) 组合 = 一张固定二维码 = 一条批次
--   scene = ticketqr_{batchId}，公众号永久二维码（QR_LIMIT_STR_SCENE）
--   max_claims = NULL（不限总数）
--
-- 限领口径（用户 2026-08-21 拍板）：**按模板算，一人一天一张**——
-- 直接查 ticket 表 (template_id + member_id + 当天)，不看是扫的哪张码，
-- 所以"换一个店员的码再领一次"这个口子是堵死的。

----------------------------------------------------------------------
-- 段 1：批次表加 channel（投放场景，与 ticket.channel 同义）
----------------------------------------------------------------------
ALTER TABLE ticket_share_batch ADD channel varchar(50) NULL;
GO

-- 同一个店员、同一模板、同一场景只该有一张码。已有 personal/group 批次 channel 为空，不受影响。
CREATE UNIQUE INDEX UX_tsb_qrcode ON ticket_share_batch (staff_id, template_id, channel)
    WHERE share_type = 'qrcode';
GO

----------------------------------------------------------------------
-- 段 2：领取记录按天去重
----------------------------------------------------------------------
-- 原索引是 (batch_id, member_id) —— 每人每批次只能领一次「总共」。
-- 二维码批次要允许同一个人不同天各领一次，所以去重维度必须加上日期。
-- personal/group 的「每人只能领一张」不受影响：那两种模式在应用层查的是
-- 「有没有领过」（不带日期），跨天照样拦得住；唯一索引只做同日并发兜底。
ALTER TABLE ticket_share_claim ADD claim_date date NOT NULL
    CONSTRAINT DF_tsc_claim_date DEFAULT CAST(GETDATE() AS date);
GO

-- 存量记录回填成各自的领取当天
UPDATE ticket_share_claim SET claim_date = CAST(create_date AS date);
GO

DROP INDEX UX_tsc_batch_member ON ticket_share_claim;
GO

CREATE UNIQUE INDEX UX_tsc_batch_member_date
    ON ticket_share_claim (batch_id, member_id, claim_date);
GO

----------------------------------------------------------------------
-- 复查
----------------------------------------------------------------------
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('ticket_share_batch', 'ticket_share_claim')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
GO

SELECT OBJECT_NAME(object_id) AS 表, name AS 索引, is_unique
FROM sys.indexes
WHERE OBJECT_NAME(object_id) IN ('ticket_share_batch', 'ticket_share_claim') AND name IS NOT NULL;
GO
