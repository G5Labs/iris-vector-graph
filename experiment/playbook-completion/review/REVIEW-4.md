# Independent review, fourth pass (playbook §3.8, §5c)

Reviewer: independent reviewer lane (read-only). I did not produce the work under review. Product pin `3eaa79cf`
(tree `b098a6f4`, unchanged: `check-product-scope.sh` passes). No IRIS connection, no live run, no commit. I wrote only
this file, `review/review-4/` (scripts and data) and `$RUN_DIR/review-4/` (reruns, logs, clean tree exports).
`PC/` = `experiment/playbook-completion/`.

**Scope.** Everything committed since the third pass that the task names:
- the D-1 crates the third pass did not cover: `proofs-d1c`, `-d1d`, `-d1e`, `-d1f` (commits `f35ab8ac`, `b25d84b9`);
- `proofs-d9b` (D-9 remainder, F-CS01, D-12; `e8a0d08a`) and `proofs-pa3` (D-13; `8d11c49c`);
- `models/core-partition` (D-10) and `models/semantics` with `semantics/` (§3.3a; `b0433157`);
- `writesets/` and its 7 findings (`ed0fc784`), `reflection/` (`bad04b31`) and `tools/intent_check.py` (`05a86981`);
- the `build_matrix.py` and `orchestrator_status.json` changes, and the findings records changed since `1f7f22fd`.

Scope state is `e8a0d08a`. HEAD moved to `7b72fc52` during this pass (structural and product-gates lanes, 75 new
runs, about 23 new findings). That commit is **not** reviewed here. Where a check gives different results on the two
trees, I report both, each from a clean `git archive` export (`$RUN_DIR/review-4/tree-<commit>`).

Method. I did the mechanical evidence audit, the reruns of the six proof gates and of the cheap checkers, the matrix
builder audit and the account claims myself. Four read-only forks of this reviewer read the writesets, semantics, D-1
and d9b/pa3/core-partition material in depth (pin source included). I re-checked every one of their findings that I
use as a condition against the logs or the source myself; the rows below say what I confirmed.

## Decision: **no sign-off**

The proof and model work is sound as stated in its narrow sense:
- all six proof gates reproduce exactly in my rerun;
- every sampled control (23 D-1 controls, 12 d9b/pa3 controls) encodes the pin's code, with one exception (R4-03);
- the core-partition counts and the semantics model checks reproduce;
- no text presents a model result as a product result.

Two substantive problems and a set of account defects block sign-off:
1. **R4-01 (S2).** D-9 is called "paid at model level". But the reviewed design's no-tombstone theorem holds only
   for *recorded* content. It therefore admits the behaviour that the audit's own new S1 finding F-C1350 calls a
   violation of the product's intent.
2. **R4-02 (S2).** A product-level `holds-live` label (WS-OBL-093) rests on a run that never exercised the pair. The
   matrix builder now drops every failed run cited by a lemma or guard discharge, with no check of which pair failed.
3. **R4-09 (S3).** Several of the audit's own ratchets are red on the committed tree: the ontology gate, the semantics
   checker and the reflection checkers. `verify.sh`'s fast gate therefore fails. `verify.sh` also does not run any
   steer-7 crate or checker, and no verification run has been registered since `b25d84b9`.

The operator ruling O-1 (R2-07) is still pending. I did not try to resolve it.

## 1. Third-pass conditions

| Condition | Checked against | Verdict |
|---|---|---|
| A-1 (P-D9-3 listed as violated) | `proofs-d9/PROOFS.md:132` (§5 table): "false at the pin (added after review-3 A-1)" | **partly met**. The trailing section "Premises the pin violates" (`proofs-d9/PROOFS.md:219-225`) still omits it. `proofs-d9b` carries P-D9-1..5 "unchanged" (`proofs-d9b/PROOFS.md:115`) and omits it too (R4-04) |
| A-2 (06/18 product labels) | `matrix/obligations.json`: every 3.3-L1/L2/refinement/controls cell of modules 01-18 is level `model`, product label `fails`; no `holds-in-model-only` remains on these gates | **met** (weak basis, see R4-15) |
| A-3 (F-CS01 on RED-B12, RED-B4) | `ontology-review3-a3` (log: 3,877 statements, 0 violations, self-test PASS, recheck PASS) | **met** at that commit. The ontology gate fails again now for the same class of reason (R4-09) |
| A-4 (STATUS §3.8 row and verdict) | `STATUS.md` §3.8 row fixed | **met for §3.8**. STATUS is stale again on the steer-7 lanes (R4-13) |
| O-1 / R2-07 (operator) | no ruling recorded | **open (operator)** |

