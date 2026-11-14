"""Probe platform_schema_waiver (O-SCHEMA F-S2; model witness_waiver_releases_a_mismatch).

L1 (ADR-0016:11, FR-006): an engine that asks for another schema than the recorded one is refused before any database
access, whoever builds it. The migrations build IRISGraphEngine(conn) on the environment's or default schema and call
engine._waive_schema_check() (graph_scoped_embeddings.py:287-288, temporal_structural_rows.py:85-89), which releases a
mismatch refusal too (engine.py:1874-1890).

READ-ONLY. Both migrations run as dry runs, which by contract write nothing; the schema they are pointed at
(IVG_SCHEMA_PREFIX=IVGPROBE) has never been set up, so no object of it exists to write to. No reset.

Driven entry points: iris_vector_graph.migrations.migrate_to_graph_scoped_embeddings(conn, dry_run=True) (exported);
iris_vector_graph.migrations.temporal_structural_rows.backfill_structural_rows(conn, dry_run=True); and, as the
control, IRISGraphEngine(conn).node_count() under the same environment (no waiver).
Expected (L1): all three raise IVGSchemaError (mismatch) and the snapshot is unchanged.
Model prediction: the control raises IVGSchemaError; the two migrations do not (they reach SQL on IVGPROBE, which fails
on a missing table, or return a plan) -> OBSERVED_DEFECT.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import connect, engine, record  # noqa: E402

OTHER = "IVGPROBE"


def snapshot(conn, native) -> dict:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_NAME IN ('nodes', 'rdf_edges')"
        )
        tables = sorted([str(a), str(b)] for a, b in cur.fetchall())
    finally:
        cur.close()
    return {
        "record": native.get("^IVG.Deploy", "schema"),
        "recorded_stamp": native.get("^IVG.Deploy", "schema", "recorded"),
        "ivg_table_schemas": tables,
        "other_marker_defined": int(native.isDefined("^oddDEF", f"{OTHER}.funcCYCMP") or 0),
    }


def attempt(fn) -> dict:
    try:
        value = fn()
        return {"raised": None, "value": repr(value)[:400]}
    except Exception as exc:
        return {"raised": type(exc).__name__, "message": str(exc)[:600]}


def main() -> int:
    conn, native = connect()
    obs: dict = {"probe": "platform_schema_waiver", "other_schema": OTHER}
    before = snapshot(conn, native)
    obs["before"] = before
    recorded = before["record"]
    if recorded in (None, "") or str(recorded).upper() == OTHER.upper():
        obs["verdict"], obs["reason"] = "INCONCLUSIVE", f"namespace record is {recorded!r}"
        path = record("platform_schema_waiver", obs)
        print(f"INCONCLUSIVE: {obs['reason']} ({path})")
        return 0

    from iris_vector_graph.migrations import migrate_to_graph_scoped_embeddings
    from iris_vector_graph.migrations.temporal_structural_rows import backfill_structural_rows

    saved = os.environ.get("IVG_SCHEMA_PREFIX")
    os.environ["IVG_SCHEMA_PREFIX"] = OTHER
    try:
        def control():
            eng = engine(conn, vector_dtype="DOUBLE")
            return eng.node_count()

        obs["control_engine_node_count"] = attempt(control)
        obs["migrate_to_graph_scoped_embeddings_dry_run"] = attempt(
            lambda: migrate_to_graph_scoped_embeddings(conn, dry_run=True))
        obs["backfill_structural_rows_dry_run"] = attempt(
            lambda: backfill_structural_rows(conn, dry_run=True))
    finally:
        if saved is None:
            os.environ.pop("IVG_SCHEMA_PREFIX", None)
        else:
            os.environ["IVG_SCHEMA_PREFIX"] = saved
    try:
        conn.rollback()
    except Exception:
        pass
    after = snapshot(conn, native)
    obs["after"] = after
    unchanged = before == after
    obs["unchanged"] = unchanged

    control_refused = obs["control_engine_node_count"].get("raised") == "IVGSchemaError"
    mig = {k: obs[k] for k in ("migrate_to_graph_scoped_embeddings_dry_run", "backfill_structural_rows_dry_run")}
    not_refused = [k for k, c in mig.items() if c.get("raised") != "IVGSchemaError"]
    if not control_refused:
        verdict, reason = "INCONCLUSIVE", f"the control engine on {OTHER} was not refused ({obs['control_engine_node_count']})"
    elif not unchanged:
        verdict, reason = "OBSERVED_DEFECT", "the namespace changed during dry runs: " + \
            ", ".join(k for k in before if before[k] != after[k])
    elif not_refused:
        verdict, reason = "OBSERVED_DEFECT", (
            f"the namespace records {recorded}; an engine on {OTHER} is refused, but the migrations' waived engine was "
            "not: " + "; ".join(f"{k} -> {mig[k].get('raised') or 'returned'}" for k in not_refused))
    else:
        verdict, reason = "OBSERVED_AS_EXPECTED", "the migrations' engines on another schema are refused too"
    obs["verdict"], obs["reason"] = verdict, reason
    path = record("platform_schema_waiver", obs)
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
