# 租赁订单详情页 rent_order_detail 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `pages/admin/rent/rent_order_detail` 页，采用 Alpine Operational Minimalist 风格，完整实现租赁订单详情展示与所有操作，替换旧 `rent_details` 的所有入口。

**Architecture:** 4 文件 micro-page（json/js/wxml/wxss），JS 重构自 `rent_details.js` 的核心逻辑（renderOrder + interaction handlers），样式全换为纯 CSS token（同 `pages/order/payment_entry`）。旧 `rent_details` 保留不删。

**Tech Stack:** 原生微信小程序 JS，Vant WeApp（van-icon、van-button），无 TypeScript，无 fui-* 组件。

---

## 文件结构

创建：
- `pages/admin/rent/rent_order_detail/rent_order_detail.json`
- `pages/admin/rent/rent_order_detail/rent_order_detail.js`
- `pages/admin/rent/rent_order_detail/rent_order_detail.wxml`
- `pages/admin/rent/rent_order_detail/rent_order_detail.wxss`

修改：
- `app.json` — 注册新页面（pages 数组加一行）
- `pages/payment/settle/index.js:28` — 跳转 → rent_order_detail
- `pages/admin/rent/new_rent_list.js:266` — 跳转 → rent_order_detail
- `pages/admin/rent/unreturned.js:47` — 跳转 → rent_order_detail
- `pages/admin/rent/search_fuzzy.js:90` — 跳转 → rent_order_detail
- `components/rent/rent_backdrop.js:95` — 跳转 → rent_order_detail

---

## Task 1: Scaffold — JSON + app.json 注册 + 骨架 JS/WXML

**Files:**
- Create: `pages/admin/rent/rent_order_detail/rent_order_detail.json`
- Modify: `app.json`
- Create: `pages/admin/rent/rent_order_detail/rent_order_detail.js` (骨架)
- Create: `pages/admin/rent/rent_order_detail/rent_order_detail.wxml` (骨架)

- [ ] **Step 1: 创建 JSON**

```json
{
  "navigationBarTitleText": "租赁订单明细",
  "usingComponents": {
    "van-icon": "/miniprogram_npm/@vant/weapp/icon/index",
    "van-button": "/miniprogram_npm/@vant/weapp/button/index"
  }
}
```

文件路径：`pages/admin/rent/rent_order_detail/rent_order_detail.json`

- [ ] **Step 2: 在 app.json 的 pages 数组中新增页面**

在 `app.json` 的 `pages` 数组（约第 74 行，`"pages/admin/rent/rent_details"` 前后）追加：

```json
"pages/admin/rent/rent_order_detail/rent_order_detail",
```

- [ ] **Step 3: 创建骨架 JS（仅 Page 结构，具体逻辑在 Task 3 填充）**

文件路径：`pages/admin/rent/rent_order_detail/rent_order_detail.js`

```js
// pages/admin/rent/rent_order_detail/rent_order_detail.js
var app = getApp()
var util = require('../../../utils/util.js')
var data = require('../../../utils/data.js')

Page({
  data: {
    id: null,
    order: null,
    shopObj: null,

    _orderInfoExpanded: true,
    _paymentExpanded: true,
    _refundExpanded: true,

    _rentalTab: 0,
    _expandedRentals: {},
    _expandedDetails: {},
    _expandedItems: {},

    allValid: false,
  },

  onLoad(options) {
    this.setData({ id: parseInt(options.id) })
  },

  onShow() {
    var that = this
    app.loginPromiseNew.then(function () {
      that.getData()
    })
  },

  getData() {
    wx.showLoading({ title: '加载中' })
    var that = this
    var sessionKey = app.globalData.sessionKey
    var id = that.data.id
    data.getOrderByStaffPromise(id, sessionKey).then(function (order) {
      if (!order) { wx.hideLoading(); return }
      var rentalPromises = []
      for (var i = 0; order.rentals && i < order.rentals.length; i++) {
        rentalPromises.push(data.getRentalPromise(order.rentals[i].id, sessionKey))
      }
      Promise.all(rentalPromises).then(function (rentals) {
        for (var i = 0; i < rentals.length; i++) {
          if (rentals[i]) order.rentals[i] = rentals[i]
        }
        order = that.renderOrder(order)
        wx.hideLoading()
        that.setData({ order })
      })
    }).catch(function () { wx.hideLoading() })
  },

  renderOrder(order) {
    // 实现见 Task 3
    return order
  },

  checkAppendingRentalValid() {
    // 实现见 Task 8
  },
})
```

- [ ] **Step 4: 创建骨架 WXML**

文件路径：`pages/admin/rent/rent_order_detail/rent_order_detail.wxml`

```xml
<view class="page" wx:if="{{order}}">
  <!-- Card 1: 订单信息 -->
  <!-- Card 2: 支付信息 -->
  <!-- Card 3: 租赁信息 -->
  <!-- Card 4: 退款 -->
  <!-- 底部操作栏 -->
</view>
<view wx:else class="page-loading">
  <text>加载中…</text>
</view>
```

- [ ] **Step 5: 在微信开发者工具中确认页面可跳转、无编译错误**

从 `pages/admin/rent/unreturned.js` 或 `new_rent_list.js` 临时改一个跳转测试，能进入新页面显示「加载中…」即通过。

---

## Task 2: WXSS — 完整样式系统

**Files:**
- Create: `pages/admin/rent/rent_order_detail/rent_order_detail.wxss`

- [ ] **Step 1: 写完整 WXSS 文件**

文件路径：`pages/admin/rent/rent_order_detail/rent_order_detail.wxss`

