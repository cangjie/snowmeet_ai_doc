# 2026-05-30 接待表单收尾 + choose_identity 软授权对齐 + alipay Phase A 暂搁置 + beacon_scan 落地

本场会话四条主线：① 接待表单两处小迭代（去结算每次建新订单 / 押金租金 modal 数字键盘）；② `choose_identity` 状态的软授权流程对齐 `direct_to_scanner`，前后端各反复一轮；③ 启了一个支付宝小程序 `alipay_snowmeet` 落地的 4 阶段计划，Phase A 后端 3 接口落工作区编译通过后因支付宝注册授权未到位**暂时搁置**；④ 新建 `pages/blt/beacon_scan` 蓝牙 Beacon 扫描页，iOS+Android 双路径并行。

---

## 1. 接待表单收尾两处

### 1.1 「去结算」每次新建订单（不复用旧 OrderPayment）

**问题**：用户反馈，第一次去结算后再回到购物车点「去结算」，**给同一订单累加 OrderPayment** 而不是新建订单 —— 不符合业务预期。

**根因**：[recept_new.js:onCheckout](snowmeet_wechat_mini/pages/admin/reception/recept_new.js) 调 `PlaceRentOrder/{order.id}` 用的是当次本地 `order.id`。一次下单后 `valid=1`，但购物车依旧绑这个 id，再次结算时:
- `saveRentReceptOrder` 用 `valid:0` 把 placed order 倒回未下单
- 再调 `PlaceRentOrder` 把同一订单重置 valid=1（甚至重新生成 code）
- 结算页 `GetWepayPayment/{id}` 在该订单上 append 新 OrderPayment

**修法**：`PlaceRentOrder` 成功 + `navigateTo` 之后，立刻把本地 `order` 脱钩：
```js
this.setData({ order: {
  ...rentOrder, id: 0, code: null, valid: 0,
  rentals: (rentOrder.rentals || []).map(r => ({
    ...r, id: 0, order_id: 0,
    rentItems: (r.rentItems || []).map(ri => ({ ...ri, id: 0, rental_id: 0 }))
  }))
}})
```
下次 `saveRentReceptOrder` 因为 `id=0` 会被后端当新单插入，再次 `PlaceRentOrder` 在新 id 上。即使用户回到购物车再编辑触发 `onSyncRent → save`，也走新订单，不再回写已下单的旧订单。

### 1.2 押金/租金 modal 改 type=digit 数字键盘

**问题**：原来用 `wx.showModal({editable: true})` 弹输入框，系统原生只能给字符键盘，**没法切到带小数点的数字键盘**。

**修法**：替换成自建 `van-popup` + `<input type="digit">`：

- [rent_recept_form.js](snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.js) 加 `data.amountModal = {show, title, placeholder, value, ridx, field}`，`onPkgDepositTap` / `onPkgRateTap` 改成 `setData({amountModal: {...}})` 开 popup
- 新增 `onAmountModalInput / Cancel / Confirm` 三个 handler
- 二次确认（"押金将修改为 ¥xxx，是否确认？"）仍走 `wx.showModal`，UX 保持
- [rent_recept_form.wxml](snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.wxml) 末尾加 `<van-popup>` 块 `<input type="digit">`（iOS 原生带小数点）
- [rent_recept_form.wxss](snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.wxss) 加 `.amount-modal*` 样式

---

## 2. choose_identity 状态软授权对齐 direct_to_scanner（前后端各反复一次）

### 2.1 第一轮：gate 卡片，错的

**用户反馈截图**：新单匹配到会员"苍杰(个人) 186****7897"，扫码方未绑手机号，但前端只显示「正常支付 / 替人代付」两按钮，没引导手机号验证。要求：**对齐 `direct_to_scanner` 已经测过的软授权流程**。

**我的初版**（错）：在 `pay-identity-confirm/index.wxml` 加了一个独立的 gate 卡片，把原本的「正常支付 / 替人代付」按钮**挤掉**，显示「授权手机号 / 跳过」让用户先过 gate 再进选身份。

