# Manage search indexes

Inspect available embedding routes, build an IVF index, or upgrade a BM25 index. See [search](../features/search.g5.md) for query results and [search storage and indexes](../architecture/search-storage-and-indexes.g5.md) for index maintenance.

## Definitions

- **Route**: the one table that holds a given graph's vectors of a given model and kind (node or edge). A **routed table** is a route created for one graph and model.
- **Named search index**: an index a caller builds and searches by name, apart from the embedding tables: BM25 for text, and IVF, VecIndex and PLAID for vectors. PLAID keeps several vectors per document.
- **BM25 index**: a named lexical index over the text of one graph's nodes. Each node is a **document**, and its **terms** are the words left after tokenizing.
- **Index schema**: the version of a BM25 index's stored layout. Schema 1 is the original; schema 2 adds document frequencies and token records.

## Inspect embedding routes

<a id="search.routes.inventory"></a>
[I · search.routes.inventory]

The embedding inventory reports one row per route and one row for each graph that has nodes but no route, and reading it creates nothing.

- A route's row gives its width and type, its vector count inside its own graph, and whether IRIS holds an ANN index on its table.
- A graph's no-route row names no table, counts 0 and shows no index; a graph with a route gets no such row.
- `ivg embeddings inventory` prints the same rows, straight from IRIS, and counts as routed tables only the rows that name a table.

## Building an IVF index

<a id="search.scope.indexes.ivf"></a>
[I · search.scope.indexes.ivf]

An IVF build reads vectors from the requested graph and model's route, never another pair's table. If the pair has no route, it raises an error before reading any vector table or starting the index build; a routed selection with no vectors also raises an error.
- Request validation and required library loading may refuse the build before the route is read. Building an index does not establish that later graph writes keep it current; the caller owns [index upkeep](../architecture/search-storage-and-indexes.g5.md#search.scope.indexes.upkeep).

## Upgrade a BM25 index

<a id="search.bm25.upgrade"></a>
[I · search.bm25.upgrade]

An upgrade converts a schema-1 index to schema 2 in one pass while searches keep working.
- Writers are refused while it runs.
- A search never sees schema 2 before the document frequencies, token records and totals are complete.
- An interrupted upgrade leaves the index flagged as upgrading, so writers stay refused until it runs again; running it again finishes the conversion. On a schema-2 index without that flag it does nothing.

## Metadata

### search.routes.inventory

- Sources: [API reference, embedding_inventory](../../../docs/API_REFERENCE.md#L148-L154), [ADMIN_GUIDE, route report](../../../docs/ADMIN_GUIDE.md#L1128-L1145), [ADMIN_API, CLI](../../../docs/ADMIN_API.md#L404), [report](../../../iris_vector_graph/_engine/schema.py#L1715-L1806), [CLI payload](../../../iris_vector_graph/cli.py#L77-L108)
- Verus: [embedding_inventory](../../Verus_verification/models/embedding_inventory/NOTES.md) `theorem_unrouted_graph_reported`, `theorem_routed_graph_has_no_empty_row`, `theorem_rows_name_table_iff_route` (as built)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-29/inventory-PAIRS.md)
- Expands: [Routes](../features/search.g5.md#search.routes)
- agent
- user-facing-behavior, operations

State machines: [embedding inventory](../../Verus_verification/models/embedding_inventory/manifest.json)

### search.scope.indexes.ivf

- design-verified

- Sources: [public IVF build contract and admission](../../../iris_vector_graph/_engine/vector.py#L1880-L1948), [routed vector selection and build](../../../iris_vector_graph/_engine/vector.py#L1949-L2027), [existing route-build tests](../../../tests/unit/test_227_ivf_route.py), [source survey](../../uplift/consolidated/iteration-10/next-vector-survey-report.md), [native no-route refusal](../../uplift/consolidated/iteration-11/root-vector-native.json)
- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_no_route_refuses_before_vector_read`, `theorem_empty_ids_after_cursor_before_select`, `theorem_malformed_info_after_build_keeps_local_maps` and `theorem_valid_info_publishes_after_native_prefix` derive the separate build admission/effect order from raw arguments, route rows and provider replies. The ordinary explicit text/metric/positive-int rule is modeled; generic Pydantic coercion is not. External Build/AddBatch/Finalize/Info effects can survive a later error; only local publication waits for syntax-valid Info. Opaque decoded Info content, base64/float32/clustering/native index correctness and rollback are outside this contract.
- Expands: [Graph-scoped indexes](../features/search.g5.md#search.scope.indexes)
- agent
- user-facing-behavior

This owns build admission, separately from an absent pair's empty search answer. The existing search routing model and prepared route fixtures do not establish the raw build refusal/effect order. A successful one-vector source/provider fixture exercises Build/AddBatch/Finalize/Info carriers; root's native panel only confirms the no-route refusal. Native clustering, index contents, later search correctness, post-Build failures and rollback are not established by admission.

Audit reproduction: [F-0607](../../Verus_verification/bugs_issues.md#F-0607) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [The IVF index's 'cosine' metric is an unnormalised dot product](../../Verus_verification/bugs_issues.md#F-0607).

State machines: [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.bm25.upgrade

- Sources: [spec 044 FR-023](../../../specs/044-bm25-index/spec.md#L169), [Upgrade](../../../iris_src/src/Graph/KG/BM25Index.cls#L516-L581), [upgrade tests](../../../tests/integration/test_044_bm25_incremental.py#L294-L400)
- Expands: [BM25 index](../features/search.g5.md#search.bm25)
- Observed divergence: a second upgrade waiting on the lock does not recheck whether the index is already converted, and re-runs on schema 2 (F4 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- agent
- operations, data-integrity
- test-coverage

Findings: [A second or re-run BM25 upgrade rebuilds an index that is already upgraded, and searches answer nothing meanwhile](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-004)
