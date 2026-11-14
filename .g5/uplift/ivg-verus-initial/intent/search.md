# Intent recovery: embeddings and search (worker A-search)

Pin: product baseline `3eaa79cf` (v4.7.0 + checklist commit). `git diff 3eaa79cf HEAD` touches no product, docs, specs or tests path, so every citation below is valid at the pin. Read-only inspection only; nothing was run.

Tags: **(H)** human requirement or answered question, **(D)** accepted design decision (ADR, spec Clarifications/Decisions, release note recording a decision), **(O)** observed implementation only, **(P)** proposed improvement. "SUSPECTED" means the source text alone does not prove the defect; a live run is needed.

## Scope and sources inspected

| Locator | Revision / date | Authority | Inspected portion | Follow-up |
|---|---|---|---|---|
| `docs/adr/0005-vector-width-is-not-declared-in-to-vector.md` | `18dfe745`, 2026-09-19 | D (Accepted) | whole | 3-arg `TO_VECTOR` still used for query vectors (F12) |
| `docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md` | `18dfe745`, 2026-09-19 | D (Accepted) | whole | Partly superseded by 4.0.0 routing; ADR has no "Later" note |
| `docs/adr/0007-bm25-df-and-doc-record-schema-2.md` | `bb98725f`, 2026-10-08 | D | whole | "every write under a lock" vs `Build` (F2) |
| `docs/adr/0004-erasure-removes-content-not-history.md` | 2026-09-14 | D (Accepted) | whole | Its "every store" clause vs `^BM25Idx`/`^IVF` (F1) |
| `specs/044-bm25-index/spec.md` (+ `data-model.md`, `tasks.md` headers) | `bb98725f` 2026-10-08, `231eb76b` 2026-10-09 | D (Clarifications 2026-10-08/09). H only secondhand: the opsreview request, external file not in repo | FR table, Edge Cases, both Clarification sessions | Status still "Draft". FR-012 is not implemented (Q3) |
| Specs 226 / 227 / 230 | **absent from the repo at every commit** (`git log --all -- '*226-*' '*227-*'` finds nothing) | — | FR numbers known only from code comments and CHANGELOG | Comments quoting FR-xxx are agent-written and secondhand |
| `CHANGELOG.md` v3.2.0 (l.4371ff), v4.0.0 (l.4046ff), v4.2.0 BM25 (l.3296, 3374-3400), 4.7.0 | 2026-09-19 … 2026-11-12 | D (release notes) | embedding, routing, quarantine and BM25 blocks | — |
| `docs/KNOWN_ISSUES.md` l.172-181 (`kg_RRF_FUSE` answers `[]`), l.702-714 (SQL vector procs), l.810-824 | `3653ce88`, 2026-11-12 | O + operator guidance | listed entries | Confirmed in code (C5) |
| `docs/migration/v4.0.0.md` l.300-390, 525-600, 742-751 | 2026-09-22+ | D/guide | quarantine, docs, edge vectors, "remaining gap" | l.750 and l.588-597 contradict code (F1, F10) |
| `CONTEXT.md` l.140-165 (glossary) | 2026-10-08+ | glossary (agent-written) | BM25, Index Schema, Embedding Registry, Quarantine | "refused rather than mixed in" overstated (Q1) |
| `iris_src/src/Graph/KG/BM25Index.cls` | `b300134f` 2026-11-08 | O | whole (635 lines) | — |
| `iris_src/src/Graph/KG/Eraser.cls` | `aad50087` | O | l.1-313, 690-845, grep for vector/BM25 terms | EraseNodeIds is only partly read |
| `iris_src/src/Graph/KG/GraphStores.cls` | — | O (claims to be the single inventory) | l.1-200 | — |
| `iris_src/src/Graph/KG/EmbedQueue.cls`, `EmbedQueueTask.cls` | `8431f034` | O | ClaimPendingBatch, RouteTable, RouteDtype, ProcessBatch; Task whole | — |
| `iris_src/src/Graph/KG/IVFIndex.cls`, `VecIndex.cls`, `PLAIDSearch.cls` | — | O | headers and method list only | not traced in depth |
| `iris_vector_graph/embedding_identity.py` | `18dfe745`+ | O (docstrings cite FR-004/7/8/10/14) | whole | — |
| `iris_vector_graph/_engine/embeddings.py` | `0cf1524f` 2026-11-10 | O | l.1-1290, 1803-2076 | `embed_nodes`/`embed_edges` only skimmed |
| `iris_vector_graph/_engine/schema.py` | `70fb921c` | O | registry/quarantine DDL l.140-230; identity l.987-1530; reconcile l.1688; quarantine l.1911-2095; setup l.2535-2575 | — |
| `iris_vector_graph/_engine/vector.py` | `0eb099d2` | O | l.84-226, 333-620, 917-1054 (grep), 1382-1452, 1749-1879 | `vector_search`, `kg_VECTOR_GRAPH_SEARCH` not traced |
| `iris_vector_graph/fusion.py`, `operators.py` l.30-45, `text_search.py`, `embed_selector.py` | — | O | fusion/text_search whole; embed_selector head | — |
| `iris_vector_graph/schema.py` l.2440-2560 (generated `kg_KNN_VEC`, `kg_TXT`, `kg_RRF_FUSE`) | — | O | listed | — |
| `iris_vector_graph/cypher/translator.py` l.317-323, 3125-3360 | — | O | `ivg.bm25.search`, `ivg.retrieve` | — |
| `iris_vector_graph/migrations/graph_scoped_embeddings.py`, `docs_and_edge_vectors.py`, `statements.py` l.200-215 | — | O | module docstrings, `_plan`, `_fate`, `_drain`, `_redistribute`, `_rewrite_registry`, `place_edge_vectors` | `rekey` not read |
| Tests: `tests/integration/test_embedding_registry_e2e.py`, `test_044_bm25_incremental.py`, `test_044_bm25_max_df.py`, `tests/e2e/test_230_retrieval_scope.py` l.505-650, `test_460_embed_queue_worker_routes_e2e.py` header; unit test names for 227/230/rrf | — | evidence | names, fixtures and selected bodies | none run |

## Capabilities

### C1. Embedding identity: who owns model identity and width

