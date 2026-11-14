# Round 1 review — R1-core (ledger, erasure, redaction)

Reviewer: R1-core. Product baseline 3eaa79cf (worktree HEAD 0e441f1c, uplift files under `.g5/` untracked).
Scratch and raw logs: `/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-g5-verus-20261113/agents/R1-core/`.

## Independent expectations

Written from the original sources only (ADR-0003/0004/0013, spec 256 spec/plan/tasks, spec 213 contracts,
CONTEXT.md History, USER_GUIDE section 9, `Graph.KG.{Ledger,LedgerApply,LedgerRedact,LedgerRevision,LedgerGenesis,
Eraser,GraphKey}`, `iris_vector_graph/ledger/*`, `_engine/nodes_edges.py`, the spec 256 E2E test) before opening
any uplift ontology page, model, coverage record or finding.

### E1 Commit admission (Ledger.Commit / CommitInTxn)

- E1.1 Check order is lock -> state (never-enabled / disabled) -> idempotency -> idemRedacted -> expected_head ->
  size/empty -> apply -> redaction-marker block -> write revision + idem binding. A refusal at any step writes
  nothing (TROLLBACK 1; head unchanged; counters only).
- E1.2 Idempotency: key bound with the same fingerprint `{actor, actor_type, ops}` -> original revision with
  `replayed=True`, no new revision, even when `expected_head` is stale (fingerprint excludes expected_head). Same key,
  different fingerprint -> `idempotency_conflict`. No key -> no replay at all (a second identical commit is a new
  revision). USER_GUIDE "Retries" says committing the same actor and ops again replays; that only holds with a key.
- E1.3 A key whose revision was redacted is refused (`idempotency_redacted`), never replayed and never re-bound;
  `idem` and `idemRedacted` are disjoint for a key.
- E1.4 Nested in a caller transaction (4.7.0): the revision and its writes go with the caller's commit/rollback; the
  head lock is held to the outermost end. Redact and enable refuse an open caller transaction.
- E1.5 Strict mode refuses non-ledger structural writes in Python only (guard with 5 s TTL cache, fails open);
  `erase_graph`, `delete_nodes_by_prefix`, `erase_all`, `drop_graph` are guarded, so erasure (and thus redaction)
  needs strict off. Raw SQL / BulkLoader are not guarded.
- E1.6 `post_commit_properties` are written after the revision by direct SQL with no record; a failure leaves the
  revision committed (`post_commit_applied=False`), and verify reports the props as unrecorded writes.

### E2 Verify / replay

- E2.1 verify = replay seq 1..head (tombstones and `revision`-kind records contribute nothing) compared graph-blind
  on nodes and per (s,p,o,graph) on relationships against the tables, temporal-marked rows excluded on both sides.
- E2.2 After erase alone verify diverges (replay rebuilds the erased relationships); after erase + redaction of the
  same target(s) it is `equal`.
- E2.3 While the marker exists verify returns `redaction_in_progress` and never adopts. The marker check happens
  once, outside the lock, before replay; a redaction starting after the check is not excluded (check-then-read), so
  adoption during a race relies on CommitInTxn's marker block.
- E2.4 `verify(adopt=True)` after erase but before redaction commits an adoption revision whose delete records carry
  the erased tenant's tuples (new tenant content in history); the later redaction must still reach them.

### E3 Erasure (ADR-0004, Eraser)

- E3.1 One transaction owned by the Eraser: all stores or nothing; failure throws after rollback; `0` = nothing
  matched. `rec` never touched.
- E3.2 Invariant "no live statement outlives its content": EraseGraph kills every `stmt` entry of the graph (live
  and closed) plus derived tuple keys (one pass over `stmt`, graph read from value position 4). EraseNodes /
  EraseNodeIds / EraseEdges kill the live statement per erased edge through the tuple index; closed statements
  survive.
