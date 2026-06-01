# 2026-06-01 4 业务财年报表按业务合并：is_test 列 + 储值支付覆盖收款方式 + 怀北/渔阳追加

按业务（租赁/零售/雪票/养护）把上月按店铺导出的财年报表合并到 4 份新文件；中间走过两轮否决的试验（按 `is_test` 重判「测试」列 + 按 member 优先重判「客户名称」），最终回滚走"独立合并脚本不动 skill"路线。会话尾追加怀北/渔阳两店 fy 报表，再次重跑合并。

## 1. WT_ZL_251208_00005 「测试 = 是」根因排查

用户问万龙财年报表里 `WT_ZL_251208_00005` 为什么标「测试」。脚本 SQL：

```sql
CASE WHEN ISNULL(pay_agg.paid, 0) < 5
          OR (s.name IS NOT NULL AND s.name LIKE N'%苍%')
     THEN N'是' ELSE N'' END                            AS 测试
```

这单 `pay_agg.paid = ¥0`、店员肖志强（非「苍」字）→ 命中"支付 < 5"分支被误判。客户「张小飞（个人）」、`order.is_test = 0` 真实非测试。

## 2. 第一轮试验（回滚）：按 `is_test` 字段重判「测试」列

调研后写 [`rebuild_test_column_by_is_test.py`](rebuild_test_column_by_is_test.py)，对 14 份 fy 报表逐一查 DB `[order].is_test`、重写「测试」列。结果（旧/新）：租赁 704→204、零售 173→114、雪票 573→0（财年内 ski_pass 业务 is_test=1 零单）、养护 969→207。同步把 4 个 fiscal year skill 的 SQL 改成 `CASE WHEN o.is_test = 1 THEN N'是' ELSE N'' END`。

## 3. 第二轮试验（回滚）：客户名称按 member 优先

用户提"客户名称首先看 `order.member_id` 对应的 `member.real_name`，没命中再 `order.contact_name`"。原 SQL 是反的：

```sql
COALESCE(NULLIF(LTRIM(RTRIM(o.contact_name)), N''), m.real_name)  -- 旧：先 contact_name
```

写 [`rebuild_customer_name_by_member.py`](rebuild_customer_name_by_member.py) 翻转优先级，14 份报表共动 30 条（租赁 2 / 零售 10 / 雪票 2 / 养护 15 + 雪票 1 单清空）。4 个 skill SQL 同步改为：

```sql
COALESCE(NULLIF(LTRIM(RTRIM(m.real_name)), N''), NULLIF(LTRIM(RTRIM(o.contact_name)), N''))
```

用户决策不过滤 `m.valid`。`WT_ZL_251208_00005` 因 `contact_name=NULL` 旧规则就已 fallback 到 real_name='张小飞（个人）'，新规则结果不变。

## 4. 回滚

用户拍板"所有报表直接放弃修改，从 git 上拉下来"。执行 `git checkout -- *.xlsx skills/`：snowmeet_ai_doc 下 13 份 xlsx + 4 个 fy skill .py 全部恢复 git 版本（SQL 回到 paid<5 OR 含苍 + contact_name 优先）。两个 untracked `rebuild_*.py` 删除。根目录 `D:\snowmeet\wanlong_rent_orders_fy_...xlsx` 不在 git 里无法 checkout，留原状但不参与合并。

## 5. 合并方案设计（Plan Mode）

用户最终需求：

1. 按业务合并所有店报表生成 4 份新文件
2. 利用现有「门店」列做店铺区分（已存在于所有 sheet，无需新加）
3. 保留原「测试」列原值不动
4. **新增「is_test」列**末尾追加，值取 DB `[order].is_test`(0/1)
5. **覆盖「收款方式」列**：若该订单有任意一笔 `status=支付成功 AND valid=1 AND pay_method='储值支付'` → 改写为"储值支付"

明细 sheet 处理：用户选"全部 sheet 都合"（包括支付明细 / 支付流水 / 年度{业务}明细 / 雪票列表）。合并单元格不重建（本期折衷）。

plan 文件：`~/.claude/plans/is-test-0-whimsical-patterson.md`。

### 关键数据核实

- DB `[order].is_test=1` 财年 4 业务共 446 单（租赁109/零售129/雪票0/养护209）
- DB `pay_method='储值支付'` 财年成功 276 笔 ¥69,702.75（在 16 个 pay_method 字符串里排第 3）
- Explore agent 初版漏报"储值支付不在 DB"（未加 type 过滤被微信支付 7000+ 笔淹没），自己 SQL 复查更正

### 14 份输入的 sheet 差异（同业务列联集对齐）

- 租赁：主 sheet 列数 99/63/54（maxPay 1~6 / maxRef 1~5 / maxShare 0~1）
- 零售：51~56（maxPay 1~6 / maxRef 0 / maxShare 0）
- 雪票：57+4/85（崇礼独有「雪票列表」/ 南山独有「年度雪票明细」）
- 养护：54~63（maxPay 1~6 / maxRef 0~5）

