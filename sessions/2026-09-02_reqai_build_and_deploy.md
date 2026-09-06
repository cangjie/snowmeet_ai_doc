# 2026-09-02 需求收集与分析系统 reqai：从零建成并部署上线（跨至 09-06）

新建独立项目 `reqai`（`/Users/cangjie/source/snowmeet/reqai/`，GitHub `cangjie/snowmeet_reqai`），
与 snowmeet 三个业务仓平级但独立。Claude.ai 形态的对话工具：碎片化中文需求进，结合项目
**真实的**代码、文档、生产库结构，产出带引用的冲突判定 / 开发建议 / FSD。19 次提交，
217 个测试，已部署到 https://snowmeet.goldenma.xyz。

**为什么做**：2026-04 手工做过一轮完整的需求分析（产物在 `request_analyze/`），
然后因为「复制粘贴的开销超过收益」停摆五个月。这个停摆本身就是产品需求。

---

## 1. 语料库：三次扩张，每次都是被实测推着走

### 1.1 起点：只索引 snowmeet_ai_doc（约 49 万 token）

按 `##` / `###` 分五族差异化切分：`CLAUDE.md` 拆成 context_core / current_state /
93 条按日期的 devlog；`sessions/` 整篇或按 `## N.` 切；specs/plans 按标题切。

### 1.2 第一次扩张：加代码 —— 因为 doc 是开发史不是规则库

**关键认识**：`snowmeet_ai_doc` 记的是「2026-08-14 改了 TicketController，因为 X」这类
**代码变更叙事**，而 obsidian 那 14 篇业务笔记又不全面。真正说得清「现在是什么」的是
**源代码本身**。

加入 `SnowmeetApi` / `snowmeet_wechat_mini` / `SnowmeetOfficialAccount`，后来补上漏掉的
`alipay_snowmeet`（只有 7 个 js，但它是**支付宝支付与雪票下单路径的唯一真相**）。

**代码按「成员」切而不是按段落**：C# 方法/属性、小程序 `Page({})` 属性。一个方法从中间
断开就没有意义了。

**排除的**：`.wxml`/`.wxss`（28 万 token 的标记与样式）、GB18030 编码表（10 万 token 纯数据）。

### 1.3 第二次扩张：生产库 schema

用户原本提议让美国服务器**只读直连中国生产库**。评估后**否决**：需求分析要的是 schema 和
枚举取值，不是行数据；行数据是 PII，跨境有 PIPL 合规成本；让 LLM 对生产库写即席查询有风险；
往返延迟 200ms+。

替代方案 `tools/dump_schema.py`：在**能连到库的位置**用只读账号导出 schema + 枚举分布为
markdown。导出 109 张表 / 3.8 万 token。最有价值的是枚举分布 ——
`order.type = 养护(15492)/租赁(11431)/零售(3855)/雪票(1626)/餐饮(300)/聚合(31)`，
**这些取值此前只散落在代码的字符串比较里，没有一处权威列举**。

另有一个写 FSD 时要留意的发现：**全库只有 3 个声明式外键**，表关系基本靠 `xxx_id` 命名约定维系。

### 1.4 索引 vs 权限：必须分开定

用户说「任何子目录都可以查看」。盘了一遍发现全量索引会毁掉检索：

- `alipay-sdk-net-all-master` 是 vendor 的第三方 SDK，**47,151 文件 / 125MB**，光它占语料 98%
- `/SnowmeetApi`、`/snowmeet_wechat_mini`、`/SnowmeetOfficialAccount` 是**旧 checkout**（落后 3~10 个月）
- **`wl_school_wechat_mini_core` 名字像小程序，remote 实为 `SnowmeetApi.git` 的另一分支** ——
  索引进去核心代码会被重复计 3 次

结论：**权限全开（后台只读文件浏览器可看任意目录），索引按清单**。去重**按 git remote
不按目录名**（上面那条就是反例）。排除理由连同清单写进 `config.CORPUS_EXCLUDED` 并在后台
显示，避免将来有人「顺手」加回来。

---

## 2. 七条定位规则

| | 规则 |
|---|---|
| R1 | 普通用户提零碎需求；复杂需求建 Project 攒 N 条，合成一份 FSD |
| R2 | **决策依据是代码和数据库，文档只答「为什么」** |
| R3 | 后台：管理员可看全部会话原文；FSD 导出 Markdown / Word |
| R4 | 权限全开，索引按清单 |
| R5 | **只能微信扫码登录**，无密码通道 |
| R6 | 手机号 `18601197897` 是唯一管理员，每次登录按手机号重算 |
| R7 | 模型与 reasoning effort 白名单，只有管理员能改 |

