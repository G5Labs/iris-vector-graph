# Verifier-unit count audit

Dated 2026-11-15T21:15:44.428848+00:00. This is a label correction, not a new product/model finding or withdrawn theorem. Stable source/model/manifest bytes, verifier totals, controls, raw receipts and sealed archives are unchanged. Root owns correction of current prose/ledgers with a dated note; preserved historical snapshots are not rewritten.

| Package | Source proof declarations | Recursive spec checks | nonlinear_arith subqueries | Total |
|---|---:|---:|---:|---:|
| ppr_walk |68 (30 named theorems+38 helpers)|18|17|103|
| fusion_ranking |7|2|2|11|
| iteration10 new PPR+Cost |108|21|17|146|

The old PPR “35 recursive-spec checks” combined18 recursive checks with17 nonlinear assertion subqueries. The old iteration10 “38 spec termination” similarly combined21 with17. The extra nonlinear queries are neither recursive-spec checks nor additional source proof declarations/independent behavioral guarantees. The existing fusion11 total is already right; the correct decomposition is7+2+2, not10 or7+4 recursion. Its current NOTES/manifest did not state the erroneous recursive split.

Evidence is explicit source plus verifier attribution, not a difference inferred solely from103−68. The scanner masks comments/literals, records each proof/spec declaration, each decreasing self-recursive spec, and every explicit by(nonlinear_arith) site with line number. Exact source copies and model manifests are preserved in count-audit-scratch/inputs/models/. Full baselines and isolated function outputs use the unchanged pinned verifier,4threads, ordinary flags.

The37 stable .rs source files were scanned; moving vector_admission and weighted_fraction were excluded entirely. Only PPR17 and fusion2 contain explicit nonlinear_arith. No active iteration11 model was inspected or replayed for this audit. This scan does not assert all unrelated historical accounting perfect or rerun every old model.

## PPR recursive declarations independently checked

| Spec function | Source line | Isolated verified units | Raw log |
|---|---:|---:|---|
| scoped |22|1|[log](count-audit-scratch/logs/ppr_walk/scoped.log)|
| valid_seeds |25|1|[log](count-audit-scratch/logs/ppr_walk/valid_seeds.log)|
| copies |29|1|[log](count-audit-scratch/logs/ppr_walk/copies.log)|
| hops |30|1|[log](count-audit-scratch/logs/ppr_walk/hops.log)|
| pos |39|1|[log](count-audit-scratch/logs/ppr_walk/pos.log)|
| sum |41|1|[log](count-audit-scratch/logs/ppr_walk/sum.log)|
| seed_add |43|1|[log](count-audit-scratch/logs/ppr_walk/seed_add.log)|
| ship |47|1|[log](count-audit-scratch/logs/ppr_walk/ship.log)|
| scatter |51|1|[log](count-audit-scratch/logs/ppr_walk/scatter.log)|
| delta |177|1|[log](count-audit-scratch/logs/ppr_walk/delta.log)|
| held |178|1|[log](count-audit-scratch/logs/ppr_walk/held.log)|
| iterate |180|1|[log](count-audit-scratch/logs/ppr_walk/iterate.log)|
| insert |285|1|[log](count-audit-scratch/logs/ppr_walk/insert.log)|
| rank |286|1|[log](count-audit-scratch/logs/ppr_walk/rank.log)|
| rows |287|1|[log](count-audit-scratch/logs/ppr_walk/rows.log)|
| sparse |288|1|[log](count-audit-scratch/logs/ppr_walk/sparse.log)|
| has |289|1|[log](count-audit-scratch/logs/ppr_walk/has.log)|
| missing |290|1|[log](count-audit-scratch/logs/ppr_walk/missing.log)|

All18 are actual source self-recursive specs with decreasing headers and each isolated run reports1 verified/0errors. Proof-function recursion/decreases is part of that proof body, not an extra spec check.

## Nonlinear-containing proof attribution

| Package / proof | Explicit nonlinear source lines | Body + nonlinear queries observed | Raw log |
|---|---|---:|---|
| ppr_walk/lemma_seed_add |93,95|3 =1+2|[log](count-audit-scratch/logs/ppr_walk/lemma_seed_add.log)|
| ppr_walk/theorem_initial_uniform_mass |102|2 =1+1|[log](count-audit-scratch/logs/ppr_walk/theorem_initial_uniform_mass.log)|
| ppr_walk/lemma_ship |134,136|3 =1+2|[log](count-audit-scratch/logs/ppr_walk/lemma_ship.log)|
| ppr_walk/lemma_scatter |157,161,162|4 =1+3|[log](count-audit-scratch/logs/ppr_walk/lemma_scatter.log)|
| ppr_walk/theorem_step_mass_from_raw_outgoing |174|2 =1+1|[log](count-audit-scratch/logs/ppr_walk/theorem_step_mass_from_raw_outgoing.log)|
| ppr_walk/theorem_iterated_mass |193|2 =1+1|[log](count-audit-scratch/logs/ppr_walk/theorem_iterated_mass.log)|
| ppr_walk/lemma_div_one |328|2 =1+1|[log](count-audit-scratch/logs/ppr_walk/lemma_div_one.log)|
| ppr_walk/theorem_zero_tolerance_does_not_stop_on_zero_change |396|2 =1+1|[log](count-audit-scratch/logs/ppr_walk/theorem_zero_tolerance_does_not_stop_on_zero_change.log)|
| ppr_walk/lemma_isolated3_recurrence |451,453|3 =1+2|[log](count-audit-scratch/logs/ppr_walk/lemma_isolated3_recurrence.log)|
| ppr_walk/theorem_recurrence_cap_fabricates_zero |469|2 =1+1|[log](count-audit-scratch/logs/ppr_walk/theorem_recurrence_cap_fabricates_zero.log)|
| ppr_walk/lemma_isolated_seed_scores_positive |600,606|3 =1+2|[log](count-audit-scratch/logs/ppr_walk/lemma_isolated_seed_scores_positive.log)|
| fusion_ranking/theorem_second_leg_changes_winner |53,54|3 =1+2|[log](count-audit-scratch/logs/fusion_ranking/theorem_second_leg_changes_winner.log)|

The12 nonlinear-containing proof functions across the two packages individually report exactly one body plus their source-listed nonlinear sites. Fusion rank and score individually report1 each; fusion theorem_second_leg_changes_winner reports3 (body+2queries). One nonlinear-free proof in each package independently reports1. Full original-source baselines report PPR103/0 and fusion11/0. All36 sequential scratch commands succeed, no timeout/resource/type/parse failures; measured wall45.233s.

Cost remains43new=40proof+3recursive+0nonlinear, with45 unchanged imported/rechecked JSON units. Therefore iteration10 new146=108proof+21recursive+17nonlinear; total191 including imported45 is unchanged. The draft fraction165 reported by its builder is not independently audited here and remains outside this pre-freeze scan.

Raw command vectors, expected/observed counts, exact source hashes, full stable-file inventory and individual outputs are in [count-audit-results.json](count-audit-results.json). The reproducible audit is [count-audit-run.py](count-audit-run.py); [stdout](count-audit-run.log) and all copied inputs/logs remain under count-audit-scratch. No shared/model/ontology/Git/native edit was made.

The builder and independent review both previously accepted the wrong PPR subtype label. This report owns that correction while preserving the valid103 result and its bounded mathematical/source correspondence claims.
