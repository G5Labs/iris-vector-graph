"""traversal_strategy binding: fresh nodes, edges and named graphs on the run-isolated continuation fixture
(ivg-cont-20261117-iris, USER, prefix i57a_<tag>_, graphs i57ag<tag>...).

The binding writes an edge history through the product API (create_node, create_edge, set_multigraph, delete_edge,
store_embedding), keeps its own copy of that history (graph, source, type, target, key), and reads the real readers:
store.execute_bfs (as selected, and with the product's _SqlBfsFallbackAdapter forced on the instance),
store._sql_bfs_fallback (raw walk), execute_vl_ends, shortest_path_length, execute_shortest_path, engine.khop,
store._select_bfs_strategy (real, and with Arno premises injected on the instance), execute_knn_vec. Every expected
answer is a Python port of traversal_strategy.rs applied to the history this binding wrote, never to the product's
output. Each mutation mirrors a control and must change at least one prediction; one tampered observation must be
detected. Ordinary data only."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("TS_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
P = f"i57a_{TAG}_"; G = f"i57ag{TAG}"
MUTS = ["bfs_lists_source", "bfs_every_depth", "sql_revisits", "graph_unscoped", "cap_zero_cuts_all",
        "cap_passed_to_adapter", "arno_named_graph", "arno_any_direction", "arno_ignores_other_graphs",
        "no_fallback_on_empty", "length_in_reversed", "trail_repeats_edges", "khop_walks_both", "knn_unrouted_legacy",
        "sql_unknown_dir_as_out", "types_ignore_case", "bfsfast_case_insensitive", "esp_no_reversal", "length_both_as_out"]


def dir_text(t, m):
    """(BFSFast walks it, the SQL fallback's direction, ReachTypes' direction) for the text execute_bfs is handed."""
    os_walks = t in ("out", "in", "both") or (m.get("bfsfast_case_insensitive") and t.lower() in ("out", "in", "both"))
    if t in ("out", "outbound") or (m.get("sql_unknown_dir_as_out") and t not in ("in", "inbound", "both")):
        sql = "out"
    elif t in ("in", "inbound"):
        sql = "in"
    else:
        sql = "both"
    low = {"outbound": "out", "inbound": "in"}.get(t if m.get("types_ignore_case") else t.lower(), t if m.get("types_ignore_case") else t.lower())
    typ = low if low in ("out", "in") else "both"
    return os_walks, sql, typ


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ port of traversal_strategy.rs
def nbrs(E, g, preds, d, u, m):
    """step(es, q, u, v): the nodes one edge carries u to (graph, type, direction)."""
    out = set()
    for (eg, s, p, o, k) in E:
        if eg != g and not m.get("graph_unscoped"):
            continue
        if preds and p not in preds:
            continue
        if d in ("out", "both") and s == u:
            out.add(o)
        if d in ("in", "both") and o == u:
            out.add(s)
    return out


def levels(E, g, preds, d, src, hops, m):
    """sql_new / os_front: the frontier at each hop (visited-checked), and os_walked: every node walked at each hop."""
    front = {0: {src}}; visited = {src}; walked = {}
    for h in range(1, hops + 1):
        w = set()
        for u in front[h - 1]:
            w |= nbrs(E, g, preds, d, u, m)
        walked[h] = w
        new = w if m.get("sql_revisits") else (w - visited)
        front[h] = new; visited |= new
        if not new:
            for j in range(h + 1, hops + 1):
                walked[j] = set(); front[j] = set()
            break
    return front, walked


def reach_type(E, g, preds, d, depth, v):
    """ReachTypes: the first type (collation) of the edges reaching v from a node one hop nearer."""
    best = []
    for (eg, s, p, o, k) in E:
        if eg != g or (preds and p not in preds):
            continue
        if d in ("out", "both") and o == v and depth.get(s) == depth[v] - 1:
            best.append(p)
        if d in ("in", "both") and s == v and depth.get(o) == depth[v] - 1:
            best.append(p)
    return min(best) if best else ""


def bfs_rows(E, g, preds, dt, src, hops, cap, m):
    """os_row (= sql_row by theorem_os_rows_eq_sql_rows), typed, ordered by (depth, id), then cut."""
    os_walks, sqld, typd = dir_text(dt, m)
    d = (dt.lower() if os_walks else sqld)
    front, walked = levels(E, g, preds, d, src, hops, m)
    if m.get("cap_passed_to_adapter") and cap:
        walked = capped_walk(E, g, preds, d, src, hops, cap, m)
    depth = {}
    for h in sorted(walked):
        for v in walked[h]:
            if (v != src or m.get("bfs_lists_source")) and v not in depth:
                depth[v] = h
    full = dict(depth); full.setdefault(src, 0)
    if m.get("bfs_every_depth"):
        rows = sorted([[v, h] for h in walked for v in walked[h] if v != src], key=lambda r: (r[1], r[0]))
    else:
        rows = sorted([[v, h] for v, h in depth.items()], key=lambda r: (r[1], r[0]))
    rows = [[v, h, reach_type(E, g, preds, typd, {**full, v: h}, v)] for v, h in rows]
    if m.get("cap_zero_cuts_all"):
        return rows[:cap]
    return rows[:cap] if cap else rows


def capped_walk(E, g, preds, d, src, hops, cap, m):
    """BFSFast with maxResults = cap: counts walked edges, stops after the frontier node that reaches the cap."""
    walked = {}; seen = {src}; front = [src]; count = 0
    for h in range(1, hops + 1):
        w = set(); nxt = set()
        for u in sorted(front):
            if count >= cap:
                break
            for (eg, s, p, o, k) in sorted(E):
                if eg != g or (preds and p not in preds):
                    continue
                for a, b in ([(s, o)] if d in ("out", "both") else []) + ([(o, s)] if d in ("in", "both") else []):
                    if a == u:
                        count += 1; w.add(b)
                        if b not in seen:
                            nxt.add(b)
        walked[h] = w
        if count >= cap or not nxt:
            break
        seen |= nxt; front = list(nxt)
    return walked


def sql_raw(E, g, preds, d, src, hops, m):
    """_sql_bfs_fallback's raw (id, hop) rows: sql_new for h >= 1."""
    front, _ = levels(E, g, preds, d, src, hops, m)
    return sorted([[v, h] for h in front if h >= 1 for v in front[h]])


