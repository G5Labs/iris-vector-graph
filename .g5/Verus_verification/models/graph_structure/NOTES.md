<!-- markdownlint-disable MD013 -->

# graph_structure — Verus model notes (worker B-structure; round 1 repaired 2026-11-14)

Product baseline `3eaa79cf` (read-only; no product file changed). Intent leads: `.g5/uplift/ivg-verus-initial/intent/graph-structure.md`. Review: `.g5/uplift/ivg-verus-initial/review/round1-data.md` (R1-4, R1-8, R1-10, R1-13 addressed below).

- Root `graph_structure.rs` (one file, four sections); `model.json` has 22 controls. Toolchain: Verus `0.2026.10.04.426d8b0`, z3 4.16.0, bundled vstd only (`../../SOURCE.json`), 4 threads.
- Run: `source experiment/g5-verus/environment.sh; VERUS_RUN_THREADS=4 python3 .g5/Verus_verification/run_verus.py prove|controls .g5/Verus_verification/models/graph_structure`.
- **Current results.** Prove PASS, 67 verified, 0 errors (`results/graph_structure/20261114T000451Z-prove/receipt.json`). Controls: 22 of 22 EXPECTED_FAIL (`results/graph_structure/20261114T0005*–0008*-control-*/receipt.json`).
- **Superseded receipts (kept).** `receipts/graph_structure/20261113T*`: round 0, 56 verified, 17 controls; its first controls run had 2 FAIL_ELSEWHERE, see O3. The round-0 file is `$RUN_DIR/agents/B-structure/graph_structure.round0.rs`.
- **Native results** (raw copies in `.g5/Verus_verification/receipts/native/graph_structure_*.json`; product baseline 3eaa79cf, adjacency index `functional`):

| Probe | Verdict | Decisive observation |
|---|---|---|
| `graph_structure_parallel_delete_rel.py` | OBSERVED_DEFECT (default and named graph) | Before: 2 rows, children [0,1], `#`=2, degree 2. After the ledger delete_rel: 1 row, no leaf, no `in`, Degree 0, Count 0. Cypher MATCH still returns the neighbour (SQL). verify_graph reports `missing` 1. |
| `graph_structure_algo_cache_rollback.py` | OBSERVED_DEFECT | Baseline WCC: c alone (token 8340). Dirty: c joined (8341, stored). After the rollback: 0 rows c→a, token 8341, and a fresh engine's WCC is a cache **hit** with c joined. |
| `graph_structure_keys.py` | OBSERVED_DEFECT (K4); K1, K2, K3, K5 OBSERVED_AS_EXPECTED | K4: `create_edge` with "g5k" and "g5k"+NUL both return True and write two rows (graph_id 'g5k', 'g5k\x00') with one ^KG entry. `delete_edge(graph="g5k")` leaves the 'g5k\x00' row with no ^KG entry, and `verify_graph("g5k")` reports ok with 0 SQL edges. P-CTRL observed: 0x01, 0x1F, 0x7F, 0x80, 0x85, 0x9F refused; 0xA0 accepted. |
| `graph_structure_degree_aba.py` | INCONCLUSIVE | 3,383 writer rounds, but **reader_calls = 0**: reader connections failed with "Unable to allocate a license" (Community). The race could not occur in that run. The probe now says so explicitly and defaults to 3 readers (`G5_PROBE_READERS`). |

Authority tags: **(H)** human requirement / answered clarification, **(D)** accepted decision, **(O)** observed implementation only.

---

## O1 — Graph keys (§1)

**Governing sources.**
- CONTEXT.md:27-36 (D): Graph and Named Graph.
- CONTEXT.md:50-58 (D): Graph Key — "derived from the name, never converted"; "a wrong key reads nothing, never another graph's data".
- ADR-0001:23-24 (D): the default graph's key is integer 0.
- ADR-0003:10-27, 42-48, 66-74 (D): two derivations; "0" and `$Char(1)` refused.
- GraphKey.cls:23-37 and _validate.py:31-32 (O): NUL is a transport artifact and is the only character removed.

