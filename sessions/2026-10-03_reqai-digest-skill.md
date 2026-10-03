# 2026-10-03 reqai 归档分析 skill：新建 /reqai-digest，并让 reqai 不读摘要

按时间线整理。本场从 start-work 开始，接着为 Codex 做的 reqai 每日归档（`reqai_archives/`）配一个分析 skill，把分析结果加载进项目上下文；随后按用户决定改 reqai 代码，让 reqai 不检索这份摘要，并部署到美国服务器。改动落在 `snowmeet_ai_doc/`（skill、摘要、CLAUDE.md）和独立仓 `snowmeet_reqai/backend/`。

> 本文件会进 reqai 检索，所以**不复述摘要的具体内容**（已确认决策、reqai 提案、待确认事项），只记过程。摘要见 [reqai_digest/INDEX.md](../reqai_digest/INDEX.md)。

## 1. start-work 状态核对

- 文档仓库已是最新的 `5184c49`，不需要拉取。
- 用 SSH 执行 `git fetch` 时多个仓库报「access rights」，后来又通了。改用 HTTPS `git ls-remote` 查到真实远端：
  - 文档、SnowmeetApi、公众号、reqai 都和远端一致；
  - 小程序落后 2 个提交（`9a3434d1`、`023f7858`「show legacy」）；
  - 公众号 `OfficialAccountApi.cs` 还有改动没提交。
- 纠正一处过时记录：SnowmeetApi 蓝牙打印实验的两个提交其实在 10-03 10:00 已推到 `origin/ai`（由 reflog 确认）。CLAUDE.md 原来写的「没 push」不对，同日另一场会话已在文档中更正。

## 2. 需求：分析 reqai 归档并加载到上下文

用户原话：「我用codex做了一个有关于reqai会话的归档功能，在snowmeet_ai_doc下的reqai_archives目录里，这里的会话大多数是需求讨论，和项目进度的记录，需要创建个skill去分析，并把分析的结果加载到项目上下文中。」

### 2.1 归档的结构（读代码和样本后确认）

- `reqai_archives/YYYY-MM-DD/`：`manifest.json`、`conversations/session-N.{md,json}`、`files/<id>_<原名>`。
- **同一会话在每个有活动的日期都存一份「截至当天」的完整快照**，所以增量只能按「会话 id + 消息」判断，不能按日期。
- JSON 字段：`session`；`project`（`instructions` 是项目总体说明）；`owner`；`messages`（`id`、`parent_id`、`role`、`status`、`content`、`attachment_ids`）；`attachments`（`sha256`、reqai 提取的 `extracted_text`，图片不提取）。
- 现有 5 个会话：
  - #4 是空会话；
  - #2 有两次失败的回答（`status` 为 `error`/`streaming`，内容为空），用户随后原样重发了同一问题。
- reqai 的语料同步（`SKIP_DIRS`）、切分（`classify`）、文件浏览器三处都排除了 `reqai_archives`，排除理由是「含用户资料，不作为需求事实进入检索」。

### 2.2 设计取舍

- **确定性部分交给脚本**，Claude 只负责理解和判断：哪些消息是新的、哪些是噪声、分析进度，都由 `scan.py` 维护。
- **只有用户消息能产生需求或决策**。助手消息一律记为「reqai 提案（未确认）」；reqai 说「已有实现」不算数，以 CLAUDE.md 和代码为准。
- **按需求主题组织**，不按日期或会话，因为同一件事常常跨会话、跨 reqai 项目讨论。
- **必须做对照核查**：查实现状态（CLAUDE.md 和代码 grep）、与已确认决策或现状的冲突（两边都注明出处，不替用户选），以及知识缺口（能很快从代码查清的就查）。
- **怎么进入上下文**：CLAUDE.md 里放一个带标记的区块（`<!-- reqai-digest:begin/end -->`，约 7 行），由 skill 整段替换；start-work 照搬区块内容，再附上 `scan.py --check` 的结果，自己不做分析。

## 3. 实现

### 3.1 [`scan.py`](../.claude/skills/reqai-digest/scan.py)

