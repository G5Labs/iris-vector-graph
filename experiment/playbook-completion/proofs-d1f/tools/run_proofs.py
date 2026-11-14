#!/usr/bin/env python3
"""Proof gate of the PROOFS-D1F lane (experiment/playbook-completion/proofs-d1f; proof debt D-1, playbook §3.3).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-d1f/tools/run_proofs.py              # trust scan, baseline, controls
    python experiment/playbook-completion/proofs-d1f/tools/run_proofs.py --register   # ... and register the runs
    PROOFS_OUT_DIR=<dir> python .../run_proofs.py                                     # a re-check: logs and RESULTS.json
                                                                                       # go to <dir>, nothing overwritten

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom or uninterpreted
   function. The actors dependency (verified in the same build, without --no-cheating, which is forwarded to this
   crate only) is scanned for the same items. vstd is Verus's trusted base and is listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors (modules 15, 16 and 17: L1/L2, refinement,
   invariants, theorems, progress, non-vacuity witnesses).
3. Controls: each Cargo feature puts back one as-built decision of the pin. It must make verification fail with every
   error located in its expected file and every failing function in that file's module, and its proved
   counterexample (src/cx_*.rs, compiled only with that feature: a run of the L2 step relation, as the control
   changes it, from the initial state to a step that is not an L1 step; for the progress-only control a fair
   infinite execution whose rank never reaches 0) must verify in the same build. The progress-only control must fail
   `nonincreasing` only: every safety function verifies.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy /usr/bin/time timeout 3600 cargo verus
verify ...` after `cargo clean -p ivg-d1f-proofs` (a cached build replays old diagnostics without verifying). A
timeout, a resource limit or a missing result is a failure, never a pass. Logs: $RUN_DIR/proofs-d1f/<tag>.log
(diagnostics, plus one line the runner appends with the counts read from the JSON) and <tag>.json (Verus JSON), or
under $PROOFS_OUT_DIR when set. Result: proofs-d1f/RESULTS.json (or $PROOFS_OUT_DIR/RESULTS.json).
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
CRATE = "ivg-d1f-proofs"
LANE = "proofs-d1f"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

CONTROLS = {
    # module 15: a FHIR graph's sync, erase, sync task and registration
    "control_hd1503_erase_ignores_sync_lock": {
        "module": "15", "finding": "HD-1503 / HD-1502 (explorer cmc-fhir-erase-as-built, cmc-fhir-durable-as-built)",
        "expected": "src/fhir_l2.rs", "counterexample": "cx_hd1503::counterexample_hd1503",
        "what": "EraseGraph takes no lock, so an erase or a durable removal commits while a SyncOnce runs; the sync's next "
                "batch writes its absolute watermark from its in-memory position (Eraser.cls:47-258; FHIRGraph.cls:543-626, "
                "1967-1969)",
    },
    "control_fc1501_schedule_untransacted": {
        "module": "15", "finding": "F-C1501", "expected": "src/fhir_l2.rs",
        "counterexample": "cx_fc1501::counterexample_fc1501",
        "what": "Schedule saves the %SYS.Task, then records task_id in a separate autocommit UPDATE; a failed UPDATE "
                "leaves a task the registry does not name (FHIRGraph.cls:701-703)",
    },
    "control_f1511_upsert_before_load": {
        "module": "15", "finding": "F-1511", "expected": "src/fhir_l2.rs",
        "counterexample": "cx_f1511::counterexample_f1511",
        "what": "Register upserts fhir_graphs before LoadColumns can throw, with no transaction (FHIRGraph.cls:235-258, "
                "274-276)",
    },
    "control_progress_rederive_restart": {
        "module": "15", "finding": "progress-only (INT-F5.7, spec 235 FR-024; as built and intended)",
        "expected": "src/fhir_progress.rs", "counterexample": "cx_progress::counterexample_progress",
        "progress_only": True,
        "what": "an interrupted re-derivation pass starts again from the first key (FHIRGraph.cls:573-581, 1451-1473)",
    },
    # modules 16 and 17: one HTTP call through IVGClient and the Cypher HTTP server
    "control_fc1604_server_reruns_write": {
        "module": "16", "finding": "F-C1604 (HD-1603)", "expected": "src/call_l2.rs",
        "counterexample": "cx_fc1604::counterexample_fc1604",
        "what": "_run_cypher runs the query again after any exception, a write whose statement left included "
                "(cypher_api.py:239-250)",
    },
    "control_fc1602_unknown_as_client_error": {
        "module": "16", "finding": "F-C1602", "expected": "src/call_l2.rs",
        "counterexample": "cx_fc1602::counterexample_fc1602",
        "what": "a lost IRIS connection after the statement left is answered HTTP 400, a definite client error "
                "(cypher_api.py:369-376)",
    },
    "control_fc1703_client_resends_write": {
        "module": "17", "finding": "F-C1703 (HD-1702)", "expected": "src/call_l2.rs",
        "counterexample": "cx_fc1703::counterexample_fc1703",
        "what": "IVGClient._post resends the same POST after a timeout or a 5xx whatever the query (sdk.py:209-228)",
    },
    # module 16: a unit of work over Bolt and the Neo4j HTTP commit route
    "control_f1601_bolt_run_commits": {
        "module": "16", "finding": "F-1601", "expected": "src/unit_l2.rs",
        "counterexample": "cx_f1601::counterexample_f1601",
        "what": "Bolt BEGIN/COMMIT/ROLLBACK do nothing and every RUN commits (bolt_server.py:500-510, 579-581)",
    },
    "control_f1610_tx_commit_per_statement": {
        "module": "16", "finding": "F-1610", "expected": "src/unit_l2.rs",
        "counterexample": "cx_f1610::counterexample_f1610",
        "what": "/db/neo4j/tx/commit runs each statement through _run_cypher, which commits it (cypher_api.py:391-401)",
    },
    # modules 16 and 17: the authorization boundary and the client's status map
    "control_f1614_app_without_key_gate": {
        "module": "16", "finding": "F-1614", "expected": "src/auth_l2.rs",
        "counterexample": "cx_f1614::counterexample_f1614",
        "what": "the demo server's app has no ApiKeyMiddleware (src/iris_demo_server/app.py:1-22)",
    },
    "control_fc1603_bolt_binds_every_interface": {
        "module": "16", "finding": "F-C1603", "expected": "src/auth_l2.rs",
        "counterexample": "cx_fc1603::counterexample_fc1603",
        "what": "BOLT_TCP_HOST defaults to 0.0.0.0 unless `ivg server start` set it (cypher_api.py:51; cli.py:429)",
    },
    "control_f1714_unmapped_refusal": {
        "module": "17", "finding": "F-1714", "expected": "src/auth_l2.rs",
        "counterexample": "cx_f1714::counterexample_f1714",
        "what": "explain, load_ndjson and AsyncIVGClient raise httpx's HTTPStatusError for 401/403 (sdk.py:166-182, 254-281)",
    },
    # module 17: the SQL adapter
    "control_hd1701_read_only_ignored": {
        "module": "17", "finding": "HD-1701 (live ib-HD1701-readonly-flag)", "expected": "src/sqla_l2.rs",
        "counterexample": "cx_hd1701::counterexample_hd1701_read_only",
        "what": "execute_sql(read_only=True) runs any statement (iris_sql_store.py:1522-1531)",
    },
    "control_hd1701_write_reported_failed": {
        "module": "17", "finding": "HD-1701 observation (ib-HD1701-readonly-flag; unfiled candidate S3)",
        "expected": "src/sqla_l2.rs", "counterexample": "cx_hd1701::counterexample_hd1701_write_reported",
        "what": "a statement with no result set that ran comes back with IVGResult.error (iris_sql_store.py:1531, 1537-1553)",
    },
    "control_f1701_unscoped_merge": {
        "module": "17", "finding": "F-1701", "expected": "src/sqla_l2.rs",
        "counterexample": "cx_f1701::counterexample_f1701",
        "what": "get_nodes with graph None reads every graph's labels and folds them by id (iris_sql_store.py:1116-1150)",
    },
    # module 17: status claims and the driver pin
    "control_f1713_status_parts_short": {
        "module": "17", "finding": "F-1713", "expected": "src/opsc_l2.rs",
        "counterexample": "cx_f1713::counterexample_f1713",
        "what": "STATUS_PARTS lacks adjacency and routines, which status() can mark unknown (status.py:11; admin.py:551, 752-753)",
    },
    "control_fc1706_driver_floor": {
        "module": "17", "finding": "F-C1706", "expected": "src/opsc_l2.rs",
        "counterexample": "cx_fc1706::counterexample_fc1706",
        "what": "pyproject asks intersystems-iris>=1.0.0 and uv.lock pins intersystems-irispython 5.3.2 "
                "(pyproject.toml:42; uv.lock:1358-1371)",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
GROUPS = {
    "module 15 (FHIR sync, erase, task, registration; progress)": ("fhir_l1", "fhir_l2", "fhir_runs", "fhir_progress", "witness_fhir"),
    "modules 16+17 (one HTTP call: retries and status map)": ("call_l1", "call_l2", "call_runs", "witness_call"),
    "module 16 (unit of work: Bolt, HTTP tx/commit)": ("unit_l1", "unit_l2", "unit_runs", "witness_unit"),
    "modules 16+17 (authorization boundary, client status map)": ("auth_l1", "auth_l2", "witness_auth"),
    "module 17 (SQL adapter)": ("sqla_l1", "sqla_l2", "sqla_runs", "witness_sqla"),
    "module 17 (status, capability claims, driver pin)": ("opsc_l1", "opsc_l2", "witness_opsc"),
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
        "premises": "named in PROOFS.md (P-F*, PF-*, P-C*, P-U*, P-A*, P-Q*, P-O*, P-D1); none is an assumption inside a proof",
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
                funcs.append({"function": f["function"].replace("ivg_d1f_proofs::", ""), "ms": f["time"],
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
            if meta.get("progress_only"):
                # a progress-only control fails `nonincreasing` only: every safety function verifies
                r["progress_only_ok"] = bool(r.get("failing_functions")) and all(
                    f.endswith("::nonincreasing") for f in r.get("failing_functions", []))
                r["killed"] = r["killed"] and r["progress_only_ok"]
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
        "crate": f"experiment/playbook-completion/proofs-d1f ({CRATE})",
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
            f"{CRATE} baseline with --no-cheating (modules 15, 16, 17: FHIR sync/erase/task/register with progress, "
            f"HTTP call retries and status map, Bolt/HTTP units, authorization boundary, SQL adapter, status/capability "
            f"claims and driver pin: L1, L2, refinement, invariants, witnesses): {base.get('verified')} verified, {base.get('errors')} errors; "
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
