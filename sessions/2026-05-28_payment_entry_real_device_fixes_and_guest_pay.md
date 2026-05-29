# 2026-05-28 真机测试根因排查 + 决策架构重构 + 非会员软授权支付

按主题/时间线整理。本场会话从 5-27 留下的「待真机端到端测试」入口启动，用户在真机上跑 payment_entry 发现一连串 bug，反推出多处架构和守卫问题。三条主线：① 真机暴露的 wepay 调不起 / 订单归属转移失效根因排查；② 用户重申"订单归属应在支付成功后设置"原则后的决策架构重构；③ 非会员/未绑手机号软授权支付流程实施。改动横跨 SnowmeetApi 后端 + snowmeet_wechat_mini 前端。

## 1. 真机 bug 1：「点身份按钮后 wx.requestPayment 调不起」

### 1.1 现象与初判

- 用户用其它微信账号扫顾客二维码，进 payment_entry 看到「选择支付身份」卡片
- 点「正常支付（订单转归我）」→ 后端 `_applyChoice` 写 `op.member_id=扫码方` + `is_proxy_pay=false`
- 前端 `onIdentityRefreshed` 收到的 `result.status` 不是 `'direct'` → 不自动调起支付
- 看似前端逻辑没问题，根因在后端

### 1.2 根因（first cut，后被否定）

`_resolveStatus` 计算 status 时只看 `order.member_id`，没看 `op.member_id`。但 `_applyChoice` 按"决策时机迁到 notify"设计**只改 `op.member_id`，不动 `order.member_id`** → 重算 status 仍是 `choose_identity` → 前端循环。

**初步修复**：`_resolveStatus` Step 4 开头加 `if (op.member_id != null) status='direct'`。本地 `dotnet build` 通过。

### 1.3 第二个根因：客户端真的调不起

用户继续追问"现在是小程序客户端，没有拉起微信支付，你再看看？"。重新审查 `Order/WechatPayByOrderPayment`：

- TenpayController.TenpayRequest line 119-122 用 `payment.open_id` 作为 wepay JSAPI 的 payer openid
- `_applyChoice` 只写 `op.member_id`，**不动 `op.open_id`**
- WechatPayByOrderPayment 现有两个分支：
  - 「首次」(`payment.member_id == null`) — 不触发，身份验证已 pre-set member_id
  - 「换人」(`payment.member_id != member.id`) — 不触发，扫码方就是已 pre-set 的 member_id
- → `payment.open_id` 保持订单原会员的 openid → TenpayRequest 用错 openid 申请 prepay → wx.requestPayment 因 openid 不匹配**弹不出窗**

