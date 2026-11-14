# Round 2 review — R2-core (ledger, erasure, redaction, cross-domain)

Reviewer: R2-core (fresh, isolated). Round 2 of at most 3. Date 2026-11-14. Product baseline `3eaa79cf`; worktree HEAD `0e441f1c`.
Scratch and raw logs: `$RUN_DIR/agents/R2-core/` (`$RUN_DIR` = `~/runs/iris-vector-graph-g5-verus-20261113`), written `$SCR` below.
Product untouched. Nothing under `.g5/` was edited except this file (the Verus runbook steps were run from a scratch mirror of `.g5/`, see "Foundation handoff reproduction").
IRIS: under the round-2 exception, only `redaction_binding.py` (03:30:20Z) and `redaction_concurrent_targets.py` (03:30:47Z) were run, one at a time. No docker command was run.

Order of work: governing sources and code first (ADR-0004, ADR-0013, spec 256 spec/plan, spec 213 `contracts/ledger-api.md`, CONTEXT.md, `LedgerRedact.cls`, `Ledger.cls`, `LedgerApply.cls`, `LedgerRevision.cls`, `Eraser.cls`, `GraphStores.cls`, `TemporalIndex.cls`, `replay.py`, `client.py`, `guard.py`, `_engine/nodes_edges.py`). I only read `model.json` before writing the expectations, because the runbook reproduction needs it. After that I read the uplift pages, model, coverage map, register and round-1 material.

## Independent expectations

Derived from the sources above before reading the uplift's ontology, models or findings.

**Target and records**

- E1. A target is a graph, optionally narrowed by `prefix+separator`. Records are matched by the graph in record position 7. Node records always carry graph `""`. Relationship and temporal records are matched by the endpoints in their tuple JSON. Qualifier records are matched through the statement's endpoints (PrePass, `("redacting","stmt")`, then the live `("stmt")` map). Anything else answers -1. It is skipped, counted as `unattributed_records`, and the run still says `complete` (FR-001 says "every record").
- E2. A tombstone is `$LB("redacted", sha256(CanonicalRecord), flags, op, kind)` at the same position. Every other record stays byte-identical (SC-004 for records). The digest is unsalted.
- E3. Metadata is cleared on **any** tombstone in a revision. Decision 2 overrides FR-004's "every". The idempotency key moves to `idemRedacted`. The admission order is: lock → state → bound key replay/conflict → redacted key → expected head → size → apply → BlocksCommit → write. The trigger exemption is narrow, and it is keyed on a process variable plus `redactedRev`.
- E4. The audit revision is content-free (counts, an unsalted `sha256(graph NUL match)`, and one `redact` record per seq). It is written through `WriteRevision`, so it bumps `CommitsOk`.

**Lifecycle and concurrency**

- E5. Refusals before any write: `transaction_open`, `not_enabled`, `disabled`, `invalid_target`, another target's marker, and `target_live`. Liveness reads only `nodes`, `rdf_labels`, `rdf_props` and `rdf_edges`. The default graph is graph-blind for node tables only with a prefix. The temporal index, docs, vectors and reifications are not read.
- E6. Batches run one transaction each under the head lock. The marker is set at the first **hit**, not at start, so a run with no hits never sets it. The cursor restarts from seq 1 on every call. Final re-checks liveness under the lock, then runs `DropStatements`, then writes the audit, then kills the whole `^IVG.Ledger("redacting")` subtree (counters, `revs`, `stmt`). It does this whoever owns the marker. Final writes nothing when there is no marker and no statement was dropped. With no marker but dropped statements, it writes an audit.
- E7. Concurrency:
  - Entry checks run outside the lock, so two different targets can both start.
  - Same-target concurrency is benign.
  - BlocksCommit runs in the committing process, after apply. It sees no PrePass knowledge.
  - Readers check the marker once, outside any lock. `history`, `stats` and SQL `ledger_records` never check it.
  - `verify(adopt=True)` is not isolated from a redaction or a commit.
