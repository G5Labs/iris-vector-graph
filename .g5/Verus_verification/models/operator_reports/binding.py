"""Binding for operator_reports (W58, iteration 52; extended in iteration 53) on the run-isolated continuation fixture.

Status counts every graph of a namespace, so the binding drops and re-creates its own namespace I53B (from %SYS, in
the container ivg-cont-20261117-iris only; iteration 52's runs used I52B, which this binding no longer touches) and
replays one history of public writes there: setup on the empty
namespace, create_edge, sync(), a triple shared by two graphs, verify_sync(heal=True), delete_node, a caller
transaction around bulk_load_session, routed and legacy vectors, bm25_build/bm25_drop, setup again from the engine
that synced and from a fresh engine, a snapshot save/restore. After each step it reads the same facts through every
reader (EngineStatus fields, readiness properties and report line, verify_sync, a fresh engine's capabilities and the
calling engine's cached ones, /server and /stats through the in-process FastAPI client, the schema diagram,
snapshot_info) and compares them with a Python port of operator_reports.rs's writers and readers applied to the same
history. Iteration 53 adds routed and legacy edge vectors (ready_for_edge_search), the revision ledger (enable, two
commits, a commit refused for a stale head) and the same moment read by four monitoring users whose privileges let only
some probes succeed (users i53_bmon, i53_bnative, i53_bpart, i53_bnoledger and role i53_brole, created in %SYS for the
run and dropped at its end): status() counts, unknown parts, readiness flags and ledger line, /server and /metrics.
Expected answers come from the port, never from the product's answers. The producer inputs taken from the product
are the routed tables' registry names (the writer's hash), the diagram's label list and the rdf_labels/rdf_props row
counts as _SYSTEM reads them. Mutations mirror the model's 24 controls; one deciding observation is tampered.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/operator_reports/binding.py)
"""
import dataclasses, hashlib, json, os, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

NS = "I53B"
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
P = "i53b_"
DIM = 768
MUTS = ["registry-keeps-case", "verify-counts-distinct-rows", "nkg-per-graph", "heal-rereads", "status-pending-reads-nkg",
        "setup-inits-skeleton", "put-always-interns", "multihop-needs-nkg", "sync-sets-markers", "setup-marks-empty",
        "engine-cache-unchanged", "bulk-leaves-flag", "delete-keeps-nkg", "drop-keeps-index", "stats-every-graph",
        "viz-none-distinct", "setup-skips-bootstrap", "metrics-marks-unknown", "readiness-unknown-not-false",
        "failed-count-not-zero", "side-count-marks-unknown", "edge-registry-keeps-case", "ledger-read-reported",
        "meta-failure-silent"]
PW = "i53bPass!x"
# monitoring user -> (Native API resources through role i53_brole, Graph_KG tables it may SELECT; "*" every table but "-x")
USERS = {"i53_bmon": (False, []), "i53_bnative": (True, []),
         "i53_bpart": (True, ["nodes", "rdf_edges", "embedding_registry", "kg_NodeEmbeddings"]),
         "i53_bnoledger": (True, ["*", "-ledger_stats"])}
# which probes each user's privileges let succeed (the model's Probes), written from the grants above
PROBES = {"_SYSTEM": dict(native=True, census=True, labels=True, props=True, node_vec=True, edge_vec=True, ledger_stats=True),
          "i53_bmon": dict(native=False, census=False, labels=False, props=False, node_vec=False, edge_vec=False, ledger_stats=False),
          "i53_bnative": dict(native=True, census=False, labels=False, props=False, node_vec=False, edge_vec=False, ledger_stats=False),
          "i53_bpart": dict(native=True, census=True, labels=False, props=False, node_vec=True, edge_vec=False, ledger_stats=False),
          "i53_bnoledger": dict(native=True, census=True, labels=True, props=True, node_vec=True, edge_vec=True, ledger_stats=False)}
MODELED_PARTS = ("graph", "vector_index", "sync", "fulltext_index", "ledger")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ port of operator_reports.rs
class Ns:
    def __init__(self):
        self.rows = []            # (g, s, p, o)
        self.nodes = []           # (g, id)
        self.skel = False; self.dict_ = False; self.triples = set(); self.count = 0
        self.mk = False; self.mn = False
        self.legacy = 0; self.routes = []   # (name, g, rows)
        self.hnsw = False; self.bm25 = set()
        self.edge_legacy = 0; self.edge_routes = []   # (name, g, rows)
        self.led = {"enabled": False, "seq": 0, "commits": 0, "rejections": 0}
        self.label_rows = 0; self.prop_rows = 0       # count inputs

    def copy(self):
        n = Ns(); n.__dict__.update({k: (list(v) if isinstance(v, list) else set(v) if isinstance(v, set) else dict(v) if isinstance(v, dict) else v)
                                     for k, v in self.__dict__.items()}); return n


class Eng:
    def __init__(self):
        self.dirty = False; self.caps = None


def tri(e):
    return e[1:]


def ndistinct(rows):
    return len({tri(e) for e in rows})


