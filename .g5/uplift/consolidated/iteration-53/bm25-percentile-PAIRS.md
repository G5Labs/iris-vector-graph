# W59 (iteration 53, Part B): BM25 scoring and percentiles — predictions frozen before reading deciding source

Frozen before opening any deciding body: `BM25Index.cls` (Tokenize, Build, IndexDoc, SearchCore, …), `SqlProcs.cls`
(`kgBM25`, `PercentilePDISC/PCONT`), `IVG/Percentile.cls` bodies, the translator's emit code for `ivg.bm25.search`
and `percentileDisc/Cont`, `_engine/vector.py` bm25 bodies, and tests.

Sources used: USER_GUIDE "BM25 text search" (formula, worked example 1.347, tokenizer, the 77 stopwords) and the
procedure table; API_REFERENCE `bm25_build`/`bm25_search`/`bm25_insert`/`bm25_delete`; CHANGELOG (common-term cutoff
and fallback, schema 2 query-time IDF, score text below 1, sort-key fix, `k` below 1 refused, `percentileCont` over
no rows null, `IVG.Percentile` "(n-1)*p formula"); docstrings extracted without bodies (`BM25Index.Build`, `Search`,
`SearchReport`, `Insert`, `Delete`, `List`; `Percentile.PDISC`, `PCONT`, `SortArray`; Python `bm25_build`,
`bm25_search`); owners `search.bm25`, `search.bm25.scoring`, `search.bm25.query_time_idf`,
`query.functions.percentile`; the `bm25_counts` model and the iteration-22 panel (which already held "scores equal the
formula", "a repeated query term doubles", "a stopword query answers nothing", "an insert changes others' scores").
The rows below add neighbors not yet checked.

Expected scores are the owner formula computed in Python (k1 1.5, b 0.75), rounded to 6 places; tolerance 1e-6.

## Workflow B1: BM25 score and rank (`bm25_search`, the reader; `kg_BM25` and `CALL ivg.bm25.search` beside it)

Corpus, one property `t` per node, built with `bm25_build(name, ["t"])`:
`d1` "graph database graph", `d2` "vector database", `d3` "The graph of things", `d4` "state-of-the-art graph",
`d5` "über vector", `d6` "vector database". After tokenizing and stopword removal (the, of): lengths 3, 2, 2, 3, 2, 2;
N 6; avgdl 14/6.

| # | Changing input | Reader | Predicted | Source |
|---|---|---|---|---|
| B1a | query `graph` vs `Graph!` | `bm25_search(name, q, 10)` | both `d1` 0.906922 > `d3` 0.740768 > `d4` 0.614181; `d3`'s stopwords count in neither its length nor the score; case and punctuation do not change the answer | owner scoring; USER_GUIDE tokenizer |
| B1b | query `the` (stopword only) vs `things` | same | `the` → `[]`; `things` → `d3` 1.646277 only | USER_GUIDE stopwords |
| B1c | query `über` vs `uber` | same | `über` → `d5` only; `uber` → `[]` (accents kept, no folding) | USER_GUIDE |
| B1d | query `state art` vs `state-of-the-art` | same | both `d4` 2.729903 only (the hyphenated query splits into the same terms; of/the dropped) | USER_GUIDE |
| B1e | ties: query `vector` (d2, d5, d6 all length 2, tf 1) with k 10 vs k 2 | same | k 10: three hits, each 0.740768; k 2: exactly two of them. Order among equal scores is not documented; frozen guess: all tied hits kept (no hit lost to a shared sort key) | owner "top k by score"; CHANGELOG sort-key fix |
| B1f | `max_df_fraction` 0 vs 0.4, query `graph things` | `bm25_search(..., max_df_fraction=x, report=True)` | 0: `d3` (graph+things) first, `d1`, `d4`; 0.4: `graph` (df 3/6 = 0.5) skipped, only `d3` 1.646277; `skipped` = `["graph"]`, `fallback` false | CHANGELOG cutoff; `Search` docstring |
| B1g | `max_df_fraction` 0.4, query `graph` alone | same | every term over the cutoff, so the lowest-df term is kept: the same three hits and scores as with 0; `fallback` true | `Search` docstring |
| B1h | query `zzz graph` (a term no document holds) | `bm25_search` | same answer as `graph` (adds nothing) | USER_GUIDE |
| B1i | `k` 0 vs 1 | `bm25_search` | k 0 raises (refused); k 1 → `[d1]` | CHANGELOG (k below 1 refused) |

## Workflow B2: query-time IDF after incremental writes vs a fresh build

| # | Changing input | Reader | Predicted | Source |
|---|---|---|---|---|
| B2a | `bm25_insert(name, "d7", "graph")` vs a fresh `bm25_build` over d1..d7 | `bm25_search(name, "graph")` | identical answers within 1e-6: `d7` 0.757058, `d1` 0.728309, `d3` 0.593159, `d4` 0.487597 (N 7, df 4, avgdl recomputed at search time) | `search.bm25.query_time_idf` |
| B2b | `bm25_delete(name, "d1")` vs fresh build without d1 | same | identical: `d3` 0.912811, `d4` 0.752356 | same |

## Workflow B3: the SQL and Cypher readers agree with the Python reader

| # | Changing input | Reader | Predicted | Source |
|---|---|---|---|---|
| B3a | the same index and query `graph` | `SELECT Graph_KG.kg_BM25(name, 'graph', 3)` (JSON text) vs `bm25_search` | same ids, same order, same scores (as iteration 47 S2) | ADMIN_GUIDE function list; procedure table |
| B3b | the same | `CALL ivg.bm25.search(name, 'graph', 3) YIELD node, score` | same ids and scores; `score` a number | USER_GUIDE example |

## Workflow P1: percentileDisc and percentileCont

Reader: Cypher `UNWIND $xs AS x RETURN percentileDisc(x, $p), percentileCont(x, $p)` (and, beside it, the SQL
functions `Percentile_PDISC/PCONT('[…]', p)`).

| # | Changing input | Predicted (Disc, Cont) | Source |
|---|---|---|---|
| P1a | [10, 20, 30, 40], p 0.5 vs [10, 20, 30], p 0.5 | (20, 25.0) vs (20, 20.0) | owner (Neo4j example) |
| P1b | [10, 20, 30, 40], p 0.6 vs p 0.9 | nearest rank (ceil(p·n)): (30, 28.0) vs (40, 37.0). If the product instead uses floor((n−1)·p) for Disc (CHANGELOG "(n-1)*p formula"), Disc would be 20 and 30 — the frozen prediction follows the owner ("nearest rank") | owner; CHANGELOG |
| P1c | p 0 vs p 1 over [30, 10, 20, 40] (unsorted input) | (10, 10.0) vs (40, 40.0); input order does not matter | owner; `SortArray` docstring |
| P1d | [10, null, 30] vs [] (all null / no rows), p 0.5 | (10 or 30 by the rule: n 2, ceil(1) → 10; Cont 20.0) vs (null, null) | owner; CHANGELOG (Cont over no rows null) |
| P1e | p 1.5 vs p −0.1 | both fail with NumberOutOfRange | owner |
| P1f | [10, 10, 20, 30], p 0.5 | (10, 15.0): duplicates keep their ranks | owner |
| P1g | Disc type: [1, 2, 3] p 0.5 | Disc 2 an integer (the stored value), Cont 2.0 a float | owner "returns the stored value" |
