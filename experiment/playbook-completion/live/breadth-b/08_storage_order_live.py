#!/usr/bin/env python3
"""Gate §3.4 storage-order probes for module-08 sites that take a result prefix without ORDER BY.

    bash experiment/playbook-completion/tools/locks.sh iris python experiment/playbook-completion/live/breadth-b/08_storage_order_live.py

Sites ($RUN_DIR/checks/storage-order.json):
- engine.py:1340 (db.schema.nodeTypeProperties samples `SELECT TOP 1 rl.s ... WHERE rl.label = ?`) and engine.py:1382
  (db.schema.relTypeProperties samples `SELECT TOP 1 qualifiers ... WHERE p = ?`): the reported property names are
  those of whichever row storage order puts first;
- translator.py:11141 / 11175 (`_merge_action_value_sql`: an ON CREATE / ON MATCH SET value read with `SELECT TOP 1`
  from the rows the preceding clauses bound) and translator.py:12386 (`SET r = a` copies `SELECT TOP 1` node's
  properties): with several preceding rows each merged entity should take its own row's value.
Oracle: openCypher (MERGE runs per row; a schema procedure lists every property key the label's / type's elements
hold). Log: $RUN_DIR/breadth-b/live/08-storage-order[$B08_LOG_SUFFIX].json.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c08", HERE / "08_common.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def main():
    R = {}
    with C.session08("08-storage-order", native_cypher=False) as s:
        R["ledger_meta"] = C.ledger_meta(s)
        if R["ledger_meta"].get("strict"):
            R["skipped"] = "ledger strict on"
            print(C.write_log(s, R, name="08-storage-order"))
            return
        C.cleanup(s)
        # 1. schema sampling (insertion order: the node with k2 first, then the node with k1)
        C.run(s, "CREATE (:B08SA {id:'b08_sa2', k2: 1})")
        C.run(s, "CREATE (:B08SA {id:'b08_sa1', k1: 1})")
        C.run(s, "CREATE (:B08SX {id:'b08_sx1'})-[:B08SR {qa: 1}]->(:B08SX {id:'b08_sx2'})")
        C.run(s, "CREATE (:B08SX {id:'b08_sx3'})-[:B08SR {qb: 1}]->(:B08SX {id:'b08_sx4'})")
        nt = C.run(s, "CALL db.schema.nodeTypeProperties()")
        rt = C.run(s, "CALL db.schema.relTypeProperties()")
        sa_props = sorted({r[2] for r in nt["rows"] if r and r[1] == ["B08SA"]})
        sr_props = sorted({r[1] for r in rt["rows"] if r and r[0] == "B08SR"})
        R["schema_sampling"] = {
            "nodeTypeProperties_B08SA": sa_props, "relTypeProperties_B08SR": sr_props,
            "oracle": "every key the label's nodes hold: id, k1, k2; every key the type's edges hold: qa, qb (+ weight)",
            "verdict": "reproduced" if (not {"k1", "k2"} <= set(sa_props) or not {"qa", "qb"} <= set(sr_props)) else "not-reproduced",
        }
        # 2. MERGE action value per row (translator.py:11123-11190)
        C.run(s, "CREATE (:B08PP {id:'b08_p1', city:'ca', pop: 1}), (:B08PP {id:'b08_p2', city:'cb', pop: 2})")
        m = C.run(s, "MATCH (p:B08PP) MERGE (c:B08CT {name: p.city}) ON CREATE SET c.pop = p.pop")
        pops = C.run(s, "MATCH (c:B08CT) RETURN c.name AS n, c.pop AS pop ORDER BY n")
        got = {r[0]: r[1] for r in pops["rows"]}
        R["merge_action_per_row"] = {"exc": m.get("exc"), "msg": (m.get("msg") or "")[:300], "cities": got,
                                     "oracle": "openCypher: city ca gets pop 1, cb gets pop 2",
                                     "verdict": "reproduced" if (not m.get("exc") and got not in ({"ca": 1, "cb": 2},))
                                     else ("refused" if m.get("exc") else "not-reproduced")}
        # 3. SET r = a per row (translator.py:12362-12395)
        C.run(s, "CREATE (:B08TT {id:'b08_tt'})")
        r3 = C.run(s, "MATCH (a:B08PP), (t:B08TT {id:'b08_tt'}) MERGE (a)-[r:B08MR3]->(t) ON CREATE SET r = a")
        quals = s.c.sql("SELECT s, qualifiers FROM Graph_KG.rdf_edges WHERE p = 'B08MR3' ORDER BY s")
        qmap = {}
        for src, q in quals:
            try:
                qmap[src] = json.loads(q) if q else None
            except Exception:  # noqa: BLE001
                qmap[src] = q
        own = all(isinstance(v, dict) and str(v.get("city")) == ("ca" if k == "b08_p1" else "cb") for k, v in qmap.items()) and len(qmap) == 2
        R["set_rel_from_node_per_row"] = {"exc": r3.get("exc"), "msg": (r3.get("msg") or "")[:300], "qualifiers": qmap,
                                          "oracle": "openCypher: each new relationship copies its own row's a (b08_p1 -> city ca, b08_p2 -> city cb)",
                                          "verdict": "refused" if r3.get("exc") else ("not-reproduced" if own else "reproduced")}
        R["cleanup"] = C.cleanup(s)
        p = C.write_log(s, R, name="08-storage-order")
    print(p)
    for k in ("schema_sampling", "merge_action_per_row", "set_rel_from_node_per_row"):
        print(k, json.dumps(R[k], default=str)[:600])
    print("cleanup", R["cleanup"]["left"])


if __name__ == "__main__":
    main()
