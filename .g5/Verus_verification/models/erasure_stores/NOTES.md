# Erasure across stores

As-built transcription at `3eaa79cf` (iteration 65). Owners: [erasure](../../../ontology/features/erasure.g5.md)
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
| `valid`, `refused` | `GraphKey.cls` `Validate` 38-48; `_validate.py` `validate_graph_name` 19-51; `Eraser.cls` `EraseNodes` 324-326, `nodes_edges.py` 1554 | `"0"` and control characters refused before anything; the empty prefix refused first |
| `graph_kill`, `keep_graph`, `erase_graph` | `Eraser.cls` `EraseGraph` 47-305; `Adjacency.RemoveGraph` 428-447; `TemporalIndex.EraseGraph` 366-377; `EraseLedgerFor` 1117-1144; `EraseFHIRGraphRows` 1151-1180 | the graph's rows, documents, legacy and routed vectors, edge vectors, FHIR side rows, adjacency, gen/degc/degw, `^IVG.AdjNoLock`, label/prop/deg2p globals, temporal subtrees, multigraph mode, statements and tuple lookups go; reifications of its edges go; temporal-only settings and FHIR registrations (watermarks reset) stay; `^IVG.AlgoCache` goes for every graph; `^NKG` goes whole when the graph has an interned node or edge (`at_risk_graph`, `GraphEdgesInNKG`/`GraphNodesInNKG`); claimed routes dropped after the commit, their registry row only after a successful drop; orphans emptied, never dropped |
| `count_graph` | `EraseGraph` 217-225 | rdf_edges + nodes `%ROWCOUNT` |
| `prefix_sel`, `list_sel`, `keep_ids`, `erase_ids`, `count_ids` | `EraseNodes` 322-351, `EraseNodeIds` 372-388, `EraseIdSet` 467-636, `EraseEdgeRow` 641-680, `Adjacency.RemoveNode` 396-423, `TemporalIndex.EraseNodes` 400-444 | prefix ids from node rows of the graph only; listed ids as named, present or not; each id's own stores in the graph; every incident relationship row with its reification, edge vector, edge-route rows, statement and tuple; adjacency and temporal entries with an end in the set; deg2p, `^IVG.AlgoCache`, `^NKG` as the source decides; node rows counted only |
| `keep_edges`, `erase_edges`, `count_edges` | `EraseEdges` 395-463 | every row of each named triple in the graph and what hangs off it; adjacency of the triple; nodes kept; `^NKG`, deg2p, cache when anything went; relationship rows counted |
| `keep_all`, `erase_all`, `count_all` | `EraseAll` 709-845 | everything goes except the quarantine, history, FHIR registrations (watermarks reset), the named search indexes and the routed tables it may not or could not drop; the registry is deleted inside the transaction |
| `delete_edge` | `nodes_edges.py` `delete_edge` 1382-1457 | the bypass: the triple's rows and adjacency only |
| `call` | the Catch of every entry point (`While $TLevel > tTxnLevel { TROLLBACK 1 }`) | Refused / Failed (stores as found, the version stamp may move) / Count |
| `joined_then`, `dedicated_then` | `_write_txn.WriteTxn.begin` 164-176; `iris_sql_store._eraser_txn` 1451-1473; `engine.IRISGraphEngine._iris_obj` 1894-1943 | the caller's commit or rollback decides a joined erase (its post-commit DROP runs inside the caller's transaction); a from_connect engine's erase commits on its own connection |
| `list_erase`, `list_erase_joined` | `iris_sql_store.delete_nodes` 1320-1362 | one EraseNodeIds call per 500 ids; unjoined, earlier chunks stay erased when a later one fails |
| `eraser_of`, `method_ep`, `bda_triples` | the engine and store erase methods | every method reaches an Eraser entry point except `delete_edge`; `drop_graph` is `erase_graph`; `bulk_delete_adjacency` is EraseEdges per graph |
| `digest_kind`, `digest_empty` | `GraphStores.Digest` 189-213 over `Inventory` 28-134 | the empty-graph reader |

## Claims (49 verified, vstd only)

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
- `theorem_refusal_changes_nothing`, `theorem_unsafe_or_empty_refused`, `theorem_failed_call_leaves_stores`,
  `theorem_joined_caller_decides`.

Witnesses (as built; several refute an owner promise):
- `witness_graph_erase_drops_unscoped_nkg` refutes erasure.kept#o01 ([bug-str-118](../../bugs_issues.md#bug-str-118)).
- `witness_empty_digest_bm25_survives` refutes erasure.history#o03 for a row-based empty check and
  search.erasure.indexes#o01 ([bug-srch-001](../../bugs_issues.md#bug-srch-001)).