## 2. Evidence audit (221 run records)

These are all the records added since my third pass: 96 records from `a6dc67a1..1f7f22fd` (the D-1 crates,
`verify-full-b25d84b9`, `ontology-review3-a3`, `independent-review-3`) and 125 from `1f7f22fd..e8a0d08a`.

- **Hashes.** All 221 logs re-hash to their recorded SHA-256 and size (`review/review-4/rehash.py`,
  `$RUN_DIR/review-4/rehash.json`): 0 mismatches.
- **Verus logs.** For all 121 Verus records (the D-1, d9b and pa3 crates), the error locations in the record equal the
  locations in the log (`review/review-4/verus_logs.py`).
- **Verdicts.** One per record, in `review/review-4/evidence-verdicts.json`: **171 MATCH, 48 PARTIAL, 2 MISMATCH**.

| Group | Records | Verdict | Note |
|---|---|---|---|
| `ws-live-ins-bulkloader_load_edges` | 1 | **MISMATCH** | Observes says "equal again after erasing wsd10". Log: `verify_after_erasing_D.result = diverges`, because the rel `wsd10\|n1-R->wsd10\|n2` remains (I read the log) |
| `ws-live-ins-import_rdf` | 1 | **MISMATCH** | Observes says "verify() went equal -> diverges ... equal again after erasing wsd11". Log: `verify_baseline.result = diverges` and after-erase `diverges`, both from a `wst10` rel left by the previous case (I read the log) |
| other `ws-*` | 26 | 25 MATCH, 1 PARTIAL | `ws-deploy-auditb`: "namespace empty before the probes" is not in the log. `ws-check` (185 obligations; finding/inspected 23, finding/live 41, guard/live 9, lemma/inspected 85, lemma/live 20, open 7) and `ws-check-selftest` (19/19) match |
| `proofs-d9b-*` (not the recheck) | 16 | PARTIAL | RC-E1 recurs. The logs end at cargo's `Finished`/`error` output; "158 verified" and "counterexample ... verified=True" are only in the JSON logs, which neither record nor log pins by SHA-256. The third pass named `proofs-d1b`'s runner summary as the fix to copy; it was not copied. My rerun reproduces every value |
| `proofs-pa3-*` (not the recheck) | 10 | PARTIAL | as above |
| `proofs-d9b-recheck`, `proofs-pa3-recheck` | 2 | MATCH | counts in the log |
| "N errors" counts failing functions | (7, within the rows above) | PARTIAL | d1d f0701 (r1 and r2) 3 vs 4 diagnostics; d1e f1004 1 vs 2; d9b f1302 2 vs 3; pa3 fc0401 1 vs 2, hd0401-erase 3 vs 6, hd0401-rebuild 2 vs 3. The convention erratum covers only `proofs-breadth-hd0401-erase-kills-gen` |
| `proofs-d1c/d1d/d1e/d1f-*` | 93 | 90 MATCH, 3 PARTIAL (the f0701 and f1004 rows) | runner summary with the JSON pinned; `json_sha256` matches; 645 = 94+92+111+118+115+115 and 81 = 7+11+10+21+15+17 confirmed from the records. The 22 round-r1 `proofs-d1d-*` records are superseded by r2 (disclosed at `proofs-d1d/PROOFS.md:31-35, :349`) but have no errata entry. `proofs-d1c..d1f-recheck` observes carry no counts (the logs do) |
| `m2p-*` | 16 | MATCH | pieces, states (21,355,762 reviewed; 25,117,999 as-built isolation-stmt), transitions, 0 truncated, peak RSS (14,684,468 kB = "14.7 GB"); F-1305 violated in exactly the 22 worlds with a G:n node row; coverage and union controls fail as designed |
| `sem-*` | 45 | 30 MATCH, 15 PARTIAL | Counts, states, laws and passing instances match (`semantics/sem_logs.out`). The PARTIAL rows are 8 as-built (`retry, excl, derived, removal, queue, cap, catalog, sys00`) and 7 controls (`retry, excl, derived, removal, queue, catalog, sys00`): "each a violation of exactly its law" is an artefact of `Keep::only`, see R4-08. `sem-mc-all` matches after its erratum (controls 59) |
| `rf-premise-map-check` | 1 | PARTIAL | "39 S1", the four detected ids and "7 product-defect triage rules" are not in the 2-line log |
| `rf-root-causes-check`, `-r2` | 2 | PARTIAL | "260 audit records in 25 files" and "7 conditional" are not in the log |
| other `rf-*`, `intent-structure-*` | 5 | MATCH | 15/15, 17/17 x2, "61 decisions, 0 problem(s)", 6 seeded defects |
| `verify-full-b25d84b9` | 1 | MATCH | 35/35 steps exit 0, every step-log hash matches; "seven" corrected to eight by erratum |
| `ontology-review3-a3`, `independent-review-3` | 2 | MATCH | the latter is byte-identical to `review/REVIEW-3.md` |