```css
@import '/app.wxss';

/* ── 页面 & 卡片 ─────────────────────── */
.page { background: #F8F8F8; padding: 20rpx 24rpx 160rpx; min-height: 100vh; }
.page-loading { display: flex; align-items: center; justify-content: center; height: 100vh; color: #999; }

.card { background: #FFF; border-radius: 12rpx; padding: 24rpx; margin-bottom: 20rpx; }

/* ── 分组标题（蓝色竖条） ─────────────── */
.section-title {
  display: flex; align-items: center;
  font-size: 30rpx; font-weight: 600; color: #333;
  padding: 12rpx 0; margin-bottom: 8rpx;
}
.section-title::before {
  content: ''; display: inline-block;
  width: 6rpx; height: 28rpx;
  background: #2EA6D0; border-radius: 3rpx;
  margin-right: 14rpx; flex-shrink: 0;
}
.section-title-right { margin-left: auto; display: flex; align-items: center; gap: 8rpx; }

/* ── KV 行 ────────────────────────────── */
.kv-row {
  display: flex; justify-content: space-between; align-items: center;
  min-height: 64rpx; font-size: 28rpx; padding: 4rpx 0;
}
.kv-label { color: #666; flex-shrink: 0; }
.kv-value { color: #333; text-align: right; flex: 1; margin-left: 16rpx; word-break: break-all; }
.kv-value--blue { color: #2EA6D0; font-weight: 600; }
.kv-value--red { color: #E64340; font-weight: 600; }
.kv-value--amount { font-weight: 600; font-size: 32rpx; }

/* ── Chip ─────────────────────────────── */
.chip {
  display: inline-flex; padding: 4rpx 12rpx;
  border-radius: 20rpx; font-size: 22rpx; line-height: 1.4;
  flex-shrink: 0;
}
.chip--member { background: #dbeafe; color: #1d4ed8; }
.chip--guest { background: #f3f4f6; color: #6b7280; }
.chip--package { background: #e0f2fe; color: #0369a1; }
.chip--item { background: #f3f4f6; color: #6b7280; }
.chip--status-unreturned { background: #fef9c3; color: #854d0e; }
.chip--status-issued { background: #dbeafe; color: #1d4ed8; }
.chip--status-returned { background: #dcfce7; color: #15803d; }
.chip--status-noneed { background: #f3f4f6; color: #9ca3af; }

/* ── 分隔线 ───────────────────────────── */
.divider { height: 1rpx; background: #F0F0F0; margin: 12rpx 0; }

/* ── 支付摘要 2×3 grid ────────────────── */
.pay-summary-grid {
  display: flex; flex-wrap: wrap; gap: 16rpx;
  margin-bottom: 16rpx;
}
.pay-summary-cell {
  flex: 0 0 calc(50% - 8rpx);
  background: #F8F8F8; border-radius: 8rpx;
  padding: 12rpx 16rpx;
}
.pay-summary-label { font-size: 24rpx; color: #999; margin-bottom: 4rpx; }
.pay-summary-value { font-size: 30rpx; font-weight: 600; color: #333; }
.pay-summary-value--blue { color: #2EA6D0; }
.pay-summary-value--red { color: #E64340; }

/* ── 支付明细表格 ─────────────────────── */
.pay-table { width: 100%; }
.pay-table-row {
  display: flex; align-items: center;
  font-size: 24rpx; min-height: 56rpx;
  border-bottom: 1rpx solid #F5F5F5;
  gap: 8rpx;
}
.pay-table-row:last-child { border-bottom: none; }
.pay-col-date { flex: 0 0 120rpx; color: #666; font-size: 22rpx; }
.pay-col-method { flex: 1; color: #666; }
.pay-col-type { flex: 0 0 60rpx; }
.pay-col-amount { flex: 0 0 130rpx; text-align: right; font-weight: 600; }
.pay-col-amount--pay { color: #2EA6D0; }
.pay-col-amount--refund { color: #E64340; }

/* ── Tab pill ─────────────────────────── */
.tab-pill {
  display: flex; height: 56rpx; border-radius: 28rpx;
  background: #f3f4f6; flex-shrink: 0;
}
.tab-pill__item {
  flex: 1; text-align: center; line-height: 56rpx;
  font-size: 26rpx; border-radius: 28rpx; color: #6b7280;
}
.tab-pill__item--active { background: #2EA6D0; color: #fff; }

/* ── 租赁子卡片 ───────────────────────── */
.rental-card {
  background: #F8F8F8; border-radius: 8rpx;
  padding: 12rpx 16rpx; margin-bottom: 12rpx;
}
.rental-card:last-child { margin-bottom: 0; }

.rental-head {
  display: flex; align-items: center; gap: 8rpx;
  min-height: 52rpx;
}
.rental-head-name {
  flex: 1; font-size: 28rpx; font-weight: 600; color: #333;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.rental-head-meta { display: flex; align-items: center; gap: 8rpx; flex-shrink: 0; }
.rental-head-fee { font-size: 24rpx; color: #666; }
.rental-head-fee text { color: #333; font-weight: 600; }

.rental-body { padding-top: 12rpx; }
.rental-detail-grid {
  display: flex; flex-wrap: wrap; gap: 0;
  font-size: 26rpx;
}
.rental-detail-cell {
  flex: 0 0 50%; display: flex;
  min-height: 56rpx; align-items: center; gap: 8rpx;
}
.rental-detail-label { color: #999; font-size: 24rpx; flex-shrink: 0; }
.rental-detail-value { color: #333; }

.rental-fee-row {
  display: flex; gap: 16rpx; flex-wrap: wrap;
  font-size: 26rpx; padding: 8rpx 0;
}
.rental-fee-cell { display: flex; gap: 6rpx; }
.rental-fee-label { color: #999; }
.rental-fee-value { color: #333; font-weight: 600; }

.rental-memo-row {
  display: flex; align-items: flex-start; gap: 8rpx;
  font-size: 26rpx; min-height: 52rpx; padding: 4rpx 0;
}
.rental-memo-label { color: #999; flex-shrink: 0; padding-top: 6rpx; }
.rental-memo-tap {
  flex: 1; color: #333; word-break: break-all;
  border-bottom: 1rpx solid #e5e7eb; padding-bottom: 4rpx;
}
.rental-memo-placeholder { color: #ccc; }

.toggle-row {
  display: flex; align-items: center; gap: 8rpx;
  font-size: 26rpx; color: #2EA6D0; padding: 8rpx 0;
}

/* ── 详情 / 物明细 ─────────────────────── */
.detail-table { font-size: 24rpx; }
.detail-table-row {
  display: flex; gap: 8rpx; min-height: 48rpx; align-items: center;
  border-bottom: 1rpx solid #F0F0F0;
}
.detail-table-row:last-child { border-bottom: none; }
.detail-table-head { color: #999; font-weight: 600; }
.detail-col-date { flex: 0 0 110rpx; }
.detail-col-amount { flex: 1; text-align: right; color: #333; }
.detail-col-discount { flex: 1; text-align: right; color: #E64340; }
.detail-col-subtotal { flex: 1; text-align: right; font-weight: 600; color: #333; }

.item-table-row {
  display: flex; gap: 8rpx; min-height: 52rpx; align-items: center;
  border-bottom: 1rpx solid #F0F0F0; font-size: 24rpx;
}
.item-table-row:last-child { border-bottom: none; }
.item-col-code { flex: 0 0 120rpx; color: #666; font-size: 22rpx; }
.item-col-name { flex: 1; color: #333; }
.item-col-cat { flex: 0 0 100rpx; color: #666; font-size: 22rpx; }
.item-col-status { flex: 0 0 80rpx; text-align: right; }

/* ── 按租赁物 flat list ────────────────── */
.flat-item-row {
  display: flex; gap: 8rpx; min-height: 64rpx; align-items: center;
  border-bottom: 1rpx solid #F0F0F0; font-size: 26rpx;
}
.flat-item-row:last-child { border-bottom: none; }
.flat-item-code { flex: 0 0 120rpx; color: #666; font-size: 24rpx; }
.flat-item-name { flex: 1; color: #333; }
.flat-item-cat { flex: 0 0 100rpx; color: #666; font-size: 22rpx; }
.flat-item-pkg { flex: 0 0 140rpx; color: #aaa; font-size: 22rpx; overflow: hidden; text-overflow: ellipsis; }
.flat-item-status { flex: 0 0 80rpx; text-align: right; }

/* ── 退款 Card ────────────────────────── */
.refund-summary { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 16rpx; }
.refund-cell {
  flex: 0 0 calc(50% - 8rpx);
  background: #F8F8F8; border-radius: 8rpx; padding: 12rpx 16rpx;
}
.refund-cell-label { font-size: 24rpx; color: #999; margin-bottom: 4rpx; }
.refund-cell-value { font-size: 28rpx; font-weight: 600; color: #333; }
.refund-need { color: #E64340; }
.refund-amount-row {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 28rpx; min-height: 56rpx;
}
.refund-amount-label { color: #666; }
.refund-amount-value { font-weight: 600; color: #333; }
.refund-btn-row { margin-top: 16rpx; }

/* ── 底部操作栏 ───────────────────────── */
.bottom-bar {
  position: fixed; bottom: 0; left: 0; right: 0;
  background: #fff; padding: 16rpx 24rpx;
  display: flex; gap: 16rpx;
  border-top: 1rpx solid #f0f0f0;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
}
.bottom-btn {
  flex: 1; height: 76rpx; border-radius: 8rpx;
  font-size: 28rpx; line-height: 76rpx; text-align: center;
  border: none;
}
.bottom-btn--add { background: #e0f2fe; color: #0369a1; }
.bottom-btn--confirm { background: #2EA6D0; color: #fff; }
.bottom-btn--disabled { background: #f3f4f6; color: #9ca3af; }

/* ── 追加中租赁 ───────────────────────── */
.appending-section { margin-top: 20rpx; }
.appending-title {
  font-size: 26rpx; color: #f59e0b; font-weight: 600;
  margin-bottom: 8rpx;
}
.appending-card {
  background: #fff8f0; border-radius: 8rpx;
  padding: 12rpx 16rpx; margin-bottom: 8rpx;
  border: 1rpx solid #fde68a;
}
.appending-card-head { display: flex; justify-content: space-between; align-items: center; }
.appending-card-name { font-size: 28rpx; color: #333; flex: 1; }
.appending-del-btn { color: #E64340; font-size: 24rpx; padding: 8rpx; }
```

