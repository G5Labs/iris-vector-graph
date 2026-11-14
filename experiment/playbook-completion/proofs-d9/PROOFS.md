# PROOFS-D9: the erase/redact/replay protocol under the pin's real premises (proof debt D-9)

Crate `experiment/playbook-completion/proofs-d9` (`ivg-proofs-d9`), Verus 0.2026.10.04, vstd 0.0.0-2026-09-20-0158,
`actors` at `c03f9fa`. Evidence grade: **proved** (decisive, `--no-cheating`, no trusted items), about **models only**.
No proof here connects the ObjectScript or Python at pin `3eaa79cf` to these contracts, and none of the guards proved
necessary here is present at the pin. Every result below reads "the reviewed model satisfies ...". None of it is a
property of the product.

| Item | Result | Registry |
|---|---|---|
| Baseline `cargo verus verify -- --no-cheating` | **115 verified, 0 errors**, Verus 4.6 s, 20.1 M rlimit | `proofs-d9-baseline` |
| Safety controls (5 new guards + F-1201 regression) | 6 of 6 rejected only in the expected file; each has a proved reachable counterexample | `proofs-d9-{bypass-start, bypass-erase, liveness-dirty, unaligned-rm, unaligned-sc, f1201-erase-unlocked}` |
| Progress-only control | fails only `progress::RunProgress::nonincreasing` (`src/progress.rs:183`); the 104 non-progress functions all verify | `proofs-d9-progress-rewind` |
| Trust inventory | empty (this crate and `actors`) | `RESULTS.json` `trust_inventory` |
| Gate | **pass** (`RESULTS.json`, sources SHA-256 `b779916f...`, logs `$RUN_DIR/proofs-d9/run-20261114T074409Z/`) | |

Rerun: `source experiment/playbook-completion/environment.sh; python experiment/playbook-completion/proofs-d9/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600`, after `cargo clean -p`; logs in a new `run-<stamp>/`
directory under `$PROOFS_OUT_DIR` or `$RUN_DIR/proofs-d9`; `--register` refuses an id that is already recorded and
takes `--id-suffix` for a rerun).

## 0. What D-9 asked, and what changed against `proofs/`

`proofs/` (88 verified) collapses three premises the pin violates (`proofs/PROOFS.md`, "Premises the pin violates").
This crate drops all three and puts each mechanism into the model:

| Collapsed in `proofs/` | Here | Where |
|---|---|---|
| P-C03: one target predicate for record match, liveness and statement cleanup (F-1304, F-1305) | a target is **three predicates** `Tgt { rm, lv, sc }` (Matches, LiveRows, DropStatements). BlocksCommit uses `rm`, Start/Final check `lv`, Final drops `sc`. The reviewed Start refuses a target that does not satisfy the side condition `lv ⊇ rm ⊇ sc` (on edges) | `vocab.rs` (`aligned`, `rm_in_lv`, `sc_in_rm`), `mid.rs` |
| P-C02: no ledger-bypassing writer (writer census: 46 undeclared writers; F-C1301) | a fourth participant **Writer**: any content write outside the ledger, in its own open transaction, visible at once (E-VIS), committed or rolled back; it never reads the marker and takes no ledger lock unless a guard says so | `writer.rs`, `protocol_top.rs` |
| P-C04: an erasure never rolls back after a liveness check saw it (F-C1201) | the erasure is four steps of one open transaction (row deletes, statement cleanup, outermost commit **or rollback**), its undo log in the store; rollback is value-based (E-ROLLBACK-OTHER, E-STOP) | `store.rs` |

