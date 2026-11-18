# Bug review record — fresh findings audit

This file is outside the active bug register. All removed starting IDs and historical qualifications remain addressable here. Lack of reproduction is not proof of correctness. The exact sealed starting text is in [start/bugs_issues.md](start/bugs_issues.md); full source/evidence inventories are [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json). Seven stopped, never-filed candidates remain unassessed. No protected human status existed in the starting registers.

<a id="bug-str-002"></a>
### A cached algorithm answer computed over a write that later rolls back stays current

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [graph_structure_algo_cache_rollback](../../receipts/native/graph_structure_algo_cache_rollback.json) — connection 1 opens a transaction and adds edge `c→a` (token 655000→655001); connection 2 computes WCC (miss, put) and sees `c` joined to `a`; connection 1 rolls back (no `c→a` row); connection 3's WCC is a cache hit at token 655001 and still joins `c` to `a`.

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md](../../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md), [iris_src/src/Graph/KG/AlgoCache.cls](../../../../iris_src/src/Graph/KG/AlgoCache.cls), [iris_src/src/Graph/KG/TraversalBuild.cls](../../../../iris_src/src/Graph/KG/TraversalBuild.cls), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py), [specs/236-arno-callout-adoption/research-token-audit.md](../../../../specs/236-arno-callout-adoption/research-token-audit.md), [specs/236-arno-callout-adoption/spec.md](../../../../specs/236-arno-callout-adoption/spec.md), [tests/integration/test_236_token_write_paths.py](../../../../tests/integration/test_236_token_write_paths.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-002). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-002"></a>
### A failed BM25 insert or delete rolls back the caller's whole transaction

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [search_bm25_caller_txn_rollback](../../receipts/native/search_bm25_caller_txn_rollback.json) — on an engine over a plain DB-API connection, the caller opened a transaction, created a node, then called `bm25_insert` with a document whose ID is too long for a subscript; the insert raised `<SUBSCRIPT>` and `$TLEVEL` went from 1 to 0, and after the caller's commit its node is gone. [search_bm25_caller_txn_lock](../../receipts/native/search_bm25_caller_txn_lock.json) showed IRIS keeps the index lock until the caller's transaction ends, so W-O1d's lost-update trace (which assumes the lock is released at the inner `TCommit`) is not reachable; the finding rests on the rollback alone.

Source/test check: [docs/adr/0007-bm25-df-and-doc-record-schema-2.md](../../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_src/src/Graph/KG/Txn.cls](../../../../iris_src/src/Graph/KG/Txn.cls), [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py), [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py), [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-002). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-007"></a>
### Claiming the default embedding table for a model that already has a default-graph route makes that model's stored vectors unreadable

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [search_route_split](../../receipts/native/search_route_split.json) — a declared model stored a default-graph vector while `kg_NodeEmbeddings` was unclaimed (its own `kg_emb_…` route was created); after `kg_NodeEmbeddings` was claimed for the same model, two registry rows answer `('', model)` and `get_embedding` returns nothing although the vector is still in the `kg_emb_…` table.

Source/test check: [docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md](../../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md), [docs/migration/v4.0.0.md](../../../../docs/migration/v4.0.0.md), [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [tests/e2e/test_227_two_models.py](../../../../tests/e2e/test_227_two_models.py), [tests/integration/test_embedding_registry_e2e.py](../../../../tests/integration/test_embedding_registry_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-007). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-001"></a>
### The 4.0.0 documents migration can drop the documents table after its copy failed with a tolerated error

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/migration/v4.0.0.md](../../../../docs/migration/v4.0.0.md), [iris_vector_graph/migrations/__init__.py](../../../../iris_vector_graph/migrations/__init__.py), [iris_vector_graph/migrations/_commit.py](../../../../iris_vector_graph/migrations/_commit.py), [iris_vector_graph/migrations/kg_node_stores.py](../../../../iris_vector_graph/migrations/kg_node_stores.py), [iris_vector_graph/migrations/upgrade.py](../../../../iris_vector_graph/migrations/upgrade.py), [specs/240-alt-migration-as-data/spec.md](../../../../specs/240-alt-migration-as-data/spec.md), [specs/241-alt-single-graph-backfill/spec.md](../../../../specs/241-alt-single-graph-backfill/spec.md), [tests/e2e/test_262_upgrade_451.py](../../../../tests/e2e/test_262_upgrade_451.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-001). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0409"></a>
### A failed adjacency rebuild inside a caller's transaction rolls back the caller's work

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

