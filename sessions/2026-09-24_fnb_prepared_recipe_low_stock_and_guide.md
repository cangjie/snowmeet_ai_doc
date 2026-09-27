# 2026-09-25 ~ 09-27 食材管理第三轮打磨：半成品分类与配方、制作页开封、用量预警、操作指南 PPT

接 [09-24 第二轮打磨](2026-09-24_fnb_category_inbound_kitchen_orders.md)。用户继续在开发者工具里边试边提改，改动落在两个业务仓，均已由用户提交并推送：SnowmeetApi `ai@9db5d2a9`、小程序 `ai@528d8366`。接口口径同步到 [`docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md`](../docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md) 的「2026-09-25 变更：半成品分类」「2026-09-26 变更：用量预警」两节。

## 1. 半成品分类（09-25）

- 起因：用户找不到新增分类时的「半成品」选项。当时半成品类型只在「＋ 食材」表单里选，分类上从来没有这个选项。我先改了文案，指出正确路径。
- 用户原话：「半成品可能是用多种食材制作的，但是半成品本身也是一种食材。所以半成品应该可以是一个独立的分类。我添加分类的时候应该可以选则是否是半成品。」
- 实现：
  - 迁移脚本 [`sql/2026-09-25_fnb_category_prepared.sql`](../sql/2026-09-25_fnb_category_prepared.sql)：`fnb_material_category` 加 `is_prepared BIT NOT NULL DEFAULT 0`。
  - 已有二级分类里的食材如果全是半成品，迁移时把该分类标为半成品分类。
  - 分类算不算半成品：自身或一级父分类的 `is_prepared` 为 1 就算。
  - 食材的 `item_type` 由所在分类决定，`SaveMaterial.itemType` 不再采用。已有食材保留原类型。
  - 分类下已有另一类型的有效食材时，不能改分类类型，返回 `code=1` 并提示另建分类。这条规则由我定，已告知用户。
  - 一级分类改为用弹层新增和编辑，也能选类型。
- 验证：小程序 151/151，服务端单元 346，LocalDB 集成 23/23。

## 2. 半成品配方

- **新建入口**：用户建了分类「Pizza面团」却加不了配方。原因是配方的产出必须是一个具体的半成品食材，而「半成品配方」页之前没有新建入口。现在加了「＋ 新建半成品」，一步完成：填名称，选半成品分类和计量单位，添加用料，保存并发布。
- **去掉「每次产出」**：用户原话「为什么还需要设置每次产出多少个？这个应该不需要吧」。现在配方按每 1 个单位的半成品记：
  - 服务端存的 `output_qty` = 1 个单位换算成基本单位的量。
  - 计量单位选千克或升时，按每 1 千克、1 升记。
  - 编辑旧配方时，按旧的 `output_qty` 折算回每 1 单位的用量。
- **用量单位自动换算**：食材计量单位是千克或升时，用料行的用量单位默认用克或毫升（`recipe.lineUnitCode`）。

## 3. 制作页（prep）

- **产出数量**：按半成品自己的单位填（按个的只能填整数），原料需要量 = 每 1 单位用量 × 产出数量。
- **开封按钮**：用户要求「像添加厨房单一样」提供开封。
  - 制作页改用 `FnbKitchen/GetDeductStock` 取可扣量。缺料而另有未开封整包时，那一行显示「另有 N 袋未开封」和「开封 1 袋」。
  - 开封逻辑从出餐页抽成 [`pages/fnbinv/common/open-pack.js`](../../snowmeet_wechat_mini/pages/fnbinv/common/open-pack.js)，制作页和出餐页共用。用户问过为什么多了这个文件，答：出餐页原有的开封代码搬进来共用，不是新写一套。
- **照片选填**：用户原话「拍照非必选」。`PostPreparation` 的 `imageIds` 可为空，此时 `image_ids` 存 NULL。
  - 用户随后在线上遇到「半成品批次参数无效」，原因是服务端还没部署新版本，仍在强制要求照片。