**Spot checks of expected violations.**
- Every Verus control log shows errors only in its stated file. My rerun's locations are identical to the registered
  ones for all 84 safety controls and 3 progress-only controls of the six crates.
- The explorer controls (m2p, sem) show their stated violation. For 19 of the 59 sem controls the violation is not
  the only one (R4-08).

## 3. Reruns (all in my directories)

| What | Command | Result |
|---|---|---|
| proofs-d1c | `PROOFS_OUT_DIR=$RUN_DIR/review-4/proofs-d1c python PC/proofs-d1c/tools/run_proofs.py` | exit 0, gate PASS: 111 verified, 0 errors; 10/10 controls rejected in their file with verified counterexample; sources `2a16c6b07632` = registered |
| proofs-d1d | same | PASS: 118/0, 21/21; sources `24b0330807ea` = round r2 (r1 was `a8b4c625`) |
| proofs-d1e | same | PASS: 115/0, 15/15; `cb604bc3555e` |
| proofs-d1f | same | PASS: 115/0, 16 safety + 1 progress-only control; `fce4cc117e95` |
| proofs-d9b | same | PASS: 158/0, 13/13 safety controls with counterexamples, 2/2 progress-only controls (`progress.rs:192`, `:184`); `f07f7c4d932e` |
| proofs-pa3 | same | PASS: 108/0, 9/9; `599e7da930d8` |
| All six: trust inventory | (from the reruns above) | empty; actors `c03f9fa` scanned |
| core-partition (fork) | binary built into `$RUN_DIR/review-4/core-partition/target`; coverage, union, fidelity and five families (the reviewed family under `locks.sh heavy`; the runner writes into the crate, so it was not used) | coverage-keys rc 0 and its control rc 1; 4 unions rc 0 and union-control rc 1; fidelity rc 0; F1304, liveness-collapsed, dropstatements, F1305 (22/21, 6,893,103 states) and reviewed (21,355,762 states, 266,808,918 transitions, 0 truncated) equal the registered runs. Not rerun: as-built isolation-stmt and the two unpartitioned runs |
| models/semantics (fork) | `cargo run --release --offline -- --out $RUN_DIR/review-4/semantics/RESULTS.json` | 266 of 266 met; identical to the registered RESULTS.json apart from timings |
| `semantics/tools/check_semantics.py` | clean exports | **exit 1** at `e8a0d08a`: "1 violations", `[finding-class] finding F-C1351 has no class`. Exit 1 at HEAD (24). Self-test: base not clean |
| `writesets/tools/check_discharges.py`, `--self-test` | both exports | exit 0, "check: pass"; self-test 19/19 |
| `reflection/tools/check_root_causes.py` | exports | **exit 1** at `e8a0d08a` (12 problems: F-C1350, F-C1351, F-C1850, F-C0450, F-C0151, F-C0150, F-C1150, F-C0670 unassigned; F-C1301 disposition copied wrong; corpus counts). 35 at HEAD. Self-test: 17/17 caught, unmutated not clean |
| `reflection/tools/check_premise_map.py` | exports (pin objects via alternates) | **exit 1** at `e8a0d08a` (debt row D-14 has no entry; detection section stale). 4 at HEAD. Self-test: 15/15 caught, unmutated not clean. `build_test_reflection.py --check`: STALE |
| `tools/intent_check.py`, `--self-test` | both exports | exit 0: "61 decisions, 0 problem(s)"; self-test pass |
| `matrix/build_matrix.py --check` | both exports | **STALE**, 0 problems. At `e8a0d08a` the committed matrix was built from a working tree holding 61 uncommitted run records and the structural lane's uncommitted findings (`registry_runs` 1064 vs 1003 committed; 25 cells carry findings such as F-C0440, F-C0640, F-C1547 that the commit lacks). At HEAD the cells are identical; only `registry_runs` differs (1080 vs 1078) |
| `ontology/tools/ontology_check.py --check` | both exports | **exit 1**: "RED-B1.1: [uncited-finding] F-C1350 ... F-C1351"; INDEX.md stale |
| `tools/check_registry.py` | working tree | 1,080 runs, 0 problems |

