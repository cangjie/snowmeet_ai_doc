# 食材管理 v4 服务端接口契约

日期：2026-10-06。上午部署的是第 1 期 17 个认证与主数据接口。用户随后明确要求开发全部 v4 后端，现已补入库、库存、作业、半成品、菜品、厨房单、出餐、盘点、报表，以及原排除的区域、物资、工具、开门检查。新增实现及完整请求格式见 [完整后端扩展契约](2026-10-06-fnb-v4-operations-api.md)。完整后端与扩展 SQL 已于 18:29 生产发布。

同日下午新增并部署企业微信 H5，已接入第一期接口并复用现有上传/OCR/蓝牙模块。用户指出客户端仍是旧样子后，全部运营模块已补接口接入并发布 ai@4a5b3fa1。页面覆盖与切换约定见 [H5 文档](2026-10-06-fnb-v4-h5.md)。`/fnb/b` 保留静态入口跳转，新后端另提供批次查询及标签数据。

## 数据与上线约定

- 用户修订为只新增 SQL：`sql/2026-10-06_fnb_v4_rebuild.sql` 新增 18 张 `fnb_v4_*` 表、2 个视图，共用 `fnb_unit`，只补缺失单位种子；不删除、不更新、不覆盖任何旧食材表或数据。
- 新系统从新增空表开始；不会读取旧食材业务数据。分类、食材、链路、进货规格在门店间共享；库存、配方和单据按门店隔离。
- 用户随后要求删除不再使用的旧对象：18 张旧食材表和 2 个旧视图已通过独立 [DROP 脚本](../../sql/2026-10-06_fnb_drop_legacy_objects.sql) 从生产库删除；fnb_unit、v4 及共享表保留。原增量脚本仍只新增，不得重建旧表或启用旧业务接口。见 [执行记录](../../sessions/2026-10-06_fnb-drop-legacy-objects.md)。
- SQL 重复执行会跳过已有对象；已有对象缺字段会报错并回滚，要求人工核对，不自动覆盖。脚本不读取连接配置，由用户审阅后执行。2026-10-06 用户另行明确授权，本次已代为执行生产 SQL，并运行服务器原有 republish.sh 发布 `ec7c2561`，见部署记录。
- 这只是第一期，不能直接作为完整食材系统上线。旧业务控制器已停止注册，旧批次读写和提醒方法不再是路由；上传、OCR、旧 OAuth 和 JS-SDK 签名暂留，第三期再迁移公共接口。旧类型/访问器只供未迁移源码编译，旧批次、分类、食材和视图已从 EF 模型排除。
- 当前生产已提供本文 17 个主数据/身份接口；第二、三期功能尚未提供。新食材与批次表为空，旧食材页面仍保留原文件，但旧业务接口已停用。

## 调用格式

- 基址：`/api/{controller}/{action}`，同源 H5 不需要新增 CORS。
- `sessionKey` 始终在 query。GET 的 `shopId` 在 query；POST 的 `shopId` 在 JSON body。
- GET `FnbAuth/GetMe` 不要求 `shopId`。`FnbAuth/WeComLogin` 不要求旧会话。
- JSON body 使用 camelCase；数据库实体字段保持下划线命名，如 `base_unit_code`。`long` 主键及外键均以 JSON 字符串返回；`int` 返回数字。数量、比例为 JSON 数值。
- 返回统一为 `{ "code": 0, "message": "", "data": ... }`。业务错误仍为 HTTP 200；JSON 类型不符、缺少必需 body 等由 ASP.NET Core 返回 HTTP 400。
- 返回码：0 成功；1 输入或业务规则不满足；2 会话失效、非支持会话或员工已离职；3 无门店/角色权限；4 并发冲突、SQL 1205 死锁或唯一索引竞争。
- S：本店在职店员。M：S 且 `title_level >= 200`。不接受客户端自报身份或角色。每次请求重新解析现有 `mini_session`、员工绑定和所属门店。
- 第一期开通的写接口只维护主数据，不改变库存，不需要 `requestId`。全部写操作使用 Serializable 事务；第二、三期的库存写接口必须额外使用 `requestId` 幂等，同一冲突请求重试沿用原值。
- VARCHAR 按 GBK 字节长度校验，不接受无法存入 `Chinese_PRC_CI_AS` 的字符（例如 emoji）。编码标准化为大写 A–Z/0–9，1–16 位。
- 时间戳为 UTC `datetime2(3)`；生产/到期等日期为 date；营业日期按 Asia/Shanghai。前端不得自行计算换算、批次号、到期、出成率或可出餐数量。

