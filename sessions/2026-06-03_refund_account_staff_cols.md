# 2026-06-03 4 业务财年报表退款列扩展：加退款账号 + 退款人 + 支付流水操作人

接续 6-1 把 5+2 店 × 4 业务财年报表按业务合并成 4 份 merged xlsx 的工作。用户原话：「需要修改 6月1日导出的所有的报表。各个退款列，需要增加退款的账号，如果是微信支付，需要写入微信支付的商户号，如果是支付宝，直接填写支付宝。另外还需要增加每笔退款的退款人，根据 payment_refund 的 staff_id 关联。」改动落在 `snowmeet_ai_doc/`。

## 1. 调查阶段

### 1.1 退款列在哪些 sheet / 哪些 K 组

并行 3 个 Explore agent 调查：
- merged 4 份 xlsx 的退款列 audit（编码问题，最终用本机 py 跑）
- 4 个 fy skill 主脚本 + add_payment_detail_sheet_to_fy_xlsx.py + add_*detail_merged 系列里"退款"相关的代码段
- DB schema：payment_refund / order_payment / wepay_key / staff 模型字段 + 关联键

结论：
- **主 sheet（年度{业务}）**：动态 K 组 `【退款K】日期 / 时间 / 金额 / 退款方式`（4 列/K），K=1..maxRefund
- **支付明细 sheet**：动态 K 组 `退款K日期 / 时间 / 金额 / 方式`（4 列/K，无方括号、无"退款"前缀）
- **支付流水 sheet**：退款是行不是列；行级 8 列含 `订单号/支付方式/支付账户/商户订单号/类型/交易金额/日期/时间`，没有"操作人"列
- **年度{业务}明细 sheet**：从主 sheet 读 main_headers + 追加 DETAIL_COLS → **自动继承新列**，无需改 add_*detail_merged 脚本
- **merge_fy_orders.py**：`union_headers + remap_rows` 按列名联集对齐 → **自动适配新列**，无需改

### 1.2 DB JOIN 路径

| 字段 | 来源 |
|---|---|
| 退款账号（微信） | `payment_refund.payment_id → order_payment.mch_id → wepay_key.mch_id`（真实商户号字串如 `1636404775`） |
| 退款账号（支付宝） | 直接填字串 `"支付宝"`（CASE WHEN op.pay_method = N'支付宝' THEN N'支付宝'） |
| 退款账号（其他） | `N''` 空串（与现有「支付账号」列对其他通道一致处理） |
| 退款人 | `payment_refund.staff_id → staff.id → staff.name` |

## 2. 用户决策（plan 阶段 AskUserQuestion）

| 问题 | 决策 |
|---|---|
| 范围 | **所有都需要**：主 sheet + 支付明细 sheet + 支付流水 sheet 加操作人列 |
| 实现方式 | **改 4 skill + add_payment_detail 后全量重跑**（不写补丁脚本） |
| 支付宝账号在「支付」列要否对称改写 | **不改，只动退款侧**（支付侧支付宝→空串保持现状） |
| 列名 | **`【退款K】退款账号 / 【退款K】退款人`**（主 sheet）、`退款K账号 / 退款K退款人`（支付明细 sheet） |

## 3. 实施阶段

### 3.1 4 个 fy skill 主脚本同构改动

每个 `skills/export_{rent,retail,ski_pass,care}_order_fiscal_year/export_*_orders_fy.py`：

```sql
-- REFUND_DETAIL_SQL 改
SELECT o.id AS oid,
       pr.create_date AS rt,
       pr.amount,
       op.pay_method AS refund_method,
       CASE WHEN op.pay_method = N'微信支付' THEN wk.mch_id
            WHEN op.pay_method = N'支付宝'   THEN N'支付宝'
            ELSE N'' END                            AS refund_account,
       sa.name                                       AS refund_staff
FROM [order] o
JOIN payment_refund pr ON pr.order_id = o.id
LEFT JOIN order_payment op ON op.id = pr.payment_id
LEFT JOIN wepay_key wk ON wk.id = op.mch_id   -- 新增
LEFT JOIN staff sa ON sa.id = pr.staff_id      -- 新增
WHERE {ORDER_FILTER} AND {REFUND_COND}
ORDER BY o.id ASC, pr.create_date ASC, pr.id ASC
```

```python
# ref_by_oid 元组扩 5 项
for oid, rt, amt, rm, racct, rstaff in cur.fetchall():
    ref_by_oid[oid].append((rt, amt, rm, racct, rstaff))

# headers 退款段每 K 6 列
for k in range(1, max_refund + 1):
    headers += [f'【退款{k}】日期', f'【退款{k}】时间', f'【退款{k}】金额',
                f'【退款{k}】退款方式',
                f'【退款{k}】退款账号', f'【退款{k}】退款人']

# seg3 6 项
for k in range(max_refund):
    if k < len(rlist):
        rt, amt, rm, racct, rstaff = rlist[k]
        rd_, rtm = split_dt(rt)
        seg3 += [rd_, rtm, round(float(amt), 2) if amt is not None else None,
                 rm, racct or '', rstaff or '']
    else:
        seg3 += [None, None, None, None, None, None]
```

