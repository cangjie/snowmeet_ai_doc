# 2026-06-03 MemberLogin alipay payerid→cell 兜底 + 推迟建会员原则贯穿到 alipay 全链路

接续 6-3 续 留的 AES 解密诊断 pending bug。本场 plan mode 起手，先落 MemberLogin 二次匹配链 + AES helper（commit `e60105e`）；真机测试暴露两件事——AES 实际还是 `not a valid Base-64 string` soft-fail、且用户重申「会员推迟到支付成功才建」原则要贯穿 alipay 全链路 → 第二轮把 PaymentIdentity 三入口 + AlipayPayByOrderPayment + AliController.CallBack 同步对齐（commit `5855be1`）。SnowmeetApi `ai` 分支 push 完结。

## 1. 第一轮：MemberLogin alipay 二次匹配链 + AES helper（commit `e60105e`）

### 1.1 用户需求 + plan 拍板

用户原话："1. 从支付宝提供的API接口，获取到payerid后，先查 member_social_account 查询到valid=1的记录获取到会员ID。2. 如果未获取到会员ID，或者获取到会员ID后，发现该会员没有验证过的手机号，则需要调用支付宝小程序接口获取手机号。3. 如果此时还没有获取到会员ID，但是获取到了手机号，则利用此手机号，继续在 member_social_account 中再次搜索会员id。4. 此时将获取到的信息写入到 mini_session 中的各个字段。... 5. 如果未获取到会员id，此时无需注册新会员和生成新会员ID。"

plan 阶段 4 个决策点（AskUserQuestion 收口）：
- **MSA type 字符串**：保留 `alipay_payerid`（与 `Member.alipayPayerId` getter 对齐，不动 5-30 落地的常量）
- **手机号入口**：两次调用（首次只带 auth_code → `needPhone` 信号；客户端 `my.getPhoneNumber` 拿 encData 后再发起二次调用）
- **AES bug**：本次顺手把 JSON 解包 + base64 字符级清洗 + aes_key.txt BOM/CRLF 清理一并修
- **"没有验证过的手机号"判定**：直查 MSA 表（`valid=1 AND type='cell'` 至少一条），不走 `Member.cell` getter

### 1.2 schema + Code2Session 扩展

