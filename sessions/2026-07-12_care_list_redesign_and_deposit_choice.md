# 2026-07-12（续） 养护列表重设计+分页 + 列表布局微调 + 养护开单储值选择意向

按主题整理。接续同日「养护详情页重设计」会话，本场三件事全围绕养护：①养护订单列表仿租赁列表重做+加分页；②列表布局两处微调；③养护开单页加「显示储值+勾选是否用储值」。前两件纯前端（`snowmeet_wechat_mini`），第三件前后端 + 需生产库加列。

## 1. 养护订单列表重设计 + 分页

### 1.1 需求 + 现状

用户：「养护订单列表页，仿照租赁订单列表页的样式，增加分页组件，其他的查询条件和旧版保持一致，只是样式修改。」

- 旧养护列表 [`care_order_list`](../snowmeet_wechat_mini/pages/admin/care/care_order_list.js)：`fui-card`/`fui-row`/`fui-col` 三栏布局；旧非分页接口 `getOrdersByStaffPromise`（一次拉全部）；查询条件 店铺/日期/测试/招待/减免/非雪季/次卡/手机/备注。
- 样式蓝本 [`new_rent_list`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.wxml)：Alpine 风格（`#f8f9ff` 背景 + 白卡 + 头部订单号/状态chip + 左标签列 + 右详情行）+ `date-range-picker` + `list-pager` 分页组件 + 后端分页接口 `getRentOrdersByStaffPagedPromise`。

### 1.2 关键判定：后端零改动

