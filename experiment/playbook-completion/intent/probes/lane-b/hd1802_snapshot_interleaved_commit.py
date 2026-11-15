"""HD-1802 probe: is a snapshot a point-in-time view? A commit from another process lands between the save's table
reads and its global reads.

Run under the EXCLUSIVE lane lock. Pin API: save_snapshot, engine.ledger.commit. The interleaving is forced in this
test process only: the saving engine's bound `_export_global_to_ndjson` is wrapped so that, before the first global is
read, a second process (an identity-checked Conn with its own engine) commits a ledger changeset. The save holds no
lock and no transaction (snapshot.py:864-1034), so nothing in the product prevents the same interleaving in time.
A quiescent control save (no interleaving) comes first.

Property checked on each archive: the archived ledger head's records are reflected in the archived tables
(every node a create_node record names is in sql/Graph_KG_nodes.ndjson), i.e. replay(archive ledger) == archive rows.
Alternatives (HD-1802): (a) document not point-in-time / quiet writers; (b) hold the ledger head lock (or a
namespace write lock) for the save and record the head; (c) one transaction at a snapshot isolation level (IRIS SQL
offers no MVCC snapshot read, so (c) would not exclude the interleaving: a model must treat it like no lock).
No stated contract at the pin promises a point-in-time view ("point-in-time" was removed from ADMIN_API.md in
e146fc7a, 2026-11-03, "reviewed against the code").
"""
import json
import os
import zipfile

from _ib3_common import Conn, engine_on, out, cleanup, foreign_rows

from iris_vector_graph.ledger import Changeset


def archive_view(path):
    with zipfile.ZipFile(path) as zf:
        nodes = [json.loads(ln)["node_id"] for ln in zf.read("sql/Graph_KG_nodes.ndjson").decode().splitlines() if ln.strip()]
        led = [json.loads(ln) for ln in zf.read("globals/IVG.Ledger.ndjson").decode().splitlines() if ln.strip()]
    head = [x["v"] for x in led if x["k"] == ["head"]]
    rec_seqs = sorted({int(x["k"][1]) for x in led if len(x["k"]) == 3 and x["k"][0] == "rec"})
    ib3_nodes = sorted(n for n in nodes if n.startswith("ib3_"))
    return {"head": head, "rec_seqs": rec_seqs, "ib3_nodes_in_tables": ib3_nodes}


def main():
    c1 = Conn("AUDITIB")
    c2 = Conn("AUDITIB")
    d = os.path.join(os.environ["RUN_DIR"], "intent-b")
    try:
        out("foreign rows at start", foreign_rows(c1))
        cleanup(c1)
        a = engine_on(c1)
        b = engine_on(c2)
        a.ledger.enable()
        cs = Changeset(actor="probe:ib3", actor_type="system")
        cs.create_node("ib3_q1")
        out("commit 1", a.ledger.commit(cs).revision.seq)

        p0 = os.path.join(d, "ib3_hd1802_quiet.snapshot")
        a.save_snapshot(p0)
        v0 = archive_view(p0)
        out("quiet save", v0)

        orig = a._export_global_to_ndjson
        fired = {}

        def interleave(iris_obj, global_name, prefix_subs):
            if not fired:
                cs2 = Changeset(actor="probe:ib3-other-process", actor_type="system")
                cs2.create_node("ib3_q2")
                fired["seq"] = b.ledger.commit(cs2).revision.seq
                fired["before_global"] = global_name
            return orig(iris_obj, global_name, prefix_subs)

        a._export_global_to_ndjson = interleave
        p1 = os.path.join(d, "ib3_hd1802_interleaved.snapshot")
        a.save_snapshot(p1)
        v1 = archive_view(p1)
        out("other process committed during save", fired)
        out("interleaved save", v1)
        quiet_ok = (v0["head"] == ["2"] or v0["head"] == [2]) and v0["ib3_nodes_in_tables"] == ["ib3_q1"]
        torn = str(v1["head"][0]) == str(fired.get("seq")) and "ib3_q2" not in v1["ib3_nodes_in_tables"]
        out("VERDICT quiet save consistent (premise of alternative a suffices here)", quiet_ok)
        out("VERDICT interleaved save torn: archived ledger head includes a revision whose rows are not archived", torn)
    finally:
        cleanup(c1)
        c1.close()
        c2.close()


if __name__ == "__main__":
    main()
