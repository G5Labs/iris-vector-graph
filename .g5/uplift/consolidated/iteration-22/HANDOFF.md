# Iteration 22: BM25 text search counts and scoring

Before image: seal 21 `36f9a1b2`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only.

BM25 had detailed owners (`search.bm25.*`) but no model and no source binding. Predictions derived from the owner
formula and count rules were frozen before observation ([PAIRS](bm25-PAIRS.md)); every one held: build counts, scores
within 1e-6 at every step, repeated query terms, stopword queries, query-time IDF after inserts, stopword-only
replacement removing the document, absent delete as a no-op, replacement moving frequencies. No discrepancy.

New model [bm25_counts](../../../Verus_verification/models/bm25_counts/NOTES.md): 7 verified, no imports. It proves
that incremental `Insert`/`RemoveDoc`/`Delete`, as transcribed, preserve the owner invariant (df = documents holding the
term, N = documents) for every sequence, not just the panel. Four controls, all EXPECTED_FAIL. The native binding reads
the stored `^BM25Idx` globals after each of 61 seeded operations: 244 comparisons, AGREES, all mutations detected,
and `vocab_size` matches a recount (observed, not modeled). `search.bm25.counts` and `.scoring` gain Verus/evidence
metadata.

Reach **273 → 278 of 4,130** ([delta](member-delta.json)): `BM25Index.cls::Insert`, `::RemoveDoc`, `::Delete`,
`VectorMixin.bm25_insert`, `VectorMixin.bm25_delete`. Lost: none.

Gates: `check_consolidated.py` PASS; `check_ontology.py` 453 blocks, 0 issues; `check_findings.py` no problems;
[12 freshness cases](freshness-controls.json); [correspondence stamp](correspondence-inputs.json).

Cost: about 17:24–17:35 UTC. Tokens and currency unavailable.
