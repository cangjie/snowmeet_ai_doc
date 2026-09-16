# 2026-09-10（跨夜至 09-11） reqai 上线收尾：部署 + Git 对齐 + OpenAI key 轮换 + 模型切 luna

本场从 `start-work` 开始，主线是把 09-10 下午做完但没上线的 reqai 管理员助手 v1 推到生产，随后按用户要求轮换 OpenAI key 并把模型从 sol 换成 luna。**本场只动 reqai 生产环境与配置，四个代码仓一行未改。**

## 1. 开场盘点与复盘

### 1.1 start-work 基线

- doc 仓 `pull --ff-only` → already up to date，HEAD=`c0d8b74`
- 五仓核查（skill 已扩为含 `reqai`）：工作区全干净；当时 SnowmeetApi ahead 13 / 小程序 ahead 9 / reqai ahead 8
- **快照会过期**：当时报的「ahead 13」是 20:06~20:11 之间的瞬时状态，20:11 另一端就 push 了。后来用 `git ls-remote` 查真实远端才确认 SnowmeetApi 与小程序其实已同步，只有 reqai 真的没推

### 1.2 用户问「今天下午 chatGPT 都做了什么」

41 个 commit / 4 仓 / 约 5400 行新增（15:25–20:06）。三层分工：reqai 只出查询计划与措辞（779 行）、SnowmeetApi 执行只读查询（3018 行）、小程序只执行固定跳转（1560 行）。开发走隔离 worktree 后 fast-forward 回主分支。

### 1.3 用户追问「浪费了多少工作量」

按 commit 归类 + 时钟时间归属（相邻 commit 间隔，>45 分钟的算中断）：

| 口径 | 加固/脱敏 | 核心功能 | 占比 |
|---|---|---|---|
| 新增代码行 | 1,868 | 3,432 | 33% |
| 时钟时间 | ~76 分钟 | ~81 分钟 | 29% |
| commit 数 | 14 | 10 | 48% |

**回答用户的结论：约 30% 浪费**（加固扣掉其中正当的会话隔离，加上验证记录/归档的反复重写）。加固那 1,868 行里 62% 是测试代码。时间分布比总量更说明问题：**18:21 全链路就已贯通**，之后 78 分钟全在 fix，且 `AdminAiController.cs` 被反复改了四次、`AdminAssistantService.cs` 三次，都是同一类问题分四轮才收敛。

## 2. 自然语言处理能力评估（只读审查，未改代码）

### 2.1 做得对的部分

- 11 字段白名单；`rent_status` 是 9 值 Literal 枚举；布尔/日期/`cell_suffix` 都有约束
- 模型不碰业务数据：planner 只出计划，finalize 只收聚合、收不到订单明细行
- 日期基准由调用方传入，prompt 明令「绝不能使用服务器日期」（reqai 在美国，不写就差一天）
- `replace` / `patch` 语义明确：显式 null 清除、省略保持原值

### 2.2 ⚠️ 门店（shop）是整条链路唯一软肋（**未修**）

| 字段 | 模型端约束 | 服务端匹配 |
|---|---|---|
| rent_status | 枚举写死 9 值 | 直接用 |
| cell_suffix | 正则 4–15 位数字 | 后缀匹配 |
| **shop** | **自由字符串，prompt 里没给门店清单** | **`shop.name == 输入` 精确相等** |

- 模型不知道门店叫什么，只能从用户原话抄；库里是「万龙服务中心」而用户说「万龙店」就匹配不上
- [`RentalOrderQueryExecutor.cs:39`](../SnowmeetApi/Services/AdminAssistant/RentalOrderQueryExecutor.cs) 抛「租赁门店不支持」→ 前端统一显示「暂时无法获得回答」+ 重试按钮，**用户看不到真因，重试永远失败**
- 讽刺的是 2026-08 那次改造刚把 `product.shop` 自由文本退役改成 `shop_id`，助手这条新链路又退回按门店名精确匹配
- 修法（半小时）：把 `shop.rent == 1` 的门店名列表塞进 planner prompt 当枚举 + 执行器加包含匹配兜底 + 匹配不上时把可选门店列进澄清 reply
- 其他限制：没有金额区间条件；`cell_suffix` 至少 4 位

