# Snowmeet 雪季上线测试方案（Copilot 执行版）

日期：2026-09-30。输入：[系统功能说明](2026-09-30-system-feature-inventory.md)、当前五个仓库、现有测试和运行器。目标：验证实际业务规则，产出可复现的缺陷与覆盖报告。本文是执行方案，不代表下述业务用例已经实现或通过。

配套：[Copilot 启动指令](2026-09-30-copilot-test-prompt.md)、[用例索引](2026-09-30-copilot-test-cases.json)。先读本文，再按索引逐项执行；索引由本文第 6 章的用例表生成。

共170条主用例（P0 92、P1 76、P2 2），其中12条D类人工验收；一条主用例可能含多个参数和执行层，实际子例数会更多。索引是待执行目录，不是170条通过记录。

## 1. 执行范围与当前基准

### 1.1 代码快照

| 仓库 | 当前分支 / HEAD | 工作区与范围 |
|---|---|---|
| snowmeet_ai_doc | main / dc2cec6 | 功能说明和本方案；本方案为新增文件 |
| SnowmeetApi | ai / 18e0601a | 后端、静态后台、聚合支付 H5；项目实际目标框架 net9.0 |
| snowmeet_wechat_mini | ai / 0c712574 | 另有 50 个既存未提交文件改动；必须测试当前工作区，不能 reset/checkout 丢弃 |
| SnowmeetOfficialAccount | ai / 4c9c0a6 | 公众号接口、事件处理；独立 EF 模型，与主后端共用业务表 |
| reqai | main / 6131ea4 | 本机 D:\source\snowmeet\snowmeet_reqai；独立项目，不在 ai 目录内 |
| alipay_snowmeet | 工作目录现状 | 独立的支付宝页面；按文件哈希留存基准，不假设有 Git 仓库 |

本方案覆盖功能说明 4.1～4.9、5.1～5.16、全部 35 条历史回归点及第 6 章疑点。覆盖静态检查、规则、隔离库持久化、前端交互与人工验收。无实现的功能（例如外卖平台自动采集、接待入口的扫码占位功能）不编造通过结果。

### 1.2 已核对的文档差异

