# 2026-10-03 reqai 每日会话与附件自动归档

用户要求：按日期目录归档每天的会话和上传原件，推送到 GitHub 的 snowmeet_ai_doc；网页可手动执行，自动时段暂定每天 12、15、18、21、24 点。

## 已上线行为

- 管理员入口：reqai「后台 → 每日归档 → 立即归档并推送」。显示进度、上次成功、下次计划、覆盖数量、Git 提交及失败原因。
- 北京时间 12:00、15:00、18:00、21:00、24:00 自动执行；24:00 即次日 00:00，补齐前一天。服务启动补跑，失败每 5 分钟重试，进程内互斥。
- 输出：`reqai_archives/YYYY-MM-DD/conversations/session-ID.md` 与 `.json`、`files/ID_原文件名`、`manifest.json`。保存会话、消息、项目、用户显示名、引用、消息附件 ID 和 SHA-256，原件不转换。
- 按会话创建/更新、消息创建及附件上传的北京时间日期选当天有活动的会话；完整对话截至该日结束。首次补归档现存历史数据，同日更新，次日补齐后封存。已保存资料不随网页删除而移除；从未归档的已删资料无法恢复。
- 独立 clone：`/home/ubuntu/reqai-data/archive/repo`，状态：`/home/ubuntu/reqai-data/archive/state.json`。新建父目录归 ubuntu、0700；原有数据父目录和附件目录权限未改。
- 不复用 corpus checkout；只提交归档目录，拒绝其他改动/提交，不强推。推送失败保留本地提交；远端文档变化时只重放归档提交，同一归档冲突时报错并保留本地工作。
- 不进入需求检索。手动接口和状态只限管理员；普通用户经文件浏览器也不能读全部用户归档。

## 版本与验证

- reqai：`6f24248` 主功能，`fefa3a4` 独立可写存储目录；本机 `D:/source/snowmeet/ai/snowmeet_reqai`、GitHub main 和 `/home/ubuntu/reqai` 均为 **fefa3a4**。旧目录 `D:/source/snowmeet/snowmeet_reqai` 未修改。
- Windows 相关回归 **104 过/11 排除**：5 项依赖旧 Mac 文件路径、6 项假定 POSIX 路径字符串的既有用例。服务器隔离 SQLite/本地 Git 回归 **110 过/5 排除**，仅排除旧 Mac 文件浏览用例。
- 新测试覆盖日期边界、原件哈希、幂等、Git 实际提交/推送、失败保留、远端文档更新后的恢复、互斥、启动补跑、重试、权限及检索排除。Git 测试仅用本地 bare remote。
- 前端 TypeScript/Vite 构建、lint 通过，保留既有分块/其他页面警告。浏览器本地隔离页面实际点击了标签和按钮，状态/时段显示正确，使用模拟执行结果；线上使用认证 HTTP 验收，未做线上浏览器点测。
- 首次线上手动归档：**3 个活动日期（09-06、09-11、10-02）、5 份会话、22 条消息、3 份原件**，文档提交 **e87f5a0**。原件 3/3 字节数及 SHA-256 通过，匿名 401、普通用户 403、管理员可执行。
- 自动启动补跑成功（`caller=schedule`、`last_schedule_slot=2026-10-03T00:00:00+08:00`），没有重复 Git 提交。下次计划 **2026-10-03 12:00 北京时间**。未等待到实际计划时刻，时段边界由测试验证。
- 收尾服务 active/running、`NRestarts=0`、入口最终 200，归档 clone 干净、与 origin/main 一致。Python/MySQL 时间均验证为 UTC，`ARCHIVE_DB_UTC_OFFSET_HOURS=0`。

## 部署与恢复

- 备份：`/home/ubuntu/reqai-deploy-backups/20261003T021447Z-archive`，含原 env（0600）、旧前端及隔离测试资料。
- 增加六项 ARCHIVE_*，`deploy/configure_archive.py` 只更新这些变量。调度在已有单 worker 内，无额外 cron、无新依赖、无 DB schema/DDL。
- `deploy/verify_archive.py` 用现有管理员、仅内存中的签名 cookie，不输出凭据或正文；默认只读，`--trigger` 才手动归档。
- 设置 `ARCHIVE_ENABLED=false` 并重启可禁用自动任务，手动仍可用。回退旧代码须恢复备份 env/前端，避免旧代码拒绝新变量；保留归档 clone、Git 提交和现有原件。
- 本轮不改 SnowmeetApi、公众号、小程序或 Snowmeet 业务库。保留其他会话的工作及公众号已有未提交改动。
