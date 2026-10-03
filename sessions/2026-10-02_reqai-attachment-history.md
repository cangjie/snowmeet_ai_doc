# 2026-10-02 reqai 任意格式附件：保留原件并可从项目历史下载

接续当天已归档的 reqai 同步、价格与简洁回答工作。本轮代码于 10-02 完成并部署，用户于 **2026-10-03（北京时间）**要求 `end-work`；归档文件按本轮工作起始日命名。

用户要求：「上传文件需要可以接受任何格式的文件，如果你解析不了，可以直接保存，在未来回顾项目历史进度的时候原样输出就好。当然你解析的了的文件，还是需要你来理解的。」实现落在独立仓 `/Users/cangjie/Projects/snowmeet/reqai`。

## 1. 最终行为

- 前后端取消文件类型白名单。
- 单文件上限仍为 20 MB。
- 每条消息最多 5 个附件。
- 会话累计数量不再限制为 5 个。
- 能解析的内容进入模型上下文。
- 解析失败仍保存完整原件。
- 页面区分已解析、图片、未解析。
- 历史消息、会话与项目可下载原件。
- 编辑和重新生成保留原附件。
- 后续对话继续参考解析文本。
- 导出包含原件下载链接。
- 下载权限跟随所属会话。

支持提取 PDF 文本、DOCX 段落及表格、XLSX 单元格、PPTX 幻灯片文本，以及可解码的 UTF-8/UTF-16 文本（不限扩展名）。有效 PNG/JPEG/GIF/WebP 送入视觉模型；损坏图片不发送错误视觉输入。扫描 PDF、旧版 Office 或其他不能提取的文件可保存原件，但不声称已经理解其内容。

解析文本与模型上下文仍有长度预算，截取时明确提示；原件不截断、不转换。原件下载使用 attachment 响应与 `nosniff`。原件存储名由服务器生成；权限不足时私有附件返回 403，未登录返回 401。

## 2. 数据与接口

`chat_attachments` 保存原件元数据及可选提取文本，新增 nullable `messages.attachment_ids JSON` 保存本轮关联。原件继续属于会话，编辑/重发可复用；旧附件没有强行推断消息关联，仍可在会话、项目附件列表和会话导出中访问。

| 接口 | 用途 |
|---|---|
| `POST /api/sessions/{sid}/attachments` | 上传任意格式 |
| `GET /api/sessions/{sid}/attachments` | 会话全部附件 |
| `GET /api/projects/{pid}/attachments` | 项目历史附件 |
| `GET /api/attachments/{aid}/download` | 下载原件 |

上传返回 `processing`（`parsed` / `image` / `stored`）、`download_url` 和原件 SHA-256。附件 ID 在写用户消息前校验，其他会话的 ID 被拒绝且不留下空消息。

## 3. 美国部署与持久存储

reqai 提交 **`e1c83735412996a773adbb6f57a52aa16b1d0bdb`** 已推送到 `main`，服务器 `/home/ubuntu/reqai` 快进到同版，并更新构建后的 `backend/static`。

- 主机：`ubuntu@44.207.251.65`。
- 服务：systemd `reqai`，单 worker。
- 监听：`127.0.0.1:8003`。
- 配置：`/etc/reqai/env`，凭据未输出/入仓。
- 原件：`/home/ubuntu/reqai-data/attachments`。
- MySQL：**仅 `snowmeet_reqai` schema 5→6**。
- reqai Nginx 两处限额：8m→22m。
- 入口：`http://ai.snowmeet.top/`。

迁移 [`2026-10-02_attachment_history.sql`](../../../reqai/backend/migrations/2026-10-02_attachment_history.sql) 通过 information_schema 判断列是否存在；线上连续应用两次通过，旧消息数量不变。既有 SQLite 开发库启动时补列。

