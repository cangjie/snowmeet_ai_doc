# 2026-07-04 养护开单迁移：旧版养护业务结构 × 新版租赁开单公共流程，前后端全量落地

按时间线整理。接续租赁现场开单流程重构（recept_entry → recept_new + rent_recept_form → settle 已跑通），本场把养护（maintain）开单迁移到同一套公共流程。用户需求原话：「参考小程序过去的养护开单的代码和现在新重构的租赁开单的流程，迁移养护开单。会员、开单流程都遵循租赁开单的流程，因为这是个公共流程。而养护自身的业务数据结构，参考旧版的代码。」改动落在 `SnowmeetApi`（3 接口）+ `snowmeet_wechat_mini`（1 新组件 + 1 新页面 + 4 处接线）。

## 1. Plan 模式：三路并行探索 + 方案设计

### 1.1 探索分工（3 个 Explore agent 并行）

- **旧版养护开单**：`components/care/care_recept.js`（836 行大表单）+ `care_back_drop.js`（整单 `Order/PlaceOrder` 一次性提交，无草稿）；care 对象字段、票券模板 12/16/17/18 逻辑、定价 `getProduct()`（双项/修刃/打蜡 × 立等/次日、summer 硬编码 330、质保/招待 0 元）
- **新版租赁架构**：`recept_entry` 已有 maintain 卡片（且已要求姓名+手机号+性别）；`recept_new` 里 maintain 是占位符「养护开单（下一步迁移）」；settle 页完全类型无关只吃 orderId；rent_recept_form 组件契约 = props {shop, memberId, rentals} + events syncRent/addAction/checkout
- **后端 Care 模型**：`Models/Care/Care.cs`（表 care）+ `CareTask.cs`（表 care_task，任务 sort 10 安检/20 修刃/30 维修/40 热蜡机打蜡/50 刮蜡/60 发板）+ Brand/Series/CareImage 全部现成；`EffectCareOrder` 按 flags 生成任务序列

### 1.2 主 agent 亲自验证的载荷事实（探索报告之外）

- **支付触发已就绪，零改动**：`DealSuccessPaidOrder`（OrderController.cs:2293，微信/支付宝回调）对 type=='养护' 调 `EffectCareOrder`；`EffectUnpaidOrder`（手工收款）内部调 DealSuccessPaidOrder；`PayWithDeposit` 直接调 —— 三条支付路径全通
- **旧 `PlaceOrder` 养护分支（OrderController.cs:832-977）**：服务端权威定价 + ticket fixed_price 覆盖 + `total_amount=paying_amount=total` + total==0→dealed=1 + member_pick_date=urgent?今:明 + Discount 记录（**发现既存 copy-paste bug：ticket_discount 分支 amount 误用 `cares[i].discount`**）+ paying_amount==0 时立即 EffectCareOrder
- **EffectCareOrder 三坑**（CareController.cs:397-）：① `.Include(o.cares)` **不过滤 care.valid** → 草稿删除必须物理删行；② 非雪季分支 `GenerateTicketByAction(17/18, (int)care.order.member_id, ...)` 散客 null 强转必炸；③ `order.code.Split('_')` 生成 task_flow_code → 必须先 GenerateOrderCode
- `Rent/GetReceptingOrders` 不按 type 过滤 → 养护草稿天然进中断单列表

### 1.3 用户拍板（AskUserQuestion）

1. 表单功能范围：**全量对齐旧版**（服务项+定价、照片、票券、非雪季、质保/招待、维修项，一次到位）
2. 支付完成「查看订单」：**本期新做养护详情页**（Alpine 风格，对标 rent_order_detail）

插曲：Phase 2 的 Plan agent 撞会话限额（"You've hit your session limit"）返回空结果，主 agent 用探索产物自行完成方案设计，未重试。

## 2. 后端实现（SnowmeetApi，branch ai，编译 0 错误）

### 2.1 `CareController.SaveCareRecept`（新，POST，镜像 SaveRentRecept 4135-4324）