## 6. 实施：`merge_fy_orders.py`

新建 [`merge_fy_orders.py`](merge_fy_orders.py)（~230 行，单文件），结构：

- `INPUTS[biz]` 输入文件清单
- `MAIN_SHEET[biz]` 主 sheet 名映射
- `fetch_db_attrs(codes)` 一次性 batch query（900/批）拿 `{code: (is_test, has_sv_pay)}` 字典；同 code 多条用 max 聚合（兜底竞态码重复）
- `read_sheet(path, sheet)` openpyxl read_only=True 迭代器读取 + 空行过滤 + 行长度对齐
- `union_headers([hs1, hs2, ...])` 按首店首次出现顺序联集
- `remap_rows(rows, src_headers, dst_headers)` 列名映射，缺的留 None
- `write_sheet(ws, headers, rows)` 表头粗体白字 `1F4E78` 蓝底 + freeze A2 + 列宽自适应（视觉宽度算法 sample 前 300 行）
- `process_biz(biz)`：加载 → DB query → 各 sheet 联集对齐 → 主 sheet 加 is_test+覆盖收款方式 → 写新 xlsx

输出：`merged_{biz}_orders_fy_2025-05-01_2026-04-30.xlsx`（4 份）

### 三项校验（首轮 3 店）

| 业务 | 主 sheet 行 | is_test=1 | 储值支付覆盖 | 行数守恒 |
|---|---|---|---|---|
| 租赁 | 2743 (2319+192+232) | 106（DB 109，差 3） | 46（DB 46 ✓） | ✓ |
| 零售 | 1022 (186+31+261+497+47) | 114（DB 129，差 15） | 0（DB 0 ✓） | ✓ |
| 雪票 | 1561 (709+852) | 0（DB 0 ✓） | 0（DB 0 ✓） | ✓ |
| 养护 | 4713 (4601+26+86) | 207（DB 209，差 2） | 230（DB 230 ✓） | ✓ |

- 校验 1 行数守恒：16 个 sheet 累计差异 0
- 校验 2 抽样 130 条 0 miss / 0 mismatch（订单号/门店/订单结余/客户名称对齐）
- 校验 3 储值支付 4 业务 0 差异；is_test 差异都是预期外因（怀北/渔阳没报表 + 万龙报表去重）

## 7. 怀北/渔阳追加（用户尾轮要求）

用户："所有的店铺，都需要跑一下。在现有报表上追加即可。"

DB 调研：怀北 租赁 13 / 零售 9 / 养护 6 / 雪票 0；渔阳 租赁 25 / 零售 17 / 养护 2 / 雪票 0。两店 DB `shop` 字段直接是「怀北」/「渔阳」（无"滑雪场"后缀）。

跑 3 业务 × 2 店 = 6 份 fy 报表（雪票跳过）：

```bash
py {biz}_orders_fy.py --shop 怀北 --out huaibei_{biz}_orders_fy_xxx.xlsx
py {biz}_orders_fy.py --shop 渔阳 --out yuyang_{biz}_orders_fy_xxx.xlsx
```

`SHOP_PREFIX` 已含 `huaibei`/`yuyang`，参数化即可。

每份追加：
- `add_payment_detail_sheet_to_fy_xlsx.py --xlsx ... --main-sheet 年度{业务}` → 加支付明细+支付流水
- 养护 2 份 + `add_care_detail_merged_sheet.py --shop {怀北|渔阳}` → 加年度养护明细

改 [`merge_fy_orders.py`](merge_fy_orders.py) 的 `INPUTS` 把怀北/渔阳路径加进去（租赁 3→5 店、零售 5→7 店、养护 3→5 店）。重跑合并：

| 业务 | 之前 → 现在主 sheet 行 | is_test=1 之前→现在 | DB | 是否对齐 |
|---|---|---|---|---|
| 租赁 | 2743 → **2781**（+38） | 106→106 | 109 | 差 3（万龙报表去重 6 冲突 code 中 3 是 is_test=1） |
| 零售 | 1022 → **1048**（+26） | 114→**129** ✓ | 129 | ✓ |
| 雪票 | 1561（不变） | 0 ✓ | 0 | ✓ |
| 养护 | 4713 → **4721**（+8） | 207→**208** | 209 | 差 1（万龙服务去重 `WF_YH_251110_00017` 双插测试单） |

