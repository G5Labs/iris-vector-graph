# W21: setup lifecycle on a fresh namespace — predictions frozen before observation

A different underserved workflow (schema setup, `_engine/schema.py`: 7 of 83 members bound), tested before any
convergence claim. Frozen 2026-11-16 before running setup in namespace W21. Exposure: the `initialize_schema` docstring
(report keys; dry run writes no DDL, row, global or grant; caller-transaction refusal). Owners:
[install.setup](../../../ontology/concepts/install.g5.md#install.setup), `.dry_run`, `.resume`.

Fixture: namespace W21 with its own new database, created inside the run-isolated container for this test. Snapshot
reader after each step: tables in schema `Graph_KG` with row counts, routines in `Graph_KG`, compiled `Graph.KG.*`
classes, and `^IVG.Deploy("schema")`.

| Step | Prediction (owner) |
|---|---|
| 1. dry run | snapshot unchanged (no tables, routines, classes or record); report `dry_run` true and a `schema_recorded` value saying the schema would be recorded as new |
| 2. real run | tables, routines and classes created; record `Graph_KG`; report `schema_recorded` new |
| 3. dry run again | snapshot identical to after step 2; report says the schema is already recorded |
| 4. real run again | snapshot identical to after step 2 (no row, table or class change); no duplicates |

## Outcome of steps 1–4 ([observation](setup-lifecycle-observed-20261116T171148Z.json))

All held: dry run unchanged and `new`; real run created 18 tables, 114 routines, 140 classes and recorded `Graph_KG`
(`new`); second dry run and second real run unchanged, `existing`.

## Steps 5–7, frozen before observation (source read: `_record_and_initialize`)

| Step | Prediction |
|---|---|
| 5. remove `^IVG.Deploy("schema")` (an interrupted setup: tables, no record), dry run | report `inferred`; record still absent |
| 6. real run | report `inferred`; record `Graph_KG` restored; tables/routines/classes as after step 2 |
| 7. engine with `schema_prefix="W21Other"` | `IVGSchemaError` (record names another schema); snapshot unchanged |
