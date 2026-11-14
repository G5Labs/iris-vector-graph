#!/usr/bin/env python3
"""Module 08: where does a Cypher relationship property bound to a parameter go? (AUDITD, live)

    locks.sh iris python cy_relprop.py OUT.json

Found by cap_values.py (08-cypher-create-relprop-*): `CREATE (a:L {id: 'x'})-[:R {q: $v}]->(b:L {id: 'y'})` answers
no error and stores no q. Variants separate the cause: literal vs parameter property, literal vs parameter endpoint
ids, endpoints matched first, MERGE, and create_edge with qualifiers as the reference writer. Oracle: rdf_edges
.qualifiers (SQL) and the Cypher read `MATCH ()-[r]->() RETURN r.q` for the edge, compared with the value written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
import lib  # noqa: E402

VARIANTS = [
    ("literal prop, literal ids", "CREATE (a:L {id: 'a1'})-[:R {q: 'val'}]->(b:L {id: 'b1'})", {}, "a1"),
    ("param prop, literal ids", "CREATE (a:L {id: 'a2'})-[:R {q: $v}]->(b:L {id: 'b2'})", {"v": "val"}, "a2"),
    ("param prop, param ids", "CREATE (a:L {id: $s})-[:R {q: $v}]->(b:L {id: $o})", {"s": "a3", "o": "b3", "v": "val"}, "a3"),
    ("param prop, matched endpoints", "MATCH (a {id: 'm1'}), (b {id: 'm2'}) CREATE (a)-[:R {q: $v}]->(b)", {"v": "val"}, "m1"),
    ("param prop, MERGE literal ids", "MERGE (a:L {id: 'a4'})-[:R {q: $v}]->(b:L {id: 'b4'})", {"v": "val"}, "a4"),
    ("param prop, CREATE after MATCH-less WITH", "WITH $v AS v CREATE (a:L {id: 'a5'})-[:R {q: v}]->(b:L {id: 'b5'})", {"v": "val"}, "a5"),
    ("param number prop, literal ids", "CREATE (a:L {id: 'a6'})-[:R {q: $n}]->(b:L {id: 'b6'})", {"n": 7}, "a6"),
]


def main() -> int:
    outp = Path(sys.argv[1])
    c = lib.conn()
    res = []
    try:
        lib.reset(c)
        e = lib.engine(c)
        e.create_node("m1", labels=["L"])
        e.create_node("m2", labels=["L"])
        e.create_node("c1", labels=["L"])
        e.create_node("c2", labels=["L"])
        e.create_edge("c1", "R", "c2", qualifiers={"q": "val"})
        c.conn.commit()
        for label, q, params, src in VARIANTS + [("reference create_edge qualifiers", None, None, "c1")]:
            err = None
            if q:
                r = e.execute_cypher(q, params)
                err = str(r.error)[:300] if r.error else None
                c.conn.commit()
            rows = c.sql("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ?", src)
            sqlq = None
            if rows and rows[0][0] not in (None, ""):
                try:
                    sqlq = json.loads(str(rows[0][0])).get("q")
                except Exception:  # noqa: BLE001
                    sqlq = f"<unparsed {str(rows[0][0])[:60]}>"
            rd = e.execute_cypher("MATCH (a {id: $s})-[r:R]->(b) RETURN r.q AS q", {"s": src})
            cq = None if rd.error or not rd.rows else (rd.rows[0][0] if not isinstance(rd.rows[0], dict) else rd.rows[0].get("q"))
            want = str(params.get("v", params.get("n"))) if params else "val"
            res.append({"variant": label, "query": q, "error": err, "edge_rows": len(rows), "sql_qualifier_q": sqlq,
                        "cypher_r_q": cq, "stored": str(sqlq) == want, "read_back": str(cq) == want})
            print(json.dumps(res[-1]), flush=True)
    finally:
        lib.reset(c)
        c.close()
    lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
