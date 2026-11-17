# W53: the SQL readers of the named indexes (kg_IVF, kg_BM25) against the Python readers

Selected from the product-wide inventory after iteration 46: `Graph.KG.SqlProcs` (36 members, none bound). Most of its
members are helpers behind examined paths (`CypherFn_*` behind Cypher, `Txn_*` behind write transactions,
`ledger_records` excluded with the ledger). `kg_IVF` and `kg_BM25` are documented SQL functions (ADMIN_GUIDE privileges
table) that read the same named indexes as `ivf_search` and `bm25_search`: a different final reader. Representative
check; predictions frozen from ADMIN_GUIDE and the API reference.

| ID | Case | Reader | Predicted |
|---|---|---|---|
| S1 | an IVF index of four 4-wide vectors; `SELECT <schema>.kg_IVF(name, <query>, 3, 2)` | its answer vs `ivf_search(name, q, 3, 2)` | the same nodes in the same order, the same scores |
| S2 | a BM25 index over three documents; `SELECT <schema>.kg_BM25(name, 'term', 3)` | vs `bm25_search(name, 'term', 3)` | the same nodes and scores |
| S3 | neighbor: an index name never built | both readers | empty answers, no error |

## Result (iteration 47, fresh run on the fixture: [observation](sqlprocs-observed-20261117T014739Z.json))

The draft of this iteration was stopped before grading; the predictions above were frozen in that draft and are kept
verbatim. Re-run fresh here.

| ID | Held? | Observed |
|---|---|---|
| S1 | held | `kg_IVF` and `ivf_search` both `c` 0.98, `a` 0.9, `b` 0.5 |
| S2 | held | `kg_BM25` and `bm25_search` the same three ids and scores (0.4183). The probe's `bm25_build` takes no `node_ids`, so the index covers every default-graph node with a `text` property, including the stopped draft's `sq011856_*` nodes; the comparison is between two readers of one index and is unaffected |
| S3 | held | `[]` from all four readers for a name never built |

Not predicted, found while reading `IVFIndex.Search` to bind S1: S1's 0.98 for `c` = (0.7,0.7) against q = (0.9,0.5)
is the raw dot product, not the cosine (0.961), although the index was built with the default metric "cosine".
A separate probe ([ivf_cosine_probe.py](ivf_cosine_probe.py), [observation](ivf-cosine-observed-20261117T014744Z.json))
shows the order changes: `long_off` = (10,0,0,0) scores 6.0 above `unit_on` = (0.6,0.8,0,0) at 1.0 for the query
(0.6,0.8,0,0), while `search_nodes_by_vector` on the same vectors ranks `unit_on` 1.0 above `long_off` 0.6.
Registered as [bug-srch-109](../../../Verus_verification/bugs_issues.md#bug-srch-109); owner
[search.ivf.metric](../../../ontology/features/search.g5.md#search.ivf.metric).

Dispositions: `kg_IVF` bound (delegate to `Search`, with `SearchProc`); `kg_BM25` **not bound**: S2 held, but no formal
model decides BM25 search scoring or order (`bm25_counts` covers the counters only), so a binding would cite a claim
that does not constrain the reader. It stays a residual (first missing step: a BM25 `Search` scoring model).