- `witness_erase_all_keeps_named_indexes` refutes search.erasure.indexes#o03 ([bug-srch-117](../../bugs_issues.md#bug-srch-117)).
- `witness_id_erase_count_omits_relationships` refutes erasure.count#o01 for node erases ([q-007](../../open_questions.md#q-007)).
- `witness_delete_edge_leaves_statement` refutes erasure.live-statements#o01 and single-path#o01
  ([bug-str-013](../../audits/register-20261115/bugs-review.md#bug-str-013)).
- `witness_list_erase_commits_earlier_chunk` is erasure.atomic#o05 ([bug-led-011](../../audits/register-20261115/bugs-review.md#bug-led-011)).
- `witness_dedicated_erase_survives_caller_rollback` is the q-plt-006 contrast.
- `witness_named_erase_keeps_reifier_node` ([F-1502](../../bugs_issues.md#F-1502)),
  `witness_prefix_leaves_event_ids_remove` (the explicit-ID route around [bug-led-007](../../bugs_issues.md#bug-led-007)),
  `witness_zero_count_with_content_removed`, `witness_digest_reports_kept_setting`, `witness_graph_erase_clears_nolock`.

## Premises and trust

- Atomicity of one call is the IRIS transaction premise: TROLLBACK restores every journaled SQL row and global set in
  the transaction, `$Increment` excepted. The binding checks it at the reader for one production-reachable failure per
  path (E3, E4, E5); the model does not decompose a call into its statements.
- `eid_unique` (one rdf_edges row per edge_id) for the reification frame.
- A routed table is "claimed" when a registry row of the graph names it and its name has the route shape (`tbl > 0`
  stands for `IsRouteName`).
- `df` (the claimed routes whose DROP fails) is an input: no DROP failure was produced on the fixture.
- The temporal aggregates (bucket, tagg, edgeprop, tlast, tin) are one kind for a graph erase; for list erases
  `TemporalIndex.EraseNodes` rewrites them per bucket and they are not modelled at that grain.

## Controls (20, each EXPECTED_FAIL in its named functions)

`spelling-not-coalesced`, `frame-ignores-graph`, `reif-of-all-graphs`, `prefix-from-names`, `empty-prefix-accepted`,
`unsafe-name-accepted`, `count-includes-labels`, `count-ids-includes-edges` (q-007 repair), `orphan-dropped`,
`registry-before-drop`, `erase-all-quarantine`, `erase-all-clears-indexes` (bug-srch-117 repair), `chunks-all-or-nothing`
(bug-led-011 repair), `edge-row-keeps-statement`, `graph-erase-keeps-nkg` (bug-str-118 repair), `fhir-watermark-kept`,
`joined-commits-own`, `delete-edge-through-eraser` (simp-str-001), `failed-call-partial`, `graph-erase-keeps-nolock`.
The first run of `frame-ignores-graph` and `erase-all-quarantine` named callers that rely on the failing helper's
`ensures` (FAIL_ELSEWHERE, receipts kept); the controls now name `theorem_graph_erase_frame` and
`theorem_no_erase_touches_kind`.

## Product binding (`binding.py`)

The real engine from the pin on the run's own fixture (`ivg-cov-20261118-a-iris`), namespaces I65B-I65E, 28 cases,
AGREES. Each case observes the whole store map before and after the call with an observer independent of the Eraser
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
- Detection: a changed observed field, a dropped other-graph entry, and three transcription mutants (frame without the
  graph, count with relationships, prefix by name) each disagree with the live observations.

Disclosed fixture substitutions (no public writer on this fixture): documents, the quarantine row, FHIR tables (product
DDL) and rows, the orphan route (registry row deleted), the orphan property row, `^IVG.AdjNoLock` marks, and the
application FK table. Not produced: the NULL spelling (every content table declares `graph_id` NOT NULL at the pin),
edge vectors and edge routes, the optimized node table, IVF and PLAID indexes, label sets, Arno, a failed DROP.

Not established: a failed post-commit DROP (needs, for example, a role without the DROP privilege on a route another
user created); `test_eraser_failures.py` was not run (it needs `IVG_NS_IVG236` and opens about 176 connections, beyond
the Community licence's limit; its `BEFORE DELETE` trigger injection is not a production path).

## Latest receipts

- proof `results/erasure_stores/20261118T042417Z-prove/receipt.json` PASS 49
- controls `results/erasure_stores/20261118T0424*-control-*/receipt.json` 20 EXPECTED_FAIL
- binding `results/erasure_stores/20261118T042401Z-binding/receipt.json` AGREES 28 cases, 5/5 detection
