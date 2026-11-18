# Blind review packet (iteration 64)

Rows in a fixed shuffled order. For each: the block's canonical text, the obligation as stated, its cases and observation, the model locators and receipts cited, and the model premises. No grade, check, scope, gap or reason is given.

## temporal.window.sources#o04

- page: `.g5/ontology/features/temporal.g5.md`
- statement: Naming two or more of source, list and prefix is refused before any server call.
- cases: two filters vs one
- observation: exception, no call
- model locators: .g5/Verus_verification/models/temporal_window_reader/temporal_window_reader.rs::theorem_two_filters_refused
- design receipts: .g5/Verus_verification/results/temporal_window_reader/20261116T160858Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/temporal_window_reader/20261115T042304Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · temporal.window.sources]

Leaving the source filter out and passing an empty list of sources are different requests. Left out, the read covers every source in the window; an empty list covers none and returns nothing.
- The Python reader sends no `sources` key when the caller passes none, and sends an empty list when the caller passes one.
- The server reads every source only when the request names no source, no list and no prefix. A list that names nothing, or names only empty strings, reads nothing.
- Naming more than one of a source, a list and a prefix is refused before any server call.
```

## temporal.latest#o08

- page: `.g5/ontology/features/temporal.g5.md`
- statement: On a graph written before the index existed, named-source reads search back through time and prefix/every-source reads are refused until one rebuild.
- cases: pre-index graph: named vs prefix vs after rebuild
- observation: get_latest_edges
- model locators: (none)
- design receipts: (none)
- as-built evidence: native AS-PREDICTED .g5/uplift/consolidated/iteration-51/stats-observed-20261117T034349Z.json
- model premises: (none)

Block text:

```
[D · temporal.latest]

IVG keeps the newest-event index up to date on every write, so a latest read never has to search all of time.
- A latest read returns each requested source's newest temporal edge with its attributes.
- The caller names sources, a source prefix, or neither for every source.
- An optional predicate narrows the edges; an optional cutoff excludes edges at or after it, and an optional look-back ignores edges older than the cutoff minus the look-back.
- Ties at the newest timestamp go to the last predicate and target in index order.
- A source with no qualifying edge is left out, never returned empty.
- A graph written before this index existed answers named sources by searching back through time, and refuses prefix and every-source reads until its index is rebuilt once.
```

## query.native.privileges#o01

- page: `.g5/ontology/architecture/query-execution.g5.md`
- statement: A caller lacking SELECT on any of the four graph tables is answered by the SQL path, never the native one
- cases: engine whose user holds SELECT on all four tables vs lacks it on one
- observation: which path answers
- model locators: .g5/Verus_verification/models/native_admission/native_admission.rs::priv_probe; .g5/Verus_verification/models/native_admission/native_admission.rs::theorem_missing_select_keeps_sql; .g5/Verus_verification/models/native_admission/native_admission.rs::theorem_revoke_does_not_reach_running_engine; .g5/Verus_verification/models/native_admission/native_admission.rs::theorem_revoke_reaches_sql_anchor_only
- design receipts: .g5/Verus_verification/results/native_admission/20261118T022637Z-prove/receipt.json; .g5/Verus_verification/results/native_admission/20261118T021702Z-control-recheck-privileges/receipt.json; .g5/Verus_verification/results/native_admission/20261118T021739Z-control-anchor-ignores-privileges/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/native_admission/20261118T022729Z-binding/receipt.json
- model premises: a fresh engine is kept off (proved); a running engine that cached the answer is not (witness)

Block text:

```
[D · query.native.privileges]

A caller without SQL `SELECT` on the node, label, property and edge tables gets the SQL path, never the native one. SQL table privileges keep deciding what a caller can read, even though native reads do not pass through SQL.

- Working assumption: Split the question. (1) A SQL REVOKE is not guaranteed to reach running engines' native reads. To cut native access, revoke the database resource or %Native_ClassExecution, or start new engines. Treat FR-011's executor-side check as an unimplemented spec requirement (F-0908) whose amendment is the maintainer's call. (2) For the route capability, keep FR-003: native reads require the index to be declared at the time of the read. Model an out-of-band drop under running engines as a premise violation ('the index is not dropped while engines run'), not a supported transition, unless Run checks Indexed().
```

## redaction.metadata#o01

- page: `.g5/ontology/features/redaction.g5.md`
- statement: Clearing is triggered by the first tombstone in a revision (any, not every record), including spanning revisions.
- cases: spanning revision with one target record vs revision with none
- observation: revision row free-text fields
- model locators: .g5/Verus_verification/models/ledger_redaction/redaction.rs::tombstone_at; .g5/Verus_verification/models/ledger_redaction/redaction.rs::lemma_step_preserves_inv
- design receipts: .g5/Verus_verification/results/ledger_redaction/20261116T160746Z-prove/receipt.json
- as-built evidence: native OBSERVED_AS_EXPECTED .g5/Verus_verification/receipts/native/redaction_binding.json
- model premises: serialised redactions

Block text:

```
[D · redaction.metadata]

A revision with any redacted record loses its message, source, correlation ID and idempotency key, even when its other records belong to another tenant. Its seq, revision ID, parent, kind and commit time stay, and so do the other graphs' records.
```

## install.export.rdf.scope#o09

- page: `.g5/ontology/features/data-interchange.g5.md`
- statement: N-Quads/TriG keep each triple in its row's graph context
- cases: same triple in g and h -> two quads
- observation: parsed N-Quads
- model locators: .g5/Verus_verification/models/rdf_reporting/rdf_reporting.rs::theorem_raw_selection_preserves_graph; .g5/Verus_verification/models/rdf_reporting/rdf_reporting.rs::theorem_distinct_contexts_share_union_triple
- design receipts: .g5/Verus_verification/results/rdf_reporting/20261116T163325Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/rdf_reporting/20261116T163512Z-binding/receipt.json
- model premises: SQL equality, nullable-graph normalization and a stable view (correspondence conditions); rdflib serializer and parser (provider)

Block text:

```
[D · install.export.rdf.scope]

`export_rdf` writes labels, properties and outgoing edges from every graph when `graph_id` is None, only the default graph when it is empty, and only the named graph otherwise. Nonempty node and label filters narrow that selection; a label must belong to the source node in the row's own graph.

- Empty filter collections do not narrow the export. A label filter writes the matching labels, the selected source nodes' properties and their outgoing edges; it does not pull in a target's other rows.
- A physical node without any selected label, property or outgoing edge contributes no RDF subject. Context-aware formats keep each generated triple in its row's graph.
```

## access.api_key#o01

- page: `.g5/ontology/concepts/access.g5.md`
- statement: With IVG_API_KEY unset or empty, the HTTP server asks for no key on any route
- cases: key unset; key empty string; key set
- observation: HTTP status (handler runs vs 401)
- model locators: experiment/playbook-completion/proofs-d1f/src/auth_l2.rs::http_decide
- design receipts: (none)
- as-built evidence: upstream-test not-run-here tests/e2e/test_460_r222_server_key_and_version_e2e.py
- model premises: HTTP server (api_auth.py)

Block text:

```
[D · access.api_key]

The API key is optional. With `IVG_API_KEY` unset or empty, the HTTP server and Bolt ask for no key at all.

- Working assumption: Model the single key and the IRIS user's privileges as the authorization surface. Treat an admin-only key or a kill route that is off by default as a proposed strengthening. Record IVG_READ_ONLY as the existing, coarse lever.
```

## query.functions.strings#o04

- page: `.g5/ontology/features/cypher.g5.md`
- statement: substring(s, start, l) answers the characters from 0-based start, at most l of them
- cases: start 0 vs 1; start + l inside vs past the end
- observation: the execute_cypher result row (SQL path; the native executor declines these shapes)
- model locators: .g5/Verus_verification/models/cypher_exprs/cypher_exprs.rs::as_built_substring; .g5/Verus_verification/models/cypher_exprs/cypher_exprs.rs::rule_substring; .g5/Verus_verification/models/cypher_exprs/cypher_exprs.rs::theorem_inside_substring_follows_rule
- design receipts: .g5/Verus_verification/results/cypher_exprs/20261117T044807Z-prove/receipt.json; .g5/Verus_verification/results/cypher_exprs/20261117T044822Z-control-substring-zero-based/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/cypher_exprs/20261117T044717Z-binding/receipt.json
- model premises: start >= 0, l >= 1, start + l <= n

Block text:

```
[I · query.functions.strings]

String functions give the openCypher answer for literal and run-time arguments alike. `toUpper`, `toLower`, `trim`, `ltrim`, `rtrim` and `replace` (every occurrence) work on the text, and the trim functions remove leading or trailing whitespace; `substring(s, start, length)` counts from 0 and takes at most `length` characters; `left` and `right` take at most that many; `size()` counts a string's characters or a list's elements; `toInteger` and `toFloat` read numeric text and give null for other text.
- A negative start or length is an error. Today a negative `substring` start answers leading characters (`substring('hello', -1, 2)` is `'h'`), a negative length fails with an IRIS error that names no Cypher error, and `left(s, -1)` is null ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-123)).
- A length of 0 gives the empty string. Today `left(s, 0)`, `right(s, 0)` and `substring(s, 1, 0)` give null ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-124)).
- Today `trim()` in a result or a `SET` removes spaces only, so `trim('\t a \n')` is unchanged and `rtrim()` keeps a line break, while a node `CREATE` of the same `trim()` removes tabs and line breaks too ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-130)).
```

## algorithms.op.leiden#o02

- page: `.g5/ontology/features/algorithms.g5.md`
- statement: gamma 1.0 optimizes modularity; other gamma values use CPM.
- cases: gamma 1.0 vs 0.5
- observation: rows / implementation used
- model locators: (none)
- design receipts: (none)
- as-built evidence: none
- model premises: (none)

Block text:

```
[D · algorithms.op.leiden]

