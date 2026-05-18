---
name: export_ski_pass_order_fiscal_year
description: 按店铺 + 财年口径从生产 SQL Server 导出年度雪票（ski_pass）订单到单 sheet 宽表 xlsx（财务/业务视角），仿零售财年版规则，换成雪票业务（order.type=雪票，行项目 ski_pass，无charge_type/成本/工序状态）。5 段拼接：固定前缀(财年/营非/运营日序号/支付退款汇总) + 动态支付区(每笔5列) + 动态退款区(每笔4列) + 固定中段(雪票张数/成交价/度假区分布/减免/分账/会员) + 固定后缀(订单号/结算/测试/临时单/正闭)。触发场景：「按财年导一份 xx 店铺雪票订单」「导崇礼/万龙/南山雪票宽表」「财务要的年度雪票大表」「雪票数据导出」等。
---

# Export Ski Pass Order (Fiscal Year) Skill

按店铺 + 财年从生产 SQL Server (`100.28.143.19/snowmeet_new`) 导出**年度雪票订单**到**单 sheet 宽表** xlsx，规则**完全仿照零售财年版** [`../export_retail_order_fiscal_year`](../export_retail_order_fiscal_year/SKILL.md)，换成雪票（ski_pass）业务。

## 雪票 vs 零售 数据模型差异

| 维度 | 零售 (retail) | **雪票（ski_pass）** |
|---|---|---|
| `order.type` | `零售` | `雪票` |
| 行项目表 | `retail` | **`ski_pass`** |
| 金额 | `retail.deal_price` | **`ski_pass.deal_price`** |
| 数量单位 | 件数 | **张数** |
| 品类/度假区 | 无 | **`resort` 字段（南山/万龙）** |
| 招待标记 | `retail.order_type`∈{普通,招待} | 无（可通过 `order.pay_option` 推断） |
| 成本字段 | 无 | **`ticket_price`（票面价），可含差价** |
| 行粒度 | 一行一订单 | 一行一订单（多张票聚合，不展开明细） |
| 支付/退款/分账 | 共用 | **完全相同**（订单级共用表） |

## 何时触发

- 「按财年/年度导一份 xx 店铺雪票订单」「财务要的年度雪票大表」「导崇礼/万龙/南山雪票宽表」

## 一次性环境准备

```bash
# Windows（本 skill 落地环境，已验证可跑）
pip install pyodbc openpyxl    # 需 "ODBC Driver 18 for SQL Server"
# 本机 python/python3 是 Microsoft Store 空壳，用 py 启动器跑
```

依赖 sibling 目录 `../export_rent_order/export_rent_orders.py`（import `SHOP_PREFIX/REFUND_COND/DEFAULT_CONN/write_sheet`，单点真理）。四个 export skill 目录的 sibling 关系不可破坏。

## 调用方式（两脚本工作流，顺序不可换）

```bash
cd snowmeet_ai_doc/skills/export_ski_pass_order_fiscal_year
py export_ski_pass_orders_fy.py --shop 崇礼旗舰店 \
   --out /abs/path/snowmeet_ai_doc/chongli_ski_pass_orders_fy_2025-05-01_2026-04-30.xlsx
cd ../..
py add_payment_detail_sheet_to_fy_xlsx.py \
   --xlsx snowmeet_ai_doc/chongli_ski_pass_orders_fy_2025-05-01_2026-04-30.xlsx \
   --main-sheet 年度雪票
py verify_payment_reconcile.py \
   --xlsx snowmeet_ai_doc/chongli_ski_pass_orders_fy_2025-05-01_2026-04-30.xlsx
```

> ⚠️ **两脚本依赖**：重跑第 1 步会重建整个 xlsx，必须紧接着重跑第 2 步，否则「支付明细/支付流水」两 sheet 丢失。

参数同零售财年版（`--shop` 必填 / `--start` `--end` 默认 25-26 财年 / `--out` / `--conn` / `--include-invalid`）。`{prefix}` 复用 `SHOP_PREFIX`（万龙体验中心→wanlong / 万龙服务中心→wanlong_service / 崇礼旗舰店→chongli / 南山→nanshan）。`add_payment_detail_sheet_to_fy_xlsx.py` 传 `--main-sheet 年度雪票`。

