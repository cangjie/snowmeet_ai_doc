# 优惠券转赠：订阅消息通知 + 回赠同款券 + 领取上限

日期：2026-08-14
状态：设计已确认，待实施

## 背景

2026-08-12 上线了优惠券转赠给微信好友（硬编码支持模板 12 免费打蜡券 / 16 老顾客优惠券）。目前对方领取成功后，只有**接受人**会收到一条公众号客服消息（`NotifyAcceptedByOA`），**分享人什么都收不到**。

本次要做三件事：

1. 分享人转赠时提示订阅小程序订阅消息，对方领取后推送通知
2. 对方领取成功后，自动回赠分享人一张同款券
3. 给「领取分享来的券」加一条持有上限，防止个人囤同款券

### 为什么分享人不能靠公众号通知

公众号客服消息有额度窗口（[官方文档](https://developers.weixin.qq.com/doc/service/guide/product/kf/intro.html)）：只有「用户主动发消息」是 5 条 / 48 小时，「关注服务号」「扫描二维码」都只有 3 条 / **1 分钟**。分享人在对方领取的那一刻，早就不在任何额度窗口里，公众号这条路走不通。所以用小程序**一次性订阅消息**。

## 关键决策

| 决策点 | 结论 | 说明 |
|---|---|---|
| 回赠是真发券还是文案 | **真发券** | 对方领取成功即给分享人发一张同 `template_id` 的新券 |
| 回赠是否设上限 | **不设** | 业务明确选择"鼓励无限传播"。新券同样可转赠，等于每转赠一次净增一张券——已知且接受 |
| 新券有效期 | **本雪季末** | 当前月 ≥ 5 月 → 次年 4-30 23:59:59；否则 → 当年 4-30 23:59:59。与财年 5-01~4-30 口径一致 |
| 订阅消息 `time2` 显示哪张券 | **新回赠那张** | 用户接下来能用的是新券 |
| 订阅授权交互 | **两步式：先订阅再分享** | `wx.requestSubscribeMessage` 必须在 tap 回调里调用，而 `open-type="share"` 点下去立刻拉起转发面板，同一次点击两个系统弹窗会打架 |
| 备注文案 | **「对方已领取，回赠您一张同款券」** | 14 字，`thing` 类型上限 20 字 |
| 领取上限阈值 | **已有 3 张即拒绝** | 领取后名下最多持有 3 张 |
| 上限计数口径 | **只数真能用的** | `valid=1 && used!=1 && 未过期`。分享中的券仍在自己名下，计入 |

### 为什么回赠不受领取上限约束

领取上限只管「领取分享来的券」这个动作。回赠是系统奖励，不走该门槛，所以分享人名下可能超过 3 张。**这是有意为之**，不是漏判——防囤的对象是"到处领别人的券"，不是"自己转赠攒下的奖励"。后续维护不要把它当 bug 改掉。

## 现状与可复用的东西

- **小程序 access_token 已有**：`MiniAppHelperController.GetAccessToken()` 用的就是小程序 appid `wxd1310896f2aa68bb`（文件名 `access_token.official_account` 是历史误命名），带 1 小时文件缓存
- **项目里没有任何小程序订阅消息基础设施**。现有 `ServiceMessageController` 走的是**公众号**模板消息 `cgi-bin/message/template/send`，token 来自 `weixin.snowmeet.top/get_token.aspx`（公众号的），两者不能混用
- **`AcceptTicketCore` 是唯一的接受出口**，小程序点接受（`AcceptTicket`）和扫码关注自动接受（`AcceptTicketByOaFollow`）都汇聚于此，所以领取上限和回赠都只需在这里加一次
- **`onShareAppMessage` 靠 `res.target.dataset.code` 取券码**，两步式弹层里的分享按钮照样带 `data-key` 即可，这段逻辑不动

## 模板

- 模板 ID：`TsWgivHWG5TT8OVI5hN7n56yCWJ5K8THFBtmmACfek4`（模版编号 38451）
- 标题：优惠券领取成功提醒
- 字段：

| 字段 | 含义 | 类型 | 填什么 |
|---|---|---|---|
| `thing1` | 优惠券名称 | thing（≤20 字） | 新券 `ticket.name`，超长截断到 20 |
| `time2` | 有效期 | time | `2026年8月14日~2027年4月30日`——**只到日、不带时分**，起点取新券 `start_date`、终点取 `expire_date`。⚠️ 连接符必须是**半角 `~` (U+007E)**，全角 `～` (U+FF5E) 会被判 47003，见下 |
| `thing3` | 备注 | thing（≤20 字） | `对方已领取，回赠您一张同款券` |
| `page` | 落地页 | — | `pages/mine/ticket/ticket_list` |

`thing1` 已经是券名，所以 `thing3` 不重复券名。

## 架构

| 新增/改动 | 职责 |
|---|---|
| `SnowmeetApi/Helpers/SubscribeMessageHelper.cs`（新建） | 单一职责：给某小程序 openid 发某模板的订阅消息。入参 `(openId, templateId, page, Dictionary<string,string> data)`，复用 `MiniAppHelperController.GetAccessToken()`，POST `cgi-bin/message/subscribe/send`，返回微信响应体 |
| `TicketController.RewardSenderForAcceptedTransfer`（新增 `[NonAction]`） | 回赠发券 + 发订阅消息，整体 try/catch |
| `TicketController.SeasonEndDate`（新增 `[NonAction]` 或静态工具） | 计算本雪季末 |
| `TicketController.CountUsableTicketsOfTemplate`（新增 `[NonAction]`） | 数某会员名下某模板可用券张数，供领取上限用 |
| `TicketController.AcceptTicketCore`（改） | 插入领取上限校验；末尾加一行调用 `RewardSenderForAcceptedTransfer` |
| `TicketController.GenerateTicketByAction`（改） | 加可选参数 `DateTime? expireDate = null`，不传维持原样抄模板（**零回归**）；并补写 `start_date` |
| `ticket_list` / `ticket_detail`（改） | 「转赠好友」改两步式 + 共用确认弹层 |
| `ticket_share`（可能改） | 展示领取被拒的新文案 |

## 数据流

```
点「转赠好友」（普通 button，bindtap）
  → wx.requestSubscribeMessage(['TsWgi…'])          ← 必须在 tap 回调里
  → 同意/拒绝都继续，打开「确认转赠」弹层
  → 点弹层里的「选择好友」(open-type=share, data-code)
  → onShareAppMessage → SetTicketToShare → 微信转发面板   ← 这段不动
  → 好友打开 ticket_share → 关注/已关注 → AcceptTicketCore
       ├ ① 券/状态校验                    （现有）
       ├ ② 不能转赠给自己                  （现有）
       ├ ③ 领取上限校验                    ← 新增
       ├ ④ HasFollowedForTransfer         （现有）
       ├ ⑤ 券归属转给接受人 + 落 ticket_log （现有）
       ├ ⑥ NotifyAcceptedByOA → 通知接受人 （现有，公众号客服消息）
       └ ⑦ RewardSenderForAcceptedTransfer ← 新增
              ├ 回赠发券（同模板，归分享人，有效期到雪季末）
              └ 发订阅消息给分享人
```

领取上限（③）放在「不能转赠给自己」之后、「请先关注公众号」之前——否则用户白关注一次才被告知券太多。

## 领取上限

```
名下同模板可用券 = ticket.member_id == accepter.id
                && ticket.template_id == 待领券.template_id
                && valid == 1
                && used != 1
                && (expire_date == null || expire_date >= 当前时间)
```

`>= 3` 即拒绝，返回 `code=1`、message 形如「您名下未使用的『XX券』已有 3 张，用掉一些再来领吧」。

**店员豁免**：接受人是在职店员（`title_level >= 100`）时，跳过这道上限——店员要做测试、
也会代顾客操作，不该被卡住。按接受人的小程序 openid 走 `StaffController.GetStaffBySocialNum`
反查（内含在职时间窗判断），反查不到就按普通顾客处理、限制照常生效。
这确实是一个上限旁路（店员账号可以无限领同款券），业务有意接受。

被拒时**不改任何数据**：原券保持 `shared=1`，分享人可撤回分享或改送他人；分享人也拿不到回赠（压根没接受成功）。

`expire_date == null` 视为未过期（模板 16 老顾客优惠券的过期时间就是 NULL，库里 4694 张 12/16 券里有 1915 张 `start_date` 也为空）。

## 回赠新券

- `template_id` 同原券；`member_id` = 分享人；`open_id` = 分享人 mini openid
- `expire_date` = 本雪季末（**不抄模板**）
- `start_date` = 发放时刻
- `create_memo = "转赠被领取回赠"`，便于日后统计这批券

**为什么必须覆盖 `expire_date` 而不能抄模板**：`ticket_template` 12「免费打蜡券」的 `expire_date` 是 `2024-12-07`，已经过期快两年；16「老顾客优惠券」是 NULL，而 `GenerateTicketByAction` 对 NULL 会写成 `DateTime.MaxValue`（9999 年）。照抄两个模板都得到废值。

## 错误处理

| 情况 | 处理 |
|---|---|
| 发券失败（分享人无 mini openid、DB 异常） | 记日志、**不发消息**——不能让消息说"已回赠"但券没发出来。接受动作已成功，不回滚 |
| 发消息失败（`43101` 用户没订阅 / `47003` 参数不符模板 / token 失效） | 吞掉 + 记返回体。券已经发了，不受影响 |
| 整个 `RewardSenderForAcceptedTransfer` | 外层 try/catch，**绝不能让它把接受动作弄失败** |
| 用户拒绝订阅授权 | 券照常转赠，只是收不到通知（发送返回 43101，正常吞掉） |

**一次性订阅**：一次授权只能发一条消息，用户每转赠一张券都要重新授权。这是微信的机制，不做额外处理。

### 用户勾了「总是保持以上选择，不再询问」

订阅弹窗底部有这个勾选框。勾上再点取消，微信就把该模板的选择**永久记住**：之后每次调
`wx.requestSubscribeMessage` 都直接返回 `reject` 且**不再弹窗**（勾着点允许同理，以后自动同意也不弹）。
代码绕不过去，唯一恢复途径是用户自己去小程序设置里改。

处理方式是**检测 + 引导**，不是重试：

- `requestSubscribeMessage` 结果不是 `accept` 时，用 `wx.getSetting({withSubscriptions: true})` 查 `subscriptionsSetting`
- 判定见 `ticket_helper.isSubscribePermanentlyBlocked`：`mainSwitch === false`（订阅总开关被关）
  或 `itemSettings[模板] === 'reject'` 才算被永久拒绝
- ⚠️ `itemSettings` **只包含用户勾过「总是保持」的模板**。某模板不在里面 ≠ 被拒绝，
  只是以后每次还会正常弹窗——两种情况不能混
- 被永久拒绝时，在转赠确认弹层里显示一行提示 + 「去开启」，点击走 `wx.openSetting({withSubscriptions: true})`
  （同样需要点击手势触发）。**不阻断转赠**，只是告诉用户收不到通知

## 可观测

发送结果落**现有** `template_message` 表（`ServiceMessageController` 在用）：`from` 写小程序 appid、`template_id` 写模板 ID、`keywords` 写 data 的 JSON、`ret_message` 写微信返回体。

落库由 `SubscribeMessageHelper` **内部**完成——每一次发送都该留痕，不能指望每个调用方各记一遍。调用方只拿返回体判断成败。

**不加新表、不需要 DDL。**

## 测试

**后端**
- 雪季末计算：8 月 → 次年 4-30；1 月 → 当年 4-30；4-30 当天 → 当年；5-1 → 次年
- `thing` 超 20 字截断
- 领取上限：名下 0/1/2 张放行，3 张拒绝；已过期券不计入；已核销券不计入；分享中的券计入
- 分享人无 mini openid 时不抛异常、不发消息、接受动作仍成功

**前端**
- 两步式：点「转赠好友」弹订阅授权 → 同意/拒绝都能继续到分享面板
- 列表页和详情页两个入口行为一致

**真机端到端**
- 授权 → 分享 → 对方领取 → 分享人收到订阅消息 → 「我的优惠券」里多一张有效期到 2027-04-30 的新券
- 对方名下已有 3 张同款券时，领取被拒且文案清晰
- 拒绝订阅授权后，转赠照常完成，只是没有通知

## 连带修复：`GetMyTickets` 过期过滤写反（实施中发现，已确认一并修）

`TicketController.GetMyTickets` 对 `used == 0` 的过滤原本是：

```csharp
tickets.Where(t => t.expire_date == null || ((DateTime)t.expire_date).Date <= DateTime.Now.Date)
```

`<=` 保留的恰好是**已过期**的券。生产库实测（`valid=1` 且未核销共 11205 张）：无到期日 1892 张（显示，正确）、已过期 9125 张（显示，**错误**）、未过期且有到期日 188 张（隐藏，**错误**）。

**这会让本功能直接失效**：回赠券的到期日是未来的雪季末，正好落在被隐藏的那一类——用户收到「已回赠您一张同款券」的通知，进券包却找不到。

改为 `TicketTransferRules.IsNotExpired`（`expire_date == null || expire_date.Date >= now.Date`，当天到期的当天仍显示）。副作用是 9125 张过期废券从顾客的「未使用」列表消失——本来就不该显示。

## 实施中踩到：`sender` 必须带 MSA 加载

`AcceptTicketCore` 里原本是 `sender = _context.member.FindAsync(ticket.member_id)`。
`Member.wechatMiniOpenId` 是遍历 `memberSocialAccounts` 算出来的计算属性，而 `FindAsync`
不加载导航属性、项目也没开延迟加载 —— 这样拿到的 `sender.wechatMiniOpenId` **恒为空**。

原来只用它写 `ticket_log`，有 `?? ticket.open_id` 兜底所以一直没暴露（2026-08-15 实测：
券 193596120 的接受日志里 `sender_open_id` 落的就是兜底值，跟该会员真实 openid 对不上）。
但回赠要靠这个 openid 发券和发订阅消息，取不到就会静默跳过、功能等于没上线。

已改为 `MemberController.GetWholeMemberById`（带 `Include(memberSocialAccounts)`）。
副带好处：`ticket_log.sender_open_id` 从此记的是分享人真实 openid 而不是券上可能过期的
`open_id`，「已分享」列表按 sender 反查也更准。

**这类 bug 单元测试抓不到**（是数据加载姿势问题，不是纯逻辑），只能靠真机端到端验证。

## 实施中踩到：access_token 失效要强制刷新重试

首次真机验证（2026-08-15 16:35，券 193596120）：回赠券正常生成、订阅消息也发出去了，
但微信返回 `{"errcode":42001,"errmsg":"access_token expired"}`。

`MiniAppHelperController.GetAccessToken()` 用本地文件 `access_token.official_account` 缓存，
只按「拿到超过 1 小时」判断新鲜度。但同一个 appid 被多方获取时，**后取的会让先取的失效**，
而缓存这边不知情、继续拿着已经作废的 token 用。本项目正好有多个获取方：
两台服务器（mini.snowmeet.top / snowmeet.wanlonghuaxue.com）各自部署、各自维护缓存文件，
另有 legacy `weixin.snowmeet.top/get_token.aspx`。

处理：`GetAccessToken` 加可选参数 `forceRefresh`（删掉缓存文件重新取，默认 false、其它调用方零影响）；
`SubscribeMessageHelper.Send` 收到 token 类错误就强制刷新重试一次。

**要跟业务错误区分开**——见 `IsTokenInvalidResponse`：只有 `40001`（凭证无效）/
`40014`（token 非法）/ `42001`（token 过期）才重试；`43101`（用户没订阅额度）、
`47003`（参数不符模板）这类重试多少次都一样，不能重试。非 JSON 响应（网关吐 HTML 错误页）
一律不重试且不抛异常。

留痕的 `remark` 会标成「小程序订阅消息(token失效已重试)」，便于回头判断这个碰撞多不多。
如果发现频繁重试，根治要把 token 获取收敛到单一来源（集中式缓存），本次不做。

## 实施中踩到：time 类型的连接符必须是半角 `~`

第二轮真机验证（2026-08-15，token 重试修复已生效、42001 被兜住后）拿到：

```
{"errcode":47003,"errmsg":"argument invalid! data.time2.value invalid"}
time2 = "2026年8月15日～2027年4月30日"
                     ↑ U+FF5E 全角
```

微信文档规定 time 类型的时间段用 **`~`（半角 U+007E）** 连接（示例 `15:01`、
`2019年10月1日 15:01`、`15:01~17:00`）。中文输入法下极易打成全角 `～`(U+FF5E)，
肉眼几乎看不出区别，但微信直接判非法。

已抽成常量 `TicketTransferRules.RangeSeparator` 并加了一条专门断言"不含全角波浪号"的
测试，防止以后手滑改回去。

**排查这类错误的正确姿势**：不要盯着字符串看，直接把 `template_message_log.keywords`
里的实际 payload 逐字符打出码点——`' '.join(f'{c}(U+{ord(c):04X})')`，一眼就能看出来。

如果改成半角后仍报 `data.time2.value invalid`，下一个候选是补上时分
（`2026年8月15日 00:00~2027年4月30日 23:59`，贴合文档示例格式），再不行就退成单个日期。

## 追加需求：券列表显示时间（2026-08-15）

| tab | 情况 | 取值 | 文案 |
|---|---|---|---|
| 未使用 | 转赠领来的 | `ticket_log` 里我接受那条的 `transact_time` | 领取时间 |
| 未使用 | 自己获得的 | `create_date` | 获得时间 |
| 已使用 | — | `used_time` | 核销时间 |
| 已分享 | 对方还没接受 | `shared_time` | 分享时间 |
| 已分享 | 对方已接受 | 最后一条转赠成功记录的 `transact_time` | 对方领取时间 |

**⚠️ 不能用 `ticket.accepted_time`**：字段名像"接受时间"，实际只在建券时赋 `DateTime.Now`、
转赠接受时**从不更新**——生产库 12164 张券它全部等于 `create_date`。真正的接受时间只在
`ticket_log.transact_time` 里。

实现要点：

- 时间和文案都由**后端**按所在 tab 算好下发（`Ticket.displayTimeLabel` / `displayTimeText`），
  前端零判断。理由同 `transferredOut`：不让前端从字段反推语义
- **下发的是格式化好的字符串**（`yyyy-MM-dd HH:mm`），前端不做任何日期解析——
  iOS 上 `new Date('2026-08-16 10:30:00')` 会得到 `Invalid Date`
- 转赠记录**批量查**（`FillDisplayTime` 一次捞完这批券的 log），不要在循环里逐张查
- 已使用 / 已分享-未接受这两种上下文用不到转赠记录，跳过那次查询

**详情页没做**：`GetTicket` 是无会话接口，判断不了"这张券是我领来的还是自己获得的"，
要做得先换成带 sessionKey 的接口。列表页够用就先不动。

## 部署注意

- 无库表变更，不需要 DDL
- 前后端必须一起上：订阅消息模板 ID 前端要传给 `requestSubscribeMessage`、后端要用它发送
- 需在小程序后台确认模板 `TsWgivHWG5TT8OVI5hN7n56yCWJ5K8THFBtmmACfek4` 处于启用状态