Leiden community detection reads the graph as undirected, simple and unweighted: any number of edges between two nodes, in either direction, is one edge of weight 1.

- With `gamma=1.0` it optimizes modularity; any other `gamma` uses the Constant Potts Model.
- `random_seed` makes a run repeatable. Rows are `{id, community, size}`, community 0 the largest, and `top_k` counts rows, so it can cut through a community.
- The first available implementation answers: `leidenalg` inside IRIS, else Louvain in ObjectScript, then Arno's Leiden, then Python's `leidenalg` or, failing that, networkx's Louvain.
- With `gamma` other than 1.0 the Arno step is skipped, and the Python step needs `leidenalg`.
```

## redaction.after-erasure.default-graph#o02

- page: `.g5/ontology/features/redaction.g5.md`
- statement: For the whole default graph (no prefix) a node row live in any graph must refuse the redaction; as built only default-graph rows are counted, so named-graph node records are tombstoned while the node is live.
- cases: node live in a named graph only vs nowhere
- observation: redact() outcome; verify after
- model locators: .g5/Verus_verification/models/ledger_redaction/redaction.rs::witness_default_graph_target_is_not_graph_blind; .g5/Verus_verification/models/ledger_redaction/redaction.rs::witness_full_check_refuses_the_gaps
- design receipts: .g5/Verus_verification/results/ledger_redaction/20261116T160746Z-prove/receipt.json
- as-built evidence: native OBSERVED_DEFECT .g5/Verus_verification/receipts/native/redaction_default_graph_whole.json
- model premises: (none)

Block text:

```
[I · redaction.after-erasure.default-graph]

For a default-graph target, live node, label and property rows count in every graph, because the ledger's node records and verify both ignore graphs. Relationship rows count only in the target graph.

- So the whole default graph, with no prefix, cannot be redacted while any graph holds a node.
```

## install.snapshot.routes#o06

- page: `.g5/ontology/operations/snapshots-and-bulk-load.g5.md`
- statement: An archived routed table without a width entry takes the restored registry row's width.
- cases: no width entry vs entry
- observation: table width
- model locators: .g5/Verus_verification/models/snapshot_routes/snapshot_routes.rs::theorem_fallback_and_invalid
- design receipts: .g5/Verus_verification/results/snapshot_routes/20261116T160848Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/snapshot_routes/20261115T171758Z-binding/receipt.json
- model premises: decoded unique node routes; successful SQL/DDL

Block text:

```
[I · install.snapshot.routes]

A snapshot saves each routed vector table and restores it at the width the archive records, with each graph's vectors kept to that graph. After a restore, a width-checked vector search on each route reads its own table at its own width.
- A route is saved from its registry row. A row whose table name is not the routed shape, or that has no positive width, is not saved, and a warning says so.
- A restore creates each routed table at the archived width, not at the restoring engine's width, then loads it, builds its index and records the index state the database really has.
- A routed table found in the archive with no width entry takes its width from the restored registry row.
- Node vectors and routed vectors are matched on graph and node, so two graphs' rows stay apart. Edge vectors match on source, predicate and target with no graph.
- Observed limits: an existing routed table keeps its current width; an incompatible empty table refuses incoming vectors and reports failed rows. A merge keeps an existing graph/node vector and counts that skipped row as restored, even when the incoming vector has another width.
- A failed registry index-state update is logged and clears this engine's route cache, but can leave the archive's old index claim. A route with invalid width metadata may remain registered without a table; its vector reader then raises rather than answering empty.
- The generic node merge guard uses only the exported first column. A node with the same ID in another graph can therefore suppress the required parent, making its archived vector fail and its reader answer empty; this is a known merge defect, not the intended graph-key rule.
```

## temporal.labelset#o02

- page: `.g5/ontology/features/temporal.g5.md`
- statement: Equal sets share one hash and different sets get different hashes.
- cases: two sets differing by a quoted string -> same hash; one nested set interned twice -> two hashes
- observation: hash
- model locators: .g5/Verus_verification/models/temporal_stats/temporal_stats.rs::theorem_label_sets_collide; .g5/Verus_verification/models/temporal_stats/temporal_stats.rs::theorem_nested_value_hash_per_call
- design receipts: .g5/Verus_verification/results/temporal_stats/20261117T072022Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/temporal_stats/20261117T065845Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · temporal.labelset]

Interning a set of attributes stores its canonical JSON text once and returns the SHA-1 hash of that text. Equal sets must share one hash and different sets must get different hashes. Today this fails for nested objects and lists, and for strings that hold a quote (both below).
- Keys are sorted; numbers stay numbers, booleans booleans and null null, and key order does not change the hash.
- Resolving a known hash returns the canonical text, and an unknown hash returns an empty string.
- Interned sets are append-only: no purge removes them.
- Today string values are written without JSON escaping and a fraction below one is written as `.5`. A value holding a quote can therefore produce the same text and hash as a different set, and some resolved texts are not JSON.
- Today a nested object or list is written as an internal object reference such as `"12@%Library.DynamicObject"`, which changes from call to call and ignores the content. The same set then gets a new hash, and a new stored entry, on every call, and two different nested values can share a hash ([bug-tmp-105](../../Verus_verification/bugs_issues.md#bug-tmp-105)).
- Text that is not JSON fails with a parsing error rather than returning an empty hash. The Python entry point always sends JSON.
```

## erasure.kept#o05

- page: `.g5/ontology/features/erasure.g5.md`
- statement: A graph erase resets the FHIR graph's watermarks.
- cases: FHIR graph with watermarks erased -> watermarks reset; registry row kept
- observation: Graph_KG.fhir_graphs watermarks read by FHIR sync
- model locators: experiment/playbook-completion/proofs-d1f/src/fhir_l2.rs::erased
- design receipts: (none)
- as-built evidence: inspection read iris_src/src/Graph/KG/Eraser.cls
- model premises: proofs-d1f reviewed design (one graph, one feed); erased() transcribes Eraser.cls's FHIR reset by reading; reviewed-design crate with a baseline receipt only

Block text:

```
[D · erasure.kept]

A graph erase keeps configuration and stores that belong to no single graph.

- A graph's temporal-only predicate settings and FHIR registration survive, so a re-ingest behaves as before. The erase clears the graph's multigraph mode and resets a FHIR graph's watermarks.
- The embedding quarantine is never touched by any erase, because its rows are the only copy of vectors whose graph is unknown. Whether the document and edge-vector quarantines are kept too is part of an [open question](../../Verus_verification/open_questions.md#q-srch-001).
- Stores that record no graph are emptied by an erase of all graphs; what a single-graph erase must do to the search indexes among them is [open](search.g5.md#search.erasure.indexes).

- Working assumption: Keep quarantined data and explicitly report retention until an owner chooses a purge API and its unknown-graph semantics.
- Working assumption: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
```

## search.vecindex#o09

- page: `.g5/ontology/features/search.g5.md`
- statement: As built, inserting a vector of another width is accepted and sets the recorded width
- cases: index width 3, insert 2-wide -> accepted, width 2
- observation: vec_info width
- model locators: .g5/Verus_verification/models/vec_index/vec_index.rs::theorem_insert_overwrites_dim
- design receipts: .g5/Verus_verification/results/vec_index/20261116T215323Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/vec_index/20261116T215331Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · search.vecindex]

A VecIndex is a named vector index that a caller fills and searches by name; it records no graph. A search returns up to k stored IDs, nearest first.

- For cosine the score is the cosine and the distance is 1 minus it. For dot the score is the dot product, largest first, and the distance is its negative. For l2, l1 and chebyshev both are the distance.
- A vector inserted after a build can be found at once; a build places every stored vector again. A search ranks only the IDs in the tree leaves the query reaches, so it is approximate once the index holds more vectors than a leaf.
- Inserting an ID again replaces its vector. Today the reported count still goes up by one, and creating the index again under the same name keeps the vectors but reports a count of 0.
- Today a vector of another width is accepted and becomes the index's recorded width; distances to it use only the parts both vectors have.
- Dropping the index removes everything; a search then returns nothing.
```

## structure.node.update#o02

- page: `.g5/ontology/features/graph-structure.g5.md`
- statement: A given value replaces the property, None removes it, and properties not given stay.
- cases: k given, j None, other key untouched
- observation: get_node properties
- model locators: .g5/Verus_verification/models/node_edge_update/node_edge_update.rs::theorem_store_node_updates; .g5/Verus_verification/models/node_edge_update/node_edge_update.rs::apply_props
- design receipts: .g5/Verus_verification/results/node_edge_update/20261116T222416Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/node_edge_update/20261116T222424Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · structure.node.update]

Writing a node with `store_node` creates its row if it is missing and always reports True.

- Each property it is given replaces that property's value; a None value removes the property, and other properties stay.
- Each label it is given is added; existing labels stay.
- The node gets an `id` property equal to its ID only when it has none yet.
- The row, properties and labels are one transaction, and a duplicate node or label is not an error.
```

