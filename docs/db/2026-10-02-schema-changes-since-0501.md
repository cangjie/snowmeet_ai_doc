# 数据库结构变更清单（2026-05-01 起）

2026-10-02 整理。范围是 `ai` 分支开发期间（5 月 1 日到现在）业务库 `snowmeet_new` 的结构变化。

**资料来源：**
- `sql/` 下的 34 个迁移脚本，外加未提交的 `2026-10-01_staff_bind_code.sql`；
- SnowmeetApi 数据模型的改动（`9b4d35f1` → `3c9dc278`）；
- 开发记录（`CLAUDE.md`、`sessions/`）。

**没有直接核实生产库。** 只读查询系统目录的请求被权限规则拦下了。所以下面的「状态」都是开发记录里的说法，最后一节列出了核实方法。

**状态说明：**
- ✅：记录里写明已执行或已核实存在；
- ❓：记录里没有确认；
- ⏸：脚本写好了，但按决定暂缓、不执行；
- ⏳：新写的，还没执行。

## 一、总览

| 类别 | 数量 |
|---|---|
| 新建的表 | 25 张：会员标签 2、食材批次与提醒日志 2、优惠券分享 2、管理员 AI 日志 1、食材管理 17、员工绑定码 1（未执行） |
| 新建的视图 | 2 个（食材库存、损耗） |
| 已有表新增的列 | 约 40 列，涉及 10 张 5 月前就有的表 |
| 改了类型或可空性的列 | 1 列：`ticket_template.available_days` 由不可空改为可空。食材新表内部的调整不计 |
| 删除 | 没有删除已有表或已有列。`product.shop` 的删除脚本已暂缓 |
| 只改数据的脚本 | 8 个 |
| **没有脚本存档、只在库里手工执行过的** | 约 22 列，见第六节 |

## 二、新建的表

| 表 | 用途 | 脚本 | 状态 |
|---|---|---|---|
| `member_tag` | 会员自定义标签 | `2026-06-30_member_tag.sql` | ✅ 功能上线时已在生产直接建表 |
| `member_tag_preset` | 标签库字典，脚本里预置 13 个标签 | `2026-06-30_member_tag_preset.sql` | ✅ |
| `fnb_material_batch` | 食材批次台账（过期提醒） | `2026-07-15_fnb_material_batch.sql` | ✅ |
| `fnb_material_alert_log` | 过期提醒发送记录 | 同上 | ✅ |
| `ticket_share_batch` | 店员分享发券批次 | `2026-08-20_ticket_share_batch.sql` | ❓ |
| `ticket_share_claim` | 分享券领取记录 | 同上 | ❓ |
| `admin_ai_request_log` | 管理员 AI 帮助和查询的调用日志 | `2026-09-07_admin_ai_request_log.sql` | ✅ 9 月 7 日已部署 |
| 食材 17 张：`fnb_unit`、`fnb_material_category`、`fnb_shelf_life_rule`、`fnb_material_item`、`fnb_material_batch_stock`、`fnb_dish_spec`、`fnb_recipe`、`fnb_recipe_line`、`fnb_channel_shop`、`fnb_channel_dish_map`、`fnb_order`、`fnb_order_line`、`fnb_order_import`、`fnb_stock_document`、`fnb_stock_document_line`、`fnb_stock_movement`、`fnb_stocktake_line` | 食材管理（库存、配方、厨房单、盘点），`fnb_unit` 预置 5 个计量单位 | `2026-09-22_fnb_inventory_other_tables.sql`（VARCHAR 版；`2026-09-21_*_schema_review.sql` 是作废的 NVARCHAR 旧稿，不要执行） | ✅ 9 月 22 日只读核对存在 |
| 视图 `vw_fnb_material_stock`、`vw_fnb_material_loss` | 食材库存、损耗报表 | 同上 | ✅ |
| `staff_bind_code` | 员工账号一次性绑定码 + 自助登记待开通记录 | `2026-10-01_staff_bind_code.sql`（**文档仓库未提交**） | ⏳ **要先于新版员工账号接口部署执行** |

另外两张表 `punch_card`（次卡/季卡）、`punch_card_used`（次卡核销）**5 月前就已在生产库里**，原先没有数据模型。6 月 29～30 日起后端才开始读写它们。它们新增的列见第三节。

