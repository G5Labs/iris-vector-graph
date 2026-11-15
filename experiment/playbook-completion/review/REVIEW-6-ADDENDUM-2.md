# Independent review 6, addendum 2: `0b36c251..d293fb6b` (proofs-sys, proofs-env2, F-C1750)

Reviewer: independent reviewer lane (read-only), the same one that wrote passes 5 and 6 and the first addendum.
- **Scope:** `git log 0b36c251..d293fb6b` (2 commits):
  - `792b8d6f`: proofs-sys, the D-14 composition;
  - `d293fb6b`: proofs-env2, the D-7 remainder; the write-set fallback cells WS-OBL-147/148/150/154 and F-C1750.
- **Out of scope:** the running full verification (`verify.sh --live --clean`) and its result.
- **Rules followed:**
  - no IRIS connection, no Verus, cargo or explorer run, no commit, no stash;
  - nothing read from `$RUN_DIR/versions/secrets/`, nothing from the archive branch.
- **Files written:** only this file and `$RUN_DIR/review-6-add2/` (ratchet logs).
- **Product scope:** passes. `check-product-scope.sh` says "Product matches 3eaa79cf in HEAD, index and worktree", and
  nothing outside `PC/` changed in scope (`PC/` = `experiment/playbook-completion/`).
- **Who checked what:** a read-only fork of this reviewer read proofs-env2 in depth (section 2). I re-checked every point
  I raise below.
- **Registry:**
  - the 68 run records added in scope all re-hash (68 MATCH);
  - `ws-live-sql-fallback-priv`'s results file re-hashes too;
  - `check_registry.py`: 1,547 runs, 0 problems.

## Decision

**My sign-off of the account extends to `d293fb6b`, on two conditions (A2-01, A2-02) to be met in the next commit.**

Severities used here:

| Severity | Meaning | Effect on this extension |
|---|---|---|
| S1 | blocking | blocks |
| S2 | a claim the evidence does not support | blocks until fixed |
| S3 | a now-false or overstated statement that changes no matrix status, product label, count or gate result | a condition |
| S4 | wording or record-keeping | recommended |

- There is no S1 or S2 item.
- **A2-01:** the write-set lane's DISCHARGES.json still records modules 13 and 17 as open.
- **A2-02:** F-C1750's intent anchor overstates the product's documentation for its live trigger.
- **The rest are S4:**
  - A2-03: one attribution in the built matrix;
  - A2-04: proofs-env2 wording;
  - A2-05: the ENV2 premise rows;
  - A2-06: three precision points in proofs-sys;
  - A2-07: two stale STATUS phrases;
  - A2-08: the privilege record.
- **What holds:**
  - Both crates' numbers match their results and registered logs.
  - The new finding is real, and its control is faithful.
  - The disposable principal was restored.
  - Every ratchet passes.
- **What the sign-off covers:** still the specification against intent and the accuracy of the account, not the
  product.

## 1. proofs-sys (`792b8d6f`, D-14 composition)

**PROOFS.md agrees with RESULTS.json and the runs.**
- **Baseline:** 256 verified, 0 errors, with `--no-cheating` in the recorded command and the log's RUNNER SUMMARY.
  - 54 refutations and counterexamples verified (27 + 27).
  - `trusted_items_in_this_crate` is empty. My own scan of `proofs-sys/src` and `proofs-env2/src` finds no `assume`,
    `admit`, `external_body` or `uninterp`.
- **Controls:** each of the 12 fails only at its LOCATE lines, and only in its own `discharge_axNN` functions.
- **Recheck** (`proofs-sys-recheck`): the same sources hash `fc9757dc…`, 256/0, 12/12.
- **Model source:** `models/semantics/src/sys00.rs` is unchanged in scope (`ca7c21e7…` at all three commits);
  `semantics/axioms.json` is not (A2-06).
- **Matrix:** `792b8d6f` changes no cell's status, product label or grade (752 cells compared).

