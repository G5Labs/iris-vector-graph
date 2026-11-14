# Copied from $RUN_DIR/refusals/17/make_fragment.py (fork A). Usage: python make_audit_17.py <refusals dir> <results.json>;
# it reads fragment-meta.json next to the results file (a copy is refusals/audit-meta-17.json).
"""Compose refusals/audit/17.json from the registered rx-live-17 log (case names copied, not retyped)."""
import json, os, sys
LANE = sys.argv[1]
RES = sys.argv[2]
xs = {s['id']: s for s in json.load(open(f'{LANE}/x-statements.json'))['statements']}
d = json.load(open(RES))
cases = {}
for c in d['cases']:
    st = c.get('statement')
    if st and st.startswith('OPS-') and c.get('outcome') not in ('observation', None):
        cases.setdefault(st, []).append(c)
R = "run:rx-live-17"
META = json.load(open(f'{os.path.dirname(RES)}/fragment-meta.json'))
out = []
for sid in [s for s in xs if s.startswith('OPS-')]:
    m = META[sid]
    e = {"id": sid, "text": xs[sid]['text'], "outcome": m['outcome'], "implementing_code": m['code'],
         "evidence": m.get('evidence', [R]), "notes": m['notes']}
    if m['outcome'] in ('holds-live', 'product-defect') and sid in cases:
        sel = m.get('cases')
        names = [c['case'] for c in cases[sid] if (sel is None or any(k in c['case'] for k in sel))]
        if m['outcome'] == 'holds-live':
            bad = [c['case'] for c in cases[sid] if c['case'] in names and c['outcome'] != 'holds-live']
            assert not bad, (sid, bad)
        e['live_cases'] = names
    for k in ('finding', 'dependency', 'log_contains', 'absent'):
        if k in m:
            e[k] = m[k]
    out.append(e)
json.dump({"module": "17", "code": "OPS", "lane": "refusals", "statements": out}, open(f'{LANE}/audit/17.json', 'w'), indent=1)
print(len(out))
