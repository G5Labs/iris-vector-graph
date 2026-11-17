# Iteration 60 repair 2: the round-1 validation residue (case V3, wording, re-enable clause)

Assignment: [ASSIGNMENT.md](ASSIGNMENT.md). Validation: `$G5_RUN_STATE/review-60v/VALIDATION.md` (published round-1
feedback, read in full; exposed). Repair-2 builder session 2370c4fd, 2026-11-17 about 21:58Z to 23:20Z, with one
interruption (API network failure at about 22:52Z; the same session was resumed, and nothing on disk was lost).

- Before: `12b648c1c` (repair-1 handoff). Commits: `9b7a66fa2` (assignment and predictions, before any run),
  `d87a22595` (prediction addendum, before any run), `8ab0f2585` (native probes, model fix, theorems, controls, prove and
  control receipts), `1e6c41f91` (owners, registers, binding receipt, crosswalk, coverage), `81c69d247` (bullet
  wording; correspondence inputs recaptured after the final edit), then the handoff commit with this file. Product pin
  `3eaa79cf` unchanged (consolidated confinement check passes).
- Fixture: local `ivg-uplift-next-20261115` (127.0.0.1:35975, IRIS 2026.1 Build 234U). Every connection checked the
  instance hostname `1a97b1515453` against the container, and 483 executable product files were byte-checked against
  `3eaa79cf`. This repair's own namespaces were created additively from `%SYS` with `CREATE DATABASE` and deployed with
  `initialize_schema()`. `I60SA` holds the probe, with a table `SQLUser.i60s_app` of its own. The binding uses `I60SB`
  (with `SQLUser.i60s_app`), `I60SC` (`max_ops` 2) and `I60SE` (never enabled). IDs start with `i60s_` / `i60b_`.
  X's head lock was a Native API lock on this repair's own namespaces and was always released. Nothing was written to
  USER, `I60L*`, `I60R*`, `R60*` or `V60L`. There was no erase, reset, kill or drop, and no other container was touched.
- **Concurrent writer (disclosed).** At about 23:00Z another session, outside this run, began an ontology
  reorganization in the same working tree (`.g5/pr_ontology_diff_design/ontology-organization/ontology-plan.md`: new
  `architecture/`, `operations/` and feature pages; findings relinked). It also relinked links inside my bug-led-017
  entry to its new pages. I staged none of its edits. The three files we both edited (`bugs_issues.md`, `coverage.md`,
  `features/ledger.g5.md`) were rebuilt from HEAD plus only my changes and staged as blobs. All gates ran on a clean
  `git clone --local` of `81c69d247`, not on the shared working tree. The other session's edits remain unstaged in the
  tree, and its copy of my caller-transaction bullets carries the same final wording as `81c69d247`.

## Item 1: counter row held by a caller transaction (validation V3): accepted, reproduced, modelled, bound, registered

**Native reproduction** ([predictions](PREDICTIONS.md), [grades](PREDICTIONS-graded.md): 13 of 13 held; [probe](probes/i60s_probe.py)):

| Case | Observed (I60SA; counters read through `GraphLedger.stats()` on a third connection) | Evidence |
|---|---|---|
| S1 = V3 | X locks the head. A (autocommit off) commits and gets `LedgerLockTimeoutError` after 30.1 s, `$TLEVEL` 1, `rej_lock_timeout` +0. X unlocks. B's valid commit gets `LedgerInconsistencyError("stats save failed: ERROR #5803 … 'Graph.KG.LedgerStats'")` after 10.2 s: one `inconsistent` event, head unchanged, 0 node rows, no counter moved. After A's rollback, B's retry commits on the prior head with `commits_ok` +1 | [s1](probes/observed-20261117T220645Z-s1-s2.json) |
| S2 (valid neighbour) | The same with no caller transaction: A 30.0 s and +1. B commits at once (0.0 s) and is counted | same file |
| S3 (strict) | Strict on. A (autocommit off) inserts one row of its own, then `create_node` is refused (`LedgerStrictModeError`). `rej_strict_block` +1 while A is open. B gets `inconsistent` after 10.1 s, nothing written. After A's rollback the strict count is +0 and B's retry commits | [s3…](probes/observed-20261117T220811Z-s3-s3z-s4-s6-s6n.json) |
| S3z, S4 (neighbours) | Nothing written yet (`$TLEVEL` 0), or autocommit on: the count is kept (+1) and B commits at once | same file |
| S6 (verify) | A (autocommit off) inserts one row, then `ledger.verify()` (equal). B gets `inconsistent` after 10.1 s. A's rollback also takes back `last_verify_result` | same file |
| S6n (neighbour) | Nothing written yet: B commits at once; the verify result is kept | same file |

