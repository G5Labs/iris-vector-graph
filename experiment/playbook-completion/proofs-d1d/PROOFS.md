# PROOFS-D1D: Verus L1/L2 refinement for modules 07 (text search), 08 (Cypher on SQL) and 09 (native executor) (proof debt D-1, playbook §3.3)

Crate `experiment/playbook-completion/proofs-d1d` (`ivg-d1d-proofs`), Verus 0.2026.10.04.426d8b0, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved** (`--no-cheating`, no trusted item in this
crate), about **models**. Every theorem here is a statement about an L1 contract or a reviewed L2 machine. None says
that the Python or ObjectScript at pin `3eaa79cf` has the property. The product's obligations stay as the as-built
evidence leaves them (failed or open: `findings/audit/07.json`, `08.json`, `09.json`, `zz-versions.json`).

Each module has two families, chosen where its reproduced defects of highest impact sit. Where an operation's own
semantics is too large to model (BM25 ranking, tokenisation, the Cypher translation, plan generation), the L1 states the
invariant-relevant abstraction explicitly (each L1 file's header, and below).

| Gate item (§3.3) | 07 one index's writers | 07 the namespace's indexes | 08 write queries | 08 read scope | 09 plan cache | 09 native read |
|---|---|---|---|---|---|---|
| L1 contract with the business invariants (`Contract` + `SafeContract`) | `src/bmw_l1.rs` | `src/bmn_l1.rs` | `src/cyw_l1.rs` | `src/cys_l1.rs` | `src/planc_l1.rs` | `src/nread_l1.rs` |
| L2 machine over the stored layout, reviewed design | `src/bmw_l2.rs` (^BM25Idx(name): postings, token records, header counters; IRIS transaction levels; the write lock; a running build) | `src/bmn_l2.rs` (^BM25Idx: every index's subtree and `cfg graph`; the `__stop__` node; readers' graph check; the eraser) | `src/cyw_l2.rs` (nodes, rdf_edges qualifiers, rdf_props, ^IVG.Ledger("meta"), the engine's LedgerGuard cache) | `src/cys_l2.rs` (nodes, rdf_labels, rdf_edges with graph_id; three read routes) | `src/planc_l2.rs` (^IVG.CypherCompiled entries and lines, generated classes, build locks, build jobs, readers, the $ZCRC hash) | `src/nread_l2.rs` (relationship rows, rdf_labels, ^KG("label"), the two functional indexes, SQL grants, the executor's check cache, the $ZCRC of relationships) |
| `Refines<L1>` for **every** L2 step | 11 labels (`lemma_step`) | 5 labels | 4 labels | 6 labels | 8 labels | 12 labels |
| L2 invariant inductive (`SafeContract`) | `inv07w` | `inv07n` | `inv08w` | `inv1` (FKs) | `inv09p` | `inv09r` |
| Every raw L2 execution refines L1 and keeps the invariant | `bmw_l2::theorem_raw_executions_refine` | `bmn_l2::…` | `cyw_l2::…` | `cys_l2::…` | `planc_l2::…` | `nread_l2::…` |
| Broken-implementation controls rejected in the expected file | 3 of 3, `src/bmw_l2.rs` | 4 of 4, `src/bmn_l2.rs` | 5 of 5, `src/cyw_l2.rs` | 3 of 3, `src/cys_l2.rs` | 2 of 2, `src/planc_l2.rs` | 4 of 4, `src/nread_l2.rs` |
| Each control's counterexample proved reachable | `cx_fc0702`, `cx_f0701`, `cx_f0704` | `cx_fc0701`, `cx_f0705`, `cx_f0707`, `cx_f0702` | `cx_f0801_ttl`, `cx_f0801_failopen`, `cx_f0805`, `cx_fc0803`, `cx_f0810` | `cx_f0802`, `cx_f0816`, `cx_f0818` | `cx_f0901`, `cx_fc0901` | `cx_f0902`, `cx_f0908`, `cx_hd0902`, `cx_f0906` |
| Non-vacuity (the reviewed L2 does real work) | `witness_bmw` | `witness_bmn` | `witness_cyw` | `witness_cys` | `witness_planc` | `witness_nread` |
| Trust inventory | empty (this crate and `actors`) | same | same | same | same | same |

Baseline (decisive round r2): `cargo verus verify -- --no-cheating`: **118 verified, 0 errors**; Verus 2.28 s, SMT
1.69 s, 3.72 M rlimit, wall 2.70 s, 0.47 GB peak (registry `proofs-d1d-r2-baseline`, log
`$RUN_DIR/proofs-d1d/r2/baseline.log`, which ends with the counts read from its JSON). Gate: **pass**, 21 of 21
controls rejected in their expected file with their counterexample verified (`RESULTS.json`, round `r2`, sources
SHA-256 `24b0330807ead96f...`). An unregistered run over the same sources (`$RUN_DIR/proofs-d1d/scratch-2`) gave the
same result.

Rounds: round r1 (registry `proofs-d1d-baseline` and 21 `proofs-d1d-<control>`, logs `$RUN_DIR/proofs-d1d/*.log`, its
RESULTS.json kept as `$RUN_DIR/proofs-d1d/RESULTS-r1.json`, sources `a8b4c62549b4f668...`) also passed, but this lane's
own review found that `cx_f0818` and `witness_cys` began at a constructed state holding node rows instead of stepping
there from the initial state, and that `witness_nread` listed 8 of its 12 steps. Round r2 adds those steps (the only
source change); the r1 records and logs stay as they were. Every figure below is r2's. Rerun:
`source experiment/playbook-completion/environment.sh; python3 experiment/playbook-completion/proofs-d1d/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600` after `cargo clean -p`; `PROOFS_OUT_DIR=<dir>` writes logs and
RESULTS.json there so a re-check never overwrites the registered logs; `--register` registers the decisive runs;
`--round <r>` gives a later decisive round its own log directory `$RUN_DIR/proofs-d1d/<r>` and registry ids
`proofs-d1d-<r>-*`).

