#!/usr/bin/env python3
"""Proof gate of crate proofs-pa3 (lane models-2; proof debt D-13, playbook §3.3): the BREADTH-PROOFS crate
(experiment/playbook-completion/proofs-breadth, D-1) copied with premise P-A3 removed (EraseGraph interleaves with writers
of its own graph; reviewed guards R11-7 and R04-5; as-built controls F-1201 and F-C1202 added to the seven copied ones).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-pa3/tools/run_proofs.py              # trust scan, baseline, controls
    python experiment/playbook-completion/proofs-pa3/tools/run_proofs.py --register   # ... and register the runs

1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom or uninterpreted
   function. The actors dependency (verified in the same build, without --no-cheating, which is forwarded to this
   crate only) is scanned for the same items. vstd is Verus's trusted base and is listed, not scanned.
2. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors (module 11 and module 04 L1/L2, refinement,
   invariants, theorems, non-vacuity witnesses).
3. Controls: each Cargo feature puts back one as-built decision of the pin. It must make verification fail with every
   error located in its expected file and every failing function in that file's module, and its proved
   counterexample (src/cx_*.rs, compiled only with that feature: a run of the L2 step relation, as the control
   changes it, from the initial state to a step that is not an L1 step) must verify in the same build.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy /usr/bin/time timeout 3600 cargo verus
verify ...` after `cargo clean -p ivg-pa3-proofs` (a cached build replays old diagnostics without verifying). A
timeout, a resource limit or a missing result is a failure, never a pass. Logs: $RUN_DIR/proofs-pa3/<tag>.log
(diagnostics) and <tag>.json (Verus JSON), or under $PROOFS_OUT_DIR when set (a re-check run, so the registered
decisive logs are never overwritten). Result: proofs-pa3/RESULTS.json (or $PROOFS_OUT_DIR/RESULTS.json).
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
CRATE = "ivg-pa3-proofs"
LANE = "proofs-pa3"          # run directory, target directory and registry id prefix
REG_LANE = "models-2"        # the lane that registers the runs
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

CONTROLS = {
    "control_f0801_ttl_cache": {
        "module": "11", "finding": "F-0801", "expected": "src/ledger_l2.rs",
        "counterexample": "cx_f0801_ttl::counterexample_f0801_ttl",
        "what": "the strict-mode guard answers from the meta it cached within its TTL (guard.py:38-41): another "
                "engine's set_strict does not refresh it",
    },
    "control_f0801_fail_open": {
        "module": "11", "finding": "F-0801 (LED-B11.3)", "expected": "src/ledger_l2.rs",
        "counterexample": "cx_f0801_failopen::counterexample_f0801_failopen",
        "what": "a guard probe that cannot run reads as never-enabled (guard.py:55-56)",
    },
    "control_f1108_unguarded_bulk_delete": {
        "module": "11", "finding": "F-1108", "expected": "src/ledger_l2.rs",
        "counterexample": "cx_f1108::counterexample_f1108",
        "what": "bulk_delete_adjacency calls no guard and erases edge rows and their statement entries "
                "(nodes_edges.py:2301-2339)",
    },
    "control_fc1101_stats_whole_row": {
        "module": "11", "finding": "F-C1101 (root cause shared with F-1102)", "expected": "src/ledger_l2.rs",
        "counterexample": "cx_fc1101::counterexample_fc1101",
        "what": "LedgerStats.Bump saves the whole stats row from the copy %OpenId opened without a lock "
                "(LedgerStats.cls:65-88)",
    },
    "control_fc0401_write_before_gen": {
        "module": "04", "finding": "F-C0401", "expected": "src/adj_l2.rs",
        "counterexample": "cx_fc0401::counterexample_fc0401",
        "what": "an adjacency writer changes ^KG(\"out\") before its first generation step (Adjacency.cls:87-89, "
                "143-148)",
    },
    "control_hd0401_erase_kills_gen": {
        "module": "04", "finding": "F-0401 / HD-0401 (erase)", "expected": "src/adj_l2.rs",
        "counterexample": "cx_hd0401_erase::counterexample_hd0401_erase",
        "what": "RemoveGraph kills ^KG(\"out\", g), then ^KG(\"gen\", g) and ^KG(\"degc\", g); a rollback restores "
                "them (Adjacency.cls:434-439)",
    },
    "control_hd0401_rebuild_kills_gen": {
        "module": "04", "finding": "HD-0401 (rebuild)", "expected": "src/adj_l2.rs",
        "counterexample": "cx_hd0401_rebuild::counterexample_hd0401_rebuild",
        "what": "RemoveAll kills ^KG(\"gen\") with out and degc and FillEdge does not step it "
                "(Adjacency.cls:452-462, 824-830)",
    },
    "control_f1201_erase_no_head_lock": {
        "module": "11", "finding": "F-1201 (P-A3 violated)", "expected": "src/ledger_l2.rs",
        "counterexample": "cx_f1201::counterexample_f1201",
        "what": "EraseGraph takes no ledger head lock (Eraser.cls:47-261): a ledger commit of a new edge into the graph "
                "lands between its row DELETE and EraseLedgerFor (1117-1144), which kills the new statement entry",
    },
    "control_fc1202_erase_unguarded": {
        "module": "04", "finding": "F-C1202 (P-A3 violated)", "expected": "src/adj_l2.rs",
        "counterexample": "cx_fc1202::counterexample_fc1202",
        "what": "EraseGraph takes no lock before its DELETE and RemoveGraph's ^IVG.AdjW(g)#\"S\" excludes no writer "
                "(Adjacency.cls:428-445): a writer inserts a new edge of g after the DELETE, and RemoveGraph's kill drops "
                "its committed adjacency entry",
    },
}
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")


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
                 "note": "Verus standard library: the trusted base (its axioms, e.g. Set::len and Map::new, are "
                         "Verus's own); not scanned"},
        "trusted_items_in_this_crate": [],
        "premises": "named in PROOFS.md (P-L1..P-L6, P-A1, P-A2, P-A4..P-A6, P-E1..P-E3; P-A3 removed); none is an "
                    "assumption inside a proof",
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
                funcs.append({"function": f["function"].replace("ivg_pa3_proofs::", ""), "ms": f["time"],
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


def per_crate_cost(base: dict) -> dict:
    """Cost of each module's proof (its L1, L2, witness), from the baseline's per-module SMT times."""
    groups = {"module 11 (ledger)": ("ledger_l1", "ledger_l2", "witness_ledger"),
              "module 04 (adjacency)": ("adj_l1", "adj_l2", "witness_adj")}
    out = {}
    mods = base.get("modules", {})
    for name, ms in groups.items():
        sel = {m: v for m, v in mods.items() if m.split("::")[-1] in ms}
        out[name] = {"modules": sel, "ms": sum(v["ms"] for v in sel.values()),
                     "rlimit": sum(v["rlimit"] for v in sel.values()),
                     "functions": sum(1 for f in base.get("all_functions", []) if f["function"].split("::")[0] in ms)}
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
    base["cost_per_module_proof"] = per_crate_cost(base)
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
        "crate": f"experiment/playbook-completion/proofs-pa3 ({CRATE})",
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
                            "--lane", REG_LANE, "--command", r["command"], "--observes", observes,
                            "--extra", f"verified={r.get('verified')}", f"errors={r.get('errors')}",
                            f"error_locations={','.join(r['error_locations'])}", f"sources_sha256={sha}",
                            f"json_log={r['json']}", f"verus_total_ms={r.get('verus_total_ms')}",
                            f"rlimit_total={r.get('rlimit_total')}"], cwd=REPO, check=True)
        reg(f"{LANE}-baseline", "proof", "pass" if base["pass"] and trust_ok else "fail", base,
            f"{CRATE} baseline with --no-cheating (modules 11 and 04 with premise P-A3 removed: EraseGraph interleaving "
            f"with writers of its graph under reviewed guards R11-7 head lock and R04-5 exclusive AdjW; L1, L2, refinement, "
            f"invariants, witnesses incl. witness_erase and witness_overlap): "
            f"{base.get('verified')} verified, {base.get('errors')} errors; trust inventory "
            f"{'empty' if trust_ok else 'NOT empty'}")
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
