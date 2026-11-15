# Independent review, fifth pass (playbook §3.8, §5c)

Reviewer: independent reviewer lane (read-only). I did not produce the work under review.
- Product pin `3eaa79cf` (tree `b098a6f4`) is unchanged: `check-product-scope.sh` passes.
- The original submission's tree is `becf53a4`, both at `9c3719c1` and at the candidate.
- Since `f497a387`, nothing outside `experiment/playbook-completion/` changed, and no `.cls`, patch or diff file was added.
- I made no IRIS connection, ran no Verus or explorer crate, and committed nothing.
- I wrote only this file, `review/review-5/` and `$RUN_DIR/review-5/`.

`PC/` = `experiment/playbook-completion/`.

**Scope.** Candidate `25ba22dd`, that is the 35 commits `f497a387..25ba22dd` (695 files; 299 new run records, none
modified or removed). They contain:
- the orchestrator's answers to R4-01..R4-15;
- operator clarification O-1;
- the crash, licence and least-privilege worlds;
- the clean live gate that the orchestrator ran on this candidate during the review (`$RUN_DIR/verify/20261114T203920Z`).

**Method.**
- **Done by me:** the re-hash of all 299 logs; the R4 conditions about the account and the matrix; the diff of matrix
  cells since `f497a387`; the O-1 and log-provenance records; the gate.
- **Read in depth by four read-only forks of this reviewer:**
  - (a) `proofs-d9c` and `proofs-mech`;
  - (b) semantics, contract-2, ontology-2 and reflection;
  - (c) the live lanes (writesets, structural, trace-replay, refusals, product-gates, orchestrator, operator) and the
    crash, licence and least-privilege worlds;
  - (d) the new and changed findings.
- **Re-checked by me:** every fork result used below as a condition, against the log, the source at the pin, or a
  clean `git archive` export.
- **Files:** scripts and data in `review/review-5/`, raw outputs in `$RUN_DIR/review-5/`.

## Decision: **no sign-off** for `25ba22dd`; the remaining conditions are text and commit fixes

**What holds.**
- The fourth pass's two S2 conditions are met:
  - R4-01: `proofs-d9c`'s no-tombstone theorem now covers content of any provenance under the reviewed guard G-BM;
  - R4-02: WS-OBL-093 rests on a committed-delete rerun, and the matrix builder's failed-run rule is pair-specific.
- R4-03..R4-08 and R4-10..R4-12 are met.
- O-1 is resolved by the operator and correctly attributed for F-C1306 and WS-OBL-066.
- The six superseded proof logs stay superseded; they are not relabelled.
- All 299 new logs re-hash: 273 records match their text, 25 are partial (detail beyond the log) and 1 is a count
  mismatch. No record misstates a result's direction.
- No text presents a model result as a product result, and I found no product change in disguise.
- The clean live gate on the candidate ran 73 steps, all exit 0 (`verify-clean-25ba22dd`).

**What blocks the account's sign-off.** All of these are fixable without IRIS or Verus.
- **R5-01 (S3), and with it the remainder of R4-09: the committed tree does not reproduce its own gate.** The closure
  check fails on a clean checkout, because `contract-2/coverage.json`, which 18 closed cells cite, is git-ignored and
  was never committed. `worktree_status_lines` cannot see ignored files.
- **R5-02..R5-05 (S3, and S4 for R5-05): account statements that are now false.**
  - TRUST and F-C1102 say SynchCommit=1 is untested, although it was tested 3 times; STATUS calls it "shown
    sufficient".
  - STATUS says G-BM is "proved", and the F-C1350 control is said to follow the live schedule.
  - The 3.8-review cell, QUEUE and the O-1 record misstate the review and operator state.
  - Two headline STATUS figures are wrong.
- **R5-06 (S3): a second O-1 namespace (`IVG262CAP`)** is attributed to the operator's clarification without saying it
  is the orchestrator's extension of it.
- **R4-13 is partly met:** F-C1301 still opens "Model only" (R5-07, S4).

R5-07..R5-11 are not blocking.

## 1. Fourth-pass conditions

