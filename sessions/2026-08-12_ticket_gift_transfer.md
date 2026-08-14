# 2026-08-12 优惠券转赠（转赠好友）功能：全栈实现 + 关注核验反复调试 + 已分享历史

从零实现"优惠券（ticket）可以转赠给微信好友"这个功能，硬编码先支持模板 12（免费打蜡券）、16（老顾客优惠券）。改动横跨三个仓库：`SnowmeetApi`（后端）、`snowmeet_wechat_mini`（小程序）、`SnowmeetOfficialAccount`（公众号事件回调服务，本场会话中才第一次被拉进本地工作区）。三个仓本地均未提交/未部署，由用户按自己的节奏发布。

## 1. 前置修复：我的雪票查询简化

`GetMySkipass` 原来 `member_id == member.id || wechat_mini_openid == ...` 双条件查询，改成只按 `member_id` 单键查询。业务不变量：会员注销前必须先把资产合并到另一账户才允许注销，所以任何时候按 `member_id` 单键查都是安全的，不存在"查不到孤儿订单"的情况。

## 2. 转赠功能主体（客户自助转赠 + 微信原生分享卡片）

### 2.1 规则确认

用户经问答确认：客户自助发起转赠（不是店员操作）；复用微信小程序原生 `open-type="share"` 分享卡片机制选好友，不做站内好友列表；先硬编码模板 12、16 允许转赠，其余模板不允许。

### 2.2 后端（`SnowmeetApi/Controllers/TicketController.cs`）

- `TransferableTemplateIds = {12, 16}` 白名单常量
- `SetTicketToShare(code, sessionKey)`：按 `member_id` 校验归属（不是 `open_id`——很多券的 `open_id` 是空的，`CreateTicket`/`GenerateTickets` 从来没填过），白名单校验，`used`/`valid` 校验，设置 `shared=1` + `shared_time`
- `AcceptTicket(code, memo, sessionKey)`：解析接受人、自赠自己拦截、关注核验（见第 3 节）、把 `member_id`/`open_id` 改成接受人、`shared` 重置为 0（否则同一张券理论上能被接受两次）、写 `TicketLog`
- `CancelShare(code, sessionKey)`：撤回分享，仅限 `shared==1` 且本人持有

### 2.3 前端三个页面

- `ticket_list`（我的优惠券列表）：卡片下方按状态显示"转赠好友"（`open-type="share"`）或"撤回分享"按钮
- `ticket_detail`（券详情页）：同样的分享/撤回逻辑
- `ticket_share`（好友点开分享卡片后落地页，新页面）：展示券信息 + 接受流程

### 2.4 顺带修的两个既有 bug

- `ticket_share.js` 原来直接读 `wx.request` 的 `res.data` 当 Ticket 对象，但接口实际返回 `ApiResult<Ticket>` 包装——切到 `data.js` 统一 wrapper 修复
- `ticket_detail.js` 的 `onShareAppMessage` 原来 `wx.request` 发出去就立刻同步 return 分享配置，success 回调其实是死代码——改成正确的 Promise 链

## 3. 强制关注公众号才能接受：三轮迭代

用户要求："转赠微信好友，好友接受，需要强制关注微信公众号后，才能接受。"这条需求在本场会话内经历了三轮实质性迭代。

### 3.1 第一轮：基于 `oa_receive` 事件日志推断（初版）

生产库里理论上该记录"是否关注"状态的 `OfficialAccoutUser`/`UnionId` 表实际映射到不存在的表（死代码）。唯一可用信号是 `oa_receive`——微信公众号服务器事件回调落库表（`MiniAppHelperController.PushMessage` 写入）。生成一个带 scene 的临时二维码（`MediaHelper.ShowImageFromOfficialAccount` → 外部 `wxoa.snowmeet.top` 代理），扫码触发 `subscribe`（新关注）或 `SCAN`（已关注用户扫码）事件，轮询 `oa_receive` 里有没有匹配记录。

**真实事故（2026-08-12）**：场景值最初只绑定券的静态 `code`（`ticket_gift_{code}`）。同一张券换收件人再转赠时，会复用上一个收件人（甚至完全无关的人）历史上留下的扫码/关注记录，导致新收件人明明没扫码却直接判定"已关注"。用户实测复现：分享给 A，A 没关注却显示已关注。

