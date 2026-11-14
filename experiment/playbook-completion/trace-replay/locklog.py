"""Lock logs for playbook §3.7 "database statement/lock log checked against the lock plan".

IRIS keeps no lock event log, so two observations are combined (nothing is compiled; both read the lock table from a
plain `iris session` script in the lane's namespace, as traces/journal.py reads the journal):

1. `poll(names, seconds)`: a tight server-side loop over the planned lock names (exact references such as
   ^IVG.AdjW("tr04g") or ^IVG.Ledger("head")), reading ^$LOCK(name,"OWNER"/"MODE"/"COUNTS") and writing a line only
   when the entry changes, with $ZHOROLOG time; plus a slow full scan of ^$LOCK (about 16 scans/s on this
   container) every `scan_every` seconds that records any other lock whose name contains one of `scan_match` (so an
   unplanned lock taken long enough is seen too).
2. `block_probe(...)`: a probe process holds one planned lock in a conflicting mode; the operation runs in another
   process; while it is held the operation's process state (State, CurrentLineAndRoutine) and the lock table rows
   it owns are read; the probe then releases. A wait at a line shows the operation requests that lock there, and the
   locks it already holds at that moment were taken before it.

The workloads run the module's real entry points in one process (`X`) while the poller runs; the log is analysed per
owner pid: which planned names and modes were held, and in which order (first appearance within each episode
between two moments at which X holds none of the polled locks).
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional

import trlib
from iris_conn import Conn

NS = trlib.NS


def _quote(ref: str) -> str:
    return ref.replace('"', '""')


def poll_script(names: List[str], seconds: float, scan_every: float, scan_match: List[str]) -> str:
    sets = " ".join(f'set nm({i})="{_quote(n)}"' for i, n in enumerate(names, 1)) or 'set nm=""'
    if not scan_every:
        scan_every = 10 ** 9   # fast poll only (a separate scan-only poller covers unplanned names)
    match = " ".join(f'set mt({i})="{_quote(m)}"' for i, m in enumerate(scan_match, 1))
    body = (
        f' {sets} {match} set nn={len(names)},nmt={len(scan_match)},t0=$zh,last=t0,k=0,ns=0'
        ' write !,"T0|",t0,!'
        ' for { set k=k+1 for i=1:1:nn { set n=nm(i),v=""'
        '  if $data(^$LOCK(n)) { set v=$get(^$LOCK(n,"OWNER"))_"~"_$get(^$LOCK(n,"MODE"))_"~"_$get(^$LOCK(n,"COUNTS"))_"~"_$get(^$LOCK(n,"FLAGS")) }'
        '  if v'
        "=$get(prev(i)) { continue } set prev(i)=v write \"P|\",$zh-t0,\"|\",i,\"|\",v,! }"
        f'  if ($zh-last)>{scan_every} {{ set last=$zh,ns=ns+1,n="",line="" for {{ set n=$order(^$LOCK(n)) quit:n=""'
        '   set hit=0 for j=1:1:nmt { if n[mt(j) { set hit=1 quit } } continue:\'hit'
        '   set line=line_$zcvt(n,"O","JSON")_"~"_$get(^$LOCK(n,"OWNER"))_"~"_$get(^$LOCK(n,"MODE"))_"~"_$get(^$LOCK(n,"COUNTS"))_";" }'
        '   if line\'=$get(prevscan) { set prevscan=line write "S|",$zh-t0,"|",line,! } }'
        f'  quit:($zh-t0)>{seconds} }}'
        ' write "END|",k,"|",ns,! halt'
    )
    return body + "\n"


class Poller:
    """Runs poll_script in a background `iris session` (one licence) and parses its output."""

    def __init__(self, names: List[str], seconds: float, scan_every: float = 0.25,
                 scan_match: Optional[List[str]] = None):
        self.names, self.seconds = names, seconds
        self.scan_match = scan_match or ["IVG", "KG", "t52S", "Graph"]
        self.script = poll_script(names, seconds, scan_every, self.scan_match)
        self.out = b""
        self.proc = None

    def start(self):
        self.proc = subprocess.Popen(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session",
                                      "IRIS", "-U", NS], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        self.proc.stdin.write(self.script.encode())
        self.proc.stdin.close()
        self.proc.stdin = None   # communicate() must not flush a closed pipe
        time.sleep(0.3)
        return self

    def join(self, timeout: float = 120) -> Dict:
        self.out, err = self.proc.communicate(timeout=timeout)
        text = self.out.decode("utf-8", "replace").replace("\r", "")
        events, scans, end = [], [], None
        for line in text.split("\n"):
            if line.startswith("P|"):
                _, t, i, v = line.split("|", 3)
                owner, mode, counts, flags = (v.split("~") + ["", "", "", ""])[:4] if v else ("", "", "", "")
                events.append({"t": float(t), "name": self.names[int(i) - 1], "owner": owner, "mode": mode,
                               "counts": counts, "flags": flags})
            elif line.startswith("S|"):
                _, t, rest = line.split("|", 2)
                rows = []
                for item in rest.split(";"):
                    if not item:
                        continue
                    parts = item.split("~")
                    rows.append({"name": json.loads('"' + parts[0] + '"') if parts[0] else "",
                                 "owner": parts[1] if len(parts) > 1 else "", "mode": parts[2] if len(parts) > 2 else "",
                                 "counts": parts[3] if len(parts) > 3 else ""})
                scans.append({"t": float(t), "rows": rows})
            elif line.startswith("END|"):
                _, k, ns = line.split("|")
                end = {"iterations": int(k), "scans": int(ns)}
        if end is None:
            raise RuntimeError("poller did not finish: " + text[-800:])
        return {"names": self.names, "events": events, "scans": scans, "end": end,
                "rate_per_s": round(end["iterations"] / max(self.seconds, 1e-9))}


def episodes(log: Dict, owner: str) -> List[List[Dict]]:
    """Per owner: maximal runs of polled-lock events between moments at which the owner holds none of them."""
    held: Dict[str, Dict] = {}
    out: List[List[Dict]] = []
    cur: List[Dict] = []
    for e in log["events"]:
        if e["owner"] == owner and e["mode"] != "":
            if e["name"] not in held:
                cur.append({"name": e["name"], "mode": e["mode"], "t": e["t"], "counts": e["counts"]})
            held[e["name"]] = e
        elif e["name"] in held and e["owner"] != owner:
            del held[e["name"]]
            if not held and cur:
                out.append(cur)
                cur = []
    if cur:
        out.append(cur)
    return out


def summarize(log: Dict, owner: str) -> Dict:
    eps = episodes(log, owner)
    seen = sorted({(x["name"], x["mode"]) for ep in eps for x in ep})
    orders = sorted({tuple(x["name"] for x in ep) for ep in eps})
    others = sorted({(r["name"], r["mode"]) for s in log["scans"] for r in s["rows"] if r["owner"] == owner})
    return {"episodes": len(eps), "held": [list(x) for x in seen], "orders": [list(o) for o in orders],
            "scan_rows_of_owner": [list(x) for x in others], "poll_rate_per_s": log["rate_per_s"]}


def run_workload(names: List[str], seconds: float, work: Callable[[Conn, float], Dict], setup=None,
                 scan: bool = True) -> Dict:
    """Start a fast poller over `names` and (scan=True) a separate full-scan poller, run work(conn, deadline) in one
    connection until the deadline, join both, summarise for the work connection's pid."""
    x = Conn(NS)
    try:
        if setup:
            setup(x)
        p = Poller(names, seconds + 1.0, scan_every=0).start()
        q = Poller([], seconds + 1.0, scan_every=0.05).start() if scan else None
        t0 = time.time()
        info = work(x, t0 + seconds)
        log = p.join(timeout=seconds + 120)
        if q is not None:
            log["scans"] = q.join(timeout=seconds + 120)["scans"]
        res = {"pid": x.pid, "work": info, "log": log, "summary": summarize(log, x.pid)}
        return res
    finally:
        x.close()