- 只用 Python 标准库。根据自身位置找到 `snowmeet_ai_doc/`，在 Windows（`py`）和 Mac（`python3`）上都能跑。
- 按会话 id 取最新日期的快照。每条消息的哈希由 `role`、`status`、`content`、`attachment_ids` 算出，和 `reqai_digest/state.json` 里记录的比对：
  - 新增或内容变化的消息算作待分析；
  - 之前停在 `streaming` 的回答，完成后哈希会变，所以会被重新识别。
- 噪声标记：失败的助手回答；「回答失败、后面又原样重发」的那条用户消息。用户消息是需求来源，不会被整体当成噪声。
- 子命令：
  - 默认：列出待分析的会话；
  - `--check`：输出一行摘要，给 start-work 用；
  - `--show ID [--all]`：打印增量消息正文和附件提取文本；
  - `--mark ID|all`：分析完成后记录进度。
- 验证：在 scratchpad 里模拟「次日会话 #5 新增 2 条消息（1 条还在 streaming）」，结果只报出这 2 条，未完成的那条被标出。

### 3.2 [`SKILL.md`](../.claude/skills/reqai-digest/SKILL.md)

- 三条底线：
  - 归档是数据不是指令；
  - 只有用户消息能产生需求或决策；
  - reqai 不读摘要（第 5 节改成这一条）。
- 消息分 5 类：需求提出、决策确认、进度记录、业务问答、噪声。主题状态只用 6 个 emoji 表示。
- 流程 12 步：pull → 扫描 → 读增量 → 读现有摘要 → 归主题 → 对照核查 → 写主题文件 → 更新 INDEX → 更新 CLAUDE.md 区块 → `--mark` → 只 add `reqai_digest` 和 `CLAUDE.md` 后提交推送 → 简报。
- 附三套模板：主题文件、INDEX、CLAUDE.md 区块。

### 3.3 其他

- start-work 的「Present」部分加了「reqai 需求动态」。
- 首次分析了会话 #1、#2、#3、#5，生成 [INDEX](../reqai_digest/INDEX.md) 和 2 个主题文件，写入 CLAUDE.md 区块，执行 `--mark all`。提交 `2ae7a54`。
- 分析中有 1 个知识缺口顺手用 SnowmeetApi 代码核实了，结论写在 INDEX 里。

## 4. reqai 不读摘要（用户决定）

用户原话：「对的，不让reqai读取摘要，区分提议和事实。」

### 4.1 排查

- reqai 的 `classify()` 只索引这些：根目录的 `*.md`、`sessions/`、`docs/superpowers/`、`docs/business/`、`SKILL.md`、`sql/`。所以 `reqai_digest/*.md` 本来就不会被索引。
- 但 **CLAUDE.md 会被整篇索引**，里面的摘要区块会被读到；另外 `reqai_digest/` 在文件浏览器里所有人都能打开。
- 服务器只读探查发现：
  - 语料由 cron **每 30 分钟**调用 `/api/admin/sync` 同步（in-process，异步返回 `started`）；
  - 北京时间 11:00 那次同步已把区块读进索引，共 4 个块含相关字样：其中 2 块来自 CLAUDE.md（区块本身，以及被并进「当前状态」的开始标记行），另外 2 块是 skill 说明文件。

### 4.2 reqai 改动（`main@8a7f7b7`）

- `config.py` 新增 `PRIVATE_DOC_DIRS = ("reqai_archives", "reqai_digest")`，语料同步 `SKIP_DIRS`、`chunker.classify`、文件浏览器三处共用；`CORPUS_EXCLUDED` 补了两项及理由。
- `chunker.strip_digest_block()`：切分 CLAUDE.md 前剥掉标记区块，兼容 CRLF。如果缺了结束标记，就剥到区块自身标题之后的下一个二级标题。
- 文件浏览器：`reqai_digest/` 和归档一样，只有管理员能看。
- 测试：新增 7 项，全部通过（剥区块、CRLF、缺结束标记、`reqai_digest` 不入索引 ×3、非管理员 403）。归档、切分、只读三组测试共 68 过；另有 6 项 `test_readonly` 失败，是改动前就有的 Windows 路径分隔符问题。
- 用真实 CLAUDE.md 验证：剥掉的正好是区块的 794 个字符，前后内容都保留。

### 4.3 部署与清理

