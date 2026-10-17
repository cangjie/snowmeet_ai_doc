# 食材 v4 测试数据逻辑删除操作参考

用户 2026-10-12 的定义：只处理 `fnb_v4_` 开头的表；删除是逻辑删除，把 `valid` 置 0 并刷新更新时间。它取代 2026-10-06 的旧范围（全部新旧食材、餐饮商品与订单、`fnb_unit`、上传记录与文件物理清空）。旧范围从未在生产执行过。

2026-10-13 补充：停用是 `enabled=0`，仍未删除（`valid=1`），可在界面重新启用；删除是 `valid=0`，界面中消失，不能通过保存或启用恢复。本工具不改 `enabled`。10 张主数据表新增独立 `enabled` 列，见 [增量 SQL](../../../../sql/2026-10-13_fnb_v4_enabled.sql)。既有 `valid=0` 保持删除，不转换成停用。

工具：[clear_test_data.py](../scripts/clear_test_data.py)。默认只预览；加 `--execute` 后在一个数据库事务里完成全部更新。运行过程中不询问第二次确认，也不自动读取 `config.sqlServer`。此工具仅用于正式上线前，所有入口受同目录生命周期状态约束。

## 实际范围

目标表在运行时按前缀从数据库目录读取，下面是 2026-10-12 生产库 `snowmeet_new` 的实际情况（31 张 `fnb_v4_` 表，全部在 dbo，现在都有 `valid` 列）。

| 处理方式 | 表 |
|---|---|
| `valid` 置 0，并刷新 `updated_at`（10 张） | `fnb_v4_area`、`fnb_v4_category`、`fnb_v4_check_item`、`fnb_v4_check_line`、`fnb_v4_dish_spec`、`fnb_v4_item`、`fnb_v4_item_form`、`fnb_v4_order`、`fnb_v4_purchase_spec`、`fnb_v4_shelf_life_rule` |
| 只把 `valid` 置 0，表里没有更新时间列（21 张） | `fnb_v4_alert_delivery`、`fnb_v4_area_image`、`fnb_v4_batch`、`fnb_v4_batch_detail`、`fnb_v4_batch_image`、`fnb_v4_check_handling`、`fnb_v4_check_sheet`、`fnb_v4_order_import`、`fnb_v4_order_line`、`fnb_v4_recipe`、`fnb_v4_recipe_line`、`fnb_v4_request`、`fnb_v4_stock_document`、`fnb_v4_stock_document_line`、`fnb_v4_stock_movement`、`fnb_v4_stock_operation`、`fnb_v4_stocktake_line`、`fnb_v4_supply`、`fnb_v4_supply_movement`、`fnb_v4_tool`、`fnb_v4_tool_log` |

其中 21 张表的 `valid` 列是 2026-10-12 按用户决定补上的（[增量 SQL](../../../../sql/2026-10-12_fnb_v4_add_valid.sql)，只加列、默认 1，生产已执行）：`fnb_v4_alert_delivery`、`fnb_v4_area_image`、`fnb_v4_batch`、`fnb_v4_batch_detail`、`fnb_v4_batch_image`、`fnb_v4_check_handling`、`fnb_v4_check_line`、`fnb_v4_check_sheet`、`fnb_v4_order`、`fnb_v4_order_import`、`fnb_v4_order_line`、`fnb_v4_recipe`、`fnb_v4_recipe_line`、`fnb_v4_request`、`fnb_v4_stock_document`、`fnb_v4_stock_document_line`、`fnb_v4_stock_movement`、`fnb_v4_stock_operation`、`fnb_v4_stocktake_line`、`fnb_v4_supply_movement`、`fnb_v4_tool_log`。原来就有 `valid` 的是另外 10 张主数据表。以后新增的 v4 表如果没有 `valid` 列，脚本原样保留、只报告行数。

