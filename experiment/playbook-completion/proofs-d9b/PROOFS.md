# PROOFS-D9B: revision metadata, retry keys, statement history, readers and the scan bound (proof debts D-9, D-12)

Crate `experiment/playbook-completion/proofs-d9b` (`ivg-proofs-d9b`), a copy of `proofs-d9` (registered results
unchanged), Verus 0.2026.10.04, vstd 0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved**
(decisive, `--no-cheating`, no trusted items), about **models only**. No proof here connects the ObjectScript or Python
at pin `3eaa79cf` to these contracts, and none of the guards proved necessary here is present at the pin. Every result
below reads "the reviewed model satisfies ...". None of it is a property of the product.

| Item | Result | Registry |
|---|---|---|
| Baseline `cargo verus verify -- --no-cheating` | **158 verified, 0 errors**, wall 9.1 s, Verus 8.6 s, 37.97 M rlimit | `proofs-d9b-baseline` |
| Safety controls (6 of D-9 kept working + 7 new) | 13 of 13 rejected only in the expected file; every function outside it verifies and is the baseline's; each has a proved reachable counterexample | `proofs-d9b-{bypass-start, bypass-erase, liveness-dirty, unaligned-rm, unaligned-sc, f1201-erase-unlocked, fcs01-noop-unrecorded, f1302-unlocked-start, f1303-other-marker, f1306-replay-reapplies, sc-narrow, f1402-reader-no-recheck, reader-marker-recheck-only}` |
| Progress-only controls (D-1 rewind kept; **D-12 new**) | each fails only `progress::RunProgress::nonincreasing`; the 147 functions outside `progress` all verify and are exactly the baseline's | `proofs-d9b-progress-rewind`, `proofs-d9b-bound-follows-tail` |
| Trust inventory | empty (this crate and `actors`) | `RESULTS.json` `trust_inventory` |
| Gate | **pass** (`RESULTS.json`, sources SHA-256 `f07f7c4d...`, logs `$RUN_DIR/proofs-d9b/run-20261114T120856Z/`) | |
| Independent recheck | gate **pass**, same sources, same counts and locations (`$RUN_DIR/proofs-d9b-recheck/run-20261114T121143Z/`) | `proofs-d9b-recheck` |

Rerun: `source experiment/playbook-completion/environment.sh; python experiment/playbook-completion/proofs-d9b/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600`, after `cargo clean -p`; logs in a new `run-<stamp>/`
directory under `$PROOFS_OUT_DIR` or `$RUN_DIR/proofs-d9b`; `--register` refuses an id that is already recorded and
takes `--id-suffix`/`--id-prefix` for a rerun). The gate now also requires, for each safety control, that every function
outside the expected file and outside its counterexample module verifies and equals the baseline's set.

## 0. What was asked, and what changed against `proofs-d9`

`proofs-d9/PROOFS.md` section 9 left these D-9 obligations explorer-only; D-12 was not written. Each is now in the
model, in priority order:

