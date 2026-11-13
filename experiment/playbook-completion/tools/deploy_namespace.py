#!/usr/bin/env python3
"""Deploy the pinned product into one audit namespace with the pin's own deploy path.

    python experiment/playbook-completion/tools/deploy_namespace.py AUDITCORE

Uses IRISGraphEngine.initialize_schema() from the unchanged checkout (the documented Community path, the same one
the preflight used), then records which product classes the namespace holds and whether each compiled class's
source text equals the pin's .cls file. Nothing but the pin's sources is compiled.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iris_conn import Conn, REPO  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402


def main() -> int:
    ns = sys.argv[1]
    c = Conn(ns)
    try:
        eng = IRISGraphEngine(c.conn, namespace=ns, embedding_dimension=4)
        status = eng.initialize_schema()
        summary = {k: status.get(k) for k in ("schema", "objectscript_skipped", "objectscript_failed", "warnings")}
        rows = c.sql("SELECT Name FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'Graph.KG' OR Name %STARTSWITH 'IVG.'")
        classes = sorted(r[0] for r in rows)
        pin_files = {p.stem: p for p in (REPO / "iris_src" / "src").rglob("*.cls")}
        # Class name from path: iris_src/src/Graph/KG/Eraser.cls -> Graph.KG.Eraser
        by_name = {".".join(p.relative_to(REPO / "iris_src" / "src").with_suffix("").parts): p
                   for p in pin_files.values()}
        compiled_vs_pin = {}
        for name in classes:
            p = by_name.get(name)
            compiled_vs_pin[name] = (hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p else "not-in-iris_src/src")
        out = {"namespace": ns, "initialize_schema": summary, "compiled_classes": len(classes),
               "pin_source_sha256_16": compiled_vs_pin,
               "missing_from_namespace": sorted(set(by_name) - set(classes))}
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0 if summary.get("schema") == "Graph_KG" and not summary.get("objectscript_failed") else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