- v4 表没有 `update_date` 列，对应的是 `updated_at`。写入值是数据库服务器的 UTC 时间（`SYSUTCDATETIME()`，精确到毫秒），同一次运行所有表用同一个值。
- 已经是 `valid=0` 的行不动。
- 不删任何行。行数、表结构、索引、约束、ID 序号都不变。
- `fnb_unit`、旧食材表、餐饮商品/分类/订单/支付、`mini_upload`、S3 与服务器文件、员工、会员、门店都不碰。

逻辑删除后的表现：

- 修正后的 10 张主数据表：全局查询过滤只读取 `valid=1`；“包含停用”只额外包含 `enabled=0` 的未删除记录，绝不包含 `valid=0`。按旧 ID 保存也找不到删除记录。唯一索引仍带 `WHERE valid = 1`，停用记录保留名称/条码，删除后同名的分类、食材、区域、物资以及同一条码可以重新创建。
- 10-12 补列的 21 张表，接口从 SnowmeetApi `ai@fe4eb6c2`（2026-10-12 23:04 发布）起处理：
  - 其中 20 张加了全局查询过滤，任何查询都只看 `valid=1` 的行，所以逻辑删除后的批次、库存流水、单据、订单、配方、检查单在界面和报表里不再出现。新写入的行不用显式赋值，默认就是有效。
  - `fnb_v4_request` 是幂等记录，照样会被置 0，但接口不过滤它：同一个 requestId 任何时候都不能再执行一次。停用/删除分离的修正还会拒绝重试已删除请求，避免旧响应重新显示已删除数据。
  - 两个视图 `vw_fnb_v4_stock`、`vw_fnb_v4_loss` 只统计有效行。
- 5 个唯一索引改成只约束有效行（[增量 SQL](../../../../sql/2026-10-12_fnb_v4_valid_filters.sql)，生产已执行），这些键在逻辑删除后可以重新使用：同门店的批号、同门店同日期的检查单、同来源的外部订单号、订单导入去重键、同门店的工具资产编号。其余唯一索引都以上级记录的 id 开头，上级重建后 id 不同，没有改。
- 有效行之间这些键仍然唯一。按清单恢复旧行时，如果之后已经用同样的键建了新的有效行，数据库会拒绝，需要先处理冲突。
- **已发布的 `fe4eb6c2` 仍混用主数据的停用与删除，尚不足以满足 10-13 的定义。** 新版 API 与 `enabled` SQL 都完成部署后才再执行本 skill；仅存在本地源码不代表线上具备这些行为。2026-10-13 09:40 已发布 `ai@76246c61`，SQL 已执行两遍并验证原业务字段不变；线上含停用列表不显示删除行，按已删除区域 ID 使用 enabled=true 或旧 valid=true 保存均返回 code 1。停用→启用流程在隔离 SQLite 和离线浏览器验证通过。详见 [部署记录](../../../../sessions/2026-10-13_fnb-v4-enabled-deletion-production-deploy.md)。

## 一条命令执行

需要 Python 3.10+、pyodbc、机器上的 SQL Server ODBC 驱动。不需要 boto3 或 AWS 凭据。

先在运行环境中配置 `SNOWMEET_FNB_CLEAR_DSN`（完整 ODBC 连接串，数据库 snowmeet_new）。脚本只读取显式指定的环境变量，不读仓库配置文件；连接串不要提交到 Git。默认库名必须与真实连接库名一致。

在 snowmeet_ai_doc 目录执行预览（Mac 用 `python3`）：

```powershell
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --manifest .local/fnb-clear-preview.json
```

执行命令：

```powershell
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --execute --manifest .local/fnb-clear-executed.json
```

脚本在 Serializable 事务中独占锁定会被修改的表，防止运行期间有新行写入；一次运行只有几十次查询，锁定时间很短。不会停止 API 服务，其他业务表不加锁。

