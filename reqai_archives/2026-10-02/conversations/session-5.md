# 等待崔洋确认今日输出

> 归档日期：2026-10-02（北京时间） · 会话 #5 · 模式：chat
> 所属用户：苍杰(私)

## 用户 · 2026-10-02T15:09:22+08:00

食材管理，需要增加对于餐饮工具的管理，餐具的管理（一次性餐具可否等同于食材？）然后，需要增加存储区域的管理。每天开门，员工需要按照存储区域进行相应的检查，（可否借鉴目前的盘点功能）。请结合已经实现的系统，整理一份FSD



## 助手 · 2026-10-02T15:09:31+08:00

# 餐饮工具、餐具、存储区域与开门检查 FSD（初稿）

## 1. 结论

建议将新增能力拆成三个业务模块：

1. **餐饮物资档案与库存**
   - 食材：继续使用现有 `fnb_material_item` 与食材库存体系。
   - 一次性餐具：不等同于食材，但可复用库存过账、批次、成本和预警能力。
   - 餐饮工具：作为可重复使用的资产／工具管理，不直接按食材批次扣减。
2. **存储区域管理**
   - 给食材、一次性餐具、工具和检查项绑定 `storage_area`。
   - 支持门店内的区域树、区域状态和区域负责人。
3. **每日开门检查**
   - 按存储区域生成检查任务。
   - 借鉴盘点的“快照—填写—提交—并发校验”模式，但不能直接复用盘点单，因为开门检查不应修改库存。

---

## 2. 与现有系统的衔接

### 2.1 已有能力

当前食材库存已经具备以下可复用基础：

- 食材品种档案为 `fnb_material_item`，批次库存扩展为 `fnb_material_batch_stock`，库存流水为 `fnb_stock_movement`。[[C13]]
- 入库、开封、半成品制作、出餐、盘点和销毁均通过库存业务单据及流水处理。[[C6]]
- 所有库存写入应在一个事务中完成，包括锁定库存、写入单据和流水、更新批次数量及状态。[[C5]]
- 库存数量统一使用 `g`、`ml`、`piece`，包装单位保留输入单位和换算快照。[[C1]]
- 现有盘点只盘可用的散装、已开封和半成品，使用系统快照和实盘数，并在提交时检查快照是否过期。[[C5]]
- 小程序已有 `pages/fnbinv/stock`、`pages/fnbinv/count` 等库存和盘点页面，并存在 `stocktake.js`、`stock-view.js` 等公共模块。[[C19]]
- 服务端已经存在盘点相关能力，但目前 `CreateSnapshot` 仅店长可调用，并且没有查询进行中盘点单的接口。[[C12]]
- 现有库存低量预警已经支持按食材设置比例或固定数量，默认规则为最近一次入库数量的 10%。[[C4]]

第二轮餐饮库存实现中，相关服务文件包括：

- `SnowmeetApi/Services/Fnb/FnbServeService.cs`
- `SnowmeetApi/Services/Fnb/FnbInventoryRules.cs`
- `SnowmeetApi/Services/Fnb/FnbStockPostingService.cs`
- `SnowmeetApi/Services/Fnb/FnbReceiptService.cs`
- `SnowmeetApi/Controllers/Fnb/FnbKitchenController.cs`[[C2]]

这些服务可以作为库存过账和餐饮业务权限的复用入口，但**目前资料没有确认它们已经支持“餐具”“工具”或“存储区域”字段**，不能直接假设现有接口无需改造。

### 2.2 不建议直接复用的部分

不建议把一次性餐具直接写进 `fnb_material_item`，也不建议把每日开门检查直接伪装成盘点：

| 对象 | 是否进入食材档案 | 是否产生批次库存 | 是否允许库存扣减 | 是否适合盘点模型 |
|---|---:|---:|---:|---:|
| 食材 | 是 | 是 | 是 | 是 |
| 一次性餐具 | 否，建议新建物资档案 | 是 | 是 | 部分适合 |
| 可重复使用餐具 | 否 | 可选 | 通常不按消耗扣减 | 可盘数量，但不是库存出入库 |
| 餐饮工具 | 否 | 否，建议资产档案 | 否 | 不适合按库存流水处理 |
| 开门检查项 | 否 | 否 | 否 | 只借鉴快照机制 |

一次性餐具与食材都属于“会消耗的物资”，但业务属性不同：

- 食材有保质期、开封、FEFO、制作配方和成本追溯。
- 一次性餐具通常只需要规格、包装换算、库存数量、低库存预警和领用／损耗记录。
- 餐饮工具关注的是是否存在、是否可用、所在区域、责任人、维修或报废状态，而不是批次成本。

因此，建议采用：

> **统一物资库存底座，食材、一次性餐具作为不同物资类型；餐饮工具单独建立工具资产模型。**

这是设计建议，当前文档没有记载已经作出该决策。

---

# 3. 业务范围

## 3.1 本期目标

本期实现：

