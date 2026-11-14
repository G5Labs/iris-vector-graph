# PROOFS-D9C: bypass writers honour the marker, and F-1306 as the pin writes it (review-4 R4-01, R4-03, R4-04, R4-14)

Crate `experiment/playbook-completion/proofs-d9c` (`ivg-proofs-d9c`), a copy of `proofs-d9b` at sources `f07f7c4d`
(whose registered runs stay reproducible: its sources are unchanged), Verus 0.2026.10.04, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved** (decisive, `--no-cheating`, no trusted items),
about **models only**. No proof connects the ObjectScript or Python at pin `3eaa79cf` to these contracts, and none of
the guards proved necessary here is present at the pin. Everything `proofs-d9b/PROOFS.md` states holds here unless
this file says otherwise; sections 1-3 below are the changes.

| Item | Result | Registry |
|---|---|---|
| Baseline `cargo verus verify -- --no-cheating` | **158 verified, 0 errors**, wall 8.3 s, Verus 7.8 s, 38.22 M rlimit | `proofs-d9c-baseline` |
| Safety controls | 14 of 14 rejected only in the expected file; every function outside it verifies and is the baseline's; each has a proved reachable counterexample | `proofs-d9c-*` (section 4) |
| Progress-only controls | 2 of 2 fail only `progress::RunProgress::nonincreasing`; the 147 functions outside `progress` verify as in the baseline | `proofs-d9c-progress-rewind`, `proofs-d9c-bound-follows-tail` |
| Trust inventory | empty (this crate and `actors`) | `RESULTS.json` `trust_inventory` |
| Gate | **pass** (`RESULTS.json`, sources SHA-256 `f34be0bd...`, logs `$RUN_DIR/proofs-d9c/run-20261114T125652Z/`) | |
| Independent recheck | gate **pass**, same sources, identical counts and error locations (`$RUN_DIR/proofs-d9c-recheck/run-20261114T125915Z/`) | `proofs-d9c-recheck` |

Rerun: `source experiment/playbook-completion/environment.sh; python experiment/playbook-completion/proofs-d9c/tools/run_proofs.py`
(`--register`, `--id-suffix`, `--id-prefix` as in d9b; logs in a new `run-<stamp>/` under `$PROOFS_OUT_DIR` or
`$RUN_DIR/proofs-d9c`).

**R4-14.** Every text log the runner writes ends with `RUNNER SUMMARY (<json>, sha256 <hex>): verification results::
<n> verified, <m> errors (failing functions); rc; failing functions; error locations`, as `proofs-d1b`'s runner does, and
each registry record carries `json_sha256`; a record's count is pinned by the log it hashes. "errors" counts failing
functions (a function may have several error lines).

## 1. R4-01: guard G-BM, and the no-tombstone theorem for content of any provenance (fix (b))

**Problem (review-4).** In `proofs-d9`/`proofs-d9b`, `theorem_no_tombstone_of_live` concludes only `!rec_content`:
a bypass `BBegin` is admitted while the marker exists, so a ledger-bypassing writer may re-create target content after
the entry check and the batches tombstone its history. That is F-C1350 (live, `ws-live-ins-store_node` and 11 sibling
runs, `findings/audit/zz-writesets.json`), and its working answer reads RED-B1.1/FR-005 as the product's own checks do:
any content row of the target is live.

**Guard chosen: G-BM, bypass writers honour the marker** (`biz.rs:75`, `bypass_honours_marker`): while a target is
marked, a ledger-bypassing write of a row its liveness predicate `lv` selects is refused (the writer reads
`^IVG.Ledger("redacting")` and answers busy, as BlocksCommit refuses a ledger commit into the target). Why this one:

- the maintainer's own statement of the intent is general: "Spec 256 Decision 3: while a redaction runs, nothing may be
  written into its target" (Ledger.cls:514), which the pin enforces for ledger commits only; ADR-0013:17-18 (refused
  while any row of the target is live; while a redaction runs the marker marks it) and FR-005 (spec.md:124) say the
  same of the target's rows;
- it closes F-C1350 at its cause (no non-ledger writer reads the marker) and also discharges, for bypass writers, the
  progress premise PF-6 that F-C1307 violates (a writer keeping a marked target live); only ledger commits into
  `lv \ rm` remain under PF-6;