class Port:
    def __init__(self, m):
        self.m = m

    def detect(self, ns):
        return {"kg_built": ns.mk, "nkg_built": ns.mn}

    def caps_of(self, ns, eng):
        return eng.caps if eng.caps is not None else self.detect(ns)

    def setup(self, ns):
        if self.m.get("setup-skips-bootstrap"):
            return
        if (len(ns.rows) > 0 or self.m.get("setup-marks-empty")) and not ns.mk:
            ns.mk = True; ns.mn = True

    def fresh_setup(self):
        ns = Ns(); ns.skel = bool(self.m.get("setup-inits-skeleton")); self.setup(ns); return ns

    def create_node(self, ns, g, i):
        ns.nodes.append((g, i))

    def create_edge(self, ns, e):
        ns.rows.append(e)
        if ns.skel or self.m.get("put-always-interns"):
            ns.dict_ = True
            if tri(e) not in ns.triples:
                ns.triples.add(tri(e)); ns.count += 1

    def sync(self, ns, eng):
        c = self.caps_of(ns, eng)
        ns.skel = True; ns.dict_ = len(ns.rows) > 0; ns.triples = {tri(e) for e in ns.rows}
        ns.count = len(ns.rows) if self.m.get("nkg-per-graph") else ndistinct(ns.rows)
        if self.m.get("sync-sets-markers"):
            ns.mk = True; ns.mn = True
        eng.dirty = False
        eng.caps = dict(c) if self.m.get("engine-cache-unchanged") else dict(c, kg_built=True)

    def delete_node(self, ns, eng, g, x):
        ns.rows = [e for e in ns.rows if not (e[0] == g and (e[1] == x or e[3] == x))]
        ns.nodes = [n for n in ns.nodes if n != (g, x)]
        if not self.m.get("delete-keeps-nkg"):
            ns.skel = False; ns.dict_ = False; ns.triples = set(); ns.count = 0
        eng.dirty = False

    def bulk(self, ns, eng, nodes, edges):
        ns.nodes += nodes
        for e in edges:  # each row through the adjacency index: Put interns when the skeleton exists
            self.create_edge(ns, e)
        if not self.m.get("bulk-leaves-flag"):
            eng.dirty = True

    @staticmethod
    def up(c):
        return c - 32 if 97 <= c <= 122 else c

    def registry_text(self, name):
        return name if self.m.get("registry-keeps-case") else "".join(chr(self.up(ord(ch))) for ch in name)

    @staticmethod
    def is_route(n):
        return (len(n) == 23 and n.startswith("kg_emb_") and all(ch in "0123456789abcdef" for ch in n[7:]))

    def node_vecs(self, ns):
        return ns.legacy + sum(r for name, g, r in ns.routes if self.is_route(self.registry_text(name)))

    def status(self, ns, eng):
        kgp = len(ns.rows) > 0
        nv = self.node_vecs(ns)
        pending = eng.dirty or (bool(self.m.get("status-pending-reads-nkg")) and kgp and not ns.dict_)
        bfs = kgp and len(ns.rows) > 0
        multihop = bfs and (ns.dict_ if self.m.get("multihop-needs-nkg") else kgp)
        return {"nodes": len(ns.nodes), "edges": len(ns.rows), "node_vecs": nv, "kg_populated": kgp,
                "kg_edge_count": len(ns.rows), "nkg_populated": ns.dict_, "pending": pending,
                "ready_bfs": bfs, "ready_multihop": multihop, "ready_vec": nv > 0,
                "vec_state": "absent" if nv == 0 else ("ready" if ns.hnsw else "empty"),
                "ready_ft": len(ns.bm25) > 0, "sync_line": "needs sync" if pending else "in sync"}

    def verify(self, ns, eng):
        sql = ndistinct(ns.rows) if self.m.get("verify-counts-distinct-rows") else len(ns.rows)
        return {"in_sync": not (sql > ns.count) and not eng.dirty, "sql": len(ns.rows), "glob": ns.count,
                "pending": eng.dirty}

    def heal(self, ns, eng):
        r = self.verify(ns, eng)
        if r["in_sync"]:
            return dict(r, healed=False)
        self.sync(ns, eng)
        if self.m.get("heal-rereads"):
            return dict(self.verify(ns, eng), healed=True)
        return dict(r, in_sync=True, healed=True)

    def stats_nodes(self, ns):
        return len(ns.nodes) if self.m.get("stats-every-graph") else sum(1 for g, _ in ns.nodes if g == "")

    def label_id(self, labels, lab):
        if lab is None:
            return -1 if self.m.get("viz-none-distinct") else 0
        return labels.index(lab) if lab in labels else 0

    def bm25_drop(self, ns, x):
        if not self.m.get("drop-keeps-index"):
            ns.bm25.discard(x)

    # iteration 53: edge vectors, the ledger, probes that fail for the caller's privileges
    @staticmethod
    def is_eroute(n):
        return (len(n) == 24 and n.startswith("kg_eemb_") and all(ch in "0123456789abcdef" for ch in n[8:]))

    def edge_vecs(self, ns):
        def name(n):
            return n if self.m.get("edge-registry-keeps-case") else self.registry_text(n)
        return ns.edge_legacy + sum(r for n, g, r in ns.edge_routes if self.is_eroute(name(n)))

    def ledger_enable(self, ns):
        if not ns.led["enabled"]:
            ns.led = {"enabled": True, "seq": 1, "commits": 1, "rejections": 0}

    def ledger_commit(self, ns):
        if ns.led["enabled"]:
            ns.led["seq"] += 1; ns.led["commits"] += 1

    def ledger_reject(self, ns):
        if ns.led["enabled"]:
            ns.led["rejections"] += 1

    def unknown_of(self, pr):
        graph = not pr["census"]
        if self.m.get("side-count-marks-unknown"):
            graph = graph or not pr["labels"] or not pr["props"] or not pr["edge_vec"]
        u = {"graph": graph, "vector_index": not pr["node_vec"] or not pr["native"], "sync": not pr["native"],
             "fulltext_index": not pr["native"], "ledger": not pr["native"]}
        return sorted(k for k, v in u.items() if v)

    def ledger_line(self, ns, pr):
        if not pr["native"] and not self.m.get("meta-failure-silent"):
            return "unknown"
        if not ns.led["enabled"]:
            return "not_enabled"
        if not pr["ledger_stats"]:
            return "unknown" if self.m.get("ledger-read-reported") else [ns.led["seq"], 0, 0]
        return [ns.led["seq"], ns.led["commits"], ns.led["rejections"]]

    def status_p(self, ns, eng, pr):
        unk = self.unknown_of(pr)
        census = pr["census"] or bool(self.m.get("failed-count-not-zero"))
        nodes = len(ns.nodes) if census else 0
        edges = len(ns.rows) if pr["census"] else 0
        kgp = pr["native"] and len(ns.rows) > 0
        nv = self.node_vecs(ns) if pr["node_vec"] else 0
        ev = self.edge_vecs(ns) if pr["edge_vec"] else 0
        bfs = kgp and (edges > 0 or (bool(self.m.get("readiness-unknown-not-false")) and "graph" in unk))
        return {"nodes": nodes, "edges": edges, "labels": ns.label_rows if pr["labels"] else 0,
                "props": ns.prop_rows if pr["props"] else 0, "node_vecs": nv, "edge_vecs": ev, "kg_populated": kgp,
                "unknown": unk, "ledger": self.ledger_line(ns, pr), "ready_bfs": bfs,
                "ready_multihop": bfs and (ns.dict_ if self.m.get("multihop-needs-nkg") else kgp),
                "ready_vec": nv > 0, "ready_edge": ev > 0, "ready_ft": pr["native"] and len(ns.bm25) > 0,
                "graph_line": None if "graph" in unk else [nodes, edges]}

    def readers_p(self, st_):
        unk = st_["unknown"]
        if self.m.get("metrics-marks-unknown"):
            met = {"nodes": None if "graph" in unk else st_["nodes"], "edges": None if "graph" in unk else st_["edges"],
                   "embeddings": None if "vector_index" in unk else st_["node_vecs"]}
        else:
            met = {"nodes": st_["nodes"], "edges": st_["edges"], "embeddings": st_["node_vecs"]}
        return {"server": {"nodes": st_["nodes"], "edges": st_["edges"], "labels": st_["labels"],
                           "embeddings": st_["node_vecs"], "kg": st_["kg_populated"]}, "metrics": met}


