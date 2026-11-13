"""HD-1105 probe: post_commit_properties are written outside the revision (spec 218 Approach A).

Run under the EXCLUSIVE lane lock. Pin API only.
  1. commit with post_commit_properties {ib3_p1: {audit: $REVISION_ID}} and an idempotency key
     -> the property row exists, no record of it in the revision (Approach A), verify() reports it (test comment
        tests/e2e/test_470_ledger_caller_txn_e2e.py:218-219)
  2. a governed set_property(ib3_p1, audit, "manual") through the ledger
  3. retry of the first changeset with the same key -> replayed=True; does the retry re-apply the post-commit
     property over the governed value? (F-1101; replay contract ledger-api.md:26 "original outcome with
     replayed=True"; tests/integration/test_ledger_us04_idempotency.py "applies nothing")
Discriminates HD-1105 alternatives: (a) recorded as set_prop of the same revision -> record present, verify equal;
(b) Approach A (as built) -> no record, verify diverges; and F-1101 (replay applies them again).
"""
from _ib3_common import Conn, engine_on, out, cleanup, foreign_rows

from iris_vector_graph.ledger import Changeset
from iris_vector_graph.ledger.changeset import REVISION_ID_SENTINEL


def prop(c):
    return c.sql('SELECT graph_id, val FROM Graph_KG.rdf_props WHERE s = ? AND "key" = ?', "ib3_p1", "audit")


def cs1():
    cs = Changeset(actor="probe:ib3", actor_type="system", idempotency_key="ib3-k1105",
                   post_commit_properties={"ib3_p1": {"audit": REVISION_ID_SENTINEL}})
    cs.create_node("ib3_p1", labels=["IB3"])
    return cs


def main():
    c = Conn("AUDITIB")
    try:
        out("foreign rows at start", foreign_rows(c))
        cleanup(c)
        e = engine_on(c)
        e.ledger.enable()
        r1 = e.ledger.commit(cs1())
        recs = [(m.op, m.entity_id, m.attr, m.new) for m in e.ledger.get_revision(r1.revision.revision_id).records]
        out("1 commit", (r1.revision.seq, r1.replayed, r1.post_commit_applied, r1.post_commit_error))
        out("1 revision records", recs)
        out("1 property row", prop(c))
        v1 = e.ledger.verify()
        out("1 verify", (v1.result, v1.classification, [(d.entity_id, d.attr, d.before, d.after) for d in v1.differences]))

        cs2 = Changeset(actor="probe:ib3", actor_type="system", message="governed overwrite")
        cs2.set_property("ib3_p1", "audit", "manual")
        r2 = e.ledger.commit(cs2)
        out("2 governed set_property", (r2.revision.seq, [(m.op, m.attr, m.prior, m.new) for m in
                                         e.ledger.get_revision(r2.revision.revision_id).records]))
        out("2 property row", prop(c))

        r3 = e.ledger.commit(cs1())
        out("3 retry same key", (r3.revision.seq, r3.replayed, r3.post_commit_applied))
        after = prop(c)
        out("3 property row after replay", after)
        v3 = e.ledger.verify()
        out("3 verify", (v3.result, v3.classification, [(d.entity_id, d.attr, d.before, d.after) for d in v3.differences]))

        approach_a = (not any(op == "set_prop" and attr == "audit" for op, _, attr, _ in recs)) and v1.result == "diverges"
        reapplied = r3.replayed and after and after[0][1] == r1.revision.revision_id
        out("VERDICT (b) Approach A: unrecorded, verify reports it", approach_a)
        out("VERDICT (a) recorded in the revision", not approach_a)
        out("VERDICT replay applies nothing (ledger-api.md:26, us04 test)", "VIOLATED: replay re-applied the post-commit "
            "property over the governed value" if reapplied else "holds")
    finally:
        cleanup(c)
        c.close()


if __name__ == "__main__":
    main()
