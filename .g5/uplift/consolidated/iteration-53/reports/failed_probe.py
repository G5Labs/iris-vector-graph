"""Iteration 53 probe (review round 2 items M2, M3, m7, m8): failed count probes, the ledger counters, routed edge
vectors and cheap operator-reader cases, on the run-isolated fixture ivg-cont-20261117-iris, namespace I53.

I53 is created afresh from %SYS for this probe (nothing else writes there). A failed probe is made honestly: an IRIS
monitoring user that may read the namespace's database but holds SELECT on only some IVG tables, the way an operator
would give a dashboard a narrow role. Two such users are created (i53_mon: no table privilege; i53_part: the node,
edge, registry and node-vector tables only) and dropped at the end. For each user the probe reads the same facts through
status() (fields, unknown, errors, readiness flags, report lines), /server and /metrics (FastAPI TestClient, no port,
the user's credentials) and the CLI `ivg status` (click CliRunner over the same client); _SYSTEM's reading of the same
moment is the truth. This script only observes.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-53/reports/failed_probe.py)
"""
import dataclasses, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[4]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

NS = "I53"
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
P = "i53_"
DIM = 768
# user -> (Native API resources granted through the role i53_role, the Graph_KG tables it may SELECT; "*" every table but
# the ones listed after "-")
USERS = {"i53_mon": (False, []), "i53_native": (True, []),
         "i53_part": (True, ["nodes", "rdf_edges", "embedding_registry", "kg_NodeEmbeddings"]),
         "i53_noledger": (True, ["*", "-ledger_stats"])}
PW = "i53Pass!x"


def obs(f):
    try:
        return f()
    except Exception as ex:  # the error is an observation
        return {"error": type(ex).__name__, "msg": str(ex)[:400]}


def iris_sys(script):
    out = subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", "%SYS"],
                         input=script + "\nHalt\n", capture_output=True, text=True, timeout=300).stdout
    return out


def recreate_namespace():
    script = (f'Set ns="{NS}", dir="/usr/irissys/mgr/{NS.lower()}/"\n'
              'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
              'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
              'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
              'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
              'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
              'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
              'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!')
    out = iris_sys(script)
    assert "RESULT OK" in out, out


def make_role():
    # The Native API resources a dashboard engine needs (globals and class methods), plus the namespace's database.
    script = ('If ##class(Security.Roles).Exists("i53_role") { Set sc=##class(Security.Roles).Delete("i53_role") }\n'
              'Set sc=##class(Security.Roles).Create("i53_role","i53 probe monitoring role",'
              '"%DB_%DEFAULT:RW,%Native_GlobalAccess:U,%Native_ClassExecution:U")\n'
              'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!')
    out = iris_sys(script)
    assert "RESULT OK" in out, out


def drop_role():
    return "RESULT OK" in iris_sys('Set sc=##class(Security.Roles).Delete("i53_role")\n'
                                    'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!')


def make_user(name, native):
    # Database access (and, when native, the Native API resources): no SQL table privilege is implied.
    roles = "%DB_%DEFAULT,i53_role" if native else "%DB_%DEFAULT"
    script = (f'If ##class(Security.Users).Exists("{name}") {{ Set sc=##class(Security.Users).Delete("{name}") }}\n'
              f'Set sc=##class(Security.Users).Create("{name}","{roles}","{PW}","i53 probe monitoring user")\n'
              'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!')
    out = iris_sys(script)
    assert "RESULT OK" in out, out


def drop_user(name):
    return "RESULT OK" in iris_sys(f'Set sc=##class(Security.Users).Delete("{name}")\n'
                                    'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!')


def connect(user="_SYSTEM", pw="SYS"):
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username=user, password=pw)
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close()
        raise RuntimeError("fixture identity mismatch")
    return c


def engine(c):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c, embedding_dimension=DIM, native_cypher=False)


