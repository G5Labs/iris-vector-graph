#!/usr/bin/env python3
"""Module 18 capacity: client memory of save_snapshot / restore_snapshot against content size (AUDITD, live).

    locks.sh iris python snapshot_mem.py OUT.json

For N in (2,000, 8,000, 32,000) edges (N/2 nodes, one property each, default graph): peak Python allocation
(tracemalloc) of save_snapshot and of a replacing restore_snapshot, the archive's size, and a content check after
the restore (row counts and the key/FK oracles). save_snapshot builds the archive in memory
(iris_vector_graph/_engine/snapshot.py:862-1041) and restore reads every member into memory (:1103-1110); the probe
measures how the peak grows with N (a bound would show as a flat peak).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from keys import keys_check  # noqa: E402
from fk import fk_check  # noqa: E402


def measure(f):
    tracemalloc.start()
    t0 = time.time()
    r = f()
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return r, round(peak / 1e6, 1), round(time.time() - t0, 1)


def main() -> int:
    outp = Path(sys.argv[1])
    res = []
    for n in (2000, 8000, 32000):
        c = lib.conn()
        try:
            lib.reset(c)
            e = lib.engine(c)
            k = n // 2
            e.bulk_create_nodes([{"id": f"sm:{i}", "labels": ["A"], "properties": {"t": "x" * 40}} for i in range(k)])
            e.bulk_create_edges([{"source_id": f"sm:{i % k}", "predicate": f"R{i // k}", "target_id": f"sm:{(i * 7 + 1) % k}"}
                                 for i in range(n)])
            c.conn.commit()
            before = lib.counts(c)
            with tempfile.TemporaryDirectory() as d:
                p = str(Path(d) / "s.zip")
                _r, save_peak, save_s = measure(lambda: e.save_snapshot(p))
                size = os.path.getsize(p)
                lib.reset(c)
                rr, rest_peak, rest_s = measure(lambda: lib.engine(c).restore_snapshot(p))
                c.conn.commit()
            after = lib.counts(c)
            r = {"edges": n, "nodes": k, "archive_bytes": size, "save_peak_MB": save_peak, "save_secs": save_s,
                 "restore_peak_MB": rest_peak, "restore_secs": rest_s, "counts_before": before, "counts_after": after,
                 "content_equal_counts": before == after, "key_violations": keys_check(c)["violations"],
                 "fk_violations": fk_check(c)["violations"]}
        finally:
            lib.reset(c)
            c.close()
        res.append(r)
        print(json.dumps(r), flush=True)
        lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