**Reachability (source, then natively confirmed).** The strict guard's `count_rejection` and `verify()`'s
`RecordVerify` call `Graph.KG.Ledger` through `engine._iris_obj()`. For an engine built as `IRISGraphEngine(conn)` (the
construction README, USER_GUIDE and ADMIN_GUIDE show), that is `iris.createIRIS(conn)`: the caller's own server
process. So the counter save nests in the caller's open transaction once `$TLEVEL` is above 0 (after any write). An
engine from `from_connect` uses a connection of its own (not run; source only). `disable()` and `set_strict()` also
save the row on that process and are not refused inside a caller's transaction (source only, not probed).

**Owner** ([ledger.g5.md](../../../../ontology/features/ledger.g5.md)):
- `ledger.commit.caller-transaction` now says that a refused nested commit is never counted, and which nested commits
  keep the counter row. As built: the row can be held without the head (own lock timeout, strict refusal, or `verify()`
  after a write), and other connections' valid commits then fail with `LedgerInconsistencyError` after about 10 s.
  Intended: counting is bookkeeping and never changes an outcome. Sources: `LedgerStats.Bump` "in its own small
  transaction"; `LedgerInconsistencyError` "the ledger's own structures disagree". Intent is not unsettled, so no open
  question was added.
- `ledger.observability` states the same: as-built and intended, and that a refusal inside the caller's own
  transaction is uncounted.

