# 2026-10-12 食材 v4 测试数据清理：改为逻辑删除，全部 v4 表补 valid，接口发布并在线上演练

按时间线整理。会话在 Mac mini 上进行，从 start-work 开始，10-12 21:26 到 10-13 01:30 左右。用户原本只想执行一下食材测试数据清理 skill，过程中重新定义了它的范围和做法，随后给 v4 的表补了 `valid` 列，并把接口改到认这一列、发布上线、在线上演练验证。改动落在文档仓的 skill、SQL 和 Windows 测试工具，以及 SnowmeetApi 的 v4 模型与配置。

## 1. start-work 核对

- 文档仓已是最新 `46b74ae`。
- 本机 SnowmeetApi `9db5d2a9`（落后 17）、小程序 `b6892624`（落后 19）、reqai `2541e8b`（落后 18），工作区都干净；公众号一致。公众号和 reqai 的 22 端口 fetch 失败，改走 443 成功。
- **三张证书还没续**：经美国服务器实测，wxoa 10-14 14:59、wl 15:59、mini 19:59（北京时间）到期。
- 本机磁盘只剩 372 MB。
- 发现 10-11～10-12 有一轮京东山姆旗舰店抓取没有归档（见 CLAUDE.md「下一步」里的山姆条目）。
- `/reqai-digest` 提示 2 个会话（#5 #7）有未分析内容，本次没有处理。

## 2. 原版 skill 没有执行成

### 2.1 原版范围

用户说：「V4这块，貌似有个清空测试数据的skill，帮我执行一下。」

原版 `fnb-clear-test-data`（10-06 定义）是物理清空：全部新旧食材表、`fnb_unit`、餐饮商品与分类、餐饮销售订单及支付退款记录、食材相关上传记录，以及 S3 上对应文件的全部历史版本。

### 2.2 连接和权限

- 脚本只认环境变量 `SNOWMEET_FNB_CLEAR_DSN`，明文禁止读 `SnowmeetApi/config.sqlServer`。本机没有这个变量。
- 问过用户后，用户选择：连接串用本机 `config.sqlServer`；「只删除数据库记录即可，实际的S3不用删」。这是用户当场对这一次的授权，skill 的规则没有改。
- 本机直连生产库不通，经美国服务器转发 `44.207.251.65,1433` 可以连，每次往返约 0.47 秒。
- 原版脚本要跑四千多次查询，估计每趟 35 分钟，期间订单、支付、商品、上传等共用表被独占锁住。

### 2.3 预览被拦

- 预览报 `No primary key: order_online`，在选数据之前就拒绝，一行没删，没有留下锁。
- `order_online` 是 2017-04 至 2025-04-18 的旧在线订单表，49,370 行，没有主键和任何索引，里面没有餐饮订单。脚本要求白名单里每张表都有主键。
- 用户问：「order_online和V4有什么关系？」——没有关系，它只是原版要检查「有没有餐饮订单」的旧订单表之一。

### 2.4 把范围核对给用户

按脚本的选取规则只读重算（不是脚本自己的预览），原版会删约 1,110 行：

| 类别 | 会删 / 全表 |
|---|---|
| v4 表 | 23 / 23 |
| `fnb_unit` | 5 / 5 |
| 餐饮分类 `category` | 14 / 20 |
| 餐饮商品 `product` | 14 / 646 |
| 餐饮订单 `order` | 300 / 32,767（2025-07 至 2025-10，崇礼旗舰店，合计 15,399 元） |
| 订单明细 `fd_order` | 392 / 392 |
| 支付 `order_payment` | 151 / 34,869 |
| 退款、分账、优惠 | 2、3、117 |
| 上传记录 `mini_upload` | 60 / 145,986 |
| 商品图片、属性、库存流水 | 10、4、12 |

300 张订单里 295 张是用户自己两个测试账号下的，线上实付合计 1.37 元。

## 3. 用户重新定义：只处理 v4 表，逻辑删除

用户原话：「这个skill，需要修改，第一，只删除fnb_v4_ 开头的表的数据；第二，删除也是逻辑删除，把valid设置为0，同时更新update_date」

### 3.1 查到的两个事实

- v4 的表里没有 `update_date` 列，对应的是 `updated_at`，接口写的是 UTC。接口自己停用记录时也是 `valid=false` 加 `updated_at=UtcNow`。
- 31 张 `fnb_v4_` 表里只有 10 张有 `valid`：`area`、`category`、`check_item`、`dish_spec`、`item`、`item_form`、`purchase_spec`、`shelf_life_rule`、`supply`、`tool`。其中 `supply`、`tool` 没有更新时间列。

### 3.2 改写后的脚本

[clear_test_data.py](../.claude/skills/fnb-clear-test-data/scripts/clear_test_data.py)：

