#!/usr/bin/env python3
"""Gate 5-hygiene (playbook §5: one heavy job at a time, time caps, disk floor, wait timeouts, stop by PID), checked
mechanically on the hold log tools/locks.sh writes ($RUN_DIR/locks/holds.jsonl, one JSON object per event).

    python3 tools/hygiene_check.py [--log PATH] [--since EPOCH|ISO] [--cap-seconds 10800] [--json OUT]
    python3 tools/hygiene_check.py --self-test

Holds are grouped by their hold id; only holds whose request is at or after --since are checked. Problems:
  H1 one holder at a time   two acquired holds of the same lock overlap (a hold ends at its released record; the
                            next holder may acquire up to SLACK seconds before that record, which is written after the
                            holder exits and the lock is free)
  H2 released               an acquired hold has no released record and its holder pid is not alive
  H3 time cap               a hold was (or is) held longer than the cap
  H4 disk floor             a request below its disk floor that was not refused; or a request with no disk reading
  H5 stop by pid            an acquired record without an integer pid and process group
  H6 wait timeout           a wait longer than its cap (+ SLACK), or a request with no outcome (acquired, refused,
                            timeout) whose requesting pid is not alive
  H7 malformed              a line that is not a JSON object with hold, lock, event and t
What this cannot see: a job that never went through locks.sh (incidents/ records the known lapses before the log).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

SLACK = 5.0


def alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True


def parse_since(s: str | None) -> float:
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load(path: Path) -> tuple[list, list]:
    recs, bad = [], []
    for n, line in enumerate(path.read_text().splitlines(), 1) if path.exists() else []:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if not (isinstance(r, dict) and all(k in r for k in ("hold", "lock", "event", "t"))):
                raise ValueError("missing keys")
            recs.append(r)
        except (ValueError, json.JSONDecodeError) as e:
            bad.append(f"H7 line {n}: {e}")
    return recs, bad


def check(recs: list, since: float = 0.0, cap: float = 10800.0, now: float | None = None,
          is_alive=alive) -> dict:
    now = time.time() if now is None else now
    holds: dict = {}
    for r in recs:
        holds.setdefault(r["hold"], {})[r["event"]] = r
    probs = []
    checked = {k: v for k, v in holds.items() if "request" in v and v["request"]["t"] >= since}
    intervals: dict = {}
    stats = {"holds": len(checked), "by_lock": {}, "refused": 0, "timeouts": 0, "max_held_s": 0.0,
             "max_wait_s": 0.0, "min_disk_gb": None, "still_held": 0}
    for hid, h in sorted(checked.items(), key=lambda kv: kv[1]["request"]["t"]):
        req = h["request"]
        lock = req["lock"]
        stats["by_lock"][lock] = stats["by_lock"].get(lock, 0) + 1
        disk, floor = req.get("disk_gb"), req.get("floor_gb")
        if not isinstance(disk, (int, float)) or not isinstance(floor, (int, float)):
            probs.append(f"H4 {hid}: request without a disk reading or floor")
        else:
            stats["min_disk_gb"] = disk if stats["min_disk_gb"] is None else min(stats["min_disk_gb"], disk)
            if disk < floor and "refused" not in h:
                probs.append(f"H4 {hid}: {disk} GB below the floor {floor} GB and not refused")
        if "refused" in h:
            stats["refused"] += 1
            if "acquired" in h:
                probs.append(f"H4 {hid}: refused and acquired")
            continue
        if "timeout" in h:
            stats["timeouts"] += 1
            continue
        acq = h.get("acquired")
        if acq is None:
            if not is_alive(req.get("pid")):
                probs.append(f"H6 {hid}: request with no outcome and its pid {req.get('pid')} is gone")
            continue
        w = float(acq.get("waited_s") or 0.0)
        stats["max_wait_s"] = max(stats["max_wait_s"], w)
        if w > float(req.get("wait_cap_s") or 10800) + SLACK:
            probs.append(f"H6 {hid}: waited {w:.0f} s, over its cap {req.get('wait_cap_s')} s")
        if not isinstance(acq.get("pid"), int) or not isinstance(acq.get("pgid"), int):
            probs.append(f"H5 {hid}: acquired without an integer pid and process group")
        rel = h.get("released")
        if rel is None:
            if is_alive(acq.get("pid")):
                end = now
                stats["still_held"] += 1
            else:
                probs.append(f"H2 {hid}: acquired, never released, holder pid {acq.get('pid')} is gone")
                end = None
        else:
            end = rel["t"]
        if end is not None:
            held = end - acq["t"]
            stats["max_held_s"] = max(stats["max_held_s"], round(held, 3))
            if held > cap:
                probs.append(f"H3 {hid}: held {held:.0f} s, over the cap {cap:.0f} s ({lock}: {req.get('cmd')})")
            intervals.setdefault(lock, []).append((acq["t"], end, hid))
    for lock, iv in intervals.items():
        iv.sort()
        for (a0, a1, ha), (b0, b1, hb) in zip(iv, iv[1:]):
            if b0 < a1 - SLACK:
                probs.append(f"H1 {lock}: {hb} acquired at {b0:.3f} while {ha} held it until {a1:.3f}")
    return {"since": since, "cap_s": cap, "slack_s": SLACK, "stats": stats, "problems": probs}


def self_test() -> int:
    t0 = 1_800_000_000.0

    def hold(h, lock, t, held, wait=0.0, rc=0, pid=None, disk=100, floor=20, events=("request", "acquired", "released")):
        pid = pid if pid is not None else 900000 + abs(hash(h)) % 50000
        out = []
        for e in events:
            if e == "request":
                out.append({"hold": h, "lock": lock, "event": e, "t": t, "pid": pid, "disk_gb": disk, "floor_gb": floor,
                            "wait_cap_s": 10800, "cmd": ["x"]})
            elif e == "acquired":
                out.append({"hold": h, "lock": lock, "event": e, "t": t + wait, "pid": pid + 1, "pgid": pid,
                            "waited_s": wait})
            elif e == "released":
                out.append({"hold": h, "lock": lock, "event": e, "t": t + wait + held, "rc": rc})
            else:
                out.append({"hold": h, "lock": lock, "event": e, "t": t + wait})
        return out

    base = (hold("a", "heavy", t0, 100) + hold("b", "heavy", t0 + 50, 10, wait=50.5)
            + hold("c", "iris", t0, 30) + hold("d", "iris", t0 + 1, 0, wait=1.0, events=("request", "timeout"))
            + hold("e", "iris", t0 + 2, 0, disk=10, events=("request", "refused")))
    dead = lambda pid: False  # noqa: E731
    ok = True
    r = check(base, now=t0 + 1000, is_alive=dead)
    print(f"unmutated: {len(r['problems'])} problems {r['problems'][:3]}")
    ok &= not r["problems"]
    mutants = {
        "H1 overlap": base + hold("f", "heavy", t0 + 60, 5),
        "H2 never released": base + hold("g", "iris", t0 + 200, 5, events=("request", "acquired")),
        "H3 over the cap": base + hold("h", "heavy", t0 + 300, 20000),
        "H4 below floor, not refused": base + hold("i", "iris", t0 + 400, 1, disk=5),
        "H4 no disk reading": base + [dict(x, disk_gb=None) if x["event"] == "request" else x
                                      for x in hold("j", "iris", t0 + 500, 1)],
        "H5 no pid": base + [dict(x, pid=None) if x["event"] == "acquired" else x for x in hold("k", "iris", t0 + 600, 1)],
        "H6 no outcome": base + hold("l", "iris", t0 + 700, 0, events=("request",)),
        "H6 wait over cap": base + hold("m", "iris", t0 + 800, 1, wait=20000),
    }
    for name, recs in mutants.items():
        got = check(recs, now=t0 + 40000, is_alive=dead)["problems"]
        hit = any(p.startswith(name.split()[0]) for p in got)
        ok &= hit
        print(f"{'caught' if hit else 'MISSED'} {name}: {got[:2]}")
    # a holder still running is not a problem; with is_alive true the open hold counts as still held
    r = check(base + hold("n", "iris", t0 + 900, 0, events=("request", "acquired")), now=t0 + 950,
              is_alive=lambda pid: True)
    ok &= not r["problems"] and r["stats"]["still_held"] == 1
    print(f"live holder: problems {r['problems']}, still_held {r['stats']['still_held']}")
    # malformed line
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "holds.jsonl"
        p.write_text(json.dumps(base[0]) + "\nnot json\n")
        _, bad = load(p)
        ok &= len(bad) == 1
        print(f"malformed lines caught: {len(bad)}")
    print("self-test", "pass" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    ap.add_argument("--since")
    ap.add_argument("--cap-seconds", type=float, default=10800.0)
    ap.add_argument("--json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    log = Path(a.log or Path(os.environ["RUN_DIR"]) / "locks" / "holds.jsonl")
    recs, bad = load(log)
    r = check(recs, parse_since(a.since), a.cap_seconds)
    r["problems"] = bad + r["problems"]
    r["log"] = str(log)
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1))
    print(json.dumps(r["stats"]))
    for p in r["problems"]:
        print("PROBLEM", p)
    print(f"hygiene: {len(r['problems'])} problem(s) over {r['stats']['holds']} holds")
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