The executable twins are breadth lane B's explorer families (`models/breadth-b/src`): `m07` machines `bm25` (F-0701,
F-0704) and `leg` (F-0705, F-0707); `m08` machines `txn` (F-0805, F-0806) and `scope` (F-0802, F-0816, F-0818); `m09`
machines `planc` (F-0901, F-C0901, F-0905), `used` (F-0902), `gate` (F-0906) and `mode` (F-0903); module 11's guard
machine (`b-mc-m11-guard-*`) for F-0801. F-C0702, F-C0701, F-0702, F-C0803, F-0810, F-0908 and HD-0902 have no explorer
model; their counterexamples here are the first model-level reproductions.

## 1. Module 07: one BM25 index's writers and the caller's transaction (`bmw_l1.rs`, `bmw_l2.rs`)

**L1.** State: what searchers and the caller see (`db`: the index as document -> tokens, `None` when there is none, and
the caller's rows) and the caller's open transaction (`open`: `db` when it began). Labels `CBegin`, `CWrite`, `CCommit`,
`CRollback`, `Build{corpus, ok}`, `Insert{d, toks, ok}`, `Delete{d, ok}`, `Drop`, `Search{ans}`. Abstraction: one index;
tokenisation is given (documents are their token sets); ranking is not modelled: a search answers the documents it
scores and the set its counters count (N and totalLen are functions of it). Rules and theorems:

- **a failed write changes nothing**, the caller's open transaction and rows included (SYS-I3, TXT-X2; the 4.6.4
  nesting rule, `_write_txn.py:1-30`): `theorem_failed_write_changes_nothing`;
- **a write nested in the caller's transaction goes with the caller's rollback**: `theorem_nested_write_goes_with_callers_rollback`;
- **a build replaces the index whole or changes nothing** (HD-0701 working answer, FR-016): `theorem_build_all_or_nothing`;
- **a search's counters count exactly the documents it scores** (TXT-I2, FR-016/FR-018): `theorem_search_counts_its_documents`;
- `inv1` (proved inductive): every stored document has a token.

**L2.** Layout: `docs` (tf/doc/len per document), `counted` (the documents the header's N and totalLen count: an
abstraction of the arithmetic, exact while the header is consistent), `hdr`, the caller's rows, the caller's level as the
image it would roll back to, a running build (corpus, to-do, local count, shadow).

