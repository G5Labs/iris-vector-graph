"""Iteration 60 repair: native reproductions of the review-60 findings (FE-1..FE-6, C4, CG-3) on the local fixture.

Local fixture only (local-runtime/runtime.py: ivg-uplift-next-20261115, 127.0.0.1:35975, identity-checked on every
connection). Writes only in this repair's own namespaces, created additively from %SYS with SQL CREATE DATABASE and
deployed with initialize_schema() from the unchanged pin: I60RA (client, counters, limits, readers), I60RC (max_ops 2),
I60RE (never enabled), I60RV (verify, general), I60RT (verify, temporal text marker). IDs start with i60r. No erase,
reset, kill or drop; no write to USER, I60L* or R60*. Predictions: ../PREDICTIONS.md (committed before any run).

Usage: python -B i60r_probe.py <section ...>   sections: setup fe1 fe2 fe3 fe4 fe5 c4   -> observed-<stamp>-<sections>.json
"""
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "local-runtime"))
import runtime as rt  # noqa: E402  local fixture runtime (identity-checked connect)

import iris_vector_graph as ivg  # noqa: E402
from iris_vector_graph.errors import IVGError  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402
from iris_vector_graph.ledger import errors as LE  # noqa: E402

OBS = {"fixture": rt.FIXTURE, "product": rt.PRODUCT, "identity": []}
NAMESPACES = {"I60RA": {"enable": {}}, "I60RC": {"enable": {"max_ops": 2}}, "I60RE": {"enable": None},
              "I60RV": {"enable": {}}, "I60RT": {"enable": {}}}


def stamp():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def exc(e):
    d = {"class": type(e).__name__, "module": type(e).__module__, "mro": [c.__name__ for c in type(e).__mro__[:5]],
         "msg": str(e)[:400]}
    for a in ("op_index", "missing_node", "current_head", "limit"):
        if hasattr(e, a):
            d[a] = getattr(e, a)
    return d


def connect(ns):
    c = rt.connect(ns)  # raises on identity mismatch
    ok, host = rt.identity(c)
    OBS["identity"].append({"ns": ns, "ok": ok, "host": host})
    assert ok
    return c


def open_ns(ns):
    c = connect(ns)
    return c, rt.engine(c, ns)


def vfy(L, **kw):
    r = L.verify(**kw)
    return {"result": r.result, "classification": r.classification, "seq": r.verified_seq,
            "entries": [[e.entity_kind, e.entity_id, e.attr, e.before, e.after] for e in r.differences],
            "adoption_seq": r.adoption_revision.seq if r.adoption_revision else None}


def only(v, needle):
    return [x for x in v["entries"] if needle in x[1] or (x[4] and needle in str(x[4]))]


def counters(ns):
    """ledger_stats read from a fresh connection (another server process)."""
    c = connect(ns)
    cur = c.cursor()
    cur.execute("SELECT commits_ok, replays_idem, rej_stale_head, rej_unknown_head, rej_idem_conflict, rej_failed_op, "
                "rej_strict_block, rej_size_limit, rej_disabled, rej_lock_timeout FROM Graph_KG.ledger_stats")
    r = cur.fetchone()
    c.close()
    names = ["commits_ok", "replays_idem", "rej_stale_head", "rej_unknown_head", "rej_idem_conflict", "rej_failed_op",
             "rej_strict_block", "rej_size_limit", "rej_disabled", "rej_lock_timeout"]
    return dict(zip(names, [int(x or 0) for x in r]))


def delta(a, b):
    return {k: b[k] - a[k] for k in a if b[k] != a[k]}


def head_seq(L):
    return L.head().seq


