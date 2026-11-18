#!/usr/bin/env python3
"""sample.py BEFORE_DIR OUT_DIR — deterministic stratified review sample (iteration 64). Run from the repo root.
Strata (disjoint), ranked by sha256('it64-review:' + id), first N of each:
  T1-full   10  full after regrade, tranche 1 (iteration 61/62), empty gap at start
  T2-full   10  full after regrade, tranche 2 (iteration 63), empty gap at start
  GAP-full  10  full after regrade that had a non-empty gap at start (either tranche)
  DOWN      10  full at start, partial or absent after
  UP         5  absent at start, partial or full after
  ABS        5  absent at start and after
Writes OUT_DIR/sample.tsv (id, stratum) and OUT_DIR/blind.md (no grades, checks, scopes, gaps, sources or reasons)."""
import csv, hashlib, os, re, sys
sys.path.insert(0, ".g5/Verus_verification/tools")
import census  # noqa
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import show  # noqa

def rd(p):
    return {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)}

before, out = sys.argv[1], sys.argv[2]
B = rd(os.path.join(before, "obligations.tsv"))
A = rd(f"{census.CEN}/obligations.tsv")
emp = lambda g: g.strip().lower() in ("", "none", "-", "n/a")
h = lambda i: hashlib.sha256(("it64-review:" + i).encode()).hexdigest()
strata = [
    ("T1-full", 10, lambda b, a: a["grade"] == "full" and b["iteration"] in ("61", "62") and emp(b["gap"])),
    ("T2-full", 10, lambda b, a: a["grade"] == "full" and b["iteration"] == "63" and emp(b["gap"])),
    ("GAP-full", 10, lambda b, a: a["grade"] == "full" and b["grade"] == "full" and not emp(b["gap"])),
    ("DOWN", 10, lambda b, a: b["grade"] == "full" and a["grade"] != "full"),
    ("UP", 5, lambda b, a: b["grade"] == "absent" and a["grade"] != "absent"),
    ("ABS", 5, lambda b, a: b["grade"] == "absent" and a["grade"] == "absent"),
]
pick, taken = [], set()
for name, n, f in strata:
    ids = sorted((i for i in A if i not in taken and f(B[i], A[i])), key=h)[:n]
    taken |= set(ids)
    pick += [(i, name) for i in ids]
os.makedirs(out, exist_ok=True)
with open(f"{out}/sample.tsv", "w") as fh:
    fh.write("id\tstratum\n")
    for i, s in pick:
        fh.write(f"{i}\t{s}\n")
order = sorted(pick, key=lambda x: h("blind:" + x[0]))  # strata interleaved so the reviewer cannot infer them
L = ["# Blind review packet (iteration 64)", "",
     "Rows in a fixed shuffled order. For each: the block's canonical text, the obligation as stated, its cases and "
     "observation, the model locators and receipts cited, and the model premises. No grade, check, scope, gap or reason "
     "is given.", ""]
for i, _ in order:
    a = A[i]
    page, body, _m = show.block_text(a["block"])
    prem = " || ".join(s for s in re.split(r"\s*;\s*(?=requires-reviewed:|refutes:)", a["premises"])
                       if not s.strip().startswith(("requires-reviewed:", "refutes:")))
    locs = list(dict.fromkeys(census.split_list(B[i]["model_locators"]) + census.split_list(a["model_locators"])))
    L += [f"## {i}", "", f"- page: `{page}`", f"- statement: {a['statement']}", f"- cases: {a['cases']}",
          f"- observation: {a['observation']}", f"- model locators: {'; '.join(locs) or '(none)'}",
          f"- design receipts: {a['design_receipts'] or '(none)'}", f"- as-built evidence: {a['as_built'] or '(none)'}",
          f"- model premises: {prem or '(none)'}", "", "Block text:", "", "```", body, "```", ""]
open(f"{out}/blind.md", "w").write("\n".join(L))
print(len(pick), "rows")
