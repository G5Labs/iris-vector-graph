# BM25 scoring and ranking (W59, iteration 53)

Product `3eaa79cf`, unchanged. Predictions frozen before the deciding source was read:
[bm25-percentile-PAIRS.md](../../../uplift/consolidated/iteration-53/bm25-percentile-PAIRS.md) (commit `5f4d435f`).
Owners: [search.bm25.scoring](../../../ontology/features/search.g5.md#search.bm25.scoring),
[search.bm25.query_time_idf](../../../ontology/features/search.g5.md#search.bm25.query_time_idf),
[search.bm25.cutoff](../../../ontology/features/search.g5.md#search.bm25.cutoff). Counts under incremental writes stay
with [bm25_counts](../bm25_counts/NOTES.md), whose df/N invariant this model relies on (premise P-COUNTS, proved there).

## What the model decides (from inputs)

- **Tokens.** `kept(stop, raw)`: the analyzer's raw tokens (a provider, `%iFind.Utils.Analyze`) minus stopwords, in
  order, repeats kept (`Tokenize` 56-91; the 77 words of `InitStopwords` 41-50).
- **Which occurrences score.** `scored`: known terms (df > 0) not skipped by the common-term cutoff; `over` is
  df × fden > fnum × N; when every known term is over, `min_tok` (the first lowest-df known term) is kept
  (`SearchCore` 263-290). Unknown terms are neither skipped nor kept.
- **The value.** `occ = idf(t) × tfpart`, `score` sums occurrences. `tfpart(tf, len, T, N) = 20 tf T / (8 tf T + 3 T +
  9 len N)` is the exact value of tf (k1 + 1) / (tf + k1 (1 − b + b len / avgdl)) for k1 = 3/2, b = 3/4, avgdl = T/N
  (`SearchCore` 312-318, the parenthesised 4.2.0 form). The IDF is ln of `idf_arg(N, df) = (2N + 2)/(2df + 1)`; ln is
  premise **P-LN** (strictly increasing, positive above 1), so the model proves facts about the argument and the binding
  checks the values natively.
- **Statistics.** `used_arg(schema, …)`: schema 2 reads N and df at search time; schema 1 the stored IDF.
- **Order.** `before(ka, a, kb, b)`: a higher 12-decimal key first, then the lower id (`^||bm25sorted(sortKey, docId)`
  walked with `$Order(…, -1)` over keys and forward over ids, 327-360).
- **The Python reader.** `patch`: `bm25_search`'s `_parse` inserts "0" before ".<digit>" after ':', '[' or ',' anywhere
  in the raw answer, ids included (`vector.py` 1817-1819; F-C0715).

## Theorems (32 verified; no assume, admit or external_body; vstd only)

General: `theorem_stopword_query_empty`, `theorem_repeat_kept`, `theorem_cutoff_off_scores_known`,
`theorem_cutoff_skips_common_term`, `theorem_fallback_keeps_lowest_df`, `theorem_fallback_ignores_unknown_terms`,
`theorem_repeat_adds_twice`, `theorem_unknown_term_adds_nothing`, `theorem_shorter_document_scores_higher`,
`theorem_tf_raises_and_saturates`, `theorem_idf_arg_positive_and_decreasing`, `theorem_ties_by_id`,
`theorem_schema2_reads_current_stats`, neighbor `theorem_schema1_reads_stored`, `theorem_id_without_dot_kept`.
Witnesses: `theorem_worked_example` (USER_GUIDE's 1.347: factor 320/233, argument 8/3),
`theorem_id_with_colon_dot_digit_rewritten` (F-C0715, "c:.5x" → "c:0.5x").

## Controls (9, all EXPECTED_FAIL in their named theorems)

`stopwords-kept`, `query-terms-deduplicated`, `unknown-terms-scored`, `no-fallback`, `left-to-right-denominator` (the
pre-4.2.0 bug), `idf-without-plus-one` (classic Robertson IDF, negative for common terms), `ties-by-key-only`,
`schema2-reads-stored`, `parse-keeps-ids` (F-C0715's repair direction).

Kept runs: `20261117T051339Z-control-unknown-terms-scored` SURVIVED. The control then replaced the `df = 0` guard in
`scored` only, and the theorems were phrased with `known`, so the change made them vacuous; nothing observable at the
reader depends on that guard alone (an unknown term has no posting list). The control now changes `known` itself (an
unknown term can then be the cutoff's lowest-df term), the theorems are stated on df, and
`theorem_fallback_ignores_unknown_terms` was added. `20261117T051402Z` FAIL_ELSEWHERE named a vacuous theorem;
`20261117T051422Z-prove` failed one step of the new theorem (fixed). Final:
[prove](../../results/bm25_scoring/20261117T051500Z-prove/receipt.json) and the `20261117T0515*` controls.

## Binding

[Receipt](../../results/bm25_scoring/20261117T051620Z-binding/receipt.json): **AGREES 46 cases**, all 9 mutations and
the tamper detected. Readers: `bm25_search` (Python), `BM25Index.Search`'s raw answer, `bm25_search(report=True)` for
the cutoff, SQL `kg_BM25`, `CALL ivg.bm25.search`; an incremental insert and delete against a fresh build over the
same documents. Expected values from the port (the stopword list as USER_GUIDE prints it, a plain splitter, statistics
from the written corpus, `math.log` for P-LN); relative tolerance 1e-12. The Cypher `score` column reads as a
`Decimal`; the binding compares it as a number.

## Premises and limits

- P-LN (ln), P-COUNTS (df and N agree with the documents after writes; `bm25_counts`), P-ANALYZER (the IRIS analyzer
  splits the binding's corpus as a plain punctuation splitter does; USER_GUIDE's examples), P-KEY (12-decimal keys
  separate distinct scores; scores closer than 1e-12 tie).
- Not modeled: `Build`'s graph-scoped SELECT, `Insert`/`Delete` locking and transactions (bm25_counts and the write
  lock owner), schema-1 `Upgrade`, `SearchReport`'s skipped-term order (q-srch-005; the binding compares a set),
  `kg_BM25`'s rdf_props privilege check (W53).
