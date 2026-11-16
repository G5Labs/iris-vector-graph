# W31: engine writes inside a caller's transaction, by how the engine was opened — predictions frozen before observation

Frozen 2026-11-16, iteration 26. Before image: seal 25 `2300521b`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: step-1 inventory. `_write_txn.py` has 20 of 20 named members without an active binding; it decides
whether every engine write commits, nests or refuses, which every later reader depends on. The open question
`structure.write.engine-connection` says the answer depends on how the engine was opened. Outside the comparison-
operator family and outside the bulk-loader batch.

Sources used for these predictions: owners `structure.write`, `structure.adjacency.undeclared`, `query.writes.atomic`,
the open question card, and USER_GUIDE "Writes inside your transaction" (lines 236-310). `_write_txn.py`, the temporal
writer and the readers were **not** read. Verus before this iteration determines none of these cases.

Engines: **C** = `IRISGraphEngine(conn)` on the caller's connection; **F** = `IRISGraphEngine.from_connect(...)`, the
caller opening its transaction on `F.conn`. The namespace has the declared adjacency index.

| Case | History | Reader | Owner / docs prediction | Verus |
|---|---|---|---|---|
| T1 | C: `START TRANSACTION`; `create_node` a, b; `create_edge(a,R,b)`; `ROLLBACK` | `get_node`; Cypher edge match; adjacency (`^KG("out")`) | all gone (the write nests; rollback removes rows and adjacency entries); `^KG("__version")` raised | not determined |
| T2 | T1 with `COMMIT` | same | all present | not determined |
| T3 | F: same as T1 | same | all gone (ordinary rows and the declared index are on `F.conn`, the caller's transaction) | not determined |
| T4 | C: `START TRANSACTION`; `create_edge_temporal(a,R,b,ts,w)`; `ROLLBACK` | temporal window read; Cypher edge match | nothing (nests) | not determined |
| T5 | F: same as T4 | same | the temporal store entry **remains** (written over F's own Native API connection, outside the caller's transaction); whether the structural edge row it marks also remains: unknown, leaning yes (same native call) | not determined |
| T6 | F: T4's history with `COMMIT` | same | present | not determined |
| T7 | C: `START TRANSACTION`; `create_node` x; `BulkLoader(conn).load_nodes([y])` | the call; then after `ROLLBACK`: `get_node` x, y | `CallerTransactionOpenError` before writing; after rollback neither x nor y | not determined |
| T8 | C: `START TRANSACTION` with nothing written; `BulkLoader(conn).load_nodes([y])`; `ROLLBACK` | `get_node` y | the loader runs (nothing of the caller's to commit) and y remains after the rollback | not determined |

### Added after reading the source, before any observation (exposed: source-informed)

Reading showed that `create_edge_temporal` goes through the store's `createIRIS(store.conn)` (the engine's own SQL
connection's server process), while `purge_before`, `rebuild_temporal_latest`, `set_temporal_structural`,
`drop_temporal_structural_rows` and `backfill_temporal_structural_rows` call `engine._iris_obj()`, which on a
`from_connect` engine opens a separate Native API connection. Source-based expectations, recorded beside the frozen
doc-based ones above:

| Case | History | Reader | Source-based expectation |
|---|---|---|---|
| T5 (again) | as above | as above | contradicts the docs: nothing remains (InsertEdge nests in F's transaction) |
| T9 | committed temporal edge at ts 1000 in the default graph; C: `START TRANSACTION`; `purge_before(2000)`; `ROLLBACK` | window read | the edge is back (the purge nested and was rolled back) |
| T10 | same history on F | window read | the edge stays purged: the purge ran on F's separate connection, outside the caller's transaction (this is what the open question describes) |

### Added after the first binding run, before the targeted observation (exposed: source- and binding-informed)

The first `write_routing` binding run DISAGREED in three histories, all with the driver's autocommit off and a
rollback (`create_edge_temporal` on both engines, `set_temporal_structural` on the caller's connection): the effect
survived. `WriteTxn` opens the caller's level first when autocommit is off (`Txn_Begin(1)`), but these calls go to
ObjectScript directly. `InsertEdge` sets `^KG("tout")`/`("tin")` before its embedded SQL inserts the marked structural
row and endpoint nodes (`AssertTemporalRow`). Expectation for T11 (C) and T12 (F): autocommit off, nothing written,
`create_edge_temporal`, `conn.rollback()` → the window read still returns the edge; the structural row, its
`^KG("out")` entry and the endpoint nodes are gone (rolled back with the SQL's implicit transaction). Neighbor T13:
the same with SQL `START TRANSACTION` → everything gone (T4/T5).

## Outcome ([observation](caller-txn-observed-20261116T213901Z.json); [autocommit](autocommit-observed-20261116T214248Z.json); binding receipts in `results/write_routing/`)

| Case | Outcome |
|---|---|
| T1, T2, T3 (+ F commit) | held: node, edge and adjacency follow the caller's end on both engines |
| T4 | held |
| T5 | **miss** (docs-based): F's `create_edge_temporal` joined the caller's transaction and was rolled back. Held for the source-based expectation. Low bug-plt-107 (guide wording) |
| T6 | held (Cypher `y.id` is null: the endpoint nodes a temporal write creates have no `id` property, as already owned by `temporal.structural.ledger-nodes`) |
| T7 | held: `CallerTransactionOpenError`, nothing written |
| T8 | **miss**: after SQL `START TRANSACTION` with nothing written, `$TLEVEL` is already 1, so the loader refuses. The guide promised only the autocommit-off case; the owner now states both |
| T9 | held (source-based) |
| T10 | held (source-based): F's `purge_before` survives the caller's rollback and retires the bare endpoint nodes |
| T11, T12 | held (source/binding-based): split state; **High bug-tmp-102, new discovery** |
| T13, T11n | held |

Material predictions gained: an owner reader can now predict every cell of the 32-history matrix from `structure.write`;
`write_routing` distinguishes the WriteTxn path, the direct-call step order and the engine's own connection. The
first binding run's three disagreements are kept as the discovery record.

## Correction (recorded in iteration 27)

The predictions above were taken from the USER_GUIDE and the owners' **metadata** entries; the statement bodies were not
read. [structure.write](../../../ontology/features/graph-structure.g5.md#structure.write) already stated that temporal
purges, rebuilds and settings use the engine's own native connection and commit on their own under `from_connect`
(T10), and that the bulk loader refuses a caller's open transaction (T8 as observed). [temporal.write](../../../ontology/features/temporal.g5.md#temporal.write)
already stated that a direct temporal write joins a caller's transaction (T5 as observed). So T5, T8 and T10 were
**predicted by the owners**; the misses were against the USER_GUIDE only. Not predicted by any owner: the autocommit-off
split (T11, T12; bug-tmp-102) and the autocommit-off temporal setting. Those two facts are now in the statements; the
four-bullet rule this iteration had added to `structure.write`'s metadata was removed as a duplicate of the statement.