**Governing statements**
- (D) The recorded model identity and width live in `Graph_KG.embedding_registry`, not in the ledger. The rule is that "an embedding write must be refusable before it happens, on every installation, including … one that has no history feature enabled" (ADR-0006 l.13-16). The ledger is disqualified because it is opt-in, embedding writes bypass it, it is namespace-wide and it is a history (ADR-0006 l.18-42). CHANGELOG v3.2.0 l.4373: "a write that disagrees is refused instead of stored".
- (D) Width is enforced at the column declaration (IRIS `SQLCODE -104` at INSERT) and against the registry. It is never enforced by reshaping the query vector (ADR-0005 l.21-23, l.69-71).
- (D, v4.0.0) An embedding is a per-`(graph_id, model_key)` resource. Each pair has its own routed table `kg_emb_<sha256-16>` (edge pairs: `kg_eemb_`), created by the first write at the vector's width and registered by a `(table_name, graph_id)` row. "Never derive a name to find a route", and a pair with no route reads nothing (CHANGELOG l.4161-4184). This **supersedes** ADR-0006's "`graph_id` reserved … nothing may read it otherwise" (ADR-0006 l.65-68). ADR-0006 was never amended.
- (O) The column is the authority on width: `reconcile_recorded_dimensions` copies each legacy column's declared width into the registry on every `initialize_schema` (`_engine/schema.py:1688-1710`). A reused orphan routed table whose width differs is refused (`_engine/embeddings.py:589-641`). The registry is the authority on model. Comparison rules are a 2×2 over recorded/offered known/unknown, with width and dtype enforced in all four cells (`embedding_identity.py:180-241`). Normalization is strip + casefold + whitespace collapse, with no JSON canonicalization (l.42-72).
- (O, cites FR-010) An "offered unknown" writer (no `embedding_config`, no embedder) is never model-compared, only width-compared (`embedding_identity.py:85-91`).

**Operations**
- Entry: `store_embedding` (`_engine/embeddings.py:942`), `store_embeddings` (:1028), `store_edge_embedding(s)` (:1117, :1207), `embed_nodes`/`embed_edges` (:1291, :1502), `enqueue_for_embedding` (:1803), `process_embed_queue` (:1898), `set_embedding_identity` (`_engine/schema.py:1086`), `initialize_schema` → `adopt_embedding_identities` (:1256, called :2543) and `_record_configured_embedding_identity` (:1485, called :2568).
- Guards, in order for a node write: `_assert_node_exists` (:967). Then `_route_for_write` (:973 → :755): `_read_route` (:377) reads the registry for `(graph, model_key, kind)`, raises on any error except SQLCODE -30 (4.6.0 R161), and is cached for 30 s per engine (:313). Then `enforce_embedding_identity` (:981 → `schema.py:1354-1396`). Then the length check against `_route_width` (:794).
- Writers: scoped `DELETE` + `INSERT … TO_VECTOR(…)` inside `write_txn` (:1005-1024), nested in a caller transaction when one exists (`_write_txn.py` docstring). Route creation `_create_route` (:470-558) runs `CREATE TABLE`, an attempted ANN index and the registry INSERT, then `conn.commit()` (:537). It is refused inside a caller transaction (:494). A per-process `threading.Lock` per route key (:98-104) serializes creators. Across processes the registry PK `(table_name, graph_id)` (`schema.py:143-160`) arbitrates, and the loser re-reads (:520-531). The claim of an adopted (unknown) row is a conditional `UPDATE … WHERE model_key IS NULL` followed by a re-read (`schema.py:1177-1209`).
- Readers: `kg_KNN_VEC` (`vector.py:504`) via `_route_for_read` (`embeddings.py:652-679`); `_knn_routes` (:693); the generated SQL `kg_KNN_VEC` reads `kg_NodeEmbeddings` only, and its `kg_VEC_ROUTE_GUARD` raises for a routed named graph (`schema.py:2469-2481`, KNOWN_ISSUES l.702).

**Outcome-changing cases**
- *Ledger disabled.* Nothing in `_engine/embeddings.py` mentions the ledger (grep), so enforcement is ledger-independent. Confirmed.
- *Different model, same graph.* The pair resolves to a different route (or a new one is created), so the write **succeeds into a separate table**. It is not refused. Refusal remains for: width or dtype mismatch on the same pair; mechanism mismatch for the same key (`embedding_identity.py:214-219`); `set_embedding_identity` against another declared model (`schema.py:1211-1215`); and `initialize_schema` by an engine whose `embedding_config` differs from the model claimed on `kg_NodeEmbeddings` (`schema.py:1512` raises through setup).
- *Undeclared writer, default graph.* `(graph '', model None)` is the "default pair" (`embeddings.py:743-753`). It writes to `kg_NodeEmbeddings` even when that table's row is claimed by model A, because `_read_route` finds no `model_key IS NULL` row, so `_is_default_pair` falls back to legacy (:779). Enforcement compares width only. Vectors of unknown provenance therefore mix into A's table. *Undeclared writer, named graph g* gets its own route `kg_emb_hash(g,"")`. The two cases are asymmetric (Q1).
- *Adopted (unknown) row and a declared writer.* `conflicts` returns None (claim allowed), but `enforce_embedding_identity` does **not** claim. Only `set_embedding_identity` / setup claims (O).
- *Registry unreadable.* `_read_route` raises. However, `get_embedding_identity` swallows **every** exception and returns None ("nothing recorded"), so `enforce_embedding_identity` passes (`schema.py:1054-1056`, :1383-1385). That is fail-open whenever the route came from the cache (F11).
- *Check-then-write.* The registry read and the vector INSERT are not in one transaction or lock. A concurrent `set_embedding_identity(force=True)` can interleave (O). The claim is atomic. Enforcement plus write is not.
- *Queue.* `enqueue_for_embedding` checks the entry's config against `kg_NodeEmbeddings`@'' for **every** graph (:1838-1842). The Python worker deliberately does not (`_assert_entry_is_this_workers_work`, :1987-2016, whose docstring calls the kg_NodeEmbeddings check the 3.2.0 mistake). The IRIS worker `EmbedQueue.ProcessBatch` writes default-graph entries into `kg_NodeEmbeddings` whatever the entry's config, with no registry identity check. Named-graph entries go to `RouteTable(graph, config)` (`EmbedQueue.cls:278-283, 316`). See F8.

