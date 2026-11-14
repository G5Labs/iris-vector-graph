#!/usr/bin/env python3
"""An orphan property row blocks every prefix redaction of its tenant (review round 3 R3-4; model witness W6).

Graph_KG.rdf_props has no foreign key to Graph_KG.nodes, and post_commit_properties insert property rows directly
(client._apply_post_commit_properties). The prefix erase collects ids from node rows (Eraser.cls:331-349), so it
never selects a property row whose node row does not exist; LedgerRedact.LiveRows counts rdf_props rows by prefix.
Expected (ADR-0004 erasure of every store; ADR-0013 erase-then-redact recipe): after delete_nodes_by_prefix("tP|")
the tenant has no live content and redact(None, prefix="tP") completes. Observed as built (model W6): the redaction
is refused target_live, a second prefix erase changes nothing, and only an explicit-id erase clears the row.
"""
from redaction_common import connect, cs, engine, ensure_schema, reset, verdict


def props_of(conn, nid):
    cur = conn.cursor()
    try:
        cur.execute('SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s = ?', [nid])
        p = int(cur.fetchone()[0])
        cur.execute('SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?', [nid])
        return p, int(cur.fetchone()[0])
    finally:
        cur.close()


def try_redact(led):
    try:
        r = led.redact(None, prefix="tP")
        return {"refused": False, "complete": r.complete}
    except Exception as ex:
        return {"refused": True, "error": type(ex).__name__, "message": str(ex)[:200]}


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    led = eng.ledger
    led.enable()
    c = cs("tenant P", "tP|c", "tP-k", "tP-feed")
    c.create_node("tP|1", properties={"s": "pSecret"})
    c.post_commit_properties = {"tP|x": {"audit_rev": "pAudit"}}  # documented audit-trail pattern, node never created
    res = led.commit(c)
    state0 = props_of(conn, "tP|x")
    eng.delete_nodes_by_prefix("tP|")
    state1 = props_of(conn, "tP|x")
    r1 = try_redact(led)
    eng.delete_nodes_by_prefix("tP|")
    r2 = try_redact(led)
    explicit = None
    try:
        explicit = eng.delete_node("tP|x", graph="")
    except Exception as ex:
        explicit = f"{type(ex).__name__}: {str(ex)[:160]}"
        try:
            explicit = str(eng._store.delete_nodes(["tP|x"], graph=""))
        except Exception as ex2:
            explicit = explicit + f" | store: {type(ex2).__name__}: {str(ex2)[:160]}"
    state2 = props_of(conn, "tP|x")
    r3 = try_redact(led)
    data = {"post_commit_applied": res.post_commit_applied, "orphan_prop_rows_node_rows": [state0, state1, state2],
            "redact_after_prefix_erase": r1, "redact_after_second_prefix_erase": r2, "explicit_erase": explicit,
            "redact_after_explicit_erase": r3}
    ok = not r1["refused"]
    reason = (f"orphan (props, nodes) after commit {state0}, after prefix erase {state1}; redact → {r1.get('error') or 'completed'}; "
              f"again after a second prefix erase → {r2.get('error') or 'completed'}; explicit-id erase → props {state2[0]}; "
              f"redact → {r3.get('error') or 'completed'}")
    return verdict("redaction_orphan_prop_blocks", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
