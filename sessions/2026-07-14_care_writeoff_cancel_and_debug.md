# 2026-07-14 养护核销全链路 + 取消功能 + 校验 bug 排查：会员身份核验落地，取消养护弹窗一处校验问题未闭环

按时间线整理。本场接续 7-13 的养护订单详情页工作，围绕"养护订单结算时的会员权益核验"这条此前一直搁置的主线，一次性把 plan `0-calm-storm.md` 的全部条目（B1-B4 后端 + F1-F3 前端）落地，随后顺手修了一个安全检查字段的持久化 bug，又做了一个全新的"取消养护"功能（三轮按用户反馈重做），最后被用户在真机上发现的一个校验 bug 打断，排查未完全闭环。改动落在 `SnowmeetApi` + `snowmeet_wechat_mini`。

## 1. 养护开单核销/支付前身份核验（B1-B4 + F1-F3）

### 1.1 业务背景与决策

- 起点是用户提问："目前养护开单过程当中，如果使用了各种卡券，是在什么时候核销？" —— 排查发现现状几乎没有约束：`PlaceCareOrder` 对 0 元单直接 `EffectCareOrder` 立即生效、无任何身份核验；储值 `pay_with_deposit` 只落库意向从未实扣；卡券选了只按 0 计价、不扣次数不置 used。
- 用户给出完整需求："养护开单过程中，如果使用了储值、卡券等权益，最后需要的支付金额如果是0，则需要通过扫码验证扫码的用户就是开单流程中获取到的用户，才可以核销并且使得订单生效；如果需要支付，到结算页面，如果选择微信支付，则需要通过当前会员绑定的微信号扫码，如果选择支付宝支付，则需要先用微信扫码验证身份后，再用支付宝扫码支付。验证身份参考租赁订单详情页的身份验证。"
- 通过 AskUserQuestion 确认三个关键口径：① 同时做储值实扣 + 卡券核销（不是分批做）；② 微信支付本身就视为核验会员本人（支付码即校验，不需要额外一层验证）；③ 仅储值/卡券导致的 0 元单需要核验，质保/招待导致的 0 元单不需要（业务上这类不消耗会员权益）。
- Plan 文档 `0-calm-storm.md` 写就并经 ExitPlanMode 批准，切成 B1-B4（后端）+ F1-F3（前端）共 7 个原子任务，用 TaskCreate 跟踪，全部标记 completed。

### 1.2 后端四块（B1-B4）

- **B1** `CareController.EffectCareOrder`（这是养护订单唯一的"生效"收敛点，五条路径——`PlaceCareOrder` 0元单/`WriteoffCareOrder`/`DealSuccessPaidOrder`/`EffectUnpaidOrder`/`PayWithDeposit`——都汇聚于此）加入卡券核销：遍历 care，`use_card && card_id != null` 时创建 `PunchCardUsed` 记录并扣减 `punches`（季卡 `total==null` 时跳过扣减，因为不限次数）。
- **B2** `OrderController.PlaceCareOrder` 的 0 元单分叉：新增 `usedBenefit` 布尔（任一 care 用了卡/或用了储值/或有 ticket_code）。`usedBenefit=false` 的 0 元单（纯质保/招待）照旧立即 `EffectCareOrder`；`usedBenefit=true` 的 0 元单不再立即生效，等结算页核验完再核销。
- **B3** 新增 `OrderController.WriteoffCareOrder(orderId, sessionKey, sessionType)`：先做幂等短路（查 care 上 `task_flow_code` 是否已生成，生成过说明已核销过，直接返回）；再检查 `order.wechat_unverified`（这个字段名有点反直觉——**值为 1 代表"已通过微信核验为本人"**，不是"未核验"）必须为真，否则拒绝；如果订单标了 `pay_with_deposit`，内联一段镜像 `PayWithDeposit` 的储值消费逻辑（`ConsumeDeposit` 写负额 + 插入储值支付记录），显式控制 `dealed`/`pay_flow_status`/`paying_amount` 字段；最后调用 B1 强化过的 `EffectCareOrder` 完成核销 + 生效。
- **B4** `PaymentIdentityController._resolveStatus`（这个方法本来是通用的身份核验决策树，5 态：`error`/`phone_required`/`direct`/`direct_to_scanner`/`choose_identity`）加了第 6 态 `care_member_required`：当 `order.type=='养护' && payerType=='wechat' && order.member_id!=null && result.scannerMemberId!=order.member_id` 时命中，表示"这是养护单，走微信支付，但扫码人不是订单匹配到的会员本人"，此时不允许支付。判定精确限定在 `order.type=='养护'`，不影响租赁/零售/雪票走这条决策树的既有行为。

