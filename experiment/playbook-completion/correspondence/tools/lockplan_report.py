#!/usr/bin/env python3
"""Summarize lockplan.json: where X waited (mapped to .cls lines), what it held, what it wrote before the release,
and what it still held after the operation and after its own COMMIT.

    python lockplan_report.py LOCKPLAN.json [--json OUT]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import where  # noqa: E402


def held_by(rows, pid):
    return sorted({f"{r['ref']} {r['mode']}{' ' + r['flags'] if r.get('flags') not in (None, 'None', '') else ''}"
                   for r in rows if r.get("owner") == pid})


def summarize(r):
    x = r["pids"]["X"]
    waits = [s for s in r.get("x_state_while_held", []) if s.get("state")]
    last = waits[-1] if waits else {}
    locs = sorted({s.get("at") for s in waits if s.get("at")})
    mapped = {loc: where.to_cls(loc) for loc in locs}
    return {
        "probe": r["probe"], "expect": r["expect"], "held_by_probe": r["lock"] and f"{r['lock'][0]}{tuple(r['lock'][1])} "
        f"{'shared' if r['mode'] == 'S' else 'exclusive'} {r['hold_s']} s",
        "x_result": r["x"], "x_states": sorted({s.get("state") for s in waits}),
        "x_wait_locations": {loc: (f"{m[0]}:{m[1]}" if m else None) for loc, m in mapped.items()},
        "x_in_transaction_while_waiting": sorted({s.get("in_txn") for s in waits}),
        "x_locks_while_held": held_by(r.get("locks_while_held", []), x),
        "x_writes_before_release": sorted({rec["g"].split("(")[0] for rec in r.get("x_records_before_release", [])}),
        "x_n_writes_before_release": len(r.get("x_records_before_release", [])),
        "x_locks_after_op": held_by(r.get("locks_after_op", []), x),
        "x_locks_after_outer_commit": held_by(r.get("locks_after_outer_commit", []), x) if "locks_after_outer_commit" in r else None,
        "x_adjnolock_sets": r.get("x_adjnolock", []),
        "x_transactions": r.get("x_transactions"),
        "x_globals_written": r.get("x_record_globals"),
        "last_state": last,
    }


def main() -> int:
    data = json.loads(Path(sys.argv[1]).read_text())
    out = [summarize(r) for r in data]
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1, default=str))
    for s in out:
        print(json.dumps(s, default=str)[:1400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
