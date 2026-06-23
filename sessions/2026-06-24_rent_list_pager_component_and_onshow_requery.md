# 2026-06-24 租赁列表翻页组件化 + onShow 保参重查 + 退押金前提 + 日期可选全程：五项前端打磨

接续 6-22 未归还列表 / 招待开关线。本场全部是 `snowmeet_wechat_mini` 前端改动（含一个新建可复用组件），无后端、无库改。本环境无微信开发者工具，仅过 `node --check` + wxml 标签平衡。代码仓本地未提交，由用户按部署节奏处理；本次 end-work 仅 doc 仓。

## 1. 租赁订单查询日期可选全程（不再只能选今天以后）

- **现象**：`new_rent_list` 的日期范围选择器只能选当天及以后，查不了历史订单。
- **根因**：`van-calendar` 的 `min-date` 默认是「今天」、`max-date` 默认「今天起 6 个月后」。
- **修复**（[`components/date-range-picker/index.{js,wxml}`](../snowmeet_wechat_mini/components/date-range-picker/index.js)）：`attached()` 计算 `minDate`（往回 3 年）+ `maxDate`（今天，历史查询无需选未来）；wxml 给 `<van-calendar>` 显式绑 `min-date`/`max-date`。

## 2. 退押金按钮前提之一：所有 rental 均已退租

- 「申请退款」（退押金）按钮原 disabled 条件 = `order.closed==1 || totalRentUnRefund<=0`，未含「全部退租」前提。
- **判定口径**（沿用现有退租派生）：每条 rental 的相关租赁物（排除 `noNeed`/`已更换`）全部 `_returned`（依据 RentItemLog 归还事件）即该 rental 已退租；所有 rental 退租 → `order._allRentalsReturned=true`。与 settled 无关。
- **改动**（[`rent_order_detail`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js)）：`renderOrder` 加 `allRentalsReturned` 累加 → `rental._allReturned` + `order._allRentalsReturned`；wxml 按钮 disabled 加 `|| !order._allRentalsReturned`，下方加红色提示「所有租赁物退租后才能退押金」（仅在有应退押金、未关单且未全退租时显示）；wxss `.refund-hint`。

## 3. 新建可复用翻页组件 `components/list-pager/`（首页/末页/页码跳转/自定义 pagesize）

用户需求：翻页按钮加「首页」「末页」+ 页码直接填写跳转 + pagesize 文本框（默认 50）；五按钮 + 两输入框在查询进行中禁用（与查询按钮一致）；做成**用户自定义组件**可被各列表复用；出现在查询结果首尾两端。

- **新建 4 文件**（json/js/wxml/wxss）。通用、与「租赁订单」零耦合。
  - props：`page` / `totalPages` / `pageSize` / `disabled`(查询中) / `maxPageSize`(默认 500)
  - 统一 `change` 事件：翻页/跳转带当前 pageSize；改每页条数 → 回第 1 页带新 pageSize
  - 输入框内部状态自管理（`pageInput`/`pageSizeInput`），`observers.pageSize` 同步显示
  - 所有按钮/输入框 `disabled` 时禁用 + 内部 handler 短路双保险
- **接入 `new_rent_list`**：json 注册 `list-pager`；wxml 顶部（统计行下）+ 列表底部各放一个 `<list-pager ... disabled="{{querying}}" bind:change="onPagerChange">`；删掉页面内联翻页 wxml + 8 个旧 handler + `pageInput`/`pageSizeInput` data + 对应 wxss（迁进组件）；`getData(page, pageSize)` 支持传 pageSize、`renderOrders` 回填 `pageSize`；`onPagerChange` 统一回调（`querying` 中短路 + setData querying:true + getData）。
- 默认 pageSize 仍 50。

## 4. 列表页 onShow 保参重查（约定：以后新列表都遵循）

用户需求：从订单明细返回列表（触发 onShow），先记录页面各参数（pageSize / 当前页 / 选中 tag 等）→ 重新查询 → 按当前参数显示。先改未归还列表和租赁订单列表。

