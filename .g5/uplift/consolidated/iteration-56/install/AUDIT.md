# Binding-integrity audit: install_lifecycle rows (iteration 56 Part B)

Question per row with relation models/proves: would swapping or weakening this member's own decision break a theorem
or the binding? "Control/mutation" names the model control and the binding mutation that encode that weakening.
Rows whose member supplies a model input, or whose removal the binding cannot tell from its caller's, are relabeled
`cites`/`delegates` (not counted by `member_reach.py`). Rows: [decision-links.tsv](decision-links.tsv) (35 rows, 22
distinct active members: 21 newly active, `_record_and_initialize` strengthened).

| Member | Relation | Own decision | Weakened → detected by | Verdict |
|---|---|---|---|---|
| `schema_name.py::validate_schema_name` | proves | rule order, code-package refusal | `code-package-unchecked` (theorem; `name:Graph_KG_x`, `IVG_A`, `IVGC`) | active |
| `schema_name.py::resolve_schema_name` | proves | argument over environment | `env-over-arg` (theorem; `resolve:arg_env`) | active |
| `schema_name.py::check_first_access` | proves | record compare; no-record marker admission | `no-mismatch-check` (`A:alt_call`), `unrecorded-marker-refused` (`A:norecord_marker_call`) | active |
| `schema_name.py::_why_not_current` | proves | reason order | `traces-before-legacy` (`C:legacy_class`) | active |
| `schema_name.py::refuse_other_record` | proves | deploy refusal on another record | `no-mismatch-check` (`A:alt_deploy`; theorem `theorem_deploy_refuses_other_record`) | active |
| `schema_name.py::refuse_package_clash` | proves | refuse before DDL when foreign classes exist | `clash-unchecked` (`C:clash_dry`, `C:clash_run`, `C:clash_record`) | active; *which* classes are foreign is `foreign_classes`' (an input, cited) |
| `schema_name.py::foreign_classes` | cites | classifies classes | model takes `clash` as input | locator |
| `schema_name.py::same_schema` | cites | case-insensitive equality | the model compares canonical ids; the case-variant consequences are provider premises | locator |
| `schema_name.py::write_record` | cites | none (writes what it is given) | — | locator |
| `schema_name.py::FirstAccessCheck.guard_methods` | delegates | wraps methods | removing it: the `conn` property still raises; binding cannot tell | not counted |
| `_engine/schema.py::SchemaMixin._record_and_initialize` | proves | mismatch, how, explicit, clash order, dry run, record written last | `explicit-refused` (`B:y_explicit_*`), `dry-run-records` (`A:dry1_record`) | active (strengthened) |
| `_engine/schema.py::SchemaMixin._ivg_table_schemas` | cites | where the tables are | model input `held_self/held_other` | locator |
| `_engine/schema.py::SchemaMixin._plan_setup` | delegates | forwards plan_packaged_classes | — | not counted |
| `_engine/class_deploy.py::_unchanged` | proves | fingerprint and every class compiled | `skip-on-marker-only` (`A:plan_class_missing`, `A:setup_class_missing`, `A:class_back`) | active |
| `_engine/class_deploy.py::upload_and_compile` | proves | marker cleared before load, set only after a clean compile | `failed-deploy-keeps-marker` (`B:fingerprint_after_lower`) | active |
| `_engine/class_deploy.py::plan_packaged_classes` | proves | the dry run's compile list from `_unchanged` and force | `skip-on-marker-only` (`A:plan_*`) | active (its own role: the reader of the decision; force not exercised) |
| `_engine/class_deploy.py::deploy_packaged_classes` | proves | refuse_other_record before anything | `no-mismatch-check` (`A:alt_deploy`) | active |
| `_engine/class_deploy.py::foreign_schema_classes` | cites | taken classes | not exercised; model input | locator |
| `_engine/schema.py::SchemaMixin._vector_column_action` | proves | unchanged/alter/manual/rewidth incl. unknown width | `populated-altered`, `rewidth-not-required`, `unknown-width-counted` | active |
| `_engine/schema.py::SchemaMixin._plan_vector_dimensions` | models | the dry run's buckets | swapped buckets change `W:e16_dry`, `W:e8_dry_populated`, `D:lower16_dry` (binding) | active (binding-detected, no own theorem) |
| `_engine/schema.py::SchemaMixin._refuse_width_change` | proves | which actions refuse | `rewidth-not-required` (`W:e16_setup`), `populated-altered` (`W:e8_rewidth_populated`) | active |
| `_engine/schema.py::SchemaMixin._migrate_vector_dimensions` | models | ALTER only for alter | `populated-altered`/`rewidth-not-required` change `W:col_*`, `D:after_lower` | active |
| `_engine/schema.py::SchemaMixin.reconcile_recorded_dimensions` | models | registry width follows a readable declared width | dropping it changes `W:reg_after_rewidth`; reading the width case-insensitively changes `D:after_lower.reg` | active |
| `_engine/schema.py::SchemaMixin._sync_recorded_dimension` | models | the registry UPDATE | dropping it changes `W:reg_after_rewidth` | active |
| `_engine/schema.py::SchemaMixin.set_embedding_identity` | proves | claim only unknown; force; no-op on same | `claim-known-model` (`I:other_model`) | active |
| `_engine/schema.py::SchemaMixin.adopt_embedding_identities` | proves | never overwrite | `adopt-overwrites` (`I:adopt`, `I:reg_node_after_adopt`) | active |
| `_engine/schema.py::SchemaMixin.enforce_embedding_identity` | proves | none recorded passes, else conflicts refuse | `width-only-with-models` (`I:enforce_w8`, `W:store8`); removing the call: same cases | active (the width/model decision is `conflicts`', shared) |
| `embedding_identity.py::conflicts` | proves | model, mechanism, width, dtype | `width-only-with-models` | active |
| `_engine/schema.py::SchemaMixin.place_quarantined` | proves | check order, insert then delete | `row-read-materialized`, `place-skips-node-check`, `placement-creates-route`, `delete-before-insert` (`Q:*`, `QR:*`) | active; post-read checks conditional on the repair |
| `_engine/schema.py::SchemaMixin._quarantined_row` | cites | the read that fails | model takes `row_read_ok` as a provider input | locator (bug-srch-116) |
| `schema.py::GraphSchema.get_embedding_dimension` | cites | declared width lookup | model input `db` (P-CASE-LOOKUP) | locator |

Withdrawn: none (no existing row changed). Members assessed but not given a row: `IVGSchemaError` message
constructors (no decision; the binding matches their text), `read_record`, `FirstAccessCheck.ensure`, `rewrite_schema_text`,
`SchemaConnection`/`SchemaCursor`, `_plan_routines`, `list_quarantine` (reason refusal observed only), `is_ready`.
