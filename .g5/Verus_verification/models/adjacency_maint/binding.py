"""adjacency_maint binding: histories of writes and deletes on the run-isolated continuation fixture
(ivg-cont-20261117-iris, USER, prefix i57b_<tag>_, graphs i57bg<tag>...).

The binding writes each history through the real product API (engine.create_node / create_edge / set_edge_weight /
delete_edge / delete_node / delete_nodes_by_prefix / set_multigraph / sync, store.write_nodes / write_edges /
delete_edges, Cypher CREATE and DELETE r), recording the history as the model's ops (Create / DelRow / Update /
EraseTriple / EraseNodes / Sync). A port of adjacency_maint.rs applied to that history (never to the product's output)
predicts every ^KG("out") entry of this run's nodes (leaf, keyed children, "#"), the in mirror, the label index,
Graph.KG.Adj.Count degrees, khop2_count_fast / exact, the ^NKG edge after a delete held by another graph, and the
BFS reach of named graphs. Observed globals are compared with the prediction; mutations mirroring the model's
controls must each change at least one case; a tamper of one observed deciding field must be detected.
The only product outputs consumed as history are multigraph ekeys (read off the rows right after a Cypher CREATE,
the identity of the row the history wrote) and which ekey a `LIMIT 1` Cypher DELETE r removed."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("AM_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["remove_keyed_takes_triple", "put_keyed_drops_others", "leaf_highest", "plain_remove_keeps",
        "erase_ignores_graph", "held_elsewhere_ignored", "fresh_ignores_stamp", "label_erase_by_label",
        "reweight_ignored", "exact_is_sum", "transition_new_weight", "create_ignores_mode"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------- port of adjacency_maint.rs ----------------
def lowest_w(m, mu):
    k = (max if mu.get("leaf_highest") else min)(m)
    return m[k]


def canon(multi, rows, mu):
    if not rows:
        return None
    if multi and len(rows) >= 2:
        return (lowest_w(rows, mu), dict(rows))
    return (next(iter(rows.values())), {})


def put_keyed(e, others, k, w, mu):
    if e is None:
        return (w, {})
    leaf, kids = e
    if not kids and not others:
        return (w, {})
    if not kids:
        base = {} if mu.get("put_keyed_drops_others") else ({x: (w if mu.get("transition_new_weight") else leaf) for x in others}
                                                            if len(others) == 1 else dict(others))
    else:
        base = dict(kids)
    base[k] = w
    return (lowest_w(base, mu), base)


def remove_keyed(e, others, k, mu):
    if mu.get("remove_keyed_takes_triple"):
        return None
    if e is None:
        return None
    leaf, kids = e
    if not kids:
        return e if others else None
    if k not in kids:
        return e
    k2 = {x: v for x, v in kids.items() if x != k}
    if len(k2) >= 2:
        return (lowest_w(k2, mu), k2)
    if len(k2) == 1:
        return (next(iter(k2.values())), {})
    return (leaf, {})


def row_put(multi, e, others, k, w, mu):
    return put_keyed(e, others, k, w, mu) if (multi and not mu.get("create_ignores_mode")) else (w, {})


def row_remove(multi, e, others, k, mu):
    if multi:
        return remove_keyed(e, others, k, mu)
    return e if mu.get("plain_remove_keeps") else None


def row_update(e, k, w, mu):
    if e is None or mu.get("reweight_ignored"):
        return e
    leaf, kids = e
    if k in kids:
        k2 = dict(kids); k2[k] = w
        return (lowest_w(k2, mu), k2)
    return (w, kids)


def rebuild(multi, rows, order, mu):
    e = None
    for k in order:
        e = row_put(multi, e, {x: v for x, v in rows.items() if x != k}, k, rows[k], mu)
    return e


class Port:
    """rows_at / adj_at for every triple the history touched; labels; the ^NKG edge decision."""

    def __init__(self, multi, mu):
        self.multi, self.mu = multi, mu
        self.rows, self.adj, self.labels, self.nodes = {}, {}, set(), set()

    def apply(self, op):
        mu, kind = self.mu, op[0]
        if kind == "create":
            _, t, k, w = op
            rows = self.rows.setdefault(t, {})
            self.adj[t] = row_put(t[0] in self.multi, self.adj.get(t), dict(rows), k, w, mu)
            rows[k] = w
            self.nodes |= {(t[0], t[1]), (t[0], t[3])}
        elif kind == "delrow":
            _, t, k = op
            rows = self.rows.get(t, {})
            if k in rows:
                del rows[k]
                self.adj[t] = row_remove(t[0] in self.multi, self.adj.get(t), dict(rows), k, mu)
        elif kind == "update":
            _, t, k, w = op
            rows = self.rows.get(t, {})
            if k in rows and rows[k] != w:
                rows[k] = w
                self.adj[t] = row_update(self.adj.get(t), k, w, mu)
        elif kind in ("erase_triple", "erase_nodes"):
            for t in list(self.rows):
                if (kind == "erase_triple" and t == op[1]) or (kind == "erase_nodes" and (t[0] == op[1] or mu.get("erase_ignores_graph"))
                                                               and (t[1] in op[2] or t[3] in op[2])):
                    self.rows[t] = {}; self.adj[t] = None
            if kind == "erase_nodes":
                g, ids = op[1], op[2]
                gone = {x for x in self.labels if x[0] == g and x[2] in ids}
                if mu.get("label_erase_by_label"):
                    gone |= {x for x in self.labels if x[0] == g and any(y[1] == x[1] for y in gone)}
                self.labels -= gone
                self.nodes -= {(g, n) for n in ids}
        elif kind == "label":
            self.labels.add((op[1], op[2], op[3])); self.nodes.add((op[1], op[3]))
        elif kind == "sync":
            for t, rows in self.rows.items():
                self.adj[t] = rebuild(t[0] in self.multi, rows, sorted(rows), mu)

    def entries(self, prefix):
        out = {}
        for t, e in self.adj.items():
            if e is not None and t[1].startswith(prefix):
                out[repr(t)] = [e[0], {str(k): v for k, v in sorted(e[1].items())}, len(e[1]) if e[1] else None]
        return dict(sorted(out.items()))

    def count(self, g, s, p):
        n = 0
        for t, e in self.adj.items():
            if e is not None and t[0] == g and t[1] == s and t[2] == p:
                n += len(e[1]) if e[1] else 1
        return n

    def out(self, g, s, p):
        return sorted(t[3] for t, e in self.adj.items() if e is not None and t[0] == g and t[1] == s and t[2] == p)

    def two_hop(self, s, p):
        mids = self.out(0, s, p)
        tgt = set()
        for m in mids:
            tgt |= set(self.out(0, m, p))
        walk = len(tgt - {s} - set(mids))
        total = sum(self.count(0, m, p) for m in mids)
        return walk, total

    def reach(self, g, src, hops=3):
        seen, front = {src}, {src}
        for _ in range(hops):
            nxt = set()
            for t, e in self.adj.items():
                if e is not None and t[0] == g and t[1] in front and t[3] not in seen:
                    nxt.add(t[3])
            seen |= nxt; front = nxt
        return sorted(seen - {src})


def nkg_edge_after_remove(before, had, built, held, mu):
    if had and built and (not held or mu.get("held_elsewhere_ignored")):
        return False
    return before


def marks_stale(gkey, left, built, interned, mu):
    return (gkey != 0 or mu.get("mark_gone_default")) and not left and built and interned


def fast_answer(fresh, total, walk, mu):
    return total if ((fresh or mu.get("fresh_ignores_stamp")) and total > 0) else walk


def exact_answer(fresh, stored, walk, total, mu):
    stored = total if mu.get("exact_is_sum") else stored
    return stored if ((fresh or mu.get("fresh_ignores_stamp")) and stored > 0) else walk


# ---------------- reading the product ----------------
def children(nat, *subs):
    out, k = [], ""
    while True:
        k = nat.nextSubscript(False, *subs, k)
        if k is None or k == "":
            return out
        out.append(k)


def gkey(g):
    return 0 if not g else g


def read_entries(nat, keys, triples, prefix):
    out = {}
    for t in triples:
        g, s, p, o = t
        if not s.startswith(prefix):
            continue
        k = gkey(g)
        if not nat.isDefined("^KG", "out", k, s, p, o):
            continue
        leaf = nat.get("^KG", "out", k, s, p, o)
        kids = {str(c): nat.get("^KG", "out", k, s, p, o, c) for c in children(nat, "^KG", "out", k, s, p, o) if str(c) != "#"}
        h = nat.get("^KG", "out", k, s, p, o, "#") if nat.isDefined("^KG", "out", k, s, p, o, "#") else None
        mirror = nat.isDefined("^KG", "in", k, o, p, s)
        out[repr(t)] = [_num(leaf), {c: _num(v) for c, v in sorted(kids.items())}, None if h is None else int(h)]
        if not mirror:
            out[repr(t)].append("NO_IN_MIRROR")
    return dict(sorted(out.items()))


def _num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except Exception:
        return v


def main():
    import iris
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c)
    store = getattr(e, "_store", None) or e._e._store
    P = f"i57b_{TAG}_"; GA, GB, GM = f"i57bg{TAG}a", f"i57bg{TAG}b", f"i57bg{TAG}m"
    hist, obs, notes = [], {}, {}
    multi = {GM}
    R, Q = "R57", "Q57"

    def T(g, s, p, o):
        return (g or 0, s, p, o)

    def rec(op):
        hist.append(op)

    def create(s, p, o, w, g=None):
        for n in (s, o):
            e.create_node(n, graph=g)
        e.create_edge(s, p, o, weight=w, graph=g)
        rec(("create", T(g, s, p, o), 0, w))

    def node(n, labels, g=None):
        e.create_node(n, labels=labels, graph=g)
        for l in labels:
            rec(("label", g or 0, l, n))

    obs["index_kind"] = str(nat.classMethodValue("Graph.KG.Adjacency", "IndexKind", "Graph.KG.rdfedges"))
    obs["arno_loaded"] = bool(_safe(lambda: nat.classMethodValue("Graph.KG.NKGAccel", "Available")))

    # ---- default graph: D3 (engine delete_edge, store delete_edges), R1 reweight, R2 two-hop, labels ----
    a, b, cc, d, x = (P + n for n in ("a", "b", "c", "d", "x"))
    node(a, ["L57"]); node(b, ["L57"])
    create(a, R, b, 2); create(a, R, cc, 1); create(b, R, cc, 1); create(cc, R, d, 4)
    store.write_nodes([{"id": x, "labels": ["L57"]}]); rec(("label", 0, "L57", x))
    store.write_edges([{"source": d, "predicate": R, "target": x}, {"source": x, "predicate": R, "target": a}])
    rec(("create", T(None, d, R, x), 0, 1)); rec(("create", T(None, x, R, a), 0, 1))
    e.set_edge_weight(a, R, b, 5); rec(("update", T(None, a, R, b), 0, 5))
    obs["reweight_before_sync"] = read_entries(nat, None, [T(None, a, R, b)], P)
    # two-hop shape on Q: s2 -> m1, m2; m1 -> y, s2; m2 -> y
    s2, m1, m2, y = (P + n for n in ("s2", "m1", "m2", "y"))
    for u, v in ((s2, m1), (s2, m2), (m1, y), (m1, s2), (m2, y)):
        create(u, Q, v, 1)

    # ---- named graphs: D2 / D1 / D4 ----
    n1, n2, keep = P + "n_1", P + "n_2", P + "keep"
    for g in (GA, GB):
        node(n1, ["L57"], g); node(n2, ["L57"], g); node(keep, ["L57"], g)
        create(n1, R, n2, 1, g); create(n2, R, keep, 1, g); create(keep, R, n1, 1, g)

    # ---- multigraph: D3 parallel edges through Cypher ----
    ms, mt, mu_ = P + "ms", P + "mt", P + "mu"
    e.set_multigraph(GM, True)
    for n in (ms, mt, mu_):
        e.create_node(n, graph=GM)

    def cy_create(s, o, w):
        before = set(_ekeys(c, s, R, o, GM))
        e.execute_cypher(f"USE GRAPH '{GM}' MATCH (a {{id: '{s}'}}), (b {{id: '{o}'}}) CREATE (a)-[:{R} {{weight: {w}}}]->(b)", {})
        new = sorted(set(_ekeys(c, s, R, o, GM)) - before)
        rec(("create", T(GM, s, R, o), new[0], w))
        return new[0]

    k1 = cy_create(ms, mt, 7); k2 = cy_create(ms, mt, 3); cy_create(ms, mu_, 2)
    obs["multi_two"] = read_entries(nat, None, [T(GM, ms, R, mt)], P)
    obs["count_ms_two"] = int(nat.classMethodValue("Graph.KG.Adj", "Count", GM, ms, R))

    # first sync: ^NKG built from ^KG (records whether the sync path writes ^NKG at all)
    e.sync(); rec(("sync",))
    obs["nkg_built_after_sync"] = bool(nat.isDefined("^NKG", "$meta", "nodeCount"))

    # D2 at ^NKG: delete n1->n2 in GA while GB holds it (engine.delete_edge: a row DELETE, RowRemove -> Remove)
    def nkg_edge(s, p, o):
        si, oi, pi = (_get(nat, "^NKG", "$NI", s), _get(nat, "^NKG", "$NI", o), _get(nat, "^NKG", "$LI", p))
        if si is None or oi is None or pi is None:
            return False
        return bool(nat.isDefined("^NKG", -1, int(si), -(int(pi) + 1), int(oi)))

    obs["nkg_n1n2_before"] = nkg_edge(n1, R, n2)
    e.delete_edge(n1, R, n2, graph=GA); rec(("delrow", T(GA, n1, R, n2), 0))
    obs["nkg_n1n2_after_ga"] = nkg_edge(n1, R, n2)
    obs["bfs_ga_n1"] = _bfs(store, n1, GA); obs["bfs_gb_n1"] = _bfs(store, n1, GB)
    # x->a in the default graph only: delete it (not held elsewhere) -> its ^NKG edge goes
    obs["nkg_xa_before"] = nkg_edge(x, R, a)
    e.delete_edge(x, R, a); rec(("delrow", T(None, x, R, a), 0))
    obs["nkg_xa_after"] = nkg_edge(x, R, a)

    # D3: Cypher DELETE r of one of two parallel edges (LIMIT 1), then which ekey went
    before = set(_ekeys(c, ms, R, mt, GM))
    e.execute_cypher(f"USE GRAPH '{GM}' MATCH (a {{id: '{ms}'}})-[r:{R}]->(b {{id: '{mt}'}}) WITH r LIMIT 1 DELETE r", {})
    gone = sorted(before - set(_ekeys(c, ms, R, mt, GM)))
    notes["cypher_delete_removed_ekeys"] = gone
    obs["cypher_delete_r_rows"] = len(gone)   # DELETE r of one relationship: the model's DelRow is one row
    for k in gone:
        rec(("delrow", T(GM, ms, R, mt), k))
    obs["multi_after_delete_r"] = read_entries(nat, None, [T(GM, ms, R, mt)], P)
    obs["count_ms_after_delete_r"] = int(nat.classMethodValue("Graph.KG.Adj", "Count", GM, ms, R))
    obs["bfs_gm_ms"] = _bfs(store, ms, GM)
    k3 = cy_create(ms, mt, 9); k4 = cy_create(ms, mt, 1)

    # engine.delete_edge on a default triple (b->c) and store.delete_edges (d->x)
    e.delete_edge(b, R, cc); rec(("delrow", T(None, b, R, cc), 0))
    store.delete_edges([(d, R, x)]); rec(("erase_triple", T(None, d, R, x)))

    # D1 / D4: delete_nodes_by_prefix in GA; delete_node of cc in the default graph
    e.delete_nodes_by_prefix(P + "n_", graph=GA); rec(("erase_nodes", GA, frozenset({n1, n2})))
    e.delete_node(cc, graph=None); rec(("erase_nodes", 0, frozenset({cc})))
    obs["bfs_ga_keep"] = _bfs(store, keep, GA); obs["bfs_gb_keep"] = _bfs(store, keep, GB)

    # snapshot before the second sync (R1), then sync, snapshot again
    triples = sorted({op[1] for op in hist if op[0] in ("create", "delrow", "update", "erase_triple")}, key=repr)
    obs["entries_before_sync"] = read_entries(nat, None, triples, P)
    obs["labels_before_sync"] = _labels(nat, [0, GA, GB], "L57", P)
    e.sync(); rec(("sync",))
    obs["entries_after_sync"] = read_entries(nat, None, triples, P)
    obs["labels_after_sync"] = _labels(nat, [0, GA, GB], "L57", P)
    obs["counts"] = {f"{g}|{s}": int(nat.classMethodValue("Graph.KG.Adj", "Count", gkey(g), s, R))
                     for g, s in ((None, a), (GB, n1), (GA, keep), (GM, ms))}

    # R2: two-hop right after sync (retry when another worker's write moved ^KG("__version") meanwhile)
    for _ in range(3):
        v0 = str(nat.get("^KG", "__version")); f0 = str(_get(nat, "^IVG.BuiltFrom", "deg2p"))
        fe0 = str(_get(nat, "^IVG.BuiltFrom", "deg2p_exact"))
        fast, exact = e.khop2_count_fast(s2, Q), e.khop2_count_exact(s2, Q)
        v1 = str(nat.get("^KG", "__version"))
        if v0 == v1 == f0 == fe0:
            break
        e.sync()
    notes["two_hop_stamps_fresh"] = v0 == v1 == f0 == fe0
    obs["two_hop_after_sync"] = [fast, exact]
    create(P + "z1", R, P + "z2", 1)   # a later edge write
    obs["two_hop_after_write"] = [e.khop2_count_fast(s2, Q), e.khop2_count_exact(s2, Q)]
    # R3: ^NKG after the deletes and sync, by names, for this run's default/named triples (merged view)
    obs["nkg_by_names"] = sorted({f"{s}|{p}|{o}" for (g, s, p, o) in triples if nkg_edge(s, p, o)})
    c.close()

    def predict(mu):
        port = Port({GM}, mu); out = {}
        idx_first_sync = hist.index(("sync",))
        for i, op in enumerate(hist):
            port.apply(op)
            if op == ("create", T(GM, ms, R, mu_), k_of(hist, T(GM, ms, R, mu_)), 2) and "multi_two" not in out:
                out["multi_two"] = {k: v for k, v in port.entries(P).items() if k == repr(T(GM, ms, R, mt))}
                out["count_ms_two"] = port.count(GM, ms, R)
            if op == ("update", T(None, a, R, b), 0, 5):
                out["reweight_before_sync"] = {k: v for k, v in port.entries(P).items() if k == repr(T(None, a, R, b))}
            if i == idx_first_sync:
                built = True
                out["nkg_built_after_sync"] = built
                out["nkg_n1n2_before"] = True
                out["nkg_xa_before"] = True
            if op == ("delrow", T(None, x, R, a), 0):
                held = any(port.adj.get(T(g, x, R, a)) is not None for g in (GA, GB, GM))
                out["nkg_xa_after"] = nkg_edge_after_remove(True, True, True, held, mu)
            if op == ("delrow", T(GA, n1, R, n2), 0):
                out["bfs_ga_n1"] = port.reach(GA, n1); out["bfs_gb_n1"] = port.reach(GB, n1)
                held = port.adj.get(T(GB, n1, R, n2)) is not None
                out["nkg_n1n2_after_ga"] = nkg_edge_after_remove(True, True, True, held, mu)
            if op[0] == "delrow" and op[1] == T(GM, ms, R, mt) and "multi_after_delete_r" not in out:
                out["cypher_delete_r_rows"] = 1
                out["multi_after_delete_r"] = {k: v for k, v in port.entries(P).items() if k == repr(T(GM, ms, R, mt))}
                out["count_ms_after_delete_r"] = port.count(GM, ms, R)
                out["bfs_gm_ms"] = port.reach(GM, ms)
            if op == ("erase_nodes", 0, frozenset({cc})):
                out["bfs_ga_keep"] = port.reach(GA, keep); out["bfs_gb_keep"] = port.reach(GB, keep)
                out["entries_before_sync"] = port.entries(P)
                out["labels_before_sync"] = sorted(f"{g}|{n}" for (g, l, n) in port.labels if l == "L57" and n.startswith(P))
            if op == ("sync",) and i != idx_first_sync:
                out["entries_after_sync"] = port.entries(P)
                out["labels_after_sync"] = sorted(f"{g}|{n}" for (g, l, n) in port.labels if l == "L57" and n.startswith(P))
                out["counts"] = {f"{g}|{s}": port.count(gkey(g), s, R) for g, s in ((None, a), (GB, n1), (GA, keep), (GM, ms))}
                walk, total = port.two_hop(s2, Q)
                fresh = True
                out["two_hop_after_sync"] = [fast_answer(fresh, total, walk, mu), exact_answer(fresh, walk, walk, total, mu)]
                out["nkg_by_names"] = sorted({f"{t[1]}|{t[2]}|{t[3]}" for t in triples if any(
                    e_ is not None and (tt[1], tt[2], tt[3]) == (t[1], t[2], t[3]) for tt, e_ in port.adj.items())})
            if op[0] == "create" and op[1] == T(None, P + "z1", R, P + "z2"):
                walk, total = port.two_hop(s2, Q)
                stamp_total, stamp_walk = total, walk
                out["two_hop_after_write"] = [fast_answer(False, total, walk, mu), exact_answer(False, walk, walk, total, mu)]
        return out

    def k_of(h, t):
        for op in h:
            if op[0] == "create" and op[1] == t:
                return op[2]

    for k in ("bfs_ga_n1", "bfs_gb_n1", "bfs_gm_ms", "bfs_ga_keep", "bfs_gb_keep"):
        obs[k] = sorted(obs[k]) if isinstance(obs[k], list) else obs[k]
    exp = predict({})
    norm = lambda v: json.loads(json.dumps(v, sort_keys=True, default=str))
    observed = {k: norm(obs[k]) for k in exp}
    expected = {k: norm(v) for k, v in exp.items()}
    mism = [{"case": k, "observed": observed[k], "expected": expected[k]} for k in expected if observed[k] != expected[k]]
    sens = {}
    for m in MUTS:
        pm = {k: norm(v) for k, v in predict({m: True}).items()}
        sens[m] = sorted(k for k in pm if pm[k] != observed[k])
    tampered = json.loads(json.dumps(observed))
    key = repr(T(GM, ms, R, mt))
    tampered["multi_after_delete_r"][key][0] = tampered["multi_after_delete_r"][key][0] + 1 if key in tampered["multi_after_delete_r"] else 0
    tamper_detected = tampered["multi_after_delete_r"] != expected["multi_after_delete_r"]
    body = {"kind": "binding", "model": "adjacency_maint", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "prefix": P, "graphs": [GA, GB, GM],
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(expected), "mismatches": mism,
            "observed": observed, "expected": expected, "history": [list(map(str, op)) for op in hist], "notes": notes,
            "index_kind": obs["index_kind"], "arno_loaded": obs["arno_loaded"],
            "sensitivities_detected_cases": {m: len(v) for m, v in sens.items()}, "sensitivity_cases": sens,
            "all_sensitivities_detected": all(len(v) > 0 for v in sens.values()),
            "tamper": {"field": f"multi_after_delete_r[{key}].leaf + 1", "detected": tamper_detected},
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "adjacency_maint.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in [
                           "iris_vector_graph/stores/iris_sql_store.py", "iris_vector_graph/_engine/nodes_edges.py",
                           "iris_vector_graph/_engine/schema.py", "iris_vector_graph/_engine/query.py", "iris_vector_graph/_engine/admin.py",
                           "iris_src/src/Graph/KG/Adjacency.cls", "iris_src/src/Graph/KG/TraversalBuild.cls",
                           "iris_src/src/Graph/KG/Eraser.cls", "iris_src/src/Graph/KG/TraversalKHop.cls", "iris_src/src/Graph/KG/Adj.cls"]}},
            "scope": "Real engine/store/Cypher writes on IRIS 2026.1 (pin 3eaa79cf), USER namespace, declared adjacency index "
                     f"({obs['index_kind']}); default graph, two named graphs and one multigraph. Integer weights. sync() is namespace-wide "
                     "(other prefixes' rows are fixture data). Multigraph ekeys and the ekey a LIMIT 1 DELETE r removed are read off the "
                     "rows as history identity. The two-hop stamps can be moved by a concurrent worker's write: notes.two_hop_stamps_fresh "
                     "records whether the after-sync read saw current stamps."}
    dd = REPO / ".g5/Verus_verification/results/adjacency_maint" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    dd.mkdir(parents=True); (dd / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "tamper", "elapsed_s", "index_kind", "arno_loaded")}, default=str))
    print("RECEIPT", dd / "receipt.json")
    for m in mism:
        print("MISMATCH", json.dumps(m, default=str))


def _takes_graph(e):
    return True


def _safe(f):
    try:
        return f()
    except Exception:
        return None


def _get(nat, *subs):
    try:
        return nat.get(*subs) if nat.isDefined(*subs) % 10 == 1 else None
    except Exception:
        return None


def _ekeys(c, s, p, o, g):
    cur = c.cursor()
    cur.execute("SELECT ekey FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND COALESCE(graph_id, '') = ?", [s, p, o, g or ""])
    return [int(r[0]) for r in cur.fetchall()]


def _bfs(store, src, g):
    try:
        r = store.execute_bfs(src, [], 3, "out", 0, graph=g)
        return sorted(row[0] for row in r.rows)
    except Exception as exc:
        return f"error: {str(exc)[:120]}"


def _labels(nat, graphs, label, prefix):
    out = []
    for g in graphs:
        for n in children(nat, "^KG", "label", gkey(g), label):
            if str(n).startswith(prefix):
                out.append(f"{g}|{n}")
    return sorted(out)


if __name__ == "__main__":
    main()
