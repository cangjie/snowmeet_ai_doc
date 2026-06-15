# 2026-06-15 超时费改回按天 + 「免除」当日费用：brainstorm→spec→plan→实现

接续当天早些时候的 `rent_order_detail` 工作。用户给出一句话需求 + 一张截图（编辑租金明细弹窗，红圈空白处要加东西）+ 一个接口 URL，要求：① 超时费按当天算、每天可各一笔（撤销今早拍板的 rental 级单条存）；② 弹窗加「取消/免除」选项抹除当天全部费用；③ 抹除后列表里用横线划掉。本场严格走 superpowers 全流程（brainstorming → spec → writing-plans → executing-plans → finishing），改动落在 `SnowmeetApi`（后端）+ `snowmeet_wechat_mini`（前端）+ `snowmeet_ai_doc`（spec/plan/归档）。

## 1. 摸清现状（探索）

### 1.1 后端
- 接口 [`Rent/UpdateRentalDayChargesByStaff/{rentalId}`](../../SnowmeetApi/Controllers/RentController.cs#L5410)（POST，query 参数 `rentDetailId/rent/overtime/discount/scene/sessionKey`）。
- 现状：租金、减免**已按天**（`rentDetailId` 定位当天）；但超时费查找键 = `rental_id + charge_type='超时费' + valid=1`（**无 rental_date 窗口**），全单只有一笔 → 在某天填超时费会改到别天那条。这正是今早「rental 级单条存」的实现。
- 减免存在独立 `discount` 表（`biz_type=租赁 / sub_biz_type=日租金 / sub_biz_id=租金detail.id / ticket_code=null`），通过 [`OrderController.UpdateSingleDiscount`](../../SnowmeetApi/Controllers/OrderController.cs#L2826) 维护——`amount=0` 置 valid=0 **保留 amount**，`amount≠0` 命中已有行则 valid=1+改额（天然可逆）。
- 两个同名 `RentalDetail` 类：EF 实体在 [`Rental.cs:287`](../../SnowmeetApi/Models/Rent/Rental.cs#L287)（`[Table("rental_detail")]`，含 id/valid/charge_type/rental_date/amount）；旧 view model 在 `Models/Rent/RentalDetail.cs`（别开错）。
- `RentalDetail.discounts` 是 [`Rental.cs:323`](../../SnowmeetApi/Models/Rent/Rental.cs#L323) `[ForeignKey(Discount.sub_biz_id)]` 导航，`GetRental` 已 `Include(d=>d.discounts)`，前端能拿到该天全部减免（含 valid=0）。

### 1.2 前端
- [`rent_order_detail.js`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) `renderOrder` 把 `rental.details` 按 `rental_date` 聚合成 `feeRows`，**只取 valid==1 且 charge_type∈{租金,超时费}**；被免除（valid=0）的天会整行消失。
- 弹窗（[`.wxml`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml) `_dayChargeShow`）已有 租金/超时费/减免 三个 `type=digit` 输入 + 取消/确定；点输入框自动清空（`_resolveDayChargeVal` 留空回退原值，今早刚加）。

## 2. 设计（brainstorming → spec）

### 2.1 唯一向用户拍板的抉择：免除在 DB 里怎么标记
- **方案 A（选中）**：复用 `valid=0`——当天租金/超时费/减免三条 valid 置 0、金额保留；恢复置回 1。零库表改动、天然不计入总额、`UpdateSingleDiscount` 已支持可逆。副作用：租期 `realStartDate/EndDate` 取 valid=1 明细，免除首/末/唯一天会让显示租期缩（用户接受）。
- 方案 B：加独立 `waived` 列。语义干净但要 SQL Server 迁移 + 多处统计排除，改动面大。**用户选 A**。

### 2.2 关键交互澄清（用户原话）
> 「抹除的，点击也是弹出明细。如果想恢复，取消勾选"免除"的复选框即可！」

→ 免除做成弹窗里的**「免除」复选框**（不是独立按钮）：勾选+确定=抹除+划线；被划掉的天仍可点开、复选框呈勾选态，取消勾选+确定=恢复。可逆。

### 2.3 spec 自审抓到的坑
- 恢复时传入 `rent` 常等于被保留的原值（如 ¥0.01 头盔），若把「复活 valid」嵌在「金额变了」分支里 → 永远不复活、一直划线。spec 明确：**「金额变」与「复活 valid」相互独立判定**。

spec 落 [`docs/superpowers/specs/2026-06-15-rental-day-charges-waive-and-per-day-overtime-design.md`](../docs/superpowers/specs/2026-06-15-rental-day-charges-waive-and-per-day-overtime-design.md)。

## 3. 实现计划（writing-plans）

3 个 task：① 后端整方法替换；② 前端逻辑（data.js + 聚合 + 弹窗状态/handler）；③ 前端视图（wxml + wxss）。计划落 [`docs/superpowers/plans/2026-06-15-rental-day-charges-waive-and-per-day-overtime.md`](../docs/superpowers/plans/2026-06-15-rental-day-charges-waive-and-per-day-overtime.md)。

适配项目现实：**无自动化测试框架**，验证用 `dotnet build` + `node --check` + 手工 DB/模拟器；commit 由用户部署（计划里标可选）。

## 4. 执行（executing-plans）

### 4.1 后端（提交 `9d504ea`）
- 加 `[FromQuery] bool waived=false`，定位当天 `rentDetail` 后分两路：
  - **A 免除**：租金 valid→0 + 当天超时费 valid→0（均 `Entry().State=Modified`）+ 减免有 valid=1 行才 `UpdateSingleDiscount(0)`（避免 amount=0 无行 NRE）。
  - **B 正常/恢复**：租金金额变与复活 valid 独立判定；减免 curDiscount 守卫；超时费按天 upsert（`rental_id + 当天 + 超时费`，不限 valid 以支持恢复）。
- `dotnet build` → 0 错误（12 历史无关告警）。

### 4.2 前端（提交 `63fdbcf`，含昨天未提交前端）
- `data.js` 加第 8 参 `waived` → `&waived=true|false`。
- 聚合改写：纳入被免除天（只有 valid=0 租金明细 → `row.waived=true`，优先 valid=1）；超时费免除天取 `_otAllSum`（含 valid=0）正常天取 `_otValidSum`；减免改从 `detail.discounts` 原始数组求和（`ticket_code==null`，不论 valid）。
- 弹窗：data 加 `_dayChargeWaived`，`onEditDayCharge` 带出 `!!row.waived`，新增 `onDayChargeWaivedToggle`，`onDayChargeConfirm` 传第 8 参。
- wxml：列表行加 `{{row.waived?'detail-table-row--waived':''}}`；减免行与按钮间加「免除本日全部费用」复选框，勾选时三输入框 `disabled`+置灰。
- wxss：`.detail-table-row--waived` 划线（含五列变灰）+ `.dc-checkbox*`（勾选 `#2EA6D0`）+ `.dc-input--disabled`。
- `node --check` 两文件通过；grep 核对跨文件标识符一致。

### 4.3 收尾（finishing-a-development-branch）
- 两代码仓在 branch `ai`、直接改（无 feature 分支/worktree），用户选「本地 commit、不 push」→ SnowmeetApi `9d504ea`（1 文件隔离）、snowmeet_wechat_mini `63fdbcf`（4 文件，含今早未提交的卡片重构/弹窗自动清空）。

## 关键改动文件

| 仓库 | 文件 | 改动 |
|---|---|---|
| SnowmeetApi | [`Controllers/RentController.cs`](../../SnowmeetApi/Controllers/RentController.cs#L5410) | `UpdateRentalDayChargesByStaff` 加 `waived` + 按天超时费 + 免除/恢复两路径 + 每处 `Entry().State=Modified` |
| snowmeet_wechat_mini | [`utils/data.js`](../../snowmeet_wechat_mini/utils/data.js#L666) | `updateRentalDayChargesPromise` 加 `waived` 入参 |
| snowmeet_wechat_mini | [`.../rent_order_detail.js`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) | 聚合纳入免除天 + 减免从 discounts 原始取 + 弹窗 waived 状态/handler |
| snowmeet_wechat_mini | [`.../rent_order_detail.wxml`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml) | 列表行划线 class + 弹窗免除复选框 + 输入框禁用 |
| snowmeet_wechat_mini | [`.../rent_order_detail.wxss`](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss) | 划线 + 复选框 + 禁用输入框样式 |
| snowmeet_ai_doc | `docs/superpowers/specs|plans/2026-06-15-*.md` | spec + plan |

## 学到的小知识

1. **免除/恢复必须把「金额变」与「复活 valid」解耦**：恢复时 rent 常等于被保留原值（valid=0 时金额没动），若复活嵌在「金额≠原值」分支里就永远恢复不了。两个独立 `if` + 一个 `dirty` 标志。
2. **减免原值要从 `detail.discounts` 原始数组取**（`ticket_code==null`、不论 valid），不能用计算属性 `othersDiscountAmount`（只算 valid=1）——否则免除后 valid=0，前端读成 0、恢复丢值、划线行也显不出原减免。
3. **全局 NoTracking 老坑**：新写的每处「查实体→改 valid/amount→SaveChanges」都要 `Entry(x).State=EntityState.Modified`，否则静默不存（6-14 翻车点，本次全程带上）。
4. **`UpdateSingleDiscount(amount=0, 无现有行)` 会 NRE**：免除分支调它前必须先查到 valid=1 减免行才调。
5. **superpowers 全流程值在「一句话需求里藏数据语义抉择」时最明显**：这单的核心抉择是「免除怎么在 DB 落地（valid 标记 vs 新列）」，brainstorm 把它提前暴露给用户拍板，避免实现到一半返工。
6. **本项目无测试框架**：验证＝`dotnet build` + `node --check` + 手工 DB/模拟器；行为验证（含 NoTracking 回归）必须真机/真库，本环境（无 devtools、sessionKey 过期）只能到编译/语法层。
7. **end-work 只 push doc 仓**：代码改动（SnowmeetApi/snowmeet_wechat_mini）本地 commit 在 `ai`，部署由用户做；`UpdateRentalDayChargesByStaff` 必须重新 `dotnet publish` 才生效。
