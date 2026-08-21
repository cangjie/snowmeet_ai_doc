-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║  暂缓执行（2026-08-19 用户决定）                                      ║
-- ║  只在程序里停用这一列，DB 列先保留，本脚本**不要跑**。                  ║
-- ╚══════════════════════════════════════════════════════════════════════╝
--
-- 留着列是安全的：EF 生成显式列名的 SQL，模型里已无 shop 属性，
-- 永远不会 SELECT/UPDATE 它；INSERT 不带该列，DB 自动写 NULL
-- （varchar(50) NULL，无默认约束、无 check 约束、无索引）。
-- 后端也没有任何针对 product 的裸 SQL（FromSqlRaw/ExecuteSqlRaw 零处）。
--
-- ⚠️ 副作用：这一列从此**逐渐失真**——存量行保留旧值不再更新，新建商品为 NULL。
--    手工查库 / 导 Excel / 接 BI 时不能再拿它当准数，看门店一律走 shop_id → shop_list。
--
-- 将来真要删时的前置条件：
--   1. 后端新版本（已移除 shop 属性的那版）必须先部署完成——旧实例还在读它，先删列会报错
--   2. 确认没有新增的裸 SQL / 报表 / 外部系统在读 product.shop
--   3. 先跑下面的快照 SELECT INTO，再 DROP
--
-- 2026-08-19  删除 product.shop（门店名文本列）
--
-- ⚠️ 执行顺序：**必须等后端新版本部署完成之后**再跑。
--    新版本已把这一列从 EF 模型里移除、所有读写点改为 shop_id 关联 shop_list；
--    但旧版本仍在读它，先删列会让旧实例查询直接报错。
--
-- 为什么删：
--   1. 写法不统一 —— 同一个门店存过「万龙」和「万龙服务中心」两种值，养护定价靠
--      `p.shop.IndexOf(shop) >= 0 || shop.IndexOf(p.shop) >= 0` 双向子串匹配才蒙对，
--      门店改个写法就会静默失配、服务费变成 0。
--   2. 语义被复用 —— 雪票商品拿它存**雪场**名，而崇礼旗舰店卖的是万龙雪场的票
--      （shop='崇礼旗舰店'、resort='万龙'），导致 `p.shop == resort` 查万龙雪票查不出一条。
--   3. shop_id + shop_list 是主数据，同一个门店只有一个写法，且能级联改名。
--
-- 本次改造已完成的替换（后端）：
--   养护定价    CareController.GetProducts          shop 文本双向子串 → shop_id
--   次卡收款    RentController 自助购买/投影         shop 文本 → shop_id → shop_list.name
--   雪票筛商品  SkiPassController / ProductController  门店比雪场 → category_id（南山雪票/万龙雪票）
--   雪票下单    SkiPassController / NanshanSkipass   order.shop ← shop_id → shop_list.name
--   雪票同步    WanlongZiwoyouHelper                 新建商品写 shop_id + category_id
--   优惠券/养护商品维护                              只写 shop_id，不再写 shop
--
-- 列定义：varchar(50) NULL，无默认约束、无索引 —— 直接 DROP 即可。

-- 建议先留个快照，万一要回滚查得到原值
SELECT id, name, shop, shop_id, category_id, type, valid
INTO product_shop_backup_20260819
FROM product;
GO

ALTER TABLE product DROP COLUMN shop;
GO

-- 复查：列已不存在
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'product' AND COLUMN_NAME = 'shop';
GO
