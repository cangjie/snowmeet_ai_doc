# 2026-06-21 储值付租金退押金不退 + ¥0 储值支付 + 找回中断订单空单（三修）

接 6-20续3，继续测租赁订单详情 / 接待开单流程。用户报两组 bug，都先连生产库 `100.28.143.19/snowmeet_new` **只读**核查（用户明确授权"你可以自己连上数据库看呀"）定根因，再改。frontend 为主 + 各一处后端。改动在 snowmeet_wechat_mini + SnowmeetApi 工作区**未提交**，需小程序重编 / 后端 `dotnet publish`。本环境无微信开发者工具，靠 `node --check` / `dotnet build` + DB 实查 + 截图数字验证。

## 1. 储值付租金 + 申请退款：押金不退（order 71769，他人微信代付）

用户：勾「储值付租金」+「申请退款」→ `order_payment` 插**储值支付 0 元**（用户以为该 0.01）+ `payment_refund` 无微信退款。强调"订单属于其他人微信代付"。

### 1.1 代码链路梳理
- 前端 [`_refundWithDeposit`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js)：`payAmount=order.totalRentSummaryAmount`(modal 显示) → `payWithDepositPromise`(→后端 `Order/PayWithDeposit`) → 取 `rAmount=paidOrder.totalRentUnRefund`，`rAmount<=0` 就**提前 return（弹"储值支付成功"），不调 refundPromise** → 否则找一笔 `status=支付成功 && remainAmount>=rAmount` 的 payment，调 `refundPromise`(→后端 `Refund`)。
- 后端 [`PayWithDeposit`](../SnowmeetApi/Controllers/OrderController.cs#L2954)：租赁单 `payingAmount=(double)order.totalRentSummaryAmount`(第 2998 行)，`if(order.depositPaidAmount==0)` 插一条 `amount=payingAmount` 的储值支付。
- `Rental.totalSummary = totalRentalAmount + overtime + repair - discount`，`totalRentalAmount` 只累加 **valid=1 的「租金」rental_detail**。

### 1.2 DB 实查 71769（决定性）
- rental 54394「头盔」entertain=招待(rent 0) + 54393「Burton」rent 0.01。
- **`rental_detail` 113352(Burton 租金 0.01) `valid=0`** → `totalRentSummaryAmount=0` → 储值支付插 0。
- `core_data_mod_log`：113352 `valid 1→0, scene=租赁订单详细页修改租金明细, 20:39:17, staff 28`（在 20:38:53 归还结算之后）→ **租金是被店员有意免除的**。用户确认"免除是我有意的"。
- 押金 0.01：guaranty 15913 `relieve=1 valid=1`，`guaranty_payment(15913↔42625)` 在，42625=微信支付 0.01 `is_proxy_pay=True` 支付成功 → **押金正常已付，代付链路完好**。
- 4 条 ¥0 储值支付(42627–42630, 06-21 08:33–08:35)= 用户点 4 次的产物；`payment_refund` 0 条。

### 1.3 根因
- **储值支付=0**：租金被免除(valid=0)→ totalRentSummaryAmount=0。免除有意 → 0 是对的，但**不该硬插 ¥0 记录**(攒垃圾)。
- **押金不退**：`PayWithDeposit` 末尾 `order=GetOrder(order.id)` 返回，而 [`GetOrder`](../SnowmeetApi/Controllers/OrderController.cs#L38) 只加载 rental 级 `r.guaranties`，**不加载订单级 `order.guarantys`**（rentProperties 注释明说"由 GetCommonOrders 加载"）→ `rentProperties.totalPaidGuarantyAmount=0` → `paidOrder.totalRentUnRefund=0` → 前端 `rAmount<=0` 提前 return → **从没调 refundPromise**（4 次都没插 payment_refund，印证；若调过，后端 Refund 会先插行再调微信，必留行）。
- **代付不是原因**：后端 [`Refund`](../SnowmeetApi/Controllers/OrderController.cs#L2714) 按 payment_id + out_trade_no 退，对 is_proxy_pay 无过滤。

### 1.4 修复
- [`rent_order_detail.js`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) `_refundWithDeposit`：`rAmount` 改用页面捕获的 `refundAmount`（=`order.totalRentUnRefund`，6-20续3 已改成基于可靠的 `order.totalGuarantyAmount`），不读 `paidOrder.totalRentUnRefund`。→ rAmount=0.01 → 命中代付微信单 42625 → 退款 0.01。
- [`OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs#L3023) `PayWithDeposit`：`if(order.depositPaidAmount==0 && payingAmount>0)` 才插储值支付。**需 publish**。

## 2. 找回中断的订单 = 空单（order 71770）

用户：开单加租赁商品后，「找回中断的订单」找回的都是空单，"以为没保存到数据库"。

### 2.1 DB 实查 71770
- `valid=0 recepting=1 租赁` 订单，库里 **rental_cnt=2 / rental_valid_cnt=0 / item_cnt=8** → rental/item **都存了**，只是 rental `valid=0`。
- 对比已下单 71769：rental valid=1。

### 2.2 根因
- 接待中 rental 本就是 `valid=0` 草稿态：`recept_package.js` 建套餐 rental 即 `valid:0`、`Rental` 模型默认 `valid=0`；[`PlaceRentOrder`](../SnowmeetApi/Controllers/OrderController.cs#L2813) 去结算时才 `rental.valid=1`(实证 71769 placed=valid1 / 71770 interrupted=valid0)。**设计如此**。
- [`recept_new.js onLoad`](../snowmeet_wechat_mini/pages/admin/reception/recept_new.js)（文件 5-30，早于 6-20续2 找回功能）找回时 ① 用 `getOrderByStaffPromise`(→`GetOrderByStaff`，按 `r.valid==1` 过滤)拉单 → 草稿 rental 全滤掉；② **只取了 `customer` 信息（姓名/手机/性别/memberId），完全没还原 `order.rentals` 和 `order.id`** → 购物车空 + 新 id。
- 6-20续2 加找回功能：接了"列表(GetReceptingOrders)+跳转 recept_new?orderId=X"+后端 `GetReceptingOrder`，但**没改 recept_new 去消费 orderId 还原整单**（功能没接完）。`GetReceptingOrder`(单)本身不过滤 valid、带 rentItems+pricePresets，是对的，只是前端没用它。

### 2.3 修复
[`recept_new.js onLoad`](../snowmeet_wechat_mini/pages/admin/reception/recept_new.js)：带 orderId(找回)时 → 用 `getRentReceptingOrderPromise`(→`GetReceptingOrder`，不过滤 valid) 拉单 → **整单还原** `this.data.order = 中断单`(含 id + rentals，rentals 补 timeStamp 供 wx:key) + `shop` 取 `recoveredOrder.shop`。购物车(`rent-recept-form rentals="{{order.rentals}}"`)直接显示原商品；后续 `saveRentReceptOrder` 因 id>0 走后端 SaveRentRecept 的 id>0 分支、更新同一张中断单；去结算 PlaceRentOrder 置 valid=1。非找回(无 orderId)走原 else 分支，无回归。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`rent_order_detail.js`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) | `_refundWithDeposit` 的 rAmount 改用页面 `refundAmount`（不读 PayWithDeposit 返回的 totalRentUnRefund） |
| [`OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs#L3023) | `PayWithDeposit`：`payingAmount>0` 才插储值支付（**需 publish**） |
| [`recept_new.js`](../snowmeet_wechat_mini/pages/admin/reception/recept_new.js) | `onLoad` 找回：用 `getRentReceptingOrderPromise` + 整单还原 rentals/id |

## 学到的小知识

1. **接待中 rental 是 `valid=0` 草稿，`PlaceRentOrder` 才置 1**：任何"重载/找回中断单"必须用 `GetReceptingOrder`(不过滤 valid)，用 `GetOrderByStaff`/`GetOrder`(valid=1 过滤)会得空 rentals。
2. **`PayWithDeposit` 返回的 order 经 `GetOrder`、不带订单级 `order.guarantys`** → `rentProperties.totalPaidGuarantyAmount`/`totalRentUnRefund` 恒 0；前端储值付租金退款别信它，用页面 `order.totalGuarantyAmount` 口径（与 6-20续3 应退押金同源）。
3. **找回/恢复类功能要"接完整链"**：跳转 + 后端取数接口 + 前端消费还原，缺一环就空单（6-20续2 漏了 recept_new 消费 orderId）。
4. **DB 实查戳穿"没保存"误判**：71770 库里有 2 rental/8 item 只是 valid=0、71769 储值支付确为 0；先看库里关键字段(valid/amount)再下结论，比信用户表象快。
5. **后端 `Refund` 对代付无过滤**：用户强调"代付"时先确认它是否真相关——本例代付是干扰项，真因在前端 rAmount 取值。
6. 用户授权连库后，按 `SnowmeetApi/config.sqlServer`(Driver 13 + `ODBCSYSINI=/usr/local/Cellar/unixodbc/2.3.4/etc`，本机 Intel Mac) 只读跑 pyodbc 即可；查完删临时脚本。
