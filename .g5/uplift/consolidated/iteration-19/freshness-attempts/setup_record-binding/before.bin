"""setup_record binding: the model's port against two recorded native lifecycle runs on the fresh namespace W21 of the
run-isolated fixture (iteration-19/setup-lifecycle-observed-*.json). Creating a namespace needs %SYS, so this binding
compares recorded observations instead of re-running setup; the probe that produced them is setup_lifecycle_probe.py."""
import glob, hashlib, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
OBS = sorted(glob.glob(str(REPO / ".g5/uplift/consolidated/iteration-19/setup-lifecycle-observed-*.json")))
T = "Graph_KG"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def decide(rec, held, t, explicit, rules):
    if rec is not None:
        return "existing" if (rec == t or rules.get("mismatch_adopts")) else "Refused"
    if not held: return "new"
    if not (held - {t}): return "new" if rules.get("unrecorded_tables_new") else "inferred"
    return "explicit" if (explicit or rules.get("unnamed_other_schema_recorded")) else "Refused"
def setup(rec, held, t, explicit, dry, rules):
    how = decide(rec, held, t, explicit, rules)
    if (dry and not rules.get("dry_run_writes")) or how == "Refused": return rec, held, how
    return t, held | {t}, how
def state(snap): return snap["schema_record"], ({T} if snap["tables"] else set())
def check(rules=None):
    rules = rules or {}; cells = []
    for f in OBS:
        steps = json.load(open(f))["steps"]
        for prev, s in zip(steps, steps[1:]):
            if "report" not in s: continue
            t = "W21Other" if s["step"].startswith("7") else T
            rec, held = state(prev["snapshot"])
            rec2, held2, how = setup(rec, held, t, False, s.get("dry_run", False), rules)
            obs_how = "Refused" if s.get("error") else s["report"]["schema_recorded"]
            obs_rec, obs_held = state(s["snapshot"])
            unchanged = s["snapshot"] == prev["snapshot"]
            want_unchanged = (rec2, held2) == (rec, held)
            cells.append({"file": Path(f).name, "step": s["step"], "expected": [how, rec2, sorted(held2), want_unchanged],
                          "observed": [obs_how, obs_rec, sorted(obs_held), unchanged]})
    return cells
def main():
    start = time.monotonic(); cells = check()
    mism = [c for c in cells if c["expected"] != c["observed"]]
    sens = {r: sum(1 for a, b in zip(check({r: True}), cells) if a["expected"] != b["observed"])
            for r in ["dry_run_writes", "mismatch_adopts", "unrecorded_tables_new", "unnamed_other_schema_recorded"]}
    body = {"kind": "binding", "model": "setup_record", "verdict": "AGREES" if not mism else "DISAGREES", "cells": cells,
            "comparisons": 4 * len(cells), "mismatches": mism, "sensitivities_detected_cells": sens,
            "observation_files": {Path(f).name: sha(f) for f in OBS}, "elapsed_s": time.monotonic() - start,
            "inputs": {str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "setup_record.rs", HERE / "model.json"]},
            "scope": "Recorded native lifecycle runs (fresh namespace W21, IRIS 2026.1): dry/real/dry/real, record removed then dry/real, "
                     "and a mismatching engine. The explicit-name case with tables in another schema is modeled, not observed."}
    out = REPO / ".g5/Verus_verification/results/setup_record" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "comparisons", "sensitivities_detected_cells")})); [print("MISMATCH", m) for m in mism]
if __name__ == "__main__":
    main()
