#!/usr/bin/env python3
"""Proof gate of the PROOFS-D9B lane (experiment/playbook-completion/proofs-d9b, proof debts D-9 and D-12).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-d9b/tools/run_proofs.py                # trust scan, baseline, every control
    python experiment/playbook-completion/proofs-d9b/tools/run_proofs.py --register     # ... and register the decisive runs
    PROOFS_OUT_DIR=/some/dir python .../run_proofs.py                                   # a recheck: logs and RESULTS.json there

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom, uninterpreted
   function or assume_specification. The actors dependency (verified in the same build without --no-cheating, which is
   forwarded to this crate only) is scanned for the same items. vstd is Verus's trusted base, listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors.
3. Safety controls (the D-9 guards, the F-1201 regression, and the D-9b controls: F-CS01, the re-run F-1302, F-1303,
   F-1306 controls, the statement-history guard, F-1402 and HD-1401 (b1)): each Cargo feature removes one guard or
   puts back one as-built behaviour. It must make verification fail with every error in its expected file, every
   function outside that file (and outside its counterexample module) must verify and be exactly the baseline's, and
   its proved counterexample (src/cx_*.rs, compiled only with that feature: a run of the composed participant
   contracts, as the control changes them, from the initial state to a business violation) must verify in the same
   build.
4. Progress-only controls (the cursor rewind, D-1; the bound that follows the tail, D-12): each must fail with every
   error in src/progress.rs while every function of every other module verifies (per-function results from Verus's
   JSON output), and the set of those functions equals the baseline's.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy timeout 3600 cargo verus verify ...`, after
`cargo clean -p ivg-proofs-d9b` (a cached build replays old diagnostics without verifying). A timeout, a resource limit
or a missing result is a failure, never a pass. Each invocation writes its logs into a NEW directory
<out>/run-<UTC stamp>/ (out = $PROOFS_OUT_DIR or $RUN_DIR/proofs-d9b), so no registered log is ever overwritten; with
--register, an id that already has a record in evidence/runs/ is refused (use --id-suffix for a rerun; --id-prefix
names a recheck's ids, e.g. proofs-d9b-recheck).
RESULTS.json: $PROOFS_OUT_DIR/RESULTS.json when set, else experiment/playbook-completion/proofs-d9b/RESULTS.json.
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
RUNS = COMPLETION / "evidence" / "runs"
CRATE = "ivg-proofs-d9b"
MOD = "ivg_proofs_d9b::"
LANE = "proofs-d9b"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

SAFETY_CONTROLS = {
    "control_bypass_start": {
        "guard": "G-B bypass writers serialized with redaction start", "finding": "F-C1301",
        "expected": "src/protocol_top.rs", "counterexample": "cx_bypass_start::counterexample_bypass_start",
        "what": "Start does not wait for open ledger-bypassing transactions (no writer takes a lock the redaction "
                "takes, as at the pin)",
    },
    "control_bypass_erase": {
        "guard": "G-BE the eraser waits for open bypass transactions on its target", "finding": "new (model)",
        "expected": "src/protocol_top.rs", "counterexample": "cx_bypass_erase::counterexample_bypass_erase",
        "what": "EraseRows does not wait for open bypass transactions on its target's rows",
    },
    "control_liveness_dirty": {
        "guard": "G-L liveness on committed state or under the eraser's lock", "finding": "F-C1201",
        "expected": "src/protocol_sys.rs", "counterexample": "cx_liveness_dirty::counterexample_liveness_dirty",
        "what": "the liveness check runs at the call, without the head lock, on uncommitted rows "
                "(LedgerRedact.cls:206-210); the locked Start does not check again",
    },
    "control_unaligned_rm": {
        "guard": "G-P side condition, part rm ⊆ lv", "finding": "F-1304 (shape of F-C1308)",
        "expected": "src/protocol_sys.rs", "counterexample": "cx_unaligned_rm::counterexample_unaligned_rm",
        "what": "Start accepts a target whose record match selects rows its liveness check does not look at",
    },
    "control_unaligned_sc": {
        "guard": "G-P side condition, part sc ⊆ rm (edges)", "finding": "core m1-control-dropstatements-all-graphs",
        "expected": "src/protocol_sys.rs", "counterexample": "cx_unaligned_sc::counterexample_unaligned_sc",
        "what": "Start accepts a target whose statement cleanup selects statements outside its record match",
    },
    "control_f1201_erase_unlocked": {
        "guard": "original HD-1201 eraser head lock (regression)", "finding": "F-1201",
        "expected": "src/protocol_sys.rs", "counterexample": "cx_f1201::counterexample_f1201",
        "what": "the eraser takes no ledger head lock (Eraser.cls:47-261)",
    },
    "control_fcs01_noop_unrecorded": {
        "guard": "R-1 every operation leaves a record (no-op record)", "finding": "F-CS01",
        "expected": "src/protocol_rl.rs", "counterexample": "cx_fcs01::counterexample_fcs01",
        "what": "as built: a no-op operation writes no record and the commit writes the revision row and key binding "
                "regardless (Ledger.cls:489-492, 520-525; LedgerApply.cls:229-233, 252-263); a zero-record revision "
                "keeps its metadata and its bound key through a complete redaction",
    },
    "control_f1302_unlocked_start": {
        "guard": "HD-1301 locked Start writes its marker (re-run)", "finding": "F-1302",
        "expected": "src/protocol_rl.rs", "counterexample": "cx_f1302::counterexample_f1302",
        "what": "Start checks without the head lock and writes no marker; the first tombstone writes it "
                "(LedgerRedact.cls:202-211, 322-324)",
    },
    "control_f1303_other_marker": {
        "guard": "HD-1301 Final under its own marker (re-run)", "finding": "F-1303",
        "expected": "src/protocol_rl.rs", "counterexample": "cx_f1303::counterexample_f1303",
        "what": "Final runs under whatever marker exists (FinalInLock, LedgerRedact.cls:409-441)",
    },
    "control_f1306_replay_reapplies": {
        "guard": "HD-1305 a replayed retry applies nothing (re-run)", "finding": "F-1306",
        "expected": "src/protocol_sys.rs", "counterexample": "cx_f1306::counterexample_f1306",
        "what": "a replayed retry re-applies its post-commit properties (client.py:430-435 after Ledger.cls:457-462)",
    },
    "control_sc_narrow": {
        "guard": "G-P side condition, part rm ⊆ sc on edges (statement history)", "finding": "none (design control)",
        "expected": "src/protocol_sys.rs", "counterexample": "cx_sc_narrow::counterexample_sc_narrow",
        "what": "Start accepts a target whose statement cleanup misses edges its record match owns; a closed "
                "statement entry survives a complete redaction",
    },
    "control_f1402_reader_no_recheck": {
        "guard": "reader re-checks marker and epoch after reading (HD-1401 b2)", "finding": "F-1402",
        "expected": "src/protocol_rd.rs", "counterexample": "cx_reader::counterexample_reader_half_redacted",
        "what": "as built: a reader checks the marker once before reading and returns its view unchecked "
                "(client.py:720-728, replay.py:231-269)",
    },
    "control_reader_marker_recheck_only": {
        "guard": "reader compares the redaction epoch (HD-1401 b2 vs b1)", "finding": "F-1402 (HD-1401 b1)",
        "expected": "src/protocol_rd.rs", "counterexample": "cx_reader::counterexample_reader_half_redacted",
        "what": "a reader re-checks the marker after reading but compares no epoch; a whole redaction inside one "
                "read passes it",
    },
}
PROGRESS_CONTROL = {
    "control_progress_rewind": {
        "expected": "src/progress.rs", "element": "D-1 (cursor survives a stop)",
        "what": "a resume rewinds the run's cursor to the first record (the pin's Redact restarts its scan, "
                "LedgerRedact.cls:213)",
    },
    "control_bound_follows_tail": {
        "expected": "src/progress.rs", "element": "D-2 (scan bound fixed at marking); proof debt D-12",
        "what": "the run's scan bound follows the tail: every commit while a marker exists moves it to the new head, "
                "as the pin's scan runs to the current end (LedgerRedact.cls:216-226, 308-313)",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def out_base() -> Path:
    return Path(os.environ.get("PROOFS_OUT_DIR") or (Path(os.environ["RUN_DIR"]) / LANE))


def run_dir() -> Path:
    d = out_base() / f"run-{STAMP}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def rel(p: Path) -> str:
    try:
        return "$RUN_DIR/" + str(p.resolve().relative_to(Path(os.environ["RUN_DIR"]).resolve()))
    except ValueError:
        return str(p)


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
                 "note": "Verus standard library: the trusted base (its axioms and admits are Verus's own); not scanned"},
        "trusted_items_in_this_crate": [],
        "premises": "named in PROOFS.md (P-D9-1..P-D9-5, P-D9b-1..P-D9b-4, PF-1..PF-6); none is an assumption inside a proof",
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
    d = run_dir()
    log = d / f"{tag}.log"
    js = d / f"{tag}.json"
    if log.exists() or js.exists():
        raise SystemExit(f"refusing to overwrite {log}")
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
           "log": rel(log), "json": rel(js),
           "wall_seconds": float(wall[-1]) if wall else None, "error_locations": locations(text),
           "resource_limit_hit": bool(re.search(r"rlimit|resource limit|timed out", text, re.I))}
    try:
        raw = js.read_text()
        # a fresh target directory first verifies vstd/actors, which print their result lines before the JSON
        dj = json.loads(raw[raw.index("{"):])
    except (json.JSONDecodeError, OSError, ValueError):
        dj = None
    if dj:
        vr = dj["verification-results"]
        out.update(verified=vr["verified"], errors=vr["errors"], success=vr["success"])
        t = dj["times-ms"]
        smt = t["smt"]
        out["verus_total_ms"] = t["total"]
        out["smt_run_ms"] = smt["smt-run"]
        out["rlimit_total"] = smt["rlimit-run"]
        mods, funcs = {}, []
        for m in smt.get("smt-run-module-times", []):
            mods[m["module"]] = {"ms": m["time"], "rlimit": m["rlimit"]}
            for f in m.get("function-breakdown", []):
                funcs.append({"function": f["function"].replace(MOD, ""), "ms": f["time"],
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
    ap.add_argument("--id-suffix", default="", help="suffix for registry ids of a rerun (e.g. -r2)")
    ap.add_argument("--id-prefix", default=LANE, help="prefix for registry ids (a recheck: proofs-d9b-recheck)")
    ap.add_argument("--lane", default=LANE, help="lane recorded in the registry")
    a = ap.parse_args()

    def rid_of(feat: str) -> str:
        return f"{a.id_prefix}-{feat.replace('control_', '').replace('_', '-')}{a.id_suffix}"

    ids = [f"{a.id_prefix}-baseline{a.id_suffix}"] + [rid_of(f) for f in {**SAFETY_CONTROLS, **PROGRESS_CONTROL}]
    if a.register:
        taken = [i for i in ids if (RUNS / f"{i}.json").exists()]
        if taken:
            raise SystemExit(f"registry ids already recorded (a rerun needs --id-suffix): {taken}")

    trust = trust_inventory()
    for v in trust["own_sources"]["violations"] + trust["actors"]["violations"]:
        print("TRUST:", v)
    sha = sources_sha256()
    base = verify("baseline")
    base["pass"] = base["rc"] == 0 and base.get("errors") == 0 and bool(base.get("verified")) and not base["timed_out"]
    base_fns = {f["function"] for f in base.get("all_functions", [])}
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
            ok_fns = {f["function"] for f in r.get("all_functions", []) if f["success"]}
            r["counterexample_verified"] = meta["counterexample"] in ok_fns
            stem = Path(meta["expected"]).stem + "::"
            cxmod = meta["counterexample"].split("::")[0] + "::"
            r["failing_outside_expected_file"] = [f for f in r.get("failing_functions", []) if not f.startswith(stem)]
            outside = {f["function"] for f in r.get("all_functions", [])
                       if not f["function"].startswith(stem) and not f["function"].startswith(cxmod)}
            outside_ok = {f["function"] for f in r.get("all_functions", [])
                          if not f["function"].startswith(stem) and not f["function"].startswith(cxmod) and f["success"]}
            r["others_verify_as_baseline"] = outside == outside_ok and outside == {f for f in base_fns if not f.startswith(stem)}
            r["killed"] = r["killed"] and not r["failing_outside_expected_file"] and r["others_verify_as_baseline"]
            r.pop("all_functions", None)
            controls[feat] = r
            print(f"{feat}: {'REJECTED' if r['killed'] else 'SURVIVED'} ({r.get('errors')} errors at {locs}; failing "
                  f"{r.get('failing_functions')}); counterexample {meta['counterexample']} "
                  f"{'verified' if r['counterexample_verified'] else 'NOT verified'}")
        for feat, meta in PROGRESS_CONTROL.items():
            r = verify(feat, feat)
            locs = r["error_locations"]
            r.update(meta)
            others = [f for f in r.get("failing_functions", []) if not f.startswith("progress::")]
            non_progress = {f["function"] for f in r.get("all_functions", []) if not f["function"].startswith("progress::")}
            non_progress_ok = {f["function"] for f in r.get("all_functions", [])
                               if not f["function"].startswith("progress::") and f["success"]}
            r["failing_outside_progress"] = others
            r["killed"] = (not r["timed_out"]) and bool(r.get("errors")) and bool(locs) \
                and all(x.startswith(meta["expected"] + ":") for x in locs) and not others \
                and bool(r.get("failing_functions"))
            r["safety_still_verifies"] = not others and non_progress == non_progress_ok \
                and non_progress == {f for f in base_fns if not f.startswith("progress::")}
            r["non_progress_functions_verified"] = len(non_progress_ok)
            r.pop("all_functions", None)
            controls[feat] = r
            print(f"{feat}: {'FAILS ONLY PROGRESS' if r['killed'] else 'NOT PROGRESS-ONLY'} "
                  f"({r.get('errors')} errors at {locs}; failing {r.get('failing_functions')}; "
                  f"safety still verifies: {r['safety_still_verifies']})")

    trust_ok = not trust["own_sources"]["violations"] and not trust["actors"]["violations"]
    gate_ok = trust_ok and base["pass"] and (a.baseline_only or (
        all(c["killed"] for c in controls.values())
        and all(c["counterexample_verified"] for f, c in controls.items() if f in SAFETY_CONTROLS)
        and all(c["safety_still_verifies"] for f, c in controls.items() if f in PROGRESS_CONTROL)))
    verus_v = subprocess.run(["verus", "--version"], capture_output=True, text=True).stdout.split()
    result = {
        "crate": f"experiment/playbook-completion/proofs-d9b ({CRATE})",
        "debt": "D-9 and D-12 (experiment/playbook-completion/PROOF-DEBT.md)",
        "scope": "statements about models only; no proof connects the product at pin 3eaa79cf to these contracts",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "run_dir": rel(run_dir()),
        "verus": next((v for v in verus_v if v[:1].isdigit()), None),
        "actors_rev": ACTORS_REV,
        "sources_sha256": sha,
        "baseline": base,
        "controls": controls,
        "trust_inventory": trust,
        "gate": "pass" if gate_ok else "fail",
    }
    results_path = Path(os.environ["PROOFS_OUT_DIR"]) / "RESULTS.json" if os.environ.get("PROOFS_OUT_DIR") else PROOFS / "RESULTS.json"
    results_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"proofs-d9b gate: {result['gate'].upper()}  ({results_path}, sources {sha[:12]})")

    if a.register:
        def reg(rid, kind, res, r, observes):
            subprocess.run([sys.executable, str(REGISTER), rid, kind, res, str(run_dir() / Path(r["log"]).name),
                            "--lane", a.lane, "--command", r["command"], "--observes", observes,
                            "--extra", f"verified={r.get('verified')}", f"errors={r.get('errors')}",
                            f"error_locations={','.join(r['error_locations'])}", f"sources_sha256={sha}",
                            f"json_log={r['json']}", f"verus_total_ms={r.get('verus_total_ms')}",
                            f"rlimit_total={r.get('rlimit_total')}"], cwd=REPO, check=True)
        reg(ids[0], "proof", "pass" if base["pass"] and trust_ok else "fail", base,
            f"ivg-proofs-d9b baseline with --no-cheating: {base.get('verified')} verified, {base.get('errors')} errors; "
            f"trust inventory {'empty' if trust_ok else 'NOT empty'} (models only)")
        for feat, r in controls.items():
            rid = rid_of(feat)
            ok = r["killed"] and r.get("counterexample_verified", r.get("safety_still_verifies"))
            reg(rid, "control", "expected-violation" if ok else "fail", r,
                f"{feat} ({r.get('guard', 'progress-only')}; {r.get('finding', '')}): {r.get('errors')} errors, all in "
                f"{r['expected']}: {r['error_locations']}; failing functions {r.get('failing_functions')}"
                + (f"; counterexample {r['counterexample']} verified={r['counterexample_verified']}" if 'counterexample' in r
                   else f"; safety still verifies={r.get('safety_still_verifies')}"))
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
