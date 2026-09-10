# 管理员帮助系统结构化指令协议 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将管理员帮助统一为 reqai 规划、SnowmeetApi 校验执行、小程序显示答复并跳转租赁订单结果页的 v1 协议，同时支持连续自然语言筛选和查询条件回顾。

**Architecture:** reqai 只生成严格的文字答复与语义 action；SnowmeetApi 是唯一可信执行边界，合并上下文、校验权限、查询全量结果、计算汇总并调用 finalize；小程序只执行 SnowmeetApi 返回的 `rental_order.show_results`。三个子系统共同组成一条协议链路，因此采用一份跨仓垂直计划，每个任务仍保持独立测试和提交。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、pytest；ASP.NET Core / C# net9.0、EF Core、xUnit；微信小程序 JavaScript、Node.js `node:test`。

**Spec:** `snowmeet_ai_doc/docs/superpowers/specs/2026-09-10-admin-assistant-command-protocol-design.md`

## Global Constraints

- 协议版本固定为字符串 `"1"`，reqai 每轮最多返回一个 action。
- v1 唯一服务端业务 action 是 `rental_order.query`；唯一客户端 action 是 `rental_order.show_results`。
- reqai 不得返回 SQL、API URL、小程序路由、代码、脚本或任意方法名。
- v1 查询字段仅允许 `start_date`、`end_date`、`shop`、`rent_status`、`is_test`、`is_entertain`、`have_discount`、`use_card`、`has_retail`、`cell_suffix`、`keyword`。
- 日期范围必填且最多 365 天；`cell_suffix` 至少四位且只能为数字。
- 汇总指标仅允许 `order_count`、`charge_total`、`paid_total`、`refund_total`、`unpaid_count`；分组仅允许 `rent_status`、`shop`、`biz_date`，最多两个维度。
- 查询和汇总必须基于完整匹配结果，不能沿用旧接口的 200 单截断。
- 查询权限最低 `title_level >= 100`；纯页面帮助沿用 `title_level >= 200`。
- finalize 只接收问题、完整筛选条件和汇总，不接收订单行、姓名、完整手机号、openid 或支付流水。
- 第一版不新增数据库表或 DDL，不实现任何写业务 action。
- `AdminAssistant:StructuredProtocolEnabled` 初始为 `false`；关闭时由 SnowmeetApi 服务端兼容旧 reqai 接口，小程序不恢复关键词判断。
- 旧 `page-help`、`rent-query-intent`、`GetPageHelpByStaff`、`AskPageHelpByStaff` 和 `QueryRentOrdersByNaturalLanguage` 本期保留。

---

### Task 1: reqai v1 严格协议模型

**Files:**
- Create: `reqai/backend/app/admin_assistant_protocol.py`
- Create: `reqai/backend/tests/test_admin_assistant_protocol.py`

**Interfaces:**
- Consumes: Pydantic 2 `BaseModel`、`ConfigDict(extra="forbid")`。
- Produces: `AdminAssistantPlanIn`、`AdminAssistantPlan`、`AdminAssistantAction`、`RentalOrderQueryArguments`、`AggregationRequest`、`AdminAssistantFinalizeIn`、`AdminAssistantFinalizeOut`；Task 2 的路由直接使用这些类型。

- [ ] **Step 1: 写协议模型失败测试**

```python
import pytest

from pydantic import ValidationError

from app.admin_assistant_protocol import (
    AdminAssistantPlan,
    AdminAssistantAction,
    AdminAssistantFinalizeIn,
    AggregationRequest,
    AssistantReply,
    RentalOrderQueryArguments,
)


def valid_query_action():
    return AdminAssistantAction.model_validate({
        "id": "a1", "type": "rental_order.query", "mode": "replace",
        "arguments": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
        "aggregation": {"metrics": ["order_count"], "group_by": []},
    })


def valid_finalize_payload():
    return {
        "version": "1", "trace_id": "trace-12345678", "question": "查询四月订单",
        "planner_reply": None,
        "query": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
        "aggregation": {"metrics": ["order_count"], "group_by": []},
        "summary": {"metrics": {"order_count": 12}, "groups": []},
    }


def test_plan_requires_reply_or_action():
    with pytest.raises(ValidationError):
        AdminAssistantPlan(version="1", reply=None, actions=[])


def test_plan_rejects_unknown_action_and_extra_argument():
    with pytest.raises(ValidationError):
        AdminAssistantAction.model_validate({"id": "a1", "type": "refund.execute", "mode": "replace", "arguments": {}})
    with pytest.raises(ValidationError):
        RentalOrderQueryArguments.model_validate({"start_date": "2026-04-01", "sql": "select 1"})


def test_patch_retains_explicit_null_presence():
    args = RentalOrderQueryArguments.model_validate({"shop": None})
    assert args.model_fields_set == {"shop"}
```

- [ ] **Step 2: 运行测试确认因模块不存在而失败**

Run: `cd /Users/cangjie/Projects/snowmeet/reqai/backend && pytest tests/test_admin_assistant_protocol.py -q`

Expected: FAIL，错误包含 `ModuleNotFoundError: No module named 'app.admin_assistant_protocol'`。

- [ ] **Step 3: 实现严格模型和跨字段校验**

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Metric = Literal["order_count", "charge_total", "paid_total", "refund_total", "unpaid_count"]
GroupBy = Literal["rent_status", "shop", "biz_date"]
RentStatus = Literal["未支付", "未开始", "租赁中", "部分归还", "全部归还", "部分退押金", "全额退押金", "了结关闭", "临时订单"]


class RentalOrderQueryArguments(StrictModel):
    start_date: date | None = None
    end_date: date | None = None
    shop: str | None = Field(default=None, max_length=64)
    rent_status: RentStatus | None = None
    is_test: bool | None = None
    is_entertain: bool | None = None
    have_discount: bool | None = None
    use_card: bool | None = None
    has_retail: bool | None = None
    cell_suffix: str | None = Field(default=None, min_length=4, max_length=15, pattern=r"^[0-9]+$")
    keyword: str | None = Field(default=None, max_length=100)


class AggregationRequest(StrictModel):
    metrics: list[Metric] = Field(default_factory=lambda: ["order_count"], min_length=1)
    group_by: list[GroupBy] = Field(default_factory=list, max_length=2)