**L1.**
- (a) **Normalization (made explicit, R1-4).** Two names denote the same graph iff they differ only by NUL characters (`nul_free`, `l1_same_graph`). This is defined with vstd `Seq::filter`, independently of the transcription.
- (b) Each store's key is a function of the graph and injective on graphs (relative to (a)).
- (c) The default graph's key differs from every named graph's key in both stores.
- (d) "0" and every control character are refused before any write.
- (e) A key of one store used on the other matches nothing (default graph) or the same named graph.
- (f) **(R1-4)** Every store spells a graph by the same canonical name: each writer's SQL `graph_id` is `ForName(name)` (`binding_ok`).

**L2 → L3.**

| Model | Product |
|---|---|
| `canonical` / `strip_nul` | `GraphKey.Canonical`, GraphKey.cls:82-85 |
| `valid` | `Validate`, 38-48 |
| `for_index` | `ForIndex`, 51-56 |
| `for_ledger` | `ForLedger`, 72-77 |
| `for_name` | `ForName`, 65-69 |
| `sub_of`, `int_zero` | IRIS subscript canonicalization (ADR-0003:42-48) |
| `py_valid` | _validate.py:19-53 |
| `sql_gid_create_edge` | nodes_edges.py:1197 (validate) and 1213 (`gid = graph or ""`, raw); the row's callback keys ^KG by `ForIndex(graph_id)` (Adjacency.cls:482) |
| `sql_gid_repaired` | proposal: bind `ForName(name)`, as `Graph.KG.Eraser` does |

**Proved.**
- `lemma_canonical_is_nul_free`: the transcription's normalization is exactly L1(a).
- `theorem_key_is_function_of_graph`, `theorem_nul_is_stripped`, `theorem_refusals`.
- `theorem_index_key_injective`, `theorem_ledger_key_injective`, `theorem_name_injective`: all three now conclude `l1_same_graph`.
- `theorem_default_key_is_unique`, `theorem_cross_store_key_reads_nothing_foreign` (concludes `l1_same_graph`), `theorem_default_keys_never_cross`.
- `theorem_control_names_never_merge`: a concrete theorem, independent of the lemma.
- `theorem_repaired_binding_one_graph_in_every_store`: with the `ForName` binding, two names share an index key iff they share a SQL graph.

**Witnesses.**
- `witness_raw_sql_name_splits_one_index_graph` (R1-4/Q5). Under create_edge's raw binding, "g" and "g"+NUL are one index graph but two SQL graphs, and `binding_ok` fails. **Observed natively (K4).**
- `witness_python_mirror_admits_c1_control` (Q4). The Python validator admits U+0085, which GraphKey refuses. **Native K3:** Python passed the name and IRIS refused it inside the INSERT (SQLCODE -400 "graph name contains a control character"), with nothing written. The two validators still disagree. Only the late refusal is benign: the caller gets an SQL error rather than a ValueError.

**Premises.**
- P-CTRL: now **observed natively** (table above). The proofs need only `$Char(0)` and `$Char(1)` in the class and "0" outside it.
- P-CANON: canonical numeric text is unique; `other_canonical_number` is uninterpreted.

**Controls.**
- `key-no-zero-refusal`, `key-no-control-refusal`, `key-no-nul-strip`, `ledger-key-skips-canonical`.
- **`canonical-strips-controls`** (review Check A, R1-4). The normalization strips every control character, so 'a'+`$Char(1)` would be merged with 'a' instead of refused. It now fails in `lemma_canonical_is_nul_free` and `theorem_control_names_never_merge`.
  - The injectivity theorems consume that lemma's contract, so modular verification attributes the failure to the lemma. My scratch replay (`$RUN_DIR/agents/B-structure/checkA_mine.log`) gives 56 verified, 3 errors.
- **`repaired-binding-is-raw`** (R1-4).

All six are EXPECTED_FAIL.

**Not represented.** SQL's NULL vs '' vs `$Char(0)` spelling of the default graph (each SQL site uses COALESCE); the inverse key→name sites; legacy rows already named "0"; `^NKG`; the other writers' SQL bindings: `create_node` (nodes_edges.py:1019, unvalidated) and the ledger's `OpCreateRel` (LedgerApply.cls:494, raw tuple graph). By code reading, both have create_edge's raw binding; neither was modeled or probed.

