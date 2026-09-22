# 食材管理服务器 API 开发计划（审阅稿）

日期：2026-09-22。范围：完成 SnowmeetApi 服务端与 SQL Server 验证；小程序客户端由用户安排 Claude 开发并独立审查服务端代码，企业微信 H5 后续使用同一业务 API。本文是实施依据，开发进度以代码和验证记录为准。

范围修订（2026-09-22）：用户明确表示平台门店／SKU 映射不在需求中。服务端不提供这两类映射及依赖它们的渠道导入接口；已执行的建表脚本和线上空表暂不改动。当前数据库约束要求平台订单关联 `fnb_channel_shop`，所以平台订单自动导入和截图补录暂不作为本轮可用接口；后续需先根据实际业务重新确定订单识别和菜品匹配方式。库存、本站餐饮订单和出餐继续实施。本轮仅用 SQL Server 隔离库做集成写入测试，业务库只读核对。

订单入口修订（2026-09-22）：用户确认先由员工直接选择现有菜品和数量手动建立厨房单；`order`／`fd_order` 自动同步接口后置。本轮不引入 SKU。数据库中的 `fnb_dish_spec` 仅作为一菜一份的内部配方目标；没有记录时服务端自动建立“标准份”，不要求员工填写规格编码。尚未发布配方的手动单保留为待核对，不能出餐扣料。

## 已确认的起点

- 目标库 `snowmeet_new` 已建好 17 张新表、2 个视图及基础单位；只读结构核对无差异。2026-09-22 按用户要求清空旧效期数据后，`fnb_material_batch` 和 `fnb_material_alert_log` 均为 0 条；新 `fnb_material_batch_stock`、`fnb_material_item`、`fnb_stock_document` 和 `fnb_order` 目前为空。旧效期照片位于共享上传系统，未随业务表清理。
- 现有 `FnbMaterialController` 已支持小程序员工会话和企业微信员工会话，并有批次、OCR、图片、到期提醒接口；小程序已有 BLE 标签打印组件。现有 `SaveBatch`、`DisposeBatch`、`DeleteBatch` 可以直接改旧批次，必须在库存启用前加兼容保护。
- `ApplicationDBContext` 尚未映射新表，`Order` 模型尚未映射 `order_source` 和 `source_order_no`。新业务不能直接复用当前旧批次的写法或把外卖代收款记作本站收款。

## 实现方式

按业务拆为档案、效期与库存、配方与制作、本站厨房订单、盘点与报表五组 API。控制器负责鉴权和输入输出；业务服务负责规则与事务；数据库映射按已执行 SQL 精确配置。沿用项目的 `api/[controller]/[action]` 路由和 `ApiResult<T>` 返回格式，新增写操作一律 POST，列表和详情使用 GET。旧录入接口在新入库切换前保留现状，切换后不再允许新增无库存扩展的批次。

每次请求由服务端用 `sessionKey` 判定在职 `staff_id`，兼容 `wechat_mini_openid` 与 `wecom_userid`，再核验当前门店权限；不信任客户端传入的员工身份。建议首版将 `staff.base_shop_id` 作为可操作门店，在职员工可执行日常入库、开封、出餐和查询，`title_level >= 200` 才能维护档案、发布配方、确认期初与盘点、销毁及查看成本。跨门店授权如有现成规则则沿用，不由客户端传门店 ID 自行越权。

所有库存写入通过同一过账服务完成：同事务写旧效期批次、库存扩展、业务单据、明细、批次流水并更新余额；使用 `request_id` 幂等、行版本/数据库锁防并发超扣。数量与金额使用 `decimal`，服务端保存基本单位 g、ml、piece；对外 BIGINT ID 用字符串，日期按上海营业日期和 UTC 审计时间区分。到期日以批次快照为准，OCR 和规则计算仅提供候选，人工确认后才入库。中文输入需按已建 `VARCHAR` 的实际编码能力校验，避免不能表示的字符静默变问号。

## 分阶段交付