## redaction.call#o05

- page: `.g5/ontology/features/redaction.g5.md`
- statement: Two calls are the same redaction (resume rather than refusal) exactly when graph and match string are equal; acme and acme| are one target.
- cases: acme vs acme| (same); same prefix in another graph (different)
- observation: Start's marker comparison (resume vs RedactionInProgressError)
- model locators: .g5/Verus_verification/models/ledger_redaction/redaction.rs::lemma_match_string_not_doubled; .g5/Verus_verification/models/ledger_redaction/redaction.rs::step
- design receipts: .g5/Verus_verification/results/ledger_redaction/20261116T160746Z-prove/receipt.json
- as-built evidence: upstream-test passed tests/integration/test_256_ledger_redaction_e2e.py
- model premises: (none)

Block text:

```
[D · redaction.call]

A redaction call names the graph (none means the default graph), an optional prefix, the separator, an actor and a batch size, and may cap the number of batches. The defaults are separator `|`, actor `system:ledger-redact` and 2,000 tombstones per batch. Two calls are the same redaction when they name the same graph and the same match string, the prefix with its separator, so `acme` and `acme|` name one target.

- A refusal raises a typed error: `RedactionTargetLiveError`, `RedactionInProgressError`, `InvalidRedactionTargetError`, `LedgerNotEnabledError`, `LedgerDisabledError`, `LedgerTransactionOpenError` or `LedgerLockTimeoutError`.
- An unexpected failure inside a batch raises `LedgerInconsistencyError`, and that batch is rolled back.
- A refusal before the first batch changes nothing. A refusal between batches, such as `LedgerDisabledError` or `LedgerLockTimeoutError`, keeps the earlier batches and the marker; running the same call again finishes the run.
```

## access.bolt.framing#o02

- page: `.g5/ontology/features/client-interfaces.g5.md`
- statement: Over WebSocket a message split into any positive chunk sizes is received as the same message and leaves following messages intact
- cases: default chunking vs one-byte chunks of RESET followed by RUN
- observation: the dispatched body and the next RUN's result
- model locators: .g5/Verus_verification/models/bolt_stream/bolt_stream.rs::theorem_small_chunk_reencoding_leaves_terminator; .g5/Verus_verification/models/bolt_stream/bolt_stream.rs::theorem_small_chunk_empty_closes_before_queued_run; .g5/Verus_verification/models/bolt_stream/bolt_stream.rs::theorem_default_chunk_good_neighbor
- design receipts: .g5/Verus_verification/results/bolt_stream/20261117T072022Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/bolt_stream/20261117T071531Z-binding/receipt.json
- model premises: in-process session, no listener (bug-plt-101)

Block text:

```
[I · access.bolt.framing]

A message can use any positive chunk sizes through 65,535 bytes and ends with a zero-size chunk.
- Complete bodies are dispatched in order; an incomplete suffix stays buffered until it is complete.
- A zero-size chunk between messages is a keep-alive in the supported Bolt 4.4 protocol and leaves the session usable.
```

## structure.degree.cache#o02

- page: `.g5/ontology/architecture/adjacency-and-derived-data.g5.md`
- statement: Every change to a node's outgoing adjacency moves its generation
- cases: Put/Remove/PutKeyed/RemoveKeyed/RowUpdate -> gen bumped; a writer without the bump -> cached degree served stale (control writer-no-gen-bump)
- observation: ^KG(gen) and the served degree
- model locators: .g5/Verus_verification/models/graph_structure/graph_structure.rs::theorem_as_built_cache_sound
- design receipts: .g5/Verus_verification/results/graph_structure/20261116T160733Z-prove/receipt.json
- as-built evidence: upstream-test passed tests/e2e/test_degree_cache_live.py
- model premises: graph_structure §2: one graph, one source, all-predicate key; P-QUIET, P-DEFER, P-JOURNAL, P-GRAIN

Block text:

```
[D · structure.degree.cache]

A counted degree may be cached and served while the node's generation has not moved since the count. Every change to a node's outgoing adjacency moves its generation, and deleting the cache changes no answer.

- Working assumption: Unchanged from decisions.md: invalidation can never make an old degree-cache value valid again; model a monotone generation or a fresh graph epoch across erase and rebuild; keep as-built A (kill) as the baseline with its narrow window.
```

## search.bm25.write_lock#o07

- page: `.g5/ontology/architecture/search-storage-and-indexes.g5.md`
- statement: A writer waits up to the lock timeout (30 s default) then fails with no change
- cases: lock held > timeout -> error, index unchanged
- observation: exception and index
- model locators: .g5/Verus_verification/models/search/search.rs::WAct; .g5/Verus_verification/models/search/search.rs::theorem_locked_build_preserves
- design receipts: (none)
- as-built evidence: inspection holds iris_src/src/Graph/KG/BM25Index.cls:403-410
- model premises: (none)

Block text:

```
[D · search.bm25.write_lock]

Every write to an index runs under that index's write lock inside a transaction, so a failed write leaves the index as it was and two writers never interleave. Searches take no lock.
- A failed write takes back only its own changes. It never commits or rolls back a transaction the caller has open, so the caller's earlier writes in that transaction survive.
- Index writes go through the engine's own native connection, so they are part of the caller's transaction only when the engine was made on the caller's connection ([engine connection](../../Verus_verification/open_questions.md#structure.write.engine-connection)).
- A writer waits for the lock up to a set time, 30 seconds by default, then fails without changing anything.
- Counters are updated with plain writes, not atomic increments, because a rollback does not undo an atomic increment.

- Working assumption: Serialize Build, Drop, Insert, Delete and Upgrade per index and publish a complete generation or return unavailable, including after a crash; a Build that is refused or indexes nothing must not destroy the previous index. Model the as-built (unlocked Build/Drop, Kill-first) separately as the baseline. Same as decisions.md.
- Working assumption: Treat transaction membership as dependent on the connection used by the engine.
```

## temporal.optout.drop#o01

- page: `.g5/ontology/features/temporal.g5.md`
- statement: A drop removes the marked structural edges of a temporal-only predicate in one graph and keeps unmarked ones and other graphs'.
- cases: marked vs unmarked row; other graph
- observation: rows
- model locators: .g5/Verus_verification/models/temporal/temporal.rs::drop_rows; .g5/Verus_verification/models/temporal/temporal.rs::witness_optin_strand_recovery_by_drop; .g5/Verus_verification/models/temporal/temporal.rs::lemma_temporal_ops_keep_explicit_rows
- design receipts: .g5/Verus_verification/results/temporal/20261116T160854Z-prove/receipt.json
- as-built evidence: upstream-test PASS tests/e2e/test_temporal_structural_optout_e2e.py
- model premises: (none)

Block text:

```
[I · temporal.optout.drop]

Dropping removes the marked structural edges of temporal-only predicates in one graph, and by default the nodes this leaves bare.
- A purge does not look for these edges, even ones written before the predicate was registered; removing them is the drop's job.
- The drop refuses a predicate that is still structural, because new writes would put the edges back.
- It removes only edges that still carry the mark when they are deleted.
- It runs in bounded transactions and can be resumed; a dry run counts and changes nothing.
- It needs the adjacency index declared.

- Working assumption: Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately.
```

## temporal.edge.graph-scope#o02

- page: `.g5/ontology/features/temporal.g5.md`
- statement: A temporal write, delete, purge or statistics purge in graph g (the default graph included) never changes another graph's temporal stores.
- cases: purge/delete/write in g with identical coordinates in g' -> g' stores unchanged
- observation: per-graph stores
- model locators: .g5/Verus_verification/models/temporal_clock/temporal_clock.rs::theorem_final_window_excludes_wrong_graph_and_time; .g5/Verus_verification/models/temporal/temporal.rs::tout_after_purge
- design receipts: .g5/Verus_verification/results/temporal_clock/20261116T160855Z-prove/receipt.json
- as-built evidence: upstream-test PASS tests/integration/test_223_temporal_graph_scope.py; native AS-EXPECTED .g5/Verus_verification/receipts/native/temporal_endpoint_nodes_verify.json
- model premises: (none)

Block text:

```
[I · temporal.edge.graph-scope]

Every temporal store is kept per graph, and an operation on one graph never reads or changes another graph's temporal data.
- The default graph follows the same rules as a named graph.
- A graph name that cannot be stored safely, such as `"0"` or a name with control characters, is refused before anything is written.
```

## algorithms.op.subgraph.guided#o06

- page: `.g5/ontology/features/algorithms.g5.md`
- statement: Repeated seeds count once and non-node seeds add nothing to the guided answer.
- cases: seeds [a,a]: same as [a]; [a,ghost]: same as [a]
- observation: result
- model locators: .g5/Verus_verification/models/retrieval_compose/retrieval_compose.rs::admit
- design receipts: (none)
- as-built evidence: none
- model premises: (none)

Block text:

