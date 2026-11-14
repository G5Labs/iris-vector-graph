#!/usr/bin/env python3
"""§3.6 row-id and key invariants, per module, live on AUDITD (observation only).

    locks.sh iris python keys.py OUT.json [case-prefix ...]

Oracle (keys_check): over the whole namespace after each case
  K1 no two rows share a declared key: nodes (graph_id, node_id), rdf_labels (graph_id, s, label), rdf_props
     (graph_id, s, key), rdf_edges (s, p, o_id, graph_id, ekey), kg_NodeEmbeddings (graph_id, node_id),
     rdf_reifications (reifier_id); counted with %NOINDEX full scans (a %NOINDEX/%NOCHECK row is invisible to an
     index read, premise P-0304), compared with the same count through the indexes;
  K2 the adjacency index is exactly the rows: ^KG("out", G, s, p, o) and ^KG("in", G, o, p, s) for every rdf_edges
     row and no ^KG("out") leaf without a row; ^KG("label", G, label, s) exactly the rdf_labels rows;
  K3 row ids: edge_id distinct.
Each case writes through one module's own writers (sequential duplicates, in-batch duplicates, concurrent duplicates
from several connections, re-creation after delete) and the oracle runs after it.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
import lib  # noqa: E402

KEYS = {
    "nodes": ("Graph_KG.nodes", "COALESCE(graph_id,''), node_id"),
    "rdf_labels": ("Graph_KG.rdf_labels", "COALESCE(graph_id,''), s, label"),
    "rdf_props": ("Graph_KG.rdf_props", "COALESCE(graph_id,''), s, \"key\""),
    "rdf_edges": ("Graph_KG.rdf_edges", "s, p, o_id, COALESCE(graph_id,''), ekey"),
    "kg_NodeEmbeddings": ("Graph_KG.kg_NodeEmbeddings", "COALESCE(graph_id,''), node_id"),
    "rdf_reifications": ("Graph_KG.rdf_reifications", "reifier_id"),
}


def gk(g):
    g = "" if g in (None, "\x00") else str(g)
    return 0 if g == "" else g


def kg_leaves(c, d, gl="^KG"):
    """Every gl(d, G, a, p, b) leaf (and keyed sub-leaves) as (G, a, p, b)."""
    out = set()
    if not int(c.o.isDefined(gl, d)):
        return out
    for G, _ in c.o.iterator(gl, d).items():
        for a, _ in c.o.iterator(gl, d, G).items():
            for p, _ in c.o.iterator(gl, d, G, a).items():
                for b, _ in c.o.iterator(gl, d, G, a, p).items():
                    out.add((str(G), str(a), str(p), str(b)))
    return out


def scan_from(c, t):
    """A FROM clause that reads the table's master map (every row, %NOINDEX rows included): %IGNOREINDEX *."""
    try:
        c.sql(f"SELECT COUNT(*) FROM %IGNOREINDEX * {t}")
        return f"%IGNOREINDEX * {t}"
    except Exception:  # noqa: BLE001
        return t


def read_state(c):
    """Everything the key and FK oracles look at, read by full scans (rows) and the Native API (^KG)."""
    st = {"rows": {}, "kg": {}}
    for name, (t, cols) in KEYS.items():
        frm = scan_from(c, t)
        st["rows"][name] = [tuple("" if v is None else str(v) for v in r) for r in c.sql(f"SELECT {cols} FROM {frm}")]
    st["edges"] = [("" if v is None else str(v) for v in r) for r in
                   c.sql(f"SELECT s, p, o_id, graph_id, ekey, edge_id FROM {scan_from(c, 'Graph_KG.rdf_edges')}")]
    st["edges"] = [tuple(x) for x in st["edges"]]
    st["kg"]["out"] = sorted(kg_leaves(c, "out"))
    st["kg"]["in"] = sorted(kg_leaves(c, "in"))
    lidx = set()
    if int(c.o.isDefined("^KG", "label")):
        for G, _ in c.o.iterator("^KG", "label").items():
            for l, _ in c.o.iterator("^KG", "label", G).items():
                for s, _ in c.o.iterator("^KG", "label", G, l).items():
                    lidx.add((str(G), str(l), str(s)))
    st["kg"]["label"] = sorted(lidx)
    return st


