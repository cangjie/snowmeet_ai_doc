# 2026-06-30 次卡消费打磨（复选框/核验/申请退款核销/卡标签）+ 会员管理 v1（plan 流程）

接 6-29 次卡消费首版。本会话两大块：① 次卡消费按用户反馈多轮打磨；② 全新「会员管理」功能（plan mode 全流程）。代码在 `SnowmeetApi` + `snowmeet_wechat_mini`，**本地未提交**，用户按部署节奏处理；end-work 仅 doc 仓（含 sql/ + templates/member 设计稿）。

---

## 一、次卡消费打磨（rent_order_detail，前后端）

6-29 首版是「退款区一个『扣 N 次 ›』按钮、点了立即核销」。本会话按用户反馈逐条改：

1. **次卡消费改复选框（可选，同储值付租金）**：从「扣 N 次 ›」按钮改成与「储值付租金」同款复选框（✓ + 锁定）。
2. **微信身份核验门槛（次卡也要核验本人，同储值）**：勾选次卡先过微信核验（`wechat_unverified==1` 即已核验）；`_openWechatVerify(purpose)` 加 `purpose`('deposit'/'punch')，核验通过后按 purpose 分流（次卡→弹选卡弹窗、储值→预览），二维码弹窗提示文案 `_verifyTip` 动态。
3. **储值/次卡 全归还后才可点击**：`onTogglePayWithDeposit`/`onTogglePunchCard` 加 `order._allRentalsReturned` 守卫 + 复选框未全归还时置灰。
4. **核销移到「申请退款」时操作**：次卡从「立即核销」改成**勾选预览**（同储值）——`onPunchModalConfirm` 只记 `punchCardSelection{card_id,punch_count,freedRent}` + renderOrder 预览（被免雪板租金加回应退），真正核销在 `onRefund` 时链式跑 `_runWriteoffAndRefund`：① `UseRentalPunchCard`(免雪板租金) → ② `PayWithDeposit`(储值付剩余) → ③ `refund`(退押金，用页面预览额 + `_allocateRefund` 贪心分配)。预览叠加口径：勾储值→加回 sumSummary（储值兜全部）；仅次卡→加回 freedRent（雪板那部分）。
5. **无应退时按钮变「确认核销」**：`order._pendingWriteoff`(储值/次卡待核销) → 应退>0 显「申请退款 ¥X」、应退=0 但有待核销显「确认核销」、都没有则灰。
6. **已核销 N 次显示 + 后端 usedPunches**：⚠️ 6-29 那次加 `usedPunches` 的 edit **被消息打断没真写进文件**（本会话查 RentController 才发现），本次补上——`GetRentalPunchCardInfo` 返 `usedPunches`（该订单 punch_card_used valid 求和，正常+无会员两路径都加）；前端次卡行 wx:if 不再被 `cards.length>0` 卡死（改 `(有卡&有需扣) || usedPunches>0`），值三态：`已核销 N 次`/`抵 N 次`(预览)/`剩余 X 次`。验证：用户测试单 71808 有 2 条 punch_card_used 但 rental.use_card=0 → 这正是「核销了却不显示/筛不到」的根因。
7. **储值支付时间显示 1970-01-01（修）**：根因 `DepositController.ConsumeDeposit` 置「支付成功」时**漏写 `paid_date`** → 前端支付明细 `new Date(null)`→epoch。修 ConsumeDeposit 补 `payment.paid_date=DateTime.Now`（所有储值消费入口统一修）；前端支付明细 `paid_date` 为空时回退 `create_date`（历史记录不用刷库也对）。
8. **订单查询 次卡=包含 兼容 punch_card_used**：列表 `OrderController.GetCommonOrders` 次卡过滤（租赁+养护两 branch）从 `useCard==rentals.Any(use_card==true)` 改成 `useCard==(rentals.Any(use_card) || EXISTS punch_card_used(order_id&valid))`。旧规则保留、全部/包含/不含 语义不变。连库实证 71808（old_use_card=0 但 used=2）→ 之前筛不到，修后命中。
9. **列表「卡」标签**：WXML 早有 `{{item.useCard}}`→蓝色「卡」标签但从没赋值。后端 `Order` 加 `[NotMapped] usePunchCard`，`GetOrdersByStaffPaged` 分页后批量查 punch_card_used 标记本页；前端 `new_rent_list.renderOrders` 设 `order.useCard = usePunchCard || pay_method=='次卡支付'`。