```
[I · algorithms.op.subgraph.guided]

`kg_PPR_GUIDED_SUBGRAPH` runs personalized PageRank from the seeds on the default graph, keeps the `ppr_top_k` (50) best positive scores, and returns the subgraph within `k_hops` (1) of the seeds and those nodes with their scores. The answer has at most `min(max_nodes, ppr_top_k)` nodes and lists the edges among them.
- Damping outside (0, 1) or fewer than 1 iteration raises `ValueError` before any data is read. A repeated seed counts once; seeds that are not nodes add nothing.
- Today every seed and top node with an edge is taken in, however many there are, so the answer can exceed the cap: three seeds with `ppr_top_k` 1 answer three nodes ([finding](../../Verus_verification/bugs_issues.md#bug-plt-113)).
- Today, once those nodes fill the cap, only the first of them in ID order is expanded, so the answer lists only its out-edges and the edges among the others are missing. With the default 50 this happens whenever the walk reaches 50 nodes ([finding](../../Verus_verification/bugs_issues.md#bug-plt-113)).
- Both departures were seen on the ObjectScript subgraph reader. With the Arno accelerator loaded and no edge-type filter, another reader answers first; it was not checked.
- `IRISGraphOperators` takes `top_k` and `max_hops` as other names for `ppr_top_k` and `k_hops`. `kg_PPR` is the same walk's scores as a list, best first, zero scores included.
```

## query.system-procedures#o08

- page: `.g5/ontology/features/cypher.g5.md`
- statement: gds.nodeSimilarity.stream is passed to IVG's vector search with its arguments unchanged
- cases: nodeSimilarity call answered by vector search vs refused
- observation: rows
- model locators: (none)
- design receipts: (none)
- as-built evidence: none
- model premises: (none)

Block text:

```
[D · query.system-procedures]

So that Neo4j tools work, IVG answers some Neo4j procedure calls itself, outside SQL.

- `db.*` and `dbms.*` metadata calls, such as `db.labels`, `db.relationshipTypes`, `db.propertyKeys` and `dbms.components`, and `apoc.meta.data` and `apoc.meta.schema`.
- `gds.pageRank.stream`, `gds.betweenness.stream` and `gds.shortestPath.dijkstra.stream`, with GDS's graph-name and configuration arguments; the graph name is not read.
- A `gds.*` call takes after its `YIELD` only a `WHERE` and a `RETURN` of yielded names.
- A `db.*`, `dbms.*` or `apoc.*` call takes after its `YIELD` only a `WHERE`, one `WITH` of yielded names, a `RETURN` of yielded names, `ORDER BY`, `SKIP` and `LIMIT`; any other clause is refused, naming it.
- Another `gds.*` call is refused, naming IVG's own procedure to call instead; `gds.nodeSimilarity.stream` is the exception, passed to IVG's vector search with its arguments as given.

- Working assumption: Prefer declared YIELD aliases at the public reader, while documenting current handled-call names until the owner decides.
- Working assumption: Prefer validating a requested WHERE independent of row count; current empty-provider acceptance does not settle intent.
- Working assumption: Prefer a clear unknown-procedure refusal; preserve present empty results as observed compatibility until the owner decides.
```

## temporal.window.paging.release#o04

- page: `.g5/ontology/features/temporal.g5.md`
- statement: Closing mid-read sends one close; a second close or a close after the end sends nothing; a closed reader yields nothing more.
- cases: close, close again, next
- observation: server calls and events
- model locators: .g5/Verus_verification/models/temporal_window_reader/temporal_window_reader.rs::theorem_close_mid_read_once; .g5/Verus_verification/models/temporal_window_reader/temporal_window_reader.rs::theorem_exhaustion_frees_without_close
- design receipts: .g5/Verus_verification/results/temporal_window_reader/20261116T160858Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/temporal_window_reader/20261115T042304Z-binding/receipt.json
- model premises: close mid-read proved right after the opening page

Block text:

```
[I · temporal.window.paging.release]

The server handle of a paged read is freed exactly once, by whichever comes first: the server's last page, the caller's close, a failed page, the end of a `with` block, or garbage collection.
- A window that fits the first page is answered and freed inside the opening call. That costs one round trip, and no close call follows.
- When a later page comes back marked done, the server has freed the handle itself, so the reader makes no close call either.
- Closing before the end sends one close call. Closing again, or after the last page, sends nothing, and the closed reader returns no more events.
- A failed page raises a temporal window error after one close call has freed the handle. A failed opening call raises at the call, and there is no reader to close.
- On the server, closing a handle that is not open does nothing, and asking for the next page of one raises an error instead of returning an empty page.
- A handle belongs to the process and connection that opened it: another connection cannot page it, and the handle is freed when that process ends.
- Today's server never sends an empty page that is not marked done: a page stops only at its row count, its size limit or the end of the window, and each of the first two holds at least one row.
```

## search.fusion.python#o01

- page: `.g5/ontology/architecture/search-storage-and-indexes.g5.md`
- statement: RRF uses each entity's first (1-based) position per list
- cases: duplicate entity at positions 1 and 3 -> rank 1
- observation: fused order
- model locators: .g5/Verus_verification/models/fusion_ranking/fusion_ranking.rs::theorem_first_occurrence_wins
- design receipts: .g5/Verus_verification/results/fusion_ranking/20261116T160726Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/fusion_ranking/20261115T061036Z-binding/receipt.json
- model premises: (none)

Block text:

```
[D · search.fusion.python]

The exported Python `RRFFusion.fuse_results` uses each entity's first position in each list, starting at one, and adds nothing for a missing entity. It ignores the providers' score magnitudes, returns each entity once in descending fused score, and promises no order between tied scores.

- `HybridSearchFusion.multi_modal_search` fuses the legs that completed and returns at most k entities with their fused rank and each retained leg's first score and position. A successful graph expansion is another ranked leg.
- These Python helpers' shipped behavior is settled; whether to keep them as supported public API is [open](../../Verus_verification/open_questions.md#HD-0705).

- Working assumption: Treat the three as compatibility surfaces and qualify each: RRFFusion is a pure standard-RRF helper (document that its rule differs from engine `kg_RRF_FUSE`, HD-0702); HybridSearchFusion is de facto public (migration guide) and graph-scoped; TextSearchEngine is exported but reads every graph and its document search cannot reach the IVG Schema, so it is not a supported reader of graph-scoped data. Prefer deprecation with migration advice (to `kg_TXT` / `bm25_search`) or a `graph=` argument; do not remove without a compatibility decision.
```

## ledger.readers.history#o04

- page: `.g5/ontology/features/ledger.g5.md`
- statement: A full page returns its last seq as the cursor (also when final); a short or empty page returns none
- cases: exactly full final page: cursor then empty page vs short page: no cursor
- observation: history() page rows and next cursor
- model locators: .g5/Verus_verification/models/history_paging/history_paging.rs::theorem_full_page_supplies_cursor; .g5/Verus_verification/models/history_paging/history_paging.rs::theorem_short_or_empty_page_ends; .g5/Verus_verification/models/history_paging/history_paging.rs::theorem_after_last_is_empty
- design receipts: .g5/Verus_verification/results/history_paging/20261116T160735Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/history_paging/20261115T171553Z-binding/receipt.json
- model premises: explicit provider fragment (SqlUpperAscii); decoded cursor input domain

Block text:

```
[I · ledger.readers.history]

History filters the current revision rows before it sorts and limits a page. Oldest-first pages exclude the cursor sequence and everything older; newest-first pages exclude it and everything newer, while integer zero starts at the newest revision.
- A full nonempty page returns its last sequence as the next cursor, even when it is the final full page. A short or empty page returns no cursor, so an exactly full final page needs one extra empty read.
- Time bounds include equality. A filter set to None is omitted; empty text is still a supplied filter.
- Text comparisons follow the database: this provider accepts ASCII case changes and trailing spaces or tabs, but interior JSON spacing still matters for stored source text. Decoding that source for display is a separate step.
- A zero limit returns an empty page, and IRIS refuses a negative one. A failed read or required-field decode raises instead of becoming an empty page. Each acquired cursor gets one close attempt.
- Pages are live reads, not one fixed snapshot. Text "0" is tested as true before cursor conversion, so in newest-first order it selects sequences below zero instead of the initial page. The scope of exact text matching is [open](../../Verus_verification/open_questions.md#q-iter-003).

- Working assumption: Preserve current database comparison for compatibility and expose the difference from binary Python identity; a portable text rule needs owner choice.
```

## temporal.stats.distinct#o06

- page: `.g5/ontology/features/temporal.g5.md`
- statement: An empty window answers 0.
- cases: no target vs one target
- observation: estimate
- model locators: .g5/Verus_verification/models/temporal_stats/temporal_stats.rs::theorem_distinct_empty_is_zero
- design receipts: .g5/Verus_verification/results/temporal_stats/20261117T072022Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/temporal_stats/20261117T065845Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · temporal.stats.distinct]

A distinct-target read estimates how many distinct targets one source's edges of one predicate reach, or every source's when no source is named.
- With no source named, an empty predicate means every predicate. With a source named, today an empty predicate fails with a server subscript error.
- It merges the sketches of every bucket the window touches, so a target outside the window in a touched bucket counts.
- An empty window answers 0, and the estimate must stay within about a quarter of the true number.
- Today any window that holds at least one target answers at least 11, so one target answers 11 and the error is large below about 40 targets.
- A delete rebuilds the sketch from the surviving edges; a raw purge keeps it; a bucket-range purge removes it.
```

## query.aql#o05

- page: `.g5/ontology/features/cypher.g5.md`
- statement: Against a literal null on the right, == becomes IS NULL and != becomes IS NOT NULL
- cases: x == null vs x != null
- observation: translated predicate
- model locators: .g5/Verus_verification/models/aql_frontend/aql_frontend.rs::theorem_null_operators; .g5/Verus_verification/models/aql_frontend/aql_frontend.rs::resolve
- design receipts: .g5/Verus_verification/results/aql_frontend/20261116T160713Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/aql_frontend/20261115T183339Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · query.aql]

`execute_aql` translates AQL into Cypher and passes that text and its bindings to the Cypher reader. For traversal depth, a single integer becomes equal lower and upper bounds; `1..2` keeps both integer bounds, while a decimal depth raises `AQLParseError` before execution.

- Against a literal null on the right, equality becomes `IS NULL` and inequality becomes `IS NOT NULL`. The string `"null"` stays a string comparison, and other operators keep their comparison form.
- This is a translation contract. It does not prove traversal results, Cypher null semantics, bound-parameter null rewriting or the whole AQL language.
```

