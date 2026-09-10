# 管理员帮助系统：答复与操作指令协议设计

日期：2026-09-10  
状态：设计已确认，待实现计划

## 1. 背景

当前管理员帮助系统存在两条割裂的链路：普通问题进入页面操作帮助，租赁订单查询依赖小程序关键词判断和专用查询接口。该做法只能覆盖少量固定表达，无法支持连续筛选、查询条件回顾以及未来更多受控操作。

目标是让所有帮助问题先进入 reqai，由 reqai 返回结构化的“文字答复”和“业务操作指令”。SnowmeetApi 负责校验、执行和审计；小程序只显示 SnowmeetApi 返回的文字，并执行 SnowmeetApi 签发的客户端指令。

## 2. 目标

第一版实现以下能力：

1. reqai 的一次响应可以只有文字、只有操作指令，或两者兼有。
2. 当前只允许 `rental_order.query` 一种业务操作。
3. 用户可以从任意管理员页面发起租赁订单查询。
4. 查询完成后，小程序跳转到租赁订单列表，显示完整查询条件和匹配订单。
5. 用户可以继续用自然语言增量修改条件，例如“只看未支付的”或“改成五月份”。
6. 用户可以随时询问“当前查询条件是什么”，获得完整的自然语言说明。
7. SnowmeetApi 基于全部匹配订单计算汇总，并由 reqai 根据真实汇总生成最终文字答复。
8. 新协议可通过配置开关关闭，并回退到现有帮助和查询链路。

## 3. 非目标与永久安全边界

- 第一版不实现开单、盘点或任何写操作。
- 未来开单、盘点等能力必须作为新的白名单操作单独设计、实现和验收，不能复用一个通用“执行任意操作”入口。
- 退款、资金划转、删除、作废等高风险动作永久不允许通过自然语言触发。
- reqai 不生成 SQL、API URL、小程序路由、代码或脚本。
- 小程序不直接执行 reqai 的原始输出。
- 第一版不新增服务端会话表；查询上下文只在当前小程序会话内传递。

## 4. 总体架构

采用 SnowmeetApi 统一编排的两阶段流程：

```text
小程序
  │  问题 + 当前页面 + 对话 + 查询上下文
  ▼
SnowmeetApi / AskAdminAssistantByStaff
  │  身份认证、补充当前日期/时区、生成 trace_id
  ▼
reqai / admin-assistant/plan
  │  返回 reply + semantic actions
  ▼
SnowmeetApi
  │  操作白名单校验、参数合并、权限校验、查询、汇总
  ▼
reqai / admin-assistant/finalize
  │  只接收查询条件和汇总，不接收订单明细
  ▼
SnowmeetApi
  │  返回最终 reply + 已签发的 client actions + context
  ▼
小程序
     显示 reply；执行 rental_order.show_results
```

文字问题没有操作指令时，SnowmeetApi 不执行第二阶段业务查询，直接返回 reqai 的文字答复。

存在操作指令时，规划阶段的 `reply` 只作为执行意图说明，不作为查询结果。SnowmeetApi 必须在执行完成后用 finalize 答复替换它；如果 finalize 失败，则用确定性模板替换。这样即使 reqai 的规划响应只有 action，统一响应也一定包含基于真实结果生成的文字答复，不会只显示“我来查询”。

## 5. 请求协议

小程序统一调用 `AdminAi/AskAdminAssistantByStaff`：

```json
{
  "version": "1",
  "page_key": "pages/admin/member/member_list",
  "question": "请查询今年四月份的租赁订单",
  "conversation": [
    { "role": "user", "content": "上一轮问题" },
    { "role": "assistant", "content": "上一轮答复" }
  ],
  "context": {
    "rental_order_query": null
  }
}
```

SnowmeetApi 不信任客户端传入的身份、日期或时区。它通过 `sessionKey` 推导员工身份，并加入：

- `staff_id`
- `trace_id`
- `current_date`
- `timezone`，固定为 `Asia/Shanghai`

