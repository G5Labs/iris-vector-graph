# PROOFS-D1E: Verus L1/L2 refinement for modules 01 (install/schema), 02 (graph identity) and 10 (algorithms) (proof debt D-1, playbook §3.3)

Crate `experiment/playbook-completion/proofs-d1e` (`ivg-d1e-proofs`), Verus 0.2026.10.04.426d8b0, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved** (`--no-cheating`, no trusted item in this
crate), about **models**. Every theorem here is a statement about an L1 contract or a reviewed L2 machine. None says
that the Python or ObjectScript at pin `3eaa79cf` has the property. The product's obligations stay as the as-built
evidence leaves them (failed or open: `findings/audit/01.json`, `02.json`, `10.json`).

**Numeric algorithms.** For module 10 the models check result-contract properties, not numerics: cache validity (a
served answer equals a fresh computation), completeness (PageRank lists every node), graph scope (a walk stays in one
graph; labels are default-graph nodes), the direction contract of shortest paths, and a read's footprint. Scores,
iteration counts, tie-breaking, convergence and the search algorithms themselves are not modelled (section 4).

Five families, one per invariant group:

| Gate item (§3.3) | 01 record/readiness/upgrade/legacy | 02 graph names and graph-scoped reads | 02 multigraph mode | 10 cached answers, completeness, footprint | 10 path direction, walk scope, label propagation |
|---|---|---|---|---|---|
| L1 contract with the business invariants (`Contract` + `SafeContract`) | `src/inst_l1.rs` | `src/gid_l1.rs` | `src/gmode_l1.rs` | `src/acache_l1.rs` | `src/atrav_l1.rs` |
| L2 machine over the stored layout, reviewed design | `src/inst_l2.rs` (^IVG.Deploy("schema"), tables per schema, the IVG functions with the ^oddDEF marker class, Graph.KG classes, ^KG bootstrap, legacy views/classes, the setup run and its reply) | `src/gid_l2.rs` (Graph_KG.nodes, rdf_labels, rdf_props by graph_id) | `src/gmode_l2.rs` (rdf_edges rows of a triple by ekey, ^IVG.GraphMode, each engine's mode cache, Cypher statements in flight, the mode lock) | `src/acache_l2.rs` (nodes, ^KG("out", 0), ^KG("__version"), node token, ^IVG.AlgoCache, calls in flight, SQL function classes, ^IVG.Deploy("routines")) | `src/atrav_l2.rs` (^KG("out"/"in", g), default-graph nodes, CDLPJson's local labels) |
| `Refines<L1>` for **every** L2 step | 15 labels (`lemma_step`) | 5 labels | 8 labels | 10 labels | 9 labels |
| L2 invariant inductive (`SafeContract`) | `inv01` (L1's `inv1` through the abstraction + 2) | `inv02` (= `inv1` of the abstraction, `lemma_inv02_is_inv1`) | `invm` (`inv1` + 4) | `inv10c` (FK + cache entries + calls) | `inv10t` (FK + mirror + CDLP labels) |
| Every raw L2 execution refines L1 and keeps both invariants | `inst_l2::theorem_raw_executions_refine` | `gid_l2::...` | `gmode_l2::...` | `acache_l2::...` | `atrav_l2::...` |
| Broken-implementation controls rejected in the expected file | 4 of 4, `src/inst_l2.rs` | 3 of 3, `src/gid_l2.rs` | 3 of 3, `src/gmode_l2.rs` | 3 of 3, `src/acache_l2.rs` | 2 of 2, `src/atrav_l2.rs` |
| Each control's counterexample proved reachable | 4 (`cx_f0103`, `cx_f0102`, `cx_f0109`, `cx_f0101`) | 3 (`cx_f0202`, `cx_f0206`, `cx_f0106`) | 3 (`cx_f0201`, `cx_f0208`, `cx_f0207`) | 3 (`cx_f1004`, `cx_f1003`, `cx_fc1001`) | 2 (`cx_hd1003`, `cx_f1008`) |
| Non-vacuity (the reviewed L2 does real work) | `witness_inst.rs` | `witness_gid.rs` | `witness_gmode.rs` | `witness_acache.rs` | `witness_atrav.rs` |
| Trust inventory | empty (this crate and `actors`) | same | same | same | same |

Baseline: `cargo verus verify -- --no-cheating`: **115 verified, 0 errors** (module 01: 26; module 02: 21 + 20;
module 10: 21 + 27); Verus 2.17 s, SMT 1.71 s, 4.16 M rlimit, wall 2.59 s, 0.48 GB peak (registry
`proofs-d1e-baseline`, log `$RUN_DIR/proofs-d1e/baseline.log`, which ends with the counts read from its JSON). Gate:
**pass** (`RESULTS.json`, sources SHA-256 `cb604bc3555ef40d...`). An unregistered run over the same sources
(`$RUN_DIR/proofs-d1e/scratch-1`) gave the same result. Rerun:
`source experiment/playbook-completion/environment.sh; python3 experiment/playbook-completion/proofs-d1e/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600` after `cargo clean -p`; `PROOFS_OUT_DIR=<dir>` writes logs and
RESULTS.json there; `--register` registers the decisive runs).

