# 2026-07-19（续2） 养护开单店铺不一致排查：「找回中断的订单」沿用旧店铺

纯诊断会话，接续当天上午的 mat_expire 打磨 + shop_selector bug 修复。用户提出新问题后本会话只做代码排查，**未做任何代码改动**，最后卡在一个需要用户拍板的设计取舍上，会话即被 end-work 打断。

## 1. 问题现象

用户提问原话（大意）：养护开单，为什么店铺选择的是「万龙体验中心」，但开单流程中提交给 `api/Care/CalcCareCharge` 接口的店铺名称却是「崇礼旗舰店」？

## 2. 排查过程

### 2.1 先确认数据流向

- `Care/CalcCareCharge` 请求体里的 `shop` 来自 [`care_recept_form.js:312`](../components/reception/care_recept_form/care_recept_form.js) `shop: this.data.shop`（组件 `properties.shop`，父页传入）
- 组件的 `shop` prop 由 [`recept_new.wxml`](../pages/admin/reception/recept_new.wxml) 三处 `shop="{{shop}}"` 绑定传入
- `recept_new.js` 页面级 `this.data.shop` 的唯一来源在 `onLoad`：

```js
const shop = safeDecode(options.shop) || draft.shopName || '';
...
if (recoveredOrder) {
  this.setData({
    ...
    shop: recoveredOrder.shop || shop,   // ← 关键行，见 recept_new.js:112
    ...
  });
} else {
  this.setData({ ..., shop, ... });
}
```

### 2.2 定位关键分支：找回中断单

`recoveredOrder` 只有在 URL 带 `orderId` 参数、且成功拉到中断单时才非空。检查整个项目，唯一会带 `orderId` 导航到 `recept_new` 的入口是 [`recept_entry.js:276-284`](../pages/admin/reception/recept_entry.js) 的 `onRecoverOrderTap`（「找回中断的订单」弹窗点击某一项）：

```js
onRecoverOrderTap(e) {
  const orderId = e.currentTarget.dataset.id
  const shop = this.data.currentShopName || ''
  this.setData({ showRecoverPanel: false })
  wx.navigateTo({
    url: '/pages/admin/reception/recept_new?orderId=' + orderId
      + '&bizType=rent&shop=' + encodeURIComponent(shop),
  })
},
```

这里传的 `shop` 是**当前 shop-selector 选中的店**（万龙体验中心）。但 `recept_new.js` 收到 `orderId` 后，`onLoad` 里 `shop: recoveredOrder.shop || shop` 会用**订单自己在数据库里落库的 shop 字段**（崇礼旗舰店）覆盖它——URL 传的值反而被忽略。

普通新建订单（不带 `orderId`）没有这个分支，`this.data.shop` 就是当前选中店，两者一致，不会复现。

### 2.3 次要疑点：跨店查询

顺手查了 [`RentController.cs:4552`](../SnowmeetApi/Controllers/RentController.cs) 的 `GetReceptingOrders`：

```csharp
.Where(o => (o.shop.Trim().Equals(shop) || shop == "" || shop == null) && o.valid == 0 && o.recepting == 1 && o.create_date.Date == DateTime.Now.Date)
```

如果打开「找回中断的订单」面板那一刻 `currentShopName` 恰好还是空字符串（比如 shop-selector 的蓝牙 beacon 扫描尚未完成落地），这条过滤会直接放行，把**全部店铺**当天的中断单都列出来 —— 店员可能在没意识到的情况下点开了别的店创建的草稿单。这不是本次现象的确认根因，只是一个相关联的可疑点，未深入验证。

## 3. 关键结论

订单的 `shop` 字段本质是**业务归属店**（财税/报表按店分组统计的依据），不是「当前正在操作的店」。`recoveredOrder.shop || shop` 这行代码是在刻意保留订单原始创建店铺的设计——问题是 UI 侧完全没有提示这一点，让人以为「当前选中店」就是接下来所有操作走的店。

## 4. 待用户拍板的设计问题（未答复）

我在对话里向用户抛出两个选项，会话结束前用户尚未回答：

- **方案 A（保留现状）**：找回旧单时继续用订单原始创建店铺，但需要在 UI 上明确显示「这张单归属 XX 店」，避免与当前选中店混淆
- **方案 B（找回时同步）**：找回中断单时强制把订单的 shop 改成当前选中店——风险是如果店员是在原店换了台设备/重新选了一次店继续这单，会把订单的店铺归属错误篡改成别的店

## 关键改动文件

无。本会话纯代码阅读排查，未执行任何 Edit/Write。

## 学到的小知识

1. **多入口共享同一 onLoad 分支时，要把每条能走到该分支的路径都列出来核对**：`recept_new.js onLoad` 只有一处 `if (recoveredOrder)` 分支，但要先确认「谁会在什么条件下带着 orderId 导航过来」才能锁定唯一复现路径（本例是「找回中断的订单」按钮）
2. **订单级归属字段（如 shop）与 UI 上的"当前选择"是两个概念**，代码里保留前者、覆盖后者往往是有意为之（保业务数据完整性），但缺 UI 提示会让人误判为 bug——排查这类"数据对但让人困惑"的问题时，先分清是真 bug 还是"设计正确但沟通缺失"
