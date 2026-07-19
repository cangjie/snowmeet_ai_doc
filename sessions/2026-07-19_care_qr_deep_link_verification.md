# 2026-07-19（续3） 养护标签二维码 URL 规则 + careId 深链展开行为核实：纯只读问答，无代码改动

接续当天前两场会话（mat_expire 打磨 + 养护店铺不一致诊断）。用户提出两个关于养护订单明细页的问题，均为对既有实现的核实，未发现 bug，未做任何代码改动。

## 1. 打印顾客小票二维码的 URL 规则

用户问：养护订单明细页打印顾客小票时，二维码指向的 URL 遵循什么规则。

- 定位到唯一生成入口 [`components/care/print_care_label.js:294`](../snowmeet_wechat_mini/components/care/print_care_label.js#L294)：
  ```js
  var qrCodeText = 'https://mini.snowmeet.top/mapp/admin/care/care_order_detail/care_order_detail?orderId=' + that.data.order.id.toString() + '&careId=' + care.id.toString()
  ```
- `orderId`=订单主键、`careId`=当前打印的这件装备（care 行）主键；存根/客户联两种小票共用同一 `getCommand`，二维码逻辑不分类型
- 二维码在打印时现算，不落库不缓存
- 落地页解析：[`care_order_detail.js:73-83`](../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js#L73) 优先从 `options.q`（扫码进入时的 URL-encoded 原始参数）解析 `orderId`/`careId`，解不到 fallback `options.id/orderId`/`options.careId`（兼容站内直接 navigateTo）
- 代码注释确认：新标签指向新版 `care_order_detail`；已打印的旧标签仍指旧版 `pages/admin/care/order_detail`（旧页因此保留，专门兼容存量标签）；该路径规则需在公众平台「扫普通链接二维码打开小程序」登记（此前已记入 CLAUDE.md 待办，未见新增阻塞）

## 2. careId 深链应「只展开该 care、其余折叠」行为核实

用户复述预期行为（带 careId 进入时目标 care 展开、其它折叠），要求核实是否已实现。

- 核实 [`_applyTargetCare()`](../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js#L459)：遍历全部 care **显式赋值** `_expanded = (c.id === cid)`——不是只展开目标，而是把其余全部显式设 false，因此「其他折叠」是硬保证而非默认值副作用
- 核实 [`renderOrder`](../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js#L151) 的「首次进入默认展开第一件」分支加了 `!this._targetCareId` 判断，带 careId 进入时不会触发，不会和目标展开冲突
- 调用时机：`onLoad` 存 `_targetCareId` → `loadOrder()` 拿到数据 `renderOrder` 完成后紧接调用 `_applyTargetCare()`（[line 139](../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js#L139)），含 300ms 延迟 `wx.pageScrollTo` 滚动定位到 `#care-{id}`
- `_targetApplied` 标志位保证只在首次 loadOrder 生效一次，之后用户手动展开/折叠不会被覆盖
- wxml 侧确认 `_expanded` 绑定一致：[wxml:137](../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.wxml#L137) 折叠箭头方向、[wxml:149](../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.wxml#L149) 卡片主体展开/收起同读一个字段

**结论**：两项功能均已按预期实现，逻辑严谨（尤其「其余折叠」用显式赋值而非默认值，规避了潜在冲突），本次未发现需要修复的问题。

## 关键改动文件

无（纯只读核实，无代码改动）。

## 学到的小知识

无新增；本次是对 2026-07-12（养护详情页重设计）已完成功能的复核确认。
