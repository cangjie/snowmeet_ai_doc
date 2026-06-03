---
name: export_retail_order_fiscal_year
description: 按店铺 + 财年口径从生产 SQL Server 导出年度零售（retail）订单到单 sheet 宽表 xlsx（财务/业务视角），并复用支付明细/支付流水后处理 + 对账。仿租赁/养护财年版规则，换成零售业务（order.type=零售，行项目 retail，无 charge_type/成本/数量/工序状态）。5 段拼接：固定前缀(财年/营非/运营日序号/支付退款汇总) + 动态支付区(每笔5列) + 动态退款区(每笔6列) + 固定中段(零售件数/销售额/招待件数/减免/分账/会员) + 固定后缀(订单号/结算/测试/临时单/正闭)。触发场景：「按财年导一份 xx 店铺零售订单」「导南山/万龙零售宽表」「财务要的年度零售大表」「零售数据导出」等。
---

# Export Retail Order (Fiscal Year) Skill

按店铺 + 财年从生产 SQL Server (`100.28.143.19/snowmeet_new`) 导出**年度零售订单**到**单 sheet 宽表** xlsx，规则**完全仿照租赁财年版** [`../export_rent_order_fiscal_year`](../export_rent_order_fiscal_year/SKILL.md) / 养护财年版 [`../export_care_order_fiscal_year`](../export_care_order_fiscal_year/SKILL.md)，换成零售（retail）业务。

## 零售 vs 租赁/养护 数据模型差异

| 维度 | 租赁 | 养护 | **零售（retail）** |
|---|---|---|---|
| `order.type` | 租赁 | 养护 | `零售` |
| biz_code | ZL | YH | `LS` |
| 行项目表 | rental+rental_detail+rent_item | care+care_task | **`retail`**（一单可多件商品） |
| 金额 | charge_type 分租金/超时/赔偿 | repair_charge+common_charge | **`retail.deal_price`**（实际成交价）；`sale_price` 生产恒 NULL，不取 |
| 数量/成本/工序 | — | care_task 工序 | **无** qty/cost/charge_type/工序状态 |
| 招待标记 | rental.entertain | care.entertain | **`retail.order_type`**∈{普通,招待} |
| 减免 | discount 三类去重 | discount(biz_type=养护) | `discount`(biz_type=零售)；**四店实测零售无任何 discount 记录，减免恒 0**（仍按口径保留列，未来稳） |
| 完成状态 | rentStatus 状态机 | care_task 末工序 | **无履约状态**，「订单状态」按订单级支付派生（已支付/未支付/空） |
| 行粒度 | 一行一订单 | 一行一订单 | 一行一订单（多件聚合，不展开逐件明细） |
| 支付/退款/分账 | 共用 | 共用 | **完全相同**（订单级共用表） |

## 何时触发

- 「按财年/年度导一份 xx 店铺零售订单」「财务要的年度零售大表」「导南山/万龙/崇礼零售宽表」

## 一次性环境准备

```bash
# Windows（本 skill 落地环境，已验证可跑）
pip install pyodbc openpyxl    # 需 "ODBC Driver 18 for SQL Server"
# 本机 python/python3 是 Microsoft Store 空壳，用 py 启动器跑
```

依赖 sibling 目录 `../export_rent_order/export_rent_orders.py`（import `SHOP_PREFIX/REFUND_COND/DEFAULT_CONN/write_sheet`，单点真理）。四个 export skill 目录的 sibling 关系不可破坏。

## 调用方式（两脚本工作流，顺序不可换）

```bash
cd snowmeet_ai_doc/skills/export_retail_order_fiscal_year
py export_retail_orders_fy.py --shop 南山 \
   --out /abs/path/snowmeet_ai_doc/nanshan_retail_orders_fy_2025-05-01_2026-04-30.xlsx
cd ../..
py add_payment_detail_sheet_to_fy_xlsx.py \
   --xlsx snowmeet_ai_doc/nanshan_retail_orders_fy_2025-05-01_2026-04-30.xlsx \
   --main-sheet 年度零售
py verify_payment_reconcile.py \
   --xlsx snowmeet_ai_doc/nanshan_retail_orders_fy_2025-05-01_2026-04-30.xlsx
```

> ⚠️ **两脚本依赖**：重跑第 1 步会重建整个 xlsx，必须紧接着重跑第 2 步，否则「支付明细/支付流水」两 sheet 丢失。

参数同租赁财年版（`--shop` 必填 / `--start` `--end` 默认 25-26 财年 / `--out` / `--conn` / `--include-invalid`）。`{prefix}` 复用 `SHOP_PREFIX`（万龙体验中心→wanlong / 万龙服务中心→wanlong_service / 崇礼旗舰店→chongli / 南山→nanshan）。`add_payment_detail_sheet_to_fy_xlsx.py` 传 `--main-sheet 年度零售`。

## 输出结构（单 sheet「年度零售」，5 段）

固定列 ＝ 段1(17) + 段4(15) + 段5(14) = 46；动态 ＝ maxPay×5 + maxRefund×4。

