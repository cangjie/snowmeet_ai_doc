# 2026-06-15 储值付租金 + 微信身份核验：rent_order_detail 退款区一路打磨到「储值付租金需扫码核验本人」

接 6-15 早/续2（租赁物明细卡重构、超时费按天 + 免除）之后的延续。这场会话全在新版租赁订单详情页 `pages/admin/rent/rent_order_detail/` 的「租赁物明细卡 + 退款区」上推进，最后长出一整套「用会员储值付租金前要微信核验本人」的前后端 + 新落地页。环境无 devtools，全部只过 `dotnet build` / `node --check` / wxml 标签平衡，**真机与部署都没测**。

## 1. 已更换（被换下）租赁物：置灰 + 不计件

### 1.1 需求（用户原话）
- 「被更换掉的物品，首先，不用有赔偿按钮，既然都已经更换完成了，说明租赁物没有问题；第二，被更换掉的物品应该用更深一点的底色和更浅一点的文字颜色来体现该租赁物已经不可用。」
- 「被换下来的租赁物，不统计在件数当中。」

### 1.2 实现
- `renderOrder` 派生 `rentItem._replaced = (rentItem.status == '已更换')`。
- 卡片加 `item-detail-card--replaced`：底色 `#fff→#e6eaf0`、头部条 `#eff4ff→#dbe1e9`、文字 `#0b1c30/#3f4850/#6f7881 → #9aa3ad/#b0b8c0`。
- 赔偿按钮 gated `!_replaced`；已更换时所有操作按钮都不显示 → 连带把空的 `.rid-actions` 行也 `wx:if` 掉。
- 件数：`rental._activeItemCount = (rentItems||[]).filter(it=>!it._replaced).length`，wxml「租赁物明细 ({{item._activeItemCount}}件)」。

## 2. 赔偿入口重做

### 2.1 移到「赔偿金额」行
- 原赔偿按钮在底部操作行（归还/暂存/更换/赔偿）。用户：「赔偿按钮放在赔偿金额那一行」。
- 移到 `rid-kv`（赔偿金额行）右侧，新样式 `rid-kv-repair-btn`（紧凑红色，仿 `rid-mini-btn` 尺寸 + danger 色），`!_replaced` 才显示。

### 2.2 改成弹窗
- 用户：「点击赔偿按钮，应该弹出和修改押金租金一样的对话框输入金额」。
- 复用本页租金明细弹窗的 `dc-*` 样式做单字段「赔偿金额」弹窗：点开自动清空、原值作 placeholder、`focus` 自动弹键盘；留空回退原值（复用 `_resolveDayChargeVal`）。
- 确定仍走原 `Rent/SetRentItemRepairAmount/{id}?amount=` + `refreshStatus`。新增 data `_repairShow/_repairItemId/_repairAmount/_repairAmountOrig` + handler `onItemRepairEdit`(开弹窗)/`onRepairInput/onRepairCancel/onRepairConfirm`，删掉原行内编辑分支。

## 3. 退款结算「设了赔偿不计算」——根因 + 修复（本场最关键）

### 3.1 现象
- 用户设了赔偿，退款区「总计赔偿 ¥0.00 / 实际应退」不动。后又出现「showcase 赔偿=0 但总计赔偿=¥1」自相矛盾的截图。

### 3.2 根因
- 退款区绑的 `order.totalRentRepairAmount` / `totalRentUnRefund` / `totalRentNeedToRefundAmount` 是后端 `Order` 的 `[NotMapped]` **订单级计算属性**——拉单（GetOrderByStaff）序列化那一刻算成静态数字下发。
- 但前端 `getData` 会逐条 `getRentalPromise` 替换 `order.rentals[i]`，且改赔偿/改租金只 `refreshStatus(newRental)` 换**单条 rental** 再 `renderOrder`——这些订单级标量**从不重算**，永远停在拉单瞬间的旧值。
- 「showcase=0 / 总计=1」正是这个：showcase 读最新 rental、总计读旧标量。（也据此判断出某次"对不上"其实是旧编译包。）

### 3.3 修复
- `renderOrder` 里用最新 `order.rentals` **重新累加**：`sumSummary/sumOvertime/sumRepair`（`totalSummary` 仅 `!experience && !entertain` 计入），赋回 `order.totalRentSummaryAmount/OverTimeAmount/RepairAmount`；再 `totalRentNeedToRefundAmount = paidGuaranty - sumSummary + depositPaidAmount`、`totalRentUnRefund = … - refundAmount`。口径与 `Models/Order/Order.cs` 的 getter 一字不差（赔偿/超时/减免都已含在 `Rental.totalSummary` 里）。
- 副作用红利：租金明细弹窗改超时/租金/减免后，退款区也随之刷新了（之前同样不刷）。

