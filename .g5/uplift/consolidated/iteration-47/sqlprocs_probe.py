"""W53: kg_IVF and kg_BM25 over SQL against ivf_search and bm25_search (run-isolated continuation fixture)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent / "iteration-36")); import runtime  # noqa: E402
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
G, K, NAME, p = f"sqg{TAG}", f"sq-k-{TAG}", f"sqi{TAG}", f"sq{TAG}_"
for n, v in {"a": [1, 0, 0, 0], "b": [0, 1, 0, 0], "c": [0.7, 0.7, 0, 0], "d": [0, 0, 1, 0]}.items():
    e.create_node(p + n, graph=G); e.store_embedding(p + n, [float(x) for x in v], graph=G, model_key=K)
e.ivf_build(NAME, nlist=2, graph=G, model_key=K)
def sql(fn, *args):
    cur = c.cursor(); cur.execute(f"SELECT {e._ivg_schema}.{fn}({', '.join('?' * len(args))})", list(args)); r = cur.fetchone()[0]; cur.close(); return r
def case(k, f):
    try: out["cases"][k] = f()
    except Exception: out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:300]
q = [0.9, 0.5, 0, 0]
case("S1_ivf", lambda: {"python": [(i, round(s, 4)) for i, s in e.ivf_search(NAME, q, 3, 2)],
                        "sql": [(r["id"], round(float(r["score"]), 4)) for r in json.loads(sql("kg_IVF", NAME, json.dumps(q), 3, 2))]})
for n, t in {"x": "graph database vector", "y": "vector index search", "z": "unrelated words here"}.items():
    e.create_node(p + n, properties={"text": t})
BN = f"sqb{TAG}"
case("S2_bm25", lambda: (e.bm25_build(BN, text_props=["text"], node_ids=[p + "x", p + "y", p + "z"]) if "node_ids" in e.bm25_build.__code__.co_varnames else e.bm25_build(BN, text_props=["text"]),
                         {"python": [(i, round(s, 4)) for i, s in e.bm25_search(BN, "vector", 3)],
                          "sql": [(r["id"], round(float(r["score"]), 4)) for r in json.loads(sql("kg_BM25", BN, "vector", 3))]})[1])
case("S3_missing", lambda: {"ivf_py": e.ivf_search(f"nope{TAG}", q, 3, 2), "ivf_sql": sql("kg_IVF", f"nope{TAG}", json.dumps(q), 3, 2),
                            "bm25_py": e.bm25_search(f"nope{TAG}", "vector", 3), "bm25_sql": sql("kg_BM25", f"nope{TAG}", "vector", 3)})
(HERE / f"sqlprocs-observed-{RUN}.json").write_text(json.dumps(out, indent=2, default=str) + "\n"); print(json.dumps(out, default=str))
