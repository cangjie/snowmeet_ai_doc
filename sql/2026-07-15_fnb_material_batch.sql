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

-- 提醒发送记录：每次企微推送、每个被提醒的批次一行（同一次推送多批次共享同一 msgid）。
-- 用途：批次维度「提醒过几次/最后提醒时间」展示 + 当天已提醒去重（防重复骚扰）+ 推送失败排查
CREATE TABLE fnb_material_alert_log (
    id            INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    batch_id      INT            NOT NULL,                -- fnb_material_batch.id
    alert_status  NVARCHAR(10)   NOT NULL,                -- 提醒时点状态快照：临期 / 今日 / 已过期
    expire_date   DATE           NOT NULL,                -- 到期日快照（批次事后被改/删仍可追溯当时依据）
    touser        NVARCHAR(200)  NOT NULL DEFAULT '@all', -- 企微接收人（@all 或 userid|userid…）
    msgid         VARCHAR(100)   NULL,                    -- 企微返回 msgid（同次推送多批次共享）
    success       INT            NOT NULL DEFAULT 0,      -- 1=企微返回 errcode=0
    err_msg       NVARCHAR(200)  NULL,                    -- 失败时记 errcode+errmsg
    send_userid   VARCHAR(64)    NULL,                    -- 触发人企微 UserId（定时任务触发=NULL）
    create_date   DATETIME       NOT NULL DEFAULT GETDATE()
);

-- 「该批次最近一次提醒」+ 当天去重查询
CREATE INDEX IX_fnb_material_alert_log_batch ON fnb_material_alert_log (batch_id, create_date);
