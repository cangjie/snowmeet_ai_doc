# 食材管理 v4 重建计划（服务端）

## 背景

用户在 Claude Design 更新了「食材管理 v4」原型（项目 442106f7：`食材管理 v4.dc.html`、`食材管理 从零上手操作说明.dc.html`、`食材形态流转 方案.dc.html`）。2026-10-06 用户决定**推翻重来**：

- 现有食材数据全部不要。
- 能复用的只有三样：**店员登录认证体系**、**部分表结构**、**部分 API 接口**。
- 前端（小程序 + 企业微信 H5）基本推倒重做。本计划只覆盖服务端：数据库、接口，以及如何同时兼容两个客户端。

**范围（用户已定）**
- 做 v4 原型里除 10/02 那批以外的全部功能：
  - 库存、入库、作业台、出餐、临期与销毁、用量预警
  - 分类与分类属性、形态链路与进货规格、半成品、菜品配方
  - 盘点、看板与报表导出
- **不做**：
  - 10/02 那批（存储区域、开门检查、餐饮物资、餐饮工具），还在等崔洋确认；
  - 美团订单导入，用户说「各模块开发好后一定会接上」。
  
  这两块都要在结构上预留好接口。
- 分类属性的规则：分类给默认值，食材可以单独改。

**v4 的核心模型**
- 每种食材是一条**形态链**：采购态 → 中间态 → 出品态。
- 相邻形态之间只走一个固定**作业**，例如拆箱、开盖、冷藏解冻、切片。作业有换算、标准出成率和可选耗时。
- **入库只进进货规格指定的那一层，配方和出餐只扣出品态。**
- 没配链路的食材按默认处理：
  - 散装：入库即出品态；
  - 封装：一步「开封」。
- 半成品是「多原料作业」，按「每批产出 × 批数」制作。

---

## 复用与废弃

**复用**

| 类别 | 内容 |
|---|---|
| 认证 | `Services/Fnb/FnbAccess.cs` 的 `ResolveActorAsync` / `CanAccess`：`mini_session` 两种会话（`wechat_mini_openid`、`wecom_userid`），店员按 `base_shop_id` 定门店，`title_level ≥ 200` 为店长；`FnbMaterialController.OAuthLogin` 里企业微信 code 换 UserId 再过在职店员闸门的逻辑 |
| 表结构 | `fnb_unit`（保留数据）；分类树、食材、保质期规则、配方/配方行、菜品规格（挂在 `product` 上）、单据/单据行/流水账、盘点行、厨房单/厨房单行/订单导入日志——**结构思路复用，按新模型重建** |
| 接口与代码 | `ApiResult` 返回码 0/1/2/3/4；requestId 幂等；Serializable 过账骨架和单号生成（`FnbStockPostingService`）；FEFO 分配与到期计算（`FnbInventoryRules`）；照片上传（`UploadPhoto`）；OCR（`OcrScanName`）；JS-SDK 签名（`FnbWeComController`）；标签打印数据；long id 序列化成字符串 |

**废弃**
- 所有现有 fnb 业务数据。
- 旧的食材过期提醒：`fnb_material_batch` / `fnb_material_alert_log`，`FnbMaterialController` 的批次接口，`wwwroot/fnb/mat_expire` H5，小程序 `mat_expire` 页面，以及小程序现有的 `pages/fnbinv` 分包。新系统已包含临期提醒。

---

## 第一部分：数据库（一份重建脚本）

脚本：`snowmeet_ai_doc/sql/2026-10-xx_fnb_v4_rebuild.sql`，可重复执行，分两段。

**第 1 段：删旧**
- 删除对象：
  - 两个视图：`vw_fnb_material_stock`、`vw_fnb_material_loss`；
  - fnb 库存类表：`fnb_material_batch_stock`、`fnb_stock_document`/`_line`、`fnb_stock_movement`、`fnb_stocktake_line`、`fnb_recipe`/`_line`、`fnb_dish_spec`、`fnb_order`/`_line`/`_import`、`fnb_channel_*`、`fnb_shelf_life_rule`、`fnb_material_item`、`fnb_material_category`；
  - 旧提醒表：`fnb_material_batch`、`fnb_material_alert_log`。
- 删除顺序按外键依赖倒序。
- **不动**：`fnb_unit`（保留种子数据）、`product` 表（共享表，旧菜品行留着不删）、`[order]` 上的 `order_source` / `source_order_no`。

