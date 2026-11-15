#!/usr/bin/env python3
"""§3.6 capacity, module 07: BM25 terms and document ids near the subscript limit (AUDITD, live).

    locks.sh iris python cap_bm25.py OUT.json

^BM25Idx(name, "tf", term, docId) and the stopword probe $Data(^BM25Idx("__stop__", term)) put a term in a
subscript (BM25Index.cls:83, 194). Cases: a build over documents one of which holds a token of n characters; a
rebuild over an existing good index; bm25_insert and bm25_search with a long token; a 256-character document id
with long terms. Oracle: the call's answer and the index state read back through bm25_search / bm25_info for the
ordinary terms of every document (a document silently missing from an index that reported success is data loss;
an error that leaves no index where a good one was is a destroyed index).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
import lib  # noqa: E402

DOCS = {"bm:1": "alpha bravo", "bm:2": "charlie delta", "bm:3": "echo foxtrot", "bm:4": "golf hotel", "bm:5": "india juliet"}
TERMS = {"bm:1": "alpha", "bm:2": "delta", "bm:3": "echo", "bm:4": "hotel", "bm:5": "juliet"}


def load(eng, docs):
    for nid, text in docs.items():
        eng.create_node(nid, labels=["Doc"], properties={"text": text})


def found(eng, name):
    out = {}
    for nid, term in TERMS.items():
        try:
            r = eng.bm25_search(name, term, k=10)
            ids = [str(x[0] if isinstance(x, (list, tuple)) else (x.get("id") or x.get("node_id"))) for x in (r or [])]
            out[nid] = nid in ids
        except Exception as ex:  # noqa: BLE001
            out[nid] = f"<{type(ex).__name__}: {str(ex)[:120]}>"
    return out


def call(f):
    try:
        return {"ok": True, "answer": str(f())[:300]}
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:300]}"}


def case(label, fn):
    c = lib.conn()
    t0 = time.time()
    try:
        lib.reset(c)
        eng = lib.engine(c)
        r = {"case": label}
        r.update(fn(c, eng))
    except Exception:  # noqa: BLE001
        r = {"case": label, "harness_error": traceback.format_exc()[-1200:]}
    finally:
        try:
            lib.reset(c)
        except Exception:  # noqa: BLE001
            pass
        c.close()
    r["secs"] = round(time.time() - t0, 2)
    print(json.dumps(r, default=str)[:1500], flush=True)
    return r


def build_with_long_token(n):
    def f(c, eng):
        docs = dict(DOCS)
        docs["bm:3"] = "echo " + "z" * n + " foxtrot"
        load(eng, docs)
        b = call(lambda: eng.bm25_build("ix", ["text"]))
        return {"token_len": n, "build": b, "found_after": found(eng, "ix"), "info": call(lambda: eng.bm25_info("ix"))}
    return f


def rebuild_over_good(n):
    def f(c, eng):
        load(eng, DOCS)
        b1 = call(lambda: eng.bm25_build("ix", ["text"]))
        before = found(eng, "ix")
        eng.create_node("bm:6", labels=["Doc"], properties={"text": "kilo " + "y" * n})
        b2 = call(lambda: eng.bm25_build("ix", ["text"]))
        return {"token_len": n, "first_build": b1, "found_before": before, "rebuild": b2, "found_after": found(eng, "ix"),
                "info": call(lambda: eng.bm25_info("ix"))}
    return f


def insert_and_search(n):
    def f(c, eng):
        load(eng, DOCS)
        b = call(lambda: eng.bm25_build("ix", ["text"]))
        ins = call(lambda: eng.bm25_insert("ix", "bm:9", "lima " + "w" * n))
        srch = call(lambda: eng.bm25_search("ix", "w" * n, k=5))
        return {"token_len": n, "build": b, "insert": ins, "search_long": srch, "found_after": found(eng, "ix"),
                "lima_found": call(lambda: eng.bm25_search("ix", "lima", k=5)), "info": call(lambda: eng.bm25_info("ix"))}
    return f


def long_docid(term_len):
    def f(c, eng):
        nid = "d" * 255 + "1"
        docs = dict(DOCS)
        load(eng, docs)
        eng.create_node(nid, labels=["Doc"], properties={"text": "mike " + "t" * term_len})
        b = call(lambda: eng.bm25_build("ix", ["text"]))
        mk = call(lambda: eng.bm25_search("ix", "mike", k=10))
        return {"docid_len": 256, "term_len": term_len, "build": b, "found_after": found(eng, "ix"), "mike": mk,
                "info": call(lambda: eng.bm25_info("ix"))}
    return f


def main() -> int:
    outp = Path(sys.argv[1])
    res = []
    for n in (200, 400, 600, 2000):
        res.append(case(f"07-build-long-token-{n}", build_with_long_token(n)))
        lib.dump(outp, res)
    for n in (600,):
        res.append(case(f"07-rebuild-over-good-index-token-{n}", rebuild_over_good(n)))
        res.append(case(f"07-insert-search-long-token-{n}", insert_and_search(n)))
        lib.dump(outp, res)
    for t in (100, 230, 300):
        res.append(case(f"07-docid-256-term-{t}", long_docid(t)))
        lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
