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


# ---------------------------------------------------------------------------------------------- extension (r3)
# Scratch tables, created by reset(): T, S, E (k, v), F (k, v) with the functional index fx (%iFind.Index.Basic,
# a %Library.FunctionalIndex subclass shipped with IRIS: nothing of ours is compiled), C (declared column order).
# D1 and D2 are created and dropped by the cases themselves.
F_TABLE = "IVGAudit.F"
E_TABLE = "IVGAudit.E"
C_COLS = "zeta VARCHAR(5), alpha VARCHAR(5), mid INTEGER, k VARCHAR(5) PRIMARY KEY"
FIND_IDS = f"SELECT %ID FROM {F_TABLE} WHERE %ID %FIND search_index(fx, ?) ORDER BY %ID"
EXISTS_Q = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='IVGAudit' AND TABLE_NAME=?"
MATCH_Q = f"SELECT COUNT(*) FROM {E_TABLE} WHERE COALESCE(v, '') = COALESCE(?, '')"
VEC_A, VEC_B = "TO_VECTOR('1,0', DOUBLE)", "TO_VECTOR('0.6,0.8', DOUBLE)"


def tname(t: str) -> str:
    return f"IVGAudit.{t}"


def hints(op: Dict) -> str:
    return ("%NOINDEX " if op.get("noindex") else "") + ("%NOCHECK " if op.get("nocheck") else "")


def sql_lit(v: Optional[str]) -> str:
    return "NULL" if v is None else "'" + v.replace("'", "''") + "'"


def ddl_create(t: str) -> str:
    # storage under the scratch prefix (^IVGAudit<t>.N), so reset() can empty it whatever the indexes hold
    return (f"CREATE TABLE {tname(t)} (k VARCHAR(20) PRIMARY KEY, v VARCHAR(20)) "
            f"WITH %CLASSPARAMETER DEFAULTGLOBAL = '^IVGAudit{t}'")


def select_q(t: str) -> str:
    # a full scan (%NOINDEX rows are in no index); no ORDER BY: ordering by the unique key keeps one row per key
    # when %NOCHECK / %NOINDEX made it non-unique (explore-6 K3), so the client sorts by (k, v)
    return f"SELECT k, v FROM %IGNOREINDEX * {tname(t)}"


def sql_fn_q(name: str) -> str:
    return f"SELECT {name}({VEC_A}, {VEC_B})"


def fmt4(x) -> Optional[str]:
    return None if x is None else str(round(float(x), 4))


def canon(s) -> str:
    """A subscript as IRIS writes it: the Native API answers numeric subscripts as int / float."""
    if isinstance(s, bool):
        return str(int(s))
    if isinstance(s, int):
        return str(s)
    if isinstance(s, float):
        t = repr(s)
        if t.endswith(".0"):
            t = t[:-2]
        if t.startswith("0."):
            t = t[1:]
        elif t.startswith("-0."):
            t = "-" + t[2:]
        return t
    if isinstance(s, (bytes, bytearray)):
        return s.decode()
    return str(s)