## query.values.ordering#o03

- page: `.g5/ontology/features/cypher.g5.md`
- statement: r.p < 2 keeps a relationship with p 'x' (RETURN reads 'x') while the node with p 'x' is dropped
- cases: 'x' on a relationship vs a node
- observation: WHERE rows and RETURN
- model locators: .g5/Verus_verification/models/typed_equality/typed_equality.rs::theorem_rel_text_orders_as_cast
- design receipts: .g5/Verus_verification/results/typed_equality/20261116T173044Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/typed_equality/20261116T173137Z-binding/receipt.json
- model premises: cast premise

Block text:

```
[I · query.values.ordering]

A `WHERE` ordering comparison (`<`, `>`, `<=`, `>=`) between a stored property and a number literal treats node and relationship properties differently.
- A node property orders only when it holds a stored number; a string or boolean is null against a number, so the row is dropped, as openCypher requires.
- A relationship property is cast from its qualifier text to a number: numeric text orders by its value, a JSON boolean orders as 1 or 0, text with a leading number orders by that number (`"12abc"` as 12), and any other text, including the empty string, orders as 0.
- So `r.p < 2` keeps a relationship whose `p` is `"x"`, while `RETURN r.p` reads `"x"`; the same node property is dropped.
- Comparisons between two stored properties, and against a boolean, already use Cypher orderability on both kinds.
```

## ledger.commit.caller-transaction#o08

- page: `.g5/ontology/features/ledger.g5.md`
- statement: An uncounted nested refusal (e.g. inconsistent) holds the head but not the counter row; the competing lock-timeout is counted and the count survives the caller's rollback
- cases: nested inconsistent: other's lock +1 vs nested counted commit: other's lock +0
- observation: ledger stats
- model locators: .g5/Verus_verification/models/ledger_client/ledger_client.rs::theorem_uncounted_nested_refusal_leaves_the_counter_row; .g5/Verus_verification/models/ledger_client/ledger_client.rs::theorem_caller_transaction_holds_the_head
- design receipts: .g5/Verus_verification/results/ledger_client/20261118T013558Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/ledger_client/20261117T225756Z-binding/receipt.json
- model premises: (none)

Block text:

```
[D · ledger.commit.caller-transaction]

A commit made inside the caller's open transaction is part of that transaction. The caller's rollback removes the revision and its changes without leaving a gap in the numbering, and frees the changeset's idempotency key. The head stays locked until the caller's transaction ends, so another connection's commit waits for the lock timeout and fails with `LedgerLockTimeoutError`, changing nothing.

- Enabling the ledger and redaction refuse to run inside a caller's transaction.
- A refused commit inside the caller's transaction is never counted: IVG takes back its own part of the transaction, and the count goes with it.
- A commit inside the caller's transaction that touched the ledger's counter row keeps that row locked until the transaction ends: a written or replayed commit, or a refusal of a kind that is normally counted. Meanwhile another connection's refused commit fails after about 40 seconds, not 30, and is not counted, and any other counter change made elsewhere, such as a strict-mode refusal count, is lost ([finding](../../Verus_verification/bugs_issues.md#bug-led-014)).
- A commit refused without a count (for example `inconsistent`) holds only the head, so the other connection's refusal comes after 30 seconds and is counted.
- Today the caller's transaction can hold the counter row without the head: after the caller's own commit timed out waiting for the head, or, once the caller has written in the transaction, after a strict-mode refusal or a `verify()` made through an engine built on the caller's connection. Until that transaction ends, every other connection's valid commit waits about 10 seconds and fails with `LedgerInconsistencyError` ("stats save failed"), writing nothing ([finding](../../Verus_verification/bugs_issues.md#bug-led-017)).
- Intended: counting is bookkeeping, done "in its own small transaction", and `LedgerInconsistencyError` means the ledger's own structures disagree. So a valid commit should not fail because another transaction holds the counter row.
- The caller's rollback also takes back that caller's own counter changes.
```

## search.knn.threshold#o01

- page: `.g5/ontology/features/search.g5.md`
- statement: vector_search / edge_vector_search with no threshold keep every score eligible
- cases: no threshold, k=3 over 3 rows -> 3 rows
- observation: returned rows
- model locators: .g5/Verus_verification/models/vector_threshold/vector_threshold.rs::theorem_no_threshold_keeps_all; .g5/Verus_verification/models/vector_threshold/vector_threshold.rs::theorem_omitted_threshold_has_one_vector
- design receipts: .g5/Verus_verification/results/vector_threshold/20261116T160907Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/vector_threshold/20261115T070051Z-binding/receipt.json
- model premises: scores supplied as exact scaled integers by a ranked provider

Block text:

```
[I · search.knn.threshold]

The generic `vector_search` and graph-routed `edge_vector_search` apply an optional cosine score threshold before taking their highest-scoring rows. Omitting it keeps all scores eligible; giving it keeps scores equal to or above it, so a score of 0.5 survives a threshold of 0.5 and a score of 0.25 does not.

- Both bind the threshold in a WHERE predicate on the cosine expression, repeating the query-vector bind for that expression. The optional graph predicate combines with that filter; sorting follows it.
- This rule concerns these two helpers, not every KNN, IVF, fusion or Cypher search surface.
```

## install.legacy#o03

- page: `.g5/ontology/operations/setup-and-upgrade.g5.md`
- statement: dry_run=False removes exactly the listed objects that are IVG's
- cases: IVG-owned vs operator-owned same-named objects
- observation: catalog after
- model locators: (none)
- design receipts: (none)
- as-built evidence: upstream-test not-run-here tests/e2e/test_463_legacy_same_named_functions_e2e.py
- model premises: (none)

Block text:

```
[I · install.legacy]

Legacy objects are removed only when an operator asks. The default call lists the legacy objects present and changes nothing, and the removing call removes exactly those listed objects that are IVG's. The result reports truthfully, per object, whether it was removed, and running the call again lists what remains. The removing call refuses to run inside a caller's open transaction.

- Working assumption: Inventory both install paths. The product contract (spec 262 schema, inventory test) covers initialize_schema only. scripts/deploy_production.py + sql/schema.sql + sql/operators_fixed.sql form a reachable legacy path that produces a non-conforming namespace (DDL-only before its class step, unqualified procedures). sql/fraud_sample_data.sql is maintained demo data. Files with no loader are historical material.
- Working assumption: Classify sql/operators.sql as shipped historical/reference SQL with no deployment path. It is outside the executed product surface, but stays in the inventory as a shipped artifact whose definitions are not graph-scoped. Trace operators_fixed.sql (legacy deployer) and the schema.py procedures separately. If anyone runs the file by hand, it creates unqualified, graph-blind procedures (F-0820-like behaviour).
```

## redaction.metadata.exception#o03

- page: `.g5/ontology/features/redaction.g5.md`
- statement: The four-field update is allowed only when the redaction's context names the row.
- cases: update in redaction context vs outside
- observation: update outcome
- model locators: .g5/Verus_verification/models/ledger_client/ledger_client.rs::theorem_revision_rows_immutable; .g5/Verus_verification/models/ledger_client/ledger_client.rs::update_allowed
- design receipts: .g5/Verus_verification/results/ledger_client/20261118T013558Z-prove/receipt.json
- as-built evidence: upstream-test passed tests/integration/test_256_ledger_redaction_e2e.py; inspection read iris_src/src/Graph/KG/LedgerRevision.cls
- model premises: (none)

Block text:

```
[D · redaction.metadata.exception]

Clearing those four fields is the only change ever allowed to a revision row. It is allowed only to the redaction itself, for a revision that already has a tombstone, and only to empty those fields. Every other update and every delete is still refused.
```

## temporal.edge.clock#o11

- page: `.g5/ontology/features/temporal.g5.md`
- statement: On a duplicate explicit positive timestamp the normal bulk path reports count 0 and one collision, the fallback reports count 1 and no collision, and the stored event is unchanged on both.
- cases: occupied coordinate via Counts vs prewrite fallback
- observation: returned counts and stores
- model locators: .g5/Verus_verification/models/temporal_clock/temporal_clock.rs::theorem_duplicate_counts_differ
- design receipts: .g5/Verus_verification/results/temporal_clock/20261116T160855Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/temporal_clock/20261115T182957Z-binding/receipt.json
- model premises: t != 0, coordinate occupied

Block text:

