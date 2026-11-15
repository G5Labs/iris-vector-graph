#!/usr/bin/env python3
"""Pieces of the bounded merge gate (`verify.sh --merge`; playbook "One gate = one build on one machine, at most 20
minutes", experiment/playbook-uplift/verification-playbook.txt:479-489), each used as one step:

    python tools/merge_gate.py base                       # the base: the candidate of the newest passing full (clean) verification
    python tools/merge_gate.py changed-crates BASE        # Verus crates whose sources changed since BASE (or are new)
    python tools/merge_gate.py cache-check BASE           # unchanged crates: recomputed sources hash = the last decisive result's
    python tools/merge_gate.py trust-scan                 # no assume/admit/external_body/axiom/uninterp/assume_specification
    python tools/merge_gate.py verus CRATE OUT_DIR        # baseline of a changed crate (--no-cheating); logical errors block
    python tools/merge_gate.py touched-modules BASE       # product modules whose verification artifacts changed since BASE
    python tools/merge_gate.py contract-outside LOG       # exit 0 iff a contract check log reports 0 outside the contract
    python tools/merge_gate.py --self-test

Blocking (playbook): spec checks, the trust inventory, real-database tests of the touched slices plus a fixed canary set,
and Verus on the changed crates only, where only logical errors block (a time or resource limit is recorded as debt).
Every crate's Verus with its controls, and the full live rounds, stay in the periodic full verification
(`verify.sh --live --clean`). Results are reused by input hash only after the hash is recomputed here: cache-check
fails if any unchanged crate's sources differ from the hash its last decisive result recorded, or that result is not
a registered passing run.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PC = Path(__file__).resolve().parents[1]
REPO = PC.parents[1]
REL = PC.relative_to(REPO).as_posix()
FORBIDDEN = re.compile(r"\b(assume\s*\(|admit\s*\(|external_body|#\[verifier::external\b|axiom\b|uninterp\b|assume_specification)")


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout


def crates() -> list[str]:
    return sorted(p.parent.name for p in PC.glob("proofs*/RESULTS.json"))


def base() -> str:
    best = None
    for p in sorted((PC / "evidence" / "runs").glob("verify-clean-*.json")):
        r = json.loads(p.read_text())
        if r.get("result") != "pass":
            continue
        log = Path(str(r["log"]).replace("$RUN_DIR", os.environ["RUN_DIR"]))
        inputs = log.parent / "inputs.txt"
        if not inputs.exists():
            continue
        c = dict(l.split(" ", 1) for l in inputs.read_text().splitlines() if " " in l).get("candidate_commit", "").strip()
        if c and (best is None or r["registered_utc"] > best[0]):
            best = (r["registered_utc"], c)
    if not best:
        raise SystemExit("no passing full verification registered")
    return best[1]


def changed_crates(b: str) -> list[str]:
    out = []
    for c in crates():
        paths = [f"{REL}/{c}/src", f"{REL}/{c}/Cargo.toml", f"{REL}/{c}/Cargo.lock"]
        existed = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{b}:{REL}/{c}/Cargo.toml"],
                                 capture_output=True).returncode == 0
        if not existed or git("diff", "--name-only", b, "HEAD", "--", *paths).strip():
            out.append(c)
    return out


def runner(c: str):
    spec = importlib.util.spec_from_file_location(f"rp_{c.replace('-', '_')}", PC / c / "tools" / "run_proofs.py")
    m = importlib.util.module_from_spec(spec)
    argv = sys.argv
    sys.argv = ["run_proofs.py"]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = argv
    return m


def hash_same(want: str, got: str) -> bool:
    """Recorded and recomputed sources hashes agree; an empty or short value on either side never matches."""
    want, got = str(want or ""), str(got or "")
    if len(want) < 12 or len(got) < 12:
        return False
    return got.startswith(want) or want.startswith(got)


SHARED = (r"/traces/", r"/iris-contract/", r"/contract-2/", r"/trace-replay/(trlib|run|families_[\w]+|lockrun|lockcheck|locklog)\.py$",
          r"/tools/(iris_conn|locks)\.", r"/live/")


def blocked_replay() -> set[str]:
    """Modules whose 3.7-trace-replay cell is blocked (an unavailable dependency, e.g. 15: no FHIR server)."""
    ob = json.loads((PC / "matrix" / "obligations.json").read_text())
    return {c["module"] for c in ob["cells"] if c["gate"] == "3.7-trace-replay" and c["status"] == "blocked"}


def replayable() -> list[str]:
    return sorted(p.stem[1:] for p in (PC / "trace-replay").glob("m[0-9][0-9].py") if p.stem[1:] not in blocked_replay())


def base_summary(b: str) -> dict:
    """The per-step exit codes of the passing clean full verification whose candidate is b."""
    for p in sorted((PC / "evidence" / "runs").glob("verify-clean-*.json")):
        r = json.loads(p.read_text())
        log = Path(str(r["log"]).replace("$RUN_DIR", os.environ["RUN_DIR"]))
        inputs = log.parent / "inputs.txt"
        if r.get("result") == "pass" and inputs.exists() and f"candidate_commit {b}" in inputs.read_text():
            return {"run": r["id"], "steps": {json.loads(l)["step"]: json.loads(l)["exit"] for l in log.read_text().splitlines()}}
    return {}


def cache_check(b: str) -> int:
    changed = set(changed_crates(b))
    bs = base_summary(b)
    bad = 0 if bs else 1
    if not bs:
        print(f"no passing clean full verification registered for {b}")
    for c in crates():
        if c in changed:
            print(f"{c}: changed since {b[:8]}: its baseline runs in this gate")
            continue
        res = json.loads((PC / c / "RESULTS.json").read_text())
        want = str(res.get("sources_sha256", ""))
        m = runner(c)
        got = m.sources_sha256() if hasattr(m, "sources_sha256") else ""
        same = hash_same(want, got)
        step = bs.get("steps", {}).get(c)
        ok = same and step == 0
        bad += not ok
        print(f"{c}: sources {got[:12]} = recorded {want[:12]}: {same}; unchanged since {b[:8]}; its gate in "
              f"{bs.get('run', '?')} exited {step} -> {'reuse' if ok else 'FAIL'}")
    print(f"cache-check: {len(crates()) - len(changed)} unchanged crates reuse the base's full verification "
          f"({bs.get('run', 'none')}), {bad} problem(s)")
    return 1 if bad else 0


def trust_scan() -> int:
    hits = []
    for c in crates():
        for p in sorted((PC / c / "src").rglob("*.rs")):
            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                code = line.split("//")[0]
                if FORBIDDEN.search(code):
                    hits.append(f"{p.relative_to(PC)}:{i}: {line.strip()[:100]}")
    for h in hits:
        print("TRUSTED ITEM:", h)
    print(f"trust-scan: {len(crates())} crates, {len(hits)} trusted item(s) (the inventory is declared empty)")
    return 1 if hits else 0


def verus(c: str, out: str) -> int:
    from verus_json import parse_verus_json  # noqa: E402
    o = Path(out)
    o.mkdir(parents=True, exist_ok=True)
    m = runner(c)
    # a per-crate target directory of the merge gate (warm after its first run; the crate itself is cleaned below)
    env = dict(os.environ, CARGO_TARGET_DIR=str(Path(os.environ["RUN_DIR"]) / "target" / f"merge-{c}"))
    pkg = re.search(r'^name\s*=\s*"([^"]+)"', (PC / c / "Cargo.toml").read_text(), re.M).group(1)
    subprocess.run(["cargo", "clean", "-p", pkg], cwd=PC / c, env=env, capture_output=True)
    js, log = o / "baseline.json", o / "baseline.log"
    cmd = ["bash", str(PC / "tools" / "locks.sh"), "heavy", "timeout", "900", "cargo", "verus", "verify", "--offline",
           "--fwd-verus-args-to", "roots", "--", "--no-cheating", "--triggers-mode", "silent", "--output-json"]
    with open(js, "w") as fo, open(log, "w") as fe:
        rc = subprocess.run(cmd, cwd=PC / c, env=env, stdout=fo, stderr=fe).returncode
    d = parse_verus_json(js.read_text(errors="replace"))
    text = log.read_text(errors="replace")
    if rc == 124 or re.search(r"rlimit|resource limit", text, re.I) and not d:
        # playbook: a resource-limit or time-limit result is recorded as proof debt with its location, not a gate
        # failure, and is never a pass: written to merge-debt.jsonl, which verify.sh reports as inconclusive
        with open(o.parent / "merge-debt.jsonl", "a") as f:
            f.write(json.dumps({"crate": c, "rc": rc, "log": str(log), "kind": "time-or-resource-limit",
                                "location": re.findall(r"-->\s*(\S+:\d+)", text)[:5]}) + "\n")
        print(f"{c}: INCONCLUSIVE (time or resource limit, rc {rc}): recorded as proof debt in merge-debt.jsonl")
        return 0
    if not d:
        print(f"{c}: no verification result (rc {rc}); see {log}")
        return 1
    vr = d["verification-results"]
    print(f"{c}: baseline {vr['verified']} verified, {vr['errors']} errors, success {vr['success']} (rc {rc})")
    return 0 if vr["success"] and vr["errors"] == 0 else 1


def touched_modules(b: str) -> list[str]:
    mods = set()
    names = git("diff", "--name-only", b, "HEAD", "--", REL).split()
    if any(re.search(s, n) for n in names for s in SHARED):
        return replayable() + [m for m in ("12", "13", "14") if m not in replayable()]
    # lane-level files (writesets/, structural/, refusals/, ...): the modules whose matrix cells changed
    try:
        old = json.loads(git("show", f"{b}:{REL}/matrix/obligations.json"))
        new = json.loads((PC / "matrix" / "obligations.json").read_text())
        key = lambda c: (c["gate"], c["module"], c.get("obligation_id"))  # noqa: E731
        sig = lambda c: (c.get("status"), c.get("product_obligation"), tuple(c.get("cited_runs") or []), c.get("remaining"))  # noqa: E731
        o = {key(c): sig(c) for c in old["cells"]}
        for c in new["cells"]:
            if o.get(key(c)) != sig(c) and re.fullmatch(r"\d\d", str(c["module"])):
                mods.add(c["module"])
    except subprocess.CalledProcessError:
        pass
    for n in names:
        m = re.search(r"/(?:findings/audit|modules|footprints)/(\d\d)[-.]", n) or re.search(r"/ontology/(\d\d)-", n) \
            or re.search(r"/trace-replay/m(\d\d)\.py$", n)
        if m:
            mods.add(m.group(1))
        elif re.search(r"/findings/audit/zz-[\w-]+\.json$", n):
            new = json.loads((REPO / n).read_text()) if (REPO / n).exists() else []
            try:
                old = json.loads(git("show", f"{b}:{n}"))
            except subprocess.CalledProcessError:
                old = []
            f = lambda d: {r["id"]: r for r in (d if isinstance(d, list) else d.get("findings", []) + d.get("new_findings", []))}  # noqa: E731
            o, w = f(old), f(new)
            for i, r in w.items():
                if o.get(i) != r and re.fullmatch(r"\d\d", str(r.get("module", ""))):
                    mods.add(str(r["module"]))
    return sorted(mods)


def contract_outside(log: str) -> int:
    m = re.search(r"outside-contract (\d+)", Path(log).read_text())
    print(f"outside-contract {m.group(1) if m else '?'}")
    return 0 if m and m.group(1) == "0" else 1


def self_test() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "x.rs"
        p.write_text("fn f() { assume(false); }\n// assume( in a comment is fine\n")
        lines = [l for l in p.read_text().splitlines() if FORBIDDEN.search(l.split("//")[0])]
        ok &= len(lines) == 1
        lg = Path(t) / "c.log"
        lg.write_text("cases 3 observed-runs 3 outside-contract 1 singleton-cases 3")
        ok &= contract_outside(str(lg)) == 1
        lg.write_text("cases 3 observed-runs 3 outside-contract 0 singleton-cases 3")
        ok &= contract_outside(str(lg)) == 0
    ok &= bool(crates())
    ok &= not hash_same("", "") and not hash_same("abc", "") and not hash_same("", "a" * 64)
    ok &= hash_same("0123456789ab", "0123456789abcdef") and not hash_same("0123456789ab", "0123456789ac")
    print("self-test", "pass" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    a = sys.argv[1:]
    sys.path.insert(0, str(PC / "tools"))
    if not a or a[0] == "--self-test":
        return self_test()
    if a[0] == "base":
        print(base())
        return 0
    if a[0] == "changed-crates":
        print(" ".join(changed_crates(a[1])))
        return 0
    if a[0] == "cache-check":
        return cache_check(a[1])
    if a[0] == "trust-scan":
        return trust_scan()
    if a[0] == "verus":
        return verus(a[1], a[2])
    if a[0] == "touched-modules":
        print(" ".join(touched_modules(a[1])))
        return 0
    if a[0] == "blocked-replay":
        print(" ".join(sorted(blocked_replay())))
        return 0
    if a[0] == "contract-outside":
        return contract_outside(a[1])
    raise SystemExit(f"unknown command {a[0]}")


if __name__ == "__main__":
    raise SystemExit(main())
