# 食材管理数据库结构审阅稿 v4

日期：2026-09-22。状态：`2026-09-22_fnb_inventory_other_tables.sql` 已由用户在业务库执行；本文保留结构说明与后续范围修订。

当前建表脚本：[2026-09-22_fnb_inventory_other_tables.sql](../../../sql/2026-09-22_fnb_inventory_other_tables.sql)（`VARCHAR` 版），已经执行；它不修改 `order` 或旧食材表字段。旧[完整脚本](../../../sql/2026-09-21_fnb_inventory_schema_review.sql)是 `NVARCHAR` 方案的审阅稿，已停用，不要再执行。已有旧 `CK_order_source_pair` 需要单独删除。

依据：用户提供的 `mat.pptx` 18 页功能说明、`mat.zip` 原型、当前 SnowmeetApi 模型，以及[平台实施顺序](../../../sessions/2026-09-21_fnb-platform-sequence.md)和[外卖订单获取评估](../../../sessions/2026-09-21_fnb-takeaway-order-acquisition.md)。原型中的演示数据不作为真实保质期和成本配置。

**实施范围修订（2026-09-22）**：用户明确排除平台门店／SKU 映射。下文对应表与外卖导入流程仅保留为已经执行的历史建表说明，不作为当前开发需求或可用接口；线上表结构暂不变更。当前先实施本站餐饮订单与食材库存 API，外部订单接入待另行确定无需上述映射的业务流程及数据库约束。

## 设计范围与选择

推荐：**保留旧效期批次，增加一对一库存扩展；统一库存业务单据和批次流水。** 当前脚本新建 17 张表、2 个普通查询视图；`order` 来源字段已由独立脚本处理，其他现有表不改结构。新表字符列按用户最新选择使用 `VARCHAR`，并明确采用简体中文代码页排序规则；这能保存该代码页覆盖的常用中文，不能保证保存全部 Unicode 字符。

另外两种方式是直接在旧批次表增加全部库存列，或建立完全独立的新批次表。前者会让旧效期接口直接写入库存实体，后者需要迁移旧二维码与提醒关系。本稿的一对一扩展使旧批次保持原 ID，库存接管也可以逐批完成；代价是新业务需要在同一事务里维护批次效期和库存扩展。

本稿的设计假设，供本轮一起审阅：

- 当前可以只使用一个餐饮门店，但批次、库存单据、菜品配方和厨房订单均有 `shop_id`，防止以后不同门店混账；分类和食材品种作为共享档案。多门店业务尚未因此自动实现，应用仍须按员工权限过滤门店。
- 菜品资料复用 `product`，新建规格和配方；食材品种使用 `fnb_material_item`，不把旧 `product_stock` 的商品件数当作食材批次库存。
- 库存和配方统一使用 g、ml、piece。kg、l 在录入时换算；瓶、袋、盒是包装单位，单据保留输入单位及换算快照。重量与体积之间不能自动转换。
- 成本采用批次实际成本，食材汇总展示在库加权平均成本；半成品产出成本来自本次实际消耗成本。更改配方、价格或分类不会追改已过账数量和成本。
- 同日开封只合并同一个来源批次、同一开封日期、同一开封后储存条件下的未销毁子批次；不同原包装批次不混合，避免丢失效期与成本追溯。

## 表清单

| 表名 | 用途 |
|---|---|
| `fnb_unit` | 计量单位 |
| `fnb_material_category` | 食材两级分类 |
| `fnb_shelf_life_rule` | 分类保质期规则 |
| `fnb_material_item` | 食材品种档案 |
| `fnb_material_batch_stock` | 批次库存扩展 |
| `fnb_dish_spec` | 菜品规格 |
| `fnb_recipe` | 配方版本 |
| `fnb_recipe_line` | 配方用料 |
| `fnb_channel_shop` | 外卖门店映射 |
| `fnb_channel_dish_map` | 平台菜品规格映射 |
| `fnb_order` | 厨房订单主表 |
| `fnb_order_line` | 厨房订单明细 |
| `fnb_order_import` | 订单采集与核对记录 |
| `fnb_stock_document` | 库存业务单据 |
| `fnb_stock_document_line` | 库存单据用料／产出明细 |
| `fnb_stock_movement` | 批次库存流水 |
| `fnb_stocktake_line` | 盘点快照与实盘数 |

## 复用现有表及字段

| 现有表 | 继续使用的内容 | 本稿处理 |
|---|---|---|
| `fnb_material_batch` | 批次 ID、名称、批号、生产日期、保质期、最终效期、预警天数、照片、处置状态、员工与审计时间 | 不重建、不改字段；有对应库存扩展行才属于新库存体系 |
| `fnb_material_alert_log` | 批次提醒及发送结果 | 继续按原批次 ID 记录，不另建提醒账或修改旧字段 |
| `mini_upload` | 批次照片、OCR 截图和档案图 | 实际表名为 mini_upload；旧注释里的 upload_file 是历史名称错误 |
| `printer` | 已有打印机配置 | 复用 BLE 标签打印；本需求未要求另建打印任务／日志表 |
| `shop_list`、`staff` | 门店与员工 | 新业务外键引用；两端登录继续沿用现有员工会话体系 |
| `product` | 菜品基本资料 | 新规格通过 product_id 关联；旧按规格分别建商品的情况通过 legacy_product_id 映射 |
| `order`、`fd_order` | 现有餐饮订单与明细 | 本站餐饮单继续复用；平台单也记录到 `order`，厨房订单关联其 `id`；平台收款不写成本站支付 |
| `category`、`product_stock`、`order_payment` 等 | 现有销售分类、商品库存及支付业务 | 保持原用途，新食材业务不向这些表写入原料库存 |

现有订单表的复用边界：

| 现有数据 | 可以直接复用 | 新系统仍需记录 |
|---|---|---|
| `order` 且 `type='餐饮'` | `id`、单号 `code`、营业日 `biz_date`、门店名称 `shop`、金额和原支付／退款流程 | 门店名称需核对并映射到 `shop_list.id`；新增来源字段，厨房接单、出餐和食材扣减有独立状态 |
| `fd_order` 且 `valid=1` | `id`、所属 `order_id`、`product_id`、菜名、售价、整数份数、备注 | 规格与配方映射、套餐／加料展开、取消数量和出餐时锁定的配方版本 |

`order` 的新增字段规则：

| 字段 | SQL 定义 | 含义 |
|---|---|---|
| `order_source` | `NVARCHAR(32) COLLATE Latin1_General_100_BIN2 NULL` | 来源平台编码，例如 `meituan`、`eleme`；本站旧单和今后本站自建单均为 `NULL` |
| `source_order_no` | `NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NULL` | 平台完整订单号；本站订单为 `NULL`，OCR 不能确认完整号码时先留在采集记录待核对 |

两个字段均无非空默认值；现有记录添加列后自动保持 `(NULL, NULL)`。这两个字段属于此前独立补列步骤，仍按该脚本的 `NVARCHAR` 定义；本次 `VARCHAR` 版本只重做 17 张新表，不转换已加的 `order` 列。建表脚本不创建来源字段的 CHECK 约束；如数据库中已有 `CK_order_source_pair`，需单独删除，新的规则由使用者定义。`order.code` 仍是本系统单号，不能拿短取餐号代替 `source_order_no`。平台门店身份、平台订单去重继续使用 `fnb_channel_shop` 和厨房单上的 `(channel_shop_id, external_order_no)`；创建 `order` 与厨房单需同一事务，并校验 `order_source = fnb_channel_shop.platform`、`source_order_no = fnb_order.external_order_no`。仅这两个字段不提供足够的平台门店范围，不能据此假定平台订单号在所有门店全局唯一。

