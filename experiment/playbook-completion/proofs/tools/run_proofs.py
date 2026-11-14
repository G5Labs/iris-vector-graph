#!/usr/bin/env python3
"""Proof gate of the CORE-PROOFS lane (experiment/playbook-completion/proofs, playbook §3.3 gate and §5 trust).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs/tools/run_proofs.py              # trust scan, baseline, every control
    python experiment/playbook-completion/proofs/tools/run_proofs.py --register   # ... and register the decisive runs

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom or uninterpreted
   function. The actors dependency (verified in the same build, but without --no-cheating, which is forwarded to this
   crate only) is scanned for the same items. vstd is Verus's standard trusted base and is listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors.
3. Safety controls: each Cargo feature replaces one coordination decision by the pin's behaviour. It must make
   verification fail, with every error located in its expected file.
   Its proved counterexample (src/cx_*.rs, compiled only with that feature: a run of the composed participant
   contracts, as the control changes them, from the initial state to a business violation) must verify.
4. Progress-only control: it must fail with every error in src/progress.rs while every function of every other
   module verifies (per-function results from Verus's JSON output).

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy timeout 3600 cargo verus verify ...`, after
`cargo clean -p ivg-core-proofs` (a cached build replays old diagnostics without verifying). A timeout or a missing
result is a failure, never a pass. Logs: $RUN_DIR/core-proofs/<tag>.log (diagnostics) and <tag>.json (Verus JSON).
Result: experiment/playbook-completion/proofs/RESULTS.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from verus_json import parse_verus_json  # noqa: E402  (cold builds print dependency summaries before the JSON)

PROOFS = Path(__file__).resolve().parent.parent
COMPLETION = PROOFS.parent
REPO = COMPLETION.parent.parent
LOCKS = COMPLETION / "tools" / "locks.sh"
REGISTER = COMPLETION / "tools" / "register_run.py"
CRATE = "ivg-core-proofs"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

SAFETY_CONTROLS = {
    "control_f1302_unlocked_start": {
        "finding": "F-1302", "expected": "src/protocol_rl.rs", "counterexample": "cx_f1302::counterexample_f1302",
        "what": "Start checks without the head lock and writes no marker; the first tombstone writes it "
                "(LedgerRedact.cls:202-211, 322-324), so a Scan may run with no marker",
    },
    "control_f1303_other_marker": {
        "finding": "F-1303", "expected": "src/protocol_rl.rs", "counterexample": "cx_f1303::counterexample_f1303",
        "what": "Final runs under whatever marker exists, not its own target's (LedgerRedact.cls:409-441)",
    },
    "control_f1201_erase_unlocked": {
        "finding": "F-1201", "expected": "src/protocol_sys.rs", "counterexample": "cx_f1201::counterexample_f1201",
        "what": "the eraser takes no ledger head lock (Eraser.cls:47-261): a commit can land between its row deletes "
                "and its statement cleanup",
    },
    "control_f1306_replay_reapplies": {
        "finding": "F-1306", "expected": "src/protocol_sys.rs", "counterexample": "cx_f1306::counterexample_f1306",
        "what": "a replayed retry re-applies its post-commit properties to the store (client.py:430-435)",
    },
}
PROGRESS_CONTROL = {
    "control_progress_rewind": {
        "expected": "src/progress.rs",
        "what": "a resume rewinds the run's cursor to the first record (the pin's Redact restarts its scan, "
                "LedgerRedact.cls:213)",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")


def run_dir() -> Path:
    # PROOFS_OUT_DIR (a verify run) keeps reruns from overwriting the registered decisive logs in core-proofs/
    d = Path(os.environ.get("PROOFS_OUT_DIR") or (Path(os.environ["RUN_DIR"]) / "core-proofs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def env() -> dict:
    return dict(os.environ, CARGO_TARGET_DIR=str(Path(os.environ["RUN_DIR"]) / "target" / "core-proofs"))


def sources() -> list[Path]:
    return sorted((PROOFS / "src").glob("*.rs")) + [PROOFS / "Cargo.toml", PROOFS / "Cargo.lock"]


def sources_sha256() -> str:
    h = hashlib.sha256()
    for p in sources():
        h.update(str(p.relative_to(PROOFS)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def scan(paths: list[Path], root: Path) -> list[str]:
    bad = []
    for p in paths:
        code = re.sub(r"//[^\n]*", "", p.read_text())
        for pat in FORBIDDEN:
            for m in re.finditer(pat, code):
                line = code[: m.start()].count("\n") + 1
                bad.append(f"{p.relative_to(root)}:{line}: {m.group(0)!r}")
    return bad


def actors_src() -> Path | None:
    base = Path.home() / ".cargo" / "git" / "checkouts"
    hits = sorted(base.glob(f"playbook-reference-actors-*/{ACTORS_REV[:7]}/crates/actors/src"))
    return hits[0] if hits else None


def trust_inventory() -> dict:
    own = scan(sorted((PROOFS / "src").glob("*.rs")), PROOFS)
    a = actors_src()
    actors = scan(sorted(a.glob("*.rs")), a) if a else ["actors checkout not found"]
    return {
        "own_sources": {"scanned": [str(p.relative_to(PROOFS)) for p in sorted((PROOFS / "src").glob("*.rs"))],
                        "patterns": FORBIDDEN, "violations": own},
        "actors": {"rev": ACTORS_REV, "path": str(a) if a else None, "violations": actors,
                   "note": "verified in the same build without --no-cheating (forwarded to roots only)"},
        "vstd": {"version": "0.0.0-2026-09-20-0158",
                 "note": "Verus standard library: the trusted base (its axioms and admits are Verus's own); not "
                         "scanned"},
        "trusted_items_in_this_crate": [],
        "premises": "named in PROOFS.md (P-C01..P-C03, PF-1..PF-4); none is an assumption inside a proof",
    }


def locations(text: str) -> list[str]:
    locs, pending = [], False
    for line in text.splitlines():
        if line.startswith("error"):
            pending = not line.startswith("error: could not compile")
            continue
        m = re.search(r"--> (src/[\w/]+\.rs):(\d+)", line)
        if m and pending:
            locs.append(f"{m.group(1)}:{m.group(2)}")
            pending = False
    return sorted(set(locs), key=lambda s: (s.split(":")[0], int(s.split(":")[1])))


def verify(tag: str, features: str = "") -> dict:
    log = run_dir() / f"{tag}.log"
    js = run_dir() / f"{tag}.json"
    subprocess.run(["cargo", "clean", "-p", CRATE, "--offline"], cwd=PROOFS, env=env(), capture_output=True)
    cargo = ["cargo", "verus", "verify", "--offline", "--fwd-verus-args-to", "roots"]
    if features:
        cargo += ["--features", features]
    cargo += ["--", "--no-cheating", "--triggers-mode", "silent", "--time-expanded", "--output-json"]
    cmd = ["bash", str(LOCKS), "heavy", "/usr/bin/time", "-f", "WALLSECONDS %e", "timeout", "3600"] + cargo
    with open(log, "w") as fe, open(js, "w") as fo:
        rc = subprocess.run(cmd, cwd=PROOFS, env=env(), stdout=fo, stderr=fe).returncode
    text = log.read_text(errors="replace")
    wall = re.findall(r"WALLSECONDS ([\d.]+)", text)
    out = {"tag": tag, "features": features, "rc": rc, "timed_out": rc == 124,
           "command": " ".join(["bash", "experiment/playbook-completion/tools/locks.sh", "heavy", "timeout", "3600"] + cargo),
           "log": "$RUN_DIR/" + str(log.relative_to(os.environ["RUN_DIR"])), "json": "$RUN_DIR/" + str(js.relative_to(os.environ["RUN_DIR"])),
           "wall_seconds": float(wall[-1]) if wall else None, "error_locations": locations(text)}
    try:
        d = parse_verus_json(js.read_text())
    except (json.JSONDecodeError, OSError):
        d = None
    if d:
        vr = d["verification-results"]
        out.update(verified=vr["verified"], errors=vr["errors"], success=vr["success"])
        t = d["times-ms"]
        smt = t["smt"]
        out["verus_total_ms"] = t["total"]
        out["smt_run_ms"] = smt["smt-run"]
        out["rlimit_total"] = smt["rlimit-run"]
        mods, funcs = {}, []
        for m in smt.get("smt-run-module-times", []):
            mods[m["module"]] = {"ms": m["time"], "rlimit": m["rlimit"]}
            for f in m.get("function-breakdown", []):
                funcs.append({"function": f["function"].replace("ivg_core_proofs::", ""), "ms": f["time"],
                              "rlimit": f["rlimit"], "success": f["success"]})
        out["modules"] = dict(sorted(mods.items(), key=lambda kv: -kv[1]["rlimit"]))
        out["top_functions"] = sorted(funcs, key=lambda f: -f["rlimit"])[:10]
        out["all_functions"] = sorted(funcs, key=lambda f: f["function"])
        out["failing_functions"] = sorted(f["function"] for f in funcs if not f["success"])
        out["functions_checked"] = len(funcs)
        out["max_function_rlimit"] = max((f["rlimit"] for f in funcs), default=0)
    else:
        found = RESULT_RE.findall(text)
        out.update(verified=int(found[-1][0]) if found else None, errors=int(found[-1][1]) if found else None,
                   success=False, failing_functions=[])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--register", action="store_true", help="register the decisive runs (tools/register_run.py)")
    a = ap.parse_args()

    trust = trust_inventory()
    for v in trust["own_sources"]["violations"] + trust["actors"]["violations"]:
        print("TRUST:", v)
    sha = sources_sha256()
    base = verify("baseline")
    base["pass"] = base["rc"] == 0 and base.get("errors") == 0 and bool(base.get("verified"))
    print(f"baseline: {base.get('verified')} verified, {base.get('errors')} errors, rc {base['rc']}, "
          f"verus {base.get('verus_total_ms')} ms, rlimit {base.get('rlimit_total')}")

    controls = {}
    if not a.baseline_only:
        for feat, meta in SAFETY_CONTROLS.items():
            r = verify(feat, feat)
            locs = r["error_locations"]
            r.update(meta)
            r["killed"] = (not r["timed_out"]) and bool(r.get("errors")) and bool(locs) \
                and all(x.startswith(meta["expected"] + ":") for x in locs)
            # The control's proved counterexample (a run of the composed participant contracts, as the control changes
            # them, from the initial state to a business violation) must verify in the same build.
            ok_fns = {f["function"] for f in r.get("all_functions", []) if f["success"]}
            r["counterexample_verified"] = meta["counterexample"] in ok_fns
            r.pop("all_functions", None)
            controls[feat] = r
            print(f"{feat}: {'REJECTED' if r['killed'] else 'SURVIVED'} ({r.get('errors')} errors at {locs}); "
                  f"counterexample {meta['counterexample']} {'verified' if r['counterexample_verified'] else 'NOT verified'}")
        for feat, meta in PROGRESS_CONTROL.items():
            r = verify(feat, feat)
            locs = r["error_locations"]
            r.update(meta)
            others = [f for f in r.get("failing_functions", []) if not f.startswith("progress::")]
            r["failing_outside_progress"] = others
            r["killed"] = (not r["timed_out"]) and bool(r.get("errors")) and bool(locs) \
                and all(x.startswith(meta["expected"] + ":") for x in locs) and not others \
                and bool(r.get("failing_functions"))
            r["safety_still_verifies"] = not others and r.get("verified") == (base.get("verified") or 0) - len(
                r.get("failing_functions", []))
            r.pop("all_functions", None)
            controls[feat] = r
            print(f"{feat}: {'FAILS ONLY PROGRESS' if r['killed'] else 'NOT PROGRESS-ONLY'} "
                  f"({r.get('errors')} errors at {locs}; failing {r.get('failing_functions')})")

    trust_ok = not trust["own_sources"]["violations"] and not trust["actors"]["violations"]
    gate_ok = trust_ok and base["pass"] and (a.baseline_only or (
        all(c["killed"] for c in controls.values())
        and all(c["counterexample_verified"] for f, c in controls.items() if f in SAFETY_CONTROLS)))
    verus_v = subprocess.run(["verus", "--version"], capture_output=True, text=True).stdout.split()
    result = {
        "crate": f"experiment/playbook-completion/proofs ({CRATE})",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "verus": next((v for v in verus_v if v[:1].isdigit()), None),
        "actors_rev": ACTORS_REV,
        "sources_sha256": sha,
        "baseline": base,
        "controls": controls,
        "trust_inventory": trust,
        "gate": "pass" if gate_ok else "fail",
    }
    results_path = Path(os.environ["PROOFS_OUT_DIR"]) / "RESULTS.json" if os.environ.get("PROOFS_OUT_DIR") else PROOFS / "RESULTS.json"
    results_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"core-proofs gate: {result['gate'].upper()}  (RESULTS.json, sources {sha[:12]})")

    if a.register:
        def reg(rid, kind, res, r, observes):
            subprocess.run([sys.executable, str(REGISTER), rid, kind, res, str(run_dir() / Path(r["log"]).name),
                            "--lane", "core-proofs", "--command", r["command"], "--observes", observes,
                            "--extra", f"verified={r.get('verified')}", f"errors={r.get('errors')}",
                            f"error_locations={','.join(r['error_locations'])}", f"sources_sha256={sha}",
                            f"json_log={r['json']}", f"verus_total_ms={r.get('verus_total_ms')}",
                            f"rlimit_total={r.get('rlimit_total')}"], cwd=REPO, check=True)
        reg("core-proofs-baseline", "proof", "pass" if base["pass"] and trust_ok else "fail", base,
            f"ivg-core-proofs baseline with --no-cheating: {base.get('verified')} verified, {base.get('errors')} errors; "
            f"trust inventory {'empty' if trust_ok else 'NOT empty'}")
        for feat, r in controls.items():
            short = feat.replace("control_", "").replace("_", "-")
            res = "expected-violation" if r["killed"] else "fail"
            where = r["expected"]
            reg(f"core-proofs-{short}", "control", res, r,
                f"{feat} ({r.get('finding', 'progress-only')}): {r.get('errors')} errors, all in {where}: "
                f"{r['error_locations']}; failing functions {r.get('failing_functions')}")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
