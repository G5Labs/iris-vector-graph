"""W60 post-read probe (T1-T7 of pipeline-PAIRS.md): Bolt whole-node property truncation, relationship endpoints by
column order, node-id collisions, parameter vs literal equality, int64 overflow, var-length LIMIT, long-list grouping.
Same fixture and readers as pipeline_probe.py (whose helpers it imports); fresh prefix."""
import asyncio, json, os, socket, sys, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline_probe as pp  # noqa: E402
runtime = pp.runtime

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i55b_{TAG}_"; L = f"I55B{TAG}"; K = f"I55BK{TAG}"


def collide(prefix, tries=400000):
    seen = {}
    for i in range(tries):
        s = f"{prefix}h{i}"
        h = hash(s) & 0x7FFFFFFF
        if h in seen:
            return seen[h], s, h
        seen[h] = s
    return None


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph import bolt_server as bs
    import neo4j
    out = {"run": RUN, "tag": TAG, "fixture": runtime.NAME, "product": runtime.PRODUCT}
    import importlib.metadata as md
    out["drivers"] = {p: md.version(p) for p in ("intersystems-irispython", "neo4j")}
    c = runtime.connect(); e = runtime.engine(c)
    A, B, C = P + "a", P + "b", P + "c"
    e.create_node(A, labels=[L], properties={"s200": "y" * 200, "s201": "y" * 201, "s300": "x" * 300, "lst": list(range(100)), "v": 1})
    e.create_node(B, labels=[L], properties={"v": "1"})
    e.create_node(C, labels=[L], properties={"v": 2})
    e.create_edge(A, K, B, qualifiers={"w": 3})
    e.create_edge(B, K, C)
    col = collide(P)
    out["collision"] = list(col) if col else None
    if col:
        e.create_node(col[0], labels=[L + "H"], properties={"n": 1})
        e.create_node(col[1], labels=[L + "H"], properties={"n": 2})

    c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True).start()
    s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
    srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
    os.environ.pop("IVG_API_KEY", None); os.environ.pop("IVG_READ_ONLY", None)

    def both(key, q, params=None, graph=False):
        rec = {}
        try:
            r = e.execute_cypher(q, params or {})
            rec["PY"] = {"columns": list(r.columns or []), "rows": [pp.norm(list(x)) for x in r.rows]}
            if getattr(r, "error", None):
                rec["PY"]["error_field"] = str(r.error)[:300]
        except Exception as x:
            rec["PY"] = pp.err(x)
        try:
            with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x"), connection_timeout=10) as d, d.session() as s:
                res = s.run(q, params or {})
                recs = list(res)
                rec["BOLT"] = {"columns": list(res.keys()), "rows": [pp.norm(list(r.values())) for r in recs]}
                if graph:
                    g = res.graph()
                    rec["BOLT"]["graph_nodes"] = len(g.nodes); rec["BOLT"]["graph_rels"] = len(g.relationships)
        except Exception as x:
            rec["BOLT"] = pp.err(x)
        out[key] = rec
        return rec

    both("T1_node", f"MATCH (n:{L} {{node_id: '{A}'}}) RETURN n")
    both("T1_scalar", f"MATCH (n:{L} {{node_id: '{A}'}}) RETURN n.s200 AS a, n.s201 AS b, n.s300 AS c, n.lst AS d")
    both("T2_abr", f"MATCH (a:{L} {{node_id: '{A}'}})-[r:{K}]->(b) RETURN a, r, b")
    both("T2_bra", f"MATCH (a:{L} {{node_id: '{A}'}})-[r:{K}]->(b) RETURN b, r, a")
    both("T2_rev", f"MATCH (b:{L} {{node_id: '{B}'}})<-[r:{K}]-(a) RETURN b, r, a")
    both("T2_r", f"MATCH (a:{L} {{node_id: '{A}'}})-[r:{K}]->(b) RETURN r")
    both("T2_abr_last", f"MATCH (a:{L} {{node_id: '{A}'}})-[r:{K}]->(b) RETURN a, b, r")
    if col:
        both("T3_collide", f"MATCH (n:{L}H) RETURN n ORDER BY n.n", graph=True)
    both("T3_distinct", f"MATCH (n:{L}) WHERE n.node_id IN ['{A}', '{C}'] RETURN n ORDER BY n.node_id", graph=True)
    both("T4_param_int_vs_string", f"MATCH (n:{L}) WHERE n.v = $x RETURN n.node_id AS id ORDER BY id", {"x": 1})
    both("T4_literal_int", f"MATCH (n:{L}) WHERE n.v = 1 RETURN n.node_id AS id ORDER BY id")
    both("T4_literal_str", f"MATCH (n:{L}) WHERE n.v = '1' RETURN n.node_id AS id ORDER BY id")
    both("T4_param_str", f"MATCH (n:{L}) WHERE n.v = $x RETURN n.node_id AS id ORDER BY id", {"x": "1"})
    both("T4_param_int2", f"MATCH (n:{L}) WHERE n.v = $x RETURN n.node_id AS id ORDER BY id", {"x": 2})
    both("T4_param_float", f"MATCH (n:{L}) WHERE n.v = $x RETURN n.node_id AS id ORDER BY id", {"x": 2.0})
    both("T5_overflow", "RETURN 9223372036854775807 + 1 AS x")
    both("T5_max", "RETURN 9223372036854775807 AS x")
    both("T5_big_literal", "RETURN 9223372036854775808 AS x")
    both("T6_order_limit", f"MATCH (a:{L} {{node_id: '{A}'}})-[:{K}*1..2]->(b) RETURN b.node_id AS id ORDER BY id LIMIT 1")
    both("T6_limit", f"MATCH (a:{L} {{node_id: '{A}'}})-[:{K}*1..2]->(b) RETURN b.node_id AS id LIMIT 1")
    both("T6_none", f"MATCH (a:{L} {{node_id: '{A}'}})-[:{K}*1..2]->(b) RETURN b.node_id AS id")
    both("T6_inner_limit", f"MATCH (a:{L} {{node_id: '{A}'}}) WITH a LIMIT 1 MATCH (a)-[:{K}*1..2]->(b) RETURN b.node_id AS id")
    both("T6_path_order_limit", f"MATCH p = (a:{L} {{node_id: '{A}'}})-[:{K}*1..2]->(b) RETURN b.node_id AS id ORDER BY id DESC LIMIT 1")
    longl = ", ".join(f"'{'z' * 40}{i}'" for i in range(20))
    both("T7_long", f"UNWIND [{longl}] AS x RETURN x, count(*) AS c ORDER BY x LIMIT 2")
    both("T7_short", "UNWIND ['a', 'b', 'a'] AS x RETURN x, count(*) AS c ORDER BY x")
    # T5 raw: what the server writes when a value does not fit
    try:
        out["T5_raw"] = pp.runq(port, "RETURN 9223372036854775807 + 1 AS x")
    except Exception as x:
        out["T5_raw"] = pp.err(x)
    srv.close(); loop.call_soon_threadsafe(loop.stop)
    c2.close(); c.close()
    name = f"pipeline-observed2-{RUN}.json"
    (HERE / name).write_text(json.dumps(out, indent=1, sort_keys=True, default=repr, ensure_ascii=False) + "\n")
    print(name)


if __name__ == "__main__":
    main()