**Tests**
- Live: `tests/integration/test_embedding_registry_e2e.py` (skipif `SKIP_IRIS_TESTS`) covers shape, PK, set/get cases, adoption, claim-over-adopted, wrong-width refusal, and concurrent claim of an adopted row (l.608).
- Live: `test_embedding_identity_refusal_e2e.py`, `test_embed_queue_identity_e2e.py`, `test_to_vector_width_regression_e2e.py` (-257 pin), `tests/e2e/test_227_two_models.py`.
- Mocked: `tests/unit/test_227_*` over `route_fakes_227.py`.
- Not found: two models across two graphs through the queue; undeclared writer into a claimed default table; route-then-claim ordering (F9).

**Seed check (index.md "Embeddings")** — *corrected.* "The registry owns the declared model identity and width" holds for model identity. For width, the column declaration is the authority and the registry mirrors it (`schema.py:1688`, `embeddings.py:589`). Since 4.0.0 the registry is also the **routing authority** for `(graph, model, kind) → table`. Most model disagreements are routed, not refused. "Checked on write even when the ledger is disabled": confirmed. However, the check (a) is fail-open on a registry read error, (b) is absent from the IRIS queue worker for the default graph, and (c) compares width only for undeclared writers.

### C2. Graph scoping of vectors and vector search

- (D, v4.0.0) `graph=None` means the default graph `''`, never every graph. Every scoped predicate COALESCEs both sides (`routing.py:81-100`; CHANGELOG l.4184-4190). A graph ID is collision avoidance, not an authorization boundary (FR-032 as quoted in docstrings).
- (O) Store and read are keyed `(graph_id, node_id)`. Edge vectors are keyed `(graph_id, s, p, o_id)`. An unrouted pair reads nothing, except the default pair, which falls back to the legacy table (`embeddings.py:652-679`). `kg_KNN_VEC` refuses a wrong-width literal before any SQL (`vector.py:455-502`) and scopes the seed lookup (:566-575).
- (O) The SQL procedure `kg_KNN_VEC` reads only `kg_NodeEmbeddings` and raises for a routed named graph (KNOWN_ISSUES l.702).
- (O) IVF: `^IVF(name,"cfg","table")` records the route table but no graph. The engine only knows an IVF index's graph in the process that built it (`vector.py:150-185`).
- (O) VecIndex and PLAID: no graph concept (headers), caller-managed IDs.
- (O) `TextSearchEngine.search_documents` (`text_search.py:31-66`) is unscoped, reads an unqualified `docs`, and uses `%FIND(text, ?)`, which the generated-SQL comment says resolves as a user function (`schema.py:2499-2502`). See F13.
- Cases: same node ID in two graphs; default graph spelled NULL vs `''`; a named graph with no route (reads `[]`); a seed node ID vs a literal; wrong width (raise, not `[]`); a label filter joined in-graph.
- Tests: `tests/e2e/test_230_retrieval_scope.py` (live) and `test_230_scope_isolation.py`, `test_230_embedding_width_isolation.py` (live); `tests/unit/test_230_*` mocked or source-text.

### C3. Quarantine of vectors the upgrade could not place