# ------------------------------------------------------------------ the fixture
def recreate_namespace():
    script = (f'Set ns="{NS}", dir="/usr/irissys/mgr/{NS.lower()}/"\n'
              'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
              'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
              'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
              'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
              'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
              'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
              'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!\nHalt\n')
    out = subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", "%SYS"], input=script,
                         capture_output=True, text=True, timeout=300).stdout
    assert "RESULT OK" in out, out


def connect(user="_SYSTEM", pw="SYS"):
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username=user, password=pw)
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close(); raise RuntimeError("fixture identity mismatch")
    return c


def engine(c=None):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c or connect(), embedding_dimension=DIM, native_cypher=False)


def ostatus(e):
    s = e.status()
    line = [ln for ln in s.report().splitlines() if ln.startswith("Sync state:")][0].split(":", 1)[1].strip()
    return {"nodes": s.tables.nodes, "edges": s.tables.edges, "node_vecs": s.tables.node_embeddings,
            "kg_populated": s.adjacency.kg_populated, "kg_edge_count": s.adjacency.kg_edge_count,
            "nkg_populated": s.adjacency.nkg_populated, "pending": s.pending_sync, "ready_bfs": s.ready_for_bfs,
            "ready_multihop": s.ready_for_multihop_bfs, "ready_vec": s.ready_for_vector_search,
            "vec_state": s.vector_index_state, "ready_ft": s.ready_for_full_text, "sync_line": line}


def overify(e, heal=False):
    r = e.verify_sync(heal=heal)
    d = {"in_sync": r.in_sync, "sql": r.sql_edges, "glob": r.global_edges, "pending": r.pending_sync}
    if heal:
        d["healed"] = r.healed
    d["bool"] = bool(r)
    return d


def ocaps(e):
    c = e.capabilities
    return {"kg_built": c.kg_built, "nkg_built": c.nkg_built}


# ------------------------------------------------------------------ iteration 53: monitoring users and their readers
def iris_sys(script):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", "%SYS"],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=300).stdout


OK_TAIL = 'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!'