### 2.3 多轮筛选怎么用

第二轮直接说「其中只看招待订单」即可——每轮都会把当前筛选发给模型，它输出 `mode=patch` + `is_entertain=true`，日期自动保留。最保险写法是「4 月的订单里只看招待的」（即使误判成 replace 也不丢日期）。自查：追问「当前的筛选条件是什么」会逐一列出全部 11 个字段。

**口径差异**：助手不填 `is_entertain` = 不限（**含**招待），而页面手点默认 `isEntertain: false`（**排除**招待），所以助手报的总数会比店员平时看到的大。

## 3. 用户实测发现「还是回操作说明」→ 定位为新版没上线

用户截图：问「只看招待订单」返回的是操作指引 + `[[C5]][[C17]]` 引用 + 「依据项目资料生成」——这是 page-help 文档问答的输出格式。结论：**三个仓一个都没部署/发布，手机上跑的是 09-07 旧版**，旧版没有 plan/finalize 链路，也没有查询上下文，做不到多轮 patch。

## 4. reqai 生产部署（本场核心）

### 4.1 前置核对

- SSH 通了（09-10 那场「连续超时」是间歇性的）
- 服务器 `backend/app/routers/` 里**确实没有** `admin_assistant.py`，`main.py` 挂载列表也没有它 → 新版确实没上线
- **昨天上传到 `deploy-backups/admin-assistant-v1/` 的两个文件 MD5 与本机 `95354a3` 逐字节一致**，不用重传

### 4.2 渐进式安装

内存紧（1.8G，`MemoryMax=700M`），所以先装文件但不挂载、import 验证通过再重启：

1. 备份 `main.py` → `deploy-backups/admin-assistant-v1/main.py.pre-admin-assistant`
2. 装两个文件；用服务自己的 venv 验证：`IMPORT_OK routes=2`，两个路由都在，依赖（`service_auth`/`retrieval`/`models`）全齐
3. `sed` 把 `"admin_assistant"` 加进 `_mount_frontend()` 元组
4. 重启 → `active`、内存 364/700MB
5. 验证：plan/finalize **401**（存在且要求 service token，不是 404）、page-help 401（既有功能没坏）、日志无 error、snowmeet 与 **ari 均 200**

## 5. Git 对齐：把「scp 直改」的债清掉

09-08 归档警告过「服务器工作区有 45 个未提交文件，直接 pull 会覆盖线上代码」。本场逐文件比对（58 vs 60 个代码文件）：

- **53 个完全一致**
- **4 个内容不同**：`main.py`（预期内）、`pyproject.toml`、`backend/.env.example`、`deploy/env.example` —— 差异**全部是「本机多、服务器少」**，且都是 `.example` 模板或依赖声明，真实配置在 `/etc/reqai/env`（不在 git 里）
- **1 个只在服务器有**：`backend/app/query_intent.py`

**孤儿文件的真相**：它是 `app/routers/query_intent.py` 的**早期误放副本**，两文件开头逐行相同；时间戳 11:07 vs 11:12 还原了当时的操作——先 scp 到错位置、5 分钟后重传到正确位置。`grep` 确认**无人引用**，`_mount_frontend()` 只扫 `app.routers.*`，它从未被加载过。

确认无可抢救内容后执行：全量备份（`deploy-backups/pre-git-align-20260910-132847.tgz`，268K）→ `git fetch` + `reset --hard origin/main`（`527b466` → `95354a3`）→ 删孤儿副本 → 重启。结果：**backend 未提交改动归零**（总数 47→26，余下全是根目录杂物），`rent-query-intent` 旧端点仍 401 活着，ari 200。