**第 2 段：新建**

沿用现有约定：VARCHAR 用 `Chinese_PRC_CI_AS`；`*_at` 列为 DATETIME2(3) UTC；营业日期按 Asia/Shanghai；不用级联外键。

**主数据：门店间共享**

| 表 | 要点 |
|---|---|
| `fnb_category` | 两级树：`parent_id`、`level`、`name`、`sort`、`valid`。二级分类的属性：`batch_code`（批次号编码，二级分类内唯一）、`measure_type`（weight/volume/count，对应 `fnb_unit.dimension`）、`default_storage`、`warn_days`（临期提前提醒）、`open_days`（开封/作业后保质）、`is_prepared`（半成品分类） |
| `fnb_shelf_life_rule` | `category_id` 与 `item_id` 二选一（食材级覆盖分类级）；`storage_type`；`season`（all / warm / cold，warm = 6–9 月）；`days`；`valid` |
| `fnb_item` | `category_id`、`name`、`item_type`（raw/prepared，由分类决定）、`base_unit_code`（g/ml/piece，即出品态的单位）、`warn_days` / `open_days`（null = 跟分类）、`low_stock_ratio` / `low_stock_qty`（二选一，都为空时按最近入库量 × 10%）、`image_id`、`valid` |
| `fnb_item_form` | 形态链，每种食材至少一行，即出品态。字段：`item_id`、`seq`（0 = 最上游，最大 = 出品态）、`name`、`unit_name`（箱/桶/ml，只做显示）、`per_base`（1 单位等于多少基本单位，出品态 = 1）、`storage_type`、`shelf_after_op_days`（null = 沿用原到期）、`form_code`（派生批次号后缀）。到达本形态的作业：`in_op_name`、`in_op_ratio`、`in_op_yield`、`in_op_hours`（seq 0 为空）。另有 `valid`。过滤唯一（`item_id`, `seq`） |
| `fnb_purchase_spec` | 进货规格：`item_id`、`entry_form_id`、`name`、`brand`、`pack_desc`、`barcode`（启用中的规格全局唯一）、`valid`、`sort`。被入库行引用后只能停用 |

**门店数据**

| 表 | 要点 |
|---|---|
| `fnb_batch` | **取代旧的两张批次表**。字段：`shop_id`、`item_id`、`form_id`、`batch_no`；`state`（三种：sealed = 未配链路的整件封装，只能落在出品态；staged = 链路中间态，不能扣；final = 出品态，可扣）；`quantity` / `amount`（**一律按基本单位**，形态单位只做显示）；`pack_size` / `pack_label`（仅 sealed）；`storage_type`；`production_date`、`expire_date`（原到期）、`op_date`、`op_expire_date`；`effective_expire`（计算列，取原到期与作业后到期中较早的一个）；`expiry_source`；`parent_batch_id`（来源批次）；`ready_at`（耗时作业完成时刻，之前不能扣、不能继续作业）；`spec_id`；`received_at`；`dispose_status`（null / used_up / wasted / destroyed）；`row_version`。CHECK 约束沿用旧表思路：不为负、sealed 必须是整件、销毁后数量为 0 等。批次照片放子表 `fnb_batch_image(batch_id, upload_id)` |
| `fnb_stock_document` / `_line` / `fnb_stock_movement` | 沿用旧结构（单据 → 单据行 → 批次级流水，流水上记过账后余额；(`shop_id`, `document_type`, `request_id`) 唯一，用来保证幂等）。外键改指 `fnb_batch`。`document_type`：receipt / op / prep / serve / waste / destroy / stocktake。单据行增加 `spec_id`、`form_id` |
| `fnb_stock_operation` | 一次作业一行，覆盖链路作业和封装开封：`document_id`、`item_id`、`from_form_id`、`to_form_id`、`source_batch_id`、`output_batch_id`、`op_name`、`input_qty`、`std_ratio`、`std_yield`、`expected_qty`、`actual_qty`、`loss_base_qty`、`duration_hours`、`ready_at`、`status`（running/done）、`completed_at`、店员 id |
| `fnb_recipe` / `fnb_recipe_line` | 沿用旧结构：版本化、发布。半成品配方的 `output_qty` = 每批产出 |
| `fnb_dish_spec` | 沿用旧结构（挂在 `product` 上）。增加过滤唯一（`product_id`, `name`），**为以后按「菜品名 + 规格名」匹配外部订单做准备** |
| `fnb_stocktake_line` | 沿用旧结构；只盘出品态 |
| `fnb_order` / `_line` / `fnb_order_import` | 沿用旧结构：现在用于手动建的厨房单；以后订单导入直接写这几张表，`source_type` 和外部单号字段已经有了 |