**Findings (O1).**
- **R1-4 / Q5, bug, CONFIRMED natively (K4), Medium.**
  - Expected: L1(f) (CONTEXT.md:27-36; ADR-0003; spec 252 FR-016 "no adjacency without a row").
  - Observed: create_edge validates and canonicalizes the ^KG key but binds the raw name to SQL. A NUL-padded name therefore makes a second SQL graph that shares the first graph's index entry. Deleting the canonical graph's row kills the entry the padded row still needs.
  - `verify_graph` cannot see the orphan: its SQL predicate is the canonical name (GraphVerify.cls:69).
  - Repair (proved): bind `ForName(name)` in every writer.
- Q4: open question; the two validators disagree on U+0080–U+009F. Native result: refused late, with nothing written.
- Doc drift: ADR-0003:14 says `$ZStrip(graphId,"*C")` (strip), while the code refuses. Check A shows that the stripping reading would merge distinct names.

---

## O3 — Degree served from the generation-validated cache (§2)

**Governing sources.** ADR-0010:12-15 (D); ADR-0012:12-17, 23-26 (D); CONTEXT.md:103-107 (D); spec 248 spec.md:76-77 (D, draft) and Adj.cls:46-48 (O), which claim the post-store re-read covers erase.

**L1.** A cached degree served by `Degree`/`Cached` equals what a recount answers at that moment (`theorem_served_equals_recount`).

**L2 → L3** (one graph, one source, the all-predicate key):
- `Start`/`served`: Adj.cls:63-67 and 93-106.
- `Probe`: 68-72. `Count`: 73 (and 110-133). `Check`: 75. `Set`: 77. `ReRead`: 78-80.
- `Write`: WriterLock Adjacency.cls:61-73; Put 86-93; Remove 150-158; PutKeyed 233-262; RemoveKeyed 291-315; RowUpdate 523-530.
- `Commit`/`Rollback`: Txn.cls:49-58; Eraser.cls:260, 459, 630; Ledger.cls:204-206, 268, 279. Journaled Set and Kill are restored; `$Increment` stays.
- **`KillCommitted` (route list completed, R1-8/R1-10).** Every path below kills gen:
  - `RemoveSource` (Adjacency.cls:373-377), reached from delete_node (Eraser.EraseIdSet 547) and from the purge's default `retire_bare_nodes=True` (Eraser.ForgetNodes 1320-1327; temporal.py:623);
  - `RemoveGraph` from erase_graph (Eraser.cls:234; Adjacency.cls:435-440);
  - `RemoveAll` from sync()/BuildKG (TraversalBuild.cls:68) and from `%BuildIndices`' PurgeIndex (AdjIndex.cls:29-32; Adjacency.cls:459-465);
  - the non-indexed restore (snapshot.py:1688-1691).

  The next `$Increment` restarts gen at 1.
- `KillInTx`: RemoveSource inside EraseIdSet's TSTART that rolls back.

**Proved.**
- `theorem_as_built_cache_sound` holds under P-QUIET, for any number of readers and writers, commit and rollback, lockless writers and committed kills. Supporting lemmas: `lemma_dinit` and the per-step lemmas.
- `theorem_repaired_cache_sound` (epoch repair) and **`theorem_kill_bump_cache_sound`** (review Check B repair, see below): both cover committed kills with no P-QUIET.