## 4. 用量预警（09-26）

- 用户原话：「所有库存的食材，需要可以添加和修改用量预警，默认剩下封装和已开封总量的10%的时候，就要预警。预警信息在库存列表里，和临期与过期批次并排显示。」
- 用户后来纠正了口径：「应该是可用的量 占最后一个批次的10%，作为默认的报警用量。」
- 规则：
  - 可用量 = 未开封 + 已开封 + 散装 + 自制，不含过期、报损、已处理的量。
  - 默认预警线 = 最近一次入库（半成品取最近一次制作）数量 × 10%。
  - 可以按比例改，也可以直接填数量；填了数量就不按比例。
- 数据库：迁移脚本 [`sql/2026-09-26_fnb_item_low_stock.sql`](../sql/2026-09-26_fnb_item_low_stock.sql) 给 `fnb_material_item` 加 `low_stock_ratio DECIMAL(5,4)` 和 `low_stock_qty DECIMAL(18,6)`。两列都空时按默认 10% 算；CHECK 约束不许两列同时有值。
- 服务端：
  - `FnbLowStockService` 和 `FnbLowStockRules`。
  - `GET FnbInventory/ListLowStock`（员工可用）。
  - `POST FnbCatalog/SaveLowStockAlert`（仅店长）。
- 小程序：
  - 库存页顶部「临期与过期批次」「用量预警」两张卡并排。
  - 列表里库存低的食材带「库存低」标签。
  - 库存 tab 角标 = 临期过期批次数 + 库存低食材数。
  - 新页面 `pages/fnbinv/lowstock/`。
- **设置入口放库存页**：用户原话「如果食材很多，我如何通过这个列表找到我需要设置预警的食材呢？应该是在库存的页面，针对于各个食材设置」。
  - 库存页搜到食材、点开后，第一行显示预警线和规则，店长点「设置」修改。
  - 弹层抽成组件 `pages/fnbinv/components/low-stock-editor/`，库存页和 lowstock 页共用。
  - 已用完、在库存页看不到的食材，仍在 lowstock 页设置。
- 验证：
  - 小程序 167/167，服务端单元 350。
  - LocalDB 集成 24 条全过，新增用量预警一条（含 CHECK 约束）；制作测试补了无照片的情况。
  - EF 模型与迁移后的表结构一致。

## 5. 操作指南 PPT（09-27）

- 用户要求：「做个PPT，来讲述这几天开发的食材管理系统如何在界面上操作。」
- 产出：Slides 类型的 Artifact「食材管理系统操作指南」，共 20 页：https://claude.ai/artifact/AkjZNKHQ3xkP2v7Ei4evCf 。仅用户本人可见，可下载成 PPTX 或 PDF。
- 章节：
  - 开始（入口、8 个页签、一天的流程、按批次记账）
  - 基础资料
  - 入库与库存（含开封、临期过期、用量预警）
  - 配方与制作
  - 出餐（含欠料）
  - 盘点与看板
  - 附录（权限表、常见问题）