- 鉴权 staff≥100；开头置空 `order.member/staff/rentals`、每个 care 的 `order/tasks/pickImage`、careImages 的 `care/image` —— 防 JSON 往返子图让 `_db.Update` 在 TrackGraph 抛 `Value cannot be null (key)`（SaveRentRecept 6-21续2 同款教训）
- id==0：type='养护'、valid=0、recepting=1、is_test 按 Host 判、cares[].valid=0，`AddAsync` 级联插 cares+careImages
- id>0 增量：新 care（id==0）挂 order_id；`_db.Update(order)` 后按 DB↔payload diff **物理删除**被移除的 care（连带 care_image 行）；已有 care 的 careImages 按 id diff 删缺失照片行（graph Update 不会删缺失子行）

### 2.2 `RentController.GetReceptingOrder` 扩展（:4575）

加 `.Include(o => o.cares).ThenInclude(c => c.careImages).ThenInclude(ci => ci.image)` + `order.cares` 按 id 正序。租赁单 cares 空、养护单 rentals 空，互不影响，一个接口两用。

### 2.3 `OrderController.PlaceCareOrder`（新，GET `{tempOrderId}`，插在 PlaceRentOrder 后）

- 守卫：staff≥100、`valid==0 && type=='养护'`、cares 非空；**任一 care.summer!=null 且 order.member_id==null → 返回「非雪季养护需要匹配会员，请先录入顾客手机号」**（对应坑 ②）
- 每 care：summer→biz_type='非雪季养护' → `_careHelper.GetProduct(shop, care)` 服务端重算 common_charge（null/质保/招待→0；ticket valid=1 used=0 的 productTicketTemplate.fixed_price 覆盖）→ member_pick_date → valid=1 + `Entry(care).State=Modified`（全局 NoTracking）
- 汇总：`total_amount=paying_amount=Σ(common+repair−discount−ticket_discount)`；total==0→dealed=1；`GenerateOrderCode`（坑 ③：先于 EffectCareOrder）→ SaveChanges → Detach → Discount 记录（**ticket_discount 金额写正确值，不复刻旧 bug**）→ `paying_amount==0` 时 EffectCareOrder + GetOrder 重载返回

## 3. 前端实现（snowmeet_wechat_mini）

### 3.1 新组件 `components/reception/care_recept_form/`（4 文件）

- 契约镜像 rent_recept_form：props {shop, memberId, cares}；events `syncCare {cares, needUpdate}` / `checkout {cares}`；wxss `@import "../rent_recept_form/rent_recept_form.wxss"` 复用卡片/chip/结算条/金额 modal，只写增量样式
- 一个 care = 一块板：折叠态单行（装备名 + 服务 chips + 金额，缺项名称变红）/ 展开态编辑；van-swipe-cell 左划删除
- 字段全量对齐旧版：装备类型（双板/单板 toggle，切换清品牌与维修项）、品牌 picker（`Care/GetBrands` + 末项「＋新增品牌」→ `Care/UpdateBrandByStaff`）、长度、照片（旧 `uploadFilePromise` 两段上传即传即得 image_id）、优惠券（复用 `components/ticket_selector/ticket_list`；模板 12→free_wax+fixed_price 定价、16→双项减30/单项减20、17→summer now、18→summer later）、修刃+角度（默认 89）、热蜡（连带刮蜡、与机打蜡互斥）、刮蜡、立等、非雪季 now/later（联动服务 flags + 禁用常规项）、维修项多选（`Care/GetOthersService` + 自由追加）+ 附加费/减免（金额 modal 二次确认）、特殊（普通/招待/质保）、备注
- `evalCare` 对齐旧 `util.getCareWellFormMessage`：类型必选 → 图片或品牌+长度必填其一 → 至少一个业务项；`_othersView` 预置 `on` 布尔标记（WXML 不支持 `.indexOf()`，6-30 教训）
- 估价仅展示（`getCareProductPromise` 名称匹配），真理之源 = PlaceCareOrder 服务端重算

### 3.2 recept_new 接线

- wxml：maintain 渲染 `<care-recept-form>`（删占位）；json 注册组件
- `onLoad` 找回：**`TYPE_TO_BIZ[(recoveredOrder.type||'').trim()]` 反推 bizType** —— 原逻辑只看 URL/draft，养护草稿会被租赁表单渲染；cares 补 timeStamp
- `saveCareReceptOrder()`：payload type='养护'、rentals:[]、cares 剥 ticket/product/tasks/order 对象；**响应按下标合并回本地 careImages/ticket/product** —— 后端 CareImage 模型没有 url/thumb 展示字段，round-trip 会丢照片显示地址
- `_checkoutCare()`：await 落盘 → `Order/PlaceCareOrder/{id}` → navigateTo settle → 本地态脱钩（cares/careImages id 清零，同租赁写法）；`performWebRequest` 对 code!=0 自动 toast 后端 message（非雪季拦截提示天然透出）

