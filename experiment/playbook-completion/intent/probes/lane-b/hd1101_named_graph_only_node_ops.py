"""HD-1101 probe: ledger node changes on an id that only a named graph holds (F-1105).

Run under the EXCLUSIVE lane lock. Pin API only: engine.create_node(graph=...), engine.ledger.enable/commit/verify,
Changeset builder; SQL reads of the canonical tables.

Discriminates the alternatives of HD-1101:
  (a) refuse node changes whose default-graph row is absent  -> expect refusals for set_prop/add_label/delete_node
  (b) materialise the default-graph row first                -> expect a nodes row ('' graph) after set_prop
  (c) as built (graph-blind NodeExists, default-graph writes) -> create refused node_exists; set_prop writes an
      orphan default-graph rdf_props row; add_label fails on the FK; delete_node records a delete that removed nothing
Stated-contract oracle: a commit the ledger accepts keeps replay == store (ADR-0013:35 "Verifiable means replay
equals the store"; USER_GUIDE.md:1085-1088,1107-1108: verify() reports writes made outside the ledger). A divergence
after ledger-only writes is a violation.
"""
from _ib3_common import Conn, engine_on, meta, out, purge_ledger, cleanup, foreign_rows

from iris_vector_graph.ledger import Changeset

G = "ib3_g1101"


def commit(e, label, build):
    cs = Changeset(actor="probe:ib3", actor_type="system", message=label)
    build(cs)
    try:
        r = e.ledger.commit(cs)
        recs = [(m.op, m.entity_id, m.attr, m.prior, m.new) for m in e.ledger.get_revision(r.revision.revision_id).records]
        out(f"[{label}] committed seq={r.revision.seq}", recs)
        return ("ok", recs)
    except Exception as ex:  # noqa: BLE001
        out(f"[{label}] refused", f"{type(ex).__name__}: {ex}")
        return ("refused", f"{type(ex).__name__}: {ex}")


def rows(c, nid):
    return {
        "nodes": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = ?", nid),
        "labels": c.sql("SELECT graph_id, label FROM Graph_KG.rdf_labels WHERE s = ?", nid),
        "props": c.sql('SELECT graph_id, "key", val FROM Graph_KG.rdf_props WHERE s = ?', nid),
    }


def main():
    c = Conn("AUDITIB")
    try:
        out("foreign rows at start", foreign_rows(c))
        cleanup(c, graphs=(G,))
        e = engine_on(c)
        for n in ("ib3_n1", "ib3_n2", "ib3_n3", "ib3_n4"):
            out(f"create_node({n}, graph={G})", e.create_node(n, labels=["InG"], properties={"p": "g"}, graph=G))
        out("create_node(ib3_d) default graph (control)", e.create_node("ib3_d", labels=["InDefault"]))
        gen = e.ledger.enable()
        out("enable -> genesis", (gen.seq, gen.kind))
        v0 = e.ledger.verify()
        out("verify after genesis", v0.result)

        res = {}
        res["create_node"] = commit(e, "create_node ib3_n1", lambda cs: cs.create_node("ib3_n1"))
        res["upsert_node"] = commit(e, "upsert_node ib3_n1 (no labels/props)", lambda cs: cs.upsert_node("ib3_n1"))
        res["set_prop"] = commit(e, "set_property ib3_n1.k=v", lambda cs: cs.set_property("ib3_n1", "k", "v"))
        out("rows ib3_n1 after set_prop", rows(c, "ib3_n1"))
        res["add_label"] = commit(e, "add_label ib3_n2 L2", lambda cs: cs.add_label("ib3_n2", "L2"))
        res["remove_label"] = commit(e, "remove_label ib3_n4 InG", lambda cs: cs.remove_label("ib3_n4", "InG"))
        res["delete_node"] = commit(e, "delete_node ib3_n3 (strict)", lambda cs: cs.delete_node("ib3_n3"))
        out("rows ib3_n3 after delete_node", rows(c, "ib3_n3"))
        res["control_delete_default"] = commit(e, "delete_node ib3_d (control, default graph)",
                                               lambda cs: cs.delete_node("ib3_d"))
        v1 = e.ledger.verify()
        diffs = [(d.entity_kind, d.entity_id, d.attr, d.before, d.after) for d in v1.differences]
        out("verify after ledger-only commits", (v1.result, v1.classification, diffs[:10]))

        orphan = c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props p WHERE p.s = 'ib3_n1' AND p.graph_id = '' AND NOT EXISTS "
                       "(SELECT 1 FROM Graph_KG.nodes n WHERE n.node_id = p.s AND n.graph_id = '')")[0][0]
        out("orphan default-graph property rows for ib3_n1", orphan)

        # Verdicts
        a_refuses = all(res[k][0] == "refused" for k in ("set_prop", "add_label", "delete_node"))
        b_materialises = any(r[0] == "" for r in rows(c, "ib3_n1")["nodes"])
        c_as_built = (res["create_node"][0] == "refused" and "node_exists" in str(res["create_node"][1])
                      and res["set_prop"][0] == "ok" and orphan == 1
                      and res["add_label"][0] == "refused" and "insert label failed" in str(res["add_label"][1])
                      and res["delete_node"][0] == "ok")
        out("VERDICT alternative (a) refuse", a_refuses)
        out("VERDICT alternative (b) materialise default row", b_materialises)
        out("VERDICT alternative (c) as built (F-1105)", c_as_built)
        out("VERDICT stated contract replay==store after ledger-only commits",
            "holds" if v1.result == "equal" else "VIOLATED (" + v1.result + ")")
        out("ledger meta at end", meta(c))
    finally:
        cleanup(c, graphs=(G,))
        c.close()


if __name__ == "__main__":
    main()
