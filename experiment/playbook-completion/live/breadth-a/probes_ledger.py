"""Live checks in AUDITA of module 03/05/06 findings that need the revision ledger enabled. See probe_lib.

The ledger is namespace-wide state: `p_enable` enables it (not strict) first, the probes run in order, and
`p_disable` turns strict off and disables it last. Run the whole file in one lock hold:

    bash experiment/playbook-completion/tools/locks.sh iris python probes_ledger.py
"""
from __future__ import annotations

import sys
import time

from probe_lib import Result, conn, engine, erase, gname, run

from iris_vector_graph.ledger import Changeset

C = {}  # shared connection/engine for the ordered run


def _eng():
    if "eng" not in C:
        C["c"], C["eng"] = engine()
    return C["c"], C["eng"]


def cs(**kw):
    return Changeset(actor="breadth-a", actor_type="system", **kw)


def p_enable(r: Result):
    """Setup: enable the ledger (not strict) on AUDITA and check verify() is equal before any probe."""
    c, eng = _eng()
    try:
        r.obs("meta_before", eng.ledger.meta())
    except Exception as e:
        r.obs("meta_before", str(e)[:200])
    info = eng.ledger.enable(strict=False)
    r.obs("enable", str(info)[:200])
    v = eng.ledger.verify()
    r.obs("verify_after_enable", {"result": v.result, "differences": len(v.differences)})
    r["reproduced"] = None
    r["verdict"] = "setup"


