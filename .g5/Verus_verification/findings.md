# Findings register — IVG Verus uplift, consolidated (2026-11-14)

Product baseline `3eaa79cf`. The register covers every bug, design simplification and unresolved question found during intent recovery, modeling, native observation and the independent review rounds. Proposed repairs are not implemented: the product was read-only for this uplift. The consolidated uplift (2026-11-14) imported every playbook-arm finding, root cause and decision; each source ID maps to one entry in the [crosswalk](crosswalk/). The [final report](../uplift/ivg-verus-initial/final-report.md) summarises them; statuses of the claims they affect are in the [coverage map](coverage.md).

| File | Entries | High | Medium | Low | Observations / drift | Natively reproduced |
|---|---:|---:|---:|---:|---:|---:|
| [Bugs and issues](bugs_issues.md) | 432 | 48 | 130 | 223 | 31 | 242 of 401 |
| [Design simplifications](design_simplification.md) | 55 | 16 | 25 | 13 | 1 | n/a |
| [Open questions](open_questions.md) | 146 | 1 | 23 | 42 | 16 | n/a |

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
| [F-0304](bugs_issues.md#F-0304) | playbook: writes | Storing an edge over a marked edge does not take the edge over | yes |
| [F-0409](bugs_issues.md#F-0409) | playbook: adjacency | A failed adjacency rebuild inside a caller's transaction rolls back the caller's work | yes |
| [F-0505](bugs_issues.md#F-0505) | playbook: temporal | The marker test differs between the deleters and the ledger | yes |
| [F-0606](bugs_issues.md#F-0606) | playbook: vectors | Erasure leaves IVF, tree and PLAID indexes holding an erased graph's ids and vectors | yes |
| [F-0702](bugs_issues.md#F-0702) | playbook: text search | Erasure leaves BM25 indexes holding an erased graph's terms and node ids | yes |
| [F-0705](bugs_issues.md#F-0705) | playbook: text search | An index with no recorded graph is read as the default graph's own index | yes |
| [F-0707](bugs_issues.md#F-0707) | playbook: text search | Under USE GRAPH, BM25 calls do not check that the index was built for that graph | yes |
| [F-0711](bugs_issues.md#F-0711) | playbook: text search | TextSearchEngine answers across graphs and cannot reach iFind | yes |
| [F-0802](bugs_issues.md#F-0802) | playbook: Cypher | Text shortcuts answer by substring and ignore USE GRAPH | yes |
| [F-0814](bugs_issues.md#F-0814) | playbook: Cypher | AQL text values are pasted into the Cypher text, and execute_aql ignores read-only | yes |
| [F-0815](bugs_issues.md#F-0815) | playbook: Cypher | A dotted function name pastes raw text into the SQL | yes |
| [F-0816](bugs_issues.md#F-0816) | playbook: Cypher | Schema procedures ignore USE GRAPH | yes |
| [F-0818](bugs_issues.md#F-0818) | playbook: Cypher | A variable-length walk in an all-graphs read can cross graphs | yes |
| [F-0820](bugs_issues.md#F-0820) | playbook: Cypher | kg_GRAPH_PATH reads every graph | yes |
| [F-1002](bugs_issues.md#F-1002) | playbook: algorithms | random_walk needs the Arno library for an ObjectScript walk, and walks every graph's edges | yes |
| [F-1008](bugs_issues.md#F-1008) | playbook: algorithms | Variable-length expansion's every-graph mode walks across graphs | yes |
| [F-1101](bugs_issues.md#F-1101) | playbook: ledger | A replayed commit writes its post-commit properties again | yes |
| [F-1114](bugs_issues.md#F-1114) | playbook: ledger | Erasure changes the statement maps without the head lock | yes |
| [F-1302](bugs_issues.md#F-1302) | playbook: redaction | Redaction can tombstone history of content a concurrent commit made live (unlocked start, late marker) | yes |
| [F-1305](bugs_issues.md#F-1305) | playbook: redaction | A graph-per-tenant redaction with unprefixed ids reports success while the tenant's node history remains | yes |
| [F-1306](bugs_issues.md#F-1306) | playbook: redaction | A retried commit re-applies post-commit properties and revives erased content | yes |
| [F-1402](bugs_issues.md#F-1402) | playbook: replay | A reader can return a partially redacted view | yes |
| [F-1502](bugs_issues.md#F-1502) | playbook: integrations | A reifier node always lands in the default graph, and erasing the edge's graph leaves it (with its properties) live | yes |
| [F-1503](bugs_issues.md#F-1503) | playbook: integrations | delete_reification deletes any id's node, labels and properties in every graph without checking it is a reifier | yes |
| [F-1603](bugs_issues.md#F-1603) | playbook: interfaces | The generated GraphQL server mixes graphs in one answer | yes |
| [F-1604](bugs_issues.md#F-1604) | playbook: interfaces | The sample API's biomedical fields and its update mutation ignore graphs | yes |
| [F-1701](bugs_issues.md#F-1701) | playbook: operations | The SQL adapter's unscoped node and label reads merge graphs | yes |
| [F-1801](bugs_issues.md#F-1801) | playbook: snapshot | A replacing restore lays the archive's ledger over the live one | yes |
| [F-C1250](bugs_issues.md#F-C1250) | playbook: erasure | An rdf_edges row a %NOINDEX bulk load wrote survives delete_nodes_by_prefix of both its endpoints and EraseAll+PurgeAll until the indices are rebuilt; its endpoint nodes are deleted under it | yes |
| [F-C1306](bugs_issues.md#F-C1306) | playbook: redaction | After a 4.5.x upgrade to a non-default IVG Schema, Graph_KG.ledger_revisions keeps the tenant's messages, sources, correlation ids and idempotency keys, which redaction never clears | yes |
| [F-C1350](bugs_issues.md#F-C1350) | playbook: redaction | Redaction batches tombstone the history of content a ledger-bypassing writer made live after the run's entry check | yes |
| [F-C1351](bugs_issues.md#F-C1351) | playbook: redaction | The redaction's liveness check misses rows a bulk load wrote with %NOINDEX: the redaction completes while the tenant's rows exist, and they reappear at the next index rebuild | yes |
| [F-C1803](bugs_issues.md#F-C1803) | playbook: snapshot | Graph.KG.Snapshot's unused file helpers read, write and delete server files for any Native API caller | yes |
| [F-C1804](bugs_issues.md#F-C1804) | playbook: snapshot | A snapshot carries no routed edge vectors (kg_eemb_ tables): a restore loses them silently | yes |
| [F-C1850](bugs_issues.md#F-C1850) | playbook: snapshot | A replacing restore leaves the live ledger's redaction stores in place: a marked target comes back live, and a second redaction of a restored tenant keeps its revision text and retry key | yes |

## Simplifications ranked High or Medium

| ID | Proposal |
|---|---|
| [simp-001](design_simplification.md#simp-001) | Claim the redaction marker for one run, under the head lock, before the first batch |
| [simp-cyp-001](design_simplification.md#simp-cyp-001) | Name each compiled Cypher class by its code's digest instead of the shape's CRC-32 |
| [RC-01](design_simplification.md#RC-01) | Graph scope is added by hand to each statement |
| [RC-02](design_simplification.md#RC-02) | Stored facts whose key omits the graph |
| [RC-03](design_simplification.md#RC-03) | Removal reach is not derived from a declared store inventory |
| [RC-04](design_simplification.md#RC-04) | Erase, ledger commits and redaction start are not serialized on the ledger head lock |
| [RC-07](design_simplification.md#RC-07) | Multi-call readers have no consistency protocol |
| [RC-08](design_simplification.md#RC-08) | The ledger is not the single writer of governed content |
| [RC-09](design_simplification.md#RC-09) | Retries re-execute effects the idempotency record does not cover |
| [RC-11](design_simplification.md#RC-11) | IVG ObjectScript writers roll back their caller's transaction |
| [RC-16](design_simplification.md#RC-16) | The Cypher and AQL translators have no reference semantics |
| [RC-19](design_simplification.md#RC-19) | Query text is built by pasting values |
| [RC-20](design_simplification.md#RC-20) | No server-side authorization or exposure boundary |
| [RC-22](design_simplification.md#RC-22) | Derived-row marks are ordinary qualifier keys with no single predicate |
| [RC-25](design_simplification.md#RC-25) | Restore writes stores directly instead of through their owners |
| [RC-35](design_simplification.md#RC-35) | Bulk loads bypass the indexes and key checks every other path relies on |
| [simp-002](design_simplification.md#simp-002) | Put a relationship's endpoints in every relationship record so redaction never has to look them up |
| [simp-003](design_simplification.md#simp-003) | Derive redaction's liveness check from the eraser's store inventory |
| [simp-str-001](design_simplification.md#simp-str-001) | Delete a relationship through one Eraser path, whatever the caller |
| [simp-srch-001](design_simplification.md#simp-srch-001) | One fusion function with an explicit absent-rank rule and per-leg failure reporting |
| [simp-plt-001](design_simplification.md#simp-plt-001) | Enforce strict ledger mode once, on the server, instead of in each Python engine |
| [simp-cyp-002](design_simplification.md#simp-cyp-002) | Carry each node binding's graph through Cypher translation instead of correlating graphs by regex afterwards |
| [RC-05](design_simplification.md#RC-05) | Unlocked read-modify-write of shared facts outside the ledger |
| [RC-06](design_simplification.md#RC-06) | Derived stores and caches have no reliable staleness signal |
| [RC-10](design_simplification.md#RC-10) | A command's writes are not one validated, all-or-nothing unit |
| [RC-12](design_simplification.md#RC-12) | Environment premises are asserted, not validated |
| [RC-13](design_simplification.md#RC-13) | The IVG Schema name is not resolved from one source |
| [RC-14](design_simplification.md#RC-14) | Failures are swallowed into empty, default or success answers |
| [RC-17](design_simplification.md#RC-17) | Stored values carry no type |
| [RC-18](design_simplification.md#RC-18) | Domain codes, units and metrics are untyped |
| [RC-21](design_simplification.md#RC-21) | Edge identity for parallel edges is not one rule |
| [RC-23](design_simplification.md#RC-23) | Results depend on storage order or join multiplicity |
| [RC-24](design_simplification.md#RC-24) | Identity by a non-injective checksum |
| [RC-26](design_simplification.md#RC-26) | Vector identity is enforced per seam and fails open |
| [RC-27](design_simplification.md#RC-27) | Input validation is per entry point, not at the shared write boundary |
| [RC-28](design_simplification.md#RC-28) | Resource bounds are not declared |
| [RC-29](design_simplification.md#RC-29) | Parallel implementations of one operation diverge |
| [RC-30](design_simplification.md#RC-30) | Progress is not designed for resumable or queued work |
| [RC-32](design_simplification.md#RC-32) | Test, packaging and deploy tooling diverges from the product |
| [RC-33](design_simplification.md#RC-33) | Stated refusals, options and protocol verbs are accepted and ignored |
| [RC-36](design_simplification.md#RC-36) | Server answers are hand-encoded text decoded by patterns |

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
| [q-iter-006](open_questions.md#q-iter-006) | Should the sample API retry construction after a startup outage? |
| [q-iter-004](open_questions.md#q-iter-004) | Should standalone handled metadata calls expose YIELD aliases as result columns? |
| [q-iter-005](open_questions.md#q-iter-005) | Should handled WHERE validation happen when no rows exist? |
| [q-iter-003](open_questions.md#q-iter-003) | Should history text filters use binary identity or the current database comparison? |

## Sources of the findings

- Stage A intent notes: [`intent/`](../uplift/ivg-verus-initial/intent/) and the fresh-reader [reconstruction check](../uplift/ivg-verus-initial/reconstruction-check.md).
- Models and their NOTES: [`models/`](models/) (ledger_redaction, graph_structure, temporal, search, platform).
- Native observations: [`receipts/native/`](receipts/native/) ([sources](receipts/native/SOURCES.txt)).
- Independent review rounds: [`review/`](../uplift/ivg-verus-initial/review/); adjudications in the [uplift plan](../uplift/ivg-verus-initial/uplift-plan.md).
