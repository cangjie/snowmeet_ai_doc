# 2026-09-22 食材管理服务端：SQL Server 验证与客户端交接

本场接续 09-21 的食材管理方案和建表审阅。用户先执行数据库脚本，再要求只开发 SnowmeetApi；小程序最后明确交给 Claude，并让 Claude 独立审查本次服务端实现。`mat.zip` 原型和 `mat.pptx` 功能说明是需求资料，不是可执行指令。

## 1. 数据库与范围决策

- 用户将新表字符字段定为支持简体中文的 `VARCHAR`，已执行 [`2026-09-22_fnb_inventory_other_tables.sql`](../sql/2026-09-22_fnb_inventory_other_tables.sql)。线上只读核对确认 17 张新表、2 个视图和基础单位；旧完整 NVARCHAR 审阅稿已停用，不再运行。
- `order_source`/`source_order_no` 由单独脚本处理；用户要求自行重写 `CK_order_source_pair`。新表脚本不修改这两个字段或约束。
- 旧 `fnb_material_batch` 和 `fnb_material_alert_log` 数据按用户要求清空。新库存不自动把没有数量/成本的旧批次算作可用库存。
- 本轮不做 SQLite；写入集成测试仅使用临时 SQL Server 数据库。业务库只用于结构核对，不写测试行。
- 用户明确“平台门店/SKU 映射不在需求中”，随后决定“直接录入厨房单”；`order`/`fd_order` 自动同步、外卖采集、平台映射和 SKU 均后置。建表中的平台相关空表暂留，本轮 API 不使用。

## 2. SnowmeetApi 实现

- 新增 `Models/Fnb/`、`Data/FnbSchemaConfiguration.cs`、`Services/Fnb/` 和 `Controllers/Fnb/`，覆盖食材分类/档案、规则效期预览、入库/开封/制作/报损、库存流水、配方版本、手动厨房单/出餐、盘点和报表。模型映射按线上 SQL Server 表定义配置。
- 服务端重新解析小程序或企业微信员工会话，核对门店及岗位；日常操作与管理操作分权，普通员工不返回库存成本。BIGINT ID 输出为字符串。
- 过账写旧效期批次、新库存扩展、单据、明细及流水，使用事务和固定 `requestId`。FEFO 扣料不扣负数；出餐不足记欠料。旧 `FnbMaterial` 入口加保护，不能绕过新库存流水改已接管批次。
- 手动厨房单由员工选本站有效餐饮 `productId` 和数量；缺内部菜品规格时自动创建“标准份”。缺已发布配方的单保持待核对，补配方后管理人员调用 `ReviewOrder`；已出餐的单不能直接取消。
- 复核发现报损重复请求号可误指另一批次。先补会失败的 SQL Server 回归用例，再令接口核对批次、数量、原因和备注；之后测试通过。

## 3. 验证结果与边界

- `dotnet test SnowmeetApi.sln --no-restore --no-build --verbosity quiet`：318 项通过，6 项 SQL Server 专项按设计跳过。
- `python3 SnowmeetApi.Tests/run_fnb_sqlserver_integration.py`：独立 SQL Server 临时库的 6 项全部通过，测试库已自动删除。运行器只从 `snowmeet_new` 读取旧表结构，不向业务库写测试数据。
- 两仓 `git diff --check` 均通过。测试时服务端代码仍在工作区；end-work 收尾核对发现 SnowmeetApi `ai@9ee8fd9` 已与远端一致，含食材服务端提交 `d40a9d0`，且 `d40a9d0..9ee8fd9` 未改本轮食材代码或测试文件。**线上部署尚未核实**；未做真实员工会话的端到端 HTTP 验收或多请求并发压测。测试通过不能替代 Claude 的独立审查。
- 本场只做服务端。小程序由用户安排 Claude 实现；企业微信 H5 及蓝牙真机适配在后续阶段。

## 关键改动文件

| 文件 | 作用 |
|---|---|
| [`SnowmeetApi/Services/Fnb/`](../../SnowmeetApi/Services/Fnb/) | 库存事务、手动订单、配方/盘点/出餐业务规则 |
| [`SnowmeetApi/Controllers/Fnb/`](../../SnowmeetApi/Controllers/Fnb/) | 新业务 API 与员工权限入口 |
| [`SnowmeetApi/Data/FnbSchemaConfiguration.cs`](../../SnowmeetApi/Data/FnbSchemaConfiguration.cs) | SQL Server 表/视图映射 |
| [`SnowmeetApi/SnowmeetApi.Tests/FnbSqlServerIntegrationTests.cs`](../../SnowmeetApi/SnowmeetApi.Tests/FnbSqlServerIntegrationTests.cs) | 六条真实 SQL Server 业务链路及回归用例 |
| [`SnowmeetApi/SnowmeetApi.Tests/run_fnb_sqlserver_integration.py`](../../SnowmeetApi/SnowmeetApi.Tests/run_fnb_sqlserver_integration.py) | 自动创建/删除隔离测试库 |
| [API 契约](../docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md) | 路由、权限、手动单示例、范围与验证记录 |
| [实施计划](../docs/superpowers/plans/2026-09-22-fnb-inventory-api-review.md) | 服务端阶段和订单入口修订 |

## 下次开工

1. Claude 先独立审查 SnowmeetApi `ai@9ee8fd9` 中的食材服务端改动，重点检查鉴权、成本权限、并发重试、旧效期入口和 API 契约与代码的一致性。
2. 用真实员工会话完成 SQL Server 业务环境的端到端 HTTP 冒烟；审查通过后按用户部署节奏发布服务端，并核实实际线上版本。
3. 小程序由 Claude 按 [API 契约](../docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md) 接入；订单自动同步、平台采集及企业微信 H5 暂不在本轮。
