# Iteration 65 handoff — erasure across stores: what each erase entry point removes, keeps and returns

Builder: Opus 5.5 (high). Assignment: [ASSIGNMENT.txt](ASSIGNMENT.txt). Start commit `97020aa3` (iteration 64's
integration). Product pin `3eaa79cf`; no product file was edited (`git diff 3eaa79cf -- iris_vector_graph iris_src api`
is empty). The STOP file was checked throughout and was never present. Fixture: the run's own
`ivg-cov-20261118-a-iris` (127.0.0.1:36481), namespaces `I65*` only.

## 1. Result

| | start (`97020aa3`) | end |
|---|---:|---:|
| erasure page (features/erasure.g5.md) full / total | 2 / 47 (4.3%) | **45 / 49 (91.8%)** |
| the 15 changed blocks, full / total | 7 / 62 | **57 / 65** |
| whole foundation: full / partial / absent | 744 / 686 / 667 of 2097 | **794 / 666 / 640 of 2100** |
| full/total, recorded | 35.5% | **37.8%** |
| proved over the full stated scope | 196 | 227 |
| proved incl. narrowed / bounded / refuted | 1105 / 1 / 145 | 1138 / 1 / 152 |
| active bindings (member_reach) | 797 / 4130 | **824 / 4130** |

- **New model:** [erasure_stores](../../../Verus_verification/models/erasure_stores/NOTES.md), 49 verified, vstd only (no
  `assume`, `admit` or `external_body`), 20 controls each EXPECTED_FAIL in its named functions.
- **Live binding:** 28 cases on the real engine, AGREES at entry level over every store.
- **Detection:** five checks fire — a changed observed field, a dropped other-graph entry, and three transcription
  mutants.
- **Findings:**
  - opened: bug-str-118, bug-str-119, bug-str-120 (model only) and bug-srch-117;
  - reproduced for the first time, each with a passing neighbour: bug-led-011 and bug-str-013.
- **Owner text:** four statements the assignment named were checked, and each was corrected or confirmed (§6).

**Scope change vs retained obligations.** There are 3 new obligations, all from the corrected owner text:
erasure.atomic#o06 (absent), erasure.entry-points.single-path#o04 (full) and search.erasure.indexes#o05 (full).
On the 51 retained rows the regrade changed:

| transition | rows |
|---|---:|
| absent → full | 28 |
| partial → full | 20 |
| full → full (re-cited) | 2 |
| partial → partial (re-cited) | 1 |

No row was downgraded.

## 2. The model and what it proves

`erasure_stores.rs` keeps one store map: a sequence of entries, each with a kind, the raw graph spelling, the IDs or
triple, the edge ID, the route table and the watermark. The kinds cover every store
[features/erasure.g5.md](../../../ontology/features/erasure.g5.md) names, plus the ones the code touches:
- node, label, property and relationship rows;
- documents; legacy, routed and edge vectors; the registry and the routed tables;
- reifications; FHIR side rows and FHIR registrations with their watermarks; the quarantine;
- `^KG` out/in, gen, degc and degw, and `^IVG.AdjNoLock`; label, property and deg2p globals; the temporal subtrees;
- temporal-only settings, multigraph mode and the algorithm cache;
- ledger stmt, tuple and rec;
- `^NKG`, label sets, merged counts and Arno;
- `^BM25Idx`, `^IVF`, `^PLAID` and `^VecIdx`.

Each entry point's effect is derived from its own selection rule:
- `EraseGraph`: the `COALESCE` predicate on both sides;
- `EraseNodes`: IDs taken from node rows of the graph;
- `EraseNodeIds`: the IDs named, present or not;
- `EraseEdges`: the rows of each named triple;
- `EraseAll`;
- the `delete_edge` bypass.

The model also derives each call's count and refusal. It represents the transaction boundary where it changes the
outcome:
- the Eraser rolls back to the level it found, and a rollback does not undo `$Increment`;
- the store sends one call per 500 IDs;
- a joined call lets the caller's commit or rollback decide;
- a `from_connect` call runs on a dedicated connection;
- the claimed-route DROP runs after the commit.

Full table: [NOTES](../../../Verus_verification/models/erasure_stores/NOTES.md).

**Proved (all store maps).** Premises are as stated:

| property | premise |
|---|---|
| `theorem_graph_erase_removes_scoped` | every graph-scoped kind of g goes, in any spelling |
| `theorem_default_graph_both_spellings` | — |
| `theorem_graph_erase_frame` | every kind outside g except the derived `^IVG.AlgoCache`/`^NKG` and the reifications/routes the next two theorems own |
| `theorem_graph_erase_keeps_other_reifications` | premise `eid_unique`: edge_id is the table's identity |
| `theorem_graph_erase_routes` | claimed / orphan / failed drop |
| `theorem_graph_erase_keeps_settings` | — |
| `theorem_graph_erase_keeps_unscoped_except_nkg` | — |
| `theorem_graph_erase_statements` | — |
| `theorem_graph_erase_digest_empty` | content stores only |
| `theorem_ids_erase`, `theorem_prefix_selects_node_rows` | — |
| `theorem_ids_erase_statements`, `theorem_edges_erase_statements` | iff: only the deleted relationships' |
| `theorem_edges_erase_keeps_nodes` | — |
| `theorem_bda_is_erase_edges` | one graph |
| `theorem_methods_reach_eraser`, `theorem_drop_graph_is_erase_graph` | — |
| `theorem_erase_all_empties`, `theorem_erase_all_failed_drop` | — |
| `theorem_no_erase_touches_kind` (Rec, Quar and the four named indexes; every entry point and outcome) | — |
| `theorem_no_erase_touches_quarantine`, `theorem_no_erase_touches_history` | — |
| `theorem_erase_clears_algo_cache` | — |
| `theorem_count_ignores_derived`, `theorem_count_adds_rows` | — |
| `theorem_refusal_changes_nothing`, `theorem_unsafe_or_empty_refused` | — |
| `theorem_failed_call_leaves_stores` | the IRIS transaction premise |
| `theorem_joined_caller_decides` | — |

**Refuted owner promises (modelled counterexample with a reachable witness, each reproduced live unless stated):**

| witness | owner promise | live evidence |
|---|---|---|
| `witness_graph_erase_drops_unscoped_nkg` | erasure.kept#o01: unscoped stores kept | B1 |
| `witness_empty_digest_bm25_survives` | erasure.history#o03: an empty check means nothing live | B1 readers |
| `witness_erase_all_keeps_named_indexes` | search.erasure.indexes#o03; erasure.kept#o07 for the graphless indexes | D1 |
| `witness_id_erase_count_omits_relationships` | erasure.count#o01, for node erases | C1 |
| `witness_delete_edge_leaves_statement` | single-path#o01, live-statements#o01 | C7 |
| `theorem_erase_all_failed_drop` | routes#o03, erase-all variant | model only |

**As-built witnesses for as-built obligations:**

| witness | as-built obligation | live evidence |
|---|---|---|
| `witness_list_erase_commits_earlier_chunk` | atomic#o05 | E4 |
| `witness_dedicated_erase_survives_caller_rollback` | q-plt-006 | E6 |
| `witness_prefix_leaves_event_ids_remove` | prefix-match#o03 contrast | C1 / C3 |
| `witness_zero_count_with_content_removed` | — | — |
| `witness_digest_reports_kept_setting` | — | — |
| `witness_named_erase_keeps_reifier_node` | F-1502 | B1 reader |
| `witness_graph_erase_clears_nolock` | — | B1 |

**Controls (20).** Each removes or changes a decisive selection, frame or refusal, or applies a repair:

| kind | controls |
|---|---|
| selection | `spelling-not-coalesced`, `prefix-from-names`, `reif-of-all-graphs` |
| frame | `frame-ignores-graph`, `erase-all-quarantine`, `fhir-watermark-kept`, `graph-erase-keeps-nolock` |
| refusal | `empty-prefix-accepted`, `unsafe-name-accepted` |
| count | `count-includes-labels`, `count-ids-includes-edges` |
| routes | `orphan-dropped`, `registry-before-drop` |
| transaction | `chunks-all-or-nothing`, `joined-commits-own`, `failed-call-partial` |
| statements | `edge-row-keeps-statement` |
| repairs | `graph-erase-keeps-nkg`, `erase-all-clears-indexes`, `delete-edge-through-eraser` |

The first run of two controls returned FAIL_ELSEWHERE: `frame-ignores-graph` and `erase-all-quarantine`. The named
callers rely on a helper's `ensures`, so the failure showed up in the helper, not in them. The names were corrected to
the helpers, and those receipts are kept.

**Receipts:**
- proof [20261118T043243Z-prove](../../../Verus_verification/results/erasure_stores/20261118T043243Z-prove/receipt.json);
- controls `20261118T043246Z`…`043338Z-control-*`;
- binding [20261118T043516Z-binding](../../../Verus_verification/results/erasure_stores/20261118T043516Z-binding/receipt.json).

Earlier, superseded runs are kept: proofs 040711Z and 042417Z, the two control series, and binding 042401Z.

