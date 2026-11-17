# Iteration 60 repair: dispositions of review 60 (round 1)

Assignment: [ASSIGNMENT.md](ASSIGNMENT.md). Review: `$G5_RUN_STATE/review-60/REVIEW.md` (published review, read in
full; exposed). Repair builder session 2026-11-17, about 20:58Z to 21:45Z.

- Before: `030f1c536` (iteration 60 seal). Checkpoints: `00966ce88` (predictions frozen), `91d574425` (prediction
  addendum), `f2a342934` (repair batch), then the handoff commit with this file. Product pin `3eaa79cf` unchanged
  (consolidated confinement check passes).
- Fixture: local `ivg-uplift-next-20261115` (127.0.0.1:35975, IRIS 2026.1 Build 234U); every connection checked the
  instance hostname `1a97b1515453` against the container. Repair-owned namespaces, created additively from `%SYS` with
  `CREATE DATABASE` and deployed with `initialize_schema()`: `I60RA` (client, counters, limits, readers, one redaction
  of its own prefix), `I60RC` (`max_ops` 2), `I60RE` (never enabled), `I60RV` (verify, general), `I60RT` (verify,
  temporal text marker; it now never verifies equal, by design of the bug it reproduces). Nothing was written to USER,
  `I60L*` or `R60*`; no erase, reset, kill or drop; no other container touched.
- Every adjudicated finding was reproduced natively by this repair before the owner, model or register changed:
  [predictions](PREDICTIONS.md) (frozen first, exposed), [grades](PREDICTIONS-graded.md) (20/20 held),
  [probe](probes/i60r_probe.py) with observations
  [fe1 fe2 fe5 c4](probes/observed-20261117T210756Z-fe1-fe2-fe5-c4.json) and
  [fe4 fe3](probes/observed-20261117T210820Z-fe4-fe3.json).

## Per-item dispositions

### 1. FE-1 (material): verify's two temporal-marker rules — **accepted**

- **Reproduced E2E** (`I60RT`, probe `fe1`): a committed relationship with `temporal="true"` (and with Python `True`,
  stored as `"true"`) gives `diverges`/`unrecorded_writes`; `verify(adopt=True)` writes adoption revisions 4 and 6;
  the next verify has the same entries. Also new: an unrecorded `create_edge(..., {"temporal": "true"})` never closes
  either (adoption 7). Neighbours: `"yes"` gives no entry; a JSON-`true` direct write is left out of both sides.
- **Register:** [bug-led-013](../../../../Verus_verification/bugs_issues.md#bug-led-013), **Medium**, E2E. Severity:
  visible misbehaviour of the ledger's integrity check (a permanent false divergence that hides real ones and grows the
  history on every adopting verify or re-enable), repairable by an administrator (change or remove the qualifier), no
  graph content lost. Reachability limits: only a qualifier named exactly `temporal` with value `"true"` or `True`; the
  name is neither reserved nor documented as reserved. Shares the unreserved-marker root with archived F-C0351/F-C0450
  (different trigger and reader), so it is a new entry, not a reopened one.
- **Owner** (`ledger.verify`, `ledger.verify.scope`): each side's rule stated; intent stated as settled (one rule on both
  sides; a caller's `temporal` "true" is an ordinary qualifier), from `_drop_temporal_marked`'s docstring and
  `LedgerGenesis.TemporalMarked`'s comment; as-built divergence stated with the finding. No open question (intent is
  not unsettled). CG-1 closed by the same text; CG-5 (re-enable compounds it) stated in `ledger.verify`.
