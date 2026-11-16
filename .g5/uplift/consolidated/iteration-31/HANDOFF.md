# Iteration 31: BulkLoader and the IVG Schema (bug-plt-012); bug-tmp-102 on the batch writer and the delete

Before image: seal 30 `1b4e3683`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`,
including a new namespace `W37` (database `W37DB`, created from `%SYS`) set up with IVG Schema `Kg2`.

## W36: bug-plt-012

A consequential, tractable gap left from iteration 25: an unreproduced inherited suspicion that contradicts the owner's
statement. Predictions frozen first ([schema-PAIRS.md](schema-PAIRS.md)); exposure: the loader source was read in 25.
The metadata/source predictions held and the statement's intended rule did not: without a schema the loader fails
("Table 'GRAPH_KG.NODES' not found"); with `schema="Kg2"` its rebuild answers `false` for all four `Graph.KG.*` classes
and an unindexed load stays unreadable. Neighbor in `USER` works. **bug-plt-012 E2E reproduced** (Medium, restored live;
repair of a known suspicion). `install.bulk_load.loader` gains a "Today" bullet; `bulk_load` gains two theorems and two
controls (10 verified, 8 EXPECTED_FAIL); its binding gains three `W37` histories (75 histories, AGREES).

## W37: bug-tmp-102's rule on other direct temporal calls

Predictions frozen from the updated `temporal.write` statement ([temporal-variants-PAIRS.md](temporal-variants-PAIRS.md)).
With autocommit off, a rolled-back `bulk_create_edges_temporal` keeps its temporal entries and loses its structural
rows and nodes; a rolled-back `delete_edge_temporal` leaves the temporal edge deleted while its structural row comes
back. Both undone after `START TRANSACTION`. bug-tmp-102 widened (same rule, not a new entry); `temporal.write` updated;
`write_routing` covers both calls (8 verified, 9 controls EXPECTED_FAIL, binding AGREES over 52 histories).

## Recount

Active behavioral bindings 364 → **368** of 4,130 ([member-delta.json](member-delta.json)): 4 newly bound
(`DeleteTemporalEdge`, `TemporalMixin.delete_edge_temporal`, `IRISGraphStore.delete_temporal_edge`,
`BulkLoader._table`), 4 existing members gain a claim; lost 0.