**"Each control breaks exactly the axioms the explorer's `violates` lists" holds for 11 of the 12 controls.**
- **The 11 that match.** I compared each control with `models/semantics/RESULTS.json`. Each set is equal (the
  explorer's "AX-11 a marked target is not live" = AX-11M):

  | Control | Broken axioms |
  |---|---|
  | as-built | AX-06, -07, -08, -10, -11, -11M |
  | ax02 | AX-02, -07 |
  | ax03 | AX-03, -07, -08, -11M |
  | ax06 | AX-06, -10, -11M |
  | ax08 | AX-08, -10 |
  | ax11 | AX-07, -11, -11M |
  | ax12 | AX-10, -12 |
  | ax04, ax05, ax07, ax10 | one each |

- **AX-14 under the as-built design:** kept in both the explorer (`sys00-as-built-ax-14` met) and the crate
  (`keep_sysasbuilt_ax14`).
- **The AX-14 control** is a progress check.
  - Its explorer record (`models/semantics/RESULTS.json:272`) has `violates: null` and `found` AX-14, and no safety
    complement was computed.
  - So its `violates=AX-14` (`proofs-sys/src/ctl_sys.rs:251`) is not "copied from models/semantics/RESULTS.json", as
    `tools/run_proofs.py:25-26` says (A2-06).
  - The refutation itself is genuine: `lemma_never_cleared` (`cx.rs:428`) proves that no continuation of the reached
    state finishes.

**The open obligations are stated honestly** (`PROOFS.md:148-157`):
- no code correspondence;
- no refinement from sys00 to the mechanism machines. The bridge proves obligation equalities for M-02, M-03, M-04, M-05
  and M-10, and none for M-01;
- sys00's small world (PS-1);
- AX-14 as AG EF only (PS-3);
- the M03-L2 gap: F-1201's lost statement entry lies outside sys00's state.

The three matrix supplements (`matrix-input/proofs-sys.json`) repeat these and change no status.

**The D-14 row does not over-claim, but needs two precision points (A2-06).**
- What it says:
  - "composition paid at model level";
  - the six composed mechanisms by name;
  - the reuse as "a proved equality of obligations ..., not a refinement";
  - every open obligation above.
- What it lacks:
  - it does not say that the other seven mechanisms are outside sys00;
  - its "equal to the explorer's `violates` list" needs the AX-14 qualification.

**PS-1..PS-4 are graded fairly.** Each is graded as the table grades the same kind of premise:

| Premise | Grade | Graded like |
|---|---|---|
| PS-1 | tested-partial, by the simulator | MP-2 and PM-3 |
| PS-2 | tested-partial, by the bounded-resume runs | PF-1 and MA-2 |
| PS-3 | untested | — |
| PS-4 | tested-partial, by the baselines, with the correspondence by inspection | — |

Only PS-2 and PS-3 (progress) enter CLOSURE, as the extractor's engine/progress rule says.

## 2. proofs-env2 (`d293fb6b`, D-7 remainder)

**The numbers are accurate.** The fork checked them, and I re-checked the counts.
- **Baseline:** 433 verified, 0 errors, `--no-cheating`, empty trust inventory.
- **Controls:** 22, each located, with its counterexample verified.
- **Differential:**
  - 2,430 of 2,943 recorded case runs over 11 rounds, 0 disagreements, 0 outside;
  - the nine outside families sum to 513, and 2,430 + 513 = 2,943;
  - 49/49 mutants killed (29 + 20).
- **Recheck:** identical numbers. All 51 records re-hash.
- **Unchanged:** proofs-env and proofs-mech. No crate imports proofs-env2.
- **No upgrades:** no matrix status or label changed. CLOSURE did not upgrade the "Embedded SQL" row (validated stays 47).

**"No closure premise rests on the nine families" is true.**
- My own search of the 76 proof-premise rows of `reflection/closure.json` finds none of: DDL, NOINDEX, JSON, `$LIST`,
  TOP, MERGE, `$QUERY`, ZKILL, `$VECTOR`, STAR, CREATE, DROP, ALTER.
- The credit belongs to that search, not to the premise-map run (A2-05).

**The D-7 row, TRUST.md:14 and :45 and the supplements state what the crate shows, with two wording points (A2-04).**
- **E-1 is "proved" in the specification because the specification defines it so.**
  - `emb_dml` is `plain_dml` when no mutant flag is set (`proofs-env2/src/ext.rs:386-401`), and `gen_e1` has an empty
    body (`src/gen.rs:601-608`).
  - That IRIS behaves this way is still shown only by the E-1 rounds (c2-e1-r1 and -r2, 121 cases) and the 6 E-1
    mutants.
  - `TRUST.md:45` says "In the Verus specification". `matrix-input/proofs-env.json:59` ("is proved by proofs-env2") and
    `matrix-input/proofs-env2.json:37` ("moves from outside-contract to proved") drop that qualifier.
- **P-M2 is overstated in D-7.** "P-M2 proved in part (statement atomicity)" (`PROOF-DEBT.md:17`) is broader than
  `premise_d1e_p_m2_stmt_atomic` (`src/premises.rs:445-455`). The theorem covers only an INSERT ... SELECT that fails on
  a key while no other process holds row locks: it writes nothing and answers -119.
- **The A-04 linkage text stays true for proofs-env2.**

**ENV2-1..ENV2-5 are accurate except for one gap and two attributions (A2-05).**
- **Accurate:**
  - ENV2-3: `disc` violated, F-1201;
  - ENV2-5: a modelling choice checked by the differential and the batch-atomic mutant;
  - ENV2-4: mirrors ENV-4.
- **The gap: ENV2-4 is not mapped.**
  - ENV2-4 entered CLOSURE (now 76 proof-premise rows) after `proofs-env2-premise-map` had run on 75.
  - `tools/premise_map.py` has no entry for it, so the crate's own reproduce step (`PROOFS.md:160`) would now report
    "unmapped closure condition".
  - `STATUS.md:35` says "every proof premise linked by a theorem or a verdict"; that is 75 of 76.
  - This is A-03's mechanism again: a premise table added at integration, after the map ran.
- **Attribution 1:** ENV2-2 credits the family check to the premise-map run. `premise_map.py` makes no such check, and
  its 351-byte log shows only verdict counts.
- **Attribution 2:** ENV2-1 says "all 11 rounds", but lists no faithfulness test for c2-e1-r2, the two regress rounds,
  estop-gap or dml-single. This is inherited from ENV-1.

## 3. F-C1750 and the write-set closures (`d293fb6b`)

**The run records what happened.** Both the results file and the log re-hash.
- **The harness that ran is the committed one.** Its mtime is 00:10:53; the run was 00:11:18-00:11:20.
- **Seed:** the same in both variants (4 nodes, 2 recorded edges, verify equal).
- **doc variant:**
  - the probe cache is True;
  - the rows, the `^KG` out entries and both statements are gone.
- **noexec variant:**
  - The probe cache is False, with the DEBUG line "Graph.KG.Eraser.EraseNodeIds taken as absent: <PROTECT> *Resource
    %Native_ClassExecution required".
  - The rows and `^KG` out entries are gone, but both statements are still live (`stmt_live_without_row` true).
  - There is no warning except the five driver `gref` lines, which appear identically in the control.
- **verify():** it diverges (unrecorded_writes) in both variants. The run record says so; the finding does not rest on
  it.

**The control is faithful.**
- It is ADMIN_GUIDE.md:463's writing row, in AUDITB.
- AUDITB's one database holds both globals and routines under `%DB_%DEFAULT` (`versions/PRIVILEGE.md:22-23`), so the
  routines resource is held once.
- SELECT and EXECUTE were already granted.
- The variant differs from the control only in `%Native_ClassExecution`.

**The intent anchor is sound for the INV-stmt break, but overstated for the trigger (A2-02).**
- **Sound:**
  - `iris_sql_store.py:1333-1338` reserves the SQL path for "an install with no ObjectScript classes, hence no ^KG to
    maintain". Here the classes, the ledger and `^KG` all exist.
  - INV-stmt is the audit's own invariant.
  - `_has_eraser_method` caches *any* exception as absent for the store's life (`:1315-1317`), so the path does not
    need the undocumented role.
- **Overstated:**
  - ADMIN_GUIDE.md:511-514's ClassesUnreadable rule covers a routines database that the role cannot read. At the pin it
    is raised only when the `<PROTECT>` names that database (`schema.py:119-143`).
  - `schema.py:134-137` names this very refusal and makes the opposite choice: "a refusal that names no database (a
    missing %Native_ClassExecution): the dictionary's answer stands".
  - The engine's own capability probe also takes it as absent, at DEBUG (`schema.py:2828-2830`).
  - R206 (`_dictionary.py:8-12`) fixed the SELECT refusal by asking natively; it says nothing about a refused native
    call.
