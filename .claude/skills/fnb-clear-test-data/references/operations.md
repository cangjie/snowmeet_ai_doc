# 食材 v4 测试数据逻辑删除操作参考

用户 2026-10-12 的定义：只处理 `fnb_v4_` 开头的表；删除是逻辑删除，把 `valid` 置 0 并刷新更新时间。它取代 2026-10-06 的旧范围（全部新旧食材、餐饮商品与订单、`fnb_unit`、上传记录与文件物理清空）。旧范围从未在生产执行过。

工具：[clear_test_data.py](../scripts/clear_test_data.py)。默认只预览；加 `--execute` 后在一个数据库事务里完成全部更新。运行过程中不询问第二次确认，也不自动读取 `config.sqlServer`。此工具仅用于正式上线前，所有入口受同目录生命周期状态约束。

## 实际范围

目标表在运行时按前缀从数据库目录读取，下面是 2026-10-12 生产库 `snowmeet_new` 的实际情况（31 张 `fnb_v4_` 表，全部在 dbo，现在都有 `valid` 列）。

| 处理方式 | 表 |
|---|---|
| `valid` 置 0，并刷新 `updated_at`（10 张） | `fnb_v4_area`、`fnb_v4_category`、`fnb_v4_check_item`、`fnb_v4_check_line`、`fnb_v4_dish_spec`、`fnb_v4_item`、`fnb_v4_item_form`、`fnb_v4_order`、`fnb_v4_purchase_spec`、`fnb_v4_shelf_life_rule` |
| 只把 `valid` 置 0，表里没有更新时间列（21 张） | `fnb_v4_alert_delivery`、`fnb_v4_area_image`、`fnb_v4_batch`、`fnb_v4_batch_detail`、`fnb_v4_batch_image`、`fnb_v4_check_handling`、`fnb_v4_check_sheet`、`fnb_v4_order_import`、`fnb_v4_order_line`、`fnb_v4_recipe`、`fnb_v4_recipe_line`、`fnb_v4_request`、`fnb_v4_stock_document`、`fnb_v4_stock_document_line`、`fnb_v4_stock_movement`、`fnb_v4_stock_operation`、`fnb_v4_stocktake_line`、`fnb_v4_supply`、`fnb_v4_supply_movement`、`fnb_v4_tool`、`fnb_v4_tool_log` |

其中 21 张表的 `valid` 列是 2026-10-12 按用户决定补上的（[增量 SQL](../../../../sql/2026-10-12_fnb_v4_add_valid.sql)，只加列、默认 1，生产已执行）：`fnb_v4_alert_delivery`、`fnb_v4_area_image`、`fnb_v4_batch`、`fnb_v4_batch_detail`、`fnb_v4_batch_image`、`fnb_v4_check_handling`、`fnb_v4_check_line`、`fnb_v4_check_sheet`、`fnb_v4_order`、`fnb_v4_order_import`、`fnb_v4_order_line`、`fnb_v4_recipe`、`fnb_v4_recipe_line`、`fnb_v4_request`、`fnb_v4_stock_document`、`fnb_v4_stock_document_line`、`fnb_v4_stock_movement`、`fnb_v4_stock_operation`、`fnb_v4_stocktake_line`、`fnb_v4_supply_movement`、`fnb_v4_tool_log`。原来就有 `valid` 的是另外 10 张主数据表。以后新增的 v4 表如果没有 `valid` 列，脚本原样保留、只报告行数。

- v4 表没有 `update_date` 列，对应的是 `updated_at`。写入值是数据库服务器的 UTC 时间（`SYSUTCDATETIME()`，精确到毫秒），同一次运行所有表用同一个值；接口自己停用记录时也是 `valid=false` 加 `updated_at=UtcNow`。
- 已经是 `valid=0` 的行不动。
- 不删任何行。行数、表结构、索引、约束、ID 序号都不变。
- `fnb_unit`、旧食材表、餐饮商品/分类/订单/支付、`mini_upload`、S3 与服务器文件、员工、会员、门店都不碰。

逻辑删除后的表现：

- 原有 10 张主数据表：唯一索引都带 `WHERE valid = 1`，同名的分类、食材、区域、物资以及同一条码可以重新创建；接口列表按 `valid` 过滤，停用的行不再出现，带「含已停用」选项的列表仍会显示。例外是 `fnb_v4_tool` 的资产编号唯一索引没有这个条件，**同一门店下已停用工具的资产编号不能复用**。
- **10-12 补列的 21 张表，接口还不认 `valid`。** 截至 2026-10-12 已发布的接口（SnowmeetApi `ai@9c5d46c9`）里这些表的实体没有 `valid` 属性，查询不过滤：
  - `valid=0` 的批次、库存流水、单据、订单、配方、检查单在界面和报表里照常出现；两个视图 `vw_fnb_v4_stock`、`vw_fnb_v4_loss` 也照常统计。
  - 这些表的唯一索引不区分是否有效：同门店同日期的检查单、同门店的批号、同来源的外部订单号等，逻辑删除后不能重建同样的键。
  - 新写入的行靠列默认值得到 `valid=1`，接口运行不受影响。
- 要让这 21 张表的逻辑删除在系统里真正生效，还需要一次接口改动并发布：实体加 `valid`、查询只看有效行、相关唯一索引和两个视图只看有效行，并在 Windows LocalDB 上跑完整验证。这项工作 2026-10-12 尚未开始，做之前先和用户确认。

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

2026-10-12 改写后这套验证尚未在 Windows LocalDB 上运行过（改写在 Mac 上完成）。下次在 Windows 机上使用本 skill 前先跑一遍。
