# A-platform: install, schema, upgrades and platform boundaries (stage A intent notes)

Worker A-platform, product pin `3eaa79cf` (v4.7.0 `fabf4fae` + checklist). This worker was read-only on the product, ran no tests and did not touch IRIS. Three parallel sub-readers covered (a) HTTP/GraphQL/Bolt/MCP auth, (b) FHIR, snapshot and bulk load, and (c) Arno routing and algorithms. A-platform spot-checked their headline claims (Bolt BEGIN/COMMIT no-ops, GraphQL `executeCypher` as a Query field, the raw-cursor path in `api/routers/cypher.py`) against the source.

Tags: **(H)** human requirement or answered question; **(D)** accepted design decision; **(O)** observed implementation only; **(P)** proposed improvement. All commits have one author name, so "Tom's decision" is recorded secondhand in spec or commit text. It is treated as (H) only when the spec records it as a clarification answer, and as (D) otherwise.

## Scope and sources inspected

| Locator | Revision / date | Authority | Inspected portion | Follow-up |
|---|---|---|---|---|
| `docs/adr/0016-one-ivg-schema-per-namespace.md` | `7eb62f3a`, 2026-11-03 (unchanged since) | D (accepted) | all | Text is stale against the shipped design (see F-S9). |
| `specs/262-ivg-owned-sql-schema/spec.md` | `b76e7f87` clarifications 2026-11-03; amended `be6cd07c` 2026-11-07; "Implemented in 4.6.0" | H (Clarifications Q/A, US3 "Tom's requirement"); D (FRs) | all | none |
| `specs/262-…/plan.md`, `data-model.md`, `research.md` R1/R3 | 2026-11-03..07 | D | plan; data-model state machine; research R1, R3 | R4/R6 (grants, manifest) only skimmed |
| `specs/240-alt-migration-as-data`, `specs/241-alt-single-graph-backfill` | `b38b537b`/`9b7bb810`, `996aed7a`, 2026-10-12 | D (local design notes) | spec and plan | The status lines say "not adopted" and "Draft", but both are merged at the pin (F-S10). |
| `CONTEXT.md` glossary (IVG Schema, namespace) | pin | D | lines 13-31 | none |
| `CHANGELOG.md` v4.6.0–v4.7.0 | 2026-11-07..12 | D / O | 4.7.0 header and upgrading sections (lines 1-60, 488-560); 4.6.0 summary (550-560, 933-990) | Earlier versions not read |
| `docs/ADMIN_GUIDE.md` | pin | D (operator contract) | 17-35, 60-72, 100-130, 330-355, 495-540, 785-800 | Privilege tables §3 were read by sub-reader (a) |
| `docs/KNOWN_ISSUES.md` | pin | D / O | 677-690 (Arno named graphs), 734-760 (`^NKG` procedures), 785-835 (interrupted setup, 2.x upgrade, snapshots) | none |
| `iris_vector_graph/schema_name.py` | pin | O | all 540 lines | none |
| `iris_vector_graph/_engine/schema.py` | pin | O | 2097-2420 (setup entry, record transitions, dry-run plan), 2440-2475, 2576-2740 (deploy, reply) | `_initialize_schema` body 2475-2575 only skimmed |
| `iris_vector_graph/_engine/class_deploy.py` | pin | O | all | none |
| `iris_vector_graph/schema.py` | pin | O | 2870-2935 (deploy entry and record refusal) | DDL and procedures body not read |
| `iris_vector_graph/engine.py` | pin | O | 290-420 (construction, first-access), 1742-1786 (capabilities), 1840-1892 | none |
| `iris_vector_graph/_engine/legacy.py`, `legacy_manifest.py`, `legacy_bodies.py`, `_engine/admin.py` 378-441 | pin | O | `present_legacy_objects`, `copy_grants`, `copy_ledger_history`, `remove_legacy_objects`, status schema | `grant_read_path`, `revoke_legacy_arno` bodies skimmed |
| `iris_vector_graph/migrations/{__init__,_commit,upgrade,kg_node_stores,statements,docs_and_edge_vectors,temporal_structural_rows}.py`; `graph_scoped_embeddings.py` 270-295, 720-760 | pin; `51c51217` 2026-11-10 last | O | as listed | `graph_scoped_embeddings.py` placement logic not read |
| `capabilities.py`, `status.py` | pin | O | all of `capabilities.py`; `status.py` dataclasses | none |
| Auth surfaces: `api/main.py`, `api/routers/cypher.py`, `api/gql/schema.py`, `iris_vector_graph/{_api_key,api_auth,bolt_server,cypher_api,gql}`, `cypher/read_only.py`, `SqlPrivilege.cls`, `MCPTools/MCPToolSet/MCPService.cls`, `Service.cls` 12-75; `specs/release-4.6.0/{plan,tasks}.md` R097–R115 | pin | D (R-rows, ADMIN_API), O | via sub-reader (a); A-platform re-read `bolt_server.py:496-512`, `api/gql/schema.py:98-165`, `api/routers/cypher.py:100-170`, `api/main.py:20-80`, `Service.cls:12-75` | `src/iris_fraud_server`, `api/gql/core` not read |
| FHIR, snapshot and bulk load (spec 235, `fhir_bridge.py`, `fhir_links.py`, `_engine/fhir*.py`, `FHIRGraph*.cls`, `api/routers/fhir_event.py`, `Snapshot.cls`, `_engine/snapshot.py`, `bulk_loader.py`) | pin | see section | via sub-reader (b) | see section |
| Arno and algorithms (specs 210, 236, `_arno_gate.py`, `arno_readers.py`, `docs/dev/arno-reader-proof.json`, algorithm classes, `algo_cache.py`) | pin | see section | via sub-reader (c) | see section |
| Tests (classified, not run): `tests/unit/test_schema_name.py`, `test_remove_legacy_objects.py`, `test_migration_statements.py`; `tests/e2e/test_262_{record,upgrade_451,two_engines,not_upgraded,alt_schema_paths,…}.py`; `tests/conftest.py` 215-280, 1440-1490 | pin | evidence | test names, fixtures and key assertions | none |
| `experiment/g5-verus/run-community-redaction.py`, `environment.sh` | `203fd4b8` | experiment harness | all | none |

## Capabilities

### C1. One IVG Schema per namespace: choose, record, refuse

**Governing statements**

- (D) Every SQL object IVG creates lives in one schema per namespace, `Graph_KG` by default. The schema is chosen by `schema_prefix=`, else `IVG_SCHEMA_PREFIX`, else the default. "The first `initialize_schema()` in a namespace records the name … An engine that asks for a different name in a namespace that already has one is refused with an error naming both" (ADR-0016:11). The rationale: `^KG`, `^NKG` and `^IVG.*` belong to the namespace, so "two IVG schemas in one namespace would share one adjacency index and one ledger" (ADR-0016:17).
- (H) US3 is "Tom's requirement" (spec 262:107). The clarifications record the human answers (spec 262:40-45): grants are copied; renaming is out of scope; a 5% speed budget; and a not-yet-upgraded namespace raises one error on first access, running nothing else.
- (D) FR-003…FR-009 (spec 262:236-257). FR-004 validates the name before any DB call. FR-005 records it on first setup. FR-006 requires a mismatch to raise naming both "on its first database access, before any write". FR-006a refuses an unrecorded or un-upgraded namespace. FR-009 covers inference and refusal for 4.5.x namespaces.
- (D) The data-model state machine (data-model.md:20-36) has these states: absent → recorded(name) on a new namespace; inferred when IVG tables are in exactly the engine's schema; refused when they are in another single schema; refused with counts when they are in several and no name was given; recorded(S) with the others reported when S is named. recorded(S) plus an engine on T leads to an error with nothing written.
- (D, supersedes ADR wording) Research R1 says the ObjectScript classes never read the record. The deploy rewrites class sources for the schema before compiling, to keep embedded SQL within the 5% budget (research.md:8-30; plan.md:11-13; `schema_name.py:6-7`). ADR-0016:11 still says "the ObjectScript classes read it there".
- (D) The record is `^IVG.Deploy("schema")`, with `^IVG.Deploy("schema","recorded")` = "<UTC> UTC <version>" (research R3, data-model.md:18).
- (O) The name check is `[A-Za-z][A-Za-z0-9_]*`, refuses `%…` and `SQLUser`, and refuses any package equal to or under `Graph.KG`, `IVG` or `IVGC`. `graph_kg` in any case canonicalizes to `Graph_KG` (`schema_name.py:143-164`). ADR-0016:11 says `[A-Z][A-Z0-9_]*`; FR-004 and the code agree on mixed case.

**Operations**

