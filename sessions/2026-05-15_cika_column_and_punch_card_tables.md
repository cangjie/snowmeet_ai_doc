# 2026-05-15 财年导出加「次卡」列 + 次卡相关表勘察

接续 2026-05-15 白天的财年版租赁导出工作（`wanlong_rent_orders_fy_2025-05-01_2026-04-30.xlsx`，2428 行 × 98 列）。本场会话三条主线：用户反馈昨日导出"数据不准"待澄清；勘察 DB 里和「次卡」相关的所有表；给现有 xlsx 加一列「次卡」标识。

---

## 1. 用户反馈昨日导出数据不准

- 用户上来直说「今天你做的导出数据，表现太差了！」+「数据不准 / 金额对不上」
- 我连提两轮 AskUserQuestion 想细化是哪类金额（实收/退款/减免/租金赔偿/超时费）和验证口径（手动 SQL/对账版/单单核对），用户 dismiss 让等下次具体指示
- 本场未继续这条线，留给后续会话

📌 **结论**：用户的"数据不准"指向不明，先封存。后续推进时第一件事问清是哪个订单号或哪类金额，再回脚本去查。

---

## 2. 数据库里和「次卡」相关的表

用户问「看一下数据库，和次卡相关的表有哪些」。DB 直查（`INFORMATION_SCHEMA.TABLES` LIKE `%card%`/`%ticket%`/`%pass%`/`%punch%`）+ 列名 LIKE 命中 + 字符串 LIKE `%次卡%` 三路盘查。

### 2.1 核心：次卡专用表

| 表 | 行数 | 字段（关键） |
|---|---:|---|
| `punch_card` | 36 | id / biz_type / card_name / member_id / mi7_code / **total** / **punches** / create_date / update_date |
| `punch_card_used` | **0** | id / card_id / order_id / biz_type / biz_id / payment_id / **punch_count** / valid |

- `punch_card.punches` = 已打孔次数，`total` = 总次数；典型多次卡数据模型
- `punch_card_used` 写入接口看上去未启用（0 行）

### 2.2 周边卡券系列（不专属次卡）

| 表 | 行数 |
|---|---:|
| `card` | 16365 |
| `card_detail` | 681 |
| `ticket` | 12244 |
| `ticket_template` | 18 |
| `product_ticket_template` | 11 |

`card.is_ticket` / `is_package` / `used` 字段说明 card 表既承载单次礼券、套餐券，也可能承载历史次卡数据。

### 2.3 字符串「次卡支付」出现的地方（旧路径）

- `order_online.pay_memo = '次卡支付'` 共 6 行
- `[order].pay_option = '次卡支付'`：[RentController.cs:1629](../SnowmeetApi/Controllers/RentController.cs:1629) 检查 → 报表 type 标 "次卡"
- [MaintainLiveController.cs:609 / 692 / 698](../SnowmeetApi/Controllers/MaintainLiveController.cs:609)：保养业务走 `payOption.Trim().Equals("次卡支付")` 走免支付分支
- [MigrationController.cs:755](../SnowmeetApi/Controllers/MigrationController.cs:755)：标准化 `payMemo.IndexOf("次卡") >= 0` → `payMemo = "次卡"`

### 2.4 📌 关键发现

`SnowmeetApi/Models/` 下**没有** `PunchCard` / `PunchCardUsed` 的 C# 模型类（`grep -r 'Table("punch_card' Models/` 0 命中）。DB 表是裸建的，EF 层未接入，因此当前业务核销「次卡支付」仍走 `pay_option/pay_memo` 字符串标记的老路径，新结构化的 `punch_card_used` 明细表无写入代码。

→ 已写进 CLAUDE.md「已知遗留」节，避免未来误判"有表就有逻辑"。

---

## 3. 给财年版 xlsx 加「次卡」列

### 3.1 规则澄清

用户原话：「如果该笔订单下存在有效的rental 的 use_card 不为0 则填写为"是"，如果不存在，如果当前订单支付次数大于1，则填写为"否"，支付次数为0则填写"-"」。

我先 DB 端验证字段 + 分布：
- `rental.use_card` 是 `bit`，全表 32 行 = True / 17701 行 = False
- 万龙 25-26 财年区间 + code 非空：use_card 命中 19 单（27 rentals）
- 支付次数分布（`order_payment.status='支付成功'`）：0 笔 398 单 / **1 笔 2170 单（大头）** / 2 笔 47 / 3+ 笔 6

发现规则覆盖不全 — "支付次数 > 1"按字面会留 2170 单（单笔支付的主体）空白。AskUserQuestion 澄清：

| 澄清问题 | 用户回答 |
|---|---|
| 支付次数 = 1（2170 单）怎么填？ | 填"否"（原意是 ≥1 都填否） |
| "有效的 rental" 怎么定义？ | `rental.valid = 1` |

修正后规则：
1. `rental.valid=1 AND use_card=1` 任一存在 → **是**
2. 否则 `order_payment.status='支付成功'` 笔数 ≥ 1 → **否**
3. 否则（0 笔成功支付） → **-**

### 3.2 实施

走 plan 流程，plan 文件 `~/.claude/plans/start-work-ethereal-allen.md`。

仿 [`add_balance_to_api_xlsx.py`](../add_balance_to_api_xlsx.py) 的"补列"模式，新建 [`add_cika_column_to_fy_xlsx.py`](../add_cika_column_to_fy_xlsx.py)：