- **段1（17）**：业务(零售) / 财年 / 营/非 / 财年序号(空) / 运营日序号 / 日序号 / 月份 / 创建日期 / 创建时间 / 支付次数 / 支付合计 / 退款次数 / 退款合计 / 订单结余 / **订单状态(支付派生🔶)** / 最后退款日期 / 最后退款时间
- **段2（maxPay×5）/ 段3（maxRefund×6）**：照搬（共用支付/退款表）。段 3 每笔 6 列：日期/时间/金额/退款方式 / **退款账号**（微信→真实 mch_id / 支付宝→"支付宝" / 其他→空）/ **退款人**（pr.staff_id → staff.name）
- **段4（15，零售特化）**：零售件数(COUNT valid retail) / 销售额合计(SUM deal_price) / 招待件数(retail.order_type=招待 计数) / 减免合计(discount 表去重，零售口径) / 隐藏订单 / 应分账 / 实分账 / 待分账 / 业务(零售) / 门店 / 客户名称 / 电话 / 顾客openid / 收款方式 / 支付账号
- **段5（14，照搬）**：订单号 / 业务日期 / 业务时间 / 结算日期 / 结算时间 / 支付总金额 / 退款总金额 / 订单结余 / 店员姓名 / 店员openid / 测试 / 临时订单 / 客户名称 / 正/闭

照搬：财年、营/非(SEASON 雪季窗口)、日序号、测试(支付<5 或店员含「苍」)、临时订单(非测试+结余>0+无有效 retail)、正/闭(未支付且无招待 retail→关闭)、收款方式、顾客/店员 openid(两级偏好)、同订单号去重(有支付>valid>id)、`--include-invalid`、金额 round(2)+`0.00`。

## 关键口径说明（验收注意）

- **「订单状态」是简化派生🔶**：零售无履约/工序状态，按订单级支付派生 —— 无有效 retail 行→空（临时单候选）；支付合计>0→`已支付`；否则→`未支付`。非后端枚举，仅作业务标识。
- **`sale_price` 生产恒 NULL** → 不设「标价合计」列，金额只取 `deal_price`（实际成交价）。
- **零售减免恒 0**：四店实测 `discount` 表无任何 `order.type=零售` 关联记录；减免合计列按口径保留（order_id 或 biz_type=零售 biz_id∈retail.id 去重），值全 0，未来若启用零售券会自动生效。
- **销售额合计 ≠ 三表结余**：`销售额合计`=Σdeal_price（商品标的额）；`订单结余`=Σ支付−Σ退款。两者因招待/折让/部分支付可不等，属正常（已逐店验证 deal_price 聚合 vs DB 精确一致）。

## 已知问题排查

1. **ImportError: export_rent_orders** → sibling `../export_rent_order/export_rent_orders.py` 缺失/被移动。
2. **`pyodbc.drivers()` 无 Driver 18** → 未装 ODBC Driver 18。
3. **`python` 无输出 exit 49** → 用 `py` 启动器（python/python3 是 Store 空壳）。
4. **「支付明细/支付流水」不见了** → 重跑第 1 步后没重跑第 2 步。
5. **xlsx 写入 PermissionError** → 文件被 Excel/WPS 打开，关掉再跑。

## 文件清单

- [`SKILL.md`](SKILL.md)（本文档）
- [`export_retail_orders_fy.py`](export_retail_orders_fy.py) — 主导出脚本（仿财年版，retail 特化 SQL + derive_retail_status）

复用（非本目录）：`../../add_payment_detail_sheet_to_fy_xlsx.py`（`--main-sheet 年度零售`）、`../../verify_payment_reconcile.py`（`--xlsx`）、`../export_rent_order/export_rent_orders.py`（单点真理 import）。

## 变更记录

- 2026-05-18：初版。四店 25-26 财年（biz_date 2025-05-01~2026-04-30，默认 valid=1）实测，全部 **0 重复、0 分账、maxPay=1**，三表（年度零售Σ订单结余＝支付明细Σ支付结余＝支付流水按订单号汇总Σ交易金额）零差异、销售额合计 vs DB SUM(deal_price) 精确一致、营/非 与 SEASON 窗口 0 违例、行数 vs DB 精确：
  - **万龙体验中心** `wanlong_retail_orders_fy_*.xlsx`：55 列×186 行；maxRefund=1；销售额 ¥161,490.81；三表结余 ¥139,706.64（DB 支付 145,196.64 − 退款 5,490.00）；订单状态 已支付144/未支付42
  - **万龙服务中心** `wanlong_service_retail_orders_fy_*.xlsx`：51 列×31 行；maxRefund=0；销售额 ¥33,643.09；三表结余 ¥33,519.04；已支付25/未支付6
  - **崇礼旗舰店** `chongli_retail_orders_fy_*.xlsx`：55 列×261 行；maxRefund=1；销售额 ¥393,515.57；三表结余 ¥346,792.26；已支付204/未支付57
  - **南山** `nanshan_retail_orders_fy_*.xlsx`：55 列×497 行；maxRefund=1；销售额 ¥395,362.00；三表结余 ¥347,191.00；已支付468/未支付29；全 497 营业
