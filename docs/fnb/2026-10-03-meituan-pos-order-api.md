# 美团管家（pos.meituan.com）订单接口勘察记录

2026-10-03 用真实账号（门店「Snowmeet · 多呆一会儿吧」）录制勘察，并用采集程序自动跑通一轮。
本文只记录接口地址、参数和字段结构，**不含任何顾客数据**。
采集程序：`SnowmeetApi/Tools/meituan_collector/`（Python）。

## 结论

- **能抓下来。** 订单列表在报表的「订单明细」，菜品明细在每张单的详情接口里。
  - 店内、外卖平台、外卖自营三类订单都有列表接口。
  - 菜品明细不在列表里（`itemList` 为 null），每张单要单独打开详情才能拿到。
- **抓取方式：** 采集程序打开真实的 Edge 浏览器，直接打开下面的页面地址，由页面自己发请求，程序只截获返回结果。
  - 美团的接口带安全签名（`yodaReady=h5&csecplatform=4&csecversion=4.3.0`，由页面上的 H5guard 生成），不在浏览器外伪造请求。
- **2026-10-03 实测：** 单轮抓取抓到当天 14 张店内单和 2 张美团外卖单，16 张详情全部取到。
  - 每张详情约 13 秒（含 1.5 秒间隔）。
  - 详情没变化的单，下一轮直接跳过。
- **登录状态会保存在采集程序的浏览器配置目录里。**
  - 17:59 登录，18:03、18:47 两次重启程序都不用重新登录。
  - 能保持多久还要继续观察。

## 页面地址（采集程序直接打开）

| 用途 | 页面地址 | 页面发出的数据接口 |
|---|---|---|
| 店内订单列表 | `/web/report/orderList#/rms-report/orderList` | `POST /web/api/v2/reports/order-detail-instore/list` |
| 外卖平台订单列表 | `/web/report/orderListWM#/rms-report/orderListWM` | `POST /web/api/v2/reports/order-detail-platform/list` |
| 外卖自营订单列表 | `/web/report/orderListWMSelf#/rms-report/orderListWMSelf` | `POST /web/api/v2/reports/order-detail-self/list` |
| 订单详情 | `/web/fe.rms-portal/rms-report.html#/rms-report/orderDetail?orderId={orderBase.id}` | `GET /web/api/v1/orders/detail?orderId={orderBase.id}` |
| 退款单列表 | `/web/report/refundOrderList#/rms-report/refundOrderList` | `POST /web/api/v2/reports/refund-order/list` |
| 退款单详情 | `/web/fe.rms-portal/rms-report.html#/rms-report/refundOrderDetail?refundId={refundId}` | `GET /web/api/v1/orders/refund/detail-pos?refundId={refundId}` |
| 菜品库 | `/web/operation/goods/list#/rms-goods/goods/list` | `POST /web/api/v1/admin/poi/goods/filter-es`（主列表不带 spuType；套餐列表 `spuType:20`） |
| 菜品分类树（菜品库顺带请求） | — | `GET /web/api/v1/goods/common/poi/categories/tree` |
| 菜品分类（报表页顺带请求） | — | `POST /web/api/v2/reports/goods/poi/categories/list` |
| 菜品名字典（报表页顺带请求） | — | `POST /web/api/v2/reports/dict/search-deleted-dish-list` |

菜单树（`GET /web/api/v1/permissions/menu/pc/tree`）里有全部页面的地址，例如菜品属性（规格/做法/加料）`/web/operation/goodsv2/attribute`、美团外卖菜品 `/web/operation/goods/waimailist`、菜品销售明细 `/web/report/dishSaleDetail`。

登录页：`/web/rms-account#/login`。登录表单在 `rmslogin.meituan.com` 的 iframe 里。判断是否已登录的依据：页面地址里有没有 `/rms-account`。

## 列表接口参数（页面默认发出的）

- **时间：** `startDate`/`endDate`、`beginTime`/`endTime` 都是毫秒时间戳，默认是当天 00:00:00.000～23:59:59.999（北京时间），`queryTimeType: "4"`。
- **分页：** `pageNo`、`pageSize: 20`。返回里有 `total`、`totalPageCount`。
- **店内：**
  - `typeList: ["100","200","400"]`
  - `unionTypeList: [0,1]`
  - **默认 `statusList: ["300"]`，即只查「已结账」。** 页面上的标签对应：全部订单＝不传 statusList、未结账＝`200`、已结账＝`300`、已退单＝`["500","30"]`、已撤单＝`600`。采集程序会点「全部订单」。
