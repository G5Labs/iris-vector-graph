# Graph structure

Nodes and structural edges inside one graph, the multigraph option, the adjacency index derived from the edge rows, degree, the stores that are rebuilt rather than kept current, and how drift is repaired and checked. Which graph content belongs to is described in [graph scope](../concepts/graph-scope.g5.md).

## Definitions

- **Node**: an ID inside one graph, with that graph's labels and properties.
- **Structural edge** (edge): a typed, directed relationship from a source node to a target node.
- **Triple**: an edge's source, type and target.
- **Qualifiers**: an edge's key-value properties, including its weight.
- **Edge key**: a small whole number that tells apart the edges of one triple; 0 for the first or only edge.
- **Reifier node** and **reification**: a reifier node is an ordinary node that holds properties about one edge; the reification is the link from the reifier to that edge's row.
- **Documents**: the text kept for a node in the documents table, one per node per graph, which text search reads.
- **Multigraph mode**: a per-graph setting that lets one triple hold several edges.
- **Adjacency index**: the native index of each graph's out-edges, in-edges and node labels, used for neighbor lookup, walks and the graph algorithms.
- **Declared index**: an adjacency index that the database maintains from the edge and label tables on every row change.
- **Degree**: the number of outgoing edges of a node, or of one edge type on it.
- **Generation**: a per-node counter that moves whenever the node's outgoing adjacency changes.
- **Rebuilt store**: a derived store that is rebuilt from the tables rather than kept current on every write.
- **Graph-version token**: one namespace-wide counter of writes that can change an algorithm's answer.
- **Interned snapshot**: a rebuilt copy of every graph's edges with each node ID numbered once; it has no graph dimension.
- **Two-hop statistics**: precomputed per-node counts of the nodes two hops away, by edge type, used to answer two-hop counts quickly.
- **Accelerator's snapshot**: a whole-database copy of the adjacency index that the optional native accelerator library reads.
- **Drift**: a disagreement between the rows and a derived store about the same content.
- **Bypass**: a write path that changes one of those stores without the other.
- **Rebuild**: `engine.sync()`, which recreates the derived stores from the rows.

## Writes

<a id="structure.write"></a>
[D · structure.write]

Each engine write is its own transaction when the caller has none, and a nested part of the caller's open transaction otherwise. If the write fails, only its own part is taken back; the caller's commit or rollback decides the rest. These kinds of call are the exceptions:

