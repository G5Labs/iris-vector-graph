# PROOFS-ENV2: the contract clauses outside proofs-env's Verus subset, brought in (proof debt D-7, remaining part)

Lane proofs-env2 (steer 13), product pin `3eaa79cf`. A new crate `ivg-proofs-env2`: a copy of `proofs-env`
(integrated at 737c3930; its sources and its registered runs `proofs-env-*` are unchanged) whose Verus specification
is extended by the clauses that were outside its subset. Evidence grade: **proved** for the statements below (Verus
`0.2026.10.04.426d8b0`, `--no-cheating`, empty trust inventory, `proofs-env2-baseline`: 433 verified, 0
errors), each about a **model** (the Verus specification of the IRIS 2026.1 contract); the link to the executable
contract is by an exec model verified against that specification and run on every recorded round (no IRIS): 0
disagreements, 0 observations outside. Everything `proofs-env/PROOFS.md` states (sections 1-5, the head-lock
refinement, the premise theorems, the 17 controls) holds here unchanged, now over the extended operation set.

Summary: cases in the Verus subset **2,430 of 2,943** recorded case runs (proofs-env r3: 1,769), 0
disagreements, 0 observations outside the Verus model; Verus-model mutants killed by observation **49/49**
(the 20 new ones included); 22 located controls (5 new), each with a verified counterexample; two premises linked anew
(E-1 proved, P-M2 proved in part). Still outside: 513 case runs in 9 clause families, listed with their exact
obligations in section 6.

## 1. What the specification now includes (`src/ext.rs`, `src/spec.rs`)

