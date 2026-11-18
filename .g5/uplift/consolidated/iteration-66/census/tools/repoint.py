"""Repoint census receipt citations to the latest receipt of the same model, kind and label (run from the repo root).

    python3 repoint.py [--models native_admission,erasure_stores] [--dry-run]

Only a citation under .g5/Verus_verification/results/<model>/ that is no longer the latest of its kind/label is
rewritten, and only when the latest carries the expected verdict (PASS / AGREES / EXPECTED_FAIL). Prints each change.
Use after a model's proof, controls or binding were re-run (as the iteration-65 master did for 105 cells)."""
import json, os, re, sys
sys.path.insert(0, '.g5/Verus_verification/tools')
import census as C
models = None
if '--models' in sys.argv:
    models = set(sys.argv[sys.argv.index('--models') + 1].split(','))
dry = '--dry-run' in sys.argv
rows = C.read_tsv(f'{C.CEN}/obligations.tsv', C.OBL_COLS)
PAT = re.compile(r'\.g5/Verus_verification/results/([^/]+)/[^/ ;]+/receipt\.json')


def key_of(path):
    d = json.load(open(path))
    kind = d.get('kind')
    if kind == 'playbook-crate-rerun':
        return None, None
    if 'control' in d and isinstance(d['control'], dict):
        return ('control', d['control'].get('name')), 'EXPECTED_FAIL'
    return (kind, None), ('AGREES' if kind == 'binding' else 'PASS')


n = 0
for r in rows:
    for col in ('design_receipts', 'as_built'):
        def sub(m):
            global n
            path, model = m.group(0), m.group(1)
            if (models and model not in models) or not os.path.exists(path):
                return path
            key, want = key_of(path)
            if key is None:
                return path
            lat = C.latest_receipts(f'{C.V}/results/{model}').get(key)
            if lat and lat != path and json.load(open(lat)).get('verdict') == want:
                print(f"{r['id']}\t{col}\t{path}\t->\t{lat}")
                n += 1
                return lat
            return path
        r[col] = PAT.sub(sub, r[col])
if not dry:
    C.write_tsv(f'{C.CEN}/obligations.tsv', C.OBL_COLS, rows)
print(f'# {n} citation(s) repointed{" (dry run)" if dry else ""}', file=sys.stderr)