# ------------------------------------------------------------------------------------------------ setup
def setup():
    o = OBS.setdefault("setup", {})
    c = connect("%SYS")
    cur = c.cursor()
    for ns, cfg in NAMESPACES.items():
        cur.execute("SELECT Name FROM Config.Namespaces WHERE Name = ?", [ns])
        existed = cur.fetchone() is not None
        if not existed:
            cur.execute(f"CREATE DATABASE {ns}")
        o[ns] = {"existed": existed}
    c.close()
    for ns, cfg in NAMESPACES.items():
        cn, e = open_ns(ns)
        st = e.initialize_schema()
        o[ns]["init_tables"] = sorted(st.get("tables_created", [])) if isinstance(st, dict) else str(st)[:200]
        m = e.ledger.meta()
        if cfg["enable"] is not None and m.get("state") == "never-enabled":
            info = e.ledger.enable(**cfg["enable"])
            o[ns]["enable"] = {"seq": info.seq, "kind": info.kind}
        o[ns]["meta"] = e.ledger.meta()
        cn.close()


# ------------------------------------------------------------------------------------------------ FE-1 (I60RT)
def fe1():
    o = OBS.setdefault("fe1", {})
    c, e = open_ns("I60RT")
    L = e.ledger
    s = stamp().lower()
    p = f"i60r_t{s}_"
    o["verify_start"] = vfy(L)
    # R1.a neighbour: qualifier temporal "yes"
    cs = Changeset(actor="i60r", actor_type="agent")
    for x in ("ya", "yb"):
        cs.upsert_node(p + x)
    cs.create_relationship(p + "ya", "I60RREL", p + "yb", qualifiers={"temporal": "yes"})
    o["R1a.commit_seq"] = L.commit(cs).revision.seq
    v = vfy(L)
    o["R1a.verify"] = {"result": v["result"], "entries_for_yes": only(v, p + "ya")}
    # R1.b qualifier temporal "true" (text)
    cs = Changeset(actor="i60r", actor_type="agent")
    for x in ("ta", "tb"):
        cs.upsert_node(p + x)
    cs.create_relationship(p + "ta", "I60RREL", p + "tb", qualifiers={"temporal": "true", "w": "1"})
    res = L.commit(cs)
    o["R1b.commit"] = {"seq": res.revision.seq, "stmt_ids": res.stmt_ids}
    cur = c.cursor()
    cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ?", [p + "ta"])
    o["R1b.row_qualifiers"] = [r[0] for r in cur.fetchall()]
    o["R1b.records"] = [[r.op, r.entity_id, r.attr, r.new] for r in L.get_revision(res.revision.revision_id).records]
    v1 = vfy(L)
    o["R1b.verify_1"] = {"result": v1["result"], "classification": v1["classification"], "entries": only(v1, p + "ta")}
    h = head_seq(L)
    va = vfy(L, adopt=True)
    o["R1b.verify_adopt"] = {"result": va["result"], "adoption_seq": va["adoption_seq"], "entries": only(va, p + "ta"),
                             "head_moved": head_seq(L) - h}
    if va["adoption_seq"]:
        rid = L.history(limit=100000).revisions[-1].revision_id
        o["R1b.adoption_records"] = [[r.op, r.entity_id, r.attr, r.new] for r in L.get_revision(rid).records]
    v2 = vfy(L)
    o["R1b.verify_2"] = {"result": v2["result"], "entries": only(v2, p + "ta")}
    # R1.c Python boolean True
    cs = Changeset(actor="i60r", actor_type="agent")
    for x in ("ba", "bb"):
        cs.upsert_node(p + x)
    cs.create_relationship(p + "ba", "I60RREL", p + "bb", qualifiers={"temporal": True})
    o["R1c.commit_seq"] = L.commit(cs).revision.seq
    cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ?", [p + "ba"])
    o["R1c.row_qualifiers"] = [r[0] for r in cur.fetchall()]
    v3 = vfy(L)
    o["R1c.verify_1"] = {"result": v3["result"], "entries": only(v3, p + "ba")}
    h = head_seq(L)
    va = vfy(L, adopt=True)
    o["R1c.verify_adopt"] = {"adoption_seq": va["adoption_seq"], "head_moved": head_seq(L) - h}
    v4 = vfy(L)
    o["R1c.verify_2"] = {"result": v4["result"], "entries": only(v4, p + "ba")}
    # R1.d unrecorded engine edge with text "true"; R1.e unrecorded engine edge with JSON true
    e.create_edge(p + "ya", "I60RUT", p + "tb", qualifiers={"temporal": "true"})
    e.create_edge(p + "ya", "I60RUB", p + "ba", qualifiers={"temporal": True})
    cur.execute("SELECT p, qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p IN ('I60RUT', 'I60RUB')", [p + "ya"])
    o["R1de.rows"] = [list(r) for r in cur.fetchall()]
    v5 = vfy(L)
    o["R1d.verify_1"] = [x for x in v5["entries"] if "I60RUT" in x[1] or "I60RUT" in str(x[4])]
    o["R1e.verify_1"] = [x for x in v5["entries"] if "I60RUB" in x[1] or "I60RUB" in str(x[4])]
    h = head_seq(L)
    va = vfy(L, adopt=True)
    o["R1d.verify_adopt"] = {"adoption_seq": va["adoption_seq"], "head_moved": head_seq(L) - h}
    v6 = vfy(L)
    o["R1d.verify_2"] = [x for x in v6["entries"] if "I60RUT" in x[1] or "I60RUT" in str(x[4])]
    o["R1e.verify_2"] = [x for x in v6["entries"] if "I60RUB" in x[1] or "I60RUB" in str(x[4])]
    o["final_result"] = v6["result"]
    cur.close()
    c.close()


