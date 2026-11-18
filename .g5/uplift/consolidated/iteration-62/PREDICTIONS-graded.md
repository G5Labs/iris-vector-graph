# Iteration 62: predictions graded

Both sets were frozen before the deciding code was read:
- the builder's: [PREDICTIONS-builder.md](PREDICTIONS-builder.md), sha256 in [PREDICTIONS-builder.sha256](PREDICTIONS-builder.sha256), commit `e443e7ee`;
- the master's: `$G5_RUN_STATE/assignments/iteration-62-master-predictions.md`, sha256 `b2a3684a…13fbbd`, checked
  against the `.sha256` beside it before reading.

Evidence: E = the binding receipt `results/native_admission/20261118T021610Z-binding` (case names below);
M = a `native_admission.rs` theorem; U = a unit-level call of the real function in the same binding.

Grades: **S** supported, **W** wrong, **P** partial, **U** unconfirmed.

## Builder

| id | grade | evidence and what differed |
|---|---|---|
| PA1 | S | E `switch_argNone_envunset` native, `switch_argFalse_envunset` SQL, same rows and types |
| PA2 | **W** | Predicted that `IVG_NATIVE_CYPHER=0` wins over an explicit `native_cypher=True`. It does not: E `switch_argTrue_env0` answered natively; M `theorem_explicit_true_beats_env_zero`; bug-cyp-159 |
| PA3 | S | E `bulk_before`/`bulk_inside`/`bulk_after`: native, SQL, native |
| PA4 | S | E `write_set`, `union`, `call`, `skip`: SQL, no native run |
| PA5 | P | Predicted that no part of a write query reaches the native executor. Right for the owner's example and for count_create: their read steps are declined by the translation-width check (E `row_merge_prefix`, `count_create_step`; M `theorem_write_read_steps`). Wrong for a read statement chained after a write: it runs natively and reads the uncommitted SET (E `chained_write_then_read`) |
| PA6 | S | E `priv_i62_all` native, `priv_i62_part` SQL with rows |
| PA7 | P | Predicted that the running engine keeps answering after the REVOKE. True for a label scan (E `priv_rev_running_engine_label_scan`). A property-lookup read instead fails in Exec's SQL anchor and falls back to SQL, which fails too (E `priv_rev_running_engine_props_anchor`; M `theorem_revoke_reaches_sql_anchor_only`). New engine: SQL as predicted (an error result) |
| PA8 | S | E `exec_v2_new_engine_gate`, `exec_missing_new_engine_gate` (version warning once, cached), `exec_restored_cached_engine_stays_sql`, `exec_restored_after_setup`; the transient branch is M only |
| PA9 | S | E `mapped_label` SQL with the table's row; `unmapped_label_same_engine` native |
| PA10 | U | Not run live this iteration (the gate reads the cached `idx_edges_adj` answer; M `gate`) |
| PF1 | S | E `exec_v2_running_engine_falls_back`, `exec_missing_running_engine_new_reason` |
| PF2 | S | E: one warning, then none for the same reason, then one for a new reason |
| PF3 | S | Message-keyed as predicted, refined: the key is the exception type plus the first 160 characters (U `warned_set_unit` [1,1,2,2,3]; M `theorem_reason_is_type_and_160_chars`) |
| PF4 | S | E `priv_rev_running_engine_props_anchor`: the SQL path's error result, not the native error |
| PF5 | S | E `exec_v2_shadow_native_failure`: a second engine warned again for the same reason |
| PS1 | P | Equal answers returned the native result (E `shadow_eq_read`, one native run); a difference raises and is never returned, but the message names the plan, not the query (E `shadow_order_empty_string`; bug-cyp-161) |
| PS2 | P | Error result: `NativeMismatch` as predicted (E `priv_rev_running_engine_shadow_scan`). A raised SQL error is **not** a `NativeMismatch`: a plain `RuntimeError` becomes an error result at `execute_cypher` (M `theorem_shadow_sql_failure`; not constructed live) |
| PS3 | S | E `exec_v2_shadow_native_failure`: SQL answer, no raise |
| PS4 | P | The attribute is per engine as predicted; the variable is read on every call, not when the engine is built (E `shadow_env_on`/`shadow_env_off` on one engine built before the variable was set) |
| PS5 | S | E `route_held_sql_no_shadow` (routed SQL) beside `route_held_sql_shadow` (native, compared); `shadow_records_no_route` |
| PS6 | S | U comparator domain (2,116 inputs); M `theorem_limit_pass_means_rows_of_full_answer`; E `shadow_limit_unordered` |
| PS7 | S | U comparator domain: `1`, `'1'`, `1.0`, `true` are four values; M `theorem_type_is_part_of_the_value` |
| PS8 | S | The decision is supported: U `f0907_tie_order` (real planner flag `ordered`, real comparator raises on a tie permutation, with and without LIMIT); M `theorem_partial_order_compared_in_order`. No live raise: SQL and native returned the same tie order on this data |
| PS9 | S | E `skip` SQL; M `theorem_skip_never_compared` |

