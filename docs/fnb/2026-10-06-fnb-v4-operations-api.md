# 食材管理 v4 完整后端扩展契约

2026-10-06 用户将范围扩展为全部 v4 后端，包含原计划排除的存储区域、开门检查、餐饮物资与工具。本文补充 [认证与主数据契约](2026-10-06-fnb-v4-api-contract.md)。本机已通过构建、467 项非 SQL 回归与 22 项 LocalDB 集成测试（含 32 步）；共新增 69 个动作，连同第一期 17 个共 86 个 v4 动作。生产当前仍是第一期 API 和 H5，生产 SQL 必须先供用户审阅。

## 通用约定

- 路径 `/api/{controller}/{action}`；会话 `sessionKey` 在 query。GET 的 `shopId` 在 query，POST 在 JSON body。
- S 为本店在职员工，M 为店长。鉴权复用现有小程序和企业微信会话；跨店返回 code 3。主数据共享，库存、区域、配方、订单、检查和流水分店。
- 返回 `{code,message,data}`，code 0/1/2/3/4 分别为成功、业务错误、会话失效、权限错误、并发冲突。
- 库存写、撤销、工具状态及检查流程请求全部携带非空 UUID `requestId`。同店同动作同 ID 同请求精确返回首次结果；同 ID 换内容 code 4。网络失败沿用原 ID，不自动生成新 ID 重试。查询和主数据配置不需要 ID。
- 写操作统一 Serializable；查出后修改显式标记 Modified。库存金额按 6 位小数分摊；批次最后一次扣减取全部剩余金额，库存永不负数。SQL 1205、唯一竞争及 rowversion 冲突映射 code 4。
- 请求字段 camelCase，实体字段下划线；long ID 输入支持十进制字符串，输出均字符串；int 数字。数量最多 6 位小数，基本单位 g/ml/piece，温度允许负数。
- 时间戳 UTC，营业日 UTC+8；当天到期可使用，到期早于今天不可扣；未来 `ready_at` 不可扣。换算、到期、批号、推荐、份数、配方所需量和报表全部服务端计算。

## 库存、入库、作业

| 控制器/动作 | 方法/权限 | 业务输入及返回 |
|---|---|---|
| FnbHome/GetHome | GET/S | 返回预警、临期/过期、在库品种/批次、已开封、进行中作业、建议作业数量、营业日及今日检查状态 |
| FnbInbound/NextBatchNo | GET/S | itemId；返回 batchNo 与 reserved=false，预览不占号；过账重新生成 |
| FnbInbound/PreviewExpiry | GET/S | itemId,storageType,productionDate?,expireDate?；返回到期、来源、规则及是否过期 |
| FnbInbound/PostReceipt | POST/S | requestId,lines[1..100],remark?；返回 documentId 与成品批次详情 |
| FnbInbound/DeleteReceipt | POST/S | requestId,documentId；10 分钟内、无后续流水才能撤销，原单标记 cancelled，保留批次及正反流水 |
| FnbStock/ListStock | GET/S | categoryId?,storageType?,keyword?；每项包含可用、待作业、封装、总量、金额、预警、可出餐数及形态分层 |
| FnbStock/GetItemLayers | GET/S | itemId；单食材库存与各形态批次 |
| FnbStock/GetBatch | GET/S | batchId；批次、食材/形态名、显示单位与数量、可用性、到期剩余天数、区域、照片与标签字段 |
| FnbStock/ListExpiry | GET/S | kind?=expired/today/near；按有效到期排序的批次详情 |
| FnbStock/ListDestroy | GET/S | 待销毁批次及已销毁单据 |
| FnbStock/PostDestroy | POST/S | requestId,batchId,quantity,reason,confirmExpired=true；只能销毁确实过期的批次 |
| FnbStock/PostWaste | POST/M | requestId,batchId,quantity,reason；按基本量报损，封装须整包装 |
| FnbStock/ListLowStock | GET/S | 返回 food 与 supplies，两类均含服务端阈值 |
| FnbStock/SaveLowStockRule | POST/M | itemId,ratio 或 quantity，两者只能一个非 null |
| FnbOperation/GetWorkbench | GET/S | 进行中、建议、可作业批次、今日记录与是否就绪 |
| FnbOperation/PreviewOperation | GET/S | batchId,quantity；投入单位/基本量、预计产出、比例/出成率、耗时、就绪时间、新批号、到期及储存 |
| FnbOperation/PostOperation | POST/S | requestId,batchId,inputQuantity,actualQuantity,areaId；只做相邻一步，actualQuantity 是产出形态单位量；返回作业、实际出成率、偏低提示和新批次 |
| FnbOperation/CompleteOperation | POST/M | requestId,operationId；仅店长提前完成，到时无需调用即可继续作业或使用 |

