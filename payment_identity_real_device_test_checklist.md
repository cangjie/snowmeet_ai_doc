# 支付前身份验证 — 真机测试核查清单

适用版本：`SnowmeetApi @ origin/ai` + `snowmeet_wechat_mini @ origin/ai`，含 2026-05-27 决策时机迁回 notify 改动。

## 0. 前置部署 / 准备

- [ ] **后端**：`origin/ai` 最新 commit 部署到生产或测试环境（含 `PaymentIdentityController.cs` 决策时机改动 + `OrderController.DealSuccessPaidOrder` 同步逻辑）
- [ ] **DB schema** 已具备（应已在 2026-05-14 加过，可二次确认）：
  ```sql
  -- 应均返回 1
  SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID('[order]') AND name = 'wechat_unverified';
  SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID('order_payment') AND name = 'is_proxy_pay';
  ```
- [ ] **小程序**：拉 `origin/ai` 最新 + 微信开发者工具 `Tools → Cache → Clear all data + Clear file cache + 编译`，上传体验版
- [ ] 准备 **两个微信账号** A / B，B 已绑手机号（作为扫码方），手头有第三个账号 C 未绑手机号（用于 phone_required 场景）
- [ ] **真机** 不用开发者工具（`getPhoneNumber` 在工具内不返真号）

## 1. 测试场景矩阵（按 `_resolveStatus` 5 状态）

每场景两阶段验证：
- **阶段 A**：点完身份确认按钮后立刻查 DB（仅 `OrderPayment` 应有变化）
- **阶段 B**：完成支付（或主动放弃）后查 DB（`Order` 才同步）

### 场景 1 — `direct`（扫码方就是订单原会员，无需选择）

**构造**：A 自己下租赁单 → A 自己扫支付二维码

**期望**：
- UI：`pay-identity-confirm` 不显示（status=`direct` 直接进支付按钮）
- 阶段 A：直接进入支付，无 `ConfirmPayIdentity` 调用
- 阶段 B（支付成功）：`order.member_id` 已是 A，`order_payment.member_id` 由微信支付回调本身写入

**SQL**：
```sql
SELECT id, member_id, wechat_unverified FROM [order] WHERE id = @orderId;
SELECT id, member_id, is_proxy_pay, status, pay_method FROM order_payment WHERE id = @paymentId;
```

### 场景 2 — `direct_to_scanner`（订单无主，扫码方有手机号）

**构造**：店员代下单时不录会员（`order.member_id IS NULL`）→ B 扫码

**期望 UI**：显示「确认订单归属，支付完成后订单将归您 1**\*\*\*\*7897」按钮 → 点「确认并继续」→ 跳到支付按钮

**阶段 A（点完"确认并继续"后立即查）**：
```sql
SELECT id, member_id, wechat_unverified FROM [order] WHERE id = @orderId;
-- 期望：member_id 仍为 NULL（关键！决策时机改动的核心断言）
-- 期望：wechat_unverified 仍为 0

SELECT id, member_id, is_proxy_pay, status FROM order_payment WHERE id = @paymentId;
-- 期望：member_id = B 的 member.id，is_proxy_pay = 0，status = 待支付
```

**阶段 B1（支付成功后）**：
```sql
SELECT id, member_id, wechat_unverified FROM [order] WHERE id = @orderId;
-- 期望：member_id = B 的 member.id（由 DealSuccessPaidOrder 同步）
-- 期望（微信支付）：wechat_unverified = 0
```

**阶段 B2（中途放弃，未完成支付）— 关键验证迁移生效**：
```sql
SELECT id, member_id, wechat_unverified FROM [order] WHERE id = @orderId;
-- 期望：member_id 仍为 NULL（订单未变归属，避免错乱）

SELECT id, member_id, status FROM order_payment WHERE id = @paymentId;
-- 期望：member_id = B（已落库，不回滚——这是付款方意图，本就该立即写）
-- status = 待支付
```

### 场景 3 — `choose_identity` → 选 self（订单已匹配 A，B 扫码选"正常支付，转归我"）

**构造**：A 下单后 B 扫支付二维码（B 与 A 不同 member.id）

**期望 UI**：「本订单已记录会员 张三 1**\*\*\*\*7897。您与该会员不一致，请选择...」→ 点「正常支付（订单转归我）」

**阶段 A**：
```sql
SELECT id, member_id FROM [order] WHERE id = @orderId;
-- 期望：member_id 仍为 A（!! 关键：以前是立即被改成 B，现在不该再改）

SELECT id, member_id, is_proxy_pay FROM order_payment WHERE id = @paymentId;
-- 期望：member_id = B，is_proxy_pay = 0
```

**阶段 B（支付成功后）**：
```sql
SELECT id, member_id FROM [order] WHERE id = @orderId;
-- 期望：member_id = B（DealSuccessPaidOrder 把 op.member_id 同步过来）
```

**校验 CoreDataModLog 自动 diff（UpdateOrder 触发）**：
```sql
SELECT TOP 10 * FROM core_data_mod_log
WHERE table_name = 'Order' AND key_value = @orderId AND field_name = 'member_id'
ORDER BY id DESC;
-- 期望最新一条：prev_value=A.id, current_value=B.id, scene='支付成功'
```

### 场景 4 — `choose_identity` → 选 proxy（订单已匹配 A，B 扫码选"替人代付"）

**构造**：同场景 3，但 B 在二次确认 modal 里选「替人代付」

