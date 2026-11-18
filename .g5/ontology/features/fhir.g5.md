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

- Working assumption: the FHIR graph is an external writer of a rebuildable projection at the pin. verify() keeps reporting its rows (never silently 'equal'); strict mode is not a guarantee for FHIR namespaces until FHIR writes are either refused under strict or recorded.

<a id="fhir.graph.install"></a>
[D · fhir.graph.install]

FHIR support is not a separate install. Its classes compile on every IRIS edition and stay idle where no FHIR server exists. Its tables are created by the first registration, and registration is refused where the namespace has no repository.

<a id="fhir.graph.lifecycle"></a>
[I · fhir.graph.lifecycle]

An operator registers a repository once, which names its graph, builds the graph with a rebuild, and keeps it current with syncs run on demand or by a schedule.

- Scheduling creates or updates one Task Manager task per graph; its interval rounds up to whole minutes.
- Scheduling and unscheduling act only on the graph's own task, and refuse, changing nothing, when the stored task ID names another task.
- Status reports the graph's counts, pending changes, last sync and rebuild, last error and task.

## Synchronize or rebuild a FHIR graph

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

- Working assumption: Preserve the documented single-sync restriction and keep competing non-sync writers unestablished; choose serialization or conflict detection explicitly.
- Working assumption: erase of a FHIR graph must be serialized with an active sync (take ^IVG.FHIRGraph(graph) and answer busy, or have RunBatch abort when the watermark moved backwards); until then the quiet-sync premise must be explicit for erase.
- Working assumption: Failure without advancing the watermark is the documented contract (not a choice to revisit silently). Surface the offending key (already in last_error) and treat the missing recovery procedure (repair/delete the resource, or json_links=[]) as a documentation gap; do not assume silent skips.

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

<a id="fhir.rebuild"></a>
[I · fhir.rebuild]

A rebuild reconciles the whole graph with the repository by comparing, not by erasing, so vectors on surviving nodes are kept. It then resets both watermarks to the highest values read before the scan. A rebuild is not one transaction; if it fails partway, the next sync replays the changes.

<a id="fhir.erase"></a>
[I · fhir.erase]

Erasing a FHIR graph keeps its registration but resets its watermarks and interpretation version, so the next sync rebuilds its content from scratch.

- Working assumption: Separate transient clear from decommissioning. Ordinary erase keeps registration and task (supported). For durable tenant removal require, as a stated premise, unschedule before erase and no manual sync afterwards, and verify the graph stays empty before redaction; at the pin there is no single-graph deregistration, so 'deregister' is a new command, not an available step.

## How FHIR resources become graph data

<a id="fhir.interpretation"></a>
[D · fhir.interpretation]

A sync adds compartment edges from each resource to its patients, derived from the reference edges already synced and the server's patient-compartment rules.

- The source resource owns its compartment edges: they are re-derived in the same transaction as its reference edges and deleted with it.
- Erasure, snapshot restore and graph verification (`verify_graph`) treat compartment edges as ordinary edges.
- Personalized PageRank skips them by default, and status counts them apart from reference edges.

<a id="fhir.interpretation.version"></a>
[I · fhir.interpretation.version]

A graph whose interpretation version is missing or older than the current rules is fully re-derived once, on its next sync or on request. An interrupted re-derivation leaves the old version, so the next sync starts it again.

## Mapped SQL tables

<a id="fhir.sql_mapping"></a>
[D · fhir.sql_mapping]

An existing SQL table can be mapped to a node label as a read-only view: Cypher reads the table's rows as that label's nodes at query time, and nothing is copied into IVG's tables. Mapping, remapping and removing a mapping are writes to IVG's configuration tables, which a snapshot carries.

- A mapped label is read from its table only: Cypher no longer reads IVG's own nodes that carry the same label.
- Removing a mapping also removes every relationship mapping from or to its label, and leaves the SQL table untouched.
- Each engine reads mappings from its own cache, so an engine already running keeps its old reading of a label until it calls `reload_table_mappings()` ([open question](../../Verus_verification/open_questions.md#fhir.sql_mapping.cache)).
- A table named without a schema is refused even when IRIS has it in `SQLUser` ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-110)).