- **Model** (`ledger_verify`): `QVal::{Bool,Text}`, `table_marked` (JSON true) and `replay_marked` (text "true")
  separately, `stores_as_text` (QualsJson), `redrop` after adoption. New: `theorem_text_marker_never_equal` (every
  verify diverges whatever the history; every adopting verify writes again), `theorem_adoption_never_closes_a_text_marker`,
  `theorem_marker_rules_differ`, `lemma_replay_view_dropped`.
  - **Narrowed:** `theorem_adoption_closes_the_difference` now requires `no_text_marker(b)` and is stated over
    `redrop(adopt(..))`. **Withdrawn:** its unconditional iteration-60 form.
  - **Narrowed/split:** `theorem_temporal_marked_rows_left_out` now states the two rules with neighbours (JSON-true row
    out of the tables, text-true row kept; text-true statement out of the replay, "yes" kept). **Withdrawn:** "a marked
    row is left out on both sides" for one marker.
  - **Controls** (all EXPECTED_FAIL): `one-marker-rule` (the iteration-60 single marker hides FE-1),
    `text-marker-premise-dropped`, `no-redrop`, plus the re-anchored `temporal-row-governed`, `replay-keeps-marked`.
- **Binding** (`ledger_verify`, `I60RV`/`I60RT`): T1 commits `"true"`, `True`, `"yes"` and writes unrecorded text-true
  and JSON-true edges; T2 adopts and re-verifies. AGREES; `replay-keeps-marked` is now natively detected (iteration 60
  thought it needed forged history). Binding row for `_drop_temporal_marked` changed from "drops temporal-marked
  statements" (contradicted) to the text-"true" rule, bound to `replay_marked` and the new theorems.
- **Map:** I3 → N (narrowed) + OC + C → bug-led-013; I5 → N (repaired; replay half now observed) + OC + C.
- Remaining limits: JSON `null` qualifier values and non-boolean JSON values are abstracted as text; one comparable
  relationship per tuple; quiescent inputs (q-led-006).

### 2. Observability and counters (FE-3, FE-4, FE-5, FE-7) — **accepted**

