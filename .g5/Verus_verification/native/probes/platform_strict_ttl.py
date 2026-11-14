"""Probe platform_strict_ttl (O-WRITE-SURFACE; model witness_ttl_window_admits_a_write_after_set_strict).

L1 (spec 213 contracts/ledger-api.md:82-92): once set_strict(True) has returned, a structural write outside the ledger
that begins afterwards is refused. LedgerGuard caches its Meta() probe for TTL_SECONDS = 5 per engine
(ledger/guard.py:20, 38-59); set_strict refreshes only the calling engine's guard (ledger/client.py:305-309).

Two engine objects on one connection stand for two processes (each engine has its own guard: _engine/ledger.py:30-38).
Writes to this arm's instance: reset() first and last.
Driven entry points: engine.ledger.enable/set_strict, engine.create_node.
Steps: engine 2 writes once while strict is off (its guard caches "not strict"); engine 1 calls set_strict(True);
engine 2 at once calls create_node("ttl-bypass"); after > 5 s engine 2 calls create_node("ttl-after").
Expected (L1): both of engine 2's calls after set_strict raise LedgerStrictModeError; neither row exists.
Model prediction: "ttl-bypass" is written (within 5 s of engine 2's probe); "ttl-after" is refused -> OBSERVED_DEFECT.
"""
from __future__ import annotations

import sys
import time
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


def attempt(fn) -> dict:
    try:
        return {"raised": None, "value": repr(fn())[:200]}
    except Exception as exc:
        return {"raised": type(exc).__name__, "message": str(exc)[:300]}


def main() -> int:
    conn, native = connect()
    eng1 = engine(conn)
    eng2 = engine(conn)
    schema = str(native.get("^IVG.Deploy", "schema") or "Graph_KG")
    obs: dict = {"probe": "platform_strict_ttl", "schema": schema}
    reset(eng1, native)
    try:
        eng1.ledger.enable(strict=False)
        t0 = time.monotonic()
        obs["warm"] = attempt(lambda: eng2.create_node("ttl-warm"))
        t1 = time.monotonic()
        eng1.ledger.set_strict(True)
        t2 = time.monotonic()
        obs["meta_after_set_strict"] = eng1.ledger.meta()
        obs["engine1_same_engine"] = attempt(lambda: eng1.create_node("ttl-engine1"))
        t3 = time.monotonic()
        obs["bypass"] = attempt(lambda: eng2.create_node("ttl-bypass"))
        t4 = time.monotonic()
        time.sleep(max(0.0, 5.5 - (time.monotonic() - t0)))
        t5 = time.monotonic()
        obs["after_ttl"] = attempt(lambda: eng2.create_node("ttl-after"))
        obs["seconds"] = {"warm_probe": round(t1 - t0, 3), "set_strict_returned": round(t2 - t0, 3),
                          "bypass_call": round(t4 - t0, 3), "after_ttl_call": round(t5 - t0, 3), "engine1_call": round(t3 - t0, 3)}
        try:
            conn.rollback()
        except Exception:
            pass
        obs["rows"] = {n: node_rows(conn, schema, n) for n in ("ttl-warm", "ttl-engine1", "ttl-bypass", "ttl-after")}
    finally:
        try:
            eng1.ledger.set_strict(False)
        except Exception:
            pass
        reset(eng1, native)

    r = obs["rows"]
    if r["ttl-warm"] != 1 or obs["engine1_same_engine"].get("raised") != "LedgerStrictModeError":
        verdict, reason = "INCONCLUSIVE", f"fixture did not behave: warm row {r['ttl-warm']}, engine 1 call {obs['engine1_same_engine']}"
    elif obs["seconds"]["bypass_call"] >= 5.0:
        verdict, reason = "INCONCLUSIVE", f"engine 2's call came {obs['seconds']['bypass_call']} s after its probe, outside the TTL"
    elif r["ttl-bypass"] == 1:
        verdict, reason = "OBSERVED_DEFECT", (
            f"engine 2 wrote 'ttl-bypass' unrecorded {obs['seconds']['bypass_call'] - obs['seconds']['set_strict_returned']:.3f} s "
            f"after set_strict(True) returned (cached probe); after the TTL it was "
            f"{'refused' if obs['after_ttl'].get('raised') == 'LedgerStrictModeError' else 'NOT refused'}")
    elif obs["bypass"].get("raised") == "LedgerStrictModeError" and obs["after_ttl"].get("raised") == "LedgerStrictModeError":
        verdict, reason = "OBSERVED_AS_EXPECTED", "engine 2 was refused immediately after set_strict(True)"
    else:
        verdict, reason = "INCONCLUSIVE", f"bypass {obs['bypass']}; after {obs['after_ttl']}"
    obs["verdict"], obs["reason"] = verdict, reason
    path = record("platform_strict_ttl", obs)
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
