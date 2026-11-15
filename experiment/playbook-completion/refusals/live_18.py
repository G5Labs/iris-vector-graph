#!/usr/bin/env python3
"""Module 18 (snapshots): live probes of the stated refusals (SNP kind X) in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_18.py [--out NAME] [case ...]

Each case triggers the refused condition through the product's real entry point (engine.save_snapshot /
restore_snapshot, the Graph.KG.Snapshot class methods over the Native API) inside a journal window (rxlib). Crafted
archives are ZIP files written under $RUN_DIR/refusals/18/archives (client side); the one server-side directory
(SNP-X5.1) is a scratch path under /tmp created by the product's own ExportGlobals and removed by this script.
Scratch content uses ids and graphs starting rx18; the only non-product global is ^IVGAuditRX18 (scratch).
Results: $RUN_DIR/refusals/18/<NAME or results.json>.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, returns, run_cases, open_caller_txn, rollback_all, tlevel  # noqa: E402

STATS = r"(?i)ledger_?stats"   # the stats row a counted strict-mode rejection bumps (guard.py:75-80, Ledger.cls Count)
# restore's version floors: _raise_nkg_version / _raise_kg_version and ArnoAccel.BumpVersion (snapshot.py:37-58,
# 1588-1591; ArnoAccel.cls:299-303) run in restore's `finally` whenever the archive holds any global file
VERSIONS = [r'^\^KG\("__version"\)$', r'^\^NKG\("\$meta","version"\)$']

ARCH = None  # set in main


def seed(L, g="rx18g"):
    e = L.eng
    e.create_node("rx18:a", labels=["RX18"], properties={"name": "a"}, graph=g)
    e.create_node("rx18:b", labels=["RX18"], properties={"name": "b"}, graph=g)
    e.create_edge("rx18:a", "R", "rx18:b", graph=g)
    L.c.conn.commit()


def real_archive(L, name="real.zip"):
    p = ARCH / name
    if p.exists():
        p.unlink()
    L.eng.save_snapshot(str(p))
    return p


def craft(src: Path, name: str, *, layout=None, sql=None, globals_=None, keep_members=False) -> Path:
    """A copy of a real archive's metadata.json with chosen sql/ and globals/ members (crafted archive)."""
    with zipfile.ZipFile(src) as z:
        meta = json.loads(z.read("metadata.json"))
        members = {n: z.read(n) for n in z.namelist() if n != "metadata.json"} if keep_members else {}
    if layout is not None:
        meta["layout"] = layout
    meta["tables"], meta["globals"] = {}, {}
    out = ARCH / name
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("metadata.json", json.dumps(meta, indent=2))
        for n, b in members.items():
            z.writestr(n, b)
        for n, lines in (sql or {}).items():
            z.writestr(f"sql/{n}.ndjson", "\n".join(json.dumps(x) for x in lines))
        for n, lines in (globals_ or {}).items():
            z.writestr(f"globals/{n}.ndjson", "\n".join(json.dumps(x) for x in lines))
    return out


def node_ids(L):
    return sorted(r[0] for r in L.c.sql("SELECT node_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'rx18'"))


# ------------------------------------------------------------------------------------------------- save
def c_x1_9_1(L):
    """SNP-X1.9.1: NodeValueJSON / SetNodeJSON refuse any global but ^IVF, ^PLAID, ^VecIdx (Snapshot.cls:93-106)."""
    L.reset()
    seed(L)
    o = L.c.o
    # positive control: an allowed global is answered ("" for an absent node), so the refusal is name-specific
    ok = o.classMethodValue("Graph.KG.Snapshot", "NodeValueJSON", "^IVF", json.dumps(["rx18none"]))
    L.note("SNP-X1.9.1", "control: NodeValueJSON on ^IVF (allowed) answers", value=str(ok))
    for g, subs in (("^KG", ["out"]), ("^IVG.Ledger", ["head"]), ("^IVGAuditRX18", ["a"])):
        L.refusal("SNP-X1.9.1", f"NodeValueJSON {g} refused",
                  lambda g=g, subs=subs: o.classMethodValue("Graph.KG.Snapshot", "NodeValueJSON", g, json.dumps(subs)),
                  raises("Exception", match="not a vector-index global"),
                  entry="Graph.KG.Snapshot.NodeValueJSON (Native API)")
    for g, subs in (("^IVGAuditRX18", ["a"]), ("^KG", ["rx18probe"])):
        L.refusal("SNP-X1.9.1", f"SetNodeJSON {g} refused",
                  lambda g=g, subs=subs: o.classMethodVoid("Graph.KG.Snapshot", "SetNodeJSON", g, json.dumps(subs),
                                                           json.dumps({"v": "1"})),
                  raises("Exception", match="not a vector-index global"),
                  after=lambda g=g, subs=subs: {"node_defined_after": int(o.isDefined(g, *subs))},
                  entry="Graph.KG.Snapshot.SetNodeJSON (Native API)")


