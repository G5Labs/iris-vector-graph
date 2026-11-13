"""Validate declared writer footprints (footprints/NN.json) against the IRIS journal (traces/journal.py) in AUDITA.

    bash experiment/playbook-completion/tools/locks.sh iris \
        python experiment/playbook-completion/live/breadth-a/journal_validate.py [J01 ...]

For each candidate of models/breadth-a/inventory/journal-candidates.json: set up in a fresh graph, mark the journal,
run the one operation, read the records of database /usr/irissys/mgr/audita/, and compare:
- observed write set (store names: SQL table through the compiled storage map, or global root with its first subscript
  for the kind-first roots ^KG, ^NKG, ^IVG.Ledger) against the footprint's declared `writes`;
- transaction structure: per process, the outermost transactions and whether each record was inside one; a record
  journaled outside a transaction while its process had one open is a non-transactional write ($Increment, P-0401).
Writes the result to live/breadth-a/journal/<Jnn>.json and a summary; nothing is compared by reading the source again.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import traceback
from pathlib import Path

from probe_lib import DB, J, ROOT, conn, engine, erase, gname

OUT = Path(__file__).resolve().parent / "journal"
LOG = Path(os.environ["RUN_DIR"]) / "breadth-a" / "journal"
KIND_FIRST = ("^KG", "^NKG", "^IVG.Ledger")


def store_name(node: str, smap) -> str:
    s = J.store_of(node, smap)
    if s.startswith("sql:"):
        return s
    root = J.global_root(node)
    if root.startswith("^IRIS.IF."):
        return "index-internal:" + root  # iFind word/transformation globals of an SQL iFind index
    if root in KIND_FIRST and "(" in node:
        first = node.split("(", 1)[1]
        if first.startswith('"'):
            return f'global:{root}("{first[1:].split(chr(34), 1)[0]}")'
    return "global:" + root


def declared(fp_module: str, fp_id: str):
    fp = json.loads((ROOT / "footprints" / f"{fp_module}.json").read_text())
    for e in fp["entry_points"]:
        if e["id"] == fp_id:
            return e
    return None


def analyse(recs, smap):
    open_ = {}
    units = []
    rows = []
    for r in recs:
        p, t = r["p"], r["t"]
        if t.startswith("BeginTrans"):
            if p not in open_:
                open_[p] = {"pid": p, "begin": r["a"], "levels": 1, "stores": set(), "nontxn_inside": set()}
            else:
                open_[p]["levels"] += 1
            continue
        if t.startswith("CommitTrans"):
            if t == "CommitTrans" and p in open_:
                u = open_.pop(p)
                u["end"] = "commit"
                units.append(u)
            continue
        if t.startswith("RollbackTrans") or t == "Rollback":
            if p in open_:
                u = open_.pop(p)
                u["end"] = "rollback"
                units.append(u)
            continue
        if not r["g"]:
            continue
        st = store_name(r["g"], smap)
        inside = p in open_
        rows.append({"pid": p, "store": st, "x": r["x"], "open": inside, "t": t})
        if inside and r["x"]:
            open_[p]["stores"].add(st)
        elif inside:
            open_[p]["nontxn_inside"].add(st)
    for u in open_.values():
        u["end"] = "open-at-capture-end"
        units.append(u)
    outside = sorted({(x["pid"], x["store"]) for x in rows if not x["open"]})
    return {
        "pids": sorted({x["pid"] for x in rows}),
        "stores_written": sorted({x["store"] for x in rows}),
        "outermost_transactions": [{"pid": u["pid"], "end": u["end"], "nesting_levels": u["levels"],
                                    "stores_in_txn": sorted(u["stores"]),
                                    "non_transactional_inside": sorted(u["nontxn_inside"])} for u in units],
        "written_with_no_transaction_open": [f"{p} {s}" for p, s in outside],
        "records": len(rows),
    }


def compare(observed_stores, decl):
    dw = {w["store"] for w in (decl or {}).get("writes", [])}
    roots = {d.split("(", 1)[0] for d in dw}
    undeclared = []
    for s in observed_stores:
        if s.startswith("index-internal:"):
            continue
        if s in dw:
            continue
        root = s.split("(", 1)[0]
        if root in roots and root.replace("global:", "") not in KIND_FIRST:
            continue
        undeclared.append(s)
    declared_not_seen = sorted(d for d in dw if d not in observed_stores and
                               not any(o.split("(", 1)[0] == d.split("(", 1)[0] for o in observed_stores))
    return sorted(undeclared), declared_not_seen


# ---- candidates: (module, footprint id, setup(c, eng, o, G) -> ctx, action(c, eng, o, G, ctx), cleanup) ----

def _n(eng, G, *ids):
    for i in ids:
        eng.create_node(i, graph=G)


CANDS = {
    "J01": ("03", "py:IRISGraphEngine.create_node", None,
            lambda c, e, o, G, x: e.create_node("jv_n1", labels=["L"], properties={"k": "v"}, graph=G)),
    "J02": ("03", "py:IRISGraphEngine.create_edge", None,
            lambda c, e, o, G, x: e.create_edge("jv_a", "R", "jv_b", weight=2.0, graph=G)),
    "J03": ("03", "py:IRISGraphEngine.store_edge",
            lambda c, e, o, G: e.create_edge_temporal("jv_s", "T", "jv_t", timestamp=1700000000, graph=G),
            lambda c, e, o, G, x: e.store_edge("jv_s", "T", "jv_t", qualifiers={"w": 1}, graph=G)),
    "J03b": ("03", "py:IRISGraphEngine.store_edge", None,
             lambda c, e, o, G, x: e.store_edge("jv_s", "T", "jv_t", qualifiers={"w": 1}, graph=G)),
    "J04": ("03", "py:IRISGraphEngine.delete_edge",
            lambda c, e, o, G: e.create_edge("jv_a", "R", "jv_b", graph=G),
            lambda c, e, o, G, x: e.delete_edge("jv_a", "R", "jv_b", graph=G)),
    "J05": ("03", "py:IRISGraphEngine.bulk_create_nodes", lambda c, e, o, G: e.capabilities,
            lambda c, e, o, G, x: e.bulk_create_nodes([{"id": f"{G}_b{i}", "labels": ["B"]} for i in range(2500)],
                                                      disable_indexes=False)),
    "J06": ("03", "py:IRISGraphEngine.bulk_ingest_edges", lambda c, e, o, G: e.capabilities,
            lambda c, e, o, G, x: e.bulk_ingest_edges([{"s": f"{G}_e{i}", "o": f"{G}_e{i+1}"} for i in range(1500)],
                                                      predicate="JV", auto_sync=False)),
    "J07": ("03", "py:iris_vector_graph.bulk_loader.BulkLoader.load_edges",
            lambda c, e, o, G: (__import__("iris_vector_graph.bulk_loader", fromlist=["BulkLoader"]).BulkLoader(
                c.conn, graph=G, batch_size=100), _n(e, G, "jv_l0", "jv_l1", "jv_l2"))[0],
            lambda c, e, o, G, bl: bl.load_edges([("jv_l0", "LL", "jv_l1", None), ("jv_l1", "LL", "jv_l2", None)])),
    "J08": ("02", "py:IRISGraphEngine.set_multigraph", lambda c, e, o, G: e.set_multigraph(G, True),
            lambda c, e, o, G, x: e.set_multigraph(G, False)),
    "J09": ("04", "cls:Graph.KG.Adjacency.PutShadow",
            lambda c, e, o, G: o.classMethodValue("Graph.KG.Adjacency", "PutShadow", G, "jv_p", "W", "jv_q", "1.0"),
            lambda c, e, o, G, x: o.classMethodValue("Graph.KG.Adjacency", "PutShadow", G, "jv_p", "W", "jv_q", "5.0")),
    "J10": ("04", "cls:Graph.KG.Adjacency.Reweight", lambda c, e, o, G: e.create_edge("jv_r", "RW", "jv_s2", graph=G),
            lambda c, e, o, G, x: o.classMethodValue("Graph.KG.Adjacency", "Reweight", G, "jv_r", "RW", "jv_s2", "3.0")),
    "J11": ("04", "cls:Graph.KG.Adj.Degree",
            lambda c, e, o, G: (e.create_edge("jv_d", "D", "jv_e", graph=G), o.kill("^KG", "degc", G, "jv_d")),
            lambda c, e, o, G, x: o.classMethodValue("Graph.KG.Adj", "Degree", G, "jv_d", "")),
    "J12": ("04", "py:IRISGraphEngine.sync", lambda c, e, o, G: e.create_edge("jv_y1", "S", "jv_y2", graph=G),
            lambda c, e, o, G, x: e.sync()),
    "J13": ("05", "py:IRISGraphEngine.create_edge_temporal", None,
            lambda c, e, o, G, x: e.create_edge_temporal("jv_ta", "TT", "jv_tb", timestamp=1700000000, weight=2.0,
                                                         graph=G)),
    "J14": ("05", "py:IRISGraphEngine.create_edge_temporal",
            lambda c, e, o, G: e.create_edge_temporal("jv_u", "TU", "jv_v", timestamp=1700000100, weight=1.0, graph=G),
            lambda c, e, o, G, x: e.create_edge_temporal("jv_u", "TU", "jv_v", timestamp=1700000100, weight=5.0,
                                                         graph=G, mode="update")),
    "J15": ("05", "py:IRISGraphEngine.delete_edge_temporal",
            lambda c, e, o, G: (e.create_edge("jv_x", "TX", "jv_y", qualifiers={"temporal": 1}, graph=G),
                                e.create_edge_temporal("jv_x", "TX", "jv_y", timestamp=1700000200, graph=G)),
            lambda c, e, o, G, x: e.delete_edge_temporal("jv_x", "TX", "jv_y", 1700000200, graph=G)),
    "J17": ("06", "py:IRISGraphEngine.store_embedding", lambda c, e, o, G: e.create_node("jv_v1", graph=G),
            lambda c, e, o, G, x: e.store_embedding("jv_v1", [0.1, 0.2, 0.3, 0.4], graph=G)),
    "J18": ("06", "py:IRISGraphEngine.store_embeddings", None,
            lambda c, e, o, G, x: e.store_embeddings([{"node_id": "jv_missing", "embedding": [0.1, 0.2, 0.3, 0.4]}],
                                                     graph=G + "_fresh", model_key="jv-model")),
    "J19": ("06", "cls:Graph.KG.IVFIndex.Insert",
            lambda c, e, o, G: ([(e.create_node(f"jv_i{i}", graph=G), e.store_embedding(f"jv_i{i}", v, graph=G))
                                 for i, v in enumerate([[1, 0, 0, 0], [0.9, 0.1, 0, 0], [0, 0, 1, 0], [0, 0, 0.9, 0.1]])],
                                e.ivf_build(G + "_ivf", nlist=2, metric="dot", graph=G)),
            lambda c, e, o, G, x: e.ivf_insert(G + "_ivf", "jv_i0", [0, 0, 1, 0])),
    "J20": ("06", "cls:Graph.KG.EmbedQueue.ProcessBatch",
            lambda c, e, o, G: (e.create_node(G + "_q1"),
                                o.classMethodValue("Graph.KG.EmbedQueue", "Enqueue", G + "_q1", "jv-no-such-config",
                                                   "hello", "")),
            lambda c, e, o, G, x: o.classMethodValue("Graph.KG.EmbedQueue", "ProcessBatch", 10, 5)),
    "J16": ("05", "cls:Graph.KG.TemporalIndex.Purge",
            lambda c, e, o, G: e.create_edge_temporal("jv_pa", "TP", "jv_pb", timestamp=1700000300, graph=G),
            lambda c, e, o, G, x: o.classMethodVoid("Graph.KG.TemporalIndex", "Purge")),
    "J21": ("01", "py:IRISGraphEngine.initialize_schema", None, lambda c, e, o, G, x: e.initialize_schema()),
}

CLEANUP = {
    "J05": lambda c, e, G: (c.sql("DELETE FROM Graph_KG.rdf_labels WHERE graph_id = '' AND s %STARTSWITH ?", G),
                            c.sql("DELETE FROM Graph_KG.rdf_props WHERE graph_id = '' AND s %STARTSWITH ?", G),
                            c.sql("DELETE FROM Graph_KG.nodes WHERE graph_id = '' AND node_id %STARTSWITH ?", G)),
    "J06": lambda c, e, G: e.bulk_delete_nodes([f"{G}_e{i}" for i in range(1501)]) if hasattr(e, "bulk_delete_nodes")
    else None,
    "J19": lambda c, e, G: e.ivf_drop(G + "_ivf"),
    "J20": lambda c, e, G: [c.o.kill("^EmbedQueue", k) for k in _queue_ids(c)
                            if str(c.o.get("^EmbedQueue", k, "node_id")) == G + "_q1"],
}


def _queue_ids(c):
    out, k = [], ""
    while True:
        k = c.o.nextSubscript(False, "^EmbedQueue", k)
        if k in (None, ""):
            return out
        if k != "$seq":
            out.append(k)


def main(argv):
    OUT.mkdir(parents=True, exist_ok=True)
    LOG.mkdir(parents=True, exist_ok=True)
    want = argv or [k for k in CANDS if k not in ("J16", "J21")] + ["J16"]
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log = LOG / f"journal-{stamp}.log"
    lines = []
    c, eng = engine()
    smap = J.storage_map(c)
    for jid in want:
        mod, fid, setup, action = CANDS[jid]
        G = gname("j" + jid[1:].lower())
        res = {"id": jid, "module": mod, "footprint": fid, "graph": G, "namespace": "AUDITA", "conn_pid": c.pid}
        try:
            ctx = setup(c, eng, c.o, G) if setup else None
            m = J.mark()
            t = time.time()
            try:
                out = action(c, eng, c.o, G, ctx)
                res["call"] = f"returned {str(out)[:200]}"
            except Exception as ex:
                res["call"] = f"raised {type(ex).__name__}: {str(ex)[:300]}"
            res["seconds"] = round(time.time() - t, 2)
            recs = J.records_since(m, dbs={DB})
            res["observed"] = analyse(recs, smap)
            decl = declared(mod, fid)
            res["declared_found"] = decl is not None
            res["declared_writes"] = sorted({w["store"] for w in (decl or {}).get("writes", [])})
            und, unseen = compare(res["observed"]["stores_written"], decl)
            res["undeclared_writes"] = und
            res["declared_not_observed_this_run"] = unseen
            res["verdict"] = "footprint covers every observed write" if not und else "undeclared writes observed"
        except Exception:
            res["error"] = traceback.format_exc()
            res["verdict"] = "harness error"
        finally:
            try:
                if jid in CLEANUP:
                    CLEANUP[jid](c, eng, G)
            except Exception as ex:
                res["cleanup_error"] = str(ex)[:200]
            erase(eng, G, G + "_fresh")
        res["log"] = "$RUN_DIR/" + str(log.relative_to(Path(os.environ["RUN_DIR"])))
        (OUT / f"{jid}.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
        line = f"{jid} {fid}: {res['verdict']}; call {res.get('call', '')[:80]}; pids {res.get('observed', {}).get('pids')}; " \
               f"txns {[(u['pid'], u['end'], len(u['stores_in_txn'])) for u in res.get('observed', {}).get('outermost_transactions', [])]}; " \
               f"undeclared {res.get('undeclared_writes')}; outside-txn {res.get('observed', {}).get('written_with_no_transaction_open')}"
        print(line, flush=True)
        lines.append(line)
        lines.append(json.dumps(res, sort_keys=True, default=str))
    log.write_text("\n".join(lines) + "\n")
    print("log:", log)
    c.close()


if __name__ == "__main__":
    main(sys.argv[1:])
