# Independent review 6, addendum: what changed after the sign-off of `76fb07ce`

Reviewer: independent reviewer lane (read-only), the same one that wrote passes 5 and 6.
- **Scope:** `git log 76fb07ce..4e4a4d88` (14 commits). `4e4a4d88` changes only LANES and QUEUE rows, which I checked. The new uncommitted lanes `proofs-sys/` and `proofs-env2/` are out of scope.
- **Rules followed:** no IRIS connection, no Verus or explorer run, no commit.
- **Files written:** only this file, `review/review-6/` and `$RUN_DIR/review-6*/`.
- **Product scope** passes; nothing outside `PC/` changed (`PC/` = `experiment/playbook-completion/`).
- **Who checked what:** a read-only fork of this reviewer read proofs-env in depth (item 3). I re-checked every point I
  raise below.
- **Registry:** every new run record's log re-hashes (`check_registry.py`: 0 problems).

## Decision

**My sign-off of the account extends to `4e4a4d88`** (`8dc612d1` plus a queue checkpoint).
- No new blocking condition.
- A-01..A-06 below are S4: wording, attribution and two latent weaknesses of the merge-gate tool. None changes a
  status, a product label, a count or a gate result.
- The sign-off still covers the specification against intent and the accuracy of the account, not the product.

## 1. R6-01..R6-03 (`f4383333`): met

- **R6-01.** F-C1102's notes no longer say SynchCommit=1 is untested, and its evidence lists `live-crash-world-r2`,
  `live-crash-repeat-sc0` and `-sc1`. A trivial leftover: a missing space ("container).Environment").
- **R6-02.** The generator line is fixed (`build_test_reflection.py`). TEST-REFLECTION section F now reads "More crash
  trials ... under `SynchCommit=1` (3 trials ran ...; evidence, not proof)", and the D-5 row no longer lists
  SynchCommit=1. `incidents/SYNCHCOMMIT-WORLDS.md:14-16` records the 363.2 s first restart.
- **R6-03.** `O-1-FIXTURES.md` gives the counts (55/8/11/148 against 54/8/11/178), and an erratum covers
  `o1-cap-inventory`.
- `review/REVIEW-6.md` is committed byte-identical to the registered log.

**Correction to my own sixth pass (A-05).** I marked R5-09 "met". Its last item was not done: the eight records whose
details exist only in unregistered side files have no errata. They are `st-live-cap-upgrade-build`, `-load`,
`tr-replay-01-r2`, `tr-replay-09-r2`, `ws-check-r2`, `ws-check-r4`, `rx-dec-live-18` and `status-numbers-check`.

## 2. O-1 applied to IVG262CAP (`920996d7`): exact

`incidents/O-1-FIXTURES.md` "IVG262CAP under O-1" records:
- **Version:** v4.5.1 = `f60b20c2`.
- **Fixture:** `build_release_namespace.build('v4.5.1','IVG262CAP')`, unmodified at the pin. At the pin it imports
  `tcp_setup` and calls `make_scratch_namespace.recreate`.
- **Helper classes:** `IVGDev.Setup` and `IVGDev.Run` in `%SYS`. At the pin, `tcp_setup.ensure_helper` compiles them only
  if absent or different. They were present and equal to the pin's files.
- **Namespace and database.**
- **Effects:**
  - 165 classes after the build;
  - 110,058 nodes, 230,054 edges, 320,064 properties, 2,002 vectors and 51 revisions, all present in the
    `st-live-cap-upgrade-load` log;
  - the pin's upgrade;
  - 222 classes afterwards (`o1-cap-inventory`).
- **Use:** 3.6-capacity/01.

The operator's text is quoted, and the earlier history is kept.

**The stale confirmation wording is gone.** A search of HEAD for "awaiting / awaits / requested confirmation", "asks
the operator to confirm" and "operator confirmation" finds nothing outside the historical review files. The 3.6-capacity/01
cell's `depends_on` now names the operator's application. `RESPONSE-5.md:13` keeps its historical sentence, with the
22:42 update at `:20`.

