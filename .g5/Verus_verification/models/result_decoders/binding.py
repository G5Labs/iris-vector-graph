"""result_decoders binding (iteration 58, W62): the product's translator, decoders and four final readers against a port
of result_decoders.rs. Fixture ivg-cont-20261117-iris (USER), fresh prefix i58d_<tag>_ (no sync()). Nodes are written
by create_node with one property `p` of each modeled kind (int 3, float 2.5, string, '', true, false, [], {}, none) and
`k = 'a'`. Each value-column shape (n.p; WITH n.p; RETURN coalesce(n.p, n.q); WITH coalesce; RETURN CASE; WITH CASE)
is read at execute_cypher (PY), Bolt (neo4j driver against start_tcp_bolt_server, real engine), /api/cypher (API) and
/db/neo4j/tx/commit (TX), under intersystems-irispython 5.3.2 (this venv) and 5.4.1 (I55_VENV541, a subprocess that
runs the same readers). Also the comparison column `n.p > 2.7` and the unbound OPTIONAL node's labels column.
Each port mutation mirrors a control of model.json and must be detected; one tampered observation must be detected."""
import asyncio, json, os, socket, subprocess, sys, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/Verus_verification/tools")); sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import binding_common as bc  # noqa: E402
PIN = bc.import_pin()
import runtime  # noqa: E402

MUTS = ["case-typed", "with-coalesce-typed", "coalesce-cast-gone", "driver-541-native", "no-mark-decode", "no-prop-text",
        "case-prop-text", "bool-text-ignored", "bool-expr-off", "gt-text-zero", "missing-not-null", "labels-null",
        "ret-coalesce-untyped", "with-prop-untyped", "typed-emitted-raw", "no-json-decode", "bit-one-false"]
WRITES = {"int": ("Int", 3), "float": ("Float", 25), "str": ("Str", "txt"), "empty": ("Empty",), "btrue": ("Bool", True),
          "bfalse": ("Bool", False), "list0": ("List0",), "map0": ("Map0",), "absent": ("Absent",)}
PYVAL = {"int": 3, "float": 2.5, "str": "txt", "empty": "", "btrue": True, "bfalse": False, "list0": [], "map0": {}}
SHAPES = ["Prop", "WithProp", "RetCoalesce", "WithCoalesce", "RetCase", "WithCase"]


# ------------------------------------------------------------------ port of result_decoders.rs (m = active mutation)
def store(w):
    k = w[0]
    if k == "Absent": return ("Missing",)
    if k in ("Int", "Float"): return ("Native", (k[0], w[1]))
    if k == "Str": return ("Txt", ("Plain", w[1]))
    return ("Txt", {"Empty": ("Empty",), "Bool": ("BoolT", w[1] if k == "Bool" else None), "List0": ("ListT",), "Map0": ("MapT",)}[k])


def reads_node_value(s, m):
    if s == "RetCase" and m == "case-typed": return True
    if s == "WithCoalesce" and m == "with-coalesce-typed": return True
    if s == "RetCoalesce" and m == "ret-coalesce-untyped": return False
    if s == "WithProp" and m == "with-prop-untyped": return False
    return s in ("Prop", "WithProp", "RetCoalesce")


def sql_form(s, m):
    if reads_node_value(s, m): return "Raw" if m == "typed-emitted-raw" else "CyTyped"
    if s == "WithCoalesce": return "Raw" if m == "coalesce-cast-gone" else "CastVarchar"
    return "Raw"


def prop_text_col(s, m):
    if m == "no-prop-text": return False
    return reads_node_value(s, m) or (m == "case-prop-text" and s in ("RetCase", "WithCase"))


def sql_value(f, st, d, m):
    if st[0] == "Missing": return ("T", ("Empty",)) if m == "missing-not-null" else ("Null",)
    if st[0] == "Txt": return ("T", st[1])
    n = st[1]
    if f == "CyTyped": return ("T", ("Mark", n))
    if f == "CastVarchar": return ("T", ("NumT", n))
    return ("N", n) if d == "5.3.2" or m == "driver-541-native" else ("T", ("NumT", n))


def dec_typed(v, m):
    if v[0] == "T":
        t = v[1]
        if t[0] == "Mark": return v if m == "no-mark-decode" else ("N", t[1])
        if t[0] == "ListT": return v if m == "no-json-decode" else ("L0",)
        if t[0] == "MapT": return ("M0",)
    return v


def dec_prop_text(v, m):
    if v[0] == "T" and v[1][0] == "BoolT" and m != "bool-text-ignored": return ("B", v[1][1])
    return v


def dec_bool_expr(v, m=None):
    if v[0] == "Bit": return ("B", m != "bit-one-false") if v[1] == 1 else ("B", False) if v[1] == 0 else v
    if v[0] == "T" and v[1][0] == "BoolT": return ("B", v[1][1])
    return v


def text_str(t):
    k = t[0]
    if k == "Plain": return t[1]
    if k == "Empty": return ""
    if k == "BoolT": return "true" if t[1] else "false"
    if k == "ListT": return "[]"
    if k == "MapT": return "{}"
    if k == "NumT": return str(t[1][1]) if t[1][0] == "I" else str(t[1][1] / 10)
    return "\x01" + t[1][0] + str(t[1][1])


