#!/usr/bin/env python3
"""overlay.py OUTDIR ROWS.tsv [ROWS.tsv ...] — run from the repository root.

ROWS.tsv: the 17 obligations.tsv columns plus a final `reason` column, one row per reviewed obligation (an existing id;
no additions or removals). Copies the start-of-iteration census (scratch/iteration-64/before/*.tsv) into OUTDIR,
replaces those rows, runs `census.py --dir OUTDIR` (all checks + strict-grade lint) and prints the problems that name
one of the given ids, then a change summary. Exit 0 when no problem names a given id.
"""
import csv, os, shutil, subprocess, sys

sys.path.insert(0, ".g5/Verus_verification/tools")
import census  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEFORE = os.path.join(HERE, "before")
COLS = census.OBL_COLS


def read(path, cols):
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        if r.fieldnames != cols:
            raise SystemExit(f"{path}: header {r.fieldnames} != {cols}")
        return list(r)


def main(argv):
    out, files = argv[0], argv[1:]
    os.makedirs(out, exist_ok=True)
    for n in ("blocks.tsv", "excluded.tsv"):
        shutil.copy(os.path.join(BEFORE, n), os.path.join(out, n))
    base = read(os.path.join(BEFORE, "obligations.tsv"), COLS)
    idx = {r["id"]: i for i, r in enumerate(base)}
    new = {}
    bad = []
    for f in files:
        for r in read(f, COLS + ["reason"]):
            if r["id"] not in idx:
                bad.append(f"unknown id {r['id']} in {f}")
                continue
            if r["id"] in new:
                bad.append(f"duplicate id {r['id']} in {f}")
            for c in COLS + ["reason"]:
                if r.get(c) is None or "\t" in r[c] or "\n" in r[c]:
                    bad.append(f"{r['id']}: bad cell {c}")
            if r["block"] != base[idx[r["id"]]]["block"]:
                bad.append(f"{r['id']}: block changed")
            new[r["id"]] = r
    rows = [dict((c, new[r["id"]][c]) for c in COLS) if r["id"] in new else r for r in base]
    census.write_tsv(os.path.join(out, "obligations.tsv"), COLS, rows)
    p = subprocess.run([sys.executable, ".g5/Verus_verification/tools/census.py", "--dir", out],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    import re
    pat = re.compile(r"^- FAIL: (?:LINT-\S+ |as_built |exclusion )?(\S+?):")
    mine = [l for l in p.stdout.splitlines() if (m := pat.match(l)) and m.group(1) in new]
    for b in bad:
        print("ERROR:", b)
    for l in mine:
        print(l)
    ch = {}
    for i, r in new.items():
        o = base[idx[i]]
        k = f"{o['grade']}->{r['grade']}"
        ch[k] = ch.get(k, 0) + 1
        if o["check_scope"] != r["check_scope"]:
            k = f"scope {o['check_scope']}->{r['check_scope']}"
            ch[k] = ch.get(k, 0) + 1
        if o["statement"] != r["statement"]:
            ch["statement changed"] = ch.get("statement changed", 0) + 1
    print(f"rows reviewed: {len(new)}; problems naming them: {len(mine)}; errors: {len(bad)}")
    for k in sorted(ch):
        print(f"  {k}: {ch[k]}")
    return 1 if (mine or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