# ------------------------------------------------------------------------------------------------ FE-2 (I60RV)
def fe2():
    o = OBS.setdefault("fe2", {})
    c, e = open_ns("I60RV")
    L = e.ledger
    s = stamp().lower()
    n, orphan = f"i60r_on{s}", f"i60r_orphan{s}"
    o["verify_start"] = vfy(L)["result"]
    cs = Changeset(actor="i60r", actor_type="agent", post_commit_properties={orphan: {"k": "v"}})
    cs.upsert_node(n)
    res = L.commit(cs)
    o["commit"] = {"seq": res.revision.seq, "post_applied": res.post_commit_applied, "post_error": res.post_commit_error}
    cur = c.cursor()
    cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", [orphan])
    o["orphan_node_rows"] = int(cur.fetchone()[0])
    cur.execute('SELECT "key", val FROM Graph_KG.rdf_props WHERE s = ?', [orphan])
    o["orphan_prop_rows"] = [list(r) for r in cur.fetchall()]
    v = vfy(L)
    o["verify_1"] = {"result": v["result"], "entries": only(v, orphan)}
    va = vfy(L, adopt=True)
    o["verify_adopt_seq"] = va["adoption_seq"]
    o["verify_2"] = vfy(L)["result"]
    cur.close()
    c.close()


