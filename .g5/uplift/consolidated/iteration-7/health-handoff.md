# Service-health builder handoff — iteration7

Bounded package: `models/service_health/`, its `results/service_health/` receipts and `health-*` evidence. Product3eaa79cf and foundation-before709a497f stay pinned. No Git/index/shared tool/ontology/native runtime was changed by this builder.

Final result: **18 proofs,13 decisive controls,84 actual-Python/in-process ASGI comparisons,0 mismatches,6 sensitivity checks true,0 network attempts;11 original unit tests pass.** Model inputs are raw constructor/query/record outcomes rather than a supplied readiness flag. Main app capture, lazy cache retry, retained failed cache, recovery/reset and the actual `_run_cypher` competing cache writer reach the next health reader. All provider and deployment limits are in model NOTES. api.main and its nested health closure remain outside the historical member denominator.

Source discovery H6 is necessary for fidelity: `_run_cypher` is the sole production reset caller. A raised query exception resets/retries once and changes the next health result; a folded result.error is raised outside its loop, does not reset, and leaves that old engine cached. It is now modeled and exercised through real `/api/cypher` followed by `/health`; no arbitrary Cypher semantics or authentication claim follows. Original H1-H5 predictions and baseline ontology/model judgments remain in `health-PAIRS.md`.

## Canonical integration recommendations

Keep `access.health`'s basic requirement and existing sample/API distinction. Add a child `access.health.lifecycle` with this suggested as-built body:

> The sample API keeps the engine captured when its app is created. If automatic construction or its first connection access fails, the app still starts, but health remains unavailable until the app is recreated; the health request does not retry construction. An already-bound engine can recover when its own probe succeeds again. If the caller injects an engine whose first connection access fails, app creation raises.
>
> The Cypher HTTP server constructs an engine when its cache is empty. Failed construction leaves it empty for the next request to retry; a later query failure keeps a successfully constructed engine cached. A later successful query on that engine can recover health. Reset tries to close the engine and clears the cache even if close raises, so the next request can construct a replacement.
>
> A normal query request is another cache writer: its first raised exception resets and retries once, while a folded result error does not reset. A second raised exception stops and leaves the replacement cached. These are observed recovery rules, not a guarantee that an external database or connection will recover.

In the owning metadata use stable `[service health contract](../../Verus_verification/models/service_health/service_health.rs)`, plus the model NOTES for role evidence. Keep implementation locators/receipts with the formal family. Model declarations include `problem`, `main_boot`, `main_request`, `cache_request`, `reset`, `run_query` and named theorems. The role table in NOTES enumerates the actual producers/writers/readers, including the out-of-census API roles.

Refine the existing status statement if useful: the sample API requires SELECT1=1 plus a matching namespace record for an IRIS connection; the Cypher server uses success/absence of a nonempty probe-result error. Neither promises that every database feature works. Preserve their actual different response bodies and raw provider/detail logging boundary.

Potential child policy Q under access.health, **not opened or answered by this builder**: Should the sample API retry construction after a startup outage, or must an operator restart/recreate it? Current as-built assumption: recreate it. A changed policy would require modeling startup replacement and the actual GraphQL/query consumers that also capture engine ownership; no owner approval is inferred from source or the formal model. This is not currently a proved requirement violation or a newly counted bug.

## Evidence, changes and misses

`health-validation.json` records final measured commands, exact receipts/input hashes and available costs. Model/manifest/harness and deciding product sources are stamped; `api/main.py` is an explicit correspondence input. Failed/earlier attempts remain under `health-attempts/`. First model15 and binding80 passed before the necessary competing-writer extension. The first reset instrument checked copy state only; that credit was withdrawn and replaced by a mutation of the real module cache followed by an actual health request. No product bug or extra gain is counted for correcting the instrument.

`health-freshness.json` exercises root's actual correspondence gate on a disposable copy. The unchanged copy reuses both inputs; changing only api/main.py's health branch or adding a potential cache-writer module preserves proof reuse but returns correspondence STALE_ALL. Changing the formal folded-error rule returns STALE_ALL for both. The new source writer was never run or added to the product. Final measured costs: proof0.718s, all13 controls14.396s, binding2.332s; original unit reported0.40s. Native/network/provider deployment was not measured.

No owner decision, new product defect or simplification is made here. H1/H2 already had supported ontology predictions; H3/H4/H6 gain a concrete lifecycle and actual binding. This is builder-visible/self-evaluated evidence, not an unseen holdout or a prevalence estimate. General Unicode casing/custom driver objects, network/deployment, real database/permission failures, native first-access rules, concurrent schedules and physical close effects remain unassessed or conditional. The selected original11 unit tests and84 binding assertions are separate measures, not added into one score. Tokens/cache/currency and solver-only cost are unavailable.

Root can now integrate canonical/crosswalk/register/metrics and independently review. No additional health model scope is proposed for this iteration. The package supplies no convergence claim; the concurrent procedure-result work addresses a different underserved caller boundary.