## 4. 可用储值 + 储值付租金（从旧版 rent_details 移植）

### 4.1 需求
- 用户给了旧版 `rent_details`（【】方括号样式）截图：要「显示可用储值」+「可以用储值支付」。

### 4.2 实现
- 退款区加行：`可用储值 ¥xxx  储值付租金 ☐`，`wx:if="{{order.member.availableDeposit > 0}}"`。
- 勾选语义：租金改由会员储值支付 → 押金全额退。`renderOrder` 里 `if (payWithDeposit && !(depositPaidAmount>0)) totalRentUnRefund += sumSummary`（已用储值支付过则 depositPaid 项已含、不重复加）。
- 退款 `_refundWithDeposit`：`储值支付确认` modal → `data.payWithDepositPromise`（`Order/PayWithDeposit`，已存在）→ 再退全额押金（`refundPromise`）。`onRefund` 勾选时分流到它。

### 4.3 「加了为什么不显示」——根因
- 用户：「这两项你没加上呀？显示在哪儿了？」（看的是旧 `rent_details` 页）。
- 真因：`Member.availableDeposit` 是按 `depositAccounts` 求和的 `[NotMapped]`，**GetOrderByStaff 的 `order.member` 不带 depositAccounts** → `availableDeposit=0` → 行被 `wx:if` 藏了。旧版 rent_details 之所以有，是它 `getData` 额外 `getMemberPromise(order.member_id)` 拉了完整 member。
- 修复：新版 `getData` 在 `Promise.all(rentals)` 后补一发 `getMemberPromise`，把 `member.availableDeposit` 拷到 `order.member` 再 `renderOrder`。

## 5. 储值付租金的微信身份核验门槛（plan 流程）

### 5.1 需求（用户原话）
- 「order 表有字段 `wechat_unverified`，顾客用微信支付、支付中拿到的 member_id 和订单 member_id 一致则置 1，否则都 0，即便本人支付宝也不行。然后退款页勾了储值付租金但此时 `wechat_unverified=0`，则弹微信二维码让顾客扫码验证身份，验证后 member_id 与订单一致，勾选才生效。」

### 5.2 探查 + plan 决策
- 查清：`wechat_unverified` 此前**只写不读**（仅 `DealSuccessPaidOrder` 对支付宝置 true），故重定义其语义（1=已核验本人）安全；现有 `CheckPayerIdentity` 比对扫码人/订单会员，但**硬绑「待支付的 payment」**，无法直接复用于纯核验。
- AskUserQuestion 三问，用户全选推荐：①新建按 orderId 的纯核验流程 ②核验通过持久化写库 ③店员端轮询状态接口。plan 已批准。

### 5.3 实现
- **Part 1 写入** `OrderController.DealSuccessPaidOrder`：把原「支付宝→true」整块换成
  `wechat_unverified = 微信支付 && !is_proxy_pay && paidOp.member_id != null && paidOp.member_id == order.member_id`（在 `order.member_id = paidOp.member_id` 之后求值；非代付微信支付 → true，代付/支付宝 → false）。
- **Part 2 后端** `PaymentIdentityController` 两个 `[HttpGet]`：
  - `VerifyWechatIdentity(orderId, sessionKey)`：`_loadSessionContext` 取扫码人 `sess.member_id`，与 `order.member_id` 比对；命中则 `order.wechat_unverified=true` + `_db.order.Entry(order).State=Modified` + `CoreDataModLog`（防全局 NoTracking 静默不存）+ SaveChanges，返回 `{matched:true}`；不命中返回 `{matched:false, orderMemberMaskedCell}`。
  - `GetWechatVerifyStatus(orderId, sessionKey)`：`Util.GetStaffBySessionKey` 鉴权，只读返回 `{verified: order.wechat_unverified}`。
- **前端**：
  - 新页 `pages/order/identity_verify.{js,wxml,wxss,json}`：onLoad 解析 orderId（兼容 `options.q`）、`app.loginPromiseNew` 登录 → `VerifyWechatIdentity` → 显示 加载中/✅成功/❌不一致/失败。`app.json` 注册。
  - `data.js`：`verifyWechatIdentityPromise` + `getWechatVerifyStatusPromise`。
  - `rent_order_detail`：`onTogglePayWithDeposit` 勾上时——已勾→关；`wechat_unverified` 真→直接生效；否则 `_openWechatVerify()` 弹二维码（`MediaHelper/GetQRCode?qrCodeText=<verify URL>`）+ `_startVerifyPolling`（2s 调 `GetWechatVerifyStatus`，verified 后关弹窗、本地置 `wechat_unverified=true`、`payWithDeposit=true`、`renderOrder`）；`onHide/onUnload` 清 timer。

