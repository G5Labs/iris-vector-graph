"""Iteration 50 follow-up probe for review 47-49 minors m4, m6, m10 and m3 neighbors (prefix i50b_<HHMMSS>_).
    cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-50/review_repro2.py
"""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); T = RUN[9:15]
P, L = f"i50b_{T}_", f"I50B{T}"


def main():
    c = runtime.connect()
    from iris_vector_graph.engine import IRISGraphEngine
    e = IRISGraphEngine(c, embedding_dimension=768)
    out = {"run": RUN, "prefix": P, "fixture": runtime.NAME, "product": runtime.PRODUCT, "cases": {}}

    def case(item, k, q, params=None):
        try:
            r = e.execute_cypher(q, params or {})
            res = {"rows": [list(x) for x in r.rows], "error": str(r.error) if getattr(r, "error", None) else None}
        except Exception as x:
            res = {"exception": f"{type(x).__name__}: {str(x)[:300]}"}
        out["cases"][k] = {"item": item, "q": q, "params": params, **res}

    case("setup", "setup", f"CREATE (n:{L} {{id: '{P}c', a: 2, s: '\\t a \\n'}})")
    C = f"MATCH (n:{L} {{id: '{P}c'}})"
    # m4: trim family in RETURN (SQL TRIM) versus a node CREATE (folded in Python)
    case("m4", "return_trim_literal", "RETURN trim('\\t a \\n') AS t")
    case("m4", "return_ltrim_rtrim_literal", "RETURN ltrim('\\t a') AS l, rtrim('a \\n') AS r")
    case("m4", "return_trim_property", f"{C} RETURN trim(n.s) AS t")
    case("m4", "return_trim_spaces", "RETURN trim('  a  ') AS t")
    case("m4", "create_trim", f"CREATE (:{L}T {{id: '{P}t', t: trim('\\t a \\n')}})")
    case("m4", "create_trim_read", f"MATCH (x {{id: '{P}t'}}) RETURN x.t")
    case("m4", "set_trim", f"{C} SET n.t2 = trim('\\t a \\n') RETURN n.t2")
    # m6: range with a non-integer step / bound
    case("m6", "range_frac_step_literal", "RETURN range(1, 3, 1.5)")
    case("m6", "range_frac_step_row", "UNWIND [1.5] AS s RETURN range(1, 3, s)")
    case("m6", "range_frac_step_param", "RETURN range(1, 3, $s)", {"s": 1.5})
    case("m6", "range_frac_end_row", "UNWIND [3.5] AS x RETURN range(1, x)")
    case("m6", "range_int_step_row", "UNWIND [2] AS s RETURN range(1, 5, s)")
    # m3: SET of a list literal by element kind
    case("m3", "set_list_property_elem", f"{C} SET n.l1 = [n.a, 1] RETURN n.l1")
    case("m3", "set_list_row_elem", f"{C} UNWIND [5] AS x SET n.l2 = [x, 1] RETURN n.l2")
    case("m3", "set_list_param_elem", f"{C} SET n.l3 = [$x, 1] RETURN n.l3", {"x": 5})
    case("m3", "set_list_arith_elem", f"{C} SET n.l4 = [1 + 1, 1] RETURN n.l4")
    case("m3", "create_list_property_elem", f"{C} CREATE (:{L}L {{id: '{P}l', l: [n.a, 1]}})")
    case("m3", "after_refusal_read", f"{C} RETURN n.l1")
    # m10: relationship SET from its own property, by expression
    case("m10", "rel_setup", f"CREATE (a:{L}R {{id: '{P}r1'}})-[r:R{T} {{age: '30', n: 1}}]->(b:{L}R {{id: '{P}r2'}})")
    case("m10", "rel_set_toInteger_own", f"MATCH (a {{id: '{P}r1'}})-[r:R{T}]->(b) SET r.age = toInteger(r.age)")
    case("m10", "rel_set_arith_own", f"MATCH (a {{id: '{P}r1'}})-[r:R{T}]->(b) SET r.n = r.n + 1")
    case("m10", "rel_set_toString_own", f"MATCH (a {{id: '{P}r1'}})-[r:R{T}]->(b) SET r.n = toString(r.n)")
    case("m10", "rel_read", f"MATCH (a {{id: '{P}r1'}})-[r:R{T}]->(b) RETURN r.age, r.n")
    c.close()
    p = HERE / f"review-repro2-{RUN}.json"
    p.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(p)


if __name__ == "__main__":
    main()
