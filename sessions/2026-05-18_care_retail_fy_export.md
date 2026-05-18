# 2026-05-18 养护+零售财年导出 skill：仿租赁财年版新建两条业务线导出，养护3店+零售4店全量导出并三表对账闭合

接续 5-13~5-17 的多店数据导出线（租赁财年版已收尾）。本场会话产出两个新 sibling skill（`export_care_order_fiscal_year`、`export_retail_order_fiscal_year`），导出养护 3 店 + 零售 4 店共 7 份 xlsx，全部三表零差异。改动落在 `snowmeet_ai_doc/`（新 skill 目录 + 2 个复用脚本小改）。

## 1. 背景与规划

### 1.1 start-work（plan mode）→ 养护导出规划

- 会话以 `/start-work` 开始（plan mode）。只读校验本地 `main` HEAD = 远端 `0b6f364`，上下文最新
- 用户选定方向："继续导出各店其它业务数据，今天先仿照昨天前天规则，导出万龙服务中心的养护数据"
- 3 个 Explore agent 并行探查：①租赁财年版规则提取 ②养护后端数据模型 ③养护 DB/订单表落地

### 1.2 两口径经 AskUserQuestion 确认（用户原话）

- **行粒度**："暂时只看订单，不用看逐个雪板的养护明细" → 一行一订单（多块 care 聚合）
- **营/非**："照搬租赁营/非" → 复刻 SEASON 雪季窗口；非雪季养护单落窗口外→非营业（设计预期）
- 其余列规格按"基线推断填草稿 + 用户纠偏"，不逐列追问

## 2. 探查关键发现（DB 只读 probe）

### 2.1 养护（care）数据模型

- 行项目 `care`（[Table("care")]，一单可多块送修板）+ `care_task`（工序流水）；**无** rental_detail/charge_type/押金/超时/赔偿
- `order.type=N'养护'`，biz_code `YH`；万龙养护单 `shop='万龙服务中心'`（`ReceptController` 把"养护下单+万龙体验中心"自动改写过去）
- 毛费 = `repair_charge + common_charge`；减免 `discount`(biz_type=N'养护', 同时填 order_id + biz_id=care.id) + care 行自带 `discount`/`ticket_discount`
- **`care.finish` 生产恒为 0**（4394/4394）→ 完成真信号在 `care_task` 最后一条工序：`发板`/`强行索回` → 已完成（复刻 `Care.cs` 计算属性 `status`）
- `care.biz_type` 多为 NULL（4197），仅 197 `非雪季养护`
- 万龙服务中心：4605 养护单，order_share=0（无分账，同崇礼/南山形态）

### 2.2 零售（retail）数据模型

- 行项目 `retail`（[Table("retail")]，一单可多件）；`order.type=N'零售'`，biz_code `LS`
- 金额取 `retail.deal_price`（实际成交价）；**`sale_price` 生产 100% NULL** → 弃用"标价合计"列
- 无 charge_type/成本/数量/工序状态；`retail.order_type ∈ {普通958, 招待17}`
- **四店零售 `discount` 表无任何关联记录** → 减免恒 0（仍按口径保留列，未来零售券自动生效）
- 四店均 0 重复 0 分账 maxPay=1：万龙体验186/万龙服务31/崇礼261/南山497

## 3. 养护财年导出 skill

新建 [`skills/export_care_order_fiscal_year/export_care_orders_fy.py`](../skills/export_care_order_fiscal_year/export_care_orders_fy.py) + SKILL.md。以租赁财年版 `export_rent_orders_fy.py` 为模板，sibling import `../export_rent_order` 的 `SHOP_PREFIX/REFUND_COND/DEFAULT_CONN/write_sheet`。克隆点改动：

