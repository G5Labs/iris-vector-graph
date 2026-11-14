#!/usr/bin/env python3
"""§3.6 well-formedness under row permutation, live on AUDITD (structural lane, observation only).

    locks.sh iris timeout 1200 python permutation.py OUT.json MOD[,MOD...] | selftest

Per module, one small dataset is written through the product's own writers in three insertion orders (forward,
reverse, a fixed shuffle). Between orders the namespace is emptied by lib.reset (the product's EraseAll/PurgeAll), so
rows get new row ids in a different order while their keys stay the same. The module's read APIs then answer, and the
answers of the three orders are compared:
  set     multiset equality after deep canonicalisation (every list sorted): APIs that promise no order;
  list    exact equality: APIs whose contract includes an order or a top-k/paging cut (cited per read);
  sample  allowed to differ where the contract is a documented sample, but every answer must pass the read's
          well-formedness validator (a valid sample of the data).
Generated identities (edge ids, revision ids, timestamps, hashes) are normalised out where noted, except where the
identity is the subject (F-C1108). A difference in a set/list read, or a sample failing its validator, is a finding.

selftest: two harness-own readers over the same insertion orders: SELECT TOP 1 ... FROM %IGNOREINDEX * (storage
order) must be flagged, SELECT ... ORDER BY node_id must not.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import random
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
import lib  # noqa: E402

ORDERS = ("forward", "reverse", "shuffle")


def permute(items, order):
    items = list(items)
    if order == "reverse":
        return items[::-1]
    if order == "shuffle":
        r = random.Random(20261114)
        x = items[:]
        r.shuffle(x)
        if x == items or x == items[::-1]:
            x = items[1:] + items[:1]
        return x
    return items


def canon(x, deep_sort):
    if isinstance(x, dict):
        return {str(k): canon(v, deep_sort) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple, set, frozenset)):
        v = [canon(i, deep_sort) for i in x]
        if deep_sort or isinstance(x, (set, frozenset)):
            v = sorted(v, key=lambda i: json.dumps(i, sort_keys=True, default=str))
        return v
    if isinstance(x, float):
        return round(x, 9)
    if hasattr(x, "__dict__") and not isinstance(x, type):
        return canon({k: v for k, v in vars(x).items() if not k.startswith("_")}, deep_sort)
    if x is None or isinstance(x, (int, str, bool)):
        return x
    try:
        return round(float(x), 9)  # Decimal (driver 5.3.2 answers scores as Decimal, F-C1706)
    except Exception:  # noqa: BLE001
        return str(x)


def call(fn):
    try:
        return fn()
    except Exception as ex:  # noqa: BLE001
        return {"error": f"{type(ex).__name__}: {str(ex)[:200]}"}


# ------------------------------------------------------------------------------------------------ scenarios
# each: (writes(e, c, order) -> None, reads(e, c) -> {name: (mode, value, basis)}, validators {name: fn(value) -> ok})

def m01():
    nodes = [("pm:a", ["L1"], {"k1": "1"}), ("pm:b", ["L1"], {"k2": "1"}), ("pm:c", ["L1", "L3"], {"k3": "1"}),
             ("pm:x", ["L2"], {"kx": "1"}), ("pm:y", ["L3"], {"ky": "1"})]
    edges = [("pm:a", "R", "pm:x"), ("pm:c", "R", "pm:y"), ("pm:b", "R", "pm:x")]

    def writes(e, c, order):
        for n, l, p in permute(nodes, order):
            e.create_node(n, labels=l, properties=p)
        for s, p, o in permute(edges, order):
            e.create_edge(s, p, o)

    def reads(e, c):
        return {"get_schema_visualization": ("sample", call(e.get_schema_visualization),
                                             "_engine/schema.py:2772-2779 'Sampled, not exact'")}

    keys_by_label = {}
    for n, ls, p in nodes:
        for l in ls:
            keys_by_label.setdefault(l, []).append(sorted(p))
    labels_of = {n: set(ls) for n, ls, p in nodes}

    def valid(v):
        if not isinstance(v, dict) or "error" in v:
            return False
        names = {n["id"]: n["name"] for n in v.get("nodes", [])}
        for n in v.get("nodes", []):
            ks = sorted(x["name"] for x in n["properties"] if x["name"] != "id")  # the stored id property every node carries
            if ks not in keys_by_label.get(n["name"], []):
                return False
        for r in v.get("relationships", []):
            sl, el = names.get(r.get("startNode", r.get("start"))), names.get(r.get("endNode", r.get("end")))
            ok = any(sl in labels_of[s] and el in labels_of[o] for s, p, o in edges if p == r.get("type", r.get("name")))
            if not ok and (sl is not None or el is not None):
                return False
        return True
    return writes, reads, {"get_schema_visualization": valid}


def m02():
    data = [("pg:1", ""), ("pg:2", ""), ("pg:1", "pg1"), ("pg:3", "pg1"), ("pg:1", "pg2"), ("pg:4", "pg2")]

    def writes(e, c, order):
        for n, g in permute(data, order):
            e.create_node(n, labels=["G"], properties={"g": g or "default"}, graph=g or None)
        e.create_edge("pg:1", "R", "pg:3", graph="pg1")
        e.create_edge("pg:1", "R", "pg:4", graph="pg2")

    def reads(e, c):
        return {
            "list_graphs": ("set", call(e.list_graphs), "no order promised"),
            "count_nodes_pg1": ("set", call(lambda: e.count_nodes(graph="pg1")), ""),
            "get_nodes_pg2": ("set", call(lambda: e.get_nodes(["pg:1", "pg:4"], graph="pg2")), ""),
            "get_node_default": ("set", call(lambda: e.get_node("pg:1")), ""),
            "more_than_one_graph": ("set", call(e._more_than_one_graph), "private helper of every all-graphs read"),
        }
    return writes, reads, {}


def m03():
    nodes = [(f"pw:{i}", ["L"], {"k": "v", "t": f"x{i}"}) for i in range(6)]

    def writes(e, c, order):
        for n, l, p in permute(nodes, order):
            e.create_node(n, labels=l, properties=p)
        # one triple in the default graph and in graph pw2, with different qualifiers
        e.create_node("pw:0", graph="pw2")
        e.create_node("pw:1", graph="pw2")
        pair = [("", {"w": "1"}), ("pw2", {"w": "2"})]
        for g, q in permute(pair, order if order != "shuffle" else "reverse"):
            e.create_edge("pw:0", "R", "pw:1", qualifiers=q, graph=g or None)

    def reads(e, c):
        return {
            "get_node_ids_by_label": ("set", call(lambda: e.get_node_ids_by_label("L")), ""),
            "get_node_ids_by_property_limit2": ("set", call(lambda: e.get_node_ids_by_property("k", "v", limit=2)),
                                                "nodes_edges.py:815 'Cap on returned rows': which rows is not promised; compared as a set"),
            "get_property_pairs_like_limit2": ("set", call(lambda: e.get_property_pairs_like("t", "x%", limit=2)), ""),
            "get_node": ("set", call(lambda: e.get_node("pw:3")), ""),
            "count_nodes": ("set", call(lambda: e.count_nodes("L")), ""),
            "filter_edges_by_properties_default": ("set", call(lambda: e._filter_edges_by_properties(
                [{"s": "pw:0", "p": "R", "o": "pw:1", "step": 1}], {"w": "1"})),
                "private helper reached from query.py:4218 (variable-length walks with a relationship property filter)"),
        }
    return writes, reads, {}


def m04():
    edges = [("pa:1", "R", "pa:2"), ("pa:1", "R", "pa:3"), ("pa:2", "S", "pa:3"), ("pa:4", "R", "pa:1"), ("pa:3", "R", "pa:4")]

    def writes(e, c, order):
        for n in permute(["pa:1", "pa:2", "pa:3", "pa:4"], order):
            e.create_node(n, labels=["A"])
        for s, p, o in permute(edges, order):
            e.create_edge(s, p, o)

    def reads(e, c):
        return {
            "kg_NEIGHBORS_both": ("set", call(lambda: e.kg_NEIGHBORS(["pa:1"], direction="both")), "'in the order found'; no order promised"),
            "edge_count_R": ("set", call(lambda: e.get_edge_count("R")), ""),
            "verify_graph": ("set", call(lambda: e.verify_graph()), ""),
            "cypher_edges": ("set", call(lambda: e.execute_cypher("MATCH (a)-[r]->(b) RETURN a.id AS a, type(r) AS t, b.id AS b")), "no ORDER BY: rows unordered"),
            "degree_pa1": ("set", call(lambda: c.call("Graph.KG.Adj", "Degree", 0, "pa:1")), ""),
        }
    return writes, reads, {}


def m05():
    base = 1_700_000_000
    ev = [("pt:s", "P", "pt:a", base + 10), ("pt:s", "P", "pt:b", base + 10), ("pt:s", "P", "pt:c", base + 20),
          ("pt:s", "P", "pt:d", base + 30), ("pt:u", "P", "pt:a", base + 20)]

    def writes(e, c, order):
        for s, p, o, ts in permute(ev, order):
            e.create_edge_temporal(s, p, o, timestamp=ts, weight=1.0)

    def reads(e, c):
        return {
            "get_edges_in_window": ("list", call(lambda: e.get_edges_in_window("pt:s", "P", base, base + 100)),
                                    "a window read answers events in time order (TemporalWindow pages in ^KG subscript order)"),
            "aggregate_count": ("set", call(lambda: e.get_temporal_aggregate("pt:s", "P", "count", base, base + 100)), ""),
            "bucket_groups": ("set", call(lambda: e.get_bucket_groups("P", base, base + 100)), ""),
            "latest_edges": ("set", call(lambda: e.get_latest_edges(["pt:s", "pt:u"])), ""),
            "find_burst_nodes": ("set", call(lambda: e.find_burst_nodes("P", 100, 1, base + 50)), ""),
        }
    return writes, reads, {}


def m06():
    vecs = [("pv:1", [1.0, 0.0, 0.0, 0.0]), ("pv:2", [1.0, 0.0, 0.0, 0.0]), ("pv:3", [1.0, 0.0, 0.0, 0.0]),
            ("pv:4", [0.0, 1.0, 0.0, 0.0]), ("pv:5", [0.6, 0.8, 0.0, 0.0])]

    def writes(e, c, order):
        for n, v in permute(vecs, order):
            e.create_node(n, labels=["V"])
        for n, v in permute(vecs, order):
            e.store_embedding(n, v)

    def reads(e, c):
        q = "[1.0,0.0,0.0,0.0]"
        return {
            "kg_KNN_VEC_k2": ("list", call(lambda: e.kg_KNN_VEC(q, k=2)),
                              "a top-k by score (vector.py:504-600, ORDER BY score DESC); three tied candidates for two places"),
            "kg_KNN_VEC_k4": ("list", call(lambda: e.kg_KNN_VEC(q, k=4)), "no cut inside the tie (all three tied rows fit)"),
        }
    return writes, reads, {}


def m07():
    docs = [("px:1", "alpha beta"), ("px:2", "alpha beta"), ("px:3", "alpha beta"), ("px:4", "alpha gamma delta")]

    def writes(e, c, order):
        for n, t in permute(docs, order):
            e.create_node(n, labels=["D"], properties={"text": t})
        e.bm25_build("pxidx", text_props=["text"])
        # the docs table has no product writer: a caller writes it by SQL (schema.py:471-478; the breadth-b lane's
        # 07_live.py:59 does the same); EraseAll deletes it (Eraser.cls:769)
        for n, t in permute(docs, order):
            c.sql("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", "", n, t)

    def reads(e, c):
        return {
            "bm25_search_k2": ("list", call(lambda: e.bm25_search("pxidx", "beta", k=2)),
                               "a ranked top-k (BM25Index.Search); three tied documents for two places"),
            "bm25_search_k5": ("list", call(lambda: e.bm25_search("pxidx", "alpha", k=5)), "tied scores, no cut"),
            "kg_TXT_k2": ("list", call(lambda: e.kg_TXT("beta", k=2)),
                          "'up to k (node_id, score) pairs, highest first' (vector.py:925-929); three documents tie"),
        }
    return writes, reads, {}


def m10():
    edges = [("pr:a", "R", "pr:b"), ("pr:b", "R", "pr:c"), ("pr:c", "R", "pr:a"), ("pr:d", "R", "pr:e"),
             ("pr:e", "R", "pr:d"), ("pr:f", "R", "pr:a"), ("pr:g", "R", "pr:d")]

    def writes(e, c, order):
        for n in permute(sorted({x for s, p, o in edges for x in (s, o)}), order):
            e.create_node(n, labels=["N"])
        for s, p, o in permute(edges, order):
            e.create_edge(s, p, o)

    def reads(e, c):
        return {
            "kg_PAGERANK": ("set", call(lambda: e.kg_PAGERANK()), ""),
            "kg_WCC": ("set", call(lambda: e.kg_WCC()), ""),
            "kg_CDLP": ("set", call(lambda: e.kg_CDLP()), "label propagation: labels are node ids; ties broken by the implementation"),
            "degree_centrality_top2": ("list", call(lambda: e.degree_centrality(top_k=2)), "top-k ranking; pr:a and pr:d tie"),
            "triangle_count": ("set", call(lambda: e.triangle_count()), ""),
            "khop_a": ("set", call(lambda: e.khop("pr:a", hops=2)), ""),
            "subgraph_a": ("set", call(lambda: e.kg_SUBGRAPH(["pr:a"], k_hops=1)), ""),
        }
    return writes, reads, {}


def ledger_records(c, seq, drop_stmt=False):
    recs = []
    if not int(c.o.isDefined("^IVG.Ledger", "rec", seq)):
        return recs
    for ordn, _ in c.o.iterator("^IVG.Ledger", "rec", seq).items():
        lst = c.o.getIRISList("^IVG.Ledger", "rec", seq, ordn)
        r = [str(lst.get(i) or "") for i in range(1, lst.count() + 1)]
        if drop_stmt and r and r[1] == "rel":
            r[2] = "<stmt>"
        recs.append(r)
    return recs


def m11():
    nodes = ["pl:hub", "pl:a", "pl:b", "pl:c", "pl:d", "pl:e"]
    before = [("pl:hub", "R", "pl:a"), ("pl:c", "R", "pl:hub")]           # captured by the genesis
    after = [("pl:hub", "S", "pl:b"), ("pl:d", "S", "pl:hub"), ("pl:hub", "S", "pl:e")]  # written after enable: unrecorded

    def writes(e, c, order):
        for n in permute(nodes, order):
            e.create_node(n, labels=["P"], properties={"name": n})
        for s, p, o in permute(before, order):
            e.create_edge(s, p, o)
        c.conn.commit()
        e.ledger.enable()
        c.conn.commit()
        for s, p, o in permute(after, order):
            e.create_edge(s, p, o)
        c.conn.commit()
        from iris_vector_graph.ledger import Changeset
        ch = Changeset(actor="audit:perm", actor_type="ingest", message="detach")
        ch.delete_node("pl:hub", mode="detach")
        e.ledger.commit(ch)
        c.conn.commit()

    def reads(e, c):
        head = int(c.o.get("^IVG.Ledger", "head") or 0)
        return {
            "genesis_records": ("list", call(lambda: ledger_records(c, 1)), "genesis capture orders every scan (LedgerGenesis.cls:18-40)"),
            "detach_records_with_stmt_ids": ("list", call(lambda: ledger_records(c, head)),
                                             "statement ids the detach cascade assigns to unrecorded edges (F-C1108 subject)"),
            "detach_records_content": ("set", call(lambda: ledger_records(c, head, drop_stmt=True)), "content without statement ids"),
            "verify": ("set", call(lambda: {"result": e.ledger.verify().result}), ""),
            "history_kinds": ("list", call(lambda: [(r.seq, r.kind) for r in e.ledger.history().revisions]), "history pages in seq order"),
        }
    return writes, reads, {}


def m12():
    data = [("t1|a", ""), ("t1|b", ""), ("t2|a", ""), ("pe:x", "pe1"), ("pe:y", "pe1"), ("t1|c", "pe1")]
    edges = [("t1|a", "R", "t1|b", ""), ("t1|a", "R", "t2|a", ""), ("pe:x", "R", "pe:y", "pe1"), ("pe:x", "R", "t1|c", "pe1")]

    def writes(e, c, order):
        for n, g in permute(data, order):
            e.create_node(n, labels=["E"], properties={"p": "1"}, graph=g or None)
        for s, p, o, g in permute(edges, order):
            e.create_edge(s, p, o, graph=g or None)

    def reads(e, c):
        out = {"delete_nodes_by_prefix_t1": ("set", call(lambda: e.delete_nodes_by_prefix("t1|")), "")}
        out["erase_graph_pe1"] = ("set", call(lambda: e.erase_graph("pe1")), "")
        c.conn.commit()
        out["remaining_rows"] = ("set", call(lambda: {
            "nodes": c.sql("SELECT node_id, graph_id FROM Graph_KG.nodes"),
            "edges": c.sql("SELECT s, p, o_id, graph_id FROM Graph_KG.rdf_edges"),
            "props": c.sql('SELECT s, "key", graph_id FROM Graph_KG.rdf_props'),
            "labels": c.sql("SELECT s, label, graph_id FROM Graph_KG.rdf_labels")}), "")
        return out
    return writes, reads, {}


def m13():
    from iris_vector_graph.ledger import Changeset

    def cs(i):
        ch = Changeset(actor="audit:perm", actor_type="ingest", message=f"tenant part {i}")
        ch.create_node(f"tn|{i}", labels=["T"], properties={"secret": f"s{i}"})
        return ch

    parts = [0, 1, 2]

    def writes(e, c, order):
        e.ledger.enable()
        c.conn.commit()
        for i in permute(parts, order):
            e.ledger.commit(cs(i))
        ch = Changeset(actor="audit:perm", actor_type="ingest", message="links")
        ch.create_relationship("tn|0", "R", "tn|1")
        ch.create_node("other|1", labels=["O"])
        e.ledger.commit(ch)
        c.conn.commit()
        e.delete_nodes_by_prefix("tn|")
        c.conn.commit()

    def reads(e, c):
        rec = call(lambda: e.ledger.redact(prefix="tn"))
        c.conn.commit()
        rd = rec if isinstance(rec, dict) else {k: getattr(rec, k) for k in (
            "complete", "records_tombstoned", "metadata_cleared", "idempotency_keys_removed", "statements_removed",
            "unattributed_records", "out_of_reach")} | {"revisions_touched": len(rec.revision_seqs)}
        head = int(c.o.get("^IVG.Ledger", "head") or 0)
        import re as _re
        content = []
        for s in range(1, head + 1):
            for r in ledger_records(c, s):
                # tombstone digests depend on (seq, ordinal), which follow commit order by design; statement ids of
                # rel records follow op order: both normalised; each record kept whole (one string), so the set
                # comparison sorts records, not the fields inside a record
                r = ["<digest>" if _re.fullmatch(r"[0-9a-f]{64}", x) else x for x in r]
                if len(r) > 2 and r[1] == "rel":
                    r[2] = "<stmt>"
                content.append(json.dumps(r))
        return {"redaction_receipt": ("set", rd, ""),
                "history_records_after": ("set", content, "every revision's records, tombstone digests and rel statement ids normalised; seqs, which follow commit order by design, not compared")}
    return writes, reads, {}


def m14():
    from iris_vector_graph.ledger import Changeset

    def cs(i):
        ch = Changeset(actor="audit:perm", actor_type="ingest", message=f"part {i}")
        ch.create_node(f"pp:{i}", labels=["Q"], properties={"v": str(i)})
        return ch

    def writes(e, c, order):
        e.ledger.enable()
        c.conn.commit()
        for i in permute([0, 1, 2, 3], order):
            e.ledger.commit(cs(i))
        ch = Changeset(actor="audit:perm", actor_type="ingest", message="edges")
        for i in permute([1, 2, 3], order):
            ch.create_relationship("pp:0", "R", f"pp:{i}")
        e.ledger.commit(ch)
        c.conn.commit()

    def reads(e, c):
        head = e.ledger.head()

        def recon():
            st = canon(e.ledger.reconstruct(head.revision_id), True)
            # statement ids follow the changeset's op order (an explicit order): compared as a set of tuples
            if isinstance(st, dict) and isinstance(st.get("statements"), dict):
                st["statements"] = sorted(json.dumps(v, sort_keys=True) for v in st["statements"].values())
            return st
        return {"verify": ("set", call(lambda: {"result": e.ledger.verify().result}), ""),
                "reconstruct_head": ("set", call(recon), "GraphState at head (statement ids normalised by canonicalisation only)"),
                "read_canonical_nodes": ("set", call(lambda: sorted(c.sql("SELECT node_id FROM Graph_KG.nodes"))), "")}
    return writes, reads, {}


def m15():
    nodes = [("pi:1", ["Drug"], {"name": "a"}), ("pi:2", ["Gene"], {"name": "b"}), ("pi:3", ["Gene"], {"name": "c"})]
    edges = [("pi:1", "TARGETS", "pi:2", {"w": "1"}), ("pi:1", "TARGETS", "pi:3", {"w": "2"})]

    def writes(e, c, order):
        for n, l, p in permute(nodes, order):
            e.create_node(n, labels=l, properties=p)
        for s, p, o, q in permute(edges, order):
            e.create_edge(s, p, o, qualifiers=q)
        eid = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = 'pi:1' AND o_id = 'pi:2'")[0][0]
        e.reify_edge(eid, reifier_id="pi:r1", label="Evidence", props={"src": "paper"})
        base = 1_700_000_000
        for o, ts in permute([("pi:2", base + 5), ("pi:3", base + 5)], order):
            e.create_edge_temporal("pi:1", "OBS", o, timestamp=ts, weight=1.0)

    def reads(e, c):
        tmp = Path(tempfile.mkdtemp(prefix="ivgperm"))

        def canonical_nt(path):
            # blank-node labels are fresh per export (rdflib BNode): compare the canonical graph (rdflib.compare)
            import rdflib
            from rdflib.compare import to_canonical_graph
            g = rdflib.Graph()
            g.parse(str(path), format="nt")
            return sorted(" ".join(t.n3() for t in tr) for tr in to_canonical_graph(g))

        def rdf():
            r = e.export_rdf(str(tmp / "x.nt"), format="nt")
            return {"triples": canonical_nt(tmp / "x.nt"),
                    "summary": {k: v for k, v in (r or {}).items() if k not in ("path", "elapsed_ms", "seconds")}}

        def prov():
            r = e.prov_export(str(tmp / "p.nt"), format="nt", ts_start=1_699_999_000, ts_end=1_700_001_000)
            return {"triples": canonical_nt(tmp / "p.nt") if (tmp / "p.nt").exists() else [], "summary": str(type(r))}

        def reif():
            eid = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = 'pi:1' AND o_id = 'pi:2'")[0][0]
            out = e.get_reifications(eid)
            return canon(out, True)
        return {"export_rdf_nt": ("set", call(rdf), "triples as a set"),
                "prov_export_nt": ("set", call(prov), ""),
                "get_reifications": ("set", call(reif), "edge_id resolved per order")}
    return writes, reads, {}


class _Info:
    def __init__(self, ctx):
        self.context = ctx


def m16():
    nodes = [f"pq:{i}" for i in range(5)]

    def writes(e, c, order):
        for n in permute(nodes, order):
            e.create_node(n, labels=["Q"], properties={"name": n})

    def reads(e, c):
        from iris_vector_graph.gql.resolvers import resolve_nodes

        def page(off):
            nd = asyncio.run(resolve_nodes(_Info({"engine": e}), "Q", limit=2, offset=off))
            return [getattr(x, "id", str(x)) for x in nd]

        def core(off):
            from api.gql.core.resolvers import CoreQuery
            f = CoreQuery.nodes
            fn = getattr(getattr(f, "base_resolver", None), "wrapped_func", None) or f
            nd = asyncio.run(fn(CoreQuery(), _Info({"engine": e}), labels=["Q"], limit=2, offset=off))
            return [getattr(x, "id", str(x)) for x in nd]
        return {"gql_resolve_nodes_page0": ("list", call(lambda: page(0)), "a page: nodes(label, limit, offset) promises paging (gql/resolvers.py:32)"),
                "gql_resolve_nodes_page1": ("list", call(lambda: page(2)), ""),
                "api_core_nodes_page0": ("list", call(lambda: core(0)), "ORDER BY n.created_at DESC by default (api/gql/core/resolvers.py:159-163)"),
                "api_core_nodes_page1": ("list", call(lambda: core(2)), "")}
    return writes, reads, {}


def m17():
    nodes = [f"po:{i}" for i in range(5)]

    def writes(e, c, order):
        for n in permute(nodes, order):
            e.create_node(n, labels=["O"], properties={"k": "v"})

    def reads(e, c):
        st = e._store

        def ids(r):
            d = {"rows": getattr(r, "rows", None), "error": getattr(r, "error", None)} if hasattr(r, "rows") else r
            return canon(d, False)
        # query_nodes(limit=n) is probed in a child process by so_live.py (P17): it crashes the client on this setup
        return {"query_nodes_label": ("set", call(lambda: ids(st.query_nodes(label_filter="O"))), ""),
                "get_nodes": ("set", call(lambda: ids(st.get_nodes(["po:1", "po:3"]))), ""),
                "get_node_count": ("set", call(lambda: ids(st.get_node_count("O"))), "")}
    return writes, reads, {}


SCENARIOS = {"01": m01, "02": m02, "03": m03, "04": m04, "05": m05, "06": m06, "07": m07, "10": m10, "11": m11,
             "12": m12, "13": m13, "14": m14, "15": m15, "16": m16, "17": m17}


def selftest_scenario():
    nodes = [f"ps:{i}" for i in range(6)]

    def writes(e, c, order):
        for n in permute(nodes, order):
            e.create_node(n)

    def reads(e, c):
        return {"seeded_top1_no_order": ("list", call(lambda: c.sql("SELECT TOP 1 node_id FROM %IGNOREINDEX * Graph_KG.nodes WHERE node_id %STARTSWITH 'ps:'")), "seeded storage-order reader"),
                "seeded_ordered": ("list", call(lambda: c.sql("SELECT node_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'ps:' ORDER BY node_id")), "seeded order-free reader")}
    return writes, reads, {}


def run_module(mod, factory):
    writes, reads, validators = factory()
    per = {}
    for order in ORDERS:
        c = lib.conn()
        try:
            lib.reset(c)
            e = lib.engine(c)
            werr = None
            try:
                writes(e, c, order)
                c.conn.commit()
            except Exception as ex:  # noqa: BLE001
                werr = f"{type(ex).__name__}: {str(ex)[:300]}"
                traceback.print_exc()
                with contextlib.suppress(Exception):
                    c.conn.rollback()
            e = lib.engine(c)  # a fresh engine: no cached graph modes or routes from the writes
            r = reads(e, c) if werr is None else {}
            per[order] = {"write_error": werr, "reads": {k: {"mode": m, "value": canon(v, m == "set"), "basis": b}
                                                          for k, (m, v, b) in r.items()}}
        finally:
            with contextlib.suppress(Exception):
                lib.reset(c)
            c.close()
    names = sorted({k for o in per.values() for k in o["reads"]})
    cmp = {}
    for n in names:
        vals = {o: per[o]["reads"].get(n, {}).get("value") for o in ORDERS}
        mode = next((per[o]["reads"][n]["mode"] for o in ORDERS if n in per[o]["reads"]), "?")
        same = all(json.dumps(vals[o], sort_keys=True, default=str) == json.dumps(vals["forward"], sort_keys=True, default=str) for o in ORDERS)
        errors = [o for o in ORDERS if isinstance(vals[o], dict) and set(vals[o]) == {"error"}]
        entry = {"mode": mode, "equal": same, "errors": errors}
        if mode == "sample":
            v = validators.get(n)
            entry["valid"] = {o: (bool(v(vals[o])) if v else None) for o in ORDERS}
            entry["verdict"] = "holds" if v and all(entry["valid"].values()) else "fails"
        else:
            entry["verdict"] = "holds" if same and not errors else ("error" if errors and same else "differs")
        if not same:
            entry["values"] = vals
        cmp[n] = entry
    write_errors = {o: per[o]["write_error"] for o in ORDERS if per[o]["write_error"]}
    return {"module": mod, "orders": {o: permute(list(range(6)), o) for o in ORDERS}, "per_order": per,
            "comparison": cmp, "write_errors": write_errors}


def main() -> int:
    out = Path(sys.argv[1])
    what = sys.argv[2]
    t0 = time.time()
    res = {"namespace": lib.NS, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "modules": {}}
    if what == "selftest":
        r = run_module("selftest", selftest_scenario)
        c = r["comparison"]
        ok = c["seeded_top1_no_order"]["verdict"] == "differs" and c["seeded_ordered"]["verdict"] == "holds"
        res["selftest"] = {"pass": ok, "result": r}
        print("selftest", "PASS" if ok else "FAIL", json.dumps(c, default=str)[:1500])
    else:
        for m in what.split(","):
            print(f"== module {m}", flush=True)
            try:
                r = run_module(m, SCENARIOS[m])
            except Exception as ex:  # noqa: BLE001
                traceback.print_exc()
                r = {"module": m, "harness_error": f"{type(ex).__name__}: {ex}"}
            res["modules"][m] = r
            for n, v in r.get("comparison", {}).items():
                print(f"   {n:40s} {v['mode']:6s} {v['verdict']}", flush=True)
            if r.get("write_errors"):
                print("   write errors:", json.dumps(r["write_errors"])[:600])
            lib.dump(out, res)  # after every module, so a crash later keeps what was observed
    res["seconds"] = round(time.time() - t0, 1)
    lib.dump(out, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
