# Simplification comparisons — fresh register audit

All 55 starting IDs reviewed. No product design was changed. 54 unsubstantiated simplification claims are withdrawn; the already retired counterproposal stays retired. This does not reject a possible repair. Counts below are measured declarations or recorded solver queries, never states or a whole-product complexity estimate.

<a id="simp-001"></a>
### simp-001

Preserve: resuming the same target after a pause, error or process death; refusing a different target while one is unfinished; a re-run of a finished target writes nothing and leaves no marker; readers and target commits refused only while a run is unfinished; batches still release the head lock between transactions.

Decision and cost: The prose token/takeover protocol adds identity and recovery checks. The actual repaired flag only changes admission guards; Run.started remains in the model.

Actual Verus comparison: `{"metric": "declared model schema; shared by both variants", "as_built": {"St_fields": 12, "Run_fields": 4, "Action_variants": 9}, "proposed": {"St_fields": 12, "Run_fields": 4, "Action_variants": 9}, "removed": 0, "qualification": "Measured declarations, not independent states. Same Run.started and all nine action alternatives remain. Witnesses change Variant flags; prose run-token/inventory API is not modeled. Sequences/maps/sets have unbounded mathematical domains; no reachable-state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-cyp-001"></a>
### simp-cyp-001

Preserve: one class per shape and layout; interpreted until built; R311's digest check; a deploy and `Gen.DropAll()` still discard every class.

Decision and cost: Digest/sequence identity adds class lifetime, collision and stale-layout binding obligations; entry/class matching cannot simply disappear.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-01"></a>
### RC-01

Preserve: Default/named/all-graph results and scoped writes, including optional null rows and parallel edges.

Decision and cost: A scoped query layer must represent the current exceptional calls and composite joins; every adapter and SQL escape hatch still needs binding evidence.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-02"></a>
### RC-02

Preserve: Existing node/edge identity, replay, diff, redaction target attribution and old archive readability.

Decision and cost: Adding graph keys changes records, hashes and migration/read compatibility; attribution moves into every writer and the migration boundary.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 118, "reviewed": 118, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-03"></a>
### RC-03

Preserve: Removal reach and retained configuration, separator-aware targets and truthful receipts.

Decision and cost: An inventory generator needs complete writer/store discovery, versioned hooks and tests; completeness is a new central obligation, not an eliminated one.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 92, "reviewed": 92, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-04"></a>
### RC-04

Preserve: Nested transactions, concurrent unrelated targets, and required erase/redact refusal.

Decision and cost: The shared lock must cover all writers with a lock-order and progress proof; it adds contention and cannot repair dirty-read isolation by naming a lock alone.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 159, "reviewed": 158, "removed": 1, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-07"></a>
### RC-07

Preserve: Consistent multi-call results with bounded readers and existing refusal behavior.

Decision and cost: A snapshot/version protocol adds retries or locks and needs starvation, crash and incomplete-read handling; reader consistency has not disappeared.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 159, "reviewed": 158, "removed": 1, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-08"></a>
### RC-08

Preserve: All documented strict-mode exemptions, ledger writes, refusal errors and transaction nesting.

Decision and cost: Server ownership needs a bypass-writer census and capability context; centralized admission adds a trusted boundary and deployment/compatibility work.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 111, "reviewed": 111, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-09"></a>
### RC-09

Preserve: The original keyed outcome and no duplicate external effect, including ambiguous replies.

Decision and cost: A durable effect/outcome record adds state, recovery and retention rules; an unknown-outcome response changes client interfaces.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 159, "reviewed": 158, "removed": 1, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-11"></a>
### RC-11

Preserve: Caller-owned transaction levels and only the failed operation being undone.

Decision and cost: A shared helper still needs accurate started-level tracking at every ObjectScript caller and process-death behavior; helpers do not remove transaction obligations.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 118, "reviewed": 118, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-16"></a>
### RC-16

Preserve: Supported clause semantics, typed values, graph scope and refusal of unsupported forms.

Decision and cost: A reference evaluator adds an independent semantics maintenance burden and coverage domain; it is additional verification, not a smaller product model.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 118, "reviewed": 118, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-19"></a>
### RC-19

Preserve: Accepted ordinary literals and identifiers, query parameters and requested read-only behavior.

Decision and cost: Binding and name validation need separate identifier/value APIs and complete translator coverage; this is a security repair candidate, source review only.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-20"></a>
### RC-20

Preserve: Documented namespace privileges, graph collision-avoidance semantics and existing operator controls.

Decision and cost: Authorization moves into server middleware/executors and needs deployment and credential compatibility; source-only security scope, no new reproduction.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 118, "reviewed": 118, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-22"></a>
### RC-22

Preserve: Explicit edges survive temporal cleanup and inferred/derived provenance stays distinguishable.

Decision and cost: A shared marker predicate still needs a reserved-key policy, old-data handling and writers that cannot forge or misclassify marks.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 111, "reviewed": 111, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-25"></a>
### RC-25

Preserve: Archive readability, intended merge/replace behavior, per-store ownership and honest partial failures.

Decision and cost: Owner hooks need archive versioning and transaction/refusal interfaces; the proposal transfers import correctness to each store.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 92, "reviewed": 92, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-35"></a>
### RC-35

Preserve: Bulk load throughput, declared chunk commits, constraints and rebuilt indexes on every graph.

Decision and cost: Index/key maintenance or staging adds load-time checks and rebuild recovery; omitting them is a behavior change, not a simplification.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-002"></a>
### simp-002

Preserve: the canonical form and digest of every existing record (old records keep their layout; the reader must accept both); replay and diff results; the record count of a commit if the create-on-assign variant is chosen must be documented.

Decision and cost: Endpoint-bearing records add stored fields and old-record branches. Knowledge lookup may shrink only if legacy layouts, record hashes and record-count compatibility are accounted for.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-003"></a>
### simp-003

Preserve: the separator boundary (`acme` is not blocked by live `acme-health|` rows); the refusal message naming the stores that are live; a target whose content was erased is not refused.

Decision and cost: One inventory owns completeness and hook coverage. Full liveness adds checked stores and refusal cases rather than eliminating the content-ownership decision.

Actual Verus comparison: `{"metric": "declared model schema; shared by both variants", "as_built": {"St_fields": 12, "Run_fields": 4, "Action_variants": 9}, "proposed": {"St_fields": 12, "Run_fields": 4, "Action_variants": 9}, "removed": 0, "qualification": "Measured declarations, not independent states. Same Run.started and all nine action alternatives remain. Witnesses change Variant flags; prose run-token/inventory API is not modeled. Sequences/maps/sets have unbounded mathematical domains; no reachable-state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-str-001"></a>
### simp-str-001

Preserve: `delete_edge`'s return value and graph scoping; the ledger's record of the delete in the same transaction; Cypher's per-graph correlation of the deleted rows; nesting in a caller's transaction.

Decision and cost: The Eraser API must preserve ledger recording, keyed edge selection, caller transactions and returned counts. Each caller still needs a correspondence check.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-srch-001"></a>
### simp-srch-001

Preserve: per-graph scoping of each leg; the empty-text skip; the default `c`.

Decision and cost: A common fusion API needs leg-failure and absent-rank policy, corpus choice, weights, duplicate/tie semantics and compatibility adapters; no replacement is modeled.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-plt-001"></a>
### simp-plt-001

Preserve: the documented exemptions (BulkLoader, raw SQL, the marked temporal row), the rejection counter, the ledger's own writes, and the error type `LedgerStrictModeError` at the Python surface.

Decision and cost: A server gate needs a complete exemption/writer list, nested-transaction behavior and Python error mapping; the five-second client cache vanishes only after those obligations are supplied.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-cyp-002"></a>
### simp-cyp-002

Preserve: the plans IRIS gets when only one graph exists (`translator.py:783-785`), the LEFT JOIN null-row placement (`:730-733`), and every row of the e2e write matrix.

Decision and cost: Graph-bearing AST bindings add types and per-join null-placement rules; late regex decisions move into translation, with no proposed Verus AST/SQL model.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-05"></a>
### RC-05

Preserve: Concurrent updates without lost facts and the same public error/rollback contracts.

Decision and cost: A shared lock or atomic primitive requires per-key ownership, failure cleanup and competing-writer coverage; serialization costs remain at the storage boundary.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-06"></a>
### RC-06

Preserve: Fresh answers after commit, rollback, process death, erase and independent cache deletion.

Decision and cost: A token scheme needs every relevant producer and rollback/death invalidation; the validity proof moves to token ownership and admission.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-10"></a>
### RC-10

Preserve: Whole-operation rollback where promised and documented chunked-loader semantics.

Decision and cost: Validation/transactions need staging, temporary capacity and explicit multi-transaction exceptions; costs move to the shared writer.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 111, "reviewed": 111, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-12"></a>
### RC-12

Preserve: Supported server/driver/platform outcomes and explicit refusal of missing premises.

Decision and cost: Environment checks need deploy-time provenance, cache invalidation and runtime rechecks; validation adds failure states.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-13"></a>
### RC-13

Preserve: One schema per namespace, migration to legacy installs and case-compatible naming.

Decision and cost: The resolver becomes a central dependency; every raw SQL/native/deploy entry still needs a schema-binding proof.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-14"></a>
### RC-14

Preserve: Distinguishing empty success, partial success and provider failure without hiding completed effects.

Decision and cost: Typed result propagation changes error interfaces and callers; recovery and compatibility decisions remain per operation.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-17"></a>
### RC-17

Preserve: Numbers versus numeric-looking strings, booleans, nulls, legacy values and relationship qualifiers.

Decision and cost: A common encoding needs versioned storage/migration and readers; typed node paths already exist, so a whole-product reduction is not shown.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-18"></a>
### RC-18

Preserve: Existing domain codes, metrics and units with explicitly compatible conversions.

Decision and cost: Types need conversion and unknown-value policies at all external providers; obligation counts cannot omit the adapters.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-21"></a>
### RC-21

Preserve: Single-edge and multigraph identity, lowest-key representatives and per-edge deletes.

Decision and cost: A shared edge identity changes tuple references and migrations; ambiguous legacy references still need a chosen refusal policy.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-23"></a>
### RC-23

Preserve: Bag multiplicity, specified tie ordering and graph-specific joins.

Decision and cost: Canonicalization/sorting adds CPU and memory and requires a tie contract; an unspecified order cannot be silently made a new promise.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-24"></a>
### RC-24

Preserve: Identity discrimination and stale-entry rejection for ordinary names, plans and relationships.

Decision and cost: Collision-safe identity requires full-key comparisons or wider keys plus lifetime/compatibility rules; checks cannot just move into a hash provider.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 118, "reviewed": 118, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-26"></a>
### RC-26

Preserve: Registry identity refusals before writes and declared missing-registry compatibility.

Decision and cost: A common admission gate must cover routes, queues, optimizer and raw helper exceptions; the complete writer binding remains.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-27"></a>
### RC-27

Preserve: Ordinary valid inputs, stable validation errors and write-nothing refusals.

Decision and cost: Shared validation needs server/Python agreement and exceptions for low-level documented coercion; it adds a common failure interface.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 115, "reviewed": 115, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-28"></a>
### RC-28

Preserve: Correct bounded responses and explicit capacity failures with recorded partial work.

Decision and cost: Streaming/chunking adds continuation and intermediate-capacity obligations; final size, peak memory and fairness are different bounds.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-29"></a>
### RC-29

Preserve: The same observable contract on each supported native, Owner, SQL and Python route.

Decision and cost: A shared implementation must preserve platform/fallback availability; moving code removes neither route admission nor provider correspondence.

Actual Verus comparison: `{"metric": "verification queries in the same whole crate (includes unrelated modules)", "as_built": 118, "reviewed": 118, "removed": 0, "qualification": "Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count."}`

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-30"></a>
### RC-30

Preserve: Pause/retry recovery, no duplicate effects and honest progress on queued/batched work.

Decision and cost: Persisted cursors/claims add lease, recovery and cleanup state and fairness assumptions; progress still depends on scheduling.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-32"></a>
### RC-32

Preserve: Installable packages and the same Community/Enterprise deployment behavior as supported setup.

Decision and cost: A shared deploy manifest adds edition-specific predicates and packaging tests; tooling reuse alone does not shrink the product model.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-33"></a>
### RC-33

Preserve: Requested semantic options are honored or clearly refused before effects.

Decision and cost: Central admission requires an option-support matrix and compatibility errors for every route; it adds explicit refusal transitions.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-36"></a>
### RC-36

Preserve: All accepted text/JSON values, types, delimiters and stable external results.

Decision and cost: A codec adds versioning and legacy decode support; producer/consumer agreement and malformed-reply handling remain proof obligations.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-str-002"></a>
### simp-str-002

Preserve: every SQL `COALESCE(graph_id,'')` predicate; default and named graph rows.

Decision and cost: GraphKey gains the inverse contract and every SQL/native caller needs the same default/named conversion; migration and old aliases remain.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-str-003"></a>
### simp-str-003

Preserve: the token still moves on every rebuild; readers during the rebuild still see it as not current.

Decision and cost: Changing warm/token order still requires no reader to admit an unfinished rebuild; one ordering check replaces another, with no alternate state model.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-tmp-001"></a>
### simp-tmp-001

Preserve: an idempotent backfill with a read-only dry run.

Decision and cost: Removing the legacy Python path requires opt-out, dry-run/backfill and non-indexed fallback coverage; dropping a supported fallback narrows the operating envelope.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-srch-002"></a>
### simp-srch-002

Preserve: refusal before anything is queued or written; "no registry" (SQLCODE -30) still passes as documented.

Decision and cost: The route-row snapshot must remain valid until the write, including registry changes and missing-registry exceptions; a saved query is not a removed identity obligation.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

Receipt freshness: the historical search receipt has stale model.json/search.rs inputs. Its recorded counts are not a current source-bound comparison; the simplification claim is withdrawn. See [hash checks](reused-proof-bindings.json).

<a id="simp-plt-002"></a>
### simp-plt-002

Preserve: a native failure still yields the Owner's answer.

Decision and cost: Uniform fallback still needs per-algorithm numerical parameters, refusal/error policy and native admission; an Owner call is not an interchangeable opaque result.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-plt-003"></a>
### simp-plt-003

Preserve: the FHIR sync's output graph.

Decision and cost: Label ownership moves to Adjacency but FHIR transaction, graph key and rollback binding remain; extra helper calls may add cost.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-plt-004"></a>
### simp-plt-004

Preserve: the resulting `^KG`.

Decision and cost: Batching rebuilds trades repeated work for index-staleness intervals, failure recovery and concurrent-writer handling; final KG equality alone is insufficient.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-plt-005"></a>
### simp-plt-005

Preserve: the schema rewrite seen by each call.

Decision and cost: Retirement needs a caller census and per-engine schema-state equivalent; process-global state cannot be dropped without proving the replacement lifecycle.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-cyp-003"></a>
### simp-cyp-003

Preserve: the SQL fallback for this call; a deploy or stamp change still allows a fresh build.

Decision and cost: Failed-entry state and retry/reset policy are added; one SQL fallback does not establish future builds, concurrent users or error classification.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-led-001"></a>
### simp-led-001

Preserve: the redaction target digest and the matching of default-graph records.

Decision and cost: GraphKey owns the conversion but digest stability, prefix targeting and legacy empty/default graph encoding still need correspondence.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-15"></a>
### RC-15

Preserve: Public exception compatibility, useful operation context and distinct refusal causes.

Decision and cost: A typed hierarchy moves mapping into boundary adapters; subclass compatibility and callers catching old exceptions need checks.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-31"></a>
### RC-31

Preserve: Accurate documentation of supported behavior and exceptions.

Decision and cost: Generated descriptions need a semantic source and stable annotation/schema APIs; prose/code agreement remains a validation obligation.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="RC-34"></a>
### RC-34

Preserve: All permitted writers, transaction membership and cross-store invariants.

Decision and cost: An enforced owner API needs interception of direct SQL/native paths and deployment authority; bypass and transaction proofs move to that API.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: simplification claim withdrawn; engineering candidate retained for review. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).

<a id="simp-str-005"></a>
### simp-str-005

Preserve: Sound degree-cache admission under all competing writers and rollback.

Decision and cost: The existing counterexample shows an unrelated writer can produce a reused generation value; key ownership is not repaired by changing the counter source.

Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.

Disposition: retired counterproposal. No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement. The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).
