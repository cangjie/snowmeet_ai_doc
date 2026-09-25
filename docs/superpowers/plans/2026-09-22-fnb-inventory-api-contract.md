# 食材管理服务端 API 契约（小程序接入前审阅）

日期：2026-09-22。当前只实现服务端；小程序接入由用户安排 Claude 开发，同时独立审查服务端代码。所有接口沿用 `api/[controller]/[action]` 和 `ApiResult<object>`：`code=0` 成功，`1` 参数或业务规则错误，`2` 会话失效，`3` 门店或岗位无权，`4` 数据冲突需刷新或按原请求号重试。GET 在查询参数传 `sessionKey`、`shopId`；POST 在查询参数传 `sessionKey`，业务参数用 JSON 请求体。

| 模块 | GET | POST |
|---|---|---|
| `FnbCatalog` | `GetUnits`、`ListCategories`、`ListShelfLifeRules`、`ListMaterials`、`GetMaterial` | `SaveCategory`、`DeleteCategory`（2026-09-23 新增）、`SaveShelfLifeRule`、`SaveMaterial` |
| `FnbInventory` | `PreviewExpiry`、`ListBatches`、`GetBatch`、`GetLabelData`、`GetStock`、`GetDocument`、`ListMovements` | `PostReceipt`、`PostOpen`、`PostWaste`、`PostPreparation` |
| `FnbRecipe` | `ListDishes`（2026-09-23 新增）、`ListDishSpecs`、`ListRecipes`、`GetRecipe` | `SaveDish`（2026-09-23 新增）、`SaveDishSpec`、`SaveRecipeDraft`、`PublishRecipe` |
| `FnbKitchen` | `ListOrders`、`GetOrder`、`PreviewServe` | `CreateManualOrder`、`CancelManualOrder`、`ReviewOrder`、`PostServe` |
| `FnbStocktake` | `GetSnapshot`、`PreviewAdjustment` | `CreateSnapshot`、`SaveCount`、`PostStocktake` |
| `FnbReport` | `GetOverview`、`GetLossLedger`、`GetExpirySummary` | 无 |

小程序和企业微信会话均由服务端重新解析为在职员工；`staff.base_shop_id` 必须等于传入的 `shopId`。在职员工可建手动厨房单、入库、开封、制作、出餐和查询；`title_level >= 200` 可维护档案与配方、核对订单、盘点过账、报损销毁及查看成本。普通员工查询不会返回库存成本。所有 BIGINT ID 在 JSON 响应中按字符串表示；请求可传十进制整数。日期字段中营业日期按上海时区，审计时间按 UTC。

手动厨房单的基本请求示例：

```json
POST /api/FnbKitchen/CreateManualOrder?sessionKey=...
{
  "shopId": 9,
  "requestId": "85908fbd-3d09-4101-83bc-34533bda54ca",
  "displayNo": "A015",
  "tableNo": "A1",
  "remark": "少盐",
  "lines": [
    { "productId": 123, "quantity": 2, "remark": "不要葱" }
  ]
}
```

`productId` 是本站有效餐饮菜品 ID，员工不填 SKU 或平台信息。同一 `requestId` 重试返回首次创建的厨房单；返回 `orderId`、`displayNo`、`reviewStatus`、`lineCount`、`replayed`。没有内部菜品规格记录时自动创建“标准份”用于关联配方；没有已发布配方时订单为 `pending`，补齐配方后由管理人员调用 `ReviewOrder`，再由员工调用 `PreviewServe` 和 `PostServe`。出餐过账使用新的 `requestId`，库存不足时记录欠料，不扣成负数；已出餐的手动单不能直接取消。

库存写入的 `PostReceipt`、`PostOpen`、`PostWaste`、`PostPreparation`、`PostServe` 和 `CreateSnapshot` 都需传稳定的 `requestId`。照片沿用 `FnbMaterial` 上传入口，OCR 和效期计算只提供候选值；入库时仍需提交确认后的到期日。库存以 g、ml、piece 为基本单位，金额使用 decimal。标签接口只返回打印数据和扫码地址，小程序端打印待下一阶段实现。

