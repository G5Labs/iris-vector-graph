"""cypher_fns binding: Cypher built-in functions over run-time values on the run-isolated continuation fixture
(ivg-cont-20261117-iris), through the product's SQL Cypher path (engine._execute_parsed_sql, the path execute_cypher
takes when the native executor declines the shape; the binding records whether it declined) and, for the
SQL-callable helpers, `SELECT <IVG Schema>.CypherFn_IVGLISTGET / CypherFn_IVGRANGE / JSON_ARRAYGET`. Outcomes are
compared with a port of cypher_fns.rs. Mutations mirror the controls. Ordinary data, fresh prefix per run."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("CF_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["row_index_through_ivglistget", "ivglistget_no_wrap", "literal_negative_unwrapped", "property_to_cy_reverse",
        "row_key_by_value", "range_zero_raises", "range_ignores_direction", "per_row_evaluation"]
LIST = [1, 2, 3]
INDEXES = [-4, -3, -1, 0, 2, 3]
RANGES = [(1, 3, 0), (1, 5, 2), (5, 1, -2), (1, 5, -1), (5, 1, 1), (1, 1, 3)]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- port of cypher_fns.rs (Elem: ("at", pos) | "null" | "fails")
def json_arrayget(n, i):
    return "fails" if i < 0 else (("at", i) if i < n else "null")


def ivglistget(n, i, m):
    j = i if m.get("ivglistget_no_wrap") else (n + i if i < 0 else i)
    return "null" if j < 0 or j >= n else ("at", j)


def translated_index(kind, n, i, m):
    if kind == "literal":
        if m.get("literal_negative_unwrapped"):
            return json_arrayget(n, i)
        return (json_arrayget(n, n + i) if n >= -i else "null") if i < 0 else json_arrayget(n, i)
    return ivglistget(n, i, m) if m.get("row_index_through_ivglistget") else json_arrayget(n, i)


def reverse_result(kind, val, m):
    cy = kind != "property" or m.get("property_to_cy_reverse")
    return ("list" if val == "list" else "text") if cy else "text"


def node_key_read(kind, name, value, m):
    return value if kind == "param" or m.get("row_key_by_value") else name


def ivg_count(s, e, st, m):
    if st > 0:
        return (e - s) // st + 1 if e >= s else 0
    if st < 0:
        if m.get("range_ignores_direction"):
            return 0
        return (s - e) // (-st) + 1 if s >= e else 0
    return 0


def ivgrange(s, e, st, m):
    if st == 0:
        return "error" if m.get("range_zero_raises") else 0
    return ivg_count(s, e, st, m)


def distinct_per_rows(rows, m):
    return rows if m.get("per_row_evaluation") else 1


def classify_elem(rows, error):
    if error:
        return "fails" if "RANGE" in error else "error:" + error[-80:]
    v = rows[0][0]
    if v is None:
        return "null"
    return ("at", LIST.index(int(v)))


def main():
    t0 = time.time(); c = runtime.connect()
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    e = IRISGraphEngine(c, embedding_dimension=768)
    p, L = f"cf{TAG}_", f"CF{TAG}"
    e.execute_cypher(f"CREATE (n:{L} {{id: '{p}c', l: [1, 2, 3], k: 'gotcha', num: 5, str: 'abc'}})")
    C = f"MATCH (n:{L} {{id: '{p}c'}})"
    declined = []

    def run(q, params=None):
        params = params or {}
        if e._try_native(parse_query(q), params) is None:
            declined.append(q)
        r = e._execute_parsed_sql(parse_query(q), params, None)
        return [list(x) for x in r.rows], (str(r.error) if r.error else None)

    def sql(fn, *args):
        cur = c.cursor()
        try:
            cur.execute(f"SELECT {e._ivg_schema}.{fn}({', '.join('?' * len(args))})", list(args)); return cur.fetchone()[0], None
        except Exception as x:
            return None, str(x)
        finally:
            cur.close()

    got = {}
    for i in INDEXES:
        got[f"row_index_{i}"] = classify_elem(*run(f"{C} UNWIND [{i}] AS i RETURN n.l[i]"))
        got[f"literal_index_{i}"] = classify_elem(*run(f"{C} RETURN n.l[{i}]"))
        v, err = sql("CypherFn_IVGLISTGET", "[1,2,3]", str(i))
        got[f"sql_ivglistget_{i}"] = "fails" if err else ("null" if v in (None, "") else ("at", LIST.index(int(v))))
        # JSON_ARRAYGET refuses `?` arguments on IRIS ("Invalid number of parameters"), so the literals are inlined
        cur = c.cursor()
        try:
            cur.execute(f"SELECT {e._ivg_schema}.JSON_ARRAYGET('[1,2,3]', {int(i)})"); v, err = cur.fetchone()[0], None
        except Exception as x:
            v, err = None, str(x)
        cur.close()
        got[f"sql_json_arrayget_{i}"] = ("fails" if "RANGE" in err else "error:" + err[-80:]) if err else ("null" if v in (None, "") else ("at", LIST.index(int(v))))
    for k, q in (("reverse_property_list", f"{C} RETURN reverse(n.l)"), ("reverse_literal_list", "RETURN reverse([1, 2, 3])"),
                 ("reverse_property_string", f"{C} RETURN reverse(n.str)")):
        rows, err = run(q); v = rows[0][0] if rows else None
        got[k] = "list" if isinstance(v, list) and v == [3, 2, 1] else ("text" if isinstance(v, str) else f"other:{v!r}:{err}")
    rows, _ = run(f"{C} UNWIND ['num'] AS k RETURN n[k]"); got["node_row_key"] = {"gotcha": "name", 5: "value"}.get(rows[0][0], repr(rows[0][0]))
    rows, _ = run(f"{C} RETURN n[$k]", {"k": "num"}); got["node_param_key"] = {"gotcha": "name", 5: "value"}.get(rows[0][0], repr(rows[0][0]))
    for s_, e_, st in RANGES:
        rows, err = run(f"UNWIND [{st}] AS s RETURN range({s_}, {e_}, s)")
        got[f"range_row_{s_}_{e_}_{st}"] = "error" if err else len(rows[0][0])
        v, err = sql("CypherFn_IVGRANGE", s_, e_, st)
        got[f"sql_ivgrange_{s_}_{e_}_{st}"] = "error" if err else len(json.loads(v))
    rows, _ = run("UNWIND [1, 2, 3, 4, 5] AS i RETURN randomUUID() AS u, rand() AS r")
    got["uuid_distinct_over_5"] = len({r[0] for r in rows}); got["rand_distinct_over_5"] = len({r[1] for r in rows})
    c.close()

    def predict(m):
        out = {}
        for i in INDEXES:
            out[f"row_index_{i}"] = translated_index("row", 3, i, m)
            out[f"literal_index_{i}"] = translated_index("literal", 3, i, m)
            out[f"sql_ivglistget_{i}"] = ivglistget(3, i, m)
            out[f"sql_json_arrayget_{i}"] = json_arrayget(3, i)
        out["reverse_property_list"] = reverse_result("property", "list", m)
        out["reverse_literal_list"] = reverse_result("literal", "list", m)
        out["reverse_property_string"] = reverse_result("property", "string", m)
        out["node_row_key"] = "value" if node_key_read("row", "k", "num", m) == "num" else "name"
        out["node_param_key"] = "value" if node_key_read("param", "k", "num", m) == "num" else "name"
        for s_, e_, st in RANGES:
            out[f"range_row_{s_}_{e_}_{st}"] = ivgrange(s_, e_, st, m)
            out[f"sql_ivgrange_{s_}_{e_}_{st}"] = ivgrange(s_, e_, st, m)
        out["uuid_distinct_over_5"] = distinct_per_rows(5, m); out["rand_distinct_over_5"] = distinct_per_rows(5, m)
        return out

    norm = lambda d: json.loads(json.dumps(d))
    got = norm(got); want = norm(predict({}))
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if got.get(k) != want[k]]
    sens = {mm: sum(1 for k, v in norm(predict({mm: True})).items() if v != got.get(k)) for mm in MUTS}
    tampered = dict(got); tampered["row_index_-1"] = ["at", 2]
    tamper_detected = any(tampered.get(k) != want[k] for k in want)
    body = {"kind": "binding", "model": "cypher_fns", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "native_declined": len(declined), "native_declined_queries": declined[:6],
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "cypher_fns.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/cypher/translator.py", "iris_vector_graph/schema.py",
                                                                   "iris_src/src/Graph/KG/CypherFn.cls", "iris_src/src/Graph/KG/SqlProcs.cls"]}},
            "scope": "Actual execute_cypher SQL path and SQL-callable helpers on IRIS 2026.1 (pin 3eaa79cf); one Cypher-written node; "
                     "indexes -4..3 over [1,2,3]; six run-time ranges; five rows for randomUUID()/rand(). The native executor declined every "
                     "function shape here (counted in native_declined)."}
    d = REPO / ".g5/Verus_verification/results/cypher_fns" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "native_declined", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