**修复**：`Ticket.transfer_scene`（`[NotMapped]` 计算属性）= `code + "_" + shared_time.Ticks`，绑定"这一次分享"而不是"这张券"。每次重新分享 `shared_time` 都会刷新，场景值随之变化，历史记录不会被复用。

### 3.2 第二轮：加"当前是否关注"的直接判定 + 服务端触发

用户反馈同一个人这次关注过、下次转赠新券又要重新扫码——因为场景值绑定单次分享，天然不认"已经关注过"这件事。加 `IsCurrentlyFollowingOA`：一开始的实现是查 `oa_receive` 里该用户 openid 最新一条 `subscribe`/`SCAN`/`unsubscribe` 事件，若最新一条不是取关就认为在关注。

同一时段用户反馈"扫码关注后没有自动接受，还要退回小程序点接受"，且明确要求这个逻辑应该在**服务端**实现（收到公众号关注事件时直接完成），不该在客户端轮询触发。于是：

- `SnowmeetOfficialAccount` 的 `DealEventKeyAction` 新增 `ticket_gift` 场景分支 → `AcceptGiftedTicket`：解析出券码和扫码人 openid，直接调 `SnowmeetApi` 新增的 `AcceptTicketByOaFollow`（用 `oaOpenId` 而非 `sessionKey` 定位接受人，因为触发点是公众号服务器回调、没有小程序会话）
- `AcceptTicket` 拆成 `AcceptTicketCore`（共享逻辑）+ 两个入口（session 版给小程序手动点按钮用，oaOpenId 版给公众号服务器自动触发用）
- 新接口没加额外密钥鉴权——靠 `HasFollowedForTransfer` 内部校验兜底：没有真实的关注事件命中这张券的场景值，一样会被拒绝，伪造不出关注记录
- 小程序端 `ticket_share.js` 删掉 `_autoAccept`，轮询逻辑改成盯"券状态有没有变化"（`shared` 是否变成 0）而不是自己调接受接口，并用 `member_id` 有没有变化区分"被自动接受"还是"对方撤回分享"

### 3.3 第三轮：发现 `member.following_wechat` 是更好的真源

处理一次 `SnowmeetOfficialAccount` 代码本地手动 merge 冲突（用户手动解决后要求复查）时，合并进来的完整版代码里发现了此前从未见过的方法 `SetFollowingStatus`：每次收到 `subscribe`/`SCAN`/`unsubscribe` 事件都会同步维护 `member.following_wechat`（`0`/`1`）这个字段——**这是一个由公众号服务器实时维护的、直接挂在会员身上的关注状态字段**，比反查 `oa_receive` 历史事件推断更直接、更可靠。用户确认后，`IsCurrentlyFollowingOA` 简化为直接读 `member.following_wechat == 1`（同步方法，不再需要查库）。

**这次 merge 也暴露一个真实 bug**：合并冲突把新加的 `case "ticket":` 分发那几行漏掉了，`AcceptGiftedTicket` 方法还在文件里但成了永远不会被调用的死代码——已修复补回。

### 3.4 UI 措辞打磨

`ticket_share.js`/`.wxml` 反复调整过几轮：

- 未关注只显示二维码（不显示接受按钮），关注后台端自动接受；已关注只显示接受按钮（不显示二维码）
- "正在检测关注状态…"文案被用户指出容易让人以为系统自己也不确定——改成陈述明确事实 + 下一步提示："还未关注，请扫码关注后自动接收"
- 样式对齐新版系统（复用 `ticket_card.wxss` 里的卡片/按钮 CSS 变量）

### 3.5 接受成功后的公众号确认消息

需求：好友接受转赠优惠券后，公众号给他发一条"您已经接受了 XXX 优惠券，点击查看"，点击直接跳"我的优惠券"。

