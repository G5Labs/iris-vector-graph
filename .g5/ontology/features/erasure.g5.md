# Erasure

Erasure removes graph content from every store that holds it, as one operation. It removes content, not history: the revision ledger's records survive until they are [redacted](redaction.g5.md). See the [ledger](ledger.g5.md) for revisions and statements.

## Definitions

- **Erase**: remove content from every store that holds it.
- **Store**: one place IVG keeps content. Stores include the SQL tables (nodes, labels, properties, relationships, documents, embeddings, reifications, FHIR side tables), the adjacency index, the temporal index, other graph-scoped native indexes and caches, and the ledger's statement index.
- **Routed embedding table**: an embedding table created for one graph and model. The embedding registry names it and is the authority for it.
- **Live statement**: a ledger statement entry that says its relationship still exists.
- **Ledger history**: the ledger's records and revision rows.
- **Eraser**: the database-side class that performs every erase.

## What an erase removes

<a id="erasure.scope"></a>
[I · erasure.scope]

An erase removes a graph's content from every store that holds it: its rows, its adjacency and temporal entries, its other graph-scoped indexes and caches, and the ledger's statement entries for that graph.

- Another graph's content is never touched, even where it uses the same node IDs.
- The default graph is erased in both of its spellings: an empty graph ID and a missing one.
- A graph name that cannot be stored safely is refused before anything is deleted.

<a id="erasure.live-statements"></a>
[I · erasure.live-statements]

No live ledger statement may outlive its content. Erasing a graph removes all of the graph's statement entries and their lookups. Erasing nodes or relationships removes the live statements of the relationships it deletes.

<a id="erasure.history"></a>
[D · erasure.history]

An erase never removes ledger history: records and revision rows survive, because one revision can describe several graphs. Removing an erased target's content from history is a separate, explicit step ([redaction](redaction.g5.md#redaction.purpose)).

- So erasure alone is not a privacy tool. Documentation that mentions erasure and data deletion together must say so.
- An empty graph check after an erase means nothing live is stranded. It does not mean the ledger has no record of the graph.

<a id="erasure.kept"></a>
[D · erasure.kept]

A graph erase keeps configuration and stores that belong to no single graph.

