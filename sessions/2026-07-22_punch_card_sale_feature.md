# 2026-07-22 租赁次卡销售功能：从零设计到前后端全量落地 + 订单详情/列表联动

按时间线整理。本场会话从一个小问题（食材过期提醒打印标签尺寸确认）开场，随后进入全场主线：从零设计并实现"租赁次卡销售"这个全新业务能力（此前次卡只能免费发放），历经 Plan Mode 澄清 + 一次关键用户纠正，落地完整前后端；随后同一会话内又追加了两轮衍生需求（订单详情页展示次卡销售、订单列表加角标+筛选），并穿插修复真机测试暴露的三个 bug。全部改动在 `SnowmeetApi` + `snowmeet_wechat_mini` 两代码仓，**本地未提交**，需要先跑一份 SQL 迁移再部署。

## 1. 开场：食材过期提醒打印标签尺寸确认（已解决，无后续）

用户询问食材过期提醒功能的打印标签尺寸，直接读 [`components/fnb/print_food_label/print_food_label.js`](../../snowmeet_wechat_mini/components/fnb/print_food_label/print_food_label.js) 确认为 60mm×40mm（`LABEL_WIDTH_MM=60`/`LABEL_HEIGHT_MM=40`，2026-07-21 那次会话定的）。无代码改动。

## 2. 主线：租赁次卡销售功能设计（Plan Mode）

### 2.1 需求澄清

用户提出："租赁退押金之前，可以像顾客推销租赁的次卡。租赁次卡可以做成一个商品，存放到 product 表中。顾客可以在小程序的页面上单独购买，也可以在租赁退押金的时候购买"，并给出五步流程（确认核销次数→核销数≤总次数→多退少补→支付/退款成功后建卡+核销→订单结构上一个 order 可挂多个 rental+一个或多个零售明细）。

Explore agent 并行研究现有代码后，用 AskUserQuestion 澄清四点：
- 财务公式：`应退押金 + 立即核销省下的租金金额`（用户选择推荐项）
- 购买渠道：顾客自助（不经店员）
- 权限：普通前台店员（title_level≥100）
- 补差价方式（多选）：微信/支付宝扫码支付、现金/其他方式手动确认、允许储值扣款

### 2.2 关键用户纠正（第一次 ExitPlanMode 被拒）

第一版计划提交审批时被拒，用户给出详细纠正："最关键的是随着租赁订单的结算，有个试算功能……然后需要等支付或者退款成功才能给当前顾客创建相应的次卡，然后核销掉当前订单的次数。如果顾客需要支付，或者退款均未成功，订单的状态应该不变，销售次卡的零售订单应该无效。然后再次退款的时候，如果未选择次卡，则还是和之前的流程一样。"

这确立了三条硬性规则：
1. 试算是纯只读，不产生任何写入
2. 钱没到位之前，不能建 `PunchCard`，不能核销
3. 不选次卡时，原有退押金流程完全不受影响

Plan 修订后（加入"试算"步骤 + 引入 `StartPunchCardSaleQr` 独立创建 pending 行的接口 + 状态机图）第二次提交获批，进入实现阶段（TaskCreate 11 个任务追踪）。

## 3. 后端实现（`SnowmeetApi`）

### 3.1 数据模型

- [`Models/Product.cs`](../../SnowmeetApi/Models/Product.cs)：加 `punch_total`（该 SKU 赠送的总次数，仅 `type=="租赁次卡"` 有意义）
- [`Models/Order/Retail.cs`](../../SnowmeetApi/Models/Order/Retail.cs)：加 `product_id`（关联购买的商品）、`punch_card_id`（结算完成后回填生成的卡）
- [`Models/Rent/PunchCard.cs`](../../SnowmeetApi/Models/Rent/PunchCard.cs)：加 `source_retail_id`（追溯是哪笔零售销售生成的）

配套 SQL 迁移 [`sql/2026-07-22_punch_card_sale.sql`](../sql/2026-07-22_punch_card_sale.sql)（新增列 + 三个外键约束），**必须先在生产库执行再部署后端**。

### 3.2 `RentController.cs`

