# 2026-05-27 payment_entry 身份按钮自动调起微信支付 + pay() 3 bug 修复

接续 2026-05-14 的「支付前身份验证 A+B 切片」工作。本次承担最后一公里：把 `pay-identity-confirm` 的 4 个身份按钮和 `wx.requestPayment` 串成一次点击完成。改动落在 `snowmeet_wechat_mini/pages/order/payment_entry.js` 唯一文件，后端零改动。plan：`/Users/cangjie/.claude/plans/pages-order-payment-entry-hidden-kurzweil.md`。

## 1. 症状澄清

### 1.1 用户原话

> "pages/order/payment_entry 这个页面，需要把支付调通，前后端都需要修改。"

四选一澄清后定位为：

> "就是点击「正常支付」或「替人代付」按钮，小程序并未请求支付接口。微信支付接口看一下服务器端的 OrderPaymentController。"

### 1.2 实际链路（5-14 mvp 写完未真机测过）

1. 顾客扫店员侧支付二维码进 `payment_entry`，`paymentId` 入参
2. `onShow` → `getOrderFromPaymentByCustomer` 拉单 → `_refreshIdentity` 调 `PaymentIdentity/CheckPayerIdentity` 拉 identity 状态
3. 后端 `_resolveStatus` 5 状态决策树返：`phone_required` / `direct_to_scanner` / `choose_identity` / `direct` / `error`
4. 前端 wxml 按 status 渲染：非 direct → 显示 `pay-identity-confirm` 卡（4 种按钮各一态）；direct → 隐藏卡 + 显示「敬请支付」按钮
5. 用户在 choose_identity 点「正常支付」/「替人代付」→ 组件调 `ConfirmPayIdentity { action: 'choose', choice: 'self'|'proxy' }` → 后端写 `[order].member_id` / `order_payment.member_id` / `order_payment.is_proxy_pay` → 返新 status (此时是 direct)
6. 组件 `triggerEvent('refreshed', { result })` → 父页面 `onIdentityRefreshed` 仅 `setData({ identity: result })`
7. **此时用户必须再点一次「敬请支付」按钮**才会调 `pay()` → `Order/WechatPayByOrderPayment/{paymentId}` 拿支付参数 → `wx.requestPayment`

→ 对扫码顾客是糟糕体验。预期：4 个身份按钮按完**自动调起微信支付**。

## 2. 探索 + 排查

### 2.1 三个 Explore agent 并行覆盖前/后/集成

报告整体准确，但**第二个 agent 漏看远端分支误报关键事实**：

> "ai 分支中不存在 CheckPayerIdentity / ConfirmPayIdentity 方法"

直接核实远端：

```bash
git -C SnowmeetApi ls-tree origin/ai Controllers/Order/
# → 100644 blob 80616ed7... PaymentIdentityController.cs  ✓ 存在
git -C SnowmeetApi grep -l "wechat_unverified" origin/ai -- 'Models/*'
# → origin/ai:Models/Order/Order.cs  ✓ 存在
git -C SnowmeetApi grep -l "is_proxy_pay" origin/ai -- 'Models/*'
# → origin/ai:Models/Order/OrderPayment.cs  ✓ 存在
```

**根因**：本地 SnowmeetApi ai 分支落后 origin/ai 4 commit：

```
8fae458 bug                                                # +38/-20 行 PaymentIdentityController bug fix
1e4250b Merge branch 'ai'
2750e00 pay test                                           # +551 行 PaymentIdentityController + 4 模型字段
de6b46b rent report
```

zhx 在另一台机 5-14 提交 + push 的，本机未 pull → working tree 看不到。Explore agent 默认只看 working tree、不会主动 `git fetch` / 看远端分支。

### 2.2 教训：agent 看到的 ≠ 仓库的真实状态

多人 / 多机协作下，关键决策不能完全信任 agent 的"代码不存在"结论。**必须自己 `git ls-tree origin/<branch>` / `git show origin/<branch>:path` 核实**。差点让我重新规划实现 590 行已存在的代码。

### 2.3 部署侧已就位

用户口径："生产/staging 已部署 ai 后端"——即 zhx push 后的 ai 代码已经 deploy 到 mini.snowmeet.top，前后端协议已对齐，本次只需改前端。

## 3. 方案选型

### 3.1 三方案对比

