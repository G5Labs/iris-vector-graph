"""HD-0705 probe: what do the exported search helpers answer, measured against the documented Python read rules?

Contract cited:
- docs/USER_GUIDE.md:463 (blame 9b313a2c / 8e3b4a82): "Python methods that write or read take `graph=`; omitted, they
  mean the default graph, never every graph."
- iris_vector_graph/__init__.py:93,124-125: `TextSearchEngine` and `RRFFusion` are in `__all__`.
- docs/API_REFERENCE.md:9 (f05b4134): the public Python API is the methods of IRISGraphEngine / IRISGraphOperators,
  exceptions and IVG_* variables (the helpers are not listed).
Oracle:
- If the exported helpers are public API under the USER_GUIDE rule, TextSearchEngine readers (which take no `graph`)
  must answer the default graph only, and its document search must reach the IVG Schema's docs table.
- As-built per source: they read every graph (no graph_id predicate) and `search_documents` uses `%FIND(text, ?)` on an
  unqualified `docs` (spec 262 left no SQLUser views), so it cannot answer.
- RRFFusion.fuse_results is pure: recorded for HD-0702 (missing item adds 0).
- HybridSearchFusion: whether it is exported at top level, and whether it scopes its text leg.
Verdict: fail when an exported reader answers another graph's rows for a call that names no graph (USER_GUIDE rule),
noting that whether these exports are under that rule is HD-0705 itself.
Data: graphs `ia-0705a`, `ia-0705b`, ids `ia0705:*`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

GA, GB = "ia-0705a", "ia-0705b"


def main() -> int:
    import iris_vector_graph as ivg
    from iris_vector_graph.fusion import HybridSearchFusion, RRFFusion
    from iris_vector_graph.text_search import TextSearchEngine

    C.obs(step="exports", text_search_in_all="TextSearchEngine" in ivg.__all__, rrf_in_all="RRFFusion" in ivg.__all__,
          hybrid_in_all="HybridSearchFusion" in ivg.__all__, hybrid_top_level=hasattr(ivg, "HybridSearchFusion"))
    c = C.conn()
    e = C.engine(c)
    failures = []
    try:
        for g in (GA, GB):
            e.create_node("ia0705:x", labels=["IA0705"], properties={"name": "ia0705zebra"}, graph=g)
            e.create_node("ia0705:quokka", labels=["IA0705"], properties={"name": "other"}, graph=g)
            e.create_edge("ia0705:x", "IA0705REL", "ia0705:quokka", graph=g)
        c.sql("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", GA, "ia0705:x", "ia0705quagga text")
        t = TextSearchEngine(c.conn, schema="Graph_KG")
        names = t.extract_entity_names("ia0705zebra", k=10)
        quals = t.search_entity_qualifiers("ia0705:quokka", k=10)
        ctx = t.search_with_context("ia0705zebra", k=10)
        C.obs(step="TextSearchEngine_no_graph_arg", extract_entity_names=names, entity_qualifiers=quals,
              with_context=ctx)
        default_graph_nodes = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'ia0705:' AND "
                                    "COALESCE(graph_id, '') = ''")[0][0]
        if (names or quals or ctx) and default_graph_nodes == 0:
            failures.append(f"TextSearchEngine answered named-graph rows ({len(names)} names, {len(quals)} "
                            f"qualifier rows, {len(ctx)} context rows) for calls that name no graph; the default "
                            "graph holds none")
        docs = t.search_documents("ia0705quagga", k=5)
        kg = e.kg_TXT("ia0705quagga", k=5, graph=GA)
        C.obs(step="search_documents_vs_kg_TXT", search_documents=docs, kg_TXT=kg)
        if kg and not docs:
            failures.append("TextSearchEngine.search_documents cannot reach Graph_KG.docs (kg_TXT finds the row)")
        rrf = RRFFusion.fuse_results([[("a", 0.9), ("b", 0.8)], [("b", 3.0)]], c=60)
        C.obs(step="RRFFusion", fused=rrf, missing_contributes_zero=abs(dict(rrf)["a"] - 1 / 61) < 1e-12)
        try:
            h = HybridSearchFusion(e).multi_modal_search(query_text="ia0705quagga", k=5, graph=GA)
            hb = HybridSearchFusion(e).multi_modal_search(query_text="ia0705quagga", k=5, graph=GB)
            C.obs(step="HybridSearchFusion_text_only", graph_a=h, graph_b=hb)
        except Exception as ex:  # noqa: BLE001
            C.obs(step="HybridSearchFusion_text_only", error=str(ex)[:300])
    finally:
        c.sql("DELETE FROM Graph_KG.docs WHERE graph_id IN (?, ?)", GA, GB)
        for g in (GA, GB):
            e.erase_graph(g)
        C.obs(step="cleanup", nodes_left=c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'ia0705:'"),
              docs_left=c.sql("SELECT COUNT(*) FROM Graph_KG.docs WHERE id %STARTSWITH 'ia0705:'"))
        c.close()
    if failures:
        C.verdict("fail", "; ".join(failures))
    else:
        C.verdict("pass", "exported helpers follow the default-graph read rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