[Exact starting entry](start/bugs_issues.md#F-0409). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0505"></a>
### The marker test differs between the deleters and the ledger

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

[Exact starting entry](start/bugs_issues.md#F-0505). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1804"></a>
### A snapshot carries no routed edge vectors (kg_eemb_ tables): a restore loses them silently

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/18.json](../../../../experiment/playbook-completion/findings/audit/18.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-edge-vectors`, `c18-live-edge-routes`

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py), [iris_vector_graph/security.py](../../../../iris_vector_graph/security.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1804). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-003"></a>
### A degree cached before a node is deleted and re-created can be served afterwards as current

Disposition: **inconclusive concurrency schedule**. Reproduction level: not reproduced in this audit.

The actual preserved degree ABA probe completed 3,129 rounds without a stale answer. That negative run does not establish the required interleaving or prove cache correctness.

Previous reproduction record: none yet — [graph_structure_degree_aba](../../receipts/native/graph_structure_degree_aba.json) ran 3 readers for 120 s (3,129 rounds, about 2.1 million degree calls) with no stale entry: INCONCLUSIVE, not evidence of absence; the reader count is bounded by Community's connection licence.

Source/test check: [docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md](../../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md), [iris_src/src/Graph/KG/Adj.cls](../../../../iris_src/src/Graph/KG/Adj.cls), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [specs/248-alt-parity-os/spec.md](../../../../specs/248-alt-parity-os/spec.md), [tests/e2e/test_degree_cache_live.py](../../../../tests/e2e/test_degree_cache_live.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-003). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-tmp-004"></a>
### A temporal write creates endpoint nodes that the ledger never recorded, so verify diverges after the ledger's own temporal operation

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [temporal_endpoint_nodes_verify](../../receipts/native/temporal_endpoint_nodes_verify.json) — V1 a direct write and V2 a ledger `create_temporal_edge` with a new endpoint ID: `verify()` diverges with `unrecorded_writes` on that node; V3 a temporal op followed by `upsert_node` in one changeset: diverges; V4 `[temporal, create_node]` is refused `node_exists` while `[create_node, temporal]` commits; V5 the same under strict mode. Controls C0 (known endpoints) and C1 (temporal-only predicate) stay equal.

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_src/src/Graph/KG/LedgerGenesis.cls](../../../../iris_src/src/Graph/KG/LedgerGenesis.cls), [iris_vector_graph/_engine/temporal.py](../../../../iris_vector_graph/_engine/temporal.py), [iris_vector_graph/ledger/replay.py](../../../../iris_vector_graph/ledger/replay.py), [specs/213-graph-revision-ledger/contracts/ledger-api.md](../../../../specs/213-graph-revision-ledger/contracts/ledger-api.md), [tests/e2e/test_460_ledger_temporal_edge_e2e.py](../../../../tests/e2e/test_460_ledger_temporal_edge_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-tmp-004). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-tmp-005"></a>
### Making a temporal-only predicate structural again before dropping its rows strands marked rows that nothing removes

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [temporal_marked_row_lifecycle](../../receipts/native/temporal_marked_row_lifecycle.json) case F8 — a marked row of a re-opted-in predicate with no timestamp survives delete, purge, drop (refused: the predicate is structural) and backfill. Cases K1–K3 (marker lifecycle, adoption, temporal-only write) behaved as specified.

Source/test check: [docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md](../../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md), [docs/adr/0015-temporal-structural-rows-opt-out.md](../../../../docs/adr/0015-temporal-structural-rows-opt-out.md), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/TemporalPolicy.cls](../../../../iris_src/src/Graph/KG/TemporalPolicy.cls), [specs/254-temporal-purge-collisions-rebuild/spec.md](../../../../specs/254-temporal-purge-collisions-rebuild/spec.md), [tests/e2e/test_252_temporal_rows_e2e.py](../../../../tests/e2e/test_252_temporal_rows_e2e.py), [tests/e2e/test_254_purge_e2e.py](../../../../tests/e2e/test_254_purge_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-tmp-005). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-tmp-011"></a>
### A temporal write that races a purge or delete of the same triple can leave a live timestamp with no structural edge

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md](../../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/TemporalIndex.cls](../../../../iris_src/src/Graph/KG/TemporalIndex.cls), [iris_vector_graph/_engine/temporal.py](../../../../iris_vector_graph/_engine/temporal.py), [specs/252-adjacency-functional-index/spec.md](../../../../specs/252-adjacency-functional-index/spec.md), [specs/254-temporal-purge-collisions-rebuild/spec.md](../../../../specs/254-temporal-purge-collisions-rebuild/spec.md), [tests/e2e/test_252_temporal_rows_e2e.py](../../../../tests/e2e/test_252_temporal_rows_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-tmp-011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-003"></a>
### Building or dropping a BM25 index while documents are inserted leaves its counters inconsistent

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [search_bm25_build_insert_race](../../receipts/native/search_bm25_build_insert_race.json) — 209 inserts committed inside Build's 0.39 s window; afterwards, with no Build in flight, 94 terms had a document frequency that disagreed with their postings (for example `df(beta0)=416` with 420 postings). The drop-inside-insert trace (W-O1c) was not probed.

Source/test check: [docs/adr/0007-bm25-df-and-doc-record-schema-2.md](../../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py), [specs/044-bm25-index/spec.md](../../../../specs/044-bm25-index/spec.md), [tests/integration/test_044_bm25_incremental.py](../../../../tests/integration/test_044_bm25_incremental.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-003). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-004"></a>
### A second or re-run BM25 upgrade rebuilds an index that is already upgraded, and searches answer nothing meanwhile

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [search_bm25_upgrade_concurrent](../../receipts/native/search_bm25_upgrade_concurrent.json) — two `Upgrade` calls on a 6,000-document schema-1 index both ran (`upgraded: 1` each); 205 of 210 searches for a term present in every document answered nothing while they ran; the final index was consistent. The crash-after-flip re-run (W-O2b) was not probed.

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [specs/044-bm25-index/spec.md](../../../../specs/044-bm25-index/spec.md), [tests/integration/test_044_bm25_incremental.py](../../../../tests/integration/test_044_bm25_incremental.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-004). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-009"></a>
### Named-graph edge vectors placed by the 4.0.0 migration cannot be found by edge vector search

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/migration/v4.0.0.md](../../../../docs/migration/v4.0.0.md), [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [tests/e2e/test_227_two_models.py](../../../../tests/e2e/test_227_two_models.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-009). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-010"></a>
### A failed vector leg makes the engine's fusion answer an empty list instead of an error

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none — the behavior is recorded by the product (KNOWN_ISSUES, measured during 4.7.0); not re-run here.

Source/test check: [docs/API_REFERENCE.md](../../../../docs/API_REFERENCE.md), [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [iris_vector_graph/fusion.py](../../../../iris_vector_graph/fusion.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-010). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-002"></a>
### Bolt sessions never close the IRIS connection their engine opened

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

Source and recorded observations were checked. The exact listener lifetime, route/capability, DDL-effect or algorithm-quality assertion has no completed fresh discriminating regression here; mentioning Arno does not make the ordinary fallback unavailable. Historical evidence remains intact; correctness is not inferred.

Previous reproduction record: none

Source/test check: [api/main.py](../../../../api/main.py), [docs/ADMIN_API.md](../../../../docs/ADMIN_API.md), [iris_src/src/Graph/KG/MCPTools.cls](../../../../iris_src/src/Graph/KG/MCPTools.cls), [iris_src/src/Graph/KG/Service.cls](../../../../iris_src/src/Graph/KG/Service.cls), [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py), [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-002). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-003"></a>
### Two concurrent first setups can both record their IVG Schema, and the loser keeps writing to its own tables

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0016-one-ivg-schema-per-namespace.md](../../../../docs/adr/0016-one-ivg-schema-per-namespace.md), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [specs/262-ivg-owned-sql-schema/data-model.md](../../../../specs/262-ivg-owned-sql-schema/data-model.md), [specs/262-ivg-owned-sql-schema/spec.md](../../../../specs/262-ivg-owned-sql-schema/spec.md), [tests/e2e/test_262_not_upgraded.py](../../../../tests/e2e/test_262_not_upgraded.py), [tests/e2e/test_262_record.py](../../../../tests/e2e/test_262_record.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-003). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-008"></a>
### Neo4j-compatible transactions are not transactions: Bolt ROLLBACK keeps the writes and the HTTP transaction endpoint commits statement by statement

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py), [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-008). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-010"></a>
### After the native library is replaced, routing can keep using the old library's proof report

Disposition: **environment-blocked**. Reproduction level: not reproduced in this audit.

The cited provider/platform premise is absent from the audit runtime or not established by the saved test. A source/model result cannot substitute for that caller/provider gate.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/ArnoAccel.cls](../../../../iris_src/src/Graph/KG/ArnoAccel.cls), [specs/236-arno-callout-adoption/spec.md](../../../../specs/236-arno-callout-adoption/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-010). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-011"></a>
### An interrupted BulkLoader node load cannot be resumed: re-loading skips the labels and properties of nodes already written

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md](../../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py), [tests/integration/test_bulk_loader_endpoints.py](../../../../tests/integration/test_bulk_loader_endpoints.py), [tests/integration/test_bulk_loader_live.py](../../../../tests/integration/test_bulk_loader_live.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-012"></a>
### BulkLoader ignores the namespace's IVG Schema

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [docs/adr/0016-one-ivg-schema-per-namespace.md](../../../../docs/adr/0016-one-ivg-schema-per-namespace.md), [iris_vector_graph/_engine/class_deploy.py](../../../../iris_vector_graph/_engine/class_deploy.py), [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py), [specs/262-ivg-owned-sql-schema/plan.md](../../../../specs/262-ivg-owned-sql-schema/plan.md), [specs/262-ivg-owned-sql-schema/research.md](../../../../specs/262-ivg-owned-sql-schema/research.md), [tests/integration/test_bulk_loader_endpoints.py](../../../../tests/integration/test_bulk_loader_endpoints.py), [tests/unit/test_bulk_loader_unit.py](../../../../tests/unit/test_bulk_loader_unit.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-012). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-024"></a>
### A replacing restore leaves the live search indexes in place and merges the archive's into them

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [docs/adr/0004-erasure-removes-content-not-history.md](../../../../docs/adr/0004-erasure-removes-content-not-history.md), [docs/adr/0013-redaction-removes-content-from-history.md](../../../../docs/adr/0013-redaction-removes-content-from-history.md), [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_src/src/Graph/KG/GraphStores.cls](../../../../iris_src/src/Graph/KG/GraphStores.cls), [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-024). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-cyp-003"></a>
### Text shortcuts meant for Neo4j Browser answer unrelated queries with canned rows

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py), [iris_vector_graph/cypher/read_only.py](../../../../iris_vector_graph/cypher/read_only.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-cyp-003). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-led-003"></a>
### A replayed commit applies its post-commit properties again over newer values and returns no statement IDs

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_vector_graph/ledger/changeset.py](../../../../iris_vector_graph/ledger/changeset.py), [specs/213-graph-revision-ledger/contracts/ledger-api.md](../../../../specs/213-graph-revision-ledger/contracts/ledger-api.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-led-003). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-016"></a>
### A BM25 delete issued while a Build runs is lost, and bug-srch-003's proposed repair does not prevent it

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [search_bm25_delete_during_build](../../receipts/native/search_bm25_delete_during_build.json) — while a rebuild of a 4,000-document index ran (0.71 s), two node deletes with their `bm25_delete` landed inside the window; both deletes answered False and both documents are still returned by a search after the rebuild.

Source/test check: [docs/adr/0007-bm25-df-and-doc-record-schema-2.md](../../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py), [specs/044-bm25-index/spec.md](../../../../specs/044-bm25-index/spec.md), [tests/integration/test_044_bm25_incremental.py](../../../../tests/integration/test_044_bm25_incremental.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-016). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0201"></a>
### A graph whose mode is off can hold two edges of one triple

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/02.json](../../../../experiment/playbook-completion/findings/audit/02.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-mode-off`

[Exact starting entry](start/bugs_issues.md#F-0201). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0202"></a>
### The name check is not run at every entry that takes a graph name

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/02.json](../../../../experiment/playbook-completion/findings/audit/02.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

Source/test check: [docs/adr/0003-two-graph-key-derivations.md](../../../../docs/adr/0003-two-graph-key-derivations.md), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0202). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0303"></a>
### A direct edge delete leaves the ledger's live link for the edge

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger-stmt`

[Exact starting entry](start/bugs_issues.md#F-0303). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0305"></a>
### A bulk write larger than one chunk is not one transaction on the server-loader path

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-bulk-atomicity`, `breadth-a-live-03-bulk-killed-client`

[Exact starting entry](start/bugs_issues.md#F-0305). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0307"></a>
### The server path of bulk_ingest_edges skips a refused edge without an error

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-writes`

[Exact starting entry](start/bugs_issues.md#F-0307). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0308"></a>
### The bulk loader stores a NaN or infinite edge property as JSON no reader accepts

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-writes`

[Exact starting entry](start/bugs_issues.md#F-0308). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0406"></a>
### Clearing the degree cache alone gives zeros while the warm stamp holds

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

[Exact starting entry](start/bugs_issues.md#F-0406). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0504"></a>
### Purges and the row drop delete node rows without the strict-mode check or a record

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

Source/test check: [iris_vector_graph/_engine/temporal.py](../../../../iris_vector_graph/_engine/temporal.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0504). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0510"></a>
### The millisecond index computes 'now' in seconds

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

[Exact starting entry](start/bugs_issues.md#F-0510). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0601"></a>
### A registry read that fails for any reason lets a vector write through unchecked

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-probe-local-0101-0601`, `rx-live-priv-vec`

Source/test check: [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0601). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0604"></a>
### The IRIS queue worker marks an entry DONE when no vector was made

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

[Exact starting entry](start/bugs_issues.md#F-0604). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0608"></a>
### Vector index stores do not check width or duplicates

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

[Exact starting entry](start/bugs_issues.md#F-0608). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0615"></a>
### A store_embeddings batch refused for a missing node can leave a new empty route behind

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

[Exact starting entry](start/bugs_issues.md#F-0615). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0616"></a>
### The embed selector's label filter crosses graphs, and its exclude pattern escapes without ESCAPE

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-selector`, `breadth-a-live-06-embed`

Source/test check: [iris_vector_graph/embed_selector.py](../../../../iris_vector_graph/embed_selector.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0616). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0618"></a>
### The ledger's node delete does not reach a default-graph node's routed vectors

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

Source/test check: [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0618). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0701"></a>
### BM25 Build and Drop write without the write lock or a transaction

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0701-race`, `b-07-fp-writers`

Source/test check: [docs/adr/0007-bm25-df-and-doc-record-schema-2.md](../../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [specs/044-bm25-index/spec.md](../../../../specs/044-bm25-index/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0701). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0703"></a>
### A BM25 index goes stale silently when node text changes

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0702-f0703`

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0703). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0704"></a>
### A refused index-handle build has already destroyed the old BM25 index

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0704`

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0704). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0706"></a>
### The stopword node __stop__ is listed and writable as a BM25 index

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0706`, `b-07-fp-writers`, `b-07-probe-fusion`

Source/test check: [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [iris_vector_graph/_validate.py](../../../../iris_vector_graph/_validate.py), [specs/044-bm25-index/spec.md](../../../../specs/044-bm25-index/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0706). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0709"></a>
### Fused searches can hide a failed leg

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0709`, `b-07-f0705-f0707`, `b-07-probe-fusion`

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [iris_vector_graph/fusion.py](../../../../iris_vector_graph/fusion.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0709). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0805"></a>
### A duplicate edge CREATE between literal endpoints fails the whole query instead of adding nothing

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0805`, `b-08-live-f0805-rerun`

Source/test check: [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0805). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0813"></a>
### Relationship filters conflate numeric-looking strings and numbers

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0813`, `b-08-live-f0813-rerun`

Source/test check: [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0813). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1007"></a>
### Degree centrality counts parallel edges on out-edges but not on in-edges

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/10.json](../../../../experiment/playbook-completion/findings/audit/10.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope2`

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/Centrality.cls](../../../../iris_src/src/Graph/KG/Centrality.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1007). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1103"></a>
### An adoption is not tied to the head it compared

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1103`, `b-11-live-f1103-reenable-race`

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_src/src/Graph/KG/LedgerGenesis.cls](../../../../iris_src/src/Graph/KG/LedgerGenesis.cls), [iris_vector_graph/ledger/replay.py](../../../../iris_vector_graph/ledger/replay.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1103). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1105"></a>
### Deleting a node that only a named graph holds records a delete that removed nothing

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`, `ib-HD1101-namedonly`

Source/test check: [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1105). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1107"></a>
### A commit accepts any revision kind

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`, `rx-live-11`

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_vector_graph/ledger/client.py](../../../../iris_vector_graph/ledger/client.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1107). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1508"></a>
### The Cypher API answers a failed FHIR-graph anchor read as a bridge lookup

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c15-live-anchors`

Source/test check: [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1508). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1601"></a>
### Bolt BEGIN, COMMIT and ROLLBACK do nothing; every RUN commits at once

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s1-cypher-http`

Source/test check: [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1601). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1602"></a>
### Bolt PULL {n} drops every row after the first n

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s1-cypher-http`

Source/test check: [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1602). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1607"></a>
### Two Cypher entries of the sample API bypass the engine and answer differently

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`, `c16-s1-cypher-http`

Source/test check: [api/gql/schema.py](../../../../api/gql/schema.py), [api/routers/cypher.py](../../../../api/routers/cypher.py), [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1607). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1609"></a>
### The FHIR event route's writes are not all-or-nothing

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

Source/test check: [api/routers/fhir_event.py](../../../../api/routers/fhir_event.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1609). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1610"></a>
### The Neo4j HTTP commit route runs its statements one by one

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s1-cypher-http`

Source/test check: [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1610). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1615"></a>
### The fraud server's vector lookup always falls back to zeros

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s5-fraud-sql-stream`

[Exact starting entry](start/bugs_issues.md#F-1615). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1712"></a>
### LazyKG.in_degree collapses parallel edges that degree() counts

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_vector_graph/stores/lazy_kg.py](../../../../iris_vector_graph/stores/lazy_kg.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1712). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1803"></a>
### Edge vectors lose their graph and metadata in a snapshot

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/18.json](../../../../experiment/playbook-completion/findings/audit/18.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-edge-routes`

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1803). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1805"></a>
### A merge restore overwrites temporal aggregates instead of combining them

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/18.json](../../../../experiment/playbook-completion/findings/audit/18.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-aggregates`

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1805). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0330"></a>
### A failed server-loader bulk_create_nodes answers 'nothing written' while its first 1,000 nodes stay committed

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-trace-replay.json](../../../../experiment/playbook-completion/findings/audit/zz-trace-replay.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM)

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_vector_graph/_batch_check.py](../../../../iris_vector_graph/_batch_check.py), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0330). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0348"></a>
### Racing create_edge calls on a new edge whose endpoint is new can all lose: some answer False ('already exists') and no edge is written

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-keys-race-edge`, `st-live-keys`

Source/test check: [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0348). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0349"></a>
### The bulk loader writes duplicate node, label, property and edge keys: an id twice in one batch, a load with skip_existing=False, or two loaders at once

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-keys`

Source/test check: [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0349). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0350"></a>
### BulkLoader.load_edges' INSERT %NOINDEX %NOCHECK lets a graph whose mode is off hold two rows of one triple at the same edge key, and the index rebuild accepts them

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-writesets.json](../../../../experiment/playbook-completion/findings/audit/zz-writesets.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-ba-noindex-parallel`

Source/test check: [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py), [specs/234-multigraph-parallel-edges/spec.md](../../../../specs/234-multigraph-parallel-edges/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0350). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0450"></a>
### A ledger relationship whose qualifiers hold temporal=1 is deleted as a temporal edge's derived row, and its statement stays live

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-writesets.json](../../../../experiment/playbook-completion/findings/audit/zz-writesets.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-stmt-collision`, `ws-live-stmt-purge`

Source/test check: [docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md](../../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls), [iris_src/src/Graph/KG/TemporalPolicy.cls](../../../../iris_src/src/Graph/KG/TemporalPolicy.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0450). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0701"></a>
### An index built under the stopword name makes index-structure words stopwords in every BM25 index

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0706`

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0701). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0748"></a>
### One token longer than the subscript limit in any document makes bm25_build fail after it has emptied the index, and searches then answer nothing

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-cap-bm25`

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0748). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0803"></a>
### MERGE ... ON CREATE SET r = a gives every merged relationship the first row's properties

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-storage-order`

Source/test check: [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0803). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1601"></a>
### A finished Bolt session never gives back its IRIS connection

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

Source and recorded observations were checked. The exact listener lifetime, route/capability, DDL-effect or algorithm-quality assertion has no completed fresh discriminating regression here; mentioning Arno does not make the ordinary fallback unavailable. Historical evidence remains intact; correctness is not inferred.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s2-bolt-sessions`

Source/test check: [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1601). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1604"></a>
### The Cypher HTTP server runs a query again after any failure, writes included

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s4-server-retry`, `c16-s1-cypher-http`

Source/test check: [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1604). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1703"></a>
### One HTTP client call can create a write twice (client resend after a late reply; server re-run after an exception)

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-server`

Source/test check: [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py), [iris_vector_graph/sdk.py](../../../../iris_vector_graph/sdk.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1703). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1750"></a>
### A refused Eraser probe is cached as 'absent': the store's deletes then run as plain SQL and leave the ledger statements of the deleted edges live

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json](../../../../experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-sql-fallback-priv`

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_vector_graph/_dictionary.py](../../../../iris_vector_graph/_dictionary.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1750). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1801"></a>
### save_snapshot archives writes that never commit

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/18.json](../../../../experiment/playbook-completion/findings/audit/18.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-dirty-export`

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1801). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1802"></a>
### restore_snapshot drops a global line it cannot write without raising or counting it

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/18.json](../../../../experiment/playbook-completion/findings/audit/18.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-swallowed-lines`, `rx-live-18`

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py), [tests/integration/test_snapshot_inventory.py](../../../../tests/integration/test_snapshot_inventory.py), [tests/unit/test_460_r271_snapshot_raises.py](../../../../tests/unit/test_460_r271_snapshot_raises.py), [tests/unit/test_snapshot_inventory.py](../../../../tests/unit/test_snapshot_inventory.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1802). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-104"></a>
### A PPR limit above the native cap can turn truncated positive scores into zero

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: `root-ppr-cap-native.py` on the identity-guarded task-owned IRIS: ordinary successful1002-node bulk write without index disable/rebuild; actual public native/store PPR entry and actual private Python fallback using the same real DB. No external service/security scenario or physical unavailable-provider dispatch reproduction.

Source/test check: [iris_src/src/Graph/KG/PageRank.cls](../../../../iris_src/src/Graph/KG/PageRank.cls), [iris_vector_graph/_engine/algorithms.py](../../../../iris_vector_graph/_engine/algorithms.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-104). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-006"></a>
### Concurrent writers of one multigraph triple can lose its multiplicity or leave a ghost edge entry

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py), [specs/234-multigraph-parallel-edges/spec.md](../../../../specs/234-multigraph-parallel-edges/spec.md), [specs/252-adjacency-functional-index/spec.md](../../../../specs/252-adjacency-functional-index/spec.md), [tests/e2e/test_234_multigraph_storage_e2e.py](../../../../tests/e2e/test_234_multigraph_storage_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-006). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-007"></a>
### Restoring a multigraph archive into an indexed namespace loses its parallel edges' multiplicity

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py), [specs/234-multigraph-parallel-edges/spec.md](../../../../specs/234-multigraph-parallel-edges/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-007). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-009"></a>
### A failed indexed rebuild, or a failed rebuild after a bulk load, leaves a partial adjacency index

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md](../../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_src/src/Graph/KG/TraversalBuild.cls](../../../../iris_src/src/Graph/KG/TraversalBuild.cls), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py), [specs/248-alt-parity-os/spec.md](../../../../specs/248-alt-parity-os/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-009). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-010"></a>
### Node interning runs inside the functional-index callback, which ADR-0008 rules out

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md](../../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [iris_src/src/Graph/KG/AdjIndex.cls](../../../../iris_src/src/Graph/KG/AdjIndex.cls), [iris_src/src/Graph/KG/LabelIndex.cls](../../../../iris_src/src/Graph/KG/LabelIndex.cls), [specs/252-adjacency-functional-index/spec.md](../../../../specs/252-adjacency-functional-index/spec.md), [tests/e2e/test_252_writer_paths_e2e.py](../../../../tests/e2e/test_252_writer_paths_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-010). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-011"></a>
### The keyed adjacency writers turn errors into statuses that IRIS ignores, so a row can commit without its entry

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md](../../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [iris_src/src/Graph/KG/AdjIndex.cls](../../../../iris_src/src/Graph/KG/AdjIndex.cls), [iris_src/src/Graph/KG/LabelIndex.cls](../../../../iris_src/src/Graph/KG/LabelIndex.cls), [specs/252-adjacency-functional-index/spec.md](../../../../specs/252-adjacency-functional-index/spec.md), [tests/e2e/test_252_writer_paths_e2e.py](../../../../tests/e2e/test_252_writer_paths_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-012"></a>
### A ledger qualifier update reweights a multigraph triple's leaf to an edge that is not the lowest

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md](../../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py), [specs/234-multigraph-parallel-edges/spec.md](../../../../specs/234-multigraph-parallel-edges/spec.md), [specs/252-adjacency-functional-index/spec.md](../../../../specs/252-adjacency-functional-index/spec.md), [tests/e2e/test_234_multigraph_storage_e2e.py](../../../../tests/e2e/test_234_multigraph_storage_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-012). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-013"></a>
### Deleting a relationship with delete_edge or Cypher DELETE leaves its reifications, edge embeddings and ledger statement behind

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0004-erasure-removes-content-not-history.md](../../../../docs/adr/0004-erasure-removes-content-not-history.md), [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py), [specs/256-ledger-tenant-redaction/plan.md](../../../../specs/256-ledger-tenant-redaction/plan.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

Iteration 65 reproduction ([erasure_stores binding](../../results/erasure_stores/20261118T043516Z-binding/receipt.json), namespace I65C): `delete_edge("k3", "R", "k4", graph="g1")` removed the relationship row and its adjacency and left its live ledger statement, its tuple lookup and its reification (case `C7_delete_edge_bypass`). Passing neighbour: `store.delete_edges([("k1", "R", "k2")], graph="g1")` removed the statement and tuple with the row (`C6_store_delete_edges`). Cypher `DELETE` was not exercised. Model: [erasure_stores](../../models/erasure_stores/NOTES.md) `witness_delete_edge_leaves_statement`, control `delete-edge-through-eraser`.

[Exact starting entry](start/bugs_issues.md#bug-str-013). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-015"></a>
### Without the adjacency index, edge writers write adjacency on a second connection that commits separately from the row

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-015). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-tmp-006"></a>
### Two Python temporal paths write structural rows for a temporal-only predicate

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0015-temporal-structural-rows-opt-out.md](../../../../docs/adr/0015-temporal-structural-rows-opt-out.md), [iris_vector_graph/_engine/temporal_only_warning.py](../../../../iris_vector_graph/_engine/temporal_only_warning.py), [tests/e2e/test_temporal_structural_optout_e2e.py](../../../../tests/e2e/test_temporal_structural_optout_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-tmp-006). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-tmp-008"></a>
### The ObjectScript temporal purge-all and erase-all leave marked structural rows

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md](../../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md), [iris_src/src/Graph/KG/TemporalIndex.cls](../../../../iris_src/src/Graph/KG/TemporalIndex.cls), [specs/239-alt-temporal-erase/spec.md](../../../../specs/239-alt-temporal-erase/spec.md), [specs/254-temporal-purge-collisions-rebuild/spec.md](../../../../specs/254-temporal-purge-collisions-rebuild/spec.md), [specs/256-ledger-tenant-redaction/spec.md](../../../../specs/256-ledger-tenant-redaction/spec.md), [tests/e2e/test_254_purge_e2e.py](../../../../tests/e2e/test_254_purge_e2e.py), [tests/e2e/test_255_window_reader_us3_e2e.py](../../../../tests/e2e/test_255_window_reader_us3_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-tmp-008). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-tmp-013"></a>
### A temporal write inside a purge's range that lands after the purge removed the row leaves a marked row with no timestamp

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md](../../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/TemporalIndex.cls](../../../../iris_src/src/Graph/KG/TemporalIndex.cls), [specs/254-temporal-purge-collisions-rebuild/spec.md](../../../../specs/254-temporal-purge-collisions-rebuild/spec.md), [tests/e2e/test_252_temporal_rows_e2e.py](../../../../tests/e2e/test_252_temporal_rows_e2e.py), [tests/e2e/test_254_purge_e2e.py](../../../../tests/e2e/test_254_purge_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-tmp-013). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-011"></a>
### Fusion chooses indexes from a snapshot taken when the engine started

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [tests/e2e/test_230_retrieval_scope.py](../../../../tests/e2e/test_230_retrieval_scope.py), [tests/unit/test_460_rrf_leg_prefers_graphs_own_index.py](../../../../tests/unit/test_460_rrf_leg_prefers_graphs_own_index.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-014"></a>
### The embedding queue marks entries done without a stored vector

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/EmbedQueue.cls](../../../../iris_src/src/Graph/KG/EmbedQueue.cls), [iris_src/src/Graph/KG/EmbedQueueTask.cls](../../../../iris_src/src/Graph/KG/EmbedQueueTask.cls), [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-014). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-srch-015"></a>
### Route creation commits the routed table before its registry row, and an orphaned table makes every erase in the namespace fail

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [tests/e2e/test_227_two_models.py](../../../../tests/e2e/test_227_two_models.py), [tests/integration/test_227_orphan_route_erase.py](../../../../tests/integration/test_227_orphan_route_erase.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-srch-015). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-014"></a>
### remove_legacy_objects reports later procedures of a class as removed when the class's delete failed

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0016-one-ivg-schema-per-namespace.md](../../../../docs/adr/0016-one-ivg-schema-per-namespace.md), [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py), [iris_vector_graph/_engine/legacy.py](../../../../iris_vector_graph/_engine/legacy.py), [specs/262-ivg-owned-sql-schema/spec.md](../../../../specs/262-ivg-owned-sql-schema/spec.md), [tests/e2e/test_262_upgrade_451.py](../../../../tests/e2e/test_262_upgrade_451.py), [tests/e2e/test_460_legacy_manifest_320_loader_e2e.py](../../../../tests/e2e/test_460_legacy_manifest_320_loader_e2e.py), [tests/e2e/test_460_legacy_manifest_400_e2e.py](../../../../tests/e2e/test_460_legacy_manifest_400_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-014). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-015"></a>
### An engine whose schema name differs only in case from the record loads classes under its own spelling

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_vector_graph/schema_name.py](../../../../iris_vector_graph/schema_name.py), [specs/262-ivg-owned-sql-schema/spec.md](../../../../specs/262-ivg-owned-sql-schema/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-015). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-016"></a>
### A restore swallows a global line that fails to import

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-016). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-018"></a>
### Capabilities and status report native algorithms that are not proven or routed

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