### 1.3 前端三块（F1-F3）

- **F1** `utils/data.js` 补一个 `writeoffCareOrderPromise(orderId, sessionKey, sessionType)`，直连 B3 接口。
- **F2** `components/order-payment/index.{js,wxml,wxss}` 这个结算页支付组件加了养护专用分支：`loadOrder` 后派生 `isCare`/`careWriteoff`（是否需要核销）；`onMethodTap` 里，如果是养护单选支付宝，先弹微信核验二维码（阻断支付宝流程直到核验通过）；新增 `onCareWriteoffVerify`/`_doWriteoff`/`_openWechatVerify`/`_startVerifyPolling`/`_stopVerifyPolling`/`onWechatVerifyCancel` 一整套核验二维码 + 2 秒轮询的方法，模式完全照抄 `rent_order_detail.js` 里已经跑通的储值付租金核验流程（`GetWechatVerifyStatus` 轮询 + 弹层展示核验码）。
- **F3** `pages/order/payment_entry.wxml/wxss`：这是顾客扫码支付的落地页，加了一段——如果 `identity.status === 'care_member_required'`，隐藏支付按钮并显示一段提示文案，防止非本人在这个页面上强行扫码支付。

## 2. 安全检查默认值被无关操作冲掉（bug 修复）

- 用户描述："养护订单详情页，安全检查有默认值，但是此时如果去补全个照片并保存，默认值就消失了。这是不对的，安全检查的值，如果填写或者修改过，无论做什么操作，值都应该保留；如果没有填写或者修改过，在点击『确认安全』之前，始终应该显示默认值。"
- 根因：`care_order_detail.js` 里 `_renderCare(raw)` 每次都是 `const care = {...raw}`，纯粹从服务端原始数据重建。任何触发 `loadOrder()` 的操作（哪怕只是保存了一张不相关的照片）都会重新拉单、重新 `_renderCare`，服务端此时安全检查字段还是空的（用户还没点"确认安全"提交），于是刚才手填/带入的默认值就被这次重建覆盖掉了。
- 修复：加一个页面级的 `this._uiState.safeCheck = {}` 草稿 map（在 `onLoad` 里初始化）。`_renderCare` 合并字段时的优先级改成：服务端已经存了值 → 用服务端的；服务端没存 → 用草稿 map 里记的值（如果有）。`onSafeFieldBlur`/`onSafeMemoBlur`（用户手动改字段时触发）和 `_fetchSafeCheckHistory`（拉历史默认值带入时触发）都要同步写入这个草稿 map，不能只 `setData`。这样无论中间发生多少次 `loadOrder()`，只要没点"确认安全"提交，草稿值就一直在。

## 3. 装备「取消养护」功能——三轮迭代

这是本场耗时最长、反复最多的一块，值得完整记录迭代过程，因为每一轮的教训对以后设计类似功能有参考价值。

### 3.1 原始需求

用户："养护订单详情页，针对于每个装备，增加取消功能。需要增加一个取消按钮，点击按钮后，和发板流程一样，但是再提供一个填写备注的文本框。用户验证后，直接更新care_task里的发板任务，然后care表中我新增了两个字段is_cancel设置为1，同时更新cancel_reason"

