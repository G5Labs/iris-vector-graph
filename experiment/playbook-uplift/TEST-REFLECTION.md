# Test reflection (playbook §3.8)

What the tests behind the worked example (erasure → redaction → replay) observe, what this uplift ran, what failed and why,
and which premises still have no test. Product pin `3eaa79cf`; IRIS Community 2026.1 in `$IVG_TEST_CONTAINER`.

## A. Runs executed in this uplift

| Run | Where | Result | Log (under `$RUN_DIR`) |
|---|---|---|---|
| Upstream spec 256 e2e file, Community deploy (`run-community-redaction.py`) | live IRIS | 25 passed (62.7 s, then again 52.2 s in the final rerun) | `logs/upstream-community-redaction-1.log`, `final/upstream-community-redaction.log` |
| Upstream `tests/unit`, whole set, `SKIP_IRIS_TESTS=true` | Python, some IRIS | 24,579 passed, 264 skipped, 1 failed, 86 errors (404 s) | `unit/unit-full.log`, `unit/junit.xml` |
| Uplift live scenarios (`native/scenarios.py`, 14 scenarios) | live IRIS | 14 of 14 passed (225 checks), final rerun | `final/native.log`, `final/native/traces/*.json` |
| Model checks (`model/`, 11 checks) | Rust explorer | see `MODELS.md` | `final/mc.log`, `final/mc-summary.json` |
| Verus proof gate (`proofs/`, baseline + 6 controls) | Verus | see `STATUS.md` | `final/verus.log`, `verus/proofs-*.log` |

`evidence/test-results.json` records the status of every upstream test function in the two upstream runs; the ontology index
marks a `tested:` citation **ran** when its test passed here, and lists every cited test that did not.

## B. Triage of the failing upstream tests (from the saved logs)

| Tests | Count | Cause | Class |
|---|---|---|---|
| `tests/unit/test_203_tck_regressions.py` (several classes) | 86 errors | Setup: the upstream fixture compiles every class; `Graph.KG.MCPService`, `MCPToolSet` and `MCPTools` need `%AI`, which IRIS Community does not have (`ERROR #5373: Class '%AI.MCP.Service' ... does not exist`). Same cause as the preflight's stock run of the e2e file. | Environment (P-0101, P-0106) |
| `tests/unit/test_setup_logging.py::test_no_warning` | 1 failure | The client package logs `Class or module 'gref' not found in iris_embedded_python` (no embedded Python in this venv); the test requires no warnings. | Environment |

No failure was attributed to the product. Note for the harness: `SKIP_IRIS_TESTS=true` does not stop `test_203_tck_regressions`
from reaching IRIS; its fixture compiled classes into the dedicated container during the run.

## C. What the upstream redaction tests observe, and what they leave out

The upstream e2e file (25 tests) builds the two-tenant world with one spanning revision, scans every `^IVG.Ledger` node and
ledger row before and after, checks byte identity of tenant B's records, digests, refusals with whole-store snapshots, a
paused run and its resumption, and `verify()` before and after redaction. The unit file (36 tests) checks decoding, replay
skipping, error mapping, the readers' marker check, and (by source scan) the trigger exemption.

Left out, and covered here instead:

| Gap in the upstream tests | Covered here by | Result |
|---|---|---|
| Interruption is only cooperative (`max_batches`) | `killed_mid_batch` (process stopped while blocked inside a batch), `killed_at_random` (5 stops at spread times) | Every stop rolled back to a batch boundary; the run resumed and verify was equal |
| Concurrency: no second process during a run | `commit_in_unmarked_window`, `two_targets_at_once`; model `redaction-as-built-*` | F-1302, F-1303 reproduced |
| Retry only with tenant A's own key | `retries` (shared key, B's own key, conflict), `retry_between_erase_and_redact`; model `retry-*` | Shared key refused (Decision 2 consequence); F-1306 reproduced |
| `verify()` is never checked before the erasure | `mixed_tenant_flow` | F-1401: the fixture world already diverges on `tenantA|n3` |
| Default-graph target without prefix; graph-per-tenant without prefixes | `default_graph_without_prefix`, `graph_per_tenant_unprefixed` | F-1304, F-1305 reproduced |
| Ledger disabled between batches | `disabled_mid_run` | Refused, marker kept, resumed after enable |
| A reader racing a redaction | `reader_races_redaction` (interleaving forced in the test process); model `readers-*` | F-1402 reproduced |
| Erasure racing a commit | model `erasure-*` | F-1201 (model only) |

## D. Premises and their tests

| Premise | Test |
|---|---|
| P-0001..P-0004 (rollback on stop, dirty reads, deferred unlock, locks freed) | Live `premises` (ObjectScript probe class `native/cls/IVGUplift.Probe.cls`) and `nested_commit_holds_head` |
| P-1201 (a delete waits for a held row) | None (documentation) |
| P-1301 (separability) | Live: an independent oracle of the target rule agreed with the code's tombstones in every scenario |
| P-1302 (digest identifies the record) | Live: every tombstone digest recomputed from the record read before redaction |
| P-1306, P-1307 (progress, operator resumes) | None; progress proved only for an uninterrupted run |
| P-1308 (exemption variable) | Upstream unit source scan (ran here) |
| P-1309 (journals, backups, exports out of reach) | None |
| P-1401 (verify on a quiet ledger) | None |

## E. Not tested in this uplift

- The spec 256 performance tests (`-m perf`: SC-002, SC-003) and IRIS Enterprise.
- The statement and tuple maps are checked live after every step but are not in the Verus model.
- Mutation testing of the ObjectScript covers three guards (`native/mutants.py`, mirroring proof controls
  `control_no_commit_block`, `control_no_final_check`, `control_keep_retry_key`): each mutant was loaded into the container,
  killed by the live scenarios, and the pin's classes restored; the full scenario set then passed. The other proof controls
  (unmarked start, other target, FR-004 wording) describe the pin itself or a doc variant, so they have no mutant.
- Breadth modules (01–11, 15–18): their evidence is reading and upstream tests; only the unit run and the spec 256 e2e file
  were executed here.
