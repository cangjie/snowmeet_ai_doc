# 租赁订单详情页 rent_order_detail — 设计规格

**日期**：2026-06-13  
**设计基准**：`snowmeet_ai_doc/templates/rent/order_detail.html`  
**替换目标**：`pages/admin/rent/rent_details`（全量替换，旧页保留但不再维护）

---

## 1. 目标与范围

新建 `pages/admin/rent/rent_order_detail`（4 文件），采用 Alpine Operational Minimalist 风格（同 `pages/order/payment_entry`），完整实现租赁订单详情的**展示 + 操作**功能，替换旧 `rent_details` 页的所有入口。

不在范围内：
- 旧 `rent_details` 的删除（保留但停止维护）
- 养护/零售订单类型的详情（新页只处理租赁类型）

---

## 2. 文件结构

```
pages/admin/rent/rent_order_detail/
  rent_order_detail.js
  rent_order_detail.wxml
  rent_order_detail.wxss
  rent_order_detail.json
```

`app.json` 的 `pages` 数组中添加 `"pages/admin/rent/rent_order_detail/rent_order_detail"`。

---

## 3. 数据加载

### 3.1 入口参数
`onLoad(options)` 读取 `options.id`（orderId，数字字符串），保存至 `this.data.id`。

### 3.2 加载流程
```
onShow
  └─ await app.loginPromiseNew
       └─ getData()
            ├─ GET Order/GetOrderByStaff/{id}?sessionKey=...
            │    → 订单骨架（member、payments、rentals 基础信息）
            └─ 对每个 rental 并发 getRentalPromise(rental.id)
                 → rentItems、details 完整数据
            → 全部返回后 renderOrder(order)
            → setData({ order })
```

`getData()` 对 rentals 使用 `Promise.all`（而非串行）以加快加载。`getRentalPromise` 封装在 `utils/data.js`，已存在。

### 3.3 renderOrder()
沿用 `rent_details.js` 的派生逻辑，字段名保持原样（`rental.realGuaranty`、`rental.start_dateDateStr` 等），仅删除以下冗余分支：
- `appendingRentals` 分批加载逻辑（保留整块，仅清理无用 log）
- `checkAppendingRentalValid()` 保留（追加租赁校验需要）

派生补充：
- `order._memberTypeLabel`：`following_wechat == 1 ? '会员' : '散客'`
- 每个 rental：`_isPackage`（`rental.package_id != null`）、`_statusLabel`（根据 settled/rentItems 状态）
- 每个 rentItem：`_statusLabel`（未发放/已发放/已归还）、`_statusClass`（chip 样式类名）

---

## 4. Page Data

```js
{
  id: null,
  order: null,
  shopObj: null,

  // 折叠态
  _orderInfoExpanded: true,
  _paymentExpanded: true,
  _refundExpanded: true,

  // 租赁信息
  _rentalTab: 0,               // 0=按租赁商品 1=按租赁物
  _expandedRentals: {},        // { [rentalIdx]: bool }
  _expandedDetails: {},        // { [rentalIdx]: bool } 租金明细
  _expandedItems: {},          // { [rentalIdx]: bool } 租赁物明细
}
```

---

## 5. 页面各 Section

### 5.1 导航栏
使用小程序默认导航栏，标题 `"租赁订单明细"`，**不画自定义 topbar**。

### 5.2 整体布局
```
背景：#F8F8F8，min-height: 100vh，padding: 20rpx 24rpx 160rpx（底部为操作栏留空）
Card 顺序：订单信息 → 支付信息 → 租赁信息 → 退款
```

### 5.3 Card 1 — 订单信息（可折叠）

**标题行**（始终可见）：蓝色竖条 + 「订单信息」+ van-icon 展开/收起箭头，`bindtap="onToggleOrderInfo"`

**折叠内容**（`wx:if="_orderInfoExpanded"`）：

| 字段 | 说明 |
|------|------|
| 顾客姓名 | `order.member.title` + 右侧 chip（散客=灰 / 会员=蓝） |
| 手机号 | `order.member.cell` + 拨打按钮（`wx.makePhoneCall`） |
| 订单号 | `order.code \|\| order.id` |
| 所属门店 | `order.shop` |
| 开单店员 | `order.staffName`（由后端字段提供，若无则显示「—」） |

