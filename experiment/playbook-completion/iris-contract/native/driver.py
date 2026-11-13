#!/usr/bin/env python3
"""Run iris-contract cases on the dedicated IRIS engine (namespace AUDITENV) and record what it did.

    python driver.py cases.json observed.json [--repeat N] [--only ID ...]

A case is a schedule of (process, operation). Each process is one IRIS server process, driven either through the
product's own client path (`dbapi`: a DB-API connection and the Native API on that same connection) or through an
ObjectScript terminal (`term`: `iris session`, for operations the Native API cannot express: process-private
globals and the non-incremental LOCK). Nothing is compiled into IRIS; scratch data lives in ^IVGAuditEnv,
^IVGAuditLk and the table IVGAudit.T, which the driver empties before every case.

Observations use the contract's own JSON forms (see src/lib.rs `Obs`). An operation that may block runs
asynchronously: if it has not answered within ISSUE_WAIT seconds it is recorded as `pending`, and a later `await`
waits AWAIT_WAIT seconds for it (`blocked` if it still has not answered).
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from iris_conn import Conn  # noqa: E402

NS = "AUDITENV"
GROOT = "^IVGAuditEnv"
LROOT = "^IVGAuditLk"
TABLE = "IVGAudit.T"
ISSUE_WAIT = 1.0
AWAIT_WAIT = 3.0
LOCK_WAIT = 15


def real_root(root: str) -> str:
    return {"^X": GROOT, "^L": LROOT}.get(root, root)


def ok() -> Dict:
    return {"obs": "ok"}


def norm_err(e: BaseException) -> Dict:
    t = str(e)
    for name in ("<COMMAND>", "<TIMEOUT>", "<UNDEFINED>", "<SYNTAX>"):
        if name in t:
            return {"obs": "error", "error": name}
    if "SQLCODE" in t or "SQL ERROR" in t.upper():
        import re
        m = re.search(r"SQLCODE:?\s*<?(-?\d+)", t)
        if m:
            return {"obs": "sql_error", "sqlcode": int(m.group(1))}
    return {"obs": "error", "error": t[:120]}


class Async:
    """One operation running in a thread of the driver; the IRIS process is busy until it answers."""

    def __init__(self, fn):
        self.q: "queue.Queue" = queue.Queue()
        self.t = threading.Thread(target=lambda: self.q.put(self._run(fn)), daemon=True)
        self.t.start()

    @staticmethod
    def _run(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return norm_err(e)

    def wait(self, secs: float) -> Optional[Dict]:
        try:
            return self.q.get(timeout=secs)
        except queue.Empty:
            return None


class DbapiProc:
    kind = "dbapi"

    def __init__(self) -> None:
        self.c = Conn(NS)
        self.o = self.c.o
        self.pid = self.c.pid
        self.pending: Optional[Async] = None

    def node(self, n: Dict):
        return (real_root(n["root"]), *n.get("subs", []))

    def _lock(self, n: Dict, mode: str, timeout: int) -> Dict:
        root, *subs = self.node(n)
        try:
            self.o.lock("S" if mode == "S" else "", timeout, root, *subs)
            return {"obs": "test", "test": True}
        except RuntimeError as e:
            if "TIMEOUT" in str(e):
                return {"obs": "test", "test": False}
            raise

    def _dml(self, op: Dict) -> Dict:
        cur = self.c.conn.cursor()
        try:
            if op["op"] == "insert":
                cur.execute(f"INSERT INTO {TABLE} (k, v) VALUES (?, ?)", (op["k"], op["v"]))
            elif op["op"] == "update":
                cur.execute(f"UPDATE {TABLE} SET v = ? WHERE k = ?", (op["v"], op["k"]))
            else:
                cur.execute(f"DELETE FROM {TABLE} WHERE k = ?", (op["k"],))
            return {"obs": "count", "rowcount": max(cur.rowcount, 0)}
        except Exception as e:  # noqa: BLE001
            return norm_err(e)
        finally:
            cur.close()

    def run(self, op: Dict) -> Dict:
        k = op["op"]
        o = self.o
        try:
            if k == "await":
                if self.pending is None:
                    return {"obs": "error", "error": "nothing pending"}
                r = self.pending.wait(AWAIT_WAIT)
                if r is None:
                    return {"obs": "blocked"}
                self.pending = None
                return r
            if self.pending is not None:
                return {"obs": "error", "error": "busy"}
            if k == "t_start":
                o.tStart(); return ok()
            if k == "t_commit":
                o.tCommit(); return ok()
            if k == "t_rollback_one":
                o.tRollbackOne(); return ok()
            if k == "t_rollback":
                o.tRollback(); return ok()
            if k in ("sql_start", "sql_commit", "sql_rollback"):
                stmt = {"sql_start": "START TRANSACTION", "sql_commit": "COMMIT", "sql_rollback": "ROLLBACK"}[k]
                cur = self.c.conn.cursor(); cur.execute(stmt); cur.close(); return ok()
            if k == "drv_commit":
                self.c.conn.commit(); return ok()
            if k == "drv_rollback":
                self.c.conn.rollback(); return ok()
            if k == "set_autocommit":
                self.c.conn.setAutoCommit(bool(op["on"])); return ok()
            if k == "t_level":
                return {"obs": "level", "tlevel": int(o.getTLevel())}
            if k == "set":
                o.set(op["value"], *self.node(op["node"])); return ok()
            if k == "kill":
                o.kill(*self.node(op["node"])); return ok()
            if k == "get":
                v = o.get(*self.node(op["node"]))
                return {"obs": "value", "value": None if v is None else str(v)}
            if k == "data":
                return {"obs": "data", "data": int(o.isDefined(*self.node(op["node"])))}
            if k == "incr":
                return {"obs": "value", "value": str(o.increment(1, *self.node(op["node"])))}
            if k == "lock":
                if op.get("wait"):
                    n, m = op["node"], op["mode"]
                    a = Async(lambda: self._lock(n, m, LOCK_WAIT))
                    r = a.wait(ISSUE_WAIT)
                    if r is None:
                        self.pending = a
                        return {"obs": "pending"}
                    return r
                return self._lock(op["node"], op["mode"], 0)
            if k == "unlock":
                mode = ("S" if op["mode"] == "S" else "") + ("I" if op.get("immediate") else "")
                o.unlock(mode, *self.node(op["node"])); return ok()
            if k == "release_all":
                o.releaseAllLocks(); return ok()
            if k in ("insert", "update", "delete"):
                a = Async(lambda: self._dml(op))
                r = a.wait(ISSUE_WAIT)
                if r is None:
                    self.pending = a
                    return {"obs": "pending"}
                return r
            if k == "select":
                cur = self.c.conn.cursor()
                cur.execute(f"SELECT k, v FROM {TABLE} ORDER BY k")
                rows = [[str(a), str(b)] for a, b in cur.fetchall()]
                cur.close()
                return {"obs": "rows", "rows": rows}
            return {"obs": "refused", "what": f"{k} on dbapi"}
        except Exception as e:  # noqa: BLE001
            return norm_err(e)

    def close(self) -> None:
        try:
            if self.pending is None:
                self.o.tRollback()
                self.o.releaseAllLocks()
        except Exception:  # noqa: BLE001
            pass
        self.c.close()


class TermProc:
    """An ObjectScript terminal on the server (`iris session`): one server process, driven line by line."""
    kind = "term"

    def __init__(self) -> None:
        self.p = subprocess.Popen(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session",
                                   "IRIS", "-U", NS], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.q: "queue.Queue[str]" = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()
        self.seq = 0
        self.pending: Optional[int] = None
        self.pid = self._call("write $c(30),\"R|\",$job,!", 20)["raw"]

    def _reader(self) -> None:
        buf = ""
        for ch in iter(lambda: self.p.stdout.read(1), ""):
            buf += ch
            if ch == "\n":
                if buf.startswith("\x1e") or "\x1e" in buf:
                    self.q.put(buf[buf.index("\x1e") + 1:].rstrip("\r\n"))
                buf = ""

    def _send(self, line: str) -> int:
        self.seq += 1
        tagged = line.replace('"R|"', f'"R{self.seq}|"').replace('"E|"', f'"E{self.seq}|"')
        self.p.stdin.write(" " + tagged + "\n")
        self.p.stdin.flush()
        return self.seq

    def _get(self, seq: int, secs: float) -> Optional[Dict]:
        end = time.time() + secs
        while time.time() < end:
            try:
                line = self.q.get(timeout=max(0.01, end - time.time()))
            except queue.Empty:
                return None
            tag, _, rest = line.partition("|")
            if tag in (f"R{seq}", f"E{seq}"):
                return {"ok": tag.startswith("R"), "raw": rest}
        return None

    def _call(self, cmd: str, secs: float = 10) -> Dict:
        seq = self._send(f"try {{ {cmd} }} catch ex {{ write $c(30),\"E|\",ex.Name,! }}")
        r = self._get(seq, secs)
        if r is None:
            raise RuntimeError(f"terminal did not answer: {cmd}")
        return r

    @staticmethod
    def ref(n: Dict) -> str:
        root = real_root(n["root"])
        subs = n.get("subs", [])
        return root + ("(" + ",".join('"' + s.replace('"', '""') + '"' for s in subs) + ")" if subs else "")

    def _translate(self, op: Dict) -> Optional[str]:
        k = op["op"]
        w = 'write $c(30),"R|",'
        if k == "t_start": return 'tstart  write $c(30),"R|","ok",!'
        if k == "t_commit": return 'tcommit  write $c(30),"R|","ok",!'
        if k == "t_rollback_one": return 'trollback 1  write $c(30),"R|","ok",!'
        if k == "t_rollback": return 'trollback  write $c(30),"R|","ok",!'
        if k == "t_level": return w + '"L",$tlevel,!'
        if k in ("sql_start", "sql_commit", "sql_rollback"):
            stmt = {"sql_start": "START TRANSACTION", "sql_commit": "COMMIT", "sql_rollback": "ROLLBACK"}[k]
            return f'set rs=##class(%SQL.Statement).%ExecDirect(,"{stmt}") ' + w + '"S",rs.%SQLCODE,"|",rs.%ROWCOUNT,!'
        if k == "set": return f'set {self.ref(op["node"])}="{op["value"]}" ' + w + '"ok",!'
        if k == "kill": return f'kill {self.ref(op["node"])} ' + w + '"ok",!'
        if k == "get": return w + f'"V",$data({self.ref(op["node"])})#2,"|",$get({self.ref(op["node"])}),!'
        if k == "data": return w + f'"D",$data({self.ref(op["node"])}),!'
        if k == "incr": return w + f'"I",$increment({self.ref(op["node"])}),!'
        if k == "ppg_set": return f'set {self.ref(op["node"]).replace("^", "^||", 1)}="{op["value"]}" ' + w + '"ok",!'
        if k == "ppg_get":
            r = self.ref(op["node"]).replace("^", "^||", 1)
            return w + f'"V",$data({r})#2,"|",$get({r}),!'
        if k == "lock":
            t = "S" if op["mode"] == "S" else ""
            typ = f'#"{t}"' if t else ""
            return f'lock +{self.ref(op["node"])}{typ}:{LOCK_WAIT if op.get("wait") else 0} ' + w + '"T",$test,!'
        if k == "lock_only":
            return f'lock {self.ref(op["node"])}:{LOCK_WAIT if op.get("wait") else 0} ' + w + '"T",$test,!'
        if k == "unlock":
            t = ("S" if op["mode"] == "S" else "") + ("I" if op.get("immediate") else "")
            typ = f'#"{t}"' if t else ""
            return f'lock -{self.ref(op["node"])}{typ} ' + w + '"ok",!'
        if k == "release_all": return 'lock  ' + w + '"ok",!'
        if k in ("insert", "update", "delete"):
            if k == "insert": stmt = f"INSERT INTO {TABLE} (k, v) VALUES ('{op['k']}', '{op['v']}')"
            elif k == "update": stmt = f"UPDATE {TABLE} SET v = '{op['v']}' WHERE k = '{op['k']}'"
            else: stmt = f"DELETE FROM {TABLE} WHERE k = '{op['k']}'"
            return f'set rs=##class(%SQL.Statement).%ExecDirect(,"{stmt}") ' + w + '"S",rs.%SQLCODE,"|",rs.%ROWCOUNT,!'
        if k == "select":
            return (f'set rs=##class(%SQL.Statement).%ExecDirect(,"SELECT k, v FROM {TABLE} ORDER BY k"), out="" '
                    'while rs.%Next() { set out=out_rs.k_$c(31)_rs.v_$c(29) } ' + w + '"W",out,!')
        return None

    @staticmethod
    def _decode(op: Dict, r: Dict) -> Dict:
        if not r["ok"]:
            return {"obs": "error", "error": r["raw"]}
        raw = r["raw"]
        if raw == "ok": return ok()
        tag, body = raw[0], raw[1:]
        if tag == "L": return {"obs": "level", "tlevel": int(body)}
        if tag == "V":
            d, _, v = body.partition("|")
            return {"obs": "value", "value": v if d == "1" else None}
        if tag == "D": return {"obs": "data", "data": int(body)}
        if tag == "I": return {"obs": "value", "value": body}
        if tag == "T": return {"obs": "test", "test": body == "1"}
        if tag == "S":
            code, _, n = body.partition("|")
            code = int(code or 0)
            if code < 0: return {"obs": "sql_error", "sqlcode": code}
            if op["op"] in ("insert", "update", "delete"):
                return {"obs": "count", "rowcount": int(n or 0)}
            return ok()
        if tag == "W":
            rows = [x.split("\x1f") for x in body.split("\x1d") if x]
            return {"obs": "rows", "rows": rows}
        return {"obs": "error", "error": raw}

    def run(self, op: Dict) -> Dict:
        k = op["op"]
        if k == "await":
            if self.pending is None:
                return {"obs": "error", "error": "nothing pending"}
            seq, pop = self.pending
            r = self._get(seq, AWAIT_WAIT)
            if r is None:
                return {"obs": "blocked"}
            self.pending = None
            return self._decode(pop, r)
        if self.pending is not None:
            return {"obs": "error", "error": "busy"}
        cmd = self._translate(op)
        if cmd is None:
            return {"obs": "refused", "what": f"{k} on term"}
        seq = self._send(f"try {{ {cmd} }} catch ex {{ write $c(30),\"E|\",ex.Name,! }}")
        r = self._get(seq, ISSUE_WAIT if k in ("lock", "lock_only", "insert", "update", "delete") else 15)
        if r is None:
            self.pending = (seq, op)
            return {"obs": "pending"}
        return self._decode(op, r)

    def close(self) -> None:
        try:
            if self.p.poll() is None:
                self.p.stdin.write(" trollback  lock  halt\n")
                self.p.stdin.flush()
                self.p.wait(10)
        except Exception:  # noqa: BLE001
            self.p.kill()


def reset(ctl: Conn) -> None:
    ctl.o.kill(GROOT)
    ctl.o.kill(LROOT)
    if not ctl.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='IVGAudit' AND TABLE_NAME='T'")[0][0]:
        ctl.sql(f"CREATE TABLE {TABLE} (k VARCHAR(20) PRIMARY KEY, v VARCHAR(20))")
    ctl.sql(f"DELETE FROM {TABLE}")


def gone(ctl: Conn, pid: str, secs: float = 15) -> bool:
    end = time.time() + secs
    while time.time() < end:
        if not int(ctl.call("%SYS.ProcessQuery", "%ExistsId", pid) or 0):
            return True
        time.sleep(0.1)
    return False


def run_case(case: Dict, ctl: Conn) -> Dict:
    reset(ctl)
    kinds = case.get("kinds") or ["dbapi"] * case["procs"]
    procs: List[Any] = [DbapiProc() if kd == "dbapi" else TermProc() for kd in kinds]
    dead = set()
    obs = []
    try:
        for p, op in case["steps"]:
            if op["op"] == "terminate":
                t = op["target"]
                if t not in dead:
                    ctl.call("%SYSTEM.Process", "Terminate", procs[t].pid)
                    if not gone(ctl, procs[t].pid):
                        raise RuntimeError("terminated process did not exit")
                    dead.add(t)
                obs.append(ok())
                continue
            if p in dead:
                obs.append({"obs": "error", "error": "dead"})
                continue
            obs.append(procs[p].run(op))
        finals = []
        for n in case.get("observe", []):
            v = ctl.o.get(real_root(n["root"]), *n.get("subs", []))
            finals.append({"obs": "value", "value": None if v is None else str(v)})
        for _t in case.get("observe_tables", []):
            rows = ctl.sql(f"SELECT k, v FROM {TABLE} ORDER BY k")
            finals.append({"obs": "rows", "rows": [[str(a), str(b)] for a, b in rows]})
        return {"obs": obs, "finals": finals}
    finally:
        for i, pr in enumerate(procs):
            if i not in dead:
                if pr.kind == "dbapi" and pr.pending is not None:
                    ctl.call("%SYSTEM.Process", "Terminate", pr.pid)
                    gone(ctl, pr.pid)
                    pr.c.close()
                else:
                    pr.close()


def main() -> int:
    cases = json.loads(Path(sys.argv[1]).read_text())
    out_path = Path(sys.argv[2])
    repeat = int(sys.argv[sys.argv.index("--repeat") + 1]) if "--repeat" in sys.argv else 1
    only = set(sys.argv[sys.argv.index("--only") + 1:]) if "--only" in sys.argv else None
    observed: Dict[str, List[Dict]] = json.loads(out_path.read_text()) if out_path.exists() and only else {}
    ctl = Conn(NS)
    try:
        from iris_conn import version
        print("engine:", version(ctl), flush=True)
        for c in cases:
            if only and c["id"] not in only:
                continue
            runs = []
            for _ in range(repeat):
                t = time.time()
                runs.append(run_case(c, ctl))
                print(f"{c['id']}: {time.time() - t:.2f}s", flush=True)
            observed[c["id"]] = runs
            out_path.write_text(json.dumps(observed, indent=1))
    finally:
        reset(ctl)
        ctl.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