| L2 step (source) | L1 step | Proof |
|---|---|---|
| `CBegin`/`CWrite`/`CCommit`/`CRollback` (the caller's SQL) | same | `lemma_step` |
| `Ins{fail}` (Insert BM25Index.cls:442-493: lock, RequireWritable, TSTART, body, TCOMMIT, or the Catch :486-490) | `Insert{ok: !fail}` | `lemma_ins` |
| `Del{fail}` (Delete :496-514, Catch :507-511) | `Delete{ok: !fail}` | `lemma_del` |
| `BStart` (Build :97-99) | stutter | `lemma_bstart` |
| `BDoc` (IndexDoc :178-205) | stutter | `lemma_bdoc` |
| `BHeader{refused}` (:160-170; the handle's 0-row refusal, vector.py:299-310) | `Build{ok: !refused}` | `lemma_bheader` |
| `Drop` (:587-591) | `Drop` | `lemma_step` |
| `Search` | `Search` | `lemma_step` |

`inv07w`: the header counts exactly the stored documents, no header means no documents, every document has a token (for
the live state and the caller's image); a running build's shadow is exactly the corpus's indexed documents done so far,
and no caller transaction is open during it. L2 theorems: `theorem_header_counts_the_stored_documents`,
`theorem_build_invisible_until_published`.

## 2. Module 07: the namespace's indexes (`bmn_l1.rs`, `bmn_l2.rs`)

**L1.** State: `idx` (name -> documents and recorded graph). Labels `Build{n, g, corpus, ok}`, `Insert{n, d, text, ok}`
(a first Insert creates an index recording no graph), `Drop{n, ok}`, `Search{n, g, q, ans}`, `EraseGraph{g}`.
Abstraction: words are integers, a text is its word set, tokenisation is set difference with the stopwords (`sw()`, two
words standing for the 77; word 1 is "the"); a search answers the documents holding a query token. Rules and theorems:

- **"__stop__" is not an index name** (HD-0704, supported; BM25Index.cls:626-631): `theorem_stop_name_is_not_an_index`;
- **a document's tokens are its words less the 77 stopwords, in every index** (TXT-D1, USER_GUIDE.md:886-891):
  `theorem_tokens_are_words_less_the_stopwords`;
- **a search for graph g answers only from an index recorded for g**; an index with no recorded graph answers no
  scoped search, the default graph's included (TXT-I7, TXT-B8.3, HD-0703): `theorem_scoped_search_reads_its_graphs_index`;
- **after graph g is erased no index built for g remains** (CONTEXT.md:198-208; F-0702 remedy):
  `theorem_erase_leaves_no_index_of_the_graph`;
- `inv1` (proved inductive): no index is named "__stop__"; every document has a token and no stopword.

**L2.** Layout: `gl` (each name's subtree with its `cfg graph`), `stop` (the first-level children of
^BM25Idx("__stop__"), Tokenize's test at :83; InitStopwords :41-50 restores the 77 when "the" is missing: `eff`).
Steps `Build`, `Insert`, `Drop`, `Search{surf}` (`UseGraph`: Cypher under USE GRAPH; `Engine`: fusion legs and unscoped
Cypher, which read the graph through Info and `_index_graph`), `Erase`. Each maps to the L1 label of the same name
(`lemma_build`, `lemma_insert`, `lemma_drop`, `lemma_search`, `lemma_erase`). `inv07n`: the stopword node holds exactly
the 77, no index is named "__stop__", plus L1's `inv1`. L2 theorem: `theorem_stopword_node_is_the_77`.

## 3. Module 08: Cypher write queries under the ledger's strict guard (`cyw_l1.rs`, `cyw_l2.rs`)

**L1.** State: nodes, relationships (one type), their qualifiers, node properties, and the ledger's `en`/`strict`.
Labels `Meta` (another process changes the ledger), `Write{q}`, `Refuse{q, why}` (`Strict`, `Unavailable`, `Env`,
`Dup`). **Abstraction of the translation**: a write query is one of three shapes, each given by its openCypher effect:
`CreateLit` (CREATE of nodes and of relationships between literal endpoints), `MergeCopy` (MATCH (a), (t) MERGE
(a)-[r]->(t) ON CREATE SET r = a, given by the rows' (a, t) pairs; modelled only for rows whose relationship does not
exist yet and whose pairs are distinct, as in the live check), `SetProp` (SET n.k = value or literal null). Values are
integers; `Val::Empty` is the stored '' standing for no value. Ledger changeset recording is not modelled. Rules and
theorems:

- **in strict mode no write query commits** (ledger-api.md:82-92, CYP-X7.2; HD-0801): `theorem_strict_mode_refuses_every_write`;
- **a refused query changes nothing, and is never refused because a relationship it creates exists** (CYP-I6.4,
  KNOWN_ISSUES.md:25-31): `theorem_refused_query_writes_nothing`, `theorem_existing_relationship_create_adds_nothing`;
- **each merged relationship carries its own row's node's properties** (CYP-B6.8): `theorem_merge_copies_each_rows_node`;
- **a null SET removes the key** (CYP-B6.9): `theorem_null_set_removes_the_key`;
- `inv1` (proved inductive): every relationship has its qualifiers; no stored property or qualifier is empty.

**L2.** The rows, ^IVG.Ledger("meta"), and the guard's cache (`cache`, `fresh`). Steps `Meta` -> `Meta`; `Tick` (the
cache ages past the TTL) -> stutter; `Exec{q, pok, top}` (guard passes, the translation commits; `pok`: the probe can
run; `top`: the row SELECT TOP 1 returns) -> `Write{q}` (`lemma_exec`); `Refuse{q, pok, why}` -> `Refuse{q, why}`
(`lemma_refuse`). `inv08w` = L1's `inv1` of the abstraction. L2 theorem: `theorem_strict_meta_admits_no_write` (from a
state whose Meta is strict, no `Exec` is enabled, whatever the cache and the probe).

## 4. Module 08: graph scope of reads (`cys_l1.rs`, `cys_l2.rs`)

**L1.** The stored rows (nodes, labels, relationships, each with its graph; node ids shared across graphs). Reads
`Labels{g}` (CALL db.labels() under USE GRAPH g: the label rows behind the names), `Counts{g}` (the count UNION query
under USE GRAPH g: the rows it counts), `Walk` (an all-graphs `MATCH (a) WITH a MATCH (a)-[*1..2]->(b)`). Rules:
**a scoped read answers from its graph's rows only** (SYS-I2, USER_GUIDE.md:401-404) and **a walk stays in its source's
graph** (FR-009 as cited at translator.py:15423-15424): `theorem_scoped_reads_answer_their_graph`,
`theorem_walk_stays_in_its_graph`; `inv1`: foreign keys. **L2**: the same rows (identity abstraction) with the read
routes as the pin computes them; the designs differ only in the routes, where the findings are; `lemma_step` maps every
step to itself.

## 5. Module 09: the compiled-plan cache (`planc_l1.rs`, `planc_l2.rs`)

**L1.** State: the data (`db`). Labels `Write{db}`, `Answer{s, a}`. **Abstraction**: a plan shape is an integer and the
interpreter's answer for it is `interp(s, db) = (s, db)`: an answer identifies the shape it was computed for (code
written for another shape answers differently, as the live collision did: [[2]] where SQL answered [[1]]); each anchor's
Walk1 call is one answer. Rule: **every answer of a read of shape s is the interpreter's answer for s** (ADR-0014:19,
NAT-I3): `theorem_every_answer_is_its_shapes` (L1 invariant `true`; the rule is on the labels).