## 3. Runtime correspondence (binding.py)

`binding.py` runs the real engine from the pin through `run_binding.py`, one fresh namespace per scenario. Each case
works the same way:
- It observes the whole store map before and after the call, with an observer independent of the Eraser: SQL over every
  table and an ObjectScript `$Query` walk of every global.
- It derives the expected map and return from a Python transcription of the model's spec functions.
- It compares the two entry by entry, plus the return value or raised error.

| scenario | cases | what was observed |
|---|---|---|
| I65B graph erase | B0-B7 + 4 readers | g1 and g2 share node IDs. The fixture holds every reachable store, an orphan route, `^IVG.AdjNoLock` and a cached WCC answer. `erase_graph`, `drop_graph`, `erase_graph(None)`, `"0"`, `"bad\x01"`, the Eraser's own refusal and an empty graph all agree. `bm25_search` still answers. Digest lists only `^IVG.TemporalStructural`. The reifier node keeps `secret-g1`. `is_multigraph` is g1 False, g2 True. B0: NULL is refused by every content table. |
| I65C list erases | C1-C8 | prefix `acme|` (returns 2 node rows; `acme-health|1` kept); empty prefix refused; explicit IDs with no node row (returns 0, removes the temporal event and the orphan prop); `delete_node`; `bulk_delete_nodes` [2, 0]; `store.delete_edges` (stmt and tuple removed); `delete_edge` (stmt, tuple and reification kept); `bulk_delete_adjacency` across two graphs (returns 1) |
| I65D erase-all | D1 + reader | 13 returned. Only Quar, Rec, FhirReg (wm reset), 95 `^BM25Idx` and 10 `^VecIdx` nodes survive. `bm25_search` still answers. |
| I65E transactions | E1-E6 | E1: joined, then rollback; everything back, including the routed table and its registry row. E2: joined, then commit. E3: a joined list erase fails (over-long ID); the caller's write survives its commit. E4: unjoined 500 + 2; chunk 1 committed, chunk 2 raised. E5: a graph erase fails on an application FK; every store unchanged. E6: a `from_connect` engine's erase survives the caller's rollback. |

**Failure injections, both reachable in production:**
- an over-long node ID in a caller's ID list (`<SUBSCRIPT>` inside `EraseNodeIds`);
- an application table with a foreign key to `Graph_KG.nodes` (`DELETE FROM nodes` fails with -124).

