# 七色米只读 API

2026-10-20。代码位于 `SnowmeetApi`，基础路径 `/api/Qisemi`。开发验收后已获用户确认并生产部署，库存筛选增强现为 `ai@99a6e306`；见 [筛选说明](inventory-filters-2026-10-20.md) 和 [本轮部署记录](deployment-filters-2026-10-20.md)。接口不执行建表、导入、零售映射或扣库存。

## 会话与响应

所有接口（包括文件）均接受可选请求头：

```http
SessionKey: <未来的会话值>
SessionType: <未来的会话类型>
```

本期缺省、任意值都可访问，不查询或验证身份。`QisemiSessionFilter` 将两个头写入请求级 `QisemiSessionContext`；以后从这个统一入口接入鉴权。Swagger 在每个七色米操作上列出这两个头。不把会话值返回给前端或写入日志。

成功 JSON：

```json
{
  "code": 0,
  "message": "",
  "data": {
    "snapshot": {
      "id": "1",
      "batchId": "1",
      "currentFullBatchId": "1",
      "currentInventoryBatchId": "1",
      "businessTimezone": "Asia/Shanghai",
      "quantityKind": "book_stock",
      "batch": {}
    },
    "result": {
      "items": [],
      "total": "0",
      "page": 1,
      "pageSize": 30
    }
  }
}
```

示例 ID 均为合成值。列表 `total`、所有 SQL `bigint` 身份及计数以字符串返回，防止 JavaScript 丢失精度；数量与金额是十进制 JSON 数字。字段从 SQL 下划线命名转为 camelCase。`*Json` 字段返回 JSON 对象/数组，不返回第二次编码的字符串。业务时间带 `+08:00`，采集、发布、来源创建修改和本地审计时间带 `Z`；采集起止时间与业务日期不能混用。

`Sources` 例外：`data.items` 为数据源列表，无批次包装。单项详情、模块列表、尺码详情等 `result` 结构见各接口描述。文件成功时直接返回文件流，不套 JSON。JSON 保留业务自定义字段与数组，但递归省略凭据、私有存储键、本地路径；数据库原文仍完整保留。

错误：400 参数错误、404 不存在/已删除、409 没有可用发布批次或批次变化、503 暂时读取失败。业务错误包含 `code/message`；ASP.NET 参数类型/范围校验错误使用框架标准 400 ValidationProblemDetails。409 的 `code=4`，503 的 `code=5`，其余业务参数错误 `code=1`。数据库异常详情不会返回客户端。所有响应设置 `Cache-Control: no-store`；文件附加 `X-Content-Type-Options: nosniff`。

## 公共查询参数

| 参数 | 含义 |
| --- | --- |
| `sourceId` | 数据源本地 ID；只有一个有效源时可省略，多源时必须传 |
| `batchId` | 首次响应拿到的当前批次 ID；翻页、详情、文件继续携带；指针变化返回 409，要求前端重新开始查询 |
| `page` / `pageSize` | 从 1 开始；默认 1 / 30；pageSize 最大 100 |
| `keyword` | 最长 160 字，多关键词按空白分开，最多 12 个不同词，全部词命中；SQL 通配符按字面匹配 |
| `dateFrom` / `dateTo` | `yyyy-MM-dd`，业务日期首尾均包含；仅业务单据、历史版本、流水和销售报表应用日期筛选 |

库存、款式、仓库、顶级商品分类及库存明细使用 `currentInventoryBatchId`；其余使用 `currentFullBatchId`。两个批次可以不同，前端不能把库存批次号传给全业务接口。结构化查询只展示当前已发布指针对应的数据；`Batches` 可列出以往发布元数据，但本轮不提供任意旧快照的主档重建与切换。

只读 SQL 服务复用既有 `ApplicationDBContext` 的连接配置，新建短连接；不额外维护生产连接串。每个请求用只读语句和 RepeatableRead 事务固定本次读取过程，查询检查有效源、已发布且核对通过的批次、模块、原始记录和所属对象。来源停用、来源删除、红冲与本地逻辑删除分别处理：`valid=0` 隐藏，来源标记保留展示。

## 库存主入口

