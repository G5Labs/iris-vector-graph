#!/usr/bin/env python3
"""Smaller lifecycle observations around a redaction (each prints its own verdict).

a. mixed_retry      tenant B retries the revision it shared with tenant A (key shared-k1) after A's
                    redaction; and retries its own unshared revision (key tB-k1).
                    Expected per spec 256 plan step 7: a key in idemRedacted is refused (idempotency_redacted);
                    an unshared key replays. Recorded as observation: whether B's refusal is wanted is a
                    human decision (findings register).
b. readers_midrun   while a redaction is paused: which readers refuse (plan "Readers": get_revision, diff,
                    reconstruct, export_reconstruction raise; verify returns redaction_in_progress).
c. temporal_blocked while a redaction of gA is paused, a commit with a temporal edge into gA is refused
                    (BlocksCommit matches temporal records by tuple) and one into gB is accepted.
d. post_commit      post_commit_properties are written outside the ledger (client._apply_post_commit_properties,
                    "Approach A — direct SQL, no new revision"): what verify() reports afterwards.
"""
import json
import os

from redaction_binding import GA, GB, build
from redaction_common import Changeset, connect, cs, engine, ensure_schema, ledger_records, marker, reset, revision_rows, verdict


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    led = eng.ledger

    # a. mixed retry
    reset(eng, native); build(eng)
    eng.erase_graph(GA); eng.delete_nodes_by_prefix("tenantA|")
    led.redact(GA); led.redact(None, prefix="tenantA")
    # byte-identical to the changesets build() committed (same actor, ops and therefore fingerprint)
    shared = cs("sync both", "shared|c1", "shared-k1", "shared-feed")
    shared.set_property("tenantA|n1", "secret", "alpha2")
    shared.set_property("tenantB|n1", "secret", "bravo2")
    shared.create_relationship("tenantA|n2", "BACK", "tenantA|n1", graph=GA)
    shared.create_relationship("tenantB|n2", "BACK", "tenantB|n1", graph=GB)
    snap = ledger_records(native)
    try:
        led.commit(shared); a_shared = {"outcome": "accepted"}
    except Exception as ex:
        a_shared = {"outcome": type(ex).__name__, "message": str(ex)}
    own = cs("tenantB more", "tenantB|c2", "tB-k2", "tenantB-feed")
    own.set_property("tenantB|n2", "name", "bravoName2")
    own.create_temporal_edge("tenantB|n1", "METRIC", "tenantB|n2", ts=1700000001, weight=6.0, graph=GB)
    try:
        res = led.commit(own); a_own = {"outcome": "replayed" if res.replayed else "new revision"}
    except Exception as ex:
        a_own = {"outcome": type(ex).__name__, "message": str(ex)}
    if os.environ.get("ONLY_MIXED_RETRY"):
        verdict("redaction_mixed_retry", a_shared["outcome"] == "IdempotencyRedactedError" and a_own["outcome"] == "replayed",
                f"tenant B retry of the shared revision: {a_shared['outcome']}; of its own revision: {a_own['outcome']}",
                {"shared": a_shared, "own": a_own, "unchanged_by_refusal": ledger_records(native) == snap})
        return 0
    verdict("redaction_mixed_retry", a_shared["outcome"] == "IdempotencyRedactedError" and a_own["outcome"] == "replayed",
            f"tenant B retry of the shared revision: {a_shared['outcome']}; of its own revision: {a_own['outcome']}",
            {"shared": a_shared, "own": a_own, "unchanged_by_refusal": ledger_records(native) == snap})

    # b. readers mid-run, c. temporal blocked
    reset(eng, native); build(eng)
    eng.erase_graph(GA)
    led.redact(GA, batch_size=1, max_batches=1)
    revs = revision_rows(conn)
    first, last = min(revs), max(revs)
    rid = {s: r["revision_id"] for s, r in revs.items()}
    readers = {}
    for name, fn in [("get_revision", lambda: led.get_revision(rid[first])),
                     ("diff", lambda: led.diff(rid[first], rid[last])),
                     ("reconstruct", lambda: led.reconstruct(rid[last])),
                     ("export_reconstruction", lambda: led.export_reconstruction(rid[last], "/dev/null")),
                     ("verify", lambda: led.verify().result),
                     ("history", lambda: [(r.seq, r.message, r.correlation_id) for r in led.history(limit=100).revisions]),
                     ("stats", lambda: vars(led.stats())),
                     ("ledger_records_sql", lambda: _sql_records(conn))]:
        try:
            out = fn()
            readers[name] = {"refused": False, "sample": json.dumps(out, default=str)[:600]}
        except Exception as ex:
            readers[name] = {"refused": True, "error": type(ex).__name__}
    expected_refuse = {"get_revision", "diff", "reconstruct", "export_reconstruction"}
    ok_b = all(readers[n]["refused"] for n in expected_refuse) and readers["verify"]["sample"].strip('"') == "redaction_in_progress"
    verdict("redaction_readers_midrun", ok_b,
            "refused: " + ", ".join(n for n, v in readers.items() if v["refused"]) +
            "; answered: " + ", ".join(n for n, v in readers.items() if not v["refused"]), {"readers": readers})

    t_in = Changeset(actor="probe", actor_type="ingest")
    t_in.create_temporal_edge("tenantB|n1", "METRIC", "tenantB|n2", ts=1700000500, graph=GA)
    try:
        led.commit(t_in); c_in = "accepted"
    except Exception as ex:
        c_in = type(ex).__name__
    t_out = Changeset(actor="probe", actor_type="ingest")
    t_out.create_temporal_edge("tenantB|n1", "METRIC", "tenantB|n2", ts=1700000501, graph=GB)
    try:
        led.commit(t_out); c_out = "accepted"
    except Exception as ex:
        c_out = type(ex).__name__
    verdict("redaction_temporal_blocked", c_in == "RedactionInProgressError" and c_out == "accepted",
            f"temporal commit into the target graph: {c_in}; into another graph: {c_out}", {"into_target": c_in, "elsewhere": c_out})
    led.redact(GA)

    # d. post_commit_properties and verify
    reset(eng, native)
    led.enable()
    c = cs("pcp", None, None, None)
    c.create_node("pcp|1")
    c.post_commit_properties = {"pcp|1": {"audit_rev": "x"}}
    res = led.commit(c)
    rep = led.verify()
    verdict("ledger_post_commit_verify", rep.result == "equal",
            f"post_commit_applied={res.post_commit_applied}; verify={rep.result}; differences={[vars(d) for d in rep.differences][:3]}",
            {"post_commit_applied": res.post_commit_applied, "verify": rep.result, "differences": [vars(d) for d in rep.differences]})
    return 0


def _sql_records(conn):
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM Graph_KG.ledger_records(1, 1000000, 1, 50)")
        return [list(r) for r in cur.fetchall()][:5]
    finally:
        cur.close()


if __name__ == "__main__":
    raise SystemExit(main())
