"""Iteration 60 native probe: run the frozen ledger predictions (adopted iteration-59 W1/W2 rows and new N rows).

Local fixture only (local-runtime/runtime.py: ivg-uplift-next-20261115, 127.0.0.1:35975, identity-checked). Writes only
in the task-owned namespaces I60LA (W1 client/admission), I60LB (W2 readers), I60LC (never-enabled, then
max_ops=2/recon_bound=1) and I60LD (recon_bound=2 neighbor); IDs start with i60. No erase/reset/kill, no USER write.
Usage: python -B ledger_probe.py <section ...>  (sections: w1 w2 c d lock large; default all). Output: observed-<stamp>-<sections>.json
"""
import json, sys, time, traceback, tempfile, os, threading
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "local-runtime"))
import runtime as rt  # local fixture runtime
from iris_vector_graph.ledger import Changeset
from iris_vector_graph.ledger import errors as LE
from iris_vector_graph.ledger.replay import Diff

OBS = {}


def exc(e):
    d = {"class": type(e).__name__, "mro": [c.__name__ for c in type(e).__mro__[:4]], "msg": str(e)[:300]}
    for a in ("op_index", "missing_node", "reason", "current_head", "limit", "bound", "estimate"):
        if hasattr(e, a):
            d[a] = getattr(e, a)
    return d


