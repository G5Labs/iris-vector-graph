# FHIR graphs and mapped SQL tables

IVG can project an InterSystems IRIS FHIR repository into a graph and keep that graph in step with the repository. A deprecated HTTP route also records single FHIR events. Existing SQL tables can also be read as graph nodes and relationships without copying them; that feature lives here because the code groups it with the FHIR bridges.

## Definitions

- **FHIR repository**: the resource store of an IRIS for Health FHIR server in the same namespace.
- **FHIR key**: a resource's type and ID, such as `Patient/p1`.
- **FHIR graph**: the named graph a registered repository is projected into.
- **Watermark**: the last repository change a FHIR graph has applied, one per change feed (new resources, and later versions or deletes).
- **Resync**: rebuilding one FHIR key's node, labels and outgoing edges from the repository's current state.
- **Rebuild**: reconciling a whole FHIR graph with the repository.
- **Compartment edge**: a derived edge from a resource to each patient whose compartment it belongs to.
- **Interpretation version**: the version of the derivation rules a FHIR graph was last processed with.
- **FHIR event**: one call to the deprecated `/fhir-event` route that records a resource and its patient.
- **Mapped label**: a node label whose nodes are the rows of an existing SQL table, read in place.

## The FHIR graph

<a id="fhir.graph"></a>
[D · fhir.graph]

A registered FHIR repository is projected into its own named graph, never the default graph. The graph holds one node per live resource, keyed by its FHIR key and labelled with its resource type, and one edge per indexed reference to a live local resource. Codes and most properties stay in the repository and are read live.

<a id="fhir.graph.install"></a>
[D · fhir.graph.install]

FHIR support is not a separate install. Its classes compile on every IRIS edition and stay idle where no FHIR server exists. Its tables are created by the first registration, and registration is refused where the namespace has no repository.

<a id="fhir.graph.lifecycle"></a>
[I · fhir.graph.lifecycle]

An operator registers a repository once, which names its graph, builds the graph with a rebuild, and keeps it current with syncs run on demand or by a schedule.

- Scheduling creates or updates one Task Manager task per graph; its interval rounds up to whole minutes.
- Scheduling and unscheduling act only on the graph's own task, and refuse, changing nothing, when the stored task ID names another task.
- Status reports the graph's counts, pending changes, last sync and rebuild, last error and task.

## Keeping the graph in step

<a id="fhir.graph.lifecycle.tasks"></a>
[D · fhir.graph.lifecycle.tasks]

Scheduling derives ownership from the actual saved task before changing it.

- It reuses an existing object only when its class is `Graph.KG.FHIRGraphSyncTask`, its namespace is current, and its raw Settings identify this graph; the last exact `GraphId` key wins, including an odd last key's empty value.
- An existing foreign object refuses without task or registry changes; a stale ID naming no object is replaced on schedule or cleared on unschedule. A removed task's old ID is returned even after the registry ID is cleared.
- The public interval is an integer of at least sixty seconds, or None to retain the registered interval; an effective interval below sixty refuses. Task minutes round upward while registered seconds remain exact.
- Task save/delete precedes registry update; a failure in the later update can leave them disagreeing, so a status ID alone proves neither a live task nor ownership. A new ID equal to an unused stale registry ID can accidentally restore their agreement even on that error.
- The saved canonical GraphId determines the eligible task invocation target; busy succeeds as an invocation while error, thrown call or invalid reply fails. Scheduling proves neither background activation nor completed sync.


<a id="fhir.sync"></a>
[I · fhir.sync]

A sync applies the repository's changes since the graph's watermarks, in batches of keys. Each batch's graph changes and its watermark advance commit together, so a failure rolls back both and the next sync repeats the batch.

<a id="fhir.sync.idempotent"></a>
[I · fhir.sync.idempotent]

Resyncing a key reads only the repository's current state, so repeating it gives the same graph. Any sequence of syncs ends with the same graph a rebuild would build.

