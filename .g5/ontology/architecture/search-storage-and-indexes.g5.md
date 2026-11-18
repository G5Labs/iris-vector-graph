# Search storage and indexes

See how IVG maintains embedding routes, named indexes and the inputs to a fused search. For query inputs and returned results, start at [search](../features/search.g5.md).

## Definitions

- **Embedding table**: a SQL table of vectors. The **original tables** are `kg_NodeEmbeddings`, `kg_NodeEmbeddings_optimized` and `kg_EdgeEmbeddings`.
- **Route**: the one table that holds a given graph's vectors of a given model and kind (node or edge). A **routed table** is a route created for one graph and model.
- **Embedding registry**: the table `Graph_KG.embedding_registry`, with one row per embedding table and graph, recording model key, mechanism, width and element type.
- **Quarantine**: tables holding vectors and documents that an upgrade could not assign to a graph.
- **Document frequency (df)**: for a term, how many documents in the index contain it. A document's **token record** lists its distinct terms.
- **Index schema**: the version of a BM25 index's stored layout. Schema 1 is the original; schema 2 adds document frequencies and token records.

## Embedding registration and production

<a id="search.embedding.registry"></a>
[D · search.embedding.registry]

The record lives in the embedding registry, a table every installation has. It is not kept in the revision ledger or in each vector row.
- It works when the revision ledger is off, which is the default.
- It can describe a table that holds no vectors yet.
- It holds the current identity, not a history of changes.

<a id="search.embedding.width.raw-helpers"></a>
[D · search.embedding.width.raw-helpers]

The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract.

<a id="search.embedding.claim"></a>
[D · search.embedding.claim]

An upgrade records each existing table with its width and an unknown model. Setup by an engine that declares a model, or an explicit identity call, claims such a table; when two claim at once, exactly one wins. An ordinary vector write never claims a table: a write that names a model goes to that model's own route.
- After that, an operator can replace the recorded model only with an explicit force. The override is logged as a warning, because every vector already stored becomes incomparable.

<a id="search.embedding.queue"></a>
[I · search.embedding.queue]

Queued embedding work is checked before it is queued, against the identity of the table it will be written to. A worker fails each entry that asks for a model it does not produce, and the rest of the batch continues.
- An entry whose text cannot be embedded, or whose vector cannot be stored, is marked as an error with the reason, never as done.

- Working assumption: A single active consumer per namespace is the contract (supported by 5bb149ed); model both workers as independently schedulable, treat single-worker as an unenforced premise, and prefer enforcement (refuse a second worker) or documentation; atomic claims with recovery remain the multi-worker alternative.
- Working assumption: one worker at a time is assumed, so entries are not claimed. An entry is marked done before its vector is stored, and is changed to an error if storing then fails.

<a id="search.embedding.bulk"></a>
[D · search.embedding.bulk]