One S4 point (A-05): "absent beforehand (checked)" rests on a check that is not in the registered build log.

## 3. D-7, proofs-env (`737c3930` and later)

**"D-7 paid at model level for the contract's Verus subset" is accurate.** Three qualifications that the D-7 row should
state (A-04):
- **Spec to exec model: by proof.** `e_step` and `e_run` are proved equal to the step function (`exec.rs:1490-1492`,
  `:1755-1759`). The trust inventory is empty, and baseline and recheck both report 305 verified, 0 errors.
- **Spec to the executable contract: by differential testing, not proof.**
  - `proofs-env-differential-r3`: 11 recorded rounds, 1,769 in-subset case runs, 0 disagreements, every observation
    inside the permitted set;
  - `proofs-env-mutants-r3`: 29 of 29 Verus-model mutants killed by observations.
- **Spec to the other crates' premises: by restatement.**
  - No proof crate imports `proofs-env`.
  - Each premise is re-formalized as a theorem in `src/premises.rs`. Faithfulness to how each crate uses the premise is
    by inspection.
  - The head-lock refinement is proved per step, and the trace statement follows by induction outside Verus
    (`PROOFS.md:118-123`).

**Premise verdicts: right as stated.**
- `premise_map.json`: 79 rows, made of 12 proved, 10 in part, 8 under the product discipline, 3 shown false,
  1 permitted-not-implied, 9 outside and 36 progress.
- My fork checked 14 theorems against the spec. They include every shown-false and not-implied row (P-D9-2's Freedom,
  P-U2/P-C5, Txn.cls:8) and P-C04. Each is a universal theorem with a concrete satisfying instance in `cx.rs`.
- The 17 controls each fail only at their `LOCATE` lines, and their counterexamples verify.
- The two contract rounds test what they claim:
  - `env-estop-gap`: a stop at `$TLEVEL` 2 rolls back every level;
  - `env-dml-single`: an empty DELETE or UPDATE leaves `$TLEVEL` 0, and a failing single-row INSERT gives -119 with
    `$TLEVEL` 1;
  - both report 0 outside the contract;
  - the contract's model and oracle are unchanged; only two case files were added.
- One label inconsistency: `PROOFS.md:141` labels P-D9-2's second half "permitted-not-implied", while the map counts it
  under P-D9-2's in-part verdict. The totals are consistent.

**Model presented as product: none.**
- `PROOFS.md:3-7` disclaims product claims.
- The head-lock results are stated under the hypothesis `disc`, which the pin violates (F-1201).
- The 3.2-library cell's product label is `n/a`, and 3.6-closure stays `fails`.
- No closure condition was upgraded on the strength of a proof.

**Attribution defect (A-03).** `reflection/CLOSURE.md:205-210` lists `proof-premise:proofs-env:PF-1..PF-6`. These are
copies of the proofs/ and proofs-d9* progress premises, created by the extractor's rule that "every PF-n named anywhere in
the file is a premise of that crate" (`reflection/tools/check_premise_map.py:11-12`). As a result, CLOSURE has 79
proof-premise rows. "Every proof-premise condition of CLOSURE.md (72)" (`proofs-env/PROOFS.md:12`) and PROOF-DEBT D-7's
"every proof-premise condition of CLOSURE.md mapped" are stale: 7 rows are unmapped, namely ENV-4 and the six copies.

**Evidence.** 48 records (34 control and recheck records, 2 baselines, 4 differential, 4 mutant, 2 premise-map,
env-estop-gap, env-dml-single). All hashes match: 46 MATCH, 2 PARTIAL. `proofs-env-premise-map` and `-r2` describe
seeded faults and citations that are not in their logs (A-06).

## 4. The 20-minute gate (operator, 22:45 UTC; `4f7da97d`..`bb1f23fc`)

**The interpretation is faithful.**
- **What the playbook says (`verification-playbook.txt:479-489`):**
  - "A merge gate is a single build with a hard 20-minute timeout".
  - It blocks on "real-database tests ... of the touched slices plus a fixed canary slice set; pipeline `--check`; the
    trust inventory; Verus on the changed crates only".
  - "Full controls and every crate run in the periodic full verification".
  - Results are cached by input hash, and lines 495-498 tier the gates the same way.