| # | Obligation | Here | Where |
|---|---|---|---|
| 1 | **F-CS01** (live `sim-fcs01-minimal`): a changeset whose operations record nothing still writes a revision row and a key binding (Ledger.cls:489-492 counts operations; :520-525 writes regardless); metadata is cleared only on a revision's first tombstone (LedgerRedact.cls:332-347) | revision metadata `meta[i] = {txt, key, okey, named}`; zero-record revisions; reviewed design **R-1** (a no-op operation leaves a content-free no-op record, `Eff::Nop`); `theorem_redaction_clears_metadata`; as-built control `control_fcs01_noop_unrecorded` with `cx_fcs01` | `ledger.rs`, `vocab.rs`, `protocol_rl.rs`, `theorems.rs`, `cx_fcs01.rs`, `witness_meta.rs` |
| 2 | **INV-retry**: after a complete redaction a same-key retry is refused, never replayed, never re-created | `idem`/`idemr` with the move at the tombstone (LedgerRedact.cls:359-365); `theorem_retry_refused`, `theorem_retry_refused_forever`, `theorem_redaction_retry_refused`; broken by the F-CS01 control (`cx_fcs01`: key 2 still replayed) | `ledger.rs`, `theorems.rs` |
| 3 | **D-12**: progress-only control for D-2 (scan bound fixed at marking) | `control_bound_follows_tail`: commits while marked move the bound to the head; fails only progress, at the **commit** case | `ledger.rs` (`bound_after_commit`), `progress.rs:184` |
| 4 | **Statement history**: closed `^IVG.Ledger("stmt")` entries and DropStatements on closed entries | store `shist` (live and closed entries) with the erasure's undo log; side condition part `rm ⊆ sc` on edges; `theorem_final_clears_statement_history`, `theorem_erasure_clears_statement_history`; control `control_sc_narrow` | `store.rs`, `vocab.rs`, `theorems.rs`, `cx_sc_narrow.rs` |
| 5 | **Readers and verify() racing a redaction** (F-1402, HD-1401) | participant **Reader** and protocol `ReadP: RL x Reader -> RdOuter` (a partition, section 2); redaction epoch (reviewed); `theorem_accepted_view_consistent`; as-built control `control_f1402_reader_no_recheck` and the (b1) control `control_reader_marker_recheck_only`, one counterexample `cx_reader` | `reader.rs`, `protocol_rd.rs`, `witness_rd.rs`, `cx_reader.rs` |
| 6 | **F-1306** (a replayed retry re-applies post-commit properties) and **Decision 2** (revision free text) | `theorem_replay_changes_nothing`; control `control_f1306_replay_reapplies` (`cx_f1306`); `theorem_decision2_any` and `witness_decision2_spanning` | `protocol_sys.rs`, `theorems.rs`, `cx_f1306.rs`, `witness_meta.rs` |
| 7 | Re-run **F-1302, F-1303, F-1306** as located controls in this crate | `control_f1302_unlocked_start` (`cx_f1302`), `control_f1303_other_marker` (`cx_f1303`), `control_f1306_replay_reapplies` | `protocol_rl.rs`, `protocol_sys.rs` |

No item failed to converge; nothing was partitioned for lack of convergence. The readers are a deliberate partition
(they write nothing; section 2).

## 1. Participants (each `Contract` + `SafeContract`, own state only)

| Participant | State (D-9b additions in bold) | Labels | Own invariant |
|---|---|---|---|
| **Ledger** (`ledger.rs`) | history; **`meta[i]`: revision row (`txt` free text present, `key` idempotency_key column; ghost `okey` the key committed with, `named` the keys the changeset's operations addressed)**; `idem`; **`idemr` (`^IVG.Ledger("idemRedacted", sha256(key))`)**; head lock; enabled; marker (three-predicate target) with cursor and bound; count/tally; **`epoch` (reviewed, readers)** | `Commit { cs, named, key }` (**as built: needs `named.len() > 0`, i.e. counts operations, Ledger.cls:489-492; BlocksCommit on records only**), `Replay`, `Lock`, `Unlock`, `SetEnabled`, `Mark` (**epoch+1**), `Batch` (**its tombstone clears its revision's row and moves its key to idemRedacted**, LedgerRedact.cls:332-377), `Rewind`, `Audit` (**epoch+1**, content-free row) | count = tally; no marker ⇒ count 0; **`meta_ok`**: one row per revision; bound key ⇔ row key; idemRedacted ∩ idem = ∅; a row with text carries its committed key; a cleared row carries none and its committed key is in idemRedacted; **a revision with a tombstone has no text (Decision 2)** |
| **Redactor** (`redactor.rs`) | as in D-9 | as in D-9 | as in D-9 |
| **Store** (`store.rs`) | rows, `unrec`, live index `stmts`, **statement history `shist` (live and closed `("stmt")` entries)**, open erasure with undo log (**+ `ssh`, the history entries its cleanup killed**) | as in D-9; `Apply` opens history entries; `EraseIndex` kills the graph's live and closed entries (Eraser.cls:1117-1144); `Drop` kills the target's live and closed entries (LedgerRedact.cls:444-471); `EraseAbort` restores them | structural: index and history hold edges only; undo log inside the erasure's target |
| **Writer** (`writer.rs`) | as in D-9 | as in D-9 | `true` |
| **Reader** (`reader.rs`, new) | `rd[q] = {e0, view}`: a read in progress, the epoch it began with, the revisions read so far | `Begin { q, e0 }`, `Page { q, rs }` (one revision as it is now), `Accept { q }`, `Refuse { q }` | `true` |

