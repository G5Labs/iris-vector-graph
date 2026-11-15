# Independent review, sixth pass: the R5 conditions on candidate `76fb07ce`

Reviewer: independent reviewer lane (read-only), the same one that wrote the fifth pass.
- No IRIS connection, no Verus or explorer run, no commit.
- I wrote only this file, `review/review-6/` and `$RUN_DIR/review-6/`.
- `PC/` = `experiment/playbook-completion/`.

**Scope.**
- `25ba22dd..76fb07ce`: the fixes, with `review/RESPONSE-5.md` mapping each condition.
- `7d054f25`: registration of the fresh-checkout fast gate.

**What I checked.**
- The product scope passes, nothing outside `PC/` changed, and the product's `.gitignore` is unchanged.
- I classified every file changed since `25ba22dd` (233 files):
  - account text, findings and errata;
  - matrix inputs;
  - the force-added data files;
  - `tools/ignored_check.py`, `tools/status_numbers.py` and two new fast steps in `verify.sh`;
  - five run records;
  - this reviewer's own review-5 files, committed byte-identical (the registered SHA `88c83d93…` matches).
- No proof or model crate source, live harness, trace or contract source changed.
- `check_registry.py` reports 1,424 runs and 0 problems.

## Decision: **sign-off** of the account for `76fb07ce`

**Scope of the sign-off.** It covers the spec against intent and the accuracy of the account, as of `76fb07ce` with its
gates `verify-clean-25ba22dd` and `verify-fast-export-76fb07ce-r2`. It does not cover the product.

**State of the conditions.**
- The six blocking conditions are met. For R5-02 this holds in the account's primary documents, with two leftovers
  graded S4 below.
- The gate is now reproducible from the commit.
- What remains is wording in a findings note, a generated reflection section and an incident record. None of it changes
  a status, a product label, a count or a gate.

**What the product still fails.**
- It fails most obligations the evidence touches.
- These gates stay open for the reasons the account states:
  - statement, handler, lock-plan and composition proofs: no verifier;
  - editions, Enterprise, multi-node, FHIR: unavailable;
  - product-code mutation: operator question O-2;
  - every finding's fix or decision: maintainers;
  - the 20-minute single-gate target: `proofs-mech`, 2,230 s.
- The IVG262CAP reading of O-1 still awaits the operator's confirmation and is recorded as such.

## R5 conditions

| Condition | Evidence at `76fb07ce` / `7d054f25` | Verdict |
|---|---|---|
| R5-01 gate not reproducible; cited files uncommitted | All five ignored paths are committed (`contract-2/coverage.json`, `semantics/data/`, 52 files under `live/breadth-a/results/`, 132 under `models/breadth-b/results/`, the review-5 log). The committed `coverage.json` has SHA `dfc0dffb…`, the same file the `25ba22dd` gate read. `git status --ignored` shows nothing under `PC/` except caches. New fast steps `ignored-files` and `ignored-selftest` (`tools/ignored_check.py`; a tracked force-added file is not reported, a seeded ignored one is). `verify-fast-export-76fb07ce-r2`: 40/40 exit 0 in 46 s. Its `inputs.txt` shows `candidate_commit 76fb07ce`, `worktree_status_lines 0` and experiment tree `26ea4a7b` (= `76fb07ce:PC`). Every step log re-hashes. `ignored-files` reports 0; `closure-check` and `ontology-gate` pass. The failed first attempt is kept (`verify-fast-export-76fb07ce`, ontology gate only) | **met** |
| R5-02 durability statements; incident record | `TRUST.md:42` (1/1 and 3/3 lost under 0, 0/3 under 1, "evidence, not proof", restored); `STATUS.md:46-47, :102` ("evidence, not proof"); the 3.8-test-reflection cell; `incidents/SYNCHCOMMIT-WORLDS.md` (times, BEFORE/AFTER, the kills, restarts and restore) | **met in the primary documents**. Leftovers R6-01, R6-02 (S4) |
| R5-03 F-C1350 counterexample; G-BM "proved" | `proofs-d9c/PROOFS.md:65` now says "F-C1350's outcome under the reviewed, locked Start ... this counterexample places the write after the marker". `PROOF-DEBT.md` D-9, `STATUS.md:32` and `:91` call G-BM "an assumed reviewed guard". "live schedule" and "G-BM, proved" occur nowhere | **met** |
| R5-04 review and operator state | The 3.8-review cell cites reviews 1-5 and O-1's resolution. `QUEUE.md:41, :49` are done; `:61-63` record O-1 as resolved and the IVG262CAP extension as awaiting confirmation. `O-1-FIXTURES.md:43-45` records 111 product compiles in AUDITC as product operation, not O-1 | **met** |
| R5-05 two STATUS figures | Both are generated (`tools/status_numbers.py`, checked in the gate). Write sets: census 185 (finding 64, guard 9, lemma 105, open 7) and breadth-a 566 (finding 190, guard 20, lemma 352, open 4), equal to the gate's `writesets-check` log. IRIS features over all 19 modules: 784 / 324 / 1,237 / 0 | **met** |
| R5-06 IVG262CAP | `CONVENTIONS.md:46-50` and `O-1-FIXTURES.md` ("Orchestrator's extension of O-1") say it is the orchestrator's reading and ask the operator to confirm. 3.6-capacity/01 carries `depends_on`. `o1-cap-inventory` (log re-hashes): 222 classes = 55 pin-equal + 8 v4.5.1-only + 11 + 148 generated. Its compare section is labelled "FC" because the script reuses that sub-directory name; the export is IVG262CAP's | **met**. One S4 wording point (R6-03) |
| R5-07 F-C1301 | `observed` opens "First shown in the core model ... and reproduced live since steer 7" | **met** |
| R5-08 TSTART | TRUST, PROOF-DEBT D-13 and `proofs-pa3/PROOFS.md` read "has passed TSTART but not executed its DELETE". The comment in `adj_l2.rs` is unchanged because the registered sources hash covers it; that is acceptable | **met** |
| R5-09 errata | 41 added (89 in total). The texts I read for `env2-coverage-selftest`, `live-licence-world`, `ws-live-ba-explicit-survives`, `st-live-susp-loader-clear`, the two d9c records and the general "errors count failing functions" entry are accurate. 23 `proofs-d1d` errata; the d1c/d1e/d1f recheck counts; F-C1795 corrected | **met** |
| R5-10 R4-14/15 remainders | "25+ undeclared writers" is gone (0 cells). The 5 remaining "[proofs-pa3]" tags sit on module 04, 11 and 12 cells that do cite `proofs-pa3`. Declared not done: the d9b/pa3 runner summaries, `evidence_file` grading, and the older "stated fails" bases | **partly met, as declared** (S4) |
| R5-11 small text | Met: the TRUST provenance sentence (the incident file names the reruns); F-C0350 → F-C0349; F-C1018 no longer cites spec 230; F-C1743's notes are consistent; F-C1306 names LedgerRevision/LedgerStats/Meta; F-C1795's range is noted. Not done: the `LANES.md:4` fragment, and the 363 s restart (R6-02) | **mostly met** (S4) |

