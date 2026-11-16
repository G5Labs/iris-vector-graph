# Redaction

Redaction removes an erased target's content from the [revision ledger](ledger.g5.md)'s history and keeps the history's shape. It always follows an [erasure](erasure.g5.md). Together, the two are meant to cover everything IVG can reach; the known gaps are listed under the [purpose](#redaction.purpose), and copies outside IVG stay out of reach.

## Definitions

- **Target**: what one redaction removes. It is a graph, optionally narrowed to the entity IDs that begin with a prefix followed by a separator (`|` by default).
- **Live**: present in the graph's current tables.
- **Canonical record**: the ledger's fixed JSON form of one record. The digest is computed over it.
- **Tombstone**: what a redacted record becomes. It stays at the record's position and holds a digest of the original record instead of its content.
- **Spanning revision**: a revision with records in more than one graph, for example one that touches two tenants.
- **Redaction revision**: the content-free revision that a finished redaction adds to the ledger.
- **In-progress marker**: the ledger entry that says a redaction has started and not finished.
- **Receipt**: what a redaction returns: what it did and what stays out of reach.

## Purpose and target

<a id="redaction.purpose"></a>
[I · redaction.purpose]

After a target's content has been erased, an operator can remove that content from the ledger's history. The history keeps its shape: every revision and every record position stays, and only the target's content goes. Afterwards, no record, revision field or ledger index reachable through IVG holds the target's IDs, values or messages.