- 目标表按前缀 `fnb_v4_` 从数据库目录读取，只认 dbo。
- 有 `valid` 列的表：`UPDATE … SET valid=0, updated_at=<UTC 时间戳> WHERE valid IS NULL OR valid<>0`，同一次运行所有表用同一个时间戳；没有更新时间列的只改 `valid`。
- 没有 `valid` 列的表原样保留，只报告行数。
- 一个 Serializable 事务；统计和锁定用一条 `UNION ALL` 语句完成，整个运行只有几十次往返（约 15 秒）。
- 拒绝条件：库名不符、已有外层事务、非 dbo 的 v4 表、`valid` 类型异常、目标表上有启用的触发器、更新行数与预先统计不一致。
- 清单记录每张表的行数、置为无效的行数和主键（用 `OUTPUT inserted.<主键>` 取得）、时间戳。
- 去掉了全部 S3 / 本机文件删除、`--resume-files`、`--local-app-root`。生命周期（testing / retired）保留。

### 3.3 第一次生产执行（22:32）

| 表 | 置为无效 | 内容 |
|---|---|---|
| `fnb_v4_area` | 5 | 二楼教室、吧台、冷藏柜、豆仓、杯架 |
| `fnb_v4_category` | 4 | 乳制品、粮油、鲜奶、进口面粉 |
| `fnb_v4_check_item` | 4 | 温度、咖啡豆是否充足、杯子杯盖是否充足、开瓶器状态 |
| `fnb_v4_tool` | 1 | 开瓶器 |

- `updated_at` = `2026-10-12 14:32:12.275`（UTC）。
- 执行前后对 31 张 v4 表和 `fnb_unit` 做了全量快照逐行比对：只有上面四张表的 `valid`、`updated_at`（及 `fnb_v4_tool` 的 `row_version`）变化，没有行被删除。
- 被改行的主键：area 1–5，category 1–4，check_item 1–4，tool 1。

## 4. 给 21 张表补 valid 列

用户决定：「加 valid 列」。

- [2026-10-12_fnb_v4_add_valid.sql](../sql/2026-10-12_fnb_v4_add_valid.sql)：21 张表各加 `[valid] bit NOT NULL DEFAULT CAST(1 AS bit)`，只加列、可重复执行。22:42 在生产执行，1.1 秒。
- 执行后核对：31 张表都有 `valid`，已有行都是 1，其他列逐行未变；服务 active、没有重启、Swagger 200、日志无数据库报错。
- 补列后脚本不用改就把这 21 张表纳入。22:43 第二次执行，置为无效 9 行：
  - `fnb_v4_request` 5 行：门店 10 的 `check.confirm`、`check.save`×2、`check.start`、`check.submit`
  - `fnb_v4_area_image` 1 行（area 1，upload 157726）
  - `fnb_v4_check_line` 1 行（id 1，`updated_at` = `2026-10-12 14:43:07.819`）
  - `fnb_v4_check_sheet` 1 行（id 1，10-06 的检查单）
  - `fnb_v4_tool_log` 1 行（id 1）
- 至此 v4 的 23 行全部 `valid=0`，`fnb_unit` 5 行未动。
- 两份执行清单只在 Mac mini 本机 `snowmeet_ai_doc/.local/`，不入库；需要恢复时按上面列出的主键把 `valid` 改回 1。

## 5. 接口补齐（SnowmeetApi `ai@fe4eb6c2`）

用户原话：「补齐，直接在线上服务器验证，因为现在还没有开始营业。」

### 5.1 改动

- 21 个实体加 `public bool valid { get; set; } = true;`（`Models/Fnb/` 下 6 个文件）。
- [FnbSchemaConfiguration.cs](../../SnowmeetApi/Data/FnbSchemaConfiguration.cs)：
  - 20 个实体加全局查询过滤 `HasQueryFilter(x => EF.Property<bool>(x, "valid"))`。
  - `FnbRequest` 不过滤：同一个 requestId 任何时候都不能再执行一次。
  - 原有 10 张主数据表不加全局过滤，仍由各查询自己决定是否包含已停用记录。
  - 5 个唯一索引加 `[valid] = 1` 条件。
- 新增 `SnowmeetApi.Tests/FnbV4SoftDeleteMappingTests.cs`（3 项，只用模型元数据，不连库）。

### 5.2 为什么只改 5 个唯一索引

会在逻辑删除后重新出现的自然键只有这些：

