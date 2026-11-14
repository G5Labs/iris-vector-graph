#!/usr/bin/env python3
"""O5 / F1 — does erase_graph leave a BM25 index's answers for the erased graph?

Model: search.rs witness_erase_leaves_bm25 (W-O5); repair theorem theorem_repaired_erase_removes_answers.
L1 (ADR-0004 "removes graph content from every store that holds it"; GraphStores.cls "no answer outlives
erased content"; Eraser.cls:138-144 on the BM25 corpus): after erase_graph(g) commits, a search of the
index built for g returns none of g's erased nodes, and erased text never scores for a node re-created
with the same id.

Drives only public entry points: create_node, bm25_build, bm25_search, bm25_info, erase_graph, bm25_drop.
"""
from search_common import connect, engine, ensure_schema, reset, say

G = "g5probe_bm25_erase"
IX = "g5pbm25erase"
NODE = "g5p:erase:1"
WORD = "zyxwortle"


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    data = {"schema": ensure_schema(eng)}
    reset(eng, native)
    try:
        eng.bm25_drop(IX)
    except Exception:
        pass
    data["created"] = eng.create_node(NODE, labels=["Doc"], properties={"name": f"{WORD} quorble"}, graph=G)
    data["build"] = eng.bm25_build(IX, ["name"], graph=G)
    before = eng.bm25_search(IX, WORD, 5)
    data["search_before"] = before
    if not any(i == NODE for i, _ in before):
        say("search_bm25_erase", "INCONCLUSIVE", f"the index did not answer {NODE} before the erase: {before}", data)
        return 0
    data["erase_removed"] = eng.erase_graph(G)
    data["node_exists_after"] = eng.node_exists(NODE, graph=G)
    after = eng.bm25_search(IX, WORD, 5)
    data["search_after"] = after
    data["info_after"] = eng.bm25_info(IX)
    # the same id comes back in the same graph with other text
    data["recreated"] = eng.create_node(NODE, labels=["Doc"], properties={"name": "plain other words"}, graph=G)
    after_recreate = eng.bm25_search(IX, WORD, 5)
    data["search_after_recreate"] = after_recreate
    eng.bm25_drop(IX)
    reset(eng, native)

    # expected from L1, independently of the implementation: no erased node is answered
    expected_after = []
    stale = [i for i, _ in after if i == NODE]
    stale_recreated = [i for i, _ in after_recreate if i == NODE]
    data["expected_after"] = expected_after
    if data["node_exists_after"]:
        say("search_bm25_erase", "INCONCLUSIVE", "the node still exists after erase_graph", data)
    elif stale or stale_recreated:
        say("search_bm25_erase", "OBSERVED_DEFECT",
            f"after erase_graph({G!r}) bm25_search({IX!r}, {WORD!r}) still answers {NODE} "
            f"({after}); after re-creating {NODE} with other text the erased text still scores it ({after_recreate})", data)
    else:
        say("search_bm25_erase", "OBSERVED_AS_EXPECTED", f"no erased node answered after erase_graph ({after})", data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
