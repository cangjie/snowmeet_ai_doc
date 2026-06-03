---
name: export_care_order_fiscal_year
description: 按店铺 + 财年口径从生产 SQL Server 导出年度养护（care）订单到单 sheet 宽表 xlsx（财务/业务视角），并复用支付明细/支付流水后处理 + 对账。仿租赁财年版 export_rent_order_fiscal_year 规则，换成养护业务（order.type=养护，行项目 care+care_task，无押金/超时费/赔偿/charge_type）。5 段拼接：固定前缀(财年/营非/运营日序号/支付退款汇总) + 动态支付区(每笔5列) + 动态退款区(每笔4列) + 固定中段(养护件数/维修费/普通养护费/减免/分账/会员) + 固定后缀(订单号/结算/测试/临时单/正闭)。触发场景：「按财年导一份 xx 店铺养护订单」「导万龙服务中心养护宽表」「财务要的年度养护大表」「养护数据导出」等。
---

# Export Care Order (Fiscal Year) Skill

按店铺 + 财年从生产 SQL Server (`100.28.143.19/snowmeet_new`) 导出**年度养护订单**到**单 sheet 宽表** xlsx，规则**完全仿照租赁财年版** [`../export_rent_order_fiscal_year`](../export_rent_order_fiscal_year/SKILL.md)，换成养护（care）业务。面向财务/业务汇报，非对账。

## 养护 vs 租赁数据模型差异

| 维度 | 租赁（rental） | **养护（care）** |
|---|---|---|
| `order.type` | `租赁` | `养护` |
| 店铺 | 万龙体验中心… | **万龙养护单 shop=`万龙服务中心`**（`ReceptController` 自动改写「养护下单+万龙体验中心」→「万龙服务中心」） |
| 行项目表 | `rental` + `rental_detail` + `rent_item` | `care`（一张订单可多块送修板）+ `care_task`（工序流水） |
| 收费 | charge_type 分 租金/超时费/赔偿金 | `repair_charge` + `common_charge`；减免 `discount` + `ticket_discount` |
| 押金/超时/赔偿 | 有 | **无** |
| 完成状态 | rental.settled/closed 状态机 | `care.finish` **生产恒 0**；真状态在 `care_task` 工序（最后一条 task=`发板`/`强行索回` → 已完成） |
| 行粒度 | 一行一订单 | 一行一订单（多块养护聚合，**不展开逐块明细**——用户已确认） |
| 支付/退款/分账/减免 | order_payment / payment_refund / discount / order_share / payment_share | **完全相同**（订单级共用表） |

> ⚠️ 与租赁财年版**日期口径相同**（按 `order.biz_date` 过滤），但业务不同，不可交叉对账。

## 何时触发

- 「按财年/年度导一份 xx 店铺养护订单」「财务要的年度养护大表」「导万龙服务中心养护宽表」
- 用户提到 **养护 / care / 财年 / 营非 / 运营日序号 / 维修费 / 普通养护费 / 服务项目** 等

## 一次性环境准备

```bash
# Windows（本 skill 落地环境，已验证可跑）
pip install pyodbc openpyxl
# 需已安装 "ODBC Driver 18 for SQL Server"（验证：py -c "import pyodbc;print(pyodbc.drivers())"）
# 注意本机 python/python3 是 Microsoft Store 空壳，用 py 启动器跑

# macOS（如换机）
brew install unixodbc msodbcsql18
pip3 install pyodbc openpyxl
export ODBCSYSINI=/opt/homebrew/etc
```

依赖 sibling 目录 `../export_rent_order/export_rent_orders.py`（import 复用 `SHOP_PREFIX / REFUND_COND / DEFAULT_CONN / write_sheet`，单点真理）。**三个 skill 目录的 sibling 关系不可破坏**，否则 ImportError。

## 调用方式（两脚本工作流，顺序不可换）

```bash
cd snowmeet_ai_doc/skills/export_care_order_fiscal_year
# 1) 主表「年度养护」
py export_care_orders_fy.py --shop 万龙服务中心 \
   --out /abs/path/snowmeet_ai_doc/wanlong_service_care_orders_fy_2025-05-01_2026-04-30.xlsx

# 2) 追加「支付明细」「支付流水」（复用租赁版后处理，传 --main-sheet 年度养护）
cd ../..
py add_payment_detail_sheet_to_fy_xlsx.py \
   --xlsx snowmeet_ai_doc/wanlong_service_care_orders_fy_2025-05-01_2026-04-30.xlsx \
   --main-sheet 年度养护

# 3) 只读对账校验（复用，sheet 名不变零改动）
py verify_payment_reconcile.py \
   --xlsx snowmeet_ai_doc/wanlong_service_care_orders_fy_2025-05-01_2026-04-30.xlsx
```