- For a live key, resync makes sure the node and its label exist and recomputes its outgoing edges. It also turns unresolved references that point to the key into edges.
- For a deleted or absent key, resync removes the key's edges, labels, properties, vectors and node, and records its incoming references as unresolved.

<a id="fhir.sync.exclusive"></a>
[I · fhir.sync.exclusive]

Only one sync, rebuild or re-interpretation runs per FHIR graph at a time. A second caller is told the graph is busy and changes nothing.

<a id="fhir.sync.behind"></a>
[I · fhir.sync.behind]

When the repository is behind the graph's watermarks, for example after a reset or a restore from an older backup, a sync rebuilds the graph instead and says so.

<a id="fhir.sync.other_writers"></a>
[Q · fhir.sync.other_writers]

What should happen when other writers touch a FHIR graph? There is no provisional answer. Plausible answers: the FHIR graph belongs to the sync alone and other writes are refused, or other writes are allowed and must take the sync's lock.

- Today erasing a FHIR graph, or writing to it from Python, does not wait for a running sync.
- An edge a user adds from a FHIR key is deleted at that key's next resync.

<a id="fhir.rebuild"></a>
[I · fhir.rebuild]

A rebuild reconciles the whole graph with the repository by comparing, not by erasing, so vectors on surviving nodes are kept. It then resets both watermarks to the highest values read before the scan. A rebuild is not one transaction; if it fails partway, the next sync replays the changes.

<a id="fhir.erase"></a>
[I · fhir.erase]

Erasing a FHIR graph keeps its registration but resets its watermarks and interpretation version, so the next sync rebuilds its content from scratch.

## Interpretation

<a id="fhir.interpretation"></a>
[D · fhir.interpretation]

A sync adds compartment edges from each resource to its patients, derived from the reference edges already synced and the server's patient-compartment rules.

- The source resource owns its compartment edges: they are re-derived in the same transaction as its reference edges and deleted with it.
- Erasure, snapshot restore and graph verification (`verify_graph`) treat compartment edges as ordinary edges.
- Personalized PageRank skips them by default, and status counts them apart from reference edges.

<a id="fhir.interpretation.version"></a>
[I · fhir.interpretation.version]

A graph whose interpretation version is missing or older than the current rules is fully re-derived once, on its next sync or on request. An interrupted re-derivation leaves the old version, so the next sync starts it again.

<a id="fhir.ledger"></a>
[Q · fhir.ledger]

Must FHIR sync writes be recorded in, or refused by, the revision ledger? There is no provisional answer.

- Today they are neither recorded nor refused in strict mode, so verify would report them as unrecorded.
- Plausible answers: FHIR graphs are exempt, like the bulk loader; verify adopts them; or the sync commits through the ledger.

## Mapped SQL tables

<a id="fhir.sql_mapping"></a>
[D · fhir.sql_mapping]

An existing SQL table can be mapped to a node label as a read-only view: Cypher reads the table's rows as that label's nodes at query time, and nothing is copied into IVG's tables. Mapping, remapping and removing a mapping are writes to IVG's configuration tables, which a snapshot carries.

- A mapped label is read from its table only: Cypher no longer reads IVG's own nodes that carry the same label.
- Removing a mapping also removes every relationship mapping from or to its label, and leaves the SQL table untouched.

<a id="fhir.sql_mapping.relationships"></a>
[D · fhir.sql_mapping.relationships]

A relationship between two mapped labels can be mapped to SQL, either as a foreign key on the source table or as a join table. Both labels must already be mapped.

<a id="fhir.sql_mapping.adjacency"></a>
[D · fhir.sql_mapping.adjacency]

Mapped nodes and relationships are not in the adjacency index. Pattern and property queries in Cypher see them, but breadth-first walks, variable-length paths, centrality and the other graph algorithms do not. To use them in algorithms, write them as real nodes and edges instead.

<a id="fhir.sql_mapping.embeddings"></a>
[I · fhir.sql_mapping.embeddings]

