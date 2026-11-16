# Findings register — fresh iteration 13 audit

Git `eceb147d37720658e34b07f279cc267870fd393c`, product `3eaa79cf`. This audit changes registers and supporting ontology/evidence only. It does not change production behavior or the frozen seal.

| Register | Starting IDs | Reconciliation |
|---|---:|---|
| [Bugs](bugs_issues.md) | 434 | 42 e2e reproduced; 4 partial reproduced; 107 security-related source-only; 281 moved to the review record |
| [Simplifications](design_simplification.md) | 55 | 54 unsupported reduction claims withdrawn; 1 previously retired proposal retained |
| [Questions](open_questions.md) | 146 | 9 settled by existing authority; 121 owner decisions open; 2 historical reports; 14 qualified proof-debt records |

The [audit handoff](audits/register-20261115/README.md) records actual commands, positive neighbors, substituted dependencies, bounded refutations, caller-unreachability checks, environment blocks and incomplete regressions. Every original ID remains in its live register or the [bug review record](audits/register-20261115/bugs-review.md); [crosswalks](crosswalk/) now carry an explicit canonical_path. No human protection status was present at the start. No new human approval was inferred.

A passing audit regression means its recorded defect contrast and passing neighbor reproduced; it does not mean the product was repaired. A Verus repair/control pair is not a measured design simplification. Security entries remain explicitly outside active reproduction scope.

## Entries added after the audit

The audit table above keeps its own counts. Later iterations add entries here; `make_findings_index.py` deliberately
does not regenerate this file.

| Entry | Severity · status | Iteration | Reproduction |
|---|---|---|---|
| [bug-tmp-101](bugs_issues.md#bug-tmp-101) A temporal edge's internal mark is returned as relationship data by Cypher and written as an RDF qualifier | Low · Open | 15 (cloud continuation) | e2e reproduced on the run-isolated IRIS fixture, with plain and adopted neighbors |
