#!/usr/bin/env python3
"""The whole default graph as a target while its node ids are still live in a named graph (witness W3).

Ledger node records are graph-blind (all in the default graph) and verify() compares nodes graph-blind;
spec 256 plan.md says "The node-liveness check for a default-graph target is graph-blind for the same
reason". LiveRows applies that only with a prefix (LedgerRedact.cls:155-165): without one it counts the
default graph's rows only.

Expected: redact(None) is refused (target_live) while node rows with those ids are live in graph gN, and
nothing changes.
"""
from redaction_common import connect, cs, engine, ensure_schema, ledger_records, reset, verdict


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    led = eng.ledger
    led.enable()
    c = cs("nodes and a named-graph edge", "w|c", "w-k", "w-feed")
    c.create_node("X", labels=["L"], properties={"p": "xSecret"})
    c.create_node("Y")
    c.create_relationship("X", "R", "Y", graph="gN")
    led.commit(c)
    eng.erase_graph(None)
    cur = conn.cursor()
    cur.execute("SELECT node_id, graph_id FROM Graph_KG.nodes ORDER BY node_id"); rows = cur.fetchall()
    cur.close()
    before = ledger_records(native)
    verify_before = led.verify().result
    try:
        r = led.redact(None)
        outcome = {"refused": False, "receipt": vars(r)}
    except Exception as ex:
        outcome = {"refused": True, "error": type(ex).__name__, "message": str(ex)}
    after = ledger_records(native)
    tombed = sorted(str(k) for k in after if after[k][0] == "redacted" and before[k][0] != "redacted")
    data = {"node_rows_after_erasing_default_graph": [list(r) for r in rows], "outcome": outcome,
            "node_records_tombstoned": tombed, "verify_before": verify_before, "verify_after": led.verify().result}
    ok = outcome["refused"] and outcome.get("error") == "RedactionTargetLiveError" and before == after
    reason = (f"live node rows {[(r[0], r[1]) for r in rows]}; redact(None) {'refused' if outcome['refused'] else 'completed'}; "
              f"{len(tombed)} records tombstoned; verify after: {data['verify_after']}")
    return verdict("redaction_default_graph_whole", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
