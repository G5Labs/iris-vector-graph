"""Binding for operator_reports (W58, iteration 52) on the run-isolated continuation fixture.

Status counts every graph of a namespace, so the binding drops and re-creates its own namespace I52B (from %SYS, in
the container ivg-cont-20261117-iris only) and replays one history of public writes there: setup on the empty
namespace, create_edge, sync(), a triple shared by two graphs, verify_sync(heal=True), delete_node, a caller
transaction around bulk_load_session, routed and legacy vectors, bm25_build/bm25_drop, setup again from the engine
that synced and from a fresh engine, a snapshot save/restore. After each step it reads the same facts through every
reader (EngineStatus fields, readiness properties and report line, verify_sync, a fresh engine's capabilities and the
calling engine's cached ones, /server and /stats through the in-process FastAPI client, the schema diagram,
snapshot_info) and compares them with a Python port of operator_reports.rs's writers and readers applied to the same
history. Expected answers come from the port, never from the product's answers. The only producer inputs taken from
the product are the routed table's registry name (the writer's hash) and the snapshot path. Mutations mirror the
model's 17 controls; one deciding observation is tampered.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/operator_reports/binding.py)
"""
import dataclasses, hashlib, json, os, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

NS = "I52B"
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
P = "i52b_"
DIM = 768
MUTS = ["registry-keeps-case", "verify-counts-distinct-rows", "nkg-per-graph", "heal-rereads", "status-pending-reads-nkg",
        "setup-inits-skeleton", "put-always-interns", "multihop-needs-nkg", "sync-sets-markers", "setup-marks-empty",
        "engine-cache-unchanged", "bulk-leaves-flag", "delete-keeps-nkg", "drop-keeps-index", "stats-every-graph",
        "viz-none-distinct", "setup-skips-bootstrap"]


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

    def copy(self):
        n = Ns(); n.__dict__.update({k: (list(v) if isinstance(v, list) else set(v) if isinstance(v, set) else v)
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


def connect():
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username="_SYSTEM", password="SYS")
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
    return out


def main():
    t0 = time.time()
    obs = history(True, None)
    inputs = {k: v for k, v in obs.items() if k.startswith("inputs:")}
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
    tamper_detected = bool(compare(want, tampered))
    contrasts = {"first_edge_status_vs_verify": [obs["s1_first_edge:status"]["sync_line"], obs["s1_first_edge:verify"]["in_sync"],
                                                  obs["s1_first_edge:status"]["nkg_populated"], obs["s1_first_edge:status"]["ready_multihop"]],
                 "unique_after_sync_in_sync": obs["s3_put_after_sync:verify"]["in_sync"],
                 "heal_report": obs["s5:heal"], "after_heal": obs["s5_after_heal:verify"], "after_sync_again": obs["s6_sync_again:verify"],
                 "routed_only": [obs["s9_routed_vectors:status"]["node_vecs"], obs["s9_routed_vectors:status"]["vec_state"], obs["s9:search_g"]],
                 "registry_name_vs_distinct": [obs["inputs:route_name"], obs["provider:distinct_text"]],
                 "caps_fresh_after_sync": obs["s2_sync:caps_fresh"], "caps_e1_after_sync": obs["s2:caps_e1"],
                 "caps_after_e1_setup": obs["s15:caps_after_e1_setup"], "caps_after_fresh_setup": obs["s15:caps_after_fresh_setup"],
                 "stats_vs_server_nodes": [obs["s14:stats_nodes"], obs["s14:server"]["nodes"]], "viz": obs["s14:viz"]}
    pins = ["iris_vector_graph/status.py", "iris_vector_graph/_engine/admin.py", "iris_vector_graph/_engine/schema.py",
            "iris_vector_graph/engine.py", "iris_vector_graph/schema.py", "iris_vector_graph/cypher_api.py",
            "iris_vector_graph/_engine/snapshot.py", "iris_vector_graph/security.py", "iris_vector_graph/_engine/nodes_edges.py",
            "iris_src/src/Graph/KG/Adjacency.cls", "iris_src/src/Graph/KG/TraversalBuild.cls"]
    body = {"kind": "binding", "model": "operator_reports", "fixture": runtime.NAME, "port": runtime.PORT, "namespace": NS,
            "product_baseline": runtime.PRODUCT, "run": RUN, "prefix": P,
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": ncases,
            "mismatches": [{"case": n, "expected": w_, "observed": g_} for n, w_, g_ in mism], "contrasts": contrasts,
            "observed": obs, "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "operator_reports.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in pins}},
            "scope": "Actual product on IRIS 2026.1 (pin 3eaa79cf) in the dedicated namespace I52B, re-created from %SYS for each run: "
                     "initialize_schema, create_node/create_edge (default and a named graph), sync, verify_sync(heal=True), delete_node, "
                     "START TRANSACTION + bulk_load_session + commit on a second engine, store_embeddings (routed and legacy), "
                     "search_nodes_by_vector, bm25_build/bm25_drop, setup again from the syncing and a fresh engine, save/restore_snapshot; "
                     "readers status() and its properties and report line, verify_sync, capabilities (fresh and cached), /server, /metrics, "
                     "/stats (FastAPI TestClient, no port), get_schema_visualization, snapshot_info. Expected answers from the port of the "
                     "model's writers and readers. Producer inputs from the product: the routed table's name and the diagram's label list. "
                     "Provider observed: SELECT DISTINCT answers the upper-cased name (P-COLLATE)."}
    d = REPO / ".g5/Verus_verification/results/operator_reports" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "contrasts", "all_sensitivities_detected", "sensitivities_detected_cases",
                                             "observation_tamper_detected", "elapsed_s")}, default=str))
    for x in body["mismatches"]:
        print("MISMATCH", json.dumps(x, default=str)[:600])


if __name__ == "__main__":
    main()
