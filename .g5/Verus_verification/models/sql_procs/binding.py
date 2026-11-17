"""Binding for sql_procs (iteration 53, Part B) on the run-isolated continuation fixture.

Iteration 56 (review 53-55 F4): the namespace is now I56Q; the privilege verdict is computed from each user's recorded
grants (table, schema and column privileges, a role, %All) by a port of `require`, never hand-labelled; MatchEdges is
also called with every spelling of the default graph (SQL '', CHAR(0), a bound '', 0, '0', NULL) beside a name.

The SQL procedures read or write a whole namespace, so the binding drops and re-creates its own namespace I56Q (from
%SYS, in the container ivg-cont-20261117-iris only), runs setup, writes one history through the public engine API
(nodes and weighted edges in graphs g, g2, gz and the default graph; temporal edges, a temporal-only predicate, an
explicit edge with a timestamp, a structural row deleted by SQL), and calls the SQL entry points `MatchEdges`,
`MatchEdgesAllGraphs`, `DijkstraPath`, `backfill_temporal_rows` and `rebuild_edge_indices` as _SYSTEM and as eight
users i56q_* with different grants (created in %SYS for the run and deleted after it). It also runs the same Cypher hop
with IVG_EDGESCAN unset and 1, and the Cypher CALL ivg.shortestPath.weighted beside the SQL entry. Every expected
answer comes from a Python port of sql_procs.rs applied to the history the binding wrote (and, for the search, a
port of the documented rule: the cheapest path within maxCost and maxHops, weights <= 0 as 1), never from the
product's answers. Mutations mirror the model's 12 controls; one deciding observation is tampered.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/sql_procs/binding.py)
"""
import hashlib, heapq, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

NS = "I56Q"
PW = "i56qPass9"
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
OK_TAIL = 'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!'
MUTS = ["shard-partitions", "default-reads-every-graph", "empty-predicate-matches-none", "all-graphs-default-only",
        "no-select-check", "scan-exposes-weight", "sql-entry-unchecked", "nul-read-as-empty", "count-written-rows",
        "optout-backfilled", "backfill-marks-existing", "rebuild-refusal-answers-zero",
        # iteration 56 (review 53-55 F4 and the MatchEdges graph argument)
        "column-grant-counts", "schema-grant-ignored", "roles-ignored", "all-not-shortcut", "first-table-only",
        "nul-not-normalized", "empty-not-default", "zero-text-is-a-name", "readers-check-nodes"]
# Iteration 56 (review 53-55 F4): the verdict is no longer hand-labelled. Each user's grants are recorded as IRIS
# records them (own table / schema / column privileges, roles with their grants, %All) and the expected verdict is
# computed from them by the port of `require` below. Users and the role are created for the run and deleted after it.
SCH = "Graph_KG"
T_NODES, T_EDGES = "Graph_KG.nodes", "Graph_KG.rdf_edges"
EXEC = "GRANT EXECUTE ON SCHEMA Graph_KG TO {u}"
# user: (caller as recorded: all, own {table,schema,column} privilege pairs, role names), the SQL grants made, %BUILD_INDEX
USERS = {
    "i56q_noselect": ({"all": False, "table": {(T_NODES, "s")}, "schema": set(), "column": set(), "roles": []},
                      [EXEC, "GRANT SELECT ON Graph_KG.nodes TO {u}"], False),
    "i56q_select": ({"all": False, "table": set(), "schema": {(SCH, "s")}, "column": set(), "roles": []},
                    [EXEC, "GRANT SELECT ON SCHEMA Graph_KG TO {u}"], False),
    "i56q_writer": ({"all": False, "table": set(), "schema": {(SCH, "s"), (SCH, "i"), (SCH, "u"), (SCH, "d")}, "column": set(), "roles": []},
                    [EXEC, "GRANT SELECT ON SCHEMA Graph_KG TO {u}", "GRANT INSERT, UPDATE, DELETE ON SCHEMA Graph_KG TO {u}"], False),
    "i56q_table": ({"all": False, "table": {(T_EDGES, "s")}, "schema": set(), "column": set(), "roles": []},
                   [EXEC, "GRANT SELECT ON Graph_KG.rdf_edges TO {u}"], False),
    "i56q_column": ({"all": False, "table": set(), "schema": set(), "column": {(T_EDGES, "s")}, "roles": []},
                    [EXEC, "GRANT SELECT (s, p, o_id) ON Graph_KG.rdf_edges TO {u}"], False),
    "i56q_role": ({"all": False, "table": set(), "schema": set(), "column": set(), "roles": ["i56q_r"]},
                  [EXEC, "GRANT i56q_r TO {u}"], False),
    "i56q_nodesins": ({"all": False, "table": {(T_NODES, "i")}, "schema": {(SCH, "s")}, "column": set(), "roles": []},
                      [EXEC, "GRANT SELECT ON SCHEMA Graph_KG TO {u}", "GRANT INSERT ON Graph_KG.nodes TO {u}"], False),
    "i56q_all": ({"all": True, "table": set(), "schema": set(), "column": set(), "roles": ["%All"]},
                 [], True),
}
ROLES = {"i56q_r": {"table": {(T_EDGES, "s")}, "schema": set(), "column": set()}}
ROLE_GRANTS = {"i56q_r": ["GRANT SELECT ON Graph_KG.rdf_edges TO i56q_r"]}


