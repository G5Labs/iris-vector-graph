# IRIS environment contract: coverage of the modules' features (lane contract-2, gate 3.2-coverage)

Pin `3eaa79cf` (unchanged; `check-product-scope.sh` passes). Engine IRIS 2026.1 Community (Build 234U), dedicated
container; client `intersystems-irispython` 5.3.2 (the pin's `uv.lock`) unless a run says 5.4.0. Namespaces: AUDITENV
(contract cases, no product classes; scratch `^IVGAuditEnv`, `IVGAudit.T`) and AUDITCORE (the pin's own compiled
classes, deployed by its own deploy path; only rows under the test prefix `env2e1` were written, and removed).
Nothing was compiled. The contract crate is a copy (`contract-2/contract/`); `iris-contract/` (round r6) is untouched.

**Result.** For each of the 15 open module cells (01-11, 15-18), a mechanical scan of the code the module owns lists
every IRIS feature it uses, and every listed feature is classified: inside an r6 clause, validated by this lane, or
outside the contract with a named premise and its consequence (`coverage.json`, 0 unclassified, `env2-coverage-2`; its first registration `env2-coverage` misstated the number of premise families as 40: 57 are defined, 54 used). By
the gate's definition the cells can close at method level; the outside premises stay **assumed** (they are not shown
to hold). The lane validated premise E-1 (the pin's compiled embedded SQL behaves as the dynamic SQL the contract
models) and nine further clauses, and found one product defect (F-C1720).

## 1. Premise E-1: the pin's compiled embedded SQL against the contract

The pin's own compiled `&sql` was called through the Native API on the DB-API connection (one server process with
the case's transaction verbs, dynamic SQL and driver calls), exactly as `driver.py` drives dynamic SQL
(`contract/native/driver_e1.py`, `cases_e1.py`). Each pin method is an operation of the copied model
(`contract/src/lib.rs`, `Op::Emb*`), whose effect is the dynamic statement's (E-1), so the same permitted-set
machinery and the same clause ids decide it; E-1 mutants encode the plausible ways an embedded statement could differ.

| Pin method (at the pin) | Embedded statements | Model table |
|---|---|---|
| `Graph.KG.EdgeScan.RegisterDefaultNode` (EdgeScan.cls:247-258) | `SELECT 1 INTO :x ... WHERE node_id = :p AND graph_id = ''`, then `INSERT ... VALUES (:p, '')`, -119 tolerated | N (nodes, default graph) |
| `Graph.KG.Adjacency.RetractTemporalRows` (Adjacency.cls:650-692) | `DELETE FROM rdf_edges WHERE s, p, o, COALESCE(graph_id,'') = COALESCE(:g,'') AND qualifiers %STARTSWITH ...` | R (rdf_edges, graph env2e1g) |
| `Graph.KG.GraphVerify.VerifyGraph` (GraphVerify.cls:40-79) | `DECLARE ... CURSOR`, `OPEN`, `FETCH` over rdf_edges (counts.sqlEdges) | R |
| `Graph.KG.GraphStores.VectorRouteGuard` (GraphStores.cls:304-318) | `SELECT TOP 1 table_name INTO :t FROM embedding_registry ...` | G (embedding_registry) |
| `Graph.KG.Adjacency.AssertTemporalRow` (Adjacency.cls:575-620) | two `INSERT ... SELECT :h WHERE NOT EXISTS (...)`, host variable `$Char(0)` or `""` | N, R0 (default-graph edges) |
| `SELECT Graph_KG.Txn_Begin/Txn_End/Txn_Undo(?)` (SqlProcs.cls:168-180 over Txn.cls:19-58) | `[SqlProc]` methods doing TSTART / TCOMMIT / TROLLBACK 1 | (process levels) |

