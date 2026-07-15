# 2026-06-28 订单追加商品界面重组（独立追加页）+ 多笔退款逐笔输入 + 一串连带修复

本场从 brainstorming「订单详情页追加租赁商品应有独立区域」开始，落地一条完整的追加功能链（详情页独立卡片区 + 新建独立追加页 + 草稿/待支付/生效分流 + 实时保存），过程中由用户真机反复反馈，连带修了 payment_entry 多笔 payment 误判（微信 + 支付宝两端）、库存 status、退款多笔逐笔输入等。所有代码改动散落 `snowmeet_wechat_mini` / `SnowmeetApi` / `alipay_snowmeet`，**本地未提交**，由用户按部署节奏处理；本次 end-work 仅 doc 仓。spec 见 [`docs/superpowers/specs/2026-06-28-rent-append-redesign-design.md`](../docs/superpowers/specs/2026-06-28-rent-append-redesign-design.md)。

## 1. 追加商品界面重组（brainstorming → 实现）

### 1.1 现状摸底
- 详情页 `rent_order_detail` 原在**底部常驻栏**「+添加套餐 / +添加单品 / ✓确认追加」。后端追加骨架已在：`Rental.appending`(bool?) / `append_commit_time` + `AppendRental`/`SaveAppendings`/`RemoveAppendingRental`/`EffectAppendingRentals`/`EffectRentOrder`。
- 关键发现：底部栏「添加套餐」绑 `selectPackage` 事件，而 `recept_package` 实际 emit 的是 `rentalsSelected` —— **事件名不匹配，旧底部栏追加套餐其实从没跑通**（解释了用户"没概念"）。

### 1.2 设计（用户确认的 4 点）
1. 入口从底部常驻栏 → 详情页内**独立卡片区**（入口按钮 + 已追加项简要信息）。
2. 点入口进**独立追加页**，录入"和开单一样的规则"（内嵌 `rent_recept_form`）。
3. 生效分流：**应付>0 → 支付成功后才生效**；**应付=0 → 二次确认后生效**。
4. 未确认草稿可**随时删除=放弃**。

### 1.3 详情页改动（`rent_order_detail`）
- 移除底部 `bottom-bar` + 旧 `onAddPackage`/`onAddItem`/`onConfirmAppend`（+ wxss `.bottom-*`、Card3 内旧「追加中」小列表）。
- `renderOrder` 把 `order.appendingRentals` 拆两态：`draftRentals`(`appending=true` 草稿) / `pendingRentals`(`appending=false` 待支付)。
- 新增「追加租赁商品」独立 Card（退款卡之后、订单未关闭显示）：入口按钮 `onOpenAppend`(跳 `rent_append`) + 草稿区(继续编辑/删除/放弃全部) + 待支付区(去支付/删除)。
- 新 handler：`onOpenAppend`、`onDiscardAllAppend`(逐个 RemoveAppendingRental)；`onDelAppendingRental` 改文案区分草稿/待支付 + 删完 `getData`。

### 1.4 新建独立追加页 `pages/admin/rent/rent_append`（4 文件 + app.json 注册）
- 内嵌 `rent-recept-form`，`onLoad(orderId)` 用 `getOrderByStaffPromise` 拉单（含 appendingRentals），购物车只装草稿。
- `_setOrder` 兜底补 rentItem 前端字段（class_name/categoryName/chooseCategories/pick_type，从 `it.category` 派生）+ **默认立即租赁**(pick_type=立即租赁 + 起租=今天当前时分 + atOnce 按 pick_type 派生)。
- 添加入口：套餐→`recept_package`→`AppendRental(packageId)`；单品→`AppendRental(categoryId&rentProductId)`；无码→`AppendRental`(无参=AppendBlank)。
- `onSyncRent`：实时保存 `SaveAppendings(commit=false)` + 检测左划删除 → `RemoveAppendingRental`。
- 「确认追加」(组件 checkout 事件)：前端预估应付押金分流 → 应付>0 `SaveAppendings(commit=true)` 跳结算页 / 应付=0 二次确认 modal 后 `SaveAppendings(commit=true)` 生效。

## 2. 后端追加链改动（`RentController.cs` / `OrderController.cs`）

