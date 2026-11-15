# O-1: operator scope clarification on the pinned fixtures (recorded 2026-11-14, after the account switch)

**Clarification (operator, verbatim essentials).** Deploying the existing pinned upstream fixture's unchanged 4.5.1
release into its isolated migration-test namespace, and the unchanged repository `IVGDev` test helpers into this
dedicated experiment instance, are authorized verification setup. The broad ban on all compilation was an operator
precaution; these existing test fixtures need no further approval. Record the exact versions, namespaces, classes and
effects; retain the historical incident records; correct any result that lacks the required attribution. This
authorizes test setup, not repairs to the product or weakened oracles. The assessment of the current source stays at
the product pin. Review conditions other than O-1 still need their own evidence.

This answers review conditions R2-07 / O-1 (`review/REVIEW-2.md`, `REVIEW-3.md`, `REVIEW-4.md`). Historical records
are kept unchanged: `incidents/NAMESPACES.md` (IVG262FC1306 row), `fc1306/RESULT.md` "Scope notes",
`validation/SUITES.md` "Upstream side effects", `incidents/IVG460SNAP.md`.

## What the two setups left (live, read-only inventory `o1-fixture-inventory`)

Method: `$System.OBJ.ExportUDL` of each class into the container's `/tmp` (copied out, then removed; nothing compiled
or written in IRIS), compared by `incidents/o1/compare_classes.py` with the pin's sources and with git tag `v4.5.1`
(`f60b20c20de13bffb30c2fbb9cdb3a4e73f3a675`). Normalization: whitespace and blank lines, the deploy-time
`Parameter SOURCEHASH` value, and the schema names the pin's `schema_prefix` deploy rewrites (`Graph_KG`, `Graph.KG`,
`RAG`).

| Setup | Version | Namespace | Classes | Effect |
|---|---|---|---|---|
| `IVGDev` helpers, compiled by the suites' own `scripts/dev/tcp_setup.ensure_helper` (validation lane, first seen after `docs-1`) | pin `3eaa79cf` (`scripts/dev/objectscript/IVGDev/Run.cls`, `Setup.cls`; last changed in 87438b30) | `%SYS` | `IVGDev.Run`, `IVGDev.Setup`: both equal the pin's files | make and drop scratch namespaces over TCP for the suites (`tcp_setup.make_namespace`/`drop_namespace`); every namespace they made is listed in `incidents/NAMESPACES.md` |
| v4.5.1 release built by the pinned fixture `scripts/fixtures/build_release_namespace.build('v4.5.1', 'IVG262FC1306', schema_prefix='RAG')`, then the pin's own `initialize_schema(schema_prefix='RAG')` (fc1306 lane, 2026-11-14 01:51:59-01:52:28 UTC) | v4.5.1 = `f60b20c2`; pin = `3eaa79cf` | `IVG262FC1306` (database `/usr/irissys/mgr/ivg262fc1306/`) | 251 non-% classes: 54 equal the pin's sources; 8 exist only in v4.5.1 (`Graph.KG.BenchFormat`, `Graph.KG.Benchmark`, `User.CypherFn`, `User.Exec`, `User.SQL`, `User.funcJSONKEYS`, `User.funcSTRSPLIT`, `iris.vector.graph.GraphOperators`); 11 carry a pin name with text equal to neither tree (v4.5.1's schema classes `Graph.KG.LedgerRevision`, `Graph.KG.LedgerStats`, `Graph.KG.Meta`, which the pin compiles into the schema's own package instead, and formatting-only differences); 178 are IRIS-generated | 7 legacy revisions in `Graph_KG.ledger_revisions` from v4.5.1's `engine.ledger.commit`; the pin's upgrade copied them (`ledger_history_copied` 7); the probe then erased and redacted tenant T through the pin's public API |

## Attribution corrections

- F-C1306 (`fc1306/finding.json`, `findings/audit/followup.json`): the evidence is from a namespace that holds the
  pin's classes **and** v4.5.1 residue. The finding is about the pin's upgrade path (the pin's `initialize_schema`
  copies v4.5.1's rows and the pin's redaction misses the legacy table), so the residue is the intended precondition
  of the test, not a confound. Attribution now stated on the record (see its `notes`).
- WS-OBL-066 (`writesets/DISCHARGES.json`, `depends_on: ["O-1"]`): its evidence `fc1306-legacy-ledger-rows` is now
  authorized setup; the cell keeps its live grade with this record cited.
