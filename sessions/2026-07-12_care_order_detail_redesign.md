# 2026-07-12 新版养护详情页重设计：全量迁移旧页能力 + 非雪季标志 + 任务执行按实际时间引导

按时间线整理。会话起始 start-work（doc/两代码仓全部与远端一致：SnowmeetApi `aabc3527` / mini `41c0744f`）。用户需求原话：「根据现有的微信小程序的养护订单详情页，重新设计新的页面，风格和目前的新页面保持一致。如果是非雪季养护订单，需要有明显的标志。尽可能引导店员执行养护任务的时候，按照实际的任务开始和结束来点击开始/结束的按钮。」改动全落 `snowmeet_wechat_mini`（8 文件），**后端零改动**。

## 1. Plan 模式：探索 + 拍板

### 1.1 三路并行探索（Explore agents）

- **旧页 `pages/admin/care/order_detail`**：任务执行（`task.current` 串行派生 + setTaskStart/setTaskEnd + 强行中止）、发板核销四方式（本人扫码 WebSocket / 验证码 / 拍照凭证两段上传 / 店长确认）、装备基础信息编辑（品牌 picker+新增品牌/序列号分左右/附件/照片增删）、非雪季只靠「寄存或快递」任务隐式区分（无独立徽标）
- **新页 `pages/admin/care/care_order_detail`（7-4 建）**：任务时间线已有开始/结束小按钮、安检/寄存/取板码/店长确认面板；但扫码取板+拍照凭证挂「请使用旧版」提示（wxml L232）、装备信息只读、非雪季只有 care 级小 chip、**列表入口仍跳旧页**（新页仅结算后「查看订单」一个入口）
- **后端 CareTask/接口**：`Care/SetTaskStatus`（已开始→start_time+staff_id / 已完成→end_time+发板自动发券16 / 强行中止→terminate_staff_id）无顺序约束；care.summer ∈ now/later/null；`biz_type='非雪季养护'`；热蜡完成后端自动把寄存任务置已开始；所有所需接口全部已存在 → **后端零改动成立**

### 1.2 用户拍板（AskUserQuestion）

1. **全量迁移 + 切入口**：扫码取板 + 拍照凭证迁入新页，care_order_list 切新页，旧页可退役
2. **装备基础信息编辑一并迁入**
3. **引导强度 = 视觉引导 + 计时提醒**（当前任务高亮大按钮、进行中显示已用时、结束显示耗时、耗时异常短二次确认；不做后端硬约束）

### 1.3 Plan agent 方案要点（已批准，plan 文件 `~/.claude/plans/dapper-foraging-blossom.md`）

| 决策点 | 结论 |
|---|---|
| 非雪季横幅配色 | 琥珀系（`#fffbeb`/`#f59e0b`/`#92400e`）——蓝=操作、绿=成功、红=危险已占用，琥珀与既有 `btn--warning` 警示语义一致 |
| 计时器 | 页面级单个 `setInterval` 30s 一跳，只 setData 进行中任务 `_elapsedStr` 路径；挂 `this._elapsedTimer` 不进 data；onHide/onUnload 清理 |
| WebSocket 扫码 | 页面级单例（同一时刻仅一个 care 扫码态）；切方式/折叠卡/离开页统一 `_closeScan()` |
| UI 状态记忆 | `_expanded`/`_veriType` 按 care.id 记忆 `this._uiState`，loadOrder 全量重渲染回填 |
| 编辑取消/保存 | 都走 `loadOrder()` 全量刷新（服务端为真理之源） |
| 内联接口 | 新页用到的旧页内联接口全部收口 `utils/data.js`；旧页不动 |

## 2. 实施前关键核实

### 2.1 `CareController.UpdateCare`（L28-63）careImages diff 规则

- oriCare.careImages 里「posted care.careImages 无对应 id」的行 → `Entry(oriImage).State = Deleted` **物理删**
- `care.tasks = null` 后 `_db.care.Update(care)` → payload 里 tasks 被忽略（发不发无所谓）
- **推论**：保存 payload 必须带全要保留的 careImage（含原 id）；新照片 id=0 由 Update 图插入

