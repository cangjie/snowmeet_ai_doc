# 2026-07-15 养护流程收尾修复 + 食材过期提醒（fnb mat_expire）全量实施

按时间线分两阶段。上午接续 7-14 养护核销/取消线，逐个修用户实测报的 bug（Phase A，7+ 项）；下午用户宣布「养护暂告一段落」，开启全新功能「食材过期提醒」H5（Phase B），走完 brainstorming → spec → DDL → plan → 全量实施 → 烟测 → commit+push。改动落 `SnowmeetApi` + `snowmeet_wechat_mini` + `snowmeet_ai_doc`（spec/DDL）。

## 1. Phase A — 养护流程收尾修复

### 1.1 退款弹窗备注默认取取消原因

- 需求原话：「养护订单退款，退款备注默认是当前订单中取消的那个 care 的取消的备注。如果多个 care 取消，默认填写订单中第一个 care 的取消备注」
- [`care_order_detail.js`](../../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js) `onOpenRefundPopup`：`cares.find(c => c.is_cancel)` 取 `cancel_reason` 作默认值

### 1.2 `api/Order/Refund/71881` 500（Nullable object must have a value）

- 用户贴 payload `[{"id":0,"payment_id":42700,"amount":170,"reason":"赶火车"}]` + 完整异常栈
- 根因：`OrderController.Refund` 追加草稿清理行（6-28 加的）对**非租赁单**执行 `(double)order.totalRentUnRefund` 强转——养护单 `totalRentUnRefund` 恒 null → NRE
- 修复：加 `order.type == "租赁"` 短路守卫（对照下方同类代码本就有该守卫）
- **关键认知**：崩溃发生在退款落库 + 网关已退**之后**，所以那次 500 的钱其实已退成功——这直接解释了用户下一个问题

### 1.3 「超额退款」提示答疑（无改码）

- 用户再对 71881 发起 170 退款报「超额退款」→ DB 实查 `payment_refund` 已有一条成功 170（上次 500 请求落的）→ 提示正确，无需处理

### 1.4 可退金额 0 → 退款按钮 disable

- `payment` 派生加 `canRefund = round(paidAmount − refundAmount) > 0`；按钮 `btn--disabled`（opacity .45）+ `onOpenRefundPopup` 顶部守卫 toast「无可退款金额」

### 1.5 0 元招待单点「确认生效」报「处理失败」

- 根因：`components/order-payment` 对 `paying_amount==0 && dealed==1`（PlaceCareOrder 已立即生效的质保/招待单）仍显示「确认生效」按钮 → 点击调 `EffectUnpaidOrder` 对已生效单必失败
- 修复：[`order-payment/index.js`](../../snowmeet_wechat_mini/components/order-payment/index.js) `loadOrder()` 检测该状态直接置 paid 态 + `triggerEvent('paid')`
- 附带需求：0 元订单点「去结算」加确认 modal（[`recept_new.js`](../../snowmeet_wechat_mini/pages/admin/reception/recept_new.js) `_checkoutCare` 拆出 `_doCheckoutCare`，估算 0 元且未用权益时先 `wx.showModal`「本单金额为 ¥0.00，无需收款，确认后订单立即生效。」）

### 1.6 71884 选打蜡季卡但 `punch_card_used` 无记录（根因排查 + 修复）

- 生产库只读实查（用户点名授权）：
  - `core_data_mod_log`：order 71884 `member_id 15506→41137 scene=支付成功`——`DealSuccessPaidOrder` 在 `EffectCareOrder` **之前**把订单归属改成了支付宝付款方物化出的另一会员号
  - `punch_card` 42 的 `member_id=15506` ≠ 改写后的 41137 → `EffectCareOrder` 卡核销守卫 `punchCard.member_id == order.member_id` 失败 → **静默跳过**不核销