Builder: 24 predictions. 17 S, 1 W, 5 P, 1 U. (PF3 and PS8 count as S with the refinement stated.)

## Master

| id | grade | evidence and what differed |
|---|---|---|
| A1 | P | The bulk-session neighbour is supported on an admitted read (E `bulk_*`). The stated query `MATCH (n:L) RETURN n.id ORDER BY n.id` is never native: the planner declines `x.id` (a property row on the SQL path; only `node_id` is the identity). Checked with the real `plan_query` |
| A2 | S | E `mapped_label`, `unmapped_label_same_engine` |
| A3 | S | A fresh engine is gated (NoSelect) and the SQL path's error result is returned (E `priv_rev_new_engine`, for `rdf_props`). A running engine was not part of the prediction (see PA7) |
| A4 | P | Writes go to SQL (E `write_set`). The read step before a per-row MERGE does **not** run natively (E `row_merge_prefix`); a read statement chained after a write does, and sees the uncommitted row (E `chained_write_then_read`) |
| A5 | P | UNION and CALL: S (E `union`, `call`). Chained statements: **W** — each supported read statement runs natively (E `chained_parts`, two native runs; bug-cyp-160) |
| A6 | S | E `exec_v2_new_engine_gate`: SQL and one `native Cypher off ... redeploy` warning |
| A7 | P | Per-engine: S (E `switch_argFalse_envunset` beside the native default). `IVG_NATIVE_CYPHER=0` → every engine SQL: **W** for an engine built with `native_cypher=True` (E `switch_argTrue_env0`; bug-cyp-159) |
| A8 | U | Not run live. The model caches the index answer per engine until setup (M `idx_probe`, `setup`), which supports the prediction formally |
| B1 | S | E `exec_v2_running_engine_falls_back`, `exec_v2_same_reason_again`, `exec_missing_running_engine_new_reason` |
| B2 | S | E `exec_v2_shadow_native_failure`; M `theorem_shadow_native_failure_uncompared` |
| C1 | S | E sample `eq_read`: `'1'` is a str on both paths |
| C2 | S | E sample `order_empty_string` (native `a, b, '', null`; SQL `'', a, b, null`) and `shadow_order_empty_string` raises (bug-cyp-104) |
| C3 | S | E sample `group_mixed_types` and `shadow_group_mixed_types` raises (bug-cyp-136) |
| C4 | S | U comparator domain; E `shadow_limit_unordered`; M `theorem_limit_pass_means_rows_of_full_answer` |
| C5 | P | Raised and never returned; names the parameters and a row, but the plan instead of the query (bug-cyp-161) |

Master: 15 predictions. 9 S, 0 W (two W halves sit inside P rows A5 and A7), 5 P, 1 U.

## What the predictions did not anticipate (found by the probe or the binding after the source read)

- Exec's property-lookup and unlabelled-id anchors go through `%SQL.Statement`, so a REVOKE reaches those native
  reads, though not label scans (now `theorem_revoke_reaches_sql_anchor_only`).
- The per-row MERGE prefix and count_create's count step are declined by the translation-width check, because of
  their `__` aliases (now `theorem_write_read_steps`).
- The shadow mismatch names the plan's repr (bug-cyp-161).
