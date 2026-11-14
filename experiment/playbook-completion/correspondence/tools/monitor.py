"""IRIS line-by-line monitor (%Monitor.System.LineByLine) around a scenario: an instance monitor, no product change.

start(d): Start(routines, $lb("RtnLine"), processes="") for the INT routines of common.CLASSES (all processes: the
          scenarios run under the IRIS lock, so no other lane's process runs product code meanwhile).
collect(d): the Result query per routine -> d/monitor.json {routine: [count per INT line]}.
stop(d): Stop.
Counts are per INT line of the compiled class routine; coverage.py maps INT lines to .cls lines.
"""
from __future__ import annotations

import json
from pathlib import Path

from common import CLASSES, NS, marked, session

ROUTINES_FILE = Path(__file__).resolve().parent / "routines.json"


def routines():
    if ROUTINES_FILE.exists():
        return json.loads(ROUTINES_FILE.read_text())
    return [f"{c}.1" for c in CLASSES]


def _lb(items):
    return "$lb(" + ",".join('"' + i + '"' for i in items) + ")"


def discover() -> list:
    """The INT routines of common.CLASSES that exist in AUDITC (^ROUTINE), saved to routines.json."""
    from common import Conn
    c = Conn(NS)
    try:
        names = [f"{cls}.{n}" for cls in CLASSES for n in range(0, 8) if int(c.o.isDefined("^ROUTINE", f"{cls}.{n}"))]
    finally:
        c.close()
    ROUTINES_FILE.write_text(json.dumps(names))
    return names


def start(d: Path) -> None:
    stop(d, quiet=True)  # a monitor left running by an interrupted step
    rl = routines() if ROUTINES_FILE.exists() else discover()
    log = []
    for third in ('""', "$lb()", None):
        arg = "" if third is None else "," + third
        out = session(f' set sc=##class(%Monitor.System.LineByLine).Start({_lb(rl)},$lb("RtnLine"){arg})\n'
                      ' write $c(30),"START|",$system.Status.IsOK(sc),"|",$system.Status.GetErrorText(sc),"|",##class(%Monitor.System.LineByLine).IsActive(),!\n'
                      ' halt\n', ns=NS)
        log.append(out)
        st = marked(out, "START")
        if st and st[0].split("|")[1].startswith("1"):
            (d / "monitor-start.log").write_text("\n----\n".join(log))
            return
    (d / "monitor-start.log").write_text("\n----\n".join(log))
    raise RuntimeError("line monitor did not start: " + log[-1][-800:])


def collect(d: Path) -> None:
    res = {}
    for rtn in routines():
        out = session(' set rs=##class(%ResultSet).%New("%Monitor.System.LineByLine:Result")'
                      f' set sc=rs.Execute("{rtn}") set n=0'
                      ' while rs.Next() { set n=n+1 set v=rs.GetData(1) write $c(30),"L|",n,"|",$select($listvalid(v):$listtostring(v,","),1:v),! }'
                      ' write $c(30),"END|",n,!\n halt\n', ns=NS, timeout=300)
        if not res:
            (d / "monitor-raw-first.log").write_text(out[-20000:])
        counts = []
        for ln in marked(out, "L"):
            _, n, v = ln.split("|", 2)
            first = v.split(",")[0] if v else "0"
            counts.append(int(first or 0) if first.lstrip("-").isdigit() else 0)
        res[rtn] = counts
    (d / "monitor.json").write_text(json.dumps(res))


def stop(d: Path, quiet: bool = False) -> None:
    out = session(' set sc=##class(%Monitor.System.LineByLine).Stop()'
                  ' write $c(30),"STOP|",$system.Status.IsOK(sc),"|",##class(%Monitor.System.LineByLine).IsActive(),!\n halt\n', ns=NS)
    if not quiet:
        (d / "monitor-stop.log").write_text(out)


def clear() -> None:
    """Zero the counters (called at the journal mark, so setup work before the mark is not counted)."""
    out = session(' set sc=##class(%Monitor.System.LineByLine).Clear()'
                  ' write $c(30),"CLEAR|",$system.Status.IsOK(sc),!\n halt\n', ns=NS)
    st = marked(out, "CLEAR")
    if not st or not st[0].split("|")[1].startswith("1"):
        raise RuntimeError("line monitor Clear failed: " + out[-400:])