**L2.** Steps `For` (Gen.cls:61-105, one atomic step) -> stutter (`lemma_for`); `Walk` (one Walk1 call; a missing class
raises in Run and the engine answers by SQL) -> `Answer` (`lemma_walk`); `BLeave`, `BRefuse` (R311 digest check
:175-182), `BCompile` (:183-205), `BFail` (:208-214), `BMark` (:207) -> stutter (`lemma_bother`, `lemma_bcompile`,
`lemma_bmark`); `Write` -> `Write`. Initial states: any hash assignment, collisions included. `inv09p`: an "ok" entry's
class (if it exists) was compiled from that entry's shape (NAT-T5.16); a reader in flight runs a class compiled from its
shape; a compiled build's class is its lines' shape; every class name is below the counter. L2 theorem:
`theorem_ok_entry_runs_its_shapes_class`.

## 6. Module 09: a native read against the SQL path (`nread_l1.rs`, `nread_l2.rs`)

**L1.** State: relationships into one hub (`rels`, with a writer's open-transaction image `snap`), `held` (users holding
SELECT), `chk` (process/user checks passed), label rows. **Abstraction**: one pattern `(a)-[:T]->(h)<-[:T]-(c)`, answered
as the set of ordered pairs of distinct relationships (`pairs`); one label read. Rules and theorems:

- **a native answer is the SQL path's** (FR-002, NAT-B1.11): `theorem_native_answer_is_the_sql_answer`;
- **a native read by process p of user u runs only after a check that passed for (p, u), now or earlier** (FR-011 as
  written, "cached per process and user": HD-0901's P1'): `theorem_native_read_needs_a_passed_check`;
- **a shadow-mode answer was compared** (US1/FR-006 with HD-0902's working answer): `theorem_shadow_answer_was_compared`;
- **a read sees another writer's open transaction and loses it on rollback** (HD-0903's working answer, F-0909):
  `theorem_open_transaction_is_seen_and_rolled_back`;
- L1 invariant `true` (the rules are on the labels).

**L2.** Steps (all mapped by `lemma_step`): the writer's `TBegin`/`TAdd`/`TCommit`/`TRollback`, `Grant`/`Revoke`,
`LWrite` (the row, and ^KG("label") from the label index when functional or by the engine when the edge index is not,
engine.py:703-724), `Run` -> `NRead` (`lemma_run`), `RunLabels` -> `NLabels` (`lemma_runlabels`), `Decline` -> `NRefuse`,
`ShadowRun` -> `Shadow` (`lemma_shadow`), `SqlRead`. Initial states: any grants, any index declarations (edge-only
included), any checksums. `inv09r`: ^KG("label") equals the label rows wherever label writes keep it. L2 theorem:
`theorem_native_read_sees_the_open_transaction` (HD-0903: with a writer's transaction open, a native read and a
SQL-path read answer the same rows, the uncommitted ones included).

