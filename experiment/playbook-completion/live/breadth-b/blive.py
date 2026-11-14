"""Shared helpers for breadth lane B live checks (modules 07..11) on IRIS namespace AUDITB only.

Rules (CONVENTIONS.md): run every script that uses this module under `bash experiment/playbook-completion/tools/locks.sh iris python ...` (container-wide 8-connection cap; open at most 6 connections);
the product is used only through the pin's public Python API, deployed class methods and SQL;
nothing is compiled; scratch data uses graph ids / node ids prefixed with the check's own tag and is removed by the
check; namespace-wide state a check changes (ledger state, compile mode, BM25 indexes, caches) is restored before the
lane lock is released.

    from blive import session, capture, write_log
    with session("07-build-drop") as s:          # takes the lane-B AUDITB lock, opens Conn("AUDITB") + engine
        cap = capture(s, lambda: s.eng.bm25_build("b07x", ["name"], graph="b07g"))
        ...
        write_log(s, {"footprint": cap.footprint_json(), ...})

`capture` runs an operation between two journal marks and returns the journal records of the AUDITB database, the
written stores per process (journal.footprint over storage_map), the transaction grouping (journal.transactions) and
the operation's result or exception. The journal is written by IRIS itself, so it is an independent oracle for what an
operation wrote and inside which transaction.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parents[1]
REPO = COMPLETION.parents[1]
for p in (COMPLETION / "tools", COMPLETION / "traces", REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import logging  # noqa: E402

logging.getLogger().setLevel(logging.ERROR)

from iris_conn import Conn  # noqa: E402
import journal as J  # noqa: E402

NAMESPACE = "AUDITB"
DB = "/usr/irissys/mgr/auditb/"
RUN_DIR = Path(os.environ["RUN_DIR"])
LOG_DIR = RUN_DIR / "breadth-b" / "live"
LOCK = RUN_DIR / "breadth-b" / "auditb.lock"


def open_conn(attempts: int = 6, wait_s: float = 5.0) -> Conn:
    """Conn("AUDITB") with retries on license-allocation failures (infrastructure, CONVENTIONS "Connection cap"; the
    identity probe reports a mismatch when the license is refused). Run every IRIS command under
    `tools/locks.sh iris` so this is rarely needed; a failure after all attempts raises and is never a product result."""
    last = None
    for i in range(attempts):
        try:
            return Conn(NAMESPACE)
        except Exception as e:  # noqa: BLE001
            last = e
            msg = str(e)
            if "license" in msg.lower() or "identity" in msg.lower() or "allocate" in msg.lower():
                time.sleep(wait_s * (i + 1))
                continue
            raise
    raise RuntimeError(f"INFRASTRUCTURE: could not connect to AUDITB after {attempts} attempts: {last}")


@contextlib.contextmanager
def lane_lock(timeout_s: float = 3600.0):
    """Exclusive use of AUDITB among lane-B workers (every wait has a timeout)."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    f = open(LOCK, "w")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() - t0 > timeout_s:
                f.close()
                raise TimeoutError("AUDITB lane lock not acquired")
            time.sleep(0.5)
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


@dataclass
class Session:
    name: str
    c: Conn
    eng: Any
    smap: Dict[str, str]
    started: float = field(default_factory=time.time)
    extra_conns: List[Conn] = field(default_factory=list)

    def conn2(self) -> Conn:
        """A second IRIS process on AUDITB (another server process: its own transactions and locks)."""
        c = open_conn()
        self.extra_conns.append(c)
        return c

    def engine_on(self, c: Conn, **kw):
        from iris_vector_graph.engine import IRISGraphEngine
        return IRISGraphEngine(c.conn, namespace=NAMESPACE, **kw)


def make_engine(c: Conn, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    kw.setdefault("embedding_dimension", 4)
    return IRISGraphEngine(c.conn, namespace=NAMESPACE, **kw)


@contextlib.contextmanager
def session(name: str, lock: bool = True, **engine_kw):
    cm = lane_lock() if lock else contextlib.nullcontext()
    with cm:
        c = open_conn()
        try:
            eng = make_engine(c, **engine_kw)
            smap = J.storage_map(c)
            s = Session(name, c, eng, smap)
            yield s
        finally:
            for x in getattr(locals().get("s"), "extra_conns", []) or []:
                x.close()
            c.close()


@dataclass
class Capture:
    result: Any
    error: Optional[str]
    records: List[Dict]
    footprint: Dict[str, set]
    txns: List[Dict]
    seconds: float

    def footprint_json(self) -> Dict[str, List[str]]:
        return {p: sorted(v) for p, v in self.footprint.items()}

    def stores(self, pid: Optional[str] = None) -> List[str]:
        if pid is None:
            return sorted({x for v in self.footprint.values() for x in v})
        return sorted(self.footprint.get(pid, set()))

    def txn_summary(self, smap: Dict[str, str]) -> List[Dict]:
        out = []
        for u in self.txns:
            out.append({"pid": u["pid"], "kind": u["kind"], "committed": u["committed"],
                        "rolled_back": u.get("rolled_back"), "nested_levels": u.get("nested_levels", 0),
                        "n": len(u["records"]),
                        "stores": sorted({J.store_of(r["g"], smap) for r in u["records"] if r["g"]})})
        return out

    def writes_outside_txn(self, smap: Dict[str, str]) -> List[Dict]:
        return [{"pid": r["p"], "t": r["t"], "store": J.store_of(r["g"], smap), "g": r["g"]}
                for r in self.records if r["g"] and not r["x"]]


def capture(s: Session, op: Callable[[], Any], pids: Optional[set] = None, settle: float = 0.0) -> Capture:
    m = J.mark()
    t0 = time.time()
    res, err = None, None
    try:
        res = op()
    except Exception as e:  # recorded, not hidden: the caller decides what an error means
        err = f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    if settle:
        time.sleep(settle)
    recs = J.records_since(m, dbs={DB}, pids=pids)
    # transaction markers carry no database: keep only processes that wrote AUDITB, or that we asked for
    wrote = {r["p"] for r in recs if r["g"]}
    keep = pids if pids is not None else wrote
    recs = [r for r in recs if r["p"] in keep]
    fp = J.footprint(recs, s.smap)
    tx = J.transactions(recs)
    return Capture(res, err, recs, fp, tx, dt)


def write_log(s: Session, obj: Dict, name: Optional[str] = None) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = LOG_DIR / f"{name or s.name}.json"
    obj = {"check": name or s.name, "namespace": NAMESPACE, "server_pid": s.c.pid,
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **obj}
    p.write_text(json.dumps(obj, indent=1, default=_default, sort_keys=False) + "\n")
    return p


def _default(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    return repr(o)


def gget(c: Conn, *subs, root: str):
    """Value of a global node, or None (Native API)."""
    try:
        if c.o.isDefined(root, *subs) % 10 == 1:
            return c.o.get(root, *subs)
    except Exception:
        return None
    return None


def gdefined(c: Conn, root: str, *subs) -> int:
    return int(c.o.isDefined(root, *subs))


def gsubs(c: Conn, root: str, *subs) -> List[Any]:
    """First-level subscripts under ^root(subs...)."""
    out = []
    it = c.o.iterator(root, *subs)
    for k in it.subscripts():
        out.append(k)
    return out


def tb() -> str:
    return traceback.format_exc()
