#!/usr/bin/env python3
"""merge.py BEFORE_DIR OUT_LEDGER [--apply] — iteration-64 regrade merge. Run from the repository root.

Layers, in order, onto BEFORE_DIR/obligations.tsv (the census at the start commit):
  1. every fork's rows.tsv   (scratch/iteration-64/forks/G*/rows.tsv; 17 census columns + reason)
  2. the integrator's rows   (scratch/iteration-64/integrator/rows.tsv; same format)
  3. reviewer corrections    (scratch/iteration-64/review/corrections.tsv; same format, accepted rows only)
  4. owner-contradicted tags (scratch/iteration-64/integrator/owner_contradicted.tsv: id, item, evidence) appended to
     `gap` as an `owner-contradicted: <evidence> (iteration-63 §6.1 item N)` segment joined with ' || '.
A later layer replaces the whole row. Writes OUT_LEDGER: one row per obligation whose row changed, with the old and new
grade / design_check / check_scope, whether the statement changed, the reason, and a JSON object of every changed
column's new value (enough to replay the change with replay.py). With --apply, writes the merged obligations.tsv into
the repository census. Deterministic.
"""
import csv, glob, json, os, sys

sys.path.insert(0, ".g5/Verus_verification/tools")
import census  # noqa: E402

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLS = census.OBL_COLS
LEDGER_COLS = ["id", "tranche", "old_grade", "old_check", "old_scope", "new_grade", "new_check", "new_scope",
               "statement_changed", "layer", "reason", "changes"]


def read(path, cols):
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        if r.fieldnames != cols:
            raise SystemExit(f"{path}: header {r.fieldnames} != {cols}")
        return list(r)


def main(argv):
    before_dir, out_ledger = argv[0], argv[1]
    base = read(os.path.join(before_dir, "obligations.tsv"), COLS)
    old = {r["id"]: r for r in base}
    cur = {r["id"]: dict(r) for r in base}
    why = {}
    layer = {}
    layers = [(f, os.path.basename(os.path.dirname(f))) for f in sorted(glob.glob(f"{S}/forks/G*/rows.tsv"))]
    layers.append((f"{S}/integrator/rows.tsv", "integrator"))
    if os.path.exists(f"{S}/review/corrections.tsv"):
        layers.append((f"{S}/review/corrections.tsv", "reviewer"))
    seen_in = {}
    for path, name in layers:
        for r in read(path, COLS + ["reason"]):
            oid = r["id"]
            if oid not in cur:
                raise SystemExit(f"{name}: unknown id {oid}")
            if name.startswith("G") and oid in seen_in:
                raise SystemExit(f"{oid} in two fork groups ({seen_in[oid]}, {name})")
            if name.startswith("G"):
                seen_in[oid] = name
            if r["block"] != old[oid]["block"]:
                raise SystemExit(f"{name}: {oid} changes its block")
            new = {c: r[c] for c in COLS}
            if new != cur[oid]:
                why[oid] = r["reason"] if oid not in why else (why[oid] + " || " + name + ": " + r["reason"])
                layer[oid] = name if oid not in layer else layer[oid] + "+" + name
            cur[oid] = new
    oc = read(f"{S}/integrator/owner_contradicted.tsv", ["id", "item", "evidence"])
    for e in oc:
        oid = e["id"]
        if oid not in cur:
            raise SystemExit(f"owner_contradicted: unknown id {oid}")
        seg = f"owner-contradicted: {e['evidence']} (iteration-63 §6.1 item {e['item']})"
        g = cur[oid]["gap"].strip()
        if g.lower() in ("", "none", "-", "n/a"):
            g = ""
        if "owner-contradicted:" in g:
            continue  # a fork already tagged it; keep the fork's evidence
        cur[oid]["gap"] = seg if not g else g + census.GAP_SEP + seg
        if cur[oid]["iteration"] != "64":
            cur[oid]["iteration"] = "64"
        note = f"gap tagged owner-contradicted (§6.1 item {e['item']})"
        why[oid] = note if oid not in why else why[oid] + "; " + note
        layer[oid] = "owner-tag" if oid not in layer else layer[oid] + "+owner-tag"
    ledger = []
    for r in base:
        oid = r["id"]
        n = cur[oid]
        if n == r:
            continue
        ch = {c: n[c] for c in COLS if n[c] != r[c]}
        ledger.append({"id": oid, "tranche": "1" if r["iteration"] in ("61", "62") else "2",
                       "old_grade": r["grade"], "old_check": r["design_check"], "old_scope": r["check_scope"],
                       "new_grade": n["grade"], "new_check": n["design_check"], "new_scope": n["check_scope"],
                       "statement_changed": "yes" if n["statement"] != r["statement"] else "no",
                       "layer": layer.get(oid, ""), "reason": why.get(oid, "").replace("\t", " "),
                       "changes": json.dumps(ch, ensure_ascii=False, sort_keys=True)})
    census.write_tsv(out_ledger, LEDGER_COLS, ledger)
    print(f"ledger rows: {len(ledger)} -> {out_ledger}")
    if "--apply" in argv:
        census.write_tsv(f"{census.CEN}/obligations.tsv", COLS, [cur[r["id"]] for r in base])
        print("obligations.tsv written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
