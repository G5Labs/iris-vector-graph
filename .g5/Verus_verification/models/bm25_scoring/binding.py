"""Binding for bm25_scoring (W59, iteration 53) on the run-isolated continuation fixture.

One fresh graph in USER (prefix i53s_), a corpus of nodes with one text property, bm25_build over it, then queries
through every reader: VectorMixin.bm25_search (Python, with and without the cutoff report), Graph.KG.BM25Index.Search's
raw answer, SQL Graph_KG.kg_BM25 and CALL ivg.bm25.search. Then an incremental insert and delete beside a fresh build
over the same documents. Expected answers come from a Python port of bm25_scoring.rs: the stopword list as USER_GUIDE
prints it, a plain splitter (the corpus is chosen so the analyzer's splitting is ordinary: lower case, break at
punctuation, accents kept), statistics from the corpus the binding wrote, the model's tfpart and idf_arg with
math.log (premise P-LN), the (key desc, id asc) order and the cutoff/fallback rule, and the `_parse` patch. Never from
the product's answers. Scores are compared with a relative tolerance of 1e-12 (the product writes ~20 significant
digits; Python reads a double). One port mutation per control; one observation is tampered.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/bm25_scoring/binding.py)
"""
import hashlib, json, math, os, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); T = RUN[-7:-1]
P = f"i53s_{T}_"; G = f"i53sbg{T}"; PROP = f"i53sbt{T}"
TOL = 1e-12
MUTS = ["stopwords-kept", "query-terms-deduplicated", "unknown-terms-scored", "no-fallback", "left-to-right-denominator",
        "idf-without-plus-one", "ties-by-key-only", "schema2-reads-stored", "parse-keeps-ids",
        # iteration 56 (review 53-55 minors): subscript collation of tied ids; k at the three readers
        "numeric-ids-as-text", "text-case-folded", "sql-entry-validates-k", "nonpositive-k-takes-all"]
# a tie: six documents with the same text; two ids are canonical numbers (9 before 10 by value, "10" first as text)
NUM9, NUM10 = "7" + T + "9", "7" + T + "10"
TIES = [NUM9, NUM10, P + "d10", P + "d9", P + "dB", P + "da"]
STOP = set("a,an,the,and,or,but,in,on,at,to,for,of,with,by,from,is,are,was,were,be,been,being,have,has,had,do,does,did,"
           "will,would,could,should,may,might,shall,this,that,these,those,it,its,i,we,you,he,she,they,them,their,our,your,"
           "his,her,not,no,nor,so,yet,both,either,neither,each,all,any,such,as,if,than,then,there,here,when,where,which,"
           "who,what,how".split(","))
# ids carry a ':.5'-style suffix on one document so the reader's `_parse` patch shows (F-C0715)
CORPUS = {"d1": "graph database graph", "d2": "vector database", "d3": "The graph of things",
          "d4": "state-of-the-art graph", "d5": "über vector", "d6": "vector database", "e:.5x": "graph engine",
          "f": "Graph, graph; GRAPH engine graph", "g": "and the of"}
QUERIES = ["graph", "Graph!", "the", "things", "über", "uber", "state art", "state-of-the-art", "vector",
           "zzz graph", "graph graph", "graph things", "engine graph", "database vector graph"]
CUTOFF = [("graph things", 0.4), ("graph", 0.4), ("zzz graph", 0.4), ("engine graph", 0.5), ("vector database", 0.2)]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ port of bm25_scoring.rs
def tokens(text, m):
    raw = [t for t in re.split(r"[^\w]+", text.lower()) if t]
    return raw if m.get("stopwords-kept") else [t for t in raw if t not in STOP]


def stats(docs, m):
    toks = {d: tokens(t, m) for d, t in docs.items()}
    toks = {d: ts for d, ts in toks.items() if ts}
    df = {}
    for ts in toks.values():
        for t in set(ts):
            df[t] = df.get(t, 0) + 1
    return {"n": len(toks), "total": sum(len(ts) for ts in toks.values()), "df": df,
            "tf": {d: {t: ts.count(t) for t in set(ts)} for d, ts in toks.items()}, "len": {d: len(ts) for d, ts in toks.items()}}