def check_priv(gr, t, a, m):
    """P-CHECKPRIV: a table or schema privilege counts; a column privilege does not."""
    if (t, a) in gr["table"]:
        return True
    if not m.get("schema-grant-ignored") and (SCH, a) in gr["schema"]:
        return True
    return bool(m.get("column-grant-counts") and (t, a) in gr["column"])


def holds_priv(c, t, a, m):
    if check_priv(c, t, a, m):
        return True
    if m.get("roles-ignored"):
        return False
    return any(check_priv(ROLES[r], t, a, m) for r in c["roles"] if r in ROLES)


def require(c, tables, acts, m):
    """RequireSelect / RequireWrite: %All passes; else the first (table, action) not held is named."""
    if c["all"] and not m.get("all-not-shortcut"):
        return "pass"
    for i, t in enumerate(tables):
        if i > 0 and m.get("first-table-only"):
            break
        for a in acts:
            if not holds_priv(c, t, a, m):
                return f"refused:{ {'s': 'SELECT', 'i': 'INSERT'}[a]} {t}"
    return "pass"


# the edges written: (s, p, o, weight or None, graph or None)
E = [("a", "P", "b", 1.0, "g"), ("b", "P", "c", 1.0, "g"), ("c", "P", "d", 1.0, "g"), ("a", "P", "d", 10.0, "g"),
     ("a", "Q", "e", 1.0, "g"), ("e", "Q", "d", None, "g"),
     ("a", "P", "b", 2.0, "g2"), ("a", "P", "b2", 1.0, "g2"),
     ("s", "Z", "t", 0.0, "gz"), ("s", "Y", "u", -2.0, "gz"),
     ("x", "P", "y", 3.0, None)]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ port of sql_procs.rs
def gkey(graph):
    return "" if graph in (None, "", 0) else graph


def graph_arg_key(raw, m):
    """EdgeScan.MatchEdges 52-58 on the raw argument as the body receives it: CHAR0 ($Char(0), SQL's ''), "" (NULL,
    omitted, a bound ''), 0, "0", or a name. "" is the default graph's key; "<nul>"/"<empty>" are graphs nobody writes."""
    g = raw
    if g == "CHAR0" and not m.get("nul-not-normalized"):
        g = ""
    if g == "" and not m.get("empty-not-default"):
        g = 0
    if g == "CHAR0":
        return "<nul>"
    if g == "":
        return "<empty>"
    if g in (0, "0"):
        return "<zero-text>" if (g == "0" and m.get("zero-text-is-a-name")) else ""
    return g


def scan_hit(a, key, src, pred, shard, m):
    g, s, p, o, w = a
    if m.get("shard-partitions") and shard != 0:
        return False
    if m.get("default-reads-every-graph"):
        if not (g == key or key == ""):
            return False
    elif g != key:
        return False
    if src and s != src:
        return False
    if m.get("empty-predicate-matches-none"):
        return p == pred
    return not pred or p == pred


def all_hit(a, src, pred, shard, m):
    g, s, p, o, w = a
    if m.get("all-graphs-default-only") and g != "":
        return False
    return (not src or s == src) and (not pred or p == pred)


def scan_w(w):
    return 1.0 if w is None else float(w)