| Run | Cases | Outside | Singleton | Mutants killed |
|---|---|---|---|---|
| `env2-e1-r1` (seed 7177; 27 named + 40 random `rand-e1`) | 67 | **0** | 67 | **14/14**: emb-select-committed-only, emb-ignores-driver-autocommit, emb-empty-host-var-empty, emb-ignores-row-locks, emb-own-txn, maxlen-not-enforced, sql-select-committed-only, and 7 r2 clause mutants (rollback-one-undoes-all, dml-ignores-row-locks, stop-commits, sql-rollback-ends-all, driver-rollback-one-level, autocommit-on-keeps-txn, failed-dml-opens-nothing) |
| `env2-e1-r1-journal` (journal oracle over r1) | 15 named | 0 row writes outside the transaction | — | footprints of 6 methods match their tables; embedded and dynamic nodes INSERT and rdf_edges DELETE have the same journal signature |
| `env2-e1-r2` (seed 8221; S-1: 9 named + 30 `rand-s1` + 15 `rand-e1`) | 54 | **0** | 54 | **8/8** (sqlproc-levels-end-with-statement by 5 named cases, and 7 clause mutants) |

What the pin's embedded statements were observed to do (each the dynamic statement's permitted outcome): an
embedded INSERT / DELETE inside TSTART is seen dirty by other processes and undone by TROLLBACK, by TROLLBACK 1 at its
own level only, by the SQL ROLLBACK statement (one level), by the driver's rollback() (every level) and by a process
stop (E-NEST, E-PARTIAL, E-SQL-END, E-DRV, E-STOP); it holds its row lock to the end of the transaction, so a dynamic
DELETE / UPDATE of the row waits and after a rollback affects nothing, and a dynamic INSERT of the key fails at once
with -119 (E-ROWLOCK, E-UNIQUE); at level 0 it holds no lock afterwards; with the driver's autocommit off it opens the
level the driver's rollback() ends, a failing one included (E-AUTOCOMMIT, X-STMT); the embedded DELETE waits for a row
another transaction inserted and deletes nothing after its rollback; embedded SELECT INTO, SELECT TOP 1 INTO and a
cursor read uncommitted rows and miss uncommitted deletes (E-VIS); a host variable `""` binds as NULL (graph_id NOT
NULL: SQLCODE -108, nothing written), `$Char(0)` and the literal `''` as the empty string (X-NULL; the pin's own
premises GraphVerify.cls:50-56 and Adjacency.cls:583 hold); an over-long key reports -104 on both paths. The journal
shows the statement-level nested level ("BeginTrans with level" / "CommitTrans Pending with level") for embedded and
dynamic statements alike, the row-id counter written outside the transaction, and the pin's AdjIndex writing
`^KG("out"/"in")` in the row's transaction (X-FX holds for the pin's own functional index, not only for the iFind
carrier) while its `$Increment` counters `^KG("gen")` and `^KG("__version")` are written outside it (E-INCR).
S-1: `Txn_Begin` opens a level that stays open after the SELECT, `Txn_End` commits only while `$TLEVEL >= level`,
`Txn_Undo` takes back only IVG's level, and with autocommit off `Txn_Begin(1)` opens the caller's level first, which the
driver's commit() / rollback() ends: the premise of `_write_txn.py` / Txn.cls:1-11 holds on 2026.1 with driver 5.3.2.

Residual of E-1 (by analogy, not observed): embedded UPDATE, cursors over many rows, and embedded text using `%INLIST`,
`%STARTSWITH` (exercised only on its matching row) or a named `%IGNOREINDEX` (family `esql-other`).

## 2. Clauses added and validated (round env2-r1, AUDITENV)

Drafted from probes (`env2-x2-explore`), smoke-checked (`env2-x2-smoke`: 76 cases, 0 outside, 28/28 mutants, no
revision), decided on a fresh seed by **`env2-x2-r1`: 190 cases (40 named + 25 random per family), 0 outside, 189
singleton (max 6: TOP without ORDER BY), 29/29 mutants, each X2 mutant killed by a named case.** Model: `contract/src/x2.rs`
(JSON, $LIST) and `lib.rs` (`select_top`, `insert_many`, `upsert_run`, `data_nodes`, MERGE, ZKILL); driver
`native/driver_x2.py` (terminal values cross as code points); cases `native/cases_x2.py`.

