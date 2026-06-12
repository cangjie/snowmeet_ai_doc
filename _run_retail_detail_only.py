"""仅重跑 5 个 retail detail_merged 脚本（前一轮 mi7 列缺失全失败）"""
import subprocess
import sys
sys.stdout.reconfigure(encoding='utf-8')

DOC = 'D:/snowmeet/snowmeet_ai_doc'
PY = sys.executable

JOBS = [
    ('retail / nanshan',         [f'{DOC}/add_retail_detail_merged_xlsx.py']),
    ('retail / chongli',         [f'{DOC}/add_chongli_retail_detail_merged_xlsx.py']),
    ('retail / wanlong',         [f'{DOC}/add_wanlong_retail_detail_merged_xlsx.py']),
    ('retail / wanlong_service', [f'{DOC}/add_wanlong_service_retail_detail_merged_xlsx.py']),
    ('retail / headquarters',    [f'{DOC}/add_headquarters_retail_detail_merged_xlsx.py']),
]

failed = []
for i, (label, args) in enumerate(JOBS, 1):
    print(f'\n[{i}/{len(JOBS)}] {label}')
    r = subprocess.run([PY] + args, cwd=DOC, capture_output=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f'  FAILED rc={r.returncode}')
        print(f'  STDOUT:\n{r.stdout[-1500:]}')
        print(f'  STDERR:\n{r.stderr[-1500:]}')
        failed.append(label)
        continue
    tail = r.stdout.strip().splitlines()[-3:]
    print('  ' + '\n  '.join(tail))

print(f'\n=== DONE; failed: {len(failed)}')
for f in failed: print(f'  - {f}')
sys.exit(1 if failed else 0)