A bulk embed computes and stores vectors for the nodes of one graph that it selects, through the same checked write as any vector write.
- It selects the graph's nodes with the given label, or the listed IDs, minus those an exclusion glob matches. A node that already has a vector on the route is skipped unless the call forces a new one.
- The text embedded for a node is its ID, unless the caller gives a text function.
- Today a glob containing `_` or `%` excludes nothing ([finding](../../Verus_verification/bugs_issues.md#bug-srch-105)), and the label may come from the same ID in another graph ([finding](../../Verus_verification/bugs_issues.md#bug-srch-106)).

## How routes and indexes stay current

<a id="search.routes.cache"></a>
[D · search.routes.cache]

A route lookup may reuse a decoded registry row for up to 30 seconds by default, with a separate entry for each registry, graph, model and vector kind. A response with no row or an absent registry does not create a cache entry; a remembered row may hide a later registry change until it expires or is invalidated.
- A row exactly at the time limit is still usable. Disabling cache lookup forces a fresh read without clearing stored entries.

<a id="search.routes.create_on_write"></a>
[D · search.routes.create_on_write]

The first write for a graph and model creates the route at the width of the vector being written: the table, an attempted vector index and a registry row, committed together. When two writers create one route at once, one table results and both use its recorded width.
- A new route cannot be created inside a caller's open transaction.

<a id="search.routes.orphan"></a>
[D · search.routes.orphan]

A routed table that exists without its registry row is an orphan. No read uses it, an erase empties the erased graph's rows from it but never drops it, and creating that route again reuses the table only if its column declares the width asked for.

<a id="search.scope.indexes.upkeep"></a>
[D · search.scope.indexes.upkeep]

A named search index changes only through its own build, insert, delete and drop calls, so the caller keeps it in step with the graph. Node writes and node deletes do not update it, so a deleted node stays findable through the index until the caller removes it or rebuilds the index.
- Erasure is the exception: it must [clear the erased graph's content](../features/search.g5.md#search.erasure.indexes) from these indexes.

## Vectors and documents awaiting graph assignment

<a id="search.quarantine"></a>
[I · search.quarantine]

An upgrade puts every existing vector either into exactly one graph or into quarantine with a reason. It never assigns an uncertain vector to the default graph, and no search reads quarantined vectors.
- The reasons are: several graphs hold the node, no graph holds it, or a caller-supplied resolver declined to choose.
- A resolver may choose a graph, but only one that holds the node.
- The upgrade can be run again after it stops. Placed plus quarantined vectors always equal the vectors it started with.
- Documents and edge vectors that the same upgrade could not place go to quarantine tables of their own, and an operator places them by hand.

- Working assumption: Keep quarantined data and explicitly report retention until an owner chooses a purge API and its unknown-graph semantics.
- Working assumption: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.

<a id="search.quarantine.placement"></a>
[I · search.quarantine.placement]

An operator places quarantined vectors one at a time, naming the graph and model. Placement never creates a route. It is refused, leaving the vector in quarantine, unless the route exists with the same width and element type and the node exists in that graph.
- The vector is copied into the route and removed from quarantine in one transaction. If the route refuses the copy, for example because it already holds a vector for that node, the vector stays in quarantine.
- Today no quarantined vector can be placed through the IRIS DB-API driver: the call fails reading the row it just fetched ("Cursor closed"), and the vector stays in quarantine ([bug-srch-116](../../Verus_verification/bugs_issues.md#bug-srch-116)).

## How BM25 maintains document frequencies

<a id="search.bm25.query_time_idf"></a>
[D · search.bm25.query_time_idf]

IDF and average length are computed at search time from the current document count, document frequencies and total length. A score therefore never reflects an older index size. The scores of an index that had incremental inserts change when it is upgraded.

<a id="search.bm25.counts"></a>
[I · search.bm25.counts]

At every committed point, an index's stored counts agree with its stored postings.
- A term's df equals the number of documents holding it, and the term has no df entry when that number is zero.
- A document's token record lists exactly its distinct terms.
- The document count, total length and number of distinct terms match the stored documents.

<a id="search.bm25.incremental"></a>
[I · search.bm25.incremental]

Adding, replacing or removing one document costs in proportion to that document's distinct terms, never to the size of the index or its vocabulary.
- Only a full build and an upgrade may walk a whole posting list or the whole vocabulary.

<a id="search.bm25.write_lock"></a>
[D · search.bm25.write_lock]

Every write to an index runs under that index's write lock inside a transaction, so a failed write leaves the index as it was and two writers never interleave. Searches take no lock.
- A failed write takes back only its own changes. It never commits or rolls back a transaction the caller has open, so the caller's earlier writes in that transaction survive.
- Index writes go through the engine's own native connection, so they are part of the caller's transaction only when the engine was made on the caller's connection ([engine connection](../../Verus_verification/open_questions.md#structure.write.engine-connection)).
- A writer waits for the lock up to a set time, 30 seconds by default, then fails without changing anything.
- Counters are updated with plain writes, not atomic increments, because a rollback does not undo an atomic increment.

- Working assumption: Serialize Build, Drop, Insert, Delete and Upgrade per index and publish a complete generation or return unavailable, including after a crash; a Build that is refused or indexes nothing must not destroy the previous index. Model the as-built (unlocked Build/Drop, Kill-first) separately as the baseline. Same as decisions.md.
- Working assumption: Treat transaction membership as dependent on the connection used by the engine.

<a id="search.bm25.schema"></a>
[D · search.bm25.schema]

Each index records its schema, and an index without one is schema 1. Searches work on both schemas. Inserts and deletes on schema 1 are refused with an error naming the upgrade, with no fallback to the slow method.
- A full build and the first insert into a new index create schema 2.

## How fusion assembles its inputs

<a id="search.fusion.python"></a>
[D · search.fusion.python]

The exported Python `RRFFusion.fuse_results` uses each entity's first position in each list, starting at one, and adds nothing for a missing entity. It ignores the providers' score magnitudes, returns each entity once in descending fused score, and promises no order between tied scores.

- `HybridSearchFusion.multi_modal_search` fuses the legs that completed and returns at most k entities with their fused rank and each retained leg's first score and position. A successful graph expansion is another ranked leg.
- These Python helpers' shipped behavior is settled; whether to keep them as supported public API is [open](../../Verus_verification/open_questions.md#HD-0705).

- Working assumption: Treat the three as compatibility surfaces and qualify each: RRFFusion is a pure standard-RRF helper (document that its rule differs from engine `kg_RRF_FUSE`, HD-0702); HybridSearchFusion is de facto public (migration guide) and graph-scoped; TextSearchEngine is exported but reads every graph and its document search cannot reach the IVG Schema, so it is not a supported reader of graph-scoped data. Prefer deprecation with migration advice (to `kg_TXT` / `bm25_search`) or a `graph=` argument; do not remove without a compatibility decision.

<a id="search.fusion.leg_index"></a>
[D · search.fusion.leg_index]

The engine's fusion reads its vector leg from an IVF index recorded for the requested graph, else from the server-side vector search, else from an IVF index whose graph is unknown; with none of these the vector leg is empty.
- Only the engine object that built an IVF index knows its graph. The same call on the same data therefore reads the IVF index in the process that built it and the server-side search everywhere else, including in `IRISGraphOperators`, which makes its own engine ([finding](../../Verus_verification/bugs_issues.md#bug-srch-110)).
- An IVF index built with "cosine" ranks by the dot product ([search.ivf.metric](../features/search.g5.md#search.ivf.metric)), so the two answers can differ.
- The text leg uses the graph's own BM25 index, whose graph is stored with it.

## Metadata

### search.embedding.registry

- Sources: [ADR-0006 decision and context](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md#L7-L54), [registry DDL](../../../iris_vector_graph/_engine/schema.py#L143-L160), [test_embedding_registry_e2e.py](../../../tests/integration/test_embedding_registry_e2e.py)
- Expands: [Embedding identity](../features/search.g5.md#search.embedding)
- Superseded in part: ADR-0006 says `graph_id` is reserved and read by nothing. Since v4.0.0 it is real, and the registry also names each route ([CHANGELOG v4.0.0](../../../CHANGELOG.md#L4161-L4183)).
- agent
- architecture-decision
- test-coverage

### search.embedding.width.raw-helpers

- Expands: [parent](../features/search.g5.md#search.embedding.width)
- agent
- manual-check-review

Findings: [Should the low-level vector helper refuse a vector of the wrong width?](../../Verus_verification/open_questions.md#HD-1704).

Audit sources, current behavior, options, costs and settling evidence: [question review](../../Verus_verification/audits/register-20261115/question-review.md#HD-1704).

Audit (HD-1704): Existing authority: The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-1704).

### search.embedding.claim

- Sources: [ADR-0006 on the conditional first-writer claim](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md#L51-L54), [set_embedding_identity](../../../iris_vector_graph/_engine/schema.py#L1086-L1220), [concurrent claim test](../../../tests/integration/test_embedding_registry_e2e.py#L608-L681), [force test](../../../tests/integration/test_embedding_registry_e2e.py#L389-L398)
- Verus: [install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_adopt_never_overwrites`, `theorem_claim_only_unknown`, `theorem_adopted_row_claimed_keeps_width`, `theorem_same_model_kept`, `theorem_undeclared_set_refused` (binding `I:*`: adopted, claimed, normalized key kept, other model refused, forced, re-adoption leaves rows; concurrency not exercised)
- Expands: [Embedding identity](../features/search.g5.md#search.embedding)
- agent
- data-integrity, operations
- test-coverage

Findings: [Claiming the default embedding table for a model that already has a default-graph route makes that model's stored vectors unreadable](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-007)


The body's earlier "first writer that declares a model claims the table" was ADR-0006's wording from before routing; review round 3 R3-reader H4 aligned it with the code ([schema.py set_embedding_identity](../../../iris_vector_graph/_engine/schema.py#L1086-L1220), [setup claim](../../../iris_vector_graph/_engine/schema.py#L1485-L1513), [_read_route](../../../iris_vector_graph/_engine/embeddings.py#L403-L416) matches `model_key` only).

### search.embedding.queue

- uncertain
- Sources: [enqueue_for_embedding](../../../iris_vector_graph/_engine/embeddings.py#L1803-L1874), [process_embed_queue docstring and worker check](../../../iris_vector_graph/_engine/embeddings.py#L1898-L2016), [ClaimPendingBatch rationale](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L105-L136), [IRIS worker: a failed write is an error, not done](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L318-L333), [test_embed_queue_identity_e2e.py](../../../tests/integration/test_embed_queue_identity_e2e.py)
- Expands: [Embedding identity](../features/search.g5.md#search.embedding)
- Children: [May two workers process the queue at the same time, and must an entry be marked done only after its vector is committed?](../../Verus_verification/open_questions.md#search.embedding.queue.processing)
- Observed divergence: enqueueing checks the default graph's original table whatever the target graph, and the IRIS worker writes default-graph entries there whatever their model (F8 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)). The IRIS worker also marks an entry done when its embedding statement fails to prepare or returns no row ([ProcessBatch](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L306-L330)).
- Observed (iteration 36, [W42](../../uplift/consolidated/iteration-36/embed-queue-PAIRS.md)): the Python worker follows this rule. The IRIS worker (the task `start_background_embedding` starts) marks an entry done, with no vector and no reason, when the provider fails, answers nothing or the config is unknown. It also cannot store any default-graph vector: each such entry ends as an error naming a required `graph_id`. In a named graph it stores the provider's vector and marks the entry done.
- Verus: active: [`embed_queue.rs`](../../Verus_verification/models/embed_queue/embed_queue.rs) `rule_ok` (this rule), `theorem_python_worker_meets_rule`, `theorem_iris_named_success_stored`; as-built departures `theorem_iris_unanswered_marked_done`, `theorem_iris_default_graph_never_stores`; reviewed repair `theorem_reviewed_iris_meets_rule`; open question `theorem_interrupted_mark_breaks_rule`.
- agent
- data-integrity, operations
- test-coverage

Findings: [The embedding queue checks identity against the wrong table, and its IRIS worker writes default-graph entries with no identity check](../../Verus_verification/bugs_issues.md#bug-srch-006); [The IRIS queue worker marks an entry done when the provider fails or answers nothing](../../Verus_verification/bugs_issues.md#bug-srch-103); [The IRIS queue worker cannot store a default-graph vector](../../Verus_verification/bugs_issues.md#bug-srch-104)

Open questions: [May two embed queue workers run at once?](../../Verus_verification/open_questions.md#HD-0604), [May two workers process the queue at the same time, and must an entry be marked done only after its vector is committed?](../../Verus_verification/open_questions.md#search.embedding.queue.processing)

### search.embedding.bulk

- Sources: [API_REFERENCE embed_nodes, get_unembedded_nodes, embedding_count](../../../docs/API_REFERENCE.md); [DATA_FORMATS §7](../../../docs/setup/DATA_FORMATS.md); [`EmbeddingsMixin.embed_nodes`](../../../iris_vector_graph/_engine/embeddings.py#L1291), [`build_node_where`](../../../iris_vector_graph/embed_selector.py#L75), [`_glob_to_sql_like`](../../../iris_vector_graph/embed_selector.py#L71-L72)
- Expands: [Embedding identity](../features/search.g5.md#search.embedding)
- Verus: active: [`embed_selection.rs`](../../Verus_verification/models/embed_selection/NOTES.md) `theorem_existing_vectors`, `theorem_plain_pattern_excludes`; as-built departures `theorem_special_pattern_excludes_nothing`, `theorem_label_from_other_graph`.
- agent
- user-facing-behavior

Recovered in iteration 43 from the API reference and observation ([W49](../../uplift/consolidated/iteration-43/embed-nodes-PAIRS.md)) with a fixture model on the per-text path; the SentenceTransformer batch path was not exercised.

Findings: [embed_nodes ignores an exclude_pattern with an underscore](../../Verus_verification/bugs_issues.md#bug-srch-105); [embed_nodes in a named graph selects by another graph's label](../../Verus_verification/bugs_issues.md#bug-srch-106)

### search.routes.cache

- design-verified

- Sources: [cache key and clock](../../../iris_vector_graph/_engine/embeddings.py#L307-L344), [invalidation](../../../iris_vector_graph/_engine/embeddings.py#L346-L375), [raw registry reader](../../../iris_vector_graph/_engine/embeddings.py#L377-L468), [source survey](../../uplift/consolidated/iteration-10/next-vector-survey-report.md), [actual native miss then another-engine creation](../../uplift/consolidated/iteration-11/root-vector-native.json)
- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `key`, `cached`, `evict`, `resolve`, `invalidate` and `theorem_all_search_phases_keep_original_scope` derive cache key isolation, separate store/lookup timestamps, strict expiry, no negative insertion and read counts. V2 fixes registry/graph/model/node-kind/TTL from the original stable engine request across fallbacks; only provider replies and clock samples vary. Integer clock ticks preserve comparisons; arbitrary native float-clock refinement, concurrent DDL/writer correctness and universal invalidation are unproved. TTL0 bypasses lookup without clearing old entries.
- Expands: [Routes](../features/search.g5.md#search.routes)
- agent
- user-facing-behavior

The strict expiration comparison permits a hit at exactly the TTL, and a positive hit does not reread the current backend row or its errors. The source caches only decoded positive rows, including their timestamp; a miss and registry-absent response are not cached. Per-engine clocks, invalidation, typed TTL and raw registry-provider behavior remain distinct from concurrent route-writer correctness. The earlier cached-absence forecast was refuted and retained, not counted as a defect.

State machines: [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.routes.create_on_write

- Sources: [_create_route and its 4.7.0 commit comment](../../../iris_vector_graph/_engine/embeddings.py#L470-L558), [per-route locks](../../../iris_vector_graph/_engine/embeddings.py#L67-L81), [_route_for_write](../../../iris_vector_graph/_engine/embeddings.py#L755-L792), [width per route test](../../../tests/e2e/test_227_two_models.py#L86-L112)
- Expands: [Routes](../features/search.g5.md#search.routes)
- Observed divergence: [_create_routed_table and _attempt_route_index](../../../iris_vector_graph/_engine/schema.py#L884-L933) each commit, so the table and its index are committed before the registry row is inserted, and a failure between them leaves an [orphan](#search.routes.orphan). Correction 2 of the [reconstruction check](../../uplift/ivg-verus-initial/reconstruction-check.md#3-corrections-proposed) proposed restating the as-built order as the decision; the newest stated intent, the 4.7.0 comment in `_create_route`, is kept instead.
- agent
- architecture-decision
- test-coverage

Findings: [Route creation commits the routed table before its registry row, and an orphaned table makes every erase in the namespace fail](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-015)

### search.routes.orphan

- Sources: [Eraser orphan collection](../../../iris_src/src/Graph/KG/Eraser.cls#L100-L113), [CollectOrphanRoutes](../../../iris_src/src/Graph/KG/Eraser.cls#L1063-L1102), [drop only claimed routes](../../../iris_src/src/Graph/KG/Eraser.cls#L276-L299), [reused-route width check](../../../iris_vector_graph/_engine/embeddings.py#L589-L641), [test_227_orphan_route_erase.py](../../../tests/integration/test_227_orphan_route_erase.py)
- Expands: [Routes](../features/search.g5.md#search.routes)
- Note: correction 2 proposed an invariant that no orphan ever exists, on the grounds that an orphan makes every erase fail. Since 2026-09-22 the Eraser empties orphans found in the catalog, and the live test above shows an erase succeeding with one. The `_create_route` comment repeating the older claim is stale. Orphans can still arise, so this block records how they are treated.
- agent
- architecture-decision, data-integrity
- test-coverage

Findings: [Route creation commits the routed table before its registry row, and an orphaned table makes every erase in the namespace fail](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-015)

### search.scope.indexes.upkeep

- Sources: [USER_GUIDE: bm25_insert and bm25_delete keep an index current](../../../docs/USER_GUIDE.md#L893-L896), [index protocol, the only generic insert caller](../../../iris_vector_graph/index_protocol.py#L31-L60), [index wrappers](../../../iris_vector_graph/_engine/vector.py#L1548-L1879), [VecIndex usage](../../../iris_src/src/Graph/KG/VecIndex.cls#L1-L18)
- Expands: [Indexes](../features/search.g5.md#search.scope.indexes)
- Note: added from correction 6 of the [reconstruction check](../../uplift/ivg-verus-initial/reconstruction-check.md#3-corrections-proposed) as a D, because the user guide documents caller upkeep for ordinary writes and deletes. That guide does not govern erasure, which [the erasure rule](../features/search.g5.md#search.erasure.indexes) covers. No product code calls these indexes' insert or delete from a node write or delete path.
- agent
- architecture-decision, operations

Findings: [Re-inserting a node into an IVF index keeps its old vector](../../Verus_verification/bugs_issues.md#bug-srch-107)

### search.quarantine

- uncertain
- Sources: [CHANGELOG v4.0.0 quarantine](../../../CHANGELOG.md#L4199-L4217), [migration guide](../../../docs/migration/v4.0.0.md#L303-L390), [migration rules](../../../iris_vector_graph/migrations/graph_scoped_embeddings.py#L1-L33), [_fate](../../../iris_vector_graph/migrations/graph_scoped_embeddings.py#L895-L920), [quarantine DDL](../../../iris_vector_graph/_engine/schema.py#L205-L227), [test_227_migration.py](../../../tests/e2e/test_227_migration.py), documents and edge vectors: [migration](../../../iris_vector_graph/migrations/docs_and_edge_vectors.py#L1-L44), [guide](../../../docs/migration/v4.0.0.md#L525-L598), [test_230_migration.py](../../../tests/e2e/test_230_migration.py)
- Children: [Placement](#search.quarantine.placement), [Should quarantined vectors and documents survive erasure indefinitely?](../../Verus_verification/open_questions.md#q-srch-001)
- Note: no API places quarantined documents or edge vectors; the guide gives hand-written SQL.
- agent
- data-integrity, operations
- test-coverage

Open questions: [Should erasure and redaction reach the store in REACH-2?](../../Verus_verification/open_questions.md#REACH-2), [Should erasure and redaction reach the store in REACH-3?](../../Verus_verification/open_questions.md#REACH-3), [Should quarantined vectors and documents survive erasure indefinitely?](../../Verus_verification/open_questions.md#q-srch-001)

### search.quarantine.placement

- Sources: [place_quarantined](../../../iris_vector_graph/_engine/schema.py#L1972-L2070), [CHANGELOG v4.0.0](../../../CHANGELOG.md#L4199-L4217)
- Expands: [Quarantine](#search.quarantine)
- Note: only mocked unit tests exercise placement ([test_227_quarantine_api.py](../../../tests/unit/test_227_quarantine_api.py)); a mocked cursor hides the closed-cursor read of bug-srch-116.
- Verus: [install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_unreadable_row_never_placed` (as built), `theorem_placed_only_when_every_check_passes`, `theorem_refused_row_stays`, `theorem_placement_conserves_and_never_creates_route` (the post-read checks bound only with the row read repaired: binding `QR:*`)
- agent
- operations, data-integrity

Findings: [bug-srch-116](../../Verus_verification/bugs_issues.md#bug-srch-116)

### search.bm25.query_time_idf

- Sources: [spec 044 FR-017](../../../specs/044-bm25-index/spec.md#L163), [ADR-0007](../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [SearchCore](../../../iris_src/src/Graph/KG/BM25Index.cls#L236-L312)
- Expands: [BM25 index](../features/search.g5.md#search.bm25)
- Note: supersedes spec 044 FR-008's allowance for stale IDF. A schema-1 index still scores with the IDF stored at write time until it is upgraded.
- agent
- architecture-decision
- design-verified
- Formal: [`theorem_schema2_reads_current_stats`, `theorem_schema1_reads_stored`](../../Verus_verification/models/bm25_scoring/bm25_scoring.rs)

Iteration 53: an incremental insert and delete answered the same scores as a fresh build over the same documents (binding cases `inc_*` beside `fresh:*`).

### search.bm25.counts

- design-verified
- Sources: [spec 044 FR-016 and FR-018](../../../specs/044-bm25-index/spec.md#L162-L164), [Insert and RemoveDoc](../../../iris_src/src/Graph/KG/BM25Index.cls#L412-L493), [df test](../../../tests/integration/test_044_bm25_incremental.py#L157-L203)
- Expands: [BM25 index](../features/search.g5.md#search.bm25)
- Verus: [bm25_counts.rs](../../Verus_verification/models/bm25_counts/bm25_counts.rs) `theorem_insert_consistent`, `theorem_remove_consistent`, `theorem_empty_replacement_removes`, `theorem_absent_delete_is_noop` and `theorem_replace_keeps_n`; [scope](../../Verus_verification/models/bm25_counts/NOTES.md). Sequential writes only; the concurrent build below is outside the model.
- Evidence: [frozen predictions and native scoring/count observations](../../uplift/consolidated/iteration-22/bm25-PAIRS.md)
- Observed divergence: a full build running at the same time as an insert can leave df and the document count disagreeing (F2 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- agent
- data-integrity

Findings: [Building or dropping a BM25 index while documents are inserted leaves its counters inconsistent](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-003)

State machines: [bm25 counts](../../Verus_verification/models/bm25_counts/manifest.json)

### search.bm25.incremental

- Sources: [spec 044 FR-015](../../../specs/044-bm25-index/spec.md#L161), [spec 044 clarification 2026-10-08](../../../specs/044-bm25-index/spec.md#L299-L312), [cost tests](../../../tests/integration/test_044_bm25_incremental.py#L204-L231)
- Expands: [BM25 index](../features/search.g5.md#search.bm25)
- agent
- operations
- test-coverage

Findings: [A BM25 delete issued while a Build runs is lost, and bug-srch-003's proposed repair does not prevent it](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-016)

### search.bm25.write_lock

- uncertain
- Sources: [ADR-0007](../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [spec 044 FR-019](../../../specs/044-bm25-index/spec.md#L165), [LockWrite and Insert](../../../iris_src/src/Graph/KG/BM25Index.cls#L380-L493), [lock and rollback tests](../../../tests/integration/test_044_bm25_incremental.py#L491-L535), caller transaction: 4.6.4 rule "an IVG write never commits or rolls back its caller's transaction" (commit `aad50087`, [_write_txn.py](../../../iris_vector_graph/_write_txn.py#L1-L30))
- Expands: [BM25 index](../features/search.g5.md#search.bm25)
- Observed divergence: a full build and a drop take no lock (F2). The Catch of `Insert` and `Delete` runs a bare `TRollback`, which ends every transaction level: [a native probe](../../Verus_verification/receipts/native/search_bm25_caller_txn_rollback.json) saw a failed `bm25_insert` take the level from 1 to 0, and the node the caller had created earlier in that transaction was gone after its commit reported success (F3 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings); review round 1, R1-2).
- agent
- architecture-decision, data-integrity
- test-coverage

Findings: [A failed BM25 insert or delete rolls back the caller's whole transaction](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-002); [Building or dropping a BM25 index while documents are inserted leaves its counters inconsistent](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-003); [A BM25 delete issued while a Build runs is lost, and bug-srch-003's proposed repair does not prevent it](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-016)

Open questions: [Must a BM25 Build (and Drop) exclude writers and be all-or-nothing?](../../Verus_verification/open_questions.md#HD-0701), [Should whether a write joins the caller's transaction depend on how the engine was opened?](../../Verus_verification/open_questions.md#structure.write.engine-connection)

### search.bm25.schema

- Sources: [spec 044 FR-022](../../../specs/044-bm25-index/spec.md#L168), [RequireWritable](../../../iris_src/src/Graph/KG/BM25Index.cls#L383-L394), [CHANGELOG v4.2.0 BM25 schema 2](../../../CHANGELOG.md#L3374-L3400), [schema tests](../../../tests/integration/test_044_bm25_incremental.py#L270-L293)
- Expands: [BM25 index](../features/search.g5.md#search.bm25)
- Note: a full build is not refused on a schema-1 index; it replaces the index as schema 2.
- agent
- architecture-decision, operations
- test-coverage

### search.fusion.python

- design-verified

- uncertain
- Sources: [`RRFFusion.fuse_results`](../../../iris_vector_graph/fusion.py#L27-L64), [`HybridSearchFusion.multi_modal_search`](../../../iris_vector_graph/fusion.py#L113-L253), [migration guide](../../../docs/migration/v4.0.0.md#L427-L435)
- Verus: [fusion_ranking](../../Verus_verification/models/fusion_ranking/NOTES.md), as-built `rank`, `score`, `theorem_rank_ignores_magnitude`, `theorem_first_occurrence_wins`, `theorem_second_leg_changes_winner`; exact real arithmetic for rank contributions and a strict pair winner. General sorting, floating point rounding and detail assembly are observed in Python, not proved.
- Expands: [fusion](../features/search.g5.md#search.fusion)
- Children: [Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?](../../Verus_verification/open_questions.md#HD-0705)
- agent
- user-facing-behavior

No order is claimed between ties or at a tied k cutoff. This helper's zero absent contribution does not settle the shared rule for the other fusion entry points.

Open questions: [Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?](../../Verus_verification/open_questions.md#HD-0705)

State machines: [fusion ranking](../../Verus_verification/models/fusion_ranking/manifest.json)

Assumption review evidence: Same direction as decisions.md.

### search.fusion.leg_index

- Sources: [_fusion_leg_index](../../../iris_vector_graph/_engine/vector.py#L187-L225), [_index_graph](../../../iris_vector_graph/_engine/vector.py#L150-L185), [ivf_build scope](../../../iris_vector_graph/_engine/vector.py#L2023-L2025), [IRISGraphOperators.__init__](../../../iris_vector_graph/operators.py#L15-L18)
- Expands: [Fusion](../features/search.g5.md#search.fusion)
- Verus: active: [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `ivf_scope_seen`, `leg_index`, `above`, `theorem_fused_leg_depends_on_building_engine`, `theorem_other_graph_ivf_not_read`
- agent
- architecture-decision

Recovered in iteration 49; prediction F7 held for the building engine and missed for a fresh engine and the operators.

State machines: [retrieval compose](../../Verus_verification/models/retrieval_compose/manifest.json)

Findings: [The engine's fusion reads a cosine IVF index only in the process that built it, so the same call ranks differently elsewhere](../../Verus_verification/bugs_issues.md#bug-srch-110)
