# Setup's schema record across a namespace's lifecycle

Product `3eaa79cf`, unchanged. Iteration 19 (cloud continuation): the different underserved workflow tested before any
convergence claim. Predictions frozen before native observation in
[setup-lifecycle-PAIRS.md](../../../uplift/consolidated/iteration-19/setup-lifecycle-PAIRS.md). Owners:
[install.setup](../../../ontology/concepts/install.g5.md#install.setup), `.dry_run`, `.resume`.

## What the model decides

`decide` transcribes `SchemaMixin._record_and_initialize`'s record transitions from the namespace's recorded schema and
the schemas holding IVG tables: a record naming another schema is refused; a matching record is `existing`; no IVG
tables is `new`; tables only in this schema is `inferred`; tables elsewhere is `explicit` if the caller named the schema
and refused otherwise. `setup` writes nothing on a dry run or a refusal; a real run creates this schema's tables and
writes the record last. `interrupted` is a real run stopped before the record.

## Theorems (7, all new; no imports)

`theorem_dry_run_writes_nothing`, `theorem_refusal_writes_nothing`, `theorem_fresh_namespace_is_new_and_recorded`,
`theorem_second_run_existing_and_unchanged`, `theorem_mismatch_refused`, `theorem_interrupted_setup_resumes` (inferred,
then the same end state as an uninterrupted run) and `theorem_other_schema_needs_a_name`. Tables, routines and classes
are abstracted to "this schema's objects"; privileges, grants, legacy objects, vector widths and class compilation
failures are outside. No `assume`, `admit` or `external_body`.

## Controls and binding

Four controls, all EXPECTED_FAIL full and isolated: `dry-run-writes`, `mismatch-adopts`, `unrecorded-tables-new`,
`unnamed-other-schema-recorded`.

The [binding](../../results/setup_record/) compares the port with two recorded native runs on a fresh namespace `W21`
created inside the run-isolated fixture: dry/real/dry/real, then record removed followed by dry/real, then an engine
naming another schema. 28 comparisons, AGREES. Three of four rule mutations are detected; the explicit-name case
(tables in another schema) was not observed, so `unnamed-other-schema-recorded` has formal but no native
distinction. Every predicted step held, including the resume and the mismatch refusal ("Nothing was written").