**修复**：[`OrderController.cs:1592`](../SnowmeetApi/Controllers/OrderController.cs#L1592) 加第 3 个分支：

```csharp
if (payment.member_id == member.id
    && member.wechatMiniOpenId != null
    && (payment.open_id == null
        || payment.open_id.Trim() != member.wechatMiniOpenId.Trim()))
{
    payment.open_id = member.wechatMiniOpenId.Trim();
    payment.out_trade_no = outTradeNo.Trim();
    payment.prepay_id = null;
    payment.timestamp = null;
    payment.nonce = null;
    payment.sign = null;
    payment.update_date = DateTime.Now;
    _db.orderPayment.Entry(payment).State = EntityState.Modified;
    await _db.SaveChangesAsync();
}
```

这条分支专门处理「身份验证 pre-set member_id 但 open_id 没改」的中间态。

## 2. 用户重申原则：「订单归属应在支付成功后设置」

### 2.1 用户原话

> 订单归属问题，应该在支付成功后设置，支付不成功的话，订单归属不变。

这话推翻了 1.2 节的初步修复 — 「`op.member_id != null → status='direct'`」实际上把"付款方意图"当成了"订单归属已决定"，违反原则。

### 2.2 漏洞场景验证

- 扫码方 A 点「正常支付」→ `op.member_id = A`
- A 关闭/取消微信支付
- A 刷新页面 → `_resolveStatus` 命中我加的兜底分支 → 返回 `direct` → wxml 跳过选择卡片直接显示「敬请支付」
- A 无法改主意（点不到「替人代付」），且 `ConfirmPayIdentity` 顶部幂等检查（`if op0.member_id != null`）又拦掉重写

→ **必须让"意图"不持久化为"已决策"**。

### 2.3 解耦重构

[`PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) 三处改动：

1. **`_resolveStatus` 不再依赖 `op.member_id`**：只看 `order.member_id` + `result.scannerMemberId`。Step 4 决策树和原版一致（顺序：phone_required / direct_to_scanner / direct / choose_identity）
2. **删除 `ConfirmPayIdentity` 顶部幂等检查**：原 `if (op0.member_id != null) { return existing }` 块整段删除。允许扫码方改主意（覆盖写 `op.member_id` / `is_proxy_pay`）
3. **`_applyChoice` / `_applyConfirmDirect` 末尾强制 `status='direct'`**：本次响应触发 `pay()`，但不污染 `_resolveStatus`（刷新后仍按 `order.member_id` 重算）

| 概念 | 写入位置 | 持久性 | 是否影响 status 决策 |
|------|---------|-------|--------------------|
| 付款方意图 (`op.member_id` / `is_proxy_pay`) | `_applyChoice` / `_applyConfirmDirect` 落库 | DB 持久 | ❌ 不进 `_resolveStatus` |
| 本次点击响应 `status='direct'` | action handler 强制返回 | 仅本次 HTTP 响应 | ✅ 触发前端 auto-pay |
| 订单归属 (`Order.member_id`) | `DealSuccessPaidOrder` (notify) | DB 持久 | ✅ 决定下次 `_resolveStatus` |

## 3. 真机 bug 2：「订单转归我」对已有归属订单失效

### 3.1 现象

用户报告：「我支付的时候点的是订单归我，但支付完了订单的 member_id 还是原来手机号 13501177897 那个会员」。

### 3.2 根因

[`DealSuccessPaidOrder` 同步守卫](../SnowmeetApi/Controllers/OrderController.cs#L1787)：

```csharp
if (paidOp.is_proxy_pay == false && paidOp.member_id != null && order.member_id == null)
//                                                              ↑ 多余守卫
{
    order.member_id = paidOp.member_id;
}
```

`order.member_id == null` 条件让**已有归属订单**永远无法被「正常支付」转走。但按钮 UI 写的就是「订单转归我」— 设计与实现矛盾。

### 3.3 修复

去掉 `order.member_id == null` 守卫。代付仍由 `is_proxy_pay==true` 拦截，不会误转：

| 场景 | `is_proxy_pay` | `op.member_id` | `order.member_id` 原值 | 修后行为 |
|------|---------------|----------------|----------------------|---------|
| 正常支付（归我），原有归属 | false | 扫码方 C | 苍杰 | ✅ 同步为 C |
| 正常支付（归我），无归属 | false | 扫码方 C | null | ✅ 同步为 C |
| 替人代付 | true | C | 苍杰 | ✅ 不动 |
| 自己付自己单 | false/null | scanner | scanner | 赋同值（无影响） |

## 4. 客户端守卫：已支付订单不应再显示身份选择卡片

### 4.1 现象

用户截图：订单已是「支付成功」（已支付 ¥0.03，总计 ¥0.00），但页面同时显示「选择支付身份」卡片 + 两个按钮 + 底部「支付成功」三件套同框。

### 4.2 根因

可能数据层有脏数据 — 订单已支付但残留 `op.status='待支付'` 记录（多次 prepay 重试产生）。但 UI 应该做防御性兜底。

### 4.3 修复

[`payment_entry.wxml`](../snowmeet_wechat_mini/pages/order/payment_entry.wxml)：

- 「支付成功」消息提前到所有支付 UI 之前显示
- 「选择支付身份」卡片加 `order.orderStatus != '支付成功'` 守卫
- 「敬请支付」按钮同样守卫

## 5. 非会员/未绑手机号软授权支付流程（大改）

### 5.1 用户需求

- pages/order/payment_entry 获取会员信息失败后报错，需修复
- 非会员也应该可以支付，但 UI 要有提示
- 点支付按钮时，未授权手机号则**弹提示**，顾客有权**授权或跳过**，不论选哪个**都可以继续支付**

### 5.2 实施方案（Plan Mode 设计 + 用户确认）

UI 形态：**全屏遮罩 + 底部滑入卡片**，含「授权手机号」+ 「跳过，直接支付」两个按钮。授权按钮用 WeChat `<button open-type="getPhoneNumber">`（小程序限制 getPhoneNumber 只能由 button 直接触发）。

### 5.3 后端改动

1. **[`OrderController.GetOrderFromPaymentByCustomer`](../SnowmeetApi/Controllers/OrderController.cs#L2117)** — 加 `member == null` 兜底
   - 游客查待支付订单不再 NRE
   - 已支付订单仍仅对相关会员开放（`member == null` 时拒绝）

2. **[`PaymentIdentityController._resolveStatus`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs)** — 删 `phone_required` 硬阻断分支
   - `scannerHasCell` 字段仍写入响应（前端用于判断是否弹软授权）
   - 决策树继续往下：`order.member_id==null → direct_to_scanner` / `scannerMemberId==order.member_id → direct` / 否则 `choose_identity`
   - 游客（`MemberLogin` 自动创建的最小 stub）也能正常进入支付流程

### 5.4 前端改动

1. **[`utils/util.js`](../snowmeet_wechat_mini/utils/util.js#L115)** — `performWebRequest` 非 200 加 `reject(res.statusCode)`
   - 修挂起 Promise bug：原 `if (statusCode != 200) { toast; return; }` 不 reject 导致 Promise 永远 pending
   - 这是全局 bug，影响所有 `wx.request` 调用，不止 payment_entry

2. **[`pages/order/payment_entry.js`](../snowmeet_wechat_mini/pages/order/payment_entry.js)** — `pay()` 改造
   - 新增 `showPhonePrompt: false` data
   - `pay()` 检查 `identity.scannerHasCell`：true → 直接 `_doWepay()`；false → `setData({ showPhonePrompt: true })`
   - 拆出 `_doWepay()`：原 `pay()` 里 `WechatPayByOrderPayment` + `wx.requestPayment` 的逻辑
   - 新增 `onAuthorizePhone(e)`：getPhoneNumber 回调 → 复用 `data.confirmPayIdentityPromise({ action:'submit_phone', encData, iv })` → 成功后 `_doWepay()`；取消/失败也兜底 `_doWepay()`
   - 新增 `onSkipPhone()`：直接 `_doWepay()`

3. **[`pages/order/payment_entry.wxml`](../snowmeet_wechat_mini/pages/order/payment_entry.wxml)** — 加全屏遮罩 + 底部滑入卡片
   ```html
   <view wx:if="{{showPhonePrompt}}" class="phone-prompt-overlay" bindtap="onSkipPhone">
     <view class="phone-prompt-card" catchtap="">
       <view class="phone-prompt-title">建议授权手机号</view>
       <view class="phone-prompt-hint">便于查询订单与售后服务,您也可以跳过直接支付</view>
       <view class="phone-prompt-btn-row">
         <button class="phone-prompt-btn-primary" open-type="getPhoneNumber" bindgetphonenumber="onAuthorizePhone">授权手机号</button>
         <button class="phone-prompt-btn-secondary" bindtap="onSkipPhone">跳过,直接支付</button>
       </view>
     </view>
   </view>
   ```
   - `bindtap="onSkipPhone"` 在遮罩上 — 点遮罩视作跳过
   - `catchtap=""` 在卡片上 — 拦截冒泡，防止误关

4. **[`pages/order/payment_entry.wxss`](../snowmeet_wechat_mini/pages/order/payment_entry.wxss)** — 加 `.phone-prompt-*` 样式 + 淡入/滑入动画

5. **[`components/pay-identity-confirm/index.wxml`](../snowmeet_wechat_mini/components/pay-identity-confirm/index.wxml)** — 删 `phone_required` 渲染分支
   - 组件保留 `direct_to_scanner` / `choose_identity` / `error` 三态
   - phone_required 状态后端虽仍可能返回（其它历史路径），但前端不再用组件渲染（payment_entry 直接根据 scannerHasCell 弹软提示）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) | `_resolveStatus` 删 phone_required 硬阻断 + 不再用 op.member_id 判 direct；删 ConfirmPayIdentity 幂等拦截；`_applyChoice`/`_applyConfirmDirect` 末尾强制 status='direct' |
| [`SnowmeetApi/Controllers/OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) | `WechatPayByOrderPayment` 加 open_id 不匹配补写分支；`DealSuccessPaidOrder` 删 `order.member_id == null` 守卫；`GetOrderFromPaymentByCustomer` 加 member==null 兜底 |
| [`snowmeet_wechat_mini/utils/util.js`](../snowmeet_wechat_mini/utils/util.js) | `performWebRequest` 非 200 加 `reject(res.statusCode)` |
| [`snowmeet_wechat_mini/pages/order/payment_entry.js`](../snowmeet_wechat_mini/pages/order/payment_entry.js) | 新增 showPhonePrompt + 拆出 _doWepay + onAuthorizePhone + onSkipPhone |
| [`snowmeet_wechat_mini/pages/order/payment_entry.wxml`](../snowmeet_wechat_mini/pages/order/payment_entry.wxml) | 加 orderStatus='支付成功' 守卫；加全屏遮罩 + 底部卡片软授权弹窗 |
| [`snowmeet_wechat_mini/pages/order/payment_entry.wxss`](../snowmeet_wechat_mini/pages/order/payment_entry.wxss) | 加 .phone-prompt-* 样式 + 动画 |
| [`snowmeet_wechat_mini/components/pay-identity-confirm/index.wxml`](../snowmeet_wechat_mini/components/pay-identity-confirm/index.wxml) | 删 phone_required 分支，wx:if 起首位置改到 direct_to_scanner |

## 学到的小知识

1. **WeChat JSAPI 支付 openid 必须与 prepay 申请 openid 完全一致**：`TenpayRequest` 用 `payment.open_id` 申请 prepay，回前端的 `prepay_id` 只能由该 openid 的 `wx.requestPayment` 调起。任何中间态改了 member_id 但没改 open_id，结果就是支付窗弹不出，且没有明显错误提示

2. **`getPhoneNumber` 不能由 JS 程序触发**：必须由 `<button open-type="getPhoneNumber">` 用户直接点击。意味着「单一支付按钮 + 中途引导」这种 UX 设计是行不通的，必须把授权按钮独立出来（或弹窗里）让用户点击

3. **`MemberLogin` 对游客自动建最小 stub**：[`MemberLogin` lines 206-235](../SnowmeetApi/Controllers/MiniAppHelperController.cs)：openid 没绑过会员时，自动 `_db.member.AddAsync(new Member())` + 绑一条 wechat_mini_openid MSA，sessionKey/MiniSession 仍正常写入。意味着前端 `app.globalData.member` 可能 undefined，但 `sessionKey` 一定有效，后端反查 mini_session.member_id 总能拿到（最小 stub）会员

4. **`performWebRequest` 非 200 不 reject 的隐蔽 bug**：[`util.js:115`](../snowmeet_wechat_mini/utils/util.js#L115) 原代码 toast 后 return（不 reject）。Promise 会**永久 pending**，调用方既不会 then 也不会 catch。任何接口偶发 500/401 时页面就会停在加载中。今天顺手修了

5. **决策时机与意图持久性的解耦**：
   - 「付款方意图」（`op.member_id`/`is_proxy_pay`）落 DB 持久 — 给 notify 用
   - 「订单归属」（`Order.member_id`）也落 DB 持久 — 但只在 notify 成功时同步
   - 「本次响应触发 pay()」只在当次 HTTP 响应里 force `status='direct'` — 不污染后续 `_resolveStatus`
   - 三者分离让用户改主意成本最低（刷新就重新决策），且失败重试不会破坏归属

6. **「正常支付（订单转归我）」对已有归属订单的转移是真转移**：`DealSuccessPaidOrder` 同步 `order.member_id = op.member_id`（去掉 `order.member_id == null` 守卫后）。`UpdateOrder` 内的 `Util.GetUpdateDifferenceLog` 会自动产 `core_data_mod_log` 记录 scene=`支付成功`，原值/新值留痕

## 待真机端到端验证（接续 5-27 未完）

- 改主意场景：选「正常支付」→ 取消 → 刷新 → 选「替人代付」→ 支付，校验 `OrderPayment.is_proxy_pay` 写为 true、`Order.member_id` 不变
- open_id 切换场景：A 选「正常支付」未付款 → C 扫码 → C 选「正常支付」→ `WechatPayByOrderPayment` 触发「换人」分支 → wepay 用 C 的 openid 申请 prepay
- 「订单转归我」对已有归属订单：苍杰建的单 + C 扫码选「正常支付」付款成功 → `Order.member_id == C`，`core_data_mod_log` 留痕
- 游客授权手机号路径：新顾客扫码 → 点「敬请支付」→ 弹软提示 → 「授权手机号」→ `_submitPhone` 解码 → `member_social_account` 新增 `type='cell' && valid=1` → 自动调起支付
- 游客跳过路径：新顾客扫码 → 点「敬请支付」→ 弹软提示 → 「跳过」→ 直接调起支付，不写 cell；付款后 `Order.member_id` 指向游客 stub member.id
- 游客取消授权路径：弹软提示 → 「授权」→ 微信弹窗取消 → 兜底当跳过，继续调起支付
