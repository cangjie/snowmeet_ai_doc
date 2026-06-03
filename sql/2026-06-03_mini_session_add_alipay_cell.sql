-- 2026-06-03: mini_session 加 alipay_payerid + cell 字段
--
-- 背景:
--   MemberLogin 支付宝分支增加「payerid 没命中 → 取手机号 → 用手机号反查 MSA cell → memberId」二次匹配链。
--   原 _alipayMemberLogin 把 payerId 塞进 wechat_openid 列是 hack, 新建独立列 alipay_payerid 承载,
--   并新增 cell 列暂存解密后的手机号(不一定写到 MSA, 看后续 PaymentIdentity 流程是否绑定)。
--
-- 兼容性:
--   两列均 NULL, SQL Server ADD COLUMN NULL 是 online 操作。
--   历史 session 这两列保持 NULL: PaymentIdentityController._loadSessionContext 改造时做兼容(优先看新列, fallback 旧 wechat_openid 列)。
--
-- 实际情况: prod DB 在 plan 阶段核实已加(用户口述), 本文件留备忘 + 跨机同步参考。
--   核实命令: SELECT TOP 0 alipay_payerid, cell FROM mini_session;
--   实际类型: alipay_payerid varchar(64) NULL, cell varchar(15) NULL (与下方 DDL 一致)
--
-- 执行方式: 若新机器/新环境缺列, 在 DB 上低峰期执行下方 ALTER。

ALTER TABLE mini_session ADD alipay_payerid NVARCHAR(64) NULL;
GO

ALTER TABLE mini_session ADD cell NVARCHAR(15) NULL;
GO

-- 验证: 应该看到两列已加
-- SELECT TOP 1 session_key, session_type, member_id, wechat_openid, wechat_unionid, alipay_payerid, cell, valid, expire_date FROM mini_session;

-- 回滚(如需):
-- ALTER TABLE mini_session DROP COLUMN alipay_payerid;
-- ALTER TABLE mini_session DROP COLUMN cell;