# ------------------------------------------------------------------------------------------------ FE-3 (I60RA)
def fe3():
    import iris
    o = OBS.setdefault("fe3", {})
    s = stamp().lower()
    cB, eB = open_ns("I60RA")
    LB = eB.ledger
    o["t0"] = counters("I60RA")
    # R3.a: caller A's committed nested ledger commit holds the head and the counter row
    cA, eA = open_ns("I60RA")
    cA.setAutoCommit(False)
    try:
        csA = Changeset(actor="i60rA", actor_type="agent"); csA.upsert_node(f"i60r_la{s}")
        o["R3a.A_commit"] = eA.ledger.commit(csA).revision.seq
        o["R3a.t1_A_open"] = counters("I60RA")
        csB = Changeset(actor="i60rB", actor_type="agent"); csB.upsert_node(f"i60r_lb{s}")
        t = time.time()
        try:
            LB.commit(csB); o["R3a.B"] = "succeeded"
        except Exception as ex:  # noqa: BLE001
            o["R3a.B"] = exc(ex)
        o["R3a.B_wait_s"] = round(time.time() - t, 1)
        o["R3a.t2_after_B_A_open"] = counters("I60RA")
        # R3.c: the strict guard's counter call from a third process while A is open
        c3 = connect("I60RA")
        n3 = iris.createIRIS(c3)
        t = time.time()
        try:
            o["R3c.count_status_A_open"] = str(n3.classMethodValue("Graph.KG.Ledger", "Count", "rej_strict_block"))[:200]
        except Exception as ex:  # noqa: BLE001
            o["R3c.count_status_A_open"] = exc(ex)
        o["R3c.count_wait_s"] = round(time.time() - t, 1)
        o["R3c.t3_after_count_A_open"] = counters("I60RA")
    finally:
        cA.rollback(); cA.setAutoCommit(True)
    o["R3a.t4_after_A_rollback"] = counters("I60RA")
    t = time.time()
    try:
        o["R3c.count_status_after"] = str(n3.classMethodValue("Graph.KG.Ledger", "Count", "rej_strict_block"))[:200]
    except Exception as ex:  # noqa: BLE001
        o["R3c.count_status_after"] = exc(ex)
    o["R3c.count_after_wait_s"] = round(time.time() - t, 1)
    o["R3c.t5_after_count"] = counters("I60RA")
    c3.close()
    hb = LB.head()
    rB = LB.commit(csB)
    o["R3a.B_after_rollback"] = {"seq": rB.revision.seq, "parent_is_prior_head": rB.revision.parent_id == hb.revision_id,
                                 "seq_is_next": rB.revision.seq == hb.seq + 1}
    # R3.d: A's nested commit refused 'inconsistent' (uncounted) still holds the head, not the counter row
    o["R3d.t0"] = counters("I60RA")
    cA.setAutoCommit(False)
    try:
        csA = Changeset(actor="i60rA", actor_type="agent", message="m" * 5000); csA.upsert_node(f"i60r_ld{s}")
        try:
            eA.ledger.commit(csA); o["R3d.A_commit"] = "succeeded"
        except Exception as ex:  # noqa: BLE001
            o["R3d.A_commit"] = exc(ex)
        csB2 = Changeset(actor="i60rB", actor_type="agent"); csB2.upsert_node(f"i60r_le{s}")
        t = time.time()
        try:
            LB.commit(csB2); o["R3d.B"] = "succeeded"
        except Exception as ex:  # noqa: BLE001
            o["R3d.B"] = exc(ex)
        o["R3d.B_wait_s"] = round(time.time() - t, 1)
        o["R3d.t1_after_B_A_open"] = counters("I60RA")
    finally:
        cA.rollback(); cA.setAutoCommit(True)
    o["R3d.t2_after_A_rollback"] = counters("I60RA")
    # R3.b: a Native API lock on the head from another connection (no transaction)
    cn = connect("I60RA")
    nat = iris.createIRIS(cn)
    try:
        nat.lock("", 2, "^IVG.Ledger", "head")
        o["R3b.native_lock"] = "acquired"
    except Exception as ex:  # noqa: BLE001
        o["R3b.native_lock"] = exc(ex)
    c0 = counters("I60RA")
    csB3 = Changeset(actor="i60rB", actor_type="agent"); csB3.upsert_node(f"i60r_lf{s}")
    t = time.time()
    try:
        o["R3b.B"] = {"seq": LB.commit(csB3).revision.seq}
    except Exception as ex:  # noqa: BLE001
        o["R3b.B"] = exc(ex)
    o["R3b.B_wait_s"] = round(time.time() - t, 1)
    o["R3b.delta"] = delta(c0, counters("I60RA"))
    try:
        nat.unlock("", "^IVG.Ledger", "head")
    except Exception as ex:  # noqa: BLE001
        o["R3b.unlock"] = exc(ex)
    cn.close()
    cA.close(); cB.close()


