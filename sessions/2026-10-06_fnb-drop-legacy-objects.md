# 2026-10-06 删除旧食材表和视图

用户先要求列出旧版中 v4 不再使用的数据库表；确认 18 张旧表与 2 个旧视图后，明确要求“帮我 drop 掉，不留垃圾”。此指令覆盖本次生产 DROP，取代此前对这 20 个对象的保留限制，不扩大到单位、v4、员工、共享业务表或实际上传文件。

## 执行结果

- 目标生产库 `snowmeet_new`，经既有 `44.207.251.65:2222` SSH 转发到 mini 服务器操作。只在服务器内部使用已有连接配置，未读取 Windows 本机 `SnowmeetApi/config.sqlServer`，未复制或打印凭据。
- 已执行 [2026-10-06_fnb_drop_legacy_objects.sql](../sql/2026-10-06_fnb_drop_legacy_objects.sql)，SHA-256 `5382593c9bdcc36cf8e2918b19908b57658464a8b768684e4ebc9165f4a78663`。
- 实际删除 **18 张表、2 个视图**；原表共 **299 条旧食材测试记录**随表删除。重复执行安全；对象清单完全不存在。
- 保留 `fnb_unit`、18 张 `fnb_v4_*` 表、`vw_fnb_v4_stock`、`vw_fnb_v4_loss`，以及全部员工/认证/共享业务表。所有清单外对象和列结构哈希与执行前相同；单位行哈希相同，员工仍 59 行。
- `mini.snowmeet.top.service` active/running，MainPID 37224、NRestarts 0；本机和公网 Swagger HTTP 200、518 条路径；失效会话 `FnbAuth/GetMe` HTTP 200 / code 2。
- 没有 API 代码变更、重新部署、重启、修改美团采集器、小程序或页面；没有执行测试数据清理 skill，没有清理共享餐饮记录、单位数据、上传记录或实际文件。

## 删除对象

表：fnb_material_category、fnb_material_item、fnb_shelf_life_rule、fnb_material_batch、fnb_material_batch_stock、fnb_material_alert_log、fnb_dish_spec、fnb_recipe、fnb_recipe_line、fnb_stock_document、fnb_stock_document_line、fnb_stock_movement、fnb_stocktake_line、fnb_order、fnb_order_line、fnb_order_import、fnb_channel_shop、fnb_channel_dish_map。

视图：vw_fnb_material_stock、vw_fnb_material_loss。

## 备份和回滚

生产数据文件约 3.2 GB，服务器根盘只剩约 1 GB，未做占满磁盘风险较大的全库备份。仅导出目标 20 个对象的结构、299 条测试记录及恢复 SQL，未导出员工或共享业务表。备份保存在服务器私有目录 `/home/ubuntu/fnb-drop-legacy-20261006/backup`（目录 700、文件 600），未在业务库里创建备份表。

- `restore.sql` SHA-256：`cce7417ad1d5773237924a5aebe24b01fac15941e4615b715e0188559515ecb3`
- `catalog.json` SHA-256：`7e7ae89634fbe52ed146ae61ebc5101762a791f01dedc73c0ede66599e97bb0d`
- `manifest.json` 记录对象与行数；执行结果、执行前快照和验证记录分别在同目录上层 result.json、before.json、verification.json。

导出工具 [backup_legacy_objects.py](../tools/fnb/backup_legacy_objects.py) 仅使用调用方传入的连接，不自动读配置；保存列、默认值、身份值、索引、CHECK、外键、视图、扩展属性和权限元数据。恢复 SQL 支持基本结构、可写数据、身份 ID、索引、CHECK、外键和视图；扩展属性/权限保存在 catalog 供核对。ROWVERSION 在恢复时重新生成，原二进制值保存在 catalog。恢复需先在隔离库核对，且共享父记录存在；不应将生产整库回退为旧版本。

## 验证

`py tools/windows_test/run_integration_localdb.py --verify-drop-legacy-fnb` 全部通过，最终随机 LocalDB `snowmeet_fnb_test_0cd4e34a9517` 已删除。验证错库/缺少备份确认/已有外层事务拒绝、外部外键/视图/动态 SQL/同义词/DDL 触发器拒绝、实际删完所有旧对象后异常全回滚、只删目标对象且保留数据不变、重复执行，以及备份恢复可写数据/身份 ID/自引用与循环外键/CHECK/索引/视图。

本轮只修改 SQL、导出工具、验证运行器及文档，未改 EF 模型或应用代码，未重新运行无关单元测试。后续不能启用旧业务接口、重建旧食材表或部署依赖旧表的服务端版本；第二、三期继续使用已有 v4 结构。