### 3.2 add_payment_detail_sheet_to_fy_xlsx.py 改动

- `fetch_payments` 加 `LEFT JOIN staff pay_sa ON pay_sa.id = op.staff_id` 取 `pay_staff_name`
- `fetch_refunds` 加 `LEFT JOIN staff sa ON sa.id = pr.staff_id` 取 `staff_name`
- `build_headers_and_rows` 退款 K 组 4→6 列：
  ```python
  headers += [f"退款{k}日期", f"退款{k}时间", f"退款{k}金额", f"退款{k}方式",
              f"退款{k}账号", f"退款{k}退款人"]
  ```
- `refund_acct_for(p)` helper：微信→`p["pay_account"]`（已是 str(real_mch_id) 或 ""）/ 支付宝→"支付宝" / 其他→""
- **关键坑**：`money_col_idxs` 中"退款k金额"偏移从 `10 + k*4 + 3 → 10 + k*6 + 3`；`refund_block_end` 从 `10 + maxRefund*4 → 10 + maxRefund*6`。漏改会导致金额列没锁 `0.00` 格式
- `build_transaction_rows` 末尾加「操作人」列：支付行=`p["pay_staff_name"]` / 退款行=`r["staff_name"]` / 分账行=空串
- docstring 描述「动态 maxRefund × 4 列」→「× 6 列」+ 增 2 列说明

### 3.3 Smoke 怀北 13 单租赁

```bash
py skills/export_rent_order_fiscal_year/export_rent_orders_fy.py --shop 怀北
# 写 Excel: huaibei_rent_orders_fy_2025-05-01_2026-04-30.xlsx （56 列 × 13 行）

py add_payment_detail_sheet_to_fy_xlsx.py --xlsx huaibei_rent_orders_fy_2025-05-01_2026-04-30.xlsx --main-sheet 年度租赁
# 输出列：16（固定 10 + 退款 1×6 + 分账 0×3）
# 支付流水 sheet：21 行（支付 11 / 退款 10 / 分账 0）
```

抽样：HB_ZL_251114_00002 退款 ¥1 微信 账号=1636313350 退款人=张新健 ✓

### 3.4 全量重跑（19 组 fy + add_payment_detail）

