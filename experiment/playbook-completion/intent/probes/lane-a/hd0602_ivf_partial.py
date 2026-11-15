"""HD-0602 probe: does a reader see a half-built IVF index, and does a stopped build leave a partial one?

Contracts cited:
- vector.py ivf_build (1880-2027): Graph.KG.IVFIndex.Build (Kill ^IVF(name), IVFIndex.cls:8), then one AddBatch call
  per build_batch_size rows, then FinalizeIndex, each a separate server call with no lock and no transaction;
  docstring "writes the index name ..., replacing one of that name".
- ivf_search docstring: "Returns up to k (node_id, score) tuples, best first, or [] when the index does not exist."
- No spec/ADR states a reader or interruption contract for IVF/VecIndex/PLAID builds. The only maintainer precedent
  for a rebuilt derived index is ^NKG ("a reader during the rebuild never sees it empty", ADMIN_GUIDE:1049-1050).
- Working assumption (decisions.md HD-0602): readers see a complete published index or a clear unavailable result.

Oracle (real product code, two connections): build a complete index of N vectors (reader sees N). Then rebuild with
the same public call (ivf_build, build_batch_size=1) on connection A in a thread while connection B searches with
k >= N, nprobe = nlist. Any search answering 0 < n < N without error, or [] while the index existed with N before, is
a visible partial state (as-built option (c)); only N or an explicit unavailable/error result fits the working
assumption. Then start the same rebuild again in a child process and kill it (SIGKILL) after some batches: the index
left behind answering fewer than N with no error is a partial index left by a stopped build.
Cleanup: drops its own index; erases its own graph.
"""
from __future__ import annotations

import random
import signal
import subprocess
import sys
import threading
import time

import _common as C

G = "ia-0602"
IVF = "ia0602ivf"
N = 300
NLIST = 4


def main() -> None:
    a = C.conn()
    b = C.conn()
    ea, eb = C.engine(a), C.engine(b)
    rnd = random.Random(602)
    try:
        ea.erase_graph(G)
        ea.ivf_drop(IVF)
        for i in range(N):
            nid = f"ia0602:n{i:04d}"
            ea.create_node(nid, graph=G)
            ea.store_embedding(nid, [rnd.uniform(-1, 1) for _ in range(4)], graph=G)
        q = [0.3, -0.2, 0.5, 0.1]
        ea.ivf_build(IVF, nlist=NLIST, graph=G)
        full = len(eb.ivf_search(IVF, q, k=N + 10, nprobe=NLIST))
        C.obs(step="complete-index", reader_sees=full)

        # 1. reader during a rebuild
        seen = []
        done = threading.Event()
        err = {}

        def build():
            try:
                ea.ivf_build(IVF, nlist=NLIST, graph=G, build_batch_size=1)
            except Exception as ex:  # noqa: BLE001
                err["build"] = str(ex)
            done.set()

        th = threading.Thread(target=build, daemon=True)
        th.start()
        t0 = time.time()
        while not done.is_set() and time.time() - t0 < 120:
            try:
                seen.append(len(eb.ivf_search(IVF, q, k=N + 10, nprobe=NLIST)))
            except Exception as ex:  # noqa: BLE001
                seen.append(f"error:{type(ex).__name__}")
        th.join(timeout=30)
        partial = [s for s in seen if isinstance(s, int) and s < full]
        C.obs(step="reader-during-rebuild", searches=len(seen), distinct_counts=sorted({str(s) for s in seen})[:20],
              partial_answers=len(partial), min_seen=min([s for s in seen if isinstance(s, int)], default=None),
              build_error=err.get("build"), after=len(eb.ivf_search(IVF, q, k=N + 10, nprobe=NLIST)))

        # 2. a stopped rebuild: the builder's process is killed (SIGKILL) between AddBatch calls
        child = subprocess.Popen([sys.executable, __file__, "--build-child"], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        t0 = time.time()
        n = full
        while time.time() - t0 < 60 and child.poll() is None:
            n = len(eb.ivf_search(IVF, q, k=N + 10, nprobe=NLIST))
            if 0 < n < full // 2:
                break
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=30)
        time.sleep(1.0)
        left = len(eb.ivf_search(IVF, q, k=N + 10, nprobe=NLIST))
        info = eb._iris_obj().classMethodValue("Graph.KG.IVFIndex", "Info", IVF)
        C.obs(step="stopped-rebuild", child_returncode=child.returncode, seen_when_killed=n,
              reader_sees_after_stop=left, info=str(info))

        if partial or left < full:
            C.verdict("fail", f"partial IVF index visible to a reader during rebuild ({len(partial)} of {len(seen)} "
                      f"searches answered < {full}) and a stopped rebuild left {left} of {full} with no error")
        else:
            C.verdict("pass", "no partial state observed")
    finally:
        try:
            eb.ivf_drop(IVF)
            eb.erase_graph(G)
        finally:
            a.close()
            b.close()


def build_child() -> None:
    c = C.conn()
    C.engine(c).ivf_build(IVF, nlist=NLIST, graph=G, build_batch_size=1)
    c.close()


if __name__ == "__main__":
    if "--build-child" in sys.argv:
        build_child()
    else:
        main()
