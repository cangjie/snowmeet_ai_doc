# 2026-10-02 reqai 同步与部署：价格修正和默认简洁回答

本次从 `start-work` 开始。用户要求「最近代码有更新，需要同步更新 reqai，更新后重新部署到美国的服务器上，以便整理需求」，随后确认「就是 http 即可」「入口是 ai.snowmeet.top」，并指出默认模型价格标注错误、每次对话输出过长。工作落在独立仓 `/Users/cangjie/Projects/snowmeet/reqai`，未改 Snowmeet 业务代码或执行生产 SQL。

## 1. 开工状态与范围

文档仓先 `pull --ff-only`，开工基线为 `d3251f9`。本机 SnowmeetApi `ai@8a4c335` 干净，拉取远端引用后落后 19 个提交；本次没有更新其工作区。小程序 `ai@023f7858` 有 118 个既有旧版生成文件改动，保留原状；公众号 `ai@4c9c0a6` 干净。reqai 从 `95354a3` 快进至 `6131ea4`，包括管理员助手四业务域能力和取消链路等 4 个既有提交。

收尾复核：reqai 本机、GitHub `main` 和美国服务器均为 `56b59cd4c3fb8577a3a054530563bf432fc873c0`，tracked 工作区干净。其他业务仓不自动提交、拉取或发布。

## 2. 美国部署与语料同步

### 2.1 部署位置

| 项目 | 当前配置 |
|---|---|
| 主机 | `ubuntu@44.207.251.65` |
| 仓库 | `/home/ubuntu/reqai`，分支 `main` |
| 后端工作目录 | `/home/ubuntu/reqai/backend` |
| 环境文件 | `/etc/reqai/env`；凭据不入仓、不打印 |
| Python | 后端 `.venv/bin/python` |
| systemd | `reqai`，单 worker |
| 监听 | `127.0.0.1:8003` |
| reqai MySQL schema | `schema_version=5` |
| 实际入口 | `http://ai.snowmeet.top/` |

SSH 使用本机 `~/.aws/ari.pem`；`~/.ssh/PEM.pem` 不是该主机匹配的密钥。网络间歇超时时使用 `ConnectTimeout=10`、`BatchMode=yes`，建立带 `ControlMaster=auto` / `ControlPersist=600` 的复用连接，避免每个检查都重新握手。

服务器开工已在 `6131ea4`，仍按 Git 快进部署并重启确认；价格修正 `456cf5b` 拉取后再次重启，最终 PID 为 **308721**、服务 **active**、`NRestarts=0`。服务器根目录有 26 个旧 untracked 文件/目录，本次保留，未执行 `git clean` 或 `reset --hard`。同机其他站点配置未改动。

### 2.2 语料副本与验收

仅同步 reqai 自己克隆的副本；用户本机工作区不受影响。同步时版本：

| 来源 | 服务器路径 | 提交 |
|---|---|---|
| 项目文档 | `/home/ubuntu/corpus/snowmeet_ai_doc` | `d3251f9` |
| SnowmeetApi | `/home/ubuntu/corpus/SnowmeetApi` | `3c9dc278` |
| 微信小程序 | `/home/ubuntu/corpus/snowmeet_wechat_mini` | `023f7858` |
| 公众号 | `/home/ubuntu/corpus/SnowmeetOfficialAccount` | `4c9c0a6` |
| 支付宝小程序 | `/home/ubuntu/corpus/alipay_snowmeet` | `ed9c53d` |

业务笔记 `/home/ubuntu/corpus/business` 和静态结构 `/home/ubuntu/reqai/schema` 为只读源。**本次未重导 Snowmeet 生产库 schema，也未读取生产业务行数据、执行 DDL 或部署 SnowmeetApi。** 新代码被索引不证明生产库已执行对应迁移。

通过服务进程内 `POST /api/admin/sync?pull=false` 触发同步，鉴权 token 只在服务器内存使用。`sync_runs.id=1249` 于 **2026-10-02 06:48:13 UTC** 完成，状态 `ok`：959 扫描、0 改动、0 写入、0 错误、0 embedding tokens；此前 cron 已完成同一批源码更新，因此不是没有扫描。

独立复核 959 个有效文件的 SHA-256 与实际语料一致；有效片段 **2,792**、总量 **2,147,790 tokens**，无缺失向量、无维度错误。现有管理账号的只读检索请求返回 200，可找到：

- `Models/Staff/StaffBindCode.cs`；
- `sql/2026-10-01_staff_bind_code.sql`；
- `Services/StaffAccounts/StaffAccountService.cs`；
- `Controllers/StaffAdminController.cs`；
- `pages/staffadmin/bindcode/bindcode.js`；
- `pages/staffadmin/selfreg/selfreg.js`。

后续文档收尾提交尚待服务器定时同步拾取；以上数量对应此次语料验收时点，不代表永远固定。

### 2.3 域名澄清

