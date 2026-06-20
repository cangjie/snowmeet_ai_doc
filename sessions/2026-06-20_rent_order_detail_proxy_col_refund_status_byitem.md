# 2026-06-20 rent_order_detail：支付明细代付列 + 退租/应退押金/退押金状态三 bug + 按商品/按物品视图重构

接续当天前两场（8 态状态机 / alipay openid 等）。本场全部围绕租赁订单详情页 `pages/admin/rent/rent_order_detail`，按用户逐条反馈推进：先做支付明细的「他人代付」标红 + 脱敏手机号列，再修 order 71766 暴露的退租/应退押金/退押金状态三个 bug，最后按用户要求重构「按租赁商品 / 按租赁物」两个视图。frontend 为主，仅一处后端（`Order.cs` 退押金状态口径）。本环境无微信开发者工具，验证靠 `node --check` + wxml 标签/模板平衡 + 截图真实数据反推 + DB 只读（实际改动未连库，截图数字已足够定位）。

代码仓改动**本地未提交**（end-work 只提交 doc 仓）；小程序需重编、`Order.cs` 需 `dotnet publish` 后生效。

## 1. 支付明细：他人代付标红 + 脱敏手机号列

需求 4 轮迭代（每轮用户看真机截图后细化）：
1. 「支付明细，他人代付条目字体变红，显示支付脱敏手机号，没有则显示 —」
2. 「支付方式后边增加一列『手机号』，自己付款该列空着，他人代付显示脱敏手机号」（从副行改成正式列）
3. 「手机号搞那么宽干啥？窄一点，不要挤日期时间，让所有文字在一行」（日期 `2026-06-19` 换行了）
4. 「手机号字体大小应该和其他列一样，在自己的列居中」

### 1.1 数据来源（确认可用）
- `OrderPayment.is_proxy_pay`（bool，prod 早有，2026-05-14 加）→ 代付标记
- `OrderPayment.cell`（代付人手机号，模型有 + DTO 6-20 已补；`is_proxy_pay=1` 时由 `PaymentIdentityController._applyChoice(proxy)` 写入，拿不到留空）
- `order.availablePayments` 直接返回 `OrderPayment` 实体列表 → 两字段随序列化下发
- 每笔 payment 的 `押金 ¥0.01` 行（per-rental）用的是 `rental.totalPaidGuarantyAmount`（per-rental，payment **有** Include，payStatus 可靠）—— 与第 3 节订单级的坑区分开

### 1.2 实现
- `rent_order_detail.js`：
  - 加模块级 `maskCell(cell)`：11 位 `138****7897`；非标准长度 >7 取前 3 后 4、>4 尾部打码；空/null 返 `—`
  - 支付明细循环（renderOrder）设 `payment._isProxy = is_proxy_pay===true||===1`、`payment._proxyCellMasked = _isProxy ? maskCell(cell) : ''`（自己付款空串、代付脱敏或 `—`）
- `rent_order_detail.wxml`：表头/支付行/退款行各插 `.pay-col-cell`（手机号）列，位于支付方式与金额之间；支付行 `class="pay-table-row {{item._isProxy?'pay-table-row--proxy':''}}"`
- `rent_order_detail.wxss`：
  - `.pay-table-row--proxy` 下 date/time/method/cell/amount 全部 `color:#E64340`（整条标红）
  - 列宽收敛 + 全列 `white-space:nowrap`：date 118 / time 100 / method 94 / cell 124（`text-align:center`、22rpx 同其他列）/ amount flex
  - **第 3 轮的真 bug 是缺 `nowrap`**：日期列窄了 + 没 nowrap → `2026-06-19` 折成两行。补 nowrap 后所有列单行

📌 设计判断：起初做成「代付行下方整宽副行」，用户明确要「列」→ 改 `.pay-col-cell` 独立列。最终列宽从手机号挤占 → 收窄 + 居中 + 同字号，靠 amount flex 列吸收余量，不挤 date/time。

## 2. 退租状态 bug（order 71766）：全部归还却显示「未退租」

用户：「租赁物已经全部归还，但租赁商品却不是退租状态？」截图 rentItem 状态=已归还（发放 18:38 / 归还 18:48），但退租卡显「未退租」。

### 2.1 根因（纯代码定位，不需 DB）
- 退租卡 wxml 绑 `item.end_dateDateStr` ← renderOrder 由 `rental.end_date` 派生（空则「未退租」）
- `rental.end_date`（新 `Rental` 表列）**新租赁流程从不写**：grep `\.end_date *=` 仅命中 `RentController.cs:2499/2704`，均作用于**旧 `RentOrder` 模型**（`_db.RentOrder.Entry(...)`），与新 `[Table("rental")]` 无关 → 恒 null → 恒「未退租」
- `rental.settled` 仅由结算/关单流程写（`RentController.cs:5202/5219`），归还租赁物不写 → 即便用后端 `realEndDate`（settled 门控）也取不到（71766 未结算）

