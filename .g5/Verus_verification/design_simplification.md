# Design simplifications — IVG initial Verus uplift

Proposals only; nothing here is implemented. Each says what makes the current design complicated, what would change, the behavior that must survive and a case that would show a safe change. Index: [findings register](findings.md).

<a id="simp-001"></a>
### Claim the redaction marker for one run, under the head lock, before the first batch

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: HD-1301 (playbook decision: should the redaction's opening check and its marker be one locked step; [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md), intent [HD-1301](../../experiment/playbook-completion/intent/HD-1301.md)). (crosswalk)

Comparison: [As-built](results/ledger_redaction/20261114T044401Z-prove/receipt.json) → [Proposed simplification](results/ledger_redaction/20261114T044401Z-prove/receipt.json)

Scope qualification: both sides are the same Verus model ([redaction.rs](models/ledger_redaction/redaction.rs)); the as-built side is `witness_concurrent_targets_break_the_marker` under `Variant { serial: false, repaired: false }`, the proposal is `witness_repair_refuses_the_interleaving` under `repaired: true`. These are finite witnesses, not state counts; the serialised invariant (`lemma_step_preserves_inv`) is proved for the as-built design only.

What is complicated now: `LedgerRedact.Redact` checks the marker and liveness outside the head lock; the marker is written lazily by the first batch that finds a match; `BatchInLock` and `FinalInLock` never compare the marker with their own target; counters and the redacted-revision list live under the marker and are shared by any run. Correctness therefore depends on callers never running two redactions at once, and readers, commits and receipts all derive their view from a marker no run owns.

Proposal: in the first batch's transaction, under the head lock, re-run the liveness check and write the marker with the run's target digest and a run token; refuse a batch or final step whose token is not the marker's; let a later call of the same target take over a stale token. The "started" state and the separate entry check disappear.

Behavior to preserve: resuming the same target after a pause, error or process death; refusing a different target while one is unfinished; a re-run of a finished target writes nothing and leaves no marker; readers and target commits refused only while a run is unfinished; batches still release the head lock between transactions.

Distinguishing case: the schedule of `redaction_concurrent_targets` (two targets started while a long commit holds the head lock) — the second run must be refused with `redaction_in_progress`, and each completed target must have its own redaction revision.

<a id="simp-cyp-001"></a>
### Name each compiled Cypher class by its code's digest instead of the shape's CRC-32

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/platform/20261114T002651Z-prove/receipt.json) → none

Scope qualification: the as-built side is the witnesses `witness_collision_swaps_the_class_mid_run`, `witness_collision_leaves_another_shapes_code_under_an_ok_entry`, `witness_straggler_recompiles_for_an_old_layout` and `witness_readback_trusts_the_entrys_class` in [platform.rs](models/platform/platform.rs), finite traces rather than state counts; no proposal variant was run. Review R3-platform's scratch check Adv-2 showed that a shape check in `Build` alone closes W-O2b but not W-O2a.

What is complicated now: the class name `IVGC.P<$ZCRC(shape,7)>` (`Gen.cls:69, 183`) is shared by colliding shapes, so `For` must compare the stored shape (`:71`), rebuild the same class for each colliding shape in turn (thrash), check the class name (`:73`) and the lines' SHA-256 digest (R311), and still cannot stop a class changing under a run ([bug-cyp-001](bugs_issues.md#bug-cyp-001), [bug-cyp-007](bugs_issues.md#bug-cyp-007), [bug-cyp-008](bugs_issues.md#bug-cyp-008)).

Proposal: name the class by the SHA-256 already computed for its lines (or by a per-entry sequence) and record it in the entry; have `Build` require the entry's shape and stamp to match the lines it compiles; optionally store shape and stamp as class parameters and compare them in `RunA`.

Behavior to preserve: one class per shape and layout; interpreted until built; R311's digest check; a deploy and `Gen.DropAll()` still discard every class.

Distinguishing case: two shapes forced to one CRC-32 by a test hook, run alternately in job and sync mode; each run executes only its own shape's code and no rebuild thrash occurs. Governing statement: [query.compiled.integrity](../ontology/features/cypher.g5.md#query.compiled.integrity).

