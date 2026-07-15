# 2026-07-10~11 季卡与服务端计费：punch_card 季卡化、养护计费/服务项服务端化、保存串行化、非雪季数据修复

按时间线整理。接 7-09 券/卡双 tab 选择弹层，本场是用户边真机联调边提需求的快速迭代（十余轮），主线四条：punch_card 季卡语义、养护计费全面服务端化、开单稳定性修复、非雪季存量数据核查与修复。**两代码仓已全部 commit+push**（SnowmeetApi `aabc3527` / mini `41c0744f`）。

## 1. punch_card 季卡化（用户直改 DB schema，代码跟上）

### 1.1 total/punches 可空 → 线上 500

- 用户改 `punch_card.total/punches` 可空，**total=NULL 即季卡（不限次数）**；线上 `GetMemberAssetsByStaff` 立即抛 `SqlNullValueException`（C# 模型不可空，EF 读 NULL 崩）
- 修：`PunchCard.total/punches` → `int?`；`remaining` → `int?`（季卡 null，punches 空当 0）
- 消费方逐个适配：资产聚合排除季卡；`GetPunchCardPresets` 排除季卡（发放路径要求 total>0）；租赁核销列表排除季卡 + `punches = (punches ?? 0) + need`；member_detail 季卡行显示「季卡 · 不限次数」；选卡弹层季卡判定改数据驱动（`total==null`/`isSeason`，卡名兜底）

### 1.2 equip 四字段：限装备季卡

- 新列 `equip_type(8)/equip_brand(32)/equip_scale(16)/equip_serial(64)`；**三个展示字段全非空即绑定**，serial 暂不参与限制（用户明示"未来有可能限序列号"，字段已随接口带回）
- `GetMemberCardsByStaff` 返回四字段 + `equipBound`；同轮加 `bizType` 参数（**养护开单不显示租赁卡**，弹层复用 ticketType 传参）
- 选中限装备季卡：装备类型/品牌/长度自动带入卡绑定值并锁定（类型按钮灰死+toast「该季卡已绑定装备，不可修改」、品牌 picker/长度 input disabled 置灰、橙色提示行）；换券/换卡/不使用解锁（值保留）；`card_equip_lock` 前端标量随保存往返（找回后锁松、值在）
- 测试数据：15506 名下「机打蜡季卡」id=42

## 2. 养护计费/服务项全面服务端化（plan 流程 + 多轮演进）

### 2.1 演进过程（用户逐步收紧）

1. 初版（plan 批准）：`CalcCareCharge` 算 `commonCharge/ticketDiscount`，前端仍留默认/联动
2. 「返回应有的服务选项」→ 加 `deriveServices` + `ApplyDefaultServices`，响应带 services
3. 「payload 应含全部信息，之前加选修刃后季卡信息丢了」→ 全量 payload（wrapper DTO）+ 卡身份先 [NotMapped] 后落 DB 列
4. 「card 跟 care 走不跟订单走」→ 删 wrapper 里的平级 cardId/cardName，**`care.card_id/card_name` 加 care 表实体列**（用户建列，模型映射；中断找回从此可还原选卡）
5. 「热蜡带刮蜡这类联动放后端」→ 加 `changedField` + `ApplyServiceLinkage`，**响应返回整个 care 作为真理之源**
6. 「机打蜡季卡升级热蜡/加修刃按免费打蜡券规则加价」→ `CalcCharge` 加 card 参数，卡名含「机打蜡」走券12模板 fixed_price 加价（`PlaceCareOrder` 同步按 care.card_id 加载卡传入）

### 2.2 定稿架构（真理之源全在服务端）

- 请求：`{shop, memberId, deriveServices, changedField, care}`——每次界面操作全量提交；卡信息只在 care 内
- 响应：`{commonCharge, ticketDiscount, care}`——care 含联动/推导后的服务项 + 盖章后的 common_charge/discount，前端只回填
- 三 helper（`CareController`）：
  - `CalcCharge(shop, care, ticket, card)`：选卡 0（用户拍板，纯卡单 total=0 place 即生效）/ 质保招待 0 / summer 330 / GetProduct+券 fixed_price / 券16 减免双项30单项20 / **机打蜡季卡例外加价**
  - `ApplyDefaultServices`：双项卡→修刃89+热蜡+刮蜡；机打蜡卡→机打蜡；券12→机打蜡；券17/18→非雪季；单项/季卡不默认（季卡默认规则几轮反复后定为"暂不默认，机打蜡季卡除外"）
  - `ApplyServiceLinkage(care, changedField)`：热蜡开关→刮蜡跟随+清机打蜡；机打蜡→清热蜡刮蜡；修刃→角度默认89；summer later/now→三项联动+取消立等。**联动是事件语义，必须知道改的是哪个字段**
- 换券/换卡仍「先清空再套默认」（清空含减免；立等/维修/质保/招待保留）；机打蜡按钮显示条件放宽（券12 或 机打蜡季卡选中 或 free_wax=1，升级热蜡后可切回）

## 3. 开单稳定性修复

### 3.1 「订单尚未生成」（生产实录诊断）

- DB 实查：孤儿草稿**成对出现**（间隔 ~90ms，6+ 对）——order.id=0 时并发保存都走 create 分支重复建单
- 用户场景：下完一单（71866）→ 脱钩（id 清零购物车保留）→ 继续编辑点结算 → 新草稿 create 在飞 → 前置守卫弹「订单尚未生成」
- 修（[recept_new.js](../../snowmeet_wechat_mini/pages/admin/reception/recept_new.js)）：① `saveCareReceptOrder` 串行化入口（在飞排队合并一笔，返回最终状态 Promise）② `_checkoutCare` 删前置 id 守卫（等保存建单后取 id，仍拿不到才提示）③ **响应合并反转**：以响应时刻最新本地状态为基底、只吸收服务端主键（care.id/order_id/careImage.id）——此前晚到旧响应整体覆盖，正是「加选修刃后季卡丢失」的元凶