class AdminAssistantAction(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["rental_order.query"]
    mode: Literal["replace", "patch"]
    arguments: RentalOrderQueryArguments
    aggregation: AggregationRequest = Field(default_factory=AggregationRequest)


class AssistantReply(StrictModel):
    text: str = Field(min_length=1, max_length=12_000)
    citations: list[dict] = Field(default_factory=list)


class AdminAssistantPlan(StrictModel):
    version: Literal["1"]
    reply: AssistantReply | None = None
    actions: list[AdminAssistantAction] = Field(default_factory=list, max_length=1)

    @model_validator(mode="after")
    def require_content(self):
        if self.reply is None and not self.actions:
            raise ValueError("reply 和 actions 不能同时为空")
        return self
```

`AdminAssistantPlanIn` 精确定义 `version`、`page_key`、`question`、最多 20 条 `conversation`、`context`、`staff_id`、`trace_id`、`current_date` 和固定 `timezone="Asia/Shanghai"`。`AdminAssistantFinalizeIn` 精确定义 `version`、`trace_id`、`question`、`planner_reply`、完整 `query`、`aggregation`、`summary`；`AdminAssistantFinalizeOut` 只包含 `version` 与非空 `reply`。

- [ ] **Step 4: 补齐边界测试并确认通过**

```python
def test_only_one_action_and_two_groups_are_allowed():
    action = valid_query_action()
    with pytest.raises(ValidationError):
        AdminAssistantPlan(version="1", actions=[action, action])
    with pytest.raises(ValidationError):
        AggregationRequest(metrics=["order_count"], group_by=["shop", "biz_date", "rent_status"])


def test_finalize_input_rejects_order_rows():
    body = valid_finalize_payload()
    body["orders"] = [{"contact_name": "不应出现"}]
    with pytest.raises(ValidationError):
        AdminAssistantFinalizeIn.model_validate(body)
```

Run: `cd /Users/cangjie/Projects/snowmeet/reqai/backend && pytest tests/test_admin_assistant_protocol.py -q`

Expected: PASS。

- [ ] **Step 5: 提交 reqai 协议模型**

```bash
cd /Users/cangjie/Projects/snowmeet/reqai
git add backend/app/admin_assistant_protocol.py backend/tests/test_admin_assistant_protocol.py
git commit -m "feat: define admin assistant v1 protocol"
```

### Task 2: reqai plan 与 finalize 服务路由

**Files:**
- Create: `reqai/backend/app/routers/admin_assistant.py`
- Create: `reqai/backend/tests/test_admin_assistant_router.py`
- Modify: `reqai/backend/app/main.py:33-38`

**Interfaces:**
- Consumes: Task 1 的所有协议类型；现有 `llm.complete_json()`、`settings_store.resolve_for_session()`、`build_context()`、`require_snowmeet_service()`。
- Produces: `POST /api/service/admin-assistant/plan` 和 `POST /api/service/admin-assistant/finalize`；响应分别为 `AdminAssistantPlan` 与 `AdminAssistantFinalizeOut`，外加 `model`、`effort` 可观测字段；token 用量继续由 `llm.complete_json()` 写入现有 usage 记录。

- [ ] **Step 1: 写两个服务路由的失败测试**

```python
import json

from fastapi.testclient import TestClient

from app import service_auth
from app.admin_assistant_protocol import AdminAssistantFinalizeOut, AdminAssistantPlan
from app.main import app
from app.routers import admin_assistant


def service_headers():
    return {"X-Snowmeet-Service-Token": "test-service-token"}


def plan_request():
    return {
        "version": "1", "page_key": "pages/admin/member/member_list",
        "question": "查询今年四月租赁订单", "conversation": [],
        "context": {"rental_order_query": None}, "staff_id": 7,
        "trace_id": "trace-12345678", "current_date": "2026-09-10",
        "timezone": "Asia/Shanghai",
    }


def sample_plan():
    return AdminAssistantPlan.model_validate({
        "version": "1", "reply": {"text": "我来查询。", "citations": []},
        "actions": [{"id": "a1", "type": "rental_order.query", "mode": "replace",
                     "arguments": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
                     "aggregation": {"metrics": ["order_count"], "group_by": []}}],
    })


def test_plan_returns_text_and_query_action(client, monkeypatch):
    monkeypatch.setattr(admin_assistant.llm, "has_key", lambda: True)
    async def fake_messages(body):
        return [{"role": "user", "content": body.question}]
    monkeypatch.setattr(admin_assistant, "_build_plan_messages", fake_messages)
    monkeypatch.setattr(admin_assistant.llm, "complete_json", lambda *a, **k: sample_plan())
    response = client.post("/api/service/admin-assistant/plan", headers=service_headers(), json=plan_request())
    assert response.status_code == 200
    assert response.json()["actions"][0]["type"] == "rental_order.query"


def test_finalize_only_receives_summary(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(admin_assistant.llm, "has_key", lambda: True)
    def fake_complete(messages, *args, **kwargs):
        captured["messages"] = messages
        return AdminAssistantFinalizeOut.model_validate({"version": "1", "reply": {"text": "共 12 单。", "citations": []}})
    monkeypatch.setattr(admin_assistant.llm, "complete_json", fake_complete)
    response = client.post("/api/service/admin-assistant/finalize", headers=service_headers(), json=finalize_request())
    assert response.status_code == 200
    serialized = json.dumps(captured["messages"], ensure_ascii=False)
    assert "contact_name" not in serialized
    assert "openid" not in serialized
```

`finalize_request()` 在测试文件中直接返回 Task 1 的 `valid_finalize_payload()` 同结构字典；`client` fixture 将 `service_auth.settings.SNOWMEET_SERVICE_TOKEN` 设为 `test-service-token` 后创建 `TestClient(app)`。

- [ ] **Step 2: 运行测试确认路由为 404**

Run: `cd /Users/cangjie/Projects/snowmeet/reqai/backend && pytest tests/test_admin_assistant_router.py -q`

Expected: FAIL，首先因为 `app.routers.admin_assistant` 尚不存在；创建路由文件但尚未注册时失败状态为 HTTP 404。

- [ ] **Step 3: 实现 planner prompt、RAG 上下文和路由**

```python
router = APIRouter(prefix="/api/service/admin-assistant", tags=["snowmeet-admin-assistant"])


@router.post("/plan", dependencies=[Depends(require_snowmeet_service)])
async def plan(body: AdminAssistantPlanIn):
    if not llm.has_key():
        raise HTTPException(503, "服务端未配置 OPENAI_API_KEY")
    model, effort = settings_store.resolve_for_session(None, None)
    messages = await _build_plan_messages(body)
    result = await run_in_threadpool(
        llm.complete_json, messages, AdminAssistantPlan,
        model=model, purpose="snowmeet_admin_assistant_plan", effort=effort,
    )
    return {**result.model_dump(mode="json"), "model": model, "effort": effort}
```

`_build_plan_messages()` 调用 `build_context(prompt, pinned=[], mode="chat", instructions=None, history=history, history_summary=None, user_id=None)`，携带最近 20 条对话与完整 `rental_order_query`。系统提示逐字列出 v1 action、字段、replace/patch/null 语义和禁止项；询问当前条件时要求列出全部 11 个字段且不产生 action；普通页面问题仅给 `reply`；不能确定日期时返回澄清 `reply` 且不产生 action。

- [ ] **Step 4: 实现 finalize 路由并记录既有调用日志**

```python
@router.post("/finalize", dependencies=[Depends(require_snowmeet_service)])
async def finalize(body: AdminAssistantFinalizeIn):
    if not llm.has_key():
        raise HTTPException(503, "服务端未配置 OPENAI_API_KEY")
    model, effort = settings_store.resolve_for_session(None, None)
    messages = _build_finalize_messages(body)
    result = await run_in_threadpool(
        llm.complete_json, messages, AdminAssistantFinalizeOut,
        model=model, purpose="snowmeet_admin_assistant_finalize", effort=effort,
    )
    return {**result.model_dump(mode="json"), "model": model, "effort": effort}
```

在 `snowmeet_help_invocations` 中使用短操作名 `plan`/`finalize`，`prompt` 存问题，`business_context` 存筛选与汇总，`answer` 存最终结构化响应 JSON；沿用现有表，不创建 migration。异常时写 `status="error"` 后返回 502。

- [ ] **Step 5: 注册路由并验证旧路由仍存在**

```python
for name in (
    "sessions", "projects", "chat", "docs", "admin", "export", "files",
    "attachments", "page_help", "query_intent", "admin_assistant",
):
    try:
        mod = __import__(f"app.routers.{name}", fromlist=["router"])
        app.include_router(mod.router)
    except ModuleNotFoundError:
        pass
```

测试 OpenAPI 同时包含 `/api/service/page-help`、`/api/service/rent-query-intent`、`/api/service/admin-assistant/plan` 和 `/api/service/admin-assistant/finalize`。

Run: `cd /Users/cangjie/Projects/snowmeet/reqai/backend && pytest tests/test_admin_assistant_protocol.py tests/test_admin_assistant_router.py tests/test_service_auth.py -q`

Expected: PASS。

- [ ] **Step 6: 运行 reqai 全量测试并提交**

Run: `cd /Users/cangjie/Projects/snowmeet/reqai/backend && pytest -q`

Expected: 全部 PASS。

```bash
cd /Users/cangjie/Projects/snowmeet/reqai
git add backend/app/routers/admin_assistant.py backend/app/main.py backend/tests/test_admin_assistant_router.py
git commit -m "feat: add admin assistant plan and finalize endpoints"
```

### Task 3: SnowmeetApi 协议解析、白名单和上下文合并

**Files:**
- Create: `SnowmeetApi/Models/AdminAssistant/AdminAssistantContracts.cs`
- Create: `SnowmeetApi/Helpers/AdminAssistantProtocolRules.cs`
- Create: `SnowmeetApi/SnowmeetApi.Tests/AdminAssistantProtocolRulesTests.cs`

**Interfaces:**
- Consumes: reqai v1 JSON 和小程序 v1 request JSON。
- Produces: `AdminAssistantRequest`、`AdminAssistantResponse`、`ReqaiPlanResponse`、`RentalOrderQueryState`、`RentalOrderQueryPatch`；`AdminAssistantProtocolRules.ParsePlan(string)`、`Merge(mode, current, patch)`、`ValidateQuery(state)`。

- [ ] **Step 1: 写 replace、patch、清除和非法字段失败测试**

```csharp
[Fact]
public void Patch只修改出现的字段并允许null清除()
{
    RentalOrderQueryState current = new() { start_date = D("2026-04-01"), end_date = D("2026-04-30"), shop = "万龙", rent_status = "未支付" };
    RentalOrderQueryPatch patch = AdminAssistantProtocolRules.ParseArguments("{\"shop\":null,\"rent_status\":\"全部归还\"}");
    RentalOrderQueryState merged = AdminAssistantProtocolRules.Merge("patch", current, patch);
    Assert.Null(merged.shop);
    Assert.Equal("全部归还", merged.rent_status);
    Assert.Equal(D("2026-04-01"), merged.start_date);
}

[Fact]
public void 未知action和参数被拒绝()
{
    Assert.Throws<InvalidOperationException>(() => AdminAssistantProtocolRules.ParsePlan(PlanJson("refund.execute")));
    Assert.Throws<InvalidOperationException>(() => AdminAssistantProtocolRules.ParseArguments("{\"sql\":\"select 1\"}"));
}
```

测试类同时定义 `private static DateTime D(string value) => DateTime.Parse(value, CultureInfo.InvariantCulture);`，以及返回完整 v1 JSON 的 `PlanJson(string actionType)`；该 JSON 只改变 action type，其他字段使用 `version="1"`、`mode="replace"`、四月日期和 `order_count`。

- [ ] **Step 2: 运行测试确认类型尚不存在**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter AdminAssistantProtocolRulesTests`

Expected: FAIL，编译错误指出 `AdminAssistantProtocolRules`/`RentalOrderQueryState` 不存在。

- [ ] **Step 3: 定义稳定的请求、响应和状态 DTO**

```csharp
public sealed class RentalOrderQueryState
{
    public DateTime? start_date { get; set; }
    public DateTime? end_date { get; set; }
    public string? shop { get; set; }
    public string? rent_status { get; set; }
    public bool? is_test { get; set; }
    public bool? is_entertain { get; set; }
    public bool? have_discount { get; set; }
    public bool? use_card { get; set; }
    public bool? has_retail { get; set; }
    public string? cell_suffix { get; set; }
    public string? keyword { get; set; }
}

public sealed class AdminAssistantResponse
{
    public string version { get; set; } = "1";
    public string trace_id { get; set; } = "";
    public AssistantReply reply { get; set; } = new();
    public List<ClientAssistantAction> actions { get; set; } = new();
    public AdminAssistantContext context { get; set; } = new();
}
```

`AdminAssistantRequest` 包含 `version`、`page_key`、`question`、`conversation`、`context`。客户端 action DTO 只允许 `id`、固定 `type`、`status="completed"`、完整 `state` 和 `summary`。

- [ ] **Step 4: 用 `JsonDocument` 实现递归白名单和字段存在性**

```csharp
private static readonly HashSet<string> QueryFields = new(StringComparer.Ordinal)
{
    "start_date", "end_date", "shop", "rent_status", "is_test", "is_entertain",
    "have_discount", "use_card", "has_retail", "cell_suffix", "keyword"
};

public static RentalOrderQueryPatch ParseArguments(JsonElement element)
{
    RejectUnknownProperties(element, QueryFields);
    RentalOrderQueryPatch patch = new();
    foreach (JsonProperty property in element.EnumerateObject())
    {
        patch.Specified.Add(property.Name);
        patch.Set(property.Name, property.Value.ValueKind == JsonValueKind.Null ? null : property.Value);
    }
    return patch;
}
```

`ParsePlan` 对根、reply、action、aggregation 和 arguments 每层检查允许属性；检查 version、最多一个 action、reply/action 非同时为空、action type、mode、指标、分组及重复项。`Merge("replace", ...)` 从空 state 开始；`Merge("patch", ...)` 复制 current，仅覆盖 `Specified` 字段。

- [ ] **Step 5: 实现权威条件校验并跑测试**

```csharp
public static void ValidateQuery(RentalOrderQueryState state)
{
    if (state.start_date == null || state.end_date == null)
        throw new AdminAssistantClarificationException("请明确查询日期范围。");
    if (state.end_date < state.start_date || state.end_date > state.start_date.Value.AddDays(365))
        throw new InvalidOperationException("查询日期范围不能超过 365 天");
    if (state.rent_status != null && !RentStatuses.Contains(state.rent_status))
        throw new InvalidOperationException("租赁状态不支持");
    if (state.cell_suffix != null && (state.cell_suffix.Length < 4 || !state.cell_suffix.All(char.IsDigit)))
        throw new InvalidOperationException("手机号条件不合法");
}
```

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter AdminAssistantProtocolRulesTests`

Expected: PASS。

- [ ] **Step 6: 提交协议规则**

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi
git add Models/AdminAssistant Helpers/AdminAssistantProtocolRules.cs SnowmeetApi.Tests/AdminAssistantProtocolRulesTests.cs
git commit -m "feat: validate admin assistant v1 actions"
```

### Task 4: SnowmeetApi 全量租赁查询与聚合

**Files:**
- Create: `SnowmeetApi/Services/AdminAssistant/IRentalOrderQueryExecutor.cs`
- Create: `SnowmeetApi/Services/AdminAssistant/RentalOrderQueryExecutor.cs`
- Create: `SnowmeetApi/Helpers/RentalOrderAssistantSummary.cs`
- Create: `SnowmeetApi/SnowmeetApi.Tests/RentalOrderAssistantSummaryTests.cs`
- Modify: `SnowmeetApi/Startup.cs:56-76`

**Interfaces:**
- Consumes: Task 3 的 `RentalOrderQueryState`、指标和分组列表；现有 `OrderController.GetCommonOrders()` 和 `OrderQueryRules.FilterByCustomerCellSuffix()`。
- Produces: `IRentalOrderQueryExecutor.ExecuteAsync(state, metrics, groupBy, cancellationToken) -> RentalOrderQueryExecution`；execution 仅含完整 state、总量汇总和分组，不含订单明细。

- [ ] **Step 1: 写全量指标与分组失败测试**

```csharp
[Fact]
public void 汇总不截断200单并可按状态门店分组()
{
    string[] allMetrics = { "order_count", "charge_total", "paid_total", "refund_total", "unpaid_count" };
    List<RentalOrderAggregateRow> rows = Enumerable.Range(1, 250)
        .Select(i => new RentalOrderAggregateRow(i, i % 2 == 0 ? "万龙" : "南山", D("2026-04-01"), i % 3 == 0 ? "未支付" : "全部归还", 100, 80, 5, i % 3 == 0))
        .ToList();
    RentalOrderQuerySummary summary = RentalOrderAssistantSummary.Build(rows, allMetrics, new[] { "shop", "rent_status" });
    Assert.Equal(250, summary.metrics["order_count"]);
    Assert.Equal(25000d, summary.metrics["charge_total"]);
    Assert.Equal(4, summary.groups.Count);
}
```

测试类定义 `private static DateTime D(string value) => DateTime.Parse(value, CultureInfo.InvariantCulture);`。

- [ ] **Step 2: 运行测试确认汇总器不存在**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter RentalOrderAssistantSummaryTests`

Expected: FAIL，编译错误指出 `RentalOrderAssistantSummary` 不存在。

- [ ] **Step 3: 实现纯聚合器**

```csharp
public sealed record RentalOrderAggregateRow(
    int OrderId, string Shop, DateTime BizDate, string RentStatus,
    double ChargeTotal, double PaidTotal, double RefundTotal, bool IsUnpaid);

public static RentalOrderQuerySummary Build(
    IReadOnlyCollection<RentalOrderAggregateRow> rows,
    IReadOnlyCollection<string> metrics,
    IReadOnlyList<string> groupBy)
{
    Dictionary<string, double> values = new();
    if (metrics.Contains("order_count")) values["order_count"] = rows.Count;
    if (metrics.Contains("charge_total")) values["charge_total"] = rows.Sum(x => x.ChargeTotal);
    if (metrics.Contains("paid_total")) values["paid_total"] = rows.Sum(x => x.PaidTotal);
    if (metrics.Contains("refund_total")) values["refund_total"] = rows.Sum(x => x.RefundTotal);
    if (metrics.Contains("unpaid_count")) values["unpaid_count"] = rows.Count(x => x.IsUnpaid);
    return new RentalOrderQuerySummary(values, BuildGroups(rows, groupBy, metrics));
}
```

`BuildGroups` 按请求顺序生成 key（`biz_date` 使用 `yyyy-MM-dd`），每个 bucket 复用同一指标计算函数；空 `group_by` 返回空数组。

- [ ] **Step 4: 实现只读查询执行器且删除 200 单截断**

```csharp
List<Order> orders = await orderController.GetCommonOrders(
    null, state.shop, null, null, "租赁", state.start_date, state.end_date,
    null, state.is_test, state.is_entertain, null, null, state.have_discount,
    null, null, null, null, state.keyword, null, null, null, state.use_card,
    state.cell_suffix, state.rent_status, state.has_retail);
orders = OrderQueryRules.FilterByCustomerCellSuffix(orders, state.cell_suffix);
List<RentalOrderAggregateRow> rows = orders.Select(o => new RentalOrderAggregateRow(
    o.id, o.shop, o.biz_date, o.rentProperties?.rentStatus ?? "临时订单",
    o.totalCharge, o.paidAmount, o.refundAmount,
    o.paidAmount < o.totalCharge && o.closed == 0)).ToList();
return new RentalOrderQueryExecution(state, RentalOrderAssistantSummary.Build(rows, metrics, groupBy));
```

执行查询前校验门店属于权威租赁门店列表：

```csharp
if (state.shop != null && !await _db.shop.AsNoTracking().AnyAsync(
        shop => shop.rent == 1 && shop.name == state.shop, cancellationToken))
    throw new InvalidOperationException("租赁门店不支持");
```

不得调用 `Take(200)`；不得把 `orders` 写入返回 DTO 或 finalize request。注册 `IRentalOrderQueryExecutor` 为 scoped。

- [ ] **Step 5: 跑聚合及现有订单查询规则测试**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter "RentalOrderAssistantSummaryTests|OrderQueryRulesTests"`

Expected: PASS，250 单用例仍返回 `order_count=250`。

- [ ] **Step 6: 提交查询执行器**

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi
git add Services/AdminAssistant Helpers/RentalOrderAssistantSummary.cs SnowmeetApi.Tests/RentalOrderAssistantSummaryTests.cs Startup.cs
git commit -m "feat: aggregate complete rental query results"
```

### Task 5: SnowmeetApi reqai 客户端与结构化编排服务

**Files:**
- Create: `SnowmeetApi/Services/AdminAssistant/IReqaiAdminAssistantClient.cs`
- Create: `SnowmeetApi/Services/AdminAssistant/ReqaiAdminAssistantClient.cs`
- Create: `SnowmeetApi/Services/AdminAssistant/AdminAssistantService.cs`
- Create: `SnowmeetApi/SnowmeetApi.Tests/AdminAssistantServiceTests.cs`
- Modify: `SnowmeetApi/Startup.cs:56-76`

**Interfaces:**
- Consumes: Task 2 reqai endpoints、Task 3 规则、Task 4 查询执行器。
- Produces: `IAdminAssistantService.AskAsync(request, staff, traceId, structuredEnabled, cancellationToken) -> AdminAssistantExecutionResult`；`response` 成功时始终包含非空 reply，执行 query 时只返回固定 `rental_order.show_results`；`audit` 保存原始 planner JSON、验证结论、完整条件、汇总和错误供 controller 落库。

- [ ] **Step 1: 写文字、查询、finalize 回退和权限失败测试**

```csharp
[Fact]
public async Task 查询action执行后被转换且不会原样下发()
{
    FakeReqaiClient reqai = new(plan: QueryPlan("rental_order.query"), final: Reply("共 12 单。"));
    FakeQueryExecutor query = new(Summary(orderCount: 12));
    AdminAssistantResponse result = (await Service(reqai, query).AskAsync(Request(), Staff(level: 100), "trace", true, default)).response;
    Assert.Equal("共 12 单。", result.reply.text);
    Assert.Equal("rental_order.show_results", Assert.Single(result.actions).type);
    Assert.DoesNotContain(result.actions, x => x.type == "rental_order.query");
}

[Fact]
public async Task Finalize失败仍返回确定性汇总和成功action()
{
    FakeReqaiClient reqai = new(plan: QueryPlan(), finalizeError: new HttpRequestException());
    AdminAssistantResponse result = (await Service(reqai, new FakeQueryExecutor(Summary(12))).AskAsync(Request(), Staff(100), "trace", true, default)).response;
    Assert.Contains("12", result.reply.text);
    Assert.Equal("completed", Assert.Single(result.actions).status);
}

[Theory]
[InlineData(99, true)]
[InlineData(199, false)]
public async Task 权限按action而不是统一门槛判断(int level, bool query)
{
    await Assert.ThrowsAsync<AdminAssistantPermissionException>(() =>
        Service(query ? QueryPlanClient() : TextPlanClient(), FakeQuery()).AskAsync(Request(), Staff(level), "trace", true, default));
}
```

测试文件中的构造器必须使用以下确定值：`Request()` 返回 page `pages/admin/member/member_list`、问题“查询今年四月租赁订单”、空 conversation/context；`Staff(level)` 返回 `id=7,title_level=level`；`Summary(n)` 返回 `order_count=n` 且其余金额为 0。`FakeReqaiClient` 实现下面四个接口方法并从构造参数返回值或抛出 `finalizeError`；`FakeQueryExecutor` 实现 Task 4 接口并返回构造时传入的 summary：

```csharp
public interface IReqaiAdminAssistantClient
{
    Task<string> PlanAsync(ReqaiPlanRequest request, CancellationToken cancellationToken);
    Task<AssistantReply> FinalizeAsync(ReqaiFinalizeRequest request, CancellationToken cancellationToken);
    Task<LegacyRentIntent> LegacyRentIntentAsync(string question, CancellationToken cancellationToken);
    Task<AssistantReply> LegacyPageHelpAsync(AdminAssistantRequest request, int staffId, string traceId, CancellationToken cancellationToken);
}

public interface IAdminAssistantService
{
    Task<AdminAssistantExecutionResult> AskAsync(AdminAssistantRequest request, Staff staff, string traceId, bool structuredEnabled, CancellationToken cancellationToken);
}

public sealed class AdminAssistantExecutionResult
{
    public AdminAssistantResponse response { get; init; } = new();
    public AdminAssistantAuditData audit { get; init; } = new();
}
```

`QueryPlanClient()` 是 `new FakeReqaiClient(plan: QueryPlan("rental_order.query"))`，`TextPlanClient()` 是 `new FakeReqaiClient(plan: TextPlan("页面说明"))`，`FakeQuery()` 是 `new FakeQueryExecutor(Summary(0))`。`Service(reqai, query)` 精确返回 `new AdminAssistantService(reqai, query)`。

- [ ] **Step 2: 运行测试确认服务不存在**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter AdminAssistantServiceTests`

Expected: FAIL，编译错误指出 `AdminAssistantService` 不存在。

- [ ] **Step 3: 实现带服务 token 的 reqai 客户端**

```csharp
private async Task<string> PostAsync(string path, object body, CancellationToken cancellationToken)
{
    string baseUrl = _configuration["Reqai:BaseUrl"]?.TrimEnd('/') ?? "";
    string token = _configuration["Reqai:ServiceToken"] ?? "";
    if (baseUrl.Length == 0 || token.Length == 0)
        throw new InvalidOperationException("reqai 服务地址或服务凭据未配置");
    using HttpRequestMessage request = new(HttpMethod.Post, baseUrl + path)
    {
        Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json")
    };
    request.Headers.Add("X-Snowmeet-Service-Token", token);
    using HttpResponseMessage response = await _httpClientFactory.CreateClient("Reqai").SendAsync(request, cancellationToken);
    string payload = await response.Content.ReadAsStringAsync(cancellationToken);
    if (!response.IsSuccessStatusCode) throw new ReqaiException((int)response.StatusCode, payload);
    return payload;
}
```

提供 `PlanAsync`、`FinalizeAsync`、`LegacyRentIntentAsync` 和 `LegacyPageHelpAsync` 四个明确方法，不提供任意 URL 调用方法给编排层。

- [ ] **Step 4: 实现 structured 编排和确定性回退**

```csharp
ReqaiPlanResponse plan = AdminAssistantProtocolRules.ParsePlan(
    await _reqai.PlanAsync(BuildPlanRequest(request, staff, traceId), cancellationToken));
if (plan.actions.Count == 0)
{
    RequireLevel(staff, 200);
    AdminAssistantResponse response = TextOnly(traceId, plan.reply!, request.context);
    return new AdminAssistantExecutionResult { response = response, audit = AuditForText(plan) };
}
RequireLevel(staff, 100);
ReqaiQueryAction action = plan.actions.Single();
RentalOrderQueryState state = AdminAssistantProtocolRules.Merge(action.mode, request.context.rental_order_query, action.arguments);
AdminAssistantProtocolRules.ValidateQuery(state);
RentalOrderQueryExecution execution = await _query.ExecuteAsync(state, action.metrics, action.group_by, cancellationToken);
AssistantReply finalReply;
try { finalReply = await _reqai.FinalizeAsync(BuildFinalizeRequest(request, plan.reply, execution), cancellationToken); }
catch (Exception error) when (error is ReqaiException or HttpRequestException or TaskCanceledException)
{ finalReply = DeterministicReply(execution.summary); }
AdminAssistantResponse completed = CompletedQuery(traceId, action.id, finalReply, execution);
return new AdminAssistantExecutionResult
{
    response = completed,
    audit = AuditForQuery(plan, state, execution.summary)
};
```

`BuildFinalizeRequest` 的类型没有订单数组属性。`CompletedQuery` 始终写入完整 query state 和 summary；规划 reply 只传给 finalize，不与最终文字拼接。`AuditForText`/`AuditForQuery` 构造的 `AdminAssistantAuditData` 固定包含 `planner_json`、`validation_result`、`query`、`summary` 和 `error`；文字路径的 query/summary 为 null，成功查询路径的 `validation_result="accepted"`，不得包含订单集合。

- [ ] **Step 5: 注册服务并跑测试**

```csharp
services.AddScoped<IReqaiAdminAssistantClient, ReqaiAdminAssistantClient>();
services.AddScoped<IAdminAssistantService, AdminAssistantService>();
```

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter AdminAssistantServiceTests`

Expected: PASS。

- [ ] **Step 6: 提交结构化编排**

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi
git add Services/AdminAssistant SnowmeetApi.Tests/AdminAssistantServiceTests.cs Startup.cs
git commit -m "feat: orchestrate structured admin assistant queries"
```

### Task 6: SnowmeetApi 统一控制器、审计与关闭开关兼容路径

**Files:**
- Modify: `SnowmeetApi/Controllers/AdminAiController.cs:21-294`
- Modify: `SnowmeetApi/appsettings.json`
- Create: `SnowmeetApi/SnowmeetApi.Tests/AdminAssistantLegacyAdapterTests.cs`
- Modify: `SnowmeetApi/Services/AdminAssistant/AdminAssistantService.cs`

**Interfaces:**
- Consumes: Task 5 `IAdminAssistantService` 和旧 reqai 两个接口。
- Produces: `POST api/AdminAi/AskAdminAssistantByStaff`；始终返回 `ApiResult<AdminAssistantResponse>`；旧三个 controller action 不变。

- [ ] **Step 1: 写关闭开关兼容和审计字段失败测试**

```csharp
[Fact]
public async Task 开关关闭时查询先走旧意图并转换为v1响应()
{
    FakeReqaiClient reqai = new(legacyIntent: ReadyIntent("2026-04-01", "2026-04-30"));
    AdminAssistantResponse response = (await LegacyService(reqai, Summary(3)).AskAsync(Request(), Staff(100), "trace", false, default)).response;
    Assert.Equal("1", response.version);
    Assert.Equal("rental_order.show_results", Assert.Single(response.actions).type);
}

[Fact]
public async Task 开关关闭时unsupported意图回退旧页面帮助()
{
    FakeReqaiClient reqai = new(legacyIntent: UnsupportedIntent(), legacyHelp: "这里是页面说明。");
    AdminAssistantResponse response = (await LegacyService(reqai, Summary(0)).AskAsync(Request("这个页面怎么用"), Staff(200), "trace", false, default)).response;
    Assert.Equal("这里是页面说明。", response.reply.text);
    Assert.Empty(response.actions);
}
```

- [ ] **Step 2: 运行测试确认兼容分支不存在**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter AdminAssistantLegacyAdapterTests`

Expected: FAIL，断言显示服务仍调用 structured planner 或没有 legacy 方法。

- [ ] **Step 3: 实现服务端 legacy adapter**

```csharp
private async Task<AdminAssistantExecutionResult> AskLegacyAsync(AdminAssistantRequest request, Staff staff, string traceId, CancellationToken ct)
{
    LegacyRentIntent intent = await _reqai.LegacyRentIntentAsync(request.question, ct);
    if (intent.status == "ready")
    {
        RequireLevel(staff, 100);
        RentalOrderQueryState state = LegacyIntentToState(intent);
        AdminAssistantProtocolRules.ValidateQuery(state);
        RentalOrderQueryExecution execution = await _query.ExecuteAsync(state, DefaultMetrics, Array.Empty<string>(), ct);
        AdminAssistantResponse response = CompletedQuery(traceId, "legacy_query", DeterministicReply(execution.summary), execution);
        return new AdminAssistantExecutionResult { response = response, audit = AuditForLegacyQuery(intent, state, execution.summary) };
    }
    if (intent.status == "clarification_required")
    {
        AdminAssistantResponse response = TextOnly(traceId, new AssistantReply { text = intent.clarification ?? "请补充查询日期范围。" }, request.context);
        return new AdminAssistantExecutionResult { response = response, audit = AuditForLegacyIntent(intent) };
    }
    RequireLevel(staff, 200);
    AssistantReply help = await _reqai.LegacyPageHelpAsync(request, staff.id, traceId, ct);
    return new AdminAssistantExecutionResult
    {
        response = TextOnly(traceId, help, request.context),
        audit = AuditForLegacyHelp(intent)
    };
}
```

该分支不使用小程序关键词；旧意图返回 unsupported 后才调用旧页面帮助。

- [ ] **Step 4: 新增统一 controller action 和完整审计**

```csharp
[HttpPost]
public async Task<ActionResult<ApiResult<AdminAssistantResponse>>> AskAdminAssistantByStaff(
    [FromBody] AdminAssistantRequest request, string sessionKey,
    string sessionType = "wechat_mini_openid", CancellationToken cancellationToken = default)
{
    ValidateClientRequest(request);
    Staff? staff = await Util.GetStaffBySessionKey(_db, sessionKey, sessionType);
    if (staff == null) return Ok(new ApiResult<AdminAssistantResponse> { code = 1, message = "没有权限" });
    string traceId = Guid.NewGuid().ToString("N");
    bool enabled = _config.GetValue<bool>("AdminAssistant:StructuredProtocolEnabled");
    return await ExecuteAndAudit(request, staff, traceId, enabled, sessionType, cancellationToken);
}
```

`ValidateClientRequest` 必须执行以下确定校验：`version == "1"`；`page_key` 以 `pages/admin/` 开头且长度不超过 255；`question.Trim()` 长度为 1 到 2000；conversation 最多 20 条、role 仅为 user/assistant、每条 content 最多 2000 字且合计不超过 12000 字。失败统一返回 HTTP 400 和 `ApiResult.code=1`，不能调用 reqai。

`ExecuteAndAudit` 从 `AdminAssistantExecutionResult.audit` 取得原始 planner JSON、验证结果、完整筛选和汇总，并使用现有 `admin_ai_request_log`：`operation="admin_assistant"`，记录员工、页面、问题、response、HTTP 状态、耗时和 error；删除 token/Cookie/订单明细后再序列化。查询失败不返回 completed action；澄清返回文字且 action 为空。

- [ ] **Step 5: 增加初始关闭配置并验证旧 action 保留**

```json
"AdminAssistant": {
  "StructuredProtocolEnabled": false
}
```

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter "AdminAssistant"`

Expected: PASS；编译时旧 `GetPageHelpByStaff`、`AskPageHelpByStaff`、`QueryRentOrdersByNaturalLanguage` 仍存在。

- [ ] **Step 6: 跑 SnowmeetApi 全量测试并提交**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi && dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj`

Expected: 全部 PASS。

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi
git add Controllers/AdminAiController.cs Services/AdminAssistant/AdminAssistantService.cs appsettings.json SnowmeetApi.Tests/AdminAssistantLegacyAdapterTests.cs
git commit -m "feat: expose unified admin assistant endpoint"
```

### Task 7: 小程序协议客户端、会话上下文与固定 action executor

**Files:**
- Create: `snowmeet_wechat_mini/utils/adminAssistant.js`
- Create: `snowmeet_wechat_mini/tests/admin_assistant.test.js`
- Modify: `snowmeet_wechat_mini/utils/data.js:502-520,1766-1768`
- Modify: `snowmeet_wechat_mini/utils/adminAiQuery.js:1-58`
- Modify: `snowmeet_wechat_mini/tests/admin_ai_query.test.js:1-72`

**Interfaces:**
- Consumes: SnowmeetApi v1 response。
- Produces: `buildRequest(pageKey, question, conversation, staff)`、`acceptContext(staff, context)`、`currentContext(staff)`、`executeActions(actions, navigateTo)`、`clearContext()`；`data.askAdminAssistantPromise(request, sessionKey)`。

- [ ] **Step 1: 写上下文隔离与 action 白名单失败测试**

```javascript
test('同一员工连续提问携带完整查询上下文', () => {
  assistant.acceptContext({ id: 7 }, { rental_order_query: aprilUnpaid })
  const request = assistant.buildRequest('pages/admin/member/member_list', '改成五月份', [], { id: 7 })
  assert.deepEqual(request.context.rental_order_query, aprilUnpaid)
})

test('切换员工清除上下文', () => {
  assistant.acceptContext({ id: 7 }, { rental_order_query: aprilUnpaid })
  assert.equal(assistant.currentContext({ id: 8 }).rental_order_query, null)
})

test('只执行完成的租赁结果action', () => {
  const urls = []
  assistant.executeActions([{ type: 'rental_order.show_results', status: 'completed', state: aprilUnpaid }], url => urls.push(url))
  assert.match(urls[0], /^\/pages\/admin\/rent\/new_rent_list\?aiIntent=/)
  assert.throws(() => assistant.executeActions([{ type: 'refund.execute', status: 'completed' }], () => {}), /暂不支持/)
})
```

- [ ] **Step 2: 运行测试确认模块不存在**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini && node --test tests/admin_assistant.test.js`

Expected: FAIL，错误包含 `Cannot find module '../utils/adminAssistant.js'`。

- [ ] **Step 3: 实现运行期会话存储和请求构造**

```javascript
let ownerStaffId = null
let context = { rental_order_query: null }

function syncStaff(staff) {
  const next = staff && staff.id != null ? String(staff.id) : null
  if (next !== ownerStaffId) {
    ownerStaffId = next
    context = { rental_order_query: null }
  }
}

function buildRequest(pageKey, question, conversation, staff) {
  syncStaff(staff)
  return {
    version: '1', page_key: pageKey, question,
    conversation: (conversation || []).slice(-20),
    context: JSON.parse(JSON.stringify(context))
  }
}
```

`acceptContext` 先 `syncStaff` 再复制 SnowmeetApi 返回的 context。`clearContext` 在退出/失去员工身份时调用；模块不写本地持久化，进程重启自然清空。

- [ ] **Step 4: 实现固定 action executor 和统一 API 方法**

```javascript
function executeActions(actions, navigateTo) {
  ;(actions || []).forEach(function (action) {
    if (action.type !== 'rental_order.show_results' || action.status !== 'completed') {
      throw new Error('当前版本暂不支持此操作，请升级后重试')
    }
    navigateTo(adminAiQuery.buildRentOrderListUrl(action.state))
  })
}

const askAdminAssistantPromise = function (request, sessionKey) {
  var url = app.globalData.requestPrefix + 'AdminAi/AskAdminAssistantByStaff?sessionKey=' + encodeURIComponent(sessionKey)
    + '&sessionType=' + encodeURIComponent('wechat_mini_openid')
  return util.performWebRequest(url, request)
}
```

删除 `isRentOrderDataQuery` 导出和对应关键词测试；保留 `buildRentOrderListUrl`、`readRentOrderIntent`、`buildRentOrderListState`。在 state 映射中将 `hasRetail` 改为 `_nullable(intent.has_retail)`。

- [ ] **Step 5: 运行工具层测试并提交**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini && node --test tests/admin_assistant.test.js tests/admin_ai_query.test.js`

Expected: PASS。

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini
git add utils/adminAssistant.js utils/adminAiQuery.js utils/data.js tests/admin_assistant.test.js tests/admin_ai_query.test.js
git commit -m "feat: add admin assistant v1 client executor"
```

### Task 8: 小程序帮助组件统一提问并跳转完整筛选结果

**Files:**
- Modify: `snowmeet_wechat_mini/components/admin-page-help/index.js:1-168`
- Modify: `snowmeet_wechat_mini/components/admin-page-help/index.wxml:1-40`
- Modify: `snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js:1-140`
- Modify: `snowmeet_wechat_mini/tests/admin_page_help_component.test.js:1-130`
- Create: `snowmeet_wechat_mini/tests/new_rent_list_ai_state.test.js`

**Interfaces:**
- Consumes: Task 7 `adminAssistant` 和 `data.askAdminAssistantPromise()`。
- Produces: 所有帮助输入统一走 v1；组件显示 `reply.text`、保存 context、执行 action；租赁列表完整应用 11 个查询字段。

- [ ] **Step 1: 重写组件测试使其要求单一统一调用**

```javascript
test('四月租赁查询显示服务端文字保存上下文并跳转', async () => {
  const component = loadComponentWithData({
    askAdminAssistantPromise: async request => {
      assert.equal(request.question, '请查询一下今年4月份的租赁订单')
      return responseWithReplyActionAndContext()
    }
  })
  component.data.input = '请查询一下今年4月份的租赁订单'
  await component.sendQuestion()
  assert.equal(component.data.messages.at(-1).content, '共查询到 12 单。')
  assert.match(navigatedUrl, /^\/pages\/admin\/rent\/new_rent_list\?aiIntent=/)
})

test('普通帮助和条件回顾也只调用统一接口', async () => {
  await ask(component, '这个页面怎么操作')
  await ask(component, '当前查询条件是什么')
  assert.equal(unifiedCalls, 2)
  assert.equal(legacyHelpCalls, 0)
  assert.equal(legacyQueryCalls, 0)
})
```

- [ ] **Step 2: 运行测试确认旧关键词分流导致失败**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini && node --test tests/admin_page_help_component.test.js`

Expected: FAIL，旧实现仍调用 `queryRentOrdersByNaturalLanguagePromise` 或 `askAdminPageHelpPromise`。

- [ ] **Step 3: 将初始页面说明和所有追问改为统一协议**

```javascript
async ask(question, appendUserMessage) {
  var app = getApp()
  await app.loginPromiseNew
  var conversation = this.data.messages
  var request = adminAssistant.buildRequest(this.data.pageKey, question, conversation, app.globalData.staff)
  var result = await data.askAdminAssistantPromise(request, app.globalData.sessionKey)
  adminAssistant.acceptContext(app.globalData.staff, result.context)
  var next = appendUserMessage ? conversation.concat([{ role: 'user', content: question }]) : conversation.slice()
  next.push({ role: 'assistant', content: result.reply.text, citations: result.reply.citations || [] })
  this.setData({ messages: next, pageHelp: result.reply, input: '', loading: false })
  adminAssistant.executeActions(result.actions, url => wx.navigateTo({ url }))
}
```

`loadPageHelp()` 调用同一方法，问题固定为“请说明当前页面的用途、标准操作步骤、关键限制和常见错误。”且不添加伪造用户消息。`sendQuestion()` 不检查 queryMode/关键词。查询按钮只把输入提示改为“例如：请查询今年四月份的租赁订单”，不切换路由状态。

- [ ] **Step 4: 完整应用列表 state 并写页面测试**

```javascript
test('列表将has_retail和全部AI筛选送入分页查询', () => {
  const state = adminAiQuery.buildRentOrderListState({
    start_date: '2026-04-01', end_date: '2026-04-30', shop: '万龙',
    rent_status: '未支付', is_test: false, is_entertain: true,
    have_discount: false, use_card: true, has_retail: true,
    cell_suffix: '7788', keyword: '雪板'
  })
  assert.equal(option(state, 'hasRetail'), true)
  assert.equal(state.cell, '7788')
  assert.equal(state.keyword, '雪板')
})
```

`new_rent_list.js` 保留现有分页 API；`onLoad` 用完整 state 初始化控件，`_buildQueryParams` 将 `hasRetail`、手机号后缀、关键词、门店、日期和全部布尔条件原样送出，AI state 下不触发手机号/关键词的默认日期重置。

- [ ] **Step 5: 未知 action 保留文字并显示升级提示**

```javascript
try {
  adminAssistant.executeActions(result.actions, url => wx.navigateTo({ url }))
} catch (error) {
  this.setData({ error: '当前版本暂不支持此操作，请升级后重试' })
}
```

该异常不能删除已经加入的 `reply.text`，也不能发起跳转。

- [ ] **Step 6: 跑小程序全量测试并提交**

Run: `cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini && npm test`

Expected: 全部 PASS，测试中不存在关键词分流断言。

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini
git add components/admin-page-help pages/admin/rent/new_rent_list.js tests/admin_page_help_component.test.js tests/new_rent_list_ai_state.test.js
git commit -m "feat: route admin help through structured assistant"
```

### Task 9: 跨仓验证、开关验收与发布记录

**Files:**
- Create: `snowmeet_ai_doc/sessions/2026-09-10_admin_assistant_command_protocol.md`

**Interfaces:**
- Consumes: Tasks 1-8 的三个仓库提交。
- Produces: 可复现测试结果、开关打开/关闭验收证据和发布顺序；不在本任务自动修改生产配置。

- [ ] **Step 1: 运行三个仓库全量自动测试**

```bash
cd /Users/cangjie/Projects/snowmeet/reqai/backend
pytest -q

cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi
dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj

cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini
npm test
```

Expected: 三组测试全部 PASS；记录每组通过数量和命令输出摘要。

- [ ] **Step 2: 用本地 stub 验证 structured 开启链路**

依次让 stub planner 返回：纯文字、四月查询、`patch` 未支付、`patch` 改五月、查询条件回顾、未知 action、三个 group_by。验证预期分别是：文字无跳转；查询文字加跳转；条件被保留/替换；完整列出 11 条条件；未知 action 被 SnowmeetApi 拒绝；三个分组被 SnowmeetApi 拒绝。

Run:

```bash
: "${ADMIN_ASSISTANT_TEST_SESSION:?请先设置本地测试员工 sessionKey}"
curl -k -sS -X POST "https://localhost:5001/api/AdminAi/AskAdminAssistantByStaff?sessionKey=${ADMIN_ASSISTANT_TEST_SESSION}" \
  -H 'Content-Type: application/json' \
  --data '{"version":"1","page_key":"pages/admin/member/member_list","question":"请查询今年四月份的租赁订单","conversation":[],"context":{"rental_order_query":null}}'
```

Expected: 成功查询响应只有 `rental_order.show_results`，`context.rental_order_query` 为完整合并状态，summary 数量不受 200 限制。执行人员使用自己的本地端口和测试 session，不把值提交到仓库。

- [ ] **Step 3: 验证关闭开关兼容链路**

将本地 `AdminAssistant:StructuredProtocolEnabled=false`，对统一接口分别发送“请查询今年四月份的租赁订单”和“这个页面怎么操作”。

Expected: 前者通过旧 rent intent 转换成 v1 查询结果并跳转；后者通过旧 page-help 转换成 v1 文字；小程序两次都只调用统一 SnowmeetApi 接口。

- [ ] **Step 4: 检查日志与敏感数据边界**

检查 `admin_ai_request_log` 最近两条记录以及 reqai `snowmeet_help_invocations` 的 plan/finalize 记录。

Expected: 有 trace、staff、page、问题、action、条件、汇总、耗时和错误状态；没有 service token、Cookie、订单数组、姓名、完整手机号、openid 或支付流水。

- [ ] **Step 5: 写发布记录和明确上线顺序**

发布记录写入以下固定章节，并从对应命令的真实输出逐字记录哈希和通过数量：

```markdown
# 2026-09-10 管理员帮助结构化指令协议

## 构建版本

记录 `git -C /Users/cangjie/Projects/snowmeet/reqai rev-parse --short HEAD`、`git -C /Users/cangjie/Projects/snowmeet/snowmeet_ai/SnowmeetApi rev-parse --short HEAD` 和 `git -C /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_wechat_mini rev-parse --short HEAD` 的输出。

## 自动测试

记录本任务 Step 1 三条全量测试命令各自的通过数量。

## 验收结论

记录四月查询、连续 patch、条件回顾、纯帮助、finalize 故障、未知 action、关闭开关各自的实际结果。

## 发布与回滚

发布顺序为 reqai → SnowmeetApi（开关 false）→ 小程序 → 小范围打开开关 → 全量打开。回滚只关闭 `AdminAssistant:StructuredProtocolEnabled`；不回滚数据库，不恢复客户端关键词分流。
```

- [ ] **Step 6: 提交验证记录**

```bash
cd /Users/cangjie/Projects/snowmeet/snowmeet_ai/snowmeet_ai_doc
git add sessions/2026-09-10_admin_assistant_command_protocol.md
git commit -m "docs: record admin assistant protocol verification"
```

生产启用、push 和部署在测试与人工验收通过后按用户明确指令执行；本实施计划本身不授权生产变更。
