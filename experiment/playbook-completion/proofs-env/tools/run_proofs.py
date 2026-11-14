#!/usr/bin/env python3
"""Gate of the PROOFS-ENV lane (experiment/playbook-completion/proofs-env, proof debt D-7).

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-env/tools/run_proofs.py                # trust, baseline, controls, differential
    python experiment/playbook-completion/proofs-env/tools/run_proofs.py --register     # ... and register the decisive runs
    python .../run_proofs.py --only ctl_unlock_immediate,...                             # a subset of controls (never registered)
    PROOFS_OUT_DIR=$RUN_DIR/proofs-env-recheck python .../run_proofs.py                  # a recheck: logs and RESULTS.json there

Pattern of proofs-mech/tools/run_proofs.py, adapted to clause controls:
1. Trust inventory: src/*.rs may contain no assume, admit, external_body/external, axiom, uninterpreted function or
   assume_specification (comments stripped). The crate's only dependency is vstd (Verus's trusted base: listed, not
   scanned). The harness (harness/src/main.rs) is unverified test code (JSON, interning, choice enumeration), listed.
2. Hygiene: every `// CONTROL <feature> clause=.. mutant=.. cx=..` line in src/clauses.rs is followed by its
   `#[cfg(feature = "<feature>")]` definition of `validated()`; Cargo.toml declares exactly these features; every
   feature has at least one `// LOCATE` line; every LOCATE names declared features; every cx function exists.
3. Baseline: `cargo verus verify -- --no-cheating` (after `cargo clean -p ivg-proofs-env`) must report 0 errors and every
   function must verify, the counterexamples among them. The stream is parsed with tools/verus_json.py (cold builds
   print dependency summaries before the JSON).
4. Each control (one feature: `validated()` with one clause weakened) must fail with errors exactly at the lines whose
   LOCATE names it, its failing functions must be exactly the functions containing those lines, every other function
   must verify and be the baseline's, and every counterexample must verify in the same build.
5. Differential (no IRIS): build iris-contract (r6) and contract-2's binary and the harness (each into its own target
   under $RUN_DIR/target), then for every registered round: `iris-contract permitted` and `proofs-env-harness check`
   (the verified exec model over every choice sequence) -- the Verus model's set must equal the contract's on every
   case in the Verus subset, every observation must lie in it; mutants of the Verus model are killed by observations.

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy /usr/bin/time ... timeout 3600 cargo verus
verify ...` (it queues behind other heavy jobs). Each invocation writes into a NEW directory <out>/run-<UTC stamp>/
(out = $PROOFS_OUT_DIR or $RUN_DIR/proofs-env); each Verus text log ends with a line `RUNNER SUMMARY (<json>, sha256
<sha of the JSON log>): verification results:: <n> verified, <m> errors ...`.
RESULTS.json: $PROOFS_OUT_DIR/RESULTS.json when set, else experiment/playbook-completion/proofs-env/RESULTS.json.
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
COMPLETION = Path(os.environ.get("IVG_COMPLETION_DIR") or PROOFS.parent)
REPO = COMPLETION.parent.parent
LOCKS = COMPLETION / "tools" / "locks.sh"
REGISTER = COMPLETION / "tools" / "register_run.py"
RUNS = COMPLETION / "evidence" / "runs"
sys.path.insert(0, str(COMPLETION / "tools"))
from verus_json import parse_verus_json  # noqa: E402

CRATE = "ivg-proofs-env"
MOD = "ivg_proofs_env::"
LANE = "proofs-env"
FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# The registered rounds (cases + observations under $RUN_DIR) and the contract binary deciding each: r6 is the
# validated round of iris-contract (VALIDATED_ROUND); r2, r4, r5 are earlier rounds the r6 model reproduces with 0
# outside (CONTRACT.md); contract-2's rounds and its regression of r2 / r6 use contract-2's binary.
ROUNDS = [
    ("r6", "env/r6", "r6", "T,S,E,C", False),
    ("r2", "env/r2", "r6", "T,S,E,C", False),
    ("r4", "env/r4", "r6", "T,S,E,C", False),
    ("r5", "env/r5", "r6", "T,S,E,C", False),
    ("c2-e1-r1", "contract-2/e1-r1", "c2", "T,S,E,C,N,R,G,R0", True),
    ("c2-e1-r2", "contract-2/e1-r2", "c2", "T,S,E,C,N,R,G,R0", True),
    ("c2-x2-r1", "contract-2/x2-r1", "c2", "T,S,E,C,N,R,G,R0", True),
    ("c2-regress-r6", "env/r6", "c2", "T,S,E,C", False),
    ("c2-regress-r2", "env/r2", "c2", "T,S,E,C", False),
    # the orchestrator's targeted round for the E-STOP gap this lane reported (run env-estop-gap): stops at $TLEVEL 2
    ("estop-gap", "env/estop-gap", "r6", "T,S,E,C", False),
    # the orchestrator's single-row autocommit-off DML round (run env-dml-single), for the two mutants decided only by
    # INSERT ... SELECT cases before
    ("dml-single", "env/dml-single", "r6", "T,S,E,C", False),
]
PROBE_MUTANTS = {"freedom-waits-only (sharpening; expected alive)"}


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


def target(name: str) -> str:
    return str(Path(os.environ["RUN_DIR"]) / "target" / name)


def env(tgt: str) -> dict:
    return dict(os.environ, CARGO_TARGET_DIR=tgt)


def sources() -> list[Path]:
    return sorted((PROOFS / "src").glob("*.rs")) + [p for p in (PROOFS / "Cargo.toml", PROOFS / "Cargo.lock",
                                                                  PROOFS / "harness" / "src" / "main.rs",
                                                                  PROOFS / "harness" / "Cargo.toml",
                                                                  PROOFS / "harness" / "Cargo.lock") if p.exists()]


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


def trust_inventory() -> dict:
    own = scan(sorted((PROOFS / "src").glob("*.rs")), PROOFS)
    return {
        "own_sources": {"scanned": [str(p.relative_to(PROOFS)) for p in sorted((PROOFS / "src").glob("*.rs"))],
                        "patterns": FORBIDDEN, "violations": own},
        "vstd": {"version": "0.0.0-2026-09-20-0158",
                 "note": "Verus standard library: the trusted base (its axioms and admits are Verus's own); not scanned"},
        "harness": {"path": "harness/src/main.rs",
                    "note": "unverified test code: reads the rounds' JSON, interns names and values, enumerates choice "
                            "sequences depth-first and renders outcomes; the outcome computation it calls (e_run) is "
                            "verified; its rendering is cross-checked by set equality with the contract binary"},
        "trusted_items_in_this_crate": [],
        "premises": "named in PROOFS.md; the discipline `disc` of the head-lock theorems is a hypothesis, never assumed",
    }


# ------------------------------------------------------------------------------------------------ control metadata

CONTROL_RE = re.compile(r"^\s*// CONTROL (\S+)\s+(.*)$")
LOCATE_RE = re.compile(r";\s*// LOCATE ((?:ctl_\w+\s*)+)$")
CFG_RE = re.compile(r'#\[cfg\(feature\s*=\s*"([^"]+)"\)\]')
FN_RE = re.compile(r"^\s*pub\s+(?:proof\s+)?fn\s+(\w+)")


def parse_controls() -> tuple[dict, dict, list[str]]:
    problems = []
    clauses = (PROOFS / "src" / "clauses.rs").read_text().splitlines()
    controls = {}
    for i, line in enumerate(clauses):
        m = CONTROL_RE.match(line)
        if m:
            kv = dict(x.split("=", 1) for x in m.group(2).split())
            nxt = clauses[i + 1] if i + 1 < len(clauses) else ""
            cm = CFG_RE.search(nxt)
            if not cm or cm.group(1) != m.group(1):
                problems.append(f"src/clauses.rs:{i + 1}: CONTROL {m.group(1)} not followed by its cfg")
            controls[m.group(1)] = {"clause": kv.get("clause"), "mutant": kv.get("mutant"), "cx": kv.get("cx"),
                                    "control_line": f"src/clauses.rs:{i + 1}", "locate": []}
    fn_of_line = {}
    for p in sorted((PROOFS / "src").glob("*.rs")):
        lines = p.read_text().splitlines()
        cur = None
        for i, line in enumerate(lines):
            fm = FN_RE.match(line)
            if fm:
                cur = f"{p.stem}::{fm.group(1)}"
            lm = LOCATE_RE.search(line)
            if lm:
                for f in lm.group(1).split():
                    if f not in controls:
                        problems.append(f"src/{p.name}:{i + 1}: LOCATE names undeclared control {f}")
                        continue
                    controls[f]["locate"].append({"at": f"src/{p.name}:{i + 1}", "function": cur})
                fn_of_line[f"src/{p.name}:{i + 1}"] = cur
    for f, c in controls.items():
        if not c["locate"]:
            problems.append(f"control {f} has no LOCATE line")
        if not re.search(rf"pub proof fn {re.escape(c['cx'] or '')}\(", (PROOFS / "src" / "cx.rs").read_text()):
            problems.append(f"control {f}: counterexample {c['cx']} not in src/cx.rs")
    cargo = (PROOFS / "Cargo.toml").read_text()
    block = cargo.split("#@CONTROLS-BEGIN", 1)[1].split("#@CONTROLS-END", 1)[0]
    declared = set(re.findall(r"^(\w+)\s*=\s*\[\]", block, re.M))
    if declared != set(controls):
        problems.append(f"Cargo.toml features differ from the controls: {sorted(declared ^ set(controls))}")
    return controls, fn_of_line, problems


# ------------------------------------------------------------------------------------------------ Verus runs

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
    log, js = d / f"{tag}.log", d / f"{tag}.json"
    if log.exists() or js.exists():
        raise SystemExit(f"refusing to overwrite {log}")
    tgt = target(LANE)
    subprocess.run(["cargo", "clean", "-p", CRATE, "--offline"], cwd=PROOFS, env=env(tgt), capture_output=True)
    cargo = ["cargo", "verus", "verify", "--offline", "--fwd-verus-args-to", "roots"]
    if features:
        cargo += ["--features", features]
    cargo += ["--", "--no-cheating", "--triggers-mode", "silent", "--time-expanded", "--output-json"]
    cmd = ["bash", str(LOCKS), "heavy", "/usr/bin/time", "-f", "WALLSECONDS %e", "timeout", "3600"] + cargo
    with open(log, "w") as fe, open(js, "w") as fo:
        rc = subprocess.run(cmd, cwd=PROOFS, env=env(tgt), stdout=fo, stderr=fe).returncode
    text = log.read_text(errors="replace")
    wall = re.findall(r"WALLSECONDS ([\d.]+)", text)
    out = {"tag": tag, "features": features, "rc": rc, "timed_out": rc == 124,
           "command": " ".join(["bash", "experiment/playbook-completion/tools/locks.sh", "heavy", "timeout", "3600"] + cargo),
           "log": rel(log), "json": rel(js), "wall_seconds": float(wall[-1]) if wall else None,
           "error_locations": locations(text),
           "resource_limit_hit": bool(re.search(r"rlimit|resource limit|timed out", text, re.I))}
    raw = js.read_bytes()
    out["json_sha256"] = hashlib.sha256(raw).hexdigest()
    dj = parse_verus_json(raw.decode(errors="replace"))
    if dj and "verified" not in dj["verification-results"]:
        dj = None  # a compile error: no counts (fail closed)
    if dj:
        vr = dj["verification-results"]
        out.update(verified=vr["verified"], errors=vr["errors"], success=vr["success"])
        t = dj["times-ms"]
        out["verus_total_ms"] = t["total"]
        out["smt_run_ms"] = t["smt"]["smt-run"]
        out["rlimit_total"] = t["smt"]["rlimit-run"]
        mods, funcs = {}, []
        for m in t["smt"].get("smt-run-module-times", []):
            mods[m["module"].replace(MOD, "")] = {"ms": m["time"], "rlimit": m["rlimit"]}
            for f in m.get("function-breakdown", []):
                funcs.append({"function": f["function"].replace(MOD, ""), "ms": f["time"], "rlimit": f["rlimit"],
                              "success": f["success"]})
        out["modules"] = dict(sorted(mods.items(), key=lambda kv: -kv[1]["rlimit"]))
        out["top_functions"] = sorted(funcs, key=lambda f: -f["rlimit"])[:10]
        out["all_functions"] = sorted(funcs, key=lambda f: f["function"])
        out["failing_functions"] = sorted(f["function"] for f in funcs if not f["success"])
        out["functions_checked"] = len(funcs)
    else:
        found = RESULT_RE.findall(text)
        out.update(verified=int(found[-1][0]) if found else None, errors=int(found[-1][1]) if found else None,
                   success=False, failing_functions=[], all_functions=[], json_parse="failed (fail closed)")
    with open(log, "a") as fe:
        fe.write(f"RUNNER SUMMARY ({js.name}, sha256 {out['json_sha256']}): verification results:: "
                 f"{out.get('verified')} verified, {out.get('errors')} errors (failing functions); rc {rc}; "
                 f"features {features or '-'}; failing functions {out.get('failing_functions')}; "
                 f"error locations {out['error_locations']}\n")
    return out


# ------------------------------------------------------------------------------------------------ differential

def build(manifest: Path, tgt: str, d: Path, tag: str) -> dict:
    log = d / f"build-{tag}.log"
    cmd = ["cargo", "build", "--release", "--offline", "--manifest-path", str(manifest)]
    with open(log, "w") as f:
        rc = subprocess.run(cmd, cwd=REPO, env=env(tgt), stdout=f, stderr=subprocess.STDOUT).returncode
    return {"tag": tag, "rc": rc, "log": rel(log), "command": f"CARGO_TARGET_DIR={tgt} " + " ".join(cmd)}


def differential() -> dict:
    d = run_dir() / "differential"
    d.mkdir(parents=True, exist_ok=True)
    rd = Path(os.environ["RUN_DIR"])
    builds = [
        build(COMPLETION / "iris-contract" / "Cargo.toml", target("proofs-env-contract-r6"), d, "iris-contract-r6"),
        build(COMPLETION / "contract-2" / "contract" / "Cargo.toml", target("proofs-env-contract-2"), d, "contract-2"),
        build(PROOFS / "harness" / "Cargo.toml", target("proofs-env-harness"), d, "harness"),
    ]
    bins = {"r6": Path(target("proofs-env-contract-r6")) / "release" / "iris-contract",
            "c2": Path(target("proofs-env-contract-2")) / "release" / "iris-contract"}
    harness = Path(target("proofs-env-harness")) / "release" / "proofs-env-harness"
    rounds = {}
    summary_lines = []
    for name, path, binary, tables, long_keys in ROUNDS:
        cases, observed = rd / path / "cases.json", rd / path / "observed.json"
        if not cases.exists() or not observed.exists():
            rounds[name] = {"missing": True}
            continue
        perm = d / f"{name}-permitted.json"
        with open(perm, "w") as f:
            prc = subprocess.run([str(bins[binary]), "permitted", str(cases)], stdout=f, stderr=subprocess.PIPE,
                                 timeout=1800).returncode
        rep = d / f"{name}-report.json"
        cmd = [str(harness), "check", str(cases), str(observed), str(perm), "--round", name, "--tables", tables,
               "--out", str(rep)] + (["--long-keys-refused"] if long_keys else [])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        summary_lines.append(r.stdout.strip())
        report = json.loads(rep.read_text()) if rep.exists() else {}
        rounds[name] = {
            "cases": rel(cases), "observed": rel(observed), "contract_binary": binary, "permitted_rc": prc,
            "permitted": rel(perm), "permitted_sha256": hashlib.sha256(perm.read_bytes()).hexdigest(),
            "report": rel(rep), "harness_rc": r.returncode, "summary": r.stdout.strip(),
            **{k: report.get(k) for k in ("cases", "in_subset", "outside_subset", "disagree", "observed_runs",
                                          "observed_outside_verus", "singleton_cases", "max_permitted", "freedom_cases",
                                          "overflow_cases", "errors")},
            "mutants_killed": sorted(k for k, v in report.get("mutants", {}).items() if v["killed"]),
            "mutant_kinds": {k: v["kind"] for k, v in report.get("mutants", {}).items()},
        }
    log = d / "differential.log"
    log.write_text("\n".join(summary_lines) + "\n")
    allm = {}
    for rr in rounds.values():
        for k, kind in rr.get("mutant_kinds", {}).items():
            allm.setdefault(k, {"kind": kind, "killed_in": []})
            if k in rr.get("mutants_killed", []):
                allm[k]["killed_in"].append([n for n, x in rounds.items() if x is rr][0])
    gating = {k: v for k, v in allm.items() if k not in PROBE_MUTANTS}
    agree = all(r.get("harness_rc") == 0 and r.get("permitted_rc") == 0 and r.get("disagree") == 0
                and r.get("observed_outside_verus") == 0 and not r.get("errors") and r.get("overflow_cases") == 0
                for r in rounds.values() if not r.get("missing"))
    tot = lambda key: sum(r.get(key) or 0 for r in rounds.values() if not r.get("missing"))
    res = {
        "builds": builds, "rounds": rounds, "log": rel(log), "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "builds_ok": all(b["rc"] == 0 for b in builds),
        "agreement": agree and all(b["rc"] == 0 for b in builds),
        "cases_in_subset": tot("in_subset"), "cases_total": tot("cases"), "observed_runs": tot("observed_runs"),
        "observed_outside_verus": tot("observed_outside_verus"), "disagreements": tot("disagree"),
        "mutants": allm,
        "gating_mutants": len(gating),
        "gating_killed": sum(1 for v in gating.values() if v["killed_in"]),
        "gating_alive": sorted(k for k, v in gating.items() if not v["killed_in"]),
        "probe_mutants": {k: allm.get(k) for k in PROBE_MUTANTS},
    }
    with open(log, "a") as f:
        f.write(f"RUNNER SUMMARY differential: agreement {res['agreement']}; cases in the Verus subset "
                f"{res['cases_in_subset']} of {res['cases_total']}; observed runs {res['observed_runs']}, outside the "
                f"Verus model {res['observed_outside_verus']}; disagreements {res['disagreements']}; gating mutants "
                f"killed {res['gating_killed']}/{res['gating_mutants']}, alive {res['gating_alive']}\n")
    res["log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
    return res


# ------------------------------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--no-differential", action="store_true")
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--id-suffix", default="")
    ap.add_argument("--id-prefix", default=LANE)
    ap.add_argument("--only", default="")
    ap.add_argument("--differential-only", action="store_true",
                    help="rerun only the differential and mutant check (no Verus); registers <prefix>-differential<suffix> "
                         "and <prefix>-mutants<suffix>; updates the differential section of RESULTS.json in place")
    a = ap.parse_args()
    if a.differential_only:
        return differential_only(a)
    if a.register and (a.only or a.baseline_only or a.no_differential or os.environ.get("IVG_COMPLETION_DIR")):
        raise SystemExit("partial runs and development copies cannot register")

    controls, fn_of_line, problems = parse_controls()
    for p in problems:
        print("HYGIENE:", p)
    selected = [f for f in controls if not a.only or f in a.only.split(",")]
    rid = lambda f: f"{a.id_prefix}-{f.replace('_', '-')}{a.id_suffix}"
    ids = [f"{a.id_prefix}-baseline{a.id_suffix}", f"{a.id_prefix}-differential{a.id_suffix}",
           f"{a.id_prefix}-mutants{a.id_suffix}"] + [rid(f) for f in selected]
    if a.register:
        taken = [i for i in ids if (RUNS / f"{i}.json").exists()]
        if taken:
            raise SystemExit(f"registry ids already recorded (a rerun needs --id-suffix): {taken}")

    trust = trust_inventory()
    for v in trust["own_sources"]["violations"]:
        print("TRUST:", v)
    sha = sources_sha256()
    base = verify("baseline")
    base_fns = {f["function"] for f in base.get("all_functions", [])}
    base_ok = {f["function"] for f in base.get("all_functions", []) if f["success"]}
    cx_names = sorted(f"cx::{c['cx']}" for c in controls.values())
    base["cx_missing"] = [x for x in cx_names if x not in base_ok]
    base["pass"] = (base["rc"] == 0 and base.get("errors") == 0 and bool(base.get("verified")) and not base["timed_out"]
                    and base_fns == base_ok and not base["cx_missing"])
    print(f"baseline: {base.get('verified')} verified, {base.get('errors')} errors, rc {base['rc']}, verus "
          f"{base.get('verus_total_ms')} ms, rlimit {base.get('rlimit_total')}, wall {base.get('wall_seconds')} s"
          + (f"; MISSING counterexamples {base['cx_missing']}" if base["cx_missing"] else ""))

    results = {}
    if not a.baseline_only:
        for feat in selected:
            c = controls[feat]
            r = verify(feat, feat)
            exp_locs = sorted({x["at"] for x in c["locate"]}, key=lambda s: (s.split(":")[0], int(s.split(":")[1])))
            exp_fail = sorted({x["function"] for x in c["locate"]})
            ok_fns = {f["function"] for f in r.get("all_functions", []) if f["success"]}
            all_fns = {f["function"] for f in r.get("all_functions", [])}
            r.update({"clause": c["clause"], "mutant": c["mutant"], "counterexample": f"cx::{c['cx']}",
                      "expected_locations": exp_locs, "expected_failing_functions": exp_fail})
            r["located"] = r["error_locations"] == exp_locs
            r["others_verify_as_baseline"] = (all_fns == base_fns) and (all_fns - set(exp_fail)) <= ok_fns
            r["counterexample_verified"] = f"cx::{c['cx']}" in ok_fns
            r["counterexamples_all_verified"] = all(x in ok_fns for x in cx_names)
            r["killed"] = (not r["timed_out"] and r.get("errors") == len(exp_locs) and r["located"]
                           and r.get("failing_functions") == exp_fail and r["others_verify_as_baseline"]
                           and r["counterexample_verified"] and r["counterexamples_all_verified"])
            r.pop("all_functions", None)
            results[feat] = r
            print(f"{feat}: {'REJECTED AT ITS LOCATED PREMISES' if r['killed'] else 'NOT AS EXPECTED'} "
                  f"({r.get('errors')} errors at {r['error_locations']}, expected {exp_locs}; failing "
                  f"{r.get('failing_functions')}; others as baseline {r['others_verify_as_baseline']}; counterexample "
                  f"{r['counterexample_verified']})")

    diff = None
    if not a.no_differential and not a.only and not a.baseline_only:
        diff = differential()
        print(f"differential: agreement {diff['agreement']}; in subset {diff['cases_in_subset']}/{diff['cases_total']}; "
              f"observed {diff['observed_runs']}, outside {diff['observed_outside_verus']}; mutants killed "
              f"{diff['gating_killed']}/{diff['gating_mutants']} alive {diff['gating_alive']}")

    trust_ok = not trust["own_sources"]["violations"]
    complete = not a.only and not a.baseline_only and not a.no_differential
    proofs_ok = trust_ok and not problems and base["pass"] and all(r["killed"] for r in results.values())
    diff_ok = diff is not None and diff["agreement"]
    result = {
        "crate": f"experiment/playbook-completion/proofs-env ({CRATE})",
        "debt": "D-7 (experiment/playbook-completion/PROOF-DEBT.md): the IRIS environment contract as a Verus "
                "specification linked to the participant contracts",
        "scope": "statements about the contract's Verus specification (a model of IRIS 2026.1 validated by the "
                 "registered rounds); the product's discipline (disc) and its code correspondence are not proved here",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "run_dir": rel(run_dir()),
        "verus": next((v for v in subprocess.run(["verus", "--version"], capture_output=True, text=True).stdout.split()
                       if v[:1].isdigit()), None),
        "sources_sha256": sha,
        "complete_run": complete,
        "hygiene_problems": problems,
        "baseline": {k: v for k, v in base.items() if k != "all_functions"} | {"functions": sorted(base_fns)},
        "controls": results,
        "differential": diff,
        "trust_inventory": trust,
        "gate_proofs": "pass" if proofs_ok and complete else ("partial-pass" if proofs_ok else "fail"),
        "gate_differential": "pass" if diff_ok else ("not-run" if diff is None else "fail"),
        "gate_mutants": (None if diff is None else ("pass" if not diff["gating_alive"] else "incomplete")),
    }
    results_path = (Path(os.environ["PROOFS_OUT_DIR"]) / "RESULTS.json" if os.environ.get("PROOFS_OUT_DIR")
                    else PROOFS / "RESULTS.json")
    if a.only or a.baseline_only or a.no_differential:
        results_path = run_dir() / "RESULTS-partial.json"
    results_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    summary = (f"proofs-env gate: proofs {result['gate_proofs'].upper()}, differential "
               f"{result['gate_differential'].upper()}, mutants {str(result['gate_mutants']).upper()} ({results_path}, "
               f"sources {sha[:12]}): baseline {base.get('verified')} verified, {base.get('errors')} errors; controls "
               f"rejected at their located premises {sum(r['killed'] for r in results.values())}/{len(results)}; trust "
               f"{'empty' if trust_ok else 'NOT empty'}")
    print(summary)
    (run_dir() / "runner-summary.txt").write_text(summary + "\n")

    if a.register:
        def reg(i, kind, res, log, command, observes, extra):
            subprocess.run([sys.executable, str(REGISTER), i, kind, res, log, "--lane", LANE, "--command", command,
                            "--observes", observes, "--extra"] + extra + [f"sources_sha256={sha}"], cwd=REPO, check=True)
        rd = Path(os.environ["RUN_DIR"])
        bl = rd / base["log"].replace("$RUN_DIR/", "")
        reg(ids[0], "proof", "pass" if base["pass"] and trust_ok and not problems else "fail", str(bl), base["command"],
            f"ivg-proofs-env baseline with --no-cheating: {base.get('verified')} verified, {base.get('errors')} errors; "
            f"trust inventory {'empty' if trust_ok else 'NOT empty'}; {len(cx_names)} counterexamples verified; the "
            f"contract's Verus subset, its exec model verified against it, the head-lock refinement and "
            f"{sum(1 for f in base_fns if f.startswith('premises::'))} premise theorems (models only)",
            [f"verified={base.get('verified')}", f"errors={base.get('errors')}", f"json_log={base['json']}",
             f"json_sha256={base['json_sha256']}", f"verus_total_ms={base.get('verus_total_ms')}",
             f"rlimit_total={base.get('rlimit_total')}"])
        dl = rd / diff["log"].replace("$RUN_DIR/", "")
        reg(ids[1], "check", "pass" if diff_ok else "fail", str(dl),
            "python experiment/playbook-completion/proofs-env/tools/run_proofs.py (differential)",
            f"verified exec model vs iris-contract/contract-2 permitted sets on {len([r for r in diff['rounds'].values() if not r.get('missing')])} "
            f"recorded rounds (no IRIS): {diff['cases_in_subset']} of {diff['cases_total']} cases in the Verus subset, "
            f"{diff['disagreements']} disagreements, {diff['observed_runs']} observations, "
            f"{diff['observed_outside_verus']} outside the Verus model's permitted set",
            [f"agreement={diff['agreement']}"])
        reg(ids[2], "check", "pass" if not diff["gating_alive"] else "incomplete", str(dl),
            "python experiment/playbook-completion/proofs-env/tools/run_proofs.py (differential, mutants)",
            f"Verus-model mutants killed by observations: {diff['gating_killed']}/{diff['gating_mutants']}; alive "
            f"{', '.join(diff['gating_alive']) or 'none'}; probe freedom-waits-only alive as expected="
            f"{not (diff['probe_mutants'].get('freedom-waits-only (sharpening; expected alive)') or {}).get('killed_in')}",
            [f"gating_killed={diff['gating_killed']}", f"gating_total={diff['gating_mutants']}"])
        for feat, r in results.items():
            cl = rd / r["log"].replace("$RUN_DIR/", "")
            reg(rid(feat), "control", "expected-violation" if r["killed"] else "fail", str(cl), r["command"],
                f"{feat} (clause {r['clause']}, mutant {r['mutant']}): {r.get('errors')} errors exactly at "
                f"{r['error_locations']}; failing {r.get('failing_functions')}; every other function verifies as in the "
                f"baseline={r['others_verify_as_baseline']}; counterexample {r['counterexample']} verified="
                f"{r['counterexample_verified']}",
                [f"verified={r.get('verified')}", f"errors={r.get('errors')}",
                 f"error_locations={','.join(r['error_locations'])}", f"json_log={r['json']}",
                 f"json_sha256={r['json_sha256']}"])
    return 0 if proofs_ok and (a.only or a.baseline_only or a.no_differential or diff_ok) else 1


def differential_only(a) -> int:
    if os.environ.get("IVG_COMPLETION_DIR"):
        raise SystemExit("development copies cannot register")
    ids = [f"{a.id_prefix}-differential{a.id_suffix}", f"{a.id_prefix}-mutants{a.id_suffix}"]
    if a.register:
        taken = [i for i in ids if (RUNS / f"{i}.json").exists()]
        if taken:
            raise SystemExit(f"registry ids already recorded: {taken}")
    sha = sources_sha256()
    diff = differential()
    print(f"differential: agreement {diff['agreement']}; in subset {diff['cases_in_subset']}/{diff['cases_total']}; "
          f"observed {diff['observed_runs']}, outside {diff['observed_outside_verus']}; mutants killed "
          f"{diff['gating_killed']}/{diff['gating_mutants']} alive {diff['gating_alive']}")
    results_path = (Path(os.environ["PROOFS_OUT_DIR"]) / "RESULTS.json" if os.environ.get("PROOFS_OUT_DIR")
                    else PROOFS / "RESULTS.json")
    res = json.loads(results_path.read_text()) if results_path.exists() else {}
    if res.get("sources_sha256") and res["sources_sha256"] != sha:
        raise SystemExit("sources changed since RESULTS.json's proof run: rerun the whole gate")
    prev = res.get("differential")
    res.setdefault("differential_history", []).append(
        {"run_dir": res.get("run_dir"), "agreement": prev and prev["agreement"],
         "gating_killed": prev and prev["gating_killed"], "gating_alive": prev and prev["gating_alive"],
         "rounds": prev and sorted(prev["rounds"])})
    res["differential"] = diff
    res["differential_run_dir"] = rel(run_dir())
    res["differential_generated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    res["gate_differential"] = "pass" if diff["agreement"] else "fail"
    res["gate_mutants"] = "pass" if not diff["gating_alive"] else "incomplete"
    results_path.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    if a.register:
        dl = Path(os.environ["RUN_DIR"]) / diff["log"].replace("$RUN_DIR/", "")
        n = len([r for r in diff["rounds"].values() if not r.get("missing")])
        def reg(i, res_, observes, extra):
            subprocess.run([sys.executable, str(REGISTER), i, "check", res_, str(dl), "--lane", LANE, "--command",
                            "python experiment/playbook-completion/proofs-env/tools/run_proofs.py --differential-only",
                            "--observes", observes, "--extra"] + extra + [f"sources_sha256={sha}"], cwd=REPO, check=True)
        reg(ids[0], "pass" if diff["agreement"] else "fail",
            f"verified exec model vs iris-contract/contract-2 permitted sets on {n} recorded rounds incl. "
            f"{', '.join(k for k in ('estop-gap', 'dml-single') if k in diff['rounds'])} "
            f"(no IRIS): {diff['cases_in_subset']} of {diff['cases_total']} cases in the Verus subset, "
            f"{diff['disagreements']} disagreements, {diff['observed_runs']} observations, "
            f"{diff['observed_outside_verus']} outside the Verus model's permitted set",
            [f"agreement={diff['agreement']}"])
        reg(ids[1], "pass" if not diff["gating_alive"] else "incomplete",
            f"Verus-model mutants killed by observations ({n} rounds): {diff['gating_killed']}/"
            f"{diff['gating_mutants']}; alive {', '.join(diff['gating_alive']) or 'none'}; killed in: "
            f"stop-rolls-back-top-level-only {(diff['mutants'].get('stop-rolls-back-top-level-only') or {}).get('killed_in')}, "
            f"failed-dml-opens-nothing {(diff['mutants'].get('failed-dml-opens-nothing') or {}).get('killed_in')}, "
            f"empty-dml-opens-txn {(diff['mutants'].get('empty-dml-opens-txn') or {}).get('killed_in')}",
            [f"gating_killed={diff['gating_killed']}", f"gating_total={diff['gating_mutants']}"])
    return 0 if diff["agreement"] else 1


if __name__ == "__main__":
    sys.exit(main())
