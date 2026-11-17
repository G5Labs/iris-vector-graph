# Register entries from worker W3 (iteration 56): insert into `.g5/Verus_verification/bugs_issues.md`

Both entries go in the **Low** part of "Findings by severity and evidence scope" (beside bug-tmp-106 / bug-cyp-133).
Paths below are relative to `.g5/Verus_verification/` (as in `bugs_issues.md`). Spares not used: bug-plt-130,
bug-srch-114, bug-tmp-109.

<a id="bug-tmp-108"></a>
### An aggregate read with an empty source or predicate answers 0 when the window only cuts buckets and meets no edge

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: independent review round 3 (session c68a5c59, challenge to the round-2 m2 disposition), on the as-built observation of the iteration-53 probe (`m2_*`). Formal: [temporal_stats](models/temporal_stats/NOTES.md) `get_aggregate_keys`, `theorem_empty_key_quiet_cut_window_answers_zero` (general over every state, graph, key and window), neighbor `theorem_empty_key_raises_with_whole_bucket_or_event`, witness `theorem_empty_key_witness`; controls `empty-key-refused` (the repair) and `empty-key-never-raises`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, iteration 56 ([binding](results/temporal_stats/20261117T065845Z-binding/receipt.json) cases `ek_*`). One edge `ek -P-> a` at T+50 in a fresh graph (T on a 300-second bucket boundary). `get_temporal_aggregate("", "P", "count", T+100, T+200)` answers `0`; `sum` answers `0.0`; `(ek, "", count)` and `("", "", count)` answer `0`. The same empty-source read over [T+10, T+100] (the edge's timestamp in the cut part) raises `RuntimeError: <SUBSCRIPT>GetAggregate+32 ^KG("tout",g,T+50,"")`; over the whole bucket [T, T+299], and over the empty whole bucket [T+300, T+599], it raises `<SUBSCRIPT>GetAggregate+13 ^KG("tagg",g,b,"")`. Neighbor: `(ek, "P", count)` answers 1 over [T+10, T+100] and 0 over [T+100, T+200].

Expected: an aggregate read needs a source and a predicate ([temporal.stats.window](../ontology/features/temporal.g5.md#temporal.stats.window)); no document promises an empty key as a wildcard (USER_GUIDE 1011-1027, the `get_temporal_aggregate` docstring), so an invalid call is refused, the same way whatever the window.

Observed: `GetAggregate` (TemporalIndex.cls 1445-1493) reads `^KG("tagg", g, b, source, predicate, ...)` for a whole bucket and walks `^KG("tout", g, ts)` for a cut one, ordering `^KG("tout", g, ts, source, predicate, o)` at each timestamp present. With an empty source or predicate the first whole bucket or the first timestamp met raises <SUBSCRIPT>; a window that holds no whole bucket and meets no timestamp of its graph (any source's) reads nothing and returns count 0 and sum 0. The Python layer (`get_temporal_aggregate`, `iris_sql_store.get_temporal_aggregate`) passes "" through; for min, max and avg the empty answer then raises the store's `ValueError` (bug-tmp-009) as for any empty window.

Consequence: a caller that passes an empty source by mistake gets a plausible 0 in quiet windows and a server error in busy ones; whether the call is valid depends on the data. Low: it needs an invalid argument, and the Python entry point does not offer an empty source as a feature.

Repair proposal (not implemented): refuse an empty source or predicate in `get_temporal_aggregate` (Python) or at the top of `GetAggregate`, before any read. Preserve: every given-key read (all existing `agg_*` binding cases), the group and target reads where an empty predicate means every predicate. Distinguishing case: `ek_src_quiet_count` refused instead of 0 (control `empty-key-refused` is this repair in the model; it was not run against a patched product). Governing statement: [temporal.stats.window](../ontology/features/temporal.g5.md#temporal.stats.window).

<a id="bug-srch-113"></a>
### The SQL function kg_BM25 answers an empty list for k of 0 or less, while bm25_search and ivg.bm25.search refuse it

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: independent review round 3 (session c68a5c59, minor "kg_BM25 vs bm25_search"). Formal: [bm25_scoring](models/bm25_scoring/NOTES.md) `taken`, `entry_k`, `theorem_sql_k_nonpositive_empty_others_refuse` (general over k and the ranked count); controls `sql-entry-validates-k` (the repair) and `nonpositive-k-takes-all`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, iteration 56 ([binding](results/bm25_scoring/20261117T070040Z-binding/receipt.json) cases `k:*`). Over one built index and the query `graph`: `SELECT Graph_KG.kg_BM25(name, 'graph', 0)` and `(…, -1)` answer `[]`; `bm25_search(name, 'graph', 0)` and `-1` raise a pydantic `ValidationError` (k ≥ 1); `CALL ivg.bm25.search(name, 'graph', 0)` and `-1` raise `ValueError`. Neighbor: k 1 answers the same single top document on all three.

Expected: the three readers apply one argument rule. The translator (`_translate_bm25_search`, translator.py 3161-3166) says the procedure validates "the model bm25_search runs: a name and a query that are not blank, and k of 1 or more (4.6.5)"; ADMIN_GUIDE 256 and 433 list `kg_BM25` as the SQL form of the same search.

Observed: `SqlProcs.kgBM25` (131-135) checks the SELECT privilege and calls `BM25Index.SearchProc` → `Search` → `SearchCore`, which quits its result walk when `count >= k` before taking a document (336-345), so any k ≤ 0 gives `[]` with no error. k is not validated on the SQL path.

Consequence: a direct SQL caller that passes 0 or a negative k (for example a computed limit) silently gets no documents, where the Python and Cypher entries report the bad argument. Low: the caller passes an invalid argument and the answer is empty, not wrong documents.

Repair proposal (not implemented): refuse k < 1 in `SqlProcs.kgBM25` (or `SearchProc`) with an SQL error naming k, as the other two readers do. Preserve: every k ≥ 1 answer (the binding's `sql:*`, `tie:sql` and `k:sql@1` cases). Distinguishing case: `k:sql@0` refused instead of `[]` (control `sql-entry-validates-k` is this repair in the model; not run against a patched product). Governing statement: [search.bm25](../ontology/features/search.g5.md#search.bm25).