def norm_arcs(arcs):
    return sorted([[g, s, p, o, scan_w(w)] for g, s, p, o, w in arcs])


def match_edges(adj, src, pred, shard, graph, m):
    return norm_arcs([a for a in adj if scan_hit(a, gkey(graph), src, pred, shard, m)])


def match_edges_arg(adj, src, pred, raw, m):
    return norm_arcs([a for a in adj if scan_hit(a, graph_arg_key(raw, m), src, pred, 0, m)])


def match_all(adj, src, pred, shard, m):
    return norm_arcs([a for a in adj if all_hit(a, src, pred, shard, m)])


def gate(holds, t, m):
    return t if (holds or m.get("no-select-check")) else "refused"


def rel_weight(scan, w, m):
    if scan and not m.get("scan-exposes-weight"):
        return None
    return None if w is None else float(w)


def dijkstra_json(src, dst, wp, direction, m, search):
    """src/dst as the body sees them: '' is SQL's $Char(0) ("\x00"), unless the mutation reads it as ''."""
    if not m.get("sql-entry-unchecked"):
        if wp not in ("", "weight"):
            return "raises"
        if direction not in ("out", "in", "both"):
            return "raises"
    s = ("" if m.get("nul-read-as-empty") else "\x00") if src == "" else src
    d = ("" if m.get("nul-read-as-empty") else "\x00") if dst == "" else dst
    if s == "" or d == "":
        return {}
    if s == d:
        return {"nodes": [s], "totalCost": 0.0}
    return search()


def rule_search(adj, src, dst, max_cost, max_hops, direction, preds, graph):
    """The documented weighted path: the cheapest path within maxCost and (maxHops > 0) maxHops; weight <= 0 or none
    costs 1; 'in' walks against the edges; preds empty = every type."""
    key = gkey(graph)
    nbr = {}
    for g, s, p, o, w in adj:
        if g != key or (preds and p not in preds):
            continue
        c = 1.0 if (w is None or w <= 0) else float(w)
        if direction in ("out", "both"):
            nbr.setdefault(s, []).append((o, c))
        if direction in ("in", "both"):
            nbr.setdefault(o, []).append((s, c))
    bound = max_hops > 0
    best = {}
    pq = [(0.0, 0, src, [src])]
    while pq:
        cost, hops, node, path = heapq.heappop(pq)
        if node == dst:
            return {"nodes": path, "totalCost": cost}
        if best.get(node, 1e18) <= hops:
            continue
        best[node] = hops
        if bound and hops >= max_hops:
            continue
        for o, c in nbr.get(node, []):
            nc = cost + c
            if nc > max_cost or o in path:
                continue
            heapq.heappush(pq, (nc, hops + 1 if bound else 0, o, path + [o]))
    return {}


class Bf:
    """The backfill's stores: the structural writer gives each structural temporal triple a marked row when it has
    none; an explicit create_edge an unmarked one; a temporal-only predicate none."""
    def __init__(self):
        self.tout = set(); self.optout = set(); self.rows = {}

    def temporal(self, g, s, p, o):
        self.tout.add((g, s, p, o))
        if (g, p) not in self.optout and (g, s, p, o) not in self.rows:
            self.rows[(g, s, p, o)] = True

    def explicit(self, g, s, p, o):
        self.rows.setdefault((g, s, p, o), False)

    def structural(self, m):
        return {t for t in self.tout if m.get("optout-backfilled") or (t[0], t[2]) not in self.optout}

    def backfill(self, m):
        st = self.structural(m)
        count = len([t for t in st if t not in self.rows]) if m.get("count-written-rows") else len(st)
        for t in st:
            if t not in self.rows:
                self.rows[t] = True
            elif m.get("backfill-marks-existing"):
                self.rows[t] = True
        return count

    def view(self):
        return sorted([[g, s, p, o, mk] for (g, s, p, o), mk in self.rows.items()])


def rebuild(schema_kind, build_priv, m):
    if schema_kind == "not_identifier":
        return "raises_not_identifier"
    if schema_kind == "missing":
        return "raises_naming_table"
    if build_priv:
        return 4
    return 0 if m.get("rebuild-refusal-answers-zero") else "raises_naming_table"


# ------------------------------------------------------------------ the fixture
def iris_sys(script):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", "%SYS"],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=300).stdout


