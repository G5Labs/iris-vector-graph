# Install, schema, upgrades and data movement

Choose [setup and upgrades](../operations/setup-and-upgrade.g5.md), [status and repair](../operations/status-and-repair.g5.md), [snapshots and bulk loading](../operations/snapshots-and-bulk-load.g5.md), or [graph import and export](../features/data-interchange.g5.md).

## Earlier links

These links take you to the current sections and statements.

<a id="the-namespace-and-its-ivg-schema"></a>

[Which schema belongs to this namespace?](../operations/setup-and-upgrade.g5.md#which-schema-belongs-to-this-namespace)

<a id="status-reports"></a>

[Check readiness and synchronization](../operations/status-and-repair.g5.md#check-readiness-and-synchronization)

<a id="setup"></a>

[Set up a namespace](../operations/setup-and-upgrade.g5.md#set-up-a-namespace)

<a id="deploying-classes-and-iris-editions"></a>

[Deploy on the installed IRIS edition](../operations/setup-and-upgrade.g5.md#deploy-on-the-installed-iris-edition)

<a id="upgrading-an-existing-namespace"></a>

[Upgrade an existing namespace](../operations/setup-and-upgrade.g5.md#upgrade-an-existing-namespace)

<a id="legacy-objects"></a>

[Legacy objects](../operations/setup-and-upgrade.g5.md#legacy-objects)

<a id="data-migrations"></a>

[Data migrations](../operations/setup-and-upgrade.g5.md#data-migrations)

<a id="snapshots"></a>

[Save or restore a snapshot](../operations/snapshots-and-bulk-load.g5.md#save-or-restore-a-snapshot)

<a id="bulk-loading"></a>

[Load data in bulk](../operations/snapshots-and-bulk-load.g5.md#load-data-in-bulk)

<a id="imports-and-inference"></a>

[Import triples and graph records](../features/data-interchange.g5.md#import-triples-and-graph-records)

<a id="ordinary-graph-exports"></a>

[Export graph data](../features/data-interchange.g5.md#export-graph-data) · [Validating graph data with SHACL](../features/data-interchange.g5.md#validating-graph-data-with-shacl)

<a id="definitions"></a>

[Definitions](../operations/setup-and-upgrade.g5.md#definitions)

<a id="metadata"></a>

[Statement metadata](../operations/setup-and-upgrade.g5.md#metadata)

<a id="install.namespace"></a>

[install.namespace](../operations/setup-and-upgrade.g5.md#install.namespace)

<a id="install.schema"></a>

[install.schema](../operations/setup-and-upgrade.g5.md#install.schema)

<a id="install.schema.name"></a>

[install.schema.name](../operations/setup-and-upgrade.g5.md#install.schema.name)

<a id="install.schema.record"></a>

[install.schema.record](../operations/setup-and-upgrade.g5.md#install.schema.record)

<a id="install.schema.refusal"></a>

[install.schema.refusal](../operations/setup-and-upgrade.g5.md#install.schema.refusal)

<a id="install.schema.not_ready"></a>

[install.schema.not_ready](../operations/setup-and-upgrade.g5.md#install.schema.not_ready)

<a id="install.schema.existing"></a>

[install.schema.existing](../operations/setup-and-upgrade.g5.md#install.schema.existing)

<a id="install.schema.concurrency"></a>

[install.schema.concurrency](../operations/setup-and-upgrade.g5.md#install.schema.concurrency)

<a id="install.schema.classes_follow"></a>

[install.schema.classes_follow](../operations/setup-and-upgrade.g5.md#install.schema.classes_follow)

<a id="install.schema.speed"></a>

[install.schema.speed](../operations/setup-and-upgrade.g5.md#install.schema.speed)

<a id="install.status"></a>

[install.status](../operations/status-and-repair.g5.md#install.status)

<a id="install.status.readiness"></a>

[install.status.readiness](../operations/status-and-repair.g5.md#install.status.readiness)

<a id="install.status.sync"></a>

[install.status.sync](../operations/status-and-repair.g5.md#install.status.sync)

<a id="install.status.verify_sync"></a>

[install.status.verify_sync](../operations/status-and-repair.g5.md#install.status.verify_sync)

<a id="install.status.capabilities"></a>

[install.status.capabilities](../operations/status-and-repair.g5.md#install.status.capabilities)

<a id="install.status.readers"></a>

[install.status.readers](../operations/status-and-repair.g5.md#install.status.readers)

<a id="install.status.ledger"></a>

[install.status.ledger](../operations/status-and-repair.g5.md#install.status.ledger)

<a id="install.status.diagram"></a>

[install.status.diagram](../operations/status-and-repair.g5.md#install.status.diagram)

<a id="install.setup"></a>

[install.setup](../operations/setup-and-upgrade.g5.md#install.setup)

<a id="install.setup.dry_run"></a>

[install.setup.dry_run](../operations/setup-and-upgrade.g5.md#install.setup.dry_run)

<a id="install.setup.resume"></a>

[install.setup.resume](../operations/setup-and-upgrade.g5.md#install.setup.resume)

<a id="install.deploy"></a>

[install.deploy](../operations/setup-and-upgrade.g5.md#install.deploy)

<a id="install.deploy.editions"></a>

[install.deploy.editions](../operations/setup-and-upgrade.g5.md#install.deploy.editions)

<a id="install.upgrade"></a>

[install.upgrade](../operations/setup-and-upgrade.g5.md#install.upgrade)

<a id="install.upgrade.grants"></a>

[install.upgrade.grants](../operations/setup-and-upgrade.g5.md#install.upgrade.grants)

<a id="install.upgrade.arno_revoke"></a>

[install.upgrade.arno_revoke](../operations/setup-and-upgrade.g5.md#install.upgrade.arno_revoke)

<a id="install.legacy"></a>

[install.legacy](../operations/setup-and-upgrade.g5.md#install.legacy)

<a id="install.legacy.manifest"></a>

[install.legacy.manifest](../operations/setup-and-upgrade.g5.md#install.legacy.manifest)

<a id="install.legacy.ownership"></a>

[install.legacy.ownership](../operations/setup-and-upgrade.g5.md#install.legacy.ownership)

<a id="install.migration"></a>

[install.migration](../operations/setup-and-upgrade.g5.md#install.migration)

<a id="install.migration.steps"></a>

[install.migration.steps](../operations/setup-and-upgrade.g5.md#install.migration.steps)

<a id="install.migration.schema"></a>

[install.migration.schema](../operations/setup-and-upgrade.g5.md#install.migration.schema)

<a id="install.snapshot"></a>

[install.snapshot](../operations/snapshots-and-bulk-load.g5.md#install.snapshot)

<a id="install.snapshot.scope"></a>

[install.snapshot.scope](../operations/snapshots-and-bulk-load.g5.md#install.snapshot.scope)

<a id="install.snapshot.failure"></a>

[install.snapshot.failure](../operations/snapshots-and-bulk-load.g5.md#install.snapshot.failure)

<a id="install.snapshot.derived"></a>

[install.snapshot.derived](../operations/snapshots-and-bulk-load.g5.md#install.snapshot.derived)

<a id="install.snapshot.routes"></a>

[install.snapshot.routes](../operations/snapshots-and-bulk-load.g5.md#install.snapshot.routes)

<a id="install.snapshot.temporal"></a>

[install.snapshot.temporal](../operations/snapshots-and-bulk-load.g5.md#install.snapshot.temporal)

<a id="install.snapshot.info"></a>

[install.snapshot.info](../operations/snapshots-and-bulk-load.g5.md#install.snapshot.info)

<a id="install.bulk_load"></a>

[install.bulk_load](../operations/snapshots-and-bulk-load.g5.md#install.bulk_load)

<a id="install.bulk_load.loader"></a>

[install.bulk_load.loader](../operations/snapshots-and-bulk-load.g5.md#install.bulk_load.loader)

<a id="install.bulk_load.ledger"></a>

[install.bulk_load.ledger](../operations/snapshots-and-bulk-load.g5.md#install.bulk_load.ledger)

<a id="install.bulk_load.rebuild"></a>

[install.bulk_load.rebuild](../operations/snapshots-and-bulk-load.g5.md#install.bulk_load.rebuild)

<a id="install.import"></a>

[install.import](../features/data-interchange.g5.md#install.import)

<a id="install.import.rdf"></a>

[install.import.rdf](../features/data-interchange.g5.md#install.import.rdf)

<a id="install.import.ndjson"></a>

[install.import.ndjson](../features/data-interchange.g5.md#install.import.ndjson)

<a id="install.inference"></a>

[install.inference](../features/data-interchange.g5.md#install.inference)

<a id="install.export.ndjson"></a>

[install.export.ndjson](../features/data-interchange.g5.md#install.export.ndjson)

<a id="install.export.rdf.scope"></a>

[install.export.rdf.scope](../features/data-interchange.g5.md#install.export.rdf.scope)

<a id="install.export.rdf.content"></a>

[install.export.rdf.content](../features/data-interchange.g5.md#install.export.rdf.content)

<a id="install.export.rdf.report"></a>

[install.export.rdf.report](../features/data-interchange.g5.md#install.export.rdf.report)

<a id="install.shacl"></a>

[install.shacl](../features/data-interchange.g5.md#install.shacl)

<a id="install.export.prov"></a>

[install.export.prov](../features/data-interchange.g5.md#install.export.prov)

<a id="install.export.rdf.cypher"></a>

[install.export.rdf.cypher](../features/data-interchange.g5.md#install.export.rdf.cypher)