### 3.3 结算链路 + 新版养护详情页

- `settle/index.js` paid modal「查看订单」按 `detail.order.type` 路由：'养护' → `/pages/admin/care/care_order_detail/care_order_detail?id=`，否则原租赁详情
- `order-summary-card` 加 `isCare` 分支：「养护内容」= 装备·品牌·长度（+description）
- 新页 `pages/admin/care/care_order_detail/`（app.json 已注册）：订单信息双列 + 支付四格（总计/已付/退款/待付）+ 折叠明细 + 装备卡：服务 chips、照片 previewImage、任务时间线（第一个未完成任务派生 `_current` 可操作）、任务开始/结束（他人执行中→强行中止确认，对齐旧页）、安检录入（身高/体重|间距/前后脱落值|左右角度，字段用后端 `left_angle/right_angle`）+「确认安全」（updateCarePromise scene '安全检查' + SetTaskStatus 完成）、寄存或快递（寄存/快递/万龙寄存柜 + 快递单号必填）、发板核销（发送取板码 `CreateVerifyCode` + 4 位码验证 `VeriCareFinishCode` + 店长确认 ≥200）、打印标签/小票（复用旧 `print-care` 组件）
- **有意留在旧页的**：发板「扫码取板」（WebSocket + QrCode 链路）和「拍照凭证」（SetPickImageId）两种核销、装备基础信息编辑（新页只读）—— 页内有文字提示引导

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/CareController.cs` | 新增 `SaveCareRecept`（草稿保存，care 物理删 + careImages diff） |
| `SnowmeetApi/Controllers/RentController.cs` | `GetReceptingOrder` include cares(+careImages.image) + cares 正序 |
| `SnowmeetApi/Controllers/OrderController.cs` | 新增 `PlaceCareOrder`（服务端定价/0元单即时生效/summer 无会员拦截） |
| `snowmeet_wechat_mini/components/reception/care_recept_form/*`（新×4） | 养护开单表单组件（全量字段） |
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.{js,wxml,json}` | 养护分支：onSyncCare/saveCareReceptOrder/_checkoutCare/bizType 反推 |
| `snowmeet_wechat_mini/pages/payment/settle/index.js` | paid modal 按 order.type 路由详情页 |
| `snowmeet_wechat_mini/components/order-summary-card/index.{js,wxml}` | 养护内容展示分支 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_detail/*`（新×4） | 新版养护订单详情页（Alpine） |
| `snowmeet_wechat_mini/app.json` | 注册 care_order_detail 页面 |

## 学到的小知识

1. **EffectCareOrder 加载 cares 不过滤 valid**：`.Include(o => o.cares)` 全量拿。草稿购物车里删掉的 care 若只软删（valid=0），下单生效时照样给它生成任务序列 —— SaveCareRecept 必须物理删行
2. **csproj 未开 `<Nullable>enable</Nullable>`**：非空 `string equipment` 不触发 ASP.NET 隐式 Required 校验，`equipment=null` 的空白草稿能正常落库。若未来开 nullable，这里会开始 400
3. **Care 模型 `warranty/entertain/use_card` 是 bool、`with_pole` 是 bool?**：旧前端发 1/0 数字，新前端必须发布尔（同 6 月 `atOnce` 反序列化 400 教训）；`left_angel` 是旧前端拼写错误，后端真名 `left_angle`
4. **EffectCareOrder 非雪季分支两个隐雷**：`(int)care.order.member_id` 强转（散客 null 崩）+ `order.code.Split('_')`（code 未生成崩）→ PlaceCareOrder 用「summer 拦截 + 先 GenerateOrderCode」双前置化解，不动 300 行老函数
5. **后端模型没有的展示字段 round-trip 即丢**：CareImage 无 url/thumb → SaveCareRecept 响应里照片显示地址消失。解法 = 前端保存后按下标把本地展示对象合并回响应（同 rent 流程 realGuaranty 教训的变体）
6. **子 agent 也会撞会话限额**：Plan agent 跑了 45 次 tool 调用后限额中断、只返回「You've hit your session limit」。探索产物在主 agent 手里时可直接自行设计，不必重跑