These checkers are deliberate ratchets: they fail when a later finding or debt row is not yet classified. That is
not a defect in itself. But the committed tree fails its own gates, the closed cells (`3.3a-*`, `5c-root-causes`,
`3.8-test-reflection`) cite passes taken before, and nothing in `verify.sh` runs the semantics, writesets or
reflection checkers (R4-09).

## 4. Claims audit

**Product versus model.**
- No text describes the product as meeting a property only a model has. Every cell citing `proofs-d9b`, `proofs-pa3`,
  `m2p-*` or `sem-*` is level `model` or `method`, with product label `fails` (3.3-cost: `unknown`).
- The `holds-live` and `holds-inspected` labels exist only on single write-set pairs (114 cells). R4-02 and R4-07 bear
  on them.

**"Paid at model level".** Accurate for the D-1 crates, D-10 and D-13 as model statements. Every crate lists premises
the pin violates, but the D-9 entry rests on a reading the audit rejects, and the lists have the gaps below:

| Claim | Problem (verified by me) |
|---|---|
| D-9 paid: "no tombstone of live content re-verified" (`proofs-d9b/PROOFS.md:112`) | R4-01 |
| `control_f1306_replay_reapplies` located | The counterexample's step d7 applies the replayed properties with `store_apply` as *recorded* content (`cx_f1306.rs:41, :78`). At the pin they are a direct SQL DELETE+INSERT with no ledger record (`ledger/client.py:445-481`). `proofs/PROOFS.md:70` says that modelled as a write "the F-1306 control would pass" (R4-03) |
| d9b "Premises the pin violates" | omits P-D9-3 (`followup-writer-census`; F-C1850, F-C1150 live). The liveness check is assumed to see every row, which F-C1351 violates live, and that premise is unnamed. F-C1301 is still listed as "model" (`proofs-d9b/PROOFS.md:249`) though it is reproduced live (`ws-live-fc1301-delete-reification`) (R4-04) |
| TRUST.md:43 and PROOF-DEBT.md D-13: P-A3 "follows from" / "is a proved consequence" of R11-7/R04-5 | `theorem_pa3_from_guard` (`proofs-pa3/src/adj_l2.rs:2249-2253`) is module 04 only and weaker: a writer and an eraser of g may overlap while the eraser is Locked and the writer is lock-less in flight. In module 11, ledger-bypassing writes of new rows still overlap (`proofs-pa3/PROOFS.md:125-138`). The crate's own text is precise; the account's summary is not (R4-05) |
| Module 00 not applicable (`matrix/orchestrator_status.json:2285, 2292, 2299, 2306`) | "its system-wide invariants are proved in the composed protocols (proofs/, proofs-d9/)". Neither PROOFS.md mentions SYS-I (`grep -c` = 0); the only module-00 result is the explorer check `sem-mc-sys00-*` (mc) (R4-12) |
| D-12 | `control_bound_follows_tail` fails only `progress.rs:184`; 147 non-progress functions verify (`RESULTS.json`). This is accurate. There is no proved counterexample; the claim rests on a located assertion failure |

