# Status of the IVG playbook uplift

Product pin `3eaa79cf` (v4.7.0 + checklist). IRIS Community 2026.1 (build 234U) in `ivg-playbook-20261113-iris`.
Reference libraries `G5Labs/actors` at `c03f9fa` (actors, explorer, vecops; the r8 PostgreSQL models were not staged and are
not applicable to IRIS). Verus `0.2026.10.04.426d8b0`. Final reruns: 2026-11-13, logs under `$RUN_DIR/final`.

## What each evidence level means here

| Level | Meaning | Where |
|---|---|---|
| **Proved** | Verus, `--no-cheating`, no trusted items, over the L1/L2 *models* of the reviewed design | `proofs/`, `MODELS.md` |
| **Model-checked (bounded)** | Every reachable state of an executable machine within its declared bounds | `model/`, `MODELS.md` |
| **Observed live** | Seen on IRIS Community in the dedicated container by a scenario or the upstream suite | `native/`, `$RUN_DIR/final` |
| **Tested upstream / ran** | An upstream test asserts it; **ran** when it passed in this uplift's runs | `evidence/test-results.json` |
| **Inspected** | Read in the code at the pin | ontology Evidence column |
| **Assumed** | A named premise, with or without a test | `TRUST.md`, `trust/` |
| **Open** | A decision for the human | `DECISIONS.md`, `decisions/` |

## Phase gates

| Phase | Gate | Result |
|---|---|---|
| §3.1 Uplift (whole product) | `tools/ontology_index.py --check`: parents resolve, grade ≤ 8, terms defined in scope, every evidence reference resolves, every cell defined or assigned | **Pass**: 3,015 statements in 19 modules, 904 cells (29 open, each assigned to the human), self-test 11/11 injected violations rejected |
| §3.2 Environment | IRIS premises observed live; dependency `actors` verified fresh (121 verified, 0 errors) | P-0001..P-0004 observed live; no IRIS environment *model* was built (pgspec does not apply; see Gaps) |
| §3.3 L1/L2, protocol, progress | refinement for every operation; controls rejected; progress | **Pass** for the reviewed design: 53 verified, 0 errors; 6/6 controls rejected in `l2.rs`; bounded progress proved |
| §3.3a Semantics | axioms, mechanisms, lifecycles, write-set obligations | `semantics/`: 83 obligations generated, all covered, **17 open** (covered only by a finding) |
| §3.4–3.6 Storage lemmas, handlers, composition | — | **Not done** (no generated statements; the code is ObjectScript); see Gaps |
| §3.7 Validation | explorers, live worlds with interruption and races, upstream suites, trace checks | 11/11 model checks met; 14/14 live scenarios (225 checks) passed; 3/3 ObjectScript mutants killed live; upstream spec 256 e2e on Community 25/25 twice; unit set 24,579 passed with 87 environment failures triaged |
| §3.8 Account | status, trust inventory, test reflection, reviewer | this file, `TRUST.md`, `TEST-REFLECTION.md`; independent review: no sign-off on the first pass; every finding fixed or recorded; **sign-off** on the second pass (`REVIEW.md`) |

## The worked example: guarantees and their status at the pin

"Holds" means the code at the pin does it; "fails" means a finding with a reproduction. Proofs and bounded model passes are
about the reviewed design unless the row says otherwise.

