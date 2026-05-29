# 2026-05-29 MemberLogin 不再建 stub + 一系列 valid/排序根因修复：从「前端 stall」一路定位到「`new MemberSocialAccount` 漏 valid=1」

接续 5-28 真机测试。用户报告 `paymentId=42551` 走完授权流程后页面循环要求授权手机号、无法进微信支付。多轮迭代：每轮真机给出 console log + DB SQL 观察 → 定位 → 重构 → 部署 → 暴露新根因 → 再修。本日改动覆盖前端 (`snowmeet_wechat_mini/`)、后端 (`SnowmeetApi/`)、文档 (`snowmeet_ai_doc/`) 三个仓库。

## 1. 第一轮：前端 stall + UI 简化

### 1.1 paymentId=42549「请稍候」死页

- 用户反馈：进 `pages/order/payment_entry?paymentId=42549` 后页面卡在「请稍候……」字面文字，看不到订单、点不了支付、更别说「软授权手机号」弹窗。
- 用户原话："昨晚改过为什么没生效？"
- 根因：[`payment_entry.js:41-52`](../snowmeet_wechat_mini/pages/order/payment_entry.js) `onShow` 两层 promise 都没 `.catch()`：
  ```js
  app.loginPromiseNew.then(function (){
    data.getOrderFromPaymentByCustomer(...).then(function (order){
      // ...
    })  // ❌ 没 .catch()
  })  // ❌ 也没 .catch()
  ```
- 5-28 同时改了 [`util.js:115-120`](../snowmeet_wechat_mini/utils/util.js) `performWebRequest` 非 200 `reject(res.statusCode)`，加上后端 `code != 0` 也走 reject。这套组合让 latent bug 触发：reject 真的发生，但没 catch → `order` 不 setData → wxml `<view class="page" wx:if="{{order}}">` 整页空 → 只剩 `<view wx:if="{{!order}}">请稍候……</view>`。
- 修复：
  - `onShow` 补两层 catch，外层 catch（`loginPromiseNew` 失败）`setData({orderLoadFailed: true})`，内层 catch（`getOrderFromPaymentByCustomer` 失败）`setData({orderLoadFailed: true, order: null, payment: null})` 并仍调 `_refreshIdentity()`
  - wxml 把 `<view wx:if="{{!order}}">请稍候……</view>` 拆成两态：`!order && !orderLoadFailed` 显示 loading；`!order && orderLoadFailed` 显示 fallback page（最小订单卡片 + 嵌入 `pay-identity-confirm` + 「继续支付」按钮）
  - `pay()` 跳过 `payment==null` 的早 return；`_doWepay()` 用 `pid = (payment && payment.id) || that.data.paymentId` 兜底，让 fallback 路径也能调微信支付
  - 后端 [`OrderController.GetOrderFromPaymentByCustomer:2104`](../SnowmeetApi/Controllers/OrderController.cs) `GetMemberBySessionKey` 包 try/catch 当 null，sessionKey 失效不阻塞游客查待支付单

### 1.2 全局 latent 卡死：`app.js:140` loginPromiseNew 永久 pending

- 加诊断 log 后用户发现「获取会员信息失败」toast — 来自 [`MiniAppHelperController.MemberLogin:245`](../SnowmeetApi/Controllers/MiniAppHelperController.cs) 当 `memberId` 找到 MSA 但 member 表查不到时（脏数据）返 `code=1`。
- 真正根因：[`app.js:140`](../snowmeet_wechat_mini/app.js) `util.performWebRequest(url).then(function (resolveData) { ... resolve({}) })` **只有 then 没 catch**。MemberLogin reject 后 then 不跑 → `resolve({})` 永远不被调用 → `loginPromiseNew` 永久 pending（既不 resolve 也不 reject）。所有 page 的 `app.loginPromiseNew.then(...)` 永远不跑，外层 catch 也接不住 pending。
- 修复：app.js `performWebRequest(MemberLogin).then(...)` 后补 `.catch(function (err) { resolve({}) })` + `wx.login fail` 分支也补 `resolve({})`
- 5-28 该跟着 util.js 一起改，没改：留了一周的全局 latent bug