本轮不提供 `SyncInternalOrder`、平台门店／SKU 映射、平台订单采集及导入接口。已建的相关空表保留，不代表相应功能已实现或启用。服务端集成测试使用独立 SQL Server 数据库，运行器为 `SnowmeetApi/SnowmeetApi.Tests/run_fnb_sqlserver_integration.py`；线上业务库不写入测试数据。Claude 接入前请独立复核鉴权、并发重试、成本权限和旧接口绕行路径；目前自动化测试覆盖业务服务和 SQL Server 数据写入，尚无真实员工会话的端到端 HTTP 冒烟验证。

验证记录（2026-09-22）：`dotnet test SnowmeetApi.sln --no-restore --no-build --verbosity quiet` 通过 318 项，另 6 项 SQL Server 专项测试按设计跳过；单独运行上述隔离库脚本，6 项全部通过，测试库已自动删除。报损重复请求号指向不同批次的错误已用先失败、后通过的回归用例验证。上述结果不等于已部署到线上 API，也不覆盖真实员工会话和多请求并发压测。

## 2026-09-23 补充：菜品接口与小程序客户端

- `GET FnbRecipe/ListDishes?sessionKey=&shopId=`（在职员工）：返回 `{ dishes, categories }`。
  - `dishes` 是本店有效、未隐藏、属于有效餐饮分类的商品，每条含 `productId`、`name`、`salePrice`、`categoryId`、`categoryName`、`specId`、`specName`、`publishedRecipeId`、`publishedVersion`、`draftRecipeId`（配方号为字符串）。
  - `categories` 是可选的有效餐饮分类。
- `POST FnbRecipe/SaveDish?sessionKey=`（`title_level >= 200`）：请求体 `{ shopId, id, name, salePrice, categoryId?, categoryName?, valid }`。
  - `categoryId` 为空时，按 `categoryName` 找同名餐饮分类，没有就新建；
  - 新建菜品时自动建默认规格「标准份」；
  - `valid=false` 表示停用菜品。
- `POST FnbCatalog/DeleteCategory?sessionKey=`（`title_level >= 200`）：请求体 `{ shopId, id }`，返回 `{ ids }`（被删除的分类 id）。
  - 删除即把分类 `valid` 置 0，不物理删除：库存、看板仍按 id 显示已停用食材的分类名；
  - 删除一级分类时，其下有效的二级分类一并删除；
  - 受影响分类下只要还有 `valid=1` 的食材，整体拒绝（`code=1`，提示剩余食材数），需先停用这些食材；
  - `SaveCategory` 不再接受把有效分类改为 `valid=false`，停用分类只能走本接口。
- 小程序客户端在分包 `snowmeet_wechat_mini/pages/fnbinv/`，后台菜单入口是「【餐饮】食材管理」。
- 验证结果与仍待服务端处理的问题见 [接口验证报告](2026-09-23-fnb-inventory-api-verification.md)。

## 2026-09-24 变更：分类属性下沉到食材

原因：同一个二级分类下的食材包装规格各不相同（如速冻饺子有散装、有成袋），计量单位、临期提醒、开封后默认和保质期规则应属于具体食材。须先执行 [`sql/2026-09-24_fnb_item_expiry_settings.sql`](../../../sql/2026-09-24_fnb_item_expiry_settings.sql)，再部署同版本 SnowmeetApi。

- `SaveCategory` 请求体改为 `{ shopId, id, parentId, level, name, defaultStorage, sort, valid }`。
  - 二级分类只需名称和 `defaultStorage`（ambient/chilled/frozen）；一级分类不能带 `defaultStorage`。
  - `fnb_material_category` 已删除 `default_unit_code`、`warn_days`、`default_open_storage`、`default_open_days` 四列。
- `SaveMaterial` 请求体新增 `warnDays`（必填，≥0）、`defaultOpenStorage`（可空）、`defaultOpenDays`（可空，≥0），存入 `fnb_material_item` 同名列；小程序入库时带出作为默认值。
- 保质期规则改挂食材：
  - `SaveShelfLifeRule` 请求体的 `categoryId` 改为 `itemId`，须为有效食材；已有规则不能改挂到其他食材；
  - `ListShelfLifeRules` 的筛选参数 `categoryId` 改为 `itemId`，且只返回食材规则；
  - `PreviewExpiry`、`PostReceipt`（`expirySource=category`）按本食材的规则查找和校验，同分类其他食材的规则不能套用。