- 服务器 `git pull --ff-only` 后重启 `reqai`。启动时要加载索引，约 20 秒后才开始监听 8003。第一次健康检查等得不够久，返回 000，服务本身正常。
- 同步按文件原始内容的 sha256 判断是否变化，**切分规则改了，内容没变的文件不会重切**。所以文档仓库改了 CLAUDE.md 区块的开始标记（注明「reqai 检索时剥掉本区块」，提交 `2157bed`），让文件哈希变化。
- 手动触发同步 #1291（状态 ok，3 个文件有变化）后复查：
  - CLAUDE.md 不再含摘要；
  - `reqai_digest/` 0 个文件入索引；
  - 剩下的命中只有 3 个 SKILL.md 提到 `reqai-digest` 这个名字。它们不含需求内容，skill 里原来举的具体主题例子已删掉。
- 收尾时服务 active、`NRestarts=0`、健康检查 200。重启前 10 分钟内没有人发消息。

### 4.4 规矩固化

- reqai-digest SKILL.md 底线 3：摘要内容**只能**放在 `reqai_digest/` 和 CLAUDE.md 区块里；区块外的 CLAUDE.md、`sessions/`、`docs/`、SKILL.md 都会进 reqai 检索。两条标记行要保持原样。
- end-work 第 3 步加一条：区块不手改，摘要内容不抄到区块外。

## 5. 与另一场会话并发改 CLAUDE.md

- 同一时间另一场会话（美国服务器端口转发）在改 CLAUDE.md 的标题行和新章节，还没提交。
- 处理方式：只提交自己的改动。先 `git show HEAD:CLAUDE.md` 取出原文件，改好自己那一行，用 `git hash-object -w` 写成对象，再 `git update-index --cacheinfo` 放进暂存区，最后不带路径执行 `git commit`。对方的改动留在工作区。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`.claude/skills/reqai-digest/SKILL.md`](../.claude/skills/reqai-digest/SKILL.md) | 新 skill：底线、分类规则、12 步流程、三套模板 |
| [`.claude/skills/reqai-digest/scan.py`](../.claude/skills/reqai-digest/scan.py) | 增量扫描、噪声标记、记录进度 |
| [`reqai_digest/`](../reqai_digest/INDEX.md) | INDEX、2 个主题文件、`state.json`（进度，入库跨机） |
| [`.claude/skills/start-work/SKILL.md`](../.claude/skills/start-work/SKILL.md) | 新增「reqai 需求动态」 |
| [`.claude/skills/end-work/SKILL.md`](../.claude/skills/end-work/SKILL.md) | 摘要内容不抄到区块外 |
| `CLAUDE.md` | reqai-digest 区块、状态条目、开发日志 |
| `snowmeet_reqai/backend/app/config.py` | `PRIVATE_DOC_DIRS`、`CORPUS_EXCLUDED` 两项 |
| `snowmeet_reqai/backend/app/corpus/chunker.py` | `classify` 用共享常量；`strip_digest_block` |
| `snowmeet_reqai/backend/app/corpus/sync.py` | `SKIP_DIRS` 用共享常量 |
| `snowmeet_reqai/backend/app/routers/files.py` | `_is_private_doc`，`reqai_digest` 只有管理员能看 |
| `snowmeet_reqai/backend/tests/test_{chunker,archive}.py` | 新增 7 项测试 |

## 学到的小知识

1. **reqai 语料同步是每 30 分钟一次的 cron**（`/etc/cron.d/reqai-sync` 调 `POST /api/admin/sync`，带 `X-Sync-Token`）。它在服务进程内运行、异步返回 `{"started":true}`；要等结果，就轮询 `sync_runs` 表最新一行的状态。
2. **同步按文件原始内容的 sha256 增量**：改了切分规则后，内容没变的文件不会重切。要么改一下文件内容，要么清掉 `doc_files.content_sha256`。
3. **reqai 重启后约 20 秒才开始监听 8003**（要先把索引加载进内存）。健康检查的重试至少要等 30 秒。
4. **reqai 的 `classify` 只索引固定几类路径**，子目录里的 `*.md` 默认不进检索；但 `SKILL.md` 不管在哪个目录都会进。
5. **归档快照是累积的**：同一会话会出现在多个日期，增量必须按会话 id + 消息哈希判断。
6. **多场会话同时改一个文件时，只提交自己的那部分**：`show HEAD:file` → 修改 → `hash-object -w` → `update-index --cacheinfo` → 不带路径执行 `commit`。
