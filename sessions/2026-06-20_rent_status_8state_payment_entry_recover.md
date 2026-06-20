# 2026-06-20（续2） 租赁状态机8态 + payment_entry 修复 + CloseOrder 加固 + 找回中断订单

接续上次 context 满截断的会话（8 态状态机实际已在上次落地）。本场补充：解答 `closed=1` 在哪里更新，修 payment_entry 日租金/总计显示为 0 的 bug，加固 CloseOrder 不误关订单，以及实现"业务开单"页的"找回中断的订单"功能。改动跨 `SnowmeetApi` 和 `snowmeet_wechat_mini`，**代码仓本地未提交，用户按部署节奏处理**。

---

## 1. 背景：为什么 WT_ZL_260619_00008 显示"租赁中"（承上次）

**问题根因**（上次已解决）：旧状态机以 `realStartDate`（由 RentItemLog 发放事件推算）作为"已开始"判断，¥0 订单或未付款订单也能触发"租赁中"，与付款状态完全脱钩。

**解决方案**：重写 `Order.rentProperties` 为完整 8 态状态机：
1. 了结关闭（`closed=1`，最高优先）
2. 未支付（`paying_amount>0 && paidAmount==0`）
3. 未开始（付款后，`start_date` 还在未来）
4. 租赁中（所有 rentItem 已发放或 noNeed=true，settled=0）
5. 部分归还
6. 全部归还
7. 部分退押金
8. 全额退押金

---

## 2. `closed=1` 在哪里更新

**用户问题**：`order.closed` 更新成 1 的位置？

**结论**：对新 `order` 表，唯一入口是 `RentController.CloseOrder()`（`GET /api/Rent/CloseOrder`）。分两个分支：

| 分支 | 条件 | 行号 |
|------|------|------|
| 废单立即关闭 | `availablePayments.Count <= 0 && paying_amount > 0` | 原 5785 |
| 正常结案关闭 | `allSettled && totalRentUnRefund ≈ 0` | 5815 |

旧表（`rent_list`/`RentOrder`）有 3 处额外赋值（1248/1255/3332），与新流程无关。

---

## 3. `CloseOrder` 加固（不误关订单）

**改动**：[`RentController.cs`](../SnowmeetApi/Controllers/RentController.cs)

### 3.1 废单分支加 `paying_amount > 0` 守卫

**之前**：`availablePayments.Count <= 0` → 立即 `closed=1`，¥0 订单（`paying_amount=0`）也被关

**之后**：只有 `availablePayments.Count <= 0 && paying_amount > 0` 才立即关（真正的废单），¥0 订单跳过此分支进入完整检查

### 3.2 主流程加 `paymentFulfilled` 校验

新增条件：`Math.Round(paidAmount - paying_amount, 2) == 0`，即"应付金额 = 实付金额"才允许关单

三个保护条件并列（全满足才 `finished=true`）：
1. `allSettled`（无未退租）
2. `paymentFulfilled`（应付=实付）**← 新增**
3. `totalRentUnRefund ≈ 0`（应退押金为0）

---

## 4. `payment_entry` 日租金/总计修复

**问题**：顾客扫码付款页（`pages/order/payment_entry`）中：
- 日租金显示 ¥0.00：`rental.totalRentalAmount` 从 `rental_detail` 累计，付款前没有计费明细，所以为 0
- 总计显示 ¥0.00：用了 `order.total_amount`（DB 字段），租赁订单这个字段未被设置（恒为 0）

### 4.1 后端：`GetOrder` 加 pricePresets Include