- `ORDER_FILTER` type=N'养护'；`SHEET_TITLE='年度养护'`
- 删 rental_detail 的 `ot`/`rc` join → 换 `ca`（care 聚合：件数/repair_sum/common_sum/care_disc/ticket_disc/need_* 并集 MAX）+ `cs`（订单级状态：每块 care `OUTER APPLY` 取最后一条 valid care_task）
- 减免合计：`discount.order_id=o.id OR (biz_type=N'养护' AND biz_id∈本单 care.id)`，按 discount.id 去重 SUM
- `derive_care_status`：全完成→已完成 / 全无 task→未开始 / 0完成有进行→进行中 / 部分→部分完成 / 无 care→空
- 段4 加 🆕 养护件数/服务项目(need_* 并集 修刃·打蜡·去蜡·维修)/卡券减免合计/养护直减合计；`_entertain`=order.entertain OR care.entertain
- 照搬：财年/营非/SEASON/运营日序号/日序号/测试/临时订单/正闭/收款方式/openid 两级偏好/同 code 去重

## 4. 后处理参数化 + verify utf-8 修复

- [`add_payment_detail_sheet_to_fy_xlsx.py`](../add_payment_detail_sheet_to_fy_xlsx.py)：加 `--main-sheet`（默认`年度租赁`，向后兼容），`read_order_codes` 收参；养护/零售传 `--main-sheet 年度养护/年度零售`。支付明细/支付流水/对账脚本本就按主 sheet 订单号取数、与 order.type 无关，**零重写复用**
- [`verify_payment_reconcile.py`](../verify_payment_reconcile.py)：补 `import sys` + `sys.stdout.reconfigure('utf-8')`（与同族脚本一致），修 Windows GBK 控制台对 ✓ 的 `UnicodeEncodeError`（脚本逻辑本就正确，仅末行打印崩）

## 5. 万龙服务中心养护导出 + 重复单详查

- 产物 `wanlong_service_care_orders_fy_2025-05-01_2026-04-30.xlsx`：63 列 × 4601 行（DB valid+code 4602，去重 1 个重复 code `WF_YH_251110_00017` → 4601）；maxPay=2/maxRefund=1/无分账
- 三表 ¥735,956.52 零差异；段2/段3 逐笔==段1 合计 0 偏差；营/非 与 SEASON 100% 自洽（6 单非营业）；订单状态 已完成3607/未开始354/进行中53/空587
- 列合计 vs DB 仅差被去重那 1 单（care_cnt−2/维修−10/普通−400/减免−409.98 全额可溯）
- **重复单 `WF_YH_251110_00017` 详查**（用户要求）：双胞胎 id=61535/61536，create_date 仅差 60ms（`GenerateOrderCode` 序号竞态），各自带独立 2 care + 2 discount，净额≈¥0.02，0 支付，店员"苍杰（个人）"测试单。去重保留 id 大者 61536（paycnt/valid 并列→id 最大）。即便不去重也被`测试=是`标出、结余 0 不影响对账

## 6. 服务项目列实现说明（用户追问"服务项目你是怎么写的"）

- 源数据 = care 表 4 个 `need_*` 整型标志位（**非** Care.cs 的 SkiService/BoardService 枚举，**未含** free_wax）
- SQL：`ca` 子查询对一单所有 valid care 取 `MAX(CASE need_x=1)` = 并集/OR
- Python：`SERVICE_LABELS=[(_f_edge,修刃),(_f_wax,打蜡),(_f_unwax,去蜡),(_f_repair,维修)]`，`·` 拼接
- 已明确告知用户：标签是推断口径（need_wax 实际可能是热蜡/机打蜡；need_unwax 工序名其实叫刮蜡），并集不带数量/不分块；如需更细可改 care_task 工序集合口径

## 7. 南山/崇礼养护导出 + 三店复核

- 南山 `nanshan_care_orders_fy_*.xlsx`：54×86，0 重复，三表 ¥7,800.00，列合计 vs DB 完全相等，已完成67/未开始18/进行中1
- 崇礼 `chongli_care_orders_fy_*.xlsx`：54×26，0 重复，三表 ¥4,000.01，列合计 vs DB 完全相等，已完成20/未开始3/空3
- 三店复核：每个 xlsx 年度养护Σ订单结余 ＝ 支付明细Σ支付结余 ＝ 支付流水按订单号汇总Σ交易金额，两两差≤1分；年度养护两个「订单结余」列逐行相等

## 8. 零售财年导出 skill + 四店导出 + 复核