- E8. `verify()` compares only nodes (graph-blind), labels, props and edges with qualifiers. It skips temporal-marked rows and never reads the temporal index, docs, BM25/vector indexes or reifications. So "equal after redaction" says nothing about those stores.

**Erasure and stores**

- E9. Erasure (ADR-0004) runs in one transaction over the inventory. Routed tables are dropped after commit. The quarantine is kept. `EraseNodes(prefix)` collects its ids **from `Graph_KG.nodes` rows** and erases temporal edges only for those ids. A temporal-only predicate (ADR-0015) writes no node row. `^BM25Idx`, `^VecIdx`, `^IVF`, `^PLAID` and `^EmbedQueue` are not in the inventory and no erase touches them.

**Strict mode and unrecorded writes**

- E10. Strict mode is a client-side guard with a 5 s cache that fails open. It refuses `erase_graph`, `erase_all` and `delete_nodes_by_prefix`. Under strict mode the Python API's only deletion path is therefore a ledger changeset. `LedgerApply.DeleteNodeRows` removes only embeddings, labels, props and the node row. It leaves `docs` (no FK), the temporal index, FHIR side tables and named indexes.
- E11. Unrecorded writes that break verify:
  - erasure (by design, until redaction);
  - every non-strict engine, Cypher or bulk write;
  - BulkLoader and raw SQL (strict-exempt);
  - `post_commit_properties`, which `ledger.commit` itself writes by direct SQL after the revision. Strict mode does not refuse them, BlocksCommit does not check them, and a replay applies them again.
- E12. Outside the reach of redaction: exports, journals, backups, the marker's plain text in journals, snapshot archives, and relationships in other graphs that name the tenant. Records of reifier cascades and unprefixed node IDs are also left.

## Foundation handoff reproduction (runbook steps 1–6)

To stay inside my write permission, steps 1–3 and 5 ran exactly as written, but from `$SCR/mirror` (a byte-identical copy of `.g5/` and `experiment/g5-verus/environment.sh`, checked with `diff -r`). I set `RUN_DIR=$SCR/rundir` and `VERUS_RUN_THREADS=4` after sourcing the environment. Steps 4 and 6 ran in the worktree as written.