- **Name resolution:** `IRISGraphEngine.__init__` → `resolve_schema_name` (`engine.py:298`, `schema_name.py:167-173`). `_schema_explicit` is True when an argument is given or the environment variable is non-empty (`engine.py:297`).
- **First-access check:** at construction (`engine.py:375-378`) → `_check_namespace_schema` (`engine.py:1847-1866`) → `check_first_access` (`schema_name.py:220-235`).
  - With a record, the check passes on a case-insensitive match and otherwise raises `mismatch`.
  - With no record, it probes `^oddDEF(<pkg>.funcCYCMP)` for the engine's spelling and its upper case. If that is absent, `_why_not_current` classifies the namespace as `not_upgraded` (a legacy-manifest class is present), `setup_unfinished` (IVG classes, tables or `^KG`/`^IVG.Deploy` are present), or `never_set_up` (`schema_name.py:249-267`).
  - A refusal installs a `FirstAccessCheck` on `conn` (`guarded_connection`, `schema_name.py:356-373`) and wraps every public method of the engine and its store (`engine.py:385-390, 414-416`; `schema_name.py:322-348`).
  - The exempt methods are `initialize_schema`, `status`, `remove_legacy_objects` and `close` (`schema_name.py:377`).
  - A record that cannot be read, for any non-`IVGSchemaError` exception, is logged at WARNING and **the check is skipped** (`engine.py:1862-1866`; documented for roles lacking `%Native_GlobalAccess`, ADMIN_GUIDE:515-518).
  - Non-IRIS connections are never checked (`schema_name.py:270-283`).
- **Setup:** `initialize_schema(dry_run, rewidth)` (`_engine/schema.py:2097-2161`) first refuses a caller transaction (2152-2156, 4.7.0), then runs `_record_and_initialize` (2198-2326):
  - It reads the record (2222) and raises on mismatch before anything else (2224-2225).
  - It computes `held` from `INFORMATION_SCHEMA` (`_ivg_table_schemas`, 2173-2196) and derives `how` ∈ {existing, new, inferred, explicit} or raises `unrecorded_schemas` (2229-2242).
  - It runs `refuse_package_clash` (2243). For a dry run it plans and returns (2248-2273).
  - A real run refuses a width change (2275-2280) and runs `_initialize_schema` through `in_schema` (2281-2286). That step does the table DDL, routines, and the class deploy (2578-2595, best-effort).
  - It then runs the Arno wrapper replace and revoke, the grant copy, the read-path grants and the ledger-history copy (2294-2308).
  - **`write_record` only if no record existed** (2309-2312), then `conn.commit()` (2313).
  - `_schema_check_passed` releases the guard (`engine.py:1874-1885`).
- **Deploy-side refusals:** `GraphSchema.deploy_objectscript_classes` calls `refuse_other_record` before the rescue probe (`schema.py:2878-2888`). `deploy_packaged_classes` calls it again before loading (`class_deploy.py:355-357`). The test fixture `_deploy_objectscript` refuses a non-`Graph_KG` record (`tests/conftest.py:233-239`).
- **Other readers of the record:** `/health` in `api/main.py:39-66` (503 on no record or a mismatch; 4.7.0) and `status()` (`_engine/admin.py:396-441`).

**Outcome-changing cases**

1. **Fresh namespace, default name:** "new" → recorded `Graph_KG`.
2. **Fresh namespace, `IVGALT`:** all objects go in `IVGALT` and no `Graph_KG` schema is created (US3, `test_262_alt_schema_paths.py`).
3. **Recorded `Graph_KG`, engine `RAG`:** refused at construction, and every public call raises (`test_262_record.py`).
4. **4.5.1 namespace with tables only in `RAG`:** an engine on `RAG` is inferred; an engine on `Graph_KG` (unnamed) is refused naming `RAG`.
5. **Tables in two schemas, no name given:** refused with counts and nothing recorded (`test_262_record.py:194-206`). With a name given: recorded "explicit", the other schema's rows untouched (`:223-245`).
6. **Interrupted first setup:** the marker exists but there is no record. The next engine on the same schema **is accepted** without a record. `status()` reports "setup has not finished" (`admin.py:433-439`), and re-running setup "inferred" records it (`test_262_upgrade_451.py:315-344`; KNOWN_ISSUES:787-807).
7. **Interrupted first setup on S, then an *explicitly named* T:** `held={S}`, `how="explicit"`, T is recorded while `^KG`/`^IVG.*` already hold S's data (see F-S3).
8. **Two first setups at once with different names:** no lock between 2222 and 2312 (F-S1).
9. **A reading role without `%Native_GlobalAccess`:** the mismatch check is skipped with a WARNING (ADMIN_GUIDE:515-518).
10. **Name case:** `ivgalt` vs recorded `IVGALT` compares equal (`same_schema`, `schema_name.py:138-140`). The deploy rewrite, however, uses the engine's spelling (`_engine/schema.py:2219`; `class_deploy.py:318`) (F-S6).
11. **Migrations build their own engine and waive the check**, a mismatch included (F-S2).

**Tests**

- Unit, mocked: `tests/unit/test_schema_name.py` (11 tests: name rules, environment precedence, package rule). It has no case covering a recorded upper-case schema used from a lower-case engine.
- Live IRIS (e2e, scratch namespaces): `tests/e2e/test_262_record.py` (record, infer, refuse, explicit; deep before/after snapshots); `test_262_not_upgraded.py`; `test_262_two_engines.py` (two namespaces, two schemas, one process); `test_262_upgrade_451.py` (frozen 4.5.1 DDL, interrupted upgrade via the `_UPGRADE_HOOK` seam at `_engine/schema.py:2287-2290`); `test_262_alt_schema_paths.py`, `test_262_alt_schema_fhir.py`, `test_262_inventory.py`.
- Not found: any concurrency test for setup.

**Seed-claim check.** No `index.md` seed is about the IVG Schema. The "Graph scope" seed (ADR-0003 key derivations) belongs to A-structure. The schema boundary confirms the CONTEXT.md premise that the namespace, not the schema, is the isolation unit (CONTEXT.md:15-18, 20-24). **Confirmed** as a design statement.

### C2. Class deploy, Community Edition and capability detection

**Governing statements**

- (D) Setup compiles only what the server can run. A class with `[Language = python]` needs embedded Python; a class naming `%AI.*` needs `%AI`; dependants of a skipped class are skipped transitively. "Everything else works without them" (ADMIN_GUIDE:335-353). Spec 262 edge case: "Classes skipped because the server lacks embedded Python or `%AI` keep being skipped, and the inventory says so" (spec 262:222-223).
- (O) The skip logic is `select_classes` (`class_deploy.py:78-106`). `upload_and_compile` skips on an unchanged fingerprint plus all classes compiled (213-226, 241-243).
  - It kills `^IVG.Deploy("fingerprint")` before loading and sets it only after a clean compile (255, 295-296).
  - It compiles functional-index types first and `SqlProcs` last (267-293).
- (O) A deploy failure is **best-effort**. `initialize_schema` records the failure in `warnings` and `objectscript_failed` and carries on (`_engine/schema.py:2578-2595, 2731-2738`). The schema record is still written (2309-2312).
- (O) `IRISCapabilities` holds 4 booleans, detected once per engine and cached (`capabilities.py:9-15`; `engine.py:1742-1760`). `graphoperators_deployed` probes `iris.vector.graph.GraphOperators`, a class 4.6.0 retired (FR-015; manifest entry). On a 4.6+ namespace it is True only where that legacy class was left behind (`schema.py:2837`).
- (O) `GraphSchema.last_deploy` is a class attribute (`schema.py:2908-2921`). Concurrent setups in one process share it.

**Community Edition path**

- (D) On IRIS Community 2026.1, which has embedded Python and no `%AI`, setup skips exactly `Graph.KG.MCPTools`, `MCPToolSet` and `MCPService` (ADMIN_GUIDE:349-353). A grep at the pin confirms that only these three sources name `%AI` (`MCPService.cls:3`, `MCPToolSet.cls:5,13`, `MCPTools.cls:3`), and no other class names them.
- **Capability lost on Community:** the IRIS-hosted MCP tool surface (`CypherQuery`, `RunSQL`, `LoadGraph`, `GraphStats`, `PPRWalk`, `EvidenceSearch`). IVG's Python, HTTP and Bolt servers, the algorithms, the ledger, erasure and redaction all compile.
  - `Graph.KG.Service`, `PyOps`, `Communities`, `PageRankEmbedded` and `IVG.CypherEngine` need embedded Python, so they would be lost only on a server without it (ADMIN_GUIDE:343-348).
  - Community's core cap is a deployment premise, not a code path: it shuts down above its licensed cores (ADMIN_GUIDE:66-69).
- (O) The upstream session fixture `tests/conftest._deploy_objectscript` loads every `.cls` unconditionally, one at a time, and raises on any failure (`tests/conftest.py:215-261`). On Community the three MCP classes fail, so the suite cannot start. `experiment/g5-verus/run-community-redaction.py` replaces only that fixture with `engine.initialize_schema()`. Its pass condition is schema `Graph_KG`, no `objectscript_failed`, and no "failed" warning (lines 35-42).
  - The two paths differ. `initialize_schema` loads with `-d`, then `CompileList` over the rewritten sources, and records `^IVG.Deploy("fingerprint")` and the schema record. The fixture loads with `ck-d` and records `^IVGDeployed(ns,file)`.
  - Neither difference changes ledger semantics. A later run of the upstream fixture in the same namespace would still redeploy every class, because `^IVGDeployed` is absent.

**Tests:** `tests/e2e/test_262_inventory.py` (live; inventory versus ADMIN_GUIDE, including the skipped table). The skip selection is unit-tested by source-shape tests (not enumerated here). No Community-specific CI test was located beyond `.github/workflows/quickstart.yml`, which ADMIN_GUIDE:27 cites.

### C3. Upgrade of an existing namespace (4.5.x → 4.6+), legacy objects and grants

**Governing statements**