# ------------------------------------------------------------------------------------------------ FE-4 / FE-6 (I60RA)
def fe4():
    o = OBS.setdefault("fe4", {})
    c, e = open_ns("I60RA")
    L = e.ledger
    events = []
    L.register_metrics_hook(lambda d: events.append(d.get("outcome")))
    s = stamp().lower()
    pfx = f"i60r_red{s}"
    ids = [f"{pfx}|{i}" for i in range(3)]
    cs = Changeset(actor="i60r", actor_type="agent")
    for i in ids:
        cs.upsert_node(i, properties={"p": "x"})
    L.commit(cs)
    cs = Changeset(actor="i60r", actor_type="agent")
    for i in ids:
        cs.delete_node(i)
    L.commit(cs)
    r1 = L.redact(None, prefix=pfx, batch_size=1, max_batches=1)
    o["redact_1"] = {"complete": r1.complete, "batches": r1.batches}
    o["in_progress"] = L.redaction_in_progress() is not None
    unknown = "e" * 32
    known = L.history(limit=1).revisions[0].revision_id
    rd = {}
    for name, fn in (("get_revision", lambda: L.get_revision(unknown)), ("diff", lambda: L.diff(known, unknown)),
                     ("reconstruct", lambda: L.reconstruct(unknown)),
                     ("export_reconstruction", lambda: L.export_reconstruction(unknown, f"/tmp/i60r-{s}.ndjson"))):
        try:
            fn(); rd[name] = "returned"
        except Exception as ex:  # noqa: BLE001
            rd[name] = exc(ex)["class"]
    o["R5.readers_unknown_id_during"] = rd
    try:
        o["R5.head_during"] = L.head().seq
    except Exception as ex:  # noqa: BLE001
        o["R5.head_during"] = exc(ex)
    h0, c0, ev0 = head_seq(L), counters("I60RA"), len(events)
    cs = Changeset(actor="i60r", actor_type="agent")
    cs.upsert_node(f"{pfx}|9")
    try:
        L.commit(cs); o["R4.blocked_commit"] = "succeeded"
    except Exception as ex:  # noqa: BLE001
        o["R4.blocked_commit"] = exc(ex)
    o["R4.events"] = events[ev0:]
    o["R4.counter_delta"] = delta(c0, counters("I60RA"))
    o["R4.head_moved"] = head_seq(L) - h0
    r2 = L.redact(None, prefix=pfx)
    o["redact_2"] = {"complete": r2.complete}
    o["in_progress_after"] = L.redaction_in_progress() is not None
    rd = {}
    for name, fn in (("get_revision", lambda: L.get_revision(unknown)), ("diff", lambda: L.diff(known, unknown)),
                     ("reconstruct", lambda: L.reconstruct(unknown)),
                     ("export_reconstruction", lambda: L.export_reconstruction(unknown, f"/tmp/i60r-{s}.ndjson"))):
        try:
            fn(); rd[name] = "returned"
        except Exception as ex:  # noqa: BLE001
            rd[name] = exc(ex)["class"]
    o["R5.readers_unknown_id_after"] = rd
    o["R5.export_file_written"] = Path(f"/tmp/i60r-{s}.ndjson").exists()
    c.close()


# ------------------------------------------------------------------------------------------------ FE-5 (I60RA)
def fe5():
    o = OBS.setdefault("fe5", {})
    c, e = open_ns("I60RA")
    L = e.ledger
    events = []
    L.register_metrics_hook(lambda d: events.append(d.get("outcome")))
    s = stamp().lower()
    cur = c.cursor()
    cases = [("message_4000", {"message": "m" * 4000}), ("message_5000", {"message": "m" * 5000}),
             ("key_256", {"idempotency_key": "k" * 240 + s[:16]}), ("key_300", {"idempotency_key": "k" * 284 + s[:16]}),
             ("correlation_300", {"correlation_id": "c" * 300}), ("actor_300", {"actor": "a" * 300}),
             ("source_object_4100", {"source": {"blob": "s" * 4100}})]
    for name, kw in cases:
        h0, c0, ev0 = head_seq(L), counters("I60RA"), len(events)
        args = dict(actor="i60r", actor_type="agent")
        args.update(kw)
        cs = Changeset(**args)
        nid = f"i60r_lim_{name}_{s}"
        cs.upsert_node(nid)
        try:
            res = {"ok_seq": L.commit(cs).revision.seq}
        except Exception as ex:  # noqa: BLE001
            res = exc(ex)
        cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", [nid])
        o[name] = {"result": res, "head_moved": head_seq(L) - h0, "node_rows": int(cur.fetchone()[0]),
                   "counter_delta": delta(c0, counters("I60RA")), "events": events[ev0:]}
    # R6.c keyed retry with an over-long message replays
    key = f"i60r-k-{s}"
    cs = Changeset(actor="i60r", actor_type="agent", idempotency_key=key, message="first")
    cs.upsert_node(f"i60r_lk_{s}")
    first = L.commit(cs)
    c0, ev0 = counters("I60RA"), len(events)
    cs = Changeset(actor="i60r", actor_type="agent", idempotency_key=key, message="m" * 5000)
    cs.upsert_node(f"i60r_lk_{s}")
    try:
        r = L.commit(cs)
        res = {"seq": r.revision.seq, "replayed": r.replayed, "same_seq": r.revision.seq == first.revision.seq}
    except Exception as ex:  # noqa: BLE001
        res = exc(ex)
    o["R6c.keyed_retry_long_message"] = {"result": res, "counter_delta": delta(c0, counters("I60RA")), "events": events[ev0:]}
    cur.close()
    c.close()


