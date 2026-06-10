# 2026-06-10 「切支付宝 order_payment 仍是微信支付」根因定位：线上后端旧构建

纯排查会话，无任何代码改动。承接用户在最终支付页（店员侧收款二维码页 `pages/payment/settle/` 的 `order-payment` 组件）的反复反馈：切换微信支付/支付宝时，新插入的 `order_payment` 记录 `pay_method` 一律是微信支付。上一轮我把它误判为「前端 stale build」，被用户用「现在已能生成真实支付宝二维码」否定后，本轮逐层读源码 + 翻 git 史定性，结论是**源码已修、线上后端是 6/2 修复前旧构建**。

## 1. 现象与上一轮的误判

### 1.1 用户反馈

- 「收款二维码页面，切换支付方式，order_payment 中新插入的记录，永远是微信支付。即使选择了支付宝，插入的记录也是微信支付。」
- 「现在可以真实地生成支付宝小程序的二维码，支付宝扫描后进入 `pages/payment_entry/index?paymentId=xxxx`，xxxx 就是 paymentId。」
- 「那么，现在在最终支付页面，切换微信支付和支付宝，order_payment 的记录的 pay_method 为什么一律都是微信支付？」

### 1.2 上一轮误判（需避免重复）

- 上一轮把 bug 归为「前端旧 bundle（b7b5a23 之前 alipay 走 `showWepayQrCode`）」。
- 用户「现在能生成真实支付宝二维码」实质否定了该解释：能出真实 alipay scheme 码 ⇒ 前端是新版。
- 教训：用户二次反馈同一现象时，「重新构建/部署」必须先用源码 + git 史坐实「源码已对、线上滞后」再讲。

## 2. 逐层读源码：排除源码 bug

### 2.1 前端路由全对（`snowmeet_wechat_mini/components/order-payment/index.js`）

