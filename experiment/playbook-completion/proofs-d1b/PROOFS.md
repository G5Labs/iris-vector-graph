# PROOFS-D1B: Verus L1/L2 refinement for modules 18 (snapshot) and 06 (vectors) (proof debt D-1, playbook §3.3)

Crate `experiment/playbook-completion/proofs-d1b` (`ivg-d1b-proofs`), Verus 0.2026.10.04.426d8b0, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved** (`--no-cheating`, no trusted item in this
crate), about **models**. Every theorem here is a statement about an L1 contract or a reviewed L2 machine. None says
that the Python or ObjectScript at pin `3eaa79cf` has the property. The product's obligations stay as the as-built
evidence leaves them (failed or open: `findings/audit/18.json`, `06.json`, `followup.json`).

| Gate item (§3.3) | Module 18 (snapshot) | Module 06 (IVF index lifecycle) | Module 06 (embed queue) |
|---|---|---|---|
| L1 contract with the business invariants (`Contract` + `SafeContract`) | `src/snap_l1.rs` | `src/vidx_l1.rs` | `src/vq_l1.rs` |
| L2 machine over the stored layout, reviewed design | `src/snap_l2.rs` (content stores, `^IVG.Ledger` head/idBySeq/rec, `^Graph.KG.LedgerRevisionD`, one writer transaction, the save, the replacing restore, archive files) | `src/vidx_l2.rs` (route rows, `^IVF(name)` cfg/list, staging generation, the `ivf_build` calls) | `src/vq_l2.rs` (`^EmbedQueue(node, text/status)`, vector rows, workers, worker lock) |
| `Refines<L1>` for **every** L2 step | 15 labels, each mapped (`lemma_step`) | 8 labels (`lemma_step`) | 5 labels (`lemma_step`) |
| L2 invariant inductive (`SafeContract`) | `inv18` (6 conjuncts) | `inv06i` (2) | `inv06q` (3) |
| Every raw L2 execution refines L1 and keeps both invariants | `snap_l2::theorem_raw_executions_refine` | `vidx_l2::theorem_raw_executions_refine` | `vq_l2::theorem_raw_executions_refine` |
| Broken-implementation controls rejected in the expected file | 6 of 6, all errors in `src/snap_l2.rs` | 2 of 2, all in `src/vidx_l2.rs` | 3 of 3, all in `src/vq_l2.rs` |
| Each control's counterexample proved reachable | 6 (`src/cx_f1801_history.rs`, `cx_f1801_unredact.rs`, `cx_fc1304.rs`, `cx_fc1801.rs`, `cx_fc1802.rs`, `cx_fc1804.rs`) | 2 (`src/cx_f0606.rs`, `cx_hd0602.rs`) | 3 (`src/cx_hd0604.rs`, `cx_f0604.rs`, `cx_fc0601.rs`) |
| Non-vacuity (the reviewed L2 does real work) | `src/witness_snap.rs` | `src/witness_vidx.rs` | `src/witness_vq.rs` |
| Trust inventory | empty (this crate and `actors`) | same | same |

Baseline: `cargo verus verify -- --no-cheating`: **92 verified, 0 errors** (module 18: 47; module 06: 25 + 20); Verus
2.19 s, SMT 2.41 s, 4.74 M rlimit, wall 2.61 s, 0.47 GB peak (registry `proofs-d1b-baseline`, log
`$RUN_DIR/proofs-d1b/baseline.log`, which ends with the counts read from its JSON). Gate: **pass** (`RESULTS.json`,
sources SHA-256 `6947c33b20bfe84f...`). An unregistered re-check over the same sources (`$RUN_DIR/proofs-d1b/scratch-2`)
gave the same result. Rerun:
`source experiment/playbook-completion/environment.sh; python3 experiment/playbook-completion/proofs-d1b/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600` after `cargo clean -p`; `PROOFS_OUT_DIR=<dir>` writes logs and
RESULTS.json there so a re-check never overwrites the registered logs; `--register` registers the decisive runs).

## 1. Module 18: snapshot save/restore against the ledger and redaction

### L1 contract (`snap_l1.rs`)