> ⚠️ **两脚本依赖**：每次重跑第 1 步会重建整个 xlsx，必须紧接着重跑第 2 步，否则「支付明细/支付流水」两 sheet 丢失（与租赁财年版同坑）。

参数（同租赁财年版）：

```
--shop   必填，店铺中文名（DB order.shop，养护一般是「万龙服务中心」）
--start  业务日期 biz_date 起（inclusive），默认 2025-05-01
--end    业务日期 biz_date 止（inclusive），默认 2026-04-30
--out    输出 xlsx 路径，默认 {prefix}_care_orders_fy_{start}_{end}.xlsx
--conn   ODBC 连接串，默认连生产（复用 ../export_rent_order/DEFAULT_CONN）
--include-invalid  导出 order 不论 valid（默认仅 valid=1）；仅放宽 order 表
```
`{prefix}` 复用 `SHOP_PREFIX`（万龙服务中心→`wanlong_service`）。
`add_payment_detail_sheet_to_fy_xlsx.py` 新增 `--main-sheet`（默认 `年度租赁`，养护传 `年度养护`），向后兼容、不影响租赁。

## 输出结构（单 sheet「年度养护」，5 段，63 列实测）

固定列 ＝ 段1(17) + 段4(18) + 段5(14) = 49；动态 ＝ maxPay×5 + maxRefund×4。

- **段1 固定前缀（17）**：业务(养护) / 财年 / 营/非 / 财年序号(空) / 运营日序号 / 日序号 / 月份 / 创建日期 / 创建时间 / 支付次数 / 支付合计 / 退款次数 / 退款合计 / 订单结余 / **订单状态(养护近似)** / 最后退款日期 / 最后退款时间
- **段2 动态支付（maxPay×5）**：【支付k】日期/时间/金额/支付方式/支付账号（微信→真实 mch_id）
- **段3 动态退款（maxRefund×6）**：【退款k】日期/时间/金额/退款方式（=原支付通道）/ 退款账号（微信→真实 mch_id / 支付宝→"支付宝" / 其他→空）/ 退款人（pr.staff_id → staff.name）
- **段4 固定中段（18，养护特化）**：养护件数 / 维修费合计(SUM repair_charge) / 普通养护费合计(SUM common_charge) / 减免合计(discount 表去重) / 卡券减免合计(SUM care.ticket_discount) / 养护直减合计(SUM care.discount) / 服务项目(修刃·打蜡·去蜡·维修，need_* 聚合) / 隐藏订单 / 应分账金额 / 实分账金额 / 待分账金额 / 业务(养护) / 门店 / 客户名称 / 电话 / 顾客openid / 收款方式 / 支付账号
- **段5 固定后缀（14，照搬租赁）**：订单号 / 业务日期 / 业务时间 / 结算日期 / 结算时间 / 支付总金额 / 退款总金额 / 订单结余 / 店员姓名 / 店员openid / 测试 / 临时订单 / 客户名称 / 正/闭

照搬租赁财年版：财年、营/非（SEASON 雪季窗口）、运营日序号、日序号、测试(支付<5 或店员含「苍」)、临时订单(非测试+结余>0+无有效 care)、正/闭(未支付且非招待→关闭)、收款方式(最大笔)、顾客/店员 openid(店员两级偏好)、同订单号去重(有支付>valid>id)、`--include-invalid`、金额 round(2)+`0.00`。

## 减免合计（订单级，养护口径）

`discount` 表（`valid=1`）以下两类记录**按 discount.id 去重后** SUM：
1. `discount.order_id = 当前订单 id`
2. `discount.biz_type=N'养护'` AND `discount.biz_id ∈ {该订单 valid=1 care 的 id}`

（养护无 rental_detail 叶层，去掉租赁版第 3 路 sub_biz）。另：`care.discount`（养护直减合计）/`care.ticket_discount`（卡券减免合计）是 care 行自带的并行台账，与 discount 表**不完全相等**（万龙服务中心 25-26 实测 discount 表 ¥138,997 vs SUM(care.discount) ¥139,827，相差约 ¥830），故三列并存，按需取用。

## 「订单状态」是近似值（验收注意）

