#!/usr/bin/env python3
"""Module 11 (ledger core): live probes of every stated refusal (LED kind X) in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1800 \
        python experiment/playbook-completion/refusals/live_11.py [case ...]

Each case triggers the refused condition through the product's real entry point (engine.ledger / Changeset, the
Graph.KG.Ledger class methods the client calls over the Native API, SQL and the object API on the revision table),
inside a journal window (rxlib): the case holds when the product refuses as the statement says and the journal shows
no net change outside the stores the statement names (the stats row of a counted rejection; IRIS extent ID counters,
which a rollback does not undo by design, where a refused commit had already inserted a row). Setup (enable, seed)
runs outside the windows. Results: $RUN_DIR/refusals/11/results.json (results-partial.json for a subset).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, returns, either, run_cases, engine, tlevel, open_caller_txn, rollback_all  # noqa: E402

from iris_vector_graph.ledger import Changeset, OpRef  # noqa: E402

STATS = r"sql:Graph_KG\.ledger_stats"          # the stats row a counted rejection bumps (Ledger.cls:369-370)
ID_COUNTER = r"^\^[A-Za-z0-9.]+$"              # an extent's ID counter (unsubscripted root), $Increment: not rolled back
NONTXN = True                                   # rx-live-11-r2: report non-transactional increments separately (rxlib)


def cs(msg="rx11", **kw):
    return Changeset(actor="audit:refusals", actor_type="ingest", message=msg, **kw)


def rel(*args, **kw):
    """A changeset holding one create_relationship (the builder returns an OpRef for it, not the changeset)."""
    c = cs("rel")
    c.create_relationship(*args, **kw)
    return c


def hold_head_native(L, c2):
    """Hold ^IVG.Ledger("head") from another process with the Native API lock, verified from the lane's process
    (a lock attempt with timeout 0 must fail). Returns the name form that worked."""
    for name in ("^IVG.Ledger", "IVG.Ledger"):
        c2.o.lock("", 5, name, "head")
        try:
            L.c.o.lock("", 0, name, "head")
        except Exception:  # noqa: BLE001  (<TIMEOUT>: held by c2, as wanted)
            return name
        L.c.o.releaseAllLocks()
        c2.o.releaseAllLocks()
    raise RuntimeError("could not hold ^IVG.Ledger(\"head\") from a second process")


def commit(L, c):
    r = L.eng.ledger.commit(c)
    L.c.conn.commit()
    return r


def seed_nodes(L, *ids):
    c = cs("seed")
    for i in ids:
        c.create_node(i, labels=["RX11"], properties={"name": i})
    return commit(L, c)


def stats(L):
    s = L.eng.ledger.stats()
    return {"state": s.state, "head_seq": s.head_seq, "commits_ok": s.commits_ok, "rejections": s.rejections}


def server_commit(L, payload: str, meta: dict, conn=None):
    c = conn or L.c
    return json.loads(str(c.call("Graph.KG.Ledger", "Commit", payload, json.dumps(meta))))


def meta_for(changeset: Changeset, kind="changeset"):
    return {"fingerprint": changeset.fingerprint(), "expected_head": changeset.expected_head,
            "idempotency_key": changeset.idempotency_key, "kind": kind, "schema": "Graph_KG", "staged": False}


def rx_counter(L, name):
    def after():
        st = stats(L)
        return {"stats": st, "counter": name, "value": st["rejections"].get(name)}
    return after


def _count(L, table, where, *params):
    return int(L.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{table} WHERE {where}", *params)[0][0])


# ---------------------------------------------------------------------------------------------------- lifecycle
def c_b1_9(L):
    """LED-B1.9: Enable (server) refused with an open transaction on its own process; skipped when enabled."""
    L.reset()
    lvl = open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx11:txnopen')")
    L.note("LED-B1.9", "setup: caller transaction open", tlevel=lvl)
    L.refusal("LED-B1.9", "server Enable with $TLEVEL>0 -> transaction_open",
              lambda: json.loads(str(L.c.call("Graph.KG.Ledger", "Enable", 0, 50000, 250000, "Graph_KG"))),
              returns(lambda r: r.get("ok") is False and r.get("error") == "transaction_open",
                      "{'ok': false, 'error': 'transaction_open'}"),
              keep_txn=True, after=lambda: {"tlevel": tlevel(L.c.conn)},
              entry="Graph.KG.Ledger.Enable (Native API, same process as the open transaction)")
    rollback_all(L.c.conn)
    L.note("LED-B1.9", "after rollback: ledger state", state=L.eng.ledger.meta().get("state"))
    # skipped when on: enabled ledger + open transaction answers ok (fast path, Ledger.cls:252-258)
    L.reset(ledger=True)
    open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx11:txnopen2')")
    r = json.loads(str(L.c.call("Graph.KG.Ledger", "Enable", 0, 50000, 250000, "Graph_KG")))
    L.note("LED-B1.9", "enabled ledger: Enable with an open transaction answers ok (check skipped)",
           ok=r.get("ok"), adoption_needed=r.get("adoption_needed"), tlevel=tlevel(L.c.conn))
    rollback_all(L.c.conn)


def c_b1_10(L):
    """LED-B1.10: the Python enable refuses a caller transaction holding a write and sends nothing."""
    L.reset()
    L.note("LED-B1.10", "setup: caller transaction open",
           tlevel=open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx11:txnopen3')"))
    L.refusal("LED-B1.10", "engine.ledger.enable() with a caller write open -> LedgerTransactionOpenError",
              lambda: L.eng.ledger.enable(), raises("LedgerTransactionOpenError"), keep_txn=True,
              after=lambda: {"tlevel": tlevel(L.c.conn), "caller_row_still_there":
                             _count(L, "nodes", "node_id = ?", "rx11:txnopen3")},
              entry="engine.ledger.enable")
    rollback_all(L.c.conn)
    L.note("LED-B1.10", "after rollback: ledger state", state=L.eng.ledger.meta().get("state"))


def c_b1_11(L):
    """LED-B1.11: Enable waits up to 30 s for the head lock, then gives up and changes nothing."""
    L.reset()
    c2 = L.conn()
    try:
        name = hold_head_native(L, c2)
        L.note("LED-B1.11", "setup: a second process holds ^IVG.Ledger(\"head\")", holder_pid=c2.pid, lock_name=name)
        L.refusal("LED-B1.11", "enable while another process holds the head lock -> lock_timeout after ~30 s",
                  lambda: L.eng.ledger.enable(),
                  raises("LedgerLockTimeoutError"),
                  after=lambda: {"state": L.eng.ledger.meta().get("state")},
                  entry="engine.ledger.enable -> Graph.KG.Ledger.Enable")
    finally:
        c2.o.releaseAllLocks()
        L.drop(c2)
    L.reset(ledger=True)
    L.eng.ledger.disable()
    L.c.conn.commit()
    L.fresh_engine()
    c2 = L.conn()
    try:
        name = hold_head_native(L, c2)
        L.refusal("LED-B1.11", "re-enable a disabled ledger while another process holds the head lock -> lock_timeout",
                  lambda: L.eng.ledger.enable(), raises("LedgerLockTimeoutError"),
                  after=lambda: {"state": L.eng.ledger.meta().get("state")},
                  entry="engine.ledger.enable -> Graph.KG.Ledger.Enable (disabled path)")
    finally:
        c2.o.releaseAllLocks()
        L.drop(c2)


def c_b3_4(L):
    """LED-B3.4: enabled with no revision -> Head answers inconsistent. Not reachable through an entry point
    (Enable writes head and the genesis revision in one transaction): observe Head on the reachable states."""
    L.reset()
    L.refusal("LED-B3.4", "Head on a never-enabled ledger -> not_enabled (neighbouring branch, reachable)",
              lambda: L.eng.ledger.head(), raises("LedgerNotEnabledError"), entry="engine.ledger.head")
    L.reset(ledger=True)
    L.note("LED-B3.4", "enabled ledger: head after genesis", head_seq=L.eng.ledger.head().seq)


# ---------------------------------------------------------------------------------------------------- commit guards
def c_b4_4(L):
    """LED-B4.4: a commit gives up after 30 s without the head lock; changes nothing; counted rej_lock_timeout."""
    L.reset(ledger=True)
    seed_nodes(L, "rx11:a")
    before = stats(L)
    c2 = L.conn()
    try:
        # the product's own holder: a commit inside an open caller transaction keeps the head lock until that
        # transaction ends (Ledger.cls:389-396)
        e2 = engine(c2)
        open_caller_txn(c2.conn)
        held = e2.ledger.commit(cs("holder").create_node("rx11:holder"))
        L.note("LED-B4.4", "setup: process 2 committed inside its open transaction (head lock held)",
               holder_pid=c2.pid, holder_seq=held.revision.seq, holder_tlevel=tlevel(c2.conn))
        c = cs("locked").set_property("rx11:a", "k", "v")
        L.refusal("LED-B4.4", "commit while another process holds the head lock -> lock_timeout, rej_lock_timeout",
                  lambda: L.eng.ledger.commit(c), raises("LedgerLockTimeoutError"), allowed=[STATS],
                  after=lambda: {"before": before["rejections"].get("rej_lock_timeout"),
                                 **rx_counter(L, "rej_lock_timeout")(),
                                 "prop_rows": _count(L, "rdf_props", "s = ? AND \"key\" = 'k'", "rx11:a")},
                  entry="engine.ledger.commit")
    finally:
        c2.o.releaseAllLocks()
        L.drop(c2)


def c_b4_5(L):
    """LED-B4.5: a commit is refused when the ledger was never enabled (not counted)."""
    L.reset()
    c = cs("never").create_node("rx11:never")
    L.refusal("LED-B4.5", "commit on a never-enabled ledger -> not_enabled",
              lambda: L.eng.ledger.commit(c), raises("LedgerNotEnabledError"),
              after=lambda: {"node_rows": _count(L, "nodes", "node_id = ?", "rx11:never")},
              entry="engine.ledger.commit")


def c_b4_6(L):
    """LED-B4.6: a commit is refused while the ledger is disabled; counted rej_disabled."""
    L.reset(ledger=True)
    L.eng.ledger.disable()
    L.c.conn.commit()
    L.fresh_engine()
    c = cs("disabled").create_node("rx11:dis")
    L.refusal("LED-B4.6", "commit on a disabled ledger -> disabled, rej_disabled",
              lambda: L.eng.ledger.commit(c), raises("LedgerDisabledError"), allowed=[STATS],
              after=lambda: {**rx_counter(L, "rej_disabled")(),
                             "node_rows": _count(L, "nodes", "node_id = ?", "rx11:dis")},
              entry="engine.ledger.commit")


def c_b4_7_1(L):
    """LED-B4.7.1: a retry key bound to a different fingerprint is refused (idempotency_conflict, with the head)."""
    L.reset(ledger=True)
    r1 = commit(L, cs("k1", idempotency_key="rx11-key").create_node("rx11:k1"))
    head = L.eng.ledger.head().revision_id
    c = cs("k1", idempotency_key="rx11-key").create_node("rx11:k2")
    L.refusal("LED-B4.7.1", "same idempotency key, different changeset -> idempotency_conflict",
              lambda: L.eng.ledger.commit(c), raises("IdempotencyConflictError"), allowed=[STATS],
              after=lambda: {**rx_counter(L, "rej_idem_conflict")(),
                             "node_rows": _count(L, "nodes", "node_id = ?", "rx11:k2")},
              entry="engine.ledger.commit")
    # the wire answer carries the head (server entry the client calls)
    c3 = cs("k1", idempotency_key="rx11-key").create_node("rx11:k3")
    L.refusal("LED-B4.7.1", "server Commit: conflict answer names the head",
              lambda: server_commit(L, c3.canonical_json(), meta_for(c3)),
              returns(lambda r: r.get("ok") is False and r.get("error") == "idempotency_conflict"
                      and r.get("head") == head, f"error idempotency_conflict, head == {head}"),
              allowed=[STATS], entry="Graph.KG.Ledger.Commit")
    # not a conflict: same payload, another message/correlation id (fingerprint excludes them)
    c4 = cs("another message", idempotency_key="rx11-key", correlation_id="rx11-corr").create_node("rx11:k1")
    try:
        r4 = L.eng.ledger.commit(c4)
        L.c.conn.commit()
        L.note("LED-B4.7.1", "same key and ops, new message/correlation id: replay, not a conflict",
               replayed=r4.replayed, seq=r4.revision.seq, first_seq=r1.revision.seq)
    except Exception as e:  # noqa: BLE001
        L.note("LED-B4.7.1", "same key and ops, new message/correlation id", error=f"{type(e).__name__}: {e}")


def c_b4_8(L):
    """LED-B4.8: a stale expected head is refused; the answer names the head."""
    L.reset(ledger=True)
    g = L.eng.ledger.head().revision_id
    commit(L, cs("advance").create_node("rx11:s1"))
    h = L.eng.ledger.head().revision_id
    c = cs("stale", expected_head=g).create_node("rx11:s2")
    L.refusal("LED-B4.8", "expected_head = an older revision -> stale_head naming the head",
              lambda: L.eng.ledger.commit(c), raises("StaleHeadError", attr={"current_head": h}),
              allowed=[STATS], after=lambda: {**rx_counter(L, "rej_stale_head")(),
                                             "node_rows": _count(L, "nodes", "node_id = ?", "rx11:s2")},
              entry="engine.ledger.commit")
    # two processes, same expected head: exactly one wins
    c2 = L.conn()
    try:
        e2 = engine(c2)
        e2.ledger.commit(cs("w1", expected_head=h).create_node("rx11:w1"))
        c2.conn.commit()
        cw = cs("w2", expected_head=h).create_node("rx11:w2")
        L.refusal("LED-B4.8", "second process commits on the same expected head -> stale_head",
                  lambda: L.eng.ledger.commit(cw), raises("StaleHeadError"), allowed=[STATS],
                  entry="engine.ledger.commit (two processes)")
    finally:
        L.drop(c2)


def c_b4_8_1(L):
    """LED-B4.8.1: an expected head naming no revision of this ledger -> unknown_head; a rolled-back one too."""
    L.reset(ledger=True)
    c = cs("unknown", expected_head="ffffffffffffffffffffffffffffffff").create_node("rx11:u1")
    L.refusal("LED-B4.8.1", "expected_head names no revision -> unknown_head",
              lambda: L.eng.ledger.commit(c), raises("UnknownRevisionError"), allowed=[STATS],
              after=lambda: {**rx_counter(L, "rej_unknown_head")(),
                             "node_rows": _count(L, "nodes", "node_id = ?", "rx11:u1")},
              entry="engine.ledger.commit")
    # a revision a caller rolled back is unknown
    open_caller_txn(L.c.conn)
    rb = L.eng.ledger.commit(cs("to roll back").create_node("rx11:rb"))
    rid = rb.revision.revision_id
    rollback_all(L.c.conn)
    L.note("LED-B4.8.1", "setup: a revision committed inside a caller transaction, then rolled back",
           revision_id=rid, node_rows=_count(L, "nodes", "node_id = ?", "rx11:rb"))
    c2 = cs("after rollback", expected_head=rid).create_node("rx11:u2")
    L.refusal("LED-B4.8.1", "expected_head = a rolled-back revision -> unknown_head",
              lambda: L.eng.ledger.commit(c2), raises("UnknownRevisionError"), allowed=[STATS],
              entry="engine.ledger.commit")


def c_b4_9(L):
    """LED-B4.9: a changeset with no changes is refused by the server (code empty, not counted)."""
    L.reset(ledger=True)
    before = stats(L)
    empty = cs("empty")
    L.refusal("LED-B4.9", "server Commit with ops [] -> empty (not counted)",
              lambda: server_commit(L, json.dumps({"actor": "audit:refusals", "actor_type": "ingest", "ops": []}),
                                    {"fingerprint": "x", "kind": "changeset", "schema": "Graph_KG"}),
              returns(lambda r: r.get("ok") is False and r.get("error") == "empty", "error empty"),
              after=lambda: {"before": before["rejections"], "after": stats(L)["rejections"]},
              entry="Graph.KG.Ledger.Commit")
    L.refusal("LED-B4.9", "engine.ledger.commit(empty) -> EmptyChangesetError",
              lambda: L.eng.ledger.commit(empty), raises("EmptyChangesetError"), entry="engine.ledger.commit")


def c_b4_9_1(L):
    """LED-B4.9.1: more changes than the size limit -> too_large before any change; counted rej_size_limit."""
    L.reset()
    L.eng.ledger.enable(max_ops=3)
    L.c.conn.commit()
    L.fresh_engine()
    c = cs("big")
    for i in range(4):
        c.create_node(f"rx11:big{i}")
    L.refusal("LED-B4.9.1", "4 ops with max_ops=3 -> too_large with limit, rej_size_limit",
              lambda: L.eng.ledger.commit(c), raises("ChangesetTooLargeError", attr={"limit": lambda v: v in (3, None)}),
              allowed=[STATS], after=lambda: {**rx_counter(L, "rej_size_limit")(),
                                              "node_rows": _count(L, "nodes", "node_id %STARTSWITH ?", "rx11:big")},
              entry="engine.ledger.commit")


def c_b4_9_2(L):
    """LED-B4.9.2: a commit takes only kinds changeset and adoption (F-1107: any kind is stored)."""
    L.reset(ledger=True)
    c = cs("bogus kind").create_node("rx11:kind")
    L.refusal("LED-B4.9.2", "engine.ledger.commit(kind='bogus') -> refused (stated)",
              lambda: L.eng.ledger.commit(c, kind="bogus"), raises("LedgerError"), allowed=[STATS],
              after=lambda: {"head_kind": L.eng.ledger.head().kind,
                             "node_rows": _count(L, "nodes", "node_id = ?", "rx11:kind")},
              entry="engine.ledger.commit(kind=...)")
    L.c.conn.commit()
    e = cs("bogus kind, no ops")
    L.refusal("LED-B4.9.2", "server Commit kind='bogus' with ops [] -> refused (stated)",
              lambda: server_commit(L, json.dumps({"actor": "audit:refusals", "actor_type": "ingest", "ops": []}),
                                    {"fingerprint": "y", "kind": "bogus", "schema": "Graph_KG"}),
              returns(lambda r: r.get("ok") is False, "ok false"), allowed=[STATS],
              after=lambda: {"head": L.eng.ledger.head().__dict__},
              entry="Graph.KG.Ledger.Commit")
    L.c.conn.commit()


def c_b4_11_8(L):
    """LED-B4.11.8: a revision row that cannot be saved stops the commit (message over 4,000 letters)."""
    L.reset(ledger=True)
    head = L.eng.ledger.head().seq
    c = Changeset(actor="audit:refusals", actor_type="ingest", message="m" * 4001).create_node("rx11:longmsg")
    L.refusal("LED-B4.11.8", "message of 4,001 letters -> inconsistent, nothing saved",
              lambda: L.eng.ledger.commit(c), raises("LedgerInconsistencyError"), allowed=[ID_COUNTER],
              after=lambda: {"head_before": head, "head_after": L.eng.ledger.head().seq,
                             "node_rows": _count(L, "nodes", "node_id = ?", "rx11:longmsg")},
              entry="engine.ledger.commit")


def c_b4_13(L):
    """LED-B4.13: a fault in a commit undoes its own transaction level; the answer is inconsistent."""
    L.reset(ledger=True)
    L.refusal("LED-B4.13", "server Commit with a malformed meta JSON (fault) -> inconsistent, $TLEVEL 0",
              lambda: server_commit_raw(L, json.dumps({"ops": [{"op": "create_node", "id": "rx11:f"}]}), "{not json"),
              returns(lambda r: r.get("ok") is False and r.get("error") == "inconsistent", "error inconsistent"),
              after=lambda: {"tlevel": tlevel(L.c.conn)}, entry="Graph.KG.Ledger.Commit")
    # inside a caller transaction: only the commit's own level is undone; the caller's level and write remain
    lvl = open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx11:caller')")
    L.refusal("LED-B4.13", "fault inside a caller transaction -> inconsistent, caller's level kept",
              lambda: server_commit_raw(L, json.dumps({"ops": [{"op": "create_node", "id": "rx11:f2"}]}), "{not json"),
              returns(lambda r: r.get("ok") is False and r.get("error") == "inconsistent" and tlevel(L.c.conn) == lvl,
                      "error inconsistent, $TLEVEL back to the caller's level"),
              keep_txn=True, caller_txn_open=True,
              after=lambda: {"tlevel_before": lvl, "tlevel_after": tlevel(L.c.conn),
                             "caller_row_visible": _count(L, "nodes", "node_id = ?", "rx11:caller")},
              entry="Graph.KG.Ledger.Commit (same process as the caller)")
    rollback_all(L.c.conn)


def server_commit_raw(L, payload, meta_text):
    return json.loads(str(L.c.call("Graph.KG.Ledger", "Commit", payload, meta_text)))


# ---------------------------------------------------------------------------------------------------- operations
def failed_op(match=None):
    return raises("ChangesetOperationError", match=match)


def c_b5_6(L):
    """LED-B5.6: a reserved property name is refused; the commit saves nothing (builder and server)."""
    L.reset(ledger=True)
    seed_nodes(L, "rx11:r")
    L.refusal("LED-B5.6", "builder: create_node props {'id': ...} -> reserved_property at once",
              lambda: cs().create_node("rx11:r2", properties={"id": "x"}), failed_op("reserved_property"),
              entry="Changeset.create_node")
    L.refusal("LED-B5.6", "builder: set_property '__graph' -> reserved_property at once",
              lambda: cs().set_property("rx11:r", "__graph", "g"), failed_op("reserved_property"),
              entry="Changeset.set_property")
    payload = json.dumps({"actor": "audit:refusals", "actor_type": "ingest",
                          "ops": [{"op": "create_node", "id": "rx11:r3"},
                                  {"op": "set_prop", "id": "rx11:r", "key": "__graph", "value": "g"}]})
    L.refusal("LED-B5.6", "server: op 1 sets '__graph' after op 0 created a node -> failed_op, nothing saved",
              lambda: server_commit(L, payload, {"fingerprint": "r", "kind": "changeset", "schema": "Graph_KG"}),
              returns(lambda r: r.get("ok") is False and r.get("error") == "failed_op"
                      and "reserved_property" in str(r.get("reason")), "failed_op reserved_property"),
              allowed=[STATS, ID_COUNTER],
              after=lambda: {"node_rows": _count(L, "nodes", "node_id = ?", "rx11:r3")},
              entry="Graph.KG.Ledger.Commit")
    payload2 = json.dumps({"actor": "audit:refusals", "actor_type": "ingest",
                           "ops": [{"op": "create_node", "id": "rx11:r4", "props": {"id": "z"}}]})
    L.refusal("LED-B5.6", "server: create_node props {'id': ...} -> failed_op reserved_property",
              lambda: server_commit(L, payload2, {"fingerprint": "r2", "kind": "changeset", "schema": "Graph_KG"}),
              returns(lambda r: r.get("ok") is False and "reserved_property" in str(r.get("reason")),
                      "failed_op reserved_property"),
              allowed=[STATS, ID_COUNTER], entry="Graph.KG.Ledger.Commit")


def c_b5_8(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:l")
    L.refusal("LED-B5.8", "remove_label of a label the node lacks -> label_not_present",
              lambda: L.eng.ledger.commit(cs().remove_label("rx11:l", "Nope")), failed_op("label_not_present"),
              allowed=[STATS], entry="engine.ledger.commit")


def c_b5_10(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:p")
    L.refusal("LED-B5.10", "remove_property the node lacks -> property_not_present",
              lambda: L.eng.ledger.commit(cs().remove_property("rx11:p", "nope")), failed_op("property_not_present"),
              allowed=[STATS], entry="engine.ledger.commit")


def c_b5_11(L):
    L.reset(ledger=True)
    for name, build in [("set_property", lambda: cs().set_property("rx11:ghost", "k", "v")),
                        ("add_label", lambda: cs().add_label("rx11:ghost", "L")),
                        ("delete_node", lambda: cs().delete_node("rx11:ghost"))]:
        c = build()
        L.refusal("LED-B5.11", f"{name} on a node that is not there -> NodeNotFoundError",
                  lambda c=c: L.eng.ledger.commit(c), raises("NodeNotFoundError", attr={"missing_node": "rx11:ghost"}),
                  allowed=[STATS], entry="engine.ledger.commit")


def c_b5_12(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:d1", "rx11:d2")
    commit(L, rel("rx11:d1", "R", "rx11:d2"))
    c = cs().delete_node("rx11:d1", mode="detach").set_property("rx11:d1", "k", "v")
    L.refusal("LED-B5.12", "set_property on a node deleted earlier in the changeset -> refused, nothing saved",
              lambda: L.eng.ledger.commit(c), failed_op("deleted earlier in this changeset"),
              allowed=[STATS, ID_COUNTER], allow_nontxn_increments=NONTXN,
              after=lambda: {"node_rows": _count(L, "nodes", "node_id = ?", "rx11:d1"),
                             "edge_rows": _count(L, "rdf_edges", "s = ?", "rx11:d1")},
              entry="engine.ledger.commit")
    # the node delete above was refused: the edge is live; delete it, then qualify it, in one changeset
    c2 = cs().delete_relationship(("rx11:d1", "R", "rx11:d2")).set_qualifier(("rx11:d1", "R", "rx11:d2"), "w", "1")
    # by tuple: the edge row is already gone, so the tuple lookup answers "relationship not found" (LedgerApply.cls:
    # 190-191) before the deletedStmt test (197): refused, with that reason
    L.refusal("LED-B5.12", "set_qualifier by tuple on an edge deleted earlier in the changeset -> refused (op 1)",
              lambda: L.eng.ledger.commit(c2), raises("ChangesetOperationError", attr={"op_index": 1}),
              allowed=[STATS, ID_COUNTER], allow_nontxn_increments=NONTXN,
              after=lambda: {"edge_rows": _count(L, "rdf_edges", "s = ?", "rx11:d1")},
              entry="engine.ledger.commit")
    sid = L.eng._iris_obj().classMethodValue("Graph.KG.Ledger", "StmtForTuple", "rx11:d1", "R", "rx11:d2", "")
    c3 = cs().delete_relationship(None, stmt_id=str(sid)).set_qualifier(None, "w", "1", stmt_id=str(sid))
    L.refusal("LED-B5.12", "set_qualifier by statement id on an edge deleted earlier in the changeset -> 'deleted earlier'",
              lambda: L.eng.ledger.commit(c3), failed_op("deleted earlier in this changeset"),
              allowed=[STATS, ID_COUNTER], allow_nontxn_increments=NONTXN,
              after=lambda: {"edge_rows": _count(L, "rdf_edges", "s = ?", "rx11:d1")},
              entry="engine.ledger.commit")


def c_b5_13(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:h1", "rx11:h2")
    commit(L, rel("rx11:h1", "R", "rx11:h2"))
    L.refusal("LED-B5.13", "plain (strict) delete_node with a default-graph edge -> node_has_relationships",
              lambda: L.eng.ledger.commit(cs().delete_node("rx11:h1")), failed_op("node_has_relationships"),
              allowed=[STATS], entry="engine.ledger.commit")
    raw = cs().delete_node("rx11:h2")
    L.note("LED-B5.13", "builder default mode", mode=raw.ops[0].get("mode"))


def c_b5_18(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:e1", "rx11:e2")
    commit(L, rel("rx11:e1", "R", "rx11:e2"))
    L.refusal("LED-B5.18", "create_relationship that already exists -> relationship_exists",
              lambda: L.eng.ledger.commit(rel("rx11:e1", "R", "rx11:e2")),
              failed_op("relationship_exists"), allowed=[STATS], entry="engine.ledger.commit")
    L.refusal("LED-B5.18", "create_relationship to a missing end node -> node_not_found",
              lambda: L.eng.ledger.commit(rel("rx11:e1", "R", "rx11:missing")),
              raises("NodeNotFoundError"), allowed=[STATS], entry="engine.ledger.commit")


def c_b5_21(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:q1", "rx11:q2")
    L.refusal("LED-B5.21", "create_relationship with weight 'heavy' -> weight must be numeric",
              lambda: L.eng.ledger.commit(rel("rx11:q1", "R", "rx11:q2", qualifiers={"weight": "heavy"})),
              failed_op("must be numeric"), allowed=[STATS], entry="engine.ledger.commit")
    commit(L, rel("rx11:q1", "R", "rx11:q2"))
    L.refusal("LED-B5.21", "set_qualifier weight 'x' -> weight must be numeric",
              lambda: L.eng.ledger.commit(cs().set_qualifier(("rx11:q1", "R", "rx11:q2"), "weight", "x")),
              failed_op("must be numeric"), allowed=[STATS], entry="engine.ledger.commit")
    L.refusal("LED-B5.21", "replace_qualifiers weight 'x' -> weight must be numeric",
              lambda: L.eng.ledger.commit(cs().replace_qualifiers(("rx11:q1", "R", "rx11:q2"), qualifiers={"weight": "x"})),
              failed_op("must be numeric"), allowed=[STATS], entry="engine.ledger.commit")


def c_b5_26(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:m1", "rx11:m2")
    commit(L, rel("rx11:m1", "R", "rx11:m2", qualifiers={"a": "1"}))
    L.refusal("LED-B5.26", "remove_qualifier of a key not there -> qualifier_not_present",
              lambda: L.eng.ledger.commit(cs().remove_qualifier(("rx11:m1", "R", "rx11:m2"), key="nope")),
              failed_op("qualifier_not_present"), allowed=[STATS], entry="engine.ledger.commit")


def c_b5_27(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:x1", "rx11:x2")
    L.refusal("LED-B5.27", "set_qualifier on a tuple with no edge -> relationship not found",
              lambda: L.eng.ledger.commit(cs().set_qualifier(("rx11:x1", "NOPE", "rx11:x2"), "a", "1")),
              failed_op("relationship not found"), allowed=[STATS], entry="engine.ledger.commit")
    L.refusal("LED-B5.27", "set_qualifier on an unknown statement id -> statement unknown",
              lambda: L.eng.ledger.commit(cs().set_qualifier(None, "a", "1", stmt_id="987654")),
              failed_op("is unknown"), allowed=[STATS], entry="engine.ledger.commit")
    L.refusal("LED-B5.27", "delete_relationship on a tuple with no edge -> relationship not found",
              lambda: L.eng.ledger.commit(cs().delete_relationship(("rx11:x1", "NOPE", "rx11:x2"))),
              failed_op("not found"), allowed=[STATS], entry="engine.ledger.commit")


def c_b6_7(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:c1", "rx11:c2")
    r = commit(L, rel("rx11:c1", "R", "rx11:c2"))
    sid = list(r.stmt_ids.values())[0]
    d = commit(L, cs().delete_relationship(None, stmt_id=sid))
    L.note("LED-B6.7", "setup: statement closed", stmt_id=sid, closed_in=d.revision.seq)
    L.refusal("LED-B6.7", "set_qualifier on a closed statement id -> 'statement N was deleted in revision M'",
              lambda: L.eng.ledger.commit(cs().set_qualifier(None, "a", "1", stmt_id=sid)),
              failed_op(rf"statement {sid} was deleted in revision {d.revision.seq}"), allowed=[STATS],
              entry="engine.ledger.commit")


# ---------------------------------------------------------------------------------------------------- revision table
def _rev_class(L):
    rows = L.c.sql("SELECT ID FROM %Dictionary.CompiledClass WHERE SqlSchemaName = 'Graph_KG' "
                   "AND SqlTableName = 'ledger_revisions'")
    return str(rows[0][0])


def c_b7(L):
    L.reset(ledger=True)
    commit(L, cs("rev").create_node("rx11:rev"))
    rid = L.c.sql("SELECT ID FROM Graph_KG.ledger_revisions WHERE seq = 2")[0][0]
    L.refusal("LED-B7.1", "SQL UPDATE of a revision row -> refused",
              lambda: L.c.sql("UPDATE Graph_KG.ledger_revisions SET message = 'tampered' WHERE seq = 2"),
              raises("Exception", match="immutable|trigger|SQLCODE|-1"),
              after=lambda: {"message": L.c.sql("SELECT message FROM Graph_KG.ledger_revisions WHERE seq = 2")[0][0]},
              entry="SQL UPDATE Graph_KG.ledger_revisions")
    L.c.conn.commit()
    L.refusal("LED-B7.2", "SQL DELETE of a revision row -> refused",
              lambda: L.c.sql("DELETE FROM Graph_KG.ledger_revisions WHERE seq = 2"),
              raises("Exception", match="immutable|trigger|SQLCODE|-1"),
              after=lambda: {"rows": L.c.sql("SELECT COUNT(*) FROM Graph_KG.ledger_revisions")[0][0]},
              entry="SQL DELETE Graph_KG.ledger_revisions")
    L.c.conn.commit()
    cls = _rev_class(L)
    L.note("LED-B7.3", "revision class", cls=cls, id=rid)

    def resave():
        o = L.c.o.classMethodObject(cls, "%OpenId", str(rid))
        o.set("Message", "tampered")
        st = str(o.invoke("%Save"))
        return {"status": st, "ok": st == "1"}

    def delete():
        st = str(L.c.o.classMethodValue(cls, "%DeleteId", str(rid)))
        return {"status": st, "ok": st == "1"}

    L.refusal("LED-B7.3", "object %Save of a stored revision -> error status",
              resave, returns(lambda r: not r["ok"] and "immutable" in r["status"], "error status 'immutable'"),
              after=lambda: {"message": L.c.sql("SELECT message FROM Graph_KG.ledger_revisions WHERE seq = 2")[0][0]},
              entry=f"{cls}.%OpenId + %Save (Native API)")
    L.refusal("LED-B7.3", "object %DeleteId of a stored revision -> error status",
              delete, returns(lambda r: not r["ok"] and "immutable" in r["status"], "error status 'immutable'"),
              after=lambda: {"rows": L.c.sql("SELECT COUNT(*) FROM Graph_KG.ledger_revisions")[0][0]},
              entry=f"{cls}.%DeleteId (Native API)")
    rollback_all(L.c.conn)


# ---------------------------------------------------------------------------------------------------- client-side
def c_b8_2(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:v")
    for label, fn in [("set_property None", lambda: cs().set_property("rx11:v", "k", None)),
                      ("set_property list", lambda: cs().set_property("rx11:v", "k", [1, 2])),
                      ("create_node props dict value", lambda: cs().create_node("rx11:v2", properties={"k": {"a": 1}})),
                      ("set_qualifier None", lambda: cs().set_qualifier(("rx11:v", "R", "rx11:v"), "k", None))]:
        L.refusal("LED-B8.2", f"builder {label} -> ChangesetOperationError",
                  fn, raises("ChangesetOperationError"), entry="Changeset builder")


def c_b8_4(L):
    L.reset(ledger=True)
    seed_nodes(L, "rx11:o1", "rx11:o2")
    events = []
    L.eng.ledger.register_metrics_hook(lambda ev: events.append(ev))
    L.refusal("LED-B8.4", "commit(empty changeset) -> EmptyChangesetError before sending",
              lambda: L.eng.ledger.commit(cs()), raises("EmptyChangesetError"),
              after=lambda: {"wire_events": len(events)}, entry="engine.ledger.commit")
    bad = cs().create_node("rx11:o3")
    bad.set_qualifier(OpRef(0), "a", "1")
    L.refusal("LED-B8.4", "back link OpRef(0) to a create_node -> ChangesetOperationError before sending",
              lambda: L.eng.ledger.commit(bad), raises("ChangesetOperationError", match="create_rel or upsert_rel"),
              after=lambda: {"wire_events": len(events),
                             "node_rows": _count(L, "nodes", "node_id = ?", "rx11:o3")},
              entry="engine.ledger.commit")
    fwd = cs().set_qualifier(OpRef(1), "a", "1")
    fwd.create_relationship("rx11:o1", "R", "rx11:o2")
    L.refusal("LED-B8.4", "forward back link OpRef(1) -> ChangesetOperationError before sending",
              lambda: L.eng.ledger.commit(fwd), raises("ChangesetOperationError", match="earlier operation"),
              after=lambda: {"wire_events": len(events)}, entry="engine.ledger.commit")
    # a positive control for the hook: a sent (refused) commit emits one event
    L.refusal("LED-B8.4", "control: a server-refused commit is sent and emits one event",
              lambda: L.eng.ledger.commit(cs().remove_label("rx11:o1", "Nope")), failed_op("label_not_present"),
              allowed=[STATS], after=lambda: {"wire_events": len(events)}, entry="engine.ledger.commit")


def c_b15_1(L):
    L.reset()
    for bad in ("Graph_KG.nodes --", "1abc", "Graph KG"):
        L.refusal("LED-B15.1", f"RebuildEdgeIndices({bad!r}) -> refused before any statement",
                  lambda bad=bad: L.c.call("Graph.KG.Ledger", "RebuildEdgeIndices", bad),
                  raises("Exception", match="not an SQL identifier"), entry="Graph.KG.Ledger.RebuildEdgeIndices")
    L.refusal("LED-B15.1", "SQL procedure rebuild_edge_indices('Graph_KG.nodes --') -> refused",
              lambda: L.c.sql("SELECT Graph_KG.rebuild_edge_indices(?)", "Graph_KG.nodes --"),
              raises("Exception", match="not an SQL identifier|SQLCODE|identifier"),
              entry="SQL Graph_KG.rebuild_edge_indices")


CASES = [("b1_9", c_b1_9), ("b1_10", c_b1_10), ("b1_11", c_b1_11), ("b3_4", c_b3_4), ("b4_4", c_b4_4),
         ("b4_5", c_b4_5), ("b4_6", c_b4_6), ("b4_7_1", c_b4_7_1), ("b4_8", c_b4_8), ("b4_8_1", c_b4_8_1),
         ("b4_9", c_b4_9), ("b4_9_1", c_b4_9_1), ("b4_9_2", c_b4_9_2), ("b4_11_8", c_b4_11_8), ("b4_13", c_b4_13),
         ("b5_6", c_b5_6), ("b5_8", c_b5_8), ("b5_10", c_b5_10), ("b5_11", c_b5_11), ("b5_12", c_b5_12),
         ("b5_13", c_b5_13), ("b5_18", c_b5_18), ("b5_21", c_b5_21), ("b5_26", c_b5_26), ("b5_27", c_b5_27),
         ("b6_7", c_b6_7), ("b7", c_b7), ("b8_2", c_b8_2), ("b8_4", c_b8_4), ("b15_1", c_b15_1)]


def main():
    args = sys.argv[1:]
    out = "results.json"
    if args and args[0].startswith("--out="):
        out = args.pop(0)[6:]
    only = args or None
    with Lane("11") as L:
        L.reset()
        L.control()
        run_cases(L, CASES, only)
        L.reset()
        L.save(out if not only or out != "results.json" else "results-partial.json")


if __name__ == "__main__":
    main()
