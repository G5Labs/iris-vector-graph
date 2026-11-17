"""Iteration 50: fresh fixture reproduction of review 47-49's items on ivg-cont-20261117-iris (prefix i50_<HHMMSS>_).

Runs each case through IRISGraphEngine.execute_cypher (default engine, as a caller would use it) and, for the
PPR-guided subgraph, kg_PPR_GUIDED_SUBGRAPH on a fresh star graph. Writes review-repro-<run>.json beside this file.
    cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-50/review_repro.py
"""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); T = RUN[9:15]
P, L = f"i50_{T}_", f"I50{T}"


def main():
    c = runtime.connect()
    from iris_vector_graph.engine import IRISGraphEngine
    e = IRISGraphEngine(c, embedding_dimension=768)
    out = {"run": RUN, "prefix": P, "fixture": runtime.NAME, "product": runtime.PRODUCT, "cases": {}}

    def case(item, k, q, params=None):
        try:
            r = e.execute_cypher(q, params or {})
            rows = getattr(r, "rows", None)
            res = {"rows": [list(x) for x in rows] if rows is not None else None,
                   "error": str(r.error) if getattr(r, "error", None) else None}
        except Exception as x:
            res = {"exception": f"{type(x).__name__}: {str(x)[:300]}"}
        out["cases"][k] = {"item": item, "q": q, "params": params, **res}

    case("setup", "setup", f"CREATE (n:{L} {{id: '{P}c', l: [1, 2, 3], num: 5, s1: '1', i1: 1, a: 2, k: 'gotcha'}})")
    C = f"MATCH (n:{L} {{id: '{P}c'}})"
    # item 2 (bug-cyp-111): list source decides; WITH-literal list with a run-time index answers typed
    case("2", "idx_with_literal_row_neg", "WITH [1, 2, 3] AS l UNWIND [-1] AS i RETURN l[i]")
    case("2", "idx_with_literal_row_nonneg", "WITH [1, 2, 3] AS l UNWIND [0, 2, 5] AS i RETURN i, l[i]")
    case("2", "idx_with_literal_param_neg", "WITH [1, 2, 3] AS l RETURN l[$i]", {"i": -1})
    case("2", "idx_prop_row_neg", f"{C} UNWIND [-1] AS i RETURN n.l[i]")
    case("2", "idx_prop_row_nonneg", f"{C} UNWIND [0] AS i RETURN n.l[i]")
    case("2", "idx_with_prop_row_neg", f"{C} WITH n.l AS l UNWIND [-1] AS i RETURN l[i]")
    case("2", "idx_with_prop_row_nonneg", f"{C} WITH n.l AS l UNWIND [1] AS i RETURN l[i]")
    # item 3 (bug-cyp-112): reverse's argument forms
    case("3", "rev_prop", f"{C} RETURN reverse(n.l)")
    case("3", "rev_with_prop", f"{C} WITH n.l AS l RETURN reverse(l)")
    case("3", "rev_with_literal", "WITH [1, 2, 3] AS l RETURN reverse(l)")
    case("3", "rev_slice", "WITH [1, 2, 3] AS l RETURN reverse(l[0..2])")
    case("3", "rev_coalesce", f"{C} RETURN reverse(coalesce(n.l, []))")
    case("3", "rev_nested_subscript", "WITH [[1, 2], [3, 4]] AS l RETURN reverse(l[0])")
    case("3", "rev_literal", "RETURN reverse([1, 2, 3])")
    case("3", "rev_string_prop", f"{C} RETURN reverse(n.k)")
    case("3", "rev_tail_prop", f"{C} RETURN reverse(tail(n.l))")
    # item 5 (bug-cyp-120): a parameter on a relationship CREATE between new nodes
    case("5", "rel_new_param", f"CREATE (a:{L}Q {{id: '{P}q1'}})-[r:Q{T} {{k: $k, lit: 1}}]->(b:{L}Q {{id: '{P}q2'}})", {"k": 4})
    case("5", "rel_new_param_read", f"MATCH (a {{id: '{P}q1'}})-[r:Q{T}]->(b) RETURN r.k, r.lit, keys(r)")
    case("5", "rel_matched_param", f"MATCH (a {{id: '{P}q1'}}), (b {{id: '{P}q2'}}) CREATE (a)-[r:M{T} {{k: $k}}]->(b)", {"k": 9})
    case("5", "rel_matched_param_read", f"MATCH (a {{id: '{P}q1'}})-[r:M{T}]->(b) RETURN r.k")
    case("5", "node_param", f"CREATE (n:{L}N {{id: '{P}np', k: $k}})", {"k": 4})
    case("5", "node_param_read", f"MATCH (n {{id: '{P}np'}}) RETURN n.k")
    # item 6: a null run-time index
    case("6", "idx_null_row_with_literal", "WITH [1, 2, 3] AS l UNWIND [null] AS i RETURN l[i]")
    case("6", "idx_null_literal_prop", f"{C} RETURN n.l[null]")
    case("6", "idx_null_missing_prop", f"{C} RETURN n.l[n.nope]")
    case("6", "idx_null_param", "WITH [1, 2, 3] AS l RETURN l[$i]", {"i": None})
    case("6", "idx_null_literal_list", "RETURN [1, 2, 3][null]")
    case("6", "idx_null_row_prop", f"{C} UNWIND [null] AS i RETURN n.l[i]")
    # item 7: simple CASE coercion
    case("7", "case_simple_prop_str_vs_int", f"{C} RETURN CASE n.s1 WHEN 1 THEN 'num' WHEN '1' THEN 'str' ELSE 'other' END")
    case("7", "case_simple_row_str_vs_int", "UNWIND ['1'] AS s RETURN CASE s WHEN 1 THEN 'num' ELSE 'other' END")
    case("7", "case_simple_int_prop_vs_str", f"{C} RETURN CASE n.i1 WHEN '1' THEN 'str' WHEN 1 THEN 'num' ELSE 'other' END")
    case("7", "eq_prop_str_vs_int", f"{C} RETURN n.s1 = 1, CASE WHEN n.s1 = 1 THEN 'num' ELSE 'other' END")
    case("7", "case_simple_same_type", f"{C} RETURN CASE n.i1 WHEN 1 THEN 'num' ELSE 'other' END, CASE n.s1 WHEN '1' THEN 'str' ELSE 'other' END")
    case("7", "where_prop_str_vs_int", f"{C} WHERE n.s1 = 1 RETURN n.id")
    # minor items
    case("m1", "null_list_slice", f"{C} RETURN n.missing[0..2]")
    case("m1", "null_list_index", f"{C} RETURN n.missing[0]")
    case("m2", "param_list_slice", "RETURN $l[$s..$e]", {"l": [1, 2, 3, 4], "s": 1, "e": 3})
    case("m2", "param_list_slice_open", "RETURN $l[$s..]", {"l": [1, 2, 3, 4], "s": 1})
    case("m2", "param_list_slice_literal_bounds", "RETURN $l[1..3]", {"l": [1, 2, 3, 4]})
    case("m2", "param_list_index", "RETURN $l[$s]", {"l": [1, 2, 3, 4], "s": 1})
    case("m2", "with_param_list_slice", "WITH $l AS l RETURN l[$s..$e]", {"l": [1, 2, 3, 4], "s": 1, "e": 3})
    case("m3", "set_list_from_props", f"{C} SET n.l2 = [n.a, 1] RETURN n.l2")
    case("m3", "set_list_literal", f"{C} SET n.l3 = [2, 1] RETURN n.l3")
    case("m4", "trim_tabs_newlines", "RETURN trim('\\t a \\n') AS t, size(trim('\\t a \\n')) AS n")
    case("m4", "trim_spaces", "RETURN trim('  a  ') AS t, size(trim('  a  ')) AS n")
    case("m5", "key_from_with_column", f"{C} WITH n, 'num' AS k RETURN n[k]")
    case("m5", "key_from_param", f"{C} RETURN n[$k]", {"k": "num"})
    case("m6", "range_fractional_step_literal", "RETURN range(1, 3, 1.5)")
    case("m6", "range_fractional_step_row", "UNWIND [1.5] AS s RETURN range(1, 3, s)")
    case("m10", "rel_retype_setup", f"CREATE (a:{L}R {{id: '{P}r1'}})-[r:R{T} {{age: '30'}}]->(b:{L}R {{id: '{P}r2'}})")
    case("m10", "rel_retype", f"MATCH (a {{id: '{P}r1'}})-[r:R{T}]->(b) SET r.age = toInteger(r.age)")
    case("m10", "rel_retype_read", f"MATCH (a {{id: '{P}r1'}})-[r:R{T}]->(b) RETURN r.age")
    case("m10", "node_retype", f"{C} SET n.s1 = toInteger(n.s1) RETURN n.s1")

    # item 1 (bug-plt-113): the PPR-guided subgraph on a star s -> a1..a6 plus a1 -> a2
    ids = {k: P + k for k in ["s", "a1", "a2", "a3", "a4", "a5", "a6"]}
    for v in ids.values():
        e.create_node(v, labels=[L + "G"])
    for k in ["a1", "a2", "a3", "a4", "a5", "a6"]:
        e.create_edge(ids["s"], "LINK", ids[k])
    e.create_edge(ids["a1"], "LINK", ids["a2"])
    sh = lambda x: str(x).replace(P, "")
    def node_id(n):
        return n if isinstance(n, str) else (n.get("id") if isinstance(n, dict) else str(n))
    sub = {}
    for seeds, top, mx in [(["s"], 3, 5000), (["s"], 7, 5000), (["s"], 50, 5000), (["s", "a3", "a4"], 1, 5000),
                           (["s"], 50, 3), (["a3", "a4", "a5"], 1, 5000)]:
        r = e.kg_PPR_GUIDED_SUBGRAPH([ids[x] for x in seeds], ppr_top_k=top, max_nodes=mx)
        sub[f"guided_{'+'.join(seeds)}_top{top}_max{mx}"] = {
            "nodes": sorted(sh(node_id(n)) for n in r.nodes),
            "edges": sorted(f"{sh(x['src'])}>{sh(x['dst'])}" for x in r.edges),
            "top_ids": [sh(k) for k, _ in r.ppr_scores]}
    for seeds, mx, hops in [(["s"], 3, 1), (["s"], 10000, 1), (["a1", "a2", "s"], 3, 1)]:
        r = e.kg_SUBGRAPH([ids[x] for x in seeds], k_hops=hops, max_nodes=mx)
        sub[f"subgraph_{'+'.join(seeds)}_max{mx}_hops{hops}"] = {
            "nodes": sorted(sh(node_id(n)) for n in r.nodes),
            "edges": sorted(f"{sh(x[0])}>{sh(x[2])}" if isinstance(x, (list, tuple)) else sh(x) for x in r.edges)}
    out["subgraph"] = sub
    out["arno_loaded"] = bool(getattr(e, "_arno_available", None) and e._arno_available) if hasattr(e, "_arno_available") else "attribute absent"
    c.close()
    p = HERE / f"review-repro-{RUN}.json"
    p.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(p)


if __name__ == "__main__":
    main()