- 修复（[`CareController.cs`](../../SnowmeetApi/Controllers/CareController.cs)）：EffectCareOrder 核销守卫删 member 比对（只留 `punchCard != null`，注释记录 71884 实录根因）；[`OrderController.PlaceCareOrder`](../../SnowmeetApi/Controllers/OrderController.cs) 卡不属会员分支追加清 `use_card/card_id/card_name` 双保险
- 顺带核查券核销：`EffectCareOrder` 券置 used 代码正确，但近 30 天 3 张选券单全 `dealed=0` 未生效 → **无实证样本**，留待带券单端到端验证
- 71884 补记录 SQL 已交付用户（未执行）：`INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date) VALUES (42, 71884, N'养护', 25690, NULL, 1, 1, '2026-07-15 10:23:45');`

### 1.7 用了老顾客券后手动加大减免被冲回

- 现象：券16 + 手动改减免 229.99（支付 0.01）→ 下单后减免变回 200
- 根因：`PlaceCareOrder` / `CalcCareCharge` 对券16 `care.discount = ticketDiscount` **无条件覆盖**
- 修复：两处改保底语义 `if (ticketDiscount > 0 && care.discount < ticketDiscount)` 才补齐——手动更大的减免不再被冲掉

### 1.8 详情页 UI 打磨四件（纯前端）

- 删「已带入…历史安检数据」toast（静默预填保留）
- 安检备注框高度减为 1/3（`.safe-memo-textarea` 100rpx）
- 装备无照片时安检面板内直接上传照片：wxml 加 `wx:if="{{care._photos.length===0}}"` van-uploader，`onSafePhotoRead` 两段上传 → 以 `_rawCares` 为基底 `_stripImageNavs + concat` → `updateCarePromise` → loadOrder（沿 7-12 careImages 全量 payload 约定）
- 装备卡显示所用卡券 icon：`_hasBenefit` 派生（use_card+card_id 或 ticket_code），`onBenefitTap` 卡显示 card_name、券首次点按调 `Ticket/GetTicket/{code}` 拉券名并缓存 `_ticketNameCache`

### 1.9 养护订单列表「券」标签

- [`care_order_list`](../../snowmeet_wechat_mini/pages/admin/care/care_order_list.js) renderOrders：care 有 `ticket_code` → `haveTicket=true` → 标签列加橙色「券」（`.tag--ticket` `#ffedd5`/`#c2410c`）；`use_card` → useCard 沿用「卡」标签

## 2. Phase B — 食材过期提醒（fnb mat_expire）

### 2.1 需求收敛（brainstorming，多轮 AskUserQuestion）

- 企业微信打开的 H5 + OAuth 认证；部署 `wwwroot/fnb/mat_expire/`（用户先说 fd/ 后拍板 fnb/ 统一餐饮缩写）
- 全新功能从零建表；单店不分 shop；闭环 = 录入+列表+处置（用完/报废）+编辑+删除
- 设计稿：claude design 导出 `~/Downloads/new_batch.html` + `list.html`（配色从 computed style 提取——style 属性超 6000 字符，采样窗口放大到 120000 才抓全）
- 预警走企微消息（复用 `FnbWeComController.SendNews`），本期手动触发不做定时；扫码录批次号本期不做
- plan 首次被拒：用户指出「需要有个地方配置通知发给谁，这个你应该没考虑到吧？」→ 拍板**配置文件**方案（`config.fnbAlertReceivers`，镜像 config.sqlServer 模式：Util.workingPath 下纯文本、gitignored、publish 不覆盖、每次现读免重启）

### 2.2 数据表（用户在生产库自建）

DDL 见 [`sql/2026-07-15_fnb_material_batch.sql`](../sql/2026-07-15_fnb_material_batch.sql)：
- `fnb_material_batch`：name/batch_no/produce_date/shelf_life_value/shelf_life_unit/expire_date/warn_days(默认3)/image_ids(逗号分隔复用 upload_file)/dispose_status/dispose_userid/dispose_date/create_userid/valid + 2 索引
- `fnb_material_alert_log`：batch_id/alert_status(快照)/expire_date(快照)/touser(默认@all)/msgid/success/err_msg/send_userid + 索引——批次维度提醒历史 + 当天去重 + 失败排查