- [ ] **Step 2: 确认微信开发者工具编译无 CSS 错误**

---

## Task 3: JS — onLoad / getData / renderOrder

**Files:**
- Modify: `pages/admin/rent/rent_order_detail/rent_order_detail.js`

- [ ] **Step 1: 替换 renderOrder 实现**

在 JS 文件中找到 `renderOrder(order)` 方法，替换为完整实现：

```js
renderOrder(order) {
  var that = this
  var packages = []
  var rentals = []
  var packageNum = 0
  var totalGuarantyAmount = 0
  var totalSummary = 0
  var unRelieveGuaranty = 0
  var relieveGuaranty = 0
  var allSettled = true

  for (var i = 0; order.rentals && i < order.rentals.length; i++) {
    var rental = order.rentals[i]
    rental.realGuaranty = rental.guaranty
    if (!isNaN(rental.guaranty_dicount)) {
      rental.realGuaranty = rental.guaranty - parseFloat(rental.guaranty_dicount)
    }
    rental.realGuaranty = parseFloat(rental.realGuaranty.toFixed(2))
    totalGuarantyAmount += rental.realGuaranty
    totalSummary += rental.totalSummaryAmount || 0
    if (rental.settled != 1) allSettled = false
    if (rental.guarantyRelieve != 1) {
      unRelieveGuaranty += rental.realGuaranty
    } else {
      relieveGuaranty += rental.realGuaranty
    }

    if (rental.realEndDate == null) {
      rental.realEndDateStr = '--'
    } else {
      rental.realEndDateStr = util.formatDate(new Date(rental.realEndDate))
    }
    if (rental.realStartDate == null) {
      rental.realStartDateStr = '--'
    } else {
      rental.realStartDateStr = util.formatDate(new Date(rental.realStartDate))
    }

    if (rental.isPackage) {
      packages.push(rental)
      packageNum++
      rental._isPackage = true
    } else {
      rentals.push(rental)
      rental._isPackage = false
    }

    if (rental.noGuaranty == true) {
      rental.guarantyAmountStr = '免押金'
    } else {
      rental.guarantyAmountStr = util.showAmount(rental.totalPaidGuarantyAmount)
    }

    if (rental.start_date) {
      var startDate = new Date(rental.start_date)
      rental.start_dateDateStr = util.formatDate(startDate)
      rental.start_dateTimeStr = util.formatTimeStr(startDate)
    } else {
      rental.start_dateDateStr = '——'
      rental.start_dateTimeStr = '——'
    }
    if (rental.end_date) {
      var endDate = new Date(rental.end_date)
      rental.end_dateDateStr = util.formatDate(endDate)
      rental.end_dateTimeStr = util.formatTimeStr(endDate)
    } else {
      rental.end_dateDateStr = '——'
      rental.end_dateTimeStr = '——'
    }

    // 租赁物明细
    for (var j = 0; rental.rentItems && j < rental.rentItems.length; j++) {
      var rentItem = rental.rentItems[j]
      if (rentItem.noNeed) {
        rentItem._statusLabel = '不需要'
        rentItem._statusClass = 'chip--status-noneed'
      } else if (rentItem.status == '未发放') {
        rentItem._statusLabel = '未发放'
        rentItem._statusClass = 'chip--status-unreturned'
      } else if (rentItem.status == '已发放') {
        rentItem._statusLabel = '已发放'
        rentItem._statusClass = 'chip--status-issued'
      } else if (rentItem.status == '已归还') {
        rentItem._statusLabel = '已归还'
        rentItem._statusClass = 'chip--status-returned'
      } else {
        rentItem._statusLabel = rentItem.status || '—'
        rentItem._statusClass = 'chip--status-noneed'
      }
      rentItem.totalRepairationAmountStr = util.showAmount(rentItem.totalRepairationAmount)
      if (rentItem.pickDate == null) {
        rentItem.pickDateStr = '--'
        rentItem.pickTimeStr = '--'
      } else {
        rentItem.pickDateStr = util.formatDate(new Date(rentItem.pickDate))
        rentItem.pickTimeStr = util.formatTimeStr(new Date(rentItem.pickDate))
      }
      if (rentItem.returnDate == null) {
        rentItem.returnDateStr = '--'
        rentItem.returnTimeStr = '--'
      } else {
        rentItem.returnDateStr = util.formatDate(new Date(rentItem.returnDate))
        rentItem.returnTimeStr = util.formatTimeStr(new Date(rentItem.returnDate))
      }
    }

    // 租金明细
    for (var j = 0; rental.details && j < rental.details.length; j++) {
      var detail = rental.details[j]
      var rDate = new Date(detail.rental_date)
      detail.rental_dateDateStr = util.formatDate(rDate)
      detail.amount = parseFloat(detail.amount).toFixed(2)
      detail.othersDiscountAmount = parseFloat(detail.othersDiscountAmount).toFixed(2)
      detail.summary = (parseFloat(detail.amount) - parseFloat(detail.othersDiscountAmount)).toFixed(2)
      detail.summaryStr = util.showAmount(parseFloat(detail.summary))
    }
  }

  // appendingRentals 处理（追加中的租赁）
  for (var i = 0; order.appendingRentals && i < order.appendingRentals.length; i++) {
    var rental = order.appendingRentals[i]
    rental.realGuaranty = rental.guaranty
    if (!isNaN(rental.guaranty_discount)) {
      rental.realGuaranty = rental.guaranty - parseFloat(rental.guaranty_discount)
    }
    if (rental.noGuaranty) {
      rental.realGuaranty = 0
      rental.guaranty_dicount = 0
    }
    rental.realGuaranty = parseFloat(rental.realGuaranty.toFixed(2))
    rental.realDepositStr = util.showAmount(rental.realGuaranty)
    rental.startDate = util.formatDate(new Date(rental.start_date))
    var totalRentalAmount = 0
    for (var j = 0; rental.pricePresets && j < rental.pricePresets.length; j++) {
      rental.pricePresets[j].priceStr = util.showAmount(rental.pricePresets[j].price)
      totalRentalAmount += rental.pricePresets[j].price
    }
    rental.totalRentalAmount = totalRentalAmount
    rental.totalDiscountAmountStr = util.showAmount(totalRentalAmount)
  }

  // 支付明细
  for (var i = 0; order.availablePayments && i < order.availablePayments.length; i++) {
    var payment = order.availablePayments[i]
    var paidDate = new Date(payment.paid_date)
    payment.paid_dateDateStr = util.formatDate(paidDate)
    payment.paid_dateTimeStr = util.formatTimeStr(paidDate)
    payment.amountStr = util.showAmount(payment.amount)
    payment.remainAmount = payment.amount
    if (!isNaN(payment.refundedAmount)) {
      payment.remainAmount = payment.remainAmount - payment.refundedAmount
    }
    payment.remainAmountStr = util.showAmount(payment.remainAmount)
  }

  if (order.appendingRentals && order.appendingRentals.length > 0) {
    that.checkAppendingRentalValid()
  }

  // 关单时间
  if (order.closed == 1) {
    var closeDate = new Date(order.close_date)
    order.close_dateDateStr = util.formatDate(closeDate)
    order.close_dateTimeStr = util.formatTimeStr(closeDate)
  } else {
    order.close_dateDateStr = '--'
    order.close_dateTimeStr = '--'
  }

  // 会员类型
  order._memberTypeLabel = (order.member && order.member.following_wechat == 1) ? '会员' : '散客'
  order._memberTypeClass = (order.member && order.member.following_wechat == 1) ? 'chip--member' : 'chip--guest'

  // 汇总字段
  order.packageNum = packageNum
  order.categoryNum = order.rentals.length - packageNum
  order.paidAmountStr = util.showAmount(order.paidAmount)
  order.refundAmountStr = util.showAmount(order.refundAmount)
  order.unRelieveGuaranty = unRelieveGuaranty
  order.unRelieveGuarantyStr = util.showAmount(unRelieveGuaranty)
  order.relieveGuarantyStr = util.showAmount(relieveGuaranty)
  order.totalGuarantyAmountStr = util.showAmount(order.totalGuarantyAmount)
  order.totalRentSummaryAmountStr = util.showAmount(order.totalRentSummaryAmount)
  order.totalRentNeedToRefundAmountStr = util.showAmount(order.totalRentNeedToRefundAmount)
  order.totalRentOverTimeAmountStr = util.showAmount(order.totalRentOverTimeAmount)
  order.totalRentRepairationAmountStr = util.showAmount(order.totalRentRepairAmount)
  if (order.rentProperties) {
    order.rentProperties.totalPaidGuarantyAmountStr = util.showAmount(order.rentProperties.totalPaidGuarantyAmount)
    order.rentProperties.relieveGuarantyAmountStr = util.showAmount(order.rentProperties.relieveGuarantyAmount)
  }
  order.totalRentUnRefund = parseFloat(order.totalRentUnRefund.toFixed(2))
  if (order.totalRentUnRefund < 0 && order.totalRentUnRefund > -0.001) {
    order.totalRentUnRefund = 0
  }
  order.totalRentUnRefundStr = util.showAmount(order.totalRentUnRefund)

  // 按租赁物 flat list
  var allRentItems = []
  for (var i = 0; order.rentals && i < order.rentals.length; i++) {
    var r = order.rentals[i]
    for (var j = 0; r.rentItems && j < r.rentItems.length; j++) {
      var it = Object.assign({}, r.rentItems[j])
      it._rentalName = r.name
      allRentItems.push(it)
    }
  }
  order._allRentItems = allRentItems

  return order
},
```

