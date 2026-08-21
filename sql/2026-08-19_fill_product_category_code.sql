-- 2026-08-19  用 category.code 回填 product.category_code
--
-- 为什么：category.id 是自增值、会变（分类重建/迁移就换号），code 是人工维护的稳定值。
-- 商品挂分类应当以 code 为准，id 只作运行期的连接键。
--
-- 现状（执行前实测）：
--   cat 25 万龙雪票  code=0302  挂 394 个商品  category_code 全空
--   cat 24 南山雪票  code=0301  挂  94 个商品  category_code 全空
--   cat 14 普通养护  code=0203  挂  16 个商品  category_code 全空
--   cat 11 咖啡      code=(空)  挂   5 个商品  ← 分类本身没 code，填不了
--   cat 12 鲜榨果汁  code=(空)  挂   6 个商品  ← 同上
--   另有 125 个商品 category_id 为空（其中 716/717/718 反过来只有 category_code）
--
-- code 全表无重复，映射唯一。

----------------------------------------------------------------------
-- 段 1：回填（只填分类确实有 code 的）
----------------------------------------------------------------------
UPDATE p SET p.category_code = c.code
FROM product p
JOIN category c ON c.id = p.category_id
WHERE c.code IS NOT NULL AND c.code <> ''
  AND (p.category_code IS NULL OR p.category_code <> c.code);
GO

-- 复查 1：有分类且分类有 code 的商品，两边必须一致，应返回 0 行
SELECT p.id, p.name, p.category_id, c.code AS cat_code, p.category_code
FROM product p JOIN category c ON c.id = p.category_id
WHERE c.code IS NOT NULL AND c.code <> ''
  AND ISNULL(p.category_code, '') <> c.code;
GO

-- 复查 2：按分类看回填结果
SELECT c.id, c.biz_type, c.code, c.name, COUNT(p.id) AS 商品数,
       SUM(CASE WHEN p.category_code = c.code THEN 1 ELSE 0 END) AS 已回填
FROM category c LEFT JOIN product p ON p.category_id = c.id
GROUP BY c.id, c.biz_type, c.code, c.name
ORDER BY c.biz_type, c.id;
GO


----------------------------------------------------------------------
-- 段 2：餐饮分类还没有 code —— 需要你先定，定完再跑段 1 才能覆盖到
----------------------------------------------------------------------
-- 现有编码规律：前两位 = 业务线，后两位 = 序号
--   01xx 租赁   0101 次卡
--   02xx 养护   0201 次卡 / 0202 季卡 / 0203 普通养护
--   03xx 雪票   0301 南山雪票 / 0302 万龙雪票
-- 按此规律，餐饮应当是 04xx。下面是建议值，**确认后再取消注释执行**：
--
-- UPDATE category SET code = '0401' WHERE id = 11;   -- 咖啡（挂 5 个商品）
-- UPDATE category SET code = '0402' WHERE id = 12;   -- 鲜榨果汁（挂 6 个商品）
-- UPDATE category SET code = '0403' WHERE id = 13;   -- 鸡尾酒（挂 0 个商品）
-- GO
-- 执行后重跑段 1，餐饮那 11 个商品才会被回填。
--
-- 注：id 1~10 那批餐饮分类 valid=0 且不挂任何商品，是历史重复项，不用编码。