后端很直接：`Care.cs` 加 `is_cancel`(bool) + `cancel_reason`(string?) 两个字段；`CareController.SetTaskStatus`（这是 4 种核验方式——扫码取板/验证码/拍照凭证/店长确认——共同收敛的完成点）和 `VeriCareFinishCode`（验证码方式的内部实现，会转调 `SetTaskStatus`）都加 `isCancel`/`cancelReason` 两个可选参数，当发板任务被标记完成且 `isCancel=true` 时，跳过原来"养护完成赠送优惠券16"的逻辑，改为把 `care.is_cancel` 置 1、写入 `cancel_reason`、留一条 `CoreDataModLog`。

### 3.2 第一轮：终态开关

第一版把"取消"做成"发板"面板内一个可以手动切换的开关，只在"所有任务都完成、或者只剩发板没完成"这个终态阶段才显示。做完之后用户问："刚才说的取消按钮在哪里？加上了吗？"——我说明了位置后，用户纠正："已开始，也可以取消。只要不是所有任务都完成或者只剩发板没有完成，都可以取消。"

也就是说取消的可用范围应该反过来：不是"只在终态可用"，而是"除了终态之外的所有中间阶段都可用"（终态阶段应该走正常发板，不应该再给取消选项——毕竟都快完成了）。

### 3.3 第二轮：自动派生 + 内联展开

第二版把开关改成自动派生：`care._canCancel` 由任务状态计算得出——存在发板任务、发板未完成、且不是"除发板外全部任务都已完成"（即还有除发板外的任务处于未完成/进行中状态）——满足则可取消。可取消时把这套四方式核验面板（改成取消语义）内联展开显示在页面上。

用户带了一张截图反馈："这个不应该直接显示在界面上，毕竟取消是少数情况。应该做成一个按钮，点击按钮后，弹出来modal，再显示这些内容。"

### 3.4 第三轮（终态）：按钮 + modal

最终形态：
- 任务行内一个不起眼的小按钮"取消养护"，只在 `care._canCancel` 为真时出现。
- 点击后弹出 `van-popup`（bottom 位置，圆角，最大高度 85%）modal，里面是：取消原因文本框（必填）+ 复用的四方式核验面板（全部按钮文案改成取消语义——比如"店长确认发板"变成"店长确认取消"）。
- 原本"发板"面板恢复成最原始最简单的样子（无任何取消感知，纯粹正常发板），只在终态阶段（`!care._canCancel` 时）显示——这样两个入口在视觉上完全互斥，不会同时出现。
- Modal 复用同一份 `cares` 数据的技巧：`<van-popup>` 内部再套一层 `wx:for="{{cares}}"`，用 `wx:if="{{cidx === cancelModal.cidx}}"` 过滤只渲染目标那一件装备。这样 modal 里的所有按钮可以直接复用外层已经写好的 `data-cidx="{{cidx}}"` + 事件处理函数（`onVeriCodeConfirm`/`onMasterFinish` 等），不需要另写一套逻辑，只是渲染位置换到了 modal 里。

### 3.5 一处需要仔细处理的时序细节

`_scanCancelParams`（记录当前扫码会话是不是处于"取消模式"、取消原因是什么）必须在 `_closeScan()` 之前读取，因为 `_closeScan()` 会把它清空。这体现在两处：

- `_openScan(cidx)`：先算出 `cp = _resolveCancelParams(care)`，再调 `_closeScan()` 关掉旧会话，然后才把 `this._scanCancelParams = cp` 设进去，最后才开新会话。
- `_onScanMessage(res)`（扫码结果回调）：先 `const cp = this._scanCancelParams` 取出来，再走后续逻辑（其中会调用 `_closeScan()`）。

## 4. 未解决：取消 modal 里"扫码取板"校验 bug