- 一次 SQL 拉两份 dict（命中 use_card 的 code set + 每订单支付成功笔数）
- 用 `?` 占位符参数化（含中文常量 `N'支付成功'`）防注入
- 表头样式与 add_balance 完全一致：`Font(bold=True, color="FFFFFF")` + `PatternFill("solid", "1F4E78")` + 居中
- 幂等：检测到「次卡」列已存在则覆盖，否则追加到末尾

### 3.3 跑通 + 验证

```
DB use_card 命中 (订单数): 19
DB 订单总数 (有支付聚合): 2615
新建「次卡」列（第 100 列）
xlsx 行数: 2428
  是: 19
  否: 2062
  -:  347
  合计: 2428
写入 .../wanlong_rent_orders_fy_2025-05-01_2026-04-30.xlsx
文件大小: 672.3 KB
```

3 类 spot-check（每类 3 单，对照 DB 查 `use_card_rentals` + `pay_success_cnt`）全 PASS：

| xlsx 标签 | 样本 | use_card rentals | pay_success_cnt |
|---|---|---:|---:|
| 是 | WT_ZL_251127_00006 | 2 | 1 |
| 是 | WT_ZL_251127_00007 | 2 | 1 |
| 是 | WT_ZL_251128_00012 | 1 | 1 |
| 否 | WT_ZL_251021_00001 | 0 | 1 |
| - | WT_ZL_251022_00001 | 0 | 0 |

### 3.4 踩坑

**xlsx sheet 名差异**：脚本里我死写 `SHEET = "订单"`（对账版的命名），第一次跑报错 `sheet '订单' 不存在，实际: ['年度租赁']`。财年版用「年度租赁」。修后再跑通。教训：跨 skill 复用代码时 sheet 名要从源 xlsx 实际 sheetnames 兜底，不要假设统一。

---

## 4. WT_ZL_251222_00009 排查（未完成）

用户问「这个订单为什么从小程序上查询不到？12 月 22 号的」。

DB 直查 `[order] WHERE code = 'WT_ZL_251222_00009'`：

```
id                 = 64707
code               = 'WT_ZL_251222_00009'
shop               = '万龙体验中心'
type               = '租赁'
pay_option         = '普通'
member_id          = 30597
biz_date           = 2025-12-22 10:22:24
staff_id           = 7
valid              = 1
closed             = 1
recepting          = 1
hide               = False
update_date        = 2025-12-22 22:00:11
create_date        = 2025-12-22 10:22:24
```

**关键发现**：`order_payment WHERE order_id = 64707` **0 行** — 这单根本没付过钱（即便 `closed=1`）。

`api/Rent/GetConfirmedRentOrder` 5 条规则（小程序查询入口）：
1. **paidAmount > 0** ← ❌ 失败（0 笔支付）
2. closed = 1 ← PASS
3. close_date != null ← 未确认（被打断前没取这列）
4. !hide ← PASS
5. 不含非微信非支付宝支付 ← N/A

→ 推测命中第 1 条过滤被剔出，所以小程序查不到。

待续查（被用户 end-work 打断）：
- rental 表此单数据（valid / settled / 是否有 use_card / 是否含赔偿/退款明细）
- payment_refund 是否有记录
- close_date 是否为空
- 业务侧此单是怎么"结束"的（招待？测试？人工标 closed=1？）

---

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`snowmeet_ai_doc/add_cika_column_to_fy_xlsx.py`](../add_cika_column_to_fy_xlsx.py) | **新建** 补列脚本（109 行），幂等 |
| [`snowmeet_ai_doc/wanlong_rent_orders_fy_2025-05-01_2026-04-30.xlsx`](../wanlong_rent_orders_fy_2025-05-01_2026-04-30.xlsx) | 第 100 列追加「次卡」（2428 行：是 19 / 否 2062 / - 347） |
| `snowmeet_ai_doc/CLAUDE.md` | 当前状态日期戳更新、新增 1 条「已知遗留」、新增本日开发日志 |
| `~/.claude/plans/start-work-ethereal-allen.md` | plan 文件 |

环境：`pip3 install --user openpyxl`（首次跑前装的，3.1.5）；`pyodbc 4.0.39` + `ODBCSYSINI=/opt/homebrew/etc` 沿用。

---

## 学到的小知识

1. **DB 表结构齐全 ≠ 业务接通**：`punch_card` / `punch_card_used` schema 在生产，但 EF Model 不存在 → 表是裸建的，未写入。改/对账次卡功能前必须翻 controller 确认走哪条路径（pay_option 字符串 vs punch_card 表），不要假设"有表就有逻辑"
2. **xlsx 补列前必须先核 sheet 名**：财年版 sheet 名是「年度租赁」而非「订单」（与对账版命名不同）。脚本里别死写，要么参数化要么 `wb.sheetnames` 兜底 + 报错时打印实际值
3. **`pyodbc` 参数化 SQL 含中文常量无编码问题**：`N'支付成功'` 用 `?` 占位 + 中文字面量混合传入正常工作（不像有些驱动需 prepared statement 改写）
4. **"支付次数 > 1"是用户的常见省略**：大多数业务文案里"大于 1"≈"≥ 1"≈"有过支付"，但代码里必须澄清。本次 2170 单单笔支付被字面规则漏掉险些错填 "-"
5. **`closed=1` 不代表 `paidAmount > 0`**：WT_ZL_251222_00009 是典型反例。`closed` 字段被人工 / 异常路径置 1 时，金额条件仍可能失败。报表过滤要按"满足全部 5 条"判定，不能只看 closed
6. **`use_card` 是 bit 字段**：Python pyodbc 拉出来是 True/False；写 xlsx 规则时 `r.use_card != 0` 等价于 `= True` / `= 1`