| Guarantee (statement) | Proved | Model-checked | Live | Status at the pin |
|---|---|---|---|---|
| Erasure keeps every record (ERS-B1.3) | — | — | yes | Holds |
| Erasure is all or nothing (ERS-I1) | — | — | upstream test (not run here); P-0001 live | Holds (inspected) |
| No statement entry outlives its edge (ERS-I2) | — | reviewed passes | yes (every step of every scenario) | Holds in all observed runs |
| No recorded live edge loses its statement entry (ERS-I3) | — | as-built fails, reviewed passes | not reproduced | **Fails** under a concurrent commit (F-1201) |
| Erasure alone makes replay differ from the store (ERS-B3, RPL-B4) | `theorem_erasure_alone_diverges` | — | yes | Holds |
| Redaction is refused while the target is live (RED-X1) | — | — | yes (upstream and scenarios) | Holds for the check itself |
| Redaction never tombstones live content (RED-B1.1) | reviewed: `theorem_begin_spares_live` + refinement, assuming no erasure open at start (P-1311) | as-built fails (3 steps), reviewed passes (11.35 M states) | **violation reproduced** | **Fails** (F-1302) |
| A default-graph target without prefix spares named-graph nodes (RED-X2) | — | — | **violation reproduced** | **Fails** (F-1304) |
| A tenant in its own graph can be fully redacted (RED-B1.2) | — | — | **cannot**, reproduced | **Fails** without id prefixes (F-1305) |
| Shape kept; other records byte-identical (RED-I1, RED-I2) | `theorem_l2_satisfies_l1`, `theorem_isolation` | reviewed passes | yes (byte comparison, independent oracle) | Holds in all observed runs |
| Tombstone keeps a recomputable digest (RED-B2.1/2.2) | — | — | yes (recomputed) | Holds; rests on P-1302 |
| Any tombstone clears the revision's free text (RED-B3) | yes (control for FR-004 wording rejected) | reviewed passes | yes | Holds; spec FR-004 says otherwise (F-1301) |
| A redacted retry key never saves or replays (RED-B4) | `theorem_retry_refused` | reviewed passes | yes, incl. the other tenant's shared key | Holds |
| A retry between erase and redact does not revive content (RED-B4.3) | — | as-built fails, reviewed passes | **violation reproduced** | **Fails** (F-1306) |
| A marked target refuses commits into it (RED-B5) | yes | reviewed passes | yes | Holds once the marker exists |
| One target at a time (RED-B6, RED-B6.1) | reviewed only | as-built fails (7 steps) | **both ran; audits mixed** | **Fails** for runs that start together (F-1303) |
| Audit revision is content-free and per-target (RED-B7, RED-B7.1) | — (L2 has no counts) | as-built fails | content-free: yes; per-target: **fails** (10/6, 14/2, 1/15 vs 9/7) | Content-free holds; counts fail (F-1303) |
| A stopped run leaves the last batch boundary and resumes (RED-I3, RED-B8) | resumption: `theorem_run_can_step`; batch atomicity is assumed (P-0001) | — | yes (stopped inside a batch; 6 random stops) | Holds |
| A run takes bounded steps without new commits (RED-B8.1) | `theorem_run_bounded` | — | — | Proof only; premise P-1306 otherwise |
| Erase then redact makes verify equal (RPL-B3) | `theorem_erase_then_redact`, `theorem_commit_between`, for separable targets with one scope (P-1301, P-1310) | reviewed: "replay equals store once settled" | yes, six scenarios; **fails** in the F-1305 world | Holds where P-1310 holds and no unrecorded writes; **fails** for unprefixed tenants in their own graph |
| Verify says equal when every change went through the ledger (RPL-B7) | — | — | **violation reproduced** (upstream fixture world) | **Fails** after a detach delete with named-graph edges (F-1401) |
| Readers never see a half-done redaction (RPL-I1) | — | as-built fails (4 steps), reviewed passes | **violation reproduced** (reconstruct) | **Fails** (F-1402) |

Model assumptions, not observed: P-1201 (row locks), P-1306 (commits pause), P-1307 (operator resumes), P-1309 (out of
reach), P-1401 (quiet verify). Observed live: P-0001..P-0004, P-1301 (oracle agreement), P-1302 (digest recomputation).

## Breadth (§3.1) summary

19 modules, 3,015 statements: 338 definitions, 1,160 business rules, 822 technical rules, 149 invariants, 364 refusals,
105 premise statements, 58 open questions; 138 named premises and 61 decisions for the human. Evidence: 2,922 statements cite production code; 1,220 cite an upstream test, of which 665
cite a test that passed in this uplift's runs; 234 carry a finding; 198 rest on a premise; 60 wait on a human decision;
8 are documented but not implemented. Findings: 197 across the modules (`FINDINGS.md`, `findings/NN.md`), each with
evidence and what would close it. Only modules 12–14 carry proved, model-checked or live evidence; the breadth modules were
built by reading code and upstream tests (their findings are inspection findings unless stated otherwise).

## Gaps

- No IRIS environment contract (the playbook's §3.2 library step): the IRIS behaviours used are named premises, four observed
  live. pgspec models PostgreSQL and does not apply.
- No storage lemmas, handler proofs or composition theorem over the ObjectScript (§3.4–3.6); the code is tied to the models by
  controls, as-built model designs and live traces only.
- ObjectScript mutation testing covers three guards only (`native/mutants.py`: commit block, final re-check, retry key; all
  killed live, pin restored and rerun clean); no `-m perf` run (SC-002, SC-003); no IRIS Enterprise run.
- Protocols are not written as `actors::protocol::Protocol2`: erasure, ledger and readers are composed inside one L1/L2 machine
  and four small explorer machines.
- F-1201 is a model result only (not reproduced live).
- The breadth modules' findings (outside 12–14) are from reading code; none was reproduced live.