Source and recorded observations were checked. The exact listener lifetime, route/capability, DDL-effect or algorithm-quality assertion has no completed fresh discriminating regression here; mentioning Arno does not make the ordinary fallback unavailable. Historical evidence remains intact; correctness is not inferred.

Previous reproduction record: none

Source/test check: [docs/dev/arno-reader-proof.json](../../../../docs/dev/arno-reader-proof.json), [iris_vector_graph/arno_readers.py](../../../../iris_vector_graph/arno_readers.py), [specs/236-arno-callout-adoption/spec.md](../../../../specs/236-arno-callout-adoption/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-018). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-019"></a>
### The HTTP server and the SDK retry a failed Cypher write, so a write can apply twice

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py), [iris_vector_graph/sdk.py](../../../../iris_vector_graph/sdk.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-019). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-020"></a>
### The MCP evidence search binds its natural-language input as a node ID

Disposition: **environment-blocked**. Reproduction level: not reproduced in this audit.

The public %AI MCP tool and real embedding provider are absent. Binding natural-language text as an ID is source evidence, not an observed successful application result.

Previous reproduction record: none

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_src/src/Graph/KG/MCPToolSet.cls](../../../../iris_src/src/Graph/KG/MCPToolSet.cls), [iris_src/src/Graph/KG/MCPTools.cls](../../../../iris_src/src/Graph/KG/MCPTools.cls), [tests/integration/test_mcp_tools.py](../../../../tests/integration/test_mcp_tools.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-020). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-021"></a>
### The Txn_End and Txn_Undo SQL procedures end every transaction level, the caller's included

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/Txn.cls](../../../../iris_src/src/Graph/KG/Txn.cls), [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py), [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py), [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py), [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-021). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-cyp-004"></a>
### A write inside CALL { } is refused with a raw SQL syntax error instead of a clear refusal

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: [cypher_subquery_write](../../receipts/native/cypher_subquery_write.json) — `CALL { CREATE (n:SubqProbe {id: 'subq|1'}) } RETURN 1 AS one` returned a result whose `error` field holds SQLCODE -12 ("A term expected…"), raised nothing and wrote nothing; a plain `CREATE` wrote its node. This meets "carried out or refused" (verdict OBSERVED_AS_EXPECTED for that intent); the defect is the form of the refusal.

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [docs/dev/TCK.md](../../../../docs/dev/TCK.md), [iris_vector_graph/cypher/ast.py](../../../../iris_vector_graph/cypher/ast.py), [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py), [specs/229-tck-write-verification/spec.md](../../../../specs/229-tck-write-verification/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-cyp-004). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-led-002"></a>
### A ledger commit into a graph during its erase can lose the new relationship's statement entry

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_src/src/Graph/KG/LedgerRedact.cls](../../../../iris_src/src/Graph/KG/LedgerRedact.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-led-002). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-016"></a>
### Without the adjacency index, a temporal write to an existing triple changes its stored weight without moving the version token

