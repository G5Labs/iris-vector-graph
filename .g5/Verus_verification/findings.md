# Findings register — IVG initial Verus uplift (2026-11-13)

Product baseline `3eaa79cf`. The register covers every bug, design simplification and unresolved question found during intent recovery, modeling, native observation and the independent review rounds. Proposed repairs are not implemented: the product was read-only for this uplift. The [final report](../uplift/ivg-verus-initial/final-report.md) summarises them; statuses of the claims they affect are in the [coverage map](coverage.md).

| File | Entries | High | Medium | Low | Observations / drift | Natively reproduced |
|---|---:|---:|---:|---:|---:|---:|
| [Bugs and issues](bugs_issues.md) | 113 | 13 | 34 | 48 | 18 | 28 of 95 |
| [Design simplifications](design_simplification.md) | 19 | 2 | 6 | 10 | 1 | n/a |
| [Open questions](open_questions.md) | 56 | 1 | 19 | 36 | 0 | n/a |

How to read an entry: a bug cites the governing source of the expected behavior (**Expected**), what the baseline does (**Observed**) and the evidence (**Found by** — model witness, source review or reviewer — and **Reproduced by** — native probe receipt under `receipts/native/` or an upstream test). An entry whose product reachability was not shown natively says **Suspected** and its severity is one level lower than its consequence. A simplification states the proposal, why it helps, the behavior to preserve and a distinguishing case. A question states the evidence, the plausible interpretations and the decision needed.

## High-severity bugs