| 改动 | 说明 |
|---|---|
| `EffectAppendingRentals` 索引 bug | 内层循环 `guaranties[i]`→`[j]`（误用外层索引），影响支付后给追加项关联押金 |
| `AppendPackage`/`AppendCategory` 补 `class_name` | 建草稿主项 rentItem 持久化品类名（修分类行空白） |
| `AppendPackage`/`AppendCategory` 默认立即租赁 | rental.pick_type=立即租赁 + start_date=DateTime.Now；rentItem.pick_type=立即租赁 + atOnce=true |
| `AppendRental` 放开"都不传"限制 | 原拒"添加为空"，改为都不传走 `AppendBlank`(无分类空白草稿=无码物品)；都传才"参数冲突" |
| `AppendRental` 加 `rentProductId` | `AppendCategory(categoryId, rentProductId)` 查 `rent_product` 拿 barcode/name 填主项 + noCode=false（搜索单品带编码） |
| `SaveAppendings` 加 `commit` 参数 | commit=false 只持久化草稿(保持 appending=true)、不提交/不生效；提交段(算应付+免押 EffectRental)用 `if(commit)` 包裹 |
| `SaveAppendingRental` 加 `commit` | `appending = commit?false:true`；`SyncRentalGuaranty` 只在 commit 时建押金 Guaranty(草稿阶段不建，避免删草稿残留) |
| `RemoveAppendingRental` 增强 | 删项时清该 rental 的 Guaranty(valid=0) + 重算 `order.paying_amount`(剩余待支付追加项未付 Guaranty 合计) |
| `EffectRental` atOnce 分支补库存 | 立即发放时 `rent_product.status="租赁中"`(item.rent_product_id 非空)，口径同 `SetRentItemStatus` |
| `OrderController.Refund` 全退款清草稿 | `refundAmount>0 && totalRentUnRefund==0` 时，清该订单 `appending=true` 未确认草稿(valid=0) |

## 3. payment_entry 多笔 payment 误判（微信 + 支付宝两端）

### 3.1 根因（用户诊断准确）
追加场景下订单有多笔 OrderPayment（原租赁押金已付 + 追加押金待付），`payment_entry` 用**订单聚合** `order.orderStatus=='支付成功'` 屏蔽支付 UI + 金额用聚合 `paying_amount`(追加场景为 0) → 顾客扫追加二维码显示「支付成功」无支付按钮、总计 ¥0。

### 3.2 修复（两端同构，纯前端）
- `renderData` 改为按**当前扫码的 paymentId** 选这笔 payment(带兜底)；需付/总计金额用**这笔 `payment.amount`**；新增派生 `order.payStatus = 当前这笔状态`，wxml/axml 4 处屏蔽判定 `order.orderStatus`→`order.payStatus`。
- 微信端：`snowmeet_wechat_mini/pages/order/payment_entry.{js,wxml}`。
- **支付宝端独立代码库** `alipay_snowmeet/pages/payment_entry/index.{js,axml}` 同步同款修复（要在支付宝开发者工具重编）。

### 3.3 详情页 showGoPay 连带放宽
- 待支付追加项重进详情页"如何支付"：待支付区加「去支付」按钮(`onGoPay`→结算页)；顶部 `showGoPay` 原用 `order.orderStatus` 聚合(追加待付时聚合成支付成功不显示)，放宽为 `有 pendingRentals 也显示`。

## 4. 退款多笔逐笔输入 + 储值排除 + 表格化

### 4.1 onRefund 重构（纯前端，后端 `Order/Refund` 本就收 refunds 数组）
- 收集可退 payment(`status=支付成功 && remain>0`)，**排除 `pay_method=='储值支付'`**(储值付租金、不参与退押金)。
- 单笔：直接退应退额；多笔+可退之和==应退：逐笔全额退(二次确认)；多笔+可退之和>应退：弹**逐笔输入 modal**。
- modal 列各笔可退 payment + 输入框，校验各笔不超可退、各笔之和==应退才可确认。

### 4.2 逐笔退款 modal 三列表格
- 用户要求"表格呈现省空间"：每笔从两行压成一行三列（支付方式 / 可退 / 实际退款输入框），加表头。

### 4.3 canConfirm 浮点 bug（用户报"待分配不为0却可确认"）
- 根因：`Math.abs(allocated - need) < 0.01` —— `0.02-0.03=0.00999…<0.01` 被误判已配平。
- 修复：改用四舍五入到 2 位的「待分配」**严格 `=== 0`**(`remainToAlloc === 0`)才可确认。

