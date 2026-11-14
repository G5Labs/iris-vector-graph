#!/usr/bin/env python3
"""Proof gate of the PROOFS-D1C lane (experiment/playbook-completion/proofs-d1c; proof debt D-1, playbook §3.3).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-d1c/tools/run_proofs.py              # trust scan, baseline, controls
    python experiment/playbook-completion/proofs-d1c/tools/run_proofs.py --register   # ... and register the runs
    PROOFS_OUT_DIR=<dir> python .../run_proofs.py                                     # a re-check: logs and RESULTS.json
                                                                                       # go to <dir>, nothing overwritten

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom or uninterpreted
   function. The actors dependency (verified in the same build, without --no-cheating, which is forwarded to this
   crate only) is scanned for the same items. vstd is Verus's trusted base and is listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors (modules 03 and 05 L1/L2, refinement,
   invariants, theorems, non-vacuity witnesses).
3. Controls: each Cargo feature puts back one as-built decision of the pin. It must make verification fail with every
   error located in its expected file and every failing function in that file's module, and its proved
   counterexample (src/cx_*.rs, compiled only with that feature: a run of the L2 step relation, as the control
   changes it, from the initial state to a step that is not an L1 step) must verify in the same build.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy /usr/bin/time timeout 3600 cargo verus
verify ...` after `cargo clean -p ivg-d1c-proofs` (a cached build replays old diagnostics without verifying). A
timeout, a resource limit or a missing result is a failure, never a pass. Logs: $RUN_DIR/proofs-d1c/<tag>.log
(diagnostics, plus one line the runner appends with the counts read from the JSON) and <tag>.json (Verus JSON), or
under $PROOFS_OUT_DIR when set. Result: proofs-d1c/RESULTS.json (or $PROOFS_OUT_DIR/RESULTS.json).
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
CRATE = "ivg-d1c-proofs"
LANE = "proofs-d1c"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

CONTROLS = {
    # the structural-versus-temporal edge (modules 03 and 05; module 12's prefix erase)
    "control_f0304_store_no_adopt": {
        "module": "03", "finding": "F-0304", "expected": "src/edge_l2.rs",
        "counterexample": "cx_f0304::counterexample_f0304",
        "what": "store_edge swallows the duplicate over a temporal edge's marked row and never adopts it, so the "
                "triple's last temporal delete deletes the stored edge (nodes_edges.py:2560-2588)",
    },
    "control_f0505_marker_predicate": {
        "module": "05", "finding": "F-0505 / HD-0302", "expected": "src/edge_l2.rs",
        "counterexample": "cx_f0505::counterexample_f0505",
        "what": "the deleters' marker test is IsTemporalMarked's %Get(\"temporal\") = 1, true for JSON true, 1 and "
                "\"1\", so an explicit {\"temporal\": 1} edge is deleted by the temporal side (Adjacency.cls:736-748)",
    },
    "control_f0507_purge_keeps_rows": {
        "module": "05", "finding": "F-0507", "expected": "src/edge_l2.rs",
        "counterexample": "cx_f0507::counterexample_f0507",
        "what": "TemporalIndex.Purge is EraseAll: every temporal global goes and no marked row is retracted "
                "(TemporalIndex.cls:381-392, 808-811)",
    },
    "control_fc0501_refused_write_partial": {
        "module": "05", "finding": "F-C0501", "expected": "src/edge_l2.rs",
        "counterexample": "cx_fc0501::counterexample_fc0501",
        "what": "WriteStores sets tout/tin/bucket before AssertTemporalRow, whose refused edge INSERT throws, and no "
                "transaction takes them back (TemporalIndex.cls:80-111; Adjacency.cls:597-608)",
    },
    "control_hd0302_delete_removes_row": {
        "module": "03", "finding": "HD-0302 (intent-a-hd0302-temporal-row-delete)", "expected": "src/edge_l2.rs",
        "counterexample": "cx_hd0302::counterexample_hd0302",
        "what": "delete_edge deletes the triple's row, marked or adopted, while its timestamps remain "
                "(nodes_edges.py:1414-1433)",
    },
    "control_fc1203_prefix_from_node_rows": {
        "module": "12", "finding": "F-C1203", "expected": "src/edge_l2.rs",
        "counterexample": "cx_fc1203::counterexample_fc1203",
        "what": "EraseNodes selects the prefix's ids from Graph_KG.nodes only, so a temporal-only edge (no row, no "
                "endpoint rows) is never erased (Eraser.cls:322-348; TemporalIndex.cls:400-453)",
    },
    "control_fc0301_adopt_after_commit": {
        "module": "03", "finding": "F-C0301", "expected": "src/edge_l2.rs",
        "counterexample": "cx_fc0301::counterexample_fc0301",
        "what": "create_edge commits the guarded insert, then adopts the marked row in a statement of its own; a "
                "temporal delete in between leaves the call answering False with no edge (nodes_edges.py:1236-1252)",
    },
    # module 03: the ledger's statement link
    "control_f0303_direct_delete_keeps_stmt": {
        "module": "03", "finding": "F-0303", "expected": "src/stmt_l2.rs",
        "counterexample": "cx_f0303::counterexample_f0303",
        "what": "delete_edge is a plain SQL DELETE: ^IVG.Ledger(\"stmt\") and (\"tuple\") stay live, and a "
                "re-created edge inherits the statement (nodes_edges.py:1414-1433; cf. Eraser.cls:641-683)",
    },
    # module 03: bulk atomicity
    "control_f0305_chunks_commit_alone": {
        "module": "03", "finding": "F-0305", "expected": "src/bulk_l2.rs",
        "counterexample": "cx_f0305::counterexample_f0305",
        "what": "outside a caller's transaction the server loader runs on the engine's Native API connection (another "
                "process), so each chunk's TCOMMIT is durable on its own (nodes_edges.py:1715-1757; EdgeScan.cls:352, 424)",
    },
    # module 05: bucket aggregates
    "control_f0501_update_counted_again": {
        "module": "05", "finding": "F-0501", "expected": "src/tagg_l2.rs",
        "counterexample": "cx_f0501::counterexample_f0501",
        "what": "an update-mode write skips the collision check and $Increments bucket, tagg count and sum again "
                "(TemporalIndex.cls:80-118)",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
GROUPS = {
    "modules 03+05 (structural-versus-temporal edge)": ("edge_l1", "edge_l2", "edge_runs", "witness_edge"),
    "module 03 (ledger statement link)": ("stmt_l1", "stmt_l2", "stmt_runs", "witness_stmt"),
    "module 03 (bulk atomicity)": ("bulk_l1", "bulk_l2", "bulk_runs", "witness_bulk"),
    "module 05 (bucket aggregates)": ("tagg_l1", "tagg_l2", "tagg_runs", "witness_tagg"),
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
        "premises": "named in PROOFS.md (P-E1..P-E9, P-L1..P-L3, P-B1..P-B3, P-T1..P-T3); none is an assumption inside a proof",
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
                funcs.append({"function": f["function"].replace("ivg_d1c_proofs::", ""), "ms": f["time"],
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
        "crate": f"experiment/playbook-completion/proofs-d1c ({CRATE})",
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
            f"{CRATE} baseline with --no-cheating (modules 03 and 05: structural-versus-temporal edge, ledger statement "
            f"link, bulk atomicity, bucket aggregates: L1, L2, refinement, invariants, witnesses): {base.get('verified')} verified, {base.get('errors')} errors; "
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
