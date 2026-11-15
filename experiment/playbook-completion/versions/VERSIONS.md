# Engine x driver results for the IRIS contract's transaction verbs

The question: does the product's premise "measured on IRIS 2026.3 (driver 5.4.0): SQL `COMMIT` and `ROLLBACK` end every
level, and `START TRANSACTION` inside a transaction does nothing" (`iris_vector_graph/_write_txn.py:15-17`,
`iris_src/src/Graph/KG/Txn.cls:7-8`) come from the driver or from the engine? `iris-contract/CONTRACT.md` ("Version
difference recorded") left two variables open. The 2026.1 results with driver 5.3.2 (`env-contract-r2`, `env-ext-r4`, ...)
stay attributed to that pair. This lane adds the cells below.

## Setup

- **Cases.** `native/cases.py --seed 20261114` (a fresh seed), filtered to every named case that uses a SQL or driver
  transaction verb (`sql_start/commit/rollback`, `drv_commit/rollback`, `set_autocommit`) or is a `txn-*` case: 23 named
  cases, the `rand-txn` family (60) and `rand-stmt` (30), 113 in all
  (`$RUN_DIR/versions/cases-versions-20261114.json`). The same file ran in every cell. The two full-set cells ran the
  unfiltered 515 (`cases-all-20261114.json`).
- **Contract.** A snapshot of the working tree at 03:27 UTC: `src/lib.rs` `0c82d244...`, `native/driver.py` `e82b7c49...`,
  `native/cases.py` `2d815de5...`. The binary is `$RUN_DIR/versions/bin/iris-contract` `9d473e24...`. The driver is
  unchanged; `versions/run_driver.py` only sets its namespace (`USER` on 2026.2) and prints the imported driver build.
  `versions/compare_cells.py` counts mutant kills only over cases whose observation is inside the contract, because an
  observation outside the contract is outside nearly every mutant too, and `check` would count it as killing all of them.
- **Engines.** 2026.1 = the audit container (`IRIS for UNIX (Ubuntu Server LTS for x86-64 Containers) 2026.1 (Build 234U)
  Fri Mar 27 2026`), namespace AUDITENV, under `tools/locks.sh iris`. 2026.2 = the isolated
  `ivg-versions-20261114-iris-2026-2` (`... 2026.2 (Build 221U) Fri Jun 26 2026`), namespace USER, scratch only
  (`ver-image-iris-2026.2`).
- **Drivers.** 5.3.2 = the main venv (the pin's `uv.lock`). 5.4.0 = `$RUN_DIR/availability/driver-5.4.0-venv` first on
  PYTHONPATH. Every driver log prints metadata `5.4.0` or `5.3.2` and the `irissdk` sha256 (`6ab7b9ea...` and
  `7663480c...`).

## Cells

| Cell | Engine | Driver | Registry id | Cases | Outside the contract | In-contract mutant kills |
|---|---|---|---|---|---|---|
| e261-d532 | 2026.1 | 5.3.2 | `ver-e261-d532` | 113 | 0 | 18 (every mutant the subset reaches) |
| e261-d540 | 2026.1 | 5.4.0 | `ver-e261-d540` | 113 | **1**: `autocommit-on-commits-one-level` | 17 (`autocommit-on-keeps-txn` not killed in-contract) |
| e262-d532 | 2026.2 | 5.3.2 | `ver-e262-d532` | 113 | 0 | 18 |
| e262-d540 | 2026.2 | 5.4.0 | `ver-e262-d540` | 113 | **1**: `autocommit-on-commits-one-level` | 17 |
| e262-d532-full | 2026.2 | 5.3.2 | `ver-e262-d532-full` | 515 (full contract) | 0 (514 singleton) | **41/41** |
| e262-d540-full | 2026.2 | 5.4.0 | `ver-e262-d540-full` | 515 | **1**: `autocommit-on-commits-one-level` | 40/41 |

`ver-matrix-compare`: against e261-d532, the only case that differs anywhere is `autocommit-on-commits-one-level`, and it
differs in both 5.4.0 cells. e262-d532 is identical to e261-d532 on all 113 cases (the two `report.json` files are
byte-identical, sha256 `b1837851...`). On the full set, the 2026.2 engine with 5.3.2 matches the 2026.1 contract on every
one of the 515 cases.

## Clause by clause (113-case subset; "holds" = every decisive case inside the contract)

| Clause | Named cases | 2026.1 x 5.3.2 | 2026.1 x 5.4.0 | 2026.2 x 5.3.2 | 2026.2 x 5.4.0 |
|---|---|---|---|---|---|
| E-GLOBALS | txn-kill-subtree-rollback | holds | holds | holds | holds |
| E-NEST | txn-nest-commit-inner, txn-commit-at-zero | holds; kills rollback-one-undoes-all (4) | holds (4) | holds (4) | holds (4) |
| E-PARTIAL | txn-rollback-one, sql-row-in-native-level | holds (4) | holds (4) | holds (4) | holds (4) |
| E-INCR | txn-incr-survives | holds; incr-rolled-back (1) | holds (1) | holds (1) | holds (1) |
| E-VIS (globals) | txn-dirty-read | holds; no-dirty-reads (1) | holds (1) | holds (1) | holds (1) |
| E-ROLLBACK-OTHER | txn-physical-rollback | holds; rollback-physical (1) | holds (1) | holds (1) | holds (1) |
| E-SQL-START | sql-start-inside-native, sql-start-twice | holds; sql-start-unless-sql-owns (7), sql-start-always (9) | holds (7, 9) | holds (7, 9) | holds (7, 9) |
| **E-SQL-END** | sql-commit-native-2, sql-rollback-native-2 | holds: **one level**; kills sql-commit-ends-all (2), sql-rollback-ends-all (4), the product's premise | holds: **one level** (2, 4) | holds: **one level** (2, 4) | holds: **one level** (2, 4) |
| E-DRV | drv-commit-native-2, drv-rollback-native-2 | holds: commit() one level, rollback() all; driver-commit-ends-all (7), driver-rollback-one-level (1) | holds (6, 1) | holds (7, 1) | holds (6, 1) |
| **E-AUTOCOMMIT** | autocommit-off-first-write, autocommit-on-commits-one-level | holds; autocommit-on-keeps-txn (1) | **outside** (below) | holds (1) | **outside** (below) |
| X-FX (SQL / driver rollback) | fx-sql-rollback, fx-autocommit-off-rollback | holds; fx-outside-row-txn (2) | holds (2) | holds (2) | holds (2) |
| X-DDL (under a SQL transaction, autocommit off) | ddl-under-sql-txn, ddl-autocommit-off | holds; ddl-not-rolled-back (1), ddl-commits-open-txn (1) | holds | holds | holds |
| X-STMT | autocommit-off-failed-dml (+ rand-stmt) | holds; statement-not-atomic (1), failed-dml-opens-nothing (1), empty-dml-opens-txn (2) | holds | holds | holds |
| X-TLEVEL-SQL | sql-tlevel, sql-tlevel-term | holds; select-opens-txn (1) | holds | holds | holds |
| rand-txn (60), rand-stmt (30) | — | 0 outside | 0 outside | 0 outside | 0 outside |

`driver-commit-ends-all` is killed by 6 cases with 5.4.0 instead of 7, because the seventh witness is
`autocommit-on-commits-one-level`, which is outside the contract there. Clauses not in the subset (locks, PPG, row locks,
unique keys, process stop, `%NOINDEX`, NULL encoding, collation, `SELECT *`, vectors, `$ZSTRIP`) ran only in the full
2026.2 cells. They hold there with both drivers, and every one of their mutants is killed.

## What differs: E-AUTOCOMMIT with driver 5.4.0 (both engines)

Named case `autocommit-on-commits-one-level`: a Native-API level is open and the driver's autocommit is already on (the
default). Then `setAutoCommit(True)` is called.

| | 5.3.2 (2026.1 and 2026.2) | 5.4.0 (2026.1 and 2026.2) |
|---|---|---|
| autocommit already on, one level open, `setAutoCommit(True)` | commits one level (`$TLEVEL` 1 -> 0; the write survives the later TROLLBACK) | **nothing** (`$TLEVEL` stays 1; TROLLBACK undoes the write) |
| two levels open, already on, `setAutoCommit(True)` | 2 -> 1 | **2 -> 2** |
| autocommit off, first write opened level 1, `setAutoCommit(True)` | commits it (1 -> 0) | commits it (1 -> 0) |

The two-case probe `versions/autocommit_probe.py` shows the same split on both engines (`ver-autocommit-probe-e261`,
`ver-autocommit-probe-e262`). So E-AUTOCOMMIT as revised after round r4 ("turning it on while a level is open commits one
level ... whether it was off or already on") describes driver **5.3.2**. With 5.4.0, `setAutoCommit(True)` commits one
level only when autocommit was off: it looks like a client-side no-op when the setting does not change. Neither the
contract nor its mutant `autocommit-on-keeps-txn` (which never commits) permits the 5.4.0 outcome. The contract needs a
driver switch for this half; that is the contract owner's change (`iris-contract/`, not edited by this lane).

Product impact: none found. The pin never calls `setAutoCommit` (grep over `iris_vector_graph/`, `src/`, `scripts/`).
Its only autocommit reading, `_write_txn._driver_autocommit_off` and `caller_transaction_level`
(`_write_txn.py:58-90`), answers the same with both builds (both expose `conn.autocommit`). A caller that turns
autocommit "on" again around IVG writes with a level open gets a commit with 5.3.2 and none with 5.4.0. That is the
caller's transaction, not IVG's.

## The version difference: driver or engine?

| Observation | 2026.1 x 5.3.2 | 2026.1 x 5.4.0 | 2026.2 x 5.3.2 | 2026.2 x 5.4.0 | Product premise (2026.3, 5.4.0) |
|---|---|---|---|---|---|
| SQL `COMMIT` at `$TLEVEL` 2 | -> 1 | -> 1 | -> 1 | -> 1 | -> 0 ("every level") |
| SQL `ROLLBACK` at `$TLEVEL` 2 | -> 1 | -> 1 | -> 1 | -> 1 | -> 0 |
| SQL `START TRANSACTION` inside a level | nothing | nothing | nothing | nothing | nothing |

Both client entry points of each build, `iris.dbapi.connect` and `iris.connect`, give the same answers
(`ver-sql-entry-probe-e261`, `ver-sql-entry-probe-e262`).

**Attribution.** Driver 5.4.0 does not produce the premise: on 2026.1 and on 2026.2, through either entry point, SQL
`COMMIT` and `ROLLBACK` end one level with 5.4.0 exactly as with 5.3.2. In each of the four cells, `sql-commit-ends-all`
is killed by 2 cases and `sql-rollback-ends-all` by 4. Engine 2026.2 Community behaves as 2026.1. The difference, if it is
real, lies in the 2026.3 engine (the product cites the AI build `irishealth:2026.3.0AI.113.0`) or in how the product
measured it. Neither can be checked here (`ver-avail-iris-2026.3`: no public 2026.3 image; the cited build is on an
InterSystems-internal registry). Recorded as finding **F-C1705** (`versions/findings.json`). F-C1705 is the version-difference record that
`CONTRACT.md` calls "F-C1701 candidate"; the id F-C1701 is already taken by module 17. The as-built main write path
(TSTART/TCOMMIT/TROLLBACK 1 through `Txn_Begin/End/Undo`) does not depend on either reading.

Within the subset and the full set, the 2026.1 contract is engine-independent between 2026.1 and 2026.2. The one
driver-dependent clause is E-AUTOCOMMIT's already-on half.
