-- 2026-08-20  店员分享发券：分享批次表 + 领取记录表
--
-- ⚠️ **必须先于后端新版本部署**（新增两张表 + 两个 EF 实体）。
--
-- 员工发券三条途径之二「分享小程序卡片」。两种模式统一走这两张表：
--   personal 分享给好友 —— max_claims = 1，一张卡片只有第一个点开的人能领
--   group    分享到群   —— max_claims 为空（不限人数），但每人只能领一张
--
-- 为什么不复用顾客转赠那条链路：转赠的关注校验场景值是
-- ticket_gift_{券码}_{分享时间}，死死绑在**单张已存在的券**上，多人各领一张套不进去。
-- 统一走批次后，顾客转赠完全不受影响，且每次分享/每次领取都有据可查，便于日后分析。

CREATE TABLE ticket_share_batch (
    id            int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    template_id   int           NOT NULL,              -- 分享的券模板
    staff_id      int           NOT NULL,              -- 发起分享的店员，领到的券也记在他名下
    share_type    varchar(10)   NOT NULL,              -- personal | group
    max_claims    int           NULL,                  -- 领取上限；personal 恒为 1，group 为空表示不限
    claim_count   int           NOT NULL CONSTRAINT DF_tsb_claim_count DEFAULT 0,  -- 已领取数（冗余计数，列表直接读）
    valid         int           NOT NULL CONSTRAINT DF_tsb_valid       DEFAULT 1,  -- 0 = 已撤回
    create_date   datetime      NOT NULL CONSTRAINT DF_tsb_create_date DEFAULT GETDATE(),
    update_date   datetime      NULL
);
GO

CREATE INDEX IX_tsb_staff ON ticket_share_batch (staff_id, create_date);
GO

-- 领取记录：既用来做「每人只能领一张」的去重，也是行为分析的原始数据
CREATE TABLE ticket_share_claim (
    id            int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    batch_id      int           NOT NULL,
    member_id     int           NOT NULL,              -- 领取人
    ticket_code   varchar(20)   NOT NULL,              -- 领到的那张券
    create_date   datetime      NOT NULL CONSTRAINT DF_tsc_create_date DEFAULT GETDATE()
);
GO

-- 同一批次同一个人只能领一次，靠唯一索引在库层面兜底（并发下两个请求同时进来也不会重复发券）
CREATE UNIQUE INDEX UX_tsc_batch_member ON ticket_share_claim (batch_id, member_id);
GO
CREATE INDEX IX_tsc_code ON ticket_share_claim (ticket_code);
GO

-- 复查
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('ticket_share_batch', 'ticket_share_claim')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
GO