对话最多携带最近 20 条，单条及总长度沿用现有帮助接口限制。

## 6. reqai 规划响应

reqai 使用严格 Pydantic schema 返回：

```json
{
  "version": "1",
  "reply": {
    "text": "我来查询今年四月份的租赁订单。",
    "citations": []
  },
  "actions": [
    {
      "id": "action_1",
      "type": "rental_order.query",
      "mode": "replace",
      "arguments": {
        "start_date": "2026-04-01",
        "end_date": "2026-04-30"
      },
      "aggregation": {
        "metrics": [
          "order_count",
          "charge_total",
          "paid_total",
          "refund_total",
          "unpaid_count"
        ],
        "group_by": []
      }
    }
  ]
}
```

`reply` 可为 `null`，`actions` 可为空数组，但二者不能同时为空。第一版每轮最多一个 action。

### 6.1 操作白名单

第一版唯一合法操作：

- `rental_order.query`

未知操作、额外字段、非法枚举或超过一个 action 均由 SnowmeetApi 拒绝，不会下发小程序。

### 6.2 查询条件

第一版支持：

- `start_date`
- `end_date`
- `shop`
- `rent_status`
- `is_test`
- `is_entertain`
- `have_discount`
- `use_card`
- `has_retail`
- `cell_suffix`
- `keyword`

日期范围是执行查询的必填条件，不能超过 365 天。门店、状态和布尔条件必须属于 SnowmeetApi 的权威白名单。手机号后缀至少四位且只能包含数字。

### 6.3 汇总白名单

指标：

- `order_count`
- `charge_total`
- `paid_total`
- `refund_total`
- `unpaid_count`

分组：

- `rent_status`
- `shop`
- `biz_date`

第一版最多使用两个分组维度。SnowmeetApi 只计算枚举内的指标和分组。

## 7. 连续筛选语义

### 7.1 replace

`mode = replace` 表示开始一组新查询。未出现的可选条件统一视为“不限制”。

示例：

> 请查询今年四月份的租赁订单。

产生四月日期范围，其余条件为空。

### 7.2 patch

`mode = patch` 表示修改当前查询：

- 字段未出现：保持原值。
- 字段有具体值：替换原值。
- 字段显式为 `null`：清除该条件。

示例：

- “只看未支付的”只设置 `rent_status = 未支付`。
- “改成五月份”只替换起止日期。
- “取消门店限制”设置 `shop = null`。

如果没有现有查询上下文，但 reqai 返回 `patch`，SnowmeetApi 将其按空上下文合并；合并后缺少日期时返回澄清问题，不执行查询。

### 7.3 查询条件说明

用户询问“当前查询条件是什么”时，reqai 返回纯文字答复，不生成 action。答复必须列出：

- 日期范围
- 门店范围
- 状态
- 测试/营业
- 招待
- 减免
- 次卡
- 零售子单
- 手机号后缀
- 关键词

没有限制的字段使用“全部”或“未限制”，不能省略，以免用户忘记隐含条件。

## 8. SnowmeetApi 执行与最终答复

SnowmeetApi 按以下顺序处理：

1. 验证员工身份。
2. 反序列化严格的 reqai 规划响应。
3. 验证协议版本、操作类型、数量和参数。
4. 按 `replace` 或 `patch` 合并查询上下文。
5. 验证完整查询条件和操作权限。
6. 使用现有权威订单查询逻辑读取全部匹配订单。
7. 在分页之前计算请求的汇总和分组。
8. 将问题、完整条件和汇总结果发送给 reqai finalize 接口。
9. 生成小程序可执行的客户端指令。
10. 写入审计日志并返回统一响应。

reqai finalize 只接收筛选条件和汇总 JSON，不接收订单列表、姓名、完整手机号、openid 或支付流水明细。

如果 finalize 失败，SnowmeetApi 使用确定性模板生成结果文字，查询及页面跳转仍然成功。