| 方案 | 描述 | 改动量 | 选 / 弃 |
|---|---|---|---|
| **A** | 前端串联：`onIdentityRefreshed` 检测 status==direct 后自动重拉单 + 调 `pay()` | 前端 ~30 行 | ✅ 选 |
| B | 后端 `ConfirmPayIdentity` 改为 status==direct 时同步调 TenpayRequest 一并返支付参数 | 后端 100+ 行 | ❌ 耦合身份/支付职责 |
| C | 新写 `Order/OrderPayment/PayWithIdentity` 端到端 endpoint | 后端 200+ 行 | ❌ 本期非必要 |

### 3.2 选 A 理由

- 改动最小（单文件 ~30 行）
- 语义清晰（前端编排、后端各 controller 单一职责）
- 对后端零侵入，灰度回退只需 `git revert pages/order/payment_entry.js`
- 减少 HTTP 一次的优化（方案 B 优势）在扫码场景下用户感知不到，不值得耦合

### 3.3 用户提示「看 OrderPaymentController」的澄清

用户原话提到 OrderPaymentController，实际：

- 当前小程序调的 `Order/WechatPayByOrderPayment`（`OrderController.cs:1504` 新接口）是 ai 分支 zhx 的新版，用新 `Order` 表，与 PaymentIdentityController 写的同一张表对齐 ✓
- `OrderPaymentController.Pay`（`core/OrderPayment/Pay/{paymentId}` 旧接口）写老的 `OrderOnline` 表，**与 PaymentIdentity 写的新 Order 表脱节**

所以 **不要切回 OrderPaymentController.Pay**，继续用 OrderController.WechatPayByOrderPayment。

## 4. 前端改动（`payment_entry.js` 唯一文件）

### 4.1 `onIdentityRefreshed` 自动串联（L72-87）

```js
onIdentityRefreshed(e) {
  var that = this
  var result = e && e.detail && e.detail.result
  if (!result) return
  if (result.status === 'direct') {
    that.setData({ identity: result })
    // 重拉订单刷新 payment 引用，避免用旧 payment 的 member_id 发起支付时后端校验失败
    data.getOrderFromPaymentByCustomer(that.data.paymentId, app.globalData.sessionKey).then(function (order){
      that.renderData(order)
      that.pay()
    }).catch(function () {
      // 拉单失败不卡死：identity 已 direct，wxml 显示「敬请支付」让用户手动点重试
    })
    return
  }
  that.setData({ identity: result })
}
```

覆盖范围：4 个身份按钮（一键授权手机号 / 确认并继续 / 正常支付 / 替人代付）任何一个按完后 status 转 direct，都会自动调起 `wx.requestPayment`。

### 4.2 `pay()` 3 bug 修复（L160-204）

**Bug 1 — 缺 `!payment` 守卫**（plan risk 2）

拉单回来 `payment=null`（罕见但 op.status 可能已变）→ `payment.pay_method` crash。新增：

```js
if (!payment) {
  wx.showToast({ title: '支付状态已变更，请刷新', icon: 'none' })
  return
}
```

**Bug 2 — 「不可支付」分支漏 `return` + paying=true 卡死**

原代码：

```js
that.setData({paying: true})              // ← 提前置位
var payment = that.data.payment
if (payment.pay_method != '微信支付' || payment.status != '待支付'){
  wx.showToast({...})                     // ← 漏 return，paying 永不复位
}
var payUrl = ...                          // ← 继续执行后续逻辑
```

修复：把 `setData paying=true` 移到所有 guard 之后；「不可支付」分支补 `return`。

**Bug 3 — promise 内层 param shadow 外层变量**

原代码：

```js
var payment = that.data.payment           // 外层
...
util.performWebRequest(payUrl, null).then(function (payment){   // ← shadow
  wx.requestPayment({
    nonceStr: payment.nonce,              // 这里的 payment 是 WechatPay 返对象
    ...
    success: (res) => {
      data.getOrderFromPaymentByCustomer(payment.id, ...)   // ← 用 wx 返对象的 id
    }
  })
})
```

碰巧 OrderController.WechatPayByOrderPayment 返的就是 OrderPayment 对象，`payment.id` 等于 paymentId 才跑通。语义混乱难维护。修复：

- 内层 promise param 重命名 `payment → payParams`
- 拉单显式 `that.data.paymentId` 不用 `payment.id`

**清理**：删 L182-193 死代码注释块（旧版试图从 `order.payments[]` 找当前 payment 然后 `setData({payment: currentPayment})`，已被 `renderData(order)` 全量刷新替代）。