入库行字段：`itemId,specId?,quantity,amount,storageType,productionDate?,expireDate?,areaId,sealed=false,packSize?,packLabel?,openStorage?,openDays?,photoIds?`。区域必须是本店启用的下级区域，上级也须启用。有多形态链必须选有效进货规格，数量乘入口形态 per_base；单形态散装按基本单位。单形态 sealed 模式 quantity 是整数包装数，packSize 是每包装基本量，须填写开封储存及天数。半成品不得采购入库。照片须为当前员工上传的食材文件。

保质期优先显式到期，否则生产日 + 适用规则；食材规则先于分类，同层当季先于 all。6–9 月 warm，其余 cold。拒绝未来生产日期和已过期入库。批号按营业日/二级分类编码/店内序号生成，派生批号来源号-形态编码，多次部分作业增加后缀。

作业投入按来源形态单位，实际产出按目标形态单位，均在服务端折基本量；产出超过投入基本量拒绝，零产出允许并全记损耗。产出保留投入成本，零产出成本记损耗。派生有效到期为原到期、已有作业到期、本次作业到期的最小值。封装开封投入为整数包装数。

## 半成品、配方、出餐、盘点及报表

| 控制器/动作 | 方法/权限 | 输入及返回 |
|---|---|---|
| FnbPrep/ListPreps | GET/S | 全部半成品与本店最新配方及用料 |
| FnbPrep/CreatePrep | POST/M | categoryId,name,unitName,baseUnitCode,outputQuantity,lines?；新建半成品及初版配方，空用料为草稿 |
| FnbPrep/SavePrepBom | POST/M | ownerId=半成品 itemId,outputQuantity,lines；发布新版本，不覆盖历史 |
| FnbPrep/PreviewPreparation | GET/S | itemId,batches；服务端返回每项所需量、可用量、缺口及总产出 |
| FnbPrep/PostPreparation | POST/S | requestId,itemId,batches,areaId,expireDate?；FEFO 核销全部用料，不足整体回滚；产出每批量×批数 |
| FnbPrep/ListPrepRecords | GET/S | 单据、用料/产出行及批次流水 |
| FnbDish/ListDishes | GET/S | 本店菜品及规格、最新配方、用料和完整配方限制的可出餐份数 |
| FnbDish/CreateDish | POST/M | name,specName=标准,salePrice?；创建本店餐饮 product 与默认规格，valid 显式为 1 |
| FnbDish/AddSpec | POST/M | productId,name,salePrice?；菜内名称唯一 |
| FnbDish/DeleteSpec | POST/M | specId；软停用，最后一个规格或待出餐引用拒绝 |
| FnbDish/SaveSpecLines | POST/M | ownerId=specId,outputQuantity=1,lines；发布配方新版本 |
| FnbServe/CreateOrder | POST/S | requestId,lines[{specId,quantity}],tableNo?,remark?；手动厨房单，快照引用当时的配方版本 |
| FnbServe/ListPendingOrders | GET/S | 待出餐订单及行，最多 200 单 |
| FnbServe/PreviewServe | GET/S | orderId；默认总用料、可用量、缺口、上游量与 receive/operate/ready 建议 |
| FnbServe/PostServe | POST/S | requestId,orderId,lines?；lines 为微调后的总用量，只能选订单配方食材，可为零；返回成本与实际/短缺量 |
| FnbServe/ListServeLog | GET/S | 单据、原订单/备注、扣减行、具体批次流水，最多 200 笔 |
| FnbStocktake/CreateSnapshot | POST/S | requestId；本店在库食材，仅出品态可用数量和批次指纹 |
| FnbStocktake/GetSnapshot | GET/S | documentId；系统量、实盘、差异与快照 |
| FnbStocktake/SaveCount | POST/S | requestId,documentId,lines[{itemId,quantity,remark?}]；保存实盘，不改库存 |
| FnbStocktake/PostStocktake | POST/M | requestId,documentId；所有行需填写；批次指纹改变 code 4，须新快照；盘亏 FEFO 扣，盘盈新批次入 |
| FnbReport/GetDashboard | GET/S | from?,to?；默认本周，范围不超过 366 天；损耗率、成本周转天数、成本结构、损耗台账和单独盘盈 |
| FnbReport/GetRecipeChain | GET/S | 每菜品规格×用料一行，采购态/单位/储存、每份反推采购量、每段作业/形态/单位/出成率/耗时 |
| FnbReport/DownloadRecipeChain | GET/S | 同预览行导出 XLSX，冻结表头及自动筛选 |
| FnbLabel/GetLabelData | GET/S | batchId；直接返回打印模块所需 batchId,name,batchNo,expireDate，以及形态、单位、数量、二维码 |