1. 餐饮物资分类扩展。
2. 一次性餐具档案与库存管理。
3. 餐饮工具档案与状态管理。
4. 存储区域档案及物资位置绑定。
5. 每日开门检查模板。
6. 按存储区域生成开门检查任务。
7. 员工填写、提交、补充说明和上传照片。
8. 店长查看当天完成情况、异常项和历史记录。
9. 对库存类检查项提供“库存异常”入口，但不在开门检查提交时直接调整库存。

## 3.2 本期不做

以下内容不应纳入本期：

- 一次性餐具进入菜品配方。
- 餐具参与厨房单扣料。
- 工具自动折旧、财务资产核算。
- 工具维修工单和供应商采购流程。
- 自动判断设备是否真正正常运行。
- 开门检查直接产生盘盈、盘亏或库存流水。
- 复杂的跨门店区域权限。
- 自动定时提醒任务。现有食材提醒设计曾明确本期不做定时任务，先支持手动触发；本期是否增加定时任务需要另行确认。[[C7]]

---

# 4. 核心概念

## 4.1 物资类型

新增统一物资类型 `material_type`：

```text
food              食材
disposable        一次性餐具
reusable_tableware 可重复使用餐具
```

建议不要将餐饮工具放入该类型，而是单独使用 `tool` 资产类型。

### 食材

沿用现有规则：

- 批次管理。
- 效期管理。
- 开封和销毁。
- FEFO 扣料。
- 成本追溯。
- 菜品配方关联。

这些规则已经是现有食材库存的既有设计。[[C1]][[C5]]

### 一次性餐具

例如：

- 一次性筷子。
- 打包盒。
- 打包袋。
- 吸管。
- 纸巾。
- 一次性手套。
- 外卖餐具包。

业务特征：

- 有库存数量。
- 可按包装单位入库，例如箱、包、袋。
- 应转换为 `piece` 作为基本数量。
- 可以设置低库存预警。
- 可以记录领用、报损、盘点调整。
- 一般不需要效期、开封后保质期或 FEFO。

这里的“通常不需要效期”是业务建议，个别物资仍应允许配置效期。

### 可重复使用餐具

例如：

- 碗。
- 盘。
- 杯。
- 勺。
- 夹子。

建议按两类场景处理：

1. **普通消耗／周转数量**
   - 只管理总数量和可用数量。
   - 适合纳入物资库存。
2. **高价值或需要逐件追踪的餐具**
   - 建议单独建立资产编号。
   - 本期可先不做逐件二维码。

### 餐饮工具

例如：

- 菜刀。
- 砧板。
- 电子秤。
- 量杯。
- 漏勺。
- 打蛋器。
- 保鲜盒。
- 温度计。
- 开瓶器。

工具应管理：

- 工具名称。
- 工具分类。
- 编号或标签。
- 所在存储区域。
- 当前状态。
- 责任岗位或责任人。
- 是否需要每日检查。
- 最近检查时间。
- 报废或停用原因。

工具不应通过 `fnb_stock_movement` 模拟每日“扣一件、补一件”，否则会制造大量没有业务意义的库存流水。这是设计建议。

---

# 5. 数据模型设计

## 5.1 现有表的使用边界

现有食材表继续承担食材业务：

- `fnb_material_item`
- `fnb_material_batch_stock`
- `fnb_stock_document`
- `fnb_stock_document_line`
- `fnb_stock_movement`
- `fnb_stocktake_line`[[C13]]

不建议直接修改 `fnb_material_item` 来承载工具。当前资料只确认该表是食材品种档案，未记载其已经支持工具或餐具类型。[[C13]]

## 5.2 建议新增表

### `fnb_storage_area`

存储区域主表。

| 字段 | 说明 |
|---|---|
| `id` | 区域 ID |
| `shop_id` | 门店 |
| `parent_id` | 父区域，可为空 |
| `name` | 区域名称 |
| `area_type` | `kitchen`、`warehouse`、`front`、`cold_storage`、`other` |
| `sort` | 排序 |
| `valid` | 是否启用 |
| `remark` | 备注 |
| `created_by` | 创建人 |
| `created_at` | 创建时间 |
| `updated_at` | 修改时间 |
| `row_version` | 并发控制 |

建议区域支持两级或多级树，例如：

```text
后厨
  冷藏柜
  冷冻柜
  调料架
前台
  打包区
  餐具柜
仓库
  一次性用品区
  工具区
```

但首版建议限制为最多两级，降低员工选择成本。

### `fnb_supply_item`

统一餐饮非食材物资档案。

| 字段 | 说明 |
|---|---|
| `id` | 物资 ID |
| `shop_id` | 门店；如果物资需要共享，可另行设计共享档案 |
| `supply_type` | `disposable`、`reusable_tableware` |
| `name` | 名称 |
| `specification` | 规格 |
| `base_unit_code` | 基本单位，通常为 `piece` |
| `display_unit_code` | 显示单位 |
| `pack_size` | 包装换算数量 |
| `default_storage_area_id` | 默认存储区域 |
| `low_stock_ratio` | 低库存比例 |
| `low_stock_qty` | 固定预警数量 |
| `valid` | 是否启用 |
| `remark` | 备注 |