### 1.3 拆掉自定义 phone-prompt-overlay 弹窗

- 用户原话："点击「确认并支付」后，会自动弹出微信自带的授权手机号的页面，因此就不需要再弹出我们自己的页面了。用户点授权或者取消，都会有相应的回调，我们接下来在这些回调里继续和服务器端交互即可。"
- 删除：[`payment_entry.wxml`](../snowmeet_wechat_mini/pages/order/payment_entry.wxml) 全屏遮罩 + 底部卡片；JS 里 `showPhonePrompt` data + `onAuthorizePhone` + `onSkipPhone` 两个方法 + `pay()` 里 `if (!identity.scannerHasCell) { showPhonePrompt: true }` 分支；wxss 全部 `.phone-prompt-*` 样式（~80 行）
- 改为：[`pay-identity-confirm/index.wxml`](../snowmeet_wechat_mini/components/pay-identity-confirm/index.wxml) `direct_to_scanner` 状态的「确认并继续」按钮加分流：`!result.scannerMemberId || !result.scannerHasCell` → `open-type="getPhoneNumber"` + `bindgetphonenumber="onGetPhoneNumberAndConfirmDirect"`；否则 `bindtap="onConfirmDirect"`
- 新加 `onGetPhoneNumberAndConfirmDirect(e)`：拒绝授权 → `_confirm({action:'confirm_direct'})`；同意 → 串 `submit_phone` → `confirm_direct` 链，最后 `triggerEvent('refreshed')`

### 1.4 关键洞察

5-28 之前以为业务需求是新功能，实际上 `_submitPhone` + `_createNewMember` 已经完整实现「无会员→验证手机号→自动建会员」的逻辑，只是被前端 stall 屏蔽了。这一轮主要是修衔接 bug，没改业务流程。

## 2. 第二轮：MemberLogin 自动建 stub 是 root cause

### 2.1 用户用 SQL 直接定位

- 真机 paymentId=42551 跑：`globalData.member {id: 41095, cell: null, wechatMiniOpenId: null}` + `[CheckPayerIdentity] {scannerMemberId: 41095, scannerHasCell: false}`
- 用户跑 `SELECT * FROM member_social_account WHERE member_id BETWEEN 41084 AND 41095 ORDER BY member_id`，**直接观察到 root cause**：相同 openid / unionid 在多个连续 member_id 下重复出现（41084 = 历史真实会员，41085-41095 = stub 累积）
- 用户原话拍板架构原则：
  > 一个微信的 openid 和 unionid 只允许有一个 member id。如果是个非会员，不能每刷新一次页面就生成个会员 id，应该是点了支付按钮的时候，看到没有会员 id 再生成会员。这样如果顾客选择了绑定手机号，那么手机号和 openid 以及 unionid 就可以绑在一个会员 id 下面，如果不授权手机号，直接给 openid 和 unionid 生成会员 id 也不晚。

### 2.2 实施

- **DDL**：[`sql/2026-05-29_mini_session_add_openid_unionid.sql`](../sql/2026-05-29_mini_session_add_openid_unionid.sql)
  ```sql
  ALTER TABLE mini_session ADD wechat_openid NVARCHAR(64) NULL;
  ALTER TABLE mini_session ADD wechat_unionid NVARCHAR(64) NULL;
  ```
  SQL Server online 操作，零锁表。EF 模型 [`MiniSession.cs`](../SnowmeetApi/Models/Member/MiniSession.cs) 加两个 nullable string 属性

- **`MiniAppHelperController.MemberLogin` 重构**（[`MiniAppHelperController.cs:206-244`](../SnowmeetApi/Controllers/MiniAppHelperController.cs)）：
  - 删除原 line 207-306 整个 if/else 块（自动建 stub + 第一轮 b 加的「脏数据自我恢复」一并回滚）
  - `memberId != null` → `_memberHelper.GetWholeMemberById((int)memberId)`；否则 `member = null`
  - mini_session 始终写入 `member_id = member?.id` + `wechat_openid = cleanOpenId` + `wechat_unionid = cleanUnionId`
  - 末尾 `if (member != null) member.memberSocialAccounts = ...` null 兜底

