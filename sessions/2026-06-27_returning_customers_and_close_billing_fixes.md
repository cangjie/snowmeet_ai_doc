# 2026-06-27 回头客分析 + CloseOrder/计费/展示 四处修复

本场先做租赁回头客数据分析(只读生产库),再由用户从真机截图逐个暴露 4 个 bug 并修复。代码改动落在 `SnowmeetApi`(后端 2 处)+ `snowmeet_wechat_mini`(前端 2 处),**均本地未提交,用户按部署节奏处理**;本次 end-work 仅提交 doc 仓。全程连生产库只读核查(用户本会话授权 `100.28.143.19/snowmeet_new`)。

## 1. 回头客分析(只读)

### 1.1 按订单笔数:三次以上回头客 = 83 人
- 源:`merged_rent_orders_fy_2025-05-01_2026-04-30.xlsx` 主 sheet,剔除测试+临时单后 2252 笔
- 按手机号/顾客openid 两键结果一致:去重顾客 1788,≥2 次 249 人,**≥3 次 83 人**(占 4.6%)
- 分布:1 次 1539 / 2 次 166 / 3 次 49 / 4 次 16 / …最高 19 次 1 人、13 次 1 人、10 次 2 人

### 1.2 按「套天」(一套含雪板的装备租一天=1次):5 次以上 = 164 人
- 用户口径:**这套含雪板(品类前缀 01双板/02单板)**才计;一套一天算一次(`DISTINCT 租赁×日期`,租金明细 valid=1)
- 雪板雪鞋品类:`rent_category` code 前缀 01/02/03/04 共 14 个(双板/单板/双板鞋/单板鞋)
- 财年内非测试、含雪板的 rental:1944 条;去重客户 1265
- **套天 ≥ 5(含5)= 164 人**;>5 = 124 人;分布 5–9:110 / 10–19:30 / 20+:24
- 注:高值多由长租/整季未归还按天累积撑起(member 优先键与手机号键结果一致)
- 租金明细偶有同一天多行(老数据 `rent_item_id=0`),故用 `DISTINCT(rental_id, rental_date)` 而非行数

## 2. CloseOrder 关不了单(`paymentFulfilled` + `paying_amount` bug)