**视图**
- `vw_fnb_stock`：按门店 + 食材汇总。
  - 可出餐量：只算 state=final、未过期、`ready_at` 已到的批次；
  - 各中间形态的待作业量；
  - 整件封装的数量；
  - 平均成本。
- `vw_fnb_loss`：报损、过期销毁、盘点差异、作业损耗（取自 `fnb_stock_operation`）。

**预留**
- 10/02 那批确认后，加 `fnb_storage_area`，并给 `fnb_batch`、`fnb_item_form`、`fnb_purchase_spec` 加可空的 `area_id`。都是新增列，与本结构不冲突。

**EF**
- 删除旧模型和 DbSet（`Models/Fnb/*`、`Data/FnbSchemaConfiguration.cs`），按新表重写。
- `FnbSchemaMappingTests` 改为校验新表。

---

## 第二部分：服务端接口（按 v4 页面分模块）

约定不变：
- 路由 `/api/[controller]/[action]`。
- 权限：S = 本店在职店员，M = 店长。
- **所有改库存的写接口都带 requestId，放在 Serializable 事务里**。
- SQL 死锁 1205 一律映射成 code 4（客户端用同一个 requestId 重试）。

| 模块 / 控制器 | 接口 |
|---|---|
| 认证 `FnbAuth` | `GetMe`（店员 id、姓名、门店 id、店名、是否店长、客户端类型）；`WeComLogin(code)`（企业微信换 UserId → 在职店员闸门 → 建会话，返回内容同 GetMe） |
| 首页 `FnbHome` | `GetHome`：首页各卡片的数字——用量预警数、临期/过期批次数、在库品种、批次数、已开封数、进行中作业数、建议作业数 |
| 分类 `FnbCatalog` | `ListCategories`、`SaveCategory`（M，含分类属性）、`DeleteCategory`（M，只能删没有食材的）；`ListShelfRules` / `SaveShelfRule`（M，分类级或食材级）；`ListUnits(measureType)` |
| 食材与链路 `FnbRoute` | `ListItems`；`CreateItem`（M：二级分类 + 名称 + 出品态名称 + 基本单位，同时建出品态）；`GetRoute(itemId)`；`AddUpstreamForm`（M，在最上游加形态和作业）；`UpdateForm`（M）；`RemoveForm`（M，只能删最上游、无库存、无规格引用的）；`SaveSpec`（M，有库存的规格只能停用）；`FindSpecByBarcode` |
| 入库 `FnbInbound` | `NextBatchNo(itemId)`：生成 `yyMMdd-<分类编码>-NN`，同店同日顺号。`PreviewExpiry`：保质期规则按「食材 → 分类」回退，按生产月份分档。`PostReceipt`：一次提交「今日入库单」的多条，每条带规格（已配链路时必填）、数量（按入口形态单位）、储存方式、日期、照片；未配链路的选散装或封装（包装规格、每件含量、开封后储存/保质）；**拒绝已过期**。`DeleteReceipt`：10 分钟内、没有后续流水才能撤销 |
| 库存 `FnbStock` | `ListStock`：按一级/二级分类、储存方式、关键字过滤；每种食材返回可出餐量、各层待作业量、可出餐份数（按配方用量折算）、标签。`GetItemLayers(itemId)`：按形态分层，每层列批次和下一步作业名。`GetBatch`。`ListExpiry`：已过期、今日到期、临期分组。`ListDestroy` / `PostDestroy`：过期批次的「确认已销毁」。`PostWaste`（M）：报损。`ListLowStock` / `SaveLowStockRule`（M） |
| 作业台 `FnbOperation` | `GetWorkbench`：进行中的耗时作业、建议作业（出品态低于预警线且上游有批次）、可作业批次、今日记录。`PreviewOperation(batchId, qty)`：换算、预计产出、新批次号（来源批次号-形态代码）、到期、默认储存方式。`PostOperation`：一次作业——扣来源、产出新批次、记损耗和出成率；出成率偏低只提示；耗时作业写 `ready_at`；封装开封也走这个接口。`CompleteOperation`（M）：提前完成耗时作业；到点后自动可用，不需要操作 |
| 半成品 `FnbPrep` | `ListPreps`；`CreatePrep`（M：分类 + 名称 + 单位 + 每批产出，同时建食材和配方）；`SavePrepBom`（M，原料只能是出品态）；`PostPreparation`（批数 × 每批产出，原料按先到期先出扣）；`ListPrepRecords` |
| 菜品配方 `FnbDish` | `ListDishes`；`CreateDish`（M：名称 + 默认规格名）；`AddSpec` / `DeleteSpec`（M）；`SaveSpecLines`（M，每行一种出品态食材 + 每份用量）。同一菜品下规格名唯一 |
| 出餐 `FnbServe` | 订单导入接上之前，厨房单手动建：`CreateOrder`（多道菜 × 规格 × 份数 + 备注）。`ListPendingOrders`。`PreviewServe`：带出默认用量和各食材库存，库存不足时返回上游还剩多少、下一步作业是什么。`PostServe`：可按备注微调用量；只扣出品态，按先到期先出扣到具体批次；不足时记欠料，不允许负库存；回写 `order_status=served`。`ListServeLog`：扣减流水 |
| 盘点 `FnbStocktake` | `CreateSnapshot`（只取出品态）、`SaveCount`、`PostStocktake`（差异记入损耗台账） |
| 看板与报表 `FnbReport` | `GetDashboard`：本周损耗率、平均周转、在库成本结构、损耗台账。`GetRecipeChain`：「出品与配方链路」预览，每道菜 × 每种用料一行，带出采购态和各段转化（作业、形态、单位、存储、出成率），列格式对照设计稿附件 `pizza-latte-report.xlsx`。`DownloadRecipeChain`：GET 返回 xlsx 文件流，用 NPOI |
| 公共 | `UploadPhoto`、`OcrScan`（生产日期、到期日、保质期、名称）、`GetLabelData`（标签二维码指向下文第 6 点的统一链接）、`GetJsSdkSignature`，都从旧控制器迁过来。`PushExpireAlert`：按新表改写，供 crontab 定时调用 |