核实 `getRentOrdersByStaffPagedPromise`（[data.js:432](../snowmeet_wechat_mini/utils/data.js#L432)）参数与旧非分页接口**完全一致**（含 `haveWarranty`/`isSummerCare`/`useCard`），只尾部多 `pageIndex/pageSize`；且接的是**通用后端** `Order/GetOrdersByStaffPaged`（[OrderController.cs:1093](../SnowmeetApi/Controllers/OrderController.cs#L1093)），`type` 参数区分业务。后端 `GetOrdersByStaffPaged` 与旧接口共用底层 `GetCommonOrders`，同样支持养护的 `isSummerCare`（cares.biz_type=='非雪季养护'）/`useCard`/`haveWarranty`。分页方法内部 `OrderByDescending(biz_date)` + Skip/Take + `RendOrderList`。→ **养护列表直接复用该 promise 传 `type='养护'`，后端零改动、data.js 零改动**。

### 1.3 实现（4 文件全重写）

- **js**：queryOptions 保留养护 5 项（isTest/isEntertain/haveDiscount/summer/useCard，去掉旧版死值 haveWarranty）；分页字段 total/page/pageSize/totalPages；`onShow` 用 `this.data.page/pageSize` 重查（返回列表保留页码）；`getData` 调 `getRentOrdersByStaffPagedPromise(..., '养护', ..., page, pageSize)`；`renderOrders` 派生 状态chip（`_statusClass`：正常订单→normal / 临时订单→temp）、支付方式拼接去重（储值/次卡单列标签）、装备照片缩略图 thumbs、本页收款累加；`onPagerChange` 统一回调；`gotoDetail` 临时订单不可点。
- **wxml**：仿 new_rent_list 结构；筛选行 店铺/日期(date-range-picker)/测试/招待/减免/非雪季/次卡/手机/备注（去租赁的状态/租赁物）；标签列加【质】haveWarranty + 【非】isSummerTask；详情行 日期/时间/顾客/手机/方式/支付金额/退款/总计收款/装备数量/项目/开单人/备注；首尾两端 list-pager。
- **wxss**：复用 new_rent_list 全部 + 加 `.tag--warranty`(青)/`.tag--summer`(琥珀)/`.status-chip--normal`(绿)/`.care-thumb`。
- **json**：注册 date-range-picker + list-pager（shop-selector/van-button 全局注册，无需加）。

### 1.4 状态取值核实

`careProperties.orderStatus`（[Order.cs:1225 CarePropertySet](../SnowmeetApi/Models/Order/Order.cs)）只有 **「临时订单」/「正常订单」** 两值（L1238/1242），与订单级 `order.orderStatus`(支付状态)是两个不同物。养护列表状态 chip 只这两态；临时订单不可进详情（旧版同逻辑）。

## 2. 列表布局微调

用户：「订单列表，时间和退款，另起一行显示，图片统一放到订单列表的最右侧。」

- **时间/退款各自独立成行**：原「日期+时间」同行双列、「支付金额+退款」同行双列 → 拆成各自单行（日期一行/时间一行、支付金额一行/退款一行），所有行统一「标签+值」单列。
- **图片移到卡片最右侧竖排**：从原卡片底部横排（`.care-thumbs` flex-wrap）改到 `order-body` 内最右侧竖排列（`.order-photos`，宽 160rpx、缩略图 150rpx 靠右）。卡片变三列：标签列 + 详情行(flex) + 照片列。

## 3. 养护开单储值选择意向

### 3.1 需求澄清（用户拍板缩小范围）

用户：「养护开单界面，如果用户有储值金额，需要显示储值金额并且让店员选择，是否可以使用储值。」

探索后发现储值支付流转有多种设计（直接扣款 vs settle 加选项、储值不足处理），用 AskUserQuestion 确认，用户回答关键点：
- **结算流程**：「结算的问题比较复杂，下一个计划我们会详细规划。目前就是显示顾客的储值，然后店员可以选择用储值支付即可。点去结算之后，让系统可以知道当前订单选了或者没选用储值支付可以了。后续储值，卡券的核销都需要顾客验证身份，我们下一步会专门来讨论。」→ **本期只做 显示+勾选+落库意向，不做实际扣款**。
- **储值不足**：「允许部分储值+补其他」→ 因此复选框**不因储值不足禁用**（本期只记意图）。
- **UI 落点**：底部结算条上方。

### 3.2 能力边界核实

- 会员条 [`reception_member_bar`](../snowmeet_wechat_mini/components/reception/reception_member_bar/reception_member_bar.js) 已拉 `getMemberAssetsByStaffPromise`(depositTotal) 显示储值 chip。
- `PayWithDeposit`（[OrderController.cs:3172](../SnowmeetApi/Controllers/OrderController.cs#L3172)）对养护：会员 + 储值余额 ≥ **全额**应付 → 扣款 + EffectCareOrder；**不支持部分抵扣、散客不行**。本期不调它。
- settle 的 [`order-payment`](../snowmeet_wechat_mini/components/order-payment/index.js) 只微信/支付宝/其他，无储值。
- 养护结算流程：care_recept_form checkout → recept_new `_checkoutCare` → `Order/PlaceCareOrder` → settle。

### 3.3 落库字段抉择

`order.pay_option`（string 默认「普通」）已被「招待/挂账/次卡支付」占用且参与查询过滤 → 复用会污染。→ 新增订单级专门字段 `pay_with_deposit`(bool)，为下一步核销铺路。

### 3.4 实现（前后端）

- 前端 [`care_recept_form`](../snowmeet_wechat_mini/components/reception/care_recept_form/care_recept_form.js)：`memberId` observer → `_loadDeposit` 拉 depositTotal（实例字段 `_lastDepositMemberId` 防重复+丢弃过期）；data 加 `hasDeposit/depositAvailableStr/useDeposit`；结算条上方 `.deposit-bar`（`wx:if="{{hasDeposit}}"`，储值余额 + 「使用储值支付」复选框，点整行 `onToggleUseDeposit`）；换人无储值自动清 useDeposit；`onCheckout` emit `{cares, useDeposit}`。
- 前端 [`recept_new.js`](../snowmeet_wechat_mini/pages/admin/reception/recept_new.js)：`onCheckout` maintain 分支 `this._checkoutCare(!!e.detail.useDeposit)`；`_checkoutCare(useDeposit)` 的 PlaceCareOrder URL 加 `&useDeposit=`。
- 后端 [`Order.cs`](../SnowmeetApi/Models/Order/Order.cs)：`pay_with_deposit`(bool default false)；[`PlaceCareOrder`](../SnowmeetApi/Controllers/OrderController.cs#L2969)：加 `bool useDeposit=false` 参数，order.valid=1 段写 `order.pay_with_deposit=useDeposit`。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `pages/admin/care/care_order_list.{js,wxml,wxss,json}` | 4 文件全重写：仿租赁 Alpine 样式 + 分页组件 + 时间/退款独立行 + 照片右侧竖排 |
| `components/reception/care_recept_form/care_recept_form.{js,wxml,wxss}` | memberId 拉储值 + 结算条上方储值行/复选框 + checkout 带 useDeposit |
| `pages/admin/reception/recept_new.js` | onCheckout/_checkoutCare 透传 useDeposit → PlaceCareOrder URL |
| `SnowmeetApi/Models/Order/Order.cs` | +`pay_with_deposit`(bool) |
| `SnowmeetApi/Controllers/OrderController.cs` | PlaceCareOrder +`useDeposit` 参数写入 |

## 学到的小知识

1. **`getRentOrdersByStaffPagedPromise` 名带 Rent 实为通用分页接口**：接 `Order/GetOrdersByStaffPaged`，`type` 区分业务；底层 `GetCommonOrders` 早已支持全业务查询参数。养护/零售/雪票列表都可复用，无需各写分页接口。
2. **`careProperties.orderStatus` 只有「临时订单/正常订单」两值**：与订单级 `order.orderStatus`(支付状态)是两物；养护列表状态 chip 只两态。
3. **`PagedOrderResult` 只返回 items+total(条数)**：无全量金额聚合，分页列表金额统计只能本页累加，措辞标「本页收款」避免误导。
4. **`PayWithDeposit` 对养护只全额扣款**：会员 + 储值 ≥ 全额；不支持部分抵扣、散客不行。本期只记意向字段不调它。
5. **`order.pay_with_deposit` 需先加列再部署**（同 customer_open_date/pay-列族教训）：EF 加字段后所有 order 查询 SELECT 该列，不先 `ALTER TABLE [order] ADD pay_with_deposit BIT NOT NULL DEFAULT 0` 会让 order 查询全挂。
6. **需求缩小范围要先用 AskUserQuestion 确认**：储值支付流转有多种设计（直接扣款/settle 选项、不足处理），猜错返工大；本场问后用户明确「本期只显示+勾选+记录意向，扣款/核销下一步专门规划」，工作量大幅缩小。