### 2.1 现象 → 根因(systematic-debugging 全程)
- 用户报某「全额退押金」单 paidAmount=0 却没变「了结关闭」
- 实查 WT_ZL_260623_00004(order 71793):头盔已还 settled=1、押金 0.01 已全额退款 → 状态「全额退押金」**正确**,只是 `closed=0`
- 系统性:**96 单**付过款的租赁单滞留未关;其中 65621(押金¥3000、2026-01-02 就全退)滞留近半年、跨多次扫描没关 → 真 bug
- 多重证据钉死根因:
  - [`OrderController.cs:2200`](../SnowmeetApi/Controllers/OrderController.cs#L2200) `DealSuccessPaidOrder` 支付成功即 `order.paying_amount = null`(设计意图:不再欠款)
  - [`RentController.cs:5843`](../SnowmeetApi/Controllers/RentController.cs) CloseOrder 在 commit `b186e49f`(2026-06-21 17:19)新增 `paymentFulfilled = Round(paidAmount − (paying_amount ?? 0),2)==0`,误把 paying_amount 当「应付总额」
  - paying_amount=null → 退化成 `paidAmount==0`,对任何已付款单恒 false → `finished` 永不成立
  - **DB 实证:06-21 17:19 之后关单数 = 0**;已关的 71754/62/53/46 是 06-17~19 被**旧版(无此闸)**关的,新闸门对它们也都 False(铁证)

### 2.2 修复(1 行,`dotnet build` 0 error)
```csharp
// 旧:Math.Round(order.paidAmount - (double)(order.paying_amount ?? 0), 2) == 0
// 新:paying_amount 表示尚欠应收,null/<=0 视为已收齐
bool paymentFulfilled = order.paying_amount == null || Math.Round((double)order.paying_amount, 2) <= 0;
```
- 「未足额收款不关单」保护仍在(paying_amount>0 → 不关);效果=回退到 06-21 前可用行为
- 验证:旧/新闸门对 6 单取值对照,新闸门让 paying_amount=null 的已付款单恢复可关
- 决策:**只改代码,不动历史**(96 单虚账不清)
- ⚠️ 65621 是另一独立 bug:押金全退导致 `totalRentUnRefund` 为负、`==0` 判定不过 → 仍关不上(本次不在范围)

## 3. 未发放也计租金(ContinueRental 缺「生效」判断)

### 3.1 现象 → 根因
- 用户报 3 单(71789/90/91)支付金额 0 却产生租金;实查:rentItem `pick_time=None`、`RentItemLog=0`、status=**未发放**,租金明细却按天累积到今天
- 计费任务「系统续租」[`RentController.cs:5667`](../SnowmeetApi/Controllers/RentController.cs) 门槛 `i.status != "已归还"` → **未发放/已更换也被当在租计费**
- `RentItem.status` 派生自 RentItemLog(无事件=「未发放」);枚举 `{未发放,已发放,暂存,已归还,已更换}`
- 影响面(本季非测试):**187 条从没发放却计租金、合计 ¥168 万**(186 条 settled=0 还在每天累积)

### 3.2 修复(用户拍板:已发放 OR 暂存才计;只改代码不动历史)
```csharp
// 旧:i.status != "已归还"
// 新:至少一件当前在外
rental.rentItems.Where(i => i.status == "已发放" || i.status == "暂存").Count() == 0
```
- 外层 `ContinueRentOrder` 已 `.ThenInclude(i => i.logs)`,status 能正确派生,安全
- 验证:本季 339 条 settled=0 在计费的 rental → 修复后 57 继续(有在外件)/ 282 停止(无在外件);3 样例单全部正确归入「停止」
- 不动 `SetRentalDetail`(立即租赁正常发放的首日计费):3 样例单无首日行,租金全来自每日任务

## 4. 小数位浮点尾数(rent_order_detail 展示)

- 现象:showcase 区 租金/小计 显示 `¥0.06000000000000005`(6天×0.01 累加)
- 根因:wxml 直接 `¥{{裸浮点值}}`(6 处:摘要租金、费用格租金/减免/赔偿/超时、小计)
- 修复:
  - [`rent_order_detail.js`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) rental 循环补 4 个 `*Str` 字段,走 `util.showAmount()`(`Math.round(×100)/100` + 2 位 + 自带 ¥)
  - [`rent_order_detail.wxml`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml) 6 处改绑 `{{xxxStr}}`(去字面 ¥)
- 全 wxml 无残留 `¥{{` 裸值绑定

## 5. 招待订单不显示租金(new_rent_list)

- 现象:招待单(order 71788,「全额退押金」)「总计租金」显示「--」
- 根因双因素:① 列表只在 `rentStatus === '了结关闭'` 才累加;② 招待 rental 后端 `totalRentalAmount` 返 0(豁免)
- `rental.details` 在列表响应里有(`GetCommonOrders` line 186 已 include、`RendOrder` 不剥)
- 修复 [`new_rent_list.js`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js) `renderOrders`:
  - 招待 rental:不受「了结关闭」限制,从 `rental.details` 累加**毛租金**显示(让店员看到招待掉的额)
  - 非招待:维持原逻辑;页级「租金收入合计」不计招待豁免额
- 效果:71788 显示「¥0.06」

## 关键改动文件

| 文件 | 改动 | 仓库/状态 |
|---|---|---|
| [`RentController.cs`](../SnowmeetApi/Controllers/RentController.cs) | CloseOrder `paymentFulfilled` 改判(§2)+ ContinueRental 计费门槛改「已发放/暂存」(§3) | SnowmeetApi,**未提交,需 publish** |
| [`rent_order_detail.{js,wxml}`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/) | 4 个 `*Str` + 6 处改绑(§4) | 小程序,**未提交,需重编** |
| [`new_rent_list.js`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js) | 招待 rental 从明细显示毛租金(§5) | 小程序,**未提交,需重编** |

## 学到的小知识

1. **CloseOrder 自 2026-06-21(`b186e49f`)起停止关单**:新增的 `paymentFulfilled = paidAmount − (paying_amount??0) == 0`,因 `DealSuccessPaidOrder` 支付成功把 `paying_amount` 置 null,退化成 `paidAmount==0` 对任何已付款单恒 false。正确判据是「无尚欠应收」(paying_amount null/<=0)。DB 实证 06-21 后关单数=0。
2. **租金「生效」= 装备真在外(已发放/暂存)**:`ContinueRental` 旧门槛 `status != "已归还"` 把「未发放/已更换」也计费 → 本季 187 条从没发放却计 ¥168 万虚账。改成 `status == 已发放 || 暂存`。
3. **`RentItem.status` 派生自 RentItemLog**:无任何领还事件 → 「未发放」;`pick_time` 列在新流程可能为空,判生效要看 log/status 不要看 pick_time。
4. **金额展示一律走 `util.showAmount`**:它 `Math.round(×100)/100` + 补 2 位 + 自带 ¥;wxml 别 `¥{{裸浮点值}}`,否则出 `0.06000000000000005`。
5. **招待 rental 后端 `totalRentalAmount`/`totalSummary` 租金部分恒 0**(`experience || entertain` 豁免);要显示招待掉的毛租金得从 `rental.details` 的「租金」明细累加(列表 `GetCommonOrders` 已 include details)。
6. **「套天」回头客口径**:含雪板(品类前缀 01/02)的 rental,按 `DISTINCT(rental_id, rental_date)` 计(租金明细偶有同日多行老数据);≥5 次 164 人。
7. **本机 Intel Mac 连库**:`ODBCSYSINI=/usr/local/Cellar/unixodbc/2.3.4/etc` + Driver 13 + 连接串 `Encrypt=yes`(Driver 13 不认 `True`);大表(rental_detail 11 万行)`NOT EXISTS` 全历史 join 会超时,先按 `create_date>'2025-10-01'` 缩小再 python 端分批。
