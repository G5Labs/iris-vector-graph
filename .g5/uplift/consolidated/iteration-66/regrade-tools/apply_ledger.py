#!/usr/bin/env python3
"""Apply census-ledger.tsv + census-newrows.tsv to a copy of the census TSVs in DIR (or in place with --in-place),
re-hashing BLOCKHASH blocks and recounting their obligations. Usage: apply_ledger.py <repo> <ledger.tsv> <DIR|--in-place>
Column changes are applied only when the current value equals the ledger's `old` (else reported and skipped)."""
import csv, os, shutil, sys
repo, ledger, dest = sys.argv[1], sys.argv[2], sys.argv[3]
CEN = f"{repo}/.g5/Verus_verification/census"
sys.path.insert(0, f"{repo}/.g5/Verus_verification/tools")
os.chdir(repo)
import census  # noqa: E402
if dest != "--in-place":
    os.makedirs(dest, exist_ok=True)
    for f in ("obligations.tsv", "blocks.tsv", "excluded.tsv"):
        shutil.copy(f"{CEN}/{f}", f"{dest}/{f}")
    D = dest
else:
    D = CEN
orows = census.read_tsv(f"{D}/obligations.tsv", census.OBL_COLS)
brows = census.read_tsv(f"{D}/blocks.tsv", census.BLOCKS_COLS)
byid = {r["id"]: r for r in orows}
newrows = census.read_tsv(ledger.replace("census-ledger.tsv", "census-newrows.tsv"), census.OBL_COLS)
skipped, rehash = [], []
for r in csv.DictReader(open(ledger), delimiter="\t", quoting=csv.QUOTE_NONE):
    if r["column"] == "NEWROW":
        continue
    if r["column"] == "BLOCKHASH":
        rehash.append(r["id"]); continue
    row = byid[r["id"]]
    if row[r["column"]] != r["old"]:
        skipped.append((r["id"], r["column"])); continue
    row[r["column"]] = r["new"]
for n in newrows:
    if n["id"] in byid:
        skipped.append((n["id"], "NEWROW exists")); continue
    # insert after the last row of its block
    idx = max(i for i, x in enumerate(orows) if x["block"] == n["block"])
    orows.insert(idx + 1, n); byid[n["id"]] = n
onto = census.parse_ontology()
for b in brows:
    if b["block"] in rehash:
        b["sha256"] = onto[b["block"]]["sha256"]
        b["obligations"] = str(sum(1 for x in orows if x["block"] == b["block"]))
        b["iteration"] = "66"
census.write_tsv(f"{D}/obligations.tsv", census.OBL_COLS, orows)
census.write_tsv(f"{D}/blocks.tsv", census.BLOCKS_COLS, brows)
print("applied; skipped:", skipped, "rehashed:", rehash)
