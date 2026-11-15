#!/usr/bin/env python3
"""Register the final runs in evidence/runs.json (live scenarios, upstream Community suite, model checks).

    python experiment/playbook-uplift/tools/register_all.py [--final DIR]

Inputs (default DIR = $RUN_DIR/final):
- DIR/native/summary.json and DIR/native/traces/<scenario>.json  -> live:native-<scenario>
- DIR/upstream-community-redaction.log                         -> live:upstream-community-redaction
- DIR/mc-summary.json and DIR/mc.log                            -> mc:<check id>

Every entry keeps the path of its log relative to $RUN_DIR and the log's SHA-256. `result` is "pass" only when every
check of a scenario held, or when a model check met its stated expectation (for an as-built design that expectation
is the named violation: the result is the reproduced finding, not a clean bill). The Verus section is written by
tools/run_verus.py and left alone here.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

UPLIFT = Path(__file__).resolve().parent.parent
REG = UPLIFT / "evidence" / "runs.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return "$RUN_DIR/" + str(p.resolve().relative_to(Path(os.environ["RUN_DIR"]).resolve()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", default=os.path.join(os.environ["RUN_DIR"], "final"))
    a = ap.parse_args()
    fin = Path(a.final)
    reg = json.loads(REG.read_text()) if REG.exists() else {"runs": {}}
    runs = reg.setdefault("runs", {})
    for k in [k for k in runs if k.startswith("native-") or k.startswith("mc-")]:
        del runs[k]

    summary = json.loads((fin / "native" / "summary.json").read_text())
    for name, res in sorted(summary.items()):
        trace = fin / "native" / "traces" / f"{name}.json"
        t = json.loads(trace.read_text())
        runs[f"native-{name}"] = {
            "kind": "live", "result": "pass" if res["ok"] else "fail",
            "command": f'python experiment/playbook-uplift/native/scenarios.py --only {name}',
            "observes": (t.get("doc") or "").strip(),
            "checks": res["checks"], "failed": res["failed"],
            "log": rel(trace), "log_sha256": sha(trace),
            "run_log": rel(fin / "native.log"),
        }

    up = fin / "upstream-community-redaction.log"
    if up.exists():
        text = up.read_text(errors="replace")
        m = re.search(r"(\d+) passed in ([\d.]+)s", text)
        bad = re.search(r"(\d+) (failed|error)", text)
        runs["upstream-community-redaction"] = {
            "kind": "live", "result": "pass" if m and not bad else "fail",
            "command": 'python "$RUN_DIR/run-community-redaction.py"',
            "observes": "Upstream tests/integration/test_256_ledger_redaction_e2e.py on IRIS Community 2026.1 with the "
                        f"public initialize_schema deploy: {m.group(0) if m else 'no result line'}.",
            "log": rel(up), "log_sha256": sha(up),
        }

    mut = fin / "mutants" / "mutants.json"
    if mut.exists():
        mj = json.loads(mut.read_text())
        ok = mj["restored_ok"] and all(m["killed"] for m in mj["mutants"])
        runs["native-mutants"] = {
            "kind": "live", "result": "pass" if ok else "fail",
            "command": "python experiment/playbook-uplift/native/mutants.py",
            "observes": "Mutation testing of the ObjectScript on IRIS: " + "; ".join(
                f"{m['mutant']} ({m['control']}) {'killed' if m['killed'] else 'SURVIVED'} by {sorted(m['failed_checks'])}"
                for m in mj["mutants"]) + f"; pin classes restored and all {len(mj['restored'])} scenarios passed: "
                + str(mj["restored_ok"]) + ".",
            "log": rel(mut), "log_sha256": sha(mut), "run_log": rel(fin / "mutants.log"),
        }

    mcs = json.loads((fin / "mc-summary.json").read_text())
    for c in mcs["checks"]:
        bounded = "within the machine's declared bounds"
        runs[c["id"]] = {
            "kind": "mc", "result": "pass" if c["met"] else "fail",
            "command": f'cargo run --release -- --only {c["id"]}  (in experiment/playbook-uplift/model)',
            "observes": f'{c["machine"]} machine, {c["design"]} design: expected {c["expect"]}; '
                        + (f'found violation of \'{c["found"]}\'' if c["found"] else "no violation")
                        + f'; {c["states"]} states, {c["transitions"]} transitions, depth {c["depth"]}, '
                        + ("stopped at the state cap" if c["truncated"] else f"exhaustive {bounded}") + ".",
            "states": c["states"], "transitions": c["transitions"], "seconds": c["seconds"],
            "counterexample": c["trace"],
            "log": rel(fin / "mc.log"), "log_sha256": sha(fin / "mc.log"),
        }
    REG.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    print(f"registered {sum(1 for k in runs if k.startswith('native-'))} live scenarios, "
          f"{len(mcs['checks'])} model checks, upstream suite: {'yes' if up.exists() else 'no'}")
    bad = [k for k, v in runs.items() if v.get("result") != "pass"]
    if bad:
        print("not passing:", ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