**Witnesses** (the product variant unless noted).
- `witness_aba_delete_and_recreate_serves_stale_degree` (route 1). R reads gen 2 and counts 2. delete_node, create_edge and delete_edge then commit and bring gen back to 2. R stores (2, 2) while s has 0 entries.
- **`witness_gen0_erase_alone_serves_stale_degree`** (review Check B2, R1-10; **non-indexed namespaces only**). Gen is absent after a non-indexed BuildKG (FillEdge, Adjacency.cls:826-830) or restore. One committed erase leaves gen 0, so R stores (0, 2) and the deleted, re-created or retired node reads 2.
- `witness_rolled_back_kill_restores_stale_entry` (route 2): model only, reachability open.
- Repairs refusing the routes:
  - route 1: `witness_repair_refuses_the_aba_store` (epoch) and `witness_kill_bump_refuses_the_aba_store` (bump);
  - gen 0: `witness_gen0_epoch_repair_refuses` and `witness_gen0_kill_bump_refuses`;
  - route 2: `witness_repair_ignores_restored_entry` (epoch) and `witness_kill_bump_ignores_restored_entry` (bump).
- `witness_quiet_premise_excludes_the_aba`, `witness_without_probe_rollback_poisons`, `witness_probe_refuses_uncommitted_count`, `witness_quiet_reader_fills_and_hits` (valid outcome), `witness_s1_set_generation_is_undone_by_rollback`.

**Premises.**
- P-QUIET: no erase of s while a Degree/WarmFill call on s is in flight. **Not established by any component.** The review's Check B confirms that the restart at 0 is the sole cause.
- P-ROLLBACK-KILL: excluded from the proved variants.
- P-DEFER and P-JOURNAL: IRIS behaviour; repo measurements support P-JOURNAL (ADR-0010 Context).
- P-GRAIN: a writer's out write and its gen bump are treated as one step (justified in round 0: the hit path reads only gen and degc).

**Not represented.** A reader inside its own writer's transaction; a committed kill while another writer has uncommitted writes on s; `WarmFill`/`WarmAll`/`AllWarm`/`degw`. The reviewer read these and found them safe because `__version` is never killed. Also not represented: per-predicate keys and weights.

**Controls.** `degree-no-probe`, `degree-no-nolock-check`, `writer-no-gen-bump`, `as-built-without-quiet-premise`, `repair-epoch-off`, `repair-kill-keeps-epoch`, `repair-kill-bumps-off`, `kill-bump-restarts-gen`: all EXPECTED_FAIL.
- `as-built-without-quiet-premise` now fails at a semantic step, `!same(s2, rd, v)` in `lemma_killcommitted`. In round 0 it failed at a proof-structure assertion.
- `repair-epoch-off` and `repair-kill-bumps-off` make the repaired theorems fail at their scope precondition `covered(v)`. Their semantic failures are in the repair witnesses.
- Round-0 attempt kept: `degree-no-gen-check` was FAIL_ELSEWHERE. Removing the gen test at Adj.cls:75 or the re-read at 78-80 is an **equivalent mutant with respect to L1** in every proved variant (`$RUN_DIR/agents/B-structure/equiv/*.log`). That control was dropped for that reason.

**Findings (O3).**
- **R1-8 / F2, bug, CONFIRMED-BY-PROOF-OF-MODEL; product status SUSPECTED, "not natively reproducible without a stall hook".**
  - Expected: ADR-0012:12-17; spec 248:76-77.
  - Observed: every erase path above kills gen and writers restart it at 1. The store test and the re-read compare equality only.
  - The window is one Degree call's count. For a small node that takes microseconds, against milliseconds for the writer transactions, so only preemption can hit it.
  - Native: INCONCLUSIVE, and the 2026-11-13 run had no reader call at all (license). It is no evidence either way.
  - The gen-absent route needs a non-indexed namespace. GraphVerify's degc check (GraphVerify.cls:131-152) would report the resulting state as "count" drift.
- **Route 2** (rolled-back erase restores an old gen and entry): reachability OPEN. The FK `fk_edges_source` (schema.py:42) and the erase's row lock probably block the concurrent writer.
- **Two repairs, both proved; the choice is for the ADR-0012 owner.**
  - **(A) Bump instead of kill** (review Check B: `$Increment(^KG("gen",g,s))` and Kill degc on erase). It keeps the entry format and the reader code, and it also closes route 2, because `$Increment` is not rolled back. Costs:
    - it leaves a gen counter behind for every erased node (Adjacency.cls:344-347 says "a node that is gone leaves no residue");
    - RemoveGraph and RemoveAll must iterate sources instead of issuing one Kill.
  - **(B) Epoch stamp.** A never-killed counter is `$Increment`ed by every erase and stored in each entry. Erase keeps killing gen (no residue per node), but the entry format and the reader change.
  - **Not a repair:** the intent notes' S1, `Set gen = $Increment(token)` (`witness_s1_set_generation_is_undone_by_rollback`).
