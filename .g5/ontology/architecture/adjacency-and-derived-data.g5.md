# Adjacency and derived graph data

Follow a graph write from its rows to the indexes and caches used by readers. This page also explains who owns the time index and how temporal events produce structural edges. For repairs, see [status and repair](../operations/status-and-repair.g5.md).

## Definitions

- **Adjacency index**: the native index of each graph's out-edges, in-edges and node labels, used for neighbor lookup, walks and the graph algorithms.
- **Declared index**: an adjacency index that the database maintains from the edge and label tables on every row change.
- **Generation**: a per-node counter that moves whenever the node's outgoing adjacency changes.
- **Rebuilt store**: a derived store that is rebuilt from the tables rather than kept current on every write.
- **Graph-version token**: one namespace-wide counter of writes that can change an algorithm's answer.
- **Time index**: the per-graph store of temporal edges, their attributes, the statistics and the newest-event index.
- **Structural edge**: a relationship row in the edge table. Where the adjacency index is declared on that table, the index mirrors each row for traversal, degree and Cypher `MATCH`.
- **Temporal mark**: a flag on a structural edge saying that it exists only because temporal edges imply it.

## Parallel edges in the adjacency index

<a id="structure.multigraph.layout"></a>
[D · structure.multigraph.layout]

A triple with one edge looks the same in the adjacency index in either mode.

- While a triple has two or more edges, each edge also has its own entry, and the triple records how many edges it holds.
- The triple's own entry carries the weight of its edge with the lowest edge key.
- Edge keys are never renumbered, and a live edge's key is never reused.
- A new edge takes one more than the triple's highest live key, or 0 for the first, so the key of a deleted highest edge can return.
- When two writers pick the same new key, the loser retries once with a fresh key and fails loudly after a second clash.
- A rebuild produces the same layout as the writes that led to it.
- The one-to-two transition keeps the earlier edge as a keyed entry with its own weight, whatever order the rows are written or rebuilt in.

## Who maintains the adjacency index?

<a id="structure.adjacency"></a>
[D · structure.adjacency]

