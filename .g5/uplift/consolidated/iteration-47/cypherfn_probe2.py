"""W54 follow-up after the source reading (not frozen): isolate the run-time index values, the node subscript by a row
variable, randomUUID()/rand() in a CREATE, and the native gate. Run-isolated continuation fixture; ordinary data."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402
RUN = os.environ.get("W54_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    from iris_vector_graph.cypher import native_plan
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    p, L = f"i47b_{TAG}_", f"I47G{TAG}"
    out = {"run": RUN, "fixture": runtime.NAME, "prefix": p, "cases": {}}
    try:
        out["native_gate"] = str(native_plan.native_gate(e))
    except Exception as x:
        out["native_gate"] = f"{type(x).__name__}: {x}"

    def q(k, text, params=None):
        params = params or {}
        cell = {"query": text, "params": params}
        try:
            nat = e._try_native(parse_query(text), params)
            cell["native_routed"] = nat is not None
        except Exception as x:
            cell["native_routed"] = f"{type(x).__name__}: {str(x)[:200]}"
        try:
            r = e._execute_parsed_sql(parse_query(text), params, None)
            cell["rows"] = [list(x) for x in r.rows]; cell["error"] = (str(r.error)[-260:] if r.error else None)
        except Exception as x:
            cell["exception"] = f"{type(x).__name__}: {str(x)[:300]}"
        out["cases"][k] = cell

    e.execute_cypher(f"CREATE (n:{L} {{id: '{p}c', l: [1, 2, 3], k: 'gotcha', num: 5, str: 'abc'}})")
    C = f"MATCH (n:{L} {{id: '{p}c'}})"
    for i in (0, 2, 3, -1, -3, -4):
        q(f"I_row_{i}", f"{C} UNWIND [{i}] AS i RETURN n.l[i]")
    q("I_param_neg", f"{C} RETURN n.l[$i]", {"i": -1})
    q("I_with_list_neg", f"{C} WITH n.l AS l UNWIND [-1] AS i RETURN l[i]")
    q("N_row_key", f"{C} UNWIND ['num', 'str', 'zz'] AS k RETURN k, n[k]")
    q("N_param_key", f"{C} RETURN n[$k]", {"k": "num"})
    q("N_with_key", f"{C} WITH n, 'str' AS k RETURN n[k]")
    q("R_return", "UNWIND [1, 2, 3] AS i RETURN i, randomUUID() AS u, rand() AS r")
    for k, text in (("R_create_both", f"UNWIND [1, 2, 3] AS i CREATE (:{L}U {{i: i, u: randomUUID(), r: rand()}})"),
                    ("R_create_uuid", f"UNWIND [1, 2, 3] AS i CREATE (:{L}V {{i: i, u: randomUUID()}})"),
                    ("R_create_rand", f"UNWIND [1, 2, 3] AS i CREATE (:{L}W {{i: i, r: rand()}})")):
        try:
            r = e.execute_cypher(text); out["cases"][k] = {"query": text, "error": str(r.error)[-260:] if r.error else None}
        except Exception as x:
            out["cases"][k] = {"query": text, "exception": f"{type(x).__name__}: {str(x)[:300]}"}
    q("R_created_uuid", f"MATCH (x:{L}V) RETURN x.i, x.u ORDER BY x.i")
    q("R_created_rand", f"MATCH (x:{L}W) RETURN x.i, x.r ORDER BY x.i")
    q("R_created", f"MATCH (x:{L}U) RETURN x.i, x.u, x.r ORDER BY x.i")
    q("R_collect", "UNWIND range(1, 50) AS i WITH randomUUID() AS u RETURN count(DISTINCT u)")
    q("V_reverse_with", f"{C} WITH n.l AS l RETURN reverse(l)")
    q("V_reverse_str", f"{C} RETURN reverse(n.str)")
    q("V_reverse_tail", f"{C} RETURN reverse(tail(n.l))")
    q("M_rows_types", "WITH {a: 1, b: 2.5, c: true, d: [1]} AS m UNWIND ['a', 'b', 'c', 'd'] AS k RETURN k, m[k]")
    q("M_literal_key", "WITH {a: 1, c: true} AS m RETURN m['a'], m.c")
    q("T_head_number_msg", f"{C} RETURN head(n.num)")
    q("T_head_number_literal", "RETURN head(5)")
    c.close()
    dest = HERE / f"cypherfn-observed2-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n"); print(dest)


if __name__ == "__main__":
    main()
