# State machines, model checks and proofs

Two layers, kept apart on purpose:

- **Model checks** (`model/`, Rust, `G5Labs/actors` explorer at `c03f9fa`): executable machines explored breadth-first over every
  reachable state **within declared bounds**. A pass is bounded evidence; a violation is a concrete shortest trace.
- **Proofs** (`proofs/`, Verus `0.2026.10.04`, `actors` at `c03f9fa`): the L1 business machine and the L2 algorithmic machine of
  the redaction slice, for all sizes, about the **models**. The code at the pin is tied to them by the controls (the pin's
  behaviour is a control the proof rejects), by the explorer's as-built designs, and by live traces, never by a proof over
  ObjectScript.

Final run: `$RUN_DIR/final/mc.log`, `final/mc-summary.json`, `final/verus.log`; registered in `evidence/runs.json`.

## Model checks (11 of 11 met their expectation)

Each machine exists in the design at the pin (`as-built`, expected to violate: that is the finding) and in a reviewed design
that changes one thing (expected to pass every state within bounds).

| Check | Machine and world | Bounds | Expectation | Result |
|---|---|---|---|---|
| `redaction-as-built-live` | Redaction core: keys a1, a2 (tenant A), b1 (tenant B); 4 changesets incl. one spanning A and B; erasure of either tenant; one ledger-bypassing write; 2 redacting processes; Start / Scan (one record) / Final / Stop | ≤ 6 revisions, ≤ 3 starts, ≤ 3 erasures | violation "no tombstone of live content" | Met: 3 steps (Start A, Commit into A, Scan) — F-1302 |
| `redaction-as-built-audit` | same | same | violation "each audit counts exactly its own target's tombstones" | Met: 7 steps; the second run's Final counts A's tombstone and removes A's marker — F-1303 |
| `redaction-reviewed` | same, reviewed Start (check and marker in one locked step) | same | no violation of any property (Decision 2, retry keys, replay equals store once settled, no tombstone of live content, per-target audit counts; AG EF "settled") | Met: 11,351,753 states, 34,915,176 transitions, depth 51, exhaustive within bounds, 78 s |
| `refinement-as-built` | `explorer::refinement::audit` of the as-built core against an executable L1 (twin of `proofs/src/l1.rs`) through the Verus abstraction | same | a violation | Met: 3 steps (the F-1302 trace) |
| `refinement-reviewed` | same, reviewed core | same | no violation: every step is an L1 step or a stutter; L1 invariants hold on every abstract state | Met: 11,351,753 states, exhaustive within bounds, 116 s, 10.4 GB peak |
| `erasure-as-built` | EraseGraph (delete rows, kill statement entries, commit) against a ledger process committing an edge create or delete; row locks; no head lock in the eraser | ≤ 2 commits | violation "statements of G equal the edges of G whenever no transaction is open" | Met: 5 steps (E deletes rows, P commits a new edge, E kills its statement) — F-1201 |
| `erasure-reviewed` | same, eraser holds the head lock | same | no violation; AG EF quiescent | Met: 23 states |
| `readers-as-built` | a record reader (marker check, then read) racing a redaction | ≤ 2 starts | violation "an accepted view never shows a redaction half done" | Met: 4 steps — F-1402 |
| `readers-reviewed` | reader re-checks marker and epoch after reading | same | no violation | Met: 54 states |
| `retry-as-built` | commit with a post-commit property, erasure, replayed retry, redaction | ≤ 2 retries, ≤ 2 erasures | violation "after erasure only a recorded commit makes the tenant's content live again" | Met: 3 steps (Commit, Erase, Retry) — F-1306 |
| `retry-reviewed` | replay applies no post-commit properties | same | no violation | Met: 10 states |

Model assumptions (each also a named premise): steps are transactions (P-0001); records are separable by replay key (P-1301);
a SQL delete waits for a row another transaction holds (P-1201); the reader takes no lock (as the code). The bypass write is
the environment's freedom (engine, SQL, Cypher, bulk paths write outside the ledger).

## Proofs (Verus, `--no-cheating`, no trusted items)

`cargo verus verify -- --no-cheating` in `proofs/`: **53 verified, 0 errors, 2.6 s**. Trust inventory: no `assume`, `admit`,
`external_body` or uninterpreted functions (a redaction target is an arbitrary predicate `spec_fn(Id) -> bool`).

| Layer | File | Main results |
|---|---|---|
| Replay model | `src/model.rs` | `lemma_replay_tomb` (replay of a tombstoned history = replay outside the target), `theorem_erasure_alone_diverges`, `theorem_commit_keeps_except`, `theorem_redaction_restores`, `theorem_audit_changes_nothing` |
| L1 business machine | `src/l1.rs` | `SafeContract` for L1 (invariants: shape, isolation, Decision 2, retry keys, marker); `theorem_begin_spares_live`, `theorem_isolation`, `theorem_retry_refused`, `theorem_erase_then_redact`, `theorem_commit_between` |
| L2 machine (reviewed design) | `src/l2.rs` | `Refines<L1>` for every step; `theorem_inv2_inductive`; `theorem_l2_satisfies_l1` (via `actors::hierarchy::refinement_preserves_safety`: every L2 execution satisfies L1's invariants) |
| Progress | `src/progress.rs` | `RankedWork` for one run; `theorem_run_bounded` (an uninterrupted run takes at most `rank0` steps); `theorem_run_can_step` |

Broken-implementation controls (each a Cargo feature; each must fail with an error located in `src/l2.rs`):

| Control | What it breaks | Result |
|---|---|---|
| `control_unmarked_start` | unlocked check, marker at the first tombstone (with `control_other_target`: the pin's Redact) | rejected (3 errors in `l2.rs`) |
| `control_other_target` | a batch tombstones its target under another target's marker | rejected (2) |
| `control_meta_every` | free text cleared only when every record is redacted (spec FR-004 wording) | rejected (2) |
| `control_keep_retry_key` | a redacted revision's retry key stays bound | rejected (2) |
| `control_no_final_check` | the final step does not re-check liveness | rejected (2; one also in `progress.rs`) |
| `control_no_commit_block` | a commit into the marked target is not refused | rejected (1) |

Not in the proofs (several raised by the independent review, `REVIEW.md`): one target predicate stands for three scopes in
the code (the Eraser's SQL, `LiveRows`, `Matches`; P-1310), so F-1304 and F-1305 cannot be expressed; erasure is one atomic
step, so a liveness check that reads an erasure's uncommitted deletes is not modelled (P-1311); the two opening reads of
`Redact` are one step; L2's audit has no counts (`counted` is a flag) and its Final requires the run's own marker, while the
code's Final also runs with no marker or another target's; the idempotent replay path (`Ledger.cls:457-462`) and the
statement and tuple maps (`DropStatements`) are absent; unattributed qualifier records are absent; batch atomicity is a
premise (P-0001), not a theorem. The explorer models audit counts and the counters across resumed runs, but its Final with no
marker skips the liveness re-check. IRIS SQL isolation and the ObjectScript itself are not modelled. The live scenarios
check the statement maps after every step (L2 invariant "live statement without its row").

## How to rerun

`bash experiment/playbook-uplift/tools/check_all.sh` (offline) or with `--live` (also the live scenarios and the upstream
Community suite). One model check: `cargo run --release -- --only <check id>` in `model/`.
