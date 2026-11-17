# Register entries from iteration 56 Part B (install lifecycle) — for the integrator

Matched by trigger and observable consequence against `bugs_issues.md`, the 2026-11-15 audit record and KNOWN_ISSUES:
- the case-variant schema name is the inherited **bug-plt-015** (audit: inconclusive, not reproduced); it is now E2E
  reproduced with wider consequences, so its full entry replaces the span line
  `<span id="bug-plt-015"></span> [bug-plt-015: review record](audits/register-20261115/bugs-review.md#bug-plt-015)`;
- the explicit name beside one other schema is the inherited **bug-plt-026** (audit: inconclusive); now E2E
  reproduced, its full entry replaces the span line for `bug-plt-026`;
- new: **bug-plt-133** (Low; a KNOWN_ISSUES item with no register entry), **bug-plt-134** (Low), **bug-srch-116**
  (Medium). Allocated IDs bug-plt-135..140 and bug-srch-117..119 are unused.

Place bug-plt-015 and bug-srch-116 in the Medium section, the others in the Low section. Evidence paths are relative to
`.g5/Verus_verification/`. Binding receipt: `results/install_lifecycle/20261117T071614Z-binding/receipt.json` (AGREES 138, 20/20 mutations, tamper
detected); prove `results/install_lifecycle/20261117T071254Z-prove/receipt.json` (32 verified).

---