本站餐饮单通过 `fnb_order.sales_order_id` 和 `fnb_order_line.legacy_fd_order_id` 关联原销售记录；平台订单同样通过 `sales_order_id` 关联 `order`，而明细以 `fnb_order_line` 的平台快照为准。导入本站订单时必须校验 `order.type='餐饮'`、来源两列均空、门店一致、每条 `fd_order.order_id` 属于该单，并忽略 `valid=0` 的明细。平台菜品尚未映射本地 `product_id` 时不能强行创建 `fd_order`；旧订单详情接口若需显示平台明细，应接入厨房明细。`order.orderStatus` 由支付、退款、`dealed` 等字段计算，不能当作厨房出餐状态；平台收款不生成本站 `order_payment`，原支付状态和营收报表必须按来源区分。已出餐后收到改单或退款应转核对，不能自动二次扣料。

旧 `fnb_material_batch` 字段的延续口径：

| 字段 | 新系统中的含义 |
|---|---|
| `id` | 唯一批次身份；新表 batch_id 直接引用，原标签二维码保持有效 |
| `name` | 批次名称快照，创建时从食材名称复制 |
| `batch_no` | 可手工输入的包装／业务批号，允许重复；不能用于库存去重 |
| `produce_date` | 实际生产日期，可空；不能在未知时编造为今天 |
| `shelf_life_value`、`shelf_life_unit` | 入库确认的保质期数值和中文天／月；保留包装或录入事实 |
| `expire_date` | 唯一最终到期日；开封批次为原包装与开封后到期日的较早者 |
| `warn_days` | 该批次预警阈值快照，分类调整不追改历史批次 |
| `image_ids` | 现场照片对应 mini_upload.id 的逗号分隔列表；新采购入库至少一张照片由应用校验 |
| `dispose_status`、`dispose_userid`、`dispose_date` | 兼容旧用完／报废展示；新库存过账后按剩余量维护，不能直接调用旧按钮修改库存 |
| `staff_id`、`create_userid` | 保留原录入人；新库存操作人记在库存单据上 |
| `valid`、`create_date`、`update_date` | 保留实际现有定义；当前模型 valid 为 bit，历史初版 SQL 为 int，本稿不重建或擅自转换 |

## 七项功能如何落表

| 功能／操作 | 数据写入与规则 |
|---|---|
| 入库 | 创建旧批次与库存扩展，receipt 单据、增加明细与批次流水一起过账；名称与照片必填，已过期不能入库 |
| 开封 | open 单据包含原 sealed 批次减少和 opened 子批次增加两行；基本单位数量及成本转移守恒 |
| 半成品制作 | prep 单据固定配方版本，原料减少、半成品新批次增加；任一原料不足全部回滚，不先扣一部分 |
| 菜品配方 | product → dish_spec → recipe 版本 → recipe_line；按规格维护，不依赖标准份的固定倍数 |
| 出餐 | kitchen order 明细锁定 recipe_id，按食材汇总到 serve 明细，流水按 FEFO 拆分；已过账订单唯一，缺料可出餐但不扣成负数 |
| 盘点 | stocktake_line 保存系统快照与实盘；盘亏 FEFO，盘盈进入同品种同店的最晚到期可用批次，无承接批次时人工确认效期与成本后新建 |
| 到期处置／损耗／看板 | 到期状态实时计算；确认销毁才写 waste 单和减少流水；损耗与盘盈从视图读取，库存及成本按批次汇总 |

## 必须在后端实现的过账规则

SQL 中的外键、CHECK、唯一索引与 rowversion 只能保护部分数据约束。**本稿没有实现过账存储过程或触发器，执行建表也不等于完成这些业务规则。** 后续 API 必须实现：

1. **一笔业务一个数据库事务**：校验权限及状态 → 锁定相关库存 → 计算数量和成本 → 写入单据明细与流水 → 更新批次数量／成本／处置状态 → 标记 posted。失败整体回滚。
2. **并发及幂等**：同一操作重试沿用 request_id；同一订单只能有一张 posted 的 serve 单。锁定同店同食材的批次范围并重新检查可用量，更新时校验 row_version；仅建 rowversion 列不能自动阻止超扣。
3. **有效可用批次**：旧批次 valid=1、未处置，扩展未销毁，quantity>0，形态为 bulk／opened／prepared，expire_date 不早于上海当地当天。以 expire_date、received_at、batch_id 升序进行 FEFO；未开封和已过期都不能出餐或制作扣料。
4. **单据数量与成本一致**：posted 明细 actual_qty／actual_amount 等于对应流水之和；批次 quantity／stock_amount 等于全部已过账流水的带符号合计。仅 serve 的减少行允许 planned_qty 大于 actual_qty，欠料差额保留但不生成虚构负库存流水。draft／void 不得留下已生效库存流水。
5. **开封**：原批次必须为 sealed，每次只能开整数件。示例：10 瓶×1000ml 在库量 10000ml、可用量 0；开 1 瓶后原批次减 1000ml，子批次加 1000ml。复制原包装效期；旧批次 expire_date 写入 min(original_expire_date, opened_expire_date)。同日补开合并不得延长既有到期日；已用完但未销毁的子批次可再次追加并清除用完状态，已确认销毁的子批次不能恢复。
6. **配方版本与制作**：发布前校验至少一条用料、数量大于 0、目标为本店菜品或半成品；不得把产出食材本身直接当作同配方原料。配方用料关联品种，实际库存可用性在制作／出餐时判断，不能因暂时只有封装库存就删除配方。prep 配方产出量按 output_qty 比例缩放；发布后只能新建版本，历史 recipe 和 recipe_line 禁止修改。
7. **成本**：入库确认单价，不把缺失单价默认当作免费；允许明确确认的 0 成本。部分扣减按批次剩余成本比例分摊，最后一次扣完带走所有舍入尾差。开封出入成本相等，制作产出成本等于本次耗料成本；出餐缺料部分没有虚构成本。汇总加权平均成本用于展示，不覆盖历史流水。
8. **盘点快照**：只盘可用的散装、已开封和半成品。快照与过账都在同店同食材的锁范围内读取批次；保存最新流水 ID 和包含批次集合、版本、数量、效期、处置状态及营业日期的 snapshot_fingerprint。提交时重算并比较摘要，同时检查新流水；有变化要求刷新重盘，不能用过时 system_qty 覆盖实时库存。盘盈并入承接批次时按其成本计价；无承接批次则确认新批次效期、照片处理方式及单位成本，不默认为永不过期／0 成本。
9. **销毁不可回退**：确认过期销毁扣尽该批次余量、is_destroyed=1，并维护旧 dispose_status=报废。后端禁止恢复销毁批次、删除已过账单据／流水或改写其数量；错误更正流程另行设计，不通过删除历史掩盖。
10. **订单归一及去重**：同一平台门店只有一条 channel_shop 记录；平台订单唯一键为 channel_shop_id＋external_order_no，API／网页／截图最终合并为同单。创建来源 `order` 与厨房单、明细必须同一事务；两张订单表的平台编码、完整订单号与门店映射须一致。每日小票流水号不能充当完整订单号；OCR 缺可靠标识先留 import 待核对。来源更新不得使旧消息覆盖新状态；已出餐后收到改单或退款保存采集记录并交由核对，不能直接修改已核销明细或再次扣料。
11. **外卖明细完整性**：套餐容器 is_inventory_line=0；子菜品、加料按整单实际数量展开。需核销食物行缺规格、缺配方或 OCR 数量未确认时不能自动出餐；单纯缺库存与缺少配方不能混同。退款与实物回库分开判断。
12. **档案及跨表校验**：分类父级必须为一级，食材与规则必须关联二级；显示单位与基本单位维度一致；已有业务的单位、门店、批次来源和包装换算不直接修改。旧订单／fd_order 与本店及餐饮业务的关系、原批次与开封子批次的形态、配方类型、销毁原因与批次日期均需服务端校验。

