# BM25 index counts under incremental writes

Product `3eaa79cf`, unchanged. Iteration 22 (cloud continuation). Predictions frozen before native observation in
[bm25-PAIRS.md](../../../uplift/consolidated/iteration-22/bm25-PAIRS.md). Owner:
[search.bm25.counts](../../../ontology/features/search.g5.md#search.bm25.counts).

## What the model decides

An index is its documents (each a set of distinct terms; tokenization is a provider), the stored document frequency
per term (0 meaning no entry, since the writer kills the node at zero) and N. `remove` transcribes `RemoveDoc`: an
absent document changes nothing; otherwise each of its terms loses one and N drops by one. `insert` transcribes
`Insert`: remove the old record, then add the new one only if it has terms. The ObjectScript loops visit each
distinct term once (the `tfMap` keys and the stored record), so their effect is the pointwise update modeled here
(inspected transcription).

## Theorems (7, all new; no imports)

`theorem_remove_consistent` and `theorem_insert_consistent` prove that every write preserves the owner's invariant:
each term's df equals the number of documents holding it, and N equals the number of documents. Also
`theorem_empty_replacement_removes`, `theorem_absent_delete_is_noop` and `theorem_replace_keeps_n`, plus the two
counting lemmas. Not modeled: `vocab_size` and `totalLen` arithmetic (checked natively below), the full `Build`,
`Upgrade`, locking, transactions, concurrency and scoring (`ln` in IDF). No `assume`, `admit` or `external_body`.

## Controls and binding

Four controls, all EXPECTED_FAIL full and isolated: `remove-keeps-df`, `insert-without-remove`, `empty-text-indexed`,
`absent-delete-decrements`.

[Binding](../../results/bm25_counts/): a seeded sequence of 61 inserts, replacements and deletes (including empty and
stopword-only texts and an absent delete) through `bm25_insert`/`bm25_delete` on the fixture. After each operation the
stored `^BM25Idx` df entries, N, document records and `vocab_size` are read over the Native API and compared with the
port and with a recount: 244 comparisons, AGREES; each mutation detected by 46–61 operations. The scoring panel in
the PAIRS file separately matched the owner formula within 1e-6 after build and after incremental writes.