### 5.4 Card 2 — 支付信息（可折叠）

**标题行**：同上，`bindtap="onTogglePayment"`

**折叠内容**：

双列摘要行（2×2 grid）：
- 支付总金额 / 退款总金额
- 支付笔数 / 退款笔数
- 在押押金 / 解押押金

分割线后支付明细表格（`wx:for="{{order.availablePayments}}"`）：

| 列 | 内容 |
|----|------|
| 日期/时间 | `payment.paid_dateDateStr` + `payment.paid_dateTimeStr` |
| 支付方式 | `payment.pay_method` |
| 类型 | 支付 / 退款 |
| 金额 | 支付=蓝色 `payment.amountStr`；退款=红色 |

退款行来自 `order.availableRefunds`（与 payments 分两个 for 循环，但合并展示时按时间合并排列——简化实现：先列 payments，再列 refunds，加类型 chip 区分）。

### 5.5 Card 3 — 租赁信息

**标题行**：「租赁信息 共 {{order.rentals.length}} 项」（不可折叠）+ 右侧 tab pill

**Tab pill**（手写，不用 van-tabs）：
```
[按租赁商品] [按租赁物]
```
选中态：蓝底白字（`#2EA6D0`）；未选：灰底灰字。`bindtap="onRentalTabChange"` 切换 `_rentalTab`。

#### Tab 0 — 按租赁商品

`wx:for="{{order.rentals}}"` 每个 rental 一张子卡片（白底，8rpx 圆角，12rpx 内边距，卡片间 12rpx 间距）：

**折叠态**（`!_expandedRentals[index]`，默认折叠）：
```
[套餐/单品] chip   租赁名称（超长跑马灯）   押金¥xxx  租金¥xxx  ▼
```

**展开态**（`_expandedRentals[index]`）：
```
起租日期  2026-04-06    起租时间  09:34
退租日期  2026-04-06    退租时间  —
──────────────────────────────────
租金 ¥220   减免 ¥0   赔偿 ¥0   超时 ¥0
招待  否     小计  ¥220.00
──────────────────────────────────
备注  [内容或「修改备注」]     ← tap → wx.showModal editable=true
──────────────────────────────────
「租金明细」▶  bindtap="onToggleDetails"
  wx:if="_expandedDetails[index]"
  → wx:for rental.details：日期 / 租金 / 减免 / 小计
「租赁物明细」▶  bindtap="onToggleItems"
  wx:if="_expandedItems[index]"
  → wx:for rental.rentItems：编码 / 名称 / 品类 / 状态chip
```

状态 chip 颜色：
- 未发放：橙色（`#f59e0b` 底 / `#92400e` 字）
- 已发放：蓝色（`#dbeafe` 底 / `#1d4ed8` 字）
- 已归还：绿色（`#dcfce7` 底 / `#15803d` 字）
- 不需要：灰色（`#f3f4f6` 底 / `#9ca3af` 字）

#### Tab 1 — 按租赁物

展平所有 `rental.rentItems`（通过 JS 在 `renderOrder` 中派生 `order._allRentItems`）：

每行：编码 / 名称 / 品类 / 所属套餐名 / 状态 chip

### 5.6 Card 4 — 退款（可折叠）

**标题行**：`bindtap="onToggleRefund"`

**折叠内容**（双列摘要）：
- 总计押金 / 总计租金
- 总计超时 / 总计赔偿
- 分割线
- 应退押金 `order.totalRentNeedToRefundAmountStr`
- 已退金额 `order.refundAmountStr`
- 实际应退 `order.totalRentUnRefundStr`（如为负显示 ¥0.00）
- 退款按钮：红色，订单已关闭或全退时 disabled

**退款按钮行为**：
1. `wx.showModal` 二次确认，内容含「实际应退 ¥xxx」
2. 确认后调旧版退款接口（与 `rent_details.js` 完全相同逻辑）
3. 成功后 `getData()` 重载页面

### 5.7 底部操作栏

固定在页面底部（`position: fixed; bottom: 0`），订单 `closed == 0` 时显示，`closed == 1` 时隐藏：

```
[+ 添加套餐]  [+ 添加单品]  [✓ 确认追加]
```