def recreate_namespace():
    out = iris_sys(f'Set ns="{NS}", dir="/usr/irissys/mgr/{NS.lower()}/"\n'
                   'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
                   'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
                   'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
                   'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
                   'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
                   'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
                   + OK_TAIL)
    assert "RESULT OK" in out, out


def connect(user="_SYSTEM", pw="SYS"):
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username=user, password=pw)
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close(); raise RuntimeError("fixture identity mismatch")
    return c


def q1(cur, sql, args=()):
    try:
        cur.execute(sql, list(args)); r = cur.fetchone()
        return r[0] if r else None
    except Exception as x:
        return f"EXC {str(x)[:900]}"


def classify_err(v):
    if not (isinstance(v, str) and v.startswith("EXC")):
        return None
    if "is not an SQL identifier" in v:
        return "raises_not_identifier"
    if "rebuilding the indexes of" in v:
        return "raises_naming_table"
    if "lacks" in v or "not privileged" in v or "SQLCODE=-99" in v:
        return "refused"
    if "ivg.shortestPath.weighted" in v:
        return "raises"
    return "other:" + v[:160]


def refusal_name(v):
    import re as _re
    if isinstance(v, str) and v.startswith("EXC"):
        mm = _re.search(r"lacks (SELECT|INSERT) on ([A-Za-z_.]+)", v)
        return f"refused:{mm.group(1)} {mm.group(2)}" if mm else "other:" + v[:160]
    return "pass"


def scan_obs(v):
    c = classify_err(v)
    if c:
        return c
    return sorted([[d["g"], d["s"], d["p"], d["o"], float(d["w"])] for d in json.loads(v)])


def path_obs(v):
    c = classify_err(v)
    if c:
        return c
    d = json.loads(v)
    return {} if not d else {"nodes": d["nodes"], "totalCost": float(d["totalCost"])}