**Write-set discharges.** The fork sampled about 40 discharges against pin lines, and I re-checked WS-OBL-004, 008, 085,
093, 135 and the INV-replay reason template myself. Justified, for example:
- the SetNodeJSON guard (`Snapshot.cls:95-99`);
- WS-OBL-001 (`LedgerRevision.cls:44, 87-108`);
- WS-GAP-001..003 (`LedgerRedact.cls:345`);
- the migrations' INV-marker and INV-no-live-tombstone pairs by code (`schema.py:1090-1157`).

Unjustified or weak:
- **WS-OBL-093 (R4-02).**
- **The INV-replay template "(journal)" (R4-07).** The 40 INV-replay lemma cells all carry the same reason text. It
  claims a journal observation ("no ^IVG.Ledger node (journal)") that `ws-live-stmt-collision` and `ws-live-stmt-purge`
  do not contain (their logs have no journal section). What holds for these cells is detection by verify()
  (RPL-B7.1), and the writer breaks RPL-B3's own premise.
- **WS-OBL-109 and 125** rest on the two MISMATCH records.
- **The six migration cells** cite `ws-live-migrations`, which was a no-op for those writers ("already at 234",
  backfilled 0). Yet the matrix grades them `registered-run`.
- **The 20 lemma/live cells** cite only runs whose result is `fail`. These are decisive in the builder's sense, so the
  cells are graded `registered-run`.

The 7 open census obligations are stated exactly.

**New findings.**

| Finding | Intended (sources opened) | Evidence | Severity | Note |
|---|---|---|---|---|
| F-C1350 | RED-B1.1, FR-005 (`spec.md:124`), ADR-0013:17, and the product's own entry and Final checks | 12 `ws-live-ins-*` runs (2 of them misstate their INV-replay part) | S1 defensible | the alternative reading is acknowledged in notes; it conflicts with D-9's reading (R4-01) |
| F-C1351 | holds | `ws-live-noindex` | S1 | the %NOINDEX edge residue after `delete_nodes_by_prefix`/EraseAll seen in the two MISMATCH logs is recorded nowhere (R4-06) |
| F-C1850 | mechanism confirmed in code; "intended" partly cites the audit's own HD-1801 working answer | `ws-live-gap-marker` matches | S1 | — |
| F-C0450, F-C0151, F-C0150 | sources correct | logs support them | S2 | F-C0450 would be better cited against INV-stmt than ERS-I2 (S4) |
| F-C1150 | `LedgerRevision.cls:1-5` | the log shows one later commit failing; "every later commit" is inferred | S2 arguable (needs SQL INSERT privilege) | — |
| F-C0670 | `EmbedQueue.cls:22-25`, commit 5bb149ed, HD-0604 | `intent-a-hd0604-queue-claim` (registered **pass** for the stated design) shows two claimants handed the same 3 entries; double processing itself is from source and model | S3 | "reproduced-live" covers the claim overlap only |

None is a duplicate. All remedies are prose.

**Product change in disguise.** None found:
- The probes compile nothing.
- They write product tables only through the product's API or SQL surface, in AUDITB, and reset afterwards.
- No upstream test was patched.
- No oracle was weakened. The INV-replay detection reading (R4-07) is the original submission's own reading
  (`playbook-uplift/semantics/WRITESETS.md:88-90`); it is a labelling issue, not a changed oracle.

**Matrix builder changes (`git log -p 1f7f22fd.. -- matrix/build_matrix.py`).**
- **Evidence-path parsing (`evidence_file`).** It accepts any existing file named first in an annotation, including
  lane JSON inputs (e.g. `modules/10.json invariant_writesets`). That grades 10 cells `inspected` that cite no
  `path:lines` at the pin. This is weaker than CONVENTIONS' "inspected" (S4, R4-15).
- **Discharge application, and `holds-live`/`holds-inspected` set to level product.** R4-02 and R4-07 apply.
- **Census-reopen lift.** It applies only when every census cell of the module is closed, and a finding discharge
  counts as closed while the product label stays `fails`. That is consistent. But the lifted cells keep the old
  reopen sentence: module 11 is `closed` while its text says "1 open per-obligation cells" (S4).
