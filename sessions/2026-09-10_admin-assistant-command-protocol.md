# 2026-09-10 管理员帮助结构化查询：租赁订单结果、跳转与多轮条件

本次接续管理员后台帮助系统，目标是让用户直接得到租赁订单查询结果，而不是再次收到操作说明。改动跨 reqai、SnowmeetApi、小程序和文档四个仓库。

## 1. 目标与协议

### 1.1 用户确认的行为

- 提问“请查询一下今年4月份的租赁订单”直接返回结果。
- 小程序同时跳转租赁订单查询页。
- 后续自然语言可追加、替换或回顾查询条件。
- 当前只允许租赁订单只读查询。
- 退款等操作不开放给自然语言。

### 1.2 结构化返回

- reqai 返回文字答复与操作指令两部分。
- SnowmeetApi 只执行 `rental_orders.query`。
- 查询上下文包含完整的 11 个筛选字段。
- 小程序只执行固定的租赁列表跳转。

## 2. 跨仓实现

### 2.1 reqai

- 新增严格 v1 协议模型。
- 新增 `/api/service/admin-assistant/plan`。
- 新增 `/api/service/admin-assistant/finalize`。
- planner 只生成查询计划，不直接访问业务数据。
- finalize 只接收汇总，不接收订单明细行。
- 最终合并：`main@95354a3`。

### 2.2 SnowmeetApi

- 新增统一管理员帮助 v1 端点。
- 使用现有租赁订单查询规则执行完整结果集。
- 支持 replace、patch、显式 null 条件合并。
- 返回文字、固定 action、完整查询上下文和 trace。
- 关闭结构化开关时由服务端走旧接口兼容路径。
- 最终合并：`ai@1d5b854`。

### 2.3 微信小程序

- 所有帮助问题统一调用 v1 接口。
- 保存同一员工/会话的查询上下文。
- 显示文字答复后执行固定页面跳转。
- 租赁列表解码并应用全部查询条件。
- 页面可见地展示当前筛选条件。
- 最终合并：`ai@2c09f385`。

### 2.4 文档

- 保存设计、实施计划和验证记录。
- 四个功能 worktree 分支均已快进合并到当前分支。
- 最终合并：`main@b70e855`。

## 3. 验证结果

- reqai 管理员帮助聚焦测试：21/21。
- SnowmeetApi 全量测试：303/303。
- 小程序全量测试：36/36。
- reqai 全量套件另有 13 个既有基线失败：旧文件路径 5 个、旧模型白名单 8 个。

## 4. 部署状态

### 4.1 reqai

- 服务器：`44.207.251.65`。
- 目录：`/home/ubuntu/reqai`。
- 服务：`reqai.service`，本地端口 8003。
- 服务器工作区本身有大量未提交线上改动，不能直接 pull。
- 新文件已上传到 `/home/ubuntu/reqai/deploy-backups/admin-assistant-v1/`。
- 后续连续 SSH 连接超时，未安装文件、未改 main、未重启。

### 4.2 其他仓库

- SnowmeetApi 未部署。
- 小程序未发布。
- 本次未 push 业务代码仓。

## 5. 过程问题与约束

- 代理把非核心隐私审查反复升级为阻塞项，造成明显过度设计。
- 用户明确不需要严格手机号脱敏，也不接受额外成本。
- 后续只做用户明确要求的动作。
- 超范围非功能工作必须先确认。
- 合并、部署或结束指令不得擅自追加检查。

## 6. 下次接手

1. 先确认当前四个分支的上述提交。
2. 若继续部署，只完成 reqai 的文件安装、路由注册、重启和最小接口检查。
3. 再按用户指令决定是否发布 SnowmeetApi 与小程序。
4. 用真实员工 session 验证四月查询、条件 patch 和条件回顾。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `../SnowmeetApi/Services/AdminAssistant/AdminAssistantService.cs` | 结构化编排 |
| `../SnowmeetApi/Controllers/AdminAiController.cs` | 统一帮助端点与兼容路径 |
| `../snowmeet_wechat_mini/utils/adminAssistant.js` | 上下文与 action 执行 |
| `../snowmeet_wechat_mini/components/admin-page-help/index.js` | 帮助 UI 统一调用 |
| `../../reqai/backend/app/routers/admin_assistant.py` | plan/finalize 路由 |

## 学到的小知识

1. **查询与回答分层**：模型负责计划和表述，业务 API 负责权威查询。
2. **上下文必须显式返回**：复杂条件只有完整回传，后续追问才可靠。
3. **流程不能凌驾目标**：审查建议不是自动扩展需求的授权。