## 2. Levels and guards

**Level 1 `RLP`: Ledger x Redactor → `RL`** (`protocol_rl.rs`): D-9's guards plus **R-1 (Commit)**: every key the
changeset's operations address has a record of the changeset (`ops_recorded(cs, named)`); a no-op operation's record
is `Eff::Nop` (changes no row, statement or provenance; the scan's record match sees it). `rl_inv` adds `attr_ok`: every
key a revision's operations addressed is named by one of its records (live or tombstoned).

**Level 2 `SysP`: RL x Store → `Mid`** (`protocol_sys.rs`, `mid.rs`): D-9's G-L, G-P and pending domains, with the
side condition strengthened: `aligned(t) = rm ⊆ lv ∧ sc ⊆ rm (edges) ∧ rm ⊆ sc (edges)` (`vocab.rs`); at the pin
Matches and DropStatements both select relationships by graph plus endpoint prefix (LedgerRedact.cls:93-111, 453-456),
so the new part holds there for relationships, up to qualifier records Matches cannot attribute (-1). Replay's store
part is none (HD-1305).

**Level 3 `TopP`: Mid x Writer → `Biz`** (`protocol_top.rs`, `biz.rs`): unchanged (G-B, G-BE, row locks). The open
erasure's overlay gains: after its cleanup no history entry of its target remains.

**Readers `ReadP`: RL x Reader → `RdOuter`** (`protocol_rd.rs`). A **partition**: readers write nothing and read only
ledger globals, so they compose with RL. `theorem_biz_ledger_step` proves that the ledger part of every Biz step is an
RL step or leaves RL unchanged, and `theorem_biz_step_is_rd_step` that every Biz step is, for readers in any state, an
RdOuter step or invisible; hence every interleaving of a Biz execution (store, erasures, bypass writers included) with
reader steps is an RdOuter execution. Reviewed reader protocol (HD-1401 working answer (b2)): begin only with no marker,
recording the epoch; read one revision per step as it is; return the view only if after reading there is no marker
**and the epoch is unchanged**, otherwise refuse. `step_binds`/`step_enabled` proved (`lemma_rd_binds`,
`lemma_rd_enabled`); any implementations of RL and Reader refine RdOuter and keep `rd_inv`
(`theorem_rd_implementations_refine`, `_safe`).

Every level proves `step_binds` and `step_enabled` for every operation (`lemma_p1_*`, `lemma_p2_*`, `lemma_p3_*`,
`lemma_rd_*`); `system.rs`'s generic composition (any implementations of Ledger, Redactor, Store, Writer refine Biz and
keep `biz_inv`) is unchanged and re-verified.

## 3. Invariants

`biz_inv` (proved inductive in `safety.rs`) is D-9's with `inv_parts` now including `meta_ok` (through `ledger_inv`)
and `attr_ok`, and `ers_key_ok` including the statement history. `rd_inv` (`protocol_rd.rs`): `rl_inv`, and for every
read in progress: `e0 ≤ epoch`, and while `epoch == e0` there is no marker and its view is a prefix of the current
history (no tombstone was written since it began: tombstones need a marker, a marker needs a start, a start advances the
epoch).

## 4. Theorems (exact statements in `theorems.rs`, `protocol_rd.rs`)

- **F-CS01's invariant** `theorem_redaction_clears_metadata(x, p, y, i)`: a successful Final of t leaves every revision
  `attributed` to `t.rm` (a record of it names a key of `t.rm`, or a key its operations addressed is in `t.rm`) with
  its metadata redacted (`meta_redacted`: no text, no key column, the committed key in idemRedacted and unbound); the
  row is unchanged by the Final. Intended: spec 256 US1 (spec.md:42-44), FR-004 (spec.md:121-123: a revision with no
  record has every record redacted), SC-001 (spec.md:142-143), plan.md:25.
- **Decision 2** `theorem_decision2_any`: in every invariant state a revision with a tombstone has its metadata redacted
  (spec.md:156, ADR-0013:15; HD-1302 "any", supported).