### 2.1 R2 的权威顺序（写死进提示词）

| 问什么 | 以什么为准 |
|---|---|
| 现在是什么（字段、接口、取值、既有实现） | **代码 + 生产库 schema** |
| 为什么当初这么设计（有意为之、不变量、踩过的坑） | 文档 |
| 文档与代码**不一致** | **以代码为准**，且这个不一致本身是必须上报的发现（`conflict` 模式里单列成一类「文档过期」） |

族权重相应反转：`schema 1.45 > code_rule 1.40 > code_model 1.35 > … > spec 1.15 > … > skill 0.80`。
检索预算的「事实池」（代码+schema）占 6 成，文档池保底 4 成 ——
全给事实池的话，冲突检查会把刻意的设计当 bug 报出来。

### 2.2 🔴 红线：reqai 对外界只读

用户明确要求「代码目录下的内容统统不许动、不写数据库」。**当时的实现正好违反着**：
`sync.py` 的 `_git_pull()` 对配置了 remote 的源跑 `git pull --ff-only`，而本机的源直接
指向用户的工作目录。

改为 `CorpusSource.readonly` 默认 `True`，git 走只读子命令白名单
（`rev-parse`/`remote`/`log`/`status`/`show`/`config`），`pull`/`fetch`/`checkout`/`reset`
一律 `PermissionError`。只有 reqai 自己 clone 的副本才可 `readonly=false`。

**实测**：记下 7 个源的整树指纹（路径+mtime_ns+大小）、HEAD、工作区状态，跑一次故意
不带 `--no-pull` 的完整 sync —— 七个源一字未变。

---

## 3. 五个对话模式

`chat` 问答 · `clarify` 追问 · **`conflict` 冲突检查** · `advise` 复用优先 · `fsd`

`conflict` 是核心：判定新需求是否撞上既有逻辑。关键是教会它**分清什么才算冲突** ——
新功能要写代码不是冲突，那是工作量；冲突是新需求与**已经成立的东西**矛盾。四类来源：
有意为之的决策 / 业务不变量 / 字段语义 / 发布耦合。**判定无冲突就直接续写 FSD**；
判定有冲突（阻断级）则**不出** FSD，因为前提还没定。

Project 需求清单：会话里「收录为需求」→ 条目管理（待确认/已确认/已排除）→ 冲突预检回写
→ 合成 FSD 落成一个可复查的会话。合成时 N 条需求**各自检索再 RRF 融合**，不拼成一个长
查询——拼起来主题被稀释，BM25 词频和 embedding 语义中心都会漂到「几条的平均」上。

---

## 4. 部署（09-06）

`44.207.251.65`（AWS us-east-1，Ubuntu 26.04 **aarch64**，Python **3.14.4**，MySQL 8.4.11，
nginx 1.28.3，1.8G 内存）。**同机正在跑 `ari.goldenma.xyz`**，全程避开。

### 4.1 勘察确认的关键事实

- **`mini.snowmeet.top` 从美国机可达**（HTTP 404 = 有响应只是没这个路由）→ 微信扫码登录可行。
  这是原计划里最大的未知。
- `api.openai.com` → 401（可达）
- 端口 **8000/8001/8002 全被占**（8000 是 nginx 自己的 default_server）→ reqai 用 **8003**
- **原本无 swap**，可用内存 590M，而 reqai 满载 336M → 必须先加 2G swap

### 4.2 执行顺序

备份 nginx → 加 swap → 建库建号 → clone 代码与语料 → 装依赖 → 配置 → 三个迁移 →
首次全量 sync → 起服务 → 传前端 → nginx server block + TLS → cron

**首次同步实测**：2055 块全部 embedding（1,713,760 tokens，约 $0.034），峰值可用内存降到
366MB、swap 只用 89MB，**无 OOM**。

### 4.3 验收

`schema_version=3`、2055/2055 embedding、`内存索引就绪：2055 块，dense=on`、
证书 `Verify return code: 0 (ok)`、reqai 内存 431MB（上限 700M）、OOM 0 次。
**`ari.goldenma.xyz` 全程 200，ari 的配置文件 0 处改动。**

---

## 关键改动文件

全部在 `/Users/cangjie/source/snowmeet/reqai/`（独立仓 `cangjie/snowmeet_reqai`）。

