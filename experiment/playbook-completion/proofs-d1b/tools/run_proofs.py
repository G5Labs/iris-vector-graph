#!/usr/bin/env python3
"""Proof gate of the PROOFS-D1B lane (experiment/playbook-completion/proofs-d1b; proof debt D-1, playbook §3.3).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-d1b/tools/run_proofs.py              # trust scan, baseline, controls
    python experiment/playbook-completion/proofs-d1b/tools/run_proofs.py --register   # ... and register the runs
    PROOFS_OUT_DIR=<dir> python .../run_proofs.py                                     # a re-check: logs and RESULTS.json
                                                                                       # go to <dir>, nothing overwritten

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom or uninterpreted
   function. The actors dependency (verified in the same build, without --no-cheating, which is forwarded to this
   crate only) is scanned for the same items. vstd is Verus's trusted base and is listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors (module 18 and module 06 L1/L2, refinement,
   invariants, theorems, non-vacuity witnesses).
3. Controls: each Cargo feature puts back one as-built decision of the pin. It must make verification fail with every
   error located in its expected file and every failing function in that file's module, and its proved
   counterexample (src/cx_*.rs, compiled only with that feature: a run of the L2 step relation, as the control
   changes it, from the initial state to a step that is not an L1 step) must verify in the same build.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy /usr/bin/time timeout 3600 cargo verus
verify ...` after `cargo clean -p ivg-d1b-proofs` (a cached build replays old diagnostics without verifying). A
timeout, a resource limit or a missing result is a failure, never a pass. Logs: $RUN_DIR/proofs-d1b/<tag>.log
(diagnostics, plus one line the runner appends with the counts read from the JSON) and <tag>.json (Verus JSON), or
under $PROOFS_OUT_DIR when set. Result: proofs-d1b/RESULTS.json (or $PROOFS_OUT_DIR/RESULTS.json).
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

PROOFS = Path(__file__).resolve().parent.parent
COMPLETION = PROOFS.parent
REPO = COMPLETION.parent.parent
LOCKS = COMPLETION / "tools" / "locks.sh"
REGISTER = COMPLETION / "tools" / "register_run.py"
CRATE = "ivg-d1b-proofs"
LANE = "proofs-d1b"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

CONTROLS = {
    # module 18 (snapshot)
    "control_f1801_no_prefix_check": {
        "module": "18", "finding": "F-1801 (history half) / HD-1801", "expected": "src/snap_l2.rs",
        "counterexample": "cx_f1801_history::counterexample_f1801_history",
        "what": "a replacing restore checks layout, strict mode and a caller transaction only, then sets the "
                "archive's ledger nodes over the live ones (snapshot.py:1095-1152, 1554-1588, 1654-1692)",
    },
    "control_f1801_restore_unredacts": {
        "module": "18", "finding": "F-1801 (redaction half) / F-C1304 (restore)", "expected": "src/snap_l2.rs",
        "counterexample": "cx_f1801_unredact::counterexample_f1801_unredact",
        "what": "the restore writes the archive's rows and ledger records with no live redaction re-applied "
                "(snapshot.py:1141-1588; no reference to redaction)",
    },
    "control_fc1304_receipt_omits_archives": {
        "module": "18", "finding": "F-C1304 (receipt)", "expected": "src/snap_l2.rs",
        "counterexample": "cx_fc1304::counterexample_fc1304",
        "what": "the redaction receipt's out_of_reach names exports, journals and backups only, never IVG's own "
                "archives (LedgerRedact.cls:504-509)",
    },
    "control_fc1801_dirty_export": {
        "module": "18", "finding": "F-C1801 / HD-1802", "expected": "src/snap_l2.rs",
        "counterexample": "cx_fc1801::counterexample_fc1801",
        "what": "save_snapshot takes no lock and writers respect no export gate; reads are uncommitted "
                "(snapshot.py:864-1034)",
    },
    "control_fc1802_swallowed_line": {
        "module": "18", "finding": "F-C1802", "expected": "src/snap_l2.rs",
        "counterexample": "cx_fc1802::counterexample_fc1802",
        "what": "a global line IRIS refuses is logged at debug and not counted (snapshot.py:1665-1684)",
    },
    "control_fc1804_edge_routes_omitted": {
        "module": "18", "finding": "F-C1804", "expected": "src/snap_l2.rs",
        "counterexample": "cx_fc1804::counterexample_fc1804",
        "what": "the routed export plan keeps node routes (kg_emb_) only, so kg_eemb_ edge-vector routes are not "
                "archived (snapshot.py:299-344; security.py:58-68)",
    },
    # module 06 (vectors)
    "control_f0606_erase_keeps_ivf": {
        "module": "06", "finding": "F-0606 / HD-0601", "expected": "src/vidx_l2.rs",
        "counterexample": "cx_f0606::counterexample_f0606",
        "what": "Eraser.EraseGraph names no ^IVF generation (Eraser.cls; GraphStores.cls:28-131)",
    },
    "control_hd0602_inplace_build": {
        "module": "06", "finding": "HD-0602 (intent-a-hd0602-ivf-partial)", "expected": "src/vidx_l2.rs",
        "counterexample": "cx_hd0602::counterexample_hd0602",
        "what": "ivf_build kills ^IVF(name) and refills it in place, batch by batch, with no lock or transaction "
                "(IVFIndex.cls:8, 237-276; vector.py:2000-2022)",
    },
    "control_hd0604_two_consumers": {
        "module": "06", "finding": "HD-0604 (intent-a-hd0604-queue-claim)", "expected": "src/vq_l2.rs",
        "counterexample": "cx_hd0604::counterexample_hd0604",
        "what": "ClaimPendingBatch is a plain scan with no claim state and nothing excludes a second worker "
                "(EmbedQueue.cls:22-25, 112-134, 258-268)",
    },
    "control_f0604_done_without_vector": {
        "module": "06", "finding": "F-0604", "expected": "src/vq_l2.rs",
        "counterexample": "cx_f0604::counterexample_f0604",
        "what": "ProcessBatch sets DONE when EMBEDDING() made no vector (EmbedQueue.cls:307-327)",
    },
    "control_fc0601_no_version_check": {
        "module": "06", "finding": "F-C0601", "expected": "src/vq_l2.rs",
        "counterexample": "cx_fc0601::counterexample_fc0601",
        "what": "the status mark is unconditional, so a re-enqueue while a worker holds the old text is "
                "overwritten by DONE with the old vector (EmbedQueue.cls:44-58, 326-327)",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
GROUPS = {
    "module 18 (snapshot)": ("snap_l1", "snap_l2", "snap_runs", "witness_snap"),
    "module 06 (IVF index lifecycle)": ("vidx_l1", "vidx_l2", "witness_vidx"),
    "module 06 (embed queue)": ("vq_l1", "vq_l2", "vq_runs", "witness_vq"),
}


def run_dir() -> Path:
    d = Path(os.environ.get("PROOFS_OUT_DIR") or (Path(os.environ["RUN_DIR"]) / LANE))
    d.mkdir(parents=True, exist_ok=True)
    return d


def env() -> dict:
    return dict(os.environ, CARGO_TARGET_DIR=str(Path(os.environ["RUN_DIR"]) / "target" / LANE))


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
                bad.append(f"{p.relative_to(root)}:{code[: m.start()].count(chr(10)) + 1}: {m.group(0)!r}")
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
                 "note": "Verus standard library: the trusted base (its axioms, e.g. Map::new and Set extensionality, "
                         "are Verus's own); not scanned"},
        "trusted_items_in_this_crate": [],
        "premises": "named in PROOFS.md (P-S1..P-S7, P-V1..P-V5, P-Q1..P-Q2); none is an assumption inside a proof",
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
    cmd = ["bash", str(LOCKS), "heavy", "/usr/bin/time", "-f", "WALLSECONDS %e MAXRSSKB %M", "timeout", "3600"] + cargo
    with open(log, "w") as fe, open(js, "w") as fo:
        rc = subprocess.run(cmd, cwd=PROOFS, env=env(), stdout=fo, stderr=fe).returncode
    text = log.read_text(errors="replace")
    wall = re.findall(r"WALLSECONDS ([\d.]+) MAXRSSKB (\d+)", text)
    rd = Path(os.environ["RUN_DIR"])
    out = {"tag": tag, "features": features, "rc": rc, "timed_out": rc == 124,
           "command": " ".join(["bash", "experiment/playbook-completion/tools/locks.sh", "heavy", "timeout", "3600"] + cargo),
           "log": "$RUN_DIR/" + str(log.relative_to(rd)) if log.is_relative_to(rd) else str(log),
           "json": "$RUN_DIR/" + str(js.relative_to(rd)) if js.is_relative_to(rd) else str(js),
           "wall_seconds": float(wall[-1][0]) if wall else None, "max_rss_kb": int(wall[-1][1]) if wall else None,
           "error_locations": locations(text),
           "resource_limit": bool(re.search(r"rlimit|resource limit|Resource limit", text))}
    try:
        d = json.loads(js.read_text())
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
                funcs.append({"function": f["function"].replace("ivg_d1b_proofs::", ""), "ms": f["time"],
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
    out["json_sha256"] = hashlib.sha256(js.read_bytes()).hexdigest() if js.exists() else None
    # the decisive log carries its own counts (review-2: a log whose counts live only in the JSON is PARTIAL)
    with open(log, "a") as fe:
        fe.write(f"RUNNER SUMMARY ({js.name}, sha256 {out['json_sha256']}): verification results:: "
                 f"{out.get('verified')} verified, {out.get('errors')} errors; rc {rc}; "
                 f"failing functions {out.get('failing_functions')}; error locations {out['error_locations']}\n")
    return out


def per_group_cost(base: dict) -> dict:
    """Cost of each module's proof (its L1, L2, runs, witness), from the baseline's per-module SMT times."""
    out = {}
    mods = base.get("modules", {})
    for name, ms in GROUPS.items():
        sel = {m: v for m, v in mods.items() if m.split("::")[-1] in ms}
        fns = [f for f in base.get("all_functions", []) if f["function"].split("::")[0] in ms]
        out[name] = {"modules": sel, "ms": sum(v["ms"] for v in sel.values()),
                     "rlimit": sum(v["rlimit"] for v in sel.values()), "functions": len(fns),
                     "largest_function": max(fns, key=lambda f: f["rlimit"]) if fns else None}
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
    base["pass"] = base["rc"] == 0 and base.get("errors") == 0 and bool(base.get("verified")) and not base["timed_out"]
    base["cost_per_module_proof"] = per_group_cost(base)
    print(f"baseline: {base.get('verified')} verified, {base.get('errors')} errors, rc {base['rc']}, "
          f"verus {base.get('verus_total_ms')} ms, rlimit {base.get('rlimit_total')}")

    controls = {}
    if not a.baseline_only:
        for feat, meta in CONTROLS.items():
            r = verify(feat, feat)
            locs = r["error_locations"]
            r.update(meta)
            exp_mod = Path(meta["expected"]).stem
            ok_fns = {f["function"] for f in r.get("all_functions", []) if f["success"]}
            r["failing_outside_expected_module"] = [f for f in r.get("failing_functions", [])
                                                    if f.split("::")[0] != exp_mod]
            r["killed"] = (not r["timed_out"]) and bool(r.get("errors")) and bool(locs) \
                and all(x.startswith(meta["expected"] + ":") for x in locs) \
                and bool(r.get("failing_functions")) and not r["failing_outside_expected_module"]
            r["counterexample_verified"] = meta["counterexample"] in ok_fns
            r.pop("all_functions", None)
            controls[feat] = r
            print(f"{feat}: {'REJECTED' if r['killed'] else 'SURVIVED'} ({r.get('errors')} errors at {locs}; "
                  f"failing {r.get('failing_functions')}); counterexample {meta['counterexample']} "
                  f"{'verified' if r['counterexample_verified'] else 'NOT verified'}")

    trust_ok = not trust["own_sources"]["violations"] and not trust["actors"]["violations"]
    gate_ok = trust_ok and base["pass"] and (a.baseline_only or (
        all(c["killed"] for c in controls.values()) and all(c["counterexample_verified"] for c in controls.values())))
    verus_v = subprocess.run(["verus", "--version"], capture_output=True, text=True).stdout.split()
    result = {
        "crate": f"experiment/playbook-completion/proofs-d1b ({CRATE})",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "verus": next((v for v in verus_v if v[:1].isdigit()), None),
        "actors_rev": ACTORS_REV,
        "sources_sha256": sha,
        "statement": "Every result is about the models (L1 contracts and the reviewed L2 machines); none is a "
                     "property of the product at pin 3eaa79cf.",
        "baseline": base,
        "controls": controls,
        "trust_inventory": trust,
        "gate": "pass" if gate_ok else "fail",
    }
    out_dir = os.environ.get("PROOFS_OUT_DIR")
    results_path = Path(out_dir) / "RESULTS.json" if out_dir else PROOFS / "RESULTS.json"
    results_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{LANE} gate: {result['gate'].upper()}  ({results_path}, sources {sha[:12]})")

    if a.register:
        def reg(rid, kind, res, r, observes):
            subprocess.run([sys.executable, str(REGISTER), rid, kind, res, str(run_dir() / Path(r["log"]).name),
                            "--lane", LANE, "--command", r["command"], "--observes", observes,
                            "--extra", f"verified={r.get('verified')}", f"errors={r.get('errors')}",
                            f"error_locations={','.join(r['error_locations'])}", f"sources_sha256={sha}",
                            f"json_log={r['json']}", f"json_sha256={r.get('json_sha256')}",
                            f"verus_total_ms={r.get('verus_total_ms')}",
                            f"rlimit_total={r.get('rlimit_total')}"], cwd=REPO, check=True)
        reg(f"{LANE}-baseline", "proof", "pass" if base["pass"] and trust_ok else "fail", base,
            f"{CRATE} baseline with --no-cheating (module 18 snapshot and module 06 IVF index and embed queue: L1, "
            f"L2, refinement, invariants, witnesses): {base.get('verified')} verified, {base.get('errors')} errors; "
            f"trust inventory {'empty' if trust_ok else 'NOT empty'}; model-level only")
        for feat, r in controls.items():
            short = feat.replace("control_", "").replace("_", "-")
            reg(f"{LANE}-{short}", "control", "expected-violation" if r["killed"] and r["counterexample_verified"]
                else "fail", r,
                f"{feat} ({r['finding']}, module {r['module']}): {r.get('errors')} errors, all in {r['expected']}: "
                f"{r['error_locations']}; failing functions {r.get('failing_functions')}; counterexample "
                f"{r['counterexample']} {'verified' if r['counterexample_verified'] else 'NOT verified'}")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
