# Embeddings and search

This page covers how IVG stores node and edge vectors for each graph and model, and how it searches vectors and text. It also covers how two rankings are fused into one, and what erasing a graph must remove from the search stores. Graphs and the default graph are defined on the [graph scope](../concepts/graph-scope.g5.md) page, and erasure on the [erasure](erasure.g5.md) page.

## Definitions

- **Vector**: a list of numbers a model produced for a node or an edge. Its **width** is the number of entries, and its **element type** is the number type, such as DOUBLE.
- **Model key**: the name a writer gives for the model that produced its vectors. A writer that names no model is **undeclared**.
- **Mechanism**: how vectors are produced: an IRIS embedding configuration, a local sentence-transformers model, or an external caller.
- **Embedding table**: a SQL table of vectors. The **original tables** are `kg_NodeEmbeddings`, `kg_NodeEmbeddings_optimized` and `kg_EdgeEmbeddings`.
- **Route**: the one table that holds a given graph's vectors of a given model and kind (node or edge). A **routed table** is a route created for one graph and model.
- **Default pair**: the default graph together with no declared model. Its vectors are in the original tables.
- **Embedding registry**: the table `Graph_KG.embedding_registry`, with one row per embedding table and graph, recording model key, mechanism, width and element type.
- **Quarantine**: tables holding vectors and documents that an upgrade could not assign to a graph.
- **Documents table**: `Graph_KG.docs`, one text per node and graph, read by plain text search and by the SQL fusion procedure.
- **Named search index**: an index a caller builds and searches by name, apart from the embedding tables: BM25 for text, and IVF, VecIndex and PLAID for vectors. PLAID keeps several vectors per document.
- **BM25 index**: a named lexical index over the text of one graph's nodes. Each node is a **document**, and its **terms** are the words left after tokenizing.
- **Document frequency (df)**: for a term, how many documents in the index contain it. A document's **token record** lists its distinct terms.
- **Index schema**: the version of a BM25 index's stored layout. Schema 1 is the original; schema 2 adds document frequencies and token records.
- **Fusion**: combining a vector ranking and a text ranking into one ranking. Each input ranking is a **leg**.

## Embedding identity

<a id="search.embedding"></a>
[I · search.embedding]

IVG records which model produced each embedding table's vectors and how wide they are, and checks every vector write against that record.

- Working assumption: Keep width-compatible undeclared writes to the claimed default table as current compatibility; separate-route enforcement needs an explicit decision.


<a id="search.embedding.registry"></a>
[D · search.embedding.registry]

The record lives in the embedding registry, a table every installation has. It is not kept in the revision ledger or in each vector row.
- It works when the revision ledger is off, which is the default.
- It can describe a table that holds no vectors yet.
- It holds the current identity, not a history of changes.


<a id="search.embedding.model_key"></a>
[D · search.embedding.model_key]

Two model keys match only if they are equal after trimming, lowercasing and collapsing runs of spaces. Nothing else is rewritten, because an operator can fix a false refusal, while a false match silently mixes two models.
- The mechanism must come from a fixed list.
- Two writers that name the same model with different mechanisms conflict.


<a id="search.embedding.width"></a>
[D · search.embedding.width]

A table's width is the width its vector column declares, and the registry copies that width rather than overriding it.
- Setup never changes the width of a table that holds vectors. It changes an empty table's width only when asked.
- A writer that reuses a table whose column declares another width is refused before any record claims its width.
- A query vector is never padded or cut to fit a table. A query of the wrong width raises an error instead of returning scores.
- That refusal comes before any search statement runs, and it names both widths. The width compared is the route's, or the column's declared width when the route records none.
- No check is made when there is nothing to compare: for a seed node ID, whose vector comes from the route itself; for a route and column with no declared width; or for a literal that cannot be parsed. IRIS then decides, and its refusal is raised, not turned into an empty answer.


<a id="search.embedding.width.raw-helpers"></a>
[D · search.embedding.width.raw-helpers]

The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract.


<a id="search.embedding.check_on_write"></a>
[I · search.embedding.check_on_write]

Every path that writes vectors checks the write against its table's recorded identity before writing anything, and refuses a conflict. No setting turns the refusal into a warning.
- A writer that names a model is checked on model, mechanism, width and element type.
- An undeclared writer is checked on width and element type only.
- A batch that mixes widths is refused whole.


<a id="search.embedding.claim"></a>
[D · search.embedding.claim]

An upgrade records each existing table with its width and an unknown model. Setup by an engine that declares a model, or an explicit identity call, claims such a table; when two claim at once, exactly one wins. An ordinary vector write never claims a table: a write that names a model goes to that model's own route.
- After that, an operator can replace the recorded model only with an explicit force. The override is logged as a warning, because every vector already stored becomes incomparable.


<a id="search.embedding.other_model"></a>
[D · search.embedding.other_model]

Vectors from two declared models never share a table. A write that names a model key goes to that model's own route for the graph, and a writer that declares a different model for a table that already records one is refused.

- Today setup by an engine configured for another model than a table records is refused, although that engine's writes would be routed. Whether setup should refuse or route is open.


<a id="search.embedding.queue"></a>
[I · search.embedding.queue]

Queued embedding work is checked before it is queued, against the identity of the table it will be written to. A worker fails each entry that asks for a model it does not produce, and the rest of the batch continues.
- An entry whose text cannot be embedded, or whose vector cannot be stored, is marked as an error with the reason, never as done.

- Working assumption: A single active consumer per namespace is the contract (supported by 5bb149ed); model both workers as independently schedulable, treat single-worker as an unenforced premise, and prefer enforcement (refuse a second worker) or documentation; atomic claims with recovery remain the multi-worker alternative.
- Working assumption: one worker at a time is assumed, so entries are not claimed. An entry is marked done before its vector is stored, and is changed to an error if storing then fails.


## Routes and graph scope


<a id="search.routes"></a>
[I · search.routes]

Each graph's vectors of one model and one kind live in one route. The registry is the only authority on which table that is, and no code derives a table name to find an existing route.
- One graph's vectors of one model are never split across two tables, so every read and write for that pair picks the same table.
- Edge vectors are routed the same way, keyed by graph and edge. An edge vector belongs to the graph that asserts the edge.


<a id="search.routes.no_fallback"></a>
[I · search.routes.no_fallback]

A read for a graph and model that has no route answers nothing, never vectors from another graph, model or table. The default pair is the exception, because its vectors are in the original tables.
- The route is looked up first, so a search of an unrouted pair is an empty answer even when its query vector has the wrong width: it is never a width error.
- Reading one node's vector through an unrouted pair answers no vector.


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


<a id="search.knn"></a>
[I · search.knn]

A vector search returns up to k pairs of node ID and cosine similarity from one graph's route, highest first.
- The query is a vector, or a node ID whose stored vector in the same graph is used. That node is left out of the answer.
- An optional label keeps only nodes that have the label in the same graph.
- Each route gets an attempted approximate-nearest-neighbour (HNSW) index. A route whose index was refused is searched by a full scan.


<a id="search.knn.threshold"></a>
[I · search.knn.threshold]

The generic `vector_search` and graph-routed `edge_vector_search` apply an optional cosine score threshold before taking their highest-scoring rows. Omitting it keeps all scores eligible; giving it keeps scores equal to or above it, so a score of 0.5 survives a threshold of 0.5 and a score of 0.25 does not.

- Both bind the threshold in a WHERE predicate on the cosine expression, repeating the query-vector bind for that expression. The optional graph predicate combines with that filter; sorting follows it.
- This rule concerns these two helpers, not every KNN, IVF, fusion or Cypher search surface.


<a id="search.scope"></a>
[I · search.scope]