## 效期、时区与未定业务口径

- 新审计时间使用 DATETIME2(3) 保存 UTC；business_date、produce_date、expire_date、opened_date 等业务日期统一按 Asia/Shanghai。不要更改旧表历史时间的解释；现有提醒、状态接口后续要统一到同一业务时区。
- 正式有效期在旧 batch.expire_date 中保存，不依赖未来分类规则反复重算。已有明确包装到期日时以其为准，calculated_expire_date 保留推算值，expiry_note 记录差异。
- 天数按 DATEADD(day, n, 生产日期)，月份按 DATEADD(month, n, 生产日期) 的日历月口径；包装到期日仍优先。月末行为需在业务验收中覆盖。
- 分类没有对应储存规则时允许选择该储存方式。原型未给出经确认的正式折算系数，本 SQL 不植入示例比例；字段支持 estimated 来源及说明，自动折算算法需另行确认，未确认前由员工填写并确认到期日。
- 损耗率的分母、周转天数的期间和成本口径尚未由用户确定。本稿保留业务日期、批次成本和完整流水，先提供基础汇总视图，不把演示看板中的 2.4%／5.8 天固化成计算规则。

## 兼容旧功能与数据接管

- 旧批次没有数量、食材主档和成本，不能自动生成真实库存。仅写入扩展表也不能替代期初流水；接管时人工确认门店、食材、包装、数量、成本及效期，创建 opening_balance 单据与对应增加流水。
- 历史记录仍用原 ID，原打印二维码、照片和提醒日志无需批量改号。新入库和新开封批次仍创建 fnb_material_batch 行，再关联库存扩展。
- **启用新库存前必须适配旧 SaveBatch／DisposeBatch／DeleteBatch 等写入口**：有库存扩展的批次不能绕过过账直接改效期、标用完／报废或软删。新旧列表、扫码详情、提醒也需按库存接管状态与门店权限路由；新表本身不会替旧接口完成这些限制。
- 旧提醒发送器可复用，但需识别库存扩展、上海日期、剩余量和销毁状态；定时任务是否已在线运行仍未核实。原配置文件接收人方式继续使用，不新增通知配置表。
- 现有 OCR 主要识别名称与日期，外卖订单 OCR 的明细解析和人工核对仍需新开发；本表结构不会使采集方案自动可用。
- 正式启用平台订单前，`Order` 模型与导入接口需增加两个可空来源字段；旧 `PlaceOrder` 产生的本站订单保持两列为空，平台订单经专门导入服务写入。现有支付状态、订单列表和营收报表需按来源调整，避免把平台代收款算作本站未付款。

## 脚本执行与验证范围

- 以仓库代码及既有 DDL 为依据，兼容项目记录的 SQL Server 2012；不使用原生 JSON、STRING_AGG、CREATE OR ALTER、DROP IF EXISTS 等较新语法。
- 在目标业务数据库执行当前 `VARCHAR` 建表脚本；它在一个事务中创建 17 张新表和 2 个视图，不修改 `order` 或旧食材表。旧的完整脚本是先前的 `NVARCHAR` 方案，不再执行。当前脚本对已存在的新对象报错，不覆盖不同结构；保留所有旧数据，只初始化 5 个基础计量单位。`CK_order_source_pair` 不由此脚本管理。
- 新表字符列均为 `VARCHAR`；普通文本列使用 `Chinese_PRC_CI_AS`，需精确比对的标识使用 `Chinese_PRC_BIN2`。`VARCHAR(n)` 的 `n` 是字节数，原 `NVARCHAR(n)` 字段按 `VARCHAR(2n)` 保留常用中文容量。简体中文代码页不能覆盖全部 Unicode，尤其是部分生僻字与 emoji。业务枚举仍受 CHECK 限制；复合索引的声明键长度按 SQL Server 2012 上限复核。
- 执行前检查旧依赖表存在、id 为 INT 且有单列唯一键。实际线上结构、权限及运行结果仍需在正式执行前校核，本轮没有连接数据库执行 DDL。
- 数量与金额使用 DECIMAL；索引列长度按 SQL Server 2012 的约束控制。流水不使用逻辑删除列，外键不做级联删除。BIGINT 主键在小程序／H5 接口中按字符串传输，避免 JavaScript 整数精度丢失。
- 语法与文档一致性检查结果见文末；检查不等于已在 SQL Server 引擎验证过建表或事务业务。

## 字段字典

以下逐表列出全部字段。SQL 定义同时列出类型、可空性、默认值／计算表达式；IDENTITY 表示数据库自增，ROWVERSION 由数据库生成。日期、金额、单位及关联含义以说明列为准。

### 01. fnb_unit — 计量单位

定义录入单位与基本单位的换算；首版仅初始化克、千克、毫升、升、个。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `code` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL` | 单位编码：g、kg、ml、l、piece；主键 |
| `name` | `VARCHAR(40) COLLATE Chinese_PRC_CI_AS NOT NULL` | 显示名称：克、千克、毫升、升、个 |
| `dimension` | `TINYINT NOT NULL` | 计量维度：1=重量，2=体积，3=个数；不同维度不能自动换算 |
| `factor_to_base` | `DECIMAL(18,6) NOT NULL` | 1 个本单位对应的基本单位数量；kg=1000g，l=1000ml |
| `valid` | `BIT NOT NULL DEFAULT (1)` | 是否启用；已被使用的换算比例不允许直接修改 |
| `sort` | `INT NOT NULL DEFAULT (0)` | 显示顺序 |

约束与索引：

- 主键：`code`。

### 02. fnb_material_category — 食材两级分类

独立于销售商品分类；二级分类承载食材储存、提醒与计量默认值。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `INT IDENTITY(1,1) NOT NULL` | 分类主键 |
| `parent_id` | `INT NULL` | 一级分类为空；二级分类指向一级分类 |
| `level` | `TINYINT NOT NULL` | 1=一级分类，2=二级分类；父级必须为一级，由应用校验 |
| `name` | `VARCHAR(100) COLLATE Chinese_PRC_CI_AS NOT NULL` | 分类名称 |
| `default_storage` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL` | 二级分类建议储存：ambient=常温，chilled=冷藏，frozen=冷冻 |
| `default_unit_code` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NULL` | 二级分类默认录入单位，关联 fnb_unit.code |
| `warn_days` | `INT NULL` | 二级分类默认提前预警天数；复制到批次后可单独调整 |
| `default_open_storage` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL` | 默认开封后储存方式；实际值在入库时确认并保存在批次扩展表 |
| `default_open_days` | `INT NULL` | 默认开封后天数；0=开封当日到期，空=没有默认值 |
| `sort` | `INT NOT NULL DEFAULT (0)` | 显示顺序 |
| `valid` | `BIT NOT NULL DEFAULT (1)` | 启用标记；停用不删除历史关系 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `updated_at` | `DATETIME2(3) NULL` | 最后修改时间，UTC |

