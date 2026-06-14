# 2026-06-14 租赁订单明细：删冗余保存按钮 + 租金明细按天超时费列 & 行内编辑

接续 `rent_order_detail`（新版租赁订单详情页）的打磨。本场两件事：① 删掉备注行多余的「保存」按钮；② 给「租金明细」表加「超时费」列，并支持点某天行弹窗改 当天租金/超时费/减免。改动跨 `SnowmeetApi`（后端新接口）+ `snowmeet_wechat_mini`（前端表格/弹窗）。

## 1. 删冗余「保存」按钮

- 需求：备注输入框右侧的「保存」按钮不需要；点输入框按现状弹对话框，输入备注点确定直接存即可。
- 排查发现：备注框（`rental-showcase-memo-box`）和「保存」`van-button` **绑的是同一个** `onModMemo`；而 `onModMemo` 本就是 `wx.showModal({ title:'修改备注', content: rental.memo, editable:true })` → 确定即 `data.updateRentalPromise` 落库 + toast。
- 结论：按钮纯属重复入口，删掉那一行 `<van-button>` 即可，零功能损失；布局不用动（`memo-box` 本就 `flex:1` 撑满）。

## 2. 租金明细：超时费列 + 按天行内编辑

### 2.1 先摸清数据模型（关键，决定了整个方案）

- `rental_detail` 表每行 = **一个 `charge_type`**（`租金` / `超时费` / `赔偿金`）× 一个 `rental_date`，带一个 `amount`。
- 「减免」不是存储列，是 `othersDiscountAmount` = 该 detail 关联的非票 `Discount` 求和（计算属性）。
- 读：`Rent/GetRentalByStaff` → `GetRental()` 用 `.Include(r => r.details).ThenInclude(d => d.discounts)` 把**所有** charge_type 的 detail 都带回（前端旧逻辑是逐 detail 一行渲染，测试单恰好只有 1 条租金）。
- 写：现有 `Rent/UpdateRentalDetails` 只能改**已存在**的 detail（`id==0` 直接 `continue`，不能新建）；超时费在旧逻辑里是 `UpdateRental` 通过 `_filledOverTimeCharge`（`totalOvertimeAmount` setter）**整单单条重建**——作废全部旧超时费明细、只重建一条。

### 2.2 方案抉择（问了用户）

- 抛出核心分叉：超时费目前是「整单一个总额」，而租金/减免按天；租金明细表按天一行，超时费列怎么放？
  - A 超时费按整单（零后端改动，复用现有两个接口）
  - B 超时费**按天**（更直观，需改后端）
- **用户选 B（超时费按天）**。

### 2.3 后端：新接口 `UpdateRentalDayChargesByStaff`

- 路由 `POST Rent/UpdateRentalDayChargesByStaff/{rentalId}`，query 参数 `rentDetailId / rent / overtime / discount / scene / sessionKey`。
- 逻辑：
  1. 用 `rentDetailId` 定位当天「租金」detail（行的真理之源，也据此确定"当天"）。
  2. 租金额变了 → 改 `amount` + 写 `core_data_mod_log` + save。
  3. 减免：先查当天「日租金」现有减免，`!=` 新值才调 `UpdateSingleDiscount`（**守卫见 2.5**）。
  4. 超时费按天 upsert：当天 `charge_type=超时费 valid=1` 的 detail —— 有则改额（清零则 `valid=0`），无且 `overtime>0` 则新建一条（`rent_item_id=null`，`rental_date` 取当天租金 detail 的值）。
  5. 返回 `GetRental(rentalId)` 全量刷新对象。
- 选「新接口」而非扩展 `UpdateRentalDetails`：后者只有 `confirm_rental.js` 在用（且总带 id），其 discount 块对未填 `_filledDiscountAmount` 易 NRE，新接口隔离更安全。

### 2.4 前端

