# 2026-10-23 扫码报到算已核验本人 + 测试订单 + 隐藏个人微信转账：四项后端改动已推送，等审核后部署

Mac mini（`/Users/cangjie/source/snowmeet/snowmeet_ai`）。接续 10-22～23 的扫码接待上线工作。改动落在 SnowmeetApi（`ai`，`33e1b2de` → `2d611b98`）和 snowmeet_wechat_mini（`ai`，`5de080ba` → `f8a1d17e`），**都已推送，都未部署 / 未上传**。

## 1. start-work

- 文档仓 `git pull` 走 22 端口 60 秒超时，改走 443（`ssh.github.com`，`HostKeyAlias=github.com`）。第一次被 kill 的拉取已把远端引用更新，导致 443 那次报 `cannot lock ref`，直接 `merge --ff-only origin/main` 快进到 `e28a804`。
- 四个仓库 fetch（443）：SnowmeetApi 落后 22（10-15～10-23 的食材 v4 / 七色米 / 扫码接待），小程序、公众号已同步，reqai 落后 18。
- 核实：10-16 下午那 4 个食材 v4 提交（到 `6e38f60d`）是已部署 `33e1b2de` 的祖先，**早已上线**，文档里的「待确认」可以划掉。
- `scan.py --check`：#5 #7 两个 reqai 会话未分析。

## 2. 扫码报到后，用券还要不要再核验身份

### 2.1 用户的问题

> 如果顾客在开单之前就识别身份了……使用了优惠券，他支付成功后，是不是就可以直接核销了？

### 2.2 核查结论（当时）

- 订单的「已核验本人」标识是 `order.wechat_unverified`（1 = 已核验，命名与字面相反）。写入点只有两处：`PaymentIdentity/VerifyWechatIdentity`（扫核验码）和 `DealSuccessPaidOrder`（本人微信付款）。
- 扫码报到只写 `scan_qrcode`（`scaner_member_id`、`cell`、`scan_time`），和订单没有关联。
- 按付款方式分：
  - 本人微信付款：付款即核验，本来就不用再扫；
  - 支付宝（养护）：先弹核验码（`order-payment/index.js` 第 193 行）；
  - 券卡全额 0 元单、储值：`WriteoffCareOrder` 要求已核验（后端 `OrderController.cs` 3526 行 + 前端 104 行）；
  - 租赁储值付租金、次卡销售：同一个标识。
- 顺带发现：「现金 / 其他」确认收款完全不做身份核验，券照样核销（已告知用户，未处理）。

### 2.3 用户拍板

> SnowmeetApi 已经pull，反正就是开单前的接待页面扫码了验证身份了，订单从一生成开始，wechat_unverified 就应该设置为1。

## 3. 实现：订单一生成就是「已核验本人」

### 3.1 第一版：小程序带报到码（`c5605156` / `6fc36470`）

- `recept_member` 跳 `recept_new` 时带 `checkinId`；`recept_new` 在 `SaveRentRecept`、`SaveCareRecept`、`PlaceOrder` 的 URL 上带它。
- 后端新文件 `Helpers/OrderVerifiedRules.cs`：
  - `CheckinVouches`：`rc_` 码、`IsVerified`（scaned=1 + 有会员 + 有手机号）、`staff_id` 是本店员、`scaner_member_id` 是订单会员、`scan_time` 在 60 分钟内（复用 `CUSTOMER_WAIT_MINUTES`）；
  - `ResolveOnSave`：担保 → 1；否则库里已是 1 且会员没换 → 1；其余 0。**不采信前端传来的值**（草稿接口把整单原样写库）；
  - `ResolveOnPaid`：本人微信付款 → 1；此前已核验且这次付款没改订单会员 → 保持 1；其余 0；
  - `ChangeLog`：取值变化写 `core_data_mod_log`（scene=开单）。
