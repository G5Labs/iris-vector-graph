#!/usr/bin/env python3
"""Module 10 live audit of stated refusals (gate 5c-refusals) on AUDITB.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 600 python experiment/playbook-completion/live/breadth-b/10_live_refusals.py

Each X statement of ontology/10-algorithms.md that a public call can trigger is run through the engine (or the
deployed class method it names) on a tiny default-graph fixture b10_a -> b10_b; the expectation is a raise (and, where
the statement says so, a message naming the setting) and no content change (row counts and ^KG("__version") equal
before and after). Statements that need a missing store method (ALG-B5.5, B5.21), a login without write access
(ALG-B9.3), two concurrent rebuilds (ALG-B12.3) or a failing rebuild (ALG-B12.8) are left to source/test evidence.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import gget, session, write_log  # noqa: E402

c10 = importlib.import_module("10_common")


def main():
    log = {"cases": []}
    with session("10-live-refusals") as s:
        eng = s.eng
        log["cleanup_before"] = c10.cleanup_b10(s)
        eng.create_node("b10_a", labels=["B10"])
        eng.create_node("b10_b", labels=["B10"])
        eng.create_edge("b10_a", "B10R", "b10_b")

        def snap():
            return (s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes")[0][0], s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges")[0][0],
                    int(gget(s.c, "__version", root="KG") or 0))

        cases = [
            ("ALG-B1.5", "damping 1.5", lambda: eng.kg_PAGERANK(damping=1.5), "damping"),
            ("ALG-B1.5", "max_iterations 0", lambda: eng.kg_PAGERANK(max_iterations=0), "max_iterations"),
            ("ALG-B1.5", "class method damping 1.5", lambda: s.c.call("Graph.KG.PageRank", "PageRankGlobalJson", "1.5", "20"), None),
            ("ALG-B2.8", "PPR damping 0", lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"], damping_factor=0.0), "damping"),
            ("ALG-B2.8", "ppr alpha 2.0", lambda: eng.ppr("b10_a", alpha=2.0), "alpha"),
            ("ALG-B2.9", "negative reverse weight", lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"], bidirectional=True, reverse_edge_weight=-1.0), "reverse_edge_weight"),
            ("ALG-B2.10", "empty seeds", lambda: eng.kg_PERSONALIZED_PAGERANK([]), None),
            ("ALG-B2.10", "single string seed", lambda: eng.kg_PERSONALIZED_PAGERANK("b10_a"), None),
            ("ALG-B2.10", "non-string seed", lambda: eng.kg_PERSONALIZED_PAGERANK([1]), None),
            ("ALG-B2.2", "graph name '0'", lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"], graph="0"), None),
            ("ALG-B2.13", "exclusions as a string", lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"], exclude_predicates="B10R"), None),
            ("ALG-B2.13", "exclusion with two dots", lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"], exclude_predicates=["a.b.c"]), None),
            ("ALG-B5.3", "degree direction 'sideways'", lambda: eng.degree_centrality(direction="sideways"), "direction"),
            ("ALG-B5.10", "betweenness sample -1", lambda: eng.betweenness_centrality(sample_size=-1), "sample"),
            ("ALG-B5.10", "betweenness max_hops 5000", lambda: eng.betweenness_centrality(max_hops=5000), "hops"),
            ("ALG-B5.17", "closeness formula 'mean'", lambda: eng.closeness_centrality(formula="mean"), "formula"),
            ("ALG-B5.22", "bfs_vector_rerank", lambda: eng.bfs_vector_rerank("b10_a", [0.0, 0.0, 0.0, 1.0]), None),
            ("ALG-B6.7", "leiden gamma 0", lambda: eng.leiden_communities(gamma=0.0), "gamma"),
            ("ALG-B8.10", "PPR-guided subgraph damping 2", lambda: eng.kg_PPR_GUIDED_SUBGRAPH(["b10_a"], damping=2.0), None),
            ("ALG-B10.6", "Dijkstra direction 'up'", lambda: s.c.call("Graph.KG.TraversalPaths", "DijkstraJson", "b10_a", "b10_b", "weight", 9999, 10, "up"), None),
        ]
        for sid, what, op, word in cases:
            before = snap()
            try:
                r = op()
                outcome = {"raised": False, "answer": json.dumps(r, default=str)[:200]}
            except TypeError as e:
                outcome = {"raised": True, "type": "TypeError", "message": str(e)[:300]}
            except Exception as e:  # noqa: BLE001
                outcome = {"raised": True, "type": type(e).__name__, "message": str(e)[:300]}
            after = snap()
            names = (word is None) or (word.lower() in outcome.get("message", "").lower())
            text = outcome.get("answer", "") or ""
            refused_in_band = (not outcome["raised"]) and ("error" in text.lower() or "refus" in text.lower())
            rec = {"statement": sid, "case": what, **outcome, "unchanged": before == after,
                   "names_setting": names, "refused": outcome["raised"] or refused_in_band,
                   "holds": (outcome["raised"] or refused_in_band) and before == after and (names or refused_in_band)}
            log["cases"].append(rec)
            print(sid, what, "->", rec["refused"], rec.get("type"), rec.get("message", rec.get("answer", ""))[:120])
        log["cleanup_after"] = c10.cleanup_b10(s)
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        by = {}
        for c in log["cases"]:
            by.setdefault(c["statement"], []).append(c["holds"])
        log["by_statement"] = {k: all(v) for k, v in by.items()}
        p = write_log(s, log)
        print("by_statement", log["by_statement"], "log", p)


if __name__ == "__main__":
    main()
