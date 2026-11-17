"""W58 probe (iteration 52): operator reports on the run-isolated fixture ivg-cont-20261117-iris, namespace I52.

Status counts every graph of a namespace, so this probe runs in the fresh namespace I52 (created from %SYS for this
iteration; nothing else writes there). One history of public writes; after each step the probe records every reader
of the same facts: EngineStatus fields and properties, report() text, verify_sync(), capabilities, the HTTP routes
(FastAPI TestClient, no port) and the CLI (click CliRunner over the same in-process client), plus the operation each
readiness flag announces. Expected values are in reports-PAIRS.md (frozen before the deciding source was read); this
script only observes.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-52/reports_probe.py)
"""
import dataclasses, json, os, sys, tempfile, time, traceback, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

NS = "I52"
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
P = "i52_"
DIM = 768


def obs(f):
    try:
        return f()
    except Exception as ex:  # the error is an observation
        return {"error": type(ex).__name__, "msg": str(ex)[:400]}


def connect():
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username="_SYSTEM", password="SYS")
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close()
        raise RuntimeError("fixture identity mismatch")
    return c


def engine(c):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c, embedding_dimension=DIM, native_cypher=False)


def st(e, internals=False):
    s = e.status(internals=internals)
    d = dataclasses.asdict(s)
    d.pop("probe_ms", None)
    for k in ("vector_index_state", "fulltext_index_state", "acceleration_state", "acceleration_label",
              "ready_for_bfs", "ready_for_multihop_bfs", "ready_for_vector_search", "ready_for_edge_search",
              "ready_for_full_text"):
        d[k] = getattr(s, k)
    d["report"] = [ln for ln in s.report(internals=internals).splitlines() if "probe:" not in ln]
    d["graph_line"] = [ln for ln in s.report().splitlines() if ln.startswith("Graph:")]
    return d


def vs(e, heal=False):
    r = e.verify_sync(heal=heal)
    return dict(r.to_dict(), bool=bool(r))


def caps(e):
    return dataclasses.asdict(e.capabilities)


def http(client):
    out = {}
    for path in ("/stats", "/server", "/indexes", "/schema"):
        r = client.get(path)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        if isinstance(body, dict):
            body.pop("probe_ms", None)
            body.pop("iris_version", None)
        out[path] = {"code": r.status_code, "body": body}
    r = client.get("/metrics")
    out["/metrics"] = {"code": r.status_code,
                       "body": {ln.split()[0]: ln.split()[1] for ln in r.text.splitlines()
                                if ln and not ln.startswith("#") and not ln.startswith("ivg_status_probe_ms")}}
    return out


def cli(client, args):
    from click.testing import CliRunner
    from iris_vector_graph import cli as ivg_cli
    from iris_vector_graph.sdk import IVGClient

    def fake_client(url, api_key):
        c = IVGClient("http://testserver", api_key=api_key)
        c._client = client
        return c

    orig = ivg_cli._client
    ivg_cli._client = fake_client
    try:
        r = CliRunner().invoke(ivg_cli.cli, args)
        return {"exit": r.exit_code, "output": r.output}
    finally:
        ivg_cli._client = orig


def ops(e, src):
    """The operations the readiness flags announce, on the current state."""
    return {
        "khop": obs(lambda: sorted(n if isinstance(n, str) else n.get("id", str(n)) for n in e.khop(src, hops=2)["nodes"])),
        "varlen": obs(lambda: e.execute_cypher(
            "MATCH (a {node_id: $s})-[*1..2]->(x) RETURN x.node_id AS x ORDER BY x", {"s": src}).rows),
        "pagerank": obs(lambda: [(n, round(float(v), 4)) for n, v in (e.kg_PAGERANK() or [])][:6]),
    }


