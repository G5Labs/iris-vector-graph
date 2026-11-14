#!/usr/bin/env python3
"""O1 cutoff — binding of the common-term cutoff contract (spec 044 FR-044-C1..C5).

Model: search.rs theorem_cutoff_contract over cutoff()/cut_scan() (SearchCore l.263-293). The expected
`skipped` and `fallback` are computed here from the spec's rule, independently of the implementation:
  - off (fraction 0)             -> nothing skipped, fallback false
  - known terms = query terms with df > 0; over = df / N > fraction
  - every known term over        -> keep the lowest df (ties: first in query order), skip the rest, fallback
  - otherwise                    -> skip exactly the known terms over the bound, no fallback
Documents are inserted with bm25_insert so df is known exactly; df is also read back from bm25_search's
own answers only through the report. Drives bm25_insert, bm25_search(report=True), bm25_drop.
"""
from search_common import connect, engine, ensure_schema, reset, say

IX = "g5pbm25cut"
# 4 documents: qcommon and qalpha and qbeta in all, qmid in 3, qrareone and qraretwo in 1
DOCS = {
    "c:1": "qcommon qalpha qbeta qmid qrareone",
    "c:2": "qcommon qalpha qbeta qmid qraretwo",
    "c:3": "qcommon qalpha qbeta qmid",
    "c:4": "qcommon qalpha qbeta",
}


def expected(query: str, frac: float, df: dict, n: int):
    if not frac > 0:
        return [], False
    toks = query.split()
    known = [t for t in toks if df.get(t, 0) > 0]
    over = {t for t in known if df[t] / n > frac}
    if known and all(t in over for t in known):
        keep = None
        for t in toks:  # first in query order among the minimal df
            if df.get(t, 0) > 0 and (keep is None or df[t] < df[keep]):
                keep = t
        return sorted(set(known) - {keep}), True
    return sorted(over), False


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    try:
        eng.bm25_drop(IX)
    except Exception:
        pass
    for d, text in DOCS.items():
        eng.bm25_insert(IX, d, text)
    df = {}
    for text in DOCS.values():
        for t in set(text.split()):
            df[t] = df.get(t, 0) + 1
    n = len(DOCS)
    cases = [
        ("qcommon qmid", 0.5),            # all known over -> keep qmid (df 3)
        ("qraretwo qrareone qcommon", 0.5),  # some under -> skip qcommon only
        ("qbeta qalpha", 0.5),            # tie at df 4 -> keep qbeta (first)
        ("qnosuchterm qcommon", 0.5),     # df-0 term ignored -> keep qcommon, nothing skipped
        ("qcommon qmid", 0.0),            # off
        ("qalpha qbeta qcommon", 0.99),   # all at 1.0 > 0.99 -> keep qalpha
    ]
    rows = []
    bad = []
    for q, f in cases:
        got = eng.bm25_search(IX, q, 10, max_df_fraction=f, report=True)
        exp_skip, exp_fb = expected(q, f, df, n)
        got_skip = sorted(got["skipped"])
        row = {"query": q, "fraction": f, "expected_skipped": exp_skip, "expected_fallback": exp_fb,
               "skipped": got["skipped"], "fallback": got["fallback"], "results": got["results"]}
        rows.append(row)
        if got_skip != exp_skip or bool(got["fallback"]) != exp_fb:
            bad.append(row)
        if any(df.get(t, 0) > 0 for t in q.split()) and not got["results"]:
            bad.append({**row, "problem": "a query with a known term answered nothing"})
    eng.bm25_drop(IX)
    data = {"df": df, "N": n, "cases": rows}
    if bad:
        say("search_bm25_cutoff", "OBSERVED_DEFECT", f"{len(bad)} case(s) differ from FR-044-C1..C5: {bad[:2]}", data)
    else:
        say("search_bm25_cutoff", "OBSERVED_AS_EXPECTED", f"all {len(cases)} cutoff cases match the contract", data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