`low_stock_ratio` 与 `low_stock_qty` 不应同时有值，这与现有食材预警约束一致。[[C4]]

### `fnb_supply_batch`

一次性餐具和可重复使用餐具的入库批次。

| 字段 | 说明 |
|---|---|
| `id` | 批次 ID |
| `supply_item_id` | 物资 |
| `shop_id` | 门店 |
| `batch_no` | 批次号 |
| `received_at` | 入库时间 |
| `quantity` | 基本单位数量 |
| `remaining_quantity` | 剩余数量 |
| `unit_cost` | 单位成本，可为空或明确为 0 |
| `storage_area_id` | 当前存储区域 |
| `status` | `available`、`depleted`、`disposed` |
| `remark` | 备注 |

若选择复用现有库存过账底座，成本规则仍需遵循现有“明确确认 0 成本，不把缺失单价当作免费”的原则。[[C5]]

### `fnb_tool`

餐饮工具档案。

| 字段 | 说明 |
|---|---|
| `id` | 工具 ID |
| `shop_id` | 门店 |
| `category_id` | 工具分类 |
| `name` | 工具名称 |
| `specification` | 规格型号 |
| `asset_no` | 工具编号 |
| `quantity` | 数量 |
| `storage_area_id` | 所在区域 |
| `status` | `normal`、`missing`、`damaged`、`repairing`、`disposed` |
| `check_required` | 是否需要开门检查 |
| `check_frequency` | `daily` 或其他 |
| `responsible_staff_id` | 责任人，可为空 |
| `image_ids` | 图片 |
| `valid` | 是否启用 |
| `remark` | 备注 |

如果工具需要逐件管理，应增加 `fnb_tool_instance`，但建议后置。本期先按“工具品种＋数量”管理。

### `fnb_opening_check_template`

开门检查模板。

| 字段 | 说明 |
|---|---|
| `id` | 模板 ID |
| `shop_id` | 门店 |
| `name` | 模板名称 |
| `business_date` | 不存具体日期 |
| `valid` | 是否启用 |
| `version` | 模板版本 |
| `created_by` | 创建人 |
| `created_at` | 创建时间 |

### `fnb_opening_check_item`

检查项定义。

| 字段 | 说明 |
|---|---|
| `id` | 检查项 ID |
| `template_id` | 模板 |
| `storage_area_id` | 存储区域 |
| `item_type` | `supply`、`tool`、`environment`、`safety` |
| `supply_item_id` | 关联一次性餐具，可为空 |
| `tool_id` | 关联工具，可为空 |
| `name` | 检查项名称 |
| `check_method` | `yes_no`、`quantity`、`text`、`photo` |
| `expected_value` | 期望值 |
| `required` | 是否必须填写 |
| `sort` | 排序 |
| `valid` | 是否启用 |

### `fnb_opening_check`

每日开门检查单。

| 字段 | 说明 |
|---|---|
| `id` | 检查单 ID |
| `shop_id` | 门店 |
| `business_date` | 营业日期 |
| `template_id` | 使用的模板 |
| `status` | `draft`、`in_progress`、`submitted`、`confirmed` |
| `started_by` | 开始员工 |
| `submitted_by` | 提交员工 |
| `submitted_at` | 提交时间 |
| `confirmed_by` | 店长确认人 |
| `confirmed_at` | 确认时间 |
| `snapshot_fingerprint` | 提交时模板／对象摘要 |
| `remark` | 整单备注 |

### `fnb_opening_check_line`

每日检查结果。

| 字段 | 说明 |
|---|---|
| `id` | 明细 ID |
| `check_id` | 检查单 |
| `storage_area_id` | 区域 |
| `check_item_id` | 检查项 |
| `expected_value` | 检查时的期望值 |
| `actual_value` | 实际填写值 |
| `result` | `pass`、`abnormal`、`na` |
| `abnormal_reason` | 异常原因 |
| `photo_ids` | 异常照片 |
| `handled` | 是否已处理 |
| `handling_remark` | 处理说明 |
| `row_version` | 并发控制 |

---

# 6. 一次性餐具是否等同于食材

## 6.1 结论

**业务上不等同，技术上可以复用部分库存能力。**

建议：

```text
食材：fnb_material_item + 食材批次规则 + 配方／效期／FEFO
一次性餐具：fnb_supply_item + 物资库存批次 + 低库存预警
工具：fnb_tool + 工具状态
```

## 6.2 可以复用的部分

一次性餐具可以复用：

- 入库。
- 库存数量。
- 包装单位换算。
- 领用。
- 报损。
- 盘点。
- 低库存预警。
- 存储区域。
- 成本统计。

