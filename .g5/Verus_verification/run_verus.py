#!/usr/bin/env python3
"""Run the IVG uplift's Verus models and faulty controls, and write receipts.

    python3 .g5/Verus_verification/run_verus.py prove    <model-dir>
    python3 .g5/Verus_verification/run_verus.py controls <model-dir>
    python3 .g5/Verus_verification/run_verus.py fresh    <receipt.json>

A model directory holds `model.json` naming its root file and its controls. `prove` verifies the
root file and expects every obligation to verify. `controls` copies the root file into $RUN_DIR,
applies one textual change per control (it must match exactly once, else the control is ERROR,
never a pass), runs Verus and expects verification to FAIL in the named functions. `fresh` checks
that a receipt's recorded input hashes still match the current files and exits 1 when they do not.

Raw logs go to $RUN_DIR/verus/; receipts (inputs, command, versions, expected and observed verdict,
counts) go to .g5/Verus_verification/results/<model>/<stamp>-<label>/receipt.json. Standard library only.
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RUN_DIR = Path(os.environ.get("RUN_DIR", str(Path.home() / "runs/iris-vector-graph-g5-verus-20261113")))
VERUS = os.environ.get("VERUS_BIN", "")
THREADS = os.environ.get("VERUS_RUN_THREADS", "8")
TIMEOUT = int(os.environ.get("VERUS_RUN_TIMEOUT", "1200"))
RESULT_RE = re.compile(r"verification results:: (\d+) verified, (\d+) errors")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def verus_version() -> str:
    out = subprocess.run([VERUS, "--version"], capture_output=True, text=True).stdout
    m = re.search(r"Version: (\S+)", out)
    return m.group(1) if m else out.strip()


def run_verus(root: Path, log: Path, function: str | None = None) -> dict:
    cmd = [VERUS, str(root), "--crate-type=lib", "--num-threads", THREADS, "--triggers-mode", "silent"]
    if function:
        cmd += ["--verify-root", "--verify-function", function]
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd=str(root.parent))
        text = p.stdout + p.stderr
        code = p.returncode
        timed_out = False
    except subprocess.TimeoutExpired as e:
        text = (e.stdout or "") + (e.stderr or "") if isinstance(e.stdout, str) else ""
        code = None
        timed_out = True
    log.write_text(text)
    m = RESULT_RE.search(text)
    return {
        "command": " ".join(cmd),
        "exit_code": code,
        "timed_out": timed_out,
        "verified": int(m.group(1)) if m else None,
        "errors": int(m.group(2)) if m else None,
        "raw_log": str(log),
        "has_resource_limit": "rlimit" in text.lower() and "exceeded" in text.lower(),
    }


def load_model(model_dir: Path) -> dict:
    spec = json.loads((model_dir / "model.json").read_text())
    spec["dir"] = model_dir
    return spec


def _raw_logs(observed: dict) -> list[str]:
    logs = [observed.get("raw_log")] + [v.get("raw_log") for v in (observed.get("per_function") or {}).values()]
    return [p for p in logs if p]


def write_receipt(model: dict, label: str, body: dict) -> Path:
    # G5 viewer layout: results/<model>/<run>/receipt.json (earlier runs of this uplift are kept under receipts/)
    out = HERE / "results" / model["name"] / f"{stamp()}-{label}" / "receipt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Consolidated uplift (2026-11-14): keep a copy of every raw Verus log beside its receipt, so the verdict can be
    # audited from the repository. The copies are evidence, not receipt inputs; the receipt records their SHA-256.
    copies = {}
    for raw in _raw_logs(body.get("observed") or {}):
        src = Path(raw)
        if src.exists():
            dst = out.parent / "logs" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copies[str(dst.relative_to(REPO))] = sha256(dst)
    if copies:
        body["raw_log_copies"] = copies
    out.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return out


def base_inputs(model: dict) -> dict:
    d = model["dir"]
    files = {str((d / f).resolve().relative_to(REPO)): sha256((d / f).resolve())
             for f in [model["root"], "model.json", *model.get("additional_inputs", [])]}
    return {
        "inputs": files,
        "verus": {"bin": VERUS, "version": verus_version()},
        "product_baseline": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
        "threads": THREADS,
        "timeout_s": TIMEOUT,
    }


def prove(model_dir: Path) -> int:
    model = load_model(model_dir)
    label = "prove"
    log = RUN_DIR / "verus" / model["name"] / f"{stamp()}-{label}.log"
    res = run_verus(model_dir / model["root"], log)
    expected = {"verified": model.get("expected_verified"), "errors": 0}
    if res["timed_out"] or res["verified"] is None:
        verdict = "ERROR" if not res["timed_out"] else "TIMEOUT"
    elif res["errors"] == 0 and (expected["verified"] is None or res["verified"] == expected["verified"]):
        verdict = "PASS"
    else:
        verdict = "UNEXPECTED"
    body = {**base_inputs(model), "kind": "proof", "expected": expected, "observed": res, "verdict": verdict}
    path = write_receipt(model, label, body)
    print(f"{model['name']}: {verdict} ({res['verified']} verified, {res['errors']} errors) -> {path.relative_to(REPO)}")
    return 0 if verdict == "PASS" else 1


def controls(model_dir: Path) -> int:
    model = load_model(model_dir)
    root = model_dir / model["root"]
    src = root.read_text()
    worst = 0
    summary = []
    only = os.environ.get("CONTROL")
    if only and not any(c["name"] == only for c in model.get("controls", [])):
        print(f"ERROR: {model['name']}: no control named {only!r}; no verifier was run")
        return 2
    for c in model.get("controls", []):
        name = c["name"]
        if only and name != only:
            continue
        # Preserve earlier work/control copies; imported model paths need the same relative layout.
        control_root = RUN_DIR / "verus" / model["name"] / "controls" / name / stamp()
        work = control_root / "models" / model["name"]
        work.mkdir(parents=True)
        for dependency in model.get("additional_inputs", []):
            src_dependency = (model_dir / dependency).resolve()
            dst_dependency = (work / dependency).resolve()
            if not dst_dependency.is_relative_to(control_root.resolve()):
                raise ValueError(f"control dependency escapes its preserved control snapshot: {dependency}")
            dst_dependency.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_dependency, dst_dependency)
        n = src.count(c["find"])
        log = RUN_DIR / "verus" / model["name"] / f"{stamp()}-control-{name}.log"
        if n != 1:
            res = {"error": f"patch anchor matched {n} times"}
            verdict = "ERROR"
        else:
            (work / model["root"]).write_text(src.replace(c["find"], c["replace"]))
            res = run_verus(work / model["root"], log)
            # attribute the failure: each named function must fail when verified alone
            per_fn = {}
            for fn in c["expect_fail_in"]:
                flog = log.with_name(log.stem + f"-{fn}.log")
                r = run_verus(work / model["root"], flog, function=fn)
                per_fn[fn] = {"verified": r["verified"], "errors": r["errors"], "raw_log": r["raw_log"], "timed_out": r["timed_out"]}
            res["per_function"] = per_fn
            hit = all((v["errors"] or 0) > 0 for v in per_fn.values())
            if res["timed_out"] or any(v["timed_out"] for v in per_fn.values()):
                verdict = "TIMEOUT"
            elif res["errors"] is None:
                # a build/type failure gives no verdict on the control
                verdict = "ERROR"
            elif res["errors"] > 0 and hit:
                verdict = "EXPECTED_FAIL"
            elif res["errors"] > 0:
                verdict = "FAIL_ELSEWHERE"
            else:
                verdict = "SURVIVED"
        body = {
            **base_inputs(model),
            "kind": "control",
            "control": c,
            "expected": {"verdict": "EXPECTED_FAIL", "fail_in": c["expect_fail_in"]},
            "observed": res,
            "verdict": verdict,
        }
        path = write_receipt(model, f"control-{name}", body)
        summary.append((name, verdict, str(path.relative_to(REPO))))
        if verdict != "EXPECTED_FAIL":
            worst = 1
    for row in summary:
        print("  ".join(row))
    return worst


def fresh(receipt: Path) -> int:
    body = json.loads(receipt.read_text())
    stale = []
    for rel, digest in body["inputs"].items():
        p = REPO / rel
        if not p.exists() or sha256(p) != digest:
            stale.append(rel)
    if stale:
        print(f"STALE: {receipt} no longer applies; changed inputs: {', '.join(stale)}")
        return 1
    print(f"FRESH: {receipt}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("prove", "controls", "fresh"):
        print(__doc__)
        return 2
    if argv[1] != "fresh" and not VERUS:
        print("VERUS_BIN is not set; source experiment/g5-verus/environment.sh")
        return 2
    target = Path(argv[2]).resolve()
    return {"prove": prove, "controls": controls, "fresh": fresh}[argv[1]](target)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