每次使用一个新的清单文件，旧清单不会被覆盖。清单包含每张表的总行数、置为无效的行数和这些行的主键、保留未动的表及行数、本次写入的时间戳，没有数据库凭据。

## 失败、重复执行与恢复

- 全部更新在同一事务中完成，任何错误都会回滚。出现非 dbo 的 `fnb_v4_` 表、`valid` 列类型异常、目标表上有启用的触发器，或运行中行数与预先统计不一致时，脚本停止，不扩大范围。
- 清单状态 `preview` 表示只预览；`prepared` 表示提交结果尚未可靠记录（如提交边界断电或断网），须先核对数据库再判断，不要手工猜测为已成功；`committed` 表示已提交。
- 重复执行安全：已无效的行不再变化，结果是 0 行。
- 需要恢复时，按执行清单里 `invalidated` 记录的主键把 `valid` 改回 1。工具不提供恢复命令，恢复属于另一项需要用户明确授权的生产写入。

## 正式上线作废

执行以下命令并提交 `lifecycle.json` 到文档仓库 main。状态只有 testing → retired，没有重新启用参数；退役后预览和执行都会在连接数据库前拒绝。

```powershell
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --status
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --retire
```

其他机器使用前同步 main；正式上线后不能恢复 testing 或运行旧版本。

## 验证

```powershell
py tools/windows_test/run_integration_localdb.py --verify-clear-test-data
```

只创建随机 `snowmeet_fnb_test_*` LocalDB 临时库，采用真实 v4 DDL 并执行补 `valid` 列的增量 SQL（连续两遍，验证可重复执行），31 张表全部有夹具，另有员工、门店、会员、商品、订单、上传和单位等非 v4 数据。检查内容：预览只读；错库、触发器、非 dbo 的 v4 表、`valid` 类型异常拒绝；中途失败整体回滚；执行后 31 张表全部置 0、有更新时间列的表等于清单时间戳、原本无效的行不变；全部非 v4 表逐行不变；没有任何行被删除、ID 序号不变；重复执行为 0 行。

运行器会在原有两份建表脚本之后执行 10-12 的两份增量 SQL（补列、索引和视图）及 10-13 的 `enabled` SQL，再比较 EF 模型和库结构。`tools/windows_test/ef_create.sql` 是运行器缓存的 EF 输出，接口模型改过之后要先删掉它让运行器重新生成，否则会报字段不一致。

2026-10-12 改写后，这套验证和接口的 22 项 SQL Server 集成测试都还没有在 Windows LocalDB 上运行过（改动在 Mac 上完成；集成测试只允许连本机 LocalDB）。当天用户决定直接在线上验证，做法和结果见 [CLAUDE.md](../../../../CLAUDE.md) 顶部 2026-10-12 条目。下次在 Windows 机上动这部分之前先把两套都跑一遍。

2026-10-17 补充：Windows LocalDB 清理专项验证已全部通过，包括只读预览、生命周期限制、异常目标拒绝、中途失败整体回滚、31 表逻辑删除、非 v4 数据逐行保留、更新时间、ID 序号和重复执行。修正了验证夹具的分类计数：运行器预先保留的分类也属于清理目标，预期行数和主键清单应包含这条基线记录。接口集成测试已于 10-16 补跑，26 项通过。

同日用户明确指定本机 `SnowmeetApi/config.sqlServer` 为本次连接来源后，已对 `snowmeet_new` 执行本 skill。31 张表中 23 张共 70 条有效记录置为 `valid=0`，另 8 张更新 0 条；事务状态 `committed`，统一写入时间为 UTC `2026-10-17 04:10:36.991`。清理后核验所有 v4 表有效行均为 0、各表总行数不变、受影响记录的更新时间正确；`fnb_unit` 5 行保留，服务 active/running、NRestarts=0。没有物理删除、上传文件操作或其他表更新。逐表行数、受影响主键和核验结果仅保存在本机 workspace 的 `.local/fnb-clear-20261017/`，不提交 Git。
