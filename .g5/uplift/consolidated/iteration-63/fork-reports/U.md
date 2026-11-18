# U report — operations/setup-and-upgrade (26 blocks)

Saved by the builder from the fork's final message. Fragment: 26 blocks complete, 106 obligations, 30 exclusions,
owner-updates empty; `merge.py` + `census.py --dir U/check` PASS.

## 1. Per block (f/p/a/u, excl)
access.defaults 0/0/3/0 (3); access.webapp 0/0/4/0 (1); install.namespace 0/0/1/0 (2); install.schema 0/0/2/0 (1);
install.schema.name 4/7/0/0 (0); .record 2/0/0/0 (2); .refusal 3/3/1/0 (2); .not_ready 5/0/2/0 (0); .existing
4/3/0/0 (1); .concurrency 4/0/0/0 (1); .classes_follow 0/0/2/0 (1); .speed 0/0/1/0 (1); install.setup 0/1/2/0 (3);
.dry_run 0/2/0/0 (0); .resume 1/3/0/0 (1); install.deploy 3/0/7/0 (1); .editions 0/0/2/0 (2); install.upgrade
0/1/5/0 (0); .grants 0/0/5/0 (0); .arno_revoke 0/0/2/0 (1); install.legacy 0/0/7/0 (2); .manifest 0/0/2/0 (0);
.ownership 0/0/2/0 (0); install.migration 0/0/6/0 (2); .steps 0/0/3/0 (1); .schema 1/0/0/0 (2). No structural zero.