- **Not logged:** "the dictionary SELECT was refused (-99)" and "IDKEYExists raised" are read from the code
  (`_dictionary.py:48-56`).

**Severity S2 is reasonable.**
- The break is silent: INV-stmt fails and the call returns success.
- It is comparable to F-C0450 and F-C0151 (INV-stmt, S2) and F-0801 (a fail-open guard, S2).
- The role is outside ADMIN_GUIDE's rows, as the notes say; the transient-error path is not.

**Discharging WS-OBL-147/148 by F-C1301 at "inspected" is fair.**
- They get the same `fc1301` rule and grade as DeleteBareSet, DropRows, `_drop_orphaned_props` and `_mirror_node`.
- `_delete_nodes_sql` deletes node rows inside a WriteTxn (`iris_sql_store.py:1379-1417`), and a WriteTxn nests in the
  caller's transaction (`_write_txn.py:10-13`).
- The run shows only that the path is reachable. RUN-PAIRS records it correctly as context for these pairs, not as
  exercised; the built matrix ignores that (A2-03).

**The principal was restored.**
- `principal_restored` is true for user, role, privcount and grants.
- The initial and final events are equal: enabled 0; resources `%DB_%DEFAULT:R,%Native_ClassExecution:U,%Native_GlobalAccess:U`;
  the same 2 grants.