def make_users(cur):
    """Role i53_brole (the namespace's database plus the Native API resources) and the four users; SELECT grants per
    USERS. Returns the grants actually made."""
    out = iris_sys('If ##class(Security.Roles).Exists("i53_brole") { Set sc=##class(Security.Roles).Delete("i53_brole") }\n'
                   'Set sc=##class(Security.Roles).Create("i53_brole","i53 binding monitoring role",'
                   '"%DB_%DEFAULT:RW,%Native_GlobalAccess:U,%Native_ClassExecution:U")\n' + OK_TAIL)
    assert "RESULT OK" in out, out
    cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Graph_KG'")
    every = [r[0] for r in cur.fetchall()]
    grants = {}
    for user, (native, spec) in USERS.items():
        roles = "%DB_%DEFAULT,i53_brole" if native else "%DB_%DEFAULT"
        out = iris_sys(f'If ##class(Security.Users).Exists("{user}") {{ Set sc=##class(Security.Users).Delete("{user}") }}\n'
                       f'Set sc=##class(Security.Users).Create("{user}","{roles}","{PW}","i53 binding monitoring user")\n' + OK_TAIL)
        assert "RESULT OK" in out, out
        tables = [t for t in every if "-" + t not in spec] if "*" in spec else spec
        for t in tables:
            cur.execute(f"GRANT SELECT ON Graph_KG.{t} TO {user}")
        grants[user] = tables
    return grants


def drop_users():
    done = {}
    for user in USERS:
        done[user] = "RESULT OK" in iris_sys(f'Set sc=##class(Security.Users).Delete("{user}")\n' + OK_TAIL)
    done["i53_brole"] = "RESULT OK" in iris_sys('Set sc=##class(Security.Roles).Delete("i53_brole")\n' + OK_TAIL)
    return done


def ostatus_p(e):
    s = e.status()
    unk = sorted(p for p in s.unknown if p in MODELED_PARTS)
    if "ledger" in s.unknown:
        led = "unknown"
    elif s.ledger is None or s.ledger.state == "never-enabled":
        led = "not_enabled"
    else:
        led = [s.ledger.head_seq, s.ledger.commits_ok, sum(s.ledger.rejections.values())]
    gl = [ln for ln in s.report().splitlines() if ln.startswith("Graph:")]
    t = s.tables
    return {"nodes": t.nodes, "edges": t.edges, "labels": t.labels, "props": t.props, "node_vecs": t.node_embeddings,
            "edge_vecs": t.edge_embeddings, "kg_populated": s.adjacency.kg_populated, "unknown": unk, "ledger": led,
            "ready_bfs": s.ready_for_bfs, "ready_multihop": s.ready_for_multihop_bfs, "ready_vec": s.ready_for_vector_search,
            "ready_edge": s.ready_for_edge_search, "ready_ft": s.ready_for_full_text,
            "graph_line": None if (gl and "unknown" in gl[0]) else [t.nodes, t.edges]}, \
        {"graph_line_text": gl, "ledger_line_text": [ln for ln in s.report().splitlines() if ln.startswith("Ledger:")],
         "errors": len(s.errors), "unknown_all": list(s.unknown)}


def oreaders(user, pw):
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    from click.testing import CliRunner
    from iris_vector_graph import cli as ivg_cli
    from iris_vector_graph.sdk import IVGClient
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE=NS, IRIS_USERNAME=user,
                      IRIS_PASSWORD=pw)
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
        os.environ.pop(k, None)
    cypher_api._engine_cache = None
    with TestClient(cypher_api.app) as client:
        sv = client.get("/server").json()
        mt = {ln.split()[0]: ln.split()[1] for ln in client.get("/metrics").text.splitlines() if ln and not ln.startswith("#")}

        def fake_client(url, api_key):
            c = IVGClient("http://testserver", api_key=api_key)
            c._client = client
            return c
        orig = ivg_cli._client
        ivg_cli._client = fake_client
        try:
            cli_exit = CliRunner().invoke(ivg_cli.cli, ["status"]).exit_code
        finally:
            ivg_cli._client = orig
    cypher_api._engine_cache = None
    return ({"server": {"nodes": sv["schema"]["nodes"], "edges": sv["schema"]["edges"], "labels": sv["schema"]["labels"],
                        "embeddings": sv["schema"]["embeddings"], "kg": sv["adjacency"]["kg_populated"]},
             "metrics": {"nodes": int(mt["ivg_nodes_total"]), "edges": int(mt["ivg_edges_total"]),
                         "embeddings": int(mt["ivg_embeddings_total"])}},
            {"server_errors": len(sv.get("errors") or []), "server_has_unknown": "unknown" in sv,
             "metrics_names": sorted(mt), "cli_status_exit": cli_exit})


