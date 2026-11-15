#!/usr/bin/env python3
"""Mutation testing of the unverified layer (playbook §3.7): broken copies of the redaction code on live IRIS.

    python experiment/playbook-uplift/native/mutants.py [--out DIR]

Each mutant changes one guard of the ObjectScript at the pin, mirroring a proof control in proofs/Cargo.toml. For each:
load the mutated class into the dedicated namespace and compile it, run the live scenarios named for it, and require that
at least one of their checks fails (the mutant is "killed"); then load the pin's class text back and compile it. After
the last mutant the whole scenario set runs once more on the restored classes and must pass. The product files in the
checkout are never changed; the classes are put into IRIS from text (ivg_native.load_class).

Exit status 0 when every mutant was killed and the restored run passed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ivg_native import Conn, load_class, pin_class_text  # noqa: E402

MUTANTS = [
    {"id": "no-commit-block", "control": "control_no_commit_block", "cls": "Graph.KG.Ledger",
     "old": '        Set tErr = ##class(Graph.KG.LedgerRedact).BlocksCommit(.tRecords)\n        If tErr \'= "" Return tErr\n',
     "new": '        Set tErr = ""\n',
     "scenarios": ["paused_and_resumed"]},
    {"id": "no-final-check", "control": "control_no_final_check", "cls": "Graph.KG.LedgerRedact",
     "old": '    If tLive > 0 Return ##class(Graph.KG.Ledger).Err("target_live", ..TargetText(pName, pMatch) _ " became live again (" _ tWhat _ "); erase it and run the redaction again")\n',
     "new": "",
     "scenarios": ["commit_in_unmarked_window"]},
    {"id": "keep-retry-key", "control": "control_keep_retry_key", "cls": "Graph.KG.LedgerRedact",
     "old": '        Kill ^IVG.Ledger("idem", tKey)\n        Set ^IVG.Ledger("idemRedacted", ..Sha256Hex(tKey)) = pSeq\n',
     "new": "",
     "scenarios": ["retries", "mixed_tenant_flow"]},
]


def run_scenarios(names, out: Path) -> dict:
    cmd = [sys.executable, str(HERE / "scenarios.py"), "--out", str(out)] + (["--only", *names] if names else [])
    with open(out.with_suffix(".log"), "w") as fh:
        subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=3600)
    return json.loads((out / "summary.json").read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.environ["RUN_DIR"], "final", "mutants"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for m in MUTANTS:
        pin = pin_class_text(m["cls"])
        assert pin.count(m["old"]) == 1, f"{m['id']}: the mutated text is not unique at the pin"
        c = Conn()
        try:
            load_class(c, m["cls"], pin.replace(m["old"], m["new"]))
        finally:
            c.close()
        try:
            summary = run_scenarios(m["scenarios"], out / m["id"])
        finally:
            c = Conn()
            try:
                load_class(c, m["cls"], pin)
            finally:
                c.close()
        failed = {k: v["failed"] for k, v in summary.items() if not v["ok"]}
        killed = bool(failed)
        results.append({"mutant": m["id"], "control": m["control"], "class": m["cls"], "scenarios": m["scenarios"],
                        "killed": killed, "failed_checks": failed})
        print(f"{m['id']}: {'KILLED' if killed else 'SURVIVED'} {failed if killed else ''}")
    clean = run_scenarios([], out / "restored")
    clean_ok = all(v["ok"] for v in clean.values())
    print(f"restored classes, all scenarios: {'PASS' if clean_ok else 'FAIL'} ({len(clean)} scenarios)")
    (out / "mutants.json").write_text(json.dumps({"mutants": results, "restored_ok": clean_ok,
                                                  "restored": clean}, indent=1, sort_keys=True))
    return 0 if clean_ok and all(r["killed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
