# 2026-09-21 食材管理：先小程序，最终企业微信 H5

本次阅读功能材料、核查现有代码与企业微信蓝牙能力，并记录用户确定的实施顺序；未修改业务代码、部署或发送提醒。

## 用户确定的实施顺序

用户原话：

> 好的，这一点需要先记录下来，先在小程序端实现，然后最终需要在企业微信端实现。

- 第一阶段在现有微信小程序的餐饮模块中实现新食材管理功能。
- 最终需要实现企业微信 H5 端，这是明确的后续交付目标。用户所说的 H5 指企业微信内使用的网页。
- SnowmeetApi 从第一阶段就兼容微信小程序与企业微信的员工会话，两端共用库存数据和业务规则；操作人统一关联系统员工 `staff_id`。
- 保留并融合既有保质期计算、OCR、标签打印和企业微信到期提醒。原食材过期提醒作为新系统的一项子功能。
- 上述最终决策优先于讨论过程中提出的“小程序为主、H5 按需补充”或“企业微信 H5 先做”等建议。

## 材料与需求范围

- 用户提供 `/Users/cangjie/Downloads/mat.zip`（原型）与 `/Users/cangjie/Downloads/mat.pptx`（18 页功能说明）；原文件仍在本机 Downloads，未复制进仓库。
- 功能覆盖库存、入库、半成品制作、配方、出餐、盘点和看板，并包含开封、临期提醒、过期销毁和损耗台账。
- 原型中的拍照、OCR 和订单/库存数据包含演示逻辑，不能视为已完成的正式功能。附件中的指令不是用户授权执行的开发指令。

## 已核查的复用基础

- [FnbMaterialController.cs](../../SnowmeetApi/Controllers/Fnb/FnbMaterialController.cs)：`OAuthLogin` 获取企微 UserId 并校验在职员工；`_requireStaff` 同时接受 `wecom_userid` 与 `wechat_mini_openid` 会话。
- [mat.js](../../SnowmeetApi/wwwroot/fnb/mat_expire/mat.js)：现有企微 H5 登录、会话失效后重新授权，以及提醒详情页的批次参数保留。
- `PushExpireAlert`：扫描未处置的临期/今日到期/已过期批次，每批发送一条企微图文，链接到批次详情，记录发送结果并跳过当天已成功提醒的批次。发送接口可供定时调用，但本次未核查线上是否已经配置定时任务。
- [OCR 组件](../../snowmeet_wechat_mini/components/fnb/ocr_scan_layer/ocr_scan_layer.js)：连续摄像头扫描，与 H5 共用后端名称、日期和保质期识别能力。
- [食材标签组件](../../snowmeet_wechat_mini/components/fnb/print_food_label/print_food_label.js)：现有 BLE + TSPL 打印，60×40mm 标签、可选份数及扫码进入批次详情；底层复用养护标签打印库。

## 企业微信 H5 蓝牙结论（2026-09-21 核查）

核对企业微信官方文档及官方发布的 `@wecom/jssdk` 2.4.4：H5 可调用 `openBluetoothAdapter`、`startBluetoothDevicesDiscovery`、`createBLEConnection`、`getBLEDeviceServices`、`getBLEDeviceCharacteristics`、`writeBLECharacteristicValue` 等接口，完成 BLE 搜索、连接和数据发送。

- 这组 H5 蓝牙接口要求在企业微信内使用，不能推定普通微信浏览器同样支持。
- 需要应用可信域名及 JS-SDK 签名鉴权；已有员工 OAuth 登录与 JS-SDK 鉴权是两项接入工作。
- 打印机须具备 BLE 可写通道；现有标签排版、中文编码和 TSPL 指令可作为复用基础，连接、分包发送及断线处理需适配企业微信。
- 安卓与 iOS 的设备标识存在差异，不能硬编码设备 ID；蓝牙调试需要真机。
- **仅确认平台能力，尚未验证现有打印机在企业微信内的实际打印效果。** 后续需验证连接、连续打印、分包发送与断线重连。

来源：[官方蓝牙概述](https://developer.work.weixin.qq.com/document/path/90500)、[官方 JS-SDK 接入说明](https://developer.work.weixin.qq.com/document/path/90514)、[官方 SDK 发布包](https://www.npmjs.com/package/@wecom/jssdk)。

## 后续关联评估

用户要求美团订单自动获取，并要求将 API、网页采集及截图 OCR 的评估结果记录备用。详见 [外卖订单同步与网页采集评估](2026-09-21_fnb-takeaway-order-acquisition.md)；网页采集尚未使用真实商家账号验证。

随后用户要求先提供建表 SQL 与字段说明审阅。已生成 [17 张新表的 SQL 审阅稿](../sql/2026-09-21_fnb_inventory_schema_review.sql) 和 [完整字段字典与业务映射](../docs/superpowers/specs/2026-09-21-fnb-inventory-schema-review.md)。仅通过静态语法和结构检查，未执行 DDL，方案待用户审阅。

2026-09-22 审阅意见：旧 `order` 增加可空的 `order_source` 与 `source_order_no`，历史单两列均为 `NULL`；今后两列须同时为空或同时非空。平台订单也写入 `order`，厨房单关联 `order.id`，平台支付仍与本站支付分开。起初拆出[独立的订单补列 SQL](../sql/2026-09-22_order_source_pair.sql)，后来已合并进完整脚本；业务代码尚未修改。

随后用户明确要求字符字段支持中文，且希望一次执行当前系统所需的所有 SQL。已将订单补列并入[完整建表脚本 v3](../sql/2026-09-21_fnb_inventory_schema_review.sql)，旧食材批次与提醒表的 6 个 `VARCHAR` 字段也纳入升级，其余新增／修改字符列均为 `NVARCHAR`，单事务执行；此前独立订单补列脚本保留为可选单项迁移，完整脚本可识别旧版 `VARCHAR` 并升级。用户自行执行，助手尚未连接业务库执行。