**核心规则一律放在服务端，有单元测试覆盖：**
- 换算与出成率：投入按上游单位 × `per_base` 折成基本单位；产出按实际值记；损耗 = 投入基本量 − 产出基本量。产出成本 = 投入成本。
- 到期：作业产出的到期 = min（来源到期，作业日 + 作业后保质）；没设作业后保质就沿用原到期。开封保质：食材 → 分类 → 「不变」。
- 能扣的批次：state=final、未过期、未处理、`ready_at` 已到。出餐、半成品、盘点共用这一个判断。
- 临期提醒天数：食材 → 分类 → 1 天。
- 用量预警线：固定值，或最近入库量 × 比例（默认 10%），二选一。

---

## 第三部分：同时兼容小程序和企业微信 H5

1. **身份统一**：两端都通过 `FnbAccess.ResolveActorAsync` 解析会话。企业微信用 `FnbAuth/WeComLogin` 拿会话，小程序沿用现有的 `MemberLogin` 会话。之后两端都用 `GetMe` 拿店员、门店和角色。单据的 `source_client` 记 mini 或 wecom。
2. **先定接口契约，两端照着做**：开发第一期时写出 `snowmeet_ai_doc/docs/fnb/2026-10-xx-fnb-v4-api-contract.md`，包括每个接口的入参出参、返回码，以及哪些字段由服务端计算。
3. **规则只在服务端**：有效到期、换算、预计产出、出成率、批次号、建议作业、分层合计、可出餐份数、报表行，全部由接口直接返回成品数据。v4 原型里写在前端的计算全部搬到服务端，两端只负责展示和收集输入。
4. **统一调用约定**：
   - sessionKey 放 query；GET 的 shopId 放 query，POST 的 shopId 放 body。
   - 返回码 0 成功、1 业务错误、2 会话失效（重新登录）、3 无权限、4 冲突（用同一个 requestId 重试）。
   - long id 一律序列化成字符串。
   - 营业日期由服务端计算。
