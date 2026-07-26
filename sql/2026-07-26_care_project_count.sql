-- 2026-07-26 养护次卡：区分单项 / 双项
--
-- 业务规则：
--   单项 = 该次核销可做「修刃」或「热蜡」（二选一）
--   双项 = 该次核销可做「修刃 + 热打蜡」
--
-- 现状问题：系统原本靠「卡名里含不含『双项』两个字」来判断
--   （CareController.ApplyDefaultServices：卡名含"双项" → 自动带出 修刃+热蜡+刮蜡）。
--   卡名是人工填的，改个字或换个叫法（历史上就有「双项10次卡」和「养护双项10次卡」两种写法）
--   就会判错，且商品维护页根本没有地方声明这个属性。
--
-- 改法：在商品上结构化声明，发卡/售卡时复制到卡上，核销时优先读该字段。
--   1 = 单项，2 = 双项，NULL = 不适用（租赁卡、养护季卡）或历史数据。
--   历史卡该字段为 NULL，核销逻辑会自动回退到原来的「卡名含双项」口径，行为不变，无需回填。
--
-- ⚠️ 执行顺序：必须先在生产库执行本脚本，再 publish SnowmeetApi。
--    EF 加了字段后所有 product / punch_card 查询都会 SELECT 这两列，不先加列会让相关查询全部报错
--    （同 punch_card.total 可空化 / order_payment.customer_open_date 的既往教训）。

ALTER TABLE product    ADD care_project_count INT NULL;
GO

ALTER TABLE punch_card ADD care_project_count INT NULL;
GO

-- 验证：应返回两行，DATA_TYPE = int，IS_NULLABLE = YES
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME = 'care_project_count' AND TABLE_NAME IN ('product', 'punch_card')
ORDER BY TABLE_NAME;
GO

-- ── 排查用（与本次迁移无关，用来定位「养护次卡添加不了」）──────────────────
-- 次卡/季卡商品的分类识别方式：product.category_code 命中 category 表中
-- biz_type ∈ {租赁,养护} 且 name ∈ {次卡,季卡} 且 valid=1 的行。
-- 下面这条应当返回 4 个组合各一行（租赁次卡/租赁季卡/养护次卡/养护季卡，缺的会在首次新增时自动建）。
-- 若「养护 + 次卡」这行缺失、valid=0、或 name 写成了「养护次卡」而不是「次卡」，
-- 商品维护页就取不到 category_code，保存会被前端拦在「分类未就绪」。
SELECT id, biz_type, name, code, valid, create_date
FROM category
WHERE name IN ('次卡', '季卡') OR code IN ('0101', '0102', '0201', '0202')
ORDER BY valid DESC, biz_type, name;
GO
