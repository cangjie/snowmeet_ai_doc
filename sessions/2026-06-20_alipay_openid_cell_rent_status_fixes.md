# 2026-06-20 支付身份/订单详情/列表 多个修复：alipay open_id 落库 + 代付 cell + choose_identity:direct + 去支付按钮 + 未支付/未开始区分 + 退租日期回退

会话起始 start-work（doc 仓 `ad9ec49`，已最新）。本场是一连串用户报的具体 bug/需求，全部围绕支付身份验证 + 租赁订单详情/列表。改动跨 `SnowmeetApi`（4 文件）+ `snowmeet_wechat_mini`（2 页），**代码仓本地未提交、由用户按部署节奏处理**；本次 end-work 仅提交 doc 仓。所有后端改动都要 `dotnet publish` 重新部署才生效。

排查口径：本机 Intel Mac，`export ODBCSYSINI=/usr/local/Cellar/unixodbc/2.3.4/etc` + Driver 13 + `config.sqlServer` 直连生产只读核查，多次用真实数据复现/验证。

## 1. 支付宝支付成功后 open_id 未写入 order_payment.open_id

用户报：支付宝支付成功后，支付宝的 open_id 没写进 `order_payment.open_id`。

### 1.1 根因（OpenID 模式 notify 字段 = buyer_open_id）