Disposition: **environment-blocked**. Reproduction level: not reproduced in this audit.

The cited provider/platform premise is absent from the audit runtime or not established by the saved test. A source/model result cannot substitute for that caller/provider gate.

Previous reproduction record: none

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py), [iris_vector_graph/algo_cache.py](../../../../iris_vector_graph/algo_cache.py), [specs/236-arno-callout-adoption/research-token-audit.md](../../../../specs/236-arno-callout-adoption/research-token-audit.md), [tests/integration/test_236_token_write_paths.py](../../../../tests/integration/test_236_token_write_paths.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-016). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-026"></a>
### Setup records an explicitly named schema while IVG's tables sit in one other schema

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py), [specs/262-ivg-owned-sql-schema/data-model.md](../../../../specs/262-ivg-owned-sql-schema/data-model.md), [specs/262-ivg-owned-sql-schema/spec.md](../../../../specs/262-ivg-owned-sql-schema/spec.md), [tests/e2e/test_262_record.py](../../../../tests/e2e/test_262_record.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-026). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-led-011"></a>
### Erasing a long list of node IDs or relationships without a caller's transaction commits once per 500 entries

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [docs/adr/0004-erasure-removes-content-not-history.md](../../../../docs/adr/0004-erasure-removes-content-not-history.md), [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py), [tests/integration/test_eraser_failures.py](../../../../tests/integration/test_eraser_failures.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

Iteration 65 reproduction ([erasure_stores binding](../../results/erasure_stores/20261118T043516Z-binding/receipt.json), namespace I65E): `IRISGraphStore.delete_nodes(500 ids + [an over-long id, n0500], graph="g1")` without a caller's transaction raised `RuntimeError <THROW>` from the second chunk's `EraseNodeIds`; the first 500 node rows (and their labels and properties) were erased and committed, n0500 was kept (case `E4_unjoined_chunk_commits`). Passing neighbour: the same failure inside a caller's transaction erased nothing and kept the caller's own write after its commit (`E3_joined_list_failure_caller_commit`). The over-long ID is caller-supplied input, so the trigger is reachable in production. Model: [erasure_stores](../../models/erasure_stores/NOTES.md) `witness_list_erase_commits_earlier_chunk`, control `chunks-all-or-nothing`.

[Exact starting entry](start/bugs_issues.md#bug-led-011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-027"></a>
### BulkLoader's node and edge loads write without indexes and return before rebuilding them

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md](../../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py), [specs/252-adjacency-functional-index/spec.md](../../../../specs/252-adjacency-functional-index/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-027). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-str-017"></a>
### Nothing reports an existing graph whose name is now refused, as ADR-0003 promises, and verification itself refuses the name "0"

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none

Source/test check: [docs/adr/0003-two-graph-key-derivations.md](../../../../docs/adr/0003-two-graph-key-derivations.md), [iris_src/src/Graph/KG/GraphVerify.cls](../../../../iris_src/src/Graph/KG/GraphVerify.cls), [iris_src/src/Graph/KG/TraversalBuild.cls](../../../../iris_src/src/Graph/KG/TraversalBuild.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-str-017). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-test-001"></a>
### The eigenvector routing unit test fails at the baseline because its mock store lacks the loners argument

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: `tests/unit/test_centrality_unit.py::TestEngineRoutingThroughStore::test_eigenvector_routes_to_store` fails alone without IRIS (log `$RUN_DIR/tests/centrality-isolated.log`): `1 failed`.

Source/test check: [tests/unit/test_centrality_unit.py](../../../../tests/unit/test_centrality_unit.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-test-001). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-led-101"></a>
### A property changed before node deletion loses its range-start prior in a lifecycle diff

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: none on IRIS in this iteration. Python `GraphLedger.diff` and `GraphLedger.reconstruct` execute with SQL, revision IDs and ObjectScript records substituted; [binding receipt](../../results/history_diff/20261115T065234Z-binding/receipt.json).

Source/test check: [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls), [iris_vector_graph/ledger/client.py](../../../../iris_vector_graph/ledger/client.py), [iris_vector_graph/ledger/export.py](../../../../iris_vector_graph/ledger/export.py), [iris_vector_graph/ledger/replay.py](../../../../iris_vector_graph/ledger/replay.py), [specs/213-graph-revision-ledger/contracts/ledger-api.md](../../../../specs/213-graph-revision-ledger/contracts/ledger-api.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-led-101). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0101"></a>
### Legacy removal reports objects removed that may still be there

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/_engine/legacy.py](../../../../iris_vector_graph/_engine/legacy.py), [specs/262-ivg-owned-sql-schema/data-model.md](../../../../specs/262-ivg-owned-sql-schema/data-model.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0101). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0102"></a>
### Some setup failures are only logged, not put in the reply's warnings

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0102). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0103"></a>
### The first-use check accepts a namespace with no schema record

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-01-install`

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [iris_vector_graph/schema_name.py](../../../../iris_vector_graph/schema_name.py), [specs/262-ivg-owned-sql-schema/spec.md](../../../../specs/262-ivg-owned-sql-schema/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0103). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0104"></a>
### Spec 240 says its design was not adopted, but it ships

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/migrations/docs_and_edge_vectors.py](../../../../iris_vector_graph/migrations/docs_and_edge_vectors.py), [specs/240-alt-migration-as-data/spec.md](../../../../specs/240-alt-migration-as-data/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0104). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0105"></a>
### The SQL files under sql/ describe an old schema and put objects outside the IVG Schema

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (confirmed-source)

[Exact starting entry](start/bugs_issues.md#F-0105). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0107"></a>
### Every setup runs an unqualified DROP INDEX

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0107). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0108"></a>
### The upstream test deploy does not follow setup's skip rules

Disposition: **source observation outside active bugs**. Reproduction level: not reproduced in this audit.

This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [tests/conftest.py](../../../../tests/conftest.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0108). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0109"></a>
### The 4.0.0 upgrade does not follow the namespace's schema

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/adr/0016-one-ivg-schema-per-namespace.md](../../../../docs/adr/0016-one-ivg-schema-per-namespace.md), [iris_vector_graph/migrations/upgrade.py](../../../../iris_vector_graph/migrations/upgrade.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0109). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0110"></a>
### ADR-0016 lags the shipped design

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/01.json](../../../../experiment/playbook-completion/findings/audit/01.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/adr/0016-one-ivg-schema-per-namespace.md](../../../../docs/adr/0016-one-ivg-schema-per-namespace.md), [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0110). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0203"></a>
### The Python name check refuses fewer control characters than the server check

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/02.json](../../../../experiment/playbook-completion/findings/audit/02.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

[Exact starting entry](start/bugs_issues.md#F-0203). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0205"></a>
### Direct edge writes, the ledger and Bolt do not track parallel edges, and the user docs do not say so

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/02.json](../../../../experiment/playbook-completion/findings/audit/02.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls), [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0205). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0207"></a>
### Turning the mode off races a write that adds a parallel edge

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-model`; [experiment/playbook-completion/findings/audit/02.json](../../../../experiment/playbook-completion/findings/audit/02.json).

Previous reproduction record: none (reproduced-model)

Source/test check: [iris_src/src/Graph/KG/GraphMode.cls](../../../../iris_src/src/Graph/KG/GraphMode.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0207). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0301"></a>
### The bulk loader writes while ledger strict mode is on

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0301). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0302"></a>
### Strict mode reaches another engine only after its five-second cache expires

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

Source/test check: [iris_vector_graph/ledger/guard.py](../../../../iris_vector_graph/ledger/guard.py), [tests/unit/test_ledger_guard.py](../../../../tests/unit/test_ledger_guard.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0302). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0306"></a>
### create_node answers False for a write IRIS refuses as invalid

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-writes`

[Exact starting entry](start/bugs_issues.md#F-0306). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0309"></a>
### The bulk loader rebuilds the indexes of Graph_KG whatever schema it loaded

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/bulk_loader.py](../../../../iris_vector_graph/bulk_loader.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0309). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0401"></a>
### A killed source generation can let an in-flight reader store a wrong out-degree

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `intent-undecided`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: none (intent-undecided)

Source/test check: [iris_src/src/Graph/KG/Adj.cls](../../../../iris_src/src/Graph/KG/Adj.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0401). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0404"></a>
### Snapshot restore writes the adjacency index outside the one writer where the row hook is not declared

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0404). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0405"></a>
### Some weight refreshes do not move the graph-version token

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

[Exact starting entry](start/bugs_issues.md#F-0405). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0407"></a>
### Reweight takes no writer lock and moves no generation, against ADR-0012 and spec 252 FR-004

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

Source/test check: [tests/e2e/test_degree_cache_live.py](../../../../tests/e2e/test_degree_cache_live.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0407). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0408"></a>
### Comments and docs still describe adjacency behaviour that changed

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/EdgeScan.cls](../../../../iris_src/src/Graph/KG/EdgeScan.cls), [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0408). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0503"></a>
### A temporal write can create node rows that the ledger never records

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `intent-undecided`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: none (intent-undecided)

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0503). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0506"></a>
### Without the adjacency index, the Python mirror writes an unmarked row for any predicate

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/temporal.py](../../../../iris_vector_graph/_engine/temporal.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0506). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0511"></a>
### A changeset's insert-mode temporal op is recorded even when it collides

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

Source/test check: [iris_vector_graph/ledger/changeset.py](../../../../iris_vector_graph/ledger/changeset.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0511). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0512"></a>
### The batch field that suppresses the reverse index is not the one spec 204 names

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

Source/test check: [specs/204-temporal-index-gaps/spec.md](../../../../specs/204-temporal-index-gaps/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0512). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0513"></a>
### Temporal writes validate their input on one path only

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-purge`

