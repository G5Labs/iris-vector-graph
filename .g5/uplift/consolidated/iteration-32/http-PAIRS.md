# W38: the same Cypher values through three HTTP readers — predictions frozen before observation

Frozen 2026-11-16, iteration 32. Before image: the iteration-31 seal. Product `3eaa79cf`. Fixture
`ivg-retest-20261116-iris`; the HTTP app is driven in-process with FastAPI's `TestClient` (no port is opened), with
`IRIS_*` pointing at the fixture and no API key.

Why this workflow: step 5 asks for an already-linked path where a different final reader could change the result.
`execute_cypher` and Bolt are bound; the HTTP readers (`/api/cypher`, `/db/neo4j/tx/commit`, `/db/neo4j/query/v2`) are
not, and earlier iterations found typing faults exactly at the engine's readers. Sources: owner `access.surfaces` (the
HTTP server serves Cypher and Neo4j-compatible routes), ADMIN_API; the routes' code was **not** read.

Values written through the Python API: node `p` = 7, 7.5, "7", true, [1, 2], and missing; relationship `w` = 1.5.

| Case | Reader | Prediction |
|---|---|---|
| H1 | `execute_cypher("MATCH ... RETURN x.p")` | 7, 7.5, "7", true, [1, 2], null; relationship 1.5 (iterations 16-24) |
| H2 | `POST /api/cypher` | the same JSON values as H1 |
| H3 | `POST /db/neo4j/tx/commit` | the same values in `results[0].data[i].row` |
| H4 | `POST /db/neo4j/query/v2` | the same values in `data.values` (typed or plain, whichever the route uses, consistently) |

### Added after reading the source, before any observation (exposed: source-informed)

All three routes call `_run_cypher(query, params, limit)` (cypher_api.py :239-265), which runs `execute_cypher` and keeps
at most `limit` rows (default 1000; `/api/cypher` passes `limitRows`). `/api/cypher` and `/query/v2` return through
FastAPI's encoder; `/tx/commit` builds a `JSONResponse` directly. Expectations:

| Case | Reader | Source-based expectation |
|---|---|---|
| H5 | `UNWIND range(1, 1200) AS i RETURN i` on each route | 1,000 rows on each; only `/api/cypher` says so (`rowCount` 1000, no total); `/tx/commit` and `/query/v2` give no sign of truncation |
| H6 | an aggregate such as `RETURN avg(x.p)`, `sum(...)` | the same value on every route, unless the engine returns a non-JSON type (then `/tx/commit` may fail where the others encode it) |

## Outcome ([observation](http-observed-20261116T221726Z.json); binding in `results/http_rows/`)

H1-H4 and H6 held: every value and type (7, 7.5, "7", true, [1, 2], null; relationship 1.5; avg 7.25, sum 14.5,
count 2) is the same from the engine and all three routes. H5 (source-based) held: 1,200 engine rows come back as
1,000 on every route; only `/api/cypher` documents the cap. **New discovery, Medium bug-plt-108**: the Neo4j routes cut
silently. Owner `access.surfaces` (whose rule the cut breaks) gains a "Today" bullet.