- [ ] **Step 2: 确认 `util.formatTimeStr` 存在**

运行 `grep -n "formatTimeStr" /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini/utils/util.js`。若不存在则从 `rent_details.js` 的 util 引用中找到正确的函数名。

- [ ] **Step 3: 确认 `data.getOrderByStaffPromise` 与 `data.getRentalPromise` 存在**

运行 `grep -n "getOrderByStaffPromise\|getRentalPromise" /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini/utils/data.js | head -10`，确认函数签名。

---

## Task 4: WXML Card 1 — 订单信息（可折叠）

**Files:**
- Modify: `pages/admin/rent/rent_order_detail/rent_order_detail.wxml`

- [ ] **Step 1: 替换骨架 WXML，加入 Card 1**

```xml
<view class="page" wx:if="{{order}}">

  <!-- ── Card 1: 订单信息 ─────────────────── -->
  <view class="card">
    <view class="section-title" bindtap="onToggleOrderInfo">
      订单信息
      <view class="section-title-right">
        <van-icon name="{{_orderInfoExpanded ? 'arrow-up' : 'arrow-down'}}" size="18px" color="#999" />
      </view>
    </view>

    <block wx:if="{{_orderInfoExpanded}}">
      <!-- 顾客姓名 + 类型 chip -->
      <view class="kv-row">
        <text class="kv-label">顾客姓名</text>
        <view style="display:flex;align-items:center;gap:8rpx;">
          <text class="kv-value">{{order.member.title || '—'}}</text>
          <view class="chip {{order._memberTypeClass}}">{{order._memberTypeLabel}}</view>
        </view>
      </view>

      <!-- 手机号 + 拨打按钮 -->
      <view class="kv-row">
        <text class="kv-label">手机号</text>
        <view style="display:flex;align-items:center;gap:12rpx;">
          <text class="kv-value">{{order.member.cell || '—'}}</text>
          <van-button wx:if="{{order.member.cell}}"
            size="mini" type="primary" plain
            style="flex-shrink:0;"
            bindtap="onCall">
            拨打
          </van-button>
        </view>
      </view>

      <!-- 订单号 -->
      <view class="kv-row">
        <text class="kv-label">订单号</text>
        <text class="kv-value">{{order.code || order.id}}</text>
      </view>

      <!-- 所属门店 -->
      <view class="kv-row">
        <text class="kv-label">所属门店</text>
        <text class="kv-value">{{order.shop || '—'}}</text>
      </view>

      <!-- 开单店员（staffName 字段，若无则隐藏整行） -->
      <view class="kv-row" wx:if="{{order.staffName}}">
        <text class="kv-label">开单店员</text>
        <text class="kv-value">{{order.staffName}}</text>
      </view>

      <!-- 订单状态 -->
      <view class="kv-row" wx:if="{{order.closed == 1}}">
        <text class="kv-label">关单时间</text>
        <text class="kv-value">{{order.close_dateDateStr}} {{order.close_dateTimeStr}}</text>
      </view>
    </block>
  </view>
```

---

## Task 5: WXML Card 2 — 支付信息（可折叠）

