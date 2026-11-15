# Independent review, third pass (playbook §3.8, §5c)

Reviewer: independent reviewer lane (read-only). Product pin `3eaa79cf` (tree `b098a6f4`, unchanged). Audit state
reviewed: `a6dc67a1` (08:42 UTC); the working tree is clean apart from registry files. No IRIS connection, no live
run, no commit; I wrote only `review/REVIEW-3.md` and `review/review-3.json`. `PC/` = `experiment/playbook-completion/`.

Integrity check of my earlier work: `review/REVIEW-2.md` is byte-identical to what I last wrote (mtime 06:17:38;
SHA-256 `ef6a7c40...` = `independent-review-2-final`'s log). `review/RESPONSE-2.md` is the orchestrator's file and now
names its author.

## Decision: **no sign-off**

All three second-pass conditions that the audit could fix are met, and the new work is strong:
- **D-9 proofs:** three target predicates, a bypass writer and erasure rollback (115 verified, 6 controls, each with a
  located counterexample).
- **Modules 18 and 06 proofs:** 92 verified, 11 controls, each with a located counterexample.
- **Randomized simulator:** 304 schedules run through the real product, with every count reconciling between the
  document and its logs. It found a real new defect, F-CS01.
- **Evidence:** every one of the 31 runs registered since my second pass matches or is only partly supported by its
  log; none is contradicted.

One sign-off condition belongs to the operator and is unchanged. The new work also brings four small
account-accuracy defects, listed below. Each is mechanical to fix, and none hides a product result.

## 1. Second-pass conditions

| Condition | Response | Checked against | Verdict |
|---|---|---|---|
| R2-11: F-1201 restored to `reproduced-live` | `findings/audit/12.json`: `disposition` `reproduced-live`; notes state "only the remedy (HD-1201) is undecided" | the record | **met in substance**. The note's quotation of ADR-0004's Consequences clause is wrong (R3-05) |
| R2-12: errata for `corr-trace-conf` and the control count | `evidence/errata.json` `corr-trace-conf`: "store-side contract steps ... checked only on the ext trace"; `CORRESPONDENCE.md` method row: "8 on `conf`: 7 rejected, the frame control expected not caught; 3 on `ext` ... store-side steps are checked on `ext` only" | errata, `git diff 739ddb8e cd17fe09` | **met** ("10/10" on line 23 is now literally right) |
| R2-12: a control for the tombstone-of-live-content rule | `corr-abstraction-selftest-r3` (`abstraction_selftest.py`: target rows made live before every redaction step of `ext`; the kill counts only at that rule) | log: `control tombstone-of-live-content: REJECTED ["redact-bounded: Batch: tombstone of live content [('node', 'x\|1')] ..."]`, `abstraction self-test PASS` | **met** |
| R2-12: the final second-pass text registered | `independent-review-2-final` (log `$RUN_DIR/review/REVIEW-2-final.md`); the draft record is marked superseded in errata | SHA-256 equal to my file | **met** |
| R2-07: operator scope ruling | none | `CONVENTIONS.md` unchanged since `bd727838`; `$RUN_DIR/supervision/operator-*.json` (00:12Z, 02:16Z, 03:16Z): none mentions the v4.5.1 release, the fixture or `%SYS` | **open (operator)** |

## 2. New work

- **`proofs-d9/` (proof debt D-9).** It drops P-C02, P-C03 and P-C04, the three premises my first pass showed false at
  the pin. Their mechanisms are now in the model:
  - three predicates `rm`, `lv`, `sc`, with the side condition `lv ⊇ rm ⊇ sc`;
  - a Writer participant;
  - erasure as an open transaction that may roll back.

  The six safety controls each name a guard and fail in their own file. Each has a counterexample that is proved
  reachable. `control_unaligned_rm` uses the pin's own `redact(None)` predicates. The progress-only control fails only
  `progress.rs:183`. The new progress premises PF-5 and PF-6 are named, and PF-6 is stated as violated live (F-C1307).
  The document's own limits are honest: readers, statement history, Decision 2, retry keys and the eraser variants
  remain explorer-only.

  Gap: **R3-01**.
- **`proofs-d1b/` (modules 18 and 06).** 92 verified. All 11 controls are located in their expected file and every
  control log ends with a runner summary that pins its JSON by SHA-256, which fixes the first pass's "count only in an
  unpinned file" pattern for this crate. "Premises the pin violates" names P-S3, P-S6 and P-V4, plus four premises the
  pin does not enforce.
- **`simulator/`.** It drives the public API from 2-4 OS processes and adds probe lock-holds and process
  terminations. A journal-replay oracle, written from the specs, judges the result.
  - Every total in `SIMULATOR.md` reconciles with the two evidence logs: schedules 204 + 100, operations
    11,905 + 4,146, committed units 8,170 + 5,112, verify points 408 + 300, readers 515 + 168, kills 62 + 20.
  - So do the per-finding counts, e.g. F-1101 33 + 13 and F-CS01 4 + 5.
  - The self-test rejects 13 of 13 injected violations above zero baselines.
  - F-CS01 is a real new defect, which my reviews missed: a no-op changeset commits a zero-record revision, and
    redaction never clears it because it has nothing to tombstone. It reproduced 3 of 3 times from the 6-operation
    plan, and ddmin found 21 reproducing candidates out of 41.
  - The documented limits are fair. One small gap is in R3-05.
- **Matrix.**
  - `5c-reviewers` is now closed, citing the simulator, which is right.
  - The proof cells for modules 04, 06, 11 and 18 are all level `model`.
  - `build_matrix.py --check` now reports `STALE`. I rebuilt it in a scratch copy: the only difference is
    `registry_runs` 781 → 782, because `verify-full-fd605df3` was registered after the build.
  - Gap: **R3-02**.
- **`PROOF-DEBT.md`.** D-1 records modules 04, 06, 11 and 18 as proved at model level; D-9 is "largely paid"; D-12 and
  D-13 are recorded. This is accurate.
- **`STATUS.md`.** Gap: **R3-04**.
- **Verification records.**
  - `verify-full-fd605df3`: 31 steps, all exit 0, and every step-log hash matches. Its `matrix.log` reads "current",
    `registry.log` "781 ... 0 problem(s)", and `models-compare` reports all reruns reproduced. The four proof gates
    ran. Its claim that the live inputs are unchanged since `0eec4df8` holds: `git diff` shows only `verify.sh`
    changed, adding the two proof steps.
  - `verify-final-candidate` was checked in my second pass.

## 3. Findings of this pass (all account accuracy; none hides a product result)

- **R3-01 (S3, angle 3): a D-9 premise the pin violates is not listed as violated.**
  - Premise P-D9-3 says "Bypass writers write content rows only, never ledger globals". It cites the *original* census
    (`$RUN_DIR/checks/writer-census.json`) and `MODELS.md`.
  - The corrected census (`followup-writer-census`, `ledger_writers_outside_ledger_classes`) lists five ledger-global
    writers outside the ledger classes: `restore_snapshot` via `_import_global_from_ndjson` at `snapshot.py:1679`,
    `Snapshot.ImportGlobals`, `Snapshot.SetNodeJSON`, `copy_ledger_history`, and the SQL INSERT surface on
    `ledger_revisions`. F-1801 and F-C1304 show restore writing the marker, `idemRedacted` and revision rows.
  - So P-D9-3 is violated at the pin, but `proofs-d9/PROOFS.md` "Premises the pin violates" omits it.
- **R3-02 (S3, angle 4): the product label is inconsistent for the new proof cells.**
  - The 06 and 18 cells for 3.3-L1, L2 and refinement say `holds-in-model-only`, while the 06 and 18 3.3-controls
    cells, citing the same crate, say `fails`. F-1801, F-0606 and F-C1304 are reproduced live.
  - The same gates for 04 and 11 say `fails`, with their findings as basis.
  - The R2-01 `--check` rule did not catch this because these cells cite only the baseline run. `MATRIX.md` therefore
    shows 7 `holds-in-model-only` cells, 6 of them these.
- **R3-03 (S3, angle 4): the ontology lags F-CS01.**
  - The ontology was last changed at `0eec4df8`, before the simulator.
  - RED-B12 ("no ledger record, row or reader shows its ids or values") and RED-B4 ("A retry key of a redacted
    revision can never be used again"; F-CS01's key stays bound and is replayed after the redaction) do not cite
    F-CS01.
  - The checker rule did not fire because F-CS01's `intended` names spec lines, not statement ids.
- **R3-04 (S3, angle 4): STATUS contradicts itself.**
  - The §3.8 row says "§5c's randomized simulator through the real product not run (`5c-reviewers` open)". Line 42
    and the matrix say the simulator ran and `5c-reviewers` is closed.
  - The verdict paragraph cites the older candidate `0eec4df8` / `verify-final-candidate`, not the latest full run,
    `verify-full-fd605df3`.
- **R3-05 (S4): cosmetic, not conditions.**
  - F-1201's note attributes to ADR-0004's Consequences "'no live statement outlives its content' and the statement
    map must track recorded live edges". The first phrase is the Decision (line 18). The second appears nowhere in the
    ADR. The clause that settles F-1201 is lines 79-80: "a write path that touches one store without the others is a
    bug". Its `intended` still cites only the converse.
  - `orchestrator_status.json` 3.7-full-rerun still reads "final verify.sh run pending".
  - The simulator's "not hit" list omits the rollback-based findings F-C1201 and F-C1301. Its bypass writes are
    single engine calls, and only a process termination can roll one back.

## 4. Evidence audit (third pass: all 31 runs registered after my second pass)

All 782 registry logs re-hashed: 776 match, and the 6 that do not are the known, disclosed superseded `core-proofs-*`
originals. All 31 runs below have matching hashes.

| # | Registry id | Verdict | Note |
|---|---|---|---|
| 1 | corr-abstraction-selftest-r3 | MATCH | 10 REJECTED + frame expected; new control rejected at its rule |
| 2 | independent-review-2-final | MATCH | identical to `review/REVIEW-2.md` |
| 3 | verify-fast-cd17fe09 | MATCH | 18/18 exit 0; step hashes ok |
| 4 | proofs-d9-baseline | PARTIAL | log ends at `Finished`; "115 verified, 0 errors" is only in the unpinned JSON (the recheck log carries it) |
| 5 | proofs-d9-bypass-start | PARTIAL | its log is byte-identical to #6 (SHA `8987eef5...`); which counterexample compiled is shown only by the unpinned JSONs (`cx_bypass_start` vs `cx_bypass_erase`); disclosed in PROOFS.md §6 |
| 6 | proofs-d9-bypass-erase | PARTIAL | as #5 |
| 7 | proofs-d9-f1201-erase-unlocked | MATCH | errors at `protocol_sys.rs:107, :116` |
| 8 | proofs-d9-liveness-dirty | MATCH | `:107`, `:115` |
| 9 | proofs-d9-progress-rewind | MATCH | 1 error at `progress.rs:183` |
| 10 | proofs-d9-unaligned-rm | MATCH | `protocol_sys.rs:107` |
| 11 | proofs-d9-unaligned-sc | MATCH | `protocol_sys.rs:107` |
| 12 | proofs-d9-recheck | MATCH | "baseline: 115 verified, 0 errors"; 6 controls REJECTED; progress control "FAILS ONLY PROGRESS" |
| 13 | proofs-d1b-baseline | MATCH | runner summary "92 verified, 0 errors", JSON pinned |
| 14 | proofs-d1b-f1801-no-prefix-check | MATCH | `snap_l2.rs:524` |
| 15 | proofs-d1b-f0604-done-without-vector | MATCH | `vq_l2.rs:229` |
| 16 | proofs-d1b-f0606-erase-keeps-ivf | MATCH | `vidx_l2.rs:176, :180` (`:171` is a note) |
| 17 | proofs-d1b-f1801-restore-unredacts | MATCH | `snap_l2.rs:538, :553, :568`; 89 / 3 |
| 18 | proofs-d1b-fc0601-no-version-check | MATCH | `vq_l2.rs:231` |
| 19 | proofs-d1b-fc1304-receipt-omits-archives | MATCH | `snap_l2.rs:454` |
| 20 | proofs-d1b-fc1801-dirty-export | MATCH | 5 locations, 87 / 5 |
| 21 | proofs-d1b-fc1802-swallowed-line | MATCH | `snap_l2.rs:536` |
| 22 | proofs-d1b-fc1804-edge-routes-omitted | MATCH | `snap_l2.rs:369` |
| 23 | proofs-d1b-hd0602-inplace-build | MATCH | `vidx_l2.rs:214, :228`; 90 / 2 |
| 24 | proofs-d1b-hd0604-two-consumers | MATCH | 1 failing function, 2 diagnostics (functions counted, as `evidence/errata.json` says for hd0401) |
| 25 | proofs-d1b-recheck | MATCH | "baseline: 92 verified, 0 errors" |
| 26 | sim-main-20261114 | MATCH | aggregate: 204 / 11,905 / 8,170; per-finding counts; verify 327 + 28 + 53 = 408 |
| 27 | sim-race-20261114 | MATCH | 100 / 4,146 / 5,112; verify 300 |
| 28 | sim-oracle-selftest | MATCH | 13 controls caught, baseline 0, 40 unmutated |
| 29 | sim-fcs01-minimal | MATCH | 3 tries, 3 hits; key still bound; revision 3 metadata |
| 30 | sim-fcs01-ddmin-s1033 | MATCH | 41 candidates, 21 hits, "minimal schedule: 7 operation(s)" |
| 31 | verify-full-fd605df3 | MATCH | 31/31 exit 0; step hashes ok; live inputs unchanged (git) |

**Result: 0 mismatches, 3 partial, 28 match.** Ratchet: RC-E1 (counts only in unpinned files) keeps rows 4-6. The
`proofs-d1b` runner summary is the fix to copy for `proofs-d9`.

## 5. Remaining conditions

**Needs the operator** (an agent cannot discharge it):
- **O-1 (R2-07).** A ruling, from the user or operator, on compiling the v4.5.1 release and `IVGDev.Setup` into
  `%SYS` through a pinned fixture (F-C1306's probe). The alternative is to re-grade that evidence as outside the
  conventions. In both cases `CONVENTIONS.md` must state the rule.

**Needs the audit** (mechanical; R3-05 is optional):
- **A-1 (R3-01).** Add P-D9-3 to `proofs-d9/PROOFS.md` "Premises the pin violates", citing `followup-writer-census`.
- **A-2 (R3-02).** Give the 06 and 18 3.3-L1, L2 and refinement cells the same product label rule as 04 and 11, and
  extend `--check` to catch the mismatch.
- **A-3 (R3-03).** Cite F-CS01 on RED-B12 and RED-B4, with `[model-only]` where their `proved:`/`mc:` items apply.
- **A-4 (R3-04).** Make STATUS's §3.8 row and verdict match the matrix and the latest full run.

**Needs a maintainer** (outside any sign-off of mine):
- §3.8's second clause: a fix or a recorded decision for every finding.
- The residual questions in `decisions.md`.
- The intent questions this audit leaves `intent-undecided`, or conditional on an assumption: F-0401, F-0503, F-C1102
  (the durability premise), F-1201's remedy (HD-1201), and F-CS01's reading of FR-004 (a revision with no records).

On O-1 and A-1 to A-4, I will sign off on spec against intent and on the account's accuracy. That sign-off covers the
account, not the product.