**HD-0903 has no control**: under its working answer (dirty per-store reads on both paths, USER_GUIDE.md:260-262) the
pin's behaviour is the model's (live probe intent-a-hd0903-native-read-open-txn), so there is no as-built defect to put
back; the theorem records it at model level. F-0909 (spec 253's "same process" reason) is a documentation defect: the
model's read runs in another process than the writer's and still sees its rows, by dirty reads (premise P-0002).

## 7. Reviewed design (the findings' remedies and the working answers) and its status at the pin

| Id | Element | Source | At the pin |
|---|---|---|---|
| R07-1 | a failed Insert/Delete rolls back its own level only (TROLLBACK 1) | F-C0702 remedy, `_write_txn` | no: `If $TLevel > 0 TRollback` (BM25Index.cls:487, :508) |
| R07-2 | Build takes the write lock, writes a shadow generation, publishes it with its header in one step; Drop takes the lock | HD-0701 working answer (assumption), F-0701 remedy | no: Kill then in-place rewrite, header last, no lock (:97-175); Drop a bare Kill (:587-591) |
| R07-3 | a refused build publishes nothing | F-0704 remedy | no: the handle refuses after Build (vector.py:299-310) |
| R07-4 | writers refuse "__stop__" | HD-0704 (supported), F-0706/F-C0701 remedy | no: BM25BuildInput checks non-empty only (_validate.py:163-179) |
| R07-5 | an absent `cfg graph` reads as unknown; a scoped search answers only from an index recorded for its graph | F-0705, F-0707 remedies, HD-0703 | no: Info answers "" (:612); no comparison under USE GRAPH (translator.py:3133-3134, 3283-3292) |
| R07-6 | the graph eraser drops the indexes recorded for the graph | F-0702 remedy | no: ^BM25Idx untouched (Eraser.cls; GraphStores.cls:26-133) |
| R08-1 | the guard reads Meta at each write and refuses when it cannot (fail-closed) | HD-0801 options b/c (assumption) | no: 5 s cache (guard.py:20, 38-41), fail-open (:42-56) |
| R08-2 | CREATE between literal endpoints is guarded by NOT EXISTS | F-0805 remedy (translator.py:10306-10365 does it for matched endpoints) | no: bare INSERT (translator.py:10212-10248) |
| R08-3 | `SET r = a` copies the node correlated with each relationship's own row | F-C0803 remedy | no: SELECT TOP 1 with no ORDER BY (translator.py:12362-12395) |
| R08-4 | a literal null deletes the property row | F-0810 remedy (the computed-null path does, translator.py:13648-13654) | no: UPDATE to '' (:13655-13665) |
| R08-5 | the count shortcut, db.labels and the walk honour the graph | F-0802, F-0816, F-0818 remedies | no (query.py:1843-1856; engine.py:1313-1318; translator.py:15404-15431) |
| R09-1 | each build compiles a class of a fresh name (a counter); a running class is never recompiled | F-0901 remedy ("or a counter"; the SHA-256 digest name is the other option, not modelled) | no: IVGC.P<$ZCRC> (Gen.cls:69, 183) |
| R09-2 | Build marks the entry only if, under its lock, it still holds the shape compiled | F-C0901 remedy | no: marks whatever entry h holds (Gen.cls:207) |
| R09-3 | the interpreter keeps used relationships by exact identity | F-0902 remedy (the compiled walk does, Gen.cls:410-433) | no: $ZCRC string (Exec.cls:1243-1245) |
| R09-4 | Exec.Run checks SELECT per process and user, cached | FR-011 literal (HD-0901 alternative c; **intent-undecided**: R280 makes the database resource the boundary) | no: no check in Run (Exec.cls:32-72); the engine's own check (engine.py:559-586) |
| R09-5 | shadow mode raises when the native path raises | HD-0902 working answer (assumption) | no: None, SQL rows, uncompared (query.py:2069-2077, 2146-2152) |
| R09-6 | the native gate requires both functional indexes | F-0906 remedy | no: edge index only (native_plan.py:528-529) |
| as built | Insert/Delete under the lock in a transaction; Build reads only its graph's nodes; the 77-word list and InitStopwords; the guarded matched-endpoint INSERT; per-query write transaction; the R311 digest check; the compiled walk's exact relationship identity; dirty reads on both paths | BM25Index.cls, translator.py, query.py, Gen.cls | yes |

## 8. Broken-implementation controls

Each feature puts back one as-built decision. Every error is in the expected file, every failing function is in that
file's module, every function of every other module verifies (`RESULTS.json`, `failing_outside_expected_module` empty),
and each control's counterexample (compiled only with it) is a proved run of the L2 step relation, as the control
changes it, from its initial state to a step that is not an L1 step.

| Control (finding) | Rejected at (function: obligation) | Proved counterexample | Registry |
|---|---|---|---|
| `control_fc0702_bare_trollback` (F-C0702, S1) | `bmw_l2.rs:184` `lemma_ins`, `:202` `lemma_del`: a failed write takes back its own level only | 3 steps: caller begins, writes row 1, a failing Insert ends the caller's transaction and takes row 1 (not an L1 step) | `proofs-d1d-r2-fc0702-bare-trollback` |
| `control_f0701_build_in_place` (F-0701, S2) | `bmw_l2.rs:216` `lemma_bstart`, `:225` `lemma_bdoc`, `:238`/`:247` `lemma_bheader`: the build is invisible until published, the header counts the stored documents | 5 steps: build of {0, 1} indexes 0 in place; an Insert of 2 creates a header over the half-built index (not an L1 step); the header counts {0, 1} of {0, 1, 2}; a search scores three documents with the counters of two (not an L1 step) | `proofs-d1d-r2-f0701-build-in-place` |
| `control_f0704_late_refusal` (F-0704, S2) | `bmw_l2.rs:238` `lemma_bheader`: a refused build publishes nothing | 5 steps: build publishes {0}; a 0-row build is refused after replacing it (not an L1 step) | `proofs-d1d-r2-f0704-late-refusal` |
| `control_fc0701_stop_name_accepted` (F-C0701/F-0706, S2) | `bmn_l2.rs:134` `lemma_build`, `:149` `lemma_insert`, `:167` `lemma_drop`: "__stop__" is refused | 2 steps: Build of "__stop__" accepted (not an L1 step); a build of index 3 drops the word "doc" (not an L1 step); a search for "doc" finds nothing | `proofs-d1d-r2-fc0701-stop-name-accepted` |
| `control_f0705_absent_graph_is_default` (F-0705, S1) | `bmn_l2.rs:180` `lemma_search`: a scoped search reads an index recorded for its graph | 1 step: an Insert creates index 3 (no graph); a default-graph engine search answers its document (not an L1 step) | `proofs-d1d-r2-f0705-absent-graph-is-default` |
| `control_f0707_no_scope_check` (F-0707, S1) | `bmn_l2.rs:180` `lemma_search` | 1 step: index 3 built for graph 2; a search under USE GRAPH 1 answers its document (not an L1 step) | `proofs-d1d-r2-f0707-no-scope-check` |
| `control_f0702_erase_keeps_index` (F-0702, S1) | `bmn_l2.rs:188` `lemma_erase`: the eraser drops the graph's indexes | 2 steps: index 3 built for graph 2; erasure of graph 2 keeps it (not an L1 step); a search for graph 2 still answers the erased node | `proofs-d1d-r2-f0702-erase-keeps-index` |
| `control_f0801_ttl_window` (F-0801, S2) | `cyw_l2.rs:154` `lemma_exec`: the guard reads the ledger's Meta now | 3 steps: a write caches Meta (off); another process sets strict; within the TTL a CREATE commits (not an L1 step) | `proofs-d1d-r2-f0801-ttl-window` |
| `control_f0801_fail_open` (F-0801, S2) | `cyw_l2.rs:154` `lemma_exec` | 2 steps: strict mode set; a write whose probe cannot run commits (not an L1 step) | `proofs-d1d-r2-f0801-fail-open` |
| `control_f0805_literal_insert_unguarded` (F-0805, S2) | `cyw_l2.rs:177` `lemma_refuse`: a query is never refused for an existing relationship | 2 steps: 1->2 created; a query creating node 3 and 1->2 is refused for the duplicate (not an L1 step), node 3 not written | `proofs-d1d-r2-f0805-literal-insert-unguarded` |
| `control_fc0803_top1_copy` (F-C0803, S2) | `cyw_l2.rs:160` `lemma_exec`: each merged relationship gets its own row's node | 4 steps: nodes 1, 2, 9 with property 7 = 1 and 2; the MERGE over (1, 9), (2, 9) with TOP 1 = (1, 9) gives 2->9 node 1's properties (not an L1 step) | `proofs-d1d-r2-fc0803-top1-copy` |
| `control_f0810_null_keeps_key` (F-0810, S2) | `cyw_l2.rs:164` `lemma_exec`: a literal null deletes the row | 3 steps: node 1, property 7 = 3, SET to null keeps key 7 empty (not an L1 step) | `proofs-d1d-r2-f0810-null-keeps-key` |
| `control_f0802_shortcut_unscoped` (F-0802, S1) | `cys_l2.rs:68` `lemma_step` (Counts) | 2 writes: node 5 in graph 1, node 6 in graph 2; the shortcut under USE GRAPH 1 counts both (not an L1 step) | `proofs-d1d-r2-f0802-shortcut-unscoped` |
| `control_f0816_dblabels_unscoped` (F-0816, S1) | `cys_l2.rs:66` `lemma_step` (Labels) | 4 writes: labels 7 (graph 1) and 8 (graph 2); db.labels() under USE GRAPH 1 lists 8 (not an L1 step) | `proofs-d1d-r2-f0816-dblabels-unscoped` |
| `control_f0818_vlp_crosses_graphs` (F-0818, S1) | `cys_l2.rs:70` `lemma_step` (Walk) | 6 writes: nodes 5, 6 of graph 1 and 6, 7 of graph 2; 5->6 in graph 1, 6->7 in graph 2; the walk from (1, 5) answers 7 (not an L1 step) | `proofs-d1d-r2-f0818-vlp-crosses-graphs` |
| `control_f0901_shared_class_name` (F-0901, S2) | `planc_l2.rs:211` `lemma_bcompile`: a build compiles into a class nobody runs yet | 8 steps (shapes 0 and 1 on hash 7): shape 0 built and marked; a reader of 0 runs it for one anchor; a reader of 1 rewrites the entry; its build recompiles IVGC.P7; the first reader's second anchor answers shape 1's answer (not an L1 step) | `proofs-d1d-r2-f0901-shared-class-name` |
| `control_fc0901_mark_any_entry` (F-C0901, S2) | `planc_l2.rs:232` `lemma_bmark`: a build marks only the entry holding its shape | 7 steps: shape 1's build compiles class 0; a read of 0 rewrites the entry; the build marks it ok with class 0 (entry of 0 bound to 1's class); 0's job leaves; the next read of 0 answers shape 1's answer (not an L1 step) | `proofs-d1d-r2-fc0901-mark-any-entry` |
| `control_f0902_crc_identity` (F-0902, S2) | `nread_l2.rs:160` `lemma_run`: two different relationships are never taken as one | 5 steps: relationships 1 and 2 with one checksum committed; the interpreter's answer lacks (1, 2) (not an L1 step) | `proofs-d1d-r2-f0902-crc-identity` |
| `control_f0908_run_unchecked` (F-0908, S3, intent-undecided) | `nread_l2.rs:158` `lemma_run`, `:168` `lemma_runlabels`: Run checks SELECT for (process, user) | 2 steps: user 3's SELECT revoked; process 5 (never checked) is answered (not an L1 step under FR-011) | `proofs-d1d-r2-f0908-run-unchecked` |
| `control_hd0902_shadow_swallows_native_error` (HD-0902, assumption) | `nread_l2.rs:178` `lemma_shadow`: a shadow answer was compared | 1 step: native raises in shadow mode; the SQL rows are returned uncompared (not an L1 step) | `proofs-d1d-r2-hd0902-shadow-swallows-native-error` |
| `control_f0906_gate_edge_index_only` (F-0906, S2) | `nread_l2.rs:170` `lemma_runlabels`: the gate opens only where ^KG("label") is kept | 2 steps (edge-only state): label (5, 7) written; the native label read answers none (not an L1 step) | `proofs-d1d-r2-f0906-gate-edge-index-only` |

