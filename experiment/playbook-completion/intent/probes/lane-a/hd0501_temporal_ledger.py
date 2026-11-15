"""HD-0501 / HD-0502 probe: what the ledger sees of a temporal write and of the node rows it creates.

Contracts cited:
- ADR-0015 (accepted) Context: "A new temporal triple writes two node rows and one marked edge row".
- CONTEXT.md:66-76: the marked Structural Edge "is not itself a ledger-governed edge (ADR-0009)"; a Temporal Edge is
  "Subject to the revision ledger (via a Changeset temporal op)". Nothing says whether the endpoint NODES are governed.
- docs/USER_GUIDE.md (ledger section): "Writes outside the ledger ... are not recorded, and verify() reports them";
  "A relationship whose endpoint does not exist fails the commit with NodeNotFoundError; auto_stub_missing_nodes=True
  creates the missing nodes instead" (recorded).
- specs/213-graph-revision-ledger/contracts/ledger-api.md:92: in strict mode
  "`create_edge_temporal(..., graph=...)` succeeds but skips the structural mirror".
- tests/integration/test_ledger_us11_temporal_coexist.py: temporal writes and purges create no revisions; verify
  equal (its endpoints always pre-exist as governed default-graph nodes).

Oracle, three paths each with NEW endpoint ids in a probe-private named graph:
  E  engine create_edge_temporal, ledger on, not strict;
  CS changeset create_temporal_edge, committed;
  ES engine create_edge_temporal, strict mode on.
For each: are endpoint node rows created? is a marked edge row created? does a revision record them? does verify()
report the endpoints as unrecorded writes?
- verify() 'diverges' naming the endpoint nodes -> the endpoints are governed content the ledger did not record
  (F-0503 reproduced; reading (b) "derived, excluded" and the coexist test's 'equal' do not hold for new endpoints).
- verify() 'equal' with node rows present -> endpoints are already treated as derived/excluded.
- ES creating node rows / a marked row -> the ledger-api strict-mode clause ("skips the structural mirror") does not
  hold with the adjacency index.
HD-0502 part: the changeset op's record fields (weight/attrs/mode present or not), whether reconstruct() carries the
temporal edge, and whether delete_edge_temporal / purge_raw_before make a revision or change verify().
Restores: strict off, the probe graph erased, the ledger returned to its prior state (disabled if it was not enabled).
"""
from __future__ import annotations

import _common as C

G = "ia-0501"
P = "IA0501_T"
TS = 1_700_000_000


def nodes(c, ids):
    q = "SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id IN (" + ",".join("?" * len(ids)) + ")"
    return sorted(c.sql(q, *ids))


def marked(c, s, o):
    return c.sql("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND graph_id = ?",
                 s, P, o, G)


def revcount(c):
    return c.sql("SELECT COUNT(*) FROM Graph_KG.ledger_revisions")[0][0]


def vdiff(e, prefix="ia0501"):
    r = e.ledger.verify()
    mine = [(d.entity_kind, d.entity_id, d.attr, d.before, d.after) for d in r.differences
            if prefix in str(d.entity_id)]
    return {"result": r.result, "classification": r.classification, "n_diff": len(r.differences), "mine": mine}