现有系统已经将库存数量、成本、流水和盘点作为独立能力设计，这些部分适合抽象为公共库存底座。[[C5]][[C6]]

## 6.3 不应复用的部分

一次性餐具不应默认接入：

- 菜品配方。
- `CreateAndServe` 厨房单扣料。
- 食材开封。
- 食材保质期规则。
- 半成品制作。
- 食材 FEFO。
- 食材临期／过期处置。

当前厨房单是按已发布菜品配方扣料，且配方用料关联食材品种。[[C6]][[C18]]如果将一次性餐具加入配方，会把“出餐用料”和“厨房加工食材”混在一起，除非后续明确要求按订单自动扣除餐具，否则本期不接入。

---

# 7. 存储区域管理

## 7.1 区域规则

1. 区域必须属于一个 `shop_id`。
2. 员工只能查看和操作有权限门店的区域。
3. 区域停用不删除历史检查记录。
4. 有绑定物资或检查项时，不允许物理删除。
5. 停用区域后：
   - 历史入库、库存、检查记录继续显示原区域名称。
   - 新建入库和新建检查项不能再选择该区域。
6. 区域名称只在同一门店、同一父级下查重。
7. 存储区域调整只影响当前位置，不改变历史库存流水的原始记录。

现有分类已经采用“只对有效同级查重、已删除名称让位”的处理方式，可作为区域名称处理的参考。[[C2]][[C16]][[C18]]

## 7.2 物资位置

同一物资可能分布在多个区域，因此不建议只在物资主档保存一个 `storage_area_id`。

建议：

```text
fnb_supply_item
  └── fnb_supply_location
        ├── supply_item_id
        ├── storage_area_id
        ├── quantity
        └── is_default
```

对于食材，位置应绑定到批次或库存扩展，而不是只绑定食材品种，否则同一种食材放在冷藏柜和仓库时无法准确展示。

建议新增：

```text
fnb_material_batch_storage
```

或在 `fnb_material_batch_stock` 增加当前位置字段。最终选哪一种，要结合当前生产库 schema 和现有批次库存代码确认；资料没有提供这两个对象的完整字段，不能直接确定改表方案。

---

# 8. 每日开门检查

## 8.1 检查流程

```text
店长配置区域
    ↓
店长配置检查模板和检查项
    ↓
员工进入“开门检查”
    ↓
系统按当前营业日期生成检查单
    ↓
按存储区域分组展示检查项
    ↓
员工逐项填写／拍照／备注
    ↓
提交
    ↓
系统校验必填项和检查单快照
    ↓
提交成功
    ↓
异常项进入待处理列表
    ↓
店长查看并确认
```

## 8.2 检查项类型

### A. 工具状态检查

例如：

- 菜刀是否在位。
- 砧板是否可用。
- 电子秤是否正常。
- 温度计是否可用。
- 保鲜盒是否齐全。

结果：

```text
正常
异常
缺失
不适用
```

### B. 一次性餐具库存检查

例如：

- 打包盒是否达到最低数量。
- 一次性筷子是否够用。
- 纸巾是否需要补充。

检查方式可以是：

- 只判断“正常／不足”。
- 填写实际数量。
- 系统显示当前库存，员工确认。
- 拍照作为异常凭证。

### C. 环境检查

例如：

- 冷藏柜温度是否正常。
- 冷冻柜门是否关闭。
- 区域是否整洁。
- 地面是否有积水。
- 食材是否放在正确区域。

### D. 安全检查

例如：

- 消毒设备是否关闭。
- 燃气阀门状态。
- 插座和电源。
- 灭火器是否在位。

安全检查涉及实际运营责任，具体项目需要由业务方确认，不能由系统自动推断。

## 8.3 检查项与库存的关系

库存类检查项可以显示：

```text
系统库存：20 包
最低库存：10 包
员工确认：正常
```

或者：

```text
系统库存：3 包
最低库存：10 包
系统提示：库存不足
员工选择：
  - 已补充
  - 尚未补充
  - 数量无误
```

但员工提交开门检查时，不应自动改变库存。

如果确实发生了补充、领用或报损，应通过相应库存业务单据完成。现有库存设计要求库存变化通过单据、流水和批次余额在同一事务中完成，不能从检查结果直接写库存数量。[[C5]]

---

# 9. 是否借鉴现有盘点功能

## 9.1 可以借鉴的机制

可以借鉴：

1. 按门店和营业日期生成业务单。
2. 进入检查时形成快照。
3. 提交时校验模板和对象是否发生变化。
4. 使用 `snapshot_fingerprint` 防止过时页面覆盖新数据。
5. 记录操作员工和操作时间。
6. 按权限限制创建、提交和确认。
7. 保存历史记录，不覆盖过去的检查结果。

现有盘点已经明确采用快照、最新流水 ID、批次集合、版本、数量、效期和状态摘要，并在提交时重新计算比较。[[C5]]

## 9.2 不能直接复用的机制

开门检查不应：