**用户怒（原话）**："操你妈，你Y是不是脑子进水了！按钮怎么改成这样了？……保留正常支付/替人代付不变，**点按钮的瞬间**才判定 scannerHasCell，参考昨天测过的 direct_to_scanner 流程"。

### 2.2 第二轮：按钮内联 open-type=getPhoneNumber

**正确的做法**：保留 `choose_identity` 卡片文案/布局**完全不变**（"本订单已记录会员 xxx，您与该会员未匹配，请选择支付身份" + 两按钮），仅按钮事件对齐 `direct_to_scanner` 的「确认并继续」模式：

```xml
<!-- 正常支付：无 cell → getPhoneNumber 触发软授权 -->
<button wx:if="{{!result.scannerHasCell}}"
        open-type="getPhoneNumber"
        bindgetphonenumber="onGetPhoneNumberAndChooseSelf">正常支付</button>
<button wx:else bindtap="onChooseSelf">正常支付</button>
```

- `onGetPhoneNumberAndChooseSelf`：用户同意 → `_submitPhoneThenChoose(encData, iv, 'self')` 链式跑 submit_phone + choose:self；用户拒绝 → fallback 直接 `_confirm({choose:'self'})`
- `onGetPhoneNumberAndChooseProxy`：先弹微信原生授权 → 弹「替人代付」二次确认 modal → 同意+确认 → `_submitPhoneThenChoose(..., 'proxy')`；拒绝授权 → modal 确认后 `_confirm({choose:'proxy'})`
- 新 helper `_submitPhoneThenChoose(encData, iv, choice)` 与现有 `onGetPhoneNumberAndConfirmDirect` 的双 Promise 链同构

`payment_entry.js` 的 `onIdentityRefreshed` 收到 `status='direct'` 已经能自动 `_doWepay()`，组件 triggerEvent 即可，父页不动。

### 2.3 第三轮（真槽点）：后端 `_applyChoice` 拒绝建游客会员，toast「扫码方尚未注册会员」

用户测试后再骂："出现这种现象，是我之前没描述清楚吗？"

**根因**：扫码方是游客（`MemberLogin` 2026-05-29 起不再建 stub），`scannerMemberId == null`。用户点「正常支付」→ 按钮弹微信手机号授权 → **拒绝** → 前端 fallback 调 `_confirm({choose:'self'})` → 后端 `_applyChoice` 在 [PaymentIdentityController.cs:383](SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) 直接抛 `"扫码方尚未注册会员，请先验证手机号"`。

对比 `_applyConfirmDirect` [PaymentIdentityController.cs:437-459](SnowmeetApi/Controllers/Order/PaymentIdentityController.cs)：在 `scannerMemberId == null` 时用 `_loadSessionContext(sessionKey)` 反查 openid+unionid → `_createNewMember(phone:null, ...)` 自动建无 cell 游客会员 → 继续走 confirm_direct。**这是「昨天测过的流程」的后端兜底层**，我上一轮只镜像了前端按钮模式，没镜像后端这块兜底。

**修法**：在 `_applyChoice` 顶部加上**同样的**自动建会员代码块（10 行代码与 `_applyConfirmDirect` 完全镜像），用户拒绝授权后端自动建游客会员 → 继续 choose:self/proxy → `status='direct'` → 自动支付。

---

## 3. alipay_snowmeet 4 阶段计划 + Phase A 落地（搁置）

### 3.1 4 阶段计划设计

用户在当前目录下新建了支付宝小程序 `alipay_snowmeet/`（空白模板），要求做对标微信端 `pages/order/payment_entry` 的「顾客扫店员二维码支付落地页」。后端 `PaymentIdentityController` 决策架构本来就是 payerType-agnostic（`_msaTypeForPayer("alipay")=alipay_payerid`、`_resolveStatus` 走 `session_type='alipay_payerid'`、`_createNewMember` 通用），缺的是入口/出口的 3 个 alipay 专属接口 + 整个小程序工程骨架。

用户拍板拆 4 阶段：

