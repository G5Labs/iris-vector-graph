"""bolt_answers binding (iteration 55, W60): the product's real functions and its real Bolt listener against a port of
bolt_answers.rs. Unit part (pin tree, in-process): negotiate_version over a grid of offers; PackStream._pack_int at the
width boundaries and past int64; _node_int_id; _recompose_graph_row on node/relationship column layouts;
_parse_props_field over values of 199-300 characters; _is_long_list_temp_error over the 64 feature combinations.
Fixture part (ivg-cont-20261117-iris, USER, fresh prefix): raw handshakes and the neo4j driver against
start_tcp_bolt_server with a real engine (versions, integers, FAILURE codes incl. IVG_READ_ONLY and IVG_API_KEY, node
ids and a found hash collision, relationship endpoints, whole-node properties), node filter equality on the SQL path,
and the parameter-list shapes under intersystems-irispython 5.3.2 (this venv) and 5.4.1 (I55_VENV541, a subprocess).
Each port mutation mirrors a control of model.json and must be detected; one tampered observation must be detected."""
import asyncio, json, os, socket, struct, subprocess, sys, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/Verus_verification/tools")); sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import binding_common as bc  # noqa: E402
PIN = bc.import_pin()
import runtime  # noqa: E402

M64 = 2**63
MUTS = ["range-unchecked", "no-bolt5", "tiny-to-255", "i16-not-smallest", "nofit-is-failure", "code-by-cause", "gates-folded",
        "id-from-node-id", "driver-no-id-cache", "swap-columns", "no-prev-node", "no-truncation", "truncate-at-200",
        "retry-any-400", "retry-writes", "slice-markers-in-order", "driver-532-binds", "string-compare-typed", "int-param-raw"]