- Every grant was revoked `AS "_SYSTEM"` with `ok`.
- The user was enabled only inside each variant.
- The wrapper's scan found no password in the run directory.
- **Authorisation:** the use (RW and write grants for about 2 s) is within the precedent PRIVILEGE.md records for the
  refusals lane. PRIVILEGE.md does not record this window (A2-08).

**Closing 3.3a-writesets/13 and /17 with "fails" is consistent in the matrix, but not in DISCHARGES.json (A2-01).**
- **In the matrix:** they close as 01, 03, 04, 06, 08, 11, 14 and 18 did.
  - Every census cell of module 17, and every census cell on module 13's invariants, has a discharge.
  - The product obligation fails by finding.
  - The matrix diff shows only these changes:
    - the module cells 13 and 17 close;
    - the 4 census cells close, each label going from unknown to fails.
- **In DISCHARGES.json:**
  - Every other closed cell has a closing module entry (finding or guard, graded inspected or live).
  - `module:13` and `module:17` stay "open"/"open", with stale reasons.

## 4. The account

**Every ratchet passes.** The logs are in `$RUN_DIR/review-6-add2/`.

| Check | Result |
|---|---|
| `status_numbers.py --check` | "status numbers current" |
| `check_premise_map`, `check_closure`, `check_root_causes` | CHECK PASS |
| `check_semantics` | 0 violations |
| `check_discharges` | pass; census 185: finding 68, guard 9, lemma 105, open 3 |
| `check_registry` | 1,547 runs, 0 problems |
| `build_matrix --check` | 0 problems |
| `check-product-scope.sh` | passes |

`check_discharges` prints "open module cells [01 … 18]". That is its C7 set: the module cells this lane decided, open or
not (`check_discharges.py:112-117`). It is not a list of open cells.