- Calls that cannot be part of one transaction refuse a caller's open transaction and commit in steps: snapshot restore and the bulk loader.
- Some calls use the engine's own native connection: erasing a graph or every graph, a rebuild, switching multigraph mode, named search-index writes (BM25 and vector indexes), temporal purges, rebuilds and settings, and FHIR graph calls. They join the caller's transaction only when the engine was made on the caller's own connection; with `from_connect` they commit on their own ([erasure](erasure.g5.md#erasure.atomic)). Whether this should depend on how the engine was opened is [open](#structure.write.engine-connection).
- Deleting nodes removes the reifier nodes of their edges in later transactions.
- Temporal writes follow their own rule ([temporal writes](temporal.g5.md#temporal.write)).

<a id="structure.write.engine-connection"></a>
[Q · structure.write.engine-connection]

Should whether a write joins the caller's transaction depend on how the engine was opened? There is no provisional answer.

- Today the calls that use the engine's own native connection nest in the caller's transaction for an engine made on the caller's connection, and commit on their own for an engine made with `from_connect`.
- Plausible answers: make every such call join the caller's transaction, refuse an open caller transaction, or document the difference per call.

## Nodes

<a id="structure.node"></a>
[I · structure.node]

Creating a node that already exists in its graph changes nothing and reports False. A write that IRIS refuses raises an error and leaves nothing behind.

- When two callers create the same node at once, one creates it and the other reports False.
- A new node gets an `id` property equal to its ID unless the caller gives one. The ledger reserves that property name ([changesets](ledger.g5.md#ledger.changeset)).

<a id="structure.node.delete"></a>
[I · structure.node.delete]

Deleting a node removes, in its graph, its labels, properties, documents, vectors and incident edges, and then the reifier nodes of those edges.

- The node and its own rows go in one transaction.
- Without a named graph, the delete uses the one graph that holds the ID ([graph scope](../concepts/graph-scope.g5.md#graph.default)).

<a id="structure.node.update"></a>
[I · structure.node.update]

Writing a node with `store_node` creates its row if it is missing and always reports True.

- Each property it is given replaces that property's value; a None value removes the property, and other properties stay.
- Each label it is given is added; existing labels stay.
- The node gets an `id` property equal to its ID only when it has none yet.
- The row, properties and labels are one transaction, and a duplicate node or label is not an error.

<a id="structure.node.read"></a>
[D · structure.node.read]

`get_node` and `get_nodes` read the named graph, or the default graph when none is named, using that graph's labels and typed properties. Batched results follow the requested ID order and preserve repeated IDs; an existing node with no labels or properties is returned, while an absent ID with no child rows is omitted (`get_node` returns None).

- Properties named `id` and `labels` are returned as `p_id` and `p_labels`, keeping the structural ID and label list intact. If the caller also stored `p_id` or `p_labels`, today's flat result loses one value according to property row order; see [the unresolved alias rule](#structure.node.read.aliases).
- A node with child rows is included without a separate node-row check; orphan child rows can therefore appear as a node. Reads fail if a database read fails, rather than returning a fabricated empty node.

<a id="structure.node.read.aliases"></a>
[Q · structure.node.read.aliases]

How should the flat node read preserve both `id` and `p_id` properties (and both `labels` and `p_labels`)? Working answer: preserve every stored property in a separate property map; the alternative is a documented reserved alias namespace with validation before writing. Today either colliding property can win, while the structural fields remain intact; the product owner must choose the compatible API change.

## Edges

<a id="structure.edge"></a>
[I · structure.edge]

An edge connects two nodes of the same graph and may carry qualifiers. Creating an edge adds any missing endpoint to that graph in the same transaction, so a failed edge leaves no node behind.

<a id="structure.edge.single"></a>
[I · structure.edge.single]

Outside multigraph mode a graph holds at most one edge per triple. Writing an existing edge again adds nothing and reports False; a duplicate is never an error.

<a id="structure.edge.weight"></a>
[D · structure.edge.weight]

An edge's weight lives in its qualifiers, so the adjacency index, a rebuild and Cypher's `r.weight` all read the same value. An edge with no weight costs 1.0 in weighted walks.

<a id="structure.edge.weight.set"></a>
[I · structure.edge.weight.set]

`set_edge_weight` changes the weight of an existing edge in the default graph only. It updates every edge of the triple in one transaction, and reports False, writing nothing, when the default graph has no such edge.

<a id="structure.edge.delete"></a>
[I · structure.edge.delete]

Deleting an edge removes the triple's edges from one graph, or from every graph when the caller asks for that. It reports success even when nothing matched, and a delete that IRIS refuses raises an error and removes nothing.

<a id="structure.edge.delete.reifications"></a>
[Q · structure.edge.delete.reifications]

Should deleting an edge also remove its reifications and edge embeddings, as deleting a node, deleting a relationship through the ledger, and erasing edges do? No source decides it, and there is no provisional answer.

## Reifications

<a id="structure.reification"></a>
[D · structure.reification]

A reifier node holds properties about one edge row, and each reifier belongs to exactly one edge.

- Reifying an edge creates the reifier node in the default graph, whatever the edge's graph, labels it, links it to the edge and adds each given property the node lacks, all in one transaction.
- Reifying an edge that does not exist writes nothing and returns no reifier.
- Reading an edge's reifications returns each reifier with its properties.
- Deleting a reifier removes its link, properties, labels and node rows in every graph, and leaves the edge in place.

## Multigraph mode

<a id="structure.multigraph"></a>
[D · structure.multigraph]

Multigraph mode is a per-graph setting, off by default and available for the default graph too. In it, two nodes may hold several edges of one type, as openCypher's `CREATE` expects, and each edge keeps its own identity.

<a id="structure.multigraph.off"></a>
[I · structure.multigraph.off]

With the mode off, a graph behaves exactly as before multigraph mode existed, with the same storage, generated SQL and adjacency layout. Every writer uses edge key 0, so such a graph holds at most one edge row per triple.

<a id="structure.multigraph.switch"></a>
[I · structure.multigraph.switch]

Turning multigraph mode on is always allowed. Turning it off is refused while any triple of the graph holds more than one edge, and erasing a graph clears its mode.

<a id="structure.multigraph.layout"></a>
[D · structure.multigraph.layout]

A triple with one edge looks the same in the adjacency index in either mode.

- While a triple has two or more edges, each edge also has its own entry, and the triple records how many edges it holds.
- The triple's own entry carries the weight of its edge with the lowest edge key.
- Edge keys are never renumbered, and a live edge's key is never reused.
- A new edge takes one more than the triple's highest live key, or 0 for the first, so the key of a deleted highest edge can return.
- When two writers pick the same new key, the loser retries once with a fresh key and fails loudly after a second clash.
- A rebuild produces the same layout as the writes that led to it.

<a id="structure.multigraph.count"></a>
[D · structure.multigraph.count]

Degree counts every edge of a multigraph triple, while the interned snapshot keeps one entry per triple. Edge embeddings stay per triple, so parallel edges share one.
- A one-hop read answers one row per relationship. Two edges of one type between the same two nodes are two rows, and `count()` counts both.
- The one-hop ID shortcut keeps this rule: it repeats a target once for each edge the triple holds.
- Cypher tells relationships apart by edge ID, so two equal parallel edges stay two; asking for distinct answers folds them.

<a id="structure.multigraph.create_edge"></a>
[Q · structure.multigraph.create_edge]

In a multigraph, should `create_edge` always add a new edge, and should a variant return the new edge's ID? The provisional answer, from the multigraph specification, is yes to both.

<a id="structure.multigraph.ledger"></a>
[Q · structure.multigraph.ledger]

How does the revision ledger name one of several parallel edges? The provisional answer, from the multigraph specification, is that a reference may carry the edge key, and a reference that fits several edges is refused as ambiguous. Today the ledger acts on the first matching row and deletes the surviving edges' adjacency (observed).

<a id="structure.multigraph.restore"></a>
[I · structure.multigraph.restore]

A restore brings back each graph's multigraph mode with its edges, so a restored multigraph keeps its parallel edges, their layout and their counts.

## Adjacency index

<a id="structure.adjacency"></a>
[D · structure.adjacency]

The adjacency index is derived from the edge and label rows, which stay authoritative. Every entry is keyed by its graph ([graph keys](../concepts/graph-scope.g5.md#graph.key)).

<a id="structure.adjacency.declared"></a>
[I · structure.adjacency.declared]

Where the index is declared, every row insert, update or delete, by any path, changes it in the same transaction. A rollback undoes both, and the index holds no entry without a row behind it.

<a id="structure.adjacency.undeclared"></a>
[I · structure.adjacency.undeclared]

Where the index is not declared, such as after a setup that did not finish, only the engine's own edge writers and a rebuild keep it current. Cypher writes, `store_edge` and the store's `write_edges` leave it stale until a rebuild.

<a id="structure.adjacency.one_writer"></a>
[D · structure.adjacency.one_writer]

One module makes every change to the out-edge and in-edge entries, so the rules every such change must follow are written once. A source scan fails on any other writer unless an explicit, justified exception is added.

<a id="structure.adjacency.bulk"></a>
[D · structure.adjacency.bulk]

A bulk path that writes rows without index upkeep must leave no duplicate rows and must rebuild the indexes before it returns, whether it succeeds or fails. Three paths do this:

- `bulk_create_nodes` and `bulk_create_edges`, which drop the indexes for a large batch and rebuild them afterwards;
- `bulk_load_session`;
- the bulk loader, whose own contract is on the [install page](../concepts/install.g5.md#install.bulk_load).

## Degree

<a id="structure.adjacency.declare"></a>
[D · structure.adjacency.declare]

Setup declares the two adjacency indexes only once their prerequisites exist, declares each one once, and leaves an index that is already declared alone.
- Nothing is declared while the callback classes are not compiled, while the schema's own procedure class is not compiled, before the edge table has its edge key column, or before both tables have the graph column. Setup skips with a reason, and a later setup declares them.
- Once every prerequisite exists, both are declared: the edge index first, then the label index.
- An index already declared as the adjacency index is left alone. A plain index with the same name is dropped and replaced.
- Before the edge index is built, every triple that has temporal events but no row gets its marked row. The build then fills the index from every row, which also repairs drift.

<a id="structure.degree"></a>
[D · structure.degree]

A node's degree is counted from the adjacency index when asked and is never kept as a stored counter. A stored counter cannot stay exact when transactions roll back, and no reader needs one.

<a id="structure.degree.cache"></a>
[D · structure.degree.cache]

A counted degree may be cached and served while the node's generation has not moved since the count. Every change to a node's outgoing adjacency moves its generation, and deleting the cache changes no answer.

<a id="structure.degree.cache.uncommitted"></a>
[I · structure.degree.cache.uncommitted]

A cached degree never includes an edge that was later rolled back.

- Each graph has one writer lock. Writers hold it shared, so writers never wait for each other, and keep it until their transaction ends.
- A reader stores its count only when it could take that lock alone at once, and the node's generation did not move while it counted.
- A writer that cannot get the lock within 5 seconds still writes, and turns degree caching off for its graph until the next rebuild.

<a id="structure.degree.cache.erase"></a>
[I · structure.degree.cache.erase]

Erasing a node or a graph clears its generations and cached degrees. No count cached before the erase may be served after it, even when later writes bring the generation back to an earlier value.

<a id="structure.degree.cache.warm"></a>
[D · structure.degree.cache.warm]

A rebuild leaves the degree cache filled, so the first reads after it do not recount.

- Standalone `WarmAll(graph)` also fills graphs that exist only in adjacency globals: it enumerates that graph's outgoing sources directly, without SQL node or edge rows. It fills an all-predicate entry and each predicate entry and returns the number of sources filled, not the number of entries; target-only nodes are not sources.
- A failed exclusive writer-lock probe, a no-lock-writer flag, or a generation change prevents that source from being counted as filled. A generation change detected after storing removes the source's new entries.
- The whole-graph stamp is replaced only when every visited source filled and the graph-version token stayed equal. Otherwise it is removed and readers use their per-source checks. Empty outgoing globals return zero and may have a current whole-graph stamp; a subsequent token change makes that stamp stale.
- At the pin a rebuild bumps the token after warming, making the whole-graph stamp stale at once even though the per-source entries remain valid; this departure remains [simp-str-003](../../Verus_verification/design_simplification.md#simp-str-003). Clearing entries alone while keeping a current stamp can return zeros ([F-0406](../../Verus_verification/bugs_issues.md#F-0406)).

## Rebuilt stores and the graph-version token

<a id="structure.rebuilt"></a>
[D · structure.rebuilt]

The interned snapshot, the two-hop statistics, the accelerator's snapshot and cached algorithm results are rebuilt stores. Each records the graph-version token it was built from and is current only while that token is still the live one, so a failed rebuild leaves it stale for every process.

<a id="structure.rebuilt.token"></a>
[I · structure.rebuilt.token]

Every change to the adjacency index, to its edges or to its labels, increases the graph-version token; a write to node rows or properties alone does not. The token never decreases and a value is never reused, even when the write rolls back. A cached answer that also depends on other content must key on that content too or not be cached ([algorithm cache](algorithms.g5.md#algorithms.cache.token)).

<a id="structure.rebuilt.stamp"></a>
[I · structure.rebuilt.stamp]

A rebuilt store is current only when it carries a build stamp and that stamp equals the live token. A store that was never stamped is stale even while the token is still zero, and a store stamped at zero is current until the token moves.
- An unset token reads as zero, but an unset or empty stamp means "not known", never zero.
- Asking which of several stores are stale applies the same rule to each store, in the order asked.
- The two-hop count reader in ObjectScript and the Python freshness module apply this one rule.

<a id="structure.rebuilt.valid"></a>
[I · structure.rebuilt.valid]

A cached algorithm result is valid only while the token it was computed under is still the live token. The token is read before the computation starts, so a write during the computation leaves the result stale, never wrongly current.

<a id="structure.rebuilt.rollback"></a>
[Q · structure.rebuilt.rollback]

When a computation sees a write that is not yet committed and that write later rolls back, must the cached result be thrown away? The provisional answer is yes, because the degree cache and the rebuild already treat that case as unsafe. Today the cached result stays current until the next write (observed).

<a id="structure.rebuilt.stale_read"></a>
[I · structure.rebuilt.stale_read]

A reader never answers from an interned snapshot known to be stale.

- After an erasure, the first algorithm that reads the snapshot rebuilds it once, under a lock, before it answers.
- A variable-length Cypher query that would read a stale snapshot raises an error asking for a rebuild.

## Drift, rebuild and verification

<a id="structure.drift"></a>
[I · structure.drift]

A declared adjacency index cannot drift from its rows, and declaring it on an install that has drifted repairs the drift.

<a id="structure.rebuild"></a>
[I · structure.rebuild]

A rebuild recreates the adjacency index from the rows and then the interned snapshot from the index, and running it again is safe. With a declared index the adjacency never needs it; the interned snapshot still does after bulk loads and erasures.

<a id="structure.rebuild.failure"></a>
[Q · structure.rebuild.failure]

What may readers see when a rebuild fails partway? The provisional answer, from the degree-cache design, is that an early failure leaves the previous adjacency, and a later one leaves a partial index whose degree cache is cleared, never wrong.

<a id="structure.verify"></a>
[I · structure.verify]

`verify_graph` reports one graph's adjacency entries with no row behind them, its rows with no adjacency entry, and its current degree-cache entries that disagree with a recount. Its `ok` answers only whether this graph's adjacency agrees with its rows.

## Metadata

### structure.write
- Sources: [WriteTxn](../../../iris_vector_graph/_write_txn.py#L1-L28), [Graph.KG.Txn](../../../iris_src/src/Graph/KG/Txn.cls), [the engine's own native connection](../../../iris_vector_graph/engine.py#L1894-L1943), [erase_graph uses it](../../../iris_vector_graph/_engine/nodes_edges.py#L1513-L1517), [set_multigraph uses it](../../../iris_vector_graph/_engine/admin.py#L893-L915), [restore refuses a caller transaction](../../../iris_vector_graph/_engine/snapshot.py#L1095-L1102), [bulk loader refuses one](../../../iris_vector_graph/bulk_loader.py#L156-L163), [reifiers deleted afterwards](../../../iris_vector_graph/_engine/nodes_edges.py#L2176-L2200)
- Children: [Engine connection](#structure.write.engine-connection)
- agent
- architecture-decision, data-integrity

Introduced in 4.6.4: before it, an engine write inside a caller's transaction committed or rolled back the caller's earlier work. The exceptions were added after the stage-A reconstruction check (its 2(b) item 14) and checked in the code. The separate native connection exists so that Native API calls never share a connection with cursor DDL; without the caller's credentials the engine uses the caller's own connection, and these calls then nest. Inside a caller's transaction, `bulk_create_nodes` and `bulk_create_edges` keep the indexes and nest instead of dropping them. Whether erasure should refuse an open caller transaction is the erasure page's open question.

Findings: [A failed BM25 insert or delete rolls back the caller's whole transaction](../../Verus_verification/bugs_issues.md#bug-srch-002); [The Txn_End and Txn_Undo SQL procedures end every transaction level, the caller's included](../../Verus_verification/bugs_issues.md#bug-plt-021)


### structure.write.engine-connection

- Sources: [engine.py _iris_obj](../../../iris_vector_graph/engine.py#L1894-L1943), [vector.py index writes](../../../iris_vector_graph/_engine/vector.py#L1566-L1650), [temporal.py purges and settings](../../../iris_vector_graph/_engine/temporal.py#L619-L824), [erasure.atomic.caller-transaction](erasure.g5.md#erasure.atomic.caller-transaction)
- Expands: [Engine writes](#structure.write)
- agent
- uncertain
- data-integrity, architecture-decision

Observed for the graph erase ([erasure_caller_transaction_from_connect](../../Verus_verification/receipts/native/erasure_caller_transaction_from_connect.json): `native_is_dedicated: true`, the erase survived the caller's rollback). The other calls are from code reading. Added by review round 3 R3-reader M5; the ledger's `disable` and `set_strict` also go through the native connection.

Findings: [Should whether a write joins the caller's transaction depend on how the engine was opened?](../../Verus_verification/open_questions.md#q-plt-006)
### structure.node
- Sources: [create_node](../../../iris_vector_graph/_engine/nodes_edges.py#L968-L1104), [a concurrent duplicate reports False](../../../iris_vector_graph/_engine/nodes_edges.py#L1095-L1104), [ledger reserved names](../../../iris_src/src/Graph/KG/LedgerApply.cls#L68-L71), [API reference](../../../docs/API_REFERENCE.md)
- Children: [deleting a node](#structure.node.delete), [writing a node](#structure.node.update), [reading nodes](#structure.node.read)
- agent
- user-facing-behavior

The `id` property dates from 4.6.0 (R181), so that `MATCH (n {id: ...})` finds the node. The concurrent-create bullet answers reconstruction gap G36 for nodes: uniqueness rests on the node table's key, with no lock.

### structure.node.delete
- Sources: [API reference, delete_node](../../../docs/API_REFERENCE.md#L516-L522), [delete_node](../../../iris_vector_graph/_engine/nodes_edges.py#L2227-L2268), [Eraser.EraseIdSet](../../../iris_src/src/Graph/KG/Eraser.cls#L467-L632)
- Expands: [nodes](#structure.node)
- agent
- user-facing-behavior, data-integrity

Observed: the reifier nodes are deleted in later transactions, and a failure there raises an error that says the node is gone and its reifiers are not. Erasure semantics are owned by the erasure pages.

### structure.node.update
- Sources: [store_node](../../../iris_vector_graph/_engine/nodes_edges.py#L2393-L2530), [API reference, store_node](../../../docs/API_REFERENCE.md#L738-L750)
- Expands: [nodes](#structure.node)
- agent
- user-facing-behavior

Added after the stage-A reconstruction check (gap G15). The docstring and API reference state this contract. Before 4.5.0 a failed property was skipped after the node row had committed. Cypher `SET` and ledger property and label operations are the other ways to change a node, owned by the Cypher and ledger pages.

### structure.node.read
- Sources: [`NodesEdgesMixin.get_nodes`](../../../iris_vector_graph/_engine/nodes_edges.py#L621-L702), [`::get_node`](../../../iris_vector_graph/_engine/nodes_edges.py#L563-L585), [`::create_node`](../../../iris_vector_graph/_engine/nodes_edges.py#L968-L1107), [typed node values](../../../iris_vector_graph/prop_values.py#L211-L232)
- Verus: [node_read](../../Verus_verification/models/node_read/NOTES.md) `theorem_bare_node_vs_absent`, `theorem_requested_duplicates_remain`, `theorem_structural_keys_kept`, `witness_alias_collision` (as-built); real Python writer/reader comparison with substituted storage and `CY_TYPED`. Graph isolation remains the existing graph owner's obligation, not a new live cross-graph claim.
- agent
- user-facing-behavior, data-integrity
- test-coverage
- Expands: [nodes](#structure.node)
- Children: [aliases](#structure.node.read.aliases)

Findings: [Colliding flat property aliases](../../Verus_verification/bugs_issues.md#bug-str-101).

### structure.node.read.aliases
- agent
- uncertain
- user-facing-behavior, architecture-decision
- Expands: [reading nodes](#structure.node.read)

Evidence and choices: [q-iter-001](../../Verus_verification/open_questions.md#q-iter-001). No human has ratified a replacement representation.

Findings: [Colliding flat property aliases](../../Verus_verification/bugs_issues.md#bug-str-101).

### structure.edge
- Sources: [CONTEXT.md, Structural Edge](../../../CONTEXT.md#L60-L63), [create_edge](../../../iris_vector_graph/_engine/nodes_edges.py#L1151-L1255), [rdf_edges DDL](../../../iris_vector_graph/schema.py#L34-L45)
- Children: [one edge per triple](#structure.edge.single), [weight](#structure.edge.weight), [deleting edges](#structure.edge.delete)
- agent
- user-facing-behavior, data-integrity

Before 4.5.0 a refused edge left its endpoint rows committed and answered False.

### structure.edge.single
- Sources: [USER_GUIDE, parallel edges](../../../docs/USER_GUIDE.md#L469-L473), [Known issue: CREATE of an existing relationship](../../../docs/KNOWN_ISSUES.md#a-cypher-create-of-a-relationship-that-already-exists-adds-nothing), [spec 234 context](../../../specs/234-multigraph-parallel-edges/spec.md#L11-L35)
- Expands: [edges](#structure.edge)
- agent
- user-facing-behavior

An explicit create of a triple whose only row came from a temporal write adopts that row instead; the temporal pages own that rule.

### structure.edge.weight
- Sources: [ADR-0008, scope of step 2](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L28-L46), [spec 252 FR-006 and FR-015](../../../specs/252-adjacency-functional-index/spec.md#L117-L131), [Adjacency.WeightOf](../../../iris_src/src/Graph/KG/Adjacency.cls#L750-L765)
- Expands: [edges](#structure.edge)
- Children: [setting a weight](#structure.edge.weight.set)
- agent
- user-facing-behavior, data-integrity

Before 4.3.0 the weight could live in the adjacency alone, so a rebuild lost it.

Findings: [A ledger qualifier update reweights a multigraph triple's leaf to an edge that is not the lowest](../../Verus_verification/bugs_issues.md#bug-str-012)

### structure.edge.weight.set
- Sources: [set_edge_weight](../../../iris_vector_graph/_engine/nodes_edges.py#L1306-L1380), [API reference, set_edge_weight](../../../docs/API_REFERENCE.md#L716-L722)
- Expands: [weight](#structure.edge.weight)
- agent
- user-facing-behavior
- test-coverage

Live coverage: [set_edge_weight is one transaction](../../../tests/e2e/test_set_edge_weight_txn_e2e.py). Added after the stage-A reconstruction check (gap G15). Before 4.6.0 a refused update answered False like a missing edge, and a multigraph triple's rows were updated one by one.

### structure.edge.delete
- Sources: [delete_edge](../../../iris_vector_graph/_engine/nodes_edges.py#L1382-L1456), [API reference, delete_edge](../../../docs/API_REFERENCE.md#L502-L514)
- Expands: [edges](#structure.edge)
- Children: [reifications](#structure.edge.delete.reifications)
- agent
- user-facing-behavior

In a multigraph this removes every parallel edge of the triple; Cypher `DELETE` removes one.

### structure.edge.delete.reifications
- Sources: [rdf_reifications has no foreign key to rdf_edges](../../../iris_vector_graph/schema.py#L514-L520), [ledger relationship delete cascades](../../../iris_src/src/Graph/KG/LedgerApply.cls#L652-L670), [Eraser.EraseEdges](../../../iris_src/src/Graph/KG/Eraser.cls#L390-L462), [changelog 4.7.0, DETACH DELETE](../../../CHANGELOG.md#L179)
- Expands: [deleting edges](#structure.edge.delete)
- agent
- uncertain
- data-integrity

Observed: `delete_edge` deletes edge rows only, leaving reification links, reifier nodes and edge embeddings behind. The reconstruction check reports, from the operation inventory and not re-read here, that Cypher `DELETE r` leaves the same rows and the ledger's statement entries. Plausible answers: (a) it is a low-level primitive by design; (b) it is an omission and should cascade like the other delete paths.

Findings: [Deleting a relationship with delete_edge or Cypher DELETE leaves its reifications, edge embeddings and ledger statement behind](../../Verus_verification/bugs_issues.md#bug-str-013)

### structure.reification
- Sources: [reify_edge, get_reifications, delete_reification](../../../iris_vector_graph/_engine/schema.py#L3264-L3392), [API reference](../../../docs/API_REFERENCE.md#L140-L146), [one reifier names one edge](../../../iris_vector_graph/schema.py#L514-L520), [node deletion removes reifiers](../../../iris_vector_graph/_engine/nodes_edges.py#L2176-L2200)
- agent
- user-facing-behavior, data-integrity

Added after the stage-A reconstruction check (its section 3 item 15). The reifier is always created in the default graph, as the docstring states, even for an edge in a named graph. Deleting a reifier is documented as not graph-scoped, an exception recorded under [default graph](../concepts/graph-scope.g5.md#graph.default); it does not go through the Eraser. Each call nests in a caller's open transaction since 4.7.0.

Findings: [delete_reification deletes the reifier's rows in every graph](../../Verus_verification/bugs_issues.md#bug-str-014)

### structure.multigraph
- Sources: [spec 234 clarifications, 2026-09-26](../../../specs/234-multigraph-parallel-edges/spec.md#L37-L53), [CONTEXT.md, Multigraph mode](../../../CONTEXT.md#L83-L86), [GraphMode](../../../iris_src/src/Graph/KG/GraphMode.cls), [changelog 4.1.0](../../../CHANGELOG.md#L3835-L3853)
- Children: [mode off](#structure.multigraph.off), [switching](#structure.multigraph.switch), [layout](#structure.multigraph.layout), [counting](#structure.multigraph.count), [create_edge](#structure.multigraph.create_edge), [ledger](#structure.multigraph.ledger), [restore](#structure.multigraph.restore)
- agent
- user-facing-behavior, architecture-decision

The spec's clarification session records questions and answers without naming who answered, so this stays `agent`. The spec status says mode, storage and Cypher shipped in 4.1.0, and that the ledger and restore work was not done.

### structure.multigraph.off
- Sources: [spec 234 FR-003, FR-016 and story 4](../../../specs/234-multigraph-parallel-edges/spec.md#L145-L175), [create_edge guards on edge key 0](../../../iris_vector_graph/_engine/nodes_edges.py#L1257-L1273), [rebuild writes leaves only outside the mode](../../../iris_src/src/Graph/KG/Adjacency.cls#L832-L855)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- data-integrity
- test-coverage

Live coverage: [upgrade leaves the adjacency byte-identical](../../../tests/e2e/test_234_multigraph_storage_e2e.py). Observed divergence: the unique key admits a nonzero edge key in a mode-off graph, and the per-engine cache of the mode or an unlocked mode switch can produce one (the per-engine cache itself is documented in API_REFERENCE; the finding is the second row it lets in, which breaks this block's one-row rule), after which deleting either row removes the shared adjacency entry ([stage-A notes, F6](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [A single-edge graph can get two rows for one triple from a stale multigraph flag or an unlocked mode switch](../../Verus_verification/bugs_issues.md#bug-str-008)

### structure.multigraph.switch
- Sources: [spec 234 FR-002](../../../specs/234-multigraph-parallel-edges/spec.md#L215-L218), [GraphMode.Set](../../../iris_src/src/Graph/KG/GraphMode.cls#L22-L45), [set_multigraph](../../../iris_vector_graph/_engine/admin.py#L893-L926), [Eraser clears the mode](../../../iris_src/src/Graph/KG/Eraser.cls#L244)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live coverage: [mode set, refusal and erase](../../../tests/e2e/test_234_multigraph_storage_e2e.py). Observed divergence: nothing stops a parallel edge from being written between the count and the switch.

Findings: [A single-edge graph can get two rows for one triple from a stale multigraph flag or an unlocked mode switch](../../Verus_verification/bugs_issues.md#bug-str-008)

### structure.multigraph.layout
- Sources: [spec 234 clarifications and FR-004 to FR-006](../../../specs/234-multigraph-parallel-edges/spec.md#L44-L47), [Adjacency.PutKeyed / RemoveKeyed](../../../iris_src/src/Graph/KG/Adjacency.cls#L197-L321), [spec 252 FR-003](../../../specs/252-adjacency-functional-index/spec.md#L109-L110)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- architecture-decision, data-integrity
- test-coverage

Key allocation and the retry come from [spec 234 FR-007 and edge cases](../../../specs/234-multigraph-parallel-edges/spec.md#L185-L190) and the [key entity](../../../specs/234-multigraph-parallel-edges/spec.md#L329-L331); Cypher allocates the key in [its keyed inserts](../../../iris_vector_graph/cypher/translator.py#L10368-L10386). Observed divergence: no retry after a key clash was found, so the losing writer's statement fails with a uniqueness error. Live coverage: [one to three edges and back, and rebuild equals 200 random keyed writes](../../../tests/e2e/test_234_multigraph_storage_e2e.py). Observed divergence, suspected: concurrent writers or parallel rebuild jobs on one triple can lose an edge from the count or leave an entry with no row, and a ledger reweight can set the triple's weight from an edge that is not the lowest ([stage-A notes, F4 and F11](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [Deleting one of several parallel edges through the ledger removes the adjacency of the edges that remain](../../Verus_verification/bugs_issues.md#bug-str-001); [Concurrent writers of one multigraph triple can lose its multiplicity or leave a ghost edge entry](../../Verus_verification/bugs_issues.md#bug-str-006); [A ledger qualifier update reweights a multigraph triple's leaf to an edge that is not the lowest](../../Verus_verification/bugs_issues.md#bug-str-012)

### structure.multigraph.count
- Sources: [spec 234 clarifications](../../../specs/234-multigraph-parallel-edges/spec.md#L47-L51), [ADR-0010](../../../docs/adr/0010-degree-is-counted-never-stored.md), [Adj.Count](../../../iris_src/src/Graph/KG/Adj.cls#L108-L133); one-hop rows: [`iris_src/src/Graph/KG/TraversalKHop.cls::KHopNeighborIds`](../../../iris_src/src/Graph/KG/TraversalKHop.cls#L28-L66) (repeats a target `#` times, `:42-44`), [`iris_vector_graph/_engine/query.py::_try_khop_fast_path`](../../../iris_vector_graph/_engine/query.py#L4294-L4330) (answers only when the default graph alone holds edges); live test [test_460_one_hop_parallel_edges_e2e.py](../../../tests/e2e/test_460_one_hop_parallel_edges_e2e.py)
- Playbook: [GID-B5.4](../../../experiment/playbook-completion/ontology/02-graph-identity.md#L131), [GID-B5.5](../../../experiment/playbook-completion/ontology/02-graph-identity.md#L132), [NAT-B1.6](../../../experiment/playbook-completion/ontology/09-native-executor.md#L75)
- Verus: no formal contract for the one-hop projection in either arm. `graph_structure` (as-built) models the keyed layout and counts; the playbook's `proofs-d1d` `nread_l2` models native reads of a reviewed design. Neither derives the one-hop row list.
- Expands: [multigraph mode](#structure.multigraph)
- agent
- user-facing-behavior
- test-coverage

Live coverage: [parallel edges count their multiplicity](../../../tests/e2e/test_degree_cache_live.py). Superseded in part: the spec's choice of set semantics for PageRank and personalized PageRank was reversed in 4.6.0, when parallel edges began to weigh their count ([changelog](../../../CHANGELOG.md#L1174-L1179)); the algorithm pages own that rule.

Findings: [Deleting one of several parallel edges through the ledger removes the adjacency of the edges that remain](../../Verus_verification/bugs_issues.md#bug-str-001)

### structure.multigraph.create_edge
- Sources: [spec 234 FR-007 and clarifications](../../../specs/234-multigraph-parallel-edges/spec.md#L246-L250), [create_edge](../../../iris_vector_graph/_engine/nodes_edges.py#L1211-L1219), [Known issue: workaround through Cypher](../../../docs/KNOWN_ISSUES.md#a-cypher-create-of-a-relationship-that-already-exists-adds-nothing)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- uncertain
- user-facing-behavior

Observed: `create_edge` still adds nothing for an existing triple in a multigraph, no `create_edge_returning_id` exists, and the changelog and API reference are silent. The decision needed is whether to drop the requirement or treat this as a defect.

Findings: [In a multigraph, must create_edge always add a new edge and offer a variant that returns its ID?](../../Verus_verification/open_questions.md#q-str-003)

### structure.multigraph.ledger
- Sources: [spec 234 FR-013 and status](../../../specs/234-multigraph-parallel-edges/spec.md#L281-L291), [LedgerApply.FindEdge](../../../iris_src/src/Graph/KG/LedgerApply.cls#L143-L157), [LedgerApply.DeleteRelInternal](../../../iris_src/src/Graph/KG/LedgerApply.cls#L672-L693)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- uncertain
- data-integrity

The spec records this work as not done, and no ledger code knows the edge key or the mode. Observed ([graph_structure_parallel_delete_rel](../../Verus_verification/receipts/native/graph_structure_parallel_delete_rel.json)): the ledger acts on the first matching row, and deleting one parallel edge through the ledger also removes the surviving edges' adjacency entries ([stage-A notes, F3](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [Until a ledger reference can name one parallel edge, should the ledger refuse relationship operations on a multigraph triple?](../../Verus_verification/open_questions.md#q-str-004)

### structure.multigraph.restore
- Sources: [spec 234 FR-001 and FR-014](../../../specs/234-multigraph-parallel-edges/spec.md#L209-L214), [snapshot store plan for the mode](../../../iris_vector_graph/_engine/snapshot.py#L157-L160), [restore order](../../../iris_vector_graph/_engine/snapshot.py#L1234-L1300)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- data-integrity, operations

Observed divergence, suspected: a restore writes the rows before the mode, so with a declared index each parallel triple is recorded as a single edge until the next rebuild ([stage-A notes, F5](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [Restoring a multigraph archive into an indexed namespace loses its parallel edges' multiplicity](../../Verus_verification/bugs_issues.md#bug-str-007)

### structure.adjacency
- Sources: [CONTEXT.md, Adjacency Index](../../../CONTEXT.md#L88-L95), [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [Graph.KG.Adjacency](../../../iris_src/src/Graph/KG/Adjacency.cls)
- Children: [declared](#structure.adjacency.declared), [not declared](#structure.adjacency.undeclared), [one writer](#structure.adjacency.one_writer), [bulk loads](#structure.adjacency.bulk), [declaration](#structure.adjacency.declare)
- agent
- architecture-decision

### structure.adjacency.declared
- Sources: [CONTEXT.md, Adjacency Index](../../../CONTEXT.md#L88-L95), [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L12-L16), [spec 252 FR-001, FR-002, FR-016](../../../specs/252-adjacency-functional-index/spec.md#L106-L133), [AdjIndex](../../../iris_src/src/Graph/KG/AdjIndex.cls), [LabelIndex](../../../iris_src/src/Graph/KG/LabelIndex.cls)
- Expands: [adjacency index](#structure.adjacency)
- agent
- data-integrity
- test-coverage

Live coverage: [every writer path leaves the index equal to a recount](../../../tests/e2e/test_252_writer_paths_e2e.py). Shipped in 4.3.0. Observed divergence, suspected: the database ignores an error status from the index callbacks, and the multigraph writers turn their errors into such statuses, so a row can commit without its entry ([stage-A notes, F10](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [Node interning runs inside the functional-index callback, which ADR-0008 rules out](../../Verus_verification/bugs_issues.md#bug-str-010); [The keyed adjacency writers turn errors into statuses that IRIS ignores, so a row can commit without its entry](../../Verus_verification/bugs_issues.md#bug-str-011)

### structure.adjacency.undeclared
- Sources: [CONTEXT.md, Adjacency Index](../../../CONTEXT.md#L88-L95), [ADMIN_GUIDE, the adjacency indexes](../../../docs/ADMIN_GUIDE.md#L1032-L1037), [create_edge without the index](../../../iris_vector_graph/_engine/nodes_edges.py#L1221-L1249)
- Expands: [adjacency index](#structure.adjacency)
- agent
- operations

In such a namespace the engine writes the index over a separate connection, so a rolled-back edge can leave its entry behind until a rebuild; the engine's error message says so.

Findings: [Without the adjacency index, edge writers write adjacency on a second connection that commits separately from the row](../../Verus_verification/bugs_issues.md#bug-str-015)


Review round 3 R3-reader M20: the engine's compensating writes call IVG's `EdgeScan` class, so they need IVG's classes; Cypher writes, `store_edge` and the store's `write_edges` make no compensating call (code reading: no `EdgeScan` call in `_engine/query.py` or `stores/iris_sql_store.py`).
### structure.adjacency.one_writer
- Sources: [ADR-0011](../../../docs/adr/0011-the-adjacency-index-has-one-writer-module.md), [Graph.KG.Adjacency header](../../../iris_src/src/Graph/KG/Adjacency.cls#L1-L47)
- Expands: [adjacency index](#structure.adjacency)
- agent
- architecture-decision
- test-coverage

Coverage is a source scan of the ObjectScript classes: [single-writer guard](../../../tests/unit/test_adjacency_single_writer.py). ADR-0011 amends ADR-0001's list of classes that may touch the index directly. The rule covers out-edge and in-edge entries; label entries are outside it. Observed divergence: a snapshot restore into a namespace without the declared index writes these entries from Python, outside the module and the scan. FHIR sync writes label entries directly ([FHIRGraph](../../../iris_src/src/Graph/KG/FHIRGraph.cls#L2552-L2568)).

### structure.adjacency.bulk
- Sources: [ADR-0008, bulk loads and consequences](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L38-L39), [spec 252 FR-008](../../../specs/252-adjacency-functional-index/spec.md#L119), [engine bulk paths rebuild in finally](../../../iris_vector_graph/_engine/nodes_edges.py#L1866-L1871), [rebuild failures only warn](../../../iris_vector_graph/_engine/nodes_edges.py#L67-L79), [the bulk loader](../../../iris_vector_graph/bulk_loader.py#L1-L22), [loader rebuilds only after a full load](../../../iris_vector_graph/bulk_loader.py#L578-L603)
- Expands: [adjacency index](#structure.adjacency)
- agent
- data-integrity, operations

Rewritten after the stage-A reconstruction check (gap G7, G34 and section 3 item 16). FR-008 covers every bulk path that writes `%NOINDEX`, the bulk loader included, so the reviewer's proposal to limit it to the engine's paths was not applied. "No duplicate rows" means none within the load and none against rows already present, because a `%NOINDEX` insert also skips the unique key (ADR-0008 consequences). Observed divergence: the engine paths rebuild in a `finally`, but an index that does not come back is only logged; the bulk loader uses `%NOCHECK`, commits per batch, and rebuilds only after both its node and edge phases succeed, so a failed phase leaves committed rows unindexed until a manual rebuild.

Findings: [A failed indexed rebuild, or a failed rebuild after a bulk load, leaves a partial adjacency index](../../Verus_verification/bugs_issues.md#bug-str-009), [BulkLoader's node and edge loads write without indexes and return before rebuilding them](../../Verus_verification/bugs_issues.md#bug-plt-027)

### structure.adjacency.declare
- Sources: [spec 252](../../../specs/252-adjacency-functional-index/spec.md), [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L40-L41), [ADR-0009](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md); [`iris_vector_graph/schema.py::GraphSchema.ensure_adjacency_index`](../../../iris_vector_graph/schema.py#L821-L898) (prerequisites `:831-860`; per index `:863-897`; backfill before the edge index `:879-884`), [`::GraphSchema.adjacency_index_kind`](../../../iris_vector_graph/schema.py#L785-L818), called last by [`::GraphSchema.ensure_indexes`](../../../iris_vector_graph/schema.py#L600-L731) (`:726`); [`iris_src/src/Graph/KG/TemporalIndex.cls`](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L226-L235) (the backfill); unit tests [test_252_index_declaration.py](../../../tests/unit/test_252_index_declaration.py#L52-L135)
- Playbook: [ADJ-B2.9](../../../experiment/playbook-completion/ontology/04-adjacency.md#L98), [TMP-B11.3](../../../experiment/playbook-completion/ontology/05-temporal.md#L301)
- Verus: see [index_declaration](../../Verus_verification/models/index_declaration/NOTES.md) (`theorem_no_prereq_no_ddl`, `theorem_prereqs_declare_both`, `theorem_declared_left_alone`, `theorem_backfill_before_edge_index`; as-built; controls `skip-ekey-check`, `backfill-after-build`, `redeclare-functional`)
- Expands: [adjacency index](#structure.adjacency)
- agent
- architecture-decision, operations
- test-coverage

Public cases M16 and J07. The playbook's `TMP-B11.3` sits in its temporal module, which is why the baseline found no canonical owner for the backfill order.

### structure.degree
- Sources: [CONTEXT.md, Degree (decided in the 2026-10-12 architecture review)](../../../CONTEXT.md#L103-L107), [ADR-0010](../../../docs/adr/0010-degree-is-counted-never-stored.md)
- Children: [the degree cache](#structure.degree.cache)
- human-verified
- architecture-decision, data-integrity

### structure.degree.cache
- Sources: [ADR-0012](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md), [Adj.Degree](../../../iris_src/src/Graph/KG/Adj.cls#L28-L89), [changelog 4.3.0](../../../CHANGELOG.md#L2952-L2958)
- Expands: [degree](#structure.degree)
- Children: [no rolled-back edges](#structure.degree.cache.uncommitted), [erase](#structure.degree.cache.erase), [warm after a rebuild](#structure.degree.cache.warm)
- agent
- architecture-decision
- test-coverage

Live coverage: [the generation-validated degree cache](../../../tests/e2e/test_degree_cache_live.py). ADR-0012 refines ADR-0010: the count is still never maintained incrementally, only cached. Observed: a second serving path, a whole-graph stamp, lets bulk readers use cached counts without reading generations and treat a missing entry as zero while nothing has written since a full fill.

Findings: [A degree cached before a node is deleted and re-created can be served afterwards as current](../../Verus_verification/bugs_issues.md#bug-str-003); [Drawing degree generations from the version token is not a repair](../../Verus_verification/design_simplification.md#simp-str-005)

### structure.degree.cache.uncommitted
- Sources: [ADR-0012](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md#L10-L27), [Adjacency.WriterLock](../../../iris_src/src/Graph/KG/Adjacency.cls#L51-L73), [changelog 4.7.0 adjacency lock](../../../CHANGELOG.md#L174-L178)
- Playbook: [ADJ-I5.8](../../../experiment/playbook-completion/ontology/04-adjacency.md#L222), [ADJ-I5.9](../../../experiment/playbook-completion/ontology/04-adjacency.md#L223)
- Verus: active (public M10): `G-graph_structure` (as-built) [`graph_structure.rs`](../../Verus_verification/models/graph_structure/graph_structure.rs) `theorem_as_built_cache_sound` with witnesses `witness_aba_delete_and_recreate_serves_stale_degree`, `witness_gen0_erase_alone_serves_stale_degree` and repaired `theorem_repaired_cache_sound`. Overlapping: the playbook's `proofs-pa3` `adj_l2` (reviewed design; controls `control_fc0401_write_before_gen`, `control_hd0401_erase_kills_gen`).
- Expands: [degree cache](#structure.degree.cache)
- agent
- data-integrity
- test-coverage

Live coverage: [rollback race over two connections](../../../tests/e2e/test_degree_cache_live.py). The lock details answer reconstruction gap G26: the lock is per graph, held shared by writers until commit or rollback, probed exclusively without waiting by readers ([Adj.Degree](../../../iris_src/src/Graph/KG/Adj.cls#L63-L80)). Superseded in part: ADR-0012 and the degree-cache spec said a writer that cannot lock writes nothing; 4.7.0 changed that so the row and its entry are written, and caching stops for the graph instead. No ADR records the change.

Findings: [ADR-0012 does not mention the lockless-writer fallback that 4.7.0 added](../../Verus_verification/bugs_issues.md#bug-doc-008)

### structure.degree.cache.erase
- Sources: [degree-cache spec, erase edge case](../../../specs/248-alt-parity-os/spec.md#L76-L77), [Adjacency.RemoveSource](../../../iris_src/src/Graph/KG/Adjacency.cls#L344-L391), [Adj.Degree post-store check](../../../iris_src/src/Graph/KG/Adj.cls#L46-L49)
- Expands: [degree cache](#structure.degree.cache)
- agent
- data-integrity
- test-coverage

Live coverage: [erase clears generations and cached degrees](../../../tests/e2e/test_degree_cache_live.py). The spec claims a recheck after storing closes the erase window. Observed divergence, suspected: a reader whose recount spans an erase and enough rewrites to bring the generation back to its starting value passes both checks and stores an old count ([stage-A notes, F2](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [A degree cached before a node is deleted and re-created can be served afterwards as current](../../Verus_verification/bugs_issues.md#bug-str-003)

### structure.degree.cache.warm
- Playbook: [ADJ-B5.17](../../../experiment/playbook-completion/ontology/04-adjacency.md#L235), [ADJ-B5.17.2](../../../experiment/playbook-completion/ontology/04-adjacency.md#L241), [ADJ-B5.17.4](../../../experiment/playbook-completion/ontology/04-adjacency.md#L243)
- Verus: [warm_sources](../../Verus_verification/models/warm_sources/NOTES.md), as-built source fill/count and stamp contracts with failed-probe, token-motion and generation-motion controls. ObjectScript binding is inspected only; source enumeration completeness during concurrent changes remains an environment premise.
- Sources: [ADR-0012 consequences](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md#L29-L35), [Adjacency.EndRebuild](../../../iris_src/src/Graph/KG/Adjacency.cls#L857-L869), [Adj.WarmAll](../../../iris_src/src/Graph/KG/Adj.cls#L177-L205)
- Expands: [degree cache](#structure.degree.cache)
- agent
- operations
- test-coverage

Live coverage: [a rebuild leaves the cache warm](../../../tests/e2e/test_degree_cache_live.py). Observed: the rebuild advances the graph-version token right after filling the cache, which voids the whole-graph stamp it has just set; the per-node entries stay valid ([stage-A notes, S5](../../uplift/ivg-verus-initial/intent/graph-structure.md#design-simplifications-p)).

Findings: [Bump the version token before ending a rebuild so the warm stamp survives it](../../Verus_verification/design_simplification.md#simp-str-003)

### structure.rebuilt
- Sources: [CONTEXT.md, Rebuilt store](../../../CONTEXT.md#L109-L114), [ADR-0008 decision](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L23-L26), [freshness module](../../../iris_vector_graph/freshness.py), [two-hop stamps](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L939-L992)
- Children: [token](#structure.rebuilt.token), [stamp](#structure.rebuilt.stamp), [valid results](#structure.rebuilt.valid), [rollback](#structure.rebuilt.rollback), [stale snapshot reads](#structure.rebuilt.stale_read)
- agent
- architecture-decision, data-integrity

The interned snapshot's graph scope is stated in [graph scope](../concepts/graph-scope.g5.md#graph.unscoped_snapshot). Observed divergence: the interned snapshot decides freshness with its own stale flag and a per-process flag rather than a token stamp, and every edge write also updates it in place. The freshness module is imported nowhere.

### structure.rebuilt.token
- Sources: [CONTEXT.md, Graph-Version Token](../../../CONTEXT.md#L116-L119), [token audit](../../../specs/236-arno-callout-adoption/research-token-audit.md#L15-L40), [label writes raise it](../../../iris_src/src/Graph/KG/Adjacency.cls#L767-L787), [restore raises the token](../../../iris_vector_graph/_engine/snapshot.py#L48-L58), [algorithm cache admission](../../../iris_vector_graph/algo_cache.py#L15-L17)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- data-integrity
- test-coverage

Live coverage: [every write path moves the token](../../../tests/integration/test_236_token_write_paths.py). Restated after the stage-A reconstruction check (gap G5, section 3 item 12). CONTEXT.md words it as "every write path able to change what an algorithm answers". The token audit narrows the token to every change of the adjacency index and has the cache admit only answers that depend on nothing else: PageRank, PPR, WCC and CDLP, with PageRank also keyed on the node set. The [algorithm cache](algorithms.g5.md#algorithms.cache.token) owns that admission rule. The reviewer's claim that label writes do not move the token was not applied: since the label index (4.3.0), every label row change raises it. The comment in `algo_cache.py` that no token moves for labels predates that. Observed: while a restore is running, the token can briefly hold a value read from the archive before it is raised past both. Observed divergence (review round 2, code reading only): without the declared adjacency index, a temporal write to a triple that already has an adjacency entry rewrites its stored weight without moving the token ([Adjacency.cls](../../../iris_src/src/Graph/KG/Adjacency.cls#L128-L136)); a token-validated cache could serve the old weight. The algorithm cache admits only PageRank, PPR, WCC and CDLP, which ignore weights, so it is unaffected; whether any `^ArnoKG` reader uses weights is not traced (the Arno library is not in this repository). Suspected, non-indexed installs only, not run.

Findings: [Without the adjacency index, a temporal write to an existing triple changes its stored weight without moving the version token](../../Verus_verification/bugs_issues.md#bug-str-016)

### structure.rebuilt.stamp
- Sources: [CONTEXT.md, Rebuilt store](../../../CONTEXT.md#L109-L114), [spec 244 freshness](../../../specs/244-alt-freshness-module/spec.md#L70-L74); [`iris_vector_graph/freshness.py::Freshness._read_int`](../../../iris_vector_graph/freshness.py#L45-L52), [`::Freshness.token`](../../../iris_vector_graph/freshness.py#L54-L57), [`::Freshness.built_from`](../../../iris_vector_graph/freshness.py#L66-L68), [`::Freshness.is_current`](../../../iris_vector_graph/freshness.py#L70-L72), [`::Freshness.stale_stores`](../../../iris_vector_graph/freshness.py#L74-L77); [`iris_src/src/Graph/KG/TraversalKHop.cls::Fresh`](../../../iris_src/src/Graph/KG/TraversalKHop.cls#L237-L243); unit tests [test_freshness.py](../../../tests/unit/test_freshness.py)
- Playbook: [ADJ-B7](../../../experiment/playbook-completion/ontology/04-adjacency.md#L255), [ADJ-B7.1](../../../experiment/playbook-completion/ontology/04-adjacency.md#L256)
- Verus: see [freshness_stamp](../../Verus_verification/models/freshness_stamp/NOTES.md) (`theorem_is_current_iff_stamped_equal`, `theorem_unstamped_stale_at_zero`, `theorem_stamped_zero_current`; as-built; control `unset-stamp-reads-zero`)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- data-integrity
- test-coverage

Public case M09. The Python `Freshness` class has no caller inside the product package (no module imports `iris_vector_graph.freshness`); the reader that decides freshness at run time is `TraversalKHop.Fresh` for the two-hop counts. Both are bound: the Python class by an enumerated comparison against the model's twin, the ObjectScript method by inspection only.

### structure.rebuilt.valid
- Sources: [CONTEXT.md, Graph-Version Token](../../../CONTEXT.md#L116-L119), [AlgoCache](../../../iris_src/src/Graph/KG/AlgoCache.cls#L1-L51), [the store's cache path](../../../iris_vector_graph/stores/iris_sql_store.py#L921-L987)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- data-integrity
- test-coverage

Live coverage: [every write path moves the token](../../../tests/integration/test_236_token_write_paths.py).

Findings: [A cached algorithm answer computed over a write that later rolls back stays current](../../Verus_verification/bugs_issues.md#bug-str-002)

### structure.rebuilt.rollback
- Sources: [ADR-0012 context, the unsafe case](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md#L19-L27), [token audit, fix 3](../../../specs/236-arno-callout-adoption/research-token-audit.md#L163-L171), [BuildKG bumps after a rollback](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L164-L170)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- uncertain
- data-integrity

Observed ([graph_structure_algo_cache_rollback](../../Verus_verification/receipts/native/graph_structure_algo_cache_rollback.json)): the algorithm cache and the stamped snapshots have no guard like the degree cache's lock probe, and ordinary rollbacks do not advance the token, so such a result stays current until the next write ([stage-A notes, F1](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)). Plausible answers: (a) yes, guard the cache or advance the token after every rollback; (b) no, accept results that can include rolled-back content until the next write.

Findings: [A cached algorithm answer computed over a write that later rolls back stays current](../../Verus_verification/bugs_issues.md#bug-str-002)

### structure.rebuilt.stale_read
- Sources: [ADMIN_GUIDE, the adjacency indexes](../../../docs/ADMIN_GUIDE.md#L1032-L1062), [EnsureNKG](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L393-L425), [variable-length routing](../../../iris_vector_graph/_engine/query.py#L2454-L2457), [IndexNotSyncedError](../../../iris_vector_graph/errors.py#L78-L88)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- user-facing-behavior, data-integrity

Added after the stage-A reconstruction check (gap G40). Observed divergence: the snapshot counts as stale for these readers only when an erasure marked it, or when this engine process itself made a bulk write; it does not compare a token stamp. So another process's bulk write leaves a variable-length query answering from the old snapshot until a rebuild.

### structure.drift
- Sources: [CONTEXT.md, Drift](../../../CONTEXT.md#L121-L126), [ADR-0008, existing installs](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L40-L41), [spec 252 FR-009](../../../specs/252-adjacency-functional-index/spec.md#L120-L121)
- agent
- data-integrity, operations
- test-coverage

Live coverage: [declaring the index repairs a drifted install](../../../tests/e2e/test_252_drifted_install_e2e.py). Observed divergence, suspected: several paths can still produce drift with the index declared ([stage-A notes, F3 to F6 and F10](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

### structure.rebuild
- Sources: [engine.sync](../../../iris_vector_graph/_engine/schema.py#L2859-L2912), [ADMIN_GUIDE, the adjacency indexes](../../../docs/ADMIN_GUIDE.md#L1032-L1062), [spec 252 FR-010](../../../specs/252-adjacency-functional-index/spec.md#L122), [BuildKG](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L30-L172)
- Children: [failure](#structure.rebuild.failure)
- agent
- operations

Findings: [A failed indexed rebuild, or a failed rebuild after a bulk load, leaves a partial adjacency index](../../Verus_verification/bugs_issues.md#bug-str-009)

### structure.rebuild.failure
- Sources: [degree-cache spec, rebuild failure](../../../specs/248-alt-parity-os/spec.md#L74-L75), [BuildKG comment on early failure](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L46-L58), [ADMIN_GUIDE, never sees it empty](../../../docs/ADMIN_GUIDE.md#L1048-L1049)
- Expands: [rebuild](#structure.rebuild)
- agent
- uncertain
- operations, data-integrity

The guide's "a reader during the rebuild never sees it empty" may refer only to the interned snapshot. The adjacency index is different: the code accepts that readers see too few edges while an index rebuild runs ([RebuildEdgeIndices](../../../iris_src/src/Graph/KG/Ledger.cls#L214-L224)), and a rebuild without the declared index commits every 50,000 edges. What is open is a failure partway. Observed, suspected: with a declared index the rebuild empties the adjacency first and refills it outside any transaction, so a failure partway leaves a partial index until the next successful rebuild ([stage-A notes, F8](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [A failed indexed rebuild, or a failed rebuild after a bulk load, leaves a partial adjacency index](../../Verus_verification/bugs_issues.md#bug-str-009)

### structure.verify
- Sources: [GraphVerify header](../../../iris_src/src/Graph/KG/GraphVerify.cls#L1-L37), [verify_graph](../../../iris_vector_graph/_engine/admin.py#L850-L890), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L444-L452)
- agent
- operations, data-integrity
- test-coverage

Partial live coverage: [a wrong current cache entry is flagged and a stale one ignored](../../../tests/e2e/test_degree_cache_live.py). Observed divergence: on a graph with parallel edges it compares the row count with the number of distinct triples, so it reports rows as missing, and it never checks edge counts; open task T036 of the multigraph spec names this ([stage-A notes, F7](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [verify_graph reports healthy parallel edges as missing adjacency and cannot see lost multiplicity](../../Verus_verification/bugs_issues.md#bug-str-004)
