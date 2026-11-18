# Administer and verify the ledger

Start here to enable or disable the ledger, adopt writes or compare the history with the graph. If a redaction is still running, see [what happens when the ledger is disabled](#ledger.lifecycle) and [how to resume](../features/redaction.g5.md#redaction.batches.resume).

## Definitions

- **Ledger**: the history of one namespace's graph changes. It is kept in the global `^IVG.Ledger` and the table `ledger_revisions`.
- **Head**: the newest revision.
- **Genesis**: the first revision. It describes the graph as it was when the ledger was turned on.
- **Adoption**: a revision that records changes made outside the ledger.
- **Strict mode**: a setting of an enabled ledger that refuses graph writes that bypass the ledger.

## Enable, disable and adopt writes

<a id="ledger.lifecycle"></a>
[I · ledger.lifecycle]

The ledger is off until someone enables it.

- The first enable writes a genesis revision that describes the current graph.
- Enabling a ledger that is already enabled changes nothing and returns the head; `enable(strict=True)` then leaves strict mode as it was.
- The first enable sets strict mode, the size limit for a changeset and the size bound for a reconstruction. Strict mode can be switched later.
- Disabling is safe to repeat. While the ledger is disabled, commits and redactions are refused with `LedgerDisabledError` and nothing is recorded, but `head()`, history and the other readers still work. Before the first enable, commits, redactions, `head()`, `verify()` and `set_strict()` are refused with `LedgerNotEnabledError`, and history is empty.
- Today, disabling does not cancel an unfinished redaction: its next batch is refused with `LedgerDisabledError`, the marker stays, and the caller runs the same redaction again after enabling. Whether disable should be refused instead is [open](../../Verus_verification/open_questions.md#q-led-003).
- Enabling again while a redaction is unfinished skips the adoption below without an error.
- Enabling again records, as one adoption revision by `system:ledger-verify`, every difference that verify finds: the changes made while it was disabled and any earlier writes made outside the ledger. Strict mode then comes from this call (off by default), so a `set_strict` made while disabled does not survive it.

- Working assumption: Prefer refusal of disable during unfinished redaction; resumption and blocked readers require a deliberate lifecycle rule.
- Working assumption: Refuse `disable()` and `set_strict()` inside a caller transaction on every engine, as `enable()`/`redact()`.
- Working assumption: Keep `max_ops` and `recon_bound` fixed at genesis. Model strict as set by `enable(strict=...)` on genesis and on every re-enable (default False) and by `set_strict`; record the reset on re-enable as an explicit transition and do not assume strict survives a disable/enable cycle.

<a id="ledger.lifecycle.genesis"></a>
[D · ledger.lifecycle.genesis]

The genesis records every node, label and property in the namespace as default-graph content, and every relationship with its own graph. It leaves out the plain relationship row that a temporal edge creates, because the ledger does not govern that row. So a node ID held by two graphs gets two node-create records, and the labels and properties of both nodes are recorded under that one ID.

- Working assumption: Keep namespace-wide bare node IDs in current genesis behavior; graph-specific ledger identity would require a record/migration decision.
- Working assumption: (a) Compare the identity the ledger governs: default-graph node rows for node records (R290), with named-graph node rows either reported as outside node governance or recorded with their graph (linked to HD-1101/1304). (b) A reader takes a redaction epoch that every redaction start and finish advances, checks the marker, reads, and re-checks both; if either changed it refuses or retries. A post-read marker check alone is not sufficient (a whole redaction can complete inside one read); a shared lock or a genuine snapshot are alternatives. Verify additionally needs a coherent cut between its record read and its table read.

## Observe commits and refusals

<a id="ledger.observability"></a>
[I · ledger.observability]

Each commit that reaches the ledger's server reports its outcome once: a log line and one event to each registered metrics hook. Most outcomes are also counted in the ledger's counters.

- The counters keep the commits written (the genesis included), the replays, and these refusals: a stale or unknown expected head, an idempotency conflict (a key whose revision was redacted included), a failed operation, too many operations, a disabled ledger and a lock timeout. Strict-mode refusals are counted too.
- These outcomes reach a hook but no counter: a refusal before the first enable, a commit refused because it writes into an unfinished redaction's target, and an `inconsistent` refusal, such as a revision field longer than its column ([size](../features/ledger.g5.md#ledger.commit.size)).
- A refused commit made inside the caller's own transaction is never counted. A strict-mode refusal count or a verify record made on the caller's connection inside its transaction is kept or taken back with that transaction ([caller's transaction](../features/ledger.g5.md#ledger.commit.caller-transaction)).
- While another caller's open transaction holds the counter row, no other connection's outcome is counted. Today, when that transaction does not also hold the head, another connection's valid commit is refused as `inconsistent` instead of being written ([caller's transaction](../features/ledger.g5.md#ledger.commit.caller-transaction)). Intended: counting never changes a commit's outcome.
- A refusal the client makes before sending (an empty changeset or a bad operation reference) is neither counted nor reported to a hook ([finding](../../Verus_verification/bugs_issues.md#bug-doc-013)).
- A hook that raises is logged, and the commit's result does not change.

## Compare the ledger with the graph

<a id="ledger.verify"></a>
[I · ledger.verify]

Verify replays every revision from the first to the head and compares the result with the current tables. It reports `equal`, or `diverges` with the differences. When asked to adopt, it records the differences as an adoption revision so that the next verify is equal; when there are no differences it records nothing.

- A node or relationship found only in the tables is reported with its labels, properties or qualifiers; one found only in the history is reported as one deletion, which also removes its attributes when adopted.
- A node is in the tables when it has a node row, a label or a non-reserved property. So a property written for an ID with no node row, such as a post-commit property, is reported as an unrecorded node with that property.
- Today one case never becomes equal: a relationship whose qualifier `temporal` is the text "true" ([scope](#ledger.verify.scope)). Verify reports it as an unrecorded write although the ledger may have recorded it, and every adopting verify, every re-enable included, records it again ([finding](../../Verus_verification/bugs_issues.md#bug-led-013)).

- Working assumption: Treat verify as requiring quiescent inputs for reliance until a consistent-view protocol is specified; unlocked multi-scan behavior is not a snapshot proof.

<a id="ledger.verify.meaning"></a>
[D · ledger.verify.meaning]

"Verifiable" means that replaying the history gives the current store. No hash chain covers the records, and the commit fingerprint exists only to recognize retries.

<a id="ledger.verify.scope"></a>
[D · ledger.verify.scope]

Verify compares the structural graph only.

- Nodes are matched by ID across all graphs, with their labels and properties. Reserved properties are left out.
- Relationships are matched by source, predicate, target and graph, with their qualifiers. Statement IDs are not compared.
- Temporal edges are left out, by a different rule on each side. The tables leave out a relationship row whose qualifier `temporal` is the JSON boolean true, the plain row a temporal write makes. The replay leaves out a recorded relationship whose qualifier `temporal` is the text "true", which is how a genesis before 4.6.0 recorded such a row.
- The temporal index itself is not compared.
- Intended: both sides leave out the same relationships, and a qualifier `temporal` of "true" that a caller gives is an ordinary qualifier, as genesis treats it. As built, the ledger stores every qualifier as text, so a relationship committed with `temporal` "true" (or Python `True`) is kept by the tables and left out of the replay, and verify never reports it equal ([finding](../../Verus_verification/bugs_issues.md#bug-led-013)).

## Metadata

### ledger.lifecycle


- uncertain
- Sources: [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md), [Ledger.cls Enable/Disable](../../../iris_src/src/Graph/KG/Ledger.cls#L250-L358), [client.py enable](../../../iris_vector_graph/ledger/client.py#L281-L303)
- Verus (iteration 60): [ledger_client](../../Verus_verification/models/ledger_client/NOTES.md) `theorem_enable_lifecycle`, `theorem_disable_and_set_strict`, `witness_strict_set_while_disabled_is_reset_by_enable`, `theorem_head_reader_states`; native binding on the local fixture agrees (enable on an enabled ledger keeps strict; a strict flag set while disabled is reset by the next enable).
- Verus (inspected typed adoption slice): [ledger_content alternate](../../Verus_verification/models/ledger_content/NOTES.md) derives adopted identity reuse/allocation and typed contents while retaining permissive payload and duplicate-view boundaries. Raw envelope/parser/tuple-JSON reference handling, canonical SQL changes and truth of supplied priors are not proved. Actual downstream Python readers execute the typed records; bounded native Adopt producer assertions were not run.
- Expands: [Revision](../features/ledger.g5.md#ledger.revision)
- Children: [Genesis](#ledger.lifecycle.genesis), [What should disabling the ledger do while a redaction is unfinished?](../../Verus_verification/open_questions.md#q-led-003)
- agent
- user-facing-behavior, operations

Live tests: `test_ledger_us01_commit_head.py` (genesis) and `test_ledger_us09_verify.py::test_disable_and_reenable_adopts`. Enable takes `strict`, `max_ops` and `recon_bound`; `set_strict` switches strict mode and takes no head lock. The redaction's stop on disable is a code comment in [LedgerRedact.cls BatchInLock](../../../iris_src/src/Graph/KG/LedgerRedact.cls#L302-L305); disable itself takes no head lock and does not refuse while a redaction is unfinished. Observed divergence: re-enabling while a redaction is unfinished skips the adoption without reporting it, because verify returns `redaction_in_progress`.

Findings: [Re-enabling the ledger during an unfinished redaction skips the adoption without telling the caller](../../Verus_verification/bugs_issues.md#bug-led-004); [What should disabling the ledger do while a redaction is unfinished?](../../Verus_verification/open_questions.md#q-led-003)

Open questions: [Should disable() and set_strict() refuse a caller's open transaction, as enable() does?](../../Verus_verification/open_questions.md#HD-1102), [Should the ledger's settings be changeable after the genesis?](../../Verus_verification/open_questions.md#HD-1104), [What should disabling the ledger do while a redaction is unfinished?](../../Verus_verification/open_questions.md#q-led-003)

Findings: [Two ledger test fixtures read a meta() key that does not exist, so their teardown always disables the ledger of the shared scratch namespace](../../Verus_verification/bugs_issues.md#bug-test-004)

State machines: [ledger content](../../Verus_verification/models/ledger_content/manifest.json), [ledger client](../../Verus_verification/models/ledger_client/manifest.json)

Assumption review evidence: Changed from decisions.md: **no** (strengthened). The live run adds a reason: ledger lifecycle state is global and read dirty by other processes, so a joined toggle that is later rolled back has already changed what other writers and guards did. Changed from decisions.md: **no**.

### ledger.lifecycle.genesis


- uncertain
- Sources: [LedgerGenesis.cls](../../../iris_src/src/Graph/KG/LedgerGenesis.cls), [CHANGELOG 4.6.0 ledger fixes](../../../CHANGELOG.md#L2210-L2227), [CHANGELOG 4.4.0](../../../CHANGELOG.md#L2767-L2769)
- Verus (inspected typed projection): [ledger_content alternate](../../Verus_verification/models/ledger_content/NOTES.md) derives Capture records/content from already-projected ordered scan rows, including distinct IDs per physical edge and bare-node graph loss. Source and typed ports are checked, but the native producer, SQL scan completeness/order and arbitrary coercion are unexecuted/unproved; no one-tuple/one-statement invariant is inferred.
- Expands: [Lifecycle](#ledger.lifecycle)
- Children: [How should the ledger's genesis record a node ID that two graphs hold?](../../Verus_verification/open_questions.md#q-led-004)
- agent
- data-integrity

The genesis scans the node, label and property tables with no graph condition ([LedgerGenesis.cls Capture](../../../iris_src/src/Graph/KG/LedgerGenesis.cls#L14-L36)). The genesis spells a default-graph relationship's graph as the NUL character read from SQL; verify treats every spelling of the default graph as one. Before 4.6.0 the genesis recorded temporal edges' plain rows, which made verify diverge right after enable (R094). Live tests: `test_ledger_us01_commit_head.py::test_genesis_on_prepopulated_graph_describes_it_and_leaves_view_unchanged`, `tests/e2e/test_460_ledger_temporal_edge_e2e.py`.

Open questions: [Verification and record readers: node identity and redaction checks](../../Verus_verification/open_questions.md#HD-1401), [How should the ledger's genesis record a node ID that two graphs hold?](../../Verus_verification/open_questions.md#q-led-004)

State machines: [ledger content](../../Verus_verification/models/ledger_content/manifest.json)

Assumption review evidence: Changed from decisions.md: **yes**. (b) the mechanism changes: decisions.md left 'epoch validation, locking or snapshots' open and the original reviewed model used a second marker check; the new live probe shows a complete redaction inside one paged read (default page…

### ledger.observability

- Sources: [ledger-prometheus-hook.md](../../../docs/ledger-prometheus-hook.md), [ledger API contract stats and hook](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L31-L33), [client.py _emit and stats](../../../iris_vector_graph/ledger/client.py#L505-L575), [LedgerStats.cls](../../../iris_src/src/Graph/KG/LedgerStats.cls)
- Verus (iteration 60, repaired after review 60): [ledger_client](../../Verus_verification/models/ledger_client/NOTES.md) `theorem_one_event_per_server_call`, `theorem_uncounted_outcomes` (which outcomes are uncounted, and that nothing is counted while another transaction holds the counter row) and the counter conclusions of `theorem_retry_with_new_metadata_replays`, `theorem_expected_head_outcomes`, `theorem_disabled_and_never_enabled`, `theorem_size_limit_boundary`, `theorem_failed_operation_reported`, `theorem_caller_transaction_holds_the_head`, `theorem_uncounted_nested_refusal_leaves_the_counter_row`; repair 2: `theorem_nested_refusal_is_never_counted`, `theorem_held_counter_row_refuses_a_valid_commit`, `theorem_in_transaction_row_save_blocks_other_writers` (the strict count and verify's record made on the caller's connection); strict-mode refusal counting is [platform](../../Verus_verification/models/platform/NOTES.md) `theorem_strict_paths`.
- Expands: [Commit](../features/ledger.g5.md#ledger.commit)
- agent
- operations
- test-coverage

Added in iteration 60 from the test-obligation map ([obligations](../../uplift/consolidated/iteration-60/test-obligations.md)): `test_ledger_observability.py` and the guard and hook unit tests assert one event and one counter per outcome. The iteration-60 text claimed a count for every outcome that reaches the server; review 60 (FE-3, FE-4) found three uncounted ones, and the repair binding ([receipt](../../Verus_verification/results/ledger_client/20261117T212518Z-binding/receipt.json), cases B8, B8b, B8c, B18, B20) observed each: a lock timeout behind a counted caller transaction, a redaction-blocked commit and an over-long revision field all send one event and move no counter. The doc's "once per call, whatever the outcome" is wider than the product. Counters are per namespace and count every process; hook events are per Python process. A caller's rollback also takes back that caller's counter changes. The report line that shows these counters is [install.status.ledger](status-and-repair.g5.md#install.status.ledger).

Findings: [The metrics hook is not called for a commit the client refuses before sending, though its document says every commit call reports once](../../Verus_verification/bugs_issues.md#bug-doc-013)

Findings: [A commit refused while another caller's transaction holds the ledger head is not counted, and other counter changes made meanwhile are lost](../../Verus_verification/bugs_issues.md#bug-led-014), [A revision field longer than its column is refused as LedgerInconsistencyError after the changeset was applied, and is not counted](../../Verus_verification/bugs_issues.md#bug-led-015), [While a caller's transaction holds the ledger's counter row but not its head, every other connection's valid commit fails as LedgerInconsistencyError](../../Verus_verification/bugs_issues.md#bug-led-017)

State machines: [ledger client](../../Verus_verification/models/ledger_client/manifest.json)

### ledger.verify

- uncertain
- Sources: [replay.py verify](../../../iris_vector_graph/ledger/replay.py#L806-L867), [ledger API contract](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L32), [USER_GUIDE section 9](../../../docs/USER_GUIDE.md#L1084-L1092)
- Verus (iteration 60, repaired after review 60): [ledger_verify](../../Verus_verification/models/ledger_verify/NOTES.md) `theorem_equal_iff_views_agree`, `theorem_adoption_closes_the_difference` (narrowed to tables with no text-"true" temporal qualifier), `theorem_text_marker_never_equal`, `theorem_adoption_never_closes_a_text_marker`, `lemma_canonical_wf`, `theorem_orphan_property_reports_node`, `theorem_entries_for_created_and_deleted_nodes`, `theorem_adoption_only_when_needed`; quiescent inputs are a premise (q-led-006).
- Children: [Meaning](#ledger.verify.meaning), [Scope](#ledger.verify.scope), [Must verify compare one consistent moment of the ledger and the tables?](../../Verus_verification/open_questions.md#q-led-006)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live test: `test_ledger_us09_verify.py`.

Findings: [A temporal write creates endpoint nodes that the ledger never recorded, so verify diverges after the ledger's own temporal operation](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-004); [An adopting verify that races a redaction can append the redacted tenant's IDs after the redaction finished](../../Verus_verification/bugs_issues.md#bug-led-001)

Findings: [A relationship whose qualifier `temporal` is the text "true" never verifies equal, and every adopting verify records it again](../../Verus_verification/bugs_issues.md#bug-led-013)

Open questions: [Must verify compare one consistent moment of the ledger and the tables?](../../Verus_verification/open_questions.md#q-led-006)

State machines: [ledger verify](../../Verus_verification/models/ledger_verify/manifest.json)

### ledger.verify.meaning

- Sources: [spec 256 What the code does today](../../../specs/256-ledger-tenant-redaction/spec.md#L20-L36), [ADR-0013 Context](../../../docs/adr/0013-redaction-removes-content-from-history.md#L35)
- Expands: [Verify](#ledger.verify)
- agent
- architecture-decision, security

The consumer asked for a "chain" that stays verifiable; this block records that no such chain exists.

### ledger.verify.scope

- Sources: [replay.py read_canonical and compare](../../../iris_vector_graph/ledger/replay.py#L588-L698), [replay.py temporal rows](../../../iris_vector_graph/ledger/replay.py#L792-L803), [LedgerGenesis.cls marker test](../../../iris_src/src/Graph/KG/LedgerGenesis.cls#L62-L72), [LedgerApply.cls QualsJson](../../../iris_src/src/Graph/KG/LedgerApply.cls#L420-L434), [changeset.py _str_value](../../../iris_vector_graph/ledger/changeset.py#L47-L60)
- Verus (iteration 60, repaired after review 60 FE-1): [ledger_verify](../../Verus_verification/models/ledger_verify/NOTES.md) `theorem_node_identity_ignores_graph`, `theorem_reserved_properties_left_out`, `theorem_temporal_marked_rows_left_out` (now the two rules with their neighbours), `theorem_marker_rules_differ`, `theorem_text_marker_never_equal`, `theorem_statement_ids_not_compared`; a node ID with property rows in two graphs is outside the claim (q-led-004).
- Expands: [Verify](#ledger.verify)
- agent
- architecture-decision, data-integrity
- test-coverage

The temporal exclusion follows spec 213 US11, which the code cites ("temporal writes create no revisions"). The intended single rule is stated by `_drop_temporal_marked`'s docstring ("the rule read_canonical applies to the tables, applied to the ledger's side too") and by `LedgerGenesis`'s marker test ("a qualifier temporal of 1 or "true" is an ordinary qualifier"); the iteration-60 text "left out on both sides" hid the difference (review 60 FE-1, CG-1). Ignoring graphs for nodes follows [node scope](../features/ledger.g5.md#ledger.node-scope). Live tests: `test_ledger_us11_temporal_coexist.py`, `test_ledger_verify_pre_enable_writes.py`; `test_read_canonical_ignores_temporal_only_edges` has no edge rows, and no test commits a text "true" qualifier.

Findings: [A relationship whose qualifier `temporal` is the text "true" never verifies equal, and every adopting verify records it again](../../Verus_verification/bugs_issues.md#bug-led-013)

State machines: [ledger verify](../../Verus_verification/models/ledger_verify/manifest.json)