**STATUS.md:**
- **The generated block agrees with the artifacts:**
  - 15 crates, 3,415 verified = 2,726 + 433 + 256;
  - the census counts;
  - matrix 618 closed, 75 open;
  - 115 new findings, 79 reproduced live, 38 at S2.
- **The edited rows agree with the artifacts:**
  - 13 + 2 crates;
  - 6 open write-set cells: modules 05, 12 and 15, and the three FHIR census cells;
  - 174 closure conditions;
  - 287 premises.
- **Exceptions:**
  - a stale check id and a stale review count (A2-07);
  - §3.2's two proofs-env2 phrases (A2-04, A2-05).

## Items

- **A2-01 (S3): DISCHARGES.json still records modules 13 and 17 as open, and three of its reasons say the fallbacks are
  unreached.**
  - **Where:**
    - `writesets/DISCHARGES.json:3621-3639`: `module:13` is "open"/"open", with the reason "every census obligation on
      them has a discharge except  (_delete_nodes_sql's SQL fallback, unreached at the pin's deploy)";
    - `:3665-3672`: `module:17` is "open"/"open", with "0 of them open (none). ... the SQL fallbacks of _delete_nodes_sql
      and delete_edges are open (unreached at the pin's deploy)";
    - `:3619`: `module:12` says "iris_sql_store SQL fallbacks: unreached at the pin's deploy".
  - **Source:** `writesets/tools/build_discharges.py`: the hard-coded texts at :683-697 and :715-716; at :725-730 only
    module 18 can close.
  - **Correction:**
    1. Close `module:13` and `module:17` the way `module:18` closes: discharge finding, grade inspected, their findings,
       and the reason "verification cell closes; product obligation fails (...)".
    2. Drop the three "unreached" clauses.
    3. Regenerate DISCHARGES.json and register a new check (`ws-check-r6`).
- **A2-02 (S3): F-C1750's intent anchor overstates ADMIN_GUIDE §3 and R206 for its live trigger.**
  - **Where:** `findings/audit/zz-orchestrator-steer7.json`:
    - :59 (`intended`);
    - :93 (`notes`: "which the guide's own rule for unreadable classes (raise) and R206 exclude");
    - :60 (`observed`: "refused (-99)", "IDKEYExists raised").
  - **The same wording also appears in:** `writesets/tools/build_discharges.py:417-420` and `SFP_REACH` (`:433`), and
    the WS-OBL-147/148 reasons generated from them.
  - **Correction:**
    1. Rest the intent on `iris_sql_store.py:1333-1338` and INV-stmt.
    2. Cite ADMIN_GUIDE.md:511-514 only as the rule for a routines database the role cannot read.
    3. Add `schema.py:134-137` and `:2828-2830` as the pin's contrary choice for a missing `%Native_ClassExecution`.
    4. Record, as a maintainer question, whether such a role must be refused or served.
    5. Mark "-99" and "IDKEYExists raised" as read from `_dictionary.py:48-56`.
  - S2 and the outcome `product-defect` stand.
- **A2-03 (S4): the matrix attributes a run's failure to two pairs it did not exercise.**
  - **The basis:** `matrix/obligations.json:25938` and `:26008` list "run ws-live-sql-fallback-priv (fail)" in the fails
    basis of WS-OBL-147 and -148.
    - The run exercised only INV-stmt; `writesets/RUN-PAIRS.json` marks it as context for these pairs.
    - It entered through `build_discharges.py:448-449`.
  - **The wording:** `matrix-input/writesets.json:289` (= `writesets/MATRIX-INPUT.json:289`) says the fallbacks of
    `_delete_nodes_sql` *and `delete_edges`* "have the F-C1301 shape (WS-OBL-147/148)". `delete_edges`' INV-marker and
    INV-no-live-tombstone are lemmas: it deletes only edge rows.
  - **Correction:**
    - Show context runs as "(context)" in `build_matrix.py`, using RUN-PAIRS, or cite the run only in the reason text of
      these two cells.
    - Say "the fallback of `_delete_nodes_sql` has the F-C1301 shape".
- **A2-04 (S4): proofs-env2 wording.**
  - **E-1:** wherever E-1 is called "proved", say "proved in the specification, where the embedded statements are
    defined as the dynamic ones (`ext.rs:386-401`); its link to IRIS is the E-1 rounds (121 cases, differential) and 6
    mutants". The places are:
    - `matrix-input/proofs-env.json:59`;
    - `matrix-input/proofs-env2.json:37`;
    - `proofs-env2/PROOFS.md:78`;
    - `PROOF-DEBT.md:17`;
    - `STATUS.md:35`.
  - **P-M2:** in `PROOF-DEBT.md:17`, replace "P-M2 proved in part (statement atomicity)" with the wording of
    `PROOFS.md:79`.
- **A2-05 (S4): the ENV2 premise rows and the premise map.**
  - **ENV2-4:**
    1. Add ENV2-4 (progress) to `proofs-env2/tools/premise_map.py`'s MAP.
    2. Re-run and re-register the map.
    3. Then correct the 75-condition verdict totals in `matrix-input/proofs-env2.json:37`, and check `STATUS.md:35`.
  - **ENV2-2** (`reflection/premise_tests.json:6875-6890`, `proofs-env2/PROOFS.md:96`): credit the keyword search of
    `PROOFS.md:83-85`, not the map run.
  - **ENV2-1** (`premise_tests.json:6838-6873`, `PROOFS.md:95`): list the faithfulness tests of the other rounds, or
    drop "all 11".
- **A2-06 (S4): three precision points in proofs-sys.**
  1. **The AX-14 control's `violates`.**
     - Places: `src/ctl_sys.rs:251`, `tools/run_proofs.py:25-26`, `PROOF-DEBT.md:24` and `QUEUE.md:55`.
     - Correction: say "the explorer's violated laws (`violates`; for the AX-14 progress control, its `found`; no
       safety complement)".
  2. **The axioms.json hash.**
     - `proofs-sys/PROOFS.md:11` cites axioms.json's SHA `95fe2736…`, which is the file at `792b8d6f`.
     - `d293fb6b` changed the file: it is now `cdf7eaff…`, after F-C1750's classes were added; the axiom texts are
       unchanged.
     - Correction: say "at 792b8d6f", or hash the axiom rules only.
  3. **The seven mechanisms outside sys00.**
     - `PROOF-DEBT.md:24`'s still-open list and `PROOFS.md:154` name only M-07 and M-13.
     - Correction: name all seven (M-06, M-07, M-08, M-09, M-11, M-12, M-13).