def main():
    t0 = time.time()
    from iris_vector_graph.engine import IRISGraphEngine
    recreate_namespace()
    c = connect(); cur = c.cursor()
    e = IRISGraphEngine(c, embedding_dimension=8, native_cypher=False)
    e.initialize_schema()
    adj = []
    for s_, p_, o_, w_, g_ in E:
        for n in (s_, o_):
            e.create_node(n, graph=g_)
        e.create_edge(s_, p_, o_, weight=w_, graph=g_)
        adj.append((gkey(g_), s_, p_, o_, w_))
    got = {}
    # ---- the scans
    SRC = ["a", "", "x", "s"]; PRED = ["P", "", "Q"]; SHARD = [0, 1, 7]; GRAPH = ["g", "g2", "", "gz"]
    for src in SRC:
        for pred in PRED:
            for shard in SHARD:
                for graph in GRAPH:
                    got[f"me|{src}|{pred}|{shard}|{graph}"] = scan_obs(q1(cur, "SELECT Graph_KG.MatchEdges(?,?,?,?)", [src, pred, shard, graph]))
            got[f"meall|{src}|{pred}"] = scan_obs(q1(cur, "SELECT Graph_KG.MatchEdgesAllGraphs(?,?,0)", [src, pred]))
    for k, sql in (("zero", "SELECT Graph_KG.MatchEdges('','P',0,0)"), ("null", "SELECT Graph_KG.MatchEdges('','P',0,NULL)"),
                   ("omitted", "SELECT Graph_KG.MatchEdges('','P')")):
        got[f"me_default_{k}"] = scan_obs(q1(cur, sql))
    # iteration 56: every spelling of the default graph, literally (SQL '' reaches the body as $Char(0)), bound, as
    # CHAR(0), 0 and '0'; beside a name
    GSPELL = {"lit_empty": ("SELECT Graph_KG.MatchEdges('','P',0,'')", (), "CHAR0"),
              "char0": ("SELECT Graph_KG.MatchEdges('','P',0,CHAR(0))", (), "CHAR0"),
              "bound_empty": ("SELECT Graph_KG.MatchEdges('','P',0,?)", ("",), "BOUND_EMPTY"),
              "zero": ("SELECT Graph_KG.MatchEdges('','P',0,0)", (), 0),
              "zero_text": ("SELECT Graph_KG.MatchEdges('','P',0,'0')", (), "0"),
              "bound_zero_text": ("SELECT Graph_KG.MatchEdges('','P',0,?)", ("0",), "0"),
              "null": ("SELECT Graph_KG.MatchEdges('','P',0,NULL)", (), ""),
              "name_g": ("SELECT Graph_KG.MatchEdges('','P',0,'g')", (), "g")}
    for k, (sql, args, _) in GSPELL.items():
        got[f"me_spell_{k}"] = scan_obs(q1(cur, sql, args))
    # ---- the Cypher hop on both plans
    for flag in ("0", "1"):
        os.environ["IVG_EDGESCAN"] = flag
        for k, q in (("nograph", "MATCH (a {id: 'a'})-[r:P]->(b) RETURN b.id AS o%s, r.weight AS w"),
                     ("default", "USE GRAPH '' MATCH (a {id: 'x'})-[r:P]->(b) RETURN b.id AS o%s, r.weight AS w"),
                     ("named", "USE GRAPH 'g' MATCH (a {id: 'a'})-[r:P]->(b) RETURN b.id AS o%s, r.weight AS w")):
            r = e.execute_cypher(q.replace("%s", flag))
            got[f"hop_{k}_{flag}"] = sorted([[x[0], None if x[1] is None else float(x[1])] for x in r.rows], key=lambda z: (z[0], z[1] is None, z[1] or 0)) if not r.error else f"error:{r.error}"
    os.environ.pop("IVG_EDGESCAN", None)
    # ---- DijkstraPath and the CALL
    DJ = {"defaults": ("a", "d", "", 9999, 10, "out", "", "g"), "hops1": ("a", "d", "", 9999, 1, "out", "", "g"),
          "hops2": ("a", "d", "", 9999, 2, "out", "", "g"), "hops0": ("a", "d", "", 9999, 0, "out", "", "g"),
          "hopsneg": ("a", "d", "", 9999, -1, "out", "", "g"), "cost1_5": ("a", "d", "", 1.5, 10, "out", "", "g"),
          "cost2": ("a", "d", "", 2, 10, "out", "", "g"), "cost1_99": ("a", "d", "", 1.99, 10, "out", "", "g"),
          "predsP": ("a", "d", "", 9999, 10, "out", '["P"]', "g"), "preds_empty": ("a", "d", "", 9999, 10, "out", "[]", "g"),
          "out_from_d": ("d", "a", "", 9999, 10, "out", "", "g"), "in_from_d": ("d", "a", "", 9999, 10, "in", "", "g"),
          "both_from_d": ("d", "a", "", 9999, 10, "both", "", "g"), "sideways": ("a", "d", "", 9999, 10, "sideways", "", "g"),
          "wp_cost": ("a", "d", "cost", 9999, 10, "out", "", "g"), "wp_weight": ("a", "d", "weight", 9999, 10, "out", "", "g"),
          "graph_default": ("a", "d", "", 9999, 10, "out", "", ""), "graph_g2": ("a", "b", "", 9999, 10, "out", "", "g2"),
          "zero_weight": ("s", "t", "", 9999, 10, "out", "", "gz"), "neg_weight": ("s", "u", "", 9999, 10, "out", "", "gz"),
          "same": ("a", "a", "", 9999, 10, "out", "", "g"), "same_unknown_cost0": ("zz", "zz", "", 0, 10, "out", "", "g"),
          "empty_both": ("", "", "", 9999, 10, "out", "", "g"), "empty_src": ("", "d", "", 9999, 10, "out", "", "g"),
          "unknown_dst": ("a", "nope", "", 9999, 10, "out", "", "g"), "default_x_y": ("x", "y", "", 9999, 10, "out", "", "")}
    for k, a in DJ.items():
        got[f"dj_{k}"] = path_obs(q1(cur, "SELECT Graph_KG.DijkstraPath(?,?,?,?,?,?,?,?)", list(a)))
    for k, q in (("defaults", "USE GRAPH 'g' CALL ivg.shortestPath.weighted('a', 'd') YIELD path RETURN path"),
                 ("hops1", "USE GRAPH 'g' CALL ivg.shortestPath.weighted('a', 'd', 'weight', 9999, 1) YIELD path RETURN path")):
        r = e.execute_cypher(q)
        p = r.rows[0][0] if r.rows else {}
        got[f"call_{k}"] = {"nodes": p["nodes"], "totalCost": float(p["totalCost"])} if p else {}
    # ---- backfill
    bf = Bf()
    T = 1_700_000_000
    def temporal(s_, p_, o_, ts, g_=None, w=1.0):
        e.create_edge_temporal(s_, p_, o_, timestamp=ts, weight=w, graph=g_); bf.temporal(gkey(g_), s_, p_, o_)
    def rows_view():
        cur.execute("SELECT graph_id, s, p, o_id, qualifiers FROM Graph_KG.rdf_edges WHERE p IN ('T', 'TO') ORDER BY graph_id, s")
        return sorted([[r[0] or "", r[1], r[2], r[3], bool(r[4] and json.loads(r[4]).get("temporal"))] for r in cur.fetchall()])
    temporal("ta", "T", "tb", T, "g", 2.0); temporal("ta", "T", "tb", T + 1, "g", 3.0); temporal("tc", "T", "td", T, "g")
    temporal("ua", "T", "ub", T)
    e.set_temporal_structural("TO", False, graph="g"); bf.optout.add(("g", "TO"))
    temporal("oa", "TO", "ob", T, "g")
    BFSTEPS = []
    got["bf_rows_0"] = rows_view(); BFSTEPS.append(("rows", None))
    got["bf_count_1"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()"); BFSTEPS.append(("count", None))
    got["bf_rows_1"] = rows_view(); BFSTEPS.append(("rows", None))
    got["bf_count_2"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()"); BFSTEPS.append(("count", None))
    cur.execute("DELETE FROM Graph_KG.rdf_edges WHERE graph_id = 'g' AND s = 'tc' AND p = 'T'"); BFSTEPS.append(("delete", ("g", "tc", "T", "td")))
    got["bf_rows_2"] = rows_view(); BFSTEPS.append(("rows", None))
    got["bf_count_3"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()"); BFSTEPS.append(("count", None))
    got["bf_rows_3"] = rows_view(); BFSTEPS.append(("rows", None))
    e.create_edge("ea", "T", "eb", graph="g"); BFSTEPS.append(("explicit", ("g", "ea", "T", "eb")))
    e.create_edge_temporal("ea", "T", "eb", timestamp=T, graph="g"); BFSTEPS.append(("temporal", ("g", "ea", "T", "eb")))
    got["bf_count_4"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()"); BFSTEPS.append(("count", None))
    got["bf_rows_4"] = rows_view(); BFSTEPS.append(("rows", None))
    bf_initial = (set(bf.tout), set(bf.optout), dict(bf.rows))
    # ---- rebuild
    for k, a in (("ok", "'Graph_KG'"), ("lower", "'graph_kg'"), ("default", ""), ("not_identifier", "'Graph_KG; DROP'"),
                 ("missing", "'NoSuchSchema'")):
        v = q1(cur, f"SELECT Graph_KG.rebuild_edge_indices({a})")
        got[f"rb_{k}"] = classify_err(v) or v
    got["rb_rows_after"] = q1(cur, "SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE p IN ('P', 'Q', 'Y', 'Z')")
    got["rb_scan_after"] = scan_obs(q1(cur, "SELECT Graph_KG.MatchEdges('a','P',0,'g')"))
    # ---- privileges (iteration 56: grants recorded, verdict computed by `require`)
    made = {}
    try:
        for r, gl in ROLE_GRANTS.items():
            for sql in (f"DROP ROLE {r}", f"CREATE ROLE {r}"):
                try:
                    cur.execute(sql)
                except Exception:
                    pass
            for g_ in gl:
                cur.execute(g_)
        for u, (_, grants, _) in USERS.items():
            roles = "%All" if u == "i56q_all" else "%DB_%DEFAULT"
            out = iris_sys(f'If ##class(Security.Users).Exists("{u}") {{ Set sc=##class(Security.Users).Delete("{u}") }}\n'
                           f'Set sc=##class(Security.Users).Create("{u}","{roles}","{PW}","i56q binding user")\n' + OK_TAIL)
            assert "RESULT OK" in out, out
            for g_ in grants:
                cur.execute(g_.format(u=u))
            cu = connect(u, PW); k = cu.cursor()
            v = q1(k, "SELECT Graph_KG.MatchEdges('a','P',0,'g')")
            got[f"priv_{u}_me"] = scan_obs(v); got[f"priv_{u}_me_name"] = refusal_name(v)
            got[f"priv_{u}_meall"] = scan_obs(q1(k, "SELECT Graph_KG.MatchEdgesAllGraphs('a','P',0)"))
            got[f"priv_{u}_dj"] = path_obs(q1(k, "SELECT Graph_KG.DijkstraPath('a','d','',9999,10,'out','','g')"))
            v = q1(k, "SELECT Graph_KG.backfill_temporal_rows()")
            got[f"priv_{u}_bf"] = classify_err(v) or v; got[f"priv_{u}_bf_name"] = refusal_name(v)
            v = q1(k, "SELECT Graph_KG.rebuild_edge_indices('Graph_KG')")
            got[f"priv_{u}_rb"] = classify_err(v) or v
            got[f"priv_{u}_rb_msg"] = (v[:300] if isinstance(v, str) else v)
            cu.close()
    finally:
        for u in USERS:
            made[u] = "RESULT OK" in iris_sys(f'Set sc=##class(Security.Users).Delete("{u}")\n' + OK_TAIL)
        for r in ROLE_GRANTS:
            try:
                cur.execute(f"DROP ROLE {r}"); made[r] = True
            except Exception:
                made[r] = False
    c.close()

    def predict(m):
        out = {}
        for src in SRC:
            for pred in PRED:
                for shard in SHARD:
                    for graph in GRAPH:
                        out[f"me|{src}|{pred}|{shard}|{graph}"] = match_edges(adj, src, pred, shard, graph, m)
                out[f"meall|{src}|{pred}"] = match_all(adj, src, pred, 0, m)
        for k in ("zero", "null", "omitted"):
            out[f"me_default_{k}"] = match_edges(adj, "", "P", 0, "", m)
        for k, (_, _, raw) in GSPELL.items():
            raw = "" if raw == "BOUND_EMPTY" else raw
            out[f"me_spell_{k}"] = match_edges_arg(adj, "", "P", raw, m)
        for flag in ("0", "1"):
            scan = flag == "1"
            hits = [a for a in adj if all_hit(a, "a", "P", 0, {}) ]
            out[f"hop_nograph_{flag}"] = sorted([[o, rel_weight(scan, w, m)] for g, s, p, o, w in hits], key=lambda z: (z[0], z[1] is None, z[1] or 0))
            hx = [a for a in adj if scan_hit(a, "", "x", "P", 0, {})]
            out[f"hop_default_{flag}"] = sorted([[o, rel_weight(scan, w, m)] for g, s, p, o, w in hx], key=lambda z: (z[0], z[1] is None, z[1] or 0))
            hg = [a for a in adj if scan_hit(a, "g", "a", "P", 0, {})]
            out[f"hop_named_{flag}"] = sorted([[o, rel_weight(False, w, m)] for g, s, p, o, w in hg], key=lambda z: (z[0], z[1] is None, z[1] or 0))
        for k, (s_, d_, wp, mc, mh, dr, pj, g_) in DJ.items():
            preds = set(json.loads(pj)) if pj not in ("", "[]") else set()
            out[f"dj_{k}"] = dijkstra_json(s_, d_, wp, dr, m, lambda: rule_search(adj, s_, d_, mc, mh, dr, preds, g_))
        out["call_defaults"] = rule_search(adj, "a", "d", 9999, 10, "out", set(), "g")
        out["call_hops1"] = rule_search(adj, "a", "d", 9999, 1, "out", set(), "g")
        b = Bf(); b.tout, b.optout, b.rows = set(), {("g", "TO")}, {}
        for t in (("g", "ta", "T", "tb"), ("g", "tc", "T", "td"), ("", "ua", "T", "ub"), ("g", "oa", "TO", "ob")):
            b.temporal(*t)
        n = 0
        for kind, arg in BFSTEPS:
            if kind == "rows":
                out[f"bf_rows_{n}"] = b.view()
            elif kind == "count":
                n += 1; out[f"bf_count_{n}"] = b.backfill(m)
            elif kind == "delete":
                b.rows.pop(arg, None)
            elif kind == "explicit":
                b.explicit(*arg)
            elif kind == "temporal":
                b.temporal(*arg)
        for k, kind in (("ok", "present"), ("lower", "present"), ("default", "present"), ("not_identifier", "not_identifier"),
                        ("missing", "missing")):
            out[f"rb_{k}"] = rebuild(kind, True, m)
        out["rb_rows_after"] = len([a for a in adj if a[2] in ("P", "Q", "Y", "Z")])
        out["rb_scan_after"] = match_edges(adj, "a", "P", 0, "g", {})
        for u, (caller, _, bld) in USERS.items():
            vs = require(caller, [T_NODES if m.get("readers-check-nodes") else T_EDGES], ["s"], m)
            vi = require(caller, [T_NODES, T_EDGES], ["i"], m)
            sel, ins = vs == "pass", vi == "pass"
            out[f"priv_{u}_me_name"] = vs if not m.get("no-select-check") else "pass"
            out[f"priv_{u}_bf_name"] = vi if not m.get("no-select-check") else "pass"
            out[f"priv_{u}_me"] = gate(sel, match_edges(adj, "a", "P", 0, "g", m), m)
            out[f"priv_{u}_meall"] = gate(sel, match_all(adj, "a", "P", 0, m), m)
            out[f"priv_{u}_dj"] = gate(sel, rule_search(adj, "a", "d", 9999, 10, "out", set(), "g"), m)
            out[f"priv_{u}_bf"] = gate(ins, len(b.structural(m)) if not m.get("count-written-rows") else 0, m)
            out[f"priv_{u}_rb"] = rebuild("present", bld, m)
        return out

    norm = lambda d: json.loads(json.dumps(d))
    got_n = norm({k: v for k, v in got.items() if not k.endswith("_rb_msg")}); want = norm(predict({}))
    mism = [{"case": k, "observed": got_n.get(k), "expected": want[k]} for k in want if got_n.get(k) != want[k]]
    sens = {mm: sum(1 for k, v in norm(predict({mm: True})).items() if v != got_n.get(k)) for mm in MUTS}
    tampered = dict(got_n); tampered["hop_nograph_1"] = want["hop_nograph_0"]
    tamper_detected = any(tampered.get(k) != want[k] for k in want)
    body = {"kind": "binding", "model": "sql_procs", "fixture": runtime.NAME, "port": runtime.PORT, "namespace": NS,
            "product_baseline": runtime.PRODUCT, "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES",
            "cases": len(want), "mismatches": mism, "observed": got, "users_dropped": made,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q_.relative_to(REPO)): sha(q_) for q_ in [HERE / "binding.py", HERE / "sql_procs.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_src/src/Graph/KG/SqlProcs.cls", "iris_src/src/Graph/KG/EdgeScan.cls",
                                                                   "iris_src/src/Graph/KG/Traversal.cls", "iris_src/src/Graph/KG/TraversalPaths.cls",
                                                                   "iris_src/src/Graph/KG/TemporalIndex.cls", "iris_src/src/Graph/KG/Adjacency.cls",
                                                                   "iris_src/src/Graph/KG/Ledger.cls", "iris_src/src/Graph/KG/SqlPrivilege.cls",
                                                                   "iris_vector_graph/cypher/translator.py", "iris_vector_graph/schema.py"]}},
            "scope": "Actual SQL entry points on IRIS 2026.1 (pin 3eaa79cf) in a re-created namespace: MatchEdges over 4 sources x 3 "
                     "predicates x 3 shards x 4 graph keys and 3 default-graph spellings, MatchEdgesAllGraphs over 12 source/predicate "
                     "pairs; the Cypher hop with IVG_EDGESCAN unset and 1 (no USE GRAPH, USE GRAPH '', a named graph); DijkstraPath "
                     "over 26 argument sets (bounds, predicates, directions, weights <= 0, graph spellings, equal and empty "
                     "endpoints, refused arguments) and the CALL beside it; backfill_temporal_rows over a history with a "
                     "temporal-only predicate, a structural row deleted by SQL and an explicit edge; rebuild_edge_indices with 5 "
                     "schema arguments; each entry as eight users whose grants are recorded and whose verdict is computed "
                     "(none, schema SELECT, schema write, table SELECT, column-only SELECT, a role holding table SELECT, "
                     "schema SELECT + INSERT on nodes only, %All); MatchEdges with 8 graph-argument spellings (iteration 56)."}
    d = REPO / ".g5/Verus_verification/results/sql_procs" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s", "users_dropped")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