**期望 UI**：点「替人代付」→ `wx.showModal` 二次确认 → 跳到支付按钮

**阶段 A**：
```sql
SELECT id, member_id FROM [order] WHERE id = @orderId;
-- 期望：member_id 仍为 A

SELECT id, member_id, is_proxy_pay FROM order_payment WHERE id = @paymentId;
-- 期望：member_id = B，is_proxy_pay = 1（代付标记！）
```

**阶段 B（支付成功后）— 代付不同步**：
```sql
SELECT id, member_id FROM [order] WHERE id = @orderId;
-- 期望：member_id 仍为 A（代付订单仍归原会员，B 仅做付款方记录）
-- DealSuccessPaidOrder 的 if (paidOp.is_proxy_pay == false ...) 守卫确保不同步
```

### 场景 5 — `phone_required`（扫码方未绑手机号）

**构造**：C（未绑手机号）扫任一支付二维码

**期望 UI**：显示「一键授权手机号」按钮（`open-type="getPhoneNumber"`）

**操作**：点按钮 → 微信弹窗授权 → 自动 POST `ConfirmPayIdentity submit_phone` → 后端解密 encData/iv 写 `member_social_account[type=cell]` → 重新 resolve 状态 → 跳转到对应后续态（场景 2/3/4）

**SQL**（点完授权后）：
```sql
SELECT * FROM member_social_account
WHERE member_id = @cMemberId AND type = 'cell' AND valid = 1
ORDER BY id DESC;
-- 期望：top 1 是新插入的手机号记录
```

## 2. 支付宝通道（如已对接）

支付宝小程序对接当前为 stub（`_submitPhone` 走 `phoneMock` 字段）。若已切真接入，**额外断言**：

**阶段 B（支付宝支付成功后）**：
```sql
SELECT id, wechat_unverified FROM [order] WHERE id = @orderId;
-- 期望：wechat_unverified = 1（由 DealSuccessPaidOrder 同步：op.pay_method='支付宝' → order.wechat_unverified=true）
```

如阶段 A 查 `wechat_unverified` 不应已是 1（关键：以前是立即写，现在延迟到支付成功）。

## 3. 异常路径（必查 — 决策时机迁移的核心价值）

| # | 场景 | 关键断言 |
|---|---|---|
| E1 | choose_identity 选 self → 关闭小程序未支付 | `order.member_id` 保持原 A 不变（以前会被错改成 B） |
| E2 | direct_to_scanner 确认后关闭小程序未支付 | `order.member_id` 保持 NULL |
| E3 | choose_identity 选 proxy → 支付成功 | `order.member_id` 仍是 A（不被 op.member_id 覆盖） |
| E4 | 用户先选 self、再切换到 proxy（同 paymentId 多次调用） | op 状态以最后一次 ConfirmPayIdentity 为准，幂等锚 `op.member_id != null && status='待支付'` 短路返回 |

E1 / E2 是这次改动**最有价值的修复点**，必跑。

## 4. 排查指南（出问题时怎么定位）

### 4.1 阶段 A 后 `order.member_id` 已变 → 决策时机迁移失效

- 查 `PaymentIdentityController.cs:_applyChoice` / `_applyConfirmDirect` 是否还在写 `order.member_id`（git diff 应只剩 op 写入）
- 看 `core_data_mod_log` 该 order 的 `scene` 字段：迁移后只该看到 `scene='支付成功'`，不再有 `scene='choose_self'` 之类的提前写入

### 4.2 阶段 B 后 `order.member_id` 没同步 → notify 钩子未生效

- 查 notify 回调日志：`SnowmeetApi/AlipayCertificate/{appId}/alipay_callback_{date}.txt` 或 `wepay` 对应回调日志路径
- 查 `core_data_mod_log` 该 order 是否有 `scene='支付成功'` 的 member_id diff 行
- 直查 op：`SELECT is_proxy_pay, member_id FROM order_payment WHERE id=@pid` — 如 `is_proxy_pay=0 && member_id=null` 则 PaymentIdentity 流程根本没走，反查 payment_entry 是否调到 `ConfirmPayIdentity`

### 4.3 `pay-identity-confirm` UI 不显示

- 检查 `pages/order/payment_entry.json` 的 `usingComponents` 是否包含 `pay-identity-confirm`
- console 看 `_refreshIdentity()` 是否调到、返回的 `identity.status` 是什么
- `getOrderFromPaymentByCustomer` 的 sessionKey 是否齐全

### 4.4 phone_required 一键授权失败

- console 看 `e.detail.encryptedData` / `e.detail.iv` 是否拿到（开发者工具内是 mock 数据）
- 后端 `_extractPhone` 用 `Util.AES_decrypt(enc, sessionKey, iv)` 解，sessionKey URL encode 问题 5-14 已修过

### 4.5 兜底接口

- 切到 swagger 直调 `GET /api/PaymentIdentity/CheckPayerIdentity?paymentId=...&payerType=wechat&scannerId=...&sessionKey=...` 看后端 raw 返回
- 验证 `_resolveStatus` 5 状态决策结果是否符合 DB 实际数据

## 5. 收尾

测试全部通过后，把结果记到 `sessions/2026-05-27_payment_identity_real_device_validation.md`，并取消 CLAUDE.md 「待真机端到端测试」标记。

5-14 留的另两个 stub（**支付宝真实手机号解密** / **决策时机迁到 notify 回调**）中，第 2 项已随本次改动完成；支付宝 stub 单独处理。
