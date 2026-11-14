# PROOFS-D1C: Verus L1/L2 refinement for modules 03 (direct writes) and 05 (temporal) (proof debt D-1, playbook §3.3)

Crate `experiment/playbook-completion/proofs-d1c` (`ivg-d1c-proofs`), Verus 0.2026.10.04.426d8b0, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved** (`--no-cheating`, no trusted item in this
crate), about **models**. Every theorem here is a statement about an L1 contract or a reviewed L2 machine. None says
that the Python or ObjectScript at pin `3eaa79cf` has the property. The product's obligations stay as the as-built
evidence leaves them (failed or open: `findings/audit/03.json`, `05.json`, `followup.json`).

Modules 03 and 05 share one invariant: the structural row a temporal edge implies (ADR-0009, CONTEXT.md:66-73) and
its ownership against explicit writes, with the temporal-only opt-out (ADR-0015). That family carries most of the
work; three smaller module-local families cover the other reproduced defects of 03 and 05 that have an explorer twin.

| Gate item (§3.3) | 03+05 edge (with 12's prefix erase) | 03 ledger statement link | 03 bulk atomicity | 05 bucket aggregates |
|---|---|---|---|---|
| L1 contract with the business invariants (`Contract` + `SafeContract`) | `src/edge_l1.rs` | `src/stmt_l1.rs` | `src/bulk_l1.rs` | `src/tagg_l1.rs` |
| L2 machine over the stored layout, reviewed design | `src/edge_l2.rs` (rdf_edges rows and qualifier kind, ^KG("out"/"in"), ^KG("tout"/"tin"), Graph_KG.nodes, ^IVG.TemporalStructural, pending adopts) | `src/stmt_l2.rs` (rdf_edges edge_id, ^IVG.Ledger("stmt"/"stmtNext"/"tuple")) | `src/bulk_l2.rs` (committed rows, the WriteTxn, loader chunks, SQL fallback) | `src/tagg_l2.rs` (^KG("tout"), ^KG("bucket"), ^KG("tagg") count/sum) |
| `Refines<L1>` for **every** L2 step | 11 labels, each mapped (`lemma_step`) | 6 labels | 8 labels | 4 labels |
| L2 invariant inductive (`SafeContract`) | `inv0305` (L1's 3 conjuncts through the abstraction + 3) | `inv03s` (3 + 3) | `inv03b` (by phase) | `inv05t` (1 + 3) |
| Every raw L2 execution refines L1 and keeps both invariants | `edge_l2::theorem_raw_executions_refine` | `stmt_l2::theorem_raw_executions_refine` | `bulk_l2::theorem_raw_executions_refine` | `tagg_l2::theorem_raw_executions_refine` |
| Broken-implementation controls rejected in the expected file | 7 of 7, all errors in `src/edge_l2.rs` | 1 of 1, `src/stmt_l2.rs` | 1 of 1, `src/bulk_l2.rs` | 1 of 1, `src/tagg_l2.rs` |
| Each control's counterexample proved reachable | 7 (`src/cx_f0304.rs`, `cx_f0505.rs`, `cx_f0507.rs`, `cx_fc0501.rs`, `cx_hd0302.rs`, `cx_fc1203.rs`, `cx_fc0301.rs`) | 1 (`src/cx_f0303.rs`) | 1 (`src/cx_f0305.rs`) | 1 (`src/cx_f0501.rs`) |
| Non-vacuity (the reviewed L2 does real work) | `src/witness_edge.rs` | `src/witness_stmt.rs` | `src/witness_bulk.rs` | `src/witness_tagg.rs` |
| Trust inventory | empty (this crate and `actors`) | same | same | same |

Baseline: `cargo verus verify -- --no-cheating`: **111 verified, 0 errors** (edge 51, statement 24, bulk 14, buckets
22); Verus 1.99 s, SMT 1.33 s, 3.43 M rlimit, wall 2.41 s, 0.47 GB peak (registry `proofs-d1c-baseline`, log
`$RUN_DIR/proofs-d1c/baseline.log`, which ends with the counts read from its JSON). Gate: **pass** (`RESULTS.json`,
sources SHA-256 `2a16c6b076326773...`). An unregistered run over the same sources (`$RUN_DIR/proofs-d1c/scratch-1`)
gave the same result. Rerun:
`source experiment/playbook-completion/environment.sh; python3 experiment/playbook-completion/proofs-d1c/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600` after `cargo clean -p`; `PROOFS_OUT_DIR=<dir>` writes logs and
RESULTS.json there so a re-check never overwrites the registered logs; `--register` registers the decisive runs).

The executable twins are the explorer families of breadth lane A (`models/breadth-a/src`): `tmp_mark` (F-0304, F-0505,
F-0507) for the edge family, `wrt_ledger_stmt` (F-0303), `wrt_bulk_atomic` (F-0305) and `tmp_bucket` (F-0501). The edge
family adds four defects with no explorer model: F-C0501, HD-0302, F-C1203 and F-C0301.

## 1. Modules 03 and 05: the structural-versus-temporal edge

### L1 contract (`edge_l1.rs`)

State: `edges` (per triple in a graph `K {g, s, p, o}`, provenance `Explicit` or `Derived`), `tev` (temporal edges
`Ev {k, ts}`), `nodes` (`NK {g, n}`), `reg` (the (graph, predicate) pairs registered temporal-only; configuration, no
step changes it, any value at init). Labels: `Node`, `Create{k, ans}` (create_edge), `Store{k}` (store_edge),
`Retract{k}` (delete_edge), `TWrite{k, ts, ok}` (create_edge_temporal; `ok` false is a write IRIS refuses),
`TDelete{k, ts}`, `PurgeBefore{g, end}` (purge_raw_before), `Purge` (TemporalIndex.Purge), `EraseNodes{g, sel}`
(delete_nodes_by_prefix; `sel` the ids the prefix selects). Business rules and `inv1` (proved inductive,
`lemma_l1_safe`):

- **a temporal edge of a structural predicate implies its structural edge** (ADR-0009; HD-0302 working answer):
  `inv_impl`; `theorem_temporal_implies_structural`;
- **a derived edge exists only while its triple has a timestamp, and only for a structural predicate** (ADR-0009
  amendment, TMP-B9.13, ADR-0015): `inv_derived`; `theorem_derived_edge_needs_time`;
- **the temporal side never removes or changes an explicit edge** (ADR-0009, HD-0302): every temporal deletion keeps
  the explicit edges and the derived edges that still have a timestamp (`keep_supported`);
  `theorem_temporal_side_keeps_explicit_edges` (TWrite, TDelete, PurgeBefore, Purge);
- **an explicit write owns the edge** (create_edge docstring, ADR-0009): `theorem_explicit_write_owns_its_edge`
  (afterwards explicit; create_edge answers True exactly when it was not explicit before: new or adopted);
- **a direct delete removes the explicit assertion only** (HD-0302 working answer): `theorem_direct_delete_keeps_supported_edge`;
- **a refused temporal write writes nothing** (create_edge_temporal docstring, temporal.py:259-261):
  `theorem_refused_temporal_write_writes_nothing`;
- **a temporal-only predicate writes nothing structural** (ADR-0015): `theorem_temporal_only_writes_nothing_structural`;
- **a prefix erase leaves nothing of the prefix in the graph, temporal-only edges included** (delete_nodes_by_prefix
  docstring nodes_edges.py:1529-1545; ADR-0015:59-60): `theorem_prefix_erase_leaves_nothing_of_the_prefix`;
- an edge's endpoints are node rows of its graph (fk_edges_source/fk_edges_dest): `inv_fk`.

### L2 machine (`edge_l2.rs`) and refinement

Layout: `rows` (Graph_KG.rdf_edges at ekey 0, qualifiers as `Marked` = {"temporal": true}, `Plain`, or `TOne` = an
explicit writer's "temporal": 1), `out` (^KG("out"/"in"), written by the row's functional index), `tout`/`tin`
(^KG("tout"/"tin"), re-indexed by triple), `nodes`, `reg` (^IVG.TemporalStructural(gKey, p), TemporalPolicy.cls:31-39),
`pend` (create_edge calls between their COMMIT and `_adopt_temporal_row`; as built only). Abstraction `abse`: a
`Marked` row is a derived edge, any other row explicit (CONTEXT.md:72-73); `tev = tout`.

| L2 step (source) | L1 step | Proof |
|---|---|---|
| `CreateNode` (create_node) | `Node` | `lemma_createnode` |
| `CInsert{res: Some}` (create_edge, nodes_edges.py:1150-1252) | `Create` | `lemma_cinsert` |
| `CInsert{res: None}` (as built: committed, not answered) | stutter (never enabled under `inv_pend`) | `lemma_cinsert` |
| `CAdopt` (`_adopt_temporal_row`, nodes_edges.py:1254-1304) | `Create` (never enabled under `inv_pend`) | `lemma_cadopt` |
| `SStore` (store_edge, nodes_edges.py:2532-2588) | `Store` | `lemma_sstore` |
| `DDelete` (delete_edge, nodes_edges.py:1382-1450) | `Retract` | `lemma_ddelete` |
| `TInsert` (InsertEdge/WriteStores TemporalIndex.cls:46-130; AssertTemporalRow Adjacency.cls:575-621) | `TWrite{ok}` | `lemma_tinsert` |
| `TRefuse` (the same call when the row INSERT is refused) | `TWrite{!ok}` | `lemma_trefuse` |
| `TDelete` (DeleteTemporalEdge TemporalIndex.cls:325-346; RetractTemporalRow Adjacency.cls:623-648) | `TDelete` | `lemma_tdelete` |
| `PurgeRaw` (PurgeRawBefore 866-943, RetireExpired 944-1049, RetractTemporalRows Adjacency.cls:650-692) | `PurgeBefore` | `lemma_purgeraw` |
| `TPurge` (Purge 808-811 = EraseAll 381-392) | `Purge` | `lemma_tpurge` |
| `ENodes` (Eraser.EraseNodes 322-370, EraseIdSet 467-639, TemporalIndex.EraseNodes 400-453) | `EraseNodes` | `lemma_enodes` |

`inv0305`: `inv1` of the abstraction, `inv_out` (^KG("out") holds exactly the rows' triples), `inv_tin` (tin mirrors
tout), `inv_pend` (no create_edge call is between its commit and its adopt). L2 theorems:
`theorem_adjacency_holds_every_structural_temporal_edge` (what MATCH, BFS and centrality read holds every structural
temporal edge, through its row) and `theorem_marked_row_has_time`. The prefix erase's proof shows why the remedy reads
the temporal index: a temporal-only edge's endpoints have no node row, so only `endpoint(tout, g, n)` selects them.

## 2. Module 03: the ledger's statement link (`stmt_l1.rs`, `stmt_l2.rs`)

L1 state: each triple's live edge with its lifetime (`row[k]`; a row created again is another edge) and the live
statements `stmts[id] = {k, life}`. Labels `LCreate`, `LUpdate` (an op by tuple: update or upsert, or an unrecorded
edge given a statement), `LDelete`, `DCreate` (create_edge), `DDelete` (delete_edge, and delete_node's per-edge step).
Rules: no live statement outlives its content (CONTEXT.md:198-205, INV-stmt), and a statement names one edge lifetime
(WRT-B1.9). `inv1`: `inv_named` (every live statement names the live edge of its lifetime), `inv_one`, `inv_fresh`.
Theorems: `theorem_live_statement_names_live_edge`, `theorem_statement_identity_is_stable`,
`theorem_direct_delete_ends_the_statement`.

L2 layout: `rows` (triple -> edge_id), `next_id`, `stmt` (^IVG.Ledger("stmt", id) = $LB(s, p, o, g, createdSeq,
deletedSeq), with the ghost `life` it was allocated for), `next_stmt`, `tuple` (^IVG.Ledger("tuple", s, p, o, gkey)).
Steps: `LCreate` (OpCreateRel create path LedgerApply.cls:455-497, AllocStmt 159-168) -> `LCreate`; `LUpdate`
(ResolveRef 185-204, merge path 470-479) -> `LUpdate`; `LDelete` (672-683) -> `LDelete`; `DCreate` -> `DCreate`;
`DDelete` -> `DDelete`; `ENode` (EraseEdgeRow, Eraser.cls:641-683) -> `DDelete`. `inv03s`: `inv1` of the abstraction,
`inv_tuple` (a tuple entry names the triple's live statement), `inv_back` (each live statement is its triple's tuple
entry), `inv_ids`. L2 theorem `theorem_tuple_entry_names_current_row`.

## 3. Module 03: bulk atomicity (`bulk_l1.rs`, `bulk_l2.rs`)

L1: the committed rows (what a READ COMMITTED reader of another process sees); `Bulk{batch, ok}` commits the whole
batch or nothing; `Read`. `theorem_bulk_all_or_nothing`. L2: bulk_create_nodes on the server-loader path
(nodes_edges.py:1715-1757): `Begin` (WriteTxn), `ChunkOk`/`ChunkFail` (BulkIngestNodesSQL per chunk, EdgeScan.cls:352,
424, 426), `Commit`, `FallbackOk`/`FallbackFail` (the SQL path over the whole batch), `Abort` (the client dies), `Read`.
Beginning, chunk and failure steps stutter; `Commit` and `FallbackOk` map to `Bulk{ok}`, `FallbackFail` and `Abort` to
`Bulk{!ok}`. `inv03b`: what the call has written, by phase. `theorem_no_partial_batch_visible`: no step of a call but
its end changes the committed rows.

## 4. Module 05: bucket aggregates (`tagg_l1.rs`, `tagg_l2.rs`)

L1: one bucket's temporal edges `tout[ts] = w` (ts an offset of the bucket, BUCKET = 300, TemporalIndex.cls:4);
`Write{ts, w, mode}` (insert/skip/update), `Delete`, `ReadAgg{count, sum}` (whole-bucket GetAggregate,
TemporalIndex.cls:1460-1471) and `ReadBucket{n}` (the counter GetVelocity/FindBursts read) answer `cnt` and `sm`, the
number of edges and their weight sum (recursive over the offsets; `lemma_cnt_insert`, `lemma_cnt_remove` by induction).
Theorems: `theorem_update_replaces_the_edge` (CONTEXT.md:173-177), `theorem_collision_changes_nothing` (spec 254 FR-003),
`theorem_aggregate_read_is_exact` (TMP-B1.7). L2: `tout`, `bucket` ($Increment, :102), `count`/`sum` ($Increment,
:117-118); `Delete` decrements the counter and rebuilds count/sum from tout (RemoveTemporalRow :348-364,
RebuildBucketAggregate :455-486). `inv05t`: count, sum and counter describe exactly tout.

## 5. Reviewed design (the findings' remedies and the working answers) and its status at the pin

| Id | Element | Source | At the pin |
|---|---|---|---|
| R03-1 | store_edge adopts a marked row inside its transaction | F-0304 remedy | no: duplicate swallowed (nodes_edges.py:2567-2581) |
| R03-2 | create_edge adopts inside the guarded insert's transaction | F-C0301 remedy | no: adopt after `txn.commit()` (nodes_edges.py:1236-1252) |
| R03-3 | delete_edge of a triple that keeps a structural timestamp reverts its row to marked | HD-0302 working answer (status **assumption**; the maintainer test tests/e2e/test_254_purge_e2e.py:322-327 accepts the as-built removal) | no: the row goes (intent-a-hd0302-temporal-row-delete) |
| R03-4 | delete_edge kills the triple's statement and tuple entry (through EraseEdges) | F-0303 remedy | no: plain SQL DELETE (nodes_edges.py:1414-1433) |
| R03-5 | the server loader runs on the cursor's process (`txn.native()` in every case) | F-0305 remedy | no: only inside a caller's transaction (nodes_edges.py:1726) |
| R05-1 | one marker predicate for every deleter: JSON true | F-0505 remedy | no: `%Get("temporal") = 1` (Adjacency.cls:736-748) |
| R05-2 | Purge retracts the marked rows | F-0507 remedy | no: EraseAll only (TemporalIndex.cls:381-392) |
| R05-3 | a refused temporal write writes nothing: the row and its endpoints first, in a transaction, then the temporal globals | F-C0501 remedy, its "assert the row first" variant (a transaction alone would not undo bucket/tagg: $Increment is not undone by rollback, iris-contract E-INCR) | no: tout/tin/bucket set before AssertTemporalRow (TemporalIndex.cls:97-111) |
| R05-4 | an update adds (new - old) to the sum, count and counter unchanged | F-0501 remedy | no: counted again (TemporalIndex.cls:82-83, 102, 117-118) |
| R12-1 | the prefix erase selects the prefix's ids from the temporal index too | F-C1203 remedy | no: from Graph_KG.nodes only (Eraser.cls:334-346) |
| as built | ADR-0015 skip (IsStructuralKey, TemporalIndex.cls:109; RetireExpired :966); AssertTemporalRow's trust-index shortcut and NOT EXISTS; the last-timestamp retraction; collisions change no store; EraseEdgeRow's statement kill; delete_node through EraseNodeIds | TemporalIndex.cls, Adjacency.cls, Eraser.cls | yes |

## 6. Broken-implementation controls

Each feature puts back one as-built decision. Every error is in the expected file, every failing function is in that
file's module, every function of every other module verifies (`RESULTS.json`, `failing_outside_expected_module`
empty), and each control's counterexample (compiled only with it) is a proved run of the L2 step relation, as the
control changes it, from its initial state to a step that is not an L1 step.

| Control (finding) | Rejected at (function: obligation) | Proved counterexample | Registry |
|---|---|---|---|
| `control_f0304_store_no_adopt` (F-0304) | `edge_l2.rs:304` `lemma_sstore`: store_edge adopts the marked row | 3 steps: temporal edge (marked row); store_edge keeps the marker (not an L1 step); the last temporal delete deletes the stored edge | `proofs-d1c-f0304-store-no-adopt` |
| `control_f0505_marker_predicate` (F-0505) | `edge_l2.rs:361` `lemma_tdelete`, `:381` `lemma_purgeraw`, `:403` `lemma_tpurge`: the marker test is JSON true only | 3 steps: create_edge with {"temporal": 1}, a temporal edge, its delete removes the explicit row (not an L1 step) | `proofs-d1c-f0505-marker-predicate` |
| `control_f0507_purge_keeps_rows` (F-0507) | `edge_l2.rs:400` `lemma_tpurge`: Purge retracts marked rows | 2 steps: temporal edge; Purge leaves the marked row and ^KG("out") with no timestamp (not an L1 step, `!inv1`) | `proofs-d1c-f0507-purge-keeps-rows` |
| `control_fc0501_refused_write_partial` (F-C0501) | `edge_l2.rs:350` `lemma_trefuse`: a refused write writes nothing | 1 step: the refused write leaves tout, tin and the endpoints, no row (not an L1 step; `!inv1`: a structural temporal edge with no structural edge) | `proofs-d1c-fc0501-refused-write-partial` |
| `control_hd0302_delete_removes_row` (HD-0302) | `edge_l2.rs:318` `lemma_ddelete`: the row stays, reverted to marked | 2 cases: temporal edge then delete_edge (marked row); temporal edge, create_edge adopts, delete_edge (adopted row): each delete is not an L1 step, `!inv1`, ^KG("out") empty while tout holds the timestamp | `proofs-d1c-hd0302-delete-removes-row` |
| `control_fc1203_prefix_from_node_rows` (F-C1203) | `edge_l2.rs:426` `lemma_enodes`: the ids include the temporal endpoints | 3 steps: predicate 9 temporal-only; node 7; temporal-only edge 1 -9-> 4; erase of prefix ids {1, 4, 7} removes node 7, leaves the edge (not an L1 step) | `proofs-d1c-fc1203-prefix-from-node-rows` |
| `control_fc0301_adopt_after_commit` (F-C0301) | `edge_l2.rs:275` `lemma_cinsert`: create_edge answers in its insert's step | 4 steps: temporal edge; create_edge commits (pending); the last temporal delete retracts the marked row; the adopt answers False with no edge (not an L1 step) | `proofs-d1c-fc0301-adopt-after-commit` |
| `control_f0303_direct_delete_keeps_stmt` (F-0303) | `stmt_l2.rs:267` `lemma_ddelete`: delete_edge unlinks statement and tuple | 4 steps: ledger create (statement 0); delete_edge (not an L1 step, `!inv1`); create_edge again (edge_id 1); an op by tuple acts on statement 0 of edge 0 (not an L1 step) | `proofs-d1c-f0303-direct-delete-keeps-stmt` |
| `control_f0305_chunks_commit_alone` (F-0305) | `bulk_l2.rs:123` `lemma_chunkok`: nothing visible before the call commits | 3 steps: begin, chunk 1 commits (a stutter that changes the committed rows: not an L1 step), a reader sees {1}; the client dies leaving chunk 1 committed | `proofs-d1c-f0305-chunks-commit-alone` |
| `control_f0501_update_counted_again` (F-0501) | `tagg_l2.rs:100` `lemma_write`: an update changes neither count nor counter | 3 steps: weight 1, update to 5: ReadAgg answers count 2, sum 6 for one edge (not an L1 step); delete: ReadBucket answers 1 for an empty bucket (not an L1 step) | `proofs-d1c-f0501-update-counted-again` |

Counts (verified / errors, each including its verified counterexample and excluding its family's witness): F-0505
108/3; every other control 110/1. Each control run took 1.84-1.97 s of wall time.

Live or model reproductions of the same as-built decisions: breadth-a-live-05-temporal (F-0304, F-0505, F-0501),
breadth-a-live-05-purge (F-0507), breadth-a-live-05-partial (F-C0501), intent-a-hd0302-temporal-row-delete (HD-0302),
fu-r04-temporal-only-live-b (F-C1203), breadth-a-live-ledger-stmt (F-0303), breadth-a-live-03-bulk-atomicity and
breadth-a-live-03-bulk-killed-client (F-0305), and the explorer families breadth-a-mc-tmp_mark-*, -wrt_ledger_stmt-*,
-wrt_bulk_atomic-*, -tmp_bucket-*. F-C0301 was confirmed in source only; `cx_fc0301` reproduces it in the model (not
live). These counterexamples are proved over the models.

Identifier note: the lane brief listed "F-0303 a write outside its transaction". At the audit F-0303 is "a direct edge
delete leaves the ledger's live link" (`findings/audit/03.json`), controlled here as such. The writes outside their
transaction are F-0305 (loader chunks), F-C0301 (the adopt) and F-C0501 (the temporal write); each has its own control.

## 7. Premises (named; none is an assumption inside a proof)

| Id | Premise | The pin |
|---|---|---|
| P-E1 | the adjacency index is declared (`Adjacency.Indexed()`): the row's functional index keeps ^KG, InsertEdge asserts the marked row | not enforced: without it the PutShadow and Python mirror paths run (F-0506, confirmed in source: an unmarked row for any predicate) |
| P-E2 | one row per triple (ekey 0); keyed edges (PutKeyed, spec 234) not modelled | not enforced; `_adopt_temporal_row` adopts only a single row (nodes_edges.py:1290-1291) |
| P-E3 | no explicit writer stores {"temporal": true} in its own qualifiers | not enforced (`_qualifiers_json`, nodes_edges.py:288-302, accepts it); then even R05-1 reads an explicit edge as derived |
| P-E4 | the temporal-only registry does not change during a run (no TemporalPolicy.Set, DropRows, BackfillRows) | not enforced: Set takes effect for the next write and leaves rows as they are until an operator runs DropRows/BackfillRows (TemporalPolicy.cls:39-40); in between the implication or the no-row rule fails |
| P-E5 | each modelled call is one atomic step (the WriteTxns of create_edge, store_edge, delete_edge; InsertEdge; DeleteTemporalEdge; PurgeRawBefore; Purge; the eraser's transaction); calls interleave only between steps | **violated**: InsertEdge is not atomic (F-C0501, live) and create_edge's adopt runs after its commit (F-C0301, source); both are controls here. DeleteTemporalEdge, PurgeRawBefore and Purge run no transaction (a purge failing part way leaves timestamps without rows, its own comment, TemporalIndex.cls:935-937), and a write between RetireExpired's survivor walk and its retraction is not modelled. R03-2 also needs the adopt's read to lock the row or the UPDATE to re-check the marker (READ COMMITTED reads take no lock) |
| P-E6 | an erase of graph g overlaps no writer of g | **violated**: F-1201 (live), F-C1202 (core model); P-S3 of `proofs-d1b`, P-A3 of `proofs-breadth` (D-13) |
| P-E7 | timestamps are >= 0 (purge_raw_before's range is [0, end); the pin skips negative ones) | not enforced: TemporalEdgeInput checks the timestamp on the single write with a timestamp only (_validate.py:207-227; F-0513 for the same gap on weights) |
| P-E8 | a prefix is the finite set of ids it selects; EraseGraph, EraseAll and EraseNodeIds are not modelled | modelling restriction (EraseNodeIds passes its ids straight to TemporalIndex.EraseNodes, so it reaches temporal-only edges, ADR-0015:59-60) |
| P-E9 | weights, attrs, edgeprop, tlast, the bucket stores, node retirement by purges (pRetireNodes 0), temporal_structural_rows=True, ledger strict mode are outside the edge model | modelling restriction (F-0503, F-0504, F-C0502 live there) |
| P-L1 | one graph; the ledger is enabled and not strict; a changeset op is one atomic step; ops by tuple only (not stmt_id/op_ref) | modelling restriction (strict mode refuses delete_edge, so F-0303 needs non-strict) |
| P-L2 | an edge erase overlaps no ledger commit | **violated**: F-1201 (live: a graph erasure removes the statement entry of an edge a concurrent ledger commit creates) |
| P-L3 | statement ids and edge_ids are fresh (stmtNext and the %ID counter only grow) | assumed |
| P-B1 | a batch of two chunks, one bulk call at a time, no other writer of its rows | modelling restriction; not enforced |
| P-B2 | nested transactions: an inner TCOMMIT only lowers $TLEVEL and an outer rollback undoes inner work | holds by the validated IRIS contract (iris-contract E-NEST); R03-5 relies on it |
| P-B3 | the server-loader path only (objectscript_deployed, default graph); the SQL fallback commits or rolls back as one step | modelling restriction |
| P-T1 | one bucket of one triple (tagg is per (g, b, s, p) across targets, the counter per (g, b, s) across predicates) | modelling restriction |
| P-T2 | weights are integers; min, max, the HLL sketch and edgeprop are not modelled; reads are whole-bucket (partial windows read tout, TemporalIndex.cls:1474-1486) | modelling restriction |
| P-T3 | the bucket's writes are not rolled back | holds for $Increment by E-INCR (not undone by rollback); relevant to R05-3, which is why the reviewed design asserts the row first |

## Premises the pin violates

Three premises of these models are false at pin `3eaa79cf` by this audit's own evidence: P-E5 (calls are atomic:
F-C0501 live, F-C0301 in source), P-E6 (an eraser overlaps a writer of its graph: F-1201, F-C1202) and P-L2 (an erase
overlaps a ledger commit: F-1201). Six more are not enforced by the pin, with no observed violation: P-E1, P-E2, P-E3,
P-E4, P-E7, P-B1. Every reviewed-design element R03-1..R03-5, R05-1..R05-4 and R12-1 is absent at the pin (section 5),
and each control shows the corresponding as-built decision violating the model's contract on a reachable run. R03-3
rests on HD-0302's working answer, an assumption that a maintainer test contradicts. So no safety result here transfers
to the product. What transfers is the negative: each as-built decision of section 6 breaks the contract on a reachable
run of the model.

## 8. Cost (measured, `RESULTS.json`)

Baseline: Verus 1.99 s, SMT 1.33 s, 3.43 M rlimit over 111 functions, wall 2.41 s, 0.47 GB.

| Module proof | Functions | SMT ms | rlimit | Largest function | Largest proof lemma |
|---|---|---|---|---|---|
| 03+05 edge (`edge_l1`, `edge_l2`, `edge_runs`, `witness_edge`) | 51 | 809 | 2.17 M | `witness_edge::witness_edge` 0.55 M | `edge_l2::lemma_tdelete` 0.12 M |
| 03 statement link (`stmt_l1`, `stmt_l2`, `stmt_runs`, `witness_stmt`) | 24 | 292 | 0.69 M | `witness_stmt::witness_stmt` 0.10 M | `stmt_l1::lemma_l1_safe` 0.08 M |
| 03 bulk (`bulk_l1`, `bulk_l2`, `bulk_runs`, `witness_bulk`) | 14 | 85 | 0.19 M | `witness_bulk::witness_bulk` 0.06 M | `bulk_l2::theorem_raw_executions_refine` 0.03 M |
| 05 buckets (`tagg_l1`, `tagg_l2`, `tagg_runs`, `witness_tagg`) | 22 | 138 | 0.37 M | `witness_tagg::witness_tagg` 0.15 M | `tagg_l2::theorem_raw_executions_refine` 0.04 M |

No rlimit was raised and no proof looped. The 11 decisive runs took 21 s of Verus wall time in total (plus the same
for the scratch run). Development needed about 15 short Verus runs: one rename (`has` is Verus syntax, so the
predicate is `has_ts`), one variant field renamed (`res`), a helper lemma (`lemma_live_named`) for triggers through the
statement abstraction, and three trigger hints through the bucket abstraction.

## 9. Trust inventory

This crate has no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). The scan of `actors` (`c03f9fa`) finds none either; `actors` was verified
in this lane's first build in the same target directory and is cached since (the runner cleans this crate only). vstd
is Verus's trusted base (finite `Set`/`Map` with their axioms). The gate status is **declared empty**
(`RESULTS.json` `trust_inventory`).

### Source-comment errata (comments only; no proof content)

Three line citations in comments of the registered sources are off by a few lines; they are left as registered so that
the sources match `sources_sha256` of the decisive runs: `src/edge_l2.rs:7` cites Adjacency.cls:590-595 for the marker,
which AssertTemporalRow sets at Adjacency.cls:585; `src/edge_l2.rs:164` cites TemporalIndex.cls:104 for WriteStores'
IsStructuralKey test, which is at :109; `src/tagg_l2.rs:6` cites TemporalIndex.cls:100 for the bucket counter's
$Increment, which is at :102. Every other citation in the sources was rechecked against the pin.

## 10. What is NOT proved (open obligations)

- **No proof connects the Python or ObjectScript to these L2 machines** (D-2, D-3). The four
  `theorem_raw_executions_refine` are the plug-in points for trace conformance; the journal traces of
  breadth-a-journal-footprints are not replayed through them.
- **The four families are not composed.** They share rdf_edges and ^KG("tout"); their joint behaviour is by inspection:
  R05-3 must also hold for the bucket model (E-INCR), and R03-3's revert-to-marked must end the statement of R03-4 (a
  marked row is not governed, CONTEXT.md:72-73). No joint invariant is proved.
- **Interleavings inside a call** (P-E5) and **an eraser overlapping a writer** (P-E6, P-L2) are not modelled; those are
  where the pin's premises fail.
- Module 03 items not modelled: strict mode and its cache (F-0301, F-0302), refusal answers and decoders (F-0306,
  F-0307), the loader's NaN and index rebuild (F-0308, F-0309), capped lookups (F-C0302), bulk_create_edges and the
  other bulk writers' adoption, Cypher writes, keyed edges.
- Module 05 items not modelled: "now" and time units (F-0502, F-0510; time is not in the model), endpoint and purge
  provenance in the ledger (F-0503 intent-undecided on HD-0501, F-0504, HD-0502's working answer), the non-indexed
  mirror (F-0506), readers' filters and formats (F-0508, F-0509, F-0512), validation (F-0513), changeset collision
  records (F-0511), capacity (F-0514), the driver issue (F-C0502), purge_before's bucket kills, PurgeBucketRange, the
  ms index, registry changes and the backfill/drop migrations.
- HD-0302's working answer and the F-0505/F-0507/F-C0501/F-C1203/F-C0301 remedies are assumptions or proposals, not
  maintainer decisions.
- No progress or liveness property (the explorer's checks are bounded and separate).
- The L1s are new contracts written for this lane; their correspondence to the ontology statements (WRT-*, TMP-*) and
  to the explorer models' invariants is by inspection.

## Debt accounting (for `PROOF-DEBT.md` D-1)

Paid, model-level only, by `proofs-d1c-baseline` and the 10 `proofs-d1c-*` control runs: the §3.3 L1, L2, refinement
and controls items for module 03 (create_edge, store_edge and delete_edge against the temporal row; the ledger statement
link; bulk_create_nodes' server-loader atomicity, as modelled) and module 05 (temporal write, refusal, delete,
purge_raw_before and Purge against the structural row and the ADR-0015 opt-out; bucket aggregates), plus module 12's
prefix erase over the same layout. Still owed under D-1: modules 00-02, 07-10 and 15-17, and the unmodelled parts of 03
and 05 listed in section 10. This lane does not edit `PROOF-DEBT.md` or `STATUS.md` (outside its write scope); the
orchestrator moves the row. The crate's `Cargo.lock` had been committed earlier (a333446f) as a copy of `proofs-d1b`'s;
this lane changed only its root package name.