def attempt(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as e:  # observation, not a failure of the probe
        return {"ok": False, "exc": exc(e)}


def rev(r):
    return None if r is None else {"seq": r.seq, "id": r.revision_id, "parent": r.parent_id, "kind": r.kind,
                                   "actor": r.actor, "op_count": r.op_count}


def cr(res):
    return {"revision": rev(res.revision), "replayed": res.replayed, "stmt_ids": dict(res.stmt_ids),
            "post_commit_applied": res.post_commit_applied, "post_commit_error": res.post_commit_error}


def recs(L, rid):
    return [[r.ordinal, r.op, r.entity_kind, r.entity_id, r.attr, r.prior, r.new] for r in L.get_revision(rid).records]


def diffl(d):
    return [[e.entity_kind, e.entity_id, e.attr, e.before, e.after] for e in d.entries]


def vfy(L, **kw):
    r = L.verify(**kw)
    return {"result": r.result, "seq": r.verified_seq, "diffs": [[e.entity_kind, e.entity_id, e.attr, e.before, e.after] for e in r.differences],
            "adoption": rev(r.adoption_revision)}


def node(e, nid):
    n = e.get_node(nid)
    return None if n is None else {k: n.get(k) for k in ("id", "labels", "properties")} if isinstance(n, dict) else str(n)


def stats(L):
    s = L.stats()
    return {"commits_ok": s.commits_ok, "replays_idem": s.replays_idem, "rej": dict(s.rejections), "state": s.state, "strict": s.strict}


def cs(actor="w1", actor_type="agent", **kw):
    return Changeset(actor=actor, actor_type=actor_type, **kw)


def commit(L, c):
    return attempt(lambda: cr(L.commit(c)))


def open_ns(ns):
    c = rt.connect(ns)
    e = rt.engine(c, ns)
    return c, e


# ----------------------------------------------------------------------------------------------- W1 (I60LA)
def w1():
    c, e = open_ns("I60LA")
    L = e.ledger
    ev = []
    L.register_metrics_hook(lambda d: ev.append(d))
    o = OBS.setdefault("w1", {})
    o["enable"] = rev(L.enable())
    o["events_after_enable"] = list(ev)
    seed = cs(); seed.create_node("i60_m"); seed.create_node("i60_a"); seed.create_node("i60_b")
    o["seed"] = commit(L, seed)

    # P1.1 idempotency replay vs conflict
    c1 = cs(message="m1", correlation_id="c1", idempotency_key="i60-k1"); c1.create_node("i60_p11", properties={"v": "v1"})
    h0 = L.head().seq; n0 = len(L.history(limit=1000).revisions)
    o["P1.1.A.first"] = commit(L, c1)
    c2 = cs(message="m2", correlation_id="c2", idempotency_key="i60-k1"); c2.create_node("i60_p11", properties={"v": "v1"})
    o["P1.1.A.retry"] = commit(L, c2)
    o["P1.1.A.head_hist"] = [h0, L.head().seq, n0, len(L.history(limit=1000).revisions)]
    c3 = cs(idempotency_key="i60-k1"); c3.create_node("i60_p11", properties={"v": "v2"})
    hb = L.head().seq
    o["P1.1.B.conflict"] = commit(L, c3)
    o["P1.1.B.after"] = {"head": L.head().seq, "head_before": hb, "node": node(e, "i60_p11")}
    c4 = cs(idempotency_key="i60-k1b"); c4.set_property("i60_m", "z", "1")
    o["P1.1.B.fresh"] = commit(L, c4)

    # P1.2 canonical form and fingerprint
    def mk(order=(("a", "1"), ("b", "2")), actor_type="agent", message=None, props=None):
        x = cs(actor_type=actor_type, message=message)
        for k, v in order:
            x.set_property("i60_m", k, v)
        if props is not None:
            x.create_node("i60_px", properties=props)
        return x
    A, B = mk(), mk()
    o["P1.2"] = {
        "same_json": A.canonical_json() == B.canonical_json(), "same_fp": A.fingerprint() == B.fingerprint(), "fp_len": len(A.fingerprint()),
        "dict_order_same_fp": mk(props={"x": 1, "y": 2}).fingerprint() == mk(props={"y": 2, "x": 1}).fingerprint(),
        "reversed_same_fp": mk(order=(("b", "2"), ("a", "1"))).fingerprint() == A.fingerprint(),
        "actor_type_same_fp": mk(actor_type="human").fingerprint() == A.fingerprint(),
        "message_same_fp": mk(message="other").fingerprint() == A.fingerprint()}
    k1 = cs(idempotency_key="i60-k12"); k1.set_property("i60_m", "a", "1"); k1.set_property("i60_m", "b", "2")
    o["P1.2.commit_first"] = commit(L, k1)
    k2 = cs(idempotency_key="i60-k12"); k2.set_property("i60_m", "b", "2"); k2.set_property("i60_m", "a", "1")
    o["P1.2.commit_reversed_same_key"] = commit(L, k2)

    # S1.3 builder refusals, S1.4 numeric text
    def b(f):
        x = cs()
        return attempt(lambda: (f(x), [op for op in x.ops])[1])
    o["S1.3"] = {"id": b(lambda x: x.set_property("i60_m", "id", "v")), "__graph": b(lambda x: x.set_property("i60_m", "__graph", "v")),
                 "idx": b(lambda x: x.set_property("i60_m", "idx", "v")),
                 "both_refs": b(lambda x: x.delete_relationship(("i60_a", "R", "i60_b"), stmt_id="1")),
                 "tuple_only": b(lambda x: x.delete_relationship(("i60_a", "R", "i60_b"))),
                 "create_node_reserved": b(lambda x: x.create_node("i60_q", properties={"id": "q"}))}
    n1 = cs(); n1.set_property("i60_m", "p", 30); n2 = cs(); n2.set_property("i60_m", "p", "30")
    o["S1.4"] = {"same_fp": n1.fingerprint() == n2.fingerprint(), "json": n1.canonical_json()}

    # P2.1 expected head; P2.2 admission order; S2.3 empty changesets
    h = L.head()
    x = cs(expected_head=h.revision_id); x.create_node("i60_x21")
    o["P2.1.A"] = {"head": rev(h), "res": commit(L, x)}
    h = L.head()
    y = cs(); y.create_node("i60_y21"); o["P2.1.B.y"] = commit(L, y)
    x2 = cs(expected_head=h.revision_id); x2.create_node("i60_x21b")
    o["P2.1.B.stale"] = commit(L, x2)
    o["P2.1.B.after"] = {"head": rev(L.head()), "node": node(e, "i60_x21b")}
    z = cs(); z.create_node("i60_z21"); o["P2.1.B.next"] = commit(L, z)
    k1r = cs(idempotency_key="i60-k12", expected_head=h.revision_id); k1r.set_property("i60_m", "a", "1"); k1r.set_property("i60_m", "b", "2")
    o["P2.2.A.replay_stale"] = commit(L, k1r)
    fr = cs(idempotency_key="i60-k22", expected_head=h.revision_id); fr.create_node("i60_x22")
    o["P2.2.B.fresh_stale"] = commit(L, fr)
    un = cs(expected_head="0123456789abcdef0123456789abcdef"); un.create_node("i60_x22u")
    o["P2.2.B.unknown"] = commit(L, un)
    st0 = stats(L); ev0 = len(ev)
    o["S2.3.empty_stale"] = commit(L, cs(expected_head=h.revision_id))
    o["S2.3.empty_current"] = commit(L, cs(expected_head=L.head().revision_id))
    o["S2.3.counters_events"] = {"stats_before": st0, "stats_after": stats(L), "events_added": ev[ev0:]}
    # N2 (refusal part): the key of the stale refusal above (i60-k22) is free for other ops
    k22 = cs(idempotency_key="i60-k22"); k22.create_node("i60_n2r")
    o["N2.refused_key_free"] = commit(L, k22)

    # P3.1 failing operation vs auto-stub
    hb = L.head().seq; ev0 = len(ev)
    f = cs(); f.create_node("i60_f1"); f.create_node("i60_f2"); f.create_relationship("i60_f1", "R", "i60_missing")
    o["P3.1.A"] = {"res": commit(L, f), "head": [hb, L.head().seq], "nodes": [node(e, "i60_f1"), node(e, "i60_f2")], "events": ev[ev0:]}
    g = cs(auto_stub_missing_nodes=True); g.create_node("i60_f1"); g.create_node("i60_f2"); g.create_relationship("i60_f1", "R", "i60_missing")
    o["P3.1.B"] = {"ops": [op["op"] for op in g.ops], "res": commit(L, g), "missing": node(e, "i60_missing")}

    # S3.3 hierarchy and unknown code
    names = ["StaleHeadError", "UnknownRevisionError", "IdempotencyConflictError", "NodeNotFoundError", "ChangesetTooLargeError",
             "EmptyChangesetError", "LedgerDisabledError", "LedgerNotEnabledError", "LedgerLockTimeoutError", "LedgerStrictModeError"]
    unk = LE.from_commit_error({"ok": False, "error": "weird_code", "reason": "why"})
    o["S3.3"] = {"subclass": {n: issubclass(getattr(LE, n), LE.LedgerError) for n in names},
                 "unknown": {"class": type(unk).__name__, "msg": str(unk)}}

    # S3.4 hook that raises; event fields
    def bad(d):
        raise RuntimeError("hook boom")
    L.register_metrics_hook(bad)
    ev0 = len(ev)
    hk = cs(); hk.create_node("i60_hook")
    o["S3.4"] = {"res": commit(L, hk), "event": ev[ev0:]}
    L._hooks.remove(bad)

    # N3 duplicate relationship vs upsert
    r0 = cs(); r0.create_relationship("i60_a", "R", "i60_b"); o["N3.setup"] = commit(L, r0)
    hb = L.head().seq
    d1 = cs(); d1.set_property("i60_a", "x", "1"); d1.create_relationship("i60_a", "R", "i60_b")
    o["N3.A"] = {"res": commit(L, d1), "head": [hb, L.head().seq], "a": node(e, "i60_a")}
    u1 = cs(); u1.set_property("i60_a", "x", "1"); u1.upsert_relationship("i60_a", "R", "i60_b", qualifiers={"w": "2"})
    ru = commit(L, u1)
    o["N3.B"] = {"res": ru, "records": recs(L, ru["value"]["revision"]["id"]) if ru["ok"] else None,
                 "cypher": attempt(lambda: e.execute_cypher("MATCH (a {id:'i60_a'})-[r:R]->(b {id:'i60_b'}) RETURN count(r) AS n").rows)}

    # N4 record shape and same-value no-op
    n4 = cs(); n4.create_node("i60_n4", labels=["L"], properties={"p": "1"}); r = commit(L, n4)
    o["N4.A"] = {"res": r, "records": recs(L, r["value"]["revision"]["id"]) if r["ok"] else None}
    n4b = cs(); n4b.set_property("i60_n4", "p", "1"); n4b.set_property("i60_n4", "q", "2"); r = commit(L, n4b)
    o["N4.B.mixed"] = {"res": r, "records": recs(L, r["value"]["revision"]["id"]) if r["ok"] else None}
    n4c = cs(); n4c.set_property("i60_n4", "p", "1"); r = commit(L, n4c)
    o["N4.B.allnoop"] = {"res": r, "records": recs(L, r["value"]["revision"]["id"]) if r["ok"] else None}

    # N5 unknown revision IDs
    hd = L.head(); g0 = L.history(limit=1).revisions[0]
    tmpd = tempfile.mkdtemp(prefix="i60-n5-"); path = os.path.join(tmpd, "x.ndjson")
    o["N5.A"] = {"get_revision": attempt(lambda: L.get_revision("0" * 32)), "diff": attempt(lambda: L.diff(g0.revision_id, "0" * 32)),
                 "reconstruct": attempt(lambda: L.reconstruct("f" * 32)), "export": attempt(lambda: str(L.export_reconstruction("f" * 32, path))),
                 "export_file_exists": os.path.exists(path), "malformed": attempt(lambda: L.get_revision("xyz"))}
    o["N5.B"] = {"get_revision_head_seq": L.get_revision(hd.revision_id).info.seq == hd.seq, "diff_equal": len(L.diff(hd.revision_id, hd.revision_id))}

    # N7 statement addressing
    s1 = cs(); s1.create_node("i60_sa"); s1.create_node("i60_sb"); s1.create_relationship("i60_sa", "R", "i60_sb"); r1 = commit(L, s1)
    o["N7.C1"] = r1
    sid = list(r1["value"]["stmt_ids"].values())[0] if r1["ok"] else None
    s2 = cs(); s2.set_qualifier(("i60_sa", "R", "i60_sb", None), "w", "1"); r2 = commit(L, s2)
    o["N7.C2"] = {"res": r2, "records": recs(L, r2["value"]["revision"]["id"]) if r2["ok"] else None}
    hb = L.head().seq
    s3b = cs(); s3b.delete_relationship(stmt_id=str(int(sid) + 100000)) if sid else None
    o["N7.B.unknown_stmt"] = {"res": commit(L, s3b), "head": [hb, L.head().seq]}
    s3 = cs(); s3.delete_relationship(stmt_id=sid); r3 = commit(L, s3)
    o["N7.C3"] = {"res": r3, "records": recs(L, r3["value"]["revision"]["id"]) if r3["ok"] else None}
    if r1["ok"] and r3["ok"]:
        st3 = L.reconstruct(r3["value"]["revision"]["id"])
        o["N7.C3.reconstruct_has"] = st3.stmt_for_tuple(("i60_sa", "R", "i60_sb", None))
        o["N7.C3.diff"] = diffl(L.diff(r1["value"]["revision"]["id"], r3["value"]["revision"]["id"]))

    # N8 counters for a commit, a replay and a stale refusal
    s0 = stats(L)
    q = cs(idempotency_key="i60-k8"); q.create_node("i60_n8"); o["N8.commit"] = commit(L, q); s1_ = stats(L)
    q2 = cs(idempotency_key="i60-k8"); q2.create_node("i60_n8"); ev0 = len(ev); o["N8.replay"] = commit(L, q2); s2_ = stats(L)
    o["N8.replay_event"] = ev[ev0:]
    q3 = cs(expected_head=h.revision_id); q3.create_node("i60_n8s"); o["N8.stale"] = commit(L, q3); s3_ = stats(L)
    o["N8.stats"] = [s0, s1_, s2_, s3_]
    o["N8.status"] = attempt(lambda: {"state": e.status().ledger.state, "head_seq": e.status().ledger.head_seq, "head": L.head().seq})

    # P5.1 post-commit properties; S5.3 dirty marking
    p = cs(post_commit_properties={"i60_p": {"last_rev": "$REVISION_ID"}}, idempotency_key="i60-k51"); p.create_node("i60_p")
    r = commit(L, p)
    o["P5.1.A"] = {"res": r, "node": node(e, "i60_p"), "records": recs(L, r["value"]["revision"]["id"]) if r["ok"] else None,
                   "verify": vfy(L)}
    p0 = cs(); p0.create_node("i60_p0"); o["P5.1.B.plain"] = {"res": commit(L, p0), "node": node(e, "i60_p0")}
    cur = c.cursor(); cur.execute("UPDATE Graph_KG.rdf_props SET val='x' WHERE s='i60_p' AND \"key\"='last_rev'"); cur.close()
    p2 = cs(post_commit_properties={"i60_p": {"last_rev": "$REVISION_ID"}}, idempotency_key="i60-k51"); p2.create_node("i60_p")
    o["P5.1.B.replay"] = {"before": node(e, "i60_p"), "res": commit(L, p2), "after": node(e, "i60_p")}
    o["S5.3.before"] = getattr(e, "_nkg_dirty", None)
    e._nkg_dirty = False
    sp = cs(); sp.set_property("i60_m", "dirty", "1"); o["S5.3.prop"] = [commit(L, sp)["ok"], getattr(e, "_nkg_dirty", None)]
    sr = cs(); sr.create_relationship("i60_m", "D", "i60_a"); o["S5.3.rel"] = [commit(L, sr)["ok"], getattr(e, "_nkg_dirty", None)]
    o["S5.3.status"] = attempt(lambda: {"pending_sync": getattr(e.status(), "pending_sync", "n/a")})
    o["S5.3.nkg_meta"] = attempt(lambda: str(e._iris_obj().classMethodValue("Graph.KG.Meta", "GetNKG", "$meta", "nodeCount")))

    # P5.2 post-commit ghost target and caller transaction rollback
    pg = cs(post_commit_properties={"i60_ghost": {"k": "v"}}); pg.create_node("i60_pg")
    o["P5.2.A"] = {"res": commit(L, pg), "ghost_node": node(e, "i60_ghost"),
                   "ghost_rows": attempt(lambda: (lambda cu: (cu.execute("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s='i60_ghost'"), cu.fetchone()[0])[1])(c.cursor())),
                   "ghost_node_rows": attempt(lambda: (lambda cu: (cu.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='i60_ghost'"), cu.fetchone()[0])[1])(c.cursor()))}
    hb = L.head()
    c.setAutoCommit(False)
    try:
        pt = cs(post_commit_properties={"i60_ptx": {"k": "v"}}); pt.create_node("i60_ptx")
        o["P5.2.B.in_txn"] = commit(L, pt)
    finally:
        c.rollback(); c.setAutoCommit(True)
    o["P5.2.B.after"] = {"head": [hb.seq, L.head().seq], "node": node(e, "i60_ptx"),
                         "props": attempt(lambda: (lambda cu: (cu.execute("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s='i60_ptx'"), cu.fetchone()[0])[1])(c.cursor()))}
    nx = cs(); nx.create_node("i60_after_rb"); o["P5.2.B.next"] = commit(L, nx)

    # N2 key freed by a caller rollback; kept key conflicts
    c.setAutoCommit(False)
    try:
        kx = cs(idempotency_key="i60-k2"); kx.create_node("i60_n2x"); o["N2.A.in_txn"] = commit(L, kx)
    finally:
        c.rollback(); c.setAutoCommit(True)
    ky = cs(idempotency_key="i60-k2"); ky.create_node("i60_n2y"); o["N2.A.reuse"] = commit(L, ky)
    kz = cs(idempotency_key="i60-k2"); kz.create_node("i60_n2z"); o["N2.B.conflict"] = commit(L, kz)

    # P4.1 strict toggle; N8 strict counter; P4.2 disable/enable; P3.2 B; S4.3 caller transaction
    o["P4.1.A"] = {"create": attempt(lambda: e.create_node("i60_free")), "verify": vfy(L)}
    lc = cs(); lc.create_node("i60_l41"); o["P4.1.A.commit"] = commit(L, lc)
    sb = stats(L)
    L.set_strict(True)
    o["P4.1.B"] = {"create": attempt(lambda: e.create_node("i60_blocked")), "node": node(e, "i60_blocked"),
                   "cypher": attempt(lambda: e.execute_cypher("CREATE (n:I60 {id:'i60_cy'}) RETURN n").rows),
                   "cypher_read": attempt(lambda: e.execute_cypher("MATCH (n {id:'i60_m'}) RETURN n.id").rows),
                   "cy_node": node(e, "i60_cy")}
    lc2 = cs(); lc2.create_node("i60_l41s"); o["P4.1.B.commit"] = commit(L, lc2)
    o["N8.strict_counter"] = [sb["rej"].get("rej_strict_block"), stats(L)["rej"].get("rej_strict_block")]
    pcs = cs(post_commit_properties={"i60_strictpc": {"k": "v"}}); pcs.create_node("i60_strictpc")
    o["P5.1.B.strict_pcp"] = {"res": commit(L, pcs), "node": node(e, "i60_strictpc")}
    L.set_strict(False)
    o["P4.1.B.after_off"] = attempt(lambda: e.create_node("i60_free2"))
    # S4.5 second engine sees strict within ~5 s
    c2_, e2 = open_ns("I60LA")
    o["S4.5.prime"] = attempt(lambda: e2.create_node("i60_e2a"))
    L.set_strict(True)
    t0 = time.time(); seen = []
    while time.time() - t0 < 8:
        r_ = attempt(lambda: e2.create_node(f"i60_e2_{len(seen)}"))
        seen.append([round(time.time() - t0, 2), r_["ok"], (r_.get("exc") or {}).get("class")])
        if not r_["ok"]:
            break
        time.sleep(0.5)
    o["S4.5"] = seen
    c2_.close()
    # P4.2: strict on; disable twice; unrecorded write; enable again (default strict)
    hb = L.head()
    o["P4.2.A.disable"] = [attempt(lambda: L.disable()), attempt(lambda: L.disable())]
    o["P4.2.A.create_off"] = attempt(lambda: e.create_node("i60_off"))
    o["P4.2.A.head_unchanged"] = [hb.seq, L.head().seq]
    sd = stats(L); ev0 = len(ev)
    dc = cs(); dc.create_node("i60_dis"); o["P3.2.B.commit_disabled"] = commit(L, dc)
    o["P3.2.B.stats"] = [sd["rej"].get("rej_disabled"), stats(L)["rej"].get("rej_disabled")]; o["P3.2.B.events"] = ev[ev0:]
    o["N6.B.disabled_readers"] = {"head": attempt(lambda: rev(L.head())), "history_n": attempt(lambda: len(L.history(limit=1000).revisions)),
                                  "status_state": attempt(lambda: e.status().ledger.state)}
    en = attempt(lambda: rev(L.enable()))
    o["P4.2.A.reenable"] = {"res": en, "strict_meta": L.meta().get("strict"), "create_after": attempt(lambda: e.create_node("i60_after_reenable")),
                            "verify": vfy(L)}
    if en["ok"]:
        o["P4.2.A.adoption_records"] = recs(L, en["value"]["id"])
    hb = L.head()
    o["P4.2.B.enable_strict_on_enabled"] = {"res": attempt(lambda: rev(L.enable(strict=True))), "head": [hb.seq, L.head().seq],
                                             "strict_meta": L.meta().get("strict"), "create": attempt(lambda: e.create_node("i60_stillfree"))}
    L.disable(); e.create_node("i60_off2")
    o["P4.2.B.reenable_strict"] = {"res": attempt(lambda: rev(L.enable(strict=True))), "strict_meta": L.meta().get("strict"),
                                    "create": attempt(lambda: e.create_node("i60_blocked2"))}
    L.set_strict(False)
    # S4.3 caller transaction refusals and joined toggles
    c.setAutoCommit(False)
    try:
        e.create_node("i60_txnw")  # caller writes: $TLEVEL > 0
        lvl = attempt(lambda: (lambda cu: (cu.execute("SELECT $TLEVEL"), cu.fetchone()[0])[1])(c.cursor()))
        o["S4.3"] = {"tlevel": lvl, "enable": attempt(lambda: rev(L.enable())), "disable": attempt(lambda: L.disable()),
                     "state_in_txn": L.meta().get("state")}
    finally:
        c.rollback(); c.setAutoCommit(True)
    o["S4.3"]["state_after_rollback"] = L.meta().get("state")
    o["S4.3"]["node_after_rollback"] = node(e, "i60_txnw")
    if L.meta().get("state") != "enabled":
        L.enable()

    # N9 adoption only when needed (after cleaning)
    o["N9.clean"] = vfy(L, adopt=True)
    hb = L.head()
    o["N9.A"] = {"verify": vfy(L, adopt=True), "head": [hb.seq, L.head().seq]}
    e.create_node("i60_n9u")
    hb = L.head()
    v1 = vfy(L, adopt=True); v2 = vfy(L, adopt=True)
    o["N9.B"] = {"first": v1, "second": v2, "head": [hb.seq, L.head().seq], "parent_is_old_head": (v1["adoption"] or {}).get("parent") == hb.revision_id}
    o["final_head"] = rev(L.head())
    c.close()


# ----------------------------------------------------------------------------------------------- lock (I60LA)
def lock():
    o = OBS.setdefault("lock", {})
    ca, ea = open_ns("I60LA"); cb, eb = open_ns("I60LA")
    La, Lb = ea.ledger, eb.ledger
    h = La.head()
    # N1.A: A's transaction holds the head lock; B times out; A rolls back; B retries
    ca.setAutoCommit(False)
    try:
        xa = cs(actor="A"); xa.create_node("i60_lockA"); o["N1.A.a_commit"] = commit(La, xa)
        yb = cs(actor="B"); yb.create_node("i60_lockB")
        t0 = time.time(); o["N1.A.b_commit"] = commit(Lb, yb); o["N1.A.b_elapsed_s"] = round(time.time() - t0, 1)
    finally:
        ca.rollback(); ca.setAutoCommit(True)
    o["N1.A.head_after_rollback"] = [h.seq, rev(La.head())]
    yb2 = cs(actor="B"); yb2.create_node("i60_lockB"); r = commit(Lb, yb2)
    o["N1.A.b_retry"] = r; o["N1.A.parent_is_h"] = r["ok"] and r["value"]["revision"]["parent"] == h.revision_id
    # N1.B: A commits its transaction first
    h = La.head()
    ca.setAutoCommit(False)
    try:
        xa = cs(actor="A"); xa.create_node("i60_lockA2"); ra = commit(La, xa)
        ca.commit()
    finally:
        ca.setAutoCommit(True)
    t0 = time.time(); yb = cs(actor="B"); yb.create_node("i60_lockB2"); rb = commit(Lb, yb)
    o["N1.B"] = {"a": ra, "b": rb, "elapsed_s": round(time.time() - t0, 1), "h": h.seq,
                 "b_parent_is_a": rb["ok"] and ra["ok"] and rb["value"]["revision"]["parent"] == ra["value"]["revision"]["id"]}
    ca.close(); cb.close()


# ----------------------------------------------------------------------------------------------- large (I60LA)
def large():
    o = OBS.setdefault("large", {})
    c, e = open_ns("I60LA"); L = e.ledger
    s0 = cs(); s0.create_node("i60_big")
    commit(L, s0)
    big = cs()
    for i in range(2000):
        big.set_property("i60_big", f"k{i:04d}", ("v%04d" % i) + "x" * 2495)
    o["N10.A.json_chars"] = len(big.canonical_json())
    r = commit(L, big); o["N10.A.res_ok"] = r["ok"]; o["N10.A.res"] = r if not r["ok"] else {"seq": r["value"]["revision"]["seq"], "op_count": r["value"]["revision"]["op_count"]}
    if r["ok"]:
        rr = L.get_revision(r["value"]["revision"]["id"]).records
        o["N10.A.records"] = {"n": len(rr), "lens": sorted({len(x.new or "") for x in rr}), "first": rr[0].attr, "last": rr[-1].attr}
        n = e.get_node("i60_big")
        props = (n or {}).get("properties") or {}
        o["N10.A.node"] = {"n_props": len([k for k in props if k.startswith("k")]), "len_k1999": len(str(props.get("k1999", "")))}
    rel = cs(); rel.create_node("i60_hub")
    for i in range(2000):
        rel.create_node(f"i60_t{i:04d}"); rel.create_relationship("i60_hub", "R", f"i60_t{i:04d}")
    r = commit(L, rel)
    o["N10.B"] = {"ok": r["ok"], "n_stmt": len(r["value"]["stmt_ids"]) if r["ok"] else None, "exc": r.get("exc"),
                  "keys_min_max": [min(r["value"]["stmt_ids"]), max(r["value"]["stmt_ids"])] if r["ok"] else None}
    c.close()


# ----------------------------------------------------------------------------------------------- C/D: never-enabled, small bounds
def nc():
    o = OBS.setdefault("c", {})
    c, e = open_ns("I60LC"); L = e.ledger
    ev = []; L.register_metrics_hook(lambda d: ev.append(d))
    o["N6.A"] = {"meta": L.meta(), "head": attempt(lambda: rev(L.head())), "verify": attempt(lambda: vfy(L)),
                 "status_state": attempt(lambda: e.status().ledger.state), "stats": attempt(lambda: stats(L)),
                 "history": attempt(lambda: [len(L.history().revisions), L.history().next_after_seq]),
                 "set_strict": attempt(lambda: L.set_strict(True)), "disable": attempt(lambda: L.disable())}
    x = cs(); x.create_node("i60_c_x")
    o["P3.2.A"] = {"res": commit(L, x), "events": list(ev), "node": node(e, "i60_c_x"), "meta_state": L.meta().get("state")}
    ev.clear()
    o["enable"] = rev(L.enable(max_ops=2, recon_bound=1))
    o["S3.4.enable_events"] = list(ev)
    o["meta"] = L.meta()
    revs = {}
    for name, f in (("a", lambda z: z.create_node("i60_ca")), ("b", lambda z: z.create_node("i60_cb")), ("del_b", lambda z: z.delete_node("i60_cb"))):
        z = cs(); f(z); r = commit(L, z); revs[name] = r
    o["R2.B.commits"] = revs
    hd = L.head()
    o["R2.B.reconstruct_head"] = attempt(lambda: sorted(L.reconstruct(hd.revision_id).nodes))
    o["R2.B.stream"] = attempt(lambda: sorted(str(getattr(x_, "entity_id", x_)) for x_ in L.reconstruct(hd.revision_id, stream=True)))
    tmpd = tempfile.mkdtemp(prefix="i60-r2b-"); path = os.path.join(tmpd, "h.ndjson")
    o["R2.B.export"] = attempt(lambda: str(L.export_reconstruction(hd.revision_id, path)))
    o["R2.B.export_lines"] = open(path).read().splitlines() if os.path.exists(path) else None
    if revs["a"]["ok"]:
        o["R2.B.reconstruct_a"] = attempt(lambda: sorted(L.reconstruct(revs["a"]["value"]["revision"]["id"]).nodes))
    ev.clear()
    two = cs(); two.create_node("i60_c2a"); two.create_node("i60_c2b"); o["S3.5.two"] = commit(L, two)
    three = cs(); three.create_node("i60_c3a"); three.create_node("i60_c3b"); three.create_node("i60_c3c"); o["S3.5.three"] = commit(L, three)
    o["S3.5.events"] = list(ev); o["S3.5.rej_size"] = stats(L)["rej"].get("rej_size_limit")
    c.close()
    # I60LD: the same history under bound 2
    c, e = open_ns("I60LD"); L = e.ledger
    od = OBS.setdefault("d", {})
    od["enable"] = rev(L.enable(recon_bound=2))
    for f in (lambda z: z.create_node("i60_da"), lambda z: z.create_node("i60_db"), lambda z: z.delete_node("i60_db")):
        z = cs(); f(z); commit(L, z)
    hd = L.head()
    od["R2.B.bound2_head"] = attempt(lambda: sorted(L.reconstruct(hd.revision_id).nodes))
    c.close()


# ----------------------------------------------------------------------------------------------- W2 (I60LB)
def w2():
    o = OBS.setdefault("w2", {})
    c, e = open_ns("I60LB"); L = e.ledger
    o["genesis"] = rev(L.enable())
    o["V1.A.clean"] = [vfy(L), vfy(L), L.head().seq]
    for i, actor in enumerate(("a", "b", "a")):
        z = cs(actor=actor); z.create_node(f"i60r_h{i}"); commit(L, z)

    def page(**kw):
        p = L.history(**kw)
        return [[r.seq for r in p.revisions], p.next_after_seq]
    o["H1.B"] = [page(limit=2), page(limit=2, after_seq=2), page(limit=2, after_seq=4), page(limit=0)]
    z = cs(actor="b"); z.create_node("i60r_h3"); commit(L, z)
    o["H1.A"] = [page(limit=2), page(limit=2, after_seq=2), page(limit=2, after_seq=4), page(limit=0),
                 [r.kind for r in L.history(limit=10).revisions],
                 all(L.history(limit=10).revisions[i].parent_id == L.history(limit=10).revisions[i - 1].revision_id for i in range(1, 5))]
    o["H2.A"] = [page(limit=2, descending=True, after_seq=0), page(limit=2, descending=True, after_seq=4)]
    o["H2.B"] = {"text0": attempt(lambda: page(limit=2, descending=True, after_seq="0")), "actor_a": page(actor="a", limit=2),
                 "actor_A": page(actor="A", limit=2), "actor_empty": page(actor="", limit=2)}

    # D1 continuous attribute
    def com(f, actor="w2"):
        z = cs(actor=actor); f(z); r = commit(L, z)
        return r["value"]["revision"]["id"] if r["ok"] else r
    r1 = com(lambda z: z.create_node("i60r_n", properties={"p": "1"}))
    r2 = com(lambda z: (z.set_property("i60r_n", "p", 2), z.create_node("i60r_m"), z.create_relationship("i60r_n", "K", "i60r_m")))
    r3 = com(lambda z: z.set_property("i60r_n", "p", 3))
    d13 = L.diff(r1, r3); d31 = L.diff(r3, r1)
    o["D1.A"] = {"d13": diffl(d13), "d31": diffl(d31), "d31_eq_inverse": d31 == d13.inverse(), "inv_inv": d13.inverse().inverse() == d13,
                 "d11": len(L.diff(r1, r1))}
    b1 = com(lambda z: z.create_node("i60r_n2", properties={"p": "1"}))
    b2 = com(lambda z: z.set_property("i60r_n2", "p", "2"))
    b3 = com(lambda z: z.set_property("i60r_n2", "p", "1"))
    o["D1.B"] = {"d13": diffl(L.diff(b1, b3)), "d12": diffl(L.diff(b1, b2))}
    # D2 lifecycle
    q1 = com(lambda z: z.create_node("i60r_d", labels=["L"], properties={"q": "x"}))
    q2 = com(lambda z: z.delete_node("i60r_d"))
    o["D2.A"] = {"d12": diffl(L.diff(q1, q2)), "recon_q1_d": attempt(lambda: (lambda s: [sorted(s.nodes["i60r_d"].labels), s.nodes["i60r_d"].props])(L.reconstruct(q1)))}
    t1 = com(lambda z: z.create_node("i60r_anchor"))
    t2 = com(lambda z: z.create_node("i60r_tmp"))
    t3 = com(lambda z: z.delete_node("i60r_tmp"))
    o["D2.A.created_and_deleted"] = diffl(L.diff(t1, t3))
    u1 = com(lambda z: z.create_node("i60r_d2", properties={"q": "1"}))
    u2 = com(lambda z: z.set_property("i60r_d2", "q", "2"))
    u3 = com(lambda z: z.delete_node("i60r_d2"))
    u4 = com(lambda z: z.create_node("i60r_d2"))
    u5 = com(lambda z: z.set_property("i60r_d2", "q", "3"))
    d15 = L.diff(u1, u5)
    o["D2.B"] = {"d15": diffl(d15), "d51_eq_inv": L.diff(u5, u1) == d15.inverse()}

    # R1 named revision vs head; export
    g = L.history(limit=1).revisions[0].revision_id
    s2_ = com(lambda z: z.create_node("i60r_rn", properties={"p": "1"}))
    s3_ = com(lambda z: z.set_property("i60r_rn", "p", "2"))
    s4_ = com(lambda z: (z.create_node("i60r_rm"), z.create_relationship("i60r_rn", "K", "i60r_rm")))
    R2s = L.reconstruct(s2_); RH = L.reconstruct(L.head().revision_id); RG = L.reconstruct(g)
    tmpd = tempfile.mkdtemp(prefix="i60-r1-"); path = os.path.join(tmpd, "r2.ndjson")
    exp = attempt(lambda: str(L.export_reconstruction(s2_, path)))
    lines = [json.loads(x) for x in open(path).read().splitlines()] if os.path.exists(path) else []
    o["R1.A"] = {"r2_rn": R2s.nodes.get("i60r_rn").props if "i60r_rn" in R2s.nodes else None,
                 "r2_rel": R2s.stmt_for_tuple(("i60r_rn", "K", "i60r_rm", None)),
                 "head_rn": RH.nodes["i60r_rn"].props, "head_rel": RH.stmt_for_tuple(("i60r_rn", "K", "i60r_rm", None)) is not None,
                 "genesis_has_rn": "i60r_rn" in RG.nodes, "export": exp,
                 "export_ids": sorted(str(x.get("id") or x.get("node_id") or x.get("source") or json.dumps(x, sort_keys=True))[:60] for x in lines),
                 "export_types": sorted({str(x.get("type")) for x in lines}),
                 "recon_ids": sorted(R2s.nodes), "recon_rels": len(R2s.statements)}
    oldh = L.head().revision_id
    e.create_node("i60r_u")
    o["R1.B"] = {"head_has_u": "i60r_u" in L.reconstruct(L.head().revision_id).nodes}
    v = vfy(L, adopt=True)
    o["R1.B"].update({"adopt": v["adoption"], "new_head_has_u": "i60r_u" in L.reconstruct(L.head().revision_id).nodes,
                      "old_head_has_u": "i60r_u" in L.reconstruct(oldh).nodes})

    # R2.A deleted entities (detach delete)
    w2a = com(lambda z: (z.create_node("i60r_rd"), z.create_node("i60r_rdm"), z.create_relationship("i60r_rd", "K", "i60r_rdm")))
    strict_del = cs(); strict_del.delete_node("i60r_rd"); o["R2.A.strict_mode_delete"] = commit(L, strict_del)
    w3a = com(lambda z: z.delete_node("i60r_rd", mode="detach"))
    o["R2.A"] = {"r2": ["i60r_rd" in L.reconstruct(w2a).nodes, L.reconstruct(w2a).stmt_for_tuple(("i60r_rd", "K", "i60r_rdm", None)) is not None],
                 "r3": ["i60r_rd" in L.reconstruct(w3a).nodes, L.reconstruct(w3a).stmt_for_tuple(("i60r_rd", "K", "i60r_rdm", None)) is not None] if isinstance(w3a, str) else w3a,
                 "records": recs(L, w3a) if isinstance(w3a, str) else None}

    # V1.B unrecorded write, adopt, strict refusal, immutability
    hb = L.head().seq
    e.create_node("i60r_vu")
    vb = vfy(L)
    o["V1.B"] = {"verify": vb, "head": [hb, L.head().seq]}
    va = vfy(L, adopt=True)
    o["V1.B"].update({"adopt": va["adoption"], "after": vfy(L)["result"]})
    L.set_strict(True)
    o["V1.B.strict"] = {"create": attempt(lambda: e.create_node("i60r_vs")), "verify": vfy(L)["result"]}
    L.set_strict(False)
    h1 = L.head(); hist1 = len(L.history(limit=1000).revisions)
    cur = c.cursor()
    o["V1.B.sql_update"] = attempt(lambda: cur.execute("UPDATE Graph_KG.ledger_revisions SET message='tamper' WHERE seq=2"))
    o["V1.B.sql_delete"] = attempt(lambda: cur.execute("DELETE FROM Graph_KG.ledger_revisions WHERE seq=2"))
    cur.close()
    o["V1.B.after_tamper"] = [h1.seq == L.head().seq, hist1 == len(L.history(limit=1000).revisions),
                              L.history(limit=3).revisions[1].message]

    # V2 scope
    com(lambda z: (z.create_node("i60r_va"), z.create_node("i60r_vb")))
    e.create_edge("i60r_va", "K", "i60r_vb")
    o["V2.A"] = vfy(L)
    vfy(L, adopt=True)
    o["V2.B.temporal"] = attempt(lambda: e.create_edge_temporal("i60r_va", "K2", "i60r_vb", timestamp=1700000000))
    o["V2.B.verify_temporal"] = vfy(L)
    com(lambda z: (z.create_node("i60r_vn"), z.set_property("i60r_vn", "p", "30")))
    o["V2.B.cypher_set"] = attempt(lambda: e.execute_cypher("MATCH (n {id:'i60r_vn'}) SET n.p = 30 RETURN n.p").rows)
    o["V2.B.verify_after_set"] = vfy(L)
    o["V2.B.temporal_new_ends"] = attempt(lambda: e.create_edge_temporal("i60r_tn1", "K3", "i60r_tn2", timestamp=1700000000))
    o["V2.B.verify_new_ends"] = vfy(L)
    vfy(L, adopt=True)
    # C1 temporal marked row
    o["C1.A"] = {"verify": vfy(L)["result"], "recon_has": L.reconstruct(L.head().revision_id).stmt_for_tuple(("i60r_va", "K2", "i60r_vb", None)) is not None,
                 "cypher": attempt(lambda: e.execute_cypher("MATCH (a {id:'i60r_va'})-[r:K2]->(b) RETURN b.id").rows)}
    o["C1.B.create_edge"] = attempt(lambda: e.create_edge("i60r_va", "K2", "i60r_vb"))
    v = vfy(L)
    o["C1.B"] = {"verify": v}
    va = vfy(L, adopt=True)
    o["C1.B"].update({"adopt_records": recs(L, va["adoption"]["id"]) if va["adoption"] else None, "after": vfy(L)["result"],
                      "recon_has": L.reconstruct(L.head().revision_id).stmt_for_tuple(("i60r_va", "K2", "i60r_vb", None)) is not None})
    # C2 adoption items across kinds
    com(lambda z: (z.create_node("i60r_cn", properties={"p": "2"}), z.create_node("i60r_cz")))
    oldh = L.head().revision_id
    e.create_node("i60r_x", labels=["X"], properties={"k": "v"})
    o["C2.A.set"] = attempt(lambda: e.execute_cypher("MATCH (n {id:'i60r_cn'}) SET n.p = '9' RETURN n.p").rows)
    o["C2.A.del"] = attempt(lambda: e.delete_node("i60r_cz"))
    o["C2.A.verify"] = vfy(L)
    va = vfy(L, adopt=True)
    o["C2.A.adopt"] = {"rev": va["adoption"], "records": recs(L, va["adoption"]["id"]) if va["adoption"] else None,
                       "diff": diffl(L.diff(oldh, va["adoption"]["id"])) if va["adoption"] else None, "after": vfy(L)["result"]}
    t = cs(); t.upsert_node("i60r_a2"); t.upsert_node("i60r_b2"); t.create_temporal_edge("i60r_a2", "T", "i60r_b2", ts=1700000000)
    rt_ = commit(L, t)
    o["C2.B.with_upserts"] = {"res": rt_, "verify": vfy(L), "diff_kinds": sorted({x[0] for x in diffl(L.diff(oldh, L.head().revision_id))})}
    vfy(L, adopt=True)
    t2 = cs(); t2.create_temporal_edge("i60r_a3", "T", "i60r_b3", ts=1700000000)
    o["C2.B.without"] = {"res": commit(L, t2), "verify": vfy(L)}
    o["final_head"] = rev(L.head())
    c.close()


SECTIONS = {"w1": w1, "lock": lock, "large": large, "c": nc, "w2": w2}

if __name__ == "__main__":
    which = sys.argv[1:] or list(SECTIONS)
    started = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    meta = {"fixture": rt.FIXTURE, "product": rt.PRODUCT, "started": started, "sections": which}
    c0 = rt.connect("USER"); meta["identity"] = rt.identity(c0); c0.close()
    for s in which:
        try:
            SECTIONS[s]()
        except Exception as ex:
            OBS.setdefault(s, {})["_probe_error"] = traceback.format_exc()
    meta["finished"] = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = HERE / f"observed-{started}-{'-'.join(which)}.json"
    out.write_text(json.dumps({"meta": meta, "obs": OBS}, indent=1, default=str) + "\n")
    print(out)
