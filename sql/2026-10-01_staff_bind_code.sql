-- 2026-10-01 员工账号管理：一次性绑定码 + 自助登记待开通记录。
-- 用途（purpose）：
--   private   管理员生成，员工用私人手机的微信扫码，把这套手机号 + 微信关联到 staff_id；30 分钟有效、只能用一次
--   job_phone 管理员生成，用工作手机上的微信扫码，给 social_account_id 这部工作手机补上微信；30 分钟有效、只能用一次
--   selfreg   员工经公众号入职码自助登记后的待开通记录；开通时写 used_date，拒绝时写 cancel_date
-- staff / staff_social_account / social_account_for_job 三张表结构不变。
--
-- 执行顺序：先执行本脚本，再部署同版本 SnowmeetApi（新版员工账号接口读写这张表）。
-- 由用户审阅后手动执行；已执行过会直接报错退出，不会重复改动。
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
    IF OBJECT_ID(N'dbo.staff_social_account', N'U') IS NULL OR OBJECT_ID(N'dbo.social_account_for_job', N'U') IS NULL
        THROW 51001, N'当前数据库没有员工表，请确认选对了业务数据库。', 1;
    IF OBJECT_ID(N'dbo.staff_bind_code', N'U') IS NOT NULL
        THROW 51002, N'本脚本已执行过：dbo.staff_bind_code 已存在。', 1;

    BEGIN TRANSACTION;

    CREATE TABLE [dbo].[staff_bind_code] (
        [id] INT IDENTITY(1, 1) NOT NULL,
        [token] VARCHAR(32) NOT NULL,                 -- 二维码里带的随机串（Guid N 格式）
        [purpose] VARCHAR(16) NOT NULL,               -- private / job_phone / selfreg
        [staff_id] INT NULL,                          -- private、selfreg：员工账号
        [social_account_id] INT NULL,                 -- job_phone：工作手机；selfreg：登记的私人手机
        [created_by_staff_id] INT NOT NULL,           -- 生成的管理员；自助登记为 0
        [create_date] DATETIME NOT NULL CONSTRAINT [DF_staff_bind_code_create_date] DEFAULT (GETDATE()),
        [expire_date] DATETIME NOT NULL,
        [used_date] DATETIME NULL,
        [cancel_date] DATETIME NULL,
        CONSTRAINT [PK_staff_bind_code] PRIMARY KEY CLUSTERED ([id]),
        CONSTRAINT [UQ_staff_bind_code_token] UNIQUE ([token]),
        CONSTRAINT [CK_staff_bind_code_purpose] CHECK ([purpose] IN ('private', 'job_phone', 'selfreg'))
    );
    CREATE INDEX [IX_staff_bind_code_staff_id] ON [dbo].[staff_bind_code] ([staff_id]);
    CREATE INDEX [IX_staff_bind_code_social_account_id] ON [dbo].[staff_bind_code] ([social_account_id]);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

-- 核对（只读）：新表存在且为空
EXEC (N'SELECT COUNT(*) AS staff_bind_code_rows FROM [dbo].[staff_bind_code];');