**关键发现/教训**
- **次卡按次不按额、预览+申请退款核销与储值叠加**：核销=免雪板租金 detail valid=0，getData 重拉 sumSummary 自动减；储值在剩余非雪板上付。
- **金额配平/分配**：`_allocateRefund` 贪心填可退支付（排除储值支付）；预览 freedRent = skiRentals 各 rentalDates 合并按 date 升序前 N 天 amount。
- **`punch_card_used.valid` 是 bit→bool**；`ConsumeDeposit` 漏 paid_date 是「储值支付时间 1970」根因。
- **被打断的 edit 要回查落没落**：6-29 的 usedPunches edit 没生效，本次靠读源码才发现补上 → 关键改动后顺手 grep 确认。

---

## 二、会员管理 v1（plan mode 全流程，新功能）

设计稿 `snowmeet_ai_doc/templates/member/`（list/detail/register/tag-sheet 4 屏 + shared 令牌，Alpine `#006495`+Lexend）。需求：会员按**姓名/电话/参与业务**搜索、维护**标签**、给单会员**加储值/次卡/优惠券**、**店长/管理员手机号注册会员**。plan：[`~/.claude/plans/punch-card-calm-wand.md`](file:///Users/cangjie/.claude/plans/punch-card-calm-wand.md)。

### 后端勘察拍板的关键偏差（设计稿 vs 现实）
- **储值**：生产 `deposit_account` 只有单一 `type='服务储值'`（设计稿 A/B/C 三类不存在）。用户拍板：**未来 ABC、目前只 C，API 留 depositType 接口**。
- **标签**：无任何 tag 表 → 新建 `member_tag`（会员实际标签）+ 后来 `member_tag_preset`（标签库字典）。系统标签=参与业务**派生**（order.type 去重，不入库）。
- **龙珠**：表是 `user_point_balance`（`Point` 模型映射），v1 只读展示。
- **次卡**：`punch_card`，预置卡种（租赁10/20次、养护单项/双项10次）下拉发放。
- **优惠券**：`ticket_template`(模型只映射 id/type/name/memo/hide/miniapp_recept_path/expire_date **子集**，无 biz_type/currency_value/valid)+`ticket`(无 amount/points 映射,有 member_id)。`TicketController.GenerateTickets` 生成的是**待领空券**(不绑 member)→ 发券给指定会员需**自建 Card+Ticket 直绑 member_id**(GetMemberTickets 按 member_id&valid&is_active 读)。
- **权限**：`staff.title_level≥200`（店长/管理员）。
- **member 3.2 万行** → 列表分页 + 派生只对当前页算。

### 后端实现
- 新表+模型：[`MemberTag.cs`](../SnowmeetApi/Models/Member/MemberTag.cs)(`[Table member_tag]`) + [`MemberTagPreset.cs`](../SnowmeetApi/Models/Member/MemberTagPreset.cs)(`[Table member_tag_preset]`,tag/group_name/sort/valid) + ApplicationDBContext 两 DbSet。
- 新建 [`MemberAdminController.cs`](../SnowmeetApi/Controllers/MemberAdminController.cs)（全 title_level≥200）：`SearchMembersByStaff`(分页,姓名 LIKE/手机 MSA LIKE/性别/参与业务 EXISTS order/自定义标签 EXISTS member_tag;只对当前页批量派生 cell/储值合计/龙珠/系统标签/自定义标签) / `GetMemberDetailByStaff`(资料+储值按type分组+龙珠+系统/自定义标签+绑定账户MSA+最近订单轻量直查+名下次卡) / `AddMemberTag`+`RemoveMemberTag`(软删) / `GetTagLibrary`(读 member_tag_preset) / `RegisterMemberByPhone`(GetWholeMemberByNum 查重→建 Member valid=1 source='店员注册'+BindMemberMainCellNum) / `ChargeMemberDeposit`(包 DepositController.DepositCharge,depositType 留接口、落"服务储值") / `GrantPunchCard`+`GetPunchCardPresets`(punch_card distinct) / `GrantCoupon`(自建 Card+Ticket 直绑 member_id,valid=1 is_active=1)+`GetCouponTemplates`。
- `dotnet build` 0 error。

### 前端实现（snowmeet_wechat_mini）
- [`data.js`](../snowmeet_wechat_mini/utils/data.js) 11 个 promise（search/detail/tagLibrary/add+removeTag/register/charge/grantPunch/punchPresets/grantCoupon/couponTemplates）。
- 新页 `pages/admin/member/`：`member_list`(折叠筛选+会员卡+list-pager+onShow保参重查) / `member_detail`(资料/储值龙珠/标签/绑定账户/最近订单/名下次卡 + 标签编辑弹层 + 充值/加次卡/发券三弹窗) / `member_register`(手机号检测→已存在/新建→完成态)。图标全 van-icon。
- 标签库**DB 驱动**：两页 onLoad 拉 `getTagLibraryPromise` 填 `presetTags`（删掉原写死的 `PRESET_TAGS`）。
- [`app.json`](../snowmeet_wechat_mini/app.json) 注册 3 页 + [`admin.js`](../snowmeet_wechat_mini/pages/admin/admin.js)/[`admin.wxml`](../snowmeet_wechat_mini/pages/admin/admin.wxml) 加「会员管理」入口（`member_list` case）。
- 全 `node --check` + wxml 平衡。

### 建表 + 验证
- `member_tag` **用户手动建好**（安全分类器拦了 AI 对生产库 CREATE TABLE）；`member_tag_preset` SQL 已落 [`sql/2026-06-30_member_tag_preset.sql`](../snowmeet_ai_doc/sql/2026-06-30_member_tag_preset.sql)（含 13 标签 seed，三组）待用户建。`member_tag` DDL 备忘 [`sql/2026-06-30_member_tag.sql`](../snowmeet_ai_doc/sql/2026-06-30_member_tag.sql)。
- 只读核对：`member_tag` 列与模型一致；复跑 SearchMembersByStaff 核心 SQL 命中 member 15506(苍杰)——储值 ¥3772.04/龙珠 340/参与业务 4 种/标签 0，派生口径全对。

**关键发现/教训**
- **安全分类器拦 AI 对生产库 DDL**：授权只在 plan 文件/问句不够，需用户明确 in-message 授权或用户自己跑。用户手动建表收尾。
- **DB schema 常比 C# 模型新（又一例）**：TicketTemplate/Ticket 模型只映射子集，发券只能用已映射字段（无 amount/points/currency_value）。
- **GenerateTickets 不绑 member**：发券给指定会员要自建 Ticket 直绑 member_id。
- **3.2 万会员列表**：派生（参与业务/储值/龙珠/标签）只对当前页 N 条批量算，不全表聚合。
- **标签两层分清**：member_tag_preset=可后台维护的标签库字典；member_tag=会员实际标签。

---

## 状态
- ✅ 两块前后端完成：`dotnet build` 0 error、前端全 `node --check`+wxml 平衡；`member_tag` 已建、查询逻辑经真实数据验证。
- 🚧 **待用户**：① 生产库建 `member_tag_preset`（SQL 已给）② **publish SnowmeetApi**（次卡打磨的后端：usedPunches/ConsumeDeposit paid_date/次卡筛选/usePunchCard 标签/退押金状态；+ 会员管理 MemberAdminController+模型+DbSet）③ 重编小程序（次卡复选框/核验/申请退款核销/卡标签 + 会员管理 4 页 + 入口）④ 真机端到端：次卡消费全链路 + 会员管理搜索/详情/标签/充值/发卡/发券/注册。
- ⏳ 仍开放：A/B 储值类型（仅留接口）；远程预约/绑定账户编辑/充值龙珠（v1 不做）；次卡核销撤销。
- 代码仓改动本地未提交，用户部署；本次 end-work 仅 doc 仓（含 sql/ + templates/member 设计稿）。