def to_v(v):
    k = v[0]
    if k == "Null": return ["Null"]
    if k == "N": return ["Int", v[1][1]] if v[1][0] == "I" else ["Float", v[1][1]]
    if k == "T": return ["Str", text_str(v[1])]
    if k == "B": return ["Bool", v[1]]
    if k == "L0": return ["List0"]
    if k == "M0": return ["Map0"]
    return ["Int", v[1]]


def answer(s, w, d, m):
    v = sql_value(sql_form(s, m), store(w), d, m)
    a = dec_typed(v, m) if reads_node_value(s, m) else v
    return to_v(dec_prop_text(a, m) if prop_text_col(s, m) else a)


def answer_gt(w, c, m):
    st = store(w)
    if st[0] == "Native":
        n = st[1]; t = 10 * n[1] if n[0] == "I" else n[1]
        v = ("Bit", 1 if t > c else 0)
    else:
        v = ("Bit", 0) if m == "gt-text-zero" else ("Null",)
    return to_v(v if m == "bool-expr-off" else dec_bool_expr(v, m))


def node_labels_answer(r, m):
    # unbound node: id null; labels '[]' (or null under the labels-null mutation)
    if r == "BOLT": return ["Null"]
    return ["Null"] if m == "labels-null" else ["Str", "[]"]


# ------------------------------------------------------------------ the product
def classify(v):
    if v is None: return ["Null"]
    if isinstance(v, bool): return ["Bool", v]
    if isinstance(v, int): return ["Int", v]
    if isinstance(v, float): return ["Float", round(v * 10)]
    if isinstance(v, str): return ["Str", v]
    if isinstance(v, list) and not v: return ["List0"]
    if isinstance(v, dict) and not v: return ["Map0"]
    return ["Other", repr(v)[:80]]


def queries(L, P):
    case = "CASE WHEN n.k = 'a' THEN n.p ELSE n.q END"
    return {
        "Prop": f"MATCH (n:{L}) RETURN n.node_id AS id, n.p AS x ORDER BY id",
        "WithProp": f"MATCH (n:{L}) WITH n.node_id AS id, n.p AS x RETURN id, x ORDER BY id",
        "RetCoalesce": f"MATCH (n:{L}) RETURN n.node_id AS id, coalesce(n.p, n.q) AS x ORDER BY id",
        "WithCoalesce": f"MATCH (n:{L}) WITH n, coalesce(n.p, n.q) AS x RETURN n.node_id AS id, x ORDER BY id",
        "RetCase": f"MATCH (n:{L}) RETURN n.node_id AS id, {case} AS x ORDER BY id",
        "WithCase": f"MATCH (n:{L}) WITH n, {case} AS x RETURN n.node_id AS id, x ORDER BY id",
        "Gt": f"MATCH (n:{L}) WHERE n.node_id IN ['{P}int', '{P}float', '{P}str', '{P}empty', '{P}absent'] "
              f"RETURN n.node_id AS id, n.p > 2.7 AS x ORDER BY id",
        "Opt": f"MATCH (a:{L} {{node_id: '{P}int'}}) OPTIONAL MATCH (a)-[:I58D_NONE]->(b) RETURN a.node_id AS id, b",
    }


def observe(L, P):
    """Rows of every query at the four readers, with the IRIS driver this process runs."""
    import importlib.metadata as md
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph import bolt_server as bs
    import neo4j
    Q = queries(L, P); obs = {r: {} for r in ("PY", "BOLT", "API", "TX")}
    c = runtime.connect(); e = runtime.engine(c)
    for k, q in Q.items():
        r = e.execute_cypher(q, {})
        obs["PY"][k] = {"columns": list(r.columns or []), "rows": [list(x) for x in r.rows], "error": getattr(r, "error", None)}
    c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True).start()
    s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
    srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
    os.environ.pop("IVG_API_KEY", None); os.environ.pop("IVG_READ_ONLY", None)
    with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x"), connection_timeout=10) as d:
        for k, q in Q.items():
            with d.session() as s:
                res = s.run(q, {}); rows = [list(x.values()) for x in res]
                obs["BOLT"][k] = {"columns": list(res.keys()), "rows": [[None if type(v).__name__ == "Node" and False else v for v in r] for r in rows]}
    loop.call_soon_threadsafe(srv.close); time.sleep(0.3); loop.call_soon_threadsafe(loop.stop); c2.close()
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    with TestClient(cypher_api.app) as client:
        for k, q in Q.items():
            a = client.post("/api/cypher", json={"query": q, "parameters": {}}).json()
            obs["API"][k] = {"columns": a.get("columns"), "rows": a.get("rows")}
            t = client.post("/db/neo4j/tx/commit", json={"statements": [{"statement": q, "parameters": {}}]}).json()
            res = (t.get("results") or [{}])[0]
            obs["TX"][k] = {"columns": res.get("columns"), "rows": [x["row"] for x in res.get("data", [])], "errors": t.get("errors")}
    c.close()
    return md.version("intersystems-irispython"), json.loads(json.dumps(obs, default=lambda v: {"__node__": repr(v)[:120]} if v is not None else None))


