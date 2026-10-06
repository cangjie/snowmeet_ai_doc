# 小程序请求发送失败原因排查

> 归档日期：2026-10-06（北京时间） · 会话 #7 · 模式：chat
> 所属用户：苍杰(私)

## 用户 · 2026-10-06T20:38:50+08:00

你还可以工作吗？



## 助手 · 2026-10-06T20:38:54+08:00

可以。我会继续基于 Snowmeet 项目资料工作：先核对已有代码、接口和生产状态，再给出带资料引用的分析、建议或功能规格。



## 用户 · 2026-10-06T20:39:32+08:00

小程序的请求，为什么发不上来了？



## 助手 · 2026-10-06T20:39:37+08:00

目前资料不足以确定唯一原因；从现有代码看，优先排查**请求域名、微信合法域名和后端是否收到请求**，而不是先改业务接口。

- 如果使用 `utils/util.js:performWebRequest`，非 `200` 会直接 `reject` 并提示“网络错误 xxx”；后端业务错误则会提示接口返回的 `message`。[[C2]]
- 部分页面不是统一封装，而是直接拼接 `https://` + `app.globalData.domainName`，例如 `SkiPass` 请求；因此 `domainName` 配错、HTTPS 证书/域名变更，都会导致请求根本到不了后端。[[C16]]
- 若只有新版结算页二维码相关功能失败，还要检查微信公众平台的 `downloadFile` 合法域名；这影响下载二维码，不一定影响普通 API 请求。[[C10]]
- 如果后端完全没有访问日志，优先看：微信开发者工具控制台的具体报错、请求 URL 是否仍是 HTTPS、是否命中小程序“request 合法域名”、以及当前环境是否切到了错误的 `requestPrefix/domainName`。如果后端有访问但返回非 200，再查接口路由、会话和服务端日志。

请提供一条失败请求的**完整 URL（可隐藏参数）、微信控制台报错、HTTP 状态码，以及后端是否有日志**，才能进一步判断是域名拦截、网络失败、接口路由还是业务错误。



---

## 引用来源

| 标记 | 来源 | 位置 |
|---|---|---|
| `[[C2]]` | `alipay_snowmeet:utils/util.js` | utils/util.js |
| `[[C16]]` | `snowmeet_wechat_mini:pages/ski_pass/skipass_detail_new.js` | ski_pass/skipass_detail_new.js > _requestPayment |
| `[[C10]]` | `snowmeet_ai_doc:sessions/2026-06-07_settle_qr_share_button_and_payment_link.md` | 2026-06-07 — settle 页二维码「转发给微信好友」按钮 + 微信支付链接路径改 order_payment |

## 附件原件

