#!/usr/bin/env python3
"""Proof gate of the PROOFS-D1D lane (experiment/playbook-completion/proofs-d1d; proof debt D-1, playbook §3.3).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-d1d/tools/run_proofs.py              # trust scan, baseline, controls
    python experiment/playbook-completion/proofs-d1d/tools/run_proofs.py --register   # ... and register the runs
    PROOFS_OUT_DIR=<dir> python .../run_proofs.py                                     # a re-check: logs and RESULTS.json
                                                                                       # go to <dir>, nothing overwritten
    python .../run_proofs.py --round r2 --register   # a later decisive round: logs under $RUN_DIR/proofs-d1d/r2, registry
                                                     # ids proofs-d1d-r2-*; earlier rounds' records and logs stay

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom or uninterpreted
   function. The actors dependency (verified in the same build, without --no-cheating, which is forwarded to this
   crate only) is scanned for the same items. vstd is Verus's trusted base and is listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors (modules 07, 08 and 09 L1/L2, refinement,
   invariants, theorems, non-vacuity witnesses).
3. Controls: each Cargo feature puts back one as-built decision of the pin. It must make verification fail with every
   error located in its expected file and every failing function in that file's module, and its proved
   counterexample (src/cx_*.rs, compiled only with that feature: a run of the L2 step relation, as the control
   changes it, from the initial state to a step that is not an L1 step) must verify in the same build.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy /usr/bin/time timeout 3600 cargo verus
verify ...` after `cargo clean -p ivg-d1d-proofs` (a cached build replays old diagnostics without verifying). A
timeout, a resource limit or a missing result is a failure, never a pass. Logs: $RUN_DIR/proofs-d1d/<tag>.log
(diagnostics, plus one line the runner appends with the counts read from the JSON) and <tag>.json (Verus JSON), or
under $PROOFS_OUT_DIR when set. Result: proofs-d1d/RESULTS.json (or $PROOFS_OUT_DIR/RESULTS.json).
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
CRATE = "ivg-d1d-proofs"
LANE = "proofs-d1d"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

CONTROLS = {
    # module 07, one BM25 index's writers and the caller's transaction
    "control_fc0702_bare_trollback": {
        "module": "07", "finding": "F-C0702", "expected": "src/bmw_l2.rs",
        "counterexample": "cx_fc0702::counterexample_fc0702",
        "what": "a failed Insert/Delete's Catch runs `If $TLevel > 0 TRollback`, every level: the caller's open "
                "transaction ends and its uncommitted rows go (BM25Index.cls:487, :508)",
    },
    "control_f0701_build_in_place": {
        "module": "07", "finding": "F-0701", "expected": "src/bmw_l2.rs",
        "counterexample": "cx_f0701::counterexample_f0701",
        "what": "Build kills and rewrites the live index with no lock and no transaction, header last from its own "
                "count; an Insert during it is visible over a half-built index and left uncounted (BM25Index.cls:97-175)",
    },
    "control_f0704_late_refusal": {
        "module": "07", "finding": "F-0704", "expected": "src/bmw_l2.rs",
        "counterexample": "cx_f0704::counterexample_f0704",
        "what": "the index handle refuses a 0-row build after Build replaced the index (vector.py:299-310; "
                "BM25Index.cls:99)",
    },
    # module 07, the namespace's indexes
    "control_fc0701_stop_name_accepted": {
        "module": "07", "finding": "F-C0701 / F-0706", "expected": "src/bmn_l2.rs",
        "counterexample": "cx_fc0701::counterexample_fc0701",
        "what": "Build/Insert/Drop accept \"__stop__\": its structure subscripts become stopwords of every index "
                "(BM25Index.cls:41-50, :83; _validate.py:163-179)",
    },
    "control_f0705_absent_graph_is_default": {
        "module": "07", "finding": "F-0705", "expected": "src/bmn_l2.rs",
        "counterexample": "cx_f0705::counterexample_f0705",
        "what": "Info answers graph \"\" for an index with no graph subscript, read as the default graph "
                "(BM25Index.cls:612; vector.py:164-185)",
    },
    "control_f0707_no_scope_check": {
        "module": "07", "finding": "F-0707", "expected": "src/bmn_l2.rs",
        "counterexample": "cx_f0707::counterexample_f0707",
        "what": "ivg.bm25.search under USE GRAPH answers from another graph's index (translator.py:3133-3134, 3283-3292)",
    },
    "control_f0702_erase_keeps_index": {
        "module": "07", "finding": "F-0702", "expected": "src/bmn_l2.rs",
        "counterexample": "cx_f0702::counterexample_f0702",
        "what": "a graph erasure leaves the BM25 indexes built for the graph (Eraser.cls:138-147; GraphStores.cls:26-133)",
    },
    # module 08, Cypher write queries on the SQL path
    "control_f0801_ttl_window": {
        "module": "08", "finding": "F-0801 (TTL window)", "expected": "src/cyw_l2.rs",
        "counterexample": "cx_f0801_ttl::counterexample_f0801_ttl",
        "what": "the ledger guard answers from Meta cached for 5 s: a Cypher write commits after strict mode was set "
                "(guard.py:20, 38-41; query.py:2299-2301)",
    },
    "control_f0801_fail_open": {
        "module": "08", "finding": "F-0801 (fail-open)", "expected": "src/cyw_l2.rs",
        "counterexample": "cx_f0801_failopen::counterexample_f0801_failopen",
        "what": "a guard probe that cannot run reads never-enabled: a Cypher write commits under strict mode "
                "(guard.py:42-56)",
    },
    "control_f0805_literal_insert_unguarded": {
        "module": "08", "finding": "F-0805", "expected": "src/cyw_l2.rs",
        "counterexample": "cx_f0805::counterexample_f0805",
        "what": "CREATE between literal endpoints is a bare INSERT: an existing relationship fails the whole query "
                "(translator.py:10212-10248)",
    },
    "control_fc0803_top1_copy": {
        "module": "08", "finding": "F-C0803", "expected": "src/cyw_l2.rs",
        "counterexample": "cx_fc0803::counterexample_fc0803",
        "what": "MERGE ... ON CREATE SET r = a copies (SELECT TOP 1 a.node_id ...) onto every merged relationship "
                "(translator.py:12362-12395)",
    },
    "control_f0810_null_keeps_key": {
        "module": "08", "finding": "F-0810", "expected": "src/cyw_l2.rs",
        "counterexample": "cx_f0810::counterexample_f0810",
        "what": "SET n.p = <literal null> updates the row to '' and keeps the key (translator.py:13655-13665)",
    },
    # module 08, graph scope of reads
    "control_f0802_shortcut_unscoped": {
        "module": "08", "finding": "F-0802", "expected": "src/cys_l2.rs",
        "counterexample": "cx_f0802::counterexample_f0802",
        "what": "the count UNION text shortcut counts every graph's rows under USE GRAPH (query.py:1843-1856)",
    },
    "control_f0816_dblabels_unscoped": {
        "module": "08", "finding": "F-0816", "expected": "src/cys_l2.rs",
        "counterexample": "cx_f0816::counterexample_f0816",
        "what": "db.labels() lists every graph's labels under USE GRAPH (engine.py:1313-1318)",
    },
    "control_f0818_vlp_crosses_graphs": {
        "module": "08", "finding": "F-0818", "expected": "src/cys_l2.rs",
        "counterexample": "cx_f0818::counterexample_f0818",
        "what": "an all-graphs variable-length walk from a WITH-carried start walks every graph (translator.py:15404-15431)",
    },
    # module 09, the compiled-plan cache
    "control_f0901_shared_class_name": {
        "module": "09", "finding": "F-0901", "expected": "src/planc_l2.rs",
        "counterexample": "cx_f0901::counterexample_f0901",
        "what": "a build compiles into IVGC.P<$ZCRC(shape,7)>: a colliding shape's build recompiles the class a reader "
                "is running (Gen.cls:69, 183-207)",
    },
    "control_fc0901_mark_any_entry": {
        "module": "09", "finding": "F-C0901", "expected": "src/planc_l2.rs",
        "counterexample": "cx_fc0901::counterexample_fc0901",
        "what": "a build marks ok whatever entry its hash holds: one shape's entry runs another shape's class for good "
                "(Gen.cls:207)",
    },
    # module 09, a native read against the SQL path
    "control_f0902_crc_identity": {
        "module": "09", "finding": "F-0902", "expected": "src/nread_l2.rs",
        "counterexample": "cx_f0902::counterexample_f0902",
        "what": "the interpreter tells used relationships apart by $ZCRC: two colliding relationships are taken as one "
                "(Exec.cls:1243-1245)",
    },
    "control_f0908_run_unchecked": {
        "module": "09", "finding": "F-0908 (intent-undecided, HD-0901)", "expected": "src/nread_l2.rs",
        "counterexample": "cx_f0908::counterexample_f0908",
        "what": "Exec.Run checks no privilege: a process of a user without SELECT that never passed a check is "
                "answered (Exec.cls:32-72; engine.py:559-586)",
    },
    "control_hd0902_shadow_swallows_native_error": {
        "module": "09", "finding": "HD-0902 (assumption)", "expected": "src/nread_l2.rs",
        "counterexample": "cx_hd0902::counterexample_hd0902",
        "what": "in shadow mode a native exception yields None: the SQL rows are returned uncompared "
                "(query.py:2069-2077, 2146-2152)",
    },
    "control_f0906_gate_edge_index_only": {
        "module": "09", "finding": "F-0906", "expected": "src/nread_l2.rs",
        "counterexample": "cx_f0906::counterexample_f0906",
        "what": "the native gate opens on the edge index alone: labels are read from a ^KG the label writes do not keep "
                "(native_plan.py:528-529)",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
GROUPS = {
    "module 07 (one BM25 index's writers, the caller's transaction)": ("bmw_l1", "bmw_l2", "bmw_runs", "witness_bmw"),
    "module 07 (the namespace's indexes: stopwords, graph scope, erasure)": ("bmn_l1", "bmn_l2", "bmn_runs", "witness_bmn"),
    "module 08 (Cypher write queries under the ledger guard)": ("cyw_l1", "cyw_l2", "cyw_runs", "witness_cyw"),
    "module 08 (graph scope of reads)": ("cys_l1", "cys_l2", "witness_cys"),
    "module 09 (compiled-plan cache)": ("planc_l1", "planc_l2", "planc_runs", "witness_planc"),
    "module 09 (a native read against the SQL path)": ("nread_l1", "nread_l2", "nread_runs", "witness_nread"),
}


ROUND = ""


def run_dir() -> Path:
    d = Path(os.environ.get("PROOFS_OUT_DIR") or (Path(os.environ["RUN_DIR"]) / LANE))
    if ROUND:
        d = d / ROUND
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
        "premises": "named in PROOFS.md (P-W1..P-W4, P-N1..P-N3, P-C1..P-C5, P-S1, P-P1..P-P4, P-R1..P-R3); none is an assumption inside a proof",
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
                funcs.append({"function": f["function"].replace("ivg_d1d_proofs::", ""), "ms": f["time"],
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
    ap.add_argument("--round", default="", help="a later decisive round: its own log directory and registry ids")
    a = ap.parse_args()
    global ROUND
    ROUND = a.round
    rid = f"{LANE}-{ROUND}" if ROUND else LANE

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
        "crate": f"experiment/playbook-completion/proofs-d1d ({CRATE})",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "verus": next((v for v in verus_v if v[:1].isdigit()), None),
        "actors_rev": ACTORS_REV,
        "sources_sha256": sha,
        "round": ROUND or "r1",
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
        reg(f"{rid}-baseline", "proof", "pass" if base["pass"] and trust_ok else "fail", base,
            f"{CRATE} baseline with --no-cheating (modules 07, 08, 09: BM25 writers and caller transaction, BM25 namespace, "
            f"Cypher writes under the ledger guard, read scope, compiled-plan cache, native read vs SQL path: L1, L2, "
            f"refinement, invariants, witnesses): {base.get('verified')} verified, {base.get('errors')} errors; "
            f"trust inventory {'empty' if trust_ok else 'NOT empty'}; model-level only")
        for feat, r in controls.items():
            short = feat.replace("control_", "").replace("_", "-")
            reg(f"{rid}-{short}", "control", "expected-violation" if r["killed"] and r["counterexample_verified"]
                else "fail", r,
                f"{feat} ({r['finding']}, module {r['module']}): {r.get('errors')} errors, all in {r['expected']}: "
                f"{r['error_locations']}; failing functions {r.get('failing_functions')}; counterexample "
                f"{r['counterexample']} {'verified' if r['counterexample_verified'] else 'NOT verified'}")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
