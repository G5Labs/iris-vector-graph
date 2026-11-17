#!/usr/bin/env python3
"""Iteration-57 member delta: compare two member_reach.py outputs (before = 9f74e690, after = working tree).

Union = active bindings plus the frozen baseline historical locators ($G5_RUN_STATE/baseline/historical.json,
in-census members with a citation or exact crosswalk), as master/tools/score.py counts it.
Usage: member_delta.py BEFORE_DIR AFTER_DIR OUT.json
"""
import json, os, sys
from pathlib import Path

before, after, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rs = Path(os.environ['G5_RUN_STATE'])
hist = json.loads((rs / 'baseline/historical.json').read_text())['members']


def load(d):
    bound = json.loads((d / 'bindings.json').read_text())
    census = set(json.loads((d / 'census.json').read_text()))
    hloc = {k for k, v in hist.items() if v.get('in_census') and (v.get('cited_in') or v.get('exact_crosswalk')) and k in census}
    return bound, hloc | set(bound)


b_bound, b_union = load(before)
a_bound, a_union = load(after)
new = sorted(set(a_bound) - set(b_bound))
lost = sorted(set(b_bound) - set(a_bound))
strengthened = []
for k in sorted(set(a_bound) & set(b_bound)):
    old = {(r['formal item'], r['role']) for r in b_bound[k]}
    add = [r for r in a_bound[k] if (r['formal item'], r['role']) not in old]
    if add:
        strengthened.append({'member': k, 'by': [r['formal item'].split('/')[-1] + ': ' + r['role'][:160] for r in add]})
res = {
    'before': {'revision': 'fb1f806b', 'active': len(b_bound), 'union': len(b_union)},
    'after': {'revision': 'working tree at the iteration-56 seal', 'active': len(a_bound), 'union': len(a_union)},
    'denominator': len(json.loads((after / 'census.json').read_text())),
    'newly_bound': [{'member': k, 'existing_locator': k in b_union,
                     'roles': [r['relation'] + ' ' + r['formal item'].split('/')[-1] + ': ' + r['role'][:160] for r in a_bound[k]]} for k in new],
    'newly_reached': sorted(a_union - b_union),
    'existing_locator_gaining_binding': [k for k in new if k in b_union],
    'strengthened': strengthened,
    'lost_active': lost,
    'lost_union': sorted(b_union - a_union),
}
out.write_text(json.dumps(res, indent=2) + '\n')
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}, indent=1))