### 2.2 `CareImage` 模型字段（Care.cs:137-151）

id/image_id/care_id/title/valid/update_date/create_date + care/image 两导航。**扁平化只发 {id,care_id,image_id} 会让 create_date 被模型默认 `DateTime.Now` 冲掉** → 既有行必须以 raw 原对象为基底（保留全部标量），仅剥 `.image`/`.care` 导航（防 EF 图附加撞键，7-8 同族坑）

### 2.3 print-care 组件依赖

`print_care_label.js` 读 `care.shop`（L44）/ `care.customerName`（L196）/ `care.customerCell`（L197）——旧页 showPrintBackDrop 会先塞；**新页 7-4 版没塞 → 打印顾客名/电话/店铺空**（存量隐患，本场顺手修）

### 2.4 拍照缩略图来源

旧页 afterReadPick 用 `e.detail.file.thumb`；care_recept_form 模式 `uploadFile.thumb || uploadFile.tempFilePath` fallback → 沿用后者

## 3. 实施（8 文件）

### 3.1 `care_order_detail.js`（整文件重写，~360→~850 行）

- **data 新增**：`summerBanner{show,desc}` / `scanQr{careId,url,status}` / `addBrand{show,cidx,name,chineseName}` / `skiBrandList/boardBrandList`
- **实例字段**（不进 data）：`_elapsedTimer` / `_runningPaths` / `_scan{careId,qrCode,socketTask,replied}` / `_uiState{expanded,veriType}` / `_rawCares` / `_loadedOnce` / `_targetCareId`
- **生命周期**：onLoad 解析 `options.q`（`util.parseQuery`，标签二维码扫码进入）+ `options.careId`（深链定位）+ 加载双/单板品牌字典；onShow `_loadedOnce` 才 loadOrder，**编辑中跳过刷新**（相机/相册返回可能触发 onShow，整页重载丢编辑内容）但补启 timer；onHide/onUnload 停 timer + `_closeScan()`
- **非雪季**：renderOrder 统计 nowCount/laterCount/otherCount → `summerBanner.desc`（「立等现修 N 件 · 寄存后修 M 件」，其他归「非雪季养护 N 件」，全空兜底「本单含非雪季养护装备」）；`_renderCare` chips 改对象数组，非雪季推 `{text:'非雪季·立等现修/寄存后修/非雪季', cls:'chip-summer'}`
- **任务派生扩展**：`_done`/`_running`/`_isMine`/`_elapsedStr`（进行中已用时）/`_durationStr`（完成实际耗时）/`_hint`（未开始→「请在实际开始操作时点击，系统将记录真实开始时间」；进行中本人→「完成后请及时点击结束…」；他人→「xx 执行中」）；`_current = (!done && !currentFound) || _running`（**加 `|| _running` 保证乱序开始的任务也能结束**，对齐旧页语义）
- **计时**：`_fmtDuration(ms)`（<60s→X 秒 / <60min→X 分钟 / ≥→X 小时 Y 分）；`_collectRunning` 收集 `_runningPaths` 启停 timer；`_tickElapsed` 一次 setData 合并多路径
- **onTaskStart**：弹窗文案「点击确定后将记录「{任务名}」的实际开始时间，请确保现在开始操作」
- **onTaskEnd**：强行中止分支不变；正常结束 modal 显示实际耗时，**elapsedMs<60000 追加第二个 modal「本任务仅用时 X 秒，确认已实际完成操作？」（确认完成/返回）**，两级确认才 `_commitTaskEnd`
- **发板核销**：`onVeriTypeTap` 调度（写 `_uiState.veriType`；切走扫码先 `_closeScan`；选验证码弹「发送给【{member.title||contact_name}】手机号【…】」确认）；`_openScan`→`createScanQrCodeByStaffPromise('care_veri_'+careId,…)`→`getOAQrCodeUrlPromise`→`_startSocket`（`wss://{domainName}/ws` send queryqrscan）；`_onScanMessage` 本人→取 `find(task_name==='发板')`（**不用旧页的 `tasks[length-1]`**）→SetTaskStatus '扫码取板'→toast「扫码发板完成」（toast 带 icon ≤7 字）；非本人→toast「顾客非本人」+ scanQr.status='broken' 显示「重新生成二维码」；`_onScanClosed` 未 replied→broken 显示「重新连接」（**不用旧页 navigateBack modal**）；`_closeScan` 未 replied 时 fire-and-forget `StopQeryScan` + close socket + 清态；`_syncScanWithOrder` loadOrder 后发板已非待核销即清理
- **拍照凭证 onPickPhotoRead**：showLoading → 原图上传（purpose '养护取板'）→ 缩略图上传 → `setCarePickImagePromise` → SetTaskStatus '上传照片取板' → loadOrder；catch hideLoading+toast（uploadFilePromise 已修非 2xx reject，链路天然中断）
- **装备编辑**：onEditTap 预派生 `_brandIndex`（WXML 不能 indexOf）/`_diffSerial`/`_leftSerial/_rightSerial`/`_photoFiles`（van-uploader file-list，image_id 对齐服务端）/`_specialKey`；字段 handler `onEditFieldBlur`（data-field 泛化）+ `onBoardFrontTap/onSerialDiffTap/onWithPoleTap/onSpecialTap/onBrandChange`（末项开新增品牌弹层）；照片 `onEditPhotoRead`（两段上传、uploading 占位、失败剔除，照搬 care_recept_form）/`onEditPhotoDelete`；**onEditSave 以 `_rawCares[cidx]` 为基底**合成 payload——编辑字段合入、`serials=left|right` 合成、**bool coerce 不发 null**（with_pole/entertain/warranty/use_card）、careImages 既有行保留 raw 原对象剥导航 + 新行 `{id:0,care_id,image_id,valid:true}` → `updateCarePromise(…,'养护订单详情页修改装备信息')` → loadOrder
- **onSafeCheck 顺手加固**：payload careImages 走 `_stripImageNavs`（剥 image/care 导航），其余不变
- **新增品牌**：`onAddBrandConfirm` → `updateCareBrandPromise` → 返回列表补「新增品牌」末项 + 定位新品牌回填 brand/_brandIndex
- **深链**：`_applyTargetCare`（careId→只展开目标 care + `wx.pageScrollTo('#care-{id}')`，一次性守卫）
- **打印修复**：`_preparePrint(cidx)` 塞 customerName（member.title 优先，回退 contact_name/'散客'）/customerCell/shop