def main() -> None:
    c = C.conn()
    e = C.engine(c)
    meta0 = e.ledger.meta()
    C.obs(step="ledger-before", meta=meta0,
          rows=dict(nodes=c.sql("SELECT COUNT(*) FROM Graph_KG.nodes")[0][0],
                    edges=c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges")[0][0]))
    enabled_here = False
    try:
        e.erase_graph(G)
        if meta0.get("state") != "enabled":
            info = e.ledger.enable(strict=False)
            enabled_here = True
            C.obs(step="ledger-enabled", revision=str(info))
        e.ledger.set_strict(False)
        C.obs(step="verify-baseline", **vdiff(e))

        # E: engine path, not strict, new endpoints
        r0 = revcount(c)
        e.create_edge_temporal("ia0501:a", P, "ia0501:b", timestamp=TS, weight=2.5, graph=G)
        C.obs(step="E.engine-temporal", nodes=nodes(c, ["ia0501:a", "ia0501:b"]),
              marked_row=marked(c, "ia0501:a", "ia0501:b"), new_revisions=revcount(c) - r0, verify=vdiff(e))

        # CS: changeset path, new endpoints
        from iris_vector_graph.ledger import Changeset
        cs = Changeset(actor="ia0501-probe", actor_type="system")
        cs.create_temporal_edge("ia0501:c", P, "ia0501:d", ts=TS + 1, weight=3.5, graph=G,
                                attrs={"k": "v"}, mode="update")
        r0 = revcount(c)
        res = e.ledger.commit(cs)
        rev = e.ledger.get_revision(res.revision.revision_id)
        recs = [dict(op=r.op, kind=r.entity_kind, id=r.entity_id, attr=r.attr, new=r.new, graph=r.graph)
                for r in rev.records]
        C.obs(step="CS.changeset-temporal", new_revisions=revcount(c) - r0, records=recs,
              nodes=nodes(c, ["ia0501:c", "ia0501:d"]), marked_row=marked(c, "ia0501:c", "ia0501:d"),
              verify=vdiff(e))
        st = e.ledger.reconstruct(e.ledger.head().revision_id)
        in_recon_nodes = sorted(n for n in st.nodes if str(n).startswith("ia0501"))
        in_recon_stmts = sorted(str(s.tuple) for s in st.statements.values() if "ia0501" in str(s.tuple))
        C.obs(step="CS.reconstruct-head", nodes=in_recon_nodes, statements=in_recon_stmts)

        # ES: engine path in strict mode, new endpoints
        e.ledger.set_strict(True)
        r0 = revcount(c)
        err = None
        try:
            ok = e.create_edge_temporal("ia0501:e", P, "ia0501:f", timestamp=TS + 2, graph=G)
        except Exception as ex:  # noqa: BLE001
            ok, err = None, f"{type(ex).__name__}: {ex}"
        C.obs(step="ES.engine-temporal-strict", ok=ok, error=err, nodes=nodes(c, ["ia0501:e", "ia0501:f"]),
              marked_row=marked(c, "ia0501:e", "ia0501:f"), new_revisions=revcount(c) - r0, verify=vdiff(e))

        # HD-0502: temporal delete and purge under strict mode: refused? revision? verify change?
        r0 = revcount(c)
        before = vdiff(e)
        out = {}
        for name, fn in (("delete_edge_temporal", lambda: e.delete_edge_temporal("ia0501:c", P, "ia0501:d", TS + 1,
                                                                                   graph=G)),
                         ("purge_raw_before", lambda: e.purge_raw_before(TS + 10, graph=G))):
            try:
                out[name] = str(fn())
            except Exception as ex:  # noqa: BLE001
                out[name] = f"raised {type(ex).__name__}: {ex}"
        C.obs(step="HD0502.temporal-delete-purge-strict", results=out, new_revisions=revcount(c) - r0,
              verify_before=before, verify_after=vdiff(e),
              tout_left=int(c.o.isDefined("^KG", "tout", G)),
              nodes=nodes(c, ["ia0501:a", "ia0501:b", "ia0501:c", "ia0501:d", "ia0501:e", "ia0501:f"]))

        C.verdict("pass", "observations recorded; see step lines (verdict per HD in the registry)")
    finally:
        try:
            e.ledger.set_strict(bool(meta0.get("strict")))
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_error=f"set_strict: {ex}")
        try:
            C.obs(step="cleanup-erase", removed=e.erase_graph(G))
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_error=f"erase: {ex}")
        try:
            C.obs(step="verify-after-cleanup", **vdiff(e))
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_error=f"verify: {ex}")
        if enabled_here:
            try:
                e.ledger.disable()
            except Exception as ex:  # noqa: BLE001
                C.obs(cleanup_error=f"disable: {ex}")
        C.obs(step="ledger-after", meta=e.ledger.meta())
        c.close()


if __name__ == "__main__":
    main()