规划阶段同时返回文字和 action 时，规划文字会作为 finalize 的上下文，但不会与最终答复简单拼接，避免重复、冲突或把执行前推测显示成执行结果。无 action 时，规划文字就是最终答复。

## 9. SnowmeetApi 对小程序的统一响应

```json
{
  "version": "1",
  "trace_id": "4cf2...",
  "reply": {
    "text": "共查询到 126 单，应收 38,200 元，其中未支付 5 单。",
    "citations": []
  },
  "actions": [
    {
      "id": "action_1",
      "type": "rental_order.show_results",
      "status": "completed",
      "state": {
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "shop": null,
        "rent_status": null
      },
      "summary": {
        "order_count": 126,
        "charge_total": 38200,
        "unpaid_count": 5
      }
    }
  ],
  "context": {
    "rental_order_query": {
      "start_date": "2026-04-01",
      "end_date": "2026-04-30",
      "shop": null,
      "rent_status": null
    }
  }
}
```

SnowmeetApi 返回给小程序的 action 不是 reqai 原始 action，而是完成校验和查询后签发的客户端指令。

## 10. 小程序执行规则

帮助组件执行顺序：

1. 将用户问题加入对话。
2. 调统一接口。
3. 显示 `reply.text`。
4. 保存响应中的完整 `context`。
5. 逐项检查客户端 action 白名单。
6. 对 `rental_order.show_results` 跳转租赁订单列表，并传入完整 state。
7. 目标页面使用 state 初始化所有筛选控件，再调用现有分页接口加载订单。

查询上下文按当前登录员工隔离，保存在小程序运行期会话中；退出登录、切换员工或小程序进程被清理时必须清除。第一版不承诺重启小程序后恢复查询上下文。订单分页接口仍独立校验员工权限和所有筛选条件，不能因 state 来自帮助系统而跳过校验。

小程序不再使用关键词或正则判断问题类型。现有“查询数据”按钮可以保留为输入提示入口，但不能改变路由逻辑或绕过统一协议。

如果小程序收到未知 action，它保留文字答复、拒绝执行，并显示“当前版本暂不支持此操作，请升级后重试”。

## 11. 权限与安全

- SnowmeetApi 是唯一执行边界，reqai 没有业务数据库写权限。
- 所有操作使用代码内注册表，不使用配置或模型输出动态注册。
- 第一版 `rental_order.query` 沿用租赁查询的员工权限，最低 `title_level >= 100`。
- 页面帮助文字权限沿用现有规则；统一接口按实际 action 分别校验，不能用文字权限推导操作权限。
- 查询条件在 SnowmeetApi 再验证一次，不能信任 reqai 或小程序。
- 客户端仅接受 SnowmeetApi 签发的固定 action type，不接受 URL、脚本或任意方法名。
- 审计记录包含 trace、员工、页面、问题、规划 action、验证结果、查询条件、汇总和错误；不记录密钥、Cookie 或订单明细。

未来新增操作必须显式定义风险等级、权限、确认策略、幂等规则、审计字段和回滚方式。退款及资金类操作不进入注册表。

## 12. 错误处理

| 场景 | 行为 |
|---|---|
| 条件不完整 | 返回澄清文字，不执行查询、不跳转 |
| reqai 返回未知/非法 action | SnowmeetApi 拒绝，返回安全提示 |
| 查询失败 | 返回查询失败文字和 trace_id，不下发 completed action |
| finalize 失败 | 使用 SnowmeetApi 确定性汇总模板，仍下发成功 action |
| 小程序不认识 action | 显示文字和升级提示，不执行 |
| context 缺失 | 新查询正常；增量查询合并空上下文并按规则澄清 |
| 新协议关闭 | 统一接口通过服务端兼容适配器调用旧 reqai 帮助/租赁意图链路，并仍返回 v1 外层响应；不要求小程序恢复关键词判断 |