Counts (verified / errors, each including its verified counterexample and excluding its family's witness): F-0701 and
F-C0701 115/3; F-C0702 and F-0908 116/2; every other control 117/1. Each control run took 1.91-2.10 s of wall time.
The F-C0901 control keeps the reviewed fresh class names so that it isolates the marking decision; with the as-built
names the same schedule also breaks (the live run b-09-f0901-collision). For's check that an "ok" entry names IVGC.P<h>
(Gen.cls:73) is not modelled (under R09-1 it becomes "the entry names the class it records").

Live or model reproductions of the same as-built decisions: b-07-fc0702-nested-rollback (F-C0702), b-07-f0701-race and
m07-bm25-as-built-* (F-0701), b-07-f0704 (F-0704), b-07-f0706 (F-C0701), b-07-f0705-f0707 (F-0705, F-0707),
b-07-f0702-f0703 (F-0702), b-08-live-f0801 and b-08-run-unit (F-0801), b-08-live-f0805 (F-0805),
b-08-live-storage-order (F-C0803), b-08-live-f0810 (F-0810), b-08-live-f0802/-f0816/-f0818 and m08-scope-as-built-*,
b-09-f0901-collision and m09-planc-as-built-* (F-0901, F-C0901), b-09-f0902-collision and m09-used-as-built (F-0902),
ver-priv-r3 (F-0908), intent-a-hd0902-shadow-native-exception (HD-0902), m09-gate-as-built (F-0906, model only). These
counterexamples are proved over the models.

## 9. Premises (named; none is an assumption inside a proof)

| Id | Premise | The pin |
|---|---|---|
| P-W1 | an Insert/Delete is one step (it holds the lock; a reader sees it whole) | not enforced: readers take no lock and read uncommitted globals (P-0002, HD-0903), so a search during an Insert can see part of it; not observed for BM25 |
| P-W2 | Build and Drop run with no caller transaction open, and none begins while a build runs | not enforced; not observed |
| P-W3 | the BM25 writer runs in the caller's server process, so its level nests in the caller's | **violated for `from_connect` engines**: `bm25_insert` runs on `_iris_obj()`, a dedicated Native API connection when the credentials are known (engine.py:1916-1945; F-0909 live shows the separate process for native reads); there the Insert is not nested at all and the caller's rollback keeps it (the L1 nesting rule fails the other way, not modelled). Holds for an engine built on a connection object (b-07-fc0702-nested-rollback) |
| P-W4 | no Upgrade, no schema-1 index, no lock timeout | modelling restriction |
| P-N1 | each namespace-level call is one step | **violated**: Build is not atomic (F-0701, live; `bmw` models it) |
| P-N2 | no Upgrade, no schema-1 index | modelling restriction |
| P-N3 | an index's documents are the nodes of its recorded graph; an index with no recorded graph is not dropped by an erasure | not enforced: bm25_insert takes any id; an index built before spec 230 records no graph and covered every graph (BM25Index.cls:608-611) |
| P-C1 | a write query is one atomic step | not enforced (other writers' statements interleave with the query's; dirty reads); not observed for the modelled shapes |
| P-C2 | no caller transaction around the query | modelling restriction |
| P-C3 | no multigraph mode | modelling restriction (keyed edges take another INSERT path) |
| P-C4 | one graph, one relationship type; MERGE rows are distinct pairs whose relationship does not exist | modelling restriction (as in the live check) |
| P-C5 | the engine's guard is the only strict-mode check that matters | **violated**: raw SQL and other clients are not guarded at all; IRIS only records the flag (Ledger.cls:360-375; HD-0801) |
| P-S1 | each read takes the route modelled (the shortcut's text match, an uncorrelated WITH-carried start) | modelling restriction |
| P-P1 | job mode, one namespace stamp, no DropAll while builds run | **violated**: DropAll does not wait for running builds (F-0905, live b-09-f0905-dropall-race); unknown mode values act as sync (F-0903, live) |
| P-P2 | Gen.For is one step | not enforced (it holds no lock); atomicity can hide interleavings, not add them |
| P-P3 | compiling shape s's lines gives code that answers interp(s, db) | assumed (the generator's correctness is not modelled) |
| P-P4 | an orphaned class is left in place | modelling choice (the remedy deletes it) |
| P-R1 | each read is one step | **violated**: a native walk reads the stores at moments spread over it and can see part of one transaction (live intent-a-hd0903-native-read-open-txn); HD-0903's working answer allows it, the model does not cover it |
| P-R2 | no out-of-band index drop under running engines | not enforced: the engine caches the index kind for its life (engine.py:704-723; HD-0901 working answer (2) calls it a premise violation) |
| P-R3 | a process's caller identity is its Native API session's user | assumed |

Intent status of the L1 rules (none is a maintainer decision unless marked): HD-0701 (assumption), HD-0703
(assumption), HD-0704 (supported), HD-0801 (assumption), FR-011 vs R280 (HD-0901: **intent-undecided**; F-0908's
control shows only the gap with FR-011), HD-0902 (assumption), HD-0903 (assumption, satisfied by the pin).

## Premises the pin violates

Five premises of these models are false at pin `3eaa79cf` by this audit's own evidence: P-W3 (a `from_connect`
engine's BM25 writes run in another process: source), P-N1 (Build is not atomic: F-0701, live), P-C5 (strict mode binds
only the engine's guard: HD-0801, source), P-P1 (DropAll races builds: F-0905, live; unknown modes act as sync: F-0903,
live) and P-R1 (a native walk reads stores at different moments: live). Five more are not enforced by the pin, with no
observed violation here: P-W1, P-W2, P-N3, P-C1, P-R2 (and P-P2). Every reviewed-design element R07-1..R07-6,
R08-1..R08-5 and R09-1..R09-6 is absent at the pin (section 7), and each control shows the corresponding as-built
decision violating the model's contract on a reachable run. Six L1 rules rest on working answers that are assumptions
and one (FR-011) on an intent-undecided question. So no safety result here transfers to the product. What transfers is
the negative: each as-built decision of section 8 breaks the contract on a reachable run of the model.

