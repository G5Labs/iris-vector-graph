"""Intent lane B probes for the erasure / redaction / replay decisions (HD-1201, HD-1303, HD-1304, HD-1305, HD-1401).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 900 \
        python experiment/playbook-completion/intent/probes/lane-b/hd12_14_redaction_probes.py <scenario> > LOG 2>&1

Scenarios (each starts from a purged ledger and removes its own ibR_ data at the end; at most 3 connections):

  open_erasure      HD-1201  A redaction starts while an erasure of its target is open (caller transaction on the
                             eraser's connection), completes, and the erasure then rolls back.
                             Stated contract: ADR-0013:17 "Redaction only follows erasure. It is refused while any row
                             of the target is live"; spec 256 FR-005; CONTEXT.md:212.
  reader_full_race  HD-1401  A record reader (ledger.reconstruct, default page size 5,000) reads its first page, a whole
                             redaction of the target runs to completion in another process, the reader reads the rest.
                             Stated contract: spec 256 Decision 3 (readers honour the marker; it replaced "atomic from a
                             reader's view", commit 42907b21) and client.py:691-692 ("record readers would see it half
                             done"). Discriminates mechanisms: a post-read marker re-check (the original reviewed model)
                             vs a redaction epoch (head / redaction revision count) compared before and after.
  nopfx_default     HD-1303b Nodes live only in a named graph, recorded graph-blind by the genesis; redact(None) with no
                             prefix. Stated design: specs/256-ledger-tenant-redaction/plan.md:10 ("the node-liveness check
                             for a default-graph target is graph-blind").
  graph_per_tenant  HD-1304  One graph per tenant, unprefixed node ids; erase_graph + redact(graph). Spec 256 context
                             (spec.md:16-18, US1) vs ADR-0013:37 (node records reachable only by prefix).
  retry_revives     HD-1305  (1) a retry between erase and redaction replays and re-applies post_commit_properties;
                             (2) a retry during an unfinished run of the same target does the same while the marker is
                             set. Stated contract: ledger-api.md:26 ("original outcome with replayed=True"),
                             tests/integration/test_ledger_us04_idempotency.py:52 ("applies nothing"), Ledger.cls:514
                             ("while a redaction runs, nothing may be written into its target"), ADR-0013:15.

Only the pin's public Python API and deployed class methods are used. The interleavings are forced from this test
process (as the original uplift's reader_races_redaction did); no product code is changed.
"""
from __future__ import annotations

import json
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITIB"
PFX = "ibR_"
GA, GB = "ibR_gA", "ibR_gB"
VERDICTS: list = []


def out(label, value=None):
    print(label if value is None else f"{label}: {value}", flush=True)


def verdict(name, ok, detail=""):
    VERDICTS.append((name, bool(ok)))
    out(f"CHECK {'TRUE ' if ok else 'FALSE'} {name}", detail)


def eng(c: Conn) -> IRISGraphEngine:
    # Built on the caller's connection: Native API calls run in the same server process as its SQL.
    return IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)


def meta(c: Conn) -> dict:
    return json.loads(str(c.call("Graph.KG.Ledger", "Meta")))


def purge(c: Conn) -> None:
    c.call("Graph.KG.Ledger", "PurgeAll")  # Ledger.cls:241-248, the pin's test/admin reset


def cs(actor="probe:ibR", **kw) -> Changeset:
    return Changeset(actor=actor, actor_type="ingest", **kw)


def rows(c: Conn, graph=None, prefix=None) -> dict:
    res = {}
    for t, col in (("nodes", "node_id"), ("rdf_edges", "s"), ("rdf_labels", "s"), ("rdf_props", "s")):
        q = f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE 1=1"
        args = []
        if graph is not None:
            q += " AND COALESCE(graph_id, '') = ?"
            args.append(graph)
        if prefix is not None:
            q += f" AND %EXACT({col}) %STARTSWITH ?"
            args.append(prefix)
        res[t] = c.sql(q, *args)[0][0]
    return res