```
[D · temporal.edge.clock]

Timestamp normalization and the selected writer determine the stored coordinate,
so fixed-coordinate repeatability requires the same resolved event times.

- Single Python omission, None and explicit zero reach the single writer as text zero and remain epoch zero; a normal bulk zero uses each item's current seconds.
- If the bulk endpoint is unavailable before writing, its single-edge fallback stores that same zero at epoch zero. Explicit positive timestamps retain event time on all three paths.
- Bulk items require a usable timestamp; all items are validated and normalized before the first write, while an empty batch succeeds with count zero.
- Numeric short alias `ts=0` defers to a supplied long `timestamp` alias, while text `ts="0"` keeps zero. A present None long alias can fail conversion where an absent long alias defaults to zero.
- On a duplicate explicit positive timestamp, normal bulk reports a collision and zero writes; fallback counts the successful single call and cannot report the collision. The stored existing event remains unchanged.
```

## access.health.lifecycle#o09

- page: `.g5/ontology/operations/status-and-repair.g5.md`
- statement: A second raised exception stops the retry, leaving the replacement engine cached
- cases: two raised exceptions
- observation: result and cache state
- model locators: .g5/Verus_verification/models/service_health/service_health.rs::theorem_second_query_exception_stops
- design receipts: .g5/Verus_verification/results/service_health/20261116T160847Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/service_health/20261115T181721Z-binding/receipt.json
- model premises: sequential requests under the engine lock; named provider ports for constructor, probe, record and close; ASCII schema names

Block text:

```
[D · access.health.lifecycle]

Health reflects both the probe and the engine retained by the app.

- The sample API captures its engine when created. Failed automatic construction or first connection access still starts an app, but health stays unavailable until recreation; an already-bound engine can recover when its probe succeeds again.
- Injecting an engine whose first connection access fails raises during app creation, rather than starting the engine-absent app.
- The Cypher HTTP server constructs an engine when its cache is empty and retries failed construction on a later request. A later health-query failure retains that engine; a successful probe on it can recover health.
- Reset tries to close the engine and clears the cache even if close raises, allowing later replacement. A normal query's first raised exception resets and retries once; a folded result error does not reset, and a second exception stops with the replacement cached.
```

## ledger.commit.caller-transaction#o11

- page: `.g5/ontology/features/ledger.g5.md`
- statement: Intended: counting is bookkeeping and never makes a valid commit fail
- cases: counter row held elsewhere: valid commit should still be written; as built it is refused inconsistent (bug-led-017)
- observation: commit result
- model locators: .g5/Verus_verification/models/ledger_client/ledger_client.rs::theorem_held_counter_row_refuses_a_valid_commit; .g5/Verus_verification/models/ledger_client/ledger_client.rs::theorem_in_transaction_row_save_blocks_other_writers
- design receipts: .g5/Verus_verification/results/ledger_client/20261118T013558Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/ledger_client/20261117T225756Z-binding/receipt.json
- model premises: (none)

Block text:

```
[D · ledger.commit.caller-transaction]

A commit made inside the caller's open transaction is part of that transaction. The caller's rollback removes the revision and its changes without leaving a gap in the numbering, and frees the changeset's idempotency key. The head stays locked until the caller's transaction ends, so another connection's commit waits for the lock timeout and fails with `LedgerLockTimeoutError`, changing nothing.

- Enabling the ledger and redaction refuse to run inside a caller's transaction.
- A refused commit inside the caller's transaction is never counted: IVG takes back its own part of the transaction, and the count goes with it.
- A commit inside the caller's transaction that touched the ledger's counter row keeps that row locked until the transaction ends: a written or replayed commit, or a refusal of a kind that is normally counted. Meanwhile another connection's refused commit fails after about 40 seconds, not 30, and is not counted, and any other counter change made elsewhere, such as a strict-mode refusal count, is lost ([finding](../../Verus_verification/bugs_issues.md#bug-led-014)).
- A commit refused without a count (for example `inconsistent`) holds only the head, so the other connection's refusal comes after 30 seconds and is counted.
- Today the caller's transaction can hold the counter row without the head: after the caller's own commit timed out waiting for the head, or, once the caller has written in the transaction, after a strict-mode refusal or a `verify()` made through an engine built on the caller's connection. Until that transaction ends, every other connection's valid commit waits about 10 seconds and fails with `LedgerInconsistencyError` ("stats save failed"), writing nothing ([finding](../../Verus_verification/bugs_issues.md#bug-led-017)).
- Intended: counting is bookkeeping, done "in its own small transaction", and `LedgerInconsistencyError` means the ledger's own structures disagree. So a valid commit should not fail because another transaction holds the counter row.
- The caller's rollback also takes back that caller's own counter changes.
```

## adapters.embedded.no_data#o03

- page: `.g5/ontology/architecture/adapters.g5.md`
- statement: The no-row rule applies when SQLCODE 100 is on the error or its cause, on any of the three paths.
- cases: cause100 on the third path -> empty; code 100 on prepared path -> empty
- observation: cursor result
- model locators: .g5/Verus_verification/models/embedded_no_data/embedded_no_data.rs::theorem_no_data_on_every_path; .g5/Verus_verification/models/embedded_no_data/embedded_no_data.rs::theorem_no_data_is_empty
- design receipts: .g5/Verus_verification/results/embedded_no_data/20261116T160723Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/embedded_no_data/20261115T042852Z-binding/receipt.json
- model premises: control ignore-cause EXPECTED_FAIL

Block text:

```
[I · adapters.embedded.no_data]

A no-row statement is an empty result with row count 0, not an error. Every other error still raises.
- The rule keys on SQLCODE 100, on the error itself or on the error that caused it, whichever of the three paths ran.
- When the written-in path meets SQLCODE 100 it returns no result, and for `UPDATE`, `DELETE` and `INSERT` the cursor reports row count 0 for that too.
- After a statement that did change rows, the row count is -1, not the number changed. Only a no-row statement reports 0.
- A batch call runs the statement once for each row and reports how many rows it ran, no-row statements included. Any other error stops the batch and raises.
```

## install.status.capabilities#o03

- page: `.g5/ontology/operations/status-and-repair.g5.md`
- statement: sync() sets kg_built only in the calling engine's cache and never sets nkg_built or the markers
- cases: syncing engine vs another engine after sync()
- observation: engine.capabilities
- model locators: .g5/Verus_verification/models/operator_reports/operator_reports.rs::theorem_markers_never_set_after_empty_setup; .g5/Verus_verification/models/operator_reports/operator_reports.rs::sync_eng; .g5/Verus_verification/models/operator_reports/operator_reports.rs::lemma_markers_kept
- design receipts: .g5/Verus_verification/results/operator_reports/20261117T045706Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/operator_reports/20261117T045659Z-binding/receipt.json
- model premises: declared adjacency index; KGEdgeCount below its 10000 cap; no Arno library; P-COLLATE (IRIS DISTINCT answers SQLUPPER, observed); probe failures as inputs

Block text:

```
[I · install.status.capabilities]

`engine.capabilities` says what the namespace has deployed. Each engine reads it once, from the class dictionary and two markers that setup writes when it finds edge rows to build from.
- `sync()` sets `kg_built` only in the engine that ran it and never sets `nkg_built` or the markers.
- So on a namespace set up while empty, every engine created later reads `kg_built` and `nkg_built` False whatever is built, until setup runs again while edges exist. Meanwhile personalized PageRank skips its ObjectScript fast path in those engines ([bug-plt-117](../../Verus_verification/bugs_issues.md#bug-plt-117)).
- Running setup again re-detects the capabilities and sets both markers once edges exist, from any engine.
- Working assumption: the store's `capabilities()` is a fixed list of what the adapter implements, every algorithm True, with only the Arno entries live; it is not a report of what this namespace can run. Read availability from `engine.capabilities` and `status()` ([open question](../../Verus_verification/open_questions.md#HD-1703)).
```

## ledger.observability#o05

- page: `.g5/ontology/operations/ledger.g5.md`
- statement: While another transaction holds the counter row, no outcome of this connection is counted
- cases: row held elsewhere: any outcome +0 vs free: counted
- observation: stats
- model locators: .g5/Verus_verification/models/ledger_client/ledger_client.rs::theorem_uncounted_outcomes
- design receipts: .g5/Verus_verification/results/ledger_client/20261118T013558Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/ledger_client/20261117T225756Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · ledger.observability]

Each commit that reaches the ledger's server reports its outcome once: a log line and one event to each registered metrics hook. Most outcomes are also counted in the ledger's counters.