## 输出结构（单 sheet「年度雪票」，5 段）

固定列 ＝ 段1(17) + 段4(16) + 段5(14) = 47；动态 ＝ maxPay×5 + maxRefund×4。

- **段1（17）**：业务(雪票) / 财年 / 营/非 / 财年序号(空) / 运营日序号 / 日序号 / 月份 / 创建日期 / 创建时间 / 支付次数 / 支付合计 / 退款次数 / 退款合计 / 订单结余 / **订单状态(支付派生🔶)** / 最后退款日期 / 最后退款时间
- **段2（maxPay×5）/ 段3（maxRefund×4）**：照搬（共用支付/退款表）
- **段4（16，雪票特化）**：雪票张数(COUNT ski_pass) / 成交价合计(SUM deal_price) / 万龙张数 / 南山张数 / 减免合计(discount 表去重，雪票口径) / 隐藏订单 / 应分账 / 实分账 / 待分账 / 业务(雪票) / 门店 / 客户名称 / 电话 / 顾客openid / 收款方式 / 支付账号
- **段5（14，照搬）**：订单号 / 业务日期 / 业务时间 / 结算日期 / 结算时间 / 支付总金额 / 退款总金额 / 订单结余 / 店员姓名 / 店员openid / 测试 / 临时订单 / 客户名称 / 正/闭

照搬：财年、营/非(SEASON 雪季窗口)、日序号、测试(支付<5 或店员含「苍」)、临时订单(非测试+结余>0+无有效 ski_pass)、正/闭(支付=0→关闭，否则正常)、收款方式、顾客/店员 openid(两级偏好)、同订单号去重(有支付>valid>id)、`--include-invalid`、金额 round(2)+`0.00`。

## 关键口径说明（验收注意）

- **「订单状态」是简化派生🔶**：雪票无工序/履约状态，按订单级支付派生 —— 无有效 ski_pass 行→空（临时单候选）；支付合计>0→`已支付`；否则→`未支付`。非后端枚举，仅作业务标识。
- **度假区标记**：`ski_pass.resort` 字段（南山/万龙）允许同一订单混合多个度假区的票，报表分别计数展示。
- **雪票张数 ≠ 三表结余**：`雪票张数`=COUNT(有效 ski_pass)；`订单结余`=Σ支付−Σ退款。两者因部分支付可不等，属正常。
- **成交价合计 vs 票面价**：报表取 `SUM(deal_price)`（实际成交价），与后端订单字段对应。`ticket_price`（票面价）可用于财务差异分析，但不在报表主体展示。
- **减免恒 0 or 有值**：`discount` 表 `biz_type=雪票` 或 `order_id` 直接关联；取决于业务是否启用了雪票券/优惠。列按口径保留，值自动反映数据。

## 已知问题排查

1. **ImportError: export_rent_orders** → sibling `../export_rent_order/export_rent_orders.py` 缺失/被移动。
2. **`pyodbc.drivers()` 无 Driver 18** → 未装 ODBC Driver 18。
3. **`python` 无输出 exit 49** → 用 `py` 启动器（python/python3 是 Store 空壳）。
4. **「支付明细/支付流水」不见了** → 重跑第 1 步后没重跑第 2 步。
5. **xlsx 写入 PermissionError** → 文件被 Excel/WPS 打开，关掉再跑。

## 文件清单

- [`SKILL.md`](SKILL.md)（本文档）
- [`export_ski_pass_orders_fy.py`](export_ski_pass_orders_fy.py) — 主导出脚本（仿零售版，ski_pass 特化 SQL + derive_skipass_status）

复用（非本目录）：`../../add_payment_detail_sheet_to_fy_xlsx.py`（`--main-sheet 年度雪票`）、`../../verify_payment_reconcile.py`（`--xlsx`）、`../export_rent_order/export_rent_orders.py`（单点真理 import）。

## 变更记录

- 2026-05-18：初版。崇礼旗舰店 25-26 财年（biz_date 2025-05-01~2026-04-30，默认 valid=1）首次导出。