### 2.3 状态派生唯一口径（不落库）

```
已处理  dispose_status 非空 → 已过期 expire<今天 → 今日 = → 临期 ≤今天+warn_days → 正常
```
「今天」以服务器日期为准（GetBatches 返回），避免手机改时间错乱。`expire_date` 是效期唯一真理之源。

### 2.4 后端（`Controllers/Fnb/FnbMaterialController.cs` 新建 ~470 行 + 模型 + DbSet）

- 认证：`OAuthLogin(code)` —— `FnbWeComController.GetToken` → `cgi-bin/auth/getuserinfo` 换 UserId（走 `_mH.PerformRequest` 留 WebApiLog）→ 非企业成员拒绝 → 写 `mini_session`（新 `session_type='wecom_userid'`，UserId 存 `wechat_openid` 列，列名复用有 alipay 先例；Guid N sessionKey，30 天）
- `_getWecomUserId(sessionKey)` 校验 session_type+valid+expire；失效统一返 `code=2`（前端识别静默重走 OAuth）
- CRUD：`GetBatches`（valid=1 全量 expire 升序 + 服务器 today）/ `SaveBatch`（id=0 新增、编辑保留 create_*/dispose_*，**Entry().State=Modified**）/ `DisposeBatch`（用完|报废，幂等）/ `DeleteBatch`（valid=0）/ `GenBatchNo`（`B{yyMMdd}-{NN}`）/ `UploadPhoto`（薄上传，UploadFile staff_id=null、owner=UserId、purpose=食材批次）/ `GetImages`（编辑回显）
- `PushExpireAlert(sessionKey, touser?)`：候选=未处置且状态≠正常 → alert_log 当天 success=1 去重 → 组 1 条图文（title「食材到期提醒：N 项需处理」desc「已过期 X · 今日到期 Y · 临期 Z。名1、名2、名3 等」url=H5）→ `SendNews` → 逐批次写 alert_log 快照。接收人 = touser 参数 → `config.fnbAlertReceivers` → @all
- `.gitignore` 加 `config.fnbAlertReceivers`

### 2.5 前端（`wwwroot/fnb/mat_expire/` 4 文件，原生静态 H5 无构建链）

- `mat.js` 公共模块：`inWeCom()`（UA 含 wxwork）/ 非企微显提示防重定向死循环 / `ensureSession()`（**?sessionKey= 调试后门** → ?code= 换 session + `history.replaceState` 清 code → localStorage → OAuth）/ `api()` fetch 包装（code=2 清 key 重走 OAuth）/ `deriveStatus` 与后端同口径
- `index.html` 列表页：搜索本地过滤（扫码 toast 占位）、六状态 chips 计数、卡片+徽章（逾期N天红/今日到期橙/剩N天琥珀/正常绿/已用完·已报废灰）、more_vert 底部面板（用完/报废/编辑/删除 confirm）、FAB；已处理 chip 下按 dispose_date 倒序
- `new.html` 录入/编辑页：名称*/批次号*+生成/照片多张即传即得含删除/生产日期+保质期天月切换→自动推算到期日+「自动」徽标（手改 `expireManual=true` 后不再覆盖）/预警步进器默认3/实时状态预览条/保存 disabled 门控（含 uploading 计数）；`?id=` 编辑回填（expireManual=true 视为已定）
- 图标全部内联 SVG（不引 Material Symbols web font）、系统字体栈（不内嵌 Lexend）；配色 Alpine 系（主 #006495、过期红 #ba1a1a、今日橙 #c2410c、临期琥珀 #a8720a、正常绿 #1f8a5b）

### 2.6 验证

