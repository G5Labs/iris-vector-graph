"""Live IRIS access for the erasure -> redaction -> replay scenarios (playbook §3.7).

Every connection is checked against the dedicated container ($IVG_TEST_CONTAINER) with the same identity probe the
upstream fixtures use, so a scenario can never run against another database. One connection is one IRIS process,
which is what lets a scenario hold a lock in one process while another redacts.

Run from the repository root with the experiment environment ($RUN_DIR/environment.sh) sourced.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import iris  # noqa: E402
import iris.dbapi  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402
from tests import conftest as fixtures  # noqa: E402

SCHEMA = "Graph_KG"
CONTENT_TABLES = ("nodes", "rdf_labels", "rdf_props", "rdf_edges")


class Conn:
    """One DBAPI connection, its Native API handle and its engine: one IRIS process."""

    def __init__(self) -> None:
        container = os.environ["IVG_TEST_CONTAINER"]
        self.conn = iris.dbapi.connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]),
                                       namespace=os.environ.get("IVG_NAMESPACE", "USER"),
                                       username="_SYSTEM", password="SYS")
        actual = fixtures.probe_instance_hostname(self.conn)
        if not fixtures.container_hostname_matches(actual, fixtures.docker_container_hostname(container),
                                                   fixtures.docker_container_id(container)):
            self.conn.close()
            raise RuntimeError(f"database identity does not match {container}")
        self.o = iris.createIRIS(self.conn)
        self.eng = IRISGraphEngine(self.conn, embedding_dimension=4)
        self.pid = str(self.o.classMethodValue("%SYSTEM.SYS", "ProcessID"))

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()

    # -- server calls ------------------------------------------------------------------------------------------
    def call(self, cls: str, method: str, *args) -> Any:
        return self.o.classMethodValue(cls, method, *args)

    def redact_raw(self, graph: str = "", prefix: str = "", batch: int = 2000, max_batches: int = 0,
                   actor: str = "") -> Dict[str, Any]:
        """Graph.KG.LedgerRedact.Redact as the server answers it (JSON), without the Python error mapping."""
        out = str(self.call("Graph.KG.LedgerRedact", "Redact", graph, prefix, "|", actor, batch, max_batches, SCHEMA))
        if out.startswith("CHUNKED:"):
            _, tag, n = out.split(":")
            out = "".join(str(self.call("Graph.KG.Ledger", "ReadLargeOutChunk", tag, i)) for i in range(1, int(n) + 1))
        return json.loads(out)

    def sql(self, q: str, *params) -> List[Tuple]:
        cur = self.conn.cursor()
        try:
            cur.execute(q, params) if params else cur.execute(q)
            return [tuple(r) for r in cur.fetchall()] if cur.description else []
        finally:
            cur.close()


def terminate(killer: Conn, pid: str) -> int:
    """Stop an IRIS process by its recorded pid (never by pattern)."""
    return int(killer.call("%SYSTEM.Process", "Terminate", pid) or 0)


def reset(c: Conn) -> None:
    """Empty every store and the ledger of the dedicated namespace."""
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    c.o.kill("^IVGUplift")
    with contextlib.suppress(Exception):
        c.conn.commit()


# ---------------------------------------------------------------------------------------------------------------
# observation: the L2 state as stored (globals and tables), decoded


def _decode(v) -> Any:
    if isinstance(v, (bytes, bytearray)):
        try:
            lst = iris.IRISList(bytes(v))
            return [_decode(lst.get(i)) for i in range(1, lst.count() + 1)]
        except Exception:
            return bytes(v).decode("utf-8", "replace")
    if v is None:
        return ""
    return str(v) if not isinstance(v, (int, float)) else str(v)


def walk(o, gname: str, subs: Tuple = ()):
    d = int(o.isDefined(gname, *subs))
    if d in (1, 11):
        yield subs, o.getBytes(gname, *subs)
    if d >= 10:
        for sub, _ in o.iterator(gname, *subs).items():
            yield from walk(o, gname, subs + (sub,))


def lb(o, gname: str, *subs) -> List[str]:
    lst = o.getIRISList(gname, *subs)
    if lst is None:
        return []
    out = []
    for i in range(1, lst.count() + 1):
        x = lst.get(i)
        out.append("" if x is None else (x.decode("utf-8", "replace") if isinstance(x, (bytes, bytearray)) else str(x)))
    return out


def observe(c: Conn) -> Dict[str, Any]:
    """Everything the slice's invariants read, in one JSON-able object (sorted, deterministic)."""
    o = c.o
    rec: Dict[str, List[str]] = {}
    for subs, _ in walk(o, "^IVG.Ledger", ("rec",)):
        if len(subs) == 3:
            rec[f"{int(subs[1])}:{int(subs[2])}"] = lb(o, "^IVG.Ledger", *subs)
    stmt = {str(s[1]): lb(o, "^IVG.Ledger", *s) for s, _ in walk(o, "^IVG.Ledger", ("stmt",)) if len(s) == 2}
    tup = sorted([list(map(str, s[1:])) + [str(o.get("^IVG.Ledger", *s))] for s, _ in walk(o, "^IVG.Ledger", ("tuple",))
                  if len(s) == 5])
    idem = {str(s[1]): lb(o, "^IVG.Ledger", *s) for s, _ in walk(o, "^IVG.Ledger", ("idem",)) if len(s) == 2}
    idem_red = {str(s[1]): str(o.get("^IVG.Ledger", *s)) for s, _ in walk(o, "^IVG.Ledger", ("idemRedacted",))
                if len(s) == 2}
    red_rev = sorted(int(s[1]) for s, _ in walk(o, "^IVG.Ledger", ("redactedRev",)) if len(s) == 2)
    marker = lb(o, "^IVG.Ledger", "redacting") if int(o.isDefined("^IVG.Ledger", "redacting")) in (1, 11) else None
    redacting_revs = {str(s[2]): str(o.get("^IVG.Ledger", *s)) for s, _ in walk(o, "^IVG.Ledger", ("redacting", "revs"))
                      if len(s) == 3}
    counters = {str(s[2]): str(o.get("^IVG.Ledger", *s)) for s, _ in walk(o, "^IVG.Ledger", ("redacting", "n"))
                if len(s) == 3}
    revs = {}
    for row in c.sql(f"SELECT seq, revision_id, parent_id, kind, actor, message, source, correlation_id, "
                     f"idempotency_key, op_count FROM {SCHEMA}.ledger_revisions ORDER BY seq"):
        seq, rid, parent, kind, actor, msg, src, corr, key, ops = row
        revs[str(int(seq))] = {"revision_id": rid, "parent_id": parent or "", "kind": kind, "actor": actor,
                               "message": msg or "", "source": src or "", "correlation_id": corr or "",
                               "idempotency_key": key or "", "op_count": int(ops or 0)}
    content = {
        "nodes": sorted([[g or "", n] for n, g in c.sql(f"SELECT node_id, graph_id FROM {SCHEMA}.nodes")]),
        "labels": sorted([[g or "", s, l] for s, l, g in c.sql(f"SELECT s, label, graph_id FROM {SCHEMA}.rdf_labels")]),
        "props": sorted([[g or "", s, k, "" if v is None else str(v)]
                         for s, k, v, g in c.sql(f'SELECT s, "key", val, graph_id FROM {SCHEMA}.rdf_props')]),
        "edges": sorted([[g or "", s, p, o_, q or ""]
                         for s, p, o_, g, q in c.sql(f"SELECT s, p, o_id, graph_id, qualifiers FROM {SCHEMA}.rdf_edges")]),
    }
    return {"head": str(o.get("^IVG.Ledger", "head") or "0"), "state": str(o.get("^IVG.Ledger", "meta", "state") or ""),
            "rec": dict(sorted(rec.items(), key=lambda kv: tuple(map(int, kv[0].split(":"))))),
            "stmt": stmt, "tuple": tup, "idem": idem, "idemRedacted": idem_red, "redactedRev": red_rev,
            "marker": marker, "redactingRevs": redacting_revs, "counters": counters, "revisions": revs,
            "content": content}


