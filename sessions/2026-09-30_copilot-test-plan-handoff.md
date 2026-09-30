# 2026-09-30 Copilot 测试方案交接：按实际代码编写 170 条用例

本会话在 Windows 工作区 `D:\source\snowmeet\ai` 从 start-work 开始。承接 Claude 写好的系统功能说明和小程序已有南山清理改动，用户要求编写交给 Copilot 自动执行的测试方案。本轮交付都在文档仓，未修改业务代码。

## 1. 用户需求和工作范围

用户要求：

> 根据系统的实际情况和刚刚 Claude 编写的系统功能说明，来编写测试方案。该测试方案会交给 Copilot 自动执行。参考 2026-09-30-system-feature-inventory.md。

因此本轮不仅整理测试点，还核对当前源码、现有测试和脚本，把执行方式、环境限制、测试数据、可判定断言和报告格式写清。支付、退款、第三方订票、扫码、蓝牙和真实消息不伪装成可全自动验证。

## 2. 启动状态

文档仓 `pull --ff-only` 返回 Already up to date；基准 `main@dc2cec6`。Git 在沙箱账户下报仓库所有者不同；联网 pull 以仓库所有者身份执行，未修改全局 safe.directory 配置。

| 仓库 | 分支 / HEAD | 本轮业务改动 |
|---|---|---|
| SnowmeetApi | ai / 18e0601a | 无，工作区干净 |
| snowmeet_wechat_mini | ai / 0c712574 | 无新增；保留 36 个已暂存删除、14 个未暂存修改 |
| SnowmeetOfficialAccount | ai / 4c9c0a6 | 无 |
| reqai | main / 6131ea4 | 无；本机在 `D:\source\snowmeet\snowmeet_reqai` |
| alipay_snowmeet | 工作目录现状 | 无 |

启动时五个 Git 仓库相对本地远端引用均 ahead/behind=0/0；只有文档仓进行了联网 pull，其他仓没有据此宣称远端刚刚同步。

## 3. 源码核对得到的关键差异

### 3.1 页面与 AI 范围

- 当前 app.json：主包80页、payment1页、fnbinv12页，共93页。
- 功能说明的旧页面清单不能直接作为当前全部注册页面。
- `utils/adminAiDomains.js` 已有租赁、养护、零售、雪票四域。
- 三个非租赁列表页也接收 `applyPageIntent`。
- `Startup.cs` 注册四域查询执行器。
- 因此新方案按四域覆盖，线上 reqai 是否匹配仍待核实。

### 3.2 食材权限

- 已有食材入库允许同店员工。
- 入库时新建食材要求店长。
- `FnbStocktakeController.CreateSnapshot` 要店长。
- `SaveCount` 允许同店员工，`PostStocktake` 要店长。
- 员工不返回成本字段；跨店高级别也不可绕过基地店检查。

### 3.3 旧测试运行器的副作用

`SnowmeetApi/SnowmeetApi.Tests/run_fnb_http_smoke.py` 顶层导入 `run_fnb_sqlserver_integration.py`。后者读取业务仓 `config.sqlServer`，要求源库名为 `snowmeet_new`，在同一服务器新建测试库、读取生产表结构、结束时删库。不能仅凭“隔离测试库”名称就自动执行。

`snowmeet_ai_doc/tools/windows_test/run_integration_localdb.py` 不读生产，但包含建库、迁移和删库。功能说明要求 DDL 由负责人执行，方案保留原文七条限制，B 类改为负责人先建好本地隔离库，再由 Copilot 进行夹具 DML 和 API 测试。

`AdminAssistantControllerTests` 有 SQLite `EnsureCreatedAsync`，本次按同一限制保守排除。该排除是执行限制的解释，不能说这些测试失败；负责人可另行运行或明确调整测试权限。

### 3.4 启动与网络隔离

- `Util.GetSqlServerConnectionString` 和 `GetDbContext` 按当前工作目录读取 `config.sqlServer`。
- 仅改 ASPNETCORE_ENVIRONMENT 或连接串环境变量不足以换库。
- 小程序有默认生产域名、启动登录，以及独立上传/图片/公众号/Socket地址。
- C 类 mock/网络隔离必须在 App 启动前完成；连接 automator 后再改地址已经太晚。
- 静态帮助方法和直接 `new HttpClient` 存在，替换 IHttpClientFactory 不保证全部出站隔离。
- `ReserveSkiPass` 是 GET 但写订单，GET 不等于只读。

### 3.5 独立预期

确认万龙雪票代码两次乘 count，数量2的金额会按单价×4构造。方案用单价100、数量1/2/3应为100/200/300作为独立预期，只静态/纯规则验证，不实际下单。

租赁押金、逐笔退款、FEFO、入库成本、低库存阈值和月末日期都给出手算数据，防止测试复制错误算法而“自证正确”。历史已知问题仍记录FAIL，门店恢复和人事可见性等未拍板规则记NEEDS_DECISION。

