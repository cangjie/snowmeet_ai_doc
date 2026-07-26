# 2026-07-25 次卡自助退款 + 订单生效补全会员姓名性别（跨夜至 07-26）

接续 7-22 的租赁次卡销售、7-25 的次卡/季卡商品维护。本场两件独立的事：① 给「我的次卡」详情页做顾客自助退款（全栈 + 一列 DDL）；② 排查并补齐「订单生效后把开单填的姓名性别同步到会员档案」——这个功能 6-30 写过但只挂了一条路径。改动落在 `SnowmeetApi`（后端）+ `snowmeet_wechat_mini`（前端）+ `snowmeet_ai_doc/sql`（DDL），两代码仓均未提交。

会话期间用户并行扩展了店员侧的次卡能力（见第 3 节），与本场退款功能同处一个功能域，部署时要一起走。

---

## 1. 次卡自助退款

### 1.1 需求与两个拍板决策

用户原话：「次卡的详情页当中，如果次卡一次未使用过，应该允许退款。如果是微信支付宝退款，直接调用相应的接口退款。并且次卡 punch_card 表中，需要增加一个已退款的标志字段。退款成功后，自动置这个标志字段，界面上显示该次卡是已退款状态，风格让人看到是不可用即可。」

截图定位到的页面是 [`pages/mine/punchcard_usage`](../snowmeet_wechat_mini/pages/mine/punchcard_usage.wxml)（我的次卡 → 点某张卡 → 核销记录），数据来自 `Rent/GetMyPunchCardUsages`。

探索后发现次卡有**三条来源路径**，退款的财务性质差别很大，用 AskUserQuestion 拍板两点：

| 问题 | 用户决定 |
|---|---|
| 谁操作退款 | 微信/支付宝支付的**顾客自助退款**；否则提示联系店员 |
| 哪些卡能退 | **凡付过钱的卡都能退**（含店员退押金时卖的卡） |

### 1.2 关键洞察：「一次未使用过」天然排除了「撤销销售」的复杂度

第二个选项看似要写一整套撤销逻辑（恢复购卡时核销的次数、恢复被免除的租金、反向调整押金退款），实际不需要：

- `FinalizePunchCardSale`（店员退押金时卖卡）创建卡时 `punches = calc.punchCountNow`，且 `punchCountNow > 0` 时会调 `WriteOffSkiPunches` 免除租金 + 写 `punch_card_used`
- 所以**当场核销过次数的卡，`punches > 0`，不满足「一次未使用过」，直接被规则挡住**
- 反之 `punchCountNow == 0` 的卡既没写 `punch_card_used`、也没免除任何租金 → 撤销时无需恢复任何东西

结论：三条路径的退款金额可以统一为 `retail.deal_price`（卡价），走现成的 `AllocateRefundAcrossPayments` + `RefundCore` 按订单支付记录分摊。

**为什么这个统一口径在店员卖卡路径下财务也对**（当时逐个场景推演过）：

- `refund` 腿（卡价 X ≤ 应退押金 R）：当时退给顾客 `R − X`，即少退了 X 当卡钱。订单上微信支付 R、已退 `R−X`、未退 X → 退卡退 X 正好把剩下的押金退完 ✓
- `cash` / `qr` 腿（卡价 X > 应退押金 R）：押金 R 全额抵扣卡价 + 另收现金/扫码 `X−R`。订单可退总额 = R + (X−R) = X → 退卡退 X 把押金和补差价都退回 ✓

即：顾客为这张卡付出的价值恒等于卡价，无论形式是"少退押金"还是"额外补钱"。

### 1.3 后端实现

**DDL**（[`sql/2026-07-25_punch_card_add_is_refund.sql`](../sql/2026-07-25_punch_card_add_is_refund.sql)）：`punch_card` 加 `is_refund BIT NOT NULL DEFAULT 0`。没用删行/valid=0，因为 `punch_card` 表没有 valid 列，且销售记录（retail）、退款记录（payment_refund）都要留痕，卡本身还要在「我的次卡」里能看到已退款状态。