配方用料行 `[{itemId,quantity}]`，均为每份或每批的基本单位量。半成品循环依赖拒绝。只消耗未过期、已就绪出品态，按有效到期/收到时间/id FEFO。出餐不足记录 shortage_qty，不透支批次，订单过账后为 served；相同请求重试幂等，新 ID 再出餐拒绝。半成品产出保质期取配置值/人工到期，并不延长所耗用料的最早有效到期。

看板损耗率为损耗成本/(损耗成本+出餐成本)，分母零返回 0；平均成本周转天数为在库成本/日均出餐成本，无出餐为 null。盘盈单列，不算负损耗。盘盈沿用现有可用出品态最早到期及单位成本；无可用旧批次时到期设今天、成本 0。

## 存储区域、物资、工具、开门检查

| 控制器/动作 | 方法/权限 | 输入及返回 |
|---|---|---|
| FnbArea/ListAreas | GET/S | includeDisabled=false；区域、有效状态、照片、检查项、四类绑定数量 |
| FnbArea/SaveArea | POST/M | id=0 新建,parentId?,name,areaType=other,valid=true,sort=0；最多两级，同级有效名称唯一 |
| FnbArea/DeleteArea | POST/M | id；任何历史绑定、照片、检查项、工具日志或下级均拒绝删除，只可停用 |
| FnbArea/AddPhoto | POST/S | areaId,uploadId；每区域最多 6 张，记录员工与时间 |
| FnbArea/RemovePhoto | POST/M | areaId,uploadId；只移除区域关联，不直接删共享文件 |
| FnbSupply/ListSupplies | GET/S | type?=disposable/reusable；个数库存、包装量、预警阈值 |
| FnbSupply/SaveSupply | POST/M | id,name,supplyType,packSize,packLabel,areaId?,spec?,valid=true |
| FnbSupply/PostMovement | POST/S | requestId,supplyId,type=in/out/waste,quantity,reason?；in 数量为整数包装数，其他为个数；出库须原因，不能透支 |
| FnbSupply/UndoReceipt | POST/S | requestId,movementId；10 分钟内且无后续有效流水的入库，保留 cancelled 记录 |
| FnbSupply/ListLog | GET/S | supplyId；最近 200 条流水 |
| FnbSupply/SaveLowStockRule | POST/M | supplyId,ratio 或 quantity 二选一 |
| FnbTool/ListTools | GET/S | status?=normal/missing/damaged/repairing/disposed/abn |
| FnbTool/SaveTool | POST/M | id,name,quantity,spec?,areaId?,ownerStaffId?,dailyCheck=false,assetNo?,valid=true；每日检查工具自动同步检查项 |
| FnbTool/ChangeStatus | POST/S，报废 M | requestId,toolId,status?,areaId?,remark?；变更写状态/位置日志，找回和报废须说明 |
| FnbTool/ListLog | GET/S | toolId；最近 200 条日志 |
| FnbCheck/SaveItem | POST/M | id,areaId,name,method=yes_no/number/photo,kind=environment/safety/tool/supply,required=true,photoSuggested=false,unit?,minimum?,maximum?,toolId?,supplyId?,valid=true |
| FnbCheck/GetToday | GET/S | 今日检查状态/快照；无单时给当前有效配置 |
| FnbCheck/StartToday | POST/S | requestId；每店每天最多一张正式单 |
| FnbCheck/RefreshSnapshot | POST/S | requestId,sheetId；刷新有效检查项；相同标准保留结果，方式/阈值/单位/对象改变清结果 |
| FnbCheck/SaveDraft | POST/S | requestId,sheetId,lines[{itemId,result?,value?,reason?,uploadId?}]；number 在服务器按实测值计算 pass/abnormal |
| FnbCheck/PassAll | POST/S | requestId,sheetId；只填未填的非数值项，保留异常和已有结果 |
| FnbCheck/Submit | POST/S | requestId,sheetId；必填完成、异常写原因；配置改变 code 4，须刷新 |
| FnbCheck/HandleAbnormal | POST/M | requestId,lineId,remark；提交后追加异常处理，不覆盖员工记录 |
| FnbCheck/Confirm | POST/M | requestId,sheetId；所有异常有处理记录才可确认 |
| FnbCheck/GetSheet | GET/S | sheetId；配置快照、原结果、处理记录及进度 |
| FnbCheck/ListHistory | GET/S | from?,to?；最多 200 张检查单 |

