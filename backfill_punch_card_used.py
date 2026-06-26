#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 rental 表反推「租赁」次卡使用记录，回补进 punch_card_used，并把每张卡的累计使用次数写回 punch_card.punches。

来源信号：rental.memo LIKE '%次卡%' 且订单/租赁均有效（order.valid=1 AND rental.valid=1）。
打卡次数（天数）口径：end_date IS NULL → 1；否则 DATEDIFF(day, start_date, end_date)+1，< 1 兜底为 1。
会员→卡：order.member_id = punch_card.member_id AND biz_type='租赁'，仅「恰好 1 张」时自动回补。
跳过：settled=0（未结算虚账，如 rental 17766 累计 211 天）。
粒度：每条 rental 一条 punch_card_used（biz_type='租赁'，biz_id=rental.id）。
累加：punch_card.punches 用「重算」（SUM 有效 used.punch_count）写回，幂等。

用法：
  python3 backfill_punch_card_used.py            # dry-run：打印预览 + 写 .sql + 人工核 .csv，不写库
  python3 backfill_punch_card_used.py --apply     # 在事务里执行 17 条 INSERT + punches 重算（幂等）

Intel Mac 跑前：export ODBCSYSINI=/usr/local/Cellar/unixodbc/2.3.4/etc （Driver 13）
"""
import os
import sys
import csv
import argparse
from collections import defaultdict

import pyodbc

HERE = os.path.dirname(os.path.abspath(__file__))
# 生产连接串保存在仓库外的 SnowmeetApi/config.sqlServer（gitignore）
CONFIG = os.path.join(HERE, '..', 'SnowmeetApi', 'config.sqlServer')
SQL_OUT = os.path.join(HERE, 'backfill_punch_card_used.sql')
CSV_OUT = os.path.join(HERE, 'punch_card_used_manual_review.csv')

# 计算天数的 SQL 片段（end_date 空 → 1；否则 DATEDIFF+1，< 1 兜底 1）
DAYS_EXPR = """CASE WHEN r.end_date IS NULL THEN 1
       WHEN DATEDIFF(day, r.start_date, r.end_date) + 1 < 1 THEN 1
       ELSE DATEDIFF(day, r.start_date, r.end_date) + 1 END"""

QUERY = f"""
SELECT r.id            AS rental_id,
       r.order_id      AS order_id,
       o.code          AS order_code,
       r.settled       AS settled,
       o.member_id     AS member_id,
       r.start_date    AS start_date,
       r.end_date      AS end_date,
       {DAYS_EXPR}     AS days,
       (SELECT COUNT(*) FROM punch_card pc
          WHERE pc.member_id = o.member_id AND pc.biz_type = N'租赁') AS card_cnt,
       (SELECT MIN(pc.id) FROM punch_card pc
          WHERE pc.member_id = o.member_id AND pc.biz_type = N'租赁') AS first_card_id,
       r.memo          AS memo,
       (SELECT TOP 1 m.real_name FROM member m WHERE m.id = o.member_id) AS member_name
FROM rental r
JOIN [order] o ON o.id = r.order_id
WHERE r.memo LIKE N'%次卡%'
  AND o.valid = 1 AND r.valid = 1