The adjacency index is derived from the edge and label rows, which stay authoritative. Every entry is keyed by its graph ([graph keys](../concepts/graph-scope.g5.md#graph.key)).

- Working assumption: Unchanged: at most one publishing rebuild per adjacency structure; a second call waits or gets a documented busy result. Refined: ADMIN_GUIDE's sentence is literally about ^NKG and holds live; the ^KG half is unserialized.
- The breadth-first walk, its SQL fallback, the ends-only walk and the shortest-path routines each answer from one graph's entries; another graph's edges change no answer.
- Removing a triple from one graph leaves the interned snapshot's merged edge while another graph still holds the triple.

<a id="structure.adjacency.declared"></a>
[I · structure.adjacency.declared]

Where the index is declared, every row insert, update or delete, by any path, changes it in the same transaction. A rollback undoes both, and the index holds no entry without a row behind it.

<a id="structure.adjacency.undeclared"></a>
[I · structure.adjacency.undeclared]

Where the index is not declared, such as after a setup that did not finish, only the engine's own edge writers and a rebuild keep it current. Cypher writes, `store_edge` and the store's `write_edges` leave it stale until a rebuild.

<a id="structure.adjacency.one_writer"></a>
[D · structure.adjacency.one_writer]

One module makes every change to the out-edge and in-edge entries, so the rules every such change must follow are written once. A source scan fails on any other writer unless an explicit, justified exception is added.

<a id="structure.adjacency.bulk"></a>
[D · structure.adjacency.bulk]

A bulk path that writes rows without index upkeep must leave no duplicate rows and must rebuild the indexes before it returns, whether it succeeds or fails. Three paths do this:

- `bulk_create_nodes` and `bulk_create_edges`, which drop the indexes for a large batch and rebuild them afterwards;
- `bulk_load_session`;
- the bulk loader, whose own contract is on the [install page](../operations/snapshots-and-bulk-load.g5.md#install.bulk_load).
- `bulk_load_session` keeps `^NKG` current when no caller transaction is open. Inside one it leaves `^NKG` to `sync()`, and the loading engine's `status().pending_sync` stays True until then, even after a rollback; another engine or process reports False.

<a id="structure.adjacency.scan"></a>
[I · structure.adjacency.scan]

The SQL function `MatchEdges(source, predicate, shard, graph)` answers one graph's out-edges from the adjacency index, and `MatchEdgesAllGraphs(source, predicate, shard)` answers every graph's, each edge with its graph. A caller without SELECT on `rdf_edges` is refused before anything is read ([who holds SELECT](../concepts/access.g5.md#access.iris_boundary)).
- An empty source means every source, and an empty or NULL predicate every predicate.
- For `MatchEdges` a graph of `''`, NULL, 0, `'0'` or none is the default graph alone; no value of it means every graph. SQL hands `''` to the function as a character 0, which it reads as empty.
- Each edge carries its stored weight, 1.0 when it has none. A triple held by two graphs is answered once for each.
- The `shard` argument is not read: every value answers the same edges.
- `IVG_EDGESCAN=1` sends a Cypher hop from a node named by its id, with no `USE GRAPH` or `USE GRAPH ''`, through this scan instead of the edge rows. It must answer what the default plan answers. Today the hop's edges are the same, but every relationship property, `r.weight` included, reads null on the scan ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-133)).

<a id="structure.adjacency.declare"></a>
[D · structure.adjacency.declare]

Setup declares the two adjacency indexes only once their prerequisites exist, declares each one once, and leaves an index that is already declared alone.
- Nothing is declared while the callback classes are not compiled, while the schema's own procedure class is not compiled, before the edge table has its edge key column, or before both tables have the graph column. Setup skips with a reason, and a later setup declares them.
- Once every prerequisite exists, both are declared: the edge index first, then the label index.
- An index already declared as the adjacency index is left alone. A plain index with the same name is dropped and replaced.
- Before the edge index is built, every triple that has temporal events but no row gets its marked row. The build then fills the index from every row, which also repairs drift.

## Degree cache

<a id="structure.degree.cache"></a>
[D · structure.degree.cache]

A counted degree may be cached and served while the node's generation has not moved since the count. Every change to a node's outgoing adjacency moves its generation, and deleting the cache changes no answer.

- Working assumption: Unchanged from decisions.md: invalidation can never make an old degree-cache value valid again; model a monotone generation or a fresh graph epoch across erase and rebuild; keep as-built A (kill) as the baseline with its narrow window.

<a id="structure.degree.cache.uncommitted"></a>
[I · structure.degree.cache.uncommitted]

A cached degree never includes an edge that was later rolled back.

- Each graph has one writer lock. Writers hold it shared, so writers never wait for each other, and keep it until their transaction ends.
- A reader stores its count only when it could take that lock alone at once, and the node's generation did not move while it counted.
- A writer that cannot get the lock within 5 seconds still writes, and turns degree caching off for its graph until the next rebuild.

<a id="structure.degree.cache.erase"></a>
[I · structure.degree.cache.erase]

Erasing a node or a graph clears its generations and cached degrees. No count cached before the erase may be served after it, even when later writes bring the generation back to an earlier value.

<a id="structure.degree.cache.warm"></a>
[D · structure.degree.cache.warm]

A rebuild leaves the degree cache filled, so the first reads after it do not recount.

- Standalone `WarmAll(graph)` also fills graphs that exist only in adjacency globals: it enumerates that graph's outgoing sources directly, without SQL node or edge rows. It fills an all-predicate entry and each predicate entry and returns the number of sources filled, not the number of entries; target-only nodes are not sources.
- A failed exclusive writer-lock probe, a no-lock-writer flag, or a generation change prevents that source from being counted as filled. A generation change detected after storing removes the source's new entries.
- The whole-graph stamp is replaced only when every visited source filled and the graph-version token stayed equal. Otherwise it is removed and readers use their per-source checks. Empty outgoing globals return zero and may have a current whole-graph stamp; a subsequent token change makes that stamp stale.
- At the pin a rebuild bumps the token after warming, making the whole-graph stamp stale at once even though the per-source entries remain valid; this departure remains [simp-str-003](../../Verus_verification/design_simplification.md#simp-str-003). Clearing entries alone while keeping a current stamp can return zeros ([F-0406](../../Verus_verification/audits/register-20261115/bugs-review.md#F-0406)).

## Rebuilt stores and the graph-version token

<a id="structure.rebuilt"></a>
[D · structure.rebuilt]

The interned snapshot, the two-hop statistics, the accelerator's snapshot and cached algorithm results are rebuilt stores. Each records the graph-version token it was built from and is current only while that token is still the live one, so a failed rebuild leaves it stale for every process.

- Working assumption: yes, because the degree cache and the rebuild already treat that case as unsafe. Today the cached result stays current until the next write (observed).

<a id="structure.rebuilt.token"></a>
[I · structure.rebuilt.token]

Every change to the adjacency index, to its edges or to its labels, increases the graph-version token; a write to node rows or properties alone does not. The token never decreases and a value is never reused, even when the write rolls back. A cached answer that also depends on other content must key on that content too or not be cached ([algorithm cache](algorithm-execution.g5.md#algorithms.cache.token)).

<a id="structure.rebuilt.stamp"></a>
[I · structure.rebuilt.stamp]

A rebuilt store is current only when it carries a build stamp and that stamp equals the live token. A store that was never stamped is stale even while the token is still zero, and a store stamped at zero is current until the token moves.
- An unset token reads as zero, but an unset or empty stamp means "not known", never zero.
- Asking which of several stores are stale applies the same rule to each store, in the order asked.
- The two-hop count reader in ObjectScript and the Python freshness module apply this one rule.
- Today `khop2_count_fast` with a type answers, while the two-hop statistics are current, the sum of the middle nodes' out-degrees, which counts the start reached back and a target once per middle node; after any write it answers the walked count ([finding](../../Verus_verification/bugs_issues.md#bug-str-117)).

<a id="structure.rebuilt.valid"></a>
[I · structure.rebuilt.valid]

A cached algorithm result is valid only while the token it was computed under is still the live token. The token is read before the computation starts, so a write during the computation leaves the result stale, never wrongly current.

<a id="structure.rebuilt.stale_read"></a>
[I · structure.rebuilt.stale_read]

A reader never answers from an interned snapshot known to be stale.

- After an erasure, the first algorithm that reads the snapshot rebuilds it once, under a lock, before it answers.
- A variable-length Cypher query that would read a stale snapshot raises an error asking for a rebuild.

## Who owns the time index?

<a id="temporal.owner"></a>
[D · temporal.owner]

Only the time-index component may access the temporal stores; every other component uses its operations, so a change to the stored layout touches one place. A new cross-graph need becomes a new operation on that component.

## Who writes temporal statistics?

<a id="temporal.stats.writers"></a>
[I · temporal.stats.writers]

Each kind of write changes the statistics of the edge's bucket in a fixed way.
- An insert at free coordinates counts the edge once: count, sum, minimum, maximum, the distinct-target sketch and the source's event counter.
- An insert or skip at occupied coordinates changes nothing.
- An update at occupied coordinates counts the edge again in count, sum, extremes and event counter, although one edge remains. The docs say the statistics keep the original value; what they should hold is [open](../../Verus_verification/open_questions.md#temporal.write.update-statistics).
- A delete rebuilds the bucket's count, sum, extremes and sketch from its surviving edges and lowers the event counter by one, removing it at zero.
- A write rolled back by its caller leaves its count, sum and event counter, while its edge, extremes and sketch are undone. A whole-bucket read can then report a count with no minimum or maximum.

## How an event becomes a structural edge

<a id="temporal.structural"></a>
[D · temporal.structural]

A temporal edge implies a structural edge for the same triple in the same graph. The triple is then visible to SQL, Cypher `MATCH`, edge counts and traversal while any of its timestamps exist.
- The structural edge comes with both endpoint nodes in that graph.
- [Temporal-only predicates](../features/temporal.g5.md#temporal.optout) are the exception.
- This needs the adjacency index declared on the edge table. Without it, a write that names no graph leaves only an adjacency entry, which the next rebuild wipes; a write that names a graph also writes an unmarked structural edge and its nodes, which no temporal delete or purge removes and which ignore the temporal-only setting.
- Whether an explicit edge delete may remove a marked structural edge while timestamps remain is [open](../../Verus_verification/open_questions.md#q-tmp-006).

- Working assumption: Preserve the temporal implication requirement and record the direct-delete exception; the maintainer must decide whether to refuse or repair it.
- Working assumption: For structural predicates, a triple with surviving timestamps keeps a structural row. A direct delete may remove the explicit assertion, but the row must stay (or revert to marked) while timestamps remain. Model as-built option (a) as the baseline that violates the implication, and keep the ADR-0015 temporal-only opt-out separate (no row ever).
- Working assumption: Engine-path endpoints: derived, with identifiable provenance (e.g. the 'bare temporal endpoint' rule purge already uses) and excluded from genesis/verify; changeset temporal ops: follow the relationship endpoint rule (refuse a missing endpoint or record a stub). Keep their real effects in the environment model; treat ledger-api.md:92 as stale for the indexed path.
- Working assumption: Keep the existing ledger rules for node rows until a source extends the marked-edge exemption to endpoints.

<a id="temporal.structural.mark"></a>
[I · temporal.structural.mark]

An implied structural edge carries the temporal mark, so counts, exports and later cleanup can tell it from an explicitly written edge.
- All timestamps of one triple share one structural edge.
- The mark, not a count of timestamps, decides whether the edge may be removed; the purge itself checks whether any surviving timestamp still holds the triple.

- Working assumption: no. The mark is bookkeeping (spec 252 planned it as a separate column), so Cypher maps and RDF qualifiers would leave it out while the edge and its weight stay visible.

<a id="temporal.structural.mark.readers"></a>
[I · temporal.structural.mark.readers]

Edge readers treat a marked structural edge differently from the same edge written explicitly.
- NDJSON export writes no line for it; the temporal export writes the edge instead.
- RDF export writes the triple plus a reification with a `temporal` qualifier (true) and the weight when it is not 1, so the export report counts 3 more edges and 2 more nodes for it.
- Cypher `properties(r)` and `r.temporal` return `temporal: true`, with the weight.
- After an explicit write adopts the edge, every reader sees an ordinary edge with that write's qualifiers. A bulk create adopts with none.
- The mark is written only when the triple has no row yet: an explicit edge written first is never marked, and a later temporal write never changes the stored weight.

<a id="temporal.structural.adopt"></a>
[I · temporal.structural.adopt]

An explicit structural write of a triple that has a marked structural edge adopts it: the mark is cleared and the explicit write's qualifiers apply.
- Single and bulk edge creation, a Cypher `CREATE` or `MERGE` between matched nodes, and a ledger relationship create all adopt.
- After adoption, no temporal delete or purge removes the edge.
- An adopting `create_edge` reports True, unlike writing an existing unmarked edge again, which reports False.
- An explicit edge written before any temporal edge is never marked.
- Observed exception in Python `create_edge` and `store_edge`: caller qualifiers can supply `temporal=True`. A new row then keeps the mark; an adopting `create_edge` also keeps it when supplied again, and repeated marked creates report True and replace qualifiers. This conflicts with the unmarked explicit-edge rule above.

<a id="temporal.structural.end"></a>
[I · temporal.structural.end]

When a triple's last timestamp in a graph goes, by a delete or a purge, that graph's structural edge for the triple goes too while it still carries the mark.
- The rule is the same in the default graph and in every named graph.
- An unmarked structural edge stays.
- Endpoint nodes stay unless the purge is asked to [retire bare nodes](../features/temporal.g5.md#temporal.purge.bare-nodes).

<a id="temporal.structural.upgrade"></a>
[D · temporal.structural.upgrade]

When an install declares the adjacency index, every triple with temporal edges and no structural edge gets a marked one, except triples of temporal-only predicates.
- The upgrade never deletes rows and never registers predicates.
- It remembers a bounded number of triples and re-checks the ones it forgot, so it never misses a row.
- A row already there is left as it is, so an explicit edge stays unmarked. Running it again writes nothing.
- The SQL function `backfill_temporal_rows()` runs it for every graph and refuses a caller without INSERT on `nodes` and `rdf_edges`, writing nothing. Setup runs it before declaring the edge index and reports the edges it gave rows as `temporal_rows_backfilled`.
- Today the count it answers, and setup reports, is every structural temporal triple it walked, whether or not the triple needed a row: a second run answers the same number again ([finding](../../Verus_verification/bugs_issues.md#bug-tmp-107)).

<a id="temporal.structural.ledger"></a>
[D · temporal.structural.ledger]

A marked structural edge is derived from the time index, so it is outside ledger governance. Direct temporal writes create no revisions ([inside a changeset they do](../features/temporal.g5.md#temporal.ledger)), and the ledger's starting snapshot and its verification both skip marked edges.
- Ledger strict mode does not change this: a temporal write still succeeds, and with the adjacency index declared it still writes the marked structural edge.
- Strict mode skips only the engine's older client-side structural step, which runs when the adjacency index is not declared.

## Metadata

### structure.multigraph.layout

- Sources: [spec 234 clarifications and FR-004 to FR-006](../../../specs/234-multigraph-parallel-edges/spec.md#L44-L47), [Adjacency.PutKeyed / RemoveKeyed](../../../iris_src/src/Graph/KG/Adjacency.cls#L197-L321), [spec 252 FR-003](../../../specs/252-adjacency-functional-index/spec.md#L109-L110)
- Expands: [multigraph mode](../features/graph-structure.g5.md#structure.multigraph)
- agent
- architecture-decision, data-integrity
- test-coverage
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `lemma_create`, `lemma_second`

Key allocation and the retry come from [spec 234 FR-007 and edge cases](../../../specs/234-multigraph-parallel-edges/spec.md#L185-L190) and the [key entity](../../../specs/234-multigraph-parallel-edges/spec.md#L329-L331); Cypher allocates the key in [its keyed inserts](../../../iris_vector_graph/cypher/translator.py#L10368-L10386). Observed divergence: no retry after a key clash was found, so the losing writer's statement fails with a uniqueness error. Live coverage: [one to three edges and back, and rebuild equals 200 random keyed writes](../../../tests/e2e/test_234_multigraph_storage_e2e.py). Observed divergence, suspected: concurrent writers or parallel rebuild jobs on one triple can lose an edge from the count or leave an entry with no row, and a ledger reweight can set the triple's weight from an edge that is not the lowest ([stage-A notes, F4 and F11](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [Deleting one of several parallel edges through the ledger removes the adjacency of the edges that remain](../../Verus_verification/bugs_issues.md#bug-str-001); [Concurrent writers of one multigraph triple can lose its multiplicity or leave a ghost edge entry](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-006); [A ledger qualifier update reweights a multigraph triple's leaf to an edge that is not the lowest](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-012)

Iteration9 finite source/native qualification: the actual RowPut callback checks the GraphMode flag, not the graph name or existence of parallel SQL rows. In the retained mode-off fixture, ekey0/weight10 then ekey5/weight1 leaves bare out/in1 with no keyed children; a lowest-key expectation there was withdrawn. With mode enabled before writes, the same rows leave scalar10 and children0=10,5=1,#=2. [Native points and retained mismatch review](../../uplift/consolidated/iteration-9/weighted-projection-review.md). This corroborates the existing mode-off admission boundary and the completed mode-on fragment, without proving concurrent/index/writer histories.

Audit reproduction: [bug-str-001](../../Verus_verification/bugs_issues.md#bug-str-001) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

### structure.adjacency

- uncertain
- Sources: [CONTEXT.md, Adjacency Index](../../../CONTEXT.md#L88-L95), [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md), [Graph.KG.Adjacency](../../../iris_src/src/Graph/KG/Adjacency.cls)
- Children: [declared](#structure.adjacency.declared), [not declared](#structure.adjacency.undeclared), [one writer](#structure.adjacency.one_writer), [bulk loads](#structure.adjacency.bulk), [SQL scans](#structure.adjacency.scan), [declaration](#structure.adjacency.declare)
- agent
- architecture-decision
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) `theorem_other_graph_edges_invisible` (as built, iteration 57)
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `theorem_nkg_held_elsewhere`, `theorem_mark_graph_gone`

Open questions: [May two adjacency rebuilds run at the same time?](../../Verus_verification/open_questions.md#HD-0402)

### structure.adjacency.declared

- Sources: [CONTEXT.md, Adjacency Index](../../../CONTEXT.md#L88-L95), [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L12-L16), [spec 252 FR-001, FR-002, FR-016](../../../specs/252-adjacency-functional-index/spec.md#L106-L133), [AdjIndex](../../../iris_src/src/Graph/KG/AdjIndex.cls), [LabelIndex](../../../iris_src/src/Graph/KG/LabelIndex.cls)
- Expands: [adjacency index](#structure.adjacency)
- agent
- data-integrity
- test-coverage

Live coverage: [every writer path leaves the index equal to a recount](../../../tests/e2e/test_252_writer_paths_e2e.py). Shipped in 4.3.0. Observed divergence, suspected: the database ignores an error status from the index callbacks, and the multigraph writers turn their errors into such statuses, so a row can commit without its entry ([stage-A notes, F10](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [Node interning runs inside the functional-index callback, which ADR-0008 rules out](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-010); [The keyed adjacency writers turn errors into statuses that IRIS ignores, so a row can commit without its entry](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-011)

### structure.adjacency.undeclared

- Sources: [CONTEXT.md, Adjacency Index](../../../CONTEXT.md#L88-L95), [ADMIN_GUIDE, the adjacency indexes](../../../docs/ADMIN_GUIDE.md#L1032-L1037), [create_edge without the index](../../../iris_vector_graph/_engine/nodes_edges.py#L1221-L1249)
- Expands: [adjacency index](#structure.adjacency)
- agent
- operations

In such a namespace the engine writes the index over a separate connection, so a rolled-back edge can leave its entry behind until a rebuild; the engine's error message says so.

Findings: [Without the adjacency index, edge writers write adjacency on a second connection that commits separately from the row](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-015)


Review round 3 R3-reader M20: the engine's compensating writes call IVG's `EdgeScan` class, so they need IVG's classes; Cypher writes, `store_edge` and the store's `write_edges` make no compensating call (code reading: no `EdgeScan` call in `_engine/query.py` or `stores/iris_sql_store.py`).

### structure.adjacency.one_writer

- Sources: [ADR-0011](../../../docs/adr/0011-the-adjacency-index-has-one-writer-module.md), [Graph.KG.Adjacency header](../../../iris_src/src/Graph/KG/Adjacency.cls#L1-L47)
- Expands: [adjacency index](#structure.adjacency)
- agent
- architecture-decision
- test-coverage

Coverage is a source scan of the ObjectScript classes: [single-writer guard](../../../tests/unit/test_adjacency_single_writer.py). ADR-0011 amends ADR-0001's list of classes that may touch the index directly. The rule covers out-edge and in-edge entries; label entries are outside it. Observed divergence: a snapshot restore into a namespace without the declared index writes these entries from Python, outside the module and the scan. FHIR sync writes label entries directly ([FHIRGraph](../../../iris_src/src/Graph/KG/FHIRGraph.cls#L2552-L2568)).

### structure.adjacency.bulk

- Sources: [ADR-0008, bulk loads and consequences](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L38-L39), [spec 252 FR-008](../../../specs/252-adjacency-functional-index/spec.md#L119), [engine bulk paths rebuild in finally](../../../iris_vector_graph/_engine/nodes_edges.py#L1866-L1871), [rebuild failures only warn](../../../iris_vector_graph/_engine/nodes_edges.py#L67-L79), [the bulk loader](../../../iris_vector_graph/bulk_loader.py#L1-L22), [loader rebuilds only after a full load](../../../iris_vector_graph/bulk_loader.py#L578-L603)
- Evidence: [bulk_load_session predictions and observations](../../uplift/consolidated/iteration-35/bulk-session-PAIRS.md) (observed natively; no formal contract)
- Expands: [adjacency index](#structure.adjacency)
- agent
- data-integrity, operations

Rewritten after the stage-A reconstruction check (gap G7, G34 and section 3 item 16). FR-008 covers every bulk path that writes `%NOINDEX`, the bulk loader included, so the reviewer's proposal to limit it to the engine's paths was not applied. "No duplicate rows" means none within the load and none against rows already present, because a `%NOINDEX` insert also skips the unique key (ADR-0008 consequences). Observed divergence: the engine paths rebuild in a `finally`, but an index that does not come back is only logged; the bulk loader uses `%NOCHECK`, commits per batch, and rebuilds only after both its node and edge phases succeed, so a failed phase leaves committed rows unindexed until a manual rebuild.

Findings: [A failed indexed rebuild, or a failed rebuild after a bulk load, leaves a partial adjacency index](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-009), [BulkLoader's node and edge loads write without indexes and return before rebuilding them](../../Verus_verification/bugs_issues.md#bug-plt-027)

### structure.adjacency.scan

- Sources: [SqlProcs MatchEdges and MatchEdgesAllGraphs](../../../iris_src/src/Graph/KG/SqlProcs.cls#L145-L155), [EdgeScan header and scans](../../../iris_src/src/Graph/KG/EdgeScan.cls#L1-L145), [the IVG_EDGESCAN hop](../../../iris_vector_graph/cypher/translator.py#L16467-L16530), [a scan alias's property is NULL](../../../iris_vector_graph/cypher/translator.py#L22266-L22273), [ADMIN_GUIDE, global readers check SELECT](../../../docs/ADMIN_GUIDE.md#L566-L576), [ADMIN_GUIDE, IVG_EDGESCAN](../../../docs/ADMIN_GUIDE.md#L1248), [CHANGELOG, '' as every predicate (R269)](../../../CHANGELOG.md#L1499)
- Formal: [sql_procs](../../Verus_verification/models/sql_procs/sql_procs.rs) `match_edges`, `match_all`, `theorem_empty_predicate_every_predicate`, `theorem_shard_ignored`, `theorem_graph_scoped_vs_all`, `theorem_edgescan_reads_null_property`, `graph_arg_key`, `theorem_default_graph_spellings` (iteration 56), `match_edges_sql`, `theorem_column_only_select_refused`, `theorem_table_schema_role_select_pass` (iteration 56)
- Evidence: [frozen predictions](../../uplift/consolidated/iteration-53/sqlprocs-PAIRS.md) ME1-ME5, [probe](../../uplift/consolidated/iteration-53/sqlprocs/sqlprocs-observed-20261117T050743Z.json), [binding](../../Verus_verification/results/sql_procs/20261117T051429Z-binding/receipt.json); iteration 56: binding cases `me_spell_*` (eight spellings of the graph argument) and `priv_i56q_*` (users with recorded grants), [sql_procs results](../../Verus_verification/results/sql_procs)
- Expands: [adjacency index](#structure.adjacency)
- agent
- architecture-decision
- design-verified

Iteration 53. The rule that the `IVG_EDGESCAN` plan answers what the default plan answers comes from the docs calling it only "the plan before 4.3.0" and from CHANGELOG 4.3.0 ("every answer equal"). Premise: the adjacency index is declared, so the scan and the rows hold the same edges. Not observed: parallel edges of a multigraph through the scan.

Findings: [With IVG_EDGESCAN=1 a relationship property on a hop reads null](../../Verus_verification/bugs_issues.md#bug-cyp-133)

### structure.adjacency.declare

- design-verified
- Sources: [spec 252](../../../specs/252-adjacency-functional-index/spec.md), [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L40-L41), [ADR-0009](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md); [`iris_vector_graph/schema.py::GraphSchema.ensure_adjacency_index`](../../../iris_vector_graph/schema.py#L821-L898) (prerequisites `:831-860`; per index `:863-897`; backfill before the edge index `:879-884`), [`::GraphSchema.adjacency_index_kind`](../../../iris_vector_graph/schema.py#L785-L818), called last by [`::GraphSchema.ensure_indexes`](../../../iris_vector_graph/schema.py#L600-L731) (`:726`); [`iris_src/src/Graph/KG/TemporalIndex.cls`](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L226-L235) (the backfill); unit tests [test_252_index_declaration.py](../../../tests/unit/test_252_index_declaration.py#L52-L135)
- Playbook: [ADJ-B2.9](../../../experiment/playbook-completion/ontology/04-adjacency.md#L98), [TMP-B11.3](../../../experiment/playbook-completion/ontology/05-temporal.md#L301)
- Verus: see [index_declaration](../../Verus_verification/models/index_declaration/NOTES.md) (`theorem_no_prereq_no_ddl`, `theorem_prereqs_declare_both`, `theorem_declared_left_alone`, `theorem_backfill_before_edge_index`; as-built; controls `skip-ekey-check`, `backfill-after-build`, `redeclare-functional`)
- Expands: [adjacency index](#structure.adjacency)
- agent
- architecture-decision, operations

Public cases M16 and J07. The playbook's `TMP-B11.3` sits in its temporal module, which is why the baseline found no canonical owner for the backfill order.

State machines: [index declaration](../../Verus_verification/models/index_declaration/manifest.json)

### structure.degree.cache

- uncertain
- Sources: [ADR-0012](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md), [Adj.Degree](../../../iris_src/src/Graph/KG/Adj.cls#L28-L89), [changelog 4.3.0](../../../CHANGELOG.md#L2952-L2958)
- Expands: [degree](../features/graph-structure.g5.md#structure.degree)
- Children: [no rolled-back edges](#structure.degree.cache.uncommitted), [erase](#structure.degree.cache.erase), [warm after a rebuild](#structure.degree.cache.warm)
- agent
- architecture-decision
- test-coverage

Live coverage: [the generation-validated degree cache](../../../tests/e2e/test_degree_cache_live.py). ADR-0012 refines ADR-0010: the count is still never maintained incrementally, only cached. Observed: a second serving path, a whole-graph stamp, lets bulk readers use cached counts without reading generations and treat a missing entry as zero while nothing has written since a full fill.

Findings: [A degree cached before a node is deleted and re-created can be served afterwards as current](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-003); [Drawing degree generations from the version token is not a repair](../../Verus_verification/design_simplification.md#simp-str-005)

Open questions: [How should erase and rebuild retire a source generation?](../../Verus_verification/open_questions.md#HD-0401)

### structure.degree.cache.uncommitted

- design-verified
- Sources: [ADR-0012](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md#L10-L27), [Adjacency.WriterLock](../../../iris_src/src/Graph/KG/Adjacency.cls#L51-L73), [changelog 4.7.0 adjacency lock](../../../CHANGELOG.md#L174-L178)
- Playbook: [ADJ-I5.8](../../../experiment/playbook-completion/ontology/04-adjacency.md#L222), [ADJ-I5.9](../../../experiment/playbook-completion/ontology/04-adjacency.md#L223)
- Verus: active (public M10): `G-graph_structure` (as-built) [`graph_structure.rs`](../../Verus_verification/models/graph_structure/graph_structure.rs) `theorem_as_built_cache_sound` with witnesses `witness_aba_delete_and_recreate_serves_stale_degree`, `witness_gen0_erase_alone_serves_stale_degree` and repaired `theorem_repaired_cache_sound`. Overlapping: the playbook's `proofs-pa3` `adj_l2` (reviewed design; controls `control_fc0401_write_before_gen`, `control_hd0401_erase_kills_gen`).
- Expands: [degree cache](#structure.degree.cache)
- agent
- data-integrity

Live coverage: [rollback race over two connections](../../../tests/e2e/test_degree_cache_live.py). The lock details answer reconstruction gap G26: the lock is per graph, held shared by writers until commit or rollback, probed exclusively without waiting by readers ([Adj.Degree](../../../iris_src/src/Graph/KG/Adj.cls#L63-L80)). Superseded in part: ADR-0012 and the degree-cache spec said a writer that cannot lock writes nothing; 4.7.0 changed that so the row and its entry are written, and caching stops for the graph instead. No ADR records the change.

Findings: [ADR-0012 does not mention the lockless-writer fallback that 4.7.0 added](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-008)

State machines: [graph structure](../../Verus_verification/models/graph_structure/manifest.json)

### structure.degree.cache.erase

- Sources: [degree-cache spec, erase edge case](../../../specs/248-alt-parity-os/spec.md#L76-L77), [Adjacency.RemoveSource](../../../iris_src/src/Graph/KG/Adjacency.cls#L344-L391), [Adj.Degree post-store check](../../../iris_src/src/Graph/KG/Adj.cls#L46-L49)
- Expands: [degree cache](#structure.degree.cache)
- agent
- data-integrity
- test-coverage

Live coverage: [erase clears generations and cached degrees](../../../tests/e2e/test_degree_cache_live.py). The spec claims a recheck after storing closes the erase window. Observed divergence, suspected: a reader whose recount spans an erase and enough rewrites to bring the generation back to its starting value passes both checks and stores an old count ([stage-A notes, F2](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [A degree cached before a node is deleted and re-created can be served afterwards as current](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-003)

### structure.degree.cache.warm

- design-verified
- Playbook: [ADJ-B5.17](../../../experiment/playbook-completion/ontology/04-adjacency.md#L235), [ADJ-B5.17.2](../../../experiment/playbook-completion/ontology/04-adjacency.md#L241), [ADJ-B5.17.4](../../../experiment/playbook-completion/ontology/04-adjacency.md#L243)
- Verus: [warm_sources](../../Verus_verification/models/warm_sources/NOTES.md), as-built source fill/count and stamp contracts with failed-probe, token-motion and generation-motion controls. ObjectScript binding is inspected only; source enumeration completeness during concurrent changes remains an environment premise.
- Sources: [ADR-0012 consequences](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md#L29-L35), [Adjacency.EndRebuild](../../../iris_src/src/Graph/KG/Adjacency.cls#L857-L869), [Adj.WarmAll](../../../iris_src/src/Graph/KG/Adj.cls#L177-L205)
- Expands: [degree cache](#structure.degree.cache)
- agent
- operations

Live coverage: [a rebuild leaves the cache warm](../../../tests/e2e/test_degree_cache_live.py). Observed: the rebuild advances the graph-version token right after filling the cache, which voids the whole-graph stamp it has just set; the per-node entries stay valid ([stage-A notes, S5](../../uplift/ivg-verus-initial/intent/graph-structure.md#design-simplifications-p)).

Findings: [Bump the version token before ending a rebuild so the warm stamp survives it](../../Verus_verification/design_simplification.md#simp-str-003)

State machines: [warm sources](../../Verus_verification/models/warm_sources/manifest.json)

### structure.rebuilt

- uncertain
- Sources: [CONTEXT.md, Rebuilt store](../../../CONTEXT.md#L109-L114), [ADR-0008 decision](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L23-L26), [freshness module](../../../iris_vector_graph/freshness.py), [two-hop stamps](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L939-L992)
- Children: [token](#structure.rebuilt.token), [stamp](#structure.rebuilt.stamp), [valid results](#structure.rebuilt.valid), [When a computation sees a write that is not yet committed and that write later rolls back, must the cached result be thrown away?](../../Verus_verification/open_questions.md#structure.rebuilt.rollback), [stale snapshot reads](#structure.rebuilt.stale_read)
- agent
- architecture-decision, data-integrity

The interned snapshot's graph scope is stated in [graph scope](../concepts/graph-scope.g5.md#graph.unscoped_snapshot). Observed divergence: the interned snapshot decides freshness with its own stale flag and a per-process flag rather than a token stamp, and every edge write also updates it in place. The freshness module is imported nowhere.

Open questions: [When a computation sees a write that is not yet committed and that write later rolls back, must the cached result be thrown away?](../../Verus_verification/open_questions.md#structure.rebuilt.rollback)

### structure.rebuilt.token

- Sources: [CONTEXT.md, Graph-Version Token](../../../CONTEXT.md#L116-L119), [token audit](../../../specs/236-arno-callout-adoption/research-token-audit.md#L15-L40), [label writes raise it](../../../iris_src/src/Graph/KG/Adjacency.cls#L767-L787), [restore raises the token](../../../iris_vector_graph/_engine/snapshot.py#L48-L58), [algorithm cache admission](../../../iris_vector_graph/algo_cache.py#L15-L17)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- data-integrity
- test-coverage

Live coverage: [every write path moves the token](../../../tests/integration/test_236_token_write_paths.py). Restated after the stage-A reconstruction check (gap G5, section 3 item 12). CONTEXT.md words it as "every write path able to change what an algorithm answers". The token audit narrows the token to every change of the adjacency index and has the cache admit only answers that depend on nothing else: PageRank, PPR, WCC and CDLP, with PageRank also keyed on the node set. The [algorithm cache](algorithm-execution.g5.md#algorithms.cache.token) owns that admission rule. The reviewer's claim that label writes do not move the token was not applied: since the label index (4.3.0), every label row change raises it. The comment in `algo_cache.py` that no token moves for labels predates that. Observed: while a restore is running, the token can briefly hold a value read from the archive before it is raised past both. Observed divergence (review round 2, code reading only): without the declared adjacency index, a temporal write to a triple that already has an adjacency entry rewrites its stored weight without moving the token ([Adjacency.cls](../../../iris_src/src/Graph/KG/Adjacency.cls#L128-L136)); a token-validated cache could serve the old weight. The algorithm cache admits only PageRank, PPR, WCC and CDLP, which ignore weights, so it is unaffected; whether any `^ArnoKG` reader uses weights is not traced (the Arno library is not in this repository). Suspected, non-indexed installs only, not run.

Findings: [Without the adjacency index, a temporal write to an existing triple changes its stored weight without moving the version token](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-016)

### structure.rebuilt.stamp

- design-verified
- Sources: [CONTEXT.md, Rebuilt store](../../../CONTEXT.md#L109-L114), [spec 244 freshness](../../../specs/244-alt-freshness-module/spec.md#L70-L74); [`iris_vector_graph/freshness.py::Freshness._read_int`](../../../iris_vector_graph/freshness.py#L45-L52), [`::Freshness.token`](../../../iris_vector_graph/freshness.py#L54-L57), [`::Freshness.built_from`](../../../iris_vector_graph/freshness.py#L66-L68), [`::Freshness.is_current`](../../../iris_vector_graph/freshness.py#L70-L72), [`::Freshness.stale_stores`](../../../iris_vector_graph/freshness.py#L74-L77); [`iris_src/src/Graph/KG/TraversalKHop.cls::Fresh`](../../../iris_src/src/Graph/KG/TraversalKHop.cls#L237-L243); unit tests [test_freshness.py](../../../tests/unit/test_freshness.py)
- Playbook: [ADJ-B7](../../../experiment/playbook-completion/ontology/04-adjacency.md#L255), [ADJ-B7.1](../../../experiment/playbook-completion/ontology/04-adjacency.md#L256)
- Verus: see [freshness_stamp](../../Verus_verification/models/freshness_stamp/NOTES.md) (`theorem_is_current_iff_stamped_equal`, `theorem_unstamped_stale_at_zero`, `theorem_stamped_zero_current`; as-built; control `unset-stamp-reads-zero`)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- data-integrity
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `theorem_two_hop`, `witness_fast_overcounts`, `theorem_write_makes_stale`; findings: [bug-str-117](../../Verus_verification/bugs_issues.md#bug-str-117)

Public case M09. The Python `Freshness` class has no caller inside the product package (no module imports `iris_vector_graph.freshness`); the reader that decides freshness at run time is `TraversalKHop.Fresh` for the two-hop counts. Both are bound: the Python class by an enumerated comparison against the model's twin, the ObjectScript method by inspection only.

State machines: [freshness stamp](../../Verus_verification/models/freshness_stamp/manifest.json)

### structure.rebuilt.valid

- Sources: [CONTEXT.md, Graph-Version Token](../../../CONTEXT.md#L116-L119), [AlgoCache](../../../iris_src/src/Graph/KG/AlgoCache.cls#L1-L51), [the store's cache path](../../../iris_vector_graph/stores/iris_sql_store.py#L921-L987)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- data-integrity
- test-coverage

Live coverage: [every write path moves the token](../../../tests/integration/test_236_token_write_paths.py).

Findings: [A cached algorithm answer computed over a write that later rolls back stays current](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-002)

### structure.rebuilt.stale_read

- Sources: [ADMIN_GUIDE, the adjacency indexes](../../../docs/ADMIN_GUIDE.md#L1032-L1062), [EnsureNKG](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L393-L425), [variable-length routing](../../../iris_vector_graph/_engine/query.py#L2454-L2457), [IndexNotSyncedError](../../../iris_vector_graph/errors.py#L78-L88)
- Expands: [rebuilt stores](#structure.rebuilt)
- agent
- user-facing-behavior, data-integrity

Added after the stage-A reconstruction check (gap G40). Observed divergence: the snapshot counts as stale for these readers only when an erasure marked it, or when this engine process itself made a bulk write; it does not compare a token stamp. So another process's bulk write leaves a variable-length query answering from the old snapshot until a rebuild.

### temporal.owner

- Sources: [ADR-0002](../../../docs/adr/0002-temporal-globals-are-not-directly-accessible.md), [spec 239 FR-001](../../../specs/239-alt-temporal-erase/spec.md#L70-L71), [writer guard](../../../tests/unit/test_temporal_single_owner.py)
- agent
- architecture-decision

Observed divergence: the paged window reader reads the temporal stores directly, snapshot restore writes them from Python, and the source-text guard checks writers only.

Findings: [Temporal documentation contradicts the code in several places](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-009)

### temporal.stats.writers

- Sources: [WriteStores, RemoveTemporalRow, RebuildBucketAggregate](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L67-L133), [delete docstring](../../../iris_vector_graph/_engine/temporal.py#L334-L389), [create_edge_temporal docstring](../../../iris_vector_graph/_engine/temporal.py#L246-L333), [USER_GUIDE transactions](../../../docs/USER_GUIDE.md#L236-L275)
- Expands: [Statistics](../features/temporal.g5.md#temporal.stats)
- agent
- data-integrity
- uncertain
- design-verified
- Formal: [`theorem_update_counts_twice`, `theorem_collision_changes_nothing`, `theorem_update_whole_vs_cut`, `theorem_rolled_back_first_write`, `theorem_rolled_back_group_row`, `theorem_committed_first_write`, `theorem_delete_rebuilds_from_survivors`, `theorem_update_then_delete_leaves_velocity`](../../Verus_verification/models/temporal_stats/temporal_stats.rs)
- Open question: [temporal.write.update-statistics](../../Verus_verification/open_questions.md#temporal.write.update-statistics)

Findings: [bug-tmp-002](../../Verus_verification/bugs_issues.md#bug-tmp-002), [bug-tmp-003](../../Verus_verification/bugs_issues.md#bug-tmp-003) (both strengthened in iteration 51). The rollback rule rests on the observed premise that IRIS does not undo `$Increment` (P-INCR).

State machines: [temporal statistics](../../Verus_verification/models/temporal_stats/manifest.json)

### temporal.structural

- uncertain
- Sources: [ADR-0009](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L9-L29), [glossary](../../../CONTEXT.md#L65-L76), [spec 252 FR-014](../../../specs/252-adjacency-functional-index/spec.md#L127-L129), [AssertTemporalRow](../../../iris_src/src/Graph/KG/Adjacency.cls#L560-L618); live tests: [temporal rows](../../../tests/e2e/test_252_temporal_rows_e2e.py)
- Children: [mark](#temporal.structural.mark), [mark readers](#temporal.structural.mark.readers), [adopt](#temporal.structural.adopt), [end](#temporal.structural.end), [upgrade](#temporal.structural.upgrade), [ledger](#temporal.structural.ledger), [Are the endpoint nodes that a temporal write creates, or that a purge retires, governed by the ledger?](../../Verus_verification/open_questions.md#temporal.structural.ledger-nodes), [May an explicit delete_edge remove a marked structural row while its triple still has timestamps?](../../Verus_verification/open_questions.md#q-tmp-006)
- agent
- architecture-decision, user-facing-behavior
- test-coverage

Findings: [A temporal write whose structural step fails keeps its raw entry, cannot be finished by a retry, and the bulk fallback reports it written](../../Verus_verification/bugs_issues.md#bug-tmp-001); [A temporal write that races a purge or delete of the same triple can leave a live timestamp with no structural edge](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-011); [Remove the unadopted spec-246 Python path for temporal structural rows](../../Verus_verification/design_simplification.md#simp-tmp-001)


The non-indexed mirror is [temporal.py](../../../iris_vector_graph/_engine/temporal.py#L304-L331): with a graph named, no declared index and no spec-246 flag, it inserts endpoint nodes and an unmarked `rdf_edges` row without reading the temporal-only registry (review round 3 R3-reader M17).

Audit reproduction: [bug-tmp-001](../../Verus_verification/bugs_issues.md#bug-tmp-001) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Open questions: [May a direct edge delete remove an edge row that a temporal edge still implies?](../../Verus_verification/open_questions.md#HD-0302), [Are the end nodes a temporal write creates governed by the ledger?](../../Verus_verification/open_questions.md#HD-0501), [May an explicit delete_edge remove a marked structural row while its triple still has timestamps?](../../Verus_verification/open_questions.md#q-tmp-006), [Are the endpoint nodes that a temporal write creates, or that a purge retires, governed by the ledger?](../../Verus_verification/open_questions.md#temporal.structural.ledger-nodes)

### temporal.structural.mark

- uncertain
- Sources: [ADR-0009](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L9-L42), [spec 254 plan, Decision 1](../../../specs/254-temporal-purge-collisions-rebuild/plan.md#L5-L26); live tests: [temporal rows](../../../tests/e2e/test_252_temporal_rows_e2e.py)
- Expands: [Implied structural edge](#temporal.structural)
- agent
- data-integrity, architecture-decision
- test-coverage

The plan chose the mark over a count because a counter is not undone by a rollback, needs a new store and needs a migration. The upgrade backfill gives an edge the weight of its earliest timestamp, while live writes keep the first-written weight.

Findings: [May an explicit delete_edge remove a marked structural row while its triple still has timestamps?](../../Verus_verification/open_questions.md#q-tmp-006); [A temporal edge's internal mark is returned as relationship data by Cypher and written as an RDF qualifier](../../Verus_verification/bugs_issues.md#bug-tmp-101)

Open questions: [Should readers show the temporal mark as part of the edge's data?](../../Verus_verification/open_questions.md#temporal.structural.mark.visibility)

### temporal.structural.mark.readers

- design-verified
- Sources: [AssertTemporalRow](../../../iris_src/src/Graph/KG/Adjacency.cls#L575-L618), [export_graph_ndjson](../../../iris_vector_graph/_engine/snapshot.py#L1857-L1908), [RDF qualifier loop](../../../iris_vector_graph/_engine/_rdf_utils.py#L264-L284), [Cypher relationship map](../../../iris_vector_graph/cypher/translator.py#L23187-L23191), [create_edge adoption](../../../iris_vector_graph/_engine/nodes_edges.py#L1275-L1304), [bulk adoption](../../../iris_vector_graph/_engine/nodes_edges.py#L1990-L2001), [changelog: a temporal edge is visible structurally](../../../CHANGELOG.md#L3042-L3047)
- Expands: [the mark](#temporal.structural.mark)
- Verus: [temporal_marker.rs](../../Verus_verification/models/temporal_marker/temporal_marker.rs) `theorem_marker_decodes`, `theorem_temporal_never_rewrites_a_row`, `theorem_explicit_adopts_marked_with_own`, `theorem_bulk_adopts_marked_to_null`, `theorem_ndjson_omits_marked_includes_adopted`, `theorem_cypher_reports_marker_key`, `theorem_rdf_marked_row_is_reified` and `theorem_rdf_report_counts`; [scope](../../Verus_verification/models/temporal_marker/NOTES.md)
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-15/temporal-marker-PAIRS.md)
- agent
- user-facing-behavior, data-integrity

As-built reader behavior, observed on IRIS 2026.1 with the unchanged product for default-graph triples with one row each; a named-graph probe gave the same export results.

Findings: [A temporal edge's internal mark is returned as relationship data by Cypher and written as an RDF qualifier](../../Verus_verification/bugs_issues.md#bug-tmp-101)

State machines: [temporal marker](../../Verus_verification/models/temporal_marker/manifest.json)

### temporal.structural.adopt

- design-verified
- Sources: [ADR-0009](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L9-L14), [spec 254 sign-off](../../../specs/254-temporal-purge-collisions-rebuild/tasks.md#L72-L80), [create_edge adopt](../../../iris_vector_graph/_engine/nodes_edges.py#L1275-L1300), [ledger adopt](../../../iris_src/src/Graph/KG/LedgerApply.cls#L465-L475); live tests: [purge path matrix](../../../tests/e2e/test_254_purge_e2e.py), [ledger adopt](../../../tests/integration/test_ledger_us11_temporal_coexist.py)
- Expands: [Implied structural edge](#temporal.structural)
- Formal contract: [Python marker and adoption cases](../../Verus_verification/models/edge_acceptance/edge_acceptance.rs)
- Findings: [caller-supplied marker](../../Verus_verification/audits/register-20261115/bugs-review.md#F-C0351)
- agent
- data-integrity

Observed divergence: a multigraph `MERGE`, an undirected `MERGE` that matches the reverse row, and a `MERGE` with inline nodes still leave the mark; a bulk create adopts with empty qualifiers.

Audit reproduction: [F-0304](../../Verus_verification/bugs_issues.md#F-0304) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [Storing an edge over a marked edge does not take the edge over](../../Verus_verification/bugs_issues.md#F-0304).

State machines: [edge acceptance](../../Verus_verification/models/edge_acceptance/manifest.json), [temporal marker](../../Verus_verification/models/temporal_marker/manifest.json)

### temporal.structural.end

- Sources: [spec 254 Decisions](../../../specs/254-temporal-purge-collisions-rebuild/spec.md#L142-L149), [ADR-0009 amendment](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L31-L49), [RetractTemporalRow](../../../iris_src/src/Graph/KG/Adjacency.cls#L620-L689); live tests: [purge](../../../tests/e2e/test_254_purge_e2e.py), [temporal rows](../../../tests/e2e/test_252_temporal_rows_e2e.py)
- Expands: [Implied structural edge](#temporal.structural)
- human-verified
- data-integrity
- test-coverage

Observed divergence: a write racing the delete or purge can leave a timestamp without its edge, recorded as open. The ObjectScript whole-index purge (`TemporalIndex.Purge`, which calls the temporal `EraseAll` outside the Eraser) removes every timestamp but leaves marked structural edges.

Findings: [Making a temporal-only predicate structural again before dropping its rows strands marked rows that nothing removes](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-005); [A temporal write inside a purge's range that lands after the purge removed the row leaves a marked row with no timestamp](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-013); [Without the adjacency index, deleting a temporal edge removes the adjacency of an explicit edge on the same triple](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-012)

### temporal.structural.upgrade

- Sources: [ADR-0009](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L9-L14), [ADR-0015 upgrade](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L105-L110), [BackfillWalk](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L226-L302); live tests: [temporal rows](../../../tests/e2e/test_252_temporal_rows_e2e.py), [opt-out](../../../tests/e2e/test_temporal_structural_optout_e2e.py); [SqlProcs.backfilltemporalrows](../../../iris_src/src/Graph/KG/SqlProcs.cls#L194-L198), [AssertTemporalRow](../../../iris_src/src/Graph/KG/Adjacency.cls) (the NOT EXISTS guards), [setup's call and report](../../../iris_vector_graph/schema.py#L878-L884), [ADMIN_GUIDE setup report](../../../docs/ADMIN_GUIDE.md#L413), [ADMIN_GUIDE write privilege](../../../docs/ADMIN_GUIDE.md#L577-L579)
- Formal: [sql_procs](../../Verus_verification/models/sql_procs/sql_procs.rs) `backfill`, `backfill_count`, `theorem_backfill_writes_missing_only`, `theorem_backfill_idempotent_same_count`, `theorem_backfill_count_overstates`, neighbor `theorem_backfill_count_exact_when_all_missing`
- Evidence: [frozen predictions](../../uplift/consolidated/iteration-53/sqlprocs-PAIRS.md) BF1-BF5, [binding](../../Verus_verification/results/sql_procs/20261117T051429Z-binding/receipt.json) `bf_*`
- Expands: [Implied structural edge](#temporal.structural)
- agent
- operations
- test-coverage

Iteration 53: the three new bullets were observed in a fresh namespace (counts 3, 3, 3 and 4 for 3, 3, 3 and 4 structural triples, while 0, 0, 1 and 0 rows were written). Premise: fewer distinct triples per graph than the seen limit, 100,000; past it a triple is walked and counted again.

Findings: [backfill_temporal_rows answers the triples it walked, not the rows it wrote](../../Verus_verification/bugs_issues.md#bug-tmp-107)

### temporal.structural.ledger

- Sources: [glossary](../../../CONTEXT.md#L65-L76), [4.3.0 notes](../../../CHANGELOG.md#L3043-L3047), [replay skip](../../../iris_vector_graph/ledger/replay.py#L610-L622), [genesis skip](../../../iris_src/src/Graph/KG/LedgerGenesis.cls#L38-L45); live tests: [coexistence](../../../tests/integration/test_ledger_us11_temporal_coexist.py), [verify after enable](../../../tests/e2e/test_460_ledger_temporal_edge_e2e.py)
- Expands: [Implied structural edge](#temporal.structural)
- human-verified
- architecture-decision, data-integrity
- test-coverage

Commit 43efd473 records the decision as "Decided with Tom 2026-10-19". Strict mode: [temporal.py](../../../iris_vector_graph/_engine/temporal.py#L304-L309) skips only the client-side step, and the live strict-mode case in the coexistence test writes a marked row with the tables unchanged for verify. Superseded: the [ledger-api](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L83-L93) sentence that strict mode "skips the structural mirror" predates the declared index and now holds only for that client-side step.

Findings: [A temporal write creates endpoint nodes that the ledger never recorded, so verify diverges after the ledger's own temporal operation](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-004)
