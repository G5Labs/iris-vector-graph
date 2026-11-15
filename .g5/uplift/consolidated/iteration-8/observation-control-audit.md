# Independent observation-control audit

Product3eaa79cf; iteration8 after sealed7 `9e6a876f`. Scope: the24 active files named models/*/binding.py present at the initial audit, plus the newly appeared retry_replay binding at close, their changed-observation detection assignments and the comparison predicates they call. This is a focused audit of sensitivity claims, not a new full correspondence review or proof campaign. No native/container calls or shared/model/product edits were made. The retry_replay observation predicate was inspected only for this narrow pattern; its full model/provider fidelity is not reviewed here. fhir_tasks had no binding file in this inventory and remains a separate review.

## Finding and correction

The inherited temporal_clock changed-final-coordinate control had compared an edited result only with the original result; that credit was correctly withdrawn in clock-observation-erratum.md. Existing data agreements and three actual product mutants do not repair that control on their own. Current code derives expected_state/rev from model inputs and expected_views, requires original windows equal those views, then rejects the edited coordinate against the same expected views. This directly addresses the failure mode.

The audit found one additional weaker claim in aql_frontend: compare(change=True) originally changed expected expr to changed rather than changing actual translated cy. Its NOTES called this a changed deciding observation. It exercised oracle/query-check sensitivity, not an altered observed translation. Root accepted this distinction, changed the actual cy output instead, retained input-derived expr/bounds/bindings, and documented old oracle-only credit versus its replacement. Existing two real lexer/null product mutants, formal model and proof counts are unchanged. No product defect or new proof gain follows.

I inspected the final change at binding.py:26 and the explanatory NOTES addition. Independently copied the bounded AQL package/helper into `/Users/ziniuw/.cache/g5-verification/ivg-fhir-independent-nztdvrgb/aql-final` and ran its actual100-case binding: AGREES, zero mismatches, all three detections true, elapsed0.934s subprocess. Cypher execution remains a recording endpoint; this is no native or SQL result proof. The scratch receipt is `results/aql_frontend/20261115T183402Z-binding/receipt.json` under that copied verification tree.

## Comparison-path audit

No remaining active control was found whose sole deciding test is literal edited!=original with neither an input-derived predicate nor a separately asserted expected baseline. AST extraction of detection assignments and contextual source inspection gave:

| Packages | Actual comparison / expected relation |
|---|---|
| embedded_no_data, temporal_window_reader | changed count compared with spec_execute/spec_scenario, original and mutant run through same compare |
| freshness_stamp, index_declaration | mutated observation compared with expect/spec_plan derived from token/catalog input |
| route_recheck, rel_prop_text | changed trial tuple/classification compared with computed next-route/spec text classification |
| reconstruction, history_diff, ledger_apply | changed state/diff/prior compared with source input fold or expected endpoints/records |
| node_read, ndjson_import | typed values/counters compared with expected input-value and expected stream contract |
| edge_acceptance, bulk_delete | changed count/live state compared with expected operation/input/state outcomes |
| bulk_children | changed public value rejected by public_check over persisted reader input; producer final-state conformance separately compared with expected prestate/batch fold |
| fusion_ranking, vector_threshold, pagerank_admission | changed IDs/scores compared with rational rank sum, threshold/filter result or input node census |
| procedure_results | changed column sent through actual public observe/equal comparison against source-derived expect |
| service_health | changed HTTP status requires original==expected_cypher(profile) and changed!=same expected; product variants compare expected named-provider outcomes |
| snapshot_routes, temporal_restore | changed vector/attr rejected by complete_values/expected EVENT projection; both originals accepted |
| temporal_clock | repaired coordinate compared with expected_views from model-produced maps |
| retry_replay draft | changed final timestamp rejected by the same case.agrees input oracle for prefix effect, full fallback and final window maps; base.agrees must also hold |
| history_paging | changed seqs compared with a fresh expected(ROWS,...); cursor-truthiness product variant additionally relies on explicit literal baseline and verdict gating |
| aql_frontend | corrected actual cy text compared with unchanged input-derived depth/expression and public forwarding expectations |

Two superficially suspicious baseline comparisons are meaningful within their existing evidence:

- node_read: missing_final_column_decode compares bad rows with out.rows, but immediately prior assert fixes out to literal float0.95/int29/string0.95 with exact types. The broad value panel also checks expected(v). This is not free-form baseline inequality.
- history_paging: converted_cursor_truthiness compares actual mutated result with coercions[1].result, but coercion_ok requires exact integer0 descending page[6,5]/next5 and raw string0 empty page/nextNone, and the final verdict requires coercion_ok. A false baseline cannot receive AGREES through that detection alone.

The history_paging changed_final_revision test edits a copy of the independently computed expected page rather than an actual public result. Its comparison is still against a fresh source-derived expected page, so it is not the withdrawn edit-only inequality; qualify it as oracle-comparator sensitivity. Its actual cursor/actor mutants and actual matrix independently test product behavior. No stronger native/whole-member claim is justified by any edited-observation control.

## Read-only replay of current oracles against retained receipts

Extracted only selected AST function/constant nodes; no imports of native harness modules and no main/connect function execution. `/Users/ziniuw/.cache/g5-verification/ivg-fhir-independent-nztdvrgb/observation-oracles.py/json` records baseline accepted AND altered rejected for:

- temporal_clock current1564-case receipt182957: recomputed model maps/views for a retained native-available bulk-zero tenant case, then changed final timestamp field;
- snapshot_routes receipt171758 normal route widths/vectors, then changed vector coordinate;
- temporal_restore receipt175727 restored typed-attr projection, then changed numeric-text attr;
- node_read receipt053327 exact typed scalar result against the literal expected tuple;
- history_paging receipt171553 raw cursor0/string0 results against their literal expected pages. Product mutant was inspected, not rerun by this pure replay.

All five checks agree; elapsed0.0279s. First replay searched for the default-graph bulk-zero case, which is not retained in the matrix (bulk panel uses tenant), and raised StopIteration before any verdict. That failed selection is preserved in observation-oracles-initial.stderr. The corrected selection uses retained tenant input and derives its oracle with that same input; no expectations were changed to match a result.

Replay: `python3 /Users/ziniuw/.cache/g5-verification/ivg-fhir-independent-nztdvrgb/observation-oracles.py`. The inventory JSON beside it records25 binding source hashes and AST detection assignments:24 initially active plus the new retry_replay draft. Raw AQL command/log and copied source/receipt are retained in aql-final. This review measured local execution only; token/cache/currency and solver CPU are unavailable.

## Limits and disposition

This closes the requested literal edit-only pattern audit for the24 initially active binding files and the new retry_replay observation predicate. It does not verify arbitrary oracle correctness, model completeness, provider implementations, domain prevalence, historical receipts or every surrounding claim. Imported controls with other filenames and future/unfrozen packages are outside this focused inventory. Sealed7's clock observation credit and AQL's old altered-observation label remain withdrawn/qualified; the fresh replacements are bounded comparator evidence, not new behavior coverage or product repair.