- **外卖平台：** `sourceList: ["21","22","32","36","44"]`。默认 `tabType: "2"`＝有效订单；「全部订单」＝`tabType: "1"`（包含已取消，取消单 `status=1500`）。采集程序会点「全部订单」。
- **外卖自营：** `sourceList: ["27","28","45","34"]`。
- **其它：** 请求里带 `login`、`loginName`（门店名）、`permissionCode`。

## 字段（金额单位都是「分」，时间都是毫秒时间戳）

### 列表 `data.orderList[]`

**`orderBase`**
- 订单标识：
  - `id`：详情用的 orderId，19 位，要按字符串处理；
  - `orderNo`：完整订单号，作去重键；
  - `pickupNo` / `makeNo`：取餐号、制作号，每天会重复，不能用来去重。
- 状态：`status` / `statusName`（如 300 已结账、1400 已完成）、`refundStatus`、`isPartRefund`、`partRefundCnt`。
- 来源：`source` / `sourceName`（扫码点餐、收银POS、美团外卖……）、`typeName`（堂食/外卖）、`businessTypeName`。
- 时间：`orderTime`、`checkoutTime`、`businessTime`（营业日，`yyyy/MM/dd`）。
- 金额：`amount`、`receivable`、`payed`、`income`、`discount`、`goodsTotalPrice`、`goodsDiscountTotalPrice`。
- 外卖费用：`serviceFee`（平台佣金）、`shippingFee`。
- 店内：`tableName`、`areaName`、`customerCount`。
- 其它：`comment`（整单备注）、`cashierName`、`poiId`、`orgCode`。

**`payList[]`**（店内单有，外卖单为 null）
- `payTypeName`（如 扫码支付-微信）、`payed`、`income`、`payNo`、`status`。

**`wm`**（外卖单）
- 结算：`settlement`、`finalSettlement`（商家实收）、`receivablePoi`。
- 费用：`boxFee`、`box`、`shipping`、`partRefundPrice`。
- 配送与标签：`shippingTypeName`、`poiFirstOrderName`、`confirmTime`。
- `recipientName`、`recipientAddress`、`recipientPhone`、`secretMobile` 是顾客信息，采集程序会打码。

### 详情 `data`

顶层键：`orderBase`、`itemList`、`payList`、`discountList`、`logList`、`vip`、`member`、`orderThirds`、`opLogList`。外卖单另有 `wm`、`serviceFee`、`serviceFeeTotal`、`boxFee`、`serviceFees`。

**菜品明细 `itemList[]`**

| 类别 | 字段 |
|---|---|
| 菜品标识 | `name`、`spuName`、`skuId`、`spuId`、`itemNo`、`cateId`（分类 ID，可对应菜品分类接口；外卖单为 0） |
| 规格、单位、数量 | `specs`（外卖如「280毫升」，店内多为空）、`unit`、`count`（小数）、`weight` |
| 价格 | `price`、`actualPrice`、`originalTotalPrice`、`totalPrice`、`newTotalPrice` |
| 收入与优惠 | `income`（外卖为扣佣后收入）、`discountAmount`、`discountItems[]`、`apportionPrice`、`memberPrice` |
| 套餐 | `isCombo`、`parentNo`、`parentItemNo`、`parentType`、`comboAddPrice` |
| 做法与备注 | `attrs`（做法/口味，JSON 字符串）、`comment`（单品备注）、`extra`（JSON 字符串） |
| 退菜、赠送、折扣、促销 | `retreat`、`reason`、`present`、`presentReason`、`discount`、`promotion`、`promotionName` |
| 其它 | `status`、`pack`（打包）、`orderTime`、`batchNo`（同一批下单） |

### 退款

- 原订单详情的 `refundOrderDetailVOs[].refundOrderBase` 字段：
  - `refundId`、`refundNo`
  - `refundType`：1 全额，2 部分
  - `originAmount`、`refundedAmount`、`refundExpense`、`refundIncome`
  - `refundReason`、`creatorName`、`createdTime`
- 这里的 `refundItemList` 为空；**退了哪道菜要看退款单详情**（`orders/refund/detail-pos`）：
  - `refundItemList[]` 有 `spuName`、`skuId`、`spuId`、`count`、`price`、`totalPrice`、`refundIncome`，以及 `itemNo`（与原订单 `itemList[].itemNo` 对应）
  - `refundPayList[]` 是原路退款的支付方式