| GET 路径 | 筛选 / 返回 |
| --- | --- |
| `Sources` | 有效数据源、两个当前指针、当前会话策略 |
| `Inventory` | `keyword, warehouseId, resultWarehouseId, categoryId, topCategoryId, resultCategoryId, sortBy, sortDirection, skuId, styleId, inStockOnly, negativeOnly, sourceEnabled, sourceDeleted`；按款式分页，返回款式字段、`sizeCount,quantityMain,hasNegative,unknownCount,categoryPaths`；分页对象另含 `categoryFacets,unfilteredTotal,warehouseFacets,warehouseUnfilteredTotal` |
| `Styles/{id}` | `warehouseId,warehouseKeyword,includeZero`；返回 `style,sizes,warehouses,warehouseScopeComplete`，含尺码的逐仓数量矩阵 |
| `Warehouses` | `keyword`；仓库列表、来源状态、`coverageComplete` |
| `TopCategories` | 商品分类中 `parentId=null` 的有效顶层节点，返回 `id,name,parentId,sort,sourceEnabled,sourceDeleted`，沿用库存发布批次 |
| `Skus/{id}` | SKU 字段、属性、单位/价格、款式归组、完整档案原始记录 |
| `StockTotals` | `keyword,skuId,negativeOnly`；原始口径的 SKU 总库存分页 |
| `WarehouseStocks` | `keyword,skuId,warehouseId,negativeOnly`；实际保存的各仓明细分页，不在这个原表入口补零行 |

`Inventory` 关键词支持部分词、不区分大小写，多词可以分别命中款式文本、同一个 SKU 文本及该 SKU 所属的各级分类名称。例如 `双板鞋 fisch 24-25 110 26.5`；所有词必须由同一个 SKU 及其自身分类路径共同满足，不能把不同尺码的命中拼在一起。按 `26.5` 命中一个款式后，`Styles/{id}` 仍返回同款所有尺码，不把搜索词继续用作尺码过滤。不同硬度、颜色、雪季等归组直接使用已迁入的 `qsm_style_sku`，查询阶段不再猜测合并。

`categoryPaths` 是该同款全部有效 SKU 对应的去重分类路径，不因关键词命中某个尺码而隐藏其他路径。每项包含字符串 `categoryId`、由顶层到叶子排序的 `levels:[{id,name}]` 以及布尔 `complete`。例如 `【硬件】双板鞋 → Fischer → Fischer 24-25`。缺失或删除的上级节点不补造；路径只保留可见的连续节点并返回 `complete=false`。没有可见分类资料时返回空数组。此字段为 2026-10-20 后续开发增强，当前本机验证完成、尚未部署。

`inStockOnly=true` 在计数和分页前筛选款式：全部仓库时至少一个有效尺码的来源总库存大于零；指定仓库时至少一个尺码在该仓的账面数量大于零。零、负数和未知不单独构成有库存。筛选针对整个同款，不要求关键词命中的尺码本身有库存；详情仍保留全部尺码。API 参数缺省为 `false` 以保留原调用行为，H5 默认明确发送 `true`。

`topCategoryId` 必须为 `TopCategories` 返回的有效顶层商品分类，匹配该节点与所有有效后代的 SKU 分类；分类层级中已逻辑删除或来源链不可见的节点不参与遍历。不存在、删除或传入非顶层节点返回 404。原 `categoryId` 仍保持按款式分类精确匹配，未改变旧参数语义。顶级分类、库存、仓库与关键词共同作用后再分页。

`resultCategoryId` 为结果内的二次分类筛选，正数必须是有效顶级分类，`0` 表示没有完整可见分类路径的“未分类”，缺省不过滤。其作用对象是已经满足关键词及其他主筛选的同一个 SKU。`categoryFacets:[{id,name,count}]` 始终统计主筛选和当前二次仓库条件下、二次分类及分页之前的全部结果，每个款式在同一顶级分类只计一次；同款跨分类可分别计入，因此分类计数之和可能大于去重总款数。`unfilteredTotal` 为二次分类前去重款数，`total` 是全部二次筛选后款数，两个值和 `count` 均返回字符串。空页也返回分类统计，切换分类不会让其他分类消失。

`sortBy=name|topCategory`、`sortDirection=asc|desc`，缺省为名称正序。名称和分类名称使用数据库排序规则，排序先于分页；分类相同时继续按名称及 ID 同方向排序，以固定分页顺序。一个同款跨多个匹配分类时取名称按序最前的一项作为分类排序键，没有完整分类的款式在正序和倒序都排最后。字段和方向仅接受以上白名单值，非法值返回 400。此排序及结果分类条为后续本机增强，尚未部署。