- Working assumption: Treat mapped SQL labels as namespace-global today; assigning every row to a graph needs mapping metadata and migration policy.

<a id="fhir.sql_mapping.relationships"></a>
[D · fhir.sql_mapping.relationships]

A relationship between two mapped labels can be mapped to SQL, either through a key column or as a join table. Both labels must already be mapped.
- The key column `target_fk` is read on the target table and holds the source row's id, although the method's documentation puts it on the source table ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-108)).
- A pattern from a mapped node through a relationship that is not mapped fails with an SQL error ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-109)).

<a id="fhir.sql_mapping.adjacency"></a>
[D · fhir.sql_mapping.adjacency]

Mapped nodes and relationships are not in the adjacency index. Pattern and property queries in Cypher see them, but breadth-first walks, variable-length paths, centrality and the other graph algorithms do not. To use them in algorithms, write them as real nodes and edges instead.

<a id="fhir.sql_mapping.embeddings"></a>
[I · fhir.sql_mapping.embeddings]

A mapped table's text columns can be embedded as vectors for the nodes `<label>:<id>` of one named or default graph. A row whose node does not exist in that graph is counted and skipped, not embedded.

## FHIR events (deprecated)

<a id="fhir.event"></a>
[D · fhir.event]

The `/fhir-event` route is deprecated and is removed in 5.0, because a registered FHIR graph reads the repository itself. Until then it records the resource as a node and adds a timestamped edge from its patient, optionally in a named graph.

- Working assumption: Prefer idempotent repeated FHIR events, while preserving current event behavior as observation; event identity and replay retention need owner choice.

<a id="fhir.event.access"></a>
[I · fhir.event.access]

The FHIR event route needs the API key when one is set. Read-only mode refuses it unless `IVG_ALLOW_FHIR_WRITES=true`.

## Earlier links

These links take you to the current sections and statements.

<a id="keeping-the-graph-in-step"></a>

