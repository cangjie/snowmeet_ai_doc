-- 2026-06-30 会员管理：标签库字典表 member_tag_preset（可后台维护的预设标签）
-- 区别于 member_tag（某会员实际打的标签）。GetTagLibrary 接口读这张表。
-- 生产库 snowmeet_new。建表 + 灌入初始 13 个标签（沿用设计稿三组）。

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'member_tag_preset')
BEGIN
    CREATE TABLE member_tag_preset (
        id          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        tag         NVARCHAR(50)   NOT NULL,
        group_name  NVARCHAR(50)   NULL,          -- 客户价值 / 服务关系 / 偏好
        sort        INT            NOT NULL DEFAULT 0,
        valid       BIT            NOT NULL DEFAULT 1,
        create_date DATETIME       NOT NULL DEFAULT GETDATE()
    );

    INSERT INTO member_tag_preset (tag, group_name, sort) VALUES
        (N'VIP',       N'客户价值', 10),
        (N'高净值',    N'客户价值', 20),
        (N'老客户',    N'客户价值', 30),
        (N'潜在客户',  N'客户价值', 40),
        (N'教练',      N'服务关系', 50),
        (N'团体客户',  N'服务关系', 60),
        (N'需回访',    N'服务关系', 70),
        (N'投诉记录',  N'服务关系', 80),
        (N'黑名单',    N'服务关系', 90),
        (N'双板',      N'偏好',     100),
        (N'单板',      N'偏好',     110),
        (N'装备控',    N'偏好',     120),
        (N'亲子',      N'偏好',     130);
END