**Files:**
- Modify: `pages/admin/rent/rent_order_detail/rent_order_detail.wxml`

- [ ] **Step 1: 在 Card 1 后追加 Card 2**

```xml
  <!-- ── Card 2: 支付信息 ─────────────────── -->
  <view class="card">
    <view class="section-title" bindtap="onTogglePayment">
      支付信息
      <view class="section-title-right">
        <van-icon name="{{_paymentExpanded ? 'arrow-up' : 'arrow-down'}}" size="18px" color="#999" />
      </view>
    </view>

    <block wx:if="{{_paymentExpanded}}">
      <!-- 2×3 摘要格 -->
      <view class="pay-summary-grid">
        <view class="pay-summary-cell">
          <view class="pay-summary-label">支付总金额</view>
          <view class="pay-summary-value pay-summary-value--blue">{{order.paidAmountStr}}</view>
        </view>
        <view class="pay-summary-cell">
          <view class="pay-summary-label">退款总金额</view>
          <view class="pay-summary-value pay-summary-value--red">{{order.refundAmountStr}}</view>
        </view>
        <view class="pay-summary-cell">
          <view class="pay-summary-label">在押押金</view>
          <view class="pay-summary-value">{{order.unRelieveGuarantyStr}}</view>
        </view>
        <view class="pay-summary-cell">
          <view class="pay-summary-label">解押押金</view>
          <view class="pay-summary-value">{{order.relieveGuarantyStr}}</view>
        </view>
        <view class="pay-summary-cell">
          <view class="pay-summary-label">支付笔数</view>
          <view class="pay-summary-value">{{order.availablePayments.length}}</view>
        </view>
        <view class="pay-summary-cell">
          <view class="pay-summary-label">退款笔数</view>
          <view class="pay-summary-value">{{order.availableRefunds.length || 0}}</view>
        </view>
      </view>

      <view class="divider"></view>

      <!-- 支付明细表格 -->
      <view class="pay-table" wx:if="{{order.availablePayments.length > 0}}">
        <!-- 表头 -->
        <view class="pay-table-row" style="font-size:22rpx;color:#999;">
          <text class="pay-col-date">日期</text>
          <text class="pay-col-method">方式</text>
          <text class="pay-col-type">类型</text>
          <text class="pay-col-amount">金额</text>
        </view>
        <!-- 支付行 -->
        <view class="pay-table-row" wx:for="{{order.availablePayments}}" wx:key="id">
          <view class="pay-col-date">
            <text style="display:block;">{{item.paid_dateDateStr}}</text>
            <text style="display:block;font-size:20rpx;color:#999;">{{item.paid_dateTimeStr}}</text>
          </view>
          <text class="pay-col-method">{{item.pay_method}}</text>
          <view class="pay-col-type">
            <view class="chip chip--member" style="font-size:20rpx;padding:2rpx 8rpx;">支付</view>
          </view>
          <text class="pay-col-amount pay-col-amount--pay">{{item.amountStr}}</text>
        </view>
        <!-- 退款行（availableRefunds，若后端有单独返回） -->
        <view class="pay-table-row" wx:for="{{order.availableRefunds}}" wx:key="id">
          <view class="pay-col-date">
            <text style="display:block;">{{item.paid_dateDateStr || '—'}}</text>
          </view>
          <text class="pay-col-method">{{item.pay_method || '—'}}</text>
          <view class="pay-col-type">
            <view class="chip chip--guest" style="font-size:20rpx;padding:2rpx 8rpx;">退款</view>
          </view>
          <text class="pay-col-amount pay-col-amount--refund">-{{item.amountStr}}</text>
        </view>
      </view>
      <view wx:else style="color:#999;font-size:26rpx;text-align:center;padding:20rpx 0;">
        暂无支付记录
      </view>
    </block>
  </view>
```

---

## Task 6: WXML Card 3 — 租赁信息（Tab 切换 + 折叠子卡片）

**Files:**
- Modify: `pages/admin/rent/rent_order_detail/rent_order_detail.wxml`

- [ ] **Step 1: 在 Card 2 后追加 Card 3**