- 迁移时把每条启用的分类规则复制给该分类下每个食材，原分类规则置为停用，不删除（旧批次的 `shelf_life_rule_id` 仍引用）。
- 入库来源码 `expiry_source='category'` 保持不变（建表约束），含义改为「按食材保质期规则计算」，界面显示为「食材规则」。
- 开封后「保质期不变」：不改库、不改接口，约定开封天数记为 `36500`（小程序常量 `OPEN_KEEP_DAYS`）。`PostReceipt.openShelfLifeDays` 与食材 `default_open_days` 都可取此值；开封时到期取 min(原到期, 开封日 + 天数)，即封装原到期日；界面显示为「保质期不变」。开封子批次的 `opened_expire_date` 因约束仍为开封日 + 36500 天，业务以批次 `expire_date` 为准。
- 厨房单建单即扣料（2026-09-25）：
  - 新增 `POST FnbKitchen/CreateAndServe?sessionKey=`，请求体 `{ shopId, requestId, tableNo, remark, lines: [{ productId, quantity, remark }], ingredients }`。**一张厨房单只能有一道菜**（`lines` 恰好 1 行，`quantity` 为份数；将来由外部订单自动导入）。同一事务内建手动厨房单并按该菜**已发布配方 × 份数**以 FEFO 扣料，欠料不扣负；菜品没有已发布配方时整单回滚、返回 `code=1`。同一 `requestId` 重试返回首次结果。返回 `{ orderId, displayNo, documentId, replayed, needs }`。`ingredients` 可选，为单上微调的配料用量 `[{ itemId, quantity }]`（基本单位）：只能是该菜配方里的食材，`quantity=0` 表示这单不扣这一项，没列出的按配方 × 份数；同一食材重复、负数、小数超过 6 位返回「配料用量无效」，配方外的食材返回「只能微调配方里的配料用量」，全部为 0 返回「至少要扣一种配料」。不传或空数组即完全按配方。（2026-09-25 早先版本的 `ingredients` 可加配方外的食材，已撤回；现为只能微调配方内用量。）
  - 新增 `POST FnbKitchen/DeleteServedOrder?sessionKey=`，请求体 `{ shopId, orderId }`：扣料后 10 分钟内，本人或 `title_level >= 200` 可删除手动厨房单。扣掉的配料原样退回当时的批次（被扣光标为「用完」的批次恢复），同批次之后流水的 `balance_qty/balance_amount` 一并补回；扣料流水被盘点快照引用、批次已销毁或作废时拒绝。随后物理删除扣料单据、流水、厨房单行、导入记录和厨房单。
  - 新增 `POST FnbKitchen/UpdateServedOrder?sessionKey=`，请求体 `{ shopId, orderId, tableNo, remark, lines, ingredients }`（同 `CreateAndServe`，一道菜，无 `requestId`；`ingredients` 规则相同，按新菜品配方校验）：扣料 10 分钟内、本人或店长可编辑。同一事务内先按删除的规则退回原配料，再换菜品／份数、桌号、备注，按新菜品已发布配方重新扣料（没有配方则拒绝，原扣料不变）；沿用原扣料单据，可编辑／删除时限仍从第一次扣料算起。
  - `GetOrder` 新增 `servedNeeds`（已扣配料：计划、实际、欠料）与 `changeSecondsLeft`（可编辑／删除剩余秒数，否则 null）。
