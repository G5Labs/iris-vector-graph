# CORE-PROOFS: participant contracts, Protocol2 composition, progress and controls (playbook §3.3)

Crate `experiment/playbook-completion/proofs` (`ivg-core-proofs`), Verus 0.2026.10.04, vstd 0.0.0-2026-09-20-0158,
`actors` at `c03f9fa`. Evidence grade: **proved** (no trusted items in this crate), about **models**: no proof here
connects the ObjectScript or Python at pin `3eaa79cf` to these contracts.

| Gate item (§3.3) | Result | Evidence |
|---|---|---|
| Independent participant contracts (each `Contract` + `SafeContract`, own state only) | Ledger, Store, Redactor | `src/ledger.rs`, `src/store.rs`, `src/redactor.rs` |
| `Protocol2` composition, `step_binds` + `step_enabled` for every operation | two levels: Ledger x Redactor -> RL; RL x Store -> Biz | `src/protocol_rl.rs`, `src/protocol_sys.rs` |
| Implementations refining the participants refine the outer contract and keep its invariants | proved, generic in the implementations | `src/compose.rs`, `src/system.rs` |
| Safety: outer business invariants | inductive (`impl SafeContract for Biz`) + five business theorems | `src/biz.rs` |
| Progress under explicit fairness | `FairWork` + `eventually_drained` | `src/progress.rs` |
| Broken-implementation controls rejected | 4 of 4 rejected in the expected file, each with a proved reachable counterexample | `src/cx_*.rs`, `RESULTS.json` |
| Progress-only control fails only progress | 1 error in `src/progress.rs`; 87/87 other functions verify | `RESULTS.json` |
| Non-vacuity | `step_enabled` at both levels; concrete erase -> redact -> settled execution | `src/witness.rs` |
| Trust inventory | empty (this crate and `actors`) | `RESULTS.json` `trust_inventory` |

Baseline: `cargo verus verify -- --no-cheating`: **88 verified, 0 errors**, Verus 2.9 s, 8.6 M rlimit (registry
`core-proofs-baseline`). Gate: **pass** (`RESULTS.json`, sources SHA-256 `862f8bad...`).

Rerun: `source experiment/playbook-completion/environment.sh; python experiment/playbook-completion/proofs/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600`, after `cargo clean -p`; `--register` registers the runs).

## 1. Participant contracts

Each participant sees only its own state; its labels are the operations it exposes; its operations are the
component's *as built* (what the component permits), and which of them the reviewed design uses, and when, is the
protocols' decision. Each has its own invariant, proved inductive.