def lock_rows(obs: Conn, pid: Optional[str] = None) -> List[Dict]:
    rows = obs.sql("SELECT * FROM %SYS.LockQuery_List()")
    out = []
    for r in rows:
        r = [None if v is None else str(v) for v in r]
        if pid is not None and r[1] != pid:
            continue
        if any(m in (r[6] or "") for m in ("IVG", "KG", "t52S", "Graph")):
            out.append({"owner": r[1], "mode": r[2], "flags": r[3], "counts": r[4], "ref": r[6]})
    return out


def proc_state(obs: Conn, pid: str) -> Dict:
    r = obs.sql("SELECT State, CurrentLineAndRoutine, InTransaction FROM %SYS.ProcessQuery WHERE Pid = ?", pid)
    return {"state": str(r[0][0]), "at": str(r[0][1]), "in_txn": str(r[0][2])} if r else {}


def block_probe(lock: List, mode: str, op: Callable[[Conn], object], hold: float = 3.0, setup=None,
                nested: bool = False) -> Dict:
    """P holds `lock` = [global, subs...] in `mode` ("E" exclusive, "S" shared) while X runs op(X) in a thread."""
    if setup:
        c = Conn(NS)
        try:
            setup(c)
            c.conn.commit()
        finally:
            c.close()
    P, X, obs = Conn(NS), Conn(NS), Conn(NS)
    res = {"lock": lock, "mode": mode, "pids": {"P": P.pid, "X": X.pid}}
    try:
        m0 = trlib.journal.mark()
        P.o.lock(mode, 1, lock[0], *lock[1:])
        res["probe_holds"] = lock_rows(obs, P.pid)
        done: Dict = {}

        def work():
            t = time.time()
            try:
                if nested:
                    X.o.tStart()
                done["result"] = str(op(X))[:300]
            except Exception as ex:  # noqa: BLE001
                done["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
            done["t"] = round(time.time() - t, 3)
        th = threading.Thread(target=work)
        t0 = time.time()
        th.start()
        samples = []
        while time.time() - t0 < hold:
            time.sleep(min(0.5, hold / 5))
            samples.append({"t": round(time.time() - t0, 2), **proc_state(obs, X.pid),
                            "x_locks": lock_rows(obs, X.pid)})
        res["x_while_held"] = samples
        m_rel = trlib.journal.mark()
        P.o.releaseAllLocks()
        th.join(90)
        res["x"] = done
        res["x_locks_after"] = lock_rows(obs, X.pid)
        if nested:
            try:
                res["x_locks_before_outer_commit"] = lock_rows(obs, X.pid)
                X.o.tCommit()
            except Exception as ex:  # noqa: BLE001
                res["outer_commit_error"] = str(ex)[:200]
            res["x_locks_after_outer_commit"] = lock_rows(obs, X.pid)
        recs = trlib.journal.records_since(m0, dbs={trlib.DB}, pids={X.pid})
        res["x_records_before_release"] = [{"a": r["a"], "t": r["t"], "g": r["g"][:90]} for r in recs
                                           if r["a"] <= m_rel.address and r["g"]]
        res["x_records_total"] = len([r for r in recs if r["g"]])
        waited = [s for s in samples if s.get("state", "").startswith("LOCK")]
        res["waited"] = bool(waited)
        res["wait_at"] = sorted({s["at"] for s in waited})
        res["held_while_waiting"] = sorted({(lr["ref"], lr["mode"]) for s in waited for lr in s["x_locks"]
                                            if "W" not in (lr["flags"] or "")})
        res["held_while_waiting"] = [list(x) for x in res["held_while_waiting"]]
        res["x_finished_while_held"] = done.get("t") is not None and done["t"] < hold
        return res
    finally:
        try:
            P.o.releaseAllLocks()
        except Exception:  # noqa: BLE001
            pass
        for c in (P, X, obs):
            c.close()