- Known exceptions: records the run cannot attribute to the target ([unattributed](../../Verus_verification/open_questions.md#redaction.unattributed)), reifier delete records reached by neither target ([target nodes](#redaction.target.nodes)), actor fields, which are [kept by design](#redaction.metadata.actor), and IVG's own snapshot archives and pre-upgrade ledger rows ([other copies](../../Verus_verification/open_questions.md#q-led-002)).
- Live stores outside the ledger are erasure's job; today search indexes can still answer with erased text ([erasure](erasure.g5.md#erasure.scope)).

- Working assumption: Document the present strict-off erasure sequence as an operational precondition; do not infer that disabling strict mode is the desired product interface.
- Working assumption: List snapshots and legacy ledger copies as outside redaction reach; archive-retention/removal policy remains an owner decision.
- Working assumption: Retain an unattributed record and disclose it in the receipt until prefix ownership is established.


<a id="redaction.target"></a>
[D · redaction.target]

A target is a graph, optionally narrowed to the entity IDs that begin with a prefix and its separator.

- The separator is part of the match, so the prefix `acme` never matches `acme-health|…`.
- A prefix that already ends with the separator is used as given.
- An empty separator is refused.

- Working assumption: Retain an unattributed record and disclose it in the receipt until prefix ownership is established.


<a id="redaction.target.nodes"></a>
[D · redaction.target.nodes]

The ledger records every node in the default graph ([node scope](ledger.g5.md#ledger.node-scope)). So a tenant's node records can be reached only through an ID prefix with the default graph as the target. A named-graph target reaches relationship, qualifier and temporal-edge records, but never node records.

- A relationship delete, or a detach delete of a node, also deletes the relationship's reifier nodes. Inside the tenant's own revision, their delete records carry each reifier's own ID, the default graph and a snapshot of its labels and properties. Unless a reifier ID begins with the tenant's prefix, neither of the tenant's two targets reaches these records.


<a id="redaction.target.relationships"></a>
[D · redaction.target.relationships]

With a prefix, a relationship record belongs to the target when the relationship's source or target ID begins with the match. A qualifier change belongs to the target when its relationship does.


<a id="redaction.tenant"></a>
[D · redaction.tenant]

Fully redacting a tenant whose relationships live in its own graph takes two targets: the tenant's graph, and the tenant's prefix in the default graph.

- Erase the tenant's nodes first with the prefix and its separator, such as `tenant|`. Erasing by prefix has no separator rule, so `tenant` alone would also erase other tenants' nodes ([prefix match](erasure.g5.md#erasure.prefix-match)).
- Keep each tenant's temporal edges in its own graph. Spec 256 put off erasing one tenant's temporal data inside a shared graph, and a prefix erase misses its temporal-only events ([open question](../../Verus_verification/open_questions.md#q-009)).

- Working assumption: Treat temporal entries as live content for the intended safety rule; the existing row-only check remains a documented behavior discrepancy pending scope confirmation.
- Working assumption: Require tenant id prefixes for ledger-governed tenants and document it next to redact(); for a graph target whose erased nodes left graph-blind node records, return an explicit incomplete result (or refuse) instead of complete=true. Model graph-qualified node records for future history separately; a migration of existing history needs trustworthy provenance, which the genesis did not keep.


<a id="redaction.call"></a>
[D · redaction.call]

A redaction call names the graph (none means the default graph), an optional prefix, the separator, an actor and a batch size, and may cap the number of batches. The defaults are separator `|`, actor `system:ledger-redact` and 2,000 tombstones per batch. Two calls are the same redaction when they name the same graph and the same match string, the prefix with its separator, so `acme` and `acme|` name one target.

- A refusal raises a typed error: `RedactionTargetLiveError`, `RedactionInProgressError`, `InvalidRedactionTargetError`, `LedgerNotEnabledError`, `LedgerDisabledError`, `LedgerTransactionOpenError` or `LedgerLockTimeoutError`.
- An unexpected failure inside a batch raises `LedgerInconsistencyError`, and that batch is rolled back.
- A refusal before the first batch changes nothing. A refusal between batches, such as `LedgerDisabledError` or `LedgerLockTimeoutError`, keeps the earlier batches and the marker; running the same call again finishes the run.

## Refusals


<a id="redaction.after-erasure"></a>
[D · redaction.after-erasure]

Redaction only follows erasure. It is refused while any row of the target is live, because replaying the history without the target's records would no longer match the store.

- The refusal names the live target and changes nothing.
- Liveness is checked again, under the ledger lock, just before the run finishes.

- Working assumption: Treat temporal entries as live content for the intended safety rule; the existing row-only check remains a documented behavior discrepancy pending scope confirmation.


<a id="redaction.after-erasure.default-graph"></a>
[I · redaction.after-erasure.default-graph]

For a default-graph target, live node, label and property rows count in every graph, because the ledger's node records and verify both ignore graphs. Relationship rows count only in the target graph.

- So the whole default graph, with no prefix, cannot be redacted while any graph holds a node.


<a id="redaction.refusals"></a>
[I · redaction.refusals]

A redaction is also refused, with nothing changed, when:

- the ledger was never enabled, or is disabled;
- the caller has a transaction open;
- the graph name is invalid or the separator is empty;
- a redaction of another target has not finished ([rule](#redaction.batches.competing)).


## Tombstones


<a id="redaction.tombstone"></a>
[D · redaction.tombstone]

Each of the target's records becomes a tombstone at its own position. The tombstone keeps the kind of change, the entity kind and the record's flags, and holds the SHA-256 of the original canonical record. It holds no entity ID, attribute, value or graph.

- Working assumption: Treat auditor-held original canonical records as required to recompute digests; the product does not promise a retained recoverable preimage.


<a id="redaction.tombstone.digest"></a>
[D · redaction.tombstone.digest]

For now the digest is unsalted, so an auditor who holds the original canonical record can prove it was the one redacted. A guessable record, such as a short ID with a known shape, can be confirmed by guessing; the digest does not hide it.

- Working assumption: Record the unsalted digest as built and keep its privacy adequacy open; no guessing or confirmability experiment is in scope.


<a id="redaction.tombstone.canonical-form"></a>
[D · redaction.tombstone.canonical-form]

The canonical record is a JSON object with the record's fields in alphabetical order: attribute, entity ID, entity kind, flags (a list), graph, new value, change kind, ordinal, prior value and seq. An absent value and an empty graph are written as null, and seq and ordinal are numbers. The digest is the SHA-256 of that text in UTF-8, written as lowercase hex.


<a id="redaction.readers"></a>
[I · redaction.readers]

Replay, diff and reconstruction treat a tombstone as contributing nothing. Record readers show a tombstone as a redacted change at its position instead of hiding the position. A diff lists the positions of the tombstones in its range.


## Revision metadata and retries


<a id="redaction.metadata"></a>
[D · redaction.metadata]

A revision with any redacted record loses its message, source, correlation ID and idempotency key, even when its other records belong to another tenant. Its seq, revision ID, parent, kind and commit time stay, and so do the other graphs' records.


<a id="redaction.metadata.exception"></a>
[D · redaction.metadata.exception]

Clearing those four fields is the only change ever allowed to a revision row. It is allowed only to the redaction itself, for a revision that already has a tombstone, and only to empty those fields. Every other update and every delete is still refused.


<a id="redaction.metadata.actor"></a>
[D · redaction.metadata.actor]

A revision's actor, actor type and connection user are kept, because they identify the writer, not the tenant. A deployment that puts tenant names in the actor must choose another actor.


<a id="redaction.idempotency"></a>
[D · redaction.idempotency]

The idempotency key of each revision that gets a tombstone is unbound and kept only as a digest. A later commit with that key is refused, so a retry can neither replay the redacted revision nor re-create the erased content.

- Working assumption: Preserve refusal of the whole shared revision key and loss of its correlation lookup until the maintainer specifies a tenant-specific retry result.


## The audit and the receipt


<a id="redaction.audit"></a>
[D · redaction.audit]

A finished redaction adds one revision of kind `redaction` to the ledger. It names each redacted revision by seq with its number of tombstones, and holds counts and a digest of the target instead of the target's name. Nothing in it comes from the target.


<a id="redaction.receipt"></a>
[I · redaction.receipt]

A redaction returns a receipt that says:

- whether the run completed, and a digest of the target;
- the seqs of the redacted revisions;
- how many records became tombstones, and how many revisions, idempotency keys and statement entries were cleared or removed;
- the redaction revision, once the run completes;
- what stays out of reach.


<a id="redaction.out-of-reach"></a>
[D · redaction.out-of-reach]

Copies outside the ledger keep the content: exports written before the redaction, IRIS journals and backups. Every receipt says so.

- Working assumption: List snapshots and legacy ledger copies as outside redaction reach; archive-retention/removal policy remains an owner decision.


## Batches and the in-progress marker


<a id="redaction.batches"></a>
[D · redaction.batches]

A redaction runs in bounded batches, and an in-progress marker records it while it is unfinished. Each batch is one transaction under the ledger's head lock.

- The final step, in its own transaction, re-checks liveness, removes the target's statement entries, writes the redaction revision and removes the marker.
- Each batch holds the lock briefly; the performance target is a [child](#redaction.batches.speed).

- Working assumption: Assume completion by rerun after fixing liveness; abandonment needs an owner-approved recovery meaning for partial tombstones.
- Working assumption: (a) No generic abandon: tombstones are irreversible, so 'abandon' could only remove the marker and accept a permanently divergent history; the recovery is re-erase and resume, and the docs should say that this also erases content re-created during the run. An explicit, audited cancel that records the partial redaction as a redaction revision is the alternative. (b) Apply the plan's graph-blind liveness check to every default-graph target, so redact(None) without a prefix is refused while any node of any graph is live.


<a id="redaction.batches.readers"></a>
[I · redaction.batches.readers]

While the marker exists, record readers, diffs, reconstructions and exports refuse with `RedactionInProgressError`, and verify reports `redaction_in_progress` and adopts nothing.

- History, statistics and the SQL `ledger_records` procedure still answer and can show a half-redacted ledger. Whether they must also refuse is open.

- Working assumption: Keep the explicit redaction guards and list unguarded readers; do not infer that partial-redaction answers are acceptable.


<a id="redaction.batches.commits"></a>
[I · redaction.batches.commits]

While the marker exists, a commit with any record in the target is refused, and other commits proceed. Today a record whose attribution to the target is unknown, such as a qualifier whose statement endpoints are not known, is let through.


<a id="redaction.batches.competing"></a>
[I · redaction.batches.competing]

A redaction of a different target is refused, with nothing changed, until the unfinished one completes.


<a id="redaction.batches.resume"></a>
[I · redaction.batches.resume]

Running the same redaction again resumes an unfinished run. Running a finished redaction again changes nothing and reports zero. A caller may stop a run after a set number of batches and resume it later.

- If the ledger is disabled between batches, the run stops, keeps its marker and resumes after the ledger is enabled again.


<a id="redaction.batches.marker-text"></a>
[D · redaction.batches.marker-text]

While a run is unfinished, the marker holds the target in plain text so that commits can be checked against it. The marker is removed when the run finishes, but IRIS journals keep it.


<a id="redaction.batches.speed"></a>
[I · redaction.batches.speed]

On the laptop's enterprise container, redacting a tenant with 100,000 records should take under a minute and block commits for under one second at a time.

## Verification after redaction


<a id="redaction.verify"></a>
[I · redaction.verify]

After a target is erased and redacted, verify reports equal again; after the erase alone it reports a divergence. This holds when the ledger matched the store before the erase, nothing was written outside the ledger after it, and the redacted targets cover everything that was erased.

## Metadata

### redaction.purpose

- uncertain
- Sources: [spec 256 input and story 1](../../../specs/256-ledger-tenant-redaction/spec.md#L8-L58), [ADR-0013](../../../docs/adr/0013-redaction-removes-content-from-history.md), [CONTEXT.md Redaction](../../../CONTEXT.md#L206-L217), [OpsReview brief](../../../docs/dev/notes/for-opsreview/IVG-OPSREVIEW-BRIEF.md#L120-L126)
- agent
- security, user-facing-behavior
- test-coverage

The consumer, OpsReview, asked through an agent message for "a ledger operation that redacts or removes a Tenant's revisions and keeps the chain verifiable (a tombstoned revision with its hash kept)". A human gave the go-ahead to the request; the IVG-side agent drafted the user stories. Deleting and renumbering records was rejected (ADR-0013). Gap: a relationship in another graph that names the tenant's IDs stays, live and in its records. Live test: `test_256_ledger_redaction_e2e.py::TestUS1RedactTenant::test_nothing_in_the_ledger_or_its_readers_holds_tenant_a`. [A-history notes](../../uplift/ivg-verus-initial/intent/ledger-history.md).

Findings: [An adopting verify that races a redaction can append the redacted tenant's IDs after the redaction finished](../../Verus_verification/bugs_issues.md#bug-led-001)


The exception bullets were added by review round 3 R3-reader M3; each links the block that owns the exception. Unattributed records left in clear under a `complete` receipt were observed ([redaction_unattributed_qualifier](../../Verus_verification/receipts/native/redaction_unattributed_qualifier.json)).

Findings: [Search indexes keep answering with content that was erased, and a re-created node inherits the erased text](../../Verus_verification/bugs_issues.md#bug-srch-001)

Open questions: [How should strict mode and the erase-then-redact path fit together?](../../Verus_verification/open_questions.md#q-003), [Should the redaction receipt name IVG's own snapshot archives and the ledger rows an upgrade left behind?](../../Verus_verification/open_questions.md#q-led-002), [What should happen to a record in the target graph when it cannot be determined whether the record belongs to a prefix target?](../../Verus_verification/open_questions.md#redaction.unattributed)

### redaction.target

- uncertain
- Sources: [spec 256 FR-001 and edge cases](../../../specs/256-ledger-tenant-redaction/spec.md#L97-L116), [LedgerRedact.cls MatchString](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L45-L64), [client.py redact](../../../iris_vector_graph/ledger/client.py#L633-L680)
- Children: [Node records](#redaction.target.nodes), [Relationship records](#redaction.target.relationships)
- agent
- user-facing-behavior, security
- test-coverage

An empty prefix means the whole graph; the Eraser refuses an empty prefix for the analogous erase. Live tests: `TestDefaultGraphTenantByPrefix` in `test_256_ledger_redaction_e2e.py`.

Findings: [Spell record graphs in redaction through GraphKey instead of an inline translate](../../Verus_verification/design_simplification.md#simp-led-001)

Open questions: [What should happen to a record in the target graph when it cannot be determined whether the record belongs to a prefix target?](../../Verus_verification/open_questions.md#redaction.unattributed)

### redaction.target.nodes

- Sources: [ADR-0013 Context](../../../docs/adr/0013-redaction-removes-content-from-history.md#L37), [spec 256 plan](../../../specs/256-ledger-tenant-redaction/plan.md#L9), [LedgerRedact.cls Matches](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L87-L112)
- Expands: [Target](#redaction.target)
- agent
- architecture-decision, security
- test-coverage

Consequence: a node of a named graph that genesis or adoption recorded can be reached only through a prefix, and an ID without a tenant prefix cannot be reached at all. The reifier bullet follows from [LedgerApply.cls DeleteRelInternal](../../../iris_src/src/Graph/KG/LedgerApply.cls#L652-L692) and [DeleteNodeRows](../../../iris_src/src/Graph/KG/LedgerApply.cls#L354-L372). It is suspected, not tested; register entry [A reifier's delete record written inside a tenant's revision is reached by neither redaction target](../../Verus_verification/bugs_issues.md#bug-led-005) ([review round 1, R1-11 / CV-4](../../uplift/ivg-verus-initial/review/round1-core.md#L134-L138)). Live test: the two-tenant fixture in `test_256_ledger_redaction_e2e.py`. That fixture has no reifiers.

Findings: [A reifier's delete record written inside a tenant's revision is reached by neither redaction target](../../Verus_verification/bugs_issues.md#bug-led-005)

### redaction.target.relationships

- Sources: [spec 256 plan Design 2](../../../specs/256-ledger-tenant-redaction/plan.md#L22), [LedgerRedact.cls Matches and PrePass](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L87-L141)
- Expands: [Target](#redaction.target)
- agent
- data-integrity
- test-coverage

Live test: `TestDefaultGraphTenantByPrefix::test_the_prefix_is_matched_with_its_separator` (one relationship and one qualifier). Temporal-edge records are matched by their endpoints too, with no live test.

### redaction.tenant

- uncertain
- Sources: [ADR-0013 Context](../../../docs/adr/0013-redaction-removes-content-from-history.md#L37), [client.py redact docstring](../../../iris_vector_graph/ledger/client.py#L643-L665), [OpsReview brief usage](../../../docs/dev/notes/for-opsreview/IVG-OPSREVIEW-BRIEF.md#L125)
- agent
- user-facing-behavior, security
- test-coverage

Documentation divergence: the OpsReview brief recommends one call, `redact(graph, prefix="tenant|")`, which never reaches node records. The erase-with-separator line comes from the plain prefix match of [Eraser.cls EraseNodes](../../../iris_src/src/Graph/KG/Eraser.cls#L307-L345); the redaction tests erase with `tenantA|`. Live test: the full two-call recipe in `test_256_ledger_redaction_e2e.py`.

Findings: [The OpsReview brief's one-call redaction recipe never reaches the tenant's node records](../../Verus_verification/bugs_issues.md#bug-doc-001)


Observed divergences in the prefix step (review round 2 and 3): a prefix erase leaves temporal-only events whose endpoints have no node row, and a property row with no node row; the first lets the redaction complete while the events stay readable, the second makes every later prefix redaction refuse until the row is erased by ID ([redaction_orphan_prop_blocks](../../Verus_verification/receipts/native/redaction_orphan_prop_blocks.json)).

Findings: [Erasing a tenant by prefix leaves its temporal-only events, and the redaction that follows completes while they stay readable](../../Verus_verification/bugs_issues.md#bug-led-007); [A property row with no node row survives the prefix erase, and every later prefix redaction of its tenant is refused](../../Verus_verification/bugs_issues.md#bug-led-010)

Open questions: [How is a tenant's node history redacted when nodes live in the tenant's own graph?](../../Verus_verification/open_questions.md#HD-1304), [Should redaction count a target's temporal-only edges as live content?](../../Verus_verification/open_questions.md#q-009)

Assumption review evidence: Changed from decisions.md: **no**. Same choice; added the R290 maintainer statement, the genesis attribution contradiction, the receipt (FR-008) gap and fresh live evidence including the FR-007 divergence.

### redaction.call

- Sources: [LedgerRedact.cls Redact](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L182-L239), [spec 256 plan Design and Python](../../../specs/256-ledger-tenant-redaction/plan.md#L19-L50), [client.py redact](../../../iris_vector_graph/ledger/client.py#L633-L680), [errors.py wire map](../../../iris_vector_graph/ledger/errors.py#L156-L172)
- agent
- user-facing-behavior
- test-coverage

The target's identity is the SHA-256 of the canonical graph name, a NUL and the match string; the marker and receipt carry it as `target_sha256`. A batch also scans at most 20 records per allowed tombstone, so a sparse target still releases the lock quickly. Every run, a resumed one included, rescans from the first record and skips tombstones. Live tests: the refusal and resume tests in `test_256_ledger_redaction_e2e.py`; error mapping in the unit test `tests/unit/test_256_ledger_redaction.py`.

### redaction.after-erasure

- uncertain
- Sources: [ADR-0013 Decision](../../../docs/adr/0013-redaction-removes-content-from-history.md#L17), [spec 256 story 3 and FR-005](../../../specs/256-ledger-tenant-redaction/spec.md#L84-L124), [LedgerRedact.cls LiveRows and Final](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L143-L178)
- Children: [Default graph](#redaction.after-erasure.default-graph), [Should redaction count a target's temporal-only edges as live content?](../../Verus_verification/open_questions.md#q-009)
- agent
- data-integrity, security
- test-coverage

Liveness counts rows in nodes, labels, properties and relationships, not the ledger's own statement index (FR-005 names "live statement or node"). Writes made outside the ledger are not excluded between the two checks. Live tests: `TestUS3Refusals`.

Findings: [A redaction completes while its target's content is still uncommitted-deleted, and the caller's rollback brings the content back with its history tombstoned](../../Verus_verification/bugs_issues.md#bug-002); [Under strict mode the only API delete is a ledger changeset, which leaves documents, temporal, FHIR and search-index content that redaction and verify cannot see](../../Verus_verification/bugs_issues.md#bug-led-008)


Findings: [A property row with no node row survives the prefix erase, and every later prefix redaction of its tenant is refused](../../Verus_verification/bugs_issues.md#bug-led-010)

Open questions: [Should redaction count a target's temporal-only edges as live content?](../../Verus_verification/open_questions.md#q-009)

### redaction.after-erasure.default-graph

- Sources: [spec 256 plan](../../../specs/256-ledger-tenant-redaction/plan.md#L10), [LedgerRedact.cls LiveRows](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L143-L178)
- Expands: [After erasure](#redaction.after-erasure)
- agent
- data-integrity
- test-coverage

The bullet is a consequence of the plan's rule, which the sources do not discuss for a target without a prefix ([reconstruction check G30](../../uplift/ivg-verus-initial/reconstruction-check.md#L435)). Observed divergence: for a default-graph target with no prefix, or an empty one, only default-graph rows are counted, so nodes live in named graphs do not block a run that tombstones their records (A-history F2; observed natively in [redaction_default_graph_whole](../../Verus_verification/receipts/native/redaction_default_graph_whole.json)). Live test (prefix case only): `TestUS3Refusals::test_live_default_graph_nodes_refuse_the_prefix_and_nothing_changes`.

Findings: [Redacting the whole default graph ignores node rows in named graphs and destroys the history of nodes that are still live](../../Verus_verification/bugs_issues.md#bug-003)

### redaction.refusals

- Sources: [LedgerRedact.cls Redact](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L182-L210), [spec 256 plan Design 1](../../../specs/256-ledger-tenant-redaction/plan.md#L21), [client.py refuse caller transaction](../../../iris_vector_graph/ledger/client.py#L268-L279)
- agent
- user-facing-behavior
- test-coverage

Live tests: `TestUS3Refusals::test_a_disabled_ledger_is_refused_and_nothing_changes`, `tests/e2e/test_470_ledger_caller_txn_e2e.py::test_enable_and_redact_refuse_the_callers_transaction`.

### redaction.tombstone

- uncertain
- Sources: [ADR-0013 Decision](../../../docs/adr/0013-redaction-removes-content-from-history.md#L14), [spec 256 FR-002](../../../specs/256-ledger-tenant-redaction/spec.md#L117-L118), [LedgerRedact.cls Tombstone](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L332-L347), [Ledger.cls CanonicalRecord](../../../iris_src/src/Graph/KG/Ledger.cls#L571-L605)
- Children: [Digest](#redaction.tombstone.digest), [Canonical form](#redaction.tombstone.canonical-form)
- agent
- data-integrity, security
- test-coverage

The spec's Key Entities give a three-field tombstone; ADR-0013 and the code add the change kind and the entity kind. Live tests: `TestUS2Verifiable::test_each_tombstone_digest_is_sha256_of_the_canonical_record_it_replaced`, `::test_the_canonical_form_of_a_tombstone_holds_only_its_digest`.

Findings: [Spec 256's text contradicts its own decisions and the shipped tombstone format](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-003)

Open questions: [Which copy of a record must an auditor keep to recompute its tombstone digest?](../../Verus_verification/open_questions.md#q-led-001)

### redaction.tombstone.digest

- uncertain
- Sources: [ADR-0013 Alternatives and Consequences](../../../docs/adr/0013-redaction-removes-content-from-history.md#L43-L49), [spec 256 story 2](../../../specs/256-ledger-tenant-redaction/spec.md#L63-L80)
- Expands: [Tombstone](#redaction.tombstone)
- Children: [Which copy of a record must an auditor keep to recompute its tombstone digest?](../../Verus_verification/open_questions.md#q-led-001)
- agent
- security
- test-coverage

A salted digest was rejected "for now". The redaction revision's target digest and the kept digests of idempotency keys are unsalted too, so a guessed tenant name or key can be confirmed.


Findings: [Is an unsalted SHA-256 of a tenant name and of each record acceptable in the redacted history?](../../Verus_verification/open_questions.md#q-005)

Audit (q-005): Open owner decision. Working assumption (agent, unratified): Record the unsalted digest as built and keep its privacy adequacy open; no guessing or confirmability experiment is in scope. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#q-005).

Open questions: [Is an unsalted SHA-256 of a tenant name and of each record acceptable in the redacted history?](../../Verus_verification/open_questions.md#q-005)

### redaction.tombstone.canonical-form

- Sources: [Ledger.cls CanonicalRecord](../../../iris_src/src/Graph/KG/Ledger.cls#L571-L605), [LedgerRedact.cls Sha256Hex](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L39-L43), [reconstruction check G12](../../uplift/ivg-verus-initial/reconstruction-check.md#L405)
- Expands: [Tombstone](#redaction.tombstone)
- agent
- security, data-integrity
- test-coverage

The JSON keys are `attr`, `entity_id`, `entity_kind`, `flags`, `graph`, `new`, `op`, `ordinal`, `prior`, `seq`. Values are written as IRIS's `%ToJSON` writes them. A genesis relationship in the default graph stores its graph as a NUL character, which is written as `"\u0000"`, not null ([Which copy of a record must an auditor keep to recompute its tombstone digest?](../../Verus_verification/open_questions.md#q-led-001)). A tombstone's own canonical form holds only `digest`, `flags`, `op`, `ordinal`, `redacted_op` and `seq`. Live test: `TestUS2Verifiable::test_each_tombstone_digest_is_sha256_of_the_canonical_record_it_replaced`.

### redaction.readers

- Sources: [spec 256 FR-003](../../../specs/256-ledger-tenant-redaction/spec.md#L119-L120), [replay.py contributes and diff](../../../iris_vector_graph/ledger/replay.py#L24-L26), [Ledger.cls RecordsFetch](../../../iris_src/src/Graph/KG/Ledger.cls#L621-L646)
- agent
- user-facing-behavior
- test-coverage

FR-003 also names history and export. Neither lists record positions, so neither can mark one. Live tests: `TestUS2Verifiable::test_replay_to_every_seq_holds_no_tenant_a_content`, `::test_diff_marks_tombstones_rather_than_hiding_them`.

### redaction.metadata

- Sources: [spec 256 Decision 2](../../../specs/256-ledger-tenant-redaction/spec.md#L150-L157), [ADR-0013 Decision](../../../docs/adr/0013-redaction-removes-content-from-history.md#L15), [LedgerRedact.cls ClearRevision](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L349-L378)
- Children: [Only exception](#redaction.metadata.exception), [Actor kept](#redaction.metadata.actor)
- human-verified
- security, data-integrity
- test-coverage

Decision 2 (Tom, 2026-10-22), recorded with the tradeoff "loses t2's commit message". FR-004 ("every record is redacted") and acceptance scenario 2 were never updated to match. Spec SC-004 ("revision rows byte-identical") does not hold for spanning revisions. Live test: `TestUS1RedactTenant::test_a_spanning_revision_keeps_tenant_b_records_and_loses_its_metadata`.

Audit (HD-1302): Existing authority: Decision 2 clears the free text when any record in the revision is tombstoned. The older every-record wording is stale. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-1302).

Findings: [Which rule clears a revision's free text: any tombstone or every record?](../../Verus_verification/open_questions.md#HD-1302).

### redaction.metadata.exception

- Sources: [ADR-0013 the one exception](../../../docs/adr/0013-redaction-removes-content-from-history.md#L20-L29), [LedgerRevision.cls RejectUpdate](../../../iris_src/src/Graph/KG/LedgerRevision.cls#L77-L101)
- Expands: [Metadata cleared](#redaction.metadata)
- agent
- security, data-integrity
- test-coverage

The exception records itself twice: in a per-revision flag and in the redaction revision. A source-text unit test checks that only the redaction class sets the exemption. Live test: `TestUS1RedactTenant::test_outside_the_redaction_a_redacted_revision_is_still_immutable`.

### redaction.metadata.actor

- Sources: [ADR-0013 Consequences](../../../docs/adr/0013-redaction-removes-content-from-history.md#L50)
- Expands: [Metadata cleared](#redaction.metadata)
- agent
- security, operations

### redaction.idempotency

- uncertain
- Sources: [ADR-0013 Decision](../../../docs/adr/0013-redaction-removes-content-from-history.md#L15), [spec 256 edge cases](../../../specs/256-ledger-tenant-redaction/spec.md#L104-L105), [Ledger.cls redacted key check](../../../iris_src/src/Graph/KG/Ledger.cls#L466-L473), [LedgerRedact.cls ClearRevision](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L359-L365)
- Children: [Should another tenant's retry of a revision it shared with a redacted tenant be refused?](../../Verus_verification/open_questions.md#q-001)
- agent
- security, data-integrity
- test-coverage

The error is `IdempotencyRedactedError`, a kind of `IdempotencyConflictError`. Live test: `TestUS1RedactTenant::test_a_retry_with_a_redacted_idempotency_key_is_refused`.

Open questions: [Should another tenant's retry of a revision it shared with a redacted tenant be refused?](../../Verus_verification/open_questions.md#q-001)

### redaction.audit

- Sources: [spec 256 Decision 1 and FR-009](../../../specs/256-ledger-tenant-redaction/spec.md#L127-L154), [ADR-0013 Decision](../../../docs/adr/0013-redaction-removes-content-from-history.md#L16), [spec 256 plan](../../../specs/256-ledger-tenant-redaction/plan.md#L33-L40), [LedgerRedact.cls FinalInLock](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L409-L442)
- human-verified
- security, architecture-decision
- test-coverage

Decision 1 (Tom, 2026-10-22) chose a ledger revision over a separate audit store, on the condition that it be content-free. The draft had said the audit would not be a ledger revision. The redaction revision counts as a successful commit in the ledger's statistics. Observed divergence: two redactions started together can both run, and one redaction revision can then list both targets' revisions (A-history F1; observed natively in [redaction_concurrent_targets](../../Verus_verification/receipts/native/redaction_concurrent_targets.json)). Live test: `TestUS1RedactTenant::test_the_redaction_revision_is_content_free`.

Findings: [Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work](../../Verus_verification/bugs_issues.md#bug-001)

### redaction.receipt

- Sources: [spec 256 FR-008](../../../specs/256-ledger-tenant-redaction/spec.md#L126-L127), [LedgerRedact.cls Receipt](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L482-L511), [client.py RedactionReceipt](../../../iris_vector_graph/ledger/client.py#L138-L182)
- agent
- user-facing-behavior
- test-coverage

Live test: `TestUS1RedactTenant::test_the_receipt_counts_what_it_did_and_names_what_is_out_of_reach`.

### redaction.out-of-reach

- uncertain
- Sources: [ADR-0013 Consequences](../../../docs/adr/0013-redaction-removes-content-from-history.md#L48), [spec 256 Not in this spec](../../../specs/256-ledger-tenant-redaction/spec.md#L159-L163)
- Children: [Should the redaction receipt name IVG's own snapshot archives and the ledger rows an upgrade left behind?](../../Verus_verification/open_questions.md#q-led-002)
- agent
- security
- test-coverage

Live test: the receipt test checks that the receipt names exports, journals and backups.

Open questions: [Should the redaction receipt name IVG's own snapshot archives and the ledger rows an upgrade left behind?](../../Verus_verification/open_questions.md#q-led-002)

### redaction.batches

- design-verified

- uncertain
- Sources: [spec 256 Decision 3](../../../specs/256-ledger-tenant-redaction/spec.md#L156), [ADR-0013 Batches](../../../docs/adr/0013-redaction-removes-content-from-history.md#L18), [LedgerRedact.cls Batch and Final](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L271-L442), [spec 256 SC-003](../../../specs/256-ledger-tenant-redaction/spec.md#L146-L147)
- Children: [Readers](#redaction.batches.readers), [Commits](#redaction.batches.commits), [Competing redactions](#redaction.batches.competing), [Resume](#redaction.batches.resume), [How does an operator end a redaction that cannot finish?](../../Verus_verification/open_questions.md#q-006), [Marker text](#redaction.batches.marker-text), [Speed](#redaction.batches.speed)
- human-verified
- architecture-decision, operations

Decision 3 (Tom, 2026-10-22) chose batches with a marker over one long transaction. The draft's wish for the run to look atomic to readers was dropped. Observed divergence: the marker is created at the first tombstone, not when the run starts, so a run that has only scanned so far has no marker. The check for another target's marker runs before the lock and before liveness. Every run rescans from the first record ([LedgerRedact.cls](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L202-L226), [reconstruction check G10 and 2(b)11](../../uplift/ivg-verus-initial/reconstruction-check.md#L400)). Model scope: the final step's removal of statement entries (`DropStatements`) is not modeled in [redaction.rs](../../Verus_verification/models/ledger_redaction/redaction.rs). Nor is its branch that writes an audit revision with no marker when it drops statements ([review round 1, R1-11 / CV-5](../../uplift/ivg-verus-initial/review/round1-core.md#L139-L141)). Live tests: `TestBatchesAndMarker` and the opt-in performance test `test_256_ledger_redaction_perf.py` (SC-003).

Open questions: [Can an unfinished redaction be abandoned, and what may a default-graph target touch?](../../Verus_verification/open_questions.md#HD-1303), [How does an operator end a redaction that cannot finish?](../../Verus_verification/open_questions.md#q-006)

State machines: [ledger redaction](../../Verus_verification/models/ledger_redaction/manifest.json)

Assumption review evidence: Changed from decisions.md: **yes**. (b) upgraded from assumption to supported: plan.md:10, committed with the accepted ADR in 2b8ea46d, states the graph-blind rule, and the code comment gives its reason; the working answer becomes 'graph-blind liveness' rather than 'refuse unless ownership can be established'. (a) unchanged; added the plaintext-marker consequence…

### redaction.batches.readers

- Sources: [ADR-0013 Batches](../../../docs/adr/0013-redaction-removes-content-from-history.md#L18), [client.py readers](../../../iris_vector_graph/ledger/client.py#L682-L739), [replay.py verify](../../../iris_vector_graph/ledger/replay.py#L806-L823)
- Expands: [Batches](#redaction.batches)
- agent
- uncertain
- data-integrity, user-facing-behavior
- test-coverage

Provenance: Decision 3 (Tom, 2026-10-22) says "readers and verify() honour" the marker; the plan narrowed it to the readers named here (review round 3 R3-reader M1). Observed ([redaction_readers_midrun](../../Verus_verification/receipts/native/redaction_readers_midrun.json)): readers check the marker once before reading, so a batch can commit while they page through records. History, statistics and the SQL procedure `ledger_records` never check the marker. Decision 3 says "readers and verify() honour" the marker without limiting this to record readers. Live test: `TestBatchesAndMarker::test_a_paused_redaction_is_honoured_and_resumes` (verify and diff).

Findings: [Which ledger readers must refuse while a redaction is unfinished?](../../Verus_verification/open_questions.md#q-002)

Audit (q-002): Open owner decision. Working assumption (agent, unratified): Keep the explicit redaction guards and list unguarded readers; do not infer that partial-redaction answers are acceptable. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#q-002).

Open questions: [Which ledger readers must refuse while a redaction is unfinished?](../../Verus_verification/open_questions.md#q-002)

### redaction.batches.commits

- Sources: [ADR-0013 Batches](../../../docs/adr/0013-redaction-removes-content-from-history.md#L18), [Ledger.cls marker check](../../../iris_src/src/Graph/KG/Ledger.cls#L514-L518), [LedgerRedact.cls BlocksCommit](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L256-L269)
- Expands: [Batches](#redaction.batches)
- agent
- data-integrity
- test-coverage

Observed divergence: only ledger commits are checked. Graph writes outside the ledger can make the target live during a run, and the final liveness check then refuses to finish. Live test: `TestBatchesAndMarker::test_a_paused_redaction_is_honoured_and_resumes`.

Findings: [A redaction that finds nothing to tombstone sets no marker, so a target record committed meanwhile survives a complete run](../../Verus_verification/bugs_issues.md#bug-led-006); [Post-commit properties bypass strict mode and the block on commits into a target being redacted](../../Verus_verification/bugs_issues.md#bug-led-009)

### redaction.batches.competing

- Sources: [ADR-0013 Batches](../../../docs/adr/0013-redaction-removes-content-from-history.md#L18), [LedgerRedact.cls Redact and BatchInLock](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L202-L330), [A-history notes F1](../../uplift/ivg-verus-initial/intent/ledger-history.md)
- Expands: [Batches](#redaction.batches)
- agent
- data-integrity, security
- test-coverage

Observed divergence: the check for another target's marker runs before the lock, and a batch never compares the marker with its own target. Two redactions started before either one writes a tombstone can therefore both run: observed natively ([redaction_concurrent_targets](../../Verus_verification/receipts/native/redaction_concurrent_targets.json): one audit names both tenants' revisions, and a commit into the unfinished target is accepted; [Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work](../../Verus_verification/bugs_issues.md#bug-001)). Live test, sequential only: `TestBatchesAndMarker::test_a_paused_redaction_is_honoured_and_resumes`.

Findings: [Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work](../../Verus_verification/bugs_issues.md#bug-001)

### redaction.batches.resume

- design-verified

- Sources: [ADR-0013 Batches](../../../docs/adr/0013-redaction-removes-content-from-history.md#L18), [spec 256 acceptance 3 and FR-006](../../../specs/256-ledger-tenant-redaction/spec.md#L59-L125), [LedgerRedact.cls Redact](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L182-L239)
- Expands: [Batches](#redaction.batches)
- agent
- operations, user-facing-behavior

The stop on disable is stated in [LedgerRedact.cls BatchInLock](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L302-L305). Live tests: `TestUS1RedactTenant::test_running_the_same_redaction_again_changes_nothing`, `TestBatchesAndMarker::test_a_paused_redaction_is_honoured_and_resumes`. Disable in the middle of a run and a crash in the middle of a batch are not tested. Resume is observed natively for a graph target ([redaction_interrupt_resume](../../Verus_verification/receipts/native/redaction_interrupt_resume.json)) and a prefix target ([redaction_prefix_resume](../../Verus_verification/receipts/native/redaction_prefix_resume.json)); the model proves batches compose within one call's knowledge only. `lemma_serial_resume_keeps_attribution` and `witness_race_then_resume_loses_attribution` in [redaction.rs](../../Verus_verification/models/ledger_redaction/redaction.rs) are classification facts about the attribution test, not a proof of resume: after the race of [Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work](../../Verus_verification/bugs_issues.md#bug-001), a resumed prefix run can lose the statement endpoints its earlier call learned.

State machines: [ledger redaction](../../Verus_verification/models/ledger_redaction/manifest.json)

### redaction.batches.marker-text

- Sources: [ADR-0013 Consequences](../../../docs/adr/0013-redaction-removes-content-from-history.md#L51), [LedgerRedact.cls storage](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L19-L25)
- Expands: [Batches](#redaction.batches)
- agent
- security

### redaction.batches.speed

- Sources: [spec 256 SC-003](../../../specs/256-ledger-tenant-redaction/spec.md#L146-L147)
- Expands: [Batches](#redaction.batches)
- agent
- operations

SC-003 is agent-written spec text, not one of the human decisions, so it was moved out of the `human-verified` parent with its condition kept (review round 3 R3-reader L5). The opt-in performance test `test_256_ledger_redaction_perf.py` was not run in this uplift.

### redaction.verify

- Sources: [ADR-0013 Decision](../../../docs/adr/0013-redaction-removes-content-from-history.md#L17), [spec 256 FR-007 and SC-002](../../../specs/256-ledger-tenant-redaction/spec.md#L123-L145), [ledger verify](ledger.g5.md#ledger.verify)
- agent
- data-integrity, user-facing-behavior
- test-coverage

"Equal" is verify's comparison ([scope](ledger.g5.md#ledger.verify.scope)): it ignores graphs for nodes, does not compare statement IDs and does not cover the temporal index. The fixture had no genesis content, temporal edges, adoptions or reifications. Live tests: `TestUS2Verifiable::test_verify_diverges_after_the_erase_alone_and_is_equal_after_the_redaction`; opt-in SC-002 performance test.