- 「店员输手机号、店长授权」进入时 `recept_member` 也拿到同一个 `checkinId`，但那张码 `scaned=0`，`IsVerified` 不通过，自然排除。
- `DealSuccessPaidOrder` 原规则（6-15 用户定的「其余一律 0」）会把已核验的单在支付宝付款后冲回 0，与「从生成开始就是 1」冲突，改为 `ResolveOnPaid`。
- 收银组件 wxml：已核验时按钮改「确认核销 / 确认储值扣款」，原来写着「微信核验会员本人并核销」，点了却直接核销，文案误导。

### 3.2 用户追问「为什么需要修改小程序」

- 回答：报到和订单没关联，只有店员手机知道这张单从哪个报到来的，所以让小程序带。**但这不是唯一办法**：后端可以自己查「这位店员 60 分钟内、被本单会员本人扫码验证过的报到」，条件和传参几乎等价。
- 关键点：扫码报到页面本身在未上传的 `5de080ba` 里，小程序无论如何要上传；后端自己查的好处是部署即生效，手动录入页、找回中断单开的单也能覆盖。
- 用户：「上一个问题改成后段自己查吧」。

### 3.3 第二版：后端自己查（`902af2ed` / `1d51fac0`）

- `QrCodeController.ResolveReceptOrderVerified(order, staffId)` 返回 `(库里原值, 新值, 担保的报到码 id)`：
  - 已是 1 且会员没换 → 直接返回，不查报到（草稿每改一次就保存一次）；
  - 否则查 `scan_qrcode` 里 `staff_id`=本店员、`scaner_member_id`=订单会员、`scaned=1`、`scan_time` 在 60 分钟内的候选，用 `OrderVerifiedRules.PickVouchingCheckin` 取最近一条。
- 三个接口去掉 `checkinId` 参数；小程序 `recept_member`、`recept_new` 撤掉传参。

## 4. 「这是测试订单」（`bfe9d020` / `0d65bbb2`）

- 用户要求顾客信息页加勾选，勾了下单时 `order.is_test=1`。
- 现有规则：租赁/养护草稿新建时按域名（不是 `mini.snowmeet.top` 就是测试单），零售 `PlaceOrder` 按店员 28/31/34；两处都覆盖前端值；`PlaceRentOrder` / `PlaceCareOrder` 不动 `is_test`。
- 做法：勾选行放在店铺和业务类型之间（自定义勾选框，勾上变红）；`isTest=1` 带到 `recept_new`，三接口加 `isTest` 参数，「勾了就是测试单」叠加在原规则上。零售 `PlaceOrder` 只认店员会话（顾客自己买次卡也走它）。
- 只加在 `recept_member`，`recept_entry` 是否要加问了用户，未答复。

## 5. 隐藏个人微信转账（`2d611b98`）

- 用户：「这些以微信转账结尾的支付方式，全部隐藏，暂时不允许个人微信转账。」截图圈了苍杰微信转账、王政微信转账、肖志强工作微信转账。
- 列表来源：`Order/GetUnCommonPayMethod` 取历史收款成功的 `pay_method` 去重，前端再加「京东收银 / POS机刷卡 / 现金」和「手工填写」。新版 `order-payment`、旧版 `payment.js`、`legacy` 都用它。
- 改动：`Helpers/PayMethodRules.IsPersonalWechatTransfer`（`EndsWith("微信转账")`）；列表接口过滤；`EffectUnpaidOrder` 在作废旧待支付单之前拒绝（`!payLater` 时），提示「暂不允许个人微信转账收款」，堵住「手工填写」。
- 就叫「微信转账」的那一项用户没圈，按「全部」字面一并隐藏，已告知可以排除。
- 核实前端只 `encodeURIComponent` 一次，ASP.NET 自动解码，后端判断有效。

## 6. 养护详情页打印按钮移位（`f8a1d17e`）

- 用户截图：「这两个打印按钮，应该放到装备信息之后，养护任务之前。」
- `care_order_detail.wxml` 把「打印」块从卡片底部（发板核销之后）移到「养护任务」标题之前；间距沿用（按钮行和子标题上边距都是 24rpx）。编辑模式下按钮在编辑面板下面。

