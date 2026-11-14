"""Probe platform_strict_bulk_delete_adjacency (O-WRITE-SURFACE; model witness_bulk_delete_adjacency_bypasses_strict).

L1 (spec 213 contracts/ledger-api.md:82-92, USER_GUIDE:1107-1110): with the ledger strict, a structural write that
does not go through the ledger is refused and changes nothing; the documented exemptions are BulkLoader, raw SQL and
the derived temporal row. engine.bulk_delete_adjacency is an engine method (deprecated, still public:
docs/API_REFERENCE.md:418) that deletes rdf_edges rows through Graph.KG.Eraser.EraseEdges (nodes_edges.py:2301-2338)
and calls no ledger_check.

Writes to this arm's instance: reset() first and last; fixture committed through the ledger.
Driven entry points: engine.ledger.enable/commit/set_strict/verify, engine.bulk_delete_adjacency(["pa"]).
Expected (L1): LedgerStrictModeError and the edge pa-R->pb still present.
Model prediction: no error, the edge is gone, ledger.verify() no longer 'equal' -> OBSERVED_DEFECT.
"""
from __future__ import annotations

import sys
import traceback
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import connect, engine, record, reset  # noqa: E402


def edge_count(conn, schema, s, p, o) -> int:
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {schema}.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND COALESCE(graph_id, '') = ''",
                    [s, p, o])
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def main() -> int:
    from iris_vector_graph.ledger import Changeset

    conn, native = connect()
    eng = engine(conn)
    schema = str(native.get("^IVG.Deploy", "schema") or "Graph_KG")
    obs: dict = {"probe": "platform_strict_bulk_delete_adjacency", "schema": schema}
    reset(eng, native)
    try:
        eng.ledger.enable(strict=False)
        cs = Changeset(actor="probe:platform", actor_type="system")
        cs.create_node("pa")
        cs.create_node("pb")
        cs.create_relationship("pa", "R", "pb")
        eng.ledger.commit(cs)
        obs["verify_before"] = str(eng.ledger.verify().result)
        eng.ledger.set_strict(True)
        obs["meta"] = eng.ledger.meta()
        obs["edge_before"] = edge_count(conn, schema, "pa", "R", "pb")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                obs["call"] = {"raised": None, "value": repr(eng.bulk_delete_adjacency(["pa"]))}
        except Exception as exc:
            obs["call"] = {"raised": type(exc).__name__, "message": str(exc)[:400]}
        try:
            conn.rollback()
        except Exception:
            pass
        obs["edge_after"] = edge_count(conn, schema, "pa", "R", "pb")
        try:
            obs["verify_after"] = str(eng.ledger.verify().result)
        except Exception as exc:
            obs["verify_after"] = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        try:
            eng.ledger.set_strict(False)
        except Exception:
            pass
        reset(eng, native)

    if obs["edge_before"] != 1:
        verdict, reason = "INCONCLUSIVE", f"fixture edge count {obs['edge_before']} (expected 1)"
    elif obs["call"].get("raised") == "LedgerStrictModeError" and obs["edge_after"] == 1:
        verdict, reason = "OBSERVED_AS_EXPECTED", "bulk_delete_adjacency is refused under strict mode"
    elif obs["edge_after"] == 0:
        verdict, reason = "OBSERVED_DEFECT", (
            "under strict mode bulk_delete_adjacency deleted the edge unrecorded "
            f"(call {obs['call'].get('raised') or 'returned'}; verify {obs.get('verify_before')} -> {obs.get('verify_after')})")
    else:
        verdict, reason = "INCONCLUSIVE", f"call {obs['call']}; edge still present but no strict refusal"
    obs["verdict"], obs["reason"] = verdict, reason
    path = record("platform_strict_bulk_delete_adjacency", obs)
    print(f"{verdict}: {reason} ({path})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        print("INCONCLUSIVE: the probe itself failed (see traceback)")
        raise SystemExit(0)
