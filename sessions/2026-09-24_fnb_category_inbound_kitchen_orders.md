# 2026-09-24 食材管理第二轮打磨：分类属性下沉、入库简化、厨房单按菜品配方扣料与欠料补扣

按主题整理，跨 09-24 ~ 09-25 两天。接 09-23 交付的食材管理小程序（`snowmeet_wechat_mini/pages/fnbinv/`）和 SnowmeetApi 食材服务端，用户在开发者工具里逐项试用、逐项提改。改动落在两个业务仓（用户已分批提交），接口口径同步到 [`docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md`](../docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md)。

## 1. 后台菜单清理

- 用户原话：「管理员界面，餐饮的类目管理、商品列表、商品信息修改、订单列表，这几项和与之相关的文件，都删除掉」。
- 这 4 个页面（`pages/admin/fd/*`）其实 2026-06-15 已删，菜单项和 `admin.js` 里的跳转成了死入口。本次删掉 4 个 `mp-cell` 和对应 `nav` 分支（mini `49622320`）。

## 2. 分类只管名称和储存方式，其余属性下沉到食材

### 2.1 需求

- 用户原话：「添加二级分类过于繁琐，起个名字，选择储存方式即可。一个二级分类下可以有各种的包装规格，比如速冻饺子，那肯定有散装的，有成袋的，这个属性不应该做到分类上，而是做到具体的食材上。」

### 2.2 实现

- 迁移脚本 [`sql/2026-09-24_fnb_item_expiry_settings.sql`](../sql/2026-09-24_fnb_item_expiry_settings.sql)：
    - `fnb_material_category` 删 `default_unit_code / warn_days / default_open_storage / default_open_days`；
    - `fnb_material_item` 加 `warn_days / default_open_storage / default_open_days`；
    - 保质期规则改挂食材：每条启用的分类规则复制给该分类下每个食材，原规则停用不删（旧批次仍引用）。
- `SaveCategory` 只收名称 + `defaultStorage`；`SaveMaterial` 加临期、开封默认；`SaveShelfLifeRule` / `ListShelfLifeRules` 的 `categoryId` 改 `itemId`。
- 入库 `expiry_source='category'` 保留（建表约束），含义改为「按食材规则」。
- **⚠️ 必须先跑迁移脚本再部署 API**（EF 已按新列读写）。生产是否已执行本次未核实。

### 2.3 删除分类后同名重建报错（用户纠正过一次）

- 线上删掉「冻品」再建同名 → 500（唯一索引 `(parent_id, name)` 不区分 `valid`）。
- 第一版我让用户跑 SQL 改成带 `valid` 的过滤索引。用户原话：「我要的不是这个，而是只在未删除的分类中检查是否冲突！这个事情你不理解吗？」
- 终版纯代码：`FnbCategoryService.NameTakenAsync` 只在 `valid=1` 同级查重；`FreeNameAsync` 保存前把已删除的同名分类改名为「名称（已删除#id）」让出名称；并发撞索引（2601/2627）也返回 `code=1`。
- 已写入 memory「业务规则能在代码里实现就别依赖用户手动跑生产 SQL」，并同步进 CLAUDE.md「已知遗留」。

## 3. 入库简化

- **到期日自动算**：填生产日期 + 保质期自动算到期日；手改到期日后生产日期、保质期变灰不用填。
- **含量单位可选**：整包食材的含量单位可选 ml / L / 件等（`units.contentUnitOptions`）。
- **去掉月份快捷 chip**：用户问「这块有什么用？没有用就去掉」。
- **照片改选填**：`PostReceipt.imageIds` 可为空，`image_ids` 存 NULL；半成品制作仍要求照片。
- **新食材直接录**：名称完整同名直接选中；库里没有的食材提交时自动建档，不再先选名称再填规格。
- **开封后「保质期不变」**：不改库不改接口，约定开封天数记 `36500`（小程序常量 `OPEN_KEEP_DAYS`），开封到期取 min(原到期, 开封日+天数)。
- **入库查不到库存**：用户问「为什么现在入库的食材，在库存中查不到？」——原流程是先加进本地待提交队列，没点提交就没过账。按用户要求改成点「入库」直接过账，不再二次确认队列。
- **防误触 + 撤销**：用户随后又要「点击入库按钮后弹确认对话框；添加后 10 分钟内、没有其他操作（开封、使用）时可以删除」。
    - 新增 `FnbInventory/DeleteReceipt`：过账 10 分钟内、批次除这笔入库外没有任何流水/开封子批次/其他单据行/盘点引用、本人或店长，物理删除本次入库；
    - `GetBatch` 返回 `deleteSecondsLeft`。