- **Exclusion of cited failed runs for lemma/guard cells** (`build_matrix.py:388`). It is blanket, not pair-specific
  (R4-02).
- **orchestrator_status.json.** 3.7-suites, 3.7-e2e and 3.7-editions are `blocked` with exact dependencies, 5-hygiene
  is `open` and 3.8-review is `open`; these are honest. 3.1-intent is closed by a structural check that says it does
  not judge correctness; that is adequate for the gate's structural text. However, 3.7-perf is `closed` while
  existing baseline configurations were not run, which is inconsistent with 3.7-suites (R4-11).

## 5. Conditions

Each condition gives the exact place and the fix in prose. Severity is for the account. None hides an observed product
failure: every affected product label is already `fails`, or is a holds label that must be weakened.

**Blocking (the audit can fix them).**

- **R4-01 (S2): D-9's no-tombstone result uses a reading that F-C1350 rejects.**
  - Where:
    - `proofs-d9b/src/theorems.rs:26-36`: `theorem_no_tombstone_of_live` ensures only `!rec_content`.
    - `proofs-d9b/src/biz.rs:142-144`: recorded content excludes `unrec` rows.
    - `proofs-d9b/src/biz.rs:70`: a bypass `BBegin` is admitted while the marker exists.
    - `proofs-d9b/PROOFS.md:112`; `PROOF-DEBT.md:18` (D-9 "paid at model level").
    - `findings/audit/zz-writesets.json` F-C1350 notes: that reading "is not the product's", citing FR-005 and the
      product's own entry and Final checks.
  - Consequence: the reviewed design that D-9 "pays" admits F-C1350's S1 behaviour.
  - Fix, either of:
    - (a) qualify the theorem, D-9 and the d9b summary as holding for recorded content only, record that reading as
      intent-undecided against F-C1350's working answer, and say the reviewed design does not exclude F-C1350;
    - (b) add a reviewed guard (Batch re-checks the liveness of every row, or bypass writers honour the marker), with
      a located control and a counterexample reproducing F-C1350.
- **R4-02 (S2): an unjustified product-level `holds-live`, and a blanket builder rule.**
  - WS-OBL-093 (`delete_reification`, INV-replay, `writesets/DISCHARGES.json`) is `holds-live` on
    `ws-live-fc1301-delete-reification`. In both phases of that run the writer's delete was rolled back
    (`tlevel_after_rollback 0`, `content_live_after_rollback True`). The `diverges / unrecorded_writes` it shows comes
    from a completed redaction over restored content, not from the writer's write.
  - `matrix/build_matrix.py:388` ignores every failed run cited by any lemma or guard cell.
  - Fix:
    - regrade WS-OBL-093 to inspected, or rerun its sub-check with a committed delete;
    - make the builder skip a cited failed run only when the discharge names the pair that run failed on;
    - flag cells whose only "live" evidence is a failed run, or a run that did not exercise the pair.
- **R4-03 (S3): the F-1306 control does not model the pin's write.**
  - Where: `proofs-d9b/PROOFS.md:168` (control row), `:247` (violated-premise row) and `cx_f1306.rs:41`.
  - Fix: state that the control models the replayed post-commit properties as recorded content, whereas the pin
    writes them by direct SQL (`client.py:445-481`). Then either re-encode the replay as a Writer step and report what
    fails, or qualify the "located" claim. This is tied to R4-01.
- **R4-04 (S3): "Premises the pin violates" is incomplete.**
  - Where: `proofs-d9b/PROOFS.md:239-251` and `proofs-d9/PROOFS.md:219-225`.
  - Fix:
    - list P-D9-3 as violated (`followup-writer-census`, F-C1850, F-C1150);
    - name the premise "the liveness check sees every row of the target" and list it as violated (F-C1351);
    - change F-C1301 "model" to live (`ws-live-fc1301-delete-reification`), here, in `STATUS.md:63` and in
      `TRUST.md:29`;
    - cite F-C1350 as live evidence for the missing G-B guard.