| Condition | Checked against | Verdict |
|---|---|---|
| R4-01 (S2) D-9's no-tombstone result covers recorded content only | `proofs-d9c` (158 verified, 14 located safety controls) adds guard G-BM: bypass writers honour the marker (`proofs-d9c/src/biz.rs:75, 81-83`). `theorem_no_tombstone_of_live` now ensures `!any_content` (`theorems.rs:31-48`). `any_content` covers visible rows, rows that the rollback of an open bypass transaction would restore, and rows an erasure saved (`biz.rs:136-140, 200`). G-BM is stated as a working assumption absent at the pin, and the RED-B1.1 reading as a maintainer question (`proofs-d9c/PROOFS.md:137-139`, `PROOF-DEBT.md:19`) | **met in substance**. Two statements are wrong (R5-03): the counterexample does not follow "F-C1350's live schedule", and STATUS calls G-BM "proved" |
| R4-02 (S2) WS-OBL-093 and the blanket failed-run rule | WS-OBL-093 now cites `ws-live-replay-delete_reification`: equal baseline, `$TLEVEL` 0 before and after, journal shows the deletes committed and no ledger node, then `diverges` / `unrecorded_writes`. It is labelled `holds-as-detection`. `matrix/build_matrix.py:386-395` skips only the runs a discharge names in `failed_runs_other_pairs`. `writesets/tools/check_discharges.py:21-26` adds C9: a `live` grade must cite a run that exercised the pair (`RUN-PAIRS.json`). C10-C12 cover attribution and registration | **met** |
| R4-03 (S3) the F-1306 control | `proofs-d9c/src/protocol_top.rs:42-71` makes the replay an unrecorded writer step with no marker read, like the pin's direct SQL DELETE+INSERT (`ledger/client.py:430-481` at the pin). It models the first property row only and states "marked case only" (`proofs-d9c/PROOFS.md:89-93`). `proofs-d9b/PROOFS.md:176` is qualified | **met** |
| R4-04 (S3) premises the pin violates | P-D9-3 and P-LV are listed as violated (`proofs-d9/PROOFS.md:227-242`, `proofs-d9b/PROOFS.md:250-261`, `proofs-d9c/PROOFS.md:141-142, 171-172`). F-C1301 is live in d9b (`:258`), `STATUS.md:60` and `TRUST.md:29`. F-C1350 is cited as live evidence for G-B | **met** in the proof files and the account. F-C1301's own record is a leftover, counted under R4-13 |
| R4-05 (S3) P-A3 overstated | `TRUST.md:43`, `PROOF-DEBT.md:23` (D-13) and `proofs-pa3/PROOFS.md:45-47, 147` now state the weaker proved statements | **met**, with one wording error (R5-08). The text says the overlap is allowed while the eraser "has not passed TSTART". In the model the eraser is then in phase `Locked`: it has passed `ELock`, which is TSTART (`proofs-pa3/PROOFS.md:35`; `adj_l2.rs:254-263`), but not `ERows`, its DELETE |
| R4-06 (S3) two misstated records and the %NOINDEX residue | Errata exist for `ws-live-ins-bulkloader_load_edges` and `-import_rdf` (`evidence/errata.json` entries 22-23). `ws-live-replay-import_rdf` starts from an equal baseline (its log). The residue is now finding F-C1250 (S1, `ws-live-noindex-erase`) | **met** |
| R4-07 (S3) what the INV-replay cells show | All 40 INV-replay lemma discharges carry `holds_as`: 36 `detection` (matrix label `holds-as-detection`, defined in `MATRIX.md`) and 4 `vacuous`. WS-OBL-004, 008, 024, 064 and 105 say "the cited run has no journal section", and 008's fallback is noted. The six migration cells (WS-OBL-135, 136, 139, 140, 143, 144) are graded inspected, with `ws-live-migrations` as `context_runs` | **met** |
| R4-08 (S3) "exactly its law" | Errata 25-39 are accurate; they name the first other law per check, while the r2 logs show up to five. The harness has a complement check (`models/semantics/src/harness.rs:94` `all_violations`, `:110` `check_keep`). All 21 undeclared departures are now declared in `semantics/mechanisms.json`. `check_semantics.py` enforces departure-undeclared, departure-unshown and complement (self-test 21/21). `MECHANISMS.md:18-20` has an "Also violated by (complement)" column, and `SEMANTICS.md:65-75` is updated. `sem-mc-all-r2`: 58 of 140 checks also violate another law, as recorded | **met** |
| R4-09 (S3) ratchets red, entry point incomplete | `verify.sh:76-85` adds the writesets, semantics, root-causes, premise-map and closure checks with self-tests; `:137` adds `proofs-d9b`, `-d9c`, `-pa3` and `-mech`; `:144-152` add semantics and core-partition. `check_premise_map.py:55-63` reads the proof crates by glob. On a clean export of `25ba22dd` every checker exits 0 **except** `reflection/tools/check_closure.py` and its self-test. They fail with FileNotFoundError on `PC/contract-2/coverage.json`, which `.gitignore:60` (`coverage*.json`) excludes and which was never committed (`$RUN_DIR/review-5/closure-clean-export.log`). The gate passes only because the worktree holds the ignored file | **partly met** (R5-01) |
| R4-10 (S3) 3.3a-mechanisms | `proofs-mech`: 1,149 verified, 0 errors, `--no-cheating`, empty trust inventory. All 45 laws are proved generically over a mechanism trait (e.g. `m01_ledger.rs:49, 189-194`); the instances only implement the trait (`i01_ledger.rs:17-23`). Each of the 120 controls is rejected at its obligation (72 as-built, 46 mutants, 2 exceptions). `matrix/gates.json:28` carries "generic lemmas proved once over a trait". The cell is level model, product `fails` | **met** |
| R4-11 (S3) 3.7-perf | `matrix/orchestrator_status.json`: 3.7-perf is `blocked`, names the runnable subset and the blocked baselines (`validation/SUITES.md:188-190`) | **met** |
| R4-12 (S3) module 00 reason | `matrix/orchestrator_status.json:2301-2324`: the axioms are instantiated in the module contracts (model level) and model-checked over six composed mechanisms (M-01..05, M-10; `models/semantics/src/sys00.rs:3-5`); there is no cross-module proof (D-5) | **met** |
| R4-13 (S3) STATUS, TRUST and PROOF-DEBT lag | `STATUS.md` is rewritten, its numbers generated and checked (`tools/status_numbers.py`); my fork's independent recount equals them (197 original, 114 new, the same 43 S1 ids). The S1 table is updated. `PROOF-DEBT.md:3-4` lists d9b, d9c, pa3 and mech, and D-9 lists its open items | **partly met**. F-C1301's `observed` still opens "Model only (core M2, 5 steps)" (`findings/audit/13.json:179`, unchanged since `f497a387`), although its disposition is reproduced-live (R5-07). New staleness: R5-02, R5-04, R5-05 |
| R4-14 (S4) evidence wording | **Done:** errata for the two ws-live-ins records, `ws-deploy-auditb`, the 15 sem records and four `rf-*` records; the `proofs-d9c` and `proofs-mech` runners print a RUNNER SUMMARY with the JSON SHA; F-C1150 softened. **Not done:** (1) the general "N errors counts failing functions" erratum, although the pattern recurs in `proofs-d9c-f1302-unlocked-start` and `-f1306-replay-direct-sql` (`proofs-d9c/PROOFS.md:23-26` now defines it); (2) errata for the 22 superseded round-r1 `proofs-d1d-*` records; (3) the `proofs-d9b` / `proofs-pa3` runners (d9b's `run_proofs.py` is unchanged; pa3 changed only its JSON reader); (4) counts in the `proofs-d1c..d1f-recheck` observes; (5) F-C0670's disposition | **partly met** (R5-10) |
| R4-15 (S4) matrix housekeeping | **Done:** WS-OBL-066 carries `depends_on: ["O-1"]`; the committed matrix equals one built from the committed tree (`build_matrix.py --check` exits 0 on a clean export); lifted census cells open with "Census reopen lifted"; `check_discharges.py` C9 checks that a live grade cites a run that exercised the pair. **Not done:** (1) "25+ undeclared writers" in 12 cells; (2) the "[proofs-pa3]" tag in 8 cells; (3) `evidence_file` still grades `inspected` from any existing file (e.g. 3.6-capacity/05 on `findings/audit/05.json`); (4) 50 of the 72 3.3-L1/L2/refinement/controls `fails` cells, module 15 included, still rest only on "stated fails by orchestrator" | **partly met** (R5-10) |
| O-1 (operator) | `incidents/O-1-FIXTURES.md`, `CONVENTIONS.md:45-49` | **resolved by the operator**. Attribution is checked in section 3.5; one extension needs the operator's confirmation (R5-06) |

## 2. Evidence audit (299 run records)

The scope is all records added since `f497a387`: `git diff --name-only --diff-filter=A f497a387..25ba22dd --
PC/evidence/runs`. They come from proofs-mech 122, semantics 49, refusals 25, structural 20, proofs-d9c 18,
contract-2 16, writesets 12, ontology-2 10, orchestrator 7, product-gates 7, reflection 6, trace-replay 6 and operator 1.

- **Hashes.**
  - All 299 primary logs re-hash to their recorded SHA-256 and size, with 0 mismatches (`review/review-5/rehash.py`,
    `rehash.json`).
  - The 138 pinned JSON logs (121 proofs-mech, 17 proofs-d9c) match their `json_sha256`.
- **Verus records.**
  - Fork (a) read all 140 `proofs-d9c` and `proofs-mech` records against their text logs and pinned JSON logs:
    - their sources hash to the registered values (`f34be0bd924c`, `3e168bab3175`);
    - neither crate has `assume`, `admit`, `external_body`, `axiom`, `uninterp` or `assume_specification`;
    - no control fails outside its stated file, and none fails anywhere else as well;
    - the baseline's 352 named refutations and counterexamples all verify.
- **Verdicts** (`review/review-5/evidence-verdicts.json`): **273 MATCH, 25 PARTIAL, 1 MISMATCH.**

| Group | Records | Verdict | Note |
|---|---|---|---|
| `env2-coverage-selftest` | 1 | **MISMATCH**, no erratum | Observes: "all 14 JSON features of module 11". The log's `c_json_features_of_module_11` lists 15 (I read it). The seeded names are not in the log, which holds booleans only |
| `live-licence-world` | 1 | PARTIAL, no erratum | The worlds' outcomes match. But "~2 s per commit vs 0.2 s" takes the control figure (209 ms) from the failed, unregistered attempt `licence-world/r1.log`. The registered `r2.log` shows world C at 47.3 ms and 1.46 ms, and world X at 2,062.6 ms and 2,017.0 ms (I read both). F-C1795 quotes the r1 figures too. The qualitative claim holds, more strongly |
| `ws-live-ba-explicit-survives` | 1 | PARTIAL | For `BulkLoader.load_edges` the "explicit write" answered `edges: 0`: it skipped the existing row (I read the log). The observes says the writer "wrote the same triple explicitly" |
| `st-live-susp-loader-clear` | 1 | PARTIAL | "No ledger revision for the deleted committed edge" is not in the log. `verify_before` was already `diverges`, which the text does not say |
| `sem-check-r3`, `sem-check-r4` | 2 | PARTIAL | "299 classed / 203 break an axiom" and "309 / 208" are not in the logs, which are byte-identical to `sem-check-r2`. The counts are right in the committed `semantics/src/finding_classes.json` |
| `env2-fetchfirst-probe`, `env2-fc1720-query-nodes` | 2 | PARTIAL | The logs record no driver version (`"driver": "?"`), so the 5.3.2 attribution is not in them. "No server-side error in messages.log" is not in the log |
| `ont2-coverage`, `-r2`, `ont2-ontology-check`, `-r2` | 4 | PARTIAL | 3,580 entries / 0 uncovered and 4,216 statements / 0 violations match. The breakdowns stated beyond these (1,856 uncovered before, the 899/180 split, tag and cell counts) are not in the logs |
| `env2-coverage`, `env2-x2-r1`, `rf-premise-map-check-r3`, `tr-locklog-09` | 4 | PARTIAL, erratum exists | `tr-locklog-09`: the 91/85 job iterations, 97 compilations and "no IVGC class left" are only in the unpinned `locklog/09.json` |
| `proofs-d9c-f1302-unlocked-start`, `-f1306-replay-direct-sql` | 2 | PARTIAL | "2 errors" against 3 locations: errors count failing functions (R4-14) |
| `st-live-cap-upgrade-build`, `-load`, `tr-replay-01-r2`, `tr-replay-09-r2`, `ws-check-r2`, `ws-check-r4`, `rx-dec-live-18`, `status-numbers-check` | 8 | PARTIAL | The counts and outcomes match. Some details are only in unregistered or unpinned side files (`load-try1.json`, raw JSON) or the record's fields: the first load attempt, class names, pids, per-rule results, and the 13th of 12 type changes (the log caps the diff at 12) |
| all others | 273 | MATCH | Including every proofs-mech and proofs-d9c count and location, the semantics family logs (272 of 272 met, none truncated), contract-2 E-1/X2 (67 cases 14/14; 54 cases 8/8; 190 cases 0 outside 29/29), `rx-audit-r2` (186/29/13/11/4/1 = 244), `ws-live-replay-delete_reification`, `ws-live-replay-import_rdf`, `live-crash-repeat-sc0`/`-sc1`, `verify-clean-a42f10c8` |

**Errata the lanes reported** exist: `ws-live-ins-*` (22-23), `ws-deploy-auditb`, the 15 sem records, `env2-coverage`,
`env2-x2-r1`, `tr-locklog-09`, `rx-audit` (34 → 33), and four `rf-*` records. None exists for the MISMATCH or for the
PARTIAL rows marked "no erratum" above.

**Log provenance (TRUST.md "Log provenance").**
- The six superseded records (`core-proofs-baseline` and five controls) are unchanged since `307a0a8c`. Their digests do
  not match their (overwritten) logs. `check_registry.py` reports them as `superseded`, naming the rerun from
  `incidents/superseded-logs.json`, and as 0 problems.
- TRUST states the operator's check exactly: 1,237 records, 1,231 matching, 6 not original. It does not relabel the six.
- One sentence is imprecise (R5-11): "Their records were not rewritten; each names an explicitly superseding rerun". The
  records name nothing; the incident file names the reruns.

## 3. Claims audit

### 3.1 Product versus model

- No text describes the product as meeting a property only a model has.
  - Every matrix cell citing `proofs-d9c`, `proofs-mech`, `proofs-pa3`, `m2p-*` or `sem-*` is level `model`, with
    product label `fails`.
  - `holds-*` product labels appear only on single write-set pairs: `holds-live` 9, `holds-inspected` 69,
    `holds-as-detection` 36.
  - `holds-in-model-only` appears once (3.7-explorers) and says so.
- Two texts overstate what the models show (R5-03).
  - **"F-C1350's live schedule"** (`proofs-d9c/PROOFS.md:65`, `PROOF-DEBT.md:19`, `proofs-d9c/MATRIX-INPUT.json:99`). The
    counterexample does not follow the live run's order:
    - `cx_f1350` lets the bypass writer write after the reviewed, locked Start has set the marker (steps c6 → c7).
    - In the live runs the writer writes while the redaction waits for the head lock, after its entry check
      (`writesets/live/ws_probes.py:302-327`).
    - At the pin the marker is set only inside `BatchInLock`, after `Lock +^IVG.Ledger("head")` (`LedgerRedact.cls`,
      `Batch` / `BatchInLock`, read at `3eaa79cf`).
    - So the counterexample reproduces F-C1350's outcome under the reviewed Start, not its schedule. In the reviewed
      design the live order is excluded by the locked Start (HD-1301) together with G-BM.
  - **`STATUS.md:91`** says "guard G-BM, proved in `proofs-d9c`". G-BM is an assumed reviewed guard; what is proved is
    no-tombstone under it. `STATUS.md:32` ("G-BM excluding F-C1350") omits the locked Start.

### 3.2 Cells that changed status since `f497a387`

`review/review-5/matrix-changes.json` lists 150 changed or new cells:
- open → closed: 89 (7 of them also unknown → fails);
- open → blocked: 15, all 3.7-mutation (O-2);
- closed → blocked: 1, 3.7-perf (R4-11);
- `holds-live` / `holds-inspected` → `holds-as-detection`: 36 (R4-07);
- closed, unknown → fails: 4 (3.1-intent 08, 09, 16, 17, from new findings);
- new: 5 REACH-n-stated cells (closed, intent-undecided).

I sampled:
- 3.6-frame (13 cells);
- 3.4-declared-reads (7);
- 3.5-decoders 07/10/18;
- 5c-refusals (9);
- 3.7-trace-replay 01/08/09;
- 3.7-lock-log/09;
- 3.6-capacity/01;
- 3.1-intent 08/09/16/17;
- 3.1-coverage/04;
- 3.2-coverage/11;
- 3.7-integration-worlds;
- 3.7-failure-controls;
- 3.3a-mechanisms;
- 3.6-closure;
- 3.8-status;
- 3.8-trust.

Each cites registered runs that ran, or committed analyses, and states what remains. The exceptions:
- **The 18 closed 3.2-coverage cells (and the open 3.3a-trace cell) cite `PC/contract-2/coverage.json`**, which is not
  in the commit (git-ignored). 3.3a-trace also cites `PC/semantics/data/trace_sample_review.json`, which is likewise
  ignored (R5-01).
- **3.6-capacity/01 closes on the O-1 fixture used in a second namespace** (R5-06). Its own text says the 3.x
  whole-table migrations stay blocked. That is consistent with the frame cells, which also close with a stated
  remainder.
- **3.8-trust is closed on a TRUST.md whose durability row is stale** (R5-02).
- **3.8-test-reflection's remaining text is stale**: it still lists "the SynchCommit=1 crash world" as needing the
  operator (`matrix-input/reflection.json:74`) (R5-02).

### 3.3 New findings since `f497a387`

Fork (d) checked all 22 named ids, plus F-C1720 (a duplicate merged into F-C1743) and F-C1240 (now refuted). For each
it checked intended (sources opened at the pin), observed (registered logs), disposition, severity, remedy and id range.
I re-checked F-C1795, F-C1018, F-C1102 and F-C1301 myself. The other rows are fork (d)'s reading; I use them only for
S4 recommendations.

| Finding | Result |
|---|---|
| F-C1250 (S1), F-C0350, F-C0351, F-C0415, F-C0615, F-C0690, F-C0715..0717, F-C1046, F-C1715, F-C1716, F-C0341, F-C1041, F-C1640, F-C1641, F-C0940, F-C0841, F-C1741 | Sources exist at the pin and say what is claimed. The cited runs show what is claimed. Dispositions match the evidence. Remedies are prose only. Ids are in their lanes' ranges |
| F-C1795 (S4, licence world) | Behaviour confirmed in `r2.log`: a silent fallback from a refused dedicated connection, and a retried connect on every native call. **The timing figures are r1's** (2,064/2,017 vs 209/1.6 ms); r2 has 2,062.6/2,017.0 vs 47.3/1.46 ms. An erratum is needed (R5-09). The id (nn 95) lies in the product-gates range; the orchestrator has none (`CONVENTIONS.md:96-97`). There is no collision |
| F-C0350 | Part (b), duplicate edge keys from two `load_edges(skip_existing=False)` calls, is already F-C0349 (`zz-structural.json`, `st-live-keys`), and there is no cross-reference. Part (a), a default load then `create_edge`, is new |
| F-C1018 | Cites "spec 230 FR-017". There is no `specs/230*` at the pin; spec 230 exists only in code comments (e.g. `_engine/admin.py:306`). Cite the comment or docstring instead (S4) |
| F-C1743 | Its notes open "Tested with driver 5.3.2 … 5.4.0 not tried", while the note merged from F-C1720 cites the 5.4.0 runs |
| F-C0340 (S3) | "One the ledger committed" and "no revision records the deletion" are beyond the log, and `verify_before` already diverges. S2 is defensible (content deleted across every graph, bypassing strict mode) |
| F-C1306 | Attribution is correct (section 3.5). It names v4.5.1's `LedgerRevision` and `LedgerStats` but omits `Graph.KG.Meta` (`O-1-FIXTURES.md:26`) |
| F-C1102 | Its notes still say "With SynchCommit=1 the result may differ; not tested here" (`findings/audit/11-orchestrator.json:22`), and its evidence lists only `live-crash-world-r2` (R5-02) |
| F-0601 → reproduced-live | Justified. In `rx-live-priv-vec` case (c), as IVGAUDIT_RO with the registry unreadable (-99), `store_embedding` returned True and wrote the row. At the pin, `enforce_embedding_identity` is always called (`embeddings.py:981`), and `get_embedding_identity` answers None on any exception (`schema.py:1033-1061`) |
| F-1506 → reproduced-test | Honest. `rx-live-15` used an rdflib 8 stand-in in the probe process, and the record says so |
| F-C1301 | The disposition is reproduced-live (unchanged), but `observed` still opens "Model only" (R4-13, R5-07) |
| F-C1150 | Softened as R4-14 asked. F-C0670 was not (R5-10) |

My fork's independent recount of STATUS "Numbers" equals the generated table. The evidence ids in the STATUS S1 table
(`STATUS.md:57-65`) all exist and show the claimed behaviour.

`STATUS.md:31` says "every IRIS feature of every module classified: 673 inside, 278 validated, 1,157 outside". These are
the sums over modules 01-11 and 15-18 only. All 19 modules in `contract-2/coverage.json` give 784 / 324 / 1,237 (I
recomputed). This is a wording fix (R5-05).

### 3.4 Crash, licence and least-privilege worlds

**Crash worlds** (`live-crash-repeat-sc0`, `-sc1`).
- `$RUN_DIR/crash-repeat/sc1-procedure.log` records the reconfiguration:
  - `set SynchCommit=1`: BEFORE=0, AFTER=1, a restart, healthy, `327:SynchCommit=1`;
  - the trials;
  - then `restore SynchCommit=0`: BEFORE=1, AFTER=0, a restart, healthy, `327:SynchCommit=0`.
- So the change was restored. It is recorded in the run log and record, but there is **no `incidents/` entry**, though
  the plan in `LANES.md:21` named one (R5-02).
- The results match `results.json`:
  - in-flight commits were all-or-nothing in every trial;
  - acknowledged commits were lost in 3/3 trials under SynchCommit=0 and in 0/3 under SynchCommit=1;
  - every retry was clean.
- The oracle is sound: it requires every acknowledged commit, and all 3 acknowledgements were present in each run. Two
  caveats:
  - the field `commit_running_at_crash` means "client process alive";
  - the first sc0 restart never reported healthy (363 s, though connectable), and the record does not say so.
- **Overclaim:** "shown sufficient in 3 of 3 trials" (`STATUS.md:101`). Three container SIGKILL trials with the host
  intact support "no acknowledged commit lost in 3 trials", not sufficiency.
- **Stale account entries** (R5-02):
  - `TRUST.md:42` still says "`SynchCommit=1` untested. Every durability result of this audit holds for `SynchCommit=0`
    only" and "one trial per world";
  - F-C1102's notes;
  - `reflection/TEST-REFLECTION.md:391` ("needs the container reconfigured; the audit may not reconfigure it").

**Licence world** (`live-licence-world`, S6).
- The three worlds match `r2.log`:
  - C: units free;
  - X: 7 holders after the engine connected; the dedicated connect is refused and the engine silently falls back;
  - R: 8 holders before connecting; `from_connect` refuses, and the row counts are unchanged (0/0/0, `nothing_written`).
- It is a deliberately induced scenario with the container exclusive. It is not confused with the rule that a licence
  failure is infrastructure.
- The timing figures are from r1 (above).

**Least privilege** (`IVGAUDIT_RO`).
- Fork (c) read `final-state-r3.json`. It shows the user disabled (`enabled=0`, login refused), role resources restored, no AUDITE
  privilege rows left, and 160 CheckPrivilege calls all 0.
- The password is only in `$RUN_DIR/versions/secrets/` (mode 600). I searched for it with `git grep -F -f` over the
  `25ba22dd` tree and over the worktree's `experiment/`: 0 hits. My fork also searched git history (`git log --all -S`)
  and `$RUN_DIR` outside `secrets/`: 0 hits.

### 3.5 O-1 attribution

- **`o1-fixture-inventory` matches** `O-1-FIXTURES.md:26` (fork c): 251 classes = 54 equal to the pin + 8 v4.5.1-only +
  11 with a pin name + 178 generated. Fork (c) diffed 8 of the 11 "formatting only" classes against the pin, and they
  are formatting-only.
- **`IVGDev.Run` and `IVGDev.Setup`** equal the pin's files.
- **F-C1306's notes state the attribution correctly**: the v4.5.1 residue is the intended precondition, and the
  assessment is of the pin's upgrade path. It omits `Graph.KG.Meta` (S4).
- **WS-OBL-066** carries `depends_on: ["O-1"]`, and its cell's text cites the O-1 record.
- **IVG262CAP (R5-06).** A second namespace, built by the same fixture from the same unchanged v4.5.1 release
  (`f60b20c2`) for the capacity probe (3.6-capacity/01). It is recorded in `O-1-FIXTURES.md:45-49` and
  `NAMESPACES.md:29-31`. However:
  - the binding text names one namespace: `CONVENTIONS.md:46-48` says "in its isolated migration-test namespace
    (`IVG262FC1306`)";
  - the operator's words are singular;
  - the content was written by an audit script (`structural/upgrade/load451_child.py`) through v4.5.1's Python API;
  - no class inventory was taken after the pin's upgrade, only counts (87 → 144, fork c).

  This is plausibly within O-1's intent (test setup; an IVG262* scratch namespace that the fixture is built for). But it
  is the orchestrator's reading, not the operator's words, and the account does not say so.
- **`O-1-FIXTURES.md:42-43`** says the native executor's plan-class compilation "was not exercised". It was written
  before the module-09 replay, which made the product compile its generated IVGC classes 111 times in AUDITC
  (`trace-replay/TRACE-REPLAY.md:302-307`; `tr-locklog-09`, `tr-replay-09-r2`), under the orchestrator's scope decision
  (`CONVENTIONS.md:35`), not O-1. I accept that decision: these are the pin's own generated classes, all deleted by
  `Gen.DropAll`, and none was left. The sentence must be corrected (R5-04).
- **`QUEUE.md:60-62`** still says "Operator ruling still requested" for exactly what O-1 resolved (R5-04).

### 3.6 Product change in disguise

None found.
- Nothing outside `experiment/` differs from the pin.
- The audit compiled no class.
  - The O-1 fixture compiles only the unchanged v4.5.1 release through the pinned fixture.
  - The product's own run-time plan classes are disclosed.
- Scratch SQL is `IVGAudit.*`, dropped afterwards.
- Stand-ins for absent libraries are disclosed per run: `mcp`; `torch` and `structlog`; rdflib 8 for `rx-live-15`.
  F-1506's live cases therefore rest on a simulated library, and its disposition says reproduced-test.
- No oracle was weakened.
  - The Verus reader change (`tools/verus_json.py`, `6238aaaa`) returns the last root JSON object that carries
    verification results. It fails closed on trailing text, truncation or absence, and never reads success from text
    lines (self-test 9 cases).
  - The pair-specific failed-run rule (R4-02) is stricter than before.

## 4. The clean live gate on the candidate

**Run.** `$RUN_DIR/verify/20261114T203920Z`, `bash verify.sh --live --clean`. Inputs written 20:39:20 UTC, summary
written 22:04:39 UTC. The orchestrator registered it after the candidate as `verify-clean-25ba22dd` (result pass,
commit `d0375bae`). The record's log is `summary.jsonl` and re-hashes to its SHA-256.

**Inputs** (`inputs.txt`):
- `candidate_commit 25ba22dd`;
- `mode live clean 1`;
- `worktree_status_lines 0`;
- product tree at the pin `b098a6f4`;
- experiment tree `72cfce62`, which equals `25ba22dd:experiment/playbook-completion`;
- original submission tree `becf53a4`.

**Versions** (`versions.txt`): Verus 0.2026.10.04.426d8b0, rustc 1.98.1, Python 3.11.18, driver 5.3.2, actors `c03f9fa`.

**Result.** 73 steps, **73 exit 0**, none non-zero. I re-hashed all 73 step logs against the summary: 0 mismatches. I read
every step's result line.
- **All 12 Verus gates PASS** with the registered sources hashes and counts:
  - `proofs` 88/0, 5 controls;
  - `-breadth` 94/0/7, `-d1b` 92/0/11, `-d1c` 111/0/10, `-d1d` 118/0/21, `-d1e` 115/0/15, `-d1f` 115/0/17;
  - `-d9` 115/0/7, `-d9b` 158/0/15, `-d9c` 158/0/16, `-pa3` 108/0/9;
  - `-mech` 1,149/0, 120/120 controls rejected at their obligation, trust inventory empty.
  - The nine readers that failed in `verify-clean-a42f10c8` now pass.
- **The explorer crates reproduce every committed check** (`models-compare`): core 82, breadth-a 104, breadth-b 132,
  breadth-c 39, semantics 272; 0 missing, 0 unmet.
- **The (2,2) partition** reproduces the coverage and all six families. For example, reviewed: 43 pieces, 21,355,762
  states, 266,808,918 transitions, 0 truncated.
- **Live rounds:**
  - contract: 516 cases, 0 outside the contract, 42/42 mutants killed, on a new seed;
  - conformance: 53 transactions, 0 violations, replay equals the engine;
  - F-1201: ERS-I3 violated in 4 of 4 trials (the expected reproduction of a product defect);
  - lost-ack: 0 oracle violations in 6 worlds.
- **Product scope:** passes before and after.

**Caveat (R5-01).** The run read the worktree, and the worktree holds the ignored, uncommitted
`PC/contract-2/coverage.json`. From a clean checkout of `25ba22dd`, the `closure-check` and `closure-selftest` steps
exit 1 (I reproduced this). Fork (b) ran the fast part's other checkers on a clean export, and they exit 0. One
exception: the ontology gate also needs the product's `vendor/opencypher` submodule checked out, because it accepts the
local checkout rather than reading the gitlink commit (R5-11). The build part is clean as claimed, with empty targets
and private proof run directories. The 3.7-full-rerun cell, which
`d0375bae` closed on this run, carries the same caveat.

**Durations against the 20-minute single-gate target.**
- The fast gate (37 steps) took 51 s.
- The whole run took 5,119 s of step time, 85 minutes wall.
- One step exceeds 20 minutes: `proofs-mech`, at 2,230 s (37.2 min). STATUS says "~35 min" and PROOF-DEBT D-14 says
  "36 min" (from the earlier run's 2,110 s).
- The next slowest steps are `partition-as-built-isolation-stmt` (481 s), `partition-reviewed` (427 s) and `models-core`
  (331 s).
- 5a-gate-20min stays open, as the account says. Splitting `proofs-mech` per mechanism is the stated remedy.

## 5. Conditions

Each condition gives the exact place and the fix in prose. The severities rate the account, not the product. None of
the conditions hides an observed product failure: every product label they touch is already `fails`,
`intent-undecided` or a model-only statement. None of them needs IRIS, Verus or the operator, except the confirmation
asked in R5-06.

**Blocking.**

- **R5-01 (S3): the committed tree does not reproduce its own gate, and closed cells cite evidence that is not
  committed.**
  - Where:
    - `PC/contract-2/coverage.json` (806,943 bytes) is excluded by the product's `.gitignore:60` (`coverage*.json`) and
      was never committed.
    - `PC/semantics/data/trace_sample_review.json` is excluded by `.gitignore:44` (`data/`) and was never committed.
    - The 18 closed 3.2-coverage cells and the open 3.3a-trace cell cite them.
    - `reflection/tools/check_closure.py:54` reads `coverage.json`. That checker is the gate's `closure-check` and
      `closure-selftest` steps (`verify.sh:84-85`). `semantics/tools/trace_requirements.py --check` also needs the file.
    - On a clean `git archive 25ba22dd` export, `check_closure.py` exits 1 (FileNotFoundError,
      `$RUN_DIR/review-5/closure-clean-export.log`).
    - `verify.sh:45` counts `git status --porcelain`, which leaves ignored files out. So `worktree_status_lines 0`
      cannot reveal this, and the "clean" gate ran on the commit plus ignored files.
  - Fix:
    - commit both files (forced past the product's ignore patterns; they are audit artifacts under `PC/`);
    - make `--clean` fail on ignored files under `PC/` (other than `__pycache__`), or run it from a `git archive` export;
    - deal with the same defect where it predates this pass. `findings/audit/01.json`..`06.json` cite 50 files under
      `PC/live/breadth-a/results/`, which `.gitignore:145` (`results/`) excludes. `models/breadth-b/results/` (132
      files) is ignored too; the first review raised it. Commit these files or cite the registered logs instead;
    - run and register `verify.sh` (fast, `--clean`) from a clean export of the new candidate. The full and live steps
      of `20261114T203920Z` can stand for it if `git diff 25ba22dd..<new>` touches no crate, model, harness, trace or
      contract source. Say so in the record.
- **R5-02 (S3): durability statements contradict the crash worlds, and the reconfiguration has no incident record.**
  - Where:
    - `TRUST.md:42` says "one trial per world", "`SynchCommit=1` untested" and "Every durability result of this audit
      holds for `SynchCommit=0` only";
    - F-C1102's notes say "With SynchCommit=1 the result may differ; not tested here"
      (`findings/audit/11-orchestrator.json:22`), and its evidence lists only `live-crash-world-r2`;
    - `reflection/TEST-REFLECTION.md:391` and the 3.8-test-reflection cell (`matrix-input/reflection.json:74`) list
      the SynchCommit=1 world as needing the operator;
    - `STATUS.md:101` says SynchCommit=1 was "shown sufficient in 3 of 3 trials";
    - no `incidents/` record of the SynchCommit reconfiguration and its two restarts, which `LANES.md:21` planned.
  - Fix:
    - restate these places from `live-crash-repeat-sc0`/`-sc1`: 3+3 container SIGKILL trials; acknowledged commits lost
      3/3 under 0 and 0/3 under 1; restored to 0; results hold per setting as tested;
    - word STATUS as "no acknowledged commit lost in 3 trials", not "sufficient";
    - add an incident record from `$RUN_DIR/crash-repeat/sc1-procedure.log` and `pre-sc0.txt`, including the first sc0
      restart that never reported healthy (363 s, `sc0/results.json`).
- **R5-03 (S3): what `proofs-d9c` shows about F-C1350 is overstated.**
  - Where:
    - "F-C1350's live schedule" (`proofs-d9c/PROOFS.md:65`, `PROOF-DEBT.md:19`, `proofs-d9c/MATRIX-INPUT.json:99`);
    - "guard G-BM, proved in `proofs-d9c`" (`STATUS.md:91`);
    - "with guard G-BM excluding F-C1350" (`STATUS.md:32`).
  - Fix:
    - say that `cx_f1350` reproduces F-C1350's outcome under the reviewed locked Start: the bypass write follows the
      marker. Live, the write lands after the entry check and before `BatchInLock` sets the marker
      (`writesets/live/ws_probes.py:302-327`; `LedgerRedact.cls` `Batch`/`BatchInLock` at the pin);
    - say that the live order is excluded by the locked Start (HD-1301) together with G-BM;
    - say that G-BM is a reviewed guard the model assumes, under which no-tombstone is proved, not a proved guard.
- **R5-04 (S3): the account misstates the review and operator state.**
  - Where:
    - The 3.8-review cell (`matrix/orchestrator_status.json:328` at `25ba22dd`) cites reviews 1-3 only, says "the remaining sign-off
      condition is the operator's scope ruling O-1/R2-07", and says the steer-7 lanes are not reviewed.
    - `QUEUE.md:60-62`: "Operator ruling still requested (review-2 condition 6) ...".
    - `QUEUE.md:41` (Q17g) and `:49` (Q18c) are still "doing".
    - `incidents/O-1-FIXTURES.md:42-43` says the native executor's plan-class compilation "was not exercised".
  - Fix:
    - cite `independent-review-4` and this review in the cell; record O-1 as resolved and the R5 conditions as what
      remains;
    - correct the QUEUE rows;
    - in the O-1 record, say that during the module-09 replay the product compiled its own generated IVGC plan classes
      111 times in AUDITC (`trace-replay/TRACE-REPLAY.md:302-307`; `tr-replay-09-r2`, `tr-locklog-09`), under the
      orchestrator's scope decision (`CONVENTIONS.md:35`), not under O-1.
- **R5-05 (S4, blocking only because the numbers are the account's headline): two STATUS figures are wrong.**
  - Where and fix:
    - `STATUS.md:33`: "566 breadth-a pairs (561 closed, 5 open)" should read 562 closed and 4 open. The gate's
      `writesets-check` shows `open/open 4` (`ws-check-r4`): `bulk_load_session` was discharged in `82027430`.
    - `STATUS.md:31`: "every IRIS feature of every module classified: 673 inside, 278 validated, 1,157 outside" are the
      sums over modules 01-11 and 15-18 only. All 19 modules give 784 / 324 / 1,237. Say which, or use the totals.
  - Better still, generate both figures with `tools/status_numbers.py`.
- **R5-06 (S3): the second O-1 namespace is the orchestrator's reading, not the operator's words.**
  - Where:
    - `IVG262CAP` was built by the pinned fixture from the unchanged v4.5.1 release (`O-1-FIXTURES.md:45-49`,
      `NAMESPACES.md:29-31`);
    - content was then loaded through v4.5.1's API by the audit's `structural/upgrade/load451_child.py`;
    - 3.6-capacity/01 is closed on it;
    - `CONVENTIONS.md:46-48` names one namespace (`IVG262FC1306`), and the operator's text is singular;
    - no class inventory was taken after the pin's upgrade, only counts (87 → 144, fork c).
  - Fix:
    - state in `CONVENTIONS.md` and `O-1-FIXTURES.md` that `IVG262CAP` is the orchestrator's extension of O-1 (same
      fixture, same unchanged release, an IVG262* scratch namespace);
    - give 3.6-capacity/01 a `depends_on` naming it;
    - take the class inventory as `o1-fixture-inventory` did;
    - ask the operator to confirm. The text fix is blocking; the confirmation is not.

**Not blocking (S4, recommended).**

- **R5-07:** F-C1301's `observed` should not open "Model only" (`findings/audit/13.json:179`; R4-13's last item).
- **R5-08:** "has not passed TSTART" should read "has passed TSTART but not its DELETE" (`TRUST.md:43`,
  `PROOF-DEBT.md:23`, `proofs-pa3/PROOFS.md:47, 147`, the comment at `proofs-pa3/src/adj_l2.rs:336-337`).
- **R5-09: errata.**
  - `env2-coverage-selftest`: 15 JSON features, not 14; the seeded names are not in the log.
  - `live-licence-world` and F-C1795: the control figures are r2's 47.3/1.46 ms, not r1's 209/1.6 ms.
  - `ws-live-ba-explicit-survives`: `load_edges` skipped the row (`edges: 0`).
  - `st-live-susp-loader-clear` and F-C0340: `verify_before` already diverged; no ledger read after.
  - `sem-check-r3`/`-r4`: counts only in `finding_classes.json`.
  - `env2-fetchfirst-probe`, `env2-fc1720-query-nodes`: no driver version in the log.
  - `ont2-coverage(-r2)`, `ont2-ontology-check(-r2)`: breakdowns beyond the log.
  - The section-2 rows whose details live only in unregistered side files: register or pin those files, or add errata.
- **R5-10:** the R4-14 and R4-15 remainders listed in section 1.
- **R5-11: small text fixes.**
  - `TRUST.md:58-60`: the incident file, not the records, names the superseding reruns.
  - F-C0350: cross-reference F-C0349 for part (b).
  - F-C1018: cite the docstring or comment, not an absent spec 230.
  - F-C1743: its notes contradict the merged F-C1720 note.
  - F-C1306: also name `Graph.KG.Meta`.
  - F-C1795's id lies in the product-gates range.
  - F-C0340's severity: S2 is defensible.
  - `LANES.md:4` has a sentence fragment.
  - The ontology check accepts any file in the local `vendor/opencypher` checkout rather than the pinned gitlink commit
    (`677cbafa`). On an export without the submodule it fails on CYP-T11.103 (fork b).
  - The crash records do not mention the 363 s unhealthy first restart.

**Needs the operator.** Confirmation of R5-06 (IVG262CAP under O-1). O-2 (mutation testing of product code) is
unchanged.

**Needs a maintainer.** Unchanged:
- §3.8's "fix or recorded decision" for every finding;
- the intent-undecided items;
- the RED-B1.1 reading behind F-C1350 (G-BM as working assumption);
- F-C1102's durability premise.

## 6. Sign-off decision

**No sign-off** of the account for `25ba22dd`.

**Met.**
- R4-01..R4-08 and R4-10..R4-12.
- O-1 is resolved by the operator.
- The models and proofs stay on the model side of the line.
- The product's failures are recorded as failures.
- 273 of 299 new records match their logs, and none misstates a result's direction.
- The clean live gate on the candidate passed every step (73/73, `verify-clean-25ba22dd`).

**Not yet accurate.**
- **The gate is not reproducible from the commit** (R5-01, the remainder of R4-09). The committed tree fails its own
  closure check from a clean checkout, and 18 closed cells cite a file that is not committed.
- **Four account statements are false or out of date:**
  - durability: TRUST and F-C1102 say SynchCommit=1 was untested (R5-02);
  - G-BM is called "proved", and the F-C1350 control is said to follow the live schedule (R5-03);
  - the review and operator state in the 3.8-review cell, QUEUE and the O-1 record (R5-04);
  - two headline STATUS figures (R5-05).
- **The second O-1 namespace is attributed to the operator** without saying it is the orchestrator's reading (R5-06).

**Sign-off.** I will sign off on the account's accuracy for a successor candidate when:
- R5-01..R5-06 are met;
- a `verify.sh --clean` run from a clean export of that candidate is registered with every step at exit 0. Its full and
  live steps may be carried from `20261114T203920Z` on the terms in R5-01.

None of this needs IRIS, Verus or new evidence. R5-07..R5-11 are recommended.

That sign-off would cover the account, not the product. The product fails most obligations the evidence touches, as
its findings and the matrix record. The open gates that cannot close are recorded as open, not hidden:
- statement, handler, lock-plan and composition proofs (no verifier for ObjectScript or Python);
- editions, Enterprise, multi-node and FHIR (unavailable engines);
- product-code mutation (operator question O-2);
- every finding's fix or decision (maintainers);
- the 20-minute single-gate target (`proofs-mech` alone took 37 minutes in this run).