任何阶段失败都不能产生部分写操作。第一版只有只读查询，不涉及事务性业务修改。

## 13. 发布与回滚

配置开关命名为：

```text
AdminAssistant:StructuredProtocolEnabled
```

发布顺序：

1. reqai 部署新的 plan/finalize 接口，保留旧 page-help 和 rent-query-intent。
2. SnowmeetApi 部署统一接口和配置开关，初始关闭。
3. 小程序部署 v1 协议解析和 action executor。
4. 开启 SnowmeetApi 配置开关，小范围验收后全面启用。

回滚时先关闭配置开关。旧接口和旧 reqai 路由在本期不删除，因此不需要回滚数据库或代码即可恢复旧流程。本设计不需要 DDL。

配置开关关闭后，SnowmeetApi 的统一接口保留可用，但内部切换到旧 page-help 和 rent-query-intent 兼容适配器，并把结果转换成 v1 响应。旧版本小程序仍可继续调用原有接口；新版本小程序无需重新启用客户端关键词分流。该回退保证关闭开关本身即可生效。

## 14. 测试策略

### reqai

- 纯文字帮助返回 `reply` 且无 action。
- 明确订单查询返回 `rental_order.query`。
- 同时返回文字和 action。
- `replace`、`patch`、显式 `null` 清除条件。
- “当前查询条件是什么”完整描述全部字段。
- 严格 schema 拒绝未知 action、字段、指标和分组。
- finalize 根据给定汇总生成答案，不引用不存在的数据。

### SnowmeetApi

- 协议反序列化和版本校验。
- action 注册表和权限校验。
- replace/patch 合并语义。
- 日期、门店、状态、手机号和查询范围校验。
- 查询统计基于完整结果集而非前 200 单。
- 各指标和分组结果正确。
- finalize 失败时确定性答复回退。
- reqai 原始 action 不直接下发小程序。
- 审计成功、拒绝和失败路径。

### 小程序

- 不再依赖关键词识别。
- 文字-only、action-only、混合响应。
- `rental_order.show_results` 保存 context 并跳转。
- 目标页面筛选控件与 state 一致，分页请求条件一致。
- 连续 patch 后将完整 context 带入下一轮。
- 未知 action 拒绝执行并提示升级。
- 配置关闭时可消费服务端兼容适配后的 v1 响应；不恢复客户端关键词分流。

### 端到端验收

至少覆盖：

1. “请查询今年四月份的租赁订单”。
2. “只看未支付的”。
3. “按门店汇总”。
4. “当前查询条件是什么”。
5. “取消门店限制”。
6. 普通页面操作问题仍返回帮助文字。
7. reqai finalize 故障时仍显示确定性汇总并跳转。
8. 关闭配置开关后恢复旧流程。

## 15. 预计改动范围

### reqai

- 新增管理员助手 plan/finalize 的严格 schema、prompt、router 和测试。
- 复用现有服务认证、模型选择、用量记录和调用日志。

### SnowmeetApi

- 新增统一请求/响应 DTO、action 注册表、查询上下文合并器、租赁查询执行器和汇总器。
- 扩展 `AdminAiController` 编排及审计。
- 保留当前页面帮助和租赁自然语言查询接口。

### snowmeet_wechat_mini

- 帮助组件改为统一请求与统一响应渲染。
- 新增固定客户端 action executor。
- 查询上下文保存到小程序会话，并在跨页面后继续传递。
- 租赁订单列表继续使用现有分页 API，只接收经过 SnowmeetApi 验证的 state。
- 删除客户端问题关键词分流；配置关闭时由 SnowmeetApi 的服务端兼容适配器承接旧链路。

## 16. 后续扩展原则

未来的开单、盘点等能力各自新增独立 action type，不修改 `rental_order.query` 的语义。每个新 action 都需要独立设计评审；在实现对应功能时再决定是否需要二次确认。协议允许扩展，但 v1 客户端对未知 action 一律拒绝。
