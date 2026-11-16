# W30: the standalone BulkLoader through its readers — predictions frozen before observation

Frozen 2026-11-16, iteration 25 (retest from `cloud-iris-retest-start-20261116` = `ce5b2f7d`). Product `3eaa79cf`.
Fixture: run-isolated `ivg-retest-20261116-iris` (127.0.0.1:36216, namespace USER), deployed by [runtime.py](runtime.py).

Why this workflow: step-1 inventory of members without an active behavioral binding. `bulk_loader.py` has 18 of 18
named members unbound; public case M23; the owner says "no formal contract for endpoint registration or the refusal
path"; both inherited findings on it (bug-plt-011, bug-plt-012) are "inconclusive regression gap", never reproduced.
It is outside the recently investigated API-writer/Cypher-reader comparison family.

Exposure: the loader's own source (`bulk_loader.py`) was read to select this workflow before these predictions were
written. The readers (engine `get_node`, Cypher SQL path, status counts) were **not** read for this case. Predictions
below say which source each comes from.

Verus before this iteration: no model distinguishes any of these cases (`bulk_l2` in `proofs-d1c` is a reviewed
design of chunk checkpoints only). So every "Verus" column entry is "not determined".

| Case | Changing input or history | Reader | Owner prediction (`install.bulk_load*`) | Loader-comment prediction | Verus |
|---|---|---|---|---|---|
| A1 | `load_nodes` + `load_edges` with `use_noindex=True`, no `rebuild_all_indices` | `get_node(id)` | not stated (owner only says the loader tells the caller to rebuild) | node invisible (`_known_nodes_sql` comment: index equality read returns 0 rows for `%NOINDEX` rows) | not determined |
| A2 | same as A1 but `use_noindex=False` | `get_node(id)` | not stated | node visible with labels and properties | not determined |
| A3 | A1 then `rebuild_all_indices()` | `get_node(id)` | rebuild makes the load complete | visible | not determined |
| A4 | A1 | Cypher `MATCH (a {id:$a})-[r]->(b) RETURN b.id` (SQL path) | not stated | 0 rows | not determined |
| A5 | A2 | same Cypher | not stated | 1 row | not determined |
| A6 | A1 | Cypher `MATCH (n:L) RETURN count(n)` | not stated | undercount (likely 0) | not determined |
| A7 | `load_networkx` (rebuild + globals) on the same small graph | `get_node`, both Cypher reads | complete load | visible; 1 row; full count | not determined |
| B1 | first `load_nodes` interrupted after phase 1 commits (failure injected at the label insert), then the same call again with `skip_existing=True` | `get_node(id)` labels/properties; `MATCH (n:L)` | Suspected divergence (bug-plt-011): the re-run never adds labels and properties of nodes written by the first attempt | same (the re-run filters by node id only) | not determined |
| B2 | neighbor: first `load_nodes` completes, then the same call again | same readers | idempotent re-load: labels/properties present once, re-run writes nothing | `{"nodes": 0, "labels": 0, "props": 0}` | not determined |
| C1 | node `x` already in the default graph; `BulkLoader(graph='w30g').load_nodes([("x", …)])` | `get_node("x")` in each graph | one loader loads one graph; `x` is written into `w30g` and the default graph's `x` is unchanged | as owner | not determined |

Injected fault in B1: a wrapper around the loader's DB-API connection makes the first `executemany` of the
`rdf_labels` insert raise a non-duplicate error. That is the state a lost connection or killed process leaves after
phase 1 commits per batch; the ordering (phase 1 committed, phase 2 not) is the loader's own per-batch commit.

## Outcome ([observation](bulk-loader-observed-20261116T212413Z.json); [binding](../../../Verus_verification/results/bulk_load/20261116T213301Z-binding/receipt.json))

| Case | Outcome |
|---|---|
| A1 | held (loader-comment prediction): `get_node` None, Cypher edge 0 rows, label count 0, although the load returned 2 nodes / 2 labels / 4 props / 1 edge. The owner did not state this: an **owner gap**, now written; finding bug-plt-106 |
| A2 | held: readable at once |
| A3 | held: readable after `rebuild_all_indices`; A1's rows also became readable (the rebuild is global) |
| A4–A6 | held (A4 0 rows, A5 1 row, A6 count 0) |
| A7 | held: `load_networkx` rebuilds and builds globals; all readers see the load |
| B1 | held (owner's Suspected divergence): first call raises `BulkLoadError`; nodes present with no labels or properties; the re-run returns zeros and nothing changes. bug-plt-011 **E2E reproduced** |
| B2 | held: idempotent |
| C1 | held: written into `w30g`; the default graph's `x` keeps `p = "default"`. Unscoped Cypher `MATCH (n:L)` counts both graphs' rows (2), as `query.graph-scope` already owns |

No prediction missed. Material prediction gained: an owner reader can now predict A1 and B1 from `install.bulk_load.loader`
alone, and Verus distinguishes A1/A2, B1/B2 and C1 (`models/bulk_load`), bound to eight previously unbound loader members.
