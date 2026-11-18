# Set up and upgrade IVG

Start here to install IVG in an IRIS namespace, choose its SQL schema, or bring an older installation forward. For checks after setup, see [status and repair](status-and-repair.g5.md).

## Definitions

- **Namespace**: the IRIS namespace IVG is installed in. Everything IVG keeps outside SQL (adjacency index, ledger, settings) belongs to it.
- **IVG Schema**: the one SQL schema in a namespace that holds every table, function, procedure and view IVG creates. It is `Graph_KG` unless another name is chosen.
- **Schema record**: the namespace's note of which IVG Schema it uses, kept beside IVG's deploy record.
- **Setup**: `initialize_schema()`, which creates IVG's SQL objects, compiles its ObjectScript classes and writes the schema record.
- **Dry run**: a call that reports what setup, an upgrade step or legacy removal would do, and writes nothing.
- **Legacy object**: a function, view or class an IVG release before 4.6.0 created in `SQLUser`, the `User` package, or with no package, plus classes IVG stopped shipping.
- **Legacy manifest**: the fixed list of legacy objects, taken from the released versions.
- **Integer adjacency copy**: `^NKG`, the copy of the adjacency index the graph algorithms read. It has no graph dimension: an edge held by two graphs is one entry. `engine.sync()` rebuilds it.
- **Pending-sync flag**: one engine's own note that it wrote rows it left for `sync()` to put in the integer copy. Other engines and processes do not see it.
- **Routed vector table**: a node-vector table made for one graph or model, named `kg_emb_` plus 16 hex digits and recorded in the embedding registry; `kg_NodeEmbeddings` is the legacy table.
- **Readiness flag**: one of the status report's `ready_for_*` answers, which an operator reads before running the operation it names.

## Server deployment and defaults

<a id="access.defaults"></a>
[D · access.defaults]

Out of the box the HTTP server listens on every network interface, port 8200, and Bolt on 7687. Both connect to IRIS as `_SYSTEM` with password `SYS` unless configured. The operator guide says to set the key on any server another machine can reach, and to give the server a non-superuser login.

- Working assumption: Treat the documented open bind and credentials as current behavior only; safer defaults need a maintainer policy decision.
- Working assumption: The product contract at the pin is ADMIN_GUIDE section 5's open default; F-1709 is a documentation defect against deploy/README.md:86 (registered as fail against that stated text). For the reviewed deployment, keep local-only binding or an explicit opt-in for unauthenticated external binding as a stated premise, not as the product's intent.

<a id="access.webapp"></a>
[D · access.webapp]

The IRIS REST dispatcher stays inert until an operator creates its web application. That application uses password login and gives every user one read-only role for the namespace, which holds only what its search routes read.

- Working assumption: Treat both apps as supported entry points subject to the shared HTTP safety constraints: key gate and read-only (already applied), a depth bound, and an honest health check. Record the generated app's missing depth limit and always-healthy /health as gaps against that parity, not as violations of a stated contract.