`care.finish` 生产**恒为 0**，完成真信号在 `care_task` 工序。本 skill 复刻 `Care.cs` 计算属性 `status`：每块 care 取最后一条 `care_task`（`valid=1`，`ORDER BY id DESC`）的 `task_name`，∈`(发板,强行索回)`→该 care 已完成；无 task→未开始；否则进行中。订单级聚合：全完成→`已完成`、全未开始→`未开始`、0 完成有进行→`进行中`、部分完成→`部分完成`、无有效 care→空。⚠️ 近似，使用前抽样验收。

## 已知问题排查

1. **ImportError: export_rent_orders** → sibling 目录 `../export_rent_order/export_rent_orders.py` 缺失/被移动。
2. **`pyodbc.drivers()` 无 Driver 18** → 未装 ODBC Driver 18（Windows）/ macOS 未 `export ODBCSYSINI`。
3. **`python` 无输出 exit 49** → 本机 Windows，用 `py` 启动器（python/python3 是 Store 空壳）。
4. **「支付明细/支付流水」不见了** → 重跑第 1 步后没重跑第 2 步（两脚本依赖）。
5. **verify 报 GBK UnicodeEncodeError** → 已修（脚本头加 `sys.stdout.reconfigure('utf-8')`）。
6. **xlsx 写入 PermissionError** → 文件被 Excel/WPS 打开，关掉再跑。
7. **某订单金额存疑** → pyodbc 只读直查 `[order]`/`care`/`care_task`/`order_payment` 按 code 核对。

## 文件清单

- [`SKILL.md`](SKILL.md)（本文档）
- [`export_care_orders_fy.py`](export_care_orders_fy.py) — 主导出脚本（仿租赁财年版，care 特化 SQL + derive_care_status + 服务项目派生）

复用（非本目录）：`../../add_payment_detail_sheet_to_fy_xlsx.py`（加了 `--main-sheet`）、`../../verify_payment_reconcile.py`（加了 utf-8 头）、`../export_rent_order/export_rent_orders.py`（单点真理 import）。

## 变更记录

- 2026-05-18：初版。万龙服务中心 25-26 财年（biz_date 2025-05-01~2026-04-30，默认 valid=1）实测：**63 列 × 4601 行**（DB valid+code非空 4602，去重 1 个重复 code `WF_YH_251110_00017` → 4601）；maxPay=2 / maxRefund=1 / order_share=0（无分账，同崇礼/南山形态）。`verify_payment_reconcile.py` 口径A/B 均 **0 单不一致**，支付 ¥740,216.52 / 退款 ¥4,260.00 / 最终 ¥735,956.52 三表零差异；段2/段3 逐笔加总 == 段1 合计 0 偏差；营/非 与 SEASON 窗口 100% 自洽（6 单非营业）；订单状态 已完成 3607 / 未开始 354 / 进行中 53 / 空(无care) 587。列合计 vs DB 仅差被去重的那 1 单（care_cnt −2 / 维修 −10 / 普通 −400 / 减免 −409.98，全额可溯）。「订单状态」为 SQL 近似（care.finish 恒 0，走 care_task 工序），「财年序号」按租赁版惯例留空。
- 2026-05-18：南山 25-26 财年同法导出：**54 列 × 86 行**（DB valid+code非空 86，0 重复，0 去重）；maxPay=1 / maxRefund=0 / order_share=0（无退款无分账，动态退款列自适应省略）。`verify_payment_reconcile.py` 口径A/B 均 0 单不一致；三表 Σ 全部 ¥7,800.00 一致；段2 单笔==支付合计 0 偏差；营/非 全 86 营业（全 biz_date 落雪季窗口，0 违例）；订单状态 已完成 67 / 未开始 18 / 进行中 1。**0 重复单 → 列合计 vs DB 完全相等**（减免/直减各 259.99、维修 720、普通 10050、件数 92 均精确吻合）。产物 `snowmeet_ai_doc/nanshan_care_orders_fy_2025-05-01_2026-04-30.xlsx`。
- 2026-05-18：崇礼旗舰店 25-26 财年同法导出：**54 列 × 26 行**（DB valid+code非空 26，0 重复，0 去重）；maxPay=1 / maxRefund=0 / order_share=0。`verify_payment_reconcile.py` 口径A/B 均 0 单不一致；三表 Σ 全部 ¥4,000.01 一致；段2 单笔==支付合计 0 偏差；营/非 全 26 营业（0 违例）；订单状态 已完成 20 / 未开始 3 / 空(无care) 3。**0 重复单 → 列合计 vs DB 完全相等**（减免/直减各 380、维修 1420、普通 3300、件数 28 均精确吻合）。产物 `snowmeet_ai_doc/chongli_care_orders_fy_2025-05-01_2026-04-30.xlsx`。
