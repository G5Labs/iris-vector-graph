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
  `iris session`: process-private globals, the non-incremental `LOCK`, `%SQL.Statement` dynamic SQL, `$VECTOR`,
  `$ZSTRIP`). Nothing is compiled into IRIS: the scratch tables `IVGAudit.T/S/E/F/C/D1/D2` are DDL tables whose
  storage the driver owns (`^IVGAudit<t>.N`); the functional index on `F` is `%iFind.Index.Basic`, a
  `%Library.FunctionalIndex` subclass shipped with IRIS. `iris-contract check` reports outcomes outside the
  contract, sharpness and mutant kills.

## Clauses (validated)

Every clause decided by observation has a `Semantics` switch in `src/lib.rs`; the mutants (the plausible alternative
readings) must each be killed by an observed outcome.

| Id | Clause | Contract | Decided by (named cases; random families also kill) | Mutants | Product reliance |
|---|---|---|---|---|---|
| E-GLOBALS | Globals | SET / KILL subtree / `$GET` / `$DATA`; a rollback restores a killed subtree | txn-kill-subtree-rollback, rand-vis | (structure) | every ^KG / ^IVG writer |
| E-NEST | Nesting | `TSTART` nests; inner `TCOMMIT` only lowers `$TLEVEL`; a later outer rollback undoes inner work | txn-nest-commit-inner, txn-rollback-one | rollback-one-undoes-all | Graph.KG.Txn, Ledger.Commit (Ledger.cls:390-418) |
| E-PARTIAL | Partial rollback | `TROLLBACK 1` undoes only the top level, globals and SQL rows alike | txn-rollback-one, sql-row-in-native-level | rollback-one-undoes-all | Txn.Undo, `_write_txn` |
| E-INCR | `$INCREMENT` | not undone by rollback | txn-incr-survives | incr-rolled-back | Adjacency.cls:57 (^IVG.AdjNoLock), LedgerRedact.cls:342 |
| E-PPG | Process-private globals | not undone by rollback; invisible to other processes | ppg-not-rolled-back, ppg-private | ppg-rolled-back | ^\|\|IVG.RedactStmt, ^\|\|IVG.LedgerStage, ^\|\|IVG.CypherRun |
| E-VIS | Visibility | no isolation for globals; SQL SELECT reads uncommitted rows (READ UNCOMMITTED) | txn-dirty-read, row-dirty-select | no-dirty-reads | liveness checks (LiveRows), readers, verify, save_snapshot |
| E-ROLLBACK-OTHER | Rollback over another's write | a rollback does **not** overwrite a node another process changed after this process wrote it | txn-physical-rollback | rollback-physical | concurrent writers without locks |
| E-SQL-START | SQL `START TRANSACTION` | does nothing when any level is open; else opens level 1 | sql-start-inside-native, sql-start-twice | sql-start-unless-sql-owns, sql-start-always | `_write_txn` plain path |
| E-SQL-END | SQL `COMMIT` / `ROLLBACK` statements | end **one** level | sql-commit-native-2, sql-rollback-native-2 | sql-commit-ends-all, sql-rollback-ends-all (product premise, 2026.3) | `_write_txn` plain path; see version note |
| E-DRV | Driver `commit()` / `rollback()` | `commit()` ends one level; `rollback()` ends **every** level | drv-commit-native-2, drv-rollback-native-2 | driver-commit-ends-all, driver-rollback-one-level | autocommit-off callers (`_write_txn.py:23-25`) |
| E-AUTOCOMMIT | Autocommit | default on; with it off the first DML opens a level SQL owns; **turning it on while a level is open commits one level**, as `commit()` does, whether it was off or already on and whoever opened the level (revised after round r4; env/explore-9); turning it off inside a transaction is outside the subset | autocommit-off-first-write, autocommit-on-commits-one-level | autocommit-on-keeps-txn (and E-DRV's) | `_driver_autocommit_off`; callers toggling autocommit around writes |
| E-LOCK-DEFER | Locks: deferral | an unlock inside a transaction, including release-all and a lock taken before it, takes effect when the outermost transaction ends; an immediate unlock releases at once | lock-deferred-in-txn, lock-deferred-pre-txn, lock-release-all-in-txn, lock-immediate | unlock-immediate-in-txn | head lock (Ledger.cls:394-396, LedgerRedact.cls:289), AdjW |
| E-LOCK-LIFE | Locks: lifetime | a lock not unlocked survives the commit | lock-survives-commit | — | — |
| E-LOCK-NAMES | Locks: names | hierarchical: a name conflicts with ancestors and descendants; siblings do not | lock-hier-child, lock-hier-parent, lock-siblings | flat-lock-names | ^IVG.AdjW vs ^IVG.AdjW(g) (Adjacency.cls:449-455) |
| E-LOCK-MODES | Locks: modes | shared locks are compatible; exclusive conflicts with shared, incl. across the hierarchy | lock-shared, lock-shared-parent-excl | shared-conflicts-shared | AdjW `#"S"` writers vs `#"E"` (Adj.cls:68,144) |
| E-LOCK-COUNT | Locks: counts | incremental | lock-incremental | non-incremental-locks | nested lock/unlock pairs |
| E-LOCK-NONINC | Non-incremental `LOCK` | releases every held lock first, then locks | lock-only-releases-others, lock-only-in-txn | — | `lock ^IVG.NKGBuild`, `lock ^IVG.AdjW` |
| E-LOCK-WAIT | Lock wait | a waiting lock is granted when the holder releases; timeout 0 answers `$TEST` | lock-wait-then-get | — | head lock waits (30 s), AdjW (5 s) |
| E-ROWLOCK | Row locks | a DELETE/UPDATE waits for a row another open transaction inserted or updated; after that transaction rolls back it affects nothing; an autocommit statement holds no row lock afterwards; a global SET takes no lock | row-delete-waits-insert(-rb), row-update-waits-update, row-autocommit-no-hold, row-global-write-no-row-lock | dml-ignores-row-locks | eraser's DELETEs vs concurrent writers (P-1201) |
| E-UNIQUE | Unique keys | INSERT of a key another transaction inserted fails at once (-119) | row-insert-dup-uncommitted | — | `_write_txn.is_duplicate` |
| E-STOP | Process stop | rolls back every level and releases every lock; a waiter proceeds | stop-rolls-back, stop-nested-levels, stop-releases-locks, stop-releases-row-lock | stop-commits | P-0001, interrupted redaction |
| E-CALLER | Caller identity | SQL on a cursor and the Native API on the same connection run in one server process (same `$JOB`) | exploratory probe (env/explore-2.log, test 7) | — | `_write_txn` docstring, Txn_Begin |
| **X-FX** | Functional index in the row's transaction | the index entries of a row are written by the row's own statement, in its process and transaction: visible at once to other processes (READ UNCOMMITTED), undone with the row by `TROLLBACK`, `TROLLBACK 1` (inner level only), SQL `ROLLBACK`, driver `rollback()` and process stop; an UPDATE moves the entry, a DELETE removes it, and their rollbacks restore it; the same through `%SQL.Statement` | fx-dirty-then-rollback, fx-rollback-one, fx-update-rollback, fx-delete-rollback, fx-sql-rollback, fx-autocommit-off-rollback, fx-stop-rolls-back, fx-term-path, fx-autocommit-visible; rand-fx | fx-outside-row-txn | Graph.KG.LabelIndex / AdjIndex `InsertIndex` / `DeleteIndex` (LabelIndex.cls:10-25, AdjIndex.cls:12-23); P-0801, P-0902; modules 03, 04, 08, 09, 11, 15 |
| **X-NOINDEX** | `%NOINDEX`, `%NOCHECK`, `BUILD INDEX` | `INSERT %NOINDEX` writes the row and **no index entry at all**: the functional index does not list it and the unique index does not hold its key, so a plain INSERT of that key is not refused and writes a second row; `%NOINDEX` alone still checks uniqueness (-119); `INSERT %NOCHECK` skips the unique check (a second row); `BUILD INDEX FOR TABLE` purges and rebuilds every index from the rows, **outside** the issuing process's transaction (its rollback leaves the rebuilt entries), and fails with -400 (#5798, extent lock) while any transaction, the issuer's included, holds a row of the table; **after `BUILD INDEX` on a table, a DB-API INSERT (not `%NOINDEX`) of a key already present raises DataError `<LIST ERROR>` instead of SQLCODE -119** and writes nothing, until the table's storage is emptied, while ObjectScript `%ExecDirect` and `INSERT %NOINDEX` still report -119 (revised after round r5; env/explore-10); a `%IGNOREINDEX *` scan reaches every row | noindex-insert-then-build, noindex-in-txn-rollback, noindex-term, noindex-unique-not-maintained, noindex-insert-checks-unique, nocheck-second-row, nocheck-noindex-term, build-index-not-in-txn, build-index-needs-extent, build-index-dup-report, build-index-rebuilds-all; rand-fx | noindex-ignored, nocheck-still-unique, build-index-in-txn, rebuilt-table-dup-reports-119 | bulk_loader.py:8-11, 157-183 (`%NOINDEX %NOCHECK`, rebuild after); schema.py:1782-1788, 3051-3056; BUILD INDEX (module 11) |
| **X-DDL** | DDL and transactions | CREATE / DROP TABLE and ALTER TABLE ADD COLUMN take effect at once and are visible to other processes before commit; issued inside a transaction they **are undone by its rollback** (catalog, columns, and a dropped table's rows), on both client paths, while the transaction stays open and its earlier writes are still undone; DDL at level 0 with autocommit off opens no transaction; DROP TABLE fails with -110 while another transaction holds a row of the table; CREATE of an existing table -201, DROP / DML / SELECT of a missing one -30 | ddl-create-in-txn, ddl-create-commit, ddl-drop-in-txn, ddl-drop-waits-row-lock, ddl-visible-at-once, ddl-errors, ddl-under-sql-txn, ddl-autocommit-off, ddl-term-in-txn, alter-in-txn-rolled-back, alter-in-txn-other-process, ddl-create-rollback-fresh-statement; rand-ddl | ddl-not-rolled-back, ddl-commits-open-txn | schema init and migrations (schema.py, embeddings.py:254, vector_utils.py:195); DROP TABLE after TCOMMIT (module 18); modules 01, 03, 04, 06, 18 |
| **X-NULL** | NULL and the empty string | a DB-API parameter `''` (and `'\x00'`) is stored as the SQL empty string, `None` as NULL; an ObjectScript `%ExecDirect` parameter `""` is stored as **NULL** (P-0706) and `$C(0)` as the empty string; literals `''` / `NULL` alike on both paths; the DB-API reads `''` / `None`, an ObjectScript result set reads the empty string as **`$C(0)`** and NULL as `""`; `COALESCE(v, '') = COALESCE(?, '')` matches NULL and empty rows alike for a `None`, `''`, `""` or `$C(0)` parameter | enc-dbapi-writes, enc-term-writes, enc-dbapi-chr0, enc-coalesce-guard; rand-enc | dbapi-empty-param-null, objectscript-empty-param-empty, objectscript-reads-empty-as-empty, coalesce-c0-differs | GraphKey.cls:34-84 ($Char(0) transport), VarLength.cls:35-36, TraversalPaths.cls:281; graph guards `COALESCE(graph_id, '') = COALESCE(?, '')` (schema.py, spec 230 FR-005); P-0706 |
| **X-STMT** | Statement atomicity | a failing multi-row `INSERT ... SELECT` leaves none of its own rows (-119), at level 0 and inside a transaction, which stays open; with autocommit off at level 0 a DML statement that **fails** still opens the transaction, one that finds no row does not | stmt-atomic-in-txn, stmt-atomic-autocommit, stmt-ok-rolled-back, stmt-atomic-term, autocommit-off-failed-dml; rand-stmt | statement-not-atomic, failed-dml-opens-nothing, empty-dml-opens-txn | P-0803 (`_write_txn`), INSERT ... SELECT guards (module 08) |
| **X-ORDER** | Subscript collation | `$ORDER` and the Native API's `nextSubscript` visit canonical-format numbers first, in numeric order, whatever their magnitude (observed to 41 characters), then every other string by code point (`"01"`, `"1.0"`, `"+1"`, `"-0"`, `".5"` vs `"0.5"`, `"1E2"` are strings); `nextSubscript` answers canonical strings | order-collation; rand-order | string-collation | P-0705, snapshot.py:1612-1692 (P-1802); modules 03-07, 09, 10 |
| **X-STAR** | `SELECT *` | lists the declared columns in declaration order, without the row id; `ALTER TABLE ADD COLUMN` appends | select-star-order, alter-add-column-last | select-star-alphabetical, select-star-id-first, add-column-first | snapshot.py:866-874, 1287-1292 (P-1801) |
| **X-TLEVEL-SQL** | `SELECT $TLEVEL` | reports the process's level (both paths); a query (`SELECT`, `SELECT $TLEVEL`) with autocommit off opens no transaction | sql-tlevel, sql-tlevel-term | select-opens-txn | `caller_transaction_level` (_write_txn.py:64-90) |
| **X-VEC** | Vectors (availability) and `$VECTOR` | `VECTOR_COSINE` and `VECTOR_DOT_PRODUCT` exist (0.6 for (1,0)·(0.6,0.8)), `VECTOR_L2` **does not** (-359), with `TO_VECTOR(text, DOUBLE)`; a `$VECTOR` element SET in a global reads back, is undone by a rollback, and the Native API cannot read the value (`get` raises `<LIST ERROR>`, `isDefined` answers 1) | vec-sql-functions, vec-global, vec-native-get | vector-l2-available (product premise P-1710), vector-set-not-rolled-back, native-api-reads-vectors | dbapi_utils.py:256-272 (metric `L2` -> `VECTOR_L2`); modules 00, 06, 16, 17, 18 |
| **X-ZSTRIP** | `$ZSTRIP` | class C = code points 0-31 and 127-159; class W = **9, 32 and 160 only** (LF, VT, FF, CR are not whitespace); actions `*` all, `<` leading, `>` trailing, `=` contiguous repeats of one character reduced to one; extra characters as the third argument | zstrip-class-c, zstrip-class-w, zstrip-product-masks; rand-zstrip | zstrip-c-ascii-only, zstrip-w-space-only | GraphKey.cls:44, Gen.cls:621 (`*C`); SqlPrivilege.cls:24, EmbedQueue.cls:222,251, FHIRGraph.cls:1781 (`<>W`, `<=>W`); SortKey.cls:91-93 (`<`/`>` with "0") |

**Freedom (both outcomes permitted, not yet sharpened):** an INSERT of a key whose row another open transaction
deleted. One round observed the waiting branch; the other branch (proceeds under a new row id) was never observed and
stays permitted until a witness or a source settles it.

**Refused inside the clauses (outside the subset, the model answers `refused`, the generators avoid them):**
- `INSERT %NOCHECK`, and a failing `INSERT ... SELECT` or autocommit-off INSERT, on a table `BUILD INDEX` rebuilt
  (the report of the failure is not pinned down there);
- by-key UPDATE / DELETE, and the unique check of an INSERT, on a key that has several rows or a row in no index
  (`%NOINDEX`/`%NOCHECK` duplicates): which rows a by-key statement reaches depends on the plan (explore-5 J3: one
  `WHERE k = '1'` reached the `%NOINDEX` row, another did not; UPDATE / DELETE by key changed one of three rows), and
  the unique-check failure reached the DB-API as `<LIST ERROR>` (DataError) instead of SQLCODE -119;
- a process's use of a table after a rollback undid DDL on it, if that process compiled a statement against the table
  while the DDL was in effect: the cached statement keeps the undone definition (explore-4 B1 and explore-6 K2: a
  SELECT still returned rows of a table whose CREATE was rolled back, a cached INSERT failed with -400
  `<CLASS DOES NOT EXIST>`; the smoke run: `SELECT *` kept an undone ALTER's column). A process that compiled nothing
  against the table meanwhile finds the catalog's state (ddl-create-rollback-fresh-statement);
- `INSERT ... SELECT` or `PutE` while another process holds row locks on the target; `$ORDER` over a canonical numeric
  subscript longer than 41 characters.

## Engine observations recorded by the extension (with consequences for the product)

- **DDL is transactional on 2026.1** (X-DDL): the common reading (and the orchestrator's starting hypothesis) that
  CREATE / DROP TABLE are not undone by a rollback is refuted on both client paths; the product's choice to run DDL
  after `TCOMMIT` (module 18) is therefore necessary, not only cautious. A rollback that undoes DDL leaves cached
  statements of other processes stale (above).
- **`%NOINDEX` rows are in no index at all** (X-NOINDEX): besides the functional index, the unique index and the
  bitmap extent skip them, so `DELETE FROM t` without WHERE does not reach them (explore-4 A11: 6 of 8 rows deleted)
  and a plain INSERT of their key writes a duplicate. `ORDER BY` on the declared unique key returns one row per key
  when duplicates exist (explore-6 K3).
- **After `BUILD INDEX FOR TABLE`, a duplicate INSERT through the DB-API is not reported as -119**: it raises
  `DataError: <LIST ERROR> Incorrect list format, unsupported type for IRISList; Details: type detected : 0` (nothing
  is written), for rebuilt keys and for keys the filer wrote after the build alike, on a plain table as on the iFind
  table; ObjectScript sees -119 (env/explore-10, round r5). The text matches neither "unique" nor "-119", so
  `_write_txn.is_duplicate` (_write_txn.py:46-49) does not classify it: after the bulk loader's rebuild (bulk_loader.py
  157-183), `schema.rebuild_indexes` or module 11's `BUILD INDEX FOR TABLE`, an idempotent re-insert of an existing
  key surfaces as an error instead of "already there". Candidate finding for modules 03 / 08 / 11 (not reproduced on
  the product's tables here: AUDITENV holds no product classes).
- **`BUILD INDEX` is not part of the caller's transaction** and needs the extent lock: -400 while any open
  transaction holds a row of the table, after a 10 s wait when the holder is another process.
- **The Native API cannot read `$VECTOR` values** (`<LIST ERROR>`, type 16): a Native-API walk of a global that holds
  `$VECTOR` data (snapshot export, P-1802) fails on that node (module 18).
- `TO_VECTOR(text, 'double')` (quoted, lower case) is SQLCODE -262; the product writes the unquoted keyword `DOUBLE`.
- **A failing statement's DB-API error carries the connection's last ObjectScript error**: after a Native-API
  `tCommit` at level 0 (`<COMMAND>`), the next failing statement reports SQLCODE -119 *and* `[Error: <<COMMAND>>]`
  (env/explore-8). The driver classifies by SQLCODE first (round r3 had classified two such reports as `<COMMAND>`);
  product code that classifies an exception by an ObjectScript error name before its SQLCODE would misread it.

## Results

| Run | Cases | Outside contract | Singleton cases | Mutants killed |
|---|---|---|---|---|
| `env-contract-r1` (seed 20261113, first draft; stopped at 157 by the connection cap) | 157 run | 15 (draft wrong; revised from these observations) | — | 17/17 |
| `env-contract-r2` (seed 7331, cross-validation of the revision on fresh schedules) | 283 | **0** | 282 | **17/17** |
| `env-contract-selftest` (explorer, 2 processes x 16 ops, depth 6, bounded) | — | invariants hold | — | control caught in 2 steps |
| exploration for the extension (`env-ext-explore-4..10`; `env-ext-smoke-r3`: 60 new cases, seed 11) | 60 | 2 (both revised: `$ORDER` numeric collation has no magnitude bound; a stale cached statement after an undone ALTER is outside) | — | 40/40 |
| `env-ext-r3` (seed 4242, all clauses: 43 + 50 named, 4 x 60 + 6 x 30 random) — **gate not met, retained** | 513 | 2 (rand-stmt-4242-21/-23: the driver classified SQLCODE -119 carrying a stale `[Error: <<COMMAND>>]` as `<COMMAND>`; driver fixed to classify by SQLCODE, env/explore-8) | 511 | 40/40, but empty-dml-opens-txn and failed-dml-opens-nothing only by those two cases (named case autocommit-off-failed-dml added) |
| `env-ext-r4` (seed 9091, fresh: all named incl. the new case, 4 x 60 + 6 x 30 random, fixed driver) — **gate not met, retained** | 514 | 2 (rand-stmt-9091-9/-15: `setAutoCommit(True)` with a level open committed it; the model only set the flag; revised, E-AUTOCOMMIT) | 513 | 40/40 |
| `env-ext-r5` (seed 6061, fresh: all named incl. autocommit-on-commits-one-level, 4 x 60 + 6 x 30 random) — **gate not met, retained** | 515 | 1 (rand-fx-6061-1: after BUILD INDEX a duplicate DB-API INSERT raised `<LIST ERROR>`, not -119; revised, X-NOINDEX; the r4 autocommit revision held) | 514 | 41/41 |
| **`env-ext-r6`** (seed 2718, fresh: cross-validation of the r4 and r5 revisions; all named incl. build-index-dup-report, 4 x 60 + 6 x 30 random) — **gate met** | 516 (96 named + 420 random) | **0** | 515 | **42/42** (each extension mutant by a named case) |
| `env-ext-selftest-r6` (explorer, 2 processes x 21 ops incl. functional index / %NOINDEX / BUILD INDEX / DDL, depth 6, bounded; 2 new invariants; the model of round r6) | — | invariants hold (314,202 states) | — | control caught in 2 steps |

The revision after round 1 was driven only by engine observations; round 2 used a new seed and two new case families
(random row-lock schedules, terminal cases) and met the gate with no further change. The extension's clauses were
drafted from exploratory probes (env/explore-4..10, registered as `env-ext-explore-*`), revised from the smoke run's
two outside outcomes (`env-ext-smoke-r3`), checked by round r3 (gate not met: a driver classification error and two
mutants without a dedicated case) and round r4 (gate not met: the new statement family reached an existing verb,
`setAutoCommit(True)` inside a transaction, that the model got wrong; revised from those observations and
env/explore-9), round r5 (the r4 revision held; gate not met: the duplicate report after BUILD INDEX; revised from
that observation and env/explore-10), and decided by round r6 on a fresh seed with no change to the model after r5.
Every revised model also reproduces the earlier rounds' observations (r2, r4, r5: 0 outside; r3's two outside
outcomes are the retired driver classification).

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
Likewise `VECTOR_L2` (P-1710) does not exist here (X-VEC; the mutant encoding the premise is killed).

## Outside the semantic subset (refused, never claimed)

Engine-level: ECP, mirroring and multi-node; journal restore and crash recovery of the instance; SQL isolation levels
other than the default and `%NOLOCK`/`%NOJOURN`; **lock escalation thresholds** and the escalating lock type (`#"E"`
is treated as exclusive; the threshold depends on per-process lock counts and configuration that the subset cannot
pin down soundly); lock-table capacity; timing (lock timeouts are modelled as wait/no-wait, DDL and BUILD INDEX lock
timeouts as their final SQLCODE); `$SYSTEM.Process` other than Terminate; the cases above refused inside clauses.

Each module's `env_features` (modules/NN.json) is mapped in `COVERAGE.json` to an in-contract clause id, to
availability-only, or to outside-subset with the reason; a module's `3.2-coverage` gate stays open while any of its
features is outside. The reasons and the modules that rely on them:

| Outside the subset | Modules relying on it |
|---|---|
| %DynamicObject / JSON functions | 01, 03, 04, 05, 06, 07, 08, 10, 11 |
| class dictionary and run-time compilation (compiling is out of the audit's scope) | 01, 03, 04, 06, 09, 17, 18 |
| embedded SQL (`&sql`) compiled into classes: assumed equal to dynamic SQL (premise E-1), untested; `%SQL.Statement` is in the contract | 01, 02, 03, 04, 05, 06, 10 |
| SQLCODEs other than -30, -110, -119, -201, -359, -400 | 01, 02, 03, 04, 05, 06, 08 |
| embedded Python (needs irispython in the container) | 07, 09, 10, 16, 17 |
| engine limits (long strings, subscript length, bound-parameter count) | 07, 09, 10, 15, 17 |
| iFind search semantics (tokenizer `%iFind.Utils.Analyze`, word dictionary, ranking); only the per-row entries' transaction behaviour is X-FX | 01, 03, 06, 07, 08 |
| pure functions and clocks ($ZCRC, SHA, GUID, $RANDOM, $HOROLOG, DATEDIFF) | 05, 06, 09, 10, 11 |
| result-prefix queries (TOP / LIMIT / FETCH FIRST) | 01, 02, 03, 06, 11 |
| web dispatch, roles and SQL privileges | 01, 07, 09, 15, 16 |
| streams | 01, 04, 09, 11 |
| $LIST semantics, $NAME, $LISTVALID | 08, 09, 10, 18 |
| HNSW vector index maintenance and build | 01, 06, 17, 18 |
| INSERT OR UPDATE | 06, 15, 18 |
| JOB / WorkMgr processes | 04, 09, 10 |
| object filing (%OpenId / %Save concurrency), triggers, foreign keys, IdKey of persistent classes | 11, 15, 18 |
| journaling (the audit's oracle, not a clause) | 07, 11, 18 |
| IRISTEMP globals | 09, 10 |
| compiled SQL routines (CREATE FUNCTION / PROCEDURE, [SqlProc]) | 01, 08 |
| Task Manager | 06, 15 |
| catalog views other than TABLES / COLUMNS, default-schema resolution, namespaces | 10, 15, 17 |
| management APIs (%SYS.ProcessQuery, KillProcess, GetVersion, console log) | 09, 16 |
| named-index `%IGNOREINDEX` forms (only `%IGNOREINDEX *` is exercised) | 01, 04 |
| $ZF callouts; %Regex; EMBEDDING(); SQL text parsing; generated-SQL collation functions; the bitmap extent and index-driven full-table DML; row-id allocation; %Status errors through the Native API; Native API subscript validation; cross-connection effects of %BuildIndices | 08, 10, 06, 17, 18 (one each, see COVERAGE.json) |
| absent on Community 2026.1: InterSystems FHIR server storage, %AI classes | 15, 16 |

Module 00's features are all in the contract or availability-only (its `3.2-coverage` gate depends only on the
contract's results); every other module keeps the gate open for the reasons listed in `COVERAGE.json`
(`modules.NN.open_because`).

## Reproduce

```bash
source experiment/playbook-completion/environment.sh
cd experiment/playbook-completion/iris-contract
CARGO_TARGET_DIR=$RUN_DIR/target/iris-contract cargo build --release --offline
bash run-round.sh $RUN_DIR/env/rN <seed>                  # cases.py, then driver.py chunk by chunk under locks.sh iris
$RUN_DIR/target/iris-contract/release/iris-contract check $RUN_DIR/env/rN/cases.json $RUN_DIR/env/rN/observed.json
$RUN_DIR/target/iris-contract/release/iris-contract selftest
python coverage.py --check                                # COVERAGE.json from modules/NN.json
```