| Step | Command (as in runbook) | Expected | Observed | Raw evidence | Runbook defect |
|---|---|---|---|---|---|
| 1 Proof | `run_verus.py prove …/ledger_redaction` | `PASS (37 verified, 0 errors)` | `PASS (37 verified, 0 errors)`, 3.7 s | `$SCR/step1-prove.out`; `$SCR/rundir/verus/ledger_redaction/20261114T032746Z-prove.log`; mirror receipt `results/ledger_redaction/20261114T032750Z-prove/receipt.json` | It writes a receipt into the tracked `.g5/…/results/`. It does not set `VERUS_RUN_THREADS`, so the runner uses 8 threads. |
| 2 Controls | `run_verus.py controls …/ledger_redaction` | 13 lines, all `EXPECTED_FAIL`, ~2 min | 13/13 `EXPECTED_FAIL` (each attributed per function), 1 m 34 s | `$SCR/step2-controls.out`; per-function logs in `$SCR/rundir/verus/ledger_redaction/` | It writes 13 receipts into `.g5/`. It also `rmtree`s and recreates `$RUN_DIR/verus/ledger_redaction/controls/<name>`, which belong to the orchestrator. |
| 3 Twin | `(cd …/ledger_redaction && $VERUS_BIN twin.rs --num-threads 4 --compile -o $RUN_DIR/verus/twin/twin)` | `47 verified, 0 errors`, binary written | 47 verified, 0 errors. Binary sha256 `823bfbfb…a452` is **bit-identical** to the probes' twin and to the twin receipt's `binary_sha256` | `$SCR/step3-twin.out`, `$SCR/rundir/verus/twin/twin` | It overwrites the twin the probes use. It omits `--triggers-mode silent` (the receipt's command has it), so trigger notes are printed. It writes no receipt, although the step names one. |
| 4 Binding probe | `python3 …/probes/redaction_binding.py` | `OBSERVED_AS_EXPECTED` | `OBSERVED_AS_EXPECTED`: 31 records, 20 tombstoned as the twin predicted, byte-identical otherwise, verify diverges→equal, metadata/idem moved, both observation-mutation controls detected. Same verdict and fields as the receipt copy, with the same probe-input hashes (only revision ids and timestamps differ). | `$RUN_DIR/native/redaction_binding-20261114T033020Z.json`, `$SCR/step4-binding.out` | — |
| 5 Freshness gate | `run_verus.py fresh …/receipts/ledger_redaction/<stamp>-prove.json` | `STALE … changed inputs` and exit 1 on an edited input | Run as written, **all three** `receipts/ledger_redaction/*-prove.json` are already STALE (earlier model), with no edit at all. That does not show the gate rejecting an edit. On a current receipt (`results/…/20261114T032750Z-prove/receipt.json`): FRESH (0) → I appended a comment to `redaction.rs` → `STALE … changed inputs: redaction.rs` (1) → restored → FRESH (0). | `$SCR/step5-fresh.out` | The step points at the wrong directory and never says to edit an input. Its inputs are only `redaction.rs` and `model.json`, so a change to the transcribed product code cannot make a receipt stale (R2-7). |
| 6 Distinguishing control | `python3 …/probes/redaction_concurrent_targets.py` | `OBSERVED_DEFECT` (or `INCONCLUSIVE`) | `OBSERVED_DEFECT`. Both entry checks raced. B's audit (seq 6, B's digest) names revisions 2 (A's) and 3, with 20 records. B's Final removed the marker. A late commit into A was accepted (seq 7). A then tombstoned seq 7 and was refused by **FinalInLock** ("became live again"). A's marker is left in the namespace. The same outcome as the receipt copy, in 6.5 s instead of 121 s. | `$RUN_DIR/native/redaction_concurrent_targets-20261114T033047Z.json`, `$SCR/step6-concurrent.out` | It does not say that the probe leaves an unfinished marker behind. |

Other runbook points:

- "Each model directory has … NOTES.md": `ledger_redaction/` has none. Its premises and trust items live in `coverage.md`.
- With the runbook's commands, a read-only reviewer cannot avoid writing into `.g5/` and `$RUN_DIR/verus/` unless they work out the mirror/`RUN_DIR` redirection themselves.

**Verdict:** the representative result reproduces: proof, all controls, the bit-identical twin, the binding observation, and the distinguishing product control. The freshness gate works but is documented wrongly. See R2-6.

## Coverage findings

- **R2-1 Prefix erasure does not remove temporal-only events, so the documented "erase by prefix, then redact" recipe completes while the tenant's events stay readable.** Category: missing intent; model error; product defect (suspected).
  - **Mechanism.**
    - `Eraser.EraseNodes(g, prefix)` collects ids from `SELECT node_id FROM Graph_KG.nodes WHERE graph … %STARTSWITH prefix` (`Eraser.cls:322-345`).
    - `TemporalIndex.EraseNodes` removes `^KG("tout")` edges only for ids in that set (`TemporalIndex.cls:400-440`).
    - A temporal-only predicate writes the temporal stores and no node row (`TemporalIndex.cls:103-114`: `AssertTemporalRow` only when `IsStructuralKey`). The uplift's own observation `redaction_temporal_only_live` shows "0 edge rows, 0 node rows".
    - So a tenant's temporal-only events whose endpoint ids are not node rows in that graph survive `delete_nodes_by_prefix("tenant|")`.
    - `LiveRows` does not read the temporal index. The redaction therefore tombstones their `create_temporal_edge` records and reports complete.
    - `verify` cannot see the events, and the window reader still returns them.
  - **Why the uplift missed it.**
    - The model's `erased(TemporalOnly{g,s,o}, t)` removes every prefix-matching event regardless of node rows (`redaction.rs:448`), which hides this.
    - The ontology's Q `redaction.after-erasure.temporal` offers "rely on erasure, which removes them anyway". That premise is false for prefix targets.
    - `simp-003`'s "a target whose content was erased is not refused" would leave such a tenant permanently unredactable: no erase short of `EraseGraph` of the whole shared graph removes the events.
  - **Evidence:** scratch witnesses d1/d2 under "Adversarial checks". Not probed natively (outside my authorization).
- **R2-3 The strict-mode erase path (a ledger changeset) is not an erasure, and redaction and verify cannot tell.** Category: missing intent; product defect (suspected, source reading).
  - Under strict mode, `erase_graph`, `erase_all` and `delete_nodes_by_prefix` raise. The only API deletion is `delete_node(detach)` / `delete_relationship` through the ledger.
  - `LedgerApply.DeleteNodeRows` (`LedgerApply.cls:353-372`) deletes `kg_NodeEmbeddings(_optimized)`, `rdf_labels`, `rdf_props` and `nodes` only. It leaves `Graph_KG.docs` (no FK, `schema.py:471-479`), the BM25/vector named indexes, the temporal index, FHIR side tables and the routed node vectors. A routed table's FK may instead refuse the whole changeset.
  - `LiveRows` and `verify` read none of these stores. So "delete through the ledger, then redact" completes with `verify()` = `equal` while the tenant's text, vectors and events remain.
  - The Q `redaction.strict-mode` and the strict-erase open question record only the named-graph node gap. `erasure.entry-points.single-path` lists the other deletes that bypass the Eraser, but not the ledger's node delete.
- **R2-4 `post_commit_properties` are a write channel that the core statements say cannot exist.** Category: incorrect intent.
  - `ledger.unrecorded` says strict mode refuses writes made outside the ledger. `ledger.commit.admission` / `redaction.batches.commits` say a commit with a record in the target is refused while a redaction runs.
  - `ledger.commit` itself writes `post_commit_properties` by direct SQL after the revision (`client.py:430-487`). That write is outside BlocksCommit and is not refused by strict mode.
  - So a commit whose post-commit properties name `tenant|…` makes a default-graph prefix target live in the middle of a run. Final then refuses and the marker stays until the target is erased again. After completion, the same write re-creates erased ids as `rdf_props` rows.
  - `q-010` and `bug-led-003` cover only verify divergence and replay.
- Checked and **adequately covered** by the uplift (no new finding):
  - BM25/`^VecIdx`/`^IVF`/`^PLAID` not erased (bug-srch-001; erasure.scope metadata);
  - quarantine kept (erasure.kept);
  - readers' TOCTOU and unchecked readers (redaction.batches.readers, q-002);
  - the verify/adopt race (bug-led-001);
  - the guard's TTL and fail-open behaviour (q-plt-001, ledger.strict.fail-open);
  - the unsalted digests (redaction.tombstone.digest);
  - the marker set at the first hit (bug-led-006);
  - `DropStatements` and the audit-without-marker branch (stated exclusions);
  - reifier cascade records (bug-led-005);
  - snapshot archives (q-led-002);
  - other-graph relationships naming the tenant (redaction.purpose metadata).
- bug-led-006's limitation ("the trace needs a create and a delete of target content inside the run's window") is too narrow. One `create_temporal_edge` of a temporal-only predicate into the target writes no row, so a single op suffices. The same R2-1 store blind spot is behind it. Low.

## Fidelity findings

- **R2-2 The R1-1 repair is not real at the lifecycle level: knowledge is still a constant, and attribution across resumed calls is unchecked.** Category: model error; correspondence error.
  - `K()` remains an uninterpreted constant used by `step` (Step), `commit_admits` (BlocksCommit) and every lifecycle lemma and theorem.
  - The "per-call knowledge" section (`redaction.rs:1581-1620`) holds two point evaluations of `matches` on hand-built `Know` values. Neither touches `St`, `step` or the invariant.
  - **Adversarial b1:** I defined `K()` as knowledge that knows nothing (`redacting = ∅`, `ends = ∅`), i.e. a product that never records `("redacting","stmt")` and has no PrePass or statement map. The model still verifies with **37 verified, 0 errors**.
  - So no lifecycle check distinguishes a product that keeps qualifier attribution across a pause/resume from one that loses it. "Proved" in the `redaction.batches.resume` coverage row overclaims for prefix targets. So does the trust-inventory sentence "sound only while redactions are serialised (`lemma_serial_resume_keeps_attribution`)". The resume evidence for prefix targets is the finite native observation `redaction_prefix_resume`, which is real and correct (see R1-2 below).
  - Second divergence hidden by the same constant: product BlocksCommit runs in the committing process, with no PrePass and with the commit's own statements already applied. The model gives it the run's `K()`. I found no reachable bad trace, because a target qualifier commit needs a live target statement, which liveness forbids. But this is an unstated premise.
- R2-1's model part: `erased()` over-approximates product erasure for `TemporalOnly` under a prefix target. It is an abstraction that removes a gap, the kind the review guidance warns "can hide a bug".
- **Checked and faithful:**
  - `matches` against `LedgerRedact.Matches` (graph test first; `Redact`/tombstone → No; node → prefix; create/delete/temporal → tuple ends; qualifier → redacting, then ends, else Unknown);
  - `checked` against `LiveRows`, including the prefix-only graph-blindness;
  - `Final` killing the marker whoever owns it, and the audit only with a marker;
  - one record per Step: interleavings are a superset of the product's per-batch ones, which is sound for safety;
  - `Abandon` for batch errors and `max_batches`;
  - `commit_outcome` order against `CommitInTxn`, with BlocksCommit after apply.
- The product-observation layer (twin + `redaction_common.knowledge`) checks L2↔product. The probe's own L1 attribution matches the twin (`l1_vs_twin` empty).

## Round-1 repair validation (core scope)

| R1 | Claimed repair | Validation |
|---|---|---|
| R1-1 | knowledge as state; resume conditional on serialisation | **Insufficient** (R2-2). It added point lemmas only; adversarial b1 shows the lifecycle results are insensitive to knowledge. |
| R1-2 | prefix resume probe | Real and sufficient as evidence. `redaction_prefix_resume` ran 9 one-batch calls. The qualifier (4,1) was tombstoned after its create_rel, in a later call (the `redacting` path). `unattributed` = 0 and verify is `equal`. Probe hashes match the current files. |
| R1-3 | controls re-run on the final model | Real. All 13 control receipts and the prove receipt in `results/` are FRESH against the current inputs. My re-run gave 13/13 `EXPECTED_FAIL`. |
| R1-4 | erasure atomicity Assumed | Real (coverage erasure row). |
| R1-5 | status words | Real: readers are "Observed"; completion is conditioned on "started" and "attributable". The resume row still says "Proved" for attribution (R2-2). |
| R1-6 | register gaps | Real: bug-led-001/003/004, bug-doc-001, the USER_GUIDE retries entry and the `ledger.commit.kind` Q are present. |
| R1-7 | bug-003 consequence and severity | Real (Medium; adoption restores verify). |
| R1-8 | graph-scoped `erased()`, W3 through `Erase` | Real for node rows. The same function over-approximates temporal-only events (R2-1). |
| R1-9 | completion condition; controls A1/B1 | Real (both controls EXPECTED_FAIL in my run). |
| R1-10 | wording, receipts, probe hashes | Mostly real (every native receipt has `_probe_inputs`, all matching the current files). One claim is stale: `redaction.batches.abort` metadata still says Final's re-check "has not been observed natively". `redaction_concurrent_targets` (receipt copy and my re-run) shows A refused by FinalInLock's "became live again" (R2-5). |
| R1-11 | reifier entry, exclusions | Real (bug-led-005; the coverage "Not modeled" line). |
| R1-12 | bug-002 "found by" | Real. |

## Adversarial checks

Each check edits a scratch copy of the current `redaction.rs` (`$SCR/adv/<name>/redaction.rs`). Command in each directory: `$VERUS_BIN redaction.rs --crate-type=lib --num-threads 4 --triggers-mode silent`. Log: `$SCR/adv/<name>/verus.log`.

| Kind | Name | Change | Verdict | Meaning |
|---|---|---|---|---|
| (a) erroneously permitted step | `a1_unknown_tombstoned` | Step tombstones when `matches != No` (unattributed records too), line 623 | 36 verified, **1 error**: `theorem_step_frame` | Over-redaction of other records is rejected, but only by the frame theorem: `lemma_step_preserves_inv` still passes. |
| (a) erroneously permitted step | `a2_final_keeps_marker` | Final appends the audit but keeps the marker, line 648 | 32 verified, **5 errors**: `lemma_step_preserves_inv`, `theorem_completion`, W1, `witness_without_blockscommit`, `witness_erase_then_redact_completes` | Detected. |
| (a) false premise | `d1_model_erase_removes_temporal_only` / `d2_product_erase_leaves_temporal_only` | d1: the current model plus a witness that `Erase{prefix}` removes a temporal-only event. d2: `erased(TemporalOnly)` made product-faithful (`t.m.len() == 0` only), plus witness `witness_r2_prefix_erase_then_redact_leaves_temporal_only`: Erase → Start → Step → Final complete, with the event still `content` and live | d1: 38 verified, 0 errors. d2: **38 verified, 0 errors** (witness holds) | The model's erase premise is false for the product. Under product-faithful erasure, the recipe completes with live tenant content (R2-1). |
| (b) faulty implementation | `b1_knowledge_dropped` | `K()` := `Know{redacting: ∅, ends: ∅}`, a product that keeps no attribution knowledge | **37 verified, 0 errors (survives)** | Not detected by any lifecycle property (R2-2). |
| (c) valid outcome | `c1_other_tenant_commit_proceeds` | New witness: A's run holds the marker; a keyed commit into B is admitted; the run completes; B's records are unchanged; B's key stays bound | 38 verified, 0 errors | "Other commits proceed" and the mixed-tenant frame survive in the as-built model. |
| (c) valid outcome, repair side | `c2_repaired_variant_valid_completion` | The same witness under `concurrent_repaired()` (simp-001's model variant) | 38 verified, 0 errors | The proposed repair still allows the legitimate completion. No inductive invariant exists for any concurrent variant (finite witnesses only, as simp-001 states). |

## Evidence findings

- Results receipts: the prove receipt, all 13 control receipts and the twin receipt in `results/ledger_redaction/` are FRESH against the current `redaction.rs`, `model.json` and `twin.rs`. No zero-test result, timeout or resource limit appeared in any run here.
- Native: all `receipts/native/*.json` carry `_probe_inputs`, and every hash matches the current harness and probe files. My two re-runs reproduce the receipt copies' verdicts and substantive fields.
- **R2-7 (Low; missing or stale evidence): what the receipts do not record.**
  - Native observations do not record the twin binary's hash, yet the binding classification is the binary at `$RUN_DIR/verus/twin/twin`. I verified it equals the twin receipt's `binary_sha256` and my rebuild.
  - Proof receipts record the product baseline as a constant string, not hashes of the transcribed product files (`LedgerRedact.cls`, `Ledger.cls`, `Eraser.cls`, `replay.py`).
  - So the freshness gate can show the theorem's inputs are unchanged, but never that the binding still applies (setup_foundation "decide separately…").
- **R2-5 (Low; stale evidence):** the claim that the final step's liveness re-check "has not been observed natively" (redaction.batches.abort metadata; the R1-10 action) is contradicted by `redaction_concurrent_targets`: A was refused by FinalInLock's "became live again" message. That is native evidence for the re-check, in the race context. It is still unobserved for a serial run.
- **R2-6 (Low; runbook defects):** see the reproduction table. In particular, step 5 points at stale receipts and cannot demonstrate the gate.

## Findings-register check

- Missing entries:
  - R2-1: new bug, suspected. It also needs a correction to `q-009` option (a), to the Q `redaction.after-erasure.temporal` option "rely on erasure", and to simp-003's "behavior to preserve". A repair must extend `EraseNodes`/`TemporalIndex.EraseNodes` to temporal endpoints by id prefix, not only to node rows.
  - R2-3: a new suspected bug, or an extension of `simp-str-001`/the strict-erase open question to the ledger's node delete.
  - R2-4: extend `q-010` and correct `ledger.unrecorded` / `ledger.commit.admission`.
- Severity and classification:
  - bug-001 High: agree (observed; my re-run identical).
  - bug-002 High, bug-003 Medium, bug-004 Medium: agree.
  - bug-led-006 Low: agree, but its trigger statement is too narrow (see Coverage).
- Unsupported claims:
  - the "Proved" status for prefix-target resume attribution, and the trust-inventory justification of `K()` (R2-2);
  - "not observed natively" for Final's re-check (R2-5).
- simp-001: its scope qualification is honest. The proposal ("claim the marker with a run token at the first batch") is not what the `repaired` variant models (refuse Step/Final under another target's marker). It also leaves the unstarted-run gap (bug-led-006) to the token; the variant does not show that.

## Summary table of material findings

| ID | Severity | Category | Owning artifact | Finding | Proposed correction |
|---|---|---|---|---|---|
| R2-1 | Medium | missing intent; model error; product defect (suspected) | `erasure.scope`, `redaction.after-erasure.temporal` Q, q-009, simp-003, `redaction.rs` `erased()` | Prefix erasure removes temporal-only events only for ids with node rows, and those events write none. Erase-then-redact completes and verify is equal while the events stay readable. The model's `erased()` hides this (d1/d2). | State the gap in erasure and redaction; drop "erasure removes them anyway"; make `erased(TemporalOnly)` product-faithful and keep the d2 witness; add a register bug and a native probe (temporal-only edge with tenant ids in the default graph → `delete_nodes_by_prefix` → window reader → redact); widen the simp-003 repair to `EraseNodes`. |
| R2-2 | Medium | model error; correspondence error | `redaction.rs` per-call knowledge section; coverage resume row; trust inventory | R1-1 repair not real at the lifecycle level: `K()` is still constant (runs and BlocksCommit). A knowledge-free `K()` still proves 37/37. | Model `redacting`, PrePass and the statement map as state (killed at Final) and prove attribution across Abandon/Start for serial runs. Or downgrade the row to "Observed (`redaction_prefix_resume`) + point lemma" and list the BlocksCommit knowledge difference as a premise. |
| R2-3 | Medium | missing intent; product defect (suspected) | `redaction.strict-mode` Q, strict-erase open question, `erasure.entry-points.single-path`, register | Under strict mode the only API delete is the ledger's, which leaves docs, temporal, FHIR and index content. LiveRows and verify cannot see it, so redaction "completes". | Add this to the strict-mode Q and the single-path divergence list. Register it, or extend simp-str-001 to `DeleteNodeRows`. |
| R2-4 | Low | incorrect intent | `ledger.unrecorded`, `ledger.commit.admission`, `redaction.batches.commits`, q-010 | `post_commit_properties` bypass strict mode and BlocksCommit and can make a target live mid-run. | Qualify the statements; extend q-010. |
| R2-5 | Low | missing or stale evidence | `redaction.batches.abort` metadata | Final's re-check *was* observed natively (`redaction_concurrent_targets`, A refused by FinalInLock). | Cite it; keep "serial case unobserved". |
| R2-6 | Low | missing or stale evidence (runbook) | runbook.md | Step 5 points at stale `receipts/` and has no edit step. Steps 1–3 write into `.g5/` and `$RUN_DIR/verus` (control dirs, the probes' twin). There is no `VERUS_RUN_THREADS`. Step 3 has no `--triggers-mode silent` and writes no receipt. There is no NOTES.md for ledger_redaction. Step 6 leaves A's marker. | Fix the commands. Add a reviewer mode (results/`RUN_DIR` redirection) and the edit-then-STALE-then-restore recipe. |
| R2-7 | Low | missing or stale evidence | harness `_probe_inputs`, `run_verus.py` receipts | The twin binary hash is not in native observations, and transcribed product files are not hashed in receipts, so the gate cannot detect a binding change. | Add the twin sha and the product-file hashes to the recorded inputs. |