def digest(state: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def strings_in(state: Dict[str, Any], needles) -> List[str]:
    """Every needle found anywhere in the ledger part of an observation (records, maps, revision rows)."""
    ledger = {k: v for k, v in state.items() if k != "content"}
    text = json.dumps(ledger, sort_keys=True)
    return [n for n in needles if n in text]


# ---------------------------------------------------------------------------------------------------------------
# threads and locks


class Background:
    """Run fn(conn) on its own connection (its own IRIS process) in a thread."""

    def __init__(self, fn, name: str):
        self.c = Conn()
        self.name, self.result, self.error = name, None, None
        self.t = threading.Thread(target=self._run, args=(fn,), daemon=True)

    def _run(self, fn):
        try:
            self.result = fn(self.c)
        except BaseException as e:  # a terminated process surfaces here
            self.error = f"{type(e).__name__}: {e}"

    def start(self) -> "Background":
        self.t.start()
        return self

    def join(self, timeout: float) -> bool:
        self.t.join(timeout)
        return not self.t.is_alive()


def wait_until(pred, timeout: float, step: float = 0.002) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(step)
    return False


def lock_waiters(c: Conn, pid: str) -> bool:
    """True when process pid is waiting for a lock (its state is LOCKW or its routine is in a Lock wait)."""
    st = str(c.call("%SYSTEM.Process", "State", pid) or "")
    return "LOCK" in st.upper()


def load_class(c: Conn, name: str, text: str) -> None:
    """Put a class's UDL text into the namespace and compile it (no files in the container)."""
    sc = c.call("%Compiler.UDL.TextServices", "SetTextFromString", os.environ.get("IVG_NAMESPACE", "USER"),
                f"{name}.cls", "\r\n".join(text.splitlines()))
    if str(sc) != "1":
        raise RuntimeError(f"SetTextFromString {name}: {c.call('%SYSTEM.Status', 'GetErrorText', sc)}")
    sc = c.call("%SYSTEM.OBJ", "Compile", name, "ck-d")
    if str(sc) != "1":
        raise RuntimeError(f"Compile {name}: {c.call('%SYSTEM.Status', 'GetErrorText', sc)}")


def load_probe(c: Conn) -> None:
    load_class(c, "IVGUplift.Probe", (Path(__file__).parent / "cls" / "IVGUplift.Probe.cls").read_text())


def pin_class_text(name: str) -> str:
    """A product class's source exactly as it is at the pin (for restoring after a mutant)."""
    import subprocess
    path = "iris_src/src/" + name.replace(".", "/") + ".cls"
    return subprocess.run(["git", "-C", str(REPO), "show", f"3eaa79cf:{path}"], capture_output=True, text=True,
                          check=True).stdout