| 索引 | 原因 |
|---|---|
| `fnb_v4_batch (shop_id, batch_no)` | 批号是「日期-分类批次码-序号」，序号按有效批次算，会从 01 重新编 |
| `fnb_v4_check_sheet (shop_id, business_date)` | 同一天要能重新开始检查 |
| `fnb_v4_order (shop_id, source_type, external_order_no)` | 同一外部订单要能重新导入 |
| `fnb_v4_order_import (shop_id, source_method, dedupe_key)` | 同上 |
| `fnb_v4_tool (shop_id, asset_no)` | 原来就不区分是否有效，已停用工具的编号不能复用 |

其余唯一索引都以上级记录的 id 开头，上级重建后 id 不同，不需要改。

### 5.3 SQL

[2026-10-12_fnb_v4_valid_filters.sql](../sql/2026-10-12_fnb_v4_valid_filters.sql)：重建上面 5 个索引；`CREATE OR ALTER` 两个视图 `vw_fnb_v4_stock`、`vw_fnb_v4_loss`，定义与 10-06 逐字一致，只多了 `valid=1` 条件。22:59 在生产连跑两遍，确认可重复执行。接口代码里没有用到这两个视图，改它们是为了口径一致。

### 5.4 本机验证

- `dotnet test`：470 过、22 跳过。跳过的是 `FnbSqlServerIntegrationTests`，代码里写死只允许连本机 LocalDB 的 `snowmeet_fnb_test_` 临时库，这是有意设的保护，没有去绕。
- 在 Mac 上跑 `tools/windows_test/efschema` 生成 EF 结构，核对：31 张表都有 `valid` 且定义与补列脚本一致；5 个索引定义与新脚本逐字一致；去掉后补的列和条件后，与 10-06 的两份建表脚本完全一致。
- Windows 运行器 `run_integration_localdb.py` 相应改为在原有两份脚本之后执行 10-12 的两份增量 SQL；skill 的验证脚本改为先执行补列脚本。**这两个都没有在 Windows 上实际运行过。**

## 6. 发布

- 发布前：清日志归档（保留 300 MB）和 apt 包缓存，磁盘 790 MB → 1.9 GB；把 439 个运行文件备份到 `/home/ubuntu/fnb-v4-valid-deploy-20261012/runtime-backup`（221 MB，对应 `9c5d46c9`）。
- 发布：`ssh -p 2222 ubuntu@44.207.251.65 'cd /home/ubuntu/webs/SnowmeetApi && ./republish.sh'`，23:02:04–23:04:25，退出码 0。
- 发布后删了 `bin`、`obj`（308 MB），磁盘剩 1.7 GB（95%）。
- 上线后检查：
  - 服务 active，`NRestarts=0`。
  - 路由 587 条，其中食材 92 条，与发布前相同（接口描述在 `/swagger/v2/swagger.json`）。
  - Swagger 页面、食材 H5 首页 200；H5 的 8 个静态文件字节数与仓库一致。
  - 失效会话访问 `FnbAuth/GetMe`、`FnbStock/ListStock` 都返回 code 2。
  - 启动后日志无异常。

## 7. 线上演练

### 7.1 做法

写了一个一次性的控制台程序，引用 `SnowmeetApi.csproj`，从 Mac mini 连生产库：

- 用门店 10 的店长级员工（id 28）构造 `FnbAccess.Actor`，直接调 `FnbV4Service` 和 `FnbV4CatalogService`。不创建登录会话，不调外部服务。
- 全程在一个 ReadCommitted 事务里，最后无条件回滚。控制器自己会开事务，所以不能通过控制器走。
- 步骤：基线读取 → 全流程写入 → 检查有效行之间仍然唯一 → 31 张表有效行置 0 → 检查各列表和视图变空 → 用同样的键重建 → 回滚 → 核对行数回到基线。

### 7.2 第一次挡住了用户的页面

- 23:10:43 开始。用户 23:14:45–23:16:03 四次打开食材 H5。
- 访问日志：`FnbAuth/GetMe` 和 `FnbCatalog/ListUnits` 是 200；`FnbCatalog/ListCategories`、`FnbRoute/ListItems` 是 499（客户端关闭连接），它们被演练事务里未提交的行挡住。
- 页面要等分类和食材都回来才显示内容，所以一直停在加载中。用户问：「执行完操作，为什么h5网页上的菜单都没有了呀？」
- 23:16 停掉演练进程，连接断开后事务自动回滚；核对无残留数据、无未结事务、无被阻塞请求。
- 之前只说了「演练期间 V4 的表上会有锁」，没有明确提醒这段时间不要打开页面。

### 7.3 第二次全部通过

用户同意后重跑，23:24:03–23:33:57，594 秒，27 项检查全部通过：