- **A2-07 (S4): STATUS.**
  - `STATUS.md:37` cites `ws-check-r4` for the write-set counts; it should cite `ws-check-r5`.
  - `STATUS.md:40` says "four independent reviews"; there are now six passes and two addenda.
- **A2-08 (S4): the privilege record.**
  - `versions/PRIVILEGE.md` has no entry for this use of the principal.
  - Correction: add a section after `:143`, like the refusals lane's (`:108-143`), recording:
    - `ws-live-sql-fallback-priv`, AUDITB, 00:11:18-00:11:20 UTC;
    - the role at `%DB_%DEFAULT:RW`, so the 15 databases sharing that resource were writable for about 2 s;
    - `%Native_ClassExecution` removed in the noexec variant;
    - INSERT, UPDATE and DELETE ON SCHEMA Graph_KG granted by `_SYSTEM` and revoked `AS "_SYSTEM"`;
    - the user enabled only inside each variant;
    - the final state equal to the initial one (`results-r1.json` `principal_restored`);
    - the password scan.

**Nothing else to raise.** Not raised, and checked:
- the two commit messages' other claims;
- the root-cause attachment (RC-14 primary, RC-08 secondary);
- F-C1750's axiom classes;
- the census, closure and premise counts;
- the D-7 "still open" list;
- the verify.sh crate loop.