约束与索引：

- 主键：`id`。
- 唯一索引：`parent_id, name`。
- 外键：`(parent_id) → fnb_material_category(id)`。
- 外键：`(default_unit_code) → fnb_unit(code)`。

### 03. fnb_shelf_life_rule — 分类保质期规则

一行表示一个二级分类、储存方式和生产月份，避免跨年月份区间重叠。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `INT IDENTITY(1,1) NOT NULL` | 规则主键 |
| `category_id` | `INT NOT NULL` | 二级分类 ID；应用校验 level=2 |
| `storage_type` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL` | ambient=常温，chilled=冷藏，frozen=冷冻 |
| `production_month` | `TINYINT NOT NULL` | 生产月份，1～12；不分季节时配置 12 行相同规则 |
| `shelf_life_value` | `INT NOT NULL` | 默认保质期数值，必须大于 0 |
| `shelf_life_unit` | `VARCHAR(10) COLLATE Chinese_PRC_CI_AS NOT NULL` | day=天，month=月；写入旧批次字段时映射为中文天／月 |
| `remark` | `VARCHAR(600) COLLATE Chinese_PRC_CI_AS NULL` | 规则依据及说明；本脚本不预设实际食材保质期 |
| `valid` | `BIT NOT NULL DEFAULT (1)` | 当前是否启用；批次保存自己的效期快照 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `updated_at` | `DATETIME2(3) NULL` | 修改时间，UTC |

约束与索引：

- 主键：`id`。
- 唯一索引：`category_id, storage_type, production_month`，筛选 `valid = 1`。
- 外键：`(category_id) → fnb_material_category(id)`。

### 04. fnb_material_item — 食材品种档案

一个品种对应多个库存批次；包含原料和半成品。与销售 product 分开。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `INT IDENTITY(1,1) NOT NULL` | 食材品种主键 |
| `code` | `VARCHAR(64) COLLATE Chinese_PRC_CI_AS NOT NULL` | 系统食材编码，唯一且稳定 |
| `name` | `VARCHAR(200) COLLATE Chinese_PRC_CI_AS NOT NULL` | 食材名称，例如高筋面粉、Pizza 面团 |
| `category_id` | `INT NOT NULL` | 所属二级食材分类 |
| `item_type` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL` | raw=原料，prepared=半成品 |
| `base_unit_code` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL` | 唯一库存基本单位：g、ml、piece；有库存或流水后不可修改 |
| `default_input_unit_code` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL` | 默认录入／显示单位，例如库存用 g、界面默认显示 kg |
| `image_id` | `INT NULL` | 档案参考图片，关联现有 mini_upload.id；不能替代入库现场照片 |
| `remark` | `VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL` | 食材说明 |
| `valid` | `BIT NOT NULL DEFAULT (1)` | 是否启用；历史食材只能停用 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `updated_at` | `DATETIME2(3) NULL` | 修改时间，UTC |

约束与索引：

- 主键：`id`。
- 唯一键：`code`。
- 查询索引：`category_id, valid`。
- 外键：`(category_id) → fnb_material_category(id)`。
- 外键：`(base_unit_code) → fnb_unit(code)`。
- 外键：`(default_input_unit_code) → fnb_unit(code)`。
- 外键：`(image_id) → mini_upload(id)`。

### 05. fnb_material_batch_stock — 批次库存扩展

以 batch_id 与现有 fnb_material_batch 一对一关联；原有批次 ID、效期、照片、提醒和二维码继续使用。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `batch_id` | `INT NOT NULL` | 主键，同时关联 fnb_material_batch.id；本表不另发批次 ID |
| `shop_id` | `INT NOT NULL` | 库存所属门店，关联 shop_list.id |
| `item_id` | `INT NOT NULL` | 食材品种，关联 fnb_material_item.id |
| `stock_form` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL` | bulk=散装，sealed=未开封，opened=已开封，prepared=制作半成品 |
| `storage_type` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL` | 本批次当前储存方式：ambient／chilled／frozen |
| `storage_location` | `VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL` | 储位文字，例如冷藏柜 A 层；首版不单建库位表 |
| `quantity` | `DECIMAL(18,6) NOT NULL DEFAULT (0)` | 在库数量，始终使用食材基本单位；封装也保存全部净含量 |
| `stock_amount` | `DECIMAL(19,6) NOT NULL DEFAULT (0)` | 本批次在库成本金额，人民币元；与流水同事务更新 |
| `pack_size` | `DECIMAL(18,6) NULL` | sealed 必填：每件净含量，单位为该食材基本单位；其他形态为空 |
| `pack_unit_name` | `VARCHAR(40) COLLATE Chinese_PRC_CI_AS NULL` | sealed 必填：瓶／袋／盒等包装单位，仅用于显示 |
| `sealed_pack_count` | `AS (CASE WHEN stock_form = 'sealed' THEN CONVERT(DECIMAL(18,6), quantity / NULLIF(pack_size, 0)) ELSE NULL END) PERSISTED` | 计算列：未开封件数；约束保证是整件 |
| `parent_batch_id` | `INT NULL` | opened 必填：来源未开封批次；与当前批次门店、食材一致 |
| `opened_date` | `DATE NULL` | opened 必填：上海时区的开封日期，用于同日合并与效期计算 |
| `original_expire_date` | `DATE NOT NULL` | 原包装／开封前到期日快照；手工确认的效期也写入此列 |
| `opened_expire_date` | `DATE NULL` | opened 必填：开封日期加开封后天数计算出的到期日 |
| `open_storage_type` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL` | sealed／opened 必填：确认的开封后储存方式快照 |
| `open_shelf_life_days` | `INT NULL` | sealed／opened 必填：确认的开封后天数，允许 0 表示当日到期 |
| `shelf_life_rule_id` | `INT NULL` | 计算参考的分类规则；手填或无对应规则时可为空 |
| `calculated_expire_date` | `DATE NULL` | 根据生产日期与保质期推算的参考到期日，用于显示与手填值的差异 |
| `expiry_source` | `VARCHAR(24) COLLATE Chinese_PRC_CI_AS NOT NULL` | manual=手填，package=包装／OCR确认，category=分类规则，estimated=折算参考，opened=开封计算 |
| `expiry_note` | `VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL` | 效期来源、折算依据、人工确认或冲突说明 |
| `is_destroyed` | `BIT NOT NULL DEFAULT (0)` | 是否已确认销毁；为 1 时数量与成本必须为 0，业务上不可恢复 |
| `received_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 本批次进入库存时间，UTC；开封子批次记录其生成时间 |
| `updated_at` | `DATETIME2(3) NULL` | 最近数量、成本或批次配置更新时间，UTC |
| `row_version` | `ROWVERSION NOT NULL` | 并发版本号，不是时间；更新库存时用于冲突检测 |

约束与索引：

- 主键：`batch_id`。
- 唯一键：`batch_id, shop_id, item_id`。
- 查询索引：`shop_id, item_id, stock_form`。
- 唯一索引：`parent_batch_id, opened_date, storage_type`，筛选 `stock_form = 'opened' AND is_destroyed = 0`。
- 外键：`(batch_id) → fnb_material_batch(id)`。
- 外键：`(shop_id) → shop_list(id)`。
- 外键：`(item_id) → fnb_material_item(id)`。
- 外键：`(parent_batch_id, shop_id, item_id) → fnb_material_batch_stock(batch_id, shop_id, item_id)`。
- 外键：`(shelf_life_rule_id) → fnb_shelf_life_rule(id)`。