先做代码提取（减少重复+顺手修一个既存 bug）：
- `BuildSkiRentPunchQueue`：从 `GetRentalPunchCardInfo`/`UseRentalPunchCard` 里提取的共享逻辑，查出符合条件的雪板/雪鞋类租赁物的租金明细行。**顺手修复**：旧逻辑是"每个 rental 内部按日期排序，rental 之间按遍历顺序拼接"，改成**全局按 `rental_date` 排序**——这个功能里"到底核销哪几天"直接关系到钱，必须全局排序才对
- `WriteOffSkiPunches`：翻转 `rental_detail.valid=0` + 插入 `PunchCardUsed` + 更新 `card.punches` 的共享写入逻辑

新增六个接口：
- `GetPunchCardProducts(shop)`：会话级（无需 staff 权限），浏览可购买的次卡商品，`type=="租赁次卡" && valid==1 && on_shelves==1 && punch_total!=null`
- `GetMyPunchCards`：解析顾客自己的会话，返回其名下的次卡
- `PreparePunchCardSale(orderId, productId)`：只读试算，返回本单应核销次数、次卡总次数、立即免除租金、核销前应退押金、总收益、次卡价格、差价（多退/需补）
- `StartPunchCardSaleQr(orderId, {productId})`：创建一个 `valid=0` 的 pending `Retail` 行，代表"一次购买尝试已发起、钱还没到"；不在内部调用 `GetWepayPayment`（返回类型是嵌套的 `ActionResult<ActionResult<...>>`，处理起来别扭），而是让前端直接调用现成的 `Order/GetWepayPayment`/`GetAlipayMiniPayment`（带 `amount=priceDiff` 覆盖参数）
- `FinalizePunchCardSale(orderId, {productId, settlement})`：幂等守卫（同一 order+product 已有 `valid=1` 的 retail 就直接返回）→ 重新计算试算数字（不信任客户端）→ 身份核验门槛（`wechat_unverified` 检查）→ 四种结算腿之一（qr 校验已有支付成功记录/refund 走 `RefundCore`/cash 直接建支付成功记录/deposit——后来被删除，见 §5）→ 建 `PunchCard` + 调 `WriteOffSkiPunches` 核销 + 回填双向外键，全部在同一个 `SaveChangesAsync()` 事务里

### 3.3 `OrderController.cs`

- 抽出两个 `[NonAction]` 方法供 `RentController` 直接调用：`RefundCore`（原 `Refund` action 的核心逻辑）、`AllocateRefundAcrossPayments`（贪心分摊退款金额到多笔支付记录）
- `GetOrder`：`type=="租赁"` 分支补上加载 `order.retails`（此前从未加载——一个租赁订单理论上也可能挂零售明细）
- `GetCommonOrders`：`case "租赁":` 的 Include 链同样补上 `retails`（供订单列表页使用）
- `PlaceOrder` 的"零售"分支：当 `retail.product_id != null` 时，价格从服务端 `Product.sale_price` 取，不信任客户端传的价格（这条只影响带 `product_id` 的行，不影响现有"店员手输价格"的零售单）
- `DealSuccessPaidOrder`：新增"零售"分支——支付成功后遍历 `order.retails` 里 `product_id!=null && punch_card_id==null` 的行，自动建 `PunchCard` 并回填（`punch_card_id==null` 是天然的幂等守卫，防止支付回调重复触发时重复发卡）

## 4. 前端实现（`snowmeet_wechat_mini`）

- [`pages/admin/rent/rent_order_detail/`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/)：退押金卡片里插入"推荐次卡"入口，点开是三步弹窗（选卡 → 试算展示 → 根据 priceDiff 正负选结算方式），扫码结算腿有独立的二维码 + 2 秒轮询逻辑
- 新建 `pages/mine/punchcard/my_punchcards`（顾客自己的次卡列表）+ `pages/mine/punchcard/punchcard_shop`（顾客浏览+下单购买，走通用结算页）
- "我的"页新增"我的次卡"入口
- 新建 `pages/admin/rent/punchcard_products/`（店长≥200 权限，管理次卡商品的名称/价格/次数/上下架/店铺，复用现成的 `Category/AddProduct`/`ModProduct` 而不是新造接口）
- `utils/data.js` 新增 7 个 promise 封装函数