- **R4-05 (S3): P-A3 is overstated as a proved consequence.**
  - Where: `TRUST.md:43`, `PROOF-DEBT.md:22`.
  - Fix: replace "P-A3 follows from / is a proved consequence of R11-7/R04-5" with the precise statement:
    - module 04: a weakened form, by `theorem_pa3_from_guard` (overlap is allowed before the eraser's DELETE);
    - module 11: only ledger commits are excluded (`er_ok`), and ledger-bypassing writes of new rows still overlap.
- **R4-06 (S3): two misstated records and an unrecorded product behaviour.**
  - Fix:
    - errata for `ws-live-ins-bulkloader_load_edges` and `ws-live-ins-import_rdf` (section 2);
    - rerun import_rdf's INV-replay sub-check from an equal baseline under a new id;
    - record as a finding, or explain, the %NOINDEX edge row that survives `delete_nodes_by_prefix` of both endpoints
      and the following EraseAll+PurgeAll (both logs).
- **R4-07 (S3): what the 40 INV-replay lemma cells actually show.**
  - Fix:
    - say in `writesets/DISCHARGES.json` and the matrix that these cells hold as detection: verify() classifies the
      write (RPL-B7.1), or the write lies outside the replay abstraction, while the writer breaks RPL-B3's
      no-unrecorded-writes premise;
    - remove the "(journal)" clause where the cited run has no journal (004, 008, 024, 064, 105), and note that 008
      ran through the fallback;
    - mark `ws-live-migrations` as context for the six migration cells (it was a no-op for them).
- **R4-08 (S3): "each a violation of exactly its law" is overclaimed.**
  - Where: the 15 PARTIAL `sem-*` records, `semantics/SEMANTICS.md` §2 and §5, and `MECHANISMS.md`'s departure tables.
  - Finding: with `Keep::only` replaced by its complement (`review/review-4/semantics/specificity.txt`), 19 of 59
    controls and 38 of 84 as-built/exception checks also violate another law. 21 as-built checks break a law for which
    their instance declares no departure (`undeclared.txt`).
  - Fix: an erratum, a complement check in the harness, and the departure tables completed or justified.
- **R4-09 (S3): the committed tree fails its own gates, and the entry point does not cover the new work.**
  - Where:
    - `ontology_check.py --check`: RED-B1.1 does not cite F-C1350 or F-C1351; INDEX.md is stale;
    - `check_semantics.py`: F-C1351 is unclassed;
    - `check_root_causes.py`: 8 new findings, plus F-C1301's new disposition;
    - `check_premise_map.py`: D-14, the detection section;
    - `TEST-REFLECTION.md`: stale.
  - Ratchet hole: `reflection/tools/check_premise_map.py:54` hard-codes `PROOF_CRATES`. Its docstring says
    "proofs*/PROOFS.md", but `proofs-d9b` and `proofs-pa3` premises are never checked.
  - `verify.sh` has no step for `proofs-d9b`, `proofs-pa3`, `models/core-partition`, `models/semantics`,
    `check_semantics.py`, `check_discharges.py` or the reflection checkers.
  - The last registered entry-point run is `verify-full-b25d84b9`.
  - Fix:
    - classify and cite the new findings;
    - read the proof crates by glob;
    - add the steps to `verify.sh`;
    - rerun `verify.sh --full` on a committed tree whose matrix is built from that tree alone, and register it.
- **R4-10 (S3): 3.3a-mechanisms is closed though the playbook's proof requirement is unmet.**
  - The playbook requires "generic lemmas proved once over a trait" (`verification-playbook.txt:282`, `:642`). Only
    explorer checks exist (D-14). `matrix/gates.json:28` paraphrases the gate without that requirement.
  - Fix: reopen the cell with D-14 as what remains, or state the explorer substitution in the gate text and in the
    cell's grade.
- **R4-11 (S3): 3.7-perf is closed though baseline configurations were not run.**
  - Where: `matrix/orchestrator_status.json:2350`.
  - The Neo4j/GDS/Memgraph legs, LDBC SNB, the Enterprise/Arno `benchmarks/` scripts and SC-003's target platform
    were not run (`validation/SUITES.md:188-190`). 3.7-suites is `blocked` for the same kind of remainder.
  - Fix: make 3.7-perf `blocked` with the exact dependencies, or split it into a closed cell for the runnable subset
    and a blocked cell.
- **R4-12 (S3): the module 00 not-applicable reason is false.**
  - Where: `matrix/orchestrator_status.json:2285, 2292, 2299, 2306`.
  - Fix: replace "its system-wide invariants are proved in the composed protocols (proofs/, proofs-d9/)" with what
    exists: the axioms are instantiated in the module contracts (model level), model-checked over six composed
    mechanisms (`sem-mc-sys00-*`, mc), and there is no cross-module proof (D-5).
- **R4-13 (S3): STATUS, TRUST and PROOF-DEBT lag the steer-7 lanes.**
  - Fix:
    - `STATUS.md:24`: add `proofs-d9b` (158), `proofs-pa3` (108) and core-partition (D-10);
    - `STATUS.md:25`: replace "3.3a-writesets: 199 open cells" with 178 of 185 discharged and 7 open, and add the
      semantics results, F-C0670 and D-14;
    - `STATUS.md:37-38`: correct the new-finding counts (60, 8 S1 → 68, 11 S1 at `e8a0d08a`);
    - `STATUS.md` S1 table: add F-C1350, F-C1351 and F-C1850, and mark F-C1301 live;
    - `STATUS.md:9` (verdict): cite `verify-full-b25d84b9` or the new run from R4-09;
    - `PROOF-DEBT.md:3`: add `proofs-d9b` and `proofs-pa3`;
    - `PROOF-DEBT.md:18` (D-9 "still open"): add the items in `proofs-d9b/PROOFS.md` §10 (P-D9-5 graph-blind
      replay, the HD-1304 receipt, P-D9b-3, the unreproduced mixed-revision case);
    - F-C1301's `observed` text: stop opening with "Model only".

**Not blocking (S4, recommended).**

- **R4-14: evidence wording.**
  - Copy `proofs-d1b`'s runner summary (count and JSON SHA in the log) into the `proofs-d9b` and `proofs-pa3` runners,
    or add per-record errata.
  - Add one general erratum: "N errors" counts failing functions (the 7 records in section 2).
  - Add errata for the `rf-*` observes beyond their logs, the 22 superseded round-r1 `proofs-d1d-*` records and
    `ws-deploy-auditb`.
  - Give the `proofs-d1c..d1f-recheck` observes their counts.
  - Soften F-C1150's "every later commit" and F-C0670's disposition to what was observed.
- **R4-15: matrix housekeeping.**
  - Remove the stale reopen sentence from lifted census cells.
  - Restrict `evidence_file` grading to `path:lines` at the pin.
  - Name the findings behind the 3.3 `fails` cells (the basis is mostly "stated fails by orchestrator"), cite only a
    module's own controls, and restate module 15's basis (no live-reproduced finding).
  - Fix the "[proofs-pa3]" tag on the m2p supplements and "25+ undeclared writers" (46 in the corrected census).
  - Mark WS-OBL-066 as depending on O-1 (`fc1306-legacy-ledger-rows`).
  - Have `check_discharges.py` verify that a `live` grade cites a run that exercised the pair.
  - Never commit a matrix built from uncommitted lanes' files (as happened at `e8a0d08a`).

**Needs the operator.**
- **O-1 (R2-07).** Unchanged. Pending.

**Needs a maintainer.** Unchanged from the third pass: §3.8's "fix or recorded decision" for every finding, and the
intent-undecided items. Add one: the RED-B1.1 reading behind F-C1350 and R4-01 (is content re-created outside the
ledger after the entry check "live"?).

**Next pass.** Commit `7b72fc52` (structural and product-gates lanes) is unreviewed. Its findings already make
`proofs-d1c/PROOFS.md:201, 213` stale: P-B1 is "not enforced, no observed violation", while F-C0349 shows duplicate keys
from two loaders.

## 6. Sign-off decision

**No sign-off** of the spec against intent for the work in scope.

I will sign off on the account's accuracy for this scope when:
- R4-01 to R4-13 are met;
- a `verify.sh --full` run on the resulting committed tree is registered with every step passing;
- the operator rules on O-1.

That sign-off would cover the account, not the product: the product fails many obligations, as its findings record.
