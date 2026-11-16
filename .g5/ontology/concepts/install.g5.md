# Install, schema, upgrades and data movement

How IVG is set up in an IRIS namespace, how the namespace keeps one IVG Schema, how older installs are upgraded, and how graph data is moved in bulk (snapshots and the bulk loader).

## Definitions

- **Namespace**: the IRIS namespace IVG is installed in. Everything IVG keeps outside SQL (adjacency index, ledger, settings) belongs to it.
- **IVG Schema**: the one SQL schema in a namespace that holds every table, function, procedure and view IVG creates. It is `Graph_KG` unless another name is chosen.
- **Schema record**: the namespace's note of which IVG Schema it uses, kept beside IVG's deploy record.
- **Setup**: `initialize_schema()`, which creates IVG's SQL objects, compiles its ObjectScript classes and writes the schema record.
- **Dry run**: a call that reports what setup, an upgrade step or legacy removal would do, and writes nothing.
- **Legacy object**: a function, view or class an IVG release before 4.6.0 created in `SQLUser`, the `User` package, or with no package, plus classes IVG stopped shipping.
- **Legacy manifest**: the fixed list of legacy objects, taken from the released versions.

## The namespace and its IVG Schema

<a id="install.namespace"></a>
[D · install.namespace]

The namespace, not the schema, is IVG's isolation unit: one namespace holds one IVG install. Two tenants that must not share an adjacency index or a ledger need two namespaces.


<a id="install.schema"></a>
[D · install.schema]

Every SQL object IVG creates lives in the namespace's one IVG Schema, and IVG creates nothing in `SQLUser` or the `User` package. The ObjectScript classes IVG deploys use the same schema.


<a id="install.schema.name"></a>
[I · install.schema.name]

The engine's IVG Schema is the `schema_prefix` argument, else the `IVG_SCHEMA_PREFIX` variable, else `Graph_KG`.

- IVG never reads `IRIS_SCHEMA_PREFIX`, which another library in the same process may use.
- A name must start with a letter and contain only letters, digits and underscores.
- `SQLUser`, names starting with `%`, and names whose class package falls inside IVG's own code packages are refused.
- Setup refuses a name whose class package already holds classes IVG did not create, before any DDL.
- An invalid name raises an error naming the rule before any database call.
- Names that differ only in letter case are the same schema.


<a id="install.schema.record"></a>
[I · install.schema.record]

The first completed setup in a namespace records its IVG Schema, and the record does not change after that. Renaming a recorded schema is not supported. The documented manual route is to choose one schema, then move or drop the other schema's tables.


<a id="install.schema.refusal"></a>
[I · install.schema.refusal]

An engine or a class deploy that asks for a schema other than the recorded one is refused with an error that names both. The refusal comes before any other read or write, and nothing in the namespace changes.

- Every public engine call raises the refusal, so no catch-all can turn it into an empty answer.
- Setup, status and legacy removal still run on a refusing namespace, because they are how an operator inspects or fixes it.
- A login that cannot read the record gets a warning, and the check is skipped for that engine.

- Working assumption: Supported deployments can read the record (premise: the ADMIN_GUIDE role table grants %Native_GlobalAccess:U). Under that premise a mismatch is refused. The documented fail-open path is a separate 'unchecked' outcome that admits a mismatched engine. It is outside the binding guarantee and should be modelled that way, not treated as an accepted engine.


<a id="install.schema.not_ready"></a>
[I · install.schema.not_ready]

An engine on a namespace with no schema record, or without the current release's SQL objects, raises one error on first access and runs nothing else. It never falls back to legacy objects. The error says which case applies and names setup and its dry run as the way forward:

- set up by an earlier release and not yet upgraded;
- never set up for IVG;
- a setup that stopped before finishing.


<a id="install.schema.existing"></a>
[I · install.schema.existing]

Setup on a namespace without a record decides what to record from where IVG's tables already are:

- No IVG tables: record the engine's schema.
- Tables in the engine's schema only: record that schema.
- Tables in one other schema only: refuse, name that schema, and record nothing, even when the engine's schema was named explicitly.
- Tables in several schemas and no name given: refuse, list each schema with its row counts, and record nothing.
- Tables in several schemas and a name given: record the named schema and report the others, untouched.


<a id="install.schema.concurrency"></a>
[I · install.schema.concurrency]

A namespace ends with one recorded IVG Schema even when two setups with different schemas run at the same time. Exactly one of them records its schema; the other is refused, with its engine still refused, before it writes rows or globals for its own schema.

- Working assumption: Prefer refusing a conflicting unfinished setup; accepting it needs an explicit plan for the old globals and rebuild markers.


<a id="install.schema.classes_follow"></a>
[D · install.schema.classes_follow]

The ObjectScript classes follow the IVG Schema because setup rewrites their sources for that schema before compiling them; no class reads the record at run time. This keeps the classes' embedded SQL within the [speed budget](#install.schema.speed).


<a id="install.schema.speed"></a>
[I · install.schema.speed]

Using any IVG Schema, the default one or another, must not make a write, erase or read path more than 5% slower than the last code state before spec 262. A benchmark gate checks it.

## Status reports


<a id="install.status"></a>
[I · install.status]

Status reports current row counts across every graph, while the ordinary count methods report the default graph or the graph named by the caller. Its embedding totals count each distinct legacy or registered table of that kind, treating an older registry row with no kind as a node route.

- An install without a registry still reports its legacy embedding counts.
- A registered table that cannot be counted is named as an error, and completed counts remain available.
- If the graph census fails, the human report marks the graph size as unknown rather than printing an invented zero; the structured status keeps completed counts and probe errors.

## Setup


<a id="install.setup"></a>
[I · install.setup]

Setup can be run again at any time, and a repeated run changes no row and duplicates nothing. Operators run it after every package upgrade, after a restore, or when a class or function is missing.

- A user without the privileges setup needs gets an error naming the missing privilege, not a partial install.
- Setup refuses to start while the caller has uncommitted writes on the connection, because it commits as it goes and compiles classes.

- Working assumption: Prefer no ready schema record after failed deployment; a partial-ready record would need explicit per-capability admission rules.
- Working assumption: Treat a stored schema name as a namespace binding only. Represent readiness of each deployed capability (classes, adjacency index, ledger, erase) separately. An engine accepted by the record check has no claim on feature readiness. A feature call on a class-less namespace must give a named failure, not silently degrade.


<a id="install.setup.dry_run"></a>
[I · install.setup.dry_run]

A dry run of setup writes nothing: no DDL, row, global or grant. It reports what a real run would create, compile, grant, copy and record.


<a id="install.setup.resume"></a>
[I · install.setup.resume]

If setup stops partway, the next setup finishes the job and ends in the same state as one uninterrupted run. Setup writes the schema record as its last step, so a namespace with IVG objects and no record is an unfinished setup, and status says so.


## Deploying classes and IRIS editions


<a id="install.deploy"></a>
[I · install.deploy]

Setup compiles only the classes the server can run, and reports each skipped class with its reason. Everything else works without the skipped classes.

- A class with Python methods needs embedded Python.
- A class that names `%AI` classes needs them installed.
- A class that depends on a skipped class is skipped too.
- A deploy is skipped only when the same sources were deployed cleanly and every class is compiled, so the next setup redoes a failed deploy.
- Benchmark classes and the class that runs arbitrary code strings are not shipped.
- The REST dispatcher and the FHIR sync task ship, and stay inert until a web application or task schedule names them.


<a id="install.deploy.editions"></a>
[D · install.deploy.editions]

IVG supports IRIS Community Edition and AI-enabled builds from the same package.

- On Community 2026.1, which has embedded Python but no `%AI`, setup skips only the three MCP classes, so the IRIS-hosted MCP tools are unavailable.
- On a server without embedded Python, setup also skips the classes with Python methods and the REST dispatcher that depends on them.
- Community Edition stops on a host with more cores than its license allows, so the deployment must limit its cores.

## Upgrading an existing namespace


<a id="install.upgrade"></a>
[I · install.upgrade]

Upgrading a namespace that a 4.5.x release set up must not break the application's SQL. IVG stops using its legacy objects but leaves them in place and working, and logs once that they remain and how to remove them.

- Compiled Cypher plans built against the old names are discarded, so IVG never reuses one.
- On an IVG Schema other than `Graph_KG`, the 4.5.x ledger revision and counter rows are copied once into the schema's own ledger tables, only while those are empty.


<a id="install.upgrade.grants"></a>
[I · install.upgrade.grants]

Upgrading copies every privilege granted on a legacy object to its replacement in the IVG Schema. The setup dry run lists each grant it would copy.

- Grants on the four 4.5.x `SQLUser` views are reported and not copied, because a view has no replacement.

- Every setup also grants the rest of the Cypher read path to any user or role that already holds part of it, so a user who could run Cypher before an upgrade can after it.
- These grants are EXECUTE on routines only, never on a table.


