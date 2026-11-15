#!/usr/bin/env python3
"""Module 08 live reproductions on AUDITB (SQL path: native_cypher=False), one locked session.

    python experiment/playbook-completion/live/breadth-b/08_findings_live.py [check ...]

Each check runs the pin's public API (engine.execute_cypher / execute_aql / kg_GRAPH_PATH) on the scratch layout of
08_common.setup and records what it observed against the oracle the finding states (the intended behaviour). The
oracle is fixed per check; a check reports `reproduced` when the as-built behaviour differs from the oracle the way the
finding says, `not-reproduced` when it matches the oracle, `inconclusive` otherwise. Log:
$RUN_DIR/breadth-b/live/08-findings.json.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c08", HERE / "08_common.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

R: dict = {}


def verdict(cond_repro, cond_oracle):
    return "reproduced" if cond_repro else ("not-reproduced" if cond_oracle else "inconclusive")


def ids(r):
    return sorted(str(x[0]) for x in r.get("rows", []))


def f0802(s):
    q1 = ("USE GRAPH 'b08gA' MATCH (n) RETURN count(*) AS c UNION ALL MATCH ()-[r]->() RETURN count(*) AS c")
    r1 = C.run(s, q1)
    true_ga = [s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = 'b08gA'")[0][0],
               s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'b08gA'")[0][0]]
    all_ns = [s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes")[0][0], s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges")[0][0]]
    q2 = ("USE GRAPH 'b08gA' MATCH (n:B08L) RETURN DISTINCT n.name AS entity_name UNION ALL "
          "MATCH (n:B08L) RETURN DISTINCT n.id AS entity_name")
    r2 = C.run(s, q2)
    canned1 = r1["columns"] == ["result"]
    canned2 = r2["columns"] == ["entity", "id"]
    other_graph_ids = [row for row in r2["rows"] if len(row) > 1 and str(row[1]) in ("b08_leak", "b08_s", "b08_t")]
    R["F-0802"] = {"q_count_union": r1, "true_counts_b08gA": true_ga, "namespace_counts": all_ns,
                   "q_entity_union": r2, "rows_from_other_graphs": other_graph_ids,
                   "oracle": "a scoped UNION ALL query answers its own columns from graph b08gA only (CONTEXT.md:27-43)",
                   "verdict": verdict(canned1 or canned2, r1["columns"] == ["c"])}


def f0803(s):
    r = C.run(s, "MATCH (n:B08L) RETURN n.id AS id WHERE false")
    R["F-0803"] = {"result": r, "oracle": "CYP-X3.8: refused with a parse error (openCypher refuses WHERE after RETURN)",
                   "verdict": verdict(bool(r["rows"]) and not r["exc"], r["exc"] is not None)}


def f0804(s):
    from iris_vector_graph.cypher.parser import CypherParseError
    out = {}
    for q in ["MATCH (n) RETURN n §", "MATCH (n) RETURN 'unclosed", "MATCH (n) RETURN n; MATCH (m) RETURN m"]:
        r = C.run(s, q)
        out[q] = {"exc": r.get("exc"), "is_CypherParseError": "CypherParseError" in (r.get("exc_mro") or []),
                  "msg": r.get("msg", "")[:200]}
    bad = [q for q, v in out.items() if v["exc"] and not v["is_CypherParseError"]]
    R["F-0804"] = {"results": out, "not_CypherParseError": bad,
                   "oracle": "USER_GUIDE.md:313: a query that does not parse raises CypherParseError",
                   "verdict": verdict(bool(bad), all(v["is_CypherParseError"] for v in out.values()))}


def f0805(s):
    q = "CREATE (c:B08D {id:'b08_d3'}), (a:B08D {id:'b08_d1'})-[:B08T]->(b:B08D {id:'b08_d2'})"
    first = C.run(s, "CREATE (a:B08D {id:'b08_d1'})-[:B08T]->(b:B08D {id:'b08_d2'})")
    cap = C.capture(s, lambda: s.eng.execute_cypher(q))
    d3 = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_d3'")[0][0]
    edges = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = 'b08_d1'")[0][0]
    tx = cap.txn_summary(s.smap)
    R["F-0805"] = {"first": {k: first.get(k) for k in ("exc", "error")}, "query": q, "error": cap.error,
                   "b08_d3_after": d3, "edges_after": edges, "multigraph_default": s.eng.is_multigraph(""),
                   "journal": {"stores": cap.footprint_json(), "txns": tx,
                               "rolled_back_txns": [u for u in tx if u["kind"] == "txn" and u["rolled_back"]]},
                   "oracle": "KNOWN_ISSUES.md:25-31: CREATE of an existing edge returns no error and writes nothing for that "
                             "edge; the query's other writes (node b08_d3) stay",
                   "verdict": verdict(cap.error is not None and d3 == 0, cap.error is None and d3 == 1 and edges == 1)}


def f0806(s):
    long_id = "b08_" + "L" * 400
    C.run(s, "CREATE (:B08E {id:'b08_e1', s:'b08_short', k: 1}), (:B08E {id:'b08_e2', s: $long, k: 2})", {"long": long_id})
    C.run(s, "CREATE (:B08K {id:'b08_k1', k: 1}), (:B08K {id:'b08_k2', k: 2})")
    out = {}
    for name, q in (("row_merge", "MATCH (a:B08E) MERGE (:B08X {id: a.s})"),
                    ("row_create", "MATCH (a:B08E) WITH a.s AS s CREATE (:B08X {id: s})"),
                    ("count_create_failing_count_step", "CREATE (:B08Y {id:'b08_short'}) WITH * MATCH (b:B08K {k: 1/0}) CREATE (:B08Z)")):
        r = C.run(s, q)
        left = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_short'")[0][0]
        msg = r.get("msg") or ""
        out[name] = {"q": q, "exc": r.get("exc"), "msg": msg[:600], "short_row_after": left,
                     "claims_earlier_rows_written": "steps before it are written" in msg}
    repro = any(v["claims_earlier_rows_written"] and v["short_row_after"] == 0 for v in out.values())
    R["F-0806"] = {"cases": out,
                   "oracle": "the error text matches the outcome: a failed write query leaves nothing (USER_GUIDE.md:266-271)",
                   "verdict": verdict(repro, all(v["exc"] and not v["claims_earlier_rows_written"] for v in out.values()))}


def f0807(s):
    C.run(s, "UNWIND range(1, 47) AS i CREATE (:B08C {id: 'b08_c' + toString(i)})")
    nC = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'b08_c'")[0][0]
    cases = {
        "count_create_over_limit": "MATCH (a:B08C) MATCH (b:B08C) MATCH (c:B08C) CREATE (:B08X)",
        "merge_null": "MERGE (n:B08L {id: null})",
        "merge_set_whole_map": "MERGE (n:B08L {id:'b08_q'}) ON CREATE SET n = {a: 1}",
        "set_from_edge_prop": "MATCH (a:B08L {id:'b08_s'})-[r:B08Q]->(b) SET a.v = r.w + 1",
    }
    out = {}
    for k, q in cases.items():
        r = C.run(s, q)
        out[k] = {"q": q, "exc": r.get("exc"), "mro": r.get("exc_mro"), "msg": r.get("msg", "")[:200],
                  "is_GraphWriteError": "GraphWriteError" in (r.get("exc_mro") or [])}
    x_left = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label = 'B08X'")[0][0]
    q_left = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_q'")[0][0]
    bad = [k for k, v in out.items() if v["exc"] and not v["is_GraphWriteError"]]
    R["F-0807"] = {"B08C_nodes": nC, "cases": out, "B08X_left": x_left, "b08_q_left": q_left, "not_GraphWriteError": bad,
                   "oracle": "USER_GUIDE.md:317-318 and execute_cypher docstring: a refused write raises GraphWriteError",
                   "verdict": verdict(bool(bad), not bad and all(v["exc"] for v in out.values()))}


def f0808(s):
    r = C.run(s, "FOREACH (x IN $list | CREATE (:B08F {v: x}))", {"list": [1, 2, 3]})
    rows = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label = 'B08F'")[0][0]
    vals = s.c.sql("SELECT p.val FROM Graph_KG.rdf_labels l LEFT JOIN Graph_KG.rdf_props p ON p.s = l.s AND "
                   "p.graph_id = l.graph_id AND p.\"key\" = 'v' WHERE l.label = 'B08F'")
    r2 = C.run(s, "FOREACH (x IN [1, 2, 3] | CREATE (:B08G {v: x}))")
    lit = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label = 'B08G'")[0][0]
    R["F-0808"] = {"param_result": r, "param_nodes_created": rows, "param_values": [list(v) for v in vals],
                   "literal_result": r2, "literal_nodes_created": lit,
                   "oracle": "openCypher FOREACH runs its body once per list element: 3 nodes with v = 1, 2, 3",
                   "verdict": verdict(rows != 3 or r.get("exc") is not None, rows == 3)}


def f0810_0812(s):
    C.run(s, "MATCH (n:B08L {id:'b08_s'}) SET n.z = null")
    k1 = C.run(s, "MATCH (n:B08L {id:'b08_s'}) RETURN keys(n) AS k, properties(n) AS p")
    zrow = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s = 'b08_s' AND \"key\" = 'z'")[0][0]
    C.run(s, "MATCH (n:B08L {id:'b08_s'}) SET n.y = 5")
    C.run(s, "MATCH (n:B08L {id:'b08_s'}) SET n.y = n.missing + 1")
    k2 = C.run(s, "MATCH (n:B08L {id:'b08_s'}) RETURN keys(n) AS k")
    keys1 = (k1["rows"][0][0] if k1["rows"] else None)
    R["F-0810"] = {"keys_after_literal_null": k1, "z_rows": zrow, "keys_after_computed_null": k2,
                   "oracle": "openCypher: SET n.p = null removes the property (keys(n) lacks it)",
                   "verdict": verdict(zrow > 0 or (keys1 is not None and "z" in str(keys1)), zrow == 0)}
    C.run(s, "MATCH (:B08L {id:'b08_s'})-[r:B08Q]->() SET r.p = 1e20")
    e = C.run(s, "MATCH (:B08L {id:'b08_s'})-[r:B08Q]->() RETURN r.p AS p")
    v = e["rows"][0][0] if e["rows"] else None
    R["F-0811"] = {"result": e, "value": repr(v), "type": type(v).__name__,
                   "oracle": "openCypher: RETURN r.p answers the float 1e+20",
                   "verdict": verdict(isinstance(v, int), isinstance(v, float))}
    C.run(s, "CREATE (:B08W {id:'b08_w', w: 2})")
    C.run(s, "MATCH (n:B08W {id:'b08_w'}) SET n.w = n.w * 1.5")
    w = C.run(s, "MATCH (n:B08W {id:'b08_w'}) RETURN n.w AS w")
    wv = w["rows"][0][0] if w["rows"] else None
    R["F-0812"] = {"result": w, "value": repr(wv), "type": type(wv).__name__,
                   "oracle": "openCypher: 2 * 1.5 is the float 3.0",
                   "verdict": verdict(isinstance(wv, int), isinstance(wv, float))}


def f0814(s):
    from iris_vector_graph.cypher.aql import translate_aql
    from iris_vector_graph.cypher import writes_cypher
    honest = "FOR v IN 1..1 OUTBOUND 'b08_x' B08R FILTER v.name == 'nomatch' RETURN v"
    hostile = "FOR v IN 1..1 OUTBOUND 'b08_x' B08R FILTER v.name == 'nomatch\" OR true OR v.name = \"' RETURN v"
    out = {}
    for k, a in (("honest", honest), ("hostile", hostile)):
        try:
            cy, _ = translate_aql(a, {})
            r = s.eng.execute_aql(a)
            out[k] = {"aql": a, "cypher": cy, "rows": len(r.rows or []), "error": getattr(r, "error", None)}
        except Exception as e:  # noqa: BLE001
            out[k] = {"aql": a, "exc": f"{type(e).__name__}: {e}"}
    coll = "`B08R*1..1]->(v) SET v.pwn = 1 WITH v AS v MATCH (start)-[:B08R`"
    wa = f"FOR v IN 1..1 OUTBOUND 'b08_x' {coll} RETURN v"
    cy, _ = translate_aql(wa, {})
    cap = C.capture(s, lambda: s.eng.execute_aql(wa))
    pwn = s.c.sql("SELECT s, graph_id FROM Graph_KG.rdf_props WHERE \"key\" = 'pwn' AND s %STARTSWITH 'b08'")
    import inspect
    has_ro = "read_only" in inspect.signature(s.eng.execute_aql).parameters
    R["F-0814"] = {"filter": out, "write_payload": {"aql": wa, "cypher": cy, "writes_cypher": writes_cypher(cy),
                   "error": cap.error, "pwn_rows": [list(x) for x in pwn],
                   "journal_stores": cap.footprint_json(), "txns": cap.txn_summary(s.smap)},
                   "execute_aql_has_read_only": has_ro,
                   "oracle": "AQL literals and collection names reach Cypher only as bound values / checked names "
                             "(CYP-I9.4); execute_aql offers read_only like execute_cypher",
                   "verdict": verdict(out.get("hostile", {}).get("rows", 0) > out.get("honest", {}).get("rows", 0)
                                      or bool(pwn), False)}


def f0815(s):
    leak = ("USE GRAPH 'b08gA' RETURN `(SELECT LIST(NODE_ID) FROM GRAPH_KG.NODES WHERE %SQLUPPER(GRAPH_ID) = "
            "%SQLUPPER('B08GB')) AS LEAK --`.f(1) AS v")
    dic = "RETURN `(SELECT COUNT(*) FROM %DICTIONARY.COMPILEDCLASS) AS NCLASSES --`.f(1) AS v"
    cap = C.capture(s, lambda: s.eng.execute_cypher(leak, read_only=True))
    r1 = {"error": cap.error, "rows": [list(x) for x in (cap.result.rows if cap.result else [])],
          "columns": list(cap.result.columns) if cap.result else [], "sql": str(getattr(cap.result, "sql", ""))[:400],
          "journal_writes": cap.stores()}
    r2 = C.run(s, dic, read_only=True)
    lvl0 = s.c.sql("SELECT $TLEVEL")[0][0]
    r3 = C.run(s, "RETURN `GRAPH_KG.TXN_BEGIN(0) AS LVL --`.f(1) AS v", read_only=True)
    lvl1 = s.c.sql("SELECT $TLEVEL")[0][0]
    undo = s.c.sql("SELECT Graph_KG.Txn_Undo(1)")[0][0] if lvl1 else None
    lvl2 = s.c.sql("SELECT $TLEVEL")[0][0]
    got = str(r1["rows"])
    R["F-0815"] = {"leak_under_use_graph_read_only": r1, "dictionary_read_only": r2,
                   "txn_begin_read_only": {"result": r3, "tlevel_before": lvl0, "tlevel_after": lvl1,
                                           "undo_answer": undo, "tlevel_restored": lvl2},
                   "oracle": "CYP-I9.4 (a name reaches SQL only as a bound value or a checked name); CYP-I8.6 (read-only "
                             "changes no data); USE GRAPH scopes the answer to b08gA",
                   "verdict": verdict(("b08_leak" in got) or bool(r2.get("rows")) or (lvl1 or 0) > (lvl0 or 0), False)}


def f0816(s):
    r = C.run(s, "USE GRAPH 'b08gA' CALL db.labels() YIELD label RETURN label")
    r2 = C.run(s, "USE GRAPH 'b08gA' CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
    labs = [x[0] for x in r["rows"]]
    rts = [x[0] for x in r2["rows"]]
    R["F-0816"] = {"labels": labs, "relationshipTypes": rts,
                   "oracle": "USE GRAPH scopes a query to one graph (USER_GUIDE.md:401-404): b08gA holds only B08L, B08R, B08S",
                   "verdict": verdict("B08B" in labs or "B08Q" in rts, "B08B" not in labs and "B08Q" not in rts)}


def f0817(s):
    out = {}
    for q in ["CALL db.b08nothing()", "CALL apoc.b08nothing()", "CALL dbms.b08nothing()", "CALL ivg.b08nothing()",
              "CALL gds.b08nothing.stream()"]:
        r = C.run(s, q)
        out[q] = {"rows": r["rows"], "columns": r["columns"], "error": r["error"], "exc": r.get("exc"),
                  "msg": r.get("msg", "")[:160]}
    silent = [q for q, v in out.items() if not v["exc"] and not v["error"]]
    R["F-0817"] = {"results": out, "silent_empty": silent,
                   "oracle": "CYP-X10.2: an unknown procedure name is refused, with the list of known names",
                   "verdict": verdict(bool(silent), not silent)}


def f0818(s):
    r1 = C.run(s, "MATCH (a:B08L {id:'b08_x'}) WITH a MATCH (a)-[:B08R*1..2]->(b) RETURN b.id AS id")
    r2 = C.run(s, "MATCH (a:B08L {id:'b08_x'})-[:B08R*1..2]->(b) RETURN b.id AS id")
    R["F-0818"] = {"with_carried_start": ids(r1), "plain_alias_start": ids(r2), "sql_with": r1.get("sql", "")[:600],
                   "oracle": "CYP-I5.6: a variable-length walk in an all-graphs read stays in its start node's graph "
                             "(b08_x is in b08gA only; b08_leak is reachable only through b08gB's edge)",
                   "verdict": verdict("b08_leak" in ids(r1), "b08_leak" not in ids(r1))}


def f0819(s):
    q = "MATCH (a {node_id:'b08_x'})-[:B08R*1..2]->(m) RETURN approx_count_distinct(m) AS c"
    ex = "MATCH (a {node_id:'b08_x'})-[:B08R*1..2]->(m) RETURN count(DISTINCT m) AS c"
    before = C.run(s, q)
    sync = None
    try:
        t0 = time.time()
        sync = {"answer": str(s.eng.sync())[:300], "seconds": round(time.time() - t0, 2)}
    except Exception as e:  # noqa: BLE001
        sync = {"exc": f"{type(e).__name__}: {e}"[:300]}
    r_after = s.eng.execute_cypher(q)
    after = {"rows": [list(x) for x in r_after.rows], "sql": str(r_after.sql),
             "warnings": list(getattr(getattr(r_after, "metadata", None), "warnings", []) or [])}
    exact = C.run(s, ex)
    R["F-0819"] = {"approx_before_sync": before, "rebuild_nkg": sync, "approx_after_sync": after, "exact": exact,
                   "oracle": "CYP-I4.14: an approximate count in an all-graphs read counts each graph apart "
                             "(b08_x's graph reaches 1 distinct end: b08_m)",
                   "verdict": verdict(bool(after["rows"]) and bool(exact["rows"]) and after["rows"][0][0] != exact["rows"][0][0]
                                      and "HLL" in str(after.get("sql", "")) + str(after),
                                      bool(after["rows"]) and after["rows"][0][0] == 1)}


def f0820(s):
    try:
        res = s.eng.kg_GRAPH_PATH("b08_x", "B08R", "B08S")
        res = [list(r) if isinstance(r, (list, tuple)) else r for r in (res or [])]
        exc = None
    except Exception as e:  # noqa: BLE001
        res, exc = None, f"{type(e).__name__}: {e}"
    default_has = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = '' AND s = 'b08_x'")[0][0]
    R["F-0820"] = {"answer": res, "exc": exc, "default_graph_edges_from_b08_x": default_has,
                   "oracle": "USER_GUIDE.md:462-464: a Python read with no graph= means the default graph, never every graph",
                   "verdict": verdict(bool(res) and default_has == 0, res == [] or res is None)}


def f0823(s):
    out = {}
    for agg, want in (("max(q.v)", None), ("collect(q.v)", []), ("count(q)", 0), ("avg(q.v)", None)):
        r = C.run(s, f"MATCH (a:B08L {{id:'b08_s'}}) CALL {{ WITH a MATCH (a)-[:B08NONE]->(q) RETURN {agg} AS m }} RETURN m")
        got = r["rows"][0][0] if r["rows"] else "no-row"
        out[agg] = {"got": got, "openCypher": want, "exc": r.get("exc"), "msg": r.get("msg", "")[:160]}
    wrong = [k for k, v in out.items() if not v["exc"] and v["got"] != v["openCypher"]]
    R["F-0823"] = {"results": out, "differs_from_openCypher": wrong,
                   "oracle": "openCypher: an empty max/avg is null, an empty collect is [], count is 0",
                   "verdict": verdict(bool(set(wrong) - {"count(q)"}), not wrong)}


def f0824(s):
    from iris_vector_graph.cypher.aql import translate_aql
    out = {}
    for a in ("FOR v IN 1..1 OUTBOUND 'b08_x' B08R FILTER v.url == 'http://x' RETURN v",
              "FOR v IN 1..1 OUTBOUND 'b08_x' B08R FILTER v.url == 'x' RETURN v"):
        try:
            cy, _ = translate_aql(a, {})
            out[a] = {"cypher": cy}
        except Exception as e:  # noqa: BLE001
            out[a] = {"exc": f"{type(e).__name__}: {e}"}
    first = list(out.values())[0]
    R["F-0824"] = {"results": out, "oracle": "a string literal holding // is a string, not a comment",
                   "verdict": verdict("exc" in first, "cypher" in first)}


CHECKS = [f0802, f0803, f0804, f0805, f0806, f0807, f0808, f0810_0812, f0814, f0815, f0816, f0817, f0818, f0819,
          f0820, f0823, f0824]


def main():
    want = set(sys.argv[1:])
    with C.session08("08-findings", native_cypher=False) as s:
        meta = C.ledger_meta(s)
        R["_env"] = {"ledger_meta": meta, "pid": s.c.pid}
        if meta.get("strict"):
            R["_env"]["skipped"] = "ledger strict mode on (module 11's state); writes would be refused"
        R["_cleanup_before"] = C.cleanup(s)
        R["_setup"] = C.setup(s)
        for f in CHECKS:
            if want and f.__name__ not in want:
                continue
            try:
                f(s)
            except Exception as e:  # noqa: BLE001
                R[f.__name__] = {"harness_error": f"{type(e).__name__}: {e}", "tb": C.tb()[-1500:]}
        R["_cleanup_after"] = C.cleanup(s)
        p = C.write_log(s, R, name="08-findings" + ("-" + "-".join(sorted(want)) if want else ""))
    print(p)
    for k, v in R.items():
        if k.startswith("F-"):
            print(k, v.get("verdict"))
        elif k.startswith("f0"):
            print(k, v)
    print("cleanup", R["_cleanup_after"]["left"])


if __name__ == "__main__":
    main()
