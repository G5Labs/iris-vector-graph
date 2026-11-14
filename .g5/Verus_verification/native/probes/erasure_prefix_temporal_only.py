#!/usr/bin/env python3
"""Erase-by-prefix of a tenant whose events use a temporal-only predicate (review round 2 core R2-1).

The documented tenant recipe erases by prefix (delete_nodes_by_prefix) and redacts by prefix. Eraser.EraseNodes
collects the ids to erase from Graph_KG.nodes rows (Eraser.cls:331-349) and erases temporal edges only for those
ids (TemporalIndex.EraseNodes). A temporal-only predicate (ADR-0015) writes no node row and no edge row.
Expected (ADR-0004 / CONTEXT.md "Erasure": content is removed from every store that holds it, the temporal index
included): after delete_nodes_by_prefix("tE|") no event of the tenant remains readable, and the redaction that
follows leaves no live tenant content behind.
"""
from redaction_common import connect, cs, engine, ensure_schema, ledger_records, reset, verdict

P = "EVT_ONLY"


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    led = eng.ledger
    led.enable()
    eng.set_temporal_structural(P, False)  # default graph, temporal-only
    c = cs("tenant E", "tE|c", "tE-k", "tE-feed")
    c.create_node("tE|1", properties={"s": "eSecret"})
    c.create_temporal_edge("tE|1", P, "tE|sensor", ts=1700000200, weight=3.0)
    c.create_temporal_edge("tE|x", P, "tE|y", ts=1700000201, weight=4.0)
    led.commit(c)
    before = {s: eng.get_edges_in_window(source=s, start=0, end=2000000000) for s in ("tE|1", "tE|x")}
    removed = eng.delete_nodes_by_prefix("tE|")
    after_erase = {s: eng.get_edges_in_window(source=s, start=0, end=2000000000) for s in ("tE|1", "tE|x")}
    try:
        r = led.redact(None, prefix="tE")
        red = {"complete": r.complete, "records_tombstoned": r.records_tombstoned}
    except Exception as ex:
        red = {"error": type(ex).__name__, "message": str(ex)[:300]}
    after_redact = {s: eng.get_edges_in_window(source=s, start=0, end=2000000000) for s in ("tE|1", "tE|x")}
    ver = led.verify().result
    tomb_temporal = sum(1 for f in ledger_records(native).values() if f[0] == "redacted" and f[3] == "create_temporal_edge")
    left = {s: len(v) for s, v in after_redact.items() if v}
    data = {"events_before": {s: len(v) for s, v in before.items()}, "nodes_removed": removed,
            "events_after_erase": {s: len(v) for s, v in after_erase.items()}, "redaction": red,
            "events_after_redaction": left, "temporal_records_tombstoned": tomb_temporal, "verify": ver}
    ok = not left
    reason = (f"before {data['events_before']}; delete_nodes_by_prefix removed {removed} node row(s); events still readable after "
              f"erase {data['events_after_erase']} and after redaction {left}; redaction {red}; verify={ver}")
    return verdict("erasure_prefix_temporal_only", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
