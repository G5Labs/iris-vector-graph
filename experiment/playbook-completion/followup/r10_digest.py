#!/usr/bin/env python3
"""R-10: the redaction revision's target_sha256 confirms a guessed tenant.

    python experiment/playbook-completion/followup/r10_digest.py

No IRIS connection. Reads the digest the live probe r01a read back from the pin's own redaction revision
($RUN_DIR/followup/r01a.json: history() source.target_sha256 and the SQL row of Graph_KG.ledger_revisions), then
recomputes LedgerRedact.TargetDigest (LedgerRedact.cls:56-60: Sha256Hex(name _ $Char(0) _ match), match = prefix _
separator, :44-49) for a dictionary of candidate tenant names and measures the guessing rate on this host.
Writes $RUN_DIR/followup/r10.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

OUT = Path(os.environ["RUN_DIR"]) / "followup"


def target_digest(graph: str, prefix: str = "", separator: str = "|") -> str:
    match = "" if not prefix else (prefix if prefix.endswith(separator) else prefix + separator)
    return hashlib.sha256((graph + "\x00" + match).encode("utf-8")).hexdigest()


def main() -> int:
    live = json.loads((OUT / "r01a.json").read_text())["r10"]
    stored = live["stored_digest_history"]
    sql_source = json.loads(live["stored_source_sql"][0][0])["target_sha256"]
    # a dictionary an observer could use: 200,000 generated names plus a few real-looking tenant names
    names = [f"tenant{i}" for i in range(200_000)] + ["acme", "globex", "initech", "umbrella", "fu2", "fu1"]
    t0 = time.perf_counter()
    hits_prefix = [n for n in names if target_digest("", n) == stored]
    dt = time.perf_counter() - t0
    hits_graph = [n for n in names[-6:] if target_digest(n) == stored]
    res = {
        "stored_digest_from_history": stored, "stored_digest_from_sql_source": sql_source,
        "objectscript_TargetDigest('', 'fu1|')": live["objectscript_TargetDigest_fu1"],
        "candidates": len(names), "seconds": round(dt, 3), "guesses_per_second_one_core_python": int(len(names) / dt),
        "confirmed_as_prefix_target_in_default_graph": hits_prefix, "confirmed_as_graph_target": hits_graph,
        "examples": {"graph 'tenant-acme', no prefix": target_digest("tenant-acme"),
                     "default graph, prefix 'acme'": target_digest("", "acme")},
        "verdict": {"python_equals_objectscript": target_digest("", "fu1") == live["objectscript_TargetDigest_fu1"],
                    "guessed_tenant_confirmed": hits_prefix == ["fu1"], "stored_equals_sql": stored == sql_source},
    }
    (OUT / "r10.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
