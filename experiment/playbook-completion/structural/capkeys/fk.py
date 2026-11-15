#!/usr/bin/env python3
"""§3.6 foreign keys, per module, live on AUDITD (observation only).

    locks.sh iris python fk.py OUT.json [case-prefix ...]

Oracle (fk_check), over full scans of the namespace after each case (a %NOCHECK row skips the declared FK):
  F1 every rdf_edges row has node rows (graph_id, s) and (graph_id, o_id)       [declared: fk_edges_source/dest]
  F2 every rdf_labels row has its node row                                      [declared: fk_labels_node]
  F3 every rdf_props row has its node row                                       [not declared; a property of no node]
  F4 every kg_NodeEmbeddings row has its node row                               [declared: fk_emb_node]
  F5 every ^KG("out"/"in", G, a, p, b) leaf has node rows a and b in graph G    [index referential condition]
     every ^KG("label", G, label, s) entry has its node row
  F6 every temporal ^KG("tout", G, ts, s, p, o) entry has node rows s and o in G [temporal endpoints are nodes:
     create_edge_temporal registers them, TemporalIndex/Adjacency AssertTemporalRow]
  F7 every rdf_reifications row names an existing rdf_edges row, and its reifier node exists
Each case runs one module's delete or write paths; the violations found are reported with the rows.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from keys import call, concurrently, kg_leaves, scan_from  # noqa: E402


def S(v):
    return "" if v is None else str(v)


def read_fk_state(c):
    st = {}
    st["nodes"] = [(S(n), S(g)) for n, g in c.sql(f"SELECT node_id, graph_id FROM {scan_from(c, 'Graph_KG.nodes')}")]
    st["edges"] = [(S(s), S(o), S(g), int(i)) for s, o, g, i in
                   c.sql(f"SELECT s, o_id, graph_id, edge_id FROM {scan_from(c, 'Graph_KG.rdf_edges')}")]
    st["labels"] = [(S(s), S(lb), S(g)) for s, lb, g in c.sql(f"SELECT s, label, graph_id FROM {scan_from(c, 'Graph_KG.rdf_labels')}")]
    st["props"] = [(S(s), S(k), S(g)) for s, k, g in c.sql(f"SELECT s, \"key\", graph_id FROM {scan_from(c, 'Graph_KG.rdf_props')}")]
    try:
        st["emb"] = [(S(n), S(g)) for n, g in c.sql(f"SELECT node_id, graph_id FROM {scan_from(c, 'Graph_KG.kg_NodeEmbeddings')}")]
    except Exception:  # noqa: BLE001
        st["emb"] = []
    st["kg_out"] = sorted(kg_leaves(c, "out"))
    st["kg_in"] = sorted(kg_leaves(c, "in"))
    lb = []
    if int(c.o.isDefined("^KG", "label")):
        for G, _ in c.o.iterator("^KG", "label").items():
            for lab, _ in c.o.iterator("^KG", "label", G).items():
                for s, _ in c.o.iterator("^KG", "label", G, lab).items():
                    lb.append((str(G), str(lab), str(s)))
    st["kg_label"] = lb
    tb = []
    if int(c.o.isDefined("^KG", "tout")):
        for G, _ in c.o.iterator("^KG", "tout").items():
            for ts, _ in c.o.iterator("^KG", "tout", G).items():
                for s, _ in c.o.iterator("^KG", "tout", G, ts).items():
                    for pp, _ in c.o.iterator("^KG", "tout", G, ts, s).items():
                        for o, _ in c.o.iterator("^KG", "tout", G, ts, s, pp).items():
                            tb.append((str(G), str(ts), str(s), str(pp), str(o)))
    st["kg_tout"] = tb
    st["reif"] = [(S(r), int(x)) for r, x in c.sql("SELECT reifier_id, edge_id FROM Graph_KG.rdf_reifications")]
    return st


def eval_fk(st):
    g0 = lambda g: "0" if g in ("", "\x00") else g  # noqa: E731
    nodes = {(g0(g), n) for n, g in st["nodes"]}
    v = {}
    v["F1 edge endpoint missing"] = [[s, o, g] for s, o, g, _ in st["edges"] if (g0(g), s) not in nodes or (g0(g), o) not in nodes][:5]
    v["F2 label of no node"] = [[s, lb, g] for s, lb, g in st["labels"] if (g0(g), s) not in nodes][:5]
    v["F3 property of no node"] = [[s, k, g] for s, k, g in st["props"] if (g0(g), s) not in nodes][:5]
    v["F4 embedding of no node"] = [[n, g] for n, g in st["emb"] if (g0(g), n) not in nodes][:5]
    v["F5 adjacency of no node"] = [["out" if x in st["kg_out"] else "in", *x] for x in (st["kg_out"] + st["kg_in"])
                                    if (x[0], x[1]) not in nodes or (x[0], x[3]) not in nodes][:5]
    v["F5 label index of no node"] = [list(x) for x in st["kg_label"] if (x[0], x[2]) not in nodes][:5]
    v["F6 temporal edge of no node"] = [list(x) for x in st["kg_tout"] if (x[0], x[2]) not in nodes or (x[0], x[4]) not in nodes][:5]
    eids = {x[3] for x in st["edges"]}
    names = {n for _g, n in nodes}
    v["F7 reification of no edge"] = [[r, x] for r, x in st["reif"] if x not in eids][:5]
    v["F7 reification of no reifier node"] = [[r, x] for r, x in st["reif"] if r not in names][:5]
    viol = [f"{k}: {x[:3]}" for k, x in v.items() if x]
    return {"by_condition": v, "violations": viol,
            "counts": {k: len(st[k]) for k in ("nodes", "edges", "labels", "props", "reif", "kg_out", "kg_tout")}}


def fk_check(c):
    return eval_fk(read_fk_state(c))


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
        chk = fk_check(c)
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
    print(json.dumps({k: v for k, v in r.items() if k != "check"}, default=str)[:1800], flush=True)
    return r


def base(e, g=None, pre="f"):
    for n in ("1", "2", "3"):
        e.create_node(f"{pre}:{n}", labels=["A"], properties={"p": n}, graph=g)
    e.create_edge(f"{pre}:1", "R", f"{pre}:2", graph=g)
    e.create_edge(f"{pre}:2", "R", f"{pre}:3", graph=g)


def c02_graphs(c, e):
    s = {}
    e.create_node("fg:1")
    e.create_node("fg:2")
    s["create_edge in g where endpoints are default-graph only"] = call(lambda: e.create_edge("fg:1", "R", "fg:2", graph="fg"))
    s["cypher USE GRAPH create between default nodes"] = call(lambda: e.execute_cypher(
        "USE GRAPH 'fg2' MATCH (a {id:'fg:1'}), (b {id:'fg:2'}) CREATE (a)-[:S]->(b)").error)
    s["delete_edge all_graphs"] = call(lambda: e.delete_edge("fg:1", "R", "fg:2", all_graphs=True))
    s["rows"] = call(lambda: c.sql("SELECT s, o_id, graph_id FROM Graph_KG.rdf_edges"))
    return s


def c03_delete_paths(c, e):
    s = {}
    base(e)
    s["delete_node f:2 (default)"] = call(lambda: e.delete_node("f:2"))
    base(e, g="fx", pre="fx")
    s["cypher DETACH DELETE fx:2"] = call(lambda: e.execute_cypher("USE GRAPH 'fx' MATCH (n {id:'fx:2'}) DETACH DELETE n").error)
    s["cypher DELETE fx:1 (has no edge now?)"] = call(lambda: e.execute_cypher("USE GRAPH 'fx' MATCH (n {id:'fx:1'}) DELETE n").error)
    base(e, g="fy", pre="fy")
    s["cypher DELETE node with edges, no DETACH"] = call(lambda: e.execute_cypher("USE GRAPH 'fy' MATCH (n {id:'fy:2'}) DELETE n").error)
    s["cypher REMOVE label"] = call(lambda: e.execute_cypher("USE GRAPH 'fy' MATCH (n {id:'fy:3'}) REMOVE n:A").error)
    return s


def c03_store_and_bulk(c, e):
    from iris_vector_graph.bulk_loader import BulkLoader
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    s = {}
    st = IRISGraphStore(c.conn, namespace=lib.NS)
    s["store write_edges to unknown endpoints"] = call(lambda: st.write_edges([{"source": "fs:1", "predicate": "R", "target": "fs:2"}]).error)
    bl = BulkLoader(c.conn, graph="fb")
    s["bulkloader load_edges unknown endpoints"] = call(lambda: bl.load_edges([("fb:1", "R", "fb:2", None)]))
    s["bulkloader rebuild"] = call(lambda: bl.rebuild_all_indices())
    s["bulk_create_edges unknown endpoints"] = call(lambda: e.bulk_create_edges([{"source_id": "fbc:1", "predicate": "R", "target_id": "fbc:2"}], graph="fbc"))
    s["store_edge unknown endpoints"] = call(lambda: e.store_edge("fse:1", "R", "fse:2"))
    s["bulk_create_nodes then delete_nodes_by_prefix"] = [call(lambda: e.bulk_create_nodes([{"id": "fp:1", "labels": ["A"], "properties": {"x": "1"}}])),
                                                         call(lambda: e.delete_nodes_by_prefix("fp:"))]
    return s


def c03_erase(c, e):
    s = {}
    base(e, g="fe", pre="fe")
    e.create_edge_temporal("fe:1", "T", "fe:3", timestamp=1_700_000_000, graph="fe")
    base(e, pre="fz")
    e.create_edge_temporal("fz:1", "T", "fz:3", timestamp=1_700_000_000)
    s["erase_graph fe"] = call(lambda: e.erase_graph("fe"))
    s["delete_nodes_by_prefix fz:"] = call(lambda: e.delete_nodes_by_prefix("fz:"))
    return s


def c04_adjacency_after_deletes(c, e):
    s = {}
    base(e, pre="fa")
    s["4 concurrent delete_node fa:2 / create_edge fa:1-fa:2"] = concurrently(4, lambda i, cc, ee: (
        ee.delete_node("fa:2") if i % 2 == 0 else ee.create_edge("fa:1", "R", "fa:2")))
    s["sync"] = call(lambda: e.sync())
    return s


def c05_temporal(c, e):
    s = {}
    for n in ("ft:1", "ft:2", "ft:3"):
        e.create_node(n)
    s["temporal edges"] = [call(lambda: e.create_edge_temporal("ft:1", "T", "ft:2", timestamp=1_700_000_000)),
                           call(lambda: e.create_edge_temporal("ft:2", "T", "ft:3", timestamp=1_700_000_100))]
    s["temporal edge with unknown endpoints"] = call(lambda: e.create_edge_temporal("ftu:1", "T", "ftu:2", timestamp=1_700_000_200))
    s["delete_node ft:2"] = call(lambda: e.delete_node("ft:2"))
    s["window after"] = call(lambda: e.get_edges_in_window(source="", predicate="T", start=1_699_999_999, end=1_700_000_300))
    return s


def c05_temporal_structural_off(c, e):
    s = {}
    for n in ("fo:1", "fo:2"):
        e.create_node(n)
    s["create_edge_temporal"] = call(lambda: e.create_edge_temporal("fo:1", "T", "fo:2", timestamp=1_700_000_000))
    s["drop_temporal_structural_rows"] = call(lambda: e.drop_temporal_structural_rows())
    s["delete_node fo:1"] = call(lambda: e.delete_node("fo:1"))
    return s


def c15_reification(c, e):
    s = {}
    base(e, pre="fr")
    eid = int(c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='fr:1'")[0][0])
    eid2 = int(c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='fr:2'")[0][0])
    s["reify fr:1->fr:2"] = call(lambda: e.reify_edge(eid, reifier_id="fr:r1", props={"w": "1"}))
    s["reify fr:2->fr:3"] = call(lambda: e.reify_edge(eid2, reifier_id="fr:r2"))
    s["delete_edge fr:1-fr:2"] = call(lambda: e.delete_edge("fr:1", "R", "fr:2"))
    s["cypher DELETE r fr:2-fr:3"] = call(lambda: e.execute_cypher("MATCH (a {id:'fr:2'})-[r:R]->(b {id:'fr:3'}) DELETE r").error)
    s["get_reifications of deleted edge"] = call(lambda: e.get_reifications(eid))
    s["delete_reification of a plain node"] = call(lambda: e.delete_reification("fr:3"))
    return s


CASES = [
    ("02-graph-scoped-endpoints", "02", c02_graphs),
    ("03-delete-paths", "03", c03_delete_paths),
    ("03-store-bulk-endpoints", "03", c03_store_and_bulk),
    ("03-erase-paths", "03", c03_erase),
    ("04-adjacency-concurrent-delete", "04", c04_adjacency_after_deletes),
    ("05-temporal-endpoints", "05", c05_temporal),
    ("05-temporal-structural-rows-dropped", "05", c05_temporal_structural_off),
    ("15-reification-edge-fk", "15", c15_reification),
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
    print(json.dumps({r["case"]: [r["outcome"], r.get("violations", [])[:4]] for r in res}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