## 5. 真机反馈修复三轮

### 5.1 `priceDiff` 显示浮点尾数

用户截图显示"需补差价 ¥0.00999999999999998"。定位到 `ComputePunchCardSaleCalc` 里 `priceDiff = product.sale_price - calc.totalBenefit` 是裸 `double` 相减。修复：`freedRentValue`/`refundableDepositBeforeCard`/`totalBenefit`/`priceDiff` 全部套 `Math.Round(x, 2)`。

### 5.2 用户明确要求移除储值支付选项

用户："购买次卡，不允许储值支付。" 前端删掉"储值扣款"按钮及对应 JS 分支；后端 `FinalizePunchCardSale` **整段删除** `deposit` 结算分支（不只是隐藏前端入口，服务端也明确拒绝 `method=="deposit"`，走到 `else` 分支返回"未知的结算方式"）。顺带确认顾客自助购买（走通用 `order-payment` 组件）本来就没有储值支付入口，无需额外改动。

### 5.3 `order_type` NOT NULL 违反

真机报错：`StartPunchCardSaleQr` 500，SQL 异常 `Cannot insert the value NULL into column 'order_type'`。定位：`Retail.order_type` 是 `string?`（C# 默认 `null`），但 DB 列是 `NOT NULL`。用户直接指示："这里的 order_type 设置为'租赁附加'"。修复了三处 `new Retail()`：`StartPunchCardSaleQr` 的 pending 行、`FinalizePunchCardSale` 的 cash/refund 分支、以及顺带发现的**顾客自助购买路径**（`OrderController.PlaceOrder` 的"零售"分支，此前完全遗漏——如果不修，顾客第一次买次卡就会同样报错）。

## 6. 追加需求一：订单详情页展示次卡销售

用户："租赁订单详情页，如果当前订单的子订单，包含了次卡零售，则在订单详情页当中应该有所体现。请重新设计一下界面，付款、消费金额、退款需要可以正确体现。"

先用 Explore agent 做了一轮彻底调研，核心发现：
- `Order.cs` 上 `totalRentSummaryAmount`/`totalRentNeedToRefundAmount`/`totalRentUnRefund` 等核心租赁数字都**只算 `rentals`，从不含 `retails`**——但仔细推演发现这其实是**正确的**：次卡的售价是独立的零售消费，混进"总计租金"/"应退押金"反而是错的
- 真正的问题是：完全没有地方能看到这笔次卡销售；"购买次卡多退"这种因为次卡交易产生的退款，会无声地混进"已退金额"这个通用数字里，让店员看不出这笔钱去哪了

设计方案（无需破坏既有口径，只做"补充展示 + 显式标注"）：
1. `GetOrder` 补 `.Include(r.product).Include(r.punchCard)` 让前端能拿到商品名/卡信息
2. `FinalizePunchCardSale` 把结算细节写进 `retail.memo`（例如"购买『万龙10次卡』次卡（共10次，¥300.00）；本单核销1次；扫码支付补差价 ¥50.00"），这样订单详情页只需要展示这行 memo 就自带完整可读记录，不需要再去反查支付/退款表拼凑
3. 前端新增只读的"次卡销售"列表区块，展示每笔销售的商品名+价格+memo+时间
4. 支付信息卡片加一行"其中含购买次卡多退 ¥X"的提示，用 `reason=='购买次卡多退'` 精确过滤退款记录

## 7. 追加需求二：订单列表加"零"角标 + 筛选

用户："租赁订单的列表页，如果当前订单，包含零售的子订单，增加'零'icon，同时可以跟据包含 不包含 全部 筛选。"

