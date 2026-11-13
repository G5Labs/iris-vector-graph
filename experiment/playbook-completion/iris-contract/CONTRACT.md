# IRIS environment contract (playbook §3.2)

A reusable, executable model of the InterSystems IRIS semantics IVG relies on, validated against the dedicated
engine. It replaces the PostgreSQL contract (pgspec) for this product. PGspec is not used.

- Engine: `IRIS for UNIX (Ubuntu Server LTS for x86-64 Containers) 2026.1 (Build 234U)`, Community licence
  (8 connections), container `ivg-playbook-20261113-audit-iris`, namespace `AUDITENV` (no product classes).
- Client: `intersystems_irispython 5.3.2` / `intersystems-iris 5.3.3`: the versions the product's own `uv.lock` pins.
- Library: `src/lib.rs` (`Engine::step` returns every permitted (next state, observation)); `permitted(case)`
  enumerates the permitted outcomes of a schedule. Core models reuse its clauses.
- Validation: `native/driver.py` runs the same schedules on the engine through two drivers per process: `dbapi`
  (DB-API cursor + Native API on one connection, the product's client path) and `term` (ObjectScript terminal via
  `iris session`, for process-private globals and the non-incremental `LOCK`). Nothing is compiled into IRIS.
  `iris-contract check` reports outcomes outside the contract, sharpness and mutant kills.

## Clauses (validated)

| Clause | Contract | Decided by (named cases; random families also kill) | Product reliance |
|---|---|---|---|
| Nesting | `TSTART` nests; inner `TCOMMIT` only lowers `$TLEVEL`; a later outer rollback undoes inner work | txn-nest-commit-inner, txn-rollback-one | Graph.KG.Txn, Ledger.Commit (Ledger.cls:390-418) |
| Partial rollback | `TROLLBACK 1` undoes only the top level, globals and SQL rows alike | txn-rollback-one, sql-row-in-native-level | Txn.Undo, `_write_txn` |
| `$INCREMENT` | not undone by rollback | txn-incr-survives | Adjacency.cls:57 (^IVG.AdjNoLock), LedgerRedact.cls:342 (counters use SET for this reason) |
| Process-private globals | not undone by rollback; invisible to other processes | ppg-not-rolled-back, ppg-private | ^\|\|IVG.RedactStmt, ^\|\|IVG.LedgerStage, ^\|\|IVG.CypherRun |
| Visibility | no isolation for globals; SQL SELECT reads uncommitted rows (READ UNCOMMITTED) | txn-dirty-read, row-dirty-select | liveness checks (LiveRows), readers, verify |
| Rollback over another's write | a rollback does **not** overwrite a node another process changed after this process wrote it | txn-physical-rollback | concurrent writers without locks |
| SQL `START TRANSACTION` | does nothing when any level is open; else opens level 1 | sql-start-inside-native, sql-start-twice | `_write_txn` plain path |
| SQL `COMMIT` / `ROLLBACK` statements | end **one** level | sql-commit-native-2, sql-rollback-native-2 | `_write_txn` plain path; see version note |
| Driver `commit()` / `rollback()` | `commit()` ends one level; `rollback()` ends **every** level | drv-commit-native-2, drv-rollback-native-2 | autocommit-off callers (`_write_txn.py:23-25`) |
| Autocommit off | the first DML opens a level SQL owns | autocommit-off-first-write | `_driver_autocommit_off` |
| Locks: deferral | an unlock inside a transaction, including release-all and a lock taken before it, takes effect when the outermost transaction ends; an immediate unlock releases at once | lock-deferred-in-txn, lock-deferred-pre-txn, lock-release-all-in-txn, lock-immediate | head lock (Ledger.cls:394-396, LedgerRedact.cls:289), AdjW |
| Locks: lifetime | a lock not unlocked survives the commit | lock-survives-commit | — |
| Locks: names | hierarchical: a name conflicts with ancestors and descendants; siblings do not | lock-hier-child, lock-hier-parent, lock-siblings | ^IVG.AdjW vs ^IVG.AdjW(g) (Adjacency.cls:449-455) |
| Locks: modes | shared locks are compatible; exclusive conflicts with shared, incl. across the hierarchy | lock-shared, lock-shared-parent-excl | AdjW `#"S"` writers vs `#"E"` (Adj.cls:68,144) |
| Locks: counts | incremental | lock-incremental | nested lock/unlock pairs |
| Non-incremental `LOCK` | releases every held lock first, then locks | lock-only-releases-others, lock-only-in-txn | `lock ^IVG.NKGBuild`, `lock ^IVG.AdjW` |
| Lock wait | a waiting lock is granted when the holder releases | lock-wait-then-get | head lock waits (30 s), AdjW (5 s) |
| Row locks | a DELETE/UPDATE waits for a row another open transaction inserted or updated; after that transaction rolls back it affects nothing; an autocommit statement holds no row lock afterwards; a global SET takes no lock | row-delete-waits-insert(-rb), row-update-waits-update, row-autocommit-no-hold, row-global-write-no-row-lock | eraser's DELETEs vs concurrent writers (P-1201) |
| Unique keys | INSERT of a key another transaction inserted fails at once (-119) | row-insert-dup-uncommitted | `_write_txn.is_duplicate` |
| Process stop | rolls back every level and releases every lock; a waiter proceeds | stop-rolls-back, stop-nested-levels, stop-releases-locks, stop-releases-row-lock | P-0001, interrupted redaction |
| Caller identity | SQL on a cursor and the Native API on the same connection run in one server process (same `$JOB`) | exploratory probe (env/explore-2.log, test 7) | `_write_txn` docstring, Txn_Begin |

