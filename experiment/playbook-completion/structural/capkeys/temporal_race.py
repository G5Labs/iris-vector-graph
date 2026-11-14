#!/usr/bin/env python3
"""Module 05 keys: racing inserts of one temporal key and the bucket count (AUDITD, live).

    locks.sh iris python temporal_race.py OUT.json

keys.py saw count 4 for 3 events after four racing inserts of one (ts, s, p, o) into a bucket that already held two
events; temporal_count.py's single isolated race did not repeat it. Here 12 trials of four connections released
together inserting one key, alternating an empty bucket and a bucket already holding one other event. Oracle:
get_temporal_aggregate(count) over the window equals the number of distinct events get_edges_in_window returns.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from keys import concurrently  # noqa: E402

TS = 1_700_000_100


def main() -> int:
    outp = Path(sys.argv[1])
    res = []
    for t in range(12):
        prefill = t % 2 == 1
        c = lib.conn()
        try:
            lib.reset(c)
            e = lib.engine(c)
            e.create_node("tr:1")
            e.create_node("tr:2")
            if prefill:
                e.create_edge_temporal("tr:1", "R", "tr:2", timestamp=TS - 50)
            c.conn.commit()
            ans = concurrently(4, lambda i, cc, ee: ee.create_edge_temporal("tr:1", "R", "tr:2", timestamp=TS))
            ev = len(e.get_edges_in_window(source="tr:1", predicate="R", start=TS - 100, end=TS + 10))
            cnt = e.get_temporal_aggregate("tr:1", "R", "count", TS - 100, TS + 10)
            r = {"trial": t, "prefilled_bucket": prefill, "answers": [a.get("answer", a.get("error", "")[:80]) for a in ans],
                 "events": ev, "count_aggregate": cnt, "holds": str(cnt) in (str(ev), f"{ev}.0")}
        finally:
            lib.reset(c)
            c.close()
        res.append(r)
        print(json.dumps(r), flush=True)
    lib.dump(outp, {"trials": res, "violations": sum(not r["holds"] for r in res)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
