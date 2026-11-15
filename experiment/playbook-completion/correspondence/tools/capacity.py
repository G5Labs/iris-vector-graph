#!/usr/bin/env python3
"""§3.6 capacity: IRIS subscript and string limits through ledger commit, erasure and redaction (AUDITC, live).

    python capacity.py OUT_DIR

1. Reference-length limits, read-only: the longest s = o (p = half of it) for which a read of
   ^IVG.Ledger("tuple", s, p, o, $c(1)) and of ^KG("out", 0, s, p, o) does not raise <SUBSCRIPT> (Native API
   isDefined, which writes nothing).
2. Cases, each from a fresh ledger: the operation, its outcome, and a state comparison before/after: ^IVG.Ledger
   (whole snapshot), row counts of nodes/rdf_edges/rdf_props/ledger_revisions, ^KG("out") entries, ^IVG.AdjNoLock.
   Outcome: ok | clean-failure (error, nothing changed) | partial (error, something changed) | corrupt (no error, but
   an invariant is broken: a live edge row whose recorded statement has no tuple entry, or a row without adjacency).
Lock-table capacity is outside the IRIS contract's subset (iris-contract/CONTRACT.md "Outside the semantic subset")
and is not probed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, Conn, conformance, dump, engine, reset, version  # noqa: E402

from iris_vector_graph.ledger import Changeset  # noqa: E402


def ref_ok(c, g, *subs):
    try:
        c.o.isDefined(g, *subs)
        return True
    except Exception:  # noqa: BLE001
        return False


def limit(c, build):
    lo, hi = 1, 600
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ref_ok(c, *build(mid)):
            lo = mid
        else:
            hi = mid - 1
    return lo


def state(c):
    snap = conformance.snapshot(c)
    counts = {t: c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t}")[0][0] for t in ("nodes", "rdf_edges", "rdf_props", "ledger_revisions")}
    kg = sum(1 for _ in c.o.iterator("^KG", "out").items()) if int(c.o.isDefined("^KG", "out")) else 0
    nolock = {str(k): str(v) for k, v in c.o.iterator("^IVG.AdjNoLock").items()} if int(c.o.isDefined("^IVG.AdjNoLock")) else {}
    return {"ledger": snap, "counts": counts, "kg_out_graphs": kg, "adjnolock": nolock}


def invariants(c):
    """A recorded edge (a live ("stmt") entry names it) must have its tuple entry; every edge row its adjacency."""
    bad = []
    live = set()
    for sid, _ in c.o.iterator("^IVG.Ledger", "stmt").items():
        lst = c.o.getIRISList("^IVG.Ledger", "stmt", sid)
        if str(lst.get(6) or "") == "":
            live.add((str(lst.get(1)), str(lst.get(2)), str(lst.get(3)), str(lst.get(4) or "")))
    for eid, s, p, o, g in c.sql("SELECT edge_id, s, p, o_id, graph_id FROM Graph_KG.rdf_edges"):
        g = "" if g in (None, "") else str(g)
        recorded = (s, p, o, g) in live
        try:
            t = c.o.get("^IVG.Ledger", "tuple", s, p, o, g or "\x01")
        except Exception as ex:  # noqa: BLE001
            t = f"<{type(ex).__name__}>"
        try:
            adj = int(c.o.isDefined("^KG", "out", g or 0, s, p, o))
        except Exception as ex:  # noqa: BLE001
            adj = f"<{type(ex).__name__}>"
        if (recorded and t in (None, "")) or not adj or str(adj).startswith("<"):
            bad.append({"edge": [len(s), len(p), len(o), g], "recorded": recorded, "tuple": str(t)[:20], "adjacency": adj})
    return bad


def cs(msg, **kw):
    return Changeset(actor="audit:capacity", actor_type="ingest", message=msg, **kw)


def case(name, setup, action, note="", enable=True):
    ctl = Conn(NS)
    reset(ctl)
    if enable:
        engine(ctl).ledger.enable()
    ctl.conn.commit()
    if setup:
        try:
            setup(ctl)
            ctl.conn.commit()
        except Exception as ex:  # noqa: BLE001
            ctl.close()
            r = {"case": name, "note": note, "outcome": "setup-failed", "error": f"{type(ex).__name__}: {str(ex)[:300]}"}
            print(json.dumps(r)[:600], flush=True)
            return r
    before = state(ctl)
    ctl.close()
    x = Conn(NS)
    try:
        res, err = action(x), None
        x.conn.commit()
    except Exception as ex:  # noqa: BLE001
        res, err = None, f"{type(ex).__name__}: {str(ex)[:300]}"
        try:
            x.conn.rollback()
        except Exception:  # noqa: BLE001
            pass
    x.close()
    ctl = Conn(NS)
    after = state(ctl)
    inv = invariants(ctl)
    ctl.close()
    changed = before != after
    if err is None and isinstance(res, dict) and res.get("ok") is False:
        err = f"refused: {res.get('error')}: {str(res.get('reason'))[:200]}"
    stats_only = changed and before["ledger"] == after["ledger"] and before["counts"] == after["counts"] and \
        before["kg_out_graphs"] == after["kg_out_graphs"] and before["adjnolock"] == after["adjnolock"]
    if err is None:
        outcome = "corrupt" if inv else "ok"
    else:
        outcome = "clean-failure" if not changed or stats_only else "partial"
    diff = {}
    if changed:
        for k in ("counts", "kg_out_graphs", "adjnolock"):
            if before[k] != after[k]:
                diff[k] = [before[k], after[k]]
        lb, la = before["ledger"], after["ledger"]
        dk = [list(k) for k in set(lb) | set(la) if lb.get(k) != la.get(k)]
        if dk:
            diff["ledger_keys"] = [[str(s)[:40] for s in k] for k in dk[:8]]
    r = {"case": name, "note": note, "outcome": outcome, "error": err, "result": str(res)[:300] if res is not None else None,
         "changed": diff, "invariant_breaks": inv[:5]}
    print(json.dumps(r, default=str)[:900], flush=True)
    return r


def permutation(order):
    """OpDeleteNode detach over unrecorded incident edges (LedgerApply.cls:384-410): the cascade allocates statement
    ids in the order of an unordered SQL cursor (:385). Insert the same three bypass edges in another order and
    compare the ids assigned per tuple and the recorded content (records without their statement ids)."""
    ctl = Conn(NS)
    reset(ctl)
    led = engine(ctl).ledger
    led.enable()
    ch = cs("permutation nodes")
    for n in ("pm|1", "pm|a", "pm|b", "pm|c"):
        ch.create_node(n)
    led.commit(ch)
    ctl.conn.commit()
    e = engine(ctl)
    for x in order:
        e.create_edge("pm|1", "R", "pm|" + x)
    ctl.conn.commit()
    d = cs("detach")
    d.delete_node("pm|1", mode="detach")
    r = led.commit(d)
    ctl.conn.commit()
    seq = r.revision.seq
    recs = []
    for ordn, _ in ctl.o.iterator("^IVG.Ledger", "rec", seq).items():
        lst = ctl.o.getIRISList("^IVG.Ledger", "rec", seq, ordn)
        recs.append([str(lst.get(i) or "") for i in range(1, lst.count() + 1)])
    ctl.close()
    t2s = {r[4]: r[2] for r in recs if r[0] == "delete_rel"}
    content = sorted([r[0], r[4], r[7]] for r in recs)
    return {"insert_order": order, "records": recs, "tuple_to_stmt": t2s, "content": content}


def main() -> int:
    out = Path(sys.argv[1])
    c = Conn(NS)
    print("engine:", version(c), flush=True)
    lim_ledger = limit(c, lambda n: ("^IVG.Ledger", "tuple", "s" * n, "p" * (n // 2), "o" * n, "\x01"))
    lim_kg = limit(c, lambda n: ("^KG", "out", 0, "s" * n, "p" * (n // 2), "o" * n))
    lim_node = limit(c, lambda n: ("^KG", "prop", 0, "s" * n))
    c.close()
    limits = {"tuple_len_s_eq_o_p_half": lim_ledger, "kg_out_len_s_eq_o_p_half": lim_kg, "kg_prop_node_len": lim_node}
    print(json.dumps(limits), flush=True)
    def commits(n):
        x = Conn(NS)
        try:
            reset(x)
            engine(x).ledger.enable()
            ch = cs("probe width")
            ch.create_node("s" * n)
            ch.create_node("o" * n)
            ch.create_relationship("s" * n, "p" * (n // 2), "o" * n)
            engine(x).ledger.commit(ch)
            x.conn.commit()
            return True
        except Exception:  # noqa: BLE001
            return False
        finally:
            x.close()
    lo, hi = 1, 256
    while lo < hi:
        mid = (lo + hi + 1) // 2
        lo, hi = (mid, hi) if commits(mid) else (lo, mid - 1)
    limits["widest_committable_edge_s_eq_o_p_half"] = lo
    print(json.dumps(limits), flush=True)
    n_mid = lo              # the widest edge the content table (its unique index u_spo_graph_ekey) accepts
    p_mid = n_mid // 2

    def commit(ch):
        def f(x):
            r = engine(x).ledger.commit(ch)
            return {"seq": r.revision.seq}
        return f

    def node_case(n):
        ch = cs("long node id")
        ch.create_node("cap|" + "n" * (n - 4), properties={"k": "v"})
        return commit(ch)

    def edge_case(n, p, graph=None):
        ch = cs("long edge")
        s, o = "s" * n, "o" * n
        ch.create_node(s)
        ch.create_node(o)
        ch.create_relationship(s, "p" * p, o, graph=graph)
        return commit(ch)

    def bypass_edge(n, p):
        def f(x):
            e = engine(x)
            e.create_node("cb|" + "s" * (n - 3))
            e.create_node("cb|" + "o" * (n - 3))
            if not e.create_edge("cb|" + "s" * (n - 3), "p" * p, "cb|" + "o" * (n - 3)):
                raise RuntimeError("create_edge answered False")
        return f

    def ledger_tenant(n, p):
        def f(x):
            ch = cs("tenant at the widest width")
            ch.create_node("cb|" + "s" * (n - 3), properties={"k": "v"})
            ch.create_node("cb|" + "o" * (n - 3))
            ch.create_relationship("cb|" + "s" * (n - 3), "p" * p, "cb|" + "o" * (n - 3), qualifiers={"w": "1"})
            engine(x).ledger.commit(ch)
        return f

    def ledger_tenant_erased(n, p):
        def f(x):
            ledger_tenant(n, p)(x)
            x.conn.commit()
            x.call("Graph.KG.Eraser", "EraseNodes", "", "cb|")
        return f

    def qual_case(size):
        ch = cs("big qualifier")
        ch.create_node("q|1")
        ch.create_node("q|2")
        ch.create_relationship("q|1", "R", "q|2", qualifiers={"big": "x" * size})
        return commit(ch)

    def prop_case(size):
        ch = cs("big property")
        ch.create_node("pv|1", properties={"v": "y" * size})
        return commit(ch)

    def key_case(n):
        ch = cs("long idempotency key", idempotency_key="k" * n)
        ch.create_node(f"ik|{n}")
        return commit(ch)

    def msg_case(n):
        ch = Changeset(actor="audit:capacity", actor_type="ingest", message="m" * n)
        ch.create_node(f"mg|{n}")
        return commit(ch)

    def committed_then_erased(prefix, size):
        def f(ctl):
            ch = cs("tenant with big qualifier")
            ch.create_node(prefix + "|1")
            ch.create_node(prefix + "|2")
            ch.create_relationship(prefix + "|1", "R", prefix + "|2", qualifiers={"big": "z" * size})
            engine(ctl).ledger.commit(ch)
            ctl.conn.commit()
            ctl.call("Graph.KG.Eraser", "EraseNodes", "", prefix + "|")
        return f

    redact = lambda g, pre: (lambda x: json.loads(str(x.call("Graph.KG.LedgerRedact", "Redact", g, pre, "|",  # noqa: E731
                                                              "audit:capacity", 100, 0, "Graph_KG"))))
    results = [
        case("commit-node-id-256", None, node_case(256), "node_id is VARCHAR(256)"),
        case("commit-node-id-257", None, node_case(257), "one past the column width"),
        case("commit-edge-256-128", None, edge_case(256, 128), "widest edge the columns accept"),
        case(f"commit-edge-{n_mid}-{p_mid}", None, edge_case(n_mid, p_mid), "the widest edge that commits"),
        case(f"commit-edge-{n_mid + 1}-{(n_mid + 1) // 2}", None, edge_case(n_mid + 1, (n_mid + 1) // 2), "one wider"),
        case(f"bypass-edge-{n_mid + 1}", None, bypass_edge(n_mid + 1, (n_mid + 1) // 2),
             "a ledger-bypassing writer one wider: refused by the same index"),
        case(f"erase-nodes-at-{n_mid}", ledger_tenant(n_mid, p_mid),
             lambda x: int(x.call("Graph.KG.Eraser", "EraseNodes", "", "cb|")), "EraseEdgeRow reads the tuple index (Eraser.cls:673)"),
        case(f"erase-graph-at-{n_mid}", ledger_tenant(n_mid, p_mid),
             lambda x: int(x.call("Graph.KG.Eraser", "EraseGraph", "")), "EraseLedgerFor"),
        case(f"redact-at-{n_mid}", ledger_tenant_erased(n_mid, p_mid), redact("", "cb"), "Matches/TupleEnds/DropStatements"),
        case(f"verify-at-{n_mid}", ledger_tenant(n_mid, p_mid), lambda x: engine(x).ledger.verify().result,
             "verify's StmtForTuple lookup"),
        case(f"genesis-over-bypass-edge-{n_mid}", bypass_edge(n_mid, p_mid),
             lambda x: json.loads(str(x.call("Graph.KG.Ledger", "Enable", 0, 50000, 250000, "Graph_KG"))),
             "Capture allocates a statement per edge row (LedgerGenesis.cls:47)", enable=False),
        case("commit-qualifier-1M", None, qual_case(1_000_000), "staged payload, ~1 MB record"),
        case("commit-qualifier-4M", None, qual_case(4_000_000), "above IRIS's 3,641,144-character string"),
        case("commit-property-64000", None, prop_case(64_000), "rdf_props.val is VARCHAR(64000)"),
        case("commit-property-64001", None, prop_case(64_001), ""),
        case("commit-idem-key-256", None, key_case(256), "ledger_revisions.idempotency_key MAXLEN 256"),
        case("commit-idem-key-257", None, key_case(257), ""),
        case("commit-idem-key-600", None, key_case(600), "beyond the subscript limit of ^IVG.Ledger('idem', key)"),
        case("commit-message-4001", None, msg_case(4001), "ledger_revisions.message MAXLEN 4000"),
        case("redact-after-erase-1M-qualifier", committed_then_erased("bq", 1_000_000), redact("", "bq"),
             "CanonicalRecord and SHA-256 of a ~1 MB record"),
        case("redact-prefix-10000", None, redact("", "r" * 10_000), "a target that matches nothing"),
        case("erase-nodes-prefix-10000", None, lambda x: int(x.call("Graph.KG.Eraser", "EraseNodes", "", "e" * 10_000)), ""),
        case("commit-graph-name-300", None, edge_case(8, 4, graph="g" * 300), "graph_id is VARCHAR(256)"),
    ]
    perm = [permutation(order) for order in (("a", "b", "c"), ("c", "b", "a"), ("b", "c", "a"))]
    same = all(p["tuple_to_stmt"] == perm[0]["tuple_to_stmt"] for p in perm)
    content_same = all(p["content"] == perm[0]["content"] for p in perm)
    print(json.dumps({"row_permutation": perm, "stmt_ids_independent_of_insertion_order": same,
                      "recorded_content_independent": content_same}, default=str)[:2000], flush=True)
    dump(out / "capacity.json", {"limits": limits, "cases": results,
                                 "row_permutation": {"runs": perm, "stmt_ids_independent_of_insertion_order": same,
                                                     "recorded_content_independent": content_same}})
    print(json.dumps({r["case"]: r["outcome"] for r in results}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