- **INV-retry** `theorem_retry_refused` (step: a key in idemRedacted is neither replayed nor bound, and stays),
  `theorem_retry_refused_forever` (over every `biz_run` from the moment it is in idemRedacted), and
  `theorem_redaction_retry_refused` (after a successful Final of t at step n, no later step replays or binds the
  committed key of any revision attributable to t): a same-key retry is refused (`idempotency_redacted`, Ledger.cls:
  468-473), never replayed and never re-created (ADR-0013:15; spec.md:104-105).
- **Statement history** `theorem_final_clears_statement_history`: a successful Final of t leaves no statement entry,
  live or closed, of an edge `t.rm` selects (spec.md:102-103: "stmt entries for deleted statements must be redacted
  too"); `theorem_erasure_clears_statement_history`: an erasure's commit leaves none of its target.
- **Readers (RPL-I1)** `theorem_accepted_view_consistent`: a returned view is a prefix of the current history, with no
  marker, and the epoch unchanged since the read began — a cut of one history with no tombstone written during the
  read, never a redaction half done (Decision 3 spec.md:155; client.py:691-692).
- **Replay** `theorem_replay_changes_nothing`: a replayed retry leaves the whole business state unchanged (HD-1305;
  ledger-api.md:26).
- Every D-9 theorem (no tombstone of live content, per-target audit, marker ownership, statements match, replay =
  store once settled, Start reads committed state, pending needs cover, marked target aligned) re-verified unchanged.
- **Qualification (doc fix after review-4 R4-01; not in the sources hash).** `theorem_no_tombstone_of_live` holds for
  **recorded content only** (`!rec_content`): this reviewed design admits a ledger-bypassing writer re-creating target
  content after the entry check (a bypass `BBegin` is admitted while the marker exists, `biz.rs:70`), whose history the
  batches then tombstone — F-C1350, live (`ws-live-ins-store_node` and 11 sibling runs). F-C1350's working answer reads
  RED-B1.1/FR-005 as the product's own checks do (any content row of the target is live); under that reading this
  design does not exclude F-C1350, and the recorded-content reading is **intent-undecided** against it (maintainer
  question in review-4 §5). `proofs-d9c` adds the guard G-BM (bypass writers honour the marker) and proves the theorem
  for content of any provenance.

## 5. Premises (named; D-9's P-D9-1..P-D9-5 and PF-1..PF-6 carried unchanged)

| Id | Premise | Status |
|---|---|---|
| P-D9b-1 | A revision's free text (message, source, correlation id) and idempotency key may name the tenant of any entity its changeset's operations address (ghost `named`), and are what SC-001's scan would find; attribution is by those keys, not by content analysis | modelling premise; the simulator's oracle attributes metadata the same way (F-CS01) |
| P-D9b-2 | `idemRedacted` is keyed by sha256(key); modelled by the key itself (no collision) | assumed (SHA-256) |
| P-D9b-3 | One statement-history key per edge stands for every `("stmt")` id of that edge (a re-created edge gets a new id); EraseLedgerFor and DropStatements select ids by graph and endpoints, so they treat every id of a key alike | by inspection (Eraser.cls:1117-1144, LedgerRedact.cls:446-471) |
| P-D9b-4 | Readers read ledger globals only (records, marker; epoch in the reviewed design), unisolated (globals); one page is one revision, which over-approximates every page size (replay.py:17, 252) | by inspection; verify()'s table read is outside the model |
| design | R-1 (no-op records), the strengthened G-P (`rm ⊆ sc` on edges), the redaction epoch and the reviewed reader protocol, plus D-9's G-L, G-P, G-B, G-BE and D-1/D-2 | **none is at the pin** |

Simplification (not a premise): a tombstone clears its revision's row every time; the pin clears only on the first
(`redactedRev`, LedgerRedact.cls:345), which is value-equivalent because a cleared row has nothing left to clear. The
cases where `redactedRev` and the row disagree (restore, F-1801) are not modelled.

## 6. Intent of the reviewed F-CS01 design: **intent-undecided**

No source in `intent/` or `experiment/playbook-uplift/DECISIONS.md` decides what an all-no-op changeset should leave
(searched: no-op, op_count, zero-record, empty revision; spec 213's contracts only say a replay returns the original
outcome, ledger-api.md:26). Decided around it: FR-004/SC-001 (the zero-record revision's metadata must not survive),
plan.md:25 and ADR-0013:15 (a redacted revision's key must neither replay nor re-create), Decision 2 "any" (HD-1302,
supported).

- **Working assumption (modelled): R-1** — record each no-op operation as a content-free no-op record carrying the
  entity id and graph (the F-CS01 remedy's option (b)). Every revision then has a record for each operation, the target
  predicate matches it, its tombstone clears the metadata and moves the key. Proved: `theorem_redaction_clears_metadata`
  and INV-retry hold for zero-record changesets, and also for **mixed** changesets (a no-op of tenant A inside a
  changeset whose other records are tenant B's), whose metadata Decision 2 then clears on A's redaction.
- Alternative (a): a changeset whose operations record nothing writes no revision and binds no key. Satisfies SC-001
  for the all-no-op case, but leaves no key to move: a retry of a keyed all-no-op changeset after the tenant's erasure
  and redaction is a first attempt and may re-create the tenant (ADR-0013:15), and the mixed case keeps A-naming
  metadata. Reasoning only, not proved.
- Alternative (c): at Final, clear zero-record revisions whose changeset named the target; needs the ids, which only
  R-1 keeps.
- Residual question: does Decision 2 apply to a revision in which the target has only no-op operations? Working answer:
  yes (R-1). At the pin such a mixed revision keeps its metadata through the redaction (same mechanism as F-CS01;
  model reasoning, not reproduced live; not filed as a new finding: same root cause, recorded here).

## 7. Controls (each changes one decision; each must fail only in its file and has a proved counterexample)

Counts: baseline 158 functions; a safety control run has 159 (its counterexample added). "Rejected at" lists Verus's
error lines. Logs: `$RUN_DIR/proofs-d9b/run-20261114T120856Z/<feature>.log`.

| Control (guard; finding) | Rejected at | Proved counterexample (steps; violation) | Counts | Registry |
|---|---|---|---|---|
| `control_bypass_start` (G-B; F-C1301) | `protocol_top.rs:74` `lemma_p3_binds` | `cx_bypass_start` (6; D-9's, unchanged) | 158 / 1 | `proofs-d9b-bypass-start` |
| `control_bypass_erase` (G-BE) | `protocol_top.rs:74` `lemma_p3_binds` | `cx_bypass_erase` (6) | 158 / 1 | `proofs-d9b-bypass-erase` |
| `control_liveness_dirty` (G-L; F-C1201) | `protocol_sys.rs:122` `lemma_p2_binds`, `:130` `lemma_p2_enabled` | `cx_liveness_dirty` (6) | 157 / 2 | `proofs-d9b-liveness-dirty` |
| `control_unaligned_rm` (G-P `rm ⊆ lv`; F-1304) | `protocol_sys.rs:122` `lemma_p2_binds` | `cx_unaligned_rm` (4) | 158 / 1 | `proofs-d9b-unaligned-rm` |
| `control_unaligned_sc` (G-P `sc ⊆ rm`) | `protocol_sys.rs:122` `lemma_p2_binds` | `cx_unaligned_sc` (7) | 158 / 1 | `proofs-d9b-unaligned-sc` |
| `control_f1201_erase_unlocked` (HD-1201 lock; F-1201) | `protocol_sys.rs:122` `lemma_p2_binds`, `:131` `lemma_p2_enabled` | `cx_f1201` (4) | 157 / 2 | `proofs-d9b-f1201-erase-unlocked` |
| **`control_fcs01_noop_unrecorded`** (R-1; **F-CS01**, as built Ledger.cls:489-492, 520-525, LedgerApply.cls:229-233, 252-263) | `protocol_rl.rs:389` `lemma_p1_binds` | `cx_fcs01` (12, the live minimal schedule: commit A's node with key 1; commit a no-op changeset on A's node with key 2 — **no record**, row with text and key 2, key 2 bound; erase A; open; start; 3 scans; ToFinal; Final ok): revision 0 redacted and key 1 in idemRedacted, but revision 1, attributable to A, keeps its text and key 2, key 2 still bound, and `Replay{key: 2}` is a step after the complete redaction (**INV-retry broken**: replayed instead of refused); `!meta_redacted(z12, 1)`; `!biz_inv` from the zero-record commit on | 158 / 1 | `proofs-d9b-fcs01-noop-unrecorded` |
| **`control_f1302_unlocked_start`** (HD-1301 locked Start; **F-1302**, re-run) | `protocol_rl.rs:389`, `:393` `lemma_p1_binds`, `:407` `lemma_p1_enabled` | `cx_f1302` (8: commit A's edge; erase A (3 steps); open; start writes no marker; commit re-creates A; the first batch tombstones A's record while its key holds recorded content and only then writes the marker); `!biz_inv` | 157 / 2 | `proofs-d9b-f1302-unlocked-start` |
| **`control_f1303_other_marker`** (Final under its own marker; **F-1303**, re-run) | `protocol_rl.rs:389` `lemma_p1_binds` | `cx_f1303` (17: B committed and erased; p0 redacts A to Final; p2 resumes A to Final; p0 finishes; p1 marks B and tombstones B's record; p2's Final runs under B's marker: `Audit{A, 1}` counting B's record, B's marker removed while B's run is in Batches) | 158 / 1 | `proofs-d9b-f1303-other-marker` |
| **`control_f1306_replay_reapplies`** (HD-1305; **F-1306**, re-run) | `protocol_sys.rs:122` `lemma_p2_binds`, `:132` `lemma_p2_enabled` | `cx_f1306` (7: commit A with key 9; erase A; open; start marks A; replay of 9 writes A's content again: A holds recorded content while marked); `!biz_inv`. **Qualified (doc fix after review-4 R4-03):** this control models the replayed post-commit properties as *recorded* content (a store Apply, `cx_f1306.rs:41`); the pin writes them by direct SQL without a ledger record (`client.py:445-481`), so the location is that of the recorded-content encoding, not of the pin's write. `proofs-d9c` re-encodes it as a Writer step (`proofs-d9c-f1306-replay-direct-sql`) | 157 / 2 | `proofs-d9b-f1306-replay-reapplies` |
| **`control_sc_narrow`** (G-P `rm ⊆ sc` on edges; design control, no pin finding) | `protocol_sys.rs:122` `lemma_p2_binds` | `cx_sc_narrow` (10: A's edge created then deleted — closed entry; the redaction of A with a cleanup that misses the edge tombstones both records and completes; the closed statement entry of A's edge survives); `!biz_inv` at the marking | 158 / 1 | `proofs-d9b-sc-narrow` |
| **`control_f1402_reader_no_recheck`** (reviewed reader re-check; **F-1402**, as built client.py:720-728, replay.py:231-269) | `protocol_rd.rs:265` `lemma_rd_binds` | `cx_reader` (14: two commits of A; a reader finds no marker and reads revision 0; a whole redaction of A runs (open, start, 4 scans, ToFinal, Final); the reader reads revision 1 and returns `[[Live a1], [Tomb a2]]`: revision 0 as before the redaction, revision 1 as after it — neither history; marker absent at both ends, epoch 0 → 2) | 158 / 1 | `proofs-d9b-f1402-reader-no-recheck` |
| **`control_reader_marker_recheck_only`** (epoch; HD-1401 alternative (b1)) | `protocol_rd.rs:265` `lemma_rd_binds` | the same `cx_reader`: the post-read marker re-check passes (no marker), only the epoch detects it (live `ib-HD1401-reader-full-race`) | 158 / 1 | `proofs-d9b-reader-marker-recheck-only` |

No control passes as a stutter: `step_binds` demands one outer step per protocol step. The two bypass controls produce
byte-identical diagnostics (same lemma, same line), as in D-9; their logs differ and each lists its own counterexample.

## 8. Progress (`progress.rs`) and D-12

`theorem_redaction_completes` (productive fairness ⇒ a marked run has a successful Final), `theorem_work_available`
and the premises PF-1..PF-6 are D-9's, unchanged and re-verified.

**Progress-only controls** (each: 157 verified, 1 error; the 147 functions outside `progress` all verify and are exactly
the baseline's, `safety_still_verifies: true`):

| Control (element) | Fails at | Meaning | Registry |
|---|---|---|---|
| `control_progress_rewind` (D-1: cursor survives a stop) | `progress.rs:192`, the resume case of `RunProgress::nonincreasing` | as in D-9 (LedgerRedact.cls:213) | `proofs-d9b-progress-rewind` |
| `control_bound_follows_tail` (**D-2: bound fixed at marking; D-12**) | `progress.rs:184`, the **commit** case of `RunProgress::nonincreasing` (`assert(run_rank(v.s) <= run_rank(s))`) | with the bound following the tail as the pin's scan does (it runs until `$Order` finds no further revision, LedgerRedact.cls:216-226, 308-313), a commit while marked — which BlocksCommit admits only outside the target, so another tenant's — adds its records to the run's remaining work. Every safety proof still holds (widening the window keeps `cursor_ok`, `lemma_cursor_commit`). So, in the reviewed model, **D-2 is what keeps commits by other tenants from prolonging a run**; without it progress needs the premise "commits pause" (the original P-1306) | `proofs-d9b-bound-follows-tail` |

Modelling note on the D-12 variant: the bound is kept with the marker, so a process attached with the old bound is no
longer at the marker's cursor after such a commit and continues after a resume (PF-1). The located failure is the rank
increase at the commit itself, which does not depend on that.

## 9. Non-vacuity

`step_enabled` at all four protocols for every operation. Witnesses (each step checked against the outer contract and
keeping its invariant): D-9's `witness_erasure_rollback`, `witness_bypass_and_redaction`, `witness_settled`;
`witness_noop_recorded` (F-CS01's schedule under R-1: the no-op record is tombstoned, both revisions end redacted, keys
1 and 2 in idemRedacted, `Replay{2}` impossible); `witness_decision2_spanning` (revision 0 spans A and B with key 9;
after A's redaction B's record is still live, the row is redacted, key 9 neither replayable nor bindable);
`witness_reader_accepts` (a reader returns the history); `witness_reader_refuses` (the reviewed reader refuses the
`cx_reader` read: sharpness of the epoch).

## 10. Open obligations (nothing below is proved)

- **Correspondence to code** (D-2..D-5) is untouched: no proof links Ledger.cls, LedgerRedact.cls, Eraser.cls or the
  Python readers to these contracts.
- **verify()**: only its record read is a reader here; its table read, the coherence of its two reads, and its
  graph-blind node identity (F-1401, HD-1401(a)) are not modelled.
- **Readers' progress** ("readers can always finish", core M3-readers AG EF) is not proved; only safety (RPL-I1).
- **Post-commit properties** (HD-1305): only "a replay changes nothing" is proved; the recovery of a first attempt whose
  property write failed, and the first attempt's own late property write racing an erasure (core
  `m3-as-built-pcp-race`), are not modelled.
- **F-CS01 reviewed design** is intent-undecided (section 6); the mixed-revision case is proved only under R-1, and is
  not reproduced on the pin.
- **Statement history**: per-key abstraction (P-D9b-3); prefix erasure (EraseNodes/EraseEdges) cleanup of closed entries
  and qualifier records Matches cannot attribute (-1) are not modelled.
- `redactedRev` and restore (F-1801, F-C1304) are not modelled.
- Carried from D-9: eraser variants (EraseNodes, EraseEdges, EraseAll), temporal-only storage (F-C1308 only as the shape
  `rm ⊄ lv`), lock timeouts, graph-blind replay (P-D9-5), HD-1304's "incomplete" receipt; PF-1..PF-6 not discharged
  against IRIS scheduling.

## 11. Cost (measured, `RESULTS.json`)

Baseline: wall 9.05 s, Verus 8.57 s, SMT 21.4 s (summed over threads), 37.97 M rlimit over 158 functions (D-9: 20.06 M
over 115). Per module (rlimit): theorems 9.12 M, witness_meta 7.04 M, progress 6.13 M, witness 4.53 M, witness_rd
3.54 M, safety 3.42 M, protocol_rl 1.94 M, protocol_rd 0.65 M, vocab 0.41 M, ledger 0.31 M, system 0.27 M, others
< 0.2 M. Largest functions: `witness_meta::witness_noop_recorded` 6.35 M (4.8 s), `theorems::theorem_retry_refused`
3.42 M, `theorems::theorem_marker_owned` 2.73 M, `witness_rd::lemma_rd_run` 2.31 M. Each control run: 7.7-9.4 s wall.
No rlimit raised and no opaque layout needed; the metadata facts are a separate conjunct (`meta_ok`) proved once per
ledger operation (`lemma_meta_commit`, `_tomb`, `_audit`), so the per-key safety lemmas did not grow.

## 12. Trust inventory

This crate: no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two; scanned over all 33 source files). `actors` (`c03f9fa`): none (scanned;
verified in the same build without `--no-cheating`, which is forwarded to this crate only). vstd is Verus's trusted
base. Declared empty.

## Premises the pin violates (read before citing any result)

None of the reviewed guards exists at the pin, so the product's obligations stay failed as the as-built evidence says
(rows for P-D9-3, P-LV, F-C1301 live and F-C1350 added after review-4 R4-04; doc only, not in the sources hash):

| Reviewed element | At the pin | Evidence |
|---|---|---|
| R-1: every operation leaves a record | a no-op operation leaves none; the revision row and key binding are written anyway | F-CS01, live `sim-fcs01-minimal` (control `proofs-d9b-fcs01-noop-unrecorded`) |
| locked Start that writes its marker; Final under its own marker | unlocked opening checks, late marker; Final removes any marker | F-1302, F-1303, live (controls `proofs-d9b-f1302-unlocked-start`, `-f1303-other-marker`) |
| a replay applies nothing | a replay re-applies post-commit properties, by direct SQL without a ledger record (client.py:445-481) | F-1306, live `ib-HD1305-retry-revives` (control `proofs-d9b-f1306-replay-reapplies`, which encodes the write as recorded content; see section 7) |
| readers re-check marker and epoch | one marker check before a lazy paged read; no epoch exists | F-1402, live `ib-HD1401-reader-full-race` (controls `proofs-d9b-f1402-reader-no-recheck`, `-reader-marker-recheck-only`) |
| G-L, G-P, G-B, G-BE, eraser head lock | absent | F-C1201, F-1304, F-C1308, F-1201 live; F-C1301 **live** (`ws-live-fc1301-delete-reification`: a nested delete_reification's uncommitted delete passed the liveness check, its rollback restored rows under tombstones); F-C1350 live (`ws-live-ins-*`, 12 writers): no writer serializes with, or honours, the marker, the missing G-B side (D-9 controls) |
| P-D9-3: bypass writers write content rows only, never ledger globals | restore and ImportGlobals write records, marker, idemRedacted and redactedRev; a plain SQL INSERT into ledger_revisions is accepted | **violated**: `followup-writer-census` (5 ledger writers outside the modelled actions), F-C1850 live (`ws-live-gap-restore`, `ws-live-gap-marker`), F-C1150 live (`ws-live-sql-insert-wedge`) |
| (named here) P-LV: the liveness check sees every row of the target | LiveRows' indexed COUNT(*) misses rows a `%NOINDEX` bulk load wrote | **violated**: F-C1351 live (`ws-live-noindex`: the redaction completed while the tenant's rows existed; they reappeared at the index rebuild) |
| the no-tombstone theorem's reading: recorded content only | the product's own checks count any content row of the target as live | F-C1350 (live); intent-undecided; closed in the model by G-BM in `proofs-d9c` |
| D-1 cursor kept with the marker; D-2 bound fixed at marking | the cursor is process-local and a re-run rescans; the scan bound follows the tail | F-C1303 live; LedgerRedact.cls:213-226, 308-313 (inspected) |
| PF-6 (the target is eventually not live at Final) | a non-strict writer keeps a marked target live | F-C1307 live |

Statement history is the one area where the pin's own predicates satisfy the reviewed side condition (`rm = sc` on
relationships) and DropStatements removes closed entries; that is inspected, not proved of the product.