- The pre-store gen test and the re-read do not close the window documented for them. Spec 248:76-77 and Adj.cls:46-48 overstate them.

---

## O5 — Parallel edges and the ledger's delete_rel (§3)

**Governing sources.** Spec 234 Clarifications 2026-09-26 (H, spec.md:41-53); spec 234 FR-003/FR-004 (D, 221-233); spec 252 FR-001/FR-003/FR-016 (D, 106-110, 132); CONTEXT.md:83-95, 103-107 (D). Spec 234 status line: the ledger surface is "not done" and no refusal is specified.

**L1.** In a multigraph-mode graph, the triple's adjacency is `layout(rows)`: nothing, a bare leaf, or leaf + children + `#` = n. Degree contributes |rows|. Deleting one relationship by any path leaves `layout(rows − {e})`.

**Scope qualifier (R1-13).** "By any path" holds only **with the adjacency index declared**: `Adjacency.Indexed()`, i.e. `idx_edges_adj` is the functional `Graph.KG.AdjIndex` (Adjacency.cls:540-557). Without it, only the engine's own writers keep ^KG, and a raw SQL or Cypher write leaves it stale by design (CONTEXT.md:93-95). The model makes this explicit:
- `theorem_declared_index_sql_delete_keeps_layout`: with the index, a raw SQL delete keeps the layout;
- `witness_undeclared_index_sql_delete_leaves_entry`: without it, the entry stays;
- the control `undeclared-index-treated-as-declared`.

The repaired delete_rel theorem covers both namespace kinds. The native probe ran on an indexed namespace.

**L2 → L3.**
- `put`/`remove`: Adjacency.cls:87-88 and 152-153.
- `put_keyed`: 210-269. `remove_keyed`: 275-321.
- `row_put`/`row_remove`: 477-501 via AdjIndex.cls:12-26.
- `contrib`: Adj.cls:114-122.
- `delete_rel_as_built`: LedgerApply.cls:652-693 (678 DELETE by %ID; 688-689 `Remove` when the leaf exists; FindEdge 144-157).
- `delete_rel_repaired`: proposal; compare OpCreateRel's `Indexed()` guard at 508.

**Proved (index declared unless stated).** `lemma_row_put_keeps_layout`, `lemma_row_remove_keeps_layout`, `theorem_index_delete_keeps_parallel_edges`, `theorem_declared_index_sql_delete_keeps_layout`, and `theorem_repaired_delete_rel_keeps_layout` (both namespace kinds).

**Witnesses.** `witness_ledger_delete_rel_drops_survivor_indexed`, `witness_ledger_delete_rel_drops_survivors_non_indexed`, `witness_ledger_delete_rel_single_edge_is_right` (valid outcome), `witness_undeclared_index_sql_delete_leaves_entry`.

