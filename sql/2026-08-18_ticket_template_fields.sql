-- 2026-08-18  优惠券模板维护页面：接活 biz_type / available_days / discount_* 三个死字段
--
-- 背景：这几列 DB 里一直有，但代码零读取方。发券只抄 template.expire_date（为空写 9999-12-31），
-- 开单选券过滤的是 ticket.biz_type（券自己的列）+ 一个 template_id==12 的硬编码补丁，
-- 养护定价只读 fixed_price + 一处 template_id==16 的硬编码立减。
--
-- ⚠️ 分四段，**逐段执行 + 逐段复查**，不要整个文件一次跑完。
--    段 1/2 必须先于后端新版本部署（模型已按可空映射）；段 3/4 必须先于后端新版本部署
--    （否则开单会一张券都选不到、南山老顾客券会丢立减）。

----------------------------------------------------------------------
-- 段 1：available_days 改可空
----------------------------------------------------------------------
-- 原本是 int NOT NULL，用 0 表示"未设置"。改造后 0 是非法值（ValidateTemplate 会拒），
-- 语义统一成 NULL = 不按天数算。
ALTER TABLE ticket_template ALTER COLUMN available_days int NULL;
GO

UPDATE ticket_template SET available_days = NULL WHERE available_days = 0;   -- 模板 15 觅计划消费券
GO

-- 复查：应返回 0 行
SELECT id, name, available_days FROM ticket_template WHERE available_days = 0;
GO


----------------------------------------------------------------------
-- 段 2：消歧 5 个「可用天数与总过期日同时非设」的模板
----------------------------------------------------------------------
-- 现状（2026-08-18 生产实测）：
--   id=1  22-23雪季内购券   100天 + 2020-09-01   已隐藏，2021 年后没再发过券
--   id=10 养护双项         3650天 + 2035-12-31   保留固定截止日
--   id=12 免费打蜡券          6天 + 2024-12-07   ★ 唯一还在大量发券的（近一年 979 张）
--   id=13 大疆体验券          6天 + 2024-12-07   已停用
--   id=14 试滑券             6天 + 2024-12-07   已停用
--
-- ★ 模板 12 两个值都是死值，必须**都清空**：
--   它的券到期日完全由调用方显式传参决定——雪票取卡 ActiveSkipassTicket 写 start+1天、
--   转赠回赠写雪季末 2027-04-30。模板上的 6 天从没生效过；expire_date 2024-12-07
--   更是已过期一年半的僵尸值（任何抄它的新路径都会当场发出一张过期券）。
--   若只清 available_days 而留 expire_date，接活后新券会一落库就过期。
UPDATE ticket_template SET available_days = NULL, expire_date = NULL WHERE id = 12;
GO

-- 其余四个保留固定截止日，清掉可用天数
UPDATE ticket_template SET available_days = NULL WHERE id IN (1, 10, 13, 14);
GO

-- 复查：应返回 0 行
SELECT id, name, available_days, expire_date FROM ticket_template
WHERE available_days IS NOT NULL AND expire_date IS NOT NULL;
GO


----------------------------------------------------------------------
-- 段 3：biz_type 回填（决定开单流程能选到哪些券）
----------------------------------------------------------------------
-- 等价性已在生产库验证：现在 ticket.biz_type='养护' 的 10087 张券，所属模板集合
-- 正好是 type='养护券' 的那 9 个 (5,6,8,10,11,12,16,17,18)。回填后开单可选券集合与今天 1:1 相同。
-- 模板 12 另有 4 张 biz_type 为 NULL 的券——正是那个 template_id==12 硬编码补丁在兜底，
-- 改按模板过滤后自然覆盖，补丁可以删掉。
UPDATE ticket_template SET biz_type = N'养护' WHERE type = N'养护券';
GO

-- 租赁券 13/14（大疆体验券、试滑券）一并回填。取值域是 零售/养护/租赁/餐饮 四选一
-- （与 [order].type 对齐），没有"都不参与"这一档，留空的模板在任何开单页都选不到。
-- 实际影响为零：养护开单的选券弹层是目前唯一的消费方，它传的 bizType 恒为"养护"，
-- 这两个模板本来就选不到；而且它们已停发（最后一次发券 2024-12 / 2025-03）。
UPDATE ticket_template SET biz_type = N'租赁' WHERE type = N'租赁券';
GO

-- 剩下 7 个模板（满减券9 / 消费券15 / 内购券1 / 兑换券7 / 暖宝券2 / 儿童成长计划3 / 新手礼包4）
-- 的 type 不对应任何业务线，故意留 NULL。它们在维护页上会打「未设业务类型」橙标，
-- 第一次编辑时会被强制选一个。其中 6 个早已停发，只有满减券9（2012 张）是 2024-12 停的。

-- 复查：两个集合必须完全相同
SELECT id FROM ticket_template WHERE biz_type = N'养护' ORDER BY id;
SELECT DISTINCT template_id FROM ticket WHERE biz_type = N'养护' ORDER BY template_id;
GO


----------------------------------------------------------------------
-- 段 4：定价通用化的配套数据
----------------------------------------------------------------------
-- 4a. 老顾客券(16)：原来的立减 20/30 是 CareController 里按 template_id==16 硬编码的，
--     **不看门店**；而 product_ticket_template 只给模板 16 配了万龙的 139/140/143。
--     改成按商品读 discount_amount 后南山会丢立减，所以先补上，保证行为完全不变。
--     （生产实测老顾客券 110 次核销全在万龙服务中心，南山从没用过，属于预防性补齐。）
INSERT INTO product_ticket_template (product_id, ticket_template_id, discount_amount, valid, create_date)
VALUES (677, 16, 30, 1, GETDATE()),   -- 南山修刃打蜡（双项）
       (678, 16, 20, 1, GETDATE()),   -- 南山修刃
       (679, 16, 20, 1, GETDATE());   -- 南山打蜡
GO

-- 4b. 清脏数据：id 1/2/3 是模板 12 的规则，fixed_price=120/80/50 同时 discount_amount=1.0。
--     一口价优先级更高，这个 1.0 今天不生效、通用化后也不会生效，但留着会在维护页上误导人。
UPDATE product_ticket_template SET discount_amount = NULL
WHERE id IN (1, 2, 3) AND fixed_price IS NOT NULL;
GO

-- 复查：模板 16 应有 6 条规则（万龙 3 + 南山 3），模板 12 的 6 条规则 discount_amount 应全为 NULL
SELECT p.ticket_template_id, p.product_id, pr.name, p.fixed_price, p.discount_rate, p.discount_amount
FROM product_ticket_template p LEFT JOIN product pr ON pr.id = p.product_id
WHERE p.ticket_template_id IN (12, 16) AND p.valid = 1
ORDER BY p.ticket_template_id, p.product_id;
GO
