# Validation lane: upstream suites and performance baselines at the pin

This file covers the pin `3eaa79cf` (tree `b098a6f4`), which was not changed. Status: **final** (2026-11-14 ~05:15 UTC).
Every suite, rerun and performance run below has finished.

Other records:
- `results.json` is the machine-readable twin. It holds counts, the SHA-256 of each chunk's log, every triaged node
  id, the skip reasons and the perf JSON.
- `triage.py` holds every rule with its reason and citations.
- Evidence ids are `evidence/runs/val-<run id>.json`. Chunked runs have one id per chunk (`val-<run>-cNN`) or per
  file (`-fNN`).
- Raw logs are in `$RUN_DIR/validation/<run id>/run.log`.

## How the runs were made

- **Clean build.** Every suite ran from a clean clone of the pin, `$RUN_DIR/validation/checkout`.
  - It was made with `git clone --shared --no-checkout` of the local repository, then `checkout --detach 3eaa79cf`.
  - The submodule `vendor/opencypher` at 677cbafa came from the local module store, so no network was used.
  - `run.sh` refuses a clone that is not at the pin or has tracked changes.
  - A clone was needed because the audit worktree is read-only for this lane, and upstream tests write into the
    checkout (FastHTML's `.sesskey`, which broke `unit-1`).
  - At 01:31 UTC the clone was made go+rX, with no change to content or git status. A 0600 fixture copied into the
    container with `docker cp` had been unreadable by irisowner (rule `clone-perms`).
- **Harness (`run_suite.py`): exactly what it replaces.**
  1. **Session deploy.** It replaces only the session fixture's `tests.conftest._deploy_objectscript(<container>)`
     call.
     - The database identity is checked first.
     - The call then goes to the pin's own `IRISGraphEngine.initialize_schema()` at width 768.
     - That skips Graph.KG.MCPService, MCPToolSet and MCPTools, because the `%AI` classes are absent.
     - In scratch mode the same applies to a namespace created during the run.
     - Every other call goes to the pin's original function (recorded as `deploy_delegated`).
  2. **Namespace guard.** `scripts/dev/tcp_setup.make_namespace`/`drop_namespace` and `tcp_setup.run` lines that
     create a namespace or database raise `AuditNamespacePolicy` when they target the real server.
     - In scratch mode (`VALIDATION_SCRATCH_NS=1`, operator rulings of 2026-11-14) they are allowed only for
       namespaces absent at run start.
     - Pre-existing namespaces such as IVG460SNAP are still refused.
  3. **Driver override.** `VALIDATION_DRIVER_SITE` (driver comparison only) puts intersystems-irispython 5.4.0 first
     on `sys.path` and `PYTHONPATH`.
  4. **Gate switch.** The e2e gate's own switch `IVG_GATE_NAMESPACES=0` is used everywhere except `run_gated.sh`.
  5. **Per-run records.** Each run gets the `iris.cpf` [Namespaces] list before and after, the driver version,
     JUnit XML and an exit code.
- **Locking.** Every run holds `tools/locks.sh iris` for its whole duration. Long sets were chunked by sorted file
  list, one hold per chunk. Most holds were under 15 min. The longest functional holds were integration-1-c05
  (1,374 s) and integration-1-c02 (910 s). The announced perf hold perf-algos-1 took 2,198 s.
- **Selection.** The default pyproject addopts apply (`-m "not perf"`, `--strict-markers`).
  - Added deselections: only the 8-writer ledger cases (`test_ledger_us03 ... eight_writers`, `TestSoak`,
    `test_concurrent_query_throughput`). They need more than 6 connections, beyond the coordinator's cap and the
    8-unit licence.
- **Environment.**
  - Machine: GCP VM, Xeon Platinum 8481C, 22 vCPU (10 visible), 86 GB RAM, shared with the other lanes (load 5-8).
  - IRIS: Community 2026.1 (Build 234U) in `ivg-playbook-20261113-audit-iris`, cpuset 5,6 (2 CPUs), 8 licence units,
    USER journalled.
  - Client: Python 3.11.18 with intersystems-irispython **5.3.2**. That is the version the pin's `uv.lock` resolves
    (`pyproject.toml:42` only asks `intersystems-iris>=1.0.0`).
  - Driver 5.4.0 for the A/B runs: `$RUN_DIR/availability/driver-5.4.0-venv`.

## Functional suites

P/F/E/S/D = passed, failed, errors, skipped, deselected, summed over chunks. Categories:
- **product-defect**: behaviour that violates a contract.
- **product-defect (driver 5.3.2)**: fails on the driver the pin's `uv.lock` installs and passes on 5.4.0 in an
  alternating A/B.
- **test-stale**: the pin's own test contradicts its documented behaviour, so the suite is red at the pin.
- **environment**, **harness**, **intermittent**.

| Suite (how it is meant to run) | Run (chunks) | P | F | E | S | D | pytest s | Triage of every failure/error (rule: count) | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| tests/unit (CI: SKIP_IRIS_TESTS=true; here live) | unit-3 (8) | 24,794 | 10 | 69 | 57 | 13 | 835 | test-stale: width-refusal 68, path-as-dict 3, mock-signature 1 (red in CI too); environment: audit-ns-guard 6 (then passed in scratch-1), gref-logging 1 | val-unit-3-c00..c07; attempts val-unit-1 (harness), val-unit-2 (stopped) |
| tests/integration | integration-1 (6) | 2,651 | 31 | 100 | 437 | 9 | 4,187 | test-stale: sqluser-views 23, gql-sqluser-setup 9, var-length-raises 1; test-isolation: nodepk-leftover 2; driver 5.3.2: duplicate-listerror 3, decimal-score 2; intermittent: kgtxt-prefix 1 (passed in rerun-1); environment: audit-ns-guard 81 (then passed in scratch-1), mcp-ai-classes 5, alt-namespace(-grant) 4 (then passed in alt-1) | val-integration-1-c00..c05, val-integration-1-c00-rerun, val-rerun-1 |
| tests/e2e, gate off | e2e-1 (22) | 3,348 | 16 | 16 | 12,557 | 4 | 4,093 | driver 5.3.2: decimal-score 2, temporal-structural-cursor 2, duplicate-listerror 2; **product-defect: leiden-karate-ari 1**; intermittent: duplicate-edge-timing 2 (passed in rerun-2); environment: audit-ns-guard 13, embedded-python-deps 3, gref-logging 2, bulk-ingest-timing 1, arno-absent 1; harness: clone-perms 3 (passed in perm-rerun-1) | val-e2e-1-c00..c21, val-rerun-2, val-rerun-3, val-perm-rerun-1 |
| e2e gated subset, gate on (ruling) | gated-1..4, gated-rag-1/2 | 10,122 | 310 | 0 | 102 | 0 | 801 | driver 5.3.2: decimal-score 289, list-param-count 14, rrf-score-string 2; environment: embedded-callin-denied 4, mcp-ai-classes 1. No licence errors. One gate namespace was made and dropped per run: 6 here, and 10 counting the gated driver A/B runs. | val-gated-1..4, val-gated-rag-1/2 |
| r306 algorithm oracle in USER (`IVG_ORACLE_USER=1`; how tests/oracle runs) | oracle-1 (8) | 7,406 | 252 | 0 | 0 | 0 | 229 | driver 5.3.2: decimal-score 252 (values within tolerance; the type alone fails) | val-oracle-1-c00..c07, val-driver540-oracle-1 |
| tests/tck (scripts/tck/run_all.sh + summarize.py) | tck-1 (8 holds) | 3,895 / 3,896 eligible | 1 | - | 0 | 1 ignored upstream | 1,886 wall | driver 5.3.2: Unwind1 [3] "Unwinding a concatenation of lists", `<ARGUMENT ERROR> Incorrect number of parameters` (13/14 again in tck-unwind-rerun-1; **14/14 under 5.4.0** in driver540-tck-unwind-1) | val-tck-1, val-tck-unwind-rerun-1, val-driver540-tck-unwind-1 |
| tests/docs (static layer) | docs-2 | 196 | 16 | 0 | 0 | 0 | 3 | the 16 are test_docs_run before IVG460DOC existed (doc460, environment), superseded by docs-run-1/2 | val-docs-2 (val-docs-1 pre-lock) |
| tests/docs/test_docs_run.py in IVG460DOC (ruling) | docs-run-1, docs-run-2 | 15 / 16 docs each | 1 | 0 | 0 | 0 | 75-80 | driver 5.3.2 (by class; see note): USER_GUIDE.md block 40 expects `[['alice', 0.6, 3], ...]` and gets `Decimal('0.6')` | val-docs-run-1, val-docs-run-2 (val-docs-run-540-1 non-decisive) |
| IVG262ALT files (ruling) | alt-1 | 39 | 0 | 0 | 0 | 0 | 34 | none (test_262_alt_schema_paths, test_grant_copy, test_cypher_advanced[IVGALT]) | val-alt-1 |
| Scratch-namespace fixtures (ruling) | scratch-1 | 90 | 0 | 0 | 7 | 0 | 86 | none (skips: "not one of this project's containers") | val-scratch-1 |
| Spec 236 scratch suites (IVG_NS_IVG236=IVG236VAL) | scratch-236-1, -2a/-2b (22 per-file) | - | - | - | - | - | - | **infrastructure, not counted**: licence exhaustion (Incidents) | val-scratch-236-1, val-scratch-236-1-rerun-a-f00..b-f10 |
| tests/contract, default | contract-1 | 0 | 0 | 0 | 53 | 0 | 1 | all skipped by its conftest (TDD stubs unless IVG_RUN_CONTRACT=1) | val-contract-1 |
| tests/contract, IVG_RUN_CONTRACT=1 | contract-optin-1 | 45 | 1 | 7 | 0 | 0 | 25 | test-stale: sqluser-views 8 | val-contract-optin-1 |
| tests/regression | regression-2 | 3 | 5 | 0 | 0 | 0 | 3 | test-stale: regression-budgets 5 (not in CI) | val-regression-2 (val-regression-1) |
| tests/python | python-1 | 71 | 0 | 0 | 33 | 0 | 50 | none (skips: REST :52773 absent; iris-devtester perf env) | val-python-1 |
| tests/test_schema_contract.py | schema-contract-1 | 11 | 5 | 0 | 0 | 0 | 11 | test-stale: schema-contract-stale 5 | val-schema-contract-1 |
| tests/perf default selection (spec 227 SC-010) | perf-default-1..4 (5.3.2), -540-1/2 (5.4.0) | 1 each | 1 each | 0 | 1 each | 7 each | 10-17 | **product-defect (perf): sc010-latency**, on both drivers (table below) | val-perf-default-1..4, val-perf-default-540-1/2 |

`tests/oracle`, `tests/fixtures`, `tests/helpers` and `tests/support` are libraries with no tests; the oracle is
exercised by oracle-1 and the gated r306/r307 files. `tests/benchmarks` is scripts: see Performance.

Non-decisive runs:
- docs-run-540-1 is not a 5.4.0 measurement: `tests/docs/harness.py:553-554` resets the document worker's
  `PYTHONPATH`, so that worker used 5.3.2.
- The scratch-236 runs hit licence exhaustion.
- unit-1, unit-2, docs-1 and regression-1 are attempts, and harness-check-1 and perf-smoke-1 are harness checks.
  All are registered with the reason.

### Driver A/B (5.3.2 = the pin's `uv.lock`; 5.4.0 = the version the repo's docs name)

The runs alternate in time.

| Run | Driver | Files | Result |
|---|---|---|---|
| integration-1, e2e-1, rerun-1..3 | 5.3.2 | (whole suites, then the failing files) | decimal-score, duplicate-listerror, temporal-structural-cursor fail (above) |
| driver540-1 | 5.4.0 | 8 files holding those cases (test_algorithms_new_paths, test_store_write_paths, test_sql_store_paths, proc_yield_alias, r270_ppr_networkx, create_edge_atomic, temporal_structural_row_live, communities) | 237 passed, **1 failed (leiden-karate-ari only)** |
| driver532-1 | 5.3.2 | same 8 | 224 passed, 14 failed: decimal-score 4, duplicate-listerror 7, temporal-structural-cursor 2, leiden 1 |
| driver540-2 | 5.4.0 | same 8 | 237 passed, 1 failed (leiden) |
| driver540-oracle-1 vs oracle-1-c00 | 5.4.0 / 5.3.2 | oracle chunk 00 (960 cases) | 960/960 vs 926/960 |
| gated-540-1 / gated-532-1 | 5.4.0 / 5.3.2 | 7 gated files (list parameters, Decimal) | 138/138 vs 119/138 (list-param-count 10, decimal-score 9) |
| gated-rag-540-1 / gated-rag-532-1 | 5.4.0 / 5.3.2 | test_460_r284_retrieve_rrf_score | 2/2 vs 0/2 |
| driver540-tck-unwind-1 / tck-unwind-rerun-1 | 5.4.0 / 5.3.2 | TCK unwind area | 14/14 vs 13/14 |

## Product-defect findings

1. **The pin's lockfile installs a driver on which IVG misbehaves** (S2, high).
   - `uv.lock` resolves intersystems-irispython 5.3.2, and `pyproject.toml` sets no floor. CI tests a fresh
     resolution instead.
   - With 5.3.2, all of the following fail, and they pass with 5.4.0 (A/B above):
     - (a) Cypher `CALL ivg.*` YIELD scores and retrieve() `rrf_score` come back as `Decimal` or `str`, not float.
       Failures on the type alone, by decisive run: oracle-1 252; gated subset 289 (252 of them are the r306 oracle
       again, in a gate namespace); integration-1 2; e2e-1 2; docs-run 1; rrf_score 2.
     - (b) The duplicate-row skip in `write_nodes`/`write_edges`/`create_edge`. The driver's `<LIST ERROR>` replaces
       SQLCODE -119, so `GraphWriteError` is raised and nothing is written, against the documented "a duplicate row
       is skipped". This is intermittent per case but reproduced in every 5.3.2 run.
     - (c) `create_edge_temporal` with `temporal_structural_rows=True` raises "Cursor closed; DataRow is
       inaccessible" (`_engine/temporal.py:189`).
     - (d) Cypher with list parameters or list concatenation gets a parameter-count error. This covers TCK Unwind1 [3]
       and 14 gated e2e cases.
2. **Leiden on Zachary's karate club gives ARI 0.072** (S3, medium).
   - The test (spec 163 FR-007) requires > 0.75.
   - It fails on both drivers and in every run (e2e-1, rerun-2, driver540-1/2, driver532-1).
   - Community has no Arno, so the fallback path ran. `tests/perf/test_leiden_four_way.py` states that both paths
     agree.
3. **Spec 227 SC-010 latency budget exceeded on both drivers** (S4, medium).
   - The scoped `kg_KNN_VEC` versus the 3.2.0 scan on 300 rows, by run:
     - 5.3.2: 1.169x, 1.145x, 1.205x, 1.124x.
     - 5.4.0: 1.149x, 1.147x.
   - The budget is 1.1x, so 6 of 6 runs fail, on the test's own interleaved-median A/B.
   - The overhead is about 0.25-0.3 ms per call on this 2-CPU Community container.
4. **Test-side defects red at the pin** (S4; listed so they are not mistaken for passes).
   - width-refusal (68 unit cases, plus 13 in the cypher benchmark).
   - SQLUser-era tests and scripts: integration, contract stubs, gql, nodepk perf (`scripts/migrations/migrate_to_nodepk.py`),
     and `tests/benchmarks/bench_utils.py:11`, so the spec 093 benchmark cannot run at the pin.
   - Stale regression budgets, schema contract and mock signature (the mock is red in CI's unit job too).
   - Stale var-length and path tests.
   - nodepk-leftover isolation, and kgtxt-prefix (about 4% flaky, from its random prefix).
5. **Inspected, not run.** `api/gql/resolvers/query.py:79-92` (GraphQL `node(id)`) queries the removed SQLUser
   tables.
6. **Lead, not decidable here.** test_025 varlen lookup "DID NOT RAISE", seen only in licence-degraded scratch-236
   runs.

## Multi-process

| Run | What | Result | Evidence |
|---|---|---|---|
| mp-existing-1/-2/-3 | test_ledger_us03 (2-process same-head race; 3 writers + 1 without expected_head; unknown head), us04 (2 processes, same idempotency key), us09 (verify vs a concurrent committer process); the 8-writer case deselected (cap) | 15 passed in each of 3 runs | val-mp-existing-1..3 |
| perf-committer-n3-1 | **3 committer processes** (own connections) committing to other tenants during 2 redactions of 100,000 records | 20,415 / 21,483 commits, 0 errors, every committed node live, history contiguous and single-parent (head 20,428 / 21,496), verify equal; longest commit during redaction 36.4 / 30.6 ms | val-perf-committer-n3-1 |
| perf-committer-n1-1/-2 | 1 committer process, 3 cycles each | 0 errors, history contiguous, verify equal (below) | val-perf-committer-n1-1/-2 |

**Multi-node: blocked-access, distinct from multi-process.**
- There is one container. It has no second IRIS instance, no ECP data server and no mirror member
  (`%SYSTEM.Mirror.IsMember()` = 0).
- A multi-node run needs two or more IRIS instances, a licence that enables ECP or mirroring, and permission to
  configure them.

## Performance

All runs held `locks.sh iris`. The environment is the Community 2-CPU container on a shared VM, **not** the spec's
laptop Enterprise container. All perf runs used driver 5.3.2.

| Measurement | Run | Result | Evidence |
|---|---|---|---|
| **SC-002** (10,000 revisions over 10 tenants, 5% spanning two; upstream `-m perf`) | perf-sc256-upstream-1 / -2 | **verify() equal** both; built in 21.0 / 19.7 s; redacted 4,181 records in 1,045 revisions in 1.20 / 0.99 s (max batch 717 / 557 ms); verify 2.1 / 1.9 s; other tenants' records and revision rows byte-identical (SC-004 asserts) | val-perf-sc256-upstream-1/-2 |
| **SC-003** (100,000 records; upstream) | same | redacted in **1.42 / 1.41 s** (< 60 s), 52 batches, longest batch **39 / 31 ms** (< 1 s, product-reported) | same |
| **SC-003 committer-side** (validation/perf; a separate committer process measures its own commit wall times; A before / B during / A after on the same state) | perf-committer-n1-1, -n1-2 (3 cycles each, alternating windows) | redact 1.82 / 2.25 / 2.35 s and 1.61 / 1.51 / 1.48 s; **longest commit overlapping the redaction 311 / 55 / 57 ms and 253 / 39 / 28 ms** (receipt max_batch_ms 310 / 54 / 47 and 251 / 38 / 28: the first batch of a run is the slow one); commit p50 before 0.92-1.40 ms, during 0.99-25.8 ms (p95 26-48 ms), after 0.91-1.48 ms; 0 errors; verify equal | val-perf-committer-n1-1/-2 |
| SC-003, 3 committer processes | perf-committer-n3-1 (2 cycles) | redact 1.62 / 1.58 s; longest commit during 36.4 / 30.6 ms; p50 before 2.3 ms, during 3.6 ms | val-perf-committer-n3-1 |
| Spec 213 ledger (`-m perf`, soak deselected) | perf-ledger-1 | 4 passed: 100-op commit median 63.4 ms (p95 97.3); ledger overhead ratio 1.036; 5,000-op p95 4.61 s; head read p95 0.14 ms; verify 5.76 s; reconstruct head 2.91 s; genesis over 120,000 ops 1.41 s | val-perf-ledger-1 |
| Algorithms (communities 10K, cypher benchmark, tests/perf `-m perf`) | perf-algos-1 | 10 passed: IVG BetweennessGlobal karate 8-12 ms, ER(500) 0.69-0.73 s, ER(2000) 3.14 s; Leiden four-way IVG leg. 1 failed: Leiden ER(10,000) **62.04 s vs the 60 s NFR-004 gate** (non-Arno path; environment-timing, unconfirmed). 13 errors: test-stale width-refusal (cypher benchmark seed) | val-perf-algos-1 |
| nodepk perf/performance | perf-nodepk-1 | 1 F + 10 E: test-stale `nodepk-sqluser-bulk`; 6 skipped by their own reasons ("not achievable over Docker network", production scale opt-in) | val-perf-nodepk-1 |
| tests/performance (`-m performance`) | perf-performance-1 | 2 xfailed (both marked xfail upstream: "license exhaustion under concurrent container load") | val-perf-performance-1 |
| Spec 093 traversal benchmark (tests/benchmarks/bench.py `--datasets S M`) | bench-1, bench-2 | **no measurement**: `bench_utils.py:11` `DELETE FROM SQLUser.<table>` fails (-30); test-stale | val-bench-1/-2 |
| SC-010 single-graph latency | perf-default-1..4, -540-1/2 | scoped/legacy median 1.169, 1.145, 1.205, 1.124 (5.3.2); 1.149, 1.147 (5.4.0) vs the 1.1x budget | val-perf-default-* |

Caveats:
- SC-002 holds here.
- SC-003's 60 s and 1 s targets hold here with wide margin. That is on 2 CPUs and Community, and the spec's target is
  an Enterprise laptop container. The upstream "longest batch" is the product's own receipt. The committer-side
  numbers are an independent measurement and agree with it.
- Absolute timings depend on a shared, loaded VM.
- Not run (blocked):
  - Neo4j/GDS/Memgraph legs and LDBC SNB.
  - The `benchmarks/` scripts that need Enterprise or Arno.

## Blocked lanes (exact missing dependency)

- **Enterprise or IRIS for Health.** No image (the product's reference is `irishealth:2026.3.0AI`) and no iris.key.
  Only `iris-community:2026.1` is local, plus another project's image that is also 2026.1 Community. Nothing was
  pulled: that needs InterSystems Container Registry credentials and the network.
- **Other IRIS versions.** None is local.
- **More than 8 licence units.** This blocks:
  - the spec 236 scratch suites (22 integration files);
  - the 8-writer soaks.
- **The rest of the gated e2e files.**
  - Count: 88 of 234. The others ran in the gated subset: 102 primary-only and 44 rag-only files.
  - Why: they need several scratch namespaces per session (53 more gate groups, 28 of them name-only groups whose
    files make their own, some building releases from git tags), or many concurrent connections (16 files with
    threads, worker processes or extra users).
  - Not run, so as not to repeat the 01:31 licence alerts.
- **FHIR.** The IVGFHIR namespace with an HS_FHIRServer endpoint (IRIS for Health).
- **`%AI.Tool` / `%AI.ToolSet` / `%AI.MCP.Service` / `%AI.Policy.ConsoleAudit`.** This blocks the MCP classes and
  tests.
- **libarno_callout.so.** No Arno paths can run.
- **Embedded Python in the container.** Callin is denied (IRIS_ACCESSDENIED) and pydantic is missing. Granting
  %Service_CallIn would reconfigure the shared container.
- **Neo4j 5 + GDS / Memgraph, and LDBC datagen data.**
- **REST on :52773.** The audit container publishes only the superserver.
- **Quickstart CI.** It would start another container from docker-compose and do network installs.
- **Multi-node.** See Multi-process above.

## Incidents and side effects

- **23:01:45-23:03:40 UTC: two uncoordinated fixtures of other lanes in the shared container.**
  - A module-08 unit test reloaded about 45 pin classes into USER at 23:01:48-50 (incidents/USER-REDEPLOY-08.md).
  - Breadth lane C's tests/unit/test_snapshot.py created IVG460SNAP at 23:02:53. This lane's before/after namespace
    record caught it.
  - Only integration-1-c00 (22:57:56-23:04:23) overlapped.
  - Its rerun, integration-1-c00-rerun, has identical per-test outcomes for all 342 cases (191 P / 10 F / 141 S).
  - Both records are kept.
- **01:31:40-01:46:40 UTC, and the per-file reruns to about 01:58: licence exhaustion by this lane's spec 236 run.**
  - Cause: the pinned `ivg_236_scratch` fixture keeps every connection it opens until session end.
  - Effect: 316 "License limit exceeded" alerts, and Docker health failed.
  - Rerun: one file per process (scratch-236-2a/2b), which still exceeded the cap. A probe under the lock showed no
    other client (env-probe/licprobe-1.log), so no further rerun was made.
  - Disposition: infrastructure, not counted.
- **01:19:03 UTC: orchestrator container restart.** No validation run overlapped it.
- **Namespaces made by this lane.** All are in incidents/NAMESPACES.md and left intact.
  - IVG460SNAPVAL, IVG262REC, IVG262FPG, IVG262FPA and IVG236VAL (fixtures in scratch mode).
  - IVG460DOC (`make_scratch_namespace.py`).
  - IVG262ALT (fixture recreate).
  - Made and dropped by their own fixture or gate: IVG470NSE84FE5 and 10 IVG460FXG*P/R gate namespaces.
- **Upstream side effects.**
  - IVGDev.Setup/Run (the pin's dev helper) were compiled into %SYS by `tcp_setup.ensure_helper`.
  - test_nodepk_migration.py leaves legacy SQLUser.nodes in USER.
  - The e2e security tests create and delete their own users, roles and web applications.
