"""HD-0601 probe: after erase_graph(g), do the IVF, VecIndex and PLAID indexes still answer g's node ids?

Contracts cited:
- CONTEXT.md:198-200 Erasure: "The removal of graph content from every store that holds it"; ADR-0004 lists the
  stores (rows, ^KG, temporal index, ^NKG, ledger live indexes) and names no vector index.
- docs/USER_GUIDE.md:443: "`erase_graph` removes one graph's content from every store (rows, `^KG`, the temporal index)".
- Graph.KG.GraphStores.cls:1-16, 20: "the one declared inventory of stores holding graph content"; it lists
  graph-blind stores with reasons, and lists no ^IVF / ^VecIdx / ^PLAID entry.
- docs/ADMIN_GUIDE.md:322 (inventory row): "^BM25Idx, ^VecIdx, ^IVF, ^PLAID ... made by their *_build calls ...
  yes: only if you build one ... yes, or rebuild them from the tables".
- vector.py ivf_build docstring: "Build an IVF index over one graph's vectors" (graph-derived by construction);
  vec_insert / plaid_build take caller-supplied ids and vectors (caller-fed).

Oracle: build an IVF index from graph ia-0601's routed vectors (ivf_build(graph=...)), a VecIndex and a PLAID index
fed with the same graph's node ids and vectors; erase_graph; search each with a node's own vector.
- Erased ids still returned (and vectors still stored) -> as-built: the indexes are outside erasure (reading (b),
  undocumented), F-0606 reproduced live.
- Nothing returned / index gone -> inside erasure (reading (a)).
Cleanup: drops its own three indexes; erases its own graph (which drops its route table).
"""
from __future__ import annotations

import _common as C

G = "ia-0601"
IVF, VEC, PLD = "ia0601ivf", "ia0601vec", "ia0601plaid"
VECS = {
    "ia0601:n1": [1.0, 0.0, 0.0, 0.0],
    "ia0601:n2": [0.9, 0.1, 0.0, 0.0],
    "ia0601:n3": [0.0, 1.0, 0.0, 0.0],
    "ia0601:n4": [0.0, 0.0, 1.0, 0.0],
    "ia0601:n5": [0.0, 0.0, 0.0, 1.0],
    "ia0601:n6": [0.5, 0.5, 0.0, 0.0],
}


def drop_all(e):
    for fn, n in ((e.ivf_drop, IVF), (e.vec_drop, VEC), (e.plaid_drop, PLD)):
        try:
            fn(n)
        except Exception as ex:  # noqa: BLE001
            C.obs(drop_error=f"{n}: {ex}")


def ids(res):
    out = []
    for r in res:
        if isinstance(r, dict):
            out.append(r.get("id") or r.get("doc_id") or r.get("node_id"))
        elif isinstance(r, (list, tuple)):
            out.append(r[0])
    return out


def main() -> None:
    c = C.conn()
    e = C.engine(c)
    try:
        e.erase_graph(G)
        drop_all(e)
        for n, v in VECS.items():
            e.create_node(n, graph=G)
            e.store_embedding(n, v, graph=G)
        route_tables = c.sql("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ?", G)
        C.obs(step="setup", route=route_tables)
        info = e.ivf_build(IVF, nlist=2, graph=G)
        e.vec_create_index(VEC, dim=4, num_trees=2, leaf_size=2)
        for n, v in VECS.items():
            e.vec_insert(VEC, n, v)
        e.vec_build(VEC)
        e.plaid_build(PLD, [{"id": n, "tokens": [v, v]} for n, v in VECS.items()], n_clusters=2)
        q = VECS["ia0601:n1"]
        before = {"ivf": ids(e.ivf_search(IVF, q, k=3, nprobe=2)),
                  "vec": ids(e.vec_search(VEC, q, k=3)),
                  "plaid": ids(e.plaid_search(PLD, [q], k=3, nprobe=2))}
        C.obs(step="before-erase", ivf_info=info, results=before,
              ivf_cfg_table=c.o.get("^IVF", IVF, "cfg", "table"))

        removed = e.erase_graph(G)
        rows_left = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", G)[0][0]
        route_after = c.sql("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ?", G)
        after = {"ivf": ids(e.ivf_search(IVF, q, k=3, nprobe=2)),
                 "vec": ids(e.vec_search(VEC, q, k=3)),
                 "plaid": ids(e.plaid_search(PLD, [q], k=3, nprobe=2))}
        stored = {"ivf_vectors": sum(1 for _ in _iter_ivf(c)),
                  "vecidx_defined": int(c.o.isDefined("^VecIdx", VEC)),
                  "plaid_defined": int(c.o.isDefined("^PLAID", PLD))}
        C.obs(step="after-erase", removed=removed, node_rows_left=rows_left, route_after=route_after, results=after,
              stored=stored, ivf_cfg_table=c.o.get("^IVF", IVF, "cfg", "table"))
        erased = set(VECS)
        leaked = {k: [i for i in v if i in erased] for k, v in after.items()}
        C.obs(step="summary", erased_ids_still_answered=leaked)
        if any(leaked.values()):
            C.verdict("fail", "erase_graph left IVF/VecIndex/PLAID answering the erased graph's node ids: "
                      + ", ".join(f"{k}={len(v)}" for k, v in leaked.items()))
        else:
            C.verdict("pass", "no index answered an erased id")
    finally:
        try:
            drop_all(e)
            e.erase_graph(G)
        finally:
            c.close()


def _iter_ivf(c):
    cell = ""
    while True:
        cell = c.o.nextSubscript(False, "^IVF", IVF, "list", cell)
        if cell is None or cell == "":
            return
        nid = ""
        while True:
            nid = c.o.nextSubscript(False, "^IVF", IVF, "list", cell, nid)
            if nid is None or nid == "":
                break
            yield nid


if __name__ == "__main__":
    main()