- `SnowmeetOfficialAccount` 新增 `SendTextMessageByOpenId(openId, content)`：直接按公众号 openid 发客服消息，不走原有 `SendTextMessage` 的 `unionId → user` 表反查（那张 `user` 表是老架构死代码）
- `SnowmeetApi` 的 `AcceptTicketCore` 成功后调用 `NotifyAcceptedByOA`：拼一条内嵌 `<a data-miniprogram-appid="" data-miniprogram-path="/pages/mine/ticket/ticket_list">点击查看</a>` 的消息（这个 HTML 内嵌小程序跳转写法是 `SnowmeetOfficialAccount` 里原本就在用的标准写法），发送失败包 try/catch 不影响已成功的接受动作

## 4. 旧版接待页面退役

用户提出疑问：`pages/admin/recept/` 下 `recept_new`、`rent_recepting_list` 是不是只用于老版系统了？**排查结果推翻了用户自己的假设**——这两个老页面其实是当时首页几个入口指向的**活跃默认路径**，"新版"接待流程反而是尚未真正接入的分支。

用户拍板：首页入口全部指向新版（`pages/admin/reception/`），旧版两个页面删除。追问"还有哪些 components 也一并没用了"时，发现 `recept_member_info.js` 的 `gotoFlow` 和旧 `recept_entry.js` 内建的 QR 扫码 + WebSocket 身份验证流程都依赖被删的 `recept_new`——用 `AskUserQuestion` 征求意见后，用户明确"不需要了，一并退役"，才放心整体删除。

最终删除 60 个文件：5 个旧页面 × 4 文件 + 10 个孤儿 component × 4 文件，同步清理 `app.json`、`admin.wxml`、`admin.js`、`project.config.json` 里的引用。保留了 `components/payment/payment`（确认仍被 `retail_order_detail` 使用）。

## 5. "我的优惠券"页面重做：编码展示 + 三 tab + 已分享历史

### 5.1 编码展示 + 三 tab

- 每张卡片加一行编码展示，3 位一节横线分隔（如 `775-025-175`），纯前端格式化，不影响传给后端的原始 `code`
- Tab 从"未使用/已使用"两个改成"未使用/已使用/已分享"三个。分享中的券从"未使用"tab 移出，单独归到"已分享"

### 5.2 "已分享"历史记录：对方接受后依然要看得见

用户指出：对方接受转赠后 `ticket.member_id` 已经改成对方的，但发起人的"已分享"列表里也应该继续显示这张券——不能转赠成功就凭空消失。

新增 `GetMySharedTickets` 接口，合并两部分：① 我当前还持有、正在分享中等对方接受的券（`member_id==me && shared==1`）；② 我曾经转赠出去、已经被接受的券（从 `ticket_log` 里找"我作为 sender 且确实有 accepter"的成功记录反查券码，此时票据本身 `member_id` 已经不是我了）。

**用户随即指出一个更细的边界情况**：如果我分享出去、对方接受了，对方又转赠回给我、我又接受了——这张券理论上不该再挂在我的"已分享"历史里，因为它现在就是我手上一张普通未使用券。第一版实现（"我有没有转赠成功过"）会误判。修复为"这张券最新一条转赠成功记录的 sender 是不是我"——同一张券反复转手，只认最后一次转赠动作的方向。实现上：先找出我作为 sender 的候选券码，再把这些券码的全部转赠成功记录拉出来按 code 分组，内存里取每组最新一条判断 sender，避免 EF Core 对 `GroupBy().Select(First())` 这种"取每组最新一条"模式的 SQL 翻译不稳定。

### 5.3 已分享列表的操作权限收紧

用户要求：已分享列表里只有"分享中"状态的券能撤回分享，"对方已接受"状态不允许有任何操作；点进详情页也是一样。

排查发现 list 页和 detail 页原来是两份互相独立的状态判断代码，detail 页完全不知道"这张券是不是通过已分享 tab 点进来、已经不是我的了"——如果直接从已分享列表点进一张"对方已接受"的券，detail 页会显示"转赠好友"按钮和核销二维码（点了会失败，也不该被看到）。

抽出共用模块 `ticket_helper.js`（`annotateTicket(ticket, tab)` + `formatTicketCode`），list 页导航到 detail 页时把当前 tab 带上（`ticket_detail?code=xxx&tab=shared`），detail 页据此判断权限，与 list 页保持一致。同时加了 `ticket.actionable` 字段，核销二维码卡片跟着一起收起。