| Participant | State (pin mapping) | Labels | Own invariant |
|---|---|---|---|
| **Ledger** | `hist` records `^IVG.Ledger("rec",seq,ord)` (head = length); `idem` bindings; `locked` head lock held across steps; `enabled`; `marker` `^IVG.Ledger("redacting")` with its owner target; `mi,mj,mend` the run's cursor and scan bound kept with the marker (reviewed design D-1, not at the pin); `count` `("redacting","n","records")` and `tally` the records it counts | `Commit` (with BlocksCommit refusal, Ledger.cls:514-518), `Replay` (bound key), `Lock`, `Unlock`, `SetEnabled`, `Mark`, `Batch` (tombstone + cursor; *sets the marker if none*, as built), `Rewind`, `Audit` (*removes whichever marker exists*, as built) | `count == tally.len()`; no marker => `count == 0`; every bound key names a revision |
| **Store** | `rows` content keyed by (graph, id, edge); `stmts` live statement index `^IVG.Ledger("tuple",...)`; `erasing` an open erasure | `Apply` (a changeset's records, or direct writes), `EraseRows` (row deletes), `EraseIndex` (EraseLedgerFor + commit) | no dangling statement entry outside an open erasure (`stmts_ok`) |
| **Redactor** | `procs[p]`: process p in Redact(t) with phase `Opening`/`Batches`/`Final` and its own cursor `(i, j)` and bound `end` (process-local, as at the pin) | `Open`, `Attach{i,j,end}`, `Advance{row_end}`, `ToFinal`, `Finish`, `Stop` | no cursor passes its bound; at the bound, `j == 0` |

Shared vocabulary (`src/vocab.rs`): records `Live(c)` / `Tomb(c)` (ghost content) / `Audit{t,n}`; `replay` of a
history; the statement index a record maintains; targets are arbitrary predicates on keys (`Tgt = spec_fn(Key) -> bool`).

## 2. Protocols (two levels)

`Protocol2` has two participants, so three compose in two levels; level 1's outer contract `RL` is participant A of
level 2. Every protocol step is one atomic transaction (premise P-C01).

**Level 1, `RLP`: Ledger x Redactor -> `RL`** (`src/protocol_rl.rs`). Guard (reviewed design):
- *Start* (HD-1301): under the head lock (`!locked`), ledger enabled, `fresh == (marker is None)`, a resume needs
  `marker == Some(own target)`. A fresh start writes the marker in the same step (`Mark`, cursor at the first record,
  bound at the head); a resume attaches at the marker's cursor.
- *Scan*: under the head lock, process in `Batches` at the marker's cursor (`synced`), `marker == Some(own target)`;
  the ledger's `Batch` tombstones the record under the cursor if it is a live record of the target, and writes the
  cursor back.
- *Final*: under the head lock and the process's own marker, cursor at the bound; `Audit` when it succeeds.

**Level 2, `SysP`: RL x Store -> `Biz`** (`src/protocol_sys.rs`), owning `pend` (targets whose erasure or
redaction is under way). Guard and labels (reviewed design):
- *Erasure* (HD-1201): `EraseRows` takes the ledger head lock (`RL::Lock`), `EraseIndex` releases it (`RL::Unlock`);
  every ledger transaction needs it free, so erasure serializes with commits, replays, starts, scans and finals.
- *Start* and *Final* read store liveness in the same step as their ledger part (HD-1301; FinalInLock re-checks).
- *Replay* (HD-1305): the store takes no step.

Both levels prove `step_binds` (every synchronized step is one outer step) and `step_enabled` (every outer step from a
represented state is realized by the participants; witnesses are the outer target's projections) for **every**
operation: `lemma_p1_binds`, `lemma_p1_enabled`, `lemma_p2_binds`, `lemma_p2_enabled`. `system::sys_step` states the
composed participant contracts in one relation, and `theorem_sys_step_refines` is both levels' `step_binds` at once.

## 3. Outer contract `Biz` and its invariants

**Why not the original L1.** Its labels do not fit: L1's `Finish` has no counts and its `Begin` tombstones every
record at once (no runs, so `step_enabled` for Scan is unprovable); it has no statement index or graph-keyed store;
and its `Write` label is the environment's unrestricted freedom, under which the F-1306 control would pass as a write.
`Biz` is therefore a new outer contract. Because `step_enabled` requires the outer contract to be no more permissive
than the participants on every represented state, `Biz` is at protocol granularity (its state is RL's, the store's and
`pend`; its steps are the reviewed design's transactions, `biz_next`); its business content is in its invariants and
in the theorems below, all proved without reachability assumptions beyond `biz_inv`.

`biz_inv(x)` (`src/biz.rs`), proved inductive (`init_safe`, `lemma_biz_safe`, one lemma per operation):
- `inv_parts`: the three participants' own invariants;
- `inv_lock`: `x.rl.l.locked == (x.st.erasing is Some)`;
- `inv_erase`: an open erasure of `e` has `e` pending and nothing of `e` live;
- `inv_mark`: `marker == Some(t)` ==> `t` pending, **nothing of `t` live**, `cursor_ok(hist, dcur)` (no live record
  of `t` before the marker's cursor or at/after its bound), and every record in the tally is a record of `t`;
- `inv_stmts`: every live edge outside an open erasure has its statement entry (`edges_ok`);
- `inv_replay`: `agree(replay(hist), rows, in_pend(pend))`: replay and store agree on every key outside the pending
  targets.

Business theorems (exact statements in `src/biz.rs`):
- **No tombstone of live content** `theorem_no_tombstone_of_live(x, l, y, i, j)`: `biz_inv(x)`, `biz_next(x, l, y)`,
  record `(i, j)` of `x` is `Live(c)` and in `y` is a `Tomb` ==> `!x.st.rows.contains_key(c.k)` and
  `!y.st.rows.contains_key(c.k)`.
- **Per-target audit counts** `theorem_audit_counts_own_target(x, p, y)`: for a successful Final of process p with
  target t: `marker == Some(t)`, every tally record is a record of t, `count == tally.len()`, and the step appends
  exactly `seq![Audit { t, n: tally.len() }]` when `count > 0` and nothing otherwise; afterwards no marker, count 0.
  With `theorem_tally_counts_own_target` (every tombstone joins the tally of the target that owns the marker).
- **Marker owned by one target** `theorem_marker_owned(x, l, y)`: a set marker is never handed to another target;
  Scan and Final run only with `marker == Some(own target)` and the process at the marker's cursor; a fresh Start
  only with no marker, a resume only with its own.
- **Statement entries match live edges** `theorem_statements_match(x, k)`: `biz_inv(x)`, `k.edge`, k outside any
  open erasure ==> `stmts.contains(k) <==> rows.contains_key(k)`.
- **Replay equals store once settled** `theorem_replay_settled(x)`: `biz_inv(x)` and `pend` empty ==>
  `replay(hist) =~= rows`, no marker, no open erasure.

## 4. Composition and safety for any implementations

`compose::Sys<P, IA, IB>` is the machine of implementations `IA: Refines<P::A>`, `IB: Refines<P::B>` running in
protocol P's synchronized steps (either may also not move, or take hidden steps). `impl Refines<P::Outer> for Sys`
is proved once for every `Protocol2` with an initial condition, by `actors::protocol::theorem_compose` (both move),
`theorem_compose_stutter_b` and `step_binds`. With `Top<IL, IR, IS> = Sys<SysP, Sys<RLP, IL, IR>, IS>` (level 1's
composed machine is the implementation of level 2's participant RL), for **all** `IL: Refines<Ledger>`,
`IR: Refines<Redactor>`, `IS: Refines<Store>` (`src/system.rs`):
- `theorem_implementations_refine`: every step is a Biz step or a stutter; `theorem_implementations_init`;
- `theorem_implementations_safe`: every state of every execution satisfies `biz_inv`
  (`actors::hierarchy::refinement_preserves_safety`);
- `theorem_implementation_steps`: every visible step is a `biz_next` step between invariant states (so each business
  step theorem applies to it); `theorem_implementation_states`: statements match and replay equals store once settled;
- `theorem_levels` / `theorem_levels_init`: any machine refining the composed participant contracts
  (`Spec = Top<Id<Ledger>, Id<Redactor>, Id<Store>>`) refines Biz (`actors::protocol::theorem_trans`);
- `theorem_sys_safe`: every run of `sys_step` from the initial state stays in `biz_inv`.

## 5. Progress under named fairness

`progress::RunProgress` watches the redaction of target t from the moment t is marked. Rank = records and revision
boundaries between the marker's cursor and its bound, plus 1 for the pending final step; 0 once a Final of t
succeeds. `RankedWork::decreases`: every Scan and every successful Final of t lowers it. `FairWork::nonincreasing`: no
step raises it (commits append after the bound, the cursor survives stops, a resume continues from it, the marker of t
cannot be replaced while unfinished).

- `theorem_redaction_completes(s, l, i)`: `infinite_execution::<RunProgress>(s, l)` and
  `productive_fairness::<RunProgress>(s, l)` ==> `exists k >= i. s(k).done` (via `actors::fairness::eventually_drained`).
- `theorem_final_effect`: after a successful Final of t: no marker, no live record of t in the history, nothing of t
  in its replay.
- `theorem_work_available(w, p)`: while the run is unfinished, the ledger enabled and no erasure holding the lock, a
  process of t at the marker's cursor can Scan or go to its final step, a process at its final step can finish
  (**never refused**: nothing of t is live while t is marked), and a process not running can `Open` and resume, and
  is then at the marker's cursor.
- `lemma_watch_step`: `RunProgress`'s preconditions are kept by every Biz step (it restricts no execution that starts
  with t marked).

Environmental premises (they justify `productive_fairness`; none is assumed inside a proof):
- **PF-1** the operator re-runs the redaction after a stop (Redact is re-invoked; HD-1303 "resume the same target").
- **PF-2** the ledger is enabled again and stays enabled long enough (BatchInLock/FinalInLock refuse when disabled).
- **PF-3** every erasure ends (releases the head lock); IRIS contract clause *Lock wait* (a waiter proceeds when the
  holder releases) and *Process stop* (a stopped holder's locks are released).
- **PF-4** a process with an enabled step is eventually scheduled and its transaction commits (IRIS *Locks: deferral*,
  *Nesting*).
- Not a premise here: *commits into the target are refused while marked* is proved (BlocksCommit in the Ledger
  contract, `inv_mark`), and it is what lets the scan bound stay fixed (design element D-2), so commits by other
  tenants cannot prolong a run (the original premise P-1306 is gone).

**Progress-only control** `control_progress_rewind`: a resume rewinds the run's cursor to the first record (the pin's
re-run rescans, `LedgerRedact.cls:213`), changed consistently in RL and level 1. Result: 87 verified, 1 error at
`src/progress.rs:165` (`RunProgress::nonincreasing`, the resume case); every function of every other module verifies
(`safety_still_verifies: true`; registry `core-proofs-progress-rewind`). So the pin's rescanning resume is safe, and
its progress needs the stronger premise that eventually one run is not stopped.

## 6. Broken-implementation controls

Each feature replaces one coordination decision of the reviewed protocol by the pin's behaviour (participants
unchanged). Each must fail in its file, and its **proved counterexample** (`src/cx_*.rs`, compiled only with that
feature) shows, from the initial state, a run of the composed participant contracts (`sys_step`, as the control
changes it) that reaches a business violation; so no control is rejected only on unreachable states and the outer
contract's requirement is necessary, not arbitrary.

| Control (finding) | Change | Rejected at | Proved counterexample (steps; violation) | Registry |
|---|---|---|---|---|
| `control_f1302_unlocked_start` (F-1302) | Start without the head lock and without a marker; Scan runs with no marker, its first tombstone writes it | `protocol_rl.rs:305` `lemma_p1_binds` (RL Start must write the marker), `:309`, `:323` `lemma_p1_enabled` | `counterexample_f1302` (7: commit A, erase A, open, start, commit A again, scan): record (0,0) of A becomes a tombstone while its key is live; the marker is then set while A is live; `!biz_inv` | `core-proofs-f1302-unlocked-start` |
| `control_f1303_other_marker` (F-1303) | Final runs under whatever marker exists | `protocol_rl.rs:305` `lemma_p1_binds` | `counterexample_f1303` (16: two A processes, one B process): A's second process finishes under **B's** marker, writes `Audit{A, 1}` counting B's tombstone, and removes B's marker while B's run is in progress | `core-proofs-f1303-other-marker` |
| `control_f1201_erase_unlocked` (F-1201) | the eraser takes no head lock | `protocol_sys.rs:99`, `:100` `lemma_p2_binds` (Biz erasure takes/releases the lock), `:111` `lemma_p2_enabled` | `counterexample_f1201` (3: erase rows of A, commit an edge of A, statement cleanup): no erasure open, the edge is live, no statement entry; `!biz_inv` | `core-proofs-f1201-erase-unlocked` |
| `control_f1306_replay_reapplies` (F-1306) | a replayed retry re-applies its post-commit properties | `protocol_sys.rs:101` `lemma_p2_binds` (Biz replay changes nothing), `:112` `lemma_p2_enabled` | `counterexample_f1306` (6: commit A with key 9, erase A, open, start, replay 9): A live while marked (its Final can only be refused); `!biz_inv` | `core-proofs-f1306-replay-reapplies` |

Counts per control run: F-1302 87 verified / 2 errors; F-1303 88 / 1; F-1201 87 / 2; F-1306 87 / 2 (each count
includes the verified counterexample). No control passes as a stutter: `step_binds` demands an outer step for every
protocol step, and the outer steps' requirements are exactly those the counterexamples show necessary. These
counterexamples are proved over the models; the same defects were found by the original explorer
(`redaction-as-built-live`, `redaction-as-built-audit`, `erasure-as-built`, `retry-as-built`) and reproduced live
(F-1302, F-1303, F-1306) in the original submission.

## 7. Reviewed-design elements (what the guards encode) and their status at the pin

| Id | Element | Source | At the pin |
|---|---|---|---|
| D-3 | Start checks liveness and writes its marker in one locked step | HD-1301 | no (F-1302, F-1303) |
| D-4 | the eraser holds the head lock from its row deletes to its statement cleanup | HD-1201 | no (F-1201) |
| D-5 | a replayed retry changes nothing | HD-1305 | no (F-1306) |
| D-6 | Final runs only under its own marker | HD-1301 | no (F-1303) |
| D-1 | the run's cursor is kept with the marker; a re-run continues from it | this lane (progress) | no: process-local, rescans (progress-only control) |
| D-2 | the scan bound is the head when the run was marked | this lane; justified by BlocksCommit | no: the pin follows the tail |

## 8. Premises (named; none is an assumption inside a proof)

| Id | Premise | Maps to |
|---|---|---|
| P-C01 | Every protocol step is one atomic transaction holding `^IVG.Ledger("head")` (commit, replay, start, batch record, final), or, for the erasure, two transactions' worth of one open transaction; a stopped process loses only its own state | IRIS contract clauses *Nesting*, *Locks: deferral*, *Process stop*, *Lock wait* (`iris-contract/CONTRACT.md`); original P-0001; live `killed_mid_batch`, `killed_at_random` (original `native/scenarios.py`) |
| P-C02 | Every write to the modelled content goes through a ledger commit or an erasure (no ledger-bypassing writes; a first commit's post-commit properties are outside the model) | HD-1103 (strict mode is client-side only), HD-1105; not enforced by the product: a bypass write makes replay and store diverge (explorer `Bypass`) |
| P-C03 | Target membership is a property of the replay key (separability); one predicate stands for the Eraser's SQL, `LiveRows` and `Matches` | original P-1301, P-1310 (open; Q3 models the three predicates) |
| P-C04 | An erasure is not rolled back between its two steps (no abort modelled) | HD-1201 second question (dirty reads of an open erasure) stays open here |
| PF-1..PF-4 | progress premises (section 5) | as listed there |

## 9. Proof cost (measured, `RESULTS.json`)

Baseline: Verus total 3.1 s, SMT 3.9 s (9 threads), 8.61 M rlimit over 88 functions; largest function
`witness::witness_erase_then_redact` 2.02 M rlimit (0.9 s); largest proof lemma `progress::theorem_work_available`
0.75 M. Per module (rlimit): biz 2.39 M, witness 2.02 M, progress 1.95 M, protocol_rl 1.33 M, protocol_sys 0.31 M,
vocab 0.21 M, system 0.17 M, redactor 0.09 M, ledger 0.08 M, store 0.03 M, compose 0.02 M. Each control run: 2.7-3.0 s.
The cost stayed near 3 s while the crate grew from 63 to 88 functions; the slowest function takes 0.9 s against
Verus's default limit (rlimit 10, about 10 s); no rlimit was raised. The per-object opaque layout was therefore **not** applied: each operation already has its own lemma
over named invariant conjuncts, and the cost does not grow with the number of operations. Revisit if Q3's richer
models (three targeting predicates, statement history) are added to this crate.

## 10. Trust inventory

This crate: no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). `actors` (`c03f9fa`): none of these (scanned; it is verified in the same
build, but `--no-cheating` is forwarded to this crate only, because vstd's own admits would otherwise fail). vstd is
Verus's trusted base. Gate status: **declared empty**.

## 11. What is NOT proved

- **No proof connects the ObjectScript (or the Python client) to these contracts.** That a production trace is an
  execution of the participant contracts is trace conformance (journal oracle, AUDITCORE), done elsewhere (Q5);
  `system::sys_step`, `theorem_levels` and `theorem_implementation_steps` are the plug-in points for it.
- The three targeting rules are one predicate (P-C03): graph-blind node records (F-1304, F-1305) are not expressible.
- The statement *history* (`^IVG.Ledger("stmt")` closed entries) and `DropStatements` are not modelled; only the
  live index (tuple entries) is.
- Decision 2 (free text) and the retry-key movement to `idemRedacted` are not in this crate (the original L2 proved
  them); a replay of a redacted key is modelled only as "changes nothing".
- Erasure rollback and a Start reading an open erasure's uncommitted deletes (P-C04); ledger-bypassing writes (P-C02).
- Record readers and `verify()` coherence (F-1402, HD-1401) are not modelled.
- Progress is for a marked run under `productive_fairness`; the premises PF-1..PF-4 are not discharged against IRIS
  scheduling. "From every state a settled state is reachable" (the explorer's AG EF) is not proved here.
- The per-target audit count is proved as a step property plus the tally invariant, not as a history-wide invariant
  over all past audit revisions.
- The reviewed design is a working assumption (HD-1201, HD-1301, HD-1305 are `Assumption` in `decisions.md`), and
  D-1, D-2 are this lane's design choices; none is a maintainer decision.
