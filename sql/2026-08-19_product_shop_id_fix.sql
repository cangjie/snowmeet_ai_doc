-- 2026-08-19  修正养护服务商品的 shop_id，为「按 shop_id 关联 shop_list 匹配」做准备
--
-- ⚠️ 这段 SQL **必须先于后端新版本部署**。
--    CareController.GetProducts 改成按 shop_id 匹配后，shop_id 不对的商品会直接匹配不到，
--    GetProduct 返回 null → CalcCharge 的 commonCharge = 0 → 养护服务费变成 0 元。
--    万龙服务中心近一年有 4427 单养护（占全部 4549 单的 97%），先改代码后果是灾难性的。
--
-- 现状（2026-08-19 生产实测，category_id = 14 养护服务）：
--   137~143  万龙的 6 个养护服务   shop='万龙'         shop_id=10  ← 错，10 是「万龙体验中心」
--   715      非雪季养护            shop='万龙服务中心'  shop_id=NULL ← 缺
--   677~679  南山 3 个             shop='南山'         shop_id=4   ✓
--   711~713  崇礼旗舰店 3 个        shop='崇礼旗舰店'    shop_id=9   ✓
--
-- 为什么 137~143 的 10 是错的：shop_list 里 10 = 万龙体验中心，且它的 care 标志是 0
-- （体验中心只做零售和租赁，不做养护）；真正做养护的是 id=1 万龙服务中心（care=1）。
-- 这批商品之所以一直没出问题，是因为旧的双向子串匹配靠「万龙服务中心」包含「万龙」蒙对了。

UPDATE product SET shop_id = 1
WHERE id IN (137, 138, 139, 140, 142, 143, 715);   -- 万龙服务中心
GO

-- 复查 1：category 14 每个商品的 shop_id 都能在 shop_list 里查到，且与 shop 文本一致
SELECT p.id, p.name, p.shop AS shop_文本, p.shop_id, s.name AS shop_id_对应店名
FROM product p LEFT JOIN shop_list s ON s.id = p.shop_id
WHERE p.category_id = 14 AND p.valid = 1
ORDER BY p.shop_id, p.id;
GO

-- 复查 2：新旧两种匹配口径必须给出完全相同的商品集合（这是本次改造的验收线）
-- 期望：每个门店两列的 id 集合逐一相同
SELECT s.name AS 门店,
       (SELECT COUNT(*) FROM product p WHERE p.category_id=14 AND p.valid=1
          AND p.shop IS NOT NULL AND (CHARINDEX(p.shop, s.name) > 0 OR CHARINDEX(s.name, p.shop) > 0)) AS 旧_文本匹配数,
       (SELECT COUNT(*) FROM product p WHERE p.category_id=14 AND p.valid=1
          AND p.shop_id = s.id) AS 新_shopid匹配数
FROM shop_list s ORDER BY s.id;
GO
