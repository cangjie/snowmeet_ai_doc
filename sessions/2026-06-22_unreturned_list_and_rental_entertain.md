# 2026-06-22 未归还租赁物列表重做 + rental 招待开关：两块独立功能

本场会话两件事：① 按设计模版重做「未归还租赁物」列表并替代旧版，点击某件直达订单明细并只展开它所在的 rental；② 订单明细页支持把某个 rental 设为「招待」，按现有招待计费规则计费。改动落在 `snowmeet_wechat_mini/`（小程序）+ 一处 `SnowmeetApi/`（后端新增接口）。

## 1. 未归还租赁物列表重做（替代旧版 + 深链展开）

### 1.1 需求

- 参考 [`templates/rent/unreturned_item.html`](../templates/rent/unreturned_item.html)（Stitch 导出，3.4MB 含内联字体）完整还原新列表，替代原 [`pages/admin/rent/unreturned`](../../snowmeet_wechat_mini/pages/admin/rent/unreturned.js)（旧版 van-collapse 简单分组）。
- 点击列表中某件未归还租赁物 → 跳订单明细页，使**该租赁物所在 rental + 其租赁物列表展开**，**其余（其它 rental + 订单信息/支付/退款顶部区块）全部折叠**。
- 用户确认：「除目标外全部折叠」「完整还原模版」；且深链展开**只**从该列表点过去时生效，不影响正常订单查询。

### 1.2 数据现状（探索结论，无需后端改动）

- 接口 `Rent/GetUnReturnedRentItemsByStaff`（[`RentController.cs:5873`](../../SnowmeetApi/Controllers/RentController.cs)）返回 `CategoryRentItem[]`：`{category_id, category, items[]}`，按品类分组、件数降序。
- `RentItem`（真模型在 [`Models/Rent/Rental.cs:386`](../../SnowmeetApi/Models/Rent/Rental.cs)，**非** `Models/Rent/RentItem.cs` 那个映射 `rent` 表的旧库存模型）携带 `id/name/code(条码)/category/pickDate(NotMapped派生)/pickStaff/status/rental.id/rental.order`。
- `Order`（[`Models/Order/Order.cs:85-87`](../../SnowmeetApi/Models/Order/Order.cs)）**直接带** `name/gender/cell/code` + `contact_name/gender/num` → 顾客姓名/称谓/电话/订单号都已在返回里，模版的顾客二级分组无需加 member include。
- 前端派生：称谓「先生/女士」由 gender 映射；「已租 N 天」由 `pickDate` 到今天。

### 1.3 实现

- [`unreturned.js`](../../snowmeet_wechat_mini/pages/admin/rent/unreturned.js)：`decorate` 把 items 按 `order.id` 二级分组成 `_orderGroups` + 派生发放时间/已租天数/称谓；`applyFilter` 客户端搜索（命中编码/名称/分类名）→ `displayList` + 实时汇总「分类数/件数」；卡片点击 `gotoItem` 带 `&rentItemId=`。
- [`unreturned.wxml`](../../snowmeet_wechat_mini/pages/admin/rent/unreturned.wxml)：顶部 shop-selector+查询+搜索框 → 汇总条 → 品类可折叠 section（搜索时强制全展开）→ 顾客分组头（姓名/称谓/电话 `catchtap` 拨打/订单号）→ 租赁物卡片（van-icon + 名称 + 条码 + 发放时间 + 「发放」标签 + 已租N天）。
- [`unreturned.wxss`](../../snowmeet_wechat_mini/pages/admin/rent/unreturned.wxss)：Alpine 风格（`#f8f9ff` 底、白卡片、`#006495` 主色、8px 圆角）。
- [`unreturned.json`](../../snowmeet_wechat_mini/pages/admin/rent/unreturned.json)：注册 van-icon/van-button/shop-selector。

### 1.4 深链展开（明细侧）

明细页展开状态**按 ridx（rental 数组下标）键控**（`_expandedRentals[ridx]`/`_expandedItems[ridx]`），列表只有 id → 渲染后做 id→下标解析。

- [`rent_order_detail.js`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) `onLoad` 存 `_targetRentItemId`（实例字段，仅此入口带）+ `_deepLinkApplied=false` 守卫。
- `getData` 的 `finish()` 内 `setData({order})` 后调 `applyDeepLinkExpand(order)`：遍历 `order.rentals` 找含目标 item.id 的 ridx → 折叠顶部三区块（`_orderInfoExpanded/_paymentDetailExpanded/_refundExpanded=false`）+ 仅展开目标 rental（`_expandedRentals/{[ridx]:true}`、`_expandedItems/{[ridx]:true}`）→ setData 回调里 `createSelectorQuery` 查 `#rid-item-{id}` boundingClientRect + viewport scrollOffset → `pageScrollTo` 定位。
- wxml 模版根加 `id="rid-item-{{rentItem.id}}"`（[`rent_order_detail.wxml:3`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml)）。
- **守卫**：`_targetRentItemId==null`（普通进入）首行 return，默认展开行为不变；`_deepLinkApplied` 保证只首次生效，切后台再回不重置用户手动展开。

