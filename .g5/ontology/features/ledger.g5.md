# Revision ledger

The revision ledger is IVG's optional, append-only history of graph changes. This page covers how revisions are made, admitted and read, and what verification means. Erasure and redaction have their own pages: [erasure](erasure.g5.md) and [redaction](redaction.g5.md).

## Definitions

- **Ledger**: the history of one namespace's graph changes. It is kept in the global `^IVG.Ledger` and the table `ledger_revisions`.
- **Revision**: one numbered entry in the ledger. It has an ID (32 lowercase hex characters), a sequence number (seq), a parent (the revision before it), a kind (genesis, changeset, adoption or redaction) and metadata: actor, actor type, message, source, correlation ID and idempotency key.
- **Record**: one change inside a revision, kept at a fixed position (its ordinal). Its kind is one of: create or delete a node, add or remove a label, set or remove a property, create or delete a relationship, set or remove a qualifier, or create a temporal edge. Redaction adds two more kinds: a tombstone (`redacted`) and an audit entry (`redact`).
- **Changeset**: the list of operations a caller submits to become one revision.
- **Head**: the newest revision.
- **Statement**: the ledger's identity for one relationship, from its creation to its deletion. A statement ID is a decimal number.
- **Idempotency key**: an optional name the caller gives a changeset so that a retry can be recognized.
- **Fingerprint**: a hash of a changeset's actor, actor type and operations.
- **Genesis**: the first revision. It describes the graph as it was when the ledger was turned on.
- **Adoption**: a revision that records changes made outside the ledger.
- **Strict mode**: a setting of an enabled ledger that refuses graph writes that bypass the ledger.

## Revisions and lifecycle

<a id="ledger.revision"></a>
[I · ledger.revision]

Every revision is permanent and numbered. Seq numbers increase by one with no gaps, and each revision's parent is the revision before it.

<a id="ledger.lifecycle"></a>
[I · ledger.lifecycle]

The ledger is off until someone enables it.