A mapped table's text columns can be embedded as vectors for the nodes `<label>:<id>` of one named or default graph. A row whose node does not exist in that graph is counted and skipped, not embedded.

<a id="fhir.sql_mapping.graph_scope"></a>
[Q · fhir.sql_mapping.graph_scope]

Which graph do mapped rows belong to? There is no provisional answer.

- Their tables carry no graph, so a query under `USE GRAPH` or across every graph reads the same rows.
- Plausible answers: mapped rows belong to every graph, or a mapping is made per graph.

## FHIR events (deprecated)

<a id="fhir.event"></a>
[D · fhir.event]

The `/fhir-event` route is deprecated and is removed in 5.0, because a registered FHIR graph reads the repository itself. Until then it records the resource as a node and adds a timestamped edge from its patient, optionally in a named graph.

<a id="fhir.event.access"></a>
[I · fhir.event.access]

The FHIR event route needs the API key when one is set. Read-only mode refuses it unless `IVG_ALLOW_FHIR_WRITES=true`.

<a id="fhir.event.retry"></a>
[Q · fhir.event.retry]

Must a repeated FHIR event leave the graph unchanged? There is no provisional answer. Plausible answers: derive the time from the event so retries are harmless, or accept this until the route is removed in 5.0.

- Today an event without a usable date gets the current time, so each retry adds another timestamped edge.
- An updated resource keeps its first codes, and nothing removes a deleted resource.

## Metadata

### fhir.graph