- **`PaymentIdentityController` 新增 helper**（[`PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs)）：
  - `_loadSessionContext(sessionKey)`：反查 mini_session 拿 `(wechat_openid, wechat_unionid, sess)` 三元组
  - `_invalidateMsa(memberId, num, type)`：把指定 num+type+memberId 的 valid=1 MSA 全部 valid=0

- **`_createNewMember` 增强签名**：
  ```csharp
  private async Task<int> _createNewMember(string? phone, string scannerId, string msaType, string? unionId = null)
  ```
  phone 可空（拒绝授权场景）+ unionId 参数（绑 wechat_unionid MSA）+ `valid = 1` 显式设值（防御）

- **`_submitPhone` 重写**：
  - 顶部 `_loadSessionContext` 拿 sessOpenid/sessUnionid/sess；scannerId 空时用 sessOpenid 兜底
  - **删除两处 `alreadyBoundSameType` 拒绝逻辑**（line 286-292 + 322-328）
  - 内部 `EnsureUnionIdMsa` local helper：若 phoneOwner/scanner 没 unionid MSA 则 _addMsa 补
  - 每个分支末尾 `if (sess != null && sess.member_id != finalMemberId) { sess.member_id = finalMemberId; SaveChanges }`

- **`_applyConfirmDirect` 散客分支**：
  - 原 line 413-415 `scannerMemberId == null → 报错 scanner_not_registered`
  - 改为：`_loadSessionContext` → `_createNewMember(null, sessOpenid, msaType, sessUnionid)` 自动建会员（无 cell）+ `sess.member_id` 更新 + `pre.scannerMemberId = newMemberId` → 继续 confirm_direct 主流程

- **前端 guest 兼容**：
  - [`reg.wxml`](../snowmeet_wechat_mini/pages/register/reg.wxml) `wx:if="{{member && member.cell == null}}"` 在 `member==null` 时跳过 member-auth 走 else 显示"已合并"提示——不正确。改为 `!member || !member.cell` 让未注册 user 也能授权
  - 其他 4 个 page 引用 `globalData.member` 都通过 `|| {}` 兜底或不直接 access 字段。grep 精确搜 `globalData.member.` 字段访问零命中

## 3. 第三轮：真机暴露多个二级 bug

### 3.1 TenpayController.cs:130/268 latent crash

- 用户真机直接打 `https://mini.snowmeet.top/api/Order/WechatPayByOrderPayment/42551?sessionKey=...` → `System.ArgumentNullException: Value cannot be null. (Parameter 'prepayId')`
- trace 指向 [`TenpayController.cs:130`](../SnowmeetApi/Controllers/Order/TenpayController.cs)：`GenerateParametersForJsapiPayRequest(request.AppId, response.PrepayId)` 在 line 131 `response.PrepayId != null` 检查**之前**就调，PrepayId=null 时直接 crash
- 修复：两处（line 130 jsapi + line 268 app）一并把 if 检查移到 GenerateParameters 前，`PrepayId == null` 时：
  ```csharp
  Console.WriteLine($"TenpayRequest: PrepayId null/empty for payment {payment.id}, out_trade_no={...}, open_id={...}, response={JsonConvert.SerializeObject(response)}");
  return null;
  ```
  + `using Newtonsoft.Json` 顶部加
- 真因：微信返 PrepayId null 通常是 out_trade_no 重复、open_id 跟 appId 不匹配、amount=0 等业务层拒绝；prod 日志写 response JSON 后能 errcode/errmsg 直接定

### 3.2 `WechatPayByOrderPayment` 强制刷新 out_trade_no

- [`OrderController.cs:1611`](../SnowmeetApi/Controllers/OrderController.cs) 之前的逻辑：三个 if 分支（1551 首次/1560 换人/1595 open_id 不匹配补写）都不命中时（PaymentIdentity 已 pre-set op.member_id = member.id 且 open_id 已对得上），用 DB 里旧的 out_trade_no 申请 prepay → 微信判重复 → PrepayId=null → crash
- 修复：line 1611 调 TenpayRequest 前无条件比较 + 刷新到新算的 outTradeNo + SaveChanges：
  ```csharp
  if (payment.out_trade_no != outTradeNo) {
      payment.out_trade_no = outTradeNo;
      payment.update_date = DateTime.Now;
      ...
  }
  ```

### 3.3 真正的 root cause：`new MemberSocialAccount` 漏 valid=1

- 用户拍板（直接 SQL 观察）："注册新会员的时候，member 表的 valid 字段 和 member_social_account 的 valid 应该设置为1, 目前是默认为0的"
- 搜了 7 处 `new MemberSocialAccount`，6 处都显式 `valid = 1`，**唯一漏的就是** [`MemberController.BindMemberMainCellNum:343-349`](../SnowmeetApi/Controllers/MemberController.cs)：
  ```csharp
  if (!find) {
      MemberSocialAccount msa = new MemberSocialAccount() {
          id = 0, member_id = memberId, type = "cell", num = num.Trim()
          // ❌ 漏 valid = 1
      };
      await _db.memberSocialAccount.AddAsync(msa);
  }
  ```
- 为什么模型默认值 `public int valid {get; set;} = 1;` 不生效？推测：EF Core 9 + 某种 schema migration 路径下 `INSERT INTO ... (...)` 没把 valid 列包含进去 / DB schema 上 valid 列有 DEFAULT 0 constraint → 落库 valid=0
- 后果链：`_submitPhone` 走 "stub 无 cell + phoneOwner==null" 分支调 `BindMemberMainCellNum(scanner, cell)` → cell MSA 落库 valid=0 → `Member.cell` 计算属性（[Member.cs:81-102](../SnowmeetApi/Models/Member/Member.cs)）`GetInfo("cell")` 只收 `valid==1`，返 null → `scannerHasCell=false` → 下次再点「确认并继续」按钮，wxml 判断 `!scannerHasCell` 还是触发 getPhoneNumber → 用户反复授权死循环
- 修复：两处显式 `valid = 1`：
  - [`_createNewMember`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) 新建 Member 时也加 `valid = 1`（防御）
  - [`BindMemberMainCellNum`](../SnowmeetApi/Controllers/MemberController.cs) 新建 cell MSA 时显式 `valid = 1` + 加注释解释为什么

### 3.4 scanner 优先，不再迁移到 phoneOwner

- 用户原话："第一次支付未授权手机号，但是支付成功了；下一次，支付一个新订单，再次进入支付页面，为什么把自己上一次支付时，在 member_social_account 当中留下的记录的 valid update 成 0？应该是第二次刷新后，就可以拿到会员 ID 了，用这个会员 ID 支付呀。你是个傻逼吗？"
- root cause 分析：`_submitPhone` 的 "stub 无 cell + phoneOwner!=null + 不同 id" 分支原本：
  ```csharp
  await _addMsa(phoneOwner.id, scannerId, msaType);
  await EnsureUnionIdMsa(phoneOwner.id, phoneOwner);
  await _invalidateMsa(scannerMember.id, scannerId, msaType);  // ← 把第一次建的 member 的 openid MSA 失效
  await _invalidateMsa(scannerMember.id, sessUnionid, MemberSocialAccount.TYPE_WECHAT_UNIONID);
  finalMemberId = phoneOwner.id;
  ```
  把当前 openid 关联的 member（第一次散客建的）失效，迁移到 cell 拥有者（phoneOwner）名下。
- 用户精神：**当前 openid 已经有 member 了，就用它，绝对不动**
- 修复 _submitPhone 该分支 → 一行 `finalMemberId = scannerMember.id;`，不动 phoneOwner，不动 scanner MSA，cell 该归谁归谁
- 配套修复 [`pay-identity-confirm/index.wxml`](../snowmeet_wechat_mini/components/pay-identity-confirm/index.wxml) 按钮条件：从 `!result.scannerMemberId || !result.scannerHasCell` 改为仅 `!result.scannerMemberId` —— scanner 有会员就普通 `bindtap="onConfirmDirect"` 直接走支付，不再因 `scannerHasCell=false` 反复触发 getPhoneNumber（之前的逻辑配合"stub 不同 id 失效 MSA"会形成死循环）

## 4. 新的决策规则（拍板，未来必须遵守）

1. **MemberLogin 永不建 stub** — 未注册 user `member = null`,session 写 openid + unionid 暂存
2. **建会员的唯一入口是 PaymentIdentity** — 点支付按钮时建,要么 `_submitPhone`（授权了手机号）要么 `_applyConfirmDirect` 散客分支（拒绝授权)
3. **scanner（当前 openid 关联的 member）优先** — 不论 cell 是否被别人绑过,都用 scanner 完成支付,不去迁移、不去失效 scanner MSA
4. **新建的所有 `Member` / `MemberSocialAccount` 都必须显式 `valid = 1`** — 不依赖 model 默认值（EF Core + DB schema default 0 constraint 组合下会落库 valid=0）
5. **wxml getPhoneNumber 按钮条件**：仅当 `!scannerMemberId`（散客）。scanner 有会员就普通 bindtap → 直接 confirm_direct → 支付

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Models/Member/MiniSession.cs`](../SnowmeetApi/Models/Member/MiniSession.cs) | +`wechat_openid` + `wechat_unionid` 两 nullable string |
| [`snowmeet_ai_doc/sql/2026-05-29_mini_session_add_openid_unionid.sql`](../sql/2026-05-29_mini_session_add_openid_unionid.sql) | DDL 脚本(prod 已执行) |
| [`SnowmeetApi/Controllers/MiniAppHelperController.cs`](../SnowmeetApi/Controllers/MiniAppHelperController.cs) | `MemberLogin` 删 line 207-306 自动建 stub 整段 + session 写 openid+unionid + 末尾 `if (member != null)` null 兜底 |
| [`SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) | `_createNewMember` 加 unionId 参数 + phone 可空 + 显式 valid=1;新增 `_loadSessionContext` / `_invalidateMsa` helpers;`_submitPhone` 删 alreadyBoundSameType + 用 unionid + sess.member_id 更新 + **stub 不同 id 分支改为只用 scanner 不动 phoneOwner**;`_applyConfirmDirect` 散客分支自动建会员 |
| [`SnowmeetApi/Controllers/Order/TenpayController.cs`](../SnowmeetApi/Controllers/Order/TenpayController.cs) | PrepayId null 检查移到 GenerateParameters 之前(两处) + 失败时 log response + `using Newtonsoft.Json` |
| [`SnowmeetApi/Controllers/OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) | `GetOrderFromPaymentByCustomer` try/catch + `WechatPayByOrderPayment` 调 TenpayRequest 前强制刷新 out_trade_no |
| [`SnowmeetApi/Controllers/MemberController.cs`](../SnowmeetApi/Controllers/MemberController.cs) | **`BindMemberMainCellNum` 新建 cell MSA 显式 valid=1**（漏设的核心 bug） |
| [`snowmeet_wechat_mini/app.js`](../snowmeet_wechat_mini/app.js) | `loginPromiseNew` 补 catch + `wx.login fail` 也 resolve({}) |
| [`snowmeet_wechat_mini/pages/order/payment_entry.{js,wxml,wxss}`](../snowmeet_wechat_mini/pages/order/) | onShow 两层 catch + fallback 视图 + 删 phone-prompt-overlay + pay()/_doWepay 兼容 payment==null + 大量诊断 console.log |
| [`snowmeet_wechat_mini/components/pay-identity-confirm/index.{js,wxml}`](../snowmeet_wechat_mini/components/pay-identity-confirm/) | `onGetPhoneNumberAndConfirmDirect`(submit_phone→confirm_direct 链);按钮 wx:if 改为仅 `!scannerMemberId`;诊断 log |
| [`snowmeet_wechat_mini/pages/register/reg.wxml`](../snowmeet_wechat_mini/pages/register/reg.wxml) | `!member` 也走 member-auth(collateral，跟支付无关但避免 globalData.member 为 null 时显示"已合并") |

## 学到的小知识

1. **`new MemberSocialAccount` / `new Member` 必须显式 `valid = 1`**：model 默认值 `public int valid {get; set;} = 1;` 在 EF Core 9 + 某些 schema migration 路径下不生效。`INSERT` SQL 不一定带这个列，落库为 DB 列 default（可能是 0）。所有 7 处 `new MemberSocialAccount` 都查了一遍，唯一漏的 `BindMemberMainCellNum:343` 是本日 prod 死循环 root cause。**未来 new entity 都要显式 `valid = 1`**。

2. **`Member.cell` / `Member.wechatMiniOpenId` 都是计算属性**（`[NotMapped]`），从 `memberSocialAccounts` 集合按 `type` filter `GetInfo(type)`，且只收 `valid == 1`：
   ```csharp
   public List<MemberSocialAccount> GetInfo(string type) {
       List<MemberSocialAccount> msaList = new List<MemberSocialAccount>();
       foreach (var msa in memberSocialAccounts) {
           if (msa.valid == 1 && msa.type.Trim().Equals(type.Trim())) {
               msaList.Add(msa);
           }
       }
       return msaList;
   }
   ```
   任何让 valid 落 0 的 bug 都会让 cell/wechatMiniOpenId/wechatUnionId 计算属性返 null,引发各种"明明绑了为什么查不到"的死循环。

3. **EF Core filtered Include + AsSplitQuery + AsNoTracking 组合需小心**：`GetWholeMemberById` 用 `Include(m => m.memberSocialAccounts.Where(msa => msa.valid == 1))` filtered include + AsSplitQuery + AsNoTracking。理论上正确,实际本日没暴露 bug,但记住组合的复杂度。

4. **微信小程序 `getPhoneNumber` 只能 button `open-type=getPhoneNumber` + `bindgetphonenumber` 直接触发**：5-28 我们最初设计的"自定义遮罩 + 按钮"是多余的,微信原生授权页足够。用户授权/拒绝/取消都通过同一个 `bindgetphonenumber` 回调,`e.detail.errMsg === 'getPhoneNumber:ok'` 区分。

5. **`loginPromiseNew` 是个全局阻塞 promise,任何地方让它永久 pending 都是全局卡死**：今天发现 `app.js:140` 的 `performWebRequest(MemberLogin).then(...)` 没 catch,MemberLogin reject 后 then 不跑 → resolve({}) 永远不被调用 → loginPromiseNew permanently pending。**所有 page 的 `app.loginPromiseNew.then(...)` 永远不跑且 catch 接不住 pending**。一周内全局 latent。

6. **微信 prepay 申请失败 PrepayId=null**：常见原因 out_trade_no 重复、open_id 跟 appId 不匹配、amount=0。`TenpayController.cs:130` 在 PrepayId 检查前调 GenerateParameters 是 latent crash bug。移到 if 内 + log response JSON 让微信侧拒绝原因（errcode/errmsg）能在 prod 日志直接看到。

7. **`WechatPayByOrderPayment` 三个 if 分支（1551/1560/1595）都不命中时**：PaymentIdentity 已 pre-set op.member_id 且 open_id 对得上时,用 DB 里旧的 out_trade_no 申请 prepay → 微信判重复。**修复：line 1611 调 TenpayRequest 前无条件刷新 out_trade_no**。

8. **DB 直接 SQL 是最快的诊断工具**：本日用户用 `SELECT * FROM member_social_account WHERE member_id BETWEEN 41084 AND 41095` 一秒钟看穿"MemberLogin 每次建 stub"的 root cause,比加任何代码诊断 log 都快。前端 console.log 适合 sanity check,DB SQL 适合验证 hypothesis 和发现 anomaly。

9. **scanner 优先原则**：当前 openid 已经有自己的 member,**永远用它**,绝对不要为了"合并到老会员"去迁移 openid/unionid MSA。"_invalidateMsa(scanner)" 是危险操作,会破坏用户已有的关联。

10. **用户原话拍板的架构原则比"看起来合理"的设计更可靠**：本日多次按"看起来合理"的设计走,被用户每次拍板修正。最终用户的"openid+unionid 只允许一个 member id + 点支付按钮才建会员 + scanner 优先"三条原则成为新架构的基础。