- 31 张表可查询；20 张过滤表现有行带过滤查询为 0；幂等记录表不过滤。
- 31 张表全流程写入成功：分类、食材、保质期规则、区域、入库、幂等记录、菜品规格、配方、手工订单、出餐、订单导入、外部订单、盘点、物资、工具、检查、检查处理、工具状态、上游形态、进货规格、按规格入库、作业、区域照片、批次照片、临期提醒记录。
- 新行 `valid` 默认 1；库存服务和两个视图能看到新数据；18 个读取服务在有数据和逻辑删除后两种状态下都执行成功（空状态在第一次已通过）。
- 有效行之间仍然唯一：批号、同门店同日检查单、工具资产编号、订单导入去重键、外部订单号的重复都被数据库拒绝。
- 置为无效 56 行后：20 张表带过滤查询全部为 0，行都还在；库存不再有批次；两个视图不再统计；今日检查回到未开始；待出餐、出餐记录、入库记录、工具、物资列表为空。
- 重建：批号两遍都是 `261012-LV4583F8-01`（批次 id 4 → 8），同一天的检查单 3 → 5，同一资产编号、同一去重键、同一外部订单号都重建成功；库存里只有第二遍的食材。
- 回滚后 31 张表行数与基线一致。10-13 01:22 另行核对：v4 仍是 23 行且全部无效，`fnb_unit` 5 行有效，无演练名称的残留，无未结事务。
- 回滚占掉了自增序号：以后新建批次从 11、检查单从 6、分类从 11、区域从 12 开始。

### 7.4 没有覆盖的

- 并发、死锁、重放这类用例在 22 项集成测试里，演练不涉及。
- 控制器层（会话解析、权限、幂等包装）只验证了失效会话返回 code 2。
- 真机流程：企业微信登录、OCR、蓝牙出纸、出餐扣减。
- 演练程序放在会话临时目录，会话隔夜恢复后目录被清空，源码没有保留。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `.claude/skills/fnb-clear-test-data/scripts/clear_test_data.py` | 重写：只对 `fnb_v4_` 表做逻辑删除 |
| `.claude/skills/fnb-clear-test-data/SKILL.md`、`references/operations.md` | 新的范围、做法、恢复方法、接口行为 |
| `sql/2026-10-12_fnb_v4_add_valid.sql` | 21 张表补 `valid` |
| `sql/2026-10-12_fnb_v4_valid_filters.sql` | 5 个唯一索引和 2 个视图只看有效行 |
| `tools/windows_test/verify_clear_food_test_data.py` | 按新行为重写（未在 Windows 运行） |
| `tools/windows_test/run_integration_localdb.py` | 追加执行 10-12 的两份 SQL（未在 Windows 运行） |
| `docs/fnb/2026-10-06-fnb-clear-test-data.md`、`docs/fnb/2026-10-06-fnb-v4-h5.md` | 标注范围已变 |
| SnowmeetApi `Models/Fnb/*.cs`（6 个文件） | 21 个实体加 `valid` |
| SnowmeetApi `Data/FnbSchemaConfiguration.cs` | 全局查询过滤、5 个索引条件 |
| SnowmeetApi `SnowmeetApi.Tests/FnbV4SoftDeleteMappingTests.cs` | 新增 3 项映射测试 |

提交：文档仓 `915c80d`、`173eec3`、`d00ebdc`、`adace70` 及本次归档；SnowmeetApi `ai@fe4eb6c2`。

## 学到的小知识

1. **删除类工具先核对范围**：用户说的是「V4 这块」，工具的实际范围是全部食材和餐饮数据。预览被主键检查拦下，才有机会把 1,110 行的范围摆给用户，用户随即把范围收窄到 v4。
2. **按用户说的列名动手前先查实际结构**：用户说更新 `update_date`，v4 表里只有 `updated_at`；用户说置 `valid`，三分之二的表没有这一列。这两处都要先告诉用户再做。
3. **全局查询过滤适合「只用于逻辑删除」的表**：一处配置覆盖全部查询；但它也会让序号生成、存在性检查看不到无效行，所以相关的唯一索引必须同时加 `valid = 1` 条件。批号就是这样被发现的。
4. **幂等记录不该被过滤**：否则清理之后重放同一个请求会再执行一次，并撞上主键。
5. **`HasSentinel(true)` 加属性初始值 `= true`**：新建对象不赋值时 EF 不发送该列，由数据库默认值给出 1；显式设为 false 才会写入。
6. **对生产库开着写事务，读已提交隔离级别下的其他查询会被未提交的行挡住**：演练里刚插入的分类和食材，把线上页面的分类列表和食材列表接口卡住了。往返慢会把这种窗口拉长到十分钟。
7. **发布命令用文档里的原样写法**：`ssh … './republish.sh'` 放在后台等它结束即可，不需要再包一层脱离会话的写法。
8. **nginx 访问日志里的 499 表示客户端先断开**：页面卡住时，用它可以分清是接口报错还是接口一直没返回。
