# PROOFS-ENV: the IRIS environment contract as a Verus specification, linked to the participant contracts (proof debt D-7)

Lane proofs-env, product pin `3eaa79cf`. Evidence grade: **proved** for the statements below (Verus
`0.2026.10.04.426d8b0`, `--no-cheating`, empty trust inventory, `proofs-env-baseline`: 305 verified, 0 errors), each a
statement about a **model**: the Verus specification of the IRIS 2026.1 contract and the proof crates' premises as
stated there. Nothing here says the product satisfies a premise: whether the product follows the discipline the
head-lock theorems assume is code correspondence (D-3/D-4), and where the pin violates it the violation is the pin's.
The specification is linked mechanically to the executable contract (`iris-contract` r6, contract-2) by an exec model
verified against it and run on every recorded round (no IRIS): 0 disagreements, 0 observations outside.

Before this lane, D-7 read: "the link from the proof crates' participant contracts to the contract's clauses is by
inspection". Now: every proof-premise condition of `reflection/CLOSURE.md` (72) and 7 PROOFS.md premises it does not
list have a checked verdict (`premise_map.json`, `proofs-env-premise-map`): of the 79 rows, 12 are proved, 10 proved in
part, 8 proved under the product's discipline, 3 proved false from the contract, 1 proved permitted-not-implied, 9 are
outside the contract and 36 are progress premises the contract cannot imply (closure rows only: 9 / 10 / 5 / 3 / 0 / 9
/ 36).

## 1. The specification (`src/spec.rs`)

One step function, `step(sem, u, s, p, op, choice) -> (State, Obs)`, over a finite universe of the cells a case names,
mirroring `iris-contract/src/lib.rs` (`Engine::step`) clause for clause; `sem` carries the contract's clause switches
(`clauses::contract_sem()` is the validated contract). The **permitted-outcome structure** is kept: `outcomes(sem, u,
s, p, op)` has two elements exactly at the contract's Freedom (an INSERT of a key whose row another open transaction
deleted: it waits, or proceeds under a new row id), one otherwise; `permitted(sem, u, case, obs, finals)` is the set of
outcomes over every choice sequence (`run`).

| Contract clause (CONTRACT.md) | In the specification |
|---|---|
| E-GLOBALS (SET, KILL subtree, `$GET`, `$DATA`) | `write`, `kill_from` (logged inside a transaction), `data_of` |
| E-NEST, E-PARTIAL (TSTART / TCOMMIT / TROLLBACK 1 / TROLLBACK) | one flat undo log with a mark per level: `tstart`, `commit_top` (the inner level joins its parent), `undo_top` (the top level only), `rollback_n`, `txn_end` |
| E-SQL-START, E-SQL-END, E-DRV, E-AUTOCOMMIT | `SqlStart` (nothing when a level is open), `end_levels` (SQL COMMIT / ROLLBACK end one level; driver `rollback()` every level), `SetAutocommit` (on commits one level) |
| S-1 (contract-2: Txn_Begin / Txn_End / Txn_Undo) | `SqlTxnBegin / End / Undo` |
| E-INCR | `$INCREMENT` writes without logging |
| E-PPG | process-private globals, not rolled back |
| E-VIS (READ UNCOMMITTED for globals and SQL) | `Get`, `Select` read the current globals and rows |
| E-ROLLBACK-OTHER (value-based rollback) | `restore1`: a cell is restored only while it still holds the value this transaction wrote |
| E-LOCK-DEFER, -LIFE, -NAMES, -MODES, -COUNT, -NONINC, -WAIT | `Hold {e, s, de, ds}` per name; `conflicts` (hierarchical names, shared compatible), `acquire` (incremental), `release` (deferred inside a transaction unless immediate), `release_all`, `LockOnly`, `Await` |
| E-ROWLOCK (insert / update / delete, waits, autocommit holds nothing) | a row-lock flag per row cell, held to the outermost end; `blocked` (UPDATE / DELETE wait for a visible row another live process holds) |
| E-UNIQUE | INSERT of a visible key fails at once, -119 |
| Freedom | `freedom_cond`, `freedom_step` (two worlds) |
| E-STOP | `stop`: every level rolled back, every lock released, dead |
| X-STMT's autocommit-off statement rules (on the DML path) | `failed_stmt`, `stmt_begin`, `stmt_end` |