Source/test check: [iris_vector_graph/_validate.py](../../../../iris_vector_graph/_validate.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0513). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0514"></a>
### The Python structural-row migration cannot read a large graph

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/05.json](../../../../experiment/playbook-completion/findings/audit/05.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/temporal.py](../../../../iris_vector_graph/_engine/temporal.py), [iris_vector_graph/migrations/temporal_structural_rows.py](../../../../iris_vector_graph/migrations/temporal_structural_rows.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0514). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0602"></a>
### Vectors from one model can be stored under another model's identity

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0602). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0603"></a>
### The IRIS queue worker writes vectors with no identity check, and ignores the model for the default graph

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/EmbedQueue.cls](../../../../iris_src/src/Graph/KG/EmbedQueue.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0603). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0605"></a>
### enqueue_for_embedding checks the default table's row, not the target graph's route

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0605). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0611"></a>
### Edge vectors the upgrade places in a named graph are not found by edge search, and the edge and text quarantines have no API

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/migrations/statements.py](../../../../iris_vector_graph/migrations/statements.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0611). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0612"></a>
### The edge and table searches skip rules the node search keeps

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0612). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0613"></a>
### VectorOptimizer.migrate_to_optimized writes vectors without the identity check and reports success with failures

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/vector_utils.py](../../../../iris_vector_graph/vector_utils.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0613). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0614"></a>
### embed_nodes and embed_edges count an identity refusal as an error and return normally

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-embed`

Source/test check: [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0614). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0617"></a>
### The glossary and user guide say a second model's write is refused; the code routes it to its own table

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py), [tests/integration/test_embedding_identity_refusal_e2e.py](../../../../tests/integration/test_embedding_identity_refusal_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0617). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0708"></a>
### Spec 044 states behaviour the code no longer has

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [specs/044-bm25-index/spec.md](../../../../specs/044-bm25-index/spec.md), [tests/unit/test_bm25_index.py](../../../../tests/unit/test_bm25_index.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0708). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0710"></a>
### Weighted fusion's default weights go to legs by position, not by kind

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/fusion.py](../../../../iris_vector_graph/fusion.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0710). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0804"></a>
### Lexer errors are Python SyntaxError, not CypherParseError

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0804`, `b-08-live-f0804-rerun`

Source/test check: [iris_vector_graph/cypher/lexer.py](../../../../iris_vector_graph/cypher/lexer.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0804). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0806"></a>
### A stepped write's error message says earlier steps are kept

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0806`, `b-08-live-f0806-rerun`

Source/test check: [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0806). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0807"></a>
### Some refused writes raise ValueError or SyntaxError, not GraphWriteError

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0807`, `b-08-live-f0807-rerun`

Source/test check: [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py), [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0807). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0809"></a>
### MERGE ON CREATE SET / ON MATCH SET value shapes fail (documented, 4.7.1)

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0809`, `b-08-live-f0809-rerun`

Source/test check: [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0809). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0811"></a>
### RETURN r.p of an edge number past 64 bits answers an integer

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0811`, `b-08-live-f0811-rerun`

Source/test check: [iris_vector_graph/prop_values.py](../../../../iris_vector_graph/prop_values.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0811). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0812"></a>
### A whole-number result of SET arithmetic reads back as an integer

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0812`, `b-08-live-f0812-rerun`

Source/test check: [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0812). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0821"></a>
### The published TCK figures cannot be tied to this repository

Disposition: **source observation outside active bugs**. Reproduction level: not reproduced in this audit.

This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/dev/TCK.md](../../../../docs/dev/TCK.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0821). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0825"></a>
### An expression the translator does not handle becomes SQL NULL

Disposition: **unreachable in checked inputs**. Reproduction level: not reproduced in this audit.

The six preserved ordinary parser/translator shape checks did not reach the NULL fall-through; accepted AST reachability remains unestablished. This is bounded caller-unreachability evidence, not a universal proof.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0825). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0903"></a>
### The namespace compile mode is not checked: any value but job or off acts as sync

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/09.json](../../../../experiment/playbook-completion/findings/audit/09.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0903-mode`

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_src/src/Graph/KG/Cypher/Gen.cls](../../../../iris_src/src/Graph/KG/Cypher/Gen.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0903). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0905"></a>
### A deploy's drop does not wait for builds already running

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/09.json](../../../../experiment/playbook-completion/findings/audit/09.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0905-dropall-race`

Source/test check: [iris_src/src/Graph/KG/Cypher/Gen.cls](../../../../iris_src/src/Graph/KG/Cypher/Gen.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0905). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0906"></a>
### The native gate checks the edge index but not the label index

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-model`; [experiment/playbook-completion/findings/audit/09.json](../../../../experiment/playbook-completion/findings/audit/09.json).

Previous reproduction record: none (reproduced-model)

Source/test check: [iris_vector_graph/cypher/native_plan.py](../../../../iris_vector_graph/cypher/native_plan.py), [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0906). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0907"></a>
### Shadow mode holds any ordered projection to a fixed row order, ties included

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/09.json](../../../../experiment/playbook-completion/findings/audit/09.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0907-shadow-ties`

Source/test check: [docs/dev/TCK.md](../../../../docs/dev/TCK.md), [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py), [iris_vector_graph/cypher/native_plan.py](../../../../iris_vector_graph/cypher/native_plan.py), [iris_vector_graph/cypher/native_shadow.py](../../../../iris_vector_graph/cypher/native_shadow.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0907). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0909"></a>
### Spec 253's 'same process' reason for seeing one's own writes is not what the code does

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/09.json](../../../../experiment/playbook-completion/findings/audit/09.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0909-txn-visibility`

Source/test check: [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py), [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py), [specs/253-native-cypher-executor/spec.md](../../../../specs/253-native-cypher-executor/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0909). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1005"></a>
### The interned snapshot can lack edges with nothing saying it is out of date

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/10.json](../../../../experiment/playbook-completion/findings/audit/10.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/TemporalIndex.cls](../../../../iris_src/src/Graph/KG/TemporalIndex.cls), [iris_src/src/Graph/KG/TraversalBuild.cls](../../../../iris_src/src/Graph/KG/TraversalBuild.cls), [iris_vector_graph/_engine/temporal.py](../../../../iris_vector_graph/_engine/temporal.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1005). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1010"></a>
### Leiden's server route ignores max_levels and tol

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/10.json](../../../../experiment/playbook-completion/findings/audit/10.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/Communities.cls](../../../../iris_src/src/Graph/KG/Communities.cls), [iris_vector_graph/_engine/algorithms.py](../../../../iris_vector_graph/_engine/algorithms.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1010). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1011"></a>
### Documents describe snapshot behaviour the code no longer has

Disposition: **source observation outside active bugs**. Reproduction level: not reproduced in this audit.

This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/10.json](../../../../experiment/playbook-completion/findings/audit/10.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_vector_graph/_engine/algorithms.py](../../../../iris_vector_graph/_engine/algorithms.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1012"></a>
### The proof record names one library build for entries proven on different builds

Disposition: **environment-blocked**. Reproduction level: not reproduced in this audit.

The cited provider/platform premise is absent from the audit runtime or not established by the saved test. A source/model result cannot substitute for that caller/provider gate.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/10.json](../../../../experiment/playbook-completion/findings/audit/10.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/_arno_gate.py](../../../../iris_vector_graph/_arno_gate.py), [tests/unit/test_236_reader_gate.py](../../../../tests/unit/test_236_reader_gate.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1012). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1102"></a>
### The stats row can lose counts

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1102-contention`, `b-11-live-f1102-locktimeout`, `b-11-live-f1102-txn`

Source/test check: [docs/ledger-prometheus-hook.md](../../../../docs/ledger-prometheus-hook.md), [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_src/src/Graph/KG/LedgerStats.cls](../../../../iris_src/src/Graph/KG/LedgerStats.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1102). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1104"></a>
### Two first enables at once: the second fails instead of returning the genesis

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1104`

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [specs/213-graph-revision-ledger/contracts/ledger-api.md](../../../../specs/213-graph-revision-ledger/contracts/ledger-api.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1104). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1106"></a>
### A replayed commit returns no statement ids

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1106). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1109"></a>
### The user guide says a retry replays without a retry key

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1109). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1110"></a>
### The wire contract lags the code

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/ledger/changeset.py](../../../../iris_vector_graph/ledger/changeset.py), [specs/213-graph-revision-ledger/contracts/changeset.schema.json](../../../../specs/213-graph-revision-ledger/contracts/changeset.schema.json), [tests/unit/test_ledger_changeset.py](../../../../tests/unit/test_ledger_changeset.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1110). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1111"></a>
### The metrics hook is not called for refusals made in Python

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

Source/test check: [docs/ledger-prometheus-hook.md](../../../../docs/ledger-prometheus-hook.md), [iris_vector_graph/ledger/client.py](../../../../iris_vector_graph/ledger/client.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1111). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1112"></a>
### Two e2e fixtures read a meta key that does not exist and disable the ledger after them

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [tests/e2e/test_460_r281_ledger_post_commit_graph_e2e.py](../../../../tests/e2e/test_460_r281_ledger_post_commit_graph_e2e.py), [tests/e2e/test_460_r290_ledger_node_ops_graph_e2e.py](../../../../tests/e2e/test_460_r290_ledger_node_ops_graph_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1112). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1113"></a>
### The history source filter matches stored JSON text, not a source string

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1113`

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_vector_graph/ledger/replay.py](../../../../iris_vector_graph/ledger/replay.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1113). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1301"></a>
### Spec 256 FR-004 ('every record') contradicts Decision 2 ('any record') on clearing revision free text

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/13.json](../../../../experiment/playbook-completion/findings/audit/13.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [specs/256-ledger-tenant-redaction/spec.md](../../../../specs/256-ledger-tenant-redaction/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1301). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1501"></a>
### PROV export raises on a failed window read; its docstring and SEMANTIC_LAYER say it logs and writes an empty file

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c15-live-rdf`

Source/test check: [docs/API_REFERENCE.md](../../../../docs/API_REFERENCE.md), [docs/SEMANTIC_LAYER.md](../../../../docs/SEMANTIC_LAYER.md), [iris_vector_graph/_engine/prov.py](../../../../iris_vector_graph/_engine/prov.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1501). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1504"></a>
### map_sql_table looks up an unqualified table in schema 'USER' instead of the default schema SQLUser

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/fhir.py](../../../../iris_vector_graph/_engine/fhir.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1504). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1505"></a>
### FHIRSearchTool says it handles pagination; the condition search reads one Bundle page

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/fhir_bridge.py](../../../../iris_vector_graph/fhir_bridge.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1505). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1506"></a>
### With rdflib lacking ConjunctiveGraph (rdflib 8 per KNOWN_ISSUES), export and SHACL report 'rdflib is required'

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [docs/KNOWN_ISSUES.md](../../../../docs/KNOWN_ISSUES.md), [iris_vector_graph/_engine/_rdf_utils.py](../../../../iris_vector_graph/_engine/_rdf_utils.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1506). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1509"></a>
### The old clinical pipeline reports a failed rank walk as 'no graph connectivity'

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/fhir_bridge.py](../../../../iris_vector_graph/fhir_bridge.py), [tests/unit/test_231_fhir_bridge_fixes.py](../../../../tests/unit/test_231_fhir_bridge_fixes.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1509). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1510"></a>
### RDF export claims bounded memory but builds the whole graph in memory

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c15-live-memory`

Source/test check: [iris_vector_graph/_engine/_rdf_utils.py](../../../../iris_vector_graph/_engine/_rdf_utils.py), [iris_vector_graph/_engine/rdf_export.py](../../../../iris_vector_graph/_engine/rdf_export.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1510). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1511"></a>
### A register that fails after its upsert keeps the new settings

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-model`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: none (reproduced-model)

Source/test check: [iris_src/src/Graph/KG/FHIRGraph.cls](../../../../iris_src/src/Graph/KG/FHIRGraph.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1511). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1605"></a>
### The sample API's nodes field names Graph_KG instead of the engine's schema

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [api/gql/core/resolvers.py](../../../../api/gql/core/resolvers.py), [api/gql/loaders.py](../../../../api/gql/loaders.py), [iris_vector_graph/_engine/class_deploy.py](../../../../iris_vector_graph/_engine/class_deploy.py), [iris_vector_graph/gql/engine.py](../../../../iris_vector_graph/gql/engine.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1605). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1606"></a>
### The sample API's Cypher route accepts a timeout and a cache flag and uses neither

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

Source/test check: [api/models/cypher.py](../../../../api/models/cypher.py), [api/routers/cypher.py](../../../../api/routers/cypher.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1606). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1611"></a>
### The generated GraphQL server's health route always says healthy

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

