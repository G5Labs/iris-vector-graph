"""HD-0903 probe: what does a native read on another connection answer while a writer's transaction is open?

Sources: USER_GUIDE.md:260-262 (pin; 6a3718dd, 2026-11-09): "Another connection sees what your open transaction has
written, uncommitted: IRIS reads uncommitted by default, so a second connection's `MATCH` or `SELECT` finds the node
`create_node` wrote until you roll back"; spec 253 edge case (spec.md:91-92) speaks only of the caller's own
transaction; FR-002 (native answer equals the SQL path's).
Deterministic interleaving (graph ia-0903), connection A = writer (START TRANSACTION on its cursor, engine EA on A, writes
join it), connection B = readers: EBn (native on, compiled plans off) and EBs (native_cypher=False, SQL path).
  A1  create_node a (IaL0903), create_node b (no label), create_edge a-R->b      [open, uncommitted]
  B1  read unlabelled  MATCH (a {node_id})-[:R]->(b) RETURN b      (native and SQL)
  B2  read labelled    MATCH (a {node_id})-[:R]->(b:IaL0903) RETURN b
  A2  SET b:IaL0903 (Cypher in A's transaction)
  B3  labelled read again
  A3  ROLLBACK
  B4  both reads again
Oracle (readings):
  B1 = [b], B2 = [], B3 = [b], B4 = []   -> reads see the open transaction statement by statement, i.e. part of it
                                            (option a: dirty, per-store moment reads; documented for MATCH/SELECT)
  B1 = [] until commit                    -> committed-only reads (would need locks or snapshots: option b)
  native rows == SQL rows at every step   -> the native path has the same isolation as the SQL path (FR-002 holds here)
Contract under test: USER_GUIDE.md:260-262 and FR-002: pass when native and SQL agree at every step and both see the
uncommitted writes; the record notes that a reader sees one transaction in part.
"""
from __future__ import annotations

import _common as C

G = "ia-0903"
U = f"USE GRAPH '{G}' MATCH (a {{node_id: 'ia0903:a'}})-[:R]->(b) RETURN b.node_id AS b"
L = f"USE GRAPH '{G}' MATCH (a {{node_id: 'ia0903:a'}})-[:R]->(b:IaL0903) RETURN b.node_id AS b"


def read(e, q):
    n = e.__dict__.get("_native_answers", 0)
    r = e.execute_cypher(q)
    return {"rows": [list(x) for x in r.rows], "error": getattr(r, "error", None),
            "native": e.__dict__.get("_native_answers", 0) - n}


def main():
    ca, cb = C.conn(), C.conn()
    ea = C.engine(ca)
    ebn = C.engine(cb)
    ebs = C.engine(cb, native_cypher=False)
    steps = {}
    verdict = ("incomplete", "did not finish")
    cur = ca.conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        ea.create_node("ia0903:a", labels=["IaL0903"], graph=G)
        ea.create_node("ia0903:b", graph=G)
        ea.create_edge("ia0903:a", "R", "ia0903:b", graph=G)
        C.obs(step="A1", note="a, b and a-R->b written inside A's open transaction")
        for name, q in (("B1_unlabelled", U), ("B2_labelled", L)):
            steps[name] = {"native": read(ebn, q), "sql": read(ebs, q)}
            C.obs(step=name, **steps[name])
        ea.execute_cypher(f"USE GRAPH '{G}' MATCH (b {{node_id: 'ia0903:b'}}) SET b:IaL0903")
        C.obs(step="A2", note="SET b:IaL0903 inside A's open transaction")
        steps["B3_labelled"] = {"native": read(ebn, L), "sql": read(ebs, L)}
        C.obs(step="B3_labelled", **steps["B3_labelled"])
        cur.execute("ROLLBACK")
        C.obs(step="A3_rollback")
        for name, q in (("B4_unlabelled", U), ("B4_labelled", L)):
            steps[name] = {"native": read(ebn, q), "sql": read(ebs, q)}
            C.obs(step=name, **steps[name])
        b = [["ia0903:b"]]
        expect = {"B1_unlabelled": b, "B2_labelled": [], "B3_labelled": b, "B4_unlabelled": [], "B4_labelled": []}
        agree = all(s["native"]["rows"] == s["sql"]["rows"] for s in steps.values())
        native_ran = all(s["native"]["native"] == 1 for s in steps.values())
        dirty = all(steps[k]["native"]["rows"] == v for k, v in expect.items())
        if not native_ran:
            verdict = ("incomplete", f"a read did not run natively: { {k: s['native']['native'] for k, s in steps.items()} }")
        elif agree and dirty:
            verdict = ("pass", "native and SQL agree at every step; both read the writer's open transaction statement by "
                               "statement: the uncommitted edge before its far node's label (B1 [b], B2 []), then the "
                               "label (B3 [b]), and nothing after ROLLBACK (B4). Reading (a): dirty per-store reads; a "
                               "reader can see part of one transaction.")
        else:
            verdict = ("fail" if not agree else "pass",
                       f"agree={agree} dirty={dirty}: { {k: (s['native']['rows'], s['sql']['rows']) for k, s in steps.items()} }")
    finally:
        try:
            cur.execute("ROLLBACK")
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_note=f"no transaction left to roll back: {str(ex)[:120]}")
        cur.close()
        C.obs(step="erase", removed=ea.erase_graph(G))
        ca.close()
        cb.close()
    C.verdict(*verdict)


if __name__ == "__main__":
    main()
