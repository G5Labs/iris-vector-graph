# Search vectors and text

Start with vector similarity, BM25 text search or a fused ranking. For stored routes and index maintenance, see [search storage and indexes](../architecture/search-storage-and-indexes.g5.md).

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

<a id="search.embedding.model_key"></a>
[D · search.embedding.model_key]

Two model keys match only if they are equal after trimming, lowercasing and collapsing runs of spaces. Nothing else is rewritten, because an operator can fix a false refusal, while a false match silently mixes two models.
- The mechanism must come from a fixed list.
- Two writers that name the same model with different mechanisms conflict.

<a id="search.embedding.width"></a>
[D · search.embedding.width]

A table's width is the width its vector column declares, and the registry copies that width rather than overriding it.
- Setup never changes the width of a table that holds vectors. It changes an empty table's width only when asked.
- A setup at another width than a populated table is meant to leave it and name it for manual migration.
- Today, when an empty vector table sits beside the populated one at the old width, plain setup refuses for the empty one and `rewidth=True` refuses for the populated one, so the manual-migration reply never comes ([bug-plt-134](../../Verus_verification/bugs_issues.md#bug-plt-134)).
- Today an engine that names the IVG Schema in another letter case reads no declared width, so its setup re-declares the empty tables at its own width without being asked and leaves the registry at the old width ([bug-plt-015](../../Verus_verification/bugs_issues.md#bug-plt-015)).
- A writer that reuses a table whose column declares another width is refused before any record claims its width.
- A query vector is never padded or cut to fit a table. A query of the wrong width raises an error instead of returning scores.
- That refusal comes before any search statement runs, and it names both widths. The width compared is the route's, or the column's declared width when the route records none.
- No check is made when there is nothing to compare: for a seed node ID, whose vector comes from the route itself; for a route and column with no declared width; or for a literal that cannot be parsed. IRIS then decides, and its refusal is raised, not turned into an empty answer.

<a id="search.embedding.check_on_write"></a>
[I · search.embedding.check_on_write]

Every path that writes vectors checks the write against its table's recorded identity before writing anything, and refuses a conflict. No setting turns the refusal into a warning.
- A writer that names a model is checked on model, mechanism, width and element type.
- An undeclared writer is checked on width and element type only.
- A batch that mixes widths is refused whole.

<a id="search.embedding.other_model"></a>
[D · search.embedding.other_model]

Vectors from two declared models never share a table. A write that names a model key goes to that model's own route for the graph, and a writer that declares a different model for a table that already records one is refused.

- Today setup by an engine configured for another model than a table records is refused, although that engine's writes would be routed. Whether setup should refuse or route is open.

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

<a id="search.knn"></a>
[I · search.knn]

A vector search returns up to k pairs of node ID and cosine similarity from one graph's route, highest first.
- The query is a vector, or a node ID whose stored vector in the same graph is used. That node is left out of the answer.
- An optional label keeps only nodes that have the label in the same graph.
- Each route gets an attempted approximate-nearest-neighbour (HNSW) index. A route whose index was refused is searched by a full scan.
- With no route for the graph and model, the store's `execute_knn_vec` answers no neighbours rather than an error.

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

## VecIndex and PLAID search

<a id="search.vecindex"></a>
[I · search.vecindex]

A VecIndex is a named vector index that a caller fills and searches by name; it records no graph. A search returns up to k stored IDs, nearest first.

- For cosine the score is the cosine and the distance is 1 minus it. For dot the score is the dot product, largest first, and the distance is its negative. For l2, l1 and chebyshev both are the distance.
- A vector inserted after a build can be found at once; a build places every stored vector again. A search ranks only the IDs in the tree leaves the query reaches, so it is approximate once the index holds more vectors than a leaf.
- Inserting an ID again replaces its vector. Today the reported count still goes up by one, and creating the index again under the same name keeps the vectors but reports a count of 0.
- Today a vector of another width is accepted and becomes the index's recorded width; distances to it use only the parts both vectors have.
- Dropping the index removes everything; a search then returns nothing.

<a id="search.plaid"></a>
[I · search.plaid]

A PLAID index holds several vectors per document and ranks documents by late interaction: for each query vector, the best dot product with any of the document's vectors, summed.

- A build refuses a vector of another width before writing anything.
- Inserting a document again replaces its vectors, so it is scored on the new ones. Today the reported document and vector counts still go up by the insert.
- Today an insert of another width is accepted; it is scored on the parts both vectors have and can outrank correctly sized documents.

## IVF search and distance

<a id="search.ivf"></a>
[D · search.ivf]

An IVF index puts each vector in the cell of its nearest centroid and searches the cells nearest the query. After a build, inserts and deletes change it one node at a time, and a rebuild replaces it with the route's vectors.
- A node not in the index, or an index that was never built, gives no hit and no error; an insert into a missing index is refused.
- Today an insert does not remove the node's earlier vector in another cell, a delete removes only one copy, and every insert adds one to the reported size ([finding](../../Verus_verification/bugs_issues.md#bug-srch-107)).
- Today a query of another width is answered with scores ([finding](../../Verus_verification/bugs_issues.md#bug-srch-108)).
- The SQL function `kg_IVF` gives the same hits and scores as `ivf_search`, including an empty answer for an index that was never built. Who may call it is set by [the SQL privilege rule](../concepts/access.g5.md#access.iris_boundary).

<a id="search.ivf.metric"></a>
[I · search.ivf.metric]

An IVF index scores by the metric it was built with. With "dot" the score is the dot product, with "l2" or "euclidean" it is the negative squared distance, and with "cosine" (the default) it is the cosine, so a vector's length does not change its rank.
- Today "cosine" scores the raw dot product, the same as "dot", when a search picks the cells to probe, when an insert picks a node's cell, and when hits are ranked. A long vector can then outrank a perfectly aligned one ([finding](../../Verus_verification/bugs_issues.md#bug-srch-109)).
- A build puts each vector in the cell of its nearest centroid by plain distance, whatever the metric.
- Today, under "cosine" or "dot", re-inserting a node with its unchanged vector can therefore pick another cell than the build did, and the old entry stays ([finding](../../Verus_verification/bugs_issues.md#bug-srch-107)).
- Unit-length vectors get the same order either way.

## BM25 text search

<a id="search.bm25"></a>
[I · search.bm25]

A BM25 index is a named lexical index over chosen text properties of one graph's nodes, searched with Okapi BM25.
- A node with no indexable text is not in the index.
- Inserting a document that is already there replaces it. Replacing it with text that has no indexable terms removes it.
- Removing a document that is not in the index changes nothing.
- A search returns the top k documents by score, highest first. `bm25_search` and `CALL ivg.bm25.search` refuse a k below 1. Today the SQL function `kg_BM25` accepts any k and answers an empty list for 0 or less ([finding](../../Verus_verification/bugs_issues.md#bug-srch-113)).

- Working assumption: Assume no cross-call consistency guarantee until a read/write protocol is chosen; partial-index results remain visible risk, not approved isolation.
- Working assumption: Keep explicit BM25 selection distinct from plain text search; a default-index fallback requires a supported API/corpus decision.
- Working assumption: Model kg_TXT as iFind-then-LIKE (documented as-built). Record FR-012/US5/SC-004 and tasks T034/T035 as a spec/doc conflict (S3, F-0708), not as a current obligation the pin fails. If the fallback returns, it applies only on the LIKE path, only to an index whose recorded graph equals the requested graph, never across graphs. Why changed: decisions.md called this Supported on spec 044 FR-012, SC-004 and PR #8. Those establish the 2026-04 feature, not that it is still wanted: the Draft spec is the only post-removal carrier, it was copied wholesale with the schema-2 amendment, and the maintainer's later kg_TXT redesign (v2.18.2, US7, docstring, generated API reference) excludes it. No source "supersedes" FR-012 explicitly either, so neither reading is supported; the assumption follows the newer, user-facing contract.
- Working assumption: Reserve `__stop__`: public BM25 entry points (`bm25_build/insert/delete/drop/upgrade`, `BM25BuildInput`, index handles, `kg_BM25`/`ivg.bm25.search`) refuse it; the embedded registry walk skips it. Model the as-built acceptance as a defect against the documented stopword list (cross-index). Moving the list to its own global is the compatible alternative mechanism.

<a id="search.bm25.scoring"></a>
[I · search.bm25.scoring]

A document's score adds up, for each query term, `IDF × tf × (k1 + 1) / (tf + k1 × (1 − b + b × length / average length))`, where `IDF = ln(1 + (N − df + 0.5) / (df + 0.5))`. The defaults are `k1 = 1.5` and `b = 0.75`.
- Documents and queries are tokenized the same way: lowercased, split at punctuation, with no stemming and a fixed list of 77 common English words left out.
- A query term counts once for each time the query repeats it.
- Scores are compared to 12 decimal places, and equal scores are listed in IRIS subscript order of their node IDs: IDs that are whole numbers come first, in numeric order, and the others follow in character-code order, so `9` comes before `10`, `d10` before `d9` and `dB` before `da`. A search answers the first k of that order. This is as built; no document states a tie order.

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

<a id="search.fusion.surfaces"></a>
[I · search.fusion.surfaces]

Each fusion entry point keeps its own rule for an item one leg lacks and its own text list, so the same query can rank differently by entry point.
- The engine's `kg_RRF_FUSE` (and `kg_RERANK`, `IRISGraphOperators.kg_RRF_FUSE`) reads a BM25 index of node properties and places a missing item at the other leg's length plus c. An item only the vector leg finds can then outrank items both legs rank well ([finding](../../Verus_verification/bugs_issues.md#bug-srch-005)).
- The SQL `kg_RRF_FUSE` procedure and the `/hybridSearch` body (`PyOps.HybridSearch`, through `FuseRanks` for a routed graph) read the documents table through `kg_TXT` and place a missing item at 10^9, which is almost nothing.
- An empty text query or an empty leg still adds 1/(2c) to every row the engine answers, so the reported score is not 1/(c + rank).
- The engine method takes `c` with no default; `IRISGraphOperators` and `kg_RERANK` use 60, and `kg_RERANK` searches each leg 2 × `top_n` deep. `/hybridSearch` replaces a `c` of 0 with 60 ([finding](../../Verus_verification/bugs_issues.md#bug-srch-112)).
- Working assumption: Each rule stays as it is until one rule is chosen ([open question](../../Verus_verification/open_questions.md#HD-0702)).

<a id="search.fusion.vector_graph"></a>
[I · search.fusion.vector_graph]

`kg_VECTOR_GRAPH_SEARCH` collects vector hits, their one-hop neighbours over edges whose `confidence` is at least 1000 × `min_confidence`, and text hits into one set, keeps k of them, and only then sorts the kept ones by vector similarity.
- Which k are kept follows Python's set order, which changes between processes, so the best vector hit can be left out of the answer ([open question](../../Verus_verification/open_questions.md#HD-0603)).
- A node found only by expansion or text scores 0.0, even when it has a stored vector.
- `in_graph_expansion` is true for every node an edge reached, including a node the vector search also found.
- An edge without a `confidence` value is not followed. A query vector of the wrong width raises; a graph with no vectors answers nothing.

<a id="search.fusion.rest"></a>
[I · search.fusion.rest]

The `/vectorSearch` and `/hybridSearch` bodies (`Graph.KG.PyOps`) read a named graph's own route and the default graph's original table, like the engine.
- Today they check the query's width before looking the route up. A named graph with no route expects width 768, so a query of another width is refused with a width error where the engine answers nothing ([finding](../../Verus_verification/bugs_issues.md#bug-srch-111)).
- A failed read is raised with the SQL code, and a missing privilege names the table.

<a id="search.fusion.multi_vector"></a>
[I · search.fusion.multi_vector]

`multi_vector_search` searches each source for 2 × `top_k` rows and fuses them by weighted reciprocal rank, `weight / (rrf_k + rank)` summed per ID; any other `fusion` value ranks by the raw score and ignores the weights.
- A source that fails, such as one of another width or a routed table without a graph, is logged and skipped, so an answer can come from fewer sources than asked, and all sources failing answers nothing ([search.fusion.failed_leg](#search.fusion.failed_leg)).
- A source's own `graph` overrides the call's.

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
- Ordinary node deletes are different: the caller keeps indexes in step with those ([index upkeep](../architecture/search-storage-and-indexes.g5.md#search.scope.indexes.upkeep)).

- Working assumption: Unchanged: model retained index contents as observable after erasure unless purged; graph-owned indexes require invalidation or deletion on erase; caller-fed indexes need an explicit owner/exposure statement. Refined with the graph-derived (IVF) vs caller-fed (VecIndex, PLAID) split.
- Working assumption: Treat graphless indexes as derived data requiring a rebuild after erasure.

## Earlier links

These links take you to the current sections and statements.

<a id="embeddings-and-search"></a>

[Search vectors and text](#search-vectors-and-text)

<a id="building-an-ivf-index"></a>

[Building an IVF index](../operations/search-indexes.g5.md#building-an-ivf-index)

<a id="quarantine"></a>

[IVF search and distance](#ivf-search-and-distance) · [Vectors and documents awaiting graph assignment](../architecture/search-storage-and-indexes.g5.md#vectors-and-documents-awaiting-graph-assignment)

<a id="search.embedding.registry"></a>

[search.embedding.registry](../architecture/search-storage-and-indexes.g5.md#search.embedding.registry)

<a id="search.embedding.width.raw-helpers"></a>

[search.embedding.width.raw-helpers](../architecture/search-storage-and-indexes.g5.md#search.embedding.width.raw-helpers)

<a id="search.embedding.claim"></a>

[search.embedding.claim](../architecture/search-storage-and-indexes.g5.md#search.embedding.claim)

<a id="search.embedding.queue"></a>

[search.embedding.queue](../architecture/search-storage-and-indexes.g5.md#search.embedding.queue)

<a id="search.embedding.bulk"></a>

[search.embedding.bulk](../architecture/search-storage-and-indexes.g5.md#search.embedding.bulk)

<a id="search.routes.cache"></a>

[search.routes.cache](../architecture/search-storage-and-indexes.g5.md#search.routes.cache)

<a id="search.routes.create_on_write"></a>

[search.routes.create_on_write](../architecture/search-storage-and-indexes.g5.md#search.routes.create_on_write)

<a id="search.routes.orphan"></a>

[search.routes.orphan](../architecture/search-storage-and-indexes.g5.md#search.routes.orphan)

<a id="search.routes.inventory"></a>

[search.routes.inventory](../operations/search-indexes.g5.md#search.routes.inventory)

<a id="search.scope.indexes.upkeep"></a>

[search.scope.indexes.upkeep](../architecture/search-storage-and-indexes.g5.md#search.scope.indexes.upkeep)

<a id="search.scope.indexes.ivf"></a>

[search.scope.indexes.ivf](../operations/search-indexes.g5.md#search.scope.indexes.ivf)

<a id="search.quarantine"></a>

[search.quarantine](../architecture/search-storage-and-indexes.g5.md#search.quarantine)

<a id="search.quarantine.placement"></a>

[search.quarantine.placement](../architecture/search-storage-and-indexes.g5.md#search.quarantine.placement)

<a id="search.bm25.query_time_idf"></a>

[search.bm25.query_time_idf](../architecture/search-storage-and-indexes.g5.md#search.bm25.query_time_idf)

<a id="search.bm25.counts"></a>

[search.bm25.counts](../architecture/search-storage-and-indexes.g5.md#search.bm25.counts)

<a id="search.bm25.incremental"></a>

[search.bm25.incremental](../architecture/search-storage-and-indexes.g5.md#search.bm25.incremental)

<a id="search.bm25.write_lock"></a>

[search.bm25.write_lock](../architecture/search-storage-and-indexes.g5.md#search.bm25.write_lock)

<a id="search.bm25.schema"></a>

[search.bm25.schema](../architecture/search-storage-and-indexes.g5.md#search.bm25.schema)

<a id="search.bm25.upgrade"></a>

[search.bm25.upgrade](../operations/search-indexes.g5.md#search.bm25.upgrade)

<a id="search.fusion.python"></a>

[search.fusion.python](../architecture/search-storage-and-indexes.g5.md#search.fusion.python)

<a id="search.fusion.leg_index"></a>

[search.fusion.leg_index](../architecture/search-storage-and-indexes.g5.md#search.fusion.leg_index)

## Metadata

### search.embedding

- uncertain
- Sources: [ADR-0006](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md), [CHANGELOG v3.2.0](../../../CHANGELOG.md#L4371-L4440), [CONTEXT.md glossary](../../../CONTEXT.md#L154-L157), [stage-A notes](../../uplift/ivg-verus-initial/intent/search.md#capabilities), live tests [registry](../../../tests/integration/test_embedding_registry_e2e.py) and [refusal](../../../tests/integration/test_embedding_identity_refusal_e2e.py)
- Children: [Registry](../architecture/search-storage-and-indexes.g5.md#search.embedding.registry), [Model key](#search.embedding.model_key), [Width](#search.embedding.width), [Check on write](#search.embedding.check_on_write), [Claim](../architecture/search-storage-and-indexes.g5.md#search.embedding.claim), [Other model](#search.embedding.other_model), [May an undeclared writer add vectors to the default graph's table after a model has claimed it?](../../Verus_verification/open_questions.md#q-srch-002), [Queue](../architecture/search-storage-and-indexes.g5.md#search.embedding.queue)
- agent
- data-integrity, user-facing-behavior
- test-coverage

Open questions: [May an undeclared writer add vectors to the default graph's table after a model has claimed it?](../../Verus_verification/open_questions.md#q-srch-002)

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

Setup's width decision (iteration 56): [install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_populated_never_rewidened`, `theorem_empty_other_width_needs_rewidth`, `theorem_unknown_width_altered_unasked`; controls `populated-altered`, `rewidth-not-required`, `unknown-width-counted`.

Findings: [ivf_search answers a query of another width](../../Verus_verification/bugs_issues.md#bug-srch-108); [bug-plt-134](../../Verus_verification/bugs_issues.md#bug-plt-134); [bug-plt-015](../../Verus_verification/bugs_issues.md#bug-plt-015)

### search.embedding.check_on_write

- Sources: [enforce_embedding_identity](../../../iris_vector_graph/_engine/schema.py#L1354-L1396), [store_embedding](../../../iris_vector_graph/_engine/embeddings.py#L942-L1025), [store_embeddings](../../../iris_vector_graph/_engine/embeddings.py#L1028-L1115), [offered unknown identity](../../../iris_vector_graph/embedding_identity.py#L79-L98), [CHANGELOG v3.2.0](../../../CHANGELOG.md#L4371-L4440)
- Expands: [Embedding identity](#search.embedding)
- Verus: [install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_width_enforced_whatever_the_model` (binding `W:store8`, `I:enforce_*`)
- Observed divergence: the check passes when [the registry cannot be read](../../../iris_vector_graph/_engine/schema.py#L1033-L1084), and [the IRIS queue worker](../../../iris_src/src/Graph/KG/EmbedQueue.cls#L256-L345) writes default-graph entries without it (F8, F11 in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings)).
- agent
- data-integrity
- test-coverage

Findings: [The embedding queue checks identity against the wrong table, and its IRIS worker writes default-graph entries with no identity check](../../Verus_verification/bugs_issues.md#bug-srch-006); [Embedding identity enforcement allows the write when the registry read fails](../../Verus_verification/bugs_issues.md#bug-srch-012); [Check embedding identity against the registry row the route lookup already read](../../Verus_verification/design_simplification.md#simp-srch-002)

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

### search.routes

- Sources: [CHANGELOG v4.0.0 routed tables](../../../CHANGELOG.md#L4161-L4183), [EmbeddingRoute and resolve_route](../../../iris_vector_graph/_engine/embeddings.py#L35-L301), [route preference](../../../iris_vector_graph/_engine/embeddings.py#L107-L118), [test_227_two_models.py](../../../tests/e2e/test_227_two_models.py), edge vectors: [store_edge_embedding](../../../iris_vector_graph/_engine/embeddings.py#L1117-L1205), [edge_vector_search](../../../iris_vector_graph/_engine/vector.py#L333-L398), [migration guide](../../../docs/migration/v4.0.0.md#L553-L598)
- Children: [No fallback](#search.routes.no_fallback), [Create on write](../architecture/search-storage-and-indexes.g5.md#search.routes.create_on_write), [Orphan](../architecture/search-storage-and-indexes.g5.md#search.routes.orphan), [Route cache](../architecture/search-storage-and-indexes.g5.md#search.routes.cache), [Inventory](../operations/search-indexes.g5.md#search.routes.inventory)
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

Findings: [`/vectorSearch` and `/hybridSearch` refuse a query of another width for a graph with no vectors](../../Verus_verification/bugs_issues.md#bug-srch-111)

### search.knn

- Sources: [kg_KNN_VEC](../../../iris_vector_graph/_engine/vector.py#L504-L619), [_attempt_route_index](../../../iris_vector_graph/_engine/schema.py#L911-L933), [CHANGELOG v4.0.0 routed tables and HNSW](../../../CHANGELOG.md#L4161-L4183), [each graph's search test](../../../tests/e2e/test_227_two_models.py#L187-L203)
- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_primary_generic_failure_really_calls_optimized`, `theorem_optimized_double_failure_really_calls_client`, typed score readers and raw CSV shape/effect relations cover the primary/optimized/client node-search chain. The source model retains both the seed-identity-loss counterexample and the unknown-width mixed-error empty answer. SQL/NumPy numeric replies are provider inputs, with finite actual readers and predicates executed in735 binding comparisons; no cosine/ANN/numerical or native-body theorem follows. Nonstring/raw numeric carriers, connection/cursor allocation and exact exception text remain qualified.
- Note: added for gap G18 of the [reconstruction check](../../uplift/ivg-verus-initial/reconstruction-check.md#1b-gaps-a-builder-would-hit). The order of equal scores is not specified, and recall of the approximate index is recorded per route only when measured.
- agent
- user-facing-behavior
- Verus (iteration 57): [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) `theorem_knn_no_route_no_rows` (the store reader's no-route branch only)

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
- Children: [Upkeep](../architecture/search-storage-and-indexes.g5.md#search.scope.indexes.upkeep), [IVF build admission](../operations/search-indexes.g5.md#search.scope.indexes.ivf)
- Observed divergence: a Cypher BM25 search under a named graph never compares the index's recorded graph (F7), and an IVF index records no graph. The engine takes its list of indexes and their graphs once, so fusion does not see a dropped index or one another process built (F6). Both are in the [stage-A findings](../../uplift/ivg-verus-initial/intent/search.md#candidate-findings).
- agent
- data-integrity, architecture-decision
- test-coverage

Findings: [Fusion chooses indexes from a snapshot taken when the engine started](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-011), [A BM25 index built before 4.0.0 reports the default graph, so the default graph's fusion reads another graph's documents as its own](../../Verus_verification/bugs_issues.md#bug-srch-017)


The pre-4.0.0 index case is from [BM25Index.cls](../../../iris_src/src/Graph/KG/BM25Index.cls#L607-L611) ("a stale index is indistinguishable here; rebuild it") and the fusion's index choice in [vector.py](../../../iris_vector_graph/_engine/vector.py#L164-L206) (helper reading, review round 3 R3-reader M25; the fusion part was not re-checked).

Open questions: [May an index build be seen half-done, and may a stopped build leave a partial index?](../../Verus_verification/open_questions.md#HD-0602)

### search.vecindex

- Sources: [API reference, vec_*](../../../docs/API_REFERENCE.md#L1150-L1226), [Graph.KG.VecIndex](../../../iris_src/src/Graph/KG/VecIndex.cls), [engine wrappers](../../../iris_vector_graph/_engine/vector.py#L1548-L1650)
- Verus: [vec_index](../../Verus_verification/models/vec_index/NOTES.md) `theorem_insert_found_by_identical_query`, `theorem_build_places_every_vector`, `theorem_reinsert_inflates_count`, `theorem_distinct_inserts_count_vectors`, `theorem_recreate_zero_count_keeps_vectors`, `theorem_insert_overwrites_dim`, `theorem_drop_empties_search`, `theorem_score_mapping` (as built)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-27/vecindex-PAIRS.md)
- agent
- user-facing-behavior

Findings: [Vector index stores do not check width or duplicates](../../Verus_verification/bugs_issues.md#F-0608); [Creating a VecIndex again under the same name reports a count of 0 while its vectors stay searchable](../../Verus_verification/bugs_issues.md#bug-srch-101); [The API reference says a vector inserted into a VecIndex is searchable only after the next vec_build](../../Verus_verification/bugs_issues.md#bug-srch-102)

State machines: [vec index](../../Verus_verification/models/vec_index/manifest.json)

### search.plaid

- Sources: [API reference, plaid_*](../../../docs/API_REFERENCE.md#L1083-L1121), [Graph.KG.PLAIDSearch](../../../iris_src/src/Graph/KG/PLAIDSearch.cls), [engine wrappers](../../../iris_vector_graph/_engine/vector.py)
- Verus: [plaid_index](../../Verus_verification/models/plaid_index/NOTES.md) `theorem_build_refuses_other_width`, `theorem_reinsert_inflates_counts`, `theorem_reinsert_scored_on_new_tokens`, `theorem_insert_accepts_other_width`, `theorem_new_doc_counted_once` (as built)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-30/plaid-PAIRS.md)
- agent
- user-facing-behavior

Findings: [Vector index stores do not check width or duplicates](../../Verus_verification/bugs_issues.md#F-0608)

State machines: [plaid index](../../Verus_verification/models/plaid_index/manifest.json)

### search.ivf

- Sources: [API_REFERENCE ivf_build, ivf_search, ivf_insert, ivf_delete, ivf_info, ivf_drop](../../../docs/API_REFERENCE.md); [`IVFIndex.cls` Insert, Delete, Search](../../../iris_src/src/Graph/KG/IVFIndex.cls#L55-L230)
- Expands: [Named search index scope](../architecture/search-storage-and-indexes.g5.md#search.scope.indexes.upkeep)
- Verus: active: [`ivf_entries.rs`](../../Verus_verification/models/ivf_entries/NOTES.md) `theorem_insert_then_delete`; as-built departures `theorem_same_cell_reinsert_counts_twice`, `theorem_cross_cell_reinsert_leaves_stale_entry`, `theorem_other_width_answered`.
- agent
- user-facing-behavior, data-integrity

Recovered in iteration 46 from the API reference and observation ([W52](../../uplift/consolidated/iteration-46/ivf-PAIRS.md)). The `kg_IVF` bullet was added in iteration 47 after the frozen W53 predictions S1 and S3 held ([W53](../../uplift/consolidated/iteration-47/sqlprocs-PAIRS.md)).

Findings: [Re-inserting a node into an IVF index keeps its old vector](../../Verus_verification/bugs_issues.md#bug-srch-107); [ivf_search answers a query of another width](../../Verus_verification/bugs_issues.md#bug-srch-108)

### search.ivf.metric

- Sources: [API_REFERENCE ivf_build, ivf_info](../../../docs/API_REFERENCE.md); [`_validate.py` `_IVF_METRICS`](../../../iris_vector_graph/_validate.py#L9); [`IVFIndex.cls` Search, Insert](../../../iris_src/src/Graph/KG/IVFIndex.cls#L55-L215); [`ivf_build`'s k-means](../../../iris_vector_graph/_engine/vector.py#L1985-L2017) and [`AddBatch`](../../../iris_src/src/Graph/KG/IVFIndex.cls#L233-L259); the route search and `VecIndex` (4.7.0) score the cosine
- Expands: [IVF index](#search.ivf)
- Verus: active: [`ivf_entries.rs`](../../Verus_verification/models/ivf_entries/NOTES.md) `entry_score`, `ivf_above`, `cosine_above`; neighbor `theorem_equal_lengths_agree` (every pair of equal lengths since iteration 50); as-built departures `theorem_cosine_ranks_as_dot`, `theorem_cosine_metric_misranks` (control `cosine-normalized` is the repaired order); cells: `build_cell`, `insert_cell`, neighbor `theorem_l2_insert_matches_build`, departure `theorem_cosine_reinsert_changes_cell` (control `insert-by-distance`)
- agent
- user-facing-behavior

Recovered in iteration 47 from the metric's name, the accepted metric list and the sibling cosine searches; observed on the fixture ([W53](../../uplift/consolidated/iteration-47/sqlprocs-PAIRS.md)). Iteration 50 ([review 47-49](../../uplift/consolidated/iteration-50/REVIEW-47-49.md) m8) narrowed "when it picks cells" to search and insert, added the build's distance clustering, and observed the cell change in the [binding](../../Verus_verification/results/ivf_entries/20261117T032444Z-binding/receipt.json) (`cell_cosine`, `cell_dot`, `cell_l2`).

Findings: [An IVF index built with metric "cosine" ranks by the raw dot product](../../Verus_verification/bugs_issues.md#bug-srch-109); [Re-inserting a node into an IVF index keeps its old vector](../../Verus_verification/bugs_issues.md#bug-srch-107); [The engine's fusion reads a cosine IVF index only in the process that built it, so the same call ranks differently elsewhere](../../Verus_verification/bugs_issues.md#bug-srch-110)

### search.bm25

- uncertain
- Sources: [CONTEXT.md glossary](../../../CONTEXT.md#L130-L153), [spec 044](../../../specs/044-bm25-index/spec.md), [spec 044 FR-020 and FR-021](../../../specs/044-bm25-index/spec.md#L166-L167), [BM25Index.cls](../../../iris_src/src/Graph/KG/BM25Index.cls#L1-L33), [test_044_bm25_incremental.py](../../../tests/integration/test_044_bm25_incremental.py)
- Children: [Scoring](#search.bm25.scoring), [Query-time IDF](../architecture/search-storage-and-indexes.g5.md#search.bm25.query_time_idf), [Counts](../architecture/search-storage-and-indexes.g5.md#search.bm25.counts), [Incremental cost](../architecture/search-storage-and-indexes.g5.md#search.bm25.incremental), [Write lock](../architecture/search-storage-and-indexes.g5.md#search.bm25.write_lock), [Schema](../architecture/search-storage-and-indexes.g5.md#search.bm25.schema), [Upgrade](../operations/search-indexes.g5.md#search.bm25.upgrade), [Common-term cutoff](#search.bm25.cutoff), [May a BM25 search observe an index write that is still in progress?](../../Verus_verification/open_questions.md#q-srch-003), [Should plain text search use a BM25 index named "default" when one exists?](../../Verus_verification/open_questions.md#q-srch-004)
- Note: spec 044 is still marked Draft. Its 2026-10-08 and 2026-10-09 clarifications record a request from the opsreview consumer, secondhand, with answers attributed to no named human.
- agent
- user-facing-behavior
- test-coverage

Audit reproduction: [F-C0715](../../Verus_verification/bugs_issues.md#F-C0715) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [kg_BM25 answers an empty list for k of 0 or less](../../Verus_verification/bugs_issues.md#bug-srch-113) (review 53-55 minor; modeled as `bm25_scoring.rs::entry_k`, `theorem_sql_k_nonpositive_empty_others_refuse`, bound by binding cases `k:sql@0`, `k:sql@-1`, `k:py@0`, `k:cypher@0`, iteration 56).

Findings: [bm25_search rewrites document ids: its leading-dot patch runs over the whole answer, so an id holding ':.5', ',.7' or '[.9' comes back as ':0.5', ',0.7', '[0.9'](../../Verus_verification/bugs_issues.md#F-C0715).

Open questions: [Is spec 044's kg_TXT-to-BM25 fallback still wanted?](../../Verus_verification/open_questions.md#HD-0703), [Is `__stop__` a reserved BM25 index name?](../../Verus_verification/open_questions.md#HD-0704), [May a BM25 search observe an index write that is still in progress?](../../Verus_verification/open_questions.md#q-srch-003), [Should plain text search use a BM25 index named "default" when one exists?](../../Verus_verification/open_questions.md#q-srch-004)

### search.bm25.scoring

- Sources: [spec 044 FR-003 and FR-004](../../../specs/044-bm25-index/spec.md#L149-L150), [USER_GUIDE BM25 text search and the stopword list](../../../docs/USER_GUIDE.md#L854-L896), [InitStopwords](../../../iris_src/src/Graph/KG/BM25Index.cls#L41-L50), [bm25_build docstring](../../../iris_vector_graph/_engine/vector.py#L1749-L1785), [formula test](../../../tests/integration/test_044_bm25_incremental.py#L401-L413)
- Expands: [BM25 index](#search.bm25)
- Evidence: [native scores equal the formula within 1e-6 across build and incremental writes](../../uplift/consolidated/iteration-22/bm25-PAIRS.md); [iteration 53 predictions and probe](../../uplift/consolidated/iteration-53/bm25-percentile-PAIRS.md)
- agent
- user-facing-behavior
- design-verified
- Formal: [`theorem_stopword_query_empty`, `theorem_repeat_adds_twice`, `theorem_unknown_term_adds_nothing`, `theorem_shorter_document_scores_higher`, `theorem_tf_raises_and_saturates`, `theorem_idf_arg_positive_and_decreasing`, `theorem_worked_example`, `theorem_ties_by_id`, `theorem_ties_in_subscript_order`](../../Verus_verification/models/bm25_scoring/bm25_scoring.rs)

The model computes the length factor exactly as a rational for k1 1.5 and b 0.75, and represents IDF by its argument; `ln` is a named premise (P-LN), so scores are checked against the formula natively (relative tolerance 1e-12, [binding](../../Verus_verification/models/bm25_scoring/BINDINGS.md)) and their ordering properties formally. Tokenizing with the IRIS analyzer is a provider; the stopword filter is modeled.

Tie order (iteration 56, review 53-55): `before_id`/`id_lt` spell out IRIS subscript collation (premise P-COLLATE); the binding's six-way tie (two numeric ids, `d10`, `d9`, `dB`, `da`) agrees on three readers, and the controls `numeric-ids-as-text` and `text-case-folded` fail as expected.

State machines: [BM25 scoring](../../Verus_verification/models/bm25_scoring/manifest.json)

### search.bm25.cutoff

- uncertain
- Sources: [spec 044 session 2026-10-09](../../../specs/044-bm25-index/spec.md#L314-L334), [CONTEXT.md](../../../CONTEXT.md#L142-L147), [cutoff code](../../../iris_src/src/Graph/KG/BM25Index.cls#L210-L293), [bm25_search](../../../iris_vector_graph/_engine/vector.py#L1786-L1839), [test_044_bm25_max_df.py](../../../tests/integration/test_044_bm25_max_df.py)
- Expands: [BM25 index](#search.bm25)
- agent
- user-facing-behavior, operations
- design-verified
- Formal: [`theorem_cutoff_skips_common_term`, `theorem_fallback_keeps_lowest_df`, `theorem_fallback_ignores_unknown_terms`, `theorem_cutoff_off_scores_known`](../../Verus_verification/models/bm25_scoring/bm25_scoring.rs)

Findings: [In which order must the common-term cutoff list the terms it skipped?](../../Verus_verification/open_questions.md#q-srch-005)

Iteration 53 binding: 5 cutoff cases with the report, an unknown term beside a common one included. The binding compares the skipped terms as a set, so it does not settle q-srch-005.

Audit (q-srch-005): Open owner decision. Working assumption (agent, unratified): Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#q-srch-005).

Open questions: [In which order must the common-term cutoff list the terms it skipped?](../../Verus_verification/open_questions.md#q-srch-005)

### search.fusion

- uncertain
- Sources: [engine kg_RRF_FUSE](../../../iris_vector_graph/_engine/vector.py#L1382-L1451), [API reference](../../../docs/API_REFERENCE.md#L985-L1000), [RRFFusion](../../../iris_vector_graph/fusion.py#L21-L64), [SQL kg_RRF_FUSE](../../../iris_vector_graph/schema.py#L2526-L2560), [Cypher ivg.retrieve](../../../iris_vector_graph/cypher/translator.py#L3239-L3360), [operators default c](../../../iris_vector_graph/operators.py#L37-L44), [test_rrf_fuse_e2e.py](../../../tests/unit/test_rrf_fuse_e2e.py)
- Children: [Same graph](#search.fusion.same_graph), [Failed leg](#search.fusion.failed_leg), [Python fusion](../architecture/search-storage-and-indexes.g5.md#search.fusion.python), [Surfaces](#search.fusion.surfaces), [Leg index](../architecture/search-storage-and-indexes.g5.md#search.fusion.leg_index), [Vector and graph search](#search.fusion.vector_graph), [REST bodies](#search.fusion.rest), [Several vector columns](#search.fusion.multi_vector), [Which reciprocal-rank-fusion rule is the product's?](../../Verus_verification/open_questions.md#HD-0702), [Should every fusion entry point use the same text ranking?](../../Verus_verification/open_questions.md#q-srch-006)
- Note: the live test checks result shape only. The engine method and the SQL procedure take `c` with no default.
- agent
- user-facing-behavior
- test-coverage

Findings: [The engine's fusion gives a result missing from one leg a non-zero, length-dependent score](../../Verus_verification/bugs_issues.md#bug-srch-005); [One fusion function with an explicit absent-rank rule and per-leg failure reporting](../../Verus_verification/design_simplification.md#simp-srch-001)

Iteration 49: [bug-srch-005](../../Verus_verification/bugs_issues.md#bug-srch-005) is now E2E reproduced at the engine and `/hybridSearch` readers ([retrieval_compose binding](../../Verus_verification/models/retrieval_compose/NOTES.md)); the rule per entry point is owned by [Surfaces](#search.fusion.surfaces).

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
- Verus (engine, iteration 49): [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `engine_fuse`, `theorem_failed_vector_leg_reads_as_no_match` (control `vector-failure-isolated`), bound to the fixture: a 3-wide query answers [] while the text leg has 60 rows, and an empty vector leg answers the text ranking; `multi_vector_search` skips a failing source the same way (`theorem_failed_source_skipped`).
- Observed divergence: the engine's fusion logs a failed leg and answers an empty or one-leg ranking, which `IRISGraphOperators.kg_RRF_FUSE`'s default empty query vector triggers. The known-issue entry plans the fix for 4.7.1 ([KNOWN_ISSUES](../../../docs/KNOWN_ISSUES.md#L172-L181)), and the [API reference](../../../docs/API_REFERENCE.md#L999) still documents the log-and-continue behaviour.
- agent
- user-facing-behavior

Findings: [A failed vector leg makes the engine's fusion answer an empty list instead of an error](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-010)

State machines: [fusion ranking](../../Verus_verification/models/fusion_ranking/manifest.json)

### search.fusion.surfaces

- uncertain
- Sources: [engine kg_RRF_FUSE](../../../iris_vector_graph/_engine/vector.py#L1382-L1451), [kg_RERANK](../../../iris_vector_graph/_engine/algorithms.py#L1043-L1050), [operators](../../../iris_vector_graph/operators.py#L36-L43), [SQL kg_RRF_FUSE](../../../iris_vector_graph/schema.py#L2526-L2560), [PyOps FuseRanks, HybridSearch](../../../iris_src/src/Graph/KG/PyOps.cls#L351-L421), [API reference](../../../docs/API_REFERENCE.md#L985-L1000)
- Expands: [Fusion](#search.fusion)
- Verus: active: [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `absent_place`, `rrf`, `theorem_engine_absent_rank_reorders`, `theorem_both_legs_rank10_wins_everywhere`, `theorem_engine_absent_depends_on_length`, `theorem_engine_skipped_leg_adds_constant`, `hybrid_c`, `theorem_hybrid_c_zero_becomes_60`
- agent
- user-facing-behavior

Recovered in iteration 49 from the surfaces' source after the [W56 predictions](../../uplift/consolidated/iteration-49/retrieval-PAIRS.md) F1-F8; observed on the fixture (the same legs put a vector-only item 31st in the engine's answer and 61st in `/hybridSearch`'s).

Open questions: [Which reciprocal-rank-fusion rule is the product's?](../../Verus_verification/open_questions.md#HD-0702), [Should every fusion entry point use the same text ranking?](../../Verus_verification/open_questions.md#q-srch-006)

State machines: [retrieval compose](../../Verus_verification/models/retrieval_compose/manifest.json)

Findings: [The engine's fusion gives a result missing from one leg a non-zero, length-dependent score](../../Verus_verification/bugs_issues.md#bug-srch-005); [`/hybridSearch` replaces a fusion constant of 0 with 60](../../Verus_verification/bugs_issues.md#bug-srch-112)

### search.fusion.vector_graph

- uncertain
- Sources: [kg_VECTOR_GRAPH_SEARCH](../../../iris_vector_graph/_engine/vector.py#L1453-L1548), [API reference](../../../docs/API_REFERENCE.md#L1015-L1031), [IRISGraphOperators.kg_VECTOR_GRAPH_SEARCH](../../../iris_vector_graph/operators.py#L67-L80)
- Expands: [Fusion](#search.fusion)
- Verus: active: [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `answered`, `theorem_best_hit_can_be_dropped`, `theorem_k_covering_set_keeps_best`, `in_graph_expansion`, `vector_similarity`, `theorem_expansion_flag_and_text_only_zero`
- agent
- user-facing-behavior

Observed in iteration 49: with k = 2 the best vector hit was missing for 7 of 8 hash seeds in the binding run (5 of 8 in the first probe). Predictions V1, V2, V3 and V5 held; V4 missed.

Open questions: [Should the vector-and-graph search keep its k best candidates?](../../Verus_verification/open_questions.md#HD-0603)

State machines: [retrieval compose](../../Verus_verification/models/retrieval_compose/manifest.json)

### search.fusion.rest

- Sources: [PyOps VectorSearch, RouteVectorRows, vectorToJson, getExpectedDimension](../../../iris_src/src/Graph/KG/PyOps.cls#L98-L349), [ADMIN_GUIDE Graph.KG.Service](../../../docs/ADMIN_GUIDE.md#L702-L725)
- Expands: [Fusion](#search.fusion)
- Verus: active: [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `pyops_vector_search`, `engine_knn`, `theorem_unrouted_rest_search_refuses_width`
- agent
- user-facing-behavior

Observed by calling the class methods on the fixture; the REST web application itself was not deployed. Prediction Y1 held for a 768-wide query and missed for a 4-wide one.

State machines: [retrieval compose](../../Verus_verification/models/retrieval_compose/manifest.json)

Findings: [`/vectorSearch` and `/hybridSearch` refuse a query of another width for a graph with no vectors](../../Verus_verification/bugs_issues.md#bug-srch-111)

### search.fusion.multi_vector

- Sources: [multi_vector_search](../../../iris_vector_graph/_engine/vector.py#L1288-L1381), [API reference](../../../docs/API_REFERENCE.md#L1067-L1081)
- Expands: [Fusion](#search.fusion)
- Verus: active: [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `mvs_rows`, `theorem_failed_source_skipped` (no control; a transcription of the skip)
- agent
- user-facing-behavior

Predictions M1 and M3 held; M2 was partial (the weights are ignored outside RRF, as the API reference's "raw score" says). `resolve_route` names a route without its schema; the generic helper needs `Graph_KG.` in front.

State machines: [retrieval compose](../../Verus_verification/models/retrieval_compose/manifest.json)

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
- Observed divergence (suspected, from code reading only): because erasing everything leaves these indexes, a replacing restore keeps an index the archive lacks and overlays a same-named one with the archive's postings, which breaks [the count rule](../architecture/search-storage-and-indexes.g5.md#search.bm25.counts) ([snapshot globals](../../../iris_vector_graph/_engine/snapshot.py#L380-L400); review round 1, R1-6).
- Note: changed from Q to I by review round 1 (R1-7): the governing texts above already decide erasure. Treating these indexes as derived stores that erasure skips and the caller rebuilds would be a proposal to change this decision. The ordinary node-delete case stays with [index upkeep](../architecture/search-storage-and-indexes.g5.md#search.scope.indexes.upkeep).
- agent
- data-integrity, security

Findings: [Search indexes keep answering with content that was erased, and a re-created node inherits the erased text](../../Verus_verification/bugs_issues.md#bug-srch-001); [A replacing restore leaves the live search indexes in place and merges the archive's into them](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-024)

Open questions: [Are the IVF, tree (VecIndex) and PLAID indexes inside the erasure promise?](../../Verus_verification/open_questions.md#HD-0601), [What must erasing one graph do to a VecIndex, PLAID or IVF index, which records no graph?](../../Verus_verification/open_questions.md#search.erasure.indexes.graphless)