**共享判定 `EvaluatePunchCardRefund(card, memberId)`**（[`RentController.cs`](../SnowmeetApi/Controllers/RentController.cs)）：返回 `canRefund / contactStaff / blockReason / refundAmount / order / refunds`。判定顺序：

1. `is_refund` → 「这张卡已退款」
2. 已使用过（`punches > 0` **或** 存在 valid 的 `punch_card_used`，双重校验因两个来源历史数据可能不一致）→ 「已经使用过，不支持退款」
3. `source_retail_id == null` → 「没有关联的线上支付记录，不支持自助退款；如需退款请联系店员」
4. retail 行缺失 / `order_id` 空 → 转人工
5. `deal_price <= 0` → 「购买金额为 0，无需退款」
6. 订单加载不到 → 转人工
7. `AllocateRefundAcrossPayments` 返 null（可退余额不足，储值支付已被它自身排除）→ 转人工
8. 分摊到的任一支付腿不是微信/支付宝 → 「不是微信或支付宝支付的，请联系店员办理退款」
9. 全通过 → `canRefund = true`，并给每笔 refund 预填 `oper_member_id`

`GetMyPunchCardUsages`（只读预判）与 `RefundMyPunchCard`（真退款）调同一份，保证"页面上看到的判断"和"点下去的判断"永远一致——同 `ComputePunchCardSaleCalc` 的做法。

**退款接口 `RefundMyPunchCard`**（POST `{cardId}`）：解析会员本人 → 校验卡归属（cardId 是前端传的，不校验就能退别人的卡）→ 幂等（`is_refund` 已置则直接返回成功）→ eval → `RefundCore(order, null, refunds)` → **退款成功后**才置 `is_refund = true` + retail.memo 追加退款说明 + `CoreDataModLog`。

严格顺序是**先退款成功、再置标志位**，反过来会出现"卡废了钱没退"。

