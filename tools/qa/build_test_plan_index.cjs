// Documentation utility only: reads Markdown and writes the case index.
// Does not execute tests, access the network, start services, or connect to databases.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const plan = path.join(root, 'docs/testing/2026-09-30-copilot-test-plan.md');
const output = path.join(root, 'docs/testing/2026-09-30-copilot-test-cases.json');
const source = fs.readFileSync(plan, 'utf8');
const cases = [];
const ids = new Set();
const fixtureKeys = new Set(['ID', 'STAFF', 'SHOP', 'RENT', 'MONEY', 'CARE', 'CARD', 'COUPON', 'FNB', 'FNB-V', 'AI', 'UI']);
const modeEvidence = {
  S: ['source'], A: ['test_log'], B: ['http', 'db_before', 'db_after'],
  C: ['screenshot', 'console', 'network'], D: ['manual_record']
};
let section = '';
for (const line of source.split(/\r?\n/)) {
  if (/^### 6\./.test(line)) section = line.slice(4);
  if (!/^\| [A-Z]+-\d{2} \| P[012] \|/.test(line)) continue;
  const fields = line.split('|').slice(1, -1).map(x => x.trim());
  if (fields.length !== 5) throw new Error('Unexpected columns: ' + line);
  const [id, priority, modesText, fixturesText, actionsAndAssertions] = fields;
  if (ids.has(id)) throw new Error('Duplicate case: ' + id);
  if (!/^P[012]$/.test(priority)) throw new Error('Invalid priority: ' + id);
  if (!section) throw new Error('Missing section: ' + id);
  const modes = modesText.split('+');
  for (const mode of modes) if (!modeEvidence[mode]) throw new Error('Invalid mode: ' + id);
  const fixtures = fixturesText.split(',');
  for (const fixture of fixtures) if (!fixtureKeys.has(fixture)) throw new Error('Unknown fixture: ' + id + '/' + fixture);
  ids.add(id);
  cases.push({
    id, section, priority, required_modes: modes, fixture_keys: fixtures,
    actions_and_assertions: actionsAndAssertions,
    initial_status: modes.includes('D') ? 'MANUAL_REQUIRED' : 'NOT_RUN',
    mode_evidence: Object.fromEntries(modes.map(mode => [mode, modeEvidence[mode]]))
  });
}
if (cases.length < 100) throw new Error('Unexpectedly small case catalog');
const traceability = [];
function expandIds(value) {
  return value.trim().split(/,\s*/).flatMap(token => {
    const range = /^([A-Z]+)-(\d{2})\.\.\1-(\d{2})$/.exec(token);
    if (!range) return [token];
    const start = Number(range[2]);
    const end = Number(range[3]);
    if (end < start) throw new Error('Reversed range: ' + token);
    return Array.from({ length: end - start + 1 }, (_, n) => range[1] + '-' + String(start + n).padStart(2, '0'));
  });
}
const featureCoverage = [];
for (const line of source.split(/\r?\n/)) {
  const match = /^\| ([45]\.\d+) \| ([^|]+) \| ([^|]+) \|$/.exec(line);
  if (!match) continue;
  const mapped = expandIds(match[3]);
  for (const id of mapped) if (!ids.has(id)) throw new Error('Unknown feature mapping: ' + id);
  featureCoverage.push({ inventory_section: match[1], feature: match[2].trim(), case_ids: mapped });
}
const requiredFeatures = [
  ...Array.from({ length: 9 }, (_, n) => '4.' + (n + 1)),
  ...Array.from({ length: 16 }, (_, n) => '5.' + (n + 1))
];
if (featureCoverage.length !== 25 || featureCoverage.some((entry, n) => entry.inventory_section !== requiredFeatures[n])) {
  throw new Error('Expected feature coverage for 4.1..4.9 and 5.1..5.16');
}
for (const line of source.split(/\r?\n/)) {
  const match = /^\| (\d+) \| ([^|]+) \| ([^|]+) \|$/.exec(line);
  if (!match) continue;
  const mapped = match[3].trim().split(/,\s*/);
  for (const id of mapped) if (!ids.has(id)) throw new Error('Unknown regression mapping: ' + id);
  traceability.push({ inventory_regression: Number(match[1]), topic: match[2].trim(), case_ids: mapped });
}
if (traceability.length !== 35 || traceability.some((entry, index) => entry.inventory_regression !== index + 1)) {
  throw new Error('Expected regression mappings 1..35 exactly once');
}
// Validate all case references in the plan, not just the regression table.
for (const match of source.matchAll(/\b(?:BASE|AUTH|REC|RENT|PAY|CARE|CARD|MEMBER|DEPOSIT|RETAIL|TICKET|FNB|AI|SKI|OA|STAFF|WEB|ALI|COMMON|MAN)-\d{2}\b/g)) {
  if (!ids.has(match[0])) throw new Error('Unresolved case reference: ' + match[0]);
}
const counts = {};
for (const item of cases) counts[item.priority] = (counts[item.priority] || 0) + 1;
const index = {
  schema_version: 1,
  authored_date: '2026-09-30',
  source: '2026-09-30-copilot-test-plan.md',
  description: 'Planning catalog, not execution results. Split every required mode and parameter variant into result records; all required records must pass for parent PASS.',
  case_count: cases.length,
  priority_counts: counts,
  allowed_statuses: ['NOT_RUN', 'PASS', 'FAIL', 'BLOCKED_ENV', 'BLOCKED_SCHEMA', 'BLOCKED_TOOL', 'NOT_IMPLEMENTED_TEST', 'NEEDS_DECISION', 'MANUAL_REQUIRED', 'OUT_OF_SCOPE_APPROVED'],
  gates: { B: 'plan section 2.3', C: 'plan section 2.4', D: 'human execution only' },
  cases,
  inventory_feature_coverage: featureCoverage,
  inventory_regression_traceability: traceability
};
fs.writeFileSync(output, JSON.stringify(index, null, 2) + '\n', 'utf8');
console.log(JSON.stringify({ output, cases: cases.length, priority_counts: counts, feature_sections: featureCoverage.length, regression_mappings: traceability.length }));