### 2.2 修复（frontend `rent_order_detail.js`）
- 删 `end_date` 派生块，移到 rentItems 循环之后（item 标志位齐了）派生：
  - `relevantItems = rentItems.filter(!noNeed && !_replaced)`
  - `allReturned = relevantItems.length>0 && every(_returned)`（`_returned = returnDate != null`，后端 `RentItem.returnDate` = 末条 log 为已归还时的 create_date）
  - allReturned → 退租 = max(returnDate)；否则「未退租」
- 与 settled 无关（归还即视退租，匹配用户预期）。前端已有 `rentItem.returnDate`（GetRental include logs），无需后端改

## 3. 应退押金 bug（order 71766）：押金 0.01 / 租金 0，应退押金却 0.00

用户：「总计押金 0.01 总计租金 0.00，应退押金应该是多少？你好好看以前的代码。」

### 3.1 根因（截图数字直接反推）
- 应退押金 = `totalRentNeedToRefundAmount` = renderOrder 重算 `paidGuaranty - sumSummary + depositPaid`
- 截图：总计押金（`order.totalGuarantyAmount`）=0.01、总计租金（`sumSummary`）=0.00、应退押金=0.00 → 反推 `paidGuaranty`（=`rentProperties.totalPaidGuarantyAmount`）=0
- 两者差异：
  - `order.totalGuarantyAmount`（Order.cs:882）= Σ `rental.totalGuarantyAmount`，后者（Rental.cs:192）= `guaranty_type=='在线支付'` 的 amount 合计，**无 payStatus 过滤** → 0.01
  - `rentProperties.totalPaidGuarantyAmount`（Order.cs:1145）= Σ order 级 `guarantys` 中 `payStatus=='支付完成'` → 0
- 为何后者 0：`GetCommonOrders`(OrderController.cs:195) 的 `o.guarantys` Include **注释掉了 `.ThenInclude(g=>g.payment)`** → `Guaranty.payStatus`（Models/Guaranty.cs:31，遍历 `guarantyPayments[].payment.status`）无 payment 可判 → 退化（本单无 guarantyPayments 链记录时返「未支付」）
- 旧页 rent_details 与新页用同一 `Order/GetOrderByStaff` 端点；旧页直接显示后端 `totalRentNeedToRefundAmount`，新页 6-15 起改为前端重算（为让改赔偿/超时实时刷新），重算时押金基数选错了字段

### 3.2 修复（frontend）
- 押金基数 `paidGuaranty`（来自 rentProperties）→ 改用 `order.totalGuarantyAmount`（即展示的「总计押金」，可靠）
- 保留 sumSummary 实时重算（改赔偿/超时仍即时反映）
- 结果：应退押金 = 0.01 − 0 + 0 = 0.01 ✓；实际应退 0.01；申请退款按钮可点

## 4. 订单状态 bug（order 71766）：未退款却显示「全额退押金」

用户：「这单第一没退过款，第二应退押金不为 0，状态不该是『全额退押金』，应该是『全部归还』。」

### 4.1 根因
- 归还全部租赁物 → `RentController.cs:5200` `allReturned` 分支把 `rental.settled=1` **且 `guaranty.relieve=1`**（5210）。`relieve` 语义=押金占用解除/可退，**非已退款**（实际退款流程不碰 relieve，仅 5210 设 / 5219 re-issue 时清 0）
- `Order.cs:1180` 状态机 `settledCount==totalCount` 分支用 `relieveGuarantyAmount`(Σ payStatus=支付完成且 relieve=1 的押金) vs `paidGuarantyAmount` 判退押金档：`relieve>=paid`→全额退押金。归还即 relieve=1 → 直接「全额退押金」
- 「全额退押金」字符串全工程仅此一处产生（grep 确认；416-434 的 `s` 变量块只产「全部归还」）

### 4.2 修复（**后端 `Order.cs`**，需 publish）
状态机退押金档改以**实际退款** `refundAmount`（Order.cs:276，Σ availableRefunds.amount = payment_refund）为准：
```
needRefund = (totalGuarantyAmount ?? 0) - (totalRentSummaryAmount ?? 0) + depositPaidAmount
refundAmount <= 0.001         → 全部归还
refundAmount + 0.001 < needRefund → 部分退押金
else                         → 全额退押金
```
- 用可靠字段（totalGuarantyAmount / refundAmount），绕开不可靠的 paidGuarantyAmount
- 无递归（这几个 getter 都不依赖 rentProperties）
- **行为波及所有订单**：归还但未退款的单由「全额退押金」回正「全部归还」，退押金态仅真退款后出现 —— 正是用户要的口径
- 71766 trace：refundAmount=0 → 全部归还 ✓