def gks(g):
    return "0" if g in ("", None, "\x00") else str(g)


def eval_keys(st):
    """K1 duplicates of declared keys (full scan), K2 adjacency/label index equal to the rows, K3 edge ids distinct."""
    res = {"dup": {}, "adjacency": {}, "labels": {}}
    viol = []
    for name, rows in st["rows"].items():
        seen, dup = set(), []
        for r in rows:
            k = tuple(r)
            if k in seen:
                dup.append([x[:60] for x in k])
            seen.add(k)
        res["dup"][name] = dup[:5]
        if dup:
            viol.append(f"K1 duplicate {name} key: {dup[:2]}")
    ids = [r[5] for r in st["edges"]]
    if len(ids) != len(set(ids)):
        viol.append("K3 edge_id repeated")
    rows = {(gks(g), s, p, o) for s, p, o, g, _e, _i in st["edges"]}
    out = set(tuple(x) for x in st["kg"]["out"])
    inn = {(G, b, p, a) for (G, a, p, b) in (tuple(x) for x in st["kg"]["in"])}
    a = {"rows_without_out": sorted(rows - out)[:5], "out_without_row": sorted(out - rows)[:5],
         "rows_without_in": sorted(rows - inn)[:5], "in_without_row": sorted(inn - rows)[:5]}
    res["adjacency"] = {"rows": len(rows), "out": len(out), "in": len(inn), **a}
    for k, v in a.items():
        if v:
            viol.append(f"K2 adjacency {k}: {[list(x) for x in v[:2]]}")
    lrows = {(gks(g), l, s) for g, s, l in st["rows"]["rdf_labels"]}
    lidx = set(tuple(x) for x in st["kg"]["label"])
    res["labels"] = {"rows": len(lrows), "index": len(lidx), "rows_without_index": sorted(lrows - lidx)[:5],
                     "index_without_row": sorted(lidx - lrows)[:5]}
    if res["labels"]["rows_without_index"] or res["labels"]["index_without_row"]:
        viol.append(f"K2 label index: {res['labels']['rows_without_index'][:2]} / {res['labels']['index_without_row'][:2]}")
    res["violations"] = viol
    return res


def keys_check(c):
    st = read_state(c)
    res = eval_keys(st)
    res["row_counts"] = {k: len(v) for k, v in st["rows"].items()}
    return res


def call(f):
    try:
        v = f()
        return {"ok": True, "answer": str(v)[:300]}
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:300]}"}


def concurrently(n, fn):
    """fn(i, conn, engine) in n threads, each on its own identity-checked connection, released together."""
    conns = [lib.conn() for _ in range(n)]
    engs = [lib.engine(c) for c in conns]
    bar = threading.Barrier(n)
    out = [None] * n

    def run(i):
        try:
            bar.wait(timeout=60)
            out[i] = call(lambda: fn(i, conns[i], engs[i]))
            try:
                conns[i].conn.commit()
            except Exception:  # noqa: BLE001
                pass
        except Exception as ex:  # noqa: BLE001
            out[i] = {"ok": False, "error": f"harness {type(ex).__name__}: {ex}"}
    th = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in th:
        t.start()
    for t in th:
        t.join(timeout=300)
    for c in conns:
        c.close()
    return out


def case(label, module, fn):
    c = lib.conn()
    t0 = time.time()
    r = {"case": label, "module": module}
    try:
        lib.reset(c)
        eng = lib.engine(c)
        r["steps"] = fn(c, eng)
        try:
            c.conn.commit()
        except Exception:  # noqa: BLE001
            pass
        chk = keys_check(c)
        r["check"] = chk
        r["violations"] = chk["violations"]
        r["outcome"] = "holds" if not chk["violations"] else "violated"
    except Exception:  # noqa: BLE001
        r["outcome"] = "harness-error"
        r["trace"] = traceback.format_exc()[-1500:]
    finally:
        try:
            lib.reset(c)
        except Exception:  # noqa: BLE001
            pass
        c.close()
    r["secs"] = round(time.time() - t0, 2)
    print(json.dumps({k: v for k, v in r.items() if k not in ("check",)}, default=str)[:1600], flush=True)
    return r


# ------------------------------------------------------------------------------------------------ cases

