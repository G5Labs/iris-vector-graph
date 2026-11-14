#!/usr/bin/env python3
"""A write inside a Cypher CALL { } subquery (ontology query.writes.subquery).

Expected (openCypher semantics; IVG docs claim CALL subqueries are supported; ontology intent: carry the
write out or refuse the query): after `CALL { CREATE (n:SubqProbe {id: 'subq|1'}) } RETURN 1` either the
node exists, or the call raised. Suspected (translator reads only MATCH/WHERE/UNWIND in a subquery body and
does not mark the query as a write): the call succeeds and nothing is written.
"""
from redaction_common import connect, engine, ensure_schema, reset, verdict


def node_rows(conn, nid):
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", [nid])
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    cases = {}
    for name, q in [("call_create", "CALL { CREATE (n:SubqProbe {id: 'subq|1'}) } RETURN 1 AS one"),
                    ("plain_create", "CREATE (n:SubqProbe {id: 'subq|2'}) RETURN n.id")]:
        try:
            res = eng.execute_cypher(q)
            err = res.get("error") if isinstance(res, dict) else getattr(res, "error", None)
            rows = res.get("rows") if isinstance(res, dict) else getattr(res, "rows", res)
            cases[name] = {"raised": False, "result_type": type(res).__name__,
                           "error_in_result": str(err)[:300] if err else None, "rows": str(rows)[:200]}
        except Exception as ex:
            cases[name] = {"raised": True, "error": type(ex).__name__, "message": str(ex)[:300]}
    cases["call_create"]["node_rows"] = node_rows(conn, "subq|1")
    cases["plain_create"]["node_rows"] = node_rows(conn, "subq|2")
    c = cases["call_create"]
    refused = c["raised"] or bool(c.get("error_in_result"))
    ok = refused or c["node_rows"] == 1
    reason = (f"CALL{{CREATE}}: {'raised ' + c.get('error', '') if c['raised'] else ('refused in result: ' + str(c.get('error_in_result'))[:80] if refused else 'returned ' + c['rows'])}, node rows={c['node_rows']}; "
              f"control plain CREATE node rows={cases['plain_create']['node_rows']}")
    return verdict("cypher_subquery_write", ok, reason, cases)


if __name__ == "__main__":
    raise SystemExit(main())