- **Reproduced E2E** (`I60RA`, probe `fe3`, `fe4`, `fe5`; binding B8, B8b, B8c, B18, B20):
  - caller A commits in its open transaction; B's commit: `LedgerLockTimeoutError` after **40.0 s**, `rej_lock_timeout`
    +0 while A is open and after A's rollback (third-connection reads);
  - a `Ledger.Count("rej_strict_block")` call in that window: 10.0 s, error status from the counter row's `%Save`, +0;
    +1 after A ends (new; the review's "other processes' bumps are lost" was an inference, now observed for `Count`);
  - neighbours (new): A's nested commit refused uncounted (5,000-character message) → B fails after **30.0 s** and is
    counted (+1, kept after A's rollback); a Native API lock on the head → 30.0 s, +1;
  - redaction-blocked commit: `RedactionInProgressError`, one `redaction_in_progress` event, every counter unchanged;
  - message 5,000 / key 300 / correlation 300 / actor 300 / object source 4,100+: `LedgerInconsistencyError`, one
    `inconsistent` event, no counter, nothing written; message 4,000 commits; a keyed retry with a 5,000-character
    message replays (new).
- **Registers:** [bug-led-014](../../../../Verus_verification/bugs_issues.md#bug-led-014) (R60-F2: uncounted lock
  timeout and lost counts while a caller's transaction holds the counter row, **Low**: observability drift and a 10 s
  longer wait, no content wrong; reachable whenever callers commit inside their own transactions while others write);
  [bug-led-015](../../../../Verus_verification/bugs_issues.md#bug-led-015) (R60-F3: field limits refused as
  `LedgerInconsistencyError` after apply, uncounted, **Low**: misleading class and missing count, nothing written;
  reachable through public `Changeset` fields). Both E2E.
- **Owner:** `ledger.observability` (every outcome logged and sent to hooks; counted kinds listed; uncounted:
  not-enabled, redaction-blocked, `inconsistent`; nothing counted while another transaction holds the counter row);
  `ledger.commit.size` ("only the operation count is limited" replaced by the transport statement plus the column
  limits, the error and the keyed-retry order); `ledger.commit.caller-transaction` (counter row, ~40 s, uncounted, lost
  counts; uncounted nested refusal holds only the head; rollback takes back the caller's own counts);
  `ledger.commit.serial` (30 s; about 40 s behind a counted caller transaction — FE-7).
- **Model** (`ledger_client`): `stats_holder`/`stats_base`, `stats_free`, `refuse(s, w, p)`, `txn_commit` takes the row
  only on a counted outcome, `txn_rollback` restores the caller's counts, `count_strict`, `Apply.blocked` (while
  `redacting`), `Cs.lens` + `fits`, `Code::RedactionInProgress`.
  - **Corrected:** `theorem_caller_transaction_holds_the_head` — **withdrawn** its conclusions `o2.cnt == lock + 1` and
    `o3.cnt.lock == s.cnt.lock + 1`; now `o2.cnt == o1.cnt` (not counted) and `o3.cnt == ok + 1` only.
  - **New:** `theorem_uncounted_nested_refusal_leaves_the_counter_row`, `theorem_uncounted_outcomes` (counter effect per
    outcome derived from `bump`/`refuse`/`write`, not a blanket rule), `theorem_field_limits_checked_after_the_key`.
  - **Controls** (EXPECTED_FAIL): `stats-row-not-held` (the iteration-60 model), `bump-ignores-held-row`,
    `uncounted-refusal-holds-row`, `redaction-block-counted`, `field-limits-unchecked`, `field-limits-before-key`.
  - `Code::Inconsistent` now has the deterministic field-limit producer as well as transport failure (FE-5's model
    point); CG-2 (which producer a caller faces) is stated in `ledger.commit.size` and map row B4; the transport
    half stays M (B4).
- **Binding:** B8 now records counter deltas; new B8b, B8c, B18 (redaction-blocked, read-only/neighbour use of
  redaction on this run's own prefix; one neighbour commit outside the target), B20. Rows for `Ledger.cls::Commit`
  ("bump after the level"), `CommitInTxn`, `WriteRevision`, `LedgerStats.cls::Bump` ("one counter per refusal kind"),
  `Ensure` corrected; `Ledger.cls::Count` bound to `count_strict`.
- **Map:** E2, D14, J1, B4 corrected (see the map's repair section).
- Remaining limits: the "stall and lose" mechanism is observed for `Bump` and `Count` and inferred for `RecordVerify`
  (not observed); a successful commit whose counter row another transaction holds while the head is free
  (`server`'s `!stats_free` → `inconsistent`) is source-derived only; wall times are recorded, not modelled.

### 3. Counting (BC-1) — **accepted**

- The 24 declaration-only classes (15 in `errors.py`: `LedgerError`, `LedgerNotEnabledError`, `LedgerDisabledError`,
  `StaleHeadError`, `UnknownRevisionError`, `IdempotencyConflictError`, `ChangesetOperationError`,
  `ChangesetTooLargeError`, `EmptyChangesetError`, `ReconstructionTooLargeError`, `LedgerLockTimeoutError`,
  `LedgerTransactionOpenError`, `LedgerInconsistencyError`, `NodeNotFoundError`, `IdempotencyRedactedError`; 9 value
  classes: `client.py` `CommitResult`, `RevisionInfo`, `Revision`, `LedgerCounters`, `_CommitWireResult`; `export.py`
  `ExportSummary`; `replay.py` `Diff`, `DiffEntry`, `VerificationReport`) were relabelled `cites` in
  `crosswalk/decision-links.tsv` (iteration 56 F5 / iteration 59 B1 convention), with role prefix "locator only
  (declaration-only class ...)" and grade "Inspected only". Their deciding members (`from_commit_error`, readers,
  `compare`) stay bound. Script: [crosswalk_repair.py](crosswalk_repair.py) (raw tab-split edit; unrelated rows
  byte-identical).
- **Recount** (pinned instrument, `recount.py f2a342934`, `$G5_RUN_STATE/counts/iteration-60-repair`;
  [member delta](member-delta.json)): **union 1007, active 772** (from 1028 / 793 at `030f1c53`).
  - The 24 relabels: active −24 and **union −24**. They stay resolvable locator rows in the crosswalk, but the pinned
    instrument's citation half (`inventory.prod`) does not list Python `class` declarations as members, so a class is
    in its union only through an active binding. Reported here as the declaration-only stratum: 1007 + 24 = 1031 if
    declaration locators were counted.
  - Newly bound by this repair (+3 active): `LedgerApply.cls::QualsJson` (FE-1's text conversion, `stores_as_text`),
    `GraphLedger._refuse_while_redacting` (FE-6 decision, `seq_read`), `GraphLedger.redaction_in_progress` (the marker
    reader, justified shared delegate). Newly reached (+3 union): `QualsJson`, `GraphLedger.redaction_in_progress`,
    `LedgerGenesis.cls::TemporalMarked` (locator only, intent source).
  - Against the baseline `01e8ccba` (956 / 706): union +51, active +66; newly reached 51, gained active 66, overlap 50,
    distinct 67, losses 0. Behavioural active gain of iteration 60 + repair: 63 (review's figure) + 3.
  - The master expected active ≈ 769; the 3 above account for 772.

### 4. Map dispositions (C4, D10) — **accepted**

- **C4:** reproduced E2E (probe `c4`): `except iris_vector_graph.NodeNotFoundError` (the class `docs/API_REFERENCE.md`
  documents) does not catch the ledger's missing-endpoint error; it escapes as
  `iris_vector_graph.ledger.errors.NodeNotFoundError` (`op_index` 1); the ledger class, `IVGError` and
  `ChangesetOperationError` catch it; the classes are unrelated. Registered
  [bug-led-016](../../../../Verus_verification/bugs_issues.md#bug-led-016) (R60-F4), **Low** (misleading documentation
  and message; the commit is refused either way; reachable by any caller following the reference), E2E. Map row C4:
  T → C. Owner `ledger.commit` now names the ledger's class and the hazard.
- **D10:** D → **D (partial) + M**: `ledger_apply` has no delete operation, so "a later op naming a node or statement
  deleted earlier in this changeset fails at that op" (`OpCreateRel`'s `pCtx("deletedNode")`/`deletedStmt`) is not
  derived. Not modelled here (the delete operations need their own records and context; not cheap and bounded within
  this repair). First missing step: add `delete_node`/`delete_rel` with that context to `ledger_apply`.

### 5. Minors — **accepted**

- **FE-2** (node existence from node rows only): reproduced (probe `fe2`: a post-commit property on an ID with 0 node
  rows gives a node-existence entry and `prop:k`). **Represented:** `canon_node` includes label and non-reserved
  property rows; `lemma_canonical_wf` discharges `wf(b)` for every canonical view; `theorem_orphan_property_reports_node`
  (control `node-from-node-rows-only`); binding V1 includes the orphan property. Owner `ledger.verify` states it. Map I2.
- **FE-6** (readers check the redaction first): reproduced (probe `fe4`, binding B19: all four readers raise
  `RedactionInProgressError` for an unknown ID while unfinished, `UnknownRevisionError` after; no export file).
  **Represented:** `seq_read` checks `redacting` first; `theorem_revision_readers_resolve_ids` (control
  `lookup-before-redaction-check`); `_refuse_while_redacting` bound. Owner `ledger.readers`. Map H4.
- **CG-3** (node operations on a missing ID raise the ledger `NodeNotFoundError` with a "create_relationship failed"
  message): reproduced for `set_property`, `add_label`, `remove_property` (probe `c4`); **folded into bug-led-016**
  (no separate count). Owner `ledger.commit` states that node operations fail with the same class and the wrong message.

### Other review items

| Item | Disposition | Note |
|---|---|---|
| FE-7 (30 s vs 40 s in `ledger.commit.serial`) | accepted | owner corrected (item 2) |
| CG-1 | accepted | owner states each side's rule (item 1) |
| CG-2 | partly | stated in owner and map B4; the transport half (a lost answer after commit) stays M, first step a fault-injected disconnect |
| CG-4 | accepted | = D10 (item 4) |
| CG-5 | accepted | `ledger.verify` states that every re-enable re-records a text-"true" relationship; the field-limit half (an adoption commit's lengths) not observed |
| BC-2 | accepted | contradicted/weakened roles corrected in the crosswalk (items 1, 2) |
| BC-3 (decision supplied as input: `_refuse_in_caller_transaction`'s `in_txn`, `Changeset.validate`'s `bad_ref`) | not in this assignment; unchanged | stays a partial binding; first step: model `caller_transaction_level` (autocommit off with no write answers 0) and the op_ref rule |
| 2d: bug-led-012, bug-doc-013, bug-doc-014, bug-test-004, NKG non-registration | agreed by the review; unchanged | — |
| Guard class cache candidate | dismissed by the review; unchanged | source-only cache-False path stays unassessed |
| 2e missing evidence | closed for B8 counters, redaction-blocked, field-limit, temporal-text and orphan cases | — |
| Section 6 cross-area round trip | not in scope | the reviewer's observation stands; H6's import half remains M in the map |

## Evidence, receipts and gates

| Item | Path |
|---|---|
| `ledger_verify` prove (15 verified) and 12 controls | `Verus_verification/results/ledger_verify/20261117T211222Z-prove`, `20261117T2112*-control-*` |
| `ledger_verify` binding (AGREES 5, 10/11 mutations) | `Verus_verification/results/ledger_verify/20261117T212044Z-binding` |
| `ledger_client` prove (30 verified) and 28 controls | `Verus_verification/results/ledger_client/20261117T212536Z-prove`, `20261117T2125*/2126*-control-*` (the earlier `211628Z` prove/control run and its one ERROR control receipt, a stale replacement text, are kept) |
| `ledger_client` binding (AGREES 52, 27/28 mutations) | `Verus_verification/results/ledger_client/20261117T212518Z-binding`; run 1 crashed in its redaction setup ([log](probes/ledger_client-binding-run1-crashed.log)); run 2 `20261117T212337Z-binding` DISAGREED on one vacuous flag (kept) |
| Gates (raw) | [gates/](gates/): `check_evidence` FRESH, `check_consolidated` PASS, findings checker "No problems found" (with `--previous` snapshot), `check_ontology` 0 issues / 17 warnings, correspondence REUSABLE_INPUTS against the refreshed `iteration-60/correspondence-inputs.json` (the builder's capture and its delta are kept: `correspondence-inputs-builder-030f1c53.json`, `correspondence-check-vs-builder.json`, which lists exactly the eight foundation files this repair changed) |

Not regenerated: `findings.md` (`make_findings_index.py` refuses by design; its post-audit table stops at iteration 24),
`results/viewer-index.jsonl` (not maintained since iteration 33). The model linker (dry run, links only) reports 9
missing links on non-ledger statements, all inherited.

## Remaining work (first missing step each)

1. D10: `ledger_apply` delete operations with the deleted-earlier context.
2. B4 / CG-2: a fault-injected disconnect between `Commit` and its answer, then the keyed retry's outcome.
3. BC-3: model `caller_transaction_level` and the op_ref rule instead of taking them as inputs.
4. Counter stall for `RecordVerify` (inferred) and a write whose counter row is held while the head is free
   (source-derived): one native case each.
5. Carried from iteration 60: q-led-006 (concurrent verify), q-led-004 (two-graph node merge), NKG dirty marker,
   correlation-index build state, snapshot/upgrade survival, and the recommended next area (native Cypher executor).