**Disclosed direct-SQL fixture rows (no public writer on this fixture):**
- documents;
- the quarantine row;
- the FHIR tables (product DDL through the product's splitter) and their rows;
- the orphan route (a real route with its registry row deleted);
- the orphan property row;
- the `^IVG.AdjNoLock` marks.

**Not produced:**
- the NULL spelling (unreachable at the pin);
- edge vectors and edge routes, the optimized node table;
- IVF and PLAID indexes, label sets, Arno;
- a failed DROP: **not established**, so bug-str-120 is model only.

**Community-licence limit.** [test_eraser_failures.py](../../../../tests/integration/test_eraser_failures.py) was not
run, and no product code was changed. Per the [test-obligation recovery](test-obligations.md) §1:
- it skips without `IVG_NS_IVG236`;
- it opens about 176 connections, beyond Community's limit;
- its `BEFORE DELETE` trigger injection is a test substitution, not a production path.

The binding's E3, E4 and E5 cover its rule (a refused delete erases nothing) at the reader for every store, not only the
SQL row counts.

## 4. Per closed obligation

[closed-obligations.md](closed-obligations.md) lists, for each of the 54 rows this iteration changed or added:
- the property and its check;
- the premises;
- the observed live case;
- the source members the crosswalk binds to that property.

The proof receipt is `20261118T043243Z-prove` and the binding receipt is `20261118T043516Z-binding`.
[regrade-ledger.tsv](regrade-ledger.tsv) has every column change.
[regrade-tools/regrade.py](regrade-tools/regrade.py) replays it on the iteration-64 census TSVs.

## 5. Census before and after (per block)

[census-per-block.md](census-per-block.md) is the full table. Summary:

| block | full before → after | note |
|---|---|---|
| erasure.scope (8) | 0 → 8 | all proved over the full stated scope |
| erasure.live-statements (3) | 1 → 3 | |
| erasure.history (3) | 0 → 2 | #o02 is a documentation obligation, absent |
| erasure.kept (7) | 0 → 7 | #o01 and #o07 refuted, as built |
| erasure.atomic (5 → 6) | 0 → 5 | new #o06 absent: no lock model |
| erasure.atomic.routes (4) | 0 → 4 | #o03 refuted for erase-all, model only |
| erasure.count (4) | 0 → 4 | #o01 refuted for node erases |
| erasure.entry-points (6) | 0 → 6 | |
| erasure.entry-points.single-path (3 → 4) | 1 → 4 | |
| erasure.prefix-match (4) | 0 → 2 | #o02 (the redaction contrast) and #o04 (orphan props: no kept-side theorem) stay partial |
| search.erasure (4) | 1 → 4 | |
| search.erasure.indexes (4 → 5) | 2 → 4 | #o04 (replacing restore) stays absent |
| algorithms.cache.erasure (1) | 0 → 1 | |
| structure.degree.cache.erase (2) | 1 → 2 | |
| structure.degree.cache.uncommitted (4) | 1 → 1 | #o04 restated, still partial: the 5 s timeout and the rebuild's clearing are not modelled |

The redaction.after-erasure* rows were reviewed and are unchanged: this model has no redaction state.

**Gates** (raw in [gates/](gates/)):

| gate | result |
|---|---|
| `tools/census.py` (with the lint) | exit 0, PASS, deterministic |
| `check_evidence` | FRESH |
| `check_consolidated` (`G5_GUIDE=$G5_HARNESS/guidance`) | PASS, against the new [correspondence stamp](correspondence-inputs.json); before it, the gate showed only my files changed |
| `check_ontology` | 0 issues, 17 warnings (unchanged) |
| `check_findings` | No problems found |

**Member reach** ([member-delta.json](member-delta.json)):

| measure | count |
|---|---:|
| active bindings | 797 → 824 |
| gained an active binding | 27 |
| newly reached by a locator | 22 |
| overlap | 22 |
| distinct | 27 |
| losses | 0 |

The 27 members are:
- the Eraser's EraseGraph, EraseNodes, EraseNodeIds, EraseAll, EraseEdgeRow, EraseLedgerFor, EraseFHIRGraphRows,
  CollectOrphanRoutes, InvalidateDerived and GraphEdgesInNKG;
- Adjacency RemoveGraph and RemoveNode;
- TemporalIndex EraseGraph and EraseNodes;
- GraphIndex.DropNKG, GraphKey.Validate and GraphStores.Digest;
- the engine's erase_graph, drop_graph, erase_all, delete_nodes_by_prefix and bulk_delete_adjacency;
- `validate_graph_name`;
- the store's delete_nodes, delete_edges, delete_nodes_by_prefix and `_eraser_txn`.

## 6. Owner statements and ontology edits

Governing text was changed in four places, keeping intent apart from what is built today. Each change is noted in the
block's metadata.

1. **erasure.atomic, working assumption 2** was factually wrong as built. It said "Erasure holds [the head lock]
   through the outer transaction". No erase path takes `^IVG.Ledger("head")`: Eraser.cls has no Lock, and neither do
   the engine or store callers (F-1114). It is now labelled intended (HD-1201), with "Today no erase path takes the
   head lock, and only redaction's final step re-checks liveness under it". New obligation #o06.
2. **erasure.entry-points.single-path.** The policy stays. A bullet was added: "Today `delete_edge` runs its own
   delete … leaves the statement, reification and edge vector" (bug-str-013, reproduced as C7). New obligation #o04.
3. **search.erasure.indexes, bullets 1-2.** The intent stays. A bullet was added: "Today no erase empties a named
   index" (bug-srch-117, reproduced as D1). New obligation #o05.
4. **structure.degree.cache.uncommitted, bullet 3.** "until the next rebuild" became "until the next rebuild or erase
   of that graph": `RemoveGraph` kills `^IVG.AdjNoLock(g)` (B1).

Metadata only (no governing text):
- the model is linked from all 15 blocks in its manifest;
- iteration-65 evidence notes and finding back-links were added;
- the empty-graph reader is named in erasure.history's metadata: `GraphStores.Digest`, which still lists kept
  configuration.

erasure.kept's lead ("keeps … stores that belong to no single graph") is contradicted as built (bug-str-118). I did not
reword it, because it may be the intended policy for content stores. Its census row carries an `owner-contradicted:`
gap, and the metadata says what happens today.

## 7. Findings

| finding | change | evidence |
|---|---|---|
| [bug-str-118](../../../Verus_verification/bugs_issues.md#bug-str-118) (Low, Open) | new: a single-graph erase drops `^NKG` and every graph's cached answers | E2E, B1 |
| [bug-str-119](../../../Verus_verification/bugs_issues.md#bug-str-119) (Low, Open) | new: a joined graph erase drops its routed tables inside the caller's transaction | E2E (ordering), E1. The caller's rollback restored the table; the damage the Eraser's comment fears was not seen. |
| [bug-str-120](../../../Verus_verification/bugs_issues.md#bug-str-120) (Low, Open) | new: erase-all deletes the registry before its drops, so a failed drop leaves an orphan | model only |
| [bug-srch-117](../../../Verus_verification/bugs_issues.md#bug-srch-117) (Medium, Open) | new: erase-all leaves every named index | E2E, D1; iteration-63 §6.1 #3 |
| bug-led-011 | reproduction added to the [review record](../../../Verus_verification/audits/register-20261115/bugs-review.md#bug-led-011) | E4, with E3 as the passing neighbour |
| bug-str-013 | reproduction added to the [review record](../../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-013) | C7, with C6 as the passing neighbour |
| F-1502 (reifier node), F-1114 (head lock), bug-srch-001, bug-led-007/010, q-007, q-plt-006, q-srch-001 | linked, not duplicated | F-1502 re-observed; for q-007, prefix and ID erases count node rows only |

q-009 is unchanged (temporal-only liveness for redaction). The C3 case shows an explicit-ID erase reaching the
temporal-only events the prefix erase leaves, which gives the operator a route around bug-led-007/010.

## 8. Predictions

Graded in [PREDICTIONS-graded.md](PREDICTIONS-graded.md).

- **Master:** 10 supported, 3 partly supported, 0 wrong.
  - E2: NULL is unreachable at the pin.
  - E6: the `acme` half was checked in the model only.
  - E11: the outcome depends on how the engine was opened.
- **Builder:** of 22 workflow predictions, 15 supported, 6 partly supported, 1 wrong (P5b: the joined drop is not
  deferred); of 4 owner checks, 3 supported and the head-lock check wrong. The wrong sub-claims:
  - NULL is reachable;
  - a long name is refused;
  - prefix and ID counts include edges;
  - the drop runs outside the caller's transaction;
  - the head lock is taken.
- **Neither set predicted:**
  - the unscoped `^NKG` drop;
  - the reifier-node residue;
  - Digest listing kept configuration;
  - erase-all's registry ordering.

## 9. Limitations

- **The grades rest on a transcription.**
  - Most universal theorems follow in one step from the transcribed `keep_*` predicates.
  - Their correspondence to the product comes from the entry-level live comparison on these fixtures: 28 cases, two
    graphs, small data.
  - It is not a proof of the ObjectScript bodies.
  - An independent reviewer should sample the 50 newly full rows (48 retained, 2 new), especially the 31 graded proved
    over the full scope.
- **One erase call is atomic by premise.**
  - The model takes the IRIS transaction premise for a single call's atomicity, and does not decompose the call into
    statements.
  - E5 checks it at the reader for one failure point, the nodes DELETE.
  - E3 and E4 check it for the list path.
- **Stores not populated live:** kg_EdgeEmbeddings and edge routes, the optimized table, IVF, PLAID, label sets and
  Arno. They rest on the model and source reading. The temporal aggregates are not compared for list erases.
- **Paths not exercised:**
  - erase_bare_nodes;
  - Cypher `DELETE` / `DETACH DELETE`;
  - delete_reification;
  - temporal purge;
  - FHIR resync;
  - `_delete_in_scope`'s reifier-node cleanup, which the model does not represent;
  - strict-mode refusal of the erase methods.
- **The NULL spelling** is proved in the model but unreachable on a current schema.

## 10. Residual work and recommendation

**Residual in this family:**
- erasure.atomic#o06: needs a lock model of erase against commit and redaction (HD-1201, q-004).
- erasure.prefix-match#o02 and #o04.
- search.erasure.indexes#o04: replacing restore, bug-plt-024.
- structure.degree.cache.uncommitted#o02-o04: the lock timeout.
- erasure.history#o02: documentation.
- A production-reachable failed DROP, to settle bug-str-120. For example, a role without the DROP privilege on a route
  another user created; it needs user creation on the fixture.
- The other deletion paths that bypass the Eraser: Cypher `DELETE`, delete_reification, temporal purge and FHIR resync.

**Recommendation for the next material gap:**
1. An independent review sample of this iteration's 50 newly full rows.
2. Then the strict-mode and security surfaces, the remaining large under-modelled area from the iteration-63 queue.

Within erasure, the most consequential open item is the serialisation of erase against redaction and ledger commits
(HD-1201 / q-004, bug-002). The owner's intended lock is not built. A model with uncommitted erase state and the head
lock would connect erasure.atomic#o06, redaction.after-erasure#o01 and F-1114.