## 7. 部署讨论

- 用户问：「如果现在部署服务器端，旧的小程序客户端还可以安全运行吗？之前提交的小程序还没有通过审核。」
- 逐项核对：
  - 新参数都是可选的，返回格式不变；
  - 线上旧版没有报到页面，后端查不到报到，行为不变；草稿阶段旧版本来不会合法地写 1；
  - 支付回调只影响「已扫核验码、再用支付宝 / 代付」的单，结果是不再要求重复核验；
  - 个人微信转账：旧版列表同样看不到；手工填写被拒、订单保持未付，但旧组件 `.catch` 固定弹「处理失败」，盖掉后端原因；
  - 审核中的版本：带不带 `checkinId` 后端都能处理（多余参数被忽略）；其收银组件「已核验就直接核销」的逻辑本来就有，只是按钮文案旧。
- 结论：可以单独先部署后端。**用户决定：「现在不要部署，等现在审核的小程序通过审核后，我们再来部署。到时候我通知你。」**

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Helpers/OrderVerifiedRules.cs`](../../SnowmeetApi/Helpers/OrderVerifiedRules.cs) | 新建：报到担保、挑报到、草稿保存取值、支付成功取值、变化日志 |
| [`SnowmeetApi/Helpers/PayMethodRules.cs`](../../SnowmeetApi/Helpers/PayMethodRules.cs) | 新建：以「微信转账」结尾即个人微信转账 |
| `SnowmeetApi/Controllers/QrCodeController.cs` | 新增 `ResolveReceptOrderVerified`（后端查报到） |
| `SnowmeetApi/Controllers/RentController.cs` | `SaveRentRecept`：后端定已核验 + `isTest` |
| `SnowmeetApi/Controllers/CareController.cs` | `SaveCareRecept`：同上 |
| `SnowmeetApi/Controllers/OrderController.cs` | `PlaceOrder` 已核验 + `isTest`；`DealSuccessPaidOrder` 改 `ResolveOnPaid`；`GetUnCommonPayMethod` 过滤；`EffectUnpaidOrder` 拒绝个人微信转账 |
| `SnowmeetApi/SnowmeetApi.Tests/OrderVerifiedRulesTests.cs`、`PayMethodRulesTests.cs` | 新增单测 15 + 12 项 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_member.{js,wxml,wxss}` | 「这是测试订单」勾选，带 `isTest=1` |
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.js` | `_receptQuery` 给三个建单请求带 `isTest` |
| `snowmeet_wechat_mini/components/order-payment/index.wxml` | 已核验单的核销按钮文案 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.wxml` | 打印按钮移到装备信息之后 |

## 学到的小知识

1. **报到和订单的关联可以由后端推断**：同一店员 + 同一会员 + 短时间窗，几乎等价于前端显式传报到 id，还能覆盖其他开单入口，且不依赖小程序发版。
2. **草稿接口原样写库会让「状态字段」被前端旧值覆盖**：`recept_new` 去结算后把上一单 `...rentOrder` 展开成新草稿，旧的 `wechat_unverified` 会被带进去。状态类字段要由后端决定。
3. **改规则前先看谁会把它冲掉**：只在建单时置 1 不够，`DealSuccessPaidOrder` 每次付款成功都会重算，非本人微信付款会冲回 0。
4. **Node 24 的 `node --test` 子进程通信报 `Unable to deserialize cloned data`**：加 `--test-isolation=none` 在同进程跑；顺带暴露出一个用例结束后仍有异步回调的旧测试。
5. **只隐藏选项不等于禁止**：有「手工填写」时，必须在确认收款接口里再拦一次。
6. **旧客户端的错误提示可能被覆盖**：`performWebRequest` 先弹后端 message，调用方 `.catch` 再弹「处理失败」，后者覆盖前者。