<a id="install.upgrade.arno_revoke"></a>
[D · install.upgrade.arno_revoke]

As the one exception to keeping legacy objects working, upgrading revokes EXECUTE on the 4.5.x Arno SQL functions from everyone but `%All` holders. Those functions can open any library and call any function in it. The functions themselves stay in place.

## Legacy objects


<a id="install.legacy"></a>
[I · install.legacy]

Legacy objects are removed only when an operator asks. The default call lists the legacy objects present and changes nothing, and the removing call removes exactly those listed objects that are IVG's. The result reports truthfully, per object, whether it was removed, and running the call again lists what remains. The removing call refuses to run inside a caller's open transaction.

- Working assumption: Inventory both install paths. The product contract (spec 262 schema, inventory test) covers initialize_schema only. scripts/deploy_production.py + sql/schema.sql + sql/operators_fixed.sql form a reachable legacy path that produces a non-conforming namespace (DDL-only before its class step, unqualified procedures). sql/fraud_sample_data.sql is maintained demo data. Files with no loader are historical material.
- Working assumption: Classify sql/operators.sql as shipped historical/reference SQL with no deployment path. It is outside the executed product surface, but stays in the inventory as a shipped artifact whose definitions are not graph-scoped. Trace operators_fixed.sql (legacy deployer) and the schema.py procedures separately. If anyone runs the file by hand, it creates unqualified, graph-blind procedures (F-0820-like behaviour).


<a id="install.legacy.manifest"></a>
[D · install.legacy.manifest]

The legacy manifest is a fixed list of names and classes generated from the released versions, never a name pattern. An application object whose name only looks like IVG's is never listed or removed.


<a id="install.legacy.ownership"></a>
[D · install.legacy.ownership]

An object under a manifest name counts as IVG's only when its text matches a text some IVG release shipped. Any other object, such as an operator's own function reinstalled under the same name, is listed with a note and kept.

## Data migrations


<a id="install.migration"></a>
[I · install.migration]

Migrations that bring an older install's data into the current layout can be re-run and report what they did. They never delete a vector and never guess a graph.

- A row whose graph cannot be decided goes to a quarantine table and leaves only when an operator places it.
- Old adjacency-index entries that carry no graph are dropped and rebuilt from the SQL rows, never placed by guessing.
- A migration refuses to start while the caller has an open transaction.
- If a step's commit fails, the step is rolled back and the migration raises an error naming itself.


<a id="install.migration.steps"></a>
[D · install.migration.steps]

The 3.2.0 to 4.0.0 upgrade runs its steps in one fixed order, because each step reads what the one before it wrote. A step that would decide something again on a second run is skipped once its table is in the final shape, and a step that only repeats the same work runs again.


<a id="install.migration.schema"></a>
[I · install.migration.schema]

A migration obeys the namespace's schema record like any engine: on a namespace that records another schema, it is refused before it reads or writes. Any exemption for migrations covers at most the case where no schema is recorded yet.

- Working assumption: Require an explicit schema choice before a migration with no namespace record; arbitrary fallback schemas are not an inferred supported policy.


## Snapshots


<a id="install.snapshot"></a>
[I · install.snapshot]

A snapshot copies the namespace's graph content to a file and back. One server-side inventory of IVG's stores decides what is archived and what is derived. A snapshot is not a backup: it leaves out IVG's deploy record and compiled-plan state, its embedding queue, the quarantine table and the derived vector table.

- Working assumption: Prefer refusal while a live ledger exists until replace/merge history semantics are specified; do not count the current overlay as a decided contract.
- Working assumption: Claim a consistent snapshot only when writers are quiescent (an operator premise) or under a verified snapshot/epoch protocol; for the current exporter declare the quiet-writer premise.


<a id="install.snapshot.scope"></a>
[D · install.snapshot.scope]

Snapshots cover the whole namespace; there is no per-graph snapshot. `restore_snapshot(path)` replaces: it empties every graph and loads the archive. `restore_snapshot(path, merge=True)` keeps what is there and adds the archive's rows that are not.

- Configuration tables, such as FHIR registrations and SQL table mappings, match on their primary key: a replacing restore writes the archive's row, a merge keeps the live one.
- A restore is refused in ledger strict mode and while the caller has an open transaction.
- A restore refuses, before erasing anything, an archive whose recorded storage layout differs from the namespace's. An archive with no layout stamp is accepted.


<a id="install.snapshot.failure"></a>
[D · install.snapshot.failure]

Saving fails with no archive written if any table or global cannot be read. A restore is not atomic as a whole: a failed table commit raises an error naming the tables already committed. The erase that starts a replacing restore is one transaction.


<a id="install.snapshot.derived"></a>
[I · install.snapshot.derived]

A restore never brings back derived caches, and it moves the graph-version token past both its value before the restore and the archive's value. A cached answer from before the restore can therefore never be served after it.


<a id="install.snapshot.routes"></a>
[I · install.snapshot.routes]

A snapshot saves each routed vector table and restores it at the width the archive records, with each graph's vectors kept to that graph. After a restore, a width-checked vector search on each route reads its own table at its own width.
- A route is saved from its registry row. A row whose table name is not the routed shape, or that has no positive width, is not saved, and a warning says so.
- A restore creates each routed table at the archived width, not at the restoring engine's width, then loads it, builds its index and records the index state the database really has.
- A routed table found in the archive with no width entry takes its width from the restored registry row.
- Node vectors and routed vectors are matched on graph and node, so two graphs' rows stay apart. Edge vectors match on source, predicate and target with no graph.
- Observed limits: an existing routed table keeps its current width; an incompatible empty table refuses incoming vectors and reports failed rows. A merge keeps an existing graph/node vector and counts that skipped row as restored, even when the incoming vector has another width.
- A failed registry index-state update is logged and clears this engine's route cache, but can leave the archive's old index claim. A route with invalid width metadata may remain registered without a table; its vector reader then raises rather than answering empty.
- The generic node merge guard uses only the exported first column. A node with the same ID in another graph can therefore suppress the required parent, making its archived vector fail and its reader answer empty; this is a known merge defect, not the intended graph-key rule.


<a id="install.snapshot.temporal"></a>
[I · install.snapshot.temporal]

