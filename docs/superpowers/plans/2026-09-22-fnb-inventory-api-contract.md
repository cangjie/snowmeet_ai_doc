# 食材管理服务端 API 契约（小程序接入前审阅）

日期：2026-09-22。当前只实现服务端；小程序接入由用户安排 Claude 开发，同时独立审查服务端代码。所有接口沿用 `api/[controller]/[action]` 和 `ApiResult<object>`：`code=0` 成功，`1` 参数或业务规则错误，`2` 会话失效，`3` 门店或岗位无权，`4` 数据冲突需刷新或按原请求号重试。GET 在查询参数传 `sessionKey`、`shopId`；POST 在查询参数传 `sessionKey`，业务参数用 JSON 请求体。

| 模块 | GET | POST |
|---|---|---|
| `FnbCatalog` | `GetUnits`、`ListCategories`、`ListShelfLifeRules`、`ListMaterials`、`GetMaterial` | `SaveCategory`、`SaveShelfLifeRule`、`SaveMaterial` |
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
- 小程序客户端在分包 `snowmeet_wechat_mini/pages/fnbinv/`，后台菜单入口是「【餐饮】食材管理」。
- 验证结果与仍待服务端处理的问题见 [接口验证报告](2026-09-23-fnb-inventory-api-verification.md)。