**`RefundCore` 的 `staff` 参数改为可空**（[`OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs)）：顾客自助没有经手店员，`payment_refund.staff_id` 留空、发起人记在 `oper_member_id`。沿用 `StartMyPunchCardPayment` 里「顾客自助支付单 `staff_id = null`」的先例；`OrderPaymentRefund.staff_id` 本身就是 `int?`。既有两个调用方都传非 null，行为不变。

**`retail` 行保留 `valid = 1`**，只在 memo 追加「顾客自助退款 ¥X（时间）」。若置 valid=0，订单详情的「次卡销售」列表和 `GetMyPunchCardOrder` 的金额都按 valid=1 过滤，这笔销售会凭空消失；保留才有完整的"卖出又退回"痕迹。

### 1.4 核销拦截 6 处（已退款的卡不得再被核销）

| 位置 | 处理 |
|---|---|
| `RentController.GetRentalPunchCardInfo` | 可用卡列表加 `&& !c.is_refund` |
| `RentController.UseRentalPunchCard` | 守卫：已退款 → 「该次卡已退款，不能使用」 |
| `CareController.CalcCareCharge` | 已退款 → `card = null`，不参与定价 |
| `OrderController.PlaceCareOrder` | 已退款 → 连同"卡不属于该会员"一起清 `care.use_card/card_id/card_name` |
| `CareController.EffectCareOrder` | 核销守卫 `punchCard != null && !punchCard.is_refund`（防先下单后退卡的时序） |
| `MemberAdmin.GetMemberAssetsByStaff` | 资产聚合排除已退款卡 |
| `MemberAdmin.GetMemberCardsByStaff` | 开单选卡列表排除已退款卡 |

`GetPunchCardPresets`（按 card_name distinct 取卡种预设）不改——它是"卡种名字池"，与卡实例无关，加过滤反而可能让某个卡种从预设里消失。

### 1.5 显示侧：已退款的卡要看得见但标出来

三处列表都返回 `is_refund` 并标灰，而不是隐藏——退过款的卡凭空消失，顾客会以为卡丢了、店员也可能把它当成可用余额报给顾客：

- [`punchcard_usage`](../snowmeet_wechat_mini/pages/mine/punchcard_usage.wxml)：整卡灰化（底色/卡名/业务角标/副行一起降），右上角「剩余 N 次」换成灰色「已退款」标记
- [`my_punchcards`](../snowmeet_wechat_mini/pages/mine/my_punchcards.wxml)：整行灰化 + 右侧「已退款」
- [`member_detail`](../snowmeet_wechat_mini/pages/admin/member/member_detail.wxml)（店员侧）：同上

退款按钮用**描边红**（危险动作但不是本页主操作，实心红太抢），二次确认 modal 说明「将退回 ¥X 到原支付账户。退款后这张卡不能再使用，且无法撤销。」

### 1.6 真机反馈：「这个卡没有使用，为什么没有退款按钮？」

用户测的是一张「养护双项10次卡」，总 10 次、已核销 0 次、开卡 **2026-07-04**。

两个原因，很可能同时成立：

1. **这张卡本来就退不了**：`source_retail_id` 字段和次卡销售功能是 **7-22** 才落地的，7-04 时发卡只有一条路径——店员在会员管理页 `GrantPunchCard` 手工发放（很可能是注册开卡礼包）。这类卡系统里没有任何关联支付记录。
2. **界面没说明原因（我的设计失误）**：原来只在"可以退"和"需联系店员"两种情况显示内容，"不能退"整块留白 → 对着一张没用过的卡必然追问。

修复：改成**只要不能自助退就把原因写出来**（唯一例外是卡已退款，那时卡片已整块灰掉并标了「已退款」，再写一遍是重复）。

同时改了文案口径：原写「这张卡是赠送发放的」是武断的——7-22 之前手工发的卡里可能有线下收过钱的，系统只是没记录关联。改为「这张卡没有关联的线上支付记录，不支持自助退款；如需退款请联系店员」并置 `contactStaff = true`，交给人工判断。

还有一个前提当时无法排除：**如果后端没 publish**，接口返回里根本没有 `refund` 字段，改了前端也不会显示任何东西。已提醒用户先按顺序部署。

---

## 2. 订单生效补全会员姓名性别

### 2.1 需求

用户原话：「目前，开单场景，无论何种何业务的订单，只要订单生效，且如果当前顾客的姓名性别为空，则开单时填写的姓名性别，同步到 member 表里的姓名性别字段当中去。」

CLAUDE.md 记 6-30 做过 `SupplementMemberProfileFromOrder`「挂 `DealSuccessPaidOrder` 覆盖 notify + EffectUnpaidOrder」。

### 2.2 排查：实际只覆盖了一条路径

`grep` 全项目只有 1 个调用点——`DealSuccessPaidOrder`（支付回调；店员手工收现金/挂账也算，因为 `EffectUnpaidOrder` 内部转调它）。而**订单生效路径散落在 5 处**，另外 4 条压根不经过支付回调：

| 生效路径 | 场景 | 之前 |
|---|---|---|
| `DealSuccessPaidOrder` | 微信/支付宝支付、现金挂账确认 | ✅ 已有 |
| `PlaceOrder`（旧版开单） | 0 元养护单 place 即生效（996-1006 直接 `EffectCareOrder`） | ❌ 漏 |
| `PlaceCareOrder`（新版养护） | 无权益的 0 元单（质保/招待/全减免） | ❌ 漏 |
| `PayWithDeposit` | 储值支付（养护全额 / 租赁付租金） | ❌ 漏 |
| `WriteoffCareOrder` | 养护 0 元核销 / 储值全覆盖单核销 | ❌ 漏 |

交叉验证：`EffectRentOrder` 只有 1 个调用点（在 `DealSuccessPaidOrder` 内，已覆盖）；`EffectCareOrder` 有 5 个调用点，其中 4 个就是上面这几条。零售/雪票的生效都在 `DealSuccessPaidOrder` 的 switch 内，已覆盖。

**所以用户遇到的问题集中在养护/储值/0 元单**——这与"无论何种业务"的诉求正好对上。

### 2.3 实施

四处补上 `await SupplementMemberProfileFromOrder(order)`，并在方法头部把 5 条路径清单写进注释 + 注明「今后新增任何订单生效入口都要补一次调用」（这次遗漏的根因就是当时只想到支付回调）。

`PayWithDeposit` 的调用点特意放在**收尾处、不限业务类型**，而不是挂在 `EffectCareOrder` 旁边——租赁的「储值付租金」分支下面根本不调 Effect，挂那里会漏掉租赁。

日志 scene 从「支付成功补全会员资料」改为「订单生效补全会员资料」，并在 `manual_memo` 带上订单号便于追溯。

### 2.4 EF 跟踪坑：同 id Member 实例撞键

`PayWithDeposit` 在设 `paying_amount = null` 时对 order 做了 `Entry().State = Modified`，**EF 会沿导航图把 `order.member` 一并 attach 进跟踪器**（项目里反复踩过的 TrackGraph 坑）。此后 `SupplementMemberProfileFromOrder` 内部查出一个同 id 的新 Member 实例再 `Entry().State = Modified`，就会抛 "another instance with the same key value is already being tracked"。

修法是让方法自己健壮，5 个调用点都不必操心各自的跟踪状态：

```csharp
Models.Member member = _db.member.Local.Where(m => m.id == order.member_id).FirstOrDefault();
bool alreadyTracked = member != null;
if (member == null)
    member = await _db.member.Where(m => m.id == order.member_id).FirstOrDefaultAsync();
...
if (!alreadyTracked)
    _db.member.Entry(member).State = EntityState.Modified;   // 已跟踪的靠变更跟踪自动识别
```

全局 `QueryTrackingBehavior.NoTracking` 下 `DbSet.Local` 通常是空的（只有显式 attach 的才在里面），所以这个检查开销极小。

行为不变：只填空、不覆盖已有值；散客单（`member_id == null`）直接跳过；重复调用无副作用。

---

## 3. 会话期间用户并行扩展的店员侧次卡能力

不是本场我做的，但与退款功能同处一个功能域、部署要一起走，记录状态以免下次上下文对不上：

- `RentController.BuildPunchCardUsageView` — 把卡详情展示组装抽成顾客侧/店员侧共用的一份
- `RentController.GetPunchCardUsagesByStaff` — 店员侧看某张卡的核销记录（按 staff 权限放行，不校验"卡是我的"），**不下发 refund**，所以顾客自助退款入口在店员模式下自然不显示
- `RentController.UpdatePunchCardEquipByStaff` — 店员改季卡绑定装备的品牌/长度（装备类型不开放，换类型等于换一块板，属于"换卡"）
- `RentController.GetPunchCardSalesByStaff` + 新页面 `pages/admin/rent/punchcard_sales/` — 卡类产品销售列表（staff≥200，倒序列出已卖出/发出的次卡与季卡，按"卡是怎么来的"判定销售方式）
- 前端：`punchcard_usage` 加店员模式（`?staff=1`，换数据源 + 顾客信息卡 + 季卡绑定装备可编辑）；`member_detail` 名下次卡整行可点跳该页；`my_punchcards` 行内补开卡日期（两行布局）
- `data.js` 新增 `getPunchCardUsagesByStaffPromise` / `updatePunchCardEquipByStaffPromise`

我的 `refund` 判定完好保留在顾客侧 `GetMyPunchCardUsages` 里（`BuildPunchCardUsageView` + `EvaluatePunchCardRefund` 并列返回）。

---

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`sql/2026-07-25_punch_card_add_is_refund.sql`](../sql/2026-07-25_punch_card_add_is_refund.sql) | 新建：`punch_card.is_refund` DDL + 验证查询 |
| [`Models/Rent/PunchCard.cs`](../SnowmeetApi/Models/Rent/PunchCard.cs) | 加 `is_refund` bool |
| [`Controllers/RentController.cs`](../SnowmeetApi/Controllers/RentController.cs) | 新增 `PunchCardRefundEval` + `EvaluatePunchCardRefund` + `RefundMyPunchCard`；`GetMyPunchCardUsages` 下发 refund 判定；`GetMyPunchCards` 下发 isRefund；`GetRentalPunchCardInfo`/`UseRentalPunchCard` 排除已退款卡 |
| [`Controllers/OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) | `RefundCore` staff 改可空；`SupplementMemberProfileFromOrder` 复用已跟踪 Member 实例 + 4 处新调用点；`PlaceCareOrder` 已退款卡清引用 |
| [`Controllers/CareController.cs`](../SnowmeetApi/Controllers/CareController.cs) | `CalcCareCharge` 定价忽略已退款卡；`EffectCareOrder` 核销守卫 |
| [`Controllers/MemberAdminController.cs`](../SnowmeetApi/Controllers/MemberAdminController.cs) | 资产聚合/选卡列表排除已退款卡；会员详情下发 `is_refund` |
| [`utils/data.js`](../snowmeet_wechat_mini/utils/data.js) | 新增 `refundMyPunchCardPromise` |
| [`pages/mine/punchcard_usage.*`](../snowmeet_wechat_mini/pages/mine/punchcard_usage.js) | 退款入口 + 二次确认 + 已退款置灰 + 不可退时显示原因 |
| [`pages/mine/my_punchcards.*`](../snowmeet_wechat_mini/pages/mine/my_punchcards.wxml) | 已退款行标灰 + 「已退款」标记 |
| [`pages/admin/member/member_detail.*`](../snowmeet_wechat_mini/pages/admin/member/member_detail.wxml) | 名下次卡已退款标灰 |