Ghost provenance `unrec` (store) marks keys whose current row was last written outside the ledger; such a row is not
the content of any ledger record (core model M2's "new incarnation"). It is the only place a bypass writer weakens a
conclusion, and with no bypass write every theorem below is the corresponding theorem of `proofs/`.

## 1. Participants (each `Contract` + `SafeContract`, own state only)

| Participant | State | Labels | Own invariant |
|---|---|---|---|
| **Ledger** (`ledger.rs`) | as in `proofs/` (history, idempotency keys, head lock, enabled, marker with the run's cursor and bound, count/tally); the marker names a three-predicate target | `Commit` (BlocksCommit refusal on the marker's **record match**), `Replay`, `Lock`, `Unlock`, `SetEnabled`, `Mark`, `Batch`, `Rewind`, `Audit` | `count == tally.len()`; no marker ⇒ count 0; bound keys name revisions |
| **Redactor** (`redactor.rs`) | as in `proofs/` (process-local cursors) | `Open`, `Attach`, `Advance`, `ToFinal`, `Finish`, `Stop` | no cursor passes its bound |
| **Store** (`store.rs`) | `rows` as other processes see them (READ UNCOMMITTED); ghost `unrec`; statement index `stmts`; open erasure `{e, saved, sst, idx}` (its undo log) | `Apply`, `EraseRows`, `EraseIndex`, `EraseCommit`, `EraseAbort`, `Write`, `Undo`, `Drop` (accepts every write at any time, as built) | structural only: statement entries are edges'; the undo log lies in the erasure's target. (With rollback, row/statement consistency depends on coordination and is a business invariant, not the store's.) |
| **Writer** (`writer.rs`, new) | `open[k]`: an open bypass transaction on row k with its before-image `(before, was)` | `Begin`, `Commit`, `Abort` | `true` (nothing beyond the map's shape) |

A writer's multi-row transaction is represented as one transaction per row whose ends happen together; every
interleaving of those is an execution here, so single-row transactions over-approximate multi-row ones.

## 2. Three `Protocol2` levels and the guards

Partitioned one level per new concern, so each control's error lands in one file:

**Level 1 `RLP`: Ledger x Redactor → `RL`** (`protocol_rl.rs`): unchanged from `proofs/` (locked one-step Start with
its marker, HD-1301; Scan from the marker's cursor under its own marker; Final under its own marker). The cursor scans
with the target's record match.

**Level 2 `SysP`: RL x Store → `Mid`** (`protocol_sys.rs`, `mid.rs`), owns `pend`:
- the eraser takes the head lock at its row deletes and releases it at its outermost commit **or rollback** (HD-1201;
  E-LOCK-DEFER: an unlock inside a transaction takes effect at its end). Hence **G-L: the liveness check runs under
  the eraser's lock** — no Start or Final can observe an open erasure;
- **G-P: Start refuses a target unless `aligned(t)`** (`rm ⊆ lv` and `sc ∩ edges ⊆ rm`; HD-1303(b1) graph-blind
  liveness makes `lv` cover what `rm` matches; HD-1304 refuse/flag an unattributable target), and checks
  `!live_in(rows, t.lv)` in the same locked step;
- Final re-checks liveness and, when it succeeds, drops statements with `t.sc` (DropStatements);
- `pend`: an erasure's domain joins at its commit; a fresh run's `rm` at Start; a successful Final removes every
  pending domain its `rm` covers.

**Level 3 `TopP`: Mid x Writer → `Biz`** (`protocol_top.rs`, `biz.rs` `top_ok`):
- **G-B: Start waits until no bypass transaction is open** (bypass writers serialized with redaction start only: they
  may overlap commits, batches, Final and each other);
- **G-BE: EraseRows waits for open bypass transactions on its target's rows**;
- row locks (premise P-D9-2): a ledger commit waits for rows an open bypass transaction wrote; a bypass write waits for
  rows the open erasure deleted.

Every level proves `step_binds` and `step_enabled` for every operation (`lemma_p1_binds/enabled`,
`lemma_p2_binds/enabled`, `lemma_p3_binds/enabled`).

## 3. Outer contract `Biz` and its invariants (`biz.rs`, proved inductive in `safety.rs`)

**Committed view.** `crow(x,k)`, `cunrec(x,k)`, `cstmt(x,k)`: the row, provenance and statement entry at k that a
rollback of every open transaction (the erasure's, every writer's) would leave. The invariants are stated on the
committed view plus overlay facts relating the visible rows to it, so they hold in every state a rollback can produce.
`theorem_open_and_rollback_keep_view` (`safety.rs`): EraseRows, EraseIndex, EraseAbort, BBegin and BAbort leave the
committed view unchanged at every key; only commits change it.

`biz_inv(x)`: participants' invariants; `locked == (erasure open)`; marker ⇒ (`pend ∋ t.rm`, `aligned(t)`, cursor
and tally facts as in `proofs/`); and for every key `key_ok(x,k)`:
- C1 `c_stmt_ok`: at keys with recorded provenance, committed statement entry ⟺ committed row (edges);
- C2 `c_replay_ok`: outside `pend`, at keys with recorded provenance, replay equals the committed row;
- C3 `mark_key_ok`: while t is marked, no key `t.rm` selects holds recorded content in the committed view;
- overlay: an open bypass row is `unrec`; the erasure's saved rows are absent and not under a bypass transaction; no
  key of the erasure's target holds recorded content visibly or (unsaved) in the committed view; after cleanup no
  statement entry of the target remains.

## 4. Theorems (exact statements in `theorems.rs`) and their premises

All are proved from `biz_inv(x)` and one `biz_next` step, under the named premises of section 5 (which are encoded
in the contracts, not assumed in proofs):

- **No tombstone of live content** `theorem_no_tombstone_of_live`: a record becomes a tombstone only while its key
  holds no recorded content — not in the visible rows and not in the committed rows (what a rollback restores) —
  before and after the step.
- **Per-target audit** `theorem_audit_counts_own_target`, `theorem_tally_counts_own_target`: a successful Final runs
  under its own marker; its audit names its target and counts exactly its tally, every tallied record selected by its
  `rm`.
- **Marker ownership** `theorem_marker_owned`: as in `proofs/`.
- **Statements match live edges** `theorem_statements_match` (visible rows, outside the open erasure, at keys not
  `unrec`) and `theorem_statements_match_committed`.
- **Replay = store once settled** `theorem_replay_settled`: `settled` (nothing pending, no open erasure, no open bypass
  transaction) ⇒ replay equals the rows at every key not `unrec`, and they are equal when no bypass write happened.
- `theorem_start_reads_committed`: whenever the reviewed Start may run, the rows its check reads are the committed rows
  at every key — so the reviewed design also satisfies the alternative "liveness on committed state".
- `theorem_pending_needs_cover`: a pending domain leaves `pend` only through a successful Final whose `rm` covers it
  (F-1305's erasure of a graph whose node records the graph target does not match stays pending: never "settled").
- `theorem_marked_target_aligned`: every marked target satisfies the side condition.
- Final may run while bypass transactions are open (it reads their uncommitted rows): the proof of `lemma_final`
  relies on `sc ⊆ rm` and C3, not on Final's liveness re-check, so such a Final cannot remove a statement of recorded
  content. That the re-check is unnecessary for every invariant is reasoning only: no control removes it.

Composition (`system.rs`): for **all** implementations `IL, IR, IS, IW` of the four contracts,
`Top = Sys<TopP, Sys<SysP, Sys<RLP, IL, IR>, IS>, IW>` refines Biz (`theorem_implementations_refine`, `_init`), every
state satisfies `biz_inv` (`theorem_implementations_safe`), every visible step is a `biz_next` step between invariant
states (`theorem_implementation_steps`, `_states`), and any machine refining the composed contracts refines Biz
(`theorem_levels`). `sys_step` is the flattened composed relation the controls change; `theorem_sys_safe` covers it.

## 5. Premises (named; each weaker than the one it replaces, or new and stated)

| Id | Premise | Replaces / maps to |
|---|---|---|
| P-D9-1 | Ledger commits, replays and the redaction's Start, batches and Final are one atomic transaction each, holding the head lock (a stopped one leaves nothing). Erasures and bypass writes are **not** atomic: they stay open across steps and may roll back. | P-C01 narrowed (it covered erasure too); IRIS E-NEST, E-LOCK-DEFER, E-STOP |
| P-D9-2 | Row locks: a ledger commit waits for a row an open bypass transaction wrote; a bypass write waits for a row the open erasure deleted. Decided by the contract for inserted/updated rows (E-ROWLOCK, E-UNIQUE); the other cases (insert over another's uncommitted delete) are the contract's Freedom, modelled as a wait as core model M2 does | new |
| P-D9-3 | Bypass writers write content rows only, never ledger globals (records, statement index, marker) | writer census (`$RUN_DIR/checks/writer-census.json`; `models/core/MODELS.md` §bypass writer) |
| P-D9-4 | An erasure's row deletion and its statement cleanup select the same keys (EraseGraph's SQL and EraseLedgerFor, both by graph) | the eraser's part of P-C03; EraseNodes/EraseEdges/EraseAll not modelled |
| P-D9-5 | Record keys are the ghost keys of the rows they describe (graph-blind node records carry the ghost graph, as M1); replay is keyed the same way, so verify()'s graph-blind comparison (F-1401) is outside the model | as in `proofs/` |
| design | the reviewed guards G-L (HD-1201 + HD-1301), G-P (HD-1303/HD-1304 working answers), G-B and G-BE (F-C1301 remedy; HD-1201 extended to every same-target writer) | **none is at the pin** |

Dropped against `proofs/`: P-C02 (bypass writers), P-C03 (one predicate), P-C04 (no rollback). The old model's
executions are those of this one with no Writer step, no EraseAbort, and targets with `rm = lv = sc` (which are
aligned); this embedding is by inspection, not proved.

## 6. Controls (each removes one guard; each must fail only in its file and has a proved counterexample)

| Control (guard; finding) | Rejected at | Proved counterexample (`sys_step` run from the initial state; violation) | Counts | Registry |
|---|---|---|---|---|
| `control_bypass_start` (G-B; F-C1301) | `protocol_top.rs:74` `lemma_p3_binds` | `cx_bypass_start` (6: commit A's edge; bypass delete open; open; Start marks A — its check saw A empty; Scan tombstones the edge's record while it is committed content; bypass rollback: the edge is live, recorded, history tombstoned); `!biz_inv` | 115 / 1 | `proofs-d9-bypass-start` |
| `control_bypass_erase` (G-BE) | `protocol_top.rs:74` `lemma_p3_binds` | `cx_bypass_erase` (6: commit A's edge; bypass delete open; EraseRows misses the hidden row; cleanup kills its statement; erasure commits; bypass rollback: live recorded edge without statement, nothing open); `!biz_inv` | 115 / 1 | `proofs-d9-bypass-erase` |
| `control_liveness_dirty` (G-L; F-C1201) | `protocol_sys.rs:107` `lemma_p2_binds`, `:115` `lemma_p2_enabled` | `cx_liveness_dirty` (6: commit; erasure open holding the lock; the call's unlocked check sees A empty; erasure rolls back; locked Start marks A while live; Scan tombstones live content); `!biz_inv` | 114 / 2 | `proofs-d9-liveness-dirty` |
| `control_unaligned_rm` (G-P `rm ⊆ lv`; F-1304, shape of F-C1308) | `protocol_sys.rs:107` `lemma_p2_binds` | `cx_unaligned_rm` (4: the pin's `redact(None)`: `rm` = every node record + default-graph relationships, `lv` = default-graph rows; a node of graph 1 committed; open; Start; Scan tombstones its record while it is live); `!biz_inv` | 115 / 1 | `proofs-d9-unaligned-rm` |
| `control_unaligned_sc` (G-P `sc ⊆ rm`) | `protocol_sys.rs:107` `lemma_p2_binds` | `cx_unaligned_sc` (7: `sc` = every graph's statements; commit B's edge; redaction of A to a successful Final whose cleanup removes B's live edge's statement); `!biz_inv` | 115 / 1 | `proofs-d9-unaligned-sc` |
| `control_f1201_erase_unlocked` (original HD-1201 lock; F-1201) | `protocol_sys.rs:107` `lemma_p2_binds`, `:116` `lemma_p2_enabled` | `cx_f1201` (4: EraseRows without the lock; a commit creates A's edge; cleanup kills its statement; erasure commits); `!biz_inv` | 114 / 2 | `proofs-d9-f1201-erase-unlocked` |

Counts include the verified counterexample. No control passes as a stutter: `step_binds` demands one outer step per
protocol step. The two bypass controls produce byte-identical diagnostics (same lemma, same line, same wall time);
their JSON logs differ and each lists its own counterexample as verified.

## 7. Progress (`progress.rs`)

`theorem_redaction_completes(s, l, i)`: `infinite_execution::<RunProgress>` and `productive_fairness::<RunProgress>`
⇒ the marked run of t eventually has a successful Final (`eventually_drained`). `FairWork::nonincreasing` covers every
Biz step, including the four erasure steps, bypass begin/commit/rollback, and a Final refused because t is live again.
`theorem_work_available` shows what makes productive fairness reasonable, under these named premises:

- PF-1 the operator re-runs after a stop; PF-2 the ledger is enabled; PF-3 every erasure ends (commit or rollback
  releases the head lock); PF-4 an enabled step is eventually scheduled (as in `proofs/`);
- **PF-5 (new) every bypass transaction ends** (a resume's Start waits for them, G-B);
- **PF-6 (new) eventually nothing `t.lv` selects is live when Final runs**: neither a bypass writer (F-C1307, live at
  the pin) nor a ledger commit into `lv \ rm` (BlocksCommit refuses only `rm`) keeps it live, or the operator erases t
  again (LedgerRedact.cls:415). Final (and a resume's Start) are refused while it is live.

PF-5 and PF-6 are stronger than `proofs/`'s premises because the pin violates the old "no write outside the ledger";
none is derived or tested against IRIS scheduling.

**Progress-only control** `control_progress_rewind` (a resume rewinds the cursor to the first record, the pin's
LedgerRedact.cls:213): 114 verified, 1 error at `progress.rs:183` (`RunProgress::nonincreasing`, the resume case);
the 104 functions outside `progress` all verify and are exactly the baseline's (`safety_still_verifies: true`;
`proofs-d9-progress-rewind`).

## 8. Non-vacuity

`step_enabled` at all three levels for every operation; `witness.rs`: `witness_erasure_rollback` (commit two tenants;
erasure of A rolls back and A's row and statement are restored exactly; erasure again to its commit),
`witness_bypass_and_redaction` (a bypass write that rolls back, the same write committed, then the whole redaction of
A with three different aligned predicates: `lv` wider than `rm`, `sc` narrower), `witness_settled` (settled; replay
equals the store except at the bypass-written key, which stays live and unrecorded). Every step is checked against
`Biz::next` and keeps `biz_inv`; states with an open erasure, an open bypass transaction and a marker all satisfy it.

## 9. Open obligations (D-9 not fully paid; nothing below is proved)

- **Not modelled from D-9's list**: record readers and `verify()` racing a redaction (F-1402, HD-1401); the statement
  *history* (`^IVG.Ledger("stmt")` closed entries) and DropStatements on closed entries; Decision 2 (revision free
  text); retry-key movement to `idemRedacted`; F-1306 (a replay re-applying post-commit properties — Replay changes
  nothing here, as reviewed). These remain explorer-only (core M1, M2, M3).
- The original controls F-1302, F-1303, F-1306 are not re-run in this crate (their level-1 guards are unchanged;
  `proofs/` keeps them).
- Eraser variants (EraseNodes, EraseEdges, EraseAll) and a prefix eraser whose cleanup predicate differs from its row
  predicate (P-D9-4); temporal-only storage (F-C1308 is covered only as the shape `rm ⊄ lv`); lock timeouts; graph-blind
  replay (P-D9-5).
- The receipt: HD-1304's "incomplete" outcome is not modelled; only `theorem_pending_needs_cover` (such a state is not
  settled).
- The side condition is a design requirement on targets; which product targets satisfy it (e.g. `redact(None)` without
  a prefix does not) is by inspection (`cx_unaligned_rm` uses the pin's predicates as read at LedgerRedact.cls:89-178).
- No proof loop occurred; no obligation was partitioned. Correspondence to code (D-2..D-5) is untouched.

## 10. Cost (measured, `RESULTS.json`)

Baseline: wall 5.1 s, Verus 4.6 s, SMT 8.7 s, 20.06 M rlimit over 115 functions; largest function
`theorems::theorem_marker_owned` 3.21 M rlimit (1.0 s), then `progress::lemma_watch_step` 1.81 M,
`witness::witness_bypass_and_redaction` 1.67 M. Per module (rlimit): progress 5.92 M, theorems 4.63 M, witness 3.57 M,
safety 3.34 M, protocol_rl 1.39 M, others < 0.35 M. Each control run: 4.4-5.0 s. About 2.3x `proofs/` (8.6 M) for
27 more functions and a fourth participant; no rlimit was raised, no opaque layout was needed (each operation has its
own lemma over per-key invariants, `key_ok`).

## 11. Trust inventory

This crate: no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). `actors` (`c03f9fa`): none (scanned; verified in the same build without
`--no-cheating`, which is forwarded to this crate only). vstd is Verus's trusted base. Declared empty.

## Premises the pin violates (read before citing any result)

Every guard this model needs is absent at the pin: Start's liveness check is unlocked and reads uncommitted rows
(G-L; F-C1201, live), the eraser takes no head lock (F-1201), no writer serializes with redaction start or with the
eraser (G-B, G-BE; F-C1301), and `redact(None)` without a prefix violates `rm ⊆ lv` (G-P; F-1304, live), as do targets
whose temporal-only edges LiveRows ignores (F-C1308, live). PF-6 is violated live (F-C1307). The product's obligations
stay failed/open as the as-built evidence says.
