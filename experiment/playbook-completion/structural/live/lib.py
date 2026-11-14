"""Shared harness of the structural lane (namespace AUDITD, observation only).

Rules every live script of this lane follows:
- run under `bash experiment/playbook-completion/tools/locks.sh iris python ...`; at most 6 connections at once;
- be self-contained inside one lock hold: start from `reset()` (the product's own Graph.KG.Eraser.EraseAll and
  Graph.KG.Ledger.PurgeAll, plus the product's own BM25 drop for any index left), never rely on state left by an
  earlier lock hold (other sub-lanes of this lane share AUDITD between holds);
- use only the product's public Python API, deployed Graph.KG class methods through the Native API, or SQL;
  scratch globals only ^IVGAuditD*; nothing compiled into IRIS; no product file touched.

Helpers: conn(), engine(c, **kw), reset(c), capture(c, fn) (journal-oracled write footprint of fn, pid-filtered),
dump(path, obj), session(script) (an `iris session` terminal in AUDITD, nothing compiled), log_path(name).
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                      # experiment/playbook-completion
REPO = ROOT.parents[1]
for p in (ROOT / "tools", ROOT / "traces", REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from iris_conn import Conn, version  # noqa: E402,F401
import journal as J  # noqa: E402

NS = "AUDITD"
DB = "/usr/irissys/mgr/auditd/"
RUN_DIR = Path(os.environ["RUN_DIR"])
OUT = RUN_DIR / "structural"


def conn() -> Conn:
    c = Conn(NS)
    if c.namespace != NS:
        raise RuntimeError("wrong namespace")
    return c


def engine(c: Conn, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    kw.setdefault("embedding_dimension", 4)
    return IRISGraphEngine(c.conn, namespace=NS, **kw)


def reset(c: Conn) -> dict:
    """Empty AUDITD's product content through the product's own erasers (not a product change)."""
    out = {}
    with contextlib.suppress(Exception):
        c.conn.rollback()
    out["erase_all"] = str(c.call("Graph.KG.Eraser", "EraseAll"))
    c.call("Graph.KG.Ledger", "PurgeAll")
    c.conn.commit()
    # Stores EraseAll does not reach (F-0702, F-0606): drop what is left through the product's own commands.
    with contextlib.suppress(Exception):
        names = []
        if int(c.o.isDefined("^BM25Idx")):
            for k, _ in c.o.iterator("^BM25Idx").items():
                if str(k) != "__stop__":
                    names.append(str(k))
        for n in names:
            with contextlib.suppress(Exception):
                c.call("Graph.KG.BM25Index", "Drop", n)
        out["bm25_dropped"] = names
    c.conn.commit()
    return out


def counts(c: Conn) -> dict:
    return {t: c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t}")[0][0]
            for t in ("nodes", "rdf_edges", "rdf_props", "rdf_labels")}


def capture(c: Conn, fn, smap=None):
    """Run fn() and return (result, error, records, footprint) where records are the journal records of c's process
    in AUDITD's database written while fn ran, and footprint the stores they belong to."""
    smap = smap if smap is not None else J.storage_map(c)
    m = J.mark()
    res, err = None, None
    try:
        res = fn()
    except Exception as ex:  # noqa: BLE001
        err = f"{type(ex).__name__}: {str(ex)[:400]}"
    recs = J.records_since(m, dbs={DB}, pids={c.pid})
    fp = sorted(J.footprint(recs, smap).get(c.pid, set()))
    return res, err, recs, fp


def session(script: str, timeout: int = 600) -> str:
    r = subprocess.run(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session", "IRIS", "-U", NS],
                       input=script, capture_output=True, text=True, errors="replace", timeout=timeout)
    return r.stdout.replace("\r", "")


def marked(out: str, tag: str):
    return [ln[1:] for ln in out.split("\n") if ln.startswith("\x1e" + tag + "|")]


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str))


def log_path(name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    return OUT / f"{name}-{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}.json"
