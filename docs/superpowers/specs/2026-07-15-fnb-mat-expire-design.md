# 食材过期提醒（fnb mat_expire）设计

2026-07-15 · 已与用户逐项确认。设计稿：claude design 导出 `new_batch.html`（录入批次，fb-form）+ `list.html`（食材库存列表，fb-variant-b），原稿在用户 Downloads，实现时从原稿取精确配色。

## 背景与范围

餐饮业务（fnb）需要食材效期台账：录入食材批次 → 列表按临期紧急度展示 → 到期处置（用完/报废）。企业微信内打开的 H5，部署在 `SnowmeetApi/wwwroot/fnb/mat_expire/`（域名 mini.snowmeet.top）。

已拍板的范围决定：

- 全新功能、从零建表；**单店**，不设 shop 字段
- 企业微信打开 + **OAuth 认证**（snsapi_base 换 UserId），复用餐饮自建应用 AgentId 1000009（`FnbWeComController` 常量）
- 功能闭环 = 录入 + 列表 + 处置（用完/报废）+ 编辑 + 删除
- 设计稿底部 4 tab（工作台/库存/预警/我的）**不做**；预警走企业微信消息（推送通道 `FnbWeComController.SendNewsMessage` 已有，**本期不做定时任务**，先手动触发）
- 批次号**扫码录入本期不做**（企微 JS-SDK 签名是另一套链路，图标 UI 保留、点击提示后续开放）

## 页面（按设计稿还原）

原生静态 H5 双页（无构建链），Lexend 字体 + Material Symbols 图标，与 Alpine Operational Minimalist 视觉同源。

### 列表页 `index.html`（食材库存）

- 顶部：标题「食材库存」+ 右上角 add 按钮（→ new.html）
- 搜索框：按 名称/批次号 前端本地过滤；右侧扫码图标（本期点击 toast「后续开放」）
- 状态筛选 chips（带计数）：全部 / 已过期 / 今日 / 临期 / 正常 / 已处理
- 批次卡片：名称 + 批次号 + 「到期 MM/DD」+ 右侧状态徽章（逾期 N 天=红 / 今日到期=橙 / 剩 N 天=临期黄、正常灰绿）+ more_vert 菜单
- more_vert 菜单：标记用完 / 标记报废 / 编辑（→ new.html?id=）/ 删除（二次确认，软删）
- 右下 FAB 新增
- 排序：默认按 expire_date 升序（最紧急在最上）；已处理 chip 下按处置时间倒序

### 录入页 `new.html`（录入批次，编辑复用）

- 基本信息：名称*；批次号*（「生成」按钮调后端发号，也可手输）；现场照片（选填，`<input type=file capture>` 拍照/相册多张，即传即得 image id）
- 效期：生产日期（date）+ 保质期（数值 + 天/月 切换）→ **自动推算到期日期***（可手改，改后不再自动覆盖）
- 提醒：到期预警提前 N 天（-/+ 步进器，默认 3），文案「到期前 N 天进入临期提醒」
- 底部实时状态预览条：「录入后状态：{派生状态} · 距到期还有 N 天 · 到期 yyyy/MM/dd」
- Footer：取消 / 保存并加入提醒（必填齐才可点）
- 编辑模式：`new.html?id=123` 回填全部字段，保存走同一接口

## 状态派生（唯一口径，前后端一致）

```
已处理  dispose_status 非空（用完/报废都算）
已过期  expire_date <  今天
今日    expire_date == 今天
临期    今天 < expire_date <= 今天 + warn_days
正常    expire_date >  今天 + warn_days
```

状态不落库；`expire_date` 是效期唯一真理之源（生产日期/保质期仅录入辅助，原样保存供追溯）。

## 数据表

`fnb_material_batch`，DDL 见 [sql/2026-07-15_fnb_material_batch.sql](../../../sql/2026-07-15_fnb_material_batch.sql)（用户在生产库执行）。要点：批次号不设唯一约束；照片 `image_ids` 逗号分隔复用 `upload_file`；`valid` INT 软删，与 order/care 同约定；录入人/处置人存企微 UserId 字符串。