def st(e):
    s = e.status()
    return {
        "tables": dataclasses.asdict(s.tables), "unknown": list(s.unknown), "errors": list(s.errors),
        "kg_populated": s.adjacency.kg_populated, "nkg_populated": s.adjacency.nkg_populated,
        "kg_edge_count": s.adjacency.kg_edge_count, "kg_predicates_consistent": s.adjacency.kg_predicates_consistent,
        "bfs_path": s.adjacency.bfs_path,
        "ledger": s.ledger.to_dict() if s.ledger is not None else None,
        "ready": {k: getattr(s, k) for k in ("ready_for_bfs", "ready_for_multihop_bfs", "ready_for_vector_search",
                                              "ready_for_edge_search", "ready_for_full_text")},
        "vector_index_state": s.vector_index_state,
        "report": [ln for ln in s.report().splitlines() if "probe:" not in ln and "Probe time" not in ln],
    }


def ledger_stats(e):
    c = e.ledger.stats()
    return {"state": c.state, "commits_ok": c.commits_ok, "replays_idem": c.replays_idem,
            "rejections": {k: v for k, v in c.rejections.items() if v}, "head_seq": c.head_seq}


def http_cli(user, pw):
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    from click.testing import CliRunner
    from iris_vector_graph import cli as ivg_cli
    from iris_vector_graph.sdk import IVGClient
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE=NS, IRIS_USERNAME=user,
                      IRIS_PASSWORD=pw)
    for k in ("IVG_API_KEY", "IVG_READ_ONLY", "IVG_DISABLE_ARNO"):
        os.environ.pop(k, None)
    cypher_api._IRIS_NAMESPACE = NS
    cypher_api._engine_cache = None
    out = {}
    with TestClient(cypher_api.app) as client:
        r = client.get("/server")
        body = r.json()
        if isinstance(body, dict):
            body.pop("probe_ms", None); body.pop("iris_version", None); body.pop("ivg_version", None)
        out["/server"] = {"code": r.status_code, "body": body}
        r = client.get("/metrics")
        out["/metrics"] = {"code": r.status_code, "body": {ln.split()[0]: ln.split()[1] for ln in r.text.splitlines()
                                                          if ln and not ln.startswith("#") and not ln.startswith("ivg_status_probe_ms")}
                           if r.status_code == 200 else r.text[:300]}

        def fake_client(url, api_key):
            c = IVGClient("http://testserver", api_key=api_key)
            c._client = client
            return c
        orig = ivg_cli._client
        ivg_cli._client = fake_client
        try:
            res = CliRunner().invoke(ivg_cli.cli, ["status"])
            out["cli_status"] = {"exit": res.exit_code, "has_errors_key": '"errors"' in res.output,
                                 "errors_nonempty": '"errors": []' not in res.output}
        finally:
            ivg_cli._client = orig
    cypher_api._engine_cache = None
    return out