def p0303_direct_delete_keeps_stmt(r: Result):
    """F-0303: a direct delete_edge of a ledger-created edge leaves ^IVG.Ledger("tuple"/"stmt") naming it; a later ledger
    create of the same triple reuses the old statement id. Oracle: CONTEXT.md:198-205 (no live statement outlives
    its content) and INV-stmt."""
    c, eng = _eng()
    a, b = gname("la"), gname("lb")
    ch = cs()
    ch.create_node(a)
    ch.create_node(b)
    ch.create_relationship(a, "LR", b)
    res = eng.ledger.commit(ch)
    r.obs("stmt_ids_first", dict(res.stmt_ids))
    t1 = r.obs("tuple_entry_after_create", str(c.o.get("^IVG.Ledger", "tuple", a, "LR", b, 0) or ""))
    r.obs("direct_delete_edge", eng.delete_edge(a, "LR", b))
    r.obs("row_after_direct_delete", c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ? AND o_id = ?", a, b)[0][0])
    t2 = r.obs("tuple_entry_after_direct_delete", str(c.o.get("^IVG.Ledger", "tuple", a, "LR", b, 0) or ""))
    r.obs("stmt_entry_alive", int(c.o.isDefined("^IVG.Ledger", "stmt", int(t2))) if t2 else 0)
    ch2 = cs()
    ch2.create_relationship(a, "LR", b)
    res2 = eng.ledger.commit(ch2)
    r.obs("stmt_ids_recreate", dict(res2.stmt_ids))
    v = eng.ledger.verify()
    r.obs("verify", {"result": v.result, "classification": v.classification,
                     "differences": [str(d)[:160] for d in v.differences[:5]]})
    r["oracle"] = "after the edge row is gone no live statement names it; a re-created edge gets a new statement"
    r["reproduced"] = bool(t2) and t2 == t1
    r["verdict"] = f"tuple entry {t2} survives the direct delete" if r["reproduced"] else "cleared"
    C["f0303"] = (a, b)


def p0503_changeset_temporal_endpoint(r: Result):
    """F-0503 (HD-0501): a governed changeset whose temporal op names endpoints with no node op creates node rows
    (Adjacency.AssertTemporalRow) that no record names; verify() then diverges though every write went through the
    ledger."""
    c, eng = _eng()
    v0 = eng.ledger.verify()
    r.obs("verify_before", {"result": v0.result, "differences": len(v0.differences)})
    s, o = gname("ts"), gname("to")
    ch = cs()
    ch.create_temporal_edge(s, "TP", o, ts=1700000000, weight=2.0)
    res = eng.ledger.commit(ch)
    r.obs("commit", str(res.revision)[:160])
    r.obs("node_rows", c.sql("SELECT node_id FROM Graph_KG.nodes WHERE node_id IN (?, ?)", s, o))
    v = eng.ledger.verify()
    diffs = [str(d)[:200] for d in v.differences]
    mine = [d for d in diffs if s in d or o in d]
    r.obs("verify_after", {"result": v.result, "classification": v.classification, "differences_naming_endpoints": mine,
                           "differences_total": len(diffs)})
    r["oracle"] = "with every write made through the ledger, verify() answers equal (RPL-B3, INV-replay)"
    r["reproduced"] = v.result == "diverges" and bool(mine)
    r["verdict"] = "verify diverges on node rows the changeset's temporal op created" if r["reproduced"] else v.result
    C["f0503"] = (s, o)


def p0511_insert_collision_recorded(r: Result):
    """F-0511: a changeset temporal op in mode "insert" at occupied coordinates changes nothing yet commits a revision
    recording a create_temporal_edge."""
    c, eng = _eng()
    s, o = C.get("f0503", (gname("ts"), gname("to")))
    w_before = r.obs("weight_before", str(c.o.get("^KG", "tout", 0, 1700000000, s, "TP", o)))
    ch = cs()
    ch.create_temporal_edge(s, "TP", o, ts=1700000000, weight=9.0, mode="insert")
    try:
        res = eng.ledger.commit(ch)
        r.obs("commit", ["ok", str(res.revision)[:160]])
        rev = eng.ledger.get_revision(res.revision.revision_id)
        r.obs("recorded_ops", str(getattr(rev, "records", getattr(rev, "ops", rev)))[:400])
    except Exception as e:
        r.obs("commit", ["refused", f"{type(e).__name__}: {str(e)[:200]}"])
    w_after = r.obs("weight_after", str(c.o.get("^KG", "tout", 0, 1700000000, s, "TP", o)))
    r["oracle"] = "Changeset.create_temporal_edge docstring: insert fails if the key exists; a no-op is not recorded"
    r["reproduced"] = r["observed"]["commit"][0] == "ok" and w_before == w_after
    r["verdict"] = "collision committed and recorded; weight unchanged" if r["reproduced"] else "refused/changed"


def p0618_ledger_delete_routed_vector(r: Result):
    """F-0618: a ledger delete_node of a default-graph node that has a vector in a declared-model route is refused
    (LedgerApply.DeleteNodeRows clears only the legacy tables; the route's FK refuses the node delete), where the
    engine's delete_node succeeds."""
    c, eng = _eng()
    n = gname("vn")
    ch = cs()
    ch.create_node(n)
    eng.ledger.commit(ch)
    eng.store_embedding(n, [1.0, 0.0, 0.0, 0.0], model_key="ba-fk")
    r.obs("route", c.sql("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = '' AND model_key = 'ba-fk'"))
    ch2 = cs()
    ch2.delete_node(n)
    try:
        res = eng.ledger.commit(ch2)
        r.obs("ledger_delete", ["ok", str(res.revision)[:120]])
    except Exception as e:
        r.obs("ledger_delete", ["refused", f"{type(e).__name__}: {str(e)[:250]}"])
    r.obs("node_after", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = '' AND node_id = ?", n)[0][0])
    r["oracle"] = "a ledger delete_node removes what the engine's delete_node removes (Eraser reaches every route)"
    r["reproduced"] = r["observed"]["ledger_delete"][0] == "refused"
    r["verdict"] = "ledger delete refused by the route's foreign key" if r["reproduced"] else "deleted"
    try:
        r.obs("engine_delete_node", eng.delete_node(n, graph=None))
    except Exception as e:
        r.obs("engine_delete_node", f"{type(e).__name__}: {str(e)[:200]}")


def p0302_strict_cache_window(r: Result):
    """F-0302: engine E1 has cached "not strict"; E2 turns strict on; E1's direct write within the 5 s TTL succeeds.
    Oracle: USER_GUIDE.md:1107-1121 (strict mode refuses the writes; no window stated)."""
    c, eng = _eng()
    c2, e2 = engine(conn())
    try:
        n0 = gname("w0")
        eng.create_node(n0)  # primes E1's guard cache (not strict)
        e2.ledger.set_strict(True)
        t = time.time()
        n1 = gname("w1")
        try:
            r.obs("e1_write_after_strict", eng.create_node(n1))
        except Exception as e:
            r.obs("e1_write_after_strict", f"refused {type(e).__name__}")
        r.obs("elapsed_s", round(time.time() - t, 2))
        try:
            e2.create_node(gname("w2"))
            r.obs("e2_write", "accepted")
        except Exception as e:
            r.obs("e2_write", f"refused {type(e).__name__}")
        r["oracle"] = "once strict is on, every engine refuses the guarded writes"
        r["reproduced"] = r["observed"]["e1_write_after_strict"] is True
        r["verdict"] = "another engine wrote within its cache window" if r["reproduced"] else "refused"
    finally:
        c2.close()


def p0301_bulk_loader_under_strict(r: Result):
    """F-0301 (HD-0301 supported: the loader is excluded): with strict on, create_node is refused and BulkLoader still
    writes. Recorded as the documented exclusion; the USER_GUIDE text says "and the other methods"."""
    from iris_vector_graph.bulk_loader import BulkLoader
    c, eng = _eng()
    time.sleep(5.5)  # past every engine's guard cache
    try:
        eng.create_node(gname("sx"))
        r.obs("create_node_under_strict", "accepted")
    except Exception as e:
        r.obs("create_node_under_strict", f"refused {type(e).__name__}")
    n = gname("bl")
    out = BulkLoader(c.conn).load_nodes([(n, {"k": "v"})], use_noindex=False)
    r.obs("bulk_loader", str(out)[:200])
    r.obs("rows", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = '' AND node_id = ?", n)[0][0])
    r["oracle"] = "Spec 213 API contract: bulk loader and raw SQL are outside strict mode (HD-0301)"
    r["reproduced"] = r["observed"]["rows"] == 1 and r["observed"]["create_node_under_strict"].startswith("refused")
    r["verdict"] = "loader wrote under strict mode (contract exception; docs say otherwise)" if r["reproduced"] else "?"
    C["f0301"] = n


def p0504_purge_retires_nodes_under_strict(r: Result):
    """F-0504: under strict mode delete_node is refused, but purge_before retires bare temporal endpoint nodes with a
    SQL delete and no guard."""
    c, eng = _eng()
    s, o = C.get("f0503", (None, None))
    r.obs("endpoints_before", c.sql("SELECT node_id FROM Graph_KG.nodes WHERE node_id IN (?, ?)", s, o))
    try:
        eng.delete_node(s, graph=None)
        r.obs("delete_node_under_strict", "accepted")
    except Exception as e:
        r.obs("delete_node_under_strict", f"refused {type(e).__name__}")
    try:
        r.obs("purge_before", eng.purge_before(1700000001))
    except Exception as e:
        r.obs("purge_before", f"refused {type(e).__name__}: {str(e)[:150]}")
    after = r.obs("endpoints_after", c.sql("SELECT node_id FROM Graph_KG.nodes WHERE node_id IN (?, ?)", s, o))
    v = eng.ledger.verify()
    r.obs("verify", {"result": v.result, "differences": [str(d)[:160] for d in v.differences if s in str(d) or o in str(d)]})
    r["oracle"] = "strict mode refuses structural deletes not made through the ledger (USER_GUIDE.md:1107-1121)"
    r["reproduced"] = r["observed"]["delete_node_under_strict"].startswith("refused") and len(after) < 2
    r["verdict"] = "purge deleted governed node rows under strict mode" if r["reproduced"] else "kept"


def p_disable(r: Result):
    """Teardown: strict off, ledger disabled, probe content removed."""
    c, eng = _eng()
    try:
        eng.ledger.set_strict(False)
    except Exception as e:
        r.obs("set_strict_false", str(e)[:200])
    time.sleep(5.5)
    for key in ("f0303", "f0503"):
        for nid in C.get(key, ()):
            try:
                eng.delete_node(nid, graph=None)
            except Exception:
                pass
    if C.get("f0301"):
        try:
            eng.delete_node(C["f0301"], graph=None)
        except Exception:
            pass
    eng.ledger.disable()
    r.obs("meta_after", eng.ledger.meta())
    r["reproduced"] = None
    r["verdict"] = "teardown"


def p0303b_direct_delete_keeps_stmt(r: Result):
    """F-0303 (corrected harness: the tuple index is keyed by GraphKey.ForLedger, not 0): after a direct delete_edge of a
    ledger-created edge, the tuple index still maps the triple to the edge's statement and the statement entry is live;
    after a direct re-create, the tuple index hands that old statement to the next ledger op on the triple."""
    c, eng = _eng()
    a, b = gname("la"), gname("lb")
    gk = r.obs("ledger_key_default", repr(str(c.call("Graph.KG.GraphKey", "ForLedger", ""))))
    gk = str(c.call("Graph.KG.GraphKey", "ForLedger", ""))
    ch = cs()
    ch.create_node(a)
    ch.create_node(b)
    ch.create_relationship(a, "LR", b)
    res = eng.ledger.commit(ch)
    s1 = str(list(res.stmt_ids.values())[0])
    r.obs("stmt_first", s1)
    r.obs("tuple_after_create", str(c.o.get("^IVG.Ledger", "tuple", a, "LR", b, gk)))
    eng.delete_edge(a, "LR", b)
    r.obs("row_after_direct_delete", c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ? AND o_id = ?", a, b)[0][0])
    t2 = r.obs("tuple_after_direct_delete", str(c.o.get("^IVG.Ledger", "tuple", a, "LR", b, gk) or ""))
    alive = r.obs("stmt_entry_alive_after_direct_delete", int(c.o.isDefined("^IVG.Ledger", "stmt", int(s1)) or 0))
    v = eng.ledger.verify()
    r.obs("verify_after_direct_delete", {"result": v.result, "classification": v.classification,
                                         "differences": [str(d)[:200] for d in v.differences][:4]})
    eng.create_edge(a, "LR", b)  # re-created outside the ledger
    t3 = r.obs("tuple_after_direct_recreate", str(c.o.get("^IVG.Ledger", "tuple", a, "LR", b, gk) or ""))
    r["oracle"] = "no live statement outlives its edge row (CONTEXT.md:198-205, INV-stmt)"
    r["reproduced"] = bool(t2) and t2 == s1 and bool(alive)
    r["verdict"] = (f"statement {s1} and its tuple entry stay live after the row is gone; the re-created edge inherits it"
                    if r["reproduced"] else "cleared")
    C["f0303"] = (a, b)


PROBES = {f.__name__: f for f in (p_enable, p0303b_direct_delete_keeps_stmt, p0303_direct_delete_keeps_stmt, p0503_changeset_temporal_endpoint,
                                  p0511_insert_collision_recorded, p0618_ledger_delete_routed_vector,
                                  p0302_strict_cache_window, p0301_bulk_loader_under_strict,
                                  p0504_purge_retires_nodes_under_strict, p_disable)}

if __name__ == "__main__":
    try:
        sys.exit(run("ledger", PROBES, sys.argv[1:]))
    finally:
        if "c" in C:
            C["c"].close()
