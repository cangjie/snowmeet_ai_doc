-- 2026-09-23 食材管理：新建餐饮门店「多呆一会儿吧」并绑定后厨员工
-- 背景：食材/厨房单接口要求 staff.base_shop_id = 操作门店，且新表 shop_id 外键指向 shop_list。
--       线上 29 名在职员工里 25 人 base_shop_id 为空，餐饮商品 shop_id 也不在 shop_list 中，
--       不执行本脚本，小程序食材管理对所有员工都会提示「无门店权限」。
-- 由用户审阅后手动执行；Claude 未对生产库写入。

-- 1. 新建餐饮门店（只开餐饮：sale/care/rent=0，restuarant=1；经纬度 0 不参与定位；sort=900 排在门店下拉最后）
--    注意：Order/GetShops 不过滤门店类型，这家店会出现在租赁/养护等页面的门店下拉里（排最后）。
IF NOT EXISTS (SELECT 1 FROM shop_list WHERE name = '多呆一会儿吧')
    INSERT INTO shop_list (name, code, sort, lat_from, lat_to, long_from, long_to, sale, care, rent, restuarant)
    VALUES ('多呆一会儿吧', 'DDY', 900, 0, 0, 0, 0, 0, 0, 0, 1);

SELECT id, name, code FROM shop_list WHERE name = '多呆一会儿吧';

-- 2. 绑定后厨员工：把下面 IN (...) 换成实际员工 staff.id 后再执行。
--    ⚠️ base_shop_id 也是租赁/养护页门店选择器的默认值来源，改了之后这些员工在其他页面的默认门店会变成本店。
--    店长级功能（建档、配方、盘点过账、销毁、看板）要求 title_level >= 200。
-- UPDATE staff
--    SET base_shop_id = (SELECT id FROM shop_list WHERE name = '多呆一会儿吧'), update_date = GETDATE()
--  WHERE id IN (/* 后厨员工 staff.id，例如 31 */);

-- 3. 核对
-- SELECT id, name, title_level, base_shop_id FROM staff
--  WHERE base_shop_id = (SELECT id FROM shop_list WHERE name = '多呆一会儿吧');
