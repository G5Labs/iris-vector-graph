"""W54: Cypher built-in functions over values known only at run time (run-isolated continuation fixture; ordinary data).

Each query runs on both of the product's own entry points used by execute_cypher: the native executor
(engine._try_native; None when it does not accept the shape) and the SQL path (engine._execute_parsed_sql).
The frozen predictions are in cypherfn-PAIRS.md."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W54_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def res(r):
    if r is None:
        return None
    err = getattr(r, "error", None)
    return {"rows": [list(x) for x in r.rows], "error": str(err)[:400] if err else None}


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    p, L = f"i47_{TAG}_", f"I47F{TAG}"
    out = {"run": RUN, "fixture": runtime.NAME, "prefix": p, "label": L, "cases": {}}

    def both(q, params=None):
        params = params or {}
        cell = {"query": q, "params": params}
        try:
            nat = e._try_native(parse_query(q), params)
            cell["native"] = res(nat[1]) if nat is not None else None
        except Exception as x:
            cell["native"] = {"exception": f"{type(x).__name__}: {str(x)[:300]}"}
        try:
            cell["sql"] = res(e._execute_parsed_sql(parse_query(q), params, None))
        except Exception as x:
            cell["sql"] = {"exception": f"{type(x).__name__}: {str(x)[:300]}"}
        return cell

    def case(k, q, params=None):
        try:
            out["cases"][k] = both(q, params)
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:300]

    # Data: Cypher-written lists and strings; a Python-written twin; keys; percentiles.
    e.execute_cypher(f"CREATE (n:{L} {{id: '{p}c', l: [1, 2, 3], e: [], s: 'a,b,,c', z: '', num: 5, "
                     f"t: [1, 'a', 2.5, true], str: 'abc'}})")
    e.create_node(p + "py", labels=[L], properties={"t": [1, "a", 2.5, True], "l": [1, 2, 3], "e": []})
    e.create_node(p + "k", labels=[L + "K"], properties={"a": 1, "b": 2})
    e.create_node(p + "k2", labels=[L + "K"])
    e.create_edge(p + "k", f"R{TAG}", p + "k2", qualifiers={"x": 1})
    for i, v in enumerate([10, 20, 30, 40]):
        e.create_node(f"{p}v{i}", labels=[L + "P"], properties={"v": v})
    for i, v in enumerate([10, None, 30]):
        e.create_node(f"{p}q{i}", labels=[L + "Q"], properties={} if v is None else {"v": v})

    C = f"MATCH (n:{L} {{id: '{p}c'}})"
    PY = f"MATCH (n:{L} {{id: '{p}py'}})"
    # L1
    case("L1_list", f"{C} RETURN head(n.l), last(n.l), tail(n.l), reverse(n.l)")
    case("L1_empty", f"{C} RETURN head(n.e), last(n.e), tail(n.e), reverse(n.e)")
    case("L1_literal_neighbor", "WITH [1, 2, 3] AS l, [] AS e RETURN head(l), last(l), tail(l), reverse(l), head(e), last(e), tail(e), reverse(e)")
    # L2
    case("L2_index_rows", f"{C} UNWIND [0, -1, 2, 3, -4] AS i RETURN i, n.l[i]")
    case("L2_index_const", f"{C} RETURN n.l[0], n.l[-1], n.l[3], n.l[-4]")
    case("L2_python_list", f"{PY} UNWIND [0, -1, 3, -4] AS i RETURN i, n.l[i]")
    # L3
    case("L3_cypher_written", f"{C} RETURN head(n.t), last(n.t), n.t[1], n.t[2]")
    case("L3_python_written", f"{PY} RETURN head(n.t), last(n.t), n.t[1], n.t[2]")
    # L4
    case("L4_range_rows", "UNWIND [2, -1] AS s RETURN s, range(1, 5, s)")
    case("L4_range_down", "UNWIND [-2] AS s RETURN range(5, 1, s)")
    case("L4_range_param", "RETURN range(1, 5, $s), range(5, 1, $d)", {"s": 2, "d": -2})
    case("L4_range_zero_rows", "UNWIND [0] AS s RETURN range(1, 3, s)")
    # L5
    case("L5_split", f"{C} RETURN split(n.s, ','), split(n.z, ','), split(n.missing, ',')")
    case("L5_split_literal", "RETURN split('a,b,,c', ','), split('', ',')")
    case("L5_split_empty_delim", f"{C} RETURN split(n.str, '')")
    # L6
    case("L6_keys_node", f"MATCH (n:{L}K {{id: '{p}k'}}) RETURN keys(n)")
    case("L6_keys_rel", f"MATCH (a {{id: '{p}k'}})-[r:R{TAG}]->(b) RETURN keys(r)")
    case("L6_keys_map", f"{C} WITH {{a: 1, b: n.missing}} AS m RETURN keys(m)")
    case("L6_keys_map_literal", "RETURN keys({a: 1, b: null})")
    # L7
    case("L7_map_get_rows", "WITH {a: 1, b: 'x'} AS m UNWIND ['a', 'b', 'zz'] AS k RETURN k, m[k]")
    case("L7_map_get_param", "WITH $m AS m RETURN m[$k], m[$z]", {"m": {"a": 1, "b": "x"}, "k": "b", "z": "zz"})
    case("L7_node_get_rows", f"{C} UNWIND ['num', 'str', 'zz'] AS k RETURN k, n[k]")
    # L8
    case("L8_regex", f"{C} RETURN n.str =~ 'a.c', n.str =~ 'b', n.missing =~ 'a'")
    case("L8_regex_param", f"{C} RETURN n.str =~ $p1, n.str =~ $p2", {"p1": "a.c", "p2": "b"})
    case("L8_regex_rows", "UNWIND ['abc', 'b', ''] AS s RETURN s, s =~ 'b', s =~ '.*'")
    # L9
    case("L9_pct4", f"MATCH (n:{L}P) RETURN percentileDisc(n.v, 0.5), percentileCont(n.v, 0.5)")
    case("L9_pct_empty", f"MATCH (n:{L}None) RETURN percentileDisc(n.v, 0.5), percentileCont(n.v, 0.5)")
    case("L9_pct_nulls", f"MATCH (n:{L}Q) RETURN percentileDisc(n.v, 0.5), percentileCont(n.v, 0.5)")
    case("L9_pct_quartiles", f"MATCH (n:{L}P) RETURN percentileDisc(n.v, 0.25), percentileDisc(n.v, 0.75), percentileCont(n.v, 0.25)")
    case("L9_pct_unwind", "UNWIND [10, 20, 30, 40] AS x RETURN percentileDisc(x, 0.5), percentileCont(x, 0.5)")
    # L10
    case("L10_pct_bad_param", f"MATCH (n:{L}Q) RETURN percentileCont(n.v, $p)", {"p": 1.5})
    case("L10_pct_good_param", f"MATCH (n:{L}Q) RETURN percentileCont(n.v, $p)", {"p": 0.5})
    case("L10_pct_bad_disc", f"MATCH (n:{L}Q) RETURN percentileDisc(n.v, $p)", {"p": -1})
    # L11
    case("L11_head_number", f"{C} RETURN head(n.num)")
    case("L11_index_number", f"{C} RETURN n.num[0]")
    case("L11_head_list", f"{C} RETURN head(n.l)")
    case("L11_head_string", f"{C} RETURN head(n.str)")
    # L12
    case("L12_ids", "UNWIND [1, 2, 3] AS i RETURN randomUUID(), rand()")
    c.close()
    dest = HERE / f"cypherfn-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(dest)


if __name__ == "__main__":
    main()
