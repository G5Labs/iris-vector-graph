# Service health: app capture, lazy cache and actual request results

Product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; iteration7 starts after `709a497f`. As-built transcription with the existing pinned Verus/vstd, no assume/admit/external_body and no executable product-body proof. **18 named proofs pass; all13 decisive controls fail their named proofs.**

## Frozen questions and actual decisions

`health-PAIRS.md` freezes H1/H2 from product docs/tests and the iteration6 independent breadth observations before the new model. Existing `access.health` already represented those basic status neighbors. H3/H4 cover the different startup/cache histories missing from that prose and existing formal admission models. The later actual-writer census found `_run_cypher` as the only production caller of `_reset_engine`; H6 records that consequential producer before the model was extended. No private evaluator draw was used.

`api.main.create_app` tries automatic construction and first connection access once. Failure still creates an app whose health closure captures no engine. Every later health request remains unavailable, even if construction would now succeed. An already-bound engine can recover when its own query/record provider recovers. An injected engine's first connection access is outside the catch: that app construction raises instead of returning the engine-absent app.

`problem` derives the sample API's status from raw SELECT1 rows/exceptions, actual connection classification, and raw namespace-record read outcomes. It checks the namespace only after SELECT1 succeeds and only for an IRIS connection. Missing, mismatching and unreadable records have distinct fixed reasons. `selected_one` includes ordinary Python numeric equality (including True and rational1); text"1", null, missing/wrong rows and nonfinite values fail. `same_schema` derives equality from ASCII uppercase characters, matching normal validated schema names. Arbitrary Unicode upper()/custom scalar protocols and malformed driver objects are not proved; the binding exercises actual Python equality and `schema_name.read_record/same_schema` over the stated ordinary scalar/ASCII domain.

`cypher_api._get_engine` caches a successfully returned engine and leaves construction failure uncached. `cache_request` therefore retries failed construction but retains an engine on a later query exception or folded nonempty result.error. A later successful query on that same engine can recover without constructing another one. Empty error text is falsey and remains healthy as built, even though IVGResult's separate object truthiness treats non-None error differently; the endpoint reads the error field itself. Success says only that this probe answered, not that arbitrary graph queries, tables or schema identity are available.

`reset` attempts to close a present engine, then clears the cache even when close raises. Its `closed` field denotes a successfully reported close, **not** a claim that a failed close had no resource effect. The next request can construct a replacement. The actual competing writer `_run_cypher` resets/retries once on a raised construction/query exception. It examines a folded result.error after that loop, so that case does not reset. A second exception stops with the replacement still cached. `run_query` represents that writer and the next health-observable state; it is not a model of arbitrary Cypher evaluation.

All cache operations are modeled sequentially under the existing lock discipline. The binding observes lock ownership during factory/query calls, and direct reset calls hold the real lock; this is not a proof of concurrent schedules or fairness. `_engine_cache` assignments were enumerated: construction in `_get_engine` and clearing in `_reset_engine`, whose current caller is `_run_cypher`. The sample app writes app.state.engine once, but its health handler uses the captured local engine, not a fresh state lookup.

## Formal and implementation roles

| Role | Production member | Contract | Evidence / boundary |
| --- | --- | --- | --- |
| app construction/capture | `api/main.py::create_app` | `main_boot`, `main_injected`, `main_request` | actual app construction and ASGI route closure; connection/constructor provider substituted |
| final sample health reader | `api/main.py::create_app.health` | `main_request` | actual HTTPstatus/body from captured engine; nested/API member outside historical census |
| sample connection producer | `api/main.py::get_engine` | `main_boot` | actual factory body over named connector and engine-constructor ports; no connection proof |
| probe/schema decision | `api/main.py::database_problem` | `selected_one`, `problem` | actual SELECT1 scalar/error and NativeAPI record-read path |
| record adapter | `iris_vector_graph/schema_name.py::read_record` | `Record` / `problem` | actual get/None/empty/str conversion over named native-get provider; no native call |
| schema comparison | same file `same_schema` | `same_schema` | actual ASCII case and mismatch fixtures; general Unicode casing open |
| lazy factory producer | `iris_vector_graph/cypher_api.py::_make_engine` | `Factory` / `cache_request` | actual explicit-host branch over connector/constructor ports; embedded/environment branches open |
| cache writer/reader | same file `_get_engine` | `cache_request` | actual no-cache construction and reuse/failure behavior |
| request/lock boundary | same file `_engine` | `cache_request` | real lock-held factory/query calls; shared role under sequential protocol |
| final HTTP reader | same file `health` | `query_ok`, `cache_request` | actual result.error/exception to ASGIstatus/body |
| cache reset writer | same file `_reset_engine` | `reset` | actual close success/failure and cache clearing |
| competing writer/caller | same file `_run_cypher` | `attempt_raised`, `run_query` | actual other-query exception versus folded error, followed by next health request |

