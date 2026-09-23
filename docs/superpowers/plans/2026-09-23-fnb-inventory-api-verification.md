# 食材管理服务端接口验证报告

日期：2026-09-23。对象：SnowmeetApi `ai@9ee8fd9` 中 codex 实现的 6 个食材控制器（`FnbCatalog`、`FnbInventory`、`FnbRecipe`、`FnbKitchen`、`FnbStocktake`、`FnbReport`），以及 Claude 本次为小程序补充的 `FnbRecipe/ListDishes`、`FnbRecipe/SaveDish`。

## 结论

- **接口本身可用。** 用真实员工会话链路，按 HTTP 全链路验证了 80 项：77 项通过，3 项失败。
- 失败的 3 项都不破坏数据：库存没有出现负数，同一请求号只生成 1 张单，失败请求用原请求号重试都能成功。
- **目前挡在上线前面的是生产数据，不是代码。**
  - 线上 29 名在职员工中，25 人的 `base_shop_id` 为空；
  - 餐饮商品的 `shop_id` 不在 `shop_list` 里。

  按现有鉴权规则，不修正数据的话，所有员工都会提示「无门店权限」。修正脚本见 [2026-09-23_fnb_restaurant_shop.sql](../../../sql/2026-09-23_fnb_restaurant_shop.sql)，需要用户审阅后执行。
- **线上是否已部署尚未核实。** 本机访问 `mini.snowmeet.top`（161.189.64.210:443）超时，关闭沙箱后同样超时；github 可以访问。

## 验证方式

| 层 | 做法 | 结果 |
|---|---|---|
| 单元测试 | `dotnet test SnowmeetApi.sln` | 344 通过，8 跳过（SQL Server 专项，按设计跳过） |
| SQL Server 集成 | `run_fnb_sqlserver_integration.py`：临时建隔离库，跑完删除 | 原 6 条 + 新增 `SaveDish*` 2 条，全部通过 |
| HTTP 全链路 | 新增 `run_fnb_http_smoke.py`（见下） | 80 项：77 通过，3 失败 |
| 生产环境 | 只执行 SELECT；API 只发无会话的 GET | 结果见下两节 |

`run_fnb_http_smoke.py` 的做法：
1. 复用集成运行器，建立隔离库。
2. 额外复制会话解析要用的 5 张表的结构：`mini_session`、`member`、`social_account_for_job`、`staff_social_account`、`member_social_account`。
3. 灌入 3 名测试员工：同店店长（200）、同店员工（100）、他店员工（300），各带真实格式的小程序会话。
4. 用临时 `config.sqlServer` 在本机启动 API，用 HTTP 驱动全部接口。
5. 结束后删除隔离库，生产库零写入。

## HTTP 全链路结果

以下各组全部通过：

- **鉴权**
  - 无会话返回 2；跨店员工返回 3；员工调用维护类接口返回 3。
  - 员工看不到成本，`ListBatches`、`GetOverview`、入库返回的 `amount` 都是 null；店长能看到。
- **档案**
  - 一级、二级分类可以增改，二级分类带默认值；12 个月的规则能正常写入，同月重复写入被拒。
  - 食材可以建档，也能按分类查询。
  - `PreviewExpiry` 的算法是「生产日 + N 天」；储存方式没有规则时返回 `rule=null`。
- **入库**
  - 散装按 kg 录入，库里存为 g；封装按件录入，按件价计算金额。
  - 同一 requestId 重放时返回 `replayed=true`，不会重复入库。
- **开封与报损**
  - 开封 1 瓶放出 1000 ml，可用量和未开封量分开统计。
  - 员工报损返回 3；店长报损的重放是幂等的。
  - 临期汇总带状态；标签数据接口可用。
- **配方与制作**
  - `ListDishes`/`SaveDish`（新）能建菜品，并自动建「标准份」；用旧 rowVersion 发布返回 4。
  - 制作按配方比例核销原料；原料不足时整单被拒，库存不变。
- **厨房单**
  - 已有配方的菜品建单直接是 verified；缺配方是 pending，店长核对时被拒。
  - 出餐预览和实际扣减的数量正确；库存不足时仍能出餐，并记录欠料，库存为 0 而不是负数。
  - 出餐后再出餐、出餐后取消都会被拦，返回 4。
- **盘点**
  - 快照、录入、rowVersion 冲突、差异预览、盘亏过账都正常。
  - 盘点期间有入库时，过账被拒（4）；盘盈缺承接批次时被拒（1），补齐后可以过账。
- **报表**
  - 员工看总览没有金额；员工调损耗台账返回 3；店长的损耗台账包含报损和盘亏。
- **旧接口保护**
  - `FnbMaterial/DisposeBatch` 处置新库存批次时返回 1，提示「库存批次不能从旧接口处置」。
  - `GenBatchNo` 仍可用，小程序新入库继续用它发号。