### 5.4 二维码路径的两版
- 初版：复用已登记的 `mini.snowmeet.top/mapp/order_payment?verifyOrderId=`，由 `payment_entry.onLoad` 检测 `verifyOrderId` → `redirectTo` identity_verify（省公众平台报备）。
- 用户问「为什么除了核验页还要弄个入口页？」→ 改成**专用 `order_verify?verifyOrderId=` 直达 identity_verify**；删回 `payment_entry` 的转跳 + onShow 守卫（恢复其纯支付）。需用户在公众平台登记 `order_verify → pages/order/identity_verify`。

## 6. 「点了储值付租金不弹码」排查（疑似旧包）
- 用户：order 71746 `wechat_unverified=0` 但点了不弹码、勾选框却是 ✓。
- 推理：门槛代码已确认在源码、`wechat_unverified` 是普通 bool 列、DB=0 必序列化为 false → 我的代码**只可能弹码、不可能直接打勾**。直接打勾只剩两解释：①跑的是旧编译包（本会话反复出现）②`depositPaidAmount>0` 把勾选框锁成选中+置灰、点击 early-return。
- 措施：在 `onTogglePayWithDeposit` 顶部加临时 `console.log('[储值付租金] tap', {wechat_unverified, depositPaidAmount, availableDeposit, payWithDeposit})`，请用户重编后看 console 区分。**此 log 待移除。**

## 7. 顺带的只读排查
- `components/firstui/fui-icon/fui-icon.wxss` **仍在用**：app.json:190 全局注册 + `fd_order_detail.wxml`(×4)/`fd_category_prod_list.wxml`(×1) 的 `<fui-icon name="close">`。
- `fui-col` **大量在用**：app.json:176 注册 + 6 文件（`components/rent/rent_charge` + `order_entry`/`care_order_list`/`new_rent_list`/`print_task`/`retail_order_list`），始终与 `fui-row` 配对。两者都别删。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Controllers/OrderController.cs`](../../SnowmeetApi/Controllers/OrderController.cs) | `DealSuccessPaidOrder` 改 `wechat_unverified` 写入规则（微信+本人=1，否则 0） |
| [`SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`](../../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) | 新增 `VerifyWechatIdentity` + `GetWechatVerifyStatus` |
| [`rent_order_detail.js`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) | `_replaced`/`_activeItemCount`、赔偿弹窗、退款重算、`availableDeposit` 补拉、储值付租金、核验门槛+轮询+诊断 log |
| [`rent_order_detail.wxml`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml) | 已更换卡 class、赔偿行按钮、可用储值/储值付租金行、赔偿弹窗、微信核验二维码弹窗 |
| [`rent_order_detail.wxss`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss) | `--replaced`、`rid-kv-repair-btn`、`refund-deposit-*`、`verify-qr-*` |
| [`pages/order/identity_verify.{js,wxml,wxss,json}`](../../snowmeet_wechat_mini/pages/order/identity_verify.js) | 新建：扫码身份核验落地页 |
| [`utils/data.js`](../../snowmeet_wechat_mini/utils/data.js) | `verifyWechatIdentityPromise` + `getWechatVerifyStatusPromise` |
| [`app.json`](../../snowmeet_wechat_mini/app.json) | 注册 `pages/order/identity_verify` |
| `pages/order/payment_entry.js` | 加过 verifyOrderId 转跳，后又删回（净无改动） |

## 学到的小知识

1. **订单级 `[NotMapped]` 汇总 = 拉单瞬间快照**：前端再 setData 局部换 rental 不会触发后端 getter 重算；要在 `renderOrder` 用最新 rentals 自己累加。退款金额/总计赔偿/总计超时全受此影响——这是「设了赔偿不计算」的真因。
2. **`Member.availableDeposit` 默认拿不到**：它按 `depositAccounts` 求和，而 `GetOrderByStaff` 的 `order.member` 不 Include depositAccounts；要单独 `getMemberPromise` 补。
3. **`wechat_unverified` 命名反直觉**：本需求里 1=已核验本人。改前先确认它原本无任何读取方，重定义才安全；代码两处加注释提醒后人。
4. **普通链接二维码开小程序**：模拟器扫不出、需真机；URL 在 `options.q`（要 `decodeURIComponent`）。专用路径（`order_verify`）要在公众平台「扫普通链接二维码打开小程序」单独登记测试链接/正式规则；复用已登记路径 + 小程序内 `redirectTo` 可免报备。
5. **全局 NoTracking 老坑又一例**：`VerifyWechatIdentity` 写 `order.wechat_unverified` 必须显式 `_db.order.Entry(order).State = EntityState.Modified` 否则静默不存。
6. **`util.performWebRequest` 约定**：`code==0` resolve `res.data.data`（已拆包）；`code!=0` 弹 toast + reject。所以「不匹配」要返回 `code=0 + {matched:false}` 才能正常 resolve、不弹错误 toast。
