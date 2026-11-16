# The HTTP Cypher readers' row cap

Product `3eaa79cf`, unchanged. Iteration 32 (retest). Predictions frozen before observation in
[http-PAIRS.md](../../../uplift/consolidated/iteration-32/http-PAIRS.md). Owner:
[access.surfaces](../../../ontology/concepts/access.g5.md#access.surfaces). Finding: bug-plt-108.

## What the model decides

`kept(rows, limit)` transcribes `_run_cypher`'s cut: the whole answer when it fits, else its first `limit` rows.
`/api/cypher` applies its `limitRows` and reports `rowCount` = rows kept; `/db/neo4j/tx/commit` and `/db/{db}/query/v2`
apply the default 1,000 and report no count. `execute_cypher`'s rows are the input (bound by other models); the JSON
encoding of ordinary values is a premise, observed unchanged for int, float, string, boolean, list, null and an
aggregate in W38.

## Theorems (3, all new; no imports)

`theorem_answer_is_prefix`, `theorem_neo4j_answer_cannot_tell_truncation` (two different engine answers — 1,000 rows and
more with the same first 1,000 — give the same Neo4j-route answer), `theorem_api_row_count_is_kept`. No `assume`,
`admit` or `external_body`.

## Controls

Three, all EXPECTED_FAIL full and isolated: `no-limit` (the Neo4j contract), `api-counts-total`, `cut-one-short`. The
first run of `cut-one-short` was ERROR (its patch anchor matched nothing); the anchor was corrected and the control
rerun; that receipt is kept.

## Binding

[binding.py](binding.py) drives the actual routes in-process (FastAPI `TestClient`, no listener) for 999, 1,000, 1,001
and 1,200 rows and `/api/cypher` with `limitRows` 5 and 2,000: **AGREES, 36 comparisons**, all mutations detected.

## Limits

Bolt (its own model) and the `sdk` client are not checked here; neither are the read-only refusal, authentication or
error mapping of these routes.