Each family mirrors `iris-contract/src/lib.rs` (r6) and `contract-2/contract/src/lib.rs` clause for clause, keeps the
permitted-outcome structure (the only nondeterminism stays the Freedom, now also for E-1's embedded INSERT), and has
its exec counterpart in `src/ext_exec.rs`, verified equal to it (`e_ext_step` == `ext_step`, `e_await` == `await_step`).

| Family (clause) | In the specification | Mutants (killed in rounds) |
|---|---|---|
| X-TLEVEL-SQL (`SELECT $TLEVEL`) | `Op::SqlTLevel`: the statement's `select_txn`, then the level | (by the existing select-opens-txn) |
| X-VEC, SQL functions (VECTOR_COSINE / DOT_PRODUCT / L2) | `sqlfn_obs`: L2 answers -359 on this engine; other names refused | vector-l2-available (r4, r5, r6, c2-regress-r6) |
| X-ZSTRIP (`$ZSTRIP` masks and the class tables) | `zclass`, `zfilter`, `zlead`, `ztrail`, `zcollapse`, `zstrip`, `zranges` over code points; refused on DB-API | zstrip-c-ascii-only, zstrip-w-space-only (r4, r5, r6, c2-regress-r6) |
| X-ORDER (canonical numbers before strings, numeric collation) | `canonical`, `collate`, `subs_from`, `isort`, `order_obs`; a canonical number longer than 41 characters refused | string-collation (r4, r5, r6, c2-regress-r6) |
| X-NULL (NULL vs "" vs $C(0) through DB-API and ObjectScript, COALESCE) | `Val::{Null, Empty, Nul}`, `Param`, `stored`, `gete_obs`, `matches_e`, `match_from` | dbapi-empty-param-null, objectscript-empty-param-empty, objectscript-reads-empty-as-empty, coalesce-c0-differs (r4, r5, r6, c2-regress-r6) |
| X-STMT, INSERT ... SELECT (atomic; refused while another process holds row locks) | `insert_select`: source rows in key order, `first_fail`, `is_write`, `is_lock` | statement-not-atomic (r4, r5, r6, c2-regress-r6) |
| E-1 (embedded SQL as dynamic SQL, the pin's `&sql` statements) | `emb_dml`, `emb_visible`, `emb_register`, `emb_assert`, `rows_count`; `EmbRegister / EmbRetract / EmbCount / EmbRoute / EmbAssert`; the VARCHAR(256) key limit (-104) | emb-own-txn, emb-ignores-driver-autocommit (e1-r1, e1-r2), emb-select-committed-only, emb-ignores-row-locks, emb-empty-host-var-empty, maxlen-not-enforced (e1-r1) |
| X2-BATCH (DB-API `executemany`) | `insert_many`: one INSERT per row, a failing row skipped (one row raises), `batch_probe` for the atomic mutant | batch-raises-on-dup, batch-atomic, batch-single-row-skips (x2-r1) |
| X2-IOU (`INSERT OR UPDATE`) | `upsert_run`: updates the visible row (waiting for its row lock), -109 when it is gone after the wait, else inserts | iou-retries-insert, iou-ignores-row-locks (x2-r1) |

The theorems of `proofs-env` quantify over every operation, so they now cover these: well-formedness
(`lemma_step_wf`), the footprint (`lemma_step_eff`: another process is unchanged), and the head-lock invariant
(`theorem_inv_h`, `theorem_atomic`). The extension's operations write only row cells (`wr`), never the ledger's globals
(`lemma_r_glob_rows`), so they need no new discipline; the bundle `xok` (`src/ext_lemmas.rs`) proves each of them well
formed, inside its footprint, keeping the actor's user locks, level and committed state on the protected region. Two
specification corrections came out of these proofs (both are the contract's behaviour, now stated): `clean_proc`
records that a process at level 0 holds no deferred unlock counts, and the row-lock clause of the footprint was
dropped (a statement's own row locks are its effect).

## 2. The mechanical link (`harness/`, `src/exec.rs`, `src/ext_exec.rs`)

The harness (unverified test code) now reads every extension operation, allocates row cells per (table, key) in key
order (INSERT ... SELECT reads its source in key order), marks over-long keys under `--long-keys-refused`, and renders
the new observations; it computes the Verus model's permitted set of each case over every choice sequence and compares
it with `iris-contract permitted` (r6 binary; contract-2's binary for its rounds and regressions).

| Round | Contract binary | Cases | In the Verus subset | Disagree | Observations | Outside the Verus model | Freedom cases |
|---|---|---|---|---|---|---|---|
| r6 | r6 | 516 | 420 | 0 | 420 | 0 | 1 |
| r2 | r6 | 283 | 283 | 0 | 283 | 0 | 1 |
| r4 | r6 | 514 | 419 | 0 | 419 | 0 | 1 |
| r5 | r6 | 515 | 420 | 0 | 420 | 0 | 1 |
| c2-e1-r1 | c2 | 67 | 67 | 0 | 67 | 0 | 0 |
| c2-e1-r2 | c2 | 54 | 54 | 0 | 54 | 0 | 0 |
| c2-x2-r1 | c2 | 190 | 59 | 0 | 59 | 0 | 0 |
| c2-regress-r6 | c2 | 516 | 420 | 0 | 420 | 0 | 1 |
| c2-regress-r2 | c2 | 283 | 283 | 0 | 283 | 0 | 1 |
| estop-gap | r6 | 3 | 3 | 0 | 3 | 0 | 0 |
| dml-single | r6 | 2 | 2 | 0 | 2 | 0 | 0 |
| **all** | | **2,943** | **2,430** | **0** | **2,430** | **0** | |

proofs-env r3 (`proofs-env-differential-r3`): 1,769 of 2,943 on the same 11 rounds.

Mutants: 49/49 gating mutants killed by observations, union over the rounds (`proofs-env2-mutants`); the probe
`freedom-waits-only` stays alive by design (the Freedom's proceeding branch is unobserved).

## 3. The premises, linked (`src/premises.rs`, `src/gen.rs`, `premise_map.json`)

New theorems (each one call of a generic lemma whose precondition is the clause it needs, stated over `validated()`):

| Premise | Verdict | Theorem | Controls |
|---|---|---|---|
| TRUST (new) "Embedded SQL (&sql) behaves as dynamic SQL for the clauses used" | **proved in the specification** (was outside-contract), where the embedded statements are defined as the dynamic ones (`src/ext.rs:386-401`; `gen_e1` needs nothing beyond that definition); its link to IRIS is the E-1 rounds (c2-e1-r1, -r2: 121 cases, differential) and the 6 E-1 mutants: the embedded DML has the dynamic statement's effect and answer; its SELECT INTO sees uncommitted rows as a dynamic SELECT does; its DELETE waits exactly when the dynamic DELETE does; its INSERT over another's uncommitted DELETE is the same Freedom | `premise_trust_e1` (`gen_e1`) | `ctl_emb_own_txn`, `ctl_emb_ignores_autocommit`, `ctl_emb_select_committed_only`, `ctl_emb_ignores_row_locks` |
| proofs-d1e P-M2 "each SQL statement and global operation is one atomic step" | **proved in part** (was outside-contract): the part the contract states (X-STMT) -- a multi-row INSERT ... SELECT that fails on a key while no other process holds row locks writes none of its rows and answers -119; the step granularity itself stays the contract's own, Cypher's mode read product code | `premise_d1e_p_m2_stmt_atomic` (`gen_stmt_atomic`) | `ctl_statement_not_atomic` |
| TRUST "IRIS environment contract" | proved in part, with the larger subset (`e_ext_step` added to the linked functions); the remaining families of section 6 stay executable evidence | `exec::e_run`, `exec::e_step`, `ext_exec::e_ext_step` | -- |
| new closure rows proofs-env ENV-4, proofs-sys PS-2, PS-3, and proofs-env2 ENV2-4 (mapped at integration, `proofs-env2-premise-map-r2`) | progress | -- | -- |

No other closure premise depends on the new clauses (checked by hand at the lane's run: the 75 proof-premise conditions of
`reflection/closure.json` searched for NULL / collation / $ZSTRIP / INSERT ... SELECT / executemany / INSERT OR
UPDATE / JSON / $LIST / TOP / MERGE / $QUERY / vector / DDL / index / embedded). `premise_map.json`
(`proofs-env2-premise-map-r2`, after ENV2-4 was added at integration): 76 closure conditions -- outside-contract 7, product-discipline 5, progress 40, proved 10, proved-in-part 11, shown-false 3; 83 rows with the PROOFS.md premises; problems 0. Since that run the map itself searches the 76 conditions for the words of the 9 families still outside (section 6): 0 hits. The lane's own run (`proofs-env2-premise-map`) mapped the 75 conditions of its time.

## 3a. This crate's own premises

Added at integration by the orchestrator: proofs-env's ENV-1..ENV-4 carried over to the extended subset, plus the
one modelling choice section 8 names.

| Id | Premise | Status |
|---|---|---|
| ENV2-1 | The recorded rounds are faithful observations of IRIS 2026.1 (proofs-env ENV-1), now for the 11 rounds the extended subset reads (r2, r4, r5, r6, c2-e1-r1, c2-e1-r2, c2-x2-r1, contract-2's regressions of r2 and r6, estop-gap, dml-single), contract-2's included | each round's registered validation run (`env-contract-r2`, `env-ext-r4`, `-r5`, `-r6`, `env2-e1-r1`, `env2-e1-r2`, `env2-x2-r1`, `env2-regress`, `env-estop-gap`, `env-dml-single`; r4 and r5 failed against their contract models of the time, which the r6 model reproduces with 0 outside), the drivers' self-tests and mutants (`env-contract-selftest`, `env-ext-r6`, `env2-e1-r1`, `env2-x2-r1`); the exec model agrees with the contract binaries on every in-subset case (`proofs-env2-differential`) |
| ENV2-2 | The Verus subset covers the clauses the proof premises use (proofs-env ENV-2); the 9 families of section 6 stay executable evidence only | stated; `proofs-env2-premise-map-r2` gives each closure premise a verdict, and its keyword search finds no closure premise naming the 9 families (0 hits over 76) |
| ENV2-3 | The product discipline `disc` (proofs-env ENV-3) | a hypothesis of the head-lock theorems; violated at the pin by EraseGraph (F-1201) |
| ENV2-4 | No liveness clause (proofs-env ENV-4): the progress premises are not implied by the contract | stated; they stay assumed (PROOF-DEBT D-8) |
| ENV2-5 | `batch_probe` (the batch-atomic mutant's dry run) is stated on the globals alone: an INSERT's outcome depends only on its table's existence and its row's visibility | a modelling choice the differential checks (`proofs-env2-differential`, `proofs-env2-mutants`), not proved |

## 4. Controls

The 17 controls of `proofs-env` (same lines' premises, same counterexamples) plus 5 new ones, all rejected exactly at
their located lines, every other function verifying as in the baseline, every counterexample verified
(`proofs-env2-ctl-*`, expected-violation):

| Control (clause; mutant) | Fails at | Counterexample |
|---|---|---|
| `ctl_emb_own_txn` (E-1; emb-own-txn) | `premise_trust_e1` | `cx_emb_own_txn`: an embedded INSERT in its own transaction is not in the caller's log |
| `ctl_emb_ignores_autocommit` (E-1; emb-ignores-driver-autocommit) | `premise_trust_e1` | `cx_emb_ignores_autocommit`: with autocommit off the embedded INSERT opens no level |
| `ctl_emb_select_committed_only` (E-1; emb-select-committed-only) | `premise_trust_e1` | `cx_emb_select_committed_only`: SELECT INTO misses another's uncommitted row |
| `ctl_emb_ignores_row_locks` (E-1; emb-ignores-row-locks) | `premise_trust_e1` | `cx_emb_ignores_row_locks`: the embedded DELETE does not wait where the dynamic one does |
| `ctl_statement_not_atomic` (X-STMT; statement-not-atomic) | `premise_d1e_p_m2_stmt_atomic` | `cx_statement_not_atomic`: INSERT ... SELECT writes its first row, then fails on the second |

Located lines (this build): `ctl_emb_own_txn` src/premises.rs:442; `ctl_emb_ignores_autocommit` src/premises.rs:442; `ctl_emb_select_committed_only` src/premises.rs:442; `ctl_emb_ignores_row_locks` src/premises.rs:442; `ctl_statement_not_atomic` src/premises.rs:453. All 22/22 controls rejected at their located premises.

## 5. Registered runs

`proofs-env2-baseline` (proof, pass: 433 verified, 0 errors, `--no-cheating`, trust empty); 22 `proofs-env2-ctl-*` (control, expected-violation); `proofs-env2-differential` (check, pass: 11 rounds, 2,430 of 2,943 case runs in the subset, 0 disagreements, 0 outside); `proofs-env2-mutants` (check, pass: 49/49); `proofs-env2-premise-map` (check, pass). Logs: `$RUN_DIR/proofs-env2/run-20261114T235905Z/` (each Verus text log ends with its RUNNER SUMMARY line; differential in `differential/`). Sources digest `b9a7bb764d46174889eac4290b91b4799f308914c4a682cbed7db9716ad1c99d` (src, Cargo files, harness). A first gate attempt (`$RUN_DIR/proofs-env2/run-20261114T235027Z`, same sources) stopped in the differential on a bug in the runner's new outside-family accounting, before registering anything; its logs are kept, unregistered. Independent recheck `proofs-env2-recheck-*` (same gate, `PROOFS_OUT_DIR=$RUN_DIR/proofs-env2-recheck`, `$RUN_DIR/proofs-env2-recheck/run-20261115T000520Z`): proofs pass, differential pass, mutants pass, baseline 433 verified, same sources digest.

## 6. Open obligations (exact)

Families still outside the Verus subset (the executable contract stays the evidence for them), with the recorded
case runs each leaves outside (`RESULTS.json` `differential.outside_families_total`; per round
`differential.rounds.<r>.outside_families`) and what bringing it in needs:

1. **X-DDL** -- 172 case runs (e.g. ddl-create-commit, ddl-create-in-txn, ddl-drop-in-txn): table existence becomes state (`U.texists` is static today): CREATE / DROP TABLE and ALTER ... ADD COLUMN with their behaviour inside a transaction and under autocommit off (the r6 X-DDL clause), `table_exists`; a dropped table's rows and the -30 answers of later statements.
2. **X-FX** -- 115 case runs (e.g. fx-autocommit-visible, fx-dirty-then-rollback, fx-rollback-one): table F's functional index (`find` by word): the index content as a function of the stored values, its update inside transactions and its visibility (rollback, autocommit off, stop).
3. **X-NOINDEX** -- 83 case runs (e.g. noindex-in-txn-rollback, noindex-insert-then-build, noindex-term): rows and unique-index entries as separate state (INSERT %NOINDEX / %NOCHECK, BUILD INDEX), replacing the representation choice 'an index entry exists exactly when its row does'; the contract's refusals (several rows per key, <LIST ERROR> after BUILD INDEX) as outcomes.
4. **X2-JSON** -- 38 case runs (e.g. x2-json-number-form, x2-json-order, x2-json-reset-keeps-place): %ToJSON insertion order and the JSON round trip: a value-level model of the JSON text (numbers, strings, escapes).
5. **X2-LIST** -- 33 case runs (e.g. x2-list-get, x2-list-item, x2-list-walk): $LIST / $LISTBUILD encoding, $LISTGET defaults, $LISTSAME, $LISTFROMSTRING, the native $LB bytes: a value-level model of the list encoding.
6. **X2-QUERY/MERGE/ZKILL** -- 30 case runs (e.g. x2-merge-rollback, x2-query-back, x2-query-walk): $QUERY's depth-first walk in collation order over whole paths (X-ORDER's `sub_lt` lifted to paths); MERGE's subtree copy (a destination cell per source cell in the universe, logged writes to globals: head-lock footprint and `disc`); ZKILL as a one-node logged kill.
7. **X2-TOP** -- 30 case runs (e.g. x2-limit, x2-top-asc, x2-top-zero): SELECT TOP / LIMIT ... OFFSET with SQLUPPER or exact ordering; without ORDER BY every n-subset is permitted, so the choice structure must become n-ary (today: the binary Freedom choice).
8. **X-VEC ($VECTOR set/get)** -- 8 case runs (e.g. vec-global, vec-native-get): `$VECTOR` element maps encoded in a global's value, `vector_set_rolled_back`; a new writer of globals, so the head-lock footprint / `disc` must cover it.
9. **X-STAR** -- 4 case runs (e.g. select-star-order): a column schema per table in the state (SELECT * after ADD COLUMN, column order); depends on X-DDL.

Carried over unchanged from `proofs-env` (section 7 there): the discipline `disc` against the product (D-3/D-4;
violated by EraseGraph at the pin, F-1201); locks / regions not composed into one invariant; the Freedom's proceeding
branch unobserved (now for E-1's embedded INSERT as well); progress premises (D-8).

## 7. Cost (measured, `RESULTS.json`)

Baseline: Verus total 15.9 s, SMT 60.1 s (parallel), 150.3 M rlimit, 433 verified items (412 functions: exec 74, ext_exec 56, effects 48, headlock 40, premises 36, wf 33, gen 30, ext_lemmas 28, cx 26, spec 21, ext 19, clauses 1), wall 16.4 s. Per module (rlimit): ext_exec 31.8 M, headlock 24.1 M, cx 23.6 M, exec 20.6 M, wf 19.7 M, gen 14.4 M, effects 7.7 M, ext_lemmas 7.2 M. Largest functions: `wf::lemma_await_wf` 15.9 M, `ext_exec::e_ext_step` 11.1 M. No rlimit raised (one exec dispatcher was split into `e_e1_step` / `e_x2_step` instead). Each control run about 16 s wall.

## 8. Trust inventory

As `proofs-env`: no `assume`, `admit`, `external_body` / `external`, `axiom`, `assume_specification` or `uninterp` in
`src/*.rs` (scanned; `--no-cheating` enforced). Dependency: vstd only. Unverified test code: the harness (JSON reading,
interning, cell allocation, rendering, choice enumeration); its rendering is cross-checked by set equality with the
contract binaries on every in-subset case. The contract binaries are built from their committed, unchanged sources.
One modelling choice the differential checks rather than a proof: `batch_probe` (the batch-atomic mutant's dry run)
is stated on the globals alone, since an INSERT's outcome depends only on its table's existence and its row's
visibility.

## 9. Reproduce

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-env2/tools/run_proofs.py
    PROOFS_OUT_DIR=$RUN_DIR/proofs-env2-recheck python experiment/playbook-completion/proofs-env2/tools/run_proofs.py
    python experiment/playbook-completion/proofs-env2/tools/premise_map.py --results experiment/playbook-completion/proofs-env2/RESULTS.json --out experiment/playbook-completion/proofs-env2/premise_map.json