- (H, clarification) Grants on legacy objects are copied to the replacements, and the dry run lists them (spec 262:42).
- (H, clarification) A 4.6 engine on an un-upgraded namespace raises one error on first access and runs nothing else (spec 262:45).
- (D) FR-010: legacy objects stay in place and working, with a single log line. FR-010a copies grants. FR-010b adds read-path grants on every setup. FR-010c (Tom 2026-11-04, R293) revokes EXECUTE on the 4.5.x `SQLUser.ivg_arno_*` wrappers from all but `%All`.
- (D) FR-011/012: `remove_legacy_objects(dry_run=True)` lists exactly the frozen-manifest objects present and changes nothing; `dry_run=False` removes exactly those, never by pattern (spec 262:263-265). ADR-0016:25 says "5.0 removes them on upgrade". ADR-0016 calls the function `remove_legacy_sql_objects`; the code and spec say `remove_legacy_objects`.
- (D, 4.6.3 refinement, CHANGELOG:501-510) A manifest name is not enough: an object counts as IVG's only when its body, query or class source fingerprint matches a text some release shipped (`legacy_bodies.py:1-10`). Others are listed with `ivg_owned=False` and kept.
- (D) FR-014: compiled native plans built against 4.5.x names are discarded on upgrade (live test `test_262_upgrade_451.py:282`).
- (D) Spec edge case: an upgrade interrupted between creating objects and writing the record "resumes on the next `initialize_schema()` and ends in the same state" (spec 262:210-211). KNOWN_ISSUES:787-807 documents the window in which the engine accepts the namespace before the record exists.

**Operations**

- `present_legacy_objects` (`_engine/legacy.py:112-175`) reads `INFORMATION_SCHEMA.ROUTINES/VIEWS` in `SQLUser`, `%Dictionary.ClassDefinition` (with a Native fallback), fingerprints the texts, and reads grants in one query.
- `copy_grants` (248-276) issues `GRANT … ON <schema>.<replacement>`, with identifiers checked by regex. GRANT is idempotent, so a re-run re-grants.
- `copy_ledger_history` (606-646) runs `INSERT … SELECT` from `Graph_KG.ledger_*` into `<schema>.ledger_*` only when the target is empty. A second run copies nothing.
- `remove_legacy_objects` (`_engine/admin.py:378-394` → `legacy.py:654-686`) refuses a caller transaction when not a dry run. It runs `DROP VIEW` / `DROP FUNCTION` with a fall-back to `%SYSTEM.OBJ.Delete` of the class, one delete per class. There is no transaction: the DDL and class deletes are individually durable, and `conn.commit()` follows at 685.
- The leftover notice is INFO, logged once per namespace per process (`legacy.py:710-719`).

**Outcome-changing cases**

- An application's `SQLUser.CY_MINE` is never listed (US2 s4).
- An operator's re-installed `SQLUser.JSON_VALUE` is listed `ivg_owned=False` and kept (`test_463_legacy_same_named_functions_e2e.py`).
- A class with several SqlProcs is deleted once, and the result is reported per item (see F-S4).
- A partial failure of `remove_legacy_objects` leaves the rest removed. A re-run lists what remains, so the operation is idempotent by re-listing.
- A namespace upgraded 3.2.0 → 4.x → 4.6 must end where a direct 4.5.1 upgrade ends (`test_262_upgrade_451.py:419-434`, live).

**Tests**

- Live: `tests/e2e/test_262_upgrade_451.py` (frozen 4.5.1 DDL; dry run writes nothing; grant copied; role runs Cypher before and after; native plan gone; removal exact; interrupted resume), `test_460_legacy_manifest_{400,320_loader}_e2e.py`, `test_463_legacy_same_named_functions_e2e.py`.
- Unit, mocked: `tests/unit/test_remove_legacy_objects.py` (fake world; no case for a failed class delete), `test_legacy_manifest.py` and `test_legacy_bodies.py` (regenerate and compare), `test_460_r293_legacy_arno_wrappers.py`.

### C4. Data migrations (3.2.0 → 4.0.0) and step commits

**Governing statements**

- (D) Each migration "must be re-runnable and reportable" and never deletes a vector or guesses a graph (`migrations/__init__.py:1-21`).
- (D) `upgrade_to_4_0_0` runs four ordered steps: embeddings, docs, edge_vectors, kg_node_stores. A step is guarded "when re-running it would *decide* something again, not merely do work again" (`upgrade.py:17-32`).
- (D) FR-011 (spec 230) as restated in `kg_node_stores.py:21-36`: flat `^KG` node stores are killed and rebuilt by the single server-side writer `Graph.KG.TraversalBuild`. No entry's graph is inferred.
- (D, 4.7.0 row 3b, `51c51217`) A refused commit rolls the step back and raises naming the migration. Every entry refuses a caller's open transaction (`_commit.py:1-35`; CHANGELOG:39-40).
- (D, local design notes) Spec 240 says statements are declared as data and run through `run_statement`, with no SQL, parameter or commit-point change (spec 240:47-48). Spec 241 adds a constant-UPDATE backfill only when exactly one non-NULL graph exists and there are no orphan child rows, with a fallback otherwise (spec 241:57-63). Both are merged (`9b7bb810`; `996aed7a` is an ancestor of the pin), despite their status lines.

**Operations and commit boundaries**

- `upgrade_to_4_0_0` (`upgrade.py:130-202`) runs each step through `_run_step_body` (250-292). The docs and edge-vector steps are skipped by catalog shape (`_docs_already_migrated` 379-402: `graph_id NOT NULL` and no staging table; `_edge_vectors_already_migrated` 405-419). `_tune` + `commit_step` follow (205-218).
- Docs and edge vectors (`docs_and_edge_vectors.py`):
  - `prepare_*` and `finish_*` run their statement lists through `_run_tolerantly`. Errors whose text contains any of `already`, `not unique`, `-201`, `not found`, `does not exist`, `-30>` or `-315` are treated as done (89-97, 647-657). One commit happens at the end of each list.
  - The finish sequence is: staging create → copy placed rows → `DROP TABLE docs` → rename staging (`statements.py:257-264`).
  - A crash between the drop and the rename is resumed: `place_documents` detects the staging table when `docs` is absent (`docs_and_edge_vectors.py:294-300`).
- `rekey_kg_node_stores` (`kg_node_stores.py:113-187`):
  1. Refuse a caller transaction.
  2. Check the sources declare `graph_id`.
  3. Recompile the shipped `Graph.KG` classes (not the package), then repair iFind and require the entry points. All three happen before the kill (159-168).
  4. Kill four `^KG` subtrees (175-176), then call `BuildKG`, `Build2HopStats` and `Build2HopExactStats` (178-180), then commit (182).
  - The kill and rebuild are Native-API global operations outside any SQL transaction. A crash between them leaves those stores empty, and a re-run is the recovery path ("a kill followed by a deterministic rebuild", `upgrade.py:27-30`).
- Migrations construct their own engine and **waive** the schema check: `graph_scoped_embeddings.py:287-288` and `temporal_structural_rows.py:85-89` → `engine._waive_schema_check()` (`engine.py:1887-1890`).

