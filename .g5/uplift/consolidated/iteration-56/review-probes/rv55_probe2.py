"""Review 53-55 follow-up probe: bug-cyp-136 (native vs SQL grouping), Bolt explicit-transaction rollback (F-1601),
length(p) of a null OPTIONAL path. Fixture ivg-cont-20261117-iris, USER, prefix rv55b_<tag>_."""
import asyncio, json, os, socket, sys, threading, time
sys.path.insert(0, "/tmp/review-53-55/tree/.g5/uplift/consolidated/iteration-36")
os.environ.setdefault("IVG_REPO", "/tmp/review-53-55/tree")
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"rv55b_{TAG}_"; G = f"RV55BG{TAG}"; A = f"RV55BA{TAG}"; K = f"RV55BK{TAG}"
out = {"run": RUN, "tag": TAG, "prefix": P}


def norm(v):
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in v.items()}
    if isinstance(v, (bool, int, float, str)) or v is None:
        return [type(v).__name__, v]
    return [type(v).__name__, repr(v)]


def main():
    from iris_vector_graph.cypher.parser import parse_query
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = runtime.engine(c)
    en = IRISGraphEngine(c, embedding_dimension=768, native_cypher=True)

    def q(key, text, params=None):
        rec = {"q": text}
        for lab, eng in (("sql", e), ("native_engine", en)):
            try:
                r = eng.execute_cypher(text, params or {})
                rec[lab] = {"rows": norm([list(x) for x in r.rows])}
                if getattr(r, "error", None):
                    rec[lab]["error"] = str(r.error)[:300]
            except Exception as x:
                rec[lab] = {"exc": f"{type(x).__name__}: {x}"[:300]}
        try:
            nr = en._try_native(parse_query(text), params or {})
            rec["_try_native"] = "declined" if nr is None else norm([list(x) for x in nr.rows])
        except Exception as x:
            rec["_try_native"] = {"exc": f"{type(x).__name__}: {x}"[:300]}
        out[key] = rec
        print(key, json.dumps(rec, default=str)[:700])

    for i, k in enumerate([1, "1", 1.0, "true", True]):
        e.create_node(f"{P}g{i}", labels=[G], properties={"k": k})
    e.create_node(f"{P}a1", labels=[A], properties={"name": "a1"})
    e.create_node(f"{P}a2", labels=[A], properties={"name": "a2"})
    e.create_node(f"{P}a3", labels=[A], properties={"name": "a3"})
    e.create_edge(f"{P}a1", K, f"{P}a2")
    e.create_edge(f"{P}a2", K, f"{P}a3")

    q("cyp136_group", f"MATCH (n:{G}) RETURN n.k AS k, count(*) AS c")
    q("len_null_fixed", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH p = (a)-[:{K}]->(b) RETURN length(p) AS l, p IS NULL AS isnull")
    q("len_nonnull_fixed", f"MATCH (a:{A} {{name: 'a1'}}) OPTIONAL MATCH p = (a)-[:{K}]->(b) RETURN length(p) AS l")
    q("len_null_var", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH p = (a)-[:{K}*1..2]->(b) RETURN length(p) AS l")
    q("len_null_all", f"MATCH (a:{A}) OPTIONAL MATCH p = (a)-[:{K}]->(b) RETURN a.name AS a, length(p) AS l ORDER BY a")
    q("len_literal_null", "RETURN length(null) AS l")

    # Bolt explicit transaction rollback / commit
    try:
        import neo4j
        from iris_vector_graph import bolt_server as bs
        c2 = runtime.connect(); e2 = runtime.engine(c2)
        s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
        loop = asyncio.new_event_loop()
        th = threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True); th.start()
        asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
        time.sleep(0.5)
        b = {}
        with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x")) as d:
            with d.session() as s:
                tx = s.begin_transaction()
                tx.run(f"CREATE (:{A} {{id: '{P}tx_rb', name: 'rb'}})").consume()
                tx.rollback()
            with d.session() as s:
                tx = s.begin_transaction()
                tx.run(f"CREATE (:{A} {{id: '{P}tx_fail', name: 'fail'}})").consume()
                try:
                    tx.run("RETURN 1 AS a UNION RETURN 2 AS b").consume()
                except Exception as x:
                    b["tx_fail_error"] = type(x).__name__
                try:
                    tx.rollback()
                except Exception as x:
                    b["tx_fail_rollback"] = type(x).__name__
            with d.session() as s:
                def work(t):
                    t.run(f"CREATE (:{A} {{id: '{P}tx_fn', name: 'fn'}})").consume()
                    raise RuntimeError("client aborts the unit of work")
                try:
                    s.execute_write(work)
                except Exception as x:
                    b["execute_write_abort"] = type(x).__name__
        e3 = runtime.engine(runtime.connect())
        for key in ("tx_rb", "tx_fail", "tx_fn"):
            r = e3.execute_cypher(f"MATCH (n:{A}) WHERE n.id = '{P}{key}' RETURN count(n) AS c", {})
            b[f"persisted_{key}"] = r.rows[0][0] if r.rows else None
            b[f"get_node_{key}"] = e3.get_node(f"{P}{key}") is not None
        out["bolt_tx"] = b
        print("bolt_tx", json.dumps(b, default=str))
        loop.call_soon_threadsafe(loop.stop)
    except Exception as x:
        out["bolt_tx_exc"] = f"{type(x).__name__}: {x}"[:400]; print("bolt exc", repr(x))

    p = f"/tmp/review-53-55/probes/rv55b-observed-{RUN}.json"
    json.dump(out, open(p, "w"), indent=1, default=str); print("wrote", p)


if __name__ == "__main__":
    main()