## 三、已有表新增的列

| 表 | 列 | 类型 | 日期 | 脚本 | 状态 |
|---|---|---|---|---|---|
| `order` | `wechat_unverified` | bit NOT NULL DEFAULT 0 | 05-14 | 无，手工执行 | ✅ 05-27 记录「用户已 ALTER」 |
| `order` | `pay_with_deposit` | bit NOT NULL DEFAULT 0 | 07-12 | 无 | ❓ |
| `order` | `order_source`、`source_order_no` | varchar(32)、varchar(128)，可空 | 09-22 | `2026-09-22_order_source_pair.sql` | ✅ 随食材上线 |
| `order_payment` | `is_proxy_pay` | bit NOT NULL DEFAULT 0 | 05-14 | 无，手工执行 | ✅ 05-27 |
| `order_payment` | `customer_open_date` | datetime 可空 | 06-08 | 无（语句写在 06-08 会话记录里） | ❓ 后端已长期依赖 |
| `mini_session` | `wechat_openid`、`wechat_unionid` | nvarchar(64) 可空 | 05-29 | `2026-05-29_mini_session_add_openid_unionid.sql` | ✅ |
| `mini_session` | `alipay_payerid`、`cell` | nvarchar(64)、nvarchar(15) 可空 | 06-03 | `2026-06-03_mini_session_add_alipay_cell.sql` | ✅ 脚本写明已核实 |
| `mini_session` | `alipay_openid` | 字符串，可空 | 6 月 | 无 | ✅ 06-20 记录里实查到有值 |
| `shop_list` | `beacon_mac`、`beacon_uuid` | nvarchar(32)… 可空 | 05-31 | `2026-05-31_shop_add_beacon.sql` | ✅ |
| `rent_product` | `status` | nvarchar(20) 可空 | 06-28 | `2026-06-28_rent_product_add_status.sql` | ✅ |
| `care` | `card_id`、`card_name` | int、字符串，可空 | 07-10/11 | 无，用户手工建列 | ✅ 记录写明「用户建列」 |
| `care` | `is_cancel`、`cancel_reason` | bit NOT NULL DEFAULT 0、nvarchar(500) 可空 | 07-14 | 无 | ❓ 记录多次标「交付状态不明」 |
| `product` | `punch_total` | int 可空 | 07-22 | `2026-07-22_punch_card_sale.sql` | ✅ |
| `product` | `usage_rules` | nvarchar(max) 可空 | 07-25 | `2026-07-25_product_add_usage_rules.sql` | ✅ 7 月 26 日确认 |
| `product` | `care_project_count` | int 可空 | 07-26 | `2026-07-26_care_project_count.sql` | ✅ 7 月 26 日确认 |
| `retail` | `product_id`、`punch_card_id` | int 可空，外键 `FK_retail_product`、`FK_retail_punch_card` | 07-22 | `2026-07-22_punch_card_sale.sql` | ✅ |
| `punch_card` | `source_retail_id` | int 可空，外键 `FK_punch_card_source_retail` | 07-22 | 同上 | ✅ |
| `punch_card` | `is_refund` | bit NOT NULL DEFAULT 0 | 07-25 | `2026-07-25_punch_card_add_is_refund.sql` | ❓ |
| `punch_card` | `care_project_count` | int 可空 | 07-26 | `2026-07-26_care_project_count.sql` | ✅ |
| `punch_card` | `equip_type`、`equip_brand`、`equip_scale`、`equip_serial`、`update_date`、`create_date` | 字符串/日期 | 7 月（季卡绑定装备） | 无 | ❓ 5 月勘察时表里只有 id/biz_type/card_name/member_id/mi7_code/total/punches，这几列何时加的我没核实到 |
| `ticket_template` | `sharable` | int NOT NULL DEFAULT 0 | 08-20 | `2026-08-20_ticket_template_sharable.sql` | ❓ |
| `ticket_template` | `cover_upload_id`、`poster_width`、`poster_height`、`qr_x`、`qr_y`、`qr_width`、`qr_height` | int（海报、二维码位置） | 08-28 | **无存档**（记录写「用户已取得幂等 DDL」） | ❓ |
| `ticket_share_batch` | `channel` | varchar(50) 可空，另建唯一索引 `UX_tsb_qrcode` | 08-21 | `2026-08-21_ticket_qrcode_share.sql` | ❓ |
| `ticket_share_claim` | `claim_date` | date NOT NULL；唯一索引从 `UX_tsc_batch_member` 换成 `UX_tsc_batch_member_date` | 08-21 | 同上 | ❓ |
| `fnb_material_batch` | `staff_id` | int 可空 | 07-16 | `2026-07-16_fnb_material_batch_add_staff_id.sql` | ✅ |
| `fnb_material_item` | `warn_days` 等食材级设置 | — | 09-24 | `2026-09-24_fnb_item_expiry_settings.sql` | ❓ |
| `fnb_material_category` | `is_prepared` | bit | 09-25 | `2026-09-25_fnb_category_prepared.sql` | ❓ |
| `fnb_material_item` | `low_stock_ratio`、`low_stock_qty` | 数值，带检查约束 | 09-26 | `2026-09-26_fnb_item_low_stock.sql` | ❓ |