- 欠料处理（2026-09-25）：库存不够仍可建单（菜已做出），不扣成负数，欠的部分记为欠料；建单前提示，事后可补扣。
  - 新增 `GET FnbKitchen/GetDeductStock?sessionKey=&shopId=&itemIds=10,12`（逗号分隔，1～100 个）：返回 `[{ itemId, availableQuantity, sealedQuantity, sealedPacks, openBatchId, openBatchNo, openPackSize, packUnitName }]`。`availableQuantity` 与扣料同口径（有效、未处置、未销毁、未过期的散装／已开封／自制）；`sealed*` 为能开封的整包（条件同 `PostOpen`）；`openBatchId` 为最早到期、还够 1 件的未开封批次，没有则 null。仅作提示，以扣料结果为准。
  - 新增 `POST FnbKitchen/FillShortage?sessionKey=`，请求体 `{ shopId, orderId }`：补录入库或开封后，按现在的库存以 FEFO 把这单欠的配料再扣一次，仍不够的继续记欠料。扣的量记在原扣料单据行上（`actual_qty`／`actual_amount` 增加，计划用量不变，`remark` 追加「时间 员工 补扣 数量」），另写流水；同一行已扣过的批次不再使用（唯一约束）。不受 10 分钟限制，门店员工都可操作。10 分钟内删除或编辑厨房单时，补扣的配料一并退回。出餐后已盘点（盘点单过账时间晚于扣料、该食材已录实盘数）的食材不补扣，差异视为已由盘点调整。没有欠料、全部已盘点、库存仍为 0 时返回 `code=1`。返回 `{ orderId, needs, filledItems, settledByStocktake }`（后者为跳过的食材名）。
  - 新增 `GET FnbKitchen/ListShortageOrders?sessionKey=&shopId=&days=7`（1～31）：扣料时间在近 `days` 天内、还有未补欠料（且未被之后的盘点调整）的厨房单，最多 100 单，按扣料时间新的在前；返回厨房单数组（同 `ListOrders` 的 `rows`）。
  - `ServeNeed`（`servedNeeds`、各扣料接口的 `needs`）新增 `settledByStocktake`：欠料的食材在出餐后已盘点时为 true。
  - 小程序：「将扣减」每行显示可用量，不够的标红并写欠多少；缺的是整包没开封时提示并给「开封 1 袋」按钮（调 `PostOpen`，开完重新查库存）。有欠料时提交先弹确认框列出欠料，「仍然建单」才提交。出餐列表新增「今日／有欠料（近 7 天）」切换；有未补欠料的单显示「欠料」标记和「补扣欠料」按钮；已由盘点调整的欠料注明「已盘点」。
  - 小程序新建厨房单：菜名文本框输入、按菜品库自动提示（完整同名直接选中）；填份数；按配方 × 份数带出将扣减的用料（按食材常用单位显示），每项用量可微调，改过的注明配方原用量，填 0 表示不用这一项；再改份数时改过的保留、没改的跟着重算；只把改过的项作为 `ingredients` 提交。编辑已扣料的厨房单时，实际扣减与配方不同的项按微调带出。按钮「建单并扣料」。列表每单直接列出耗用食材与用量。旧的「待核对 / 待出餐」厨房单仍按原流程核对、预览、出餐或取消。
- `SaveDish` 的 `salePrice`、`categoryId`、`categoryName` 改为可不传（2026-09-25）：新建时售价 0、归入餐饮分类「未分类」（不存在则自动建）；修改时不传就保持原售价和分类。小程序新建菜品只填名称和用料：先 `SaveDish` 取得「标准份」规格，再 `SaveRecipeDraft`／`PublishRecipe`；「菜品资料」只改名称或停用。
- 新增 `POST FnbInventory/DeleteReceipt?sessionKey=`（2026-09-25）：请求体 `{ shopId, batchId }`，删除一次误录的入库。
  - 条件：入库单过账后 10 分钟内；批次除这笔入库外没有任何流水、开封子批次、其他单据行或盘点快照引用；本人入库或 `title_level >= 200`。不满足返回 `code=1` 并说明原因。
  - 物理删除本次入库写入的流水、单据行、单据、批次库存和旧批次行；自动建档的食材保留。
  - `GetBatch` 新增 `deleteSecondsLeft`：当前员工还能删除时为剩余秒数，否则为 null；小程序据此显示「删除这次入库」。
  - 小程序「提交入库」前弹确认框；入库页「本次已入库」10 分钟内可直接删除。
- `PostReceipt` 的批次照片改为选填：`imageIds` 可为空数组，此时 `fnb_material_batch.image_ids` 存 NULL；传了照片仍须有效、不重复且用途为「食材批次」。半成品制作 `PostPreparation` 仍要求照片。
- 分类重名（线上 2026-09-24 删掉「冻品」后再建同名返回 500）：只在未删除（`valid=1`）的同级分类中查重，不改数据库。
  - `SaveCategory` 与未删除的同级分类重名时返回 `code=1`「同级已有「名称」分类」；一级分类 `parent_id` 为 NULL，彼此视为同级。
  - 唯一索引 `IX_fnb_material_category_sibling_name (parent_id, name)` 不区分 `valid`，所以已删除的同名分类在保存前改名为「名称（已删除#id）」让出名称；库存、看板按 id 仍能找到它。
  - 连点保存等并发请求撞唯一索引时同样返回 `code=1`，不再是 500。
