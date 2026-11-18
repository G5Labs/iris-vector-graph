#!/usr/bin/env python3
"""Census before (git rev, default fb6660a0) vs the working tree: whole foundation and per page, with the retained
obligations (ids present before) separated from the scope change (ids added). Run from the repository root.

    python3 census_delta.py [REV] > census-delta.md
"""
import collections
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".g5/Verus_verification/tools")
import census as C  # noqa: E402

REV = sys.argv[1] if len(sys.argv) > 1 else "fb6660a0"
GR = ("full", "partial", "absent", "unassessed")


def load_rev(name, cols):
    txt = subprocess.check_output(["git", "show", f"{REV}:.g5/Verus_verification/census/{name}"], text=True)
    tmp = Path(f"/tmp/census_delta_{name}")
    tmp.write_text(txt)
    return C.read_tsv(str(tmp), cols)


def pages(blocks):
    return {b["block"]: b["page"].replace(".g5/ontology/", "") for b in blocks}


def main():
    ob = {r["id"]: r for r in load_rev("obligations.tsv", C.OBL_COLS)}
    oa = {r["id"]: r for r in C.read_tsv(f"{C.CEN}/obligations.tsv", C.OBL_COLS)}
    pb = pages(load_rev("blocks.tsv", C.BLOCKS_COLS))
    pa = pages(C.read_tsv(f"{C.CEN}/blocks.tsv", C.BLOCKS_COLS))
    gone = sorted(set(ob) - set(oa))
    new = sorted(set(oa) - set(ob))
    kept = sorted(set(ob) & set(oa))

    def cnt(rows):
        c = collections.Counter(r["grade"] for r in rows)
        return [c[g] for g in GR]

    def line(label, rows):
        c = cnt(rows)
        n = sum(c)
        return f"| {label} | {c[0]} | {c[1]} | {c[2]} | {c[3]} | {n} | {100 * c[0] / n:.1f}% |" if n else f"| {label} | 0 | 0 | 0 | 0 | 0 | N/A |"

    print(f"# Census delta: {REV} -> working tree\n")
    print("| scope | full | partial | absent | unassessed | total | full/total |\n|---|---:|---:|---:|---:|---:|---:|")
    print(line(f"whole foundation, before ({REV})", ob.values()))
    print(line("whole foundation, after", oa.values()))
    print(line("retained obligations, before", [ob[i] for i in kept]))
    print(line("retained obligations, after", [oa[i] for i in kept]))
    print(line("scope change: added obligations", [oa[i] for i in new]))
    print(f"\nRemoved ids: {len(gone)} {gone[:10]}\n")
    tr = collections.Counter((ob[i]["grade"], oa[i]["grade"]) for i in kept if ob[i]["grade"] != oa[i]["grade"])
    print("Retained grade transitions:\n\n| from -> to | rows |\n|---|---:|")
    for (a, b), n in sorted(tr.items()):
        print(f"| {a} -> {b} | {n} |")
    print("\n## Per page\n")
    print("| page | full/total before | after | retained full before -> after | added (full/total) |\n|---|---:|---:|---:|---:|")
    allp = sorted(set(pb.values()) | set(pa.values()))
    for p in allp:
        b = [r for r in ob.values() if pb.get(r["block"]) == p]
        a = [r for r in oa.values() if pa.get(r["block"]) == p]
        kb = [ob[i] for i in kept if pb.get(ob[i]["block"]) == p]
        ka = [oa[i] for i in kept if pa.get(oa[i]["block"]) == p]
        ad = [oa[i] for i in new if pa.get(oa[i]["block"]) == p]
        f = lambda rows: sum(1 for r in rows if r["grade"] == "full")
        print(f"| {p} | {f(b)}/{len(b)} | {f(a)}/{len(a)} | {f(kb)} -> {f(ka)} of {len(kb)} | {f(ad)}/{len(ad)} |")


if __name__ == "__main__":
    main()