- The validation suites' results that ran with `IVGDev` present in `%SYS` (from `docs-1` on) are unaffected: the
  helpers equal the pin's own files.

## Not covered by O-1

Compiling anything else (new or modified classes, other releases, the audit's own helpers) stays out of scope. The
native executor compiling generated plan classes at run time (trace-replay cell 09) is the product's own behaviour,
not a fixture, and is not claimed under O-1. It was exercised later as product operation in AUDITC (steer 9: 7 generated
`IVGC.*` classes, 111 compiles, all removed again by the product's `Gen.DropAll`; `tr-replay-09-r2`, `tr-locklog-09`,
`trace-replay/TRACE-REPLAY.md`).

## IVG262CAP under O-1 (operator application, 2026-11-14 22:42 UTC)

**Operator (verbatim essentials):** O-1 also covers IVG262CAP when it uses the existing pinned migration/capacity fixture to
deploy the unchanged upstream 4.5.1 release into that isolated namespace; this is the same attributed verification setup,
and no further confirmation is needed. The unchanged product pin and the separately recorded historical fixture remain the
assessment inputs. (The orchestrator had first used the fixture there on its own reading of O-1 and asked for this
confirmation; that history is kept in git and `review/REVIEW-5.md` R5-06.)

| Item | Value |
|---|---|
| Version | upstream release v4.5.1 = git tag `v4.5.1`, commit `f60b20c20de13bffb30c2fbb9cdb3a4e73f3a675`, unchanged; then the pin `3eaa79cf`'s own `initialize_schema()` upgrade |
| Fixture | `scripts/fixtures/build_release_namespace.build('v4.5.1', 'IVG262CAP')` at the pin, called unmodified by `structural/upgrade/upgrade_probe.py build` (19:36:44-19:36:56 UTC); it creates the namespace with `scripts/dev/make_scratch_namespace.py` and runs its setup through `scripts/dev/tcp_setup.py` |
| Helper classes | `IVGDev.Setup` and `IVGDev.Run` in `%SYS` (already present from the validation suites; equal to the pin's `scripts/dev/objectscript/IVGDev/*.cls`, `o1-fixture-inventory`); nothing else compiled by the audit |
| Namespace | `IVG262CAP`, database `/usr/irissys/mgr/ivg262cap/`, absent beforehand (checked), kept, never dropped (`incidents/NAMESPACES.md`) |
| Effects | v4.5.1's own setup compiled v4.5.1's classes (165 non-% classes after the build); content loaded through v4.5.1's API (110,058 nodes, 230,054 edges, 320,064 properties, 2,002 vectors, 51 ledger revisions; `st-live-cap-upgrade-load`); the pin's upgrade (dry run, a run killed mid-way, the completing run; `st-live-cap-upgrade-run`); afterwards 222 non-% classes: 55 equal to the pin's sources, 8 v4.5.1-only, 11 v4.5.1 schema classes or formatting differences, 148 generated (`o1-cap-inventory`) |
| Used for | 3.6-capacity/01 (the pin's upgrade of a loaded 4.5.1 namespace); the assessment is of the pin's code |

| Setup | Version | Namespace | Classes | Effect |
|---|---|---|---|---|
| v4.5.1 release built by the pinned fixture `scripts/fixtures/build_release_namespace.build('v4.5.1', 'IVG262CAP')` (default schema `Graph_KG`), called unmodified by `structural/upgrade/upgrade_probe.py build` (19:36:44-19:36:56 UTC) | v4.5.1 = `f60b20c2` | `IVG262CAP` (database `/usr/irissys/mgr/ivg262cap/`) | 165 non-% classes after the build (85 `Graph.KG.*`, 37 `User.*`, 2 `IVG.*`, 1 `iris.vector.*`, 40 generated `INFORMATION.SCHEMA.*`; `$RUN_DIR/structural/upgrade/build.json`) | content written through v4.5.1's own API (`structural/upgrade/load451_child.py`: BulkLoader.load_networkx, bulk_create_nodes/edges, bulk_create_edges_temporal, store_embeddings, ledger commits), then the pin's own `initialize_schema()` upgrade (dry run, a run killed mid-way, the completing run) for 3.6-capacity/01; the namespace then holds the pin's classes over v4.5.1 residue; kept, never dropped |