def tfpart(tf, ln, total, n, m):
    if m.get("left-to-right-denominator"):
        return 5 * tf * total / ((2 * tf + 3) * ln * n)
    return 20 * tf * total / (8 * tf * total + 3 * total + 9 * ln * n)


def idf(n, df, m):
    a = (2 * n - 2 * df + 1) / (2 * df + 1) if m.get("idf-without-plus-one") else (2 * n + 2) / (2 * df + 1)
    return math.log(a)


def search(st, query, k, m, frac=0.0, stored=None):
    """stored: the stats of an earlier build (schema 1 / the schema2-reads-stored mutation)."""
    if st["n"] == 0:
        return {"results": [], "skipped": [], "fallback": False}
    q = tokens(query, m)
    known = (lambda t: True) if m.get("unknown-terms-scored") else (lambda t: st["df"].get(t, 0) > 0)
    over = lambda t: frac > 0 and st["df"].get(t, 0) > 0 and st["df"][t] / st["n"] > frac
    skip = {t for t in q if over(t)}
    fallback = False
    ks = [t for t in q if known(t)]
    if frac > 0 and ks and all(over(t) for t in ks) and not m.get("no-fallback"):
        mt = None
        for t in ks:
            if mt is None or st["df"].get(t, 0) < st["df"].get(mt, 0):
                mt = t
        skip.discard(mt); fallback = True
    terms = [t for t in q if known(t) and t not in skip]
    if m.get("query-terms-deduplicated"):
        terms = list(dict.fromkeys(terms))
    src = stored if (m.get("schema2-reads-stored") and stored) else st
    scores = {}
    for t in terms:
        if st["df"].get(t, 0) == 0:
            continue
        w = idf(src["n"], src["df"].get(t, st["df"][t]), m)
        for d, tfs in st["tf"].items():
            if t in tfs:
                scores[d] = scores.get(d, 0.0) + w * tfpart(tfs[t], st["len"][d], st["total"], st["n"], m)
    keyed = {}
    for d, s in scores.items():
        key = round(s * 1e12)
        if m.get("ties-by-key-only"):
            keyed[(key, "")] = (d, s)        # one subscript per key: the last document written wins
        else:
            keyed[(key, d)] = (d, s)
    order = sorted(keyed, key=lambda x: (-x[0], collate(x[1], m)))
    return {"results": [list(keyed[x]) for x in order[:k]], "skipped": sorted(skip), "fallback": fallback}


def collate(d, m):
    """P-COLLATE: a canonical number first, by value; other ids by character codes."""
    canon = re.fullmatch(r"-?(0|[1-9][0-9]*)", d) is not None
    if canon and not m.get("numeric-ids-as-text"):
        return (0, int(d), ())
    return (1, 0, tuple(-ord(c) for c in d) if m.get("text-case-folded") else tuple(ord(c) for c in d))


def take(results, k, entry, m):
    """entry_k: SQL passes k through (SearchCore answers [] for k <= 0); Python and Cypher refuse k < 1."""
    if k < 1 and (entry != "sql" or m.get("sql-entry-validates-k")):
        return "refused"
    if k <= 0:
        return list(results) if m.get("nonpositive-k-takes-all") else []
    return list(results[:k])


def py_patch(raw, m):
    return raw if m.get("parse-keeps-ids") else re.sub(r'(?<=[:\[,])(\.\d)', r'0\1', raw)


