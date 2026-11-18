# Nodes and relationships

Read about writing and reading nodes and relationships, including parallel edges and reification. For index maintenance, see [adjacency and derived data](../architecture/adjacency-and-derived-data.g5.md).

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
- Some calls use the engine's own native connection: erasing a graph or every graph, a rebuild, switching multigraph mode, named search-index writes (BM25 and vector indexes), temporal purges, rebuilds and settings, and FHIR graph calls. They join the caller's transaction only when the engine was made on the caller's own connection; with `from_connect` they commit on their own ([erasure](erasure.g5.md#erasure.atomic)). Whether this should depend on how the engine was opened is [open](../../Verus_verification/open_questions.md#structure.write.engine-connection).
- Today, when the caller turned the driver's autocommit off and has written nothing yet, such a call can commit on its own even on the caller's connection; a temporal setting does.
- Deleting nodes removes the reifier nodes of their edges in later transactions.
- Temporal writes follow their own rule ([temporal writes](temporal.g5.md#temporal.write)).

- Working assumption: Allow the observed interleavings on both paths: a native or SQL read may see a writer's uncommitted writes, including part of one transaction, and loses them on rollback. Grant snapshot or all-or-nothing visibility only to paths with an explicit synchronization contract and evidence (none for Cypher reads). The ADR-0012 degree cache is the one guarded structure.
- Working assumption: Treat transaction membership as dependent on the connection used by the engine.

## Nodes

<a id="structure.node"></a>
[I · structure.node]

`create_node` changes nothing and reports False when the node already exists in its graph. A write that IRIS refuses raises an error and leaves nothing behind.

- When two callers create the same node at once, one creates it and the other reports False.
- A new node gets an `id` property equal to its ID unless the caller gives one. The ledger reserves that property name ([changesets](ledger.g5.md#ledger.changeset)).

<a id="structure.node.bulk"></a>
[I · structure.node.bulk]

`bulk_create_nodes` returns the accepted input IDs in order, including repeats and nodes already present. It skips IDs that Python treats as empty, including 0, False, None and empty text; each node's own graph value wins over the call's graph, and None names the default graph.

- Existing nodes gain labels and property keys they lack and keep the values they already hold. Before adding any node row, the batch removes properties left for its IDs whose node row is missing in that graph; repeated IDs then merge into the first occurrence, and other graphs stay unchanged.
- A None-valued property is omitted. An absent `id` property defaults to the node ID; an explicit None-valued `id` property is omitted too. [Node reads](#structure.node.read) apply the shared type and alias rules.
- A SQL batch that leaves indexes in place checks every expected parent, label and non-null property key before returning. A missing required row or failed write raises and takes back that SQL operation under the database transaction contract; an existing property's different value is a permitted merge.
- The native loader's chunk commits and index drop/rebuild follow the separate [bulk-load boundary](../operations/snapshots-and-bulk-load.g5.md#install.bulk_load); the SQL rollback rule does not establish those guarantees.

<a id="structure.node.delete"></a>
[I · structure.node.delete]

Deleting a node removes, in its graph, its labels, properties, documents, vectors and incident edges, and then the reifier nodes of those edges.

- The node and its own rows go in one transaction.
- Without a named graph, the delete uses the one graph that holds the ID ([graph scope](../concepts/graph-scope.g5.md#graph.default)).
- A delete by ID or by prefix in one graph leaves the same IDs, their edges and their labels in other graphs; another node with the same label keeps it.

<a id="structure.node.delete.bulk"></a>
[D · structure.node.delete.bulk]

Bulk node deletion drops None and empty IDs, converts the rest to text and removes repeats, then runs batches in each selected graph; a failed batch is logged and later batches still run. Its `DeleteResult` reports `deleted` from calls that returned successfully and `failed` as the number of requested IDs in calls that raised; converting it to an integer or boolean uses only `deleted`.

- A true result can have failures. A false result does not prove that nothing was deleted: a node delete can finish before its later reifier cleanup raises, and the caller counts that whole batch as failed.
- The same risk applies when an underlying store call commits some chunks before a later chunk fails ([erasure atomicity](erasure.g5.md#erasure.atomic)). The batch log's claim that everything rolled back is too strong.
- With an explicit graph only that graph is selected. With graph omitted, an ID held in several graphs is refused before any deletion.

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

- Properties named `id` and `labels` are returned as `p_id` and `p_labels`, keeping the structural ID and label list intact. If the caller also stored `p_id` or `p_labels`, today's flat result loses one value according to property row order; see [the unresolved alias rule](../../Verus_verification/open_questions.md#q-iter-001).
- A node with child rows is included without a separate node-row check; orphan child rows can therefore appear as a node. Reads fail if a database read fails, rather than returning a fabricated empty node.

- Working assumption: Preserve both accepted property values and structural identity; reserve aliases or introduce a property map only after a compatibility choice.

<a id="structure.node.read.properties"></a>
[I · structure.node.read.properties]

The property lookups match and return values as they are stored.

- `get_nodes_by_property` and `get_node_ids_by_property` compare `val` with the stored text, so "7" finds both a number 7 and a string "7", and "true" finds a stored true.
- `get_nodes_by_property` and `get_nodes_by_label` return default-graph nodes as `get_node` does; `get_node_ids_by_property`, `get_property_values` and `get_property_pairs` read every graph ([open question](../../Verus_verification/open_questions.md#HD-0201)).
- `get_property_values` and `get_property_pairs` return numbers as numbers. Today they return a stored true as the string "true", where `get_node` returns true.
- `get_node_properties` is `get_node` without `id` and `labels`; `nodes_exist` looks in every graph; `list_graphs` lists the named graphs that have edges.

## Edges

<a id="structure.edge"></a>
[I · structure.edge]

An edge connects two nodes of the same graph and may carry qualifiers. Creating an edge adds any missing endpoint to that graph in the same transaction, so a failed edge leaves no node behind.

<a id="structure.edge.single"></a>
[I · structure.edge.single]

Outside multigraph mode a graph holds at most one ordinary edge per triple. An ordinary duplicate changes no edge values: `create_edge` reports False, while `store_edge` accepts it and reports True; neither treats it as an error.

<a id="structure.edge.weight"></a>
[D · structure.edge.weight]

An edge's weight lives in its qualifiers, so the adjacency index, a rebuild and Cypher's `r.weight` all read the same value. An edge with no weight costs 1.0 in weighted walks.

<a id="structure.edge.weight.set"></a>
[I · structure.edge.weight.set]

`set_edge_weight` changes the weight of an existing edge in the default graph only. It updates every edge of the triple in one transaction, and reports False, writing nothing, when the default graph has no such edge.

<a id="structure.edge.delete"></a>
[I · structure.edge.delete]

Deleting an edge removes the triple's edges from one graph, or from every graph when the caller asks for that. It reports success even when nothing matched, and a delete that IRIS refuses raises an error and removes nothing.

- Working assumption: Treat edge deletion as removing only the rows its implementation explicitly cleans up.
- Deleting an edge from one graph leaves the same triple in every other graph, with its adjacency entry and traversal answers.

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

- Working assumption: Keep direct create as deduplicating at this pin; the specification planned keyed parallel creation, whose public ID-returning interface is unfinished.
- Working assumption: Keep the spec requirement to refuse ambiguous ledger references; do not accept first-row selection as intended parallel-edge semantics.

<a id="structure.multigraph.off"></a>
[I · structure.multigraph.off]

With the mode off, a graph behaves exactly as before multigraph mode existed, with the same storage, generated SQL and adjacency layout. Every writer uses edge key 0, so such a graph holds at most one edge row per triple.

<a id="structure.multigraph.switch"></a>
[I · structure.multigraph.switch]

Turning multigraph mode on is always allowed. Turning it off is refused while any triple of the graph holds more than one edge, and erasing a graph clears its mode.

<a id="structure.multigraph.count"></a>
[D · structure.multigraph.count]

Degree counts every edge of a multigraph triple, while the interned snapshot keeps one entry per triple. Edge embeddings stay per triple, so parallel edges share one.
- A one-hop read answers one row per relationship. Two edges of one type between the same two nodes are two rows, and `count()` counts both.
- The one-hop ID shortcut keeps this rule: it repeats a target once for each edge the triple holds.
- Cypher tells relationships apart by edge ID, so two equal parallel edges stay two; asking for distinct answers folds them.
- Deleting one of two parallel edges with Cypher `DELETE r` leaves the other: the target is still reached, the triple carries the survivor's weight, and the degree drops by one.

<a id="structure.multigraph.restore"></a>
[I · structure.multigraph.restore]

A restore brings back each graph's multigraph mode with its edges, so a restored multigraph keeps its parallel edges, their layout and their counts.

## Degree

<a id="structure.degree"></a>
[D · structure.degree]

A node's degree is counted from the adjacency index when asked and is never kept as a stored counter. A stored counter cannot stay exact when transactions roll back, and no reader needs one.

## Earlier links

These links take you to the current sections and statements.

<a id="graph-structure"></a>

[Nodes and relationships](#nodes-and-relationships)

<a id="adjacency-index"></a>

[Who maintains the adjacency index?](../architecture/adjacency-and-derived-data.g5.md#who-maintains-the-adjacency-index)

<a id="rebuilt-stores-and-the-graph-version-token"></a>

[Rebuilt stores and the graph-version token](../architecture/adjacency-and-derived-data.g5.md#rebuilt-stores-and-the-graph-version-token)

<a id="drift-rebuild-and-verification"></a>

[Find and repair index drift](../operations/status-and-repair.g5.md#find-and-repair-index-drift)

<a id="structure.multigraph.layout"></a>

[structure.multigraph.layout](../architecture/adjacency-and-derived-data.g5.md#structure.multigraph.layout)

<a id="structure.adjacency"></a>

[structure.adjacency](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency)

<a id="structure.adjacency.declared"></a>

[structure.adjacency.declared](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.declared)

<a id="structure.adjacency.undeclared"></a>

[structure.adjacency.undeclared](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.undeclared)

<a id="structure.adjacency.one_writer"></a>

[structure.adjacency.one_writer](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.one_writer)

<a id="structure.adjacency.bulk"></a>

[structure.adjacency.bulk](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.bulk)

<a id="structure.adjacency.scan"></a>

[structure.adjacency.scan](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.scan)

<a id="structure.adjacency.declare"></a>

[structure.adjacency.declare](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.declare)

<a id="structure.degree.cache"></a>

[structure.degree.cache](../architecture/adjacency-and-derived-data.g5.md#structure.degree.cache)

<a id="structure.degree.cache.uncommitted"></a>

[structure.degree.cache.uncommitted](../architecture/adjacency-and-derived-data.g5.md#structure.degree.cache.uncommitted)

<a id="structure.degree.cache.erase"></a>

[structure.degree.cache.erase](../architecture/adjacency-and-derived-data.g5.md#structure.degree.cache.erase)

<a id="structure.degree.cache.warm"></a>

[structure.degree.cache.warm](../architecture/adjacency-and-derived-data.g5.md#structure.degree.cache.warm)

<a id="structure.rebuilt"></a>

[structure.rebuilt](../architecture/adjacency-and-derived-data.g5.md#structure.rebuilt)

<a id="structure.rebuilt.token"></a>

[structure.rebuilt.token](../architecture/adjacency-and-derived-data.g5.md#structure.rebuilt.token)

<a id="structure.rebuilt.stamp"></a>

[structure.rebuilt.stamp](../architecture/adjacency-and-derived-data.g5.md#structure.rebuilt.stamp)

<a id="structure.rebuilt.valid"></a>

[structure.rebuilt.valid](../architecture/adjacency-and-derived-data.g5.md#structure.rebuilt.valid)

<a id="structure.rebuilt.stale_read"></a>

[structure.rebuilt.stale_read](../architecture/adjacency-and-derived-data.g5.md#structure.rebuilt.stale_read)

<a id="structure.drift"></a>

[structure.drift](../operations/status-and-repair.g5.md#structure.drift)

<a id="structure.rebuild"></a>

[structure.rebuild](../operations/status-and-repair.g5.md#structure.rebuild)

<a id="structure.verify"></a>

[structure.verify](../operations/status-and-repair.g5.md#structure.verify)

## Metadata

### structure.write

- uncertain
- Sources: [WriteTxn](../../../iris_vector_graph/_write_txn.py#L1-L28), [Graph.KG.Txn](../../../iris_src/src/Graph/KG/Txn.cls), [the engine's own native connection](../../../iris_vector_graph/engine.py#L1894-L1943), [erase_graph uses it](../../../iris_vector_graph/_engine/nodes_edges.py#L1513-L1517), [set_multigraph uses it](../../../iris_vector_graph/_engine/admin.py#L893-L915), [restore refuses a caller transaction](../../../iris_vector_graph/_engine/snapshot.py#L1095-L1102), [bulk loader refuses one](../../../iris_vector_graph/bulk_loader.py#L156-L163), [reifiers deleted afterwards](../../../iris_vector_graph/_engine/nodes_edges.py#L2176-L2200)
- Children: [Should whether a write joins the caller's transaction depend on how the engine was opened?](../../Verus_verification/open_questions.md#structure.write.engine-connection)
- Verus: [write_routing](../../Verus_verification/models/write_routing/NOTES.md) `theorem_writetxn_call_follows_caller_end`, `theorem_start_transaction_direct_call_follows_caller_end`, `theorem_autocommit_off_temporal_edge_splits`, `theorem_own_process_write_survives_rollback`, `theorem_routing`, `theorem_loader_refusal` (as built)
- agent
- architecture-decision, data-integrity

Introduced in 4.6.4: before it, an engine write inside a caller's transaction committed or rolled back the caller's earlier work. The exceptions were added after the stage-A reconstruction check (its 2(b) item 14) and checked in the code. The separate native connection exists so that Native API calls never share a connection with cursor DDL; without the caller's credentials the engine uses the caller's own connection, and these calls then nest. Inside a caller's transaction, `bulk_create_nodes` and `bulk_create_edges` keep the indexes and nest instead of dropping them. Whether erasure should refuse an open caller transaction is the erasure page's open question.

Findings: [A failed BM25 insert or delete rolls back the caller's whole transaction](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-srch-002); [The Txn_End and Txn_Undo SQL procedures end every transaction level, the caller's included](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-021); [With the driver's autocommit off, rolling back a create_edge_temporal keeps the temporal edge but removes its structural edge and nodes](../../Verus_verification/bugs_issues.md#bug-tmp-102); [The user guide says a from_connect engine's temporal edge writes run outside the caller's transaction; create_edge_temporal joins it](../../Verus_verification/bugs_issues.md#bug-plt-107)

Open questions: [What may a native read answer while another writer's transaction is open?](../../Verus_verification/open_questions.md#HD-0903), [Should whether a write joins the caller's transaction depend on how the engine was opened?](../../Verus_verification/open_questions.md#structure.write.engine-connection)

State machines: [write routing](../../Verus_verification/models/write_routing/manifest.json)

### structure.node

- Sources: [create_node](../../../iris_vector_graph/_engine/nodes_edges.py#L968-L1104), [a concurrent duplicate reports False](../../../iris_vector_graph/_engine/nodes_edges.py#L1095-L1104), [ledger reserved names](../../../iris_src/src/Graph/KG/LedgerApply.cls#L68-L71), [API reference](../../../docs/API_REFERENCE.md)
- Children: [deleting a node](#structure.node.delete), [writing a node](#structure.node.update), [reading nodes](#structure.node.read)
- agent
- user-facing-behavior

The `id` property dates from 4.6.0 (R181), so that `MATCH (n {id: ...})` finds the node. The concurrent-create bullet answers reconstruction gap G36 for nodes: uniqueness rests on the node table's key, with no lock.

### structure.node.bulk

- design-verified
- Sources: [bulk writer](../../../iris_vector_graph/_engine/nodes_edges.py#L1648-L1873), [orphan cleanup](../../../iris_vector_graph/_engine/nodes_edges.py#L1617-L1646), [child merge tests](../../../tests/e2e/test_460_bulk_create_nodes_paths_e2e.py), [orphan tests](../../../tests/e2e/test_470_bulk_orphan_props_e2e.py)
- Expands: [nodes](#structure.node)
- Formal contract: [bulk children](../../Verus_verification/models/bulk_children/bulk_children.rs)
- agent
- user-facing-behavior, data-integrity

State machines: [bulk children](../../Verus_verification/models/bulk_children/manifest.json)

### structure.node.delete

- Sources: [API reference, delete_node](../../../docs/API_REFERENCE.md#L516-L522), [delete_node](../../../iris_vector_graph/_engine/nodes_edges.py#L2227-L2268), [Eraser.EraseIdSet](../../../iris_src/src/Graph/KG/Eraser.cls#L467-L632)
- Verus: [node_edge_update](../../Verus_verification/models/node_edge_update/NOTES.md) `theorem_delete_node_removes_incident` (as built); [evidence](../../uplift/consolidated/iteration-33/update-delete-PAIRS.md)
- Expands: [nodes](#structure.node)
- Children: [bulk deletion counts](#structure.node.delete.bulk)
- agent
- user-facing-behavior, data-integrity
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `theorem_erase_nodes_takes_incident`, `theorem_label_delete_scoped`

Observed: the reifier nodes are deleted in later transactions, and a failure there raises an error that says the node is gone and its reifiers are not. Erasure semantics are owned by the erasure pages.

State machines: [node edge update](../../Verus_verification/models/node_edge_update/manifest.json)

### structure.node.delete.bulk

- design-verified
- Sources: [`NodesEdgesMixin.bulk_delete_nodes`](../../../iris_vector_graph/_engine/nodes_edges.py#L2270-L2299), [`_delete_in_scope`](../../../iris_vector_graph/_engine/nodes_edges.py#L2176-L2200), [`DeleteResult`](../../../iris_vector_graph/_engine/nodes_edges.py#L103-L111), [`_delete_scopes`](../../../iris_vector_graph/_engine/nodes_edges.py#L2202-L2225), [`IRISGraphStore.delete_nodes`](../../../iris_vector_graph/stores/iris_sql_store.py#L1323-L1361)
- Verus: [bulk_delete](../../Verus_verification/models/bulk_delete/NOTES.md), as-built `theorem_later_batch_runs_after_failure`, `theorem_failed_counts_requested_not_existing`, `theorem_cleanup_failure_is_not_rollback`; raw ID filtering, positive batching and primary/cleanup failure ordering. Provider calls are substituted in the Python comparison; no live erase or implementation proof.
- Expands: [deleting nodes](#structure.node.delete)
- agent
- user-facing-behavior, data-integrity

Findings: [inherited partial erase](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-led-011). Reifier cleanup is another inspected partial-effect path; the new unit comparison observes its Python caller with a substituted store, not IRIS erasure.

State machines: [bulk delete](../../Verus_verification/models/bulk_delete/manifest.json)

### structure.node.update

- Sources: [store_node](../../../iris_vector_graph/_engine/nodes_edges.py#L2393-L2530), [API reference, store_node](../../../docs/API_REFERENCE.md#L738-L750)
- Verus: [node_edge_update](../../Verus_verification/models/node_edge_update/NOTES.md) `theorem_store_node_updates`, `theorem_store_new_gets_id` (as built); [evidence](../../uplift/consolidated/iteration-33/update-delete-PAIRS.md)
- Expands: [nodes](#structure.node)
- agent
- user-facing-behavior

Added after the stage-A reconstruction check (gap G15). The docstring and API reference state this contract. Before 4.5.0 a failed property was skipped after the node row had committed. Cypher `SET` and ledger property and label operations are the other ways to change a node, owned by the Cypher and ledger pages.

State machines: [node edge update](../../Verus_verification/models/node_edge_update/manifest.json)

### structure.node.read

- design-verified

- uncertain
- Sources: [`NodesEdgesMixin.get_nodes`](../../../iris_vector_graph/_engine/nodes_edges.py#L621-L702), [`::get_node`](../../../iris_vector_graph/_engine/nodes_edges.py#L563-L585), [`::create_node`](../../../iris_vector_graph/_engine/nodes_edges.py#L968-L1107), [typed node values](../../../iris_vector_graph/prop_values.py#L211-L232)
- Verus: [node_read](../../Verus_verification/models/node_read/NOTES.md) `theorem_bare_node_vs_absent`, `theorem_requested_duplicates_remain`, `theorem_structural_keys_kept`, `witness_alias_collision` (as-built); real Python writer/reader comparison with substituted storage and `CY_TYPED`. Graph isolation remains the existing graph owner's obligation, not a new live cross-graph claim.
- agent
- user-facing-behavior, data-integrity
- Expands: [nodes](#structure.node)
- Children: [How should flat node reads preserve colliding property aliases?](../../Verus_verification/open_questions.md#q-iter-001)

Findings: [Colliding flat property aliases](../../Verus_verification/bugs_issues.md#bug-str-101).; [get_property_values and get_property_pairs return a stored boolean as the string "true"](../../Verus_verification/bugs_issues.md#bug-str-102)

Audit reproduction: [bug-str-101](../../Verus_verification/bugs_issues.md#bug-str-101) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Open questions: [How should flat node reads preserve colliding property aliases?](../../Verus_verification/open_questions.md#q-iter-001)

State machines: [ndjson export](../../Verus_verification/models/ndjson_export/manifest.json), [node read](../../Verus_verification/models/node_read/manifest.json)

### structure.node.read.properties

- Sources: [API reference, property readers](../../../docs/API_REFERENCE.md#L588-L720), [readers](../../../iris_vector_graph/_engine/nodes_edges.py)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-34/property-readers-PAIRS.md)
- Expands: [node reads](#structure.node.read)
- agent
- user-facing-behavior

No formal contract: the outcomes are observed natively only.

Findings: [get_property_values and get_property_pairs return a stored boolean as the string "true"](../../Verus_verification/bugs_issues.md#bug-str-102)

### structure.edge

- Sources: [CONTEXT.md, Structural Edge](../../../CONTEXT.md#L60-L63), [create_edge](../../../iris_vector_graph/_engine/nodes_edges.py#L1151-L1255), [rdf_edges DDL](../../../iris_vector_graph/schema.py#L34-L45)
- Children: [one edge per triple](#structure.edge.single), [weight](#structure.edge.weight), [deleting edges](#structure.edge.delete)
- agent
- user-facing-behavior, data-integrity

Before 4.5.0 a refused edge left its endpoint rows committed and answered False.

### structure.edge.single

- design-verified
- Sources: [USER_GUIDE, parallel edges](../../../docs/USER_GUIDE.md#L469-L473), [Known issue: CREATE of an existing relationship](../../../docs/KNOWN_ISSUES.md#a-cypher-create-of-a-relationship-that-already-exists-adds-nothing), [spec 234 context](../../../specs/234-multigraph-parallel-edges/spec.md#L11-L35)
- Expands: [edges](#structure.edge)
- Formal contract: [edge acceptance](../../Verus_verification/models/edge_acceptance/edge_acceptance.rs)
- agent
- user-facing-behavior

An explicit create of a triple whose only row came from a temporal write adopts that row instead; the temporal pages own that rule.

State machines: [edge acceptance](../../Verus_verification/models/edge_acceptance/manifest.json)

### structure.edge.weight

- Sources: [ADR-0008, scope of step 2](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L28-L46), [spec 252 FR-006 and FR-015](../../../specs/252-adjacency-functional-index/spec.md#L117-L131), [Adjacency.WeightOf](../../../iris_src/src/Graph/KG/Adjacency.cls#L750-L765)
- Expands: [edges](#structure.edge)
- Children: [setting a weight](#structure.edge.weight.set)
- agent
- user-facing-behavior, data-integrity

Before 4.3.0 the weight could live in the adjacency alone, so a rebuild lost it.

Findings: [A ledger qualifier update reweights a multigraph triple's leaf to an edge that is not the lowest](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-012)

### structure.edge.weight.set

- Sources: [set_edge_weight](../../../iris_vector_graph/_engine/nodes_edges.py#L1306-L1380), [API reference, set_edge_weight](../../../docs/API_REFERENCE.md#L716-L722)
- Verus: [node_edge_update](../../Verus_verification/models/node_edge_update/NOTES.md) `theorem_set_weight_default_graph_only` (as built); [evidence](../../uplift/consolidated/iteration-33/update-delete-PAIRS.md)
- Expands: [weight](#structure.edge.weight)
- agent
- user-facing-behavior
- test-coverage

Live coverage: [set_edge_weight is one transaction](../../../tests/e2e/test_set_edge_weight_txn_e2e.py). Added after the stage-A reconstruction check (gap G15). Before 4.6.0 a refused update answered False like a missing edge, and a multigraph triple's rows were updated one by one.

State machines: [node edge update](../../Verus_verification/models/node_edge_update/manifest.json)

### structure.edge.delete

- uncertain
- Sources: [delete_edge](../../../iris_vector_graph/_engine/nodes_edges.py#L1382-L1456), [API reference, delete_edge](../../../docs/API_REFERENCE.md#L502-L514)
- Verus: [node_edge_update](../../Verus_verification/models/node_edge_update/NOTES.md) `theorem_delete_edge_one_graph` (as built); [evidence](../../uplift/consolidated/iteration-33/update-delete-PAIRS.md)
- Expands: [edges](#structure.edge)
- Children: [Should deleting an edge also remove its reifications and edge embeddings, as deleting a node, deleting a relationship through the ledger, and erasing edges do?](../../Verus_verification/open_questions.md#structure.edge.delete.reifications)
- agent
- user-facing-behavior
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `theorem_other_graph_untouched`

In a multigraph this removes every parallel edge of the triple; Cypher `DELETE` removes one.

Audit (HD-0202): Existing authority: Without an edge ID, direct delete_edge removes the whole triple. A per-edge ID argument is planned, absent at the pin. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-0202).

Findings: [In a multigraph, does a direct edge delete remove one parallel edge or all of them?](../../Verus_verification/open_questions.md#HD-0202).

Open questions: [Should deleting an edge also remove its reifications and edge embeddings, as deleting a node, deleting a relationship through the ledger, and erasing edges do?](../../Verus_verification/open_questions.md#structure.edge.delete.reifications)

State machines: [node edge update](../../Verus_verification/models/node_edge_update/manifest.json)

### structure.reification

- Sources: [reify_edge, get_reifications, delete_reification](../../../iris_vector_graph/_engine/schema.py#L3264-L3392), [API reference](../../../docs/API_REFERENCE.md#L140-L146), [one reifier names one edge](../../../iris_vector_graph/schema.py#L514-L520), [node deletion removes reifiers](../../../iris_vector_graph/_engine/nodes_edges.py#L2176-L2200)
- agent
- user-facing-behavior, data-integrity

Added after the stage-A reconstruction check (its section 3 item 15). The reifier is always created in the default graph, as the docstring states, even for an edge in a named graph. Deleting a reifier is documented as not graph-scoped, an exception recorded under [default graph](../concepts/graph-scope.g5.md#graph.default); it does not go through the Eraser. Each call nests in a caller's open transaction since 4.7.0.

Findings: [delete_reification deletes the reifier's rows in every graph](../../Verus_verification/bugs_issues.md#bug-str-014)

### structure.multigraph

- uncertain
- Sources: [spec 234 clarifications, 2026-09-26](../../../specs/234-multigraph-parallel-edges/spec.md#L37-L53), [CONTEXT.md, Multigraph mode](../../../CONTEXT.md#L83-L86), [GraphMode](../../../iris_src/src/Graph/KG/GraphMode.cls), [changelog 4.1.0](../../../CHANGELOG.md#L3835-L3853)
- Children: [mode off](#structure.multigraph.off), [switching](#structure.multigraph.switch), [layout](../architecture/adjacency-and-derived-data.g5.md#structure.multigraph.layout), [counting](#structure.multigraph.count), [In a multigraph, must create_edge always add a new edge and offer a variant that returns its ID?](../../Verus_verification/open_questions.md#q-str-003), [Until a ledger reference can name one parallel edge, should the ledger refuse relationship operations on a multigraph triple?](../../Verus_verification/open_questions.md#q-str-004), [restore](#structure.multigraph.restore)
- agent
- user-facing-behavior, architecture-decision

The spec's clarification session records questions and answers without naming who answered, so this stays `agent`. The spec status says mode, storage and Cypher shipped in 4.1.0, and that the ledger and restore work was not done.

Open questions: [In a multigraph, must create_edge always add a new edge and offer a variant that returns its ID?](../../Verus_verification/open_questions.md#q-str-003), [Until a ledger reference can name one parallel edge, should the ledger refuse relationship operations on a multigraph triple?](../../Verus_verification/open_questions.md#q-str-004)

### structure.multigraph.off

- Sources: [spec 234 FR-003, FR-016 and story 4](../../../specs/234-multigraph-parallel-edges/spec.md#L145-L175), [create_edge guards on edge key 0](../../../iris_vector_graph/_engine/nodes_edges.py#L1257-L1273), [rebuild writes leaves only outside the mode](../../../iris_src/src/Graph/KG/Adjacency.cls#L832-L855)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- data-integrity
- test-coverage

Live coverage: [upgrade leaves the adjacency byte-identical](../../../tests/e2e/test_234_multigraph_storage_e2e.py). Observed divergence: the unique key admits a nonzero edge key in a mode-off graph, and the per-engine cache of the mode or an unlocked mode switch can produce one (the per-engine cache itself is documented in API_REFERENCE; the finding is the second row it lets in, which breaks this block's one-row rule), after which deleting either row removes the shared adjacency entry ([stage-A notes, F6](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [A single-edge graph can get two rows for one triple from a stale multigraph flag or an unlocked mode switch](../../Verus_verification/bugs_issues.md#bug-str-008)

Audit reproduction: [bug-str-008](../../Verus_verification/bugs_issues.md#bug-str-008) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

### structure.multigraph.switch

- Sources: [spec 234 FR-002](../../../specs/234-multigraph-parallel-edges/spec.md#L215-L218), [GraphMode.Set](../../../iris_src/src/Graph/KG/GraphMode.cls#L22-L45), [set_multigraph](../../../iris_vector_graph/_engine/admin.py#L893-L926), [Eraser clears the mode](../../../iris_src/src/Graph/KG/Eraser.cls#L244)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live coverage: [mode set, refusal and erase](../../../tests/e2e/test_234_multigraph_storage_e2e.py). Observed divergence: nothing stops a parallel edge from being written between the count and the switch.

Findings: [A single-edge graph can get two rows for one triple from a stale multigraph flag or an unlocked mode switch](../../Verus_verification/bugs_issues.md#bug-str-008)

Audit reproduction: [F-0208](../../Verus_verification/bugs_issues.md#F-0208) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [An engine keeps a graph's mode forever, so another engine's change is not seen](../../Verus_verification/bugs_issues.md#F-0208).

Audit reproduction: [bug-str-008](../../Verus_verification/bugs_issues.md#bug-str-008) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

### structure.multigraph.count

- design-verified
- Sources: [spec 234 clarifications](../../../specs/234-multigraph-parallel-edges/spec.md#L47-L51), [ADR-0010](../../../docs/adr/0010-degree-is-counted-never-stored.md), [Adj.Count](../../../iris_src/src/Graph/KG/Adj.cls#L108-L133); one-hop rows: [`iris_src/src/Graph/KG/TraversalKHop.cls::KHopNeighborIds`](../../../iris_src/src/Graph/KG/TraversalKHop.cls#L28-L66) (repeats a target `#` times, `:42-44`), [`iris_vector_graph/_engine/query.py::_try_khop_fast_path`](../../../iris_vector_graph/_engine/query.py#L4294-L4330) (answers only when the default graph alone holds edges); live test [test_460_one_hop_parallel_edges_e2e.py](../../../tests/e2e/test_460_one_hop_parallel_edges_e2e.py)
- Playbook: [GID-B5.4](../../../experiment/playbook-completion/ontology/02-graph-identity.md#L131), [GID-B5.5](../../../experiment/playbook-completion/ontology/02-graph-identity.md#L132), [NAT-B1.6](../../../experiment/playbook-completion/ontology/09-native-executor.md#L75)
- Verus: no formal contract for the one-hop projection in either arm. `graph_structure` (as-built) models the keyed layout and counts; the playbook's `proofs-d1d` `nread_l2` models native reads of a reviewed design. Neither derives the one-hop row list.
- Expands: [multigraph mode](#structure.multigraph)
- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_appending_row_counts_physical_multiplicity` and `theorem_scalar_is_raw_scoped_cardinality`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). SQL/report census counts matching physical rows. This source relation does not establish ordinary writer uniqueness, adjacency callback maintenance or cache correctness.
- agent
- user-facing-behavior
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `theorem_delete_one_parallel_keeps_other`

Live coverage: [parallel edges count their multiplicity](../../../tests/e2e/test_degree_cache_live.py). Superseded in part: the spec's choice of set semantics for PageRank and personalized PageRank was reversed in 4.6.0, when parallel edges began to weigh their count ([changelog](../../../CHANGELOG.md#L1174-L1179)); the algorithm pages own that rule.

Findings: [Deleting one of several parallel edges through the ledger removes the adjacency of the edges that remain](../../Verus_verification/bugs_issues.md#bug-str-001)

Audit reproduction: [bug-str-001](../../Verus_verification/bugs_issues.md#bug-str-001) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [routine reporting](../../Verus_verification/models/routine_reporting/manifest.json)

### structure.multigraph.restore

- Sources: [spec 234 FR-001 and FR-014](../../../specs/234-multigraph-parallel-edges/spec.md#L209-L214), [snapshot store plan for the mode](../../../iris_vector_graph/_engine/snapshot.py#L157-L160), [restore order](../../../iris_vector_graph/_engine/snapshot.py#L1234-L1300)
- Expands: [multigraph mode](#structure.multigraph)
- agent
- data-integrity, operations

Observed divergence, suspected: a restore writes the rows before the mode, so with a declared index each parallel triple is recorded as a single edge until the next rebuild ([stage-A notes, F5](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [Restoring a multigraph archive into an indexed namespace loses its parallel edges' multiplicity](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-007)

### structure.degree

- Sources: [CONTEXT.md, Degree (decided in the 2026-10-12 architecture review)](../../../CONTEXT.md#L103-L107), [ADR-0010](../../../docs/adr/0010-degree-is-counted-never-stored.md)
- Children: [the degree cache](../architecture/adjacency-and-derived-data.g5.md#structure.degree.cache)
- human-verified
- architecture-decision, data-integrity
