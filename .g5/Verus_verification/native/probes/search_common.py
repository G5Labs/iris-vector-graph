"""Shared helpers for the B-search probes (model .g5/Verus_verification/models/search).

Only observation helpers live here: a verdict printer and a read-only walk of ^BM25Idx(name) that
recomputes the L1 counters (spec 044 FR-016/FR-018) by brute force from what is stored. Nothing here
writes to the database.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import _walk, connect, engine, ensure_schema, record, reset  # noqa: E402,F401


def say(name: str, verdict: str, reason: str, data: dict) -> str:
    data = {**data, "verdict": verdict, "reason": reason}
    path = record(name, data)
    print(f"{name}: {verdict} — {reason} [{path}]")
    return verdict


def _list_items(val) -> list:
    import iris

    if val is None or val == "":
        return []
    try:
        lst = val if isinstance(val, iris.IRISList) else iris.IRISList(val)
        out = [lst.get(i) for i in range(1, lst.count() + 1)]
        return [x.decode() if isinstance(x, bytes) else str(x) for x in out]
    except Exception:
        return [f"<undecodable {val!r}>"]


def bm25_state(native, name: str) -> dict:
    """The stored index, read without writing (global walk)."""
    nodes = _walk(native, "^BM25Idx", (name,))
    st = {"tf": {}, "df": {}, "doc": {}, "len": {}, "cfg": {}, "idf_terms": 0}
    for key, val in nodes.items():
        kind = key[1] if len(key) > 1 else None
        if kind == "tf" and len(key) == 4:
            st["tf"][(str(key[2]), str(key[3]))] = int(val)
        elif kind == "df" and len(key) == 3:
            st["df"][str(key[2])] = int(val)
        elif kind == "doc" and len(key) == 3:
            st["doc"][str(key[2])] = _list_items(val)
        elif kind == "len" and len(key) == 3:
            st["len"][str(key[2])] = int(val)
        elif kind == "cfg" and len(key) == 3:
            st["cfg"][str(key[2])] = val
        elif kind == "idf":
            st["idf_terms"] += 1
    return st


def bm25_violations(st: dict) -> list:
    """L1 counter consistency (the model's cons_present), recomputed from tf and len."""
    v = []
    post = {}
    for (t, d) in st["tf"]:
        post.setdefault(t, set()).add(d)
    for t in sorted(set(post) | set(st["df"])):
        want = len(post.get(t, ()))
        got = st["df"].get(t)
        if (got or 0) != want or (got is None) != (want == 0):
            v.append(f"df({t})={got} but {want} posting(s)")
    for d in sorted(set(st["doc"]) | set(st["len"]) | {d for (_, d) in st["tf"]}):
        terms = {t for (t, dd) in st["tf"] if dd == d}
        rec = set(st["doc"].get(d, []))
        if rec != terms:
            v.append(f"doc({d})={sorted(rec)} but postings {sorted(terms)}")
        if d not in st["len"]:
            v.append(f"len({d}) missing")
        elif st["len"][d] != sum(st["tf"][(t, d)] for t in terms):
            v.append(f"len({d})={st['len'][d]} but sum tf={sum(st['tf'][(t, d)] for t in terms)}")
    cfg = st["cfg"]
    n = cfg.get("N")
    if n is not None and int(n) != len(st["len"]):
        v.append(f"N={n} but {len(st['len'])} len node(s)")
    tl = cfg.get("totalLen")
    if tl is not None and int(tl) != sum(st["len"].values()):
        v.append(f"totalLen={tl} but sum len={sum(st['len'].values())}")
    vs = cfg.get("vocab_size")
    if vs is not None and int(vs) != len(st["df"]):
        v.append(f"vocab_size={vs} but {len(st['df'])} df node(s)")
    return v


def tlevel(conn) -> int:
    cur = conn.cursor()
    try:
        cur.execute("SELECT $TLEVEL")
        return int(cur.fetchone()[0])
    finally:
        cur.close()