def main():
    out = {"run": RUN, "namespace": NS, "fixture": runtime.NAME, "product": runtime.PRODUCT, "steps": {}}
    S = out["steps"]
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE=NS, IRIS_USERNAME="_SYSTEM",
                      IRIS_PASSWORD="SYS")
    for k in ("IVG_API_KEY", "IVG_READ_ONLY", "IVG_DISABLE_ARNO"):
        os.environ.pop(k, None)

    c1 = connect()
    e1 = engine(c1)
    # A fresh engine before setup sees nothing deployed
    S["pre_setup"] = {"caps": obs(lambda: caps(e1)), "status": obs(lambda: st(e1))}
    e1.capabilities = None
    S["setup"] = obs(lambda: {k: v for k, v in e1.initialize_schema().items() if k in ("schema", "kg_built", "warnings")})
    c2 = connect(); e2 = engine(c2)
    S["s0"] = {"e1": st(e1), "e1_caps": caps(e1), "e2_caps": caps(e2), "vs": vs(e1), "nkg_meta": obs(lambda: {
        "nodeCount_defined": int(e1._iris_obj().isDefined("^NKG", "$meta", "nodeCount"))})}

    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    with TestClient(cypher_api.app) as client:
        S["s0"]["http"] = http(client)

        # 1. one edge in the default graph, no sync
        e1.create_node(P + "a", labels=["A"], properties={"name": "alpha"})
        e1.create_node(P + "b", labels=["B"], properties={"name": "beta"})
        e1.create_edge(P + "a", "R", P + "b")
        S["s1_edge"] = {"e1": st(e1), "vs": vs(e1), "ops": ops(e1, P + "a"), "http": http(client),
                        "cli_status": cli(client, ["status"]), "cli_indexes": cli(client, ["indexes", "list"]),
                        "cli_schema": cli(client, ["schema", "status"]), "e2_caps": caps(e2),
                        "e3_caps": caps(engine(connect()))}

        # 2. sync
        S["s2_sync"] = {"sync": obs(lambda: e1.sync())}
        S["s2_sync"].update({"e1": st(e1), "vs": vs(e1), "ops": ops(e1, P + "a"), "http": http(client),
                             "e1_caps": caps(e1), "e2_caps": caps(e2), "e4_caps": caps(engine(connect()))})

        # 3. a second default-graph edge without sync
        e1.create_node(P + "c", labels=["C"])
        e1.create_edge(P + "b", "R", P + "c")
        S["s3_second_edge"] = {"e1": st(e1), "vs": vs(e1), "ops": ops(e1, P + "a")}

        # 4. the same triple a-R->b in named graph g
        g = "i52g"
        e1.create_node(P + "a", labels=["A"], graph=g)
        e1.create_node(P + "b", labels=["B"], graph=g)
        e1.create_edge(P + "a", "R", P + "b", graph=g)
        S["s4_same_triple_other_graph"] = {"e1": st(e1), "vs": vs(e1), "vs_e2": vs(e2), "http": http(client),
                                           "counts": {"node_count": e1.node_count(), "node_count_g": e1.node_count(graph=g),
                                                      "edge_count": e1.edge_count(), "edge_count_g": e1.edge_count(graph=g)}}
        S["s4_heal"] = {"heal": vs(e1, heal=True), "after": vs(e1), "after_e2": vs(e2),
                        "kg_edge_count": st(e1)["adjacency"]["kg_edge_count"]}
        S["s4_sync_again"] = {"sync": obs(lambda: e1.sync()), "after": vs(e1), "after_e2": vs(e2)}

        # 5. a new graph-only triple in g (not in default)
        e1.create_node(P + "d", labels=["D"], graph=g)
        e1.create_edge(P + "b", "S", P + "d", graph=g)
        S["s5_g_only_edge"] = {"vs": vs(e1), "e1": st(e1)}

        # 6. delete a default-graph node: deleting engine vs another engine
        S["s6_delete"] = {"delete": obs(lambda: e1.delete_node(P + "c", graph=None))}
        S["s6_delete"].update({"vs_e1": vs(e1), "vs_e2": vs(e2), "e1_pending": st(e1)["pending_sync"],
                               "e2_pending": st(e2)["pending_sync"], "e1": st(e1)})
        e1.sync()

        # 7. vectors only in a routed table (graph g)
        vec = [0.0] * DIM; vec[0] = 1.0
        S["s7_routed_vectors"] = {"store": obs(lambda: e1.store_embeddings([{"node_id": P + "a", "embedding": vec}], graph=g))}
        S["s7_routed_vectors"].update({
            "e1": st(e1), "http": http(client),
            "search_g": obs(lambda: [r if isinstance(r, (str, list, tuple)) else r for r in e1.search_nodes_by_vector(vec, k=3, graph=g)]),
            "search_default": obs(lambda: e1.search_nodes_by_vector(vec, k=3)),
            "embedding_count": obs(lambda: e1.embedding_count()), "embedding_count_g": obs(lambda: e1.embedding_count(graph=g))})

        # 8. a vector in the default table
        S["s8_default_vector"] = {"store": obs(lambda: e1.store_embeddings([{"node_id": P + "b", "embedding": vec}]))}
        S["s8_default_vector"].update({"e1": st(e1), "http": http(client),
                                       "search_default": obs(lambda: e1.search_nodes_by_vector(vec, k=3))})

        # 9. BM25 build, then drop
        S["s9_bm25"] = {"build": obs(lambda: e1.bm25_build("i52bm", ["name"]))}
        S["s9_bm25"].update({"e1": st(e1), "http": http(client), "search": obs(lambda: e1.bm25_search("i52bm", "alpha")),
                             "cli_indexes": cli(client, ["indexes", "list"])})
        S["s10_bm25_drop"] = {"drop": obs(lambda: e1.bm25_drop("i52bm"))}
        S["s10_bm25_drop"].update({"e1": st(e1), "http": http(client),
                                   "search": obs(lambda: e1.bm25_search("i52bm", "alpha"))})

        # 11. an edge vector
        evec = [0.0] * DIM; evec[1] = 1.0
        S["s11_edge_vector"] = {"store": obs(lambda: e1.store_edge_embeddings(
            [{"s": P + "a", "p": "R", "o": P + "b", "embedding": evec}]))}
        S["s11_edge_vector"].update({"e1": st(e1)})

        # 12. internals
        S["s12_internals"] = {"true": st(e1, internals=True), "false": st(e1, internals=False)}

        # 13. bulk_load_session in a caller transaction, committed / rolled back; another engine reads
        def bulk(tag, commit):
            c5 = connect(); e5 = engine(c5)
            res = {}
            try:
                cur = c5.cursor(); cur.execute("START TRANSACTION")  # the caller's transaction
                e5.create_node(P + tag + "x")  # a write of the caller's (TLEVEL > 0)
                with e5.bulk_load_session() as sess:
                    sess.add_nodes([{"id": P + tag + "y", "labels": ["Y"]}])
                    sess.add_edges([(P + tag + "x", P + tag + "y", "BL")])
                res["inside_pending_e5"] = e5.status().pending_sync
                cur.execute("SELECT $TLEVEL"); res["tlevel_before_end"] = int(cur.fetchone()[0])
                (c5.commit() if commit else c5.rollback())
                res["after_pending_e5"] = e5.status().pending_sync
                res["after_pending_e1"] = e1.status().pending_sync
                res["vs_e5"] = vs(e5)
                res["rows_x"] = e1.get_node_count(graph=None)
            except Exception as ex:
                res["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
                res["trace"] = traceback.format_exc()[-800:]
            finally:
                try:
                    c5.rollback()
                except Exception:
                    pass
            return res
        S["s13_bulk_commit"] = bulk("bc", True)
        S["s13_bulk_rollback"] = bulk("br", False)
        e1.sync()

        # 14. ledger off, then on with one commit
        S["s14_ledger"] = {"off": st(e1)["ledger"]}
        try:
            e1.ledger.enable()
            from iris_vector_graph.ledger import ChangeSet  # noqa: F401
        except Exception as ex:
            S["s14_ledger"]["enable_error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
        S["s14_ledger"]["after_enable"] = obs(lambda: st(e1)["ledger"])

        # 15. snapshot: save, info, write more, restore, status
        tmp = Path(tempfile.mkdtemp(prefix="i52snap"))
        path = str(tmp / "snap.zip")
        before = st(e1)["tables"]
        saved = obs(lambda: e1.save_snapshot(path))
        info = obs(lambda: e1.snapshot_info(path))
        if isinstance(info, dict) and "metadata" in info:
            info = {k: v for k, v in info.items() if k != "metadata"}
            info["metadata_keys"] = sorted(e1.snapshot_info(path)["metadata"].keys())
            info["metadata_ivg_version"] = e1.snapshot_info(path)["metadata"].get("ivg_version")
        e1.create_node(P + "late", labels=["L"])
        restored = obs(lambda: {k: v for k, v in e1.restore_snapshot(path).items() if k in ("restored_tables", "failed_rows")})
        after = st(e1)["tables"]
        bad = str(tmp / "bad.zip")
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("other.txt", "x")
        S["s15_snapshot"] = {"status_tables_at_save": before, "saved_tables": saved.get("tables") if isinstance(saved, dict) else saved,
                             "saved_globals": saved.get("globals") if isinstance(saved, dict) else None,
                             "info": info, "restored": restored, "status_tables_after_restore": after,
                             "info_no_metadata": obs(lambda: e1.snapshot_info(bad)),
                             "late_exists": obs(lambda: e1.node_exists(P + "late"))}

        # 16. schema visualization: a predicate whose endpoints carry no label
        e1.create_node(P + "u1"); e1.create_node(P + "u2")
        e1.create_edge(P + "u1", "UNLAB", P + "u2")
        S["s16_schema_viz"] = obs(lambda: e1.get_schema_visualization())

        # 17. acceleration label under IVG_DISABLE_ARNO
        os.environ["IVG_DISABLE_ARNO"] = "1"
        e6 = engine(connect())
        S["s17_disable_arno"] = {"label": obs(lambda: e6.status().acceleration_label),
                                 "arno": obs(lambda: dataclasses.asdict(e6.status().arno))}
        os.environ.pop("IVG_DISABLE_ARNO", None)
        S["s17_default_arno"] = {"label": st(e1)["acceleration_label"], "arno": st(e1)["arno"],
                                 "store_caps": obs(lambda: e1._store.capabilities())}

    out["source_hashes"] = runtime.hashes()
    dest = HERE / f"reports-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(dest)


if __name__ == "__main__":
    main()