def vl_ends(E, g, preds, d, src, minh, maxh, m):
    """vl_end: each node reached by a trail (no edge twice) of length minh..maxh, at its least such length."""
    best = {}
    edges = [e for e in E if e[0] == g and (not preds or e[2] in preds)]

    def go(u, used, l):
        if minh <= l <= maxh and (u not in best or l < best[u]):
            best[u] = l
        if l >= maxh:
            return
        for i, (eg, s, p, o, k) in enumerate(edges):
            if i in used and not m.get("trail_repeats_edges"):
                continue
            nxt = []
            if d in ("out", "both") and s == u:
                nxt.append(o)
            if d in ("in", "both") and o == u and not (d == "both" and s == o):
                nxt.append(s)
            for v in nxt:
                go(v, used | {i}, l + 1)
    go(src, frozenset(), 0)
    return sorted([[v, l] for v, l in best.items()])


def has_len(E, g, preds, d, src, dst, maxh, m):
    if src == dst:
        return 0
    front, _ = levels(E, g, preds, d, src, maxh, m)
    for h in range(1, maxh + 1):
        if dst in front.get(h, set()):
            return h
    return -1


def esp_len(E, g, preds, d, src, dst, maxh, m):
    if m.get("esp_no_reversal") and d == "in":
        return -1                     # ShortestPathJson walks out and both only: 'in' finds no path
    return has_len(E, g, preds, "out", dst, src, maxh, m) if d == "in" else has_len(E, g, preds, d, src, dst, maxh, m)


def spl_len(E, g, preds, d, src, dst, maxh, m):
    dd = d if m.get("length_in_reversed") else ("both" if d == "both" and not m.get("length_both_as_out") else "out")
    if m.get("length_in_reversed") and d == "in":
        return has_len(E, g, preds, "out", dst, src, maxh, m)
    return has_len(E, g, preds, dd, src, dst, maxh, m)


