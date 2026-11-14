"""Shared helpers for the graph_structure probes (worker B-structure; product baseline 3eaa79cf).

Read-only use of the product: the probes drive engine methods, the ledger client and SQL on the product's tables,
and read globals only to observe. The expected outcome of each probe is computed from the L1 rule in
.g5/Verus_verification/models/graph_structure/NOTES.md, never from the implementation.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import connect, engine, ensure_schema, record, reset  # noqa: E402,F401

OUT = "out"


def sql_all(conn, sql, args=()):
    cur = conn.cursor()
    try:
        cur.execute(sql, list(args))
        try:
            return [list(r) for r in cur.fetchall()]
        except Exception:
            return []
    finally:
        cur.close()


def sql_exec(conn, sql, args=()):
    cur = conn.cursor()
    try:
        cur.execute(sql, list(args))
    finally:
        cur.close()


def defined(native, *path) -> int:
    try:
        return int(native.isDefined(*path))
    except Exception:
        return -1


def children(native, *path) -> list:
    """Subscripts directly under path (strings or ints as the driver returns them)."""
    out = []
    sub = ""
    while True:
        try:
            sub = native.nextSubscript(False, *path, sub)
        except Exception:
            break
        if sub is None or sub == "":
            break
        out.append(sub)
    return out


def triple_layout(native, gkey, s, p, o) -> dict:
    """^KG("out", gkey, s, p, o): $Data, leaf value, children and "#" (Adjacency.PutKeyed's layout)."""
    d = defined(native, "^KG", OUT, gkey, s, p, o)
    kids = [k for k in children(native, "^KG", OUT, gkey, s, p, o) if str(k) != "#"]
    has_hash = defined(native, "^KG", OUT, gkey, s, p, o, "#") % 10 == 1
    return {
        "data": d,
        "leaf": (d % 10 == 1) if d >= 0 else None,
        "children": [str(k) for k in kids],
        "hash": native.get("^KG", OUT, gkey, s, p, o, "#") if has_hash else None,
        "in_data": defined(native, "^KG", "in", gkey, o, p, s),
    }


def adj_degree(native, gkey, s, pred=""):
    try:
        return int(native.classMethodValue("Graph.KG.Adj", "Degree", gkey, s, pred) or 0)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def adj_count(native, gkey, s, pred=""):
    try:
        return int(native.classMethodValue("Graph.KG.Adj", "Count", gkey, s, pred) or 0)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def adj_cached(native, gkey, s, pred=""):
    """Graph.KG.Adj.Cached: the degree a reader is served from the cache right now ("" when none is current)."""
    try:
        v = native.classMethodValue("Graph.KG.Adj", "Cached", gkey, s, pred)
        return "" if v is None else str(v)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def index_kind(native) -> str:
    try:
        return str(native.classMethodValue("Graph.KG.Adjacency", "IndexKind"))
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def err(e: BaseException) -> dict:
    return {"type": type(e).__name__, "message": str(e)[:500], "trace": traceback.format_exc()[-1500:]}


def finish(name: str, verdict: str, reason: str, obs: dict, self_check: dict | None = None) -> None:
    obs = dict(obs)
    obs["verdict"] = verdict
    obs["reason"] = reason
    if self_check is not None:
        obs["verdict_self_check"] = self_check
    path = record(name, obs)
    print(f"{name}: {verdict} — {reason} ({path})")
