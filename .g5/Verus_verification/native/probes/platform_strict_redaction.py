"""Probe platform_strict_redaction (O-WRITE-SURFACE consequence; model theorem_strict_blocks_named_graph_redaction and
witness_strict_erase_then_redact_needs_strict_off).

Sources: ADR-0013 ("Redaction only follows erasure ... The order is EraseGraph (or EraseNodes) first, then Redact";
LedgerRedact.Redact refuses target_live, LedgerRedact.cls:203-210) and spec 213's strict guard, which refuses
erase_graph (nodes_edges.py:1513). The ledger's node deletes touch the default graph only (LedgerApply.cls:357-385),
while a changeset relationship in a named graph writes its endpoints' node rows there (EnsureEndpoint, 97-110).
Expected (the conjunction of the two accepted sources, as the model derives it): with strict on, erase_graph(G) is
refused, a ledger delete of G's relationship and of its endpoints leaves G's node rows, and redact(G) is refused as
target_live; after set_strict(False), erase_graph(G) and redact(G) both succeed. This is a consequence for a human
decision (open question), not a defect claim: OBSERVED_AS_EXPECTED means the consequence holds in the product.

Writes to this arm's instance: reset() first and last.
Driven entry points: engine.ledger.enable/commit/set_strict/redact, engine.erase_graph.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import connect, engine, record, reset  # noqa: E402

TENANT = "tenantG"


def graph_rows(conn, schema, graph) -> dict:
    cur = conn.cursor()
    out = {}
    try:
        for table in ("nodes", "rdf_edges"):
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table} WHERE COALESCE(graph_id, '') = ?", [graph])
            out[table] = int(cur.fetchone()[0])
    finally:
        cur.close()
    return out


def attempt(fn) -> dict:
    try:
        return {"raised": None, "value": repr(fn())[:300]}
    except Exception as exc:
        return {"raised": type(exc).__name__, "message": str(exc)[:300]}


def main() -> int:
    from iris_vector_graph.ledger import Changeset

    conn, native = connect()
    eng = engine(conn)
    schema = str(native.get("^IVG.Deploy", "schema") or "Graph_KG")
    obs: dict = {"probe": "platform_strict_redaction", "schema": schema, "graph": TENANT}
    reset(eng, native)
    try:
        eng.ledger.enable(strict=False)
        cs = Changeset(actor="probe:platform", actor_type="system")
        cs.create_node("tx")
        cs.create_node("ty")
        cs.create_relationship("tx", "R", "ty", graph=TENANT)
        eng.ledger.commit(cs)
        obs["rows_fixture"] = graph_rows(conn, schema, TENANT)
        eng.ledger.set_strict(True)
        obs["a_erase_strict"] = attempt(lambda: eng.erase_graph(TENANT))
        cs2 = Changeset(actor="probe:platform", actor_type="system")
        cs2.delete_relationship(("tx", "R", "ty", TENANT))
        obs["b_ledger_delete_rel"] = attempt(lambda: eng.ledger.commit(cs2))
        cs3 = Changeset(actor="probe:platform", actor_type="system")
        cs3.delete_node("tx")
        cs3.delete_node("ty")
        obs["c_ledger_delete_nodes"] = attempt(lambda: eng.ledger.commit(cs3))
        obs["rows_after_ledger_deletes"] = graph_rows(conn, schema, TENANT)
        obs["d_redact_strict"] = attempt(lambda: eng.ledger.redact(TENANT))
        eng.ledger.set_strict(False)
        obs["e_erase_after_strict_off"] = attempt(lambda: eng.erase_graph(TENANT))
        obs["f_redact_after_erase"] = attempt(lambda: eng.ledger.redact(TENANT))
        obs["rows_end"] = graph_rows(conn, schema, TENANT)
    finally:
        try:
            eng.ledger.set_strict(False)
        except Exception:
            pass
        reset(eng, native)

    ok = (
        obs["rows_fixture"]["nodes"] >= 2
        and obs["a_erase_strict"].get("raised") == "LedgerStrictModeError"
        and obs["b_ledger_delete_rel"].get("raised") is None
        and obs["rows_after_ledger_deletes"]["nodes"] >= 1
        and obs["d_redact_strict"].get("raised") == "RedactionTargetLiveError"
        and obs["e_erase_after_strict_off"].get("raised") is None
        and obs["f_redact_after_erase"].get("raised") is None
    )
    if ok:
        verdict, reason = "OBSERVED_AS_EXPECTED", (
            f"under strict mode {TENANT} cannot be erased, the ledger leaves its {obs['rows_after_ledger_deletes']['nodes']} node "
            "row(s), and redact is refused target_live; with strict off both run (consequence for a human decision)")
    elif obs["d_redact_strict"].get("raised") is None and obs["rows_after_ledger_deletes"]["nodes"] > 0:
        verdict, reason = "OBSERVED_DEFECT", "redact ran while the target still held live node rows"
    else:
        verdict, reason = "INCONCLUSIVE", "the steps did not follow the modelled outcome: " + \
            "; ".join(f"{k}={v.get('raised')}" for k, v in obs.items() if isinstance(v, dict) and "raised" in v)
    obs["verdict"], obs["reason"] = verdict, reason
    path = record("platform_strict_redaction", obs)
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