<a id="RC-01"></a>
### Graph scope is added by hand to each statement

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_f0106_keys_join_on_id` (as built)](results/playbook-proofs-d1e/20261115T035515Z-control_f0106_keys_join_on_id/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (6 such controls rerun here); the rest is prose only

- Burden today: Graph isolation is a column or first subscript that every query, join, walk, procedure and writer must add for itself; there is no graph-scoped access layer. Readers and writers that omit the predicate (all-graphs walks, joins by id across graphs, schema procedures under USE GRAPH, the SQL adapter, sample servers, native readers, reifier deletion) answer with, or change, another graph's content.
- Findings that share it: 23 (highest S1): F-0106, F-0206, F-0616, F-0707, F-0711, F-0816, F-0818, F-0819, F-0820, F-1001, F-1002, F-1006, F-1008, F-1009, F-1013, F-1503, F-1507, F-1603, F-1604, F-1701, F-C1041, F-C1046, F-C1547.
- Rule it breaks: SYS-I2; SYS-D3/SYS-D4 (each datum belongs to one graph; a call that names no graph uses the default graph); CONTEXT.md:38-43 (an all-graphs read is the union of each graph's own answer).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Route every read and write through one graph-scoped access layer whose statements always bind graph_id (default '') and join on (graph_id, id); refuse unscoped calls; give every reader's tests a two-graph fixture with one id held by both graphs.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-02"></a>
### Stored facts whose key omits the graph

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1d `control_f0705_absent_graph_is_default` (as built)](results/playbook-proofs-d1d/20261115T035644Z-control_f0705_absent_graph_is_default/receipt.json) → [reviewed design](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (1 such controls rerun here); the rest is prose only

- Burden today: Several stores key a fact without its graph: ledger node records (genesis and LedgerApply record nodes graph-blind), reifier nodes (always the default graph), BM25 and IVF indexes with no recorded graph, edge vectors in a snapshot. Ownership checks built on them (redaction's targets, liveness, verify(), node-delete existence, index use under a graph) cannot attribute the fact, so they attribute it to the default graph or to every graph.
- Findings that share it: 8 (highest S1): F-0609, F-0705, F-1105, F-1304, F-1305, F-1401, F-1502, F-1803.
- Rule it breaks: SYS-I2; SYS-D3 (each piece of data belongs to one graph); ADR-0013/plan.md:9-10 (node records are graph-blind by design).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Make the graph part of every stored key: record each node record's graph, create reifiers in the edge's graph, record the graph of every derived index and archive row; treat an absent graph as unknown (refuse or report incomplete), never as the default graph.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-03"></a>
### Removal reach is not derived from a declared store inventory

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1b `control_f0606_erase_keeps_ivf` (as built)](results/playbook-proofs-d1b/20261115T035745Z-control_f0606_erase_keeps_ivf/receipt.json) → [reviewed design](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (5 such controls rerun here); the rest is prose only

- Burden today: Erasure, redaction's liveness and reach, snapshot export and the redaction receipt each list by hand the stores and fields they cover. Stores and fields outside those lists keep an erased or redacted tenant's content and the receipt does not name them: IVF/tree/PLAID and BM25 indexes, temporal-only edges, routed vectors, embedding_quarantine, legacy Graph_KG ledger rows after an upgrade, IVG's own snapshot archives, the metadata of a revision that recorded nothing, and the audit's target digest.
- Findings that share it: 12 (highest S1): F-0606, F-0618, F-0702, F-C1203, F-C1304, F-C1305, F-C1306, F-C1308, F-C1309, F-C1548, F-C1804, F-CS01.
- Rule it breaks: SYS-I4; SYS-D26 (erasure removes content from every store); ADR-0004; spec 256 US1/SC-001 and FR-008 (the receipt names what it does not reach).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Declare one store inventory (each store and field with its owning graph/tenant key and its erase, redact, export and liveness hooks) and generate erasure, LiveRows/Matches, the snapshot plan and the receipt's out_of_reach list from it; check mechanically that every writer's target store is in the inventory.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-04"></a>
### Erase, ledger commits and redaction start are not serialized on the ledger head lock

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d9c `control_f1201_erase_unlocked` (as built)](results/playbook-proofs-d9c/20261115T040828Z-control_f1201_erase_unlocked/receipt.json) → [reviewed design](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (5 such controls rerun here); the rest is prose only

- Burden today: The eraser deletes rows and kills statement-map entries without ^IVG.Ledger("head"); redaction reads its 'another run?' check and its liveness check unlocked and READ UNCOMMITTED and sets its marker only with the first tombstone; adoption and the first enable read the state they decide on before taking the lock. Each is a check-then-act on ledger-owned facts that a concurrent commit, erasure, rollback or second run invalidates.
- Findings that share it: 10 (highest S1): F-1103, F-1104, F-1114, F-1201, F-1302, F-1303, F-C1201, F-C1202, F-C1301, F-C1302.
- Rule it breaks: SYS-I1, SYS-I3; LED-B4.14.4 (only the head-lock holder changes the statement maps); RED-B1.1 (never tombstone live content); premises P-1311, P-C01, P-A3 (false at the pin).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Serialize erase, ledger commits, adoption, enable and redaction start on the head lock (HD-1201 and HD-1301 working answers): take the lock before reading what a step decides on, check liveness against committed state and set the per-target marker in the same locked step, run the eraser's row deletes and statement cleanup under the same lock, and let Final act only when its scan reached the head it holds.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-07"></a>
### Multi-call readers have no consistency protocol

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d9c `control_f1402_reader_no_recheck` (as built)](results/playbook-proofs-d9c/20261115T040858Z-control_f1402_reader_no_recheck/receipt.json) → [reviewed design](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (2 such controls rerun here); the rest is prose only

- Burden today: Readers that span several calls check the redaction marker once before reading, and save_snapshot reads every store READ UNCOMMITTED with no epoch, so a reader can return a partially redacted view and an archive can hold writes that never commit.
- Findings that share it: 2 (highest S1): F-1402, F-C1801.
- Rule it breaks: SYS-I8; HD-1401 (a reader returns a consistent view or the documented in-progress result); HD-1802 (a consistent snapshot needs quiet writers or an epoch); IRIS contract E-VIS.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Validate every multi-call read against an epoch (bumped by each redaction batch and Final and by writers) after the read and retry or refuse on change; for exports, an export gate that writers respect or a refusal while transactions are open.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-08"></a>
### The ledger is not the single writer of governed content

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1c `control_f0303_direct_delete_keeps_stmt` (as built)](results/playbook-proofs-d1c/20261115T035830Z-control_f0303_direct_delete_keeps_stmt/receipt.json) → [reviewed design](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (9 such controls rerun here); the rest is prose only

- Burden today: Ledger-governed content has many writers besides the ledger (bulk loader, purges and row drops, direct edge deletes, GraphQL mutations, bulk_delete_adjacency, temporal writes, server writers, raw SQL), and strict mode is a per-engine cached client check (5 s TTL, fail-open). So writes reach governed content unrecorded, leave live statement entries for removed rows, and are not refused by a redaction's marker.
- Findings that share it: 10 (highest S1): F-0301, F-0302, F-0303, F-0503, F-0504, F-0801, F-1108, F-C1150, F-C1307, F-C1350.
- Rule it breaks: SYS-I1, SYS-I7; spec 213 FR-047; premises P-C02 and P-L6 (false at the pin); HD-1103 (strict mode is client-side).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Enforce ownership in the server: one write gate (Txn_Begin or the content tables' row hooks) that every content writer passes, which refuses ungoverned writes under strict mode and writes into a marked target, decided per write and fail-closed; the writer census becomes its test list.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-09"></a>
### Retries re-execute effects the idempotency record does not cover

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d9c `control_f1306_replay_direct_sql` (as built)](results/playbook-proofs-d9c/20261115T040845Z-control_f1306_replay_direct_sql/receipt.json) → [reviewed design](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (1 such controls rerun here); the rest is prose only

- Burden today: Idempotency covers only the revision: post-commit properties are a separate write that a replay applies again, a replay rebuilds its answer without statement ids, and the HTTP client and the Cypher server resend a write after an ambiguous outcome. A retry can therefore save twice or revive erased content.
- Findings that share it: 5 (highest S1): F-1101, F-1106, F-1306, F-C1604, F-C1703.
- Rule it breaks: SYS-I6; spec 213 ledger-api.md:26 (a replay returns the original outcome); HD-1305, HD-1603, HD-1702.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Put the whole effect under the idempotency record (post-commit properties recorded with the revision and skipped on replay; the stored first answer returned) and retry only reads or writes known not to have started; answer 'outcome unknown' otherwise.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-11"></a>
### IVG ObjectScript writers roll back their caller's transaction

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1d `control_fc0702_bare_trollback` (as built)](results/playbook-proofs-d1d/20261115T035637Z-control_fc0702_bare_trollback/receipt.json) → [reviewed design](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (1 such controls rerun here); the rest is prose only

- Burden today: Some ObjectScript writers (adjacency sync/rebuild, BM25 Insert/Delete) handle a failure with TROLLBACK, which ends every level, instead of the nesting discipline the Python path follows; a failing IVG call inside a caller's transaction discards the caller's own work.
- Findings that share it: 2 (highest S1): F-0409, F-C0702.
- Rule it breaks: SYS-I3; CHANGELOG 4.6.4 and _write_txn.py:1-30 (an IVG write nested in a caller's transaction undoes only its own level); IRIS contract E-PARTIAL.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One Txn helper for every ObjectScript writer that rolls back only the level it opened (TROLLBACK 1, and only when it started one); a nested-failure test per writer.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-16"></a>
### The Cypher and AQL translators have no reference semantics

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1d `control_f0802_shortcut_unscoped` (as built)](results/playbook-proofs-d1d/20261115T035657Z-control_f0802_shortcut_unscoped/receipt.json) → [reviewed design](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (4 such controls rerun here); the rest is prose only

- Burden today: The translators rewrite each clause shape into SQL locally, with no reference evaluator to compare against; shapes outside the tested ones (literal-endpoint CREATE, FOREACH over a parameter, MERGE ON SET shapes, UNWIND..WITH, empty aggregates, null SET, '//' in strings, inline relationship properties, per-row MERGE SET, shortcut texts matched by substring) give wrong answers or errors.
- Findings that share it: 13 (highest S1): F-0802, F-0805, F-0808, F-0809, F-0810, F-0822, F-0823, F-0824, F-C0101, F-C0803, F-C0841, F-C0848, F-C0849.
- Rule it breaks: none of SYS-I1..SYS-I10; openCypher semantics and the TCK (docs/dev/TCK.md); CYP-B6.x; KNOWN_ISSUES.md.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Drive the translators from a reference semantics: the typed openCypher TCK at the pin on every supported engine, a differential oracle per clause shape against a reference evaluator, and a refusal for every shape outside the covered set.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-19"></a>
### Query text is built by pasting values

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: The AQL translator pastes literals into Cypher text and a dotted function name is pasted into SQL, so caller text rewrites the query (and execute_aql has no read-only switch).
- Findings that share it: 3 (highest S1): F-0814, F-0815, F-C0341.
- Rule it breaks: none of SYS-I1..SYS-I10; CYP-I9.4 (a name in a query reaches SQL only as a bound value or a checked name); CYP-I8.6 (read-only changes nothing).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Bind every literal as a parameter, validate identifiers against a grammar or an allow-list, and apply read_only at every query entry including execute_aql.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-20"></a>
### No server-side authorization or exposure boundary

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1d `control_f0908_run_unchecked` (as built)](results/playbook-proofs-d1d/20261115T035706Z-control_f0908_run_unchecked/receipt.json) → [reviewed design](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (1 such controls rerun here); the rest is prose only

- Burden today: Protection rests on documentation, client flags or the start-up path: file and global helpers are callable by a reading role, ImportGlobals skips the allow-list, Bolt binds every interface unless started by the CLI, the CLI binds 0.0.0.0 with no key, demo write routes need no key, the executor checks no privilege, the installer creates no least-privilege user.
- Findings that share it: 7 (highest S1): F-0908, F-1614, F-1709, F-1806, F-C1603, F-C1741, F-C1803.
- Rule it breaks: none of SYS-I1..SYS-I10; no SYS-I axiom covers it (an ontology gap); HD-1601 (the namespace is the authorization boundary); ADMIN_GUIDE.md:450-473 (least-privilege reading role); deploy/README.md:86.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Decide the boundary (HD-1601) and enforce it in the server: no file or global helpers reachable by reading roles, loopback default bind and a refusal of unauthenticated external binds in the app itself, the key middleware on every server, a privilege check in the executor (or a documented resource boundary), an installer that creates the least-privilege user.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-22"></a>
### Derived-row marks are ordinary qualifier keys with no single predicate

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1c `control_f0304_store_no_adopt` (as built)](results/playbook-proofs-d1c/20261115T035820Z-control_f0304_store_no_adopt/receipt.json) → [reviewed design](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (4 such controls rerun here); the rest is prose only

- Burden today: Whether an edge row is derived (temporal-backed, or inferred) is recorded as an ordinary qualifier key that any caller, the ledger included, can also write ('temporal', 'inferred'), and is tested by different predicates in the deleters, the ledger and the Python mirror; the adopt/retract step runs on some writers only (store_edge does not adopt; Purge leaves marked rows; create_edge adopts after its commit). Governed and explicit rows are therefore deleted as derived ones, and derived rows surv…
- Findings that share it: 8 (highest S1): F-0304, F-0505, F-0506, F-0507, F-C0151, F-C0301, F-C0351, F-C0450.
- Rule it breaks: none of SYS-I1..SYS-I10; ADR-0009 and its amendment; HD-0302; ADR-0015; schema.py:3187 (retract_inference deletes only what materialize_inference wrote).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One shared mark that no caller can write (a reserved key refused by every writer and the ledger, or a column), one predicate, and one adopt/retract step called by every writer and deleter inside its own transaction.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-25"></a>
### Restore writes stores directly instead of through their owners

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1b `control_f1801_no_prefix_check` (as built)](results/playbook-proofs-d1b/20261115T035736Z-control_f1801_no_prefix_check/receipt.json) → [reviewed design](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (2 such controls rerun here); the rest is prose only

- Burden today: save_snapshot/restore_snapshot copy rows and globals wholesale: a replacing restore lays an archive's ledger over the live one, a merge guards plain tables on their first column only and overwrites temporal aggregates, and the adjacency index is written outside its one writer. The stores' own invariants are not maintained.
- Findings that share it: 5 (highest S1): F-0404, F-1801, F-1802, F-1805, F-C1850.
- Rule it breaks: SYS-I1, SYS-I5; spec 213 FR-043 (the ledger survives a snapshot); ADR-0011 (one adjacency writer); SNP-B4.x (merge by the row's own key).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Restore through the owners: refuse an archive whose ledger history does not extend the live one before any mutation, rebuild derived stores (adjacency, aggregates) from restored rows, and guard each merged table on its primary or unique key.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-35"></a>
### Bulk loads bypass the indexes and key checks every other path relies on

Severity: High · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: BulkLoader writes with INSERT %NOINDEX %NOCHECK by default: the rows it writes are in no index and pass no unique check until the indexes are rebuilt. Readers, the liveness check, erasure and the key invariants all read through those indexes, so duplicate keys are stored, a mode-off graph holds parallel rows, erasure leaves the loaded edge, and redaction completes while the tenant's loaded rows exist.
- Findings that share it: 4 (highest S1): F-C0349, F-C0350, F-C1250, F-C1351.
- Rule it breaks: SYS-I8, SYS-I1; schema.py:34-44, 396-419 (unique keys); GID-I4.10; spec 256 FR-005 (refuse while any row of the target is live); ADR-0004.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Make the bulk loader leave the indexes current before it returns (rebuild inside the load, or no %NOINDEX on key-carrying tables) and drop %NOCHECK for unique keys; until then refuse erasure and redaction while an index build is pending.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="simp-002"></a>
### Put a relationship's endpoints in every relationship record so redaction never has to look them up

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/ledger_redaction/20261114T044401Z-prove/receipt.json) → none

Scope qualification: the as-built side is `witness_unattributed_qualifier_survives` and `lemma_complete_run_removes_every_target_record` (which needs premise P_ends); no proposal model was run.

What is complicated now: qualifier records (`set_qual`, `remove_qual`) carry only a statement id. `LedgerRedact.Matches` reconstructs the endpoints from a pre-pass over create/delete records (process-private `^||IVG.RedactStmt`), the live statement map, and the statements tombstoned by the run (`("redacting","stmt")`). When none of these knows the statement — a statement assigned to an edge written outside the ledger and erased since — the record is left in place and counted as `unattributed_records`.

Proposal: when the ledger assigns a statement (`assigned_stmt`) or writes any qualifier record, include the tuple (source, target, graph) in the record (or always write a `create_rel` record when a statement is first assigned). Matching then reads only the record itself; the pre-pass, the private global and the redacting-statement set can go.

Behavior to preserve: the canonical form and digest of every existing record (old records keep their layout; the reader must accept both); replay and diff results; the record count of a commit if the create-on-assign variant is chosen must be documented.

Distinguishing case: `redaction_unattributed_qualifier` — the qualifier record must become a tombstone and `unattributed_records` must be 0.

<a id="simp-003"></a>
### Derive redaction's liveness check from the eraser's store inventory

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/ledger_redaction/20261114T044401Z-prove/receipt.json) → [Proposed simplification](results/ledger_redaction/20261114T044401Z-prove/receipt.json)

Scope qualification: the as-built side is `lemma_checked_implies_content` with witnesses W2 (temporal-only) and W3 (whole default graph); the proposal side is `witness_full_check_refuses_the_gaps` under `full_check: true`, in the same model.

What is complicated now: `LedgerRedact.LiveRows` keeps its own list of four tables and its own graph-blindness rule (only with a prefix), separate from `Graph.KG.GraphStores`, the inventory the eraser derives its work from. The two lists already disagree: the temporal index and a whole-default-graph target's named-graph node rows are content to the eraser but not to the liveness check.

Proposal: answer "is the target live?" from the same inventory the eraser uses, with one graph-blindness rule for every default-graph target (prefix or not), as spec 256 plan.md states.

Behavior to preserve: the separator boundary (`acme` is not blocked by live `acme-health|` rows); the refusal message naming the stores that are live; a target whose content was erased is not refused.

Precondition (review round 3 R3-3): the last property holds only once the prefix erase itself reaches every store the full check reads. Under the as-built `EraseNodes`, which selects IDs from node rows, a full check would refuse every prefix redaction of a tenant with temporal-only events whose endpoints have no node row ([bug-led-007](bugs_issues.md#bug-led-007)) or with property rows that have no node row ([bug-led-010](bugs_issues.md#bug-led-010)), until those are erased by ID. So this simplification depends on bug-led-007's erase repair (and bug-led-010's). Distinguishing cases a repair must pass: [erasure_prefix_temporal_only](receipts/native/erasure_prefix_temporal_only.json) (after the prefix erase, no event of the tenant is readable and the redaction completes) and [redaction_orphan_prop_blocks](receipts/native/redaction_orphan_prop_blocks.json) (after the prefix erase, the redaction completes without an explicit-id erase); in the model, W5 `witness_prefix_erase_leaves_temporal_only_content` and W6 `witness_orphan_prop_row_blocks_prefix_redaction` must stop holding.

Distinguishing cases: `redaction_temporal_only_live` and `redaction_default_graph_whole` must both be refused with `target_live`, and `test_live_acme_health_nodes_do_not_block_redacting_acme` must still pass.

<a id="simp-str-001"></a>
### Delete a relationship through one Eraser path, whatever the caller

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model run compares the as-built deletes with the proposal.

What is complicated now: four paths delete a relationship row: `delete_edge` (`nodes_edges.py:1382-1456`), Cypher `DELETE r` (`translator.py:10699-10712`), ledger `DeleteRelInternal` (`LedgerApply.cls:652-693`) and `Eraser.EraseEdgeRow` (`Eraser.cls:641-677`). Each removes a different set of satellites (reifications, edge embeddings, ledger tuple and statement entries, adjacency), and the ledger path adds its own adjacency call that breaks multigraph triples ([bug-str-001](bugs_issues.md#bug-str-001), [bug-str-013](bugs_issues.md#bug-str-013)).

Proposal: route `delete_edge`, Cypher relationship `DELETE` and the ledger's relationship delete through `Eraser.EraseEdgeRow` (by edge ID), so the satellites and the adjacency move in one transaction by one rule.

Behavior to preserve: `delete_edge`'s return value and graph scoping; the ledger's record of the delete in the same transaction; Cypher's per-graph correlation of the deleted rows; nesting in a caller's transaction.

Distinguishing case: delete one of two parallel edges that has a reification and an edge embedding through each path; afterwards the survivor keeps its adjacency, and the deleted edge's reification, vector and live statement are gone in every case. Governing statement: [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path).

<a id="simp-srch-001"></a>
### One fusion function with an explicit absent-rank rule and per-leg failure reporting

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model run covers fusion.

What is complicated now: four RRF implementations rank the same inputs differently: the engine (`vector.py:1444-1446`, absent rank from the leg's length), the SQL procedure (`schema.py:2536-2537`, 1e9), `ivg.retrieve` (`translator.py:3342-3352`, 0) and `fusion.py:56-58` (0); one `try` turns a failed leg into an empty answer ([bug-srch-005](bugs_issues.md#bug-srch-005), [bug-srch-010](bugs_issues.md#bug-srch-010)).

Proposal: one function, called by the engine, the operators and `fusion.py`, with an absent item contributing 0 (or one documented constant) and a failed leg raised or reported by name; the SQL procedure and `ivg.retrieve` document the same rule.

Behavior to preserve: per-graph scoping of each leg; the empty-text skip; the default `c`.

Distinguishing case: A at vector rank 1 only and B at rank 50 in both legs of 200 (c=60): B must rank first on every entry point. Open part: [search.fusion.absent](../ontology/features/search.g5.md#search.fusion.absent). Governing statement: [search.fusion](../ontology/features/search.g5.md#search.fusion).

<a id="simp-plt-001"></a>
### Enforce strict ledger mode once, on the server, instead of in each Python engine

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/platform/20261114T002651Z-prove/receipt.json) → none

Scope qualification: the as-built side is `witness_ttl_window_admits_a_write_after_set_strict`, `witness_failed_probe_admits_a_write`, `witness_undocumented_bypasses_break_the_contract` and `witness_class_absent_cached_for_the_engines_lifetime` in [platform.rs](models/platform/platform.rs); controls `g-ttl-zero` and `g-fail-closed` show the first two depend on the cache and the fail-open path. No server-side gate variant was run.

What is complicated now: the strict check exists only in Python, as a per-engine probe cached for 5 s that fails open (`ledger/guard.py:20, 38-59`), called method by method; no ObjectScript writer reads `^IVG.Ledger("meta","strict")`. Paths without the call bypass it (`bulk_delete_adjacency` and the sample API's raw cursor, undocumented; FHIR sync and the MCP Cypher tool, undecided), an engine that first checked before the ledger classes existed never enforces it ([bug-plt-025](bugs_issues.md#bug-plt-025)), and another engine can write for up to 5 s after `set_strict(True)` ([bug-plt-005](bugs_issues.md#bug-plt-005), [bug-plt-006](bugs_issues.md#bug-plt-006), [q-plt-001](open_questions.md#q-plt-001)).

Proposal: read the strict flag in the ObjectScript writers' shared entry (or in the Eraser and the adjacency writers), so every path that changes structure checks it at write time.

Behavior to preserve: the documented exemptions (BulkLoader, raw SQL, the marked temporal row), the rejection counter, the ledger's own writes, and the error type `LedgerStrictModeError` at the Python surface.

Distinguishing cases: the TTL window (a second engine's `create_node` 1 ms after `set_strict(True)`), `bulk_delete_adjacency` and FHIR sync under strict. Governing statement: [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict).

<a id="simp-cyp-002"></a>
### Carry each node binding's graph through Cypher translation instead of correlating graphs by regex afterwards

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model run covers the translator.

What is complicated now: the all-graphs rule is added after translation by regular expressions over join and sub-SELECT text (`translator.py:564-1035`); it took surface-by-surface fixes from 2026-10-20 to 2026-11-10 (`56de32f5`, R157, R158, R192, R226/R260 `c3a05900`, R308 `ecc07c57`, R310, R319, `b1af594e`, 4.7.0 row 11, the 4.6.1/4.6.2 shortestPath fixes), and correlation is skipped from a one-table probe ([bug-cyp-005](bugs_issues.md#bug-cyp-005)).

Proposal: make a node binding `(alias, graph_expr)` from the start; emit every join and sub-SELECT with the graph equality; treat `USE GRAPH` as binding `graph_expr` to a literal.

Behavior to preserve: the plans IRIS gets when only one graph exists (`translator.py:783-785`), the LEFT JOIN null-row placement (`:730-733`), and every row of the e2e write matrix.

Distinguishing case: a pattern comprehension or `EXISTS {}` over a node ID shared by two graphs, a spelling the regexes may miss. Governing statement: [query.graph-scope.read](../ontology/features/cypher.g5.md#query.graph-scope.read).

<a id="RC-05"></a>
### Unlocked read-modify-write of shared facts outside the ledger

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_f0207_set_off_unlocked` (as built)](results/playbook-proofs-d1e/20261115T035520Z-control_f0207_set_off_unlocked/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (5 such controls rerun here); the rest is prose only

- Burden today: Outside the ledger, writers of shared facts read, decide and write with no lock, or under a lock mode that excludes nothing: multigraph mode off vs a parallel-edge write, BM25 Build/Drop, adjacency rebuilds (shared ^IVG.AdjW), native-plan DropAll vs Build, embed-queue claims, ledger_stats counters (%OpenId/%Save), snapshot file names.
- Findings that share it: 10 (highest S2): F-0207, F-0701, F-0905, F-1102, F-1807, F-C0348, F-C0402, F-C0601, F-C0670, F-C1101.
- Rule it breaks: SYS-I1; playbook §1 principle 3 (concurrency control lives in the database; lock plans are proved per handler).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Give every handler a lock plan: each read-modify-write of a shared fact holds the owner's exclusive lock across the read and the write, or uses an atomic primitive ($Increment, unique names, a version-checked write); one two-process interleaving test per handler.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-06"></a>
### Derived stores and caches have no reliable staleness signal

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_f0208_mode_cached_forever` (as built)](results/playbook-proofs-d1e/20261115T035518Z-control_f0208_mode_cached_forever/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (5 such controls rerun here); the rest is prose only

- Burden today: Caches and rebuilt stores (degree cache, algorithm cache, BM25 indexes, the interned snapshot ^NKG, temporal bucket aggregates, an engine's multigraph-mode cache) are kept current by a token or generation that is stepped after the write, killed and restarted, not stepped on every path (weights, node-only writes, temporal writes), survives a rollback ($Increment), or is not consulted at all, so a derived answer stays 'current' after its source changed or rolled back.
- Findings that share it: 11 (highest S2): F-0208, F-0401, F-0402, F-0405, F-0406, F-0501, F-0703, F-1004, F-1005, F-C0401, F-C0801.
- Rule it breaks: SYS-I8; CONTEXT.md:109-120 (graph-version token); ADR-0012; AlgoCache.cls:5-7 ('never wrongly fresh').
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One staleness mechanism for every derived store: a monotonic per-graph epoch stepped before every source write on every path and never killed, recorded at build and compared at read; mark the derived store stale on rollback, or store a computed answer only when the writer lock was free and the epoch did not move.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-10"></a>
### A command's writes are not one validated, all-or-nothing unit

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1c `control_f0305_chunks_commit_alone` (as built)](results/playbook-proofs-d1c/20261115T035832Z-control_f0305_chunks_commit_alone/receipt.json) → [reviewed design](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (3 such controls rerun here); the rest is prose only

- Burden today: Multi-step and multi-store commands run in several transactions or autocommit statements (bulk loader chunks, the FHIR event route, the Neo4j commit route, FHIR Register and Schedule, reifier cleanup, temporal-index writes), and some refusals are detected after the first write (index-handle build, store_embeddings routes, a refused temporal write), so a failure or refusal leaves part of the command applied.
- Findings that share it: 12 (highest S2): F-0305, F-0615, F-0704, F-1511, F-1609, F-1610, F-C0330, F-C0415, F-C0501, F-C0748, F-C1501, F-C1502.
- Rule it breaks: SYS-I3, SYS-I4; USER_GUIDE.md:238-241 (each bulk write is a transaction); Neo4j commit-route and Bolt transaction semantics (P-1612).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One write-transaction wrapper used by every entry point: validate the whole request first, then perform every write of the command in one transaction (nesting with TROLLBACK 1), never committing inside it; a failure test per entry that asserts no store changed.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-12"></a>
### Environment premises are asserted, not validated

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_fc1001_read_creates_routines` (as built)](results/playbook-proofs-d1e/20261115T035523Z-control_fc1001_read_creates_routines/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (1 such controls rerun here); the rest is prose only

- Burden today: The product relies on engine, edition, driver and optional-library behaviour it neither probes at run time nor tests on the configurations it supports: SQL COMMIT/ROLLBACK ending every level (true only as 'measured on 2026.3'), durability of an acknowledged commit with SynchCommit=0, the uv.lock driver 5.3.2 (Decimal scores, <LIST ERROR> duplicate reports, closed cursors), VECTOR_L2 on Community, %AI classes in the test deploy, rdflib's API, the Arno library's presence and build, IRIS's default…
- Findings that share it: 12 (highest S2): F-1012, F-1504, F-C0502, F-C0615, F-C1001, F-C1102, F-C1110, F-C1704, F-C1705, F-C1706, F-C1716, F-C1743.
- Rule it breaks: none of SYS-I1..SYS-I10; playbook §1 principle 2 (model the environment's freedom; state each narrower premise and test it); SYS-P1..SYS-P4 are stated premises.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): An executable environment contract for every supported (engine, edition, driver, optional library) cell, run in CI, plus run-time capability probes that refuse with a named reason instead of assuming; a driver floor in pyproject.toml with a refreshed uv.lock.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-13"></a>
### The IVG Schema name is not resolved from one source

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_f0103_marker_admits` (as built)](results/playbook-proofs-d1e/20261115T035505Z-control_f0103_marker_admits/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (2 such controls rerun here); the rest is prose only

- Burden today: The namespace's schema record is the intended single source of the IVG Schema name, but legacy SQL files, the 4.0.0 upgrade, the bulk loader's index rebuild, setup's DROP INDEX and the sample API hard-code Graph_KG or unqualified names, and the first-use check accepts a namespace with no record.
- Findings that share it: 7 (highest S2): F-0103, F-0105, F-0107, F-0109, F-0309, F-1605, F-C0690.
- Rule it breaks: SYS-I10; ADR-0016 (the schema chosen at install is followed by everything); spec 262 FR-001/FR-006a/FR-007.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Derive every SQL name through one qualifier from the deploy record (engine._ivg_schema); refuse a namespace with no record; retire or regenerate the legacy SQL files; run the suites on a non-default-schema namespace.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-14"></a>
### Failures are swallowed into empty, default or success answers

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_f0101_removed_unchecked` (as built)](results/playbook-proofs-d1e/20261115T035511Z-control_f0101_removed_unchecked/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (4 such controls rerun here); the rest is prose only

- Burden today: Handlers catch failures and answer as if nothing happened: [] for a failed read, False ('exists') for a refused write, DONE for a failed embedding, success with failed rows, 'healthy' with no database, zero vectors for a failed lookup, a fused search without its failed leg, a restore that drops a line it cannot write. The outcome is not computed from the operation's result.
- Findings that share it: 18 (highest S2): F-0101, F-0102, F-0209, F-0306, F-0307, F-0511, F-0604, F-0614, F-0709, F-1508, F-1509, F-1611, F-1615, F-C0940, F-C1640, F-C1750, F-C1795, F-C1802.
- Rule it breaks: SYS-I9; CHANGELOG 4.6.0 rule 'a failed read raises'; 4.7.0 row 14 (every bulk writer raises for a refused row); 4.6.0 R265 (no silent empty answer).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Enforce the 4.6.0 rule mechanically: no handler returns an empty/default answer from an except clause; every outcome (removed, DONE, restored counts, health, legs used) is computed from the operation's own result; a lint over except clauses plus a fault-injection test per reader.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-17"></a>
### Stored values carry no type

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Property and qualifier values are stored as JSON text or native subscripts with no type tag and no single serializer, so numbers and strings compare as each other, floats come back as integers, NaN is stored as JSON no reader accepts, canonical label forms are not JSON, native index values return as text, and a filter matches stored JSON text.
- Findings that share it: 7 (highest S2): F-0308, F-0509, F-0811, F-0812, F-0813, F-1113, F-1804.
- Rule it breaks: none of SYS-I1..SYS-I10; playbook §1 principle 7 (typed ids and values); spec 255 (a value comes back with the type it was written with); spec 204 FR-012.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): A typed value encoding shared by every writer and reader (the planned typed storage), one JSON serializer (allow_nan=False) for qualifiers and label sets, and the TCK typed runs on mixed data.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-18"></a>
### Domain codes, units and metrics are untyped

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Kinds, modes, time units, metric names and fusion weights are raw strings or numbers: any revision kind is accepted, any compile-mode value acts as sync, 'now' is computed in seconds for a millisecond index, a missing time becomes 0, 'cosine' is an unnormalised dot product, an L2 distance is ranked as a similarity, default weights go to legs by position.
- Findings that share it: 7 (highest S2): F-0502, F-0510, F-0607, F-0710, F-0903, F-1107, F-1705.
- Rule it breaks: none of SYS-I1..SYS-I10; playbook §1 principle 7 (enums, not codes; typed values); NAT-X12; LED-B4.9.2.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Enums for kinds and modes that refuse unknown values, a unit carried by each temporal index, metric objects that carry normalisation and sort direction, weights keyed by leg kind; one unit test per value of each enum.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-21"></a>
### Edge identity for parallel edges is not one rule

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_f0201_ekey0_guard` (as built)](results/playbook-proofs-d1e/20261115T035517Z-control_f0201_ekey0_guard/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (1 such controls rerun here); the rest is prose only

- Burden today: Multigraph support (spec 234) was implemented on some paths only: single-edge writers guard the triple only when ekey is 0, verify_graph and the graph check compare rows to keyed counts per triple wrongly, Bolt and the ledger identify an edge by its triple, in-degree collapses parallel edges that out-degree counts.
- Findings that share it: 6 (highest S2): F-0201, F-0204, F-0205, F-0403, F-1007, F-1712.
- Rule it breaks: none of SYS-I1..SYS-I10; spec 234 FR-002/FR-007/FR-012/FR-013, SC-005; CONTEXT.md:103-108 (parallel edges each count).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One edge identity (s, p, o, ekey) used by rows, adjacency counts, the ledger, Bolt ids, degree and verify, with spec 234's ambiguous-tuple refusal where only a triple is given; a multigraph fixture in each reader's tests.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-23"></a>
### Results depend on storage order or join multiplicity

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Result prefixes (TOP n) without a total ORDER BY, TOP 1 over several qualifying rows, statement-id allocation in scan order, schema procedures sampling one element, tie handling in shadow mode, and label joins that repeat a node make answers a function of storage order or join shape.
- Findings that share it: 11 (highest S2): F-0907, F-C0302, F-C0602, F-C0603, F-C0604, F-C0642, F-C0703, F-C0802, F-C1108, F-C1642, F-C1742.
- Rule it breaks: none of SYS-I1..SYS-I10; playbook §1 principle 5 (never depend on storage or insertion order, only on keys and explicit orderings); gate 3.4-storage-order.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Order every result prefix and every allocation by a total key, use EXISTS for filters, and close the storage-order scan's candidate list (order or document each).
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-24"></a>
### Identity by a non-injective checksum

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1d `control_f0901_shared_class_name` (as built)](results/playbook-proofs-d1d/20261115T035702Z-control_f0901_shared_class_name/receipt.json) → [reviewed design](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (3 such controls rerun here); the rest is prose only

- Burden today: Compiled plan classes and the interpreter's used-relationship set are keyed by a 32-bit $ZCRC, so two shapes share one class and two relationships count as one; a build then marks whatever entry the hash holds.
- Findings that share it: 3 (highest S2): F-0901, F-0902, F-C0901.
- Rule it breaks: none of SYS-I1..SYS-I10; ADR-0014:19 (a compiled class answers exactly as the interpreter does); NAT-B1.11; NAT-I3.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Key plans and relationships by an exact key or a collision-resistant digest (the SHA-256 already computed), and keep the shape check under the entry's lock.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-26"></a>
### Vector identity is enforced per seam and fails open

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Each vector-writing seam (engine writes, Python embedder fallback, the IRIS queue worker, VectorOptimizer, enqueue, upgrade placement, kg_KNN_VEC's route guard) implements its own identity and route check, some none, and a failed registry read turns the check off.
- Findings that share it: 7 (highest S2): F-0601, F-0602, F-0603, F-0605, F-0610, F-0611, F-0613.
- Rule it breaks: none of SYS-I1..SYS-I10; ADR-0006 (every seam that writes vectors consults the registry); spec 226 FR-014 (enforcement is not opt-in); spec 227.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One vector-write gate in the server that every seam calls: it resolves the (graph, model, kind) route, compares identity and width, and fails closed when the registry cannot be read.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-27"></a>
### Input validation is per entry point, not at the shared write boundary

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1e `control_f0202_writer_skips_name_check` (as built)](results/playbook-proofs-d1e/20261115T035512Z-control_f0202_writer_skips_name_check/receipt.json) → [reviewed design](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (2 such controls rerun here); the rest is prose only

- Burden today: Each entry point validates its own input, so graph names, timestamps and weights, vector widths and duplicates, the reserved stopword name and the wire schema's length limits are checked on some paths and not others.
- Findings that share it: 8 (highest S2): F-0202, F-0203, F-0513, F-0608, F-0706, F-C0150, F-C0701, F-C1107.
- Rule it breaks: SYS-I3; ADR-0003:119-121 (the validator rejects '0'); CHANGELOG.md:4618-4620 (the Python mirror refuses what the server refuses); changeset.schema.json limits.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One validator per input kind at the shared write boundary (the server), the Python mirror generated from it, and a refusal with a validation code before the transaction starts.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-28"></a>
### Resource bounds are not declared

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Limits exist but are neither declared nor checked at the boundary: a combined key length for (s, p, o, graph), the subscript limit for a prefix, a ~35k-edge window cap under a migration, Python memory for an export claimed bounded, a Bolt session's IRIS connection, a latency budget.
- Findings that share it: 10 (highest S2): F-0514, F-1510, F-C0347, F-C0606, F-C0948, F-C1106, F-C1204, F-C1549, F-C1601, F-C1848.
- Rule it breaks: none of SYS-I1..SYS-I10; playbook §3.6 (capacity condition); SC budgets in specs 227 and 236.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Declare every bound (key lengths, prefix length, row caps, memory, connections, latency) in the contract, check it at the boundary with a named refusal, and test each at the limit.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-29"></a>
### Parallel implementations of one operation diverge

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: [playbook-proofs-d1d `control_f0906_gate_edge_index_only` (as built)](results/playbook-proofs-d1d/20261115T035710Z-control_f0906_gate_edge_index_only/receipt.json) → [reviewed design](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json) — a reviewed model that removes this burden for one member finding (2 such controls rerun here); the rest is prose only

- Burden today: One operation has several implementations (owner vs native PageRank, Arno vs fallback Leiden, the engine vs the sample API's Cypher entries, node vs edge/table vector search, the native gate vs the SQL path) with no differential test, and they answer differently.
- Findings that share it: 5 (highest S2): F-0612, F-0906, F-1003, F-1607, F-C1002.
- Rule it breaks: none of SYS-I1..SYS-I10; ALG-I1 (IVG answers the same without the library); ADR-0014:19; API-B5.8; spec 236 FR-014a.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One implementation per operation, or a differential test that runs every route on the same fixtures and compares answers.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-30"></a>
### Progress is not designed for resumable or queued work

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: A bounded redaction re-scans from the first record on every call, and the embed queue serves PENDING entries in node-id order, so repeated work need not finish.
- Findings that share it: 2 (highest S2): F-C0605, F-C1303.
- Rule it breaks: none of SYS-I1..SYS-I10; LedgerRedact.cls:178-180 (running the same target again resumes it); progress premises PF-1..PF-4; HD-0604.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Persist the scan cursor with the marker so a resume continues, serve queues in arrival order, and add a progress test (a bounded run finishes in finitely many calls).
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-32"></a>
### Test, packaging and deploy tooling diverges from the product

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: The product's own fixtures, installers and entry points are not exercised as shipped: the test deploy compiles every class (unlike setup), two e2e fixtures read a meta key that does not exist, the bolt-on installer and the docker recipe do not do what the README says, declared console scripts cannot run.
- Findings that share it: 6 (highest S2): F-0108, F-1112, F-1708, F-1710, F-C0090, F-C1701.
- Rule it breaks: none of SYS-I1..SYS-I10; docs/ADMIN_GUIDE.md:353 (Community is supported); deploy/README.md; pyproject.toml console scripts.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): CI that installs from the built package, runs the deploy recipes and console scripts on Community, and fixtures that call the product's own setup and read its real keys.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-33"></a>
### Stated refusals, options and protocol verbs are accepted and ignored

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Interfaces accept inputs whose documented meaning they do not implement, instead of refusing them: a WHERE after RETURN, an unknown procedure, an untranslatable expression (NULL), a burst predicate, Leiden's max_levels/tol, suppress_reverse, a route timeout and cache flag, Bolt BEGIN/COMMIT/ROLLBACK and PULL {n}, transaction verbs on the embedded cursor, IVG_STRICT_NAMESPACE, --workers N, FHIR pagination, ACORN first, the metrics hook for every outcome, the MCP query text.
- Findings that share it: 18 (highest S2): F-0508, F-0512, F-0803, F-0817, F-0825, F-1010, F-1111, F-1505, F-1601, F-1602, F-1606, F-1613, F-1702, F-1703, F-1706, F-C1641, F-C1702, F-C1715.
- Rule it breaks: SYS-I9; playbook §5 lesson 'a refusal written in the spec is not a refusal'; CYP-X3.8, CYP-X10.2, CYP-X12.x; Bolt protocol (P-1612).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Audit every documented refusal, parameter and protocol verb mechanically (a list generated from the docs and specs), implement it or refuse it with a named error, and test each.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-36"></a>
### Server answers are hand-encoded text decoded by patterns

Severity: Medium · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Several ObjectScript methods answer Python with hand-built text (comma lists, partly escaped JSON, shape-sniffed maps), and the Python side repairs or decodes it by text patterns: a leading-dot patch rewrites ids, comma splitting breaks names, an unescaped control character breaks the JSON, a node named 'components' is read as a summary.
- Findings that share it: 4 (highest S2): F-C0715, F-C0716, F-C0717, F-C1018.
- Rule it breaks: none of SYS-I1..SYS-I10; TXT-B2.13 (each id and score in the answer is valid JSON); RFC 8259 escaping (CHANGELOG.md:463-467); the decoders' own docstrings.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One wire encoding for every server answer (%DynamicObject / JSON arrays built by the library, never by concatenation) decoded by json.loads only, with no text repair; a round-trip test with hostile names and ids.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="simp-str-002"></a>
### Give the inverse of a graph key one owner in GraphKey

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the graph-key model proves the forward keys only.

What is complicated now: several sites turn an index key back into a SQL `graph_id` on their own (`Adjacency.cls:583, 627, 654, 698, 889`, `AssertTemporalRow`, `Retract*`, `OtherEdgeKeys`, Python `delete_edge`), an undeclared third derivation outside `GraphKey` that is right only while `ForIndex(g) = ForName(g)` for named graphs (ADR-0003); the ledger's redaction code spells record graphs with an inline `$Translate` too ([simp-led-001](#simp-led-001)).

Proposal: add `GraphKey.NameOf(indexKey)` (or pass names to those methods) and use it at every site.

Behavior to preserve: every SQL `COALESCE(graph_id,'')` predicate; default and named graph rows.

Distinguishing case: default- and named-graph rows deleted through each site. Governing statement: [graph.key.owner](../ontology/concepts/graph-scope.g5.md#graph.key.owner).

<a id="simp-str-003"></a>
### Bump the version token before ending a rebuild so the warm stamp survives it

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the warm stamp is not represented in the model.

What is complicated now: `BuildKG` bumps the token after `EndRebuild(1)` (`TraversalBuild.cls:142-145`), so the whole-graph warm stamp written during the rebuild is stale at once and the O(1) bulk readers fall back after every `sync()`, against ADR-0012 and `Adj.cls:180-183`.

Proposal: bump the token before `EndRebuild(1)`.

Behavior to preserve: the token still moves on every rebuild; readers during the rebuild still see it as not current.

Distinguishing case: `AllWarm(g) = 1` right after `BuildKG` with no writer. Governing statement: [structure.degree.cache.warm](../ontology/features/graph-structure.g5.md#structure.degree.cache.warm).

<a id="simp-tmp-001"></a>
### Remove the unadopted spec-246 Python path for temporal structural rows

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the Python legacy path is not represented in the temporal model.

What is complicated now: besides the server-side `AssertTemporalRow`/`RetractTemporalRow`, the engine keeps the `temporal_structural_rows` keyword, `_own_structural_row`, `_owned_structural_row`, `_triple_survives`, a flag branch of `delete_edge_temporal` and `migrations/temporal_structural_rows.py` (spec 246 "not adopted"); this path ignores the temporal-only registry ([bug-tmp-006](bugs_issues.md#bug-tmp-006)).

Proposal: remove the path, or make the migration delegate to `TemporalPolicy.BackfillRows`.

Behavior to preserve: an idempotent backfill with a read-only dry run.

Distinguishing case: flag on, predicate opted out, write: with the path removed no row appears. Governing statement: [temporal.structural](../ontology/features/temporal.g5.md#temporal.structural).

<a id="simp-srch-002"></a>
### Check embedding identity against the registry row the route lookup already read

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/search/20261114T000543Z-prove/receipt.json) → [Proposed simplification](results/search/20261114T000543Z-prove/receipt.json)

Scope qualification: both sides are `witness_identity_fail_open` in [search.rs](models/search/search.rs): its as-built branch (a cached route plus a failed identity read) admits the mismatched writer, and its fail-closed branch, the one raise-on-error policy proposed here, refuses it; control `repair-fail-closed-off` shows the refusal depends on the repair. Finite witnesses, not state counts.

What is complicated now: a write reads the registry twice, once in `_read_route` (raises on error, R161) and again in `get_embedding_identity` (swallows every error, `schema.py:1054-1056`), and the second read decides the identity check ([bug-srch-012](bugs_issues.md#bug-srch-012)); the queue's enqueue check reads a third, wrong table ([bug-srch-006](bugs_issues.md#bug-srch-006)).

Proposal: let `enforce_embedding_identity` use the row `_read_route` returned, with one raise-on-error policy, and give `enqueue_for_embedding` the same route-based check.

Behavior to preserve: refusal before anything is queued or written; "no registry" (SQLCODE -30) still passes as documented.

Distinguishing case: a cached route plus a failing identity read must refuse a mismatched mechanism. Governing statement: [search.embedding.check_on_write](../ontology/features/search.g5.md#search.embedding.check_on_write).

<a id="simp-plt-002"></a>
### Make the engine's Owner fallback uniform across algorithms

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model covers algorithm routing.

What is complicated now: for PageRank, WCC and CDLP the engine re-calls the same Owner after the store's Owner failed (`_engine/algorithms.py:797-804, 823-828, 845-849`), while PPR raises (R127); `Proof.from_dict`'s IN_SCOPE filter is dead code given the all-or-nothing validation (A-platform F-A8).

Proposal: raise after the store's Owner fails for every algorithm, and remove the dead filter.

Behavior to preserve: a native failure still yields the Owner's answer.

Distinguishing case: a store whose Owner raises: every algorithm raises once, with no second Owner call. Governing statement: [algorithms.routing.fallback](../ontology/features/algorithms.g5.md#algorithms.routing.fallback).

<a id="simp-plt-003"></a>
### Write FHIR graph labels through the adjacency writer that owns the label index

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — FHIR is not modelled.

What is complicated now: `FHIRGraph` sets `^KG("label")` directly in `EnsureNode`, `SyncProps` and `DropNode` (`FHIRGraph.cls:2477-2616`), beside the `rdf_labels` functional index, with no version-token bump (A-platform F-B10; A-ops hazard (a)8).

Proposal: call `Adjacency.PutLabel`/`RemoveLabel`.

Behavior to preserve: the FHIR sync's output graph.

Distinguishing case: a sync followed by `verify_graph` and the token: same labels, and the token moves. Governing statement: [fhir.sync](../ontology/features/fhir.g5.md#fhir.sync).

<a id="simp-plt-004"></a>
### Rebuild adjacency once after load_networkx

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — bulk loading is not modelled.

What is complicated now: `load_networkx` runs `rebuild_all_indices` and then `BuildKG` in indexed mode, rebuilding adjacency twice (A-platform F-B11).

Proposal: run one rebuild.

Behavior to preserve: the resulting `^KG`.

Distinguishing case: compare `^KG` dumps and the token delta with one and with two rebuilds. Governing statement: [install.bulk_load.rebuild](../ontology/concepts/install.g5.md#install.bulk_load.rebuild).

<a id="simp-plt-005"></a>
### Retire the leftover schema-state helpers that are process-global or probe retired classes

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — not modelled.

What is complicated now: `IRISCapabilities.graphoperators_deployed` probes a class FR-015 retired (`capabilities.py:15`; `schema.py:2837`); `GraphSchema.last_deploy` is process-global (`schema.py:2908-2921`); `runs_in_ivg_schema` swaps `self.conn` on a shared engine (`schema_name.py:512-527`), unsafe when an engine is shared across threads, as `cypher_api` does under `_engine_lock` only (A-platform F-S11).

Proposal: drop the probe, keep the deploy result per engine, and use a per-call rewritten cursor.

Behavior to preserve: the schema rewrite seen by each call.

Distinguishing case: two threads on one engine, one inside `runs_in_ivg_schema`: the other keeps its own connection. Governing statement: [install.deploy](../ontology/concepts/install.g5.md#install.deploy).

<a id="simp-cyp-003"></a>
### Mark a compiled entry failed when its walk raises, so the interpreter answers next time

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the compiled-plan model does not represent a raising walk.

What is complicated now: a compiled walk that raises falls to the SQL path, as the fallback rule allows, but the entry stays `ok`, so the shape pays a failed native run and a SQL run on every call until a deploy, warned once per engine (A-cypher F12).

Proposal: in `RunA`'s caller, mark the entry failed when `Walk1` raises.

Behavior to preserve: the SQL fallback for this call; a deploy or stamp change still allows a fresh build.

Distinguishing case: a shape whose compiled walk raises: the second call is answered by the interpreter, not SQL. Governing statement: [query.compiled.fallback](../ontology/features/cypher.g5.md#query.compiled.fallback).

<a id="simp-led-001"></a>
### Spell record graphs in redaction through GraphKey instead of an inline translate

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the redaction model treats the graph spelling as given.

What is complicated now: `LedgerRedact.Matches`, `PrePass` and `DropStatements` turn record graphs into names with an inline `$Translate`, a fourth spelling of the graph-key rules that ADR-0003 asks to keep in `GraphKey`.

Proposal: call `GraphKey.ForName` (or the inverse in [simp-str-002](#simp-str-002)) at those sites.

Behavior to preserve: the redaction target digest and the matching of default-graph records.

Distinguishing case: redact a named graph and the default graph with a prefix; the same records are tombstoned before and after. Governing statement: [redaction.target](../ontology/features/redaction.g5.md#redaction.target).

<a id="RC-15"></a>
### Refusals are not mapped to one typed error hierarchy at the boundary

Severity: Low · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Each layer raises its own exception types and messages: lexer SyntaxError, ValueError from the translator, connection failures reported as client syntax errors, node_not_found decoded as a relationship failure, wrong reasons in messages, SDK calls that skip the 401/403 map, the metrics hook missing Python-side refusals.
- Findings that share it: 8 (highest S3): F-0804, F-0806, F-0807, F-1506, F-1704, F-1714, F-C1109, F-C1602.
- Rule it breaks: SYS-I9; errors.py:1-17 (one catchable root IVGError); USER_GUIDE.md:313-318 (CypherParseError, GraphWriteError).
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): One error mapping per boundary (parser, write path, HTTP status, SDK, wire decoder): every refusal is a subclass of IVGError carrying the server's reason code, transport failures are transient errors; a test that enumerates every exported exception class and server code.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-31"></a>
### Descriptions are written by hand and not checked against the code

Severity: Low · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Specs, ADRs, guides, docstrings and self-describing outputs (wire schema, SHOW CONSTRAINTS, STATUS_PARTS, TCK figures) are maintained by hand; they lag the code or state behaviour it does not have, and nothing fails when they drift.
- Findings that share it: 16 (highest S3): F-0104, F-0110, F-0407, F-0408, F-0617, F-0708, F-0821, F-0909, F-1011, F-1109, F-1110, F-1301, F-1501, F-1707, F-1711, F-1713.
- Rule it breaks: none of SYS-I1..SYS-I10; playbook §3.1 and §3.8 (every requirement carries evidence); docs/dev/TESTING_POLICY.md.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Generate or test every description: execute documentation examples (tests/docs), check spec and ADR status lines in CI, generate the wire schema, constraint lists and status parts from the code, and keep evidence claims tied to commits of this repository.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="RC-34"></a>
### Stores have no enforced single write owner

Severity: Low · Decision: Open

Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)

Comparison: none — the playbook arm's remedy is prose only; no model compares it here

- Burden today: Outside the ledger, stores owned by one module are written directly by others: ^KG("prop") has no owner and four writers, the Arno bridge moves the adjacency token, the vector module kills a sub-store of ^NKG, the Cypher DELETE and the SQL adapter delete vector, document and reification rows themselves, the FHIR build writes the label index and vector rows, a loader clears content tables by raw SQL. Each direct writer skips the owner's rules (routes, tokens, graph scope, strict mode).
- Findings that share it: 7 (highest S3): F-C0340, F-C0440, F-C0640, F-C0840, F-C1040, F-C1540, F-C1740.
- Rule it breaks: SYS-I1; playbook §3.4 (each store has a single write owner); ADR-0011 (one adjacency writer); module Scope sections of the ontology.
- Redundant decision a shared mechanism would remove, and the proposal (not implemented): Name one owner per store (as GraphStores.Inventory does for erasure) and route every other writer through the owner's method; a mechanical census (as the structural lane's st-check-own-census) that fails on a write to a store outside its owner.
- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.
- Source: [reflection/ROOT-CAUSES.md](../../experiment/playbook-completion/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

## Observations and documentation drift

<a id="simp-str-005"></a>
### Drawing degree generations from the version token is not a repair

Severity: Unranked

Run: Uplift 2026-11-13

Comparison: [As-built](results/graph_structure/20261114T000451Z-prove/receipt.json) → [Proposed simplification](results/graph_structure/20261114T000451Z-prove/receipt.json)

Scope qualification: the as-built side is `witness_aba_delete_and_recreate_serves_stale_degree`; the proposal side is `witness_s1_set_generation_is_undone_by_rollback`, which shows the proposal reviving an old entry after a rollback. Finite witnesses, not state counts.

Rejected proposal (A-structure S1): `Set ^KG("gen",g,s) = $Increment(^KG("__version"))` in place of the two `$Increment`s. A `Set` is journaled, so a rollback restores the pre-image over a concurrent writer's committed generation and revives an old cache entry; the product's `$Increment` of `gen` is load-bearing (ADR-0012:23-24). The epoch stamp in [bug-str-003](bugs_issues.md#bug-str-003) is the proposed repair instead. Governing statement: [structure.degree.cache](../ontology/features/graph-structure.g5.md#structure.degree.cache).
