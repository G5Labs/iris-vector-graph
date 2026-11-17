"""Review 53-55 independent probe (read-only reviewer). Fixture ivg-cont-20261117-iris, USER, prefix rv55_<tag>_.
Reproduces bug-cyp-134/135/136/138, bug-plt-123, bug-cyp-145, F-1602 and probes neighbor cases derived by the reviewer."""
import asyncio, json, os, socket, sys, threading, time
sys.path.insert(0, "/tmp/review-53-55/tree/.g5/uplift/consolidated/iteration-36")
os.environ.setdefault("IVG_REPO", "/tmp/review-53-55/tree")
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"rv55_{TAG}_"; G = f"RV55G{TAG}"; A = f"RV55A{TAG}"; K = f"RV55K{TAG}"; S = f"RV55S{TAG}"
out = {"run": RUN, "tag": TAG, "prefix": P}


def norm(v):
    try:
        import neo4j.graph as g
        if isinstance(v, g.Node):
            return {"node": dict(v).get("id", None), "labels": sorted(v.labels), "eid": v.element_id}
        if isinstance(v, g.Relationship):
            return {"rel": v.type, "start": (dict(v.start_node).get("id") if v.start_node else None),
                    "start_eid": v.start_node.element_id if v.start_node else None,
                    "end_eid": v.end_node.element_id if v.end_node else None}
    except ImportError:
        pass
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in v.items()}
    if isinstance(v, (bool, int, float, str)) or v is None:
        return [type(v).__name__, v]
    return [type(v).__name__, repr(v)]