### 06. fnb_dish_spec — 菜品规格

复用现有 product 作为菜品档案，一道菜有多个规格，每个规格独立维护配方。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `INT IDENTITY(1,1) NOT NULL` | 规格主键 |
| `shop_id` | `INT NOT NULL` | 规格所属门店；应用校验与 product.shop_id 一致 |
| `product_id` | `INT NOT NULL` | 对应现有菜品 product.id；应用校验属于餐饮业务 |
| `spec_code` | `VARCHAR(64) COLLATE Chinese_PRC_CI_AS NOT NULL` | 菜品内部规格编码，例如 standard／large |
| `name` | `VARCHAR(100) COLLATE Chinese_PRC_CI_AS NOT NULL` | 规格名称，例如标准份、大份 |
| `sale_price` | `DECIMAL(19,4) NULL` | 规格参考售价，元；空时沿用 product.sale_price，不参与支付结算 |
| `legacy_product_id` | `INT NULL` | 旧餐饮系统每个规格作为独立商品时，对应旧 product.id；用于旧 fd_order 映射 |
| `is_default` | `BIT NOT NULL DEFAULT (0)` | 是否默认规格；同一菜品最多一个启用的默认规格 |
| `valid` | `BIT NOT NULL DEFAULT (1)` | 是否启用 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `updated_at` | `DATETIME2(3) NULL` | 修改时间，UTC |

约束与索引：

- 主键：`id`。
- 唯一键：`id, shop_id`。
- 唯一键：`product_id, spec_code`。
- 唯一索引：`product_id`，筛选 `is_default = 1 AND valid = 1`。
- 唯一索引：`legacy_product_id`，筛选 `legacy_product_id IS NOT NULL`。
- 外键：`(shop_id) → shop_list(id)`。
- 外键：`(product_id) → product(id)`。
- 外键：`(legacy_product_id) → product(id)`。

### 07. fnb_recipe — 配方版本

菜品规格配方与半成品制作配方共用；已发布版本不直接修改，变更创建新版本。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 配方版本主键 |
| `shop_id` | `INT NOT NULL` | 配方所属门店 |
| `recipe_type` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL` | dish=出餐配方，prep=半成品制作配方 |
| `dish_spec_id` | `INT NULL` | dish 必填：菜品规格 ID；prep 为空 |
| `output_item_id` | `INT NULL` | prep 必填：产出半成品食材 ID；dish 为空 |
| `output_qty` | `DECIMAL(18,6) NOT NULL` | 一次配方的基准产量：dish 固定 1 份，prep 为产出食材基本单位数量 |
| `version_no` | `INT NOT NULL` | 版本号，从 1 开始，在同一规格／半成品与门店下递增 |
| `status` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('draft')` | draft=草稿，published=当前发布，retired=历史版本 |
| `remark` | `VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL` | 配方说明 |
| `created_by_staff_id` | `INT NULL` | 创建员工，关联 staff.id |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `published_at` | `DATETIME2(3) NULL` | 发布时间，UTC；发布后记录保留 |
| `row_version` | `ROWVERSION NOT NULL` | 配方编辑并发版本号 |

约束与索引：

- 主键：`id`。
- 唯一键：`id, shop_id`。
- 唯一键：`id, dish_spec_id, shop_id`。
- 唯一索引：`dish_spec_id, version_no`，筛选 `dish_spec_id IS NOT NULL`。
- 唯一索引：`shop_id, output_item_id, version_no`，筛选 `output_item_id IS NOT NULL`。
- 唯一索引：`dish_spec_id`，筛选 `dish_spec_id IS NOT NULL AND status = 'published'`。
- 唯一索引：`shop_id, output_item_id`，筛选 `output_item_id IS NOT NULL AND status = 'published'`。
- 外键：`(shop_id) → shop_list(id)`。
- 外键：`(dish_spec_id, shop_id) → fnb_dish_spec(id, shop_id)`。
- 外键：`(output_item_id) → fnb_material_item(id)`。
- 外键：`(created_by_staff_id) → staff(id)`。

### 08. fnb_recipe_line — 配方用料

配方关联食材品种，不直接绑定某个库存批次；实际扣料时再按 FEFO 选择可用批次。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 配方用料行主键 |
| `recipe_id` | `BIGINT NOT NULL` | 配方版本 ID |
| `item_id` | `INT NOT NULL` | 原料或已有半成品的食材 ID |
| `quantity` | `DECIMAL(18,6) NOT NULL` | 完成 recipe.output_qty 产量所需的基本单位用量 |
| `sort` | `INT NOT NULL DEFAULT (0)` | 用料显示顺序 |
| `remark` | `VARCHAR(600) COLLATE Chinese_PRC_CI_AS NULL` | 用料说明 |

约束与索引：

- 主键：`id`。
- 唯一键：`recipe_id, item_id`。
- 外键：`(recipe_id) → fnb_recipe(id)`。
- 外键：`(item_id) → fnb_material_item(id)`。

### 09. fnb_channel_shop — 外卖门店映射

把平台门店映射到系统门店；API、网页与截图共用该映射，不按采集方式另建门店。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `INT IDENTITY(1,1) NOT NULL` | 平台门店映射主键 |
| `shop_id` | `INT NOT NULL` | 系统 shop_list.id |
| `platform` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL` | meituan=美团，eleme=饿了么／淘宝闪购 |
| `external_shop_id` | `VARCHAR(128) COLLATE Chinese_PRC_BIN2 NOT NULL` | 平台门店 ID，按原始字符串保存，不转数字 |
| `external_shop_name` | `VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL` | 平台门店名称快照 |
| `preferred_method` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NULL` | api／web／ocr；仅方案配置，不代表接口已开通或采集已实现 |
| `valid` | `BIT NOT NULL DEFAULT (1)` | 是否启用同步 |
| `last_success_at` | `DATETIME2(3) NULL` | 最近成功同步时间，UTC；用于识别同步中断 |
| `last_error` | `VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL` | 最近同步错误摘要，不保存密钥、Cookie 或验证码 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `updated_at` | `DATETIME2(3) NULL` | 修改时间，UTC |

约束与索引：

- 主键：`id`。
- 唯一键：`id, shop_id`。
- 唯一键：`platform, external_shop_id`。
- 外键：`(shop_id) → shop_list(id)`。

### 10. fnb_channel_dish_map — 平台菜品规格映射

平台 SKU 与规范化选项组合映射到本店菜品规格；套餐、加料由订单适配器拆为可核销明细。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `INT IDENTITY(1,1) NOT NULL` | 映射主键 |
| `shop_id` | `INT NOT NULL` | 系统门店 ID，用复合外键保证两侧同店 |
| `channel_shop_id` | `INT NOT NULL` | 平台门店映射 ID |
| `external_sku_key` | `VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL` | 平台商品／SKU 稳定标识；网页或 OCR 无标识时，人工确认后使用规范化业务键 |
| `option_key` | `VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL DEFAULT ('')` | 规格及选项的规范化键；无选项用空串，避免只按菜名误配 |
| `external_name` | `VARCHAR(300) COLLATE Chinese_PRC_CI_AS NOT NULL` | 平台菜品名称，用于核对与展示 |
| `options_text` | `VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL` | 平台规格与加料描述，供人工核对 |
| `dish_spec_id` | `INT NOT NULL` | 本系统菜品规格 ID |
| `valid` | `BIT NOT NULL DEFAULT (1)` | 是否启用；停用记录不再自动匹配 |
| `confirmed_by_staff_id` | `INT NULL` | 人工确认映射的员工 ID |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `updated_at` | `DATETIME2(3) NULL` | 修改时间，UTC |

