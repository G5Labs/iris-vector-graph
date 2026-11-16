# W26: BM25 build, incremental writes and scoring — predictions frozen before observation

Frozen 2026-11-16 before any BM25 call. Before image: seal 21 `36f9a1b2`. Exposure: the `search.bm25.*` owners and the
`bm25_build`/`bm25_info` docstrings; `Graph.KG.BM25Index` source not read.

Reference: the owner formula (`idf = ln(1 + (N − df + 0.5)/(df + 0.5))`, k1 1.5, b 0.75), lowercase, split at
punctuation, stopwords removed from documents and queries, length = terms left, IDF and average length at search time.

Corpus (one run-unique text property, default graph): d1 "graph database graph", d2 "graph theory",
d3 "The cat sat", d4 "Graph-DB, fast!".

| Step | Prediction |
|---|---|
| build | N 4, avgdl (3+2+2+3)/4 = 2.5 ("the" dropped), vocab {graph, database, theory, cat, sat, db, fast} = 7 |
| search "graph" | d1 > d4 > d2 or per formula exactly; d3 absent; scores equal the reference |
| search "graph graph" | every score doubles |
| search "the" | no results (stopword) |
| insert d5 "graph" | N 5; the "graph" scores of d1/d2/d4 change (query-time IDF and avgdl) |
| replace d3 with "the and of" | d3 removed: N back to 4 |
| delete absent "nope" | nothing changes |
| replace d1 with "theory" | df(graph) 3 → 2, df(theory) 1 → 2; counts agree with documents |

## Outcome ([observation](bm25-observed-20261116T172500Z.json))

Every prediction held: build N 4, avgdl 2.5, vocab 7; scores equal the owner formula within 1e-6 at every step;
repeated query terms double scores; the stopword query returns nothing; inserting d5 changed the other documents'
scores (query-time IDF); the stopword-only replacement removed d3 (N 4); the absent delete changed nothing; replacing
d1 moved its frequencies. No discrepancy. Formal model and 61-operation count binding: `models/bm25_counts`.
