#!/usr/bin/env python3
"""F2 route 1: a degree served from the cache after delete_node + re-creation brought the generation back (ABA).

L1 (ADR-0012:12-17, "the cache is derived: Kill it and every answer is still right"; model graph_structure.rs §2
theorem_served_equals_recount): whenever Graph.KG.Adj.Cached answers a number for s, it equals Graph.KG.Adj.Count for s.

Model prediction (witness_aba_delete_and_recreate_serves_stale_degree): a Degree(g, s) call that reads gen k and
counts, then stalls while delete_node(s) commits (RemoveSource kills gen) and later writes bring gen back to k with a
different count, passes its store test (Adj.cls:75) and its re-read (78-80) and stores (k, old count).

This is a STRESS probe: the window is inside one Graph.KG.Adj.Degree call and cannot be scheduled from outside without
changing the product. Many reader processes call Degree on s while one writer alternates two states that both end at
gen 2 — A: {s->a, s->b} (count 2) and B: {} after create+delete of s->c (count 0), each reached from a delete_node(s)
that kills gen. Between rounds the readers pause and the probe compares Cached with Count. A mismatch is
OBSERVED_DEFECT; no mismatch is INCONCLUSIVE (the race was not hit; absence is not evidence). Duration:
G5_PROBE_SECONDS (default 120), readers: G5_PROBE_READERS (default 16).

Public entry points: engine.create_edge / delete_edge / delete_node (writer), Graph.KG.Adj.Degree (the call
iris_vector_graph.stores.lazy_kg makes through the Native API). Observation: Adj.Cached, Adj.Count, ^KG("gen"/"degc").
"""
from __future__ import annotations

import os
import threading
import time

from graph_structure_common import adj_cached, adj_count, connect, engine, ensure_schema, err, finish, index_kind, reset

NAME = "graph_structure_degree_aba"
G = 0  # GraphKey.ForIndex(None): the default graph's ^KG key (model §1)
S, P = "g5aba:s", "G5ABA_T"
SECONDS = float(os.environ.get("G5_PROBE_SECONDS", "120"))
# Community license: each reader is one more connection; the 2026-11-13 run with 16 got none (reader_calls 0)
READERS = int(os.environ.get("G5_PROBE_READERS", "3"))


def gen_of(native):
    v = native.get("^KG", "gen", G, S)
    return None if v is None else int(v)


def degc_of(native):
    try:
        import iris

        v = native.get("^KG", "degc", G, S, "\x01")
        if v is None:
            return None
        lst = iris.IRISList(v)
        return [lst.get(1), lst.get(2)]
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def state_a(eng):
    eng.delete_node(S)
    eng.create_edge(S, P, "g5aba:a")
    eng.create_edge(S, P, "g5aba:b")


def state_b(eng):
    eng.delete_node(S)
    eng.create_edge(S, P, "g5aba:c")
    eng.delete_edge(S, P, "g5aba:c")


def judge(mismatches: list, rounds: int, errors: list, reader_calls: int = 1) -> tuple[str, str]:
    if mismatches:
        m = mismatches[0]
        return "OBSERVED_DEFECT", f"round {m['round']}: Cached answered {m['cached']} while Count is {m['count']} (gen {m['gen']}, degc {m['degc']})"
    if rounds == 0:
        return "INCONCLUSIVE", f"no round completed: {errors[:1]}"
    if reader_calls == 0:
        return "INCONCLUSIVE", f"no reader call ran ({len(errors)} reader errors, e.g. a license limit): the race could not occur"
    return "INCONCLUSIVE", f"no stale entry in {rounds} rounds; the race window was not hit (not evidence of absence)"


def self_check() -> dict:
    bad, _ = judge([{"round": 1, "cached": "2", "count": 0, "gen": 2, "degc": [2, 2]}], 1, [])
    none, _ = judge([], 5, [])
    idle, why = judge([], 5, [], 0)
    return {"mismatch_case": bad, "clean_case": none, "no_reader_case": why,
            "discriminates": bad == "OBSERVED_DEFECT" and none == "INCONCLUSIVE" and "no reader call" in why}


def main() -> None:
    obs = {"probe": NAME, "seconds": SECONDS, "readers": READERS}
    conn, native = connect()
    eng = engine(conn)
    obs["schema"] = ensure_schema(eng)
    reset(eng, native)
    obs["adjacency_index_kind"] = index_kind(native)
    run = threading.Event()
    stop = threading.Event()
    calls = [0] * READERS
    errors: list = []

    def reader(i):
        try:
            _c, nat = connect()
        except Exception as e:  # noqa: BLE001
            errors.append(err(e))
            return
        while not stop.is_set():
            if not run.wait(0.05):
                continue
            try:
                nat.classMethodValue("Graph.KG.Adj", "Degree", G, S, "")
                calls[i] += 1
            except Exception as e:  # noqa: BLE001
                if len(errors) < 20:
                    errors.append(err(e))

    threads = [threading.Thread(target=reader, args=(i,), daemon=True) for i in range(READERS)]
    for t in threads:
        t.start()
    mismatches: list = []
    rounds = 0
    t0 = time.time()
    try:
        state_a(eng)
        while time.time() - t0 < SECONDS:
            run.set()
            (state_b if rounds % 2 == 0 else state_a)(eng)
            time.sleep(0.002)
            run.clear()
            time.sleep(0.02)  # let in-flight Degree calls finish before observing
            rounds += 1
            cached = adj_cached(native, G, S)
            count = adj_count(native, G, S)
            if cached not in ("", None) and not str(cached).startswith("error") and int(cached) != count:
                mismatches.append({"round": rounds, "cached": cached, "count": count, "gen": gen_of(native), "degc": degc_of(native)})
                break
    except Exception as e:  # noqa: BLE001
        errors.append(err(e))
    finally:
        stop.set()
        run.set()
        for t in threads:
            t.join(timeout=5)
    obs.update({"rounds": rounds, "reader_calls": sum(calls), "mismatches": mismatches, "errors": errors[:20]})
    sc = self_check()
    v, why = judge(mismatches, rounds, errors, sum(calls))
    if not sc["discriminates"]:
        v, why = "INCONCLUSIVE", f"verdict self-check failed: {sc}"
    finish(NAME, v, why, obs, sc)


if __name__ == "__main__":
    main()