## Is the R5-01 reproduction adequate?

**Yes.**
- **The checkout is complete.** `git worktree add --detach` gives a checkout of exactly the commit's tracked content.
  Files ignored or untracked in the main worktree are absent from it, which is what R5-01 required.
- **The submodule belongs to the pin.** `vendor/opencypher` is part of the product pin (gitlink `677cbafa` at
  `3eaa79cf` and at `76fb07ce`). Initializing it at that gitlink from the local module store, with no network, completes
  the checkout of the pinned tree. It adds nothing outside the pin.
- **One deviation from my R5 wording, accepted.** The run used `--fast` without `--clean`. In fast mode the only build is
  the iris-contract binary into the shared target. That affects build cleanliness, not input reproducibility, and its
  sources are unchanged since the clean build in `verify-clean-25ba22dd`.
- **The full and live steps carry over.** Since `25ba22dd`, no crate, model, harness, trace or contract source changed.
  The added `models/breadth-b/results/` files are deleted from the copy that `verify.sh` builds. `coverage.json` is
  byte-identical to the file the clean gate read.

## Is anything in RESPONSE-5 itself inaccurate?

Three small points; none affects the decision.
- **R6-01 (S4).** The R5-02 row says F-C1102's notes now "state the three trials per setting without claiming
  sufficiency".
  - They do, in an appended sentence.
  - Earlier in the same notes, "With SynchCommit=1 the result may differ; not tested here" and "(live-crash-world-r2,
    one trial; SynchCommit=1 untested)" remain (`findings/audit/11-orchestrator.json`, F-C1102).
  - Its `evidence` still lists only `live-crash-world-r2`.
  - Fix: delete the two stale clauses and add `live-crash-repeat-sc0` and `-sc1` to its evidence.
- **R6-02 (S4).** The same row says TEST-REFLECTION.md is regenerated.
  - It is, but section F still lists "The crash world with `SynchCommit=1` (needs the container reconfigured; the audit
    may not reconfigure it)". That text is hard-coded at `reflection/tools/build_test_reflection.py:231`.
  - Its D-5 row still names SynchCommit=1 as uncovered.
  - `incidents/SYNCHCOMMIT-WORLDS.md` does not mention the first sc0 restart that never reported healthy (363 s,
    `$RUN_DIR/crash-repeat/sc0/results.json`), which R5-02 asked for.
- **R6-03 (S4).** The R5-06 row and `O-1-FIXTURES.md` say IVG262CAP has "the same composition as IVG262FC1306". The
  groups are the same, but the counts differ (55/8/11/148 against 54/8/11/178). Say "the same kinds of classes".

Not blocking: the R5-10 items declared not done, and `LANES.md:4`.

**Needs the operator.** Confirmation of the IVG262CAP reading of O-1 (recorded, with `depends_on` on
3.6-capacity/01). O-2 is unchanged.

**Needs a maintainer.** Unchanged from the fifth pass.
