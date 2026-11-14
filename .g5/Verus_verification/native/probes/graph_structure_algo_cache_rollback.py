#!/usr/bin/env python3
"""F1: a cached algorithm answer computed over a write that then rolls back.

L1 (CONTEXT.md:116-119 "a cached algorithm result is valid only while the token it was computed under is current";
ADR-0012:23-25 names "a reader caching an uncommitted edge that is then rolled back" as the unsafe case; model
graph_structure.rs §4): after the rollback, WCC must answer for the committed graph — c is its own component.

Model prediction (witness_rolled_back_write_poisons_algo_cache): connection 1 opens a transaction and creates c->a
(the write bumps ^KG("__version"), which the rollback does not take back); connection 2's kg_WCC misses at the new
token, computes over the uncommitted edge and stores under it; connection 1 rolls back; a third connection's kg_WCC is
served the stored answer, in which c is joined to a and b.

Public entry points: engine.create_node / create_edge (inside the caller's SQL transaction, 4.6.4), engine.kg_WCC
(cached through IRISSQLStore._cached_algorithm), SQL START TRANSACTION / ROLLBACK on the caller's connection.
Requires the algorithm cache enabled (IVG_DISABLE_ALGO_CACHE unset).
"""
from __future__ import annotations

import os

from graph_structure_common import connect, engine, ensure_schema, err, finish, reset, sql_all, sql_exec

NAME = "graph_structure_algo_cache_rollback"
A, B, C, P = "g5ac:a", "g5ac:b", "g5ac:c", "G5AC_T"


def joined(wcc: dict, x: str, y: str):
    if not isinstance(wcc, dict) or x not in wcc or y not in wcc:
        return None
    return wcc[x] == wcc[y]


def token(native):
    return native.get("^KG", "__version")


def judge(obs: dict) -> tuple[str, str]:
    if obs.get("setup_error") or obs.get("baseline_c_joined") is not False:
        return "INCONCLUSIVE", f"baseline not as set up: {obs.get('setup_error') or obs.get('baseline')}"
    if obs.get("dirty_c_joined") is not True:
        return "INCONCLUSIVE", "the second connection did not see the uncommitted edge (no poisoning possible this run)"
    if obs.get("rows_c_a_after_rollback") != 0:
        return "INCONCLUSIVE", f"the rollback left {obs.get('rows_c_a_after_rollback')} rows of c->a"
    after = obs.get("after_c_joined")
    if after is True:
        return "OBSERVED_DEFECT", (f"after the rollback WCC still joins c to a (token {obs.get('token_after_rollback')} "
                                   f"= token the dirty answer was stored under {obs.get('token_dirty')})")
    if after is False:
        return "OBSERVED_AS_EXPECTED", "after the rollback WCC answers the committed graph"
    return "INCONCLUSIVE", f"WCC after rollback: {obs.get('after')}"


def self_check() -> dict:
    base = {"baseline_c_joined": False, "dirty_c_joined": True, "rows_c_a_after_rollback": 0}
    bad, _ = judge(dict(base, after_c_joined=True))
    good, _ = judge(dict(base, after_c_joined=False))
    return {"defect_case": bad, "fixed_case": good, "discriminates": bad == "OBSERVED_DEFECT" and good == "OBSERVED_AS_EXPECTED"}


def main() -> None:
    obs = {"probe": NAME, "algo_cache_disabled_env": os.environ.get("IVG_DISABLE_ALGO_CACHE", "")}
    conn1, native = connect()
    eng1 = engine(conn1)
    obs["schema"] = ensure_schema(eng1)
    reset(eng1, native)
    conn2, _n2 = connect()
    eng2 = engine(conn2)
    conn3, _n3 = connect()
    eng3 = engine(conn3)
    try:
        for n in (A, B, C):
            eng1.create_node(n)
        eng1.create_edge(A, P, B)
        base = eng2.kg_WCC()
        obs["baseline"] = {k: base.get(k) for k in (A, B, C)}
        obs["baseline_c_joined"] = joined(base, C, A)
        obs["token_baseline"] = token(native)
    except Exception as e:  # noqa: BLE001
        obs["setup_error"] = err(e)
    if not obs.get("setup_error"):
        try:
            sql_exec(conn1, "START TRANSACTION")
            eng1.create_edge(C, P, A)  # nested in the caller's open transaction
            obs["token_dirty"] = token(native)
            dirty = eng2.kg_WCC()
            obs["dirty"] = {k: dirty.get(k) for k in (A, B, C)}
            obs["dirty_c_joined"] = joined(dirty, C, A)
            obs["algo_cache_stats_eng2"] = dict(getattr(eng2._store, "_algo_cache_stats", {}) or {})
        except Exception as e:  # noqa: BLE001
            obs["dirty_error"] = err(e)
        finally:
            try:
                sql_exec(conn1, "ROLLBACK")
            except Exception as e:  # noqa: BLE001
                obs["rollback_error"] = err(e)
        obs["rows_c_a_after_rollback"] = len(sql_all(conn3, "SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ?", [C, P, A]))
        obs["token_after_rollback"] = token(native)
        try:
            after = eng3.kg_WCC()
            obs["after"] = {k: after.get(k) for k in (A, B, C)}
            obs["after_c_joined"] = joined(after, C, A)
            obs["algo_cache_stats_eng3"] = dict(getattr(eng3._store, "_algo_cache_stats", {}) or {})
        except Exception as e:  # noqa: BLE001
            obs["after_error"] = err(e)
    sc = self_check()
    v, why = judge(obs)
    if not sc["discriminates"]:
        v, why = "INCONCLUSIVE", f"verdict self-check failed: {sc}"
    finish(NAME, v, why, obs, sc)


if __name__ == "__main__":
    main()
