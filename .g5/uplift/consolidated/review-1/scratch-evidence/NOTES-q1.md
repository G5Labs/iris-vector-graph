# review-1 Q1 (native executor) — reviewer notes

Derived first from spec 253 (FR-001..015), CONTEXT.md "Query execution", docs/dev/TCK.md "How the native path is held",
_engine/query.py 2032-2249, native_plan.py, native_shadow.py, native_route.py, engine.py 290-320/559-610/704-723,
Exec.cls Run/RunA/Anchors, Props.cls, Gen.cls, schema.py 2930-2941.

## Replays (scratch clone, RUN_DIR=scratch/review-1/native/rundir)
- prove native_admission: PASS (54 verified, 0 errors) results/native_admission/20261118T045025Z-prove (clone only)
- controls complete-order-flag, anchor-ignores-privileges, drop-bulk-gate: EXPECTED_FAIL each
- r1_native_witness.rs (model + one reviewer theorem): 55 verified, 0 errors.
  r1_witness_topk_wrong_group_passes: aggregate ORDER BY count only + LIMIT -> plan unordered, compare passes a wrong
  top-1 that owner_equal(complete_order=true) rejects.
- topk_probe.py (real plan_query + real native_shadow.compare): agg_order_by_count_limit planned
  {ordered False, limited True}; wrong top-1 accepted; reversed count order without LIMIT accepted.
- live/r1_route_alternation.py (namespace R1N, dropped, verified Exists 0,0): default engine (native_cypher True,
  native_route_ms 50), bug-cyp-104 query, 12 identical calls: 1-3 native, then sql/native alternate; two distinct
  answers ['a','b',1,2,'',None] (native) vs ['','a','b',1,2,None] (sql).
- Not replayed: native_admission binding (hard-coded I62B/I62C namespaces, creates users/roles; outside R1-only
  permission). Master replay log scratch/master-62-binding.log: AGREES 50 live cases.

## Findings drafted (see final report)
N1 shadow/equal-answers blind to partial ORDER BY (material)
N2 default route trial alternates answers where paths differ (material, cross-area)
N3 fallback#o01 scope: Python half of native path outside the try (minor)
N4 reads-only owner example still wrong (minor; owner-contradicted since it62, not repaired)
N5 shadow#o03 refutation rests on unconstructed RuntimeError branch (minor; premise recorded, gap empty)
N6 deploy-discards#o01 check_scope full despite swallowed DropAll failure (minor)
N7 setup resets executor cache only when objectscript_deployed (minor correspondence)
N8 merge_prefix j==0 branch has no __ alias; declined by planner instead (minor; outcome unchanged)