- **核心原理**：`navigateTo` 进明细期间列表页实例不销毁，`page`/`pageSize`/筛选 tag/`groupMode`/`keyword` 全在 `this.data` 里。返回 onShow 直接读取重查即可，无需额外快照。
- **`new_rent_list.js`**：`onShow` 由硬编码 `getData(1)`（每次返回重置第 1 页）改为 `getData(this.data.page, this.data.pageSize)`，保留页码 + pagesize + 全部筛选 tag；首次进入 page=1/pageSize=50 自然等同初始查询；「查询」按钮仍重置第 1 页（不变）。
- **`unreturned.js`**：数据加载从 `onLoad` 移到 `onShow`（onLoad 改空），返回也重新拉取；`getData→render` 沿用当前 `groupMode`(分类/订单/顾客) + `keyword` + `shop`。
- **约定**：列表页初始查询放 `onShow`，从 `this.data` 读当前分页/筛选参数重查并显示，不在 onShow 里重置回初始值。

## 5. 按租赁商品视图：恢复展开租赁物明细里的操作按钮

- **现象**：「按租赁物」视图的租赁物卡片有归还/暂存/更换/赔偿/备注操作按钮；「按租赁商品」展开的租赁物明细里同一卡片**没有**这些按钮。
- **根因**：两视图共用 `rentItemCard` 模板，「按租赁商品」传 `readonly: true` 隐藏操作按钮（6-20 续3 的「按商品只读概览」设计）。用户要求把按钮加回来。
- **修复**（[`rent_order_detail.wxml`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml)，一行核心）：「按租赁商品」展开明细的 `readonly: true` → `false`，与「按租赁物」一致；同步更新模板注释。事件绑定（`data-ridx`/`data-iidx`）两边都对得上，无需改 JS。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`components/date-range-picker/index.{js,wxml}`](../snowmeet_wechat_mini/components/date-range-picker/index.js) | attached 算 minDate(往回3年)/maxDate(今天) + van-calendar 绑 min/max-date |
| [`components/list-pager/index.{json,js,wxml,wxss}`](../snowmeet_wechat_mini/components/list-pager/index.js) | 新建：通用翻页组件（首页/上一页/下一页/末页 + 页码跳转 + 自定义 pageSize + disabled 全禁） |
| [`pages/admin/rent/new_rent_list.{js,wxml,wxss,json}`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js) | 接入 list-pager 首尾两端 + 删内联翻页/8 handler + getData/renderOrders 带 pageSize + onShow 保参重查 |
| [`pages/admin/rent/unreturned.js`](../snowmeet_wechat_mini/pages/admin/rent/unreturned.js) | 数据加载 onLoad→onShow，返回保 groupMode/keyword/shop 重查 |
| [`pages/admin/rent/rent_order_detail/rent_order_detail.{js,wxml,wxss}`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) | 退押金按钮加「全部退租」前提；按租赁商品展开明细 readonly→false 恢复操作按钮 |

## 学到的小知识

1. **`van-calendar` 默认只能选今天起 6 个月**：`min-date` 默认今天、`max-date` 默认 +6 月。历史查询要显式绑 `min-date`(过去)/`max-date`(今天) 时间戳。
2. **`navigateTo` 列表页实例不销毁**：`this.data` 即「记录下的页面参数」；返回 onShow 重查只需读 `this.data` 的 page/pageSize/筛选，不要重置回初始值——这就是「保参重查」的全部。把初始查询放 onShow（onLoad 不查）即首次进入也走同一条路、无双查。
3. **翻页栏抽组件的干净边界**：组件只吃 `page/totalPages/pageSize/disabled`、只吐一个 `change{page,pageSize}`；输入框内部状态自管理 + `observers` 同步父级 prop；父级数据加载后回填 page/pageSize/totalPages 让组件 prop 同步。改 pageSize 在组件内回第 1 页。复用只需注册组件 + 一个 `onPagerChange`。
4. **同模板 + `readonly` flag 控操作显隐**：`rentItemCard` 模板既给「只读概览」也给「操作视图」，切换只读/可操作就是传 `readonly: true/false`，无 JS 改动。要恢复操作按钮，改传值即可。