### 3.2 选卡后装备卡片不折叠

- 根因又是 key 漂移（7-8 已知坑变体）：选卡让表单瞬间「已录入」+ 保存分配真实 id → key 从 `t+timeStamp` 变 `c+id` → 展开记录成孤儿 → 默认规则折叠
- 修：`_refreshCares` key 迁移（新 key 无记录时搬旧 key 记录）+ 选券/卡时显式记展开

## 4. 顾客支付页养护明细（payment_entry）

- 新增「养护内容」段：每件装备一段，列 装备（类型·品牌·长度）/ 项目（对齐开单页 _svcChips 口径，含维修/质保/招待）/ 优惠（券显示 code、卡显示卡名）/ 金额（common+repair−discount−ticket_discount）
- 数据零后端改动（GetOrder 养护分支本就带 cares；card_name 已持久化）；支付宝端未同步（遗留）

## 5. 非雪季养护数据核查（只读）+ 修复（写）

- **口径**：非雪季在管 = 券「非雪季赠双项」`used=0` 的 order 下的 care；寄存方式在 `care_task.deal_method`（task_name='寄存或快递' 行）；热蜡完成自动置寄存「已开始」（CareController:1043）；发板完成自动发券16
- **核查结论**：券未用 143 件 → 寄存+刮蜡都未完成 13 件（真实顾客 10 人，名单含手机号已给用户）；财年 177 件 → 已发板仅 4 件（3 件 later 当天取走 + 1 件 now 寄存两周后提前取）；在途 173 件全表（含手机号）已给用户
- **29 件无「寄存或快递」步骤**分两类：27 件 2026-03-07 前旧流程（任务链=普通养护链，summer 字段空/乱码）+ 2 件未支付单（71528 无支付记录 / 71553 仅作废待支付，各 ¥330 无任务链——未支付 EffectCareOrder 未跑，机制正常）
- **数据写入（用户明确指示）**：26 件补插「寄存或快递」任务——每件 care 内 `sort≥刮蜡` 的行 +1 腾位（原 sort 连续无空隙；sort 全局分配但仅 care 内比较，跨 care 无冲突），插入 `task_name='寄存或快递', memo='非雪季养护', status='未开始', valid=1`，其余可空字段 NULL；单事务 + 逐件校验（热蜡<寄存<刮蜡）+ 抽查。**23837 无热蜡/刮蜡锚点跳过待定**

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Models/Rent/PunchCard.cs` | total/punches/remaining 可空 + equip 四字段 |
| `SnowmeetApi/Models/Care/Care.cs` | card_id/card_name 实体列映射 |
| `SnowmeetApi/Controllers/CareController.cs` | CalcCareCharge 全量版 + CalcCharge/ApplyDefaultServices/ApplyServiceLinkage |
| `SnowmeetApi/Controllers/MemberAdminController.cs` | GetMemberCardsByStaff（bizType/equip/isSeason）+ 消费方可空适配 |
| `SnowmeetApi/Controllers/OrderController.cs` | PlaceCareOrder 共用 CalcCharge（含卡加载） |
| `SnowmeetApi/Controllers/RentController.cs` | 租赁核销可空适配 + 排除季卡 |
| `snowmeet_wechat_mini/components/reception/care_recept_form/*` | _fetchPrice 整包提交/整 care 回填、装备锁定、开关只翻自己、key 迁移 |
| `snowmeet_wechat_mini/components/reception/ticket_card_selector/*` | 季卡数据驱动判定、绑定装备行、bizType 传参 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.js` | 保存串行化 + 响应合并反转 + checkout 守卫重做 |
| `snowmeet_wechat_mini/pages/order/payment_entry.{js,wxml}` | 养护内容明细段 |
| `snowmeet_wechat_mini/pages/admin/member/member_detail.{js,wxml}` | 季卡显示 |
| `snowmeet_wechat_mini/utils/data.js` | calcCareChargePromise 整包版 + getMemberCardsPromise bizType |
| 生产库 | punch_card/care 列变更（用户）；care_task 插入 26 行（本场） |

## 学到的小知识

1. **用户直改 DB schema 时模型必须同批跟上**：列改可空 + 已有 NULL 数据 → 老部署的 EF 读到即 500（不是新功能不可用，是全线崩）。这类改动的部署有硬顺序
2. **服务联动是事件语义**：只看状态区分不了"刚开热蜡（要带刮蜡）"和"开着热蜡手动关刮蜡（要尊重）"，前端必须告知 changedField
3. **保存响应整体覆盖本地状态是状态丢失的总根源**：POST 到响应之间用户还在操作，正确姿势=以响应时刻本地状态为基底、只吸收服务端生成的主键
4. **并发 create 重复建单**：草稿 id=0 时任何两笔在飞的保存都会各建一单；串行化（在飞排队合并）是前端侧最小修复
5. **care_task.sort 全局递增分配、但仅 care 内比较**：给旧数据"中间插一步"用腾位法（组内 ≥锚点 +1）安全
6. **PowerShell `>` 重定向会重编码 UTF-8 stdout 成乱码**：拿中文查询结果直接从 stdout 取，别经文件中转
