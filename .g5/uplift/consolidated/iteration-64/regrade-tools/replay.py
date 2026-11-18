#!/usr/bin/env python3
"""replay.py — replay the iteration-64 regrade ledger. Run from the repository root.

    python3 .g5/uplift/consolidated/iteration-64/regrade-tools/replay.py [START_COMMIT]   (default e309b116's successor 3f18ba52)

Reads obligations.tsv at START_COMMIT (git show), applies every ledger row's `changes` (JSON: column -> new value),
and compares the result with the working-tree census obligations.tsv. Prints REPLAY OK or the differing ids.
"""
import csv, io, json, subprocess, sys
sys.path.insert(0, ".g5/Verus_verification/tools")
import census  # noqa
start = sys.argv[1] if len(sys.argv) > 1 else "3f18ba52"
src = subprocess.check_output(["git", "show", f"{start}:.g5/Verus_verification/census/obligations.tsv"], text=True)
rows = list(csv.DictReader(io.StringIO(src), delimiter="\t", quoting=csv.QUOTE_NONE))
led = list(csv.DictReader(open(".g5/uplift/consolidated/iteration-64/regrade-ledger.tsv", encoding="utf-8"),
                          delimiter="\t", quoting=csv.QUOTE_NONE))
ch = {r["id"]: json.loads(r["changes"]) for r in led}
for r in rows:
    r.update(ch.get(r["id"], {}))
cur = list(csv.DictReader(open(f"{census.CEN}/obligations.tsv", encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
bad = [a["id"] for a, b in zip(rows, cur) if a != b] + (["(row count)"] if len(rows) != len(cur) else [])
print("REPLAY OK" if not bad else f"REPLAY DIFFERS: {bad[:10]}")
sys.exit(1 if bad else 0)