| 阶段 | 服务器接口与结果 | 验收重点 |
|---|---|---|
| 1. 公共基础与旧接口保护 | 映射本轮使用的食材、库存、配方、订单及报表对象；统一双端员工鉴权、门店权限、日期/单位/成本工具；`FnbMaterial` 的旧写接口对有库存扩展的批次禁止直接编辑、处置或软删，启用新入库接口时关闭旧无库存批次新增入口 | 新批次不能绕过库存流水；无权员工不能跨店读取或写入；切换前旧端行为按现状保留 |
| 2. 档案、效期与入库 | `FnbCatalog` 的单位、分类、保质期规则、食材档案查询/维护；`FnbInventory` 的效期预览、库存/批次列表与详情、采购入库、标签数据接口；复用现有照片上传与 OCR | 校验二级分类、单位维度、效期来源、照片、成本；入库有完整单据/流水；库存从新入库开始，不做历史批次期初接管 |
| 3. 开封、报损与提醒 | `FnbInventory` 的开封、报损/销毁、单据详情和流水查询；改造 `PushExpireAlert` 对已接管批次按门店、剩余量、处置状态判断，保留现有去重和推送记录 | 未开封不能直接供制作/出餐；开封数量/成本守恒且最终效期不延长；销毁不可恢复；已清零/已销毁批次不重复提醒 |
| 4. 菜品配方与半成品制作 | `FnbRecipe` 的菜品规格、配方草稿/明细、发布新版本、当前版本查询；`FnbInventory` 的半成品制作预览与过账 | 对接 `product`，历史版本不可改；制作按配方比例和 FEFO 扣料，任一原料不足整单回滚；产出成本等于实际耗料成本 |
| 5. 厨房订单与出餐 | `FnbKitchen` 的手动建单、列表/详情、取消、配方核对、出餐预览与过账；本站 `order`/`fd_order` 自动同步后置 | 手动单以请求号去重；已出餐不重复扣料；缺配方阻止出餐，缺库存记录欠料但不生成负库存 |
| 6. 盘点与基础报表 | `FnbStocktake` 的快照、录入、差异预览、确认过账；`FnbReport` 的库存、临期、损耗与盘盈查询，复用现有视图 | 快照期间库存变动会要求重新盘点；盘盈效期/成本需确认；报表数量和成本可追溯至批次流水 |

平台自动拉单与截图补录留待订单识别方式确定后单独设计，不在本轮 API 范围。

拟提供的主要 action 如下；执行时会形成逐接口请求/响应文档，现有 `FnbMaterial` 的 OAuth、照片上传和 OCR 接口继续复用。

| 控制器 | 主要 GET action | 主要 POST action |
|---|---|---|
| `FnbCatalog` | `GetUnits`、`ListCategories`、`ListShelfLifeRules`、`ListMaterials`、`GetMaterial` | `SaveCategory`、`SaveShelfLifeRule`、`SaveMaterial` |
| `FnbInventory` | `PreviewExpiry`、`GetStock`、`ListBatches`、`GetBatch`、`GetLabelData`、`GetDocument`、`ListMovements` | `PostReceipt`、`PostOpen`、`PostWaste`、`PostPreparation` |
| `FnbRecipe` | `ListDishSpecs`、`GetRecipe`、`ListRecipes` | `SaveDishSpec`、`SaveRecipeDraft`、`PublishRecipe` |
| `FnbKitchen` | `ListOrders`、`GetOrder`、`PreviewServe` | `CreateManualOrder`、`CancelManualOrder`、`ReviewOrder`、`PostServe` |
| `FnbStocktake` | `GetSnapshot`、`PreviewAdjustment` | `CreateSnapshot`、`SaveCount`、`PostStocktake` |
| `FnbReport` | `GetOverview`、`GetLossLedger`、`GetExpirySummary` | 无 |

## 接口契约与错误语义

- 列表接口统一 `shopId`、筛选、分页；返回批次效期状态、数量和单位的服务端结果。批次标签返回名称、批号、最终效期和稳定的扫码 URL，由小程序现有 BLE/TSPL 组件打印；未来企微 H5 仍用同一标签数据，另适配 JS-SDK 蓝牙。
- 过账请求包含稳定 `requestId`；重复请求返回首次过账结果。编辑草稿和盘点提交传行版本；业务冲突返回明确的“库存已变化/需要刷新”错误。服务端重新计算数量与成本，复核效期来源和日期逻辑；人工确认的到期日与依据一起保存到批次快照。
- 未登录、无门店权限、输入错误、库存冲突、待人工核对分开返回，沿用现有 `ApiResult` 外层格式；服务端记录操作人、门店、请求 ID 和单据号。

## 代码落点与验证

主要修改 `SnowmeetApi/Data/ApplicationDBContext.cs`、`Models/Fnb/`、`Controllers/Fnb/`，新增按职责拆分的 Fnb 服务和请求/响应 DTO；只对 `Order` 模型、旧 `FnbMaterialController` 及必要的订单展示/支付分流逻辑做定点修改，不重写现有支付体系。配套维护接口清单和字段映射文档。

每阶段做业务规则单元测试及 SQL Server 集成测试，覆盖幂等重试、并发扣减、事务回滚、FEFO、成本尾差、跨店权限、月末效期、开封与销毁、旧接口兼容。集成写入测试使用隔离测试库；业务库仅执行只读核对，不拿真实订单和库存作测试数据。每阶段通过构建与相关测试后再进入下一阶段。

## 已确认的实施边界

1. 本轮只实现并验证服务器端；小程序客户端由 Claude 负责，本轮不修改小程序或企业微信 H5 页面。
2. 食材管理集成写入测试直接使用隔离 SQL Server 数据库，不为本模块增设 SQLite 测试方案。
3. 暂按在职员工执行日常操作、`title_level >= 200` 管理档案、发布配方、确认盘点、销毁和查看成本实施。若后续确认已有餐饮专属授权规则，再按实际权限规则调整。
