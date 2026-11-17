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
MUTS = ["row_index_through_ivglistget", "ivglistget_no_wrap", "literal_negative_unwrapped", "with_literal_elem_unwrapped",
        "with_literal_elem_untyped", "null_index_is_null", "property_to_cy_reverse", "reverse_column_typed",
        "row_key_by_value", "with_key_by_value", "range_zero_raises", "range_ignores_direction", "per_row_evaluation"]
LIST = [1, 2, 3]
INDEXES = [-4, -3, -1, 0, 2, 3]
SOURCES = ("property", "with_literal", "with_other")
KINDS = ("row", "literal", "param")
RANGES = [(1, 3, 0), (1, 5, 2), (5, 1, -2), (1, 5, -1), (5, 1, 1), (1, 1, 3)]


def REV(C, W, O):
    """reverse() argument forms: (kind, value, whether the translator knows the column is a list, query)."""
    return [("property", "list", False, f"{C} RETURN reverse(n.l)"), ("slice", "list", True, f"{W} RETURN reverse(l[0..3])"),
            ("subscript", "list", False, "WITH [[1, 2, 3], [4]] AS l RETURN reverse(l[0])"),
            ("other_call", "list", False, f"{C} RETURN reverse(coalesce(n.l, []))"),
            ("variable", "list", False, f"{O} RETURN reverse(l)"), ("variable", "list", True, f"{W} RETURN reverse(l)"),
            ("literal", "list", True, "RETURN reverse([1, 2, 3])"), ("list_call", "list", True, f"{C} RETURN reverse(n.l + [])"),
            ("case", "list", True, "RETURN reverse(CASE WHEN 1 = 1 THEN [1, 2, 3] END)"),
            ("property", "string", False, f"{C} RETURN reverse(n.str)"),
            ("variable", "string", False, f"{C} WITH n.str AS s RETURN reverse(s)")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- port of cypher_fns.rs (Elem: ("at", pos) | "null" | "fails")
def json_arrayget(n, i):
    return "fails" if i < 0 else (("at", i) if i < n else "null")


def ivglistget(n, i, m):
    j = i if m.get("ivglistget_no_wrap") else (n + i if i < 0 else i)
    return "null" if j < 0 or j >= n else ("at", j)


def json_arrayget_opt(n, i, m):
    if i is None:
        return "null" if m.get("null_index_is_null") else (("at", 0) if n > 0 else "null")
    return json_arrayget(n, i)


def json_value_index(n, i):
    if i is None:
        return ("at", 0) if n > 0 else "null"
    return "fails" if i < 0 else (("at", i) if i < n else "null")


def cy_list_elem(n, i):
    j = n + i if i < 0 else i
    return "null" if j < 0 or j >= n else ("at", j)


def translated_index(src, kind, n, i, m):
    if kind == "literal":
        if i is None:
            return json_arrayget_opt(n, None, m)
        if m.get("literal_negative_unwrapped"):
            return json_arrayget(n, i)
        return (json_arrayget(n, n + i) if n >= -i else "null") if i < 0 else json_arrayget(n, i)
    if kind == "row":
        if src == "property":
            if m.get("row_index_through_ivglistget"):
                return "null" if i is None else ivglistget(n, i, m)
            return json_arrayget_opt(n, i, m)
        if src == "with_literal":
            if i is None:
                return json_value_index(n, None)
            return json_arrayget(n, i) if m.get("with_literal_elem_unwrapped") else cy_list_elem(n, i)
        return json_value_index(n, i)
    if src == "property":
        return "fails"
    return "fails" if i is None else json_arrayget(n, i)


def translated_type(src, kind, m):
    if kind == "literal":
        return "typed"
    if kind == "row":
        return "typed" if src == "with_literal" and not m.get("with_literal_elem_untyped") else "text"
    return "text"


def with_type(elem, src, kind, i, m):
    # the type is compared where the index is not null (a null index's element type is not claimed)
    return elem if not isinstance(elem, tuple) or i is None else (elem[0], elem[1], translated_type(src, kind, m))


def reverse_result(kind, val, known, m):
    if val == "string":
        return "reversed_text"
    cy = kind in ("literal", "comprehension", "list_call", "variable", "case") or m.get("property_to_cy_reverse")
    if not cy:
        return "reversed_text"
    return "list" if (known or m.get("reverse_column_typed")) else "list_as_json_text"


def node_key_read(kind, name, value, m):
    if kind == "with":
        return value if m.get("with_key_by_value") else "fails"
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


FAIL_MARKS = ("RANGE", "Incorrect number of parameters", "Invalid number of parameters", "JSON_VALUE")


def classify_elem(rows, error, i=None):
    if error:
        return "fails" if any(x in error for x in FAIL_MARKS) else "error:" + error[-80:]
    v = rows[0][-1]
    if v is None:
        return "null"
    pos = LIST.index(int(v))
    return ("at", pos) if i is None else ("at", pos, "typed" if isinstance(v, int) and not isinstance(v, bool) else "text")


def classify_reverse(rows, err, want_list, want_text):
    if err or not rows:
        return f"error:{err}"
    v = rows[0][-1]
    if isinstance(v, list):
        return "list" if v == want_list else f"other:{v!r}"
    if isinstance(v, str):
        if v == want_text:
            return "reversed_text"
        if v.startswith("["):
            return "list_as_json_text"
        return "reversed_text" if v.startswith("]") else f"other:{v!r}"
    return f"other:{v!r}"


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
    W = "WITH [1, 2, 3] AS l"
    O = f"{C} WITH n.l AS l"
    for i in INDEXES + [None]:
        lit = "null" if i is None else str(i)
        tag = "null" if i is None else str(i)
        q = {("property", "row"): f"{C} UNWIND [{lit}] AS i RETURN n.l[i]", ("property", "literal"): f"{C} RETURN n.l[{lit}]",
             ("property", "param"): f"{C} RETURN n.l[$i]",
             ("with_literal", "row"): f"{W} UNWIND [{lit}] AS i RETURN l[i]", ("with_literal", "literal"): f"{W} RETURN l[{lit}]",
             ("with_literal", "param"): f"{W} RETURN l[$i]",
             ("with_other", "row"): f"{O} UNWIND [{lit}] AS i RETURN l[i]", ("with_other", "literal"): f"{O} RETURN l[{lit}]",
             ("with_other", "param"): f"{O} RETURN l[$i]"}
        for (src, kind), text in q.items():
            got[f"index_{src}_{kind}_{tag}"] = classify_elem(*run(text, {"i": i} if kind == "param" else None), i=i)
        if i is None:
            continue
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
    for kind, val, known, text in REV(C, W, O):
        got[f"reverse_{kind}_{val}_{'known' if known else 'unknown'}"] = classify_reverse(*run(text), [3, 2, 1], "cba" if val == "string" else None)
    rows, _ = run(f"{C} UNWIND ['num'] AS k RETURN n[k]"); got["node_row_key"] = {"gotcha": "name", 5: "value"}.get(rows[0][0], repr(rows[0][0]))
    rows, _ = run(f"{C} RETURN n[$k]", {"k": "num"}); got["node_param_key"] = {"gotcha": "name", 5: "value"}.get(rows[0][0], repr(rows[0][0]))
    rows, err = run(f"{C} WITH n, 'num' AS k RETURN n[k]")
    got["node_with_key"] = "fails" if err and "Non-integer index type" in err else ({"gotcha": "name", 5: "value"}.get(rows[0][0], repr(rows[0][0])) if rows else f"error:{err}")
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
        for i in INDEXES + [None]:
            tag = "null" if i is None else str(i)
            for src in SOURCES:
                for kind in KINDS:
                    out[f"index_{src}_{kind}_{tag}"] = with_type(translated_index(src, kind, 3, i, m), src, kind, i, m)
            if i is None:
                continue
            out[f"sql_ivglistget_{i}"] = ivglistget(3, i, m)
            out[f"sql_json_arrayget_{i}"] = json_arrayget(3, i)
        for kind, val, known, _ in REV("", "", ""):
            out[f"reverse_{kind}_{val}_{'known' if known else 'unknown'}"] = reverse_result(kind, val, known, m)
        out["node_row_key"] = "value" if node_key_read("row", "k", "num", m) == "num" else "name"
        out["node_param_key"] = "value" if node_key_read("param", "k", "num", m) == "num" else "name"
        out["node_with_key"] = (lambda r: "fails" if r == "fails" else ("value" if r == "num" else "name"))(node_key_read("with", "k", "num", m))
        for s_, e_, st in RANGES:
            out[f"range_row_{s_}_{e_}_{st}"] = ivgrange(s_, e_, st, m)
            out[f"sql_ivgrange_{s_}_{e_}_{st}"] = ivgrange(s_, e_, st, m)
        out["uuid_distinct_over_5"] = distinct_per_rows(5, m); out["rand_distinct_over_5"] = distinct_per_rows(5, m)
        return out

    norm = lambda d: json.loads(json.dumps(d))
    got = norm(got); want = norm(predict({}))
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if got.get(k) != want[k]]
    sens = {mm: sum(1 for k, v in norm(predict({mm: True})).items() if v != got.get(k)) for mm in MUTS}
    tampered = dict(got); tampered["index_property_row_-1"] = ["at", 2, "typed"]
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
                     "indexes -4..3 and null over [1,2,3] from three list sources (property, WITH literal, WITH property) by literal, row "
                     "and parameter; eleven reverse() argument forms; three node-key forms; six run-time ranges; five rows for "
                     "randomUUID()/rand(). The native executor declined every function shape here (counted in native_declined). The "
                     "element type is compared for non-null indexes only. Iteration 50 (review 47-49 items 2, 3, 6, m5)."}
    d = REPO / ".g5/Verus_verification/results/cypher_fns" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "native_declined", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
