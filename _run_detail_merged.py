"""跑所有 add_*_detail_merged_sheet 脚本：retail(5) + ski_pass(2) + care(5)"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = 'D:/snowmeet/snowmeet_ai_doc'
PY = sys.executable

# (描述, 命令参数列表)
JOBS = [
    # ─── retail: 各店独立脚本，hardcoded paths ───
    ('retail / nanshan',         [f'{DOC}/add_retail_detail_merged_xlsx.py']),
    ('retail / chongli',         [f'{DOC}/add_chongli_retail_detail_merged_xlsx.py']),
    ('retail / wanlong',         [f'{DOC}/add_wanlong_retail_detail_merged_xlsx.py']),
    ('retail / wanlong_service', [f'{DOC}/add_wanlong_service_retail_detail_merged_xlsx.py']),
    ('retail / headquarters',    [f'{DOC}/add_headquarters_retail_detail_merged_xlsx.py']),
    # ─── ski_pass: 崇礼 = 雪票列表 + annotate + detail；南山 = 仅 detail ───
    ('ski_pass / chongli 雪票列表 sheet', [f'{DOC}/add_skipass_list_sheet_to_chongli_fy.py']),
    ('ski_pass / chongli annotate',       [f'{DOC}/annotate_skipass_list_sheet.py']),
    ('ski_pass / chongli detail',         [
        f'{DOC}/add_skipass_detail_merged_sheet.py',
        '--xlsx', f'{DOC}/chongli_ski_pass_orders_fy_2025-05-01_2026-04-30.xlsx',
        '--shop', '崇礼旗舰店'
    ]),
    ('ski_pass / nanshan detail', [
        f'{DOC}/add_skipass_detail_merged_sheet.py',
        '--xlsx', f'{DOC}/nanshan_ski_pass_orders_fy_2025-05-01_2026-04-30.xlsx',
        '--shop', '南山'
    ]),
    # ─── care: 5 店都跑 detail merged ───
    ('care / wanlong_service', [
        f'{DOC}/add_care_detail_merged_sheet.py',
        '--xlsx', f'{DOC}/wanlong_service_care_orders_fy_2025-05-01_2026-04-30.xlsx',
        '--shop', '万龙服务中心'
    ]),
    ('care / chongli', [
        f'{DOC}/add_care_detail_merged_sheet.py',
        '--xlsx', f'{DOC}/chongli_care_orders_fy_2025-05-01_2026-04-30.xlsx',
        '--shop', '崇礼旗舰店'
    ]),
    ('care / nanshan', [
        f'{DOC}/add_care_detail_merged_sheet.py',
        '--xlsx', f'{DOC}/nanshan_care_orders_fy_2025-05-01_2026-04-30.xlsx',
        '--shop', '南山'
    ]),
    ('care / huaibei', [
        f'{DOC}/add_care_detail_merged_sheet.py',
        '--xlsx', f'{DOC}/huaibei_care_orders_fy_2025-05-01_2026-04-30.xlsx',
        '--shop', '怀北'
    ]),
    ('care / yuyang', [
        f'{DOC}/add_care_detail_merged_sheet.py',
        '--xlsx', f'{DOC}/yuyang_care_orders_fy_2025-05-01_2026-04-30.xlsx',
        '--shop', '渔阳'
    ]),
]

failed = []
for i, (label, args) in enumerate(JOBS, 1):
    print(f'\n[{i}/{len(JOBS)}] {label}')
    print(f'  $ python {os.path.basename(args[0])} {" ".join(args[1:])}')
    cmd = [PY] + args
    r = subprocess.run(cmd, cwd=DOC, capture_output=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f'  FAILED rc={r.returncode}')
        print(f'  STDOUT:\n{r.stdout[-1500:]}')
        print(f'  STDERR:\n{r.stderr[-1500:]}')
        failed.append(label)
        continue
    tail = r.stdout.strip().splitlines()[-3:]
    print('  ' + '\n  '.join(tail))

print(f'\n=== DONE; failed: {len(failed)}')
for f in failed:
    print(f'  - {f}')
sys.exit(1 if failed else 0)