end-work 触发之前，用户带截图报告了这个问题：取消养护弹窗里，"取消原因"文本框已经填了"赶火车"，点"扫码取板"按钮，还是弹出"请填写取消原因"的 toast；而且点了"扫码取板"之后二维码不会自动生成，还得再点一次"生成二维码"按钮。

### 4.1 第一轮排查与修复尝试

分析代码后定位到两个可疑点：

1. **失焦时序竞争**：`onCancelReasonBlur` 原来只绑了 `bindblur`。理论上，用户从文本框移开手指点击旁边的按钮，`blur` 事件应该先于按钮的 `catchtap` 触发，但在部分设备/场景下这个顺序可能不保证。加了 `bindinput`，让每次按键都实时同步 `care._cancelReason`，理论上能消除这个竞争。
2. **重试逻辑缺失**：`onVeriTypeTap` 原来的逻辑是 `if (!care || care._veriType === type) return;`——如果当前类型已经是"扫码取板"，再点一次直接短路返回，不会重新调用 `_openScan`。问题在于：第一次点击"扫码取板"时，`_veriType` 已经被 setData 成"扫码取板"（在校验失败之前就设置了），但如果校验失败（原因未填），`_openScan` 内部会因为 `_resolveCancelParams` 返回 `{ok:false}` 而提前 return，不会真正去请求二维码。这样 UI 上"扫码取板"标签已经显示为选中态，但底层二维码会话从未成功建立。用户后来填完原因再点"扫码取板"，由于 `_veriType` 已经等于"扫码取板"，直接被短路 return，根本不会重试。改成：已选中"扫码取板"时再点一次，改为调用 `_openScan(cidx)` 重试，而不是直接返回。

两处改完，用户重新编译测试，反馈："界面操作没有任何变化呀，和刚才还一样"——并追问了一句关键问题："即便是填写了取消原因，为什么点击『扫码取板』，还是提示『请填写取消原因』？另外，点扫码取板，直接显示二维码即可，不需要再次点击生成二维码了。"

我怀疑用户可能是重复发了同一张旧截图（截图内容与上一次一模一样，连 toast 位置都完全一致），请用户确认是否重新编译测试过。用户明确回复"当然重新编译了！"——排除了缓存/未编译的可能。

### 4.2 决定性线索：生成二维码按钮没消失

进一步追问，用户提供了一个关键的观察："至少那个生成二维码的按钮，没有消失。"

这句话很有价值：wxml 里"生成二维码"按钮的显示条件是 `scanQr.careId !== care.id || scanQr.status === 'broken'`。如果这个按钮还在（且显示的是"生成二维码"而不是"重新生成二维码"），说明 `_openScan` 里那句 `this.setData({ scanQr: { careId: care.id, url: '', status: 'loading' } })` 从未被执行到——也就是说，**即便加了两轮修复，`_resolveCancelParams` 校验依然在失败**，`_openScan` 依然在校验这一步就提前返回了。

这排除了"重试逻辑缺失"是唯一根因的可能（因为重试逻辑已经修好，理论上第二次点击应该能重新进入 `_openScan`），说明真正的问题出在 `care._cancelReason`（或者 `care._cancelMode`）读到的值本身就不对，而不是"点没点对按钮"的问题。

### 4.3 临时诊断代码

为了避免继续凭空猜测浪费用户的测试轮次，在 `_resolveCancelParams` 里加了一段临时诊断：把失败时的 toast 从固定文案"请填写取消原因"改成把实际读到的运行时值打印出来——`未填[mode=xxx,val="xxx"]`，格式类似 `未填[mode=true,val="赶火车"]`。这样用户不需要打开开发者工具控制台，直接截个图或者念出 toast 上的文字，就能把 `care._cancelMode` 和 `care._cancelReason` 的实际值回传回来，一轮就能判断出到底是哪个字段读错了、还是 cidx 定位错了别的 care。

这段诊断代码标注了 `// TEMP DEBUG` 注释，等定位到根因之后需要删除。