- E3.3 Default graph has two SQL spellings (NULL and ''), COALESCE on both sides; the ledger key is `$Char(1)` and the
  index key is `0` (ADR-0003); names `"0"` and control characters are refused before any transaction.
- E3.4 Erasure does not take the ledger head lock; a concurrent ledger commit into the same graph is not serialized
  with it (open concurrency question; ADR-0004 is silent).
- E3.5 `delete_nodes_by_prefix(prefix)` matches the raw prefix (no separator), while redaction matches
  `prefix + separator`; `acme` erases `acme-health|...` too.

### E4 Redaction (ADR-0013, spec 256, LedgerRedact)

- E4.1 Target = (graph name, optional match string `prefix+separator`, not doubled). A record matches when its graph
  equals the target graph and, with a prefix, a node record's id or a relationship's s or o starts with the match.
  Node records always have graph `""`, so a tenant takes two targets (graph, and default graph + prefix).
- E4.2 Mixed revision: only the target's records become tombstones `$LB("redacted", sha256(CanonicalRecord), flags,
  op, kind)` in place; other records and all ordinals unchanged. Metadata (message, source, correlation_id,
  idempotency_key) cleared when ANY record is redacted (Decision 2 overrides FR-004's "every"); seq, id, parent,
  kind, committed time, actor, op_count stay.
- E4.3 Qualifier records (`set_qual`/`remove_qual` of a prefix target) carry only a statement id: endpoints come from
  (i) statements whose create/delete was tombstoned in this run (`redacting.stmt`, persisted and rolled back with the
  batch), (ii) a per-call PrePass over untombstoned create_rel/delete_rel records of the graph (process-private,
  outside the lock), (iii) the live `stmt` map. A record whose endpoints are unknown is counted
  (`unattributed_records`) and left in clear; the run still reports `complete`. Reachable when a statement was
  assigned by a ledger op to an edge written outside the ledger (`assigned_stmt`: set_qual/upsert_rel via tuple, no
  create_rel record) and then erased (EraseNodes kills the live stmt). Reifier `delete_node` cascade records carry
  the reifier id, not the tenant prefix.
- E4.4 Refusals before any write: transaction_open, not_enabled, disabled, invalid_target (bad name, empty
  separator), redaction_in_progress (a different target's marker), target_live (nodes/labels/props graph-blind for a
  default-graph prefix target; edges in the target graph). SQL failure -> `inconsistent`.
- E4.5 Batches: each batch is TSTART + head lock, at most `batch` tombstones and `batch*20` scanned records; the
  marker is set at the first tombstone (not before), so before the first match commits into the target are not
  blocked. Each batch re-checks only that the ledger is enabled, not liveness. A failed batch rolls back and the
  cursor resets to the batch start. `max_batches` stops early with the marker in place (complete=false).
- E4.6 Final (own transaction under lock): re-check liveness (target_live -> rollback, marker remains), drop the
  target's `stmt`/`tuple` entries (tuple only if it points at the doomed stmt), write the `redaction` revision (one
  `redact` record per redacted seq, counts, sha256(graph NUL match), no target content), kill the marker.
  No marker and no statements -> no revision (idempotent rerun reports zeros).
- E4.7 Retry/resume: rerunning the same target resumes (cursor restarts at seq 1, skipping tombstones); another
  target is refused until the first finishes; counts accumulate across runs. The scan reaches records appended by
  commits during the run (ascending `$Order` to the live end).
- E4.8 Marker blocks commits with a record that matches the marker target (BlocksCommit, after apply, inside
  the commit transaction; uses the committer's own process-private PrePass global, normally empty). A key of a
  redacted revision is refused forever, including for the other tenant of a spanning revision.
- E4.9 Readers (`get_revision`, `diff`, `reconstruct`, `export_reconstruction`) refuse while the marker exists
  (check-then-read, outside the lock); `history` does not; SQL `ledger_records` is not guarded.
- E4.10 Trigger exemption: UPDATE passes only with `%IVGLedgerRedaction = seq`, `redactedRev(seq)` present, no other
  column changed, all four new values empty. Object save/delete and SQL delete stay closed.

### Outcome-changing cases to check in the uplift

C1 mixed-tenant revision (shape kept, metadata cleared, other tenant's key now refused); C2 qualifier records with
unknown endpoints (left in clear, run still `complete`); C3 interrupted batch (rollback restores cursor and counts;
partial tombstones survive committed batches; marker semantics); C4 resume after `max_batches` with knowledge lost
from PrePass but kept in `redacting.stmt`; C5 Final refusal after a commit made the target live before the marker
existed; C6 idempotent rerun after completion (zeros, no revision); C7 retry of a redacted key (refused, not
replayed); C8 two targets for one tenant and their order; C9 verify race with marker check; C10 erase/commit
concurrency; C11 default graph spelling and "0" refusal; C12 separator over-match in erase vs redact.

## Coverage findings

Compared with the expectations above, the ontology pages (`ledger`, `erasure`, `redaction`) are broad and mostly
faithful: C1, C2, C6, C7, C8, C9, C10, C11 and C12 all appear as statements, observed divergences or questions. What is
missing or only partly covered:

- **CV-1 Resume for a prefix target is covered nowhere (C4).** The product's knowledge of a qualifier record's
  endpoints is rebuilt for each call: `PrePass` reads only records that are not yet tombstoned, into a process-private
  global. On resume, `("redacting","stmt")` has to stand in for the `create_rel` records an earlier call
  tombstoned. Neither the model (`K()` is one constant knowledge for every call), nor the twin adapter (field
  `redacting` is hard-coded `"0"`), nor any probe exercises this. `redaction_interrupt_resume` uses a whole-graph
  target (`gA`, no prefix), where `Matches` never consults knowledge. Owner: redaction.batches.resume, coverage.md
  row "batches compose".
- **CV-2 Completion is guaranteed only for runs that wrote a tombstone.** `theorem_completion` requires
  `s.runs[p].started`. A run that finds no target record never sets the marker. A target commit that lands after its
  scan ends is therefore admitted, and the record survives a run that reports `complete`. My scratch witness
  `rv_witness_unstarted_run_completes_with_target_record` verifies this under `as_built()`. The product does the same
  (`BatchInLock` sets the marker lazily; `FinalInLock` returns "" when there is no marker and no statement). The
  ontology mentions the lazy marker, but coverage.md states the guarantee without this condition. The product impact
  is low: the trace needs a create+delete in the window, because live content makes Final refuse.
- **CV-3 verify(adopt=True) racing a redaction (A-history F5) is not in the register.** `verify()` checks the marker
  once, outside the lock, replays, and commits the adoption with no `expected_head`. If the redaction's Final commits
  in between, the adoption (`delete_node` / `delete_rel` items whose ids and tuples are the erased tenant's) is
  admitted after the marker is gone. Tenant ids then re-enter `^IVG.Ledger("rec")` after a `complete` receipt. The
  ontology has only the generic [Q ledger.verify.consistency]. The same path runs implicitly from `enable()` after a
  re-enable.
- **CV-4 Reifier cascade records.** `DeleteRelInternal` writes `delete_node` (graph `""`, the reifier's own id,
  prior = label/property snapshot) for each reifier of a deleted tenant edge. Neither `redact(tenantGraph)` nor
  `redact(None, prefix=tenant)` reaches it unless the reifier id carries the tenant prefix. The general sentence "an
  ID without a tenant prefix cannot be reached" covers it in principle. This concrete source of tenant content inside
  a tenant's own revision is not named, and nothing tests it.
- **CV-5 Final's statement-index step is unmodeled.** `DropStatements` removes the target's `stmt`/`tuple` entries,
  and when it drops any it writes a redaction revision even with no marker. Neither appears in the model. The `stmt`
  map is part of `Matches`' knowledge, and it changes at Final (CV-1).
- **CV-6 Ledger findings that the ontology records but the register drops** (see Findings-register check): commit
  `kind` chosen by the caller (forgeable `adoption`/`redaction`/`genesis` revisions); a replay returns
  `stmt_ids = {}` and re-applies `post_commit_properties`; re-enable during a redaction skips the adoption silently;
  the OpsReview brief recipe (`redact(graph, prefix=...)` alone) misses every node record.

## Fidelity findings

Challenge 1 asked whether the fine-grained `Step` over-approximates a batch transaction, and whether the
scan-done/Final boundary is right. My verdict: sound for safety, with two caveats.

- A real batch holds the head lock, so no `Commit`/`Final`/`Start` can interleave inside it. The model allows
  interleaving between any two Steps, which is a superset.
- A failed batch rolls back every tombstone, metadata clear, key move and first marker it wrote. The resulting state
  equals the model state reached by `Abandon` at the batch's start, because nothing could interleave in the real
  batch. So `Abandon` without undo still covers the rollback.
- The model sets `done` at the last record that exists at that Step. The product only learns the end when
  `$Order` returns `""`, which can be one batch later; a batch that stops on `pBatch`/`pCap` exactly at the end
  scans late commits in the next batch. The model's unscanned gap before Final is therefore at least as large as the
  product's, which is pessimistic and fine.
- Both quit Final without rescanning, and both refuse Final on `target_live` while keeping the marker.
- Caveat 1: the boundary guarantee only holds with a marker (CV-2).
- Caveat 2: Final's `DropStatements` and its audit-without-marker branch are not modeled (CV-5).

The remaining fidelity findings:

- **FI-1 `K()` hides per-call knowledge (challenge 2), category: model error.** `lemma_batches_compose` and
  `lemma_rescan_is_harmless` are proved for one `k` across all calls. The product rebuilds knowledge per call:
  - `PrePass` runs per call, outside the lock, over records not yet tombstoned.
  - `("redacting","stmt")` grows with tombstones, rolls back with a batch, and is killed with the whole
    `("redacting")` subtree by *any* run's `FinalInLock`.
  - The live `stmt` map is changed by erasure and by Final.
  - `BlocksCommit` runs in the committer's process, where `^||IVG.RedactStmt` is empty.

  For a single unraced call I checked that the answers agree: every statement added to `redacting` has a parseable
  `create_rel`/`delete_rel` in `PrePass`. A committer's qualifier records name live statements, so the `stmt` map
  answers for `BlocksCommit`. The abstraction fails when knowledge shrinks between calls. Under bug-001, run B's
  Final kills run A's `("redacting","stmt")`. A resumed A call then has neither `PrePass` (its `create_rel` is a
  tombstone) nor `redacting` (killed) nor the `stmt` map (erased) for its statements. Their remaining qualifier
  records answer -1 and stay in clear under `complete=true`. Scratch witness `rv_witness_knowledge_lost_between_calls`
  verifies this: the same two records under one knowledge are both redacted; with call 1 stopped after the
  `create_rel` and call 2 resumed with the lost knowledge, the `set_qual` survives.
- **FI-2 The twin adapter matches `Matches` only for a fresh call (challenge 3), category: correspondence error,
  limited.** `redaction_common.knowledge` reproduces `PrePass` faithfully:
  - It applies the same filters (kind `rel`, graph after NUL strip, non-empty id, `create_rel` -> new, `delete_rel`
    -> prior) with last-wins.
  - It reproduces the stmt-map fallback, with `PrePass` taking precedence.
  - It takes its snapshot after the erase.
  - Empty ids give Unknown.

  It differs in three ways:
  - It never sets `redacting` (`"0"`).
  - It snapshots once before the run.
  - It classifies node-ness by op code (Matches uses entity kind) and maps unknown ops to `No`.

  For the binding world (two fresh calls, every record written by `LedgerApply`) this is equivalent: twin Unknown =
  0, L1-vs-twin = 0. The binding does not extend to resumed or raced calls (FI-1, CV-1).
- **FI-3 Model `Erase` is graph-blind for default-graph targets, category: correspondence error.** In
  `content(NodeRow{g,id}, t)`, `t.g.len()==0` matches node rows of every graph, so the model's `Erase{default
  target}` removes named-graph rows. `EraseGraph(None)` and `EraseNodes("", p)` remove default-graph rows only.
  As a result, the model's erase-then-redact path can never reach bug-003's state, and W3 builds that state directly.
  `Erase` should remove `g == ""` rows only, and the witness should then show erase -> `Start` admitted -> live
  `gN` nodes tombstoned.
- **FI-4 Weak detection of the final liveness check, category: model error (minor).** The only property that fails
  under `no-final-liveness` is the conjunct `!any_checked(s.live, t)` of `theorem_completion`, which restates the
  removed guard. The lifecycle has no replay/verify consequence of completing while live.
- **FI-5 Commit-admission theorems are transcriptions.** `theorem_retry_replays_first`,
  `theorem_redacted_key_refused_before_apply` and `theorem_commit_writes_only_when_admitted` re-read one `if` chain.
  They check the transcribed order, not the product, whose order rests on reading `CommitInTxn`. Their "Proved"
  status should say "transcription".
- **Can the model pass while violating the ontology?**
  - `theorem_completion` holds while Unknown records survive (P_ends, W4).
  - It holds while another target's revisions are listed in the audit (concurrent variant; serial premise).
  - Receipts (FR-008 counts) are not modeled, so the receipt mis-counts of bug-001 cannot be expressed.

## Adversarial checks

- All runs use `$VERUS_BIN redaction.rs --crate-type=lib --num-threads 4 --triggers-mode silent`, plus
  `--verify-root --verify-function <fn>` for attribution, on copies under
  `$RUN_DIR/agents/R1-core/` (`RUN_DIR=/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-g5-verus-20261113`).
  Verus 0.2026.10.04.426d8b0.
- Baseline: the current `redaction.rs` (sha256 b9f9f69c…) gives **35 verified, 0 errors**, matching the 22:58 prove
  receipt. Log: `base/prove.log`.
- `twin.rs` gives 45 verified, 0 errors. Log: `twin/verify.log`.

| Kind | Change (scratch copy) | Expected | Verdict | Raw log |
|---|---|---|---|---|
| (a) erroneously permitted step | `Start` no longer refuses while another target's marker exists (a stale marker from a paused run, serial variant) | invariant breaks | **caught**: `lemma_step_preserves_inv` postcondition fails (34v/1e) | `adv/A1-start-ignores-other-marker/all.log` |
| (a) false premise | drop `s.runs[p].started` from `theorem_completion` | theorem fails | **caught**: postcondition fails even with the auxiliary asserts removed (0v/1e) | `adv/A2-completion-without-started{,-noaux}/all.log` |
| (a) positive side | `rv_witness_unstarted_run_completes_with_target_record` | unstarted run completes, target record survives | **verified**: the gap is real in the model | `adv_valid/verus.log` |
| (b) faulty implementation | `BlocksCommit` checks only a changeset's first record (mixed changeset) | detected | **caught** in `lemma_commit_preserves` (inv postcondition) and the bridge `lemma_commit_admits_matches_outcome` (33v/2e). `--verify-function lemma_step_preserves_inv` alone *passes* (1v/0e), because it trusts its callee | `adv/B1-blockscommit-first-record-only/` |
| (b) faulty implementation | `Final` allowed before the scan is done (e.g. after a `max_batches` stop) | detected | **caught**: `theorem_completion` fails (34v/1e; without the auxiliary asserts, its record-cleanliness conjunct fails) | `adv/B2-final-before-scan-done{,-noaux}/all.log` |
| (c) valid outcome survives | `rv_witness_mixed_pause_other_commit_resume_completes`: a spanning revision (a and b, with a key), pause, tenant b's commit admitted under a's marker, retry of the key refused, resume to completion | reachable | **verified**: b's records byte-identical, a's record a tombstone, marker gone, one audit record | `adv_valid/verus.log` (38v/0e) |
| K() probe | `rv_witness_knowledge_lost_between_calls` | qualifier survives when knowledge shrinks | **verified** | `adv_valid/verus.log` |

- Control re-run: all 11 `model.json` controls on the **current** model are `EXPECTED_FAIL`, each attributed to
  its named function. Summary: `controls/summary.txt`.
- Suggestion: add A1 and B1 to `model.json` controls, with B1 naming `lemma_commit_preserves`.

## Evidence findings

- **EV-1 Stale control receipts (missing or stale evidence).** 9 of the 11 control receipts (22:44–22:45) record
  inputs `redaction.rs` c5300fa7 (31 obligations) and `model.json` 0e7176c9/bc5f5a6a. The current files are
  b9f9f69c / 79011cfc, with 35 obligations. Only the 22:58 prove and the two new controls are fresh, and no reuse
  justification is recorded. My re-run confirms all 11 verdicts on the current model. The uplift must re-run them
  and keep the receipts.
- **EV-2 The erasure atomicity evidence is zero-test.**
  - `test_eraser_failures`: 30 skipped in the default run (`IVG_NS_IVG236` unset). The scratch rerun gave
    1 passed / 30 errors with "Unable to allocate a license".
  - `test_edgescan_ledger_erase`: 6 skipped, then 1 failed / 6 errors. This includes
    `test_erasing_a_graph_removes_its_ledger_statements_and_leaves_other_graphs`.

  coverage.md (trust inventory and the erasure row) cites `test_eraser_failures` as discharge, so "erasure either
  completes or leaves the graph untouched" has no runtime evidence in this run. The commit side has some
  (`test_ledger_us02_rollback`, 8 passed).
- **EV-3 The native evidence trail is incomplete.**
  - `receipts/native/` has no `redaction_mixed_retry` copy. The applicable raw observation is `…T234221Z`
    (`OBSERVED_AS_EXPECTED`); `…T232514Z` (`OBSERVED_DEFECT`) came from an earlier probe text whose own-revision
    changeset had 1 op.
  - `redaction_lifecycle_checks.py` was edited at 23:25:39, after its b–d observations at 23:25:14
    (readers_midrun, temporal_blocked, ledger_post_commit_verify). The text that produced them is not kept, and
    observations carry no probe or harness hash.
  - The drafts still hold the placeholders `RESULT_MIXED_RETRY`, `RESULT_READERS`, `RESULT_ERASE_TXN` and
    `RECEIPT_PROVE`.
- **EV-4 Misattributed observation.** The `redaction_interrupt_resume` docstring says step 4 runs batches and
  "final step refuses", and q-006 cites that step as evidence of the Final refusal path. Step 4 adds a live `gA`
  edge before calling `redact`, so `LiveRows` at entry refuses it, before any batch. `FinalInLock`'s under-lock
  re-check has no native observation; only the model control covers it.
- **EV-5 Stale runbook.** The runbook expects 31 verified (now 35) and a twin with 41 (now 45). The coverage.md
  "Native suites" section is unfilled.
- **EV-6 Receipt location.** `run_verus.py` writes to `results/<model>/…`, which does not exist. The cited receipts
  live under `receipts/`, so the runner's output path and the evidence trail disagree.
- **EV-7 Status words in coverage.md.**
  - "readers refuse while unfinished — **Proved** for the listed readers' guard" is wrong: readers are not modeled,
    and `marker_names_started_run` holds only under serialisation. The correct status is "Observed (paused,
    sequential)". Check-then-read and bug-001 are open.
  - "batches compose / resumption — Observed" overstates: the observation covers a whole-graph target only, and the
    proof holds under constant `K` (CV-1, FI-1).
  - "a completed run leaves no target record — Proved under serialisation" omits "started runs" and "records
    attributable under the run's knowledge".
  - The erasure row's "Observed · conditional on the IRIS premise" rests on EV-2, and bug-002 contradicts "a
    transaction it owns" on plain connections.

Every other Proved/Observed tag I checked has a matching receipt or raw observation:
- match string: upstream e2e, 25 passed;
- frame / mixed revision: binding probe rev 4, records [4,1] and [4,3] only;
- competing runs: `raced_entry_checks: true`;
- the two liveness gaps;
- unattributed qualifier;
- redacted-key retry: upstream test plus `…T234221Z`;
- replay = store: binding probe `diverges`->`equal`, zero record or metadata problems, both observation-mutation
  controls detected.

## Findings-register check

Drafts `core-{bugs,simplifications,questions}.md` and the later `register/previous/` (which adds q-009 and q-010).

Challenge 4: are any of the four core bugs a misreading, and can production actually execute each trace?

- **bug-001 — not a misreading.** The native trace (`raced_entry_checks: true`; B's audit names 2 and 3; A's
  receipt says `metadata_cleared: 0`) uses only public calls. In production the race window is wide: from the entry
  check through `LiveRows` and a full `PrePass` scan of `rec` to the first match. Add the FI-1 consequence: B's
  Final kills A's `("redacting","stmt")`, so a resumed A leaves qualifier records in clear under `complete`. With
  that consequence High is justified.
- **bug-002 — not a misreading.** It needs an erase inside an open caller transaction on a plain connection,
  rolled back after another connection redacts. That is reachable by design since aad50087. Drop "Found by … the
  model's liveness premise": the model has no notion of uncommitted state. Keep High because the loss of history is
  irreversible, but note the precondition.
- **bug-003 — not a misreading**, because the plan explicitly makes default-graph liveness graph-blind.
  - The consequence "verify can no longer be made equal for them" is unsupported. The probe shows verify was
    already `diverges` after the erase alone, and `verify(adopt=True)` records the bare `gN` nodes and restores
    `equal`. The real loss is the history of nodes that are still live.
  - The trigger is a whole-default-graph target, not the tenant recipe.
  - Suggest **Medium**, and link FI-3.
- **bug-004 — not a misreading.** It needs an edge written outside the ledger and never adopted (a non-strict
  deployment). Medium is right. Note that the Python receipt never raises on `unattributed_records > 0`.

Missing entries:

| Missing entry | Source | Category | Suggested severity |
|---|---|---|---|
| verify(adopt=True) concurrent with a redaction appends tenant ids after the redaction completes (CV-3) | A-history F5; replay.py verify; ADR-0013 "Nothing … comes from the target" | product defect (suspected, no native) | Medium |
| The OpsReview brief recommends `redact(graph, prefix=...)` alone, which misses every node record | A-history F3; redaction.tenant metadata | product defect (doc), confirmed | Medium |
| USER_GUIDE "Retries" replay without a key | A-history F7; ledger.idempotency.key-required | product defect (doc), confirmed | Low |
| Replay returns `stmt_ids={}` and re-applies `post_commit_properties`, so a stale retry overwrites newer values | A-history F13; ledger-api.md "original outcome"; client.py `_commit` | product defect / question | Medium |
| Callers can choose the commit `kind` (forge `adoption` records without changing tables, or label a changeset `redaction`/`genesis`) | ledger.commit.kind [Q] | unresolved decision | Medium |
| Re-enable during a redaction skips the adoption silently | A-history F14; ledger.lifecycle | product defect | Low |
| verify reads ledger and tables without a lock; adoption has no expected_head | ledger.verify.consistency [Q] | unresolved decision | Low–Medium |

Other register problems:

- q-006's evidence is misattributed (EV-4).
- q-001 still has its placeholder; it should cite `…T234221Z`.
- simp-002 (endpoints in every relationship record) would also remove FI-1's dependence on per-call knowledge.
  It deserves that note, and the proposal should check that old records keep their canonical form and digest.

## Summary table of material findings

| ID | Severity | Category | Owning artifact | Finding | Proposed correction |
|---|---|---|---|---|---|
| R1-1 | High | model error / correspondence error | redaction.rs (`K()`), coverage.md "batches compose" | Knowledge is constant across calls in the model. In the product it is rebuilt per call, and any run's Final kills `("redacting","stmt")`, so a resumed prefix run can leave qualifier records in clear (scratch witness). | Model knowledge as state (`redacting` set, `PrePass` from the untombstoned records, `stmt` map) and re-prove resume. Add the consequence to bug-001. Downgrade "batches compose" to conditional. |
| R1-2 | Medium | missing or stale evidence | native probes, twin adapter | Resume of a prefix target is never observed. The adapter hard-codes `redacting=0`, and the resume probe uses a whole-graph target. | Add a prefix-target pause/resume probe with qualifier records, and feed the observed `("redacting","stmt")` to the twin. |
| R1-3 | Medium | missing or stale evidence | receipts/ledger_redaction, runbook | 9/11 control receipts are on an older `redaction.rs`/`model.json`; the runbook counts are stale (31/41 vs 35/45). | Re-run controls (reviewer re-run: all EXPECTED_FAIL), store fresh receipts, and fix the runbook. |
| R1-4 | Medium | missing or stale evidence | coverage.md erasure row, trust inventory | `test_eraser_failures` and `test_edgescan_ledger_erase` produced no passing test (skipped, then license errors), yet they are cited as discharge. | Re-run them in a licensed scratch namespace, or mark erasure atomicity "Assumed/Open". |
| R1-5 | Medium | correspondence error | coverage.md status words | The readers row is tagged "Proved" with no reader model. The completion row omits "started" and "attributable". The erasure row ignores bug-002. | Re-tag per EV-7. |
| R1-6 | Medium | missing intent (register) | findings register | Several items are missing: the verify-adopt race with redaction, the OpsReview recipe doc bug, replay `stmt_ids` / `post_commit` re-apply, caller-chosen commit kind, silent adoption skip on re-enable, the USER_GUIDE retries doc bug. | Add the register entries in the table above. |
| R1-7 | Medium | incorrect claim / severity | bug-003 | "verify can no longer be made equal" is unsupported (adoption restores it; verify already diverged after the erase). | Correct the consequence; suggest Medium; link R1-8. |
| R1-8 | Low | correspondence error | redaction.rs `content`/`Erase` | The model's erase of a default-graph target removes named-graph node rows; the product's does not. | Restrict `Erase` to `g == ""` and derive W3 through `Erase`. |
| R1-9 | Low | model error | redaction.rs `theorem_completion` | Completion holds only for started runs; an unstarted run can complete with a target record committed in the gap (scratch witness). `no-final-liveness` is caught only by a conjunct that restates the guard. | State the condition in coverage.md, or claim the marker at start (simp-001). Add A1 and B1 controls (B1 naming `lemma_commit_preserves`). |
| R1-10 | Low | missing or stale evidence | interrupt_resume probe, q-006, receipts/native | Step 4 is refused at entry, not by Final. The mixed_retry receipt copy is missing. The lifecycle probe was edited after its observations. Placeholders remain in the drafts. | Fix the docstring and q-006. Add a concurrent-writer probe for Final's re-check. Copy `…T234221Z`. Record probe hashes in observations. |
| R1-11 | Low | missing intent | redaction ontology | Reifier `delete_node` cascade records inside a tenant's revision are unreachable by both targets (CV-4), and Final's `DropStatements` and audit-without-marker are unmodeled (CV-5). | Name the cascade case under redaction.target.nodes and add a test. Model or explicitly exclude `DropStatements`. |
| R1-12 | Low | incorrect claim | bug-002 | "Found by … the model's liveness premise" is unsupported; the model has no uncommitted state. | Change it to "source review + native probe". |