## FnbAuth

| 方法 | 动作 | 输入 | 返回 |
|---|---|---|---|
| GET | GetMe | query: `sessionKey` | 身份对象 |
| POST | WeComLogin | body: `{ "code": "企业微信OAuth授权code" }` | 身份对象，含新 `sessionKey` |

身份对象：`staffId`, `name`, `shopId`, `shopName`, `isManager`, `clientType`（mini/wecom）, `sessionKey`（GetMe 为 null）。两端用同一个 GetMe；小程序继续使用现有 MemberLogin。企业微信 code 经现有餐饮应用换 UserId，只给已关联的在职员工且已配置有效门店者发 30 天会话。未关联/无门店时不发会话，不自动创建员工或会员。测试使用假 OAuth 网关，不调用真实企业微信。

## FnbCatalog

| 方法 | 动作 / 权限 | 输入 | data |
|---|---|---|---|
| GET | ListUnits / S | `shopId`, 可选 `measureType`（weight/volume/count） | 启用单位列表，按 sort/code 排序 |
| GET | ListCategories / S | `shopId`, `includeDisabled=false` | 分类实体列表，按 level/sort/id 排序 |
| POST | SaveCategory / M | 分类输入 | 保存后的分类实体 |
| POST | DeleteCategory / M | `shopId`, `id` | `{ "ids": [停用的分类id] }` |
| GET | ListShelfRules / S | `shopId`, 可选 `categoryId` 或 `itemId`（不能同时传），`includeDisabled=false` | 保质期规则实体列表 |
| POST | SaveShelfRule / M | 规则输入 | 保存后的规则实体 |

分类输入：`shopId`, `id`（0 新建）, `parentId`, `level`（1/2）, `name`，可选 `batchCode`, `measureType`, `defaultStorage`, `warnDays`, `openDays`, `isPrepared=false`, `sort=0`, `valid=true`。

- 一级只维护名称/排序，`parentId` 和分类属性均为空，`isPrepared=false`。
- 二级必须挂在有效一级分类下，必须提供 `batchCode`、`measureType`、`defaultStorage`。weight 对应 g，volume 对应 ml，count 对应 piece；数据库单位维度分别为 1/2/3。
- 二级 `isPrepared` 决定食材类型 raw/prepared。分类下已有任何食材时，不允许改变计量类型或原料/半成品类型；不批量改写既有食材。
- 有效同级名称唯一，有效二级批次编码唯一。已有分类层级不可变。
- DeleteCategory 软停用；删除一级时一起停用子分类。存在任何食材（含停用食材）则整次操作拒绝。停用分类名可以重新使用，不改旧行名称。
- `warnDays` / `openDays` 可为空，非空为 0–36500。0 是有效覆盖值。

规则输入：`shopId`, `id`（0 新建）, `categoryId` 或 `itemId`（二选一）, `storageType`, `season`（all/warm/cold）, `days`（1–36500）, `valid=true`。分类级只允许有效二级分类。已有规则不能改归属，可改天数/季节/储存方式/启停。有效同归属、同储存方式、同季节唯一。

规则回退由服务端执行：先食材，再分类；同一层先季节专用规则，再 all；warm 为生产月份 6–9 月，cold 为其余月份。

## FnbRoute

| 方法 | 动作 / 权限 | 输入 | data |
|---|---|---|---|
| GET | ListItems / S | `shopId`, 可选 `categoryId`, `keyword`, `page=1`, `pageSize=30`（1–100） | `{ total, rows }` |
| GET | GetRoute / S | `shopId`, `itemId` | `{ item, defaults, forms, specs, shelfRules }` |
| POST | CreateItem / M | 新食材输入 | 食材实体；同事务自动创建一个出品态 |
| POST | SaveItemDefaults / M | `shopId`, `itemId`, `warnDays`, `openDays`（可 null） | 食材实体 |
| POST | AddUpstreamForm / M | 新上游形态输入 | 新形态实体 |
| POST | UpdateForm / M | 形态编辑输入 | 更新后的形态实体 |
| POST | RemoveForm / M | `shopId`, `itemId`, `id` | `{ id }` |
| POST | SaveSpec / M | 进货规格输入 | 保存后的规格实体 |
| GET | FindSpecByBarcode / S | `shopId`, `barcode` | `{ spec, item, entryForm }` |