- 写入 `fnb_stocktake_line`。
- 产生盘盈或盘亏流水。
- 修改批次数量。
- 修改成本。
- 自动将“工具缺失”转成库存损耗。
- 自动将“餐具不足”转成盘亏。

盘点的结果是库存调整；开门检查的结果是运营状态记录。二者虽然都有“预期值—实际值—异常”，但业务后果不同。

## 9.3 推荐抽象

建议抽象一个公共的“检查快照”机制，而不是让开门检查复用整张盘点单：

```text
公共能力：
  - snapshot_fingerprint
  - row_version
  - business_date
  - submit validation
  - operator audit

盘点：
  - 结果可以产生库存过账

开门检查：
  - 结果只产生检查记录和异常事项
```

这是推荐的技术方向，当前文档没有记载已有公共快照服务，需要开发前检查现有代码是否已经抽取。

---

# 10. API 规格

以下接口命名沿用当前项目的 `api/[controller]/[action]` 约定，新增写操作使用 POST，查询使用 GET。[[C20]]

## 10.1 存储区域

```text
GET  FnbStorage/ListAreas?sessionKey=&shopId=
POST FnbStorage/SaveArea?sessionKey=
POST FnbStorage/DeleteArea?sessionKey=
```

`SaveArea`：

```json
{
  "shop_id": "1",
  "id": "0",
  "parent_id": "10",
  "name": "一次性用品区",
  "area_type": "warehouse",
  "sort": 10,
  "valid": true,
  "remark": ""
}
```

## 10.2 餐饮物资

```text
GET  FnbSupply/ListItems?sessionKey=&shopId=&supplyType=
GET  FnbSupply/GetItem?sessionKey=&shopId=&id=
POST FnbSupply/SaveItem?sessionKey=
POST FnbSupply/DisableItem?sessionKey=
POST FnbSupply/SaveLowStockAlert?sessionKey=
```

所有前端请求字段使用 `snake_case`，与项目既有约定一致。项目现有食材接口已经使用类似 `shopId` 的文档参数描述，但前端请求字段约定要求使用 snake_case；正式 API 契约应以实际代码为准，并在接口核对时重点确认这一点。[[C20]]

这里存在一个需要核实的命名风险：文档示例中的请求字段有 `shopId`、`requestId`，而项目约定要求前端发送 snake_case。文档与项目约定不完全一致，不能直接照抄文档字段，需检查现有 Controller 的实际绑定行为。

## 10.3 一次性餐具库存

如果复用现有库存过账服务，建议提供独立的业务入口：

```text
POST FnbSupply/CreateReceipt?sessionKey=
POST FnbSupply/PostReceipt?sessionKey=
POST FnbSupply/CreateIssue?sessionKey=
POST FnbSupply/PostIssue?sessionKey=
POST FnbSupply/PostWaste?sessionKey=
POST FnbSupply/DeleteReceipt?sessionKey=
```

不建议让客户端直接调用食材 `PostReceipt`，因为食材入库还包含效期、照片和食材规则等校验。当前 `DeleteReceipt` 已存在于食材库存接口，并限制在入库后 10 分钟内、没有后续流水或引用时删除。[[C18]]一次性餐具是否采用相同删除窗口，可复用该原则，但需要重新确认业务。

## 10.4 餐饮工具

```text
GET  FnbTool/List?sessionKey=&shopId=&storageAreaId=&status=
GET  FnbTool/Get?sessionKey=&shopId=&id=
POST FnbTool/Save?sessionKey=
POST FnbTool/ChangeStatus?sessionKey=
POST FnbTool/MoveArea?sessionKey=
```

工具状态变更应保留历史日志，不能只覆盖当前状态。

## 10.5 开门检查

```text
GET  FnbOpeningCheck/GetToday?sessionKey=&shopId=
POST FnbOpeningCheck/Start?sessionKey=
POST FnbOpeningCheck/SaveDraft?sessionKey=
POST FnbOpeningCheck/Submit?sessionKey=
GET  FnbOpeningCheck/List?sessionKey=&shopId=&fromDate=&toDate=
GET  FnbOpeningCheck/Get?sessionKey=&shopId=&id=
POST FnbOpeningCheck/Confirm?sessionKey=
POST FnbOpeningCheck/HandleAbnormal?sessionKey=
```

### `Start`

```json
{
  "shop_id": "1"
}
```

返回：

```json
{
  "check_id": "1001",
  "business_date": "2026-10-02",
  "areas": [
    {
      "area_id": "20",
      "area_name": "一次性用品区",
      "items": []
    }
  ],
  "status": "in_progress"
}
```

### `Submit`

```json
{
  "shop_id": "1",
  "check_id": "1001",
  "snapshot_fingerprint": "...",
  "lines": [
    {
      "check_item_id": "301",
      "actual_value": "normal",
      "result": "pass",
      "abnormal_reason": "",
      "photo_ids": []
    }
  ],
  "remark": ""
}
```