`resultWarehouseId` 为搜索结果中的有货仓二次筛选，必须是当前来源可见的正数仓库 ID。仓内至少一个有效尺码的已取得账面数量大于零才命中，按整个同款判断，不要求关键词命中尺码本身有货；零、负数和未知不构成有货。若设置主 `warehouseId`，二次仓库只在该主仓范围内，传入其他仓返回 400；不存在或逻辑删除的仓返回 404。列表 `quantityMain` 改为二次所选仓的同款合计，可能因其他尺码负库存而为零，未知数量仍按原规则处理；未选择二次仓时保留原总表/主仓口径。H5 展开时将 `resultWarehouseId ?? warehouseId` 传给 `Styles` 的既有 `warehouseId` 参数，流水跳转也沿用此仓。

两组结果统计互相联动、各自排除本组选择：`categoryFacets` 与 `unfilteredTotal` 在当前二次仓库下、二次分类前统计；`warehouseFacets:[{id,name,count}]` 与 `warehouseUnfilteredTotal` 在当前二次分类下、二次仓库前统计。两者都覆盖分页前的全部结果。仓库项只返回至少一款有正库存的可见仓库，每个同款在同仓只计一次，可分别计入多个仓。`warehouseUnfilteredTotal` 是该分类下全部去重款数，取消正库存条件时也可能包含没有任何已知正库存仓的款式。点击仓库后仍保留其他有货仓数量，空页也返回统计。此结果仓库增强尚未部署。

默认 `Inventory.quantityMain` 使用来源总表；指定仓库后为所选仓的账面合计。任一参与尺码数量未知时合计为 null。`negativeOnly` 表示包含负库存尺码的款式，而不是仅筛选合计为负的款式。

款式详情中的每个尺码包含 `warehouses[]`：

```json
{
  "warehouseId": "1",
  "warehouseName": "示例仓库",
  "quantityMain": -1,
  "quantityState": "reported",
  "hasNegative": true,
  "sourceAvailableQuantity": null,
  "orderQuantity": null,
  "onInQuantity": null,
  "onOutQuantity": null
}
```

`quantityState` 为 `reported`（来源明确记录）、`inferred_zero`（该仓完整采集且缺失此组合）、`unknown`（未完整取得、原行/来源链删除等）。未知数值为 null，不伪造金额、占用或可售库存。默认 `includeZero=false` 仅隐藏数量等于零的仓，未知与负数保留，零库存尺码也始终保留。`selectedQuantity` 对所选/搜索到的仓计算，仓未知或一个仓都没匹配时为 null。`sourceTotalQuantity` 是独立来源总表值，便于库存对照。

## 单据与完整字段

| GET 路径 | 筛选 / 返回 |
| --- | --- |
| `Documents` | `module,documentType,keyword,dateFrom,dateTo,state,writeBack,warehouseId`；当前版本单据分页；`state` 对应来源 `sourceBillState` 原码，`writeBack` 单独筛选红冲标志 |
| `Documents/{id}` | 可加 `versionId` 查看该单据指定版本；返回单据版本完整字段、原始主记录、可用分区名称 |
| `Documents/{id}/Sections/{section}` | `versionId,page,pageSize`；分区为 `lines,settlements,writeoffs,relations,movements,versions,files,raw` |
| `Versions` | 历史版本分页；`module=sales_history_details` / `purchases_history_details` 或 `documentType`，可加 `documentId,keyword,dateFrom,dateTo` |
| `Versions/{id}` | 指定版本详情，包含版本种类；不计入当前单据列表 |
| `StockMovements` | `skuId,warehouseId,documentId,versionId,keyword,dateFrom,dateTo`；来源流水行分页，包括原有重复行及其 `duplicateOrdinal` |
| `SalesLines` | `skuId,documentId,keyword,dateFrom,dateTo`；销售/退货报表原口径，返回匹配的 `documentType` |
| `Records` | `module,carrier,keyword`；任一已导入模块的完整原始 JSON 分页 |
| `Modules/{module}/Records` | `Records?module=...` 的普通模块快捷路由 |
| `Records/{id}` | 原始 JSON、所属模块、行号、哈希、重复次序与结构化单据链接 |

单据 `module` 使用已确认界面的模块 key；采购/销售/预订单/草稿/退货/调拨/盘点/借入借出/入出库/收付款等类型分开。借入与借出模块同时列出对应的归还/收回身份。`lines` 包含书面/实盘/差异/归还数量等结构化字段；`settlements` 与 `writeoffs` 保留结构化来源覆盖的部分，完整父子数组可从 `raw` 查看。

