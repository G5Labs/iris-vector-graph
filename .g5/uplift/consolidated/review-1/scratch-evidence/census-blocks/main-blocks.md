# Reviewer main thread: graph.names, graph.names.report, ledger.commit.expected-head,
# redaction.tombstone.canonical-form, search.knn.threshold, temporal.write.retry

graph.names (4/2): own count 4-5/2. Grades agree (o01 full/full, o02 full/full, o03 full/narrowed, o04 partial).
 - o04 model_locators empty; erasure_stores.rs:542 theorem_refusal_changes_nothing represents refuse-before-write
   for the 5 erase entry points (one writer family) -> partial stays, locator missing.
 - x01 WA1 mixes restatement (refusal of new names = o01-o04; legacy report = graph.names.report#o01) with policy
   (migration plan); kind undecided-alternative acceptable, restatement owners not recorded (minor).
 - Fidelity: GraphKey.cls:38-48 Validate / ForIndex / ForLedger / ForName == graph_structure.rs valid/for_*; Python
   _validate.py:44 (ord<32 or 127) == py_valid.
 - Side finding: erasure_stores.rs:44 ctl = (<32 || ==127) is the Python set, labelled "GraphKey.Validate /
   validate_graph_name"; Eraser.cls:50-51,328-329,374 refuse via server GraphKey (also 128-159).
graph.names.report (3/0): agree; o01 absent (no verify_graph model), o02 partial (key refusal only; VerifyGraph
 GraphVerify.cls:41 call order not modeled), o03 absent. Parent entailment: none claimed, none needed.
ledger.commit.expected-head (2/0): own 3-4. Grades agree (full, narrowed by key None/holder free).
 - Missing: "expected head == current head commits" (lead "may name the head it expects"); o01's cases column lists
   it but theorem_expected_head_outcomes (ledger_client.rs:589-598) concludes nothing when e == head; only server()
   :217 falls through (definition). Missed obligation, partial at best.
 - Fidelity: Ledger.cls:475-486 order unknown-then-stale matches model :215-218; errors.py:161-162 map classes.
redaction.tombstone.canonical-form (4/0): agree all absent (digest_of uninterp, redaction.rs:151; no canonical
 JSON in any model or playbook crate).
search.knn.threshold (4/1): own 5/1. o03 full -> partial: theorem_filter_precedes_limit (vector_threshold.rs) uses a
 sorted 3-element input; a limit-then-filter mutant satisfies all its ensures (and theorem_boundary_included). The
 census case "best row below threshold, second above" is never exercised; controls (NOTES) do not include a
 limit-order mutant. Ordering is by `search` definition only (checklist a/b).
 Fidelity: vector.py:370-382, 1259-1268 WHERE ... AND cos>=? ... ORDER BY score DESC with TOP k matches.
temporal.write.retry (5/1): agree 5/5. theorem_fault_replays_entire_batch distinguishes "fallback starts from the
 prefix state" vs rollback; o05 count==2 distinguishes discarded vs summed prefix counters.
 Fidelity: iris_sql_store.py:2745-2783 BulkInsertCounts then per-edge write_temporal_edge, count of non-error
 calls, no collisions column - matches run().