提交失败时应返回明确原因：

- 检查项已被停用。
- 区域已被删除或停用。
- 模板版本已变化。
- 检查单已提交。
- 必填项未填写。
- 快照已过期，需要刷新。

---

# 11. 权限设计

沿用当前餐饮模块的权限分层：

- 在职员工：查看区域、执行开门检查、填写检查结果、查看自己的操作结果。
- `title_level >= 200`：维护物资档案、工具档案、存储区域、检查模板、确认异常和查看完整历史。
- 店长或管理权限：确认检查单、处理异常、调整库存规则。

当前服务端计划中，日常操作由在职员工执行，`title_level >= 200` 管理档案、发布配方、确认盘点、销毁和查看成本。[[C3]]新模块可以沿用这一权限边界，但“店长”是否等同于 `title_level >= 200`，需要以实际授权代码核实。

---

# 12. 前端页面建议

建议继续放在餐饮分包 `pages/fnbinv/` 下，避免重新建设一套餐饮后台入口。现有餐饮管理页面已经位于该分包，包含库存、批次、制作、配方、厨房单和盘点等页面。[[C19]]

新增页面：

```text
pages/fnbinv/storage/
pages/fnbinv/supply/
pages/fnbinv/tool/
pages/fnbinv/opening/
pages/fnbinv/opening-history/
pages/fnbinv/components/area-picker/
pages/fnbinv/components/check-result/
```

## 12.1 库存首页

新增入口卡片：

```text
餐饮物资
  一次性餐具
  可重复使用餐具
  工具
  存储区域
  今日开门检查
```

库存页继续显示现有的临期过期和用量预警卡片。现有库存页已经有这两类提醒入口。[[C4]]

## 12.2 开门检查页

页面按区域分组：

```text
今日开门检查

[后厨]
  冷藏柜
    □ 温度正常
    □ 门关闭
  调料架
    □ 区域整洁

[仓库]
  一次性用品区
    □ 打包盒库存正常
    □ 一次性筷子库存正常

[工具区]
  □ 菜刀齐全
  □ 砧板无明显损坏
```

异常时显示：

- 异常原因。
- 照片上传。
- 是否已处理。
- 处理备注。

---

# 13. 关键业务规则

## 13.1 区域变更

- 物资移动区域必须记录操作人和时间。
- 移动不会生成食材成本流水。
- 已提交的开门检查保留原区域名称和 ID。
- 当前库存展示使用最新区域。
- 区域停用后不能新建检查项，但不能影响历史记录。

## 13.2 一次性餐具入库

- 以 `piece` 作为基本单位。
- 例如 1 箱、每箱 500 个，入库数量为 500。
- 保留原包装单位和换算快照。
- 单价按基本单位保存，或者同时保存包装单位单价和换算结果。
- 入库确认后才产生可用库存。
- 错误入库的删除必须受后续流水、盘点和领用引用限制。

单位和包装换算沿用现有库存设计的基本原则。[[C1]]

## 13.3 餐具领用

建议本期先支持手动领用：

```text
领用原因：
  - 日常使用
  - 外卖打包
  - 员工领用
  - 其他
```

不自动与厨房单关联。当前厨房单已经按菜品配方扣减食材并支持欠料补扣。[[C10]][[C18]]餐具是否随订单自动扣减，属于另一个业务决策，不应在本期隐式加入。

## 13.4 工具异常

工具状态变更：

```text
normal → damaged
normal → missing
damaged → repairing
repairing → normal
damaged → disposed
missing → normal
```

“missing → normal”必须要求备注，避免员工直接恢复丢失工具而没有解释。

## 13.5 开门检查提交

- 员工可以保存草稿。
- 必填项完成后才能提交。
- 异常项必须填写原因。
- 配置要求照片时必须上传照片。
- 提交后普通员工不能修改。
- 店长可以确认，但不应直接修改员工原始结果。
- 更正应通过“处理记录”追加，而不是改写原始检查结果。
- 同一天、同一门店默认只有一张正式开门检查单。
- 重新检查使用补充检查或异常复核，不创建第二张互相冲突的正式单据。

---

# 14. 与盘点的关系

| 项目 | 盘点 | 开门检查 |
|---|---|---|
| 目的 | 确认实物数量并调整库存 | 确认门店是否具备营业条件 |
| 是否产生库存流水 | 是 | 否 |
| 是否修改库存 | 是 | 否 |
| 是否记录快照 | 是 | 是 |
| 是否需要区域分组 | 可选 | 必须 |
| 是否检查工具 | 不适合 | 适合 |
| 是否检查环境 | 不适合 | 适合 |
| 是否可以填写数量 | 是 | 可选 |
| 是否有异常处理 | 有库存调整 | 有整改记录 |
| 是否允许员工执行 | 当前盘点创建受店长权限限制 | 建议在职员工执行 |
| 是否需要店长确认 | 现有盘点由管理权限确认 | 建议异常项需要确认 |

