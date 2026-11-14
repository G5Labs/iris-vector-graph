#!/usr/bin/env python3
"""Live drive of the decoders and status maps of modules 07, 10 and 18 (gate 3.5-decoders), namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/decoders/live_decoders.py 07|10|18

Each case calls the producer through the product's real entry point twice: once raw (the ObjectScript class method
the client calls, over the Native API, or the SQL / HTTP surface) and once through the product's Python decoder,
and compares what the decoder yields with what the server said. A case `match`es when the decoded value equals the
wire value under the decoder's documented contract; otherwise it names the mismatch and the finding. Setup and
cleanup use the product's own API (create_node, bm25_build, ..., bm25_drop / vec_drop / plaid_drop) and the
product's EraseAll/PurgeAll (rxlib.Lane.reset). Nothing is compiled; no product file is changed.
Results: $RUN_DIR/refusals/decoders/<module>/live-<module>.json.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import traceback
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from rxlib import Lane, rollback_all  # noqa: E402

CASES: List[Dict[str, Any]] = []


def case(module: str, decoder: str, name: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    t0 = time.time()
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001  (a harness error is recorded, not a product result)
        r = {"match": None, "harness_error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-2500:]}
    r = {"module": module, "decoder": decoder, "case": name, "seconds": round(time.time() - t0, 3), **r}
    CASES.append(_jsonable(r))
    flag = {True: "OK ", False: "MIS", None: "ERR"}[r.get("match")]
    print(f"[{flag}] {module} {decoder[:38]:<38} {name[:70]:<70} {r.get('why', r.get('harness_error', ''))[:150]}",
          flush=True)
    return r


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        if isinstance(v, dict):
            return {str(k): _jsonable(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_jsonable(x) for x in v]
        return repr(v)[:2000]


def raised(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "type": type(e).__name__, "message": str(e)[:600]}


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(f"{record.levelname}:{record.name}:{record.getMessage()[:400]}")


# ================================================================================================== module 07
def m07(L: Lane) -> None:
    e = L.eng
    o = L.c.o
    call = L.c.call
    G = "rxdg"
    ids = ["rxd:a", "rxd:.5x", "rxd,.7y", "rxd[.9z", "rxd:b"]
    created = {}
    for i in ids:
        created[i] = raised(lambda i=i: e.create_node(i, labels=["RXD"], properties={"name": f"zebra {i} stripes"},
                                                      graph=G))
    e.create_node("rxd:c", labels=["RXD"], properties={"name": "lion"}, graph=G)
    L.c.conn.commit()
    made = [i for i in ids if created[i]["ok"] and created[i]["value"]]
    CASES.append({"module": "07", "case": "setup nodes", "created": created, "made": made})

    # --- Build: answer vs Info
    def build():
        ans = e.bm25_build("rxdidx", ["name"], graph=G)
        raw_info = str(call("Graph.KG.BM25Index", "Info", "rxdidx"))
        info = json.loads(raw_info)
        same = (ans.get("indexed") == info.get("N") and ans.get("graph") == info.get("graph") == G
                and abs(float(ans.get("avgdl")) - float(info.get("avgdl"))) < 1e-9
                and ans.get("vocab_size") == info.get("vocab_size"))
        return {"wire_info": raw_info, "decoded_build": ans, "match": same,
                "why": f"build answer {ans} vs Info {info}"}
    case("07", "bm25_build <- Build", "build answer agrees with the stored index (Info)", build)

    # --- Info on a built index, absent index, insert-made index
    def info_built():
        raw = str(call("Graph.KG.BM25Index", "Info", "rxdidx"))
        dec = e.bm25_info("rxdidx")
        e._index_graph_scopes.pop("rxdidx", None)
        g = e._index_graph("rxdidx", "bm25")
        ok = {k: v for k, v in dec.items() if k != "type"} == json.loads(raw) and dec.get("type") == "bm25" and g == G
        return {"wire": raw, "decoded": dec, "index_graph": g, "match": ok, "why": f"graph decoded {g!r}"}
    case("07", "bm25_info/_index_graph <- Info", "index built for graph rxdg", info_built)

    def info_absent():
        raw = str(call("Graph.KG.BM25Index", "Info", "rxd_absent"))
        dec = e.bm25_info("rxd_absent")
        g = e._index_graph("rxd_absent", "bm25")
        ok = raw == "{}" and dec == {"type": "bm25"} and g is None
        return {"wire": raw, "decoded": dec, "index_graph": g, "match": ok,
                "why": f"absent index: wire {raw}, decoded {dec}, graph {g!r} (None = unknown)"}
    case("07", "bm25_info/_index_graph <- Info", "absent index", info_absent)

    def info_insert_made():
        r = e.bm25_insert("rxdins", "rxd:a", "zebra stripes")
        recorded = int(o.isDefined("BM25Idx", "rxdins", "cfg", "graph"))
        raw = str(call("Graph.KG.BM25Index", "Info", "rxdins"))
        e._index_graph_scopes.pop("rxdins", None)
        g = e._index_graph("rxdins", "bm25")
        wire_graph = json.loads(raw).get("graph")
        # contract (TXT-B8.3, the cell's remaining: "Info answers null for an absent graph"): no recorded graph is
        # unknown (None), never the default graph ''
        ok = recorded == 0 and wire_graph is None and g is None
        return {"insert": r, "graph_subscript_defined": recorded, "wire": raw, "index_graph": g, "match": ok,
                "finding": None if ok else "F-0705",
                "why": f"no graph recorded ($Data={recorded}); Info answers graph {wire_graph!r}; "
                       f"_index_graph decodes {g!r} (the default graph)"}
    case("07", "bm25_info/_index_graph <- Info", "index made by bm25_insert (no recorded graph)", info_insert_made)

    # --- Search: raw JSON vs bm25_search vs Cypher (JSON_TABLE)
    def search():
        raw = str(call("Graph.KG.BM25Index", "Search", "rxdidx", "zebra", 10))
        wire = json.loads(raw)  # valid JSON: the server writes the leading 0
        dec = e.bm25_search("rxdidx", "zebra", k=10)
        wire_pairs = [(r["id"], float(r["score"])) for r in wire]
        cy = raised(lambda: e.execute_cypher(
            "USE GRAPH 'rxdg' CALL ivg.bm25.search('rxdidx', 'zebra', 10) YIELD node, score RETURN node.node_id, score"))
        cy_rows = None
        if cy["ok"]:
            res = cy["value"]
            cy_rows = [list(r) for r in getattr(res, "rows", res)]
        mism = [(w, d) for w, d in zip(wire_pairs, dec) if w[0] != d[0] or abs(w[1] - d[1]) > 1e-12]
        leading_dot_in_wire = bool(re.search(r'"score":-?\.', raw))
        ok = not mism and len(dec) == len(wire_pairs)
        cy_ids = sorted(r[0] for r in cy_rows) if cy_rows else None
        return {"wire": raw, "decoded": dec, "cypher": cy_rows if cy["ok"] else cy, "mismatches": mism,
                "cypher_ids_equal_wire_ids": cy_ids == sorted(w[0] for w in wire_pairs) if cy_ids else None,
                "wire_score_leading_dot": leading_dot_in_wire, "match": ok,
                "why": f"{len(mism)} of {len(wire_pairs)} rows decoded differently: {mism}"}
    r = case("07", "bm25_search _parse <- Search", "ids containing ':.5', ',.7', '[.9' and scores", search)

    def report():
        raw = str(call("Graph.KG.BM25Index", "SearchReport", "rxdidx", "zebra stripes", 10, 0.5))
        wire = json.loads(raw)
        dec = e.bm25_search("rxdidx", "zebra stripes", k=10, max_df_fraction=0.5, report=True)
        wp = [(x["id"], float(x["score"])) for x in wire["results"]]
        ok = (dec["skipped"] == wire["skipped"] and dec["fallback"] == bool(wire["fallback"])
              and [p[0] for p in dec["results"]] == [p[0] for p in wp])
        return {"wire": raw, "decoded": dec, "match": ok,
                "why": f"skipped {dec['skipped']} vs {wire['skipped']}; fallback {dec['fallback']} vs {wire['fallback']}; "
                       f"ids equal {[p[0] for p in dec['results']] == [p[0] for p in wp]}"}
    case("07", "bm25_search(report) <- SearchReport", "skipped terms and fallback flag", report)

    # --- Upgrade answers (pass-through)
    def upgrade():
        out = {}
        for name in ("rxd_absent", "rxdidx"):
            raw_d = e.bm25_upgrade(name)
            out[name] = raw_d
        ok = out["rxd_absent"] == {"upgraded": 0, "missing": 1} and out["rxdidx"] == {"upgraded": 0, "already": 1}
        return {"decoded": out, "match": ok,
                "why": f"absent -> {out['rxd_absent']} (the docstring lists only upgraded/already), "
                       f"schema 2 -> {out['rxdidx']}"}
    case("07", "bm25_upgrade <- Upgrade", "absent and schema-2 answers", upgrade)

    # --- Insert / Delete integer answers
    def ins_del():
        n0 = int(json.loads(str(call("Graph.KG.BM25Index", "Info", "rxdidx")))["N"])
        a = e.bm25_insert("rxdidx", "rxd:new", "zebra herd")
        n1 = int(json.loads(str(call("Graph.KG.BM25Index", "Info", "rxdidx")))["N"])
        b = e.bm25_insert("rxdidx", "rxd:stop", "the and of")
        c = e.bm25_delete("rxdidx", "rxd:new")
        d = e.bm25_delete("rxdidx", "rxd:none")
        f = e.bm25_delete("rxd_absent", "x")
        n2 = int(json.loads(str(call("Graph.KG.BM25Index", "Info", "rxdidx")))["N"])
        ok = (a is True and n1 == n0 + 1 and b is False and c is True and d is False and f is False and n2 == n0)
        return {"insert_tokens": a, "insert_stopwords_only": b, "delete_present": c, "delete_missing": d,
                "delete_absent_index": f, "N": [n0, n1, n2], "match": ok, "why": f"N {n0}->{n1}->{n2}"}
    case("07", "bm25_insert/delete <- Insert/Delete", "integer answers to bool", ins_del)

    # --- List: comma-joined names
    def listing():
        r1 = e.bm25_insert("rxd,comma", "rxd:a", "zebra")
        r2 = e.bm25_insert(" rxdspace", "rxd:a", "zebra")
        raw = str(call("Graph.KG.BM25Index", "List"))
        e._index_registry_cache = None if hasattr(e, "_index_registry_cache") else None
        reg = e._build_index_registry()
        bm = sorted(k for k, v in reg.items() if v == "bm25")
        real = sorted(n for n in ("rxdidx", "rxdins", "rxd,comma", " rxdspace"))
        missing = [n for n in real if n not in reg]
        phantom = [n for n in bm if n not in real]
        from rxlib import engine as _mk_engine
        fresh = _mk_engine(L.c)
        listed = raised(lambda: sorted(n for n, t in fresh._index_registry.items() if t == "bm25"))
        ok = not missing
        return {"inserts": [r1, r2], "wire": raw, "registry_bm25": bm, "missing_from_registry": missing,
                "phantom_names": phantom, "fresh_engine_registry_bm25": listed, "match": ok,
                "why": f"List answers {raw!r}; the registry has {bm}; real indexes missing {missing}; phantoms {phantom}"}
    case("07", "_build_index_registry <- List", "index names holding the separator or a leading space", listing)

    # --- control character in the graph name
    def control_char():
        b = raised(lambda: e.bm25_build("rxdctl", ["name"], graph="rxd\tg"))
        stored = o.get("BM25Idx", "rxdctl", "cfg", "graph")
        raw = str(call("Graph.KG.BM25Index", "Info", "rxdctl"))
        parse = raised(lambda: json.loads(raw))
        info = raised(lambda: e.bm25_info("rxdctl"))
        e._index_graph_scopes.pop("rxdctl", None)
        g = e._index_graph("rxdctl", "bm25")
        ok = b["ok"] and info["ok"] and g == "rxd\tg"
        return {"build": b, "stored_graph": stored, "wire": raw, "json_loads": parse, "bm25_info": info,
                "index_graph": g, "match": ok,
                "why": f"build -> {b.get('type', 'ok')}: {b.get('message', '')[:80]}; Info wire not JSON: "
                       f"{not parse['ok']}; _index_graph -> {g!r}"}
    case("07", "bm25_build/bm25_info <- Build/Info", "graph name with a tab", control_char)

    # --- kg_TXT: which path, what scores
    def kg_txt():
        cur = L.c.conn.cursor()
        idx = L.c.sql("SELECT COUNT(*) FROM %Dictionary.CompiledIndex WHERE parent %STARTSWITH 'Graph.KG' "
                      "AND Name = 'idxdocstextifind'")
        idx2 = L.c.sql("SELECT Name, parent FROM %Dictionary.CompiledIndex WHERE Name %STARTSWITH 'idx' "
                       "AND Name [ 'ifind'")
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)",
                    [G, "rxd:a", "zebra zebra zebra stripes"])
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", [G, "rxd:b", "one zebra"])
        L.c.conn.commit()
        cur.close()
        cap = LogCapture()
        lg = logging.getLogger("iris_vector_graph")
        lg.addHandler(cap)
        lg.setLevel(logging.DEBUG)
        try:
            res = raised(lambda: e.kg_TXT("zebra", k=10, graph=G))
        finally:
            lg.removeHandler(cap)
        warn = [r for r in cap.records if "kg_TXT" in r]
        path = "like-fallback" if any("falling back to LIKE" in w for w in warn) else "ifind"
        scores = dict(res["value"]) if res["ok"] else None
        if path == "ifind":
            ok = bool(scores) and abs(scores.get("rxd:a", 0) - 3.0) < 1e-9 and abs(scores.get("rxd:b", 0) - 1.0) < 1e-9
            why = f"iFind path: tf scores {scores} (a: 3 occurrences, b: 1)"
        else:
            ok = bool(scores) and all(abs(v - 1.0) < 1e-12 for v in scores.values())
            why = f"LIKE fallback (warning logged): every score 1.0 as documented: {scores}"
        return {"ifind_index": [idx, idx2], "result": res, "log": warn, "path": path, "match": ok, "why": why}
    case("07", "kg_TXT error-text map / row decoder", "docs rows of graph rxdg", kg_txt)

    for name in ("rxdidx", "rxdins", "rxd,comma", " rxdspace", "rxdctl"):
        try:
            e.bm25_drop(name)
        except Exception:  # noqa: BLE001
            pass


# ================================================================================================== module 10
def m10(L: Lane) -> None:
    e = L.eng
    call = L.c.call
    # default graph: a->b->c->a, c->largest, d alone; chain x1->x2->x3->x4 for a non-converging WCC
    for n in ("a", "b", "c", "largest", "d", "x1", "x2", "x3", "x4"):
        e.create_node(f"rxd{n}" if n != "largest" else "largest", labels=["RXD"], properties={"name": n})
    for s, o in (("a", "b"), ("b", "c"), ("c", "a"), ("c", "largest"), ("x1", "x2"), ("x2", "x3"), ("x3", "x4")):
        e.create_edge(f"rxd{s}", "R", "largest" if o == "largest" else f"rxd{o}")
    L.c.conn.commit()

    def ppr():
        raw = str(call("Graph.KG.PageRank", "RunJson", json.dumps(["rxda"]), "0.85", "100", "0", "1.0", ""))
        wire = {r["id"]: float(r["score"]) for r in json.loads(raw)}
        dec = e.kg_PERSONALIZED_PAGERANK(["rxda"], damping_factor=0.85, max_iterations=100)
        st = e._store.execute_ppr(["rxda"], 0.85, 100)
        st_rows = {r[0]: float(r[1]) for r in st.rows}
        diff = {k: (wire[k], dec.get(k)) for k in wire if dec.get(k) is None or abs(dec[k] - wire[k]) > 1e-9}
        extra = {k: v for k, v in dec.items() if k not in wire}
        ok = not diff and all(v == 0 for v in extra.values()) and st_rows == wire and st.error is None
        return {"wire": raw, "decoded": dec, "store_rows": st.rows, "store_error": st.error, "diff": diff,
                "unscored_added": extra, "match": ok,
                "why": f"{len(wire)} scored rows; differences {diff}; zero rows added for unscored nodes {sorted(extra)}"}
    case("10", "_scored_node_rows <- PageRank.RunJson", "personalized PageRank from rxda", ppr)

    def pagerank():
        from iris_vector_graph._edgeless import edgeless as _edgeless_of
        edgeless = _edgeless_of(e._loners())
        raw = str(call("Graph.KG.PageRank", "PageRankGlobalJson", "0.85", "20",
                       *((json.dumps(edgeless),) if edgeless else ())))
        wire = [(r["id"], float(r["score"])) for r in json.loads(raw)]
        dec = e.kg_PAGERANK()
        wd = dict(wire)
        diff = [(k, v, wd.get(k)) for k, v in dec if wd.get(k) is None or abs(wd[k] - v) > 1e-9]
        ok = not diff and len(dec) == len(wire)
        return {"edgeless": edgeless, "wire": raw, "decoded": dec, "diff": diff, "match": ok,
                "why": f"{len(wire)} wire rows, {len(dec)} decoded; differences {diff}"}
    case("10", "_scored_node_rows <- PageRankGlobalJson", "global PageRank of the default graph", pagerank)

    def wcc():
        raw = str(call("Graph.KG.Algorithms", "WCCJson"))
        wire = json.loads(raw)
        st = e._store._execute_wcc()
        dec = e.kg_WCC()
        node_largest_in_wire = "largest" in wire
        engine_ok = all(dec.get(k) == v for k, v in wire.items())
        store_ok = st.error is None and {r[0]: r[1] for r in st.rows} == wire
        return {"wire": raw, "store_rows": st.rows, "store_error": st.error, "engine": dec,
                "wire_has_node_named_largest": node_largest_in_wire, "engine_matches_wire": engine_ok,
                "store_matches_wire": store_ok, "match": engine_ok and store_ok,
                "why": f"store decoder: {'ok' if store_ok else 'error ' + str(st.error)}; engine answer equals wire: "
                       f"{engine_ok} (falls back to WCCJson)"}
    case("10", "_membership_rows <- Algorithms.WCCJson", "a default-graph node named 'largest'", wcc)

    def cdlp():
        raw = str(call("Graph.KG.Algorithms", "CDLPJson", 10))
        wire = json.loads(raw)
        st = e._store._execute_cdlp(10)
        dec = e.kg_CDLP(10)
        engine_ok = all(dec.get(k) == v for k, v in wire.items())
        store_ok = st.error is None and {r[0]: r[1] for r in st.rows} == wire
        return {"wire": raw, "store_rows": st.rows, "store_error": st.error, "engine": dec,
                "engine_matches_wire": engine_ok, "store_matches_wire": store_ok, "match": engine_ok and store_ok,
                "why": f"store decoder: {'ok' if store_ok else 'error ' + str(st.error)}; engine equals wire: {engine_ok}"}
    case("10", "_membership_rows <- Algorithms.CDLPJson", "a default-graph node named 'largest'", cdlp)

    def wcc_limit():
        raw = raised(lambda: str(call("Graph.KG.Algorithms", "WCCJson", 1)))
        st = e._store.execute_wcc(max_iterations=1)
        dec = raised(lambda: e.kg_WCC(max_iterations=1))
        ok = (not raw["ok"]) and st.error and (not dec["ok"]) and "converge" in dec.get("message", "")
        return {"wire": raw, "store_error": st.error, "engine": dec, "match": bool(ok),
                "why": f"server throws: {not raw['ok']}; store error set: {bool(st.error)}; engine raises "
                       f"{dec.get('type')}: {dec.get('message', '')[:100]} (ALG-I5: no empty answer)"}
    case("10", "ALG-I5 store error -> exception", "WCC with max_iterations=1 on a 4-node chain", wcc_limit)

    def subgraph():
        raw = str(call("Graph.KG.Subgraph", "SubgraphJson", json.dumps(["rxda"]), 2, "", 100))
        wire = json.loads(raw)
        sg = e.kg_SUBGRAPH(["rxda"], k_hops=2)
        we = sorted((x["s"], x["p"], x["o"]) for x in wire["edges"])
        ok = (sorted(sg.nodes) == sorted(wire["nodes"]) and sorted(sg.edges) == we
              and sg.node_properties == wire["properties"] and sg.node_labels == wire["labels"])
        return {"wire": raw, "decoded": {"nodes": sg.nodes, "edges": sg.edges, "properties": sg.node_properties,
                                         "labels": sg.node_labels}, "match": ok,
                "why": f"nodes {len(sg.nodes)}/{len(wire['nodes'])}, edges {len(sg.edges)}/{len(we)}"}
    case("10", "_subgraph_payload <- Subgraph.SubgraphJson", "2 hops from rxda", subgraph)

    def degree():
        raw = str(call("Graph.KG.Centrality", "DegreeCentralityJson", "out", "", 10000))
        wire = [[r["id"], float(r["score"]), int(r["degree"])] for r in json.loads(raw)]
        st = e._store.execute_degree_centrality("out", "", 10000)
        ok = st.error is None and [list(r) for r in st.rows] == wire
        return {"wire": raw, "store_rows": st.rows, "store_error": st.error, "match": ok,
                "why": f"{len(wire)} wire rows; store rows equal: {ok}"}
    case("10", "execute_degree_centrality <- DegreeCentralityJson", "out-degree, default graph", degree)

    def khop():
        raw = str(call("Graph.KG.Traversal", "BFSFastJson", "rxda", "", 2, "", "out"))
        wire = json.loads(raw)
        dec = e.khop("rxda", hops=2)
        ok = dec["edges"] == wire and dec["nodes"][0] == "rxda"
        return {"wire": raw, "decoded": dec, "match": ok, "why": f"{len(wire)} edges; decoded edges equal wire: {dec['edges'] == wire}"}
    case("10", "khop <- Traversal.BFSFastJson", "2 hops out of rxda", khop)

    def missing_texts():
        from iris_vector_graph._engine.algorithms import _runjson_missing
        out = {}
        for cls, m in (("Graph.KG.PageRankRXD", "RunJson"), ("Graph.KG.PageRank", "RunJsonRXD"),
                       ("Graph.KG.CentralityRXD", "DegreeCentralityJson")):
            try:
                call(cls, m)
                out[f"{cls}.{m}"] = {"raised": False}
            except Exception as exc:  # noqa: BLE001
                s = str(exc)
                out[f"{cls}.{m}"] = {"raised": True, "type": type(exc).__name__, "text": s[:300],
                                     "runjson_missing": _runjson_missing(exc),
                                     "degree_fallback_token": ("CLASS DOES NOT EXIST" in s or "DBSRV" in s)}
        a = out["Graph.KG.PageRankRXD.RunJson"]
        b = out["Graph.KG.PageRank.RunJsonRXD"]
        c = out["Graph.KG.CentralityRXD.DegreeCentralityJson"]
        fmt_class = a["raised"] and "<CLASS DOES NOT EXIST>" in a["text"] and "*Graph.KG.PageRankRXD" in a["text"]
        fmt_method = b["raised"] and "<METHOD DOES NOT EXIST>" in b["text"] and "*RunJsonRXD,Graph.KG.PageRank" in b["text"]
        ok = (fmt_class and fmt_method and a["runjson_missing"] is False and b["runjson_missing"] is False
              and c["degree_fallback_token"] is True)
        return {"texts": out, "class_text_format_as_the_regex_assumes": fmt_class,
                "method_text_format_as_the_regex_assumes": fmt_method, "match": ok,
                "why": "the driver writes '<CLASS DOES NOT EXIST> ... *<class>' and '<METHOD DOES NOT EXIST> ... "
                       "*<method>,<class>', the shapes _RUNJSON_MISSING keys on; near-miss names do not match; the "
                       f"degree fallback token is present for a missing class: {c['degree_fallback_token']}"}
    case("10", "error-text maps (_RUNJSON_MISSING, degree fallback)", "driver error text for a missing class/method",
         missing_texts)

    def native_reader():
        from iris_vector_graph import arno_readers  # noqa: F401
        st = raised(lambda: str(call("Graph.KG.ArnoAccel", "PageRankNativeJson", "0.85", "20")))
        return {"arno_call": st, "match": None if not st["ok"] else True,
                "why": "Native Reader producers (ArnoAccel *NativeJson) need libarno_callout.so (absent for x86_64, "
                       f"F-1001): {st.get('message', 'answered')[:160]}"}
    r = case("10", "_scored_node_rows <- ArnoAccel (Native Reader)", "Arno producers", native_reader)
    if r.get("match") is None:
        CASES[-1]["blocked"] = "libarno_callout.so for x86_64 (F-1001; versions/AVAILABILITY.md)"


# ================================================================================================== module 18
def _table_rows(L: Lane, table: str):
    cur = L.c.conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table}")
        cols = [d[0].lower() for d in cur.description]
        rows = cur.fetchall()
    finally:
        cur.close()
    skip = {"edge_id", "reification_id", "label_id", "prop_id", "val_key", "id"} if table != "Graph_KG.docs" else {"val_key"}
    out = []
    for r in rows:
        out.append({c: (repr(type(v).__name__), str(v)) for c, v in zip(cols, r) if c not in skip})
    return sorted(out, key=lambda d: json.dumps(d, sort_keys=True))


def _global_values(L: Lane, gname: str, prefix=()):
    o = L.c.o
    out = {}

    def walk(subs):
        sub = o.nextSubscript(False, gname, *subs, "")
        while sub is not None and sub != "":
            ns = list(subs) + [sub]
            d = int(o.isDefined(gname, *ns))
            if d in (1, 11):
                if gname in ("^IVF", "^PLAID", "^VecIdx"):
                    v = str(L.c.call("Graph.KG.Snapshot", "NodeValueJSON", gname, json.dumps(ns)))
                    out[json.dumps(ns)] = ("server-json", v)
                else:
                    try:
                        v = o.get(gname, *ns)
                        out[json.dumps(ns)] = (type(v).__name__, v if isinstance(v, (int, float, str)) else repr(v))
                    except Exception as exc:  # noqa: BLE001
                        out[json.dumps(ns)] = ("unreadable", str(exc)[:80])
            if d >= 10:
                walk(ns)
            sub = o.nextSubscript(False, gname, *subs, sub)
    walk(list(prefix))
    return out


def m18(L: Lane) -> None:
    e = L.eng
    o = L.c.o
    out_dir = L.out
    G = "rxdg"
    e.create_node("rxd:a", labels=["RXD"], properties={"name": "a", "code": "007", "ratio": "1.50"}, graph=G)
    e.create_node("rxd:b", labels=["RXD"], properties={"name": "b"}, graph=G)
    e.create_node("rxd:c", labels=["RXD"], properties={"name": "c"})
    e.create_edge("rxd:a", "R", "rxd:b", weight=0.5, qualifiers={"since": 2020, "note": "x"}, graph=G)
    e.create_edge_temporal("rxd:a", "T", "rxd:b", timestamp=1_700_000_000,
                           attrs={"amount": 20, "rate": 0.5, "neg": -0.25, "tag": "x"}, graph=G)
    e.store_embedding("rxd:a", [0.1, -0.5, 0.25, 1.0], metadata={"m": 1}, graph=G)
    vec = raised(lambda: (e.vec_create_index("rxdvec", 4), e.vec_insert("rxdvec", "rxd:a", [0.1, -0.5, 0.25, 1.0]),
                          e.vec_insert("rxdvec", "rxd:b", [1.0, 0.0, 0.0, 0.5])))
    plaid = raised(lambda: e.plaid_build("rxdplaid", [{"id": "rxd:a", "tokens": [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]},
                                                       {"id": "rxd:b", "tokens": [[0.9, 0.1, 0.2, 0.3]]}],
                                         n_clusters=2, dim=4))
    L.c.conn.commit()
    CASES.append({"module": "18", "case": "setup", "vec_index": vec, "plaid_index": plaid})
    attrs_before = e.get_edge_attrs(1_700_000_000, "rxd:a", "T", "rxd:b", graph=G)
    tables = ["Graph_KG.nodes", "Graph_KG.rdf_edges", "Graph_KG.rdf_labels", "Graph_KG.rdf_props",
              "Graph_KG.kg_NodeEmbeddings", "Graph_KG.embedding_registry"]
    before_rows = {t: _table_rows(L, t) for t in tables}
    gl = ["^KG", "^VecIdx", "^PLAID", "^IVG.GraphMode", "^IVG.TemporalStructural"]
    before_g = {g: _global_values(L, g) for g in gl}
    path = str(out_dir / "rxd-decoders.snapshot")
    if os.path.exists(path):
        os.unlink(path)
    saved = e.save_snapshot(path)
    with zipfile.ZipFile(path) as z:
        meta = json.loads(z.read("metadata.json"))
        names = z.namelist()
        lines = {n: [json.loads(x) for x in z.read(n).decode().splitlines() if x.strip()]
                 for n in names if n.startswith("globals/")}

    def meta_case():
        info = e.snapshot_info(path)
        ok = (info["metadata"] == meta and info["tables"] == meta["tables"] and info["layout"] == meta["layout"]
              and info["snapshot_ts"] == meta["created_ts"] and info["globals"] == meta["globals"]
              and info["version"] == meta["version"] and info["has_vector_sql"] == meta["has_vector_sql"]
              and saved["snapshot_ts"] == meta["created_ts"] and saved["tables"] == meta["tables"])
        return {"metadata": meta, "snapshot_info": {k: v for k, v in info.items() if k != "metadata"},
                "save_answer": saved, "match": ok,
                "why": "snapshot_info's fields equal metadata.json's, and save's answer agrees"}
    case("18", "snapshot_info <- metadata.json", "a fresh archive", meta_case)

    def vec_lines():
        vl = lines.get("globals/VecIdx.ndjson", []) + lines.get("globals/PLAID.ndjson", [])
        forms = sorted({next((k for k in ("vec", "list") if k in x), "v") for x in vl})
        return {"forms": forms, "n_lines": len(vl), "sample": vl[:3], "match": True if vl else None,
                "why": f"vector-global archive line forms {forms}"}
    case("18", "global value line <- NodeValueJSON", "forms written for ^VecIdx/^PLAID", vec_lines)

    # replacing restore after the product's own erase (inside restore)
    restored = e.restore_snapshot(path)
    L.c.conn.commit()
    after_rows = {t: _table_rows(L, t) for t in tables}
    after_g = {g: _global_values(L, g) for g in gl}
    attrs_after = e.get_edge_attrs(1_700_000_000, "rxd:a", "T", "rxd:b", graph=G)

    def tables_case():
        diffs = {}
        for t in tables:
            b, a = before_rows[t], after_rows[t]
            if b != a:
                bset = {json.dumps(x, sort_keys=True) for x in b}
                aset = {json.dumps(x, sort_keys=True) for x in a}
                diffs[t] = {"only_before": sorted(bset - aset)[:5], "only_after": sorted(aset - bset)[:5]}
        return {"restore": restored, "diffs": diffs, "match": not diffs,
                "why": f"tables whose rows (column type, text) differ after a replacing restore: {sorted(diffs)}"}
    case("18", "SQL row encoder/decoder (ndjson rows)", "save, replacing restore: every row's columns", tables_case)

    def globals_case():
        diffs = {}
        for g in gl:
            b, a = before_g[g], after_g[g]
            keys = sorted(set(b) | set(a))
            d = {k: {"before": b.get(k), "after": a.get(k)} for k in keys if b.get(k) != a.get(k)}
            if d:
                diffs[g] = dict(list(d.items())[:12])
                diffs[g]["__count__"] = len(d)
        type_only = {g: [k for k, v in d.items() if k != "__count__" and v["before"] and v["after"]
                         and v["before"][0] != v["after"][0] and str(v["before"][1]) == str(v["after"][1])]
                     for g, d in diffs.items()}
        return {"diffs": diffs, "type_changes_same_text": type_only, "edge_attrs_before": attrs_before,
                "edge_attrs_after": attrs_after, "match": not diffs,
                "finding": "F-1804" if any(type_only.values()) else None,
                "why": f"globals with changed nodes {sorted(diffs)}; of which value type only (int->str): "
                       f"{ {g: len(v) for g, v in type_only.items()} }; edge attrs {attrs_before} -> {attrs_after}"}
    case("18", "global value line (plain 'v' form) <- str(value)", "save, replacing restore: ^KG and vector globals",
         globals_case)

    def table_missing():
        from iris_vector_graph._engine.snapshot import _table_missing
        cur = L.c.conn.cursor()
        try:
            cur.execute("SELECT * FROM Graph_KG.rxd_no_such_table")
            exc = None
        except Exception as x:  # noqa: BLE001
            exc = x
        finally:
            cur.close()
        rollback_all(L.c.conn)
        cur = L.c.conn.cursor()
        try:
            cur.execute("SELECT no_such_column FROM Graph_KG.nodes")
            exc2 = None
        except Exception as x:  # noqa: BLE001
            exc2 = x
        finally:
            cur.close()
        rollback_all(L.c.conn)
        a = exc is not None and _table_missing(exc)
        b = exc2 is not None and not _table_missing(exc2)
        return {"missing_table_text": str(exc)[:300], "missing_table_mapped": a,
                "other_error_text": str(exc2)[:300], "other_error_mapped_as_missing": not b, "match": a and b,
                "why": f"driver text for a missing table maps to 'missing': {a}; a missing column (SQLCODE -29) "
                       f"does not: {b}"}
    case("18", "_table_missing <- driver SQLCODE text", "missing table vs missing column", table_missing)

    def http_map():
        os.environ.update({"IRIS_HOST": "127.0.0.1", "IRIS_PORT": os.environ["IVG_PORT"], "IRIS_NAMESPACE": "AUDITE",
                           "IRIS_USERNAME": "_SYSTEM", "IRIS_PASSWORD": "SYS", "BOLT_ENABLED": "0",
                           "IVG_SNAPSHOT_DIR": str(out_dir) + "/"})
        os.environ.pop("IVG_API_KEY", None)
        os.environ.pop("IVG_READ_ONLY", None)
        from fastapi.testclient import TestClient
        import iris_vector_graph.cypher_api as api
        client = TestClient(api.app)
        res = {}
        try:
            r = client.post("/admin/snapshot")
            j = r.json()
            res["ok"] = {"status": r.status_code, "keys": sorted(j), "result_keys": sorted(j.get("result", {})),
                         "path_exists": bool(j.get("path")) and os.path.exists(j["path"])}
            if j.get("path") and os.path.exists(j["path"]):
                os.unlink(j["path"])
            os.environ["IVG_READ_ONLY"] = "true"
            r = client.post("/admin/snapshot")
            res["read_only"] = {"status": r.status_code, "body": r.json()}
            os.environ.pop("IVG_READ_ONLY")
            os.environ["IVG_SNAPSHOT_DIR"] = str(out_dir) + "/no-such-dir/"
            r = client.post("/admin/snapshot")
            res["unwritable_dir"] = {"status": r.status_code, "body": r.json()}
            os.environ["IVG_SNAPSHOT_DIR"] = str(out_dir) + "/"
            os.environ["IVG_API_KEY"] = "rxd-key"
            r = client.post("/admin/snapshot")
            res["no_key"] = {"status": r.status_code, "body": r.json()}
            os.environ.pop("IVG_API_KEY")
        finally:
            os.environ.pop("IVG_API_KEY", None)
            os.environ.pop("IVG_READ_ONLY", None)
            with api._engine_lock:
                api._reset_engine()
        ok = (res["ok"]["status"] == 200 and res["ok"]["keys"] == ["path", "result", "status"]
              and res["ok"]["result_keys"] == ["globals", "path", "snapshot_ts", "tables"]
              and res["read_only"]["status"] == 403 and res["read_only"]["body"].get("error") == "read_only_mode"
              and res["unwritable_dir"]["status"] == 500 and "detail" in res["unwritable_dir"]["body"]
              and res["no_key"]["status"] == 401)
        return {"responses": res, "match": ok,
                "why": f"statuses ok {res['ok']['status']}, read-only {res['read_only']['status']}, "
                       f"unwritable {res['unwritable_dir']['status']}, no key {res['no_key']['status']} "
                       "(docs/ADMIN_API.md:73, 292-303)"}
    case("18", "POST /admin/snapshot HTTP status map", "200 / 403 read-only / 500 / 401", http_map)

    for drop in (lambda: e.vec_drop("rxdvec"), lambda: e.plaid_drop("rxdplaid")):
        try:
            drop()
        except Exception:  # noqa: BLE001
            pass
    try:
        os.unlink(path)
    except OSError:
        pass


def main():
    mod = sys.argv[1]
    fn = {"07": m07, "10": m10, "18": m18}[mod]
    with Lane(f"decoders/{mod}") as L:
        L.reset()
        L.control()
        try:
            fn(L)
        except Exception as e:  # noqa: BLE001  (a setup failure is recorded; the cases run so far are kept)
            CASES.append({"module": mod, "case": "harness-error (module aborted)", "match": None,
                          "harness_error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]})
            print(f"[ERR] module aborted: {type(e).__name__}: {e}", flush=True)
        finally:
            rollback_all(L.c.conn)
            L.reset()
        decided = [c for c in CASES if "match" in c]
        doc = {"module": mod, "namespace": "AUDITE", "pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
               "oracle_control_ok": L.control_ok, "cases": CASES,
               "summary": {"match": sum(1 for c in decided if c["match"] is True),
                           "mismatch": sum(1 for c in decided if c["match"] is False),
                           "not_decided": sum(1 for c in decided if c["match"] is None)}}
        p = L.out / f"live-{mod}.json"
        if p.exists():
            p = L.out / f"live-{mod}-{time.strftime('%Y%m%dT%H%M%S')}.json"
        p.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
        print(f"wrote {p}: {doc['summary']}")


if __name__ == "__main__":
    main()