## 2. 订单明细：rental 设/撤「招待」

### 2.1 关键发现 — 招待规则早已全链路存在

`Rental.entertain`（bool，[`Rental.cs:32`](../../SnowmeetApi/Models/Rent/Rental.cs)）已被计费 honor：

- `totalRentalAmount`（:210）：`if (experience || entertain) return 0;` → 租金免。
- `totalSummary`（:243）：`(entertain ? 0 : totalRentalAmount) + 超时费 + 赔偿 - 减免` → 招待只免租金，超时/赔偿仍计。
- 订单应收（[`Order.cs:912`](../../SnowmeetApi/Models/Order/Order.cs)）：`if (rental.experience==false && rental.entertain==false) amount += rental.totalSummary` → 招待 rental 被排除；招待项金额单列进 `entrtainAmount`（:579）。

→ 用户要的「按现有招待计费规则计费」= 暴露这个 flag。**只需持久化 + UI 开关，不动 rental_detail**（招待是派生豁免，租金明细仍显毛额、小计自动归 0）。验证：day-charge 编辑（改实际租金）也不回写订单级金额，确认招待同理无需。

### 2.2 实现

- 后端新增 [`SetRentalEntertainByStaff`](../../SnowmeetApi/Controllers/RentController.cs)（紧随 UpdateRentalDayChargesByStaff）：`[HttpPost("{rentalId}")]`，参数 `entertain/scene/sessionKey`；权限校验（title_level>=100）→ 载入 rental → 变更时写 `CoreDataModLog.CreateManualLog("rental","entertain",...)` 差异日志 + 置 entertain/update_date → 保存 → 返回 `GetRental`。镜像 `UpdateRentalGuarantyByStaff` 写法。
- [`data.js setRentalEntertainPromise`](../../snowmeet_wechat_mini/utils/data.js)（POST 空 body，query 传参，沿用 updateRentalDayChargesPromise 风格）+ 导出。
- [`rent_order_detail.js onToggleEntertain`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js)：`wx.showModal` 二次确认 → 调接口 → 替换 `od.rentals[ridx]` + `renderOrder` + toast。
- [`rent_order_detail.wxml`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml)：showcase「招待」格做成 `bindtap=onToggleEntertain data-ridx`，加 edit 图标提示（注意 van-icon 不能嵌在 `<text>` 里 → 放 flex `<view>` 标签行），「是」时金额橙色高亮。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/pages/admin/rent/unreturned.{js,wxml,wxss,json}` | 按模版重做未归还列表 + 深链跳转 |
| `snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js` | onLoad 取 rentItemId + applyDeepLinkExpand + onToggleEntertain |
| `snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml` | 模版根加 scroll 锚 id + 招待格可点 |
| `snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss` | 招待格 tappable/高亮样式 |
| `snowmeet_wechat_mini/utils/data.js` | setRentalEntertainPromise |
| `SnowmeetApi/Controllers/RentController.cs` | 新增 SetRentalEntertainByStaff 接口 |

## 学到的小知识

1. **有两个 `RentItem` 类**：`Models/Rent/RentItem.cs`（映射 `rent` 表，旧库存/产品模型，含 GetRental 计价）vs `Models/Rent/Rental.cs:386` 的 `Models.RentItem`（映射 `rent_item`，租赁行项，DbSet 是 `rentItem`，含 logs/status/noNeed/pickDate/rental 导航）。控制器用的是后者。
2. **招待是派生豁免，不改 rental_detail**：`entertain=true` 只让计算属性返 0，租金明细行原样保留（显毛额），所以设/撤招待是纯标志切换，比改 day-charge 还轻。
3. **明细页深链：id→下标**：明细页展开 map 按 `ridx` 键控，外部只有 id，必须渲染后遍历 `order.rentals` 反查下标再 setData 展开。
4. **WeChat `<text>` 不能内嵌组件**：van-icon 放在 `<text>` 里不渲染，要放 `<view>`（flex 行）。
5. **深链副作用隔离**：用「仅此入口带的 URL 参数」+「首行 null-return」+「_deepLinkApplied 一次性守卫」三重保证，普通订单查询完全不受影响。