三个按钮横排（flex，各占 1/3）：
- **添加套餐**：`wx.navigateTo` 跳 `recept_package`，eventChannel 回传，与旧 `rent_details` 相同逻辑
- **添加单品**：`wx.navigateTo` 跳 `search_fuzzy`，与旧版相同
- **确认追加**：调 `Rent/SaveRentRecept` + `Order/PlaceRentOrder`，与旧版相同；追加物为空时 disabled

---

## 6. CSS 架构

文件：`rent_order_detail.wxss`，`@import '/app.wxss'`

核心 token（与 `payment_entry.wxss` 一致）：

```css
.page           { background: #F8F8F8; padding: 20rpx 24rpx 160rpx; }
.card           { background: #FFF; border-radius: 12rpx; padding: 24rpx; margin-bottom: 20rpx; }
.section-title  { flex + 6rpx × 28rpx #2EA6D0 竖条 + 30rpx 600 #333 }
.kv-row         { display:flex; justify-content:space-between; min-height:64rpx; font-size:28rpx; }
.kv-label       { color:#666; flex-shrink:0; }
.kv-value       { color:#333; text-align:right; }
.kv-value--amount { font-weight:600; }
.kv-value--blue   { color:#2EA6D0; font-weight:600; }
.kv-value--red    { color:#E64340; font-weight:600; }
.divider        { height:1rpx; background:#F0F0F0; margin:8rpx 0; }
.chip           { display:inline-flex; padding:4rpx 12rpx; border-radius:20rpx; font-size:22rpx; }
.chip--member   { background:#dbeafe; color:#1d4ed8; }
.chip--guest    { background:#f3f4f6; color:#6b7280; }
.chip--package  { background:#e0f2fe; color:#0369a1; }
.chip--item     { background:#f3f4f6; color:#6b7280; }
.tab-pill       { flex; height:56rpx; border-radius:28rpx; background:#f3f4f6; }
.tab-pill__item { flex:1; text-align:center; line-height:56rpx; font-size:26rpx; border-radius:28rpx; }
.tab-pill__item--active { background:#2EA6D0; color:#fff; }
.bottom-bar     { position:fixed; bottom:0; left:0; right:0; background:#fff; 
                  padding:16rpx 24rpx; display:flex; gap:16rpx; border-top:1rpx solid #f0f0f0; }
.bottom-btn     { flex:1; height:76rpx; border-radius:8rpx; font-size:28rpx; }
```

**不引入任何 fui-\* 组件**。van 组件只用 `van-icon`（展开箭头）和 `van-button`（拨打电话按钮）。

---

## 7. JSON 依赖

```json
{
  "navigationBarTitleText": "租赁订单明细",
  "usingComponents": {
    "van-icon": "/miniprogram_npm/@vant/weapp/icon/index",
    "van-button": "/miniprogram_npm/@vant/weapp/button/index"
  }
}
```

---

## 8. 入口替换清单

完成后需将以下位置的 `rent_details` 替换为 `rent_order_detail`：

1. `pages/payment/settle/index.js` — `onPaid` 的「查看订单」`redirectTo`
2. `pages/admin/reception/recept_new.js` — 跳转到订单详情的入口（若有）
3. `pages/admin/rent/new_rent_list.js` — 列表点击跳详情
4. `pages/admin/rent/rent_list_by_cell.js` — 同上
5. `pages/admin/rent/unreturned.js` — 同上
6. `components/reception_tabbar/reception_tabbar.js` — 若有跳转
7. 其他 `grep -rn "rent_details" pages/` 命中处

---

## 9. 关键约束（已知坑）

- `order.staffName` 字段需确认后端 `GetOrderByStaff` 是否返回；若无，隐藏「开单店员」行
- 退款接口名和参数与旧 `rent_details.js` 保持完全一致，不改接口
- `order.availableRefunds` 的退款行若后端通过 `availablePayments` 一并返回（refund 字段），则不单独循环，直接按 `payment.refundedAmount` 渲染
- 底部操作栏固定定位时需确认 safe area（iPhone 底部刘海），加 `padding-bottom: env(safe-area-inset-bottom)`
- 所有折叠态切换都用手写 `wx:if`，不引入 `van-collapse`