- The counters keep the commits written (the genesis included), the replays, and these refusals: a stale or unknown expected head, an idempotency conflict (a key whose revision was redacted included), a failed operation, too many operations, a disabled ledger and a lock timeout. Strict-mode refusals are counted too.
- These outcomes reach a hook but no counter: a refusal before the first enable, a commit refused because it writes into an unfinished redaction's target, and an `inconsistent` refusal, such as a revision field longer than its column ([size](../features/ledger.g5.md#ledger.commit.size)).
- A refused commit made inside the caller's own transaction is never counted. A strict-mode refusal count or a verify record made on the caller's connection inside its transaction is kept or taken back with that transaction ([caller's transaction](../features/ledger.g5.md#ledger.commit.caller-transaction)).
- While another caller's open transaction holds the counter row, no other connection's outcome is counted. Today, when that transaction does not also hold the head, another connection's valid commit is refused as `inconsistent` instead of being written ([caller's transaction](../features/ledger.g5.md#ledger.commit.caller-transaction)). Intended: counting never changes a commit's outcome.
- A refusal the client makes before sending (an empty changeset or a bad operation reference) is neither counted nor reported to a hook ([finding](../../Verus_verification/bugs_issues.md#bug-doc-013)).
- A hook that raises is logged, and the commit's result does not change.
```

## query.aggregation.keys#o04

- page: `.g5/ontology/features/cypher.g5.md`
- statement: The native executor groups by typed value, so a grouped query over a number and its spelling answers different groups on the two paths
- cases: same query and data with native on vs off
- observation: group rows on each path
- model locators: .g5/Verus_verification/models/cypher_clauses/cypher_clauses.rs::theorem_paths_disagree_exactly_on_marked_text; .g5/Verus_verification/models/cypher_clauses/cypher_clauses.rs::theorem_native_group_follows_rule
- design receipts: .g5/Verus_verification/results/cypher_clauses/20261117T072020Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/cypher_clauses/20261117T065639Z-binding/receipt.json
- model premises: native Exec.GroupOf/KeyValues transcribed (inspected)

Block text:

```
[I · query.aggregation.keys]

Grouping keys, `DISTINCT` and `count(DISTINCT)` treat two values as one when they are [equal](#query.values.equality), on both paths. A number and a string are never one value, so the integer 1 and the string "1" are two groups. Whether an integer and a float of equal value, such as 1 and 1.0, are one value is [still open](../../Verus_verification/open_questions.md#query.aggregation.keys.numbers); openCypher compares numbers by value.
- Today on the SQL path a grouping key, `count(DISTINCT)` and `WITH DISTINCT` compare a stored value's text. So a stored number and the string that spells it (1 and "1", 1.0 and "1") are one group, whose key reads as one of them, while `RETURN DISTINCT` and `collect(DISTINCT)` keep them apart ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-135)).
- Today the native executor groups by type, so the same grouped query answers different groups on the two paths ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-136)).
- Over a list the query holds, `UNWIND [1, '1'] AS k` also gives one group and one `DISTINCT` row.
- A boolean and the string that spells it are one stored value ([documented known issue](../../../docs/KNOWN_ISSUES.md#L332-L368)), so they stay one group on both paths.
- Working assumption: an integer and a float of equal value (1 and 1.0) are two groups, as the native executor answers; this is provisional.
- Today on the SQL path, for stored properties, a grouping key and `count(DISTINCT)` make 1 and 1.0 one value, while `RETURN DISTINCT` keeps them apart. Over a list the query holds, `RETURN DISTINCT` and `UNION` also make them one row (`UNWIND [1, 1.0] AS x RETURN DISTINCT x` and `RETURN 1 AS x UNION RETURN 1.0 AS x` each answer one row). Which side departs depends on the open question.
- Today over a list the query holds, a grouping key and `count(DISTINCT)` also make the integer 1 and `true` (0 and `false`) one value, and a list and the string spelling it (`[1]` and `'[1]'`) one value, while `RETURN DISTINCT` keeps them apart. The string `'true'` and `true` stay two groups ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-149)).
```

## search.embedding.queue#o04

- page: `.g5/ontology/architecture/search-storage-and-indexes.g5.md`
- statement: Provider failure, empty answer, unknown config or a storing failure ends the entry as ERROR with a reason, never DONE
- cases: provider fails/answers nothing (IRIS worker) -> DONE without vector or reason; Python worker -> ERROR with reason
- observation: GetEntry status/reason and get_embedding
- model locators: .g5/Verus_verification/models/embed_queue/embed_queue.rs::theorem_python_worker_meets_rule; .g5/Verus_verification/models/embed_queue/embed_queue.rs::theorem_iris_unanswered_marked_done; .g5/Verus_verification/models/embed_queue/embed_queue.rs::theorem_iris_default_graph_never_stores
- design receipts: .g5/Verus_verification/results/embed_queue/20261117T001459Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/embed_queue/20261117T001547Z-binding/receipt.json
- model premises: entries for nodes present in their graph (node_in_graph); provider outcomes are environment inputs

Block text:

```
[I · search.embedding.queue]

Queued embedding work is checked before it is queued, against the identity of the table it will be written to. A worker fails each entry that asks for a model it does not produce, and the rest of the batch continues.
- An entry whose text cannot be embedded, or whose vector cannot be stored, is marked as an error with the reason, never as done.

- Working assumption: A single active consumer per namespace is the contract (supported by 5bb149ed); model both workers as independently schedulable, treat single-worker as an unenforced premise, and prefer enforcement (refuse a second worker) or documentation; atomic claims with recovery remain the multi-worker alternative.
- Working assumption: one worker at a time is assumed, so entries are not claimed. An entry is marked done before its vector is stored, and is changed to an error if storing then fails.
```

## ledger.readers.diff#o01

- page: `.g5/ontology/features/ledger.g5.md`
- statement: diff(lo,hi) selects records in (lo, hi]
- cases: a change in lo: excluded; in hi: included
- observation: Diff entries
- model locators: .g5/Verus_verification/models/history_diff/history_diff.rs::theorem_range_lower_exclusive; .g5/Verus_verification/models/ledger_content/ledger_content.rs::theorem_named_generated_full_content_endpoints
- design receipts: .g5/Verus_verification/results/history_diff/20261116T160734Z-prove/receipt.json; .g5/Verus_verification/results/ledger_content/20261116T160742Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/history_diff/20261115T065234Z-binding/receipt.json
- model premises: upper inclusion proved for attribute records stamped at hi over a base at or below lo (ledger_content)

Block text:

```
[I · ledger.readers.diff]

A diff selects records after the earlier revision through the later revision, including that later revision. Equal endpoints return no entries; reversing the endpoints swaps each entry's before and after values.

- Within one uninterrupted entity life, each changed attribute shows its first prior and last new value; if those match, the attribute contributes no entry.
- A life created and deleted inside the range contributes no entry. Deleting a life that existed before the range and then recreating it contributes separate deletion and creation entries.
- Node deletion carries its labels and properties in the deletion's JSON snapshot. The reverse existence entry keeps that snapshot; a separate property entry with an absent after value does not by itself say the old life lacked that property.
- As built, changing a property before deleting and recreating the node can lose the range's original value: the snapshot holds the value at deletion, and closing that life drops its earlier attribute prior. The promised net change remains the requirement; this [reported gap](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-led-101) has no product repair here.

- Working assumption: Treat lifecycle diff as an unordered net-change result until a stable script order is specified; consumers must not infer dependency order.
```

## algorithms.op#o08

- page: `.g5/ontology/features/algorithms.g5.md`
- statement: The integer options are accepted exactly in their ranges (topK 0..1,000,000, maxHops 0..1000, sampleSize >= 0, maxIter 1..1000, memBudgetMB 16..8192) and formula/direction only as exact literals.
- cases: topK -1 / maxIter 1001 / memBudgetMB 0 / direction 'OUT' / formula 'Classical': refused vs boundary values accepted
- observation: acceptance vs ValueError
- model locators: .g5/Verus_verification/models/algo_options/algo_options.rs::theorem_ranges; .g5/Verus_verification/models/algo_options/algo_options.rs::theorem_enumerations_exact; .g5/Verus_verification/models/algo_options/algo_options.rs::in_range
- design receipts: .g5/Verus_verification/results/algo_options/20261116T220030Z-prove/receipt.json; .g5/Verus_verification/results/algo_options/20261116T220033Z-control-topk-from-one/receipt.json; .g5/Verus_verification/results/algo_options/20261116T220034Z-control-maxiter-unbounded/receipt.json; .g5/Verus_verification/results/algo_options/20261116T220036Z-control-formula-any-case/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/algo_options/20261116T220059Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · algorithms.op]

Every algorithm answer includes every node of the graph, nodes with no edge too, and the n in any formula is the graph's node count. Ranked answers come highest first, and ties go by node ID in IRIS collation; two scores equal to 12 decimal places are a tie.

- A direction is `out` (along edges), `in` (against them) or `both` (the graph read as undirected).
- PageRank and PPR reject a damping factor outside (0, 1) or an iteration count below 1 with `ValueError` before reading data.
- Operations with a direction reject an unknown direction with `ValueError` before reading data.
- The centrality and community methods and their Cypher procedures (`CALL ivg.*`) accept the same option values and refuse the same ones with `ValueError` before reading data: `topK` 0 to 1,000,000 (0 keeps every row), `maxHops` 0 to 1000, `sampleSize` 0 or more, `maxIter` 1 to 1000, `memBudgetMB` 16 to 8192, `gamma` above 0 up to 100, and `formula` and `direction` spelled exactly. A whole-number string or float is taken as that number; a procedure refuses an option it does not list, naming the ones it does.
- The exceptions to "every node" are betweenness, which lists only nodes that score above 0, and walks and subgraphs, which list what they reach.
```

## temporal.stats.velocity#o08

- page: `.g5/ontology/features/temporal.g5.md`
- statement: In the millisecond class the velocity window is in milliseconds: a window of 300 reaches back 0.3 seconds.
- cases: ms window 300 vs 300000 over two consecutive ms buckets -> 1 vs 2
- observation: velocity
- model locators: .g5/Verus_verification/models/temporal_stats/temporal_stats.rs::velocity
- design receipts: (none)
- as-built evidence: binding AGREES .g5/Verus_verification/results/temporal_stats/20261117T065845Z-binding/receipt.json
- model premises: (none)

Block text:

```
[I · temporal.stats.velocity]

Velocity and burst reads count events from the per-source event counters of every bucket from the one holding now minus the window to the one holding now.
- The bucket holding now counts whole, so an event later than now in that bucket counts too; so does an event up to a bucket before the window's start.
- A source's events over every predicate count. The burst read accepts a predicate and does not use it, although its parameter documentation says it filters.
- A burst read lists a source when its total reaches the threshold, the threshold itself included, and only sources holding a counter in those buckets.
- Now is the caller's timestamp when one is given, otherwise the wall clock in seconds.
- In the millisecond entry point the default now is still in seconds, so an event stored in milliseconds is never counted unless the caller passes now.
- In the millisecond entry point the window is in milliseconds too, although the parameter is named in seconds: a window of 300 reaches back 0.3 seconds.
```

## search.embedding.width#o09

- page: `.g5/ontology/features/search.g5.md`
- statement: The width refusal is raised before any search statement runs, names the query width and the stored width, and compares against the route's recorded width or, when none, the column's declared width
- cases: route width 4, query 3 -> Width{query 3, stored 4}, quiet trace; route width none and catalog 4 -> compared to 4; route width none and no catalog width -> no check
- observation: exception content and statements issued
- model locators: .g5/Verus_verification/models/vector_admission/vector_admission.rs::theorem_whole_raw_row_four_query_three_no_scoring; .g5/Verus_verification/models/vector_admission/vector_admission.rs::theorem_catalog_only_when_literal_and_no_route_width; .g5/Verus_verification/models/vector_admission/vector_admission.rs::theorem_direct_guard_no_score; .g5/Verus_verification/models/vector_admission/vector_admission.rs::theorem_preflight_derived_mismatch
- design receipts: .g5/Verus_verification/results/vector_admission/20261116T160906Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/vector_admission/20261115T214431Z-binding/receipt.json
- model premises: catalog width is a heuristic provider; node KNN entry points

Block text:

```
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
```

## access.api_key.every_route#o03

- page: `.g5/ontology/concepts/access.g5.md`
- statement: Public routes are matched on the exact path; a longer or different path needs the key
- cases: /health vs /health/x or /healthz
- observation: HTTP status
- model locators: (none)
- design receipts: (none)
- as-built evidence: none
- model premises: api_auth.py public list

Block text:

```
[I · access.api_key.every_route]

With the key set, every route needs it except `/health` and the API documentation.

- The public routes are matched on the exact path.
- A route added later needs the key unless it is added to the public list.
- Every HTTP method needs it. A browser's CORS preflight is answered without it and runs no handler.
- A missing or wrong key gets `401` before any handler runs and before the read-only check.
```

## query.system-procedures.results#o07

- page: `.g5/ontology/features/cypher.g5.md`
- statement: Unsupported WHERE expressions and missing parameters raise only when the producer has rows; an empty producer returns no rows without error
- cases: unsupported WHERE on empty vs nonempty labels
- observation: execute_cypher columns, rows or error
- model locators: .g5/Verus_verification/models/procedure_results/procedure_results.rs::theorem_empty_skips_expression_validation; .g5/Verus_verification/models/procedure_results/procedure_results.rs::theorem_unsupported_nonempty_refused
- design receipts: .g5/Verus_verification/results/procedure_results/20261116T160821Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/procedure_results/20261115T182206Z-binding/receipt.json; native OBSERVED .g5/uplift/consolidated/iteration-7/procedure-native.json
- model premises: single-column db.labels provider, scoped Tail/condition variants, nat SKIP/LIMIT

Block text:

```
[D · query.system-procedures.results]

Handled metadata rows apply the following result rules.

- A `YIELD` alias names the value read by `WHERE` and `RETURN`; only a true condition keeps a row, so a comparison with null does not. Filtering precedes `SKIP` and `LIMIT`.
- As built, bare `db.labels() YIELD label AS l` keeps result column `label`, while `RETURN l` projects column `l`. `ORDER BY` reads a returned column and refuses another name even on empty data, so bare `ORDER BY l` refuses while `RETURN l ORDER BY l` succeeds.
- A RETURN list already equal to the physical result columns bypasses source-name validation: `YIELD absent AS label RETURN label` keeps actual label values, while alias `l` refuses on nonempty rows.
- Unsupported WHERE expressions and missing parameters are evaluated only when producer rows exist; an empty producer can return no rows without that error. Unsupported structural clauses such as `MATCH` refuse independently of whether rows exist.
```

## ledger.node-scope#o02

- page: `.g5/ontology/features/ledger.g5.md`
- statement: Node records carry no graph; relationship records carry the relationship's graph
- cases: relationship in named graph g: record names g; default: empty/None normalized
- observation: get_revision record graph field
- model locators: .g5/Verus_verification/models/ledger_content/ledger_content.rs::theorem_raw_graph_tuple_normalization; .g5/Verus_verification/models/ledger_content/ledger_content.rs::theorem_committed_revision_full_content; .g5/Verus_verification/models/ledger_content/ledger_content.rs::theorem_raw_new_rel_uses_own_fresh_counter; .g5/Verus_verification/models/ledger_content/ledger_content.rs::theorem_new_node_emits_separate_content
- design receipts: .g5/Verus_verification/results/ledger_content/20261116T160742Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/ledger_content/20261115T231345Z-binding/receipt.json
- model premises: (none)

Block text:

```
[D · ledger.node-scope]

The ledger keeps nodes in the default graph. Its node operations read and write only default-graph rows, and its node records name no graph. Relationship records name the relationship's own graph.

- One exception: a relationship created in a named graph adds bare node rows for its endpoints in that graph, if they are missing there. The database requires those rows. They get no node records.
- An endpoint counts as existing if its ID exists in any graph.

- Working assumption: Keep graph-blind existence. A node change that needs the default-graph row (`set_prop`, `remove_prop`, `add_label`, `remove_label`, `delete_node`, `upsert_node` with labels or properties) refuses with nothing applied and no record when that row is absent, under a reason distinct from `node_not_found` (the maintainer's meaning of that code stays). Model edge endpoint lookup separately (`EnsureEndpoint`).
```

## query.native.reads-only#o04

- page: `.g5/ontology/architecture/query-execution.g5.md`
- statement: Chained statements take the SQL path
- cases: single statement vs chained statements
- observation: which path answers
- model locators: .g5/Verus_verification/models/native_admission/native_admission.rs::chain_part; .g5/Verus_verification/models/native_admission/native_admission.rs::theorem_chained_part_runs_natively
- design receipts: .g5/Verus_verification/results/native_admission/20261118T022637Z-prove/receipt.json; .g5/Verus_verification/results/native_admission/20261118T021733Z-control-chained-part-keeps-chain/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/native_admission/20261118T022729Z-binding/receipt.json
- model premises: execute_cypher's chained loop

Block text:

```
[I · query.native.reads-only]

No write runs on the native executor. A query with a write clause anywhere, a procedure call, a `UNION` or chained statements takes the SQL path.

- A read step inside a write, such as the `MATCH` before a per-row `MERGE`, may still run natively; it then sees the write's own uncommitted changes.
```

## query.functions.slice#o02

- page: `.g5/ontology/features/cypher.g5.md`
- statement: A negative slice bound counts from the end, literal or run-time
- cases: l[-3..5] / l[0..-1] literal vs run-time
- observation: the execute_cypher result row (SQL path; the native executor declines these shapes)
- model locators: .g5/Verus_verification/models/cypher_exprs/cypher_exprs.rs::translated_bound; .g5/Verus_verification/models/cypher_exprs/cypher_exprs.rs::theorem_row_negative_slice_departs
- design receipts: .g5/Verus_verification/results/cypher_exprs/20261117T044807Z-prove/receipt.json; .g5/Verus_verification/results/cypher_exprs/20261117T044808Z-control-row-slice-wrapped/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/cypher_exprs/20261117T044717Z-binding/receipt.json
- model premises: 0 < k < len; witness family l[-k..len] and l[0..-k]

Block text:

```
[I · query.functions.slice]

`list[a..b]` gives the elements from position `a` up to, but not including, `b`. A negative bound counts from the end, a bound past either end is clamped to the list, and a null bound gives null.
- Today this holds for bounds written in the query and for run-time bounds of 0 or more. A negative bound known only at run time counts as 0, so `l[-3..5]` gives the whole list and `l[0..-1]` gives `[]` ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-117)).
- Today a lower bound that is a variable name does not parse: `l[a..3]`, `l[a..b]` and `l[a..]` are refused, while `l[$a..3]` and `l[x[0]..3]` work ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-122)).
- Today slicing a null list gives `[]` instead of null ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-129)). With the fixture's driver a slice of a parameter list by parameter bounds (`$l[$s..$e]`) fails, while `WITH $l AS l RETURN l[$s..$e]` works ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-125)).
```

## ledger.verify.meaning#o01

- page: `.g5/ontology/operations/ledger.g5.md`
- statement: No integrity check beyond replay covers the records: a record edit that still replays to the current tables verifies equal
- cases: edited record consistent with the tables: equal vs edited record inconsistent: diverges
- observation: verify status
- model locators: .g5/Verus_verification/models/ledger_verify/ledger_verify.rs::theorem_equal_iff_views_agree
- design receipts: .g5/Verus_verification/results/ledger_verify/20261118T013559Z-prove/receipt.json
- as-built evidence: binding AGREES .g5/Verus_verification/results/ledger_verify/20261117T212044Z-binding/receipt.json
- model premises: quiescent inputs

Block text:

```
[D · ledger.verify.meaning]

"Verifiable" means that replaying the history gives the current store. No hash chain covers the records, and the commit fingerprint exists only to recognize retries.
```
