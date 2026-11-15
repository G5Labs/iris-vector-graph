#!/usr/bin/env python3
"""Module 07 (text search and fusion) live checks on AUDITB, lane B.

    python experiment/playbook-completion/live/breadth-b/07_live.py <check> [<check> ...]   (or: all)

Every check runs inside blive.session (lane-B AUDITB lock), uses only the pin's public Python API, deployed class
methods and SQL a caller would issue, writes scratch data under graphs b07g* / node ids b07_* / BM25 index names b07*,
and removes it before the session ends. Each check writes $RUN_DIR/breadth-b/live/07-<check>.json with its
observations and a verdict: "defect-reproduced" (the product violated the cited contract), "holds" (the contract held)
or "inconclusive".
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import capture, gget, gsubs, session, write_log, J  # noqa: E402

G1, G2, G3 = "b07g1", "b07g2", "b07g3"


def bm25_state(c, name):
    """Abstract ^BM25Idx(name) state: header, number of doc/len records, df agreement (read-only)."""
    hdr = {k: gget(c, name, "cfg", k, root="BM25Idx") for k in ("N", "totalLen", "vocab_size", "schema", "graph", "upgrading")}
    docs = gsubs(c, "BM25Idx", name, "doc")
    lens = {d: int(gget(c, name, "len", d, root="BM25Idx") or 0) for d in gsubs(c, "BM25Idx", name, "len")}
    df = {t: int(gget(c, name, "df", t, root="BM25Idx") or 0) for t in gsubs(c, "BM25Idx", name, "df")}
    tf_terms = gsubs(c, "BM25Idx", name, "tf")
    df_from_tf = {t: len(gsubs(c, "BM25Idx", name, "tf", t)) for t in tf_terms}
    return {"header": hdr, "doc_records": len(docs), "len_records": len(lens), "sum_len": sum(lens.values()),
            "df_terms": len(df), "df_mismatch": sorted(t for t in set(df) | set(df_from_tf) if df.get(t, 0) != df_from_tf.get(t, 0)),
            "exists": bool(c.o.isDefined("BM25Idx", name))}


def cleanup(s, names=(), graphs=()):
    for n in names:
        try:
            s.eng.bm25_drop(n)
        except Exception:
            pass
    for g in graphs:
        try:
            s.eng.erase_graph(g)
        except Exception:
            pass
        try:
            s.c.sql("DELETE FROM Graph_KG.docs WHERE graph_id = ?", g)
        except Exception:
            pass


def seed(s, graph, items):
    """items: [(node_id, text)] -> nodes with property name=text in `graph`, plus a docs row for kg_TXT."""
    for nid, text in items:
        s.eng.create_node(nid, labels=["B07Doc"], properties={"name": text}, graph=graph)
        s.c.sql("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", graph, nid, text)


# ------------------------------------------------------------------ footprints (journal oracle)
def fp_writers():
    name = "b07fp"
    with session("07-fp-writers") as s:
        cleanup(s, [name], [G1])
        seed(s, G1, [("b07_a", "alpha beta gamma"), ("b07_b", "beta delta"), ("b07_c", "gamma epsilon zeta")])
        out = {}

        def rec(label, op):
            cap = capture(s, op)
            out[label] = {"result": cap.result, "error": cap.error, "footprint": cap.footprint_json(),
                          "transactions": cap.txn_summary(s.smap), "outside_txn": cap.writes_outside_txn(s.smap),
                          "nodes_written": sorted({r["g"].split(",")[1] if r["g"].count(",") >= 1 else r["g"] for r in cap.records if r["g"]})[:40],
                          "n_records": len([r for r in cap.records if r["g"]]), "seconds": round(cap.seconds, 3)}
            return cap

        rec("Build", lambda: s.eng.bm25_build(name, ["name"], graph=G1))
        out["state_after_build"] = bm25_state(s.c, name)
        rec("Search", lambda: s.eng.bm25_search(name, "beta", k=5))
        rec("SearchReport", lambda: s.eng.bm25_search(name, "beta gamma", k=5, max_df_fraction=0.5, report=True))
        rec("Insert-new", lambda: s.eng.bm25_insert(name, "b07_d", "eta theta beta"))
        rec("Insert-replace", lambda: s.eng.bm25_insert(name, "b07_d", "iota"))
        rec("Delete", lambda: s.eng.bm25_delete(name, "b07_d"))
        rec("Delete-absent", lambda: s.eng.bm25_delete(name, "b07_zz"))
        rec("Upgrade-schema2", lambda: s.eng.bm25_upgrade(name))
        rec("Info", lambda: s.eng.bm25_info(name))
        out["state_before_drop"] = bm25_state(s.c, name)
        rec("Drop", lambda: s.eng.bm25_drop(name))
        out["state_after_drop"] = bm25_state(s.c, name)
        rec("Insert-missing-index", lambda: s.eng.bm25_insert("b07fpi", "b07_x", "kappa lambda"))
        out["state_insert_created"] = bm25_state(s.c, "b07fpi")
        rec("Drop-insert-created", lambda: s.eng.bm25_drop("b07fpi"))
        # Search's stopword write: Drop("__stop__") (accepted, F-0706) then a Search of an existing index (it
        # tokenizes; a Search of a missing index returns before tokenizing) re-creates the list
        s.eng.bm25_build("b07fps", ["name"], graph=G1)
        stop_before = len(gsubs(s.c, "BM25Idx", "__stop__"))
        rec("Drop-__stop__", lambda: s.eng.bm25_drop("__stop__"))
        stop_mid = len(gsubs(s.c, "BM25Idx", "__stop__"))
        rec("Search-missing-index-after-stopdrop", lambda: s.eng.bm25_search("b07none", "the beta", k=3))
        stop_mid2 = len(gsubs(s.c, "BM25Idx", "__stop__"))
        rec("Search-rebuilds-stopwords", lambda: s.eng.bm25_search("b07fps", "the beta", k=3))
        stop_after = len(gsubs(s.c, "BM25Idx", "__stop__"))
        out["stopwords"] = {"before": stop_before, "after_drop": stop_mid, "after_search_missing_index": stop_mid2,
                            "after_search_existing_index": stop_after}
        cleanup(s, [name, "b07fpi", "b07fps"], [G1])
        out["cleanup_state"] = {"b07fp": bm25_state(s.c, name)["exists"], "b07fpi": bm25_state(s.c, "b07fpi")["exists"]}
        p = write_log(s, out)
        print(p)
        return out


# ------------------------------------------------------------------ F-0704
def f0704():
    name = "b07h"
    with session("07-f0704-refused-build-destroys") as s:
        cleanup(s, [name], [G1])
        seed(s, G1, [("b07_a", "alpha beta"), ("b07_b", "beta gamma")])
        info0 = s.eng.bm25_build(name, ["name"], graph=G1)
        before = bm25_state(s.c, name)
        eng2 = s.engine_on(s.c, embedding_dimension=4)  # fresh registry: knows b07h from BM25Index.List
        err = None
        try:
            eng2.index(name).build(properties=["no_such_property"], graph=G1)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        after = bm25_state(s.c, name)
        search_after = s.eng.bm25_search(name, "beta", k=5)
        verdict = "defect-reproduced" if (err and before["doc_records"] > 0 and after["doc_records"] < before["doc_records"]) else (
            "holds" if after == before else "inconclusive")
        out = {"build_before": info0, "state_before": before, "refused_rebuild_error": err, "state_after": after,
               "search_after": search_after, "verdict": verdict,
               "contract": "TXT-X2 / SYS-I3: a refused build leaves the old index as it was"}
        cleanup(s, [name], [G1])
        print(write_log(s, out))
        return out


# ------------------------------------------------------------------ F-0702 and F-0703
def f0702_f0703():
    with session("07-f0702-f0703-erase-and-stale") as s:
        cleanup(s, ["b07e", "b07s"], [G2, G1])
        seed(s, G2, [("b07_e1", "secretword tenant two"), ("b07_e2", "secretword again")])
        s.eng.bm25_build("b07e", ["name"], graph=G2)
        before = s.eng.bm25_search("b07e", "secretword", k=5)
        cap = capture(s, lambda: s.eng.erase_graph(G2))
        rows_left = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", G2)[0][0]
        after = s.eng.bm25_search("b07e", "secretword", k=5)
        term_left = bool(s.c.o.isDefined("BM25Idx", "b07e", "df", "secretword"))
        f0702 = {"search_before_erase": before, "erase_result": cap.result, "erase_error": cap.error,
                 "erase_footprint": cap.footprint_json(), "bm25_written_by_erase": any("BM25Idx" in x for v in cap.footprint.values() for x in v),
                 "graph_nodes_left": rows_left, "search_after_erase": after, "term_still_in_index": term_left,
                 "info_after": s.eng.bm25_info("b07e"),
                 "verdict": "defect-reproduced" if (after and rows_left == 0) else "holds",
                 "contract": "TXT-I8, ADR-0004, GraphStores.cls:113-115: erasure removes content from every store"}
        # F-0703: delete a node; the index still answers it, Info has no staleness signal
        seed(s, G1, [("b07_s1", "stalephrase one"), ("b07_s2", "other words")])
        s.eng.bm25_build("b07s", ["name"], graph=G1)
        info_before = s.eng.bm25_info("b07s")
        s.eng.delete_node("b07_s1", graph=G1)
        s.c.sql("DELETE FROM Graph_KG.docs WHERE graph_id = ? AND id = ?", G1, "b07_s1")
        node_left = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ? AND node_id = ?", G1, "b07_s1")[0][0]
        hits = s.eng.bm25_search("b07s", "stalephrase", k=5)
        info_after = s.eng.bm25_info("b07s")
        f0703 = {"info_before": info_before, "node_rows_left": node_left, "search_after_delete": hits,
                 "info_after": info_after, "info_unchanged": info_before == info_after,
                 "verdict": "defect-reproduced" if (node_left == 0 and hits and info_before == info_after) else "holds",
                 "contract": "TXT-I6 / SYS-I8: a derived store matches its sources or says it is out of date"}
        cleanup(s, ["b07e", "b07s"], [G2, G1])
        out = {"F-0702": f0702, "F-0703": f0703}
        print(write_log(s, out))
        return out


# ------------------------------------------------------------------ F-0705 and F-0707
def f0705_f0707():
    with session("07-f0705-f0707-graph-scope") as s:
        cleanup(s, ["b07i", "b07g2idx", "b07g1idx"], [G1, G2, G3])
        # F-0705: an index created by a first Insert records no graph; its doc is graph G3's node
        seed(s, G3, [("b07_n3", "zebracrossing in graph three")])
        s.eng.bm25_insert("b07i", "b07_n3", "zebracrossing in graph three")
        info_i = s.eng.bm25_info("b07i")
        has_graph_sub = bool(s.c.o.isDefined("BM25Idx", "b07i", "cfg", "graph"))
        eng2 = s.engine_on(s.c, embedding_dimension=4)
        idx_graph = eng2._index_graph("b07i", "bm25")
        pick = eng2._fusion_leg_index(("bm25",), "")
        fused = eng2.kg_RRF_FUSE(k=5, k1=5, k2=5, c=60, query_vector="[0.1,0.2,0.3,0.4]", query_text="zebracrossing", graph=None)
        # the same call with a vector the route refuses: the vector leg's exception also drops the text leg (F-0709)
        fused_badvec = eng2.kg_RRF_FUSE(k=5, k1=5, k2=5, c=60, query_vector="[]", query_text="zebracrossing", graph=None)
        cy = eng2.execute_cypher("CALL ivg.bm25.search('b07i', 'zebracrossing', 5) YIELD node, score RETURN node, score")
        default_has = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE COALESCE(graph_id,'') = '' AND node_id = ?", "b07_n3")[0][0]
        f0705 = {"info": info_i, "cfg_graph_subscript_defined": has_graph_sub, "engine_index_graph": idx_graph,
                 "default_graph_leg_pick": pick, "default_graph_fusion": fused,
                 "fusion_with_refused_vector": fused_badvec,
                 "cypher_rows": cy.rows, "cypher_error": cy.error, "cypher_sql": cy.sql, "node_in_default_graph": default_has,
                 "verdict": "defect-reproduced" if (idx_graph == "" and any(r[0] == "b07_n3" for r in fused) and default_has == 0) else "holds",
                 "contract": "TXT-B8.3: an index whose graph is not known is never taken as the default graph's own index"}
        # F-0707: under USE GRAPH g1, a BM25 call on g2's index answers g2's node ids
        seed(s, G2, [("b07_g2a", "pineapple only in graph two")])
        seed(s, G1, [("b07_g1a", "banana only in graph one")])
        s.eng.bm25_build("b07g2idx", ["name"], graph=G2)
        r = s.eng.execute_cypher("USE GRAPH 'b07g1' CALL ivg.bm25.search('b07g2idx', 'pineapple', 5) YIELD node, score RETURN node, score")
        f0707 = {"rows": r.rows, "error": r.error, "sql": r.sql,
                 "verdict": "defect-reproduced" if (r.rows and any("b07_g2a" in str(x) for x in r.rows)) else (
                     "holds" if r.error else "inconclusive"),
                 "contract": "TXT-I7 / SYS-I2: with a graph in scope, BM25 calls answer only from an index built for that graph"}
        # retrieve under USE GRAPH with another graph's index
        r2 = s.eng.execute_cypher("USE GRAPH 'b07g1' CALL ivg.retrieve('pineapple', 5, 'b07g2idx') YIELD node, score RETURN node, score")
        f0707["retrieve_rows"] = r2.rows
        f0707["retrieve_error"] = r2.error
        cleanup(s, ["b07i", "b07g2idx"], [G1, G2, G3])
        out = {"F-0705": f0705, "F-0707": f0707}
        print(write_log(s, out))
        return out


# ------------------------------------------------------------------ F-0706
def f0706():
    with session("07-f0706-stopword-node") as s:
        cleanup(s, ["b07w", "__stop__"], [G1])
        seed(s, G1, [("b07_w1", "doc tf len cfg df words"), ("b07_w2", "plain words here")])
        s.eng.bm25_build("b07w", ["name"], graph=G1)
        hits_before = {t: s.eng.bm25_search("b07w", t, k=5) for t in ("doc", "tf", "len", "plain")}
        build_stop = None
        try:
            build_stop = s.eng.bm25_build("__stop__", ["name"], graph=G1)
        except Exception as e:
            build_stop = f"refused: {type(e).__name__}: {e}"
        info_stop = s.eng.bm25_info("__stop__")
        list_names = str(s.c.call("Graph.KG.BM25Index", "List"))
        stop_has_the = bool(s.c.o.isDefined("BM25Idx", "__stop__", "the"))
        stop_tf_node = int(s.c.o.isDefined("BM25Idx", "__stop__", "tf"))
        # rebuild b07w now that "__stop__" also holds index nodes: words named like index subscripts are stopwords
        s.eng.bm25_build("b07w", ["name"], graph=G1)
        hits_after = {t: s.eng.bm25_search("b07w", t, k=5) for t in ("doc", "tf", "len", "plain")}
        st = bm25_state(s.c, "b07w")
        # Drop("__stop__") deletes the stopword list; the next Tokenize rebuilds it
        s.eng.bm25_drop("__stop__")
        after_drop = len(gsubs(s.c, "BM25Idx", "__stop__"))
        s.eng.bm25_search("b07w", "plain", k=1)
        after_search = len(gsubs(s.c, "BM25Idx", "__stop__"))
        lost = [t for t in ("doc", "tf", "len") if hits_before[t] and not hits_after[t]]
        out = {"hits_before": hits_before, "build___stop__": build_stop, "info___stop__": info_stop,
               "List()": list_names, "stoplist_has_the": stop_has_the, "$Data(^BM25Idx(__stop__,tf))": stop_tf_node,
               "hits_after_stop_build": hits_after, "b07w_state_after": st,
               "stopword_nodes_after_drop": after_drop, "stopword_nodes_after_next_search": after_search,
               "words_lost_namespace_wide": lost,
               "verdict": "defect-reproduced" if (isinstance(build_stop, dict) and lost) else "inconclusive",
               "contract": "HD-0704 working assumption: reserve __stop__; reject it at public index-management entry points"}
        cleanup(s, ["b07w"], [G1])
        print(write_log(s, out))
        return out


# ------------------------------------------------------------------ F-0709
def f0709():
    with session("07-f0709-fusion-legs") as s:
        cleanup(s, ["b07f"], [G1])
        seed(s, G1, [("b07_f1", "mango fruit"), ("b07_f2", "mango tree")])
        eng2 = s.engine_on(s.c, embedding_dimension=4)
        # engine kg_RRF_FUSE for a graph that has docs but no BM25 index: no error, no text leg
        fused_no_index = eng2.kg_RRF_FUSE(k=5, k1=5, k2=5, c=60, query_vector="[0.1,0.2,0.3,0.4]", query_text="mango", graph=G1)
        txt = eng2.kg_TXT("mango", k=5, graph=G1)
        # HybridSearchFusion: a failing vector leg (malformed vector) is logged and dropped; the text leg answers
        from iris_vector_graph.fusion import HybridSearchFusion
        hs = HybridSearchFusion(eng2)
        mm_err, mm = None, None
        try:
            mm = hs.multi_modal_search(query_vector="not-a-vector", query_text="mango", k=5, graph=G1)
        except Exception as e:
            mm_err = f"{type(e).__name__}: {e}"
        modes = sorted({m["mode"] for r in (mm or []) for m in r["search_modes"]})
        out = {"engine_fusion_without_text_index": fused_no_index, "kg_TXT_same_query": txt,
               "multi_modal_with_bad_vector": {"error": mm_err, "results": mm, "modes": modes},
               "verdict": "defect-reproduced" if ((not fused_no_index and txt) or (mm and "vector" not in modes)) else "holds",
               "contract": "TXT-B13.7 (the fused search raises and names the leg), TXT-B17.3, spec 044 US7 scenario 9"}
        cleanup(s, ["b07f"], [G1])
        print(write_log(s, out))
        return out


# ------------------------------------------------------------------ F-0711
def f0711():
    with session("07-f0711-textsearchengine") as s:
        cleanup(s, [], [G1, G2])
        seed(s, G1, [("b07_t1", "quokka graph one")])
        seed(s, G2, [("b07_t2", "quokka graph two")])
        from iris_vector_graph.text_search import TextSearchEngine
        tse = TextSearchEngine(s.c.conn)
        names = tse.extract_entity_names("quokka", k=10)
        ctx = tse.search_with_context("quokka", k=10)
        docs = tse.search_documents("quokka", k=10)
        graphs_seen = sorted({str(x[0]) for x in names})
        out = {"extract_entity_names": names, "search_with_context": ctx, "search_documents": docs,
               "ids_from_both_graphs": sorted(graphs_seen),
               "verdict": "defect-reproduced" if ({"b07_t1", "b07_t2"} <= {str(x[0]) for x in names}) else "inconclusive",
               "contract": "TXT-B19.1 / SYS-I2: its searches answer from one graph only"}
        cleanup(s, [], [G1, G2])
        print(write_log(s, out))
        return out


CHECKS = {"fp": fp_writers, "f0704": f0704, "f0702": f0702_f0703, "f0705": f0705_f0707, "f0706": f0706,
          "f0709": f0709, "f0711": f0711}

if __name__ == "__main__":
    which = sys.argv[1:] or ["all"]
    if which == ["all"]:
        which = list(CHECKS)
    for w in which:
        r = CHECKS[w]()
        print(w, json.dumps({k: (v.get("verdict") if isinstance(v, dict) else None) for k, v in r.items()} if "verdict" not in r else r["verdict"]))