- 支付宝下单走 **OpenID 模式**：[`AlipayPayByOrderPayment`](../SnowmeetApi/Controllers/OrderController.cs#L1913) 用 `model.BuyerOpenId = buyerId`（`buyerId = mini_session.alipay_openid`，2026-06-06 起「只提交 open_id」）。这个 open_id 落进了 `payment.ali_buyer_id`，`payment.open_id` 从头到尾没人赋值。
- 成功回调 [`AliController.CallBack`](../SnowmeetApi/Controllers/Order/AliController.cs#L592)：`ParseCallBack` 只解析 `buyer_id`（无 `case "open_id"`/`buyer_open_id`）。OpenID 模式 notify **回的是 `buyer_open_id`、`buyer_id` 为空** → `callback.buyerId` 解出空串 → 614 行 `payment.ali_buyer_id = callback.buyerId` 用空串覆盖、`open_id` 仍空 → **用户看到的现象**。
- 连带：640 行 `!string.IsNullOrEmpty(callback.buyerId)` 为假 → 游客支付宝单的 `_materializeAlipayMemberOnPaid` 被跳过、会员没兜底建。

### 1.2 用户提供真实 notify 一锤定音

用户贴回一条真实回调文本（订单 `WT_ZL_260619_00002_ZF_01`）：含 `buyer_open_id=040P5...`、`merchant_app_id=2021006157624571`、**无 `buyer_id`**。python 复跑 ParseCallBack 的 split 逻辑确认：`buyerId=''`、`buyerOpenId='040P5...'`、`payment.open_id` 将被写入、物化判定通过。

### 1.3 修复（[`AliController.cs`](../SnowmeetApi/Controllers/Order/AliController.cs)，4 处）

- `AliCallBackModel` 加 `buyerOpenId` 字段
- `ParseCallBack` 加 `case "buyer_open_id"`
- 成功回调：`payerOpenId = buyerOpenId 优先，否则 buyer_id`；非空时写 `payment.open_id = payerOpenId` + `open_id_type = "alipay_openid"` + `ali_buyer_id = payerOpenId`（不再用空 buyer_id 覆盖）
- 会员物化判定/入参从 `callback.buyerId` 改 `payerOpenId`（`_materializeAlipayMemberOnPaid` 内部按 MSA `alipay_payerid` 匹配，存的就是 open_id，传 open_id 能命中已有会员）
- 兼容旧商户号（user_id 模式回 buyer_id）：`payerOpenId` 回退到 buyer_id

## 2. 代付(is_proxy_pay=1) 落库代付人手机号到 order_payment.cell

用户：不论微信/支付宝，`order_payment.is_proxy_pay=1` 时要更新 cell 字段；查不到代付人手机号则提示验证手机号。

### 2.1 澄清（两点关键，用户拍板）

- **`order_payment.cell` 列在生产库已存在**（实查：`varchar(16)` nullable Chinese_PRC_CI_AS），C# DTO `OrderPayment` 漏了这属性 → EF 没映射、写不进去。**补 DTO 即可，不改表**。
- **手机号验证保持软提示可跳过**（现状不变）。现有前端在 `scannerHasCell=false` 时已弹手机号授权，代付按钮也走这条软授权链 → **前端无需改**。

### 2.2 实现（plan 流程，纯后端）

plan 文件 `~/.claude/plans/order-payment-is-proxy-pay-1-cell-hashed-reddy.md`（不入 doc 仓）。

- [`Models/Order/OrderPayment.cs`](../SnowmeetApi/Models/Order/OrderPayment.cs)：加 `public string? cell { get; set; } = null;`（对齐已存在 DB 列；列已存在 → EF SELECT 它安全）
- [`PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs)：新增 `_resolveProxyPayerCell(scannerMemberId, sessionKey)`（微信取会员档案 `Member.cell`；支付宝会员推迟创建，取 `mini_session.cell` 兜底）；`_applyChoice` 在 `choice=="proxy"` 时 `op.cell = proxyCell`（拿不到留空、不阻断）。`is_proxy_pay=true` 全局仅此一处写，故唯一落点。

## 3. 「当前状态非 choose_identity: direct」（paymentId 42618）

用户报支付宝扫码报这个错。

### 3.1 根因（扫码人 == 订单本人，状态合法翻 direct）

DB 核查：订单 71761 归属会员 **15506**；扫码的支付宝账号（最近 session `alipay_openid=040P5...`、`cell=18601197897`）也解析到会员 **15506** → 扫码人就是订单本人。

时序：① 页面初次 CheckPayerIdentity 时 openid 还没关联到 15506 → 状态 `choose_identity`（前端弹自己付/替人代付卡）；② 用户授权手机号，`submit_phone` 把 openid 绑到 15506（因手机号属 15506）；③ 再点 `choose` → `_resolveStatus` 现在 scanner=15506==owner → 返 `direct` → [`_applyChoice` 旧代码](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs#L538) 报 `unexpected_state`。真实顾客第一次用支付宝付自己的单也会撞上，非纯测试。

### 3.2 修复（[`_applyChoice`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs#L538)）

状态翻成 `direct`/`direct_to_scanner` 时不再报错，强制 `choice="self"` 按直付走完（`op.member_id=扫码方`、`is_proxy_pay=false`、返 `direct` 让前端自动发起支付）。代付无意义（你就是本人）。

## 4. 订单详情页加「去支付」按钮（仅租赁）

用户：订单列表打开未支付订单，详情页应显示「去支付」按钮，点击跳开单流程里那个支付页。

走 brainstorming 流程，澄清：仅租赁详情页 `rent_order_detail`（用户选）。纯前端。

- 目标页就是通用结算页 `pages/payment/settle/index?orderId=`，复用（与「追加租赁」line 1214 同款 navigateTo）。
- [`rent_order_detail.js`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js)：`renderOrder` 派生 `order.showGoPay`（`orderStatus ∈ {待生成,待支付,部分支付}` 且应付>0）+ `order.payableAmountStr`；新增 `onGoPay()` → navigateTo settle。
- [`.wxml`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml)：支付信息卡摘要格下方加整宽主色按钮「去支付 ¥应付」（`wx:if showGoPay`）。
- [`.wxss`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss)：`.go-pay-btn`（#006495）。
- 闭环：付完后 settle 现有 `onPaid` 已 `redirectTo` 回 rent_order_detail → 重新 getData → 按钮自动消失。无需改 settle。

## 5. 列表区分「未支付」与「未开始」

用户：租赁订单列表「未支付」「未开始」没区分开，应该分开。澄清定义：**未支付 = 顾客还没付；未开始 = 已付但起租时间未到（计费未开始）**。要加「未支付」筛选项。

口径（列表 chip / 筛选 / 已做的去支付按钮三处统一）：未支付 = `orderStatus ∈ {待生成,待支付,部分支付}` 且应付>0（排除挂账/已付/关闭/免费单）。

- 后端 [`OrderController.cs GetOrdersByStaff`](../SnowmeetApi/Controllers/OrderController.cs#L286) 状态过滤：`未支付` → 返回未付清单；其它 rentStatus（未开始/租赁中…）→ 加「已付清」前置（未付清的不再混进来）；`临时订单` 不变。
- 前端 [`new_rent_list`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js)：chip = `未付 ? "未支付" : rentStatus`（`_statusClass` 加 `未支付→unpaid`）；筛选栏加「未支付」radio；`.status-chip--unpaid` 橙色样式。
- 效果：之前都显示「未开始」的单，未付清的变橙色「未支付」；筛选「未支付」只出未付清单、「未开始」只出已付未起租单。

## 6. 租赁物全部归还后租赁商品无退租日期、订单状态错（order 71762）

用户：某租赁商品的租赁物全部归还后，该商品没有退租日期，导致订单状态都不对。

### 6.1 根因（生命周期绑在计费明细上，免除唯一明细丢失起止）

systematic debugging + DB 实查时间线（`core_data_mod_log`）：
- 15:53 发放（RentItemLog 已发放）→ 15:54 归还（settled 0→1）→ **15:55 在「修改租金明细」把唯一一条 rental_detail valid 1→0**（免除/清零）。
- `Rental.realStartDate`/`realEndDate`（和 rentStatus）**只从有效 `rental_detail`（按天租金）推导**，不从租赁物领还事件（RentItemLog）。唯一明细 valid=0 后 `availabelRentDetails` 空 → 两者都成 null → 状态机 `realStartDate==null` 判「未开始」、无退租日期。
- 这就是 6-15「免除」特性当时记的副作用的完整后果。

### 6.2 修复（Option A 治本，用户选，[`Rental.cs`](../SnowmeetApi/Models/Rent/Rental.cs#L47)）

- `realStartDate`/`realEndDate` 在无有效 rental_detail 时**回退到租赁物领还事件**：起租=最早 `rentItem.pickDate`（已发放日志）；退租（settled=1 时）=最晚 `returnDate`（已归还日志）。正常单（有有效明细）行为不变。
- 配套 [`OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs#L187)：列表查询 `GetOrdersByStaff` 给租赁物 include 上 `logs`（两处分支：租赁 branch line 187 + default branch line 249），否则列表里拿不到领还事件、回退取不到值。详情页 `GetRental` 本就 include logs。
- 模拟验证（71762 真实数据）：有效明细 0 → 触发回退 → 起租=退租=2026-06-19、`settledCount 1/1` → **状态 = 全部归还**。

## 关键改动文件

| 仓库 | 文件 | 改动 |
|---|---|---|
| SnowmeetApi | [`Controllers/Order/AliController.cs`](../SnowmeetApi/Controllers/Order/AliController.cs) | ParseCallBack 加 `buyer_open_id`；成功回调写 open_id/open_id_type/ali_buyer_id + 物化用 payerOpenId |
| SnowmeetApi | [`Models/Order/OrderPayment.cs`](../SnowmeetApi/Models/Order/OrderPayment.cs) | DTO 补 `cell` 属性（对齐已存在 DB 列） |
| SnowmeetApi | [`Controllers/Order/PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) | `_resolveProxyPayerCell` + `_applyChoice` 代付写 cell + 接受 direct/direct_to_scanner 按 self 直付 |
| SnowmeetApi | [`Controllers/OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) | GetOrdersByStaff 加「未支付」过滤 + 其它 rentStatus 排除未付；rentals.rentItems include logs（两 branch） |
| SnowmeetApi | [`Models/Rent/Rental.cs`](../SnowmeetApi/Models/Rent/Rental.cs) | realStartDate/realEndDate 无有效明细时回退 RentItemLog pickDate/returnDate |
| snowmeet_wechat_mini | [`pages/admin/rent/rent_order_detail/{js,wxml,wxss}`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/) | 去支付按钮（showGoPay/payableAmountStr/onGoPay + 样式） |
| snowmeet_wechat_mini | [`pages/admin/rent/new_rent_list/{js,wxml,wxss}`](../snowmeet_wechat_mini/pages/admin/rent/) | 未支付 chip + 筛选项 + unpaid 样式 |

全部 `dotnet build` 0 error / `node --check` 通过。

## 学到的小知识

1. **支付宝 OpenID 模式 notify 字段是 `buyer_open_id`、`buyer_id` 为空**：`alipay.trade.create` 用 `BuyerOpenId` 创建（OpenID 模式商户）→ 异步 notify 回 `buyer_open_id`，不回 `buyer_id`。任何解析 alipay 回调取付款方标识都要认 `buyer_open_id`。真实样本：`buyer_open_id=040P5LaEkN0J...`、`merchant_app_id=2021006157624571`、无 buyer_id。
2. **`order_payment` 表早有 `cell` 列（varchar 16），DTO 此前漏映射**：DB schema 比 C# 模型新的又一例（同 punch_card 系列）。补 DTO 前先连库 `INFORMATION_SCHEMA.COLUMNS` 确认列真存在 + 类型，列已存在则 EF SELECT 安全（不像 customer_open_date 要先 ALTER）。
3. **choose_identity 会合法翻成 direct**：扫码人授权的手机号若属于订单本人，`submit_phone` 把 openid 绑到该会员后，scanner 变 == owner → `_resolveStatus` 返 direct。`_applyChoice` 必须容忍 direct/direct_to_scanner（按 self 直付），不能报 unexpected_state 把人卡死。
4. **租赁生命周期（起租/退租/状态）原本绑在 rental_detail 计费明细上、与领还事件脱钩**：`realStartDate`/`realEndDate` 取 valid=1 明细首/末日；免除唯一明细 → 双 null → 状态退回「未开始」。治本是回退到 `RentItemLog` 的 pickDate/returnDate（领还事件才是生命周期真源）。
5. **改 `realStartDate`/`realEndDate` 计算属性要同步给列表查询补 include**：列表 `GetOrdersByStaff` 原本只 include 了 `rentItems` + `category`、没 include `logs`，所以回退逻辑在列表上下文取不到 pickDate/returnDate（它们从 `logs` 派生）。详情页 GetRental 本就 include logs。
6. **Order.cs:1102 endDate 拷的是 `rental.end_date` 列（恒 null，SetRentItemStatus 从不写）而非 `realEndDate`**：既存 oddity。本次修复后最终状态由 `settledCount` 决定（已正确为「全部归还」）、详情页退租日期用 `rental.realEndDate`（已修），故不影响本次问题；是否把 1102 对齐成 realEndDate 留给用户定。
7. **systematic debugging「DB 直查 + 真实样本复现」最快定根因**：open_id（让用户贴真 notify）、direct（DB 查 order/session 的 member_id）、退租日期（core_data_mod_log 时间线 + 模拟计算属性）三处都靠真实数据一击命中，不靠猜。
