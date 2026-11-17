"""W59 raw probe: Cypher clauses over API-written data, default (single-edge) mode and parameters, on the run-isolated
fixture ivg-cont-20261117-iris (USER, fresh tag). Reads: execute_cypher on the SQL path (native_cypher=False) and the
native executor's own answer via _try_native where it accepts the shape. Writes: execute_cypher, then a later MATCH,
get_node() and edge counts. Rows of the frozen PAIRS file are keyed by their IDs."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i54_{TAG}_"; A = f"I54A{TAG}"; C = f"I54C{TAG}"; G = f"I54G{TAG}"; K = f"K{TAG}"; KC = f"KC{TAG}"
NG = f"i54g{TAG}"; MG = f"i54m{TAG}"


def main():
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "tag": TAG, "fixture": runtime.NAME, "product": runtime.PRODUCT}

    def norm(v):
        return json.loads(json.dumps(v, default=repr))

    def q(key, text, params=None, native=True):
        params = params or {}
        rec = {"q": text, "params": params}
        try:
            r = e.execute_cypher(text, params)
            err = getattr(r, "error", None)
            rec["sql"] = {"columns": list(getattr(r, "columns", []) or []), "rows": [list(x) for x in r.rows]}
            if err:
                rec["sql"]["error"] = str(err)
        except Exception as x:
            rec["sql"] = {"error": f"{type(x).__name__}: {x}"[:400]}
        if native:
            try:
                nr = e._try_native(parse_query(text), params)
                rec["native"] = "declined" if nr is None else {"rows": [list(x) for x in nr.rows]}
            except Exception as x:
                rec["native"] = {"error": f"{type(x).__name__}: {x}"[:300]}
        out[key] = norm(rec)
        return rec

    # ---- fixture: API-written default graph
    e.create_node(P + "a1", labels=[A], properties={"name": "a1", "v": 1, "s": "1", "f": 2.5, "b": True, "l": [1, 2], "m": {"k": 1}})
    e.create_node(P + "a2", labels=[A], properties={"name": "a2", "v": 2, "s": "x", "f": 1.0, "l": [3]})
    e.create_node(P + "a3", labels=[A], properties={"name": "a3"})
    e.create_node(P + "d1", labels=[A], properties={"name": "dup"})
    e.create_node(P + "d2", labels=[A], properties={"name": "dup"})
    e.create_edge(P + "a1", K, P + "a2", qualifiers={"w": 1})
    e.create_edge(P + "a1", K, P + "a3", weight=2.5)
    e.create_edge(P + "a2", K, P + "a3")
    # Cypher-written twin
    e.execute_cypher(f"CREATE (:{C} {{id: '{P}c1', name: 'a1', v: 1, s: '1', f: 2.5, b: true, l: [1, 2]}}), "
                     f"(:{C} {{id: '{P}c2', name: 'a2', v: 2, s: 'x', f: 1.0, l: [3]}}), (:{C} {{id: '{P}c3', name: 'a3'}})")
    e.execute_cypher(f"MATCH (a:{C} {{id: '{P}c1'}}), (b:{C} {{id: '{P}c2'}}) CREATE (a)-[:{KC} {{w: 1}}]->(b)")
    e.execute_cypher(f"MATCH (a:{C} {{id: '{P}c1'}}), (b:{C} {{id: '{P}c3'}}) CREATE (a)-[:{KC} {{weight: 2.5}}]->(b)")
    e.execute_cypher(f"MATCH (a:{C} {{id: '{P}c2'}}), (b:{C} {{id: '{P}c3'}}) CREATE (a)-[:{KC}]->(b)")
    # grouping data (API) and twin (Cypher)
    for i, k in enumerate([1, 1, "1", 1.5]):
        e.create_node(f"{P}g{i}", labels=[G], properties={"k": k})
    for i, k in enumerate(["1", "'1'", "1", "1.5"]):
        pass
    e.execute_cypher(f"CREATE (:{G}C {{id: '{P}t0', k: 1}}), (:{G}C {{id: '{P}t1', k: 1}}), (:{G}C {{id: '{P}t2', k: '1'}}), (:{G}C {{id: '{P}t3', k: 1.5}})")
    for i, k in enumerate([1, "1", True, "true"]):
        e.create_node(f"{P}h{i}", labels=[G + "D"], properties={"k": k})
    # named graph and multigraph graph
    e.create_node(P + "gx", labels=[A + "N"], properties={"name": "gx"}, graph=NG)
    e.create_node(P + "gy", labels=[A + "N"], properties={"name": "gy"}, graph=NG)
    e.create_edge(P + "gx", K, P + "gy", graph=NG)
    e.create_node(P + "gx", labels=[A + "N"], properties={"name": "gx-default"})  # same id in the default graph
    e.create_edge(P + "gx", K, P + "a1")
    e.set_multigraph(MG, True)
    out["mg_create_1"] = e.create_edge(P + "mx", K, P + "my", qualifiers={"n": 1}, graph=MG)
    out["mg_create_2"] = e.create_edge(P + "mx", K, P + "my", qualifiers={"n": 2}, graph=MG)
    # default graph: create_edge twice on one pair
    e.create_node(P + "sx", labels=[A + "S"]); e.create_node(P + "sy", labels=[A + "S"])
    out["single_create_1"] = e.create_edge(P + "sx", K, P + "sy", qualifiers={"n": 1})
    out["single_create_2"] = e.create_edge(P + "sx", K, P + "sy", qualifiers={"n": 2})

    # ---- OPTIONAL MATCH
    q("OM1_a3", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH (a)-[r:{K}]->(b) RETURN a.name, b.name, r IS NULL")
    q("OM1_a1", f"MATCH (a:{A} {{name: 'a1'}}) OPTIONAL MATCH (a)-[r:{K}]->(b) RETURN a.name, b.name, r IS NULL ORDER BY b.name")
    q("OM1_twin_c3", f"MATCH (a:{C} {{name: 'a3'}}) OPTIONAL MATCH (a)-[r:{KC}]->(b) RETURN a.name, b.name, r IS NULL")
    q("OM2_type", f"MATCH (a:{A} {{name: 'a1'}}) OPTIONAL MATCH (a)-[:NOSUCH{TAG}]->(b) RETURN a.name, b")
    q("OM2_label", f"MATCH (a:{A} {{name: 'a1'}}) OPTIONAL MATCH (a)-[:{K}]->(b:NoSuch{TAG}) RETURN a.name, b")
    q("OM3_inside", f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) WHERE b.v = 2 RETURN a.name, b.name ORDER BY a.name, b.name")
    q("OM3_after", f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) WITH a, b WHERE b.v = 2 RETURN a.name, b.name")
    q("OM3_inside_param", f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) WHERE b.v = $v RETURN a.name, b.name ORDER BY a.name, b.name", {"v": 2})
    q("OM4_nomatch", f"MATCH (a:{A} {{name: 'a3'}}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN b.v + 1, coalesce(b.v, 0), b IS NULL, b.name STARTS WITH 'x'")
    q("OM4_match", f"MATCH (a:{A} {{name: 'a1'}}) OPTIONAL MATCH (a)-[:{K}]->(b {{name: 'a2'}}) RETURN b.v + 1, coalesce(b.v, 0), b IS NULL, b.name STARTS WITH 'x'")
    q("OM5_counts", f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN a.name, count(b), count(*), collect(b.name) ORDER BY a.name")
    q("OM5_sumavg", f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) RETURN a.name, sum(b.v), avg(b.v) ORDER BY a.name")
    q("OM5_twin", f"MATCH (a:{C}) OPTIONAL MATCH (a)-[:{KC}]->(b) RETURN a.name, count(b), count(*), sum(b.v) ORDER BY a.name")
    q("OM6_return", f"OPTIONAL MATCH (n:NoSuch{TAG}) RETURN n")
    q("OM6_count", f"OPTIONAL MATCH (n:NoSuch{TAG}) RETURN count(n)")
    q("OM7_default", f"MATCH (a:{A} {{name: 'a1'}}) OPTIONAL MATCH (a)-[:{K}]->(b) OPTIONAL MATCH (b)-[:{K}]->(c) RETURN b.name, c.name ORDER BY b.name")
    q("OM7_named", f"USE GRAPH '{NG}' MATCH (a {{name: 'gx'}}) OPTIONAL MATCH (a)-[:{K}]->(b) OPTIONAL MATCH (b)-[:{K}]->(c) RETURN b.name, c.name")

    # ---- aggregation
    q("AG1_api", f"MATCH (n:{G}) RETURN n.k AS k, count(*) AS c")
    q("AG1_twin", f"MATCH (n:{G}C) RETURN n.k AS k, count(*) AS c")
    q("AG1_api_distinct", f"MATCH (n:{G}) RETURN DISTINCT n.k AS k")
    q("AG2_api", f"MATCH (n:{G}D) RETURN count(DISTINCT n.k)")
    q("AG2_api_vals", f"MATCH (n:{G}D) RETURN n.k AS k, count(*) AS c")
    q("AG2_unwind", "UNWIND [1, '1', true, 'true'] AS k RETURN count(DISTINCT k)")
    q("AG2_param", "UNWIND $xs AS k RETURN count(DISTINCT k)", {"xs": [1, "1", True, "true"]})
    q("AG3_lists", f"MATCH (n:{A}) WHERE n.l IS NOT NULL RETURN collect(n.l)")
    q("AG3_maps", f"MATCH (n:{A}) WHERE n.m IS NOT NULL RETURN collect(n.m)")
    q("AG3_twin_lists", f"MATCH (n:{C}) WHERE n.l IS NOT NULL RETURN collect(n.l)")
    q("AG4_int", f"MATCH (n:{A}) WHERE n.v IS NOT NULL RETURN sum(n.v), avg(n.v)")
    q("AG4_mixed", f"MATCH (n:{A}) WHERE n.v IS NOT NULL OR n.name = 'a3' WITH n, CASE WHEN n.name = 'a3' THEN 2.5 ELSE n.v END AS x RETURN sum(x), avg(x)")
    q("AG4_mixed_props", f"MATCH (n:{A}) WHERE n.f IS NOT NULL RETURN sum(n.f), sum(n.v) + sum(n.f), avg(n.f)")
    q("AG5_api", f"MATCH (n:{A}) WHERE n.s IS NOT NULL RETURN sum(n.s)")
    q("AG5_api_num", f"MATCH (n:{G}) WHERE n.k = '1' OR n.k = 1 RETURN sum(n.k)")
    q("AG5_unwind", "UNWIND ['1', '2'] AS x RETURN sum(x)")
    q("AG6_global", f"MATCH (n:NoSuch{TAG}) RETURN count(n), sum(n.v), avg(n.v), collect(n.v)")
    q("AG6_grouped", f"MATCH (n:NoSuch{TAG}) RETURN n.k, count(n), sum(n.v)")
    q("AG7_api", f"MATCH (a:{A} {{name: 'a1'}})-[r:{K}]->() RETURN sum(coalesce(r.w, r.weight)), collect(r.w), collect(r.weight)")
    q("AG7_api_sum", f"MATCH (a:{A} {{name: 'a1'}})-[r:{K}]->() RETURN sum(r.w) + sum(r.weight)")
    q("AG7_twin_sum", f"MATCH (a:{C} {{name: 'a1'}})-[r:{KC}]->() RETURN sum(r.w) + sum(r.weight)")

    # ---- WITH / DISTINCT / ORDER BY / SKIP / LIMIT
    q("WS1_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name SKIP $s LIMIT $l", {"s": 1, "l": 2})
    q("WS1_literal", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name SKIP 1 LIMIT 2")
    q("WS2_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": -1})
    q("WS2_literal", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT -1")
    q("WS3_skip_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name SKIP $s", {"s": -1})
    q("WS3_skip_literal", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name SKIP -1")
    q("WS3_limit_float_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": 1.5})
    q("WS3_limit_float_literal", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT 1.5")
    q("WS3_skip_float_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name SKIP $s", {"s": 1.5})
    q("WS3_limit_string_param", f"MATCH (n:{A}) RETURN n.name ORDER BY n.name LIMIT $l", {"l": "2"})
    q("WS4_param", f"MATCH (n:{A}) RETURN n.name LIMIT $l", {"l": 0})
    q("WS4_literal", f"MATCH (n:{A}) RETURN n.name LIMIT 0")
    q("WS4_with_param", f"MATCH (n:{A}) WITH n ORDER BY n.name LIMIT $l RETURN n.name", {"l": 0})
    q("WS5_nodes", f"MATCH (n:{A}) WHERE n.name = 'dup' RETURN DISTINCT n")
    q("WS5_values", f"MATCH (n:{A}) WHERE n.name = 'dup' RETURN DISTINCT n.name")
    q("WS5_count_nodes", f"MATCH (n:{A}) WHERE n.name = 'dup' RETURN count(DISTINCT n), count(DISTINCT n.name)")
    q("WS6_with_col", f"MATCH (n:{A}) WITH n.name AS nm, n.v AS v WHERE v IS NOT NULL RETURN nm ORDER BY v DESC")
    q("WS6_alias", f"MATCH (n:{A}) RETURN n.name AS nm ORDER BY nm DESC")
    q("WS7_literal", f"MATCH (n:{A}) WITH n ORDER BY n.v DESC LIMIT 1 RETURN n.name")
    q("WS7_param", f"MATCH (n:{A}) WITH n ORDER BY n.v DESC LIMIT $l RETURN n.name", {"l": 1})
    q("WS7_notnull", f"MATCH (n:{A}) WHERE n.v IS NOT NULL WITH n ORDER BY n.v DESC LIMIT $l RETURN n.name", {"l": 1})
    q("WS7_skip_param_with", f"MATCH (n:{A}) WITH n ORDER BY n.name SKIP $s LIMIT 1 RETURN n.name", {"s": 2})

    # ---- UNION / EXISTS / comprehension
    q("UN1_union", "RETURN 1 AS x UNION RETURN 1 AS x")
    q("UN1_all", "RETURN 1 AS x UNION ALL RETURN 1 AS x")
    q("UN2_int", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n.v AS x UNION MATCH (m:{A} {{name: 'a2'}}) RETURN m.v - 1 AS x")
    q("UN2_str", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n.s AS x UNION MATCH (m:{A} {{name: 'a2'}}) RETURN m.v - 1 AS x")
    q("UN2_str_api_props", f"MATCH (n:{A} {{name: 'a1'}}) RETURN n.s AS x UNION MATCH (m:{A} {{name: 'a1'}}) RETURN m.v AS x")
    q("UN2_twin_props", f"MATCH (n:{C} {{name: 'a1'}}) RETURN n.s AS x UNION MATCH (m:{C} {{name: 'a1'}}) RETURN m.v AS x")
    q("UN2_bool_str", f"MATCH (n:{G}D) WHERE n.k = true RETURN n.k AS x UNION RETURN 'true' AS x")
    q("UN3_columns", "RETURN 1 AS x UNION RETURN 2 AS y")
    q("UN3_mixed", "RETURN 1 AS x UNION RETURN 1 AS x UNION ALL RETURN 1 AS x")
    q("UN4_nodes", f"MATCH (n:{A} {{name: 'dup'}}) RETURN n UNION MATCH (n:{A} {{name: 'dup'}}) RETURN n")
    q("EX1_exists", f"MATCH (n:{A}) WHERE EXISTS {{ (n)-[:{K}]->() }} RETURN n.name ORDER BY n.name")
    q("EX1_pattern", f"MATCH (n:{A}) WHERE (n)-[:{K}]->() RETURN n.name ORDER BY n.name")
    q("EX1_not", f"MATCH (n:{A}) WHERE NOT EXISTS {{ (n)-[:{K}]->() }} RETURN n.name ORDER BY n.name")
    q("EX1_twin", f"MATCH (n:{C}) WHERE EXISTS {{ (n)-[:{KC}]->() }} RETURN n.name ORDER BY n.name")
    q("EX2_named", f"USE GRAPH '{NG}' MATCH (n) WHERE EXISTS {{ (n)-[:{K}]->() }} RETURN n.id")
    q("EX2_all", f"MATCH (n) WHERE n.id STARTS WITH '{P}' AND EXISTS {{ (n)-[:{K}]->() }} RETURN n.id ORDER BY n.id")
    q("EX2_named_pattern", f"USE GRAPH '{NG}' MATCH (n) WHERE (n)-[:{K}]->() RETURN n.id")
    q("PC1_a1", f"MATCH (n:{A} {{name: 'a1'}}) RETURN [(n)-[:{K}]->(m) | m.name]")
    q("PC1_a3", f"MATCH (n:{A} {{name: 'a3'}}) RETURN [(n)-[:{K}]->(m) | m.name]")
    q("PC2_multi", f"USE GRAPH '{MG}' MATCH (x {{id: '{P}mx'}}) RETURN size([(x)-[:{K}]->(y) | y])")
    q("PC2_single", f"MATCH (x:{A}S {{id: '{P}sx'}}) RETURN size([(x)-[:{K}]->(y) | y])")
    q("PC3_api", f"MATCH (n:{A} {{name: 'a1'}}) RETURN [x IN n.l WHERE x > 1 | x * 10]")
    q("PC3_twin", f"MATCH (n:{C} {{name: 'a1'}}) RETURN [x IN n.l WHERE x > 1 | x * 10]")

    # ---- paths
    q("PA1_api", f"MATCH p = (a:{A} {{name: 'a1'}})-[r:{K}]->(b:{A} {{name: 'a2'}}) RETURN length(p), type(r), startNode(r).name, endNode(r).name, size(nodes(p)), size(relationships(p))")
    q("PA1_twin", f"MATCH p = (a:{C} {{name: 'a1'}})-[r:{KC}]->(b:{C} {{name: 'a2'}}) RETURN length(p), type(r), startNode(r).name, endNode(r).name, size(nodes(p)), size(relationships(p))")
    q("PA2_incoming", f"MATCH (b:{A} {{name: 'a2'}})<-[r:{K}]-(a) RETURN startNode(r).name, endNode(r).name")
    q("PA2_undirected", f"MATCH (b:{A} {{name: 'a2'}})-[r:{K}]-(x) RETURN x.name, startNode(r).name, endNode(r).name ORDER BY x.name")
    q("PA2_twin_incoming", f"MATCH (b:{C} {{name: 'a2'}})<-[r:{KC}]-(a) RETURN startNode(r).name, endNode(r).name")
    q("PA3_named", f"USE GRAPH '{NG}' MATCH p = (x)-[r]->(y) RETURN type(r), startNode(r).id, length(p)")
    q("PA3_all", f"MATCH p = (x {{id: '{P}gx'}})-[r]->(y) RETURN type(r), startNode(r).name, endNode(r).name, length(p) ORDER BY endNode(r).name")
    q("PA4_var", f"MATCH p = (a:{A} {{name: 'a1'}})-[:{K}*1..2]->(c) RETURN length(p), [x IN nodes(p) | x.name] ORDER BY length(p), c.name")
    q("PA4_rels", f"MATCH p = (a:{A} {{name: 'a1'}})-[:{K}*1..2]->(c) RETURN length(p), [r IN relationships(p) | type(r)], [r IN relationships(p) | startNode(r).name] ORDER BY length(p), c.name")
    q("PA5_multi", f"USE GRAPH '{MG}' MATCH (x {{id: '{P}mx'}})-[r:{K}]->(y) RETURN count(r), collect(r.n)")
    q("PA5_single", f"MATCH (x:{A}S {{id: '{P}sx'}})-[r:{K}]->(y) RETURN count(r), collect(r.n)")
    q("PA5_multi_rel_ids", f"USE GRAPH '{MG}' MATCH (x {{id: '{P}mx'}})-[r:{K}]->(y) RETURN count(DISTINCT r), count(DISTINCT y)")
    # bulk duplicates in one batch
    e.create_node(P + "bx", labels=[A + "B"]); e.create_node(P + "by", labels=[A + "B"])
    try:
        out["PA6_bulk_ret"] = e.bulk_create_edges([{"source_id": P + "bx", "predicate": K, "target_id": P + "by"},
                                                   {"source_id": P + "bx", "predicate": K, "target_id": P + "by"}])
    except Exception as x:
        out["PA6_bulk_ret"] = f"{type(x).__name__}: {x}"[:300]
    q("PA6_count", f"MATCH (x:{A}B {{id: '{P}bx'}})-[r:{K}]->(y) RETURN count(r)")
    try:
        out["PA6_bulk_again"] = e.bulk_create_edges([{"source_id": P + "bx", "predicate": K, "target_id": P + "by"}])
    except Exception as x:
        out["PA6_bulk_again"] = f"{type(x).__name__}: {x}"[:300]
    q("PA6_count_again", f"MATCH (x:{A}B {{id: '{P}bx'}})-[r:{K}]->(y) RETURN count(r)")
    # Cypher CREATE over an existing API edge: single-edge default vs multigraph
    q("PA7_single", f"MATCH (a:{A}S {{id: '{P}sx'}}), (b:{A}S {{id: '{P}sy'}}) CREATE (a)-[:{K}]->(b)", native=False)
    q("PA7_single_count", f"MATCH (x:{A}S {{id: '{P}sx'}})-[r:{K}]->(y) RETURN count(r)")
    q("PA7_multi", f"USE GRAPH '{MG}' MATCH (a {{id: '{P}mx'}}), (b {{id: '{P}my'}}) CREATE (a)-[:{K}]->(b)", native=False)
    q("PA7_multi_count", f"USE GRAPH '{MG}' MATCH (x {{id: '{P}mx'}})-[r:{K}]->(y) RETURN count(r)")

    # ---- DELETE / DETACH DELETE / REMOVE
    def node_state(nid, graph=None):
        n = e.get_node(nid) if graph is None else e.get_node(nid, graph=graph)
        return None if n is None else sorted(k for k in n.keys())
    q("DL1_edges", f"MATCH (n:{A} {{id: '{P}a1'}}) DELETE n", native=False)
    out["DL1_after_a1"] = node_state(P + "a1")
    q("DL1_after_edges", f"MATCH (n:{A} {{id: '{P}a1'}})-[r]->() RETURN count(r)")
    q("DL1_noedge", f"MATCH (n:{A} {{id: '{P}d1'}}) DELETE n", native=False)
    out["DL1_after_d1"] = node_state(P + "d1")
    q("DL2_incoming", f"MATCH (n:{A} {{id: '{P}a3'}}) DELETE n", native=False)
    out["DL2_after_a3_refused"] = node_state(P + "a3")
    q("DL2_detach", f"MATCH (n:{A} {{id: '{P}a3'}}) DETACH DELETE n", native=False)
    out["DL2_after_a3"] = node_state(P + "a3")
    q("DL2_reader_out", f"MATCH (a:{A} {{name: 'a1'}})-[:{K}]->(b) RETURN b.name ORDER BY b.name")
    q("DL2_reader_any", f"MATCH (a {{id: '{P}a2'}})-[r]->(b) RETURN count(r)")
    try:
        out["DL2_degree_a1"] = e.get_edge_count() if False else None
    except Exception:
        pass
    q("DL3_delete_r", f"MATCH (:{A} {{id: '{P}a1'}})-[r:{K}]->(:{A} {{id: '{P}a2'}}) DELETE r", native=False)
    q("DL3_after", f"MATCH (a:{A} {{id: '{P}a1'}})-[r:{K}]->(b) RETURN b.name")
    out["DL3_endpoints"] = [node_state(P + "a1") is not None, node_state(P + "a2") is not None]
    out["DL3_recreate"] = e.create_edge(P + "a1", K, P + "a2")
    q("DL3_after_recreate", f"MATCH (a:{A} {{id: '{P}a1'}})-[r:{K}]->(b) RETURN b.name, r.w")
    q("DL4_remove_prop", f"MATCH (n:{A} {{id: '{P}a1'}}) REMOVE n.f", native=False)
    q("DL4_keys", f"MATCH (n:{A} {{id: '{P}a1'}}) RETURN keys(n), n.f")
    out["DL4_get_node"] = node_state(P + "a1")
    q("DL4_remove_label", f"MATCH (n:{A} {{id: '{P}a2'}}) REMOVE n:{A}", native=False)
    q("DL4_labels", f"MATCH (n {{id: '{P}a2'}}) RETURN labels(n)")
    out["DL4_get_node_labels"] = (e.get_node(P + "a2") or {}).get("labels")
    q("DL5_named", f"USE GRAPH '{NG}' MATCH ()-[r:{K}]->() DELETE r", native=False)
    q("DL5_named_after", f"USE GRAPH '{NG}' MATCH ()-[r:{K}]->() RETURN count(r)")
    q("DL5_default_after", f"MATCH ({{id: '{P}gx'}})-[r:{K}]->() RETURN count(r)")
    q("DL6_one", f"USE GRAPH '{MG}' MATCH ({{id: '{P}mx'}})-[r:{K}]->() WITH r LIMIT 1 DELETE r", native=False)
    q("DL6_after_one", f"USE GRAPH '{MG}' MATCH ({{id: '{P}mx'}})-[r:{K}]->() RETURN count(r)")
    q("DL6_detach", f"USE GRAPH '{MG}' MATCH (n {{id: '{P}mx'}}) DETACH DELETE n", native=False)
    q("DL6_after_detach", f"USE GRAPH '{MG}' MATCH ()-[r:{K}]->() RETURN count(r)")
    c.close()
    d = HERE / f"clauses-observed-{RUN}.json"
    d.write_text(json.dumps(out, indent=1, default=repr) + "\n")
    print(d)


if __name__ == "__main__":
    main()