## 2. Page totals
full 27, partial 20, absent 59, unassessed 0, total 106 (25.5%). Proved 36 (18 full scope, 18 narrowed); refuted 7
(full scope: install.schema.not_ready#o02, install.schema.existing#o04; narrowed: install.schema.concurrency#o01–#o04,
install.migration.schema#o01); bounded 0; unchecked 0; none 63. Full with no design check: install.schema.name#o02
("IRIS_SCHEMA_PREFIX is never read": the model's `resolve` has no such input; binding case `resolve:iris_prefix`).
Receipts (latest, fresh): install_lifecycle prove 20261117T072020Z, binding AGREES 20261117T072228Z and controls;
setup_record prove 20261116T171334Z, binding 20261116T171338Z; platform prove 20261116T160814Z and `s-*` controls;
native platform_schema_refusal (as expected), platform_schema_waiver (observed defect).
Exclusions 30: undecided-alternative 11, restatement 9, rationale 5, navigation 2, evidence-annotation 2, definition 1.

## 3. Grade sources: 40 reused, 6 changed, 60 new
Reused: install_lifecycle NOTES and decision-links (name rules, refusal, not_ready, existing, dry-run plan, deploy
fingerprint skip); setup_record NOTES (idempotence, dry run, resume, record); coverage.md platform rows (record under
serial setups, refusal changes nothing, unreadable-record skip, migration.schema "Violated").
Changed from coverage.md:
- install.schema.not_ready#o02: "Observed (upstream)" → full, refuted (`theorem_record_admits_without_objects`, bug-plt-133).
- install.schema.existing#o04: "Proved (transitions)" → full, refuted (`theorem_other_schema_needs_a_name`, control `explicit-refused`, bug-plt-026).
- install.schema.concurrency#o01–#o04: "Suspected violation" → full, refuted, narrowed (rule 3; modelled witnesses reach the record and the losing schema's writes; none probed natively).
Partial grades: deciding value is a model input (name pattern, IVG code-package membership, foreign-class clash,
guarded/exempt method sets); case-insensitivity is an abstraction; error texts not modelled; setup_record abstracts
rows, routines and grants.

## 4. Parents (no entailment claimed; open cases)
install.namespace#o01 — two schemas' engines in one namespace share ^KG/^NKG and ledger globals.
install.schema#o01 — a creator outside setup puts objects elsewhere (BulkLoader Graph_KG default bug-plt-012; legacy deployer).
install.setup#o01 — a repeated run re-creates routines (case-variant redeploy, bug-plt-015).
install.deploy#o01 — the skip rule drops a class the server could run.
install.deploy.editions#o01 — a non-skipped class fails to compile on one edition.
install.upgrade#o01 — a legacy function is redefined or dropped.
install.legacy#o03 — removing a multi-procedure class fails part-way (bug-plt-014).
install.migration#o01 — a re-run duplicates rows.

## 5. Restatements
No owner updates. Cross-fork: install.migration#x01 lead "They never delete a vector" → owner block search.quarantine
(S2) ("Placed plus quarantined vectors always equal the vectors it started with"). install.migration#o03 is counted here
and covers non-vector rows only.

## 6. Grade-source errors
1. coverage.md "Coverage gaps — Install" stale: says install.schema.name, install.setup*, install.deploy* not modelled; install_lifecycle (it. 56) and setup_record (it. 19) model them.
2. coverage.md not_ready row stale: "no separate theorem"; `theorem_unrecorded_reason_order` and `theorem_record_admits_without_objects` exist, the latter refutes the lead.
3. coverage.md existing row overstates "Proved": explicit name over one other schema is refuted (bug-plt-026).
4. coverage.md platform "Latest evidence" cites superseded prove receipt 20261114T002651Z; latest 20261116T160814Z.
5. NOTES of install_lifecycle and setup_record link owners at concepts/install.g5.md#…, which holds no canonical blocks.
6. design-verified tags overstate install.setup (0/3 full), install.setup.dry_run (0/2), install.setup.resume (1/4).
7. Ontology statements contradicted by evidence: install.setup bullet 1 ("not a partial install") vs its own metadata (objects created before the failing statement stay); install.legacy ("reports truthfully, per object") vs bug-plt-014; install.schema / classes_follow: BulkLoader ignores the schema (bug-plt-012, bulk_loader.py:41,56-60,495; owned by install.bulk_load.loader) and deploy rewrites class sources with the engine's spelling, not the recorded one (bug-plt-015); access.defaults correct for `ivg server start`, but sample api/main.py reads IRIS_USER and listens on 8000 (line 155).

## 7. Ranked uncovered
1. Upgrade grants and Arno revoke (security; no model): install.upgrade.grants#o01–#o05, arno_revoke#o01–#o02. EXECUTE only never table privileges; view grants reported not copied; read-path completion; revoke from everyone but %All holders. Bind _engine/legacy.py::copy_grants, revoke step, read-path grant in _engine/schema.py; observe privileges and dry-run plan.
2. Web application role (security; no model): access.webapp#o01–#o04. Bind Service.cls::CreateWebApp, ::EnsureWebAppRole, ::GrantWebAppSql; observe Security.Applications/Roles, a write through the application.
3. Legacy removal: install.legacy#o01–#o07, manifest#o01–#o02, ownership#o01–#o02 (bug-plt-014). Bind _engine/admin.py::remove_legacy_objects, legacy_manifest.py, legacy_bodies.py; observe removed/ivg_owned flags vs catalog.
4. Data migrations: install.migration#o01–#o06, steps#o01–#o03 (bug-plt-001). Bind migrations/upgrade.py::upgrade_to_4_0_0, migrations/_commit.py, kg_node_stores.py unplaced table; observe tables and ^KG after re-run or injected commit failure.
5. Deploy capability selection: install.deploy#o01–#o05, #o09, #o10, editions#o01–#o02. Bind class_deploy.py::select (_PY_METHOD, _AI_CLASS, dependency closure).
6. Upgrade of 4.5.x SQL: install.upgrade#o01–#o04, #o06 (copy_ledger_history); #o05 partial (fingerprint change → deploy → DropAll not composed).
7. Partly covered: install.schema.name#o03, #o05, #o06; refusal#o02, #o05, #o06 (FirstAccessCheck.guard_methods, EXEMPT_METHODS); install.setup#o02, #o03; dry_run create/grant/copy lists; other interruption points in resume#o01.
8. Server defaults: access.defaults#o01–#o03 (cli.py::server_start, cypher_api.py, bolt_server.py::start_tcp_bolt_server).

## 8. Iteration-60 residual mapping
Migrations: install.migration#o01–#o06, steps#o01–#o03, install.upgrade#o01–#o06 (migration.schema#o01 covered, refuted).
Install residue: install.upgrade*, grants*, arno_revoke*, install.legacy*, install.deploy#o01–#o05, #o09, #o10,
install.setup#o02–#o03, install.schema.speed. SDK/CLI/HTTP admin: access.defaults, access.webapp (admin routes belong
to concepts/access). Ledger "snapshot and upgrade survival": install.upgrade#o06 only.
Source-discovered omissions: sample API's 0.0.0.0:8000 bind (api/main.py:155); `ivg server start` has no
--iris-username option (cli.py:420-427); Bolt per-session IRIS connections never closed (metadata only); dry-run and
report shapes of individual migrations.

## 9. Limitations
Split granularity (11 for schema.name, 10 for deploy, 7 for legacy removal; error texts split from decisions);
concurrency refutations model-only; install.schema.record#o02 narrowed to serial setups; install.setup.resume#o02
("record last") holds by the model's definition only; nothing run (inspection = source reads at the pin; upstream-test
verdicts from coverage.md); install.legacy's legacy-deployer assumption graded absent without reading
scripts/deploy_production.py.