**Model** (`ledger_client`, [NOTES](../../../../Verus_verification/models/ledger_client/NOTES.md)):
- **Corrected:** `txn_commit` restores `cnt` when the nested commit raises (`write_txn` undoes IVG's level) and
  decides `took_row` before that undo. **Withdrawn:** the repair-1 definition that kept a nested refusal's count until
  the caller's transaction ended. No proved claim depended on it.
- **New definitions:** `Via::{CallerConn, OwnConn}` and `row_save` (in-process counter-row saves); `plain_valid`.
- **New theorems:**
  - `theorem_nested_refusal_is_never_counted`;
  - `theorem_nested_lock_timeout_keeps_the_counter_row` (V3 and its neighbour);
  - `theorem_held_counter_row_refuses_a_valid_commit` (whoever holds the row; with the free-row neighbour);
  - `theorem_in_transaction_row_save_blocks_other_writers` (strict count and verify record; level 0 and own-connection
    neighbours).
- **New controls** (all EXPECTED_FAIL):
  - `nested-refusal-counted` (the pre-fix model);
  - `nested-refusal-frees-row`;
  - `held-row-not-checked` (removes the deciding row check; fails 4 theorems, `theorem_uncounted_outcomes` included);
  - `in-transaction-save-commits-at-once`;
  - `save-held-at-level-0`.
- **Receipts:**
  - [prove](../../../../Verus_verification/results/ledger_client/20261117T221544Z-prove/receipt.json): PASS, 34 verified, 0 errors;
  - controls `20261117T2215*/2216*-control-*`: 33 of 33 EXPECTED_FAIL;
  - both run after the final `.rs`/`model.json` edit, and FRESH.

**Binding** ([receipt](../../../../Verus_verification/results/ledger_client/20261117T225756Z-binding/receipt.json),
local fixture, I60SB/I60SC/I60SE; [log](probes/ledger_client-binding-run1.log)):
- AGREES on 58 native cases;
- 32 of 33 mutations detected (`update-without-emptying` is not natively exercisable, as before);
- a changed observation is caught;
- new cases: B21 (V3), B21n (neighbour), B22/B22z (strict after/before the first write), B23/B23z (verify);
- wall times: B21 A 30.1 s / B 10.1 s; B21n B 0.0 s; B22 and B23 B 10.1 s; B22z and B23z 0.0 s.

**Register** ([bugs_issues.md](../../../../Verus_verification/bugs_issues.md)):

| ID | Change | Tier | Severity | Reachability |
|---|---|---|---|---|
| [bug-led-017](../../../../Verus_verification/bugs_issues.md#bug-led-017) | **new** sibling | E2E (S1/S3/S6 with neighbours; binding B21-B23) | **Medium** | Ordinary. Needs a caller transaction that has written anything, on the documented engine construction, then a `verify()`, a strict refusal, or its own commit timing out on the head. Every other connection's ledger commit in the namespace is refused after a 10 s wait each, with a class that claims internal inconsistency. Lasts as long as that transaction stays open. Nothing written; a retry afterwards succeeds |
| [bug-led-014](../../../../Verus_verification/bugs_issues.md#bug-led-014) | extended | E2E | Low (unchanged) | Adds that the caller's own nested refusals are never counted (S1/B21: +0, against S2/B21n: +1), with a pointer to bug-led-017 |

Severity reasoning: Medium, not Low, because valid writes by every other connection are refused (not just
miscounted), under a misleading class, and the triggers include a read-only `verify()`. Not High, because nothing wrong
is written, the condition ends when the transaction ends, and a retry succeeds. Kept as a sibling rather than an
extension of bug-led-014: the observable consequence and the severity differ, and so does the trigger set (the
in-process paths). `findings.tsv` has a row for it.

## Item 2: `coverage.md:745` wording: corrected

It now says that the 24 relabelled declaration-only classes also left the pinned instrument's union (−24, with +3
newly reached: 1028 → 1007), and that they form a locator stratum outside that union (1007 + 24 = 1031).

## Item 3: bug-led-013 re-enable clause: observed natively

S5 ([s5](probes/observed-20261117T220854Z-s5.json), [s5r](probes/observed-20261117T220914Z-s5r.json); `I60SA`):
- a committed `temporal="true"` relationship plus a `"yes"` neighbour;
- two `disable()`/`enable()` cycles each return an adoption revision (seq 10, 11; head +1 each) that records `create_rel`
  and `set_qual temporal "true"` for that relationship;
- the next verify after each cycle still diverges with the same two entries; the `"yes"` neighbour gives none.

bug-led-013's Reproduced-by paragraph now cites this.

## Recount and member delta

Pinned instrument: `recount.py 81c69d247 $G5_RUN_STATE/counts/iteration-60-repair2`. Census 4,130; **union 1009,
active 774**, from 1007 / 772 at `12b648c1c`.

| Change | Members |
|---|---|
| Newly reached (+2) | `Ledger.cls::RecordVerify`, `_write_txn.py::WriteTxn.__exit__` |
| Gained active (+2) | The same two |
| Overlap / distinct / losses | 2 / 2 / 0 |

[member-delta.json](member-delta.json) has the details. The other 14 new crosswalk rows add new formal claims to members
that were already bound through other families: `GraphLedger.commit`, `caller_transaction_level`, `WriteTxn.rollback`,
`Txn.cls::Undo`, `Ledger.cls::{Commit,CommitInTxn,WriteRevision,Count}`, `LedgerStats.cls::Bump`,
`LedgerGuard.{count_rejection,check_structural_write}`, `IRISGraphEngine._iris_obj` and `replay.verify`.

Against the baseline `01e8ccba` (956 / 706): 53 newly reached, 68 gained active, overlap 52, distinct 69, losses 0.

- **Material prediction gained:** the reader-visible outcome of a valid commit while another transaction holds the
  counter row (`inconsistent`, nothing written), with its three producers.
- **Prediction corrected:** the caller's own nested refusal is +0, not +1.

## Gates (raw outputs in [gates/](gates/), run on a clean clone of `81c69d247`)

| Gate | Result |
|---|---|
| `check_evidence.py` | FRESH (exit 0) |
| `check_consolidated.py` (`G5_GUIDE=$G5_HARNESS/guidance`) | PASS, all sections (exit 0) |
| `check_findings.py … --previous <8ab0f2585 registers>` | "No problems found." |
| `check_ontology.py .g5/ontology` | 0 issues, 17 writing warnings (as at baseline) |
| `correspondence_gate.py check iteration-60/correspondence-inputs.json` (recaptured after the final edit) | proof and correspondence REUSABLE_INPUTS |
| model linker (`--links-only --dry-run`, Verus root) | 9 would-add links on non-ledger statements, all inherited (same as repair 1) |

Earlier gate runs on the shared working tree (`gates/check_*-1.txt`) are kept: they include the other session's
in-progress reorganization (findings checker 128 problems from moved statements, 26 ontology files) and do not
describe this candidate.

## Remaining limits and work

1. Not observed: an engine from `from_connect` (its guard and verify use another process; source-derived: B commits);
   `disable()` / `set_strict()` inside a caller's transaction (source only); `RecordVerify`'s stall while another
   transaction holds the row (inferred).
2. `row_save` takes `level` and `Via` as inputs (write_routing's premises), not derived from the driver.
   `txn_rollback` restores ledger fields to the before-image, which is valid only while the caller holds the head or
   the row (stated in NOTES).
3. Single native runs on one fixture; wall times recorded, not modelled.
4. Carried unchanged from repair 1: D10 delete operations in `ledger_apply`; B4/CG-2 transport loss after a commit;
   BC-3 decisions supplied as inputs; q-led-006; q-led-004; NKG dirty marker; correlation-index build; snapshot/upgrade
   survival.
5. The concurrent ontology reorganization in the working tree will need to carry bug-led-017's links and the
   repair-2 owner text into its new pages when it is committed. It had already started doing so.