end-work 触发时，用户还没有来得及重新编译测试并提供诊断输出，这个 bug 排查在本场会话内没有闭环。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/CareController.cs` | `EffectCareOrder` 并入卡券核销（PunchCardUsed + 扣次数）；`SetTaskStatus`/`VeriCareFinishCode` 加 `isCancel`/`cancelReason` 参数，取消时跳过发板赠券改置位+留痕 |
| `SnowmeetApi/Controllers/OrderController.cs` | `PlaceCareOrder` 按 `usedBenefit` 分叉 0 元单是否立即生效；新增 `WriteoffCareOrder`（幂等+核验门槛+储值消费+EffectCareOrder） |
| `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs` | `_resolveStatus` 新增 `care_member_required` 状态（养护单微信支付非本人拦截） |
| `SnowmeetApi/Models/Care/Care.cs` | 新增 `is_cancel`(bool) + `cancel_reason`(string?) 两字段 |
| `snowmeet_wechat_mini/utils/data.js` | 新增 `writeoffCareOrderPromise`；`updateCareTaskStatusPromise`/`veriCareFinishCodePromise` 扩展 `isCancel`/`cancelReason` 参数 |
| `snowmeet_wechat_mini/components/order-payment/{index.js,wxml,wxss}` | 养护核销/储值/微信核验二维码轮询/支付宝前置核验分支 |
| `snowmeet_wechat_mini/pages/order/payment_entry.{wxml,wxss}` | `care_member_required` 状态下隐藏支付按钮 + 提示 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_detail/{care_order_detail.js,wxml,wxss}` | 安全检查默认值持久化草稿 map；取消养护功能三轮迭代终态（按钮+modal）；`_resolveCancelParams` 临时诊断代码（未删） |

## 学到的小知识

1. **`order.wechat_unverified` 命名反直觉**：字段名读起来像"未核验"，但实际语义是"1 = 已通过微信核验为本人"。这个命名在早期就定了（微信支付场景下 `wechat_unverified` 起初的字面意思可能是"是否需要走微信核验"这个开关，后来演变成了核验结果标记），改代码前一定要确认清楚当前语义再用，不要按字面意思猜。
2. **`EffectCareOrder` 是养护订单唯一的生效收敛点**：五条不同路径（0元单直接生效、核销接口、微信/支付宝支付成功回调、手工收款、储值支付）都汇聚在这一个方法里。这意味着往里加逻辑（比如这次的卡券核销）一次改动就能让所有路径同时受益，但也意味着改动前必须想清楚"这段逻辑是不是应该对所有触发路径都生效"，避免只想着某一条路径就直接往里塞。
3. **微信小程序 WXML 里 `wx:for` + `wx:if` 过滤是复用同一份数据在不同渲染位置的一个实用技巧**：不需要为 modal 单独维护一份数据或者写一套新的事件处理逻辑，只要用同样的 `wx:for-item`/`wx:for-index` 变量名，配合 `wx:if` 精确过滤到目标项，外层已经写好的 `data-cidx` + handler 可以在任意渲染位置直接复用。
4. **"已选中态点击直接短路返回"这种交互优化容易掩盖内部状态未就绪的情况**：如果"选中"这个 UI 状态和"选中后需要执行的副作用是否成功"这两件事被合并成一个判断条件，一旦副作用因为某种原因失败了（比如校验没过），后续重试就可能被这个"已经选中了所以直接返回"的短路逻辑挡住，导致用户怎么点都没反应。
5. **诊断复杂问题时，把实际运行时的值直接打印在用户能看到的地方（比如 toast），比让用户描述"我做了什么、看到了什么"更可靠**：本场对话里连续两轮基于纯代码审查的猜测性修复都没能解决问题，直到决定直接展示运行时状态才有了明确的排查方向——这提示以后遇到"猜测性修复两轮不奏效"时应该更早切到"展示实际状态"这个策略，而不是继续凭代码审查猜第三轮、第四轮。
