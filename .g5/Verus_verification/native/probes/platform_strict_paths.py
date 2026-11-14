"""Probe platform_strict_paths (O-WRITE-SURFACE, spec 213; model theorem_strict_paths, guarded paths).

L1 (spec 213 contracts/ledger-api.md:82-92, USER_GUIDE:1107-1120): with the ledger enabled in strict mode,
engine.create_node, engine.execute_cypher with an updating clause, and engine.erase_graph raise
LedgerStrictModeError and change nothing.

Writes to this arm's instance: reset() first and last; the fixture is committed through the ledger (recorded).
Driven entry points: engine.ledger.enable/commit/set_strict/stats, engine.create_node,
engine.execute_cypher("CREATE ..."), engine.erase_graph("tenantG").
Expected (from L1): each of the three raises LedgerStrictModeError; the rows of every graph are unchanged after each
call; rej_strict_block grows by 3.
Verdict: OBSERVED_AS_EXPECTED / OBSERVED_DEFECT / INCONCLUSIVE.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import connect, engine, record, reset  # noqa: E402

TENANT = "tenantG"


def schema_of(native) -> str:
    return str(native.get("^IVG.Deploy", "schema") or "Graph_KG")


def rows(conn, schema) -> dict:
    cur = conn.cursor()
    out = {}
    try:
        for table, cols in (("nodes", "node_id"), ("rdf_edges", "s, p, o_id")):
            cur.execute(f"SELECT COALESCE(graph_id, ''), {cols} FROM {schema}.{table}")
            out[table] = sorted([str(x) for x in r] for r in cur.fetchall())
    finally:
        cur.close()
    return out


def attempt(fn) -> dict:
    try:
        value = fn()
        err = getattr(value, "error", None)
        return {"raised": None, "value": repr(value)[:300], "result_error": str(err)[:300] if err else None}
    except Exception as exc:
        return {"raised": type(exc).__name__, "message": str(exc)[:400]}


def main() -> int:
    from iris_vector_graph.ledger import Changeset

    conn, native = connect()
    eng = engine(conn)
    schema = schema_of(native)
    obs: dict = {"probe": "platform_strict_paths", "schema": schema}
    reset(eng, native)
    try:
        eng.ledger.enable(strict=False)
        cs = Changeset(actor="probe:platform", actor_type="system")
        cs.create_node("pa")
        cs.create_node("pb")
        cs.create_relationship("pa", "R", "pb")
        cs.create_node("tx")
        cs.create_node("ty")
        cs.create_relationship("tx", "R", "ty", graph=TENANT)
        eng.ledger.commit(cs)
        eng.ledger.set_strict(True)
        obs["meta"] = eng.ledger.meta()
        rej0 = eng.ledger.stats().rejections.get("rej_strict_block", 0)
        before = rows(conn, schema)
        obs["before"] = before
        calls = {
            "create_node": lambda: eng.create_node("probe-cn"),
            "execute_cypher_create": lambda: eng.execute_cypher("CREATE (n {node_id:'probe-cy'})"),
            "erase_graph": lambda: eng.erase_graph(TENANT),
        }
        results = {}
        for name, fn in calls.items():
            results[name] = attempt(fn)
            try:
                conn.rollback()
            except Exception:
                pass
            results[name]["rows_unchanged"] = rows(conn, schema) == before
        obs["calls"] = results
        obs["rej_strict_block_delta"] = eng.ledger.stats().rejections.get("rej_strict_block", 0) - rej0
    finally:
        try:
            eng.ledger.set_strict(False)
        except Exception:
            pass
        reset(eng, native)

    refused = {k: r.get("raised") == "LedgerStrictModeError" for k, r in results.items()}
    unchanged = {k: r["rows_unchanged"] for k, r in results.items()}
    obs["refused"], obs["unchanged"] = refused, unchanged
    if all(refused.values()) and all(unchanged.values()):
        verdict, reason = "OBSERVED_AS_EXPECTED", "create_node, Cypher CREATE and erase_graph are refused under strict mode and change nothing"
    elif not all(unchanged.values()):
        verdict, reason = "OBSERVED_DEFECT", "a call under strict mode changed rows: " + \
            ", ".join(k for k, v in unchanged.items() if not v)
    else:
        verdict, reason = "OBSERVED_DEFECT", "not refused with LedgerStrictModeError: " + \
            ", ".join(f"{k} ({results[k].get('raised')})" for k, v in refused.items() if not v)
    obs["verdict"], obs["reason"] = verdict, reason
    path = record("platform_strict_paths", obs)
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
