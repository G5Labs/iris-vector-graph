# Iteration 32: the same Cypher answer through three HTTP readers

Before image: seal 31 `51df2486`. Product `3eaa79cf` unchanged. The HTTP app ran in-process (FastAPI `TestClient`, no
listener) against the run-isolated fixture.

Provenance note: seal 31 accidentally includes `results/http_rows/` (this iteration's first prove, control and binding
receipts and logs; a temporary move of the iteration-32 files collided on the directory name). The model, binding
source, PAIRS and observations land in this seal; the receipts' input hashes identify them. Nothing was rewritten.

## W38

Step 5: an already-linked path (`execute_cypher`) with different final readers (`/api/cypher`, `/db/neo4j/tx/commit`,
`/db/{db}/query/v2`). Predictions frozen from `access.surfaces` and ADMIN_API; source-based expectations added, marked,
before observation ([http-PAIRS.md](http-PAIRS.md)).

- Held: every value and type agrees across the engine and the three routes (H1-H4, H6).
- **New discovery, Medium bug-plt-108**: the Neo4j-compatible routes return at most 1,000 rows and say nothing; only
  `/api/cypher` documents its `limitRows`. `access.surfaces` (whose rule this breaks) gains a "Today" bullet.
- Formal: [models/http_rows](../../../Verus_verification/models/http_rows/NOTES.md), 3 verified, 3 controls
  EXPECTED_FAIL (one first ERROR on a bad anchor, kept), in-process binding AGREES 36 comparisons.

## Recount

Active behavioral bindings 368 → **371** of 4,130 ([member-delta.json](member-delta.json)): `cypher_query`,
`neo4j_tx_commit`, `neo4j_query_v2` newly bound; `_run_cypher` gains a claim; lost 0.

## Step-5 judgment at this seal

Convergence is **not** supported. Of the nine retest workflows, four found something no one had recorded (W31 High
bug-tmp-102, W32 two Low, W38 Medium bug-plt-108, plus W37's widening), three repaired known suspicions (W30, W35, W36)
and two agreed (W33, W34). Every new discovery came from a final reader or entry point no iteration had examined, and
several such readers remain (GraphQL, the `sdk` client and the CLI's `query`, `/schema` and `/stats`, embedded
connections). Next: continue with those readers.
