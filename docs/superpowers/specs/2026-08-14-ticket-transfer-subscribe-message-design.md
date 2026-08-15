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
| `time2` | 有效期 | time | `2026年8月14日～2027年4月30日`——**只到日、不带时分**，起点取新券 `start_date`、终点取 `expire_date`（time 类型支持 `~` 连接时间段） |
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

## 部署注意

- 无库表变更，不需要 DDL
- 前后端必须一起上：订阅消息模板 ID 前端要传给 `requestSubscribeMessage`、后端要用它发送
- 需在小程序后台确认模板 `TsWgivHWG5TT8OVI5hN7n56yCWJ5K8THFBtmmACfek4` 处于启用状态
