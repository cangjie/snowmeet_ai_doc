# 2026-10-06 v4 完整后端补齐

用户追问存储区域“暂未开通”，指出全部 v4 后端均应开发。上午实际只交付认证、分类、食材链路和规格第一期；此前“后端做好”的说法范围不明确。此次按最新要求补齐所有原计划第 2/3 期及区域、开门检查、物资、工具。开发和测试仅本机，未连接生产、未启动生产 API，未读 config.sqlServer，未执行或 import HTTP smoke 脚本。用户期间要求先查看扩展 SQL，已提供文件；生产扩展 SQL 和部署均未执行。

## 改动文件

API `ai`，共 22 个文件：

- `Models/Fnb/FnbV4OperationsEntities.cs`、`FnbV4Requests.cs`：13 张扩展表及全模块请求模型。
- `Data/ApplicationDBContext.cs`、`FnbSchemaConfiguration.cs`：DbSet、精度、无级联关联、索引及约束；SQLite 兼容的长 JSON 字段。
- `Controllers/Fnb/FnbV4ControllerBase.cs`：员工/店长权限与事务分开；UUID/内容哈希/响应重放，stock 写 Serializable，SQL1205/唯一/rowversion code 4。
- `Controllers/Fnb/FnbV4StockControllers.cs`、`FnbV4KitchenControllers.cs`、`FnbV4FacilitiesControllers.cs`、`FnbV4ReportController.cs`、`FnbV4AlertController.cs`：完整新动作，保留旧 cron URL。
- `Services/Fnb/FnbV4Service.cs`、`FnbV4OperationService.cs`、`FnbV4KitchenService.cs`、`FnbV4FacilitiesService.cs`、`FnbV4CheckService.cs`、`FnbV4ReportService.cs`、`FnbConflictException.cs`：库存过账、FEFO、成本、转换、日期、推荐、配方、检查与报表。
- `Services/Fnb/FnbV4CatalogService.cs`：添加上游时“作业后保质”属于目标形态，修正此前错误落在新来源形态的问题。
- `SnowmeetApi.Tests/FnbV4WorkflowIntegrationTests.cs`、`FnbV4GuideIntegrationTests.cs`、`FnbSqlServerIntegrationTests.cs`、`FnbV4HttpContractTests.cs`：工作流、32 步、并发、权限、死锁、跨端会话及 HTTP 契约。

文档 `main`：新增完整契约、SQL 审阅说明、本记录及扩展 SQL；更新原计划、一期契约、H5 状态和 CLAUDE；更新离线 SQL 生成/LocalDB 运行器；清理 skill 精确白名单和照片引用同步到新 13 表，并扩充其隔离测试。原一期 SQL 内容未改。

## 验证

- API/测试工程构建 0 错误；现有项目 nullable 等警告保留，不宣称零警告。
- 全部非 SQL 单元/接口回归 **467/467 通过**，其中全部非食材现有测试通过。
- 随机 LocalDB **22/22 通过**：双端认证、权限与跨店、NoTracking 更新、真实 SQL1205 回滚；幂等与内容冲突；多行失败全部回滚；并发报损不透支；相邻/部分/封装作业、成本、有效到期、耗时和店长提前完成；FEFO、历史配方快照、缺口不负库存；过期确认销毁；盘点指纹和盘盈盘亏；区域绑定、物资流水和工具日志；检查草稿、数值标准、刷新、提交和追加处理；假消息网关去重。
- **32 步披萨/拿铁验收通过**：区域照片、温度项、七种食材及完整采购链；鲜奶整箱 2 箱=24000 ml 和单桶 2 桶=4000 ml；牛肉拆箱/切片 1880 g；芝士真实 24 小时限制，用隔离库就绪时间夹具验证到点自然可用；面粉/油/咖啡/鲜奶转换；饼底 2 批=12 个；检查提交确认；2 披萨+2 拿铁并微调芝麻菜；鲜奶盘到1200 ml、牛肉1740 g、油4880 ml，饼底余10个、芝士2670 g；物资仍100个；7 行配方链路 XLSX 导出可重新读取。
- 两份 SQL 在 LocalDB 重复执行，旧数据/单位/已有 v4 数据保留；全部 32 张表字段与 EF 对齐，无非新增操作。
- 新白名单 **50 表**清理工具隔离验证通过：个人/非食材逐行保留、未知表及共用文件拒绝、注入失败事务全回滚、幂等重跑、模拟 S3 及生命周期永久作废。未删生产数据或真实文件。

## SQL 与切换

生产一期已存在，只需先审阅 [扩展 SQL](../sql/2026-10-06_fnb_v4_operations.sql)，其 SHA256 `52632E5BCD021AEB99AAAB137007A1C23F8A38989FBF1F49F45A004ECD9FBDEC`；13 张新表、18 个新索引，无写旧数据或改变已有对象。审阅说明见 [对应文档](../docs/fnb/2026-10-06-fnb-v4-operations-sql-review.md)。审阅并明确执行后补结构，再发布 API，最后联调 H5。没有生产执行或部署。

## 与旧计划的差异、默认做法

- 按最新用户要求覆盖所有后端，包含之前排除的区域/检查/物资/工具，不再分期停工。69 个新动作加一期17个，总86个。
- 保持旧已发布表不变，批次位置与封装开封配置用伴随表；SQL只增加结构。旧数据库对象此前已删除，未重建。
- 配方按版本存档；订单引用创建时版本，避免改配方影响待出餐单。重复请求结果另存 journal，除了库存，还保护检查/工具的重试。
- 检查刷新同标准保留原结果，数值/方式/单位/引用变化须重填；比原型无条件保留更严谨。
- 半成品到期不超过已耗用料最早有效到期；盘盈缺现存批次时今天到期、零成本。报表平均周转使用成本，避免不同计量维度直接相加。
- 暂留已禁用的旧控制器/规则源码供编译及纯规则测试，旧业务路由不注册；未物理删除这一批源码。现有上传/OCR/OAuth/蓝牙保留。美团采集和自动订单导入仍按原计划后续处理，小程序不改。
- 五项默认全部遵守：仅店长提前完成、不提供作业撤销、投入允许小数、条码全局唯一、主数据共享而库存/配方分店。
- 本次只补后端；已部署 H5 后续占位按钮仍须联调，不把后端完成说成系统全部可用。

此前生产清理请求仍未执行：DSN 读取例外与 S3 删除权限信息未收到答复，临时 skill lifecycle 仍 testing。Git/Python standing 授权不覆盖这些具体限制。自动审批曾对一次 LocalDB 清理验证超时，按工具说明仅重试一次后成功；没有需要用户处理的自动审批阻塞。