- A graph's temporal-only predicate settings and FHIR registration survive, so a re-ingest behaves as before. The erase clears the graph's multigraph mode and resets a FHIR graph's watermarks.
- The embedding quarantine is never touched by any erase, because its rows are the only copy of vectors whose graph is unknown. Whether the document and edge-vector quarantines are kept too is part of an [open question](search.g5.md#search.quarantine.retention).
- Stores that record no graph are emptied by an erase of all graphs; what a single-graph erase must do to the search indexes among them is [open](search.g5.md#search.erasure.indexes).

## How an erase runs

<a id="erasure.atomic"></a>
[D · erasure.atomic]

An erase runs as one transaction that the database-side Eraser owns. It either completes or leaves the content untouched. On any failure it rolls back and raises instead of returning a count.

- An erase never commits or rolls back work that a caller's open transaction holds. When it joins that transaction, the caller's commit or rollback decides the outcome ([open choice](#erasure.atomic.caller-transaction)).
- Today, without a caller's transaction, erasing a list of node IDs or relationships commits once per 500 entries, so a failure keeps the earlier entries erased.

<a id="erasure.atomic.caller-transaction"></a>
[Q · erasure.atomic.caller-transaction]

When a caller's transaction is open, should erasing a graph or erasing everything join that transaction or refuse to run? There is no provisional answer. The node, prefix and relationship erases already join it.

- Join it: run the erase on the caller's own connection, as those erases do.
- Refuse it, as snapshot restore, enabling the ledger and redaction do.
- Run outside it, and document that, as the temporal stores' writes are.

<a id="erasure.atomic.routes"></a>
[D · erasure.atomic.routes]

Routed embedding tables are emptied inside the transaction and dropped after it commits, and only when the registry claims them. If a drop fails, the erase still counts as complete and leaves an empty table with its registry row. A table the registry does not name is emptied but never dropped.

<a id="erasure.count"></a>
[D · erasure.count]

An erase returns the number of node and relationship rows it removed. Zero means that no node or relationship row matched, which is not an error. Derived stores are not counted.

<a id="erasure.entry-points"></a>
[I · erasure.entry-points]

The Eraser has these entry points, and every erase call of the engine uses one of them:

- Erase a graph: everything in one graph.
- Erase all: every graph, plus the stores that cannot be split by graph.
- Erase nodes by ID prefix in one graph, with what hangs off them there ([how the prefix matches](#erasure.prefix-match)). An empty prefix is refused, because that would be a graph erase.
- Erase a list of node IDs in one graph, with their relationships in that graph.
- Erase a list of relationships in one graph, leaving nodes alone.

<a id="erasure.entry-points.single-path"></a>
[D · erasure.entry-points.single-path]

Every path that deletes graph content goes through the Eraser's transaction. A path that removes content from one store but not the others is a defect, not a mode.

- The old graph-drop call is only a deprecated name for a graph erase.
- The old adjacency-only delete survives only as a deprecated name for a relationship erase, and must be refused in strict mode like the other erases.

<a id="erasure.prefix-match"></a>
[D · erasure.prefix-match]

Erasing by prefix matches a plain, exact, case-sensitive start of the node ID, with no separator rule. To erase one tenant, pass the prefix with its separator, such as `tenant|`. Otherwise `acme` would also erase `acme-health|…` nodes, which a redaction of `acme` does not match.

- Whether erasing by prefix should also require the separator, as redaction does, is open; a bare prefix irreversibly erases a neighbouring tenant.
- Today the prefix erase finds IDs through node rows, so content of an ID with no node row is not erased: temporal-only events and property rows.

<a id="erasure.concurrency"></a>
[Q · erasure.concurrency]

Must an erase exclude ledger commits and redactions that run at the same time? Today an erase does not take the ledger's head lock, and a redaction can see an erase that has not yet committed. There is no provisional answer.

- An erase takes the head lock while the ledger is enabled.
- A redaction waits for uncommitted erases.
- The risk is accepted and documented.

## Metadata

### erasure.scope

- Sources: [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md#L8-L23), [CONTEXT.md Erasure](../../../CONTEXT.md#L194-L205), [Eraser.cls EraseGraph](../../../iris_src/src/Graph/KG/Eraser.cls#L37-L306)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live tests: `tests/integration/test_erase_graph.py` (rows, adjacency, degree cache, temporal index, both default-graph spellings, another graph untouched, invalid name). Observed divergence: the BM25, vector (`^VecIdx`), IVF and PLAID indexes are not erased, so erased content can still be found through them until a rebuild ([search question](search.g5.md#search.erasure.indexes); [operations inventory](../../uplift/ivg-verus-initial/intent/operations.md#L254-L256)). The store list is derived from `Graph.KG.GraphStores` and checked by a source-text unit test (`tests/unit/test_eraser_inventory_coverage.py`).

Findings: [Search indexes keep answering with content that was erased, and a re-created node inherits the erased text](../../Verus_verification/bugs_issues.md#bug-srch-001); [Erasing a tenant by prefix leaves its temporal-only events, and the redaction that follows completes while they stay readable](../../Verus_verification/bugs_issues.md#bug-led-007)

### erasure.live-statements

- Sources: [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md#L17-L44), [Eraser.cls EraseLedgerFor](../../../iris_src/src/Graph/KG/Eraser.cls#L1107-L1143), [Eraser.cls EraseEdgeRow](../../../iris_src/src/Graph/KG/Eraser.cls#L638-L680)
- agent
- data-integrity
- test-coverage

A graph erase also removes closed statement entries, not only live ones ([spec 256 plan](../../../specs/256-ledger-tenant-redaction/plan.md#L12)). Observed divergence: deletes outside the Eraser, such as `delete_edge` and Cypher `DELETE`, leave the relationship's live statement behind ([single path](#erasure.entry-points.single-path)). Live test: `tests/integration/test_edgescan_ledger_erase.py::test_erasing_a_graph_removes_its_ledger_statements_and_leaves_other_graphs`. It checks the tuple lookup only.

Findings: [Deleting a relationship with delete_edge or Cypher DELETE leaves its reifications, edge embeddings and ledger statement behind](../../Verus_verification/bugs_issues.md#bug-str-013)

### erasure.history

- Sources: [ADR-0004 Decision and Consequences](../../../docs/adr/0004-erasure-removes-content-not-history.md#L14-L89), [ADR-0013](../../../docs/adr/0013-redaction-removes-content-from-history.md#L45-L47), [Eraser.cls header](../../../iris_src/src/Graph/KG/Eraser.cls#L26-L33)
- agent
- architecture-decision, security, data-integrity
- test-coverage

Rejected alternatives (ADR-0004): refusing to erase when the ledger holds revisions; marking the ledger stale; pruning records by graph. Live evidence that records survive an erase: `test_256_ledger_redaction_e2e.py::TestUS1RedactTenant::test_the_scan_sees_tenant_a_after_the_erase_alone`.

### erasure.kept

- Sources: [Eraser.cls EraseGraph](../../../iris_src/src/Graph/KG/Eraser.cls#L240-L254), [Eraser.cls quarantine](../../../iris_src/src/Graph/KG/Eraser.cls#L300-L302), [Eraser.cls EraseAll](../../../iris_src/src/Graph/KG/Eraser.cls#L699-L760)
- agent
- architecture-decision, operations
- test-coverage

The quarantine rule cites FR-039/FR-040 of an embedding spec that is not in `specs/`. Erase-all empties the temporal-only settings, the label-set interning, `^NKG` and the whole embedding registry. It keeps the quarantine and the ledger's records. Live test: `test_erase_graph.py::test_erase_all_empties_the_stores_that_cannot_be_erased_per_graph`.


Review round 3 R3-reader M7: the multigraph mode is killed by a graph erase ([Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls#L243-L244), matching [the multigraph switch](graph-structure.g5.md#structure.multigraph.switch)) and the FHIR watermarks are reset ([Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls#L180-L181)); the embedding quarantine rule is in [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls#L300-L302). No erase names the document or edge-vector quarantine tables either.
### erasure.atomic

- Sources: [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md#L21-L51), [Eraser.cls header](../../../iris_src/src/Graph/KG/Eraser.cls#L18-L24), [CHANGELOG 4.6.4](../../../CHANGELOG.md#L410-L426), [USER_GUIDE writes inside your transaction](../../../docs/USER_GUIDE.md#L285-L310)
- Children: [Caller's transaction](#erasure.atomic.caller-transaction), [Routed tables](#erasure.atomic.routes)
- agent
- architecture-decision, data-integrity
- test-coverage

Live test: `tests/integration/test_eraser_failures.py` (a refused delete in any table erases nothing). It compares SQL row counts only, not the native indexes or ledger statements. The rule that IVG never commits or rolls back a caller's transaction comes from 4.6.4. Since then the Eraser rolls back only to the level it found; before, it rolled back every level.


Observed divergence (code reading, review round 3 R3-reader M4): the store splits ID lists into chunks of 500 and calls the Eraser once per chunk, and with no caller transaction each call commits on its own ([iris_sql_store.py](../../../iris_vector_graph/stores/iris_sql_store.py#L1302-L1358), [_eraser_txn](../../../iris_vector_graph/stores/iris_sql_store.py#L1451-L1472)). `bulk_delete_nodes` batches by design and counts a failed batch as wholly failed even when its earlier chunks committed ([nodes_edges.py](../../../iris_vector_graph/_engine/nodes_edges.py#L2283-L2298)); `erase_bare_nodes` commits per 10,000 IDs ([Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls#L1297-L1304)). No failure was injected natively.

Findings: [Erasing a long list of node IDs or relationships without a caller's transaction commits once per 500 entries](../../Verus_verification/bugs_issues.md#bug-led-011)
### erasure.atomic.caller-transaction

- Sources: [nodes_edges.py erase_graph](../../../iris_vector_graph/_engine/nodes_edges.py#L1513-L1517), [engine.py _iris_obj](../../../iris_vector_graph/engine.py#L1894-L1943), [iris_sql_store.py _eraser_txn](../../../iris_vector_graph/stores/iris_sql_store.py#L1451-L1471), [CHANGELOG 4.7.0](../../../CHANGELOG.md#L68-L79), [USER_GUIDE writes inside your transaction](../../../docs/USER_GUIDE.md#L296-L310), [reconstruction check 2(b)1](../../uplift/ivg-verus-initial/reconstruction-check.md)
- Expands: [One transaction](#erasure.atomic)
- agent
- uncertain
- data-integrity, architecture-decision

Observed: the erases of nodes, prefixes and relationships run through the store on the caller's own process, so the Eraser's transaction nests in the caller's. Erasing a graph or everything calls the Eraser through the engine's native connection. For an engine made on the caller's plain connection, that is the same process, and the erase nests. For an engine made with `from_connect`, which keeps its login, it is a dedicated connection: the erase commits on its own, the caller's rollback does not undo it, and it cannot see the caller's uncommitted rows. The user guide names only the temporal stores and non-indexed adjacency as running outside a caller's transaction. Tests replace the native connection with the caller's, so only the nesting path is tested. Both transports were observed: nested on a plain connection ([probe](../../Verus_verification/receipts/native/erasure_caller_transaction_redaction.json)), committing on its own through `from_connect` ([probe](../../Verus_verification/receipts/native/erasure_caller_transaction_from_connect.json)).

Findings: [Should whether a write joins the caller's transaction depend on how the engine was opened?](../../Verus_verification/open_questions.md#q-plt-006)


The general question, which also covers search-index writes, temporal purges and settings and FHIR graph calls, is [structure.write.engine-connection](graph-structure.g5.md#structure.write.engine-connection).
### erasure.atomic.routes

- Sources: [Eraser.cls after the commit](../../../iris_src/src/Graph/KG/Eraser.cls#L262-L303), [Eraser.cls route collection](../../../iris_src/src/Graph/KG/Eraser.cls#L67-L111)
- Expands: [One transaction](#erasure.atomic)
- agent
- architecture-decision, operations
- test-coverage

DDL runs outside the transaction because a rolled-back `DROP TABLE` is not dependable in IRIS (code comment). Live test: `tests/integration/test_227_orphan_route_erase.py`.

### erasure.count

- Sources: [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md#L21-L23), [Eraser.cls EraseGraph doc](../../../iris_src/src/Graph/KG/Eraser.cls#L37-L46), [nodes_edges.py erase_graph](../../../iris_vector_graph/_engine/nodes_edges.py#L1495-L1499)
- agent
- uncertain
- user-facing-behavior
- test-coverage

ADR-0004 says "a returned 0 means nothing matched". The Eraser says the count deliberately leaves out derived stores. Labels, properties, documents or temporal entries with no node or relationship row can be erased while 0 is returned. The "nothing matched" wording is therefore true only for node and relationship rows. Erasing nodes counts only node rows, and erasing relationships counts only relationship rows. Live test: `test_erase_graph.py::test_erasing_a_graph_with_no_content_returns_zero`.


Findings: [What does erasure's returned count promise?](../../Verus_verification/open_questions.md#q-007)
### erasure.entry-points

- Sources: [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls#L307-L400), [nodes_edges.py](../../../iris_vector_graph/_engine/nodes_edges.py#L1473-L1595)
- Children: [Single path](#erasure.entry-points.single-path)
- agent
- user-facing-behavior
- test-coverage

In strict ledger mode the engine's erase methods are refused ([strict mode](ledger.g5.md#ledger.strict)). The engine's `erase_graph` (alias `drop_graph`), `erase_all`, `delete_nodes_by_prefix`, `delete_node` and `bulk_delete_nodes`, and the store's `delete_nodes`, `delete_edges` and `erase_bare_nodes`, call the Eraser. Live tests: `test_erase_graph.py`, `test_eraser_failures.py` (graph, prefix, IDs, edges, all).

### erasure.entry-points.single-path

- Sources: [ADR-0004 Consequences](../../../docs/adr/0004-erasure-removes-content-not-history.md#L71-L82), [Eraser.cls header](../../../iris_src/src/Graph/KG/Eraser.cls#L1-L16), [nodes_edges.py delete_edge](../../../iris_vector_graph/_engine/nodes_edges.py#L1382-L1456), [schema.py delete_reification](../../../iris_vector_graph/_engine/schema.py#L3361-L3395), [operations inventory](../../uplift/ivg-verus-initial/intent/operations.md#L250-L262)
- Expands: [Entry points](#erasure.entry-points)
- agent
- architecture-decision
- test-coverage

Observed divergence: several deletes bypass the Eraser and leave stores behind.

- `delete_edge` removes the row and its adjacency, but not its reifications, edge embeddings or ledger statement.
- Cypher `DELETE` of a relationship leaves the same. `DETACH DELETE` also leaves the optimized and routed node vectors and the temporal stores (inventory, not verified here).
- `delete_reification` deletes the reifier's rows in every graph.
- The temporal delete and purge, the temporal row drop, FHIR resync and the `rebuild_edge_indices` procedure delete outside the Eraser (inventory).

The deprecated `bulk_delete_adjacency` still exists, but it now deletes through the Eraser's relationship erase, so it no longer leaves drift. ADR-0004 said it would be removed. Live test: `test_erase_graph.py::test_drop_graph_is_the_eraser_now`.

Findings: [bulk_delete_adjacency deletes relationships under strict mode without a record](../../Verus_verification/bugs_issues.md#bug-plt-006); [Deleting a relationship with delete_edge or Cypher DELETE leaves its reifications, edge embeddings and ledger statement behind](../../Verus_verification/bugs_issues.md#bug-str-013); [Under strict mode the only API delete is a ledger changeset, which leaves documents, temporal, FHIR and search-index content that redaction and verify cannot see](../../Verus_verification/bugs_issues.md#bug-led-008); [ADR-0004 says bulk_delete_adjacency was removed, but it is still shipped and documented](../../Verus_verification/bugs_issues.md#bug-doc-007); [Delete a relationship through one Eraser path, whatever the caller](../../Verus_verification/design_simplification.md#simp-str-001)

### erasure.prefix-match

- Sources: [Eraser.cls EraseNodes](../../../iris_src/src/Graph/KG/Eraser.cls#L307-L350), [LedgerRedact.cls MatchString](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L45-L53), [nodes_edges.py delete_nodes_by_prefix](../../../iris_vector_graph/_engine/nodes_edges.py#L1529-L1560), [reconstruction check G14](../../uplift/ivg-verus-initial/reconstruction-check.md#L407)
- agent
- uncertain
- user-facing-behavior, security
- test-coverage

The match rule is in the Eraser's documentation ("exact and case-sensitive"). The separator advice follows from the [redaction target](redaction.g5.md#redaction.target) and the [tenant recipe](redaction.g5.md#redaction.tenant). The redaction tests erase with `tenantA|` and `acme|`. Observed divergence: the prefix erase collects its ids from node rows, so a tenant's events of a temporal-only predicate whose endpoints have no node row are not erased; after the documented erase-then-redact recipe such an event is still readable and verify reports equal ([native observation](../../Verus_verification/receipts/native/erasure_prefix_temporal_only.json); model witness W5 in the [ledger_redaction model](../../Verus_verification/models/ledger_redaction/redaction.rs)). The same node-row selection leaves a property row with no node row, which then refuses every later prefix redaction ([native observation](../../Verus_verification/receipts/native/redaction_orphan_prop_blocks.json); model witness W6).

Findings: [Erasing a tenant by prefix leaves its temporal-only events, and the redaction that follows completes while they stay readable](../../Verus_verification/bugs_issues.md#bug-led-007); [A property row with no node row survives the prefix erase, and every later prefix redaction of its tenant is refused](../../Verus_verification/bugs_issues.md#bug-led-010); [Should erase-by-prefix and redact-by-prefix use the same prefix rule?](../../Verus_verification/open_questions.md#q-008)

### erasure.concurrency

- Sources: [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls), [Ledger.cls caller transaction note](../../../iris_src/src/Graph/KG/Ledger.cls#L385-L396), [LedgerRedact.cls LiveRows](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L143-L178), [A-history notes F4](../../uplift/ivg-verus-initial/intent/ledger-history.md)
- agent
- uncertain
- data-integrity

Two cases. First, observed natively ([erasure_caller_transaction](../../Verus_verification/receipts/native/erasure_caller_transaction_redaction.json), [A redaction completes while its target's content is still uncommitted-deleted, and the caller's rollback brings the content back with its history tombstoned](../../Verus_verification/bugs_issues.md#bug-002)): a caller erases a target inside its own transaction, a redaction on another connection reads the uncommitted erase and finishes, and the caller rolls back, so the content is live again with its history redacted. Second, suspected and not tested: a ledger commit adds a statement between the erase's row delete and its statement cleanup.

Findings: [A ledger commit into a graph during its erase can lose the new relationship's statement entry](../../Verus_verification/bugs_issues.md#bug-led-002)

Findings: [Must erasure and redaction be serialised with each other and with ledger commits?](../../Verus_verification/open_questions.md#q-004)