Every vector read and write covers exactly one graph, and leaving out the graph means the [default graph](../concepts/graph-scope.g5.md#graph.default).
- The same node ID in two graphs has two separate vectors.
- A seed node's vector, label filters and counts are read from the same graph.
- A graph ID prevents collisions but is [not a security boundary](../concepts/graph-scope.g5.md#graph.tenants).
- The SQL vector-search procedures read only the original tables. Asked about a named graph that has its own route, they raise an error that names the graph-aware calls to use instead.


<a id="search.scope.indexes"></a>
[I · search.scope.indexes]

A BM25 index covers exactly one graph, and building one without naming a graph means the default graph. An IVF index records no graph. A search in one graph must not read an index built for another graph.
- A BM25 index records which graph it covers. One built before 4.0.0 covered every graph but reports the default graph, so it must be rebuilt; today the default graph's fusion reads it as its own.
- A fusion leg uses the requested graph's own index first, then the server-side vector search scoped by the query.
- An index whose graph is unknown is used only as a last resort, with a warning.

- Working assumption: Unchanged: readers see a complete published index or a clear unavailable result, including after an interrupted rebuild; the existing partial-build behaviour is the modelled baseline.


<a id="search.scope.indexes.upkeep"></a>
[D · search.scope.indexes.upkeep]

A named search index changes only through its own build, insert, delete and drop calls, so the caller keeps it in step with the graph. Node writes and node deletes do not update it, so a deleted node stays findable through the index until the caller removes it or rebuilds the index.
- Erasure is the exception: it must [clear the erased graph's content](#search.erasure.indexes) from these indexes.

## Building an IVF index


<a id="search.scope.indexes.ivf"></a>
[I · search.scope.indexes.ivf]

An IVF build reads vectors from the requested graph and model's route, never another pair's table. If the pair has no route, it raises an error before reading any vector table or starting the index build; a routed selection with no vectors also raises an error.
- Request validation and required library loading may refuse the build before the route is read. Building an index does not establish that later graph writes keep it current; the caller owns [index upkeep](#search.scope.indexes.upkeep).

## VecIndex search


<a id="search.vecindex"></a>
[I · search.vecindex]

A VecIndex is a named vector index that a caller fills and searches by name; it records no graph. A search returns up to k stored IDs, nearest first.

- For cosine the score is the cosine and the distance is 1 minus it. For dot the score is the dot product, largest first, and the distance is its negative. For l2, l1 and chebyshev both are the distance.
- A vector inserted after a build can be found at once; a build places every stored vector again. A search ranks only the IDs in the tree leaves the query reaches, so it is approximate once the index holds more vectors than a leaf.
- Inserting an ID again replaces its vector. Today the reported count still goes up by one, and creating the index again under the same name keeps the vectors but reports a count of 0.
- Today a vector of another width is accepted and becomes the index's recorded width; distances to it use only the parts both vectors have.
- Dropping the index removes everything; a search then returns nothing.

## Quarantine


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


## BM25 text search


<a id="search.bm25"></a>
[I · search.bm25]

A BM25 index is a named lexical index over chosen text properties of one graph's nodes, searched with Okapi BM25.
- A node with no indexable text is not in the index.
- Inserting a document that is already there replaces it. Replacing it with text that has no indexable terms removes it.
- Removing a document that is not in the index changes nothing.
- A search returns the top k documents by score, highest first.

- Working assumption: Assume no cross-call consistency guarantee until a read/write protocol is chosen; partial-index results remain visible risk, not approved isolation.
- Working assumption: Keep explicit BM25 selection distinct from plain text search; a default-index fallback requires a supported API/corpus decision.
- Working assumption: Model kg_TXT as iFind-then-LIKE (documented as-built). Record FR-012/US5/SC-004 and tasks T034/T035 as a spec/doc conflict (S3, F-0708), not as a current obligation the pin fails. If the fallback returns, it applies only on the LIKE path, only to an index whose recorded graph equals the requested graph, never across graphs. Why changed: decisions.md called this Supported on spec 044 FR-012, SC-004 and PR #8. Those establish the 2026-04 feature, not that it is still wanted: the Draft spec is the only post-removal carrier, it was copied wholesale with the schema-2 amendment, and the maintainer's later kg_TXT redesign (v2.18.2, US7, docstring, generated API reference) excludes it. No source "supersedes" FR-012 explicitly either, so neither reading is supported; the assumption follows the newer, user-facing contract.
- Working assumption: Reserve `__stop__`: public BM25 entry points (`bm25_build/insert/delete/drop/upgrade`, `BM25BuildInput`, index handles, `kg_BM25`/`ivg.bm25.search`) refuse it; the embedded registry walk skips it. Model the as-built acceptance as a defect against the documented stopword list (cross-index). Moving the list to its own global is the compatible alternative mechanism.


<a id="search.bm25.scoring"></a>
[I · search.bm25.scoring]

A document's score adds up, for each query term, `IDF × tf × (k1 + 1) / (tf + k1 × (1 − b + b × length / average length))`, where `IDF = ln(1 + (N − df + 0.5) / (df + 0.5))`. The defaults are `k1 = 1.5` and `b = 0.75`.
- Documents and queries are tokenized the same way: lowercased, split at punctuation, with no stemming and a fixed list of 77 common English words left out.
- A query term counts once for each time the query repeats it.


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


<a id="search.bm25.upgrade"></a>
[I · search.bm25.upgrade]

An upgrade converts a schema-1 index to schema 2 in one pass while searches keep working.
- Writers are refused while it runs.
- A search never sees schema 2 before the document frequencies, token records and totals are complete.
- An interrupted upgrade leaves the index flagged as upgrading, so writers stay refused until it runs again; running it again finishes the conversion. On a schema-2 index without that flag it does nothing.


<a id="search.bm25.cutoff"></a>
[I · search.bm25.cutoff]

A search can skip common terms. Given a fraction f above 0, query terms whose df divided by the document count is above f are left out; with no fraction given, nothing is skipped.
- If every known query term is over the cutoff, the term with the lowest df is kept, the first in query order on a tie, so a valid query never answers with nothing.
- Terms that appear in no document are neither skipped nor kept.
- A report variant lists the skipped terms once each, in sorted order, and says whether the fallback applied.
- A schema-1 index ignores the cutoff and reports nothing skipped.
- A fraction outside 0 to 1 is refused.

- Working assumption: Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact.


## Fusion


<a id="search.fusion"></a>
[I · search.fusion]

Hybrid search fuses a vector ranking and a text ranking by reciprocal rank. A result scores `1 / (c + rank)` in each leg where it appears, those scores add up, and the answer is the top k by fused score.
- Entry points that offer a default use `c = 60`.
- An empty text query skips the text leg.

- Working assumption: Preserve each current text corpus and rank rule until one common corpus is chosen; common fusion arithmetic alone cannot settle text ranking.
- Working assumption: Unchanged: the reviewed ranking contract is the best k of the scored candidate set with defined ties; the documented set-order truncation is the baseline (now confirmed live).
- Working assumption: Preserve and test each surface's rule, including missing-rank handling and which text list it reads; document that the engine method and the SQL procedure of the same name differ. Introduce a single formula only with a versioned contract. Same as decisions.md.


<a id="search.fusion.same_graph"></a>
[I · search.fusion.same_graph]

Every leg of a fusion answers the same graph, and the legs are matched on both graph and node ID.
- On a namespace with several graphs, a Cypher fusion that names no graph is refused.


<a id="search.fusion.failed_leg"></a>
[I · search.fusion.failed_leg]

A leg that fails must be reported as a failure that names the leg, not treated as an empty ranking.

- Today `HybridSearchFusion.multi_modal_search` raises a text failure, but logs and drops a failed vector or graph leg. A successful empty leg stays in its `search_modes`; a failed leg is absent, so a returned ranking can be incomplete. This is the inherited F-0709 departure from the rule.


<a id="search.fusion.python"></a>
[D · search.fusion.python]

The exported Python `RRFFusion.fuse_results` uses each entity's first position in each list, starting at one, and adds nothing for a missing entity. It ignores the providers' score magnitudes, returns each entity once in descending fused score, and promises no order between tied scores.

- `HybridSearchFusion.multi_modal_search` fuses the legs that completed and returns at most k entities with their fused rank and each retained leg's first score and position. A successful graph expansion is another ranked leg.
- These Python helpers' shipped behavior is settled; whether to keep them as supported public API is [open](../../Verus_verification/open_questions.md#HD-0705).

- Working assumption: Treat the three as compatibility surfaces and qualify each: RRFFusion is a pure standard-RRF helper (document that its rule differs from engine `kg_RRF_FUSE`, HD-0702); HybridSearchFusion is de facto public (migration guide) and graph-scoped; TextSearchEngine is exported but reads every graph and its document search cannot reach the IVG Schema, so it is not a supported reader of graph-scoped data. Prefer deprecation with migration advice (to `kg_TXT` / `bm25_search`) or a `graph=` argument; do not remove without a compatibility decision.


## What erasure removes from search stores


<a id="search.erasure"></a>
[I · search.erasure]

[Erasing a graph](erasure.g5.md#erasure.scope) removes its search content, so no later search answers with erased content. Other graphs' vectors stay untouched, even where they share node IDs.
- The graph's vectors in its routes and in the original tables, with its edge vectors.
- The documents that plain text search reads.
- Its routed tables and their registry rows, as [the erase's route handling](erasure.g5.md#erasure.atomic.routes) describes.
- Erasing every graph also clears the whole registry, so no table keeps an identity for vectors that no longer exist.
- Its content in named search indexes, as [the index rule](#search.erasure.indexes) describes.


<a id="search.erasure.indexes"></a>
[I · search.erasure.indexes]

Erasing a graph also removes its content from every BM25 index recorded for that graph, postings and token records. After the erase, no such index answers with an erased node, even when a node with the same ID is created again.

- VecIndex, PLAID and IVF indexes record no graph. Erasing every graph empties them; what a single-graph erase must do to them is [open](../../Verus_verification/open_questions.md#search.erasure.indexes.graphless).
- Erasing every graph empties every named index, so a restore that replaces the database starts from empty indexes before it loads the archive's.
- Ordinary node deletes are different: the caller keeps indexes in step with those ([index upkeep](#search.scope.indexes.upkeep)).

- Working assumption: Unchanged: model retained index contents as observable after erasure unless purged; graph-owned indexes require invalidation or deletion on erase; caller-fed indexes need an explicit owner/exposure statement. Refined with the graph-derived (IVF) vs caller-fed (VecIndex, PLAID) split.
- Working assumption: Treat graphless indexes as derived data requiring a rebuild after erasure.

## Metadata

### search.embedding

- uncertain
- Sources: [ADR-0006](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md), [CHANGELOG v3.2.0](../../../CHANGELOG.md#L4371-L4440), [CONTEXT.md glossary](../../../CONTEXT.md#L154-L157), [stage-A notes](../../uplift/ivg-verus-initial/intent/search.md#capabilities), live tests [registry](../../../tests/integration/test_embedding_registry_e2e.py) and [refusal](../../../tests/integration/test_embedding_identity_refusal_e2e.py)
- Children: [Registry](#search.embedding.registry), [Model key](#search.embedding.model_key), [Width](#search.embedding.width), [Check on write](#search.embedding.check_on_write), [Claim](#search.embedding.claim), [Other model](#search.embedding.other_model), [May an undeclared writer add vectors to the default graph's table after a model has claimed it?](../../Verus_verification/open_questions.md#q-srch-002), [Queue](#search.embedding.queue)
- agent
- data-integrity, user-facing-behavior
- test-coverage

Open questions: [May an undeclared writer add vectors to the default graph's table after a model has claimed it?](../../Verus_verification/open_questions.md#q-srch-002)

### search.embedding.registry
- Sources: [ADR-0006 decision and context](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md#L7-L54), [registry DDL](../../../iris_vector_graph/_engine/schema.py#L143-L160), [test_embedding_registry_e2e.py](../../../tests/integration/test_embedding_registry_e2e.py)
- Expands: [Embedding identity](#search.embedding)
- Superseded in part: ADR-0006 says `graph_id` is reserved and read by nothing. Since v4.0.0 it is real, and the registry also names each route ([CHANGELOG v4.0.0](../../../CHANGELOG.md#L4161-L4183)).
- agent
- architecture-decision
- test-coverage

### search.embedding.model_key
- Sources: [normalize_model_key and MECHANISMS](../../../iris_vector_graph/embedding_identity.py#L31-L72), [conflicts](../../../iris_vector_graph/embedding_identity.py#L180-L219)
- Expands: [Embedding identity](#search.embedding)
- Note: stated only in code docstrings citing spec 226, which is not in the repository.
- agent
- data-integrity

### search.embedding.width

- design-verified
- Sources: query width before search: [`iris_vector_graph/_engine/vector.py::_assert_query_width`](../../../iris_vector_graph/_engine/vector.py#L455-L502), called first in [`::kg_KNN_VEC`](../../../iris_vector_graph/_engine/vector.py#L504-L545) (route lookup `:536-538`, check `:542`, first statement `:557`), unit tests [test_227_query_width.py](../../../tests/unit/test_227_query_width.py#L100-L132), live `tests/e2e/test_460_r223_vector_width_e2e.py`; [ADR-0005 consequences](../../../docs/adr/0005-vector-width-is-not-declared-in-to-vector.md#L62-L73), [reconcile_recorded_dimensions](../../../iris_vector_graph/_engine/schema.py#L1688-L1710), [reused-route width check](../../../iris_vector_graph/_engine/embeddings.py#L589-L641), [USER_GUIDE on setup and width](../../../docs/USER_GUIDE.md#L897-L910), [test_227_two_models.py](../../../tests/e2e/test_227_two_models.py), query width: [ADR-0005](../../../docs/adr/0005-vector-width-is-not-declared-in-to-vector.md#L7-L48), [query width check](../../../iris_vector_graph/_engine/vector.py#L455-L502), [test_to_vector_width_regression_e2e.py](../../../tests/integration/test_to_vector_width_regression_e2e.py)
- Playbook: [VEC-X5.5](../../../experiment/playbook-completion/ontology/06-vectors.md#L184)
- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `width_check`, `theorem_direct_guard_no_score` and `theorem_whole_raw_row_four_query_three_no_scoring` derive route-before-width-before-score from raw rows, query characters and catalog cells for the three node KNN entry points. Nested JSON/strings/non-numeric elements are counted by the modeled outer-array lexer; syntax does not establish vector-element validity. JSON/library correspondence is finite observation, catalog output is a heuristic rather than physical-width truth, and numeric kernels/raw identifier carriers remain providers. Existing G search and P route kernels remain substantive typed routing hits; this does not establish every vector/edge/store/protocol surface.
- Expands: [Embedding identity](#search.embedding)
- Observed divergence: several query paths, such as [edge_vector_search](../../../iris_vector_graph/_engine/vector.py#L360-L370), declare the query's own length in `TO_VECTOR`, which keeps ADR-0005's intent but not its letter.
- agent
- architecture-decision, data-integrity, operations

State machines: [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.embedding.width.raw-helpers
- Expands: [parent](#search.embedding.width)
- agent
- manual-check-review

Findings: [Should the low-level vector helper refuse a vector of the wrong width?](../../Verus_verification/open_questions.md#HD-1704).

Audit sources, current behavior, options, costs and settling evidence: [question review](../../Verus_verification/audits/register-20261115/question-review.md#HD-1704).

Audit (HD-1704): Existing authority: The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-1704).

### search.embedding.check_on_write
- Sources: [enforce_embedding_identity](../../../iris_vector_graph/_engine/schema.py#L1354-L1396), [store_embedding](../../../iris_vector_graph/_engine/embeddings.py#L942-L1025), [store_embeddings](../../../iris_vector_graph/_engine/embeddings.py#L1028-L1115), [offered unknown identity](../../../iris_vector_graph/embedding_identity.py#L79-L98), [CHANGELOG v3.2.0](../../../CHANGELOG.md#L4371-L4440)
- Expands: [Embedding identity](#search.embedding)
- Observed divergence: the check passes when [the registry cannot be read](../../../iris_vector_graph/_engine/schema.py#L1033-L1084), and [the IRIS queue worker](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L256-L345) writes default-graph entries without it (F8, F11 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- agent
- data-integrity
- test-coverage

Findings: [The embedding queue checks identity against the wrong table, and its IRIS worker writes default-graph entries with no identity check](../../Verus_verification/bugs_issues.md#bug-srch-006); [Embedding identity enforcement allows the write when the registry read fails](../../Verus_verification/bugs_issues.md#bug-srch-012); [Check embedding identity against the registry row the route lookup already read](../../Verus_verification/design_simplification.md#simp-srch-002)

### search.embedding.claim
- Sources: [ADR-0006 on the conditional first-writer claim](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md#L51-L54), [set_embedding_identity](../../../iris_vector_graph/_engine/schema.py#L1086-L1220), [concurrent claim test](../../../tests/integration/test_embedding_registry_e2e.py#L608-L681), [force test](../../../tests/integration/test_embedding_registry_e2e.py#L389-L398)
- Expands: [Embedding identity](#search.embedding)
- agent
- data-integrity, operations
- test-coverage

Findings: [Claiming the default embedding table for a model that already has a default-graph route makes that model's stored vectors unreadable](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-007)


The body's earlier "first writer that declares a model claims the table" was ADR-0006's wording from before routing; review round 3 R3-reader H4 aligned it with the code ([schema.py set_embedding_identity](../../../iris_vector_graph/_engine/schema.py#L1086-L1220), [setup claim](../../../iris_vector_graph/_engine/schema.py#L1485-L1513), [_read_route](../../../iris_vector_graph/_engine/embeddings.py#L403-L416) matches `model_key` only).

### search.embedding.other_model

- design-verified
- Sources: [CHANGELOG v4.0.0](../../../CHANGELOG.md#L4046-L4060), [routed tables](../../../CHANGELOG.md#L4161-L4183), [USER_GUIDE "Several models"](../../../docs/USER_GUIDE.md#L946-L960), [setup claim](../../../iris_vector_graph/_engine/schema.py#L1485-L1513), [test_227_two_models.py](../../../tests/e2e/test_227_two_models.py)
- Playbook: [VEC-B1.8](../../../experiment/playbook-completion/ontology/06-vectors.md#L86)
- Verus: active (public M13): `G-search` (as-built) [`search.rs`](../../Verus_verification/models/search/search.rs) `theorem_store_routes_and_refuses`, `theorem_identity_check_ignores_ledger`, witness `witness_identity_fail_open`. Overlapping: the playbook's `vec_route_batch` explorer (checks width, not a distinct model identity together with another graph's write).
- Expands: [Embedding identity](#search.embedding)
- Note: the glossary's "refused rather than mixed in" ([CONTEXT.md](../../../CONTEXT.md#L154-L157)) was added on 2026-11-04 (commit `267aaff1`), after the 4.0.0 routing release. It restates ADR-0006 without reconciling it with routing. The 4.0.0 decision governs writes that name a model key, and the user guide re-affirms that a declared different model on one table is refused, so this block reads the glossary as "never mixed" (review round 1, R1-9).
- agent
- uncertain
- architecture-decision, user-facing-behavior

Findings: [Search documents are not reconciled with graph-scoped routing or with the BM25 corpus](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-010)

The setup-versus-routing case is stage-A open question Q2 ([intent notes](../../uplift/ivg-verus-initial/intent/search.md#L319)); setup refuses at [schema.py](../../../iris_vector_graph/_engine/schema.py#L1211-L1215). Added by review round 3 R3-reader M12.

State machines: [search](../../Verus_verification/models/search/manifest.json)

### search.embedding.queue

- uncertain
- Sources: [enqueue_for_embedding](../../../iris_vector_graph/_engine/embeddings.py#L1803-L1874), [process_embed_queue docstring and worker check](../../../iris_vector_graph/_engine/embeddings.py#L1898-L2016), [ClaimPendingBatch rationale](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L105-L136), [IRIS worker: a failed write is an error, not done](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L318-L333), [test_embed_queue_identity_e2e.py](../../../tests/integration/test_embed_queue_identity_e2e.py)
- Expands: [Embedding identity](#search.embedding)
- Children: [May two workers process the queue at the same time, and must an entry be marked done only after its vector is committed?](../../Verus_verification/open_questions.md#search.embedding.queue.processing)
- Observed divergence: enqueueing checks the default graph's original table whatever the target graph, and the IRIS worker writes default-graph entries there whatever their model (F8 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)). The IRIS worker also marks an entry done when its embedding statement fails to prepare or returns no row ([ProcessBatch](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L306-L330)).
- agent
- data-integrity, operations
- test-coverage

Findings: [The embedding queue checks identity against the wrong table, and its IRIS worker writes default-graph entries with no identity check](../../Verus_verification/bugs_issues.md#bug-srch-006)

Open questions: [May two embed queue workers run at once?](../../Verus_verification/open_questions.md#HD-0604), [May two workers process the queue at the same time, and must an entry be marked done only after its vector is committed?](../../Verus_verification/open_questions.md#search.embedding.queue.processing)

### search.routes
- Sources: [CHANGELOG v4.0.0 routed tables](../../../CHANGELOG.md#L4161-L4183), [EmbeddingRoute and resolve_route](../../../iris_vector_graph/_engine/embeddings.py#L35-L301), [route preference](../../../iris_vector_graph/_engine/embeddings.py#L107-L118), [test_227_two_models.py](../../../tests/e2e/test_227_two_models.py), edge vectors: [store_edge_embedding](../../../iris_vector_graph/_engine/embeddings.py#L1117-L1205), [edge_vector_search](../../../iris_vector_graph/_engine/vector.py#L333-L398), [migration guide](../../../docs/migration/v4.0.0.md#L553-L598)
- Children: [No fallback](#search.routes.no_fallback), [Create on write](#search.routes.create_on_write), [Orphan](#search.routes.orphan), [Route cache](#search.routes.cache)
- Observed divergence: the registry does not stop two tables answering one pair, so vectors written to a routed table before setup claims the original table can be stranded (F9). The upgrade puts named-graph edge vectors in `kg_EdgeEmbeddings` with no route row, where edge search for that graph does not look (F10). Both are in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings).
- agent
- architecture-decision, data-integrity
- test-coverage

Findings: [Claiming the default embedding table for a model that already has a default-graph route makes that model's stored vectors unreadable](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-007); [Named-graph edge vectors placed by the 4.0.0 migration cannot be found by edge vector search](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-009)

### search.routes.no_fallback

- design-verified
- Sources: [_route_for_read](../../../iris_vector_graph/_engine/embeddings.py#L652-L679), [_is_default_pair](../../../iris_vector_graph/_engine/embeddings.py#L743-L753), [unrouted pair test](../../../tests/e2e/test_227_two_models.py#L204-L215); [`iris_vector_graph/_engine/vector.py::kg_KNN_VEC`](../../../iris_vector_graph/_engine/vector.py#L535-L538), [`iris_vector_graph/_engine/embeddings.py::get_embedding`](../../../iris_vector_graph/_engine/embeddings.py#L1694-L1745); unit tests [`test_an_unrouted_pair_still_reads_empty_rather_than_raising`](../../../tests/unit/test_227_query_width.py#L122-L132), [test_227_routed_reads.py](../../../tests/unit/test_227_routed_reads.py#L149-L183)
- Playbook: [VEC-B4](../../../experiment/playbook-completion/ontology/06-vectors.md#L168)
- Verus: `search` (as-built) [`search.rs`](../../Verus_verification/models/search/search.rs) `read_route` / `read_table` (route absence answers nothing; controls in its [model.json](../../Verus_verification/models/search/model.json))
- Verus (raw workflow extension): [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `resolve` and `theorem_whole_missing_raw_pair_returns_quiet_empty` derive scoped raw row selection, decoding, default/compatibility exceptions and named absence before any seed/vector/scoring effect. Stable provider row order and already-normalized identifier keys are explicit; no new route DDL/transaction or identity-codec theorem is inferred.
- Expands: [Routes](#search.routes)
- Note: the vector case of [no fall-through](../concepts/graph-scope.g5.md#graph.no_fallthrough).
- agent
- data-integrity, user-facing-behavior

State machines: [search](../../Verus_verification/models/search/manifest.json), [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.routes.cache

- design-verified

- Sources: [cache key and clock](../../../iris_vector_graph/_engine/embeddings.py#L307-L344), [invalidation](../../../iris_vector_graph/_engine/embeddings.py#L346-L375), [raw registry reader](../../../iris_vector_graph/_engine/embeddings.py#L377-L468), [source survey](../../uplift/consolidated/iteration-10/next-vector-survey-report.md), [actual native miss then another-engine creation](../../uplift/consolidated/iteration-11/root-vector-native.json)
- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `key`, `cached`, `evict`, `resolve`, `invalidate` and `theorem_all_search_phases_keep_original_scope` derive cache key isolation, separate store/lookup timestamps, strict expiry, no negative insertion and read counts. V2 fixes registry/graph/model/node-kind/TTL from the original stable engine request across fallbacks; only provider replies and clock samples vary. Integer clock ticks preserve comparisons; arbitrary native float-clock refinement, concurrent DDL/writer correctness and universal invalidation are unproved. TTL0 bypasses lookup without clearing old entries.
- Expands: [Routes](#search.routes)
- agent
- user-facing-behavior

The strict expiration comparison permits a hit at exactly the TTL, and a positive hit does not reread the current backend row or its errors. The source caches only decoded positive rows, including their timestamp; a miss and registry-absent response are not cached. Per-engine clocks, invalidation, typed TTL and raw registry-provider behavior remain distinct from concurrent route-writer correctness. The earlier cached-absence forecast was refuted and retained, not counted as a defect.

State machines: [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.routes.create_on_write
- Sources: [_create_route and its 4.7.0 commit comment](../../../iris_vector_graph/_engine/embeddings.py#L470-L558), [per-route locks](../../../iris_vector_graph/_engine/embeddings.py#L67-L81), [_route_for_write](../../../iris_vector_graph/_engine/embeddings.py#L755-L792), [width per route test](../../../tests/e2e/test_227_two_models.py#L86-L112)
- Expands: [Routes](#search.routes)
- Observed divergence: [_create_routed_table and _attempt_route_index](../../../iris_vector_graph/_engine/schema.py#L884-L933) each commit, so the table and its index are committed before the registry row is inserted, and a failure between them leaves an [orphan](#search.routes.orphan). Correction 2 of the [reconstruction check](../../uplift/ivg-verus-initial/reconstruction-check.md#3-corrections-proposed) proposed restating the as-built order as the decision; the newest stated intent, the 4.7.0 comment in `_create_route`, is kept instead.
- agent
- architecture-decision
- test-coverage

Findings: [Route creation commits the routed table before its registry row, and an orphaned table makes every erase in the namespace fail](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-015)

### search.routes.orphan
- Sources: [Eraser orphan collection](../../../iris_src/src/Graph/KG/Eraser.cls#L100-L113), [CollectOrphanRoutes](../../../iris_src/src/Graph/KG/Eraser.cls#L1063-L1102), [drop only claimed routes](../../../iris_src/src/Graph/KG/Eraser.cls#L276-L299), [reused-route width check](../../../iris_vector_graph/_engine/embeddings.py#L589-L641), [test_227_orphan_route_erase.py](../../../tests/integration/test_227_orphan_route_erase.py)
- Expands: [Routes](#search.routes)
- Note: correction 2 proposed an invariant that no orphan ever exists, on the grounds that an orphan makes every erase fail. Since 2026-09-22 the Eraser empties orphans found in the catalog, and the live test above shows an erase succeeding with one. The `_create_route` comment repeating the older claim is stale. Orphans can still arise, so this block records how they are treated.
- agent
- architecture-decision, data-integrity
- test-coverage

Findings: [Route creation commits the routed table before its registry row, and an orphaned table makes every erase in the namespace fail](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-015)

### search.knn

- design-verified
- Sources: [kg_KNN_VEC](../../../iris_vector_graph/_engine/vector.py#L504-L619), [_attempt_route_index](../../../iris_vector_graph/_engine/schema.py#L911-L933), [CHANGELOG v4.0.0 routed tables and HNSW](../../../CHANGELOG.md#L4161-L4183), [each graph's search test](../../../tests/e2e/test_227_two_models.py#L187-L203)
- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_primary_generic_failure_really_calls_optimized`, `theorem_optimized_double_failure_really_calls_client`, typed score readers and raw CSV shape/effect relations cover the primary/optimized/client node-search chain. The source model retains both the seed-identity-loss counterexample and the unknown-width mixed-error empty answer. SQL/NumPy numeric replies are provider inputs, with finite actual readers and predicates executed in735 binding comparisons; no cosine/ANN/numerical or native-body theorem follows. Nonstring/raw numeric carriers, connection/cursor allocation and exact exception text remain qualified.
- Note: added for gap G18 of the [reconstruction check](../../uplift/ivg-verus-initial/reconstruction-check.md#1b-gaps-a-builder-would-hit). The order of equal scores is not specified, and recall of the approximate index is recorded per route only when measured.
- agent
- user-facing-behavior

Findings: [ADR-0005 forbids the three-argument TO_VECTOR for query vectors, which four call sites use](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-011)

Observed fallback violation: primary seed lookup keeps its exclusion only in local SQL, then a generic scoring failure forwards the expanded literal without the original node ID. [Controlled actual native/provider cases](../../uplift/consolidated/iteration-11/root-seed-native.json) return the seed at k1, while normal seed requests return the peer and literal requests may lawfully return the seed. The injected fault is not an organic outage; [independent review](../../uplift/consolidated/iteration-11/review-seed-intent.md) confirms the existing exclusion intent and distinct root. [bug-plt-105](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-105); the exclusion requirement remains unchanged.

Audit reproduction: [F-0610](../../Verus_verification/bugs_issues.md#F-0610) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [The SQL kg_KNN_VEC answers no rows, without error, for a graph whose vectors are under a declared model](../../Verus_verification/bugs_issues.md#F-0610).

Audit reproduction: [F-C0602](../../Verus_verification/bugs_issues.md#F-C0602) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [SQL kg_KNN_VEC answers a node once per label, so a multi-label node takes several of the k places](../../Verus_verification/bugs_issues.md#F-C0602).

State machines: [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.knn.threshold

- design-verified

- Sources: [edge_vector_search](../../../iris_vector_graph/_engine/vector.py#L333-L416), [vector_search](../../../iris_vector_graph/_engine/vector.py#L1169-L1288), [threshold tests](../../../tests/unit/test_vector_score_threshold.py), [live tests, inspected only](../../../tests/integration/test_vector_score_threshold_live.py)
- Verus: [vector_threshold](../../Verus_verification/models/vector_threshold/NOTES.md), as-built scaled-integer threshold `build`, `admits`, `search`. Valid finite numeric conversion, cosine scores, ranked SQL provider and dialect preparation are premises; SQLite comparison is adapted-provider evidence, not IRIS execution.
- Expands: [vector search](#search.knn)
- agent
- user-facing-behavior

State machines: [vector threshold](../../Verus_verification/models/vector_threshold/manifest.json)

### search.scope

- design-verified
- Sources: [CHANGELOG v4.0.0 keyword graph](../../../CHANGELOG.md#L4184-L4198), [graph ID not an authorisation boundary](../../../CHANGELOG.md#L4366-L4370), [graph_scope_predicate](../../../iris_vector_graph/routing.py#L81-L100), [kg_KNN_VEC](../../../iris_vector_graph/_engine/vector.py#L504-L619), [test_230_scope_isolation.py](../../../tests/e2e/test_230_scope_isolation.py), SQL procedures: [KNOWN_ISSUES](../../../docs/KNOWN_ISSUES.md#L702-L714), [generated kg_KNN_VEC](../../../iris_vector_graph/schema.py#L2440-L2483), [test_460_r265_vector_procedures_route_e2e.py](../../../tests/e2e/test_460_r265_vector_procedures_route_e2e.py)
- Verus (node KNN slice): [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_all_search_phases_keep_original_scope` keeps original registry, normalized graph/model and TTL across every phase, with node kind fixed. Raw row filters and actual SQLite table/graph/label predicates corroborate that selected slice; fusion, other index dispatch, GraphQL and native SQL procedure scope are not transferred from it.
- Children: [Indexes](#search.scope.indexes)
- agent
- security, user-facing-behavior

Findings: [TextSearchEngine.search_documents is public, ignores graphs and very likely always fails](../../Verus_verification/bugs_issues.md#bug-srch-013)

State machines: [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.scope.indexes

- uncertain
- Sources: [BM25 Build graph parameter](../../../iris_src/src/Graph/KG/BM25Index.cls#L93-L175), [index graph scopes and fusion leg choice](../../../iris_vector_graph/_engine/vector.py#L150-L225), [scoped legs test](../../../tests/e2e/test_230_retrieval_scope.py#L505-L548), [mocked leg-choice tests](../../../tests/unit/test_460_rrf_leg_prefers_graphs_own_index.py)
- Expands: [Graph scope](#search.scope)
- Children: [Upkeep](#search.scope.indexes.upkeep), [IVF build admission](#search.scope.indexes.ivf)
- Observed divergence: a Cypher BM25 search under a named graph never compares the index's recorded graph (F7), and an IVF index records no graph. The engine takes its list of indexes and their graphs once, so fusion does not see a dropped index or one another process built (F6). Both are in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings).
- agent
- data-integrity, architecture-decision
- test-coverage

Findings: [Fusion chooses indexes from a snapshot taken when the engine started](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-011), [A BM25 index built before 4.0.0 reports the default graph, so the default graph's fusion reads another graph's documents as its own](../../Verus_verification/bugs_issues.md#bug-srch-017)


The pre-4.0.0 index case is from [BM25Index.cls](../../../iris_src/src/Graph/KG/BM25Index.cls#L607-L611) ("a stale index is indistinguishable here; rebuild it") and the fusion's index choice in [vector.py](../../../iris_vector_graph/_engine/vector.py#L164-L206) (helper reading, review round 3 R3-reader M25; the fusion part was not re-checked).

Open questions: [May an index build be seen half-done, and may a stopped build leave a partial index?](../../Verus_verification/open_questions.md#HD-0602)

### search.scope.indexes.upkeep
- Sources: [USER_GUIDE: bm25_insert and bm25_delete keep an index current](../../../docs/USER_GUIDE.md#L893-L896), [index protocol, the only generic insert caller](../../../iris_vector_graph/index_protocol.py#L31-L60), [index wrappers](../../../iris_vector_graph/_engine/vector.py#L1548-L1879), [VecIndex usage](../../../iris_src/src/Graph/KG/VecIndex.cls#L1-L18)
- Expands: [Indexes](#search.scope.indexes)
- Note: added from correction 6 of the [reconstruction check](../../uplift/ivg-verus-initial/reconstruction-check.md#3-corrections-proposed) as a D, because the user guide documents caller upkeep for ordinary writes and deletes. That guide does not govern erasure, which [the erasure rule](#search.erasure.indexes) covers. No product code calls these indexes' insert or delete from a node write or delete path.
- agent
- architecture-decision, operations

### search.scope.indexes.ivf

- design-verified

- Sources: [public IVF build contract and admission](../../../iris_vector_graph/_engine/vector.py#L1880-L1948), [routed vector selection and build](../../../iris_vector_graph/_engine/vector.py#L1949-L2027), [existing route-build tests](../../../tests/unit/test_227_ivf_route.py), [source survey](../../uplift/consolidated/iteration-10/next-vector-survey-report.md), [native no-route refusal](../../uplift/consolidated/iteration-11/root-vector-native.json)
- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_no_route_refuses_before_vector_read`, `theorem_empty_ids_after_cursor_before_select`, `theorem_malformed_info_after_build_keeps_local_maps` and `theorem_valid_info_publishes_after_native_prefix` derive the separate build admission/effect order from raw arguments, route rows and provider replies. The ordinary explicit text/metric/positive-int rule is modeled; generic Pydantic coercion is not. External Build/AddBatch/Finalize/Info effects can survive a later error; only local publication waits for syntax-valid Info. Opaque decoded Info content, base64/float32/clustering/native index correctness and rollback are outside this contract.
- Expands: [Graph-scoped indexes](#search.scope.indexes)
- agent
- user-facing-behavior

This owns build admission, separately from an absent pair's empty search answer. The existing search routing model and prepared route fixtures do not establish the raw build refusal/effect order. A successful one-vector source/provider fixture exercises Build/AddBatch/Finalize/Info carriers; root's native panel only confirms the no-route refusal. Native clustering, index contents, later search correctness, post-Build failures and rollback are not established by admission.

Audit reproduction: [F-0607](../../Verus_verification/bugs_issues.md#F-0607) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [The IVF index's 'cosine' metric is an unnormalised dot product](../../Verus_verification/bugs_issues.md#F-0607).

State machines: [vector admission](../../Verus_verification/models/vector_admission/manifest.json)

### search.vecindex

- Sources: [API reference, vec_*](../../../docs/API_REFERENCE.md#L1150-L1226), [Graph.KG.VecIndex](../../../iris_src/src/Graph/KG/VecIndex.cls), [engine wrappers](../../../iris_vector_graph/_engine/vector.py#L1548-L1650)
- Verus: [vec_index](../../Verus_verification/models/vec_index/NOTES.md) `theorem_insert_found_by_identical_query`, `theorem_build_places_every_vector`, `theorem_reinsert_inflates_count`, `theorem_distinct_inserts_count_vectors`, `theorem_recreate_zero_count_keeps_vectors`, `theorem_insert_overwrites_dim`, `theorem_drop_empties_search`, `theorem_score_mapping` (as built)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-27/vecindex-PAIRS.md)
- agent
- user-facing-behavior

Findings: [Vector index stores do not check width or duplicates](../../Verus_verification/bugs_issues.md#F-0608); [Creating a VecIndex again under the same name reports a count of 0 while its vectors stay searchable](../../Verus_verification/bugs_issues.md#bug-srch-101); [The API reference says a vector inserted into a VecIndex is searchable only after the next vec_build](../../Verus_verification/bugs_issues.md#bug-srch-102)

State machines: [vec index](../../Verus_verification/models/vec_index/manifest.json)

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
- Note: only mocked unit tests exercise placement ([test_227_quarantine_api.py](../../../tests/unit/test_227_quarantine_api.py)).
- agent
- operations, data-integrity

### search.bm25

- uncertain
- Sources: [CONTEXT.md glossary](../../../CONTEXT.md#L130-L153), [spec 044](../../../specs/044-bm25-index/spec.md), [spec 044 FR-020 and FR-021](../../../specs/044-bm25-index/spec.md#L166-L167), [BM25Index.cls](../../../iris_src/src/Graph/KG/BM25Index.cls#L1-L33), [test_044_bm25_incremental.py](../../../tests/integration/test_044_bm25_incremental.py)
- Children: [Scoring](#search.bm25.scoring), [Query-time IDF](#search.bm25.query_time_idf), [Counts](#search.bm25.counts), [Incremental cost](#search.bm25.incremental), [Write lock](#search.bm25.write_lock), [Schema](#search.bm25.schema), [Upgrade](#search.bm25.upgrade), [Common-term cutoff](#search.bm25.cutoff), [May a BM25 search observe an index write that is still in progress?](../../Verus_verification/open_questions.md#q-srch-003), [Should plain text search use a BM25 index named "default" when one exists?](../../Verus_verification/open_questions.md#q-srch-004)
- Note: spec 044 is still marked Draft. Its 2026-10-08 and 2026-10-09 clarifications record a request from the opsreview consumer, secondhand, with answers attributed to no named human.
- agent
- user-facing-behavior
- test-coverage

Audit reproduction: [F-C0715](../../Verus_verification/bugs_issues.md#F-C0715) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [bm25_search rewrites document ids: its leading-dot patch runs over the whole answer, so an id holding ':.5', ',.7' or '[.9' comes back as ':0.5', ',0.7', '[0.9'](../../Verus_verification/bugs_issues.md#F-C0715).

Open questions: [Is spec 044's kg_TXT-to-BM25 fallback still wanted?](../../Verus_verification/open_questions.md#HD-0703), [Is `__stop__` a reserved BM25 index name?](../../Verus_verification/open_questions.md#HD-0704), [May a BM25 search observe an index write that is still in progress?](../../Verus_verification/open_questions.md#q-srch-003), [Should plain text search use a BM25 index named "default" when one exists?](../../Verus_verification/open_questions.md#q-srch-004)

### search.bm25.scoring
- Sources: [spec 044 FR-003 and FR-004](../../../specs/044-bm25-index/spec.md#L149-L150), [USER_GUIDE BM25 text search and the stopword list](../../../docs/USER_GUIDE.md#L854-L896), [InitStopwords](../../../iris_src/src/Graph/KG/BM25Index.cls#L41-L50), [bm25_build docstring](../../../iris_vector_graph/_engine/vector.py#L1749-L1785), [formula test](../../../tests/integration/test_044_bm25_incremental.py#L401-L413)
- Expands: [BM25 index](#search.bm25)
- Evidence: [native scores equal the formula within 1e-6 across build and incremental writes](../../uplift/consolidated/iteration-22/bm25-PAIRS.md); no formal contract (IDF uses ln)
- agent
- user-facing-behavior
- test-coverage

### search.bm25.query_time_idf
- Sources: [spec 044 FR-017](../../../specs/044-bm25-index/spec.md#L163), [ADR-0007](../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [SearchCore](../../../iris_src/src/Graph/KG/BM25Index.cls#L236-L312)
- Expands: [BM25 index](#search.bm25)
- Note: supersedes spec 044 FR-008's allowance for stale IDF. A schema-1 index still scores with the IDF stored at write time until it is upgraded.
- agent
- architecture-decision
- test-coverage

### search.bm25.counts

- design-verified
- Sources: [spec 044 FR-016 and FR-018](../../../specs/044-bm25-index/spec.md#L162-L164), [Insert and RemoveDoc](../../../iris_src/src/Graph/KG/BM25Index.cls#L412-L493), [df test](../../../tests/integration/test_044_bm25_incremental.py#L157-L203)
- Expands: [BM25 index](#search.bm25)
- Verus: [bm25_counts.rs](../../Verus_verification/models/bm25_counts/bm25_counts.rs) `theorem_insert_consistent`, `theorem_remove_consistent`, `theorem_empty_replacement_removes`, `theorem_absent_delete_is_noop` and `theorem_replace_keeps_n`; [scope](../../Verus_verification/models/bm25_counts/NOTES.md). Sequential writes only; the concurrent build below is outside the model.
- Evidence: [frozen predictions and native scoring/count observations](../../uplift/consolidated/iteration-22/bm25-PAIRS.md)
- Observed divergence: a full build running at the same time as an insert can leave df and the document count disagreeing (F2 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- agent
- data-integrity

Findings: [Building or dropping a BM25 index while documents are inserted leaves its counters inconsistent](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-003)

State machines: [bm25 counts](../../Verus_verification/models/bm25_counts/manifest.json)

### search.bm25.incremental
- Sources: [spec 044 FR-015](../../../specs/044-bm25-index/spec.md#L161), [spec 044 clarification 2026-10-08](../../../specs/044-bm25-index/spec.md#L299-L312), [cost tests](../../../tests/integration/test_044_bm25_incremental.py#L204-L231)
- Expands: [BM25 index](#search.bm25)
- agent
- operations
- test-coverage

Findings: [A BM25 delete issued while a Build runs is lost, and bug-srch-003's proposed repair does not prevent it](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-016)

### search.bm25.write_lock

- uncertain
- Sources: [ADR-0007](../../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md), [spec 044 FR-019](../../../specs/044-bm25-index/spec.md#L165), [LockWrite and Insert](../../../iris_src/src/Graph/KG/BM25Index.cls#L380-L493), [lock and rollback tests](../../../tests/integration/test_044_bm25_incremental.py#L491-L535), caller transaction: 4.6.4 rule "an IVG write never commits or rolls back its caller's transaction" (commit `aad50087`, [_write_txn.py](../../../iris_vector_graph/_write_txn.py#L1-L30))
- Expands: [BM25 index](#search.bm25)
- Observed divergence: a full build and a drop take no lock (F2). The Catch of `Insert` and `Delete` runs a bare `TRollback`, which ends every transaction level: [a native probe](../../Verus_verification/receipts/native/search_bm25_caller_txn_rollback.json) saw a failed `bm25_insert` take the level from 1 to 0, and the node the caller had created earlier in that transaction was gone after its commit reported success (F3 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings); review round 1, R1-2).
- agent
- architecture-decision, data-integrity
- test-coverage

Findings: [A failed BM25 insert or delete rolls back the caller's whole transaction](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-002); [Building or dropping a BM25 index while documents are inserted leaves its counters inconsistent](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-003); [A BM25 delete issued while a Build runs is lost, and bug-srch-003's proposed repair does not prevent it](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-016)

Open questions: [Must a BM25 Build (and Drop) exclude writers and be all-or-nothing?](../../Verus_verification/open_questions.md#HD-0701), [Should whether a write joins the caller's transaction depend on how the engine was opened?](../../Verus_verification/open_questions.md#structure.write.engine-connection)

### search.bm25.schema
- Sources: [spec 044 FR-022](../../../specs/044-bm25-index/spec.md#L168), [RequireWritable](../../../iris_src/src/Graph/KG/BM25Index.cls#L383-L394), [CHANGELOG v4.2.0 BM25 schema 2](../../../CHANGELOG.md#L3374-L3400), [schema tests](../../../tests/integration/test_044_bm25_incremental.py#L270-L293)
- Expands: [BM25 index](#search.bm25)
- Note: a full build is not refused on a schema-1 index; it replaces the index as schema 2.
- agent
- architecture-decision, operations
- test-coverage

### search.bm25.upgrade
- Sources: [spec 044 FR-023](../../../specs/044-bm25-index/spec.md#L169), [Upgrade](../../../iris_src/src/Graph/KG/BM25Index.cls#L516-L581), [upgrade tests](../../../tests/integration/test_044_bm25_incremental.py#L294-L400)
- Expands: [BM25 index](#search.bm25)
- Observed divergence: a second upgrade waiting on the lock does not recheck whether the index is already converted, and re-runs on schema 2 (F4 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- agent
- operations, data-integrity
- test-coverage

Findings: [A second or re-run BM25 upgrade rebuilds an index that is already upgraded, and searches answer nothing meanwhile](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-004)

### search.bm25.cutoff

- uncertain
- Sources: [spec 044 session 2026-10-09](../../../specs/044-bm25-index/spec.md#L314-L334), [CONTEXT.md](../../../CONTEXT.md#L142-L147), [cutoff code](../../../iris_src/src/Graph/KG/BM25Index.cls#L210-L293), [bm25_search](../../../iris_vector_graph/_engine/vector.py#L1786-L1839), [test_044_bm25_max_df.py](../../../tests/integration/test_044_bm25_max_df.py)
- Expands: [BM25 index](#search.bm25)
- agent
- user-facing-behavior, operations
- test-coverage

Findings: [In which order must the common-term cutoff list the terms it skipped?](../../Verus_verification/open_questions.md#q-srch-005)

Audit (q-srch-005): Open owner decision. Working assumption (agent, unratified): Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#q-srch-005).

Open questions: [In which order must the common-term cutoff list the terms it skipped?](../../Verus_verification/open_questions.md#q-srch-005)

### search.fusion

- uncertain
- Sources: [engine kg_RRF_FUSE](../../../iris_vector_graph/_engine/vector.py#L1382-L1451), [API reference](../../../docs/API_REFERENCE.md#L985-L1000), [RRFFusion](../../../iris_vector_graph/fusion.py#L21-L64), [SQL kg_RRF_FUSE](../../../iris_vector_graph/schema.py#L2526-L2560), [Cypher ivg.retrieve](../../../iris_vector_graph/cypher/translator.py#L3239-L3360), [operators default c](../../../iris_vector_graph/operators.py#L37-L44), [test_rrf_fuse_e2e.py](../../../tests/unit/test_rrf_fuse_e2e.py)
- Children: [Same graph](#search.fusion.same_graph), [Failed leg](#search.fusion.failed_leg), [Python fusion](#search.fusion.python), [Which reciprocal-rank-fusion rule is the product's?](../../Verus_verification/open_questions.md#HD-0702), [Should every fusion entry point use the same text ranking?](../../Verus_verification/open_questions.md#q-srch-006)
- Note: the live test checks result shape only. The engine method and the SQL procedure take `c` with no default.
- agent
- user-facing-behavior
- test-coverage

Findings: [The engine's fusion gives a result missing from one leg a non-zero, length-dependent score](../../Verus_verification/bugs_issues.md#bug-srch-005); [One fusion function with an explicit absent-rank rule and per-leg failure reporting](../../Verus_verification/design_simplification.md#simp-srch-001)

Audit reproduction: [bug-srch-005](../../Verus_verification/bugs_issues.md#bug-srch-005) is partial reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/components.json). This is product observation, not executable-body verification.

Open questions: [Should the vector-and-graph search keep its k best candidates?](../../Verus_verification/open_questions.md#HD-0603), [Which reciprocal-rank-fusion rule is the product's?](../../Verus_verification/open_questions.md#HD-0702), [Should every fusion entry point use the same text ranking?](../../Verus_verification/open_questions.md#q-srch-006)

### search.fusion.same_graph
- Sources: [SQL kg_RRF_FUSE join](../../../iris_vector_graph/schema.py#L2526-L2560), [ivg.retrieve scope refusal](../../../iris_vector_graph/cypher/translator.py#L3255-L3261), [test_230_retrieval_scope.py](../../../tests/e2e/test_230_retrieval_scope.py#L590-L649)
- Expands: [Fusion](#search.fusion)
- agent
- security, data-integrity
- test-coverage

Findings: [Under USE GRAPH, fusion reads a BM25 index built for another graph as this graph's](../../Verus_verification/bugs_issues.md#bug-srch-008)

### search.fusion.failed_leg

- design-verified
- Sources: [KNOWN_ISSUES](../../../docs/KNOWN_ISSUES.md#L172-L181), [text leg re-raise rationale](../../../iris_vector_graph/fusion.py#L154-L170)
- Expands: [Fusion](#search.fusion)
- Verus: [fusion_ranking](../../Verus_verification/models/fusion_ranking/NOTES.md) as-built `theorem_vector_failure_dropped_text_failure_raises`, `theorem_empty_success_is_a_retained_leg`, `theorem_graph_failure_dropped`; provider outcomes are external inputs, and catch/mode admission is derived. This models the Python wrapper's departure, not compliance with the intended failure rule.
- Observed divergence: the engine's fusion logs a failed leg and answers an empty or one-leg ranking, which `IRISGraphOperators.kg_RRF_FUSE`'s default empty query vector triggers. The known-issue entry plans the fix for 4.7.1 ([KNOWN_ISSUES](../../../docs/KNOWN_ISSUES.md#L172-L181)), and the [API reference](../../../docs/API_REFERENCE.md#L999) still documents the log-and-continue behaviour.
- agent
- user-facing-behavior

Findings: [A failed vector leg makes the engine's fusion answer an empty list instead of an error](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-010)

State machines: [fusion ranking](../../Verus_verification/models/fusion_ranking/manifest.json)

### search.fusion.python

- design-verified

- uncertain
- Sources: [`RRFFusion.fuse_results`](../../../iris_vector_graph/fusion.py#L27-L64), [`HybridSearchFusion.multi_modal_search`](../../../iris_vector_graph/fusion.py#L113-L253), [migration guide](../../../docs/migration/v4.0.0.md#L427-L435)
- Verus: [fusion_ranking](../../Verus_verification/models/fusion_ranking/NOTES.md), as-built `rank`, `score`, `theorem_rank_ignores_magnitude`, `theorem_first_occurrence_wins`, `theorem_second_leg_changes_winner`; exact real arithmetic for rank contributions and a strict pair winner. General sorting, floating point rounding and detail assembly are observed in Python, not proved.
- Expands: [fusion](#search.fusion)
- Children: [Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?](../../Verus_verification/open_questions.md#HD-0705)
- agent
- user-facing-behavior

No order is claimed between ties or at a tied k cutoff. This helper's zero absent contribution does not settle the shared rule for the other fusion entry points.

Open questions: [Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?](../../Verus_verification/open_questions.md#HD-0705)

State machines: [fusion ranking](../../Verus_verification/models/fusion_ranking/manifest.json)

Assumption review evidence: Same direction as decisions.md.

### search.erasure
- Sources: [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md#L8-L23), [EraseGraph](../../../iris_src/src/Graph/KG/Eraser.cls#L36-L313), [EraseAll registry delete](../../../iris_src/src/Graph/KG/Eraser.cls#L750-L760), [store inventory](../../../iris_src/src/Graph/KG/GraphStores.cls#L1-L60), [test_227_erase_isolation.py](../../../tests/e2e/test_227_erase_isolation.py)
- Children: [Indexes](#search.erasure.indexes)
- Observed divergence: no erase path touches the BM25, IVF, PLAID or VecIndex index globals (F1 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- agent
- data-integrity, security
- test-coverage

Findings: [Search indexes keep answering with content that was erased, and a re-created node inherits the erased text](../../Verus_verification/bugs_issues.md#bug-srch-001)

### search.erasure.indexes

- uncertain
- Sources: [CONTEXT.md Erasure](../../../CONTEXT.md#L198-L206), [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md#L8-L23), [ADR-0004: one store without the others is a bug](../../../docs/adr/0004-erasure-removes-content-not-history.md#L79-L80), [ADR-0013: together they cover everything IVG can reach](../../../docs/adr/0013-redaction-removes-content-from-history.md#L47), [BM25 records its graph](../../../iris_src/src/Graph/KG/BM25Index.cls#L165-L170), [Eraser rationale for documents](../../../iris_src/src/Graph/KG/Eraser.cls#L136-L147), [replacing restore calls erase_all](../../../iris_vector_graph/_engine/snapshot.py#L1139-L1152)
- Expands: [Erasure](#search.erasure)
- Children: [What must erasing one graph do to a VecIndex, PLAID or IVF index, which records no graph?](../../Verus_verification/open_questions.md#search.erasure.indexes.graphless)
- Observed divergence: no erase path touches `^BM25Idx`, `^IVF`, `^PLAID` or `^VecIdx`, and the store inventory lists none of them ([store inventory](../../../iris_src/src/Graph/KG/GraphStores.cls#L113-L130)). [A native probe](../../Verus_verification/receipts/native/search_bm25_erase.json) saw `bm25_search` still answer an erased node, and still score its erased text after the node was re-created with other text (F1 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- Observed divergence (suspected, from code reading only): because erasing everything leaves these indexes, a replacing restore keeps an index the archive lacks and overlays a same-named one with the archive's postings, which breaks [the count rule](#search.bm25.counts) ([snapshot globals](../../../iris_vector_graph/_engine/snapshot.py#L380-L400); review round 1, R1-6).
- Note: changed from Q to I by review round 1 (R1-7): the governing texts above already decide erasure. Treating these indexes as derived stores that erasure skips and the caller rebuilds would be a proposal to change this decision. The ordinary node-delete case stays with [index upkeep](#search.scope.indexes.upkeep).
- agent
- data-integrity, security

Findings: [Search indexes keep answering with content that was erased, and a re-created node inherits the erased text](../../Verus_verification/bugs_issues.md#bug-srch-001); [A replacing restore leaves the live search indexes in place and merges the archive's into them](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-024)

Open questions: [Are the IVF, tree (VecIndex) and PLAID indexes inside the erasure promise?](../../Verus_verification/open_questions.md#HD-0601), [What must erasing one graph do to a VecIndex, PLAID or IVF index, which records no graph?](../../Verus_verification/open_questions.md#search.erasure.indexes.graphless)
