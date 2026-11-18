# The install lifecycle (install_lifecycle)

Product `3eaa79cf`, unchanged. Iteration 56, Part B. Predictions frozen before the deciding source was read:
[install-PAIRS.md](../../../uplift/consolidated/iteration-56/install-PAIRS.md) (commit `4f1c5d25`). Owners:
[install.schema.name](../../../ontology/operations/setup-and-upgrade.g5.md#install.schema.name),
[install.schema.refusal](../../../ontology/operations/setup-and-upgrade.g5.md#install.schema.refusal),
[install.schema.not_ready](../../../ontology/operations/setup-and-upgrade.g5.md#install.schema.not_ready),
[install.schema.existing](../../../ontology/operations/setup-and-upgrade.g5.md#install.schema.existing),
[install.setup.dry_run](../../../ontology/operations/setup-and-upgrade.g5.md#install.setup.dry_run),
[install.setup.resume](../../../ontology/operations/setup-and-upgrade.g5.md#install.setup.resume),
[install.deploy](../../../ontology/operations/setup-and-upgrade.g5.md#install.deploy),
[search.embedding.width](../../../ontology/features/search.g5.md#search.embedding.width),
[search.embedding.claim](../../../ontology/architecture/search-storage-and-indexes.g5.md#search.embedding.claim),
[search.embedding.check_on_write](../../../ontology/features/search.g5.md#search.embedding.check_on_write),
[search.quarantine.placement](../../../ontology/architecture/search-storage-and-indexes.g5.md#search.quarantine.placement).
An as-built Verus transcription with native agreement; **not** executable-body verification. Bundled vstd only; no
`assume`, `admit` or `external_body`. 32 verified; 20 controls, each EXPECTED_FAIL in its named theorems.

## What each section derives, from which input

| Section | Deciding input | Derived decision | Reader |
|---|---|---|---|
| N names | the name's shape (empty, `%`, pattern, SQLUser, default in any case, package under `Graph.KG`/`IVG`/`IVGC`); argument and environment | `validate` (rule order), `resolve` (argument, else non-empty `IVG_SCHEMA_PREFIX`, else `Graph_KG`) | `ValueError` / the engine's schema |
| F first access | the record, the schema's marker function, earlier-release classes, IVG's own classes/tables/globals | `first_access`: record → Ok or Mismatch; no record → marker Ok, else NotUpgraded, Unfinished, NeverSetUp; `call_runs` (exempt calls always) | the first public call / `status()` |
| S setup record | record, engine schema, where IVG's base tables are, explicit, package clash, dry run | `how` (existing, new, inferred, explicit, refuse), `setup`, `record_after` | the reply's `schema_recorded`, `^IVG.Deploy("schema")` |
| D class deploy | the marker, the source set's fingerprint, every class compiled, force, a foreign schema class, a clean compile | `deploy` (Unchanged / Refused / Deployed), `marker_after`, `plan_compiles`, `deploy_admitted` | `objectscript_compiled`, the marker |
| W widths | declared width (or none), configured width, rows (or uncounted), rewidth | `col_action`, `width_refused`, `width_after`, `reg_width_after` | the reply / dry-run lists, the column, the registry |
| I identity | recorded row, offered identity, force | `conflicts`, `set_identity`, `adopt`, `enforce_ok` | the registry row; the write's refusal |
| Q quarantine | row exists, row readable, route (width, dtype), node in graph, route key free | `place`, `place_effect` | `place_quarantined`, `list_quarantine`, route rows |

## General theorems

`theorem_name_rules_refuse_before_default`, `theorem_arg_wins`, `theorem_other_record_refused`,
`theorem_unrecorded_reason_order`, `theorem_unrecorded_with_marker_admitted`, `theorem_record_admits_without_objects`,
`theorem_dry_run_and_refusals_keep_record`, `theorem_record_never_changes_once_written`,
`theorem_first_setup_records_engine_schema`, `theorem_other_schema_needs_a_name`, `theorem_existing_after_first_run`,
`theorem_setup_then_access`, `theorem_clash_refused_before_anything`, `theorem_deploy_refuses_other_record`,
`theorem_skip_iff_same_fingerprint_and_all_compiled`, `theorem_failed_deploy_retried`, `theorem_clean_deploy_then_skip`,
`theorem_missing_class_redeploys`, `theorem_populated_never_rewidened`, `theorem_empty_other_width_needs_rewidth`,
`theorem_unknown_width_altered_unasked`, `theorem_same_width_untouched`, `theorem_adopt_never_overwrites`,
`theorem_width_enforced_whatever_the_model`, `theorem_claim_only_unknown`, `theorem_adopted_row_claimed_keeps_width`,
`theorem_same_model_kept`, `theorem_undeclared_set_refused`, `theorem_placement_conserves_and_never_creates_route`,
`theorem_placed_only_when_every_check_passes`, `theorem_refused_row_stays`, `theorem_unreadable_row_never_placed`.
Each quantifies over every input of its section (no fixed instance).

## Value domains, abstractions and premises

- Schema names are abstracted to a canonical id (`same_schema` is equality on it). The letter case of the text
  matters to the product elsewhere: catalog and class lookups are case-sensitive. That difference is carried as two
  provider premises, observed and not derived: **P-CASE-LOOKUP** (`GraphSchema.get_embedding_dimension` finds no
  declared width under another case) and **P-CASE-CLASS** (IRIS refuses a class whose name differs only in case from
  a compiled one, ERROR #5092). Both drive [bug-plt-015](../../bugs_issues.md#bug-plt-015).
- Which classes are foreign (`foreign_classes`), where IVG's tables are (`_ivg_table_schemas`) and the fingerprint
  hash are inputs; their producers are cited, not bound.
- **P-ALTER-POPULATED**: IRIS refuses `ALTER COLUMN emb VECTOR(...)` on a populated vector column at another width
  (observed in I56SD; the column and its vector stay).
- **P-DATAROW-CLOSED**: the IRIS DB-API driver (intersystems-irispython 5.3.2) refuses to read a fetched DataRow after
  its cursor closes (`<COMMUNICATION LINK ERROR> Cursor closed`). `_quarantined_row` does exactly that, so
  `row_read_ok` is false for every existing row over that driver ([bug-srch-116](../../bugs_issues.md#bug-srch-116)).
  Embedded Python (irispython inside IRIS) was not tried.
- Route key: a route holds one vector per (graph, node) (observed SQLCODE -119 on the second copy).
- Model-key normalization (trim, lower, collapse spaces) is a premise from `search.embedding.model_key`; the model
  compares normalized ids.
- Not modeled: routine fingerprints (`RoutineRecord`), legacy grants, Arno revocation, ledger history copy, the
  adjacency index and `^KG` build, `TUNE TABLE`, iFind repair, the DDL privilege refusal, concurrent setups and
  concurrent claims (two writers), `list_quarantine`'s reason check (observed), `_record_configured_embedding_identity`
  (no engine here declares a model), routed-table identities other than the legacy tables.

## Departures and findings

- [bug-plt-015](../../bugs_issues.md#bug-plt-015) (inherited, inconclusive in the 2026-11-15 audit; now E2E reproduced,
  Medium): an engine whose `schema_prefix` names the recorded schema in another letter case is accepted (as
  documented), but its setup reads no declared width and re-declares the empty vector columns at its own width unasked
  (the 4.7.0 refusal is bypassed), leaves the registry at the old width so it disagrees with the columns, and loads the
  classes under its own spelling: the three schema classes fail to compile (ERROR #5092), the deploy fingerprint is
  cleared, and every later setup recompiles every class and re-creates 58 routines.
  `theorem_unknown_width_altered_unasked`; control `unknown-width-counted`; binding `D:*`, `B:x_lower_*`.
- [bug-plt-026](../../bugs_issues.md#bug-plt-026) (inherited, inconclusive; now E2E reproduced): with IVG's tables in
  one other schema and no record, an engine naming its schema explicitly is recorded (`explicit`) and the other
  schema's engine is refused from then on, against spec FR-009 and `install.schema.existing`. ADMIN_GUIDE and the
  error's own advice describe this path, so the docs conflict with the spec. `theorem_other_schema_needs_a_name`
  (as built); control `explicit-refused` (the FR-009 repair); binding `B:y_explicit_*`, `B:record_after_explicit`.
- [bug-plt-133](../../bugs_issues.md#bug-plt-133) (Low, new register entry for a KNOWN_ISSUES item): an unrecorded
  namespace whose IVG Schema holds this release's marker function admits every engine for that schema (an interrupted
  setup after its DDL, or a removed record), against `install.schema.not_ready`; a recorded namespace is never probed
  for its objects. `theorem_unrecorded_with_marker_admitted`, `theorem_record_admits_without_objects`; control
  `unrecorded-marker-refused`; binding `A:norecord_marker_call`, `A:record_nomarker_call`.
- [bug-plt-134](../../bugs_issues.md#bug-plt-134) (Low): a populated vector table at another width beside empty ones
  at that width: plain setup raises `EmbeddingIdentityConflict` for the empty ones and `rewidth=True` raises for the
  populated one, so the documented reply (`needs_manual_migration`) never appears. `col_action` / `width_refused`;
  binding `W:e8_*`.
- [bug-srch-116](../../bugs_issues.md#bug-srch-116) (Medium): `place_quarantined` fails for every existing row over
  the DB-API driver; the row stays. `theorem_unreadable_row_never_placed`; control `row-read-materialized` (the
  repair); binding `Q:*` as built and `QR:*` under the repair (all documented refusals and the placement agree).

## Commands

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/install_lifecycle      # PASS 32
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/install_lifecycle   # 20 EXPECTED_FAIL
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/install_lifecycle/binding.py)  # AGREES 138
```

The binding drops and re-creates the namespaces I56SA, I56SB, I56SC and I56SD from `%SYS` in `ivg-cont-20261117-iris`
only (needs `docker exec` on that container), about 75 s.