Source/test check: [api/main.py](../../../../api/main.py), [iris_vector_graph/gql/__init__.py](../../../../iris_vector_graph/gql/__init__.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1611). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1613"></a>
### The MCP vector lookup treats the client's text as a node id

Disposition: **environment-blocked**. Reproduction level: not reproduced in this audit.

Community lacks the %AI tool classes used by the public MCP caller. The source binding does not execute that application/provider gate.

Existing source disposition: `blocked-access`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: none (blocked-access)

Source/test check: [iris_src/src/Graph/KG/MCPTools.cls](../../../../iris_src/src/Graph/KG/MCPTools.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1613). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1702"></a>
### A caller transaction cannot be opened through an in-IRIS cursor

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py), [iris_vector_graph/embedded.py](../../../../iris_vector_graph/embedded.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1702). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1703"></a>
### IVG_STRICT_NAMESPACE warns; two documents say it raises

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`, `rx-live-17`

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_vector_graph/exceptions.py](../../../../iris_vector_graph/exceptions.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1703). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1704"></a>
### The error root does not catch every IVG error

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/errors.py](../../../../iris_vector_graph/errors.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1704). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1705"></a>
### vector_similarity_search ranks L2 results farthest first

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/dbapi_utils.py](../../../../iris_vector_graph/dbapi_utils.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1705). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1706"></a>
### create_hnsw_index does not try ACORN first

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-vec`

Source/test check: [iris_vector_graph/dbapi_utils.py](../../../../iris_vector_graph/dbapi_utils.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1706). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1707"></a>
### SHOW CONSTRAINTS and the index lists name keys the schema does not have

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`

Source/test check: [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1707). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1708"></a>
### The bolt-on installer does not do what deploy/README.md says

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/cli.py](../../../../iris_vector_graph/cli.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1708). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1710"></a>
### The docker deploy recipe cannot build or log in as written

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: none (confirmed-source)

[Exact starting entry](start/bugs_issues.md#F-1710). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1711"></a>
### The deploy guide's SDK example reads a field IVGResult does not have

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/result.py](../../../../iris_vector_graph/result.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1711). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1713"></a>
### STATUS_PARTS omits two parts that status() marks unknown

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: none (reproduced-test)

[Exact starting entry](start/bugs_issues.md#F-1713). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1714"></a>
### Two IVGClient calls and the async client do not map 401/403

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-server`, `rx-live-17`

Source/test check: [iris_vector_graph/sdk.py](../../../../iris_vector_graph/sdk.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1714). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1807"></a>
### The HTTP snapshot endpoint can write two snapshots to one path

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/18.json](../../../../experiment/playbook-completion/findings/audit/18.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-http-endpoint`

Source/test check: [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1807). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0090"></a>
### Four unit tests never run: each is shadowed by a later method of the same name in its test class (lint warning F811)

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-product-gates.json](../../../../experiment/playbook-completion/findings/audit/zz-product-gates.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py), [tests/unit/test_coverage_boost.py](../../../../tests/unit/test_coverage_boost.py), [tests/unit/test_engine_deep.py](../../../../tests/unit/test_engine_deep.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0090). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0301"></a>
### create_edge's adoption of a marked row runs after its transaction commits

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0301). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0302"></a>
### Property lookups with a limit return a storage-order subset

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/03.json](../../../../experiment/playbook-completion/findings/audit/03.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0302). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0347"></a>
### A caller transaction with more than about 1,000 row writes to a table escalates to a table lock; every other process's write to that table, in any graph, then waits 10 s and fails with SQLCODE -110

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `intent-undecided`; [experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json](../../../../experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json).

Previous reproduction record: none (intent-undecided)

Source/test check: [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0347). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0351"></a>
### Explicit edge writers store the temporal marker {"temporal": true} given as a caller qualifier: the row is a marked row with no timestamp, and verify() does not see the relationship

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-writesets.json](../../../../experiment/playbook-completion/findings/audit/zz-writesets.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-ba-marker-qualifier`

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md](../../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md), [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/ledger/errors.py](../../../../iris_vector_graph/ledger/errors.py), [iris_vector_graph/ledger/replay.py](../../../../iris_vector_graph/ledger/replay.py), [specs/213-graph-revision-ledger/contracts/ledger-api.md](../../../../specs/213-graph-revision-ledger/contracts/ledger-api.md), [specs/254-temporal-purge-collisions-rebuild/tasks.md](../../../../specs/254-temporal-purge-collisions-rebuild/tasks.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0351). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0401"></a>
### A writer stopped between its adjacency write and its generation step lets a reader cache a count that includes the undone edge

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-model`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: none (reproduced-model)

Source/test check: [iris_src/src/Graph/KG/Adj.cls](../../../../iris_src/src/Graph/KG/Adj.cls), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0401). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0402"></a>
### Two adjacency rebuilds can run at once

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `intent-undecided`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: none (intent-undecided)

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0402). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0415"></a>
### A refused erase or adjacency rebuild (writer lock not granted) still leaves writes behind: the graph's no-lock mark, source generations and ^KG("__version")

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-refusals.json](../../../../experiment/playbook-completion/findings/audit/zz-refusals.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-live-04`

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_src/src/Graph/KG/TraversalBuild.cls](../../../../iris_src/src/Graph/KG/TraversalBuild.cls), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0415). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0440"></a>
### ^KG("prop") has no owning module, and four modules write it

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/GraphStores.cls](../../../../iris_src/src/Graph/KG/GraphStores.cls), [iris_src/src/Graph/KG/TraversalBuild.cls](../../../../iris_src/src/Graph/KG/TraversalBuild.cls), [iris_vector_graph/migrations/kg_node_stores.py](../../../../iris_vector_graph/migrations/kg_node_stores.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0440). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0502"></a>
### With temporal_structural_rows=True, create_edge_temporal raises 'Cursor closed' and writes no marked row under the driver the pin's uv.lock installs

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/zz-validation.json](../../../../experiment/playbook-completion/findings/audit/zz-validation.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [iris_vector_graph/_engine/temporal.py](../../../../iris_vector_graph/_engine/temporal.py), [tests/e2e/test_temporal_structural_row_live.py](../../../../tests/e2e/test_temporal_structural_row_live.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0502). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0601"></a>
### A node re-enqueued while a worker holds its old text is marked DONE with the old vector

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-model`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (reproduced-model)

Source/test check: [iris_src/src/Graph/KG/EmbedQueue.cls](../../../../iris_src/src/Graph/KG/EmbedQueue.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0601). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0603"></a>
### kg_KNN_VEC's route guard picks an arbitrary registry row where Python applies a fixed preference

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/GraphStores.cls](../../../../iris_src/src/Graph/KG/GraphStores.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0603). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0604"></a>
### The 4.0.0 vector migration takes an undeclared legacy table's width from an arbitrary row

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/migrations/graph_scoped_embeddings.py](../../../../iris_vector_graph/migrations/graph_scoped_embeddings.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0604). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0605"></a>
### The embed queue serves PENDING entries in node-id order, so an entry can wait indefinitely

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/06.json](../../../../experiment/playbook-completion/findings/audit/06.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/EmbedQueue.cls](../../../../iris_src/src/Graph/KG/EmbedQueue.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0605). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0606"></a>
### The graph-scoped vector search exceeds spec 227 SC-010's 1.1x latency budget in every run

Disposition: **inconclusive performance envelope**. Reproduction level: not reproduced in this audit.

The old finite latency panel is retained. No repeated comparable native performance experiment on this audit host establishes the declared 1.1x budget across the required envelope.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/zz-validation.json](../../../../experiment/playbook-completion/findings/audit/zz-validation.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [tests/perf/test_227_single_graph_latency.py](../../../../tests/perf/test_227_single_graph_latency.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0606). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0615"></a>
### VectorOptimizer.migrate_to_optimized cannot run on IRIS 2026.1: its CREATE INDEX IF NOT EXISTS ... AS HNSW is rejected, so it copies nothing and answers success False

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-refusals.json](../../../../experiment/playbook-completion/findings/audit/zz-refusals.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-live-06`

Source/test check: [iris_vector_graph/vector_utils.py](../../../../iris_vector_graph/vector_utils.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0615). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0640"></a>
### Dropping a neighborhood_vector index handle kills ^NKG("q") in the interned snapshot

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [iris_vector_graph/index_protocol.py](../../../../iris_vector_graph/index_protocol.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0640). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0642"></a>
### Vector top-k searches cut equal scores in storage order

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-perm-b`

Source/test check: [docs/API_REFERENCE.md](../../../../docs/API_REFERENCE.md), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [iris_vector_graph/dbapi_utils.py](../../../../iris_vector_graph/dbapi_utils.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0642). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0670"></a>
### Two embed-queue workers can work the same entry at once: the single-consumer premise is neither enforced nor documented

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-semantics.json](../../../../experiment/playbook-completion/findings/audit/zz-semantics.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `intent-a-hd0604-queue-claim`

Source/test check: [docs/API_REFERENCE.md](../../../../docs/API_REFERENCE.md), [iris_src/src/Graph/KG/EmbedQueue.cls](../../../../iris_src/src/Graph/KG/EmbedQueue.cls), [iris_vector_graph/_engine/embeddings.py](../../../../iris_vector_graph/_engine/embeddings.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0670). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0690"></a>
### VectorOptimizer, a public class, hard-codes the Graph_KG schema, so in a namespace whose IVG Schema has another name it reads and writes the wrong tables

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-product-gates.json](../../../../experiment/playbook-completion/findings/audit/zz-product-gates.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/adr/0016-one-ivg-schema-per-namespace.md](../../../../docs/adr/0016-one-ivg-schema-per-namespace.md), [iris_vector_graph/__init__.py](../../../../iris_vector_graph/__init__.py), [iris_vector_graph/vector_utils.py](../../../../iris_vector_graph/vector_utils.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0690). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0703"></a>
### Text-search top-k answers and fused ranks depend on scan order

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/07.json](../../../../experiment/playbook-completion/findings/audit/07.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py), [iris_vector_graph/text_search.py](../../../../iris_vector_graph/text_search.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0703). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0716"></a>
### The engine's index registry mis-decodes BM25Index.List: an index name holding a comma or a leading/trailing space is split or trimmed, so the real index is missing and phantom names appear

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-refusals.json](../../../../experiment/playbook-completion/findings/audit/zz-refusals.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-07`

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [iris_vector_graph/_validate.py](../../../../iris_vector_graph/_validate.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0716). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0717"></a>
### BM25Index.Build and Info write the graph name into their JSON escaping only backslash and quote: a graph name with a control character makes bm25_build raise JSONDecodeError after the index was rebui…

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-refusals.json](../../../../experiment/playbook-completion/findings/audit/zz-refusals.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-07`

Source/test check: [iris_src/src/Graph/KG/BM25Index.cls](../../../../iris_src/src/Graph/KG/BM25Index.cls), [iris_src/src/Graph/KG/TraversalBFS.cls](../../../../iris_src/src/Graph/KG/TraversalBFS.cls), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [iris_vector_graph/_validate.py](../../../../iris_vector_graph/_validate.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0717). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0801"></a>
### A rolled-back Cypher edge write leaves the interned snapshot's counters raised

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-fc0801-rollback-nkg`, `b-08-live-footprints`, `b-08-live-fc0801-rollback-nkg-rerun`, `b-08-live-footprints-rerun`

Source/test check: [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0801). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0802"></a>
### Schema procedures report one sampled element's property keys, chosen by storage order

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/08.json](../../../../experiment/playbook-completion/findings/audit/08.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-storage-order`

Source/test check: [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0802). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0840"></a>
### A Cypher DELETE deletes vector rows and reification rows itself, and only from the legacy vector table

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/cypher/translator.py](../../../../iris_vector_graph/cypher/translator.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0840). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0940"></a>
### IVG.CypherEngine.Scalar answers the caller's default when the read fails, so a failed COUNT reads as 0

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/IVG/CypherEngine.cls](../../../../iris_src/src/IVG/CypherEngine.cls), [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0940). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0948"></a>
### Compiled native plan classes have no bound: one class per plan shape accumulates until a deploy

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/Cypher/Gen.cls](../../../../iris_src/src/Graph/KG/Cypher/Gen.cls), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0948). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1001"></a>
### triangle_count, a read, creates twelve SQL functions (DDL, class compile, commit) and rewrites the deploy record, with no Arno library

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

Source and recorded observations were checked. The exact listener lifetime, route/capability, DDL-effect or algorithm-quality assertion has no completed fresh discriminating regression here; mentioning Arno does not make the ordinary fallback unavailable. Historical evidence remains intact; correctness is not inferred.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/10.json](../../../../experiment/playbook-completion/findings/audit/10.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-fp`, `b-10-live-fp-detail`

Source/test check: [iris_vector_graph/routine_record.py](../../../../iris_vector_graph/routine_record.py), [iris_vector_graph/stores/arno_bridge.py](../../../../iris_vector_graph/stores/arno_bridge.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1001). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1002"></a>
### Leiden on Zachary's karate club gives ARI 0.072 on the non-Arno path, against the product's 0.75 threshold

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

Source and recorded observations were checked. The exact listener lifetime, route/capability, DDL-effect or algorithm-quality assertion has no completed fresh discriminating regression here; mentioning Arno does not make the ordinary fallback unavailable. Historical evidence remains intact; correctness is not inferred.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/zz-validation.json](../../../../experiment/playbook-completion/findings/audit/zz-validation.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [tests/e2e/test_communities_e2e.py](../../../../tests/e2e/test_communities_e2e.py), [tests/perf/test_leiden_four_way.py](../../../../tests/perf/test_leiden_four_way.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1002). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1040"></a>
### Graph.KG.ArnoAccel.BumpVersion moves the adjacency module's graph-version token

Disposition: **source observation outside active bugs**. Reproduction level: not reproduced in this audit.

This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [docs/adr/0011-the-adjacency-index-has-one-writer-module.md](../../../../docs/adr/0011-the-adjacency-index-has-one-writer-module.md), [iris_src/src/Graph/KG/ArnoAccel.cls](../../../../iris_src/src/Graph/KG/ArnoAccel.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1040). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1101"></a>
### The stats row can count a commit its caller rolled back

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/11.json](../../../../experiment/playbook-completion/findings/audit/11.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1102-txn`

Source/test check: [docs/ledger-prometheus-hook.md](../../../../docs/ledger-prometheus-hook.md), [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_src/src/Graph/KG/LedgerStats.cls](../../../../iris_src/src/Graph/KG/LedgerStats.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1101). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1102"></a>
### With SynchCommit=0 (the tested setting, IRIS default) an acknowledged ledger commit can be lost on an instance crash

Disposition: **inconclusive durability contract**. Reproduction level: not reproduced in this audit.

No instance-crash experiment is run. The recorded SynchCommit setting is a source/environment fact; promised acknowledged durability and failure recovery need an owner contract and relevant provider evidence.

Existing source disposition: `intent-undecided`; [experiment/playbook-completion/findings/audit/11-orchestrator.json](../../../../experiment/playbook-completion/findings/audit/11-orchestrator.json).

Previous reproduction record: none (intent-undecided)

[Exact starting entry](start/bugs_issues.md#F-C1102). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1106"></a>
### Relationships the wire schema admits are refused once s+p+o exceed an undocumented key-length limit

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/correspondence.json](../../../../experiment/playbook-completion/findings/audit/correspondence.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `corr-capacity`

Source/test check: [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py), [specs/213-graph-revision-ledger/contracts/changeset.schema.json](../../../../specs/213-graph-revision-ledger/contracts/changeset.schema.json). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1106). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1107"></a>
### The commit does not enforce the wire schema's length limits, and reports violations as a ledger inconsistency

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/correspondence.json](../../../../experiment/playbook-completion/findings/audit/correspondence.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `corr-capacity`

Source/test check: [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_vector_graph/ledger/errors.py](../../../../iris_vector_graph/ledger/errors.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1107). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1108"></a>
### A detach delete assigns statement ids to unrecorded incident edges in storage order

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `intent-undecided`; [experiment/playbook-completion/findings/audit/correspondence.json](../../../../experiment/playbook-completion/findings/audit/correspondence.json).

Previous reproduction record: none (intent-undecided)

Source/test check: [iris_src/src/Graph/KG/LedgerApply.cls](../../../../iris_src/src/Graph/KG/LedgerApply.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1108). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1109"></a>
### Every node_not_found refusal is decoded as a create_relationship failure with relationship-only advice

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/correspondence.json](../../../../experiment/playbook-completion/findings/audit/correspondence.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM)

Source/test check: [iris_vector_graph/ledger/errors.py](../../../../iris_vector_graph/ledger/errors.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1109). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1110"></a>
### After a BUILD INDEX, a duplicate-key insert raises <LIST ERROR>, which the duplicate check does not recognise

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-contract.json](../../../../experiment/playbook-completion/findings/audit/zz-contract.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1110). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1204"></a>
### EraseNodes fails on a prefix longer than the subscript limit instead of erasing nothing

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/correspondence.json](../../../../experiment/playbook-completion/findings/audit/correspondence.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `corr-capacity`

Source/test check: [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1204). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1501"></a>
### Schedule/Unschedule change the Task Manager task and the fhir_graphs task_id in separate, untransacted steps

Disposition: **inconclusive provider failure boundary**. Reproduction level: not reproduced in this audit.

Ordinary task ownership/persistence observations exist, but atomicity failure is still a conditional save/delete-versus-SQL provider contract; no actual cross-provider failure regression reproduced it.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/FHIRGraph.cls](../../../../iris_src/src/Graph/KG/FHIRGraph.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1501). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1502"></a>
### delete_node removes the reifier nodes of the node's edges in a second transaction

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/15.json](../../../../experiment/playbook-completion/findings/audit/15.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c15-live-reify`

Source/test check: [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1502). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1540"></a>
### The FHIR graph build writes the adjacency label index and the vector and document rows itself

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_src/src/Graph/KG/FHIRGraph.cls](../../../../iris_src/src/Graph/KG/FHIRGraph.cls), [iris_src/src/Graph/KG/LabelIndex.cls](../../../../iris_src/src/Graph/KG/LabelIndex.cls), [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1540). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1548"></a>
### Deleting a relationship with delete_edge or Cypher DELETE leaves its reification rows pointing at an edge that no longer exists

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-fk`

Source/test check: [iris_vector_graph/schema.py](../../../../iris_vector_graph/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1548). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1549"></a>
### A one-edge PROV lookup fails once the default graph's temporal history no longer fits one IRIS string

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-cap-batch-r2`, `st-live-cap-batch`