## 认证链路（企微 OAuth，新开发）

1. 企微内打开 `https://mini.snowmeet.top/fnb/mat_expire/index.html`
2. 页面 JS 检查 localStorage 的 sessionKey；无效 → 302 跳 `open.weixin.qq.com/connect/oauth2/authorize?appid={CORP_ID}&redirect_uri={当前页}&response_type=code&scope=snsapi_base&agentid=1000009#wechat_redirect`
3. 回跳带 `?code=` → 调 `Fnb/OAuthLogin?code=` → 后端拿餐饮应用 access_token（复用 `FnbWeComController.GetToken`）调 `cgi-bin/auth/getuserinfo` 换 UserId
4. 后端写 `mini_session`（新 `session_type='wecom_userid'`，UserId 存 `wechat_openid` 列——列名复用有 alipay 先例），发随机 sessionKey，H5 存 localStorage
5. 后续接口全带 sessionKey；后端按 session_type + 未过期校验，取出 UserId 作操作人
6. 接口返回「会话失效」时前端清 localStorage 重走 OAuth（静默，用户无感）

鉴权粒度：OAuth 通过（= 应用可见范围内的企业成员）即可读写，不接 staff 权限体系。

**用户操作项**：企微后台给应用 1000009 配置「网页授权及 JS-SDK 可信域名」= mini.snowmeet.top（需域名校验文件时放 wwwroot 根）。

## 后端接口（新建 `Controllers/Fnb/FnbMaterialController.cs`）

路由 `api/Fnb/[action]` 风格与现有一致（实际 `[Route("api/[controller]/[action]")]`）。

| 接口 | 方法 | 说明 |
|---|---|---|
| `OAuthLogin(code)` | GET | code 换 UserId → 建 session → 返 sessionKey |
| `GetBatches(sessionKey)` | GET | 返全量有效批次（valid=1）+ 服务器今天日期；筛选/搜索/计数前端本地做（单店数据量小） |
| `SaveBatch(POST body, sessionKey)` | POST | id=0 新增 / id>0 编辑；服务端校验必填；写 create_userid / update_date |
| `DisposeBatch(id, action, sessionKey)` | GET | action=用完\|报废 → dispose_status/userid/date；幂等（已处置返当前状态） |
| `DeleteBatch(id, sessionKey)` | GET | valid=0 软删 |
| `GenBatchNo(sessionKey)` | GET | 发号 `B{yyMMdd}-{当日已发数+1，2位}`（仅参考号，不保证并发唯一） |

照片上传：复用现有 `UploadFile` 接口链路；若其鉴权与 wecom session 不兼容，则在 FnbMaterialController 内加一个转发上传的薄接口（实施时定，二选一）。

EF：`Models/Fnb/FnbMaterialBatch.cs` + DbSet；**所有「查实体→改→存」显式 `Entry().State=Modified`**（全局 NoTracking 坑）。

## 错误处理 / 边界

- OAuth code 过期/重复使用 → 返 code=1，前端重走授权（code 一次性，回跳后立即换 session 并 `history.replaceState` 清掉 URL 里的 code）
- 到期日手改后，再改生产日期/保质期不回写到期日（手改优先，页面上「自动」徽标消失）
- 删除 = 软删，列表不显示，不做恢复入口（DB 可查回）
- 派生「今天」以**服务器日期**为准（GetBatches 返回），避免手机时区/改时间导致状态错乱

## 部署

- 前端：`wwwroot/fnb/mat_expire/{index.html, new.html, mat.css, mat.js}` 随 SnowmeetApi publish
- 后端：新 controller + model，无既有查询受影响；**先建表再 publish**
- 推送（本期外）：后续定时任务扫 `临期+今日+已过期 且未处置` → `FnbWeComController.SendNews` 推 @all，图文 url 指向本 H5

## 本期不做（明确排除）

底部 4 tab、扫码录批次号、企微 JS-SDK、定时推送任务、多店、批次号唯一性约束、照片关联表。
