-- 2026-08-20  ticket_template 增加 sharable（是否允许店员分享发券）
--
-- ⚠️ **必须先于后端新版本部署**。这一列一旦进 EF 模型，EF 生成的 SQL 就会带上它，
--    DB 里没有会让 ticket_template 的所有查询报 "Invalid column name 'sharable'"，
--    优惠券模块整体不可用（顾客端券列表、开单选券、模板设置、优惠券管理全挂）。
--
-- 语义：员工发券三条途径之一「分享小程序卡片给微信好友」的开关，逐个模板控制。
--   0 = 不可分享（默认）—— 模板设置页不出现分享按钮，分享接口也会拒绝
--   1 = 可分享
-- 默认 0 是有意的：像「非雪季赠双项」这类随单自动发的券，误分享就是白送一张。
-- 需要哪个模板可分享，在「优惠券模板 → 模板设置」页上逐个打开。

ALTER TABLE ticket_template ADD sharable int NOT NULL CONSTRAINT DF_ticket_template_sharable DEFAULT 0;
GO

-- 复查：所有模板都应是 0
SELECT id, name, type, biz_type, hide, valid, sharable FROM ticket_template ORDER BY hide, id;
GO