def c03_sequential(c, e):
    s = {}
    s["create_node x2"] = [call(lambda: e.create_node("k:1", labels=["A"], properties={"p": "1"})) for _ in range(2)]
    s["create_node other graph"] = call(lambda: e.create_node("k:1", labels=["A"], graph="kg2"))
    s["create_edge x2"] = [call(lambda: e.create_edge("k:1", "R", "k:2")) for _ in range(2)]
    s["store_node x2"] = [call(lambda: e.store_node("k:3", properties={"p": "x"}, labels=["B"])) for _ in range(2)]
    s["store_edge x2"] = [call(lambda: e.store_edge("k:3", "R", "k:1", qualifiers={"w": "1"})) for _ in range(2)]
    s["bulk_create_nodes dup in batch"] = call(lambda: e.bulk_create_nodes([{"id": "k:4", "labels": ["A"]},
                                                                            {"id": "k:4", "labels": ["A", "B"]}]))
    s["bulk_create_edges dup in batch"] = call(lambda: e.bulk_create_edges([
        {"source_id": "k:4", "predicate": "R", "target_id": "k:1"}, {"source_id": "k:4", "predicate": "R", "target_id": "k:1"}]))
    s["delete_edge then create_edge"] = [call(lambda: e.delete_edge("k:1", "R", "k:2")), call(lambda: e.create_edge("k:1", "R", "k:2"))]
    s["delete_node then create_node"] = [call(lambda: e.delete_node("k:3")), call(lambda: e.create_node("k:3"))]
    return s


def bulkloader(c, graph=None):
    from iris_vector_graph.bulk_loader import BulkLoader
    return BulkLoader(c.conn, graph=graph)


def c03_bulkloader_in_batch(c, e):
    bl = bulkloader(c)
    s = {"load_nodes dup id in one batch": call(lambda: bl.load_nodes([("kb:1", {"namespace": "A", "p": "1"}),
                                                                         ("kb:1", {"namespace": "A", "p": "2"})]))}
    s["load_edges"] = call(lambda: bl.load_edges([("kb:1", "R", "kb:2", None)]))
    s["rebuild_all_indices"] = call(lambda: bl.rebuild_all_indices())
    s["build_graph_globals"] = call(lambda: bl.build_graph_globals())
    s["get_node"] = call(lambda: e.get_node("kb:1"))
    return s


def c03_bulkloader_rerun_noskip(c, e):
    bl = bulkloader(c)
    s = {"load_nodes": call(lambda: bl.load_nodes([("kr:1", {"namespace": "A"})])),
         "load_nodes again skip_existing=False": call(lambda: bulkloader(c).load_nodes([("kr:1", {"namespace": "A"})], skip_existing=False)),
         "load_edges": call(lambda: bl.load_edges([("kr:1", "R", "kr:2", None)])),
         "load_edges again skip_existing=False": call(lambda: bulkloader(c).load_edges([("kr:1", "R", "kr:2", None)], skip_existing=False)),
         "rebuild_all_indices": call(lambda: bl.rebuild_all_indices())}
    return s


def c03_bulkloader_concurrent(c, e):
    def f(i, cc, ee):
        return bulkloader(cc).load_nodes([(f"kc:{j}", {"namespace": "A", "p": str(i)}) for j in range(50)])
    s = {"2 loaders, same 50 ids": concurrently(2, f)}
    s["rebuild_all_indices"] = call(lambda: bulkloader(c).rebuild_all_indices())
    return s


def c03_concurrent_create(c, e):
    s = {"create_node x4": concurrently(4, lambda i, cc, ee: ee.create_node("kx:1", labels=["A"], properties={"p": str(i)}))}
    s["create_edge x4"] = concurrently(4, lambda i, cc, ee: ee.create_edge("kx:1", "R", "kx:2"))
    s["bulk_create_nodes x3"] = concurrently(3, lambda i, cc, ee: ee.bulk_create_nodes(
        [{"id": f"ky:{j}", "labels": ["A"], "properties": {"p": str(i)}} for j in range(20)], graph="kgc"))
    s["store_node x4"] = concurrently(4, lambda i, cc, ee: ee.store_node("kz:1", properties={"p": str(i)}, labels=["A"]))
    return s


