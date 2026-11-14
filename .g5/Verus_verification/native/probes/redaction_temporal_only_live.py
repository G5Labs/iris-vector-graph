#!/usr/bin/env python3
"""A target whose only live content is a temporal edge of a temporal-only predicate (model witness W2).

Expected (ADR-0013, CONTEXT.md "Redaction": refused while any of the target's content is live; spec 256
FR refusal target_live): redact(graph) is refused and nothing changes while the temporal edge is in the
index. LiveRows (LedgerRedact.cls:149-178) reads nodes, rdf_labels, rdf_props and rdf_edges only, and a
temporal-only predicate (ADR-0015) writes no row and no node.
"""
from redaction_common import connect, cs, engine, ensure_schema, ledger_records, reset, verdict

G = "gT"


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    eng.ledger.enable()
    eng.set_temporal_structural("METRIC", False, graph=G)
    c = cs("temporal load", "tT|c", "tT-k", "tT-feed")
    c.create_temporal_edge("tT|s", "METRIC", "tT|o", ts=1700000100, weight=7.5, graph=G, attrs={"note": "tSecret"})
    eng.ledger.commit(c)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", [G]); rows_edges = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", [G]); rows_nodes = cur.fetchone()[0]
    cur.close()
    window_before = eng.get_edges_in_window(source="tT|s", start=0, end=2000000000, graph=G)
    before = ledger_records(native)
    try:
        r = eng.ledger.redact(G)
        outcome = {"refused": False, "receipt": vars(r)}
    except Exception as ex:
        outcome = {"refused": True, "error": type(ex).__name__, "message": str(ex)}
    after = ledger_records(native)
    window_after = eng.get_edges_in_window(source="tT|s", start=0, end=2000000000, graph=G)
    tombed = [k for k, f in after.items() if f[0] == "redacted" and before.get(k, [None])[0] == "create_temporal_edge"]
    data = {"rdf_edges_rows_in_graph": rows_edges, "node_rows_in_graph": rows_nodes, "window_before": window_before,
            "window_after": window_after, "outcome": outcome, "temporal_records_tombstoned": tombed,
            "records_changed": [k for k in before if before[k] != after.get(k)], "verify": eng.ledger.verify().result}
    ok = outcome["refused"] and outcome.get("error") == "RedactionTargetLiveError" and before == after
    reason = (f"rows={rows_edges} nodes={rows_nodes} window_before={len(window_before)} outcome={outcome.get('error') or 'completed'} "
              f"tombstoned_temporal_records={len(tombed)} window_after={len(window_after)}")
    return verdict("redaction_temporal_only_live", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