ORDER BY r.id
"""


def conn_str():
    with open(CONFIG, 'r', encoding='utf-8') as f:
        base = f.read().strip()
    # config.sqlServer 默认带 Driver 18 的连法在 Intel Mac 不可用，这里强制 Driver 13。
    # base 形如 Server=...;Database=...;UID=...;PWD=...;Encrypt=True;TrustServerCertificate=True
    # Driver 13 只认 Encrypt=yes/no（不认 True/False），归一化一下。
    base = base.replace('Encrypt=True', 'Encrypt=yes').replace('TrustServerCertificate=True', 'TrustServerCertificate=yes')
    return "DRIVER={ODBC Driver 13 for SQL Server};" + base


def classify(rows):
    """返回 (auto, manual_nocard, manual_multi, skip)。"""
    auto, manual_nocard, manual_multi, skip = [], [], [], []
    for r in rows:
        if r['settled'] == 0:
            skip.append(r)
        elif (r['card_cnt'] or 0) == 0:
            manual_nocard.append(r)
        elif r['card_cnt'] > 1:
            manual_multi.append(r)
        else:
            auto.append(r)
    return auto, manual_nocard, manual_multi, skip


def fetch():
    cn = pyodbc.connect(conn_str(), timeout=20)
    cur = cn.cursor()
    cur.execute(QUERY)
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cn.close()
    return rows


def print_bucket(title, rows, show_card=True):
    print(f"\n===== {title}（{len(rows)} 条）=====")
    for r in rows:
        cid = r.get('first_card_id') if show_card else ''
        print(f"  rental={r['rental_id']:<6} {r['order_code']:<22} "
              f"member={r['member_id']:<7} days={r['days']} "
              f"card_id={cid if cid is not None else '-'}  memo={(r['memo'] or '').strip()[:30]}")


def write_sql(auto):
    lines = []
    lines.append("-- 次卡使用记录回补：punch_card_used INSERT + punch_card.punches 重算")
    lines.append("-- 自动回补 = 会员恰好 1 张租赁卡 & settled=1，每条 rental 一行")
    lines.append("-- 幂等：INSERT 用 NOT EXISTS 守卫；punches 用 SUM 重算")
    lines.append("BEGIN TRAN;")
    lines.append("")
    for r in auto:
        lines.append(
            "INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)\n"
            f"SELECT {r['first_card_id']}, {r['order_id']}, N'租赁', {r['rental_id']}, NULL, {r['days']}, 1, GETDATE()\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id={r['rental_id']} AND valid=1);"
        )
    card_ids = sorted({r['first_card_id'] for r in auto})
    lines.append("")
    in_list = ",".join(str(c) for c in card_ids)
    lines.append(
        f"UPDATE punch_card SET punches = (\n"
        f"    SELECT ISNULL(SUM(u.punch_count), 0) FROM punch_card_used u\n"
        f"    WHERE u.card_id = punch_card.id AND u.valid = 1\n"
        f"  ), update_date = GETDATE()\n"
        f"WHERE id IN ({in_list});"
    )
    lines.append("")
    lines.append("COMMIT;")
    lines.append("")
    with open(SQL_OUT, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"\n已写 SQL → {SQL_OUT}（{len(auto)} 条 INSERT + 1 条 punches 重算，覆盖卡 {in_list}）")


def write_manual_csv(manual_nocard, manual_multi):
    rows = []
    for r in manual_nocard:
        rows.append(dict(r, bucket='无卡', candidate_card_ids=''))
    for r in manual_multi:
        # 多卡：列出该会员全部租赁卡 id
        rows.append(dict(r, bucket='多卡', candidate_card_ids=''))
    # 多卡候选卡 id 需另查；这里在主查询外补一次
    if manual_multi:
        cn = pyodbc.connect(conn_str(), timeout=20)
        cur = cn.cursor()
        members = sorted({r['member_id'] for r in manual_multi})
        ph = ",".join("?" for _ in members)
        cur.execute(
            f"SELECT member_id, id FROM punch_card WHERE biz_type=N'租赁' AND member_id IN ({ph}) ORDER BY member_id, id",
            *members)
        cand = defaultdict(list)
        for mid, cid in cur.fetchall():
            cand[mid].append(str(cid))
        cn.close()
        for row in rows:
            if row['bucket'] == '多卡':
                row['candidate_card_ids'] = "/".join(cand.get(row['member_id'], []))

    fields = ['bucket', 'rental_id', 'order_code', 'member_id', 'member_name',
              'start_date', 'end_date', 'days', 'candidate_card_ids', 'memo']
    with open(CSV_OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            row = dict(row)
            row['memo'] = (row.get('memo') or '').strip()
            w.writerow(row)
    print(f"已写人工核 CSV → {CSV_OUT}（{len(rows)} 条：无卡 {len(manual_nocard)} + 多卡 {len(manual_multi)}）")


def apply(auto):
    cn = pyodbc.connect(conn_str(), timeout=30, autocommit=False)
    cur = cn.cursor()
    inserted = 0
    try:
        for r in auto:
            cur.execute(
                "IF NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=? AND valid=1) "
                "INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date) "
                "VALUES (?, ?, N'租赁', ?, NULL, ?, 1, GETDATE())",
                r['rental_id'], r['first_card_id'], r['order_id'], r['rental_id'], r['days'])
            inserted += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        card_ids = sorted({r['first_card_id'] for r in auto})
        ph = ",".join("?" for _ in card_ids)
        cur.execute(
            "UPDATE punch_card SET punches = ("
            "  SELECT ISNULL(SUM(u.punch_count), 0) FROM punch_card_used u "
            "  WHERE u.card_id = punch_card.id AND u.valid = 1"
            "), update_date = GETDATE() "
            f"WHERE id IN ({ph})", *card_ids)
        cn.commit()
        print(f"\n[APPLY] 已提交：新插入 {inserted} 条 punch_card_used，重算卡 {card_ids} 的 punches")
        # 复查
        cur.execute(f"SELECT id, total, punches FROM punch_card WHERE id IN ({ph})", *card_ids)
        print("  卡复查 (id / total / punches):")
        for row in cur.fetchall():
            print("   ", list(row))
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='执行写库（默认仅 dry-run）')
    args = ap.parse_args()

    rows = fetch()
    auto, manual_nocard, manual_multi, skip = classify(rows)

    print(f"命中 memo 含次卡的有效 rental：{len(rows)} 条")
    print_bucket("自动回补（会员恰好 1 张租赁卡 & settled=1）", auto)
    print_bucket("人工核-无卡（会员无租赁卡）", manual_nocard, show_card=False)
    print_bucket("人工核-多卡（会员有 ≥2 张租赁卡，候选见 CSV）", manual_multi, show_card=False)
    print_bucket("跳过（settled=0 未结算虚账）", skip, show_card=False)

    bycard = defaultdict(int)
    for r in auto:
        bycard[r['first_card_id']] += r['days']
    print("\n按卡累加 punches（自动桶）：")
    for cid in sorted(bycard):
        print(f"  card_id={cid} += {bycard[cid]}")

    if args.apply:
        apply(auto)
        print("\n人工核的 13 条未自动处理，见上方两桶 / 重跑 dry-run 生成 CSV。")
    else:
        write_sql(auto)
        write_manual_csv(manual_nocard, manual_multi)
        print("\n[DRY-RUN] 未写库。审阅 .sql 后用 --apply 落库，或手工执行 .sql。")


if __name__ == '__main__':
    main()