def main():
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = runtime.engine(c)

    def q(key, text, params=None, native=False):
        rec = {"q": text, "params": params or {}}
        try:
            r = e.execute_cypher(text, params or {})
            rec["sql"] = {"columns": list(r.columns or []), "rows": norm([list(x) for x in r.rows])}
            if getattr(r, "error", None):
                rec["sql"]["error"] = str(r.error)[:300]
        except Exception as x:
            rec["sql"] = {"exc": f"{type(x).__name__}: {x}"[:300]}
        if native:
            try:
                nr = e._try_native(parse_query(text), params or {})
                rec["native"] = "declined" if nr is None else norm([list(x) for x in nr.rows])
            except Exception as x:
                rec["native"] = {"exc": f"{type(x).__name__}: {x}"[:300]}
        out[key] = rec
        print(key, json.dumps(rec, default=str)[:600])
        return rec

    # --- fixture (API-written)
    for i, k in enumerate([1, 1, "1", 1.5]):
        e.create_node(f"{P}g{i}", labels=[G], properties={"k": k})
    e.create_node(f"{P}f0", labels=[S], properties={"k": 1})
    e.create_node(f"{P}f1", labels=[S], properties={"k": 1.0})
    e.create_node(f"{P}a1", labels=[A], properties={"name": f"{P}a1", "v": 1, "f": 2.5})
    e.create_node(f"{P}a2", labels=[A], properties={"name": f"{P}a2", "v": 2})
    e.create_edge(f"{P}a1", K, f"{P}a2")

    # bug-cyp-135 / -136
    q("cyp135_group", f"MATCH (n:{G}) RETURN n.k AS k, count(*) AS c ORDER BY c DESC", native=True)
    q("cyp135_distinct", f"MATCH (n:{G}) RETURN DISTINCT n.k AS k")
    q("cyp135_countdistinct", f"MATCH (n:{G}) RETURN count(DISTINCT n.k) AS c", native=True)
    # neighbor: int 1 and float 1.0 (open question; aggregate_results theorem_numeric_distinct_normalizes_int_and_whole_double)
    q("int_float_group", f"MATCH (n:{S}) RETURN n.k AS k, count(*) AS c", native=True)
    q("int_float_countdistinct", f"MATCH (n:{S}) RETURN count(DISTINCT n.k) AS c", native=True)
    q("int_float_distinct", f"MATCH (n:{S}) RETURN DISTINCT n.k AS k", native=True)
    # bug-cyp-138
    q("cyp138_union", f"MATCH (n:{A} {{name: '{P}a1'}}) RETURN n.v AS x UNION RETURN 0 AS x")
    q("cyp138_union_f", f"MATCH (n:{A} {{name: '{P}a1'}}) RETURN n.f AS x UNION ALL RETURN 0 AS x")
    q("cyp138_plain", f"MATCH (n:{A} {{name: '{P}a1'}}) RETURN n.v AS x")
    # neighbor: UNION column-name mismatch must fail (openCypher), UNION dedup of nulls
    q("union_name_mismatch", "RETURN 1 AS a UNION RETURN 2 AS b")
    q("union_null_dedup", "RETURN null AS a UNION RETURN null AS a")
    # bug-cyp-134 and percentile neighbors
    q("cyp134_p90", "UNWIND [10, 20, 30, 40] AS x RETURN percentileDisc(x, 0.9) AS p")
    q("cyp134_p60", "UNWIND [10, 20, 30, 40] AS x RETURN percentileDisc(x, 0.6) AS p")
    q("pct_nulls", "UNWIND [10, null, 30] AS x RETURN percentileDisc(x, 0.5) AS d, percentileCont(x, 0.5) AS c")
    q("pct_large_max", "UNWIND range(1, 3000) AS x RETURN percentileDisc(x, 1.0) AS d")
    q("pct_large_max_9000", "UNWIND range(1, 9000) AS x RETURN percentileDisc(x, 1.0) AS d")
    q("pct_strings_stored", f"MATCH (n:{G}) RETURN percentileDisc(n.k, 1.0) AS d")
    q("pct_param_null", "UNWIND [10, 20, 30] AS x RETURN percentileDisc(x, $p) AS d", {"p": None})
    q("pct_param_str", "UNWIND [10, 20, 30] AS x RETURN percentileDisc(x, $p) AS d", {"p": "0.5"})
    q("pct_grouped_mixed", f"MATCH (n:{A}) RETURN percentileDisc(n.v, 1.0) AS d")
    # paging neighbors
    q("limit_zero", f"MATCH (n:{G}) RETURN n.k LIMIT 0")
    q("limit_str_param", f"MATCH (n:{G}) RETURN n.k LIMIT $l", {"l": "2"})
    # path element functions on a null path (OPTIONAL MATCH)
    q("path_null_opt", f"MATCH (a:{A} {{name: '{P}a2'}}) OPTIONAL MATCH p = (a)-[:{K}]->(b) RETURN length(p) AS l, nodes(p) AS ns, relationships(p) AS rs")
    # DELETE neighbors: DELETE of a null from OPTIONAL MATCH is a no-op; non-DETACH delete with an incoming edge refused
    q("delete_null", f"MATCH (a:{A} {{name: '{P}a2'}}) OPTIONAL MATCH (a)-[:{K}]->(b) DELETE b RETURN count(*) AS c")
    q("delete_incoming_only", f"MATCH (a:{A} {{name: '{P}a2'}}) DELETE a")
    q("after_delete_incoming", f"MATCH (a:{A} {{name: '{P}a2'}}) RETURN count(a) AS c")
    # bug-cyp-145 neighbor: string literal equals a stored integer
    q("cyp145_str_eq_int", f"MATCH (n:{A}) WHERE n.v = '1' RETURN n.name AS name")
    q("cyp145_int_eq_int", f"MATCH (n:{A}) WHERE n.v = 1 RETURN n.name AS name")

    # BM25 neighbors: ties and k
    try:
        for i, doc in [("9", "zeta alpha"), ("10", "zeta alpha"), ("a", "zeta alpha"), ("B", "zeta alpha")]:
            e.create_node(f"{P}d{i}", labels=[f"RV55D{TAG}"], properties={"txt": doc})
        name = f"rv55bm{TAG}"
        ids = [f"{P}d9", f"{P}d10", f"{P}da", f"{P}dB"]
        rec = {}
        rec["build"] = e.bm25_build(name, ["txt"])
        rec["search"] = e.bm25_search(name, "zeta", k=10)
        cur = c.cursor()
        for k_ in (0, -1, 2):
            try:
                cur.execute("SELECT Graph_KG.kg_BM25(?, ?, ?)", [name, "zeta", k_]); rec[f"kg_BM25_k{k_}"] = cur.fetchone()[0]
            except Exception as x:
                rec[f"kg_BM25_k{k_}"] = f"exc {x}"[:200]
        try:
            rec["search_k0"] = e.bm25_search(name, "zeta", k=0)
        except Exception as x:
            rec["search_k0"] = f"exc {type(x).__name__}"
        e.bm25_drop(name)
        out["bm25_ties"] = rec
        print("bm25", json.dumps(rec, default=str)[:900])
    except Exception as x:
        out["bm25_ties"] = f"exc {type(x).__name__}: {x}"[:300]
        print("bm25 exc", x)

    # MatchEdges neighbor: graph '0' vs default (reserved name not refused), unknown graph
    try:
        cur = c.cursor(); rec = {}
        for g in ["", "0", "nosuch"]:
            cur.execute("SELECT Graph_KG.MatchEdges(?, ?, 0, ?)", [f"{P}a1", K, g]); rec[f"g={g!r}"] = cur.fetchone()[0]
        out["matchedges_graph"] = rec; print("matchedges", rec)
    except Exception as x:
        out["matchedges_graph"] = f"exc {x}"[:300]

    # Bolt: bug-plt-123 (reversed endpoints), F-1602 (PULL n), explicit-transaction rollback
    try:
        import neo4j
        from iris_vector_graph import bolt_server as bs
        c2 = runtime.connect(); e2 = runtime.engine(c2)
        s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
        loop = asyncio.new_event_loop()
        th = threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True); th.start()
        srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
        time.sleep(0.5)
        brec = {}
        with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x")) as d:
            with d.session() as s:
                r = s.run(f"MATCH (a {{id: '{P}a1'}})-[r:{K}]->(b) RETURN a, r, b"); brec["a_r_b"] = [norm(list(x.values())) for x in r]
                r = s.run(f"MATCH (b {{id: '{P}a2'}})<-[r:{K}]-(a) RETURN b, r, a"); brec["b_r_a"] = [norm(list(x.values())) for x in r]
                r = s.run(f"MATCH (a {{id: '{P}a1'}})-[r:{K}]->(b) RETURN r"); brec["r_only"] = [norm(list(x.values())) for x in r]
            with d.session(fetch_size=2) as s:
                brec["fetch2"] = [x[0] for x in s.run("UNWIND [1,2,3,4,5] AS i RETURN i")]
            with d.session() as s:
                tx = s.begin_transaction()
                tx.run(f"CREATE (:{A} {{id: '{P}tx1', name: 'tx'}})").consume()
                tx.rollback()
            with d.session() as s:
                brec["after_rollback"] = [x[0] for x in s.run(f"MATCH (n:{A} {{id: '{P}tx1'}}) RETURN count(n)")]
            with d.session() as s:
                try:
                    s.run("RETURN 1 AS a UNION RETURN 2 AS b").consume(); brec["err_union"] = "no error"
                except Exception as x:
                    brec["err_union"] = f"{type(x).__name__}: {getattr(x, 'code', '')}"
        out["bolt"] = brec; print("bolt", json.dumps(brec, default=str)[:1500])
        srv.close(); loop.call_soon_threadsafe(loop.stop)
    except Exception as x:
        out["bolt"] = f"exc {type(x).__name__}: {x}"[:400]; print("bolt exc", repr(x))

    p = f"/tmp/review-53-55/probes/rv55-observed-{RUN}.json"
    json.dump(out, open(p, "w"), indent=1, default=str); print("wrote", p)


if __name__ == "__main__":
    main()