def main():
    import importlib.metadata as md
    t0 = time.time()
    RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
    P = f"i58d_{TAG}_"; L = f"I58DB{TAG}"
    c = runtime.connect(); e = runtime.engine(c)
    for key, v in PYVAL.items():
        e.create_node(P + key, labels=[L], properties={"k": "a", "p": v})
    e.create_node(P + "absent", labels=[L], properties={"k": "a"})
    c.close()
    obs = dict([observe(L, P)])
    v541 = os.environ.get("I55_VENV541")
    if v541:
        out = subprocess.run([v541, "-B", __file__, "--observe", L, P], capture_output=True, text=True, cwd=str(PIN), env={**os.environ}, timeout=900)
        try:
            obs.update(json.loads(out.stdout.strip().splitlines()[-1]))
        except Exception:
            print("5.4.1 subprocess failed:", out.stderr[-2000:])
    cases = []

    def case(name, observed, predict):
        cases.append({"name": name, "observed": observed, "predict": predict})

    for drv, o in obs.items():
        for r, per in o.items():
            for s in SHAPES:
                got = {row[0]: row[1] for row in per[s]["rows"]}
                for key, w in WRITES.items():
                    case(f"{drv}_{r}_{s}_{key}", classify(got.get(P + key, "<no row>")), lambda m, s=s, w=w, drv=drv: answer(s, w, drv, m))
            got = {row[0]: row[1] for row in per["Gt"]["rows"]}
            for key in ("int", "float", "str", "empty", "absent"):
                case(f"{drv}_{r}_Gt_{key}", classify(got.get(P + key, "<no row>")), lambda m, w=WRITES[key]: answer_gt(w, 27, m))
            opt = per["Opt"]
            if r == "BOLT":
                ob = classify(opt["rows"][0][1]) if opt["columns"] == ["id", "b"] else ["Other", opt["columns"]]
            else:
                ob = classify(opt["rows"][0][opt["columns"].index("b_labels")]) if "b_labels" in (opt["columns"] or []) else ["Other", opt["columns"]]
            case(f"{drv}_{r}_Opt_labels", ob, lambda m, r=r: node_labels_answer(r, m))

    mism = [x["name"] for x in cases if x["predict"](None) != x["observed"]]
    sens = {m: [x["name"] for x in cases if x["predict"](m) != x["observed"]] for m in MUTS}
    tc = next(x for x in cases if x["name"].endswith("_PY_WithCoalesce_int"))
    tampered = ["Int", 3] if tc["observed"] != ["Int", 3] else ["Str", "3"]
    tamper_detected = tc["predict"](None) != tampered
    body = {"verdict": "AGREES" if not mism else "DISAGREES", "cases": len(cases), "comparisons": len(cases), "mismatches": mism,
            "agrees": len(cases) - len(mism),
            "sensitivities_detected_cases": {m: len(v) for m, v in sens.items()}, "all_sensitivities_detected": all(sens.values()),
            "tamper": {"case": tc["name"], "observed": tc["observed"], "tampered_observation": tampered, "detected": tamper_detected},
            "fixture": runtime.NAME, "port": runtime.PORT, "tag": TAG, "prefix": P, "label": L, "irispython": list(obs),
            "neo4j_driver": md.version("neo4j"), "elapsed_s": round(time.time() - t0, 1),
            "pin": bc.pin_identity(PIN), "model_json_sha256": bc.sha(HERE / "model.json"),
            "product_files": {p: bc.sha(PIN / p) for p in ["iris_vector_graph/_engine/query.py", "iris_vector_graph/cypher/translator.py", "iris_vector_graph/prop_values.py", "iris_vector_graph/bolt_server.py"]},
            "cells": [{k: v for k, v in x.items() if k != "predict"} | {"expected": x["predict"](None)} for x in cases],
            "scope": "Fixture: create_node-written values of nine kinds read by six value-column shapes, a comparison column and an "
                     "unbound OPTIONAL node at execute_cypher, Bolt (neo4j driver 6.4.1, the product's TCP listener), /api/cypher "
                     "and /db/neo4j/tx/commit, under IRIS drivers 5.3.2 and 5.4.1. Not covered: Cypher-written values, "
                     "relationship properties, the native executor's own rows, numeric/map/mixed decoders (no modeled kind)."}
    out = bc.write_receipt("result_decoders", Path(__file__).resolve(), body)
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "agrees", "all_sensitivities_detected", "irispython")} | {"tamper": tamper_detected, "receipt": str(out.relative_to(REPO))}))
    for x in mism: print("MISMATCH", x, [c for c in cases if c["name"] == x][0]["observed"])
    for m, v in sens.items():
        if not v: print("UNDETECTED", m)


if __name__ == "__main__":
    if "--observe" in sys.argv:
        i = sys.argv.index("--observe")
        drv, o = observe(sys.argv[i + 1], sys.argv[i + 2])
        print(json.dumps({drv: o}))
    else:
        main()
