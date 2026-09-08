# 2026-09-07 管理员页面帮助与自然语言查询：小程序入口、服务审计和 reqai 部署

按主题整理。本场新增管理员后台的 AI 帮助系统，改动跨 `snowmeet_wechat_mini`、`SnowmeetApi` 和独立项目 `reqai`。小程序负责入口与展示，SnowmeetApi 负责员工鉴权、业务数据查询和审计，reqai 负责基于项目资料的帮助生成与受限查询条件解析。

## 1. 管理员页面帮助

### 1.1 全页面挂载

- 新增 `components/admin-page-help/` 通用组件。
- 为 66 个 `pages/admin/**/*.wxml` 各挂载一次。
- 组件按当前页面 route 请求帮助说明。
- 帮助弹层支持后续自然语言追问。
- 页面说明只讲功能、规则、操作和常见错误。
- 小程序不展示代码、字段、接口或文件路径。

### 1.2 悬浮入口交互

- 帮助图标为屏幕内可拖动的圆形悬浮按钮。
- 拖动位置限制在可视区域内。
- 修复拖动后无法点击：`catchtouchstart/end` 会阻断微信 tap 合成。
- 改为普通 start/end 绑定，仅在 move 阶段阻止页面滚动。
- 拖动释放产生的合成点击短暂忽略，下一次点击可直接打开。

## 2. 服务架构与审计

### 2.1 reqai 服务接口

- 新增私有服务凭据 `SNOWMEET_SERVICE_TOKEN`。
- SnowmeetApi 以 `X-Snowmeet-Service-Token` 调 reqai。
- 未配置或错误凭据一律返回 401。
- 新增 `/api/service/page-help` 页面帮助接口。
- 页面说明按 route 缓存 30 天，追问实时生成。
- reqai 新增 `admin_page_help_cache` 和 `snowmeet_help_invocations`。
- 每次帮助调用记录 staff、route、问题、回答、引用、模型、effort、用量、状态和异常。

### 2.2 SnowmeetApi 代理与审计

- 新增 `AdminAiController`，小程序不直连 reqai。
- 页面帮助/追问要求 `staff.title_level >= 200`。
- 新增 `admin_ai_request_log` SQL Server 表和 EF 模型。
- 外呼前先落 pending，成功/失败均补齐状态、耗时、上游响应和异常。
- 不记录共享密钥、Cookie 或授权凭据。
- 生产首次 502 根因不是 token，而是 reqai 调 `build_context()` 漏传必填 `pinned`；补为 `pinned=[]` 后已恢复。

## 3. 租赁自然语言查询首版

- 仅在 `pages/admin/rent/new_rent_list` 帮助弹层显示“查询数据”。
- reqai `/api/service/rent-query-intent` 只输出严格 JSON 条件，不生成 SQL。
- 条件白名单：日期、门店、租赁状态、测试、招待、减免、次卡、手机号后缀、关键词。
- SnowmeetApi 再校验日期完整性、365 天范围、状态集合和手机号格式。
- 后端复用既有 `OrderController.GetCommonOrders` 查询。
- 返回最多 200 单的订单数、应收、实收、退款、未支付数、状态分布和提示。
- reqai 不接收订单明细或生产行数据，只负责解析员工输入。
- 补齐 `llm.complete_json(..., effort=...)`，修复结构化意图解析的运行时参数错误。

## 4. 生产部署与验证

- reqai 部署在 `44.207.251.65` 的 `/home/ubuntu/reqai`，服务端口 8003。
- 执行 reqai migration 后 `schema_version = 5`，两张帮助表均已存在。
- reqai `page-help`、`rent-query-intent` 路由均已加载。
- 实测页面帮助返回完整说明和引用；服务凭据校验正常。
- reqai 意图烟测“查询本周未支付的租赁订单”返回本周日期范围和 `未支付` 状态。
- SnowmeetApi 生产 Swagger 已包含 `QueryRentOrdersByNaturalLanguage`。
- 审计确认 `page_help` 与 `follow_up` 已有成功调用；归档时尚无 `rent_query` 的小程序端实际调用记录。
- 所有 reqai 重启后均检查 `ari.goldenma.xyz`，保持 HTTP 200；未修改 ari 或 nginx 配置。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/components/admin-page-help/` | 帮助弹层、拖动入口、追问和租赁查询 UI |
| `snowmeet_wechat_mini/utils/data.js` | 页面帮助、追问、租赁查询 API helper |
| `snowmeet_wechat_mini/app.json` | 全局注册帮助组件 |
| `snowmeet_wechat_mini/pages/admin/**/*.wxml` | 66 个管理员页挂载帮助组件 |
| `SnowmeetApi/Controllers/AdminAiController.cs` | reqai 代理、员工鉴权、审计与租赁查询执行 |
| `SnowmeetApi/Models/AdminAiRequestLog.cs` | SQL Server 审计模型 |
| `snowmeet_ai_doc/sql/2026-09-07_admin_ai_request_log.sql` | `admin_ai_request_log` DDL |
| `reqai/backend/app/routers/page_help.py` | 页面帮助、缓存和调用记录 |
| `reqai/backend/app/routers/query_intent.py` | 租赁查询意图 JSON 解析 |
| `reqai/backend/app/service_auth.py` | SnowmeetApi 私有服务鉴权 |
| `reqai/backend/app/llm.py` | 结构化输出支持 effort |
| `reqai/backend/migrations/2026-09-07_snowmeet_page_help.sql` | reqai schema 升至 5 |

## 学到的小知识

1. **小程序触摸事件会影响 tap 合成**：悬浮按钮用 `catchtouchstart/end` 会导致拖动后看得见却点不到；只拦 move。
2. **reqai 结构化输出也必须传 effort**：调用者传参数前先核函数签名，否则接口会在运行时 502。
3. **手写 MySQL DDL 要避开保留字**：`usage` 列必须写成 `` `usage` ``，SQLite 能过不代表 MySQL 能过。
4. **生产配置不是开发配置**：`appsettings.Development.json` 不会自动成为生产配置；reqai URL 与共享 token 必须在运行环境实际注入。
5. **自然语言查询不等于 AI 查询数据库**：模型只能产出受限条件，SQL/EF 查询和统计必须由业务后端确定性执行。
