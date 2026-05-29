-- 2026-05-29: mini_session 加 wechat_openid + wechat_unionid 字段
--
-- 背景:
--   MemberLogin 重构为「不自动建 stub member」后, 未注册用户的 openid + unionid 没地方存。
--   暂存到 mini_session 表,等用户点支付按钮时由 PaymentIdentityController 用这俩字段建会员。
--
-- 兼容性:
--   两列均为 NULL 默认, SQL Server 上 ADD COLUMN NULL 是 online 操作(立刻完成、零锁表)。
--   现有 row 这两列保持 NULL, 不影响旧逻辑(_resolveStatus 用 sessionKey 反查 mini_session.member_id 的路径不变)。
--
-- 执行方式: 在 prod DB(100.28.143.19, snowmeet_new) 上低峰期执行。

ALTER TABLE mini_session ADD wechat_openid NVARCHAR(64) NULL;
GO

ALTER TABLE mini_session ADD wechat_unionid NVARCHAR(64) NULL;
GO

-- 验证: 应该看到两列已加
-- SELECT TOP 1 session_key, session_type, member_id, wechat_openid, wechat_unionid, valid, expire_date FROM mini_session;

-- 回滚(如需):
-- ALTER TABLE mini_session DROP COLUMN wechat_openid;
-- ALTER TABLE mini_session DROP COLUMN wechat_unionid;