- `Order.cs` 新增 `[NotMapped] hasRetail`（`retails.Any(r=>r.valid==1)`），与 `haveDiscount`/`haveWarranty` 同一模式，无需前端 JS 计算，直接随订单序列化下发
- `GetCommonOrders`"租赁"分支的 WHERE 子句加对称的三态过滤 `hasRetail == null || hasRetail == o.retails.Any(...)`，紧邻既有的 `useCard` 判断写法
- `GetOrdersByStaffPaged` 加 `hasRetail` 参数透传给 `GetCommonOrders`
- 前端 `new_rent_list` 新增"零售"三态筛选行（复制"次卡"/"减免"筛选的既有模式）+ 标签列新角标"零"（青色 `#cffafe`/`#0e7490`，与"质"标签同配色方案）
- `utils/data.js` 的 `getRentOrdersByStaffPagedPromise` 加 `hasRetail` 参数（插在末尾，紧邻 `pageIndex`/`pageSize` 之前，避免打乱已有 24 个位置参数的顺序）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Models/Product.cs`](../../SnowmeetApi/Models/Product.cs) | 加 `punch_total` |
| [`SnowmeetApi/Models/Order/Retail.cs`](../../SnowmeetApi/Models/Order/Retail.cs) | 加 `product_id`/`punch_card_id`，导航属性 |
| [`SnowmeetApi/Models/Rent/PunchCard.cs`](../../SnowmeetApi/Models/Rent/PunchCard.cs) | 加 `source_retail_id` |
| [`SnowmeetApi/Models/Order/Order.cs`](../../SnowmeetApi/Models/Order/Order.cs) | 新增 `hasRetail` 计算属性 |
| [`SnowmeetApi/Controllers/RentController.cs`](../../SnowmeetApi/Controllers/RentController.cs) | 提取 `BuildSkiRentPunchQueue`/`WriteOffSkiPunches`；新增 6 个次卡销售接口 |
| [`SnowmeetApi/Controllers/OrderController.cs`](../../SnowmeetApi/Controllers/OrderController.cs) | 抽出 `RefundCore`/`AllocateRefundAcrossPayments`；`GetOrder`/`GetCommonOrders` 加载 retails + hasRetail 过滤；`PlaceOrder`/`DealSuccessPaidOrder` 零售分支改造 |
| [`snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/) | 卖卡 UI 三步弹窗 + 次卡销售展示区块 + 支付卡片提示行 |
| `snowmeet_wechat_mini/pages/mine/punchcard/{my_punchcards,punchcard_shop}` | 新建：顾客自助购买+查看 |
| `snowmeet_wechat_mini/pages/admin/rent/punchcard_products/` | 新建：次卡商品管理页 |
| [`snowmeet_wechat_mini/pages/admin/rent/new_rent_list.*`](../../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js) | 「零售」三态筛选 + 「零」角标 |
| [`snowmeet_wechat_mini/utils/data.js`](../../snowmeet_wechat_mini/utils/data.js) | 新增 7 个 promise 封装 + `getRentOrdersByStaffPagedPromise` 加 `hasRetail` 参数 |
| [`snowmeet_ai_doc/sql/2026-07-22_punch_card_sale.sql`](../sql/2026-07-22_punch_card_sale.sql) | 新建：数据库迁移脚本 |

## 学到的小知识

1. **"钱没到位、资产不能创建"状态机**：任何"顾客要花钱才能拿到的东西"，设计上要分清"只读试算 / 异步待收款 pending / 已收款确认建资产"三个阶段，每阶段允许写的数据范围完全不同——这是这场会话里被用户明确纠正过一次的核心教训，值得作为未来同类功能的默认设计起点
2. **核心业务数字不要强行囊括所有相关金额**：`总计租金`/`应退押金` 这类订单级汇总不含次卡销售金额是正确的，而不是遗漏——遇到"这个数字好像该包含 X 却没包含"时，先想清楚 X 在业务语义上是否真的属于这个汇总，而不是默认往里塞
3. **`Retail.order_type` 是 `NOT NULL` 列但模型默认 `null`**：这类 DB 强约束与 C# 默认值不一致的坑，本仓库已经在 `punch_card`/`customer_open_date` 上踩过多次，新建带外部约束的实体时要显式核对每个字段
4. **金额做加减法展示前必须 `Math.Round(x, 2)`**：`double` 直接相减极易产生浮点尾数直接暴露给用户
5. **`GetWepayPayment` 返回类型是嵌套的 `ActionResult<ActionResult<...>>`**：从其它 controller 内部调用会很别扭，与其硬解包装，不如让前端直接调用现成的 HTTP 接口（带参数覆盖），保持每个接口职责单一