5. **扫码**：条码由服务端 `FindSpecByBarcode` 解析。小程序用 `wx.scanCode`；企业微信用 `ww.scanQRCode`，页面需放在 `mini.snowmeet.top` 下才能拿到签名。
6. **标签二维码**：内容统一为 `https://mini.snowmeet.top/fnb/b?id={batchId}`。企业微信里打开 H5 批次页；小程序在公众平台登记「扫普通链接打开小程序」规则后跳到批次页。两端都调 `GetBatch`。
7. **文件**：
   - 照片上传接口支持 multipart，浏览器也能直接用。
   - 报表下载走 GET 文件流（参数带 sessionKey）。小程序用 `wx.downloadFile` 加 `openDocument`，downloadFile 合法域名要包含 `mini.snowmeet.top`；H5 直接打开链接。
8. **权限只在服务端判断**。企业微信店员必须有 wecom 社交账号映射，且有 `base_shop_id`。H5 与接口同域，不需要 CORS。建议把 `FnbWeComController.cs:30` 里硬编码的应用密钥移到配置文件。

---

## 分期与切换

- **第 1 期**：重建脚本 + EF 模型；`FnbAuth`；分类与分类属性；食材与链路、进货规格、条码查询；接口契约文档。
- **第 2 期**：入库；库存、分层、批次、临期与销毁、报损、用量预警；作业台与作业过账；首页。
- **第 3 期**：半成品、菜品配方、出餐（手动厨房单）、盘点、看板与报表导出；公共接口迁移；`PushExpireAlert` 改写。最后删除旧的 `FnbMaterialController` 批次接口和旧食材控制器。

**上线切换**（由用户执行，不在开发范围内）：
1. 后台隐藏旧的食材入口；
2. 在生产库执行重建脚本；
3. 发布 API；
4. 发布新的两个客户端。

**执行重建脚本后，旧页面和旧 H5 会立即失效**，所以必须先隐藏入口。

## 关键文件

- 新建：`snowmeet_ai_doc/sql/2026-10-xx_fnb_v4_rebuild.sql`、`snowmeet_ai_doc/docs/fnb/2026-10-xx-fnb-v4-api-contract.md`。
- 重写：
  - `SnowmeetApi/Models/Fnb/*`
  - `SnowmeetApi/Data/FnbSchemaConfiguration.cs`、`Data/ApplicationDBContext.cs`（fnb 相关的 DbSet）
  - `SnowmeetApi/Services/Fnb/*`
  - `SnowmeetApi/Controllers/Fnb/*`
- 复用的骨架：`FnbAccess.cs`、`FnbStockPostingService.cs`（过账和单号）、`FnbInventoryRules.cs`（FEFO 与到期）、`FnbMaterialController` 里的 `OAuthLogin` / `UploadPhoto` / `OcrScanName`、`FnbWeComController`。
- 不动：`MeituanCollectorController`、`Tools/meituan_collector`（以后接订单导入）。

## 验证

- **单元测试**：换算、出成率与损耗；派生批次到期；可扣判断（staged、未就绪、过期都不能扣）；批次号生成；分类 → 食材的属性回退；保质期分档；用量预警线；报表行生成。
- **LocalDB 集成测试**（`snowmeet_ai_doc/tools/windows_test/run_integration_localdb.py`）：
  - 改成执行新的重建脚本；改了模型要先删 `ef_create.sql`。
  - **验收场景直接照搬「从零上手操作说明」32 步**：帕斯雀牛肉披萨 + 热拿铁——从空库开始建分类、链路、规格、半成品、菜品，入库、作业（含 24 小时解冻）、做饼底、出餐、盘点，最后导出报表，逐步断言数量和到期。
- **双端会话**：在隔离库里分别造 `wechat_mini_openid` 和 `wecom_userid` 两种会话，各跑一遍 `GetMe` 和一次作业过账，核对 `source_client` 和权限。
- **非 fnb 的现有单元测试全部通过**；旧的 fnb 测试随旧代码一起替换。
- 全程不连生产库。

## 实现时的默认做法（不阻塞）

- 耗时作业只有店长能提前完成。
- 作业暂不提供撤销。
- 投入量允许小数（原型按整件加减）。
- 条码全局唯一。
- 主数据（分类、食材、链路、规格）在门店间共享，库存和配方按门店分开。