- Sources: [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md); [FHIRGraph.cls header](../../../iris_src/src/Graph/KG/FHIRGraph.cls); [_engine/fhir_graph.py](../../../iris_vector_graph/_engine/fhir_graph.py)
- Children: [install](#fhir.graph.install), [lifecycle](#fhir.graph.lifecycle)
- agent
- user-facing-behavior, architecture-decision
- test-coverage

The FHIR graph comes from specs 231 to 233, whose directories are not in the tree. The graph name has the form `fhir:<namespace>:<package>`. Live coverage needs an IRIS for Health namespace (`tests/e2e/test_231_fhir_graph_sync_e2e.py`, `tests/e2e/test_262_alt_schema_fhir.py`).

### fhir.graph.install

- Sources: [Spec 235 Clarifications, session 2026-09-27](../../../specs/235-fhir-graph-interpretation/spec.md); [_engine/fhir_graph.py](../../../iris_vector_graph/_engine/fhir_graph.py)
- Expands: [FHIR graph](#fhir.graph)
- agent
- operations
- test-coverage

Live coverage: `tests/e2e/test_235_lazy_fhir_tables_e2e.py`. Spec 235's status line still says "Draft", although it shipped in 4.1.0.

### fhir.graph.lifecycle
- Formal: [task ownership and lifecycle projection](../../Verus_verification/models/fhir_tasks/fhir_tasks.rs), [source roles and provider limits](../../Verus_verification/models/fhir_tasks/NOTES.md).

- Sources: [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md); [_engine/fhir_graph.py](../../../iris_vector_graph/_engine/fhir_graph.py); [ADMIN_GUIDE (restored task IDs)](../../../docs/ADMIN_GUIDE.md)
- Expands: [FHIR graph](#fhir.graph)
- agent
- operations

The task-ID refusal came in 4.7.0. No operation that unregisters a repository was found.

### fhir.graph.lifecycle.tasks
- agent
- user-facing-behavior
- data-integrity
- Expands: [FHIR lifecycle](#fhir.graph.lifecycle).
- Formal: [raw registry/task state to reader](../../Verus_verification/models/fhir_tasks/fhir_tasks.rs), [qualified roles](../../Verus_verification/models/fhir_tasks/NOTES.md).

Evidence: [frozen pairs](../../uplift/consolidated/iteration-8/fhir-PAIRS.md), [native Task Manager and registry points](../../uplift/consolidated/iteration-8/fhir-native.json). Full Status needs real FHIR metadata/feed tables; its successful point projection remains conditional. Native wrong-namespace setup refused before the guard, and save/delete/SQL fault ordering is source/adapter evidence. Fault tags are pre-effect at the named operation, canonical loader and allocation are provider contracts, and unassigned task fields/background timing are outside the new proof. Existing F-C1501 and its intended remedy remain; no owner decision or new defect is inferred.

### fhir.sync

- Sources: [FHIR_GRAPH.md: keeping the graph in step](../../../docs/FHIR_GRAPH.md); [FHIRGraph.cls SyncOnce, RunBatch](../../../iris_src/src/Graph/KG/FHIRGraph.cls)
- Children: [idempotent](#fhir.sync.idempotent), [exclusive](#fhir.sync.exclusive), [behind](#fhir.sync.behind), [other writers](#fhir.sync.other_writers)
- agent
- data-integrity
- test-coverage

Live coverage: `tests/e2e/test_231_fhir_graph_sync_e2e.py::test_crash_before_commit_leaves_nothing`. Observed: sync writes the label index directly in a few places without moving the graph-version token; the reference edges go through the adjacency index's own writer.

Findings: [Write FHIR graph labels through the adjacency writer that owns the label index](../../Verus_verification/design_simplification.md#simp-plt-003)

### fhir.sync.idempotent

- Sources: [FHIRGraph.cls header (RESYNC)](../../../iris_src/src/Graph/KG/FHIRGraph.cls); [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md)
- Expands: [Sync](#fhir.sync)
- agent
- data-integrity
- test-coverage

Live coverage: the sync-equals-rebuild comparison in `tests/e2e/test_231_fhir_graph_sync_e2e.py`.

### fhir.sync.exclusive

- Sources: [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md); [FHIRGraph.cls SyncOnce](../../../iris_src/src/Graph/KG/FHIRGraph.cls)
- Expands: [Sync](#fhir.sync)
- agent
- data-integrity
- test-coverage

Live coverage: the busy case in `tests/e2e/test_231_fhir_graph_sync_e2e.py`.

### fhir.sync.behind

- Sources: [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md)
- Expands: [Sync](#fhir.sync)
- agent
- operations

### fhir.sync.other_writers

- Sources: [FHIRGraph.cls ResyncKey](../../../iris_src/src/Graph/KG/FHIRGraph.cls); [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls); [Stage A notes, FHIR section](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Sync](#fhir.sync)
- agent
- uncertain
- data-integrity

Findings: [What should happen when other writers, an erase included, touch a FHIR graph during a sync?](../../Verus_verification/open_questions.md#q-plt-017)

### fhir.rebuild

- Sources: [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md); [FHIRGraph.cls Rebuild](../../../iris_src/src/Graph/KG/FHIRGraph.cls)
- agent
- data-integrity, operations

### fhir.erase

- Sources: [FHIR_GRAPH.md: Upgrading a graph built by older rules](../../../docs/FHIR_GRAPH.md); [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls)
- agent
- data-integrity
- test-coverage

Live coverage: the erase case in `tests/e2e/test_231_fhir_graph_sync_e2e.py`.

### fhir.interpretation

- Sources: [Spec 235 Clarifications, session 2026-09-26](../../../specs/235-fhir-graph-interpretation/spec.md); [FHIR_GRAPH.md interpretation contract](../../../docs/FHIR_GRAPH.md)
- Children: [version](#fhir.interpretation.version)
- agent
- user-facing-behavior

The spec's clarification answers carry no human attribution.

### fhir.interpretation.version

- Sources: [Spec 235 Clarifications (upgrading graphs synced under 4.1.0)](../../../specs/235-fhir-graph-interpretation/spec.md); [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md)
- Expands: [Interpretation](#fhir.interpretation)
- agent
- data-integrity

### fhir.ledger

- Sources: [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [access.ledger_strict.undecided](../concepts/access.g5.md#access.ledger_strict.undecided); [Stage A notes F-B8](../../uplift/ivg-verus-initial/intent/platform.md)
- agent
- uncertain
- data-integrity

No source mentions FHIR together with the ledger. No test runs a FHIR sync with the ledger enabled.

Findings: [Which write paths must strict mode govern beyond the engine's methods, and how is each classified?](../../Verus_verification/open_questions.md#q-plt-008)

### fhir.sql_mapping

- Sources: [API_REFERENCE: SQL table mappings](../../../docs/API_REFERENCE.md); [_engine/fhir.py map_sql_table](../../../iris_vector_graph/_engine/fhir.py); [cypher/translator.py](../../../iris_vector_graph/cypher/translator.py); [install.snapshot.scope](../concepts/install.g5.md#install.snapshot.scope)
- Children: [relationships](#fhir.sql_mapping.relationships), [adjacency](#fhir.sql_mapping.adjacency), [embeddings](#fhir.sql_mapping.embeddings), [graph scope](#fhir.sql_mapping.graph_scope)
- agent
- user-facing-behavior, architecture-decision

The code defines these calls in the same module as the FHIR bridges (`FhirMixin`), so they are kept on this page rather than on the install page. Since 4.7.0 they join the caller's transaction. The rule that a mapped label hides IVG's own nodes with that label is from the translator code only. No spec for the feature was found.

### fhir.sql_mapping.relationships

- Sources: [_engine/fhir.py map_sql_relationship](../../../iris_vector_graph/_engine/fhir.py); [API_REFERENCE](../../../docs/API_REFERENCE.md)
- Expands: [Mapped SQL tables](#fhir.sql_mapping)
- agent
- user-facing-behavior

### fhir.sql_mapping.adjacency

- Sources: [_engine/fhir.py map_sql_table (adjacency contract)](../../../iris_vector_graph/_engine/fhir.py)
- Expands: [Mapped SQL tables](#fhir.sql_mapping)
- agent
- architecture-decision

Stated in the method's documentation. Consistency checks of the adjacency index cannot see this gap, because nothing was written to the edge table.

### fhir.sql_mapping.embeddings

- Sources: [_engine/fhir.py attach_embeddings_to_table](../../../iris_vector_graph/_engine/fhir.py); [API_REFERENCE](../../../docs/API_REFERENCE.md)
- Expands: [Mapped SQL tables](#fhir.sql_mapping)
- agent
- user-facing-behavior

Its documentation adds that a graph ID avoids collisions and is not an authorization boundary (see [access.graph_id](../concepts/access.g5.md#access.graph_id)).

### fhir.sql_mapping.graph_scope

- Sources: [cypher/translator.py](../../../iris_vector_graph/cypher/translator.py); [_engine/fhir.py](../../../iris_vector_graph/_engine/fhir.py)
- Expands: [Mapped SQL tables](#fhir.sql_mapping)
- agent
- uncertain
- data-integrity


Findings: [Which graph do rows of a mapped FHIR SQL table belong to?](../../Verus_verification/open_questions.md#q-plt-018)
### fhir.event

- Sources: [FHIR_GRAPH.md: Deprecated in 4.1.0, removed in 5.0](../../../docs/FHIR_GRAPH.md); [api/routers/fhir_event.py](../../../api/routers/fhir_event.py)
- Children: [access](#fhir.event.access), [retry](#fhir.event.retry)
- agent
- user-facing-behavior

The route comes from spec 195, whose directory is not in the tree; commit `22f3e509` remains. Each event's steps commit separately, so a failure after the node is written leaves the node.

### fhir.event.access

- Sources: [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api_auth.py](../../../iris_vector_graph/api_auth.py)
- Expands: [FHIR events](#fhir.event)
- agent
- security

### fhir.event.retry

- Sources: [api/routers/fhir_event.py](../../../api/routers/fhir_event.py); [Stage A notes F-B9](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [FHIR events](#fhir.event)
- agent
- uncertain
- data-integrity

The live test `tests/integration/test_fhir_event_sidecar.py` checks only that a repeated event leaves at least one edge.

Findings: [Must a repeated FHIR event leave the graph unchanged?](../../Verus_verification/open_questions.md#q-plt-016)