<a id="bug-plt-015"></a>
### An engine whose schema name differs only in case from the record re-declares empty vector columns unasked and loads the schema classes under its own spelling

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56); first recorded 2026-11-13 (the audit of 2026-11-15 found it inconclusive: [review record](audits/register-20261115/bugs-review.md#bug-plt-015))

Found by: install.schema.name metadata ("suspected divergence: the deploy rewrites class sources with the engine's spelling"); iteration 56 frozen pair A6 and the post-read source (`_vector_column_action` reads the width with `GraphSchema.get_embedding_dimension` under the engine's spelling; `rewrite_sources` renames the schema classes to it); [install_lifecycle](models/install_lifecycle/NOTES.md) `theorem_unknown_width_altered_unasked`, control `unknown-width-counted`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin (fresh namespaces; [probe](../uplift/consolidated/iteration-56/install/case_probe.py) → [observation](../uplift/consolidated/iteration-56/install/case-observed-20261117T070557Z.json); binding cases `D:*`, `B:x_lower_*`, `B:fingerprint_after_lower`, `B:x_setup_after_lower`). (1) I56SD: setup with `schema_prefix="I56W"` at width 8, one 8-wide vector stored. An engine `I56W` at width 16: setup raises `EmbeddingIdentityConflict` and nothing changes (passing neighbor). The same engine named `i56w`: the dry run lists all three vector tables under `alter` (the populated one included), and setup succeeds with no warning and no `needs_manual_migration`; afterwards `kg_EdgeEmbeddings` and `kg_NodeEmbeddings_optimized` are declared 16 while the registry still records 8 for them, and the populated `kg_NodeEmbeddings` stays 8 with its vector (IRIS refused that ALTER). (2) I56SB, record `I56X`: setup by an engine named `i56x` reports `objectscript_failed` for `i56x.LedgerRevision`, `i56x.LedgerStats`, `i56x.SqlProcs` (ERROR #5092: name conflict with `I56X.…` differing only in case), re-creates all 58 routines, and clears the deploy fingerprint; the next setup by the `I56X` engine compiles every class and re-creates 58 routines again. The projected procedure and Cypher kept answering (neighbors). Engines named in either case are accepted, as documented.

Expected: names that differ only in letter case are the same schema ([install.schema.name](../ontology/concepts/install.g5.md#install.schema.name)), so setup behaves as with the recorded spelling: an empty column at another width is refused without `rewidth=True` (4.7.0, [search.embedding.width](../ontology/features/search.g5.md#search.embedding.width)), the registry width follows the column, and an unchanged class set is not recompiled.

Consequence: a deployment whose configuration spells the schema in another case (`IVG_SCHEMA_PREFIX=rag` for a namespace set up as `RAG`) silently re-declares empty vector columns at its own width, the 4.7.0 hazard the refusal exists for, and leaves registry and column disagreeing, so writes to those tables are refused at either width. Every setup from it also reports three failed classes and recompiles everything. Medium: no stored vector is lost (IRIS refuses the populated ALTER), but the documented refusal is bypassed and the namespace ends inconsistent.

Repair proposal (not implemented, not checked): canonicalize the engine's schema to the recorded spelling once the record is read (`same_schema` already accepts it), before any catalog lookup, rewrite or DDL; or read the declared width case-insensitively. Behavior to preserve: case-insensitive acceptance. Distinguishing case: binding `D:lower16_setup` must then raise as `D:upper16_setup` does. Writers/readers affected: `_record_and_initialize`, `_vector_column_action`, `reconcile_recorded_dimensions`, `deploy_packaged_classes`, `RoutineRecord`.

Governing statements: [install.schema.name](../ontology/concepts/install.g5.md#install.schema.name), [search.embedding.width](../ontology/features/search.g5.md#search.embedding.width).

---

<a id="bug-plt-026"></a>
### Setup records an explicitly named schema while IVG's tables sit in one other schema

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56); first recorded 2026-11-13 by code reading (review round 3 R3-reader H3); the 2026-11-15 audit found it inconclusive ([review record](audits/register-20261115/bugs-review.md#bug-plt-026)).

Found by: install.schema.existing metadata; iteration 56 frozen pair A3 (missed: the frozen owner reading predicted a refusal); [install_lifecycle](models/install_lifecycle/NOTES.md) `theorem_other_schema_needs_a_name` (as built), control `explicit-refused` (the FR-009 repair).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin (namespace I56SB; binding cases `B:default_*`, `B:y_explicit_dry`, `B:y_env_dry`, `B:y_explicit_setup`, `B:record_after_explicit`, `B:x_call_after_explicit`). IVG's tables in `I56X` only, the record removed. Passing neighbor: a default engine's dry run and setup raise `IVGSchemaError` naming `I56X` and record nothing. An engine with `schema_prefix="I56Y"` (or `IVG_SCHEMA_PREFIX=I56Y`): the dry run plans `explicit` with `other_schemas` `I56X`; setup records `I56Y` and creates its 18 tables, and from then on an engine for `I56X` is refused (mismatch).

Expected: spec 262 FR-009: "when it is another [schema], the engine MUST be refused with an error naming that schema ... and MUST record nothing"; an explicit name settles only the several-schema case. ADMIN_GUIDE's reply table (`explicit`: "named with `schema_prefix=` beside another schema's IVG tables") and the error's own advice ("to start a new IVG Schema beside it, name it explicitly") describe the as-built path: a doc conflict, kept with the spec as the owner does.

Consequence: one setup call with an explicit name abandons the existing tables' schema; the application's engine for it is refused until an operator moves data by hand. Low: deliberate, documented in the guide, reversible only manually.

Repair proposal (not implemented, not checked): refuse an explicit name when IVG's tables are in exactly one other schema (as FR-009), or amend FR-009 and the owner to the guide's reading; a decision either way.

Governing statement: [install.schema.existing](../ontology/concepts/install.g5.md#install.schema.existing).

---

<a id="bug-plt-133"></a>
### An unrecorded namespace whose IVG Schema holds this release's SQL objects admits engines

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: iteration 56 frozen pair A5 (missed: the owner predicts a refusal); `check_first_access` (`schema_name.py:220-242`: with no record, the class `<package>.funcCYCMP` admits the engine; with a record, nothing is probed); [install_lifecycle](models/install_lifecycle/NOTES.md) `theorem_unrecorded_with_marker_admitted`, `theorem_record_admits_without_objects`, control `unrecorded-marker-refused`. Documented in KNOWN_ISSUES ("After an interrupted setup the engine accepts the namespace, and its edge writes fail"), with no register entry before.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin (namespace I56SA; binding cases `A:norecord_marker_call`, `A:record_nomarker_call`, `A:norecord_nomarker_call`). After a complete setup, `^IVG.Deploy("schema")` killed: a new engine's first call answers (0). With the record present and `Graph_KG.CY_CMP` dropped: a new engine answers. Passing neighbor: with both the record and the marker function gone (IVG's classes and globals still there), the first call raises "setup has not finished here"; the next setup records `inferred` and recreates the one routine.

Expected: [install.schema.not_ready](../ontology/concepts/install.g5.md#install.schema.not_ready): an engine on a namespace with no schema record, or without the current release's SQL objects, raises one error on first access. ADMIN_GUIDE describes the as-built rule ("no record and lacks 4.6.0's SQL objects").

Consequence: an engine runs on a namespace whose last setup stopped after its DDL (grants, Arno revocation, ledger history and the record not yet done), or whose objects were partly dropped; failures surface later as SQL errors (KNOWN_ISSUES: edge writes fail where `Graph.KG.EdgeScan` is missing). Low: documented, and the next setup repairs it.

Repair proposal (not implemented, not checked): refuse with no record regardless of the marker (the control `unrecorded-marker-refused`), keeping setup, status and legacy removal exempt; optionally probe the marker when a record exists. Distinguishing case: `A:norecord_marker_call` must then raise "setup has not finished here".

Governing statements: [install.schema.not_ready](../ontology/concepts/install.g5.md#install.schema.not_ready), [install.setup.resume](../ontology/concepts/install.g5.md#install.setup.resume).

---

<a id="bug-plt-134"></a>
### A populated vector table at another width beside empty ones blocks setup both ways, and the manual-migration reply never comes

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: iteration 56 frozen pair D2 (partly missed); `_refuse_width_change` (`_engine/schema.py:1564-1599`) checks every vector table: an empty one at another width refuses without `rewidth`, a populated one refuses with it; [install_lifecycle](models/install_lifecycle/NOTES.md) `col_action`, `width_refused`, `theorem_populated_never_rewidened`, `theorem_empty_other_width_needs_rewidth`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin (namespace I56SA; binding cases `W:e8_dry_populated`, `W:e8_setup_populated`, `W:e8_rewidth_populated`, `W:col_after_populated`, `W:rows_after_populated`). All three vector tables declared 16, one 16-wide vector in `kg_NodeEmbeddings`, the others empty. An engine at width 8: the dry run lists `kg_NodeEmbeddings` under `needs_manual_migration` and the other two under `needs_rewidth`; `initialize_schema()` raises `EmbeddingIdentityConflict` (the empty tables); `initialize_schema(rewidth=True)` raises too (the populated one). Nothing changes; the vector stays. Passing neighbor: with all tables empty, `rewidth=True` re-declares them (`W:e16_rewidth`).

Expected: ADMIN_GUIDE §11: "plain `initialize_schema()` names the table in `status["needs_manual_migration"]`, with a matching entry in `status["warnings"]`"; the dry run's own lists predict that reply.

Consequence: the documented reply and warning never appear for the usual layout (node vectors stored, edge table empty); the operator gets a refusal naming the empty tables and, after `rewidth=True`, one naming the populated table. The documented remedy (delete the vectors, then `rewidth=True`) still works. Low: safe, misleading.

Repair proposal (not implemented, not checked): either list a populated table under `needs_manual_migration` and re-declare only the empty ones when `rewidth=True`, or document that a populated table blocks setup at another width until it is emptied.

Governing statement: [search.embedding.width](../ontology/features/search.g5.md#search.embedding.width).

---

<a id="bug-srch-116"></a>
### No quarantined vector can be placed through the IRIS DB-API driver

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: iteration 56 frozen pair F1 (missed: neither the placement nor a named refusal occurs); `_quarantined_row` (`_engine/schema.py:2072-2095`) returns `row[0]`, `row[1]`, `row[2]` after `cursor.close()`, which `get_embedding_identity` (1050-1053) explicitly avoids ("The IRIS driver's DataRow is a live view onto the cursor: reading it after close() raises <COMMUNICATION LINK ERROR> Cursor closed"); [install_lifecycle](models/install_lifecycle/NOTES.md) `theorem_unreadable_row_never_placed`, premise P-DATAROW-CLOSED, control `row-read-materialized`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin (namespace I56SA, intersystems-irispython 5.3.2; binding cases `Q:place_*`). Six quarantined rows (q1 and q2, widths 4 and 3, dtypes DOUBLE and FLOAT), a route (`g1`, `qm`) of width 4 and node q1 in `g1`: every `place_quarantined(q_rowid, graph=..., model_key="qm")` raises `ProgrammingError: <COMMUNICATION LINK ERROR> Cursor closed; Details: DataRow is inaccessible and/or Cursor is closed`, whatever the route, width, dtype or node; the quarantine keeps six rows and the route none. Passing neighbors: a q_rowid with no row raises the documented `ValueError`; `list_quarantine()` lists six and refuses an unknown reason. With `_quarantined_row` materializing the row first (the proposed repair, substituted in the harness only), every documented outcome holds (`QR:*`): no route, width and dtype conflicts, node not in the graph refused with the row kept; the valid row placed (quarantine −1, route +1); a second vector for the same node refused by the route's key (SQLCODE -119) with the row kept; totals conserved; no route created.

Expected: [search.quarantine.placement](../ontology/features/search.g5.md#search.quarantine.placement) and ADMIN_GUIDE §9: an operator places each quarantined vector, naming its graph; placement succeeds when the route and node fit, and refuses naming the reason otherwise.

Consequence: the only documented way out of quarantine does not work over the DB-API driver (the ordinary client connection), so vectors the 4.0.0 migration quarantined stay unsearchable; the error names a communication failure rather than a reason. Medium: an operator recovery path is unusable; no data is lost (the row stays). Embedded Python (irispython inside IRIS) was not tried; the unit tests use a mocked cursor.

Repair proposal (not implemented; checked only as a harness substitution, `QR:*`): materialize the row before closing the cursor (`values = None if row is None else tuple(row)`), as `get_embedding_identity` does. Behavior to preserve: refusal order and the insert-then-delete transaction.

Governing statement: [search.quarantine.placement](../ontology/features/search.g5.md#search.quarantine.placement).