# ------------------------------------------------------------------ the history, run on the product and on the port
def history(product, pt):
    """One history. product=True drives the fixture and returns observations; product=False drives the port and
    returns its predictions with the same keys. `inputs` carries the producer values the port takes from the product."""
    out = {}
    if product:
        recreate_namespace()
        e1 = engine(); e2 = engine()
        e1.initialize_schema()
    else:
        ns = pt.fresh_setup(); e1 = Eng(); e2 = Eng()
    vec = [0.0] * DIM; vec[0] = 1.0
    g = "i52bg"

    def snap(tag, e, other=None, caps_fresh=True):
        if product:
            out[tag + ":status"] = ostatus(e); out[tag + ":verify"] = overify(e)
            if other is not None:
                out[tag + ":status_other"] = ostatus(other); out[tag + ":verify_other"] = overify(other)
            if caps_fresh:
                out[tag + ":caps_fresh"] = ocaps(engine())
        else:
            out[tag + ":status"] = pt.status(ns, e); out[tag + ":verify"] = dict(pt.verify(ns, e), bool=pt.verify(ns, e)["in_sync"])
            if other is not None:
                out[tag + ":status_other"] = pt.status(ns, other)
                out[tag + ":verify_other"] = dict(pt.verify(ns, other), bool=pt.verify(ns, other)["in_sync"])
            if caps_fresh:
                out[tag + ":caps_fresh"] = pt.detect(ns)

    def node(gr, i, labels=None):
        if product:
            e1.create_node(P + i, labels=labels or [], graph=(gr or None))
        else:
            pt.create_node(ns, gr, P + i)

    def edge(gr, s, p, o):
        if product:
            e1.create_edge(P + s, p, P + o, graph=(gr or None))
        else:
            pt.create_edge(ns, (gr, P + s, p, P + o))

    snap("s0_setup", e1)
    node("", "a", ["A"]); node("", "b", ["B"]); edge("", "a", "R", "b")
    snap("s1_first_edge", e1, e2)
    if product:
        e1.sync(); out["s2:caps_e1"] = ocaps(e1)
    else:
        pt.sync(ns, e1); out["s2:caps_e1"] = pt.caps_of(ns, e1)
    snap("s2_sync", e1, e2)
    node("", "c", ["C"]); edge("", "b", "R", "c")
    snap("s3_put_after_sync", e1, caps_fresh=False)
    node(g, "a", ["A"]); node(g, "b", ["B"]); edge(g, "a", "R", "b")
    snap("s4_shared_triple", e1, e2, caps_fresh=False)
    if product:
        out["s5:heal"] = overify(e1, heal=True)
    else:
        h = pt.heal(ns, e1); out["s5:heal"] = dict(h, bool=h["in_sync"])
    snap("s5_after_heal", e1, e2, caps_fresh=False)
    if product:
        e1.sync()
    else:
        pt.sync(ns, e1)
    snap("s6_sync_again", e1, e2, caps_fresh=False)
    node(g, "d", ["D"]); edge(g, "b", "S", "d")
    snap("s7_named_put", e1, caps_fresh=False)
    if product:
        e1.delete_node(P + "c", graph=None)
    else:
        pt.delete_node(ns, e1, "", P + "c")
    snap("s8_delete", e1, e2, caps_fresh=False)
    if product:
        e1.sync()
    else:
        pt.sync(ns, e1)
    # routed vectors only, then a legacy vector
    if product:
        e1.store_embeddings([{"node_id": P + "a", "embedding": vec}], graph=g)
        cur = e1.conn.cursor()
        cur.execute("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ?", [g])
        name = cur.fetchone()[0]
        cur.execute("SELECT DISTINCT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ?", [g])
        out["inputs:route_name"] = name
        out["provider:distinct_text"] = cur.fetchone()[0]
        out["s9:search_g"] = len(e1.search_nodes_by_vector(vec, k=3, graph=g)) > 0
    else:
        name = pt.inputs["inputs:route_name"]
        ns.routes.append((name, g, 1))
        out["inputs:route_name"] = name
        out["provider:distinct_text"] = "".join(chr(Port.up(ord(ch))) for ch in name)
        out["s9:search_g"] = sum(r for _, gg, r in ns.routes if gg == g) > 0
    snap("s9_routed_vectors", e1, caps_fresh=False)
    if product:
        e1.store_embeddings([{"node_id": P + "b", "embedding": vec}])
    else:
        ns.legacy += 1
    snap("s10_legacy_vector", e1, caps_fresh=False)
    if product:
        e1.bm25_build("i52bbm", ["name"])
    else:
        ns.bm25.add("i52bbm")
    snap("s11_bm25_built", e1, caps_fresh=False)
    if product:
        e1.bm25_drop("i52bbm")
    else:
        pt.bm25_drop(ns, "i52bbm")
    snap("s12_bm25_dropped", e1, caps_fresh=False)
    # a caller transaction around bulk_load_session, committed
    if product:
        c5 = connect(); e5 = engine(c5)
        cur = c5.cursor(); cur.execute("START TRANSACTION")
        e5.create_node(P + "x")
        with e5.bulk_load_session() as sess:
            sess.add_nodes([{"id": P + "y", "labels": ["Y"]}])
            sess.add_edges([(P + "x", P + "y", "BL")])
        c5.commit()
    else:
        e5 = Eng()
        pt.bulk(ns, e5, [("", P + "x"), ("", P + "y")], [("", P + "x", "BL", P + "y")])
    snap("s13_bulk_in_caller_txn", e5, e1, caps_fresh=False)
    # an edge whose ends carry no label; the schema diagram; /stats vs /server
    node("", "u1"); node("", "u2"); edge("", "u1", "UNLAB", "u2")
    if product:
        from fastapi.testclient import TestClient
        from iris_vector_graph import cypher_api
        os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE=NS, IRIS_USERNAME="_SYSTEM",
                          IRIS_PASSWORD="SYS")
        for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
            os.environ.pop(k, None)
        cypher_api._engine_cache = None
        with TestClient(cypher_api.app) as client:
            out["s14:stats_nodes"] = client.get("/stats").json()["nodeCount"]
            sv = client.get("/server").json()
            out["s14:server"] = {"nodes": sv["schema"]["nodes"], "embeddings": sv["schema"]["embeddings"],
                                 "kg": sv["adjacency"]["kg_populated"], "nkg": sv["adjacency"]["nkg_populated"]}
            mt = {ln.split()[0]: ln.split()[1] for ln in client.get("/metrics").text.splitlines() if ln and not ln.startswith("#")}
            out["s14:metrics"] = {"nodes": int(mt["ivg_nodes_total"]), "nkg": int(mt["ivg_nkg_populated"])}
        cypher_api._engine_cache = None
        viz = e1.get_schema_visualization()
        names = [n["name"] for n in viz["nodes"]]
        rel = {r["name"]: (r["startNode"], r["endNode"]) for r in viz["relationships"]}
        out["s14:viz"] = {"labels": names, "UNLAB": list(rel["UNLAB"]), "R": list(rel["R"]), "BL": list(rel["BL"])}
    else:
        st_ = pt.status(ns, e1)
        out["s14:stats_nodes"] = pt.stats_nodes(ns)
        out["s14:server"] = {"nodes": st_["nodes"], "embeddings": st_["node_vecs"], "kg": st_["kg_populated"],
                             "nkg": st_["nkg_populated"]}
        out["s14:metrics"] = {"nodes": st_["nodes"], "nkg": 1 if st_["nkg_populated"] else 0}
        labels = pt.inputs["s14:viz"]["labels"]   # the diagram's sorted label list (a reader input)
        out["s14:viz"] = {"labels": labels, "UNLAB": [pt.label_id(labels, None), pt.label_id(labels, None)],
                          "R": [pt.label_id(labels, "A"), pt.label_id(labels, "B")],
                          "BL": [pt.label_id(labels, None), pt.label_id(labels, "Y")]}
    # setup again: from the engine that ran sync(), then from a fresh engine
    if product:
        e1.initialize_schema(); out["s15:caps_after_e1_setup"] = ocaps(engine())
        engine().initialize_schema(); out["s15:caps_after_fresh_setup"] = ocaps(engine())
    else:
        pt.setup(ns); out["s15:caps_after_e1_setup"] = pt.detect(ns)
        pt.setup(ns); out["s15:caps_after_fresh_setup"] = pt.detect(ns)
    # snapshot: info at save, a later write, a replacing restore
    if product:
        path = str(Path(tempfile.mkdtemp(prefix="i52bsnap")) / "snap.zip")
        e1.save_snapshot(path)
        info = e1.snapshot_info(path)
        out["s16:info"] = {"nodes": info["tables"]["Graph_KG.nodes"], "edges": info["tables"]["Graph_KG.rdf_edges"]}
        node("", "late"); e1.restore_snapshot(path)
        s = e1.status(); out["s16:after_restore"] = {"nodes": s.tables.nodes, "edges": s.tables.edges}
    else:
        saved = ns.copy()
        out["s16:info"] = {"nodes": len(saved.nodes), "edges": len(saved.rows)}
        node("", "late"); ns.rows = list(saved.rows); ns.nodes = list(saved.nodes)
        out["s16:after_restore"] = {"nodes": len(ns.nodes), "edges": len(ns.rows)}
    # iteration 53 (review m7): routed edge vectors only, then a legacy edge vector
    node(g, "ea"); node(g, "eb"); edge(g, "ea", "E", "eb")
    if product:
        e1.store_edge_embeddings([{"s": P + "ea", "p": "E", "o_id": P + "eb", "embedding": vec}], graph=g)
        cur = e1.conn.cursor()
        cur.execute("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ? AND kind = 'edge'", [g])
        out["inputs:edge_route_name"] = cur.fetchone()[0]
        out["s17:edge_search_g"] = len(e1.edge_vector_search(vec, top_k=3, graph=g)) > 0
        out["s17_edge_routed:status"], _ = ostatus_p(e1)
    else:
        name = pt.inputs["inputs:edge_route_name"]
        ns.edge_routes.append((name, g, 1))
        out["inputs:edge_route_name"] = name
        out["s17:edge_search_g"] = sum(r for _, gg, r in ns.edge_routes if gg == g) > 0
        ns.label_rows, ns.prop_rows = pt.inputs["inputs:label_rows@s17"], pt.inputs["inputs:prop_rows@s17"]
        out["s17_edge_routed:status"] = pt.status_p(ns, e1, PROBES["_SYSTEM"])
    if product:
        st17 = e1.status(); out["inputs:label_rows@s17"] = st17.tables.labels; out["inputs:prop_rows@s17"] = st17.tables.props
        e1.store_edge_embeddings([{"s": P + "a", "p": "R", "o_id": P + "b", "embedding": vec}])
        out["s17_edge_legacy:status"], _ = ostatus_p(e1)
    else:
        out["inputs:label_rows@s17"] = pt.inputs["inputs:label_rows@s17"]; out["inputs:prop_rows@s17"] = pt.inputs["inputs:prop_rows@s17"]
        ns.edge_legacy += 1
        out["s17_edge_legacy:status"] = pt.status_p(ns, e1, PROBES["_SYSTEM"])
    # iteration 53 (review M3): the revision ledger: enable, two commits, a commit refused for a stale head
    if product:
        from iris_vector_graph.ledger.changeset import Changeset
        e1.ledger.enable()
        e1.ledger.commit(Changeset(actor="i53b", actor_type="test").create_node(P + "l1"))
        h1 = e1.ledger.head().revision_id
        e1.ledger.commit(Changeset(actor="i53b", actor_type="test").create_node(P + "l2"))
        try:
            e1.ledger.commit(Changeset(actor="i53b", actor_type="test", expected_head=h1).create_node(P + "l3"))
            out["s18:stale_refused"] = False
        except Exception as ex:
            out["s18:stale_refused"] = type(ex).__name__
        out["s18:ledger_stats"] = (lambda c: [c.head_seq, c.commits_ok, sum(c.rejections.values())])(e1.ledger.stats())
        out["s18_ledger:status"], _ = ostatus_p(e1)
    else:
        pt.ledger_enable(ns)
        pt.create_node(ns, "", P + "l1"); pt.ledger_commit(ns)
        pt.create_node(ns, "", P + "l2"); pt.ledger_commit(ns)
        pt.ledger_reject(ns)
        out["s18:stale_refused"] = "StaleHeadError"
        out["s18:ledger_stats"] = [ns.led["seq"], ns.led["commits"], ns.led["rejections"]]
        ns.label_rows, ns.prop_rows = pt.inputs["inputs:label_rows@s18"], pt.inputs["inputs:prop_rows@s18"]
        out["s18_ledger:status"] = pt.status_p(ns, e1, PROBES["_SYSTEM"])
    # iteration 53 (review M2, M3): the same moment read by monitoring users with narrow privileges
    if product:
        st18 = e1.status(); out["inputs:label_rows@s18"] = st18.tables.labels; out["inputs:prop_rows@s18"] = st18.tables.props
        out["s19:grants"] = make_users(e1.conn.cursor())
        try:
            for user in USERS:
                cu = connect(user, PW)
                try:
                    out[f"s19_{user}:status"], out[f"evidence:s19_{user}:status"] = ostatus_p(engine(cu))
                    out[f"evidence:s19_{user}:ledger_stats"] = obs_(lambda: (lambda c: [c.head_seq, c.commits_ok, sum(c.rejections.values())])(engine(cu).ledger.stats()))
                finally:
                    cu.close()
                out[f"s19_{user}:readers"], out[f"evidence:s19_{user}:readers"] = oreaders(user, PW)
        finally:
            out["s19:dropped"] = drop_users()
    else:
        out["inputs:label_rows@s18"] = pt.inputs["inputs:label_rows@s18"]; out["inputs:prop_rows@s18"] = pt.inputs["inputs:prop_rows@s18"]
        for user in USERS:
            sp = pt.status_p(ns, e1, PROBES[user])
            out[f"s19_{user}:status"] = sp
            out[f"s19_{user}:readers"] = pt.readers_p(sp)
    return out