- (D, v4.0.0 CHANGELOG l.4199-4217; migration/v4.0.0.md l.303-350) Every pre-upgrade row is either placed in exactly one graph or quarantined with a reason. Reasons: `ambiguous_graph` (several graphs hold the node ID), `no_node`, `resolver_declined`. A row is never given the default graph to make it fit (FR-028). No search reads the quarantine. An operator places one row at a time with `place_quarantined(q_rowid, graph=, model_key=)`. It raises and leaves the row in place if there is no route, if width or dtype disagree, or if the node is absent in that graph. It never creates a route.
- (O) Migration: `_plan` / `_fate` (`graph_scoped_embeddings.py:829-920`) decides each row's fate. `_drain` (:922-972) moves chunks of 400 into staging or quarantine with `INSERT … SELECT`, committing one chunk per transaction. It resumes from `max(staging.node_id, quarantine.node_id for this source)`. `_redistribute` (:1048-1093) moves non-table-graph rows to their routes with `NOT EXISTS`, then `DELETE`s them, committing per chunk. `_rewrite_registry` (:1095-1111) renames the table's graph.
- (O) Operator placement `place_quarantined` (`schema.py:1972-2070`): it checks the row, the route (`resolve_route(create=False)`, cached up to 30 s), width, dtype and `node_exists`. Then it runs `INSERT … SELECT` before `DELETE` inside `write_txn`. A target that already holds `(graph, node)` violates UNIQUE and the row stays (O, not documented).
- (O) Documents and edge vectors have their own quarantines, `docs_quarantine` and `edge_vector_quarantine` (`docs_and_edge_vectors.py`). There is **no API** for these. Placement is hand SQL per the migration doc (l.536-547, 588-598).
- (O) Erasure never touches any quarantine. `EraseGraph` (`Eraser.cls:300-302`) and `EraseAll` (:754-757) call it "evidence, not content" (FR-039/FR-040).
- Cases: a killed pass resumed at the watermark; a resolver naming a graph that does not hold the node (declined); placement into a pair with no route (refused); two concurrent placements of one `q_rowid` into two different graphs (under IRIS's default read-uncommitted SQL, both INSERTs may succeed). SUSPECTED and low.
- Tests: `tests/unit/test_227_quarantine_api.py`, `test_227_migration_bookkeeping.py`, `test_227_migration_idempotence.py` (mocked fakes); `tests/e2e/test_227_migration.py`, `test_230_migration.py` (live).

### C4. BM25 index (schema 1 vs 2, upgrade, writes, search, cutoff)

**Governing statements**
- (H, secondhand) The opsreview cluster reported that one insert on a 337,861-document index cost seconds, and that a 99.9%-df term cost 0.9 s per query (spec 044 Clarifications 2026-10-08 l.299-301; 2026-10-09). The request file is external and was not available.
- (D) FR-015 to FR-024 and FR-044-C1 to C5 (spec 044 l.161-170, 2026-10-09 block):
  - Insert and Delete cost O(distinct tokens).
  - `df(term) = |tf(term,*)|` at every committed point (FR-016).
  - IDF is computed at query time from current df and N (FR-017).
  - `N`, `totalLen` and `vocab_size` stay consistent at every committed point (FR-018).
  - Insert takes an index-level lock and a transaction; Search takes no lock (FR-019).
  - Empty-token replace deletes (FR-020); Delete follows FR-015 to FR-019 (FR-021).
  - Writers on schema 1 raise, naming `Upgrade`, with no fallback (FR-022).
  - `Upgrade` is one pass, re-runnable, refuses writers, flips `schema` last, then removes `idf`; a Search never sees schema 2 early (FR-023).
- (D) ADR-0007: "does every write under an index-level lock in a transaction with plain `Set`". `$Increment` was rejected because it does not roll back.
- (D) The cutoff skips terms with `df/N > f` when f > 0. If all known terms are over the cutoff, the lowest-df term is kept (ties go to the first in query order). df=0 terms are neither skipped nor kept. `SearchReport` lists skipped terms alphabetically plus `fallback`. Schema 1 ignores the option. `kg_BM25` keeps three arguments.
- (D, spec 230 FR-009 via code) An index covers exactly one graph, `pGraph=""` means the default graph, and the graph is recorded in `cfg graph` (`BM25Index.cls:93-97, 165-168`).

**Operations (`iris_src/src/Graph/KG/BM25Index.cls`)**
- `Build` (:97-175): `Kill ^BM25Idx(name)` (:99) takes **no lock and no transaction**. It runs one SQL scan of `nodes ⟕ rdf_props` for the graph (:123-131), then `IndexDoc` per document writes tf, df+1, doc and len (:178-204). cfg `N`, `totalLen`, `k1`, `b`, `vocab_size` and `graph` follow, and `schema=2` is set last (:160-170).
- `Insert` (:442-493): `RequireWritable` (:385-394) passes when there is no N; it refuses on `upgrading` or schema<2. Tokenize runs outside the lock. `LockWrite` (:403-410) does `Lock +^BM25Idx(name,"lock"):timeout` (default 30 s, `cfg lock_timeout`). `RequireWritable` runs again under the lock. Then `TStart`, a new index's cfg is initialized with schema 2, `RemoveDoc` (:416-437) runs, the tf/df/vocab/doc/len/N/totalLen writes follow, and `TCommit` ends it. The Catch does `If $TLevel > 0 TRollback`, which rolls back **all levels** (:486-490).
- `Delete` (:496-514): same shape.
- `Upgrade` (:526-581): returns `missing` if there is no N. Returns `already` if schema≥2 and not `upgrading` (checked **before** the lock only). Otherwise it sets `upgrading=1` before the lock (:533), takes the lock (:535) and clears the flag on timeout. It then kills `df` and `doc` and walks tf, which rebuilds df and doc (:542-558), and recomputes N, totalLen and vocab from len and df (:559-568). `schema=2` is the flip (:570), followed by killing `idf` and `avgdl`. There is **no transaction**: resumability comes from the restart-clears-df/doc design.
- `SearchCore` (:236-374): reads `schema` once (:246). Schema 2 uses `avgdl = totalLen/N` and `idf = ln((N-df+.5)/(df+.5)+1)` from the current df (:299-302). Schema 1 uses the stored idf, with a mid-upgrade fallback to df once `schema` reads 2 (:303-311). The cutoff is :263-293. A repeated query term scores once per occurrence (documented `vector.py:1763`).
- `Drop` (:587-591) runs with no lock. `Info` (:597-615) reports `graph ""` for a pre-230 all-graphs index, indistinguishable from the default graph.
- Python wrappers: `vector.py:1749-1879`. `bm25_build` records `_index_registry[name]` and `_index_graph_scopes[name]`. `bm25_drop` removes neither.
- Readers: `bm25_search`; SQL `kg_BM25` → `SearchProc` (3-arg; `SqlProcs.cls:134`); Cypher `ivg.bm25.search` and `ivg.retrieve` (`translator.py:3145-3196, 3239-3360`); engine `kg_RRF_FUSE`.

**Outcome-changing cases**
- *Absent vs empty index.* No N means Search answers `[]` and Delete answers 0 without locking. The first Insert creates a schema-2 index.
- *Empty-token text.* Insert removes the document and returns 0. Build skips such a document (N excludes it).
- *Schema 1.* Search works; the cutoff is ignored; Insert and Delete raise naming `Upgrade`; Build is **not** refused and replaces the index as schema 2.
- *Interrupted Upgrade.* Leaves `upgrading=1`, which refuses writers until `Upgrade` is re-run. The error says "being upgraded", not "re-run Upgrade" (:388-389).
- *Competing writers.* Insert and Delete are serialized by the lock. **Build does not take it** (F2). A second Upgrade waiting on the lock does not re-check `already` (F4).
- *Caller transaction open.* Inner `TCommit` only decrements, so the lock is released before the caller commits. An error inside rolls back the caller's work (F3).
- *Search concurrent with Insert.* Search takes no lock, so it reads globals mid-transaction. Its N, df and len may come from different moments (O; Q4).
- *Graph erase.* `^BM25Idx` is untouched (F1).

**Tests**
- Live, scratch namespace IVG236: `tests/integration/test_044_bm25_incremental.py`. Covers df equal to a brute-force count, replace, last-document removal, cost bounds, empty replace, schema-1 refusal, upgrade equal to a fresh build, interrupted upgrade, insert during upgrade, a concurrent search never seeing schema 2 early (:351), lock timeout for writer and upgrade, and rollback on failure (:521).
- Live: `test_044_bm25_max_df.py`, covering the cutoff semantics including the schema-1 ignore.
- Mocked wrappers: `tests/unit/test_bm25_max_df.py`, `test_044_bm25_upgrade_wrapper.py`.
- No test found for: Build concurrent with Insert; Insert inside a caller transaction; two concurrent Upgrades; erase vs `^BM25Idx`.

**Seed check (index.md "Text search")** — *confirmed with corrections.* Insert and Delete do update the token record, df, N, totalLen and vocab together under an index-level lock in a transaction (:456-491). Writes on schema 1 do require `Upgrade`. Schema-2 scoring uses current df.

Corrections:
- `Build` and `Drop` are writes outside the lock and transaction (ADR-0007 says "every write").
- `Upgrade` uses the lock and a flag but no transaction.
- "Current" df means as-read without isolation.
- Schema-1 scoring still uses the stored `idf`.

### C5. RRF fusion semantics, including empty inputs

There are four implementations with different semantics (O):

| Implementation | Text leg | Absent-from-leg contribution | Leg failure | Scope |
|---|---|---|---|---|
| `engine.kg_RRF_FUSE` (`vector.py:1382-1451`), also `IRISGraphOperators.kg_RRF_FUSE` (`operators.py:37`) | `^BM25Idx` index picked by `_fusion_leg_index` (:187-225) | `1/(c + len(leg) + c)`, **non-zero and dependent on leg length** (:1444-1446) | one `try` around both legs; logged at ERROR; a vector failure gives `[]` and the BM25 leg never runs (:1420-1436; KNOWN_ISSUES l.172) | graph-recorded index, then hnsw, then unknown-graph index with WARNING |
| SQL procedure `kg_RRF_FUSE` (`schema.py:2526-2560`) | `kg_TXT` (iFind over `docs`, term-count score), not BM25 | `1/(c + 1e9)` ≈ 0 | SQL error raises | `:graphId` on both legs, join on id and graph |
| Cypher `ivg.retrieve` (`translator.py:3239-3360`) | `kg_BM25(bm25_name, …)`, caller-named index | 0 (UNION ALL + SUM) | statement fails | requires `USE GRAPH` on a multi-graph namespace (:3258-3261); the vector arm is scoped; **the BM25 arm's index graph is not checked against USE GRAPH** |
| `RRFFusion.fuse_results` / `HybridSearchFusion` (`fusion.py:27-64, 109-252`) | `kg_TXT` | 0 | vector leg failure logged at WARNING and swallowed (:151-152); text leg re-raises (:164-170) | `graph` passed to each leg |

- (D) The engine docstring and API reference say "each hit scores `1 / (c + rank)` … a failed index search is logged at ERROR and the legs not yet searched contribute nothing" (`vector.py:1392-1397`; API_REFERENCE l.1000). `fusion.py:11` cites Cormack & Clarke. Neither documents a non-zero contribution for an absent item. The `len+c` rule dates from at least v1.91 (`b68280b4`), with no recorded decision.
- Cases:
  - *Both legs empty:* `[]` everywhere.
  - *Empty `query_text`:* the engine skips the BM25 leg (:1431).
  - *Operators default `query_vector="[]"` with a text query:* `kg_KNN_VEC` raises a width mismatch at `_assert_query_width` (:487-502), so the BM25 leg never runs and the answer is `[]`. This is the known issue's trigger with a default argument.
  - *No BM25 index for the graph:* the text leg is silently empty (:1432-1434).
  - *An index dropped or built by another process after the engine started:* `_index_registry` and `_index_graph_scopes` are not refreshed by `bm25_drop` or by other processes (`engine.py:367, 1885`; `vector.py:1868-1870`). See F6.
  - *Ties:* `fuse_results` sorts a dict built from a `set`, so tie order depends on hash seed. The engine and SQL break ties arbitrarily too.
- Tests: `tests/unit/test_rrf_fuse_e2e.py` (live, despite its directory; checks shape and top-1 only); `tests/unit/test_460_rrf_leg_prefers_graphs_own_index.py` (mocked index choice); `tests/unit/test_230_rrf_fuse_scope.py` (source text of the generated SQL); `tests/e2e/test_230_retrieval_scope.py` (live scope). No test pins the absent-rank formula.

### C6. Erasure vs vectors, BM25 and the registry

- (D) ADR-0004 l.10-12: the Eraser "removes graph content from every store that holds it … inside a single transaction". "Every deletion path funnels through the Eraser" (l.79-80). `GraphStores` is "the one declared inventory of stores holding graph content", and it also lists the unscoped stores so they are reported (`GraphStores.cls:1-16`).
- (O) `EraseGraph` (`Eraser.cls:46-313`), inside TSTART…TCOMMIT (:56, :258):
  - collects routes from the registry (`%STARTSWITH kg_emb_`/`kg_eemb_`, `IsRouteName`) plus orphans from the catalog (:82-113);
  - deletes `rdf_labels`, `rdf_props` and `docs` by graph (:133-147);
  - deletes `kg_NodeEmbeddings` and `_optimized` by graph (:153-159);
  - `DELETE`s each route table's rows for the graph (:167-180);
  - deletes `kg_EdgeEmbeddings` by graph (:198-200), then edges, nodes and globals.
  - After the commit it runs `DROP TABLE` for **claimed** routes, then deletes their registry row; a failed drop keeps the row (:283-299). Orphan routes are emptied but not dropped.
- (O) `EraseAll` (:707-845) empties every route, deletes the **whole** registry (:758-759), including legacy tables' identity rows, and keeps `embedding_quarantine` (:754-757).
- (O) `EraseNodeIds` / `EraseNodes` (:322-640) visit every routed table with a graph predicate and never drop (:469-475).
- (O) `erase_graph` in Python invalidates **this engine's** route cache only (`nodes_edges.py:1473-1520`). Other engines keep a stale route for up to 30 s, which surfaces as a table-not-found error, not a silent failure.
- (O) **Not touched by any erase path:** `^BM25Idx`, `^IVF`, `^PLAID`, `^VecIdx` (no reference in `Eraser.cls`; absent from `GraphStores.Inventory`, scoped and unscoped lists alike). Nor are `docs_quarantine` or `edge_vector_quarantine`. Code comments call `Graph_KG.docs` "the BM25 corpus" (`Eraser.cls:138-144`, `GraphStores.cls:46-49`), and migration/v4.0.0.md l.750 says a BM25 index's "corpus is `Graph_KG.docs`". `BM25Index.Build` actually reads `rdf_props` (`BM25Index.cls:123-128`).
- Cases: erase g when g and h share node IDs (routes are per graph, so h is intact; tested in `tests/e2e/test_227_erase_isolation.py`, live); a failed DROP (empty route kept with its registry row; reused at its width); erasing the default graph (legacy rows deleted, legacy registry row kept); EraseAll followed by the next write (no registry row, so the default pair falls back to the legacy table, and width comes from the catalog per `29ea5b14`); a BM25 or IVF index built over g, then g erased (stale answers, F1).
- Tests: `tests/e2e/test_227_erase_isolation.py`, `test_230_erase_residue.py`, `tests/integration/test_227_orphan_route_erase.py` (live); `tests/unit/test_227_erase_plan.py`, `test_eraser_inventory_coverage.py` (unit). None covers `^BM25Idx` or `^IVF`.

## Candidate obligations for formal modeling

**O1 — BM25 counter consistency (L1).** At every committed point, for index `x`:
- `df(t) = |{d : tf(t,d) defined}|`, and `df(t)` is absent iff that count is 0;
- `doc(d) = {t : tf(t,d)}`;
- `N = |dom len|`;
- `totalLen = Σ len(d)`;
- `vocab_size = |dom df|`;
- `len(d) = Σ_t tf(t,d) > 0`.

Search scores with the idf of the df it reads.

L2: Insert and Delete hold `Lock ^BM25Idx(x,"lock")` and a TSTART/TCOMMIT with plain Set; RemoveDoc runs before add; tokenization happens outside the lock; RequireWritable is checked before and under the lock. Build and Drop take no lock. Search takes no lock and has no isolation.

L3 operations to bind: `BM25Index.Insert` :442, `Delete` :496, `RemoveDoc` :416, `Build`/`IndexDoc` :97/:178, `Drop` :587, `SearchCore` :236.

Cases the model must represent:
- replace with overlapping and disjoint token sets;
- replace with empty text;
- delete of an absent document;
- the first insert into an absent index;
- a failure after partial Sets (rollback);
- Build interleaved with Insert (F2);
- Insert inside a caller transaction (F3: nested TCommit plus full TRollback).

**O2 — Schema upgrade lifecycle (L1).** A schema-1 index is searchable but not writable. After `Upgrade` completes it is schema 2 with O1 holding. A reader observing `schema=2` observes complete df, doc, N, totalLen and vocab. Writers are refused from flag-set to flag-clear. Re-running after any interruption converges.

L2: the `upgrading` flag is set before the lock; the lock is held; there is no transaction; df and doc are killed and rebuilt from tf; the counters are recomputed; `schema` flips; then `idf` and `avgdl` are killed and the flag cleared. The `already` check happens only before the lock.

L3: `Upgrade` :526-581, `RequireWritable` :385, `SearchCore` :246, :303-311.

Cases: a crash at each step; a stale flag; a second concurrent Upgrade (F4); Search spanning the flip; Insert waiting on the lock across the flip.

**O3 — One route per (graph, model, kind) and identity-agreeing writes (L1).**
- Every stored vector is in exactly the table the registry names for its `(graph, model, kind)`.
- Reads of a pair never return another pair's vectors.
- A write is refused iff its width, dtype or mechanism disagrees with the pair's recorded identity (a model disagreement is routed).
- The default pair alone falls back to the legacy table.

L2: `_read_route` (preference sort when several rows answer), the 30 s TTL cache, the per-process lock, the registry PK `(table_name, graph_id)` as cross-process arbiter, the conditional claim UPDATE, and enforcement outside the write transaction.

L3: `resolve_route` :237, `_read_route` :377, `_create_route` :470, `_route_for_write` :755, `_route_for_read` :652, `store_embedding(s)` :942/:1028, `enforce_embedding_identity` `schema.py:1354`, `set_embedding_identity` :1086, `_record_configured_embedding_identity` :1485, `EmbedQueue.ProcessBatch` :258.

Cases: two creators in one process and in two processes; the route created before the legacy table is claimed (F9); an undeclared writer on the default graph vs a named graph (Q1); a stale cache after a remote erase; a registry read failure (F11); the IRIS queue worker on the default graph (F8).

**O4 — Quarantine conservation and placement (L1).**
- Migration: `placed + quarantined = pre-upgrade rows`; no row goes to the default graph by guess; re-running is idempotent.
- `place_quarantined` either moves exactly one row into an existing route whose width and dtype match and whose node exists in that graph, deleting it from quarantine in the same transaction, or changes nothing.

L2: watermark over staging and quarantine; per-chunk commits; `NOT EXISTS` plus DELETE in redistribution; INSERT before DELETE in `write_txn`.

L3: `_drain` :922, `_redistribute` :1048, `place_quarantined` `schema.py:1972`.

Cases: a kill between chunks; a resolver declining; a route absent at placement; the target `(graph, node)` already holding a vector; concurrent placement of one row.

**O5 — Erasure completeness over search stores (L1, ADR-0004).** After `EraseGraph(g)` commits, no read scoped to g returns g's erased content. That covers the routes, legacy tables, `docs`, the registry rows of dropped routes, **and** derived search indexes (BM25/IVF), unless those are declared exceptions. EraseAll empties every registry row. Quarantines survive by decision.

L2: one transaction over rows and globals; DDL after the commit; claimed vs orphan routes.

L3: `Eraser.EraseGraph` :46, `EraseAll` :707, `EraseNodeIds` :372, `GraphStores.Inventory`.

Cases: a shared node ID across graphs; a failed DROP; erasing the default graph; a BM25 index recorded for g (F1).

**O6 — Fusion contract (L1, to be decided; see Q2/F5).**
- RRF over k legs: `score(x) = Σ_{legs where x appears} 1/(c+rank)`.
- An absent item contributes 0 (or a documented constant).
- A failed leg is reported, not read as empty.
- All legs answer the same graph.

L3: `vector.py:1382`, `schema.py:2526`, `translator.py:3239`, `fusion.py:27`.

## Candidate findings

### Bugs (all SUSPECTED unless stated)

- **F1 — Derived search indexes outlive erasure.**
  - Expected (D): ADR-0004 l.10-12 ("every store that holds it") and l.79-80. `GraphStores.cls:1-16` claims to be the one inventory, including unscoped stores. The Eraser's own rationale for `docs` (`Eraser.cls:138-144`): text "outlived the graph … the id it named came back attached to whoever created that node next". `^IVG.AlgoCache` is erased because "no answer outlives erased content" (`GraphStores.cls:113-116`).
  - Observed: `^BM25Idx`, `^IVF`, `^PLAID` and `^VecIdx` are in neither inventory list and no erase path touches them. A BM25 index records its graph (`cfg graph`, `BM25Index.cls:168`), so it is attributable. After `erase_graph(g)`, `bm25_search` and `kg_RRF_FUSE(graph=g)` (which prefers the index recorded for g, `vector.py:204-206`) return erased node IDs. If those IDs are re-created in g, the erased text scores for them. `^IVF` keeps erased vectors' cell assignments after their route is dropped.
  - Docs contradict the code: migration/v4.0.0.md l.750 says the BM25 corpus is `Graph_KG.docs`; `BM25Index.Build` reads `rdf_props`.
  - Distinguishing test: build a BM25 index for g, `erase_graph(g)`, then `bm25_search` returns the erased IDs.

- **F2 — BM25 `Build` and `Drop` bypass the write lock and transaction.**
  - Expected (D): ADR-0007 "does every write under an index-level lock"; FR-016 and FR-018 consistency "at every committed point".
  - Observed: Build `Kill`s and rewrites with no lock (`BM25Index.cls:97-175`). An `Insert` that runs after Build's Kill sees no N, so it is "new" (:387). It writes N=0 and schema=2 and adds its doc's df. Build's `IndexDoc` then adds df again for the same document if Build also indexes it, and Build finally overwrites N, totalLen and vocab_size with its local counts (:160-164). Result: df > |tf| or N disagreeing with len, persisting until the next Build.
  - Distinguishing test: Insert concurrent with Build on the same name, then compare df with a brute-force count.

- **F3 — BM25 Insert/Delete undo takes back a caller's transaction.**
  - Expected (O-policy, 4.6.4 `_write_txn.py` docstring): IVG's undo "takes back IVG's level alone, so a failed write leaves the caller's earlier work". `Eraser.cls` uses `While $TLevel > tTxnLevel { TROLLBACK 1 }`.
  - Observed: `If $TLevel > 0 TRollback` (`BM25Index.cls:487, 508`) rolls back every level. The under-lock `RequireWritable` refusal (:459) throws before `TStart`, so it still rolls back the caller's work. A nested `TCommit` releases the lock (:491) before the caller commits, so another writer can build on uncommitted df/N that the caller may later roll back.
  - Reachable from ObjectScript callers in a transaction. Reachability from Python depends on whether the Native object shares the SQL connection's process (`_write_txn.py` says it "need not").

- **F4 — `Upgrade` re-checks nothing under the lock.**
  - Observed: the `already` test is before the flag and lock (:529). A second Upgrade that waited on the lock re-runs on a schema-2 index. It kills df and doc (:542) while schema=2, so Searches read a partial df and skip terms (:300-301).
  - Expected (D): FR-023, which says a Search never observes an incomplete schema 2. Low likelihood.

- **F5 — The engine RRF's absent-item contribution is non-zero and length-dependent; the four RRF implementations disagree.**
  - Evidence: `vector.py:1444-1446` vs `schema.py:2536-2537` (1e9), `translator.py:3342-3352` (0) and `fusion.py:56-58` (0).
  - Expected: the docstring and API reference ("each hit scores 1/(c+rank)"; "legs not yet searched contribute nothing").
  - Example, c=60, legs of 200: A at vector rank 1 only scores 1/61 + 1/320 = 0.01952. B at rank 50 in both scores 2/110 = 0.01818. The engine ranks A first; standard RRF ranks B first.
  - Also (confirmed, KNOWN_ISSUES l.172): one `try` makes a vector-leg failure answer `[]`. `IRISGraphOperators.kg_RRF_FUSE`'s default `query_vector="[]"` triggers it for every text-only call against a declared-width table (`operators.py:37`, `vector.py:487-502`).

- **F6 — Fusion index choice comes from an engine-lifetime snapshot.**
  - Observed: `_index_registry` is built at construction or schema check (`engine.py:367, 1885`). `bm25_drop` and `ivf_drop` remove nothing from it or from `_index_graph_scopes` (`vector.py:1868-1870, 2058-2060`). The fusion therefore keeps choosing a dropped index, whose Search answers `[]` silently, and never sees an index another process built. A cached scope survives another process rebuilding the name for another graph, so the fusion can use another graph's index as this graph's own.

- **F7 — Under `USE GRAPH g`, a BM25 index built for graph h is read as g's.**
  - Observed: `_index_graph_rows` returns None whenever `USE GRAPH` is set and never compares the recorded graph (`translator.py:3125-3141`). `ivg.retrieve` passes `bm25_name` unchecked (:3283-3292). Node IDs from h are then joined to g's nodes.
  - Expected (D): spec 230 FR-009 "an index covers one graph"; 4.6.0 R192 intent (`translator.py:3258-3261`).

- **F8 — The queue's identity check targets the wrong table, and the IRIS worker skips it for the default graph.**
  - Observed: `enqueue_for_embedding` enforces against `kg_NodeEmbeddings`@'' for every `graph` (`embeddings.py:1838-1842`). A named-graph request for model B is refused if the default table is claimed by A, although `store_embedding` would route it. The Python worker's docstring rejects exactly this check as the 3.2.0 error (:1993-1998).
  - Observed: `EmbedQueue.ProcessBatch` sends every default-graph entry to `kg_NodeEmbeddings` regardless of its `config`, with no identity check (`EmbedQueue.cls:278-283, 316`). This contradicts `ClaimPendingBatch`'s stated reason for carrying `config` (:108-111): otherwise the queue "would be the one write path that escapes the embedding identity registry".

- **F9 — Two registry rows can answer one pair.**
  - Scenario: an A-configured engine stores into the default graph while `kg_NodeEmbeddings` is still adopted-unknown, which creates `kg_emb_hash('', a)` (`embeddings.py:779-788`). A later `initialize_schema` claims `kg_NodeEmbeddings` for A (`schema.py:1512`). `_read_route`'s preference now picks `kg_NodeEmbeddings` (:455, `_route_preference` :107-118). The earlier vectors are stranded in the routed table, and undeclared vectors in the legacy table become "A". FR-011's "one graph's vectors split across both" (:270-273) results.
  - The registry has no uniqueness on `(graph_id, model_key, kind)` (`schema.py:143-160`).

- **F10 — Migrated named-graph edge vectors are unreachable.**
  - Observed: `place_edge_vectors` puts each vector in `kg_EdgeEmbeddings` with `graph_id` = the asserting graph (`statements.py:203-212`), and no registry row is added for `(g, model, edge)`. `edge_vector_search(graph=g)` reads only a registered route, so it returns `[]` (`vector.py:355-358`, `embeddings.py:676-678`). The next `store_edge_embedding(graph=g)` creates `kg_eemb_…`, splitting g's edge vectors across two tables.
  - The manual SQL in migration/v4.0.0.md l.592-597 targets the same unreachable place.
  - Distinguishing test: migrate a two-graph 3.2.0 edge table, then call `edge_vector_search(graph=g)`.

- **F11 — Identity enforcement fails open on a registry read error.**
  - Observed: `get_embedding_identity` returns None for any exception (`schema.py:1054-1056`), and `enforce_embedding_identity` then permits the write (:1383-1385).
  - Expected (O, R161 rationale at `embeddings.py:438-444`): "any other failure … raises".
  - Impact is limited: IRIS still enforces column width. What is lost is the mechanism and dtype checks and the explanatory refusal.

- **F12 (open/low) — ADR-0005's letter says the 3-argument `TO_VECTOR` "MUST NOT be used for a query vector".** It is used with the query's own length in `edge_vector_search` (`vector.py:368`), `vector_search` (:1240), `dbapi_utils.py:268` and `iris_sql_store.py:2634`. The length there is the query's own, so no reshape is expected. The ADR's measured hazard is a column width declared on the query. For a string query, the length is `count(",")+1`. Either narrow the ADR or drop the length.

- **F13 (low) — `TextSearchEngine.search_documents` is public, graph-unscoped and very likely always fails.** It reads unqualified `docs` and uses `%FIND(text,?)` (`text_search.py:48-66`; compare `schema.py:2499-2502`). Its LIKE fallback is unscoped and errors return `[]`.

### Simplifications (P)
- **S1.** One RRF function with an explicit absent-rank rule and per-leg failure reporting. The engine, operators and `fusion.py` would call it. The SQL procedure and `ivg.retrieve` would document the same rule. Preserve per-graph scoping and the empty-text skip. Distinguishing case: F5's A/B example.
- **S2.** Add `^BM25Idx`, `^IVF` and `^PLAID` to `GraphStores.Inventory`, either as graph-scoped by recorded graph (the Eraser drops or empties an index whose `cfg graph` is g, and the IVF graph is derived from `cfg table` plus the registry) or as explicit unscoped "derived, rebuild after erase". Preserve: indexes of other graphs are untouched. Distinguishing case: erase g with indexes for g and h.
- **S3.** BM25 `Build` builds under a temporary name and swaps under the write lock, or takes the lock and an `upgrading`-style flag. `Upgrade` re-checks `already` under the lock. The Catch uses `TROLLBACK 1` down to the entry level. Preserve: Search keeps working throughout.
- **S4.** Let `enforce_embedding_identity` reuse the row `_read_route` just read (one read; same raise-on-error policy), and apply the `_assert_entry_is_this_workers_work` reasoning to `enqueue_for_embedding` by checking the target route. Preserve: refusal happens before anything is queued or written.
- **S5.** Enforce uniqueness of `(graph_id, COALESCE(model_key,''), kind)` in the registry, or migrate a pre-existing route when a legacy table is claimed, so that `_route_preference` stops being load-bearing.

### Open questions for a human
- **Q1.** Should an undeclared writer be able to add vectors to a model-claimed default table at the same width? The code (`embedding_identity.py:85-91`) says yes. `CONTEXT.md` says writes at another model are "refused rather than mixed in". For named graphs, undeclared writes are isolated in their own route.
- **Q2.** Is a model mismatch to be refused (ADR-0006, v3.2.0) or routed (v4.0.0)? Currently `initialize_schema` refuses a second model on `kg_NodeEmbeddings` while `store_embedding(model_key=…)` routes it. ADR-0006 needs a "Later" note either way.
- **Q3.** Spec 044 FR-012 / US5 (`kg_TXT` uses `^BM25Idx("default")` when present) is not implemented: `kg_TXT` uses iFind/LIKE over `docs` (`vector.py:917-1054`). Is it superseded? The spec is still "Draft".
- **Q4.** Search reads BM25 globals without isolation during a write (FR-019 "Search takes no lock"). Are transiently mixed N/df/len reads, or reads of uncommitted state, acceptable? FR-023 guarantees snapshot-like behavior only for Upgrade.
- **Q5.** Should quarantines (`embedding_quarantine`, `docs_quarantine`, `edge_vector_quarantine`) survive `EraseAll` and graph erasure indefinitely? This is the current decision (FR-039/FR-040 as quoted). Is there a purge path for a deployment that must delete data? ADR-0004 says erasure is not a privacy primitive, but redaction (ADR-0013) does not mention quarantines either.
- **Q6.** Is `max_df_fraction`'s "alphabetical" `skipped` order (FR-044-C4) meant to be ObjectScript collation, where numeric terms sort first? Trivial, but a model of `SearchReport` must choose.

## Not inspected / limits
- The texts of specs 226, 227 and 230 are not in the repository. Their FR numbers come only from code comments and CHANGELOG, so the authority of each FR clause could not be verified.
- The opsreview BM25 request file is external.
- `embed_nodes`/`embed_edges` bodies, `vector_search`, `kg_VECTOR_GRAPH_SEARCH`, `measure_route_recall`, `embedding_inventory` details, `Eraser.EraseNodeIds` (only partly read), `CollectOrphanRoutes`, `GraphStores.Digest`, `IVFIndex`/`VecIndex`/`PLAIDSearch` internals, `migrations/graph_scoped_embeddings.rekey` and `kg_node_stores.py`, the snapshot/restore treatment of `^BM25Idx`/`^IVF` (`Snapshot.cls:97`), the REST `/hybridSearch` route and GraphQL resolvers.
- Concurrency claims depend on IRIS semantics: Lock, TSTART/TROLLBACK, globals read without isolation, and default SQL isolation. They were reasoned from source, not measured. Reachability of F3 from Python depends on Native API process sharing.
- No test was run. "Live" means the test needs an IRIS container per its fixtures.
