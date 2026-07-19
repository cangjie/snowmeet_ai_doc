-- 2026-07-16 食材过期提醒：批次表加录入人 staff_id + 员工企微号 MSA 录入模板
-- ⚠️ 部署顺序：先在生产库 snowmeet_new 执行本 DDL，再 publish SnowmeetApi
--（EF 模型已加 staff_id 字段，所有 fnb_material_batch 查询会 SELECT 该列，不先加列查询全挂）

-- 1) 批次表加录入人 staff_id（可空；企微 UserId 关联不上 staff 时留 NULL）
ALTER TABLE fnb_material_batch ADD staff_id INT NULL;

-- 2) 员工企微号录入模板（每个使用该 H5 的员工一条）：
--    member_social_account 加 type='wecom' 记录，num = 企业微信 UserId。
--    关联链路：企微 UserId → msa(type='wecom') → member_id → social_account_for_job → staff_social_account → staff
--    ⚠️ member_id 必须是该员工 social_account_for_job.member_id 指向的那个会员号，否则链路断在第二跳。
-- INSERT INTO member_social_account (member_id, type, num, valid, memo, create_date)
-- VALUES ({member_id}, 'wecom', N'{企微UserId}', 1, N'企业微信 UserId', GETDATE());

-- 员工的企微 UserId 查法：企微管理后台「通讯录→成员详情→账号」，
-- 或该员工打开过 H5 后查 mini_session：
-- SELECT TOP 5 wechat_openid, create_date FROM mini_session
-- WHERE session_type = 'wecom_userid' ORDER BY id DESC;