后端 `GetMySharedTickets` 的合并结果也加了一层按 `code` 分组去重兜底（防止极端情况下同一张券被两个数据源都命中）。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/SkiPass/SkiPassController.cs` | `GetMySkipass` 改按 `member_id` 单键查询 |
| `SnowmeetApi/Models/Ticket/Ticket.cs` | 新增 `transfer_scene` 计算属性 |
| `SnowmeetApi/Controllers/TicketController.cs` | 转赠全套逻辑：`SetTicketToShare`/`AcceptTicket`/`AcceptTicketCore`/`AcceptTicketByOaFollow`/`CancelShare`/`CheckTransferFollow`/`HasFollowedForTransfer`/`IsCurrentlyFollowingOA`/`NotifyAcceptedByOA`/`GetMySharedTickets` |
| `SnowmeetOfficialAccount/Controllers/OfficialAccountApi.cs` | 新增 `SendTextMessageByOpenId`、`AcceptGiftedTicket` + `ticket_gift` 场景分发 |
| `snowmeet_wechat_mini/pages/mine/ticket/ticket_list.{js,wxml,wxss}` | 三 tab、编码展示、转赠成功跳转、已分享列表接入 |
| `snowmeet_wechat_mini/pages/mine/ticket/ticket_detail.{js,wxml}` | 权限判断改用共用 `ticket_helper.js`，接收 `tab` 参数 |
| `snowmeet_wechat_mini/pages/mine/ticket/ticket_share.{js,wxml,wxss}` | 关注核验轮询 UI、状态轮询改盯券状态而非自己发起接受 |
| `snowmeet_wechat_mini/pages/mine/ticket/ticket_helper.js` | 新增，list/detail 共用的状态与权限判断 |
| `snowmeet_wechat_mini/pages/mine/ticket/ticket_card.wxss` | 新版卡片样式 token，新增 `.status-accepted`/`.ticket-code` |
| `snowmeet_wechat_mini/utils/data.js` | 新增 `setTicketToSharePromise`/`acceptTicketPromise`/`checkTransferFollowPromise`/`cancelShareTicketPromise`/`getMySharedTicketsPromise` |
| `snowmeet_wechat_mini/pages/admin/admin.{js,wxml}` + `app.json` + `project.config.json` | 旧版接待入口改指新版；删除旧页面/组件引用 |
| （删除）`pages/admin/recept/{recept_entry,recept_new,rent_recepting_list,recept_auth_list,recept_member_info}.*` | 60 个文件，含 10 个孤儿 component |

## 学到的小知识

1. **微信"扫码关注"场景值必须绑定"这一次交互"，不能绑定实体本身的静态标识**：否则同一实体反复使用会复用无关的历史事件，这是真实发生过的线上事故，不是理论风险。
2. **服务端维护的状态字段优于从事件日志反查**：`member.following_wechat` 由 `SnowmeetOfficialAccount` 在每次关注/取关事件时同步更新，直接读它比每次查 `oa_receive` 最新事件推断更快、更可靠、更少踩坑——找到这类"真源字段"比自己发明推断逻辑更值得优先。
3. **多个入口需要一致的权限判断时，判断逻辑要抽成共用模块**，不能让 list 页和 detail 页各写一份——本场就是这样漏了 detail 页的权限收紧。
4. **"某天分享成功过"和"当前状态就是分享出去的"是两回事**：涉及多方转手的资产（这里是可转赠的优惠券），历史记录查询要按"最新一次动作的方向"判断当前归属，不能只看"有没有发生过"。
5. **本地手动解决 git 冲突后要主动复查**：合并动作本身可能悄悄丢掉一段新代码（这次是丢了一个 `switch case`，方法体还在但成了死代码），`dotnet build` 能验证语法正确性但验证不了"逻辑分支有没有被漏掉分发入口"，需要针对新增符号单独 grep 确认调用点还在。
6. **WeChat 客服消息/被动回复消息都支持 `<a data-miniprogram-appid="" data-miniprogram-path="">文案</a>` 内嵌小程序跳转链接**，这是本仓库里公众号消息跳小程序的标准写法（多处已有先例）。