def rec_scan(c: Conn, needle: str) -> int:
    """Count ^IVG.Ledger("rec") values that contain needle (server-side, read-only, via the Native API)."""
    n = 0
    o = c.o
    seq = o.nextSubscript(False, "^IVG.Ledger", "rec", "")
    while seq is not None and seq != "":
        ordn = o.nextSubscript(False, "^IVG.Ledger", "rec", seq, "")
        while ordn is not None and ordn != "":
            raw = o.getBytes("^IVG.Ledger", "rec", seq, ordn) or b""
            if needle.encode() in raw:
                n += 1
            ordn = o.nextSubscript(False, "^IVG.Ledger", "rec", seq, ordn)
        seq = o.nextSubscript(False, "^IVG.Ledger", "rec", seq)
    return n


def node_records(c: Conn, prefix: str) -> dict:
    """Node records (entity_kind 'node') whose id starts with prefix, read through the pin's record reader, by op.
    Tombstones carry no id, so they are not counted."""
    import iris_vector_graph.ledger.replay as rp
    head = json.loads(str(c.call("Graph.KG.Ledger", "Meta"))).get("head_seq") or 0
    out_ = {}
    for r in rp.iter_records_sql(c.conn, "Graph_KG", 1, int(head)):
        if r.entity_kind == "node" and (r.entity_id or "").startswith(prefix):
            out_[r.op] = out_.get(r.op, 0) + 1
    return out_


def stmt_count(c: Conn, graph: str) -> int:
    o = c.o
    n = 0
    sid = o.nextSubscript(False, "^IVG.Ledger", "stmt", "")
    while sid is not None and sid != "":
        raw = o.getBytes("^IVG.Ledger", "stmt", sid) or b""
        if graph.encode() in raw:
            n += 1
        sid = o.nextSubscript(False, "^IVG.Ledger", "stmt", sid)
    return n


def marker(e) -> object:
    return e.ledger.redaction_in_progress()


def cleanup(c: Conn) -> None:
    purge(c)
    e = eng(c)
    for g in (GA, GB):
        try:
            e.erase_graph(g)
        except Exception as ex:  # noqa: BLE001
            out(f"cleanup erase_graph({g}) failed", repr(ex))
    try:
        e.delete_nodes_by_prefix(PFX)
    except Exception as ex:  # noqa: BLE001
        out("cleanup delete_nodes_by_prefix failed", repr(ex))
    for t, col in (("rdf_edges", "s"), ("rdf_labels", "s"), ("rdf_props", "s"), ("nodes", "node_id")):
        c.sql(f"DELETE FROM Graph_KG.{t} WHERE %EXACT({col}) %STARTSWITH ?", PFX)
    purge(c)
    out("cleanup: ibR_ rows left", rows(c, prefix=PFX))
    out("cleanup: ledger state", meta(c).get("state"))


def foreign(c: Conn) -> dict:
    return {t: c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE NOT (%EXACT({col}) %STARTSWITH ?)", PFX)[0][0]
            for t, col in (("nodes", "node_id"), ("rdf_edges", "s"))}


