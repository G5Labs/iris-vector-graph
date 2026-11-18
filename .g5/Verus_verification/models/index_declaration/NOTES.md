# index_declaration — notes

Consolidated uplift, 2026-11-14. Product baseline `3eaa79cf`. Root [index_declaration.rs](index_declaration.rs); controls in [model.json](model.json); binding [binding.py](binding.py). Public cases M16 and J07. Owner block: [structure.adjacency.declare](../../../ontology/architecture/adjacency-and-derived-data.g5.md#structure.adjacency.declare).

`GraphSchema.ensure_adjacency_index` is modeled as a function `plan` from catalog state (callback classes compiled, the schema's procedure class compiled, `rdf_edges.ekey` present, `graph_id` on both tables, each index functional, plain or absent) to an ordered list of actions (skip, drop a plain index, temporal backfill, create).

## Theorems (Proved, as-built transcription)

| Claim | Theorem |
|---|---|
| no DDL, drop or backfill unless every prerequisite exists | `theorem_no_prereq_no_ddl` |
| with prerequisites and neither index declared: backfill, edge index, label index | `theorem_prereqs_declare_both` |
| a declared index is left alone (and its backfill not rerun) | `theorem_declared_left_alone` |
| the edge index is always created after the temporal backfill | `theorem_backfill_before_edge_index` |
| a plain index of the same name is dropped, then declared | `theorem_plain_replaced` |
| a second setup declares nothing | `theorem_second_run_is_noop` |
| a namespace from before graph scoping skips, then declares after the upgrade | `witness_skip_then_declare` |

Expected: 7 verified, 0 errors; 4 controls EXPECTED_FAIL: `skip-ekey-check`, `backfill-after-build`, `redeclare-functional`, and `plain-taken-as-declared`, which reintroduces the historical defect fixed in 4.7.0 (row 16 of that release: a plain index named `idx_edges_adj` was taken for the adjacency index, and `^KG` went unwritten; `schema.py:788-790`, `:868-878`).

Retained failed run: the first version stated `theorem_no_prereq_no_ddl` over `!prereqs(c)`, so `skip-ekey-check` (which weakens `prereqs`) **survived** (`results/index_declaration/20261115T043352Z-control-skip-ekey-check`). The theorem is now stated over the four catalog facts; the control fails as expected.

## Bindings

| Model | Product (pin) | Grade |
|---|---|---|
| `prereqs` | `iris_vector_graph/schema.py::GraphSchema.ensure_adjacency_index` :831-860 | Observed (binding) |
| `for_index`, `plan` | `::GraphSchema.ensure_adjacency_index` :863-897 (`ADJACENCY_INDEXES` :769-782) | Observed |
| `Kind` | `::GraphSchema.adjacency_index_kind` :785-818 (the SQL branch; the native fallback for a refused role is not exercised) | Observed |
| caller | `::GraphSchema.ensure_indexes` :600-731 calls it last (`:726`), inside a try that logs a failure | Inspected |
| the backfill itself | `Graph_KG.backfill_temporal_rows()` → `iris_src/src/Graph/KG/TemporalIndex.cls` :226-235 | Inspected |

Binding: 216 catalog states (callbacks 0/1/2 x procedures x ekey x graph columns 1/2 x 3 x 3 index kinds), each run twice (the second on the state the first left), against a transcription of `plan` and `apply`: 0 mismatches. Detected: a changed observation and the plain-taken-as-declared mutant.

## Limits

The DDL's effect inside IRIS (that `CREATE INDEX ... AS Graph.KG.AdjIndex` builds `^KG` from every row) is the [structure.adjacency.declared](../../../ontology/architecture/adjacency-and-derived-data.g5.md#structure.adjacency.declared) rule, not modeled here. Concurrent setups are not modeled. Trust inventory: none; bundled `vstd` only.
