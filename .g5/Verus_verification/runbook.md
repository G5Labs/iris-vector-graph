# IVG Verus foundation — runbook

Initial uplift of iris-vector-graph at product baseline `3eaa79cf77d3e0a879b2cced634cf2729d81499e` (v4.7.0). The project had no verification tree; this foundation lives under `.g5/Verus_verification/` beside the [ontology](../ontology/root.g5.md). Plan, assignments and the review-round counter: [uplift plan](../uplift/ivg-verus-initial/uplift-plan.md). Claims and their status: [coverage map](coverage.md). Product findings: [findings register](findings.md).

Nothing here verifies the product's own executable bodies. The product is ObjectScript and Python; the Verus models are source-bound transcriptions of the as-built mechanism (L2) checked against business rules (L1), and native observations on IRIS connect them to the real operations (L3). No statement is tagged `implementation-verified`.

## Pins

| Item | Value |
|---|---|
| Product | baseline above; worktree HEAD at start `0e441f1c` (differs only under `.agents/`, `experiment/`) |
| Verus | `0.2026.10.04.426d8b0` (commit `426d8b01`), `$VERUS_BIN` from `experiment/g5-verus/environment.sh`; Z3 4.16.0; rustc 1.98.1. Hashes in [SOURCE.json](SOURCE.json). |
| Libraries | bundled vstd only. G5Labs/actors, pgspec and the bank explorer are not used (see SOURCE.json for why). bank-of-ziniu pins Verus `0.2026.09.27`; not used by these models. |
| IRIS | container `ivg-g5-verus-20261113-iris`, `127.0.0.1:35972`, namespace `USER`, Community Edition; schema deployed by `engine.initialize_schema()` (the three `%AI` MCP classes are skipped) |
| Python | `$RUN_DIR/venv` (uv, from `uv.lock`), CPython 3.11.18 |

## Environment

```sh
cd ~/experiments/iris-vector-graph-g5-verus-20261113/iris-vector-graph
source experiment/g5-verus/environment.sh      # RUN_DIR, VERUS_BIN, IVG_* for this arm only
export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=$RUN_DIR/pycache
```