Source/test check: [iris_vector_graph/_engine/prov.py](../../../../iris_vector_graph/_engine/prov.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1549). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1602"></a>
### Server and connection failures are reported as client syntax errors

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [api/routers/cypher.py](../../../../api/routers/cypher.py), [iris_vector_graph/bolt_server.py](../../../../iris_vector_graph/bolt_server.py), [iris_vector_graph/cypher_api.py](../../../../iris_vector_graph/cypher_api.py), [iris_vector_graph/gql/resolvers.py](../../../../iris_vector_graph/gql/resolvers.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1602). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1640"></a>
### The stdio MCP server's LoadGraph always reports 0 nodes and 0 edges loaded

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-mcp-load`

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1640). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1641"></a>
### The generated GraphQL server's Node.properties always answers an empty list

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-gql-props`

Source/test check: [iris_vector_graph/gql/schema.py](../../../../iris_vector_graph/gql/schema.py), [tests/e2e/test_gql_node_queries.py](../../../../tests/e2e/test_gql_node_queries.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1641). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1642"></a>
### The generated GraphQL server pages nodes(label) over an unordered id list

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-so-confirm`, `st-live-perm-c`

Source/test check: [api/gql/core/resolvers.py](../../../../api/gql/core/resolvers.py), [iris_vector_graph/gql/resolvers.py](../../../../iris_vector_graph/gql/resolvers.py), [iris_vector_graph/gql/schema.py](../../../../iris_vector_graph/gql/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1642). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1701"></a>
### Two declared console scripts cannot run from an install

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM)

[Exact starting entry](start/bugs_issues.md#F-C1701). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1702"></a>
### `ivg server start --workers N` (N > 1) exits without serving

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-server-workers`

Source/test check: [docs/ADMIN_API.md](../../../../docs/ADMIN_API.md), [iris_vector_graph/cli.py](../../../../iris_vector_graph/cli.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1702). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1704"></a>
### The L2 metric of the vector helpers fails on IRIS Community 2026.1

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/17.json](../../../../experiment/playbook-completion/findings/audit/17.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-vec`

[Exact starting entry](start/bugs_issues.md#F-C1704). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1705"></a>
### The product's transaction premise 'measured on IRIS 2026.3 (driver 5.4.0)' is false on 2026.1 and 2026.2 with either driver: the driver is not its cause

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-versions.json](../../../../experiment/playbook-completion/findings/audit/zz-versions.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ver-e261-d532`, `ver-e261-d540`, `ver-e262-d532`, `ver-e262-d540`

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_src/src/Graph/KG/Txn.cls](../../../../iris_src/src/Graph/KG/Txn.cls), [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1705). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1706"></a>
### The pin's uv.lock installs intersystems-irispython 5.3.2, on which IVG answers scores as Decimal or text, raises on duplicate rows and refuses list parameters

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-test`; [experiment/playbook-completion/findings/audit/zz-validation.json](../../../../experiment/playbook-completion/findings/audit/zz-validation.json).

Previous reproduction record: none (reproduced-test)

Source/test check: [docs/dev/driver-drift.md](../../../../docs/dev/driver-drift.md), [iris_vector_graph/_write_txn.py](../../../../iris_vector_graph/_write_txn.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py), [tests/e2e/test_460_proc_yield_alias_e2e.py](../../../../tests/e2e/test_460_proc_yield_alias_e2e.py), [tests/e2e/test_460_r284_retrieve_rrf_score_e2e.py](../../../../tests/e2e/test_460_r284_retrieve_rrf_score_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1706). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1715"></a>
### On a namespace that refuses the engine, close does not run: IRISGraphEngine has no close() and its store's close() is refused

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-refusals.json](../../../../experiment/playbook-completion/findings/audit/zz-refusals.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-live-17`

Source/test check: [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py), [iris_vector_graph/schema_name.py](../../../../iris_vector_graph/schema_name.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1715). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1716"></a>
### kill_query cannot end any process on IRIS 2026.1: %SYSTEM.SYS.KillProcess is not an SQL function (SQLCODE -359), so every call answers False

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-refusals.json](../../../../experiment/playbook-completion/findings/audit/zz-refusals.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-live-17`

Source/test check: [docs/API_REFERENCE.md](../../../../docs/API_REFERENCE.md), [iris_vector_graph/_engine/admin.py](../../../../iris_vector_graph/_engine/admin.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1716). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1740"></a>
### The SQL adapter's node delete removes document and reification rows by its own SQL

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1740). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1742"></a>
### IRISGraphStore.query_nodes(limit=n) cuts an unordered node scan

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `confirmed-source`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none (confirmed-source)

Source/test check: [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1742). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1795"></a>
### When its dedicated Native API connection is refused (licence units exhausted), the engine silently uses the caller's connection and retries the refused connect on every native call

Disposition: **environment-blocked**. Reproduction level: not reproduced in this audit.

The cited provider/platform premise is absent from the audit runtime or not established by the saved test. A source/model result cannot substitute for that caller/provider gate.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json](../../../../experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `live-licence-world`

Source/test check: [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1795). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1848"></a>
### save_snapshot and restore_snapshot hold the whole archive in client memory: about 11 MB per 1,000 edges, 190 times the archive's size

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Existing source disposition: `reproduced-live`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-cap-snapshot-mem`

Source/test check: [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1848). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-103"></a>
### PPR native/store and Python fallback can retain different top-k nodes at a rounded zero tie

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: `root-ppr-tie-native.py`, actual ordinary graph writes and native RunJson/WithUnscored/public store route plus actual private Python fallback with real database reads on the hostname-guarded task-owned IRIS. Physical provider unavailability and the outer public-to-fallback dispatch were not reproduced; the two actual implementations and final selected rows were. No external service or security scenario.

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_src/src/Graph/KG/PageRank.cls](../../../../iris_src/src/Graph/KG/PageRank.cls), [iris_vector_graph/_collation.py](../../../../iris_vector_graph/_collation.py), [iris_vector_graph/_engine/algorithms.py](../../../../iris_vector_graph/_engine/algorithms.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-103). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-plt-105"></a>
### After a primary scoring failure, a seed vector search can return the seed it should exclude