```xml
  <!-- ── Card 3: 租赁信息 ─────────────────── -->
  <view class="card">
    <view class="section-title">
      租赁信息 共{{order.rentals.length}}项
      <view class="section-title-right">
        <!-- Tab pill -->
        <view class="tab-pill">
          <view class="tab-pill__item {{_rentalTab == 0 ? 'tab-pill__item--active' : ''}}"
            bindtap="onRentalTabChange" data-tab="0">按商品</view>
          <view class="tab-pill__item {{_rentalTab == 1 ? 'tab-pill__item--active' : ''}}"
            bindtap="onRentalTabChange" data-tab="1">按物品</view>
        </view>
      </view>
    </view>

    <!-- Tab 0: 按租赁商品 -->
    <block wx:if="{{_rentalTab == 0}}">
      <view class="rental-card" wx:for="{{order.rentals}}" wx:key="id" wx:for-index="ridx">
        <!-- 折叠态 -->
        <view class="rental-head" bindtap="onToggleRental" data-ridx="{{ridx}}">
          <view class="chip {{item._isPackage ? 'chip--package' : 'chip--item'}}">
            {{item._isPackage ? '套餐' : '单品'}}
          </view>
          <text class="rental-head-name">{{item.name}}</text>
          <view class="rental-head-meta">
            <view class="rental-head-fee">押金<text>{{item.guarantyAmountStr}}</text></view>
            <van-icon name="{{_expandedRentals[ridx] ? 'arrow-up' : 'arrow-down'}}" size="16px" color="#999" />
          </view>
        </view>

        <!-- 展开态 -->
        <block wx:if="{{_expandedRentals[ridx]}}">
          <view class="divider"></view>

          <!-- 基础信息 2×2 网格 -->
          <view class="rental-detail-grid">
            <view class="rental-detail-cell">
              <text class="rental-detail-label">起租日期</text>
              <text class="rental-detail-value">{{item.start_dateDateStr}}</text>
            </view>
            <view class="rental-detail-cell">
              <text class="rental-detail-label">起租时间</text>
              <text class="rental-detail-value">{{item.start_dateTimeStr}}</text>
            </view>
            <view class="rental-detail-cell">
              <text class="rental-detail-label">退租日期</text>
              <text class="rental-detail-value">{{item.end_dateDateStr}}</text>
            </view>
            <view class="rental-detail-cell">
              <text class="rental-detail-label">退租时间</text>
              <text class="rental-detail-value">{{item.end_dateTimeStr}}</text>
            </view>
          </view>

          <view class="divider"></view>

          <!-- 费用汇总行 -->
          <view class="rental-fee-row">
            <view class="rental-fee-cell">
              <text class="rental-fee-label">租金</text>
              <text class="rental-fee-value">¥{{item.totalRentSummaryAmount}}</text>
            </view>
            <view class="rental-fee-cell">
              <text class="rental-fee-label">减免</text>
              <text class="rental-fee-value">¥{{item.totalDiscountAmount || 0}}</text>
            </view>
            <view class="rental-fee-cell">
              <text class="rental-fee-label">赔偿</text>
              <text class="rental-fee-value">¥{{item.totalRepairationAmount || 0}}</text>
            </view>
            <view class="rental-fee-cell">
              <text class="rental-fee-label">超时</text>
              <text class="rental-fee-value">¥{{item.totalOverTimeAmount || 0}}</text>
            </view>
          </view>
          <view class="rental-fee-row">
            <view class="rental-fee-cell">
              <text class="rental-fee-label">招待</text>
              <text class="rental-fee-value">{{item.entertain ? '是' : '否'}}</text>
            </view>
            <view class="rental-fee-cell">
              <text class="rental-fee-label">小计</text>
              <text class="rental-fee-value kv-value--blue">¥{{item.totalSummaryAmount || 0}}</text>
            </view>
          </view>

          <view class="divider"></view>

          <!-- 备注（点击修改） -->
          <view class="rental-memo-row">
            <text class="rental-memo-label">备注</text>
            <view class="rental-memo-tap" bindtap="onModMemo" data-ridx="{{ridx}}">
              <text wx:if="{{item.memo}}">{{item.memo}}</text>
              <text wx:else class="rental-memo-placeholder">修改备注</text>
            </view>
          </view>

          <view class="divider"></view>

          <!-- 租金明细 toggle -->
          <view class="toggle-row" bindtap="onToggleDetails" data-ridx="{{ridx}}">
            <van-icon name="{{_expandedDetails[ridx] ? 'arrow-up' : 'arrow-down'}}" size="14px" />
            <text>租金明细 ({{item.details.length}}天)</text>
          </view>
          <block wx:if="{{_expandedDetails[ridx]}}">
            <view class="detail-table">
              <view class="detail-table-row detail-table-head">
                <text class="detail-col-date">日期</text>
                <text class="detail-col-amount">租金</text>
                <text class="detail-col-discount">减免</text>
                <text class="detail-col-subtotal">小计</text>
              </view>
              <view class="detail-table-row" wx:for="{{item.details}}" wx:key="id" wx:for-item="detail">
                <text class="detail-col-date">{{detail.rental_dateDateStr}}</text>
                <text class="detail-col-amount">¥{{detail.amount}}</text>
                <text class="detail-col-discount">¥{{detail.othersDiscountAmount}}</text>
                <text class="detail-col-subtotal">{{detail.summaryStr}}</text>
              </view>
            </view>
          </block>

          <view class="divider"></view>

          <!-- 租赁物明细 toggle -->
          <view class="toggle-row" bindtap="onToggleItems" data-ridx="{{ridx}}">
            <van-icon name="{{_expandedItems[ridx] ? 'arrow-up' : 'arrow-down'}}" size="14px" />
            <text>租赁物明细 ({{item.rentItems.length}}件)</text>
          </view>
          <block wx:if="{{_expandedItems[ridx]}}">
            <view class="item-table-row" wx:for="{{item.rentItems}}" wx:key="id" wx:for-item="rentItem">
              <text class="item-col-code">{{rentItem.code || '无编码'}}</text>
              <text class="item-col-name">{{rentItem.name || '—'}}</text>
              <text class="item-col-cat">{{rentItem.class_name || '—'}}</text>
              <view class="item-col-status">
                <view class="chip {{rentItem._statusClass}}" style="font-size:20rpx;padding:2rpx 8rpx;">
                  {{rentItem._statusLabel}}
                </view>
              </view>
            </view>
          </block>
        </block>
      </view>

      <!-- 追加中的租赁 -->
      <view class="appending-section" wx:if="{{order.appendingRentals && order.appendingRentals.length > 0}}">
        <view class="appending-title">追加中 ({{order.appendingRentals.length}})</view>
        <view class="appending-card" wx:for="{{order.appendingRentals}}" wx:key="id">
          <view class="appending-card-head">
            <text class="appending-card-name">{{item.name}} · {{item.startDate}}</text>
            <text class="appending-del-btn" bindtap="onDelAppendingRental" data-id="{{item.id}}">删除</text>
          </view>
        </view>
      </view>
    </block>

    <!-- Tab 1: 按租赁物 -->
    <block wx:if="{{_rentalTab == 1}}">
      <view wx:if="{{order._allRentItems.length == 0}}"
        style="color:#999;font-size:26rpx;text-align:center;padding:20rpx 0;">
        暂无租赁物
      </view>
      <view class="flat-item-row" wx:for="{{order._allRentItems}}" wx:key="id">
        <text class="flat-item-code">{{item.code || '无码'}}</text>
        <text class="flat-item-name">{{item.name || '—'}}</text>
        <text class="flat-item-cat">{{item.class_name || '—'}}</text>
        <text class="flat-item-pkg">{{item._rentalName}}</text>
        <view class="flat-item-status">
          <view class="chip {{item._statusClass}}" style="font-size:20rpx;padding:2rpx 8rpx;">
            {{item._statusLabel}}
          </view>
        </view>
      </view>
    </block>
  </view>
```

---

## Task 7: WXML Card 4 — 退款 + 底部操作栏

**Files:**
- Modify: `pages/admin/rent/rent_order_detail/rent_order_detail.wxml`

- [ ] **Step 1: 在 Card 3 后追加 Card 4 + 底部操作栏 + 关闭 `<view class="page">`**

```xml
  <!-- ── Card 4: 退款 ─────────────────────── -->
  <view class="card">
    <view class="section-title" bindtap="onToggleRefund">
      退款
      <view class="section-title-right">
        <van-icon name="{{_refundExpanded ? 'arrow-up' : 'arrow-down'}}" size="18px" color="#999" />
      </view>
    </view>

    <block wx:if="{{_refundExpanded}}">
      <!-- 退款摘要 -->
      <view class="refund-summary">
        <view class="refund-cell">
          <view class="refund-cell-label">总计押金</view>
          <view class="refund-cell-value">{{order.totalGuarantyAmountStr}}</view>
        </view>
        <view class="refund-cell">
          <view class="refund-cell-label">总计租金</view>
          <view class="refund-cell-value">{{order.totalRentSummaryAmountStr}}</view>
        </view>
        <view class="refund-cell">
          <view class="refund-cell-label">总计超时</view>
          <view class="refund-cell-value">{{order.totalRentOverTimeAmountStr}}</view>
        </view>
        <view class="refund-cell">
          <view class="refund-cell-label">总计赔偿</view>
          <view class="refund-cell-value">{{order.totalRentRepairationAmountStr}}</view>
        </view>
      </view>

      <view class="divider"></view>

      <view class="refund-amount-row">
        <text class="refund-amount-label">应退押金</text>
        <text class="refund-amount-value">{{order.totalRentNeedToRefundAmountStr}}</text>
      </view>
      <view class="refund-amount-row">
        <text class="refund-amount-label">已退金额</text>
        <text class="refund-amount-value">{{order.refundAmountStr}}</text>
      </view>
      <view class="refund-amount-row">
        <text class="refund-amount-label">实际应退</text>
        <text class="refund-amount-value refund-need">
          {{order.totalRentUnRefund <= 0 ? '¥0.00' : order.totalRentUnRefundStr}}
        </text>
      </view>

      <!-- 退款按钮 -->
      <view class="refund-btn-row">
        <van-button
          type="danger"
          block
          disabled="{{order.closed == 1 || order.totalRentUnRefund <= 0}}"
          bindtap="onRefund">
          申请退款 {{order.totalRentUnRefund > 0 ? order.totalRentUnRefundStr : ''}}
        </van-button>
      </view>
    </block>
  </view>

</view>

<!-- 加载占位 -->
<view wx:else class="page-loading">
  <text>加载中…</text>
</view>

<!-- ── 底部操作栏（订单未关闭时显示） ─── -->
<view class="bottom-bar" wx:if="{{order && order.closed == 0}}">
  <van-button class="bottom-btn bottom-btn--add" bindtap="onAddPackage" size="small">
    + 添加套餐
  </van-button>
  <van-button class="bottom-btn bottom-btn--add" bindtap="onAddItem" size="small">
    + 添加单品
  </van-button>
  <van-button
    class="bottom-btn bottom-btn--confirm {{!allValid || !order.appendingRentals || order.appendingRentals.length == 0 ? 'bottom-btn--disabled' : ''}}"
    disabled="{{!allValid || !order.appendingRentals || order.appendingRentals.length == 0}}"
    bindtap="onConfirmAppend"
    size="small">
    ✓ 确认追加
  </van-button>
</view>
```

