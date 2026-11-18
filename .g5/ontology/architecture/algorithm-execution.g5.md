# How graph algorithms run

Find how IVG chooses a reader, what the native comparison covers, and when a cached answer can be reused. See [graph algorithms](../features/algorithms.g5.md) for the available operations and their results.

## Definitions

- **Owner**: IVG's own implementation of an algorithm, running in IRIS. It is the reference answer and the fallback.
- **Arno**: an optional native library loaded into IRIS processes. It holds the Native Readers and some faster graph walks.
- **Native Reader**: an Arno implementation of an algorithm, used only after it has been proven against its Owner.
- **Reader Revision**: a whole number Arno reports for each Native Reader, raised whenever that reader's behavior is fixed. It is unrelated to a ledger revision.
- **Proof record**: the file shipped with IVG that lists, per algorithm, the lowest Reader Revision proven equal to its Owner and the library build it was proven on.
- **Evidence gate**: the test run that compares each Native Reader with its Owner and writes the proof record.
- **Graph-version token**: the namespace-wide counter that every change to the adjacency index raises, defined on the [graph-structure page](adjacency-and-derived-data.g5.md#structure.rebuilt.token).
- **IRIS collation**: the sort order used to break ties: numbers first, by value, then text (`9`, `10`, `07`, `a`).
- **Algorithm cache**: stored algorithm answers, shared by every connection in the namespace.

## Select the IRIS or native algorithm

<a id="algorithms.owner"></a>
[D · algorithms.owner]

Every algorithm has an Owner, and IVG gives complete answers without Arno. No Owner is removed when a Native Reader is adopted.

<a id="algorithms.routing"></a>
[I · algorithms.routing]

A call uses a Native Reader only when all of these hold; otherwise the Owner answers.

- The algorithm is one of PageRank, PPR, WCC, CDLP and subgraph.
- The proof record lists the algorithm.
- The loaded library reports a Reader Revision for it at or above the proof record's minimum.
- The call is within the scope the proof covers: today, the default graph only.
- The call runs in the namespace the library reads, today `USER` only; anywhere else the Owner answers, because the library would read another namespace's graph ([open question](../../Verus_verification/open_questions.md#q-plt-015)).
- PageRank also uses its Owner when the default graph is in multigraph mode or a node has no edge.

- Working assumption: Require a proven graph-specific reader before relying on native default-graph results; an unavailable Arno provider does not settle its behavior.
- Working assumption: Keep non-USER Owner routing as current availability; cross-namespace native support requires a provider deployment/proof contract.
- Working assumption: code support and namespace availability are different facts; treat store.capabilities() as a static catalogue (document it as such) and do not read it as availability; routing that needs availability uses engine.capabilities/status() or an explicit fallback.

<a id="algorithms.routing.revision"></a>
[D · algorithms.routing.revision]

Routing reads Reader Revisions only from the library's own capability report, and minimum revisions only from the proof record. It never uses the library's version string or a list written into IVG's code. A missing, failing or unreadable report means no Native Readers.

<a id="algorithms.routing.fallback"></a>
[I · algorithms.routing.fallback]

If a Native Reader fails, returns nothing or returns an unreadable answer, the Owner answers instead and the failure is logged. The caller never sees the native failure.

<a id="algorithms.routing.reload"></a>
[I · algorithms.routing.reload]

When the library is replaced, routing reads the new library's report on its next load and never routes on the old library's revisions.

<a id="algorithms.routing.excluded"></a>
[D · algorithms.routing.excluded]

Betweenness always uses its exact directed Owner. The library's own breadth-first computation is not adopted until a separate decision.

## Check the evidence for a native reader

<a id="algorithms.proof"></a>
[D · algorithms.proof]

The proof record ships with IVG and only the evidence gate writes it, never a person. An algorithm absent from it answers from its Owner, and a missing or invalid record sends every algorithm to its Owner, with a log entry.

- Working assumption: Bind proof evidence to exact library/platform builds until source or owner authority permits broader reuse.
- Working assumption: Do not infer proof coverage for accelerated algorithms absent from the gate; extending its inventory needs provider-specific evidence.

<a id="algorithms.proof.gate"></a>
[D · algorithms.proof.gate]

The gate compares each Native Reader with its Owner, using that algorithm's equivalence rule, on at least four graph shapes and one tie-heavy graph, with five repeated calls each.

- The gate fails when the proof record claims a revision above what the installed library reports.
- Where the library is required, the gate must not skip because the library is absent.
- An algorithm that fails stays on its Owner and does not block the others.

## When can IVG reuse an algorithm result?

<a id="algorithms.cache"></a>
[I · algorithms.cache]

Answers of PageRank, PPR, WCC and CDLP are cached for every connection, separately per graph, and keyed by algorithm and parameters. A cached answer is served only while the graph is unchanged, so nothing stale is ever returned. The cache applies to Owner and Native Reader answers alike and does not depend on the library build.

<a id="algorithms.cache.token"></a>
[D · algorithms.cache.token]

A cached answer is valid only while the graph-version token it was computed under is still current, as the [structure page](adjacency-and-derived-data.g5.md#structure.rebuilt.valid) defines. The token moves on changes to the adjacency index, not on node rows or properties, so the cache admits only answers that depend on adjacency alone.

- PageRank also keys on the set of nodes, because adding a node without edges does not move the token.
- WCC and CDLP cache the labels for nodes found in adjacency. Each public call then reads the current nodes with no edge to another node and adds missing ones with their own labels, even on a cache hit.
- Subgraph extraction reads labels and properties, so its answers are never cached.
- The token is shared by the whole namespace, so a write to one graph also invalidates other graphs' answers.

<a id="algorithms.cache.pagerank"></a>
[D · algorithms.cache.pagerank]

Global PageRank puts the node table's row count and largest row ID in its cache key, alongside damping and iteration count; a cache hit also requires the current adjacency token. On a hit it returns the stored score rows without reading the nodes with no edge; adding an isolated node changes the node key and makes the next call compute again.

- An unreadable node token falls back to reading the edgeless list before lookup and using that list in the key. A missing token is not a known empty node set; an empty table successfully reads as `0:0`.
- The loner reader includes nodes whose only edges are self-loops. PageRank's adapter removes those from the edgeless list; a nonempty remaining list forces the Owner, while a self-loop-only list does not force that fallback.
- These checks assume stable reads and non-reused row IDs. They do not establish a consistent snapshot during concurrent writes, PPR freshness, or numerical correctness. The Owner's 10,000-row cap can break the requirement to list every node and return scores summing to one; that is the existing [F-1003](../../Verus_verification/bugs_issues.md#F-1003).

<a id="algorithms.cache.erasure"></a>
[I · algorithms.cache.erasure]

Erasure removes the cached answers of the graphs it erases, so no answer outlives erased content.

<a id="algorithms.cache.concurrency"></a>
[D · algorithms.cache.concurrency]

When two callers compute the same uncached answer, both answers are correct and the last one stored wins. A very large or uncacheable answer is not stored, and the call still succeeds. A read-only login gets answers without caching.

## Metadata

### algorithms.owner

- Sources: [CONTEXT.md: Owner, Arno](../../../CONTEXT.md); [Spec 236 FR-005](../../../specs/236-arno-callout-adoption/spec.md); [ADMIN_GUIDE §4: Arno](../../../docs/ADMIN_GUIDE.md)
- agent
- architecture-decision

Observed divergence: `random_walk` has no Owner; without Arno it logs a warning and returns an empty list (see [walks](../features/algorithms.g5.md#algorithms.op.walks)).

### algorithms.routing

- uncertain
- Sources: [Spec 236 FR-001, FR-006, FR-014a](../../../specs/236-arno-callout-adoption/spec.md); [CONTEXT.md: Native Reader, Reader Revision](../../../CONTEXT.md); [arno_readers.py route](../../../iris_vector_graph/arno_readers.py); [stores/iris_sql_store.py](../../../iris_vector_graph/stores/iris_sql_store.py)
- Children: [revision](#algorithms.routing.revision), [fallback](#algorithms.routing.fallback), [reload](#algorithms.routing.reload), [excluded](#algorithms.routing.excluded), [Can a default-graph algorithm call use a native reader once a named graph holds edges?](../../Verus_verification/open_questions.md#q-plt-007), [Should native readers work in namespaces other than USER?](../../Verus_verification/open_questions.md#q-plt-015)
- agent
- architecture-decision, data-integrity

Spec 236's status line still says "Draft", although it shipped in 4.2.0. Since 4.6.0 only PageRank is proven, so the other four always use their Owners (ADMIN_GUIDE §4). Some routes add parameter limits beyond the proof, for example PPR uses its Owner when the call is bidirectional or excludes nodes. The routing rules are unit-tested with supplied reports (`tests/unit/test_236_reader_routing.py`). The live gate test skips unless the library is required.


The namespace guard is in [iris_sql_store.py _arno_route](../../../iris_vector_graph/stores/iris_sql_store.py#L882-L890) and [ArnoAccel.cls](../../../iris_src/src/Graph/KG/ArnoAccel.cls#L242-L262), which also refuses native PageRank on a multigraph default graph; the edgeless-node case is at [iris_sql_store.py](../../../iris_vector_graph/stores/iris_sql_store.py#L2390-L2395). Added by review round 3 R3-reader M11.

Open questions: [Should the SQL adapter's capability list say what this namespace can run?](../../Verus_verification/open_questions.md#HD-1703), [Can a default-graph algorithm call use a native reader once a named graph holds edges?](../../Verus_verification/open_questions.md#q-plt-007), [Should native readers work in namespaces other than USER?](../../Verus_verification/open_questions.md#q-plt-015)

Assumption review evidence: Changed from decisions.md: no. Probe and source confirm; added that the product already separates the facts (engine.capabilities, a06e1f50) so option (b) is the existing design, missing only documentation.

### algorithms.routing.revision

- Sources: [Spec 236 FR-002, FR-003, FR-004, FR-008](../../../specs/236-arno-callout-adoption/spec.md); [arno_readers.py](../../../iris_vector_graph/arno_readers.py); [ArnoAccel.cls ReaderRevisions](../../../iris_src/src/Graph/KG/ArnoAccel.cls)
- Expands: [Routing](#algorithms.routing)
- agent
- architecture-decision

Observed divergence: the capability and status fields that say PPR and WCC run natively come from a list written into the ObjectScript code, not from routing, so they claim native use that routing never makes.

### algorithms.routing.fallback

- Sources: [Spec 236 Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [stores/iris_sql_store.py _native_answer](../../../iris_vector_graph/stores/iris_sql_store.py)
- Expands: [Routing](#algorithms.routing)
- agent
- data-integrity

A native answer that parses but is wrong is returned and cached; the evidence gate is the only assurance against that.

Findings: [Make the engine's Owner fallback uniform across algorithms](../../Verus_verification/design_simplification.md#simp-plt-002)

Audit reproduction: [F-C1018](../../Verus_verification/bugs_issues.md#F-C1018) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [The store's membership decoder refuses the Owner's components and label-propagation answers when a default-graph node is named 'components', 'communities' or 'largest' (read as an accelerated summary…](../../Verus_verification/bugs_issues.md#F-C1018).

### algorithms.routing.reload

- Sources: [Spec 236 Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [ArnoAccel.cls](../../../iris_src/src/Graph/KG/ArnoAccel.cls); [Stage A notes F-A2](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Routing](#algorithms.routing)
- agent
- data-integrity

Suspected divergence: the server-side loader reloads a replaced library without telling the Python side, so the engine keeps the old library's report. The unit test resets the report by hand. A failed availability probe is also kept for the life of the store.

Findings: [After the native library is replaced, routing can keep using the old library's proof report](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-010)

### algorithms.routing.excluded

- Sources: [Spec 236 FR-006, FR-015](../../../specs/236-arno-callout-adoption/spec.md)
- Expands: [Routing](#algorithms.routing)
- agent
- architecture-decision

### algorithms.proof

- uncertain
- Sources: [CONTEXT.md: Proof Record](../../../CONTEXT.md); [Spec 236 FR-007, FR-008, Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [docs/dev/arno-reader-proof.json](../../../docs/dev/arno-reader-proof.json); [arno_readers.py load_proof](../../../iris_vector_graph/arno_readers.py)
- Children: [gate](#algorithms.proof.gate), [Does a proven reader revision hold for every build and platform of the library?](../../Verus_verification/open_questions.md#q-plt-013), [Must the evidence gate also cover the other algorithms the native library speeds up?](../../Verus_verification/open_questions.md#q-plt-014)
- agent
- architecture-decision

Observed: one invalid entry, including an out-of-scope algorithm, empties the whole record (it fails safe). FR-007 asks for the build per algorithm, but the record keeps one build for all. Before 4.6.0 (R104) wheels shipped no proof record.

Findings: [Capabilities and status report native algorithms that are not proven or routed](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-018)

Open questions: [Does a proven reader revision hold for every build and platform of the library?](../../Verus_verification/open_questions.md#q-plt-013), [Must the evidence gate also cover the other algorithms the native library speeds up?](../../Verus_verification/open_questions.md#q-plt-014)

### algorithms.proof.gate

- Sources: [Spec 236 FR-009, FR-010, FR-011](../../../specs/236-arno-callout-adoption/spec.md); [scripts/arno_reader_gate.py](../../../scripts/arno_reader_gate.py)
- Expands: [Proof record](#algorithms.proof)
- agent
- data-integrity

The gate's graphs are single-graph graphs in `USER`, with no multigraph mode and no nodes without edges.

### algorithms.cache


- design-verified

- Sources: [Spec 236 FR-016, FR-017, FR-022, Story 4](../../../specs/236-arno-callout-adoption/spec.md); [algo_cache.py](../../../iris_vector_graph/algo_cache.py); [AlgoCache.cls](../../../iris_src/src/Graph/KG/AlgoCache.cls)
- Playbook: [ALG-B16](../../../experiment/playbook-completion/ontology/10-algorithms.md#L309), [ALG-B16.3](../../../experiment/playbook-completion/ontology/10-algorithms.md#L312)
- Verus: active for modeled PageRank/PPR keys and repeated calls (partial for public M21): the playbook's `proofs-d1e` [`acache_l1.rs`](../../../experiment/playbook-completion/proofs-d1e/src/acache_l1.rs) `theorem_answer_is_fresh` and `acache_l2.rs` (**reviewed design**: freshness is keyed on a node token `nver` the pin does not have; the pin's behavior is control `control_f1004_create_moves_no_token`, finding F-1004, rerun here). Its theorem supports "the reviewed design returns fresh answers", not "the product does". Overlapping: `G-graph_structure` (as-built) algorithm-cache token model, which omits the parameters from the key; its witness of a rolled-back write is finding bug-str-002. Scope correction in iteration 1: Q contains only PageRank and seeded PPR, not CDLP iteration keys; Ans does not carry CDLP labels or iteration counts. M21 remains partial.
- Children: [global PageRank admission](#algorithms.cache.pagerank), [token](#algorithms.cache.token), [erasure](#algorithms.cache.erasure), [concurrency](#algorithms.cache.concurrency)
- Verus (new bounded composition): [communities](../../Verus_verification/models/communities/NOTES.md) derives immutable core payloads from raw origins and composes selected-key/token reuse with a fresh raw live census. It proves same-core isolate visibility and retains stale same-token/different-origin counterexamples. Front/shared implementation, hashing, capacity/large results, disabled/failing cache paths, concurrent publication and actual token-writer correctness are wider than this relation; prior reviewed-design and rollback findings remain.
- agent
- data-integrity

Live coverage: `tests/integration/test_236_algo_cache.py`. Each graph's cache is keyed by the adjacency form of its graph key. The cached set is fixed in `algo_cache.py` (`CACHEABLE`).

Findings: [A cached personalized PageRank answer does not notice a node created after it](../../Verus_verification/bugs_issues.md#bug-plt-017)

Audit reproduction: [bug-plt-017](../../Verus_verification/bugs_issues.md#bug-plt-017) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [communities](../../Verus_verification/models/communities/manifest.json), [graph structure](../../Verus_verification/models/graph_structure/manifest.json)

### algorithms.cache.token


- design-verified

- Sources: [Spec 236 FR-017, FR-018, FR-019, research R2](../../../specs/236-arno-callout-adoption/spec.md); [Spec 236 token audit](../../../specs/236-arno-callout-adoption/research-token-audit.md); [algo_cache.py](../../../iris_vector_graph/algo_cache.py); [Adjacency.cls](../../../iris_src/src/Graph/KG/Adjacency.cls); [structure.rebuilt.token](adjacency-and-derived-data.g5.md#structure.rebuilt.token)
- Playbook: [ALG-B16.6](../../../experiment/playbook-completion/ontology/10-algorithms.md#L315), [ALG-B16.7](../../../experiment/playbook-completion/ontology/10-algorithms.md#L316)
- Verus: active for abstract shared-cache hits and recompute after a write (partial for public J04): the playbook's `proofs-d1e` `acache_l2.rs` (**reviewed design**, see [algorithm cache](#algorithms.cache); control `control_f1004_create_moves_no_token`). As-built evidence: `G-graph_structure` `theorem_as_built_cache_sound` and the rollback witness behind bug-str-002 (not the same defect as F-1004). Scope correction in iteration 1: WCC components and the public second-connection WCC reader are not represented, so J04 remains partial; an abstract shared-cache hit is not that workflow.
- Verus (WCC/CDLP extension): [communities](../../Verus_verification/models/communities/NOTES.md) derives SQL-node/edge versus KG incidence, value-consuming page cursors with final empty confirmation, whole-result failure discard and SQL fallback. Raw stable SQL/KG projection and a common order-preserving admitted identifier carrier are required. New census8 and reused native18 corroborate finite ordinary cases; no all-driver/collation or rollback repair is implied.
- Expands: [Algorithm cache](#algorithms.cache)
- agent
- data-integrity

Live coverage: `tests/integration/test_236_token_write_paths.py`, one case per audited write path. Where the label index is declared, label writes also move the token, so the stated reason subgraph is not cached is out of date; the decision stands. The case of a write that rolls back after a reader stored an answer is the open question [When a computation sees a write that is not yet committed and that write later rolls back, must the cached result be thrown away?](../../Verus_verification/open_questions.md#structure.rebuilt.rollback). Suspected divergence: a cached PPR answer for a seed that is not yet a node survives the node's creation, since PPR is not keyed on the node set.

Findings: [A cached personalized PageRank answer does not notice a node created after it](../../Verus_verification/bugs_issues.md#bug-plt-017), [same creation trigger in F-1004](../../Verus_verification/bugs_issues.md#F-1004)

Audit reproduction: [F-1004](../../Verus_verification/bugs_issues.md#F-1004) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [bug-plt-017](../../Verus_verification/bugs_issues.md#bug-plt-017) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [communities](../../Verus_verification/models/communities/manifest.json), [graph structure](../../Verus_verification/models/graph_structure/manifest.json)

### algorithms.cache.pagerank

- design-verified

- Sources: [COUNT:MAX producer and engine consumer](../../../iris_vector_graph/_engine/algorithms.py#L179-L194), [global engine](../../../iris_vector_graph/_engine/algorithms.py#L782-L804), [store and cache](../../../iris_vector_graph/stores/iris_sql_store.py#L2362-L2424), [edgeless producer](../../../iris_vector_graph/_edgeless.py#L65-L67), [R313 tests](../../../tests/unit/test_460_r313_pagerank_loners_lazy.py)
- Verus: [pagerank_admission](../../Verus_verification/models/pagerank_admission/NOTES.md), as-built `token`, `key`, `edgeless`, `call` and named neighbor theorems. COUNT:MAX SQL, row-ID monotonicity, snapshot consistency and actual PageRank numerics remain provider obligations.
- Expands: [cache](#algorithms.cache)
- agent
- data-integrity

Findings: [F-1003](../../Verus_verification/bugs_issues.md#F-1003). Global PageRank's node key is not evidence of [PPR freshness](#algorithms.cache.token). No live IRIS or numerical proof.

Audit reproduction: [F-1003](../../Verus_verification/bugs_issues.md#F-1003) is e2e reproduced through the actual engine/Owner cap, with a passing small graph; [results](../../Verus_verification/audits/register-20261115/regressions.json). Arno route equivalence is untested.

Findings: [Global PageRank output cap](../../Verus_verification/bugs_issues.md#F-1003).

State machines: [pagerank admission](../../Verus_verification/models/pagerank_admission/manifest.json)

### algorithms.cache.erasure

- Sources: [Spec 236 FR-020](../../../specs/236-arno-callout-adoption/spec.md); [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md)
- Expands: [Algorithm cache](#algorithms.cache)
- agent
- data-integrity
- test-coverage

Live coverage: the erase cases in `tests/integration/test_236_token_write_paths.py`.

Iteration 65: every erase that removed something kills `^IVG.AlgoCache` for every graph (`theorem_erase_clears_algo_cache`; [erasure_stores binding](../../Verus_verification/results/erasure_stores/20261118T043516Z-binding/receipt.json) `B1_erase_graph_g1`: the default graph's cached WCC answer went when g1 was erased).

State machines: [erasure across stores](../../Verus_verification/models/erasure_stores/manifest.json)

### algorithms.cache.concurrency

- Sources: [Spec 236 Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [ADMIN_GUIDE §3 (reading role)](../../../docs/ADMIN_GUIDE.md)
- Expands: [Algorithm cache](#algorithms.cache)
- agent
- operations

Findings: [A cached algorithm answer computed over a write that later rolls back stays current](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-002)
