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
