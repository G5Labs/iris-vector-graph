"""W55 follow-ups (after the first observation, before reading the deciding source): isolate each miss."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W55_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    p, L = f"i48b_{TAG}_", f"I48F{TAG}"
    out = {"run": RUN, "fixture": runtime.NAME, "prefix": p, "label": L, "cases": {}}

    def q(k, text, params=None):
        cell = {"query": text, "params": params or {}}
        try:
            nat = e._try_native(parse_query(text), params or {})
            cell["native"] = None if nat is None else [list(x) for x in nat[1].rows]
        except Exception as x:
            cell["native"] = f"EXC {type(x).__name__}: {str(x)[:200]}"
        try:
            r = e.execute_cypher(text, params or {})
            cell["rows"] = [list(x) for x in r.rows]
            cell["error"] = str(r.error)[:300] if getattr(r, "error", None) else None
        except Exception as x:
            cell["exception"] = f"{type(x).__name__}: {str(x)[:300]}"
        out["cases"][k] = cell

    e.execute_cypher(f"CREATE (n:{L} {{id: '{p}c', s: 'hello', l: [1, 2, 3, 4, 5]}})")
    C = f"MATCH (n:{L} {{id: '{p}c'}})"
    # F1 substring negative / negative length
    q("F1_lit_lit", "RETURN substring('hello', -1, 2), substring('hello', 1, -1)")
    q("F1_stored_neglen", f"{C} RETURN substring(n.s, 1, -1)")
    q("F1_rows", "UNWIND [-1, -3] AS a RETURN a, substring('hello', a, 2)")
    # F2 left/right 0
    q("F2_lit_lit", "RETURN left('hello', 0), right('hello', 0), substring('hello', 0, 0), substring('hello', 2, 0)")
    q("F2_rows", "UNWIND ['hello'] AS s RETURN left(s, 0), right(s, 0), substring(s, 1, 0)")
    q("F2_stored_sub0", f"{C} RETURN substring(n.s, 1, 0)")
    q("F2_neg", f"{C} RETURN left(n.s, -1)")
    # F3 slices with run-time negative bounds
    q("F3_rows", f"{C} UNWIND [[-3, -1], [-3, 5], [0, -1], [-2, 9], [1, -9], [-9, 2]] AS ab RETURN ab, n.l[ab[0]..ab[1]]")
    q("F3_rows_literal_list", "WITH [1, 2, 3, 4, 5] AS l UNWIND [[-3, -1], [0, -1], [-2, 9]] AS ab RETURN ab, l[ab[0]..ab[1]]")
    q("F3_params", f"{C} RETURN n.l[$a..$b], n.l[$c..], n.l[..$d]", {"a": 0, "b": -1, "c": -2, "d": -1})
    q("F3_params_literal_list", "WITH [1, 2, 3, 4, 5] AS l RETURN l[$a..$b], l[$c..]", {"a": 0, "b": -1, "c": -2})
    q("F3_literal", f"{C} RETURN n.l[0..-1], n.l[-2..], n.l[-3..5], n.l[1..-9]")
    q("F3_null_bound", f"{C} UNWIND [null] AS b RETURN n.l[1..b]")
    # F4 parse of identifier bounds
    q("F4_a_dotdot_3", "WITH [1, 2, 3] AS l, 1 AS a RETURN l[a..3]")
    q("F4_a_dotdot_b", "WITH [1, 2, 3] AS l, 1 AS a, 3 AS b RETURN l[a..b]")
    q("F4_1_dotdot_b", "WITH [1, 2, 3] AS l, 3 AS b RETURN l[1..b]")
    q("F4_a_dotdot", "WITH [1, 2, 3] AS l, 1 AS a RETURN l[a..]")
    q("F4_a_space", "WITH [1, 2, 3] AS l, 1 AS a RETURN l[a .. 3]")
    # F5 coalesce types
    q("F5_lit", "RETURN coalesce(null, 1), coalesce(null, 1, 'z'), coalesce(null, 2.5, 'z'), coalesce(null, true, 'z'), coalesce('a', 1)")
    q("F5_stored_mixed", f"{C} RETURN coalesce(n.missing, 1, 'z'), coalesce(n.missing, n.s, 1), coalesce(n.missing, n.l)")
    q("F5_rows", "UNWIND [null, 7] AS x RETURN x, coalesce(x, 1, 'z'), coalesce(x, 'z')")
    # F6 CASE WHEN over a run-time boolean
    q("F6_unwind", "UNWIND [true, false] AS f RETURN f, CASE WHEN f THEN 'y' ELSE 'n' END")
    q("F6_with", "WITH true AS f RETURN CASE WHEN f THEN 'y' ELSE 'n' END")
    q("F6_param", "RETURN CASE WHEN $f THEN 'y' ELSE 'n' END", {"f": True})
    q("F6_eq_workaround", "UNWIND [true, false] AS f RETURN f, CASE WHEN f = true THEN 'y' ELSE 'n' END")
    q("F6_where", "UNWIND [true, false] AS f WITH f WHERE f RETURN f")
    q("F6_not", "UNWIND [true, false] AS f RETURN f, NOT f, f AND true")
    q("F6_literal", "RETURN CASE WHEN true THEN 'y' ELSE 'n' END")
    q("F6_simple_case_bool", "UNWIND [true, false] AS f RETURN CASE f WHEN true THEN 'y' ELSE 'n' END")
    # F7 functions inside CREATE maps (each on a fresh node); read back
    shapes = {"toUpper_lit": "toUpper('ab')", "size_lit": "size('ab')", "abs_lit": "abs(-1)",
              "toString_lit": "toString(1)", "toInteger_lit": "toInteger('5')", "arith": "1 + 1",
              "concat": "'a' + 'b'", "list": "[1, 2]", "coalesce_lit": "coalesce(null, 'x')",
              "uuid": "randomUUID()", "rand": "rand()", "param_fn": "toUpper($s)", "param": "$s"}
    for i, (k, expr) in enumerate(shapes.items()):
        q(f"F7_create_{k}", f"CREATE (:{L}C {{id: '{p}c{i}', v: {expr}}})", {"s": "ab"})
        q(f"F7_read_{k}", f"MATCH (n:{L}C {{id: '{p}c{i}'}}) RETURN n.v")
    q("F7_unwind_fn", f"UNWIND ['ab'] AS s CREATE (:{L}D {{id: '{p}d1', v: toUpper(s)}})")
    q("F7_unwind_read", f"MATCH (n:{L}D) RETURN n.id, n.v")
    q("F7_create_then_set", f"CREATE (n:{L}E {{id: '{p}e1'}}) SET n.v = toUpper('ab'), n.u = randomUUID()")
    q("F7_create_then_set_read", f"MATCH (n:{L}E) RETURN n.id, n.v, size(n.u)")
    q("F7_rel_fn", f"CREATE (:{L}H {{id: '{p}h1'}})-[:R{TAG} {{v: toUpper('ab')}}]->(:{L}H {{id: '{p}h2'}})")
    q("F7_rel_read", f"MATCH (:{L}H)-[r:R{TAG}]->() RETURN r.v")
    q("F7_set_map", f"MATCH (n:{L} {{id: '{p}c'}}) SET n += {{u: toUpper('ab')}}")
    q("F7_set_map_read", f"MATCH (n:{L} {{id: '{p}c'}}) RETURN n.u")
    c.close()
    dest = HERE / f"cypherexpr-observed2-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(dest)


if __name__ == "__main__":
    main()