**以后 reqai 部署就是 `git pull && systemctl restart`。**

## 6. push reqai main

本机 `main` = `codex/admin-assistant-v1` = `95354a3`（下午就 fast-forward 合过），推送 `2541e8b..95354a3`。此前 8 个 commit 只存在于这台 Mac，而其中的代码已经跑在生产上。

## 7. OpenAI key 轮换

- key 只从环境变量 `OPENAI_API_KEY` 读（`config.py` → `llm.py`），数据库无覆盖值
- 备份 `/etc/reqai/env.bak-20260911-014447`；key 经 stdin 写入（`printf | sudo python3`），不进服务器进程参数
- 写入后 SSH 断了 20 分钟，靠后台 until 循环在 09-11 02:08:24 UTC 自动重启
- 验证：从 `/proc/<pid>/environ` 读**运行中进程实际加载的** key 首尾匹配；用它直连 OpenAI `models.list()` 返回 130 个模型；02:11 一条真实用户调用状态 done

## 8. 模型 sol → luna（用户指令）

### 8.1 先查清现状

模型解析顺序：数据库 `app_settings.model_defaults`（管理后台可改）→ 环境变量 `CHAT_MODEL`。线上 DB 无覆盖值，实际用 `gpt-5.6-sol`；调用日志 41 次成功调用全是 sol。

### 8.2 ⚠️ 发现 reqai 价格表是错的

我先按配置文件说「sol 最便宜」，用户质疑「最便宜的不是 luna 吗」，查官方定价后确认**用户是对的**：

| 模型 | 官方（输入/输出，每百万 token） | reqai 配置里写的 | 偏差 |
|---|---|---|---|
| gpt-5.6-luna | **$0.20 / $1.20** | $1.25 / $10.00 | 高估 6–8 倍 |
| gpt-5.6-terra | $2.00 / $12.00 | $0.25 / $2.00 | 低估 6–8 倍 |
| gpt-5.6-sol | **$4.00 / $20.00** | $0.05 / $0.40 | **低估 50–80 倍** |

（sol 官方页现价 $4/$20，第三方文章写 $5/$30，差额来自 8 月 21 日起的临时降价。）

**后果**：这张表喂给 [`llm.py:77`](../../reqai/backend/app/llm.py) 的 `DAILY_USD_CAP` 判断和管理后台「今日花费」。sol 期间**账面花费只有实际的 1/50~1/80，每日预算保护形同虚设**；切到 luna 后误差反向——账面偏高 6–8 倍，真实花费到上限 1/7 左右就会被拦。**此表尚未修正**（用户在我提议修复时直接发了 end-work）。

### 8.3 切换执行

帮助系统有两处调模型，必须一起换：主回答走全局默认；**检索前的问题改写**（[`retrieval.py:55`](../../reqai/backend/app/retrieval.py)）没传 model，落到 `UTILITY_MODEL`，且 `ENABLE_QUERY_REWRITE` 默认 true，每次提问都会跑。

执行：备份 `/etc/reqai/env.bak-20260911-022146-pre-luna` → env 的 `CHAT_MODEL`/`UTILITY_MODEL` 改 luna → `settings_store.set_model_defaults("gpt-5.6-luna", None)` 写 DB → 02:21:57 UTC 重启。

验证：进程内两个环境变量都是 luna、全局默认解析为 `('gpt-5.6-luna', None)`、**走应用自己的调用链真调一次 luna 返回「收到」**、端点 401、两站 200。

**副作用（已告知用户）**：模型设置是全局的，**reqai 自己的需求分析对话也一起切成了 luna**，没法只切帮助系统——要分开得给帮助系统单独加一个模型设置。另：已缓存的页面帮助仍是 sol 生成的答案，命中缓存不产生新调用。

## 9. 定位一个长期误判：SSH 超时是本地网络问题

