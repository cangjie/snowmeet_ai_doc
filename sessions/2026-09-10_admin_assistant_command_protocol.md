# 2026-09-10 管理员帮助结构化指令协议

## 构建版本

本次验证在隔离 worktree 中执行；以下为实际被验证的提交：

| 仓库 | 验证 worktree | 基线 → 验证提交 |
| --- | --- | --- |
| reqai | `/Users/cangjie/Projects/snowmeet/reqai/.worktrees/admin-assistant-v1` | `3b16043` → `95354a3` |
| SnowmeetApi | `/Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi/.worktrees/admin-assistant-v1` | `bb905b9` → `1d5b854` |
| snowmeet_wechat_mini | `/Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini/.worktrees/admin-assistant-v1` | `6fa472fe` → `2c09f385` |

按任务说明执行的主检出版本命令及其逐字输出如下；三个主检出仍在实施前基线，故不能把这些输出误作已验证构建：

```text
$ git -C /Users/cangjie/Projects/snowmeet/reqai rev-parse --short HEAD
3b16043
$ git -C /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi rev-parse --short HEAD
bb905b9
$ git -C /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini rev-parse --short HEAD
6fa472fe
```

第三轮最终审查修复后的实际 worktree `rev-parse --short HEAD` 输出依次为 `95354a3`、`1d5b854`、`2c09f385`。

## 自动测试

所有命令在上述对应 worktree 的仓库根目录运行。

| 仓库 | 全量命令 | 实际结果 |
| --- | --- | --- |
| reqai | `backend/.venv/bin/pytest -q` | `228 passed, 13 failed, 1 skipped, 77 warnings in 10.11s`。13 个失败与记录的基线一致：`backend/tests/test_files.py` 的 5 个旧 `/Users/cangjie/source/snowmeet` 文件根路径测试，以及 `backend/tests/test_models_r7.py` 的 8 个旧 `o4-mini` / `gpt-4.1` 白名单测试；未出现新的失败类别。 |
| SnowmeetApi | `dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj` | 命令成功完成；为取得可复现的安静汇总，随后运行 `dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --no-restore --verbosity quiet`，输出 `Failed: 0, Passed: 303, Skipped: 0, Total: 303`。现有 NuGet 漏洞、编译器和分析器警告仍出现。 |
| snowmeet_wechat_mini | `npm test` | `tests 36`、`pass 36`、`fail 0`、`skipped 0`。 |

额外的协议聚焦测试：

```text
$ backend/.venv/bin/pytest backend/tests/test_admin_assistant_protocol.py backend/tests/test_admin_assistant_router.py backend/tests/test_service_auth.py -q
24 passed, 2 warnings in 3.04s

$ dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter AdminAssistant --no-restore --verbosity quiet
Failed: 0, Passed: 51, Skipped: 0, Total: 51

$ node --test tests/admin_page_help_component.test.js tests/new_rent_list_ai_state.test.js tests/admin_ai_query.test.js tests/admin_assistant.test.js tests/auth_session.test.js
tests 33; pass 33; fail 0
```

## 验收结论

以下“自动化通过”表示在 reqai 路由测试、SnowmeetApi 服务 fake / in-memory SQLite / `TestServer` 测试，或小程序 stub 测试中有直接断言；它不表示已经用真实本地员工会话或生产数据手工验收。

