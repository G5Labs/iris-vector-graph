#!/usr/bin/env python3
"""Re-run one imported playbook-arm Verus crate on this machine from a scratch copy, and write a receipt.

    python3 .g5/Verus_verification/tools/run_playbook_crate.py <crate> [baseline] [<control_feature> ...] [--all-controls]

<crate> is a path under experiment/ (for example `playbook-completion/proofs-d1e` or `playbook-uplift/proofs`), or a bare
crate directory name, read as `playbook-completion/<name>`.

What it does, and nothing else (consolidated uplift, reviewed plan section 3.3):

1. `git archive 2d59e578 experiment/<crate>` (plus any `path =` sibling it depends on) into $RUN_DIR/pb. The imported tree in
   the repository is never touched.
2. Checks that the crate's tree hash at HEAD equals its tree hash at 2d59e578 and that every extracted `.rs` file hashes to
   its git blob at 2d59e578 (the sources are unchanged).
3. Makes exactly two substitutions in each scratch `Cargo.toml` that names them: the `actors` and `verus_builtin_macros`
   git dependencies (file:// paths on the playbook VM) become `path =` dependencies on the local snapshot $ACTORS_DIR
   (identified by the launch request as the VM's `actors` source at c03f9fa; its own SOURCE.json names Bank of Ziniu
   47bbd846 `sql/next`; not hash-compared with the VM checkout). `Cargo.lock` is removed (it pins the VM URLs).
4. Runs `cargo verus verify --offline --fwd-verus-args-to roots [--features F] -- --no-cheating --triggers-mode silent`
   (root-only `--no-cheating`: without the forwarding flag it is applied to vstd and the build fails).
5. Writes `.g5/Verus_verification/results/playbook-<crate>/<stamp>-<label>/receipt.json` with the tree hashes, the two
   substitutions, the command, the counts of every `verification results` line (the last is the root crate), the error
   locations, the result the playbook arm recorded in the crate's RESULTS.json, the comparison, and a copy of the raw log.

Verdicts. baseline: PASS when the root crate has 0 errors and the recorded count; control: EXPECTED_FAIL when the root crate
has errors and every error is located in the file the crate's Cargo.toml names for that feature; FAIL_ELSEWHERE, SURVIVED,
ERROR (no result line: a build failure gives no verdict) and TIMEOUT otherwise. `matches_record` compares counts and the
error locations with the playbook arm's RESULTS.json. Standard library only. Do not use it to run the playbook's own
verify.sh, check-product-scope.sh, register_run.py or run_proofs.py (they need the VM and fail by construction here).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
V = HERE.parent
REPO = V.parent.parent
SOURCE_COMMIT = "2d59e578362cab392b771051f79cd613aae7269c"
RUN_DIR = Path(os.environ.get("RUN_DIR", str(Path.home() / "runs/ivg-consolidated-20261114")))
ACTORS_DIR = Path(os.environ.get("ACTORS_DIR", str(Path.home() / ".cache/g5-verification/ivg-actors-c03f9fa")))
VERUS_DIR = Path(os.environ.get("VERUS_DIR", str(Path.home() / ".cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos")))
TIMEOUT = int(os.environ.get("PLAYBOOK_RUN_TIMEOUT", "3600"))
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")
ACTORS_RE = re.compile(r'actors = \{ git = "file://[^"]*", rev = "([0-9a-f]+)" \}')
MACROS_RE = re.compile(r'verus_builtin_macros = \{ git = "file://[^"]*", rev = "([0-9a-f]+)" \}')


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def crate_rel(arg: str) -> str:
    arg = arg.strip("/")
    if arg.startswith("experiment/"):
        arg = arg[len("experiment/"):]
    if "/" not in arg:
        arg = f"playbook-completion/{arg}"
    return f"experiment/{arg}"


def family_name(rel: str) -> str:
    arm, crate = rel.split("/")[1], rel.split("/")[2]
    return f"playbook-{crate}" if arm == "playbook-completion" else f"playbook-uplift-{crate}"


def siblings(rel: str) -> list[str]:
    toml = git("show", f"{SOURCE_COMMIT}:{rel}/Cargo.toml")
    out = []
    for m in re.finditer(r'\{ *path *= *"(\.\./[^"]+)"', toml):
        out.append(os.path.normpath(f"{rel}/{m.group(1)}"))
    return out


def control_files(rel: str) -> dict[str, str]:
    """feature -> the file its Cargo.toml comment names (`# src/x.rs  ...`)."""
    toml = git("show", f"{SOURCE_COMMIT}:{rel}/Cargo.toml")
    out = {}
    for line in toml.splitlines():
        m = re.match(r'^([A-Za-z0-9_]+) *= *\[\] *# *(src/[A-Za-z0-9_./]+\.rs)', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def recorded(rel: str) -> dict:
    try:
        return json.loads(git("show", f"{SOURCE_COMMIT}:{rel}/RESULTS.json"))
    except subprocess.CalledProcessError:
        return {}


def recorded_for(rec: dict, label: str) -> dict | None:
    if label == "baseline":
        return rec.get("baseline")
    ctr = rec.get("controls") or []
    if isinstance(ctr, dict):
        ctr = list(ctr.values())
    for c in ctr:
        if label in (c.get("tag"), c.get("name"), c.get("features")):
            return c
    return None


def extract(rel_paths: list[str]) -> Path:
    base = RUN_DIR / "pb"
    for rel in rel_paths:
        tgt = base / rel
        if tgt.exists():
            shutil.rmtree(tgt)
    base.mkdir(parents=True, exist_ok=True)
    arc = subprocess.run(["git", "-C", str(REPO), "archive", SOURCE_COMMIT, *rel_paths], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(base)], input=arc, check=True)
    return base


def check_sources(base: Path, rel: str) -> dict:
    tree_src = git("rev-parse", f"{SOURCE_COMMIT}:{rel}")
    tree_head = git("rev-parse", f"HEAD:{rel}")
    listing = git("ls-tree", "-r", SOURCE_COMMIT, rel)
    bad, n = [], 0
    for line in listing.splitlines():
        meta, path = line.split("\t", 1)
        blob = meta.split()[2]
        if not path.endswith(".rs"):
            continue
        n += 1
        h = subprocess.check_output(["git", "hash-object", str(base / path)], text=True).strip()
        if h != blob:
            bad.append(path)
    return {"tree_at_source": tree_src, "tree_at_head": tree_head, "tree_unchanged": tree_src == tree_head,
            "rs_files": n, "rs_files_changed": bad}


def patch_manifest(crate_dir: Path) -> list[dict]:
    p = crate_dir / "Cargo.toml"
    s = p.read_text()
    subs = []
    a = str(ACTORS_DIR)
    for rx, new in ((ACTORS_RE, f'actors = {{ path = "{a}/crates/actors" }}'),
                    (MACROS_RE, f'verus_builtin_macros = {{ path = "{a}/verification-tools/builtin-macros" }}')):
        m = rx.search(s)
        if m:
            subs.append({"file": str(p.relative_to(RUN_DIR / "pb")), "before": m.group(0), "after": new, "vm_rev": m.group(1)})
            s = rx.sub(new, s, count=1)
    p.write_text(s)
    lock = crate_dir / "Cargo.lock"
    if lock.exists():
        lock.unlink()
    return subs


def parse_errors(text: str) -> list[str]:
    locs, in_err = [], False
    for line in text.splitlines():
        if re.match(r"^error(\[[A-Z0-9]+\])?:", line):
            in_err = not line.startswith("error: aborting") and "could not compile" not in line
            continue
        if re.match(r"^(warning|note)(\[[A-Za-z0-9_]+\])?:", line):
            in_err = False
            continue
        m = re.match(r"^\s*--> (\S+?):(\d+):\d+", line)
        if m and in_err:
            loc = f"{m.group(1)}:{m.group(2)}"
            if loc not in locs:
                locs.append(loc)
            in_err = False
    return locs


def run(rel: str, label: str) -> int:
    fam = family_name(rel)
    deps = siblings(rel)
    base = extract([rel, *deps])
    src = check_sources(base, rel)
    subs = []
    for r in [rel, *deps]:
        subs += patch_manifest(base / r)
    crate_dir = base / rel
    feature = None if label == "baseline" else label
    cmd = ["cargo", "verus", "verify", "--offline", "--fwd-verus-args-to", "roots"]
    if feature:
        cmd += ["--features", feature]
    cmd += ["--", "--no-cheating", "--triggers-mode", "silent"]
    env = dict(os.environ)
    env["PATH"] = f"{VERUS_DIR}:{env.get('PATH', '')}"
    env["CARGO_TARGET_DIR"] = str(RUN_DIR / "target" / rel.split("/")[-1])
    # git archive keeps the commit's mtimes, so cargo would take a repeated run with the same features as up to date
    # and verify nothing (no result line: ERROR, never a pass). Clean the root package first, as the arm's runner did.
    pkg = re.search(r'^name *= *"([^"]+)"', (crate_dir / "Cargo.toml").read_text(), re.M)
    if pkg:
        subprocess.run(["cargo", "clean", "--offline", "-p", pkg.group(1)], cwd=str(crate_dir), env=env,
                       capture_output=True, text=True)
    st = stamp()
    log = RUN_DIR / "pb-logs" / fam / f"{st}-{label}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(crate_dir), env=env, capture_output=True, text=True, timeout=TIMEOUT)
        text, code, timed_out = p.stdout + p.stderr, p.returncode, False
    except subprocess.TimeoutExpired as e:
        text = ((e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")) + \
               ((e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or ""))
        code, timed_out = None, True
    wall = round(time.time() - t0, 1)
    log.write_text(text)
    results = [{"verified": int(a), "errors": int(b)} for a, b in RESULT_RE.findall(text)]
    root = results[-1] if results else None
    errs = parse_errors(text)
    named = control_files(rel).get(feature) if feature else None
    rec = recorded_for(recorded(rel), label)
    if feature and not named and rec:
        # a feature whose Cargo.toml comment names no file: fall back to the one file the arm's recorded errors name
        files = {(l if isinstance(l, str) else f"{l.get('file')}:{l.get('line')}").rsplit(":", 1)[0]
                 for l in (rec.get("error_locations") or [])}
        named = files.pop() if len(files) == 1 else None
    if timed_out:
        verdict = "TIMEOUT"
    elif root is None:
        verdict = "ERROR"
    elif feature is None:
        verdict = "PASS" if root["errors"] == 0 else "UNEXPECTED"
    elif root["errors"] == 0:
        verdict = "SURVIVED"
    elif named and errs and all(e.startswith(named + ":") for e in errs):
        verdict = "EXPECTED_FAIL"
    else:
        verdict = "FAIL_ELSEWHERE"
    cmp = None
    if rec is not None and root is not None:
        rec_locs = rec.get("error_locations") or []
        rec_locs = [l if isinstance(l, str) else f"{l.get('file')}:{l.get('line')}" for l in rec_locs]
        cmp = {"recorded_verified": rec.get("verified"), "recorded_errors": rec.get("errors"),
               "recorded_error_locations": rec_locs,
               "counts_match": rec.get("verified") == root["verified"] and rec.get("errors") == root["errors"],
               "locations_match": sorted(rec_locs) == sorted(errs)}
    if verdict == "PASS" and rec is not None and rec.get("verified") != root["verified"]:
        verdict = "UNEXPECTED"
    out = V / "results" / fam / f"{st}-{label}" / "receipt.json"
    (out.parent / "logs").mkdir(parents=True, exist_ok=True)
    log_copy = out.parent / "logs" / log.name
    shutil.copyfile(log, log_copy)
    body = {
        "kind": "playbook-crate-rerun",
        "family": fam,
        "crate": rel,
        "label": label,
        "source_commit": SOURCE_COMMIT,
        "sources": src,
        "substitutions": subs,
        "dependency": {"actors_dir": str(ACTORS_DIR),
                       "identification": "launch request: the playbook VM's actors source at c03f9fa; the snapshot's own "
                                         "SOURCE.json names Bank of Ziniu 47bbd846 (sql/next); not hash-compared with the VM checkout",
                       "siblings_archived": deps},
        "command": " ".join(cmd),
        "cwd": str(crate_dir),
        "cargo_target_dir": env["CARGO_TARGET_DIR"],
        "verus_dir": str(VERUS_DIR),
        "exit_code": code,
        "timed_out": timed_out,
        "wall_seconds": wall,
        "results_lines": results,
        "root": root,
        "error_locations": errs,
        "control_file": named,
        "recorded": cmp,
        "matches_record": bool(cmp and cmp["counts_match"] and cmp["locations_match"]),
        "verdict": verdict,
        "raw_log": str(log),
        "raw_log_copy": {str(log_copy.relative_to(REPO)): sha256_bytes(log_copy.read_bytes())},
        "product_baseline": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
        "statement": "A rerun of the playbook arm's model crate. Its theorems are about the playbook's L1 contracts and "
                     "(mostly reviewed-design) L2 machines, not about the product's executable bodies.",
    }
    out.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    res = f"{root['verified']} verified, {root['errors']} errors" if root else "no result"
    print(f"{fam} {label}: {verdict} ({res}; record match: {body['matches_record']}; {wall}s) -> {out.relative_to(REPO)}")
    good = {"baseline": "PASS"}.get(label, "EXPECTED_FAIL")
    return 0 if verdict == good else 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    rel = crate_rel(argv[1])
    labels = [a for a in argv[2:] if not a.startswith("--")]
    if "--all-controls" in argv:
        labels = ["baseline", *control_files(rel).keys()]
    if not labels:
        labels = ["baseline"]
    worst = 0
    for label in labels:
        worst |= run(rel, label)
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