- `rent_order_detail.js`：`renderOrder` 里把 `rental.details` **按天聚合**成 `rental.feeRows`——仅取 `charge_type∈{租金,超时费} && valid==1`，按 `util.formatDate(rental_date)` 归一行：租金=租金 detail 的 amount、超时费=同日超时费 detail 之和、减免=租金 detail 的 `othersDiscountAmount`、小计=租金+超时费−减免；赔偿金不进此表。
- 弹窗：纯 `view`+`input`（`type="digit"` 收小数），3 字段 租金/超时费/减免 + 取消/确定；`catchtap=noop` 防点卡片穿透关闭。`onEditDayCharge` 预填、`onDayChargeConfirm` 调 `updateRentalDayChargesPromise` → 用返回 rental 就地 `order.rentals[ridx]=updated` + `renderOrder` 刷新。
- `data.js`：新增 `updateRentalDayChargesPromise`（POST，body 传 `{}` 让 `performWebRequest` 走 POST，参数在 query）。
- `.wxml`/`.wxss`：表头/行加「超时费」列（在 租金 与 减免 之间），5 列宽重排，行加 `--tappable` 点击反馈 + 弹窗样式（主色 `#2EA6D0`）。

### 2.5 验证 & 查出的坑

- ✅ `dotnet build` 0 error（两次：初版 + 修守卫后）；`data.js`/`rent_order_detail.js` `node --check` 通过。
- ⚠️ **未做真机/模拟器运行验证**（本环境无微信开发者工具）；新接口需重新部署 SnowmeetApi 才生效（无库表变更）。
- 🐞 修了两个 bug：
  - `UpdateSingleDiscount(amount=0)` 在「无现有减免行」时走 else 取 `discount.id` → NRE。加守卫：先查现有减免、`!=` 才调。
  - `catchtap="true"` 会被当作"绑定名为 `true` 的方法"报错；改绑真实 `noop(){}`。
- 📌 既存未修 bug（本次未动，已记 CLAUDE.md）：顶部 showcase 三格金额（超时/租金/小计）字段名拼写与后端对不上 → 恒显 ¥0。所以明细表里改超时费、行小计会变，但顶部那三格不变。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Controllers/RentController.cs`](../SnowmeetApi/Controllers/RentController.cs) | 新增 `UpdateRentalDayChargesByStaff`（按天 upsert 租金/超时费/减免 + 减免 NRE 守卫） |
| [`snowmeet_wechat_mini/utils/data.js`](../snowmeet_wechat_mini/utils/data.js) | 新增 `updateRentalDayChargesPromise` + 导出 |
| [`snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) | 明细按天聚合成 `feeRows`；弹窗状态 + `onEditDayCharge/onDayChargeInput/onDayChargeConfirm/noop` |
| [`.../rent_order_detail.wxml`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxml) | 删备注「保存」按钮；表加超时费列、行可点；3 字段编辑弹窗 |
| [`.../rent_order_detail.wxss`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.wxss) | 5 列布局 + 超时费列 + 点击反馈 + 弹窗样式 |

## 学到的小知识

1. **超时费的两套写路径并存**：旧 `UpdateRental._filledOverTimeCharge` 是「整单单条重建」，新 `UpdateRentalDayChargesByStaff` 是「按天 upsert」。`totalOvertimeAmount` 仍按 type 求和兼容两者，但同一 rental 别混用，旧路径会把按天的多条压成一条。
2. **`UpdateSingleDiscount` 的 NRE 陷阱**：`amount==0 && 无现有 discount 行` 时会走 else 取 `discount.id`（null）崩；调用前必须先比对现有减免值。归属键 `biz_type=租赁 / sub_biz_type=日租金 / sub_biz_id=detail.id / ticket_code=null`。
3. **小程序阻止点击穿透**：`catchtap`/`catchtouchmove` 的值是**方法名**，`="true"` 会去找名为 `true` 的方法报错；要绑真实空方法 `noop(){}`。
4. **`performWebRequest` 用 body 判 GET/POST**：`data==undefined→GET，否则 POST`。要打 `[HttpPost]` 但参数全在 query 时，body 传 `{}` 即可。
5. **后端计算属性 JSON 名按 C# 原样**（`rental_date`/`othersDiscountAmount`/`isPackage` 都原样过）；前端字段拼错（如 `totalOverTimeAmount` vs `totalOvertimeAmount`）就静默拿到 `undefined`，配 `|| 0` 表现为恒 ¥0，极隐蔽。
