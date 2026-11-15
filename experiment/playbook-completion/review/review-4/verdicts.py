#!/usr/bin/env python3
"""Review 4: one verdict per in-scope run record (221), from the re-hash, the Verus log comparison
(verus_logs.py), the writesets slice (writesets/ws-review.json), the semantics slice (semantics/sem_logs.out and
specificity.txt) and the reviewer's reading of the remaining logs. Writes review-4/evidence-verdicts.json."""
import json, os, sys
from pathlib import Path
here = Path(__file__).resolve().parent
run_dir = Path(os.environ["RUN_DIR"])
ids = [Path(l).stem for l in (here / "scope-records.txt").read_text().split()]
rehash = {r["id"]: r for r in json.load(open(run_dir / "review-4" / "rehash.json"))}
ws = json.load(open(here / "writesets" / "ws-review.json"))["evidence"]
FUNC = {"proofs-d1d-f0701-build-in-place": "3 errors = failing functions; log has 4 error diagnostics",
        "proofs-d1d-r2-f0701-build-in-place": "3 errors = failing functions; log has 4 error diagnostics",
        "proofs-d1e-f1004-create-moves-no-token": "1 error = failing function; log has 2 error diagnostics",
        "proofs-d9b-f1302-unlocked-start": "2 errors = failing functions; log has 3 error diagnostics",
        "proofs-pa3-fc0401-write-before-gen": "1 error = failing function; log has 2 error diagnostics",
        "proofs-pa3-hd0401-erase-kills-gen": "3 errors = failing functions; log has 6 error diagnostics",
        "proofs-pa3-hd0401-rebuild-kills-gen": "2 errors = failing functions; log has 3 error diagnostics"}
SEM_PARTIAL = {f"sem-mc-{f}-as-built" for f in "retry excl derived removal queue cap catalog sys00".split()} | \
              {f"sem-control-{f}" for f in "retry excl derived removal queue catalog sys00".split()}
out = {}
for i in ids:
    v, notes = "MATCH", []
    if rehash[i]["log"] != "ok":
        v = "MISMATCH"; notes.append("log hash " + rehash[i]["log"])
    if i.startswith(("proofs-d9b-", "proofs-pa3-")) and i not in ("proofs-d9b-recheck", "proofs-pa3-recheck"):
        v = "PARTIAL"; notes.append("verified count and counterexample result only in the JSON log, which neither the record nor the log pins (RC-E1); reproduced by review-4 rerun")
    if i in FUNC:
        v = "PARTIAL"; notes.append(FUNC[i] + " (convention erratum exists only for proofs-breadth-hd0401)")
    if i in SEM_PARTIAL:
        v = "PARTIAL"; notes.append("'each a violation of exactly its law': the other laws are excluded by Keep::only; the complement run shows other laws violated too (semantics/specificity.txt)")
    if i == "sem-mc-all":
        notes.append("controls 59, not 61: corrected by evidence/errata.json")
    if i.startswith("ws-"):
        w = ws[i] if isinstance(ws[i], str) else ws[i].get("verdict", "")
        v = "MISMATCH" if w.startswith("MISMATCH") else "PARTIAL" if w.startswith("PARTIAL") else v
        if w != "MATCH": notes.append(w)
    if i in ("rf-premise-map-check",):
        v = "PARTIAL"; notes.append("'39 S1', the four detected finding ids and '7 product-defect triage rules' are not in the log")
    if i in ("rf-root-causes-check", "rf-root-causes-check-r2"):
        v = "PARTIAL"; notes.append("'260 audit records in 25 files' and '7 conditional (5 intent-undecided, 2 blocked-access)' are not in the log")
    if i.startswith("proofs-d1d-") and not i.startswith("proofs-d1d-r2-") and i != "proofs-d1d-recheck":
        notes.append("round r1, superseded by r2 (PROOFS.md:31-35, :349) but no errata entry; r1 cx_f0818 and witness_cys began at a constructed state")
    if i in ("proofs-d1c-recheck", "proofs-d1d-recheck", "proofs-d1e-recheck", "proofs-d1f-recheck"):
        notes.append("observes gives no counts, sources or result; the log carries them")
    if i == "verify-full-b25d84b9":
        notes.append("'seven proof gates' corrected to eight by evidence/errata.json; 35/35 steps exit 0, step hashes ok")
    out[i] = {"verdict": v, "notes": notes, "log_rehash": rehash[i]["log"]}
from collections import Counter
json.dump({"_doc": __doc__, "counts": dict(Counter(x["verdict"] for x in out.values())), "records": out},
          open(here / "evidence-verdicts.json", "w"), indent=1)
print(len(out), dict(Counter(x["verdict"] for x in out.values())))