## Which schema belongs to this namespace?

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
- Today an engine that names the recorded schema in another letter case is accepted, but its setup loads the schema classes under its own spelling, which fail to compile, and re-declares the empty vector columns at its own width without being asked, while the registry keeps the old width ([bug-plt-015](../../Verus_verification/bugs_issues.md#bug-plt-015)).

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

- Today a namespace with no record whose IVG Schema already holds this release's SQL objects (a setup that stopped after creating them, or a record removed by hand) admits every engine for that schema, and a namespace with a record is not checked for its objects ([bug-plt-133](../../Verus_verification/bugs_issues.md#bug-plt-133)).

<a id="install.schema.existing"></a>
[I · install.schema.existing]

Setup on a namespace without a record decides what to record from where IVG's tables already are:

- No IVG tables: record the engine's schema.
- Tables in the engine's schema only: record that schema.
- Tables in one other schema only: refuse, name that schema, and record nothing, even when the engine's schema was named explicitly.
- Tables in several schemas and no name given: refuse, list each schema with its row counts, and record nothing.
- Tables in several schemas and a name given: record the named schema and report the others, untouched.
- Today a name given also records the named schema when the tables are in one other schema only, and that schema's engine is refused from then on ([bug-plt-026](../../Verus_verification/bugs_issues.md#bug-plt-026)). ADMIN_GUIDE and the setup error's own advice describe this path, so the docs disagree with spec FR-009.

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

## Set up a namespace

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

- The next setup records the schema as `inferred` when IVG's tables are in the engine's schema alone.
- Today engines are not refused meanwhile once the unfinished setup created this release's SQL objects ([install.schema.not_ready](#install.schema.not_ready)).

## Deploy on the installed IRIS edition

<a id="install.deploy"></a>
[I · install.deploy]

Setup compiles only the classes the server can run, and reports each skipped class with its reason. Everything else works without the skipped classes.

- A class with Python methods needs embedded Python.
- A class that names `%AI` classes needs them installed.
- A class that depends on a skipped class is skipped too.
- A deploy is skipped only when the same sources were deployed cleanly and every class is compiled, so the next setup redoes a failed deploy. A changed fingerprint (as after a package upgrade) or one class gone makes setup compile every class again.
- Benchmark classes and the class that runs arbitrary code strings are not shipped.
- The REST dispatcher and the FHIR sync task ship, and stay inert until a web application or task schedule names them.

<a id="install.deploy.editions"></a>
[D · install.deploy.editions]

IVG supports IRIS Community Edition and AI-enabled builds from the same package.

- On Community 2026.1, which has embedded Python but no `%AI`, setup skips only the three MCP classes, so the IRIS-hosted MCP tools are unavailable.
- On a server without embedded Python, setup also skips the classes with Python methods and the REST dispatcher that depends on them.
- Community Edition stops on a host with more cores than its license allows, so the deployment must limit its cores.

## Upgrade an existing namespace

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

## Metadata

### access.defaults

- uncertain
- Sources: [ADMIN_API.md: Starting the server](../../../docs/ADMIN_API.md); [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api/main.py](../../../api/main.py); [cli.py](../../../iris_vector_graph/cli.py)
- Children: [Should the server refuse to start on a reachable address with no key and a superuser login?](../../Verus_verification/open_questions.md#q-plt-003)
- agent
- security, operations

Observed divergence: the sample API and `.env.sample` read the login from `IRIS_USER`, the HTTP server and CLI from `IRIS_USERNAME`, so following `.env.sample` for the HTTP server connects as `_SYSTEM`. Bolt per-session IRIS connections are not closed at session end.

Findings: [The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM](../../Verus_verification/bugs_issues.md#bug-plt-009)

Open questions: [Should server start refuse to listen on every address without an API key?](../../Verus_verification/open_questions.md#HD-1705), [Should the server refuse to start on a reachable address with no key and a superuser login?](../../Verus_verification/open_questions.md#q-plt-003)

Assumption review evidence: Changed from decisions.md: yes. decisions.md kept both contradictory contracts open; commit 6df261d9/R032 makes ADMIN_GUIDE the single operator document and git history shows --force-no-auth was never implemented on any branch, so the open default is the current contract and the hardening is a deployment premise.

### access.webapp

- uncertain
- Sources: [Service.cls CreateWebApp](../../../iris_src/src/Graph/KG/Service.cls); [ADMIN_GUIDE](../../../docs/ADMIN_GUIDE.md)
- agent
- security

Changed in 4.6.0 (R131, R147); earlier releases gave every authenticated user `%All`. Re-running the creator resets an application an earlier release made.

Open questions: [Should the generated GraphQL server match the sample API's safety limits?](../../Verus_verification/open_questions.md#HD-1605)

Assumption review evidence: Changed from decisions.md: **yes**. Partial change. decisions.md left the choice open between 'distinct entry points' and parity. R097, R107 and R079 show the maintainer already hardening create_app as a deployable app, so parity (b) is now the working direction. decisions.md also used 'sample' for the app the maintainer calls the development app.

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

Iteration 56: the case variant reproduced end to end (fresh namespaces I56SB, I56SD); [install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_name_rules_refuse_before_default`, `theorem_arg_wins`, `theorem_unknown_width_altered_unasked`.

Findings: [An engine whose schema name differs only in case from the record loads classes under its own spelling](../../Verus_verification/bugs_issues.md#bug-plt-015)

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

Live coverage: `tests/e2e/test_262_record.py`. The skipped check for a login without `%Native_GlobalAccess` is documented in ADMIN_GUIDE §3. Iteration 56: [install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_other_record_refused` (every public call refused, the exempt calls run; binding `A:alt_*`) and `theorem_deploy_refuses_other_record`. Observed divergence: migrations build their own engine and waive this refusal too ([receipt](../../Verus_verification/receipts/native/platform_schema_waiver.json); see [migration schema](#install.migration.schema)).

Findings: [The migrations' schema-check waiver also releases the refusal of a mismatched schema](../../Verus_verification/bugs_issues.md#bug-plt-007); [The schema check is skipped silently for logins without global access and for non-IRIS connections](../../Verus_verification/bugs_issues.md#bug-plt-022)

Open questions: [Should an engine that cannot read the schema record be refused?](../../Verus_verification/open_questions.md#HD-0101)

### install.schema.not_ready

- Sources: [Spec 262 Clarifications (not-yet-upgraded namespace), FR-006a](../../../specs/262-ivg-owned-sql-schema/spec.md); [schema_name.py](../../../iris_vector_graph/schema_name.py)
- Expands: [IVG Schema](#install.schema)
- human-verified
- user-facing-behavior, operations
- test-coverage

Live coverage: `tests/e2e/test_262_not_upgraded.py`. Known issue: after a setup that stopped once the current SQL objects existed, the engine is accepted without a record (KNOWN_ISSUES "After an interrupted setup"). ADMIN_GUIDE describes the as-built rule ("no record and lacks 4.6.0's SQL objects").

Iteration 56: [install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_unrecorded_reason_order`, `theorem_unrecorded_with_marker_admitted`, `theorem_record_admits_without_objects`; control `unrecorded-marker-refused`; binding cases `A:norecord_marker_call`, `A:record_nomarker_call`, `C:*`.

Findings: [An unrecorded namespace holding this release's SQL objects admits engines](../../Verus_verification/bugs_issues.md#bug-plt-133)

### install.schema.existing

- Sources: [Spec 262 FR-009, US4](../../../specs/262-ivg-owned-sql-schema/spec.md); [data-model.md state transitions](../../../specs/262-ivg-owned-sql-schema/data-model.md); [_engine/schema.py](../../../iris_vector_graph/_engine/schema.py)
- Tests (live): `tests/e2e/test_262_record.py` (one-schema and two-schema 4.5.1 fixtures, whole-namespace snapshots)
- Expands: [IVG Schema](#install.schema)
- agent
- data-integrity, operations
- test-coverage


Observed divergence (code reading, review round 3 R3-reader H3): setup records an explicitly named engine schema even when IVG's tables are in one other schema ([schema.py](../../../iris_vector_graph/_engine/schema.py#L2229-L2242)); FR-009 allows an explicit name only when the tables are in several schemas, and the engine's own comment says the same ([engine.py](../../../iris_vector_graph/engine.py#L294-L297)). The only test uses a default engine.

Iteration 56: reproduced end to end in I56SB ([install_lifecycle](../../Verus_verification/models/install_lifecycle/NOTES.md) `theorem_other_schema_needs_a_name`, control `explicit-refused`, binding `B:y_explicit_setup`).

Findings: [Setup records an explicitly named schema while IVG's tables sit in one other schema](../../Verus_verification/bugs_issues.md#bug-plt-026)

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

### install.setup


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


- Sources: [Spec 262 FR-013, Edge Cases (Read-only and dry runs)](../../../specs/262-ivg-owned-sql-schema/spec.md)
- Tests (live): whole-namespace before/after snapshots in `tests/e2e/test_262_record.py` and `tests/e2e/test_262_upgrade_451.py`
- Verus: [setup_record.rs](../../Verus_verification/models/setup_record/setup_record.rs) `theorem_dry_run_writes_nothing` and `theorem_refusal_writes_nothing`; [scope and native lifecycle observations](../../Verus_verification/models/setup_record/NOTES.md)
- Verus: [install_lifecycle.rs](../../Verus_verification/models/install_lifecycle/install_lifecycle.rs) `theorem_dry_run_and_refusals_keep_record`, `theorem_clash_refused_before_anything`; [scope, premises and bindings](../../Verus_verification/models/install_lifecycle/NOTES.md)
- Expands: [Setup](#install.setup)
- agent
- operations

State machines: [setup record](../../Verus_verification/models/setup_record/manifest.json)

### install.setup.resume


- design-verified

- Sources: [Spec 262 Edge Cases (An interrupted upgrade)](../../../specs/262-ivg-owned-sql-schema/spec.md); [KNOWN_ISSUES: After an interrupted setup](../../../docs/KNOWN_ISSUES.md)
- Tests (live): `tests/e2e/test_262_upgrade_451.py::test_an_interrupted_upgrade_resumes_to_the_same_end` covers only an interruption after the functions exist and before the record is written
- Verus: [setup_record.rs](../../Verus_verification/models/setup_record/setup_record.rs) `theorem_interrupted_setup_resumes`; [scope and native lifecycle observations](../../Verus_verification/models/setup_record/NOTES.md)
- Verus: [install_lifecycle.rs](../../Verus_verification/models/install_lifecycle/install_lifecycle.rs) `theorem_existing_after_first_run`, `theorem_setup_then_access`, `theorem_unrecorded_with_marker_admitted`; [scope, premises and bindings](../../Verus_verification/models/install_lifecycle/NOTES.md)
- Expands: [Setup](#install.setup)
- agent
- operations, data-integrity

Findings: [An unrecorded namespace holding this release's marker function admits engines](../../Verus_verification/bugs_issues.md#bug-plt-133)

State machines: [setup record](../../Verus_verification/models/setup_record/manifest.json)

### install.deploy

- Sources: [ADMIN_GUIDE: Classes setup skips](../../../docs/ADMIN_GUIDE.md); [Spec 262 Edge Cases (Embedded Python and Community Edition), FR-015, FR-016](../../../specs/262-ivg-owned-sql-schema/spec.md); [class_deploy.py](../../../iris_vector_graph/_engine/class_deploy.py)
- Tests (live): `tests/e2e/test_262_inventory.py` compares the published inventory, including the skipped table, with a fresh namespace
- Verus: [install_lifecycle.rs](../../Verus_verification/models/install_lifecycle/install_lifecycle.rs) `theorem_skip_iff_same_fingerprint_and_all_compiled`, `theorem_failed_deploy_retried`, `theorem_clean_deploy_then_skip`, `theorem_missing_class_redeploys`, `theorem_deploy_refuses_other_record`; [scope, premises and bindings](../../Verus_verification/models/install_lifecycle/NOTES.md)
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
