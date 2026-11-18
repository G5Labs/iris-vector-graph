#!/usr/bin/env python3
"""stats.py BEFORE_DIR — per-page before/after census table (markdown) for the iteration-64 handoff."""
import csv, collections, sys
sys.path.insert(0, ".g5/Verus_verification/tools")
import census  # noqa
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
B = rd(sys.argv[1] + "/obligations.tsv"); A = rd(f"{census.CEN}/obligations.tsv")
page = {r["block"]: r["page"].split("ontology/")[1].replace(".g5.md", "") for r in rd(f"{census.CEN}/blocks.tsv")}
def tally(rows):
    t = collections.defaultdict(collections.Counter)
    for r in rows:
        for k in (page[r["block"]], "**whole foundation**"):
            t[k][r["grade"]] += 1; t[k]["n"] += 1
            if r["design_check"] == "proved" and r["check_scope"] == "full": t[k]["pf"] += 1
            t[k][r["design_check"]] += 1
    return t
tb, ta = tally(B), tally(A)
print("| page | total | full before | full after | partial after | absent after | full/total before | after | pr-full before | after | refuted after |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for k in sorted(ta, key=lambda x: (x.startswith("**"), x)):
    b, a = tb[k], ta[k]
    print(f"| {k} | {a['n']} | {b['full']} | {a['full']} | {a['partial']} | {a['absent']} | {100*b['full']/b['n']:.1f}% | "
          f"{100*a['full']/a['n']:.1f}% | {b['pf']} | {a['pf']} | {a['refuted']} |")