| 阶段 | 内容 |
|---|---|
| A | 后端 3 接口：`MemberLogin` alipay 分支 / `AlipayPayByOrderPayment` / `_extractPhone` alipay 真实化 |
| B | 小程序骨架：`app.json` + `app.js` 登录 + `utils/util.js` + `utils/data.js` |
| C | `payment_entry` 页 + `pay-identity-confirm` 组件 |
| D | wechat 端把支付宝 mock 二维码替换成真实小程序唤起 URL |

**关键决策**：小程序 appId `2021006157678375`（独立于商户 appId `2021004143665722`）；MSA type `alipay_payerid`；MiniSession.session_type `alipay_payerid`；sessionKey 装 alipay `access_token`。

完整计划已落 [`~/.claude/plans/y-luminous-hammock.md`](file:///Users/cangjie/.claude/plans/y-luminous-hammock.md)。

### 3.2 Phase A 落地：3 接口 + 1 model getter

**5 个改动**：

1. [`Models/Member/Member.cs`](SnowmeetApi/Models/Member/Member.cs) — 加 `alipayPayerId` getter（GetInfo("alipay_payerid")，与 `wechatMiniOpenId` 同模式）
2. [`Controllers/MiniAppHelperController.cs`](SnowmeetApi/Controllers/MiniAppHelperController.cs):
   - `MemberLogin(code, openIdType)` 顶部加 `if (openIdType == "alipay_payerid") return await _alipayMemberLogin(code)` 分流
   - 新增 `_alipayMemberLogin`：`AlipaySystemOauthTokenRequest` 换 (`access_token`, `user_id`) → MSA 反查会员（不建 stub）→ 写/更新 MiniSession `session_type='alipay_payerid'`, `wechat_openid` 列复用存 `user_id` → 返 Code2Session
   - 新增 `_getAlipayMiniClient()` 用小程序 appId 证书目录加载 `IAopClient`
3. [`Controllers/OrderController.cs`](SnowmeetApi/Controllers/OrderController.cs):
   - 新增 `AlipayPayByOrderPayment(int paymentId, string sessionKey)`：sessionKey 反查会员（`alipay_payerid` 通道）→ 3 分支 op 字段补写（首次 / 换人 / `ali_buyer_id` 不匹配）→ 用小程序 appId client 调 `alipay.trade.create` → 落库 `ali_trade_no` 返前端
   - 新增 `_getAlipayMiniClientForOrder()`（与 PaymentIdentity 那个同代码，跨控制器避免循环依赖各自维护）
4. [`Controllers/Order/PaymentIdentityController.cs`](SnowmeetApi/Controllers/Order/PaymentIdentityController.cs):
   - `_extractPhone` alipay 分支真实化 + 加 `_loadAlipayAesKey` helper
   - `ConfirmPayIdentityBody` 字段语义更新
   - `_applyChoice` 加游客会员兜底（见 §2.3，本场顺手完成）
5. 编译修：`using Aop.Api.Domain;` 在 OrderController 里和 `SnowmeetApi.Models.Member/Shop/Product` 撞名 → 删 using、`AlipayTradeCreateModel` / `ExtendParams` 加完全限定名 `Aop.Api.Domain.xxx`

**编译验证**：`dotnet build` 通过，0 error 0 warning。

### 3.3 关键偏离：手机号解密换路径

原计划用户选了「client 仅拿 auth_code → 后端调 `alipay.user.phone.get`」，但落地时发现 **`AlipaySDKNet.Standard 4.8.50` + `AlipaySDKNet.OpenAPI 2.4.0` 都不暴露 `AlipayUserPhoneGet*` 类**（`strings` 扫了两个 DLL 验证）。手写 `IAopRequest<T>` 实现要赌 SDK 内部接口签名，太脆。

切到 alipay 标准的客户端加密路径：
- 客户端 `my.getPhoneNumber()` 返 `response`（AES-128-CBC + 全 0 IV + PKCS7 加密 JSON）
- 服务端用「接口加密方式」配置的 AES 密钥解密（base64，16/24/32 字节）
- 复用现有 [`Util.AES_decrypt`](SnowmeetApi/Util.cs)（wechat 通道也是这一套）
- 加 `_loadAlipayAesKey()` 从 `AlipayCertificate/2021006157678375/aes_key.txt` 读

### 3.4 暂搁置：支付宝注册授权未到位

用户："因为支付宝注册授权的问题，这个计划暂时搁置！"

**Phase A 代码已落工作区（SnowmeetApi/* 5 个文件改动），未 commit**。等支付宝那边小程序 appId 注册 + 证书签发 + AES 密钥配置 + 「获取会员手机号」能力开通到位再恢复 Phase B-D。

**部署清单**（运维侧给到才能真跑）：
- `SnowmeetApi/AlipayCertificate/2021006157678375/` 放 4 个文件：`private_key_2021006157678375.txt` / `appCertPublicKey_2021006157678375.crt` / `alipayCertPublicKey_RSA2.crt` / `alipayRootCert.crt`
- 同目录加 `aes_key.txt`（开放平台「接口加密方式」生成的 AES 密钥 base64）
- 开放平台开通：JSAPI 支付能力 + 获取会员手机号能力

---

## 4. pages/blt/beacon_scan 新页落地（含 iOS 支持）

### 4.1 需求 & 项目现状

用户："微信小程序当中，需要增加个界面，获取附近的蓝牙beacon的ID和信号强度，需要实时获取。"

摸了一圈现状：
- `pages/blt/open_lock` 是平铺结构（不是子目录），用 `wx.openBluetoothAdapter` + `wx.startBluetoothDevicesDiscovery`
- `utils/util.js:337` 有 `getBLEDeviceNameListInRangePromise` 通用 BLE 入口
- 没有现成的 beacon 解析代码

### 4.2 初版：单路径（仅 BLE 通用扫描）

**[pages/blt/beacon_scan.{js,wxml,wxss,json}](snowmeet_wechat_mini/pages/blt/) 4 文件 + app.json 注册**：

- 用 `wx.startBluetoothDevicesDiscovery({allowDuplicatesKey: true, powerLevel: 'high'})` —— `allowDuplicatesKey` 关键，不开则同一设备只回调一次拿不到 RSSI 实时刷新
- `wx.onBluetoothDeviceFound` 注册回调，每次拿到设备列表就更新内部 `_devicesMap`（用实例字段而非 `data` 避免 setData 开销）
- iBeacon 广播在 `device.advertisData` 段（ManufacturerData），按 `4C 00 02 15` 前缀识别 → 切 UUID(16B) / major(2B) / minor(2B) / txPower(1B signed)
- **200ms setData 节流**：`onBluetoothDeviceFound` 一秒回调几十次，直接 setData 会卡死，用 `_scheduleRender + _renderTimer` 合并
- 按 RSSI 降序排（强信号在前），缺失值丢底部
- 「仅显示 iBeacon」开关过滤掉普通 BLE 设备

UI：4 格信号柱（按 RSSI 分档 ≥-55/≥-70/≥-85/≥-100）+ deviceId monospace + iBeacon block（UUID/Major/Minor/TX，点 UUID 复制剪贴板）

### 4.3 用户问"支持苹果吗" → 加 iOS 路径

**iOS 拿不到 iBeacon 数据的原因**：Apple CoreBluetooth 框架系统层主动过滤掉 iBeacon 格式的 ManufacturerData（Apple 把 iBeacon 划在 CoreLocation API 名下），通用 BLE 扫描拿到的 `advertisData` 里**没有那 25 字节**。微信小程序底层包了 CoreBluetooth，绕不过这个限制。

**修法：双路径并行**：

| 路径 | API | 两平台 | 关键约束 |
|---|---|---|---|
| A 通用 BLE | `wx.startBluetoothDevicesDiscovery` + `wx.onBluetoothDeviceFound` | iOS✅ Android✅ | iOS 上 advertisData 不含 iBeacon manufacturer 数据 |
| B CoreLocation | `wx.startBeaconDiscovery({uuids})` + `wx.onBeaconUpdate` | iOS✅ Android✅ | **必须事先知道 UUID**（Apple 平台硬约束）|

**Dedup 策略**：iBeacon 在 `_devicesMap` 里用 `iBeacon:UUID:major:minor` 作 key，A、B 两路径合并到**同一行**：
- A 路径：`parseIBeacon(advertisData)` 成功 → key 用 iBeaconKey；txPower 来自 A
- B 路径：直接拿 `{uuid, major, minor, rssi, accuracy, proximity}` → 同 key；accuracy/proximity 来自 B
- 合并字段时保留对方独有的（A 的 `txPower` / B 的 `accuracy + proximity` 互不覆盖）
- `source` 字段标记 `'A' | 'B' | 'both'`，UI 上显示来源 tag（灰/紫/绿）

**UI 加项**：
- 顶部加 UUID textarea（多行，换行/逗号分隔），右上角实时显示「N 个有效」（用 `parseUuids` regex `/^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$/`）
- error-bar 旁加 warn-bar（黄底，软提示用，区别红底 error）
- iBeacon block 第三行：距离（accuracy 米）+ 远近（proximity 中文：极近/近/远/未知）+ 来源 tag

**默认 UUID**：业务侧指定，开页就预填好（两个，换行分隔，textarea 默认 `validUuidCount=2`）：
- `01122334-4556-6778-899A-ABBCCDDEEFF0`（原始 32 hex `0112233445566778899AABBCCDDEEFF0`）
- `01122334-4556-6778-899A-ABBCCDDEEFF1`（原始 32 hex `0112233445566778899AABBCCDDEEFF1`）

### 4.4 入口

注册到 `app.json` `pages` 数组（紧跟 `pages/blt/open_lock`）。导航入口暂时让用户自己加：`wx.navigateTo({ url: '/pages/blt/beacon_scan' })`。

---

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.js` | `onCheckout` 成功后立刻 reset 本地 order（id/code/valid 清零、rentals/rentItems id 清零）— 每次结算建新订单 |
| `snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.{js,wxml,wxss}` | 押金/租金 modal 从 `wx.showModal({editable:true})` 改自建 `van-popup` + `<input type="digit">`（小数点数字键盘）|
| `snowmeet_wechat_mini/components/pay-identity-confirm/index.{js,wxml}` | choose_identity 卡片两按钮按 `!scannerHasCell` 分流：无 cell 时改 `open-type="getPhoneNumber"` + 新 handler `onGetPhoneNumberAndChooseSelf/Proxy`；helper `_submitPhoneThenChoose` 与 `onGetPhoneNumberAndConfirmDirect` 同构 |
| `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs` | `_applyChoice` 加 scannerMemberId==null 兜底（自动建无 cell 游客会员）；`_extractPhone` alipay 真实化（AES 解密 my.getPhoneNumber 加密 response）；`_loadAlipayAesKey` helper；`ConfirmPayIdentityBody.encData/iv` 语义注释更新 |
| `SnowmeetApi/Models/Member/Member.cs` | 加 `alipayPayerId` getter（对标 `wechatMiniOpenId`，GetInfo("alipay_payerid")）|
| `SnowmeetApi/Controllers/MiniAppHelperController.cs` | `MemberLogin` 顶部分流 alipay 通道；新增 `_alipayMemberLogin`（oauth.token + MSA 反查 + MiniSession 写入）+ `_getAlipayMiniClient` |
| `SnowmeetApi/Controllers/OrderController.cs` | 新增 `AlipayPayByOrderPayment`（对标 `WechatPayByOrderPayment`，3 分支 op 字段补写 + `alipay.trade.create`）+ `_getAlipayMiniClientForOrder`；删 `using Aop.Api.Domain;` 避命名冲突 |
| `snowmeet_wechat_mini/pages/blt/beacon_scan.{js,wxml,wxss,json}` | 新建蓝牙 Beacon 扫描页（4 文件），双路径并行 + iBeacon dedup by `iBeacon:UUID:major:minor` |
| `snowmeet_wechat_mini/app.json` | 注册 `pages/blt/beacon_scan` |
| `~/.claude/plans/y-luminous-hammock.md` | 落 alipay 4 阶段计划 |

---

## 学到的小知识

1. **alipay 小程序 SDK 4.8.50 + OpenAPI 2.4.0 都不暴露 `AlipayUserPhoneGet*`**：朝 `alipay.user.phone.get` 这条路走得 SDK 支持，否则只能手写 `IAopRequest<T>` 实现（赌 SDK 内部接口签名，太脆）。客户端 `my.getPhoneNumber` + 服务端 AES 解密是 alipay 小程序拿手机号的事实标准路径，所有 SDK 版本都支持。

2. **`_applyChoice` 跟 `_applyConfirmDirect` 兜底逻辑必须对齐**：两者都是 ConfirmPayIdentity 的子 handler，都需要在 `scannerMemberId == null` 时自动建无 cell 游客会员（用 sessionKey 反查 openid+unionid → `_createNewMember(phone=null, ...)`），否则游客拒绝手机号授权后会被 toast 拦下。这是 2026-05-29 删 MemberLogin stub 后的后端责任迁移。

3. **iOS 的 CoreBluetooth 系统层过滤 iBeacon 广播数据**：通用 BLE 扫描（`wx.startBluetoothDevicesDiscovery`）拿到的 `advertisData` 里 iOS **不带 Apple 厂商 ID 那 25 字节**。要让 iOS 识别 iBeacon 必须用 `wx.startBeaconDiscovery({uuids})` 走 CoreLocation 路径，且 **uuids 必填**（Apple 平台硬约束，不知道 UUID 没法扫）。

4. **iBeacon 广播 ManufacturerData 格式（25 字节定长）**：
   ```
   bytes 0-1   : 4C 00     Apple Company ID（小端）
   byte  2     : 02        iBeacon 类型
   byte  3     : 15        后续长度 = 21
   bytes 4-19  : UUID      16 bytes
   bytes 20-21 : major     big-endian
   bytes 22-23 : minor     big-endian
   byte  24    : txPower   signed int8（校准 1m 处的 RSSI）
   ```
   Eddystone 在 ServiceData 段而非 ManufacturerData，需要另接口（本页不支持）。

5. **`wx.startBluetoothDevicesDiscovery` 的 `allowDuplicatesKey:true` 必须开**：不开则同一设备只回调一次，拿不到 RSSI 持续刷新。Beacon 测距/定位场景的硬要求。文档警告说会增加 CPU/内存负担 —— 对手动扫描场景可控。

6. **`onBluetoothDeviceFound` 回调高频（一秒几十次）必须节流 setData**：直接 setData 会让 UI 卡死。用 `_renderTimer + _scheduleRender` 合并到 200ms 一次刷新（同时不用 `data` 存 `_devicesMap`，挂实例字段绕过 diff 开销）。

7. **微信小程序 `wx.showModal({editable:true})` 不支持 type=digit 数字键盘**：系统原生输入框只能给字符键盘，想要带小数点的数字键盘必须改自建 `van-popup` + `<input type="digit">`。

8. **WeChat 小程序 `app.json` `pages` 数组里平铺路径和子目录都行**：`pages/blt/open_lock`（平铺）和 `pages/admin/sale/shop_sale`（子目录）混用。新页面跟着附近邻居的风格走最省事。

9. **WeChat 小程序开发者工具模拟器没蓝牙**：beacon_scan / open_lock 这类页面必须真机调试（手机连开发者工具或扫预览码）。Android 6.0+ BLE 扫描还需要定位权限（微信会自动弹）。

10. **alipay 小程序「接口加密方式」的 AES 配置**：在开放平台后台生成 base64 编码的 AES 密钥（16/24/32 字节），客户端 `my.getPhoneNumber` 返的 `response` 用这个密钥 AES-128-CBC + PKCS7 + 全 0 IV 加密 JSON。复用 wechat 通道的 `Util.AES_decrypt(data, key, "AAAAAAAAAAAAAAAAAAAAAA==")` 就行。