def c_x1_3_probe(L):
    """SNP-X1.3 (context only): a readable namespace saves; the unreadable-table trigger needs a login without SELECT.
    Recorded as an observation (the evidence for X1.3 is the upstream unit test run here)."""
    L.reset()
    seed(L)
    p = ARCH / "x1_3-readable.zip"
    if p.exists():
        p.unlink()
    r = L.eng.save_snapshot(str(p))
    L.note("SNP-X1.3", "context: save_snapshot of a readable namespace writes its archive",
           written=p.exists(), tables=r.get("tables"))


# ------------------------------------------------------------------------------------------------- restore
def c_x2_1(L):
    """SNP-X2.1: restore refused in strict ledger mode (snapshot.py:1095, guard.py:75-80), before the file is read."""
    L.reset()
    seed(L)
    arch = real_archive(L, "x2_1.zip")
    L.reset(ledger=True, strict=True)
    seed_ids = node_ids(L)
    L.refusal("SNP-X2.1", "restore_snapshot in strict ledger mode -> LedgerStrictModeError",
              lambda: L.eng.restore_snapshot(str(arch)), raises("LedgerStrictModeError"),
              allowed=[STATS], entry="engine.restore_snapshot",
              after=lambda: {"rx18_nodes_after": node_ids(L), "before": seed_ids})
    missing = ARCH / "x2_1-does-not-exist.zip"
    L.refusal("SNP-X2.1", "restore_snapshot in strict ledger mode of a missing file -> refused before the file is read",
              lambda: L.eng.restore_snapshot(str(missing)), raises("LedgerStrictModeError"),
              allowed=[STATS], entry="engine.restore_snapshot")
    L.reset()


