#!/usr/bin/env python3
"""Module 04 (adjacency): live probes of the stated refusals (ADJ kind X) in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_04.py [case ...]

ADJ-X4.7  a second connection holds ^IVG.AdjW exclusively (Native API lock, no transaction); erase_graph, erase_all
          and sync (BuildKG) on the lane's connection must be refused after 5 s with nothing written.
ADJ-X7.10 a second connection holds ^IVG.NKGBuild exclusively; rebuild_nkg (BuildNKG) must wait and be refused after
          NKGBUILDWAIT = 900 s (the case takes about 15 minutes).
ADJ-X9.4  verify_graph with a name that cannot be a graph key is refused before the check runs.
Seed content (graph rx04g and the default graph) is written by the product's own create_node/create_edge outside the
windows; each window's journal must show no net change. Results: $RUN_DIR/refusals/04/results.json.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, run_cases, NS  # noqa: E402

G = "rx04g"


def _locks(name):
    """The lock table entry for `name` (^$LOCK read by a plain `iris session` script; nothing compiled)."""
    import os
    import subprocess
    s = (f' set n="{name}" write !,"LOCK|",$data(^$LOCK(n)),"|",$get(^$LOCK(n,"OWNER")),"|",'
         '$get(^$LOCK(n,"MODE")),! halt\n')
    r = subprocess.run(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session", "IRIS", "-U", NS],
                       input=s, capture_output=True, text=True, timeout=60)
    return [ln for ln in r.stdout.replace("\r", "").split("\n") if ln.startswith("LOCK|")]


def seed(L):
    e = L.eng
    for n in ("rx04:a", "rx04:b", "rx04:c"):
        e.create_node(n, labels=["RX04"], properties={"name": n}, graph=G)
    e.create_edge("rx04:a", "R", "rx04:b", graph=G)
    e.create_edge("rx04:b", "R", "rx04:c", graph=G)
    e.create_node("rx04:d", labels=["RX04"], properties={"name": "d"})
    e.create_node("rx04:e", labels=["RX04"], properties={"name": "e"})
    e.create_edge("rx04:d", "R", "rx04:e")
    L.c.conn.commit()


def content(L):
    c = L.counts()
    c["kg_out_rx04g"] = int(L.c.o.isDefined("KG", "out", str(L.c.call("Graph.KG.GraphKey", "ForIndex", G))) or 0)
    return c


def c_x4_7(L):
    """ADJ-X4.7: erase_graph, erase_all and the adjacency rebuild are refused when the writer lock is not granted."""
    L.reset()
    seed(L)
    before = content(L)
    L.note("ADJ-X4.7", "setup: seeded content", **before)
    holder = L.conn()
    holder.o.lock("", 5, "^IVG.AdjW")   # exclusive on the parent: conflicts with every shared ^IVG.AdjW(g) request
    try:
        L.note("ADJ-X4.7", "setup: second process holds ^IVG.AdjW exclusively", holder_pid=holder.pid,
               lock_table=_locks("^IVG.AdjW"))
        L.refusal("ADJ-X4.7", f"erase_graph({G!r}) while ^IVG.AdjW is held -> refused after 5 s",
                  lambda: L.eng.erase_graph(G), raises(match=r"writer lock for graph .* was not granted in 5 seconds"),
                  entry="IRISGraphEngine.erase_graph -> Graph.KG.Eraser.EraseGraph -> Adjacency.RemoveGraph",
                  after=lambda: {"content_after": content(L), "content_before": before})
        L.refusal("ADJ-X4.7", "erase_all() while ^IVG.AdjW is held -> refused after 5 s",
                  lambda: L.eng.erase_all(), raises(match=r"RemoveAll: the writer lock was not granted in 5 seconds"),
                  entry="IRISGraphEngine.erase_all -> Graph.KG.Eraser.EraseAll -> Adjacency.RemoveAll",
                  after=lambda: {"content_after": content(L), "content_before": before})
        L.refusal("ADJ-X4.7", "sync() (BuildKG) while ^IVG.AdjW is held -> refused after 5 s",
                  lambda: L.eng.sync(), raises(match=r"BeginRebuild: the writer lock was not granted in 5 seconds"),
                  entry="IRISGraphEngine.sync -> Graph.KG.Traversal.BuildKG -> Adjacency.BeginRebuild",
                  after=lambda: {"content_after": content(L), "content_before": before})
    finally:
        holder.o.unlock("", "^IVG.AdjW")
        L.drop(holder)
    # control: with the lock released the same erase goes through (the refusal was the lock, not something else)
    t0 = time.time()
    n = L.eng.erase_graph(G)
    L.note("ADJ-X4.7", "control: erase_graph after the lock is released succeeds", removed=n,
           seconds=round(time.time() - t0, 2), content_after=content(L))


def c_x9_4(L):
    """ADJ-X9.4: verify_graph refuses a name that cannot be a graph key, before the check runs."""
    for bad, why in (("0", 'graph name "0" is reserved'), ("rx04\x01bad", "control"), (5, "graph must be a string")):
        L.refusal("ADJ-X9.4", f"verify_graph({bad!r}) -> ValueError",
                  lambda: L.eng.verify_graph(bad), raises("ValueError", match=why.split()[0]),
                  entry="IRISGraphEngine.verify_graph (validate_graph_name)")


def c_x7_10(L):
    """ADJ-X7.10: a rebuild of the interned snapshot waits for another one and is refused after 900 seconds."""
    L.reset()
    seed(L)
    wait = int(L.c.call("%Dictionary.CompiledParameter", "%ExistsId", "Graph.KG.TraversalBuild||NKGBUILDWAIT") or 0)
    L.note("ADJ-X7.10", "setup: NKGBUILDWAIT parameter compiled", exists=wait)
    holder = L.conn()
    holder.o.lock("", 5, "^IVG.NKGBuild")
    try:
        L.note("ADJ-X7.10", "setup: second process holds ^IVG.NKGBuild exclusively", holder_pid=holder.pid,
               lock_table=_locks("^IVG.NKGBuild"))
        L.refusal("ADJ-X7.10", "rebuild_nkg() while ^IVG.NKGBuild is held -> refused after 900 s",
                  lambda: L.eng.rebuild_nkg(),
                  raises(match=r"another \^NKG build held \^IVG\.NKGBuild for 900 seconds"),
                  entry="IRISGraphEngine.rebuild_nkg -> Graph.KG.Traversal.BuildNKG")
    finally:
        holder.o.unlock("", "^IVG.NKGBuild")
        L.drop(holder)
    secs = L.cases[-1].get("seconds")
    L.note("ADJ-X7.10", "waited", seconds=secs, at_least_900=bool(secs and secs >= 899))
    if secs is not None and secs < 899 and L.cases[-2].get("outcome") == "holds-live":
        L.cases[-2]["outcome"] = "not-refused-as-stated"
    L.reset()


CASES = [("x4_7", c_x4_7), ("x9_4", c_x9_4), ("x7_10", c_x7_10)]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--out=")]
    out = next((a[6:] for a in sys.argv[1:] if a.startswith("--out=")), None)
    only = args or None
    with Lane("04") as L:
        L.reset()
        L.control()
        run_cases(L, CASES, only)
        L.reset()
        L.save(out or ("results.json" if not only else "results-partial.json"))


if __name__ == "__main__":
    main()