- 店内部分退款时，原订单 `status` 仍是 300（已结账），`refundStatus` 仍为 0，只能靠 `refundOrderDetailVOs` 识别。
- 外卖整单取消时 `status=1500`、`refundStatus=2`。
- 店内「全部订单」列表里，退款单会单独占一行：`id` 就是 refundId，`orderNo` 以 88 开头，`status=30`「退款完成」，金额为负，`comment` 是退款原因。
- 这一行（也就是退款单的 refundId）不能用订单详情接口查，返回 `code=10001`，页面显示「查询结果为空」，要用退款单详情接口查。
- **日期切换（任意一天）：** 报表页是两个 ant-design 日期框（开始、结束，`input.ant-calendar-picker-input`）。
  - 弹层 `.ant-calendar-picker-container` 里，每天一个格子 `td[title='2026年9月27日']`，翻月用 `.ant-calendar-prev-month-btn`／`.ant-calendar-next-month-btn`，当前月份在 `.ant-calendar-ym-select`（如「2026年10月」）。
  - 弹层里的手输框被页面隐藏了，不能直接输入日期。
  - 选完开始日期后，页面会**自动弹出结束日期的日历**，这时再点结束框反而会把它关掉。
  - 弹层有展开动画，动画中点格子会失败。
  - 日期框的值是异步更新的，要等它变了再点「查询」。核对请求里 `startDate`、`endDate`（退款单列表在 `reqJson` 里）是不是那天的 0 点和 23:59:59.999（北京时间）。
  - 也有「今日／昨日／本周／本月」快捷按钮（`.ant-radio-button-wrapper`）。
- **补抓：** 2026-10-03 把开始日期设为 9/27 实测：9/27～10/1 五天（含跨月），每轮限 20 张详情，两轮补完，都记入 `coverage.json`。
- 采集程序遇到 `refundOrderDetailVOs` 就逐张打开退款单详情，存在订单文件的 `refunds` 里。

### 菜品库 `data.goods[]`（`filter-es`，每页 20 道，返回 `totalCount`、`totalPageCount`）

- **基本信息：** `id`（spuId）、`name`、`type`（10 单品 / 20 套餐）、`spuStatus`（1 在售）、`firstCategoryId/Name`、`secondCategoryId/Name`、`unitName`、`memo`、`detailMemo`、`tags[]`、`multimedias[]`（图片）、`letterMnemonicCode`
- **规格与价格** `poiSpuPriceTOs[]`：
  - `id`（skuId，对应订单明细的 `skuId`）、`specId`、`specName`
  - `price`、`basePrice`、`memberPrice`、`costPrice`、`barcodeList`
- **做法与加料：** `methods[]`、`sideSpus[]`、`methodGroupConfigs[]`、`sideSpuGroupConfigs[]`
- **套餐组成** `comboGroupTOS[]`：
  - 分组字段：`name`、`lowerCount`、`upperCount`
  - 分组里的 `skus[]`：`skuName`、`spuId`、`skuId`、`specName`、`salePrice`、`minAmount`、`maxAmount`、`requiredSku`
- **2026-10-03 实测：** 221 道（其中套餐 8 个、停售 90 道）。没有一道菜用了多规格、做法或加料，所以这些字段目前都为空。

## 打码规则（采集程序 `meituan_collector/sanitizer.py`）

- **整值替换为 `***` 的字段：** 字段名含 phone / mobile / tel / address / recipient / receiver / consignee / 经纬度的；以及「名字」类字段与 user / customer / nick / buyer / member / guest 同时出现的。
- **自由文本：** 备注等文本里的完整手机号替换为 `***`。例如外卖备注会带「收餐人隐私号 …」。
- **不打码的字段：** 以 `Id` / `No` / `Code` 结尾的编号（skuId、orderNo 等），以免 11 位编号被误判成手机号。

## 还没验证的（下一步）