旧服务 `PrivateTmp=true`，普通主机 `/tmp/reqai-attachments` 为空，却在 `/proc/308721/root/tmp/reqai-attachments` 找到 **1 份 1,515,420 字节原件**。部署前先备份，短暂阻止新上传/聊天，按 SHA-256 复制校验，改持久目录后再重启。已有原件重启后实际下载并核对字节通过。

备份目录：`/home/ubuntu/reqai-deploy-backups/20261002T135343Z-attachments`，含原配置、前端、相关 schema 和原件及哈希清单，访问受限。**这不是完整数据库备份**；后续备份须同时覆盖数据库与原件目录。

10-03 收尾只读复核：本机/远端/服务器提交一致，服务 active、`NRestarts=0`，schema 6；现有原件 **3/3 可用**，迁移的 1 份哈希仍与备份相同。HTTP 入口保持既有 HTTPS 跳转，最终 200。本轮只修改 reqai 站点上传限额，未更改 TLS、域名跳转或同机其他站点配置。

## 4. 验证与限制

- 新附件行为测试：17 项通过。
- 本机相关回归：79 项通过。
- 服务器隔离 SQLite 回归：79 项通过。
- 完整后端：322 过、13 败、1 跳过。
- 前端 build、lint 通过，保留既有警告。
- `git diff --check`、Python 编译通过。
- Nginx 配置校验通过。

相关回归命令：`python -m pytest tests/test_attachments.py tests/test_api.py tests/test_export.py tests/test_retrieval.py -q`；运行时使用临时 SQLite、空 OpenAI key 和测试密钥。全部模型调用均为测试替身。

线上 HTTPS 经 Nginx 实测 9 MB 任意格式文件、损坏 PDF、未知扩展名文本；上传状态、下载哈希、历史消息关联、项目附件、导出绝对链接、他人 403/匿名 401 均通过，已有原件也完成真实下载核对。验收未调用线上模型；只清理临时验收用户、项目、会话和文件，保留用户资料。

13 项失败与上一轮基线一致：5 项依赖旧机器文件路径，8 项仍使用已移出白名单的旧模型；名称见 [此前归档](2026-10-02_reqai-sync-pricing-concise.md)。不能写成全部测试通过。浏览器工具没有可用浏览器，本轮完成构建及 HTTP 验收，未做实际浏览器点测。

## 5. 关键改动文件

| 文件 | 改动 |
|---|---|
| [attachments.py](../../../reqai/backend/app/attachments.py) | 提取、图片验证、模型内容与元数据 |
| [附件路由](../../../reqai/backend/app/routers/attachments.py) | 任意上传、授权下载及历史列表 |
| [对话路由](../../../reqai/backend/app/routers/chat.py) | 持久关联、历史、编辑/重发 |
| [模型](../../../reqai/backend/app/models.py) / [迁移](../../../reqai/backend/migrations/2026-10-02_attachment_history.sql) | schema 6 |
| [附件测试](../../../reqai/backend/tests/test_attachments.py) | 17 个行为用例 |
| [Composer](../../../reqai/frontend/src/components/Composer.tsx) / [AttachmentList](../../../reqai/frontend/src/components/AttachmentList.tsx) | 任意选择、上传结果、原件下载 |
| [Chat](../../../reqai/frontend/src/routes/Chat.tsx) / [ProjectPanel](../../../reqai/frontend/src/routes/ProjectPanel.tsx) | 历史及项目附件入口 |
| [部署目录](../../../reqai/deploy/) / [README](../../../reqai/README.md) | 持久目录、上传限额与升级说明 |

## 6. 交接

功能已上线，无发布阻塞；后续用真实文件继续整理需求，按反馈补充解析支持。原件不是全局公开资源，保持所属会话权限；较长文本的上下文截取与原件完整保存须同时保留。

本轮未改 SnowmeetApi、公众号或小程序，未执行 Snowmeet 业务库 SQL/DDL。10-03 收尾业务仓核对：SnowmeetApi、公众号干净，小程序仍有 118 个既有改动；不随 end-work 自动提交。此前同步/价格/简洁回答归档保留，本次只补充附件工作。