- DB 核实 prod `mini_session` 已加 `alipay_payerid varchar(64) NULL` + `cell varchar(15) NULL`（用户口述已 ALTER，sqlcmd 验证通过）
- [`Models/Member/MiniSession.cs`](../SnowmeetApi/Models/Member/MiniSession.cs) 补 `alipay_payerid` + `cell` 两 nullable string 字段
- [`MiniAppHelperController.cs` `Code2Session`](../SnowmeetApi/Controllers/MiniAppHelperController.cs#L620) 加 `cell` + `needPhone` 两字段
- 写 DDL 备忘文件 [`snowmeet_ai_doc/sql/2026-06-03_mini_session_add_alipay_cell.sql`](sql/2026-06-03_mini_session_add_alipay_cell.sql) 跨机/新环境兜底

### 1.3 API 签名 + `_alipayMemberLogin` 重构

- `MemberLogin(code, openIdType, aliSessionKey=null, aliEncData=null)` — 微信分支已有局部 `string sessionKey = sessionObj.session_key;`，alipay 新增参数加 `ali` 前缀避命名冲突（编译期踩过一次 CS0136/CS0841）
- `_alipayMemberLogin(code, sessionKey, encData)` 分两子方法：
  - **首次**（`_alipayMemberLoginFirstCall`）：oauth.token → payerId → MSA(`alipay_payerid`) → 直查 MSA 看 `cell` 是否齐 → 写 mini_session（**用新 `alipay_payerid` 列替代往 `wechat_openid` 列塞 hack**）→ `needPhone` 信号（缺会员 或 有会员无 cell 时 true）
  - **二次**（`_alipayMemberLoginSecondCall`）：mini_session 反查 → `AlipayPhoneDecryptHelper.Decrypt` 解 encData → 仍 null 时按 phone 反查 MSA(`cell`) → 命中后 `_ensureAlipayPayerIdMsa` INSERT alipay 记录 → 更新 mini_session(cell, member_id) → 返回
- 严守 5-29 原则：**MemberLogin 永不建新 Member**

### 1.4 新建 `Helpers/AlipayPhoneDecryptHelper.cs`（AES bug 根因修）

[`SnowmeetApi/Helpers/AlipayPhoneDecryptHelper.cs`](../SnowmeetApi/Helpers/AlipayPhoneDecryptHelper.cs)（~160 行，新建）：
- **JSON 包装兜底**：my.getPhoneNumber 新 SDK 返 `{"response":"<base64>","sign":"...","signType":"RSA2"}` 整段当 base64 直传 → 试 JSON 解包取 `response` 字段
- **base64 字符级清洗**：去 CRLF/LF/空白 + `% 4` 补 `=` padding（应对 URL 传输丢 `==`）
- **aes_key.txt BOM/CRLF 清理**：显式去 UTF-8 BOM `﻿` + Replace `\r`/`\n`
- 每步 `Console.WriteLine` 打 `[AlipayPhoneDecrypt]` 标记，便于真机日志看清洗哪一步生效
- 调用方：[`PaymentIdentityController._extractPhone`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs#L546) alipay 分支收口到 helper，与 MemberLogin 二次调用同源
- `_loadSessionContext` 改造按 `session_type` 分流：alipay 取 `alipay_payerid` 列（空时 fallback `wechat_openid` 兼容历史 session）

### 1.5 rebase 远端 6 个新 commit

push 前 fetch 发现 `c801fde..15dacb2` 远端 6 个新 commit（`a127a16`/`73153584`/`fecea2b`/`bd0baa7`/`2ae4742`/`15dacb2`）。其中：
- `bd0baa7`：`_extractPhone` 3 桶 try-catch 诊断（zhx push）
- `2ae4742 pay`：JSON-wrap 解包（cangjie push，与我 helper 重复）
- `15dacb2 phone`：多路径 mobile 查找 + 嵌套 response 再解 + code/sub_code 错误透传 + `_submitPhone` alipay 软依赖兜底

rebase 1 处冲突在 `_extractPhone` alipay 分支：
- 把远端的"多路径 mobile 查找 + 嵌套 response 解包 + code/sub_code 错误透传"全数搬进 helper
- `_extractPhone` 整段收口为 `return AlipayPhoneDecryptHelper.Decrypt(body.encData, ALIPAY_MINI_APP_ID);` 一行
- 远端 `_submitPhone` 软依赖兜底（解密失败时返 `code=0` 让 choose/confirm_direct 流程能继续）独立保留

### 1.6 本机模拟验证用户 encData 通过

担心 helper 对真实 encData 是否走通，用 Python 模拟 `Util.UrlDecode + JSON 解包 + base64 padding 三步`，输入用户实际 encData `{"response":"KXJuRxc4..."}`：
- raw 207 字符 → UrlDecode 后 207（同长但内容变：`+` 转 space）→ Replace 转回 `+` ✓
- JSON 解包取 `response` 字段 → 内层 192 字符
- `192 % 4 == 0` 整除，无需补 padding
- base64 解码 → 144 字节（9 个 AES-128 块）合法密文

**编码层面 helper 应该能处理这个 input**。如果真机仍失败，根因在 server-side：① aes_key.txt 仍脏；② prod 那把 key 与客户端用的 appId 不匹配；③ AES 解密结果不是合法 JSON 或缺 mobile 字段。

### 1.7 commit `e60105e`（push origin/ai）

```
MemberLogin alipay 分支: payerid → cell 兜底 + AES 解密 bug 修
```

snowmeet_ai_doc DDL 备忘 `fd55d40`（push origin/main）。

## 2. 第二轮：用户原则贯穿 alipay 全链路（commit `5855be1`）

### 2.1 真机测试反馈 + 用户原则重申

用户在 `mini.snowmeet.top/api/PaymentIdentity/ConfirmPayIdentity` 跑 paymentId=42572 的真机请求，payload 含 `encData": "{\"response\":\"KXJuRxc4...\"}"`，结果：

```json
{
  "code": 0,
  "data": {"status": "choose_identity", "scannerHasCell": false, "scannerMemberId": null, ...},
  "message": "手机号解析失败,将按未授权继续"
}
```

用户两个不满：
1. AES 解密**还是失败**（首轮 helper 部署后仍出 soft-fail）
2. **"刚才的plan说的很明白，如果没查询到会员ID，那么在验证手机号后，生成会员ID，仅仅是在支付成功后，才生成。这个原则刚才表述的不够明确吗？"** — 用户重申"推迟建会员"原则应贯穿全链路，不只限 MemberLogin

### 2.2 AskUserQuestion 收口 3 个边界

1. **原则范围**：仅 alipay 通道（wechat 已稳定，避免回造 5-28/29 重构的路）
2. **物化策略**：alipay notify 收到支付成功后兜底建：`MSA(alipay_payerid)` 命中 → 用之；没命中再从最新 alipay session 拿 cell → `MSA(cell)` 命中 → 用之；都没命中 → 建新 Member，然后再调 `DealSuccessPaidOrder`
3. **部署状态**：用户确认已部署 e60105e（含 helper），AES 真错在 server 侧

### 2.3 PaymentIdentity 三入口 alipay 分支去 `_createNewMember`

[`PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs)：

- **`_submitPhone`**：`scannerMember == null && phoneOwner == null` 分支按 `payerType == "alipay"` 拆：alipay 把解出的 phone 写进 `mini_session.cell` 后早返回（不建会员、OP.member_id 留 null），调 `_resolveStatus` 重算 status 返回；wechat 维持原 `_createNewMember`
- **`_applyChoice`**：`pre.scannerMemberId == null` 分支同样拆：alipay 不 bootstrap 建会员，让 `OP.member_id = pre.scannerMemberId`（可空），仅写 `is_proxy_pay` 意图；wechat 维持
- **`_applyConfirmDirect`**：与 `_applyChoice` 同构改造，OP.member_id 同样可空

下游兼容：`int scannerMemberId = (int)pre.scannerMemberId;` → `int? scannerMemberId = pre.scannerMemberId;`，下方 `op.member_id = scannerMemberId;` 直接赋值（OP.member_id 本就是 `int?` 字段）。

### 2.4 `AlipayPayByOrderPayment` 容忍 OP.member_id null

[`OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) `AlipayPayByOrderPayment`：

之前要求 `GetMemberBySessionKey(sessionKey, "alipay_payerid")` 返非 null + 有 `alipayPayerId`。新流程下 PaymentIdentity 不建会员 → session.member_id 可为 null → `GetMemberBySessionKey` 返 null → 整个 `AlipayPayByOrderPayment` 直接 "未找到支付宝用户" 失败。

改为：直查 `mini_session` 拿 `alipay_payerid` 作 buyerId（**不再要求 member 实体**），`session.member_id` 可空。三分支（首次/换人/buyer_id 不匹配）按 `sessionMemberId` 可空适配：
- **首次**（`payment.member_id == null`）：`payment.member_id = sessionMemberId`（可能仍 null），`ali_buyer_id = buyerId`
- **换人** 新增守卫 `sessionMemberId != null`：guest 接续不视为换人，跳过 CoreDataModLog
- **buyer_id 不匹配**：`payment.member_id == sessionMemberId`（含两者都 null）但 buyer_id 没跟上时刷新

### 2.5 `AliController.CallBack` 兜底建会员 helper

[`AliController.cs`](../SnowmeetApi/Controllers/Order/AliController.cs) `trade_status_sync TRADE_SUCCESS` 分支，在 `DealSuccessPaidOrder` 调用之前插入：

```csharp
if (payment.member_id == null && !string.IsNullOrEmpty(callback.buyerId))
{
    payment.member_id = await _materializeAlipayMemberOnPaid(payment, callback.buyerId);
    // save
}
```

新 helper `_materializeAlipayMemberOnPaid(payment, buyerId)` 5 步：
1. MSA(`alipay_payerid=buyerId, valid=1`) → 命中即用
2. 没命中 → 最新 alipay session（`session_type='alipay_payerid' AND alipay_payerid=buyerId`，order by expire_date desc）→ 拿 cell → MSA(`cell=cell, valid=1`) → 命中即用
3. 都没命中 → 建新 Member（`source='支付宝支付成功', valid=1`），有 cell 则一并写 MSA(`cell`)
4. 所有路径都补 MSA(`alipay_payerid=buyerId, member_id=该会员, valid=1`)，把 payerId 永久绑给该会员
5. session.member_id 同步回填（下次同一 session 走 PaymentIdentity 不再走兜底）

完成兜底后再调 `DSP`，原 `paidOp.is_proxy_pay == false && paidOp.member_id != null` 同步守卫不动。

**编译踩坑**：`Member` 在 AliController 命名空间下与 `Aop.Api.Domain.Member` 歧义 → 用完全限定 `new SnowmeetApi.Models.Member { ... }`

### 2.6 soft-fail UX 改进

`_submitPhone` alipay 软失败 message 加 `+ ex.Message`：前端 toast 直接显示 helper 报的具体错（`aesKey 不是合法 base64 (len=X head12=...)` / `解密结果中无 mobile 字段 (code=10000, subCode=...)` 等），不用 SSH 抓 journalctl 就能定位 AES bug 根因。

### 2.7 commit `5855be1`（push origin/ai）

```
alipay 通道: 推迟建会员到支付成功 notify (用户原则贯穿)
```

dotnet build 0 error / 12 warning（历史无关）。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Models/Member/MiniSession.cs`](../SnowmeetApi/Models/Member/MiniSession.cs) | +`alipay_payerid` + `cell` 两 nullable string |
| [`SnowmeetApi/Helpers/AlipayPhoneDecryptHelper.cs`](../SnowmeetApi/Helpers/AlipayPhoneDecryptHelper.cs) | 新建，封装 AES 解密 + JSON 解包 + base64 清洗 + key BOM/CRLF 清洗 + 多路径 mobile 查找 + alipay code/sub_code 错误透传 |
| [`SnowmeetApi/Controllers/MiniAppHelperController.cs`](../SnowmeetApi/Controllers/MiniAppHelperController.cs) | `MemberLogin` 加 `aliSessionKey`/`aliEncData` optional 参数；`_alipayMemberLogin` 拆首次/二次；mini_session 写新列；新加 `_ensureAlipayPayerIdMsa`；`Code2Session` 加 `cell` + `needPhone` |
| [`SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) | `_extractPhone` alipay 分支收口到 helper；`_loadSessionContext` 按 session_type 分流；三入口（`_submitPhone`/`_applyChoice`/`_applyConfirmDirect`）alipay 分支去 `_createNewMember`；soft-fail message 带 ex.Message |
| [`SnowmeetApi/Controllers/OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) | `AlipayPayByOrderPayment` 不再要求 member 实体，直查 mini_session 拿 buyerId；三分支按 sessionMemberId 可空适配 |
| [`SnowmeetApi/Controllers/Order/AliController.cs`](../SnowmeetApi/Controllers/Order/AliController.cs) | `CallBack` trade_success 分支在 DSP 之前调 `_materializeAlipayMemberOnPaid` 兜底建/绑会员 |
| [`snowmeet_ai_doc/sql/2026-06-03_mini_session_add_alipay_cell.sql`](sql/2026-06-03_mini_session_add_alipay_cell.sql) | DDL 备忘（prod 已加列，跨机/新环境兜底） |

## 学到的小知识

1. **`Util.UrlDecode` 在 base64 上是无害的**：`HttpUtility.UrlDecode + Replace(" ","+")` round-trip 把 `+` → space → `+`。但若 raw JSON 里有外部 whitespace（pretty-print）会被错转 `+` 破坏 JSON。compact JSON 安全。Python 模拟两步验证过
2. **C# 参数 vs 局部变量同名 CS0136 不挑顺序**：哪怕参数仅在 alipay 分支用、wechat 分支后才声明同名局部变量，编译器仍按"参数在整个方法体可见 + 局部变量重复声明"判错。本场踩了 `string sessionKey` 一次，用 `ali` 前缀绕开
3. **`Member` 命名空间歧义**（AliController 等同时 import `Aop.Api.Domain` 和 `SnowmeetApi.Models`）：建实例时必须完全限定 `new SnowmeetApi.Models.Member { ... }`，否则 CS0104
4. **`GetMemberBySessionKey` 是 member-side 强约束**：session 命中但 `member_id` 为 null 时直接返 null，调用方拿不到 session 本体信息。新流程下 alipay 推迟建会员后 session.member_id 可能长期为 null → 上游必须改成直查 mini_session 表（payerid + cell 两列即可），不走 GetMemberBySessionKey
5. **OrderPayment `member_id` 是 `int?`，CoreDataModLog `member_id` 字段也是 `int?`**：从 `int scannerMemberId = (int)pre.scannerMemberId;` 改 `int? scannerMemberId = pre.scannerMemberId;` 下游无副作用。换人日志的 `current_value = sessionMemberId.ToString()` 在 null 时报 NRE，加守卫 `sessionMemberId != null` 跳过 guest 接续即可
6. **PaymentIdentity 三入口 + AlipayPayByOrderPayment + AliController.CallBack 是 alipay 流程的 4 个建会员/绑会员锚点**：原则贯穿要 4 处一起改，缺一处链路就断（典型：`_submitPhone` 不建 + `AlipayPayByOrderPayment` 仍要求 member → 卡死）
7. **AES 解密失败的诊断信息要回到响应里**：journalctl 在生产很难即时拿到，把 `ex.Message`（含 length/head/JSON wrap 等清洗诊断）拼到 soft-fail message 里直接前端 toast 看，调试 round trip 比 SSH 快一个数量级
8. **rebase 远端重复工作的修法**：远端 `2ae4742 pay` / `15dacb2 phone` 与 helper 直接重叠，最干净的做法是把远端的功能扩展（多路径 mobile / 嵌套 response / code/sub_code 错误透传）全数搬进 helper、调用方收口为一行 `Decrypt(...)`，保留远端的独立功能（如 `_submitPhone` soft-fail）作 helper 之外的 wrap
9. **`_materializeAlipayMemberOnPaid` 是 alipay 物化锚点**：4 个建会员/绑会员锚点中，前 3 个（PaymentIdentity 三入口）都改成"不建"，第 4 个（AliController.CallBack）变成"唯一兜底入口"。这与 wechat 路径"PaymentIdentity 仍建 stub" 不同，是 alipay 流程的独立设计