# ------------------------------------------------------------------ port of bolt_answers.rs (m = active mutation)
def one(raw, m):
    if raw == 0: return None
    maj, mi, rg = raw % 256, (raw // 256) % 256, (raw // 65536) % 256
    m4 = min(mi, 4)
    if maj == 5 and (m == "range-unchecked" or m4 > mi - rg - 1):
        return None if m == "no-bolt5" else m4 * 256 + 5
    if maj == 4 and mi >= 4: return 0x0404
    return None
def negotiate(offs, m):
    for o in offs:
        v = one(o, m)
        if v is not None: return v
    return 0
def int_marker(v, m):
    if -16 <= v <= (255 if m == "tiny-to-255" else 127): return "tiny"
    if -128 <= v <= 127: return "i8"
    if -32768 <= v <= 32767: return "i32" if m == "i16-not-smallest" else "i16"
    if -2**31 <= v <= 2**31 - 1: return "i32"
    if -M64 <= v <= M64 - 1: return "i64"
    return "nofit"
def pull_value(v, m): return ("Failure" if m == "nofit-is-failure" else "Broken") if int_marker(v, m) == "nofit" else "Records"
def bolt_code(cause, m):
    if cause == "ReadOnlyWrite": return "Neo.ClientError.Statement.SyntaxError" if m == "gates-folded" else "Neo.ClientError.Statement.AccessMode"
    if cause == "BadKey": return "Neo.ClientError.Security.Unauthorized"
    if m == "code-by-cause":
        return {"Parse": "Neo.ClientError.Statement.SyntaxError", "Undefined": "Neo.ClientError.Statement.ParameterMissing"}.get(cause, "Neo.DatabaseError.General.UnknownError")
    return "Neo.ClientError.Statement.SyntaxError"
def bolt_id(key, h, m): return key if m == "id-from-node-id" else h % 0x80000000
def client_view2(a, b, m):  # a, b = (bolt id, props)
    if m != "driver-no-id-cache" and a[0] == b[0]: return [b[1], b[1]]
    return [a[1], b[1]]
def reported(cols, i, m):  # cols: list of ("N", id) | ("R",) | ("S",)
    def prev(j):
        if j <= 0: return 0
        c = cols[j - 1]
        if c[0] == "N": return 0 if m == "no-prev-node" else c[1]
        return prev(j - 1)
    nxt = cols[i + 1][1] if i + 1 < len(cols) and cols[i + 1][0] == "N" else 0
    p = prev(i)
    return [nxt, p] if m == "swap-columns" else [p, nxt]
def bolt_node_prop(kind, rendered, m):
    cut = rendered >= 200 if m == "truncate-at-200" else rendered > 200
    if m != "no-truncation" and cut: return {"kind": "str", "whole": False}
    return {"kind": kind, "whole": True}
def is_long(f, m):
    if m == "retry-any-400": return f["c400"]
    return f["c400"] and f["subscript"] and (f["temp"] or (f["sqlcq"] and f["encoded"] and f["over"]))
def runs(f, st, m):
    if m == "retry-writes":
        return 2 if (f is not None and is_long(f, m) and st["used"] and not st["varlen"]) else 1
    if st["transactional"]: return 1
    return 2 if (f is not None and is_long(f, m) and st["used"] and not st["transactional"] and not st["varlen"]) else 1
def binds(drv, m): return True if m == "driver-532-binds" else drv.startswith("5.4")
def unwind_param(drv, xs, m): return xs if binds(drv, m) else "Fail"
def slice_answer(drv, l, s, e, m):
    if not binds(drv, m): return "Fail"
    order = ["S", "E", "L", "S", "E"] if m == "slice-markers-in-order" else ["L", "S", "E", "S", "E"]
    return l[s:e] if order[2] == "L" else []
def matches(st, op, m):  # st: ("Num", n, t) | ("Str", t); op: (kind, v)
    k, v = op
    text = st[2] if st[0] == "Num" else st[1]
    if k == "IntLit": return st[0] == "Num" and st[1] == v
    if k == "IntParam": return (text == str(v)) if m == "int-param-raw" else (st[0] == "Num" and st[1] == v)
    if k == "StrLit" and m == "string-compare-typed": return st[0] == "Str" and st[1] == v
    return text == v


# ------------------------------------------------------------------ independent raw Bolt client
def rpack(v):
    if v is None: return b"\xc0"
    if isinstance(v, bool): return b"\xc3" if v else b"\xc2"
    if isinstance(v, int):
        if -16 <= v < 128: return struct.pack(">b", v)
        if -128 <= v < 128: return b"\xc8" + struct.pack(">b", v)
        if -32768 <= v < 32768: return b"\xc9" + struct.pack(">h", v)
        if -2**31 <= v < 2**31: return b"\xca" + struct.pack(">i", v)
        return b"\xcb" + struct.pack(">q", v)
    if isinstance(v, str):
        b = v.encode(); n = len(b)
        return (bytes([0x80 | n]) if n < 16 else (b"\xd0" + bytes([n]) if n < 256 else b"\xd1" + struct.pack(">H", n))) + b
    if isinstance(v, dict): return bytes([0xA0 | len(v)]) + b"".join(rpack(k) + rpack(x) for k, x in v.items())
    raise TypeError(v)
def handshake(port, offers):
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    s.sendall(b"\x60\x60\xb0\x17" + b"".join(struct.pack(">I", o) for o in (offers + [0, 0, 0, 0])[:4]))
    got = b""
    while len(got) < 4:
        b = s.recv(4 - len(got))
        if not b: break
        got += b
    s.close()
    return struct.unpack(">I", got)[0] if len(got) == 4 else None
def marker_of(b):
    x = b[0]
    if x < 0x80 or x >= 0xF0: return "tiny"
    return {0xC8: "i8", 0xC9: "i16", 0xCA: "i32", 0xCB: "i64"}.get(x, hex(x))
def rint(b, o):
    x = b[o]
    if x < 0x80: return x, o + 1
    if x >= 0xF0: return x - 256, o + 1
    n = {0xC8: 1, 0xC9: 2, 0xCA: 4, 0xCB: 8}[x]
    return int.from_bytes(b[o + 1:o + 1 + n], "big", signed=True), o + 1 + n


def main():
    from iris_vector_graph import bolt_server as bs
    from iris_vector_graph._engine.query import _is_long_list_temp_error
    t0 = time.time(); cases = []

    def case(name, section, observed, predict, **extra):
        cases.append({"name": name, "section": section, "observed": observed, "predict": predict, **extra})

    # ---------------- unit: A
    for maj in (3, 4, 5, 0xFF):
        for mi in range(0, 10):
            for rg in range(0, 6):
                raw = rg * 65536 + mi * 256 + maj
                got = bs.negotiate_version(struct.pack(">IIII", raw, 0, 0, 0))
                case(f"A_unit_{maj}_{mi}_{rg}", "A", got, lambda m, raw=raw: negotiate([raw, 0, 0, 0], m))
    for offs in ([0x01FF, 0x0404, 0, 0], [0x0003, 0x0909, 0x0005, 0], [0x0805, 0x040805, 0, 0], [0x0204, 0x0104, 0, 0]):
        got = bs.negotiate_version(struct.pack(">IIII", *offs))
        case(f"A_unit_seq_{'_'.join(hex(o) for o in offs)}", "A", got, lambda m, offs=offs: negotiate(offs, m))
    # B
    for v in [0, 15, 16, 17, -16, -17, 127, 128, 129, -128, -129, 255, 256, 32767, 32768, -32768, -32769, 2**31 - 1, 2**31,
              -2**31, -2**31 - 1, M64 - 1, -M64, M64, -M64 - 1, M64 + 2]:
        try:
            got = marker_of(bs.PackStream._pack_int(v))
        except struct.error:
            got = "nofit"
        case(f"B_unit_{v}", "B", got, lambda m, v=v: int_marker(v, m))
    # D1 unit: the id is the low 31 bits of this process's hash
    for s in ["a", "node-1", "i55_x", "ünï"]:
        case(f"D1_unit_{s}", "D1", bs._node_int_id(s), lambda m, s=s: bolt_id(s, hash(s), m) if m != "id-from-node-id" else s)
    # D2 unit: _recompose_graph_row over layouts (relationship as the engine answers it, {"type","props"})
    sess = bs.BoltSession(None, lambda: None)
    def trip(v): return [f"{v}_id", f"{v}_labels", f"{v}_props"], [v, '["L"]', '[]']
    rel = {"type": "K", "props": {"w": 1}}
    for name, layout in [("abr", ["a", "r", "b"]), ("bra", ["b", "r", "a"]), ("r", ["r"]), ("abr_last", ["a", "b", "r"])]:
        cols, row, port_cols = [], [], []
        for v in layout:
            if v == "r":
                cols.append("r"); row.append(rel); port_cols.append(("R",))
            else:
                c, r = trip(v); cols += c; row += r; port_cols.append(("N", bs._node_int_id(v)))
        _, enc = sess._recompose_graph_row(cols, row)
        ri = layout.index("r"); data = enc[ri].data
        o = 2; _, o = rint(data, o); st, o = rint(data, o); en, o = rint(data, o)
        case(f"D2_unit_{name}", "D2", [st, en], lambda m, pc=port_cols, ri=ri: reported(pc, ri, m))
    # D3 unit
    for kind, val in [("str", "y" * 199), ("str", "y" * 200), ("str", "y" * 201), ("str", "x" * 300),
                      ("list", list(range(30))), ("list", list(range(100))), ("map", {f"k{i}": i for i in range(40)}), ("num", 12345)]:
        props = sess._parse_props_field(json.dumps([json.dumps({"key": "p", "value": val})]))
        got = props["p"]
        obs = {"kind": {str: "str", list: "list", dict: "map", int: "num"}[type(got)], "whole": got == val}
        case(f"D3_unit_{kind}_{len(str(val))}", "D3", obs, lambda m, kind=kind, n=len(str(val)): bolt_node_prop(kind, n, m))
    # E unit: the 64 feature combinations of an error text
    parts = {"c400": "[SQLCODE: <-400>:<Fatal error occurred>]", "subscript": "<SUBSCRIPT>", "temp": "^||%t(1,\"x\")",
             "sqlcq": "^%sqlcq.USER.cls1", "encoded": "Encoded subscript", "over": "> 32767 bytes"}
    keys = list(parts)
    for i in range(64):
        f = {k: bool(i >> j & 1) for j, k in enumerate(keys)}
        text = " ".join(parts[k] for k in keys if f[k]) or "plain error"
        case(f"E_unit_{i:02d}", "E", _is_long_list_temp_error(text), lambda m, f=f: is_long(f, m))
    # E transcription (inspected): runs() over statements; written as the source's two guards
    for tr in (False, True):
        for used in (False, True):
            st = {"transactional": tr, "used": used, "varlen": False}
            f = {k: True for k in keys}
            case(f"E_runs_tr{int(tr)}_used{int(used)}", "E-inspected", 1 if tr else (2 if used else 1), lambda m, f=f, st=st: runs(f, st, m),
                 note="transcription of _execute_parsed_sql/_unwind_by_index_retry guards; no product run")

    # ---------------- fixture: Bolt listener with a real engine
    import neo4j
    from iris_vector_graph.engine import IRISGraphEngine
    import importlib.metadata as md
    drv_here = md.version("intersystems-irispython")
    RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
    P = f"i55k_{TAG}_"; L = f"I55K{TAG}"; K = f"I55KK{TAG}"
    c = runtime.connect(); e = runtime.engine(c)
    A, B, Cn = P + "a", P + "b", P + "c"
    e.create_node(A, labels=[L], properties={"v": 1, "s200": "y" * 200, "s201": "y" * 201, "lst": list(range(100))})
    e.create_node(B, labels=[L], properties={"v": "1"})
    e.create_node(Cn, labels=[L], properties={"v": 2})
    e.create_edge(A, K, B, qualifiers={"w": 3})
    seen, col = {}, None
    for i in range(400000):
        s = f"{P}h{i}"; h = hash(s) & 0x7FFFFFFF
        if h in seen: col = (seen[h], s); break
        seen[h] = s
    e.create_node(col[0], labels=[L + "H"], properties={"n": 1}); e.create_node(col[1], labels=[L + "H"], properties={"n": 2})
    c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True).start()
    s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
    srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"): os.environ.pop(k, None)

    def bolt(q, params=None, auth=("neo4j", "x")):
        try:
            with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=auth, connection_timeout=10) as d, d.session() as s:
                res = s.run(q, params or {}); recs = list(res)
                return {"records": recs, "keys": list(res.keys())}
        except neo4j.exceptions.ServiceUnavailable as x:
            return {"broken": str(x)[:200]}
        except Exception as x:
            return {"code": getattr(x, "code", None), "error": type(x).__name__}

    # A: raw handshakes against the listener
    for offs in ([0x0404], [0x0003], [0x0909], [0x0005], [0x0405], [0x0805], [0x020805], [0x040805], [0x01FF, 0x0404]):
        case(f"A_wire_{'_'.join(hex(o) for o in offs)}", "A", handshake(port, offs), lambda m, offs=offs: negotiate(offs + [0] * (4 - len(offs)), m))
    # B: integers through the driver
    for v in [127, 128, -16, -17, 32767, 32768, 2**31, M64 - 1, -M64]:
        r = bolt(f"RETURN {v} AS x")
        got = "Records" if "records" in r and r["records"][0][0] == v and type(r["records"][0][0]) is int else ("Broken" if "broken" in r else "Failure")
        case(f"B_wire_{v}", "B", got, lambda m, v=v: pull_value(v, m))
    py_over = e.execute_cypher("RETURN 9223372036854775807 + 1 AS x").rows[0][0]
    r = bolt("RETURN 9223372036854775807 + 1 AS x")
    case("B_wire_overflow", "B", "Broken" if "broken" in r else ("Failure" if "code" in r else "Records"), lambda m, v=py_over: pull_value(v, m), engine_value=py_over)
    # C: FAILURE codes by cause
    r = bolt("MATCH (n RETURN n"); case("C_parse", "C", r.get("code"), lambda m: bolt_code("Parse", m))
    r = bolt(f"MATCH (n:{L}) RETURN count(n) AS x UNION MATCH (n:{L}) RETURN n.v AS x"); case("C_iris_sql", "C", r.get("code"), lambda m: bolt_code("IrisSql", m))
    r = bolt("RETURN $nope AS x"); case("C_undefined", "C", r.get("code"), lambda m: bolt_code("Undefined", m))
    if not drv_here.startswith("5.4"):
        r = bolt("UNWIND $xs AS a RETURN a", {"xs": [1, 2]}); case("C_driver_param", "C", r.get("code"), lambda m: bolt_code("DriverParam", m))
    os.environ["IVG_READ_ONLY"] = "true"
    r = bolt(f"CREATE (:{L}RO {{x: 1}})"); case("C_read_only", "C", r.get("code"), lambda m: bolt_code("ReadOnlyWrite", m))
    os.environ.pop("IVG_READ_ONLY")
    os.environ["IVG_API_KEY"] = "k55b"
    r = bolt("RETURN 1 AS x", auth=("neo4j", "wrong")); case("C_bad_key", "C", r.get("code"), lambda m: bolt_code("BadKey", m))
    os.environ.pop("IVG_API_KEY")
    # D1: collision and distinct pairs
    r = bolt(f"MATCH (n:{L}H) RETURN n ORDER BY n.n")
    obs = [dict(x[0])["n"] for x in r["records"]]
    pa = (bolt_id(col[0], hash(col[0]), None), 1); pb = (bolt_id(col[1], hash(col[1]), None), 2)
    case("D1_wire_collision", "D1", obs, lambda m: client_view2((bolt_id(col[0], hash(col[0]), m), 1), (bolt_id(col[1], hash(col[1]), m), 2), m), pair=list(col))
    r = bolt(f"MATCH (n:{L}) WHERE n.node_id IN ['{A}', '{Cn}'] RETURN n ORDER BY n.node_id")
    obs = [dict(x[0]).get("v") for x in r["records"]]
    case("D1_wire_distinct", "D1", obs, lambda m: client_view2((bolt_id(A, hash(A), m), 1), (bolt_id(Cn, hash(Cn), m), 2), m))
    # D2: endpoints through the driver (ids the driver hydrated)
    for name, q, layout in [("abr", f"MATCH (a:{L} {{node_id: '{A}'}})-[r:{K}]->(b) RETURN a, r, b", ["a", "r", "b"]),
                            ("bra", f"MATCH (a:{L} {{node_id: '{A}'}})-[r:{K}]->(b) RETURN b, r, a", ["b", "r", "a"]),
                            ("rev", f"MATCH (b:{L} {{node_id: '{B}'}})<-[r:{K}]-(a) RETURN b, r, a", ["b", "r", "a"]),
                            ("abr_last", f"MATCH (a:{L} {{node_id: '{A}'}})-[r:{K}]->(b) RETURN a, b, r", ["a", "b", "r"])]:
        rec = bolt(q)["records"][0]; ri = layout.index("r"); rv = rec[ri]
        start = rv.start_node.id if rv.start_node is not None else 0
        end = rv.end_node.id if rv.end_node is not None else 0
        ids = {"a": _nid(A, bs), "b": _nid(B, bs)}
        pc = [("R",) if v == "r" else ("N", ids[v]) for v in layout]
        case(f"D2_wire_{name}", "D2", [start, end], lambda m, pc=pc, ri=ri: reported(pc, ri, m), stored=[ids["a"], ids["b"]])
    # D3: whole-node properties over Bolt
    rec = bolt(f"MATCH (n:{L} {{node_id: '{A}'}}) RETURN n")["records"][0][0]
    full = {"s200": "y" * 200, "s201": "y" * 201, "lst": list(range(100))}
    for k, kind in [("s200", "str"), ("s201", "str"), ("lst", "list")]:
        got = rec[k]
        obs = {"kind": {str: "str", list: "list"}[type(got)], "whole": got == full[k]}
        case(f"D3_wire_{k}", "D3", obs, lambda m, kind=kind, n=len(str(full[k])): bolt_node_prop(kind, n, m))
    srv.close(); loop.call_soon_threadsafe(loop.stop); c2.close()
    # G: node filter equality on the SQL path
    stored = {A: ("Num", 1, "1"), B: ("Str", "1"), Cn: ("Num", 2, "2")}
    for name, cond, params, op in [("IntLit1", "n.v = 1", {}, ("IntLit", 1)), ("StrLit1", "n.v = '1'", {}, ("StrLit", "1")),
                                   ("IntParam1", "n.v = $x", {"x": 1}, ("IntParam", 1)), ("StrParam1", "n.v = $x", {"x": "1"}, ("StrParam", "1")),
                                   ("IntParam2", "n.v = $x", {"x": 2}, ("IntParam", 2)), ("StrLit2", "n.v = '2'", {}, ("StrLit", "2"))]:
        rows = e.execute_cypher(f"MATCH (n:{L}) WHERE {cond} RETURN n.node_id AS id ORDER BY id", params).rows
        case(f"G_{name}", "G", sorted(r[0] for r in rows), lambda m, op=op: sorted(k for k, st in stored.items() if matches(st, op, m)))
    c.close()
    # F: parameter lists under both IRIS drivers (this process and a 5.4.1 subprocess)
    f_obs = {drv_here: f_shapes()}
    v541 = os.environ.get("I55_VENV541")
    if v541:
        out = subprocess.run([v541, "-B", __file__, "--f-only"], capture_output=True, text=True, cwd=str(PIN), env={**os.environ}, timeout=600)
        f_obs.update(json.loads(out.stdout.strip().splitlines()[-1]))
    for drv, o in f_obs.items():
        case(f"F_unwind_param_{drv}", "F", o["unwind"], lambda m, drv=drv: unwind_param(drv, [1, 2], m))
        case(f"F_unwind_with_{drv}", "F", o["with"], lambda m: [1, 2])
        case(f"F_slice_{drv}", "F", o["slice"], lambda m, drv=drv: slice_answer(drv, [1, 2, 3, 4], 1, 3, m))

    # ---------------- verdict, sensitivities, tamper
    mism = [x["name"] for x in cases if x["predict"](None) != x["observed"]]
    sens = {m: [x["name"] for x in cases if x["predict"](m) != x["observed"]] for m in MUTS}
    tampered = json.loads(json.dumps(cases[-1]["observed"])); tampered = "Fail" if tampered != "Fail" else [9]
    tamper_detected = cases[-1]["predict"](None) != tampered
    body = {"verdict": "AGREES" if not mism else "DISAGREES", "cases": len(cases), "comparisons": len(cases), "mismatches": mism,
            "sensitivities_detected_cases": {m: len(v) for m, v in sens.items()}, "all_sensitivities_detected": all(sens.values()),
            "tamper": {"case": cases[-1]["name"], "tampered_observation": tampered, "detected": tamper_detected},
            "fixture": runtime.NAME, "port": runtime.PORT, "tag": TAG, "irispython": list(f_obs), "neo4j_driver": md.version("neo4j"),
            "collision_pair": list(col), "engine_overflow_value": str(py_over), "elapsed_s": round(time.time() - t0, 1),
            "pin": bc.pin_identity(PIN), "model_json_sha256": bc.sha(HERE / "model.json"),
            "product_files": {p: bc.sha(PIN / p) for p in ["iris_vector_graph/bolt_server.py", "iris_vector_graph/_engine/query.py", "iris_vector_graph/cypher/translator.py"]},
            "cells": [{k: v for k, v in x.items() if k != "predict"} | {"expected": x["predict"](None)} for x in cases],
            "scope": "Unit: the pin's negotiate_version, PackStream._pack_int, _node_int_id, _recompose_graph_row, _parse_props_field, "
                     "_is_long_list_temp_error. Fixture: the product's TCP Bolt listener and real engine read by the neo4j driver and a raw "
                     "socket; the SQL path for node filters; the IRIS driver versions for parameter lists. E-inspected rows are a "
                     "transcription of the retry guards (no product run). Not covered: WebSocket Bolt, PULL n (bolt_stream), HTTP."}
    out = bc.write_receipt("bolt_answers", Path(__file__).resolve(), body)
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "irispython")} | {"tamper": tamper_detected, "receipt": str(out.relative_to(REPO))}))
    for x in mism: print("MISMATCH", x)
    for m, v in sens.items():
        if not v: print("UNDETECTED", m)


def _nid(s, bs): return bs._node_int_id(s)


def f_shapes():
    c = runtime.connect(); e = runtime.engine(c)
    def ans(q, p):
        r = e.execute_cypher(q, p)
        if getattr(r, "error", None): return "Fail"
        return [x[0] for x in r.rows] if len(r.rows) != 1 or q.startswith("UNWIND") or q.startswith("WITH $xs") else r.rows[0][0]
    o = {"unwind": ans("UNWIND $xs AS a RETURN a", {"xs": [1, 2]}), "with": ans("WITH $xs AS l UNWIND l AS a RETURN a", {"xs": [1, 2]}),
         "slice": ans("RETURN $l[$s..$e] AS x", {"l": [1, 2, 3, 4], "s": 1, "e": 3})}
    c.close()
    return o


if __name__ == "__main__":
    if "--f-only" in sys.argv:
        import importlib.metadata as md
        print(json.dumps({md.version("intersystems-irispython"): f_shapes()}))
    else:
        main()