## 10. Cost (measured, `RESULTS.json`)

Baseline (r2): Verus 2.28 s, SMT 1.69 s, 3.72 M rlimit over 118 functions, wall 2.70 s, 0.47 GB peak.

| Module proof | Functions | SMT ms | rlimit | Largest function | Largest proof lemma |
|---|---|---|---|---|---|
| 07 writers (`bmw_l1`, `bmw_l2`, `bmw_runs`, `witness_bmw`) | 23 | 674 | 1.38 M | `witness_bmw::witness_bmw` 0.66 M | `bmw_l2::lemma_step` 0.10 M |
| 07 namespace (`bmn_*`, `witness_bmn`) | 25 | 216 | 0.50 M | `witness_bmn::witness_bmn` 0.17 M | `bmn_l1::lemma_l1_safe` 0.04 M |
| 08 write queries (`cyw_*`, `witness_cyw`) | 21 | 230 | 0.55 M | `witness_cyw::witness_cyw` 0.19 M | `cyw_l2::lemma_exec` 0.06 M |
| 08 read scope (`cys_*`, `witness_cys`) | 12 | 79 | 0.19 M | `witness_cys::witness_cys` 0.06 M | `cys_l2::theorem_raw_executions_refine` 0.03 M |
| 09 plan cache (`planc_*`, `witness_planc`) | 18 | 221 | 0.50 M | `witness_planc::witness_planc` 0.15 M | `planc_l2::lemma_for` 0.07 M |
| 09 native read (`nread_*`, `witness_nread`) | 19 | 259 | 0.60 M | `witness_nread::witness_nread` 0.27 M | `nread_l2::lemma_step` 0.04 M |