- 新建 [`skills/export_retail_order_fiscal_year/export_retail_orders_fy.py`](../skills/export_retail_order_fiscal_year/export_retail_orders_fy.py) + SKILL.md。retail 特化：`re` join（COUNT/SUM deal_price/招待件数）；减免 discount(biz_type=N'零售')去重；`derive_retail_status`（无工序→支付派生：空/已支付/未支付）；段4=零售件数/销售额合计/招待件数/减免合计/分账/会员（46 固定列）；`_entertain`=order.entertain OR retail.order_type=招待
- 四店 25-26 导出全部 0 重复/0 分账/maxPay=1，三表零差异、销售额合计 vs DB SUM(deal_price) 精确一致、行数 vs DB 精确、营/非 0 违例：
  - 万龙体验中心 55×186，销售额 ¥161,490.81，三表结余 ¥139,706.64（DB支付145,196.64−退款5,490）
  - 万龙服务中心 51×31，销售额 ¥33,643.09，三表结余 ¥33,519.04
  - 崇礼旗舰店 55×261，销售额 ¥393,515.57，三表结余 ¥346,792.26
  - 南山 55×497，销售额 ¥395,362.00，三表结余 ¥347,191.00（全 497 营业）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `skills/export_care_order_fiscal_year/{export_care_orders_fy.py,SKILL.md}` | 新建：养护财年导出 skill |
| `skills/export_retail_order_fiscal_year/{export_retail_orders_fy.py,SKILL.md}` | 新建：零售财年导出 skill |
| `add_payment_detail_sheet_to_fy_xlsx.py` | 加 `--main-sheet`（默认年度租赁，向后兼容），`read_order_codes` 收参 |
| `verify_payment_reconcile.py` | 补 `sys.stdout.reconfigure('utf-8')`，修 Windows GBK 崩溃 |
| `wanlong_service_care_orders_fy_*.xlsx` | 产物：万龙服务中心养护 63×4601 |
| `nanshan_care_orders_fy_*.xlsx` / `chongli_care_orders_fy_*.xlsx` | 产物：南山/崇礼养护 |
| `wanlong_retail_orders_fy_*.xlsx` / `wanlong_service_retail_orders_fy_*.xlsx` | 产物：万龙体验/服务零售 |
| `chongli_retail_orders_fy_*.xlsx` / `nanshan_retail_orders_fy_*.xlsx` | 产物：崇礼/南山零售 |

## 学到的小知识

1. **`care.finish` 生产恒为 0**：养护完成真信号在 `care_task` 最后一条工序（`发板`/`强行索回`→已完成）。DB schema 有 finish 字段但业务不写，状态须走 care_task。改/对账养护状态前必须看 care_task 而非 care.finish
2. **`care.biz_type` 多为 NULL**：仅少量 `非雪季养护`；它不是 discount.biz_type（后者对养护单恒填 `养护`，且 order_id+biz_id=care.id 同填）
3. **`retail.sale_price` 生产 100% NULL**：零售金额唯一可信源是 `deal_price`（实际成交价）。导零售勿取 sale_price
4. **零售/养护减免口径不同**：养护 discount 表有记录（biz_type=养护）；四店零售 discount 表零记录（减免恒 0）。脚本按 order_id OR biz_type+biz_id 去重，自适应
5. **`add_payment_detail`/`verify_payment_reconcile` 与 order.type 无关**：按主 sheet 订单号取数，只需 `--main-sheet` 参数化即可跨业务复用，无须为每业务克隆——单点真理延伸
6. **Windows `python` 是 Microsoft Store 空壳**（exit 49 无输出），必须用 `py` 启动器；pyodbc 5.3.0 + ODBC Driver 18 已就绪，DEFAULT_CONN 直连生产 OK，CLAUDE.md 的 macOS ODBC 笔记不适用 Windows
7. **`GenerateOrderCode` 序号竞态对每个业务都存在**：养护万龙服务中心命中 1 个重复 code（≈¥0.02 测试单双插）；去重规则"有支付>valid=1>id 最大"通用，财务影响 0
8. **三表对账闭环可复用到任意业务**：年度{业务}Σ订单结余 ＝ 支付明细Σ支付结余 ＝ 支付流水按订单号汇总Σ交易金额；养护 3 店 + 零售 4 店共 7 份全部 ≤1 分一致