---

## Task 8: JS Interaction Handlers

**Files:**
- Modify: `pages/admin/rent/rent_order_detail/rent_order_detail.js`

- [ ] **Step 1: 添加折叠切换 handlers**

在 `Page({...})` 内 `renderOrder` 后追加：

```js
// ── Toggle handlers ────────────────────
onToggleOrderInfo() {
  this.setData({ _orderInfoExpanded: !this.data._orderInfoExpanded })
},
onTogglePayment() {
  this.setData({ _paymentExpanded: !this.data._paymentExpanded })
},
onToggleRefund() {
  this.setData({ _refundExpanded: !this.data._refundExpanded })
},
onRentalTabChange(e) {
  this.setData({ _rentalTab: parseInt(e.currentTarget.dataset.tab) })
},
onToggleRental(e) {
  var ridx = e.currentTarget.dataset.ridx
  var key = '_expandedRentals.' + ridx
  this.setData({ [key]: !this.data._expandedRentals[ridx] })
},
onToggleDetails(e) {
  var ridx = e.currentTarget.dataset.ridx
  var key = '_expandedDetails.' + ridx
  this.setData({ [key]: !this.data._expandedDetails[ridx] })
},
onToggleItems(e) {
  var ridx = e.currentTarget.dataset.ridx
  var key = '_expandedItems.' + ridx
  this.setData({ [key]: !this.data._expandedItems[ridx] })
},
```

- [ ] **Step 2: 添加拨打电话 handler**

```js
// ── 拨打电话 ───────────────────────────
onCall() {
  var cell = this.data.order && this.data.order.member && this.data.order.member.cell
  if (!cell) return
  wx.setClipboardData({
    data: cell,
    success: function () {
      wx.makePhoneCall({ phoneNumber: cell })
    }
  })
},
```

- [ ] **Step 3: 添加退款 handler**

```js
// ── 退款 ───────────────────────────────
onRefund() {
  var that = this
  var order = that.data.order
  var refundAmount = order.totalRentUnRefund
  if (!refundAmount || isNaN(refundAmount) || refundAmount <= 0) {
    wx.showToast({ title: '无需退款', icon: 'none' })
    return
  }
  wx.showModal({
    title: '确认退款',
    content: '实际应退 ' + util.showAmount(refundAmount),
    complete: (res) => {
      if (!res.confirm) return
      var payment = null
      for (var i = 0; order.availablePayments && i < order.availablePayments.length; i++) {
        var p = order.availablePayments[i]
        var unRefund = parseFloat((p.unRefundedAmount || 0).toString())
        if (p.status == '支付成功'
          && parseFloat(unRefund.toFixed(2)) >= parseFloat(refundAmount.toFixed(2))) {
          payment = p
          break
        }
      }
      if (!payment) {
        wx.showToast({ title: '无可退款支付记录', icon: 'error' })
        return
      }
      var refunds = [{
        payment_id: payment.id,
        amount: parseFloat(refundAmount.toFixed(2)),
        reason: '租赁退押金'
      }]
      data.refundPromise(order.id, refunds, app.globalData.sessionKey).then(function () {
        wx.showToast({ title: '退款成功', icon: 'success' })
        that.getData()
      })
    }
  })
},
```

- [ ] **Step 4: 添加修改备注 handler**

```js
// ── 修改备注 ───────────────────────────
onModMemo(e) {
  var that = this
  var ridx = e.currentTarget.dataset.ridx
  var rental = that.data.order.rentals[ridx]
  wx.showModal({
    title: '修改备注',
    content: rental.memo || '',
    editable: true,
    complete: (res) => {
      if (!res.confirm) return
      var newMemo = res.content || ''
      rental.memo = newMemo
      data.updateRentalPromise(rental, '租赁订单详细页修改备注', app.globalData.sessionKey)
        .then(function () {
          that.setData({ ['order.rentals[' + ridx + '].memo']: newMemo })
          wx.showToast({ title: '备注已保存', icon: 'success' })
        })
    }
  })
},
```

- [ ] **Step 5: 添加 checkAppendingRentalValid**

```js
// ── 追加租赁校验 ───────────────────────
checkAppendingRentalValid() {
  var that = this
  var order = that.data.order
  if (!order || !order.appendingRentals) return
  var allValid = true
  var rentals = order.appendingRentals
  for (var i = 0; i < rentals.length; i++) {
    var rentalWellformed = true
    var rentItems = rentals[i].rentItems
    for (var j = 0; rentItems && j < rentItems.length; j++) {
      var rentItem = rentItems[j]
      if (rentItem.noNeed) {
        rentItem.wellFormed = true
      } else if (rentItem.noCode) {
        rentItem.wellFormed = !!(rentItem.name && rentItem.name != '')
        if (!rentItem.wellFormed) { rentalWellformed = false; allValid = false }
      } else {
        rentItem.wellFormed = !!(rentItem.code && rentItem.code != '')
        if (!rentItem.wellFormed) { rentalWellformed = false; allValid = false }
      }
    }
    rentals[i].wellFormed = rentalWellformed
  }
  that.setData({ allValid })
},
```

- [ ] **Step 6: 添加底部操作栏的追加套餐/单品/确认 handlers**

