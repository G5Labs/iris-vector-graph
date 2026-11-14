"""Map an IRIS location `Label+N^Routine` (%SYS.ProcessQuery.CurrentLineAndRoutine) to a pinned .cls file:line,
through the INT text and coverage.map_class's alignment."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import coverage

INT_DIR = Path(os.environ["RUN_DIR"]) / "correspondence" / "probe0"
LOC = re.compile(r"^([%\w]*)\+?(\d*)\^([\w.%]+?)(?:\.(\d+))?$")


@lru_cache(maxsize=None)
def _inverse(cls: str):
    mapping, _ = coverage.map_class(cls, INT_DIR)
    return {(rtn, il): n for n, (rtn, il) in mapping.items()}


@lru_cache(maxsize=None)
def _labels(rtn: str):
    p = INT_DIR / f"{rtn}.int"
    if not p.exists():
        return {}
    lines = p.read_text().split("\n")
    return {name: i for name, (i, _nxt) in coverage.int_methods(lines).items()}


def to_cls(loc: str):
    """'CommitInTxn+19^Graph.KG.Ledger.1' -> ('iris_src/src/Graph/KG/Ledger.cls', 440) or None."""
    if not loc or "^" not in loc:
        return None
    label_off, rtn = loc.split("^", 1)
    label, _, off = label_off.partition("+")
    off = int(off or 0)
    cls = rtn.rsplit(".", 1)[0]
    if label == "":
        il = off      # "+N^Routine": line N of the routine
    else:
        li = _labels(rtn).get(label)
        if li is None:
            return None
        il = li + 1 + off  # 1-based INT line: label line + offset
    n = _inverse(cls).get((rtn, il))
    return (f"iris_src/src/{cls.replace('.', '/')}.cls", n) if n else (rtn, il)
