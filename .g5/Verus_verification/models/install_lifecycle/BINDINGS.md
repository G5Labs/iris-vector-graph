# install_lifecycle bindings (iteration 56)

Receipt: [binding](../../results/install_lifecycle/20261117T071614Z-binding/receipt.json) AGREES 138 cases; 20 of 20
mutations (one per control the fixture can distinguish, `failed-deploy-keeps-marker` through the other-case deploy)
and the tampered observation (`A:norecord_marker_call`) detected. Proof:
[prove](../../results/install_lifecycle/20261117T071254Z-prove/receipt.json) 32 verified; controls
`results/install_lifecycle/20261117T0712*-control-*` and `20261117T0713*-control-*` (20 EXPECTED_FAIL).

Expected values come from `binding.py`'s port of the model applied to the history the harness wrote; the observations
come from `observe.py` driving the real engine at the pin. Rows are registered in
`crosswalk/decision-links.tsv` (family `C-install_lifecycle`); the binding-integrity audit is in
[iteration-56/install/decision-links.tsv](../../../uplift/consolidated/iteration-56/install/decision-links.tsv) and
the iteration-56 handoff.

| Member | Role | Formal item | Grade |
|---|---|---|---|
| `schema_name.py::validate_schema_name` 143-164 | decision | `theorem_name_rules_refuse_before_default` | transcription, native agreement (12 names) |
| `schema_name.py::resolve_schema_name` 167-173 | decision | `theorem_arg_wins` | native agreement (5 resolutions) |
| `schema_name.py::check_first_access` 220-242 | decision | `theorem_other_record_refused`, `theorem_unrecorded_with_marker_admitted` | native agreement |
| `schema_name.py::_why_not_current` 249-267 | decision | `theorem_unrecorded_reason_order` | native agreement (never set up / IVG global only / earlier-release class) |
| `schema_name.py::refuse_other_record` 184-191 | guard | `theorem_deploy_refuses_other_record` | native agreement (`A:alt_deploy`) |
| `schema_name.py::refuse_package_clash` 501-509 | guard | `theorem_clash_refused_before_anything` | native agreement (`C:clash_*`) |
| `_engine/schema.py::SchemaMixin._record_and_initialize` 2198-2326 | decision | `theorem_other_schema_needs_a_name`, `theorem_dry_run_and_refusals_keep_record` | native agreement |
| `_engine/class_deploy.py::_unchanged` 213-226 | decision | `theorem_skip_iff_same_fingerprint_and_all_compiled` | native agreement (marker altered, class deleted) |
| `_engine/class_deploy.py::upload_and_compile` 229-297 | decision/effect | `theorem_failed_deploy_retried` | native agreement (other-case deploy fails, marker cleared) |
| `_engine/class_deploy.py::plan_packaged_classes` 327-338 | reader | `theorem_skip_iff_same_fingerprint_and_all_compiled` | native agreement |
| `_engine/class_deploy.py::deploy_packaged_classes` 341-367 | entry/guard | `theorem_deploy_refuses_other_record` | native agreement |
| `_engine/schema.py::SchemaMixin._vector_column_action` 1516-1537 | decision | `theorem_populated_never_rewidened`, `theorem_unknown_width_altered_unasked` | native agreement |
| `_engine/schema.py::SchemaMixin._plan_vector_dimensions` 1539-1552 | reader | `col_action` | native agreement (dry-run lists) |
| `_engine/schema.py::SchemaMixin._refuse_width_change` 1564-1599 | guard | `theorem_empty_other_width_needs_rewidth` | native agreement |
| `_engine/schema.py::SchemaMixin._migrate_vector_dimensions` 1601-1686 | effect | `width_after` | native agreement (columns after) |
| `_engine/schema.py::SchemaMixin.reconcile_recorded_dimensions` 1688-1713, `_sync_recorded_dimension` 1399-1424 | effect | `reg_width_after` | native agreement (registry after) |
| `_engine/schema.py::SchemaMixin.set_embedding_identity` 1086-1222 | decision | `theorem_claim_only_unknown` | native agreement |
| `_engine/schema.py::SchemaMixin.adopt_embedding_identities` 1256-1335 | decision | `theorem_adopt_never_overwrites` | native agreement |
| `_engine/schema.py::SchemaMixin.enforce_embedding_identity` 1354-1397, `embedding_identity.py::conflicts` 180-241 | decision | `theorem_width_enforced_whatever_the_model` | native agreement |
| `_engine/schema.py::SchemaMixin.place_quarantined` 1972-2070 | decision | `theorem_unreadable_row_never_placed` (as built); `theorem_placed_only_when_every_check_passes` (conditional on the repair) | native agreement; the post-read checks only under the substituted `_quarantined_row` |

Locator-only (cited, not counted): `foreign_classes`, `same_schema`, `write_record`, `FirstAccessCheck.guard_methods`
(delegates), `_ivg_table_schemas`, `_plan_setup` (delegates), `foreign_schema_classes`, `_quarantined_row`,
`GraphSchema.get_embedding_dimension`: each either supplies a model input or has no decision the binding could tell
apart from its caller's.
