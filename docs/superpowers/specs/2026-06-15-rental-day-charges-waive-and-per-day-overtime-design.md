# 租金明细：按天超时费 + 「免除」当日费用 — 设计规格

**日期**：2026-06-15
**涉及页面**：`pages/admin/rent/rent_order_detail`（租赁订单详情页 → 租金明细 + 编辑弹窗）
**涉及接口**：`Rent/UpdateRentalDayChargesByStaff/{rentalId}`（[RentController.cs:5411](../../../../SnowmeetApi/Controllers/RentController.cs#L5411)）

---

## 1. 背景与目标

「租金明细」按天聚合，每天一行（日期 / 租金 / 超时费 / 减免 / 小计）。点某天行弹出「编辑租金明细」弹窗，改当天租金 / 超时费 / 减免，确定即存（走 `UpdateRentalDayChargesByStaff`）。

本次解决两个问题：

1. **超时费要按天，每天可各有一笔**（撤销 2026-06-15 早些时候改的「rental 级单条存」）。当前后端命中键 `rental_id + charge_type='超时费' + valid=1` **不带日期**，全单只有一笔——在某天填超时费会改到别天那条。改成按天，每天独立一笔。
2. **新增「免除」当日全部费用**：弹窗加一个「免除」复选框，勾选+确定 → 抹除当天的租金 / 超时费 / 减免；列表里该天**用横线划掉**。点开被划掉的天仍弹出同一弹窗、「免除」呈勾选态，**取消勾选+确定即恢复**（金额原样回来）。

不在本次范围：
- 顶部 showcase 五格金额拼写 bug（既存遗留，另行修）。
- 赔偿金（按租赁物每件维度，不在此表）。
- 票券类减免（`ticket_code != null`）；本弹窗只管当天的非票券「日租金」减免，与现有逻辑一致。

---

## 2. 数据模型与「免除」的标记方式（方案 A：复用 `valid=0`）

`rental_detail` 表（EF 实体 `SnowmeetApi.Models.RentalDetail`，[Rental.cs:287](../../../../SnowmeetApi/Models/Rent/Rental.cs#L287)）：`charge_type ∈ {租金, 超时费, 赔偿金}`、`rental_date`、`amount`、`valid`。当天减免存在独立 `discount` 表（`biz_type=租赁 / biz_id=rental_id / sub_biz_type=日租金 / sub_biz_id=租金detail.id / ticket_code=null`）。

**「免除」= 把当天三条记录的 `valid` 置 0，金额原样保留；恢复 = 置回 1。** 选择理由：

- `valid=0` 天然不计入总额（`GetTotalAmountByType` 只算 `valid==1`），也不计入 `availabelRentDetails`。
- 金额不清零 → 恢复时原值完整回来。
- 减免侧 `UpdateSingleDiscount` 已支持「金额=0 → 置 valid=0 且**保留 amount**」「金额≠0 且已有行 → 置 valid=1 + 改 amount」，免除/恢复天然可逆。
- 零数据库改动。

**已知副作用（用户已接受）**：租期起止 `realStartDate/realEndDate` 取自 `valid=1` 明细。免除中间某天无影响；免除首/末天或唯一一天时显示租期会跟着缩。属边缘情况。

---

## 3. 后端：`UpdateRentalDayChargesByStaff`

### 3.1 签名变更

新增查询参数 `[FromQuery] bool waived = false`。其余不变（`rentDetailId / rent / overtime / discount / scene / sessionKey / sessionType`）。前端 URL 追加 `&waived=true|false`。

权限、`rental` / `rentDetail`（按 `rentDetailId` 定位「当天」）的取数与校验保持现状。

### 3.2 ⚠️ 必须遵守：全局 NoTracking

`Startup.cs:48` 配了 `QueryTrackingBehavior.NoTracking` → **凡是「查实体 → 改字段 → SaveChanges」都必须显式 `_db.Entry(x).State = EntityState.Modified`，否则静默不持久化且不报错**（本接口 6-14 初版就因漏写翻车，6-15 已补 3 处）。本次新增的每一处 `valid` 翻转 / `amount` 改写都必须带上。`UpdateSingleDiscount` 内部已自带 `Entry().State=Modified`，调用它即可。

### 3.3 两条路径

定位当天租金明细 `rentDetail`（`id == rentDetailId && rental_id == rentalId`）后：

**路径 A — `waived == true`（免除）**：忽略 `rent/overtime/discount` 入参，只翻 `valid`（保留金额）：
1. 当天租金明细：若 `valid==1` → 置 `valid=0`（`Entry().State=Modified`），记 log「免除当日租金」。
2. 当天超时费（`rental_id + rental_date==当天 + charge_type='超时费'`，取 `valid=1` 的）：存在则置 `valid=0`，记 log。
3. 当天减免：查 `valid=1` 的非票券日租金 discount，**存在才**调 `UpdateSingleDiscount(..., 0, ...)`（置 valid=0、保留 amount）。
   - 不存在不要调——`UpdateSingleDiscount(amount=0, discount=null)` 会走 else 取 `discount.id` 触发 NRE（既有坑）。

**路径 B — `waived == false`（正常更新 / 从免除恢复）**：
1. **当天租金额**：判定「金额是否变」与「是否需复活」**相互独立**——
   - 金额变（`rentDetail.amount != rent`）→ 改 `amount` + log。
   - 原 `valid==0` → 置 `valid=1`（恢复）+ log「恢复当日租金」。
   - ⚠️ 二者任一成立就写一次 `Entry().State=Modified` + SaveChanges。**不能把复活嵌在「金额变了」分支里**——从免除恢复时，金额因被保留往往与传入 `rent` 相等（如 ¥0.01 头盔），若只在金额变时才复活，该天会一直划线、永远恢复不了。
2. **当天减免**：维持现状——`curDiscount`（现有 valid=1 日租金减免额，无则 0）`!= discount` 时才调 `UpdateSingleDiscount(..., discount, ...)`。该方法对「discount=0 → 作废」「discount≠0 且行为 valid=0 → 复活 + 改额」都已处理，恢复天然可逆。
3. **当天超时费（按天 upsert，本次核心改动）**：查找键**加日期** → `rental_id + rental_date.Date == rentDetail.rental_date.Date + charge_type='超时费'`，`OrderByDescending(id)` 取最新一条（**不限 valid**，以便从免除恢复时能找到 valid=0 那条）：
   - `overtime > 0`：命中则 `amount=overtime` 且 `valid=1`（含复活），不命中则**新插一条**（`rental_date = rentDetail.rental_date`，`valid=1`）。
   - `overtime <= 0`：命中且 `valid==1` 则置 `valid=0`，不命中不处理。
   - 所有「改已有行」分支必须 `Entry().State=Modified`；新插走 `AddAsync`（不受 NoTracking 影响）。

> 与旧逻辑差异：仅把超时费查找键由「rental 级」加回「按天」(`rental_date` 窗口)，并把 upsert 的命中改为「不限 valid」以支持恢复。租金 / 减免本就按天（`rentDetailId` 定位），不动。

末尾 `GetRental(rentalId)` 回查返回最新 rental（现状不变）。

---

## 4. 前端：`rent_order_detail` + `data.js`

### 4.1 `utils/data.js`

`updateRentalDayChargesPromise(rentalId, rentDetailId, rent, overtime, discount, scene, sessionKey)` 增加 `waived` 入参，URL 追加 `&waived=` + (waived ? 'true' : 'false')。

### 4.2 按天聚合（`renderOrder` 的 feeRows，[rent_order_detail.js:189](../../../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js#L189)）

当前只取 `valid==1`，被免除的天会整行消失。改为纳入被免除天，并带原始金额：

每天一行 `row = { dateStr, rentDetailId, rent, overtime, discount, waived, subtotal, ...Str }`，按 `rental_date` 聚合，规则：
- **租金明细**：优先取该天 `valid==1` 的；若该天只有 `valid==0` 的租金明细 → `row.waived = true`，仍取其 `id`（供点开）与 `amount`（供恢复/划线展示）。`row.rentDetailId` = 选中那条的 id。
- **超时费**：`row.overtime` = 该天超时费金额之和；非免除天只算 `valid==1`，免除天连 `valid==0` 一起算（保留原值供恢复）。
- **减免**：`row.discount` = 该天非票券「日租金」减免额，**从原始 `detail.discounts` 数组取（不论 valid，`ticket_code==null`）**，而非 `detail.othersDiscountAmount`——这样免除后（discount valid=0）仍能取到原值。非免除天此值与原 `othersDiscountAmount` 等价（每天至多一条该类 discount）。
- `row.subtotal = rent + overtime - discount`（免除天照算，仅用于划线展示；不计入页面总额，总额由后端 valid=1 决定）。
- 各 `*Str` 用 `util.showAmount` 转 2 位。

> 实现校验点：确认 `GetRental` 返回的 `detail.discounts` 数组已序列化（`Include(d => d.discounts)` 已存在）。

### 4.3 弹窗状态与交互（`rent_order_detail.js`）

- 新增 data 字段 `_dayChargeWaived`（bool）。
- `onEditDayCharge`：照常带出 `_dayChargeXxxOrig`（即使被免除天，原值来自 4.2 的 row），并 `_dayChargeWaived = row.waived`。被划掉的天**仍可点开**（它有 `rentDetailId`，不再 toast 拦截）。
- 新增 `onDayChargeWaivedToggle`（复选框 change）：切换 `_dayChargeWaived`。
- `onDayChargeConfirm`：把 `_dayChargeWaived` 作为 `waived` 传给 `updateRentalDayChargesPromise`；保存成功后用返回 rental 就地 `renderOrder` 刷新（现状）。

### 4.4 弹窗 WXML（[rent_order_detail.wxml:515](../../../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml#L515)）

在「减免」行与「取消/确定」按钮之间（即截图圈出的空白处）加一行复选框：

```
免除本日全部费用  ☐
```

- 用 `<checkbox>` 或自定义勾选块，绑 `bindtap/bindchange="onDayChargeWaivedToggle"`。
- 勾选（`_dayChargeWaived==true`）时，三个金额输入框 `disabled` + 置灰（视觉提示「免除时金额无意义」）；取消勾选恢复可编辑。
- 弹窗顶部已有「取消」按钮含义是「关闭不保存」，与「免除」语义不同，保持原样。

### 4.5 列表行 WXML（[rent_order_detail.wxml:235](../../../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml#L235)）

行 class 追加免除态：`class="detail-table-row detail-table-row--tappable {{row.waived ? 'detail-table-row--waived' : ''}}"`。被免除天仍显示原金额，只是整行划线。

### 4.6 WXSS

```css
.detail-table-row--waived { text-decoration: line-through; color: #b0b0b0; }
```

复选框行的样式按弹窗既有 `dc-*` 风格补 `dc-field--checkbox` 等。

---

## 5. 行为表

| 操作 | 后端动作 | 列表该天 | 计入页面总额 |
|------|---------|---------|-------------|
| 正常天编辑某项 | 改对应记录金额（按天定位） | 正常显示 | ✅ |
| 某天填超时费 | 仅该天 upsert 一笔超时费（不影响别天） | 该天超时费列变 | ✅ |
| 勾「免除」+ 确定 | 当天租金/超时费/减免 valid→0（保留金额） | **横线划掉**（仍显原金额） | ❌ |
| 点开被划掉的天 | 弹窗「免除」勾选、金额置灰显原值 | — | — |
| 取消勾选 + 确定 | 当天租金/超时费/减免 valid→1（金额原样） | 恢复正常显示 | ✅ 重新计入 |

---

## 6. 边界与已知影响

- **租期起止**：免除首/末天或唯一一天会让 `realStartDate/EndDate` 跟着缩（方案 A 副作用，已接受）。
- **免除只覆盖弹窗管的三项**：当天租金 + 当天超时费 + 当天非票券日租金减免。票券减免、赔偿金不在范围。
- **多笔超时费**：现按「每天至多一笔」设计（与租金行一一对应）。同一天多笔超时费非本次需求。
- **顶部 showcase 五格金额**：拼写 bug 既存，本次不修；改超时费后行小计会变，但那五格仍恒 ¥0（另行修）。
- **部署**：`UpdateRentalDayChargesByStaff` 改动需重新部署 SnowmeetApi 才生效；无库表变更。

---

## 7. 验证计划

后端（本地直连或部署后，用有效 sessionKey）：
1. 同一单两天各填不同超时费 → DB 两条 `超时费` 各带对应 `rental_date`、互不覆盖。
2. 某天填超时费=0 → 该天那条 `valid→0`，别天不受影响。
3. 勾免除 → 当天租金/超时费/减免三条 `valid` 全 0、`amount` 不变；`GetRental` 返回的总额不含该天。
4. 取消勾选 → 三条 `valid` 全回 1、金额原样；总额恢复。
5. `core_data_mod_log` 有对应 scene 记录（改租金/超时费/免除/恢复）。
6. **回归 NoTracking**：每个 valid 翻转后 DB 真变（这是 6-14 翻车点，必测）。

前端（模拟器/真机）：
1. 弹窗出现「免除」复选框，位置在减免行与按钮之间；勾选时三输入框置灰。
2. 免除后列表该天横线划掉、仍显原金额；页面总额不含该天。
3. 点开被划掉天 → 复选框勾选态 + 原值占位；取消勾选+确定 → 恢复。
4. 点输入框自动清空、直接输金额（沿用 6-15 的 `_resolveDayChargeVal` 回退原值）。