def norm_err(e: BaseException) -> Dict:
    t = str(e)
    # The statement's SQLCODE first: the server appends the process's last ObjectScript error to the next failing
    # statement's report ("[Error: <<COMMAND>>]" after a Native tCommit at level 0, env/explore-8.log), which is
    # not that statement's result.
    if "SQLCODE" in t or "SQL ERROR" in t.upper():
        import re
        m = re.search(r"SQLCODE:?\s*<?(-?\d+)", t)
        if m:
            return {"obs": "sql_error", "sqlcode": int(m.group(1))}
    for name in ("<COMMAND>", "<TIMEOUT>", "<UNDEFINED>", "<SYNTAX>", "<LIST ERROR>"):
        if name in t:
            return {"obs": "error", "error": name}
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
        t = tname(op.get("table", "T"))
        try:
            if op["op"] == "insert":
                cur.execute(f"INSERT {hints(op)}INTO {t} (k, v) VALUES (?, ?)", (op["k"], op["v"]))
            elif op["op"] == "update":
                cur.execute(f"UPDATE {t} SET v = ? WHERE k = ?", (op["v"], op["k"]))
            elif op["op"] == "delete":
                cur.execute(f"DELETE FROM {t} WHERE k = ?", (op["k"],))
            elif op["op"] == "put_e":
                if op.get("literal"):
                    cur.execute(f"INSERT INTO {E_TABLE} (k, v) VALUES ('{op['k']}', {sql_lit(op['v'])})")
                else:
                    cur.execute(f"INSERT INTO {E_TABLE} (k, v) VALUES (?, ?)", (op["k"], op["v"]))
            elif op["op"] == "insert_select":
                cur.execute(f"INSERT INTO {tname(op['to'])} (k, v) SELECT k, v FROM {tname(op['from'])}")
            return {"obs": "count", "rowcount": max(cur.rowcount, 0)}
        except Exception as e:  # noqa: BLE001
            return norm_err(e)
        finally:
            cur.close()

    def _q(self, q: str, *params):
        cur = self.c.conn.cursor()
        try:
            cur.execute(q, params) if params else cur.execute(q)
            return [tuple(r) for r in cur.fetchall()] if cur.description else cur.rowcount
        finally:
            cur.close()

    def _ext(self, k: str, op: Dict) -> Optional[Dict]:
        """The extension's operations (round r3); None if `k` is not one of them."""
        if k == "find":
            ids = [r[0] for r in self._q(FIND_IDS, op["word"])]
            keys = []
            for i in ids:
                r = self._q(f"SELECT k FROM {F_TABLE} WHERE %ID = ?", i)
                keys.append(str(r[0][0]) if r else "?")
            return {"obs": "keys", "keys": sorted(keys)}
        if k == "build_index":
            self._q(f"BUILD INDEX FOR TABLE {tname(op['table'])}"); return ok()
        if k == "create_table":
            self._q(ddl_create(op["table"])); return ok()
        if k == "drop_table":
            self._q(f"DROP TABLE {tname(op['table'])}"); return ok()
        if k == "table_exists":
            n = self._q(EXISTS_Q, op["table"])[0][0]
            return {"obs": "test", "test": bool(int(n))}
        if k == "add_column":
            self._q(f"ALTER TABLE {tname(op['table'])} ADD COLUMN {op['col']} VARCHAR(5)"); return ok()
        if k == "select_star":
            cur = self.c.conn.cursor()
            try:
                cur.execute(f"SELECT * FROM {tname(op['table'])}")
                cols = [str(d[0]) for d in cur.description]
                cur.fetchall()
            finally:
                cur.close()
            return {"obs": "cols", "cols": cols}
        if k == "get_e":
            r = self._q(f"SELECT v, CASE WHEN v IS NULL THEN 1 ELSE 0 END FROM {E_TABLE} WHERE k = ?", op["k"])
            if not r:
                return {"obs": "rows", "rows": []}
            v, n = r[0]
            return {"obs": "cell", "value": None if v is None else str(v), "null": bool(int(n))}
        if k == "match_e":
            n = self._q(MATCH_Q, op["v"])[0][0]
            return {"obs": "count", "rowcount": int(n)}
        if k == "order":
            root, *subs = self.node(op["node"])
            out, s = [], ""
            while True:
                s = self.o.nextSubscript(False, root, *subs, s)
                if s is None or s == "":
                    break
                out.append(canon(s))
            return {"obs": "subs", "subs": out}
        if k == "sql_t_level":
            return {"obs": "level", "tlevel": int(self._q("SELECT $TLEVEL")[0][0])}
        if k == "sql_fn":
            r = self._q(sql_fn_q(op["name"]))
            return {"obs": "value", "value": fmt4(r[0][0])}
        return None

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
            if k in ("put_e", "insert_select"):
                return self._dml(op)  # never blocks in the subset (the model refuses the blocking schedules)
            if k in ("insert", "update", "delete"):
                a = Async(lambda: self._dml(op))
                r = a.wait(ISSUE_WAIT)
                if r is None:
                    self.pending = a
                    return {"obs": "pending"}
                return r
            if k == "select":
                cur = self.c.conn.cursor()
                try:
                    cur.execute(select_q(op.get("table", "T")))
                    rows = sorted([str(a), str(b)] for a, b in cur.fetchall())
                finally:
                    cur.close()
                return {"obs": "rows", "rows": rows}
            r = self._ext(k, op)
            if r is not None:
                return r
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
                                  stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8",
                                  errors="replace")
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
        ex = 'set rs=##class(%SQL.Statement).%ExecDirect(,"{}"{}) ' + w + '"S",rs.%SQLCODE,"|",rs.%ROWCOUNT,!'
        if k in ("insert", "update", "delete"):
            t = tname(op.get("table", "T"))
            if k == "insert": stmt = f"INSERT {hints(op)}INTO {t} (k, v) VALUES ('{op['k']}', '{op['v']}')"
            elif k == "update": stmt = f"UPDATE {t} SET v = '{op['v']}' WHERE k = '{op['k']}'"
            else: stmt = f"DELETE FROM {t} WHERE k = '{op['k']}'"
            return ex.format(stmt, "")
        if k == "select":
            return (f'set rs=##class(%SQL.Statement).%ExecDirect(,"{select_q(op.get("table", "T"))}"), out="" '
                    'if rs.%SQLCODE<0 { ' + w + '"S",rs.%SQLCODE,"|",! quit } '
                    'while rs.%Next() { set out=out_rs.k_$c(31)_rs.v_$c(29) } ' + w + '"W",out,!')
        # ------------------------------------------------------------------------------ extension (r3)
        if k == "find":
            return ('set rs=##class(%SQL.Statement).%ExecDirect(,"' + FIND_IDS.replace(" ORDER BY %ID", "").replace("%ID FROM", "%ID AS i FROM")
                    + '","' + op["word"] + '"),out="" '
                    'if rs.%SQLCODE<0 { ' + w + '"S",rs.%SQLCODE,"|",! quit } '
                    'while rs.%Next() { set r2=##class(%SQL.Statement).%ExecDirect(,"SELECT k FROM ' + F_TABLE
                    + ' WHERE %ID = ?",rs.i),kk="?" set:r2.%Next() kk=r2.k set out=out_kk_$c(31) } ' + w + '"K",out,!')
        if k == "build_index": return ex.format(f"BUILD INDEX FOR TABLE {tname(op['table'])}", "")
        if k == "create_table": return ex.format(ddl_create(op["table"]), "")
        if k == "drop_table": return ex.format(f"DROP TABLE {tname(op['table'])}", "")
        if k == "add_column": return ex.format(f"ALTER TABLE {tname(op['table'])} ADD COLUMN {op['col']} VARCHAR(5)", "")
        if k == "insert_select":
            return ex.format(f"INSERT INTO {tname(op['to'])} (k, v) SELECT k, v FROM {tname(op['from'])}", "")
        if k == "table_exists":
            return w + f'"T",##class(%SYSTEM.SQL.Schema).TableExists("{tname(op["table"])}"),!'
        if k == "put_e":
            v = op["v"]
            if op.get("literal"):
                lit = "NULL" if v is None else "'" + v + "'"
                return ex.format(f"INSERT INTO {E_TABLE} (k, v) VALUES ('{op['k']}', {lit})", "")
            arg = "$c(0)" if v == "\x00" else '"' + (v or "") + '"'
            return ex.format(f"INSERT INTO {E_TABLE} (k, v) VALUES (?, ?)", f',"{op["k"]}",{arg}')
        if k == "get_e":
            return (f'set rs=##class(%SQL.Statement).%ExecDirect(,"SELECT v, CASE WHEN v IS NULL THEN 1 ELSE 0 END AS n '
                    f'FROM {E_TABLE} WHERE k = ?","{op["k"]}") if rs.%Next() {{ ' + w
                    + '"C",rs.n,"|",$replace(rs.v,$c(0),"<c0>"),! } else { ' + w + '"C",! }')
        if k == "match_e":
            v = op["v"]
            arg = "$c(0)" if v == "\x00" else '"' + (v or "") + '"'
            return ('set rs=##class(%SQL.Statement).%ExecDirect(,"' + MATCH_Q.replace("COUNT(*)", "COUNT(*) AS n") + '",'
                    + arg + ') do rs.%Next() ' + w + '"N",rs.n,!')
        if k == "order":
            n = op["node"]
            root = real_root(n["root"])
            subs = ",".join('"' + x.replace('"', '""') + '"' for x in n.get("subs", []))
            ref = root + "(" + (subs + "," if subs else "") + "s)"
            return 'set s="",out="" for { set s=$order(' + ref + ') quit:s=""  set out=out_s_$c(31) } ' + w + '"O",out,!'
        if k == "sql_t_level":
            return 'set rs=##class(%SQL.Statement).%ExecDirect(,"SELECT $TLEVEL AS l") do rs.%Next() ' + w + '"L",rs.l,!'
        if k == "sql_fn":
            return ('set rs=##class(%SQL.Statement).%ExecDirect(,"' + sql_fn_q(op["name"]) + ' AS d") '
                    'if rs.%SQLCODE<0 { ' + w + '"S",rs.%SQLCODE,"|",! } else { do rs.%Next() ' + w + '"F",rs.d,! }')
        if k == "vec_set":
            return f'set $vector({self.ref(op["node"])},{int(op["i"])},"double")={op["x"]} ' + w + '"ok",!'
        if k == "vec_get":
            r = self.ref(op["node"])
            i = int(op["i"])
            return (f'kill x set d=0 if $data({r})#2 {{ if $isvector({r}) {{ if $vectordefined({r},{i}) {{ set d=1,x=$vector({r},{i}) }} }} }} '
                    + w + '"V",d,"|",$get(x),!')
        if k == "z_strip":
            cs = ",".join(str(int(c)) for c in op["s"])
            rem = op.get("rem", "")
            return (f'set x=$zstrip($c({cs}),"{op["mask"]}","{rem}"),out="" for i=1:1:$length(x) {{ set out=out_$ascii(x,i)_"," }} '
                    + w + '"Z",out,!')
        if k == "z_class":
            c = op["class"]
            return ('set out="",prev=-2,st=-1 for i=0:1:65535 { set r=($zstrip($c(i),"*' + c + '")="") '
                    'if r,prev\'=(i-1) { set:st>=0 out=out_st_"-"_prev_"," set st=i } set:r prev=i } '
                    'set:st>=0 out=out_st_"-"_prev ' + w + '"R",out,!')
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
            if op["op"] in ("insert", "update", "delete", "put_e", "insert_select"):
                return {"obs": "count", "rowcount": int(n or 0)}
            return ok()
        if tag == "W":
            rows = sorted(x.split("\x1f") for x in body.split("\x1d") if x)
            return {"obs": "rows", "rows": rows}
        if tag == "K":
            return {"obs": "keys", "keys": sorted(x for x in body.split("\x1f") if x)}
        if tag == "C":
            if body == "":
                return {"obs": "rows", "rows": []}
            n, _, v = body.partition("|")
            return {"obs": "cell", "value": v.replace("<c0>", "\x00"), "null": n == "1"}
        if tag == "O":
            return {"obs": "subs", "subs": [x for x in body.split("\x1f") if x != ""]}
        if tag == "F":
            return {"obs": "value", "value": fmt4(body)}
        if tag == "Z":
            return {"obs": "codes", "codes": [int(x) for x in body.split(",") if x != ""]}
        if tag == "R":
            return {"obs": "value", "value": body}
        if tag == "N":
            return {"obs": "count", "rowcount": int(body)}
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
        r = self._get(seq, ISSUE_WAIT if k in ("lock", "lock_only", "insert", "update", "delete")
                      else (70 if k == "z_class" else 15))
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