def c04_adjacency_churn(c, e):
    s = {}
    for n in ("ka:1", "ka:2", "ka:3"):
        e.create_node(n)

    def churn(i, cc, ee):
        for k in range(15):
            ee.create_edge("ka:1", "R", "ka:2")
            ee.delete_edge("ka:1", "R", "ka:2")
            ee.create_edge("ka:1", "R", f"ka:{2 + (k + i) % 2}")
        return "done"
    s["4 writers create/delete one triple"] = concurrently(4, churn)
    s["sync"] = call(lambda: e.sync())
    s["verify_graph"] = call(lambda: e.verify_graph())
    return s


def c04_multigraph(c, e):
    s = {"set_multigraph": call(lambda: e.set_multigraph("kmg", True))}
    for n in ("km:1", "km:2"):
        e.create_node(n, graph="kmg")
    s["parallel x3"] = [call(lambda: e.create_edge("km:1", "R", "km:2", graph="kmg")) for _ in range(3)]
    s["concurrent parallel x4"] = concurrently(4, lambda i, cc, ee: ee.create_edge("km:1", "R", "km:2", graph="kmg"))
    s["cypher parallel"] = call(lambda: e.execute_cypher("USE GRAPH 'kmg' MATCH (a {id:'km:1'}), (b {id:'km:2'}) CREATE (a)-[:R]->(b)").error)
    s["delete one"] = call(lambda: e.delete_edge("km:1", "R", "km:2", graph="kmg"))
    s["count #"] = call(lambda: c.o.get("^KG", "out", "kmg", "km:1", "R", "km:2", "#"))
    s["rows"] = call(lambda: c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id='kmg'")[0][0])
    s["verify_graph"] = call(lambda: e.verify_graph(graph="kmg"))
    return s


def c05_temporal(c, e):
    s = {}
    for n in ("kt:1", "kt:2"):
        e.create_node(n)
    s["insert x2 same key"] = [call(lambda: e.create_edge_temporal("kt:1", "R", "kt:2", timestamp=1_700_000_100)) for _ in range(2)]
    s["upsert x2 same key"] = [call(lambda: e.create_edge_temporal("kt:1", "R", "kt:2", timestamp=1_700_000_200, upsert=True)) for _ in range(2)]
    s["concurrent insert x4 same key"] = concurrently(4, lambda i, cc, ee: ee.create_edge_temporal("kt:1", "R", "kt:2", timestamp=1_700_000_300))
    s["window"] = call(lambda: len(e.get_edges_in_window(source="kt:1", predicate="R", start=1_700_000_000, end=1_700_001_000)))
    s["count agg"] = call(lambda: e.get_temporal_aggregate("kt:1", "R", "count", 1_700_000_000, 1_700_001_000))
    tout, tin = set(), set()
    for d, acc in (("tout", tout), ("tin", tin)):
        if int(c.o.isDefined("^KG", d, 0)):
            for ts, _ in c.o.iterator("^KG", d, 0).items():
                for a, _ in c.o.iterator("^KG", d, 0, ts).items():
                    for p, _ in c.o.iterator("^KG", d, 0, ts, a).items():
                        for b, _ in c.o.iterator("^KG", d, 0, ts, a, p).items():
                            acc.add((str(ts), str(a), str(p), str(b)) if d == "tout" else (str(ts), str(b), str(p), str(a)))
    s["tout_vs_tin"] = {"tout": len(tout), "tin": len(tin), "tout_only": sorted(tout - tin)[:3], "tin_only": sorted(tin - tout)[:3]}
    return s


def c08_cypher(c, e):
    def q(i, cc, ee, text):
        r = ee.execute_cypher(text)
        if r.error:
            raise RuntimeError(str(r.error)[:200])
        return len(r.rows)
    s = {"MERGE node x4": concurrently(4, lambda i, cc, ee: q(i, cc, ee, "MERGE (n:A {id: 'kq:1'}) RETURN n.id"))}
    s["CREATE node x2 seq"] = [call(lambda: e.execute_cypher("CREATE (n:A {id: 'kq:2'})").error) for _ in range(2)]
    s["MERGE rel x4"] = concurrently(4, lambda i, cc, ee: q(i, cc, ee, "MERGE (a:A {id: 'kq:1'}) MERGE (b:A {id: 'kq:3'}) MERGE (a)-[:R]->(b) RETURN a.id"))
    s["MERGE path x4"] = concurrently(4, lambda i, cc, ee: q(i, cc, ee, "MERGE (a:A {id: 'kq:5'})-[:R]->(b:A {id: 'kq:6'}) RETURN a.id"))
    s["CREATE rel literal x2"] = [call(lambda: e.execute_cypher("CREATE (a:A {id: 'kq:7'})-[:R]->(b:A {id: 'kq:8'})").error) for _ in range(2)]
    s["nodes kq:1"] = call(lambda: c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='kq:1'")[0][0])
    s["edges kq:1-kq:3"] = call(lambda: c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s='kq:1' AND o_id='kq:3'")[0][0])
    s["edges kq:5-kq:6"] = call(lambda: c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s='kq:5' AND o_id='kq:6'")[0][0])
    return s


def c15_reifier(c, e):
    s = {}
    for g in (None, "kr15"):
        e.create_node("kr:1", graph=g)
        e.create_node("kr:2", graph=g)
        e.create_edge("kr:1", "R", "kr:2", graph=g)
    ea = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE graph_id = ''")[0][0]
    eb = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE graph_id = 'kr15'")[0][0]
    s["reify A as r1"] = call(lambda: e.reify_edge(int(ea), reifier_id="kr:reif", props={"who": "A"}))
    s["reify B as r1"] = call(lambda: e.reify_edge(int(eb), reifier_id="kr:reif", props={"who": "B"}))
    s["reify A twice"] = call(lambda: e.reify_edge(int(ea), reifier_id="kr:reif2"))
    s["get_reifications A"] = call(lambda: e.get_reifications(int(ea)))
    s["get_reifications B"] = call(lambda: e.get_reifications(int(eb)))
    s["concurrent reify x3 same id"] = concurrently(3, lambda i, cc, ee: ee.reify_edge(int(ea), reifier_id="kr:reif3", props={"i": str(i)}))
    s["reifier rows"] = call(lambda: c.sql("SELECT reifier_id, edge_id FROM Graph_KG.rdf_reifications"))
    return s


def c17_store(c, e):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    st = IRISGraphStore(c.conn, namespace=lib.NS)
    s = {"write_nodes dup in batch": call(lambda: st.write_nodes([{"id": "ks:1", "labels": ["A"], "properties": {"p": "1"}},
                                                                   {"id": "ks:1", "labels": ["A"], "properties": {"p": "2"}}]).error)}
    s["write_nodes again"] = call(lambda: st.write_nodes([{"id": "ks:1", "labels": ["A", "B"], "properties": {"p": "3"}}]).error)
    s["write_edges dup in batch"] = call(lambda: st.write_edges([{"source": "ks:1", "predicate": "R", "target": "ks:2"},
                                                                  {"source": "ks:1", "predicate": "R", "target": "ks:2"}]).error)
    s["write_edges again"] = call(lambda: st.write_edges([{"source": "ks:1", "predicate": "R", "target": "ks:2"}]).error)

    def cw(i, cc, ee):
        r = IRISGraphStore(cc.conn, namespace=lib.NS).write_nodes([{"id": "ks:9", "labels": ["A"], "properties": {"p": str(i)}}])
        return r.error
    s["concurrent write_nodes x4"] = concurrently(4, cw)
    s["get_nodes"] = call(lambda: st.get_nodes(["ks:1", "ks:9"]).rows)
    return s


def c18_restore(c, e):
    import tempfile
    s = {}
    e.create_node("kn:1", labels=["A"], properties={"p": "1"})
    e.create_node("kn:2", labels=["A"])
    e.create_edge("kn:1", "R", "kn:2")
    e.create_node("kn:3", graph="k18")
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "s.zip")
        s["save"] = call(lambda: e.save_snapshot(p))
        s["restore merge over same content"] = call(lambda: e.restore_snapshot(p, merge=True))
        s["restore merge again"] = call(lambda: e.restore_snapshot(p, merge=True))
        e.create_node("kn:4")
        s["restore replace"] = call(lambda: e.restore_snapshot(p))
        s["restore replace again"] = call(lambda: e.restore_snapshot(p))
    return s


def c01_catalog(c, e):
    """Declared keys (the DDL text of setup) against the namespace's catalog after the pin's own initialize_schema."""
    import re
    from iris_vector_graph.schema import GraphSchema
    ddl = GraphSchema.get_base_schema_sql(embedding_dimension=4)
    declared = {}
    for m in re.finditer(r"CREATE TABLE(?: IF NOT EXISTS)?\s+Graph_KG\.(\w+)\s*\((.*?)\n\);?", ddl, re.S):
        t, body = m.group(1), m.group(2)
        for k in re.finditer(r"CONSTRAINT\s+(\w+)\s+(PRIMARY KEY|UNIQUE|FOREIGN KEY)\s*\(([^)]*)\)(?:\s*REFERENCES\s+Graph_KG\.(\w+)\s*\(([^)]*)\))?", body):
            declared[(t.lower(), k.group(1).lower())] = {"type": k.group(2), "cols": [x.strip().lower() for x in k.group(3).split(",")],
                                                         "ref": (k.group(4) or "").lower() or None}
        for k in re.finditer(r"^\s*(\w+)\s+[^,\n]*?\bPRIMARY KEY\b", body, re.M):
            if k.group(1).upper() != "CONSTRAINT":
                declared[(t.lower(), "inline-pk")] = {"type": "PRIMARY KEY", "cols": [k.group(1).lower()], "ref": None}
    cat = c.sql("SELECT tc.TABLE_NAME, tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "WHERE tc.TABLE_SCHEMA = 'Graph_KG'")
    cols = c.sql("SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, ORDINAL_POSITION FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                 "WHERE TABLE_SCHEMA = 'Graph_KG' ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION")
    ref = c.sql("SELECT CONSTRAINT_NAME, UNIQUE_CONSTRAINT_NAME FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS "
                "WHERE CONSTRAINT_SCHEMA = 'Graph_KG'")
    catalog = {}
    for t, n, ty in cat:
        catalog[(str(t).lower(), str(n).lower())] = {"type": str(ty), "cols": []}
    for t, n, col, _o in cols:
        k = (str(t).lower(), str(n).lower())
        if k in catalog:
            catalog[k]["cols"].append(str(col).lower())
    missing, extra, differ = [], [], []
    for k, v in declared.items():
        if k[1] == "inline-pk":
            hit = [x for x, y in catalog.items() if x[0] == k[0] and y["type"] == "PRIMARY KEY"]
            if not hit:
                missing.append(list(k))
            continue
        if k not in catalog:
            missing.append(list(k))
        elif catalog[k]["type"] != v["type"] or catalog[k]["cols"] != v["cols"]:
            differ.append({"key": list(k), "declared": v, "catalog": catalog[k]})
    for k, v in catalog.items():
        if k not in declared and not any(d[0] == k[0] and d[1] == "inline-pk" and v["type"] == "PRIMARY KEY" for d in declared):
            extra.append({"key": list(k), "catalog": v})
    return {"declared": len(declared), "catalog": len(catalog), "missing": missing, "differ": differ,
            "extra": extra, "referential": [[str(a), str(b)] for a, b in ref]}


CASES = [
    ("01-catalog-keys", "01", c01_catalog),
    ("03-sequential-duplicates", "03", c03_sequential),
    ("03-bulkloader-in-batch-duplicate", "03", c03_bulkloader_in_batch),
    ("03-bulkloader-rerun-skip_existing-false", "03", c03_bulkloader_rerun_noskip),
    ("03-bulkloader-concurrent", "03", c03_bulkloader_concurrent),
    ("03-concurrent-create", "03", c03_concurrent_create),
    ("04-adjacency-churn", "04", c04_adjacency_churn),
    ("04-multigraph", "04", c04_multigraph),
    ("05-temporal-keys", "05", c05_temporal),
    ("08-cypher-merge-create", "08", c08_cypher),
    ("15-reifier-ids", "15", c15_reifier),
    ("17-store-duplicates", "17", c17_store),
    ("18-restore-keys", "18", c18_restore),
]


def main() -> int:
    outp = Path(sys.argv[1])
    sel = sys.argv[2:]
    res = []
    for label, module, fn in CASES:
        if sel and not any(label.startswith(s) for s in sel):
            continue
        res.append(case(label, module, fn))
        lib.dump(outp, res)
    print(json.dumps({r["case"]: [r["outcome"], r.get("violations", [])[:3]] for r in res}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