下面这些**不是数据库改动**：库里早就有这些列，只是 5 月后才在模型里映射。
- `order_payment.cell`：6 月 20 日记录写明「列早已存在」。
- `rent_package.package_type`。
- `ticket_template` 的 `biz_type`、`available_days`、`discount_*`：8 月 18 日脚本注明「DB 里一直有」。
- `ticket_template` 的 `valid`、`experience`、`need_points`、`currency_value`：也是 5 月后新映射的，但是不是原有列，我没查到记录。

## 四、改了类型、约束，或删除

| 对象 | 改动 | 脚本 | 状态 |
|---|---|---|---|
| `ticket_template.available_days` | int NOT NULL → 可空，原来的 0 改成 NULL | `2026-08-18_ticket_template_fields.sql`（共 4 段） | ❓ |
| `fnb_shelf_life_rule.category_id` | 改为可空，新增 `item_id`，保质期规则从分类下沉到食材 | `2026-09-24_*` | ❓ |
| `fnb_material_category.default_unit_code` | 删除（新表内部调整） | `2026-09-24_*` | ❓ |
| `order` 上的 `CK_order_source_pair` 约束 | 删除（如果建过的话） | `2026-09-22_drop_order_source_pair.sql` | 现行脚本本来就不建这个约束 |
| `product.shop` | 删除这一列 | `2026-08-19_drop_product_shop.sql` | ⏸ **用户决定暂缓**：代码已不用这一列，库里还保留 |

## 五、只改数据的脚本

| 脚本 | 内容 | 状态 |
|---|---|---|
| `2026-06-30_member_tag_preset.sql` | 预置 13 个会员标签 | ✅ |
| `2026-08-14_ticket_shared_flag_cleanup.sql` | 清洗「已被接受但 shared 仍为 1」的券 | ✅ 用户已执行，15 行 |
| `2026-08-18_ticket_template_fields.sql` 第 2～4 段 | 模板业务类型、有效天数、立减金额回填，`product_ticket_template` 补数据 | ❓ |
| `2026-08-19_fill_product_category_code.sql` | 按 `category.code` 回填 `product.category_code` | ❓ |
| `2026-08-19_product_shop_id_fix.sql` | 修正养护商品的 `shop_id` | ❓（要求先于后端部署） |
| `2026-08-19_punchcard_product_shop_id.sql` | 次卡/季卡商品改由 `shop_id` 决定收款门店 | ❓（要求先于后端部署） |
| `2026-09-23_fnb_restaurant_shop.sql` | 新建门店「多呆一会儿吧」，后厨员工 `base_shop_id` 指向它（需填员工 id） | ❓ |
| `fnb_unit` 预置 5 个计量单位 | 包含在食材建表脚本里 | ✅ |

## 六、需要特别注意的

