"""HD-1801 probe: restore an older archive into a namespace whose ledger moved on (merge restore).

Run under the EXCLUSIVE lane lock. Pin API only: engine.ledger.*, save_snapshot, restore_snapshot(merge=True).
A replacing restore (erase_all) is NOT driven here: AUDITIB is shared by the lane's probes and a replacing restore
would erase every graph. The merge restore writes the archive's ^IVG.Ledger and ledger-class storage the same way
(snapshot.py:1554-1588, :1679, node by node over what is there); the replacing path differs only by erase_all, which
keeps ^IVG.Ledger("rec"/"head"/"idem"/...) (Eraser.cls:806-812). The probe refuses to run if rows other than ib3_
exist, because the archive (taken inside this exclusive window) is written back over the namespace.

Alternatives (HD-1801): (a) replace the ledger wholesale; (b) refuse when the live head is not the archive's head
unless forced; (c) never touch the ledger; (d) (b) + re-apply live redactions. As built: overlay.
Oracle (stated): CONTEXT.md:193-196 "append-only revision history"; FR-023 immutability (LedgerRevision triggers);
spec 213 FR-043 "ledger storage survives snapshot save/restore" (tests/integration/test_ledger_snapshot.py:1).
"""
import os
import zipfile
import json

from _ib3_common import Conn, engine_on, meta, out, cleanup, foreign_rows

from iris_vector_graph.ledger import Changeset


def commit(e, label, build):
    cs = Changeset(actor="probe:ib3", actor_type="system", message=label)
    build(cs)
    try:
        r = e.ledger.commit(cs)
        return f"ok seq={r.revision.seq}"
    except Exception as ex:  # noqa: BLE001
        return f"refused {type(ex).__name__}: {str(ex)[:200]}"


def ledger_view(c):
    revs = c.sql("SELECT seq, kind, message FROM Graph_KG.ledger_revisions ORDER BY seq")
    rec_seqs = []
    o = c.o
    s = ""
    while True:
        s = o.nextSubscript(False, "^IVG.Ledger", "rec", s)
        if not s:
            break
        rec_seqs.append(int(s))
    return {"meta_head": meta(c)["head_seq"], "revision_rows": revs, "rec_seqs": rec_seqs}


def main():
    c = Conn("AUDITIB")
    path = os.path.join(os.environ["RUN_DIR"], "intent-b", "ib3_hd1801.snapshot")
    try:
        fr = foreign_rows(c)
        out("foreign rows at start", fr)
        if any(fr.values()):
            out("BLOCKED", "foreign rows present; a restore would write over another probe's data")
            return
        cleanup(c)
        e = engine_on(c)
        e.ledger.enable()
        out("A", commit(e, "A create ib3_r1", lambda cs: cs.create_node("ib3_r1", labels=["IB3"])))
        saved = e.save_snapshot(path)
        with zipfile.ZipFile(path) as zf:
            led = [json.loads(ln) for ln in zf.read("globals/IVG.Ledger.ndjson").decode().splitlines() if ln.strip()]
        out("archive ^IVG.Ledger head", [x["v"] for x in led if x["k"] == ["head"]])
        out("B", commit(e, "B create ib3_r2", lambda cs: cs.create_node("ib3_r2", labels=["IB3"])))
        out("C", commit(e, "C set ib3_r2.k", lambda cs: cs.set_property("ib3_r2", "k", "v")))
        before = ledger_view(c)
        out("live ledger before restore", before)
        rs = e.restore_snapshot(path, merge=True)
        out("restore", {k: rs[k] for k in ("failed_rows", "restored_globals")})
        after = ledger_view(c)
        out("ledger after restore", after)
        h = e.ledger.history(limit=20)
        out("history() after restore", [(r.seq, r.kind) for r in h.revisions])
        d = commit(e, "D create ib3_r3", lambda cs: cs.create_node("ib3_r3"))
        out("D commit after restore", d)
        out("ledger after D", ledger_view(c))
        v = e.ledger.verify()
        out("verify after restore", (v.result, v.classification, [(d.entity_id, d.attr, d.before, d.after) for d in v.differences][:6]))
        mixed = after["meta_head"] < max(after["rec_seqs"])
        out("VERDICT head behind surviving records (history mixes two lines)", mixed)
        out("VERDICT next commit after restore", "VIOLATED: the ledger refuses commits (seq reuse)" if d.startswith("refused")
            else "accepted (check rec mixing above)")
    finally:
        cleanup(c)
        c.close()


if __name__ == "__main__":
    main()
