"""Probe platform_strict_api_sample (O-WRITE-SURFACE F-H3/F3; model theorem_strict_paths, path ApiSampleCypher).

L1 (spec 213 contracts/ledger-api.md:82-92): with the ledger strict, execute_cypher with an updating clause is refused;
iris_vector_graph/cypher/read_only.py:3-5 lists api.main's /api/cypher among the routes the Cypher write rule covers. The api.main
handler translates the query and runs its SQL on a raw cursor between START TRANSACTION and COMMIT
(api/routers/cypher.py:130-166), with no ledger_check.

Writes to this arm's instance: reset() first and last.
Driven entry point: the handler coroutine api.routers.cypher.execute_cypher_query (the body FastAPI runs for
POST /api/cypher), called with the harness connection and engine, as api.main's dependencies would pass them.
Steps: (control) strict off: CREATE (n {node_id:'api-off'}) must write the row, else the route cannot write at all and
the strict case says nothing; (case) strict on: CREATE (n {node_id:'api-strict'}).
Expected (L1): the strict case is refused and no 'api-strict' row exists.
Model prediction: the row is written -> OBSERVED_DEFECT.
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import connect, engine, record, reset  # noqa: E402


def node_rows(conn, schema, node_id) -> int:
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {schema}.nodes WHERE node_id = ?", [node_id])
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def call_route(handler, request_cls, conn, eng, query) -> dict:
    try:
        resp = asyncio.run(handler(request_cls(query=query), db_connection=conn, engine=eng))
    except Exception as exc:
        return {"raised": type(exc).__name__, "message": str(exc)[:300]}
    status = getattr(resp, "status_code", 200)
    body = getattr(resp, "body", None)
    return {"raised": None, "status": status, "type": type(resp).__name__,
            "body": (body.decode() if isinstance(body, (bytes, bytearray)) else repr(resp))[:300]}


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    schema = str(native.get("^IVG.Deploy", "schema") or "Graph_KG")
    obs: dict = {"probe": "platform_strict_api_sample", "schema": schema}
    try:
        from api.models.cypher import CypherQueryRequest
        from api.routers.cypher import execute_cypher_query
    except Exception as exc:
        obs["verdict"], obs["reason"] = "INCONCLUSIVE", f"api.main's router cannot be imported here: {type(exc).__name__}: {exc}"
        path = record("platform_strict_api_sample", obs)
        print(f"INCONCLUSIVE: {obs['reason']} ({path})")
        return 0
    reset(eng, native)
    try:
        eng.ledger.enable(strict=False)
        obs["control_strict_off"] = call_route(execute_cypher_query, CypherQueryRequest, conn, eng,
                                               "CREATE (n {node_id:'api-off'})")
        obs["control_row"] = node_rows(conn, schema, "api-off")
        eng.ledger.set_strict(True)
        obs["meta"] = eng.ledger.meta()
        obs["strict_case"] = call_route(execute_cypher_query, CypherQueryRequest, conn, eng,
                                        "CREATE (n {node_id:'api-strict'})")
        try:
            conn.rollback()
        except Exception:
            pass
        obs["strict_row"] = node_rows(conn, schema, "api-strict")
        # the engine's own path, for contrast (guarded)
        try:
            eng.execute_cypher("CREATE (n {node_id:'engine-strict'})")
            obs["engine_path"] = {"raised": None}
        except Exception as exc:
            obs["engine_path"] = {"raised": type(exc).__name__}
        obs["engine_row"] = node_rows(conn, schema, "engine-strict")
    finally:
        try:
            eng.ledger.set_strict(False)
        except Exception:
            pass
        reset(eng, native)

    if obs["control_row"] != 1:
        verdict, reason = "INCONCLUSIVE", f"the route did not write with strict off either ({obs['control_strict_off']})"
    elif obs["strict_row"] == 1:
        verdict, reason = "OBSERVED_DEFECT", (
            "under strict mode api.main's POST /api/cypher committed CREATE unrecorded "
            f"(engine path: {obs['engine_path'].get('raised') or 'admitted'}, row {obs['engine_row']})")
    else:
        verdict, reason = "OBSERVED_AS_EXPECTED", f"the strict case wrote nothing ({obs['strict_case']})"
    obs["verdict"], obs["reason"] = verdict, reason
    path = record("platform_strict_api_sample", obs)
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