`api/` and nested closure members are outside the historical scoped production-member census. Their behavioral evidence does not silently expand that denominator. A resolved declaration does not verify its whole method; connector/engine construction, SQL, native schema storage, actual `execute_cypher` semantics and close effects remain named provider boundaries. Existing authorization/public-route and result-admission models remain separate; no authentication/permission escalation experiment was performed. PermissionError here is a named substituted provider exception, handled as an ordinary readiness failure.

## Replay and observations

```sh
export RUN_DIR=/Users/ziniuw/runs/ivg-iteration7-health-20261115
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export VERUS_RUN_THREADS=4 PYTHONDONTWRITEBYTECODE=1
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/service_health
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/service_health
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/service_health/binding.py
```

Expected: **18 verified /0 errors;13 controls EXPECTED_FAIL; binding AGREES,84 comparisons,0 mismatches,6 detections true,0 socket-connect attempts.** These checks are a purposive builder panel, not independent grading, live/native fixtures or deployment evidence. Every request uses real in-process ASGI routing. Named providers vary constructor/first-access, returned scalar/error, record get, query error/count and close; actual implementation owns retry/cache/status decisions. Wrong SELECT1, missing/mismatching/unreadable record, folded versus raised query failure, empty error, sticky/recovering histories, reset failure and the actual other-query writer are all observed through their final request readers.

The six actual Python sensitivity checks alter schema casing, record mismatch, folded-error handling, reset cache clearing, actual other-query retry and the final HTTPstatus. The reset mutant operates on the real module cache and is followed by an actual health request, rather than merely inspecting an edited/copy's state. Initial state-only reset-control credit is withdrawn; the earlier receipt remains historical. Formal controls independently change these deciding branches and constructor/refusal states. No syntax or unrelated proof failure counts as a control success.

Original health unit suites run via the guarded `health-upstream.py`: **11 passed in0.40s**,0 socket calls, with import-time connection construction blocked before api.main loads. Their two warnings concern pytest import rewriting and the installed Starlette/httpx client. Final commands, costs and receipts: [health-validation.json](../../../uplift/consolidated/iteration-7/health-validation.json). Earlier15-proof and80-comparison runs and initial control limitations are retained in `health-attempts/`; they are not extra coverage or new product defects.

## Limits and disposition

No new product bug, simplification or owner-policy answer is claimed. Automatic recovery of the sample API is unconfirmed policy: the model records its sticky startup failure, not approval of that behavior. Do not infer readiness of all graph features from either probe. Network routing, actual database/service recovery, middleware interactions beyond the ordinary request path, embedded startup, schema deploy concurrency, arbitrary record writers/Unicode data and external close effects are unestablished. The actual source-only correspondence gate was exercised on a disposable snapshot: a changed api/main.py health branch and a newly added potential cache-writer file reopen correspondence while unchanged proof inputs remain reusable; a changed formal error decision reopens both. [health-freshness.json](../../../uplift/consolidated/iteration-7/health-freshness.json) retains exact verdicts. No added writer was executed or registered in the product.

The package improves a missing lifecycle/provider-to-status prediction and its binding. It establishes no repository-wide percentage or convergence claim. Native/runtime checks remain root-owned; this builder neither connects to nor mutates that runtime.