约束与索引：

- 主键：`id`。
- 唯一键：`channel_shop_id, external_sku_key, option_key`。
- 外键：`(channel_shop_id, shop_id) → fnb_channel_shop(id, shop_id)`。
- 外键：`(dish_spec_id, shop_id) → fnb_dish_spec(id, shop_id)`。
- 外键：`(confirmed_by_staff_id) → staff(id)`。

### 11. fnb_order — 厨房订单主表

统一承接本站餐饮单、导入现有 `order` 的平台单和人工单；供出餐核销使用。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 厨房订单主键 |
| `shop_id` | `INT NOT NULL` | 所属门店 |
| `source_type` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL` | internal=本站餐饮订单，external=平台订单，manual=人工厨房单 |
| `sales_order_id` | `INT NULL` | internal/external 必填：现有 `order.id`；manual 可为空 |
| `channel_shop_id` | `INT NULL` | external 必填：平台门店映射 ID |
| `external_order_no` | `VARCHAR(256) COLLATE Chinese_PRC_BIN2 NULL` | external 必填：平台完整订单号；不能用每天重复的小票流水号替代 |
| `display_no` | `VARCHAR(128) COLLATE Chinese_PRC_CI_AS NOT NULL` | 展示单号／取餐号；不作为外卖去重依据 |
| `business_date` | `DATE NOT NULL` | 上海时区营业日期，由服务端确定 |
| `ordered_at` | `DATETIME2(3) NOT NULL` | 下单时间，UTC；导入时从平台时区转换 |
| `table_no` | `VARCHAR(100) COLLATE Chinese_PRC_CI_AS NULL` | 堂食桌号或取餐位置 |
| `order_status` | `VARCHAR(24) COLLATE Chinese_PRC_CI_AS NOT NULL` | pending=待接，accepted=已接，completed=平台完成，cancelled=取消；与库存出餐过账状态分开 |
| `platform_status` | `VARCHAR(100) COLLATE Chinese_PRC_CI_AS NULL` | 平台原始状态文本／编码，便于适配及追溯 |
| `refund_status` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('none')` | none=无退款，partial=部分退款，full=全额退款；不直接代表应恢复库存 |
| `total_amount` | `DECIMAL(19,4) NULL` | 来源订单金额快照，元；仅展示，不用于本系统收款结算 |
| `refund_amount` | `DECIMAL(19,4) NULL` | 来源退款金额快照，元；部分来源缺失时为空 |
| `review_status` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('pending')` | pending=待核对，verified=已核对；完整可信 API 数据可由系统核对 |
| `remark` | `VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL` | 订单制作备注，例如不要葱 |
| `source_updated_at` | `DATETIME2(3) NULL` | 平台最后更新时间，UTC；用于防止旧消息覆盖新状态 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 首次进入本系统的时间，UTC |
| `updated_at` | `DATETIME2(3) NULL` | 本系统最后处理时间，UTC |
| `row_version` | `ROWVERSION NOT NULL` | 并发更新版本号 |

约束与索引：

- 主键：`id`。
- 唯一键：`id, shop_id`。
- 唯一索引：`channel_shop_id, external_order_no`，筛选 `external_order_no IS NOT NULL`。
- 唯一索引：`sales_order_id`，筛选 `sales_order_id IS NOT NULL`。
- 查询索引：`shop_id, business_date, order_status`。
- 外键：`(shop_id) → shop_list(id)`。
- 外键：`(sales_order_id) → order(id)`。
- 外键：`(channel_shop_id, shop_id) → fnb_channel_shop(id, shop_id)`。

### 12. fnb_order_line — 厨房订单明细

保存菜品、规格与数量快照；套餐容器行不核销，拆出的实际菜品／加料行才关联配方。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 订单明细主键 |
| `order_id` | `BIGINT NOT NULL` | 厨房订单 ID |
| `shop_id` | `INT NOT NULL` | 门店，用复合外键约束订单与规格同店 |
| `line_key` | `VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL` | 单内稳定明细键；有平台明细 ID 时使用该 ID，否则由适配器规范化生成 |
| `parent_line_id` | `BIGINT NULL` | 套餐／加料的父行 ID，必须属于同一订单 |
| `legacy_fd_order_id` | `INT NULL` | 原有餐饮明细 fd_order.id，用于内部订单关联 |
| `external_sku_key` | `VARCHAR(256) COLLATE Chinese_PRC_BIN2 NULL` | 平台菜品／SKU 标识 |
| `option_key` | `VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL DEFAULT ('')` | 规范化规格与选项键 |
| `item_name` | `VARCHAR(300) COLLATE Chinese_PRC_CI_AS NOT NULL` | 菜品名称快照 |
| `spec_name` | `VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL` | 规格名称快照 |
| `options_text` | `VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL` | 加料、套餐组成与选项说明 |
| `quantity` | `DECIMAL(18,6) NOT NULL` | 本行总数量；套餐子行必须展开为整单实际总数量，不再重复乘父行数量 |
| `cancelled_qty` | `DECIMAL(18,6) NOT NULL DEFAULT (0)` | 未制作前已取消数量；退款数量不能未经核对直接写入 |
| `is_inventory_line` | `BIT NOT NULL DEFAULT (1)` | 1=需配方核销的食物行；0=套餐容器、包装费等非核销行 |
| `dish_spec_id` | `INT NULL` | 匹配到的本店规格；未匹配时为空并阻止自动出餐核销 |
| `recipe_id` | `BIGINT NULL` | 出餐时锁定的配方版本；后续改配方不影响已扣料记录 |
| `remark` | `VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL` | 单行制作备注 |

约束与索引：

- 主键：`id`。
- 唯一键：`id, order_id`。
- 唯一键：`order_id, line_key`。
- 唯一索引：`legacy_fd_order_id`，筛选 `legacy_fd_order_id IS NOT NULL`。
- 外键：`(order_id, shop_id) → fnb_order(id, shop_id)`。
- 外键：`(parent_line_id, order_id) → fnb_order_line(id, order_id)`。
- 外键：`(legacy_fd_order_id) → fd_order(id)`。
- 外键：`(dish_spec_id, shop_id) → fnb_dish_spec(id, shop_id)`。
- 外键：`(recipe_id, dish_spec_id, shop_id) → fnb_recipe(id, dish_spec_id, shop_id)`。

### 13. fnb_order_import — 订单采集与核对记录

承接 API 通知、网页采集和截图 OCR；无法确认订单号或明细的数据先留在这里待核对。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 采集记录主键 |
| `shop_id` | `INT NOT NULL` | 目标门店 |
| `channel_shop_id` | `INT NULL` | 外卖平台门店；内部导入可为空 |
| `source_method` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL` | api、web、ocr、internal |
| `dedupe_key` | `VARCHAR(256) COLLATE Chinese_PRC_BIN2 NOT NULL` | 本次事件／采集内容的规范化去重键；同一原始通知重试保持一致 |
| `order_id` | `BIGINT NULL` | 成功匹配／创建的厨房订单；待核对或解析失败时可为空 |
| `upload_id` | `INT NULL` | OCR 截图关联 mini_upload.id；多张截图分别记录，再匹配同一订单 |
| `raw_content` | `VARCHAR(MAX) COLLATE Chinese_PRC_CI_AS NULL` | 经必要裁剪的原始订单数据／OCR 文本；不保存登录凭证和无关顾客信息 |
| `parsed_content` | `VARCHAR(MAX) COLLATE Chinese_PRC_CI_AS NULL` | 待核对的结构化解析结果，JSON 文本；SQL Server 2012 下由应用校验格式 |
| `process_status` | `VARCHAR(24) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('pending')` | pending=待处理，accepted=已导入，review=待人工核对，failed=失败，ignored=重复或旧消息 |
| `error_message` | `VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL` | 失败原因、字段缺失或冲突说明 |
| `reviewed_by_staff_id` | `INT NULL` | 人工核对员工 |
| `captured_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 采集时间，UTC |
| `processed_at` | `DATETIME2(3) NULL` | 最后处理时间，UTC |

约束与索引：

- 主键：`id`。
- 唯一键：`shop_id, channel_shop_id, source_method, dedupe_key`。
- 查询索引：`shop_id, process_status, captured_at`。
- 外键：`(shop_id) → shop_list(id)`。
- 外键：`(channel_shop_id, shop_id) → fnb_channel_shop(id, shop_id)`。
- 外键：`(order_id, shop_id) → fnb_order(id, shop_id)`。
- 外键：`(upload_id) → mini_upload(id)`。
- 外键：`(reviewed_by_staff_id) → staff(id)`。

### 14. fnb_stock_document — 库存业务单据

入库、开封、制作、出餐、报损、盘点、期初接管统一使用单据头；一项业务一次原子过账。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 库存单据主键 |
| `shop_id` | `INT NOT NULL` | 业务门店 |
| `document_no` | `VARCHAR(80) COLLATE Chinese_PRC_CI_AS NOT NULL` | 系统库存单号，同店唯一；与包装上可重复的 batch_no 不同 |
| `document_type` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NOT NULL` | receipt=入库，open=开封，prep=制作，serve=出餐，waste=报损／销毁，stocktake=盘点，opening_balance=旧批次期初接管 |
| `status` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL DEFAULT ('draft')` | draft=未过账，posted=已过账，void=未过账作废；已过账单不可直接改为作废 |
| `request_id` | `UNIQUEIDENTIFIER NOT NULL` | 调用方同一次操作固定的请求 ID；重试不得生成新值 |
| `source_client` | `VARCHAR(20) COLLATE Chinese_PRC_CI_AS NOT NULL` | mini=小程序，wecom=企业微信，system=系统处理 |
| `business_date` | `DATE NOT NULL` | 上海时区营业日期，由服务端确定 |
| `occurred_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 实际操作时间，UTC |
| `order_id` | `BIGINT NULL` | serve 必填：厨房订单 ID；同一订单仅允许一张已过账出餐单 |
| `recipe_id` | `BIGINT NULL` | prep 必填：半成品配方版本 ID |
| `reason_code` | `VARCHAR(32) COLLATE Chinese_PRC_CI_AS NULL` | waste 必填：expiry=过期销毁，near_expiry=临期报损，damage=损坏，other=其他 |
| `reference_no` | `VARCHAR(200) COLLATE Chinese_PRC_CI_AS NULL` | 入库送货单号或其他人工外部凭据 |
| `remark` | `VARCHAR(2000) COLLATE Chinese_PRC_CI_AS NULL` | 单据说明；零成本入库、盘盈成本和效期依据在此说明 |
| `created_by_staff_id` | `INT NULL` | 发起员工；系统自动任务可为空 |
| `posted_by_staff_id` | `INT NULL` | 确认过账员工；人工单过账时必填 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 创建时间，UTC |
| `posted_at` | `DATETIME2(3) NULL` | 成功过账时间，UTC；与批次更新、流水写入同事务 |
| `row_version` | `ROWVERSION NOT NULL` | 单据并发版本号 |

