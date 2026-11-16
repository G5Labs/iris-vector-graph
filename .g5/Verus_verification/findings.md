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
| [bug-cyp-102](bugs_issues.md#bug-cyp-102) A boolean equality also matches stored integers 1 and 0, beyond the legacy strings the known issue names | Medium · Open | 16 (cloud continuation) | e2e reproduced on the run-isolated IRIS fixture, with integer and boolean neighbors |
| [bug-cyp-103](bugs_issues.md#bug-cyp-103) A relationship property that is not a number orders as one against a number literal | Medium · Open | 17 (cloud continuation) | e2e reproduced on the run-isolated IRIS fixture, with node and numeric neighbors |
| [bug-cyp-104](bugs_issues.md#bug-cyp-104) ORDER BY sorts an empty-string property with the nulls on the native executor and first on the SQL path | Medium · Open | 18 (cloud continuation) | e2e reproduced on the run-isolated IRIS fixture, SQL and native answers to one query |
| [bug-cyp-105](bugs_issues.md#bug-cyp-105) A string predicate matches a node property stored as a number by its digits | Low · Open | 20 (cloud continuation) | e2e reproduced on the run-isolated IRIS fixture, with string and typed-comparison neighbors |
| [bug-cyp-106](bugs_issues.md#bug-cyp-106) IN lists compare a property's text with each value's spelling, so they disagree with = on nodes and relationships | Medium · Open | 23 (cloud continuation) | e2e reproduced on the run-isolated IRIS fixture, with near-spelling and numeric neighbors |
| [bug-cyp-107](bugs_issues.md#bug-cyp-107) coalesce over a relationship property returns its stored text, and a boolean as '1' | Low · Open | 24 (cloud continuation) | e2e reproduced on the run-isolated IRIS fixture, with node neighbors |