## 4. 交付文件

| 文件 | 内容 |
|---|---|
| [完整测试方案](../docs/testing/2026-09-30-copilot-test-plan.md) | 170条主用例、环境闸门、阶段顺序、数据夹具、明确断言、报告和上线标准 |
| [Copilot启动指令](../docs/testing/2026-09-30-copilot-test-prompt.md) | 用户可直接复制，要求执行而非重复写计划 |
| [JSON用例索引](../docs/testing/2026-09-30-copilot-test-cases.json) | ID、优先级、必需执行层、夹具、操作断言、初始状态、证据类型、章节和回归映射 |
| [索引生成器](../tools/qa/build_test_plan_index.cjs) | 从方案表格生成JSON并检查唯一ID、合法执行层/夹具、25项章节和35项回归引用 |
| [项目上下文](../CLAUDE.md) | 当前状态、关键文件、下一步、运行器注意事项和开发日志 |

用例数量：P0 92、P1 76、P2 2，共170；其中12条为D类人工验收。多执行层、多个参数须展开成子例分别记录；父项只有所有必需层及子例通过才能PASS。

类型：S静态、A规则/单元、B本地隔离库、C实际界面（mock或本地后端）、D人工。明确区分阻塞、未实现测试、需求待决、人工待验与真正通过。

覆盖表包含功能说明4.1～4.9、5.1～5.16共25项，以及第7章全部35条历史回归。9组已知疑点单列定向复现。原功能说明未修改，差异写在新方案中。

运行器扩展只是接口规范，完整B/C业务测试套件尚待Copilot实现。新建的 `tools/qa/build_test_plan_index.cjs` 仅读写文档，不能误称为业务测试运行器。

## 5. 本轮实际验证

### 5.1 前端167项通过

在小程序目录，先用 PowerShell 枚举 `tests/*.test.js` 完整路径，再执行 `node --test @testFiles`。本机 Node v24.19.0，结果167通过、0失败、0跳过。

旧 Node 兼容工具 `tools/windows_test/run_tests.js` 不会自己展开通配符，因此方案命令同样显式枚举文件；新增复杂 hooks/mock 测试应使用支持的Node版本。

### 5.2 后端353项安全子集通过

在 SnowmeetApi 目录执行：

```powershell
& 'C:\Program Files\dotnet\dotnet.exe' test 'SnowmeetApi.Tests\SnowmeetApi.Tests.csproj' --no-restore --nologo --filter 'FullyQualifiedName!~FnbSqlServerIntegrationTests&FullyQualifiedName!~AdminAssistantControllerTests' --verbosity quiet
```

结果353通过、0失败、0跳过。两类测试是通过过滤器排除，不能计入“已测且跳过0”进而宣称全套后端已跑。编译有原有nullable/xUnit告警和ImageSharp包告警，本轮未更新依赖。

### 5.3 方案质量检查

- 生成器验证170个唯一ID。
- 25个功能章节映射完整。
- 35条历史回归映射完整。
- 两段PowerShell示例经Parser解析通过。
- 5个方案Markdown链接存在。
- 原文七条执行限制完整保留。
- JSON可解析，D类计数12。

本轮未启动业务API，未访问生产数据库，未执行DDL/支付/退款/订票/外发消息，未做开发者工具或真机验证。**353/167是既有基线，不是170条新用例的完成结果。**

## 6. 下一步交接

1. 用户把启动指令交给Copilot。
2. Copilot记录版本、dirty快照、runId，执行S/A并补缺失测试。
3. 负责人备妥本地隔离数据库和确认信息；B闸门通过后才执行接口持久化测试。
4. 有工具且启动前网络隔离通过时跑C；缺环境继续其他独立测试，不冒充通过。
5. D由人工验收，特别是支付、退款、第三方订票与设备。
6. 报告落 `snowmeet_ai_doc/artifacts/testing/<runId>/`，汇总缺陷、阻塞和未决事项。

小程序原有50个南山清理改动仍需开发者工具编译点测、由用户提交。生产schema与版本本轮未验证，不作上线结论。没有新增仅存在于本机memory的项目决策，交接知识均已固化到文档仓。

## 学到的小知识

1. **测试脚本也有生产副作用**：运行前必须追踪导入链、连接来源和建删库动作。
2. **当前代码与功能说明可能不同步**：页面数量和AI域范围应重新核对，不能照抄旧表。
3. **Mock不能替代端到端证据**：A/B/C/D分别记录，写库成功要新连接读回。
4. **“已有测试全绿”不等于核心业务覆盖**：现有前端测试集中食材/AI，支付与租赁仍需专门用例。
5. **机器可读索引可防漏项**：从Markdown单一来源生成，自动核验全部历史回归引用。
