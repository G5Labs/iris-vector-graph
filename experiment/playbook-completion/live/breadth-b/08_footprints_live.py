#!/usr/bin/env python3
"""Module 08 write footprints validated by the IRIS journal (playbook §3.4 declared writes, §3.7 statement log).

    python experiment/playbook-completion/live/breadth-b/08_footprints_live.py

For each Cypher write shape (SQL path), the declared write set (from reading the translator's statements and the
functional-index callbacks at the pin; see footprints/08.json) is compared with the stores the journal shows the
operation's process wrote. The journal also says which records were inside a transaction: the atomicity claim
(USER_GUIDE.md:266-271, query.py:1946-1966: one write_txn per query, rollback on error) requires every row/global
write of one query in one outermost transaction, and a failed query to leave no net effect. Records outside a
transaction are listed and classified (an IRIS $INCREMENT row-id counter is not transactional by design).
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c08", HERE / "08_common.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

ROWS = {"sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.rdf_edges"}

# Declared write sets (source reading; see footprints/08.json for the citations).
DECL = {
    "create_node": ROWS - {"sql:Graph_KG.rdf_edges"} | {"global:^KG"},
    "create_edge_literal": ROWS | {"global:^KG", "global:^NKG"},
    "merge_node_on_create": ROWS - {"sql:Graph_KG.rdf_edges"} | {"global:^KG"},
    "set_remove": {"sql:Graph_KG.rdf_props", "sql:Graph_KG.rdf_labels", "global:^KG"},
    "delete_edge": {"sql:Graph_KG.rdf_edges", "global:^KG", "global:^NKG"},
    "detach_delete": ROWS | {"global:^KG", "global:^NKG"},
    "foreach_literal": ROWS - {"sql:Graph_KG.rdf_edges"} | {"global:^KG"},
    "failed_duplicate_edge": ROWS | {"global:^KG", "global:^NKG"},
    "read_only_query": set(),
    "caller_transaction": ROWS | {"global:^KG", "global:^NKG"},
}


def classify_outside(rec, smap):
    g = rec["g"]
    st = C.J.store_of(g, smap)
    if re.fullmatch(r"\^t52S\.\w+\.1", g):
        return "row-id counter ($INCREMENT on the extent's data global root; not transactional in IRIS)"
    if re.match(r'\^t52S\.DMCe\.7\("W",', g):
        return "iFind word dictionary of rdf_props.idx_props_val_ifind (%iFind.Index.Basic; not transactional in IRIS)"
    if g.startswith('^KG("__version")'):
        return "adjacency version token $INCREMENT (Adjacency.cls:91; survives rollback by design)"
    if g.startswith('^KG("gen",'):
        return "degree-cache generation $INCREMENT (Adjacency.cls:23-30; survives rollback by design)"
    if g.startswith("^NKG(-3,") or g.startswith('^NKG("$meta",'):
        return "^NKG counter $INCREMENT (Adjacency.cls:95-107; survives rollback: F-C0801)"
    if C.J.global_root(g) in ("^oddTSQL", "^oddEXTR", "^rINDEXSQL"):
        return "IRIS SQL statement cache (system)"
    return "UNCLASSIFIED"


def net_effect_bits(records):
    """Net effect per node handling SET/KILL/ZKILL and BitSET (journal.net_effect treats BitSET as a kill)."""
    import base64 as _b
    first, last, bits = {}, {}, {}
    for r in records:
        g = r["g"]
        if not g:
            continue
        if r["t"].lower() == "bitset":
            n = _b.b64decode(r["n"]).decode() if r["n"] else "0"
            o = _b.b64decode(r["o"]).decode() if r["o"] else "0"
            bits[g] = bits.get(g, 0) + (1 if (n, o) == ("1", "0") else -1 if (n, o) == ("0", "1") else 0)
            continue
        if g not in first:
            first[g] = r["o"]
        last[g] = r["n"] if r["t"] == "SET" else None
    out = {g: v for g, v in last.items() if v != first[g]}
    out.update({g + " [bits]": v for g, v in bits.items() if v})
    return out


def analyse(name, cap, smap, pid):
    recs = [r for r in cap.records if r["p"] == pid]
    stores = sorted({C.J.store_of(r["g"], smap) for r in recs if r["g"]})
    data_stores = {x for x in stores if not x.startswith("global:^odd")}
    tx = C.J.transactions(recs)
    outer = [u for u in tx if u["kind"] == "txn"]
    outside = [r for r in recs if r["g"] and not r["x"]]
    out_cls = {}
    for r in outside:
        k = classify_outside(r, smap)
        out_cls.setdefault(k, []).append(f'{r["t"]} {r["g"][:90]}')
    inside_stores = sorted({C.J.store_of(r["g"], smap) for u in outer for r in u["records"] if r["g"]})
    net = {}
    for u in outer:
        net.update(net_effect_bits(u["records"]))
    decl = DECL.get(name, set())
    return {"error": cap.error, "observed_stores": stores, "declared_stores": sorted(decl),
            "undeclared": sorted(data_stores - decl - {"global:^oddTSQL"}),
            "declared_not_observed": sorted(decl - data_stores),
            "outermost_transactions": len(outer),
            "txn_detail": [{"committed": u["committed"], "nested_levels": u["nested_levels"], "n": len(u["records"]),
                            "rolled_back(net empty)": u.get("rolled_back")} for u in outer],
            "inside_txn_stores": inside_stores, "outside_txn": out_cls,
            "net_effect_nodes": len(net),
            "net_effect_sample": sorted(net)[:12]}


def main():
    R = {}
    with C.session08("08-footprints", native_cypher=False) as s:
        R["ledger_meta"] = C.ledger_meta(s)
        if R["ledger_meta"].get("strict"):
            R["skipped"] = "ledger strict on"
            print(C.write_log(s, R, name="08-footprints"))
            return
        R["cleanup_before"] = C.cleanup(s)
        pid = s.c.pid
        shapes = [
            ("create_node", "CREATE (:B08J {id:'b08_j1', name:'x'})"),
            ("create_edge_literal", "CREATE (a:B08J {id:'b08_j2'})-[:B08T]->(b:B08J {id:'b08_j3'})"),
            ("merge_node_on_create", "MERGE (n:B08J {id:'b08_j4'}) ON CREATE SET n.c = 1"),
            ("set_remove", "MATCH (n:B08J {id:'b08_j1'}) SET n.k = 'v', n:B08K REMOVE n.name"),
            ("delete_edge", "MATCH (:B08J {id:'b08_j2'})-[r:B08T]->() DELETE r"),
            ("detach_delete", "MATCH (n:B08J {id:'b08_j4'}) DETACH DELETE n"),
            ("foreach_literal", "FOREACH (x IN [1, 2] | CREATE (:B08F {v: x}))"),
            ("failed_duplicate_edge", "CREATE (c:B08J {id:'b08_j9'}), (a:B08J {id:'b08_j5'})-[:B08T]->(b:B08J {id:'b08_j6'})"),
            ("read_only_query", "MATCH (n:B08J) RETURN count(n) AS c"),
        ]
        C.run(s, "CREATE (a:B08J {id:'b08_j5'})-[:B08T]->(b:B08J {id:'b08_j6'})")  # makes the last write a duplicate
        for name, q in shapes:
            cap = C.capture(s, (lambda q=q: s.eng.execute_cypher(q)), pids={pid})
            R[name] = {"query": q, **analyse(name, cap, s.smap, pid)}
        # caller transaction: IVG's part nests; a failed write takes back only its own part (CYP-I6.3)
        def caller_txn():
            cur = s.c.conn.cursor()
            cur.execute("START TRANSACTION")
            s.eng.execute_cypher("CREATE (:B08J {id:'b08_ct1'})")
            mid_level = s.c.sql("SELECT $TLEVEL")[0][0]
            failed = None
            try:
                s.eng.execute_cypher("CREATE (a:B08J {id:'b08_j5'})-[:B08T]->(b:B08J {id:'b08_j6'})")
            except Exception as e:  # noqa: BLE001
                failed = type(e).__name__
            after_fail_level = s.c.sql("SELECT $TLEVEL")[0][0]
            ct1_visible = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_ct1'")[0][0]
            cur.execute("ROLLBACK")
            cur.close()
            return {"tlevel_after_first_write": mid_level, "second_write": failed, "tlevel_after_failure": after_fail_level,
                    "caller_work_visible_after_failure": ct1_visible}
        cap = C.capture(s, caller_txn, pids={pid})
        ct1_after = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_ct1'")[0][0]
        R["caller_transaction"] = {"observed": cap.result, "error": cap.error, "b08_ct1_after_caller_rollback": ct1_after,
                                   **analyse("caller_transaction", cap, s.smap, pid)}
        R["cleanup_after"] = C.cleanup(s)
        p = C.write_log(s, R, name="08-footprints")
    print(p)
    for k, v in R.items():
        if isinstance(v, dict) and "observed_stores" in v:
            print(k, "| err:", (v["error"] or "")[:60], "| undeclared:", v["undeclared"], "| missing:", v["declared_not_observed"],
                  "| txns:", v["txn_detail"], "| outside:", {a: len(b) for a, b in v["outside_txn"].items()})
    print("caller", R["caller_transaction"]["observed"], R["caller_transaction"]["b08_ct1_after_caller_rollback"])


if __name__ == "__main__":
    main()
