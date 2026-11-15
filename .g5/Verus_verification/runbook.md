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

Every probe under `native/probes/` drives only public product entry points on this arm's instance, through the identity-checked [harness](native/harness.py), resets the namespace's graph and ledger content first, derives its expectation independently of the implementation and prints `OBSERVED_AS_EXPECTED`, `OBSERVED_DEFECT` or `INCONCLUSIVE`. Observations land in `$RUN_DIR/native/<probe>-<stamp>.json` with the SHA-256 of the probe, its helper and the harness (`_probe_inputs`); copies of the final-candidate observations are in [`receipts/native/`](receipts/native/). Run probes one at a time: they share one IRIS namespace, and Community Edition allows only a handful of connections (concurrent probes and scratch-namespace suites hit "Unable to allocate a license").

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