1. **没有脚本存档的改动**：
   - `order.wechat_unverified`、`order.pay_with_deposit`；
   - `order_payment.is_proxy_pay`、`customer_open_date`；
   - `care.card_id`、`card_name`、`is_cancel`、`cancel_reason`；
   - `mini_session.alipay_openid`；
   - `punch_card` 的 6 个装备/日期列；
   - `ticket_template` 的 7 个海报字段。

   新环境（测试库、演示库）照着 `sql/` 目录重建会缺这些列，后端一查相关表就报 500。建议补一个汇总脚本，用「列不存在才加」的幂等写法。
2. **记录里标「未确认」的**：`care.is_cancel`/`cancel_reason`、`order.pay_with_deposit`、`punch_card.is_refund`、8 月优惠券的 3 个脚本和海报字段、9 月 23～26 日的 4 个食材脚本。
   - 推论：如果线上后端确实已经是 9 月 27 日之后的版本、而且一直正常运行，那么 9 月 26 日之前模型里的列必然都已存在，因为缺任何一列，相关查询都会报错。但「线上后端版本」本身也还没核实。
3. **`staff_bind_code` 还没执行**：脚本在文档仓库里还没提交。部署带员工账号管理的 SnowmeetApi（10-01 的 `446f955e` 之后）之前必须先执行，否则员工账号相关接口会报错。
4. **`product.shop` 不要删**：除了按决定暂缓，旧版演示服务端还依赖这一列（见第七节）。

## 七、对旧版演示服务端的影响

演示服务器打算部署 SnowmeetApi 的 `migrate_to_new_season`（`9b4d35f1`，5 月前的代码）。如果它连的是当前生产库或其副本，从结构上看**能运行**，原因如下：
- 5 月后的改动对旧代码来说都是「加」：
  - 新表旧代码不认识，不受影响；
  - 新列要么可空，要么带默认值，旧代码插入时不写这些列，由数据库自动填默认值；
  - 旧数据模型里没有映射任何被改类型的列（`available_days` 旧模型没映射）。
- 唯一被代码弃用的列 `product.shop` 还在库里，旧代码照常能读写。

数据层面有几处表现差异（不会报错）：
- 8 月 19 日之后新建的商品没有填 `product.shop`。旧代码按门店文字筛选商品时，看不到这些商品。
- 新增的门店「多呆一会儿吧」会出现在旧版的门店列表里。
- 新版写入的次卡、券分享、食材等数据，旧版看不到也用不到。

## 八、怎么核实

在生产库只读执行下面的查询，就能把上面所有 ❓ 落实：

```sql
-- 5 月 1 日后新建的对象
SELECT type_desc, name, OBJECT_NAME(parent_object_id) AS parent, create_date
FROM sys.objects WHERE create_date >= '2026-05-01' AND is_ms_shipped = 0 ORDER BY create_date;

-- 5 月前就有、5 月后改过结构的表
SELECT name, create_date, modify_date FROM sys.tables
WHERE create_date < '2026-05-01' AND modify_date >= '2026-05-01' ORDER BY modify_date;

-- 逐列核对（举例；把要查的表和列换进去）
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE (TABLE_NAME = 'care' AND COLUMN_NAME IN ('card_id','card_name','is_cancel','cancel_reason'))
   OR (TABLE_NAME = 'order' AND COLUMN_NAME IN ('pay_with_deposit','wechat_unverified','order_source','source_order_no'))
   OR (TABLE_NAME = 'order_payment' AND COLUMN_NAME IN ('is_proxy_pay','customer_open_date'))
   OR (TABLE_NAME = 'punch_card' AND COLUMN_NAME IN ('is_refund','source_retail_id','care_project_count','equip_type'))
   OR (TABLE_NAME = 'ticket_template' AND COLUMN_NAME IN ('sharable','cover_upload_id','poster_width','qr_x'))
   OR (TABLE_NAME = 'fnb_material_item' AND COLUMN_NAME IN ('warn_days','low_stock_ratio','low_stock_qty'))
   OR (TABLE_NAME = 'fnb_material_category' AND COLUMN_NAME = 'is_prepared')
   OR (TABLE_NAME = 'staff_bind_code');
```

更彻底的做法是逐列比对：用 `tools/windows_test/efschema` 按当前数据模型生成建表脚本，再和生产库的 `INFORMATION_SCHEMA.COLUMNS` 逐列比对（同样只读）。
