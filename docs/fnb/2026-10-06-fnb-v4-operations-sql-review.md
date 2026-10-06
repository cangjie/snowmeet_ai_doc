# v4 扩展 SQL 审阅说明

脚本：[2026-10-06_fnb_v4_operations.sql](../../sql/2026-10-06_fnb_v4_operations.sql)。SHA256：`52632E5BCD021AEB99AAAB137007A1C23F8A38989FBF1F49F45A004ECD9FBDEC`。

只创建 13 张新的 `fnb_v4_*` 表和 18 个索引。无 INSERT、UPDATE、DELETE、DROP、TRUNCATE、MERGE、ALTER；不会改已有表、字段、视图、员工记录或业务数据。先检查一期 `fnb_v4_batch` 已存在。已有新表/索引跳过；同名表缺预期字段会抛错回滚，要求人工核对，不自动覆盖。DDL 在一个事务中执行。

| 新表 | 用途 |
|---|---|
| fnb_v4_area | 分店两级存储区域 |
| fnb_v4_area_image | 区域照片与上传记录关联，含员工和时间 |
| fnb_v4_batch_detail | 现有批次的区域、无链路封装的开封配置；使用伴随表避免改批次表 |
| fnb_v4_request | 请求 UUID、内容摘要、首次响应和审计，用于幂等重试 |
| fnb_v4_supply | 餐饮物资档案、个数余额与预警配置 |
| fnb_v4_supply_movement | 入库、领用、报损与撤销标记 |
| fnb_v4_tool | 工具档案、数量、区域、状态、责任人及检查配置 |
| fnb_v4_tool_log | 工具状态、位置变化日志 |
| fnb_v4_check_item | 检查项、标准及工具/物资引用 |
| fnb_v4_check_sheet | 每店每日一张检查单及流程审计 |
| fnb_v4_check_line | 检查配置快照、员工实测与原始结果、照片 |
| fnb_v4_check_handling | 店长追加处理记录，不覆盖员工检查结果 |
| fnb_v4_alert_delivery | 批次/营业日提醒去重及发送状态 |

所有新外键禁止级联删除。位置、状态和业务约束由服务端检查，SQL 同时约束物资余额、工具数量和检查方式。时间戳 UTC datetime2(3)，营业日/date 独立列；字符串沿用 Chinese_PRC_CI_AS 的 VARCHAR。库存行已有 rowversion；新增物资、工具、检查单、提醒记录也使用 rowversion。

本机随机 LocalDB 已验证两份 SQL 重复执行，旧表/单位/已有 v4 数据保留，全部 32 张食材/单位表字段与 EF 对齐。用户审阅后明确要求立刻部署，本扩展 SQL 已在生产 `snowmeet_new` 成功新增 13 张表、18 个索引，已有结构未变、没有数据写入或删除；随后发布完整后端，见 [生产部署记录](../../sessions/2026-10-06_fnb-v4-operations-production-deploy.md)。无需再次执行。

切换顺序：用户审阅脚本 → 用户明确执行后补生产结构 → 发布完整 API → 联调并发布 H5 新接口接入。第一期重建 SQL 未修改；已经执行过一期的生产只需这份扩展 SQL。新增 API 不会自动启用原 H5 的占位按钮。
