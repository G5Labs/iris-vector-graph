"""W59 follow-up probe (after the first observation, before the deciding source was read): isolates grouping and
DISTINCT over mixed kinds, arithmetic over aggregates, typed values through UNION, relationships(p) comprehensions,
SKIP/LIMIT parameter kinds, a null whole node's cells, and the native executor's own answers (engine with
native_cypher=True) including adjacency after DETACH DELETE. Fresh tag; fixture ivg-cont-20261117-iris, USER."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i54b_{TAG}_"; A = f"I54B{TAG}"; G = f"I54BG{TAG}"; K = f"KB{TAG}"


def main():
    from iris_vector_graph.cypher.parser import parse_query
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = runtime.engine(c); en = IRISGraphEngine(c, embedding_dimension=768)
    out = {"run": RUN, "tag": TAG, "fixture": runtime.NAME, "product": runtime.PRODUCT}
    norm = lambda v: json.loads(json.dumps(v, default=repr))

    def q(key, text, params=None, native=True):
        params = params or {}
        rec = {"q": text, "params": params}
        try:
            r = e.execute_cypher(text, params)
            rec["sql"] = {"columns": list(getattr(r, "columns", []) or []), "rows": [list(x) for x in r.rows]}
            if getattr(r, "error", None):
                rec["sql"]["error"] = str(r.error)
        except Exception as x:
            rec["sql"] = {"error": f"{type(x).__name__}: {x}"[:400]}
        if native:
            try:
                nr = en._try_native(parse_query(text), params)
                rec["native"] = "declined" if nr is None else {"rows": [list(x) for x in nr[1].rows]}
            except Exception as x:
                rec["native"] = {"error": f"{type(x).__name__}: {x}"[:300]}
        out[key] = norm(rec)

    e.create_node(P + "a1", labels=[A], properties={"name": "a1", "v": 1, "s": "1", "f": 2.5, "b": True, "l": [1, 2]})
    e.create_node(P + "a2", labels=[A], properties={"name": "a2", "v": 2, "s": "x", "f": 1.0})
    e.create_node(P + "a3", labels=[A], properties={"name": "a3"})
    e.create_edge(P + "a1", K, P + "a2", qualifiers={"w": 1})
    e.create_edge(P + "a1", K, P + "a3", weight=2.5)
    e.create_edge(P + "a2", K, P + "a3")
    for i, k in enumerate([1, "1", 1.0, "1.0", True, "true", "01"]):
        e.create_node(f"{P}g{i}", labels=[G], properties={"k": k})

    # grouping and DISTINCT over mixed kinds
    for name, lst in (("int_str", "[1, '1']"), ("bool_str", "[true, 'true']"), ("int_float", "[1, 1.0]"),
                      ("int_bool", "[1, true]"), ("str_strfloat", "['1', '1.0']"), ("str_lead0", "['1', '01']"),
                      ("list_str", "[[1], '[1]']"), ("null_str", "[null, 'null']")):
        q(f"G_group_{name}", f"UNWIND {lst} AS k RETURN k, count(*) AS c")
        q(f"G_distinct_{name}", f"UNWIND {lst} AS k RETURN DISTINCT k")
        q(f"G_countd_{name}", f"UNWIND {lst} AS k RETURN count(DISTINCT k)")
        q(f"G_collectd_{name}", f"UNWIND {lst} AS k RETURN collect(DISTINCT k)")
        q(f"G_withd_{name}", f"UNWIND {lst} AS k WITH DISTINCT k RETURN count(*)")
    q("G_group_param", "UNWIND $xs AS k RETURN k, count(*) AS c", {"xs": [1, "1"]})
    q("G_api_group", f"MATCH (n:{G}) RETURN n.k AS k, count(*) AS c")
    q("G_api_distinct", f"MATCH (n:{G}) RETURN DISTINCT n.k AS k")
    q("G_api_countd", f"MATCH (n:{G}) RETURN count(DISTINCT n.k)")
    q("G_api_collectd", f"MATCH (n:{G}) RETURN collect(DISTINCT n.k)")
    q("G_api_withd", f"MATCH (n:{G}) WITH DISTINCT n.k AS k RETURN count(*)")
    q("G_api_eq", f"MATCH (n:{G}) WHERE n.k = 1 RETURN n.id ORDER BY n.id")
    q("G_api_group_label", f"MATCH (n:{G}) RETURN n.k AS k, collect(n.id) AS ids")

    # arithmetic over aggregates
    q("AR_int_plus_float_aggs", f"MATCH (n:{A}) WHERE n.v IS NOT NULL RETURN sum(n.v) + sum(n.f)")
    q("AR_float_plus_int_aggs", f"MATCH (n:{A}) WHERE n.v IS NOT NULL RETURN sum(n.f) + sum(n.v)")
    q("AR_int_agg_plus_half", f"MATCH (n:{A}) WHERE n.v IS NOT NULL RETURN sum(n.v) + 0.5")
    q("AR_count_plus_half", f"MATCH (n:{A}) RETURN count(*) + 0.5")
    q("AR_count_times_float", f"MATCH (n:{A}) RETURN count(*) * 1.5")
    q("AR_count_div", f"MATCH (n:{A}) RETURN count(*) / 2.0")
    q("AR_with_then", f"MATCH (n:{A}) WHERE n.v IS NOT NULL WITH sum(n.v) AS s RETURN s + 0.5")
    q("AR_literal", "RETURN 3 + 3.5")
    q("AR_unwind", "UNWIND [1, 2] AS x RETURN sum(x) + 0.5")
    q("AR_unwind_float", "UNWIND [1.5, 2] AS x RETURN sum(x) + 1")
    q("AR_max_plus", f"MATCH (n:{A}) WHERE n.v IS NOT NULL RETURN max(n.v) + 0.5, min(n.f) * 2")
    q("AR_avg_plus", f"MATCH (n:{A}) WHERE n.v IS NOT NULL RETURN avg(n.v) + 1")
    q("AR_rel", f"MATCH (a:{A} {{name: 'a1'}})-[r:{K}]->() RETURN sum(r.w) + sum(r.weight), sum(r.weight) + sum(r.w)")
    q("AR_grouped", f"MATCH (n:{A}) WHERE n.v IS NOT NULL RETURN n.name, sum(n.v) + 0.5 ORDER BY n.name")

    # UNION with typed values
    for col in ("v", "f", "b", "l", "s", "name"):
        q(f"U_prop_{col}", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n.{col} AS x UNION MATCH (n:{A} {{name: 'a1'}}) RETURN n.{col} AS x")
        q(f"U_all_prop_{col}", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n.{col} AS x UNION ALL RETURN 0 AS x")
    q("U_literals", "RETURN 1 AS x UNION RETURN 2.5 AS x UNION RETURN true AS x UNION RETURN [1] AS x")
    q("U_rel", f"MATCH (a:{A} {{name: 'a1'}})-[r:{K}]->() RETURN r.w AS x UNION ALL RETURN 0 AS x")
    q("U_no_union_prop_v", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n.v AS x")
    q("U_count", f"MATCH (n:{A}) RETURN count(n) AS x UNION ALL RETURN 0 AS x")
    q("U_node", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n AS x UNION ALL MATCH (n:{A} {{name: 'a2'}}) RETURN n AS x")
    q("U_dedup_int_vs_lit", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n.v AS x UNION RETURN 1 AS x")

    # relationships(p) in comprehensions
    for name, expr in (("type", "type(r)"), ("start", "startNode(r).name"), ("end", "endNode(r).name"), ("prop", "r.w"), ("r", "r")):
        q(f"R_var_{name}", f"MATCH p = (a:{A} {{name: 'a1'}})-[:{K}*1..2]->(c) RETURN length(p), [r IN relationships(p) | {expr}] ORDER BY length(p), c.name")
        q(f"R_fixed_{name}", f"MATCH p = (a:{A} {{name: 'a1'}})-[:{K}]->(c) RETURN [r IN relationships(p) | {expr}] ORDER BY c.name")
    q("R_var_size", f"MATCH p = (a:{A} {{name: 'a1'}})-[:{K}*1..2]->(c) RETURN length(p), size(relationships(p)) ORDER BY length(p), c.name")
    q("R_var_types_unwind", f"MATCH p = (a:{A} {{name: 'a1'}})-[:{K}*2]->(c) UNWIND relationships(p) AS r RETURN type(r)")

    # SKIP / LIMIT parameter kinds
    for kind, val in (("str", "2"), ("strneg", "-1"), ("bool", True), ("null", None), ("bigint", 2 ** 40), ("float_whole", 2.0)):
        q(f"L_limit_{kind}", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": val})
        q(f"L_skip_{kind}", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name SKIP $s", {"s": val})
    q("L_limit_expr", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT 1 + 1")
    q("L_limit_missing_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $nope")

    # a null whole node's cells, beside a found one
    q("N_null_node", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN a.name, b")
    q("N_found_node", f"MATCH (a:{A} {{name: 'a2'}}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN a.name, b")
    q("N_null_rel", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH (a)-[r:{K}]->(b) RETURN a.name, r")
    q("N_null_node_collect", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN collect(b)")
    q("N_null_node_props", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN properties(b), labels(b), keys(b)")

    # native answers on shapes it may accept
    q("NV_order_limit_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": 2})
    q("NV_order_limit_lit", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT 2")
    q("NV_skip_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name SKIP $s LIMIT $l", {"s": 1, "l": 1})
    q("NV_limit_neg", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": -1})
    q("NV_limit_float", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": 1.5})
    q("NV_limit_str", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": "2"})
    q("NV_distinct_hop", f"MATCH (a:{A} {{name: 'a1'}})-[:{K}]->(b) RETURN DISTINCT b.name ORDER BY b.name")
    q("NV_count_hop", f"MATCH (a:{A} {{name: 'a1'}})-[:{K}]->(b) RETURN count(*)")
    q("NV_group_api", f"MATCH (n:{G}) RETURN n.k AS k, count(*) AS c")
    q("NV_distinct_api", f"MATCH (n:{G}) RETURN DISTINCT n.k AS k")
    q("NV_countd_api", f"MATCH (n:{G}) RETURN count(DISTINCT n.k)")
    q("NV_hop_from_id", f"MATCH (a {{node_id: '{P}a1'}})-[:{K}]->(b) RETURN b.name ORDER BY b.name")
    # DETACH DELETE then adjacency readers (native walks ^KG)
    q("D_detach_a3", f"MATCH (n:{A} {{id: '{P}a3'}}) DETACH DELETE n", native=False)
    q("D_after_native_a1", f"MATCH (a {{node_id: '{P}a1'}})-[:{K}]->(b) RETURN b.name ORDER BY b.name")
    q("D_after_native_a2", f"MATCH (a {{node_id: '{P}a2'}})-[:{K}]->(b) RETURN count(*)")
    q("D_delete_r", f"MATCH (:{A} {{id: '{P}a1'}})-[r:{K}]->(:{A} {{id: '{P}a2'}}) DELETE r", native=False)
    q("D_after_native_r", f"MATCH (a {{node_id: '{P}a1'}})-[:{K}]->(b) RETURN count(*)")
    try:
        out["D_kg_neighbors_a1"] = norm(e.get_neighbors(P + "a1") if hasattr(e, "get_neighbors") else "n/a")
    except Exception as x:
        out["D_kg_neighbors_a1"] = f"{type(x).__name__}: {x}"[:200]
    c.close()
    d = HERE / f"clauses-observed2-{RUN}.json"
    d.write_text(json.dumps(out, indent=1, default=repr) + "\n")
    print(d)


if __name__ == "__main__":
    main()