## 4. 菜品：只填名称和用料

- 用户原话：「添加菜品，直接输入名称和编辑配料表即可，无需价格和分类设置。」
- `SaveDish` 的 `salePrice / categoryId / categoryName` 改可不传：新建售价 0、归「未分类」（没有就自动建）；修改不传保持原值。
- 修了一个顺序问题：先解析默认分类再加商品，避免建分类失败时留下半截商品。

## 5. 厨房单：一单一道菜，按配方扣料（用户纠正过一次）

### 5.1 第一版方向错了

- 先按「添加厨房单时可以直接编辑配料表，完成后自动扣减；10 分钟内可删除、配料回滚；也可编辑」做了多菜品 + 单上手填配料的版本。
- 用户原话：「这一点，你完全搞错了。添加厨房单，一单只应该有一个菜品。因为未来这些菜品肯定不是手动添加的，而是从某个地方自动导入的。而具体的菜品是根据相应的配方来减扣食材用的。……菜品的名称通过文本框输入，但是可以根据输入的文字自动提示选择库中的菜品名称。」

### 5.2 终版

- `FnbKitchen/CreateAndServe`：`lines` 恰好 1 行（份数），同一事务建单 + 按已发布配方 × 份数 FEFO 扣料，没有已发布配方整单回滚；`requestId` 幂等。
- `UpdateServedOrder`：10 分钟内本人或店长可编辑，先退回原配料再按新菜品重扣，沿用原单据、时限从第一次扣料算。
- `DeleteServedOrder`：10 分钟内删除，配料原样退回原批次，「用完」批次恢复，同批次之后流水的结存补回；被盘点引用、批次销毁/作废时拒绝。
- 小程序：菜名输入 + 菜品库自动提示（完整同名直接选中）；列表每单直接列出耗用食材和用量（`GetOrder.servedNeeds`）。

### 5.3 配料用量可微调

- 用户原话：「添加菜品的时候，配料表应该可以微调用量。」
- `CreateAndServe` / `UpdateServedOrder` 新增可选 `ingredients [{itemId, quantity}]`：只能是配方里的食材，0 表示不扣这一项，没传的按配方（`FnbServeService.Adjust`）。
- 小程序「将扣减」每行是输入框，按常用单位显示；改过的注明「配方 xxx」；改份数时改过的保留；编辑时按当时实际扣减带出。

## 6. 库存不够时怎么处理

### 6.1 讨论

- 用户问：「添加厨房单，发现食材不够，应该如何处理？」
- 结论：不拦建单（菜已做出，将来还是自动导入），也不允许负库存；欠的记欠料。
- 常见原因：有整包没点开封（系统只扣散装/已开封/自制）> 入库漏录 > 批次已过期 > 配方偏大。
- 用户选了「建单前提示」+「补扣欠料」两项，盘点兜底暂不做。

### 6.2 建单前提示

- `GET FnbKitchen/GetDeductStock?itemIds=`：可用量与扣料同口径（抽出 `FnbInventoryRules.IsDeductible` 共用）；能开封的整包件数；最早到期、够 1 件的未开封批次（开封条件抽成 `FnbStockPostingService.CanOpen`，`PostOpen` 也改用它）。
- 小程序每行显示「可用 xx」，不够标红「欠 xx」；有整包没开封时提示并给「开封 1 袋」按钮；提交时弹「库存不够」确认框。查库存失败静默不显示，不影响建单。

### 6.3 补扣欠料

- `POST FnbKitchen/FillShortage`：按现在库存 FEFO 补扣，记在原单据行（`actual_qty` 增加，`shortage_qty` 计算列自动变小），另写流水，`remark` 追加「时间 员工 补扣 数量」。
    - 不受 10 分钟限制；10 分钟内删单/编辑会连补扣一起退回（流水挂在同一单据行上）。
    - `UQ(document_line_id, batch_id)` 约束：同一行已扣过的批次跳过（极少见：别的单删掉后原批次回血）。
    - 出餐后已盘点（盘点单过账晚于扣料、该食材已录实盘数）的食材不补扣，避免和盘点调整重复扣。