当前盘点创建权限只有店长，且小程序把 `documentId` 按门店存在本地；开门检查不建议沿用这个限制，应允许员工创建和提交，店长负责模板与异常确认。[[C12]]

---

# 15. 实施顺序

## 第一期：基础档案

1. 核对生产库 schema 和现有 EF 模型。
2. 新增 `fnb_storage_area`。
3. 新增 `fnb_supply_item`。
4. 新增 `fnb_tool`。
5. 完成区域、物资、工具的 CRUD。
6. 增加门店权限和有效状态校验。

## 第二期：一次性餐具库存

1. 新增物资入库。
2. 新增领用、报损。
3. 新增库存查询。
4. 新增低库存预警。
5. 增加区域库存展示。
6. 增加库存流水和成本查询。

## 第三期：开门检查

1. 新增检查模板。
2. 新增检查项。
3. 生成当日检查单。
4. 按区域展示。
5. 草稿、提交、确认。
6. 异常照片和处理记录。
7. 增加历史查询和完成率统计。

## 第四期：盘点衔接

1. 在现有盘点中加入一次性餐具。
2. 评估是否加入可重复使用餐具。
3. 不将工具直接接入库存盘盈盘亏。
4. 建立“开门检查异常 → 创建库存业务单／工具处理单”的跳转。
5. 复用快照校验和并发控制，但不复用库存过账结果。

---

# 16. 必须先确认的问题

以下问题不应由开发自行猜测：

1. 一次性餐具是否需要按门店分别建档，还是使用共享档案？
2. 一次性餐具是否需要成本统计？
3. 餐具是否要随厨房单或外卖订单自动扣减？
4. 可重复使用餐具按总数量管理，还是需要逐件编号？
5. 餐饮工具是否需要责任人、维修和报废流程？
6. 哪些工具必须每日检查？
7. 开门检查是否必须每天完成才能进入其他系统？
8. 员工是否可以提交异常但继续营业？
9. 开门检查异常是否需要店长确认后才能关闭？
10. 存储区域是否允许跨门店共享？
11. 是否需要定时提醒未完成开门检查？
12. 低库存的默认规则是否继续采用现有“最近一次入库数量 × 10%”？
13. 一次性餐具是否需要效期字段？
14. 工具和餐具是否需要二维码？
15. 是否允许一天多次检查，还是每天只保留一张正式检查单？

---

# 17. 需要重点核查的现有实现风险

1. **现有数据库是否允许扩展非食材物资**  
   当前文档只确认食材相关表和库存流水表，未确认 `fnb_stock_document` 是否已经通过类型字段支持非食材。需要看生产库 schema 和 EF 映射后再决定是复用还是新增表。[[C13]]

2. **前端字段命名存在文档不一致**  
   项目约定要求前端向后端发送 snake_case，但近期 API 契约示例使用了 `shopId`、`requestId` 等 camelCase。文档与约定不一致，必须以实际 Controller 和客户端 `api.js` 为准。[[C16]][[C19]][[C20]]

3. **盘点快照能力是否已经抽象**  
   现有盘点有快照规则，但资料没有证明已经存在可供开门检查直接调用的公共服务。应先检查代码，避免复制一套快照校验。[[C5]][[C12]]

4. **现有库存位置模型不明确**  
   资料说明了门店、批次和库存扩展，但没有提供批次库存位置字段。存储区域必须先确认是扩展 `fnb_material_batch_stock`，还是新建位置关联表，不能直接在食材主档增加单一位置字段。[[C1]][[C13]]

5. **旧入口兼容问题**  
   现有旧批次入口不能绕过新的库存过账规则；同样，新增餐具库存后不能让旧接口直接修改库存数量。旧写入口需要明确禁用、转发或增加物资类型分支。[[C14]]

## 最终建议

本需求不要做成“把餐具全部塞进食材管理”，而应采用：

```text
餐饮物资统一入口
├── 食材：现有食材库存体系
├── 一次性餐具：复用库存过账底座，但独立档案和业务规则
├── 可重复使用餐具：按数量库存或后续资产化
└── 餐饮工具：独立工具状态管理

存储区域
└── 作为食材、餐具、工具和开门检查的共同维度

每日开门检查
└── 借鉴盘点快照机制，但不产生库存流水
```

这样既能复用现有库存、低库存预警、门店权限和盘点快照能力，又不会把食材效期、厨房扣料和工具状态混为一体。



---

## 引用来源

