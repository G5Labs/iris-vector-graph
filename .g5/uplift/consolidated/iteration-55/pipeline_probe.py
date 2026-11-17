"""W60 raw probe: one stored answer through every final reader. Fixture ivg-cont-20261117-iris (USER), fresh prefix.
Readers: PY execute_cypher (SQL path) and a native-default engine; BOLT the real neo4j driver against the product's
own TCP listener (start_tcp_bolt_server, real engine on its own connection, run in a thread); a raw Bolt socket client
for handshake bytes, PULL metadata and PackStream widths; API /api/cypher and TX /db/neo4j/tx/commit through the
FastAPI TestClient. I55_MODE=params runs only the parameter shapes on PY (used for the driver-version contrast).
Rows of iteration-55/pipeline-PAIRS.md are keyed by their IDs."""
import asyncio, json, os, socket, struct, sys, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i55_{TAG}_"; L = f"I55L{TAG}"; K = f"I55K{TAG}"
MODE = os.environ.get("I55_MODE", "all")


def norm(v):
    """Client-visible value with its Python type kept visible."""
    try:
        import neo4j.graph as g
        if isinstance(v, g.Node):
            return {"__node__": v.element_id, "id": getattr(v, "id", None), "labels": sorted(v.labels), "props": norm(dict(v))}
        if isinstance(v, g.Relationship):
            return {"__rel__": v.element_id, "type": v.type, "start": v.start_node.element_id if v.start_node else None,
                    "end": v.end_node.element_id if v.end_node else None, "props": norm(dict(v))}
        if isinstance(v, g.Path):
            return {"__path__": [norm(n) for n in v.nodes], "rels": [norm(r) for r in v.relationships]}
    except ImportError:
        pass
    if isinstance(v, bool):
        return {"bool": v}
    if isinstance(v, int):
        return {"int": str(v)}
    if isinstance(v, float):
        return {"float": repr(v)}
    if isinstance(v, str):
        return {"str": v}
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in v.items()}
    return {"other": f"{type(v).__name__}:{v!r}"[:200]}


def err(x):
    return {"error": type(x).__name__, "code": getattr(x, "code", None), "msg": str(x)[:300]}


# ---------------- raw Bolt client (independent of the product's codec)
def rpack(v):
    if v is None:
        return b"\xc0"
    if v is True:
        return b"\xc3"
    if v is False:
        return b"\xc2"
    if isinstance(v, int):
        if -16 <= v < 128:
            return struct.pack(">b", v)
        if -128 <= v < 128:
            return b"\xc8" + struct.pack(">b", v)
        if -32768 <= v < 32768:
            return b"\xc9" + struct.pack(">h", v)
        if -2**31 <= v < 2**31:
            return b"\xca" + struct.pack(">i", v)
        return b"\xcb" + struct.pack(">q", v)
    if isinstance(v, str):
        b = v.encode()
        n = len(b)
        h = bytes([0x80 | n]) if n < 16 else (b"\xd0" + bytes([n]) if n < 256 else b"\xd1" + struct.pack(">H", n))
        return h + b
    if isinstance(v, list):
        return bytes([0x90 | len(v)]) + b"".join(rpack(x) for x in v)
    if isinstance(v, dict):
        return bytes([0xA0 | len(v)]) + b"".join(rpack(k) + rpack(x) for k, x in v.items())
    raise TypeError(v)


def rmsg(tag, *fields):
    body = bytes([0xB0 | len(fields), tag]) + b"".join(rpack(f) for f in fields)
    return struct.pack(">H", len(body)) + body + b"\x00\x00"


class Raw:
    def __init__(self, port, versions):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
        vs = b"".join(struct.pack(">I", v) for v in (versions + [0, 0, 0, 0])[:4])
        self.s.sendall(b"\x60\x60\xb0\x17" + vs)
        self.agreed = self._read(4)

    def _read(self, n):
        out = b""
        while len(out) < n:
            try:
                b = self.s.recv(n - len(out))
            except socket.timeout:
                return out + b"<timeout>"
            if not b:
                return out + b"<eof>"
            out += b
        return out

    def recv(self):
        body = b""
        while True:
            h = self._read(2)
            if len(h) < 2 or h.endswith(b">"):
                return {"eof": h.hex()}
            n = struct.unpack(">H", h)[0]
            if n == 0:
                break
            body += self._read(n)
        return body

    def send(self, tag, *fields):
        self.s.sendall(rmsg(tag, *fields))
        return self.recv()


