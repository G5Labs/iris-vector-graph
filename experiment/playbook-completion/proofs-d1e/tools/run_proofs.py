#!/usr/bin/env python3
"""Proof gate of the PROOFS-D1E lane (experiment/playbook-completion/proofs-d1e; proof debt D-1, playbook §3.3).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-d1e/tools/run_proofs.py              # trust scan, baseline, controls
    python experiment/playbook-completion/proofs-d1e/tools/run_proofs.py --register   # ... and register the runs
    PROOFS_OUT_DIR=<dir> python .../run_proofs.py                                     # a re-check: logs and RESULTS.json
                                                                                       # go to <dir>, nothing overwritten

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom or uninterpreted
   function. The actors dependency (verified in the same build, without --no-cheating, which is forwarded to this
   crate only) is scanned for the same items. vstd is Verus's trusted base and is listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors (modules 01, 02 and 10 L1/L2, refinement,
   invariants, theorems, non-vacuity witnesses).
3. Controls: each Cargo feature puts back one as-built decision of the pin. It must make verification fail with every
   error located in its expected file and every failing function in that file's module, and its proved
   counterexample (src/cx_*.rs, compiled only with that feature: a run of the L2 step relation, as the control
   changes it, from the initial state to a step that is not an L1 step) must verify in the same build.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy /usr/bin/time timeout 3600 cargo verus
verify ...` after `cargo clean -p ivg-d1e-proofs` (a cached build replays old diagnostics without verifying). A
timeout, a resource limit or a missing result is a failure, never a pass. Logs: $RUN_DIR/proofs-d1e/<tag>.log
(diagnostics, plus one line the runner appends with the counts read from the JSON) and <tag>.json (Verus JSON), or
under $PROOFS_OUT_DIR when set. Result: proofs-d1e/RESULTS.json (or $PROOFS_OUT_DIR/RESULTS.json).
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
CRATE = "ivg-d1e-proofs"
LANE = "proofs-d1e"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

CONTROLS = {
    # module 01, install/schema
    "control_f0103_marker_admits": {
        "module": "01", "finding": "F-0103", "expected": "src/inst_l2.rs",
        "counterexample": "cx_f0103::counterexample_f0103",
        "what": "with no schema record, check_first_access admits an engine whose schema holds the marker class "
                "<package>.funcCYCMP (schema_name.py:233-235)",
    },
    "control_f0102_failure_only_logged": {
        "module": "01", "finding": "F-0102", "expected": "src/inst_l2.rs",
        "counterexample": "cx_f0102::counterexample_f0102",
        "what": "a base DDL statement failing for another reason than exists/privilege, and a failed ^KG bootstrap, are "
                "log lines only, not in the reply's warnings (_engine/schema.py:2508-2511, 2680-2681)",
    },
    "control_f0109_upgrade_default_schema": {
        "module": "01", "finding": "F-0109", "expected": "src/inst_l2.rs",
        "counterexample": "cx_f0109::counterexample_f0109",
        "what": "upgrade_to_4_0_0 works on its schema= argument (default Graph_KG) and never reads ^IVG.Deploy(\"schema\") "
                "(migrations/upgrade.py:58, 140)",
    },
    "control_f0101_removed_unchecked": {
        "module": "01", "finding": "F-0101", "expected": "src/inst_l2.rs",
        "counterexample": "cx_f0101::counterexample_f0101",
        "what": "remove_legacy_objects reports removed=True after DROP VIEW whatever _drop answered, and for a class's "
                "later items whatever the class delete answered (_engine/legacy.py:670-684)",
    },
    # module 02, graph names and graph-scoped reads
    "control_f0202_writer_skips_name_check": {
        "module": "02", "finding": "F-0202", "expected": "src/gid_l2.rs",
        "counterexample": "cx_f0202::counterexample_f0202",
        "what": "create_node and store_node call no graph-name check and write rows under the reserved name \"0\" "
                "(_engine/nodes_edges.py:968-1105)",
    },
    "control_f0206_hydrate_from_default": {
        "module": "02", "finding": "F-0206 / HD-0201", "expected": "src/gid_l2.rs",
        "counterexample": "cx_f0206::counterexample_f0206",
        "what": "get_nodes_by_label takes every graph's ids and hydrates them from the default graph "
                "(_engine/nodes_edges.py:760-794, 621-695)",
    },
    "control_f0106_keys_join_on_id": {
        "module": "01/02", "finding": "F-0106 / HD-0201", "expected": "src/gid_l2.rs",
        "counterexample": "cx_f0106::counterexample_f0106",
        "what": "get_property_keys(label) joins rdf_labels to rdf_props on s alone (_engine/schema.py:500-515)",
    },
    # module 02, multigraph mode
    "control_f0201_ekey0_guard": {
        "module": "02", "finding": "F-0201", "expected": "src/gmode_l2.rs",
        "counterexample": "cx_f0201::counterexample_f0201",
        "what": "the single-edge writers and the mode-off insert are stopped by a row at ekey 0 only "
                "(_engine/nodes_edges.py:1214-1217, 1257-1273; 2560-2581)",
    },
    "control_f0208_mode_cached_forever": {
        "module": "02", "finding": "F-0208", "expected": "src/gmode_l2.rs",
        "counterexample": "cx_f0208::counterexample_f0208",
        "what": "is_multigraph caches each graph's mode per engine with no expiry; another engine's Set(g, 0) is not "
                "seen (_engine/admin.py:917-926)",
    },
    "control_f0207_set_off_unlocked": {
        "module": "02", "finding": "F-0207", "expected": "src/gmode_l2.rs",
        "counterexample": "cx_f0207::counterexample_f0207",
        "what": "GraphMode.Set(g, 0) counts parallel triples, then kills the mode, with no lock any writer takes "
                "(GraphMode.cls:26-45)",
    },
    # module 10, cached answers and the read footprint
    "control_f1004_create_moves_no_token": {
        "module": "10", "finding": "F-1004", "expected": "src/acache_l2.rs",
        "counterexample": "cx_f1004::counterexample_f1004",
        "what": "a node written with no edge moves no token a cached answer is checked against; the PPR key holds the "
                "seeds and settings only (iris_sql_store.py:2248-2258; AlgoCache.cls:27-36)",
    },
    "control_f1003_owner_cap": {
        "module": "10", "finding": "F-1003 / HD-1004", "expected": "src/acache_l2.rs",
        "counterexample": "cx_f1003::counterexample_f1003",
        "what": "PageRankGlobalJson lists at most 10,000 rows (PageRank.cls:503-520)",
    },
    "control_fc1001_read_creates_routines": {
        "module": "10", "finding": "F-C1001", "expected": "src/acache_l2.rs",
        "counterexample": "cx_fc1001::counterexample_fc1001",
        "what": "triangle_count's Arno probe runs CREATE OR REPLACE FUNCTION for the $ZF wrappers the routine record "
                "does not list and saves the record (arno_bridge.py:106-134, 360-417; routine_record.py:93-95)",
    },
    # module 10, traversal result contracts
    "control_hd1003_direction_unchecked": {
        "module": "10", "finding": "HD-1003", "expected": "src/atrav_l2.rs",
        "counterexample": "cx_hd1003::counterexample_hd1003",
        "what": "ShortestLength reads every direction but \"both\" as \"out\" and shortest_path_length passes \"in\" "
                "through; ShortestPathJson answers no path for a direction it does not walk (TraversalPaths.cls:5-80, "
                "117-122; iris_sql_store.py:2162-2181)",
    },
    "control_f1008_every_graph_mixed": {
        "module": "10", "finding": "F-1008", "expected": "src/atrav_l2.rs",
        "counterexample": "cx_f1008::counterexample_f1008",
        "what": "VarLength's every-graph mode reads a node's entries in every graph at each hop (VarLength.cls:44-51, "
                "126-148)",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
GROUPS = {
    "module 01 (install/schema: record, readiness, upgrade, legacy removal)": ("inst_l1", "inst_l2", "inst_runs", "witness_inst"),
    "module 02 (graph names and graph-scoped reads)": ("gid_l1", "gid_l2", "gid_runs", "witness_gid"),
    "module 02 (multigraph mode)": ("gmode_l1", "gmode_l2", "gmode_runs", "witness_gmode"),
    "module 10 (cached answers, PageRank completeness, read footprint)": ("acache_l1", "acache_l2", "acache_runs", "witness_acache"),
    "module 10 (shortest-path direction, walk graph scope, label propagation)": ("atrav_l1", "atrav_l2", "atrav_runs", "witness_atrav"),
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
        "premises": "named in PROOFS.md (P-I1..P-I6, P-G1..P-G4, P-M1..P-M3, P-C1..P-C5, P-T1..P-T5); none is an assumption inside a proof",
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
                funcs.append({"function": f["function"].replace("ivg_d1e_proofs::", ""), "ms": f["time"],
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
        "crate": f"experiment/playbook-completion/proofs-d1e ({CRATE})",
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
            f"{CRATE} baseline with --no-cheating (module 01 record/readiness/upgrade/legacy removal; module 02 graph names, "
            f"graph-scoped reads, multigraph mode; module 10 cached answers, PageRank completeness, read footprint, "
            f"shortest-path direction, walk graph scope, label propagation: L1, L2, refinement, invariants, witnesses): "
            f"{base.get('verified')} verified, {base.get('errors')} errors; "
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