- **How the account matches it:**
  - The 5a-gate-20min cell, STATUS (lines 21-24 and the §5 row) and PROOF-DEBT D-14 now say exactly this.
  - `proofs-mech`'s 37-minute gate with 120 controls belongs to the periodic tier.

**The merge gate is a faithful native-IRIS counterpart.**
- **Hard envelope:** `verify.sh` re-execs itself under `timeout --kill-after=10 1200`, so hitting it exits 124. Since
  `10f1a103`, `verify.sh` exits non-zero on any failed step.
  - The first failing run, `4f7da97d`, still exited 0; it is kept and its record says so.
- **Spec and trust:** the 40 fast steps run unchanged, and the trust scan covers all 13 crates.
- **Verus on changed crates only:** a real baseline of `proofs-env` (305 verified, 0 errors) with `--no-cheating`, in
  12-50 s.
- **Cache by input hash:** for each of the 12 unchanged crates, the gate recomputes the sources hash, checks it equals
  `RESULTS.json`, checks git shows no change since the base, and checks the base `verify-clean-25ba22dd` step exited 0.
  The log shows all 12 hashes.
- **Fixed canaries:**
  - contract named cases (96 cases, 0 outside, 42/42 mutants);
  - ledger trace conformance;
  - F-1201 (2 trials).
- **Touched slices:** each touched module's trace replay is captured and checked live in AUDITE, into a private
  `RUN_DIR`. For an observation-only audit with the product pinned, "touched" means modules whose verification
  artifacts changed since the base. That is a reasonable counterpart.
- **Runs:**
  - `verify-merge-20e3b336` and `-bb1f23fc`: 51/51 steps, 215 s and 217 s of step time;
  - the two failing runs are kept and show the gate blocks.

**Closing 5a-gate-20min is justified.** The gate's text ("one gate = one build on one machine within 20 minutes") is
met by a gate that ran and passed inside an enforced envelope.

**Weaknesses (S4).**
- **A-01: a Verus time or resource limit is recorded as a pass.**
  - `tools/merge_gate.py:153-155` turns a time or resource limit into exit 0, which the summary reads as passed.
  - Nothing records the debt. The playbook says such a result is "recorded as proof debt with its location, not a gate
    failure", and "Inconclusive ... is never a pass".
  - Fix: record it as inconclusive in the summary and write the debt row.
  - A related gap: `cache_check` would accept an empty recomputed hash, because `want.startswith('')` is true when a
    runner lacks `sources_sha256`. All 13 runners have it today. The self-test covers neither path.
- **A-02: the slice selection misses shared changes.**
  - Changes to shared harnesses (`traces/`, `iris-contract/`, live probes) or to lane-level files (`writesets/`,
    `structural/`, `refusals/`) mark no module. Only the canaries and the spec checks cover them. State this in the
    5a-gate-20min cell.
  - `proofs-env` has not yet been through a periodic full verification; the base `25ba22dd` predates it. Its lane
    baseline, controls and recheck stand meanwhile. Say so where STATUS cites `verify-clean-25ba22dd`.

## Conditions (all S4, not blocking)

- **A-01, A-02:** the merge-gate tool and its stated limits (section 4).
- **A-03:** fix the extractor so that only premise-table rows count as a crate's premises, regenerate CLOSURE, and
  correct "(72)" and "every ... mapped" (`proofs-env/PROOFS.md:12`, PROOF-DEBT D-7).
- **A-04:** in PROOF-DEBT D-7, say how each part is linked:
  - the spec is linked to the executable contract by differential testing;
  - it is linked to the other crates' premises by restatement, checked by inspection;
  - the head-lock refinement is per step.
- **A-05:** errata or pinned side files for the eight records in section 1, including the IVG262CAP "absent
  beforehand" check.
- **A-06:** errata for `proofs-env-premise-map` and `-r2`, and the `PROOFS.md:141` label.
