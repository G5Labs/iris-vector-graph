#!/usr/bin/env python3
"""Append one lock-hold record to $LOCKS_LOG (called by tools/locks.sh; read by tools/hygiene_check.py).

    python3 locks_rec.py <event> [key=<json value> ...]

The hold id and the lock come from $LOCKS_HOLD and $LOCKS_KIND. One json.dumps line per call, opened O_APPEND, so
records of concurrent holders do not interleave. Never fails the caller: a write error is printed and ignored.
"""
import json
import os
import sys
import time

try:
    d = {"hold": os.environ["LOCKS_HOLD"], "lock": os.environ["LOCKS_KIND"], "event": sys.argv[1],
         "t": round(time.time(), 3)}
    for kv in sys.argv[2:]:
        k, v = kv.split("=", 1)
        try:
            d[k] = json.loads(v)
        except json.JSONDecodeError:
            d[k] = v
    if d["event"] == "acquired" and "LOCKS_T0" in os.environ:
        d["waited_s"] = round(d["t"] - float(os.environ["LOCKS_T0"]), 3)
    if d["event"] == "acquired":
        d["pgid"] = os.getpgid(int(d.get("pid") or os.getppid()))
    with open(os.environ["LOCKS_LOG"], "a") as f:
        f.write(json.dumps(d) + "\n")
except Exception as e:  # noqa: BLE001 - logging must not change the lock's behaviour
    print(f"locks_rec: {type(e).__name__}: {e}", file=sys.stderr)