- `dotnet build` 0 error；本地 `dotnet run`（临时 sed 改 config.sqlServer IP 161.189.64.210→100.28.143.19，测完已还原）三项烟测：伪 sessionKey→code=2、假 code→优雅 code=1（企微 60020=本机 IP 不在白名单，服务器已在白名单属预期）、GenBatchNo→code=2
- 浏览器预览：`python3 -m http.server 8391`（navigate file:// 会超时）+ `?sessionKey=preview-test` 后门进入 + 注入 mock 数据，两页视觉与设计稿一致
- SnowmeetApi commit `3d0b27b`（9 文件 +1434 行）已 push origin/ai

## 关键改动文件

| 仓库 | 文件 | 改动 |
|---|---|---|
| SnowmeetApi | `Controllers/OrderController.cs` | Refund 草稿清理加 `type==租赁` 守卫（修 NRE）；PlaceCareOrder 卡不属会员清引用 + 券16 减免改保底 |
| SnowmeetApi | `Controllers/CareController.cs` | EffectCareOrder 卡核销删 member 比对守卫；CalcCareCharge 券16 保底 |
| SnowmeetApi | `Controllers/Fnb/FnbMaterialController.cs` | 新建：wecom OAuth + 批次 CRUD + 推送提醒（~470 行） |
| SnowmeetApi | `Models/Fnb/FnbMaterialBatch.cs` + `FnbMaterialAlertLog.cs` + `Data/ApplicationDBContext.cs` | 新模型 ×2 + DbSet ×2 |
| SnowmeetApi | `wwwroot/fnb/mat_expire/{index,new}.html + mat.{css,js}` | 新建：食材过期提醒 H5 双页 |
| SnowmeetApi | `.gitignore` | + `config.fnbAlertReceivers` |
| mini | `pages/admin/care/care_order_detail/*` | 退款备注默认/canRefund disable/安检备注 1/3/安检面板补传照片/卡券 icon+toast/删历史数据 toast |
| mini | `pages/admin/care/care_order_list.*` | 「券」标签 |
| mini | `components/order-payment/index.js` | 0 元已生效单直接置 paid 态 |
| mini | `pages/admin/reception/recept_new.js` | 0 元单去结算确认 modal |
| doc | `docs/superpowers/specs/2026-07-15-fnb-mat-expire-design.md` + `sql/2026-07-15_fnb_material_batch.sql` | 设计文档 + DDL |

## 学到的小知识

1. **Refund 的 NRE 崩溃点在退款落库之后**：钱已退、响应 500 → 用户重试就撞「超额退款」。排查退款类 500 先查 `payment_refund` 有没有已成功行，别急着当退款失败处理
2. **`DealSuccessPaidOrder` 会在 `EffectCareOrder` 之前改写 `order.member_id`**（支付方≠开单会员时，如同人微信/支付宝双通道两会员号）→ 任何拿 `order.member_id` 与开单时会员资产（卡/券）比对的守卫都会静默失败。核销守卫不应比 member（卡是开单时验证过归属的）
3. **减免类字段"覆盖 vs 保底"语义要分清**：券的固定减免应是保底（`<` 才补齐），无条件赋值会冲掉店员手动加大的减免
4. **`mini_session.session_type` 可扩展承载第三方身份**：`wecom_userid` 是继 `alipay_payerid` 之后第三种，UserId 复用 `wechat_openid` 列，零 schema 改动
5. **配置文件模式（config.sqlServer 系）适合"服务器本地、免重启、不入库"的运营配置**：`Util.workingPath` 下纯文本 + gitignore + 每次现读，`config.fnbAlertReceivers` 照抄即可
6. **claude design 导出的 HTML 单个 style 属性可超 6000 字符**：抽 computed style 采样窗口要放大（本次 120000），否则正则截不到完整属性、提取全空
7. **浏览器工具 navigate file:// 会超时**：本地静态页预览用 `python3 -m http.server` 起服务；OAuth 门控页面调试留 `?sessionKey=` 后门 + 注入 mock 最快
8. **企微 OAuth 错误码 60020 = 调用方 IP 不在企业可信 IP 白名单**：本机联调必现，不代表代码错；服务器 IP 已在白名单则部署后即通
