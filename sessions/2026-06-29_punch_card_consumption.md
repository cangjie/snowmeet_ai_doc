# 2026-06-29 租赁订单详情页：次卡（punch_card）消费功能（plan 流程，前后端落地）

接 6-28 end-work 之后的新任务。用户要在租赁订单详情页退款区（截图红圈=「可用储值」行）加「次卡消费」：会员有租赁次卡时显示剩余次数 + 本次需扣次数，店员选卡核销，次卡抵含雪板雪鞋的租赁商品租金。走 plan mode 全流程（探索 → 4 个澄清问题 → plan 批准 → 实现）。代码在 `SnowmeetApi` + `snowmeet_wechat_mini`，**本地未提交**，用户按部署节奏处理；end-work 仅 doc 仓。plan 见 [`~/.claude/plans/punch-card-calm-wand.md`](file:///Users/cangjie/.claude/plans/punch-card-calm-wand.md)。

## 1. 探索结论（2 个 Explore agent）

- **EF 完全缺失**：`punch_card`(36 行) / `punch_card_used`(0→17 行，6-26 回补) 两表在库里存在，但 `Models/` 下无 C# 模型、`ApplicationDBContext` 无 DbSet。老「次卡支付」仅靠 `[order].pay_option='次卡支付'` 字符串标记。
- **字段语义**：`punch_card`：total=总次数、punches=已用累计（剩余=total−punches）、biz_type 区分租赁/养护。`punch_card_used`：biz_id→rental.id、punch_count=本次扣次数、**valid 是 bit**(连库 INFORMATION_SCHEMA 确认)、payment_id 可空。
- **储值付租金对照模板**：UI [`rent_order_detail.wxml:454-465`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml)（可用储值行+勾选）；JS `onTogglePayWithDeposit`/`_refundWithDeposit`/renderOrder 金额；后端 [`OrderController.PayWithDeposit:2974`](../SnowmeetApi/Controllers/OrderController.cs)。
- **雪板雪鞋判定**：`CODE_REQUIRED_PREFIXES=['01','02','03','04']`（双板/单板/双板鞋/单板鞋，`recept_package.js:10`）；rentItem.category.code 前两位判定。
- **租期天数**：rental_detail 是 rental 级按天（charge_type=租金 一天一条）；现成免除逻辑 `UpdateRentalDayChargesByStaff` waived 分支（`RentController.cs:5483`，`rentDetail.valid=0`）。

## 2. 用户拍板的 4 个设计决策

1. **扣次数天数口径**：实际计费天数（rental_detail charge_type=租金 valid=1 去重 rental_date）。
2. **覆盖范围**：次卡只覆盖含雪板雪鞋 rental 租金；与「储值付租金」**可叠加**（次卡付雪板、储值付非雪板）。
3. **多卡/不足**：**店员选卡** + 剩余不够**可部分用**。
4. **核销落库**：**直接免除**雪板租金 rental_detail(valid=0) + 写 punch_card_used + 扣 punches（不产生 OrderPayment）。

## 3. 后端改动（SnowmeetApi）

- 新建 [`Models/Rent/PunchCard.cs`](../SnowmeetApi/Models/Rent/PunchCard.cs)（`[Table("punch_card")]`，namespace `SnowmeetApi.Models`，`[NotMapped] remaining=total-punches`）+ [`PunchCardUsed.cs`](../SnowmeetApi/Models/Rent/PunchCardUsed.cs)（valid 用 bool 对 bit）；`ApplicationDBContext` 加 `punchCard`/`punchCardUsed` DbSet。
- `RentController.cs` 新增两接口（插在 `SetRentalEntertainByStaff` 后）：
  - `[HttpGet("{orderId}")] GetRentalPunchCardInfo`：返回 `{cards[], skiRentals[{rental_id,name,punchDays,rentalDates}], totalPunchNeed}`。含雪板判定 + 实际计费天数口径见上；`cards` 查会员 biz_type='租赁' && total>punches。
  - `[HttpPost("{orderId}")] UseRentalPunchCard`（body `{card_id, punch_count}`）：校验卡属会员+剩余够；所有含雪板雪鞋 rental 的 valid=1 租金 detail **按 rental_date 升序排队**，逐条 valid=0（`Entry().State=Modified` 防 NoTracking 静默不存）直到用满；按 rental 写 punch_card_used + CoreDataModLog(scene='次卡消费')；`card.punches += need`；返回 `GetOrder`。
- `dotnet build` 0 error。

## 4. 前端改动（snowmeet_wechat_mini）

- [`data.js`](../snowmeet_wechat_mini/utils/data.js)：`getRentalPunchCardInfoPromise` + `useRentalPunchCardPromise`（仿 payWithDepositPromise）+ export。
- [`rent_order_detail.js`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js)：getData 并行拉会员+次卡信息→`order.punchCardInfo`；renderOrder 派生 `totalRemaining`(Σ cards.remaining)；新增 `onTogglePunchCard`(选卡 modal)/`onPunchSelectCard`/`onPunchCountInput`/`onPunchModalCancel`/`onPunchModalConfirm`(二次确认→useRentalPunchCard→getData)；data 加 `punchModal`。
- [`.wxml`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml)：退款区「实际应退」行前加「次卡消费」行（`cards.length>0 && totalPunchNeed>0` 才显示，`剩余 X 次 · 扣 Y 次 ›`）+ 末尾选卡 modal（复用 dc-* 风格 + 单选卡 + 抵扣次数输入）。
- [`.wxss`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss)：pc-* 选卡弹窗样式。
- `node --check` 通过；wxml view 252/252 平衡。

## 关键发现 / 教训

1. **次卡是按次不按额**：核销 = 免除被覆盖的雪板租金 rental_detail(valid=0)，不产生 OrderPayment。核销后 getData 重拉，`renderOrder` 的 sumSummary(只累 valid=1)自动减少 → 应退押金自动增加，无需手动金额逻辑，天然与储值付租金叠加。
2. **"本次需扣"自反映剩余**：核销后雪板租金 detail valid=0 → totalPunchNeed 重算减少；全核销则归 0、行消失。不需要单独"已核销"状态。
3. **部分用分配规则**：店员选「抵 N 次」，后端把所有雪板 rental 的租金 detail 按 rental_date 升序排队逐天免除前 N 条，每个被触及 rental 写一条 punch_card_used(punch_count=被免天数)。比"每 rental 单独输入"简单。
4. **`punch_card_used.valid` 是 bit**：C# 用 bool（连库 INFORMATION_SCHEMA 确认，别想当然用 int）。
5. **NoTracking 老坑**：免除 rental_detail valid 翻转必须 `Entry().State=Modified`。
6. **Rental.cs 里的实体 namespace 是 `SnowmeetApi.Models`**（不是 Models.Rent，虽然文件在 Models/Rent/ 目录）；PunchCard 跟它一致放 SnowmeetApi.Models。

## 状态

- ✅ 前后端实现完成；`dotnet build` 0 error、`node --check` + wxml 平衡通过。
- 🚧 **待用户**：① publish SnowmeetApi（两新接口 + 模型，无库表变更——两表早已存在）② 重编 snowmeet_wechat_mini ③ 真机/模拟器端到端：会员有租赁卡的含雪板订单详情页退款区出现「次卡消费」行 → 选卡抵 N 次 → 核销后雪板租金归 0、应退押金增加、剩余次数减少；与储值付租金叠加；剩余不足时部分用。后端可本地起服务用真实 sessionKey 调 `GetRentalPunchCardInfo`/`UseRentalPunchCard` + DB 直查验证（参考 backfill 涉及的 member 15506/30868/30870）。
- ⏳ 仍开放：次卡核销**撤销**（误操作恢复 valid=1 + punch_card_used valid=0 + 回补 punches）第一版未做；与老 `pay_option='次卡支付'` 字符串路径并存不强行统一。