# --------------------------------------------------------------------------------------------- HD-1201
def open_erasure(c1: Conn, c2: Conn) -> None:
    e1, e2 = eng(c1), eng(c2)
    e1.ledger.enable()
    a = cs(message="tenant A", idempotency_key="ibR-kA")
    a.create_node("ibR_A|n1", properties={"secret": "alphaSecret"})
    a.create_node("ibR_A|n2")
    a.create_relationship("ibR_A|n1", "LINKS", "ibR_A|n2", qualifiers={"note": "alphaNote"}, graph=GA)
    e1.ledger.commit(a)
    b = cs(message="tenant B")
    b.create_node("ibR_B|m1")
    b.create_node("ibR_B|m2")
    b.create_relationship("ibR_B|m1", "LINKS", "ibR_B|m2", graph=GB)
    e1.ledger.commit(b)
    out("verify before", e1.ledger.verify().result)
    gA_rel_records_before = rec_scan(c1, "alphaNote") + rec_scan(c1, GA)
    out("records naming gA before", gA_rel_records_before)

    cur = c1.conn.cursor()
    cur.execute("START TRANSACTION")
    # One caller write so $TLEVEL > 0 before the erase (as the 4.7.0 caller-transaction tests do).
    cur.execute("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES ('ibR_txn', '')")
    cur.close()
    removed = e1.erase_graph(GA)
    tl = c1.sql("SELECT $TLEVEL")[0][0]
    out("erase_graph(gA) inside the caller transaction removed", removed)
    out("caller $TLEVEL after erase_graph (erasure still open)", tl)
    out("gA rows seen by the redactor's process while the erasure is open", rows(c2, graph=GA))

    receipt, err = None, None
    try:
        receipt = e2.ledger.redact(GA)
    except Exception as ex:  # noqa: BLE001
        err = f"{type(ex).__name__}: {ex}"
    out("redact(gA) from a second process during the open erasure",
        err or {"complete": receipt.complete, "records_tombstoned": receipt.records_tombstoned,
                "revisions": receipt.revision_seqs, "redaction_seq": getattr(receipt.redaction, "seq", None)})

    cur = c1.conn.cursor()
    cur.execute("ROLLBACK")
    cur.close()
    after_rows = rows(c2, graph=GA)
    out("gA rows after the erasure rolled back", after_rows)
    out("gA statement entries after rollback", stmt_count(c2, GA))
    out("records still naming gA after rollback", rec_scan(c2, GA))
    out("marker after", marker(e2))
    v = e2.ledger.verify()
    out("verify after", (v.result, v.classification, [str(d)[:140] for d in v.differences[:6]]))

    verdict("erasure was open (caller $TLEVEL > 0) when the redaction ran", int(tl) > 0, tl)
    verdict("redaction was accepted and completed during the open erasure",
            receipt is not None and receipt.complete and receipt.records_tombstoned > 0, err)
    verdict("after the erasure rolled back the target is live again", after_rows["rdf_edges"] > 0, after_rows)
    verdict("its history is redacted while it is live (no record names gA)", rec_scan(c2, GA) == 0)
    verdict("verify() is no longer equal", v.result != "equal", v.result)
    out("ORACLE ADR-0013:17 / FR-005: redaction only follows erasure and is refused while the target is live")
    violated = (receipt is not None and receipt.complete and after_rows["rdf_edges"] > 0 and v.result != "equal")
    out("RESULT", "VIOLATED (fail): a redaction ran on an erasure that never committed" if violated
        else "HOLDS (pass) or not reproduced")


