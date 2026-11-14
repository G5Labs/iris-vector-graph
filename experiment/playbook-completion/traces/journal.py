"""IRIS journal as an independent trace oracle (playbook §3.7 trace replay; §3.4 declared-write validation).

IRIS journals every global SET/KILL of a journaled database, with the server process id, whether it ran inside a
transaction, and BeginTrans/CommitTrans markers. SQL rows are stored in globals, so SQL writes appear too. The
journal is written by the engine itself, not by the product or by this harness, which is what makes it an
independent oracle for what a product operation actually wrote and in which transaction.

Reading is done server-side by a plain ObjectScript script fed to `iris session` (nothing is compiled into IRIS):

    m = mark()                          # address of the journal's last record now
    ... run product operations ...
    recs = records_since(m, dbs={"/usr/irissys/mgr/auditcore/"})

Each record: dict(a=address, t=type, p=pid, x=in_transaction, d=database dir, g=global node, n=new value,
o=old value, ts=timestamp). Values are base64 of the raw stored bytes (None when absent).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

SYSTEM_GLOBAL_PREFIXES = ("^rINDEXSQL", "^%", "^oddDEF", "^oddDEP", "^oddCOM", "^oddPROC", "^rOBJ", "^ROUTINE", "^rMAP",
                          "^rINDEX", "^IRIS.", "^ISC.", "^SYS(", "^SYS", "^mtemp", "^CacheTemp", "^IRIS.Temp",
                          "^oddEXT", "^oddMAP", "^oddSQL", "^oddStudio", "^oddPKG", "^SPOOL", "^ERRORS",
                          "^OBJ.DSTIME", "^IRIS.Msg", "^rBACKUP")


def _session(script: str, timeout: int = 600) -> str:
    container = os.environ["IVG_TEST_CONTAINER"]
    r = subprocess.run(["docker", "exec", "-i", container, "iris", "session", "IRIS", "-U", "%SYS"],
                       input=script, capture_output=True, text=True, timeout=timeout)
    if r.returncode not in (0, 1):  # `halt` exits the session with 0; some builds return 1
        raise RuntimeError(f"iris session failed: {r.returncode} {r.stderr[-2000:]}")
    return r.stdout


@dataclass(frozen=True)
class Mark:
    file: str
    address: int


def mark() -> Mark:
    out = _session(' set f=##class(%SYS.Journal.System).GetCurrentFileName()'
                   ' set o=##class(%SYS.Journal.File).%OpenId(f) set r=o.LastRecordGet()'
                   ' write !,$char(30),"MARK|",f,"|",r.Address,! halt\n')
    for line in out.replace("\r", "").split("\n"):  # not splitlines(): it splits on \x1e
        if line.startswith("\x1eMARK|"):
            _, f, a = line[1:].strip().split("|")
            return Mark(f, int(a))
    raise RuntimeError("no journal mark: " + out[-500:])


_READ = r'''
 set file="{file}", start={start}, dbs="{dbs}", nrec=0
 set f=##class(%SYS.Journal.File).%OpenId(file)
 for {{
  set r=$select(start:f.GetRecordAt(start),1:f.FirstRecordGet())
  if (start && $isobject(r)) {{ set r=r.Next }}
  while $isobject(r) {{
   set d="",g="",n="",o="",isSK=r.%IsA("%SYS.Journal.SetKillRecord")
   if isSK {{ set d=r.DatabaseName }}
   if (isSK && (dbs'="") && ((","_dbs_",")'[(","_d_","))) {{ set r=r.Next continue }}
   if isSK {{ set g=r.GlobalNode }}
   if (isSK && (r.NumberOfValues>0)) {{ try {{ set n=$system.Encryption.Base64Encode(r.NewValue,1) }} catch {{ set n="*" }} }}
   if isSK {{ try {{ set ov=r.OldValue if $data(ov)#2 {{ set o=$system.Encryption.Base64Encode(ov,1) }} }} catch {{ set o="*" }} }}
   write $char(30),"JRN|",r.Address,"|",r.TypeName,"|",r.ProcessID,"|",r.InTransaction,"|",d,"|",$zconvert(g,"O","JSON"),"|",n,"|",o,"|",r.TimeStamp,!
   set nrec=nrec+1, r=r.Next
  }}
  set nf="", sc=##class(%SYS.Journal.File).GetNext(file,.nf)
  if (nf="") {{ quit }}
  set file=nf, start=0, f=##class(%SYS.Journal.File).%OpenId(file)
 }}
'''


def records_since(m: Mark, dbs: Optional[Iterable[str]] = None, pids: Optional[Set[str]] = None,
                  keep_system: bool = False) -> List[Dict]:
    # The terminal runs each input line on its own, so the whole loop is one line, and the end marker is on that
    # same line: an error anywhere in the loop aborts the line before the marker is written.
    body = _READ.format(file=m.file, start=m.address, dbs=",".join(sorted(dbs or [])))
    lines = [ln.strip() for ln in body.strip().splitlines()]
    script = " " + " ".join(lines) + ' write $char(30),"JRNEND|",nrec,!\n halt\n'
    out = _session(script, timeout=1800)
    if "\x1eJRNEND|" not in out:
        raise RuntimeError("journal read did not finish: " + out[-1000:])
    recs: List[Dict] = []
    for line in out.replace("\r", "").split("\n"):  # not splitlines(): it splits on \x1e
        if not line.startswith("\x1eJRN|"):
            continue
        parts = line[1:].rstrip("\n").split("|")
        # The global node is JSON-escaped and may itself contain '|': rejoin the middle fields.
        _, a, t, p, x, d = parts[:6]
        n, o, ts = parts[-3:]
        g = "|".join(parts[6:-3])
        # "*": a value base64 cannot carry (an IRIS $vector); the write is recorded, its value is not
        rec = {"a": int(a), "t": t, "p": p, "x": x == "1", "d": d,
               "g": json.loads('"' + g + '"') if g else "", "n": None if n in ("", "*") else n,
               "o": None if o in ("", "*") else o, "ts": ts, "opaque": n == "*" or o == "*"}
        if pids is not None and rec["p"] not in pids:
            continue
        if not keep_system and rec["g"] and rec["g"].startswith(SYSTEM_GLOBAL_PREFIXES):
            continue
        recs.append(rec)
    return recs


def decode(v: Optional[str]) -> Optional[bytes]:
    return None if v is None else base64.b64decode(v)


def global_root(node: str) -> str:
    """'^KG("out",0,"a")' -> '^KG'; '^["^^/dir/"]X(1)' -> '^X'."""
    if node.startswith('^["'):
        node = "^" + node[node.index("]") + 1:]
    return node.split("(", 1)[0]


def transactions(recs: List[Dict]) -> List[Dict]:
    """Group a process's records into outermost transactions. Records outside a transaction are their own unit.

    Returns [{pid, kind: 'txn'|'auto', records, committed, rolled_back, nested_levels}] in journal order of the
    closing record. IRIS journals a nested TSTART/TCOMMIT as "BeginTrans with level" / "CommitTrans Pending with
    level" and a TROLLBACK as compensating records followed by the end marker; `rolled_back` is set when the
    transaction's net effect is empty, i.e. every write is undone by a later compensation inside it.
    """
    open_: Dict[str, Dict] = {}
    out: List[Dict] = []
    for r in recs:
        p, t = r["p"], r["t"]
        if t.startswith("BeginTrans"):
            if t == "BeginTrans" or p not in open_:
                open_[p] = {"pid": p, "kind": "txn", "records": [], "committed": False, "begin": r["a"],
                            "nested_levels": 0}
            else:
                open_[p]["nested_levels"] += 1
            continue
        if t.startswith("CommitTrans"):
            if t == "CommitTrans" and p in open_:
                u = open_.pop(p)
                u["committed"] = True
                u["end"] = r["a"]
                u["rolled_back"] = bool(u["records"]) and not net_effect(u["records"])
                u["addresses"] = [x["a"] for x in u["records"]]
                out.append(u)
            continue
        if r["x"] and p in open_:
            open_[p]["records"].append(r)
        else:
            out.append({"pid": p, "kind": "auto", "records": [r], "committed": True, "rolled_back": False,
                        "begin": r["a"], "end": r["a"], "nested_levels": 0, "addresses": [r["a"]]})
    for u in open_.values():
        u["rolled_back"] = False
        out.append(u)  # still open at the end of the capture
    return out


def net_effect(records: List[Dict]) -> Dict[str, Optional[str]]:
    """Final value per global node written by these records, minus nodes restored to their first old value.

    A KILL of a subtree is reported under its own node with value None; callers that need subtree semantics use
    the raw records.
    """
    first_old: Dict[str, Optional[str]] = {}
    last: Dict[str, Optional[str]] = {}
    for r in records:
        g = r["g"]
        if not g:
            continue
        if g not in first_old:
            first_old[g] = r["o"]
        # SET and BitSET write a value (a BitSET's value is the bit string); KILL and ZKILL remove it
        last[g] = r["n"] if r["t"].startswith(("SET", "BitSET")) else None
    return {g: v for g, v in last.items() if v != first_old[g]}


def storage_map(conn) -> Dict[str, str]:
    """Global prefix -> SQL table, from the namespace's compiled storage (DDL tables use hashed globals).

    `conn` is a tools.iris_conn.Conn on the namespace. A table's data, index and stream globals share the extent's
    prefix ('^t52S.XCFT.1', '^t52S.XCFT.2', ...), so the prefix up to the last '.' identifies the table.
    """
    rows = conn.sql("SELECT s.parent, s.DataLocation, s.IndexLocation, s.StreamLocation, c.SqlSchemaName, "
                    "c.SqlTableName FROM %Dictionary.CompiledStorage s JOIN %Dictionary.CompiledClass c "
                    "ON c.Name = s.parent WHERE c.SqlTableName IS NOT NULL")
    m: Dict[str, str] = {}
    for cls, data, index, stream, schema, table in rows:
        name = f"{schema}.{table}" if schema else str(cls)
        for loc in (data, index, stream):
            if not loc:
                continue
            loc = str(loc)
            if loc.endswith((".1", ".I", ".S")) and loc.count(".") >= 2:
                m[loc.rsplit(".", 1)[0] + "."] = name   # hashed DDL storage: ^t52S.XCFT.<n>
            else:
                m[loc] = name                             # class storage: ^Graph.KG.LedgerRevisionD
    return m


def store_of(node: str, smap: Dict[str, str]) -> str:
    """The store a journaled global node belongs to: 'sql:<schema.table>' or 'global:<root>'."""
    root = global_root(node)
    for prefix, table in smap.items():
        if prefix.endswith(".") and (root + ".").startswith(prefix) or root == prefix:
            return "sql:" + table
    return "global:" + root


def footprint(recs: List[Dict], smap: Dict[str, str]) -> Dict[str, Set[str]]:
    """Written stores per process: {pid: {store, ...}}, from SET/KILL/ZKILL records."""
    out: Dict[str, Set[str]] = {}
    for r in recs:
        if r["g"]:
            out.setdefault(r["p"], set()).add(store_of(r["g"], smap))
    return out