Raw logs and scratch output go to `$RUN_DIR` (`~/runs/iris-vector-graph-g5-verus-20261113`): `verus/` (Verus logs, control copies, the compiled twin), `native/` (probe observations), `tests/` (upstream suite logs). Receipts with input hashes are kept under `results/<model>/<stamp>-<label>/receipt.json` (final candidate; the viewer's layout). Earlier receipts of this uplift are preserved under `receipts/<model>/`, and earlier native observations under `receipts/native/earlier/`.

## On this machine (consolidated uplift, 2026-11-14)

The commands below run on the consolidating Mac (arm64) and need no IRIS. The section after this one is the guidance arm's original runbook; its proof and control steps run here unchanged with the variables below, while its native steps (4 and 6) need that arm's IRIS. Provenance of this machine's toolchain: [SOURCE-consolidated.json](SOURCE-consolidated.json). Handoff: [HANDOFF](../uplift/consolidated/HANDOFF.md).

```sh
export IVG_REPO=$PWD RUN_DIR=$HOME/runs/ivg-consolidated-20261114
export VERUS_DIR=$HOME/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos VERUS_BIN=$VERUS_DIR/verus
export ACTORS_DIR=$HOME/.cache/g5-verification/ivg-actors-c03f9fa G5_GUIDE=/Users/ziniuw/Desktop/research/G5-Lean-V2/.agents/guidance
export PATH=$VERUS_DIR:$PATH VERUS_RUN_THREADS=4 PYTHONDONTWRITEBYTECODE=1
mkdir -p $RUN_DIR/pin && git archive 3eaa79cf | tar -x -C $RUN_DIR/pin          # the exported pin, for bindings
(cd $RUN_DIR/pin && UV_PROJECT_ENVIRONMENT=$RUN_DIR/venv uv sync --frozen --all-extras)
```

**One real obligation end to end (guidance arm): tenant redaction.** `python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/ledger_redaction` → `PASS (41 verified, 0 errors)` in seconds; `CONTROL=no-blockscommit python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/ledger_redaction` → `no-blockscommit EXPECTED_FAIL`. Each receipt now carries a copy of its raw log under `logs/`.

**One new contract end to end: the paged temporal window reader** ([NOTES](models/temporal_window_reader/NOTES.md)).

1. Proof: `python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/temporal_window_reader` → `PASS (16 verified, 0 errors)`.
2. One control: `CONTROL=stop-on-empty-page python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/temporal_window_reader` → `stop-on-empty-page EXPECTED_FAIL` (fails in `lemma_drain`); all eight: omit `CONTROL` (about 10 s).
3. Product comparison: `$RUN_DIR/venv/bin/python -I .g5/Verus_verification/models/temporal_window_reader/binding.py` → `AGREES (640 cursor + 45 window_spec comparisons, 0 mismatches; detection {... all True})`; receipt `results/temporal_window_reader/<stamp>-binding/receipt.json`.
4. The other new contracts the same way: `freshness_stamp`, `embedded_no_data`, `rel_prop_text`, `index_declaration` (each has `binding.py`).

**A playbook-arm crate:** `python3 .g5/Verus_verification/tools/run_playbook_crate.py proofs-d1e baseline control_f1004_create_moves_no_token` → `PASS (115 verified …; record match: True)` and `EXPECTED_FAIL (114 verified, 1 errors; record match: True)` with errors at `src/acache_l2.rs:188-189`. It archives the crate from `2d59e578` into `$RUN_DIR/pb`, changes only the two dependency lines, cleans the package, and runs `cargo verus verify --offline --fwd-verus-args-to roots [--features F] -- --no-cheating --triggers-mode silent`. `--all-controls` runs every control the crate's Cargo.toml names.

**The gate:** `python3 .g5/Verus_verification/tools/check_consolidated.py` → `PASS` (confinement, inherited model hashes, freshness incl. bindings and playbook reruns, the G5 ontology and findings checkers, the register ratchet, the four crosswalks and the code links). Regenerate derived files with `tools/make_crosswalk.py`, `make_statements.py`, `make_families.py`, `make_findings_index.py`, `inventory.py` (each idempotent).

## Improvement iteration 1 on this Mac

Current handoff: [iteration-1/HANDOFF.md](../uplift/consolidated/iteration-1/HANDOFF.md). New families use only bundled vstd; the imported actors checkout/pins are unchanged and were not reverified this round.

```sh
export IVG_REPO=/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph
export RUN_DIR=/Users/ziniuw/.cache/g5-verification/ivg-iteration-1-20261115
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin
export IVG_PYTHON=/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export VERUS_RUN_THREADS=4 PYTHONDONTWRITEBYTECODE=1
cd "$IVG_REPO"
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/node_read
CONTROL=omit-final-column-decode python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/node_read
"$IVG_PYTHON" -B -I .g5/Verus_verification/models/node_read/binding.py
```

Expected: **13 verified / 0 errors**, control **EXPECTED_FAIL** in `theorem_sql_scalar_read_reaches_result`, binding **AGREES / 90 comparisons**, exact scalar result `[float 0.95, int 29, str "0.95"]`, alias collision witness present and four detection checks true. The binding reads writer-bound values, uses the real translator's typed-column metadata, and runs the real final result finisher. IRIS storage, transactions and CY_TYPED are substituted. Proof/control receipts retain raw logs; binding receipts retain mismatches/detection, input hashes and pin identities.

Repeat the prove/controls pattern for `ndjson_import` (9 / 4 controls), `route_recheck` (6 / 3), `warm_sources` (7 / 4). Run `binding.py` for the first two (73 sequences; 1,092 comparisons). `warm_sources` has no Python binding: ObjectScript observation remains pending. Omit CONTROL to run each complete control suite. The first five model roots, imported trees and historical receipts remain immutable.

Replay the exact final product suite command from [upstream-unit.json](../uplift/consolidated/iteration-1/upstream-unit.json), with cwd `$IVG_PIN_DIR`: expected **383 passed, 4 skipped**. Product pin source hashes are checked by the bindings; the full consolidated gate checks confinement. Final gates: `python3 .g5/Verus_verification/tools/check_consolidated.py` and `git diff --check`.

## One real obligation end to end: tenant redaction

Obligation: [redaction](../ontology/features/redaction.g5.md) — after erasure, redaction turns every record of the target into its tombstone in place, leaves every other record byte-identical, clears the four metadata fields of each revision it touched, unbinds those revisions' idempotency keys, appends one content-free redaction revision, and makes `verify()` equal again.

1. **Proof** (expected: `PASS (41 verified, 0 errors)`, receipt under `results/ledger_redaction/<stamp>-prove/`):

   ```sh
   python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/ledger_redaction
   ```

   Model: [redaction.rs](models/ledger_redaction/redaction.rs) ([NOTES](models/ledger_redaction/NOTES.md)). Key results: `lemma_batches_compose`, `lemma_rescan_is_harmless` (within one call's fixed knowledge `K()`), `lemma_step_preserves_inv` (serialised redactions), `theorem_completion`, `theorem_redacted_key_refused`, `theorem_step_frame`, the commit-admission theorems (`theorem_retry_replays_first`, `theorem_redacted_key_refused_before_apply`, `theorem_commit_writes_only_when_admitted`), `theorem_replay_skips_target`, `theorem_replay_independence`, `theorem_verify_equal_after_redaction`, the erase frame `lemma_erase_stays_in_target_graph` / `lemma_erase_keeps_other_graphs`, and the witnesses `witness_*` (W1 concurrent targets, W2 temporal-only, W3 whole default graph through `Erase`, W4 unattributed qualifier, W5 prefix erase leaves temporal-only events, W6 an orphan property row blocks prefix redaction, the BlocksCommit control trace). `lemma_serial_resume_keeps_attribution` and `witness_race_then_resume_loses_attribution` are classification facts about `Matches` under a given knowledge, not traces of the lifecycle (whose knowledge `K()` is one constant): resume across calls is **observed** natively (`redaction_interrupt_resume`, `redaction_prefix_resume`), not proved.

2. **Faulty controls** (expected: 16 lines, every one `EXPECTED_FAIL`; about 2 minutes):

   ```sh
   python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/ledger_redaction
   CONTROL=no-blockscommit python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/ledger_redaction   # one control
   ```

   Each control applies one textual change from [model.json](models/ledger_redaction/model.json) to a copy in `$RUN_DIR/verus/ledger_redaction/controls/<name>/` and requires the named functions to fail when verified alone. `no-blockscommit` removes LedgerRedact.BlocksCommit from the commit admission and must break `lemma_step_preserves_inv`.

3. **Executable twin** (expected: `51 verified, 0 errors`, binary written; last build receipt `results/ledger_redaction/<stamp>-twin/receipt.json`):

   ```sh
   (cd .g5/Verus_verification/models/ledger_redaction && $VERUS_BIN twin.rs --num-threads 4 --compile -o $RUN_DIR/verus/twin/twin)
   ```

   [twin.rs](models/ledger_redaction/twin.rs) holds exec functions proved equal to the model's `match_string`, `has_prefix` and `matches`; its line adapter (`main`) is unverified and trusted.

4. **Product observation** (expected: `redaction_binding: OBSERVED_AS_EXPECTED`):

   ```sh
   python3 .g5/Verus_verification/native/probes/redaction_binding.py
   ```

   Builds a two-tenant world through the public Python API on this arm's IRIS, erases tenant A, snapshots every ledger record and its canonical form, classifies each record with the twin and with the probe's own attribution, runs the two redaction calls, and compares every record, revision row, idempotency binding, the audit revisions and `verify()`. Two observation-mutation controls (a changed value; a changed digest) must be detected. The raw observation is written to `$RUN_DIR/native/redaction_binding-<stamp>.json`.

5. **Freshness gate** (expected: `FRESH`, exit 0; after editing any model or probe file, a `STALE/WRONG: …` line and exit 1):

   ```sh
   python3 .g5/Verus_verification/tools/check_evidence.py
   ```

   It checks every model's latest prove receipt and the latest receipt of each control in its `model.json` against the current input files, and every native observation in `receipts/native/` against the probe, helper and harness hashes it recorded. To exercise it without touching the foundation, copy `.g5/` to a scratch directory, edit one probe or model there and run it from that directory (done during the uplift on a scratch copy: 31 stale items reported, exit 1). `run_verus.py fresh <receipt>` checks one receipt.

6. **Distinguishing control on the product** (expected: `redaction_concurrent_targets: OBSERVED_DEFECT`, or `INCONCLUSIVE` if the long commit finishes before both redactions start): `python3 .g5/Verus_verification/native/probes/redaction_concurrent_targets.py`. It is the native counterpart of control `start-ignores-other-marker` / witness W1: both redactions pass their entry checks while an ordinary 12,000-op commit holds the head lock; the as-built product lets both run (bug-001).

**Reproducing without changing the foundation.** `run_verus.py` writes new receipts under `.g5/Verus_verification/results/` and control copies under `$RUN_DIR`. A reviewer who must not change the foundation copies `.g5/` to a scratch directory, sets `RUN_DIR` to a scratch path, and runs the commands there (review round 2 did this).

**What the receipts bind.** Model receipts hash the model and `model.json`; native observations hash the probe, its helper and the harness and name the product baseline commit. They do not hash product files: applicability to the product rests on the baseline commit and the confinement check (no product file changed during the uplift; `git status` and `git diff 3eaa79cf` in the [final report](../uplift/ivg-verus-initial/final-report.md#8-confinement-check)). The twin build receipt records the binary's SHA-256; the binding probe uses `$RUN_DIR/verus/twin/twin`.

## Other models

Each model directory has a root `.rs`, `model.json` (expected count and controls) and `NOTES.md` (obligations, bindings, premises, trust inventory, findings). The same two commands apply: `python3 .g5/Verus_verification/run_verus.py prove|controls .g5/Verus_verification/models/<model>` with `VERUS_RUN_THREADS=4`. Expected: graph_structure 67 / 22 controls, temporal 113 / 33, search 56 / 27, platform 51 / 30, every control `EXPECTED_FAIL`. A full control run of temporal or search takes longer than 10 minutes; use `CONTROL=<name>` to run one.

## Native checks

Every probe under `native/probes/` drives only public product entry points on this arm's instance, through the identity-checked [harness](native/harness.py), resets the namespace's graph and ledger content first, derives its expectation independently of the implementation and prints `OBSERVED_AS_EXPECTED`, `OBSERVED_DEFECT` or `INCONCLUSIVE`. Observations land in `$RUN_DIR/native/<probe>-<stamp>.json` with the SHA-256 of the probe, its helper and the harness (`_probe_inputs`); copies of the final-candidate observations are in [`receipts/native/`](receipts/native). Run probes one at a time: they share one IRIS namespace, and Community Edition allows only a handful of connections (concurrent probes and scratch-namespace suites hit "Unable to allocate a license").

## Upstream suites against the original product

```sh
python3 .g5/Verus_verification/native/run_upstream.py tests/unit -p no:randomly
python3 .g5/Verus_verification/native/run_upstream.py tests/integration/<file>.py -rfEs      # one file at a time
```

`run_upstream.py` generalises `experiment/g5-verus/run-community-redaction.py`: it replaces only the session fixture that compiles `%AI` classes with `engine.initialize_schema()`. That replacement records width 768 in the namespace, so tests that build width-4 engines and call `initialize_schema()` fail with `EmbeddingIdentityConflict` in this harness; probes use width 768. Results, counts and triage: [coverage map](coverage.md#native-suites-baseline-3eaa79cf-this-arm).

## Results

The [coverage map](coverage.md) holds every claim's status (Proved / Observed / Violated / Suspected / Assumed / Open). Product findings: [findings register](findings.md). Plan, review rounds and adjudications: [uplift plan](../uplift/ivg-verus-initial/uplift-plan.md). Final report: [final-report.md](../uplift/ivg-verus-initial/final-report.md).


## Improvement iteration 2 on this Mac

Run from `/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph`. Only `.g5/` artifacts change. The product export and Python environment are reused from the inspected immutable pin; each binding checks file identity. Verus remains `0.2026.10.04.426d8b0`, bundled vstd only for new models. The actors snapshot remains an untouched inherited dependency.

```sh
export RUN_DIR=/Users/ziniuw/runs/ivg-iteration2-20261115
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export G5_GUIDE=/Users/ziniuw/Desktop/research/G5-Lean-V2/.agents/guidance
export PYTHONDONTWRITEBYTECODE=1
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/reconstruction
CONTROL=final-size-only python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/reconstruction
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python .g5/Verus_verification/models/reconstruction/binding.py
python3 .g5/Verus_verification/tools/inventory_controls.py
python3 .g5/Verus_verification/tools/check_consolidated.py
```

Expect 11 verified / zero errors; the final-size-only control fails theorem_transient_oversize_refuses; Python AGREES on 7,020 count/content cases and the actual streaming/export survivor journey. This is a model proof and Python unit correspondence with substituted SQL/meta, not an IRIS or implementation proof. Latest receipts/raw proof logs are under results/reconstruction/. Replace reconstruction with ledger_apply (9/5), fusion_ranking (11/6) or bulk_delete (10/5) and omit CONTROL to run its full control suite. The ledger binding expressly does not execute its ObjectScript producer.

The upstream 13-file regression command and cwd are in [upstream-unit.json](../uplift/consolidated/iteration-2/upstream-unit.json); expected 314 passed. See [iteration 2 handoff](../uplift/consolidated/iteration-2/HANDOFF.md) for limits and review attacks.

## Improvement iteration 3 on this Mac

Run the named-reader producer challenge end to end:

```sh
cd /Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph
export RUN_DIR=/Users/ziniuw/runs/ivg-iteration3-20261115
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export G5_GUIDE=/Users/ziniuw/Desktop/research/G5-Lean-V2/.agents/guidance
export PYTHONDONTWRITEBYTECODE=1
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/history_diff
CONTROL=drop-delete-snapshot python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/history_diff
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python .g5/Verus_verification/models/history_diff/binding.py
python3 .g5/Verus_verification/tools/check_consolidated.py
```

Expect **12 verified / zero errors**, the control failing
`theorem_simple_delete_preserves_snapshot`, Python AGREES on **9481 named pairs**
with **8113 continuous endpoint comparisons**, and gate PASS. The binding prints
the receipt holding both simple and stronger snapshot observations. No IRIS runs.
Omit CONTROL to run all six controls. Substitute pagerank_admission (9/6),
aql_frontend (6/4), or vector_threshold (6/3) for the other proofs/controls/bindings;
their NOTES name every provider and formal gap. Vector uses adapted SQLite,
PageRank normalized fixture rows are not an ObjectScript numerical check, and
AQL ends at a recorded Cypher handoff.

The [iteration 3 handoff](../uplift/consolidated/iteration-3/HANDOFF.md),
[sample](../uplift/consolidated/iteration-3/PAIRS.md) and
[upstream command/log](../uplift/consolidated/iteration-3/upstream-unit.json)
retain the sealed scope, inputs and limitations. Expected upstream result:
164 passed, no skips. Independent review remains pending.

## Improvement iteration 4 on this Mac

[Checkpoint and limits](../uplift/consolidated/iteration-4/HANDOFF.md).
From `/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph`:

```sh
export RUN_DIR=/Users/ziniuw/runs/ivg-iteration4-20261115
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export VERUS_RUN_THREADS=4 PYTHONDONTWRITEBYTECODE=1
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/edge_acceptance
CONTROL=caller-marker-discarded python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/edge_acceptance
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/edge_acceptance/binding.py
python3 .g5/Verus_verification/tools/correspondence_gate.py check .g5/uplift/consolidated/iteration-4/correspondence-inputs.json
python3 .g5/Verus_verification/tools/member_reach.py --out "$RUN_DIR/reach-replay"
python3 .g5/Verus_verification/tools/check_consolidated.py
```

Expected 7 verified; the control fails theorem_caller_marker_retained; binding
AGREES56 with both detections true. Omit CONTROL for all six. Proof-input and
product-input mutation witnesses are in iteration-4/freshness-controls.json.
The source reverse lookup is after-reach/bindings.json keyed by path::symbol;
NOTES.md gives each formal role and its narrower evidence. Added product writers
reopen correspondence globally while leaving unchanged theorem inputs reusable.

## Improvement iteration 5 on this Mac

[Checkpoint](../uplift/consolidated/iteration-5/HANDOFF.md), family NOTES and
validation.json name source/role/receipt boundaries. Use the iteration4 Verus/Python
pins, RUN_DIR=/Users/ziniuw/runs/ivg-iteration5-snapshot-20261115 and IVG_PIN_DIR
pointing at the exported pin. From the repository root:

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/bulk_children
CONTROL=orphan-cleanup-omitted python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/bulk_children
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/bulk_children/binding.py
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/snapshot_routes
CONTROL=parent-merge-uses-graph-key python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/snapshot_routes
IVG_SNAPSHOT_NATIVE=1 /Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/snapshot_routes/binding.py
IVG_SNAPSHOT_NATIVE=1 /Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/uplift/consolidated/iteration-5/bulk-native.py
python3 .g5/Verus_verification/tools/correspondence_gate.py check .g5/uplift/consolidated/iteration-5/correspondence-inputs.json
python3 .g5/Verus_verification/tools/check_consolidated.py
```

Bulk expected30 verified/11 controls/AGREES140; snapshot14/10/AGREES11.
Omit CONTROL for each complete suite. Native commands mutate ONLY the task's
hostname-checked ivg-uplift-next-20261115 on loopback35975, namespaceUSER. They
require this iteration's initialized isolated runtime; creation/setup/error records
are native-setup.* and root-attempts.md. Do not run them concurrently or against a
sibling service. Before replaying on a stopped retained container, start that exact
container and run native-setup.py if classes are absent. The scripts refuse wrong
identity. Their state is disposable; archives/raw results persist outside it.
The compiled-index catalog observations do not prove arbitrary commit-failure
semantics. Member reverse lookup: iteration5/after-reach/bindings.json.

## Improvement iteration 6 on this Mac

[Checkpoint](../uplift/consolidated/iteration-6/HANDOFF.md) and family NOTES name
exact provider limits. Reuse iteration4 Verus/Python pins and a new isolated RUN_DIR.

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/temporal_restore
CONTROL=zero-start-export python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/temporal_restore
IVG_TEMPORAL_NATIVE=1 /Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/temporal_restore/binding.py
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/history_paging
CONTROL=converted-cursor-truthiness python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/history_paging
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/history_paging/binding.py
python3 .g5/Verus_verification/tools/correspondence_gate.py check .g5/uplift/consolidated/iteration-6/correspondence-inputs.json
python3 .g5/Verus_verification/tools/check_consolidated.py
```

Expected31 total/7 controls/AGREES7 native and20/13/AGREES6080. Omit CONTROL
for complete suites. Run native scripts serially on the guarded iteration5 isolated
instance. History iteration6/history-*-native.py retains actual writer evidence.
Additional model inputs are stamped and each control keeps its dependency tree.

## Improvement iteration 7 on this Mac

[Checkpoint](../uplift/consolidated/iteration-7/HANDOFF.md), individual handoffs and
family NOTES provide exact source roles/domain. Reuse iteration4 tool pins,4 threads
and a fresh RUN_DIR. From the repository root:

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/temporal_clock
CONTROL=bulk-preserves-zero python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/temporal_clock
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/procedure_results
CONTROL=physical-return-validates-source python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/procedure_results
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/service_health
CONTROL=cached-failure-clears-engine python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/service_health
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/temporal_clock/binding.py
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/procedure_results/binding.py
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/service_health/binding.py
python3 .g5/Verus_verification/tools/correspondence_gate.py check .g5/uplift/consolidated/iteration-7/correspondence-inputs.json
python3 .g5/Verus_verification/tools/check_consolidated.py
```

Expected56/16/AGREES1564(+5scenarios),19/10/AGREES6580,18/13/AGREES84.
Omit CONTROL for complete suites. Native supplements timestamp-native.py and
procedure-native.py require IVG_TEMPORAL_NATIVE=1 and only the guarded iteration5
runtime; run serially. Copy their scripts/outputs to a fresh replay evidence folder
before rerunning, to preserve sealed original JSON paths. posteffect-native.py is
next-model discovery evidence, not current formal credit or a real network fault.

## Improvement iteration 8 on this Mac

[Checkpoint](../uplift/consolidated/iteration-8/HANDOFF.md) and individual NOTES
retain exact commands. With inherited tool pins/4threads/fresh RUN_DIR:

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/retry_replay
CONTROL=fallback-resumes-tail python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/retry_replay
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/fhir_tasks
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/fhir_tasks
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/retry_replay/binding.py
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/fhir_tasks/binding.py
python3 .g5/Verus_verification/tools/correspondence_gate.py check .g5/uplift/consolidated/iteration-8/correspondence-inputs.json
python3 .g5/Verus_verification/tools/check_consolidated.py
```

Expected70/9/AGREES872 and27/19/AGREES731+extras. Unknown CONTROL errors with2.
Native fhir-native.py/fhir-id-native.py/fhir-name-native.py require the guarded own
instance and IVG_TEMPORAL_NATIVE=1. Preserve sealed paths: copy scripts into a new
.g5/uplift/consolidated/replay8-YYYYMMDD directory (same nesting level), so outputs
and source-relative guard remain correct; run serially. They create/delete only
unique owned fixtures; inspect final cleanup. No actual FHIR repo, namespaceguard
setup acceptance, SQL-fault, background or transport proof is implied.


### Iteration 9: raw weighted search and Bolt stream

Current continuation: [iteration9 handoff](../uplift/consolidated/iteration-9/HANDOFF.md), then iteration10 Cost/PPR. Replay `.g5/Verus_verification/run_verus.py prove` or `controls` with model directory `models/weighted_paths` or `models/bolt_stream` (use full repository-relative model path), explicit VERUS_RUN_THREADS=4 and pinned VERUS_BIN. The weighted and Bolt NOTES give exact commands, provider fragments and named controls. Binding scripts use the pinned venv/export and forbid socket connects; native scripts separately require IVG_TEMPORAL_NATIVE=1 and hostname-check the task-owned35975instance. Do not point them at another instance. No product-body proof or DijkstraCost proof is inferred from native agreement.

`check_evidence.py` checks the latest fresh proof/control/binding. Weighted integration flattened its already-recorded native/source hashes into `inputs`, so changed native fact artifacts invalidate that package binding; global `correspondence_gate.py` separately checks source/formal/name/link inputs. The nine disposable iteration9 freshness cases demonstrate both layers without mutating active inputs. External provider/runtime freshness is a named premise. `member_reach.py` gives188/4130 active named behavior locators, directbody0; observation rows do not earn reach.


## Iteration10 replay and continuation

Current [iteration10 handoff](../uplift/consolidated/iteration-10/HANDOFF.md) continues into11. Replay `python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/weighted_cost` or `controls` and likewise `models/ppr_walk`, with VERUS_RUN_THREADS=4 and pinned VERUS_BIN. Weighted Cost imports the unchanged weighted_paths model, so88 includes45 rechecked units. PPR103 is all new. Run each binding.py using the pinned venv/export and PYTHONDONTWRITEBYTECODE=1. NOTES define exact domains, provider premises, controls and raw receipts. No whole native body or arbitrary numerical refinement follows.

Root native scripts require IVG_TEMPORAL_NATIVE=1 and guard the owned35975 instance; never substitute another runtime. Prior setup5/source-export correspondence is reused explicitly. The PPR native fallback is a direct actual private-method call; physical missing-provider public dispatch is not established. Scratch PPR replay may require the narrowly audited inherited artifact-prefix alias documented in ppr-review-final.md; do not silently rewrite source/native evidence.

The latest global correspondence-inputs.json is iteration10; package flat inputs separately cover native facts. Eleven disposable freshness tests in iteration10/freshness-probe.py do not alter active inputs. member_reach.py gives197/4130 active named locators, direct-body0. Native/provider freshness and whole-member semantics remain separate judgments.


## Iteration11 replay and continuation

Current [iteration11 handoff](../uplift/consolidated/iteration-11/HANDOFF.md) continues into12. Replay pinned Verus with VERUS_RUN_THREADS=4 via `python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/weighted_fraction` or `controls`, and likewise `models/vector_admission`. Rational181 includes88 unchanged imported units; vector77 all new. NOTES specify commands, provider frames and control classes. Source companions must be declared additional_inputs; vector has parser/json_width/catalog/numbers. Run bindings with pinned venv/export and PYTHONDONTWRITEBYTECODE=1, never rerun native scripts from a reviewer or unguarded runtime.

Root native scripts use only the hostname-guarded35975 task runtime. Controlled seed5 injects one generic first-score provider exception; native subsequent scores are actual, no organic outage. No universal Double/metadata/kernel/body proof follows. The final fractional comparison helper excludes tag2; vectorV2 captures original registry/graph/model/node-kind/TTL while clocks/replies vary. Exact V1 versions are archival, superseded where stated.

All21 package controls have full and named ordinary failures; separate reviewer TTL challenge is additional, not22controls. New units170=116proof+35recursive+19nonlinear subqueries, imports88 separate. The independent PPR count correction changes labels, not totals/code/receipts; see count-correction.md. Twenty disposable freshness cases exercise both global source/formal and package flat helper/native evidence hashes without changing active inputs. Source member count208/4130 is a locator measure, direct-body0; 51 early live-edit vector input versions lack exact source bytes while final/frozen versions and raw diagnostics are retained.


Iteration11's per-member outcome ledger is [member-outcomes.json](../uplift/consolidated/iteration-11/member-outcomes.json) with a [TSV companion](../uplift/consolidated/iteration-11/member-outcomes.tsv), alongside the full before/after binding maps and unlinked complements. It separates newly bound members, new modeled behavior/domain on existing members and qualification-only context. Selected18 active members:12 finite native-correspondence roles,6 actual Python/unit roles,0 direct-body/inspection-only;190 other existing credited members are not recategorized. These are qualified workflow/source observations, not a project-wide semantic census or the evaluator's private sample. The updated scoring guidance is recorded by path/hash in scoring-guidance-update.json; no restart or prior reseal.

## Iteration12 replay and continuation

[Handoff](../uplift/consolidated/iteration-12/HANDOFF.md), [validation](../uplift/consolidated/iteration-12/validation.json), [member JSON/TSV](../uplift/consolidated/iteration-12/member-outcomes.json). Use pinned venv/export with PYTHONDONTWRITEBYTECODE=1 and VERUS_RUN_THREADS=4. Both families use shared run_verus.py prove/controls; source packages are models/communities and models/ledger_content. Native scripts are root-only guarded fixtures, never reviewer startup actions. Explicit non-login /bin/bash avoids the observed zsh startup delay; no shell config change is required. Ledger scratch identity may set IVG_LEDGER_IDENTITY_REPO solely for read-only pinned git-show lookup; current/export source bytes still hash equal.

Independent replay accepts73+108units (170new+11imports),33ordinary full/named controls,1255/4023main comparisons,174upstream. A checked decreases_by hint is part of its recursive termination query, not a separately counted proof. Source/domain/provider conditions are in frozen NOTES; Capture/Adopt are inspected typed ports, not executed native producers. Actual mainnative42 includes34ledger+8community; oldcommunity18reused and Cypher18nextprep separate. Legal ordinarymarker replay duplication strengthens existingF-C0351 without changing count/severity/policy. No source repair, raw memory/byte/body/native provider universality or private grade. Keep earlier seals and same census, create13before image before further models, then continue rawCypher MERGE and underserved workflow discovery.

## Iteration13 ordinary aggregates and reporting

[Handoff](../uplift/consolidated/iteration-13/HANDOFF.md), [validation](../uplift/consolidated/iteration-13/validation.json), [member outcomes](../uplift/consolidated/iteration-13/member-outcomes.json), [source/grade bridge](../uplift/consolidated/iteration-13/builder-scores.json). Same product3eaa79cf and completed12before image; the user redirected interrupted unsealed work to remain unpursued/unassessed. It is outside the active foundation and contributes no claims or grading. Completed seals are unchanged.

Use the pinned venv/export with PYTHONDONTWRITEBYTECODE=1, VERUS_RUN_THREADS=4 and the shared run_verus.py prove/controls commands for models/aggregate_results and models/routine_reporting. Their final standard binding receipts have flat source/helper/native-authority inputs; a global file/name correspondence stamp and23disposable freshness fixtures cover distinct source/formal and auxiliary evidence changes. Native scripts are root-only ordinary fresh-graph fixtures, not reviewer startup commands. Do not run namespace-wide Native reports over unassessed data or open the external interrupted-unassessed directory.

Independent replay accepts75aggregate units (62new+13unchanged node_read imports) and35new reporting units:97new=76ordinary proof queries+21recursive checks,0new hints/NLA.27model controls have full and named ordinary failures;23hash/name freshness fixtures are separate. Main binding checks11873, actual Python source sensitivities15 plus1SQL-provider and1actual-output corruption,220selected upstream tests. Aggregate V1's two specification controls and V2's literal observation check are withdrawn and preserved; final controls mutate actual producers and final observation sensitivity corrupts actual output against the same raw oracle. Reporting V1's missing standard binding receipt/flat provenance was corrected in V2 with exact original inputs retained.

The source map grows231→249/4130:18new members,3strengthened,0lost.21selected active roles comprise18actual-Python/local-SQL roles and3native inspected typed transcriptions; the latter are not exercised by the16SQL-native cases.14observation rows earn no new reach. The remaining228prior credited members retain their previous grades. No executable product body is proved. Stable registry view/refusal across kind scans, schema/ancillary provider truth, SQL equality/JSON/IEEE/collation and cross-read snapshot boundaries remain explicit.

Two source-grounded owners make405blocks, preserving all403prior bodies. New Low/Open bug-agg-001 records a leading grouped unmatched OPTIONAL returning NULL SUM versus newer R308's zero identity; ordinary/global/anchored passing neighbors are retained. All16fresh Native source forecasts agree;15ordinary/zero references agree and1differs, so this is not16intended conformance passes. Registers434bugs/55simplifications/146questions, no repair or owner decision. Sixty builder diagnostic rows retain49exact old after grades as both current before/after plus11overlapping ordinary extensions; no pooled private/population rate. RDF and full-record NDJSON producer/consumer boundaries remain material ordinary continuations; convergence is unsupported and no fixed round/time/percentage cap applies.

## Cloud continuation on Linux (2026-11-16): iteration 14 completion and later

[Iteration 14 handoff](../uplift/consolidated/iteration-14/HANDOFF.md); run identity, guidance hashes and fixture in
[cloud-run.json](../uplift/consolidated/iteration-14/cloud-run.json). From the repository root:

```sh
export RUN_DIR=$HOME/experiments/iris-ipm-continuous-20261116/runs/ivg-cloud-20261116
export VERUS_BIN=$HOME/.local/share/g5-verification/verus-0.2026.10.04.426d8b0/verus-x86-linux/verus
export IVG_PIN_DIR=$RUN_DIR/pin PYTHONDONTWRITEBYTECODE=1 G5_GUIDE=$G5_HARNESS/guidance
git archive 3eaa79cf | tar -x -C $IVG_PIN_DIR        # once; then, from $IVG_PIN_DIR:
UV_PROJECT_ENVIRONMENT=$RUN_DIR/venv uv sync --frozen --all-extras --python 3.11
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/rdf_reporting      # 50
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/ndjson_export    # 15 EXPECTED_FAIL
$RUN_DIR/venv/bin/python -B -I .g5/Verus_verification/models/rdf_reporting/binding.py              # AGREES 2229
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach                          # 254/4130
python3 .g5/Verus_verification/tools/check_consolidated.py                                        # PASS
```

Where to edit a link: `crosswalk/decision-links.tsv` (one row per member, formal item and role) and the family's row
in `families.tsv`; `member_reach.py` builds the map and the reverse lookup (`bindings.json`, keyed by `path::symbol`).
Worked lookup: `install.export.rdf.report` → `rdf_reporting.rs::theorem_raw_rows_to_final_report` → row for
`iris_vector_graph/_engine/rdf_export.py::RdfExportMixin.export_rdf` (line 96); in reverse, that key in
`bindings.json` lists the claim and its role. Native fixtures from iteration 15 on use only the run-isolated container
`ivg-cloud-20261116-iris` (127.0.0.1:36116), identity-checked by the iteration's `runtime.py`.

Iteration 15 ([handoff](../uplift/consolidated/iteration-15/HANDOFF.md)) adds `models/temporal_marker` (81 verified,
6 controls) and a native binding that needs the fixture running: start the container recorded in
`iteration-15/runtime.json`, then `$RUN_DIR/venv/bin/python -B .g5/Verus_verification/models/temporal_marker/binding.py`.

Iteration 16 ([handoff](../uplift/consolidated/iteration-16/HANDOFF.md)) adds `models/typed_equality` (37 verified,
5 controls) and a native binding (`models/typed_equality/binding.py`, fixture required) plus a translation-only route
trace (`iteration-16/route_trace.py`, no database).

Iteration 17 ([handoff](../uplift/consolidated/iteration-17/HANDOFF.md)) extends `models/typed_equality` to 41 verified and 7
controls; its binding now covers ordering. Native-path routing evidence: `iteration-17/native_equality_probe.py`.

Iteration 18 ([handoff](../uplift/consolidated/iteration-18/HANDOFF.md)) adds `models/sort_key` (50 verified, 5 controls); its
binding calls `Graph_KG.CY_SORT_KEY` and `Graph.KG.Cypher.SortKey.Key` on the fixture.

Iteration 19 ([handoff](../uplift/consolidated/iteration-19/HANDOFF.md)) adds `models/setup_record` (7 verified, 4 controls); its native
observations need a fresh namespace (`W21`) created in the fixture from `%SYS` as recorded in `iteration-19/inputs.json`.

Iteration 20 ([handoff](../uplift/consolidated/iteration-20/HANDOFF.md)) extends `typed_equality` to 42 verified and 8 controls;
`sort_key` re-verified at 51 after the import grew.

Iteration 22 ([handoff](../uplift/consolidated/iteration-22/HANDOFF.md)) adds `models/bm25_counts` (7 verified, 4 controls);
its binding needs the fixture and reads `^BM25Idx` over the Native API.

The cloud continuation converged after iteration 24 ([basis](../uplift/consolidated/HANDOFF.md#convergence-cloud-continuation-2026-11-16)).
Native replays need `docker start ivg-cloud-20261116-iris` first; the container was stopped, not removed.

## Retest on Linux (2026-11-16): iteration 25 and later

[Iteration 25 handoff](../uplift/consolidated/iteration-25/HANDOFF.md); run identity, guidance hashes and the dedicated
fixture in [retest-run.json](../uplift/consolidated/iteration-25/retest-run.json). From the repository root:

```sh
export RUN_DIR=$HOME/experiments/iris-uplift-retest-20261116/runs/ivg-retest-20261116
export VERUS_BIN=$HOME/.local/share/g5-verification/verus-0.2026.10.04.426d8b0/verus-x86-linux/verus
export PATH=$HOME/.cargo/bin:$PATH IVG_PIN_DIR=$RUN_DIR/pin PYTHONDONTWRITEBYTECODE=1 G5_GUIDE=$G5_HARNESS/guidance
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/bulk_load       # PASS 8
CONTROL=rerun-completes-stranded python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/bulk_load
docker start ivg-retest-20261116-iris                                                          # 127.0.0.1:36216
(cd $IVG_PIN_DIR && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/bulk_load/binding.py)  # AGREES 360
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach                       # 287/4130
python3 .g5/Verus_verification/tools/check_consolidated.py                                    # PASS
```

Worked lookup: `install.bulk_load.loader` → `bulk_load.rs::theorem_interrupted_load_is_never_completed` → rows for
`iris_vector_graph/bulk_loader.py::BulkLoader.load_nodes` (line 252, decision) and `::_executemany_batched` (line 83,
effect) in `crosswalk/decision-links.tsv`; in reverse, `bindings.json` under that key lists the claim and its role.

Iteration 26 ([handoff](../uplift/consolidated/iteration-26/HANDOFF.md)) adds `models/write_routing` (8 verified, 8
controls) and its binding (`models/write_routing/binding.py`, fixture required, about 1 s); the targeted split-state
probe is `iteration-26/autocommit_probe.py`. Worked lookup: `structure.write` →
`write_routing.rs::theorem_autocommit_off_temporal_edge_splits` → `iris_src/src/Graph/KG/TemporalIndex.cls::WriteStores`
(line 80, step order) and `iris_vector_graph/stores/iris_sql_store.py::IRISGraphStore.write_temporal_edge` (line 2655,
direct call) in `crosswalk/decision-links.tsv`.

Iteration 27 ([handoff](../uplift/consolidated/iteration-27/HANDOFF.md)) adds `models/vec_index` (8 verified, 6 controls)
and its binding (`models/vec_index/binding.py`, fixture required, about 2 s; seed 20261116).

Iteration 28 ([handoff](../uplift/consolidated/iteration-28/HANDOFF.md)) adds `models/algo_options` (5 verified, 6 controls) and its
binding (`models/algo_options/binding.py`, fixture required, about 2 s), which reuses the frozen matrix in
`iteration-28/algo_options_probe.py`.

Iteration 29 ([handoff](../uplift/consolidated/iteration-29/HANDOFF.md)) adds `models/embedding_inventory` (3 verified, 3
controls) and its binding (fixture required; it runs the CLI as a subprocess with `IRIS_*` set to the fixture).

Iteration 30 ([handoff](../uplift/consolidated/iteration-30/HANDOFF.md)) adds `models/plaid_index` (5 verified, 4 controls) and its
binding (fixture required; needs numpy and scikit-learn from the pinned venv).

Iteration 31 ([handoff](../uplift/consolidated/iteration-31/HANDOFF.md)) extends `bulk_load` (10 verified, 8 controls; the binding
needs namespace `W37`, IVG Schema `Kg2`, created as recorded there) and `write_routing` (9 controls; batch and delete).

Iteration 32 ([handoff](../uplift/consolidated/iteration-32/HANDOFF.md)) adds `models/http_rows` (3 verified, 3 controls) and an
in-process binding (FastAPI `TestClient` with `IRIS_*` set to the fixture; no port is opened).

Iteration 33 ([handoff](../uplift/consolidated/iteration-33/HANDOFF.md)) adds `models/node_edge_update` (5 verified, 6 controls) and its binding.

Iteration 35 ([handoff](../uplift/consolidated/iteration-35/HANDOFF.md)): W41 is probe-only. The retest converged after iteration 35
([basis](../uplift/consolidated/HANDOFF.md#retest-convergence-2026-11-16)). Native replays need `docker start ivg-retest-20261116-iris` first.

## Continuation on Linux (2026-11-17): iteration 36 and later

Run identity and the dedicated fixture `ivg-cont-20261117-iris` (127.0.0.1:36317): [continuation-run.json](../uplift/consolidated/iteration-36/continuation-run.json);
the fixture runtime is `iteration-36/runtime.py`. Per-iteration handoffs are linked from the
[continuation table](../uplift/consolidated/HANDOFF.md#continuation-2026-11-17). Iteration 47 from the repository root:

```sh
export RUN_DIR=$HOME/experiments/iris-uplift-continuation-20261117/runs/ivg-cont-20261117
export VERUS_BIN=$HOME/.local/share/g5-verification/verus-0.2026.10.04.426d8b0/verus-x86-linux/verus
export PATH=$HOME/.cargo/bin:$PATH PYTHONDONTWRITEBYTECODE=1 G5_GUIDE=$G5_HARNESS/guidance
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/cypher_fns        # PASS 11
CONTROL=row-index-through-ivglistget python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/cypher_fns
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/ivf_entries       # PASS 9
CONTROL=cosine-normalized python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/ivf_entries
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/cypher_fns/binding.py)   # AGREES 43
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/ivf_entries/binding.py)  # AGREES 6
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD IVG_RUNTIME_DIR=$OLDPWD/.g5/uplift/consolidated/iteration-36 \
  $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/write_routing/binding.py)                                    # AGREES 52
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after47                 # 463/4130
python3 .g5/Verus_verification/tools/check_consolidated.py                                      # PASS
```

Iteration 48 (W55, Cypher expressions over run-time values), same environment:

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/cypher_exprs      # PASS 17
CONTROL=row-slice-wrapped python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/cypher_exprs
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/cypher_exprs/binding.py) # AGREES 209
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after48                 # 480/4130
```

Iteration 49 (W56, composed retrieval), same environment:

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/retrieval_compose     # PASS 28
CONTROL=guided-cap-max-nodes python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/retrieval_compose
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/retrieval_compose/binding.py) # AGREES 41
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after49                 # 503/4130
```

Worked lookup (iteration 49): `algorithms.op.subgraph.guided` → `retrieval_compose.rs::theorem_guided_subgraph_drops_edges_among_top_nodes`
→ the rows for `iris_vector_graph/_engine/algorithms.py::AlgorithmsMixin.kg_PPR_GUIDED_SUBGRAPH` (line 971, decision: the cap
`min(max_nodes, ppr_top_k)`) and `iris_src/src/Graph/KG/Subgraph.cls::SubgraphJson` (lines 6 and 51, decision) in
`crosswalk/decision-links.tsv`; in reverse, those keys in `bindings.json` list the claims and roles. The distinguishing
control is `guided-cap-max-nodes`; the product observation is the binding's `guided[7]` (seven nodes, one edge) beside
`guided[50]` (all seven edges).

Worked lookup (iteration 48): `query.writes.computed_values` → `cypher_exprs.rs::theorem_inline_rel_expression_dropped`
→ the row for `iris_vector_graph/cypher/translator.py::_create_clause_relationship_entry` (line 10212, decision) in
`crosswalk/decision-links.tsv`; in reverse, that member's key in `bindings.json` lists this claim. The distinguishing
control is `rel-value-kept`; the product observation is the binding's `create_rel_Call_Arith` (`written_without_property`)
beside `create_rel_Lit` (`written`).

Worked lookup: `query.functions.list_index` → `cypher_fns.rs::theorem_row_negative_index_fails` → the row for
`iris_vector_graph/cypher/translator.py::_expr_subscript` (line 23509, decision) and
`iris_vector_graph/schema.py::GraphSchema.get_procedures_sql_list` (the `JSON_ARRAYGET` body, line 2179) in
`crosswalk/decision-links.tsv`; in reverse, that key in `bindings.json` lists the claims and roles. The distinguishing
control is `row-index-through-ivglistget`; the product observation is the binding's `row_index_-1` (`fails`).

Iteration 50 (repairs from independent review 47-49; [handoff](../uplift/consolidated/iteration-50/HANDOFF.md),
[dispositions](../uplift/consolidated/iteration-50/DISPOSITIONS.md)), same environment:

```sh
for m in cypher_fns cypher_exprs retrieval_compose ivf_entries; do
  python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/$m      # PASS 16 / 22 / 35 / 19
  python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/$m   # 13 / 22 / 15 / 7 EXPECTED_FAIL
  (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/$m/binding.py)  # AGREES 103 / 233 / 45 / 9
done
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-50/review_repro.py)   # the review's cases, fresh prefix
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after50                 # 505/4130
```

Worked lookup (iteration 50): `query.functions.list_index` → `cypher_fns.rs::theorem_null_index_reads_first_element` →
the rows for `iris_vector_graph/cypher/translator.py::_expr_subscript` (line 23620, decision) and `::_is_row_list_elem`
(line 7681, the WITH-literal path) in `crosswalk/decision-links.tsv`; in reverse, those keys in `bindings.json` list the
claims. The distinguishing control is `null-index-is-null`; the product observation is the binding's
`index_property_row_null` (`["at", 0]`) beside `index_with_literal_row_-1` (`["at", 2, "typed"]`).
Iteration 50 withdrew the control `guided-cap-max-nodes` (it encoded a repair that contradicts the documented cap); the
bug-plt-113 lookup now ends at `edges-among-answered` and `seeds-capped`.

Iteration 51 (W57, temporal statistics readers; [handoff](../uplift/consolidated/iteration-51/HANDOFF.md)), same environment:

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/temporal_stats       # PASS 51
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/temporal_stats    # 16 EXPECTED_FAIL
CONTROL=small-range-correction python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/temporal_stats
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/temporal_stats/binding.py)  # AGREES 139
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-51/stats_probe.py)       # raw probe, fresh prefix
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after51                 # 537/4130
```

Worked lookup (iteration 51): `temporal.stats.distinct` → `temporal_stats.rs::theorem_distinct_one_target_is_eleven`
→ the rows for `iris_src/src/Graph/KG/TemporalIndex.cls::GetDistinctCount` (lines 671-681, decision: the raw estimator,
0 only for an all-zero sketch) and `::HLLAdd` (210-224, the provider's register choice) in
`crosswalk/decision-links.tsv`; in reverse, those keys in the recount's `bindings.json` list the claims. The
distinguishing control is `small-range-correction`; the product observation is the binding's `distinct_d_d1_0_299`
(11 for three edges to one target) beside `distinct_d_nobody_0_299` (0).

Iteration 52 (W58, operator reports; [handoff](../uplift/consolidated/iteration-52/HANDOFF.md)), same environment. Status
counts every graph of a namespace, so the probe uses the fresh namespace `I52`. The binding drops and re-creates `I52B`
from `%SYS` in `ivg-cont-20261117-iris` only; it needs `docker exec` on that container.

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/operator_reports       # PASS 34
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/operator_reports    # 17 EXPECTED_FAIL
CONTROL=registry-keeps-case python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/operator_reports
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/operator_reports/binding.py)  # AGREES 414
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-52/reports_probe.py)      # raw probe in I52
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after52                 # 563/4130
```

Worked lookup (iteration 52): `install.status.readiness` → `operator_reports.rs::theorem_routed_never_counted` and
`lemma_upper_never_route` → the rows for `iris_vector_graph/_engine/admin.py::AdminMixin._embedding_tables` (line 305,
decision: the case-sensitive route test over `SELECT DISTINCT`'s collated text) and
`iris_vector_graph/security.py::is_routed_embedding_table` (line 58) in `crosswalk/decision-links.tsv`. In reverse,
those keys in the recount's `bindings.json` list the claims, beside the iteration-13 `routine_reporting` rows, whose
routed-table correspondence is withdrawn at the IRIS reader. The distinguishing control is `registry-keeps-case`. The
product observation is the binding's `provider:distinct_text` (`KG_EMB_…` for `kg_emb_…`) beside `s9_routed_vectors`
(`node_vecs` 0, `absent`) and `s9:search_g` (True).

Iteration 53 (repairs from independent review round 2, review-50-52, then the remaining SQL procedure surface;
[handoff](../uplift/consolidated/iteration-53/HANDOFF.md), [dispositions](../uplift/consolidated/iteration-53/DISPOSITIONS.md)),
same environment. The `operator_reports` binding now drops and re-creates its own namespace `I53B` (no longer `I52B`);
the `sql_procs` binding re-creates `I53Q`. Both run from `%SYS` in `ivg-cont-20261117-iris` only and need `docker exec`
on that container.

```sh
for m in temporal_stats operator_reports cypher_exprs sql_procs bm25_scoring percentile; do
  python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/$m      # PASS 58 / 48 / 22 / 16 / 32 / 26
  python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/$m   # 18 / 24 / 22 / 12 / 9 / 4 EXPECTED_FAIL
  (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/$m/binding.py)  # AGREES 148 / 535 / 236 / 224 / 46 / 156
done
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-53/temporal/labelset_probe.py)   # M1, m1, m2, m9 raw probe
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-53/reports/failed_probe.py)     # M2, M3, m7, m8 raw probe in I53
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after53                 # 603/4130
```

Worked lookup (iteration 53): `query.functions.percentile` → `percentile.rs` (see its NOTES for the floor-index claim of
bug-cyp-134) → the rows for `iris_src/src/IVG/Percentile.cls::PDISC` (line 13, decision: index floor((n−1)·p)) and
`iris_src/src/Graph/KG/SqlProcs.cls::PercentilePDISC` (the SQL entry the translator's `_scalar_statistical` emits) in
`crosswalk/decision-links.tsv`; in reverse, those keys in the recount's `bindings.json` list the claims. The product
observation is the binding's p 0.6 and 0.9 cases over 10, 20, 30, 40 (20 and 30, where the nearest rank gives 30 and 40).
Second lookup: `install.status.readers` → `operator_reports.rs::theorem_failed_census_unknown_only_in_report` → the rows
for `iris_vector_graph/cypher_api.py::get_metrics` and `::get_server_info` and `_engine/admin.py::AdminMixin._status_probes`;
control `metrics-marks-unknown`; product observation: binding step s19 (`ivg_nodes_total 0` for a user without SELECT
while `status().unknown` names `graph`).

Iteration 54 (W59, Cypher clauses over API-written data, default mode and parameters;
[handoff](../uplift/consolidated/iteration-54/HANDOFF.md)), same environment. The binding writes fresh nodes and edges
in USER (prefix `i54k_<tag>_`) and one named graph `i54kg<tag>` in `ivg-cont-20261117-iris` only.

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/cypher_clauses       # PASS 26
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/cypher_clauses    # 25 EXPECTED_FAIL
CONTROL=group-by-typed python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/cypher_clauses
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/cypher_clauses/binding.py)  # AGREES 112
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-54/clauses_probe.py)     # raw probe, fresh tag
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after54                 # 619/4130
```

Worked lookup (iteration 54): `query.aggregation.keys` → `cypher_clauses.rs::theorem_sql_group_merges_number_and_its_text`
→ the rows for `iris_vector_graph/cypher/translator.py::translate_return_clause` (30676: the item selected through
`CY_TYPED`; 30777: the plain `sql` added to `GROUP BY`) and `::_expr_aggregation` (24431, `COUNT(DISTINCT arg)`) in
`crosswalk/decision-links.tsv`; the native side is `iris_src/src/Graph/KG/Cypher/Exec.cls::GroupOf` (1349-1380) under
`theorem_paths_disagree_exactly_on_marked_text`. In reverse, those keys in the recount's `bindings.json` list the claims,
beside the inherited `aggregate_results` rows on `_expr_aggregation` and `GroupOf`. The distinguishing control is
`group-by-typed`; the product observation is the binding's `A_Int1_Str1_sql_group` (true: one group) beside
`A_Int1_Str1_sql_distinct` (false) and `A_Int1_Str1_native_group` (false).

Iteration 55 (W60, one answer through the pipeline to the Neo4j driver;
[handoff](../uplift/consolidated/iteration-55/HANDOFF.md)), same environment. The probes and the binding start the
product's own TCP Bolt listener (`start_tcp_bolt_server`, a real engine on its own connection) on a free `127.0.0.1`
port inside the probe process and read it with the neo4j Python driver 6.4.1 and a raw socket client; they write fresh
nodes in USER (prefixes `i55_`, `i55b_`, `i55k_`) in `ivg-cont-20261117-iris` only. The IRIS driver contrast needs an
isolated venv outside the repository with intersystems-irispython 5.4.1 in front of the fixture venv:

```sh
mkdir -p /tmp/i55dl && python3 -m pip download --no-deps -d /tmp/i55dl "intersystems-irispython==5.4.1"
PY=$(readlink -f $RUN_DIR/venv/bin/python); $PY -m venv --without-pip $RUN_DIR/i55/venv541
python3 -m pip install --no-deps --target $RUN_DIR/i55/venv541/lib/python3.11/site-packages /tmp/i55dl/intersystems_irispython-5.4.1-*.whl
echo "$RUN_DIR/venv/lib/python3.11/site-packages" > $RUN_DIR/i55/venv541/lib/python3.11/site-packages/zz_base.pth
cp $RUN_DIR/venv/lib/python3.11/site-packages/_editable_impl_iris_vector_graph.pth $RUN_DIR/i55/venv541/lib/python3.11/site-packages/
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/bolt_answers          # PASS 27
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/bolt_answers       # 19 EXPECTED_FAIL
CONTROL=swap-columns python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/bolt_answers
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD I55_VENV541=$RUN_DIR/i55/venv541/bin/python \
  $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/bolt_answers/binding.py)          # AGREES 400
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-55/pipeline_probe.py)    # four readers, fresh tag
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD I55_MODE=params $RUN_DIR/i55/venv541/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-55/pipeline_probe.py)  # parameters on 5.4.1
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after55                 # 640/4130
```

Worked lookup (iteration 55): `access.bolt.graph_values` → `bolt_answers.rs::theorem_endpoints_follow_columns` and the
general `theorem_one_hop_right_iff_source_first` → the rows for `iris_vector_graph/bolt_server.py::BoltSession._recompose_graph_row`
(787-799, decision: start = the node triplet before the relationship column, end = the one after) and
`::_detect_graph_columns` (669-689) in `crosswalk/decision-links.tsv`; in reverse, those keys in the recount's
`bindings.json` list the claims. The distinguishing control is `swap-columns` (and `no-prev-node`); the product
observation is the binding's `D2_wire_bra` and `D2_wire_rev` (start = b's id for a stored `a→b`) beside `D2_wire_abr`
(start = a's id). Second lookup: `query.parameters` → `theorem_param_slice_answers_empty` → `cypher/translator.py::_expr_slice`
(23778-23789); control `slice-markers-in-order`; observation `F_slice_5.4.1` (`[]`) beside `F_slice_5.3.2` (`Fail`).

Iteration 56 (repairs from independent review round 3, review-53-55, then the install lifecycle;
[handoff](../uplift/consolidated/iteration-56/HANDOFF.md), [dispositions](../uplift/consolidated/iteration-56/DISPOSITIONS.md)),
same environment. `bolt_tx` starts the product's TCP Bolt listener in-process (as `bolt_answers`) and writes nodes in USER;
`sql_procs` now drops and re-creates its own namespace `I56Q` with eight users (`i56q_*`, dropped after the run);
`install_lifecycle` drops and re-creates `I56SA`-`I56SD`. All three run from `%SYS` in `ivg-cont-20261117-iris` only and
need `docker exec` on that container.

```sh
for m in bolt_tx install_lifecycle cypher_clauses percentile aggregate_results sql_procs temporal_stats bm25_scoring; do
  python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/$m      # PASS 20 / 32 / 29 / 30 / 75 / 27 / 64 / 35
  python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/$m   # 7 / 20 / 28 / 7 / 12 / 21 / 20 / 13 EXPECTED_FAIL
  (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/$m/binding.py)  # AGREES 17 / 138 / 124 / 168 / 669 / 273 / 159 / 59
done
CONTROL=begin-refused python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/bolt_tx
CONTROL=column-grant-counts python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/sql_procs
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-56/cypher/cypher_probe.py)  # F2 raw probe, fresh prefix
python3 .g5/Verus_verification/tools/member_reach.py --out $RUN_DIR/reach-after56                 # 662/4130
python3 .g5/uplift/consolidated/iteration-56/member_delta.py $RUN_DIR/reach-before56 $RUN_DIR/reach-after56 /tmp/member-delta.json
```

Worked lookup (iteration 56): `access.bolt.transactions` → `bolt_tx.rs::theorem_rollback_keeps_writes` (general:
`theorem_rollback_departs_iff_writes`) → the rows for `iris_vector_graph/bolt_server.py::BoltSession._dispatch` (500-510,
decision: BEGIN, COMMIT and ROLLBACK answer SUCCESS and open or close nothing) and `::BoltSession._handle_run` (the
statement runs with no session transaction, so it commits at once) in `crosswalk/decision-links.tsv`; in reverse, those
keys in the recount's `bindings.json` list the claims beside the inherited `bolt_stream` and `bolt_answers` rows. The
distinguishing controls are `atomic-tx` and `begin-refused` (the two repairs); the product observation is the binding's
`R_rollback` (count 1 after BEGIN, CREATE, ROLLBACK, every answer SUCCESS) beside the commit and auto-commit neighbors.
Second lookup: `access.iris_boundary` → `sql_procs.rs::theorem_column_only_select_refused` → `iris_src/src/Graph/KG/SqlPrivilege.cls::RequireSelect`
and `::Holds`; control `column-grant-counts`; observation: user `i56q_column` refused naming `Graph_KG.rdf_edges` while
`i56q_table` and `i56q_role` pass.
