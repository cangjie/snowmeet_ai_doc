"""一次性批量重跑所有店所有业务 fy + add_payment_detail。

19 组（怀北 rent 已 smoke 完成，可重跑无副作用）。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'D:\snowmeet\snowmeet_ai_doc'
PY = sys.executable

# (biz, shop_zh, file_prefix, main_sheet_name)
JOBS = [
    # rent
    ('rent', '万龙体验中心', 'wanlong',         '年度租赁'),
    ('rent', '崇礼旗舰店',   'chongli',         '年度租赁'),
    ('rent', '南山',         'nanshan',         '年度租赁'),
    ('rent', '怀北',         'huaibei',         '年度租赁'),
    ('rent', '渔阳',         'yuyang',          '年度租赁'),
    # retail
    ('retail', '万龙体验中心', 'wanlong',         '年度零售'),
    ('retail', '万龙服务中心', 'wanlong_service', '年度零售'),
    ('retail', '崇礼旗舰店',   'chongli',         '年度零售'),
    ('retail', '南山',         'nanshan',         '年度零售'),
    ('retail', '总部',         'headquarters',    '年度零售'),
    ('retail', '怀北',         'huaibei',         '年度零售'),
    ('retail', '渔阳',         'yuyang',          '年度零售'),
    # ski_pass
    ('ski_pass', '崇礼旗舰店', 'chongli',         '年度雪票'),
    ('ski_pass', '南山',       'nanshan',         '年度雪票'),
    # care
    ('care', '万龙服务中心', 'wanlong_service', '年度养护'),
    ('care', '崇礼旗舰店',   'chongli',         '年度养护'),
    ('care', '南山',         'nanshan',         '年度养护'),
    ('care', '怀北',         'huaibei',         '年度养护'),
    ('care', '渔阳',         'yuyang',          '年度养护'),
]

SKILL_PATH = {
    'rent':     'skills\export_rent_order_fiscal_year\export_rent_orders_fy.py',
    'retail':   'skills\export_retail_order_fiscal_year\export_retail_orders_fy.py',
    'ski_pass': 'skills\export_ski_pass_order_fiscal_year\export_ski_pass_orders_fy.py',
    'care':     'skills\export_care_order_fiscal_year\export_care_orders_fy.py',
}

failed = []
for i, (biz, shop, prefix, main_sheet) in enumerate(JOBS, 1):
    out = f'{DOC}\{prefix}_{biz}_orders_fy_2025-05-01_2026-04-30.xlsx'
    print(f'\n{"="*70}\n[{i}/{len(JOBS)}] {biz} / {shop} ({prefix})\n{"="*70}')

    # step 1: fy skill
    cmd1 = [PY, f'{DOC}\{SKILL_PATH[biz]}', '--shop', shop, '--out', out]
    print(f'$ python {SKILL_PATH[biz]} --shop {shop} --out {os.path.basename(out)}')
    r = subprocess.run(cmd1, cwd=DOC, capture_output=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f'  FY FAILED rc={r.returncode}')
        print(f'  STDOUT:\n{r.stdout[-2000:]}')
        print(f'  STDERR:\n{r.stderr[-2000:]}')
        failed.append((biz, shop, 'fy'))
        continue
    # 输出后两行
    print('  ' + '\n  '.join(r.stdout.strip().splitlines()[-3:]))

    # step 2: add_payment_detail
    cmd2 = [PY, f'{DOC}\add_payment_detail_sheet_to_fy_xlsx.py',
            '--xlsx', out, '--main-sheet', main_sheet]
    print(f'$ python add_payment_detail_sheet_to_fy_xlsx.py --xlsx {os.path.basename(out)} --main-sheet {main_sheet}')
    r = subprocess.run(cmd2, cwd=DOC, capture_output=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f'  ADD_PAYMENT_DETAIL FAILED rc={r.returncode}')
        print(f'  STDOUT:\n{r.stdout[-2000:]}')
        print(f'  STDERR:\n{r.stderr[-2000:]}')
        failed.append((biz, shop, 'add_payment_detail'))
        continue
    print('  ' + '\n  '.join(r.stdout.strip().splitlines()[-3:]))

print(f'\n{"="*70}\nALL DONE; failed: {len(failed)}')
for b, s, p in failed:
    print(f'  - {b} / {s} : {p}')
sys.exit(1 if failed else 0)
