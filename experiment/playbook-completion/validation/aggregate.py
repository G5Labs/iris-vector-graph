#!/usr/bin/env python3
"""Aggregate the chunk runs of one validation run id prefix: counts, duration, log hashes, non-pass node ids.

    python aggregate.py <prefix> [<prefix> ...]      e.g. unit-3  (reads $RUN_DIR/validation/unit-3-c*/)

Prints one JSON object per prefix: summed counts (from each chunk's pytest summary line), summed pytest seconds,
wall seconds, exit codes, each chunk's run.log SHA-256, the failures/errors (node id + first message line), skip
reasons by count, and whether any chunk saw a licence-allocation failure.
"""
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize import counts, final_line, junit  # noqa: E402

V = Path(os.environ["RUN_DIR"]) / "validation"


def runs_of(prefix):
    exact = V / prefix
    chunks = sorted(p for p in V.glob(f"{prefix}-*") if p.is_dir() and re.fullmatch(rf"{re.escape(prefix)}-[cf]\d+", p.name))
    if chunks:
        return chunks
    return [exact] if (exact / "run.log").exists() else []


def aggregate(prefix):
    total = collections.Counter()
    out = {"prefix": prefix, "chunks": [], "failures": [], "errors": [], "skips": collections.Counter(),
           "license_failure": False, "namespaces_unchanged": True, "guard_hits": [], "deploy_delegated": 0}
    for d in runs_of(prefix):
        log_b = (d / "run.log").read_bytes()
        log = log_b.decode(errors="replace")
        c = counts(final_line(log))
        for k, v in c.items():
            total[k] += v
        meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        rc = (d / "exit").read_text().strip() if (d / "exit").exists() else None
        out["chunks"].append({"id": d.name, "exit": rc, "counts": c, "log": str(d / "run.log"),
                              "log_sha256": hashlib.sha256(log_b).hexdigest(), "pytest_seconds": c.get("pytest_seconds")})
        if "Unable to allocate a license" in log:
            out["license_failure"] = True
        if meta and not meta.get("namespaces_unchanged", True):
            out["namespaces_unchanged"] = False
        out["guard_hits"] += meta.get("guard_hits", [])
        out["deploy_delegated"] += len(meta.get("deploy_delegated", []))
        _, cases = junit(d / "junit.xml")
        for kind, node, msg, full in cases:
            if kind == "failure":
                out["failures"].append([node, msg, full])
            elif kind == "error":
                out["errors"].append([node, msg, full])
            else:
                out["skips"][msg] += 1
    out["counts"] = dict(total)
    out["skips"] = dict(out["skips"].most_common())
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(aggregate(p), indent=1))
