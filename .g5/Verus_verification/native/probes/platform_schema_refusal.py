"""Probe platform_schema_refusal (O-SCHEMA, spec 262 FR-006; model theorem_refusal_changes_nothing).

L1 (ADR-0016:11, FR-006): in a namespace whose ^IVG.Deploy("schema") records R, an engine that asks for another
schema T is refused with an error naming both, before any write; nothing in the namespace changes.

READ-ONLY. No second schema is created: T is a name never set up here, and the only setup call is
initialize_schema(dry_run=True), which by contract writes nothing and which the mismatch check refuses before its
dry-run branch (_engine/schema.py:2222-2226). No reset, nothing restored, because nothing may change.

Driven entry points: IRISGraphEngine(conn, schema_prefix=T) (harness.engine), engine.node_count(),
engine.list_graphs(), engine.initialize_schema(dry_run=True).
Expected outcome (from L1, not from the code): each call raises IVGSchemaError naming R and T, and the before/after
snapshot (record, record stamp, schemas holding IVG tables, T's 4.6 marker class) is identical.
Verdict: OBSERVED_AS_EXPECTED / OBSERVED_DEFECT / INCONCLUSIVE.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import connect, engine, record  # noqa: E402

OTHER = "IVGPROBE"  # an IVG Schema name never set up in this namespace


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
        "other_marker_defined_upper": int(native.isDefined("^oddDEF", f"{OTHER.upper()}.funcCYCMP") or 0),
    }


def attempt(fn) -> dict:
    try:
        value = fn()
        return {"raised": None, "value": repr(value)[:300]}
    except Exception as exc:  # the observation is the exception itself
        return {"raised": type(exc).__name__, "message": str(exc)[:600],
                "recorded": getattr(exc, "recorded", None), "requested": getattr(exc, "requested", None)}


def main() -> int:
    conn, native = connect()
    obs: dict = {"probe": "platform_schema_refusal", "other_schema": OTHER}
    before = snapshot(conn, native)
    obs["before"] = before
    recorded = before["record"]
    if recorded in (None, "") or str(recorded).upper() == OTHER.upper():
        obs["verdict"], obs["reason"] = "INCONCLUSIVE", f"namespace record is {recorded!r}: no recorded schema distinct from {OTHER}"
        path = record("platform_schema_refusal", obs)
        print(f"INCONCLUSIVE: {obs['reason']} ({path})")
        return 0
    recorded = str(recorded)

    try:
        eng = engine(conn, schema_prefix=OTHER)
        obs["construct"] = {"raised": None}
    except Exception as exc:
        eng = None
        obs["construct"] = {"raised": type(exc).__name__, "message": str(exc)[:600]}
    calls = {}
    if eng is not None:
        calls["node_count"] = attempt(lambda: eng.node_count())
        calls["list_graphs"] = attempt(lambda: eng.list_graphs())
        calls["initialize_schema_dry_run"] = attempt(lambda: eng.initialize_schema(dry_run=True))
    obs["calls"] = calls
    after = snapshot(conn, native)
    obs["after"] = after

    def refused_naming_both(c: dict) -> bool:
        msg = c.get("message") or ""
        return c.get("raised") == "IVGSchemaError" and recorded.upper() in msg.upper() and OTHER.upper() in msg.upper()

    unchanged = before == after
    construct_refused = refused_naming_both(obs["construct"])
    all_refused = construct_refused or (bool(calls) and all(refused_naming_both(c) for c in calls.values()))
    obs["unchanged"] = unchanged
    if all_refused and unchanged:
        verdict, reason = "OBSERVED_AS_EXPECTED", f"an engine on {OTHER} is refused naming {recorded} and {OTHER}; nothing changed"
    elif not unchanged:
        verdict, reason = "OBSERVED_DEFECT", "the namespace changed after a refused engine's calls: " + \
            ", ".join(k for k in before if before[k] != after[k])
    elif any(c.get("raised") is None for c in calls.values()):
        verdict, reason = "OBSERVED_DEFECT", "an engine on another schema than the recorded one was answered: " + \
            ", ".join(k for k, c in calls.items() if c.get("raised") is None)
    else:
        verdict, reason = "INCONCLUSIVE", "calls failed, but not with IVGSchemaError naming both schemas: " + \
            "; ".join(f"{k}={c.get('raised')}" for k, c in calls.items())
    obs["verdict"], obs["reason"] = verdict, reason
    path = record("platform_schema_refusal", obs)
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