[`OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) 第 68 行，租赁查询加：
```csharp
.Include(r => r.pricePresets)
```
之前 `appendingRentals` 有 include，正式 `rentals` 漏掉了。

### 4.2 前端：`payment_entry.js renderData`

[`pages/order/payment_entry.js`](../snowmeet_wechat_mini/pages/order/payment_entry.js)

**日租金**：遍历 `rental.pricePresets` 累加 `price - discount`，结果 > 0 时使用；否则退回 `totalRentalAmount`（兼容付款后已有明细的情况）

**总计**：改用 `order.paying_amount`（PlaceRentOrder 设置的押金总额），等于顾客本次实际要支付的金额

---

## 5. 找回中断的订单

### 5.1 背景

"业务开单"页（`pages/admin/reception/recept_entry`）底部"找回中断的订单"按钮 `onRecoverOrder` 是 `showToast('待实现')` 占位存根。

"中断的订单"= 工作人员已进入租赁开单页并添加了商品（触发 `Rent/SaveRentRecept`，创建 `valid=0, recepting=1` 订单），但未点"去结算"（`PlaceRentOrder` 从未调用）。

**后端已有**：
- `GET /api/Rent/GetReceptingOrders?shop=&sessionKey=` — 返回当天 `valid=0, recepting=1` 订单（含 member + staff），`data.js` 已封装 `getRentReceptingOrdersPromise`
- `GET /api/Rent/GetReceptingOrder/{id}` — 返回完整订单（含 rentals + pricePresets），`data.js` 已封装 `getRentReceptingOrderPromise`
- 新版 `reception/recept_new.js` 的 `saveRentReceptOrder` 已包含 `contact_name/contact_num/contact_gender` ✓
- 新版 `recept_new.js` `onLoad` 通过 `options.orderId` 加载并恢复顾客信息 ✓

### 5.2 旧版 saveReceptOrder 补 contact 字段

[`pages/admin/recept/recept_new.js`](../snowmeet_wechat_mini/pages/admin/recept/recept_new.js) `saveReceptOrder()`：新建订单（id=0）时补上：
```javascript
contact_name:   that.data.realName || null,
contact_num:    that.data.cell || null,
contact_gender: that.data.gender || null
```
之前缺失，旧流程中断的散客订单无顾客信息可显示。

### 5.3 recept_entry.js 实现

[`pages/admin/reception/recept_entry.js`](../snowmeet_wechat_mini/pages/admin/reception/recept_entry.js)：

- `data` 新增：`showRecoverPanel / recoverLoading / recoverOrders`
- `onRecoverOrder()`：显示 panel → 拉 `getRentReceptingOrdersPromise` → 对每条补 member 字段兜底 → 派生 `calledName`（姓名+性别称谓）+ `timeStr`
- `onRecoverOrderTap(e)`：关闭 panel → `wx.navigateTo('/pages/admin/reception/recept_new?orderId=XXX&bizType=rent&shop=XXX')`
- `onCloseRecoverPanel()`：关闭 panel

**重要**：跳转用 `orderId=`（非 `id=`），与新版 `recept_new.js onLoad` 中 `options.orderId` 对齐。

### 5.4 WXML/WXSS

[`recept_entry.wxml`](../snowmeet_wechat_mini/pages/admin/reception/recept_entry.wxml)：在根 `</view>` 前插入 `van-popup position=bottom`（70% 高度），内含 loading / 空态 / scroll-view 三态，每条显示 `calledName`、`contact_num`、`timeStr`。

[`recept_entry.wxss`](../snowmeet_wechat_mini/pages/admin/reception/recept_entry.wxss)：末尾追加 `.recover-panel` 系列样式。

---

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/OrderController.cs` | `GetOrder` 租赁查询加 `.Include(r => r.pricePresets)` |
| `SnowmeetApi/Controllers/RentController.cs` | `CloseOrder` 废单守卫 + `paymentFulfilled` 校验 |
| `snowmeet_wechat_mini/pages/order/payment_entry.js` | `renderData` 日租金用 pricePresets / 总计用 paying_amount |
| `snowmeet_wechat_mini/pages/admin/reception/recept_entry.js` | 实现 onRecoverOrder / onRecoverOrderTap / onCloseRecoverPanel；引入 util.js |
| `snowmeet_wechat_mini/pages/admin/reception/recept_entry.wxml` | 添加找回中断订单 van-popup 面板 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_entry.wxss` | 追加 .recover-panel 系列样式 |
| `snowmeet_wechat_mini/pages/admin/recept/recept_new.js` | saveReceptOrder 新建订单补 contact 三字段 |

## 学到的小知识

1. **payment_entry 的"日租金"和"总计"在开单时都是 0**：前者因为 `rental_detail` 计费明细在 `PlaceRentOrder` 后才生成，后者因为 `total_amount` DB 字段在租赁订单中未被赋值。正确来源：日租金 → `pricePresets[0].price`（开单时配置），总计 → `paying_amount`（PlaceRentOrder 写入的押金）
2. **`closed=1` 只有一个入口**：`RentController.CloseOrder` GET 接口，需手动/计划任务触发；旧 `rent_list` 表的赋值与新流程无关
3. **找回中断订单的完整基础设施已存在**：后端两个接口 + data.js 封装 + recept_new.js 恢复逻辑全都有，唯一缺的是 recept_entry.js 的 `onRecoverOrder` 实现
4. **新旧两版 recept_new.js 都要维护**：新版（`reception/`）saveRentReceptOrder 已含 contact 字段；旧版（`recept/`）saveReceptOrder 遗漏，两版都跑就要两版都改