Disposition: **inconclusive regression gap**. Reproduction level: not reproduced in this audit.

The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.

Previous reproduction record: the actual public kg_KNN_VEC and optimized fallback over the hostname-guarded task-owned IRIS, using the previously created width4 route, seed vector and peer. An in-process DBAPI adapter injects exactly one generic first-score exception; it supplies no score rows or expected result. Subsequent scoring is real native VECTOR_COSINE. Independent actual-source cases additionally exercise the embedded and DBAPI readers over a cosine/predicate provider. No organic outage, native class failure, data/metadata modification or product patch was observed or performed.

Source/test check: [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [tests/e2e/test_227_two_models.py](../../../../tests/e2e/test_227_two_models.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-plt-105). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-tmp-012"></a>
### Without the adjacency index, deleting a temporal edge removes the adjacency of an explicit edge on the same triple

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md](../../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [specs/254-temporal-purge-collisions-rebuild/spec.md](../../../../specs/254-temporal-purge-collisions-rebuild/spec.md), [tests/e2e/test_252_temporal_rows_e2e.py](../../../../tests/e2e/test_252_temporal_rows_e2e.py), [tests/e2e/test_254_purge_e2e.py](../../../../tests/e2e/test_254_purge_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-tmp-012). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-002"></a>
### The user guide says a repeated commit replays, which holds only with an idempotency key

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_vector_graph/ledger/errors.py](../../../../iris_vector_graph/ledger/errors.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-002). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-003"></a>
### Spec 256's text contradicts its own decisions and the shipped tombstone format

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0013-redaction-removes-content-from-history.md](../../../../docs/adr/0013-redaction-removes-content-from-history.md), [iris_src/src/Graph/KG/Ledger.cls](../../../../iris_src/src/Graph/KG/Ledger.cls), [iris_src/src/Graph/KG/LedgerRedact.cls](../../../../iris_src/src/Graph/KG/LedgerRedact.cls), [specs/256-ledger-tenant-redaction/spec.md](../../../../specs/256-ledger-tenant-redaction/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-003). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-004"></a>
### Several shipped specifications still say Draft or not adopted

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#bug-doc-004). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-005"></a>
### ADR-0016 still describes the IVG Schema design before it was built

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0016-one-ivg-schema-per-namespace.md](../../../../docs/adr/0016-one-ivg-schema-per-namespace.md), [specs/262-ivg-owned-sql-schema/spec.md](../../../../specs/262-ivg-owned-sql-schema/spec.md), [tests/e2e/test_262_alt_schema_paths.py](../../../../tests/e2e/test_262_alt_schema_paths.py), [tests/e2e/test_262_fresh_namespace.py](../../../../tests/e2e/test_262_fresh_namespace.py), [tests/e2e/test_262_inventory.py](../../../../tests/e2e/test_262_inventory.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-005). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-006"></a>
### ADR-0003 says control characters are stripped from named-graph keys, but the code refuses them

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0003-two-graph-key-derivations.md](../../../../docs/adr/0003-two-graph-key-derivations.md), [iris_src/src/Graph/KG/GraphKey.cls](../../../../iris_src/src/Graph/KG/GraphKey.cls), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/_engine/snapshot.py](../../../../iris_vector_graph/_engine/snapshot.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-006). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-007"></a>
### ADR-0004 says bulk_delete_adjacency was removed, but it is still shipped and documented

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0004-erasure-removes-content-not-history.md](../../../../docs/adr/0004-erasure-removes-content-not-history.md), [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_vector_graph/_engine/nodes_edges.py](../../../../iris_vector_graph/_engine/nodes_edges.py), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-007). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-008"></a>
### ADR-0012 does not mention the lockless-writer fallback that 4.7.0 added

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md](../../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md), [iris_src/src/Graph/KG/Adj.cls](../../../../iris_src/src/Graph/KG/Adj.cls), [iris_src/src/Graph/KG/Adjacency.cls](../../../../iris_src/src/Graph/KG/Adjacency.cls), [tests/e2e/test_degree_cache_live.py](../../../../tests/e2e/test_degree_cache_live.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-008). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-009"></a>
### Temporal documentation contradicts the code in several places

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0002-temporal-globals-are-not-directly-accessible.md](../../../../docs/adr/0002-temporal-globals-are-not-directly-accessible.md), [specs/239-alt-temporal-erase/spec.md](../../../../specs/239-alt-temporal-erase/spec.md), [tests/unit/test_temporal_single_owner.py](../../../../tests/unit/test_temporal_single_owner.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-009). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-010"></a>
### Search documents are not reconciled with graph-scoped routing or with the BM25 corpus

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [docs/migration/v4.0.0.md](../../../../docs/migration/v4.0.0.md), [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [tests/e2e/test_227_two_models.py](../../../../tests/e2e/test_227_two_models.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-010). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-011"></a>
### ADR-0005 forbids the three-argument TO_VECTOR for query vectors, which four call sites use

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [iris_vector_graph/_engine/schema.py](../../../../iris_vector_graph/_engine/schema.py), [iris_vector_graph/_engine/vector.py](../../../../iris_vector_graph/_engine/vector.py), [tests/e2e/test_227_two_models.py](../../../../tests/e2e/test_227_two_models.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-doc-012"></a>
### The glossary says structural edges are subject to the ledger, but Cypher writes are never recorded

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md), [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py), [iris_vector_graph/ledger/guard.py](../../../../iris_vector_graph/ledger/guard.py), [tests/integration/test_ledger_us05_compat.py](../../../../tests/integration/test_ledger_us05_compat.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-doc-012). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-cyp-009"></a>
### A build job queued before a layout change can leave a shape interpreted until the next change

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Previous reproduction record: none recorded

Source/test check: [docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md](../../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md), [iris_src/src/Graph/KG/Cypher/Exec.cls](../../../../iris_src/src/Graph/KG/Cypher/Exec.cls), [iris_src/src/Graph/KG/Cypher/Gen.cls](../../../../iris_src/src/Graph/KG/Cypher/Gen.cls), [specs/257-compiled-native-plans/spec.md](../../../../specs/257-compiled-native-plans/spec.md). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#bug-cyp-009). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-test-002"></a>
### The other unit, integration and cited end-to-end failures at the baseline come from this uplift's harness and environment, or are not root-caused

Disposition: **source observation outside active bugs**. Reproduction level: not reproduced in this audit.

This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#bug-test-002). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="bug-test-003"></a>
### Native probe runs on this arm have setup limits that bound what their verdicts show

Disposition: **source observation outside active bugs**. Reproduction level: not reproduced in this audit.

This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#bug-test-003). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-0904"></a>
### In sync mode a failed build runs in the reader's own process

Disposition: **refuted stronger effect on checked build**. Reproduction level: not reproduced in this audit.

The preserved Community 2026.1 sync-build failure still allowed three new SQL prepares and the reader answer. The stronger process-poisoning premise was not reproduced; compilation latency and the 2026.3 provider remain separate unresolved questions.

Existing source disposition: `not-reproduced`; [experiment/playbook-completion/findings/audit/09.json](../../../../experiment/playbook-completion/findings/audit/09.json).

Previous reproduction record: none recorded

Source/test check: [docs/ADMIN_GUIDE.md](../../../../docs/ADMIN_GUIDE.md), [iris_src/src/Graph/KG/Cypher/Gen.cls](../../../../iris_src/src/Graph/KG/Cypher/Gen.cls), [specs/257-compiled-native-plans/spec.md](../../../../specs/257-compiled-native-plans/spec.md), [tests/e2e/test_257_compiled_plans_e2e.py](../../../../tests/e2e/test_257_compiled_plans_e2e.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-0904). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1608"></a>
### The sample API lets two threads use its one IRIS connection at once

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Existing source disposition: `not-reproduced`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: none recorded

Source/test check: [api/main.py](../../../../api/main.py), [api/routers/cypher.py](../../../../api/routers/cypher.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1608). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-1612"></a>
### The REST dispatcher may read only the first chunk of a large request body

Disposition: **refuted premise; e2e environment-blocked**. Reproduction level: not reproduced in this audit.

The preserved real 50,000-character reads refute the 32,000-default-read premise on the tested CSP streams/build. The deployed REST/web-application gate was not exercised; no global end-to-end refutation is claimed.

Existing source disposition: `refuted`; [experiment/playbook-completion/findings/audit/16.json](../../../../experiment/playbook-completion/findings/audit/16.json).

Previous reproduction record: none recorded

Source/test check: [iris_src/src/Graph/KG/Service.cls](../../../../iris_src/src/Graph/KG/Service.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-1612). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0403"></a>
### Candidate: with the adjacency index declared, a failed rebuild could leave part of the adjacency missing

Disposition: **refuted tested failure consequence**. Reproduction level: not reproduced in this audit.

The preserved failed rebuild left all 400 source entries and verify_graph ok. This refutes that tested partial-index loss, while concurrent refill visibility and other failures remain inconclusive.

Existing source disposition: `not-reproduced`; [experiment/playbook-completion/findings/audit/04.json](../../../../experiment/playbook-completion/findings/audit/04.json).

Previous reproduction record: none recorded

Source/test check: [iris_src/src/Graph/KG/TraversalBuild.cls](../../../../iris_src/src/Graph/KG/TraversalBuild.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C0403). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1240"></a>
### EraseAll kills ^ArnoKG, a store the erase plan (GraphStores.Inventory) does not list

Disposition: **source observation outside active bugs**. Reproduction level: not reproduced in this audit.

This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.

Existing source disposition: `refuted`; [experiment/playbook-completion/findings/audit/zz-structural.json](../../../../experiment/playbook-completion/findings/audit/zz-structural.json).

Previous reproduction record: none recorded

Source/test check: [iris_src/src/Graph/KG/Eraser.cls](../../../../iris_src/src/Graph/KG/Eraser.cls), [iris_src/src/Graph/KG/GraphStores.cls](../../../../iris_src/src/Graph/KG/GraphStores.cls). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1240). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1720"></a>
### IRISGraphStore.query_nodes(limit=n) without a label filter kills the calling Python process (SIGSEGV) on the pin's locked driver 5.3.2: it sends FETCH FIRST n ROWS ONLY, which the product's own FETCH…

Disposition: **historical observation outside active bugs**. Reproduction level: not reproduced in this audit.

This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.

Existing source disposition: `duplicate`; [experiment/playbook-completion/findings/audit/zz-contract-2.json](../../../../experiment/playbook-completion/findings/audit/zz-contract-2.json).

Previous reproduction record: none recorded

Source/test check: [iris_vector_graph/_engine/query.py](../../../../iris_vector_graph/_engine/query.py), [iris_vector_graph/engine.py](../../../../iris_vector_graph/engine.py), [iris_vector_graph/stores/iris_sql_store.py](../../../../iris_vector_graph/stores/iris_sql_store.py). Full indexed file/commit identities are in source-review.json and source-catalog.json.

[Exact starting entry](start/bugs_issues.md#F-C1720). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0811"></a>
### Unfiled candidate F-C0811

Disposition: **stopped candidate unassessed**. Reproduction level: outside review scope.

This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#F-C0811). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1711"></a>
### Unfiled candidate F-C1711

Disposition: **stopped candidate unassessed**. Reproduction level: outside review scope.

This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#F-C1711). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0111"></a>
### Unfiled candidate F-C0111

Disposition: **stopped candidate unassessed**. Reproduction level: outside review scope.

This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#F-C0111). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0511"></a>
### Unfiled candidate F-C0511

Disposition: **stopped candidate unassessed**. Reproduction level: outside review scope.

This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#F-C0511). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0512"></a>
### Unfiled candidate F-C0512

Disposition: **stopped candidate unassessed**. Reproduction level: outside review scope.

This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#F-C0512). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C0513"></a>
### Unfiled candidate F-C0513

Disposition: **stopped candidate unassessed**. Reproduction level: outside review scope.

This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#F-C0513). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.

<a id="F-C1011"></a>
### Unfiled candidate F-C1011

Disposition: **stopped candidate unassessed**. Reproduction level: outside review scope.

This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.

Previous reproduction record: none recorded

[Exact starting entry](start/bugs_issues.md#F-C1011). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.