- The first enable writes a genesis revision that describes the current graph.
- Enabling a ledger that is already enabled changes nothing and returns the head.
- The first enable sets strict mode, the size limit for a changeset and the size bound for a reconstruction. Strict mode can be switched later.
- Disabling is safe to repeat. While the ledger is disabled, commits and redactions are refused with `LedgerDisabledError` and nothing is recorded. Before the first enable they are refused with `LedgerNotEnabledError`.
- Today, disabling does not cancel an unfinished redaction: its next batch is refused with `LedgerDisabledError`, the marker stays, and the caller runs the same redaction again after enabling. Whether disable should be refused instead is [open](#ledger.lifecycle.disable-during-redaction).
- Enabling again while a redaction is unfinished skips the adoption below without an error.
- Enabling again records the changes made while it was disabled as an adoption revision.

<a id="ledger.lifecycle.genesis"></a>
[D · ledger.lifecycle.genesis]

The genesis records every node, label and property in the namespace as default-graph content, and every relationship with its own graph. It leaves out the plain relationship row that a temporal edge creates, because the ledger does not govern that row. So a node ID held by two graphs gets two node-create records, and the labels and properties of both nodes are recorded under that one ID.

<a id="ledger.lifecycle.genesis.shared-ids"></a>
[Q · ledger.lifecycle.genesis.shared-ids]

How should the genesis treat a node ID that two graphs hold? Provisional answer: none recorded. Today the two nodes are merged under one ID, although a human decision says the same ID in two graphs is two nodes.

- Merging matches how verify compares nodes, but loses which graph held which label or property, against the decision that each graph's labels and properties are its own.
- When both graphs give the same property different values, which value the replay keeps and which one verify reads are not tied to each other, so verify could report a false difference.

<a id="ledger.lifecycle.disable-during-redaction"></a>
[Q · ledger.lifecycle.disable-during-redaction]

What should disabling the ledger do while a redaction is unfinished? There is no provisional answer. Today disable is accepted, the redaction's next batch is refused, and the caller must run the redaction again after enabling; that enable skips its adoption without an error.

## Changesets and commits

<a id="ledger.changeset"></a>
[I · ledger.changeset]

A changeset holds one or more operations in order: node, label, property, relationship, qualifier and temporal-edge changes.

- A reserved property name (`id`, `__graph`) is refused before anything is applied.
- A relationship is named by exactly one of these: its statement ID, its source, predicate, target and graph, or an earlier create in the same changeset.
- The same changeset always produces the same JSON form and the same fingerprint.

<a id="ledger.commit"></a>
[I · ledger.commit]

A commit applies a whole changeset as one new revision, or applies nothing. The exception is the changeset's [post-commit properties](#ledger.commit.post-commit), which are written after the revision and are not part of it.

- It returns the new revision, whether it was a replay, and the statement ID of each relationship it created, by operation position.
- A failing operation is reported by its zero-based position in the changeset.
- A relationship to a node that exists in no graph fails with `NodeNotFoundError`, unless the changeset asks for missing nodes to be created.
- Creating a relationship that already exists in its graph fails, unless the operation is an upsert, which merges the qualifiers. A temporal edge's plain row is taken over by the create instead.
- A revision, its records and its changes become visible together.
- The changes apply in order, each on top of the last. Two writes of one property in a changeset keep both records, prior value and new value each time, and the property shows the last value. Writing the value a property already has records nothing.
- The first change that fails stops the commit, and every earlier change of the changeset is rolled back with it: no revision, no record and no content change remains.

<a id="ledger.commit.admission"></a>
[D · ledger.commit.admission]

A commit is checked in a fixed order before anything is applied. The order is: take the head lock, check that the ledger is enabled, check the idempotency key, check the expected head, check the size. So a retry that matches its idempotency key replays even when its expected head is now stale.

- A reserved property name is refused when the operation is added to the changeset. The server checks it again while applying, and a refusal there rolls the whole commit back.
- While a redaction is unfinished, the operations are applied first and then checked against its target. A commit with any record in the target is refused, and its transaction rolls back ([rule](redaction.g5.md#redaction.batches.commits)).

<a id="ledger.commit.serial"></a>
[I · ledger.commit.serial]

Commits run one at a time, so the history stays one chain even with many writers. A commit waits up to 30 seconds for the head lock and then fails with `LedgerLockTimeoutError`, which is safe to retry.

<a id="ledger.commit.expected-head"></a>
[I · ledger.commit.expected-head]

A changeset may name the head it expects. If another revision was committed first, the commit fails with `StaleHeadError`, names the current head and writes nothing. An expected head that is not a revision of this ledger fails with `UnknownRevisionError`.

<a id="ledger.commit.size"></a>
[I · ledger.commit.size]

For a changeset commit, an empty changeset is refused with `EmptyChangesetError`. So is a changeset with more operations than the ledger's limit, with `ChangesetTooLargeError`; the limit is 50,000 unless set otherwise when the ledger is enabled.

<a id="ledger.commit.kind"></a>
[Q · ledger.commit.kind]

Should callers be able to choose a commit's kind? Provisional answer: no, it should be internal, because only verify needs the adoption kind.

- Today `commit` accepts any kind. A kind other than changeset skips the empty and size checks.
- The adoption kind records the given differences without changing the tables.
- Any other kind, such as `genesis` or `redaction`, is applied like a changeset but labeled with that kind.

<a id="ledger.commit.caller-transaction"></a>
[D · ledger.commit.caller-transaction]

A commit made inside the caller's open transaction is part of that transaction. The caller's rollback removes the revision and its changes without leaving a gap in the numbering. The head stays locked until the caller's transaction ends.

- Enabling the ledger and redaction refuse to run inside a caller's transaction.

<a id="ledger.commit.post-commit"></a>
[D · ledger.commit.post-commit]

A changeset can carry post-commit properties: default-graph node properties written after the revision, with `$REVISION_ID` replaced by the new revision's ID. They are not recorded in the revision, so verify reports them as unrecorded writes.

- Without a caller's transaction they are a second commit, so a failure keeps the revision and is returned in the result as `post_commit_error`, not raised.
- Inside a caller's transaction they join it, and the caller's rollback removes them with the revision.

<a id="ledger.commit.post-commit.recorded"></a>
[Q · ledger.commit.post-commit.recorded]

Should post-commit properties be recorded in the ledger, left out of verify, or only documented as unrecorded writes? There is no provisional answer. Today they are unrecorded, verify reports them, and neither strict mode nor the block on commits into a target being redacted checks them.

## Idempotency and retries

<a id="ledger.idempotency"></a>
[I · ledger.idempotency]

A commit with the same idempotency key and the same fingerprint as an earlier revision returns that revision, marked as replayed, and changes nothing.

- The fingerprint covers only the actor, actor type and operations, so a retry with a new message or correlation ID still replays.
- The same key with different operations fails with `IdempotencyConflictError`.
- A key used only by a refused commit stays free.
- Two commits sent at once with the same key make one revision.
- A key whose revision was later redacted is refused instead ([rule](redaction.g5.md#redaction.idempotency)).

<a id="ledger.idempotency.key-required"></a>
[D · ledger.idempotency.key-required]

Retry protection needs an idempotency key. A changeset without one is applied again when it is sent again.

## Scope of ledger content

<a id="ledger.node-scope"></a>
[D · ledger.node-scope]

The ledger keeps nodes in the default graph. Its node operations read and write only default-graph rows, and its node records name no graph. Relationship records name the relationship's own graph.

- One exception: a relationship created in a named graph adds bare node rows for its endpoints in that graph, if they are missing there. The database requires those rows. They get no node records.
- An endpoint counts as existing if its ID exists in any graph.

<a id="ledger.immutability"></a>
[I · ledger.immutability]

Revision rows cannot be changed or deleted, through SQL or through objects, and every record keeps its position. The only exception is redaction, which turns records into tombstones and empties four free-text fields ([exception](redaction.g5.md#redaction.metadata.exception)).

<a id="ledger.unrecorded"></a>
[I · ledger.unrecorded]

Graph writes made outside the ledger still work while it is enabled, but they create no records. Verify reports them, verify with adoption records them, and strict mode refuses them.

<a id="ledger.strict"></a>
[I · ledger.strict]

In strict mode, these engine calls are refused with `LedgerStrictModeError` and change nothing, so ledger commits are the engine's only way to change the governed graph, apart from a commit's own [post-commit properties](#ledger.commit.post-commit), which strict mode does not check. The [access rules](../concepts/access.g5.md#access.ledger_strict) say which callers and surfaces this governs.

- Node and edge writes: `create_node`, `store_node`, `create_edge`, `store_edge`, `set_edge_weight`, `delete_edge`, `delete_node`.
- Bulk writes: `bulk_create_nodes`, `bulk_create_edges`, `bulk_ingest_edges`, `bulk_delete_nodes`, `bulk_load_session`.
- Erases: `erase_graph` (and its old name `drop_graph`), `erase_all` and `delete_nodes_by_prefix`.
- Reifications and inference: `reify_edge`, `delete_reification`, `materialize_inference`, `retract_inference`.
- Imports and restore: `import_graph_ndjson`, `import_rdf`, `load_networkx`, `restore_snapshot`.
- Cypher through `execute_cypher` with any updating clause.
- The store's `write_nodes`, `write_edges`, `delete_nodes`, `delete_edges` and `erase_bare_nodes`.
- The bulk loader class and raw SQL are not guarded.
- A direct temporal-edge write is never refused, because strict mode does not govern direct temporal writes or their plain rows ([rule](temporal.g5.md#temporal.structural.ledger)). A temporal write inside a changeset is part of the revision ([temporal edges in a changeset](temporal.g5.md#temporal.ledger)).

<a id="ledger.strict.fail-open"></a>
[Q · ledger.strict.fail-open]

When the engine cannot read the ledger's state, should a strict-mode check allow the write or refuse it? Provisional answer: none; today the check allows the write. A later fix treated one such case, a writer without access to the class dictionary, as a defect.

## Reading the ledger

<a id="ledger.readers"></a>
[I · ledger.readers]

Readers show the ledger without changing it.

- History lists revisions in order and in pages. It can filter by actor, actor type, time, correlation ID and source.
- A revision's records come back in ordinal order, with prior and new values.
- A diff between two revisions gives the net change, nodes first, then relationships, each sorted by entity ID and attribute. The diff in the other direction is its exact inverse.
- Reconstruct returns the graph as of a revision. Above 250,000 nodes and relationships (set at enable) it refuses with `ReconstructionTooLargeError` unless asked to stream.
- Export writes a reconstruction as NDJSON that `import_graph_ndjson` accepts, with no size bound.

## Verification

<a id="ledger.verify"></a>
[I · ledger.verify]

Verify replays every revision from the first to the head and compares the result with the current tables. It reports `equal`, or `diverges` with the differences. When asked to adopt, it records the differences as an adoption revision so that the next verify is equal.

<a id="ledger.verify.meaning"></a>
[D · ledger.verify.meaning]

"Verifiable" means that replaying the history gives the current store. No hash chain covers the records, and the commit fingerprint exists only to recognize retries.

<a id="ledger.verify.scope"></a>
[D · ledger.verify.scope]

Verify compares the structural graph only.

- Nodes are matched by ID across all graphs, with their labels and properties. Reserved properties are left out.
- Relationships are matched by source, predicate, target and graph, with their qualifiers. Statement IDs are not compared.
- The plain relationship row of a temporal edge is left out on both sides, and the temporal index itself is not compared.

<a id="ledger.verify.consistency"></a>
[Q · ledger.verify.consistency]

Must verify compare one consistent moment of the ledger and the tables? Provisional answer: verify is best-effort, so run it when writes are quiet.

- Today it reads both without a lock, and the adoption it commits names no expected head.
- So a commit made during a verify can show up as a difference or be recorded twice.

## Metadata

### ledger.revision

- Sources: [CONTEXT.md History](../../../CONTEXT.md#L181-L217), [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md), [Ledger.cls WriteRevision](../../../iris_src/src/Graph/KG/Ledger.cls#L532-L567)
- Children: [Lifecycle](#ledger.lifecycle)
- agent
- data-integrity, architecture-decision
- test-coverage

Live test: `tests/integration/test_ledger_us03_concurrency.py` (eight writers, contiguous single-parent history) and `tests/e2e/test_470_ledger_caller_txn_e2e.py` (no gap after a caller rollback).

### ledger.lifecycle

- Sources: [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md), [Ledger.cls Enable/Disable](../../../iris_src/src/Graph/KG/Ledger.cls#L250-L358), [client.py enable](../../../iris_vector_graph/ledger/client.py#L281-L303)
- Expands: [Revision](#ledger.revision)
- Children: [Genesis](#ledger.lifecycle.genesis), [Disable during a redaction](#ledger.lifecycle.disable-during-redaction)
- agent
- user-facing-behavior, operations
- test-coverage

Live tests: `test_ledger_us01_commit_head.py` (genesis) and `test_ledger_us09_verify.py::test_disable_and_reenable_adopts`. Enable takes `strict`, `max_ops` and `recon_bound`; `set_strict` switches strict mode and takes no head lock. The redaction's stop on disable is a code comment in [LedgerRedact.cls BatchInLock](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L302-L305); disable itself takes no head lock and does not refuse while a redaction is unfinished. Observed divergence: re-enabling while a redaction is unfinished skips the adoption without reporting it, because verify returns `redaction_in_progress`.

Findings: [Re-enabling the ledger during an unfinished redaction skips the adoption without telling the caller](../../Verus_verification/bugs_issues.md#bug-led-004); [What should disabling the ledger do while a redaction is unfinished?](../../Verus_verification/open_questions.md#q-led-003)

### ledger.lifecycle.genesis

- Sources: [LedgerGenesis.cls](../../../iris_src/src/Graph/KG/LedgerGenesis.cls), [CHANGELOG 4.6.0 ledger fixes](../../../CHANGELOG.md#L2210-L2227), [CHANGELOG 4.4.0](../../../CHANGELOG.md#L2767-L2769)
- Expands: [Lifecycle](#ledger.lifecycle)
- Children: [Shared node IDs](#ledger.lifecycle.genesis.shared-ids)
- agent
- data-integrity
- test-coverage

The genesis scans the node, label and property tables with no graph condition ([LedgerGenesis.cls Capture](../../../iris_src/src/Graph/KG/LedgerGenesis.cls#L14-L36)). The genesis spells a default-graph relationship's graph as the NUL character read from SQL; verify treats every spelling of the default graph as one. Before 4.6.0 the genesis recorded temporal edges' plain rows, which made verify diverge right after enable (R094). Live tests: `test_ledger_us01_commit_head.py::test_genesis_on_prepopulated_graph_describes_it_and_leaves_view_unchanged`, `tests/e2e/test_460_ledger_temporal_edge_e2e.py`.

### ledger.lifecycle.genesis.shared-ids

- Sources: [LedgerGenesis.cls Capture](../../../iris_src/src/Graph/KG/LedgerGenesis.cls#L14-L36), [replay.py read_canonical](../../../iris_vector_graph/ledger/replay.py#L588-L612), [reconstruction check G8](../../uplift/ivg-verus-initial/reconstruction-check.md#L398)
- Expands: [Genesis](#ledger.lifecycle.genesis)
- agent
- uncertain
- data-integrity

Since the node table is keyed by (graph, node ID), one ID can be held by two graphs. Genesis reads properties ordered by node ID and key only, and verify reads them unordered, so the two sides need not keep the same value when the graphs disagree. Not tested.

Findings: [How should the ledger's genesis record a node ID that two graphs hold?](../../Verus_verification/open_questions.md#q-led-004)


### ledger.lifecycle.disable-during-redaction

- Sources: [LedgerRedact.cls BatchInLock](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L302-L305), [Ledger.cls Enable/Disable](../../../iris_src/src/Graph/KG/Ledger.cls#L331-L351)
- Expands: [Lifecycle](#ledger.lifecycle)
- agent
- uncertain
- operations, data-integrity
- test-coverage

Observed: [redaction_interrupt_resume](../../Verus_verification/receipts/native/redaction_interrupt_resume.json) (the batch after disable is refused `LedgerDisabledError`, verify mid-way reports `redaction_in_progress`, the rerun after enable completes with the uninterrupted end state). Review round 3 R3-reader M2 moved this out of the lifecycle body, where it read as a rule.

Findings: [What should disabling the ledger do while a redaction is unfinished?](../../Verus_verification/open_questions.md#q-led-003); [Re-enabling the ledger during an unfinished redaction skips the adoption without telling the caller](../../Verus_verification/bugs_issues.md#bug-led-004)
### ledger.changeset

- Sources: [changeset schema](../../../specs/213-graph-revision-ledger/contracts/changeset.schema.json), [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L36-L80), [changeset.py](../../../iris_vector_graph/ledger/changeset.py)
- agent
- user-facing-behavior
- test-coverage

Live test: `test_ledger_us02_rollback.py::test_reserved_property_rejected_before_any_apply`. The contract schema has not been updated for temporal-edge operations or for redaction's record kinds.

### ledger.commit

- Sources: [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md), [USER_GUIDE section 9](../../../docs/USER_GUIDE.md#L1052-L1115), [errors.py](../../../iris_vector_graph/ledger/errors.py); ordered application and stop at the first failure: [`iris_src/src/Graph/KG/LedgerApply.cls::ApplyAll`](../../../iris_src/src/Graph/KG/LedgerApply.cls#L18-L48); set property records prior and new, same value writes nothing: [`LedgerApply.cls`](../../../iris_src/src/Graph/KG/LedgerApply.cls#L265-L317); live tests [`test_duplicate_set_property_records_both_and_last_wins`, `test_failing_op_mid_changeset_leaves_everything_unchanged`](../../../tests/integration/test_ledger_us02_rollback.py#L62-L136)
- Playbook: [LED-B4.10](../../../experiment/playbook-completion/ontology/11-ledger.md#L190), [LED-B5.9](../../../experiment/playbook-completion/ontology/11-ledger.md#L236), record fold [RPL-T90](../../../experiment/playbook-completion/ontology/14-replay.md#L61)
- Verus: active family for the composed rule (public case M03) is the playbook's `proofs-pa3` `ledger_l2` (reviewed design: ordered `rec_put` with sequence and ordinal, ordered fold, abort; the copy of `proofs-breadth` without premise P-A3), with `ledger_redaction` (as-built) [`redaction.rs`](../../Verus_verification/models/ledger_redaction/redaction.rs) `apply`/replay and the commit-admission theorems as overlapping evidence that covers ordered records and rejection separately. See [families](../../Verus_verification/families.tsv).
- Children: [Admission order](#ledger.commit.admission), [One at a time](#ledger.commit.serial), [Expected head](#ledger.commit.expected-head), [Size](#ledger.commit.size), [Commit kind](#ledger.commit.kind), [Caller's transaction](#ledger.commit.caller-transaction), [Post-commit properties](#ledger.commit.post-commit)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Relationship create, upsert and the take-over of a temporal edge's plain row: [LedgerApply.cls OpCreateRel](../../../iris_src/src/Graph/KG/LedgerApply.cls#L450-L487). The endpoint check is graph-blind on purpose: `node_not_found` means the ID is unknown anywhere ([LedgerApply.cls EnsureEndpoint](../../../iris_src/src/Graph/KG/LedgerApply.cls#L85-L110)). Observed divergence: a replayed commit returns no statement IDs (see [idempotency](#ledger.idempotency)). Live tests: `test_ledger_us02_rollback.py` (a failing operation in the middle leaves everything unchanged), `tests/integration/test_217_ledger_missing_node_e2e.py` and `test_ledger_us11_temporal_coexist.py::test_a_governed_relationship_on_a_temporal_triple_adopts_its_row`.

### ledger.commit.admission

- Sources: [Ledger.cls CommitInTxn](../../../iris_src/src/Graph/KG/Ledger.cls#L419-L528), [Ledger.cls header](../../../iris_src/src/Graph/KG/Ledger.cls#L16-L17)
- Playbook: [LED-B4.1](../../../experiment/playbook-completion/ontology/11-ledger.md#L144), [LED-B4.7](../../../experiment/playbook-completion/ontology/11-ledger.md#L153)
- Verus: active for the replay-versus-conflict outcomes (public M01): `G-ledger_redaction` (as-built) [`redaction.rs`](../../Verus_verification/models/ledger_redaction/redaction.rs) `theorem_retry_replays_first`, `theorem_commit_writes_only_when_admitted`, `lemma_commit_admits_matches_outcome` (controls in its model.json); overlapping: the playbook's `proofs-pa3` `ledger_l1.rs::theorem_replay_returns_bound_revision`, `theorem_key_binds_one_fingerprint` (reviewed design). See [families](../../Verus_verification/families.tsv).
- Expands: [Commit](#ledger.commit)
- agent
- architecture-decision
- test-coverage

The precedence is spec 213 FR-019, cited by the code; the spec text itself is not in the repository. The redaction-target check runs after `ApplyAll`, inside the commit transaction ([Ledger.cls](../../../iris_src/src/Graph/KG/Ledger.cls#L500-L518)). The reserved-property check is in the changeset builder ([changeset.py](../../../iris_vector_graph/ledger/changeset.py#L63-L67)) and again in each node operation ([LedgerApply.cls](../../../iris_src/src/Graph/KG/LedgerApply.cls#L223-L227)). Live tests: `test_ledger_us04_idempotency.py::test_replay_wins_over_stale_expected_head`, `test_ledger_us02_rollback.py::test_reserved_property_rejected_before_any_apply`, `test_256_ledger_redaction_e2e.py::TestBatchesAndMarker`.

### ledger.commit.serial

- Sources: [Ledger.cls LOCKTIMEOUT and lock](../../../iris_src/src/Graph/KG/Ledger.cls#L21), [errors.py LedgerLockTimeoutError](../../../iris_vector_graph/ledger/errors.py#L78-L79)
- Playbook: [LED-B4.7.5](../../../experiment/playbook-completion/ontology/11-ledger.md#L162), [LED-B4.7.6](../../../experiment/playbook-completion/ontology/11-ledger.md#L166)
- Verus: active for one winner among concurrent same-key writers (public J05): the playbook's `proofs-pa3` `ledger_l2.rs` head lock and binding steps (**reviewed design**; the pin's departure for erasure, which takes no head lock, is control `control_f1201_erase_no_head_lock`, finding F-1201, rerun here). Overlapping: `G-ledger_redaction` (as-built), which takes the lock and the binding as inputs.
- Expands: [Commit](#ledger.commit)
- agent
- data-integrity, operations
- test-coverage

Live tests: `test_ledger_us03_concurrency.py`, `test_ledger_lock_and_chunks.py::test_commit_gives_up_when_another_process_holds_the_head_lock`.

### ledger.commit.expected-head

- Sources: [Ledger.cls expected_head](../../../iris_src/src/Graph/KG/Ledger.cls#L475-L486), [USER_GUIDE Concurrency](../../../docs/USER_GUIDE.md#L1100-L1101)
- Expands: [Commit](#ledger.commit)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live tests: `test_ledger_us03_concurrency.py::test_two_writers_same_expected_head_exactly_one_wins`, `::test_unknown_expected_head_is_distinct_error`.

### ledger.commit.size

- Sources: [Ledger.cls size checks](../../../iris_src/src/Graph/KG/Ledger.cls#L488-L498), [ledger API contract enable](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L22)
- Expands: [Commit](#ledger.commit)
- agent
- user-facing-behavior
- test-coverage

Live tests: `test_ledger_us01_commit_head.py::test_foundation_enable_and_reject_empty`, `test_ledger_us02_rollback.py::test_too_large_rejected_before_apply`.

### ledger.commit.kind

- Sources: [client.py commit](../../../iris_vector_graph/ledger/client.py#L381-L401), [Ledger.cls kind handling](../../../iris_src/src/Graph/KG/Ledger.cls#L488-L509), [replay.py adoption commit](../../../iris_vector_graph/ledger/replay.py#L851-L858), [reconstruction check 2(a)11](../../uplift/ivg-verus-initial/reconstruction-check.md#L515-L523)
- Expands: [Commit](#ledger.commit)
- agent
- uncertain
- data-integrity, security

A caller-chosen `redaction` kind would put a revision in history that looks like a redaction's audit. The spec 213 contract lists `commit(changeset)` with no kind parameter.

Findings: [Should callers be able to choose a commit's kind?](../../Verus_verification/open_questions.md#q-led-005)

### ledger.commit.caller-transaction

- Sources: [Ledger.cls Commit](../../../iris_src/src/Graph/KG/Ledger.cls#L385-L415), [CHANGELOG 4.7.0](../../../CHANGELOG.md#L76-L86), [USER_GUIDE writes inside your transaction](../../../docs/USER_GUIDE.md#L285-L310), [client.py commit](../../../iris_vector_graph/ledger/client.py#L381-L401)
- Expands: [Commit](#ledger.commit)
- agent
- architecture-decision, data-integrity
- test-coverage

This supersedes spec 213 FR-047, under which a commit refused an open transaction. The commit message quotes FR-047's reason from a research file that is not in the repository. Live test: `tests/e2e/test_470_ledger_caller_txn_e2e.py`.


### ledger.commit.post-commit

- Sources: [changeset.py post_commit_properties](../../../iris_vector_graph/ledger/changeset.py#L18-L25), [client.py _apply_post_commit_properties](../../../iris_vector_graph/ledger/client.py#L430-L487), [CHANGELOG spec 218](../../../CHANGELOG.md#L4991-L4998), [USER_GUIDE writes inside your transaction](../../../docs/USER_GUIDE.md#L288-L289)
- Expands: [Commit](#ledger.commit)
- Children: [Recorded?](#ledger.commit.post-commit.recorded)
- agent
- user-facing-behavior, data-integrity
- test-coverage

The code calls this "Approach A — direct SQL, no new revision"; each property is a delete then an insert scoped to the default graph, in one IVG transaction level. The IDs need not exist as nodes, so a property row can have no node row. Observed: [ledger_post_commit_verify](../../Verus_verification/receipts/native/ledger_post_commit_verify.json) (verify diverges after a commit with post-commit properties); [redaction_orphan_prop_blocks](../../Verus_verification/receipts/native/redaction_orphan_prop_blocks.json) (such a row survives a prefix erase). Added by review round 3 R3-reader H1; round 2 R2-4 had added only Metadata links.

Findings: [Post-commit properties bypass strict mode and the block on commits into a target being redacted](../../Verus_verification/bugs_issues.md#bug-led-009); [A property row with no node row survives the prefix erase, and every later prefix redaction of its tenant is refused](../../Verus_verification/bugs_issues.md#bug-led-010)

### ledger.commit.post-commit.recorded

- Sources: [client.py _apply_post_commit_properties](../../../iris_vector_graph/ledger/client.py#L430-L487), [replay.py verify](../../../iris_vector_graph/ledger/replay.py#L806-L867)
- Expands: [Post-commit properties](#ledger.commit.post-commit)
- agent
- uncertain
- data-integrity, security

The strict-mode and redaction-marker gaps are from code reading (suspected); the verify divergence is observed.

Findings: [Should post-commit properties be recorded, excluded from verify, or documented as unrecorded writes?](../../Verus_verification/open_questions.md#q-010)
### ledger.idempotency

- Sources: [Ledger.cls idempotency](../../../iris_src/src/Graph/KG/Ledger.cls#L454-L473), [changeset.py fingerprint](../../../iris_vector_graph/ledger/changeset.py#L365-L386), [ledger API contract commit](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L26)
- Playbook: [LED-B4.7](../../../experiment/playbook-completion/ontology/11-ledger.md#L153), [LED-B4.7.4](../../../experiment/playbook-completion/ontology/11-ledger.md#L161)
- Verus: active for the binding history across refused and successful attempts (public M02): the playbook's `proofs-pa3` [`ledger_l2.rs`](../../../experiment/playbook-completion/proofs-pa3/src/ledger_l2.rs) `commit_glob`, `lay_idem` with [`ledger_l1.rs`](../../../experiment/playbook-completion/proofs-pa3/src/ledger_l1.rs) `theorem_key_binds_one_fingerprint`, `theorem_replay_returns_bound_revision` (**reviewed design**; no control in that family reintroduces a pin departure for the binding, so the design and the pin agree there by the playbook's audit, not by proof). Overlapping: `G-ledger_redaction` `theorem_retry_replays_first` (as-built), which reads a supplied binding instead of deriving it.
- Children: [Key required](#ledger.idempotency.key-required)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live test: `test_ledger_us04_idempotency.py`. Observed divergence: a replay returns no statement IDs, although the contract promises the original outcome. Also, `post_commit_properties` are outside the fingerprint and are applied again on a replay.

Findings: [A replayed commit applies its post-commit properties again over newer values and returns no statement IDs](../../Verus_verification/bugs_issues.md#bug-led-003)

### ledger.idempotency.key-required

- Sources: [Ledger.cls idempotency](../../../iris_src/src/Graph/KG/Ledger.cls#L455-L465), [USER_GUIDE Retries](../../../docs/USER_GUIDE.md#L1102), [errors.py IdempotencyConflictError](../../../iris_vector_graph/ledger/errors.py#L42-L43)
- Expands: [Idempotency](#ledger.idempotency)
- agent
- user-facing-behavior

Documentation divergence: the user guide says that sending the same actor and operations again returns the first revision as replayed, and does not mention the key. [A-history notes F7](../../uplift/ivg-verus-initial/intent/ledger-history.md).

Findings: [The user guide says a repeated commit replays, which holds only with an idempotency key](../../Verus_verification/bugs_issues.md#bug-doc-002)

### ledger.node-scope

- Sources: [ADR-0013 Context](../../../docs/adr/0013-redaction-removes-content-from-history.md#L37), [LedgerApply.cls node statements](../../../iris_src/src/Graph/KG/LedgerApply.cls), [CHANGELOG 4.6.0 ledger node writes](../../../CHANGELOG.md#L2220-L2227)
- agent
- architecture-decision, data-integrity
- test-coverage

Before 4.6.0, node operations matched rows by ID in every graph (R290, R281). The endpoint rows come from `EnsureEndpoint` ([LedgerApply.cls](../../../iris_src/src/Graph/KG/LedgerApply.cls#L85-L110)): the table's composite foreign keys need an endpoint row in the relationship's graph. Verify does not see these unrecorded rows as differences, because it compares nodes by ID across graphs. Consequence: a named-graph target can never reach node records ([redaction target](redaction.g5.md#redaction.target.nodes)), and verify compares nodes without regard to graph. Live test: `tests/e2e/test_460_r290_ledger_node_ops_graph_e2e.py`.

### ledger.immutability

- Sources: [LedgerRevision.cls](../../../iris_src/src/Graph/KG/LedgerRevision.cls), [ADR-0013 the one exception](../../../docs/adr/0013-redaction-removes-content-from-history.md#L20-L29)
- agent
- data-integrity, security
- test-coverage

Spec 213 FR-023 is cited by the class but its text is not in the repository. Live tests: `test_ledger_us01_commit_head.py::test_revisions_are_immutable_via_sql` and `test_256_ledger_redaction_e2e.py::test_outside_the_redaction_a_redacted_revision_is_still_immutable`.

### ledger.unrecorded

- Sources: [USER_GUIDE writes outside the ledger](../../../docs/USER_GUIDE.md#L1107-L1109), [replay.py verify](../../../iris_vector_graph/ledger/replay.py#L806-L867)
- agent
- user-facing-behavior
- test-coverage

Live tests: `test_ledger_us05_compat.py`, `test_ledger_us09_verify.py::test_legacy_and_raw_sql_writes_are_unrecorded`.

Findings: [Post-commit properties bypass strict mode and the block on commits into a target being redacted](../../Verus_verification/bugs_issues.md#bug-led-009)

### ledger.strict

- Sources: [ledger API contract strict mode](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L82-L93), [guard.py](../../../iris_vector_graph/ledger/guard.py), [nodes_edges.py erase_graph](../../../iris_vector_graph/_engine/nodes_edges.py#L1473-L1530), [temporal.py structural step](../../../iris_vector_graph/_engine/temporal.py#L304-L312), [access.ledger_strict](../concepts/access.g5.md#access.ledger_strict)
- Children: [Fail open](#ledger.strict.fail-open)
- agent
- user-facing-behavior, security
- test-coverage

The list is the contract's, plus calls added after it: `erase_graph` replaced `drop_graph`, and `erase_all`, `delete_nodes_by_prefix`, `import_rdf`, `bulk_load_session` and `erase_bare_nodes` are guarded the same way. The erase guards block the erase step that redaction needs ([open question](redaction.g5.md#redaction.strict-mode)). The contract's sentence that a temporal write "skips the structural mirror" predates ADR-0009. The engine skips only its own client-side structural step; with the adjacency index declared, the server still writes the marked row. Observed and not guarded: embedding, vector-index and BM25 writes are outside the ledger by decision ([surfaces](../concepts/access.g5.md#access.ledger_strict.surfaces)); the deprecated `bulk_delete_adjacency` and the sample API's Cypher route are undocumented bypasses ([bypasses](../concepts/access.g5.md#access.ledger_strict.bypasses)); `set_multigraph`, FHIR sync and the `Prop_Set` and `Txn_*` SQL procedures are undecided ([open question](../concepts/access.g5.md#access.ledger_strict.undecided)) ([operations inventory](../../uplift/ivg-verus-initial/intent/operations.md#L257-L262)). Live test: `test_ledger_us05_compat.py::test_every_guarded_api_is_rejected_and_nothing_changes`.

Findings: [bulk_delete_adjacency deletes relationships under strict mode without a record](../../Verus_verification/bugs_issues.md#bug-plt-006); [Enforce strict ledger mode once, on the server, instead of in each Python engine](../../Verus_verification/design_simplification.md#simp-plt-001); [Is strict mode promised from the moment set_strict returns, or within a few seconds for other engines?](../../Verus_verification/open_questions.md#q-plt-001)

### ledger.strict.fail-open

- Sources: [guard.py probe](../../../iris_vector_graph/ledger/guard.py#L38-L59), [CHANGELOG 4.6.0 R206](../../../CHANGELOG.md#L701-L712)
- Expands: [Strict mode](#ledger.strict)
- agent
- uncertain
- security

The guard runs in Python and caches the ledger's state for five seconds, so another engine's change to strict mode can take that long to apply.

Findings: [When the strict-mode guard cannot read the ledger's state, should it allow the write?](../../Verus_verification/open_questions.md#q-plt-009)

### ledger.readers

- Sources: [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L27-L31), [client.py readers](../../../iris_vector_graph/ledger/client.py#L585-L739), [export.py](../../../iris_vector_graph/ledger/export.py)
- agent
- user-facing-behavior
- test-coverage

The diff order is [replay.py _sort_key](../../../iris_vector_graph/ledger/replay.py#L404-L405); the reconstruct bound counts nodes plus relationships while folding ([replay.py reconstruct](../../../iris_vector_graph/ledger/replay.py#L544-L558)). Live tests: `test_ledger_us06_history.py`, `test_ledger_us07_diff.py`, `test_ledger_us08_reconstruct.py`. While a redaction is unfinished some readers refuse ([rule](redaction.g5.md#redaction.batches.readers)).

Findings: [The reverse diff of a range where a node is deleted and re-created reports the earlier revision's property as absent](../../Verus_verification/bugs_issues.md#bug-led-101); questions [Must the streaming history reader bound its memory?](../../Verus_verification/open_questions.md#q-con-001), [Is a ledger diff an ordered script?](../../Verus_verification/open_questions.md#q-con-002). Public cases M04, M05 and J03 read this block; `diff(a, b)` returns `compute_diff(b..a).inverse()` when `a` is later (`ledger/client.py:706-718`), so "the reverse is the inverse" and "the same revision is empty" hold by construction of the selector, and no formal contract here relates `compute_diff` to the two reconstructed states (reviewed plan C, not built).

### ledger.verify

- Sources: [replay.py verify](../../../iris_vector_graph/ledger/replay.py#L806-L867), [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L32), [USER_GUIDE section 9](../../../docs/USER_GUIDE.md#L1084-L1092)
- Children: [Meaning](#ledger.verify.meaning), [Scope](#ledger.verify.scope), [Consistency](#ledger.verify.consistency)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live test: `test_ledger_us09_verify.py`.

Findings: [A temporal write creates endpoint nodes that the ledger never recorded, so verify diverges after the ledger's own temporal operation](../../Verus_verification/bugs_issues.md#bug-tmp-004); [An adopting verify that races a redaction can append the redacted tenant's IDs after the redaction finished](../../Verus_verification/bugs_issues.md#bug-led-001)

### ledger.verify.meaning

- Sources: [spec 256 What the code does today](../../../specs/256-ledger-tenant-redaction/spec.md#L20-L36), [ADR-0013 Context](../../../docs/adr/0013-redaction-removes-content-from-history.md#L35)
- Expands: [Verify](#ledger.verify)
- agent
- architecture-decision, security

The consumer asked for a "chain" that stays verifiable; this block records that no such chain exists.

### ledger.verify.scope

- Sources: [replay.py read_canonical and compare](../../../iris_vector_graph/ledger/replay.py#L588-L698), [replay.py temporal rows](../../../iris_vector_graph/ledger/replay.py#L792-L803)
- Expands: [Verify](#ledger.verify)
- agent
- architecture-decision, data-integrity
- test-coverage

The temporal exclusion follows spec 213 US11, which the code cites ("temporal writes create no revisions"). Ignoring graphs for nodes follows [node scope](#ledger.node-scope). Live tests: `test_ledger_us11_temporal_coexist.py`, `test_ledger_verify_pre_enable_writes.py`.

### ledger.verify.consistency

- Sources: [replay.py verify](../../../iris_vector_graph/ledger/replay.py#L806-L867), [A-history notes F5](../../uplift/ivg-verus-initial/intent/ledger-history.md)
- Expands: [Verify](#ledger.verify)
- agent
- uncertain
- data-integrity

Existing evidence for part of the intent: `test_ledger_us09_verify.py::test_verify_reports_head_observed_at_start` pins the head that verify reports.

Findings: [Must verify compare one consistent moment of the ledger and the tables?](../../Verus_verification/open_questions.md#q-led-006)
