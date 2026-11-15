#!/usr/bin/env python3
"""Module 10 live checks of the shared result cache on AUDITB (F-1004, candidate F-C1001, token facts).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 600 python experiment/playbook-completion/live/breadth-b/10_live_cache.py

Default graph scratch: b10_a -> b10_b (an edge, so the adjacency index is not empty), edgeless b10_x / b10_y.
1. Token facts: does an edgeless node create/delete move ^KG("__version") (the cache token)?
2. F-1004: kg_PERSONALIZED_PAGERANK(["b10_x"]) before b10_x exists is cached; create_node("b10_x") with no edge;
   the same call is answered from the cache; a fresh computation (after AlgoCache.InvalidateAll, the pin's own
   invalidation) answers differently. Then the reverse: delete the edgeless start node after a cached answer.
3. F-C1001: global PageRank's cache key holds the node token COUNT(*):MAX(%ID) read BEFORE the lookup
   (_engine/algorithms.py:784-792). The interleaving "token read; node y created; compute + Put; y deleted" is driven
   with the same store call the engine makes (store.execute_pagerank(..., loners=..., node_token=<token read before
   y was created>)); then an ordinary kg_PAGERANK() call is checked against a fresh computation.
Everything b10_ is removed and the cache invalidated (AlgoCache.InvalidateAll) at the end.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import capture, gget, session, write_log  # noqa: E402

c10 = importlib.import_module("10_common")


def ver(s):
    return int(gget(s.c, "__version", root="KG") or 0)


def cache_entries(s):
    out = {}
    try:
        it = s.c.o.iterator("IVG.AlgoCache")
        for g in it.subscripts():
            it2 = s.c.o.iterator("IVG.AlgoCache", g)
            for alg in it2.subscripts():
                it3 = s.c.o.iterator("IVG.AlgoCache", g, alg)
                out.setdefault(str(g), {})[str(alg)] = sum(1 for _ in it3.subscripts())
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)
    return out


def main():
    log = {"steps": []}

    def step(name, **kw):
        log["steps"].append({"step": name, **kw})
        print(name, json.dumps(kw, default=str)[:400])

    with session("10-live-cache") as s:
        eng = s.eng
        log["state_before"] = c10.state(s)
        log["cleanup_before"] = c10.cleanup_b10(s)
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        eng.create_node("b10_a", labels=["B10"])
        eng.create_node("b10_b", labels=["B10"])
        eng.create_edge("b10_a", "B10R", "b10_b")
        # 1. token facts
        v0 = ver(s)
        eng.create_node("b10_x")
        v1 = ver(s)
        eng.delete_node("b10_x")
        v2 = ver(s)
        eng.create_node("b10_x", labels=["B10"])
        v3 = ver(s)
        eng.delete_node("b10_x")
        v4 = ver(s)
        eng.create_edge("b10_b", "B10R", "b10_a")
        v5 = ver(s)
        step("token-facts", after_edge_setup=v0, edgeless_create=v1, edgeless_delete=v2, labelled_create=v3,
             labelled_delete=v4, edge_create=v5,
             node_writes_move_token=(v1 != v0 or v2 != v1 or v3 != v2 or v4 != v3), edge_write_moves_token=(v5 != v4))

        # 2. F-1004: an edgeless start node written after the answer was cached
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        r_before = eng.kg_PERSONALIZED_PAGERANK(["b10_x"])
        ent1 = cache_entries(s)
        cap = capture(s, lambda: eng.create_node("b10_x"))
        r_cached = eng.kg_PERSONALIZED_PAGERANK(["b10_x"])
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        r_fresh = eng.kg_PERSONALIZED_PAGERANK(["b10_x"])
        step("F-1004-create", before_x_exists=r_before, cache_entries=ent1,
             create_node_footprint=cap.footprint_json(), token_moved_by_create=bool(cap.records and any(
                 "__version" in r["g"] for r in cap.records)),
             cached_answer_after_create=r_cached, fresh_answer=r_fresh, stale_served=(r_cached != r_fresh))
        # reverse: delete the edgeless start node after its answer was cached
        r_with = eng.kg_PERSONALIZED_PAGERANK(["b10_x"])  # cached now (fresh run above stored it)
        eng.delete_node("b10_x")
        r_after_delete = eng.kg_PERSONALIZED_PAGERANK(["b10_x"])
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        r_fresh2 = eng.kg_PERSONALIZED_PAGERANK(["b10_x"])
        step("F-1004-delete", cached_with_x=r_with, cached_answer_after_delete=r_after_delete, fresh_answer=r_fresh2,
             stale_served=(r_after_delete != r_fresh2))

        # 3. F-C1001: node token ABA for global PageRank (the R313 key)
        from iris_vector_graph._edgeless import edgeless as edgeless_of
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        tok = eng._node_set_token()
        eng.create_node("b10_y")  # newest row id, edgeless
        tok_with_y = eng._node_set_token()
        res = eng._store.execute_pagerank(0.85, 20, loners=lambda: edgeless_of(eng._loners()), node_token=tok)
        rows_put = [r[0] for r in res.rows]
        eng.delete_node("b10_y")
        tok_after = eng._node_set_token()
        r_pr_cached = [r[0] for r in eng.kg_PAGERANK()]
        stats = dict(getattr(eng._store, "_algo_cache_stats", {}))
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        r_pr_fresh = [r[0] for r in eng.kg_PAGERANK()]
        step("F-C1001-aba", token_read_before=tok, token_with_y=tok_with_y, token_after_delete=tok_after,
             token_returned=(tok == tok_after), rows_stored_under_old_token=sorted(rows_put),
             kg_PAGERANK_after_delete=sorted(r_pr_cached), fresh=sorted(r_pr_fresh), cache_stats=stats,
             stale_served=(sorted(r_pr_cached) != sorted(r_pr_fresh)))

        # cleanup
        log["cleanup_after"] = c10.cleanup_b10(s)
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        log["state_after"] = c10.state(s)
        tf = log["steps"][0]
        log["verdict"] = {
            "F-1004": "reproduced" if log["steps"][1]["stale_served"] else "not-reproduced",
            "F-1004-delete": "reproduced" if log["steps"][2]["stale_served"] else "not-reproduced",
            "F-C1001": "reproduced" if log["steps"][3]["stale_served"] else "not-reproduced",
            "node_writes_move_token": tf["node_writes_move_token"],
        }
        p = write_log(s, log)
        print("verdict", log["verdict"], "log", p)


if __name__ == "__main__":
    main()
