# Iteration 57: W61, writes and deletes → adjacency → traversal answers, by strategy

Before image `b63a5ec1` (the master's inventory commit after seal 56). Product `3eaa79cf` unchanged: nothing outside
`.g5/` changed (`git diff b63a5ec1 -- . ':!.g5'` empty; no untracked file outside `.g5/`).
Commits:
- `9f74e690`: the freeze. It committed only [w61-PAIRS.md](w61-PAIRS.md), before any deciding source in
  `iris_sql_store.py`, `Traversal*.cls`, `Adjacency.cls` or `VarLength.cls` was read.
- `6ba3a418`: checkpoint with the three models, registers and owners integrated.
- The seal.

Guidance read at the start: `$G5_HARNESS/AGENTS.md`; `Verus/{uplift, uplift-iteration, uplift-scoring, setup_foundation,
verification}.md`; `uplift-intent-recovery.md`; `ontology-format.md`; `setup_foundation.md`; the runbook's continuation
section; and the binding-integrity rule of `assignments/iteration-56.txt`. `open_questions.md` changed only by two
appended evidence paragraphs (`structure.rebuild.failure`, `HD-1003`); no card, anchor, field or saved answer was
touched. Quarantine was respected: no iteration-13 Cypher `MERGE` material and no evaluator-private ledger. Native
evidence comes only from `ivg-cont-20261117-iris`, namespace USER, with fresh prefixes `i57a_`, `i57b_`, `i57c_` and
`i57r_` and named graphs `i57ag…` and `i57bg…`. No other container was touched and no STOP file appeared. The Arno/NKG
library is absent, so every Arno branch stays conditional; the fixture always took the ObjectScript walk (below).

**Sub-agents.** Two workers ran in parallel, each owning its own files:
- W1, traversal strategies: B1-B7, S1-S3 and N1-N2, model `traversal_strategy`, directory [strategy/](strategy/).
- W2, adjacency maintenance: D1-D4 and R1-R3, model `adjacency_maint`, directory [adjacency/](adjacency/).

The builder alone edited the shared registers (`bugs_issues.md`, `crosswalk/*.tsv`, `families.tsv`, `coverage.md`,
`open_questions.md`, `runbook.md`) and the ontology. The harness refused W2's Write of `findings.md` and `owners.md`, so
the builder saved them from W2's report. Every receipt was re-run by the builder before sealing (see "Re-verification"
below). That re-run surfaced the iteration's most consequential finding (bug-str-115), which the builder then modeled as
`rebuild_reads`.

## Predictions ([w61-PAIRS.md](w61-PAIRS.md), frozen at `9f74e690`)

There were 15 workflows. 13 had two neighbors (26 predictions); R3 and N2 had one each. Details per case are in
[strategy/OBSERVED.md](strategy/OBSERVED.md) and [adjacency/OBSERVED.md](adjacency/OBSERVED.md).