| ID | Domain | Finding | Native reproduction |
|---|---|---|---|
| [bug-001](bugs_issues.md#bug-001) | ledger/erasure/redaction | Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work | yes |
| [bug-002](bugs_issues.md#bug-002) | ledger/erasure/redaction | A redaction completes while its target's content is still uncommitted-deleted, and the caller's rollback brings the content back with its history tombstoned | yes |
| [bug-str-001](bugs_issues.md#bug-str-001) | graph structure | Deleting one of several parallel edges through the ledger removes the adjacency of the edges that remain | yes |
| [bug-str-002](bugs_issues.md#bug-str-002) | graph structure | A cached algorithm answer computed over a write that later rolls back stays current | yes |
| [bug-tmp-001](bugs_issues.md#bug-tmp-001) | temporal | A temporal write whose structural step fails keeps its raw entry, cannot be finished by a retry, and the bulk fallback reports it written | yes |
| [bug-tmp-002](bugs_issues.md#bug-tmp-002) | temporal | An update at an occupied temporal coordinate counts the edge twice in the statistics | yes |
| [bug-tmp-003](bugs_issues.md#bug-tmp-003) | temporal | A rolled-back temporal write leaves its statistics counted, so a retry counts the edge twice | yes |
| [bug-tmp-010](bugs_issues.md#bug-tmp-010) | temporal | A rolled-back temporal delete or node erase leaves the bucket's event counter decremented | yes |
| [bug-srch-001](bugs_issues.md#bug-srch-001) | search | Search indexes keep answering with content that was erased, and a re-created node inherits the erased text | yes |
| [bug-srch-002](bugs_issues.md#bug-srch-002) | search | A failed BM25 insert or delete rolls back the caller's whole transaction | yes |
| [bug-srch-007](bugs_issues.md#bug-srch-007) | search | Claiming the default embedding table for a model that already has a default-graph route makes that model's stored vectors unreadable | yes |
| [bug-plt-001](bugs_issues.md#bug-plt-001) | platform/access/install | The 4.0.0 documents migration can drop the documents table after its copy failed with a tolerated error | no — suspected |
| [bug-cyp-001](bugs_issues.md#bug-cyp-001) | Cypher | A caller with Cypher read access can forge a CRC-32 collision so that another shape's queries run its compiled code | no — suspected |

## Simplifications ranked High or Medium

| ID | Proposal |
|---|---|
| [simp-001](design_simplification.md#simp-001) | Claim the redaction marker for one run, under the head lock, before the first batch |
| [simp-cyp-001](design_simplification.md#simp-cyp-001) | Name each compiled Cypher class by its code's digest instead of the shape's CRC-32 |
| [simp-002](design_simplification.md#simp-002) | Put a relationship's endpoints in every relationship record so redaction never has to look them up |
| [simp-003](design_simplification.md#simp-003) | Derive redaction's liveness check from the eraser's store inventory |
| [simp-str-001](design_simplification.md#simp-str-001) | Delete a relationship through one Eraser path, whatever the caller |
| [simp-srch-001](design_simplification.md#simp-srch-001) | One fusion function with an explicit absent-rank rule and per-leg failure reporting |
| [simp-plt-001](design_simplification.md#simp-plt-001) | Enforce strict ledger mode once, on the server, instead of in each Python engine |
| [simp-cyp-002](design_simplification.md#simp-cyp-002) | Carry each node binding's graph through Cypher translation instead of correlating graphs by regex afterwards |

## Decisions needed (High and Medium questions)

| ID | Question |
|---|---|
| [q-004](open_questions.md#q-004) | Must erasure and redaction be serialised with each other and with ledger commits? |
| [q-001](open_questions.md#q-001) | Should another tenant's retry of a revision it shared with a redacted tenant be refused? |
| [q-003](open_questions.md#q-003) | How should strict mode and the erase-then-redact path fit together? |
| [q-008](open_questions.md#q-008) | Should erase-by-prefix and redact-by-prefix use the same prefix rule? |
| [q-009](open_questions.md#q-009) | Should redaction count a target's temporal-only edges as live content? |
| [q-010](open_questions.md#q-010) | Should post-commit properties be recorded, excluded from verify, or documented as unrecorded writes? |
| [q-str-001](open_questions.md#q-str-001) | How should an install that already holds a graph named "0", or one with a control character, find and migrate it? |
| [q-tmp-001](open_questions.md#q-tmp-001) | Must temporal writes stay exact when several writers touch the same coordinates or triple at once? |
| [q-srch-001](open_questions.md#q-srch-001) | Should quarantined vectors and documents survive erasure indefinitely? |
| [q-plt-001](open_questions.md#q-plt-001) | Is strict mode promised from the moment set_strict returns, or within a few seconds for other engines? |
| [q-plt-002](open_questions.md#q-plt-002) | Can an explicitly named schema be recorded over another schema's interrupted first setup? |
| [q-plt-003](open_questions.md#q-plt-003) | Should the server refuse to start on a reachable address with no key and a superuser login? |
| [q-plt-004](open_questions.md#q-plt-004) | What should a restore do when the namespace already has a live ledger? |
| [q-plt-005](open_questions.md#q-plt-005) | Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger? |
| [q-plt-006](open_questions.md#q-plt-006) | Should whether a write joins the caller's transaction depend on how the engine was opened? |
| [q-plt-007](open_questions.md#q-plt-007) | Can a default-graph algorithm call use a native reader once a named graph holds edges? |
| [q-plt-008](open_questions.md#q-plt-008) | Which write paths must strict mode govern beyond the engine's methods, and how is each classified? |
| [q-cyp-001](open_questions.md#q-cyp-001) | When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it? |
| [q-led-005](open_questions.md#q-led-005) | Should callers be able to choose a commit's kind? |
| [q-plt-019](open_questions.md#q-plt-019) | May the server or the client retry a call that writes? |

## Sources of the findings

- Stage A intent notes: [`intent/`](../uplift/ivg-verus-initial/intent/) and the fresh-reader [reconstruction check](../uplift/ivg-verus-initial/reconstruction-check.md).
- Models and their NOTES: [`models/`](models/) (ledger_redaction, graph_structure, temporal, search, platform).
- Native observations: [`receipts/native/`](receipts/native/) ([sources](receipts/native/SOURCES.txt)).
- Independent review rounds: [`review/`](../uplift/ivg-verus-initial/review/); adjudications in the [uplift plan](../uplift/ivg-verus-initial/uplift-plan.md).