# --------------------------------------------------------------------------------------------- HD-1401
def reader_full_race(c1: Conn, c2: Conn) -> None:
    import iris_vector_graph.ledger.replay as rp
    from iris_vector_graph.ledger.errors import RedactionInProgressError

    e1, e2 = eng(c1), eng(c2)
    e1.ledger.enable()
    a1 = cs(message="tenant A first")
    a1.create_node("ibR_A|n1")
    a1.create_node("ibR_A|n2")
    a1.create_relationship("ibR_A|n1", "LINKS", "ibR_A|n2", qualifiers={"note": "alphaFirst"}, graph=GA)
    e1.ledger.commit(a1)
    bulk = cs(message="tenant B bulk")
    for i in range(5200):  # more than one reader page (replay.RECORD_PAGE = 5,000)
        bulk.create_node(f"ibR_B|x{i}")
    e1.ledger.commit(bulk)
    a2 = cs(message="tenant A second")
    a2.create_node("ibR_A|n3")
    a2.create_relationship("ibR_A|n2", "LINKS", "ibR_A|n3", qualifiers={"note": "alphaSecond"}, graph=GA)
    e1.ledger.commit(a2)
    e1.erase_graph(GA)
    head = e1.ledger.head()
    out("head after erase", (head.seq, head.revision_id))
    pre = e1.ledger.reconstruct(head.revision_id).as_comparable()
    pre_ga = sorted(k for k in pre["rels"] if k[3] == GA)
    out("gA statements in the pre-redaction view", pre_ga)

    # Position of the first gA relationship record in the reader's stream.
    stream = list(rp.iter_records_sql(c1.conn, "Graph_KG", 1, head.seq))
    first_ga = next(i for i, r in enumerate(stream) if getattr(r, "graph", None) == GA and r.op == "create_rel")
    last_ga = max(i for i, r in enumerate(stream) if getattr(r, "graph", None) == GA and r.op == "create_rel")
    out("records in stream / first gA create_rel index / last gA create_rel index", (len(stream), first_ga, last_ga))

    orig = rp.iter_records_sql
    fired: dict = {}

    def racing(conn, schema, seq_from, seq_to, *a, **kw):
        inner = orig(conn, schema, seq_from, seq_to, *a, **kw)

        def gen():
            n = 0
            for rec in inner:
                yield rec
                n += 1
                if n == first_ga + 1 and not fired:
                    r = e2.ledger.redact(GA)  # another server process, to completion
                    fired["receipt"] = {"complete": r.complete, "records_tombstoned": r.records_tombstoned,
                                        "redaction_seq": getattr(r.redaction, "seq", None)}
        return gen()

    marker_before = marker(e1)
    head_before = e1.ledger.head().seq
    rp.iter_records_sql = racing
    view, err = None, None
    try:
        view = e1.ledger.reconstruct(head.revision_id).as_comparable()
    except RedactionInProgressError as ex:
        err = f"RedactionInProgressError: {ex}"
    finally:
        rp.iter_records_sql = orig
    marker_after = marker(e1)
    head_after = e1.ledger.head().seq
    post = e1.ledger.reconstruct(head.revision_id).as_comparable()
    post_ga = sorted(k for k in post["rels"] if k[3] == GA)
    view_ga = sorted(k for k in (view or {"rels": {}})["rels"] if k[3] == GA)
    out("redaction run inside the read", fired.get("receipt"))
    out("marker before the read / after the read", (marker_before, marker_after))
    out("head seq before / after the read", (head_before, head_after))
    out("gA statements: pre / reader's view / post", (len(pre_ga), len(view_ga), len(post_ga)))
    out("reader's gA statements", view_ga)

    verdict("the whole redaction completed inside the reader's read", bool(fired.get("receipt", {}).get("complete")))
    verdict("the reader answered (no RedactionInProgressError)", err is None, err)
    verdict("its view is neither the pre- nor the post-redaction state (half redacted)",
            view is not None and 0 < len(view_ga) < len(pre_ga) and len(post_ga) == 0, (len(view_ga), len(pre_ga)))
    verdict("a marker re-check after the read sees no marker (the re-check mechanism would accept the view)",
            marker_after is None)
    verdict("a redaction epoch (head seq) changed across the read (an epoch check would refuse/retry)",
            head_after != head_before, (head_before, head_after))
    violated = view is not None and 0 < len(view_ga) < len(pre_ga)
    out("ORACLE spec 256 Decision 3 + client.py:691-692: readers never return a half-done redaction")
    out("RESULT", "VIOLATED (fail): reconstruct returned a half-redacted view; a post-read marker re-check would "
        "not detect it" if violated else "HOLDS or not reproduced")


# --------------------------------------------------------------------------------------------- HD-1303(b)
def nopfx_default(c1: Conn, c2: Conn) -> None:
    e1 = eng(c1)
    for i in (1, 2):
        e1.create_node(f"ibR_B|m{i}", properties={"secret": f"bravo{i}"}, graph=GB)
    e1.create_edge("ibR_B|m1", "LINKS", "ibR_B|m2", graph=GB)
    e1.ledger.enable()  # genesis records gB's nodes graph-blind
    out("verify after genesis", e1.ledger.verify().result)
    out("default-graph rows / gB rows", (rows(c1, graph=""), rows(c1, graph=GB)))
    before_nodes = node_records(c1, "ibR_B|")
    out("node records of ibR_B| ids before (by op)", before_nodes)
    receipt, err = None, None
    try:
        receipt = e1.ledger.redact(None)
    except Exception as ex:  # noqa: BLE001
        err = f"{type(ex).__name__}: {ex}"
    out("redact(None) with no prefix", err or {"complete": receipt.complete,
                                               "records_tombstoned": receipt.records_tombstoned})
    v = e1.ledger.verify()
    after_nodes = node_records(c1, "ibR_B|")
    out("node records of ibR_B| ids after (by op)", after_nodes)
    out("gB relationship record still names ibR_B|m1 (graph gB, not the target)", rec_scan(c1, "ibR_B|m1"))
    out("gB rows after (still live)", rows(c1, graph=GB))
    out("verify after", (v.result, v.classification, [str(d)[:140] for d in v.differences[:6]]))
    tomb = bool(before_nodes) and not after_nodes
    verdict("the no-prefix default-graph target was accepted while gB's recorded nodes are live",
            receipt is not None, err)
    verdict("gB's live nodes' node records were all tombstoned", tomb, (before_nodes, after_nodes))
    verdict("verify() diverges afterwards", v.result != "equal", v.result)
    out("ORACLE plan.md:10: the node-liveness check for a default-graph target is graph-blind (would refuse)")
    out("RESULT", "VIOLATED (fail) against plan.md:10" if receipt is not None and tomb else "HOLDS (refused)")


