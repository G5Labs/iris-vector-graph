# IVG verification-playbook uplift: handoff

The original verification playbook (`verification-playbook.txt`) applied to iris-vector-graph at product pin `3eaa79cf`,
starting from `index.md`'s seed intents, on branch `experiment/iris-vector-graph-playbook-uplift-20261113`. Nothing outside
`experiment/playbook-uplift/` was changed. Start with `STATUS.md`.

## What is here

| Path | What |
|---|---|
| `REVIEW.md` | The independent review: findings and how each was resolved |
| `STATUS.md` | Phase gates, every guarantee of the worked example with its evidence level and status at the pin, breadth summary, gaps |
| `MODELS.md` | The state machines, bounds, properties and results; the proofs and their controls |
| `TEST-REFLECTION.md` | Runs executed, triage of failing upstream tests, what the upstream redaction tests observe and leave out, premises and their tests |
| `FINDINGS.md`, `findings/NN.md` | 197 findings (code, test or doc disagrees with a requirement), each with evidence and what would close it |
| `DECISIONS.md`, `decisions/NN.md` | 61 decisions for the human (`Owner: human`); 29 ontology cells wait on them |
| `TRUST.md`, `trust/NN.md` | 138 named premises; the proof trust inventory is empty (no assume/admit/external_body/uninterpreted functions) |
| `ontology/` | §3.1 ontology: `00-system.md` and 18 modules, `INDEX.md` (generated), `README.md` (format), `BUILDER-BRIEF.md` |
| `semantics/` | §3.3a: `SEMANTICS.md` (axioms, mechanisms, lifecycles, domain contract), `writesets.json` and generated `WRITESETS.md` |
| `proofs/` | Verus crate: L1 (`l1.rs`), L2 (`l2.rs`), replay model (`model.rs`), progress (`progress.rs`); 6 control features |
| `model/` | Explorer crate: 5 machines × 2 designs (`redaction.rs`, `refine.rs`, `erasure.rs`, `readers.rs`, `retry.rs`) |
| `native/` | Live harness on IRIS: `ivg_native.py`, `scenarios.py` (14 scenarios), `mutants.py` (3 ObjectScript mutants), `cls/IVGUplift.Probe.cls` (test-only probe class) |
| `evidence/` | `runs.json` (registry of every run: kind, result, log path under `$RUN_DIR`, log SHA-256), `test-results.json` (upstream test outcomes) |
| `tools/` | `ontology_index.py` (gate and index), `writesets.py`, `run_verus.py` (proof gate), `register_all.py`, `test_results.py`, `register_run.py`, `check_all.sh` |

## Reproduce

```bash
source "$HOME/runs/iris-vector-graph-playbook-uplift-20261113/playbook/environment.sh"   # sets RUN_DIR, IVG_*, PATH, Verus
cd "$WORK_DIR"
bash experiment/playbook-uplift/tools/check_all.sh          # offline: model checks, proof gate, index, write sets
bash experiment/playbook-uplift/tools/check_all.sh --live   # also the 14 live scenarios and the upstream Community suite
```

Offline needs Rust 1.98.1, Verus `0.2026.10.04` (`$VERUS_BIN`), the local `G5Labs/actors` checkout at `c03f9fa` (a git
dependency of both crates; edit the `file://` URL in `proofs/Cargo.toml` and `model/Cargo.toml` if it moved), about 10 GB of
memory and 6 minutes. `--live` needs the dedicated container (`$IVG_TEST_CONTAINER`, port `$IVG_PORT`); the scenarios reset the
namespace (`Graph.KG.Eraser.EraseAll`, `Graph.KG.Ledger.PurgeAll`) and refuse any database whose identity is not that container.
Individual pieces: `python experiment/playbook-uplift/tools/ontology_index.py --check`; `cargo run --release -- --only <id>`
in `model/`; `python experiment/playbook-uplift/native/scenarios.py --only <name>`.

## Results at handoff (final reruns, 2026-11-13)

- Ontology gate: pass; 3,015 statements, 19 modules, 904 cells (29 open, assigned), checker self-test 11/11.
- Model checks: 11/11 met their expectation; the reviewed redaction core and its refinement audit exhaustive within bounds
  (11,351,753 states each).
- Proofs: 53 verified, 0 errors under `--no-cheating`; 6/6 controls rejected in `l2.rs`.
- Live: 14/14 scenarios (225 checks); 3/3 ObjectScript mutants killed live; upstream spec 256 e2e on Community 25/25.
- Unit set: 24,579 passed; 86 errors and 1 failure, all environmental (triaged in `TEST-REFLECTION.md`).
- Write-set obligations: 83, all covered, 17 open (finding only).

## What is not in the repository

Raw logs, traces and build outputs are under `$RUN_DIR` (`final/`, `native/`, `mc/`, `verus/`, `unit/`, `logs/`), referenced
from `evidence/runs.json` with their SHA-256. Cargo targets are in `$RUN_DIR/mc/target` and `$RUN_DIR/verus/target-proofs`.

## State left in the dedicated container

The scenarios left the USER namespace with the last scenario's data (they reset at start, not at end). The test-only class
`IVGUplift.Probe` and the global `^IVGUplift` exist in that namespace. The upstream unit run's `test_203` fixture also compiled
the product classes there (same source as the pin). Nothing else was installed. Remove them with
`do $System.OBJ.Delete("IVGUplift.Probe")` and `kill ^IVGUplift` if the container is reused.

## Decisions for the human (most consequential first)

1. HD-1301: make the redaction's opening check and its marker one locked step (closes F-1302, F-1303; the design is proved).
2. HD-1201: should graph erasure take the ledger head lock (F-1201)?
3. HD-1305: should a replayed commit apply post-commit properties (F-1306)?
4. HD-1303 / HD-1304: default-graph targets without a prefix, and tenants whose nodes live in their own graph (F-1304, F-1305).
5. HD-1401: verification's node identity and the readers' redaction check (F-1401, F-1402).
6. HD-0001: the reading of the playbook's definitions-first rule as lexical scope.

## Next steps

- Reproduce F-1201 live (it is a model result only).
- Extend `native/mutants.py` beyond its three guards (for example the separator rule and the digest).
- Model the IRIS behaviours the slice uses as a reusable environment contract (§3.2) and split erasure, ledger and readers into
  `actors::protocol::Protocol2` modules.
- Run `-m perf` (SC-002, SC-003) and an Enterprise build.
- Take the breadth modules' highest-impact inspection findings (for example F-0815, F-0901, F-1001, F-1801) to live checks.