No rlimit was raised and no proof looped; nothing was partitioned. Each decisive round's 22 runs took 45.6 s of Verus
wall time in total (two rounds, plus one scratch run per round). Development needed 35 short Verus runs (the first
also verified `actors` once in this lane's new target directory): one syntax fix (`matches` with `&&` needs
parentheses), one trait import, two explicit witnesses for existentials in counterexamples (`cx_fc0701`, `cx_f0818`),
one equality hint for the ledger-meta step, and the reachability additions of round r2. Comment-only line citations
were corrected before round r1.

## 11. Trust inventory

This crate has no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two); the scan of `actors` (`c03f9fa`) finds none either. vstd is Verus's
trusted base (finite `Set`/`Map`, `ISet` with their axioms). The gate status is **declared empty** (`RESULTS.json`
`trust_inventory`). Verus prints three `inconsistent_fields` warnings (enum variants sharing a field name with another
type: `CSL1`, `NRL1`, `NRL2`); they disable `->field` syntax only and are not errors.

## 12. What is NOT proved (open obligations)

- **No proof connects the Python or ObjectScript to these L2 machines** (D-2, D-3). The six
  `theorem_raw_executions_refine` are the plug-in points for trace conformance; no journal trace is replayed through them.
- **The families are not composed.** `bmw` and `bmn` share ^BM25Idx; `cyw` and `cys` share the rows; `planc` and
  `nread` share the native read. Their joint behaviour is by inspection; no joint invariant is proved.
- **Interleavings inside a call** (P-W1, P-N1 beyond `bmw`'s build, P-C1, P-P2, P-R1) are not modelled; P-W3's other
  direction (a `from_connect` engine's Insert not nested) is not modelled.
- Module 07 items not modelled: ranking and fusion (F-0709, F-0710, F-C0703, HD-0702), staleness on node text changes
  (F-0703), TextSearchEngine (F-0711, HD-0705), spec drift (F-0708), Upgrade, the df counters separately from N/totalLen,
  the embedded-mode registry walk.
- Module 08 items not modelled: the Cypher translation itself (only three write shapes and three read routes, each by
  its effect), F-0803/F-0804/F-0806/F-0807/F-0808/F-0809/F-0811-F-0815/F-0817/F-0819-F-0825, F-C0801 (^NKG counters,
  intent-undecided), F-C0802, ledger changeset recording, read-only mode, multigraph mode.
- Module 09 items not modelled: F-0903 (mode decoding), F-0904, F-0905 (DropAll race: a premise here), F-0907 (shadow
  ties), HD-0901's index half (P-R2), HD-0904 (a compiled class failing at run time), plan generation and the
  generator's correctness (P-P3), parallel workers.
- HD-0701, HD-0703, HD-0801, HD-0902, HD-0903 working answers are assumptions; FR-011 vs R280 (HD-0901) is
  intent-undecided; the remedies of the findings are proposals, not maintainer decisions.
- No progress or liveness property (two colliding plan shapes taking turns forever, m09-planc-as-built-collide-progress,
  is not addressed).
- The L1s are new contracts written for this lane; their correspondence to the ontology statements (TXT-*, CYP-*,
  NAT-*) and to the explorer models' invariants is by inspection.

## Debt accounting (for `PROOF-DEBT.md` D-1)

Paid, model-level only, by `proofs-d1d-r2-baseline` and the 21 `proofs-d1d-r2-*` control runs (round r1's 22 records
stay as superseded evidence): the §3.3 L1, L2, refinement and
controls items for module 07 (one index's writers with the caller's transaction; the namespace's indexes, stopword node,
graph scope and erasure), module 08 (three Cypher write shapes under the ledger guard; three read routes' graph scope)
and module 09 (the compiled-plan cache; a native read's identity, privilege check, label gate and shadow mode), each as
modelled and with the abstractions stated. Still owed under D-1: modules 00-02, 10 and 15-17, and the unmodelled parts
of 07-09 listed in section 12. This lane does not edit `PROOF-DEBT.md` or `STATUS.md` (outside its write scope); the
orchestrator moves the row. The crate's `Cargo.lock` is a copy of `proofs-d1c`'s with only its root package name changed.
