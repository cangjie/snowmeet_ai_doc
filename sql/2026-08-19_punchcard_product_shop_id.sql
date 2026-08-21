-- 2026-08-19  次卡/季卡商品的收款归属门店改由 shop_id 决定
--
-- ⚠️ 必须**先于**后端新版本部署。改造后 RentController 的自助购买接口按
--    product.shop_id 关联 shop_list 取收款门店，shop_id 为空会直接拒绝购买
--    （提示「该商品未设置收款门店」），次卡当场卖不出去。
--
-- 为什么现在是 NULL：次卡商品维护页（punchcard_product_detail.js）保存时
-- 一直显式写 shop_id: null，只存店名文本。本次同步改成存 shop_id。
--
-- 等价性：这三个商品的 shop 文本与 shop_list.name 完全一致，
-- 换成 shop_id 后写进 order.shop 的仍是同一个字符串，GetMchId 的子串判定结果不变
-- （万龙体验中心 / 万龙服务中心 都含「万龙」、都不含「南山」）。
-- 历史订单实证：万龙体验中心 73 单、万龙服务中心 11 单，order.shop 正是这两个名字。

UPDATE product SET shop_id = 10 WHERE id = 716;          -- 租赁10次卡 → 万龙体验中心
UPDATE product SET shop_id = 1  WHERE id IN (717, 718);  -- 机打蜡季卡 / 修刃打蜡（双项）10次卡 → 万龙服务中心
GO

-- 复查：所有在售的次卡/季卡商品都要能落到 shop_list，且解析出的店名与原文本一致
SELECT p.id, p.name, p.shop AS shop_文本, p.shop_id, s.name AS shop_id_解析出的店名,
       CASE WHEN LTRIM(RTRIM(ISNULL(p.shop,''))) = LTRIM(RTRIM(ISNULL(s.name,''))) THEN '一致' ELSE '★不一致' END AS 对比
FROM product p LEFT JOIN shop_list s ON s.id = p.shop_id
WHERE p.valid = 1 AND p.category_code IS NOT NULL AND p.category_code <> ''
ORDER BY p.id;
GO