开工按旧记录检查过 `snowmeet.goldenma.xyz`，该域名不可解析，不能据此判定 reqai 没有运行。用户随后明确入口为 `ai.snowmeet.top`；其 DNS 指向 `44.207.251.65`。从用户提供的 HTTP 入口请求，现有 Nginx 301 跳转到 HTTPS，最终页面与 OpenAPI 返回 200，TLS 校验通过。按用户要求使用 HTTP 入口，本次未新增证书或修改跳转配置。

环境里的旧 `BASE_URL` 尚为历史域名，但代码当前只声明此设置、未使用；不为此增加无关部署改动。

## 3. 默认模型与价格修正

用户截图中会话为 `#/s/5`，选中 Luna，却显示 `$1.25 / $10`。只读核实：

- DB 全局默认：`gpt-5.6-luna`，effort 空；
- env `CHAT_MODEL` 和 `UTILITY_MODEL`：同为 Luna；
- 会话 5 无单独覆盖，实际解析为 Luna；
- API provider 为 `api.openai.com`，不是另一个中转价表。

以下为 **2026-10-02 核对的标准短上下文（输入不超过 272K）、未缓存输入/输出价格，单位美元/百万 tokens**：

| 模型 | 原错误输入/输出 | 修正输入/输出 | 官方来源 |
|---|---|---|---|
| Luna | $1.25 / $10 | **$0.20 / $1.20** | [模型页](https://developers.openai.com/api/docs/models/gpt-5.6-luna) |
| Terra | $0.25 / $2 | **$2 / $12** | [模型页](https://developers.openai.com/api/docs/models/gpt-5.6-terra) |
| Sol | $0.05 / $0.40 | **$4 / $20** | [模型页](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |

修改 [配置](../../../reqai/backend/app/config.py) 中 `MODEL_WHITELIST`，并标注核价日期和适用条件。`PRICING` 从白名单派生；同一张表既供 `model-settings` API / 前端下拉显示，也参与 `cost_of()`、新 `usage_log.cost_usd` 和每日预算计算。后端更新后刷新页面即可，无需修改或重建前端。

新增 [费用回归](../../../reqai/backend/tests/test_pricing.py)，按 **100,000 未缓存输入 + 10,000 输出 tokens** 手算：Luna $0.032、Terra $0.320、Sol $0.600。修正前 3 项全部失败，修正后全部通过；避免使用超过 272K 输入的样例来验证短上下文价格。

提交 `456cf5b97116c425d9aa873c78ae5c3bd9bc5b02` 已推送，并通过服务器 Git 快进、服务重启上线。线上 `GET /api/admin/model-settings` 返回 200 和修正价格，默认模型及会话 5 未改变。

历史 `usage_log` 金额保留原值，不重算。当前估算仍将全部 prompt tokens 按标准未缓存价计算，尚未按缓存 token 或长上下文分段精确记账；reqai 金额是估算，不等同 OpenAI 实际账单。

## 4. 默认回答精简

用户要求「每次对话输出的内容相对冗长，可否精简一下」。原因包括共同提示词缺少默认长度目标、追问固定 5–10 条、冲突检查无冲突时自动续写完整 FSD。

调整 `base.md`、`chat.md`、`clarify.md`、`conflict.md`、`advise.md`：

- 普通回答通常 200–400 字；简单问题 1–3 句。
- 先回答本轮核心问题，再给必要依据。
- 后续追问只补充新增内容，减少重复背景。
- 追问每轮最多 3 个关键问题，不凑数量。
- 冲突检查默认只判定并给必要解法，不自动 FSD。
- 建议只列关键改动，不强制全套表格/空章节。
- 保留引用、真实冲突、缺乏依据的说明。
- 明确要求详细、完整清单或选择 FSD 时完整输出。

字数是软目标，不通过 token 上限截断回答；`fsd.md` / `project_fsd.md` 的完整结构未删除。冲突模式下明确要求完整 FSD 时也保留全部章节，未解决的阻断/需改造冲突仍先确认方案。

Luna 使用虚构资料进行真实 API 验收，不插入用户会话；调用费用经现有 `usage_log` 正常记录：

| 样例 | 旧回答字符数 | 新回答字符数 | 结果 |
|---|---:|---:|---|
| 一次性餐具是否等同食材 | 213 | 123 | 简短回答且保留引用 |
| 无冲突的低库存提醒 | 3,450 | 132 | 不再自动续写 FSD |
| 接续一段长回答追问工具 | — | 271 | 不重述整份方案 |
| 追问库存提醒需求 | — | 457 | 仅 3 个关键问题 |
| 开发建议 | — | 607 | 只列关键改动 |
| 显式 FSD 模式 | — | 3,985 | 完整章节齐全 |
| 冲突模式明确要求 FSD | — | 3,183 | 完整章节齐全 |

字符数包括英文标识符和 Markdown；不是中文字数硬上限，也不是所有问题的固定输出长度。另验收了修改 FEFO 规则的真实冲突样例，仍会报告冲突并要求确认。

提交 `56b59cd4c3fb8577a3a054530563bf432fc873c0` 已推送、美国服务器已拉取。`llm.prompt()` 每次读取文件并 `.strip()`，因此此次仅提示词变更无需重启；旧会话下一轮即可生效。上线复核五份原始文件哈希与本机、验收稿相同，运行时读取内容相同；模型和价格保持已核实值。服务 PID 仍为 308721，未中断其他站点。

## 5. 自动化验证及既有失败

- 既有管理员助手与语料相关测试：200 过、1 跳过。
- 新价格回归：3 过，修正前确认 3 败。
- 价格修正后完整后端：305 过、13 败、1 跳过。
- 同步前完整后端：302 过、同样 13 败、1 跳过。
- `95354a3` 的相关文件基线复跑，同样 13 败。
- 简洁提示词相关测试：81 过；最终补充后检索 25 过。

完整测试的失败名称一致，未因本次变更新增失败；**不能写成全套通过**。5 个文件测试依赖旧机器 `/Users/cangjie/source/snowmeet` 上的真实文件；8 个旧模型测试仍使用白名单已移除的 `o4-mini` / `gpt-4.1`。本次不修与用户目标无关的测试夹具。

既有失败完整名称：

```text
tests/test_files.py::TestSecrets::test_secret_file_refused
tests/test_files.py::TestSecrets::test_secret_not_even_listed
tests/test_files.py::TestReading::test_large_cjk_file_does_not_break_on_truncation
tests/test_files.py::TestReading::test_binary_refused
tests/test_files.py::TestReading::test_can_browse_deliberately_unindexed_dirs
tests/test_models_r7.py::TestWhitelist::test_effort_rejected_for_unsupported_model
tests/test_models_r7.py::TestWhitelist::test_bad_effort_value_rejected
tests/test_models_r7.py::TestWhitelist::test_effort_only_sent_to_supporting_models
tests/test_models_r7.py::TestPermissions::test_admin_can_set_global_and_per_session
tests/test_models_r7.py::TestResolution::test_session_override_wins
tests/test_models_r7.py::TestResolution::test_falls_back_to_global
tests/test_models_r7.py::TestResolution::test_effort_dropped_when_model_does_not_support
tests/test_models_r7.py::TestResolution::test_unsupported_combination_errors_rather_than_silently_dropping
```

本机测试显式设置临时 SQLite、空 `OPENAI_API_KEY`、测试 `SECRET_KEY`，不碰生产库。提示词验收才在服务器受控使用现有 Luna API。

## 6. 关键文件

| 文件 | 本次改动 |
|---|---|
| [reqai 配置](../../../reqai/backend/app/config.py) | 三款模型标准价格及来源日期 |
| [费用回归](../../../reqai/backend/tests/test_pricing.py) | 低于长上下文门槛的手算样例 |
| [共同提示词](../../../reqai/backend/app/prompts/base.md) | 默认精简与详细输出例外 |
| [问答](../../../reqai/backend/app/prompts/chat.md) | 聚焦当前问题，不自动设计 |
| [追问](../../../reqai/backend/app/prompts/clarify.md) | 最多 3 个关键问题 |
| [冲突](../../../reqai/backend/app/prompts/conflict.md) | 简短判定，显式要求才完整 FSD |
| [建议](../../../reqai/backend/app/prompts/advise.md) | 关键改动与实际风险 |
| [项目上下文](../CLAUDE.md) | 完成态、入口、验证与遗留 |

## 7. 学到的小知识与交接

1. **按实际入口验收**：旧域名失败不代表服务失败，HTTP 入口的既有跳转可保持。
2. **同步走运行中服务**：不要另跑独立 CLI 同步进程，既占重复索引内存又可能让在用 worker 索引不更新。
3. **提示词热读取**：只更新提示词无需重启；哈希对比须区分原始文件与 `.strip()` 后文本。
4. **验收器不要过度限制排版**：完整 FSD 的编号章节也有效；已修正只接受未编号标题的验收规则。
5. **FastAPI 路由盘点**：当前 `.routes` 可能包含 `_IncludedRouter`，不要假设每项都有 `.path`，使用 `app.openapi()['paths']`。
6. **本机 Python 证书库**：系统 Python 的 urllib 可能缺少 CA 根证书，本次公网复核改用正常 TLS 校验的系统 curl，没有跳过证书验证。
7. **end-work 只提交本次文件**：小程序 118 个既有改动和服务器旧 untracked 文件保留。

本次用户目标已上线，无发布阻塞。下次先用现有会话继续整理需求，按实际阅读体验决定是否还需微调；完整 schema 导出刷新、13 个旧测试夹具、门店枚举/匹配和帮助/主对话分开配置可另行安排。本次未复核或扩大旧业务上线待办，也未将其升级为本次 reqai 发布阻塞。