### 3.2 `care_order_detail.wxml`（整文件重写）

顶部非雪季横幅 → 订单信息/支付信息（不变）→ 装备卡：chips 对象渲染 + `id="care-{{care.id}}"` + 装备信息「编辑」入口 + 只读/编辑二态面板 + 任务时间线三态（完成收敛单行 / 当前高亮大按钮+hint+elapsed / 未来淡化）+ 安检（确认按钮 btn--block 化 + hint「确认后您将成为本次养护的安全负责人」）+ 寄存（面板条件放宽 `_current` 即显，覆盖未自动开始的边缘态）+ 发板四方式面板（segmented + 扫码二维码区/验证码行/拍照 uploader/店长确认，**删旧「请使用旧版」提示**）+ 发板完成凭证展示 + 打印行；尾部 print-care popup + 新增品牌 popup

### 3.3 `care_order_detail.wxss`

追加：summer-banner/chip-summer、task-row--current 强化（浅蓝底+8rpx 蓝左边条）/--future 淡化/--done 收敛、task-elapsed（脉冲圆点 keyframes）、btn--block/btn--danger-plain/btn--half、task-hint、veri-seg/scan-qr、edit-panel/edit-block/seg-row、brand-modal

### 3.4 `care_order_detail.json`

+`van-uploader`（miniprogram_npm 已有且 app.json 全局注册过，页面级再注册保险）

### 3.5 `utils/data.js`

新增 7 个 promise（GET 走 `util.performWebRequest(url, undefined)`）：`createCareVerifyCodePromise` / `veriCareFinishCodePromise` / `setCarePickImagePromise` / `updateCareBrandPromise` / `createScanQrCodeByStaffPromise`（内带 sessionType=wechat_mini_openid）/ `stopScanQrCodePromise` / `getOAQrCodeUrlPromise`（裸 wx.request，返回纯字符串不走 ApiResult 解包）+ exports

