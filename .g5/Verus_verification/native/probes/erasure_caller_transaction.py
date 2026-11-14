#!/usr/bin/env python3
"""Erasure inside a caller's transaction, and a redaction that runs before that transaction ends.

Part A — engine on a plain DB-API connection: Graph.KG.Eraser.EraseGraph runs on the caller's own process,
so its TSTART nests in the caller's open transaction (4.6.4, aad50087). LedgerRedact.LiveRows reads without
locks. Sequence: conn1 START TRANSACTION; erase_graph(gA) on conn1; conn2 redact(gA); conn1 ROLLBACK.
Expected (ADR-0013 "refused while any of the target's content is live"; ADR-0004 history survives): after
the rollback, gA's content is live again, so its history must not have been tombstoned — either the
redaction is refused (target live / erase uncommitted) or it cannot complete until the erase commits.

Part B — engine from IRISGraphEngine.from_connect: the engine's native calls use a dedicated connection
(engine.py _iris_obj). Observation only: does erase_graph join the caller's transaction on engine.conn
(rolled back with it) or commit on its own?
"""
import os

from redaction_common import connect, cs, engine, ensure_schema, ledger_records, reset, verdict

GA = "gA"


def seed(eng):
    eng.ledger.enable()
    c = cs("tenant A", "tA|c", "tA-k", "tA-feed")
    c.create_node("tA|1", properties={"p": "aSecret"})
    c.create_node("tA|2")
    c.create_relationship("tA|1", "R", "tA|2", qualifiers={"q": "aQual"}, graph=GA)
    eng.ledger.commit(c)


def count_edges(conn):
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", [GA])
        return cur.fetchone()[0]
    finally:
        cur.close()


def tlevel(conn):
    cur = conn.cursor()
    try:
        cur.execute("SELECT $TLEVEL")
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def main() -> int:
    conn0, native0 = connect()
    eng0 = engine(conn0)
    ensure_schema(eng0)

    # Part A
    reset(eng0, native0)
    seed(eng0)
    conn1, _n1 = connect()
    eng1 = engine(conn1)
    cur = conn1.cursor(); cur.execute("START TRANSACTION"); cur.close()
    removed = eng1.erase_graph(GA)
    level_after_erase = tlevel(conn1)
    seen_by_other = count_edges(conn0)
    try:
        r = eng0.ledger.redact(GA)
        red = {"refused": False, "complete": r.complete, "records_tombstoned": r.records_tombstoned}
    except Exception as ex:
        red = {"refused": True, "error": type(ex).__name__, "message": str(ex)[:300]}
    conn1.rollback()
    edges_after_rollback = count_edges(conn0)
    recs = ledger_records(native0)
    tombs = sum(1 for f in recs.values() if f[0] == "redacted")
    ver = eng0.ledger.verify().result
    part_a = {"erase_removed": removed, "tlevel_after_erase": level_after_erase, "edges_seen_by_other_connection": seen_by_other,
              "redaction": red, "edges_after_caller_rollback": edges_after_rollback, "tombstones": tombs, "verify": ver}
    ok_a = not (edges_after_rollback > 0 and tombs > 0)
    verdict("erasure_caller_transaction_redaction", ok_a,
            f"erase nested at $TLEVEL={level_after_erase}; redaction {'refused: ' + red.get('error', '') if red['refused'] else 'completed with ' + str(red['records_tombstoned']) + ' tombstones'}; "
            f"after the caller's rollback gA has {edges_after_rollback} edge row(s) and the ledger {tombs} tombstone(s); verify={ver}", part_a)

    # Part B
    reset(eng0, native0)
    seed(eng0)
    from iris_vector_graph.engine import IRISGraphEngine

    engb = IRISGraphEngine.from_connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace=os.environ.get("IVG_NAMESPACE", "USER"),
                                        username="_SYSTEM", password="SYS", embedding_dimension=768)
    cur = engb.conn.cursor(); cur.execute("START TRANSACTION"); cur.close()
    removed_b = engb.erase_graph(GA)
    level_b = tlevel(engb.conn)
    engb.conn.rollback()
    edges_b = count_edges(conn0)
    part_b = {"erase_removed": removed_b, "caller_tlevel_after_erase": level_b, "edges_after_caller_rollback": edges_b,
              "native_is_dedicated": getattr(engb, "_native_conn", None) is not None}
    print(f"erasure_caller_transaction_from_connect: OBSERVATION — erase via from_connect; caller $TLEVEL={level_b}; "
          f"after the caller's rollback gA has {edges_b} edge row(s) (0 = the erase committed on its own)")
    from redaction_common import record
    record("erasure_caller_transaction_from_connect", part_b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