State: the namespace's committed `content` (items `(store, tenant, key)`; stores 0 tables, 1 `kg_emb_*` node-vector
routes, 2 `kg_eemb_*` edge-vector routes, 3 native globals), the ledger `led` (head, revision id per seq, recorded items
per seq), the redacted tenants `red`, and the archives `archives[id]`. Labels: `Commit{items,id}` (a ledger commit, module
11's contract at this level), `Write{items}` (a committed write without a revision), `Erase{ten}`, `Redact{ten,oor}`
(`oor`: the receipt's out-of-reach archives), `Save{id,arch}`, `Restore{id,out}` with `out = Refused | Done{failed}`.
Business rules and `inv1` (proved inductive):

- **an archive is a committed state** (HD-1802 working answer; SNP-I1): `Save` records exactly the committed content and
  ledger at one moment;
- **a restore keeps one history that only extends** (HD-1801 working answer; SNP-I3.6; SYS-I5): a restore is refused
  before any write, or the live history (its revision ids) is a prefix of the archive's.
  `theorem_history_only_extends`: no step lowers the head or changes a revision id. `theorem_next_seq_free`: the next
  commit's seq is free in every reachable state (F-1801's wedge cannot happen). `theorem_refused_restore_changes_nothing`.
  A restore into a fresh ledger (FR-043's round trip, head 0) is within the rule;
- **no redacted content returns** (ADR-0013; spec 256 US1; F-C1304): a restore re-applies the live redactions to the
  archive's content and records. `theorem_redacted_content_never_returns`: along any execution, once a tenant is
  redacted, no later state holds its content or a record of it, whatever saves, restores and commits follow;
  `theorem_receipt_names_holding_archives`: the redaction receipt names every archive that still holds the tenant;
- **a restore's answer says what it did not restore** (SNP-X2.14): `Done{failed}` restores exactly the archive's content
  minus `failed` (and minus redacted tenants). `theorem_complete_restore_reproduces_saved_state`: a `Save{id}` followed
  later by a `Restore{id}` that reports nothing failed brings back exactly the content and ledger the archive was saved
  from, minus only the tenants redacted since.

### L2 machine (`snap_l2.rs`) and refinement

Layout: `rows` (committed content), `cur` (what a reader sees, uncommitted rows included: SQL READ UNCOMMITTED and
global reads, SYS-P2), `g` (`^IVG.Ledger` head/idBySeq/rec and `^Graph.KG.LedgerRevisionD(seq)`, whose IdKey Seq refuses
a second row, LedgerRevision.cls:44, Ledger.cls:538-556), `scope` (reviewed only), one open writer transaction `w`, a
save in flight `x` (one read per store of the plan, then the ledger globals, then the ZIP, snapshot.py:864-1034,
395-409), a replacing restore in flight `r` (refusal checks snapshot.py:1095-1129, `erase_all` keeping the ledger's
records and head Eraser.cls:806-812, rows and globals, the archive's ledger nodes set over the live ones
snapshot.py:1554-1588 and 1654-1692, the answer), and the archive `files`. While a restore is in flight the abstraction
shows the pre-restore namespace (`abs18`); L1 sees the restore when it answers.

| L2 step | L1 step | Proof |
|---|---|---|
| `Commit` | `Commit` | `lemma_commit` |
| `CommitRefused` (revision row exists) | stutter (never enabled under `inv18`: `theorem_commit_never_wedged`) | `lemma_commit_refused` |
| `WOpen`, `WEnd{commit: false}` | stutter | `lemma_wopen`, `lemma_wend` |
| `WEnd{commit: true}` | `Write` | `lemma_wend` |
| `Erase`, `Redact` | `Erase`, `Redact` | `lemma_erase`, `lemma_redact` |
| `XStart`, `XRead`, `XLedger` | stutter | `lemma_xstart`, `lemma_xread`, `lemma_xledger` |
| `XEnd` | `Save` | `lemma_xend` (with `lemma_read_all`) |
| `RRefuse` | `Restore{Refused}` | `lemma_rrefuse` |
| `RBegin`, `RLoad`, `RLedger` | stutter | `lemma_rbegin`, `lemma_rload`, `lemma_rledger` |
| `REnd` | `Restore{Done{failed}}` | `lemma_rend` (with `lemma_overlay`) |

`inv18`: `inv_cur` (visible = committed plus the open writer's disjoint rows), `wf2(g)` (one history; revision rows are
exactly seqs 1..head), `inv_red` (no item of a redacted tenant is visible or recorded), `inv_files` (each archive's ledger
is one history), `inv_x` (a save in flight holds the gate and has collected the committed rows of the stores read so
far; its ledger copy is the ledger), `inv_r` (a restore in flight holds the gate; the live history is a prefix of the
archive's; what it has written so far). `lemma_overlay`: under the prefix the pin's overlay of the archive's ledger is a
wholesale replacement (so the reviewed design keeps the pin's write and adds the guard).

Reviewed design (the working answers and the findings' remedies), and its status at the pin:

| Id | Element | Source | At the pin |
|---|---|---|---|
| R18-1 | an export gate: the save holds it exclusively, every writer transaction (commit, writer, erase, redaction) shared | HD-1802 working answer (verified gate) | no: no lock (F-C1801, live c18-live-dirty-export, ib-HD1802-torn-save) |
| R18-2 | a restore is refused before any write unless the live history is a prefix of the archive's | HD-1801 working answer | no: checks layout/strict/caller txn only (F-1801, live) |
| R18-3 | a restore holds the same gate exclusively | HD-1801 (restore as a unit); modules/18.json omission "a restore while other processes write" | no: restore takes no lock (footprints/18.json) |
| R18-4 | a redaction keeps its scope; a restore re-applies it to the archive's rows and records; the receipt names IVG's archives | HD-1801 (keep current redaction obligations), F-C1304 remedy | no: no restore reads `redactedRev`/`idemRedacted` (snapshot.py has no reference to redaction); receipt names exports, journals, backups (LedgerRedact.cls:504-509) |
| R18-5 | a global line IRIS refuses is counted in `failed_rows` | F-C1802 remedy; restore docstring snapshot.py:1088-1094 | no: logged at debug (snapshot.py:1665-1684) |
| R18-6 | the export plan covers every store, edge-vector routes included | F-C1804 remedy; ADMIN_GUIDE.md:984-986 | no: node routes only (snapshot.py:299-344, security.py:58-68) |
| as built | the archive's ledger set node by node over the live one; refusals before any write; erase_all keeps the ledger | snapshot.py:1095-1152, 1654-1692; Eraser.cls:806-812 | yes |

## 2. Module 06: vectors

### 2a. IVF index lifecycle against erasure and builds (`vidx_l1.rs`, `vidx_l2.rs`)

L1 state: live vectors `vecs` (keyed `(graph, node)`), published indexes `idx[name] = (graph, entries)`, builds in
flight `pend[name]` with what each read. Labels: `Store`, `Erase{g}`, `BuildRead{name,g}`, `Publish{name}`,
`Abandon{name}`, `Search{name,ans}` (`ans = None` is "unavailable"). Rules: an erase of g removes g's vectors and every
index and build of g (HD-0601 working answer); a build reads g's vectors and publishes exactly that read in one step, or
is abandoned leaving the previous index (HD-0602 working answer); a search answers the published entries or
unavailable. `inv1`: every index and build lists only live vectors of its own graph. Theorems:
`theorem_search_answers_live_ids_of_its_graph` (no erased id is answered), `theorem_erase_leaves_nothing_of_the_graph`,
`theorem_published_whole`, `theorem_abandon_keeps_previous_index`, `theorem_index_changes_only_by_publish_or_erase`.

L2 layout: route rows `vecs`; `ivf[name]` = `^IVF(name)` with its cfg table (g's route, IVFIndex.cls:9, passed by the Build call at vector.py:2001-2010,
so the index's graph is in the layout) and its list (cell abstracted); `stg` (reviewed staging generation); the
`ivf_build` in flight `b` (Python read and k-means, `IVFIndex.Build`, one `AddBatch` per batch, `FinalizeIndex`,
vector.py:1880-2027, IVFIndex.cls:6-53, 237-276). Abstraction: `idx = ivf`, `pend` from `b`.

| L2 step | L1 step |
|---|---|
| `Store`, `Erase`, `Search` | same |
| `BRead` | `BuildRead` |
| `BBuild`, `BAdd` | stutter |
| `BPublish` | `Publish` |
| `BStop` | `Abandon` |

`inv06i`: the build read live vectors of its graph and its target generation holds only what it read (`inv_b`); every
staging generation holds only live vectors of its graph (`inv_stg`). L2 theorem `theorem_ivf_holds_only_live_vectors`:
no `^IVF` generation, published or staging, lists a vector not live in its graph (HD-0601's "stop holding").

### 2b. Embed queue workers (`vq_l1.rs`, `vq_l2.rs`)

L1 state per node: current request's text version, status, the text version its stored vector was made from. Labels:
`Enqueue`, `Embed{node,ver}`, `Mark{node,done}`. Rules: DONE only with a vector made from the current text (VEC-I7.18;
the re-enqueue rule of F-C0601); each request is answered once and a vector is stored only for a PENDING request
(HD-0604, single consumer). Theorems: `theorem_done_has_current_vector`, `theorem_answered_once`,
`theorem_no_work_on_answered_entry`.

L2 layout: `^EmbedQueue(node, "text"|"status")`, the vector rows, workers in flight (claim, model call, vector write,
status write; ProcessBatch EmbedQueue.cls:258-338 and Python process_embed_queue embeddings.py:1898-1990), the
reviewed worker lock. `Enqueue` -> `Enqueue`; `Claim`, `Embed` -> stutter; `Write` -> `Embed` (or stutter when no vector
was made); `Mark` -> `Mark` (or stutter when the version check writes nothing). `inv06q`: domains, single consumer
(`inv_one`), a worker's entry is PENDING and its written vector is the version it read (`inv_wk`). L2 theorem
`theorem_single_consumer`.

| Id | Element | Source | At the pin |
|---|---|---|---|
| R06-1 | a build fills a staging generation and publishes it in one step after its last batch | HD-0602 alternative (a) | no: kill and refill in place (IVFIndex.cls:8, 237-276) |
| R06-2 | EraseGraph(g) drops every `^IVF` generation (published or staging) whose recorded table is g's route | HD-0601 alternative (a) | no: the eraser names no `^IVF` (Eraser.cls; GraphStores.cls:28-131) |
| R06-3 | one worker per namespace (a lock from claim to mark) | HD-0604 (supported: 5bb149ed single-processor), alternative (b) | no: plain scan, no claim state (EmbedQueue.cls:22-25, 112-134) |
| R06-4 | ERROR when no vector was made | F-0604 remedy | no: DONE (EmbedQueue.cls:307-327) |
| R06-5 | the mark is written only if the entry's text is the one the worker read | F-C0601 remedy | no: unconditional (EmbedQueue.cls:326-327) |

## 3. Broken-implementation controls

Each feature puts back one as-built decision. Every error is in the expected file, every failing function is in that
file's module, every function of every other module verifies (`RESULTS.json`, `failing_outside_expected_module` empty),
and each control's counterexample (compiled only with it) is a proved run of the L2 step relation from its initial
state to a step that is not an L1 step.

| Control (finding) | Rejected at (function: obligation) | Proved counterexample | Registry |
|---|---|---|---|
| `control_f1801_no_prefix_check` (F-1801 history half, HD-1801) | `snap_l2.rs:524` `lemma_rbegin`: `prefix(live, archive)` | 14 steps: commit 1, save archive 0 (7 steps), commit 2, replacing restore of archive 0 (4 steps): the answer is not an L1 step, head back to 1 with revision 2's id and row left, `!inv1`; then `CommitRefused` is enabled (the wedge) | `proofs-d1b-f1801-no-prefix-check` |
| `control_f1801_restore_unredacts` (F-1801 redaction half, F-C1304 restore) | `snap_l2.rs:538` `lemma_rload` (rows re-scrubbed), `:553` `lemma_rledger` (records re-scrubbed), `:568` `lemma_rend` (the answer's ledger) | 14 steps: tenant 7 commits, save, erase, redaction, restore of the pre-redaction archive (histories agree, so the prefix check passes): row and record back, `!inv1` | `proofs-d1b-f1801-restore-unredacts` |
| `control_fc1304_receipt_omits_archives` (F-C1304 receipt) | `snap_l2.rs:454` `lemma_redact`: the receipt names every archive holding the tenant | 10 steps: commit, save, erase, redaction whose receipt names no archive while archive 0 holds the tenant | `proofs-d1b-fc1304-receipt-omits-archives` |
| `control_fc1801_dirty_export` (F-C1801, HD-1802) | `snap_l2.rs:473` `lemma_xstart` (no open writer), `:380/:408/:432/:447` `lemma_commit/wopen/erase/redact` (no save in flight) | 9 steps: a writer opens and creates a row, save of archive 0 (7 steps): the save is not an L1 step; the writer rolls back: committed rows empty, the archive holds the row | `proofs-d1b-fc1801-dirty-export` |
| `control_fc1802_swallowed_line` (F-C1802) | `snap_l2.rs:536` `lemma_rload`: the refused line is counted | 12 steps: a global line committed, saved, restored with IRIS refusing it: `failed` empty, line missing, not an L1 step | `proofs-d1b-fc1802-swallowed-line` |
| `control_fc1804_edge_routes_omitted` (F-C1804) | `snap_l2.rs:369` `lemma_read_all`: every store is in the export plan | 12 steps: an edge vector committed; the save skips the `kg_eemb_` store (not an L1 step); the replacing restore answers `failed` = {} with the edge vector gone | `proofs-d1b-fc1804-edge-routes-omitted` |
| `control_f0606_erase_keeps_ivf` (F-0606, HD-0601) | `vidx_l2.rs:176` `lemma_erase` (published generations of g dropped), `:180` (staging generations of g dropped) | 7 steps: store, build and publish over graph 0, erase_graph(0): not an L1 step; search still answers the erased id; `!inv1` | `proofs-d1b-f0606-erase-keeps-ivf` |
| `control_hd0602_inplace_build` (HD-0602) | `vidx_l2.rs:214` `lemma_bbuild`, `:228` `lemma_badd` (the published index unchanged by a build step) | 13 steps: two vectors, a complete build published, a rebuild kills the index (not an L1 step), a search answers nothing, one batch, the build stops: the index answers one of two vectors | `proofs-d1b-hd0602-inplace-build` |
| `control_hd0604_two_consumers` (HD-0604) | `vq_l2.rs:171/:172` `lemma_claim`: a second worker waits for the lock | 9 steps: two workers claim the same entry; one marks DONE with a vector, the other's model call fails and it marks ERROR over the answered request (not an L1 step) | `proofs-d1b-hd0604-two-consumers` |
| `control_f0604_done_without_vector` (F-0604) | `vq_l2.rs:229` `lemma_mark`: DONE only when a vector was made | 5 steps: claim, failed model call, no write, DONE: not an L1 step, `!inv1` | `proofs-d1b-f0604-done-without-vector` |
| `control_fc0601_no_version_check` (F-C0601) | `vq_l2.rs:231` `lemma_mark`: the entry's text is still the version read | 6 steps: claim at version 1, vector made, re-enqueue (version 2), old vector written, DONE: not an L1 step, `!inv1` | `proofs-d1b-fc0601-no-version-check` |

Counts (verified / errors, each including its verified counterexample function and excluding its family's witness):
F-1801 history 91/1; F-1801 redaction 89/3; F-C1304 91/1; F-C1801 87/5; F-C1802 91/1; F-C1804 91/1; F-0606 91/1;
HD-0602 90/2; HD-0604 91/1; F-0604 91/1; F-C0601 91/1. Each control run took 2.0-2.6 s of wall time.

The same as-built decisions were reproduced live by breadth lane C (c18-live-ledger-overlay, c18-live-dirty-export,
c18-live-swallowed-lines, c18-live-edge-vectors, c18-live-edge-routes), the follow-up (fu-r01a-snapshot-copies), the
intent lanes (ib-HD1801-merge-restore, ib-HD1802-torn-save, intent-a-hd0601-index-erasure, intent-a-hd0602-ivf-partial,
intent-a-hd0604-queue-claim) and breadth lane A (breadth-a-live-06-vectors), and by the explorer models (cmc-restore-*,
cmc-snap-*, breadth-a-mc-vec_*); F-C0601 is model-only (breadth-a-mc-vec_queue-as-built). These counterexamples are
proved over the models.

## 4. Premises (named; none is an assumption inside a proof)

| Id | Premise | The pin |
|---|---|---|
| P-S1 | a ledger commit (rows and revision) is one step; a commit nested in a caller's transaction is not modelled | modelling granularity; module 11's own L2 (`proofs-breadth`) models nesting, this model does not |
| P-S2 | each store's export read, the ledger read, the restore's load and its ledger write are one step each | the pin walks node by node; under R18-1/R18-3 nothing interleaves; as built, finer interleavings only add violations (F-C1801's control already fails) |
| P-S3 | an erase of a tenant waits for an open writer's uncommitted rows of that tenant | **violated**: F-1201 (live) and F-C1202 show an eraser overlapping a writer of the same graph (P-A3 of `proofs-breadth`, D-13) |
| P-S4 | a redaction runs only when no item of the tenant is visible (uncommitted included), in every store | established for the content tables (LiveRows, LedgerRedact.cls:206-209, 412-415); **not** for routes and native globals, which LiveRows does not read |
| P-S5 | a redacted tenant's ids are not written again | **not enforced**: CommitInTxn refuses only while a redaction runs (LedgerRedact.cls:28-29); a reuse is new content, which this model cannot tell from redacted content |
| P-S6 | at most one open (multi-step) writer transaction, one save and one restore at a time | **violated**: any number of writer transactions; N server processes can save concurrently (module 18 gate 3.7; F-1807) |
| P-S7 | revision ids identify revisions (CreateGUID is fresh), so the prefix check over ids compares histories | assumed (P-L1 of `proofs-breadth`) |
| P-V1 | one build at a time | **not enforced**: no lock; `ivf_build` is several server calls |
| P-V2 | a search reads the published generation in one step | the pin's Search walks `$Order` (IVFIndex.cls:55-158); under R06-1 the published generation changes only by an erase; as built, partial reads inside one search only add violations |
| P-V3 | an erase of g overlaps no build of g | **not enforced**: nothing locks `^IVF` against the eraser |
| P-V4 | each id is listed in one cell (the cell is abstracted) | **violated**: F-0608 (live: a re-insert lists the id in two cells) |
| P-V5 | only builds write `^IVF` (single-entry `Insert`/`Delete`, `Drop`, VecIndex, PLAID are not modelled) | `Insert`/`Delete` exist (IVFIndex.cls:180-232) and are where F-0608 lives |
| P-Q1 | one graph; node-keyed entries only (no `txt:` entries, no cross-graph refusal) | modelling restriction |
| P-Q2 | a worker's claim, model call, vector write and status write are one step each, per entry | the Python worker claims a batch and makes one model call per batch; per-entry steps are a finer view of it |

## 5. Cost (measured, `RESULTS.json`)

Baseline: Verus 2.19 s, SMT 2.41 s, 4.74 M rlimit over 92 functions, wall 2.61 s, 0.47 GB.

| Module proof | Functions | SMT ms | rlimit | Largest function | Largest proof lemma |
|---|---|---|---|---|---|
| 18 snapshot (`snap_l1`, `snap_l2`, `snap_runs`, `witness_snap`) | 47 | 1,664 | 3.21 M | `witness_snap::witness_snap` 0.72 M | `snap_l2::lemma_rend` 0.12 M |
| 06 IVF index (`vidx_l1`, `vidx_l2`, `witness_vidx`) | 25 | 309 | 0.69 M | `witness_vidx::witness_vidx` 0.14 M | `vidx_l2::lemma_erase` 0.06 M |
| 06 embed queue (`vq_l1`, `vq_l2`, `vq_runs`, `witness_vq`) | 20 | 431 | 0.84 M | `witness_vq::witness_vq` 0.35 M | `vq_l2::lemma_write` 0.06 M |

No rlimit was raised and no proof looped; each L2 step has its own lemma over named invariant conjuncts. The 12 decisive
runs took about 27 s of Verus wall time in total. Development needed five fixes before the gate passed: three trigger hints in
`vidx_l2` (an `idx_ok` instance), the lower bound of `read_upto` (stores are counted from 0), and the witness of a negated
`idx_ok` in `cx_f0606`.

## 6. Trust inventory

This crate has no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). The scan of `actors` (`c03f9fa`) finds none either; `actors` was verified
(121 verified, 0 errors) in this lane's first build in the same target directory and is cached since (the runner cleans
this crate only, as `proofs-breadth` does). vstd is Verus's trusted base (`Map::new`, set extensionality and their axioms
included). The gate status is **declared empty** (`RESULTS.json` `trust_inventory`).

## 7. What is NOT proved (open obligations)

- **No proof connects the Python or ObjectScript to these L2 machines** (D-2, D-3). The L2 step relations and the three
  `theorem_raw_executions_refine` are the plug-in points for trace conformance; the journal traces of
  c18-live-restore-footprint and breadth-a-journal-footprints are not replayed through them.
- Module 18 items not modelled: merge restore (F-1802 merge guard key, F-1805 derived aggregates; HD-1801's cells for
  merge are open); idempotency bindings (the `idemRedacted` binding F-C1304 shows live again, the binding past head in
  F-1801); value types (F-1804); edge-vector keys (F-1803); the file and global helpers (F-1806, F-C1803); the HTTP
  endpoint's file naming (F-1807); a forced replacement (HD-1801 alternative (a)); crash mid-restore (SNP-T3.1); readers
  during a restore (the abstraction shows the pre-restore namespace; a reader at the pin sees the erased one);
  capacity (the whole archive in memory).
- Module 06 items not modelled: single-entry `Insert`/`Delete` and the cell structure (F-0608, P-V4, P-V5); VecIndex and
  PLAID (caller-fed indexes, HD-0601 asks for a declaration); per-node vector deletion; stale vectors after an update
  (allowed here: a rebuild is needed); two concurrent builds (P-V1); an erase during a build (P-V3); scores, k, nprobe;
  F-0601..F-0618 other than F-0606 and F-0604; the queue's identity registry (F-0603), graphs and routes (F-0615),
  `txt:` entries and ClearDone (review R2-10's queue copies).
- HD-0602's completeness is stated against what the build read (`pend`), not against the vectors live at publication.
- No progress or liveness property for either module (the explorer's AG EF checks are bounded and separate).
- The L1s are new contracts written for this lane; their correspondence to the ontology statements (SNP-*, VEC-*) and to
  the explorer models' invariants (M4 snapcut, M5 restore, vec_ivf, vec_build_publish, vec_queue) is by inspection.
- The reviewed designs rest on working answers: HD-1801, HD-1802, HD-0601, HD-0602 are assumptions, HD-0604 is
  supported (5bb149ed) for the single-consumer premise with enforcement open; none is a maintainer decision.

## Premises the pin violates

Three premises of these models are false at pin `3eaa79cf` by this audit's own evidence: P-S3 (an eraser overlaps a
writer of the same graph: F-1201, F-C1202), P-S6 (any number of writer transactions and concurrent saves), and P-V4 (an
id listed in two cells: F-0608). Four more are not enforced by the pin, with no observed violation: P-S4 for routes and
native globals, P-S5, P-V1 and P-V3. Every reviewed-design element R18-1..R18-6 and R06-1..R06-5 is also absent at the
pin (sections 1 and 2), and each control shows the corresponding as-built decision violating the model's contract on a
reachable run. So no safety result here transfers to the product. What transfers is the negative: each as-built
decision listed in section 3 breaks the contract on a reachable run of the model.

## Debt accounting (for `PROOF-DEBT.md` D-1)

Paid, model-level only, by `proofs-d1b-baseline` and the 11 `proofs-d1b-*` control runs: the §3.3 L1, L2, refinement and
controls items for module 18 (save, replacing restore, ledger, redaction and receipt, as modelled) and module 06 (IVF
index build, publication, erasure and search; embed-queue workers). Still owed under D-1: modules 00-03, 05, 07-10 and
15-17, and the unmodelled parts of 18 and 06 listed in section 7. This lane does not edit `PROOF-DEBT.md` or
`STATUS.md` (outside its write scope); the orchestrator moves the row.