全天 SSH 反复超时，一度连续 10 次失败。对照测试给出答案：

| 目标 | 22 端口 | 443 端口 |
|---|---|---|
| reqai 服务器 | ❌ 不通 | ✅ 200 |
| **github.com** | ❌ **也不通** | ✅ 200 |

**连 GitHub 的 SSH 都连不上 → 是这台 Mac 所在网络间歇性拦截出站 22 端口，不是服务器的问题。** 09-08/09-10 归档里记的「服务器 SSH 不稳」是误判。已写入本机 memory（`local_network_port22_blocked.md`）。绕过办法：切手机热点/VPN；git 走 SSH 可用 `ssh.github.com:443`；SSH 不通时可让用户从 AWS 控制台 EC2 Instance Connect 执行。

## 关键改动文件

本场**没有改任何仓库代码**，全部是生产环境配置与部署动作：

| 位置 | 改动 |
|---|---|
| `44.207.251.65:/home/ubuntu/reqai/backend/app/routers/admin_assistant.py` | 新装（后由 git reset 变为 Git 管理版本） |
| `.../backend/app/admin_assistant_protocol.py` | 同上 |
| `.../backend/app/main.py` | 挂载列表加 `admin_assistant`（后被 origin/main 正式版覆盖） |
| `.../backend/app/query_intent.py` | 删除（误放的孤儿副本） |
| 服务器 `/home/ubuntu/reqai` 整个工作区 | `reset --hard origin/main`，`527b466` → `95354a3` |
| `/etc/reqai/env` | `OPENAI_API_KEY` 轮换；`CHAT_MODEL`/`UTILITY_MODEL` → `gpt-5.6-luna` |
| reqai 数据库 `app_settings.model_defaults` | 写入 `{"model": "gpt-5.6-luna", "effort": null}` |
| `cangjie/snowmeet_reqai` | push `2541e8b..95354a3` |

## 未完成 / 待办

1. **reqai 价格表未修**（第 8.2 节）——预算保护一直不准，建议优先
2. **门店字段未加枚举与模糊匹配**（第 2.2 节）——自然语言查询按门店筛大概率失败且报错文案无用
3. **是否把帮助系统模型与 reqai 主对话分开**——待用户决定
4. 小程序未发布、真机验收未做
5. **本场最后的线上复核没跑成**：写归档时 SSH 又不通，无法确认 09-12 那场会话重新部署（`main@c5ab3ef`）之后 luna 设置是否仍然生效。env 文件与 DB 都在 git 之外，理应不受 `git pull` 影响，但**未经复核**。下次上机第一件事就核这个。

## 学到的小知识

1. **「已推送」要用 `git ls-remote` 查真实远端**：本地 `origin/*` 是缓存，start-work 报的 ahead 数可能几分钟后就过期。同理，写部署状态前必须实际连服务器核实——09-12 那场会话正是因此纠正了「reqai 线上未部署」的错误记录
2. **对生产做 reset 前，先逐文件比对内容而不是只看 `git status`**：45 个「未提交文件」听起来吓人，实际 53 个一致、4 个是服务器落后、1 个是误放垃圾，真正的风险为零
3. **孤儿文件看时间戳能还原事故现场**：两份同名文件差 5 分钟，就是「先传错位置再重传」的痕迹
4. **改生产配置走渐进路径**：先装文件不挂载 → import 验证 → 再挂载重启。任一步失败都不影响在跑的服务
5. **验证要看运行中的进程，不是配置文件**：key 和模型都是从 `/proc/<pid>/environ` 读的，才能证明「服务真的加载了新值」
6. **代码里写死的价格表会悄悄失效**：它不参与任何测试，错了也没人发现，却直接决定预算保护是否生效。凡是硬编码的外部价格都该标注来源日期并定期核对
7. **SSH 连不上先拿第三方主机对照**（`nc -z github.com 22`），别默认是目标服务器的问题