**Freedom (both outcomes permitted, not yet sharpened):** an INSERT of a key whose row another open transaction
deleted. One round observed the waiting branch; the other branch (proceeds under a new row id) was never observed and
stays permitted until a witness or a source settles it.

## Results

| Run | Cases | Outside contract | Singleton cases | Mutants killed |
|---|---|---|---|---|
| `env-contract-r1` (seed 20261113, first draft; stopped at 157 by the connection cap) | 157 run | 15 (draft wrong; revised from these observations) | — | 17/17 |
| `env-contract-r2` (seed 7331, cross-validation of the revision on fresh schedules) | 283 | **0** | 282 | **17/17** |
| `env-contract-selftest` (explorer, 2 processes x 16 ops, depth 6, bounded) | — | invariants hold | — | control caught in 2 steps |

The revision after round 1 was driven only by engine observations; round 2 used a new seed and two new case families
(random row-lock schedules, terminal cases) and met the gate with no further change.

## Version difference recorded (product premise vs this engine)

`iris_vector_graph/_write_txn.py:15-16` and `iris_src/src/Graph/KG/Txn.cls:8` state, "measured on IRIS 2026.3
(driver 5.4.0)": SQL `COMMIT` and `ROLLBACK` end every level and `START TRANSACTION` inside a transaction does nothing.
On IRIS 2026.1 Community with the product's locked driver 5.3.2, `START TRANSACTION` matches, but the SQL `COMMIT` and
`ROLLBACK` statements end **one** level (the mutants encoding the product's premise are killed by 4 and 6 cases);
only the driver's `rollback()` ends every level. Two variables differ (engine 2026.3 vs 2026.1, driver 5.4.0 vs
5.3.2); the 2026.3 engine and driver 5.4.0 are not available here (**blocked-access**), so the difference cannot be
attributed. Impact on the as-built product: the main write path uses `Txn_Begin/End/Undo` (TSTART/TCOMMIT/TROLLBACK 1),
which behaves as the product expects; the statement is a documentation premise that is false on a supported version
(ADMIN_GUIDE lists 2026.1 Community as tested). Recorded as finding F-C1701 candidate (S3, documentation/premise).

## Outside the semantic subset (refused, never claimed)

ECP, mirroring and multi-node; journal restore and crash recovery of the instance; SQL isolation levels other than the
default and `%NOLOCK`/`%NOJOURN`; lock escalation thresholds and the escalating lock type (`#"E"` is treated as
exclusive); lock-table capacity; DDL inside transactions; iFind, vector/HNSW index maintenance; `$SYSTEM.Process`
other than Terminate; timing (lock timeouts are modelled as wait/no-wait, not durations); embedded SQL (`&sql`)
compiled into classes (assumed equal to dynamic SQL; untested premise E-1). Modules that rely on one of these list it
in `modules/NN.json` (`env_features`), and the matrix keeps their gate `3.2-coverage` open.

## Reproduce

```bash
source experiment/playbook-completion/environment.sh
cd experiment/playbook-completion/iris-contract
CARGO_TARGET_DIR=$RUN_DIR/target/iris-contract cargo build --release --offline
python native/cases.py $RUN_DIR/env/rN/cases.json --seed <S> --random-per-family 60
bash ../tools/locks.sh iris python native/driver.py $RUN_DIR/env/rN/cases.json $RUN_DIR/env/rN/observed.json
$RUN_DIR/target/iris-contract/release/iris-contract check $RUN_DIR/env/rN/cases.json $RUN_DIR/env/rN/observed.json
$RUN_DIR/target/iris-contract/release/iris-contract selftest
```