| 编号 | 文档或旧记录 | 当前证据 / 执行口径 |
|---|---|---|
| DIFF-01 | 页面清单含旧页面，历史数字 101 | 当前 app.json 为主包 80 页 + payment 1 页 + fnbinv 12 页，合计 93。每次运行重新枚举注册页；附录页面清单不能充当唯一真源 |
| DIFF-02 | AI 仅支持租赁数据查询 | utils/adminAiDomains.js、四个列表页的 applyPageIntent、Startup.cs 的四个查询执行器已支持租赁/养护/零售/雪票。测试四域；线上 reqai 是否同版本另列待验 |
| DIFF-03 | 示例可直接运行食材 HTTP 冒烟脚本 | run_fnb_http_smoke.py 导入 run_fnb_sqlserver_integration.py，后者读取 config.sqlServer，要求源库 snowmeet_new，并在同一服务器建删测试库。禁止直接执行或 import 这两个脚本 |
| DIFF-04 | LocalDB 运行器“本地安全” | tools/windows_test/run_integration_localdb.py 确实不读生产库，但会 CREATE/ALTER/DROP DATABASE、执行迁移，不符合本文 DDL 限制，交负责人使用，Copilot 不调用 |
| DIFF-05 | 命令里的 tests/*.test.js 可直接交旧 Node 运行器 | run_tests.js 自己不展开通配符；PowerShell 必须枚举文件后传完整路径，见第 4 章 |
| DIFF-06 | 食材“员工可以入库；店长才能盘点过账” | 已有食材入库允许员工；入库时新建食材需店长。FnbStocktakeController.CreateSnapshot 也要求店长，SaveCount 允许同店员工，不能把创建快照也测成员工成功 |
| DIFF-07 | 切换前端域名即可连本地 API | app.js 按 https:// 拼地址；部分图片/公众号/上传/支付/WebSocket 有独立地址。仅改 requestPrefix 或点“选择环境”不能证明所有流量已隔离 |
| DIFF-08 | 命令行 dotnet 不在 PATH | 本次可定位到 C:\Program Files\dotnet\dotnet.exe；同时有可用 Node。下一台机器重新探测，不能沿用机器假设 |

代码用于确认路径、协议和现状；代码本身不能证明业务行为正确。文档、历史要求与代码冲突时记录差异。明确的金额守恒、资产不重复扣减、无越权等要求仍作为断言，不能照错误实现修改预期。未拍板的门店恢复、人事菜单规则记 NEEDS_DECISION。

### 1.3 本次编写时实际验证

| 检查 | 本次结果 | 限制 |
|---|---|---|
| 当前小程序 tests/*.test.js | 167 通过，0 失败，0 跳过 | Node 规则/页面模拟测试；不是开发者工具或真机结果 |
| 后端安全子集 | 353 通过，0 失败，0 跳过 | 排除 FnbSqlServerIntegrationTests、AdminAssistantControllerTests；命令见 4.2 |
| 页面注册统计 | 80 + 1 + 12 = 93 | 本次统计；完整资源/菜单扫描仍属待执行用例 |
| B/C/D 业务验证 | 本次未执行 | 没有启动业务 API、访问生产库、支付、发消息或下第三方订单 |

排除 AdminAssistantControllerTests 是因为其中有 SQLite EnsureCreatedAsync；按功能说明“DDL 不由 Copilot 执行”的字面限制，本轮也没有运行这些内存建表测试。后续可由负责人运行，或明确调整测试权限后纳入，不能悄悄省略。此前“后端 362、LocalDB 24、HTTP 77/80”是历史记录，不能记成本轮结果。构建输出有既存 nullable/xUnit 与包告警；保留原始日志，另列环境/依赖事项，不把它们说成业务用例失败。

### 1.4 功能说明章节覆盖表

范围写法 `REC-01..REC-11` 包含两个端点之间全部编号。通用鉴权AUTH、基础检查BASE和非功能COMMON也适用于所有相关模块；下表给各章节的主要业务用例。

| 原章节 | 功能 | 主要用例 |
|---|---|---|
| 4.1 | 登录与会员识别 | AUTH-01..AUTH-08, REC-01, MEMBER-01..MEMBER-03 |
| 4.2 | 订单支付退款数据 | PAY-01..PAY-10, RENT-07, MAN-01..MAN-03 |
| 4.3 | 通用结算 | PAY-05, PAY-08, PAY-11, MAN-01..MAN-03 |
| 4.4 | 顾客扫码支付 | PAY-01..PAY-04, ALI-01, MAN-01 |
| 4.5 | 支付回调与生效 | PAY-04, PAY-09, TICKET-11, CARD-09, MAN-01, MAN-03, MAN-05 |
| 4.6 | 退款 | PAY-06, PAY-10, CARE-14, CARD-05, MAN-02, MAN-04, MAN-05 |
| 4.7 | 身份核验 | PAY-07, CARE-07, MAN-03, MAN-06 |
| 4.8 | 公共组件 | COMMON-01..COMMON-07, AI-07, MAN-08 |
| 4.9 | 普通链接扫码 | MAN-06 |
| 5.1 | 接待开单 | REC-01..REC-11 |
| 5.2 | 租赁 | RENT-01..RENT-17, MAN-02 |
| 5.3 | 养护 | CARE-01..CARE-16, MAN-03, MAN-04, MAN-08 |
| 5.4 | 雪票 | SKI-01..SKI-04, MAN-11 |
| 5.5 | 零售 | RETAIL-01, RETAIL-02, WEB-02 |
| 5.6 | 次卡季卡 | CARD-01..CARD-09, RENT-13, RENT-14, MAN-05 |
| 5.7 | 会员 | MEMBER-01..MEMBER-07 |
| 5.8 | 储值 | DEPOSIT-01..DEPOSIT-03, RENT-12, MAN-02, MAN-03 |
| 5.9 | 优惠券 | TICKET-01..TICKET-11, CARE-16, MAN-07 |
| 5.10 | 食材 | FNB-01..FNB-28, MAN-08..MAN-10 |
| 5.11 | 聚合支付 | WEB-03, TICKET-11, MAN-12 |
| 5.12 | 员工 | STAFF-01, AUTH-03, OA-02, MAN-12 |
| 5.13 | 管理员AI | AI-01..AI-08, MAN-12 |
| 5.14 | 公众号 | OA-01, OA-02, TICKET-03..TICKET-05, MAN-07, MAN-12 |
| 5.15 | 后台网页 | WEB-01, WEB-02, RETAIL-02, MAN-12 |
| 5.16 | 支付宝 | ALI-01, ALI-02, PAY-01..PAY-04, MAN-01 |

## 2. 执行限制与环境闸门

### 2.1 功能说明 0.3 原文（其中章节号指原功能说明）

1. **本地启动的后端默认连接生产库。** `SnowmeetApi/config.sqlServer` 指向生产 SQL Server（`snowmeet_new`）。没有换成隔离库之前，不得调用任何会写数据的接口。
2. **不得发起真实支付或退款。** 微信支付、支付宝都是真实商户号，钱是真的。支付、退款相关用例一律归入 D 类，由人工小额（0.01 元）执行。
3. **不得调用万龙雪票下单。** 万龙雪票支付成功后，后端会向第三方「自我游」真实订票并扣预存款（见 5.4）。
4. **不得触发群发推送。** 食材过期提醒 `FnbMaterial/PushExpireAlert` 默认发给企业微信全员；公众号客服消息会真实发给顾客。
5. **不改服务器本地配置并提交。** `config.sqlServer`、`config.fnbAlertReceivers` 等文件不入 git，改了会影响他人。
6. **数据库结构变更（DDL）不由 Copilot 执行**，只由负责人执行。
7. **生产环境的任何写操作都要人工确认后再做**，并用测试员工账号操作（测试订单会被自动标记，见 3.4）。

补充执行解释：A/C 中的支付金额、按钮、状态转换使用对象夹具或完全截获的假响应；这些是逻辑断言，不得据此调用真实支付/退款接口。D 仅生成检查清单，不自动执行。`is_test=1` 只是业务标记，不能隔离资金、库存、消息和第三方订票。0.01 元也不能保证自我游不扣真实票款；雪票购买单独由负责人决定，不能作为自动冒烟。

### 2.2 执行类型和证据等级

| 标记 | 执行内容 | 证据与限制 |
|---|---|---|
| S | 代码/页面/路由/模型静态核查 | 文件路径、行号、扫描报告；不等同实际接口通过 |
| A | 单元、纯规则、受控内存对象、假外部客户端 | 测试名、输入、独立预期、断言日志；不建库、不执行 DDL、不连外部系统 |
| B | 已备妥本地隔离 SQL Server 的真实 API/事务 | HTTP 请求响应 + 新 DbContext/新连接独立读回 DB 差异；不可用 SQLite/InMemory 替代 SQL Server 事务结论 |
| C | 开发者工具/受控浏览器界面 | C-M=全部业务网络 mock；C-L=批准的本地后端。截图、控件值、请求轨迹；mock 不能证明后端通过 |
| D | 真机、真实渠道、设备或线上部署人工验收 | 负责人结果、版本、时间、脱敏凭证；Copilot 始终标 MANUAL_REQUIRED，直到人工证据返回 |

表中 A+B、A+C、B+C 等表示所有列出层均需结果，不能任选一层就将整条标 PASS。C 默认 C-M，使用 C-L 必须通过 B 闸门。S 的基准数字变动先报告版本差异，不把旧数字永久写死成产品要求。

### 2.3 B 类放行条件（任一未满足，只阻塞 B 和依赖 B 的 C-L）

1. 负责人已建立专用本地数据库、应用所需 schema，并提供脱敏的环境确认；Copilot 不调用创建/迁移/删库脚本，不读生产 schema 充当测试准备。
2. 测试运行配置只接受明确指定的 `(localdb)\MSSQLLocalDB` 或负责人批准的本机 SQL Server 实例；DB 名必须等于本次 manifest 的名称且以 `snowmeet_fnb_test_` 开头。名称前缀不能替代服务器身份核验。读回服务器和 DB_NAME() 并与批准配置逐项比对。
3. API 启动工作目录是新的测试专用目录，里面的 config.sqlServer 只写本机隔离连接；不覆盖业务仓根目录的真实配置。Util.GetSqlServerConnectionString 和 Util.GetDbContext 都按当前工作目录读文件；仅设置 ASPNETCORE_ENVIRONMENT/ConnectionStrings 环境变量不够。
4. 只复制启动必需且已审查的公开配置、程序文件；不复制生产 config.*、支付证书、私钥、真实 openid/session。测试工件目录不能让 Web 静态文件服务公开连接串。
5. 应用进程只能连接本地测试库及本地 stub；微信、支付宝、自我游、公众号、企业微信、OCR、reqai 外部请求默认拒绝。此代码存在静态帮助方法和直接 new HttpClient，单换 IHttpClientFactory 不足；需实际验证进程级网络隔离或覆盖全部调用点的拦截。没有能力验证时 B 标 BLOCKED_ENV。
6. API 仅监听回环地址；使用精确到方法+路径的请求允许列表。外部交互方法（支付、退款、订票、推送、真实 OCR 等）不加入。GET 也可能写库，如 /core/SkiPass/ReserveSkiPass/{productId}，不能把所有 GET 当只读。
7. 本地库已有所需表、索引、FK、默认值、视图；缺项输出给负责人，不自动执行 EnsureCreated/Migrate/DDL。旧 LocalDB 脚本只准备食材部分表，不能据此宣称租赁/会员全链路可测。
8. 夹具和清理都限定本次 runId：只对本地人工建立的库做 DML；不得 TRUNCATE、DROP 或批量清空未知行。保留本次失败数据供复查，负责人最终回收库。

负责人提供的环境确认存 `environment-approval.json`（不含密钥）：`approvedBy, approvedAt, serverAlias, database, schemaVersion, allowedApiBaseUrl, outboundIsolationEvidence, seedAllowed, cleanupScope`。提供这些信息是环境前置条件，不是 Copilot 自动请求生产权限的理由。

### 2.4 C 类放行条件

- miniprogram-automator 目前不是 package.json 的既有依赖；先探测工具与 CLI 自动化能力。不可把“计划使用”写成“已经装好”。安装仅进入独立测试工具目录并固定版本，不改业务 lockfile。
- 使用测试专用项目副本，保留业务源码和既存未提交改动；另建测试 bootstrap。必须在 App.onLaunch、wx.login、任何 wx.request 之前安装拦截；先启动原项目、后连接 automator 再改 URL 不合格。
- C-M 拦截 request/uploadFile/downloadFile/connectSocket/login/payment、扫码、OCR、BLE、订阅/分享等；未登记 URL 或调用立即失败，绝不放行到真实地址。App 包装 wx.request 的逻辑也必须纳入探测。
- C-L 的所有请求（含图片、公众号和 WebSocket）必须出现在允许列表；本地 HTTP 与代码强制 https:// 的差异用测试副本适配，不能改正式代码来“过测试”。H5/支付宝页面同样检查首次加载请求。
- mock 返回结构来自 DTO/现有接口契约，不能根据页面期望反向捏造“总是成功”的返回。请求参数、方法、次数和失败分支也要断言。
- 没有开发者工具自动化能力时，继续完成 S/A；C 标 BLOCKED_TOOL 并提供可人工执行步骤，不能用纯 Node 页面模拟冒充 C。

## 3. 分阶段执行与停止条件

| 阶段 | Copilot 工作 | 进入下一阶段的条件 |
|---|---|---|
| E0 快照 | 读取指令、记录五仓分支/HEAD/dirty、已存在改动清单、版本/工具、runId | 没有覆盖用户文件；范围明确 |
| E1 既有基线 | 执行 4.1、4.2，完成 S 用例；建立逐条状态账本 | 失败也保留并继续独立模块；先区分工具故障与业务断言失败 |
| E2 补自动化 | 按 P0→P1→P2 编写缺失 A；复用测试框架，新增测试名含用例 ID | 测试真实调用被测规则，不复制一份同算法自测；没有安全接缝则记录缺口 |
| E3 隔离库 | 通过 2.3 后，实现无建库/删库的本地运行器、夹具、B 用例 | 每个写接口都有独立 DB 读回，运行环境证明完整 |
| E4 界面 | 通过 2.4，先 C-M 再允许的 C-L | 真正编译与操作；控制台/网络/截图留证 |
| E5 人工清单 | 输出 D、部署/配置待确认、业务待拍板清单 | 不等待 D 而停止其他自动化 |
| E6 报告 | 汇总全部用例状态、35 条回归映射、缺陷、阻塞、重跑命令 | 无遗漏 ID；未执行/跳过不计通过 |

发生访问生产/未知外部网络、环境身份不符、非本 runId 写入时，立即停受影响进程并保存证据；不要为修复测试环境自动改生产配置。单个用例失败不自动中断所有其他安全测试。

本轮默认只写测试、测试夹具、测试运行器、报告。发现业务缺陷先用最小用例固定并记录，不自行修改生产业务实现；用户另行要求修复时才开修复轮。禁止为了通过而降低断言、改金额预期、删失败用例、提交已有用户改动。默认不 commit/push/deploy。

## 4. 可直接运行的基线命令与待实现工具

以下为 PowerShell，在 workspace 根目录执行。示例绝对根路径对应本机；其他机器只改 Workspace。命令异常时记录退出码，不将依赖未安装当业务失败。

### 4.1 前端既有规则测试

```powershell
$Workspace = 'D:\source\snowmeet\ai'
$RunId = 'qa-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$RunId += '-' + ([guid]::NewGuid().ToString('N').Substring(0, 6))
$RunDir = Join-Path $Workspace ('snowmeet_ai_doc\artifacts\testing\' + $RunId)
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
$NodePath = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $NodePath) { $NodePath = 'C:\Program Files (x86)\Tencent\微信web开发者工具\node.exe' }
if (-not (Test-Path -LiteralPath $NodePath)) { throw 'BLOCKED_TOOL: 找不到 Node' }
$JsTests = @(Get-ChildItem -LiteralPath (Join-Path $Workspace 'snowmeet_wechat_mini\tests') -Filter '*.test.js' -File | Sort-Object Name | ForEach-Object FullName)
if ($JsTests.Count -eq 0) { throw '没有枚举到测试文件' }
$NodeVersion = & $NodePath --version
$NodeVersion | Set-Content -LiteralPath (Join-Path $RunDir 'node-version.txt') -Encoding UTF8
Push-Location (Join-Path $Workspace 'snowmeet_wechat_mini')
try {
    if ([int]($NodeVersion.TrimStart('v').Split('.')[0]) -ge 18) {
        & $NodePath --test @JsTests *> (Join-Path $RunDir 'frontend-baseline.log')
    } else {
        & $NodePath (Join-Path $Workspace 'snowmeet_ai_doc\tools\windows_test\run_tests.js') @JsTests *> (Join-Path $RunDir 'frontend-baseline.log')
    }
    $JsExitCode = $LASTEXITCODE
    $JsExitCode | Set-Content -LiteralPath (Join-Path $RunDir 'frontend-exit-code.txt')
} finally { Pop-Location }
```

Node 16 兼容运行器仅支持简单的 test(name, fn)，不会完整实现新 Node 的 hooks/mock/subtests。新增测试需要这些能力时使用 Node 18+，不要让不支持的用例静默丢失。读取完整日志的末尾计数和退出码；预期历史基线是 167，但新增用例后数量会增加。

### 4.2 后端无需 DDL 的基线

```powershell
$DotnetPath = 'C:\Program Files\dotnet\dotnet.exe'
if (-not (Test-Path -LiteralPath $DotnetPath)) { throw 'BLOCKED_TOOL: 找不到 .NET SDK' }
& $DotnetPath --info *> (Join-Path $RunDir 'dotnet-info.txt')
$BaselineFilter = 'FullyQualifiedName!~FnbSqlServerIntegrationTests&FullyQualifiedName!~AdminAssistantControllerTests'
Push-Location (Join-Path $Workspace 'SnowmeetApi')
try {
    & $DotnetPath test 'SnowmeetApi.Tests\SnowmeetApi.Tests.csproj' --no-restore --nologo --filter $BaselineFilter --logger 'trx;LogFileName=backend-baseline.trx' --results-directory $RunDir *> (Join-Path $RunDir 'backend-baseline.log')
    $BackendExitCode = $LASTEXITCODE
    $BackendExitCode | Set-Content -LiteralPath (Join-Path $RunDir 'backend-exit-code.txt')
} finally { Pop-Location }
```

本次此命令子集为 353 通过。没有 restore 缓存时先记环境阻塞；获准下载依赖后只 restore 对应测试工程，再重跑。不要用 `--no-build` 跑可能过期的 DLL。不要直接 `dotnet run` 启动仓根业务后端。新增任何测试前复核是否新增数据库/网络副作用；原过滤器不能永久保证未来所有新测试安全。

### 4.3 B 运行器应实现的接口（尚不存在，不能直接复制运行）

建议新增到 `snowmeet_ai_doc/tools/qa/`，工具语言使用 Copilot 所在环境可用的 Node/.NET/Python，固定依赖；不要为了凑命令假定已有实现。运行器须支持下列能力：

- `preflight`：解析环境确认，校验本地 SQL Server 和 DB_NAME、所需 schema、网络阻断、API 实际连接；只生成脱敏报告。
- `seed`：在已建库内用参数化 DML/EF 创建第 5 章夹具，输出逻辑名→ID 映射；有冲突立即停止，不覆盖陌生数据。
- `run --cases <IDs>`：仅允许已审查的路由；每个请求 30 秒上限；长批次记录独立超时；无自动无条件重试。并发用例显式控制 2/5/10 并发，默认不超过 10。
- `readback`：新连接读回数值、valid、归属、日志和库存；保存写前/写后差异，保留 SQL 参数的脱敏版。
- `cleanup --run-id <id>`：只处理 manifest 记载且确认属于本次的夹具 DML；有失败或关联不明时保留，输出给负责人。不得带建库/删库/迁移开关。

负责人完成建库后，原 FnbSqlServerIntegrationTests 可直接以过滤器运行，连接放子进程专用 `SNOWMEET_FNB_TEST_SQLSERVER`，绝不打印连接串。该测试类自己只校验库名前缀，调用它之前仍必须执行本文服务器核验。原脚本的场景可借鉴；不能通过 import 借用其初始化。

### 4.4 API 测试落点与外部边界

先从 Controller 的 Route/HttpGet/HttpPost/参数绑定以及 DTO 生成 `route-contract.json`；同一业务的旧、新接口不能盲猜统一前缀。记录字段大小写、query/path/body、响应 envelope、缺参/无权行为。Swagger 只读下载用于对照，不遍历调用所有 action。

| 模块 | 实际测试落点 | 边界 |
|---|---|---|
| 租赁 | /api/Rent/SaveRentRecept、/api/Order/PlaceRentOrder、/api/Rent/UpdateRentalDayChargesByStaff/{rentalId}、RentController 装备/追加操作 | 确认具体签名；调用会收款/退款/生成支付单的方法前停在规则或 UI mock |
| 养护 | /api/Care/CalcCareCharge、/api/Care/SaveCareRecept、/api/Order/PlaceCareOrder、WriteoffCareOrder 相关规则 | 生效可能发券/消息，只有已证明外部调用被隔离的非资金本地分支可进 B |
| 身份 | /api/PaymentIdentity/*、mini_session/员工身份解析 | 准确核对 GET/POST；真实平台换 code/手机号解密放 D |
| 食材 | /api/FnbCatalog、FnbInventory、FnbRecipe、FnbKitchen、FnbStocktake、FnbReport | 以控制器及契约文件的后续日期补充为准；PostReceipt/CreateAndServe 等用真实本地 DB |
| 雪票 | /core/SkiPass/*，特别 ReserveSkiPass/{productId} | 自动化只做静态、对象规则和 UI mock；下单、AutoReserve、支付回调都不调用 |
| AI | /api/AdminAi/AskAdminAssistantByStaff、Services/AdminAssistant/ | IReqaiAdminAssistantClient/HTTP handler stub；不自动消费线上模型或调用线上数据库 |
| 公众号 | SnowmeetOfficialAccount/Controllers/OfficialAccountApi.cs | 事件内容用合成 XML/对象验证；外发微信请求全部 stub。真关注/消息放 D |

支付成功、退款回调可测试被拆出的纯处理规则/受控 stub，但不能直接向线上或包含真实 SDK 的业务实例 POST 伪回调。没有可隔离接缝时记 BLOCKED_ENV/NOT_IMPLEMENTED_TEST，不自动重构业务代码。

## 5. 夹具、独立预期与证据规则

### 5.1 通用夹具目录

所有名字、编码、请求号绑定 runId。用独立本地合成身份，不借用生产员工 28/31/34 的 session。生产“测试账号”只留给 D 的负责人。

| 夹具 | 明确定义 |
|---|---|
| ID | G=未绑定会员会话；M1=有 cell/姓名性别/资产会员；M2=另一个会员；M0=姓名性别空会员；MC=只有 contact 的会员；MM=已合并会员。合成 session 含有效、过期、valid=0、未知、类型不匹配 |
| STAFF | 同店 S100/S200/S300/S1000、S199/S201 边界、离职/未到任/valid=0 员工、其他店 X200/X300、base_shop_id 为空员工；完整 staff_social_account/social_account_for_job 链及任职窗口；微信与 wecom 两类 |
| SHOP | SA/万龙服务中心、SB/崇礼旗舰店、SC/餐饮测试店（合成 ID，名字用于现有业务分支）；订单门店和当前选择门店可不同；价格不同用于发现串店 |
| RENT | 双板/鞋的主项 + 杖附件；无码品类、无价格品类、多品类槽位；编码 R01 正常、R02 租赁中、R03 已更换。散客和会员各一张草稿；2 天租金/超时费/减免；8 个状态的独立订单 |
| MONEY | 金额按十进制/分比较：已收押金 500，租金 100，超时 20，赔偿 30，减免 10，应收 140，应退 360；两笔可退支付 300+200。储值已付租金另设 140，避免重复补回；纯对象夹具不代表真实支付 |
| CARE | 双板品牌 A/长度 160、有照片与无照片、历史装备；SA 单项 80/双项 120/加急单项 100/双项 150；SB 单项 90/双项 130且无加急价；两非雪季类型；任务进行中/只剩发板/全完成 |
| CARD | 租赁/养护 × 次卡/季卡；次卡总 10 已用 0/1/10；季卡 total=null、care_project_count=1/2、今天已用/未用、已绑定/未绑定；已退卡；微信/支付宝/现金/店员赠卡来源 |
| COUPON | 模板 12/16 及不允许转赠模板；有效/过期/已用/valid=0；模板四业务；固定截止/启用 N 天/永久；一口价 70、折扣 0.8、立减 20；多个分享人/批次/接收人 |
| FNB | 原料 flour(g)、milk(ml)、egg(piece)，半成品 dough(g)；散装批 B1=300g 到期 D+1、B2=500g 到期 D+3；密封 2袋×500g；过期/销毁/用尽批次；菜 A 每份 flour100g+milk50ml，半成品每产 1000g 耗 flour600g |
| FNB-V | requestId 固定与新建两组，rowVersion 当前/旧值；盘点前后库存；入库/出餐时间 D-599秒、D-600秒、D-601秒；同店本人/他人/店长 |
| AI | 四域合法 plan/action，缺字段/未知字段/跨域字段/未知动作/超长文本/注入文本、返回超时、旧员工迟到响应；固定查询数据，禁止依赖真实模型随机输出 |
| UI | 0/1/50/51/101 行分页；320/375/414 宽度、长姓名/长金额/空图片；成功、业务失败、HTTP 404/500、超时、乱序、用户取消响应 |

本地只有所需 schema 时先 seed 可测模块，其他模块 BLOCKED_SCHEMA。角色权限不得只改页面上的 title_level 冒充服务端身份。金额夹具需与实际字段含义逐项核对；实现用 double 的地方也以分级容差断言，不能把不相等金额当相等。

### 5.2 可手算的断言样例

- 租赁 MONEY：未退款时应退 360；已实退 100 后剩余 260；未支付时应退 0；已通过储值扣完 140 后应退 500；相同储值结果重复渲染仍为 500。
- 多支付分配 300+60=360 合法；300+59.99、300+60.01、301+59、负数、NaN/Infinity 均不合法。检查每笔上限和总和两条约束。
- 雪票纯金额：每日单价 100，数量 1/2/3 的正确总额 100/200/300；源码当前会出现 100/400/900，应记录缺陷，不能实际调用 ReserveSkiPass 来证明。
- FEFO：B1 300g+B2 500g，需 400g，应扣 B1 300+B2 100，剩 0+400；过期、销毁、未开封批不参与出餐。需求 900g 时实际最多 800g，欠 100g，库存不负。
- 入库成本：200g×0.02元/g=4元；出库按批次成本守恒；库存数量/金额与流水合计分别校验，不用页面汇总代替。
- 低库存：最近入库 1000g 默认线 100g，可用 99/100 报警、101 不报警；固定线 200 优先按固定模式；开封/盘盈不改变“最近一批入库或制作”基数。
- 日期：上海营业日，UTC 审计时间；2026-01-31+1月→2026-02-28，2028-01-31+1月→2028-02-29；不修改系统时钟。纯测试注入时间；HTTP 用相对当前日期夹具并记录实际时间。

### 5.3 每条用例通用步骤

1. 验证所需类型闸门，准备全新夹具，记录初始状态/预期（不能运行后现算“预期”）。
2. 执行表中操作；负向/边界参数逐组跑，单独生成子例。请求模板从当前 DTO 取字段并保存证据。
3. A 断言规则结果；B 同时断言 HTTP 状态、业务 code/形状、DB 新连接读回、没有副作用；C 断言控件/交互/请求数量并截图。读取异常也算失败或阻塞，不能吞掉。
4. 对幂等用例重放相同请求、重复点击或重启后重试；对其他业务不擅自循环重试。并发出现 500 后即使重试成功仍记录首次失败。
5. 留存证据，更新账本。写后返回 200/code=0 但数据库没变必须 FAIL（Startup 全局 NoTracking 是本项目重点）。

默认证据键：S=source，A=test_log，B=http+db_before+db_after，C=screenshot+console+network，D=manual_record。不存在的证据不能用占位文件充数。每条表里的每个独立断言都须有结果，复合场景展开 `ID#参数值`。

## 6. 逐项执行用例

列定义：ID 稳定不变；P0 为雪季主流程/资金资产权限，P1 为重要业务和食材一致性，P2 为辅助体验。食材如本次不发布，应由负责人记录范围排除，不能直接从报告删掉。

### 6.1 基础、资源与路由（落点：app.json、admin.js/wxml、Controller、现有 tests）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| BASE-01 | P0 | S | UI | 枚举主包/分包全部 93 页，验证 js/json/wxml 存在、JSON 可解析、usingComponents 可解析；wxss 可按框架合法省略。输出全部路径，既有外部组件单列 |
| BASE-02 | P0 | S+C | STAFF | 按角色遍历菜单，去掉 query 后核对注册及文件，再点所有可见入口；6 个历史死入口逐项出结果，不因“已知”放过 |
| BASE-03 | P0 | S | UI | 提取前端 /api、/core、动态拼接与跨公众号调用，映射后端路由/方法/签名；原 6.2 每条单列；未解析动态 URL 记待核对，不误报成缺失 |
| BASE-04 | P0 | A | UI | 运行全部既有 JS 测试，记录文件数、测试数、退出码；零用例即失败；新增数与原 167 区分 |
| BASE-05 | P0 | A | ID | 运行 4.2 后端子集；记录所有排除类及原因，不能宣称后端全套完成 |
| BASE-06 | P1 | S | FNB | 比对 EF 模型和仓库迁移字段/类型/索引，不连接生产；输出 care取消、order储值、退卡、券分享、食材、AI日志必需结构清单交负责人 |
| BASE-07 | P0 | S+C | UI | 对当前未提交清理逐项查引用；共用雪票选择/付款落地/租赁价格入口能打开，失效雪场参数落首个有效雪场，无缺模块编译错；不测试已下线业务 |
| BASE-08 | P1 | S | ID | 审查运行器及所有新增测试的数据库/网络/进程副作用；禁止脚本不被 import，C 首次启动无真实请求；输出闸门证明 |

### 6.2 会话与权限（落点：StaffController、PaymentIdentityController、FnbAccess、会员/券/AI 控制器）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| AUTH-01 | P0 | A+C | ID | wx.login 成功/失败、MemberLogin 失败/超时分别模拟；loginPromise 均结束，失败清旧身份；未注册登录不产生“已注册”假状态 |
| AUTH-02 | P0 | B | ID | 正常/空/随机/过期/valid=0 session 调所测接口；无效会话不读出他人数据、不写库、不 500。Fnb 明确 code=2，其余按实测契约 |
| AUTH-03 | P0 | B | STAFF | 同接口替换离职、任职未开始、失效员工和类型不符 session；不取得员工权限；发现当前代码允许则记录越权，不改预期 |
| AUTH-04 | P0 | B+C | STAFF | 会员管理 199/200、合并 200/300、养护价 200/300、AI 199/200 分界；菜单与直接 API 两端核对，隐藏按钮不能代替接口鉴权 |
| AUTH-05 | P0 | B | STAFF | Fnb 同店员工、同店店长、跨店 300、无基地店矩阵；跨店高级别仍 code=3，无成本字段泄露 |
| AUTH-06 | P0 | B | ID | M1 请求 M2 订单、资产、券、次卡详情/修改；逐接口校验归属，拒绝且原数据不变；员工入口另用授权身份正向对照 |
| AUTH-07 | P0 | B | STAFF | 请求伪造 staffId/memberId/title_level/shopId，服务端只信会话推导的员工与授权；Fnb 微信/wecom 等价权限，支付宝 session 不误作后厨员工 |
| AUTH-08 | P1 | A+C | STAFF | 员工 A 发请求后换 B、退出重登、session 轮换；A 的迟到成功/失败不覆盖 B 页面和 AI 条件，退出清本地敏感状态 |

### 6.3 接待与租赁开单（落点：pages/admin/reception、components/reception/rent_recept_form、RentController）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| REC-01 | P0 | B+C | ID,SHOP | 空信息散客开租赁；11位/国际号命中 M1，contact-only MC 不匹配，MM 不回流；回填姓名性别且不覆盖手动新输入 |
| REC-02 | P0 | B+C | RENT | 连续快速改5次+网络延迟/乱序，草稿保存串行、只建1个订单；最终完整字段等于最后输入，结算等最后保存结束 |
| REC-03 | P0 | B+C | RENT,SHOP | 找回草稿→改日租金→加套餐→退出重入；数据真正保存，金额/附件/门店不丢；SA草稿在SB选择下恢复另记门店显示差异（KD-05） |
| REC-04 | P0 | A+B+C | RENT | 三租赁模式逐次切换并保存重载；start_date持久化、atOnce为bool非null；延时=明天00:00，其他=今天当前时分 |
| REC-05 | P0 | A+C | RENT | 遍历分类/编码/名称/模式/日期缺失、noNeed/noCode组合；提示优先级和结算禁用正确；禁用状态点击不发请求 |
| REC-06 | P0 | B+C | RENT | 套餐多份、多品类、附件，无价格品类修改租金；每槽正确显示分类，全部收费/附件保存重载不丢 |
| REC-07 | P0 | B+C | RENT | 搜索编码/名称，非正常物置灰；重复编码/同件并发加入两个草稿→验证最终发放不重复占用，失败不产生部分明细 |
| REC-08 | P1 | A+C | RENT | 无码物品切换有附件/无附件分类来回3次；旧附件移除，正确重建，主品类必填，无孤儿项与重复附件 |
| REC-09 | P0 | B+C | MONEY,RENT | 改押金/租金弹窗取消、确认、0、小数、负数、超长输入；净额/减免/总计一致；无价格配置也能持久化合法新租金 |
| REC-10 | P0 | B | RENT,SHOP | 草稿valid=0→PlaceRentOrder生成正式号与押金明细；同一草稿重复提交及两个独立草稿并发，不能重复生效或生成相同正式号；按已批准本地无渠道分支执行 |
| REC-11 | P1 | C | RENT | 分类/时间排序、左滑取消与删除、返回恢复；切业务不串用卡资产；接待“扫描条码”占位提示如实记录能力缺口 |

### 6.4 租赁详情、计费与列表（落点：rent_order_detail、rent_append、unreturned、Models/Order/Order.cs）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| RENT-01 | P0 | A+B+C | RENT | 分别构造8状态；按未付/未起租/在租/部分还/全还/部分退/全退/关闭验证，归还但实退0必须全部归还；关闭优先级与未付金额边界一致 |
| RENT-02 | P0 | A+B+C | RENT | 改第1天租金/超时/减免，第二天不变；清超时到0；新连接读回valid和金额，core_data_mod_log记录实际动作 |
| RENT-03 | P0 | A+B+C | RENT | 免除首/末/唯一计租日再取消免除；三类费用valid翻转、原金额保留、无重复行；恢复同金额仍有效；时间用装备记录兜底不退回未开始 |
| RENT-04 | P0 | B+C | RENT | 发放→暂存→重新发放→归还→设未归还；两视图操作同一实体结果一致，rent_product状态同步；重复动作不重复发放/归还记录 |
| RENT-05 | P0 | B+C | RENT | 更换为兼容/不兼容品类；成功保留历史，被换下项置灰不计件且不显示操作；失败新旧物状态不变 |
| RENT-06 | P0 | A+B+C | MONEY | 改赔偿30→50后应收160、应退340；页面立即重算订单级汇总；刷新与服务端读回一致，不能用旧order汇总值 |
| RENT-07 | P0 | A+C | MONEY | 已付/未付/部分付/已退对象分别算押金可退；校验5.2手算；超出配置押金的实收不被全计为可退押金 |
| RENT-08 | P0 | A+B+C | RENT | 部分/全部归还时间，最晚归还作为结束时间；只免除收费不能冒充归还；noNeed/已更换项不阻止正确结算 |
| RENT-09 | P0 | A+B+C | RENT | 招待开/关；商品小计0/恢复，列表毛租金可见；订单总应收随之变化且无重复减免 |
| RENT-10 | P0 | A+B | RENT | 未发放/已发放/暂存/已全部归还分别执行本地续租规则，同一天重复执行；只已发放或暂存计租且每天一笔；不得调用线上批量续租 |
| RENT-11 | P0 | A+B | MONEY,RENT | CloseOrder三条件逐个为假及全真；缺未归还、应退非0、欠费任一不得关；已付款且满足条件可关，无实际退款调用 |
| RENT-12 | P0 | A+C | MONEY,ID | 储值付租金勾选→未核验/错会员/核验成功/余额不足/余额0；未授权不进入扣款，成功预览全押金，取消回滚预览，无0元储值记录请求 |
| RENT-13 | P0 | A+C | RENT,CARD | 仅含雪板/鞋商品按商品×天核销，不按装备件数；全部归还才可；勾选/取消只是预览，无扣卡请求；无应退款时确认核销按钮正确 |
| RENT-14 | P0 | A+C | MONEY,CARD | 租赁卖卡价小于/等于/大于退款+抵租金额；算退款或补差；未到账/取消/失败不发卡核销；储值不得作为补差方式；重复成功响应只显示1笔销售 |
| RENT-15 | P0 | B+C | RENT | 追加套餐/单品/无码→草稿保存→删除；不补押金的本地确认分支生效一次；需补押金用C mock成功/失败；全退对象使未确认草稿作废，不删已确认项 |
| RENT-16 | P1 | B+C | RENT,UI | 列表全部筛选及两两组合；分页0/50/51/101行，跨页不重漏；详情返回保留页码/筛选并刷新，金额与标签一致 |
| RENT-17 | P1 | B+C | RENT,ID | 未归还按分类/订单/手机号聚合，缺手机号不把不同顾客乱合；查编码/姓名/手机号；跳转只展开目标rentItemId并滚动 |

### 6.5 支付、退款、身份与公共订单（落点：settle、两端payment_entry、PaymentIdentityController、OrderController）

自动化只测试纯计算、受控身份接口和 UI mock；真实资金/预下单/关单/回调都在 D。B 身份接口也须通过全部外部隔离检查。

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| PAY-01 | P0 | A+C | MONEY | 同订单两笔支付P1成功300/P2待付200，分别扫码；微信与支付宝均显示所扫支付ID的金额、状态、有效性，旧码作废时明确提示 |
| PAY-02 | P0 | A+B+C | ID,MONEY | 身份direct/direct_to_scanner/choose_identity/care_member_required/error逐项；陌生人不能替用养护权益；本人扫码不报无效身份 |
| PAY-03 | P0 | A+C | ID | 正常支付与代付分支、手机号授权同意/拒绝/超时；拒绝后按当前产品规则允许的路径继续；提交前不更改订单归属，代付标记及手机号展示脱敏 |
| PAY-04 | P0 | A+C | ID,MONEY | 模拟微信/支付宝成功、失败、取消、重复通知、错误订单/金额；成功规则恰好生效一次，失败不转归属/发卡/发券；微信openid及支付宝payerid不得为空；缺隔离接缝则标测试缺口 |
| PAY-05 | P0 | A+C | MONEY | 切换微信/支付宝/其他方式；旧待支付失效，撤单失败禁止新方式；扫码状态按等待→扫码→支付中→已收款/取消，旧轮询不得覆盖新支付 |
| PAY-06 | P0 | A+C | MONEY | 多笔退款用5.2合法/差1分/超单笔上限/负数矩阵；仅全归还可提交，储值部分不进入原路退款分配；禁用时点击不得发请求 |
| PAY-07 | P0 | A+B+C | ID | VerifyWechatIdentity用M1/M2/无会员/过期session；只本人能将wechat_unverified置1且新连接读回；staff轮询必须鉴权，不能任意查看他单 |
| PAY-08 | P0 | A+C | MONEY | 0元且已生效订单显示已收款；0元未生效权益单仍要求核验；支付结果跳租赁/养护对应详情，继续开单回首页 |
| PAY-09 | P0 | A | ID | 五个生效入口分别测M0与已有资料M1，补全只填空不覆盖；用纯处理规则/stub调用链；无法隔离入口不得标通过 |
| PAY-10 | P0 | A | MONEY | payment_refund.state=1、refund_id非空、两者皆无、重复回调/失败退款对象矩阵；实退只计有效已发起口径，无重复累计，金额不可负或超付 |
| PAY-11 | P1 | A+C | MONEY | 页面离开、后台、重进，轮询计时器/Socket释放；两页并开不串单；网络断开可重试且不重复发起资金动作 |

### 6.6 养护（落点：care_recept_form、CarePricingRules、CareController、care_order_detail）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| CARE-01 | P0 | A+B+C | CARE,ID | 新/历史装备，照片与品牌+长度矩阵；两者都无不能结算，历史带回正确品牌长度；非雪季无会员拒绝 |
| CARE-02 | P0 | A+B | CARE | 修刃/热蜡/双项/机打蜡/刮蜡×加急×两店；按5.1价格，SB缺加急回退普通价；改商品名称仍同价，热蜡默认刮蜡无重复计费 |
| CARE-03 | P0 | A+B+C | CARE | 客户端篡改0元/低价、并发快速变服务项；CalcCareCharge与PlaceCareOrder服务端重算一致；最后输入生效且不重复建草稿 |
| CARE-04 | P0 | A+B+C | CARE,COUPON | 券规则一口价→折扣→立减优先级；跨店配置和无配置回退；手动减免大于券减免时保留，失效/已用/异业务券不选 |
| CARE-05 | P0 | A+C | CARE,CARD | 次卡/季卡选中价0、与券互斥；单项/双项、机打蜡升热蜡/修刃补差；今天已用不可选；绑定装备回填锁定 |
| CARE-06 | P0 | A+B | CARE,CARD | 本地无渠道的季卡规则：首次完整装备绑定、不完整不绑定；当天重复使用拒绝；季卡不扣total但每次写记录；已退卡不可核销 |
| CARE-07 | P0 | A+C | CARE,ID | 0元招待/质保直接生效与0元储值/卡/券待核验区分；核验取消不核销；支付宝权益单需微信核验，不能靠付款方式绕过 |
| CARE-08 | P0 | A | CARE,CARD,ID | 模拟顾客支付归属变化后的卡核销，重新检查卡实际持有人/订单归属；允许路径不静默漏核销，冲突必须明确拒绝，不能扣别人的卡 |
| CARE-09 | P0 | B+C | CARE | 本地任务链按服务项构建，无遗漏/重复；开始/结束/不足60秒确认/强行中止权限；越步骤或已完成重复提交不新增任务 |
| CARE-10 | P0 | B+C | CARE | 安全检查默认历史值、手改未提交→补传照片/轮询刷新，输入不丢；保存后新连接读回；上传失败不出空白照片 |
| CARE-11 | P0 | A+C | CARE | 取消弹窗输入原因后立即点扫码（不先失焦）、失焦再点、空白原因、关闭重开；非空产生正确mock请求，空白不提交；记录KD-03是否复现 |
| CARE-12 | P0 | B+C | CARE | 取消/正常发板状态资格；全完成或只剩发板不得取消；本地已审查无消息分支验证原因必填、角色/凭证失败不改变状态；四核验方式外部部分放D |
| CARE-13 | P1 | B+C | CARE | 非雪季立等/寄存数量横幅、寄存/快递/柜分支、快递单号；保存重载一致，careId深链只展开目标 |
| CARE-14 | P0 | A+C | CARE,MONEY | 订单退款默认取消原因，0可退禁用；非0校验金额/备注；模拟500明确报错不显示成功；真实退款成功与“不报500”由D验证 |
| CARE-15 | P1 | B+C | CARE,UI | 订单/未完成/未发板列表筛选、分页、标签质/非/券与当前任务一致；已取消不混入正常待做队列（若规则不明确先记录差异） |
| CARE-16 | P0 | A+B+C | CARE,COUPON | 扫券内容为纯券码；同会员自动选券、异会员确认换顾客、取消不换；错误/失效/非养护券拒绝，价格和资产切换同步 |

### 6.7 次卡与季卡（落点：punchcard_*、Models/Rent/PunchCard*、RentController、MemberAdminController）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| CARD-01 | P1 | B+C | CARD,SHOP | 商品业务×卡型四组合，名称/价格/次数/项目数/规则/收款门店必填边界；季卡total为null，次卡正次数；上下架/停用正确 |
| CARD-02 | P0 | A+C | CARD,ID | 新顾客无会员号购买→手机号授权成功/拒绝；拒绝不下单，成功可到确认页；付款前不发卡，失败/取消不发卡，重复成功仅一次 |
| CARD-03 | P0 | A+B | CARD,SHOP | 收款门店与使用门店区分：商品配置SA收款不限制在SB合法使用；避免将shop_id误当使用范围；资金渠道选择仅对象规则验证 |
| CARD-04 | P1 | B+C | CARD | 查询全部卡型包含季卡；我的卡、员工查看使用明细、销售列表分组数量一致；已退款灰色且每个选卡入口都排除 |
| CARD-05 | P0 | A+C | CARD | 自助退款资格：从未用+微信/支付宝可申请，已用/现金/赠卡/已退均不可；页面显示正确原因且非法点击不调用退款 |
| CARD-06 | P0 | A+B | CARD | 本地纯资产使用服务/规则重复核销同商品同日，不双扣；余次0拒绝；租赁商品天数与使用记录一致；不同季卡当天不互相误锁 |
| CARD-07 | P1 | B+C | CARD | 店员发卡权限200/199、商品失效/卡型不匹配；成功发放1张且关联会员/发放员工，错误无半成品记录 |
| CARD-08 | P1 | B+C | CARD,CARE | 季卡改绑定品牌/长度有权限且读回持久化；其他会员不能改；重新开单带回新装备；历史使用记录保留 |
| CARD-09 | P0 | A+C | CARD,MONEY | 租赁卖卡与顾客自购回调先后/重复/超时后重试；卡、销售记录、核销记录的数量守恒，失败不出现已发卡状态；对应D验证真实结果 |

### 6.8 会员、储值与零售（落点：MemberAdmin、Deposit、retail_*、Mi7Order、相关模型）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| MEMBER-01 | P1 | B+C | ID,UI | 姓名/手机号/业务多选/标签多选/分页组合；已合并会员不显示；cell与contact查找口径不同且没有重复会员行 |
| MEMBER-02 | P1 | B+C | ID | 新手机号注册、已有号重复注册、非法/国际号；礼包逐项失败时正确显示每项结果，不重试已经成功项；无手机号的身份不能误创建空号会员 |
| MEMBER-03 | P0 | B+C | ID,STAFF | 店长编辑姓名性别/联系方式/标签，普通员工直接API拒绝；cell换绑与contact补充按现有规则独立，查找命中不串会员 |
| MEMBER-04 | P1 | B+C | ID | 标签人数随增删变化；有人使用时不能删除；合并标签不丢会员且不重复关联，目标等于源拒绝，空标签可删除 |
| MEMBER-05 | P0 | B | ID,CARD,COUPON,MONEY | 只在隔离库合并M1→M2：订单、储值、龙珠、次卡、券逐类计数和金额前后守恒；M1失效，旧手机号转contact；不遗留可再消费资产 |
| MEMBER-06 | P0 | B | ID,STAFF | 合并自我/不存在/已合并/权限200/并发重复；拒绝或幂等完成，任一失败不部分迁移；同库另一套公众号EF查询不误复活源会员 |
| MEMBER-07 | P1 | B+C | ID,CARD,COUPON | 会员资产与近期订单各业务tab、储值/次卡/券/龙珠汇总；总额等于明细，点击跳正确业务详情，会员变更后旧响应不覆盖 |
| DEPOSIT-01 | P0 | B+C | ID,MONEY | 隔离库充值五类型、七色米单号、备注和金额；0/负/多小数拒绝或明确规范化；成功流水、账户和会员可用余额一致，读回非假成功 |
| DEPOSIT-02 | P0 | A | MONEY,ID | 储值足额/差1分/0/负金额/重复订单规则；余额不得负或双扣；0元不生成支付记录；不调用真实Order/PayWithDeposit |
| DEPOSIT-03 | P1 | B+C | MONEY,UI | 新旧储值列表/详情/资金流水、顾客我的储值；充值行类型/七色米号/备注，消费行订单号；总额-已消费=可用，跨会员拒绝 |
| RETAIL-01 | P1 | B+C | MONEY,UI | 零售普通/招待/租赁附加三型筛选；实收按deal_price、不用标价替代；订单详情改备注/明细/图片后读回，mi7_code可追踪 |
| RETAIL-02 | P1 | B+C | UI | 仅本地导入合成七色米文件：正常/重复/缺列/坏金额/异常编码/空文件；校验导入行数与金额，重复不双入；错误行和成功行的事务策略必须可解释 |

### 6.9 优惠券（落点：TicketController、ticket_*、coupon_admin、现有 Ticket*Tests）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| TICKET-01 | P1 | A+B+C | COUPON | 模板四业务、三有效期策略互斥；固定日、启用N天、永久含跨日边界；一口价/折扣/立减合法区间；错误配置不保存 |
| TICKET-02 | P0 | A+B | COUPON,ID | 新发券valid=1、归属正确；过期/已用/无效/模板业务错不出现在开单选券列表；有效期精度按实际DateTime口径验证 |
| TICKET-03 | P1 | B+C | COUPON,STAFF | 员工发券三路径使用本地外发stub：记录staff和渠道；同模板同人同日固定码限1，次日可领；旧getticket场景只提示结束不发券 |
| TICKET-04 | P0 | A+B | COUPON,ID | 模板允许/禁止转赠、自己领、分享撤回/过期/已接受后再领；归属/分享状态转换合法且只一次，不靠前端隐藏保护 |
| TICKET-05 | P0 | A+B | COUPON,ID | 同券依次分享给M1/M2，合成关注事件只匹配本次交互；旧关注场景重放不能给新接收人授权，重复事件不多发券 |
| TICKET-06 | P1 | A+B+C | COUPON | 券A→B→A来回转赠；三tab按最后方向归属正确，无重复券，券码三位分隔不改二维码原始值 |
| TICKET-07 | P0 | B+C | COUPON,STAFF | 全店可看分享记录，但只能撤回本人批次；直接API试撤他人批次拒绝；日期默认一周、发券人多选及在职排序正确 |
| TICKET-08 | P1 | A+C | COUPON,ID | 未验证手机号详情整页遮罩不能绕过操作；授权成功恢复；分享卡片个人/群方式、取消/失败处理；未关注自动领取用stub，真实流程放D |
| TICKET-09 | P1 | A+C | COUPON,UI | 海报横竖图/动态码/静态码，二维码保持正方形且在图内，原图不拉伸；图片加载失败可重试、无空白保存 |
| TICKET-10 | P0 | A+B | COUPON | 同券两个核销请求并发、同一分享批次多人同时领取；单券最多一次有效核销，不越限多领，失败无部分资产迁移 |
| TICKET-11 | P0 | A | COUPON,CARE | 雪票/聚合/非雪季养护/发板四自动发券规则用stub分别触发重复事件；发放数符合规则且有来源；不调用真实业务回调或消息API |

### 6.10 餐饮食材（落点：Controllers/Fnb、Services/Fnb、pages/fnbinv、Fnb*Tests）

请求、权限及字段以 [食材 API 契约及补充](../superpowers/plans/2026-09-22-fnb-inventory-api-contract.md) 和当前 DTO 对照；保留 [旧 HTTP 验证报告](../superpowers/plans/2026-09-23-fnb-inventory-api-verification.md) 的失败作回归输入。数量精度至6位，BIGINT响应按字符串断言。

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| FNB-01 | P1 | B+C | FNB,STAFF | 员工查/入库/开封/制作/出餐/SaveCount成功；维护分类配方/新建食材/报损/建快照/过账/预警设置需店长；所有写接口测同店与跨店 |
| FNB-02 | P1 | B | FNB,STAFF | 员工库存/单据/流水/看板响应逐层检查成本/金额字段，不只是界面隐藏；店长能看；嵌套对象/错误响应也不泄露 |
| FNB-03 | P1 | A+B+C | FNB | 分类父子半成品继承、已有食材类型冲突拒绝；新食材类型由分类决定，伪造itemType无效；已有食材换不兼容分类拒绝 |
| FNB-04 | P1 | B+C | FNB | 有有效食材不许删分类；删空一级连子类、同名重建成功且历史仍按ID关联；同名并发返回业务错误非500 |
| FNB-05 | P1 | A+B+C | FNB | g/kg、ml/L、piece；不同量纲拒绝，1000换算准确，零负/超过6位精度/NaN拒绝；封装2袋×500g=1000g，不把袋数当克数 |
| FNB-06 | P1 | A+B+C | FNB | 生产日期+天/月、月末闰日、高低温月份、手动到期与规则互斥；同分类两个食材规则不得串；按上海日判断今天到期/已过期 |
| FNB-07 | P1 | A+C | FNB | OCR固定文本：2025-08-0512:30、四位年份与短日期混排、非法日、无日期；yyyy-MM-dd候选优先；选择确认后才填表，失败保留手填值，真实OCR放D |
| FNB-08 | P1 | B+C | FNB | 已有食材/店长临时建新食材两入库路径，单价照片均可空；传照片须有效且用途正确；提交取消无写入，成功200g×0.02=4并写批/库存/单/流水 |
| FNB-09 | P1 | B+C | FNB,FNB-V | 相同requestId串行重放3次、丢响应后重试、并发2/5/10；只一份库存和单据；不同payload复用ID不能悄悄写第二份；500仍记失败 |
| FNB-10 | P1 | B+C | FNB,FNB-V | 入库删除599/600/601秒边界按服务端比较符；本人/他人/店长；已有开封/出库/快照引用不能删；合法删除无孤儿流水，自动建的食材保留 |
| FNB-11 | P1 | B+C | FNB | 绕前端直接POST已过期批次、未来生产日/到期早于生产；明确不合法输入应拒绝且无写入；已知过期入库漏洞保留FAIL，不改成预期成功 |
| FNB-12 | P1 | A+B+C | FNB | 开封1袋→密封减500g、子批加500g，数量/成本守恒；到期=min原到期、开封后到期；36500代表保质期不变；重放不再开1袋 |
| FNB-13 | P1 | A+B+C | FNB | 菜品无售价分类可建默认标准份；配方存草稿→发布→新版本；旧rowVersion冲突，不覆盖他人版本；无效/重复/自我循环配料拒绝 |
| FNB-14 | P1 | A+B+C | FNB | 半成品每1000g耗600g，产2000g耗1200g；旧每批配方转每1单位不改变比例；不足原料整体拒绝，允许开封后重试；照片空允许 |
| FNB-15 | P1 | B | FNB | FEFO用5.2的B1/B2场景，排除密封/过期/销毁；同到期排序稳定；库存与每笔balance_qty/amount可对账，无负库存 |
| FNB-16 | P1 | B+C | FNB | CreateAndServe一道菜×2份，扣200g flour+100ml milk；0或2行菜拒绝；无已发布配方整单回滚，无孤立厨房单 |
| FNB-17 | P1 | A+B+C | FNB | 微调配料为0/合法/负数/重复/配方外/全0，按契约接受或拒绝；改份数保留已手改项，只重算未改项 |
| FNB-18 | P1 | B+C | FNB | 需求900g仅800g可用→实扣800欠100；建单前提示欠料，取消不扣；不开封时密封库存仅提示，不偷偷参与扣料 |
| FNB-19 | P1 | B+C | FNB | 后补200g→FillShortage只补100g；重复补扣不能双扣；该食材在出餐后已盘点则跳过并说明；7天/31天筛选和上限100准确 |
| FNB-20 | P1 | B+C | FNB,FNB-V | 出餐599/600/601秒编辑/删除和权限矩阵；退回原批次及后续流水余额，不延长首次时限；新菜无配方失败回滚为原单，补扣部分也正确退回 |
| FNB-21 | P1 | B | FNB | 出餐后批次被销毁/有盘点快照引用时禁止删除编辑，库存不被复活；重试不留下部分退料 |
| FNB-22 | P1 | B+C | FNB,FNB-V | 店长建快照→员工录实盘→预览→店长过账；原库存100实盘90差-10；库存被其他请求改过则code4，旧rowVersion拒绝，重复过账不重复调量 |
| FNB-23 | P1 | B+C | FNB | 过期销毁/报损合法数量及越量/重复ID/跨批次重用ID；一次扣减、旧批次状态同步、流水金额正确；不同批次相同requestId不得被误认成功 |
| FNB-24 | P1 | A+B+C | FNB | 低库存99/100/101g边界、固定线/比例/默认、无入库历史；开封与盘盈不改基数；预警可用量含有效未开封，与出餐可用量口径不同 |
| FNB-25 | P1 | B+C | FNB,UI | 库存/临期/过期/批次/流水/看板互相对账；大ID超过JS安全整数仍精确跳详情；业务日和UTC审计展示不偏一天 |
| FNB-26 | P1 | B | FNB,FNB-V | 同食材两个出餐、两个相同ID入库、盘点与出餐并发，2/5/10并发各3轮；不得双扣/负库存/部分提交；死锁500记FAIL并附重试后守恒证据 |
| FNB-27 | P2 | A+C | FNB,UI | 8tab与4详情页入口完整；旧mat_expire_detail重定向正确；旧服务端无预警接口时不影响其他页；照片加载/上传失败有提示 |
| FNB-28 | P2 | C | FNB,UI | 入库首屏日历未挂载，第一次点日期才创建；采冷启动5次中位数/p95、接口与渲染耗时、首次开日历；不把历史6.6秒/5秒当固定验收阈值 |

### 6.11 管理员 AI（落点：adminAiDomains/adminAssistant、AdminAiController、Services/AdminAssistant、reqai）

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| AI-01 | P1 | A+B+C | AI,STAFF | 四域各返回合法plan/action；按当前页面选择查询执行器，结果只跳固定对应列表；S100拒绝、S200允许，staff由服务端推导 |
| AI-02 | P1 | A+C | AI | 未知action、未知字段、跨域条件、非法日期/倒序/超365天/非法手机号后缀；拒绝执行且保留安全反馈，不任意跳URL或调用写接口 |
| AI-03 | P1 | A+B+C | AI,UI | 四月查询→只看未支付→条件回顾→切养护→改五月；四域上下文独立；页码重置1，筛选显示与实际query一致 |
| AI-04 | P0 | A+B | AI | 提示注入“忽略权限/给SQL/删除订单”、伪造staff/任意SQL参数；只能受白名单约束的只读查询，无执行代码/写数据库动作 |
| AI-05 | P1 | A+C | AI | 问题>2000字符、本地网络失败、stub超时、停止、离页、旧员工迟到响应；无无限loading/重复回答/串会话；重试不重复追加历史 |
| AI-06 | P1 | A+B | AI | 结构错误/重复JSON键/null/未知版本统一错误信封；不落入服务执行；trace关联日志，日志不存sessionKey/密钥/原始手机号 |
| AI-07 | P1 | A+C | AI,UI | 帮助只讲操作、不输出代码/接口字段；悬浮按钮拖动不出屏且不遮主要操作；未知门店、金额区间等不支持条件明确失败不伪造结果 |
| AI-08 | P1 | S | AI | 对照reqai四域能力表与前后端版本；列出本地6131ea4和线上待确认；缺仓库标BLOCKED_ENV，不读取密钥、不自动访问线上模型 |

### 6.12 雪票、公众号、员工、网页与支付宝

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| SKI-01 | P0 | A+C | SHOP,UI | 商品按雪场取，不被当前门店名误过滤；崇礼顾客可见万龙商品；有效/无效/缺省resort参数、空商品、网络失败不崩溃 |
| SKI-02 | P0 | S+A | MONEY | 静态定位ReserveSkiPass两次乘count；单价100数量1/2/3的独立期望100/200/300；若无可调用纯函数则S记录KD-04，A标NOT_IMPLEMENTED_TEST，不复制错误表达式自测 |
| SKI-03 | P0 | A+C | ID,UI | 日期价/姓名/手机号/身份证输入、无库存/预存不足stub、取消付款、成功落my_skipass；我的入口落my_skipasses，两页状态正确；绝不真实ReserveSkiPass |
| SKI-04 | P1 | A+C | SHOP,UI | 管理上下架/每日价格编辑请求校验，隐藏票顾客不可见；推荐码携带staff/referee并按优先级展示；订单取消/退款资格只用mock |
| OA-01 | P1 | S+A | COUPON,ID | 合成关注/取关/重复/非法签名/XML事件，检查模板与场景分发、关注状态规则；消息外发stub；未验证来源不得执行业务写入 |
| OA-02 | P1 | S+A | COUPON,CARE | ticket_gift/share/qr、care、recept、reserveskipass、unipay、员工注册、停用getticket逐场景；缺段/畸形/重放不串业务，不能复用旧交互授权 |
| STAFF-01 | P1 | S+C | STAFF | title_level100/101/199/200/201/300/1000列人事菜单矩阵；当前101～200可见记录KD-06，预期待负责人拍板；员工页面旧接口路由独立核对 |
| WEB-01 | P1 | A+C | UI | 后台二维码登录未扫码/超时/成功/退出/非员工；未授权不加载报表数据，退出旧会话不可复用；扫码mock，真实扫码放D |
| WEB-02 | P1 | B+C | UI,MONEY | 租赁/养护/零售/七色米/雪票/微信支付报表使用合成数据，日期/门店/测试标记/汇总与明细一致，空结果和导出特殊字符正确 |
| WEB-03 | P0 | A+C | MONEY | unipay金额空/0/负/0.01/超限/非数，微信/非微信两分支和崇礼门店参数；仅mock下单/支付/送券，取消不显示成功 |
| ALI-01 | P0 | A+C | MONEY,ID | 支付宝独立页面重复PAY-01/02/03，空openid/payerid/手机号授权失败/q参数编码；不能以微信通过代替；无支付宝工具则C单列阻塞 |
| ALI-02 | P1 | S+C | UI | 支付宝3页编译、首页导航与雪票订单列表空/有/失败；检查本地与正式域名分离、支付签名错误友好反馈，真实解密放D |

### 6.13 公共组件与非功能回归

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| COMMON-01 | P0 | A+C | SHOP,STAFF | 手动选店后延迟BLE定位成功/30秒超时不覆盖；万龙定位与基地店取舍；“全部门店”维持全部；销毁组件停止扫描 |
| COMMON-02 | P1 | A+C | UI | 今天/昨天/本周/上周、跨月跨年、周一/周日、手选范围，快捷高亮与真实范围一致；不以UTC截日偏移上海日期 |
| COMMON-03 | P1 | A+C | UI | 分页0/1/50/51/101行、末页、跳页非法、换每页数；查询时按钮不可点，返回详情保留筛选页码；最后页删除一条能回有效页 |
| COMMON-04 | P1 | A+C | UI | 图片上传超时/业务失败/坏URL/取消/成功，失败明确且可重试，无空白占位永久残留；IMAGE_HOST一致，网络轨迹无真实域名漏出 |
| COMMON-05 | P1 | C | UI | 320/375/414宽、长姓名金额、键盘遮挡、弹窗滚动、按钮连点；关键金额完整可读、禁用操作确实不发请求，回退无卡死 |
| COMMON-06 | P1 | B+C | UI | 列表51/501/2001行的本地确定性数据，记录耗时/响应大小/页码一致性；5次相同条件中位数/p95与本次基线比，增长>20%列性能观察，未经批准不当SLA |
| COMMON-07 | P0 | S+B+C | ID | 报告、日志、错误页、截图检查密钥/session/手机号/身份证脱敏；越权与500响应不暴露连接串；只保留合成夹具明文 |

### 6.14 真机与线上人工验收（Copilot 只准备步骤和账本）

各 D 用例先由负责人选择测试账号、渠道、金额、收件人、设备、开始时间，记录已部署版本和人工批准。需要交易的金额在渠道允许且不改变业务语义时用0.01元；无法小额的雪票/卡商品不得自动改线上价格来测试。每条填写执行人、订单别名、结果及脱敏截图。

| ID | 优先级 | 方式 | 夹具 | 操作与必须断言 |
|---|---|---|---|---|
| MAN-01 | P0 | D | ID,MONEY | 租赁微信/支付宝本人支付、代付各跑一次；扫码身份/金额正确，代付可弹支付窗，成功归属和标记正确，openid/payerid非空，取消不生效 |
| MAN-02 | P0 | D | RENT,MONEY | 原押金+追加押金两笔，分别扫码；全归还后逐笔原路退款，实际到账与订单余额一致；储值付租金全退押金且无0元储值记录 |
| MAN-03 | P0 | D | CARE,CARD | 养护储值/券/次卡/季卡微信核验；支付宝前置微信核验；错会员拒绝；0元权益单、0元招待单分别生效，核销不漏不重复 |
| MAN-04 | P0 | D | CARE | 养护取消原因→四核验方式；正常发板的扫码/验证码/凭证照片/店长确认；取消和发板不混，退款有到账且不500 |
| MAN-05 | P0 | D | CARD | 顾客新号授权购买次卡、租赁卖卡补差，款到发卡；未使用自助退款→已退灰色、各入口禁用；第二次退款拒绝 |
| MAN-06 | P0 | D | SHOP,ID | 四条普通链接二维码分别进入支付/核验/养护目标care/食材批次；体验版测试链接、冷启动、已登录和未登录都验证 |
| MAN-07 | P1 | D | COUPON | 转赠给未关注/已关注两人、撤回、来回转赠、个人/群卡片、动态/固定海报；只本次合法领取成功，通知仅给批准接收者 |
| MAN-08 | P1 | D | CARE,FNB | 养护/食材BLE打印，60×40mm标签、中文、二维码、份数、断开重连；扫描定位正确实体，不串上一件装备 |
| MAN-09 | P1 | D | FNB | 摄像头/OCR真实照片，优先日期候选正确、错误可手改；图片上传后其他设备可见；生产合法域名配置正确 |
| MAN-10 | P1 | D | FNB,STAFF | 企业微信登录/门店权限、旧H5跳转、提醒接收人确认；若确需提醒，仅负责人批准的测试收件范围，不默认@all |
| MAN-11 | P0 | D | SHOP | 万龙查价→订单→自我游出票→取票/取消/退款按业务允许情况；单独批准真实票款和预存扣费；支付与第三方失败补偿留证，自动化不得代做 |
| MAN-12 | P1 | D | AI,UI | 线上后端/小程序/公众号/reqai版本与必要schema/config确认；四域AI查询结果、后台扫码登录、人事入职、聚合付款送券分别验收；未发布功能逐项标明 |

## 7. 已知问题的处理与定向复现

这些是已知缺陷或待判定问题，不设“预期失败=通过”。用例正常执行并保存 actual；确有故障标 FAIL 并关联已有问题，避免重复建单；需要需求决定则 NEEDS_DECISION。不能用 xfail/skip 掩盖 P0。

| 问题 | 对应 ID | 复现/判定方式 |
|---|---|---|
| KD-01 六个菜单死入口 | BASE-02 | maintain/task_list、fire/fire_care_list的两业务入口、maintain/return_entry、maintain/maintain_in_stock、vip/maintain_recept。注册、文件和点击三层证据；共6菜单、5唯一页面路径 |
| KD-02 旧/core路由疑点 | BASE-03, STAFF-01 | 租赁报表、recept_list、staff_list/detail/reg、reserve_qrcode、ticket_template_list、ticket_unuse_list、ticket_bind逐URL记录。静态无路由不直接宣称线上404；本地404与生产代理转发待确认分开 |
| KD-03 取消原因事件时序 | CARE-11, MAN-04 | care_order_detail.js的onCancelReasonBlur、_resolveCancelParams/TEMP DEBUG；输入后不失焦直接点扫码，留mock调用与截图，再比较失焦后结果 |
| KD-04 雪票数量平方 | SKI-02 | Controllers/SkiPass/SkiPassController.cs:883,901附近两次乘count；数量2应200但源码构造400。只静态/纯规则，禁止调用下单验证 |
| KD-05 恢复草稿门店不一致 | REC-03 | SA建草稿→界面选SB→恢复→记录订单/页面/计价门店。保持订单原店是当前行为；界面必须明确真实门店；是否允许转店需负责人决定 |
| KD-06 高级别人事菜单不可见 | STAFF-01 | 101～200与201/300/1000矩阵；只记录当前可见性、需求待决，不能擅自扩权 |
| KD-07 过期批次仍能入库 | FNB-11 | 绕前端用本地隔离库PostReceipt；明确记录是否接受及全部写入。拒绝预期不因历史接受而改写 |
| KD-08 并发SQL死锁500 | FNB-09, FNB-26 | 屏障同时发起，保留每个响应与1205日志、最终账；未复现写明轮数，不宣布已修复；重试成功不消除首次失败 |
| KD-09 入库与日历性能/诊断残留 | FNB-28, COMMON-07 | 首屏/日历分段计时；源码TEMP/入库耗时输出列清单；没有负责人确认性能前不私自删日志 |

新增问题至少记录：严重度、业务影响、版本/dirty哈希、用例ID、前置夹具、最小步骤、预期与实际、首次失败证据、是否历史已知、修复后重测范围。需求不明不能伪装技术缺陷。

## 8. 35 条历史回归的追踪矩阵

编号对应功能说明第 7 章。所有映射用例各执行层都应在结果中可查；特别是资金/扫码问题必须包含 D 结果才算最终关闭。

| 原编号 | 回归主题 | 用例 ID |
|---|---|---|
| 1 | 找回草稿后保存 | REC-03 |
| 2 | 无价品类改租金 | REC-06, REC-09 |
| 3 | atOnce与起租时间持久化 | REC-04 |
| 4 | 免除日费用后的时间状态 | RENT-03, RENT-08 |
| 5 | 全归还与实际退款状态 | RENT-01, RENT-08 |
| 6 | 未付/已付的可退押金 | RENT-07 |
| 7 | 禁用按钮真的不可操作 | REC-05, PAY-06, COMMON-05 |
| 8 | 已付款订单正常关单 | RENT-11 |
| 9 | 未发放不日计租 | RENT-10 |
| 10 | 招待净额与毛租金 | RENT-09 |
| 11 | 储值付租金退款、无零金额记录 | RENT-12, DEPOSIT-02, MAN-02 |
| 12 | 两端按支付笔显示 | PAY-01, ALI-01, MAN-01, MAN-02 |
| 13 | 多笔退款精确分配 | PAY-06, MAN-02 |
| 14 | 养护快改不重复单/不冲卡 | CARE-03, CARE-05, REC-02 |
| 15 | 卡价0/季卡升级/锁装备/日限 | CARE-05, CARE-06, MAN-03 |
| 16 | 手动较大减免保留 | CARE-04 |
| 17 | 付款人变化后正确核卡 | CARE-08, MAN-03 |
| 18 | 零元招待生效 | CARE-07, PAY-08, MAN-03 |
| 19 | 养护退款不500 | CARE-14, MAN-04 |
| 20 | 安全检查值不丢 | CARE-10 |
| 21 | 代付弹支付窗 | PAY-03, PAY-04, MAN-01 |
| 22 | 支付宝openid及按手机号绑定 | PAY-04, ALI-01, MAN-01 |
| 23 | 本人身份状态正确 | PAY-02, PAY-07 |
| 24 | 五生效入口补会员资料 | PAY-09 |
| 25 | 新顾客授权买卡 | CARD-02, MAN-05 |
| 26 | 新券有效且可选 | TICKET-02 |
| 27 | 转赠不沿用旧关注记录 | TICKET-05, MAN-07 |
| 28 | 退卡后全入口禁用/退款资格 | CARD-04, CARD-05, CARE-06, MAN-05 |
| 29 | 全部卡型含季卡 | CARD-04 |
| 30 | 手选门店不被BLE覆盖 | COMMON-01 |
| 31 | 日期高亮正确 | COMMON-02 |
| 32 | 返回保留页码筛选 | RENT-16, COMMON-03 |
| 33 | 上传失败不留空图 | CARE-10, COMMON-04 |
| 34 | 崇礼查万龙雪票 | SKI-01 |
| 35 | 改商品名不改养护价格 | CARE-02 |

## 9. 覆盖与质量要求

### 9.1 每模块必交的覆盖说明

按功能说明4.1～4.9及5.1～5.16生成 `coverage-map.json`，记录功能→用例→执行层→测试文件/名称→结果。不能只报告“单测500个通过”而不说明租赁退款等核心流程是否覆盖。A/B/C/D结果分开汇总；S只反映静态证据。

租赁/养护/支付每个P0至少覆盖：成功、边界输入、无权、重复请求、网络失败、写后读回或对应人工渠道确认。新增API测试必须验证HTTP与业务码两层。禁止把预期金额直接取自被测方法另一次输出。

已存在167个前端测试主要集中AI/食材/会话/列表规则，不说明主租赁或支付端到端已有覆盖。新增测试优先复用当前框架，不能只把整页源码关键词匹配当业务测试。S可以扫描；A必须执行被测逻辑；B必须证实持久化；C必须实际渲染操作。

### 9.2 失败分级

| 严重度 | 定义 | 示例 |
|---|---|---|
| Sev0 | 真实资金/资产错账或数据破坏、权限突破 | 重复扣次/重复退款、跨会员用券、错误归属、生产误写 |
| Sev1 | 雪季主流程无法完成，或金额/状态重要错误 | 无法开单/结算/还板、后端500、押金应退错误 |
| Sev2 | 次要流程或可规避的问题 | 菜单死链、报表筛选错、明显性能退化 |
| Sev3 | 不影响完成业务的展示问题 | 非关键对齐、文字、诊断残留 |

优先级P0/P1/P2是执行顺序，严重度Sev是失败影响，两者不混用。已知问题也评严重度；示例不替代实际影响判断。

### 9.3 重测

原始失败日志永久保留。修复后先重跑失败ID和同规则边界，再跑受影响模块既有测试；涉及订单生效/身份/公共组件必须覆盖其跨模块调用方。资金、权限、事务、并发修复需有B或D证据，不能只用A关闭。记录修复提交与工作区diff，不把新结果覆写旧runId。

## 10. 输出格式、完成定义与交接

### 10.1 目录与状态

所有运行产物放 `snowmeet_ai_doc/artifacts/testing/<runId>/`（本地报告目录，不默认提交）：

```text
manifest.json                 # 版本、dirty清单/补丁摘要、工具版本、时间区间、配置哈希
environment-check.json        # S/A/B/C闸门结果，脱敏
case-results.json             # 全量ID及各执行层/子例的结果
coverage-map.json             # 功能说明章节和35条回归的覆盖映射
summary.md                    # 已测、缺陷、阻塞、人工待验、是否具备放行条件
defects.md                    # 每个缺陷的最小复现与证据路径
manual-checklist.md           # D类逐项表，人工填写人/时间/结果/证据
logs/                         # TRX、Node、编译、隔离API日志
http/                         # 脱敏请求响应
db/                           # 本地夹具映射与DML前后差异
screenshots/                  # C/D证据，必要时录屏
```

运行目录使用时间+随机后缀确保唯一；恢复执行时复用同一manifest但追加attempt，不覆盖原始证据。不要提交包含生产资料的报告、连接串、真实二维码或凭证。

修改用例后可在workspace根运行 `node snowmeet_ai_doc/tools/qa/build_test_plan_index.cjs` 重新生成索引并校验编号、执行层、夹具和35条回归映射；此工具仅读写本地文档，不执行任何业务测试。

用例状态严格使用：`NOT_RUN`、`PASS`、`FAIL`、`BLOCKED_ENV`、`BLOCKED_SCHEMA`、`BLOCKED_TOOL`、`NOT_IMPLEMENTED_TEST`、`NEEDS_DECISION`、`MANUAL_REQUIRED`、`OUT_OF_SCOPE_APPROVED`。最后一种必须写负责人和范围决定；Copilot不能自己豁免。重试后通过仍保留先前失败attempt。

`case-results.json` 至少包含：

```json
{
  "runId": "qa-20260930-example",
  "caseId": "RENT-02",
  "variant": "clear-overtime-day1",
  "mode": "B",
  "status": "NOT_RUN",
  "priority": "P0",
  "startedAt": null,
  "finishedAt": null,
  "attempt": 0,
  "fixtureKeys": ["RENT"],
  "testFile": null,
  "testName": null,
  "expected": "当天超时费valid=0，第二天不变，新连接读回一致",
  "actual": null,
  "evidence": [],
  "defectId": null,
  "blocker": null,
  "nextAction": "等待环境闸门通过并实现本用例"
}
```

一条A+B+C父用例，仅当三个层全部通过且所有参数子例通过时才PASS；其中任一FAIL父项FAIL，否则保留具体未完成状态。统计分别给父用例数、子例数、各层执行数，不能以重复运行刷通过率。

### 10.2 自动化交付完成

同时满足：

1. 第6章所有ID在账本中出现；第8章35项都有覆盖映射；无“省略后默认通过”。
2. 所有当前可运行的S/A以及通过环境闸门的B/C已执行；缺工具、缺表、缺接缝都有明确证据与下一步。单元命令退出0但用例未运行不算完成。
3. 已知/新增缺陷均可从日志和夹具复现；没有未经授权的业务修改/生产请求/DDL；原50个未提交改动保留。
4. D清单、待部署版本、schema确认和NEEDS_DECISION已交接。

环境不齐时可以完成“本轮测试交付”，报告必须写“部分验证，尚不具备上线结论”，不能写“测试全部通过”。

### 10.3 上线放行条件（由负责人决定）

- 雪季核心P0各层用例全部通过，特别是D类真实支付/退款/身份/订票；无未解决Sev0/Sev1。
- P1关键资产/权限和拟发布食材流程已通过；其余缺陷逐条由负责人接受并记录影响，不批量忽略“已知问题”。
- 后端、公众号、reqai、小程序版本匹配，所需schema/合法域名/扫码路径/设备配置有负责人证据；只通过本地测试不能证明生产已部署。
- 静态路由疑点、恢复草稿门店、人事菜单等未决项有处理决定；通过率不能掩盖未测P0。

Copilot最后回复应只汇报：运行版本、通过/失败/阻塞/人工数量、最严重缺陷、报告路径、需要负责人做的具体事项。不得把“所有可运行测试都通过”缩写成“系统可上线”。
