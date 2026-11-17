"""W62 D1-D9 probe (iteration 58, worker W2): result decoders through the four final readers.
Fixture ivg-cont-20261117-iris (USER), fresh prefix i58d_<tag>_. No sync(). Readers: PY execute_cypher (SQL path,
native_cypher=False) plus PYN (native default engine) for D8; BOLT = neo4j driver against the product's TCP listener;
API /api/cypher and TX /db/neo4j/tx/commit through the FastAPI TestClient. Reader setup reused from
iteration-55/pipeline_probe.py. Writes decoders-observed-<RUN>.json next to this file."""
import asyncio, json, os, socket, sys, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-55"))
import runtime  # noqa: E402
from pipeline_probe import norm, err, _cut, _has  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i58d_{TAG}_"; L = f"I58DL{TAG}"; K = f"I58DK{TAG}"


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph import bolt_server as bs
    import importlib.metadata as md
    out = {"run": RUN, "tag": TAG, "prefix": P, "label": L, "fixture": runtime.NAME, "product": runtime.PRODUCT}
    out["drivers"] = {p: md.version(p) for p in ("intersystems-irispython", "neo4j") if _has(md, p)}
    c = runtime.connect(); e = runtime.engine(c)
    e.create_node(P + "i", labels=[L], properties={"k": "i", "v": 3, "s": "si", "e": "", "el": [], "em": {}})
    e.create_node(P + "f", labels=[L], properties={"k": "f", "v": 2.5, "s": "sf"})
    e.create_node(P + "s", labels=[L], properties={"k": "s", "s": "txt"})
    e.create_node(P + "b", labels=[L], properties={"k": "b", "s": True})
    e.create_node(P + "w", labels=[L + "W"], properties={"v": 3.0})
    for a, b in (("i", "f"), ("f", "s"), ("s", "b"), ("i", "s")):
        e.create_edge(P + a, K, P + b)
    ob = "ORDER BY n.node_id"
    Q = [
        ("D1_case", f"MATCH (n:{L}) WITH n, CASE WHEN n.k = 'i' OR n.k = 'f' THEN n.v ELSE n.s END AS x RETURN n.node_id AS id, x {ob}"),
        ("D1_case_noid", f"MATCH (n:{L}) WITH CASE WHEN n.k = 'i' OR n.k = 'f' THEN n.v ELSE n.s END AS x RETURN x ORDER BY toString(x)"),
        ("D1_coalesce", f"MATCH (n:{L}) WITH n, coalesce(n.v, n.s) AS x RETURN n.node_id AS id, x {ob}"),
        ("D1_ret_case", f"MATCH (n:{L}) RETURN n.node_id AS id, CASE WHEN n.k = 'i' OR n.k = 'f' THEN n.v ELSE n.s END AS x {ob}"),
        ("D2_opt", f"MATCH (a:{L} {{node_id: '{P}i'}}) OPTIONAL MATCH (a)-[:I58NONE]->(b) RETURN a.node_id AS id, b, b.x AS bx"),
        ("D2_with", f"MATCH (a:{L} {{node_id: '{P}i'}}) OPTIONAL MATCH (a)-[:I58NONE]->(b) WITH a, b RETURN a.node_id AS id, b, b.x AS bx"),
        ("D2_collect", f"MATCH (a:{L} {{node_id: '{P}i'}}) OPTIONAL MATCH (a)-[:I58NONE]->(b) RETURN a.node_id AS id, collect(b) AS bs"),
        ("D3_empty", f"MATCH (n:{L} {{node_id: '{P}i'}}) RETURN n.e AS e, n.el AS el, n.em AS em"),
        ("D3_empty_with", f"MATCH (n:{L} {{node_id: '{P}i'}}) WITH n.e AS e, n.el AS el RETURN e, el"),
        ("D4_map", f"MATCH (n:{L} {{node_id: '{P}i'}}) RETURN {{a: n.v, b: 'x'}} AS m"),
        ("D4_map_nested", f"MATCH (n:{L} {{node_id: '{P}i'}}) RETURN {{a: [1, n.v], t: true, s: n.s}} AS m"),
        ("D5_int", f"MATCH (n:{L} {{node_id: '{P}i'}}) RETURN n.v + 1 AS a, n.v * 1.5 AS b, n.v / 2 AS c"),
        ("D5_float", f"MATCH (n:{L}W) RETURN n.v + 1 AS a, n.v * 1.5 AS b, n.v / 2 AS c"),
        ("D6_bool", f"MATCH (n:{L}) WHERE n.k IN ['i', 'f', 's'] RETURN n.node_id AS id, n.v > 2.7 AS b {ob}"),
        ("D7_empty", f"MATCH (a:{L} {{node_id: 'nope'}})-[:{K}]->(b) RETURN a.node_id AS id, b.x AS bx"),
        ("D7_count", f"MATCH (a:{L} {{node_id: 'nope'}}) RETURN count(*) AS c"),
        ("D8_read", f"MATCH (n:{L}) RETURN n.node_id AS id, n.v AS v, n.s AS s {ob}"),
        ("D9_limit", f"MATCH (a {{node_id: '{P}i'}})-[:{K}*1..3]->(b) RETURN b.node_id AS id LIMIT 2"),
        ("D9_order_limit", f"MATCH (a {{node_id: '{P}i'}})-[:{K}*1..3]->(b) RETURN b.node_id AS id ORDER BY id LIMIT 2"),
        ("D9_all", f"MATCH (a {{node_id: '{P}i'}})-[:{K}*1..3]->(b) RETURN b.node_id AS id ORDER BY id"),
    ]
    from iris_vector_graph.cypher.parser import parse_query
    from iris_vector_graph.cypher.translator import translate_to_sql
    meta = {}
    for key, q in Q:
        try:
            sq = translate_to_sql(parse_query(q), {})
            meta[key] = {a: (list(getattr(sq, a)) if isinstance(getattr(sq, a, None), (list, set, tuple)) else repr(getattr(sq, a, None))[:300])
                         for a in ("typed_value_columns", "json_value_columns", "map_text_columns", "numeric_expr_columns",
                                   "mixed_expr_columns", "bool_text_columns", "bool_expr_columns", "prop_text_expr_columns",
                                   "var_length_paths", "column_name_map") if hasattr(sq, a)}
            meta[key]["sql"] = (sq.sql if isinstance(sq.sql, str) else repr(sq.sql))[:1500]
        except Exception as x:
            meta[key] = err(x)
    out["meta"] = meta

    def py(key, q, eng, label):
        try:
            r = eng.execute_cypher(q, {})
            v = {"columns": list(r.columns or []), "rows": [norm(list(x)) for x in r.rows]}
        except Exception as x:
            v = err(x)
        out.setdefault(key, {})[label] = v

    en = IRISGraphEngine(c, embedding_dimension=768)
    for key, q in Q:
        py(key, q, e, "PY")
    for key, q in Q:
        if key.startswith(("D8", "D1", "D5", "D9")):
            py(key, q, en, "PYN")
    # D8 shadow / compiled on the native engine
    os.environ["IVG_CYPHER_SHADOW"] = "1"
    es = IRISGraphEngine(c, embedding_dimension=768)
    for key, q in Q:
        if key.startswith(("D8", "D1_case", "D5")):
            py(key, q, es, "PYN_SHADOW")
    os.environ.pop("IVG_CYPHER_SHADOW", None)
    out["shadow_flag_read"] = repr(getattr(es, "_cypher_shadow", lambda: None)())

    import neo4j
    c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
    loop = asyncio.new_event_loop()
    th = threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True); th.start()
    s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
    srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
    os.environ.pop("IVG_API_KEY", None); os.environ.pop("IVG_READ_ONLY", None)
    for key, q in Q:
        try:
            with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x"), connection_timeout=10,
                                            max_transaction_retry_time=0) as d, d.session() as s:
                res = s.run(q, {}); rows = [norm(list(r.values())) for r in res]; res.consume()
                v = {"columns": list(res.keys()), "rows": rows}
        except Exception as x:
            v = err(x)
        out.setdefault(key, {})["BOLT"] = v
    loop.call_soon_threadsafe(srv.close); time.sleep(0.5); loop.call_soon_threadsafe(loop.stop)
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    with TestClient(cypher_api.app) as client:
        for key, q in Q:
            try:
                a = client.post("/api/cypher", json={"query": q, "parameters": {}})
                out[key]["API"] = {"status": a.status_code, "body": _cut(a.json())}
            except Exception as x:
                out[key]["API"] = err(x)
            try:
                t = client.post("/db/neo4j/tx/commit", json={"statements": [{"statement": q, "parameters": {}}]})
                out[key]["TX"] = {"status": t.status_code, "body": _cut(t.json())}
            except Exception as x:
                out[key]["TX"] = err(x)
    c2.close(); c.close()
    out["queries"] = dict(Q)
    name = f"decoders-observed-{out['drivers'].get('intersystems-irispython')}-{RUN}.json"
    (HERE / name).write_text(json.dumps(out, indent=1, sort_keys=True, default=repr, ensure_ascii=False) + "\n")
    print(name)


if __name__ == "__main__":
    main()