---

## 学到的小知识

1. **前置条件能消灭复杂度，先找它再动手设计**：「一次未使用过」这一条把"撤销销售"（恢复核销次数/恢复免除租金/反向调整押金）整套逻辑挡在门外，三条购卡路径于是能共用一个退款口径。接需求时先问"什么情况下这个动作被禁止"，往往比先设计"怎么处理所有情况"省得多。

2. **"不可用"的 UI 必须解释原因，留白等于制造疑问**：本场原设计只在"能退"和"需联系店员"时显示内容，其余留白 → 用户立刻追问"为什么没有按钮"。凡是"按条件隐藏操作入口"的界面，都要想清楚被隐藏时用户看到什么。

3. **判断类逻辑要做成"预判与执行共用一份"**：`EvaluatePunchCardRefund` 同时服务详情页预判和真实退款，否则会出现"页面给了按钮、点下去被拒"。项目里 `ComputePunchCardSaleCalc` 是同一个模式。

4. **`DbSet.Local` 是解决"同 id 实例撞键"的干净手段**：`Entry(order).State = Modified` 会沿导航图 attach `order.member`，之后再 attach 同 id 新实例即抛异常。让被复用的方法自己 `Local.FirstOrDefault(...)` 优先复用已跟踪实例，比让每个调用点各自 Detach 更省心。全局 NoTracking 下 `Local` 通常为空，开销可忽略。

5. **"某功能已挂上"的文档记载要 grep 验证**：CLAUDE.md 记 `SupplementMemberProfileFromOrder` 已挂 `DealSuccessPaidOrder` + `EffectUnpaidOrder`，实际只有 1 个调用点，而生效路径有 5 条。文档写"已完成"时最好把调用点/路径清单一并列出，否则下次无从判断覆盖是否完整。

6. **同一件事有多个"完成入口"时，先把入口清单枚举出来再改**：本场靠 `grep EffectRentOrder(` / `grep EffectCareOrder(` / `grep "dealed = 1"` 三条命令把订单生效的全部入口锁定，才发现 4 处遗漏。只读代码顺着主流程走，一定会漏掉旁路。

7. **字段是哪个版本加的，决定了存量数据能不能用新功能**：`source_retail_id` 是 7-22 加的，所以 7-22 之前的所有次卡都没有购买关联、一律无法自助退款。做"针对存量数据的新功能"时，先确认它依赖的字段从什么时候开始有值。
