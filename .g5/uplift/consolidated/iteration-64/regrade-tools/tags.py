#!/usr/bin/env python3
"""tags.py OUT_TSV [--apply] — reconcile `design-verified` tags with the census (iteration 64). Run from the repo root.

ontology-format.md: `design-verified` needs model checking machinery + code linking, and "a model association
identifies relevant evidence; it does not by itself establish complete verification". Rule applied: a block keeps the
tag only when the census grades every one of its obligations full and none is an as-built refutation; a block with
zero counted obligations (structural zero) keeps its tag unchanged. Otherwise the `- design-verified` bullet is removed
(no verification tag replaces it; the block's Verus / State machines links stay). Writes OUT_TSV listing every tagged
block with its counts and the action. Only exact `- design-verified` bullets inside a block's metadata entry change.
"""
import csv, glob, re, sys
sys.path.insert(0, ".g5/Verus_verification/tools")
import census  # noqa

out, apply = sys.argv[1], "--apply" in sys.argv
rows = list(csv.DictReader(open(f"{census.CEN}/obligations.tsv", encoding="utf-8"), delimiter="\t",
                           quoting=csv.QUOTE_NONE))
by = {}
for r in rows:
    by.setdefault(r["block"], []).append(r)
B = census.parse_ontology()
res = []
for page in sorted(glob.glob(".g5/ontology/**/*.g5.md", recursive=True)):
    L = open(page, encoding="utf-8").read().split("\n")
    mi = L.index("## Metadata") if "## Metadata" in L else len(L)
    cur, drop = None, []
    for i in range(mi, len(L)):
        l = L[i]
        if l.startswith("### "):
            cur = l[4:].strip()
        elif l.startswith("## "):
            cur = None
        elif cur in B and l.strip() == "- design-verified":
            rs = by.get(cur, [])
            nf = sum(r["grade"] == "full" for r in rs)
            nref = sum(r["design_check"] == "refuted" for r in rs)
            keep = (not rs) or (nf == len(rs) and nref == 0)
            res.append({"block": cur, "page": page, "obligations": str(len(rs)), "full": str(nf),
                        "refuted": str(nref), "action": "kept" if keep else "removed",
                        "why": ("structural zero" if not rs else "every obligation full, none refuted") if keep else
                        (f"{len(rs) - nf} of {len(rs)} obligations not full" + (f"; {nref} as-built refutation(s)" if nref else ""))})
            if not keep:
                drop.append(i)
    if apply and drop:
        for i in reversed(drop):
            del L[i]
        open(page, "w", encoding="utf-8").write("\n".join(L))
census.write_tsv(out, ["block", "page", "obligations", "full", "refuted", "action", "why"], res)
print(f"design-verified blocks: {len(res)}; kept {sum(r['action'] == 'kept' for r in res)}; "
      f"removed {sum(r['action'] == 'removed' for r in res)}")
