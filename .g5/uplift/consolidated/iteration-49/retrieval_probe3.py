"""W56 follow-up 3 (default graph, fresh prefix): kg_SUBGRAPH's edges among nodes reached at the last hop, an
isolated seed, and kg_PPR_GUIDED_SUBGRAPH on a star whose reachable nodes outnumber ppr_top_k."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent / "iteration-36")); import runtime  # noqa: E402
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]; P = f"i49_{TAG}_"
out = {"run": RUN, "fixture": runtime.NAME, "prefix": P, "cases": {}}
def rec(k, fn):
    try: out["cases"][k] = fn()
    except Exception as x: out["cases"][k] = {"exception": f"{type(x).__name__}: {str(x)[:300]}"}
from iris_vector_graph.engine import IRISGraphEngine
c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
sh = lambda n: n[len(P):] if n.startswith(P) else n  # noqa: E731
for n in ["s", "a1", "a2", "a3", "a4", "a5", "a6", "z"]: e.create_node(P + n)
for o in ["a1", "a2", "a3", "a4", "a5", "a6"]: e.create_edge(P + "s", "LINK", P + o)
e.create_edge(P + "a1", "LINK", P + "a2")   # an edge between two nodes both one hop from s
def sg(r): return {"nodes": sorted(sh(n) for n in r.nodes), "edges": sorted(f"{sh(s)}>{sh(o)}" for s, p, o in r.edges)}
def pg(r): return {"nodes": sorted(sh(n) for n in r.nodes), "edges": sorted(f"{sh(x['src'])}>{sh(x['dst'])}" for x in r.edges), "ppr": [[sh(k), round(v, 6)] for k, v in r.ppr_scores]}
rec("S_star_1hop", lambda: sg(e.kg_SUBGRAPH([P + "s"], k_hops=1)))
rec("S_star_2hop", lambda: sg(e.kg_SUBGRAPH([P + "s"], k_hops=2)))
rec("S_isolated_seed", lambda: sg(e.kg_SUBGRAPH([P + "z"], k_hops=1)))
rec("S_isolated_plus_s", lambda: sg(e.kg_SUBGRAPH([P + "z", P + "s"], k_hops=1)))
rec("S_star_cap3", lambda: sg(e.kg_SUBGRAPH([P + "s"], k_hops=1, max_nodes=3)))
for t in (3, 5, 7, 50):
    rec(f"PG_star_top{t}", lambda t=t: pg(e.kg_PPR_GUIDED_SUBGRAPH([P + "s"], ppr_top_k=t, k_hops=1)))
rec("PG_isolated_seed", lambda: pg(e.kg_PPR_GUIDED_SUBGRAPH([P + "z"], ppr_top_k=5)))
p = HERE / f"retrieval-observed3-{RUN}.json"; p.write_text(json.dumps(out, indent=1) + "\n"); print(p)