**Not represented.** Weights (FR-004's leaf value, F11); the `in` mirror; concurrent keyed writers (F4); mode races (F6); restore order (F5).

**Controls.** `row-remove-ignores-mode` (attributed to the lemma whose contract the theorem consumes), `remove-keyed-no-collapse`, `put-keyed-ignores-other-rows`, `repaired-delete-rel-keeps-line-689`, `as-built-delete-rel-without-line-689` (attribution: line 689 alone), `undeclared-index-treated-as-declared`: all EXPECTED_FAIL.

**Findings (O5).**
- **F3, bug, CONFIRMED natively (default and named graph, index declared), High within multigraph use.**
  - Expected: spec 252 FR-001/FR-016; spec 234 FR-004; CONTEXT.md:90-95.
  - Observed: LedgerApply.cls:689 removes the survivor's bare leaf after the index has collapsed the triple. The survivor row is left without adjacency and Degree reads 0, while Cypher MATCH (SQL) still answers the neighbour.
  - In a non-indexed namespace, the same line kills every parallel entry (model witness only).
  - Reachable with the ledger in non-strict mode on a multigraph graph.
  - Repair (proved): skip 689 when `Indexed()`; otherwise call `RemoveKeyed` with the row's ekey.
- **F7, CONFIRMED natively.** `verify_graph` on a graph whose only triple has two parallel rows reports `missing` 1 (`out` and `in`) before any delete: a false drift report (GraphVerify.cls:65-104).

---

## O4 — Algorithm-cache token rule (§4)

**Governing sources.** CONTEXT.md:109-119 (D); ADR-0012:23-26 (D); AlgoCache.cls:1-13 (O); the token audit's fix applied to BuildKG only (TraversalBuild.cls:160-162).

**L1.** A cached answer equals the answer over the content readable now.

**Scope (R1-13).** "Every write moves the token" holds for every row write only with the index declared (spec 252 FR-004). Without it, a raw SQL or Cypher write moves neither ^KG nor the token, and the cache is stale by design.

**L2 → L3.** `Miss` = AlgoCache.cls:27-36; `Store` = 46-51 (iris_sql_store.py:958-981); `Add` = a write's `$Increment(^KG("__version"))` (Adjacency.cls:92); `Rollback` = Txn.Undo / the Eraser and Ledger catches, none of which bumps.

**Proved.** `theorem_repaired_algo_cache_sound` (repair: bump after every rollback), with `lemma_a_init`.

**Witnesses.** `witness_rolled_back_write_poisons_algo_cache`, `witness_bump_after_rollback_refuses_the_poison`.

**Controls.** `algo-repair-off`, `algo-write-no-token-bump`: both EXPECTED_FAIL.

**Finding F1, bug, CONFIRMED natively (WCC, two connections, index declared).** The answer computed over a rolled-back edge was stored under token 8341. After the rollback the token was still 8341, and a fresh engine's WCC was a cache hit with c joined while 0 rows of c→a existed. The repair's premise is that every rollback path bumps the token; a rollback IRIS performs for a dead process does not, so the stronger alternative is the ADR-0012 lock probe (intent S2, not modeled).

---

## Open questions

- Q-F2-2: Can s's out entries be written while an erase of s is uncommitted (FK and row locks)? This decides whether route 2 is a product defect. Both repairs refuse it in the model.
- Q4: one validator character set owned by GraphKey (native: Python admits U+0085, and IRIS refuses it late).
- R1-8 repair choice, (A) bump or (B) epoch: residue versus entry format.
- Should the ledger refuse delete_rel on a multigraph triple until spec 234 FR-013 lands?

## Trust inventory

- `uninterp spec fn other_canonical_number`: no axiom.
- No `assume`, `admit`, `external_body` or `assume_specification`. The only grep hits are the word "admits" in `witness_python_mirror_admits_c1_control`.
- vstd items used: `Seq::filter` (revealed) and `set_lib::lemma_set_empty_equivalency_len`. In this vstd every `Set` is finite.
- IRIS premises: P-CTRL (observed natively), P-CANON, P-DEFER, P-JOURNAL, P-GRAIN.
- Model premises: P-QUIET, P-ROLLBACK-KILL. Scope switches: `covered(v)`, `kill_in_tx`, and the `indexed` parameter of §3.
- This is a hand transcription; the product bodies are not verified.

## Probes

| Script | Status |
|---|---|
| `graph_structure_parallel_delete_rel.py` | run: OBSERVED_DEFECT (F3; F7 also observed) |
| `graph_structure_algo_cache_rollback.py` | run: OBSERVED_DEFECT (F1) |
| `graph_structure_keys.py` | run: OBSERVED_DEFECT for K4; K1/K2/K3/K5 as expected; P-CTRL observed |
| `graph_structure_degree_aba.py` | run: INCONCLUSIVE, 0 reader calls (license). Revised: reports "no reader call ran" explicitly and defaults to 3 readers. A rerun is needed for any evidence, and even then a clean result stays INCONCLUSIVE. |
