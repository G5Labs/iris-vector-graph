# Erasure across stores

As-built transcription at `3eaa79cf` (iteration 65; repaired in iteration 66 after [review-1](../../../uplift/consolidated/review-1/REVIEW.md), see the last section). Owners: [erasure](../../../ontology/features/erasure.g5.md)
(erasure.scope, .live-statements, .history, .kept, .atomic, .atomic.routes, .count, .entry-points,
.entry-points.single-path, .prefix-match), [search.erasure and search.erasure.indexes](../../../ontology/features/search.g5.md#search.erasure),
[algorithms.cache.erasure](../../../ontology/architecture/algorithm-execution.g5.md#algorithms.cache.erasure),
[structure.degree.cache.erase and .uncommitted](../../../ontology/architecture/adjacency-and-derived-data.g5.md#structure.degree.cache.erase).

One store map (`Seq<E>`, an entry per stored row or global node, with its kind, raw graph spelling, ids, triple, edge id,
route table and watermark) holds every store the ontology names. Each Eraser entry point's effect is a spec function of
that map and the call's own arguments, derived from its actual selection rule. The count, the refusals, the transaction
outcome (own rollback, `$Increment` kept by a rollback, chunk commits, caller join or dedicated connection) and the
post-commit route drop are spec functions too; none is an input.

## What is transcribed

| spec fn | source (pin) | what it decides |
|---|---|---|
| `canon`, `in_g` | `Eraser.cls` 117-123 (every predicate) | `COALESCE(graph_id,'') = COALESCE(name,'')`: NULL and `''` are the default graph |
| `ctl`, `valid`, `refused` | `GraphKey.cls` `Validate` 38-48 (`$ZStrip(tGraph,"*C")`); `_validate.py` `validate_graph_name` 19-51; `Eraser.cls` `EraseNodes` 324-326, `nodes_edges.py` 1554 | `"0"` and control characters (0-31, 127 and the C1 range 128-159; Python refuses only the first two, so a C1 name reaches the Eraser and is refused there, still before TSTART) refused before anything; the empty prefix refused first |
| `graph_kill`, `keep_graph`, `erase_graph` | `Eraser.cls` `EraseGraph` 47-305; `Adjacency.RemoveGraph` 428-447; `TemporalIndex.EraseGraph` 366-377; `EraseLedgerFor` 1117-1144; `EraseFHIRGraphRows` 1151-1180 | the graph's rows, documents, legacy and routed vectors, edge vectors, FHIR side rows, adjacency, gen/degc/degw, `^IVG.AdjNoLock`, label/prop/deg2p globals, temporal subtrees, multigraph mode, statements and tuple lookups go; reifications of its edges go; temporal-only settings and FHIR registrations (watermarks reset) stay; `^IVG.AlgoCache` goes for every graph; `^NKG` goes whole when the graph has an interned node or edge (`at_risk_graph`, `GraphEdgesInNKG`/`GraphNodesInNKG`); claimed routes dropped after the commit, their registry row only after a successful drop; orphans emptied, never dropped |
| `count_graph` | `EraseGraph` 217-225 | rdf_edges + nodes `%ROWCOUNT` |
| `prefix_sel`, `list_sel`, `keep_ids`, `erase_ids`, `count_ids`, `live_stmt` | `EraseNodes` 322-351, `EraseNodeIds` 372-388, `EraseIdSet` 467-636, `EraseEdgeRow` 641-680 (667-677: the statement the tuple names), `Adjacency.RemoveNode` 396-423, `TemporalIndex.EraseNodes` 400-444 | prefix ids from node rows of the graph only; listed ids as named, present or not; each id's own stores in the graph; every incident relationship row with its reification, edge vector, edge-route rows, LIVE statement and tuple (a closed statement, `deletedSeq` set, has no tuple and is kept); adjacency and temporal entries with an end in the set; deg2p, `^IVG.AlgoCache`, `^NKG` as the source decides; node rows counted only |
| `keep_edges`, `erase_edges`, `count_edges` | `EraseEdges` 395-463 | every row of each named triple in the graph and what hangs off it (the live statement only); adjacency of the triple; nodes kept; the triple's temporal events kept (EraseEdges calls no TemporalIndex method); `^NKG`, deg2p, cache when anything went; relationship rows counted |
| `keep_all`, `erase_all`, `count_all` | `EraseAll` 709-845 | everything goes except the quarantine, history, FHIR registrations (watermarks reset), the named search indexes and the routed tables it may not or could not drop; the registry is deleted inside the transaction |
| `delete_edge` | `nodes_edges.py` `delete_edge` 1382-1457 | the bypass: the triple's rows and adjacency only |
| `Tx`, `tstart`, `tcommit`, `trollback1`, `rollback_to` | IRIS TSTART / TCOMMIT / TROLLBACK 1 on one process (environment premise below) | the open levels as a stack of journal snapshots (`lv.len()` is `$TLevel`); `$Increment` counters (`St.version`, `St.bucket`) outside the journal |
| `Fault`, `eraser`, `call` | every entry point: `Set tTxnLevel = $TLevel`, TSTART, body, TCOMMIT, the post-commit DROP; the Catch `While $TLevel > tTxnLevel { TROLLBACK 1 }` then `Throw` (`EraseGraph` 54-262, `EraseIdSet` 482-633, `EraseEdges` 412-461, `EraseAll` 712-818) | Refused (before TSTART) / Failed (any partial write `mid` rolled back to the found level; the version stamp and the bucket counters keep what their `$Increment` did) / Count; `call` is the level-0 case |
| `joined_then`, `dedicated_then` | `engine.IRISGraphEngine._iris_obj` 1894-1943 (the Eraser on the caller's process) | the caller's START TRANSACTION, own writes, the erase nested at level 2, then the caller's COMMIT or ROLLBACK (its post-commit DROP runs inside the caller's transaction); a from_connect engine's erase runs at level 0 on its own connection |
| `list_erase_tx`, `list_erase`, `list_erase_joined` | `iris_sql_store.delete_nodes` 1320-1362, `_eraser_txn` 1451-1473, `_write_txn.WriteTxn` begin/commit/rollback/`__exit__` 164-276 | one EraseNodeIds call per 500 ids; unjoined (WriteTxn committed at once) every chunk commits at level 0 and earlier chunks stay erased when a later one fails; joined, IVG's WriteTxn level 2 is rolled back by `Txn_Undo(level)` and the caller's level is left |
| `reifier_sel`, `holds`, `held_sel`, `holding_graphs`, `sweep`, `delete_in_scope` | `nodes_edges.py` `_reifiers_of` 2155-2174, `_graphs_holding` 2134-2153, `_delete_in_scope` 2176-2203, `delete_node` 2227-2268, `bulk_delete_nodes` 2270-2298 | delete_node / bulk_delete_nodes: EraseNodeIds(c, ids), then, for the reifier IDs of the deleted relationships, one EraseNodeIds per graph holding such an ID (node row, or relationship end), in every graph |
| `eraser_of`, `method_ep`, `bda_triples` | the engine and store erase methods | a transcribed table (R1-ER-03: the theorem over it restates it; each method's effect is compared live): every method reaches an Eraser entry point except `delete_edge`; `drop_graph` is `erase_graph`; `bulk_delete_adjacency` is EraseEdges per graph |
| `digest_kind`, `digest_empty` | `GraphStores.Digest` 189-213 over `Inventory` 28-134 | the empty-graph reader |

## Claims (66 verified, vstd only)

Proved over all store maps (no `assume`, `admit` or `external_body`):
- `theorem_graph_erase_removes_scoped`, `theorem_default_graph_both_spellings`,
  `theorem_graph_erase_removes_reifications_and_fhir_side`, `theorem_graph_erase_frame` (every kind but the
  cache, `^NKG`, reifications and routes of another graph is kept), `theorem_graph_erase_keeps_other_reifications`
  (premise `eid_unique`: edge_id is the table's identity), `theorem_graph_erase_keeps_settings`,
  `theorem_graph_erase_keeps_unscoped_except_nkg`, `theorem_graph_erase_statements`, `theorem_graph_erase_routes`,
  `theorem_graph_erase_digest_empty` (content stores only).
- `theorem_ids_erase`, `theorem_prefix_selects_node_rows`, `theorem_ids_erase_statements`, `theorem_edges_erase_statements`,
  `theorem_edges_erase_keeps_nodes`, `theorem_bda_is_erase_edges`, `theorem_methods_reach_eraser`,
  `theorem_drop_graph_is_erase_graph`.
- `theorem_erase_all_empties`, `theorem_erase_all_failed_drop`, `theorem_no_erase_touches_kind`,
  `theorem_no_erase_touches_quarantine`, `theorem_no_erase_touches_history`, `theorem_erase_clears_algo_cache`.
- `theorem_count_ignores_derived`, `theorem_count_adds_rows`.
- `theorem_refusal_changes_nothing` (also on a caller's open transaction), `theorem_unsafe_or_empty_refused` (incl. a
  C1 control), `theorem_failed_call_leaves_stores` (any partial write, any caller level: rows and open levels as found;
  version and bucket counters as their `$Increment` left them), `lemma_eraser_keeps_levels`,
  `theorem_joined_caller_decides`, `lemma_list_keeps_levels`, `theorem_joined_list_erase_keeps_caller_work`.
- Iteration 66: `theorem_graph_erase_call` (count, stores and the version bump of a successful graph erase),
  `theorem_edges_erase_keeps_temporal`, `theorem_delete_node_sweeps_reifier_everywhere` (premise `holding_graphs`:
  `_graphs_holding`'s own result), `lemma_sweep_sub`, `lemma_sweep_removes`,
  `theorem_node_delete_and_bypass_keep_never_kinds` (the sweep and `delete_edge` also leave history, the quarantine and
  the named indexes).

Witnesses (as built; several refute an owner promise):
- `witness_graph_erase_drops_unscoped_nkg` refutes erasure.kept#o01 ([bug-str-118](../../bugs_issues.md#bug-str-118)).
- `witness_empty_digest_bm25_survives` refutes erasure.history#o03 for a row-based empty check and
  search.erasure.indexes#o01 ([bug-srch-001](../../bugs_issues.md#bug-srch-001)).
- `witness_erase_all_keeps_named_indexes` refutes search.erasure.indexes#o03 ([bug-srch-117](../../bugs_issues.md#bug-srch-117)).
- `witness_id_erase_count_omits_relationships` refutes erasure.count#o01 for node erases ([q-007](../../open_questions.md#q-007)).
- `witness_delete_edge_leaves_statement` refutes erasure.live-statements#o01 and single-path#o01
  ([bug-str-013](../../audits/register-20261115/bugs-review.md#bug-str-013)).
- `witness_list_erase_commits_earlier_chunk` is erasure.atomic#o05 and refutes erasure.atomic#o01 for the unjoined list
  path ([bug-led-011](../../audits/register-20261115/bugs-review.md#bug-led-011)).
- Iteration 66: `witness_delete_node_erases_reifier_in_other_graph` (R1-E: the reifier ID's node rows in graph h and the
  default graph go; EraseNodeIds alone keeps both; [bug-str-121](../../bugs_issues.md#bug-str-121) once registered),
  `witness_list_erase_keeps_closed_statement` (R1-ER-04), `witness_edge_erase_leaves_triple_events` (R1-ER-05),
  `witness_failed_call_keeps_increments` (R1-CR-01: rows restored, version and bucket counters moved; reachability of a
  fault after the temporal step is not established).
- `witness_dedicated_erase_survives_caller_rollback` is the q-plt-006 contrast.
- `witness_named_erase_keeps_reifier_node` ([F-1502](../../bugs_issues.md#F-1502)),
  `witness_prefix_leaves_event_ids_remove` (the explicit-ID route around [bug-led-007](../../bugs_issues.md#bug-led-007)),
  `witness_zero_count_with_content_removed`, `witness_digest_reports_kept_setting`, `witness_graph_erase_clears_nolock`.

## Premises and trust

- IRIS journal semantics (environment premise, `trollback1`): TROLLBACK 1 restores every journalled SQL row and global
  Set/Kill made since the innermost TSTART, DDL included (observed for the post-commit DROP inside a caller's
  transaction, I65Y/E1); `$Increment` is not undone. The Eraser's own steps are modelled: the found level, TSTART, the
  single TCOMMIT, the Catch's rollback to the found level; a failing step may leave ANY partial write (`Fault::At.mid`).
  The binding checks it at the reader for one production-reachable failure per path (E3, E4, E5).
- `$Increment` counters a rollback keeps: `^KG("__version")` (St.version) and the temporal `^KG("bucket")` counters
  (St.bucket, `TemporalIndex.RemoveTemporalRow` 357, reached from `EraseIdSet` through `TemporalIndex.EraseNodes`);
  `^KG("gen")` (`Adjacency.Remove`) is also incremented and not modelled as a counter. Open obligation (R1-CR-01): no
  production failure after the temporal step of an ID erase has been constructed, so whether a failed call can leave
  the bucket counters changed is unestablished.
- Names carry no NUL (both checks strip it before validating).
- `holding_graphs`: the graph list the sweep walks is `_graphs_holding`'s result on the state after the first delete
  (computed by the product from the same rows; the binding computes it from the observed map).
- `eid_unique` (one rdf_edges row per edge_id) for the reification frame.
- A routed table is "claimed" when a registry row of the graph names it and its name has the route shape (`tbl > 0`
  stands for `IsRouteName`).
- `df` (the claimed routes whose DROP fails) is an input: no DROP failure was produced on the fixture.
- The temporal aggregates (bucket, tagg, edgeprop, tlast, tin) are one kind for a graph erase; for list erases
  `TemporalIndex.EraseNodes` rewrites them per bucket and they are not modelled at that grain.
- The Eraser's store list is written by hand in `Eraser.cls`; its header's claim that it "derives the list from"
  `Graph.KG.GraphStores` is not true at the pin (only the source-text test `test_eraser_inventory_coverage.py` compares
  the two; R1-ER-09). The model's kinds were taken from the Eraser's actual statements and the ontology's store list.
- The registry rows of non-route (legacy) tables kept by a graph erase are as built; keeping them is unratified, and
  `EraseAll`'s own comment argues for deleting them (open question, R1-ER-08).

## Controls (28, each EXPECTED_FAIL in its named functions)

`spelling-not-coalesced`, `frame-ignores-graph`, `reif-of-all-graphs`, `prefix-from-names`, `empty-prefix-accepted`,
`unsafe-name-accepted`, `count-includes-labels`, `count-ids-includes-edges` (q-007 repair), `orphan-dropped`,
`registry-before-drop`, `erase-all-quarantine`, `erase-all-clears-indexes` (bug-srch-117 repair), `chunks-all-or-nothing`
(bug-led-011 repair), `edge-row-keeps-statement`, `graph-erase-keeps-nkg` (bug-str-118 repair), `fhir-watermark-kept`,
`joined-commits-own`, `delete-edge-through-eraser` (simp-str-001), `failed-call-partial`, `graph-erase-keeps-nolock`.
Iteration 66 rewrote three of them to mutate a product step rather than the definition of the outcome (R1-ER-02):
`failed-call-partial` (the Catch closes its level instead of rolling back: fails `theorem_failed_call_leaves_stores`),
`joined-commits-own` (the Eraser's TCOMMIT ends every level: fails `lemma_eraser_keeps_levels`,
`theorem_joined_caller_decides`), `chunks-all-or-nothing` (re-anchored on `list_erase_tx`); and added
`catch-rolls-back-every-level` (the pre-4.6.4 Catch), `writetxn-undo-ends-caller-level`, `edge-row-kills-closed`,
`edges-erase-temporal` (the R1-ER-05 repair; the reviewer's mutant M1), `delete-node-is-erase-ids` (the iteration-65
mapping), `reifier-sweep-default-graph-only` (the R1-ER-01 repair), `python-control-set`, `no-version-bump`.
The first run of `frame-ignores-graph` and `erase-all-quarantine` named callers that rely on the failing helper's
`ensures` (FAIL_ELSEWHERE, receipts kept); the controls now name `theorem_graph_erase_frame` and
`theorem_no_erase_touches_kind`.

## Product binding (`binding.py`)

The real engine from the pin on the run's own fixture (`ivg-cov-20261118-a-iris`), namespaces I65B-I65E and I66E,
36 cases (iteration 66), AGREES. Each case observes the whole store map before and after the call with an observer independent of the Eraser
(SQL over every table, an ObjectScript `$Query` walk of every global through `iris session`), derives the expected map
and return from the transcription and compares entry by entry, plus the return value or raised error.

- B (graph erase): `erase_graph("g1")` with g1 and g2 sharing node IDs and holding rows, documents, routed vectors
  (a claimed route and an orphan), reifications, FHIR side rows and registrations, temporal edges and a temporal-only
  event, multigraph mode, `^IVG.AdjNoLock`, ledger statements, a BM25 index, the quarantine, `^NKG` and a cached WCC
  answer; then `drop_graph("g2")`, `erase_graph(None)`, `"0"`, `"bad\x01"`, the Eraser's own refusal natively, and an
  empty graph. Readers: `bm25_search` (still answers), `GraphStores.Digest` (only `^IVG.TemporalStructural`),
  `get_node` of the reifier (still holds the edge's properties), `is_multigraph`.
- C (lists): prefix `acme|`, the empty prefix, explicit IDs with no node row, `delete_node`, `bulk_delete_nodes`,
  `store.delete_edges`, the `delete_edge` bypass, `bulk_delete_adjacency` across two graphs.
- D (all): `erase_all` with BM25 and VecIndex indexes, the quarantine and FHIR rows; `bm25_search` after.
- E (transactions): joined erase with the caller's rollback and commit; a joined list erase that fails (an over-long
  ID) with the caller's commit; the unjoined 500 + 2 list (chunk 1 committed); a graph erase failing on an application
  table's foreign key; a from_connect engine's erase under the caller's rollback.
- R (iteration 66, I66E): `delete_node("a", graph="g")` where a->b of g is reified by `ev1`, an unrelated node of graph
  h (R1-E reproduced: ev1 gone from h and from the default graph; `get_node("ev1", graph="h")` None after);
  `bulk_delete_nodes(["c"], graph="g")` (the same through its batch); `store.delete_edges` of a structural triple with
  a timestamped event (row gone, event still answered by `get_edges_in_window`); `store.delete_edges` of a triple with
  a closed and a live statement (live gone, closed kept). B8: `erase_graph("bad\x85")` passes Python's check and is
  refused by GraphKey with every store unchanged.
- The observer now reads every `^IVG.Ledger("rec")` node with a CRC of its value and every `ledger_revisions` row with
  a digest of its columns (R1-ER-07), and each statement's `deletedSeq` (R1-ER-04).
- Detection: a changed observed field, a dropped other-graph entry, a changed history record, a kept other-graph
  reifier node, the version stamp of B1, and six transcription mutants (frame without the graph, count with
  relationships, prefix by name, delete_node without the sweep, relationship erase removing events, row erase killing
  the closed statement) each disagree with the live observations.

Disclosed fixture substitutions (no public writer on this fixture): documents, the quarantine row, FHIR tables (product
DDL) and rows, the orphan route (registry row deleted), the orphan property row, `^IVG.AdjNoLock` marks, and the
application FK table. Not produced: the NULL spelling (every content table declares `graph_id` NOT NULL at the pin),
edge vectors and edge routes, the optimized node table, IVF and PLAID indexes, label sets, Arno, a failed DROP.

Not established: a failed post-commit DROP (needs, for example, a role without the DROP privilege on a route another
user created); `test_eraser_failures.py` was not run (it needs `IVG_NS_IVG236` and opens about 176 connections, beyond
the Community licence's limit; its `BEFORE DELETE` trigger injection is not a production path).

## Latest receipts

- proof `results/erasure_stores/20261118T051838Z-prove/receipt.json` PASS 66 (iteration 66; the first it-66 run
  051023Z, UNEXPECTED 53/2 before the statement theorems carried the live/closed split, is kept)
- controls `results/erasure_stores/20261118T051842Z..052020Z-control-*/receipt.json` 28 EXPECTED_FAIL
- binding `results/erasure_stores/20261118T052216Z-binding/receipt.json` AGREES 36 cases, 11/11 detection
- iteration 65 (superseded, kept): proof 043243Z PASS 49, controls 043246Z..043338Z, bindings 043516Z and the master's 044251Z

## Iteration 66 (review-1 repairs)

| review row | change |
|---|---|
| R1-ER-01 | `delete_in_scope` models `_delete_in_scope`'s reifier sweep for delete_node and bulk_delete_nodes (the same path per batch); `theorem_delete_node_sweeps_reifier_everywhere`, `witness_delete_node_erases_reifier_in_other_graph`; controls `delete-node-is-erase-ids`, `reifier-sweep-default-graph-only`; live R1/R2 in I66E. Not modelled: a failure of the sweep after the first delete committed (the call raises "the node is deleted; the reifier nodes ... are not", and bulk_delete_nodes then counts the batch as failed although its nodes are gone). |
| R1-ER-02 | the transaction is a stack of journal levels; the failed-call theorem holds for any partial write and any caller level, and the joined theorems are derived from the Eraser's TSTART/TCOMMIT, its Catch, IVG's WriteTxn level and the caller's COMMIT/ROLLBACK; controls mutate those steps. Environment premise: IRIS rollback semantics. |
| R1-ER-03 | not changed: `eraser_of`/`method_ep` stay a transcribed table (census row regraded partial). |
| R1-ER-04 | statements are live or closed; the row-level erase removes only the live one, the graph erase both; witness and control; live R4. |
| R1-ER-05 | `theorem_edges_erase_keeps_temporal`, `witness_edge_erase_leaves_triple_events`; the reviewer's M1 is the control `edges-erase-temporal`, which now fails; live R3. |
| R1-ER-06 | the reifier-node residue of a graph erase (`witness_named_erase_keeps_reifier_node`) is proposed as its own obligation of erasure.scope. |
| R1-ER-07 | history observed by content (rec CRC, revision row digest); detection `observed_history_changed`. |
| R1-ER-08, R1-ER-09 | wording corrected here and in the spec comment; question drafted. |
| R1-CR-01 | St.bucket; `witness_failed_call_keeps_increments`; premise above. |
| R1-CB-07 | GraphKey's character set (`python-control-set` control, B8 live); `theorem_graph_erase_call` with the version bump (`no-version-bump`). |
