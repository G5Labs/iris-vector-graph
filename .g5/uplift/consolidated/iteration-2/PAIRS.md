# Iteration 2: builder-selected decisions

Before: `d087503753ee4e7369d52dae860bf9059e4526ab`; product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. This is a purposive builder sample, not an independent holdout or a repository estimate. Selection started with test names and documented workflows in scarcely modeled readers. Public feedback was already known. No evaluator cases were opened. All rows, including deferred work and initial misses, stay here.

## Initial rotating sample, before implementation lookup

| ID | Source of selection | Two reachable situations and caller observation | Prediction from inherited canonical ontology | Inherited formal boundary | Selection |
|---|---|---|---|---|---|
| B2-01 | Public M03; integration rollback test | Create n, write k=1 then k=2: revision reader sees (absent,1),(1,2), table reads 2. Add a relationship to an unknown endpoint after a successful prefix: error names its index, no prefix or revision persists. | Both stated by ledger.commit. | pa3 copies supplied records; no operation failure/prior producer. | Repair priority; model raw operations through transaction and revision reader. |
| B2-02 | ledger reconstruction/export API and unit test family | Same requested revision, final graph fits the bound: history never over limit vs history grows above it then shrinks. Does ordinary reconstruction return both, while streaming/export return both? | ledger.readers states the bound but does not locate it in the fold. Initial prediction: final size decides; uncertain. | No named reconstruction contract. | Follow the record consumer; retain this initial miss. |
| B2-03 | Fusion workflow sampled beside test_227_retrieve_projection | An entity occurs in both ranked lists vs only one; caller's fused score/rank changes. Original score magnitudes change with positions fixed: RRF result should not change. | search.fusion predicts rank contributions, but no exact owner for exported Python helper or duplicate entries. | No active fusion claim. | Independent selection of another domain; trace raw lists, helper and detailed consumer. |
| B2-04 | test_470_call_yield_where | After CALL, score 0 versus null under NOT(score > 0): first row passes, null row is dropped. Alias names must survive to RETURN. | General conformance only; no exact local rule. | No producer-to-handler contract. | Deferred; parser, evaluator and both execution routes exceed this batch. |
| B2-05 | test_temporal_engine_polish | Empty bulk deletion versus one real node with no relationship: DeleteResult(0,0) versus (1,0), with int/bool conversions based on nodes. | Structure delete exists, detailed count conversions absent. | No result conversion contract. | Retain as unmodeled; revisit a different area before seal. |

## States and commands being strengthened

- Ledger application: absent/present node; absent/same/changed property; absent/present relationship; create, label, set, create relationship; stop at first refusal; publish success or roll back; read revision records. Other ledger operations remain outside this new model.
- Reconstruction: record contributes or not; node/relationship exists or not; each prefix at/below/above effective bound; named revision selector; ordinary/stream/export readers. Properties and labels do not affect entity count. Streaming is delivery from a fully folded graph.
- Fusion: entity absent/first/repeated in a leg; no/one/several legs; rank-derived scores; successful/failed vector, text and graph providers; detail reader and k limit. Provider ranking correctness, graph isolation and floating point accuracy remain outside this model.

Final observations, controls, policy reconciliation and stopping review are appended before seal. No self-grade of private cases is made.