Outside the Verus subset (counted, never compared): the r6 extension clauses X-FX, X-NOINDEX, X-DDL, X-NULL, X-STMT's
INSERT ... SELECT, X-ORDER, X-STAR, X-TLEVEL-SQL, X-VEC, X-ZSTRIP; contract-2's embedded SQL (E-1) and X2 clauses.
Representation choices (equivalent for the subset, checked by the differential): rows are cells of their table, one per
key (a unique-index entry exists exactly when its row does in the subset); the new row of the Freedom's proceeding
world holds no lock on the key (the contract's `k'new` lock, which no operation of the subset consults); arithmetic
beyond the machine types answers `Err(Overflow)` (none in the recorded rounds).

## 2. The mechanical link (`src/exec.rs`, `harness/`)

`e_step` and `e_run` compute one permitted outcome per choice; each is verified equal to `step` / `run` through views
(the 74 functions of `exec.rs`; 299 functions in all, 305 verified items). The harness (unverified test code: JSON, interning, rendering)
enumerates choice sequences depth-first, so it computes the Verus model's permitted set of every case, and compares it
with `iris-contract permitted` (r6 binary for r2, r4, r5, r6; contract-2's binary for its rounds and its regression of
r2 / r6), built from the unchanged sources into `$RUN_DIR/target/proofs-env-contract-*`.

| Round | Contract binary | Cases | In the Verus subset | Agree | Observations | Outside the Verus model | Freedom cases |
|---|---|---|---|---|---|---|---|
| r6 (VALIDATED_ROUND) | r6 | 516 | 295 | 295 | 295 | 0 | 1 |
| r2 | r6 | 283 | 283 | 283 | 283 | 0 | 1 |
| r4 | r6 | 514 | 296 | 296 | 296 | 0 | 1 |
| r5 | r6 | 515 | 293 | 293 | 293 | 0 | 1 |
| contract-2 e1-r1 | contract-2 | 67 | 0 | 0 | 0 | 0 | 0 |
| contract-2 e1-r2 | contract-2 | 54 | 13 | 13 | 13 | 0 | 0 |
| contract-2 x2-r1 | contract-2 | 190 | 6 | 6 | 6 | 0 | 0 |
| regression r6 | contract-2 | 516 | 295 | 295 | 295 | 0 | 1 |
| regression r2 | contract-2 | 283 | 283 | 283 | 283 | 0 | 1 |
| estop-gap (`env-estop-gap`, added in `proofs-env-differential-r2`) | r6 | 3 | 3 | 3 | 3 | 0 | 0 |
| dml-single (`env-dml-single`, added in `proofs-env-differential-r3`) | r6 | 2 | 2 | 2 | 2 | 0 | 0 |

(r3 is not used: its two outside outcomes were a retired driver misclassification, CONTRACT.md.) Every Freedom case
observed the waiting branch (`row-insert-after-uncommitted-delete`). The largest permitted set has 2 outcomes.

**Mutants of the Verus model** (`harness/src/main.rs`: 23 readings of the contract's own mutants that fall in the
subset, 6 seeded for the Verus model, 1 probe): **all 29 gating mutants are killed** by the recorded observations
(`proofs-env-mutants-r3`, pass). The first run (`proofs-env-mutants`) killed 26, the second (`proofs-env-mutants-r2`,
with estop-gap) 27. The probe `freedom-waits-only` (not gating) is alive as expected: the Freedom's proceeding branch
was never observed.

Killed since the second run: `failed-dml-opens-nothing` and `empty-dml-opens-txn`. In rounds r2-r6 the contract killed
them only through `autocommit-off-failed-dml` and random statement cases, all with INSERT ... SELECT (outside the Verus
subset). The orchestrator's round `env-dml-single` (AUDITENV, the contract's own driver, 0 outside the contract) has
the single-row versions: with autocommit off, a DELETE and an UPDATE that find no row leave `$TLEVEL` 0
(`autocommit-off-empty-dml-only`), a failing single-row INSERT opens the transaction
(`autocommit-off-failed-dml-single-row`). Both cases are in the Verus subset, agree with the contract and kill both
mutants.

Killed since the first run: `stop-rolls-back-top-level-only` (seeded). In rounds r2-r6 and contract-2 no case told "a
stop rolls back every level" apart from "the top level only" (`stop-nested-levels` commits its inner level before the
stop). This lane reported the gap; the orchestrator ran round `env-estop-gap` (AUDITENV, the contract's own driver: three
stops at `$TLEVEL` 2 without any commit: writes in both levels, outer only, an outer-level row INSERT): every level
rolled back, 0 outside the contract. All three cases are in the Verus subset, agree with the contract, and kill the
mutant (and `stop-commits`). P-0001, and P-C01 / P-D9-1 for a ledger commit nested in a caller's transaction (the 4.7.0
nesting, Ledger.cls:390-396), now rest on an observation of the every-level reading, not only on the clause's wording.

## 3. A transaction under an exclusive lock is one atomic step (`src/headlock.rs`)

Setting: a lock name H (`^IVG.Ledger("head")`) and the cells R it protects (the ledger's globals). **Discipline `disc`
(the product's, a hypothesis, never assumed)**: a process writes a cell of R only while it holds H exclusively inside a
transaction, never by `$INCREMENT`, and never releases H with an immediate unlock.
- `theorem_inv_h`: `inv_h` (well formed; clean levels; no two live processes hold conflicting locks on related names;
  R entries only in the log of the live exclusive holder of H) is preserved by **every permitted outcome of every
  operation of every process** under `disc`; `premise_head_lock_init`: it holds initially.
- `theorem_atomic` (holder theorem): for the process h holding H inside a transaction, whatever step any process takes:
  while h's transaction stays open, the committed state of R (`base`: what rolling back h's log leaves) is unchanged and
  h keeps H; when it ends alive, R holds all of its writes (commit) or none (rollback); when h is stopped, R holds the
  committed state ("a stopped one leaves nothing").
- `theorem_reader_under_lock`: a process holding H in any mode reads every cell of R at its committed value.
- `effects::lemma_step_eff`: the footprint every theorem reasons from: every other process is unchanged, a cell changes
  only if the operation writes it or the actor's log held an entry for it, logs grow only by entries for written cells,
  holds are gained only without conflict.

Clauses used (`hl_sem`): deferred unlock, stop rolls back (every level), KILL logged. Not used: dirty reads,
value-based rollback, $INCREMENT (nobody else writes R).

Read as a refinement: map a contract state to the committed state of R, `base(holder)` while a process holds H with an
open transaction and the globals otherwise. Every contract step under `disc` maps to a stutter, except the holder's
outermost commit, which maps to one atomic step taking R to the transaction's writes; a rollback or stop of the holder
maps to a stutter that also leaves the globals at the committed state. This is proved per step (`theorem_atomic`,
`theorem_inv_h`) with the initial state covered (`premise_head_lock_init`); the trace-level statement follows by
induction and is not itself stated as a Verus theorem over traces.

## 4. The premises, linked (`src/premises.rs`, `premise_map.json`)

Each theorem is one call of a generic lemma (`src/gen.rs`) whose precondition is the clause it needs, stated over
`validated()`. Verdicts for all 72 closure conditions and 7 more PROOFS.md premises are in `premise_map.json`
(checked: every lemma named is a verified function of the baseline, every control named is registered).

| Crate : premise | Verdict | Theorem(s) |
|---|---|---|
| proofs P-C01; proofs-d9 / -d9b / -d9c P-D9-1; proofs-breadth / -pa3 P-L3; proofs-d1b P-S1 | proved under `disc` | `premise_proofs_p_c01`, `premise_d9_p_d9_1`, `premise_breadth_p_l3`, `premise_d1b_p_s1`, `premise_head_lock_init` |
| proofs-d9 P-D9-1 "erasures and bypass writes may roll back" | proved | `premise_d9_p_d9_1_may_roll_back` |
| proofs-d9 G-L (reads under the eraser's / head lock) | proved (from `inv_h`) | `premise_d9_g_l_reader_under_lock` |
| proofs P-C04 (no erasure abort) | **permitted-not-implied** | `premise_proofs_p_c04_not_implied` (a stop is permitted at any moment) |
| TRUST P-0001 | proved; the every-level reading observed (`env-estop-gap`, `proofs-env-mutants-r2`) | `premise_trust_p_0001` |
| TRUST P-0003 | proved | `premise_trust_p_0003` |
| TRUST P-1201 | proved | `premise_trust_p_1201` |
| proofs-d9 P-D9-2 (commit waits for a bypass-written row) | proved for UPDATE / DELETE; for an INSERT of the bypass's key the contract implies an **immediate -119, not a wait** | `premise_d9_p_d9_2_wait`, `premise_d9_p_d9_2_insert_fails` |
| proofs-d9 P-D9-2 (bypass write waits for the erasure's deleted row) | **permitted-not-implied** (both outcomes permitted; the crates' wait is the observed branch, a sharpening) | `premise_d9_p_d9_2_freedom` |
| proofs-breadth / -pa3 P-L5 | proved (the nested level's row lock survives its TCOMMIT) | `premise_breadth_p_l5` |
| proofs-breadth / -pa3 P-A2 | proved for UPDATE / DELETE of an existing row | `premise_breadth_p_a2` |
| proofs-breadth / -pa3 P-A6 | proved in part: before-images restored for nodes nobody wrote since; **a node another process wrote since keeps that write** | `premise_breadth_p_a6_kill`, `premise_breadth_p_a6_incr`, `gen::lemma_fresh_set_rollback`, `premise_core_ma_5_rollback_other` |
| proofs-pa3 P-E2 | proved per row; the multi-row DELETE's scan is outside the contract | `premise_breadth_p_a2`, `premise_trust_p_1201`, `premise_d9_p_d9_2_freedom` |
| proofs-pa3 R04-5 (exclusive `^IVG.AdjW` vs `^IVG.AdjW(g)`) | proved | `premise_pa3_r04_5_names` |
| proofs-breadth P-A4 (violated at the pin) | the contract makes shared holds compatible, so the pin's `#"S"` rebuild lock cannot give P-A4: **the pin's violation** (F-C0402) | `premise_breadth_p_a4_shared` |
| proofs-d1c P-B2 | proved | `premise_d1c_p_b2` |
| proofs-d1c P-T3 | proved | `premise_d1c_p_t3` |
| proofs-d1c P-L3 | proved for `$INCREMENT` counters; stmtNext is a SET under the head lock (P-C01); %ID outside | `premise_d1c_p_l3_counter` |
| proofs-d1d P-0002 | proved | `premise_d1d_p_0002` |
| proofs-d1e P-C5, proofs-d1f P-U2 | **shown false** (a reader reads a value the writer then rolls back) | `premise_d1e_p_c5_false`, `premise_d1f_p_u2_false` |
| proofs-d1f P-F4 | proved in part (a killed holder's lock is granted to its waiter; mutual exclusion from `inv_h`) | `premise_d1f_p_f4` |
| models-core MA-5, MA-6 | proved | `premise_core_ma_5_rollback_other`, `premise_core_ma_6` (and the theorems MA-5 lists) |
| proofs-d9 EraseAbort (E-ROLLBACK-OTHER) | proved | `premise_d9_erasure_rollback` |
| contract-2 S-1 / `_write_txn` (TROLLBACK 1) | proved | `premise_contract2_s1_partial` |
| TRUST Txn.cls:8 / `_write_txn.py:15` | **shown false** on this engine | `premise_trust_txn_cls_8_false` |
| PF-3 (proofs, -d9, -d9b, -d9c) | the lock part proved (a waiter on a stopped holder proceeds; a commit releases deferred holds); that every erasure ends is progress | `premise_proofs_pf_3`, `premise_proofs_pf_3_commit` |

### What the contract does not imply

- **Product discipline** (the contract's part proved under it; at the pin violated where noted): who takes the head lock
  (`disc`: EraseGraph takes none, F-1201; P-L4 Disable takes none), whether readers hold the lock (G-L, F-C1201),
  whether a rebuild takes an exclusive lock (P-A4, F-C0402), who writes the content (P-C02, P-L6, P-D9-3).
- **Outside the contract**: CreateGUID freshness (P-L1, P-S7), sha256 (P-D9b-2), caller identity (P-R3), durability and
  crash recovery (SynchCommit), statement granularity (P-M2; the contract's own), the SQL %ID counter, a multi-row
  DELETE's scan (P-E2), embedded SQL (E-1: validated executably, outside the Verus subset).
- **Progress** (36 rows): fair scheduling, the operator re-running, the ledger re-enabled, every erasure / bypass ending
  (PF-1..PF-6, MA-1..MA-4, P-1306, PM-1, PM-2, the d1f PFs): the contract has no liveness clause.
- **Sharpenings the contract does not give**: P-D9-2's wait over an uncommitted delete (Freedom), P-C04 (no abort).

## 5. Controls (each weakens one clause in `validated()`; must fail exactly at its located premises)

All 17 rejected at their located lines, every other function verifying as in the baseline, the counterexample verified
(registry `proofs-env-ctl-*`, `expected-violation`). Counterexamples (`src/cx.rs`, always compiled) are concrete
instances satisfying every other hypothesis of the generic lemma whose conclusion is false under the weakened clause.

| Control (clause; mutant) | Fails at `src/premises.rs` lines | Theorems that fail | Counterexample |
|---|---|---|---|
| `ctl_unlock_immediate` (E-LOCK-DEFER) | 27, 37, 55, 63, 136 | P-C01, P-D9-1, P-L3, P-S1, P-0003 | `cx_unlock_immediate`: the holder's unlock frees H while its write is uncommitted |
| `ctl_stop_commits` (E-STOP) | 27, 37, 55, 63, 123 | P-C01, P-D9-1, P-L3, P-S1, P-0001 | `cx_stop_commits`: a stopped holder's write stays |
| `ctl_stop_top_level_only` (E-STOP) | 27, 37, 55, 63, 123 | as above | `cx_stop_top_level_only`: the outer level's write stays |
| `ctl_kill_not_logged` (E-GLOBALS) | 27, 37, 55, 63, 374 | P-C01, P-D9-1, P-L3, P-S1, P-A6 (kill) | `cx_kill_not_logged`: the committed state moves inside the transaction |
| `ctl_dml_ignores_row_locks` (E-ROWLOCK) | 210, 223, 245, 259, 272 | P-1201, P-D9-2 (wait, Freedom), P-L5, P-A2 | `cx_dml_ignores_row_locks` |
| `ctl_row_lock_statement_only` (E-ROWLOCK) | 210, 223, 259, 272 | P-1201, P-D9-2 (wait), P-L5, P-A2 | `cx_row_lock_statement_only` |
| `ctl_insert_dup_waits` (E-UNIQUE) | 233 | P-D9-2 (insert) | `cx_insert_dup_waits` |
| `ctl_freedom_wait_only` (Freedom) | 245, 363 | P-D9-2 (Freedom), EraseAbort | `cx_freedom_wait_only` |
| `ctl_no_dirty_reads` (E-VIS) | 289, 304 | P-U2, P-C5 (shown false) | `cx_no_dirty_reads` |
| `ctl_select_committed_only` (E-VIS, SQL) | 319, 333 | P-0002, MA-6 | `cx_select_committed_only` |
| `ctl_rollback_physical` (E-ROLLBACK-OTHER) | 348, 363 | MA-5, EraseAbort | `cx_rollback_physical` |
| `ctl_incr_rolled_back` (E-INCR) | 382, 390, 407 | P-A6 (incr), P-T3, P-L3 (d1c) | `cx_incr_rolled_back` |
| `ctl_rollback_one_undoes_all` (E-PARTIAL) | 419 | S-1 / Txn_Undo | `cx_rollback_one_undoes_all` |
| `ctl_sql_commit_ends_all` (E-SQL-END; the product's premise) | 428 | Txn.cls:8 shown false | `cx_sql_commit_ends_all` |
| `ctl_lock_wait_never_granted` (E-LOCK-WAIT) | 149, 171 | PF-3 (lock part), P-F4 | `cx_lock_wait_never_granted` |
| `ctl_flat_lock_names` (E-LOCK-NAMES) | 181 | R04-5 | `cx_flat_lock_names` |
| `ctl_shared_conflicts_shared` (E-LOCK-MODES) | 195 | P-A4 (shared) | `cx_shared_conflicts_shared` |

The controls also document which premises rest on which clause; e.g. no head-lock premise depends on E-VIS,
E-ROLLBACK-OTHER or E-INCR (those controls leave them verified).

## 6. Registered runs

`proofs-env-baseline` (proof, pass: 305 verified, 0 errors, `--no-cheating`, trust empty); 17 `proofs-env-ctl-*`
(control, expected-violation); `proofs-env-differential` (check, pass); `proofs-env-mutants` (check, **incomplete**:
26/29); `proofs-env-premise-map` (check, pass); the independent recheck `proofs-env-recheck-*` (same gate,
`PROOFS_OUT_DIR=$RUN_DIR/proofs-env-recheck`). With the estop-gap round (`run_proofs.py --differential-only`, no
Verus, same sources digest): `proofs-env-differential-r2` (check, pass: 10 rounds, 1,767 of 2,941 case runs in the
subset, 0 disagreements, 0 outside), `proofs-env-mutants-r2` (check, **incomplete**: 27/29),
`proofs-env-premise-map-r2` (check, pass). Logs: `$RUN_DIR/proofs-env/run-20261114T223057Z/` (proof gate) and
`$RUN_DIR/proofs-env/run-20261114T223917Z/differential/` (differential r2), each Verus text log ending with its RUNNER
SUMMARY line. With the dml-single round: `proofs-env-differential-r3` (check, pass: 11 rounds, 1,769 of 2,943 case runs
in the subset, 0 disagreements, 0 outside) and `proofs-env-mutants-r3` (check, **pass**: 29/29), logs
`$RUN_DIR/proofs-env/run-20261114T224125Z/differential/`. RESULTS.json carries the r3 differential (the first and r2 in
`differential_history`).

## 7. Open obligations (exact)

1. (Closed) E-STOP's every-level reading: decided by `env-estop-gap` (`proofs-env-mutants-r2`).
2. (Closed) Mutants `failed-dml-opens-nothing`, `empty-dml-opens-txn`: killed by `env-dml-single`
   (`proofs-env-mutants-r3`). INSERT ... SELECT itself stays outside the Verus subset.
3. The discipline `disc` against the product: which writers take the head lock and write the ledger globals only inside
   their transaction (D-3/D-4; violated by EraseGraph at the pin, F-1201).
4. Outside the Verus subset: the r6 extension clauses, contract-2's E-1 and X2 (executable evidence only).
5. Not composed: the head-lock theorem is about one lock and its region; several locks / regions (head lock with row
   locks, AdjW with its children) are linked premise by premise, not as one composed invariant.
6. The Freedom's proceeding branch was never observed; its truth on the engine stays open (as in CONTRACT.md).

## 8. Cost (measured, `RESULTS.json`)

Baseline: Verus total 10.8 s, SMT 28.2 s (parallel), 81.1 M rlimit, 305 verified items (299 functions: exec 74,
effects 48, headlock 40, premises 34, wf 33, gen 28, cx 21, spec 20, clauses 1), wall 11.3 s. Per module
(rlimit): cx 19.2 M, exec 18.5 M, headlock 17.7 M, gen 14.4 M, effects 6.5 M, wf 3.5 M, premises 1.0 M. Largest
function `cx::cx_select_committed_only` 7.0 M (concrete evaluation); largest proof lemma `headlock::lemma_txn_locks`
6.4 M; no rlimit raised. Each control run 10-11 s wall. The whole gate (baseline, 17 controls, differential on 9 rounds)
takes about 3 minutes (registered run: 22:30:57-22:34:07 UTC).

## 9. Trust inventory

This crate: no `assume`, `admit`, `external_body` / `external`, `axiom`, `assume_specification` or `uninterp`
(scanned by the runner; `--no-cheating` also enforced; the platform assumption `global size_of usize` was removed for
this reason). Dependency: vstd only (Verus's trusted base). Unverified test code: the harness (JSON reading, interning,
rendering, choice enumeration); its rendering is cross-checked by set equality with the contract binary on every case.
The executable contract binaries are built from their committed, unchanged sources.

## 10. Reproduce

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-env/tools/run_proofs.py
    PROOFS_OUT_DIR=$RUN_DIR/proofs-env-recheck python experiment/playbook-completion/proofs-env/tools/run_proofs.py
    python experiment/playbook-completion/proofs-env/tools/premise_map.py --results experiment/playbook-completion/proofs-env/RESULTS.json --out experiment/playbook-completion/proofs-env/premise_map.json
