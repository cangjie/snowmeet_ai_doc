# 2026-06-08 开单接待三处改进：手机号匹配会员回填 + 押金/租金弹窗自动清空 + 支付二维码状态实时显示

接续新版接待流程（`pages/admin/reception/`）。本场会话做了三件相对独立的事，前两件是纯前端小程序改动，第三件（支付状态实时显示）是前后端 + 生产库加列的完整切片（用户选「方案 A」）。

## 1. 手机号匹配会员 → 自动回填姓名/性别（recept_entry）

### 1.1 需求与实现

- 开单第一步页面 [recept_entry](../snowmeet_wechat_mini/pages/admin/reception/recept_entry.js) 输入手机号，匹配到会员就自动填姓名 + 性别。
- 复用后端 `Member/GetMemberByNum/{cell}`（返回 `Member`，字段 `real_name` / `gender` / `id`）。
- data.js 新增**静默版** `getMemberByNumSilentPromise`：匹配 resolve(member)，查不到 / 无权限 / 网络错都 resolve(null) 且**不弹 toast**。
  - **Why 不直接用现成的 `getMemberByNumPromise`**：它走 `performWebRequest`，后端「会员不存在」(code=1) 会 `wx.showToast`。接待散客大量是非会员，边输入边查会对每个非会员号码弹一次「会员不存在」，太吵。
- recept_entry.js：`onCellInput` 防抖 450ms + 去重（`_lastLookupCell`）触发；匹配后覆盖 `customerName`/`gender`（仅在档案有值时覆盖，空值不清掉已填内容）+ 轻提示「已匹配会员信息」+ 刷 `customerReadyForService`。
- 触发门槛 `shouldLookupPhone`：国内 11 位手机号，或 `+` 开头 E.164；避免国内号码输到 7~10 位（`isValidInternationalPhone` 已 true）就反复查。抽出 `normalizePhone` 复用。

### 1.2 真机问题：入口页没回填、下一页却匹配到会员