ListItems 的每行：`item`（实体）、`categoryName`、`effectiveWarnDays`、`effectiveOpenDays`、`defaultStorage`、`measureType`。只返回启用食材。

GetRoute 的 `defaults`：`warnDays`、`openDays`、`storageType`、`measureType`。`forms` 只含有效形态，按 seq 升序；`specs` 包括停用项，按 sort/id 排序；`shelfRules` 包括有效的食材级和所属分类级规则。

新食材输入：`shopId`, `categoryId`, `name`, `finalFormName`, `baseUnitCode`；可选 `finalFormCode="F"`, `storageType`（空则取分类默认）, `warnDays`, `openDays`, `imageId`。基本单位必须是与分类相符的 g/ml/piece，且已启用。同分类的启用食材名称唯一。新食材和出品态显式 `valid=true`。

SaveItemDefaults 是原计划补充的必要接口，用来实现「分类给默认值，食材可以单独改」：null 恢复分类回退；临期默认最终回退为 1 天；开封天数最终为空表示不改变到期。保存不改历史批次。

新上游形态输入：`shopId`, `itemId`, `name`, `unitName`, `perBase`, `storageType`, `formCode`, `opName`；可选 `standardYield=1`, `durationHours=0`, `shelfAfterOpDays`。

形态编辑输入：`shopId`, `itemId`, `id`, `name`, `unitName`, `perBase`, `storageType`, `formCode`；可选 `shelfAfterOpDays`, `opName`, `standardYield=1`, `durationHours=0`。

- 每条链至少保留出品态。最上游 seq=0，最大 seq 是出品态；只允许在最上游增加/删除，服务端维护连续序号。
- 到达形态的作业存放在目标形态上。新增上游时，`opName` 等表示「新上游 → 原最上游」的作业。最上游无到达作业，编辑时 `opName` 必须为空；其他形态须提供作业。
- `perBase` 是 1 个形态单位的基本量。出品态固定 `perBase=1`、`unitName=baseUnitCode`。形态单位只用于显示。
- `in_op_ratio` 由服务端用「上游 perBase / 下游 perBase」生成，保留 6 位小数。标准出成率独立为 (0,1]；耗时不小于 0。数量/比例输入最多 6 位小数，允许小数投入。
- 同食材有效形态编码唯一。已有规格、批次或流水引用时，不能改变该形态换算、单位或编码。
- RemoveForm 只允许未被任何规格（含停用项）、批次、单据或作业引用的最上游形态，并保留出品态。软停用后重新排号。

进货规格输入：`shopId`, `itemId`, `id`（0 新建）, `entryFormId`, `name`；可选 `brand`, `packDesc`, `barcode`, `sort=0`, `valid=true`。

- 入口形态必须属于同一启用食材。条码可空；去首尾空白；有效非空条码按数据库不区分大小写的规则全局唯一。
- 一旦被任何批次或入库行引用，只允许提交原字段值并设置 `valid=false`，不能改名称/包装/条码/入口/排序，也不能重新启用。
- FindSpecByBarcode 只找启用规格，返回入口形态，供两端扫码后直接选入库层级。

## 分类与形态样例

```json
{
  "shopId": 1, "id": 0, "parentId": 10, "level": 2, "name": "牛肉",
  "batchCode": "BEEF", "measureType": "weight", "defaultStorage": "frozen",
  "warnDays": 2, "openDays": 3, "isPrepared": false, "sort": 0, "valid": true
}
```

```json
{
  "shopId": 1, "itemId": 20, "name": "采购箱", "unitName": "箱",
  "perBase": 10000, "storageType": "frozen", "formCode": "BOX",
  "opName": "冷藏解冻", "standardYield": 1, "durationHours": 24
}
```

## 后续期的默认约定

耗时作业仅店长可提前完成；作业暂不撤销；投入量允许小数；条码全局唯一；主数据跨店共享，库存/配方按店隔离。前两项要到第二期作业接口实现，本期只预留结构，不声称已实现库存操作。

耗时、到期、可扣判断与出成率必须由服务端计算。批次只有 final、未过期、未处置、ready_at 已到才可扣；半成品、出餐、盘点共用同一规则。两端只显示接口结果。第 2、3 期新增字段/契约另行补充，不从原型前端搬计算逻辑到新客户端。