## 5. 列表支付方式不折行（`new_rent_list`）
- "方式"原与"支付金额"挤同一行、value 固定 160rpx → 多通道"支付宝/微信支付"折行。拆"方式"独占一行 + 整行宽度(`row-value--wide`) + `nowrap`(省略号兜底)。

## 关键改动文件

| 仓库 | 文件 | 改动 |
|---|---|---|
| snowmeet_wechat_mini | `pages/admin/rent/rent_order_detail/{js,wxml,wxss}` | 移除底部栏 + 追加卡片区(草稿/待支付/删除/去支付/放弃) + 退款多笔逐笔表格 modal + 储值排除 + 退款 canConfirm 修 |
| snowmeet_wechat_mini | `pages/admin/rent/rent_append.{js,wxml,wxss,json}` | 新建独立追加页(内嵌组件+加载+套餐/单品/无码+实时保存+确认分流+默认立即租赁) |
| snowmeet_wechat_mini | `pages/order/payment_entry.{js,wxml}` | 微信端多笔 payment 以当前 paymentId 为准 |
| snowmeet_wechat_mini | `pages/admin/rent/new_rent_list.{wxml,wxss}` | 支付方式独占一行不折行 |
| snowmeet_wechat_mini | `app.json` | 注册 rent_append |
| SnowmeetApi | `Controllers/RentController.cs` | AppendRental/AppendCategory/AppendPackage/AppendBlank + SaveAppendings/SaveAppendingRental commit + RemoveAppendingRental 清押金重算 + EffectRental 库存 + EffectAppendingRentals 索引修 |
| SnowmeetApi | `Controllers/OrderController.cs` | Refund 全退款清草稿 |
| alipay_snowmeet | `pages/payment_entry/index.{js,axml}` | 支付宝端多笔 payment 同步修复 |
| snowmeet_ai_doc | `docs/superpowers/specs/2026-06-28-rent-append-redesign-design.md` | 追加界面重组 spec |

## 学到的小知识

1. **追加用模式 P（后端 AppendRental 建草稿入库），不是前端构造**：`AppendCategory`/`AppendPackage` 直接 `AddAsync` 一个 `appending=true` rental。但后端建的草稿缺开单 `recept_package` 那套前端临时字段(class_name/categoryName/chooseCategories)，追加页加载时要从 `it.category` 兜底补齐(GetOrder 已 Include rentItems.category)。
2. **`SaveAppendings` 的 commit 参数是实时保存的关键**：旧后端不认 `commit` 会忽略它当默认提交(commit=true) → 每次编辑都把草稿提前"确认+生效"。**所以实时保存必须先部署后端、再重编小程序**(顺序依赖)。
3. **草稿阶段不建 Guaranty**：`SaveAppendingRental` 的 `SyncRentalGuaranty` 用 `if(commit)` 包裹，避免中途删草稿残留押金虚账；删草稿只需 valid=0，删待支付项才需清 Guaranty + 重算 paying_amount。
4. **`payment_entry` 多笔 payment 必须以当前 paymentId 为准**：订单聚合 `orderStatus`/`paying_amount` 在"原押金已付+追加待付"场景会误判当前这笔。这是 CLAUDE.md 早记的既知 bug(paymentId=42561)，本次彻底修(微信+支付宝两端)。
5. **支付宝端 `alipay_snowmeet` 是独立代码库**：微信端 payment_entry 修的同类 bug 必须单独同步过去，且在支付宝开发者工具单独重编。又一次印证此规律。
6. **`EffectRental` 的 atOnce 立即发放漏更新 `rent_product.status`**：库存更新逻辑原只在手动发放 `SetRentItemStatus`(已发放→租赁中/已归还→正常)。立即租赁生效走 `EffectRental` atOnce 分支只建"已发放"日志、没更新库存 → 补上同口径库存更新。`EffectRental` 是开单+追加三个生效点(4914/4816/6606)的共同出口。
7. **金额配平判定别用 `abs(a-b)<0.01` 容差**：`0.02-0.03=0.00999…` 会被误判为配平。要用四舍五入到 2 位后 `=== 0` 严格判等。
8. **同模板 + flag 复用**：`rent_recept_form` 同款 modal 用 `dc-*` 样式；逐笔退款表格复用 `dc-mask/dc-card/dc-actions`，只加 `rf-*` 列样式。
