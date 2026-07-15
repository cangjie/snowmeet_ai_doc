-- 食材过期提醒：食材批次台账表（2026-07-15，设计见 docs/superpowers/specs/2026-07-15-fnb-mat-expire-design.md）
-- 单店（餐饮），不设 shop 字段；状态（已过期/今日/临期/正常/已处理）不落库，按 expire_date/warn_days/dispose_status 实时派生
CREATE TABLE fnb_material_batch (
    id               INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name             NVARCHAR(100)  NOT NULL,                -- 食材名称，如 鲜牛奶（巴氏）
    batch_no         VARCHAR(50)    NOT NULL,                -- 批次号，自动发号 B{yyMMdd}-{当日序号2位} 或手输；不设唯一约束（手输允许重复）
    produce_date     DATE           NULL,                    -- 生产日期（选填，用于推算到期日）
    shelf_life_value INT            NULL,                    -- 保质期数值（选填）
    shelf_life_unit  NVARCHAR(10)   NULL,                    -- 保质期单位：天 / 月
    expire_date      DATE           NOT NULL,                -- 到期日期（真理之源，自动推算后可手改）
    warn_days        INT            NOT NULL DEFAULT 3,      -- 到期预警提前天数（临期判定：今天 < 到期 <= 今天+warn_days）
    image_ids        VARCHAR(500)   NULL,                    -- 现场照片，upload_file.id 逗号分隔（选填、低频，不另建关联表）
    dispose_status   NVARCHAR(10)   NULL,                    -- NULL=在库；用完 / 报废（两者都归「已处理」）
    dispose_userid   VARCHAR(64)    NULL,                    -- 处置人（企微 UserId）
    dispose_date     DATETIME       NULL,                    -- 处置时间
    create_userid    VARCHAR(64)    NULL,                    -- 录入人（企微 UserId，OAuth 获得）
    valid            INT            NOT NULL DEFAULT 1,      -- 软删标记（删除=0，与 order/care 等表同约定）
    create_date      DATETIME       NOT NULL DEFAULT GETDATE(),
    update_date      DATETIME       NULL
);

-- 列表按到期日排序 + 定时扫临期都走这条索引
CREATE INDEX IX_fnb_material_batch_expire ON fnb_material_batch (valid, expire_date) INCLUDE (dispose_status);
-- 批次号搜索
CREATE INDEX IX_fnb_material_batch_batch_no ON fnb_material_batch (batch_no);
