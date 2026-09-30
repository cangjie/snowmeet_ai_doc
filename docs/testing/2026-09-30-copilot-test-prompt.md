# 交给 Copilot 的执行指令

将下面内容作为 Copilot 的初始任务；同时让它能够读取整个工作区及本目录的方案、用例索引和功能说明。

---

请执行 Snowmeet 雪季上线测试。工作区为 `D:\source\snowmeet\ai`；独立 reqai 位于 `D:\source\snowmeet\snowmeet_reqai`。若运行在别的机器，请先定位同名仓库，不要套用不存在的绝对路径。

先完整阅读：

1. `snowmeet_ai_doc/docs/testing/2026-09-30-copilot-test-plan.md`
2. `snowmeet_ai_doc/docs/testing/2026-09-30-copilot-test-cases.json`
3. `snowmeet_ai_doc/docs/testing/2026-09-30-system-feature-inventory.md`
4. 当前适用的 AGENTS.md、`snowmeet_ai_doc/CLAUDE.md` 顶部状态及各模块代码。

以测试方案为执行流程，功能说明为需求输入，实际代码确认路径、协议和版本。文档与代码冲突要记录；不能照错误实现改业务预期。

请实际完成可安全运行的测试，不只再写一份计划。先创建runId和全量用例账本、记录各仓HEAD及既有dirty改动，然后按方案E0～E6推进，P0优先。复用既有测试，缺少的A/B/C测试在允许范围内补写，每个测试名包含用例ID；没有安全接缝时明确记录NOT_IMPLEMENTED_TEST。不要修改业务代码修缺陷；先保留最小复现并生成报告。默认不提交、不推送、不部署。

特别遵守：

- 微信小程序当前有50个既有未提交改动，不得reset、stash、checkout或批量格式化覆盖。
- 本地后端默认连生产库，不能从业务仓根目录直接dotnet run。
- 不访问生产数据库；不发真实支付/退款，不调用万龙下单/AutoReserve/实际业务回调，不发送公众号或企业微信消息，不调用线上OCR/模型。
- 不执行DDL，包括原LocalDB建删库运行器和包含EnsureCreated的测试；严格执行方案4.2的基线过滤器。严禁执行/import两个会读取生产配置并建删数据库的旧食材脚本。
- B只用负责人预先建好并确认的本地隔离库，按方案验证实例、库名、schema、API工作目录和外部网络隔离后才能写夹具。缺环境时只阻塞相关B/C-L，继续S/A和可运行的C-M。
- C必须在App启动前完成全网络拦截，未匹配的请求失败，不能先启动真实项目后再改域名。没有开发者工具/支付宝工具，明确BLOCKED_TOOL，不能用Node模拟冒充界面实测。
- 支付等A/C只做纯规则和完整mock，D只输出人工步骤；真实验收要人工执行并回填证据。is_test=1不是安全隔离。

按方案逐条记录PASS/FAIL/BLOCKED等状态。多执行层的用例分别记录，失败、跳过、静态检查、mock通过不能冒充端到端通过。已知缺陷仍需记录FAIL，需求不明记NEEDS_DECISION；不要为绿色结果改断言或删用例。

全部产物保存到 `snowmeet_ai_doc/artifacts/testing/<runId>/`：manifest、逐项case-results、coverage-map、summary、defects、manual-checklist，以及测试日志、脱敏HTTP、隔离库读回和截图。保证方案35条历史回归均有映射，没有遗漏用例ID。

结束时报告实际执行范围和统计、最严重缺陷、阻塞所缺条件、人工待验项、报告路径。只有满足方案上线闸门才能提出放行建议；本地单测全绿不代表系统可以上线。
