-- 2026-06-30 会员管理：自定义标签表 member_tag
-- 生产库 snowmeet_new。系统标签按参与业务派生（不入库），此表仅存「自定义标签」。
-- 已由会员管理功能在生产库直接建表，本文件留作备查 / 跨机重建。

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'member_tag')
BEGIN
    CREATE TABLE member_tag (
        id          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        member_id   INT            NOT NULL,
        tag         NVARCHAR(50)   NOT NULL,
        staff_id    INT            NULL,           -- 打标签的店员
        valid       BIT            NOT NULL DEFAULT 1,
        create_date DATETIME       NOT NULL DEFAULT GETDATE()
    );
    CREATE INDEX ix_member_tag_member ON member_tag (member_id, valid);
END