def main():
    t0 = time.time()
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    cur = c.cursor(); obj = e._iris_obj()
    for d, t in CORPUS.items():
        e.create_node(P + d, labels=["I53SB"], properties={PROP: t}, graph=G)
    name = f"i53sbs{T}"
    build = e.bm25_build(name, [PROP], graph=G)
    got = {"build_indexed": build["indexed"], "build_vocab": build["vocab_size"]}
    strip = lambda rs: [[i[len(P):] if isinstance(i, str) and i.startswith(P) else i, float(s)] for i, s in rs]
    for qq in QUERIES:
        got[f"py:{qq}"] = strip(e.bm25_search(name, qq, 10))
        raw = obj.classMethodValue("Graph.KG.BM25Index", "Search", name, qq, 10)
        got[f"raw:{qq}"] = strip([(r["id"], r["score"]) for r in json.loads(raw)])
    for k in (1, 2):
        got[f"py:vector@k{k}"] = strip(e.bm25_search(name, "vector", k))
    for qq, f in CUTOFF:
        r = e.bm25_search(name, qq, 10, max_df_fraction=f, report=True)
        got[f"cut:{qq}@{f}"] = {"results": strip(r["results"]), "skipped": sorted(r["skipped"]), "fallback": r["fallback"]}
    for qq in ("graph", "vector database"):
        cur.execute(f"SELECT {e._ivg_schema}.kg_BM25(?, ?, ?)", [name, qq, 10])
        got[f"sql:{qq}"] = strip([(r["id"], r["score"]) for r in json.loads(cur.fetchone()[0])])
        rows = e.execute_cypher(f"USE GRAPH '{G}' CALL ivg.bm25.search('{name}', '{qq}', 10) YIELD node, score "
                                "RETURN node.node_id AS id, score").rows
        got[f"cypher:{qq}"] = strip([(r[0], r[1]) for r in rows])
    # incremental writes vs a fresh build over the same documents
    docs = dict(CORPUS)
    e.bm25_insert(name, P + "d7", "graph"); docs["d7"] = "graph"
    got["inc_insert:graph"] = strip(e.bm25_search(name, "graph", 10))
    e.bm25_delete(name, P + "d1"); del docs["d1"]
    got["inc_delete:graph"] = strip(e.bm25_search(name, "graph", 10))
    got["inc_delete:database"] = strip(e.bm25_search(name, "database", 10))
    G2 = G + "f"
    for d, t in docs.items():
        e.create_node(P + d, labels=["I53SB"], properties={PROP: t}, graph=G2)
    fresh = name + "f"
    e.bm25_build(fresh, [PROP], graph=G2)
    got["fresh:graph"] = strip(e.bm25_search(fresh, "graph", 10))
    got["fresh:database"] = strip(e.bm25_search(fresh, "database", 10))
    # iteration 56: tie order over subscript collation, and k <= 0 at the three readers
    G3 = G + "t"
    for d in TIES:
        e.create_node(d, labels=["I53SB"], properties={PROP: "tieword"}, graph=G3)
    ties = name + "t"
    e.bm25_build(ties, [PROP], graph=G3)
    got["tie:py"] = strip(e.bm25_search(ties, "tieword", 10))
    got["tie:py@k3"] = strip(e.bm25_search(ties, "tieword", 3))
    got["tie:raw"] = strip([(r["id"], r["score"]) for r in json.loads(obj.classMethodValue("Graph.KG.BM25Index", "Search", ties, "tieword", 10))])
    cur.execute(f"SELECT {e._ivg_schema}.kg_BM25(?, ?, ?)", [ties, "tieword", 10])
    got["tie:sql"] = strip([(r["id"], r["score"]) for r in json.loads(cur.fetchone()[0])])
    for k in (0, -1, 1):
        cur.execute(f"SELECT {e._ivg_schema}.kg_BM25(?, ?, ?)", [fresh, "graph", k])
        got[f"k:sql@{k}"] = strip([(r["id"], r["score"]) for r in json.loads(cur.fetchone()[0])])
        try:
            got[f"k:py@{k}"] = strip(e.bm25_search(fresh, "graph", k))
        except Exception as x:  # noqa: BLE001
            got[f"k:py@{k}"] = "refused"; got[f"k:py@{k}:error"] = type(x).__name__
        try:
            r = e.execute_cypher(f"USE GRAPH '{G2}' CALL ivg.bm25.search('{fresh}', 'graph', {k}) YIELD node, score "
                                 "RETURN node.node_id AS id, score")
            got[f"k:cypher@{k}"] = "refused" if r.error else strip([(x[0], x[1]) for x in r.rows])
        except Exception as x:  # noqa: BLE001
            got[f"k:cypher@{k}"] = "refused"; got[f"k:cypher@{k}:error"] = type(x).__name__
    for n_ in (name, fresh, ties):
        e.bm25_drop(n_)
    c.close()

    def predict(m):
        st0 = stats(CORPUS, m)
        out = {"build_indexed": st0["n"], "build_vocab": len(st0["df"])}
        pid = lambda rs: [[py_patch(i, m), s] for i, s in rs]   # bm25_search's `_parse` over the answer's ids
        for qq in QUERIES:
            res = search(st0, qq, 10, m)["results"]
            out[f"py:{qq}"] = pid(res)
            out[f"raw:{qq}"] = res
        for k in (1, 2):
            out[f"py:vector@k{k}"] = pid(search(st0, "vector", k, m)["results"])
        for qq, f in CUTOFF:
            r = search(st0, qq, 10, m, frac=f)
            out[f"cut:{qq}@{f}"] = {"results": pid(r["results"]), "skipped": r["skipped"], "fallback": r["fallback"]}
        for qq in ("graph", "vector database"):
            out[f"sql:{qq}"] = search(st0, qq, 10, m)["results"]
            out[f"cypher:{qq}"] = search(st0, qq, 10, m)["results"]
        d1 = dict(CORPUS); d1["d7"] = "graph"
        out["inc_insert:graph"] = pid(search(stats(d1, m), "graph", 10, m, stored=st0)["results"])
        d2 = dict(d1); del d2["d1"]
        out["inc_delete:graph"] = pid(search(stats(d2, m), "graph", 10, m, stored=st0)["results"])
        out["inc_delete:database"] = pid(search(stats(d2, m), "database", 10, m, stored=st0)["results"])
        out["fresh:graph"] = pid(search(stats(d2, m), "graph", 10, m)["results"])
        out["fresh:database"] = pid(search(stats(d2, m), "database", 10, m)["results"])
        tdocs = {d: "tieword" for d in TIES}
        stt = stats(tdocs, m)
        tres = [[i[len(P):] if i.startswith(P) else i, s] for i, s in search(stt, "tieword", 10, m)["results"]]
        out["tie:py"] = pid(tres); out["tie:raw"] = tres; out["tie:sql"] = tres
        out["tie:py@k3"] = pid(tres[:3])
        full = search(stats(d2, m), "graph", 10**6, m)["results"]
        for k in (0, -1, 1):
            out[f"k:sql@{k}"] = take(full, k, "sql", m)
            out[f"k:py@{k}"] = take(pid(full), k, "py", m)
            out[f"k:cypher@{k}"] = take(full, k, "cypher", m)
        return out

    def same(a, b):
        if isinstance(a, float) or isinstance(b, float):
            try:
                return abs(float(a) - float(b)) <= TOL * max(1.0, abs(float(b)))
            except (TypeError, ValueError):
                return False
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
        return a == b

    want = predict({})
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if not same(got.get(k), want[k])]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if not same(got.get(k), v)) for mm in MUTS}
    tampered = json.loads(json.dumps(got)); tampered["py:graph"][0][1] += 1e-6
    tamper_detected = any(not same(tampered.get(k), want[k]) for k in want)
    body = {"kind": "binding", "model": "bm25_scoring", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "prefix": P, "graph": G, "tolerance_relative": TOL,
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q_.relative_to(REPO)): sha(q_) for q_ in [HERE / "binding.py", HERE / "bm25_scoring.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_src/src/Graph/KG/BM25Index.cls", "iris_src/src/Graph/KG/SqlProcs.cls",
                                                                   "iris_vector_graph/_engine/vector.py", "iris_vector_graph/cypher/translator.py"]}},
            "scope": "Actual bm25_build / bm25_search / bm25_insert / bm25_delete, Graph.KG.BM25Index.Search, SQL kg_BM25 and CALL "
                     "ivg.bm25.search on IRIS 2026.1 (pin 3eaa79cf): 9 documents (stopwords, punctuation, accents, repeats, an "
                     "id holding ':.5', a stopword-only text), 14 queries on two readers, k 1 and 2 on a three-way tie, 5 "
                     "cutoff cases with the report, kg_BM25 and the Cypher procedure on 2 queries, an incremental insert and "
                     "delete against a fresh build over the same documents; iteration 56: a six-way tie whose ids include two "
                     "canonical numbers (subscript collation) on three readers, and k 0, -1, 1 on kg_BM25, bm25_search and "
                     "CALL ivg.bm25.search."}
    d = REPO / ".g5/Verus_verification/results/bm25_scoring" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, ensure_ascii=False, default=str)[:400])


if __name__ == "__main__":
    main()