区域类型为 other/kitchen/front/warehouse/cold。新库存写必须选启用下级区域；历史批次通过扩展表记录位置，不修改已发布批次表。物资不进入配方，不随出餐扣。reusable 只补充和报损，不领用。

工具状态路径与原型一致：normal→damaged/missing，damaged→repairing/disposed，repairing→normal，missing→normal，disposed 不再转换。移动写日志；报废自动停用该工具检查项。数值检查允许 na，否则实测必须填；异常草稿可暂缺原因，但提交拒绝。检查只更新运营记录和工具最近检查日，不产生库存流水。

## 公共模块、默认做法与切换

照片继续 `FnbMaterial/UploadPhoto`，OCR 继续 `FnbMaterial/OcrScanName`，签名与蓝牙沿用 `FnbWeCom/GetJsSdkSignature` 和现有 BlePrint/TSPL 模块。未删除或重写这些模块。`FnbMaterial/PushExpireAlert` 原 cron URL 重新映射到 v4 批次，按店员配置天数和北京时间营业日去重；发送网关测试全部用假实现，不发真实消息。失败可重试，并发触发用数据库发送占位避免立即重复；外部发送后进程崩溃仍可能在占位超时后重复，这是外部接口与数据库无法原子提交的限制。

默认做法全部遵守：仅店长提前完成耗时作业、不提供作业撤销、投入允许小数、条码全局唯一、主数据共享而库存/配方分店。美团采集与自动订单导入仍按原计划后续接，不修改采集代码，小程序不改。

上线顺序：用户先审阅 [13 张新表扩展 SQL](../../sql/2026-10-06_fnb_v4_operations.sql) → 明确执行后再在生产补结构 → 发布 API → 联调并发布 H5 新接口接入。本次没有生产 SQL、消息发送、文件清理或部署；不能仅靠发布 API 就认为已部署的 H5 占位按钮自动开通。