# ------------------------------------------------------------------------------------------------ C4 / CG-3 (I60RA)
def c4():
    o = OBS.setdefault("c4", {})
    c, e = open_ns("I60RA")
    L = e.ledger
    s = stamp().lower()

    def missing_endpoint():
        cs = Changeset(actor="i60r", actor_type="agent")
        cs.upsert_node(f"i60r_nn{s}")
        cs.create_relationship(f"i60r_nn{s}", "I60RM", f"i60r_absent{s}")
        return cs
    for label, cls in (("root_NodeNotFoundError", ivg.NodeNotFoundError), ("ledger_NodeNotFoundError", LE.NodeNotFoundError),
                       ("IVGError", IVGError), ("ChangesetOperationError", LE.ChangesetOperationError)):
        try:
            try:
                L.commit(missing_endpoint()); o[label] = "committed"
            except cls as ex:
                o[label] = {"caught": True, "as": type(ex).__module__ + "." + type(ex).__name__}
        except Exception as ex:  # noqa: BLE001
            o[label] = {"caught": False, "escaped": exc(ex)}
    o["root_is_ledger_class"] = ivg.NodeNotFoundError is LE.NodeNotFoundError
    o["ledger_subclasses_root"] = issubclass(LE.NodeNotFoundError, ivg.NodeNotFoundError)
    # CG-3: node operations on an ID that is no node
    for label, build in (("set_property", lambda cs: cs.set_property(f"i60r_ghost{s}", "k", "v")),
                         ("add_label", lambda cs: cs.add_label(f"i60r_ghost{s}", "L")),
                         ("remove_property", lambda cs: cs.remove_property(f"i60r_ghost{s}", "k"))):
        cs = Changeset(actor="i60r", actor_type="agent")
        cs.upsert_node(f"i60r_real{s}{label}")
        build(cs)
        try:
            L.commit(cs); o[f"CG3.{label}"] = "committed"
        except Exception as ex:  # noqa: BLE001
            o[f"CG3.{label}"] = exc(ex)
    c.close()


SECTIONS = {"setup": setup, "fe1": fe1, "fe2": fe2, "fe3": fe3, "fe4": fe4, "fe5": fe5, "c4": c4}

if __name__ == "__main__":
    names = sys.argv[1:] or list(SECTIONS)
    OBS["started"] = stamp()
    OBS["ok"], OBS["errors"] = [], {}
    for n in names:
        try:
            SECTIONS[n]()
            OBS["ok"].append(n)
        except Exception:  # noqa: BLE001
            OBS["errors"][n] = traceback.format_exc()[-3000:]
    OBS["finished"] = stamp()
    out = HERE / f"observed-{OBS['started']}-{'-'.join(names)}.json"
    out.write_text(json.dumps(OBS, indent=1, default=str) + "\n")
    print(out)
    print(json.dumps({"ok": OBS["ok"], "errors": list(OBS["errors"])}))