## 5. 按租赁商品 / 按租赁物 视图重构

用户 4 条：① 按商品不要「全部归还」按钮 ② 按物品每个租赁物要操作按钮（参考旧版图）③ 按物品要「全部归还」按钮 ④ 切换 tab 做舒展、文字显示全。

### 5.1 现状
- Tab 0「按商品」：rental 卡 + 费用 + 租赁物明细（**含**每件操作按钮 rid-actions + per-rental「全部归还」）
- Tab 1「按物品」：扁平只读 `all-item-row` 列表（无操作）
- tab pill 挤在卡标题右上角，标签缩成「按商品/按物品」

### 5.2 用户决策（AskUserQuestion）
「按商品里每件操作按钮怎么处理」→ 选**移到按租赁物**（按商品只做只读概览）。

### 5.3 实现
- 抽 ~130 行租赁物卡为 `<template name="rentItemCard">`，加 `readonly` flag：
  - readonly=true：隐藏 赔偿按钮 / rid-actions（归还/暂存/更换/发放/设未归还）/ 备注改只读文本
  - readonly=false：全操作
  - 用 `data="{{rentItem, ridx, iidx, expLogs, expChg, refundAmount, readonly}}"`；`_expandedItemLogs[ridx+'_'+iidx]` 经 `expLogs[...]` 传入；bindtap+data-ridx/iidx 仍绑页面方法
- Tab 0：删 per-rental 全部归还按钮 + 改用 `<template is="rentItemCard" readonly:true wx:for items>`
- Tab 1：删扁平列表 → `<block wx:for=rentals>` 内 `<template ... readonly:false wx:for items>` + 底部订单级「全部归还」`onReturnAllOrder`（收集所有非 noNeed/非已归还/非已更换件，二次确认后跨 rental 顺序调 `Rent/ReturnAllRentItems/{rentalId}` → getData）
- tab pill：移出标题右上角，改整宽分段控件 `.rental-tab-pill`（flex:1 等分、active 白底主色），标签补「按租赁商品 / 按租赁物」
- 旧 `onReturnAllRental` / `_allRentItems` 构建 / `.tab-pill` `.all-item-*` wxss 现无引用，本次留存未清（死代码，无害）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) | `maskCell` + 代付列派生；退租按归还事件派生；应退押金基数改 `order.totalGuarantyAmount`；`onReturnAllOrder` |
| [`.../rent_order_detail.wxml`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml) | 手机号列（表头/支付/退款）；`rentItemCard` 模板；两 tab 重构；整宽 tab pill |
| [`.../rent_order_detail.wxss`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss) | `.pay-col-cell` + 代付红 + nowrap；`.rental-tab-pill` + `.return-all-bar` |
| [`SnowmeetApi/Models/Order/Order.cs`](../../SnowmeetApi/Models/Order/Order.cs) | 退押金状态（1180 起）改 `refundAmount` 口径（**需 publish**） |

## 学到的小知识

1. **新租赁流程不写 `Rental.end_date`**：grep `\.end_date *=` 全是旧 `RentOrder` 模型。退租展示必须按 `RentItemLog` 领还事件派生，绑 end_date 列恒「未退租」。
2. **`rentProperties.totalPaidGuarantyAmount` 在 GetOrderByStaff 上下文不可靠**：订单级 `o.guarantys` 的 `.ThenInclude(g=>g.payment)` 在 GetCommonOrders 被注释 → `Guaranty.payStatus` 退化 → 已收押金算 0。展示「总计押金/应退押金」用 `order.totalGuarantyAmount`（`rental.guaranties` 在线支付合计、无 payStatus 依赖）。
3. **`guaranty.relieve=1` ≠ 已退款**：归还即置位（仅"可退"）。退押金状态判定看实际 `refundAmount`（payment_refund），别用 relieve。
4. **WXML `<template name>` + `readonly` flag** 复用同一卡片做「只读视图/操作视图」：自闭合 `<template is=... wx:for data="{{...readonly}}"/>`，data 传 ridx/iidx/展开态 map/refundAmount，bindtap 仍绑页面方法、data-* 用 template scope。避免 ~130 行重复。
5. **截图 UI 数字是最快诊断证据**：「总计押金 0.01 / 总计租金 0.00 / 应退押金 0.00」三个数直接反推派生用错字段，比连库快。
6. **金额状态类 bug 改前先确认「字符串/状态全工程唯一产生点」**：grep「全额退押金」确认仅 `Order.cs:1180` 一处，改动面可控。