- 截图：只用了用户发来的「用量预警」页截图。库存页（第 8 页）右侧是示意图。
- **待办**：用户说服务端已部署，准备截图。
  - 我建了文件夹 `D:\source\snowmeet\ai\screenshots\`，请用户按页码命名（如 `08.png`），给了第 5～18 页的截图清单。
  - 截图放好后：用 Artifact 批量上传为资源（`asset: true` + `file_paths`），再替换对应页的示意或文字，发布到同一个 URL。
  - Slides 文件工作目录在会话 scratchpad，下次会话不在了。要先用 Artifact `read` 取回 `project/deck.json` 和 `project/slides/*.html`，再改。

## 6. 未结的问题

- **榛果糖浆「可用 0 ml」**（09-25）：给过三种可能原因：开封后已过期、批次被旧页面标成用完或报废、有同名的两个食材。用户没有再截批次图，也没同意只读查生产库，所以没有定位。制作页和出餐页现在都会显示「另有 N 袋未开封 / 开封 1 袋」，如果是整包没开封，能直接看出来。
- **线上状态**：
  - 用户 09-27 说服务端已部署（我没有核实）。
  - 09-24、09-25、09-26 三份 SQL 应在部署前按顺序执行，本次没有核实生产库。
  - 小程序代码已推送，是否上传体验版或发布未知。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`sql/2026-09-25_fnb_category_prepared.sql`](../sql/2026-09-25_fnb_category_prepared.sql) | 分类加 `is_prepared`，迁移全是半成品的二级分类 |
| [`sql/2026-09-26_fnb_item_low_stock.sql`](../sql/2026-09-26_fnb_item_low_stock.sql) | 食材加 `low_stock_ratio` / `low_stock_qty` 和 CHECK 约束 |
| `SnowmeetApi/Services/Fnb/FnbLowStockService.cs` | 新增：`FnbLowStockRules`（阈值、校验）+ `ListAsync` |
| `SnowmeetApi/Services/Fnb/FnbPreparationService.cs` | 制作照片改选填 |
| `SnowmeetApi/Controllers/Fnb/FnbInventoryController.cs` | `ListLowStock` |
| `SnowmeetApi/Controllers/Fnb/FnbCatalogController.cs` | `SaveLowStockAlert`；分类 `isPrepared` |
| `SnowmeetApi/Models/Fnb/FnbCatalogEntities.cs`、`Data/FnbSchemaConfiguration.cs` | 新列与精度 |
| `SnowmeetApi.Tests/FnbLowStockRulesTests.cs`、`FnbSqlServerIntegrationTests.cs` | 规则单测 4 条；集成新增用量预警、无照片制作 |
| `snowmeet_wechat_mini/pages/fnbinv/common/recipe.js` | `lineUnitCode` / `perUnitCode` / `prepNeeds` |
| `snowmeet_wechat_mini/pages/fnbinv/common/open-pack.js` | 新增：开封 1 袋，出餐和制作共用 |
| `snowmeet_wechat_mini/pages/fnbinv/common/lowstock.js` | 新增：预警文案、编辑状态、保存体、tab 角标 |
| `snowmeet_wechat_mini/pages/fnbinv/components/low-stock-editor/` | 新增：设置弹层组件 |
| `snowmeet_wechat_mini/pages/fnbinv/lowstock/` | 新增页面（app.json 已注册） |
| `snowmeet_wechat_mini/pages/fnbinv/{stock,prep,recipe,serve,category,expiry}/` | 预警卡与逐食材设置；产出数量与开封；新建半成品；分类类型 |
| `snowmeet_wechat_mini/tests/fnbinv_lowstock.test.js`、`fnbinv_pages.test.js` | 新增和更新的页面、规则测试 |
| [`tools/windows_test/run_integration_localdb.py`](../tools/windows_test/run_integration_localdb.py) | 加跑 09-25、09-26 迁移 |
| [`docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md`](../docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md) | 新增 09-25、09-26 两节，制作照片选填 |

## 学到的小知识

1. **小程序组件要用页面样式**：组件 `options: { addGlobalClass: true }` 后，页面 `fnb.wxss` 里的类能作用到组件内部；CSS 变量定义在 `page` 上，组件里直接可用。
2. **WXML 的 `wx:for` 不能写数组或对象字面量**：分组列表要在 JS 里先拼好 `groups` 再绑定。
3. **改了 EF 模型再跑 LocalDB 集成**：先删缓存的 `ef_create.sql`，否则按旧模型建表，表结构核对会失败。
4. **「可用量」和「库存量」不是一回事**：未开封整包算库存，但只有开封后才能被出餐和制作扣到；用量预警的可用量则把未开封也算上，因为它回答的是「还要不要补货」。
5. **Slides Artifact 的源文件放在会话 scratchpad**：下次会话要改，先用 Artifact `read` 取回 `project/` 下的文件。