1. **自动抓取退款单（已跑通）：** 2026-10-03 检查昨天时自动抓到一笔店内部分退款：`170549072610020012` 退「玛格丽特×1」49.00，原因「错点」；原订单状态仍是「已结账」。另外存了一份退款单行文件 `88170549072610020001`。检查范围、退款单列表、变化标志、历史版本的做法见采集程序 README。「内容变化」的检测已有单元测试，但还没在真实的订单变化上发生过。
2. **订单里的套餐、做法、加料、赠送：** 字段已确认存在，但当天的订单里都没有，要等出现后核对。
3. **订单列表翻页：** 当天每类都只有 1 页。翻页用的是与菜品库相同的 `saas-pagination-next`，已在菜品库实测连续翻完 12 页。
4. **登录有效期：** 要隔天、隔几天各观察一次。

## 运行方式（2026-10-03 起：Python 版）

程序在 `SnowmeetApi/Tools/meituan_collector/`（Python + Playwright），安装、自动启动和升级见该目录的 README。

- **适用环境：** 在有桌面、能弹出浏览器窗口的 Windows 或 macOS 上运行。
- **常驻：** `python -m meituan_collector serve`。
  - 浏览器一直开着、保持登录，调试端口为 127.0.0.1:9222。
  - 营业时段（默认 06:00–24:00）每 3 分钟抓一轮，其余时间每 60 分钟一轮；菜品档案每天抓一次。
  - 每轮在新标签页里抓，抓完关掉。
  - **不要关这个浏览器窗口。**
- **立即抓一轮：** `python -m meituan_collector once`。常驻开着时会连到同一个浏览器。
- **手动操作：** `python -m meituan_collector cmd <pages|goto|click|…>`；自检用 `python -m meituan_collector probe`。
- **与 C# 原型的一致性：** 最初用 C# 写过一版原型，2026-10-03 用同一天数据比对，结果完全一致——汇总表 17 单逐单一致，详情里的菜品、支付、优惠、金额、状态一致，菜品档案 221 道的规格、价格、套餐组成一致。比对后 C# 原型已删除。
- **开发机注意：** 在 Git Bash 里传 `/web/...` 这类路径参数会被改写成本地路径，要在 PowerShell 里执行。

## 网络（开发机）

- 开发机开着全局 VPN（StrongVPN，美国出口）。
- 采集程序配置 `"direct_interface": "Wi-Fi"`，浏览器从家里宽带直接出网（河北张家口联通），美团看到的是国内 IP。其它流量仍走 VPN，不影响用 Claude。
- 门店电脑不开 VPN，把这一项留空即可。
- 连通性自检：`python -m meituan_collector probe`。报告会写到 `out/probe/`，里面有浏览器的出口 IP 和登录状态。

## 企业微信提醒（2026-10-03 加）

企业微信接口有 IP 白名单，门店电脑发不了消息，所以分两段：门店电脑只上报心跳，提醒由服务器发。

- **采集程序（`meituan_collector/heartbeat.py`）：**
  - 每 5 分钟 `POST https://mini.snowmeet.top/api/MeituanCollector/Heartbeat`，状态一变就立即上报；
  - 请求头 `X-Collector-Token`；
  - 正文只有运行状态，不含订单和顾客信息：`status`（ok / running / need_login / error）、`seconds_since_last_round`、`last_round_ok`、`backfill_pending`、`machine`、`version`、`message`。
  - 用秒数而不是时间点，免得两边时钟不一致。刚启动、刚重新登录时，这个秒数从那一刻重新算。
- **服务器（SnowmeetApi）：**
  - `Controllers/Fnb/MeituanCollectorController.cs`：`Heartbeat`、`Status` 两个接口，令牌不对就返回 401。
  - `Services/Fnb/MeituanCollectorMonitor.cs`：
    - 登录失效：立即提醒，没恢复每 2 小时再提醒；
    - 20 分钟收不到心跳：提醒，没恢复每 6 小时再提醒；
    - 心跳正常但 2 小时没完成一轮：提醒；
    - 以上恢复后都发「已恢复」；
    - 状态存在 `meituan_collector_state.json`，发布重启不丢；
    - 后台每 5 分钟检查一次，服务启动后先等 6 分钟。
  - 消息经 `FnbWeComController.SendText`，用应用 1000009 发文本消息。
  - 工作目录下两份配置，不进 git：
    - `config.meituanCollectorToken`：令牌；
    - `config.meituanCollectorNotify`：接收人的企业微信 UserId，多人用 `|` 分隔。缺这个文件就不发。
- **没做的：**
  - 远程填验证码；
  - 连续出错提醒（程序在跑但每轮都报错时，服务器 `Status` 能看到 `error`，但不发提醒）。