- `GET FnbKitchen/ListShortageOrders?days=7`：近 N 天还有未补欠料的单。
- `ServeNeed.settledByStocktake`：已由盘点调整的欠料标「已盘点」。
- 小程序出餐列表加「今日 / 有欠料（近 7 天）」切换、「欠料」标记、「补扣欠料」按钮。

## 7. 验证

- 小程序 149/149（新增库存提示、补扣、筛选的单元与页面冒烟）。
- 服务端单元 346 通过；本机 LocalDB 集成 22/22（新增 3 条：库存提示口径、分次补扣 + 删单连补扣一起退回、盘点后不能补扣）。
- 集成运行器会先执行 09-22 建表 + 09-24 迁移，再核对 EF 模型与迁移后表结构一致。
- 本机 Windows 测试工具已存进 [`tools/windows_test/`](../tools/windows_test/)：
    - `run_tests.js`：开发者工具自带的 node v16 没有 `node:test`，用它代跑 `tests/*.test.js`；
    - `run_integration_localdb.py`：LocalDB 建隔离库跑 `FnbSqlServerIntegrationTests`，跑完删库；缺 `ef_create.sql` 时用 `efschema` 生成。
- 开发者工具编译、真机走查：本次未做。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Services/Fnb/FnbServeService.cs` | 一单一菜建单扣料、编辑/删除回滚、用量微调、库存提示、补扣欠料、欠料单查询 |
| `SnowmeetApi/Controllers/Fnb/FnbKitchenController.cs` | CreateAndServe / UpdateServedOrder / DeleteServedOrder / GetDeductStock / FillShortage / ListShortageOrders |
| `SnowmeetApi/Services/Fnb/FnbInventoryRules.cs` | 抽出 `IsDeductible` |
| `SnowmeetApi/Services/Fnb/FnbStockPostingService.cs` | 抽出 `CanOpen` |
| `SnowmeetApi/Services/Fnb/FnbReceiptService.cs` | 照片选填、DeleteReceipt、按食材规则 |
| `SnowmeetApi/Services/Fnb/FnbCategoryService.cs` | 只在有效同级查重、已删除同名改名让位 |
| `SnowmeetApi/Services/Fnb/FnbDishService.cs` | 售价/分类可不传 |
| `snowmeet_wechat_mini/pages/fnbinv/serve/*` | 一单一菜、自动提示、用量微调、库存提示与开封、补扣与筛选 |
| `snowmeet_wechat_mini/pages/fnbinv/common/kitchen.js` | portionNeeds / deductLines / adjustments / withStock / shortageText / openShortage |
| `snowmeet_wechat_mini/pages/fnbinv/inbound/*`、`cats/*`、`recipe/*`、`batch/*` | 入库简化、分类简化、菜品只填名称用料、删除入库 |
| `snowmeet_ai_doc/sql/2026-09-24_fnb_item_expiry_settings.sql` | 分类属性下沉到食材的迁移 |
| `snowmeet_ai_doc/tools/windows_test/` | 本机测试工具 |

## 学到的小知识

1. **业务规则能在代码里实现就别让用户跑生产 SQL**：分类查重只看有效分类，用代码改名让位即可，不必改索引。
2. **先确认业务主线再动手**：厨房单将来是外部自动导入的，「一单一菜 + 按配方扣」是由这个前提决定的；按字面理解「编辑配料表」做成手填配料就整个方向错了。
3. **计算列能省掉同步逻辑**：`shortage_qty = planned − actual` 是持久化计算列，补扣只加 `actual_qty`，欠料自动变小。
4. **补扣要避开盘点**：盘点已按实物调过库存，再补扣会重复扣；以「盘点单过账时间晚于扣料」判断。
5. **提示类接口失败要静默**：库存提示只是参考，查不到就不显示，不能挡住建单。新版小程序先上时服务端没有这个接口，也不会出错。
6. **部署顺序**：迁移脚本 → SnowmeetApi → 小程序。小程序先上会调到不存在的补扣/欠料接口；微调用量会被旧服务端静默忽略。