约束与索引：

- 主键：`id`。
- 唯一键：`id, shop_id`。
- 唯一键：`shop_id, document_no`。
- 唯一键：`shop_id, document_type, request_id`。
- 唯一索引：`order_id`，筛选 `order_id IS NOT NULL AND status = 'posted'`。
- 查询索引：`shop_id, business_date, document_type, status`。
- 外键：`(shop_id) → shop_list(id)`。
- 外键：`(order_id, shop_id) → fnb_order(id, shop_id)`。
- 外键：`(recipe_id, shop_id) → fnb_recipe(id, shop_id)`。
- 外键：`(created_by_staff_id) → staff(id)`。
- 外键：`(posted_by_staff_id) → staff(id)`。

### 15. fnb_stock_document_line — 库存单据用料／产出明细

记录每项业务计划量、实际量和成本；一行可由多个批次流水分摊。出餐按食材汇总，欠料保留在本表。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 单据明细主键 |
| `document_id` | `BIGINT NOT NULL` | 库存单据 ID |
| `shop_id` | `INT NOT NULL` | 门店，与单据和批次保持一致 |
| `line_no` | `INT NOT NULL` | 单内行号 |
| `item_id` | `INT NOT NULL` | 食材 ID |
| `item_name` | `VARCHAR(200) COLLATE Chinese_PRC_CI_AS NOT NULL` | 发生业务时的食材名称快照 |
| `direction` | `SMALLINT NOT NULL` | 1=库存增加，-1=库存减少；开封和制作同时有入、出两类行 |
| `input_qty` | `DECIMAL(18,6) NOT NULL` | 用户／计算输入数量，例如 10 瓶、0.4 千克 |
| `input_unit_name` | `VARCHAR(40) COLLATE Chinese_PRC_CI_AS NOT NULL` | 输入单位快照，例如瓶、千克、克 |
| `input_to_base` | `DECIMAL(18,6) NOT NULL` | 1 个输入单位对应多少基本单位；10瓶×1000毫升=10000毫升 |
| `planned_qty` | `AS (CONVERT(DECIMAL(18,6), input_qty * input_to_base)) PERSISTED` | 计算列：计划增加／减少数量，食材基本单位 |
| `actual_qty` | `DECIMAL(18,6) NOT NULL DEFAULT (0)` | 已实际执行数量，基本单位；为本行批次流水数量之和 |
| `shortage_qty` | `AS (CONVERT(DECIMAL(18,6), input_qty * input_to_base) - actual_qty) PERSISTED` | 计算列：计划与实际差；仅已过账出餐出库行允许大于 0 |
| `input_unit_price` | `DECIMAL(19,6) NULL` | 入库时每个输入单位的价格，元；制作／开封／出餐由实际成本计算 |
| `actual_amount` | `DECIMAL(19,6) NOT NULL DEFAULT (0)` | 已实际执行成本金额，元；为本行批次流水金额之和 |
| `specified_batch_id` | `INT NULL` | 入库、开封、销毁等指定批次；出餐／盘亏可空，由 FEFO 分配 |
| `remark` | `VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL` | 用料、欠料或价格说明 |

约束与索引：

- 主键：`id`。
- 唯一键：`document_id, line_no`。
- 唯一键：`id, shop_id, item_id, direction`。
- 唯一键：`id, document_id, shop_id, item_id`。
- 外键：`(document_id, shop_id) → fnb_stock_document(id, shop_id)`。
- 外键：`(item_id) → fnb_material_item(id)`。
- 外键：`(specified_batch_id, shop_id, item_id) → fnb_material_batch_stock(batch_id, shop_id, item_id)`。

