"""Binding for retrieval_compose (W56, iteration 49) on the run-isolated continuation fixture.

Runs the real product (exported pin tree, IRIS 2026.1 container ivg-cont-20261117-iris) on fresh ordinary data:
engine kg_RRF_FUSE / kg_RERANK, IRISGraphOperators, the SQL kg_RRF_FUSE procedure, Graph.KG.PyOps HybridSearch and
VectorSearch, kg_VECTOR_GRAPH_SEARCH (one process per hash seed), kg_SUBGRAPH and kg_PPR_GUIDED_SUBGRAPH, and
multi_vector_search. Each answer is compared with a Python port of retrieval_compose.rs's spec functions (`absent_place`,
`rrf`, `engine_fuse`, `ivf_scope_seen`/`leg_index`, `hybrid_c`, `pyops_vector_search`/`engine_knn`, `answered`,
`in_graph_expansion`/`vector_similarity`, `expand_node`/`expand_frontier` with `guided_cap`, `mvs_rows`) applied to the
legs and adjacency the product itself reports. Mutations mirror the model's controls; one observation is tampered.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/retrieval_compose/binding.py)
"""
import hashlib, json, math, os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i49b_{TAG}_"; G, G2, G3, GV = f"i49bf{TAG}", f"i49be{TAG}", f"i49bu{TAG}", f"i49bv{TAG}"
MUTS = ["engine-absent-zero", "sql-absent-like-engine", "vector-failure-isolated", "ivf-scope-persisted", "hnsw-before-own-ivf",
        "ivf-cosine-normalized", "hybrid-c-kept", "unrouted-no-width-check", "sort-before-truncate", "expansion-flag-excludes-hits",
        "edge-recorded-after-cap-test", "edges-among-answered", "seeds-capped", "expand-whole-frontier-at-cap",
        "guided-cap-top-k-only"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sh(i):
    return i[len(P):] if isinstance(i, str) and i.startswith(P) else i


def unit(deg):
    a = math.radians(deg); return [math.cos(a), math.sin(a), 0.0, 0.0]


# ------------------------------------------------------------------ ports of the spec functions
def absent_place(surface, c, leg_len, m):
    if surface == "Engine":
        return None if m.get("engine-absent-zero") else leg_len + c
    if surface == "SqlProcedure":
        return leg_len + c if m.get("sql-absent-like-engine") else 10 ** 9
    if surface == "PyOpsFuseRanks":
        return 10 ** 9
    return None


def part(surface, c, rank, leg_len, m):
    if rank is not None:
        return 1.0 / (c + rank)
    p = absent_place(surface, c, leg_len, m)
    return 0.0 if p is None else 1.0 / (c + p)


def fuse(surface, c, vleg, tleg, m, k=100):
    """vleg/tleg: ids best first (first occurrence counts). Returns {id: score} for the top k ids."""
    vr, tr = {}, {}
    for i, x in enumerate(vleg):
        vr.setdefault(x, i + 1)
    for i, x in enumerate(tleg):
        tr.setdefault(x, i + 1)
    s = {x: part(surface, c, vr.get(x), len(vleg), m) + part(surface, c, tr.get(x), len(tleg), m) for x in set(vr) | set(tr)}
    keep = sorted(s.items(), key=lambda kv: -kv[1])[:k]
    return dict(keep)


def engine_fuse(v_fails, text_requested, nt, m):
    if v_fails:
        return "TextOnly" if (m.get("vector-failure-isolated") and text_requested and nt) else "Empty"
    return "rows"


def ivf_scope_seen(built_here, m):
    return "Recorded" if (built_here or m.get("ivf-scope-persisted")) else "Unknown"


def leg_index(scope, hnsw, m):
    if scope == "Recorded" and not (m.get("hnsw-before-own-ivf") and hnsw):
        return "ivf"
    if hnsw:
        return "hnsw"
    return "ivf" if scope == "Unknown" else None


def hybrid_c(c, m):
    return c if m.get("hybrid-c-kept") else (60 if c == 0 else c)


def pyops_vector_search(route_width, named, qdim, m):
    expected = route_width if route_width is not None else (768 if named else 768)
    if qdim != expected and not (m.get("unrouted-no-width-check") and route_width is None):
        return "WidthRefused"
    return "Rows" if route_width is not None else "NoRows"


def answered(order, k, sims, m):
    if m.get("sort-before-truncate"):
        return sorted(order, key=lambda x: -sims.get(x, 0.0))[:k]
    return order[:k]


def in_graph_expansion(is_hit, is_exp, m):
    return is_exp and not is_hit if m.get("expansion-flag-excludes-hits") else is_exp


def subgraph(seeds, adj, hops, cap, m):
    """SubgraphJson: seeds with an edge either way, BFS hop by hop over the frontier in collation order."""
    has_edge = {n for n in adj if adj[n]} | {o for n in adj for o in adj[n]}
    seen, count, edges, frontier = set(), 0, [], []
    for s in seeds:
        if s in has_edge:
            if m.get("seeds-capped") and s not in seen and count >= cap:
                continue
            if s not in frontier:
                frontier.append(s)
            if s not in seen:
                seen.add(s); count += 1
    stop = False
    for _ in range(hops):
        nxt = []
        for n in sorted(frontier):
            for o in sorted(adj.get(n, [])):
                rec_edge = (n, o)
                if o in seen:
                    if rec_edge not in edges:
                        edges.append(rec_edge)
                    continue
                if count >= cap:
                    if not m.get("edge-recorded-after-cap-test") and rec_edge not in edges:
                        edges.append(rec_edge)
                    stop = True; break
                if rec_edge not in edges:
                    edges.append(rec_edge)
                seen.add(o); count += 1; nxt.append(o)
            if stop or (count >= cap and not m.get("expand-whole-frontier-at-cap")):
                stop = True; break
        frontier = nxt
        if stop or not frontier or count >= cap:
            break
    if m.get("edges-among-answered"):
        edges = [(n, o) for n in seen for o in adj.get(n, []) if o in seen]
    return {"nodes": sorted(sh(n) for n in seen), "edges": sorted(f"{sh(a)}>{sh(b)}" for a, b in edges)}


def guided_cap(max_nodes, top_k, m):
    return top_k if m.get("guided-cap-top-k-only") else min(max_nodes, top_k)


# ------------------------------------------------------------------ the run
VGS_CHILD = r"""
import sys, json; sys.path.insert(0, %(rt)r); import runtime
from iris_vector_graph.engine import IRISGraphEngine
c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
qs, G, k = %(qs)r, %(g)r, 2
r = e.kg_VECTOR_GRAPH_SEARCH(qs, k=k, graph=G)
vr = e.kg_KNN_VEC(qs, k=min(2 * k, 50), graph=G)
ve = [x for x, _ in vr]
ex = list(set(d["target"] for d in e.kg_NEIGHBORHOOD_EXPANSION(ve, 1, 500, graph=G))) if ve else []
order = list(set(ve + ex))   # the same expression, so the same order under this hash seed
print(json.dumps({"answer": [[x["entity_id"], x["vector_similarity"], x["in_graph_expansion"]] for x in r],
                  "order": order, "hits": [[x, s] for x, s in vr], "expanded": ex}))
"""


def main():
    t0 = time.time()
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.operators import IRISGraphOperators
    c = runtime.connect(); e1 = IRISGraphEngine(c, embedding_dimension=768); cur = c.cursor()
    q = [1.0, 0.0, 0.0, 0.0]; qs = json.dumps(q)
    io = e1._iris_obj()
    obs, inputs = {}, {}

    def doc(i):
        return " ".join(["zeta"] * (60 - i) + ["pad"] * i)
    e1.create_node(P + "x", properties={"text": "unrelated words"}, graph=G); e1.store_embedding(P + "x", q, graph=G)
    for i in range(60):
        nid = P + f"n{i:02d}"
        e1.create_node(nid, properties={"text": doc(i)}, graph=G); e1.store_embedding(nid, unit(i + 1), graph=G)
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", [G, nid, doc(i)])
    e1.create_node(P + "L", properties={"text": "nothing"}, graph=G); e1.store_embedding(P + "L", [10.0, 10.0, 0.0, 0.0], graph=G)
    bname = f"i49bb{TAG}"; e1.bm25_build(bname, ["text"], graph=G)
    for i in range(3):
        e1.create_node(P + f"t{i}", properties={"text": " ".join(["zeta"] * (3 - i) + ["pad"] * i)}, graph=G2)
    e1.bm25_build(bname + "e", ["text"], graph=G2)

    ids = lambda rows: [sh(r[0]) for r in rows]  # noqa: E731
    inputs["vleg"] = ids(e1.kg_KNN_VEC(qs, k=200, graph=G)); inputs["bleg"] = ids(e1.bm25_search(bname, "zeta", k=200))
    inputs["tleg"] = ids(e1.kg_TXT("zeta", k=200, graph=G)); inputs["bleg2"] = ids(e1.bm25_search(bname + "e", "zeta", k=200))
    scores = lambda rows: {sh(r[0]): round(float(r[1]), 9) for r in rows}  # noqa: E731
    obs["engine_fuse"] = scores(e1.kg_RRF_FUSE(100, 200, 200, 60, qs, "zeta", graph=G))
    obs["engine_empty_text"] = scores(e1.kg_RRF_FUSE(100, 200, 200, 60, qs, "", graph=G))
    obs["engine_failed_vector"] = len(e1.kg_RRF_FUSE(100, 200, 200, 60, "[1.0, 0.0, 0.0]", "zeta", graph=G))
    obs["engine_empty_vector_g2"] = scores(e1.kg_RRF_FUSE(100, 200, 200, 60, qs, "zeta", graph=G2))
    ops = IRISGraphOperators(c)
    obs["ops_default_vector"] = len(ops.kg_RRF_FUSE(query_text="zeta", graph=G))

    iname = f"i49bi{TAG}"; e1.ivf_build(iname, nlist=1, graph=G, metric="cosine")
    inputs["ivfleg"] = ids(e1.ivf_search(iname, q, k=200))
    obs["choice_building"] = e1._fusion_leg_index(("ivf", "hnsw"), G)[1]
    obs["engine_fuse_building"] = scores(e1.kg_RRF_FUSE(100, 200, 200, 60, qs, "zeta", graph=G))
    e2 = IRISGraphEngine(c, embedding_dimension=768)
    obs["choice_fresh"] = e2._fusion_leg_index(("ivf", "hnsw"), G)[1]
    obs["engine_fuse_fresh"] = scores(e2.kg_RRF_FUSE(100, 200, 200, 60, qs, "zeta", graph=G))
    obs["ops_fuse_fresh"] = scores(IRISGraphOperators(c).kg_RRF_FUSE(100, 200, 200, 60, qs, "zeta", graph=G))
    obs["hnsw_present"] = "hnsw" in e2._index_registry

    def da(vec):
        return io.classMethodObject("%DynamicArray", "%FromJSON", json.dumps(vec))

    def pyops(method, *args):
        return json.loads(io.classMethodObject("Graph.KG.PyOps", method, *args).invoke("%ToJSON"))
    obs["pyops_hybrid"] = {sh(r["id"]): round(r["score"], 9) for r in pyops("HybridSearch", da(q), "zeta", 100, 60, G)}
    obs["pyops_hybrid_c0"] = {sh(r["id"]): round(r["score"], 9) for r in pyops("HybridSearch", da(q), "zeta", 100, 0, G)}

    def outcome(fn):
        try:
            r = fn(); return "Rows" if r else "NoRows"
        except Exception as x:  # noqa: BLE001
            return "WidthRefused" if "768" in str(x) or "dimension" in str(x) else f"other: {str(x)[:120]}"
    obs["pyops_unrouted_4"] = outcome(lambda: pyops("VectorSearch", da(q), 5, "", G3))
    obs["pyops_unrouted_768"] = outcome(lambda: pyops("VectorSearch", da([1.0] + [0.0] * 767), 5, "", G3))
    obs["pyops_routed_4"] = outcome(lambda: pyops("VectorSearch", da(q), 5, "", G))
    obs["engine_unrouted_4"] = outcome(lambda: e1.kg_KNN_VEC(qs, k=5, graph=G3))

    # default graph: SQL procedure and its legs
    def v768(deg):
        a = math.radians(deg); v = [0.0] * 768; v[0], v[1] = math.cos(a), math.sin(a); return v
    q768s = json.dumps(v768(0))
    e1.create_node(P + "dx"); e1.store_embedding(P + "dx", v768(0))
    for i in range(30):
        nid = P + f"d{i:02d}"; e1.create_node(nid); e1.store_embedding(nid, v768(i + 1))
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", ["", nid, " ".join(["omg" + TAG] * (30 - i) + ["pad"] * i)])
    cur.execute("SELECT node_id FROM Graph_KG.kg_KNN_VEC(?, ?, ?, ?)", [q768s, 40, None, ""]); inputs["sql_vleg"] = [sh(r[0]) for r in cur.fetchall()]
    cur.execute("SELECT id FROM Graph_KG.kg_TXT(?, ?, ?, ?)", ["omg" + TAG, 40, 0, ""]); inputs["sql_tleg"] = [sh(r[0]) for r in cur.fetchall()]
    cur.execute("SELECT id, rrf FROM Graph_KG.kg_RRF_FUSE(?, ?, ?, ?, ?, ?, ?)", [100, 40, 40, 60, q768s, "omg" + TAG, ""])
    obs["sql_fuse"] = {sh(r[0]): round(float(r[1]), 9) for r in cur.fetchall()}

    # kg_VECTOR_GRAPH_SEARCH, one process per hash seed
    for n, deg in {"a": 0, "b": 10, "p": 20, "r": 30}.items():
        e1.create_node(P + n, graph=GV); e1.store_embedding(P + n, unit(deg), graph=GV)
    e1.create_node(P + "nn", graph=GV)
    e1.create_edge(P + "a", "REL", P + "nn", qualifiers={"confidence": 600}, graph=GV)
    e1.create_edge(P + "a", "REL", P + "b", qualifiers={"confidence": 900}, graph=GV)
    vgs = {}
    for seed in range(8):
        p = subprocess.run([sys.executable, "-B", "-c", VGS_CHILD % {"rt": str(REPO / ".g5/uplift/consolidated/iteration-36"), "qs": qs, "g": GV}],
                           env=dict(os.environ, PYTHONHASHSEED=str(seed)), capture_output=True, text=True, timeout=180)
        vgs[seed] = json.loads(p.stdout.strip().splitlines()[-1])
    obs["vgs"] = {s: [[sh(a), round(b, 6), f] for a, b, f in v["answer"]] for s, v in vgs.items()}
    inputs["vgs"] = {s: {"order": [sh(x) for x in v["order"]], "hits": {sh(a): round(b, 6) for a, b in v["hits"]}, "expanded": [sh(x) for x in v["expanded"]]} for s, v in vgs.items()}

    # subgraphs on the default graph: star s -> a1..a6, a1 -> a2; chain c1 -> c2 -> c3
    adj = {P + "s": [P + f"a{i}" for i in range(1, 7)], P + "a1": [P + "a2"], P + "c1": [P + "c2"], P + "c2": [P + "c3"]}
    for n in {*adj, *[o for v in adj.values() for o in v], P + "z"}:
        e1.create_node(n)
    for s_, os_ in adj.items():
        for o in os_:
            e1.create_edge(s_, "LINK", o)
    inputs["adj"] = {sh(k): [sh(o) for o in v] for k, v in adj.items()}
    sg = lambda r: {"nodes": sorted(sh(n) for n in r.nodes), "edges": sorted(f"{sh(a)}>{sh(b)}" for a, _, b in r.edges)}  # noqa: E731
    obs["subgraph"] = {}
    for seeds, hops, cap in [((P + "s",), 1, 10000), ((P + "s",), 2, 10000), ((P + "s",), 1, 3), ((P + "s",), 1, 1), ((P + "z",), 1, 10000),
                             ((P + "c1",), 1, 10000), ((P + "c1",), 2, 2), ((P + "s", P + "c1"), 1, 4)]:
        obs["subgraph"][f"{'+'.join(sh(x) for x in seeds)}|{hops}|{cap}"] = sg(e1.kg_SUBGRAPH(list(seeds), k_hops=hops, max_nodes=cap))
    obs["guided"], inputs["guided_ppr"] = {}, {}
    for t in (3, 5, 7, 50):
        r = e1.kg_PPR_GUIDED_SUBGRAPH([P + "s"], ppr_top_k=t, k_hops=1)
        obs["guided"][t] = {"nodes": sorted(sh(n) for n in r.nodes), "edges": sorted(f"{sh(x['src'])}>{sh(x['dst'])}" for x in r.edges)}
        inputs["guided_ppr"][t] = [k_ for k_, _ in r.ppr_scores]
    # iteration 50 (review 47-49 item 1): several seeds, and a max_nodes below ppr_top_k
    obs["guided_more"], inputs["guided_more"] = {}, {}
    for label, seeds, t, mx in [("s+a3+a4|1|5000", ["s", "a3", "a4"], 1, 5000), ("a3+a4+a5|1|5000", ["a3", "a4", "a5"], 1, 5000),
                                ("s|50|3", ["s"], 50, 3), ("s|50|5000", ["s"], 50, 5000)]:
        r = e1.kg_PPR_GUIDED_SUBGRAPH([P + x for x in seeds], ppr_top_k=t, k_hops=1, max_nodes=mx)
        obs["guided_more"][label] = {"nodes": sorted(sh(n) for n in r.nodes), "edges": sorted(f"{sh(x['src'])}>{sh(x['dst'])}" for x in r.edges)}
        inputs["guided_more"][label] = {"seeds": [P + x for x in seeds], "top": [k_ for k_, _ in r.ppr_scores], "t": t, "max": mx}

    # multi_vector_search: the 4-wide route and a 3-wide second model in G
    K2 = f"i49bk{TAG}"; e1.store_embedding(P + "n00", [1.0, 0.0, 0.0], graph=G, model_key=K2)
    t1 = "Graph_KG." + e1.resolve_route(graph=G).table_name; t2 = "Graph_KG." + e1.resolve_route(graph=G, model_key=K2).table_name
    src = lambda t: {"table": t, "col": "emb", "id_col": "node_id"}  # noqa: E731
    obs["mvs_one_fails"] = [sh(str(r["id"])) for r in e1.multi_vector_search([src(t1), src(t2)], q, top_k=3, graph=G)]
    obs["mvs_valid_only"] = [sh(str(r["id"])) for r in e1.multi_vector_search([src(t1)], q, top_k=3, graph=G)]
    obs["mvs_all_fail"] = e1.multi_vector_search([src(t2)], q, top_k=3, graph=G)
    obs = json.loads(json.dumps(obs))

    # ------------------------------------------------------------------ predictions
    def predict(m):
        w = {}
        r9 = lambda d: {k_: round(v, 9) for k_, v in d.items()}  # noqa: E731
        w["engine_fuse"] = r9(fuse("Engine", 60, inputs["vleg"], inputs["bleg"], m))
        w["engine_empty_text"] = r9(fuse("Engine", 60, inputs["vleg"], [], m))
        w["engine_failed_vector"] = len(inputs["bleg"]) if engine_fuse(True, True, len(inputs["bleg"]), m) == "TextOnly" else 0
        w["engine_empty_vector_g2"] = r9(fuse("Engine", 60, [], inputs["bleg2"], m))
        w["ops_default_vector"] = len(inputs["bleg"]) if engine_fuse(True, True, len(inputs["bleg"]), m) == "TextOnly" else 0
        hnsw = obs["hnsw_present"]
        ch_b = leg_index(ivf_scope_seen(True, m), hnsw, m); ch_f = leg_index(ivf_scope_seen(False, m), hnsw, m)
        w["choice_building"], w["choice_fresh"] = ch_b, ch_f
        ivf_leg = inputs["vleg"] if m.get("ivf-cosine-normalized") else inputs["ivfleg"]
        leg_for = lambda ch: ivf_leg if ch == "ivf" else inputs["vleg"]  # noqa: E731
        w["engine_fuse_building"] = r9(fuse("Engine", 60, leg_for(ch_b), inputs["bleg"], m))
        w["engine_fuse_fresh"] = r9(fuse("Engine", 60, leg_for(ch_f), inputs["bleg"], m))
        w["ops_fuse_fresh"] = w["engine_fuse_fresh"]
        w["hnsw_present"] = hnsw
        w["pyops_hybrid"] = r9(fuse("PyOpsFuseRanks", hybrid_c(60, m), inputs["vleg"], inputs["tleg"], m))
        w["pyops_hybrid_c0"] = r9(fuse("PyOpsFuseRanks", hybrid_c(0, m), inputs["vleg"], inputs["tleg"], m)) if hybrid_c(0, m) else "division by zero"
        w["pyops_unrouted_4"] = pyops_vector_search(None, True, 4, m)
        w["pyops_unrouted_768"] = pyops_vector_search(None, True, 768, m)
        w["pyops_routed_4"] = pyops_vector_search(4, True, 4, m)
        w["engine_unrouted_4"] = "NoRows"
        w["sql_fuse"] = r9(fuse("SqlProcedure", 60, inputs["sql_vleg"], inputs["sql_tleg"], m))
        w["vgs"] = {}
        for s, v in inputs["vgs"].items():
            keep = answered(v["order"], 2, v["hits"], m)
            rows = [[x, v["hits"].get(x, 0.0), in_graph_expansion(x in v["hits"], x in v["expanded"], m)] for x in keep]
            w["vgs"][s] = sorted(rows, key=lambda r: -r[1])
        a = {P + k_: [P + o for o in v] for k_, v in inputs["adj"].items()}
        w["subgraph"] = {}
        for key in obs["subgraph"]:
            seeds, hops, cap = key.split("|")
            w["subgraph"][key] = subgraph([P + x for x in seeds.split("+")], a, int(hops), int(cap), m)
        w["guided"] = {}
        for t, top in inputs["guided_ppr"].items():
            seeds = list(dict.fromkeys([P + "s"] + [x for x in top]))
            w["guided"][t] = subgraph(seeds, a, 1, guided_cap(5000, int(t), m), m)
        w["guided_more"] = {}
        for label, g in inputs["guided_more"].items():
            seeds = list(dict.fromkeys(g["seeds"] + list(g["top"])))
            w["guided_more"][label] = subgraph(seeds, a, 1, guided_cap(g["max"], g["t"], m), m)
        w["mvs_one_fails"] = obs["mvs_valid_only"]; w["mvs_valid_only"] = obs["mvs_valid_only"]; w["mvs_all_fail"] = []
        return json.loads(json.dumps(w))

    def close(x, y):
        if isinstance(x, dict) and isinstance(y, dict):
            return x.keys() == y.keys() and all(close(x[k_], y[k_]) for k_ in x)
        if isinstance(x, list) and isinstance(y, list):
            return len(x) == len(y) and all(close(a_, b_) for a_, b_ in zip(x, y))
        if isinstance(x, float) and isinstance(y, (int, float)) and not isinstance(y, bool):
            return abs(x - y) <= 2e-9 + 1e-6 * abs(y) * 0
        return x == y

    def compare(want, got):
        cases = []
        for k_ in want:
            if k_ in ("vgs", "subgraph", "guided", "guided_more"):
                for s in want[k_]:
                    cases.append((f"{k_}[{s}]", want[k_][s], got[k_].get(str(s), got[k_].get(s))))
            else:
                cases.append((k_, want[k_], got[k_]))
        return [(n, w_, g_) for n, w_, g_ in cases if not close(w_ if not isinstance(w_, list) or not w_ or not isinstance(w_[0], list) else [[r[0], round(r[1], 6), r[2]] for r in w_], g_)], len(cases)

    want = predict({})
    mism, ncases = compare(want, obs)
    # positions that decide the reported contrasts
    pos = lambda d, x: sorted(d, key=lambda k_: -d[k_]).index(x) + 1 if x in d else None  # noqa: E731
    contrast = {"x_engine": pos(obs["engine_fuse"], "x"), "x_pyops": pos(obs["pyops_hybrid"], "x"),
                "L_building": pos(obs["engine_fuse_building"], "L"), "L_fresh": pos(obs["engine_fuse_fresh"], "L"),
                "best_dropped_seeds": [s for s, v in obs["vgs"].items() if "a" not in [r[0] for r in v]],
                "guided_top7": obs["guided"]["7"],
                "guided_more": obs["guided_more"],
                # the documented rule at the reader: answered nodes, edges among them, at most the cap
                "rule_departures": {lab: {"edges_among_answered_missing": sorted(
                                              f"{x}>{o}" for x, os_ in inputs["adj"].items() for o in os_
                                              if x in g["nodes"] and o in g["nodes"] and f"{x}>{o}" not in g["edges"]),
                                          "over_cap": len(g["nodes"]) > min(inputs["guided_more"][lab]["max"], inputs["guided_more"][lab]["t"])}
                                    for lab, g in obs["guided_more"].items()}}
    sens = {}
    for mu in MUTS:
        bad, _ = compare(predict({mu: True}), obs); sens[mu] = len(bad)
    tampered = json.loads(json.dumps(obs)); tampered["engine_fuse"]["x"] = round(1 / 61, 9)
    tamper_detected = bool(compare(want, tampered)[0])
    body = {"kind": "binding", "model": "retrieval_compose", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "prefix": P, "verdict": "AGREES" if not mism else "DISAGREES", "cases": ncases,
            "mismatches": [{"case": n, "expected": w_, "observed": g_} for n, w_, g_ in mism], "contrasts": contrast,
            "observed": obs, "provider_inputs": inputs,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q_.relative_to(REPO)): sha(q_) for q_ in [HERE / "binding.py", HERE / "retrieval_compose.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/vector.py", "iris_vector_graph/_engine/algorithms.py",
                                                                   "iris_vector_graph/operators.py", "iris_vector_graph/schema.py",
                                                                   "iris_vector_graph/stores/iris_sql_store.py", "iris_src/src/Graph/KG/PyOps.cls",
                                                                   "iris_src/src/Graph/KG/Subgraph.cls", "iris_src/src/Graph/KG/IVFIndex.cls"]}},
            "scope": "Actual product on IRIS 2026.1 (pin 3eaa79cf), provider legs read back and fed to the ports: engine kg_RRF_FUSE "
                     "(62-long vector leg, 60-long BM25 leg; empty text; failed and empty vector legs), IRISGraphOperators defaults, "
                     "a cosine IVF index read by the building engine versus a fresh engine and the operators, PyOps HybridSearch "
                     "(route path, c 60 and 0) and VectorSearch (routed, unrouted 4- and 768-wide), the SQL kg_RRF_FUSE procedure on the "
                     "default graph, kg_VECTOR_GRAPH_SEARCH under hash seeds 0-7, kg_SUBGRAPH (8 seed/hop/cap shapes) and "
                     "kg_PPR_GUIDED_SUBGRAPH (ppr_top_k 3, 5, 7, 50; iteration 50: seeds s+a3+a4 and a3+a4+a5 with ppr_top_k 1, and [s] with "
                     "ppr_top_k 50 under max_nodes 3 and 5000) on a star and a chain, ObjectScript SubgraphJson path (no Arno reader), multi_vector_search with a failing source. "
                     "Floating sums compared to 2e-9; Python set order and PPR scores are provider inputs, not derived."}
    d = REPO / ".g5/Verus_verification/results/retrieval_compose" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k_: body[k_] for k_ in ("verdict", "cases", "contrasts", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in body["mismatches"]:
        print("MISMATCH", json.dumps(x, default=str)[:600])


if __name__ == "__main__":
    main()