A temporal event saved in a snapshot answers a [window read](../features/temporal.g5.md#temporal.window) after a restore, not only a row count. The native subtrees the archive holds are read from the same store plan the restore uses, so every temporal subtree goes out and comes back.
- The default graph and timestamp zero are included. A suppressed reverse entry stays absent, so an outgoing event need not appear in an inbound window.
- Attribute types should survive too. Today scalar export turns numbers into text: a numeric attribute returns as a string after restore, while text stays text; the weight reader still returns a number. This is a known failure of type preservation.
- A refused global line can be skipped without an error or failed-row count while valid neighbors restore. This is a known failure of the required restore error report.
- An archive naming another storage layout is refused before anything is erased. The current reader admits an archive with no layout stamp; this does not establish compatibility for arbitrary old global shapes.
- The temporal subtrees saved are the events by time in both directions, the time buckets and their aggregates, the edge attributes, and the latest-event index.
## Bulk loading


<a id="install.bulk_load"></a>
[D · install.bulk_load]

IVG has three ways to load many rows quickly, and they do not give the same guarantees. Every one of them must follow the [bulk index rule](../features/graph-structure.g5.md#structure.adjacency.bulk), which that page owns. The two engine paths are also refused in ledger strict mode; the `BulkLoader` class is outside strict mode by documented decision.

- `bulk_create_nodes` and `bulk_create_edges` drop some SQL indexes around a large batch and rebuild them after.
- `bulk_load_session` does the same around a session of batches.
- `BulkLoader` inserts rows without index upkeep or key checks. Its `load_networkx` then rebuilds the namespace's indexes and adjacency index; its `load_nodes` and `load_edges` leave the rebuild to the caller.

- Working assumption: Keep documented loader exemptions and chunking; preserve other graphs and multigraph data unless a narrower supported envelope is expressly adopted.


<a id="install.bulk_load.loader"></a>
[D · install.bulk_load.loader]

The `BulkLoader` class trades per-row checks for speed.

- One loader writes one graph, and the default graph is written explicitly.
- It drops duplicates within a load and skips rows already stored, so loading the same data again changes nothing.
- Today it skips an input node as soon as its node row is stored, with that node's labels and properties. A load that failed after writing node rows therefore cannot be finished by loading again: those nodes keep no labels or properties.
- It refuses a caller's open transaction and commits per batch.
- It writes and rebuilds in the namespace's recorded IVG Schema, like every other IVG writer.
- Today it uses `Graph_KG` unless it is given the schema, and its index rebuild always names the `Graph_KG` classes. In a namespace with another IVG Schema, a load without the schema fails, and an unindexed load cannot be made readable by the loader's rebuild.
- Before its unindexed edge load writes any edge, it adds each edge's two end nodes to the loader's graph, so every edge it writes has both endpoints.
- A row that IRIS refuses for a reason other than a repeat stops the load with a bulk load error that says how many rows went in first. It is never reported as zero rows inserted.


<a id="install.bulk_load.ledger"></a>
[D · install.bulk_load.ledger]

The engine's bulk paths are refused in ledger strict mode, but the `BulkLoader` class is not governed by it and its writes are not recorded. The [ledger page](../features/ledger.g5.md#ledger.strict) owns the list of governed calls.


<a id="install.bulk_load.rebuild"></a>
[I · install.bulk_load.rebuild]

After any bulk load finishes, the adjacency index, the degree cache and the graph-version token must reflect the loaded rows before a read uses them. An SQL index that fails to come back is named in a warning, and reads that need it scan the table instead. Today `BulkLoader.load_nodes` and `load_edges` leave that rebuild to the caller, against the [bulk index rule](../features/graph-structure.g5.md#structure.adjacency.bulk), so a caller who skips it leaves those rows invisible to index-based reads.


## Imports and inference


<a id="install.import"></a>
[D · install.import]

Imports write as they go. `load_networkx`, `import_graph_ndjson` and `load_obo` write one node or relationship at a time, and `import_rdf` commits one batch at a time, so a failure keeps what was already written. Every import, and materializing or retracting inference, is refused in ledger strict mode.


<a id="install.import.ndjson"></a>
[D · install.import.ndjson]

An NDJSON import ignores blank lines; logs and counts malformed JSON, non-object JSON, unknown kinds, nodes without IDs and edges without all endpoints and predicate as skipped; and continues to later lines. A writer exception stops the call and returns no counts; without a caller transaction, earlier successful writes remain.

- `kind: node|edge|temporal_edge` selects a record. Without a kind, the ledger export's `type: node|rel` selects nodes or edges, with `props` or `s/p/o/quals` respectively. An explicit kind takes precedence over `type`.
- Node and edge counters count processed lines, even when `create_node` or `create_edge` returns False for an existing item. Duplicate node lines leave the existing node's properties unchanged; `upsert_nodes` controls creation of temporal endpoints, not updating duplicate node records.
- Node lines use the caller's graph (default if omitted). Edge lines use the caller's graph if supplied, otherwise the line's graph; an explicitly empty caller graph overrides a named line graph. Temporal batches and any endpoints they create use the default graph even when the caller supplies a graph.
- Temporal lines buffer until `batch_size` or end of file. Their counter advances by the flushed batch length, independently of the writer's return count; an exception prevents that increment and prevents the final pending flush. These counters do not establish rows created or atomicity of a failed temporal batch.

## Ordinary graph exports


<a id="install.export.ndjson"></a>
[D · install.export.ndjson]

`export_graph_ndjson` writes the default graph's node records, then its non-temporal structural edge records, in the format `import_graph_ndjson` reads. Its `nodes` and `edges` answers count lines written; parallel structural edges each have a line.

- A node record uses the public [node-read projection](../features/graph-structure.g5.md#structure.node.read), including its property aliases and value conversions. Its properties omit only the structural `id` and `labels` fields; this does not promise an inverse of stored property keys.
- Named graphs and marked temporal rows are excluded. Import-format compatibility does not promise that a later import preserves physical edge IDs, multiplicity or every stored type; those depend on the import writers.


<a id="install.export.rdf.scope"></a>
[D · install.export.rdf.scope]

`export_rdf` writes labels, properties and outgoing edges from every graph when `graph_id` is None, only the default graph when it is empty, and only the named graph otherwise. Nonempty node and label filters narrow that selection; a label must belong to the source node in the row's own graph.

- Empty filter collections do not narrow the export. A label filter writes the matching labels, the selected source nodes' properties and their outgoing edges; it does not pull in a target's other rows.
- A physical node without any selected label, property or outgoing edge contributes no RDF subject. Context-aware formats keep each generated triple in its row's graph.


<a id="install.export.rdf.content"></a>
[D · install.export.rdf.content]

A selected label becomes an `rdf:type` triple, a non-null property becomes a literal triple, and an edge becomes an IRI-object triple. Each physical edge with a nonempty qualifier dictionary also gets its own statement and reifier blank nodes; the `inferred` qualifier is omitted, even when it is the only qualifier.

- Node IDs, labels and edge predicates use `base_uri` unless they already start with `http://`, `https://`, `urn:` or `ftp://`. Property keys pass through as IRIs for the first three prefixes; other keys use `urn:ivg:prop/`. Qualifier predicates use `urn:ivg:qualifier/`.
- Property text tries a canonical integer spelling first, then a float as `xsd:decimal`, then a case-insensitive boolean, then plain text. The current qualifier path falls back to plain text when that literal is falsey, so zero and false qualifiers can differ from the same property value. This describes the current projection; the intended qualifier exception is not settled by the general literal description.
- The envelope has statement subject, predicate and object triples, plus a reifier-to-statement `rdf:reifies` triple. All of these and the qualifier triples use the edge's context; equal unqualified triples can collapse while separate qualified rows retain separate envelopes.


<a id="install.export.rdf.report"></a>
[D · install.export.rdf.report]

After serialization succeeds, RDF export reports the number of distinct triples across the union of contexts, the number of distinct subjects including blank nodes, and the number of those triples with an IRI object whose predicate is not `rdf:type`. These counts include qualifier envelopes and are not physical node or edge counts; the same triple in two contexts can be two serialized quads but one reported triple.

- The format argument overrides extension inference. N-Quads and TriG preserve graph contexts; flat formats do not establish a context-preserving export, and no successful answer promises file atomicity on an earlier error.

## Metadata

### install.namespace

- Sources: [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); [CONTEXT.md glossary: Namespace](../../../CONTEXT.md); [USER_GUIDE: one namespace per tenant](../../../docs/USER_GUIDE.md)
- Decision record: spec 262 names ADR-0016 as decided in a session with Tom on 2026-11-03
- Children: [IVG Schema](#install.schema)
- human-verified
- architecture-decision, security

### install.schema

- Sources: [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); [Spec 262 FR-001, FR-002, FR-002a](../../../specs/262-ivg-owned-sql-schema/spec.md)
- Tests (live): `tests/e2e/test_262_fresh_namespace.py`, `tests/e2e/test_262_alt_schema_paths.py`, `tests/e2e/test_262_inventory.py`
- Expands: [Namespace](#install.namespace)
- Children: [name](#install.schema.name), [record](#install.schema.record), [refusal](#install.schema.refusal), [not ready](#install.schema.not_ready), [existing](#install.schema.existing), [concurrency](#install.schema.concurrency), [classes follow](#install.schema.classes_follow)
- human-verified
- architecture-decision, operations
- test-coverage

Findings: [ADR-0016 still describes the IVG Schema design before it was built](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-005)

### install.schema.name

- Sources: [Spec 262 US3, FR-003, FR-004, Edge Cases (Case)](../../../specs/262-ivg-owned-sql-schema/spec.md); [schema_name.py](../../../iris_vector_graph/schema_name.py); [Spec 262 package clash](../../../specs/262-ivg-owned-sql-schema/spec.md#L201-L203); [refuse_package_clash](../../../iris_vector_graph/schema_name.py#L501-L509)
- Expands: [IVG Schema](#install.schema)
- human-verified
- user-facing-behavior

US3 is recorded as "Tom's requirement". ADR-0016 states the pattern as `[A-Z][A-Z0-9_]*`; the spec and the code accept mixed case, compared case-insensitively. Suspected divergence: the deploy rewrites class sources with the engine's spelling, not the recorded one (no test covers a lower-case engine on an upper-case record).

Findings: [An engine whose schema name differs only in case from the record loads classes under its own spelling](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-015)

### install.schema.record

- Sources: [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); [Spec 262 FR-005, Clarifications (rename out of scope)](../../../specs/262-ivg-owned-sql-schema/spec.md); [data-model.md](../../../specs/262-ivg-owned-sql-schema/data-model.md)
- Tests (live): `tests/e2e/test_262_record.py`; the consolidation route is in `tests/e2e/test_262_not_upgraded.py`
- Expands: [IVG Schema](#install.schema)
- human-verified
- architecture-decision, data-integrity
- test-coverage

Findings: [Two concurrent first setups can both record their IVG Schema, and the loser keeps writing to its own tables](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-003)

### install.schema.refusal

- uncertain
- Sources: [Spec 262 FR-006, SC-006, US4](../../../specs/262-ivg-owned-sql-schema/spec.md); [schema_name.py](../../../iris_vector_graph/schema_name.py); [engine.py](../../../iris_vector_graph/engine.py); [ADMIN_GUIDE (Native global access)](../../../docs/ADMIN_GUIDE.md)
- Expands: [IVG Schema](#install.schema)
- human-verified
- data-integrity, security
- test-coverage

Live coverage: `tests/e2e/test_262_record.py`. The skipped check for a login without `%Native_GlobalAccess` is documented in ADMIN_GUIDE §3. Observed divergence: migrations build their own engine and waive this refusal too ([receipt](../../Verus_verification/receipts/native/platform_schema_waiver.json); see [migration schema](#install.migration.schema)).

Findings: [The migrations' schema-check waiver also releases the refusal of a mismatched schema](../../Verus_verification/bugs_issues.md#bug-plt-007); [The schema check is skipped silently for logins without global access and for non-IRIS connections](../../Verus_verification/bugs_issues.md#bug-plt-022)

Open questions: [Should an engine that cannot read the schema record be refused?](../../Verus_verification/open_questions.md#HD-0101)

### install.schema.not_ready

- Sources: [Spec 262 Clarifications (not-yet-upgraded namespace), FR-006a](../../../specs/262-ivg-owned-sql-schema/spec.md); [schema_name.py](../../../iris_vector_graph/schema_name.py)
- Expands: [IVG Schema](#install.schema)
- human-verified
- user-facing-behavior, operations
- test-coverage

Live coverage: `tests/e2e/test_262_not_upgraded.py`. Known issue: after a setup that stopped once the current SQL objects existed, the engine is accepted without a record (KNOWN_ISSUES "After an interrupted setup").

### install.schema.existing

- Sources: [Spec 262 FR-009, US4](../../../specs/262-ivg-owned-sql-schema/spec.md); [data-model.md state transitions](../../../specs/262-ivg-owned-sql-schema/data-model.md); [_engine/schema.py](../../../iris_vector_graph/_engine/schema.py)
- Tests (live): `tests/e2e/test_262_record.py` (one-schema and two-schema 4.5.1 fixtures, whole-namespace snapshots)
- Expands: [IVG Schema](#install.schema)
- agent
- data-integrity, operations
- test-coverage


Observed divergence (code reading, review round 3 R3-reader H3): setup records an explicitly named engine schema even when IVG's tables are in one other schema ([schema.py](../../../iris_vector_graph/_engine/schema.py#L2229-L2242)); FR-009 allows an explicit name only when the tables are in several schemas, and the engine's own comment says the same ([engine.py](../../../iris_vector_graph/engine.py#L294-L297)). The only test uses a default engine.

Findings: [Setup records an explicitly named schema while IVG's tables sit in one other schema](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-026)

### install.schema.concurrency

- uncertain
- Sources: [Spec 262 FR-005, FR-006, SC-006](../../../specs/262-ivg-owned-sql-schema/spec.md); [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); [_engine/schema.py _record_and_initialize](../../../iris_vector_graph/_engine/schema.py); [Stage A notes F-S1](../../uplift/ivg-verus-initial/intent/platform.md); [Review round 1, R1-4](../../uplift/ivg-verus-initial/review/round1-platform.md)
- Expands: [IVG Schema](#install.schema)
- Children: [Can an explicitly named schema be recorded over another schema's interrupted first setup?](../../Verus_verification/open_questions.md#q-plt-002)
- agent
- data-integrity

Concurrency changes how the rule is kept, not which outcome FR-005, FR-006 and ADR-0016 require ("instead of sharing globals silently"). No human source mentions concurrent setups, and "refused before it writes" is the model's proposed lock, so the block is `agent` (review round 3 R3-reader M16). Suspected divergence (not yet observed natively): setup reads the record, runs for tens of seconds and writes it if none existed, with no lock, then releases its own engine, so two racing setups can both finish and the loser keeps writing under the other record. Review round 1 notes that a compare-and-set record write alone would not repair this; the losing setup must also stay refused.

Findings: [Two concurrent first setups can both record their IVG Schema, and the loser keeps writing to its own tables](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-003)

Open questions: [Can an explicitly named schema be recorded over another schema's interrupted first setup?](../../Verus_verification/open_questions.md#q-plt-002)

### install.schema.classes_follow

- Sources: [Spec 262 research R1](../../../specs/262-ivg-owned-sql-schema/research.md); [plan.md](../../../specs/262-ivg-owned-sql-schema/plan.md); [class_deploy.py](../../../iris_vector_graph/_engine/class_deploy.py)
- Supersedes: ADR-0016's wording that "the ObjectScript classes read it there"; its status line still says "implementation pending"
- Expands: [IVG Schema](#install.schema)
- Children: [Speed budget](#install.schema.speed)
- agent
- architecture-decision

Findings: [BulkLoader ignores the namespace's IVG Schema](../../Verus_verification/bugs_issues.md#bug-plt-012)

### install.schema.speed

- Sources: [Spec 262 Clarifications (speed)](../../../specs/262-ivg-owned-sql-schema/spec.md#L44), [FR-020a](../../../specs/262-ivg-owned-sql-schema/spec.md#L290), [SC-006a](../../../specs/262-ivg-owned-sql-schema/spec.md#L322)
- Expands: [Classes follow the schema](#install.schema.classes_follow)
- human-provided
- operations

The clarification is a recorded human answer; FR-020a names the baseline code state `a42db224` and the gate's run rule (medians of at least 5 interleaved runs per path; Tom's allowed paths may cost up to twice their recorded cost). The gate was not run in this uplift. Added by review round 3 R3-reader M24.

### install.status

- design-verified
- Sources: [USER_GUIDE, status counts every graph](../../../docs/USER_GUIDE.md#L1203); [ADMIN_GUIDE, status fields and unknown probes](../../../docs/ADMIN_GUIDE.md#L920); [registry-kind and partial count tests](../../../tests/unit/test_230_status_counts.py); [report graph scope](../../../tests/unit/test_460_r050_status_counts_every_graph.py); [failed census and unknown report](../../../tests/unit/test_460_r050_status_unknown.py)
- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_raw_catalog_to_final_report`, `theorem_route_tables_never_double_count`, `theorem_registry_kind_and_shape_both_required`, `theorem_failed_table_keeps_other_counts` and `theorem_failure_is_unknown_not_empty`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). Raw rows and registry/error fields derive partial census and graph/node-vector report knowledge. Actual Python executes local SQL and the final reader under a stable registry view and refusal outcome across the two kind scans; transient per-read registry changes, native/index/schema truth, general IRIS comparison/driver semantics, other report fields and cross-read snapshots remain outside this correspondence. Label/property/edge-vector errors do not by themselves make graph size unknown.
- agent
- user-facing-behavior, operations

This owner recovers ordinary reporting intent from the primary docs and tests before the selected reporting implementation is modeled. Graph identity and the meaning of an omitted graph remain with [graph scope](graph-scope.g5.md#graph.default). Probe availability, native counters, readiness flags and other status fields are separate conditions; this count/report rule does not certify them or a transactionally consistent snapshot across separate reads. The selected producer-to-report relation has been independently replayed within the linked package's stated source and provider frame.

State machines: [routine reporting](../../Verus_verification/models/routine_reporting/manifest.json)

### install.setup

- design-verified

- uncertain
- Sources: [ADMIN_GUIDE: Running setup again](../../../docs/ADMIN_GUIDE.md); [_engine/schema.py initialize_schema](../../../iris_vector_graph/_engine/schema.py); [Spec 262 Edge Cases (Privileges)](../../../specs/262-ivg-owned-sql-schema/spec.md); [CHANGELOG v4.7.0](../../../CHANGELOG.md)
- Children: [dry run](#install.setup.dry_run), [resume](#install.setup.resume), [Should setup still record the schema when some classes failed to deploy?](../../Verus_verification/open_questions.md#q-plt-010)
- Verus: [setup_record.rs](../../Verus_verification/models/setup_record/setup_record.rs) `theorem_fresh_namespace_is_new_and_recorded`, `theorem_second_run_existing_and_unchanged`, `theorem_mismatch_refused` and `theorem_other_schema_needs_a_name`; [scope and native lifecycle observations](../../Verus_verification/models/setup_record/NOTES.md)
- agent
- operations

The caller-transaction refusal came in 4.7.0 (live: `tests/e2e/test_470_caller_txn_3b_e2e.py`). Observed divergence: when a missing privilege stops a later statement, the objects created before it stay and the error says so; a re-run once granted finishes.

Open questions: [Should setup save the schema record when the class deploy failed or was turned off?](../../Verus_verification/open_questions.md#HD-0102), [Should setup still record the schema when some classes failed to deploy?](../../Verus_verification/open_questions.md#q-plt-010)

State machines: [setup record](../../Verus_verification/models/setup_record/manifest.json)

### install.setup.dry_run

- design-verified

- Sources: [Spec 262 FR-013, Edge Cases (Read-only and dry runs)](../../../specs/262-ivg-owned-sql-schema/spec.md)
- Tests (live): whole-namespace before/after snapshots in `tests/e2e/test_262_record.py` and `tests/e2e/test_262_upgrade_451.py`
- Verus: [setup_record.rs](../../Verus_verification/models/setup_record/setup_record.rs) `theorem_dry_run_writes_nothing` and `theorem_refusal_writes_nothing`; [scope and native lifecycle observations](../../Verus_verification/models/setup_record/NOTES.md)
- Expands: [Setup](#install.setup)
- agent
- operations

State machines: [setup record](../../Verus_verification/models/setup_record/manifest.json)

### install.setup.resume

- design-verified

- Sources: [Spec 262 Edge Cases (An interrupted upgrade)](../../../specs/262-ivg-owned-sql-schema/spec.md); [KNOWN_ISSUES: After an interrupted setup](../../../docs/KNOWN_ISSUES.md)
- Tests (live): `tests/e2e/test_262_upgrade_451.py::test_an_interrupted_upgrade_resumes_to_the_same_end` covers only an interruption after the functions exist and before the record is written
- Verus: [setup_record.rs](../../Verus_verification/models/setup_record/setup_record.rs) `theorem_interrupted_setup_resumes`; [scope and native lifecycle observations](../../Verus_verification/models/setup_record/NOTES.md)
- Expands: [Setup](#install.setup)
- agent
- operations, data-integrity

State machines: [setup record](../../Verus_verification/models/setup_record/manifest.json)

### install.deploy

- Sources: [ADMIN_GUIDE: Classes setup skips](../../../docs/ADMIN_GUIDE.md); [Spec 262 Edge Cases (Embedded Python and Community Edition), FR-015, FR-016](../../../specs/262-ivg-owned-sql-schema/spec.md); [class_deploy.py](../../../iris_vector_graph/_engine/class_deploy.py)
- Tests (live): `tests/e2e/test_262_inventory.py` compares the published inventory, including the skipped table, with a fresh namespace
- Children: [editions](#install.deploy.editions)
- agent
- operations
- test-coverage

Findings: [Retire the leftover schema-state helpers that are process-global or probe retired classes](../../Verus_verification/design_simplification.md#simp-plt-005)

### install.deploy.editions

- Sources: [ADMIN_GUIDE §1 and Classes setup skips](../../../docs/ADMIN_GUIDE.md); [MCPToolSet.cls](../../../iris_src/src/Graph/KG/MCPToolSet.cls); [run-community-redaction.py](../../../experiment/g5-verus/run-community-redaction.py)
- Expands: [Deploy](#install.deploy)
- agent
- operations

Only the three MCP classes name `%AI`. The upstream test fixture loads every class unconditionally and so fails on Community; the experiment's runner uses setup's skip logic instead. The MCP live tests need `%AI`.

### install.upgrade

- Sources: [Spec 262 US2, FR-010, FR-014](../../../specs/262-ivg-owned-sql-schema/spec.md); [docs/migration/v4.6.0.md](../../../docs/migration/v4.6.0.md); [_engine/legacy.py copy_ledger_history (4.6.0 R114)](../../../iris_vector_graph/_engine/legacy.py)
- Tests (live): `tests/e2e/test_262_upgrade_451.py` builds 4.5.1 and 3.2.0 namespaces from frozen DDL and checks that a 4.5.1 native plan is gone
- Children: [grants](#install.upgrade.grants), [Arno revoke](#install.upgrade.arno_revoke)
- agent
- user-facing-behavior, operations
- test-coverage

### install.upgrade.grants

- Sources: [Spec 262 Clarifications (grants), FR-010a, FR-010b](../../../specs/262-ivg-owned-sql-schema/spec.md); [_engine/legacy.py](../../../iris_vector_graph/_engine/legacy.py)
- Tests (live): `tests/e2e/test_262_upgrade_451.py` runs Cypher as a role holding only the copied grant, before and after
- Expands: [Upgrade](#install.upgrade)
- human-verified
- security, operations
- test-coverage


The view exception is in [legacy.py copy_grants](../../../iris_vector_graph/_engine/legacy.py#L247-L250) and the ADMIN_GUIDE; added by review round 3 R3-reader M24.

### install.upgrade.arno_revoke

- Sources: [Spec 262 FR-010c](../../../specs/262-ivg-owned-sql-schema/spec.md); [CHANGELOG v4.6.0 (R293)](../../../CHANGELOG.md)
- Expands: [Upgrade](#install.upgrade)
- human-verified
- security

FR-010c records this as Tom's decision of 2026-11-04. A grant held through a schema-wide grant cannot be revoked on one object; setup warns about it.

### install.legacy

- uncertain
- Sources: [Spec 262 FR-011, US2, SC-005](../../../specs/262-ivg-owned-sql-schema/spec.md); [ADR-0016 Consequences](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); [_engine/legacy.py remove_legacy_objects](../../../iris_vector_graph/_engine/legacy.py); [Stage A notes F-S4](../../uplift/ivg-verus-initial/intent/platform.md)
- Children: [manifest](#install.legacy.manifest), [ownership](#install.legacy.ownership)
- agent
- operations, data-integrity
- test-coverage

ADR-0016 says 5.0 removes legacy objects on upgrade and calls the function `remove_legacy_sql_objects`; the shipped name is `remove_legacy_objects`. Live coverage: `tests/e2e/test_262_upgrade_451.py`, `tests/e2e/test_460_legacy_manifest_400_e2e.py`, `tests/e2e/test_460_legacy_manifest_320_loader_e2e.py`. Observed divergence: when one class holds several SQL procedures and deleting it fails, the later procedures are still reported as removed.

Findings: [remove_legacy_objects reports later procedures of a class as removed when the class's delete failed](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-014)


The caller-transaction refusal is 4.7.0 ([admin.py](../../../iris_vector_graph/_engine/admin.py#L385-L393)); added by review round 3 R3-reader L11.

Open questions: [Are the files under sql/ part of the product?](../../Verus_verification/open_questions.md#HD-0103), [Is `sql/operators.sql` product code?](../../Verus_verification/open_questions.md#HD-0803)

### install.legacy.manifest

- Sources: [Spec 262 FR-012](../../../specs/262-ivg-owned-sql-schema/spec.md); [legacy_manifest.py](../../../iris_vector_graph/legacy_manifest.py)
- Tests (unit): `tests/unit/test_legacy_manifest.py` regenerates the manifest from release tags and fails on any difference
- Expands: [Legacy objects](#install.legacy)
- agent
- data-integrity

### install.legacy.ownership

- Sources: [CHANGELOG v4.6.3 (Fixed: upgrading)](../../../CHANGELOG.md#L499-L509); [legacy_bodies.py](../../../iris_vector_graph/legacy_bodies.py)
- Tests (live): `tests/e2e/test_463_legacy_same_named_functions_e2e.py`
- Expands: [Legacy objects](#install.legacy)
- agent
- data-integrity
- test-coverage

### install.migration

- Sources: [migrations/__init__.py](../../../iris_vector_graph/migrations/__init__.py); [migrations/_commit.py](../../../iris_vector_graph/migrations/_commit.py); [migrations/kg_node_stores.py](../../../iris_vector_graph/migrations/kg_node_stores.py); [docs/migration/v4.0.0.md](../../../docs/migration/v4.0.0.md)
- Children: [steps](#install.migration.steps), [schema](#install.migration.schema)
- agent
- data-integrity, operations
- test-coverage

Live coverage: the 3.2.0 cases in `tests/e2e/test_262_upgrade_451.py`. KNOWN_ISSUES records that a 2.x named-graph edge whose endpoints are only in the default graph is kept in an unplaced table. The adjacency re-key comes from spec 230, whose directory is not in the tree; a crash between its drop and rebuild leaves those entries empty until the step is re-run.

Findings: [The 4.0.0 documents migration can drop the documents table after its copy failed with a tolerated error](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-001)

### install.migration.steps

- Sources: [migrations/upgrade.py](../../../iris_vector_graph/migrations/upgrade.py); [Spec 240](../../../specs/240-alt-migration-as-data/spec.md); [Spec 241](../../../specs/241-alt-single-graph-backfill/spec.md)
- Expands: [Migrations](#install.migration)
- agent
- architecture-decision

Specs 240 and 241 say "not adopted" or "Draft", but both are merged and shipped. Suspected risk: the docs step treats any error whose text contains "not found" or "does not exist" as already done, before a step that drops the source table.

Findings: [The 4.0.0 documents migration can drop the documents table after its copy failed with a tolerated error](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-001)

### install.migration.schema

- uncertain
- Sources: [Spec 262 FR-006](../../../specs/262-ivg-owned-sql-schema/spec.md); [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); [engine.py _waive_schema_check](../../../iris_vector_graph/engine.py); [graph_scoped_embeddings.py](../../../iris_vector_graph/migrations/graph_scoped_embeddings.py); [temporal_structural_rows.py](../../../iris_vector_graph/migrations/temporal_structural_rows.py); [Review round 1, R1-5](../../uplift/ivg-verus-initial/review/round1-platform.md)
- Expands: [Migrations](#install.migration)
- Children: [May a data migration run before any setup has recorded the namespace's IVG Schema, and on which schema?](../../Verus_verification/open_questions.md#q-plt-011)
- human-verified
- data-integrity

FR-006 has no exception for migrations, and the waiver's only stated reason (the code comment) covers a namespace no current setup has recorded. Observed divergence: with `Graph_KG` recorded, a migration engine on another schema is not refused, and the temporal backfill reaches SQL on that schema's tables ([receipt](../../Verus_verification/receipts/native/platform_schema_waiver.json)).

Findings: [The migrations' schema-check waiver also releases the refusal of a mismatched schema](../../Verus_verification/bugs_issues.md#bug-plt-007)

Open questions: [May a data migration run before any setup has recorded the namespace's IVG Schema, and on which schema?](../../Verus_verification/open_questions.md#q-plt-011)

### install.snapshot

- uncertain
- Sources: [USER_GUIDE §10](../../../docs/USER_GUIDE.md); [ADMIN_GUIDE: backups and snapshots](../../../docs/ADMIN_GUIDE.md); [_engine/snapshot.py STORE_PLAN](../../../iris_vector_graph/_engine/snapshot.py); [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md)
- Children: [scope](#install.snapshot.scope), [failure](#install.snapshot.failure), [derived](#install.snapshot.derived), [What should a restore do when the namespace already has a live ledger?](../../Verus_verification/open_questions.md#q-plt-004), [routed vectors](#install.snapshot.routes), [temporal events](#install.snapshot.temporal)
- agent
- user-facing-behavior, operations
- test-coverage

Live coverage of the inventory: `tests/integration/test_snapshot_inventory.py`. Snapshots made through the HTTP server land in the temporary directory unless `IVG_SNAPSHOT_DIR` is set (KNOWN_ISSUES).

Findings: [A merge restore keeps at most one row per graph in the core tables and reports every row restored](../../Verus_verification/bugs_issues.md#bug-plt-004)

Audit reproduction: [bug-plt-004](../../Verus_verification/bugs_issues.md#bug-plt-004) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Open questions: [Should a snapshot be a point-in-time view?](../../Verus_verification/open_questions.md#HD-1802), [What should a restore do when the namespace already has a live ledger?](../../Verus_verification/open_questions.md#q-plt-004)

Assumption review evidence: Changed from decisions.md: **no**.

### install.snapshot.scope

- Sources: [USER_GUIDE §10](../../../docs/USER_GUIDE.md); [ADMIN_GUIDE (configuration tables)](../../../docs/ADMIN_GUIDE.md); [_engine/snapshot.py restore_snapshot](../../../iris_vector_graph/_engine/snapshot.py); [Stage A notes F-B1, F-B2](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Snapshots](#install.snapshot)
- agent
- user-facing-behavior, data-integrity

Suspected divergence: a merging restore matches the core tables' rows on the first exported column only (in practice the graph ID), so it may add at most one row per graph while counting every row as restored. A multigraph graph restored into an indexed namespace may lose its parallel-edge layout.

Findings: [A replacing restore leaves the live search indexes in place and merges the archive's into them](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-024)


Layout check: [snapshot.py restore_snapshot](../../../iris_vector_graph/_engine/snapshot.py#L1086-L1129) (added by review round 3 R3-reader M24).

### install.snapshot.failure

- Sources: [_engine/snapshot.py](../../../iris_vector_graph/_engine/snapshot.py); [ADMIN_GUIDE](../../../docs/ADMIN_GUIDE.md); [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls)
- Expands: [Snapshots](#install.snapshot)
- agent
- data-integrity, operations

Introduced in 4.6.0 (R271, R276). Suspected divergence: one global line that fails to write during restore is logged and skipped without being counted or reported.

Findings: [A restore swallows a global line that fails to import](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-016)

### install.snapshot.derived

- Sources: [_engine/snapshot.py](../../../iris_vector_graph/_engine/snapshot.py); [Spec 236 FR-018](../../../specs/236-arno-callout-adoption/spec.md)
- Tests (live): `tests/integration/test_236_token_write_paths.py` (restore and merge cases)
- Expands: [Snapshots](#install.snapshot)
- agent
- data-integrity
- test-coverage

### install.snapshot.routes

- design-verified
- Sources: [`iris_vector_graph/_engine/snapshot.py::routed_export_plan`](../../../iris_vector_graph/_engine/snapshot.py#L299-L344); [`iris_vector_graph/_engine/snapshot.py::SnapshotMixin.restore_snapshot`](../../../iris_vector_graph/_engine/snapshot.py#L1077-L1611) (routed tables at the archived width `:1372-1500`; node and routed vectors matched on graph and node `:1341-1350`, `:1473-1480`); live tests [test_snapshot_routed_embeddings.py](../../../tests/integration/test_snapshot_routed_embeddings.py#L152-L200), unit [test_snapshot_inventory.py](../../../tests/unit/test_snapshot_inventory.py)
- Playbook: [SNP-B1.7](../../../experiment/playbook-completion/ontology/18-snapshot.md#L51), [SNP-B2.11](../../../experiment/playbook-completion/ontology/18-snapshot.md#L84), [SNP-B4.5](../../../experiment/playbook-completion/ontology/18-snapshot.md#L119)
- Formal contract: [routed snapshot stages and reader](../../Verus_verification/models/snapshot_routes/snapshot_routes.rs). It covers decoded node routes, declaration/registry/row stages and literal width admission; full archive loops, temporal globals and arbitrary provider failure outcomes remain open. The imported reviewed `snap_l2` is retained as partial historical evidence.
- Findings: [generic merge key](../../Verus_verification/bugs_issues.md#bug-plt-004)
- Expands: [Snapshots](#install.snapshot)
- agent
- user-facing-behavior, data-integrity

Public case J01. Edge vectors matching with no graph is the playbook's finding F-1803.

Audit reproduction: [bug-plt-004](../../Verus_verification/bugs_issues.md#bug-plt-004) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [F-1802](../../Verus_verification/bugs_issues.md#F-1802) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A merge restore guards plain tables on their first column only, and counts skipped rows as restored](../../Verus_verification/bugs_issues.md#F-1802).

State machines: [snapshot routes](../../Verus_verification/models/snapshot_routes/manifest.json)

### install.snapshot.temporal

- design-verified
- Sources: [`iris_vector_graph/_engine/snapshot.py::snapshot_globals`](../../../iris_vector_graph/_engine/snapshot.py#L387-L408), [`::kg_export_subscripts`](../../../iris_vector_graph/_engine/snapshot.py#L425-L437), `STORE_PLAN` temporal entries [`snapshot.py`](../../../iris_vector_graph/_engine/snapshot.py#L136-L144); live tests [`test_the_restored_temporal_edge_answers_a_window_query`](../../../tests/integration/test_snapshot_inventory.py#L116-L130), unit `tests/unit/test_snapshot_inventory.py::test_the_globals_export_is_derived_from_the_plan`
- Playbook: [SNP-I1.1](../../../experiment/playbook-completion/ontology/18-snapshot.md#L40), [SNP-B1](../../../experiment/playbook-completion/ontology/18-snapshot.md#L42), [TMP-B6](../../../experiment/playbook-completion/ontology/05-temporal.md#L201)
- Formal contract: [temporal restore, scalar types and window projection](../../Verus_verification/models/temporal_restore/temporal_restore.rs). Critical source keys are derived from the finite source map under the Native API enumeration contract; full page-sequence/global-loop composition and general codecs remain open. The unchanged paging family is an explicitly stamped dependency, not new proof credit.
- Findings: [scalar type loss](../../Verus_verification/bugs_issues.md#F-1804), [silent global-line loss](../../Verus_verification/audits/register-20261115/bugs-review.md#F-C1802)
- Expands: [Snapshots](#install.snapshot)
- agent
- user-facing-behavior, data-integrity

Public case J02. A hand-kept second list of exported subtrees once dropped all five temporal subtrees from every archive (playbook note on SNP-I1.1); the list is now derived.

Audit reproduction: [F-1804](../../Verus_verification/bugs_issues.md#F-1804) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [temporal restore](../../Verus_verification/models/temporal_restore/manifest.json)

### install.bulk_load

- uncertain
- Sources: [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md); [_engine/nodes_edges.py](../../../iris_vector_graph/_engine/nodes_edges.py); [bulk_loader.py](../../../iris_vector_graph/bulk_loader.py); [structure.adjacency.bulk](../features/graph-structure.g5.md#structure.adjacency.bulk)
- Children: [loader](#install.bulk_load.loader), [ledger](#install.bulk_load.ledger), [rebuild](#install.bulk_load.rebuild), [Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?](../../Verus_verification/open_questions.md#q-plt-005)
- agent
- architecture-decision, data-integrity
- test-coverage

The engine paths drop indexes only for batches of 500 rows or more. Inside a caller's transaction, `bulk_load_session` keeps its indexes and leaves the adjacency to rebuild after the caller commits (4.7.0); that rule is owned by [structure.adjacency.bulk](../features/graph-structure.g5.md#structure.adjacency.bulk). Observed divergence (review round 3 R3-reader M6): spec 252 FR-008 and ADR-0008 require every `%NOINDEX` bulk path to rebuild before it returns, but `BulkLoader.load_nodes` and `load_edges` tell the caller to call `rebuild_all_indices()` ([bulk_loader.py](../../../iris_vector_graph/bulk_loader.py#L380-L395)). Live coverage: `tests/integration/test_bulk_loader_live.py`, `tests/integration/test_bulk_loader_endpoints.py`.

Findings: [An interrupted BulkLoader node load cannot be resumed: re-loading skips the labels and properties of nodes already written](../../Verus_verification/bugs_issues.md#bug-plt-011); [BulkLoader's node and edge loads write without indexes and return before rebuilding them](../../Verus_verification/bugs_issues.md#bug-plt-027)

Open questions: [Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?](../../Verus_verification/open_questions.md#q-plt-005)

### install.bulk_load.loader

- Sources: [bulk_loader.py](../../../iris_vector_graph/bulk_loader.py); [USER_GUIDE](../../../docs/USER_GUIDE.md); [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); endpoints: [`iris_vector_graph/bulk_loader.py::BulkLoader._register_endpoints`](../../../iris_vector_graph/bulk_loader.py#L201-L228) (indexed insert into the loader's graph); refusals: [`::BulkLoader._executemany_batched`](../../../iris_vector_graph/bulk_loader.py#L83-L154) (batch failure or short count goes row by row `:118-143`; `BulkLoadError` `:126`, `:142`); live tests [test_bulk_loader_endpoints.py](../../../tests/integration/test_bulk_loader_endpoints.py), unit `tests/unit/test_bulk_loader_unit.py::TestExecutemanyBatched::test_non_unique_error_raises`
- Playbook: [WRT-B7.12](../../../experiment/playbook-completion/ontology/03-writes.md#L207), [WRT-B7.14](../../../experiment/playbook-completion/ontology/03-writes.md#L209)
- Verus: [bulk_load](../../Verus_verification/models/bulk_load/NOTES.md) `theorem_complete_rerun_is_noop`, `theorem_interrupted_load_is_never_completed`, `theorem_noindex_invisible_until_rebuild`, `theorem_done_then_rebuild_reads_input`, `theorem_same_id_other_graph_is_written`, `theorem_loader_without_schema_writes_nothing`, `theorem_rebuild_in_other_schema_leaves_rows_unreadable` (as-built, node loads). Endpoint registration and the duplicate-or-refusal decision have no formal contract; the playbook's `proofs-d1c` `bulk_l2` (reviewed design) models chunk checkpoints only.
- Expands: [Bulk loading](#install.bulk_load)
- agent
- user-facing-behavior, operations

Metadata note: the phase order and the re-run outcome after an interrupted load are in the statement; the default unindexed load's visibility is owned by [rebuild](#install.bulk_load.rebuild).

Public case M23. A repeat is told from a refusal by the error text: SQLCODE -119 or the word "unique" in the message (`bulk_loader.py:105-106`), so a non-repeat refusal whose message happens to contain "unique" would be skipped as a repeat (code reading; not run). Observed divergence: the loader defaults to `Graph_KG`, and its index rebuild names the `Graph_KG` table classes whatever schema it was given.

Findings: [BulkLoader ignores the namespace's IVG Schema](../../Verus_verification/bugs_issues.md#bug-plt-012); [An interrupted BulkLoader node load cannot be resumed: re-loading skips the labels and properties of nodes already written](../../Verus_verification/bugs_issues.md#bug-plt-011); [BulkLoader's node and edge loads write without indexes and return before rebuilding them](../../Verus_verification/bugs_issues.md#bug-plt-027)

State machines: [bulk load](../../Verus_verification/models/bulk_load/manifest.json)

### install.bulk_load.ledger

- Sources: [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [ledger.strict](../features/ledger.g5.md#ledger.strict)
- Expands: [Bulk loading](#install.bulk_load)
- agent
- data-integrity

Audit (HD-0301): Existing authority: The standalone BulkLoader and raw SQL are expressly outside the client strict-mode guard. That exception does not exempt other engine writers. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-0301).

Findings: [Does ledger strict mode cover the standalone bulk loader?](../../Verus_verification/open_questions.md#HD-0301).

### install.bulk_load.rebuild

- Sources: [bulk_loader.py](../../../iris_vector_graph/bulk_loader.py); [_engine/nodes_edges.py _rebuild_after_load](../../../iris_vector_graph/_engine/nodes_edges.py); [ADR-0011](../../../docs/adr/0011-the-adjacency-index-has-one-writer-module.md); [ADR-0012](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md)
- Verus: [bulk_load](../../Verus_verification/models/bulk_load/NOTES.md) `theorem_done_then_rebuild_reads_input` (`BulkLoader.rebuild_all_indices` for node loads)
- Expands: [Bulk loading](#install.bulk_load)
- agent
- data-integrity

The warning for an index that was not rebuilt dates from 4.6.0 (R257). The `BulkLoader` rebuild goes through the adjacency index's own writer, so it keeps ADR-0011's single writer. No test checks the degree cache or the token after a bulk load.

Findings: [Rebuild adjacency once after load_networkx](../../Verus_verification/design_simplification.md#simp-plt-004)

State machines: [bulk load](../../Verus_verification/models/bulk_load/manifest.json)

### install.import
- Children: [NDJSON](#install.import.ndjson)

- Sources: [snapshot.py load_networkx](../../../iris_vector_graph/_engine/snapshot.py#L446-L556), [import_rdf](../../../iris_vector_graph/_engine/snapshot.py#L557-L720), [import_graph_ndjson](../../../iris_vector_graph/_engine/snapshot.py#L1727-L1856), [load_obo](../../../iris_vector_graph/_engine/snapshot.py#L1694-L1726), [materialize_inference](../../../iris_vector_graph/_engine/schema.py#L2966), [ledger strict list](../features/ledger.g5.md#ledger.strict), [operations inventory G7](../../uplift/ivg-verus-initial/intent/operations.md#L150-L158)
- agent
- data-integrity, operations

Added by review round 3 R3-reader M23 (the stage-A reconstruction check items 3, 4 and 7 had raised it). `import_rdf`'s docstring says it "commits per batch"; inside a caller's transaction each batch is an IVG level nested in it, and a non-indexed install refuses the caller's transaction. Whether re-running an import after a failure finishes it cleanly was not checked. The inference commit boundary was not traced. Not modelled and not observed natively.

### install.import.ndjson

- design-verified
- Sources: [`SnapshotMixin.import_graph_ndjson`](../../../iris_vector_graph/_engine/snapshot.py#L1727-L1855), [`NodesEdgesMixin.create_node`](../../../iris_vector_graph/_engine/nodes_edges.py#L968-L1107), [unit tests](../../../tests/unit/test_edgeprop_ndjson.py#L45-L95)
- Playbook: [WRT-B7.86](../../../experiment/playbook-completion/ontology/03-writes.md#L221), [WRT-T7.87](../../../experiment/playbook-completion/ontology/03-writes.md#L222), [WRT-B2.80](../../../experiment/playbook-completion/ontology/03-writes.md#L92)
- Verus: [ndjson_import](../../Verus_verification/models/ndjson_import/NOTES.md), as-built node admission, width refusal, prefix preservation and duplicate counts. Edge routing and temporal batching are unit observations only and remain formal gaps; parser behavior is a scoped boundary assumption.
- agent
- user-facing-behavior, data-integrity
- Expands: [imports](#install.import)

State machines: [ndjson export](../../Verus_verification/models/ndjson_export/manifest.json), [ndjson import](../../Verus_verification/models/ndjson_import/manifest.json)

### install.export.ndjson

- design-verified

- Sources: [User Guide export](../../../docs/USER_GUIDE.md#L1170-L1181), [API reference](../../../docs/API_REFERENCE.md#L2163-L2169), [NDJSON format](../../../docs/setup/DATA_FORMATS.md#3-ndjson), [`SnapshotMixin.export_graph_ndjson`](../../../iris_vector_graph/_engine/snapshot.py#L1857-L1908)
- Tests (live): [R088 default/named/temporal export](../../../tests/e2e/test_460_export_graph_ndjson_e2e.py); existing [import unit tests](../../../tests/unit/test_edgeprop_ndjson.py)
- Related: [node reads](../features/graph-structure.g5.md#structure.node.read), [How should flat node reads preserve colliding property aliases?](../../Verus_verification/open_questions.md#q-iter-001), [NDJSON admission](#install.import.ndjson)
- Evidence: [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md), [sealed13 full-record survey](../../uplift/consolidated/iteration-13/next-records-survey.md)
- Verus: [ndjson_export.rs](../../Verus_verification/models/ndjson_export/ndjson_export.rs) `theorem_complete_export_line_sequence_and_counts`, `theorem_default_census_derived`, `theorem_raw_node_event_content`, `theorem_edge_census_derived`, `theorem_edge_qualifier_zero_not_omitted` and `theorem_actual_generated_export_to_import_callbacks`, with final-file witnesses; [scope and provider limits](../../Verus_verification/models/ndjson_export/NOTES.md)
- agent
- user-facing-behavior, data-integrity

Exporting writes only the default graph: first one node line for each node whose node row has the empty graph name, in node-ID order, then one edge line for each default-graph edge row, in edge-ID order. It returns `nodes` and `edges` equal to the lines of each kind it wrote.

- A node line is written even when the node has no labels or properties. A node that exists only in a named graph gets no line, and its named-graph labels and properties do not enter a default node's line.
- A node line carries every default-graph label and the properties as the node reader reports them, including the [How should flat node reads preserve colliding property aliases?](../../Verus_verification/open_questions.md#q-iter-001): a stored property named `id` appears as `p_id`. When both `id` and `p_id` are stored, only the value delivered last survives.
- Every physical default-graph edge row is its own line, so two parallel rows with the same source, predicate and target give two lines. Temporal-marked rows (qualifiers starting `{"temporal"`) and named-graph rows are not written.
- A non-empty qualifier object is copied, including `{"q": 0}`; an absent or empty qualifier is left out.
- Reading the file with [NDJSON import](#install.import.ndjson) passes each line's labels, properties, graph and qualifiers to the create calls and counts the lines read. That is argument agreement, not a storage round trip: alias and value normalization mean a re-import need not restore the original rows.

This recovers ordinary export behavior; it is not a new product requirement. The file claim assumes a stable SQL view, ordinary SQL ordering and successful JSON and file writes; failure, partial-file and concurrent-writer behavior are not covered.

State machines: [ndjson export](../../Verus_verification/models/ndjson_export/manifest.json)

### install.export.rdf.scope

- design-verified

- Sources: [Semantic Layer selection](../../../docs/SEMANTIC_LAYER.md#L95-L115), [API reference](../../../docs/API_REFERENCE.md#L2253-L2274), [`_build_rdflib_graph`](../../../iris_vector_graph/_engine/_rdf_utils.py#L102-L294)
- Tests (live): [R099 label filtering](../../../tests/e2e/test_460_rdf_export_label_filter_e2e.py), [R100 graph contexts](../../../tests/e2e/test_460_rdf_export_nquads_graphs_e2e.py), [graph scope unit tests](../../../tests/unit/test_230_rdf_export_scope.py)
- Related: [graph scope](graph-scope.g5.md#graph.default), [content](#install.export.rdf.content), [report](#install.export.rdf.report)
- Evidence: [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md), [sealed13 ordinary RDF survey](../../uplift/consolidated/iteration-13/next-reporting-survey.md)
- Verus: [rdf_reporting.rs](../../Verus_verification/models/rdf_reporting/rdf_reporting.rs) `theorem_graph_filter_is_request_value`, `theorem_empty_filters_are_unfiltered`, `theorem_label_selection_is_raw`, `theorem_wrong_graph_membership_is_excluded`, `theorem_source_not_target_selects` and `theorem_outside_requested_ids_emits_nothing`; [scope and provider limits](../../Verus_verification/models/rdf_reporting/NOTES.md)
- agent
- user-facing-behavior, data-integrity

RDF export selects rows by graph, node ID and label before building any triple.

- `graph_id=None` exports every graph; `""` exports the default graph, including rows whose graph is SQL NULL; any other value exports only that named graph.
- An empty or omitted ID list or label list does not filter. A non-empty ID list selects label, property and edge rows by their subject (the edge's source, not its target).
- With a label filter, only matching label rows become `rdf:type` triples. A property or edge row is kept only when its subject carries a matching label in the row's own graph; a label on the edge's target, or on the same ID in another graph, does not qualify.

The label projection and own-graph membership are explicit source and regression behavior; no policy about exporting all labels of a selected node is inferred. SQL equality, nullable-graph normalization and a stable relational view are correspondence conditions.

State machines: [rdf reporting](../../Verus_verification/models/rdf_reporting/manifest.json)

### install.export.rdf.content

- design-verified

- Sources: [Semantic Layer row/term/qualifier rules](../../../docs/SEMANTIC_LAYER.md#L39-L65), [`_mint_iri`, `graph_iri`, `_to_literal`, `_build_rdflib_graph`](../../../iris_vector_graph/_engine/_rdf_utils.py#L29-L294)
- Tests (live): [literal/qualifier unit tests](../../../tests/unit/test_rdf_export.py), [R100 generated context contents](../../../tests/e2e/test_460_rdf_export_nquads_graphs_e2e.py), [R122 named-graph IRIs](../../../tests/e2e/test_460_rdf_graph_id_not_an_iri_e2e.py)
- Evidence: [sealed13 typed literal and actual file observations](../../uplift/consolidated/iteration-13/next-reporting-sanity.json)
- Related: [scope](#install.export.rdf.scope), [report](#install.export.rdf.report)
- Verus: [rdf_reporting.rs](../../Verus_verification/models/rdf_reporting/rdf_reporting.rs) `theorem_raw_rows_generate_exactly_the_quad_set`, `theorem_two_raw_digits_determine_value`, `theorem_dyadic_is_derived`, `theorem_property_null_is_omitted`, `theorem_node_property_prefixes_differ`, `theorem_original_object_decides_envelope`, `theorem_inferred_only_still_has_envelope`, `theorem_falsey_qualifier_fallback`, `theorem_unqualified_parallel_rows_collapse` and `theorem_selected_qualified_parallel_rows_keep_global_blanks`; [scope and provider limits](../../Verus_verification/models/rdf_reporting/NOTES.md)
- agent
- user-facing-behavior, data-integrity

Each selected row becomes triples in its graph's context: the default graph, or the named graph's IRI.

- A label row becomes an `rdf:type` triple. A property row with a NULL value emits nothing. Otherwise its value is typed: canonical integer text (`7`) becomes `xsd:integer`; other number text (`007`, `2.5`) becomes `xsd:decimal`; `true`/`false` in any case become booleans; anything else is a plain string.
- Node IDs, labels and edge predicates starting `http://`, `https://`, `urn:` or `ftp://` are used as IRIs unchanged; other values get the base prefix. Property keys pass through only for `http://`, `https://` and `urn:`; any other key, including `ftp://`, becomes `urn:ivg:prop/<key>` whatever the base prefix.
- Each edge row adds its subject–predicate–object triple. When its qualifier text decodes to a non-empty object, the row also gets its own fresh statement and reifier blank nodes: four envelope triples, then one `urn:ivg:qualifier/<key>` triple per key except `inferred`. An object holding only `inferred` still gets the envelope; an empty or absent qualifier gets none.
- A qualifier value that would become a false literal (`0`, JSON `false`) is written as plain text (`"0"`, `"False"`), while the same value as a property keeps its type.
- Two unqualified parallel rows give one triple; two qualified parallel rows keep separate blank nodes.

The public literal description does not settle the false/zero qualifier exception, so this as-built behavior is not intended-policy approval. Graph-IRI encoding, wider numeric and JSON text, and rdflib's term, blank-node and serializer behavior are named provider conditions.

State machines: [rdf reporting](../../Verus_verification/models/rdf_reporting/manifest.json)

### install.export.rdf.report

- design-verified

- Sources: [Semantic Layer metrics and formats](../../../docs/SEMANTIC_LAYER.md#L67-L93), [`RdfExportMixin.export_rdf`](../../../iris_vector_graph/_engine/rdf_export.py#L96-L157), [format inference](../../../iris_vector_graph/_engine/_rdf_utils.py#L56-L69)
- Evidence: [sealed13 ordinary union/quad contrast](../../uplift/consolidated/iteration-13/next-reporting-survey.md), [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md)
- Related: [content](#install.export.rdf.content)
- Verus: [rdf_reporting.rs](../../Verus_verification/models/rdf_reporting/rdf_reporting.rs) `theorem_raw_rows_to_final_report`, `theorem_summary_reads_union_not_rows`, `theorem_summary_two_contexts_is_one_triple`, `theorem_summary_counts_subjects_not_objects` and `theorem_non_type_uri_count_rule`; [scope and provider limits](../../Verus_verification/models/rdf_reporting/NOTES.md)
- agent
- user-facing-behavior, data-integrity

The returned counts read the generated triples merged across contexts, not the rows or the lines in the file.

- `triples` counts distinct subject–predicate–object triples, so the same triple in two named graphs counts once even though N-Quads writes two lines.
- `nodes` counts distinct subjects, including the blank statement and reifier nodes of qualified edges; a node that appears only as an object is not counted.
- `edges` counts distinct triples whose object is an IRI and whose predicate is not `rdf:type`. This includes the IRI-valued envelope triples of qualified edges.

This settles the docs' "counts what was written" wording as a union reader without promising equal serialized line counts. Namespace binding, third-party serialization and parsing, provider failures and cross-read consistency remain qualified; no whole-serializer or failed-file guarantee follows.

State machines: [rdf reporting](../../Verus_verification/models/rdf_reporting/manifest.json)