def obs_(f):
    try:
        return f()
    except Exception as ex:
        return {"error": type(ex).__name__, "msg": str(ex)[:300]}


def main():
    t0 = time.time()
    obs = history(True, None)
    inputs = {k: v for k, v in obs.items() if k.startswith("inputs:")}
    evidence = {k: obs.pop(k) for k in [k for k in obs if k.startswith("evidence:")]}
    for k in ("s19:grants", "s19:dropped"):
        evidence[k] = obs.pop(k)
    inputs["s14:viz"] = obs["s14:viz"]

    def predict(m):
        pt = Port(m); pt.inputs = inputs
        return history(False, pt)

    def compare(want, got):
        bad = []
        for k, w in want.items():
            g_ = got.get(k)
            if isinstance(w, dict):
                for kk, ww in w.items():
                    if (g_ or {}).get(kk) != ww:
                        bad.append((f"{k}.{kk}", ww, (g_ or {}).get(kk)))
            elif w != g_:
                bad.append((k, w, g_))
        return bad

    want = predict({})
    mism = compare(want, obs)
    ncases = sum(len(v) if isinstance(v, dict) else 1 for v in want.values())
    sens = {mu: len(compare(predict({mu: True}), obs)) for mu in MUTS}
    tampered = json.loads(json.dumps(obs)); tampered["s5_after_heal:verify"]["in_sync"] = True
    tampered2 = json.loads(json.dumps(obs)); tampered2["s19_i53_bnoledger:status"]["ledger"] = "unknown"
    tamper_detected = bool(compare(want, tampered)) and bool(compare(want, tampered2))
    contrasts = {"first_edge_status_vs_verify": [obs["s1_first_edge:status"]["sync_line"], obs["s1_first_edge:verify"]["in_sync"],
                                                  obs["s1_first_edge:status"]["nkg_populated"], obs["s1_first_edge:status"]["ready_multihop"]],
                 "unique_after_sync_in_sync": obs["s3_put_after_sync:verify"]["in_sync"],
                 "heal_report": obs["s5:heal"], "after_heal": obs["s5_after_heal:verify"], "after_sync_again": obs["s6_sync_again:verify"],
                 "routed_only": [obs["s9_routed_vectors:status"]["node_vecs"], obs["s9_routed_vectors:status"]["vec_state"], obs["s9:search_g"]],
                 "registry_name_vs_distinct": [obs["inputs:route_name"], obs["provider:distinct_text"]],
                 "caps_fresh_after_sync": obs["s2_sync:caps_fresh"], "caps_e1_after_sync": obs["s2:caps_e1"],
                 "caps_after_e1_setup": obs["s15:caps_after_e1_setup"], "caps_after_fresh_setup": obs["s15:caps_after_fresh_setup"],
                 "stats_vs_server_nodes": [obs["s14:stats_nodes"], obs["s14:server"]["nodes"]], "viz": obs["s14:viz"],
                 "edge_routed_only": [obs["s17_edge_routed:status"]["edge_vecs"], obs["s17_edge_routed:status"]["ready_edge"], obs["s17:edge_search_g"]],
                 "edge_registry_name": obs["inputs:edge_route_name"],
                 "ledger_system": [obs["s18_ledger:status"]["ledger"], obs["s18:ledger_stats"]],
                 "census_failed_native_user": [obs["s19_i53_bnative:status"][k] for k in ("unknown", "graph_line", "kg_populated", "ready_bfs")]
                                              + [obs["s19_i53_bnative:readers"]["metrics"], obs["s19_i53_bnative:readers"]["server"]],
                 "ledger_stats_unreadable": [obs["s19_i53_bnoledger:status"]["ledger"], obs["s19_i53_bnoledger:status"]["unknown"]],
                 "side_counts_failed": {k: obs["s19_i53_bpart:status"][k] for k in ("labels", "props", "edge_vecs", "ready_edge", "unknown")},
                 "no_native_ledger": obs["s19_i53_bmon:status"]["ledger"],
                 "cli_status_exit_with_errors": {u: [evidence[f"evidence:s19_{u}:readers"]["cli_status_exit"], evidence[f"evidence:s19_{u}:readers"]["server_errors"]] for u in USERS}}
    pins = ["iris_vector_graph/status.py", "iris_vector_graph/_engine/admin.py", "iris_vector_graph/_engine/schema.py",
            "iris_vector_graph/engine.py", "iris_vector_graph/schema.py", "iris_vector_graph/cypher_api.py",
            "iris_vector_graph/_engine/snapshot.py", "iris_vector_graph/security.py", "iris_vector_graph/_engine/nodes_edges.py",
            "iris_src/src/Graph/KG/Adjacency.cls", "iris_src/src/Graph/KG/TraversalBuild.cls",
            "iris_vector_graph/_engine/ledger.py", "iris_vector_graph/ledger/client.py", "iris_vector_graph/_engine/embeddings.py",
            "iris_vector_graph/cli.py"]
    body = {"kind": "binding", "model": "operator_reports", "fixture": runtime.NAME, "port": runtime.PORT, "namespace": NS,
            "product_baseline": runtime.PRODUCT, "run": RUN, "prefix": P,
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": ncases,
            "mismatches": [{"case": n, "expected": w_, "observed": g_} for n, w_, g_ in mism], "contrasts": contrasts,
            "observed": obs, "evidence": evidence, "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "operator_reports.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in pins}},
            "scope": "Actual product on IRIS 2026.1 (pin 3eaa79cf) in the dedicated namespace I53B, re-created from %SYS for each run "
                     "(iteration 53; I52B is no longer touched): "
                     "initialize_schema, create_node/create_edge (default and a named graph), sync, verify_sync(heal=True), delete_node, "
                     "START TRANSACTION + bulk_load_session + commit on a second engine, store_embeddings (routed and legacy), "
                     "search_nodes_by_vector, bm25_build/bm25_drop, setup again from the syncing and a fresh engine, save/restore_snapshot; "
                     "readers status() and its properties and report line, verify_sync, capabilities (fresh and cached), /server, /metrics, "
                     "/stats (FastAPI TestClient, no port), get_schema_visualization, snapshot_info. Expected answers from the port of the "
                     "model's writers and readers. Producer inputs from the product: the routed table's name and the diagram's label list. "
                     "Provider observed: SELECT DISTINCT answers the upper-cased name (P-COLLATE). Iteration 53: store_edge_embeddings "
                     "(routed, legacy) and edge_vector_search; ledger enable, two commits and a stale-head commit; four monitoring users "
                     "(role i53_brole with the namespace database and the Native API resources, or the database only; SELECT on all, "
                     "some or none of the Graph_KG tables) created in %SYS for the run and dropped after it, each reading status(), "
                     "/server, /metrics and `ivg status` (CliRunner over the in-process client). Producer inputs added: the routed "
                     "edge table's name and the rdf_labels/rdf_props row counts as _SYSTEM reads them."}
    d = REPO / ".g5/Verus_verification/results/operator_reports" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "contrasts", "all_sensitivities_detected", "sensitivities_detected_cases",
                                             "observation_tamper_detected", "elapsed_s")}, default=str))
    for x in body["mismatches"]:
        print("MISMATCH", json.dumps(x, default=str)[:600])


if __name__ == "__main__":
    main()
