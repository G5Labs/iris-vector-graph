"""HD-0402 probe: is a second adjacency rebuild admitted while one is in progress?

Contract cited:
- docs/ADMIN_GUIDE.md:1049-1050: "`engine.sync()` rebuilds `^KG` from the rows, then `^NKG` from `^KG` ... One rebuild
  runs at a time (lock `^IVG.NKGBuild`)."
- TraversalBuild.cls:281-283 (BuildNKG): "One build at a time: the lock ^IVG.NKGBuild ... taking [^IVG.AdjW] shared
  would not exclude a second build."
- TraversalBuild.cls:34-37 (BuildKG) takes only Adjacency.BeginRebuild's shared lock ^IVG.AdjW#"S".

Deterministic two-connection interleaving with the pin's own lock calls (no race, no timing guess):
1. Connection A calls Graph.KG.Adjacency.BeginRebuild(), which leaves A in exactly the lock state a running BuildKG
   holds from its start to EndRebuild. Connection B then runs Graph.KG.Traversal.BuildKG() (the first half of
   sync()). Admitted and finished while A holds it -> ^KG rebuilds are NOT serialized (option A, "allowed").
   Blocked/refused -> serialized (options B/C).
2. Connection A takes ^IVG.NKGBuild exclusively (what BuildNKG holds while it rewrites). Connection B runs
   Graph.KG.Traversal.BuildNKG() (the second half of sync()) in a thread. Still running after 3 s and finishing only
   after A releases -> ^NKG rebuilds are serialized, as the ADMIN_GUIDE sentence literally says.
Readings: the ADMIN_GUIDE sentence read narrowly (only ^NKG serialized) passes if (2) blocks; read broadly (sync as a
whole serialized) it would also need (1) to block.
Restores: A releases both locks; the rebuilds are derived from the rows; the probe erases its own graph at the end.
"""
from __future__ import annotations

import threading
import time

import _common as C

G = "ia-0402"


def main() -> None:
    a = C.conn()
    b = C.conn()
    e = C.engine(a)
    try:
        e.erase_graph(G)
        for n in ("ia0402:a", "ia0402:b", "ia0402:c"):
            e.create_node(n, graph=G)
        e.create_edge("ia0402:a", "R", "ia0402:b", graph=G)
        e.create_edge("ia0402:b", "R", "ia0402:c", graph=G)
        C.obs(step="setup", indexed=int(a.call("Graph.KG.Adjacency", "Indexed")), pid_a=a.pid, pid_b=b.pid)

        # Part 1: BuildKG while another process holds the rebuild lock state
        st = a.call("Graph.KG.Adjacency", "BeginRebuild")
        C.obs(step="A.BeginRebuild", status=str(st))
        t0 = time.time()
        err = None
        try:
            stb = b.call("Graph.KG.Traversal", "BuildKG")
        except Exception as ex:  # noqa: BLE001
            stb, err = None, str(ex)
        kg_secs = round(time.time() - t0, 3)
        C.obs(step="B.BuildKG-while-A-rebuilding", status=str(stb), error=err, seconds=kg_secs)
        a.call("Graph.KG.Adjacency", "EndRebuild", 0)
        kg_admitted = err is None and str(stb).strip() == "1"

        # Part 2: BuildNKG while another process holds ^IVG.NKGBuild
        a.o.lock("", 5, "^IVG.NKGBuild")
        C.obs(step="A.lock-NKGBuild")
        box = {}

        def run_b():
            t = time.time()
            try:
                box["status"] = str(b.call("Graph.KG.Traversal", "BuildNKG"))
            except Exception as ex:  # noqa: BLE001
                box["error"] = str(ex)
            box["seconds"] = round(time.time() - t, 3)

        th = threading.Thread(target=run_b, daemon=True)
        th.start()
        time.sleep(3.0)
        blocked_while_held = th.is_alive()
        C.obs(step="B.BuildNKG-after-3s", still_waiting=blocked_while_held)
        a.o.unlock("", "^IVG.NKGBuild")
        th.join(timeout=120)
        C.obs(step="B.BuildNKG-done", **box, joined=not th.is_alive())
        nkg_serialized = blocked_while_held and box.get("seconds", 0) >= 3.0 and "error" not in box

        vg = e.verify_graph(G)
        C.obs(step="verify_graph", ok=vg.get("ok") if isinstance(vg, dict) else vg)
        C.obs(step="summary", kg_rebuild_admitted_concurrently=kg_admitted, nkg_rebuild_serialized=nkg_serialized)
        if nkg_serialized and kg_admitted:
            C.verdict("pass", "ADMIN_GUIDE's literal claim holds for ^NKG (serialized by ^IVG.NKGBuild); the ^KG half of "
                      "sync() is admitted while another rebuild holds its lock state (not serialized)")
        elif nkg_serialized:
            C.verdict("pass", "both halves serialized")
        else:
            C.verdict("fail", "^NKG rebuild not serialized by ^IVG.NKGBuild")
    finally:
        try:
            a.o.releaseAllLocks()
        except Exception:  # noqa: BLE001
            pass
        try:
            e.erase_graph(G)
        finally:
            a.close()
            b.close()


if __name__ == "__main__":
    main()
