# 2026-10-06 食材管理 v4 完整后端生产部署

用户审阅扩展 SQL 后明确要求“SQL看了 没问题，立刻部署”。本次执行固定审阅版本 SQL，再通过服务器原有 `republish.sh` 发布已验收的完整后端。北京时间 **2026-10-06 18:29** 完成生产检查。

## 生产 SQL

- 文件：[2026-10-06_fnb_v4_operations.sql](../sql/2026-10-06_fnb_v4_operations.sql)。SHA256 `52632E5BCD021AEB99AAAB137007A1C23F8A38989FBF1F49F45A004ECD9FBDEC`，与用户审阅版本一致。
- 目标库 `snowmeet_new`，在服务器内部使用已有连接配置，没有读取 Windows 本机 `SnowmeetApi/config.sqlServer`，没有复制或打印连接凭据。
- 成功新增 **13 张表、18 个索引**，核对所有新列与索引。执行前后原有全部表列定义与已有索引元数据保持一致。
- 仅 CREATE TABLE/INDEX，无 INSERT、UPDATE、DELETE、DROP、ALTER、TRUNCATE、MERGE；没有清理测试数据或文件，没有重跑第一期 SQL。
- 新表用途见 [SQL 审阅说明](../docs/fnb/2026-10-06-fnb-v4-operations-sql-review.md)。员工信息及其他业务数据没有写入或删除操作。

## 发布

- 经既有 `44.207.251.65:2222` SSH 转发连接，目录 `/home/ubuntu/webs/SnowmeetApi`，服务 `mini.snowmeet.top.service`。
- 发布前 `ai@955188ab4143cd63c051105823b2b4446464bc6b`，发布后 **`ai@e97190e2b0c4be8a77bac5b0f9a4993704aa123a`**。跟踪文件干净，远端 ai 与固定目标一致。
- 发布既有提交的 22 个服务端/测试文件，清单及规则见 [开发验收记录](2026-10-06_fnb-v4-complete-backend.md)；本次没有新增 API 代码修改。
- 先备份 **435 个运行文件**，再执行原 `republish.sh`，由其自身 git pull、停服务、清理 bin/obj、publish、启动服务；未改脚本，未上传另一套 DLL。
- 脚本退出 **0**，完整日志无构建错误，编译警告仍在。主程序集 SHA256 `9101107eeb1b47600e978529bd7afb28b036a63929098897597089e80f95c63e`，与发布前不同。
- 原脚本 SHA256 `dc778ef5d85148c23d3e08c39e17822dc17f01a93d2b1ce46d10150955b4a007` 未变。发布后根盘余量约 **883 MB**；未删除旧备份或其他文件。

## 验证

- 服务 **active/running**，MainPID **42615**，NRestarts **0**。
- 公网 Swagger HTTP **200**，新增 **69 个后端动作**全部注册，加一期共 **86 个 v4 动作**；总路径 587，原 **518 条路由全部保留**。
- 身份接口及 12 个新模块只读入口使用不存在的会话，均 HTTP 200 / code 2；没有创建真实会话、业务过账、发送提醒或触发 OCR。
- H5 全部 **7 个 HTML/JS/CSS 资源 HTTP 200**，响应 SHA256 与固定提交一致；长批次 ID `/fnb/b` 仍 302 到 `/fnb/v4/index.html`，query 完整保留。
- **470 个受保护文件哈希未变**，包括现有静态页面、OCR、蓝牙打印及美团采集源码/工具；小程序未修改。
- 沿用开发验收：构建 0 错误、467 项回归、22 项 LocalDB 集成测试（含 32 步）。没有在生产运行集成测试、`dotnet run` 或 `run_fnb_http_smoke.py`。

## 状态与回滚

- 完整后端和扩展结构已生产生效，本次无需用户另行执行 SQL。
- **H5 仍是此前第一期接入版本，后续页面存在占位/禁用按钮，需继续前端接口联调。发布后端不会自动启用这些按钮。**入口仍为 [食材管理 v4](https://mini.snowmeet.top/fnb/v4/index.html)，企业微信工作台配置未变。
- 真机 OAuth、相机 OCR、蓝牙连接及实际标签出纸本次未验收，没有真实库存/出餐过账。
- 回滚备份 `/home/ubuntu/fnb-v4-operations-deploy-20261006/runtime-backup`；需要回滚时恢复运行备份并重启服务，**保留新增数据库结构与数据，不执行 DROP/清库**。仅回退到本次发布前 v4，不重建已删除的旧食材结构。
- 同目录保留审阅 SQL、结构快照、SQL 执行结果、发布前状态、`republish.log`、最终 `verification.json`，目录权限 700。未触发回滚。
- 此前测试数据清理请求未在本次执行，清理 skill 仍 testing；所需 DSN 来源及 S3 删除权限条件独立于本次发布授权。

## 与计划的关系

本次执行用户最新审阅批准的扩展 SQL 和服务端发布，开发范围、五项默认业务规则及差异沿用完整后端验收记录。原“开发验收不部署”由本次明确部署指令覆盖；前端接入、美团自动订单导入仍需后续工作。