### 3.6 入口切换（3 处）

- `care_order_list.js:228`：`'order_detail?orderId='` → `'care_order_detail/care_order_detail?orderId='`
- `member_detail.js:158`：养护跳转 → `/pages/admin/care/care_order_detail/care_order_detail?orderId=`
- `print_care_label.js:292-294`：标签二维码 URL → `mapp/admin/care/care_order_detail/care_order_detail?orderId=&careId=`（注释标明需公众平台登记 + 旧标签兼容）
- `care_back_drop.js` 三处不切（旧开单收银组件，随旧流程退役）；旧页 4 文件 + app.json 注册不动

## 4. 静态验证（全过）

- 5 个改动 js `node --check` 通过（微信开发者工具自带 node：`C:\Program Files (x86)\Tencent\微信web开发者工具\node.exe`）
- wxml 标签平衡（自写配对脚本）：view 130/130、block 11/11、text 65/65、picker 1/1
- wxml 36 个事件绑定（bindtap/catchtap/bindblur/bindinput/bindchange/bind:after-read/bind:delete/bind:close）与 JS 方法一一对应（脚本核验）
- wxss 括号 105/105、无中文类名选择器
- 全项目 grep：pages 下无残留跳旧页/「请使用旧版」文案；剩余旧页引用仅 care_back_drop（有意保留）+ app.json 注册（兼容旧标签）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `pages/admin/care/care_order_detail/care_order_detail.js` | 整文件重写：非雪季横幅派生、任务引导（计时/耗时/二次确认）、扫码 WebSocket 单例、拍照凭证、装备编辑、q/careId 深链、打印补三字段 |
| `pages/admin/care/care_order_detail/care_order_detail.wxml` | 整页重构：横幅/chips 对象/任务三态/发板四方式/编辑二态/品牌弹层 |
| `pages/admin/care/care_order_detail/care_order_detail.wxss` | 追加 ~15 组新样式（琥珀横幅/当前任务高亮/计时/大按钮/编辑面板等） |
| `pages/admin/care/care_order_detail/care_order_detail.json` | +van-uploader |
| `pages/admin/care/care_order_list.js` | 列表入口切新页 |
| `pages/admin/member/member_detail.js` | 会员详情养护跳转切新页 |
| `components/care/print_care_label.js` | 标签二维码 URL 切新页（需公众平台登记） |
| `utils/data.js` | +7 个 promise 封装（旧页内联接口收口） |

## 学到的小知识

1. **`UpdateCare` 对 careImages 按 id diff 物理删**：posted 里没有的既有 id 会被删；payload 必须带全保留行。既有行以服务端原对象为基底（保全部标量）只剥 `.image/.care` 导航——扁平化新对象会让 create_date 等被模型默认值冲掉
2. **print-care 组件吃 care 上的 customerName/customerCell/shop 三个前端临时字段**：调用方必须先塞（旧页 showPrintBackDrop 模式），7-4 新页漏塞是存量 bug
3. **旧页扫码取板用 `tasks[tasks.length-1]` 定位发板任务**：依赖加载顺序，新页改 `find(t => t.task_name === '发板')` 更稳
4. **`_current` 派生要 `|| _running`**：只取「第一个未完成」会让乱序已开始的任务（如后端自动开始的寄存）失去结束按钮
5. **wx.showToast 带 icon 文案 ≤7 字**（「扫码发板完成」6 字）；`wx.showModal` confirmText ≤4 字（「确认完成」）
6. **onShow 编辑中要跳过自动刷新**：Android 相机/相册可能触发页面 onHide/onShow，整页 loadOrder 会丢编辑内容；跳过时记得补启计时器
7. **`wx.pageScrollTo({selector})`** 基础库 2.7.3+ 可用，配 `id="care-{{id}}"` 做深链定位
8. **标签二维码换页面路径 = 公众平台新登记**：「扫普通链接二维码打开小程序」规则按 URL 前缀映射页面，换路径必须为新前缀登记（体验版填测试链接）；已打印旧标签指旧页 → 旧页注册必须保留