- [`onMethodTap`](../../snowmeet_wechat_mini/components/order-payment/index.js#L63)：`wechat → showWepayQrCode`，`alipay → showAlipayMiniQrCode`，切换先清旧码 + 复位 + 关 socket/轮询。
- [`showAlipayMiniQrCode`](../../snowmeet_wechat_mini/components/order-payment/index.js#L92)：调 `Order/GetAlipayMiniPayment/{orderId}?sessionKey=`，拿回 `payment.id` 后编 `alipays://platformapi/startapp?appId=2021006157624571&page=` + encode(`pages/payment_entry/index?paymentId={id}`)，再过 `MediaHelper/GetQRCode` 成图。
- [`showWepayQrCode`](../../snowmeet_wechat_mini/components/order-payment/index.js#L119)：调 `Order/GetWepayPayment`，编 `https://mini.snowmeet.top/mapp/order_payment?paymentId=`。
- 组件 `attached`（[:27](../../snowmeet_wechat_mini/components/order-payment/index.js#L27)）只 `loadOrder()`，**不预建任何 payment**；`payMethod` 初始 `''` —— 排除「页面加载默认建微信行」的干扰。

### 2.2 关键认知：支付宝 scheme 二维码不编码 pay_method

- alipay scheme 码里只有 `paymentId`，**没有 pay_method**。
- 所以「二维码能跳进 payment_entry」**只能证明**：① 前端是新版（在编 alipay scheme）② 后端存在 `GetAlipayMiniPayment`（≥ `95b0bbd`）。
- **不能证明**那条记录的 pay_method 是支付宝 —— 这是上一轮和本轮判断的分水岭。

### 2.3 后端建单全对（`SnowmeetApi/Controllers/OrderController.cs`）

- [`GetAlipayMiniPayment`](../../SnowmeetApi/Controllers/OrderController.cs#L1722)：先 `InvalidatePendingOrderPayments(order, staff?.id, "切换为支付宝")`，再 `new OrderPayment{ pay_method = "支付宝", ... }`（[:1754](../../SnowmeetApi/Controllers/OrderController.cs#L1754)），scene=`准备支付宝小程序支付`，返回该新单。
- [`GetWepayPayment`](../../SnowmeetApi/Controllers/OrderController.cs#L1431)：先 `InvalidatePendingOrderPayments(..., "切换为微信支付")`，再插 `pay_method="微信支付"`（[:1467](../../SnowmeetApi/Controllers/OrderController.cs#L1467)）。
- 工作区干净（`git status` 空）= 跑的就是 HEAD `f455a87`，无未提交改动。

**小结**：当前源码任何路径，点支付宝都只会插支付宝行。源码无 bug。

## 3. git 史钉死根因

`git log` + `git show` 关键 commit（`Controllers/OrderController.cs`）：

### 3.1 `95b0bbd`（5/31 新增 `GetAlipayMiniPayment`）

- 插入行从第一天就是 `pay_method = "支付宝"`。**新插入行从来不是微信支付** —— 用户「新插入的记录是微信支付」是表象，不是字面真相。

### 3.2 `a127a16 switch payment` + `7315358 set paymethod`（均 2026-06-02）= 修复点

- 旧版作废逻辑**只清同种支付方式**：
  - 旧 `GetWepayPayment` 只作废 `pay_method.Equals("微信支付")` 的待支付单。
  - 旧 `GetAlipayMiniPayment` 只作废 `pay_method.Equals("支付宝")` 的待支付单（`7315358` diff 删的正是这段 inline 过滤）。
- 后果（**先点微信、再切支付宝**）：微信待支付单没被作废，与新建的支付宝单**同时 `valid=1 待支付`**；下游/查询取「有效待支付」时命中残留微信单 → 表现为「永远微信支付」。
- 修复：`a127a16` 抽出 [`InvalidatePendingOrderPayments`](../../SnowmeetApi/Controllers/OrderController.cs#L1290)（不分支付方式清掉**所有** `valid=1 待支付` 单 + 调 AliController/TenpayController 关预下单 + 写 `core_data_mod_log`），并接入 `GetWepayPayment` / `GetAlipayMiniPayment` / `GetAlipayPaymentQrCode` / `EffectUnpaidOrder`；同批给 `WechatPayByOrderPayment` 加 `valid==1` 守卫。`7315358` 把 `GetAlipayMiniPayment` 那段也换成统一调用。

### 3.3 定位线上构建窗口

- 能出**真实支付宝二维码** ⇒ 线上 ≥ `95b0bbd`（5/31）。
- **仍复现**该 bug ⇒ 线上 < `a127a16`（6/2）。
- ⇒ 线上 SnowmeetApi 构建落在 **[2026-05-31, 2026-06-02)**。

## 4. 结论与交付动作

- **源码（本地 HEAD `f455a87`）已含修复，线上未部署。**
- **动作：重新部署 SnowmeetApi（HEAD `f455a87`）到生产 `snowmeet.wanlonghuaxue.com` 即可，无需改码。**
- 部署后自检：先点微信再切支付宝，查该订单 `order_payment` 应只剩 **1 条** `valid=1 待支付`（支付宝）；`core_data_mod_log` 有 scene=`切换为支付宝` 把那条微信行置 `valid=0`。
- 未能直接核实线上部署 commit：`SnowmeetApi` 早前 `git fetch` 因权限失败、且无生产库/部署面板访问；结论靠「源码 + git 史 + 现象窗口」三方坐实。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| （无代码改动） | 本会话为纯排查 |
| `snowmeet_ai_doc/CLAUDE.md` | 状态日期戳 → 2026-06-10；新增「已知遗留」根因条目 + 本日开发日志 |
| `snowmeet_ai_doc/sessions/2026-06-10_*.md` | 本归档 |

涉及（只读）的源码：[`order-payment/index.js`](../../snowmeet_wechat_mini/components/order-payment/index.js)、[`OrderController.cs`](../../SnowmeetApi/Controllers/OrderController.cs)（`GetAlipayMiniPayment` / `GetWepayPayment` / `GetReadyOrderPayment` / `InvalidatePendingOrderPayments`）。

## 学到的小知识

1. **alipay scheme 二维码只编 `paymentId`、不编 pay_method**：所以「二维码能跳进 payment_entry」不等于「该记录是支付宝」，只证明前端新版 + 后端有该接口。诊断支付方式必须看 DB 行 / `core_data_mod_log` scene，不能看二维码能否跳转。
2. **「切换支付方式」的正确语义是先作废所有旧待支付单、再建新单**，作废过滤**不能按 pay_method 自筛**，否则跨方式切换会留下残单、出现双 `valid=1`。统一入口 `InvalidatePendingOrderPayments`。
3. **能跳转 ≠ 记录正确**：用户「能生成真实支付宝码」与「记录是微信支付」可同时成立（旧构建窗口 [5/31, 6/2)）。
4. **二次反馈先坐实「源码 vs 线上」再答**：源码读通 + `git show` 修复 commit + 现象窗口三方对齐，比「再 build 一次」更能定位线上滞后。