def runq(port, query, params=None, n=-1, versions=None):
    r = Raw(port, versions or [0x0404])
    out = {"agreed": r.agreed.hex()}
    out["hello"] = r.send(0x01, {"user_agent": "i55-raw/1", "scheme": "none"}).hex()[:60]
    out["run"] = r.send(0x10, query, params or {}, {}).hex()[:200]
    pulls = []
    for _ in range(4):
        r.s.sendall(rmsg(0x3F, {"n": n}))
        msgs = []
        while True:
            m = r.recv()
            if isinstance(m, dict):
                msgs.append(m); break
            msgs.append(m.hex())
            if m[1:2] in (b"\x70", b"\x7f", b"\x7e"):
                break
        pulls.append(msgs)
        if msgs and isinstance(msgs[-1], str) and msgs[-1][2:4] == "70" and "6861735f6d6f7265" not in msgs[-1]:
            break
    out["pulls"] = pulls
    r.s.close()
    return out


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph import bolt_server as bs
    out = {"run": RUN, "tag": TAG, "fixture": runtime.NAME, "product": runtime.PRODUCT, "mode": MODE}
    import importlib.metadata as md
    out["drivers"] = {p: md.version(p) for p in ("intersystems-irispython", "neo4j") if _has(md, p)}
    c = runtime.connect(); e = runtime.engine(c)

    def py(key, q, params=None, eng=None):
        try:
            r = (eng or e).execute_cypher(q, params or {})
            v = {"columns": list(r.columns or []), "rows": [norm(list(x)) for x in r.rows]}
            if getattr(r, "error", None):
                v["error_field"] = str(r.error)[:300]
        except Exception as x:
            v = err(x)
        out.setdefault(key, {})["PY" if eng is None else "PYN"] = v
        return v

    # ---------------- parameter shapes (the only part run under I55_MODE=params)
    e.create_node(P + "p1", labels=[L + "P"], properties={"v": 1, "w": 5})
    e.create_node(P + "p2", labels=[L + "P"], properties={"v": 2, "w": 1})
    PARAMS = [
        ("PA1_int", "RETURN $x AS x", {"x": 7}), ("PA1_float", "RETURN $x AS x", {"x": 2.5}),
        ("PA1_str", "RETURN $x AS x", {"x": "1"}), ("PA1_bool", "RETURN $x AS x", {"x": True}),
        ("PA1_null", "RETURN $x AS x", {"x": None}), ("PA1_list", "RETURN $x AS x", {"x": [1, "a", [2]]}),
        ("PA1_map", "RETURN $x AS x", {"x": {"k": 1, "l": [1]}}),
        ("PA2_int", f"MATCH (n:{L}P) WHERE n.v = $x RETURN n.node_id AS id", {"x": 1}),
        ("PA2_str", f"MATCH (n:{L}P) WHERE n.v = $x RETURN n.node_id AS id", {"x": "1"}),
        ("PA3_unwind_param", "UNWIND $xs AS a RETURN a", {"xs": [1, 2]}),
        ("PA3_with_param", "WITH $xs AS l UNWIND l AS a RETURN a", {"xs": [1, 2]}),
        ("PA3_match_unwind", f"MATCH (n:{L}P) WHERE n.v = 1 UNWIND $xs AS a RETURN a", {"xs": [1, 2]}),
        ("PA4_slice", "RETURN $l[$s..$e] AS x", {"l": [1, 2, 3, 4], "s": 1, "e": 3}),
        ("PA4_index", "RETURN $l[$s] AS x", {"l": [1, 2, 3, 4], "s": 1}),
        ("PA4_with_slice", "WITH $l AS l RETURN l[$s..$e] AS x", {"l": [1, 2, 3, 4], "s": 1, "e": 3}),
        ("PA5_in_param", f"MATCH (n:{L}P) WHERE n.v IN $xs RETURN n.node_id AS id ORDER BY id", {"xs": [1, 2]}),
        ("PA5_in_lit", f"MATCH (n:{L}P) WHERE n.v IN [1, 2] RETURN n.node_id AS id ORDER BY id", {}),
        ("PA6_map_key", "RETURN $m.k AS x", {"m": {"k": 1}}),
        ("PA6_missing", "RETURN $nope AS x", {}),
        ("PA7_reuse", f"MATCH (n:{L}P) WHERE n.v = $x OR n.w = $x RETURN n.node_id AS id ORDER BY id", {"x": 1}),
        ("PA7_two", f"MATCH (n:{L}P) WHERE n.v = $x OR n.w = $y RETURN n.node_id AS id ORDER BY id", {"x": 1, "y": 1}),
        ("PA8_skip_limit", "UNWIND [1,2,3,4,5] AS i RETURN i SKIP $s LIMIT $l", {"s": 1, "l": 2}),
        ("ER3_unwind_create_small", f"UNWIND $rows AS r CREATE (:{L}W3 {{i: r}})", {"rows": list(range(3))}),
        ("ER3_with_create_small", f"WITH $rows AS rs UNWIND rs AS r CREATE (:{L}V3 {{i: r}})", {"rows": list(range(3))}),
    ]
    for key, q, params in PARAMS:
        py(key, q, params)
    for lab in ("W3", "V3"):
        py(f"ER3_count_{lab}", f"MATCH (n:{L}{lab}) RETURN count(n) AS c")
    if MODE == "params":
        finish(out, c); return

    # ---------------- stored values
    vals = {"vi": 1, "vs": "1", "vf": 2.5, "vw": 1.0, "vb": True, "vbs": "true", "vl": [1, 2], "vm": {"k": 1},
            "ve": "", "vbig": 2**62, "vhuge": 2**64}
    e.create_node(P + "a", labels=[L], properties={"name": "a", **vals})
    e.create_node(P + "b", labels=[L], properties={"name": "b", "vi": 2})
    e.create_node(P + "c", labels=[L], properties={"name": "c"})
    e.create_edge(P + "a", K, P + "b", qualifiers={"q": 1, "t": "x"})
    e.create_edge(P + "b", K, P + "c")
    READS = [("RT_" + k, f"MATCH (n:{L} {{node_id: '{P}a'}}) RETURN n.{k} AS x", {}) for k in vals]
    READS += [
        ("RT5_missing", f"MATCH (n:{L} {{node_id: '{P}c'}}) RETURN n.vi AS x", {}),
        ("RT6_literals", "RETURN [] AS a, {} AS b, [[1,[2]],{a:[]}] AS c", {}),
        ("RT8_node", f"MATCH (n:{L} {{node_id: '{P}a'}}) RETURN n", {}),
        ("RT8_props", f"MATCH (n:{L} {{node_id: '{P}b'}}) RETURN properties(n) AS p", {}),
        ("RT9_same_twice", f"MATCH (n:{L} {{node_id: '{P}b'}}) UNWIND [1, 2] AS i RETURN n, i", {}),
        ("RT9_two_nodes", f"MATCH (n:{L}) WHERE n.node_id IN ['{P}b', '{P}c'] RETURN n ORDER BY n.node_id", {}),
        ("RT10_rel", f"MATCH (a:{L} {{node_id: '{P}a'}})-[r:{K}]->(b) RETURN a, r, b", {}),
        ("RT10_type", f"MATCH (a:{L} {{node_id: '{P}a'}})-[r:{K}]->(b) RETURN type(r) AS t, r.q AS q, r.t AS tt", {}),
        ("RT11_path", f"MATCH p = shortestPath((a {{node_id: '{P}a'}})-[:{K}*]->(b {{node_id: '{P}c'}})) RETURN p", {}),
        ("RT11_len", f"MATCH p = shortestPath((a {{node_id: '{P}a'}})-[:{K}*]->(b {{node_id: '{P}c'}})) RETURN length(p) AS n", {}),
        ("RT11_varlen", f"MATCH p = (a {{node_id: '{P}a'}})-[:{K}*1..2]->(b) RETURN p", {}),
        ("BP6_ints", "RETURN 127 AS a, 128 AS b, -16 AS c, -17 AS d, 32767 AS e, 32768 AS f, 2147483648 AS g, "
                     "9223372036854775807 AS h, -9223372036854775807 AS i", {}),
        ("BP6_minint", "RETURN -9223372036854775808 AS x", {}),
        ("BP7_unicode", "RETURN 'héllo ✓ 𝄞' AS a, 'héllo ✓ 𝄞 more' AS b, '' AS c", {}),
        ("BP8_floats", "RETURN 2.5 AS a, -0.0 AS b, 1e308 AS c, 2 AS d", {}),
        ("ER1_syntax", "MATCH (n RETURN n", {}),
        ("ER2_union_count", f"MATCH (n:{L}) RETURN count(n) AS x UNION MATCH (n:{L}) RETURN n.vi AS x", {}),
        ("ER2_union_ok", f"MATCH (n:{L}) RETURN n.vi AS x UNION MATCH (n:{L}) RETURN n.vi AS x", {}),
        ("ER4_1200", "UNWIND range(1, 1200) AS i RETURN i", {}),
        ("ER4_limit", "UNWIND range(1, 1200) AS i RETURN i LIMIT 5", {}),
        ("NR1_values", f"MATCH (n:{L}) RETURN n.node_id AS id, n.vi AS vi, n.vf AS vf, n.vs AS vs, n.vb AS vb, n.vl AS vl ORDER BY id", {}),
        ("NR1_count", f"MATCH (n:{L}) RETURN count(n) AS c", {}),
    ]
    en = IRISGraphEngine(c, embedding_dimension=768)  # native default
    for key, q, params in READS:
        py(key, q, params)
        if key.startswith(("NR", "RT_")):
            py(key, q, params, eng=en)

    # ---------------- Bolt: the product's own TCP listener with a real engine on its own connection
    import neo4j
    c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
    loop = asyncio.new_event_loop()
    th = threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True); th.start()
    s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
    srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
    out["bolt_port"] = port
    os.environ.pop("IVG_API_KEY", None); os.environ.pop("IVG_READ_ONLY", None)

    def bolt(key, q, params=None, label="BOLT", **kw):
        try:
            with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=kw.pop("auth", ("neo4j", "x")),
                                            connection_timeout=10, max_transaction_retry_time=0) as d:
                with d.session(**kw) as s:
                    res = s.run(q, params or {})
                    rows = [norm(list(r.values())) for r in res]
                    summ = res.consume()
                    v = {"columns": list(res.keys()), "rows": rows, "server": str(summ.server.protocol_version)}
        except Exception as x:
            v = err(x)
        out.setdefault(key, {})[label] = v
        return v

    for key, q, params in PARAMS + READS:
        if key.startswith("ER3"):
            continue
        bolt(key, q, params)
    bolt("BP5_fetch2", "UNWIND [1,2,3,4,5] AS i RETURN i", label="BOLT_fetch2", fetch_size=2)
    bolt("BP5_fetchall", "UNWIND [1,2,3,4,5] AS i RETURN i", label="BOLT_fetchall", fetch_size=-1)
    # BP4: failure then a new query in one session
    try:
        with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x")) as d, d.session() as s:
            first = None
            try:
                list(s.run("MATCH (n RETURN n"))
            except Exception as x:
                first = err(x)
            second = [norm(list(r.values())) for r in s.run("RETURN 1 AS x")]
            out["BP4_reset"] = {"first": first, "second": second}
    except Exception as x:
        out["BP4_reset"] = err(x)
    # BP3: API key
    os.environ["IVG_API_KEY"] = "k55-secret"
    bolt("BP3_right_key", "RETURN 1 AS x", label="BOLT_right", auth=("neo4j", "k55-secret"))
    bolt("BP3_wrong_key", "RETURN 1 AS x", label="BOLT_wrong", auth=("neo4j", "nope"))
    bolt("BP3_no_auth", "RETURN 1 AS x", label="BOLT_noauth", auth=None)
    os.environ.pop("IVG_API_KEY", None)
    bolt("BP3_unset_any", "RETURN 1 AS x", label="BOLT_unset", auth=("u", "anything"))
    # raw handshakes and raw PULL metadata
    for key, vers in [("BP1_44", [0x0404]), ("BP1_30", [0x0003]), ("BP1_99", [0x0909]), ("BP2_50", [0x0005]),
                      ("BP2_54", [0x0405]), ("BP2_58", [0x0805]), ("BP2_range", [0x020805]), ("BP2_manifest", [0x01FF, 0x0404])]:
        try:
            r = Raw(port, vers); a = r.agreed; extra = r._read(1) if a == b"\x00\x00\x00\x00" else b""
            out[key] = {"offered": [hex(v) for v in vers], "agreed": a.hex(), "after": extra.hex() if isinstance(extra, bytes) else extra}
            r.s.close()
        except Exception as x:
            out[key] = err(x)
    for key, q, n in [("BP5_raw_pull2", "UNWIND [1,2,3,4,5] AS i RETURN i", 2), ("BP5_raw_pullall", "UNWIND [1,2,3,4,5] AS i RETURN i", -1),
                      ("BP6_raw_ints", "RETURN 127 AS a, 128 AS b, -16 AS c, -17 AS d, 32767 AS e, 32768 AS f, 2147483648 AS g", -1),
                      ("BP7_raw_str", "RETURN 'héllo ✓ 𝄞' AS a, 'héllo ✓ 𝄞 more' AS b", -1)]:
        try:
            out[key] = runq(port, q, n=n)
        except Exception as x:
            out[key] = err(x)
    for key, vers in [("BP2_raw_50_run", [0x0005])]:
        try:
            out[key] = runq(port, "RETURN 1 AS x", versions=vers)
        except Exception as x:
            out[key] = err(x)
    srv.close(); loop.call_soon_threadsafe(loop.stop)

    # ---------------- HTTP: /api/cypher and /db/neo4j/tx/commit in-process
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    with TestClient(cypher_api.app) as client:
        for key, q, params in PARAMS[:9] + READS:
            try:
                a = client.post("/api/cypher", json={"query": q, "parameters": params})
                out.setdefault(key, {})["API"] = {"status": a.status_code, "body": _cut(a.json())}
            except Exception as x:
                out.setdefault(key, {})["API"] = err(x)
            try:
                t = client.post("/db/neo4j/tx/commit", json={"statements": [{"statement": q, "parameters": params}]})
                out.setdefault(key, {})["TX"] = {"status": t.status_code, "body": _cut(t.json())}
            except Exception as x:
                out.setdefault(key, {})["TX"] = err(x)
    c2.close()
    finish(out, c)


def _has(md, p):
    try:
        md.version(p); return True
    except Exception:
        return False


def _cut(b):
    s = json.dumps(b, default=repr)
    if len(s) > 6000:
        if isinstance(b, dict) and "rows" in b:
            return {**{k: v for k, v in b.items() if k != "rows"}, "rows_len": len(b["rows"]), "rows_head": b["rows"][:3]}
        if isinstance(b, dict) and "results" in b:
            r = b["results"][0] if b["results"] else {}
            return {"errors": b.get("errors"), "columns": r.get("columns"), "data_len": len(r.get("data", [])), "data_head": r.get("data", [])[:3]}
    return b


def finish(out, c):
    c.close()
    name = f"pipeline-{'params-' if MODE == 'params' else ''}observed-{RUN}.json"
    if MODE == "params":
        name = f"pipeline-params-{out['drivers'].get('intersystems-irispython')}-observed-{RUN}.json"
    (HERE / name).write_text(json.dumps(out, indent=1, sort_keys=True, default=repr, ensure_ascii=False) + "\n")
    print(name)


if __name__ == "__main__":
    main()
