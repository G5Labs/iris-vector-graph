#!/usr/bin/env python3
"""Module 08: the documented known issues F-0809, F-0813, F-0822 observed on AUDITB (SQL path).

    python experiment/playbook-completion/live/breadth-b/08_known_issues_live.py

Oracle: openCypher semantics as KNOWN_ISSUES.md states them (the issue text names the expected answer).
Log: $RUN_DIR/breadth-b/live/08-known-issues.json.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c08", HERE / "08_common.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def main():
    R = {}
    with C.session08("08-known-issues", native_cypher=False) as s:
        R["ledger_meta"] = C.ledger_meta(s)
        C.cleanup(s)
        # F-0809: MERGE ... ON CREATE SET / ON MATCH SET value shapes (KNOWN_ISSUES.md:131-142)
        C.run(s, "MERGE (n:B08M {id:'b08_mm'})")
        a = C.run(s, "MERGE (n:B08M {id:'b08_mm'}) ON MATCH SET n.s = size(n.id)")
        sval = C.run(s, "MATCH (n:B08M {id:'b08_mm'}) RETURN n.s AS s")
        b = C.run(s, "MERGE (a:B08M {id:'b08_ma'})-[:B08MR]->(b:B08M {id:'b08_mb'}) ON CREATE SET a.c = a.count + 1")
        cval = C.run(s, "MATCH (a:B08M {id:'b08_ma'}) RETURN a.c AS c")
        c = C.run(s, "MERGE (n:B08M {id:'b08_mv'}) ON MATCH SET n.v = 1 / 0")
        mv = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_mv'")[0][0]
        R["F-0809"] = {
            "on_match_size": {"exc": a.get("exc"), "msg": (a.get("msg") or "")[:200], "s_after": sval.get("rows")},
            "pattern_on_create_arith": {"exc": b.get("exc"), "msg": (b.get("msg") or "")[:200], "c_after": cval.get("rows")},
            "on_match_div0_on_created_node": {"exc": c.get("exc"), "msg": (c.get("msg") or "")[:200], "node_rows": mv},
            "oracle": "openCypher: size(n.id) = 6 stored; a.count + 1 is null on a new node (a.c absent); ON MATCH does not run on "
                      "a node the MERGE creates",
        }
        f = R["F-0809"]
        f["verdict"] = "reproduced" if (f["on_match_size"]["exc"] or f["on_match_div0_on_created_node"]["exc"]
                                          or "ARGUMENT" in str(f["pattern_on_create_arith"]["c_after"])) else "not-reproduced"
        # F-0813: values carry no stored type (KNOWN_ISSUES.md:118-130, 183-240)
        C.run(s, "CREATE (:B08N {id:'b08_n1'})-[:B08NT {w: '10'}]->(:B08N {id:'b08_n2'})")
        C.run(s, "CREATE (:B08N {id:'b08_n3'})-[:B08NT {w: 9}]->(:B08N {id:'b08_n4'})")
        gt = C.run(s, "MATCH (a)-[r:B08NT]->(b) WHERE r.w > 8 RETURN a.id AS id ORDER BY id")
        stored = s.c.sql("SELECT s, qualifiers FROM Graph_KG.rdf_edges WHERE p = 'B08NT' ORDER BY s")
        R["F-0813"] = {"edge_filter_rows": gt.get("rows"), "stored_qualifiers": [list(x) for x in stored],
                       "oracle": "openCypher: '10' > 8 is null (a string is not compared with a number): only b08_n3 matches",
                       "verdict": "reproduced" if ["b08_n1"] in (gt.get("rows") or []) else "not-reproduced"}
        # F-0822: CREATE or MERGE after UNWIND $p AS e WITH e (KNOWN_ISSUES.md:585-596)
        u = C.run(s, "UNWIND $p AS e WITH e CREATE (:B08U {id: e.id})", {"p": [{"id": "b08_u1"}, {"id": "b08_u2"}]})
        u_rows = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'b08_u'")[0][0]
        u2 = C.run(s, "UNWIND $p AS e CREATE (:B08V {id: e.id})", {"p": [{"id": "b08_v1"}, {"id": "b08_v2"}]})
        v_rows = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'b08_v'")[0][0]
        R["F-0822"] = {"with_e": {"exc": u.get("exc"), "msg": (u.get("msg") or "")[:300], "rows": u_rows},
                       "workaround_no_with": {"exc": u2.get("exc"), "rows": v_rows},
                       "oracle": "openCypher: two nodes created in both shapes",
                       "verdict": "reproduced" if u_rows != 2 else "not-reproduced"}
        R["cleanup"] = C.cleanup(s)
        p = C.write_log(s, R, name="08-known-issues")
    print(p)
    for k in ("F-0809", "F-0813", "F-0822"):
        print(k, R[k]["verdict"])


if __name__ == "__main__":
    main()
