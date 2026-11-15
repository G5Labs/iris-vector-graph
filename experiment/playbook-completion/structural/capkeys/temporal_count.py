#!/usr/bin/env python3
"""Module 05 keys: which write makes the bucket count exceed the events (AUDITD, live).

    locks.sh iris python temporal_count.py OUT.json

keys.py (05-temporal-keys) saw a count aggregate of 4 for 3 distinct (ts, s, p, o) events. Each variant here runs
alone from an empty namespace: (a) the same insert twice, (b) the same upsert twice, (c) four racing inserts of one
key, (d) one insert then one upsert of the same key. Oracle: get_temporal_aggregate(count) equals the number of
distinct events get_edges_in_window returns (the temporal index is keyed by (graph, ts, s, p, o)).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from keys import call, concurrently  # noqa: E402

TS = 1_700_000_100


def variant(name, fn):
    c = lib.conn()
    try:
        lib.reset(c)
        e = lib.engine(c)
        e.create_node("tc:1")
        e.create_node("tc:2")
        c.conn.commit()
        steps = fn(e)
        c.conn.commit()
        ev = len(e.get_edges_in_window(source="tc:1", predicate="R", start=TS - 10, end=TS + 10))
        cnt = e.get_temporal_aggregate("tc:1", "R", "count", TS - 10, TS + 10)
        r = {"variant": name, "steps": steps, "events": ev, "count_aggregate": cnt, "holds": str(cnt) in (str(ev), f"{ev}.0")}
    finally:
        lib.reset(c)
        c.close()
    print(json.dumps(r, default=str), flush=True)
    return r


def main() -> int:
    outp = Path(sys.argv[1])
    ins = lambda e: e.create_edge_temporal("tc:1", "R", "tc:2", timestamp=TS)  # noqa: E731
    ups = lambda e: e.create_edge_temporal("tc:1", "R", "tc:2", timestamp=TS, upsert=True)  # noqa: E731
    res = [variant("insert x2", lambda e: [call(lambda: ins(e)), call(lambda: ins(e))]),
           variant("upsert x2", lambda e: [call(lambda: ups(e)), call(lambda: ups(e))]),
           variant("insert then upsert", lambda e: [call(lambda: ins(e)), call(lambda: ups(e))]),
           variant("4 racing inserts", lambda e: concurrently(4, lambda i, cc, ee: ins(ee))),
           variant("insert at t, then upsert x2 at t+100 (keys.py sequence)",
                   lambda e: [call(lambda: ins(e)), call(lambda: e.create_edge_temporal("tc:1", "R", "tc:2", timestamp=TS + 5, upsert=True)),
                              call(lambda: e.create_edge_temporal("tc:1", "R", "tc:2", timestamp=TS + 5, upsert=True))]),
           variant("insert at t, then insert at t+5", lambda e: [call(lambda: ins(e)),
                   call(lambda: e.create_edge_temporal("tc:1", "R", "tc:2", timestamp=TS + 5))])]
    lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