[Synchronize or rebuild a FHIR graph](#synchronize-or-rebuild-a-fhir-graph)

<a id="interpretation"></a>

[How FHIR resources become graph data](#how-fhir-resources-become-graph-data)

## Metadata

### fhir.graph

- uncertain
- Sources: [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md); [FHIRGraph.cls header](../../../iris_src/src/Graph/KG/FHIRGraph.cls); [_engine/fhir_graph.py](../../../iris_vector_graph/_engine/fhir_graph.py)
- Children: [install](#fhir.graph.install), [lifecycle](#fhir.graph.lifecycle)
- agent
- user-facing-behavior, architecture-decision
- test-coverage

The FHIR graph comes from specs 231 to 233, whose directories are not in the tree. The graph name has the form `fhir:<namespace>:<package>`. Live coverage needs an IRIS for Health namespace (`tests/e2e/test_231_fhir_graph_sync_e2e.py`, `tests/e2e/test_262_alt_schema_fhir.py`).

Open questions: [Should a FHIR sync be governed by the ledger?](../../Verus_verification/open_questions.md#HD-1501)

Assumption review evidence: Changed from decisions.md: no. Sources confirm the working answer; added that ledger-api.md's exhaustive list is silent on FHIR (not an explicit exemption) and that verify() reads every graph.

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

State machines: [fhir tasks](../../Verus_verification/models/fhir_tasks/manifest.json)

### fhir.graph.lifecycle.tasks

- design-verified
- agent
- user-facing-behavior
- data-integrity
- Expands: [FHIR lifecycle](#fhir.graph.lifecycle).
- Formal: [raw registry/task state to reader](../../Verus_verification/models/fhir_tasks/fhir_tasks.rs), [qualified roles](../../Verus_verification/models/fhir_tasks/NOTES.md).

Evidence: [frozen pairs](../../uplift/consolidated/iteration-8/fhir-PAIRS.md), [native Task Manager and registry points](../../uplift/consolidated/iteration-8/fhir-native.json). Full Status needs real FHIR metadata/feed tables; its successful point projection remains conditional. Native wrong-namespace setup refused before the guard, and save/delete/SQL fault ordering is source/adapter evidence. Fault tags are pre-effect at the named operation, canonical loader and allocation are provider contracts, and unassigned task fields/background timing are outside the new proof. Existing F-C1501 and its intended remedy remain; no owner decision or new defect is inferred.

State machines: [fhir tasks](../../Verus_verification/models/fhir_tasks/manifest.json)

### fhir.sync

- uncertain
- Sources: [FHIR_GRAPH.md: keeping the graph in step](../../../docs/FHIR_GRAPH.md); [FHIRGraph.cls SyncOnce, RunBatch](../../../iris_src/src/Graph/KG/FHIRGraph.cls)
- Children: [idempotent](#fhir.sync.idempotent), [exclusive](#fhir.sync.exclusive), [behind](#fhir.sync.behind), [What should happen when other writers, an erase included, touch a FHIR graph during a sync?](../../Verus_verification/open_questions.md#q-plt-017)
- agent
- data-integrity
- test-coverage

Live coverage: `tests/e2e/test_231_fhir_graph_sync_e2e.py::test_crash_before_commit_leaves_nothing`. Observed: sync writes the label index directly in a few places without moving the graph-version token; the reference edges go through the adjacency index's own writer.

Findings: [Write FHIR graph labels through the adjacency writer that owns the label index](../../Verus_verification/design_simplification.md#simp-plt-003)

Open questions: [What happens when an erase runs during a FHIR sync?](../../Verus_verification/open_questions.md#HD-1503), [Should one unreadable FHIR resource block its graph's sync?](../../Verus_verification/open_questions.md#HD-1504), [What should happen when other writers, an erase included, touch a FHIR graph during a sync?](../../Verus_verification/open_questions.md#q-plt-017)

Assumption review evidence: Changed from decisions.md: no. Confirmed by source; added the documented convergence claim as the outcome anchor and the absolute-watermark write as the mechanism of the failure. Changed from decisions.md: yes. Status raised from assumption to supported for the failure semantics: FHIR_GRAPH.md:196-199 (maintainer commit 59286731) explicitly states that a walk limit fails the batch, and :255-257 that a failed batch repeats. Added that a rebuild fails too, and the json_links=[] recovery path.

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

### fhir.rebuild

- Sources: [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md); [FHIRGraph.cls Rebuild](../../../iris_src/src/Graph/KG/FHIRGraph.cls)
- agent
- data-integrity, operations

### fhir.erase

- uncertain
- Sources: [FHIR_GRAPH.md: Upgrading a graph built by older rules](../../../docs/FHIR_GRAPH.md); [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls)
- agent
- data-integrity
- test-coverage

Live coverage: the erase case in `tests/e2e/test_231_fhir_graph_sync_e2e.py`.

Open questions: [Should erasing a FHIR graph stop its sync task?](../../Verus_verification/open_questions.md#HD-1502)

Assumption review evidence: Changed from decisions.md: yes. Status raised to supported for the transient-clear half (ADR-0015:29 and the Eraser comment settle it). Refined the durable-removal half: decisions.md offered 'paused or deregistered', but no single-graph deregistration exists at the pin and an unscheduled graph still accepts manual syncs.

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

### fhir.sql_mapping

- uncertain
- Sources: [API_REFERENCE: SQL table mappings](../../../docs/API_REFERENCE.md); [_engine/fhir.py map_sql_table](../../../iris_vector_graph/_engine/fhir.py); [cypher/translator.py](../../../iris_vector_graph/cypher/translator.py); [install.snapshot.scope](../operations/snapshots-and-bulk-load.g5.md#install.snapshot.scope)
- Children: [relationships](#fhir.sql_mapping.relationships), [adjacency](#fhir.sql_mapping.adjacency), [embeddings](#fhir.sql_mapping.embeddings), [Which graph do rows of a mapped FHIR SQL table belong to?](../../Verus_verification/open_questions.md#q-plt-018)
- agent
- user-facing-behavior, architecture-decision

The code defines these calls in the same module as the FHIR bridges (`FhirMixin`), so they are kept on this page rather than on the install page. Since 4.7.0 they join the caller's transaction. The rule that a mapped label hides IVG's own nodes with that label is from the translator code only. No spec for the feature was found.

Observed (iteration 40, [W46](../../uplift/consolidated/iteration-40/sqlmap-PAIRS.md)): mapping, hiding IVG's own nodes, removal, relationship-mapping removal, the adjacency limit, `USE GRAPH` (the same rows) and typed `WHERE` agree with these statements.

Verus: active: [`sql_mapping.rs`](../../Verus_verification/models/sql_mapping/NOTES.md) `theorem_writer_reads_current`, `theorem_stale_engine_reads_own_nodes`, `theorem_fk_side_differs`, `theorem_mapped_with_ivg_relationship_errors`, `theorem_unqualified_name_refused`.

Findings: [map_sql_relationship reads target_fk on the target table](../../Verus_verification/bugs_issues.md#bug-cyp-108); [A pattern from a mapped label through an IVG relationship fails](../../Verus_verification/bugs_issues.md#bug-cyp-109); [map_sql_table refuses a table named without a schema](../../Verus_verification/bugs_issues.md#bug-cyp-110)

Open questions: [Which graph do rows of a mapped FHIR SQL table belong to?](../../Verus_verification/open_questions.md#q-plt-018), [Should a table mapping made by one engine reach engines that are already running?](../../Verus_verification/open_questions.md#fhir.sql_mapping.cache)

### fhir.sql_mapping.relationships

- Sources: [_engine/fhir.py map_sql_relationship](../../../iris_vector_graph/_engine/fhir.py); [API_REFERENCE](../../../docs/API_REFERENCE.md)
- Expands: [Mapped SQL tables](#fhir.sql_mapping)
- agent
- user-facing-behavior

Findings: [map_sql_relationship reads target_fk on the target table](../../Verus_verification/bugs_issues.md#bug-cyp-108); [A pattern from a mapped label through an IVG relationship fails](../../Verus_verification/bugs_issues.md#bug-cyp-109)

### fhir.sql_mapping.adjacency

- Sources: [_engine/fhir.py map_sql_table (adjacency contract)](../../../iris_vector_graph/_engine/fhir.py)
- Expands: [Mapped SQL tables](#fhir.sql_mapping)
- agent
- architecture-decision

Stated in the method's documentation. Consistency checks of the adjacency index cannot see this gap, because nothing was written to the edge table.

Findings: [A pattern from a mapped label through an IVG relationship fails](../../Verus_verification/bugs_issues.md#bug-cyp-109)

### fhir.sql_mapping.embeddings

- Sources: [_engine/fhir.py attach_embeddings_to_table](../../../iris_vector_graph/_engine/fhir.py); [API_REFERENCE](../../../docs/API_REFERENCE.md)
- Expands: [Mapped SQL tables](#fhir.sql_mapping)
- agent
- user-facing-behavior

Its documentation adds that a graph ID avoids collisions and is not an authorization boundary (see [access.graph_id](../concepts/access.g5.md#access.graph_id)).

### fhir.event

- uncertain
- Sources: [FHIR_GRAPH.md: Deprecated in 4.1.0, removed in 5.0](../../../docs/FHIR_GRAPH.md); [api/routers/fhir_event.py](../../../api/routers/fhir_event.py)
- Children: [access](#fhir.event.access), [Must a repeated FHIR event leave the graph unchanged?](../../Verus_verification/open_questions.md#q-plt-016)
- agent
- user-facing-behavior

The route comes from spec 195, whose directory is not in the tree; commit `22f3e509` remains. Each event's steps commit separately, so a failure after the node is written leaves the node.

Open questions: [Must a repeated FHIR event leave the graph unchanged?](../../Verus_verification/open_questions.md#q-plt-016)

### fhir.event.access

- Sources: [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api_auth.py](../../../iris_vector_graph/api_auth.py)
- Expands: [FHIR events](#fhir.event)
- agent
- security