- **并发**
  - 8 个并行开封（只有 3 瓶）：至多成功 3 次，没有 500。
  - 并发出餐后库存不为负；失败的请求重试后都能成功。

### 失败的 3 项

| # | 现象 | 根因 | 影响 | 建议 |
|---|---|---|---|---|
| 1 | 到期日早于今天的批次可以正常入库 | `FnbReceiptRules`/`FnbReceiptService` 不校验 `ExpireDate >= 营业日`；需求 deck 第 6 页写明「按包装算已过期的批次不允许入库」 | 通过接口能录入过期批次 | 服务端补校验；小程序已在客户端拦截 |
| 2 | 10 个并行 `PostServe` 中出现 HTTP 500 | SQL Server 死锁（1205），异常是裸 `SqlException`，控制器没有捕获 | 并发高峰时店员会看到「服务繁忙」；事务已回滚，数据不受影响 | 各过账接口把 1205（含 EF transient 包装）映射为 code 4「请重试」，或在服务端自动重试一次 |
| 3 | 同一 requestId 并行 `PostReceipt` 5 次，出现 HTTP 500 | 同样是死锁。EF 把它包成 `InvalidOperationException`（transient failure），而 `PostReceipt` 没有捕获这类异常；`PostOpen`/`PostServe` 会捕获 | 同上，只生成 1 张单 | 同上 |

小程序的处理：HTTP 500、网络失败和 code 4 都当作可重试，重试时沿用原 requestId，所以不会重复过账。

## 生产只读核对（2026-09-23）

- 单位表 5 行正确：g、kg、ml、l、piece。新表（分类、规则、食材、库存、厨房单、配方）**全部为空**。
- `category.biz_type='餐饮'` 下只有 3 个有效分类（咖啡、鲜榨果汁、鸡尾酒）和 7 个饮品商品。这 7 个商品的 `shop_id` 是 45855/45862/45863，**都不在 `shop_list`**。小程序后台的「餐饮商品列表/修改」是死链，现有界面没有地方能建菜品。
- 在职员工 29 人：`base_shop_id` 为 10 的 2 人，为 4 的 2 人，**其余 25 人为空**。
- 用户已决定：
  - 新建餐饮门店「多呆一会儿吧」，界面上不显示门店名；
  - 通过修数据给后厨员工绑定门店，不改鉴权代码；
  - 菜品由店长在小程序「配方」页新建（即本次的 `SaveDish`）。

## 静态审查中的其他发现（未改服务端，客户端已绕开）

1. `CreateManualOrder` 不能指定规格。这与「一菜一份」的决定一致，界面不出现规格。
2. `PostServe` 不修改 `fnb_order.order_status`，`ListOrders` 也不带出餐标记和菜品明细。小程序因此逐单调用 `GetOrder`（N+1 次请求）。**建议** `ListOrders` 返回 served 标记和菜品摘要。
3. `ListBatches` 没有「只看在库」的过滤，而且按到期日升序分页。历史批次越积越多，库存首页就会越来越慢。**建议**增加 `inStockOnly` 参数。
4. 没有制作预览接口。小程序用配方和 `GetStock` 做展示用的预估，最终以过账结果为准。
5. `ListMovements`/`GetDocument` 只有店长能调。员工在出餐页看的是 `PreviewServe`/`PostServe` 返回的 needs；今日制作记录由 `ListBatches` 派生。
6. `CreateSnapshot` 只有店长能调，而且没有「查进行中盘点单」的接口。小程序把 documentId 按门店存在本地。
7. 制作和盘盈都强制要求照片，小程序已加上拍照步骤。
8. 分类、规则、食材的列表会返回已停用的行，小程序按 `valid` 过滤。
9. 看板所需的损耗率、周转没有数据来源。首版不做（用户已同意）。

## 本次服务端改动（工作区，未提交、未部署）

- `Services/Fnb/FnbDishService.cs`
  - `ListAsync`：本店有效、未隐藏的餐饮菜品，附带默认规格、已发布配方版本和草稿号，以及可选的餐饮分类；
  - `SaveAsync`：新建或修改菜品；按名称找或建餐饮分类；新建时自动建「标准份」。
- `Controllers/Fnb/FnbRecipeController.cs`：新增 `ListDishes`（在职员工可调）、`SaveDish`（需要 `title_level ≥ 200`）。
- `SnowmeetApi.Tests/FnbSqlServerIntegrationTests.cs`：新增 2 条用例，先失败、后通过。
- `SnowmeetApi.Tests/run_fnb_http_smoke.py`：HTTP 全链路冒烟运行器。

## 复现

```bash
cd SnowmeetApi
export ODBCSYSINI=/usr/local/Cellar/unixodbc/2.3.4/etc   # 本机 Intel Mac
dotnet test SnowmeetApi.sln
python3 SnowmeetApi.Tests/run_fnb_sqlserver_integration.py
python3 SnowmeetApi.Tests/run_fnb_http_smoke.py           # 约 12 分钟，结束自动删库
```