| 场景 | 自动化证据与实际结果 | 结论 |
| --- | --- | --- |
| Structured 开启、纯文字帮助 | `AdminAssistantServiceTests.纯文字回复保留现有上下文且不查询` 断言无 action、保留 context 且查询执行器未调用；小程序“普通帮助和条件回顾均走统一接口”断言统一接口调用。 | 自动化通过 |
| 四月查询、文字与跳转 | 服务测试把内部 `rental_order.query` 转为唯一 `rental_order.show_results`；小程序“四月租赁查询…”断言显示答复、保存完整 state、跳转固定租赁列表路径。 | 自动化通过 |
| 连续 `patch`（未支付） | reqai 测试断言 patch 只序列化显式字段；`Patch只修改出现的字段并允许null清除` 保留日期、替换状态并允许显式 null 清除。 | 自动化通过；未进行真实 planner 的连续 curl 序列 |
| 连续 `patch`（改五月） | 同一 merge 规则覆盖 `start_date` / `end_date` 的显式字段；完整 11 字段 state 在小程序传输、列表初始化与分页参数测试中被保留。 | 自动化规则通过；未进行真实 planner 的五月 curl 序列 |
| 查询条件回顾 | 小程序测试把含全部 11 个字段的 context 发送给“当前查询条件是什么”，并断言保留最近 20 条会话。 | 上下文传输自动化通过；“自然语言逐项列出 11 条条件”的真实模型答复未手工验收 |
| finalize 故障 | `Finalize失败仍返回确定性汇总和成功action` 断言 fallback 文本包含数量、action 仍为 `completed`、审计为 `finalize_failed`。 | 自动化通过 |
| 未知 action | reqai 与 API 协议测试拒绝 `refund.execute`；小程序测试对未知 action 保留服务端文字、不跳转并显示升级提示。 | 自动化通过 |
| 三个 `group_by` | reqai `test_only_one_action_and_two_groups_are_allowed` 拒绝三个 group；API 解析器限制为最多两个且聚焦 API 套件通过。 | 自动化通过；未通过真实 HTTP stub 发送该 payload |
| 完整结果不受 200 限制 | `RentalOrderAssistantSummaryTests.汇总不截断200单并可按状态门店分组` 对 250 行断言 `order_count=250`、金额和四组结果。 | 自动化通过 |
| 开关关闭兼容 | 未配置时 `GetValue<bool>` 为 false。`AdminAssistantLegacyAdapterTests` 断言查询先走 legacy intent、不会调用 structured plan，并转换为 v1 `show_results`；普通帮助只在 unsupported intent 后走 legacy page-help，仍返回 v1 文字。 | 自动化通过 |
| 严格 merged context、第二轮序列化与 request binder | `合并会复制全部十一项条件` 覆盖 replace / patch 的全部 11 个字段；`执行器前拒绝客户端上下文保留的非法条件` 确认恶意保留 context 在执行前被拒绝。小程序测试将第二轮 conversation 投影成 binder 接受的严格 `role/content` JSON，丢弃无效/超长项，并将从 API 接收的 ISO 日期规范为 `yyyy-MM-dd` 后再发送。`AdminAssistantEndpointIntegrationTests` 的 `TestServer` cases 拒绝 malformed、null、大小写变体、重复属性和未知嵌套字段，并返回统一 HTTP 400 envelope。 | 自动化通过 |
| 有效 v1 HTTP 400 / 502 / 403 失败 envelope | 小程序组件测试断言有效 v1 的 400、502 和 403 envelope 均显示服务端安全 `reply`、保留 `trace_id`、不执行 action 且不显示原始敏感错误；502 可重试，400 与权限 403 不可重试。API controller 测试覆盖权限拒绝的 HTTP 403 和安全 v1 失败响应。 | 自动化通过 |
| 小程序问题长度与 loading owner | 组件测试断言超过 API 2,000 字符上限的问题显示安全反馈且不调用统一接口；同一 owner 的旧 stale 请求不能清除新请求的 `loading`，当前 stale 请求会结算自己的 `loading`。 | 自动化通过 |
| stale success、conversation 与 UI owner 隔离 | 小程序测试断言旧员工的延迟成功返回 `stale_session` 且不改写新员工 context；切换员工或同员工 sessionKey 变化会清空旧对话；旧员工的延迟初始帮助、延迟结果和重试均不会覆盖新员工界面、context 或跳转。 | 自动化通过 |
| 审计与敏感数据边界 | API in-memory SQLite / captured reqai client 测试覆盖 finalize payload、成功/失败审计和自由文本：完整及带分隔符的手机号被清除或仅保留查询后四位；带引号或多 token 的 `api-key`、`password`、`authorization`、`Cookie`、`OpenID`、payment 与 service token 值均被剔除。reqai 路由测试覆盖 plan/finalize prompt 与 invocation audit 的格式化手机号、多 token 凭据，以及从敏感键名开始直至分隔符/文本末尾的值掩码，并验证 LLM 失败记录 invocation `error`。 | 自动化通过；没有检查真实本地表或生产日志 |

未执行的人工/本地验收：运行环境未设置 `ADMIN_ASSISTANT_TEST_SESSION`，因此没有执行以下会暴露本地测试会话所需的命令，也没有启动本地服务、修改本地开关、发出 curl，或检查真实 `admin_ai_request_log` / `snowmeet_help_invocations` 最近两条记录：

```text
: "${ADMIN_ASSISTANT_TEST_SESSION:?请先设置本地测试员工 sessionKey}"
curl -k -sS -X POST "https://localhost:5001/api/AdminAi/AskAdminAssistantByStaff?sessionKey=${ADMIN_ASSISTANT_TEST_SESSION}" ...
```

因此，该项记录不能替代真实 session 下的 structured-on 端到端序列、structured-off HTTP 序列、真实 planner 的完整条件文字检查，或真实数据库日志抽检。上表列出的自动化等价证据是当前可复现证据。

## 发布与回滚

发布顺序：

1. 部署 reqai 的 `plan` / `finalize` 接口，同时保留旧 `page-help` 与 `rent-query-intent`。
2. 部署 SnowmeetApi，`AdminAssistant:StructuredProtocolEnabled=false`。
3. 部署小程序。
4. 小范围打开 SnowmeetApi 的 structured 开关并完成真实会话验收。
5. 全量打开开关。

回滚只关闭 `AdminAssistant:StructuredProtocolEnabled`。不回滚数据库，不恢复客户端关键词分流；统一接口会经服务端 legacy adapter 保持 v1 外层响应。本次未 push、未部署、未改动生产配置。

上述顺序只是上线时的操作指引，不构成部署授权。用户已授权未来对 **reqai** 进行自主 SSH / 部署，但该授权明确递延到本地验证和最终审查通过之后；本次未使用该授权。SnowmeetApi 和小程序没有自主 push 或部署授权，二者的任何 push、部署或生产配置变更都必须取得用户另行明确指示。

## 差异与工作区检查

对三个实施范围分别执行 `git diff --check <base>..<head>`，均无输出。第三轮最终审查修复增加了 reqai 直到分隔符/文本末尾的敏感值掩码，以及小程序 2,000 字符输入上限和同 owner stale-request loading 隔离。验证后的实现 worktree 状态：reqai 和 SnowmeetApi 干净；mini-program 只有既有、未暂存且未触碰的 `node_modules/@vant/weapp/package.json` 修改（41 insertions、73 deletions）。