| 标记 | 来源 | 位置 |
|---|---|---|
| `[[C13]]` | `snowmeet_ai_doc:docs/superpowers/specs/2026-09-21-fnb-inventory-schema-review.md` | 食材管理数据库结构审阅稿 v4 > 表清单 |
| `[[C6]]` | `snowmeet_ai_doc:docs/superpowers/specs/2026-09-21-fnb-inventory-schema-review.md` | 食材管理数据库结构审阅稿 v4 > 七项功能如何落表 |
| `[[C5]]` | `snowmeet_ai_doc:docs/superpowers/specs/2026-09-21-fnb-inventory-schema-review.md` | 食材管理数据库结构审阅稿 v4 > 必须在后端实现的过账规则 |
| `[[C1]]` | `snowmeet_ai_doc:docs/superpowers/specs/2026-09-21-fnb-inventory-schema-review.md` | 食材管理数据库结构审阅稿 v4 > 设计范围与选择 |
| `[[C19]]` | `snowmeet_ai_doc:sessions/2026-09-23_fnb_miniprogram_client_and_api_verification.md` | 2026-09-23 食材管理：小程序客户端实现 + codex 服务端接口验证 > 4. 小程序客户端 |
| `[[C12]]` | `snowmeet_ai_doc:docs/superpowers/plans/2026-09-23-fnb-inventory-api-verification.md` | 食材管理服务端接口验证报告 > 静态审查中的其他发现（未改服务端，客户端已绕开） |
| `[[C4]]` | `snowmeet_ai_doc:sessions/2026-09-24_fnb_prepared_recipe_low_stock_and_guide.md` | 2026-09-25 ~ 09-27 食材管理第三轮打磨：半成品分类与配方、制作页开封、用量预警、操作指南 PPT > 4. 用量预警（09-26） |
| `[[C2]]` | `snowmeet_ai_doc:sessions/2026-09-24_fnb_category_inbound_kitchen_orders.md` | 2026-09-24 食材管理第二轮打磨：分类属性下沉、入库简化、厨房单按菜品配方扣料与欠料补扣 > 关键改动文件 |
| `[[C7]]` | `snowmeet_ai_doc:docs/superpowers/specs/2026-07-15-fnb-mat-expire-design.md` | 食材过期提醒（fnb mat_expire）设计 |
| `[[C18]]` | `snowmeet_ai_doc:docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md` | 食材管理服务端 API 契约（小程序接入前审阅） > 2026-09-24 变更：分类属性下沉到食材 |
| `[[C16]]` | `snowmeet_ai_doc:docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md` | 食材管理服务端 API 契约（小程序接入前审阅） > 2026-09-23 补充：菜品接口与小程序客户端 |
| `[[C20]]` | `snowmeet_ai_doc:docs/superpowers/plans/2026-09-22-fnb-inventory-api-review.md` | 食材管理服务器 API 开发计划（审阅稿） > 实现方式 |
| `[[C3]]` | `snowmeet_ai_doc:docs/superpowers/plans/2026-09-22-fnb-inventory-api-review.md` | 食材管理服务器 API 开发计划（审阅稿） > 已确认的实施边界 |
| `[[C10]]` | `snowmeet_ai_doc:sessions/2026-09-24_fnb_category_inbound_kitchen_orders.md` | 2026-09-24 食材管理第二轮打磨：分类属性下沉、入库简化、厨房单按菜品配方扣料与欠料补扣 > 6. 库存不够时怎么处理 |
| `[[C14]]` | `snowmeet_ai_doc:docs/superpowers/specs/2026-09-21-fnb-inventory-schema-review.md` | 食材管理数据库结构审阅稿 v4 > 兼容旧功能与数据接管 |

## 用户 · 2026-10-02T20:36:32+08:00

今天的输出，等待崔洋确认！



## 助手 · 2026-10-02T20:36:37+08:00

收到。**2026-10-02 餐饮管理系统对象关系图本版输出，当前状态：等待崔洋确认。**

在确认前，先不据此进入开发、建表或调整关系。



## 用户 · 2026-10-02T21:59:45+08:00

文件有更新仅仅记录下。



## 助手 · 2026-10-02T21:59:50+08:00

已记录本轮文件更新，**暂不解读、不据此进入开发**，继续等待崔洋确认。

- `Weixin Image_20261002203450_83_283.jpg`：原件已保存，未提取文本；原件下载：[`/api/attachments/5/download`](/api/attachments/5/download)
- `snowmeet.pptx`：已保存并提取第 1–20 页文本；原件下载：[`/api/attachments/6/download`](/api/attachments/6/download)
- PPT 末页提到的高清原图「食材管理-对象关系图.png」本轮未作为独立附件提供，暂不猜测其内容。



## 附件原件

- [Weixin Image_20261002203450_83_283.jpg](../files/1_Weixin%20Image_20261002203450_83_283.jpg) · SHA-256 `4bfae267416beb25186b9b6500f1cc4f91473e86e59a2bce9c5ef3f4fcbffa33`
- [Weixin Image_20261002203450_83_283.jpg](../files/5_Weixin%20Image_20261002203450_83_283.jpg) · SHA-256 `4bfae267416beb25186b9b6500f1cc4f91473e86e59a2bce9c5ef3f4fcbffa33`
- [snowmeet.pptx](../files/6_snowmeet.pptx) · SHA-256 `bb58b928c2a766b21f357953bef7ff6ecc75d0666251747210865bfe3764090f`
