#!/usr/bin/env python3
"""Run the proof gate for experiment/playbook-uplift/proofs (playbook §3.3 gate, §5 trust inventory and controls).

    python experiment/playbook-uplift/tools/run_verus.py            # baseline + trust scan + every control
    python experiment/playbook-uplift/tools/run_verus.py --baseline-only

1. Trust inventory: the proof sources may contain no assume, admit or external_body, and exactly the uninterpreted
   spec functions listed in TRUSTED_UNINTERP (each a named premise in TRUST.md). Anything else fails.
2. Baseline: `cargo verus verify` (with --no-cheating) must report 0 errors for this crate. Its time is recorded.
3. Controls: each Cargo feature in CONTROLS breaks one guard of the L2 machine. Each must make verification fail with
   an error located in src/l2.rs. A control that verifies, or fails elsewhere, is a survivor and fails the gate.

Logs go to $RUN_DIR/verus/. The result is written to evidence/runs.json ("verus"), with the SHA-256 of the proof
sources, so the ontology index accepts `proved:<fn>` only while the sources are the ones that were verified.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from ontology_index import UPLIFT, proof_sources, uplift_hash  # noqa: E402

PROOFS = UPLIFT / "proofs"
REG = UPLIFT / "evidence" / "runs.json"
TRUSTED_UNINTERP: dict = {}
CONTROLS = {
    "control_unmarked_start": "the pin's Redact: liveness checked without the lock, marker set at the first tombstone (F-1302)",
    "control_other_target": "a batch tombstones its target while another target's marker is set (F-1303)",
    "control_meta_every": "metadata cleared only when every record of the revision is redacted (spec 256 FR-004 text)",
    "control_keep_retry_key": "the retry key of a redacted revision stays bound",
    "control_no_final_check": "the final step does not re-check liveness",
    "control_no_commit_block": "a commit into the marker's target is not refused",
}
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")


def run_dir() -> Path:
    d = Path(os.environ["RUN_DIR"]) / "verus"
    d.mkdir(parents=True, exist_ok=True)
    return d


def trust_scan() -> list:
    bad = []
    for p in proof_sources(UPLIFT):
        if p.suffix != ".rs":
            continue
        text = p.read_text()
        code = re.sub(r"//[^\n]*", "", text)
        for pat in (r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\[verifier::external"):
            for m in re.finditer(pat, code):
                bad.append(f"{p.relative_to(UPLIFT)}: forbidden {m.group(0)!r}")
        for m in re.finditer(r"uninterp\s+spec\s+fn\s+(\w+)", code):
            if m.group(1) not in TRUSTED_UNINTERP:
                bad.append(f"{p.relative_to(UPLIFT)}: uninterpreted {m.group(1)} is not in the trust inventory")
    return bad


def verify(tag: str, features: str = "") -> dict:
    log = run_dir() / f"proofs-{tag}.log"
    cmd = ["cargo", "verus", "verify"] + (["--features", features] if features else []) + ["--", "--no-cheating"]
    env = dict(os.environ, CARGO_TARGET_DIR=str(run_dir() / "target-proofs"))
    # Always verify afresh: a cached build would replay the previous run's diagnostics without verifying.
    subprocess.run(["cargo", "clean", "-p", "ivg-redaction-proofs"], cwd=PROOFS, env=env, capture_output=True)
    t0 = time.monotonic()
    with open(log, "w") as fh:
        try:
            rc = subprocess.run(cmd, cwd=PROOFS, env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=1800).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    secs = round(time.monotonic() - t0, 1)
    text = log.read_text(errors="replace")
    # The last results line is this crate's (dependencies verify first).
    found = RESULT_RE.findall(text)
    verified, errors = (int(found[-1][0]), int(found[-1][1])) if found else (None, None)
    # Locations of errors only: the first "--> src/..." after each "error:" line (notes about triggers are not errors).
    locs, pending = set(), False
    for line in text.splitlines():
        if line.startswith("error"):
            pending = not line.startswith("error: could not compile")
        m = re.search(r"--> (src/[\w/]+\.rs):(\d+)", line)
        if m and pending:
            locs.add((m.group(1), m.group(2)))
            pending = False
    locs = sorted(locs)
    fns = sorted(set(re.findall(r"(?:proof fn|fn) (\w+)\(", "\n".join(
        l for l in text.splitlines() if re.match(r"^\s*\d+ \|", l)))))
    return {"tag": tag, "features": features, "rc": rc, "seconds": secs, "verified": verified, "errors": errors,
            "error_locations": [f"{a}:{b}" for a, b in locs], "functions_in_errors": fns,
            "log": "$RUN_DIR/verus/" + log.name}


def proof_fns() -> list:
    names = []
    for p in proof_sources(UPLIFT):
        if p.suffix == ".rs":
            names += re.findall(r"\bproof\s+fn\s+(\w+)", p.read_text())
    return sorted(set(names))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-only", action="store_true")
    a = ap.parse_args()
    bad = trust_scan()
    for b in bad:
        print("TRUST:", b)
    base = verify("baseline")
    print(f"baseline: {base['verified']} verified, {base['errors']} errors, {base['seconds']} s")
    controls = {}
    if not a.baseline_only:
        for feat, what in CONTROLS.items():
            r = verify(feat, feat)
            located = any(x.startswith("src/l2.rs") for x in r["error_locations"])
            r["killed"] = bool(r["errors"]) and located
            r["what"] = what
            controls[feat] = r
            print(f"{feat}: {'KILLED' if r['killed'] else 'SURVIVED'} ({r['errors']} errors at {r['error_locations']})")
    ok = not bad and base["errors"] == 0 and all(c["killed"] for c in controls.values())
    reg = json.loads(REG.read_text()) if REG.exists() else {"runs": {}}
    prev = reg.get("verus", {})
    reg["verus"] = {
        "crate": "experiment/playbook-uplift/proofs (ivg-redaction-proofs)",
        "command": "cargo verus verify -- --no-cheating",
        "verus": subprocess.run(["verus", "--version"], capture_output=True, text=True).stdout.strip().splitlines()[0:1],
        "actors": "G5Labs/actors c03f9fa9be961610f2b274ffbb6a2c88d7d4d877 (git dependency)",
        "sources_sha256": uplift_hash(proof_sources(UPLIFT)),
        "errors": base["errors"],
        "verified": base["verified"],
        "seconds": base["seconds"],
        "log": base["log"],
        "trust_violations": bad,
        "trusted_uninterp": TRUSTED_UNINTERP,
        "proof_fns": proof_fns() if base["errors"] == 0 and not bad else [],
        "controls": controls or prev.get("controls", {}),
        "gate": "pass" if ok else "fail",
    }
    REG.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    print(f"proof gate: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
