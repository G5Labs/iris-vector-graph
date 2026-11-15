"""HD-0703 probe: does kg_TXT use a BM25 index named "default" (spec 044 FR-012 / US5 / SC-004)?

Contract cited:
- specs/044-bm25-index/spec.md:158 FR-012 (Status: Draft): "When kg_TXT falls back to LIKE, it MUST first check
  $Data(^BM25Idx("default","cfg","N")) > 0; if true, it MUST call BM25Index.Search("default", query, k) instead".
- spec.md:114-122 US5, :254 SC-004; upstream PR #8 body (merged 2026-04-10): "Automatic kg_TXT upgrade when "default"
  BM25 index exists".
- iris_vector_graph/_engine/vector.py:925-947 (kg_TXT docstring at the pin): iFind path scores occurrence counts; the
  LIKE fallback "for a namespace with no iFind index" scores 1.0 and warns.
Oracle, with docs rows and same-text nodes in graph ia-0703 and a BM25 index literally named "default" built over
ia-0703 (public engine API; the docs rows are written with SQL INSERT, as the product's own e2e tests do):
- Path taken: a WARNING "falling back to LIKE" marks the LIKE path; otherwise the iFind path answered.
- FR-012 honoured (on the LIKE path): kg_TXT answers BM25 floats equal to bm25_search("default", q, k).
- FR-012 not implemented: LIKE scores 1.0 regardless of the default index.
- On the iFind path FR-012's precondition is false and the run cannot decide FR-012 (result `incomplete`).
- Graph scope: kg_TXT(graph=None) must not answer ia-0703's documents through a "default" index built for ia-0703.
Data: graph `ia-0703`, ids `ia0703:*`, BM25 index `default` (asserted absent first, dropped afterwards).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

G = "ia-0703"
DOCS = {"ia0703:d1": "diabetes mellitus diabetes", "ia0703:d2": "insulin resistance and diabetes in a longer text",
        "ia0703:d3": "rheumatoid arthritis"}


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage()[:300])


def main() -> int:
    c = C.conn()
    e = C.engine(c)
    cap = Capture()
    logging.getLogger("iris_vector_graph").addHandler(cap)
    if c.o.isDefined("^BM25Idx", "default"):
        C.verdict("blocked", "a BM25 index named default already exists in AUDITIA; not touched")
        c.close()
        return 0
    built_default = False
    outcome = None
    try:
        for nid, text in DOCS.items():
            e.create_node(nid, labels=["IA0703"], properties={"name": text}, graph=G)
            c.sql("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", G, nid, text)
        cap.records.clear()
        r1 = e.kg_TXT("diabetes", k=5, graph=G)
        like1 = any("falling back to LIKE" in m for m in cap.records)
        C.obs(step="kg_TXT_before_default_index", rows=r1, like_path=like1, warnings=cap.records[:3])

        C.obs(step="bm25_build_default", result=e.bm25_build("default", ["name"], graph=G))
        built_default = True
        bm = e.bm25_search("default", "diabetes", k=5)
        cap.records.clear()
        r2 = e.kg_TXT("diabetes", k=5, graph=G)
        like2 = any("falling back to LIKE" in m for m in cap.records)
        C.obs(step="kg_TXT_with_default_index", rows=r2, like_path=like2, bm25_default=bm, warnings=cap.records[:3])
        cap.records.clear()
        r3 = e.kg_TXT("diabetes", k=5)  # default graph
        C.obs(step="kg_TXT_default_graph", rows=r3, leaked_ia0703=[r for r in r3 if str(r[0]).startswith("ia0703:")],
              warnings=cap.records[:3])
        same_as_bm25 = sorted((n, round(s, 6)) for n, s in r2) == sorted((n, round(s, 6)) for n, s in bm)
        if like2:
            outcome = ("pass", "LIKE path consulted the default BM25 index") if same_as_bm25 else (
                "fail", "LIKE path answered 1.0 scores although a BM25 index named default exists (FR-012 absent)")
        else:
            outcome = ("incomplete", "iFind path answered (occurrence counts); FR-012's precondition (LIKE fallback) "
                       f"is not reached on this deployment; scores {r2} unchanged by the default index: "
                       f"{sorted(r1) == sorted(r2)}; default-graph call leaked ia-0703 rows: "
                       f"{bool([r for r in r3 if str(r[0]).startswith('ia0703:')])}")
    finally:
        if built_default:
            e.bm25_drop("default")
        c.sql("DELETE FROM Graph_KG.docs WHERE graph_id = ?", G)
        e.erase_graph(G)
        C.obs(step="cleanup", default_defined=c.o.isDefined("^BM25Idx", "default"),
              docs_left=c.sql("SELECT COUNT(*) FROM Graph_KG.docs WHERE graph_id = ?", G),
              nodes_left=c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", G))
        c.close()
    C.verdict(*outcome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