写驱动脚本 `_run_all_fy.py` 用 subprocess 串跑。**第一轮失败**：路径中 `\a` 被 Python 字符串字面量解析为 BEL（0x07），错误 `'D:\\snowmeet\\snowmeet_ai_doc\x07dd_payment_detail_sheet_to_fy_xlsx.py'`。根因：bash heredoc `cat > foo.py <<'EOF'` 把 `\\` 吃成单 `\`，源代码里 `f'{DOC}\\add_payment_detail...'` 实际变成 `f'{DOC}\add_payment_detail...'`。

**修复**：重写 `_run_add_payment_detail.py` 用正斜杠 + 用 Write 工具而非 heredoc。

```python
SCRIPT = f'{DOC}/add_payment_detail_sheet_to_fy_xlsx.py'  # 正斜杠，无转义陷阱
```

19 组全部跑通：rent 5 / retail 7 / ski_pass 2 / care 5 各完成。

### 3.5 add_*_detail_merged 系列（第二轮失败 → 修复）

驱动 `_run_detail_merged.py` 跑 14 组：retail 5 + ski_pass 4（含 chongli 雪票列表 sheet + annotate）+ care 5。

**ski_pass 4 + care 5 + retail wanlong_service 全跑通**。但 **5 个 retail detail_merged 全失败**，错误：`年度零售 缺表头「七色米订单号」`。

诊断：
- add_*_retail_detail_merged_xlsx.py 在 base xlsx 的「年度零售」sheet 查 `七色米订单号` 列做匹配
- 但 fy skill 的 SQL 里没有这个列
- git 14f32e0 (6-1 commit) 的 chongli_retail base xlsx 末尾确有「七色米订单号」列（值如 `XSD20251030001A`）
- 结论：**这个列是手工/外部维护的**，不在 fy skill 输出范围。重跑 fy skill 会冲掉

**修复**：写 `_backfill_mi7_col.py` 从 git 14f32e0 commit 的 5 个 retail base xlsx 抽取 `code → mi7` mapping，回填到新文件末尾：

| 店 | 老版有 mi7 行数 |
|---|---|
| nanshan | 471 |
| chongli | 169 |
| wanlong | 138 |
| wanlong_service | 23 |
| headquarters | 40 |

回填后再跑 `_run_retail_detail_only.py`，5/5 通过。

顺手修 nanshan 脚本的过期路径：`销售单列表_c393a061-a3c1-4479-9611-f3f577a509c5.xls` → `南山_销售单列表.xls`（CLAUDE.md 5-19 续 2 已记载改名，但脚本路径没跟进）。

### 3.6 merge_fy_orders.py --biz all

最后一步合并 4 份 merged xlsx。union_headers + remap_rows 按列名自动对齐，新列零修改跟上。

| merged 文件 | 主 sheet 列数 | 支付明细列数 | 支付流水列数 | 其他 sheet |
|---|---|---|---|---|
| rent | 109 | 34 | 9 | — |
| retail | 56 | 16 | 9 | 年度零售明细 66 列 |
| ski_pass | 91 | 58 | 9 | 雪票列表 29 + 年度雪票明细 99 |
| care | 63 | 16 | 9 | 年度养护明细 84 |

## 4. 抽样验证

merged_rent_orders_fy 主 sheet 5 条退款样本：

| 订单号 | 退款金额 | 方式 | 退款账号 | 退款人 |
|---|---|---|---|---|
| WT_ZL_251021_00001 | ¥150 | 微信支付 | 1636404775 | 崔洋（个人） |
| WT_ZL_251022_00003 | ¥880 | 支付宝 | 支付宝 | 韩冬垚-工作号 |
| WT_ZL_251022_00006 | ¥0.1 | 微信支付 | 1636404775 | 肖志强（工作号） |
| WT_ZL_251022_00010 | ¥150 | 微信支付 | 1636404775 | 崔洋（个人） |
| WT_ZL_251022_00011 | ¥150 | 微信支付 | 1636404775 | 崔洋（个人） |

merged_rent 支付流水「操作人」列：
- 支付行：`WT_ZL_251021_00001 微信支付 1636404775 ¥200 操作人=崔洋（个人）` ✓
- 退款行：`WT_ZL_251021_00001 微信支付 1636404775 -¥150 操作人=崔洋（个人）` ✓
- 分账行：`WT_ZL_251129_00008 支付宝 None -¥65 操作人=None` ✓（系统触发无人工）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `skills/export_rent_order_fiscal_year/export_rent_orders_fy.py` | REFUND_DETAIL_SQL + 2 JOIN + 2 列 / ref_by_oid 5元组 / headers + seg3 各加 2 项 |
| `skills/export_retail_order_fiscal_year/export_retail_orders_fy.py` | 同上 |
| `skills/export_ski_pass_order_fiscal_year/export_ski_pass_orders_fy.py` | 同上 |
| `skills/export_care_order_fiscal_year/export_care_orders_fy.py` | 同上 |
| `add_payment_detail_sheet_to_fy_xlsx.py` | fetch_payments + fetch_refunds 加 staff JOIN / build_headers_and_rows 退款 K 4→6 列 + money_col_idxs 偏移 / build_transaction_rows 加「操作人」列 + docstring |
| `add_retail_detail_merged_xlsx.py` | SRC_XLS nanshan 过期路径修复 |
| `skills/export_{rent,retail,ski_pass,care}_order_fiscal_year/SKILL.md` × 4 | 列结构小节同步新增 2 列说明，每笔 4→6 列 |

产物（28 份 xlsx）：
- 19 份单店 fy xlsx 全部含新列
- 5 份 *_with_detail.xlsx（retail 副产物）
- 4 份 merged xlsx

## 学到的小知识

1. **`Util.AES_decrypt` / wepay_key.mch_id JOIN 模式可复用**：`LEFT JOIN wepay_key wk ON wk.id = op.mch_id` 已在 PAY_DETAIL_SQL 和 add_payment_detail 中存在，REFUND_DETAIL_SQL 直接照搬即可
2. **`merge_fy_orders.py` 是按列名联集合并的**：源 skill 加新列后 merge 脚本零修改自动跟上，所以"先改 skill + 全量重跑"是最干净的路径，比写补丁脚本只动产物更稳
3. **retail base xlsx 的「七色米订单号」列不在 fy skill 输出范围**：它是从外部 ERP (七色米) 手工维护到 base xlsx 的列。重跑 fy skill 会冲掉。未来需要先从 git 历史 commit 抽取再回填，或者把这列纳入 fy skill SQL（需先确认 DB 是否有对应字段）
4. **bash heredoc + Python f-string + Windows 路径反斜杠是三重陷阱**：`\\` 在 heredoc 内被吃成单 `\`，再被 Python 解析为转义字符（如 `\a` = BEL 0x07）。**写 Python 路径建议用 raw string + 正斜杠**：`'D:/snowmeet/...'` 在 Windows 上完全可用；或用 `os.path.join`
5. **add_*_retail_detail_merged_xlsx.py 是"两步写盘"模式**：先 `wb.save(OUT_XLSX)` 另存独立 `_with_detail.xlsx`，再 `mwb.save(SRC_XLSX)` 幂等注入 base xlsx 的「年度零售明细」sheet。所以下游 merge_fy_orders 只读 base xlsx 也能拿到 detail sheet
6. **退款方式 CASE 表达式只规定微信/支付宝**：其他通道（储值支付/现金/挂账/储值卡等）退款账号统一 `N''` 空串。和现有「支付账号」列对其他通道的处理一致
7. **money_col_idxs 偏移漏改是常见 bug**：动态列宽度从 4 变 6 时，金额列的 1-based 索引也要从 `base + k*4 + offset` 改成 `base + k*6 + offset`。漏改会导致金额列没锁 `0.00` 显示格式，可能出现科学计数法
