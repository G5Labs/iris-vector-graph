# Decisions for the IVG playbook continuation

Product `3eaa79cf`, submission `9c3719c1`. All 61 original HD entries have a working disposition. **Supported** means the cited authority settles the stated interpretation within its stated scope. **Assumption** means use the stated choice to proceed, retain alternatives, and distinguish it from a maintainer decision. A confirmed baseline defect can coexist with either disposition. Some entries combine a supported outcome with a provisional mechanism. A test distinguishes implementations; it cannot decide a policy the project never specified. Each question links to its original source citations, baseline behavior and alternatives.

## Evidence that changes the interpretation

- The product uses InterSystems IRIS SQL, ObjectScript and IRIS globals in a namespace. IRIS supplies its own transaction and storage engine. PGspec is a PostgreSQL specification. Build an IRIS contract around the operations IVG actually uses. [Project README](../../README.md) · [InterSystems architecture](https://www.intersystems.com/intersystems-iris-architecture-guide.pdf/)
- The explicit maintainer decisions arrived in [42907b21](https://github.com/intersystems-community/iris-vector-graph/commit/42907b21), followed by [the accepted ADR and plan](https://github.com/intersystems-community/iris-vector-graph/commit/2b8ea46d) and [the implementation](https://github.com/intersystems-community/iris-vector-graph/commit/e4b5eef5). They establish the any-record rule, content-free audit and reader/marker behavior. The plan's late marker conflicts with stronger invariants in concurrent schedules. [ADR-0013](../../docs/adr/0013-redaction-removes-content-from-history.md) · [Spec 256 decisions](../../specs/256-ledger-tenant-redaction/spec.md)
- The ledger API states the scope of strict mode. The documented schema isolation unit is the namespace; graphs scope ordinary operations. The later temporal-only predicate decision qualifies the general structural-edge rule. [Ledger API](../../specs/213-graph-revision-ledger/contracts/ledger-api.md) · [Namespace decision](../../docs/adr/0016-one-ivg-schema-per-namespace.md) · [Temporal opt-out at 3f15743a](https://github.com/intersystems-community/iris-vector-graph/commit/3f15743a)
- The repository has Issues and pull requests; its Discussions feature is disabled. The BM25 release PR explicitly advertises automatic `kg_TXT` upgrade. Spec 044 contains a clarification, a functional requirement and an acceptance criterion for it. The FHIR PR documents the source/projection integration, but does not settle durable erasure or sync ordering. Issue 13 records an IRIS 2026.1 SQL compatibility problem. No assertion here relies on the absence of an online comment. [BM25 PR 8](https://github.com/intersystems-community/iris-vector-graph/pull/8) · [Spec 044](../../specs/044-bm25-index/spec.md) · [FHIR PR 10](https://github.com/intersystems-community/iris-vector-graph/pull/10) · [IRIS issue 13](https://github.com/intersystems-community/iris-vector-graph/issues/13)
- Fresh checks on the continuation worktree: 43 unit tests passed across Python graph scoping, RRF, iFind/fusion SQL and the ledger guard. Four upstream cases passed against the dedicated IRIS Community 2026.1 container: mixed-revision metadata, repeat redaction, normalized prefixes and audit receipts. The 21 other tests in this file were deselected for this focused rerun. These checks characterize behavior; some unit tests use mocks or inspect generated SQL. See [preparation evidence](preparation-evidence.md).

## Method

**[HD-0001](../playbook-uplift/DECISIONS.md) — How to read "defined by its ancestors or an earlier same-level statement"**

Supported. Use the playbook’s literal term-scope rule. Rewrite/reparent terms and retain the strict regression test. The text of §3.1 specifies ancestors or an earlier sibling of this statement. Lexical inheritance through an ancestor’s siblings would be a published method change.

## Install and schema

**[HD-0101](../playbook-uplift/decisions/01.md) — Should an engine that cannot read the schema record be refused?**

Supported. Permit the documented warning/skip when the record is unreadable. Refuse a readable mismatch. Model these as separate outcomes. ADMIN_GUIDE explicitly documents the unreadable case. Failing closed for writes would strengthen it at the cost of compatibility.

**[HD-0102](../playbook-uplift/decisions/01.md) — Should setup save the schema record when the class deploy failed or was turned off?**

Assumption. Treat a stored schema name as a namespace binding only. Represent readiness of each deployed capability separately. Setup can deliberately omit ObjectScript. A partial class deploy cannot establish feature readiness. Alternatives are to omit the record or attach explicit readiness state.

**[HD-0103](../playbook-uplift/decisions/01.md) — Are the files under sql/ part of the product?**

Assumption. Inventory both install paths. Treat packaged SQL loaded by the legacy deployment script as reachable, and files with no loader as historical material. The distribution ships the files but the normal initializer uses different DDL. Bringing the legacy deployer to parity or retiring it are separate choices.

## Graph identity

**[HD-0201](../playbook-uplift/decisions/02.md) — What does a Python read with no graph argument read?**

Assumption. For documented graph-aware Python reads, omission selects the default graph. Preserve explicitly all-graph discovery helpers as separate operations and make their scope visible. Do not join ids from one scope to records from another. The user guide and get_nodes tests establish the graph-aware default. Some id-only helpers explicitly advertise all graphs. Aligning every helper with one signature would change compatibility.

**[HD-0202](../playbook-uplift/decisions/02.md) — In a multigraph, does a direct edge delete remove one parallel edge or all of them?**

Assumption. Preserve the triple-wide meaning of the legacy direct delete where documented by behavior. Model per-edge Cypher delete separately. Treat single-edge targeting on the direct API as a separate operation requiring an id or key. Spec 234 settles per-edge Cypher semantics; it leaves the direct delete ambiguous. Refusing an ambiguous direct call is a defensible alternative.

## Direct writes

**[HD-0301](../playbook-uplift/decisions/03.md) — Does ledger strict mode cover the standalone bulk loader?**

Supported. Exclude the standalone bulk loader and raw SQL from the ledger strict-mode guarantee at this pin. Enumerate them as possible writers. Spec 213’s API contract explicitly names both exceptions. Extending enforcement to those writers would be a new contract.

**[HD-0302](../playbook-uplift/decisions/03.md) — May a direct edge delete remove an edge row that a temporal edge still implies?**

Supported. A temporal-backed structural row must survive direct deletion while its temporal support remains. Preserve explicit-edge deletion separately; account for the ADR-0015 predicate opt-out. ADR-0009, subsequent purge rules, and ADR-0015 distinguish ownership and nonstructural predicates. Refusing an ambiguous delete is an alternative mechanism.

## Adjacency

**[HD-0401](../playbook-uplift/decisions/04.md) — How should erase and rebuild retire a source generation?**

Assumption. Require that invalidation can never make an old degree-cache value valid again. Model a fresh graph epoch or monotonically increasing generation, including erase/rebuild. ADR-0012 depends on generation validation. A non-identifying epoch avoids leaving erased node ids in counters. A per-source generation also works if erasure requirements allow it.

**[HD-0402](../playbook-uplift/decisions/04.md) — May two adjacency rebuilds run at the same time?**

Assumption. Allow at most one publishing rebuild per adjacency structure. Let a second call wait or return a documented busy result. The admin guide names a single rebuild, but the cited exclusive lock protects a particular snapshot path. A proven concurrent generation swap would also satisfy the objective.

## Temporal

**[HD-0501](../playbook-uplift/decisions/05.md) — Are the end nodes a temporal write creates governed by the ledger?**

Assumption. Represent implicitly created endpoint rows as real effects. For a governed changeset, record them or give them identifiable derived provenance before excluding them from replay. Respect the temporal-only opt-out. ADR-0009/0015 establish which modes create structural rows. Requiring callers to pre-create endpoints would change the existing API. The choice of representation is provisional.

**[HD-0502](../playbook-uplift/decisions/05.md) — Is the temporal index inside the ledger's guarantee?**

Supported. Record the changeset temporal operation in history. Treat temporal tiers, engine purges and unlogged temporal writes as outside the current structural replay guarantee. Keep their actual effects in the environment model. The coexistence test, replay implementation and record layout support this narrower scope. Full temporal reconstruction needs additional record fields and operations.

## Vector search

**[HD-0601](../playbook-uplift/decisions/06.md) — Are the IVF, tree (VecIndex) and PLAID indexes inside the erasure promise?**

Assumption. Model retained vector-index contents as observable after erasure unless purged. For graph-owned indexes require invalidation or deletion; for external/caller-managed indexes state the owner and exposure explicitly. The every-store promise and migration guide’s acknowledged gap preclude silently excluding the indexes. Mandatory rebuild or explicit external ownership are alternative designs.

**[HD-0602](../playbook-uplift/decisions/06.md) — May an index build be seen half-done, and may a stopped build leave a partial index?**

Assumption. Require readers to see a complete published index or a clear unavailable result, including interrupted rebuilds. Model the existing partial-build behavior separately. The multi-call implementation exposes partial generations. Atomic publication or an exclusive building state are alternatives; no source settles which service level is promised.

**[HD-0603](../playbook-uplift/decisions/06.md) — Should the vector-and-graph search keep its k best candidates?**

Assumption. Use the best k of the scored candidate set for the reviewed ranking contract, with defined tie behavior. Record the implementation’s unordered truncation as the baseline. The implementation’s docstring acknowledges arbitrary truncation. A documented approximate candidate budget is an alternative and needs its own claim.

**[HD-0604](../playbook-uplift/decisions/06.md) — May two embed queue workers run at once?**

Assumption. Model both workers as independently schedulable. Adopt a single active consumer as the minimal reviewed policy unless atomic claims with recovery are implemented. ClaimPendingBatch is a scan. A single-worker deployment is only a premise unless enforced. Multiworker ownership with redelivery is the alternative.

## Text search

**[HD-0701](../playbook-uplift/decisions/07.md) — Must a BM25 Build (and Drop) exclude writers and be all-or-nothing?**

Assumption. Serialize index modifications and publish a complete BM25 generation or return unavailable. Include Build, Drop, Insert, Delete and crash. ADR-0007 covers index-level writers. Its narrower FR names Insert/Delete. An offline, operator-quiesced rebuild is an alternative with a testable premise.

**[HD-0702](../playbook-uplift/decisions/07.md) — Which reciprocal-rank-fusion rule is the product's?**

Assumption. Preserve and test the ranking rule of each existing surface, including how missing ranks and input text lists differ. Introduce a single formula only with a versioned contract. The engine rule has its own regression, and the SQL/retrieval surfaces differ. Standard zero contribution for a missing item is a candidate for a future common API.

**[HD-0703](../playbook-uplift/decisions/07.md) — Is spec 044's kg_TXT-to-BM25 fallback still wanted?**

Supported. Honor the documented BM25 fallback when the index matches the requested graph and input corpus. Never consult another graph’s index. Record uncovered graph/corpus combinations explicitly. Spec 044 FR-012, SC-004 and upstream PR 8 establish the original feature. Later graph scoping limits safe applicability. Removing the promise would require an explicit superseding decision.

**[HD-0704](../playbook-uplift/decisions/07.md) — Is `__stop__` a reserved BM25 index name?**

Assumption. Reserve the internal stopword name for metadata. Reject it at public index-management entry points while modeling the baseline’s unchecked names. Listing already hides it and metadata shares the index key space. Moving metadata to a separate root is a compatible alternative after migration.

**[HD-0705](../playbook-uplift/decisions/07.md) — Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?**

Assumption. Treat the exported search helpers as compatibility surfaces; qualify their actual support and graph scope. Prefer deprecation with migration advice if they cannot honor the public contract. Exports are evidence for callers, even without an API-reference entry. Removing them or upgrading them both require explicit compatibility decisions.

## Cypher SQL

**[HD-0801](../playbook-uplift/decisions/08.md) — Where and how should ledger strict mode refuse a Cypher write?**

Assumption. Model the Python guard, its cache and documented failure modes. The intended refusal of guarded operations still applies; the gap between these commitments needs explicit treatment. Tests pin the TTL and fail-open cases. The spec promises refusal under strict mode. Fresh checks or fail-closed behavior would change those semantics; raw SQL remains separately classified.

**[HD-0802](../playbook-uplift/decisions/08.md) — Does a mapped label belong to every graph?**

Assumption. Treat mapping registration as namespace-wide. For a scoped read, require graph-aware mapping provenance or an explicit documented exception. Model current global visibility separately. The mapping has no graph key but graph scoping constrains ordinary graph tables. Rejecting mapped labels in a named scope is another conservative choice.

**[HD-0803](../playbook-uplift/decisions/08.md) — Is `sql/operators.sql` product code?**

Supported. Mark sql/operators.sql as a shipped reference with no standard deployment path. Trace the distinct operators_fixed.sql legacy caller and class-installed procedures separately. The deployment paths identify which definitions execute. Removing or regenerating the historical SQL is a maintenance choice.

**[HD-0804](../playbook-uplift/decisions/08.md) — Should `CREATE CONSTRAINT` / `CREATE INDEX` be refused rather than accepted as a no-op?**

Assumption. Model the accepted compatibility DDL as an acknowledged no-op; it establishes no index or uniqueness invariant. Make that outcome visible to callers. The dispatch code explicitly recognizes tooling commands. Warning versus refusing unsupported DDL remains a compatibility choice.

## Native Cypher

**[HD-0901](../playbook-uplift/decisions/09.md) — Should a running engine notice a revoked table right or a dropped adjacency index?**

Assumption. Require authorization at use and a current route capability. A cached positive result alone cannot attest either after a revoke or an index change. Spec 253 FR-011 and the gate distinguish user permissions from plan versioning. Revalidate or use sound invalidation; on failure select an authorized fallback.

**[HD-0902](../playbook-uplift/decisions/09.md) — Should shadow mode fail when the native path raises an error?**

Assumption. Keep ordinary SQL fallback. In shadow validation, record a native exception as an unsuccessful comparison and require a clean comparison for a parity claim. The spec asks for difference detection and fallback. Reporting an explicit failed comparison reconciles both. Raising in shadow mode is another valid interface.

**[HD-0903](../playbook-uplift/decisions/09.md) — What may a native read answer while another writer's transaction is open?**

Assumption. Allow the observed interleavings of native global reads and SQL reads. Grant snapshot consistency only to paths with an explicit synchronization contract and evidence. The live probe saw uncommitted global visibility; it does not establish every SQL read has the same isolation. A stable snapshot or an epoch plus a writer protocol would strengthen the promise.

**[HD-0904](../playbook-uplift/decisions/09.md) — Should a compiled plan that fails while running be set aside?**

Assumption. Treat compiled execution errors as a fallback outcome. Quarantine a failed entry per plan generation in the reviewed design; allow retry after invalidation. ADR-0014 promises a fallback for unsupported/compile-failed shapes. Retrying the compiled entry indefinitely, SQL fallback or interpreter retry are distinguishable policies.

## Algorithms

**[HD-1001](../playbook-uplift/decisions/10.md) — What should `random_walk` answer, and over which graph?**

Assumption. Require a declared graph scope and an observable unavailable result. Model the existing merged-cache route as such and do not infer an empty graph from missing acceleration. No authoritative walk specification settles this. A default-graph implementation or a documented legacy namespace-wide walk are alternatives.

**[HD-1002](../playbook-uplift/decisions/10.md) — Should label propagation say when its labels did not settle?**

Assumption. Return the last round when bounded iterations expire, and expose whether labels settled. Preserve the current return shape if a separate diagnostic suffices. The documented algorithm may oscillate. Raising instead is defensible, but changes consumers of best-effort labels.

**[HD-1003](../playbook-uplift/decisions/10.md) — Should the shortest-path routines refuse a direction they do not walk?**

Assumption. Use the documented public direction semantics, including caller reversal for inbound paths. Give lower-level procedures an explicit direction precondition or reject unsupported inputs. The callers normalize direction while class methods differ. Implementing all directions in each class is an alternative; an invalid direction must not count as proof of no path.

**[HD-1004](../playbook-uplift/decisions/10.md) — How many nodes should global PageRank list?**

Assumption. Require the same result contract on every PageRank route. Pending a documented limit, model uncapped results as the objective and expose any truncation. The native and ObjectScript implementations disagree beyond 10,000. Documented top-k or pagination is a reasonable alternative.

## Ledger

**[HD-1101](../playbook-uplift/decisions/11.md) — What should a node change do when only a named graph holds the id?**

Assumption. Scope ledger node mutations to their owned default-graph row. A same-named node only in a named graph cannot satisfy that mutation’s existence precondition; model edge endpoint lookup separately. R281/R290 and scoped node-operation tests support default-graph ownership. Deliberately graph-qualified ledger nodes would change the record schema.

**[HD-1102](../playbook-uplift/decisions/11.md) — Should disable() and set_strict() refuse a caller's open transaction, as enable() does?**

Assumption. Refuse disable/set_strict inside an incompatible caller transaction until both connection modes can join it with the same rollback behavior. The neighboring enable/redact lifecycle contract and connection routing make one opinionated behavior defensible. Explicitly enlisting both calls is the alternative.

**[HD-1103](../playbook-uplift/decisions/11.md) — Should strict mode be enforced by the server, or stay a Python-only check?**

Supported. Treat strict mode as a client-side guard on the specified methods at this pin. Inventory uncovered Python paths, cache behavior and external writers separately. Spec 213 explicitly excludes bulk/raw SQL. A server-wide barrier is a new assurance target and changes operational compatibility.

**[HD-1104](../playbook-uplift/decisions/11.md) — Should the ledger's settings be changeable after the genesis?**

Assumption. Keep creation-time size and reconstruction bounds fixed in the baseline. Record strict’s explicit toggle and current re-enable/reset semantics. Do not assume settings are mutable after genesis. Ledger.Enable distinguishes new, already-enabled and re-enabled states. Preserving an unspecified strict value or adding config setters are alternatives.

**[HD-1105](../playbook-uplift/decisions/11.md) — Should post-commit properties be recorded by the ledger?**

Supported. Treat post-commit properties as a separate direct write outside revision replay, and require idempotent retries. Report divergence when those properties affect governed state. Spec 218 explicitly chose direct SQL without another revision; the caller-transaction test comments on this. Moving properties into the original revision is a possible redesign.

## Erasure

**[HD-1201](../playbook-uplift/DECISIONS.md) — Should a graph erasure take the ledger head lock?**

Assumption. Require erase and same-target writes/redaction to serialize for the reviewed contract. Initially model the ledger head lock, including dirty reads from a still-open erasure. The counterexample and accepted erase/redact ordering support the need for coordination. A graph-specific protocol or enforced quiescence could also satisfy it. Choice of lock is provisional.

## Redaction

**[HD-1301](../playbook-uplift/DECISIONS.md) — Should the redaction's opening check and its marker be one locked step?**

Assumption. Acquire sole target ownership and check liveness atomically at start. Keep per-batch updates atomic and release ownership only for that run. ADR-0013 requires exclusion; the plan’s late marker and live observations contradict it. A target-specific ownership protocol is possible if it preserves all global reader/audit promises.

**[HD-1302](../playbook-uplift/DECISIONS.md) — Which rule clears a revision's free text: any tombstone or every record?**

Supported. Clear the revision free text if any record is redacted, keeping every unaffected record intact. Correct the stale “every” wording in FR-004. Tom’s Decision 2, accepted ADR-0013, upstream spanning-revision test and live behavior agree. The older every-record rule is contradicted.

**[HD-1303](../playbook-uplift/DECISIONS.md) — Can an unfinished redaction be abandoned, and what may a default-graph target touch?**

Assumption. Resume the same target. Preserve exclusion for other targets. Assume no generic abandonment of committed tombstones. Refuse an ambiguous unprefixed default-graph request unless ownership and absence of live matching nodes can be established. ADR-0013 defines resumption but gives no undo. A carefully audited cancellation/repair operation or graph-blind liveness check with provable attribution are alternatives.

**[HD-1304](../playbook-uplift/DECISIONS.md) — How is a tenant's node history redacted when nodes live in the tenant's own graph?**

Assumption. For historical graph-blind node records use a tenant prefix when available. Otherwise return an explicit incomplete/refused outcome if ownership cannot be established. Model graph-qualified future records separately. Spec 256 promises tenant erasure but the current records lose the information needed to distinguish some node histories. A migration with trustworthy prior provenance could support graph-only erasure.

**[HD-1305](../playbook-uplift/DECISIONS.md) — Should a replayed commit apply its post-commit properties?**

Supported. A retry must not recreate an erased tenant’s properties. Preserve idempotency and ensure genuinely incomplete first attempts have an explicit recovery path. ADR-0013 and the idempotency contract establish the outcome; suppressing reapplication after completed effects or recording atomic completion are mechanisms. The current replay path diverges.

## Replay

**[HD-1401](../playbook-uplift/DECISIONS.md) — Verification and record readers: node identity and redaction checks**

Assumption. Compare the node identity that the ledger operation governs, including graph where represented. A reader must return a consistent pre/post view or the documented in-progress result. Verify needs a coherent cut across its reads. The detach-delete and partial-view live traces distinguish failures. Target node representation remains linked to HD-1101/1304. Epoch validation, locking or genuine snapshots are alternative implementations.

## FHIR and integration

**[HD-1501](../playbook-uplift/decisions/15.md) — Should a FHIR sync be governed by the ledger?**

Assumption. Treat FHIR sync as an external writer of a rebuildable projection at the pin. Retain observable effects in verify; do not silently label divergence as equality. The integration is driven by a separate source and writes outside the Python guard. A ledger-governed projection would need recorded batches or an explicit refusal in strict mode.

**[HD-1502](../playbook-uplift/decisions/15.md) — Should erasing a FHIR graph stop its sync task?**

Assumption. Separate transient clearing from permanent decommissioning. Ordinary erase preserves registration and can refill on schedule. For durable tenant removal require the feed to be paused or deregistered and verify it stays paused. ADR-0015 describes the FHIR registry as configuration; source and watermark behavior agree. Automatically canceling the task on every erase is another product choice.

**[HD-1503](../playbook-uplift/decisions/15.md) — What happens when an erase runs during a FHIR sync?**

Assumption. Serialize erase with active sync publication (or invalidate its generation and restart safely). Cover the running task and pending batches in the machine. The eraser and FHIR sync use different coordination at the pin. An enforced quiescent-admin workflow can substitute if its premise is explicit.

**[HD-1504](../playbook-uplift/decisions/15.md) — Should one unreadable FHIR resource block its graph's sync?**

Assumption. Use failure without advancing the watermark as the baseline. Surface the offending key and documented recovery; progress depends on repair. Do not assume silent skips. The batch is transactional. A durable quarantine and replay protocol could preserve progress if the product explicitly allows partial indexing.

## Public interfaces

**[HD-1601](../playbook-uplift/decisions/16.md) — Should a server limit which graphs a caller may name?**

Supported. Use an IRIS namespace as the documented isolation boundary. Named graphs and prefixes scope data operations inside it; a graph id alone confers no authorization. USER_GUIDE and FHIR_GRAPH state this. A session-bound graph execution context is a future feature in CONTEXT. Spec 256’s tenant target does not change authentication.

**[HD-1602](../playbook-uplift/decisions/16.md) — Should admin work need a different key from reading?**

Assumption. Record the existing common key and IRIS user privileges. Treat separate admin credentials/roles as a proposed strengthening unless a stronger accepted deployment contract is found. The current HTTP server has one key. Endpoint separation, privileged route disablement or a second role remain alternatives.

**[HD-1603](../playbook-uplift/decisions/16.md) — Should the Cypher HTTP server run a failed query a second time?**

Assumption. For a reviewed retry policy, repeat a read or a write known to be unexecuted, or a write with a verified idempotency key. An ambiguous commit outcome remains unknown. The server currently retries after exceptions. Disabling retries entirely is a compatible safety alternative at the cost of availability.

**[HD-1604](../playbook-uplift/decisions/16.md) — Should the REST dispatcher's `/metaPath` take a graph?**

Assumption. Treat the current REST metaPath operation as default-graph-only and include that in its contract. A graph argument is a compatibility extension. Spec 230 explicitly extended two other routes. The traversal can support a graph argument, but this route currently does not accept one.

**[HD-1605](../playbook-uplift/decisions/16.md) — Should the generated GraphQL server match the sample API's safety limits?**

Assumption. Record the generated and sample GraphQL servers as distinct entry points. Use the shared deployment constraints when presenting either as production-ready; otherwise document limits of the generated entry point. Their depth limits, mode enforcement and health behavior differ. Bringing them to parity or designating the generated app as a sample are alternatives.

## Operations

**[HD-1701](../playbook-uplift/decisions/17.md) — Should the SQL adapter's pass-through refuse a write when called read-only?**

Assumption. Treat a true read_only parameter as a requested guarantee. Enforce at a trusted execution boundary or explicitly refuse an unsupported read-only execution. The public protocol exposes the flag but the adapter ignores it. Removing/renaming an advisory flag is a versioned alternative. A read-only name alone cannot establish database effects.

**[HD-1702](../playbook-uplift/decisions/17.md) — Should the HTTP client resend a write query after a server error?**

Assumption. After an ambiguous HTTP outcome, retry only a known read or an explicitly idempotent operation. Treat client and server retries as one combined protocol. The SDK retries POST requests; layered retries can multiply work. Reporting an unknown outcome or supplying end-to-end idempotency are alternatives.

**[HD-1703](../playbook-uplift/decisions/17.md) — Should the SQL adapter's capability list say what this namespace can run?**

Assumption. Represent supported-in-code and available-in-this-namespace as different facts. For routing, probe installed capabilities or use an explicit fallback. The advertised capability matrix is static; availability can vary with deployment. A static feature catalog remains useful if documented as such.

**[HD-1704](../playbook-uplift/decisions/17.md) — Should the low-level vector helper refuse a vector of the wrong width?**

Supported. Keep normalize_vector’s documented padding, truncation and finite-value conversion as the low-level helper contract. Keep registry-aware engine writes strict about identity/width. Test both boundaries separately. The helper docstring expressly promises coercion; ADR-0006 concerns registered engine writes. Changing the public helper to strict validation requires a compatibility decision.

**[HD-1705](../playbook-uplift/decisions/17.md) — Should server start refuse to listen on every address without an API key?**

Assumption. Keep both contradictory deployment contracts in the record. For the reviewed configuration default to local-only or require explicit opt-in for unauthenticated external binding. The deploy README and admin guide conflict. A deliberately open, separately documented trusted-network mode is an alternative. This is a provisional deployment default.

## Snapshot

**[HD-1801](../playbook-uplift/decisions/18.md) — What should a restore do to the live ledger?**

Assumption. Treat the archive’s history as a unit. For divergent histories prefer refusal before mutation, with an explicit replacement/recovery path. Preserve current redaction obligations during authorized restoration. The spec promises ledger survival; the pin overlays records. An offline complete replacement or replay of newer redactions requires an explicit retention/recovery policy.

**[HD-1802](../playbook-uplift/decisions/18.md) — Should a snapshot be a point-in-time view?**

Assumption. Only claim a consistent snapshot when writers are quiescent or there is a verified snapshot/epoch protocol. For the current exporter declare the quiet-writer premise. The exporter reads stores sequentially. Online consistent export is a stronger feature requiring store-wide coordination and conformance evidence.

## Questions to show a maintainer at the end

Carry these working choices throughout the run. Remove a question from the final list when new evidence settles it. Rank what remains by the effect a different answer would have.

1. What identity should historical nodes have when two graphs use the same unprefixed id? Can graph-only tenant erasure refuse ambiguous histories, or does it require a provenance migration? HD-1101, 1303, 1304, 1401.
2. During overlapping erase, write, sync and redaction operations, may callers receive a busy/refused result? Can operators ever abandon a partially committed redaction, and what does recovery promise? HD-1201, 1301, 1303, 1503.
3. Which derived stores must a durable tenant removal purge, and must it stop scheduled ingestion? What must happen on restoring an archive predating redaction? HD-0601, 1501–1503, 1801.
4. Which reads and exports promise a single consistent view under concurrent writes? Can an operator require a quiet namespace for an online snapshot? HD-0903, 1401, 1802.
5. Which of the incompatible public API behaviors must remain for existing users? The material cases include global discovery versus default-graph reads, ambiguous parallel-edge deletion, cross-surface ranking, and retry after an unknown write outcome. HD-0201–0202, 0702, 1603, 1702.
6. Which deployment entry points are supported in production, with what operator permissions and defaults? Preserve the current namespace authorization boundary and document any stronger assumptions separately. HD-0102–0103, 1602, 1605, 1705.