| Id | Clause (validated) | Mutants (killed by) | Product reliance |
|---|---|---|---|
| X2-JSON | `%Set`/`%ToJSON` keep insertion order, a re-`%Set` keeps the key's place; a parsed duplicate key keeps the last value at the first key's place; a number set from ObjectScript is written canonical with a leading zero (`0.5`, `-0.25`, `0.0000001`, `2.0`->`2`, `007`->`7`); a parsed number keeps its JSON text (`1.50`, `1e2`, `-0.0`, `2.0`); `%Get` of a number answers its ObjectScript value (`1.5`); booleans `true`/`false`, read back 1/0; null reads "" with type `null` and is defined, a missing key "" / `unassigned` / 0; `"`, `\` and code points < 32 escaped (`\n \t \b \f \r`, else `\u00xx`), `/`, DEL and non-ASCII raw; invalid text throws | sorted-keys, number-objectscript-form, bool-as-number, dup-first-wins, reparse-canonical, escape-slash, escape-nonascii, null-get-text, set-moves-last | features in 01, 03-18 (ledger payloads and receipts in 11-14; qualifiers: AssertTemporalRow's `{"temporal":true...` prefix that RetractTemporalRows tests (Adjacency.cls:585-590, 661) holds; Python's `json.loads` reads the leading-zero numbers) |
| X2-LIST | `$LB` undefined elements: `$LIST` -> `<NULL VALUE>`, `$LISTGET` default only for undefined or missing (a defined "" is ""), `$LISTDATA` 0, `$LISTNEXT` visits them; `$LISTFIND` compares as strings from after `start`; `$LISTSAME($LB(1),$LB("1"))` 1 while the encodings differ; `$LISTTOSTRING` of an undefined element `<NULL VALUE>` unless flag 1; `$LISTFROMSTRING` keeps empty fields defined; the driver's `IRISList` over `getBytes` decodes integers as int, decimals as Decimal (`-0.25`), strings as str, undefined as None | undefined-item-empty, get-default-on-empty, find-typed, same-typed, tostring-skips-undefined, walk-skips-undefined, irislist-int-as-str | features in 01, 03-18 (list-encoded keys and records; snapshot export) |
| X2-TOP | `TOP n` / `LIMIT n` / `LIMIT n OFFSET m` over `ORDER BY` a VARCHAR column: SQLUPPER string order (`1, 10, 2, 3, 9, a, B, c`), `DESC`, `%EXACT` = `$ORDER` collation (numbers first); `TOP 0` no row; reads uncommitted rows (E-VIS); without ORDER BY any n rows | top-default-order-exact, top-zero-means-all, limit-offset-ignored, sql-select-committed-only | features in 01-10, 12, 14-17 (first-row lookups, paging) |
| X2-BATCH | DB-API `executemany` with several rows: a refused row (-119) is skipped without an error, rowcount counts the written rows, later rows are written; one row raises -119; rows belong to the open transaction, hold their row locks, open the level with autocommit off | raises-on-dup, atomic, single-row-skips | 01, 03, 16 (bulk writers); confirms the product's own premise (`_batch_check.py:1-4`, `_widths.py:4`) |
| X2-IOU | `INSERT OR UPDATE` inserts an absent key, updates a present one; waits for a row another transaction holds; after that transaction rolls back an insert of the key it fails with **SQLCODE -109** (writes nothing); after a commit it updates | iou-retries-insert, iou-ignores-row-locks | 06, 15, 18: upserts can surface -109 under a concurrent rolled-back writer |
| X2-QUERY | `$QUERY` walks data nodes depth-first in `$ORDER` collation (`1, (1,"x"), 2, 10, "b"`); `$QUERY(ref,-1)` is the previous data node; `$QLENGTH`, `$QSUBSCRIPT` | query-string-order | 05, 09, 12 (global walkers) |
| X2-MERGE | `MERGE` copies a subtree, onto an existing one overwrites matching nodes and keeps the others, and a rollback undoes it; `ZKILL` removes the node's value only and a rollback restores it | merge-not-rolled-back, merge-replaces-target, zkill-kills-subtree | 05, 09, 10, 13, 15 (copies of subtrees, caches) |
| E-1 | see section 1 | 6 E-1 mutants | the pin's `&sql` is all in code owned by 04 (Adjacency, EdgeScan, GraphStores, GraphVerify, TraversalBuild) and 12 (Eraser); its SQLCODE / NOT NULL observations also classify `SQLCODE` handling in 01-08, 10, 15, 17 |
| S-1 | see section 1 | sqlproc-levels-end-with-statement | the mechanism of every `[SqlProc]` / `CALL` (01-17); routine-specific behaviour stays P2-SQLROUTINE |

## 3. Contract observations with product consequences

- **FETCH FIRST kills the Python client with the pin's locked driver (F-C1720, S2).** Every FETCH FIRST form ended the
  client process with SIGSEGV on 5.3.2 while TOP / LIMIT answered and the server logged nothing
  (`env2-fetchfirst-probe`); 5.4.0 answers all of them (`env2-fetchfirst-probe-d540`). Through the pin,
  `IRISGraphStore.query_nodes(limit=2)` without a label filter (it sends `FETCH FIRST 2 ROWS ONLY`,
  iris_sql_store.py:1177-1180) killed the process; its control and the engine's Cypher LIMIT paths answered
  (`env2-fc1720-query-nodes`, driver control `env2-fc1720-query-nodes-d540`). FETCH FIRST stays outside (P2-FETCH).
- **executemany skips a refused row silently** (X2-BATCH): matches the product's own premise; any caller that expects
  an exception per duplicate in a multi-row batch would miss it (the product compensates with `_batch_check`).
- **INSERT OR UPDATE fails with -109** when a concurrent transaction that inserted the key rolls back (X2-IOU): no
  product premise found about it; upserts are not "always succeed".
- **JSON numbers**: `%ToJSON` writes valid JSON numbers (leading zero), parsed number text is kept verbatim (so
  `2.0` from Python stays `2.0`), and booleans set with type "boolean" are `true`: the qualifier-prefix premise holds.
- **r6 mutant gap (contract, not product)**: the r6 model applied its `no-dirty-reads` mutant to global reads only;
  `sql-select-committed-only` (new) is killed by r6's own `row-dirty-select`, so E-VIS for SQL was decided by r6 data.
- **$SEQUENCE** (explored, not validated): unique across processes, ranges per process (one process got 7 while the
  global read 10), not undone by a rollback.
- **AUDITCORE residue**: 0 test rows remain; the pin's AdjIndex left its non-transactional counters
  `^KG("gen","env2e1g",...)`, `^KG("gen",0,"env2e1-n5"|"env2e1-n6")` and `^KG("__version")` increments (by design);
  not removed.

## 4. Method of the enumeration (`enumerate.py`, `env2-coverage-2`)

- **Ownership**: `models/breadth-c/inventory.json`. A one-owner file belongs to its module; in a multi-owner file an
  entry's range goes to its owners and every other line to all owners. ObjectScript method entries span only their
  signature line, so a multi-owner class's method bodies count for all its owners (over-approximation).
  A module's cell covers the code it owns; a feature reached through a call into another module's code is classified
  in that module's cell (the union of cells covers every site).
- **Lexing** (no feature from a comment or docstring): ObjectScript with strings and `//`, `;`, `#;`, `/* */` comments
  removed, `&sql(...)` bodies across lines, `Storage`/`XData` skipped, `Language = python` bodies as Python; Python
  with `tokenize` and `ast` docstrings; string literals that hold SQL (a statement pattern or an IRIS SQL token) and
  ObjectScript text held in Python strings are lexed too; `.sql` files; deploy files (cpf keys, `iris` CLI verbs).
- **Token classes** (every member is a feature): intrinsic functions and special variables, `$$$` macros, system classes
  (`##class(%...)`, `$SYSTEM.X.Y`, `Extends`), `%`-methods and `%`-names in strings, commands with environment semantics,
  LOCK forms (incremental, unlock, non-incremental, release-all, types, timeouts, local and indirect names), global kinds
  (product, process-private, IRISTEMP, system, extended), indirection, `SQLCODE` / `%msg`, class members (index types,
  foreign keys, triggers, SqlProc, generators); embedded SQL verbs; SQL verbs, DDL forms, `%` hints and operators,
  functions, clauses, catalog views, constraints, types, index types, system-schema tables; Python Native API and DB-API
  calls, `iris.*`, classMethod targets, DB-API error classes, IRIS error names, SQLCODE literals.
- **Classification**: first matching rule (`RULES`), status inside (r6 clause ids) / validated (`VALIDATED.json`,
  written by `validated.py` from the registry: a clause counts only when all its runs are registered with pass) /
  outside (premise family with consequence). A token no rule matches is `unclassified` and keeps the cell open.
- **Self-test** (`env2-coverage-selftest`): a seeded unknown intrinsic, system class and SQL function in module 02 are
  reported and the cell opens; a LOCK in a comment is not reported; a seeded TSTART / `$SEQUENCE` in module 05 is found
  at its site; removing the JSON rules leaves all 14 JSON features of module 11 unclassified.
- **Cross-check** (`env2-coverage-crosscheck`): every outside reason the breadth lanes' hand-curated `env_features`
  gave a module (iris-contract/COVERAGE.json) is found by the mechanical scan in that module, at its cited site in the
  owning module, or the cited lines hold no IRIS token (prose), or is explained (4 cases, listed in `crosscheck.py`);
  11 reasons name semantic limits or the journal oracle and are carried as `sem.*` outside features. 0 misses.
- **Limits of the scan**: SQL or ObjectScript text assembled at run time from variables is seen only through its
  literal pieces; dynamic dispatch (`$ClassMethod`, `$Method`, `@`) is seen as dispatch, not as the target's features
  (the target's features are classified where the target is owned).

## 5. Open (exact)

- The outside premises in the families table stay **assumed** for every module that uses them; closing the cell
  marks them, it does not discharge them. The largest by use: P2-SQLEXPR (SQL expression and query semantics),
  P2-PURE, P2-STATUS, P2-DICT, P2-CATALOG, P2-OBJ (object filing), P2-JSON residual (`%GetIterator`, `%Size`, `%Push`,
  JSON literals with content, `%Library.DynamicObject` columns, SQL JSON functions), P2-FK (foreign-key checks under
  concurrency), P2-HNSW, P2-IFIND (tokenizer, ranking), P2-EPY (embedded Python), P2-JOB, P2-ESC (lock escalation;
  the structural lane observes it live, structural/capkeys/cap_batch.py case 03), P2-TEMP, P2-SEQ, P2-FETCH.
- Not validated here although cheap: `$SEQUENCE` (explored), `$LISTVALID` / `SET $LIST`, `$VECTOROP`, foreign-key
  checks, lock escalation as a contract clause. IRISTEMP cannot be tested within the scratch-global rule (`^IVGAudit*`).
- Module 00 owns no file in the inventory and is not re-derived (its cell is closed on env-ext-r6).
- F-C1720 needs a maintainer decision (fix or a driver floor, see F-C1706).

## 6. Reproduce

```bash
source experiment/playbook-completion/environment.sh
cd experiment/playbook-completion/contract-2/contract && CARGO_TARGET_DIR=$RUN_DIR/target/contract-2 cargo build --release --offline; cd -
bash experiment/playbook-completion/contract-2/run-e1.sh $RUN_DIR/contract-2/e1-rN <seed> 40 --journal      # E-1 (AUDITCORE)
python experiment/playbook-completion/contract-2/contract/native/cases_e1.py <dir>/cases.json --seed <s> --random 30 --s1   # S-1 cases
bash experiment/playbook-completion/contract-2/run-x2.sh $RUN_DIR/contract-2/x2-rN <seed> 25                 # X2 (AUDITENV)
$RUN_DIR/target/contract-2/release/iris-contract check <dir>/cases.json <dir>/observed.json --mutants <prefixes>
python experiment/playbook-completion/contract-2/tools/e1_journal.py <e1 round dir>
python experiment/playbook-completion/contract-2/validated.py && python experiment/playbook-completion/contract-2/enumerate.py --check --sites $RUN_DIR/contract-2/coverage-sites.json
python experiment/playbook-completion/contract-2/enumerate.py --selftest
python experiment/playbook-completion/contract-2/crosscheck.py experiment/playbook-completion/contract-2/coverage.json $RUN_DIR/contract-2/coverage-sites.json
python experiment/playbook-completion/contract-2/render.py
```
The final copied model reproduces every earlier round with 0 outside (r2, r4, r5, r6, e1-r1, e1-r2, x2-smoke, x2-r1:
`env2-regress`), and its explorer self-test still passes (`env2-contract-selftest`).
