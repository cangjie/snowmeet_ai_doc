# 租金明细：按天超时费 + 「免除」当日费用 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让超时费按天独立收取（撤销今早的 rental 级单条存），并在「编辑租金明细」弹窗加「免除本日全部费用」复选框——勾选后当天租金/超时费/减免抹除、列表里横线划掉，取消勾选可原样恢复。

**Architecture:** 复用 `valid=0` 标记免除（金额保留、不计入总额、可逆）。后端 `UpdateRentalDayChargesByStaff` 拆成「免除」「正常/恢复」两条路径并把超时费查找键加回 `rental_date` 当天窗口；前端按天聚合纳入被免除天、弹窗加复选框、列表加划线样式。

**Tech Stack:** 后端 ASP.NET Core 9 / C# / EF Core（SQL Server）；前端原生微信小程序（ES5 风格 JS + WXML + WXSS）。

**设计依据：** [`docs/superpowers/specs/2026-06-15-rental-day-charges-waive-and-per-day-overtime-design.md`](../specs/2026-06-15-rental-day-charges-waive-and-per-day-overtime-design.md)

---

## ⚠️ 本项目特殊约定（执行前必读）

1. **无自动化测试框架**：本仓库不跑 pytest/jest 之类单测。验证手段＝`dotnet build`（编译）、`node --check`（JS 语法）、+ **手工 DB 查询 / 微信开发者工具模拟器**。本计划用这些真实手段，行为验证以 DB SQL 清单为准（见 Task 1 验证步骤）。本环境无微信开发者工具，模拟器/真机验证由用户完成。
2. **全局 `QueryTrackingBehavior.NoTracking`（[Startup.cs:48](../../../../SnowmeetApi/Startup.cs#L48)）**：凡「查实体 → 改字段 → SaveChanges」**必须显式 `_db.Entry(x).State = EntityState.Modified`**，否则静默不持久化且不报错（本接口 6-14 初版就栽在这）。本计划每处更新都已带上，照抄即可。
3. **部署由用户做**：`SnowmeetApi`、`snowmeet_wechat_mini` 是各自独立 git 仓（分支 `ai`）。代码改完编译/语法通过即可；commit 步骤为可选本地检查点（**不 push**），实际部署到 `mini.snowmeet.top` + 小程序重编由用户完成。`UpdateRentalDayChargesByStaff` 改动需重新部署 SnowmeetApi 才生效（无库表变更）。
4. **两个同名 `RentalDetail` 类**：改后端只动 EF 实体 `SnowmeetApi.Models.RentalDetail`（`[Table("rental_detail")]`，在 [Rental.cs:287](../../../../SnowmeetApi/Models/Rent/Rental.cs#L287)）；别动旧 view model [`Models/Rent/RentalDetail.cs`](../../../../SnowmeetApi/Models/Rent/RentalDetail.cs)。

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| [`SnowmeetApi/Controllers/RentController.cs`](../../../../SnowmeetApi/Controllers/RentController.cs#L5410) | `UpdateRentalDayChargesByStaff`：加 `waived` 参数 + 按天超时费 + 免除/恢复 | 改（整方法替换） |
| [`snowmeet_wechat_mini/utils/data.js`](../../../../snowmeet_wechat_mini/utils/data.js#L666) | `updateRentalDayChargesPromise`：加 `waived` 入参 | 改（整函数替换） |
| [`.../rent_order_detail.js`](../../../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) | 按天聚合纳入免除天 + 弹窗 `_dayChargeWaived` 状态/handler | 改（3 处） |
| [`.../rent_order_detail.wxml`](../../../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml) | 列表行划线 class + 弹窗复选框 + 输入框禁用 | 改（2 处） |
| [`.../rent_order_detail.wxss`](../../../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss) | 划线样式 + 复选框/禁用输入框样式 | 改（追加） |

---

## Task 1: 后端 — 按天超时费 + 免除/恢复

**Files:**
- Modify: `SnowmeetApi/Controllers/RentController.cs`（现有方法在 5410–5508 行）

- [ ] **Step 1: 定位并整方法替换**

用 Edit 把现有整个方法（从注释 `// 按天一次性修改：当天租金 + 当天减免 + 超时费（超时费按 rental 维度单条存储，无则新建/清零则作废）` 到该方法结尾 `}`，即 [RentController.cs:5410](../../../../SnowmeetApi/Controllers/RentController.cs#L5410) 起）替换为下面的完整新方法。新方法新增 `waived` 参数、把超时费查找键加回 `rental_date` 当天窗口、并拆成「免除」「正常/恢复」两条路径。

```csharp
        // 按天一次性修改：当天租金 + 当天减免 + 当天超时费（按天 upsert）；
        // waived=true 时免除当天全部费用（valid 置 0、金额保留），取消勾选即恢复
        [HttpPost("{rentalId}")]
        public async Task<ActionResult<ApiResult<Models.Rental?>>> UpdateRentalDayChargesByStaff([FromRoute] int rentalId,
            [FromQuery] int rentDetailId, [FromQuery] double rent, [FromQuery] double overtime, [FromQuery] double discount,
            [FromQuery] string scene, [FromQuery] string sessionKey, [FromQuery] bool waived = false,
            [FromQuery] string sessionType = "wechat_mini_openid")
        {
            Staff staff = await Util.GetStaffBySessionKey(_db, sessionKey, sessionType);
            scene = Util.UrlDecode(scene);
            if (staff == null || staff.title_level < 100)
            {
                return Ok(new ApiResult<Models.Rental?>() { code = 1, message = "没有权限", data = null });
            }
            Models.Rental rental = await _db.rental.Where(r => r.id == rentalId).AsNoTracking().FirstOrDefaultAsync();
            if (rental == null || rental.order_id == null)
            {
                return Ok(new ApiResult<Models.Rental?>() { code = 1, message = "无此租赁", data = null });
            }
            // 当天租金明细：用 id 定位（每一行的真理之源），同时也确定"当天"
            Models.RentalDetail rentDetail = await _db.rentalDetail
                .Where(d => d.id == rentDetailId && d.rental_id == rentalId).FirstOrDefaultAsync();
            if (rentDetail == null)
            {
                return Ok(new ApiResult<Models.Rental?>() { code = 1, message = "无此租金明细", data = null });
            }
            DateTime theDay = rentDetail.rental_date.Date;
            OrderController _orderHelper = new OrderController(_db, _oriConfig, _httpContextAccessor);

            if (waived)
            {
                // ===== 路径 A：免除当天全部费用（valid→0，金额保留）=====
                // 1) 当天租金明细
                if (rentDetail.valid == 1)
                {
                    await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "valid",
                        rentDetail.id, scene, null, staff.id, rentDetail.valid.ToString(), "0", "免除当日租金"));
                    rentDetail.valid = 0;
                    rentDetail.update_date = DateTime.Now;
                    _db.Entry(rentDetail).State = EntityState.Modified;
                    await _db.SaveChangesAsync();
                }
                // 2) 当天超时费（按天定位）
                Models.RentalDetail otDetailW = await _db.rentalDetail
                    .Where(d => d.rental_id == rentalId && d.rental_date.Date == theDay
                        && d.charge_type == "超时费" && d.valid == 1)
                    .OrderByDescending(d => d.id).FirstOrDefaultAsync();
                if (otDetailW != null)
                {
                    await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "valid",
                        otDetailW.id, scene, null, staff.id, otDetailW.valid.ToString(), "0", "免除当日超时费"));
                    otDetailW.valid = 0;
                    otDetailW.update_date = DateTime.Now;
                    _db.Entry(otDetailW).State = EntityState.Modified;
                    await _db.SaveChangesAsync();
                }
                // 3) 当天减免：仅在有 valid=1 减免时才作废（避免 UpdateSingleDiscount(amount=0,无行) NRE）
                var existDiscountW = await _db.discount.Where(d => d.order_id == rental.order_id
                    && d.biz_type == "租赁" && d.biz_id == rental.id && d.sub_biz_type == "日租金"
                    && d.sub_biz_id == rentDetail.id && d.ticket_code == null && d.valid == 1)
                    .AsNoTracking().FirstOrDefaultAsync();
                if (existDiscountW != null)
                {
                    await _orderHelper.UpdateSingleDiscount((int)rental.order_id, "租赁", rental.id, "日租金",
                        rentDetail.id, 0, staff.id, scene);
                }
                Rental waivedRental = await GetRental(rentalId);
                return Ok(new ApiResult<Models.Rental?>() { code = 0, message = "", data = waivedRental });
            }

            // ===== 路径 B：正常更新 / 从免除恢复 =====
            // 1) 当天租金额 + 复活（"金额是否变" 与 "是否需复活" 相互独立）
            bool rentDirty = false;
            if (rentDetail.amount != rent)
            {
                await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "amount",
                    rentDetail.id, scene, null, staff.id, rentDetail.amount.ToString(), rent.ToString(), "修改租金"));
                rentDetail.amount = rent;
                rentDirty = true;
            }
            if (rentDetail.valid != 1)
            {
                await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "valid",
                    rentDetail.id, scene, null, staff.id, rentDetail.valid.ToString(), "1", "恢复当日租金"));
                rentDetail.valid = 1;
                rentDirty = true;
            }
            if (rentDirty)
            {
                rentDetail.update_date = DateTime.Now;
                _db.Entry(rentDetail).State = EntityState.Modified;
                await _db.SaveChangesAsync();
            }
            // 2) 当天减免（与现有不同才写；UpdateSingleDiscount 自带"非0复活/0作废"）
            var existDiscount = await _db.discount.Where(d => d.order_id == rental.order_id
                && d.biz_type == "租赁" && d.biz_id == rental.id && d.sub_biz_type == "日租金"
                && d.sub_biz_id == rentDetail.id && d.ticket_code == null && d.valid == 1)
                .AsNoTracking().FirstOrDefaultAsync();
            double curDiscount = existDiscount == null ? 0 : existDiscount.amount;
            if (curDiscount != discount)
            {
                await _orderHelper.UpdateSingleDiscount((int)rental.order_id, "租赁", rental.id, "日租金",
                    rentDetail.id, discount, staff.id, scene);
            }
            // 3) 当天超时费 upsert（按天：rental_id + 当天 + 超时费；不限 valid 以支持恢复）
            Models.RentalDetail otDetail = await _db.rentalDetail
                .Where(d => d.rental_id == rentalId && d.rental_date.Date == theDay && d.charge_type == "超时费")
                .OrderByDescending(d => d.id).FirstOrDefaultAsync();
            if (otDetail != null)
            {
                if (overtime <= 0)
                {
                    if (otDetail.valid == 1)
                    {
                        await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "valid",
                            otDetail.id, scene, null, staff.id, otDetail.valid.ToString(), "0", "清空超时费"));
                        otDetail.valid = 0;
                        otDetail.update_date = DateTime.Now;
                        _db.Entry(otDetail).State = EntityState.Modified;
                        await _db.SaveChangesAsync();
                    }
                }
                else
                {
                    bool otDirty = false;
                    if (otDetail.amount != overtime)
                    {
                        await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "amount",
                            otDetail.id, scene, null, staff.id, otDetail.amount.ToString(), overtime.ToString(), "修改超时费"));
                        otDetail.amount = overtime;
                        otDirty = true;
                    }
                    if (otDetail.valid != 1)
                    {
                        await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "valid",
                            otDetail.id, scene, null, staff.id, otDetail.valid.ToString(), "1", "恢复超时费"));
                        otDetail.valid = 1;
                        otDirty = true;
                    }
                    if (otDirty)
                    {
                        otDetail.update_date = DateTime.Now;
                        _db.Entry(otDetail).State = EntityState.Modified;
                        await _db.SaveChangesAsync();
                    }
                }
            }
            else if (overtime > 0)
            {
                Models.RentalDetail newOt = new Models.RentalDetail()
                {
                    id = 0,
                    rental_id = rentalId,
                    rent_item_id = null,
                    charge_type = "超时费",
                    rental_date = rentDetail.rental_date,
                    rent_price_id = null,
                    amount = overtime,
                    memo = "",
                    staff_id = staff.id,
                    valid = 1,
                    create_date = DateTime.Now
                };
                await _db.rentalDetail.AddAsync(newOt);
                await _db.SaveChangesAsync();
                await _db.coreDataModLog.AddAsync(CoreDataModLog.CreateManualLog("rental_detail", "amount",
                    newOt.id, scene, null, staff.id, "0", overtime.ToString(), "新增超时费"));
                await _db.SaveChangesAsync();
            }
            Rental updatedRental = await GetRental(rentalId);
            return Ok(new ApiResult<Models.Rental?>() { code = 0, message = "", data = updatedRental });
        }
```

- [ ] **Step 2: 编译验证**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet build SnowmeetApi.csproj -nologo`
Expected: `Build succeeded.`，**0 Error**（历史告警 ~14 条无关，可忽略）。若报 `_oriConfig` / `_httpContextAccessor` 未定义，说明锚点没对上——这两个字段在 RentController 已存在（现方法第 2) 步原本就这么 new OrderController），确认替换范围正确。

- [ ] **Step 3: 行为验证（手工 DB，需有效 sessionKey + 本地直连或部署后）**

> 无自动化测试，按 spec §7 跑这些 SQL 核对。`{rid}`=测试 rental_id，`{dtl}`=当天租金 detail id。先在数据库找一个未结算、有 ≥2 天明细的租赁。

1. **按天超时费互不覆盖**：对第 1 天调 `overtime=10`、第 2 天调 `overtime=20`（waived=false）后：
   ```sql
   SELECT id, rental_date, charge_type, amount, valid FROM rental_detail
   WHERE rental_id={rid} AND charge_type='超时费' ORDER BY rental_date;
   ```
   预期：两条超时费，各挂各自 `rental_date`，amount 分别 10 / 20。
2. **超时费清零**：对第 1 天调 `overtime=0` → 该天那条 `valid=0`，第 2 天那条不变。
3. **免除**：对某天调 `waived=true` →
   ```sql
   SELECT id, charge_type, amount, valid FROM rental_detail
   WHERE rental_id={rid} AND CAST(rental_date AS date)='{当天}';
   SELECT id, amount, valid FROM discount
   WHERE biz_type='租赁' AND biz_id={rid} AND sub_biz_type='日租金' AND sub_biz_id={dtl} AND ticket_code IS NULL;
   ```
   预期：当天租金/超时费 `valid=0` 且 **amount 不变**；该日租金减免 `valid=0` 且 amount 不变。
4. **恢复**：对同一天调 `waived=false`（rent/overtime/discount 传原值）→ 上面几条 `valid` 全回 1、金额原样。
5. **NoTracking 回归（必测）**：第 3、4 步执行后**直接查 DB 确认 valid 真的变了**（这是 6-14 翻车点：接口返 code=0 但 DB 没动）。
6. **变更留痕**：
   ```sql
   SELECT table_name, column_name, before_value, after_value, memo, create_date FROM core_data_mod_log
   WHERE table_name='rental_detail' AND create_date >= '{今天}' ORDER BY id DESC;
   ```
   预期出现 `免除当日租金 / 免除当日超时费 / 恢复当日租金 / 修改超时费 / 新增超时费` 等 memo。

- [ ] **Step 4: 提交（可选本地检查点，不 push；部署由用户做）**

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi
git add Controllers/RentController.cs
git commit -m "feat(rent): 超时费改按天 + UpdateRentalDayChargesByStaff 支持免除/恢复当日费用

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 前端逻辑 — data.js 入参 + 聚合纳入免除天 + 弹窗状态/handler

**Files:**
- Modify: `snowmeet_wechat_mini/utils/data.js`（`updateRentalDayChargesPromise`，约 666–678 行）
- Modify: `snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js`（聚合块 189–220；data 字段 35–44；handler 335–401）

- [ ] **Step 1: data.js 加 `waived` 入参**

把 `updateRentalDayChargesPromise` 整函数替换为：

```javascript
// 按天一次性修改：当天租金 + 减免 + 超时费（按天 upsert）；waived=true 免除当天全部费用
const updateRentalDayChargesPromise = function (rentalId, rentDetailId, rent, overtime, discount, scene, sessionKey, waived) {
  var updateUrl = app.globalData.requestPrefix + 'Rent/UpdateRentalDayChargesByStaff/' + rentalId
    + '?rentDetailId=' + rentDetailId + '&rent=' + rent + '&overtime=' + overtime + '&discount=' + discount
    + '&waived=' + (waived ? 'true' : 'false')
    + '&scene=' + encodeURIComponent(scene) + '&sessionKey=' + sessionKey
  return new Promise(function (resolve, reject) {
    util.performWebRequest(updateUrl, {}).then(function (rental) {
      resolve(rental)
    }).catch(function (exp) {
      reject(exp)
    })
  })
}
```

- [ ] **Step 2: rent_order_detail.js — 聚合块纳入免除天**

把现有聚合块（从注释 `// 租金明细（按天聚合：每天一行...` 到 `rental.feeRows = feeRows`，约 189–220 行）整段替换为：

```javascript
      // 租金明细（按天聚合：每天一行；免除天连 valid=0 一起纳入并划线；赔偿金按租赁物维度不进此表）
      var feeDayMap = {}
      var feeRows = []
      for (var j = 0; rental.details && j < rental.details.length; j++) {
        var detail = rental.details[j]
        var ct = (detail.charge_type || '').trim()
        if (ct != '租金' && ct != '超时费') continue
        var dayKey = util.formatDate(new Date(detail.rental_date))
        var row = feeDayMap[dayKey]
        if (!row) {
          row = { dateStr: dayKey, rentDetailId: null, rent: 0, overtime: 0, discount: 0,
                  waived: false, _rentValid1: false, _otValidSum: 0, _otAllSum: 0 }
          feeDayMap[dayKey] = row
          feeRows.push(row)
        }
        if (ct == '租金') {
          var isV1 = (detail.valid == 1)
          // 优先取 valid=1 的租金明细；该天只有 valid=0 时标记免除（仍取原值供恢复/划线展示）
          if (isV1 || !row._rentValid1) {
            row.rentDetailId = detail.id
            row.rent = parseFloat(detail.amount) || 0
            // 当天非票券「日租金」减免（不论 valid，取原值——免除后 valid=0 仍能取到）
            var dsum = 0
            var dl = detail.discounts || []
            for (var di = 0; di < dl.length; di++) {
              var dd = dl[di]
              if (dd && (dd.ticket_code == null || dd.ticket_code === '')) dsum += parseFloat(dd.amount) || 0
            }
            row.discount = dsum
            row.waived = !isV1
            if (isV1) row._rentValid1 = true
          }
        } else { // 超时费
          var oamt = parseFloat(detail.amount) || 0
          row._otAllSum += oamt
          if (detail.valid == 1) row._otValidSum += oamt
        }
      }
      for (var fi = 0; fi < feeRows.length; fi++) {
        var r0 = feeRows[fi]
        // 免除天取全部超时费（含 valid=0 原值供恢复/划线）；正常天只取 valid=1
        r0.overtime = r0.waived ? r0._otAllSum : r0._otValidSum
        r0.subtotal = r0.rent + r0.overtime - r0.discount
        r0.rentStr = util.showAmount(r0.rent)
        r0.overtimeStr = util.showAmount(r0.overtime)
        r0.discountStr = util.showAmount(r0.discount)
        r0.subtotalStr = util.showAmount(r0.subtotal)
      }
      rental.feeRows = feeRows
```

- [ ] **Step 3: rent_order_detail.js — data 加 `_dayChargeWaived`**

在 data 区找到 `_dayChargeDiscountOrig: '',`（约 44 行），其后加一行：

```javascript
    _dayChargeWaived: false,
```

- [ ] **Step 4: rent_order_detail.js — onEditDayCharge 带出 waived**

在 `onEditDayCharge` 的 `this.setData({...})` 里，把 `_dayChargeDiscountOrig: String(row.discount),` 这行之后补一行（被划掉的天有 rentDetailId，原有的 `if (row.rentDetailId == null)` 拦截不触发，照常打开）：

```javascript
      _dayChargeWaived: !!row.waived,
```

- [ ] **Step 5: rent_order_detail.js — 新增 toggle handler**

在 `onDayChargeCancel()` 方法之后插入：

```javascript
  onDayChargeWaivedToggle() {
    this.setData({ _dayChargeWaived: !this.data._dayChargeWaived })
  },
```

- [ ] **Step 6: rent_order_detail.js — onDayChargeConfirm 传 waived**

把 `onDayChargeConfirm` 里调用 `data.updateRentalDayChargesPromise(...)` 的那两行替换为（仅在末尾加 `that.data._dayChargeWaived` 第 8 个实参）：

```javascript
    data.updateRentalDayChargesPromise(rentalId, detailId, rent, overtime, discount,
      '租赁订单详细页修改租金明细', app.globalData.sessionKey, that.data._dayChargeWaived)
```

- [ ] **Step 7: 语法验证**

Run:
```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai
node --check snowmeet_wechat_mini/utils/data.js && node --check snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js && echo OK
```
Expected: 打印 `OK`（无语法错误）。

- [ ] **Step 8: 提交（可选本地检查点，不 push）**

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini
git add utils/data.js pages/admin/rent/rent_order_detail/rent_order_detail.js
git commit -m "feat(rent_order_detail): 租金明细聚合纳入免除天 + 弹窗免除状态/入参

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 前端视图 — 弹窗复选框 + 列表划线

**Files:**
- Modify: `snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml`（列表行约 235；弹窗 515–536）
- Modify: `snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss`（追加规则）

- [ ] **Step 1: wxml — 列表行加划线 class**

把列表行（约 235 行）那行：

```html
              <view class="detail-table-row detail-table-row--tappable" wx:for="{{item.feeRows}}" wx:key="dateStr" wx:for-item="row" wx:for-index="fidx" bindtap="onEditDayCharge" data-ridx="{{ridx}}" data-fidx="{{fidx}}">
```

替换为（追加 `detail-table-row--waived` 条件 class）：

```html
              <view class="detail-table-row detail-table-row--tappable {{row.waived ? 'detail-table-row--waived' : ''}}" wx:for="{{item.feeRows}}" wx:key="dateStr" wx:for-item="row" wx:for-index="fidx" bindtap="onEditDayCharge" data-ridx="{{ridx}}" data-fidx="{{fidx}}">
```

- [ ] **Step 2: wxml — 弹窗三输入框加 disabled + 复选框行**

把弹窗里三个 `dc-field`（租金/超时费/减免）+ `dc-actions` 整段（515–536 行内，从第一个 `<view class="dc-field">` 到 `</view>` 闭合 dc-actions）替换为：

```html
    <view class="dc-field">
      <text class="dc-label">租金</text>
      <input class="dc-input {{_dayChargeWaived ? 'dc-input--disabled' : ''}}" type="digit" disabled="{{_dayChargeWaived}}" value="{{_dayChargeRent}}" data-field="Rent" bindinput="onDayChargeInput" placeholder="{{_dayChargeRentOrig}}" />
    </view>
    <view class="dc-field">
      <text class="dc-label">超时费</text>
      <input class="dc-input {{_dayChargeWaived ? 'dc-input--disabled' : ''}}" type="digit" disabled="{{_dayChargeWaived}}" value="{{_dayChargeOvertime}}" data-field="Overtime" bindinput="onDayChargeInput" placeholder="{{_dayChargeOvertimeOrig}}" />
    </view>
    <view class="dc-field">
      <text class="dc-label">减免</text>
      <input class="dc-input {{_dayChargeWaived ? 'dc-input--disabled' : ''}}" type="digit" disabled="{{_dayChargeWaived}}" value="{{_dayChargeDiscount}}" data-field="Discount" bindinput="onDayChargeInput" placeholder="{{_dayChargeDiscountOrig}}" />
    </view>
    <view class="dc-field dc-field--waive" bindtap="onDayChargeWaivedToggle">
      <text class="dc-label">免除本日全部费用</text>
      <view class="dc-checkbox {{_dayChargeWaived ? 'dc-checkbox--on' : ''}}">
        <text wx:if="{{_dayChargeWaived}}" class="dc-checkbox-tick">✓</text>
      </view>
    </view>
    <view class="dc-actions">
      <view class="dc-btn dc-btn--cancel" bindtap="onDayChargeCancel">取消</view>
      <view class="dc-btn dc-btn--confirm" bindtap="onDayChargeConfirm">确定</view>
    </view>
```

- [ ] **Step 3: wxss — 追加划线 + 复选框 + 禁用输入框样式**

在 wxss 末尾（现 505 行 `.dc-btn:active` 之后）追加：

```css
/* 免除态：整行划线 */
.detail-table-row--waived { text-decoration: line-through; color: #b0b0b0; }
.detail-table-row--waived .detail-col-date,
.detail-table-row--waived .detail-col-amount,
.detail-table-row--waived .detail-col-overtime,
.detail-table-row--waived .detail-col-discount,
.detail-table-row--waived .detail-col-subtotal { color: #b0b0b0; }

/* 弹窗：免除复选框行 + 禁用态输入框 */
.dc-field--waive { cursor: pointer; }
.dc-checkbox {
  width: 40rpx; height: 40rpx; border: 2rpx solid #c8cdd4; border-radius: 8rpx;
  display: flex; align-items: center; justify-content: center; background: #fff;
}
.dc-checkbox--on { background: #2EA6D0; border-color: #2EA6D0; }
.dc-checkbox-tick { color: #fff; font-size: 28rpx; line-height: 1; }
.dc-input--disabled { color: #b0b0b0; background: #eef0f2; }
```

- [ ] **Step 4: 模拟器/真机验证（用户执行，本环境无微信开发者工具）**

清缓存 + 编译后，进租赁订单详情 → 展开租金明细：
1. 弹窗在「减免」行与「取消/确定」之间出现「免除本日全部费用 ☐」一行；勾选后三输入框置灰不可输。
2. 勾选+确定 → 列表该天整行横线划掉、仍显原金额；顶部支付/总额不含该天。
3. 点开被划掉的天 → 复选框呈勾选态、金额按原值占位；取消勾选+确定 → 恢复正常显示、重新计入。
4. 某天填超时费只影响该天行；另一天再填超时费两天各显各的（不再互相覆盖）。
5. 点输入框自动清空、可直接输金额（沿用既有 `_resolveDayChargeVal` 留空回退原值）。

- [ ] **Step 5: 提交（可选本地检查点，不 push）**

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini
git add pages/admin/rent/rent_order_detail/rent_order_detail.wxml pages/admin/rent/rent_order_detail/rent_order_detail.wxss
git commit -m "feat(rent_order_detail): 编辑弹窗加免除复选框 + 列表免除天划线

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 部署（用户执行）

1. 重新部署 SnowmeetApi 到 `mini.snowmeet.top`（`dotnet publish -c Release -o <ExecStart 目录>` + restart service）——`UpdateRentalDayChargesByStaff` 改动不重新部署不生效。
2. 微信开发者工具：清缓存 + 编译 + 体验版/真机回归 Task 3 Step 4 清单。
3. 端到端绿灯需有效（未过期）sessionKey。
