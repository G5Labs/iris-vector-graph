# Independent aggregate-result review panel

Frozen from restored iteration12 owners and pinned primary docs/tests/production source before inspecting the new `aggregate_results` candidate. Product3eaa79cf77d3e0a879b2cced634cf2729d81499e, baseline198365a3e726bac66d5c67901a1b86e2238cbc47. Source-informed purposive obligations, not a held-out draw or project-wide estimate. No interrupted input or observation is reused. No native/network execution.

| ID | Material neighbors and expected observation |
| --- | --- |
| A1 | No raw input matches versus one match: global count returns one row with0 versus1; grouping by a key on empty input produces no group rows. Distinguish the implicit global group from a supplied empty result. |
| A2 | Raw rows `[null,2,2]`: count(*)=3, count(value)=2, count(DISTINCT value)=1. Counts must be derived from raw row presence/value, not supplied totals. |
| A3 | All-null versus numeric groups: sum is0 and collect is[] on no nonnull values; numeric values contribute their actual arithmetic total. |
| A4 | Duplicated values versus distinct values: DISTINCT changes aggregate membership, while ordinary count/collect preserve multiplicity. Collection order is only claimed under a justified provider/order frame. |
| A5 | Same ID in two graphs versus repeated same graph+ID: native count(DISTINCT node) uses graph+ID identity; an ID-only set must not collapse graphs. Raw physical edge multiplicity must reach counts. |
| A6 | Null grouping key versus nonnull key: nulls form a legitimate group and are not silently dropped or confused with empty text. |
| A7 | Two different group keys versus equal values: raw grouping equivalence decides group membership; a prepared group map cannot supply the missing producer. |
| A8 | Integer-only sum versus a sum containing a float: whole-valued float totals remain floats on typed property sums, including a WITH-carried sum; the untyped whole→int fallback applies only to marked columns. |
| A9 | Stored numeric value versus numeric-looking text: final typed reads retain the distinction within their admitted codec frame; arithmetic/native comparison coercions remain separately qualified. |
| A10 | Known mixed literal/parameter collect versus runtime/ambiguous text: typed JSON construction preserves bool/list/map/string distinctions for supported known rows; arbitrary JSON/native numeric codec correctness is not implied. |
| A11 | Node/relationship values versus scalar values: collect must derive structured values and final reader projection; existing scalar reader proof does not prove graph-object reconstruction. |
| A12 | Ordered groups with tied aggregate counts: full returned-key ordering is total only when every grouping key participates; ORDER BY count alone does not establish tie order. |
| A13 | LIMIT/SKIP off versus unsafe paging wrapper: hidden sort projections are consumed for ordering and removed from the final columns; inner SQL aliases must not escape into outer scope. |
| A14 | Returned alias versus expression column name: final naming follows the parsed RETURN projection and translation metadata; typed conversion must use the right column before final rename. |
| A15 | Empty successful result versus error: empty success can recover RETURN columns; an error is not fabricated as a valid zero aggregate and its error/columns are preserved according to the actual finalizer. |
| A16 | Leading OPTIONAL MATCH with no match versus ordinary empty MATCH: count(*) can count the optional null row as1; do not apply the ordinary empty-input law indiscriminately. |
| A17 | Native planner accepted count fragment versus declined property sum/count/list fragment: decline routes to the SQL provider rather than inventing a generic refusal or asserting native equivalence. |
| A18 | Actual raw SQL aggregate rows/metadata versus final result: hidden-column removal, typed/bool/relationship/numeric/JSON decoding and alias renaming order must be traced; passing only predecoded answers is insufficient. |
| A19 | Admitted numeric/text/JSON/order carriers versus arbitrary provider behaviors: exact mathematical aggregation may be proved in a bounded domain, with SQL/native arithmetic/collation/serialization and body limits named. Legal inputs outside the proof remain partial, not API-invalid. |
| A20 | Deciding group/aggregate logic → writer/accumulator/SQL producer → actual final reader: independently enumerate all necessary roles, distinguish unchanged imports and existing substantive hits, and credit only declared bounded source behaviors. |

Primary authority: USER_GUIDE165–170 and typed-value examples; tests/unit/test_sum_column_typing.py, test_empty_result_columns.py, test_460_r308_collect_typed.py, test_order_limit_aggregate_scope.py, test_253_native_plan_groups.py, test_460_r273_native_group_keys.py. Source inspected: translator aggregation/RETURN/WITH fragments; `_finish_sql_result`, numeric/empty-column decoders; native Exec Group/GroupCount/EmitGroups/GroupRow as inspected production evidence only. Owners: query.conformance, query.values, structure.multigraph.count, and graph scope. Existing scalar/route/paging contracts may be partial hits; none is assumed to prove this aggregate producer chain.
