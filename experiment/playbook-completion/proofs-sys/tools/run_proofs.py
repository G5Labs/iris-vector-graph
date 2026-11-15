#!/usr/bin/env python3
"""Proof gate of the PROOFS-SYS lane (experiment/playbook-completion/proofs-sys, steer 13: proof debt D-14's remaining
part, the module-00 axioms over the composed mechanisms). A copy of proofs-mech/tools/run_proofs.py with the crate,
lane and the discharge-function naming (discharge_ax06 for AX-06) changed; everything else is the same gate.

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-sys/tools/run_proofs.py                 # trust scan, baseline, every control
    python experiment/playbook-completion/proofs-sys/tools/run_proofs.py --register      # ... and register the decisive runs
    python .../run_proofs.py --only ledger_bypass_unchecked_as_built,...                  # a subset of controls (never registered)
    PROOFS_OUT_DIR=$RUN_DIR/proofs-sys-recheck python .../run_proofs.py                  # a recheck: logs and RESULTS.json there

Pattern of proofs-d9b/tools/run_proofs.py, adapted to mechanism instances:
1. Trust inventory: the crate's sources may contain no assume, admit, external_body/external, axiom, uninterpreted
   function or assume_specification. The actors dependency (verified in the same build without --no-cheating, which is
   forwarded to this crate only) is scanned for the same items. vstd is Verus's trusted base, listed, not scanned.
2. Feature hygiene: every `#[cfg(feature = ...)]` of the crate is in a src/ctl_*.rs file, introduces exactly one
   `impl <Mech>Object for <Variant>` block, carries a `// CONTROL` metadata line and at least one `// LOCATE <feature>
   <law>` line, and Cargo.toml declares exactly these features. So a control changes nothing but its own block.
3. Baseline: `cargo verus verify -- --no-cheating` must report 0 errors and every function must verify; the
   refutations (refute_*) and counterexamples (cx_*) named by the controls are among the verified functions.
4. Each control (one feature: one departing variant's attempt to discharge the trait) must fail with every error
   located exactly at its LOCATE lines (file and line, one per broken law), its failing functions must be exactly its
   own discharge_<axiom> functions of those axioms, every other function must verify and the set of other functions must
   equal the baseline's, and its refutations and counterexamples must verify in the same build. The broken laws
   (LOCATE lines) must equal the laws the semantics lane's explorer check reports violated (`violates=` in the
   CONTROL line, copied from models/semantics/RESULTS.json).

Every Verus run is `bash experiment/playbook-completion/tools/locks.sh heavy timeout 3600 cargo verus verify ...` after
`cargo clean -p ivg-proofs-sys` (a cached build replays old diagnostics without verifying). A timeout, a resource
limit or a missing result is a failure, never a pass. Each invocation writes its logs into a NEW directory
<out>/run-<UTC stamp>/ (out = $PROOFS_OUT_DIR or $RUN_DIR/proofs-sys); each text log ends with a line
`RUNNER SUMMARY (<json>, sha256 <sha of the JSON log>): verification results:: <n> verified, <m> errors ...` (as
proofs-d9c's runner). With --register, an id that already
has a record in evidence/runs/ is refused (use --id-suffix for a rerun).
RESULTS.json: $PROOFS_OUT_DIR/RESULTS.json when set, else experiment/playbook-completion/proofs-sys/RESULTS.json.
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
# development copies of the crate (outside the worktree) name the worktree's completion directory and their own target
COMPLETION = Path(os.environ.get("IVG_COMPLETION_DIR") or PROOFS.parent)
REPO = COMPLETION.parent.parent
LOCKS = COMPLETION / "tools" / "locks.sh"
REGISTER = COMPLETION / "tools" / "register_run.py"
RUNS = COMPLETION / "evidence" / "runs"
CRATE = "ivg-proofs-sys"
MOD = "ivg_proofs_sys::"
LANE = "proofs-sys"
ACTORS_REV = "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877"

FORBIDDEN = [r"\bassume\s*\(", r"\badmit\s*\(", r"external_body", r"#\s*\[\s*verifier::external", r"\buninterp\b",
             r"\baxiom\b", r"assume_specification", r"#\s*\[\s*verifier::assume"]
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MECH_OF_FILE = {}  # module stem -> mechanism id, filled from file names (mNN_, iNN_, cxNN_)


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
    return dict(os.environ, CARGO_TARGET_DIR=os.environ.get("PROOFS_MECH_TARGET") or str(Path(os.environ["RUN_DIR"]) / "target" / LANE))


def sources() -> list[Path]:
    # this crate's sources and its proofs-mech dependency's (a path dependency built in the same run)
    mech = PROOFS.parent / "proofs-mech"
    return (sorted((PROOFS / "src").glob("*.rs")) + [PROOFS / "Cargo.toml", PROOFS / "Cargo.lock"]
            + sorted((mech / "src").glob("*.rs")) + [mech / "Cargo.toml"])


def sources_sha256() -> str:
    h = hashlib.sha256()
    for p in sources():
        h.update(str(p.relative_to(PROOFS.parent)).encode() + b"\0" + p.read_bytes() + b"\0")
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
    # the proofs-mech dependency is verified in the same build without --no-cheating: scan it as well
    mech_dir = PROOFS.parent / "proofs-mech"
    own += [f"proofs-mech/{v}" for v in scan(sorted((mech_dir / "src").glob("*.rs")), mech_dir)]
    a = actors_src()
    actors = scan(sorted(a.glob("*.rs")), a) if a else ["actors checkout not found"]
    return {
        "own_sources": {"scanned": [str(p.relative_to(PROOFS)) for p in sorted((PROOFS / "src").glob("*.rs"))]
                        + [f"../proofs-mech/src/{p.name}" for p in sorted((PROOFS.parent / "proofs-mech" / "src").glob("*.rs"))],
                        "patterns": FORBIDDEN, "violations": own},
        "actors": {"rev": ACTORS_REV, "path": str(a) if a else None, "violations": actors,
                   "note": "verified in the same build without --no-cheating (forwarded to roots only)"},
        "vstd": {"version": "0.0.0-2026-09-20-0158",
                 "note": "Verus standard library: the trusted base (its axioms and admits are Verus's own); not scanned"},
        "trusted_items_in_this_crate": [],
        "premises": "named in PROOFS.md (the `| Id | Premise |` table); none is an assumption inside a proof",
    }


# ------------------------------------------------------------------------------------------------ control metadata

CONTROL_RE = re.compile(r"^\s*// CONTROL (\S+)\s+(.*)$")
LOCATE_RE = re.compile(r"// LOCATE (\S+) (\S+)")
CFG_RE = re.compile(r'#\[cfg\(feature\s*=\s*"([^"]+)"\)\]')


def parse_controls() -> tuple[dict, list[str]]:
    """Controls from src/ctl_*.rs: metadata, LOCATE lines; plus hygiene problems."""
    controls, problems = {}, []
    for p in sorted((PROOFS / "src").glob("*.rs")):
        text = p.read_text()
        lines = text.splitlines()
        relp = f"src/{p.name}"
        cfgs = [(i + 1, m.group(1)) for i, l in enumerate(lines) for m in [CFG_RE.search(l)] if m]
        if not p.name.startswith("ctl_"):
            for ln, f in cfgs:
                problems.append(f"{relp}:{ln}: feature {f} outside a ctl_ file")
            continue
        meta = {}
        for i, l in enumerate(lines):
            m = CONTROL_RE.match(l)
            if m:
                kv = dict(x.split("=", 1) for x in m.group(2).split())
                meta[m.group(1)] = {"line": i + 1, **kv}
        for ln, f in cfgs:
            if f in controls:
                problems.append(f"{relp}:{ln}: feature {f} used twice")
                continue
            nxt = lines[ln] if ln < len(lines) else ""
            im = re.match(r"\s*impl\s+(\w+)\s+for\s+(\w+)", nxt)
            if not im:
                problems.append(f"{relp}:{ln}: feature {f} does not introduce an impl block")
                continue
            if f not in meta:
                problems.append(f"{relp}:{ln}: feature {f} has no CONTROL line")
                continue
            # the impl block extends to the next cfg line or the end of the verus! block
            end = next((l2 for l2, _ in cfgs if l2 > ln), len(lines) + 1)
            loc = []
            for j in range(ln, end - 1):
                m = LOCATE_RE.search(lines[j])
                if m:
                    if m.group(1) != f:
                        problems.append(f"{relp}:{j + 1}: LOCATE for {m.group(1)} inside block of {f}")
                    loc.append({"law": m.group(2), "at": f"{relp}:{j + 1}"})
            if not loc:
                problems.append(f"{relp}:{ln}: feature {f} has no LOCATE line")
            md = meta[f]
            controls[f] = {
                "file": relp, "trait": im.group(1), "variant": im.group(2), "cfg_line": ln,
                "check": md.get("check"), "kind": md.get("kind"), "mechanism": md.get("mech"),
                "objects": [x for x in md.get("objects", "").split(",") if x],
                "findings": [x for x in md.get("findings", "").split(",") if x],
                "explorer_violates": sorted(x for x in md.get("violates", "").split(",") if x),
                "refutations": [x for x in md.get("refute", "").split(",") if x],
                "counterexamples": [x for x in md.get("cx", "").split(",") if x],
                "locate": loc,
                "broken_laws": sorted({x["law"] for x in loc}),
            }
            if controls[f]["broken_laws"] != controls[f]["explorer_violates"]:
                problems.append(f"{relp}:{ln}: {f}: located laws {controls[f]['broken_laws']} differ from the "
                                f"explorer's violated laws {controls[f]['explorer_violates']}")
    cargo = (PROOFS / "Cargo.toml").read_text()
    block = cargo.split("#@CONTROLS-BEGIN", 1)[1].split("#@CONTROLS-END", 1)[0]
    declared = set(re.findall(r"^(\w+)\s*=\s*\[\]", block, re.M))
    if declared != set(controls):
        problems.append(f"Cargo.toml features differ from the controls: only declared {sorted(declared - set(controls))}, "
                        f"only in sources {sorted(set(controls) - declared)}")
    return controls, problems


def sync_cargo_features() -> None:
    controls, _ = parse_controls()
    cargo = (PROOFS / "Cargo.toml").read_text()
    head, rest = cargo.split("#@CONTROLS-BEGIN", 1)
    _, tail = rest.split("#@CONTROLS-END", 1)
    body = "".join(f"{f} = []   # {c['file']} {c['variant']} ({c['check']}; {','.join(c['broken_laws'])})\n"
                   for f, c in sorted(controls.items(), key=lambda kv: (kv[1]['file'], kv[1]['cfg_line'])))
    (PROOFS / "Cargo.toml").write_text(head + "#@CONTROLS-BEGIN\n" + body + "#@CONTROLS-END" + tail)


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
    raw = js.read_bytes()
    out["json_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        rawt = raw.decode(errors="replace")
        # a fresh target directory first verifies vstd/actors, which print their result lines before the JSON
        dj = json.loads(rawt[rawt.index("{"):])
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
                   success=False, failing_functions=[], all_functions=[])
    # as proofs-d9c's runner (review-4 R4-14): the decisive text log carries its own counts and the JSON log's SHA-256
    with open(log, "a") as fe:
        fe.write(f"RUNNER SUMMARY ({js.name}, sha256 {out['json_sha256']}): verification results:: "
                 f"{out.get('verified')} verified, {out.get('errors')} errors (failing functions); rc {rc}; "
                 f"features {features or '-'}; failing functions {out.get('failing_functions')}; "
                 f"error locations {out['error_locations']}\n")
    return out


def mech_costs(base: dict) -> dict:
    """Baseline SMT time and rlimit per mechanism (modules mNN_*, iNN_*, cxNN_*, ctl_*)."""
    per = {}
    for mod, v in base.get("modules", {}).items():
        name = mod.replace(MOD, "").split("::")[0]
        m = re.match(r"(?:m|i|cx)(\d\d)_", name)
        key = f"M-{m.group(1)}" if m else name
        e = per.setdefault(key, {"ms": 0, "rlimit": 0, "modules": [], "functions": 0})
        e["ms"] += v["ms"]
        e["rlimit"] += v["rlimit"]
        e["modules"].append(name)
    for f in base.get("all_functions", []):
        name = f["function"].split("::")[0]
        m = re.match(r"(?:m|i|cx)(\d\d)_", name)
        key = f"M-{m.group(1)}" if m else name
        if key in per:
            per[key]["functions"] += 1
    return dict(sorted(per.items()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--register", action="store_true", help="register the decisive runs (tools/register_run.py)")
    ap.add_argument("--id-suffix", default="", help="suffix for registry ids of a rerun (e.g. -r2)")
    ap.add_argument("--id-prefix", default=LANE, help="prefix for registry ids")
    ap.add_argument("--lane", default=LANE, help="lane recorded in the registry")
    ap.add_argument("--only", default="", help="comma-separated controls to run (development; refuses --register)")
    ap.add_argument("--sync-features", action="store_true", help="rewrite Cargo.toml's control features and exit")
    a = ap.parse_args()
    if a.sync_features:
        sync_cargo_features()
        return 0
    if (a.only or os.environ.get("IVG_COMPLETION_DIR") or os.environ.get("PROOFS_MECH_TARGET")) and a.register:
        raise SystemExit("--only and development copies cannot register")

    controls, problems = parse_controls()
    for p in problems:
        print("HYGIENE:", p)
    selected = [f for f in controls if not a.only or f in a.only.split(",")]

    def rid_of(feat: str) -> str:
        return f"{a.id_prefix}-{feat.replace('_', '-')}{a.id_suffix}"

    ids = [f"{a.id_prefix}-baseline{a.id_suffix}"] + [rid_of(f) for f in selected]
    if a.register:
        taken = [i for i in ids if (RUNS / f"{i}.json").exists()]
        if taken:
            raise SystemExit(f"registry ids already recorded (a rerun needs --id-suffix): {taken}")

    trust = trust_inventory()
    for v in trust["own_sources"]["violations"] + trust["actors"]["violations"]:
        print("TRUST:", v)
    sha = sources_sha256()
    base = verify("baseline")
    base_fns = {f["function"] for f in base.get("all_functions", [])}
    base_ok_fns = {f["function"] for f in base.get("all_functions", []) if f["success"]}
    named = sorted({x for c in controls.values() for x in c["refutations"] + c["counterexamples"]})
    base["named_lemmas_missing"] = [x for x in named if x not in base_ok_fns]
    base["pass"] = base["rc"] == 0 and base.get("errors") == 0 and bool(base.get("verified")) \
        and not base["timed_out"] and base_fns == base_ok_fns and not base["named_lemmas_missing"]
    print(f"baseline: {base.get('verified')} verified, {base.get('errors')} errors, rc {base['rc']}, "
          f"verus {base.get('verus_total_ms')} ms, rlimit {base.get('rlimit_total')}, wall {base.get('wall_seconds')} s"
          + (f"; MISSING named lemmas {base['named_lemmas_missing']}" if base["named_lemmas_missing"] else ""))

    results = {}
    if not a.baseline_only:
        for feat in selected:
            c = controls[feat]
            r = verify(feat, feat)
            r.update({k: v for k, v in c.items() if k not in ("cfg_line",)})
            expected_locs = sorted({x["at"] for x in c["locate"]},
                                   key=lambda s: (s.split(":")[0], int(s.split(":")[1])))
            r["expected_locations"] = expected_locs
            own = [f for f in (x["function"] for x in r.get("all_functions", []))
                   if f.split("::")[-1].startswith("discharge_") and c["variant"] in f.split("::")]
            suffix = {x["law"]: "discharge_" + x["law"].lower().replace("-", "") for x in c["locate"]}
            expected_fail = sorted({f for f in own if any(f.endswith("::" + n) for n in suffix.values())})
            r["own_functions"] = sorted(own)
            r["expected_failing_functions"] = expected_fail
            ok_fns = {f["function"] for f in r.get("all_functions", []) if f["success"]}
            others = {f["function"] for f in r.get("all_functions", []) if f["function"] not in own}
            others_ok = others & ok_fns
            r["others_verify_as_baseline"] = others == others_ok and others == base_fns
            r["refutations_verified"] = all(x in ok_fns for x in c["refutations"]) and bool(c["refutations"])
            r["counterexamples_verified"] = all(x in ok_fns for x in c["counterexamples"]) and bool(c["counterexamples"])
            r["located"] = r["error_locations"] == expected_locs
            r["killed"] = (not r["timed_out"]) and r.get("errors") == len(expected_locs) and r["located"] \
                and r.get("failing_functions") == expected_fail and bool(expected_fail) \
                and r["others_verify_as_baseline"] and r["refutations_verified"] and r["counterexamples_verified"]
            r.pop("all_functions", None)
            results[feat] = r
            print(f"{feat}: {'REJECTED AT ITS OBLIGATION' if r['killed'] else 'NOT AS EXPECTED'} "
                  f"({r.get('errors')} errors at {r['error_locations']}, expected {expected_locs}; failing "
                  f"{r.get('failing_functions')}; others as baseline {r['others_verify_as_baseline']}; refutations "
                  f"{r['refutations_verified']}; counterexamples {r['counterexamples_verified']})")

    trust_ok = not trust["own_sources"]["violations"] and not trust["actors"]["violations"]
    complete = not a.only and not a.baseline_only
    gate_ok = trust_ok and not problems and base["pass"] and (a.baseline_only or all(r["killed"] for r in results.values()))
    verus_v = subprocess.run(["verus", "--version"], capture_output=True, text=True).stdout.split()
    costs = mech_costs(base)
    base_slim = {k: v for k, v in base.items() if k != "all_functions"}
    base_slim["functions"] = sorted(base_fns)
    result = {
        "crate": f"experiment/playbook-completion/proofs-sys ({CRATE})",
        "debt": "D-14 remainder (experiment/playbook-completion/PROOF-DEBT.md): the module-00 axioms over the composed mechanisms",
        "scope": "statements about the semantics lane's composed module-00 model (sys00) only; no proof connects the product at "
                 "pin 3eaa79cf to it; the pin's as-built composition stays failed (a located control)",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "run_dir": rel(run_dir()),
        "verus": next((v for v in verus_v if v[:1].isdigit()), None),
        "actors_rev": ACTORS_REV,
        "sources_sha256": sha,
        "complete_run": complete,
        "hygiene_problems": problems,
        "baseline": base_slim,
        "cost_per_mechanism": costs,
        "controls": results,
        "trust_inventory": trust,
        "gate": "pass" if gate_ok and (complete or a.baseline_only) else ("partial-pass" if gate_ok else "fail"),
    }
    results_path = Path(os.environ["PROOFS_OUT_DIR"]) / "RESULTS.json" if os.environ.get("PROOFS_OUT_DIR") else PROOFS / "RESULTS.json"
    if a.only:
        results_path = run_dir() / "RESULTS-partial.json"
    results_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    summary = (f"proofs-sys gate: {result['gate'].upper()} ({results_path}, sources {sha[:12]}): baseline "
               f"{base.get('verified')} verified, {base.get('errors')} errors; controls rejected at their obligation "
               f"{sum(r['killed'] for r in results.values())}/{len(results)}; trust {'empty' if trust_ok else 'NOT empty'}")
    print(summary)
    (run_dir() / "runner-summary.txt").write_text(summary + "\n")

    if a.register:
        def reg(rid, kind, res, r, observes):
            subprocess.run([sys.executable, str(REGISTER), rid, kind, res, str(run_dir() / Path(r["log"]).name),
                            "--lane", a.lane, "--command", r["command"], "--observes", observes,
                            "--extra", f"verified={r.get('verified')}", f"errors={r.get('errors')}",
                            f"error_locations={','.join(r['error_locations'])}", f"sources_sha256={sha}",
                            f"json_log={r['json']}", f"json_sha256={r['json_sha256']}",
                            f"verus_total_ms={r.get('verus_total_ms')}", f"rlimit_total={r.get('rlimit_total')}"],
                           cwd=REPO, check=True)
        reg(ids[0], "proof", "pass" if base["pass"] and trust_ok and not problems else "fail", base,
            f"ivg-proofs-sys baseline with --no-cheating: {base.get('verified')} verified, {base.get('errors')} errors; "
            f"trust inventory {'empty' if trust_ok else 'NOT empty'}; {len(named)} named refutations and counterexamples "
            f"verified; the module-00 axioms proved once over the composed design trait (models only)")
        for feat, r in results.items():
            reg(rid_of(feat), "control", "expected-violation" if r["killed"] else "fail", r,
                f"{feat} ({r['mechanism']} {r['variant']}, explorer check {r['check']}, {r['kind']}; findings "
                f"{','.join(r['findings']) or 'none'}): {r.get('errors')} errors, exactly at {r['error_locations']} "
                f"(laws {','.join(r['broken_laws'])}, the explorer's violated laws); failing {r.get('failing_functions')}; "
                f"every other function verifies as in the baseline={r['others_verify_as_baseline']}; refutations "
                f"{','.join(r['refutations'])} and counterexamples {','.join(r['counterexamples'])} verified="
                f"{r['refutations_verified'] and r['counterexamples_verified']}")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