- 现象：输 `18601197897` 入口页没回填，但下一页 member-bar 显示「会员」。
- **根因 = 登录竞态**。`app.globalData.sessionKey` 是 `loginPromiseNew`（`wx.login` + `MemberLogin` 网络往返）异步写入的（[app.js:142](../snowmeet_wechat_mini/app.js#L142)）。入口页是落地首页、**自己没 await 登录**；落地后立刻输号码（尤其粘贴）时 sessionKey 还是空 → 后端 `GetStaffBySessionKey('')` 判无权限 → 返回 null → 不回填。下一页 [recept_new.js:50](../snowmeet_wechat_mini/pages/admin/reception/recept_new.js#L50) `await app.loginPromiseNew` 后才查，所以能命中。
- 修复：`tryMatchMemberByCell` 改为 `Promise.resolve(app.loginPromiseNew).then(() => getMemberByNumSilentPromise(...))`，等登录完成再查。
- 另埋诊断：命中会员但 `real_name`/`gender` 均为空时打 `console.warn`，便于区分「登录竞态」vs「会员档案本身没名字」——**待用户重测定性**。
- 注意 member-bar 显示的名字是父页传入的 `customer.name`，它自己只把头像标记翻成「会员」，**不显示会员档案真名**；onMemberInfoFound 只 set memberId，不回填 name。

## 2. 押金/租金修改弹窗：点开自动清空（rent_recept_form）

- 「修改押金」「修改租金/日」用的是**自定义 modal**（`amountModal`，非 `wx.showModal`——为支持带小数点的 `type="digit"` 数字键盘）。
- 原来 `onPkgDepositTap`/`onPkgRateTap` 把当前值预填进 `amountModal.value`，要手删。
- 改：`value: ''`（打开即空，`focus` 已自动聚焦弹键盘），当前值改放 placeholder「原 ¥xxx」作参照。
- `onAmountModalConfirm`：输入留空 = 不修改，直接关弹窗、不报错（避免点开看一眼又不改时弹「请输入有效金额」）；输 `0` 仍有效。
- 没用「聚焦时清空」方案：反复点输入框会误删，且 `<input>` 没有可靠全选接口。仅改了新版 reception，旧版 recept 同类弹窗未同步（用户可选）。

## 3. 支付二维码状态实时显示（方案 A，前后端 + 加列）

### 3.1 现状与卡点

- [order-payment](../snowmeet_wechat_mini/components/order-payment/index.js) 原本只 `pending → paid` 两态，靠一条 WebSocket 长轮询 `paymentpaid` 死等支付成功（[Util.cs:478](../SnowmeetApi/Util.cs#L478) → `OrderController.QueryPaymentPaid` 每秒查 status 的长轮询）。
- 中间没有「已扫码」信号，**根因 = 顾客扫码打开支付页时后端 `GetOrderFromPaymentByCustomer` 只读不写**，没留痕迹。

### 3.2 能实时检测到的阶段（及判定依据）

| 阶段 | 文案 | 判定 |
|---|---|---|
| waiting | 等待扫码… | 待支付，无任何动作 |
| scanned | 顾客已扫码 | `customer_open_date` 已落戳（顾客打开了支付页） |
| paying | 顾客支付中… | `submit_time` / `prepay_id` / `open_id` 已写（顾客点支付、发起预支付） |
| paid | 已收款 | `status=支付成功` |
| cancelled | 支付已取消 | `valid=0` 或 `status=取消` |

- 验证过：出码接口 `GetWepayPayment`（[1430](../SnowmeetApi/Controllers/OrderController.cs#L1430)）/ `GetAlipayMiniPayment`（[1722](../SnowmeetApi/Controllers/OrderController.cs#L1722)）建单时都**不写** `submit_time`/`open_id`/`prepay_id`，所以「paying」对微信/支付宝都不会一出码就误判。`submit_time` 已被「向网关发起 prepay」占用（TenpayController:156 / AliController:518 / OrderController:1926），不能拿来当「已扫码」，故新加列。

### 3.3 改动

**后端**（编译 0 错误，分支 `ai`）：
- [OrderPayment.cs](../SnowmeetApi/Models/Order/OrderPayment.cs)：新增 `customer_open_date`（`DateTime?`）列。
- `GetOrderFromPaymentByCustomer`（[2410](../SnowmeetApi/Controllers/OrderController.cs#L2410)）：顾客首次打开支付页且待支付时落 `customer_open_date = DateTime.Now`（单独 tracked 查一次只更这字段）。
- 新增只读 `GetPaymentLiveStatus/{paymentId}`（店员鉴权 `title_level>=100`），返回 `{ paymentId, stage, status, paid }`。

**前端**：
- [data.js](../snowmeet_wechat_mini/utils/data.js)：新增静默 `getPaymentLiveStatusPromise`（高频轮询不弹 toast）。
- order-payment [index.js](../snowmeet_wechat_mini/components/order-payment/index.js)：出码后每 **2s 轮询**刷新 `payStage`/`payStageLabel`；**WebSocket 仍负责支付成功收尾**，与轮询经 `_paidHandled` 去重（任一先到都不重复 `triggerEvent('paid')`，轮询 paid 分支兜底再拉一次订单）；`onMethodTap`/`detached` 复位与清理。
- index.wxml/wxss：四态分色 +「已扫码/支付中」带脉冲小圆点。

### 3.4 ⚠️ 上线顺序（关键，已交代用户）

EF 模型加 `customer_open_date` 后，**所有 `order_payment` 查询都会 SELECT 这一列**。必须**先在生产库 `snowmeet_new` 跑 ALTER、再部署后端**，否则列不存在 → 全部支付查询报「无效列名」挂掉：

```sql
ALTER TABLE order_payment ADD customer_open_date datetime NULL;
```

小程序端可独立发布——后端没上前轮询拿不到就静默返回 null，状态停在「等待扫码」，不报错。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [pages/admin/reception/recept_entry.js](../snowmeet_wechat_mini/pages/admin/reception/recept_entry.js) | 手机号防抖查会员（await 登录）+ 回填姓名/性别 + normalizePhone/shouldLookupPhone |
| [utils/data.js](../snowmeet_wechat_mini/utils/data.js) | 新增 `getMemberByNumSilentPromise`、`getPaymentLiveStatusPromise`（均静默） |
| [components/reception/rent_recept_form/rent_recept_form.js](../snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.js) | 押金/租金弹窗 value 改空 + 当前值进 placeholder + 留空不报错 |
| [components/order-payment/index.{js,wxml,wxss}](../snowmeet_wechat_mini/components/order-payment/index.js) | 四态实时轮询 + markPaid 去重 + 脉冲圆点 |
| [SnowmeetApi/Models/Order/OrderPayment.cs](../SnowmeetApi/Models/Order/OrderPayment.cs) | 新增 `customer_open_date` 列 |
| [SnowmeetApi/Controllers/OrderController.cs](../SnowmeetApi/Controllers/OrderController.cs) | 落扫码戳 + 新增 `GetPaymentLiveStatus` 接口 |

## 学到的小知识

1. **入口/落地首页用 `app.globalData.sessionKey` 前必须 `await app.loginPromiseNew`**：登录是异步网络往返，落地页若不等就用 sessionKey，会拿到空串 → 后端判无权限。下游页面（recept_new）已等，入口页之前漏了。
2. **EF Core 加可空列必须先 ALTER 生产库再部署**：EF 按属性生成 `SELECT col`，列不存在则该表所有查询全挂。部署顺序：先 DDL，后发后端。
3. **静默查询要绕开全局 `performWebRequest`**：它在 code!=0 时一律 `wx.showToast`，不适合「非命中是常态」的高频/边输入场景（会员匹配、状态轮询），改用裸 `wx.request` 自行 resolve(null)。
4. **`OrderPayment.submit_time` 语义 = 已向网关发起 prepay**，非「已扫码/已查看」；想表达「顾客已打开支付页」要另加 `customer_open_date`。`submit_time`/`prepay_id`/`open_id` 在出码（GetWepayPayment/GetAlipayMiniPayment）时都不写，是干净的「顾客已点支付」信号。
5. **自定义金额弹窗自动清空**：开局 `value:''` + 当前值进 placeholder，比「聚焦时清空」更稳（避免反复点输入框误删，且 `<input>` 无可靠全选 API）。
