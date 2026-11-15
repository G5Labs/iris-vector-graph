"""Shared helper for the consolidated uplift's unit-level binding harnesses (models/<name>/binding.py).

A binding harness runs the product's real Python function from an exported pin tree ($RUN_DIR/pin, never this
working tree), over a finite enumerated input set, and compares each outcome with one derived independently from
the model's specification (a hand transcription of the model's spec functions, named in each harness). It then
requires that the comparison detects (a) a changed deciding field in one observation and (b) a product mutant.
The receipt goes to .g5/Verus_verification/results/<model>/<stamp>-binding/receipt.json with the SHA-256 of the
harness, this helper and the model root, so tools/check_evidence.py can tell when it no longer applies.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V = HERE.parent
REPO = V.parent.parent
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pin_dir() -> Path:
    d = Path(os.environ.get("IVG_PIN_DIR", str(Path(os.environ.get("RUN_DIR", str(Path.home() / "runs/ivg-consolidated-20261114"))) / "pin")))
    if not (d / "iris_vector_graph").is_dir():
        raise SystemExit(f"no exported pin tree at {d}: git -C {REPO} archive {PIN[:8]} | tar -x -C {d}")
    return d


def import_pin():
    """Put the exported pin tree first on sys.path (and nothing from the working tree)."""
    d = pin_dir()
    sys.path.insert(0, str(d))
    for k in [m for m in sys.modules if m.startswith("iris_vector_graph")]:
        del sys.modules[k]
    return d


def pin_identity(d: Path) -> dict:
    """The exported tree must be the pin: compare a few product files' hashes with the pin's blobs."""
    files = ["iris_vector_graph/_engine/temporal_window.py", "iris_vector_graph/freshness.py", "iris_vector_graph/embedded.py",
             "iris_vector_graph/prop_values.py", "iris_vector_graph/schema.py", "iris_vector_graph/_engine/query.py",
             "iris_vector_graph/ledger/replay.py", "iris_vector_graph/ledger/client.py", "iris_vector_graph/engine.py",
             "iris_vector_graph/_engine/nodes_edges.py"]
    out, ok = {}, True
    for f in files:
        blob = subprocess.run(["git", "-C", str(REPO), "rev-parse", f"{PIN}:{f}"], capture_output=True, text=True).stdout.strip()
        have = subprocess.run(["git", "hash-object", str(d / f)], capture_output=True, text=True).stdout.strip()
        out[f] = have == blob
        ok &= have == blob
    return {"pin_dir": str(d), "pin_commit": PIN, "files_equal_pin_blobs": out, "all_equal": ok}


def write_receipt(model: str, harness: Path, body: dict) -> Path:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = V / "results" / model / f"{stamp}-binding" / "receipt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    root = json.loads((V / "models" / model / "model.json").read_text())["root"]
    inputs = {str(p.relative_to(REPO)): sha(p) for p in [harness, Path(__file__).resolve(), V / "models" / model / root]}
    body = {"kind": "binding", "model": model, "inputs": inputs, "python": sys.version.split()[0],
            "platform": platform.platform(), "product_baseline": PIN, **body}
    out.write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    return out