| 文件 | 改动 |
|---|---|
| `backend/app/corpus/chunker.py` | 五族差异化切分；`classify` 按源与路径判族 |
| `backend/app/corpus/code.py` | 代码按成员切（C# 方法 / JS Page 属性），零内容丢失 |
| `backend/app/corpus/store.py` | 内存索引（numpy 矩阵 + jieba BM25）；`readonly` 白名单；重建先释放后构建 |
| `backend/app/corpus/sync.py` | 增量同步；按 git remote 去重；只读源不执行任何 git 写命令 |
| `backend/app/retrieval.py` | 改写 → 稠密+稀疏 → RRF → 族加权 → 摘要/明细去重 → MMR → 分层预算 |
| `backend/app/wechat.py` | 微信扫码登录客户端（随机 nonce、120s TTL、一次性消费） |
| `backend/app/export.py` | Markdown / Word 导出，含引用附录与 CJK 字体修复 |
| `backend/app/prompts/*.md` | 10 个中文提示词，热加载 |
| `backend/migrations/*.sql` | 三个手写迁移，`schema_version` 到 3 |
| `deploy/*` | `setup.sh` / `reqai.service` / `nginx-reqai.conf` / `sync-cron` / `env.example` |
| `tools/dump_schema.py` | 生产库 schema 只读导出，三层 PII 防护 |

---

## 学到的小知识

1. **SQLAlchemy 的 `Row.t` 是自带属性**：`.label("t")` 之后取 `r.t` 拿到的是**整个 Row**
   而不是那一列，序列化直接 500。`count` / `index` / `tuple` 同理。已加全仓扫描测试禁用这几个别名。

2. **`usage` 是 MySQL 保留字**：SQLite 接受、MySQL 8.4 直接 ERROR 1064。手写 DDL 必须加反引号；
   应用侧不受影响，因为 SQLAlchemy 生成 SQL 时会自动加引号。**只有手写 DDL 会踩**。

3. **systemd 的 `EnvironmentFile` 不剥行内注释**：`FOO=0.6  # 说明` 会让值变成
   `"0.6  # 说明"`，pydantic 解析浮点失败、服务起不来。注释必须单独成行。
   （多行单引号包裹的 JSON 反而**能**正确解析，这点实测过。）

4. **裸 JSON 会被剥引号**：`CORPUS_SOURCES=[{"a":1}]` 经 systemd 或 shell `.` 读取后双引号
   消失，`json.loads` 崩在 import 阶段。必须**整体加单引号**。

5. **GitHub deploy key 只对单个仓有效**：服务器上那把是 `cangjie/ari` 的 deploy key，
   能 clone 公开仓（因为公开仓任何有效 key 都能读），但碰不到其他私有仓。
   账号级 SSH key 才能跨仓。

6. **MySQL root 未必是 auth_socket**：这台机 root 用 `caching_sha2_password`，`sudo mysql`
   连不上。Ubuntu 的标准维护账号 `/etc/mysql/debian.cnf`（`debian-sys-maint`，auth_socket）
   在 sudo 下可用。

7. **`rsync --delete` 不删被排除的文件**：需要 `--delete-excluded`。而且排除规则要写在
   `--include='*/'` **之前**，否则目录已被包含进来。

8. **BM25Okapi 对多数文档都含的词给负 idf**：按 `score > 0` 过滤会把稀疏检索通道**静默清零**
   （小语料或常见中文词就会触发）。RRF 只吃排名不吃分值，所以负分照样可用；
   该排除的是「与查询无任何词重合」的文档。

9. **MMR 排好的序不能再按分数重排**：`_fill_stratified` 末尾按分数排序，把 MMR 放在第 2 位
   的块打到第 12 位、直接掉出上下文。分层填充要保持传入顺序。

10. **摘要层与明细层去重要继承分数**：同一天的 devlog（摘要）与 session（明细）都命中时
    丢摘要留明细，但明细若留在自己较低的排名上，等于把一次高位命中降级。要继承
    `max(摘要, 明细)` 并重排。

11. **按字节截断会劈开汉字**：`data[:400000].decode("utf-8")` 对含中文的大文件会
    `UnicodeDecodeError`，被误判成「不是 UTF-8 文件」。要往回退最多 3 字节找完整字符边界。

12. **`.gitignore` 里 `corpus/` 不加锚点会匹配任意层级**：曾把 `backend/app/corpus/` 整个包
    忽略掉，六个核心模块两次提交都没进版本库。要写 `/corpus/`。

13. **给约束块留独立检索配额是错的**：预算留了就一定会被填满，把不相干的约束硬塞进上下文，
    等于暗示模型「这里有冲突」。且 RRF 分值动态范围太窄（rank 1 到 rank 20 只差约 25%），
    相对阈值筛不掉东西。改为温和加权，让相关度说了算。

14. **`lxml` 有 cp314 aarch64 Linux 轮子但没有 macOS 的**：所以 `python-docx` 在服务器上装得上、
    Word 导出可用，本机 Mac 反而不行。平台标签不同，不能从本机推断服务器。
