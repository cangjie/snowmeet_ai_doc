# 2026-10-06 食材管理 v4 第 1 期生产部署

第 1 期开发验收完成并停期后，用户另行要求「部署下生产环境」，随后明确「在服务器上执行 republish.sh，数据库的 SQL 语句你执行」。本次授权覆盖这次生产连接、仅新增 SQL 和 API 发布；第二、三期仍未开工。验收时间为北京时间 2026-10-06 12:28。

## SQL

- 目标库：`snowmeet_new`。连接信息只在服务器内读取，不打印或复制凭据；没有读取 Windows 本机 `SnowmeetApi/config.sqlServer`。
- 执行文件：[2026-10-06_fnb_v4_rebuild.sql](../sql/2026-10-06_fnb_v4_rebuild.sql)，SHA-256 `d42ff5527e99d1f49d39a5d5cf93e38314f26a22a97219368fdc7f50351d0c18`。
- 执行前无 v4 业务表；执行后新增 **18 张 `fnb_v4_*` 表、2 个视图**。全部字段与脚本结构一致。
- 既有 `fnb_unit` 的基本单位已齐，实际新增单位 **0 行**。执行前后既有单位行完全一致；旧 fnb 表、共享表字段定义和旧视图保持不变。脚本没有 DROP/DELETE/UPDATE/ALTER/TRUNCATE/MERGE，也没有旧食材数据迁移。
- v4 食材 **0**、批次 **0**。本轮没有创建示例食材或业务库存数据。
- 服务器缺少 Python SQL 驱动，已将经 PyPI SHA-256 核验的 pymssql 2.4.3 隔离安装到 `/home/ubuntu/fnb-v4-deploy-20261006/deps`，没有改系统公共 Python 包。

## API 发布

- 服务器：经既有 `44.207.251.65:2222` 转发连接 mini 服务器；工作目录 `/home/ubuntu/webs/SnowmeetApi`，服务 `mini.snowmeet.top.service`。
- 发布前源码 `ai@0e9388c0`，没有已跟踪文件改动；服务器上已有的运行生成文件和未跟踪日志保留。
- 先备份运行文件、核对待发布版本，再执行**服务器现有 `republish.sh`**；没有改脚本、没有上传另一套 DLL 发布包。
- 发布后源码 **`ai@ec7c25612590b31ce72af56b4a1f6774d85dbdef`**。republish.sh 退出 **0**，新程序集 SHA-256 `334654396f3050eb884b0972cdecb6804c49b5937673ddae252da71cb7bc918f`。
- 服务 **active/running**，MainPID **26412**，NRestarts **0**。构建成功，旧代码警告仍在；发布后根盘剩约 **1.3 GB**，本次回滚备份保留。

## 只读验收与边界

- 本机和公网 Swagger 文档可读取，公网 `https://mini.snowmeet.top/swagger/v2/swagger.json` HTTP **200**。
- 新 `FnbAuth`、`FnbCatalog`、`FnbRoute` 的 **17 个接口**全部已注册。
- `GetMe` 使用不存在的会话返回 HTTP **200 / code 2**，验证新的处理链和生产身份表读取；没有发送真实企业微信 OAuth、支付、退款或业务过账请求。
- 旧食材库存、厨房、配方、盘点、报表控制器不再注册；旧 `FnbMaterial/GetBatches` 不再是路由。旧批次/提醒接口停用是这次版本的预期变化。
- 发布前的 **494 个非 Fnb 路由**发布后仍注册；对受保护的静态页面及采集相关文件逐文件检查，**463 个文件哈希全部相同**。没有编辑小程序、wwwroot 页面、美团采集器或其工具。
- 本次线上检查是部署及只读接口验收；第一期的完整隔离验证仍是此前 **467 项单元/HTTP + 12 项 LocalDB** 全过。没有声称完成第二、三期或 32 步完整业务验收。
- 旧客户端文件仍保留，旧食材入口和旧提醒定时调用没有改动；其旧业务请求现在会遇到停用接口。第一期只提供身份和主数据功能，入库、库存、作业、出餐、报表等需后两期实现。

## 回滚与审计

- 发布前 **435 个运行文件**备份在 `/home/ubuntu/fnb-v4-deploy-20261006/runtime-backup`，旧主程序集 SHA-256 `fa35d5dad4fd8d01d0675a51299a194085dcc663998379823964962a87a29072`。
- 发布日志 `/home/ubuntu/fnb-v4-deploy-20261006/republish.log`；SQL 结果 `sql-result.json`、发布前状态 `publication-before.json`、最终验证 `verification.json` 在同目录。目录权限 700。
- 未触发回滚。需要故障回滚时恢复备份运行文件并重启服务；保留新增表和全部数据库数据，不执行删表/删数据。源码 HEAD 已推进到 ec7c2561，恢复旧运行文件后需明确记录源码与运行版本的差异。

本次生产执行与部署已完成，继续停在第 1 期，等待用户的后续指令。