```js
// ── 底部操作栏 ─────────────────────────
onAddPackage() {
  var that = this
  var order = that.data.order
  wx.navigateTo({
    url: '/pages/admin/reception/recept_package?orderId=' + order.id
      + '&shop=' + encodeURIComponent(order.shop),
    events: {
      selectPackage: function (pkg) {
        var appendUrl = app.globalData.requestPrefix
          + 'Rent/AppendRental/' + order.id.toString()
          + '?packageId=' + pkg.id
          + '&sessionKey=' + app.globalData.sessionKey
        util.performWebRequest(appendUrl, null).then(function (updatedOrder) {
          updatedOrder = that.renderOrder(updatedOrder)
          that.setData({ order: updatedOrder })
          that.checkAppendingRentalValid()
          that.setData({ order: updatedOrder })
        })
      }
    }
  })
},

onAddItem() {
  var that = this
  var order = that.data.order
  wx.navigateTo({
    url: '/pages/admin/rent/search_fuzzy?orderId=' + order.id,
    events: {
      selectCategory: function (category) {
        var appendUrl = app.globalData.requestPrefix
          + 'Rent/AppendRental/' + order.id.toString()
          + '?categoryId=' + category.id
          + '&sessionKey=' + app.globalData.sessionKey
        util.performWebRequest(appendUrl, null).then(function (updatedOrder) {
          updatedOrder = that.renderOrder(updatedOrder)
          that.setData({ order: updatedOrder })
          that.checkAppendingRentalValid()
          that.setData({ order: updatedOrder })
        })
      }
    }
  })
},

onConfirmAppend() {
  var that = this
  var order = that.data.order
  if (!order.appendingRentals || order.appendingRentals.length == 0) return
  var appUrl = app.globalData.requestPrefix
    + 'Rent/SaveAppendings/' + order.id.toString()
    + '?sessionKey=' + app.globalData.sessionKey
  wx.showLoading({ title: '追加中' })
  util.performWebRequest(appUrl, order.appendingRentals).then(function (updatedOrder) {
    wx.hideLoading()
    if (updatedOrder.paying_amount > 0) {
      // 需要补缴，跳结算页
      var renderedOrder = that.renderOrder(updatedOrder)
      that.setData({ order: renderedOrder })
      that.checkAppendingRentalValid()
      wx.navigateTo({ url: '/pages/payment/settle/index?orderId=' + updatedOrder.id })
    } else {
      that.getData()
      wx.showToast({ title: '追加成功', icon: 'success' })
    }
  }).catch(function () {
    wx.hideLoading()
    wx.showToast({ title: '追加失败', icon: 'error' })
  })
},

onDelAppendingRental(e) {
  var that = this
  var id = e.currentTarget.dataset.id
  var order = that.data.order
  var rental = null
  for (var i = 0; order.appendingRentals && i < order.appendingRentals.length; i++) {
    if (order.appendingRentals[i].id == id) { rental = order.appendingRentals[i]; break }
  }
  if (!rental) return
  wx.showModal({
    title: '确认删除',
    content: '正在添加的租赁商品：' + rental.name + ' 即将删除。',
    complete: (res) => {
      if (!res.confirm) return
      var delUrl = app.globalData.requestPrefix
        + 'Rent/RemoveAppendingRental/' + id.toString()
        + '?sessionKey=' + app.globalData.sessionKey
      util.performWebRequest(delUrl, null).then(function (updatedOrder) {
        updatedOrder = that.renderOrder(updatedOrder)
        that.setData({ order: updatedOrder })
        that.checkAppendingRentalValid()
        that.setData({ order: updatedOrder })
      })
    }
  })
},
```

- [ ] **Step 7: 验证 WXML 和 JS 对齐**

- WXML 中的所有 `bindtap` 函数名都在 JS 中有对应实现
- `data-xxx` 参数与 JS `e.currentTarget.dataset.xxx` 对应

---

## Task 9: 入口替换 + 端到端验证

**Files:**
- Modify: `pages/payment/settle/index.js:28`
- Modify: `pages/admin/rent/new_rent_list.js:266`
- Modify: `pages/admin/rent/unreturned.js:47`
- Modify: `pages/admin/rent/search_fuzzy.js:90`
- Modify: `components/rent/rent_backdrop.js:95`

- [ ] **Step 1: 替换 settle/index.js 的跳转**

`pages/payment/settle/index.js:28` 将：
```js
wx.redirectTo({ url: '/pages/admin/rent/rent_details?id=' + orderId })
```
改为：
```js
wx.redirectTo({ url: '/pages/admin/rent/rent_order_detail/rent_order_detail?id=' + orderId })
```

- [ ] **Step 2: 替换 new_rent_list.js 的跳转**

`pages/admin/rent/new_rent_list.js:266` 将：
```js
url: '/pages/admin/rent/rent_details?id=' + order.id,
```
改为：
```js
url: '/pages/admin/rent/rent_order_detail/rent_order_detail?id=' + order.id,
```

- [ ] **Step 3: 替换 unreturned.js 的跳转**

`pages/admin/rent/unreturned.js:47` 将：
```js
url: 'rent_details?id=' + id.toString(),
```
改为：
```js
url: '/pages/admin/rent/rent_order_detail/rent_order_detail?id=' + id.toString(),
```

- [ ] **Step 4: 替换 search_fuzzy.js 的跳转**

`pages/admin/rent/search_fuzzy.js:90` 将：
```js
url: 'rent_details?id='+id,
```
改为：
```js
url: '/pages/admin/rent/rent_order_detail/rent_order_detail?id=' + id,
```

- [ ] **Step 5: 替换 rent_backdrop.js 的跳转**

`components/rent/rent_backdrop.js:95` 将：
```js
that.triggerEvent('Jump', { url: '/pages/admin/rent/rent_details?id=' + order.id })
```
改为：
```js
that.triggerEvent('Jump', { url: '/pages/admin/rent/rent_order_detail/rent_order_detail?id=' + order.id })
```

- [ ] **Step 6: 验证所有入口已替换**

运行 `grep -rn "rent_details" pages/ components/ --include="*.js"` 查看是否还有遗漏。

- [ ] **Step 7: 端到端冒烟测试**

1. 从 `new_rent_list` 点击一个租赁订单 → 进入 `rent_order_detail`
2. 验证订单信息 Card（姓名/手机号/订单号）正确展示
3. 展开支付信息，验证支付摘要数字
4. 切换租赁信息 Tab 到「按租赁物」，验证物品列表
5. 点击「修改备注」，输入文字后确认，验证备注更新
6. 点击「拨打」按钮，验证复制剪贴板+拨号弹窗
7. 从 settle 页「查看订单」跳转，验证也能正常进入

---

## 自审

**规格覆盖检查：**
- Card 1 订单信息（顾客姓名/手机号/订单号/门店/店员）✅ Task 4
- Card 2 支付信息（摘要网格/明细表格）✅ Task 5
- Card 3 租赁信息（Tab pill/按商品折叠/按物品 flat）✅ Task 6
- Card 4 退款（摘要/应退/退款按钮）✅ Task 7
- 底部操作栏（添加套餐/单品/确认追加）✅ Task 7
- WXSS token（F8F8F8/white card/2EA6D0/chip 颜色）✅ Task 2
- 入口替换（5 个文件）✅ Task 9
- checkAppendingRentalValid ✅ Task 8
- renderOrder 完整派生字段 ✅ Task 3

**约束兼容：**
- 无 fui-* 组件 ✅（仅 van-icon + van-button）
- 无自定义 topbar ✅
- 使用 wx:if 折叠不用 van-collapse ✅
- 所有操作接口与旧 `rent_details.js` 完全相同 ✅
- `order.staffName` 字段：若后端不返回则条件渲染隐藏整行 ✅（`wx:if="{{order.staffName}}"` 已处理）
- `order.availableRefunds`：若后端不单独返回则 wx:for 直接为空，不报错 ✅
- safe-area padding-bottom ✅（`env(safe-area-inset-bottom)`）