STORE_GLOBALS = 12  # ^IVGAudit<t>.1 .. .12: data, extent, indexes, iFind's globals (explore-5 J1: at most .6)


def _exists(ctl: Conn, t: str) -> bool:
    return bool(ctl.sql(EXISTS_Q, t)[0][0])


def _storage_ok(ctl: Conn, t: str) -> bool:
    r = ctl.sql("SELECT DataLocation FROM %Dictionary.CompiledStorage WHERE parent = ?", tname(t))
    return bool(r) and str(r[0][0]).startswith(f"^IVGAudit{t}.")


def _kill_store(ctl: Conn, t: str) -> None:
    for i in range(1, STORE_GLOBALS + 1):
        ctl.o.kill(f"^IVGAudit{t}.{i}")


def reset(ctl: Conn) -> None:
    """Every case starts from: ^IVGAuditEnv and ^IVGAuditLk empty; T, S, E, F empty (F with its functional index
    fx); C with its four declared columns; D1 and D2 absent. Tables are emptied by killing their own storage
    globals (a %NOINDEX row is in no index, so DELETE cannot be relied on to reach it)."""
    ctl.o.kill(GROOT)
    ctl.o.kill(LROOT)
    for t in ("T", "S", "E", "F"):
        if not (_exists(ctl, t) and _storage_ok(ctl, t)):
            if _exists(ctl, t):
                ctl.sql(f"DROP TABLE {tname(t)}")
            ctl.sql(ddl_create(t))
            if t == "F":
                ctl.sql(f"CREATE INDEX fx ON {F_TABLE} (v) AS %iFind.Index.Basic")
        _kill_store(ctl, t)
    cols = [r[0] for r in ctl.sql("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='IVGAudit' "
                                  "AND TABLE_NAME='C' ORDER BY ORDINAL_POSITION")]
    if cols != ["zeta", "alpha", "mid", "k"]:
        if _exists(ctl, "C"):
            ctl.sql("DROP TABLE IVGAudit.C")
        ctl.sql(f"CREATE TABLE IVGAudit.C ({C_COLS})")
    for t in ("D1", "D2"):
        if _exists(ctl, t):
            ctl.sql(f"DROP TABLE {tname(t)}")
        _kill_store(ctl, t)


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
        for t in case.get("observe_tables", []):
            try:
                rows = ctl.sql(select_q(t))
                finals.append({"obs": "rows", "rows": sorted([str(a), str(b)] for a, b in rows)})
            except Exception as e:  # noqa: BLE001
                finals.append(norm_err(e))
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