**网络失败处理**：外层 `performWebRequest` 补 `.catch` 复位 paying（应对 `Order/WechatPayByOrderPayment` 网络失败）；success 内拉单 catch 也复位 paying。

### 4.3 后端零改动

- `PaymentIdentityController` (origin/ai) 5 状态决策树 + 3 action 落库语义正确，不动
- `Order/WechatPayByOrderPayment` (OrderController.cs:1504 ai 分支) 已接 TenpayRequest 链路，不动
- `Order.wechat_unverified` / `OrderPayment.is_proxy_pay` / `MemberSocialAccount` 4 个 type 常量（origin/ai 已有）不动

## 5. 待真机端到端测试

按 plan §验证计划 5 个场景，至少 A/B/E 三个必跑。生产/staging 已部署 ai 后端，本次只需重编 mini 上真机。

| 场景 | 操作 | 期望 + DB 校验 |
|---|---|---|
| **A** choose_identity → self | A 账号下单 → B 真机扫码 → 点「正常支付」 | 自动调起微信支付密码框 → 支付成功；`[order].member_id=B / wechat_unverified=0` + `order_payment.member_id=B / is_proxy_pay=0 / status=支付成功` |
| **B** choose_identity → proxy | 同 A 但点「替人代付」+ 二次 modal 确认 | 自动调起 → 支付成功；`[order].member_id=A`（不变）+ `order_payment.member_id=B / is_proxy_pay=1` |
| **C** direct_to_scanner | 构造 `[order].member_id IS NULL` 订单 → B 扫码 → 点「确认并继续」 | 自动调起 → 支付成功；`[order].member_id=B` |
| **D** phone_required | 无手机号微信账号扫码 → 点「一键授权手机号」 | 授权后自动调起；`member_social_account` 多 cell 记录（开发者工具拿不到真号，**必须真机**） |
| **E** direct | 同一账号扫自己单 | 跳过 identity 卡、「敬请支付」可点 → 支付成功（**兜底验证旧路径未坏**） |

测试通过后：
- commit + push `snowmeet_wechat_mini` 的 payment_entry.js 改动
- CLAUDE.md 5-14 标记的"待真机端到端测试 A+B 切片"那条可正式划掉

如发现新问题（签名错 / 回调不通 / WebSocket 等），针对性排查。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/pages/order/payment_entry.js` | `onIdentityRefreshed` 自动串联 pay + `pay()` 3 bug 修（!payment 守卫 / 不可支付 return / payment→payParams 去 shadow + paymentId 语义化 / 删死代码 / catch 复位 paying） |

后端 0 文件改动。

## 学到的小知识

1. **Explore agent 看 working tree、不主动 fetch**：本机落后远端时，agent 会误报"代码不存在"。多机协作必须自己 `git ls-tree origin/<branch>` 核实，不能完全信任 agent 结论。本次第二个 agent 直接否认 PaymentIdentityController 存在，差点让我重新规划 590 行已存在的代码

2. **JS promise 内层 param shadow 外层变量是隐蔽 bug**：原 `.then(function (payment){...})` shadow 外层 `var payment = that.data.payment`，success 回调内 `payment.id` 实际是 wx 支付返对象 id（碰巧等于 paymentId 才跑通）。规范：内层 param 命名区分（如 `payParams`），重要的引用显式从 `that.data` 取

3. **"5-14 mvp 真机未测"的根因不是功能漏做、是 UX 设计缺陷**：身份按钮 + 支付按钮分两次点击对扫码顾客糟糕，这种缺陷只有跑真机端到端才暴露——纯 review / 单元测试看不出。任何「mvp」必须紧接真机端到端跑通才能称完成

4. **方案 A 单文件改动便于灰度回退**：`git revert pages/order/payment_entry.js` 一文件即恢复原行为，零风险尝试自动连贯支付的产品形态。架构上分清职责（前端编排 / 后端单一接口）让回退/迭代都很容易

5. **`OrderPaymentController.Pay` 是旧 OrderOnline 表入口，与新 Order 表脱节**：5-14 引入的 PaymentIdentityController 全写新 `[order]` 表；`Order/WechatPayByOrderPayment` (OrderController.cs:1504 ai 分支) 是新表对齐的支付入口，必须用这个不要切回旧 OrderPaymentController.Pay

6. **`pay-identity-confirm._confirm` 已封装完整**：busy + showLoading + triggerEvent('refreshed') + catch 全做了，父页面只需在 onIdentityRefreshed 接事件并按 status 分支即可；本次未动组件