Executable twins: breadth lane A's `ins_setup` (F-0103, F-0102; HD-0101/HD-0102), `ins_legacy` (F-0101) and
`gid_mode` (F-0201, F-0207, F-0208) in `models/breadth-a/src`; breadth lane B's `m10` machines `cache` (F-1004),
`routes` (F-1003) and `walk` (F-1008) in `models/breadth-b/src/m10.rs`. The families add defects with no explorer
model: F-0109, F-0202, F-0206, F-0106, F-C1001 and HD-1003, and a label-propagation contract (no defect).

## 1. Module 01: the deploy record, readiness, the upgrade, legacy removal

### L1 contract (`inst_l1.rs`)

State: `unreadable` (the engine's login cannot read the record; environment, any value at init, no step changes it),
`bound` (the namespace's IVG Schema), `classes` (readiness: the ObjectScript layer is deployed), `held`/`shaped`
(schemas holding IVG tables, those in the 4.0.0 shape), `views`/`lcls` (legacy views and shipped classes), `run` (a
setup in progress: schema, whether a step failed). Labels: `Begin{schema}`, `Refuse{schema}`, `Ddl{ok}`, `StepFailed`,
`Deploy{ok}`, `Bind`, `Reply{warned, ready}`, `Stop`, `Access{schema, adm}`, `Feature{rdy}`, `Upgrade`,
`Remove{obj, reported}`. Business rules and theorems:

- **an engine is admitted only by the binding** (spec 262 FR-006/FR-006a, spec.md:243-245; INS-I3.4): `adm` is
  Accepted exactly when the namespace is bound to the engine's schema and the record is readable; an unreadable
  record is the separate warned `Unchecked` outcome (HD-0101 working assumption); `theorem_admitted_only_by_binding`;
- **setup of schema T never runs on a namespace bound to another schema, and a binding never changes** (FR-006,
  ADR-0016:10-12): `inv1`, `theorem_binding_never_changes`;
- **a quiet reply means every step succeeded** (ADMIN_GUIDE.md:428, INS-B1.12): `theorem_quiet_reply_means_success`;
- **the binding is not readiness** (HD-0102 working assumption): `Reply` reports readiness, `Feature` answers or
  names the missing layer: `theorem_readiness_is_named`;
- **the upgrade follows the binding** (ADR-0016, FR-009): `theorem_upgrade_follows_binding`;
- **legacy removal says removed only when gone** (data-model.md:50-60, INS-I7.6): `theorem_removed_means_gone`.

### L2 machine (`inst_l2.rs`) and refinement

| L2 step (source at the pin) | L1 step | Proof |
|---|---|---|
| `Begin` (_record_and_initialize reads the record, _engine/schema.py:2198-2226) | `Begin` | `lemma_step` |
| `Refuse` (IVGSchemaError.mismatch, :2224-2226) | `Refuse` | `lemma_step` |
| `Ddl{ok}` (base DDL, :2440-2512; failure logged at :2508-2511) | `Ddl{ok}` | `lemma_ddl` |
| `Funcs` (the IVG Schema's SQL functions, the marker class `<package>.funcCYCMP`, schema_name.py:203-209) | stutter | `lemma_step` |
| `Deploy{on, ok}` (deploy_objectscript_classes, :2578-2594; R299 failure in warnings) | `Deploy{ok: on && ok}` | `lemma_step` |
| `Kg{ok}` (^KG bootstrap, :2674-2681) | stutter / `StepFailed` | `lemma_kg` |
| `Record` (write_record, :2309-2312; schema_name.py:194-198) | `Bind` | `lemma_step` |
| `Reply{warned, ready}` | `Reply` | `lemma_step` |
| `Stop` (the process stops between steps) | `Stop` | `lemma_step` |
| `Access{schema, adm}` (engine.py:1847-1868 -> check_first_access, schema_name.py:220-235) | `Access` | `lemma_access` |
| `Feature{rdy}` (a call needing the classes) | `Feature` | `lemma_step` |
| `Upgrade{arg}` (upgrade_to_4_0_0, migrations/upgrade.py:130-200) | `Upgrade` | `lemma_upgrade` |
| `RmView` / `RmFirst` / `RmLater` (remove_legacy_objects, _engine/legacy.py:654-686) | `Remove` | `lemma_rmview`, `lemma_rmfirst`, `lemma_rmlater` |

`inv01`: L1's `inv1` of the abstraction; a failed step of the run is in the reply's warnings; each recorded class
delete's result says whether the class is gone. L2 theorem: `theorem_no_record_no_admission`.

## 2. Module 02: graph names, keys and graph-scoped reads (`gid_l1.rs`, `gid_l2.rs`)

Graph names are ints: 0 the default graph (''), -1 the name "0", below -1 a name with a control character.
`valid(g)` is GraphKey.Validate (GraphKey.cls:23-49); `ikey(g)` is ForIndex's subscript after IRIS canonicalizes "0"
to 0 (GraphKey.cls:25-27, 50-56; ADR-0003:119-121). L1 state: node, label and property rows by graph. Labels:
`CreateNode{g, n, l, k, ok}`, `EraseGraph{g}`, `NodesByLabel{l, ans}` (the default-graph label reader),
`IdsByLabel{l, ids}` (the documented all-graph id helper), `PropertyKeys{l, keys}` (documented "Not graph-scoped").
Rules: every graph holding content has a valid name (`inv1`; `theorem_index_keys_distinct`: distinct content graphs
have distinct index keys and key 0 is the default graph's alone; `theorem_every_graph_erasable`); a read with no graph
argument reads the default graph and hydrates each id from it (USER_GUIDE.md:462-467, HD-0201 working assumption:
`theorem_default_read_is_scoped`); an all-graphs read is the union of each graph's own answer (CONTEXT.md:38-43:
`theorem_all_graph_read_is_union`).

L2: the three tables as stored; the abstraction is the identity on rows, so the refinement's content is the writers'
and readers' statement semantics: `CreateNode` (create_node, _engine/nodes_edges.py:968-1105; reviewed: the name
check count_nodes, erase_graph, delete_nodes_by_prefix and bulk_create_nodes run, :747, 1514, 1559, 1698),
`EraseGraph`, `NodesByLabel` (get_node_ids_by_label :760-777 then get_nodes :621-695 with its empty-node rule),
`IdsByLabel`, `PropertyKeys` (_engine/schema.py:500-515). Each maps to the L1 step of the same name
(`lemma_createnode`, `lemma_bylabel`, `lemma_propkeys`, `lemma_step`). `inv02` is stated on the tables and equals
`inv1` of the abstraction (`lemma_inv02_is_inv1`). L2 theorem: `theorem_no_row_under_reserved_name`.

## 3. Module 02: multigraph mode of one triple (`gmode_l1.rs`, `gmode_l2.rs`)

L1: the triple's edges `keys` and the mode `multi`; labels `SetOn`, `SetOff{ok}` (refused over parallel edges),
`Single{k, added}` (a single-edge writer adds only to a triple with no edge), `Parallel{k}` (only in multigraph mode),
`Delete{k}`. `inv1`: mode off, at most one edge (spec 234 FR-002, GID-I4.10); `theorem_mode_off_single_edge`,
`theorem_single_writer_never_parallel`.

| L2 step (source at the pin) | L1 step | Proof |
|---|---|---|
| `SetOn{e}` (GraphMode.Set(g, 1), GraphMode.cls:26-33; engine e forgets its cache, admin.py:928-936) | `SetOn` | `lemma_step` |
| `SetOffCount{e, ok}` (ParallelCount, GraphMode.cls:35-40, 48-61) | stutter (`ok`) / `SetOff{false}` | `lemma_setoffcount` |
| `SetOffKill{e}` (Kill ^IVG.GraphMode, :41) | `SetOff{true}` | `lemma_step` |
| `CyMode{e}` (the statement's mode read, translator.py:441-457; is_multigraph, admin.py:917-926) | stutter | `lemma_cymode` |
| `CyInsertPar{e, k}` (keyed insert at a fresh ekey, translator.py:10368-10388) | `Parallel{k}` | `lemma_cyinsertpar` |
| `CyInsertOne{e, added}` (the mode-off insert at ekey 0) | `Single{0, added}` | `lemma_cyinsertone` |
| `Single{e, added}` (create_edge's guarded insert, nodes_edges.py:1214-1217, 1257-1273; store_edge :2560-2581) | `Single{0, added}` | `lemma_single` |
| `Delete{k}` (Cypher per-edge DELETE) | `Delete{k}` | `lemma_step` |

`invm`: `inv1` of the abstraction; a counted Set(g, 0) holds the lock over at most one row in multigraph mode; the
lock is exclusive; a statement in flight holds it shared, and one that read "multi" sees the current mode.
`theorem_mode_off_rows`.

## 4. Module 10: cached answers, PageRank's completeness and a read's footprint (`acache_l1.rs`, `acache_l2.rs`)

Result-contract abstraction: an answer is `Ans{rows, over}`, the rows it lists and the edges its scores are computed
over (the scores are a deterministic function of the graph and the parameters and are not modelled). Personalized
PageRank lists every node when its seed is a node (an edgeless seed scores 1.0, b-10-live-cache) and none otherwise;
global PageRank lists every node of the default graph (algorithms.py:741-760; HD-1004). L1 state: default-graph nodes
and edges, SQL function classes `dict`, routine record `rrec`. Labels: node and edge writes, `Read{q, ans}` (answer ==
the fresh computation), `Triangles` (changes nothing), `Install{names}` (setup). Theorems: `theorem_answer_is_fresh`
(ALG-I4, ALG-B16.11), `theorem_edgeless_seed_is_answered` (ALG-B2.19), `theorem_pagerank_lists_every_node` (HD-1004),
`theorem_reads_change_no_content` (ALG-I6).

| L2 step (source at the pin) | L1 step | Proof |
|---|---|---|
| `CreateNode` (create_node with no edge: no token moves, b-10-live-cache) | `CreateNode` | `lemma_createnode` |
| `DeleteNode` (EraseNodeIds -> InvalidateDerived: token raised, ^IVG.AlgoCache killed, Eraser.cls:1038-1053) | `DeleteNode` | `lemma_step` |
| `AddEdge` / `DelEdge` ($Increment ^KG("__version"), Adjacency.cls:92, 135, 157, 260, 299) | same | `lemma_step` |
| `LookupHit{c, q, ans}` (AlgoCache.Lookup, AlgoCache.cls:27-36) | `Read{q, ans}` | `lemma_step` |
| `LookupMiss{c, q}` | stutter | `lemma_step` |
| `Compute{c, q, ans}` (the computation on a miss; PageRankGlobalJson for PageRank, PageRank.cls:406-520) | `Read{q, ans}` | `lemma_compute` |
| `Put{c}` (AlgoCache.Put under the token read by Lookup, :45-50; iris_sql_store.py:921-983) | stutter | `lemma_step` |
| `TriCount` (execute_triangle_count, iris_sql_store.py:3977-4006) | `Triangles` | `lemma_tricount` |
| `Install{names}` (setup's _install_procedures) | `Install` | `lemma_step` |

`inv10c`: edges join nodes; a stored entry, or a computed call, whose tokens are the current ones holds the fresh
answer, and no token held is newer than the current one. L2 theorem: `theorem_hit_is_fresh`.

## 5. Module 10: shortest-path direction, walk graph scope, label propagation (`atrav_l1.rs`, `atrav_l2.rs`)

Result-contract abstraction: a shortest-path answer is `Len{n}`, `NoPath` or `Refused`; an expansion answers its end
nodes; label propagation a label per node. L1 state: default-graph nodes, every graph's edges. Rules: the answer is the
least walk length in the direction asked, "in" from a to b being "out" from b to a (iris_sql_store.py:2197-2199), and
a direction outside {out, in, both} is refused (HD-1003, supported; TraversalPaths.cls:348-355):
`theorem_direction_contract`; a walk's edges belong to one graph (CONTEXT.md:38-43, ALG-I2):
`theorem_walk_in_one_graph`; label propagation labels every default-graph node with a default-graph node (kg_CDLP,
algorithms.py:829-840; HD-1002: no convergence claim): `theorem_labels_are_nodes`. Walk lemmas: `lemma_walk1`,
`lemma_walk2`, `lemma_walk_ext`, `lemma_shortest_ext` (walks over pointwise-equal step relations are equal).

| L2 step (source at the pin) | L1 step | Proof |
|---|---|---|
| `AddNode`, `AddEdge`, `DelEdge` (the row and both index entries) | same | `lemma_step` |
| `SpLength` (shortest_path_length -> ShortestLength, iris_sql_store.py:2162-2181; TraversalPaths.cls:117-...) | `Path` | `lemma_splength` |
| `SpPaths` (execute_shortest_path -> ShortestPathJson, iris_sql_store.py:2183-2215; TraversalPaths.cls:5-80) | `Path` | `lemma_sppaths` |
| `VarLen` (VarLength.Ends, VarLength.cls:44-51, 126-148) | `VarLen` | `lemma_varlen` |
| `CdlpInit`, `CdlpRound` (CDLPJson, Algorithms.cls:93-186) | stutter | `lemma_step`, `lemma_cdlpround` |
| `CdlpEnd` (kg_CDLP with complete_labels, _edgeless.py:109-114) | `Cdlp` | `lemma_cdlpend` |

The L2 answer of `SpLength`/`SpPaths`/`VarLen` is any answer the routine's contract allows over what it reads (the
search is not verified). `inv10t`: default-graph edges join nodes; the in entries mirror the out entries; each CDLP
call's labels cover exactly the default-graph nodes with an entry and are default-graph nodes. With the mirror, reading
out and in entries is walking the default graph both ways (`lemma_both`). L2 theorem: `theorem_cdlp_answer_in_default_graph`.

## 6. Reviewed design and its status at the pin

| Id | Element | Source | At the pin |
|---|---|---|---|
| R01-1 | no record: the first access refuses whatever the marker says (setup exempt) | F-0103 remedy; FR-006a | no: the marker admits (schema_name.py:233-235) |
| R01-2 | every passed-over setup failure is in the reply's warnings | F-0102 remedy | no: log lines (_engine/schema.py:2508-2511, 2680-2681); the deploy failure is reported (R299, :2591-2593) |
| R01-3 | the upgrade reads the record and refuses another schema | F-0109 remedy | no: `schema=` default Graph_KG, record never read (upgrade.py:58, 140) |
| R01-4 | `removed` from the drop's or the class delete's result | F-0101 remedy | no (legacy.py:670-684) |
| R01-5 | the record is a binding; readiness is reported separately; a feature call on a class-less namespace is a named failure | HD-0102 working assumption (status **assumption**) | binding and reported readiness as built; the named failure is unverified (HD-0102's probe proposed, not run) |
| R01-6 | an unreadable record is the warned `Unchecked` outcome | HD-0101 working assumption (**assumption**) | as built (engine.py:1863-1867; intent-a-hd0101-unreadable-record), on any exception |
| R02-1 | every writer that takes a graph name runs the name check | F-0202 remedy; ADR-0003 | no: create_node, store_node (nodes_edges.py:968-1105) |
| R02-2 | a default-graph reader takes its ids from the default graph | F-0206 remedy; HD-0201 (**assumption**) | no (nodes_edges.py:779-794, documented "hydrated from the default graph") |
| R02-3 | get_property_keys joins on (graph_id, s) | F-0106 remedy | no (_engine/schema.py:507-510) |
| R02-4 | the single-edge writers and the mode-off insert refuse when the triple has any row | F-0201 remedy | no: ekey 0 guard (nodes_edges.py:1257-1273) |
| R02-5 | the mode is read per statement | F-0208 remedy | no: per-engine cache (admin.py:917-926) |
| R02-6 | Set(g, 0) holds a mode lock from count to kill; Cypher writers hold it shared from mode read to insert | F-0207 remedy | no lock (GraphMode.cls:26-45) |
| R10-1 | every node write raises a monotonic node token read inside Lookup and stored in the entry | F-1004 remedy | no: PPR key holds seeds and settings only (iris_sql_store.py:2248-2258); global PageRank keys COUNT:MAX (R313) instead |
| R10-2 | the PageRank owner lists every node | HD-1004 working answer (supported) | no: 10,000 rows (PageRank.cls:517, 519) |
| R10-3 | a read probes Arno availability without DDL and writes no record | F-C1001 remedy | no (arno_bridge.py:106-134, 360-417) |
| R10-4 | ShortestLength and ShortestPathJson refuse a direction outside their set; shortest_path_length reverses "in" | HD-1003 working answer (supported, 99b00ce9) | no (TraversalPaths.cls:45, 70, 122; iris_sql_store.py:2162-2181) |
| R10-5 | the every-graph expansion walks each graph separately | F-1008 remedy | no (VarLength.cls:126-148) |
| as built | CDLP's default-graph scope and complete_labels; AlgoCache's token-before-compute Put; EraseNodeIds' InvalidateDerived; the mismatch refusal; R299 deploy failure in warnings | the cited classes | yes |

## 7. Broken-implementation controls

Each feature puts back one as-built decision. Every error is in the expected file, every failing function is in that
file's module, every function of every other module verifies (`RESULTS.json`, `failing_outside_expected_module` empty),
and each control's counterexample (compiled only with it) is a proved run of the L2 step relation, as the control
changes it, from its initial state to a step that is not an L1 step.

| Control (finding) | Rejected at (function: obligation) | Proved counterexample | Registry |
|---|---|---|---|
| `control_f0103_marker_admits` (F-0103) | `inst_l2.rs:217` `lemma_access`: admission by the record alone | 5 steps: setup of schema 1 makes its tables and functions (marker) and stops; an engine of schema 1 is admitted with no record (not an L1 step) | `proofs-d1e-f0103-marker-admits` |
| `control_f0102_failure_only_logged` (F-0102) | `inst_l2.rs:199` `lemma_ddl`, `:208` `lemma_kg`: a failed step is in the warnings | 8 steps: a DDL statement fails, every later step succeeds, the reply has no warning (not an L1 step) | `proofs-d1e-f0102-failure-only-logged` |
| `control_f0109_upgrade_default_schema` (F-0109) | `inst_l2.rs:225` `lemma_upgrade`: the bound schema or nothing | 9 steps: Graph_KG holds 3.2.0 tables; setup binds schema 1; the default upgrade migrates Graph_KG (not an L1 step) | `proofs-d1e-f0109-upgrade-default-schema` |
| `control_f0101_removed_unchecked` (F-0101) | `inst_l2.rs:234` `lemma_rmview`, `:253` `lemma_rmlater`: reported implies gone | a failed DROP VIEW reported removed; a failed class delete reported removed for its second item (each not an L1 step) | `proofs-d1e-f0101-removed-unchecked` |
| `control_f0202_writer_skips_name_check` (F-0202) | `gid_l2.rs:147` `lemma_createnode`: writes only under a valid name | 1 step: create_node under "0" (not an L1 step); the row's graph keys as 0 and no erase accepts it | `proofs-d1e-f0202-writer-skips-name-check` |
| `control_f0206_hydrate_from_default` (F-0206) | `gid_l2.rs:164` `lemma_bylabel`: default-graph nodes with the label | 3 steps: id 1 labelled 10 in graph 1 and 11 in the default graph; get_nodes_by_label(10) answers id 1 with labels {11} (not an L1 step) | `proofs-d1e-f0206-hydrate-from-default` |
| `control_f0106_keys_join_on_id` (F-0106) | `gid_l2.rs:175` `lemma_propkeys`: keys of the label's own graph | 3 steps: get_property_keys(10) lists graph 1's key 21 (not an L1 step) | `proofs-d1e-f0106-keys-join-on-id` |
| `control_f0201_ekey0_guard` (F-0201) | `gmode_l2.rs:162` `lemma_single`, `:170` `lemma_cyinsertone`: adds only to a triple with no edge | 10 steps: two parallel edges, ekey 0 deleted, mode off, create_edge inserts ekey 0 next to ekey 1 (not an L1 step; two edges in a mode-off graph) | `proofs-d1e-f0201-ekey0-guard` |
| `control_f0208_mode_cached_forever` (F-0208) | `gmode_l2.rs:152` `lemma_cymode`: a statement reads the current mode | 8 steps: engine 1 caches "multi", engine 0 turns the mode off, engine 1 inserts a parallel edge (not an L1 step) | `proofs-d1e-f0208-mode-cached-forever` |
| `control_f0207_set_off_unlocked` (F-0207) | `gmode_l2.rs:141` `lemma_setoffcount`, `:150` `lemma_cymode`: the mode lock | 8 steps: Set(g, 0) counts one edge, a Cypher CREATE adds a parallel one, the kill turns the mode off over two edges (not an L1 step) | `proofs-d1e-f0207-set-off-unlocked` |
| `control_f1004_create_moves_no_token` (F-1004) | `acache_l2.rs:188-189` `lemma_createnode`: current entries and calls hold the fresh answer | 6 steps: PPR from absent seed 9 cached as {}; node 9 created with no edge; the cache serves {} (not an L1 step: 9 is listed fresh) | `proofs-d1e-f1004-create-moves-no-token` |
| `control_f1003_owner_cap` (F-1003, HD-1004) | `acache_l2.rs:197` `lemma_compute`: the fresh answer | 2 steps on 10,001 nodes: the owner lists 10,000 (not an L1 step: node 10000 missing) | `proofs-d1e-f1003-owner-cap` |
| `control_fc1001_read_creates_routines` (F-C1001) | `acache_l2.rs:209` `lemma_tricount`: a read writes no function and no record | 1 step: triangle_count creates the wrappers and records them (not an L1 step) | `proofs-d1e-fc1001-read-creates-routines` |
| `control_hd1003_direction_unchecked` (HD-1003) | `atrav_l2.rs:201` `lemma_splength`, `:211` `lemma_sppaths`: the direction contract | 2 steps: edge 1 -> 2; length "in" from 1 to 2 answers 1, paths for an unsupported direction answer no path (neither an L1 step) | `proofs-d1e-hd1003-direction-unchecked` |
| `control_f1008_every_graph_mixed` (F-1008) | `atrav_l2.rs:219` `lemma_varlen`: walks inside one graph | 3 steps: default 1 -> 2, graph 1 2 -> 3; the every-graph expansion of length 2 from 1 answers 3 (not an L1 step) | `proofs-d1e-f1008-every-graph-mixed` |

Counts (verified / errors, each including its counterexample, excluding its family's witness): F-0102, F-0101,
F-0201, F-0207, HD-1003 113/2; the other ten 114/1. Each control run took 1.98-2.11 s of wall time.

Live, test or model reproductions of the same as-built decisions: breadth-a-live-01-install (F-0103, F-0106),
breadth-a-mc-ins_setup-as-built (F-0102, source otherwise), breadth-a-probe-local-0101-0601 (F-0101),
breadth-a-live-02-identity (F-0202, F-0206, F-0208), intent-a-hd0201-unscoped-readers (F-0206), breadth-a-live-02-mode-off
(F-0201), breadth-a-mc-gid_mode-as-built (F-0201, F-0207, F-0208), b-10-live-cache and m10-cache-as-built-ppr (F-1004),
b-10-live-cap, ib-HD1004-pagerank-cap and m10-routes-as-built-pagerank-cap (F-1003), b-10-live-fp and
b-10-live-fp-detail (F-C1001), ib-HD1003-path-direction (HD-1003), b-10-live-scope and m10-walk-as-built-one-graph
(F-1008). F-0109 was confirmed in source only; `cx_f0109` reproduces it in the model (not live). These counterexamples
are proved over the models.

Selection. Reproduced defects of 01, 02 and 10 not controlled here, with the reason: F-C0101 (a Cypher filter's
JSON_VALUE on NULL qualifiers: translator semantics, not install); F-0204 (verify_graph's drift count on parallel
edges) and F-0205 (source only); F-0203, F-0209 (S4); F-1002 (random_walk's library gate and ^NKG scope; explorer
m10-routes/m10-nkg), F-1006 (subgraph vectors read by id), F-1007 (degree on parallel edges; explorer m10-degree),
F-1009 (khop seed check; explorer m10-walk), F-1013 (PageRankEmbedded's unqualified tables): not modelled here;
F-1001 blocked-access (no Arno library); F-1005 narrowed to the unindexed branch; F-1010..F-1012 and F-C1002 (Leiden
quality, numerics: unrepresentable in a result-contract model); F-0104, F-0105, F-0107, F-0108, F-0110 (documents and
setup hygiene, S3/S4). HD-0101's as-built matches its working assumption, and HD-0102's defect is not reproduced (its
probe was not run), so neither has a control; both working answers are in the reviewed design. F-0402 belongs to
module 04 (no control here), but it violates a premise of the cache model (section 8).

## 8. Premises (named; none is an assumption inside a proof)

| Id | Premise | The pin |
|---|---|---|
| P-I1 | setup runs with a login that can read and write ^IVG.Deploy("schema"); only setup writes it | not enforced: any login with global access can kill it (the F-0103 probe removed and restored it) |
| P-I2 | one setup at a time per namespace; each modelled setup step is one atomic step | not enforced: `_record_and_initialize` takes no lock between read_record and write_record (_engine/schema.py:2198-2312) |
| P-I3 | FR-009's inference (unrecorded schemas, an explicit schema), the 4.5.x grants and Arno copies, the embeddings and ^KG upgrade steps are not modelled | modelling restriction |
| P-I4 | a feature call on a namespace without the classes raises a named error (HD-0102 working answer) | unverified (HD-0102's probe proposed only; ADMIN_GUIDE.md:213-217 says such a namespace "has none of the behaviour") |
| P-I5 | the upgrade's placements are one atomic step | modelling restriction ("a migration runs DDL, rebuilds indexes and globals, and commits step by step", migrations/_commit.py:15) |
| P-I6 | the engine's `unreadable` covers any exception reading the record | as built (engine.py:1863: `except Exception`), wider than the documented privilege case |
| P-G1 | the invalid names are "0" and names with a control character; the Python mirror's C1 gap (F-0203) is not modelled | modelling restriction |
| P-G2 | each reader's statements see one state (get_nodes_by_label is two statements and more) | not enforced (READ COMMITTED, no lock): a writer may interleave; not observed |
| P-G3 | create_node writes one label and one property; node content is SQL rows only | modelling restriction |
| P-G4 | an erase of graph g is atomic and overlaps no writer of g | **violated**: F-1201 (live), F-C1202 (core model); P-E6 of `proofs-d1c` |
| P-M1 | one triple of one graph; Cypher's keyed insert takes a fresh key (MAX(ekey)+1) | modelling restriction; two concurrent keyed inserts could compute the same MAX+1 (one then refused by the unique key), not modelled |
| P-M2 | each SQL statement and global operation is one atomic step; a Cypher statement asks the mode once | as built (translator.py:441-457) |
| P-M3 | mode changes come from GraphMode.Set only (no Kill ^IVG.GraphMode elsewhere; erase forgets the cache, admin.py:928-936) | assumed |
| P-C1 | one graph (the default), one predicate; the cache key's graph component and the front memo (iris_sql_store.py:948-959) are not modelled | modelling restriction |
| P-C2 | an answer is its rows and the edges its scores are computed over; the scores are a function of them | modelling abstraction (numerics not modelled) |
| P-C3 | the owner route only; the native reader (F-1001, blocked) and the R313 COUNT:MAX PageRank key are not modelled | modelling restriction |
| P-C4 | every adjacency write raises ^KG("__version"); the node writers are create_node and delete_node (EraseNodeIds) | by source reading of Adjacency.cls (:92, 135, 157, 260, 299); bulk loaders, rebuilds and Cypher node writes not checked |
| P-C5 | writes commit as they are made: no reader sees an uncommitted write and none is rolled back | **violated**: F-0402 (live, module 04): an ObjectScript reader computes over an open write, $Increment of the token survives the rollback (iris-contract E-INCR), and the entry with the rolled-back edge is served as current |
| P-C6 | a modelled call step (Lookup, a computation, Put, a node delete) is atomic | not enforced: a computation walks live globals with no lock; Lookup reads the token and the entry in one call (AlgoCache.cls:27-36) |
| P-T1 | no writer of the default graph overlaps a CDLP call (a guard on the writers in this model) | not enforced: CDLPJson walks ^KG with $Order and no lock; not observed |
| P-T2 | a shortest-path or expansion answer is any answer its contract allows over what the routine reads; the search (bidirectional BFS, VarLength's walk) is not verified | modelling abstraction |
| P-T3 | one predicate; VarLength "out" only, no type filter, ends as a set (lengths not answered); max_hops a number | modelling restriction |
| P-T4 | no node of the default graph is deleted in the traversal model | modelling restriction (a node deleted during a CDLP call would leave its label) |
| P-T5 | the in entries mirror the out entries (the row's functional index writes both); rows and index entries correspond | assumed for the index; the rows-to-index correspondence is not modelled (`inv10t` is over the index only), and in F-0201's live probe verify_graph reported a row with no ^KG("out") entry |

## Premises the pin violates

Two premises of these models are false at pin `3eaa79cf` by this audit's own evidence: P-G4 (an erase overlaps no
writer of its graph: F-1201 live, F-C1202 in the core model) and P-C5 (writes commit as made, none rolled back: F-0402
live, module 04). Nine more are not enforced by the pin, with no observed violation: P-I1, P-I2, P-I4 (unverified),
P-G2, P-M3, P-C4 (partly read), P-C6, P-T1, P-T5. Every reviewed-design element R01-1..R01-4, R02-1..R02-6 and
R10-1..R10-5 is absent at the pin (section 6), and each control shows the corresponding as-built decision violating
the model's contract on a reachable run. R01-5 and R01-6 rest on HD-0102's and HD-0101's working answers (status
assumption); R02-2 rests on HD-0201's (assumption); R10-2 and R10-4 on HD-1004's and HD-1003's (supported). So no
safety result here transfers to the product. What transfers is the negative: each as-built decision of section 7
breaks the contract on a reachable run of the model.

## 9. Cost (measured, `RESULTS.json`)

Baseline: Verus 2.17 s, SMT 1.71 s, 4.16 M rlimit over 115 functions, wall 2.59 s, 0.48 GB.

| Module proof | Functions | SMT ms | rlimit | Largest function | Largest proof lemma |
|---|---|---|---|---|---|
| 01 record/readiness/upgrade/legacy (`inst_*`, `witness_inst`) | 26 | 577 | 1.70 M | `inst_l2::lemma_step` 0.42 M | `inst_l2::lemma_step` 0.42 M |
| 02 graph names and graph-scoped reads (`gid_*`, `witness_gid`) | 21 | 115 | 0.29 M | `witness_gid::witness_gid` 0.08 M | below 0.08 M |
| 02 multigraph mode (`gmode_*`, `witness_gmode`) | 20 | 308 | 0.69 M | `witness_gmode::witness_gmode` 0.35 M | below 0.08 M |
| 10 cached answers, completeness, footprint (`acache_*`, `witness_acache`) | 21 | 421 | 0.85 M | `witness_acache::witness_acache` 0.38 M | `acache_l2::lemma_step` 0.12 M |
| 10 path direction, walk scope, label propagation (`atrav_*`, `witness_atrav`) | 27 | 279 | 0.64 M | `witness_atrav::witness_atrav` 0.17 M | below 0.08 M |

No rlimit was raised and no proof looped. The 16 decisive runs took 33 s of Verus wall time in total (59 s for the
runner with locks and builds; the same again for the scratch run). Development needed about 35 short Verus runs: two
trigger problems through the abstraction (an L2 invariant restated on the tables, `lemma_inv02_is_inv1`; quantified
contracts moved into named spec functions, e.g. `varlen1`), the CDLP predicates refactored to take the graph's
components (one rlimit failure in `lemma_cdlpend` during development, fixed by that refactoring), fuel and multi-trigger
hints for the recursive `walk`, and the F-1004 assertion moved from a design fact onto the cache-validity obligation.

## 10. Trust inventory

This crate has no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). The scan of `actors` (`c03f9fa`) finds none either. vstd is Verus's
trusted base (finite `Set`/`Map` with their axioms). The gate status is **declared empty** (`RESULTS.json`
`trust_inventory`).

## 11. What is NOT proved (open obligations)

- **No proof connects the Python or ObjectScript to these L2 machines** (D-2, D-3). The five
  `theorem_raw_executions_refine` are the plug-in points for trace conformance; no journal trace is replayed through
  them.
- **The families are not composed.** `inst` and `acache` share the dictionary and ^IVG.Deploy (the record vs the
  routine record); `gid`, `gmode`, `acache` and `atrav` share the graph's rows and ^KG. Their joint behaviour is by
  inspection; no joint invariant is proved.
- **Concurrency the premises exclude**: an erase overlapping a writer (P-G4, violated), rolled-back writes (P-C5,
  violated), readers spanning several statements or a live walk (P-G2, P-C6, P-T1), concurrent setups (P-I2).
- **Numerics**: scores, iteration limits, tolerances, tie-breaking and convergence (HD-1002), Leiden's quality
  (F-C1002) and the shortest-path search itself (P-T2) are not modelled; only result contracts are.
- Module 01 items not modelled: FR-009's inference, the 4.5.x legacy grants and Arno copies, F-0104/F-0105/F-0107/
  F-0108/F-0110, the upgrade's embeddings and ^KG steps, the readiness of individual capabilities (adjacency index,
  ledger, erase, temporal index; HD-0102 lists them).
- Module 02 items not modelled: F-0203, F-0204, F-0205, F-0209, keyed edges' ledger/Bolt identity, all-graph walks'
  graph listing, bulk writers' graph names, and names reaching the ledger key (ForLedger).
- Module 10 items not modelled: F-1001 (blocked), F-1002, F-1005, F-1006, F-1007, F-1009, F-1010..F-1013, the native
  readers and their proof record, ^NKG and its readers, betweenness, WCC, k-core, the cache of CDLP/WCC answers (the
  cache proof covers the PPR and PageRank keys).
- HD-0101, HD-0102 and HD-0201 are assumptions, HD-1003 and HD-1004 supported working answers; the F-0102, F-0103,
  F-0109, F-0101, F-0202, F-0206, F-0106, F-0201, F-0207, F-0208, F-1004, F-C1001 and F-1008 remedies are proposals,
  not maintainer decisions.
- No progress or liveness property.
- The L1s are new contracts written for this lane; their correspondence to the ontology statements (INS-*, GID-*,
  ALG-*) and to the explorer models' invariants is by inspection.

## Debt accounting (for `PROOF-DEBT.md` D-1)

Paid, model-level only, by `proofs-d1e-baseline` and the 15 `proofs-d1e-*` control runs: the §3.3 L1, L2, refinement
and controls items for module 01 (the record, first access, setup's reply, readiness, the 4.0.0 upgrade, legacy
removal), module 02 (graph names and keys, the default-graph and all-graph readers, multigraph mode of one triple) and
module 10 (cached PPR and PageRank answers, PageRank completeness, triangle_count's footprint, shortest-path direction,
variable-length graph scope, label propagation's labels), as modelled. Still owed under D-1: modules 00, 07-09 and
15-17, and the unmodelled parts of 01, 02 and 10 listed in section 11. This lane does not edit `PROOF-DEBT.md` or
`STATUS.md` (outside its write scope); the orchestrator moves the row. The crate's `Cargo.lock` is `proofs-d1c`'s with
only the root package name changed.