详情的 `detailCoverageJson` 是实际采集/解析覆盖说明，空数组并不表示已经完整采集。`raw` 分区包含主记录、补充详情及已关联明细的来源行；原表无法唯一对应单据时保留在原表及核对问题中，不强行关联。不跨历史版本、当前列表、报表、原表重复合计。

带斜杠的元数据/native 模块使用 `Records?module=native%2Fsales_with_details.1`，避免把斜杠塞进路径段。原始模块中没有验证过专有映射的空模块保留空状态，不猜字段。

## 档案、文件与核对

| GET 路径 | 筛选 / 返回 |
| --- | --- |
| `Modules` | 原型 50 个入口及其来源、原表、采集覆盖状态；空、未采集有区别 |
| `Archives/{module}` | `keyword,sourceEnabled,sourceDeleted`；统一档案分页 |
| `Archives/{module}/{id}` | 档案完整结构化字段及来源原始 JSON |
| `Files` | `keyword,fileType,styleId,skuId,documentId,versionId,state`；文件引用分页，优先主图；同款缩略图可从任意尺码取得。返回受控 `contentPath`，不返回存储键或来源签名 URL |
| `FileReferences/{id}/Content` | 验证引用、源、批次、模块、原始记录、父对象和文件后，从 S3 流式读取；图片可内联，其他类型作为附件 |
| `ExportSheets` | `keyword`；20 份工作表的表头、行数、原文件 ID 与关联状态 |
| `ExportSheets/{id}/Rows` | `keyword,page,pageSize`；工作表完整原始行分页 |
| `Snapshot` | 当前全业务批次详情、核对 JSON、全部逐模块覆盖与采集时间 |
| `Batches` | 已发布且核对通过的批次元数据分页 |
| `DataIssues` | `keyword,state`；来源核对问题分页 |

档案模块：`products_all,accessories,product_classes_tree,units,warehouses,branches,warehouse_positions,clients,client_classes,suppliers,supplier_classes,accounts_all,projects,employees_all,roles`。分类返回 `parentId`，保留层级；商品详情也可使用 `Skus/{id}` 取得属性和单位。

文件 `fileType` 可选 `image,attachment,export` 或扩展名（如 `pdf,xlsx`）。生产现有文件名可能仅为 `main`，图片的内联类型使用已保存的 MIME 类型判断。文件共享内容按 SHA 去重，但访问绑定引用身份；任一父对象/引用/文件本地删除后不再提供文件。S3 继续保持私有，不公开对象或生成长期链接；本期接口身份校验按用户要求留空。

`stock,stock_by_warehouse,stock_movements,sales_line_items` 分别对应四个库存/报表专用接口；两个历史入口对应 `Versions`；`media,exports,snapshot` 分别对应文件、原表、快照接口；`balances` 等无样本模块使用 `Records`。这样原型 50 入口和全部 61 API 模块、20 原表工作表及元数据均有读取入口。

## 本地验证方式

```powershell
dotnet test SnowmeetApi.Tests/SnowmeetApi.Tests.csproj --filter FullyQualifiedName~Qisemi
```

规则/HTTP 测试不连接生产。SQL Server 测试在 Windows LocalDB 自动新建并清理 `snowmeet_qsm_api_test_*` 临时库，先确认 `SERVERPROPERTY('IsLocalDB')=1`；使用相邻文档仓中的已批准 DDL（可用 `QISEMI_TEST_SCHEMA` 指定本地文件）。不读取生产连接文件，不运行生产 Startup，不启动采集看门狗。非 Windows 跳过 LocalDB 测试。

原始记录删除遮罩按请求先物化，再执行分页，避免每行重复关联多张来源表。库存先用平面连接识别匹配款式、固定页码后再算当前页尺码数量；稀疏原始键匹配使用哈希连接控制批量导入后的坏执行计划。

验证记录与剩余边界见对应会话归档。用户随后已授权实现 [H5](h5-implementation.md)，页面使用这些真实接口。本期没有部署或执行定期新快照同步；上线和真实企业微信手机验收须后续确认。

组合筛选先读取满足来源链有效性的 SKU/款式/分类身份；关键词的 SQL 字面匹配在小型商品目录查询中单独计算，再与分类路径匹配结果合并。服务层与正库存款式集合及有效分类后代集合取交集、去重，最后由 SQL 计数分页。分类仍作用在关键词匹配的同一 SKU，正库存仍针对整个同款，不因执行计划优化改变筛选语义。长搜索文本不进入来源链哈希连接，避免完整快照上过大的内存授予等待。