# --------------------------------------------------------------------------------------------- HD-1304
def graph_per_tenant(c1: Conn, c2: Conn) -> None:
    e1 = eng(c1)
    for i in (1, 2):
        e1.create_node(f"ibR_u{i}", properties={"secret": f"alphaUnpfx{i}"}, graph=GA)
        e1.create_node(f"ibR_v{i}", properties={"secret": f"bravoUnpfx{i}"}, graph=GB)
    e1.create_edge("ibR_u1", "LINKS", "ibR_u2", graph=GA)
    e1.create_edge("ibR_v1", "LINKS", "ibR_v2", graph=GB)
    e1.ledger.enable()
    out("verify after genesis", e1.ledger.verify().result)
    e1.erase_graph(GA)
    r = e1.ledger.redact(GA)
    out("redact(gA) receipt", {"complete": r.complete, "records_tombstoned": r.records_tombstoned,
                               "out_of_reach": r.out_of_reach if hasattr(r, "out_of_reach") else None})
    left = {n: rec_scan(c1, n) for n in ("ibR_u1", "ibR_u2", "alphaUnpfx1")}
    out("records still naming tenant A's node ids / values after erase+redact", left)
    v = e1.ledger.verify()
    out("verify after", (v.result, v.classification, len(v.differences)))
    try:
        rp_ = e1.ledger.redact(None, prefix="ibR_u")
        pfx = f"accepted, records_tombstoned={rp_.records_tombstoned} (prefix+separator 'ibR_u|' matches no id)"
    except Exception as ex:  # noqa: BLE001
        pfx = f"{type(ex).__name__}"
    out("a prefix call cannot express the tenant (ids carry no tenant separator); redact(None, prefix='ibR_u')", pfx)
    verdict("redact(gA) reports complete", r.complete)
    verdict("tenant A's node ids and values remain in the history", any(left.values()), left)
    verdict("the receipt does not say so (out_of_reach names only exports, journals, backups)",
            all("node" not in s for s in getattr(r, "out_of_reach", []) or []))
    verdict("verify() diverges after erase + redact (spec 256 FR-007 expects equal)", v.result != "equal", v.result)
    out("ORACLE spec 256 context (spec.md:16-18) + US1 + FR-007 vs ADR-0013:37 (prefix-only node records)")
    out("RESULT", "EXPECTED-VIOLATION: documented limitation (ADR-0013:37) contradicts the spec's deployment"
        if any(left.values()) else "HOLDS")