def c_x2_2(L):
    """SNP-X2.2: restore refused while the caller's own transaction holds a write (snapshot.py:1096-1102)."""
    L.reset()
    seed(L)
    arch = real_archive(L, "x2_2.zip")
    lvl = open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx18:txn')")
    L.note("SNP-X2.2", "setup: caller transaction open", tlevel=lvl)
    L.refusal("SNP-X2.2", "restore_snapshot with a caller write open -> CallerTransactionOpenError",
              lambda: L.eng.restore_snapshot(str(arch)), raises("CallerTransactionOpenError"),
              keep_txn=True, entry="engine.restore_snapshot",
              after=lambda: {"tlevel_after": tlevel(L.c.conn),
                             "caller_row_still_pending": L.c.sql(
                                 "SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'rx18:txn'")[0][0]})
    rollback_all(L.c.conn)
    L.note("SNP-X2.2", "after the caller's rollback the caller's row is gone (it was never committed by restore)",
           rows=L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'rx18:txn'")[0][0])


def c_x2_3(L):
    """SNP-X2.3: an archive of another layout is refused before erase_all (snapshot.py:1113-1129)."""
    L.reset()
    seed(L)
    real = real_archive(L, "x2_3-real.zip")
    for layout in ("flat", "pre-223"):
        bad = craft(real, f"x2_3-{layout}.zip", layout=layout, keep_members=True)
        before = node_ids(L)
        L.refusal("SNP-X2.3", f"replacing restore of an archive with layout {layout!r} -> ValueError, nothing erased",
                  lambda bad=bad: L.eng.restore_snapshot(str(bad)), raises("ValueError", match="layout"),
                  entry="engine.restore_snapshot (merge=False: would erase_all first)",
                  after=lambda before=before: {"rx18_nodes_before": before, "rx18_nodes_after": node_ids(L)})


def c_x2_9(L):
    """SNP-X2.9: an archived row whose column name is not a plain name is refused and counted (snapshot.py:368-378)."""
    L.reset()
    seed(L)
    real = real_archive(L, "x2_9-real.zip")
    bad_key = "node_id) VALUES ('rx18:inj'); --"
    arch = craft(real, "x2_9.zip", sql={"Graph_KG_nodes": [{"graph_id": "", bad_key: "rx18:inj"}]})
    L.refusal("SNP-X2.9", "merge restore of a nodes row with a non-identifier column -> refused, counted",
              lambda: L.eng.restore_snapshot(str(arch), merge=True),
              returns(lambda r: r["failed_rows"].get("Graph_KG.nodes") == 1
                      and r["restored_tables"].get("Graph_KG.nodes") == 0,
                      "failed_rows['Graph_KG.nodes'] == 1 and restored_tables['Graph_KG.nodes'] == 0"),
              entry="engine.restore_snapshot(merge=True)",
              after=lambda: {"rx18_inj_rows": L.c.sql(
                  "SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'rx18:inj'")[0][0]})
    arch2 = craft(real, "x2_9-props.zip",
                  sql={"Graph_KG_rdf_props": [{"s": "rx18:a", "\"key\") VALUES ('x','y','z') --": "k", "val": "v"}]})
    L.refusal("SNP-X2.9", "merge restore of an rdf_props row with a quoted/injected column -> refused, counted",
              lambda: L.eng.restore_snapshot(str(arch2), merge=True),
              returns(lambda r: r["failed_rows"].get("Graph_KG.rdf_props") == 1,
                      "failed_rows['Graph_KG.rdf_props'] == 1"),
              entry="engine.restore_snapshot(merge=True)")


def c_x2_12(L):
    """SNP-X2.12: vector text that is not numbers is refused and counted (snapshot.py:1340, 1359-1363)."""
    L.reset()
    seed(L)
    real = real_archive(L, "x2_12-real.zip")
    bad = "[1,2,3,4]', 4), ('x','rx18:inj', TO_VECTOR('1,2,3,4"
    arch = craft(real, "x2_12.zip", sql={
        "Graph_KG_kg_NodeEmbeddings": [{"graph_id": "rx18g", "node_id": "rx18:a", "emb": bad, "metadata": None}]})
    L.refusal("SNP-X2.12", "merge restore of a node vector whose text is not numbers -> refused, counted",
              lambda: L.eng.restore_snapshot(str(arch), merge=True),
              returns(lambda r: r["failed_rows"].get("Graph_KG.kg_NodeEmbeddings") == 1
                      and r["restored_tables"].get("Graph_KG.kg_NodeEmbeddings") == 0,
                      "failed_rows['Graph_KG.kg_NodeEmbeddings'] == 1, restored 0"),
              entry="engine.restore_snapshot(merge=True)",
              after=lambda: {"node_vectors": L.c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings")[0][0]})
    arch2 = craft(real, "x2_12-edge.zip", sql={
        "Graph_KG_kg_EdgeEmbeddings": [{"s": "rx18:a", "p": "R", "o_id": "rx18:b", "emb": "not numbers"}]})
    L.refusal("SNP-X2.12", "merge restore of an edge vector whose text is not numbers -> refused, counted",
              lambda: L.eng.restore_snapshot(str(arch2), merge=True),
              returns(lambda r: r["failed_rows"].get("Graph_KG.kg_EdgeEmbeddings") == 1,
                      "failed_rows['Graph_KG.kg_EdgeEmbeddings'] == 1"),
              entry="engine.restore_snapshot(merge=True)",
              after=lambda: {"edge_vectors": L.c.sql("SELECT COUNT(*) FROM Graph_KG.kg_EdgeEmbeddings")[0][0]})


def c_x2_13(L):
    """SNP-X2.13: a global not on the restore allow-list is not written; its lines count as failed (1569-1572)."""
    L.reset()
    seed(L)
    real = real_archive(L, "x2_13-real.zip")
    o = L.c.o
    o.kill("IVGAuditRX18")
    lines = [{"k": ["a"], "v": "1"}, {"k": ["b", "c"], "v": "2"}]
    arch = craft(real, "x2_13.zip", globals_={"IVGAuditRX18": lines})
    L.refusal("SNP-X2.13", "merge restore of an archive holding ^IVGAuditRX18 -> not written, 2 lines failed",
              lambda: L.eng.restore_snapshot(str(arch), merge=True),
              returns(lambda r: r["failed_rows"].get("^IVGAuditRX18") == 2 and "IVGAuditRX18" not in r["restored_globals"],
                      "failed_rows['^IVGAuditRX18'] == 2, not in restored_globals"),
              allowed=VERSIONS, entry="engine.restore_snapshot(merge=True)",
              after=lambda: {"IVGAuditRX18_defined": int(o.isDefined("IVGAuditRX18"))})


def c_x2_14(L):
    """SNP-X2.14: a native index that cannot be written stops the restore (stated); F-C1802: a line is swallowed."""
    L.reset()
    seed(L)
    real = real_archive(L, "x2_14-real.zip")
    o = L.c.o
    lines = [{"k": ["rx18x"], "v": "1"}, {"k": [""], "v": "1"}, {"k": ["rx18y", ""], "v": "1"}]
    direct = {}
    for ln in lines[1:]:
        try:
            o.set(ln["v"], "IVG.GraphMode", *ln["k"])
            direct[json.dumps(ln["k"])] = "written"
        except Exception as e:  # noqa: BLE001
            direct[json.dumps(ln["k"])] = f"{type(e).__name__}: {str(e)[:120]}"
    L.note("SNP-X2.14", "setup: the two bad subscripts cannot be written directly over the Native API", direct=direct)
    arch = craft(real, "x2_14.zip", globals_={"IVG.GraphMode": lines})
    L.refusal("SNP-X2.14", "merge restore with ^IVG.GraphMode lines that cannot be written -> RuntimeError",
              lambda: L.eng.restore_snapshot(str(arch), merge=True),
              raises("RuntimeError", match="could not write"),
              allowed=VERSIONS + [r'^\^IVG\.GraphMode\("rx18x"\)$'], entry="engine.restore_snapshot(merge=True)",
              after=lambda: {"graphmode_rx18x": str(o.get("IVG.GraphMode", "rx18x"))})


def c_x5_1(L):
    """SNP-X5.1: every way to load globals keeps to the allow-list; Graph.KG.Snapshot.ImportGlobals (F-1806)."""
    L.reset()
    o = L.c.o
    stamp = time.strftime("%Y%m%dT%H%M%S")
    d = f"/tmp/ivgaudit-rx18-{stamp}/"
    o.set("rx18 scratch", "IVGAuditRX18", "a")
    exported = str(o.classMethodValue("Graph.KG.Snapshot", "ExportGlobals", d, json.dumps([{"name": "^IVGAuditRX18"}])))
    o.kill("IVGAuditRX18")
    L.note("SNP-X5.1", "setup: product ExportGlobals wrote a .gof of the scratch global ^IVGAuditRX18, then killed",
           dir=d, exported=exported, defined_before_import=int(o.isDefined("IVGAuditRX18")))
    try:
        L.refusal("SNP-X5.1", "ImportGlobals of a dir holding ^IVGAuditRX18.gof -> refused (not on the allow-list)",
                  lambda: str(o.classMethodValue("Graph.KG.Snapshot", "ImportGlobals", d)),
                  returns(lambda r: json.loads(r).get("imported") == 0, "{'imported': 0} and nothing written"),
                  entry="Graph.KG.Snapshot.ImportGlobals (Native API)",
                  after=lambda: {"IVGAuditRX18_after": str(o.get("IVGAuditRX18", "a"))})
        # the archive path (restore_snapshot) for the same global, for contrast: refused (SNP-X2.13)
    finally:
        o.kill("IVGAuditRX18")
        r = subprocess.run(["docker", "exec", os.environ["IVG_TEST_CONTAINER"], "rm", "-rf", d],
                           capture_output=True, text=True)
        chk = subprocess.run(["docker", "exec", os.environ["IVG_TEST_CONTAINER"], "ls", "-d", d],
                             capture_output=True, text=True)
        L.note("SNP-X5.1", "cleanup: scratch directory removed", rm_rc=r.returncode, still_there=chk.returncode == 0)


CASES = [("x1_9_1", c_x1_9_1), ("x1_3_probe", c_x1_3_probe), ("x2_1", c_x2_1), ("x2_2", c_x2_2), ("x2_3", c_x2_3),
         ("x2_9", c_x2_9), ("x2_12", c_x2_12), ("x2_13", c_x2_13), ("x2_14", c_x2_14), ("x5_1", c_x5_1)]


def main():
    global ARCH
    args = sys.argv[1:]
    out = "results.json"
    if args[:1] == ["--out"]:
        out, args = args[1], args[2:]
    only = args or None
    with Lane("18") as L:
        ARCH = L.out / "archives"
        ARCH.mkdir(exist_ok=True)
        L.reset()
        L.control()
        run_cases(L, CASES, only)
        L.reset()
        L.c.o.kill("IVGAuditRX18")
        L.note("-", "final: ledger state and rx18 rows after the last reset",
               ledger=json.loads(str(L.c.call("Graph.KG.Ledger", "Meta"))).get("state"),
               rx18_nodes=node_ids(L), graphmode_rx18x=int(L.c.o.isDefined("IVG.GraphMode", "rx18x")))
        L.save(out if not only or out != "results.json" else "results-partial.json")


if __name__ == "__main__":
    main()
