"""19 组都已重跑 fy，但 add_payment_detail 全失败（路径中 \a 被当 BEL）。
本脚本仅重跑 add_payment_detail 一步。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = 'D:/snowmeet/snowmeet_ai_doc'
PY = sys.executable

JOBS = [
    ('rent', '万龙体验中心', 'wanlong',         '年度租赁'),
    ('rent', '崇礼旗舰店',   'chongli',         '年度租赁'),
    ('rent', '南山',         'nanshan',         '年度租赁'),
    ('rent', '怀北',         'huaibei',         '年度租赁'),
    ('rent', '渔阳',         'yuyang',          '年度租赁'),
    ('retail', '万龙体验中心', 'wanlong',         '年度零售'),
    ('retail', '万龙服务中心', 'wanlong_service', '年度零售'),
    ('retail', '崇礼旗舰店',   'chongli',         '年度零售'),
    ('retail', '南山',         'nanshan',         '年度零售'),
    ('retail', '总部',         'headquarters',    '年度零售'),
    ('retail', '怀北',         'huaibei',         '年度零售'),
    ('retail', '渔阳',         'yuyang',          '年度零售'),
    ('ski_pass', '崇礼旗舰店', 'chongli',         '年度雪票'),
    ('ski_pass', '南山',       'nanshan',         '年度雪票'),
    ('care', '万龙服务中心', 'wanlong_service', '年度养护'),
    ('care', '崇礼旗舰店',   'chongli',         '年度养护'),
    ('care', '南山',         'nanshan',         '年度养护'),
    ('care', '怀北',         'huaibei',         '年度养护'),
    ('care', '渔阳',         'yuyang',          '年度养护'),
]

SCRIPT = f'{DOC}/add_payment_detail_sheet_to_fy_xlsx.py'

failed = []
for i, (biz, shop, prefix, main_sheet) in enumerate(JOBS, 1):
    out = f'{DOC}/{prefix}_{biz}_orders_fy_2025-05-01_2026-04-30.xlsx'
    print(f'\n[{i}/{len(JOBS)}] {biz} / {shop} ({prefix})')
    if not os.path.exists(out):
        print(f'  SKIP: {out} 不存在')
        failed.append((biz, shop, 'missing_xlsx'))
        continue
    cmd = [PY, SCRIPT, '--xlsx', out, '--main-sheet', main_sheet]
    r = subprocess.run(cmd, cwd=DOC, capture_output=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f'  FAILED rc={r.returncode}')
        print(f'  STDOUT:\n{r.stdout[-1500:]}')
        print(f'  STDERR:\n{r.stderr[-1500:]}')
        failed.append((biz, shop, 'add_payment_detail'))
        continue
    print('  ' + '\n  '.join(r.stdout.strip().splitlines()[-3:]))

print(f'\n=== DONE; failed: {len(failed)}')
for b, s, p in failed:
    print(f'  - {b} / {s} : {p}')
sys.exit(1 if failed else 0)