def khop_nodes(E, seed, hops, seed_is_node, m):
    d = "both" if m.get("khop_walks_both") else "out"
    front, _ = levels(E, "", [], d, seed, hops, m)
    rest = set().union(*[front[h] for h in front if h >= 1]) - {seed}
    has_out = bool(nbrs(E, "", [], d, seed, m))
    return sorted(([seed] if (seed_is_node or has_out) else []) + sorted(rest))


def select(arno, arno_bfs, named, d, only_default, m):
    if d.lower() not in ("out", "outbound") and not m.get("arno_any_direction"):
        return "_ObjectScriptBfsAdapter"
    od = True if m.get("arno_ignores_other_graphs") else only_default
    if (not named or m.get("arno_named_graph")) and arno and arno_bfs and od:
        return "_ArnoBfsAdapter"
    return "_ObjectScriptBfsAdapter"


def falls_back(walked_edges, m):
    return (walked_edges == 0) and not m.get("no_fallback_on_empty")


# ------------------------------------------------------------------ fixture
def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c); st = e._store
    from iris_vector_graph.stores import iris_sql_store as S
    E = []                      # the history this binding wrote: (graph, s, p, o, key)
    made = set()

    def node(n, g=None):
        if (n, g) in made:
            return
        try:
            e.create_node(n, labels=["I57A"], graph=g)
        except Exception:
            pass
        made.add((n, g))

    def edge(a, p, b, g=None):
        """create_edge: one edge per (graph, s, p, o); a duplicate answers False and adds none (its documented return)."""
        node(P + a, g); node(P + b, g)
        if e.create_edge(P + a, p, P + b, graph=g) is not False:
            E.append((g or "", P + a, p, P + b, 0))

    def cypher_edge(a, p, b, g):
        """Cypher CREATE in a multigraph-mode graph: a new relationship (the next edge key) every time."""
        node(P + a, g); node(P + b, g)
        e.execute_cypher(f"USE GRAPH '{g}' MATCH (a), (b) WHERE a.id = '{P + a}' AND b.id = '{P + b}' CREATE (a)-[:{p}]->(b)")
        key = sum(1 for x in E if x[:4] == (g, P + a, p, P + b))
        E.append((g, P + a, p, P + b, key))

    gn = G + "n"; gm = G + "m"; gk = G + "k"
    mix = [("s", "R", "a"), ("s", "Q", "b"), ("a", "R", "c"), ("b", "R", "c"), ("c", "R", "s"), ("s", "R", "s"),
           ("a", "Q", "d"), ("d", "R", "e"), ("b", "Q", "a")]
    for a, p, b in mix:
        edge(a, p, b)
        edge(a, p, b, gn)
    edge("c", "R", "x")                                   # default graph only: graph=gn must not reach x
    edge("u", "R", "v"); edge("v", "R", "u")              # vl-ends cycle back to the source
    edge("h", "R", "i")                                   # single edge, walked undirected
    edge("p1", "R", "p2"); edge("p2", "R", "p3")          # shortest-path chain
    edge("g1", "R", "g2", gn); edge("g2", "R", "g3", gn)  # a path only gn holds
    node(P + "lone")                                       # a node with no edge
    e.set_multigraph(gm, True)
    cypher_edge("ms", "R", "mt", gm); cypher_edge("ms", "R", "mt", gm); cypher_edge("mt", "R", "mu", gm)
    edge("dup", "R", "dup2"); edge("dup", "R", "dup2")    # a duplicate create_edge: one edge
    mg_rows = None
    cur = c.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {st._ivg_schema}.rdf_edges WHERE s = ? AND o_id = ? AND graph_id = ?", [P + "ms", P + "mt", gm])
    mg_rows = int(cur.fetchone()[0])
    cur.execute(f"SELECT COUNT(*) FROM {st._ivg_schema}.rdf_edges WHERE s = ? AND o_id = ?", [P + "dup", P + "dup2"])
    dup_rows = int(cur.fetchone()[0]); cur.close()

    calls = {"fallback": 0}
    orig_fb = st._sql_bfs_fallback

    def counted(*a, **kw):
        calls["fallback"] += 1
        return orig_fb(*a, **kw)
    st._sql_bfs_fallback = counted

    obs, plans = {}, {}

    def bfs_case(name, src, preds, hops, d, cap, g):
        calls["fallback"] = 0
        r = st.execute_bfs(P + src, preds, hops, d, cap, graph=g)
        obs[name] = {"rows": [list(map(str, x[:1])) + [int(x[1]), str(x[2])] for x in (r.rows or [])], "fallback_calls": calls["fallback"],
                     "strategy": type(st._select_bfs_strategy(g, direction=d)).__name__}
        plans[name] = ("bfs", src, preds, hops, d, cap, g or "", tuple(E))

    def bfs_forced_sql(name, src, preds, hops, d, cap, g):
        saved = st._select_bfs_strategy
        st._select_bfs_strategy = lambda graph=None, direction="out": S._SqlBfsFallbackAdapter(st)
        try:
            r = st.execute_bfs(P + src, preds, hops, d, cap, graph=g)
        finally:
            st._select_bfs_strategy = saved
        raw = orig_fb(P + src, preds, hops, d, 0, graph=g)
        obs[name] = {"rows": [[str(x[0]), int(x[1]), str(x[2])] for x in (r.rows or [])],
                     "raw": sorted([[str(x[0]), int(x[1])] for x in (raw.rows or [])])}
        plans[name] = ("bfs_sql", src, preds, hops, d, cap, g or "", tuple(E))

    for d in ("out", "in", "both"):
        for preds in ([], ["R"]):
            for hops in (1, 2, 3):
                tag = f"{d}_{'R' if preds else 'any'}_{hops}"
                bfs_case(f"os_{tag}", "s", preds, hops, d, 0, None)
                bfs_forced_sql(f"sql_{tag}", "s", preds, hops, d, 0, None)
    bfs_case("os_named_out_3", "s", [], 3, "out", 0, gn)
    bfs_forced_sql("sql_named_out_3", "s", [], 3, "out", 0, gn)
    bfs_case("os_cap2", "s", [], 3, "out", 2, None)
    bfs_case("os_cap3", "s", [], 3, "out", 3, None)
    bfs_case("os_cap0", "s", [], 3, "out", 0, None)
    bfs_case("os_in_from_d", "d", [], 3, "in", 0, None)
    bfs_case("os_lone_fallback", "lone", [], 2, "out", 0, None)
    bfs_case("os_multigraph", "ms", [], 2, "out", 0, gm)
    bfs_case("os_cycle_u", "u", [], 3, "out", 0, None)
    for t in ("OUT", "sideways", "outbound", "inbound"):
        bfs_case(f"os_dirtext_{t}", "s", [], 2, t, 0, None)

    def vl_case(name, src, preds, d, mn, mx, g):
        r = st.execute_vl_ends(P + src, preds, d, mn, mx, graph=g)
        obs[name] = {"ends": sorted([[str(x[0]), int(x[1])] for x in r.rows])}
        plans[name] = ("vl", src, preds, d, mn, mx, g or "", tuple(E))
    vl_case("vl_cycle_u_1_2", "u", [], "out", 1, 2, None)
    vl_case("vl_cycle_u_1_3", "u", [], "out", 1, 3, None)
    vl_case("vl_single_both_1_2", "h", [], "both", 1, 2, None)
    vl_case("vl_parallel_both_1_2", "ms", [], "both", 1, 2, gm)
    vl_case("vl_mix_out_2_3", "s", [], "out", 2, 3, None)
    vl_case("vl_mix_both_1_3", "s", ["R"], "both", 1, 3, None)

    def sp_case(name, a, b, d, g):
        n = st.shortest_path_length(P + a, P + b, [], 5, d, graph=g)
        r = st.execute_shortest_path(P + a, P + b, [], 5, d, False, graph=g)
        obs[name] = {"spl": int(n), "esp": int(r.rows[0][1]) if r.rows else -1}
        plans[name] = ("sp", a, b, d, g or "", tuple(E))
    sp_case("sp_out_p1_p3", "p1", "p3", "out", None)
    sp_case("sp_both_p3_p1", "p3", "p1", "both", None)
    sp_case("sp_in_p3_p1", "p3", "p1", "in", None)
    sp_case("sp_in_p1_p3", "p1", "p3", "in", None)
    sp_case("sp_multigraph", "ms", "mu", "out", gm)
    sp_case("sp_named_g1_g3", "g1", "g3", "out", gn)
    sp_case("sp_default_g1_g3", "g1", "g3", "out", None)

    def khop_case(name, seed, hops, seed_is_node):
        k = e.khop(P + seed, hops=hops, max_nodes=10_000)
        obs[name] = {"nodes": sorted(map(str, k["nodes"]))}
        plans[name] = ("khop", seed, hops, seed_is_node, tuple(E))
    khop_case("khop_s_2", "s", 2, True)
    khop_case("khop_s_1", "s", 1, True)
    khop_case("khop_named_only_g1", "g1", 2, True)

    # B7: write, read, delete, read
    edge("w1", "R", "w2")
    bfs_case("b7_after_write", "w1", [], 2, "out", 0, None)
    khop_case("b7_khop_after_write", "w1", 2, True)
    e.delete_edge(P + "w1", "R", P + "w2")
    E[:] = [x for x in E if not (x[0] == "" and x[1:4] == (P + "w1", "R", P + "w2"))]
    bfs_case("b7_after_delete", "w1", [], 2, "out", 0, None)
    khop_case("b7_khop_after_delete", "w1", 2, True)

    # strategy selection: the fixture as it is, then Arno premises injected on this instance
    real = {"detect_arno": bool(st._detect_arno()), "only_default_graph": bool(st._only_default_graph())}
    obs["select_real"] = {f"{n}_{d}": type(st._select_bfs_strategy(gr, direction=d)).__name__
                          for n, gr in (("default", None), ("named", gn)) for d in ("out", "in", "both")}
    plans["select_real"] = ("select_real",)
    inj = {}
    sv = (st._detect_arno, dict(st._arno_capabilities), st._only_default_graph)
    try:
        st._detect_arno = lambda: True; st._arno_capabilities = {"bfs": True}
        for od in (True, False):
            st._only_default_graph = (lambda v: (lambda: v))(od)
            for n, gr in (("default", None), ("named", gn)):
                for d in ("out", "in", "both"):
                    inj[f"od{int(od)}_{n}_{d}"] = type(st._select_bfs_strategy(gr, direction=d)).__name__
    finally:
        st._detect_arno, st._arno_capabilities, st._only_default_graph = sv[0], sv[1], sv[2]
    obs["select_injected"] = inj; plans["select_injected"] = ("select_injected",)

    # N1: knn over a routed graph, and a (graph, model) pair with no route
    vecs = {"k1": [1.0, 0.0], "k2": [0.8, 0.6], "k3": [0.0, 1.0]}
    knn_err = None
    try:
        for n, v in vecs.items():
            node(P + n, gk)
            e.store_embedding(P + n, v + [0.0] * 766, graph=gk)
        qv = [0.9, 0.1] + [0.0] * 766
        r1 = st.execute_knn_vec(qv, 2, None, graph=gk)
        r0 = st.execute_knn_vec(qv, 2, None, graph=gk, model_key="i57a_no_such_model")
        obs["knn_routed"] = {"ids": [str(x[0]) for x in r1.rows]}
        obs["knn_unrouted"] = {"ids": [str(x[0]) for x in r0.rows]}
    except Exception as ex:
        knn_err = f"{type(ex).__name__}: {ex}"[:300]
        obs["knn_routed"] = {"ids": None}; obs["knn_unrouted"] = {"ids": None}
    plans["knn_routed"] = ("knn", True); plans["knn_unrouted"] = ("knn", False)
    st._sql_bfs_fallback = orig_fb
    c.close()

    def cos(a, b):
        import math
        return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))

    def predict(m):
        out = {}
        E = None
        for name, pl in plans.items():
            k = pl[0]
            if k in ("bfs", "bfs_sql"):
                _, src, preds, hops, d, cap, g, E = pl
                rows = bfs_rows(E, g, preds, d, P + src, hops, cap, m)
                if k == "bfs":
                    os_walks, _, _ = dir_text(d, m)
                    front, walked = levels(E, g, preds, d.lower() if os_walks else "out", P + src, hops, m)
                    walked_edges = len(walked.get(1, set())) if os_walks else 0
                    out[name] = {"rows": rows, "fallback_calls": 1 if falls_back(walked_edges, m) else 0,
                                 "strategy": select(real["detect_arno"], False, bool(g), d, real["only_default_graph"], m)}
                else:
                    out[name] = {"rows": rows, "raw": sql_raw(E, g, preds, d, P + src, hops, m)}
            elif k == "vl":
                _, src, preds, d, mn, mx, g, E = pl
                out[name] = {"ends": vl_ends(E, g, preds, d, P + src, mn, mx, m)}
            elif k == "sp":
                _, a, b, d, g, E = pl
                out[name] = {"spl": spl_len(E, g, [], d, P + a, P + b, 5, m), "esp": esp_len(E, g, [], d, P + a, P + b, 5, m)}
            elif k == "khop":
                _, seed, hops, sn, E = pl
                out[name] = {"nodes": khop_nodes(E, P + seed, hops, sn, m)}
            elif k == "select_real":
                out[name] = {f"{n}_{d}": select(real["detect_arno"], False, n == "named", d, real["only_default_graph"], m)
                             for n in ("default", "named") for d in ("out", "in", "both")}
            elif k == "select_injected":
                out[name] = {f"od{int(od)}_{n}_{d}": select(True, True, n == "named", d, od, m)
                             for od in (True, False) for n in ("default", "named") for d in ("out", "in", "both")}
            elif k == "knn":
                qv = [0.9, 0.1]
                ranked = [P + n for n, v in sorted(vecs.items(), key=lambda kv: (-cos(qv, kv[1]), kv[0]))][:2]
                out[name] = {"ids": ranked if (pl[1] or m.get("knn_unrouted_legacy")) else []}
        return out

    exp = predict({})
    mism = [{"case": n, "observed": obs[n], "expected": exp[n]} for n in exp if obs[n] != exp[n]]
    sens = {}
    for mm in MUTS:
        pm = predict({mm: True})
        sens[mm] = sorted(n for n in pm if pm[n] != obs[n])
    tam = json.loads(json.dumps(obs)); tam["os_out_any_3"]["rows"][0][1] += 1
    tamper_detected = tam["os_out_any_3"] != exp["os_out_any_3"]
    body = {"kind": "binding", "model": "traversal_strategy", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "prefix": P, "graphs": [gn, gm, gk],
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(exp), "mismatches": mism,
            "observed": obs, "edge_history": [list(x) for x in E], "edge_history_by_case": {n: len(pl[-1]) for n, pl in plans.items() if isinstance(pl[-1], tuple)}, "multigraph_rows_ms_mt": mg_rows, "duplicate_create_edge_rows": dup_rows,
            "fixture_premises": real, "knn_error": knn_err,
            "sensitivities_detected_cases": {k: len(v) for k, v in sens.items()}, "sensitivity_cases": sens,
            "all_sensitivities_detected": all(len(v) > 0 for v in sens.values()),
            "tamper": {"field": "os_out_any_3.rows[0].hops += 1", "detected": tamper_detected},
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "traversal_strategy.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/stores/iris_sql_store.py", "iris_vector_graph/_engine/algorithms.py",
                                                                    "iris_vector_graph/_engine/query.py",
                                                                    "iris_src/src/Graph/KG/TraversalBFS.cls", "iris_src/src/Graph/KG/TraversalPaths.cls",
                                                                    "iris_src/src/Graph/KG/VarLength.cls", "iris_src/src/Graph/KG/Traversal.cls"]}},
            "scope": "Actual IRISGraphStore readers and engine.khop on IRIS 2026.1 (pin 3eaa79cf), Arno library absent. Expected answers are the "
                     "port of traversal_strategy.rs applied to the edge history this binding wrote. The SQL fallback is forced by replacing "
                     "_select_bfs_strategy on this store instance with the product's own _SqlBfsFallbackAdapter; Arno selection is observed "
                     "only through _select_bfs_strategy with _detect_arno / _arno_capabilities / _only_default_graph injected on the instance "
                     "(the Arno walk itself is not run). Cypher callers are not exercised."}
    d = REPO / ".g5/Verus_verification/results/traversal_strategy" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "tamper", "knn_error", "fixture_premises", "elapsed_s")}))
    print("receipt", d / "receipt.json")
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str)[:1500])


if __name__ == "__main__":
    main()