| ID | Verdict | Note |
|---|---|---|
| B1 BFS default vs named graph | held | ObjectScript strategy on both; the named graph's rows only |
| B2 ObjectScript vs SQL fallback | held | same rows (set, order, type) in all 19 forced pairs |
| B3 cycles, self-loops, parallel edges | held | the source is never a row; a parallel edge's target appears once |
| B4 cap | held | 0 returns every row; k returns the first k rows |
| B5 direction in/both | held | |
| B6 ends-only walk vs BFS | held | the trail walk ends at the source over a 2-cycle; BFS never lists it |
| B7 k-hop after a write and after a delete | held | |
| D1 delete by prefix, one graph | held (both) | the other graph is untouched |
| D2 delete an edge held in two graphs | held (both) | beyond the prediction: the merged `^NKG` edge stays (`HeldElsewhere`) |
| D3 store/engine/Cypher deletes, multigraph `DELETE r` | held (both) | survivor keeps its weight; degree −1 |
| D4 labels | held (both) | |
| R1 rebuild vs incremental, reweight | held (both) | proved for every admissible history |
| R2 two-hop fast vs exact | **partial** | the frozen value held (fast 3, exact 1), but it contradicts the method's own documentation: **bug-str-117** |
| R2 B stale stats | held | |
| R3 `^NKG` after deletes | held | `sync()` writes `^NKG` with the ObjectScript builder (no Arno) |
| S1 length vs path, out/both, multigraph | held | |
| S2 direction in | held | the owner's working assumption named the gap; now registered as **bug-str-113** |
| S3 named graph | held | |
| N1 knn route / no route | held | |
| N2 `_khop_fallback` | **partial** | the premise was wrong: there is no native k-hop with an SQL fallback (`khop` always runs the ObjectScript walk, and the store's `_khop_fallback` is an uncalled stub); its "graph scoping preserved" half missed because khop has no graph argument (F-1009) |

Totals: 27 of 28 single predictions held in value. Of the 15 workflows, 13 held fully and 2 were partial (R2, N2). No
frozen prediction missed outright; one half (N2's scoping) missed.

Found after the freeze, outside the frozen cases:
- **bug-str-114**: a direction text other than exactly out/in/both is never refused. W1 found it while reading the source.
- **bug-str-115**: traversal reads during another session's `sync()` see a purged index. Found when the builder's
  re-verification overlapped W2's `sync()`. Workflow 3 asked about rebuilds, but no frozen prediction covered reads
  during one.

## Findings

New (matched by trigger and observable consequence against `bugs_issues.md`, the audit archive and KNOWN_ISSUES):

| ID | Severity | Trigger → observable | Found by / reproduced by |
|---|---|---|---|
| [bug-str-115](../../../Verus_verification/bugs_issues.md#bug-str-115) | Medium | reads in one session while another runs `sync()` on a declared index → khop answers the seed alone, `shortest_path_length` answers −1, `execute_bfs` types are blank (4,481 of 58,520 reads) | the builder's overlapping re-run / [race probe](rebuild_race/race_probe.py), `rebuild_reads` binding |
| [bug-str-117](../../../Verus_verification/bugs_issues.md#bug-str-117) | Medium | `khop2_count_fast` right after `sync()` → the sum of middle out-degrees (3, counting the source and repeats); after any write → the walked count (1) | R2 partial / `adjacency_maint` binding |
| [bug-str-113](../../../Verus_verification/bugs_issues.md#bug-str-113) | Low | store `shortest_path_length(…,'in')` → the outgoing length (−1 where `execute_shortest_path` answers 2, and 2 where it answers −1) | S2 / `traversal_strategy` binding |
| [bug-str-114](../../../Verus_verification/bugs_issues.md#bug-str-114) | Low | `execute_bfs` with "OUT", "sideways", "outbound" or "inbound" → the SQL fallback: an undirected walk with blank types, or the edge rows instead of `^KG`; never refused | W1 source read / `traversal_strategy` binding |

Inherited, strengthened:
- [F-1009](../../../Verus_verification/bugs_issues.md#F-1009): khop on a seed held only by a named graph. Now E2E
  reproduced, with the general theorem `theorem_khop_ignores_named_graphs`.
- [bug-plt-116](../../../Verus_verification/bugs_issues.md#bug-plt-116): the shared-triple `^NKG` mechanism is modeled
  (`theorem_nkg_held_elsewhere`).

Questions: none opened. Evidence was appended to `structure.rebuild.failure` and `HD-1003`. Simplifications: none.
Discoveries vs repairs: all four new entries came from this iteration's own search; none was supplied by a review.

## Models and receipts (final candidate)

| Model | Verified | Controls | Binding |
|---|---|---|---|
| [`traversal_strategy`](../../../Verus_verification/models/traversal_strategy/NOTES.md) (new, W1) | 30 | 19/19 | AGREES 73; 19/19 mutations, tamper detected |
| [`adjacency_maint`](../../../Verus_verification/models/adjacency_maint/NOTES.md) (new, W2) | 35 | 14/14 | AGREES 24; 12/12 mutations, tamper detected |
| [`rebuild_reads`](../../../Verus_verification/models/rebuild_reads/NOTES.md) (new, builder) | 5 | 4/4 | AGREES (58,520 reads during sync, 4,481 seed-alone); swap mutation and tamper detected |

Each answer is derived from modeled state:
- `traversal_strategy`: from a finite edge sequence (graph, source, type, target, edge key). The strategy choice is
  derived from (Arno capability, graph, direction, other graphs' edges); every strategy's rows, lengths and ends are
  functions of the edges.
- `adjacency_maint`: `^KG` entries, keyed children and counts, labels, degree and the merged `^NKG` edge, derived from
  a write/delete history.
- `rebuild_reads`: the index a reader sees, derived from the rebuild's own steps (purge, then refill in an unspecified
  order).

General theorems:
- ObjectScript rows equal SQL fallback rows for every edge set.
- Rebuild equals incremental for every admissible history.
- Every rebuild exposes a seed with no out-edge.

Domains and exclusions are in each NOTES.md.

**Re-verification by the builder:**
- Proofs re-run PASS: `traversal_strategy` 30 (`20261117T075007Z`), `adjacency_maint` 35 (`075655Z`).
- Full control suites re-run: 19/19 and 14/14 EXPECTED_FAIL, none ERROR or surviving.
- Bindings re-run sequentially: `traversal_strategy` AGREES 73 (`075638Z`), `adjacency_maint` AGREES 24 (`075646Z`).

Unsuccessful runs kept:
- `traversal_strategy` `20261117T075247Z-binding` DISAGREES: the builder's re-run overlapped W2's `sync()`. This is the
  product behavior of bug-str-115, not a harness fault.
- `traversal_strategy` `074043Z-binding` DISAGREES: W1's harness history errors, since fixed.
- `adjacency_maint` `074356Z-binding` DISAGREES: harness listing error.
- Two FAIL_ELSEWHERE `adjacency_maint` controls: their expected-item lists were too narrow, since corrected.
- `rebuild_reads` `075603Z-binding` DISAGREES: the harness judged two reads at two moments as one, since fixed.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings rose from **662 to 696** (+34, 0 lost). Union reach (active plus baseline historical locators) rose from
**886 to 907**. Of the 34:
- **21 newly reached:**
  - `Adjacency.cls::{MarkGraphGone, OtherEdgeKeys, RemoveLabel, Reweight, RowRemove, RowUpdate}`
  - `Eraser.cls::{EraseEdges, EraseIdSet}`
  - `TraversalBuild.cls::Build2HopExactStats`
  - `TraversalKHop.cls::{KHop2Count, KHop2CountExact, KHop2CountFast}`
  - `VarLength.cls::{Ends, EndsByDistance, EndsInto}`
  - `iris_sql_store.py::IRISGraphStore.{_bfs_rows, _only_default_graph, _run_objectscript_bfs, _sql_bfs_fallback, execute_bfs, execute_knn_vec}`
- **13 existing locators gaining a binding:**
  - `Adj.cls::Count`
  - `Adjacency.cls::{HeldElsewhere, PutKeyed, Remove, RemoveKeyed, SetLeafFromLowest}`
  - `TraversalBuild.cls::{Build2HopStats, BuildKG}`
  - `TraversalPaths.cls::{ShortestLength, ShortestPathJson}`
  - `iris_sql_store.py::IRISGraphStore.{_select_bfs_strategy, execute_shortest_path, shortest_path_length}`
- **Strengthened (8):**
  - `Adjacency.cls::RowPut`
  - `TraversalBFS.cls::{BFSFast, TraverseWithPredicateFast}`
  - `TraversalKHop.cls::Fresh`
  - `algorithms.py::AlgorithmsMixin._khop_fallback`
  - `nodes_edges.py::NodesEdgesMixin.{delete_edge, set_edge_weight}`
  - `translator.py::translate_delete_clause`

`Eraser.cls` rows bind only the graph scoping and incident-edge decisions that ordinary node and edge deletes reach.
They make no claim about the excluded erasure, redaction or tenant-removal workflows.

In the target files the active count rose:
- `iris_sql_store.py`: 16 → 25 of 149
- `Adjacency.cls`: 3 → 14 of 34
- `TraversalBuild.cls`: 5 → 8 of 38
- `TraversalKHop.cls`: 1 → 4 of 7
- `VarLength.cls`: 0 → 3 of 15
- `TraversalBFS.cls`: 8 of 23, unchanged in count, two members strengthened

`Traversal.cls` stays at 2 of 34. Its members are one-line facades into `TraversalBuild`, `TraversalBFS` and
`TraversalKHop`, so binding them would add `delegates` rows only. The claim "internals of modeled decisions" was tested
on the traversal classes and held only in part:
- **Held:** the strategies agree on every edge set, and rebuild equals incremental.
- **Did not hold:** the rebuild's reader exposure (bug-str-115), the two-hop fast count (bug-str-117), and the
  direction handling (bug-str-113, -114) are decisions these classes make themselves.

Corrections before the final recount: the integration first wrote 11 crosswalk symbols unqualified (for example
`_khop_fallback` instead of `AlgorithmsMixin._khop_fallback`). `check_consolidated` failed on them; they were
qualified. The recount is the one after that fix.

**Material predictions gained:**
- what `execute_bfs` answers on each strategy;
- that the fallback answers whenever the ObjectScript walk finds no edge;
- that another graph's edges and parallel edges change no traversal answer;
- what each delete path leaves in `^KG`, labels, degree and `^NKG`;
- that a rebuild changes no entry, but readers see a purged index while it runs;
- what the two-hop fast count answers when fresh and when stale;
- the `in` length of the store method;
- what an unknown direction text does.

**Withdrawn:** none.

<a id="binding-integrity-audit"></a>
## Binding-integrity audit

The question for every row added in this iteration with relation models, proves or witnesses: would swapping or
weakening this member's own decision break a theorem or the binding? Per-row detail with control and mutation names is
in [strategy/AUDIT.md](strategy/AUDIT.md) (29 rows) and [adjacency/AUDIT.md](adjacency/AUDIT.md) (35 rows); the
builder's rows are below. 69 rows were audited (29 + 35 + the builder's 5) and none was relabeled. Two of the builder's own rows were labeled
`cites` or `delegates` from the start because they failed the question.

| Member (rows) | Relation | Swap or weaken its own decision → | Verdict |
|---|---|---|---|
| `iris_sql_store.py::IRISGraphStore._select_bfs_strategy`, `_only_default_graph` | models, proves | `arno-named-graph`, `arno-any-direction`, `arno-ignores-other-graphs`; binding `select_injected` | active; **qualified**: Arno selection observed only by injecting its preconditions (the library is absent) |
| `IRISGraphStore.execute_bfs` (cap), `_bfs_rows` (one row per node, source excluded, type direction text) | models, proves | `cap-passed-to-adapter`, `cap-zero-cuts-all`, `bfs-every-depth`, `bfs-lists-source`, `types-ignore-case`; binding 22-47 cases each | active |
| `IRISGraphStore._run_objectscript_bfs` (fallback on an empty walk), `_sql_bfs_fallback` (frontier, direction text) | models, proves | `no-fallback-on-empty`, `sql-revisits`, `graph-unscoped`, `sql-unknown-dir-as-out` | active |
| `TraversalBFS.cls::BFSFast` (frontier; exact direction compare), `TraverseWithPredicateFast` (graph scope) | models, proves | `bfsfast-case-insensitive`, `graph-unscoped`; the frontier through `lemma_front_eq_new` | active; the frontier is **theorem-only** (it makes no difference to the answer after the least-depth fold) |
| `VarLength.cls::EndsInto`, `Ends` | models, proves, witnesses | `trail-repeats-edges`, `bfs-lists-source` | active |
| `VarLength.cls::EndsByDistance` | models | no formal control; the binding's independent trail port detects dropping the parallel-edge count or the source-cycle check | active, **binding-detected only** |
| `IRISGraphStore.execute_shortest_path`, `shortest_path_length`; `TraversalPaths.cls::ShortestLength`, `ShortestPathJson` | models, proves, witnesses | `esp-no-reversal`, `length-in-reversed`, `length-both-as-out`, `graph-unscoped` | active |
| `algorithms.py::AlgorithmsMixin._khop_fallback` | models, proves | `khop-walks-both`; binding `khop_s_*` | active |
| `IRISGraphStore.execute_knn_vec` | models | `knn-unrouted-legacy` (falling back to the legacy table when there is no route) | active, **qualified**: only the no-route branch is the member's modeled decision; the route lookup and the ranking are inputs (`routed`, `nearest`) |
| `Adjacency.cls::{PutKeyed, SetLeafFromLowest, OtherEdgeKeys, RemoveKeyed, RowPut, RowRemove, Remove, HeldElsewhere, RowUpdate, Reweight, RemoveLabel}`, `Adj.cls::Count` | models, proves | named controls per row (`put-keyed-drops-others`, `remove-keyed-takes-triple`, `held-elsewhere-ignored`, `update-ignored`, `label-erase-by-label`, …) and binding mutations | active |
| `Adjacency.cls::MarkGraphGone` | proves | `mark-gone-default-graph` | active, **theorem-only** (the namespace-wide stale flag is not read by the binding) |
| `Eraser.cls::{EraseEdges, EraseIdSet}`, `nodes_edges.py::NodesEdgesMixin.delete_edge` | models, proves | `erase-ignores-graph`, `label-erase-by-label`; binding `erase_ignores_graph` (5 cases) | active (graph scoping and incident edges only) |
| `nodes_edges.py::NodesEdgesMixin.set_edge_weight`, `translator.py::translate_delete_clause` | models | definitional (an Update op and a one-row DelRow); the binding detects a whole-triple delete (`cypher_delete_r_rows = 1`) and a reweight that leaves the row (reverts at sync) | active, **binding-detected only**; the weakest of the 34 and the first candidates for demotion if a later review requires a theorem per member |
| `TraversalBuild.cls::BuildKG` (W2: rebuild = incremental; builder: the purge visible to readers) | models, proves | W2: `canon-leaf-not-lowest`, `create-ignores-mode`, the `lemma_*` controls; builder: `rebuild-swaps`, `refill-keeps-old`, binding mutation `swap` (observed seed-alone reads) | active |
| `TraversalKHop.cls::{KHop2CountFast, Fresh, KHop2Count}`, `TraversalBuild.cls::{Build2HopStats, Build2HopExactStats}` | models, proves, witnesses | `fresh-ignores-stamp`, `stamp-not-equality`, `walk-counts-source-and-first-hop`; binding `exact_is_sum`, `fresh_ignores_stamp` | active |
| `TraversalKHop.cls::KHop2CountExact` | models | the binding's `exact_is_sum` | active, **binding-detected only** |
| `Adjacency.cls::BeginRebuild` (builder) | cites | it does not decide what a reader sees: readers never take the lock, so swapping its lock mode changes no theorem or observation | **not counted** |
| `_engine/schema.py::SchemaMixin._sync_kg`, `.sync` | delegates | they forward to `BuildKG` | not counted |
| `ReachTypes`, `_reach_types_sql`, `_run_arno_bfs`, `execute_vl_ends`, `QueryMixin._vl_ends`, `QueryMixin._execute_shortest_path_cypher` (length-only guard), `AlgorithmsMixin.khop`, `_khop_seed_exists`, store `_khop_fallback` (stub); `EraseEdgeRow`, store `delete_edges`/`delete_nodes`/`delete_nodes_by_prefix`, `RemoveNode`, `QueryMixin.khop2_count_fast`; `write_edges`, `write_nodes`, `FillTriple`, `BuildKGKeyed` | delegates / cites | no own decision modeled | not counted |

## Owners changed

Extended with additive bullets and metadata:
- `query.paths.varlength`: the BFS route's rows, strategy choice and the ends-only walk; the bug-str-114 "Today" bullet
  with a working assumption linked to `HD-1003`; now `uncertain`.
- `algorithms.op.paths`: length vs path; the bug-str-113 "Today" bullet.
- `algorithms.op.khop`: no graph argument; the F-1009 and bug-str-115 "Today" bullets.
- `structure.adjacency`: graph-scoped readers; the merged `^NKG` edge.
- `structure.multigraph.layout` and `.count`.
- `structure.drift`.
- `structure.edge.delete`.
- `structure.node.delete`.
- `structure.rebuild`: the ObjectScript `^NKG` builder; the bug-str-115 "Today" bullet with a working assumption linked
  to `structure.rebuild.failure`.
- `structure.rebuilt.stamp`: the bug-str-117 "Today" bullet.
- `search.knn`: the no-route answer.

No new block. `check_ontology.py`: 403 blocks, 0 issues, 17 writing warnings (unchanged).

## Correspondence

The [delta from 56](correspondence-delta-from-56.json) is STALE_ALL for proof and correspondence. The changed formal
inputs are the three new models. The changed product-side inputs are their `binding.py` files, `decision-links.tsv` and
`families.tsv`; no product file changed. The fresh [stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

<a id="checks-final-candidate"></a>
## Checks (final candidate)

| Check | Result |
|---|---|
| `check_ontology.py` | 403 blocks, 0 issues, 17 warnings |
| `check_findings.py` (`verification_root=.g5/Verus_verification`, `--previous b63a5ec1`) | No problems found (after fixing four items: a `Run:` line placement and three missing back-links) |
| `check_evidence.py` | FRESH |
| `check_consolidated.py` (G5_GUIDE set) | PASS (1,116 decision links resolve uniquely; correspondence stamp REUSABLE_INPUTS) |
| `git diff --check` | clean |
| Product diff vs pin | none outside `.g5/`; no untracked file outside `.g5/` |

## Limitations

- **Review:** this iteration is not independently reviewed.
- **Arno:** the library is absent. The Arno strategy was observed only through injected preconditions; its walk, and
  the `^NKG` readers that depend on it, stay conditional.
- **Concurrency:** bug-str-115 is observed with a declared (functional) index only. The non-indexed rebuild path
  (`RemoveAll` plus `FillEdge` in 50,000-row transactions) has the same exposure by inspection, not observation.
  Degree, PPR and native Cypher reads during a rebuild were not exercised. Writers during a rebuild (the `WriterLock`
  timeout path) were not exercised either.
- **Not modeled:** the undeclared-index path; the degree cache; temporal edges; the BulkLoader; per-hop type
  sequences; the lookahead; `dstLabel`; `find_all`; path contents; the multigraph `set_edge_weight` branch (proof only).
- **Binding-only rows:** `ReachTypes`, `EndsByDistance`, `ShortestLength`'s two-ended search and `KHop2CountExact` are
  checked by the bindings only. Collation is assumed to equal Python order for the bindings' lower-case IDs.
- **Fixture residue:** data remains in USER under `i57a_`, `i57b_`, `i57c_` and `i57r_`. Graph `i57bg…m` stays in
  multigraph mode. The bindings ran `sync()` on all of USER several times.

<a id="residual-list-first-missing-step-for-each"></a>
## Residual list (first missing step for each)

1. bug-str-115 beyond k-hop and path length: a race binding case for degree (`Adj.Count`), PPR and a native Cypher hop
   during `sync()`, plus the non-indexed rebuild path (needs a namespace without the declared index).
2. Writers during a rebuild: a `create_edge` racing `BuildKG`, checking whether `WriterLock`'s 5-second timeout path
   turns off degree caching and whether the edge survives the refill.
3. Arno strategies: the first missing step is a container with the library.
4. `Traversal.cls` facades (32 members): classify as `delegates` in one batch, or record them as excluded.
5. The rest of `iris_sql_store.py` (124 of 149 unbound): `execute_ppr`, `execute_wcc`, `execute_cdlp` (check against
   the `algo_options` and `communities` models), `execute_vl_ends` as its own reader (now `delegates`), `get_nodes`,
   `query_nodes`, `write_nodes`, `write_edges` (cites), `execute_sql` and `_stmt_is_dml`, `_check_namespace`. The first
   step is a frozen prediction for `execute_sql`'s DML detection.
6. `TraversalBuild.cls` sweeps (`RewriteNKG`, `Sweep*`, `RetireNode`, `PutNodeBack`, `SketchOf`, `Backfill*`): R3 held
   by names, but sketches and the dictionary sweep are unmodeled. The first step is a binding case on `^NKG` sketches
   after deletes.
7. Inherited queue otherwise unchanged (see the [continuation residual queue](../HANDOFF.md#continuation-2026-11-17)).

## Cost

Builder session wall clock from about 07:28 to the seal at about 08:05 UTC, roughly 37 minutes. Two parallel workers:
W1 took 19 minutes and 239k sub-agent tokens; W2 took 23 minutes and 262k sub-agent tokens. Currency is not available
in-session.