### 16. fnb_stock_movement — 批次库存流水

每个实际批次变动一行，是数量与成本追溯依据；过账后不可修改或删除。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 流水主键；可用于盘点快照后的变更检测 |
| `document_line_id` | `BIGINT NOT NULL` | 库存单据明细 ID |
| `shop_id` | `INT NOT NULL` | 门店，与单据明细和批次的复合外键一致 |
| `item_id` | `INT NOT NULL` | 食材 ID，与单据明细和批次一致 |
| `batch_id` | `INT NOT NULL` | 实际发生变化的批次 ID |
| `direction` | `SMALLINT NOT NULL` | 1=增加，-1=减少；复合外键保证与单据明细方向一致 |
| `quantity` | `DECIMAL(18,6) NOT NULL` | 本次变动数量的绝对值，使用食材基本单位，必须大于 0 |
| `amount` | `DECIMAL(19,6) NOT NULL` | 本次变动成本绝对值，元；无成本时须显式写 0 |
| `delta_qty` | `AS (CONVERT(DECIMAL(18,6), direction * quantity)) PERSISTED` | 计算列：带正负号的数量变化 |
| `delta_amount` | `AS (CONVERT(DECIMAL(19,6), direction * amount)) PERSISTED` | 计算列：带正负号的成本变化 |
| `balance_qty` | `DECIMAL(18,6) NOT NULL` | 本次操作后的批次数量快照，不能为负 |
| `balance_amount` | `DECIMAL(19,6) NOT NULL` | 本次操作后的批次成本快照，不能为负；数量清零时成本也清零 |
| `created_at` | `DATETIME2(3) NOT NULL DEFAULT (SYSUTCDATETIME())` | 流水写入时间，UTC；业务时间看单据 occurred_at |

约束与索引：

- 主键：`id`。
- 唯一键：`document_line_id, batch_id`。
- 唯一键：`id, shop_id, item_id`。
- 查询索引：`shop_id, item_id, id`。
- 查询索引：`batch_id, id`。
- 外键：`(document_line_id, shop_id, item_id, direction) → fnb_stock_document_line(id, shop_id, item_id, direction)`。
- 外键：`(batch_id, shop_id, item_id) → fnb_material_batch_stock(batch_id, shop_id, item_id)`。

### 17. fnb_stocktake_line — 盘点快照与实盘数

保存盘点时点的系统可用量与实盘量；与盘点单据共用头表，差异通过库存明细和流水落实到批次。

| 字段 | SQL 定义 | 字段说明 |
|---|---|---|
| `id` | `BIGINT IDENTITY(1,1) NOT NULL` | 盘点明细主键 |
| `document_id` | `BIGINT NOT NULL` | 库存单据 ID；应用校验 document_type=stocktake |
| `shop_id` | `INT NOT NULL` | 盘点门店 |
| `item_id` | `INT NOT NULL` | 盘点食材，基本单位由食材档案决定 |
| `system_qty` | `DECIMAL(18,6) NOT NULL` | 快照时可用量；不含未开封及已过期、已销毁批次 |
| `counted_qty` | `DECIMAL(18,6) NULL` | 实盘量，基本单位；未填写为空，确实没有库存填 0 |
| `difference_qty` | `AS (counted_qty - system_qty) PERSISTED` | 计算列：正数盘盈、负数盘亏、0 无差异 |
| `snapshot_at` | `DATETIME2(3) NOT NULL` | 取系统库存快照时间，UTC |
| `snapshot_last_movement_id` | `BIGINT NULL` | 快照时该门店该食材的最新流水 ID；无流水时空 |
| `snapshot_fingerprint` | `BINARY(32) NOT NULL` | 服务端生成的 SHA-256 快照摘要，覆盖批次集合、版本、数量、效期、处置状态和营业日期；提交时重算比较 |
| `adjustment_line_id` | `BIGINT NULL` | 盘点差异生成的库存单据明细；无差异时空，必须同单同店同食材 |
| `counted_by_staff_id` | `INT NULL` | 实盘员工 |
| `counted_at` | `DATETIME2(3) NULL` | 实盘记录时间，UTC |
| `remark` | `VARCHAR(1000) COLLATE Chinese_PRC_CI_AS NULL` | 盘点差异说明；新建盘盈批次的效期与成本须另行确认 |
| `row_version` | `ROWVERSION NOT NULL` | 盘点编辑并发版本号；不能代替库存快照校验 |

约束与索引：

- 主键：`id`。
- 唯一键：`document_id, item_id`。
- 外键：`(document_id, shop_id) → fnb_stock_document(id, shop_id)`。
- 外键：`(item_id) → fnb_material_item(id)`。
- 外键：`(snapshot_last_movement_id, shop_id, item_id) → fnb_stock_movement(id, shop_id, item_id)`。
- 外键：`(adjustment_line_id, document_id, shop_id, item_id) → fnb_stock_document_line(id, document_id, shop_id, item_id)`。
- 外键：`(counted_by_staff_id) → staff(id)`。

## 查询视图

### vw_fnb_material_stock

每行对应一个门店、一个食材，返回食材名称、分类、基本单位、总实物数量／成本、未开封数量、可用数量、过期数量、在库加权平均单位成本，以及“有余量却被旧入口软删或标为已处置”的异常批次数。封装总量以基本单位计，件数在批次 sealed_pack_count 中查看；已过期但未销毁的库存仍计入实物和在库成本。旧表误软删不能让扩展表的剩余实物在报表里悄悄消失，异常行继续计入实物并单列冲突，但不计入可用量。无库存时平均单位成本为空。

### vw_fnb_material_loss

每行对应一条已过账报损或盘点流水。返回单据、门店、营业日期、原因、食材、批次、带正负号数量／金额、过账员工和时间；盘盈 reason_code 为 stocktake_gain，不能直接加进损耗率分子。展示类别为过期销毁、临期报损、盘亏、盘盈等；本视图没有额外存一份可能与流水不同步的损耗数据。

## 官方技术参考

- [SQL Server 筛选索引](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/create-filtered-indexes)：用于 nullable 来源单号、当前配方和已过账出餐单的唯一性。
- [SQL Server rowversion](https://learn.microsoft.com/en-us/sql/t-sql/data-types/rowversion-transact-sql)：仅为并发版本值，不是日期，也不是自动加锁机制。
- [SQL Server DATEADD](https://learn.microsoft.com/en-us/sql/t-sql/functions/dateadd-transact-sql)：日期按天／日历月计算及月末处理。

## 本轮验证记录

- 使用 Microsoft.SqlServer.TransactSql.ScriptDom 180.107.0 的 TSql110Parser（SQL Server 2012 语法）解析当前建表脚本及其动态创建的两个视图：均为 0 个语法错误。
- 检查 17 张新表、235 个字段与字典一致；53 条外键的本地目标列和字段类型匹配。当前脚本不修改旧 `order`，也不创建来源字段 CHECK；实际旧表结构仍需在执行时校核。
- 新表 70 个字符列使用 `VARCHAR` 与简体中文代码页排序规则；保留旧表字符列现状。检查新表的 60 个主键、唯一键及查询索引，最大声明键长度为 516 字节，低于 SQL Server 2012 的 900 字节上限。
- 本地文档链接、字段说明覆盖及文件空白检查通过。
- **没有在 SQL Server 引擎或业务数据库执行 DDL，也未进行过账业务测试。** 语法解析不会验证数据库权限、实际旧表结构、运行时计算及库存事务行为。