**Outcome-changing cases:** a second run of a finished upgrade (the docs and edge steps are skipped; embeddings report state; the `^KG` step redoes the same work); a crash after the drop and before the rename; a crash after the `^KG` kill; a 2.x install (`blocked_because` in a dry run; KNOWN_ISSUES:810-824 quarantine); a non-default schema (the `schema=` argument covers only the placements; the embeddings step uses the engine's schema, from the environment or the default).

**Tests:** `tests/unit/test_migration_statements.py` (mocked, recording connection). The live 3.2.0 and 4.5.1 upgrade cases are in `test_262_upgrade_451.py` (419-434). The commit message of `996aed7a` mentions a live equivalence test for spec 241; it was not located by name here.

### C5. Authentication and authorization boundaries: HTTP, GraphQL, Bolt, MCP, SQL

**Governing statements**

- (D) The API key is opt-in through `IVG_API_KEY`; unset or empty means authentication is off on every server (`.env.sample:4-7`; ADMIN_GUIDE:823-842; `_api_key.py:21-23`; origin `ce337194`, spec 196, a directory no longer in the tree).
- (D, R097 `3607f957`; R112 `81a9bb33`) With the key set, every route is default-deny. Only `/health`, `/docs`, `/redoc` and OpenAPI are public, matched exactly on the routed path, including under a `root_path` or mount (CHANGELOG 4.6.0:994-1000; `docs/ADMIN_API.md:30-63`). (D, Tom 2026-11-04, `specs/release-4.6.0/plan.md:51`): `/browser` stays behind the key.
- (D, R098) The key may arrive as `X-Api-Key` or `Authorization: Bearer`. It is compared in constant time over UTF-8 bytes, and every candidate is compared (`_api_key.py:26-54`).
- (D, R111 `9cb11913`) Bolt: the key is the HELLO credentials (Bolt 4/5.0) or LOGON (5.1+). Nothing runs before authentication. A failed re-LOGON de-authenticates, and RESET does not restore it (`bolt_server.py:459-565`).
- (D, R107 `37506b46`) `IVG_READ_ONLY=true` is server-wide, with no per-key scopes. It blocks (1) write methods under `/admin/` except `/admin/explain`, (2) Cypher writes on REST, the Neo4j HTTP routes, GraphQL and Bolt, and (3) `/fhir-event` unless `IVG_ALLOW_FHIR_WRITES=true` (`api_auth.py:126-187`; ADMIN_API:66-79).
- (D, R113 `847aef28`, R115 `33fad069`; H secondhand: "reported privately", `060c3f59`, `specs/release-4.6.0/plan.md:17`) One parser rule decides a write (`writes_cypher`, `cypher/read_only.py:61-104`). Text that does not lex or parse fails closed. A keyword inside a string or comment is not a write.
- (D, R280 `d3a86fcd`, R289 `99508f6d`) The privilege boundary for global readers is the database resource. SQL-callable functions that read or write a global first check SELECT, INSERT or UPDATE on the table that global stands for (`Graph.KG.SqlPrivilege.RequireSelect/RequireWrite`, `SqlPrivilege.cls:18-84`; `%All` passes). Native-API class methods do not check, by design (ADMIN_GUIDE §3:600-616).
- (D) The MCP tools are for a trusted client: `RunSQL` runs any SQL and `LoadGraph` reads any server file (ADMIN_GUIDE:631-635, 787-791).
- (D, R131/R147) `Graph.KG.Service.CreateWebApp` grants one read-only role `IVG_KG_<NS>`, with password auth (`AutheEnabled=32`), and resets an application an earlier release made with `MatchRoles ":%All"` (`Service.cls:12-75`).
- (O) The default IRIS credentials are `_SYSTEM`/`SYS` everywhere. Only `api/main.py:21-36` warns. `cypher_api.py:170` and `cli.py:47` read `IRIS_USERNAME`, while `.env.sample:30` and `api/main.py:27` use `IRIS_USER`.

**Operations (entry → guard → executor)**

- `cypher_api` (`ivg server start`, default bind `0.0.0.0:8200` plus Bolt on 7687): CORS `*` → `ApiKeyMiddleware` → `ReadOnlyMiddleware` (`cypher_api.py:97-117`).
  - `/api/cypher` and `/db/{db}/query/v2` check the write verdict, then `_run_cypher`, then `engine.execute_cypher` (`write_txn` + `_ledger_check`, `_engine/query.py:1946-1967, 2300`).
  - `/db/neo4j/tx/commit` checks every statement first, then runs each as a separate `_run_cypher` (`cypher_api.py:380-404`).
  - Admin: `/admin/schema/init`, `/rebuild`, `/embed`, `/load`, `/snapshot`, and `DELETE /admin/queries/{id}` → `%SYSTEM.SYS.KillProcess` on any PID (`cypher_api.py:578-703`).
- `api.main` (sample app): `ApiKeyMiddleware()` and `ReadOnlyMiddleware()` with no write prefixes (`api/main.py:120-124`). `/api/cypher` runs translator SQL on a **raw cursor** with its own `START TRANSACTION`/`COMMIT` (`api/routers/cypher.py:130-166`). GraphQL `executeCypher` is a **Query** field (`api/gql/schema.py:98-165`) on the same raw path. A-platform re-read both.
- `iris_vector_graph.gql.create_app`: key only (`gql/__init__.py:47-52`). Its `cypher` field checks read-only and then calls `engine.execute_cypher` (`gql/resolvers.py:136-147`).
- Bolt:
  - BEGIN, COMMIT and ROLLBACK only answer SUCCESS (`bolt_server.py:500-510`; A-platform re-read), and each RUN commits through `execute_cypher` (567-578).
  - The `mode:"r"` access mode is ignored.
  - A per-session engine and IRIS connection is never closed (400-425, 936-960).
- MCP (`%AI` builds only): the policy is `%AI.Policy.ConsoleAudit` only (`MCPToolSet.cls:12-14`). `CypherQuery` writes with no read-only flag (`MCPTools.cls:9-29`). `RunSQL` runs arbitrary SQL (34-69). `IVG_READ_ONLY` does not apply.

**Outcome-changing cases**

- Key unset or empty: off. Whitespace: on.
- Two headers, one wrong: accepted (`any()`).
- `/health/` is not public, only `/health`.
- Behind a mount, `/ivg/admin/load` is gated as `/admin/load`.
- Bolt 5 HELLO without credentials: SUCCESS, then RUN is refused until LOGON.
- A `tx/commit` list with one write runs nothing.
- A `;`-joined text with any write is refused. `EXPLAIN CREATE` is refused.
- Under read-only, reads still write caches and plans (`^IVG.AlgoCache`, `IVGC.*`, `^KG("degc")`; ADMIN_GUIDE:557-574).
- `tx/commit` where statement 2 fails: statement 1 stays committed.
- Bolt BEGIN, CREATE, ROLLBACK: the CREATE stays.

**Tests**

- Mocked or unit: `tests/unit/test_r097_api_key_every_route.py` (enumerates routes), `test_api_security.py`, `test_r112_root_path.py`, `test_r097_bolt_auth.py`, `test_r111_bolt_logon.py`, `test_r107_cypher_api_read_only.py`, `test_r113_read_only_one_rule.py`, `test_r115_read_only_verdict_independent.py`, `test_read_only_bypass.py`, `test_460_r280_sql_readers_check_select.py`, `test_460_r289_sql_writers_check_write.py` (source-shape).
- Live IRIS: `tests/e2e/test_read_only_bypass_e2e.py`, `test_460_r222_server_key_and_version_e2e.py` (real uvicorn), `test_460_r280_*`, `test_460_r289_*`, `test_460_r279_*`, the role rows `test_460_r202_reading_role_e2e.py`, `test_460_r050_select_only_role_e2e.py`, `test_460_r311_{writer_role,trust_boundary}_e2e.py`; `tests/integration/test_mcp_tools.py` (needs `%AI`, so it cannot run on Community).
- Not found: Bolt BEGIN/ROLLBACK semantics, `tx/commit` partial failure, a GraphQL GET write, MCP under read-only, Bolt connection cleanup.

**Seed-claim check:** none of the `index.md` seeds is in this area.

### C6. Algorithms and Arno Native Reader routing

**Governing statements**

- (D, spec 236 FR-001/003/006/008/014a; CONTEXT.md:254-276) A Native Reader answers only when all of these hold:
  - the algorithm is one of {pagerank, ppr, wcc, cdlp, subgraph};
  - the loaded library reports an integer Reader Revision ≥ the proof file's `min_revision` for it;
  - the call is on the default graph.
  - Otherwise the **Owner** (ObjectScript) answers.
  - The library version string is never used for routing (FR-004).
  - A missing or invalid report or proof means no Native Readers.
  - A native failure partway through is answered by the Owner, logged.
  - Betweenness always uses its Owner (FR-006).
  - The spec's status line still says "Draft" although it shipped in v4.2.0 (`9d64a715`).
- (D, spec 236 FR-016–FR-020, research R2) The algorithm cache is scoped per graph (`GraphKey.ForIndex`, the ADR-0003 adjacency form), keyed by algorithm and parameters, and validated against `^KG("__version")` on every read. Every write moves the token. "Nothing stale is ever returned" (Story 4).
- (D, superseded) Spec 210 FR-001's shared `^ArnoAccel("dllid")` handle was reverted to per-process handles by `f99fc6ff` (v4.6.0).
- (O) The proof `docs/dev/arno-reader-proof.json` (`f99fc6ff`, 2026-11-01) proves **only `pagerank`**, at min_revision 2 on library 1.2.1, with one arm64 sha. ADMIN_GUIDE:653-656 agrees. Before R104 (`47ffe202`, v4.6.0) wheels shipped no proof, so everything ran on the Owner.
- (O) Native Readers run only in namespace `USER` (`iris_sql_store.py:883-890`; `ArnoAccel.cls:241-246`). Every other namespace, which per ADR-0016 is the isolation unit, always uses the Owner. Spec 236's open question on this is unresolved.

**Operations**

- `route()` is pure: in scope, `graph` empty, a proof entry exists, and `readers.get(alg,0) >= minimum` with an int check (`arno_readers.py:257-280`; A-platform re-read it).
- `_arno_route` adds the library availability probe and the USER check (`iris_sql_store.py:883-893`).
- `_native_answer` catches every exception and treats an empty answer as Owner (896-909).
- PageRank: `kg_PAGERANK` (`_engine/algorithms.py:741`) → `store.execute_pagerank` (2362, cached) → native only with no edgeless nodes (2394) → `PageRankNativeJson` (`ArnoAccel.cls:258`), else Owner `PageRank.PageRankGlobalJson(pGraph=0)`. On a store error the engine calls the Owner again (`algorithms.py:797-804`).
- PPR takes `graph`, and a named graph routes to the Owner (2231-2318). WCC, CDLP and subgraph are default-graph only, with Owners hard-coding `pGraph=0`.
- Cache: Lookup `H<tok>|payload` or `M<tok>`; compute; `Put` with the token read before computing (`AlgoCache.cls:5-51`; `iris_sql_store.py:921-988`). PageRank also keys on a node-set token (R313).
- Validation of the proof is all-or-nothing (`arno_readers.py:132-136, 193-197`). The proof is cached per process.
- `_arno_available` is fixed for the store's lifetime (`iris_sql_store.py:991`).

**Outcome-changing cases:** proof absent, invalid, or naming an out-of-scope algorithm; report `{}`, below, at or above the minimum; USER vs another namespace; default vs named graph; a default graph while a named graph has edges; multigraph mode; edgeless nodes; PPR options (bidirectional, exclude, limit); a native answer that throws, is empty, is malformed, or is well-formed but wrong; a library reloaded under a new `lib_path`; a write and rollback interleaved with a cache fill.

**Tests**

- Mocked: `tests/unit/test_236_reader_routing.py` (its reload case resets the report by hand), `test_236_proof_file.py`, `test_236_reader_gate.py`, `test_236_cache_keys.py`.
- Live: `tests/integration/test_236_algo_cache.py`, `test_236_token_write_paths.py` (a rolled-back bump is not undone, but no entry is computed mid-transaction), `test_236_capabilities.py`.
- e2e: `tests/e2e/test_236_reader_gate.py` skips unless `IVG_REQUIRE_ARNO=1`. Gate fixtures cover USER only, a single graph, no multigraph and no edgeless nodes.

**Seed-claim check.** "Graph scope: … a scoped operation must use the correct derivation" (index.md). The algorithm cache uses the adjacency derivation `GraphKey.ForIndex` (`AlgoCache.cls:30, 48, 56`), so this is **confirmed for the cache**. "Adjacency and degree: a cached value may be served only while its generation is current" (index.md, ADR-0012). The AlgoCache analog is **not established** under an uncommitted write then rollback (F-A1).

### C7. FHIR bridge: graph sync and `/fhir-event` ingestion

**Governing statements**

- (D, spec 235 Clarifications 2026-09-26/27, `specs/235-fhir-graph-interpretation/spec.md:39-131`)
  - Compartment edges are re-derived on every re-sync and removed on delete.
  - "Erase, snapshot/restore and verify treat them as ordinary edges."
  - A stale per-graph `interpretation_version` triggers one full re-derivation.
  - FHIR is not a separate install: `FHIRGraph.cls` reaches `HS.*` only dynamically, so it compiles but sits idle on Community.
  - The `fhir_*` tables are created lazily, only where `HS_FHIRServer.Repo` exists (`_engine/fhir_graph.py:190-216`).
  - The spec status line says "Draft", although it shipped in 4.1.0.
- (D, `FHIRGraph.cls:13-21`; `docs/FHIR_GRAPH.md:250-286`)
  - Each batch of keys is resynced and its watermark advanced in **one transaction**, and a failure rolls back both.
  - A key resync reads only current repository state, so it is idempotent.
  - Rebuild and any sequence of syncs converge.
  - One sync, rebuild or reinterpret runs per graph at a time.
- (D) A FHIR graph is always a named graph `fhir:<ns>:<pkg>`; the default graph is refused (`_engine/fhir_graph.py:43-61`; `FHIRGraph.cls:1715-1717`). `Open` derives `GraphKey.ForName` and `ForIndex` (1719-1720), consistent with ADR-0003.
- (D) `/fhir-event` was deprecated in 4.1.0, with removal planned for 5.0 (`api/routers/fhir_event.py:11-14`). Its origin, spec 195 (`22f3e509`), is **unavailable**: no `specs/195-*` exists in history.

**Operations**

- **Sync.** `engine.fhir_graph_sync` (`_engine/fhir_graph.py:255-258`) → `FHIRGraph.SyncOnce` (543-625).
  - It takes `Lock +^IVG.FHIRGraph(graph):0`, or answers `busy`.
  - A stale interpretation leads to `Rederive`, which commits per batch, then `SetInterpVersion`.
  - Per feed, `RunBatch` (1923-1979) runs `TSTART` → `ResyncKey`… → `UPDATE fhir_graphs SET <wm>` → fault hook → `TCOMMIT`.
  - Writers: dynamic SQL on IVG tables. Adjacency is written through the `AdjIndex` functional index or `Adjacency.Put/Remove`, both of which bump `^KG("gen")` and `__version`. `^KG("label")` is written directly in `EnsureNode`, `SyncProps` and `DropNode` without a `__version` bump.
- **Rebuild** (448-538): definition sync commits every 200 rows; there is one transaction per stale drop; the watermarks reset at the end. It is not atomic as a whole, and the next sync replays.
- **Ledger.** There is no ledger call in `FHIRGraph.cls` or `_engine/fhir_graph.py`, and the strict check is Python-only (`_engine/ledger.py:72-87`). **(O) FHIR sync writes are never recorded in the ledger and strict mode does not refuse them.**
- **`/fhir-event`** (`api/routers/fhir_event.py:283-365`) runs a per-event engine `IRISGraphEngine(conn)` (275) → `create_node(fhirUrl, …)`, create-if-absent (`_engine/nodes_edges.py:1028-1031`) → optional `create_node(patientRef)` → `create_edge_temporal(patient, TYPE, fhirUrl, ts, upsert=True)` → background embedding.
  - Each call is its own transaction; there is no transaction across the steps.
  - `ts = time.time()` when `date` is absent or unparseable (209-211, 236-237).
  - Auth is the key middleware only. `IVG_READ_ONLY` blocks the route unless `IVG_ALLOW_FHIR_WRITES=true` (`api_auth.py:166-171`).

**Outcome-changing cases (idempotency and scoping)**

- **Duplicate event with a `date`:** idempotent, because the temporal upsert lands on the same `(s,p,o,ts)`.
- **Duplicate event without a `date`:** a new temporal edge each second, so it is **not idempotent**.
- **Updated resource:** the first write wins for code properties, and a second temporal edge is added at the new date.
- **No delete event:** a deleted resource's node is never removed.
- **Node identity:** it is the client's `fhirUrl` text, so a relative and an absolute URL make two nodes.
- **Partial failure:** the node is written, the edge fails, and the call returns 500. A retry converges only with a stable date.
- **Strict ledger:** the event returns 500.
- **Sync crash before commit:** nothing is written (live-tested).
- **Concurrent syncs:** the second gets `busy`.
- **User edge written into a FHIR graph from a FHIR key:** it is deleted at the next resync of that key.
- **`erase_graph` and Python writers:** they do not take `^IVG.FHIRGraph(graph)`.
- **Erase of a FHIR graph:** resets the watermarks and `interp_version`, so the next sync re-derives (`Eraser.cls:1163`).

**Tests**

- Live, IRIS for Health only (namespace IVGFHIR): `tests/e2e/test_231_fhir_graph_sync_e2e.py` (idempotent, crash-before-commit, busy, sync == rebuild, erase), `test_fhirgraph_failures_e2e.py`, `test_470_snapshot_fhir_e2e.py`, `test_235_lazy_fhir_tables_e2e.py`, `test_262_alt_schema_fhir.py`.
- Live on Community: `tests/integration/test_fhir_event_sidecar.py` (asserts only "≥1 edge" on a duplicate).
- Mocked or source-text: `tests/unit/test_fhir_event_sidecar.py`, `test_231_fhir_event_deprecation.py`, `test_252_fhir_graph_leaves_adjacency_to_the_index.py`.
- Not found: FHIR sync with the ledger enabled or strict.

### C8. Snapshot export and import

**Governing statements**

- (D, ADR-0004 and `_engine/snapshot.py:87-207`) `Graph.KG.GraphStores.Inventory()` is the one store inventory. `STORE_PLAN` maps each store to sql, global or derived, with a reason for each derived store. The live inventory comparison is `tests/integration/test_snapshot_inventory.py`.
- (D) ADMIN_GUIDE:980-1010: a snapshot "is not a backup". It omits `^IVG.Deploy` (so the **schema record is not carried**), `^IVG.CypherGen`, `^EmbedQueue`, `embedding_quarantine` and `kg_NodeEmbeddings_optimized`.
- (D) USER_GUIDE:1151-1153: "`restore_snapshot` empties the namespace's graphs and loads the archive; `merge=True` adds to what is there instead". The docstring says merge "keeps what is there and inserts rows that are not" (`snapshot.py:1082-1093`).
- (D, 4.6.0 R271/R276) An unreadable table or global raises `SnapshotReadError` and no archive is written. A failed table commit raises, naming what was already committed. Restore is **not atomic as a whole** (`_commit`, 1205-1216). The replace path's `erase_all` is one transaction (`Eraser.cls:709-818`).
- (D, 4.7.0 row 26) Configuration tables are matched on their primary keys: replace overwrites, merge keeps (`snapshot.py:280-297`).

**Operations and fidelity**

- Export reads `SELECT *` with row-id and computed columns dropped (`snapshot.py:868-879`; A-platform re-read). It covers the core tables, FHIR, configuration, embeddings and routed tables, every `^KG` subtree marked "global", `^BM25Idx`, `^IVF`, `^PLAID`, `^VecIdx`, `^NKG`, the whole `^IVG.Ledger` plus ledger class storage, `^IVG.GraphMode` and `^IVG.TemporalStructural` (387-410).
- Derived stores (`gen`, `degc`, `degw`) are skipped and killed for every graph whose out/in the restore wrote (1686-1691). out, in and label are skipped when the adjacency index is declared, because the row inserts rebuild them (1662-1665).
- **Version token:** `_raise_kg_version` and `_raise_nkg_version` run in a `finally`, so `^KG("__version")` ends past both the pre-restore value and the archive's (48-58, 1585-1588). This is live-tested (`tests/integration/test_236_token_write_paths.py`).
- **Format:** `metadata.version = "1.1"` and `layout = "graph-scoped"` (838-862). Only `layout` is checked, and its absence is accepted (1117-1124). `version` and `ivg_version` are never checked.
- **Scoping:** whole namespace only. There is no graph parameter on save or restore; replace runs `erase_all`, which keeps `^IVG.Ledger("rec")`, the head and the meta (`Eraser.cls:810-812`). `save_snapshot` takes no lock or transaction, so it is not a point-in-time read under concurrent writers (O).
- `runs_in_ivg_schema` rewrites the snapshot's fixed SQL for the engine's schema by swapping `self.conn` (`schema_name.py:512-527`).

**Outcome-changing cases**

- replace vs merge;
- an empty vs a populated target;
- an archive older than the live ledger;
- a multigraph graph restored into an indexed namespace;
- an archive with NULL `graph_id` (translated to `''`, 1255-1256);
- an unreadable table at save time;
- a failure mid-restore;
- two `/admin/snapshot` calls in the same second (file named by the second, `cypher_api.py:672-673`; KNOWN_ISSUES:826-833: the default directory is the temp dir).

**Tests**

- Live: `tests/integration/test_snapshot_*.py`, `tests/e2e/test_470_snapshot_*`, `test_upgrade_snapshot_restore_e2e.py`. Several `test_snapshot_deep.py` cases skip on any exception.
- Mocked: `tests/unit/test_snapshot*.py`. The merge tests check node counts only (`tests/unit/test_snapshot.py:180-189`).
- The only ledger round trip purges first (`tests/integration/test_ledger_snapshot.py:47-55`).

**Seed-claim check.** "Live erasure … failure rolls back" (ADR-0004) is **confirmed only for the replace step's `erase_all`**. The restore that follows is not atomic, by design (R276). Graph scope: snapshot has no graph scoping at all, so the seed's derivation concern does not arise. Restore must, however, reconcile the multigraph mode (F-B2).

### C9. Bulk load (`BulkLoader`)

**Governing statements**

- (D/O) The module docstring (`bulk_loader.py:1-22`): it bypasses per-row overhead (functional index, FK checks, subquery dedup) with `%NOINDEX %NOCHECK` (`use_noindex=True` by default), then runs `%BuildIndices` and `BuildKG`/`BuildNKG`.
- (D, spec 230 FR-003/FR-005) One loader writes one graph, and the default graph is written explicitly as `''` (61-70, 180-190).
- (D, 4.7.0) The loader refuses a caller transaction, commits per batch, and raises `BulkLoadError` on a real refusal. Duplicates are skipped "because re-loading the same data has to stay idempotent" (97-103, 164-171; USER_GUIDE:300-302).
- (D) ADR-0011: `Adjacency` is the only out/in writer. The bulk path complies indirectly, through `AdjIndex` and `TraversalBuild.BuildKG`.

**What it bypasses (the brief's question)**

- **Ledger: bypassed.** `BulkLoader` takes a raw connection and never calls `ledger_check`, so strict mode does not refuse it (O). The engine's `bulk_load_session` does check.
- **Adjacency, degree generation and version token: not maintained during the `%NOINDEX` inserts.**
  - They are restored by `rebuild_all_indices` (484-507). Its `PurgeIndex` runs `Adjacency.RemoveAll`, which kills out, in, gen, degc and degw **for every graph** and bumps `__version` (`Adjacency.cls:452-473`). `InsertIndex` then calls `RowPut` per row.
  - `build_graph_globals` (512-534) follows, with `BuildKG`, `BuildNKG` and `Build2HopStats`, all namespace-wide.
  - Between the purge and the end of the re-insert, readers of every graph see partial adjacency. Only `BuildKG` holds `BeginRebuild`'s lock (`Adjacency.cls:814-823`).
  - A caller of `load_edges` who skips the rebuild leaves rows invisible to index reads (docstring 393-395).
- **Graph scoping:** rows and scans are scoped; the rebuilds and `^NKG` are namespace-wide.
- **Temporal:** not applicable.
- **IVG Schema:** `schema="Graph_KG"` is a constructor default (41, 54-58), and `rebuild_all_indices` names `Graph.KG.rdfedges/rdflabels/rdfprops/nodes` whatever `schema=` says (495).

**Tests**

- Live: `tests/integration/test_bulk_loader_live.py`, `test_bulk_loader_endpoints.py`, `tests/e2e/test_470_*`.
- Mocked: `tests/unit/test_230_bulk_loader_graph.py`, `test_bulk_loader_index_rebuild.py`.
- Not found: ledger strict mode, degree or token after a load, resumption, multigraph, or an alternative-schema `%NOINDEX` load.

**Seed-claim check.** ADR-0011 "one writer module" is **confirmed in mechanism**: `%BuildIndices` → `AdjIndex` → `Adjacency`. ADR-0012 "cached degree served only while current" is **confirmed for the purge**: `RemoveAll` kills `degc`. The index seed's "Edge identity … mode off compatible" does not hold for bulk load in multigraph mode (F-B5).

## Candidate obligations for formal modeling

1. **O-SCHEMA: one recorded IVG Schema per namespace.**
   - **L1:** a namespace's recorded schema, once written, never changes. No engine, deploy or migration writes rows or globals for a schema other than the recorded one. With no record, at most one schema's setup may ever become the record. Every refusal leaves rows and globals unchanged (FR-005, FR-006, FR-009, SC-006).
   - **L2:** the data is `^IVG.Deploy("schema")`, the per-engine `FirstAccessCheck{pending}`, the `held` map from `INFORMATION_SCHEMA`, and the marker `^oddDEF(<pkg>.funcCYCMP)`. The guards are the constructor check, the mismatch check in setup, `refuse_other_record` in both deploy entries, and the `/health` probe. The write is `write_record` after the DDL, deploy and grants, committed by `conn.commit()`. No lock is held.
   - **L3 bindings:** `schema_name.py:184-198, 220-267, 286-353`; `engine.py:375-416, 1847-1890`; `_engine/schema.py:2198-2326`; `class_deploy.py:341-367`; `schema.py:2878-2888`; `graph_scoped_embeddings.py:287-288`; `temporal_structural_rows.py:85-89`.
   - **Cases to represent:** two concurrent first setups (S≠T); an interrupted first setup then an explicit T; a migration's engine on T over a namespace recorded as S; Native API unreadable; case-variant spelling; tables in two schemas with and without a name.
2. **O-SETUP: setup is resumable and dry runs are pure.**
   - **L1:** a sequence of interrupted `initialize_schema()` calls followed by one complete call ends in the state one complete call reaches. A dry run changes nothing. A caller transaction is refused before any effect.
   - **L2:** many commits along the way (`_engine/schema.py` commits at 554…2701), a best-effort class deploy (fingerprint killed first and set last, `class_deploy.py:255, 296`), idempotent grants, a ledger-history copy only into an empty target, and the record written last.
   - **L3 bindings:** `_engine/schema.py:2097-2161, 2248-2313, 2578-2595`; `class_deploy.py:229-297`; `legacy.py:248-276, 606-646`.
   - **Cases to represent:** an interruption after each commit point; a deploy failure (the record is still written); a class compile failure on Community (skip, not fail).
3. **O-LEGACY: legacy removal is manifest- and fingerprint-bounded.**
   - **L1:** `remove_legacy_objects(dry_run=False)` removes only objects that are on the frozen manifest *and* whose text matches a shipped fingerprint, and reports truthfully what it removed. A dry run is pure. Nothing is removed implicitly on upgrade before 5.0.
   - **L2/L3:** `legacy.py:112-175, 654-686`; `admin.py:378-394`.
   - **Cases to represent:** an operator's same-named object; a class with several SqlProcs whose delete fails; a partial failure followed by a re-run.
4. **O-MIGRATE: 4.0.0 upgrade steps are re-runnable and never infer a graph.**
   - **L1:** re-running after any interruption reaches the uninterrupted end state. No vector or row is deleted unless it was moved to quarantine. `^KG` node stores come only from rows.
   - **L2/L3:** `upgrade.py:250-292, 379-419`; `docs_and_edge_vectors.py:89-97, 294-300, 647-657`; `statements.py:257-266`; `kg_node_stores.py:142-187`; `_commit.py:25-35`.
   - **Cases to represent:** a crash between the copy and the drop, between the drop and the rename, and between the kill and the rebuild; a statement error whose text matches the tolerated substrings.
5. **O-ROUTE + O-ALGOCACHE: native-reader routing and cache freshness.**
   - **L1:** native(alg) implies that alg is proven at or below the executing library's revision, the call is in the scope the proof covered (default graph, USER, parameters), and every native failure yields the Owner's answer. A cache hit equals the Owner's answer over the current committed graph.
   - **L2/L3:** `arno_readers.py:257-280`; `iris_sql_store.py:858-909, 921-988, 2318, 2394`; `AlgoCache.cls:18-51`; `Adjacency.cls` version bumps; `ArnoAccel.cls:141-169, 241-291`.
   - **Cases to represent:** a write then rollback interleaved with a fill; a reload to another library; a named graph with edges while the default graph is routed native.
6. **O-WRITE-SURFACE: every structural write path either goes through the ledger and read-only gates or is documented as exempt.**
   - **L1:** a strict-ledger namespace refuses an unrecorded structural write from any public surface. `IVG_READ_ONLY` refuses writes on every surface it claims.
   - **L3 bindings:** `api/routers/cypher.py:130-166`; `api/gql/schema.py:148-212`; `bolt_server.py:500-510, 567-578`; `cypher_api.py:380-404`; `MCPTools.cls:9-69`; `FHIRGraph.cls:1923-1979`; `bulk_loader.py:252-534`; `_engine/snapshot.py` restore.
   - **Cases to represent:** each surface crossed with {key off/on, read-only off/on, ledger strict}.

## Candidate findings

### Schema, install, upgrade (A-platform)

- **F-S1 SUSPECTED: concurrent first setups can both record, and the loser keeps working on its own schema.**
  - Expected (ADR-0016:11, FR-005/FR-006): the first setup records, and any other schema is refused.
  - Observed: `_record_and_initialize` reads the record (`_engine/schema.py:2222`), runs a long setup (ADMIN_GUIDE:102-103 measures 44-62 s and 667 round trips), and then calls `write_record` unconditionally if it saw none (2309-2312). There is no `LOCK` or compare-and-set.
  - Each engine's guard is released by `_schema_check_passed` and never re-checked (`engine.py:1874-1885`). Two processes on S and T in a fresh namespace both end "new", the record names whichever wrote last, and the other keeps writing to its own tables while sharing `^KG` and `^IVG.*`.
  - Distinguishing case: two concurrent `initialize_schema()` calls with `IVGALT` and `Graph_KG`. Expected: one raises `IVGSchemaError`.
  - Proposal (P): take `LOCK +^IVG.Deploy("schema")` around read, setup and record, and re-read the record before writing.
- **F-S2 SUSPECTED: `_waive_schema_check` also waives the mismatch refusal (FR-006).**
  - `graph_scoped_embeddings.py:287-288` and `temporal_structural_rows.py:85-89` build `IRISGraphEngine(conn)` with the schema from `IVG_SCHEMA_PREFIX` or the default, then call `_waive_schema_check()` → `_schema_check_passed()` (`engine.py:1887-1890`). That releases any refusal, a mismatch included. The intent recorded in the comment is only "may run before any 4.6.0 setup recorded the schema".
  - On a namespace recorded `RAG` with no environment variable, `backfill_structural_rows(conn)` would call `create_edge` (110) into `Graph_KG.rdf_edges` and the shared `^KG`. In FR-009's explicit two-schema case that table exists.
  - Proposal (P): waive only FR-006a (`record is None`), or build the migration engine with the recorded schema.
- **F-S3 SUSPECTED / open: an explicit second schema can be recorded over another schema's live globals.**
  - After an interrupted first setup on S (marker present, no record; KNOWN_ISSUES:787-807), an engine with an explicit T sees `held={S}` and records T as "explicit" (`_engine/schema.py:2229-2239, 2312`).
  - `^KG`, `^NKG` and `^IVG.Ledger` hold S's data. `kg_built` is already marked, so setup does not rebuild `^KG` from T's rows (`_engine/schema.py:2356-2361, 2673-2678`).
  - FR-009's "explicit" path was designed for 4.5.x namespaces. The spec does not say what happens to the namespace's globals.
  - Human decision: should "explicit" rebuild or clear the globals, or refuse while another schema holds a 4.6 marker?
- **F-S4 CONFIRMED (source alone): `remove_legacy_objects` misreports removal for the second and later SqlProcs of a class whose delete failed.**
  - `legacy.py:680-684`: when `cls in classes_done`, the item is set `removed=True` without consulting the first delete's result. FR-011 requires the report to be exact.
  - Fix (P): remember the per-class result.
- **F-S5 SUSPECTED / open: setup records the schema even when the class deploy failed.**
  - The deploy is best-effort (`_engine/schema.py:2578-2595`) and the record is written regardless (2309-2312).
  - The next engine is accepted and its writes fail with `GraphWriteError` (KNOWN_ISSUES:787-807, a similar symptom).
  - On a non-default schema whose earlier classes were compiled for `Graph_KG`, the classes keep naming `Graph_KG` while the record says otherwise.
  - Human decision: should a failed deploy withhold the record (FR-006a's "setup that stopped")?
- **F-S6 SUSPECTED: case-variant spelling.**
  - Spec 262:204-205 requires `ivgalt`/`IVGALT` to be "recorded and compared as one". Comparison is case-insensitive (`schema_name.py:138-140`).
  - The rewrite, deploy and `foreign_schema_classes` use the engine's spelling, not the recorded one (`_engine/schema.py:2219`; `class_deploy.py:204-209, 318`). A `schema_prefix="ivgalt"` engine on a namespace recorded `IVGALT` would load `ivgalt.SqlProcs` next to `IVGALT.SqlProcs`. The marker probe already hedges with `.upper()` (`schema_name.py:231-234`).
  - No test exists (`tests/unit/test_schema_name.py:52` covers `Graph_KG` only).
  - Proposal (P): canonicalize to the recorded spelling before rewrite.
- **F-S7 SUSPECTED (medium): the migration's tolerated-error list can swallow a failed copy before a destructive drop.**
  - `_run_tolerantly` treats any error whose text contains `not found`, `does not exist`, `already` and similar as done (`docs_and_edge_vectors.py:89-97, 647-657`).
  - `DOCS_FINISH` is copy → `DROP TABLE docs` → rename (`statements.py:257-264`). A `docs_copy_placed` failure such as "Field 'TEXT' not found" would be tolerated, and the source dropped.
  - Proposal (P): tolerate per statement name (for example, only `docs_staging_create` may hit "already exists").
- **F-S8 O / open: the first-access check is skipped silently for roles without `%Native_GlobalAccess` and for non-IRIS connections** (`engine.py:1862-1866`; `schema_name.py:270-283`). This is documented (ADMIN_GUIDE:515-518), so it is a design gap, not a bug. A pooled or proxied DB-API connection gets no check at all.
- **F-S9 doc drift (D vs O).** ADR-0016 still says "Status: Accepted (… implementation pending)", the regex `[A-Z][A-Z0-9_]*`, "the ObjectScript classes read it there", and `remove_legacy_sql_objects`. The shipped design (research R1, FR-004, the code) is source rewrite at deploy, mixed case allowed, and `remove_legacy_objects`.
- **F-S10 doc drift.** Specs 240 and 241 say "Exploratory (alternative implementation; not adopted)" and "Draft … not adopted", but `9b7bb810` and `996aed7a` are merged at the pin and shipped (241's shortcut is at `graph_scoped_embeddings.py:735-760`). Spec 235 and spec 236 also still say "Draft".
- **F-S11 simplification.** `IRISCapabilities.graphoperators_deployed` (`capabilities.py:15`; `schema.py:2837`) probes a class FR-015 retired. `GraphSchema.last_deploy` is process-global (`schema.py:2908-2921`). `runs_in_ivg_schema` swaps `self.conn` on a shared engine (`schema_name.py:512-527`), which is unsafe if an engine is shared across threads (as `cypher_api` does under `_engine_lock` only). A per-call rewritten cursor would preserve behavior.
- **F-S12 open.** The 4.0.0 migrations take `schema=` only for the placements. The embeddings step uses the engine's environment or default schema (`upgrade.py:145-152, 259-268`), and none of the steps consult `^IVG.Deploy("schema")`. Should migrations run against the recorded schema?

### Auth and access (sub-reader a; A-platform re-checked F-H1, F-H3, F-H4)

- **F-H1 SUSPECTED: Bolt transactions do not exist.** BEGIN, COMMIT and ROLLBACK answer SUCCESS only (`bolt_server.py:500-510`), and every RUN commits. A driver's `tx.rollback()` keeps the writes. This is not documented.
- **F-H2 SUSPECTED: `/db/neo4j/tx/commit` is not atomic.** Each statement is its own `_run_cypher` (`cypher_api.py:391-398`), so earlier writes survive a later failure.
- **F-H3 SUSPECTED: the `api.main` REST and GraphQL `executeCypher` paths bypass the engine.** They use a raw cursor (`api/routers/cypher.py:130-166`; `api/gql/schema.py:168-212`), so they skip `_ledger_check("cypher_dml")` (`_engine/query.py:2300`) and `write_txn`. A ledger-strict namespace accepts structural writes there.
  - Simplification (P): route both through `engine.execute_cypher(read_only=…)`, keeping the 413 hop cap and error redaction.
- **F-H4 SUSPECTED: a GraphQL GET can write.** `executeCypher` is a **Query** field (`api/gql/schema.py:98-165`), and Strawberry's `GraphQLRouter` is built without overriding `allow_queries_via_get` (`api/main.py:93`). With no key, a cross-site GET can run a `CREATE`.
- **F-H5 open: insecure defaults combine.** With no key, the server binds `0.0.0.0` for HTTP and Bolt and connects as `_SYSTEM`/`SYS`, a `%All` superuser. That exposes `/admin/load`, Cypher writes, and `DELETE /admin/queries/{pid}` → `KillProcess` on any PID. There is no warning in `cypher_api` or the CLI.
  - Also, `IRIS_USER` vs `IRIS_USERNAME` (F6 of sub-reader a): an operator following `.env.sample` silently connects as `_SYSTEM`.
  - Human decision: should the server refuse to start on a non-loopback host without a key?
- **F-H6 SUSPECTED: Bolt never closes per-session IRIS connections** (`bolt_server.py:400-425, 936-960`). On Community, with its license limits, this can exhaust connections.
- **F-H7 O: MCP has no read-only control.** `CypherQuery` writes and `RunSQL` runs anything (`MCPTools.cls:9-69`). `EvidenceSearch` documents a natural-language input but binds it as a node id (190-216). Open: should `IVG_READ_ONLY` cover MCP?
- **F-H8 O:** `kg_IVF` checks SELECT on a table named by `^IVF(name,"cfg","table")` (`SqlProcs.cls:141`), which a DB writer can redirect.

### Arno and algorithms (sub-reader c; A-platform re-checked `route` and `_arno_route`)

- **F-A1 SUSPECTED: the algorithm cache can serve a rolled-back graph.** A writer `TSTART` → `Adjacency.Put` (token T). A reader misses at T and computes over the uncommitted `^KG` (IRIS global reads are not isolated). It then `Put`s at T. The writer `TROLLBACK`s without a bump, so the entry stays "fresh". The degree cache avoids this with a writer lock and a no-wait probe (`Adjacency.cls:51-58`); AlgoCache has neither. This contradicts spec 236 Story 4.
- **F-A2 SUSPECTED: routing can use a stale reader report.** `ArnoAccel.IsAvailable` and `CallFn` reload silently when `lib_path` changes (`ArnoAccel.cls:141-169`), so `_reload_arno_if_needed` (`iris_sql_store.py:867`) never clears `_arno_reader_report`. The unit test resets it by hand (`test_236_reader_routing.py:258-268`). This violates the spec 236 edge case "report read again on the next load".
- **F-A3 open / SUSPECTED: native readers may read `^NKG`, which merges every graph.** The evidence conflicts:
  - `ArnoAccel.cls:255-256` says "reads the ^NKG export";
  - CONTEXT.md:267 says "Adjacency Index directly";
  - `TraversalBuild.cls:758-760`.
  - The native routes for pagerank, wcc, cdlp and subgraph have no `_named_graph_with_edges()` guard, unlike the R184 tiers (`iris_sql_store.py:3234, 3691, 3749`).
  - With pagerank proven and a named graph holding edges, a default-graph PageRank might count named-graph edges.
  - Human or live check: what does the 1.2.1 reader read?
- **F-A4 SUSPECTED (low): a cached PPR answer misses node creation.** PPR's key has no node-set token, so `[]` cached for a not-yet-existing seed survives `create_node(seed)`. R313 fixed this for PageRank only.
- **F-A5 CONFIRMED in code: capabilities and status misreport.** `ppr_arno`/`wcc_arno` and `rust_algorithms` come from a hard-coded list (`NKGAccelLoader.cls:99-127`; `iris_sql_store.py:2991-3000`), but only pagerank is proven and routed. The status "algorithms:" line prints capability keys (`status.py:325-331`). No status field shows the proof's validity or the per-algorithm route.
- **F-A6 open:** routing ignores the library build and platform (FR-004), while the proof holds one arm64 sha. Is a Reader Revision valid across platforms?
- **F-A7 open:** triangle count, SCC, k-core and Leiden use Arno via `arno_bridge` with no proof gate (`iris_sql_store.py:3737-3760, 3977-4000`). Does the evidence gate apply to them?
- **F-A8 simplification:** the engine re-calls the same Owner after the store's Owner failed, for PageRank, WCC and CDLP (`_engine/algorithms.py:797-804, 823-828, 845-849`). PPR raises instead (R127); make them uniform. The `Proof.from_dict` IN_SCOPE filter is dead code given the all-or-nothing validation.
- **F-A9 open:** Native Readers run only in `USER`, but ADR-0016 makes any namespace the isolation unit. A non-USER install never gets native routing (spec 236 open question).

### FHIR, snapshot, bulk load (sub-reader b; A-platform re-checked F-B1)

- **F-B1 SUSPECTED (high): a merge restore dedupes the core tables on the first exported column only.**
  - The generic merge guard is `WHERE NOT EXISTS (… WHERE {cols[0]} = ?)`, and `count += 1` runs regardless (`_engine/snapshot.py:1287-1298`; A-platform re-read).
  - For fresh-DDL `rdf_edges` (`schema.py:34-45`), `edge_id` is dropped at export (`snapshot.py:872-874`), so `cols[0]` is `graph_id`. The same holds for `rdf_labels`, `rdf_props` and `docs`. Merge therefore keeps at most one row per graph and reports every row as restored.
  - The v4.1.0 CHANGELOG (3926-3932) names this defect and fixed it only for `FHIR_TABLES`.
  - Distinguishing case: save two edges in G, `erase_graph(G)`, `restore_snapshot(merge=True)`. Expected: G has 2 edges.
- **F-B2 SUSPECTED: restoring a multigraph graph into an indexed namespace loses the keyed adjacency.** `erase_all` kills `^IVG.GraphMode`, and rows are restored before globals, so `RowPut` writes single-edge leaves. The keyed out/in are then skipped as index-derived (`snapshot.py:1234, 1554, 1662-1665`; `Adjacency.cls:484-487`). Spec 234 lists restore as not done.
- **F-B3 SUSPECTED / open: a replacing restore overlays the archive's ledger on the live ledger.** `erase_all` keeps `^IVG.Ledger("rec")`, the head and the meta (`Eraser.cls:810-812`), and the global import only sets values (`snapshot.py:1654-1692`). Should restore refuse or replace when a ledger is live? This is A-history's area.
- **F-B4 SUSPECTED: a failed global line is swallowed at debug** (`snapshot.py:1683-1684`). It is neither counted nor in `failed_rows`, which contradicts R271's intent.
- **F-B5 SUSPECTED: an interrupted `load_nodes` cannot be resumed.** Phase 1 commits node rows. A retry with `skip_existing=True` builds labels and props only for new nodes (`bulk_loader.py:299-314`), so the earlier nodes stay without labels or properties for good. This is against the "re-loading has to stay idempotent" promise (97-103).
- **F-B6 SUSPECTED: `BulkLoader` ignores the IVG Schema record.** Its default is `schema="Graph_KG"`, and `rebuild_all_indices` hard-codes `Graph.KG.*` classes (`bulk_loader.py:41, 54-58, 495`). In an `IVGALT` namespace, `%NOINDEX` rows stay unindexed or the wrong extent is rebuilt. This is ADR-0016's "followed by everything" unmet.
- **F-B7 O / open:**
  - BulkLoader bypasses the ledger, and strict mode does not refuse it.
  - `PurgeIndex` → `RemoveAll` empties every graph's adjacency mid-load, with no rebuild lock (`Adjacency.cls:452-473, 814-823`).
  - In-memory `(s,p,o)` dedupe means a multigraph graph silently gets no parallel edges.
  - Two concurrent loaders can insert duplicates under `%NOCHECK`.
  - Is BulkLoader single-writer, single-edge and ledger-exempt by design?
- **F-B8 open: FHIR sync is outside the ledger.** No strict check or record exists in `FHIRGraph.cls`. No source decides whether FHIR graphs are exempt.
- **F-B9 SUSPECTED: `/fhir-event` is not idempotent without `date`** (`ts = now`). An updated resource's codes never refresh, and there is no delete. The governing spec 195 is unavailable. Given the 5.0 removal, a human may drop the issue or make `ts` deterministic.
- **F-B10 O:** `FHIRGraph` writes `^KG("label")` directly, without a `__version` bump (`EnsureNode`/`SyncProps`/`DropNode`). Simplification (P): route the writes through `Adjacency.PutLabel/RemoveLabel` so the label index has one owner. Also open: `erase_graph` does not take `^IVG.FHIRGraph(graph)`, so it races a full re-derive.
- **F-B11 simplification:** `load_networkx` rebuilds adjacency twice (`rebuild_all_indices`, then `BuildKG` in indexed mode). One rebuild should give the same `^KG`; check by comparing `^KG` dumps and the `__version` delta.

## Not inspected / limits

- No tests were run and IRIS was not touched. Every SUSPECTED item needs a live distinguishing case, run by the orchestrator in the experiment's container. F-B1 and F-B2 depend on live `SELECT *` column order and restore order. F-A1 and F-S1 need interleavings.
- Not read: the body of `_initialize_schema` (2475-2575: DDL tolerance patterns, routines, iFind); `GraphSchema` DDL and procedure text; `legacy.grant_read_path`/`revoke_legacy_arno` bodies; `graph_scoped_embeddings.py` placement and quarantine logic (spec 227); `scripts/dev/gen_legacy_*.py`; `docs/migration/v4.6.0.md` beyond a grep; `src/iris_fraud_server`; `api/gql/core`; `FHIRGraph.cls` 1-447 and the concept and PPR methods; `Communities.cls`/`Centrality.cls` beyond a skim; the Arno library source; the snapshot routed-embedding restore (1371-1550); `import_rdf`/`import_graph_ndjson`.
- Unavailable: `specs/195-*` (origin of `/fhir-event`) and `specs/196-*` (origin of the API key). Only commit messages `22f3e509` and `ce337194` remain.
- The FHIR, snapshot, bulk-load, auth and Arno sections rest on sub-reader reports. A-platform re-checked their load-bearing lines but not every citation.
- The ledger-related findings (F-H3, F-B3, F-B7, F-B8) overlap A-history's ledger domain. The adjacency and degree findings (F-A1, F-B2, F-B7) overlap A-structure's. Reconcile them during integration.
