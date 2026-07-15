# 2026-07-13 养护订单详情：订单级备注 + 订单级退款弹窗

本次按需求补齐养护订单详情页（全局订单维度）两项能力：

1. 订单备注
- 在订单信息卡片新增「订单备注」输入框和「保存备注」按钮。
- 点击保存调用 `updateOrderPromise`，场景：`养护订单详情页修改备注`。
- 防重复提交：`savingOrderMemo` 状态锁。

2. 订单退款
- 在支付信息区域新增「退款」按钮。
- 点击打开 modal，填写「退款金额」+「退款备注」。
- 提交校验：
  - 金额必须 > 0
  - 金额不能超过 `paidAmount - refundAmount`
  - 备注必填
- 退款执行：
  - 使用 `order.availablePayments` 中可退款记录自动分摊（按 `unRefundedAmount` 逐笔扣减）
  - 生成 `refunds` 后调用 `refundPromise(order.id, refunds, sessionKey)`
  - 备注写入 `reason`

## 修改文件
- `snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js`
  - 新增状态：`orderMemoDraft`、`savingOrderMemo`、`refundPopup`
  - 新增方法：`onOrderMemoInput`、`onSaveOrderMemo`、`onOpenRefundPopup`、`onCloseRefundPopup`、`onRefundAmountInput`、`onRefundMemoInput`、`_buildRefundPayload`、`onConfirmRefund`
- `snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.wxml`
  - 新增订单备注区域
  - 新增退款按钮
  - 新增退款弹窗（金额/备注/确认）
- `snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.wxss`
  - 新增订单备注区、支付工具栏、退款弹窗样式

## 校验
- `node --check .../care_order_detail.js` 通过
- VS Code 诊断：`care_order_detail.js/.wxml/.wxss` 均无报错

## 备注
- 本次仅做「订单级退款发起」能力，未改后端接口。
- 退款 reason 已支持来自弹窗备注；后端接口 `Order/Refund/{orderId}` 入参沿用 `List<OrderPaymentRefund>`。