- the alternative, "every batch re-checks the liveness of the rows it tombstones" (F-C1350's second remedy), would
  have to read committed state to resist open bypass transactions, and it leaves the run stuck while a writer writes
  (F-C1307); it is consistent with the same sources but not modelled.

The mechanism is a working assumption (no maintainer decision names it); the outcome (no write into a running
redaction's target) is supported by Ledger.cls:514.

**Invariant C4** (`biz.rs:204`, `mark_key_all`, part of `key_ok`): while a target is marked, no key its record match
selects has a visible row, an open bypass transaction, or a row an open erasure would restore. Inductive with G-B
(nothing open at Start), G-BM (nothing written there while marked), BlocksCommit (no ledger record there), and the head
lock (no erasure open at Start). No new proof hints were needed: the existing per-operation lemmas of `safety.rs`
discharge it.

**Theorem** (`theorems.rs:31`, `theorem_no_tombstone_of_live`, strengthened): a record becomes a tombstone only while
its key holds **no content of any provenance** (`!any_content`: no visible row and nothing a rollback of the open
transactions would leave), before and after the step, in addition to D-9's `!rec_content`.

**Control** `control_f1350_bypass_ignores_marker` removes G-BM (as at the pin): rejected at `protocol_top.rs:114`
(`lemma_p3_binds`). Counterexample `cx_f1350` (12 steps, F-C1350's live schedule): commit A's edge; erase A (3 steps);
open; start (entry check passes, A marked); a bypass writer writes A's row and commits (unrecorded, live); the first
batch tombstones A's record while its key holds that content (`any_content`); the run reaches its final step, which can
only be refused (`forall y. !sys_step(.., Final{ok: true}, y)`), and the marker stays (F-C1307); `!biz_inv` from the
bypass write on.

## 2. R4-03: F-1306 re-encoded as the pin writes it

`proofs-d9b`'s control modelled the replayed post-commit properties as recorded content (a store Apply,
`proofs-d9b/src/cx_f1306.rs:41`). The pin answers the replay from the stored revision (Ledger.cls:457-462, before the
marker check at 514-518) and the client then writes the post-commit properties **by direct SQL, without a ledger record
and without reading the marker** (client.py:445-481). Here that write is a **Writer step**:
`control_f1306_replay_direct_sql` replaces the reviewed replay's no-op (HD-1305) by a bypass write of the first
post-commit row, at level 3 (`protocol_top.rs`, `p3_lab_m`, `p3_lab_w`, guard: replay enabled, key bound, row locks;
no marker check). The Apply-encoded control of d9b is not carried (superseded).

What then fails, and where:
- rejected at `protocol_top.rs:114` (`lemma_p3_binds`: the reviewed replay changes nothing) and `:124`, `:125`
  (`lemma_p3_enabled`); located at level 3, where the writer participant is, not at level 2 as in d9b;
- counterexample `cx_f1306` (9 steps, the live probe's "during a run" case, `ib-HD1305-retry-revives`): commit A with
  key 9; erase A; open; start marks A; the retry is replayed and the client writes A's row by direct SQL; the write
  commits; the first batch tombstones A's record while its key holds that unrecorded content. Violations: C4 and the
  strengthened no-tombstone theorem (not C3, which only covers recorded content); the run's final step can only be
  refused;
- **qualification**: between an erasure and the redaction (no marker) the same direct write is a permitted unrecorded
  write in this model; the redaction's Start is then refused (target_live). That case is a progress/availability
  effect here, not a safety violation, because the model states no "erased content stays erased against writers
  outside the ledger" invariant (RPL-X of core M3-retry is not in this crate). So the located claim for F-1306 holds
  for the marked case only.

## 3. R4-04: premises (P-ids), and the one this audit had not named

| Id | Premise | Status |
|---|---|---|
| P-D9-1..P-D9-5, P-D9b-1..P-D9b-4, PF-1..PF-6 | as in `proofs-d9b/PROOFS.md` section 5 | unchanged; P-D9-3 is false at the pin (below) |
| P-LV (named here) | the liveness check sees every row of the target (LiveRows counts every content row its predicate selects) | used by Start and Final in every D-9 crate; **false at the pin** (F-C1351) |
| design | G-BM (new) with D-9/D-9b's G-L, G-P (incl. `rm ⊆ sc`), G-B, G-BE, R-1, the reader epoch, D-1, D-2 | **none is at the pin** |

## 4. Controls (each must fail only in its file and has a proved counterexample)

Counts: baseline 158 functions; a safety control run has 159 (its counterexample added). Logs:
`$RUN_DIR/proofs-d9c/run-20261114T125652Z/<feature>.log`, each ending with its RUNNER SUMMARY line. Counterexamples are
d9b's except `cx_f1350` (new) and `cx_f1306` (re-encoded); their steps are described in `proofs-d9b/PROOFS.md` section 7.

| Control (guard; finding) | Rejected at | Counterexample | Counts | Registry |
|---|---|---|---|---|
| `control_bypass_start` (G-B; F-C1301) | `protocol_top.rs:114` | `cx_bypass_start` | 158 / 1 | `proofs-d9c-bypass-start` |
| `control_bypass_erase` (G-BE) | `protocol_top.rs:114` | `cx_bypass_erase` | 158 / 1 | `proofs-d9c-bypass-erase` |
| **`control_f1350_bypass_ignores_marker`** (**G-BM**; **F-C1350**) | `protocol_top.rs:114` | **`cx_f1350`** (12; section 1) | 158 / 1 | `proofs-d9c-f1350-bypass-ignores-marker` |
| **`control_f1306_replay_direct_sql`** (HD-1305, re-encoded; **F-1306**) | `protocol_top.rs:114`, `:124`, `:125` | **`cx_f1306`** (9; section 2) | 157 / 2 | `proofs-d9c-f1306-replay-direct-sql` |
| `control_liveness_dirty` (G-L; F-C1201) | `protocol_sys.rs:114`, `:122` | `cx_liveness_dirty` | 157 / 2 | `proofs-d9c-liveness-dirty` |
| `control_unaligned_rm` (G-P `rm ⊆ lv`; F-1304) | `protocol_sys.rs:114` | `cx_unaligned_rm` | 158 / 1 | `proofs-d9c-unaligned-rm` |
| `control_unaligned_sc` (G-P `sc ⊆ rm`) | `protocol_sys.rs:114` | `cx_unaligned_sc` | 158 / 1 | `proofs-d9c-unaligned-sc` |
| `control_sc_narrow` (G-P `rm ⊆ sc`) | `protocol_sys.rs:114` | `cx_sc_narrow` | 158 / 1 | `proofs-d9c-sc-narrow` |
| `control_f1201_erase_unlocked` (HD-1201; F-1201) | `protocol_sys.rs:114`, `:123` | `cx_f1201` | 157 / 2 | `proofs-d9c-f1201-erase-unlocked` |
| `control_fcs01_noop_unrecorded` (R-1; F-CS01) | `protocol_rl.rs:389` | `cx_fcs01` | 158 / 1 | `proofs-d9c-fcs01-noop-unrecorded` |
| `control_f1302_unlocked_start` (HD-1301; F-1302) | `protocol_rl.rs:389`, `:393`, `:407` | `cx_f1302` | 157 / 2 | `proofs-d9c-f1302-unlocked-start` |
| `control_f1303_other_marker` (own-marker Final; F-1303) | `protocol_rl.rs:389` | `cx_f1303` | 158 / 1 | `proofs-d9c-f1303-other-marker` |
| `control_f1402_reader_no_recheck` (reader re-check; F-1402) | `protocol_rd.rs:265` | `cx_reader` | 158 / 1 | `proofs-d9c-f1402-reader-no-recheck` |
| `control_reader_marker_recheck_only` (epoch; HD-1401 b1) | `protocol_rd.rs:265` | `cx_reader` | 158 / 1 | `proofs-d9c-reader-marker-recheck-only` |
| `control_progress_rewind` (D-1; progress-only) | `progress.rs:192` | — | 157 / 1 | `proofs-d9c-progress-rewind` |
| `control_bound_follows_tail` (D-2, D-12; progress-only) | `progress.rs:184` | — | 157 / 1 | `proofs-d9c-bound-follows-tail` |

The four level-3 safety controls share one error line (`lemma_p3_binds`'s postcondition); each run's log and JSON
differ and each lists its own counterexample as verified.

## 5. Open obligations (nothing below is proved)

- Everything in `proofs-d9b/PROOFS.md` section 10 (code correspondence D-2..D-5; verify()'s table read and node
  identity; readers' progress; post-commit recovery; F-CS01's design intent-undecided; statement-history abstraction;
  restore and redactedRev; eraser variants; temporal-only storage; lock timeouts; graph-blind replay P-D9-5; HD-1304's
  receipt; PF-1..PF-6).
- G-BM is a working assumption on the mechanism; the RED-B1.1 reading behind F-C1350 ("is content re-created outside
  the ledger after the entry check live?") is the maintainer question review-4 adds. Under the recorded-content
  reading, `proofs-d9b`'s theorem suffices; under F-C1350's, only this crate's.
- F-1306 between an erasure and the redaction (no marker): a permitted unrecorded write in this model (section 2).
- P-LV (F-C1351) and P-D9-3 (F-C1850, F-C1150) are violated at the pin and are not modelled: the model's liveness check
  sees every row, and no writer outside the modelled actions writes ledger globals.
- The ledger's own epoch and G-BM's marker read are reviewed additions; their cost at the pin (every writer reads a
  global) is not assessed.

## 6. Cost (measured, `RESULTS.json`)

Baseline: wall 8.26 s, Verus 7.78 s, SMT 20.3 s (summed over threads), 38.22 M rlimit over 158 functions (d9b: 37.97 M).
Per module (rlimit): theorems 8.99 M, witness_meta 7.02 M, progress 6.10 M, witness 4.73 M, safety 3.62 M (d9b
3.42 M: C4), witness_rd 3.54 M, protocol_rl 1.94 M, protocol_rd 0.66 M, others < 0.5 M. Largest functions:
`witness_meta::witness_noop_recorded` 6.34 M, `theorems::theorem_marker_owned` 3.15 M, `theorems::theorem_retry_refused`
2.98 M. Each control run 7.4-8.5 s wall. No rlimit raised.

## 7. Trust inventory

This crate: no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp` (scanned over
all 34 source files; `--no-cheating`). `actors` (`c03f9fa`): none. vstd is Verus's trusted base. Declared empty.

## Premises the pin violates (read before citing any result)

None of the reviewed guards exists at the pin, so the product's obligations stay failed as the as-built evidence says.
Complete list after review-4 R4-04:

| Premise or reviewed element | At the pin | Evidence |
|---|---|---|
| **G-BM** bypass writers honour the marker; and the theorem's reading (any content is live) | no non-ledger writer reads `^IVG.Ledger("redacting")`; BatchInLock re-checks nothing | **F-C1350**, live (`ws-live-ins-*`, 12 writers); control `proofs-d9c-f1350-bypass-ignores-marker` |
| G-B writers serialize with redaction start | no writer takes a lock the redaction takes | **F-C1301 live** (`ws-live-fc1301-delete-reification`), and F-C1350 as further live evidence of the missing writer coordination |
| G-L liveness on committed state / under the eraser's lock | unlocked, READ UNCOMMITTED entry check | F-C1201, live |
| eraser head lock (HD-1201) | absent | F-1201, live |
| G-P `rm ⊆ lv` | `redact(None)` without a prefix; temporal-only edges | F-1304, F-C1308, live |
| **P-LV** the liveness check sees every row of the target | LiveRows' indexed counts miss `%NOINDEX` rows | **F-C1351**, live (`ws-live-noindex`) |
| **P-D9-3** bypass writers write content rows only, never ledger globals | restore/ImportGlobals write records, marker, idemRedacted, redactedRev; an SQL INSERT into ledger_revisions is accepted | `followup-writer-census` (5 ledger writers outside the modelled actions), **F-C1850** live (`ws-live-gap-restore`, `ws-live-gap-marker`), **F-C1150** live (`ws-live-sql-insert-wedge`) |
| R-1 every operation leaves a record | a no-op leaves none; row and binding written anyway | F-CS01, live `sim-fcs01-minimal` |
| locked Start with its marker; own-marker Final | unlocked checks, late marker; Final removes any marker | F-1302, F-1303, live |
| a replay applies nothing | the client re-applies post-commit properties by direct SQL | F-1306, live `ib-HD1305-retry-revives` (control `proofs-d9c-f1306-replay-direct-sql`) |
| readers re-check marker and epoch | one marker check before a lazy paged read; no epoch | F-1402, live `ib-HD1401-reader-full-race` |
| D-1 cursor kept with the marker; D-2 bound fixed at marking | process-local cursor, rescans; bound follows the tail | F-C1303 live; LedgerRedact.cls:213-226, 308-313 (inspected) |
| PF-6 the target is eventually not live at Final | a non-strict writer keeps a marked target live | F-C1307, live |