def main():
    out = {"run": RUN, "namespace": NS, "fixture": runtime.NAME, "product": runtime.PRODUCT, "steps": {}}
    S = out["steps"]
    recreate_namespace()
    c1 = connect(); e1 = engine(c1)
    S["setup"] = obs(lambda: {k: v for k, v in e1.initialize_schema().items() if k in ("schema", "warnings")})
    g = "i53g"
    vec = [0.0] * DIM; vec[0] = 1.0
    e1.create_node(P + "a", labels=["A"], properties={"name": "alpha"})
    e1.create_node(P + "b", labels=["B"], properties={"name": "beta"})
    e1.create_edge(P + "a", "R", P + "b")
    e1.sync()
    e1.store_embeddings([{"node_id": P + "a", "embedding": vec}])          # legacy node vectors
    # m7: routed edge vectors only (named graph), then a legacy edge vector
    e1.create_node(P + "c", graph=g); e1.create_node(P + "d", graph=g); e1.create_edge(P + "c", "E", P + "d", graph=g)
    S["edge_routed_store"] = obs(lambda: e1.store_edge_embeddings([{"s": P + "c", "p": "E", "o_id": P + "d", "embedding": vec}], graph=g))
    cur = c1.cursor()
    S["edge_registry"] = obs(lambda: (cur.execute("SELECT table_name, COALESCE(kind,'node') FROM Graph_KG.embedding_registry"),
                                      [list(r) for r in cur.fetchall()])[1])
    S["edge_registry_distinct"] = obs(lambda: (cur.execute("SELECT DISTINCT table_name, COALESCE(kind,'node') FROM Graph_KG.embedding_registry"),
                                               [list(r) for r in cur.fetchall()])[1])
    S["edge_routed_status"] = st(e1)
    S["edge_routed_search"] = obs(lambda: len(e1.edge_vector_search(vec, top_k=3, graph=g)))
    S["edge_legacy_store"] = obs(lambda: e1.store_edge_embeddings([{"s": P + "a", "p": "R", "o_id": P + "b", "embedding": vec}]))
    S["edge_legacy_status"] = {k: v for k, v in st(e1).items() if k in ("tables", "ready", "errors", "unknown")}
    # m8 (cheap): SHOW INDEXES for a BM25 index over a property no node holds
    S["bm25_empty_build"] = obs(lambda: e1.bm25_build("i53bm_empty", ["no_such_prop"]))
    S["show_indexes_empty_bm25"] = obs(lambda: [r for r in e1.execute_cypher("SHOW INDEXES").rows if "i53bm" in str(r)])
    S["bm25_empty_search"] = obs(lambda: e1.bm25_search("i53bm_empty", "alpha", k=3) if hasattr(e1, "bm25_search") else None)
    # M3: the ledger, after commits and a rejected commit
    from iris_vector_graph.ledger.changeset import Changeset
    S["ledger_enable"] = obs(lambda: str(e1.ledger.enable()))
    S["commit1"] = obs(lambda: str(e1.ledger.commit(Changeset(actor="i53", actor_type="test").create_node(P + "l1"))))
    h1 = obs(lambda: e1.ledger.head().revision_id)
    S["head_after_1"] = h1
    S["commit2"] = obs(lambda: str(e1.ledger.commit(Changeset(actor="i53", actor_type="test").create_node(P + "l2"))))
    S["commit_stale"] = obs(lambda: str(e1.ledger.commit(Changeset(actor="i53", actor_type="test", expected_head=h1).create_node(P + "l3"))))
    S["ledger_system"] = {"status": st(e1)["ledger"], "stats": obs(lambda: ledger_stats(e1))}
    S["truth"] = st(e1)
    S["truth_http"] = http_cli("_SYSTEM", "SYS")
    # M2 / M3: the same moment through monitoring users with narrow SQL privileges
    created = []
    make_role()
    cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Graph_KG'")
    every = [r[0] for r in cur.fetchall()]
    S["graph_kg_tables"] = every
    for user, (native, spec) in USERS.items():
        make_user(user, native); created.append(user)
        tables = ([t for t in every if "-" + t not in spec] if "*" in spec else spec)
        for t in tables:
            cur.execute(f"GRANT SELECT ON Graph_KG.{t} TO {user}")
        cu = obs(lambda: connect(user, PW))
        if isinstance(cu, dict):
            S[user] = {"connect": cu}
            continue
        eu = engine(cu)
        S[user] = {"native": native, "grants": tables, "status": obs(lambda: st(eu)), "ledger_stats": obs(lambda: ledger_stats(eu)),
                   "ledger_meta": obs(lambda: eu.ledger.meta()),
                   "http": obs(lambda: http_cli(user, PW))}
        cu.close()
    out["users_dropped"] = {u: drop_user(u) for u in created}
    out["role_dropped"] = drop_role()
    path = HERE / f"failed-probe-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(path)
    print(json.dumps(out, indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
