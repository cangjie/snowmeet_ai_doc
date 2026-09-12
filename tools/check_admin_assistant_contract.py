"""跨仓契约核对：三个仓的业务域表必须一致。

reqai 的 arguments 模型、SnowmeetApi 的 AdminAssistantDomains、小程序的 adminAiDomains
是三份独立的表。它们各自都有元测试，但没有任何一处能发现「三者互相不一致」——
这个脚本就是补这一环，靠文本解析，不需要装任何依赖。
"""
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# 路径从本脚本位置推出，不写死绝对路径（本项目跨 Mac / Windows 两台机器开发）。
# 约定：本脚本在 snowmeet_ai_doc/tools/ 下，业务仓与 snowmeet_ai_doc 平级；
# reqai 是独立仓，可能与工作区平级或在上一层，两个目录名都试。
DOC_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = DOC_ROOT.parent


def _find(*candidates):
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit('找不到文件，试过：' + '、'.join(str(item) for item in candidates))


REQAI = _find(WORKSPACE / 'snowmeet_reqai' / 'backend' / 'app',
              WORKSPACE.parent / 'snowmeet_reqai' / 'backend' / 'app',
              WORKSPACE / 'reqai' / 'backend' / 'app',
              WORKSPACE.parent / 'reqai' / 'backend' / 'app')
API = _find(WORKSPACE / 'SnowmeetApi' / 'Helpers' / 'AdminAssistantDomains.cs')
MINI = _find(WORKSPACE / 'snowmeet_wechat_mini' / 'utils' / 'adminAiDomains.js')

DOMAIN_ORDER = ['rental_order.query', 'care_order.query', 'retail_order.query', 'ski_pass.query']

COMMON = ['start_date', 'end_date', 'shop', 'is_test', 'is_entertain', 'have_discount',
          'cell_suffix']


def reqai_fields():
    """从 pydantic 模型继承链推出每个域的字段集合。"""
    text = io.open(REQAI / 'admin_assistant_protocol.py', encoding='utf-8').read()
    layers = {
        'DateRangeFilters': ['start_date', 'end_date'],
        'ShopScopedFilters': COMMON,
    }
    result = {}
    mapping = {
        'rental_order.query': 'RentalOrderQueryArguments',
        'care_order.query': 'CareOrderQueryArguments',
        'retail_order.query': 'RetailOrderQueryArguments',
        'ski_pass.query': 'SkiPassQueryArguments',
    }
    for action, cls in mapping.items():
        match = re.search(r'class %s\((\w+)\):(.*?)(?=\nclass |\n# ---)' % cls, text, re.S)
        assert match, cls
        base, body = match.group(1), match.group(2)
        own = re.findall(r'^    (\w+): ', body, re.M)
        result[action] = list(dict.fromkeys(layers[base] + own))
    return result


def api_fields():
    text = io.open(API, encoding='utf-8').read()
    result = {}
    for block in re.findall(r'actionType = "([^"]+)".*?fields = Fields\((.*?)\),', text, re.S):
        action, raw = block
        result[action] = re.findall(r'"([^"]+)"', raw)
    return result


def mini_fields():
    text = io.open(MINI, encoding='utf-8').read()
    result = {}
    for block in re.findall(r"queryType: '([^']+)',.*?fields: \[(.*?)\],", text, re.S):
        action, raw = block
        result[action] = re.findall(r"'([^']+)'", raw)
    return result


def api_context_keys():
    text = io.open(API, encoding='utf-8').read()
    pairs = re.findall(r'actionType = "([^"]+)".*?contextKey = "([^"]+)"', text, re.S)
    return dict(pairs)


def mini_context_keys():
    text = io.open(MINI, encoding='utf-8').read()
    pairs = re.findall(r"queryType: '([^']+)',.*?contextKey: '([^']+)'", text, re.S)
    return dict(pairs)


def api_client_types():
    text = io.open(API, encoding='utf-8').read()
    pairs = re.findall(r'actionType = "([^"]+)".*?clientActionType = "([^"]+)"', text, re.S)
    return dict(pairs)


def mini_client_types():
    text = io.open(MINI, encoding='utf-8').read()
    pairs = re.findall(r"'([^']+\.show_results)': \{\s*queryType: '([^']+)'", text, re.S)
    return {query: show for show, query in pairs}


failures = []
reqai, api, mini = reqai_fields(), api_fields(), mini_fields()

print('=== 业务域集合 ===')
for name, table in (('reqai', reqai), ('SnowmeetApi', api), ('小程序', mini)):
    got = sorted(table)
    print('%-12s %s' % (name, got))
    if got != sorted(DOMAIN_ORDER):
        failures.append('%s 的业务域集合不是那四个：%s' % (name, got))

print('\n=== 每个域的字段集合 ===')
for action in DOMAIN_ORDER:
    sets = {'reqai': set(reqai.get(action, [])),
            'api': set(api.get(action, [])),
            'mini': set(mini.get(action, []))}
    if len(set(map(frozenset, sets.values()))) == 1:
        print('  OK  %-20s %d 个字段' % (action, len(sets['reqai'])))
    else:
        print('  差异 %s' % action)
        for name, value in sets.items():
            print('       %-6s %s' % (name, sorted(value)))
        failures.append('%s 的字段集合三仓不一致' % action)

print('\n=== contextKey 与客户端 action type ===')
api_ctx, mini_ctx = api_context_keys(), mini_context_keys()
api_client, mini_client = api_client_types(), mini_client_types()
for action in DOMAIN_ORDER:
    if api_ctx.get(action) != mini_ctx.get(action):
        failures.append('%s 的 contextKey 不一致：api=%s mini=%s'
                        % (action, api_ctx.get(action), mini_ctx.get(action)))
    if api_client.get(action) != mini_client.get(action):
        failures.append('%s 的客户端 action type 不一致：api=%s mini=%s'
                        % (action, api_client.get(action), mini_client.get(action)))
    print('  %-20s contextKey=%-20s client=%s'
          % (action, api_ctx.get(action), api_client.get(action)))

print()
if failures:
    for item in failures:
        print('FAIL ' + item)
    sys.exit(1)
print('三仓业务域契约一致。')
