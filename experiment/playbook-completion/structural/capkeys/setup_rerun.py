#!/usr/bin/env python3
"""Module 01: the pin's own initialize_schema() re-run over a populated namespace (AUDITD, live).

    locks.sh iris python setup_rerun.py OUT.json

Setup is the deploy path the conventions allow (the pin's own initialize_schema, which compiles only the pin's
classes). Before and after the re-run: content digests (rows of nodes, rdf_edges, rdf_labels, rdf_props), the key
and FK oracles (keys.keys_check, fk.fk_check) and the declared-vs-catalog constraint comparison (keys.c01_catalog).
Oracle: setup over existing content keeps every row, every key and every FK, and the catalog keeps the declared
constraints (3.6-keys, 3.6-fk, 3.6-capacity for module 01: a setup of a namespace holding data).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from keys import c01_catalog, keys_check  # noqa: E402
from fk import fk_check  # noqa: E402


def digest(c):
    out = {}
    for t, cols in (("nodes", "node_id, graph_id"), ("rdf_edges", "s, p, o_id, graph_id, ekey"),
                    ("rdf_labels", "s, label, graph_id"), ("rdf_props", 's, "key", val, graph_id')):
        rows = sorted(tuple("" if v is None else str(v) for v in r) for r in c.sql(f"SELECT {cols} FROM Graph_KG.{t}"))
        out[t] = {"rows": len(rows), "sha": hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]}
    return out


def main() -> int:
    outp = Path(sys.argv[1])
    c = lib.conn()
    res = {}
    try:
        lib.reset(c)
        e = lib.engine(c)
        n = 2000
        e.bulk_create_nodes([{"id": f"su:{i}", "labels": ["A"], "properties": {"k": str(i)}} for i in range(n)])
        e.bulk_create_nodes([{"id": f"su:{i}", "labels": ["B"]} for i in range(200)], graph="sug")
        e.bulk_create_edges([{"source_id": f"su:{i}", "predicate": "R", "target_id": f"su:{(i + 1) % n}"} for i in range(n)])
        e.bulk_create_edges([{"source_id": f"su:{i}", "predicate": "S", "target_id": f"su:{(i * 3) % n}"} for i in range(n)])
        e.bulk_create_edges([{"source_id": f"su:{i}", "predicate": "R", "target_id": f"su:{(i + 1) % 200}"} for i in range(200)], graph="sug")
        c.conn.commit()
        res["before"] = {"digest": digest(c), "keys": keys_check(c)["violations"], "fk": fk_check(c)["violations"],
                         "catalog": c01_catalog(c, e)}
        t0 = time.time()
        st = lib.engine(c).initialize_schema()
        res["initialize_schema_secs"] = round(time.time() - t0, 1)
        res["initialize_schema"] = {k: st.get(k) for k in ("schema", "objectscript_failed", "objectscript_skipped", "warnings", "tables_created")}
        c.conn.commit()
        e2 = lib.engine(c)
        res["after"] = {"digest": digest(c), "keys": keys_check(c)["violations"], "fk": fk_check(c)["violations"],
                        "catalog": c01_catalog(c, e2), "verify_default": e2.verify_graph().get("ok"),
                        "verify_sug": e2.verify_graph(graph="sug").get("ok")}
        b, a = res["before"], res["after"]
        res["holds"] = (b["digest"] == a["digest"] and not a["keys"] and not a["fk"]
                        and a["catalog"]["missing"] == b["catalog"]["missing"] and a["catalog"]["differ"] == b["catalog"]["differ"]
                        and not res["initialize_schema"].get("objectscript_failed"))
    finally:
        lib.reset(c)
        c.close()
    lib.dump(outp, res)
    print(json.dumps(res, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