零售完全对齐。剩余 4 单差异是源报表去重决策，非合并 bug。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`merge_fy_orders.py`](merge_fy_orders.py) | 新建 230 行合并脚本（`--biz {rent\|retail\|ski_pass\|care\|all}`） |
| [`merged_rent_orders_fy_2025-05-01_2026-04-30.xlsx`](merged_rent_orders_fy_2025-05-01_2026-04-30.xlsx) | 新建 1.15 MB，3 sheet × 5 店 |
| [`merged_retail_orders_fy_2025-05-01_2026-04-30.xlsx`](merged_retail_orders_fy_2025-05-01_2026-04-30.xlsx) | 新建 552 KB，4 sheet × 7 店 |
| [`merged_ski_pass_orders_fy_2025-05-01_2026-04-30.xlsx`](merged_ski_pass_orders_fy_2025-05-01_2026-04-30.xlsx) | 新建 696 KB，5 sheet × 2 店 |
| [`merged_care_orders_fy_2025-05-01_2026-04-30.xlsx`](merged_care_orders_fy_2025-05-01_2026-04-30.xlsx) | 新建 2.6 MB，4 sheet × 5 店 |
| `huaibei_{rent,retail,care}_orders_fy_...xlsx` | 新建 3 份单店 fy 报表 + 支付明细/支付流水（养护还加养护明细） |
| `yuyang_{rent,retail,care}_orders_fy_...xlsx` | 同上 3 份 |

## 学到的小知识

1. **DB `pay_method='储值支付'` 真实存在**：财年内 276 笔成功 ¥69,702.75（全库 366 笔/359 成功），在 16 个 pay_method 字符串里排第 3。早一版 Explore agent 用 `WHERE order_id IN (...)` 但漏加 `o.type IN ('租赁',...)` 过滤，结果被 40 万行成功支付的微信支付/支付宝淹没误报"DB 没有"。**做数据调研时过滤口径必须与最终用法一致**

2. **「测试」列改 `is_test` 不能简单替换旧规则**：旧规则 `paid<5 OR 含苍` 命中很多 0 元正常单（场地租赁未走收款流程）；改 `is_test` 后总命中数下降到约 1/3，但用户后续因不确定影响面反悔回滚。**重判类改动先做 dry-run + 全量影响面对账再落盘，永远别在源 SQL 里直接改判定逻辑**

3. **`COALESCE(contact_name, real_name)` vs `COALESCE(real_name, contact_name)` 影响小但非零**：4 业务财年共 27 单两者都填且不一致，改 member 优先后只动这 27 单。但对 `m.valid=0` 的合并/失效会员不过滤会带回历史名，是否要"valid=1 过滤"用户拍板"不过滤"

4. **`git checkout -- *.xlsx skills/` 一键回滚整批改动**：snowmeet_ai_doc 把 13 份 xlsx + 4 个 .py 全部入了 git，所以一行命令就还原；根目录那份 `wanlong_rent_orders_fy_xxx.xlsx` 不在 git 里就没法回滚。**重要产物建议都入 git**，未来用户反悔时回滚成本极低

5. **`SHOP_PREFIX` 已预置 6 店**：`万龙体验中心→wanlong / 万龙服务中心→wanlong_service / 渔阳→yuyang / 南山→nanshan / 怀北→huaibei / 崇礼旗舰店→chongli`。新店进来只需在 `skills/export_rent_order/export_rent_orders.py` 顶部 dict 加一行

6. **怀北/渔阳零售跳过明细 sheet**：5 店原版有「年度零售明细」依赖外部七色米 `all_销售单列表.xls`，怀北/渔阳七色米数据是否覆盖未知。本期只跑主+支付明细+支付流水 3 sheet，零售明细 skip。后续要做需先确认七色米 xls 是否含这两店数据

7. **Python f-string + Windows 路径反斜杠**：`f'{DOC}\n...'` 把 `\n` 当转义符变换行；用 `D:/snowmeet/...` 正斜杠或 `\\` 双反斜杠或 raw string `r'\xxx'`。Windows 上路径首字符配套字母（n/r/t/...）容易踩雷

8. **合并文件不重建合并单元格**：年度{业务}明细 sheet 原本有订单级列垂直合并（一对多展开时订单级列只在首行显示）。openpyxl read_only 模式读出"merged-over"位置为 None；合并写回时所有数据行都填值（视觉上看不到合并），但金额聚合 = ΣN 份单店报表的合并行单值之和（不重复算）。**本期接受视觉降级**，回看单店原报表保留合并视觉

9. **`add_payment_detail_sheet_to_fy_xlsx.py` 是通用 sheet 追加工具**：`--main-sheet 年度{业务}` 参数化跨 4 业务复用。脚本根据主 sheet 订单号反查 order_payment / payment_refund / payment_share 写出 支付明细+支付流水 两 sheet。零售/养护/雪票/租赁全部走这一个脚本

10. **三表对账闭环可复用任意业务**：`年度{业务}Σ订单结余 ＝ 支付明细Σ支付结余 ＝ 支付流水按订单号Σ交易金额`。每次新业务/新店 fy 报表落盘后跑 `verify_payment_reconcile.py --xlsx X --main-sheet 年度{业务}`，1 分钱以内一致即认为支付流水链路正确