# --------------------------------------------------------------------------------------------- HD-1305
def retry_revives(c1: Conn, c2: Conn) -> None:
    e1 = eng(c1)
    e1.ledger.enable()

    def tenant_cs():
        x = cs(message="tenant A with post-commit", idempotency_key="ibR-retry-k")
        x.create_node("ibR_A|n5")
        x.post_commit_properties = {"ibR_A|n5": {"audit": "alphaAudit"}}
        return x

    first = e1.ledger.commit(tenant_cs())
    out("first commit", (first.revision.seq, first.replayed, first.post_commit_applied))
    e1.delete_nodes_by_prefix("ibR_A|")
    out("ibR_A| rows after erasure (any graph)", rows(c1, prefix="ibR_A|"))
    again = e1.ledger.commit(tenant_cs())
    out("retry between erase and redaction", (again.revision.seq, again.replayed, again.post_commit_applied))
    revived = rows(c1, prefix="ibR_A|")
    out("ibR_A| rows after the retry", revived)
    try:
        e1.ledger.redact(None, prefix="ibR_A")
        red = "accepted"
    except Exception as ex:  # noqa: BLE001
        red = f"{type(ex).__name__}: {str(ex)[:160]}"
    out("redact(None, prefix='ibR_A') after the retry", red)
    verdict("(1) the retry replayed (replayed=True) and re-applied post-commit properties",
            again.replayed and again.post_commit_applied)
    verdict("(1) the erased tenant's property row is live again", revived["rdf_props"] > 0, revived)
    verdict("(1) the redaction is now refused as target_live", "Live" in red or "live" in red, red)

    # (2) during an unfinished run of the same target
    purge(c1)
    c1.sql("DELETE FROM Graph_KG.rdf_props WHERE %EXACT(s) %STARTSWITH ?", PFX)
    e1.delete_nodes_by_prefix(PFX)
    e1.ledger.enable()
    pre = cs(message="tenant A early")
    pre.create_node("ibR_A|n1")
    pre.create_node("ibR_A|n2")
    e1.ledger.commit(pre)
    e1.ledger.commit(tenant_cs())  # later seq, key bound
    e1.delete_nodes_by_prefix("ibR_A|")
    part = e1.ledger.redact(None, prefix="ibR_A", batch_size=1, max_batches=1)
    out("partial run", {"complete": part.complete, "records_tombstoned": part.records_tombstoned,
                        "marker": marker(e1) is not None})
    blocked = None
    try:
        b = cs(message="direct write into the target")
        b.create_node("ibR_A|n9")
        e1.ledger.commit(b)
        blocked = "committed"
    except Exception as ex:  # noqa: BLE001
        blocked = f"{type(ex).__name__}"
    out("control: a fresh commit into the target while the marker exists", blocked)
    again2 = e1.ledger.commit(tenant_cs())
    out("retry while the marker exists", (again2.revision.seq, again2.replayed, again2.post_commit_applied))
    during = rows(c1, prefix="ibR_A|")
    out("ibR_A| rows after the retry during the run", during)
    try:
        r2 = e1.ledger.redact(None, prefix="ibR_A")
        fin = {"complete": r2.complete}
    except Exception as ex:  # noqa: BLE001
        fin = f"{type(ex).__name__}: {str(ex)[:160]}"
    out("resumed run", fin)
    out("marker after resume", marker(e1))
    verdict("(2) control: a fresh commit into the target is refused while the marker exists",
            blocked != "committed", blocked)
    verdict("(2) the replayed retry wrote a post-commit property into the target while the marker exists",
            again2.replayed and during["rdf_props"] > 0, during)
    verdict("(2) the resumed run cannot finish (target_live) and the marker stays",
            isinstance(fin, str) and marker(e1) is not None, fin)
    out("ORACLE ledger-api.md:26 replay = original outcome; test_ledger_us04 'applies nothing'; Ledger.cls:514; "
        "ADR-0013:15")
    out("RESULT", "VIOLATED (fail)" if again.post_commit_applied and revived["rdf_props"] > 0 else "HOLDS")


SCENARIOS = {f.__name__: f for f in (open_erasure, reader_full_race, nopfx_default, graph_per_tenant, retry_revives)}


def main() -> int:
    name = sys.argv[1]
    c1, c2 = Conn(NS), Conn(NS)
    try:
        out("scenario", name)
        out("connections (pids)", (c1.pid, c2.pid))
        out("foreign (non-ibR_) rows at start", foreign(c1))
        cleanup(c1)
        try:
            SCENARIOS[name](c1, c2)
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            out("SCENARIO ERROR", repr(ex))
        finally:
            try:
                cur = c1.conn.cursor()
                cur.execute("ROLLBACK")
                cur.close()
            except Exception:  # noqa: BLE001
                pass
            cleanup(c1)
        out("VERDICTS", VERDICTS)
    finally:
        c1.close()
        c2.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
