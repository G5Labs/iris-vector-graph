#!/usr/bin/env python3
"""Merge census fragments onto a base census dir.
usage: merge.py BASE_DIR OUT_DIR FRAG_DIR [FRAG_DIR...]
Each FRAG_DIR may hold blocks.tsv (rows REPLACE base rows of the same block; must be not-started in base),
obligations.tsv and excluded.tsv (rows APPENDED; ids must be new), owner-updates.tsv (two columns, no header:
exclusion_id<TAB>new_owner; only the owner column of an existing base exclusion is changed).
Headers must equal the census headers. Output rows follow the base blocks order; obligations/exclusions are
appended after base rows, grouped by the base blocks order. Then run, from the repo root:
  python3 .g5/Verus_verification/tools/census.py --dir OUT_DIR
"""
import csv, os, sys
sys.path.insert(0, os.path.join(os.environ.get("REPO", "."), ".g5/Verus_verification/tools"))
B = ["block", "page", "kind", "sha256", "status", "obligations", "excluded", "structural_zero", "parent", "children", "owners_checked", "iteration"]
O = ["id", "block", "locator", "statement", "cases", "observation", "model_locators", "premises", "grade", "design_check", "check_scope", "design_receipts", "as_built", "parent_entailment", "gap", "grade_source", "iteration"]
E = ["id", "block", "locator", "kind", "owner", "reason", "iteration"]
def rd(p, cols, need=False):
    if not os.path.exists(p):
        if need: sys.exit(f"missing {p}")
        return []
    with open(p, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        if r.fieldnames != cols: sys.exit(f"{p}: header {r.fieldnames} != {cols}")
        rows = list(r)
    for x in rows:
        if None in x or any(v is None for v in x.values()): sys.exit(f"{p}: wrong column count in row {x.get(cols[0])}")
        for v in x.values():
            if "\t" in v or "\n" in v: sys.exit(f"{p}: tab/newline inside a cell: {x[cols[0]]}")
    return rows
def wr(p, cols, rows):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows: f.write("\t".join(r[c] for c in cols) + "\n")
base, out, frags = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, exist_ok=True)
bb = rd(f"{base}/blocks.tsv", B, True); bo = rd(f"{base}/obligations.tsv", O, True); be = rd(f"{base}/excluded.tsv", E, True)
idx = {r["block"]: i for i, r in enumerate(bb)}
oids = {r["id"] for r in bo}; eids = {r["id"]: r for r in be}
touched = {}
newo, newe = [], []
for fd in frags:
    for r in rd(f"{fd}/blocks.tsv", B):
        b = r["block"]
        if b not in idx: sys.exit(f"{fd}: unknown block {b}")
        if b in touched: sys.exit(f"{fd}: block {b} already supplied by {touched[b]}")
        old = bb[idx[b]]
        if old["status"] != "not-started": sys.exit(f"{fd}: block {b} is already {old['status']} in base")
        for c in ("page", "kind", "sha256", "parent", "children"):
            if r[c] != old[c]: sys.exit(f"{fd}: block {b} identity column {c} changed ({r[c]!r} != {old[c]!r})")
        touched[b] = fd; bb[idx[b]] = r
    for r in rd(f"{fd}/obligations.tsv", O):
        if r["id"] in oids: sys.exit(f"{fd}: duplicate obligation {r['id']}")
        oids.add(r["id"]); newo.append(r)
    for r in rd(f"{fd}/excluded.tsv", E):
        if r["id"] in eids: sys.exit(f"{fd}: duplicate exclusion {r['id']}")
        eids[r["id"]] = r; newe.append(r)
    up = f"{fd}/owner-updates.tsv"
    if os.path.exists(up):
        for line in open(up, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip(): continue
            xid, own = line.split("\t")
            if xid not in eids or eids[xid] in newe: sys.exit(f"{fd}: owner update for unknown base exclusion {xid}")
            if eids[xid]["kind"] != "restatement": sys.exit(f"{fd}: owner update on non-restatement {xid}")
            eids[xid]["owner"] = own
for r in newo + newe:
    if r["block"] not in touched: sys.exit(f"row {r['id']} names block {r['block']} not supplied by any fragment")
key = lambda r: (idx[r["block"]], r["id"])
wr(f"{out}/blocks.tsv", B, bb)
wr(f"{out}/obligations.tsv", O, bo + sorted(newo, key=key))
wr(f"{out}/excluded.tsv", E, be + sorted(newe, key=key))
print(f"merged {len(touched)} blocks, +{len(newo)} obligations, +{len(newe)} exclusions -> {out}")
