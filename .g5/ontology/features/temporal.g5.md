# Temporal edges

Temporal edges record when events happened between nodes. IVG keeps them in a time index per graph, summarizes them in statistics, and normally makes each one visible as an ordinary structural edge too.

## Definitions

- **Temporal edge**: one event or measurement on a source–predicate–target triple at a timestamp, in one graph, with a weight and optional attributes.
- **Triple**: a source, predicate and target, without a timestamp. Many temporal edges can share one triple.
- **Coordinates**: the graph, timestamp, source, predicate and target of a temporal edge.
- **Time index**: the per-graph store of temporal edges, their attributes, the statistics and the newest-event index.
- **Bucket**: a five-minute span of event time.
- **Statistics**: for each bucket, source and predicate, the count, sum, minimum and maximum of the weights and an approximate count of distinct targets; plus, for each bucket and source, an event counter used by velocity and burst reads.
- **Newest-event index**: for each source and predicate, the timestamp of its newest temporal edge.
- **Structural edge**: a relationship row in the edge table. Where the adjacency index is declared on that table, the index mirrors each row for traversal, degree and Cypher `MATCH`.
- **Temporal mark**: a flag on a structural edge saying that it exists only because temporal edges imply it.
- **Temporal-only predicate**: a predicate registered in one graph so that its temporal edges imply no structural edge.
- **Raw purge**: removal of temporal edges in a time range for retention.
- **Bare node**: a node with no edge, label, property, document or embedding in its graph.
- **Changeset**: a group of operations committed to the ledger as one revision.

## Temporal edges and writes

<a id="temporal.edge"></a>
[I · temporal.edge]

A temporal edge records when an event happened on a triple in one graph, with a weight and optional attributes.
- The timestamp is event time, not the time of writing; a write with no timestamp is stamped with the current time.
- At most one temporal edge exists at one set of coordinates.
- The unit is set by the entry point: the engine's interface counts seconds, and a millisecond entry point that the engine does not expose counts milliseconds; a bucket is five minutes in either.
- Both entry points use the same per-graph stores, so a caller must keep one unit per graph; IVG cannot detect a mix.
- The single Python API currently violates missing-time stamping: omission and None are sent as epoch zero; [clock resolution](#temporal.edge.clock) also distinguishes normal bulk zero from its fallback.


<a id="temporal.edge.clock"></a>
[D · temporal.edge.clock]

Timestamp normalization and the selected writer determine the stored coordinate,
so fixed-coordinate repeatability requires the same resolved event times.

- Single Python omission, None and explicit zero reach the single writer as text zero and remain epoch zero; a normal bulk zero uses each item's current seconds.
- If the bulk endpoint is unavailable before writing, its single-edge fallback stores that same zero at epoch zero. Explicit positive timestamps retain event time on all three paths.
- Bulk items require a usable timestamp; all items are validated and normalized before the first write, while an empty batch succeeds with count zero.
- Numeric short alias `ts=0` defers to a supplied long `timestamp` alias, while text `ts="0"` keeps zero. A present None long alias can fail conversion where an absent long alias defaults to zero.
- On a duplicate explicit positive timestamp, normal bulk reports a collision and zero writes; fallback counts the successful single call and cannot report the collision. The stored existing event remains unchanged.


<a id="temporal.edge.graph-scope"></a>
[I · temporal.edge.graph-scope]

Every temporal store is kept per graph, and an operation on one graph never reads or changes another graph's temporal data.
- The default graph follows the same rules as a named graph.
- A graph name that cannot be stored safely, such as `"0"` or a name with control characters, is refused before anything is written.


<a id="temporal.owner"></a>
[D · temporal.owner]

Only the time-index component may access the temporal stores; every other component uses its operations, so a change to the stored layout touches one place. A new cross-graph need becomes a new operation on that component.


<a id="temporal.write"></a>
[I · temporal.write]

Writing a temporal edge stores it with its attributes, updates the statistics and the newest-event index, and asserts the [implied structural edge](#temporal.structural) unless the predicate is temporal-only in that graph. Each write runs in one of three modes, which differ only when the coordinates already hold an edge.
- Insert, the default for direct writes, keeps the existing edge and reports a collision.
- Update replaces the existing edge's weight and attributes.
- Skip keeps the existing edge and counts the write as skipped.
- A batch write reports how many edges were written, how many collided and how many were skipped.
- A single-edge write reports success even for a collision; a caller that must know writes a one-edge batch and reads its counts.
- A write can leave out the inbound entry for edges never read by target; inbound reads then cannot see that edge.
- Today a direct write opens no transaction of its own: alone it keeps what it wrote before a failure, and inside a caller's transaction it joins it, but a rollback leaves its statistics counted. When the caller turned the driver's autocommit off and has written nothing yet, its rollback removes the structural edge and its end nodes but keeps the temporal edge. Whether a failed write must leave nothing is [open](../../Verus_verification/open_questions.md#temporal.write.partial-failure).

- Working assumption: Keep first-write-wins and exactness as requirements; concurrent provider behavior is unestablished, not an approved one-writer exemption.
- Working assumption: the statistics keep describing the first write.
- Working assumption: the parts written before the error stay, because a direct write runs no transaction.


<a id="temporal.write.collision"></a>
[I · temporal.write.collision]

An insert at coordinates that already hold an edge changes nothing anywhere, so the first write wins and the statistics never count the second write. This holds whether the earlier write came from an earlier call or from earlier in the same batch.


<a id="temporal.write.repeatable"></a>
[I · temporal.write.repeatable]

Writing the same set of temporal edges into an empty graph, in any batch size, must leave every store identical, so a graph can be rebuilt from its source events.
- The order of writes does not matter either when colliding writes are identical and all timestamps of a triple carry one weight.
- The implied structural edge keeps the weight of the triple's first write.


<a id="temporal.write.retry"></a>
[D · temporal.write.retry]

A Counts error does not undo completed items: the Python store retries every
normalized item through the single writer and reports only accepted fallback calls.

- With a nonzero current clock, an error after a completed zero-timestamp item can leave both its current-time and epoch-zero events while reporting one write. A failure before any item writes leaves only epoch zero.
- A positive explicit timestamp collides at its original coordinate; fallback can report one accepted call while inserting nothing new and reporting no collisions.
- A completed prefix of a mixed zero/positive batch remains when the whole batch is replayed; the failed prefix's counters are discarded. This describes completed item boundaries and successful fallback calls, not a partial effect inside one write or a real transport failure.


## Statistics and the newest event


<a id="temporal.stats"></a>
[I · temporal.stats]

The statistics summarize the temporal edges written to each bucket, so windowed counts, totals and extremes need not read every edge.
- An aggregate read answers exactly the requested window with both ends included.
- Buckets the window holds whole come from the statistics; a bucket the window cuts is read edge by edge.
- The distinct-target count is an estimate with an error of about a quarter.
- A velocity read counts one source's events, over every predicate, in the whole buckets that a recent window touches.
- A burst read lists every source whose velocity over such a window reaches a threshold.

- Working assumption: Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.


<a id="temporal.stats.after-purge"></a>
[D · temporal.stats.after-purge]

A raw purge keeps the statistics, so they go on describing the past after the edges they summarize are gone.
- Statistics are removed separately, by bucket range, and that never touches temporal edges.
- An aggregate read over a bucket cut by both the window and a purge counts none of the purged part.


<a id="temporal.latest"></a>
[D · temporal.latest]

IVG keeps the newest-event index up to date on every write, so a latest read never has to search all of time.
- A latest read returns each requested source's newest temporal edge with its attributes.
- The caller names sources, a source prefix, or neither for every source.
- An optional predicate narrows the edges; an optional cutoff excludes edges at or after it, and an optional look-back ignores edges older than the cutoff minus the look-back.
- Ties at the newest timestamp go to the last predicate and target in index order.
- A source with no qualifying edge is left out, never returned empty.
- A graph written before this index existed answers named sources by searching back through time, and refuses prefix and every-source reads until its index is rebuilt once.


<a id="temporal.latest.exact"></a>
[I · temporal.latest.exact]

The newest-event index must stay exact through every write, single-edge delete, purge, node erasure and graph erasure. Whether that includes overlapping writers is [open](../../Verus_verification/open_questions.md#q-tmp-001).

- Working assumption: Keep first-write-wins and exactness as requirements; concurrent provider behavior is unestablished, not an approved one-writer exemption.


<a id="temporal.delete"></a>
[I · temporal.delete]

Deleting one temporal edge removes it and everything derived from it, and reports when there was nothing to delete.
- The statistics of its bucket are recomputed from the remaining edges, and its event counter goes down by one, except in a bucket a raw purge has cut ([open question](../../Verus_verification/open_questions.md#q-tmp-002)).
- The newest-event index moves back to the newest remaining edge.
- When it was the triple's last timestamp, the structural edge follows [the end of the implication](#temporal.structural.end).

- Working assumption: Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.


## The implied structural edge


<a id="temporal.structural"></a>
[D · temporal.structural]

A temporal edge implies a structural edge for the same triple in the same graph. The triple is then visible to SQL, Cypher `MATCH`, edge counts and traversal while any of its timestamps exist.
- The structural edge comes with both endpoint nodes in that graph.
- [Temporal-only predicates](#temporal.optout) are the exception.
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
- Endpoint nodes stay unless the purge is asked to [retire bare nodes](#temporal.purge.bare-nodes).


<a id="temporal.structural.upgrade"></a>
[D · temporal.structural.upgrade]

When an install declares the adjacency index, every triple with temporal edges and no structural edge gets a marked one, except triples of temporal-only predicates.
- The upgrade never deletes rows and never registers predicates.
- It remembers a bounded number of triples and re-checks the ones it forgot, so it never misses a row.


<a id="temporal.structural.ledger"></a>
[D · temporal.structural.ledger]

A marked structural edge is derived from the time index, so it is outside ledger governance. Direct temporal writes create no revisions ([inside a changeset they do](#temporal.ledger)), and the ledger's starting snapshot and its verification both skip marked edges.
- Ledger strict mode does not change this: a temporal write still succeeds, and with the adjacency index declared it still writes the marked structural edge.
- Strict mode skips only the engine's older client-side structural step, which runs when the adjacency index is not declared.


## Temporal-only predicates


<a id="temporal.optout"></a>
[D · temporal.optout]

A graph can register a predicate as temporal-only, so that its temporal edges imply no structural edge in that graph.
- A predicate is structural until registered.
- A registration covers one graph and one exact predicate name; patterns are not supported.
- The choice is stored, not passed per write, so every writer, the upgrade and the purge give the same answer.
- A registration is configuration, not content: erasing a graph keeps it, erasing everything removes it, and snapshots carry it.

- Working assumption: Treat previous temporal edges as retained until an explicit cleanup or reclassification is authorized.


<a id="temporal.optout.effect"></a>
[I · temporal.optout.effect]

A write of a temporal-only predicate stores only time-index data: no structural edge, no node and no adjacency entry.
- Traversal, degree, edge counts and Cypher `MATCH` over it find nothing.
- An empty structural read that names such a predicate logs one warning that names the reads that do work.
- Window, aggregate, newest-event and temporal Cypher reads keep working.
- An explicit structural create of the triple still writes a normal unmarked edge.


<a id="temporal.optout.toggle"></a>
[D · temporal.optout.toggle]

Changing a registration affects only later writes: existing structural edges stay until dropped, and missing ones stay missing until backfilled.
- Writers are never blocked; writes in flight while a predicate is registered may still add marked edges, which the drop removes.
- Backfilling writes the missing marked edges and their nodes for a predicate made structural again, using its temporal edges as the authority.
- Backfilling refuses a predicate that is still temporal-only, can be repeated safely, and needs the adjacency index declared.


<a id="temporal.optout.drop"></a>
[I · temporal.optout.drop]

Dropping removes the marked structural edges of temporal-only predicates in one graph, and by default the nodes this leaves bare.
- A purge does not look for these edges, even ones written before the predicate was registered; removing them is the drop's job.
- The drop refuses a predicate that is still structural, because new writes would put the edges back.
- It removes only edges that still carry the mark when they are deleted.
- It runs in bounded transactions and can be resumed; a dry run counts and changes nothing.
- It needs the adjacency index declared.

- Working assumption: Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately.


## Window reads


<a id="temporal.window"></a>
[I · temporal.window]

A window read returns the temporal edges whose timestamps fall in a range, both ends included, ordered by timestamp, then source, predicate and target.
- It can return each edge's attributes in the same call.
- It reads a window of any size, page by page.
- A failed read raises an error and never returns a short or empty answer as if it were complete.
- It can filter by one source, a list of sources, a source prefix, a set of predicates and a direction.
- A list returns the union of its sources, each edge once; an empty list returns nothing.
- With a source filter, the cost depends on the sources asked for, not on every source active in the window.
- In the inbound direction the source filter names the target.
- The older one-call reads keep their arguments and output, and raise when a window is too large for one answer (about 35,000 edges).
- A reversed window, whose start is after its end, is empty, not an error.

- Working assumption: Treat a paged read as multiple observations today; a point-in-time promise needs an explicit snapshot/version protocol.


<a id="temporal.window.sources"></a>
[I · temporal.window.sources]

Leaving the source filter out and passing an empty list of sources are different requests. Left out, the read covers every source in the window; an empty list covers none and returns nothing.
- The Python reader sends no `sources` key when the caller passes none, and sends an empty list when the caller passes one.
- The server reads every source only when the request names no source, no list and no prefix. A list that names nothing, or names only empty strings, reads nothing.
- Naming more than one of a source, a list and a prefix is refused before any server call.


<a id="temporal.window.paging"></a>
[D · temporal.window.paging]

Each page is read live from where the last page stopped, so the server holds only a resume point between pages. A reader is closed when the iteration ends or is abandoned; [releasing the reader](#temporal.window.paging.release) says exactly when its server handle is freed.
- An edge removed after a page was read is not returned later.
- Only a page marked done ends the read. An empty page that is not marked done does not end it: the reader asks for the next page.
- The events returned are the rows of every page, in order, up to and including the page marked done.
- A page holds at most the rows asked for (1,000 by default), and stops early once its text nears two million characters.


<a id="temporal.window.paging.release"></a>
[I · temporal.window.paging.release]

The server handle of a paged read is freed exactly once, by whichever comes first: the server's last page, the caller's close, a failed page, the end of a `with` block, or garbage collection.
- A window that fits the first page is answered and freed inside the opening call. That costs one round trip, and no close call follows.
- When a later page comes back marked done, the server has freed the handle itself, so the reader makes no close call either.
- Closing before the end sends one close call. Closing again, or after the last page, sends nothing, and the closed reader returns no more events.
- A failed page raises a temporal window error after one close call has freed the handle. A failed opening call raises at the call, and there is no reader to close.
- On the server, closing a handle that is not open does nothing, and asking for the next page of one raises an error instead of returning an empty page.
- A handle belongs to the process and connection that opened it: another connection cannot page it, and the handle is freed when that process ends.
- Today's server never sends an empty page that is not marked done: a page stops only at its row count, its size limit or the end of the window, and each of the first two holds at least one row.


## Retention and erasure


<a id="temporal.purge"></a>
[I · temporal.purge]

A raw purge removes one graph's temporal edges in a time range, with their attributes and the marked structural edges that only those timestamps held up.
- The range includes its start and excludes its end.
- Statistics and interned label sets stay.
- A triple with timestamps on both sides of the range keeps its structural edge.
- Structural edges go before temporal edges, so a purge that fails part way can be finished by running it again.
- The result reports how many edges were deleted and skipped, and how many nodes were retired when that was asked.
- The legacy whole-store purge acts on the default graph and also removes statistics of buckets before the cutoff's.


<a id="temporal.purge.bare-nodes"></a>
[I · temporal.purge.bare-nodes]

A purge can also delete the endpoint nodes of the structural edges it removed, when they are left bare in that graph.
- Only those endpoints are candidates.
- A node that gains an edge, label or embedding while the purge runs is kept.
- The Python interface does this by default; the ObjectScript interface does it only when asked.
- A separate sweep removes bare nodes that an earlier purge left behind.


<a id="temporal.erase"></a>
[I · temporal.erase]

Erasing a graph removes all of its temporal data, erasing everything removes every graph's, and erasing a node removes its temporal edges at both ends in that graph.
- Node erasure keeps the remaining statistics and the newest-event index exact.
- Erasure of temporal data runs inside the erasure's transaction and changes no other graph.
- Today a prefix erase finds IDs through node rows, so a temporal-only event whose endpoints have no node row is not erased; erasing those IDs explicitly, or the whole graph, removes it.

## Temporal edges in the ledger


<a id="temporal.ledger"></a>
[I · temporal.ledger]

A changeset can include temporal edge writes, which the ledger applies in the same transaction as the changeset's other operations.
- A temporal write in a changeset defaults to update mode, unlike a direct write.
- The revision lists each temporal edge write.
- Direct temporal writes outside a changeset create no revision.

- Working assumption: Keep insert collision as an effect-free accepted temporal call today; ledger record/no-op policy still needs owner choice.
- Working assumption: Unchanged reading: record the changeset temporal op in history (audit, redaction); treat temporal tiers, engine temporal writes, purges and temporal replay as outside the structural replay guarantee; model their real effects, including purges deleting endpoint nodes.


<a id="temporal.ledger.atomic"></a>
[I · temporal.ledger.atomic]

If a changeset fails, none of its temporal writes may remain, statistics included.

## Metadata

### temporal.edge
- Sources: [glossary](../../../CONTEXT.md#L65-L76), [bucket unit](../../../specs/204-temporal-index-gaps/spec.md#L113-L159), [InsertEdge](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L46-L65), [ms index](../../../iris_src/src/Graph/KG/TemporalIndexMS.cls); live tests: [index gaps](../../../tests/integration/test_temporal_index_gaps_e2e.py)
- Children: [graph scope](#temporal.edge.graph-scope)
- agent
- user-facing-behavior
- test-coverage

The Python engine calls only the seconds entry point; the millisecond class shares the same stores. Observed divergence: the single-edge Python write sends 0 for a missing timestamp and the edge is stored at time 0, while the batch path stamps 0 as now (finding F11 in [stage-A notes](../../uplift/ivg-verus-initial/intent/temporal.md)).

Findings: [create_edge_temporal with no timestamp stores the event at time 0](../../Verus_verification/bugs_issues.md#bug-tmp-007)

Audit reproduction: [bug-tmp-007](../../Verus_verification/bugs_issues.md#bug-tmp-007) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [F-0509](../../Verus_verification/bugs_issues.md#F-0509) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [InternLabelSet's canonical form is not valid JSON for some inputs](../../Verus_verification/bugs_issues.md#F-0509).

### temporal.edge.clock

- design-verified
- agent
- user-facing-behavior
- Expands: [Temporal edge](#temporal.edge).
- Formal: [raw timestamp to final reader](../../Verus_verification/models/temporal_clock/temporal_clock.rs), [source roles and scope](../../Verus_verification/models/temporal_clock/NOTES.md).

Evidence: [source-frozen neighboring outcomes](../../uplift/consolidated/iteration-7/timestamp-PAIRS.md), [actual native clock/fallback/window cases](../../uplift/consolidated/iteration-7/timestamp-native.json). Known bug-tmp-007/F-0502 is one missing-time issue; F-0513 separately concerns negative bulk values. The new proof covers default insert and pre-effect refusal, not partial-prefix replay, all native coercions, strict ledger, millisecond entry points or arbitrary clocks.

Audit reproduction: [F-0502](../../Verus_verification/bugs_issues.md#F-0502) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A temporal write with no time lands at epoch 0, not at the current time](../../Verus_verification/bugs_issues.md#F-0502).

State machines: [temporal clock](../../Verus_verification/models/temporal_clock/manifest.json)

### temporal.edge.graph-scope
- Sources: [ADR-0003](../../../docs/adr/0003-two-graph-key-derivations.md), [GraphKey](../../../iris_src/src/Graph/KG/GraphKey.cls), [glossary](../../../CONTEXT.md#L28-L58); live tests: [graph scope](../../../tests/integration/test_223_temporal_graph_scope.py)
- Expands: [Temporal edge](#temporal.edge)
- agent
- data-integrity
- test-coverage

### temporal.owner
- Sources: [ADR-0002](../../../docs/adr/0002-temporal-globals-are-not-directly-accessible.md), [spec 239 FR-001](../../../specs/239-alt-temporal-erase/spec.md#L70-L71), [writer guard](../../../tests/unit/test_temporal_single_owner.py)
- agent
- architecture-decision

Observed divergence: the paged window reader reads the temporal stores directly, snapshot restore writes them from Python, and the source-text guard checks writers only.

Findings: [Temporal documentation contradicts the code in several places](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-009)

### temporal.write

- uncertain
- Sources: [WriteStores and BulkInsertCounts](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L67-L183), [Python writes](../../../iris_vector_graph/_engine/temporal.py#L246-L476), [inbound entry](../../../specs/204-temporal-index-gaps/spec.md#L50-L80), [glossary: Collision](../../../CONTEXT.md#L172-L176), [upsert history](../../../CHANGELOG.md#L4656-L4670); live tests: [collisions](../../../tests/e2e/test_254_collisions_e2e.py), [upsert weight](../../../tests/integration/test_221_upsert_weight_e2e.py)
- Children: [collision](#temporal.write.collision), [What should the statistics say after an update replaces an edge's weight?](../../Verus_verification/open_questions.md#temporal.write.update-statistics), [repeatable](#temporal.write.repeatable), [When a temporal write fails part way, what may it leave behind, and must a retry be able to finish it?](../../Verus_verification/open_questions.md#temporal.write.partial-failure), [Must temporal writes stay exact when several writers touch the same coordinates or triple at once?](../../Verus_verification/open_questions.md#q-tmp-001)
- agent
- user-facing-behavior
- test-coverage

As built (verified [temporal.py](../../../iris_vector_graph/_engine/temporal.py#L289-L332)): a direct write is one server call with no transaction. With the adjacency index declared, the marked structural edge is written inside that call, after the time-index entry and event counter and before the other statistics. Only without the declared index (a named graph) or with the undocumented alternative flag does the engine write the structural edge afterwards as a separate statement. The one-edge-batch advice comes from the [spec 254 plan](../../../specs/254-temporal-purge-collisions-rebuild/plan.md#L52-L62); the missing-timestamp divergence belongs to [Temporal edge](#temporal.edge).

Findings: [A temporal write whose structural step fails keeps its raw entry, cannot be finished by a retry, and the bulk fallback reports it written](../../Verus_verification/bugs_issues.md#bug-tmp-001); [With the driver's autocommit off, rolling back a create_edge_temporal keeps the temporal edge but removes its structural edge and nodes](../../Verus_verification/bugs_issues.md#bug-tmp-102)

Audit reproduction: [bug-tmp-001](../../Verus_verification/bugs_issues.md#bug-tmp-001) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Open questions: [Must temporal writes stay exact when several writers touch the same coordinates or triple at once?](../../Verus_verification/open_questions.md#q-tmp-001), [When a temporal write fails part way, what may it leave behind, and must a retry be able to finish it?](../../Verus_verification/open_questions.md#temporal.write.partial-failure), [What should the statistics say after an update replaces an edge's weight?](../../Verus_verification/open_questions.md#temporal.write.update-statistics)

### temporal.write.collision
- Sources: [spec 254 Decisions](../../../specs/254-temporal-purge-collisions-rebuild/spec.md#L142-L149), [FR-003](../../../specs/254-temporal-purge-collisions-rebuild/spec.md#L124-L126), [glossary: Collision](../../../CONTEXT.md#L172-L176); live tests: [collisions](../../../tests/e2e/test_254_collisions_e2e.py)
- Expands: [Writing](#temporal.write)
- human-verified
- user-facing-behavior, data-integrity
- test-coverage

### temporal.write.repeatable
- Sources: [spec 254 US3 and Decisions](../../../specs/254-temporal-purge-collisions-rebuild/spec.md#L79-L149), [sign-off](../../../specs/254-temporal-purge-collisions-rebuild/tasks.md#L72-L86); live tests: [rebuild](../../../tests/e2e/test_254_rebuild_e2e.py)
- Expands: [Writing](#temporal.write)
- human-verified
- data-integrity, operations
- test-coverage

The live test hashes every store across batch sizes and a shuffled order. Under update mode the statistics depend on how often a coordinate was rewritten.

### temporal.write.retry

- design-verified
- agent
- user-facing-behavior
- data-integrity
- Expands: [When a temporal write fails part way, what may it leave behind, and must a retry be able to finish it?](../../Verus_verification/open_questions.md#temporal.write.partial-failure).
- Formal: [completed-prefix and whole-batch replay](../../Verus_verification/models/retry_replay/retry_replay.rs), [exact producer/writer/reader scope](../../Verus_verification/models/retry_replay/NOTES.md).

Evidence: [retained predictions](../../uplift/consolidated/iteration-8/retry-PAIRS.md), [actual native full-completion then injected reply error](../../uplift/consolidated/iteration-7/posteffect-native.json). Native partial-prefix errors, fallback item failures, upsert/skip, within-write failure and concurrency remain conditional or open. Known bug-tmp-001/F-0502 are strengthened, not newly discovered; no retry repair or owner policy was accepted.

State machines: [retry replay](../../Verus_verification/models/retry_replay/manifest.json)

### temporal.stats

- uncertain
- Sources: [GetAggregate](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L1442-L1491), [exact window](../../../CHANGELOG.md#L1221-L1224), [distinct count](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L627-L686); live tests: [exact window](../../../tests/e2e/test_460_r217_temporal_aggregate_window_e2e.py)
- Children: [after purge](#temporal.stats.after-purge), [After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?](../../Verus_verification/open_questions.md#q-tmp-002)
- agent
- user-facing-behavior
- test-coverage

Velocity and bursts: [docstrings](../../../iris_vector_graph/_engine/temporal.py#L852-L910), [GetVelocity and FindBursts](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L757-L806). Observed divergence: the burst read accepts a predicate and ignores it, while its parameter documentation says it filters; in the millisecond entry point the default "now" is in seconds.

Findings: [An update at an occupied temporal coordinate counts the edge twice in the statistics](../../Verus_verification/bugs_issues.md#bug-tmp-002); [A rolled-back temporal write leaves its statistics counted, so a retry counts the edge twice](../../Verus_verification/bugs_issues.md#bug-tmp-003); [A temporal aggregate read of min, max or avg over an empty window raises ValueError, although the method promises 0.0](../../Verus_verification/bugs_issues.md#bug-tmp-009)

Audit reproduction: [bug-tmp-002](../../Verus_verification/bugs_issues.md#bug-tmp-002) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [bug-tmp-003](../../Verus_verification/bugs_issues.md#bug-tmp-003) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [bug-tmp-009](../../Verus_verification/bugs_issues.md#bug-tmp-009) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [F-0508](../../Verus_verification/bugs_issues.md#F-0508) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [find_burst_nodes accepts a predicate and ignores it](../../Verus_verification/bugs_issues.md#F-0508).

Open questions: [After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?](../../Verus_verification/open_questions.md#q-tmp-002)

### temporal.stats.after-purge
- Sources: [spec 204 US1](../../../specs/204-temporal-index-gaps/spec.md#L20-L48), [ADR-0009 amendment](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L31-L49), [PurgeBucketRange](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L1048-L1066); live tests: [ledger coexistence](../../../tests/integration/test_ledger_us11_temporal_coexist.py)
- Expands: [Statistics](#temporal.stats)
- agent
- operations, data-integrity
- test-coverage

### temporal.latest
- Sources: [spec 255 Decisions](../../../specs/255-temporal-window-reader/spec.md#L162-L168), [US3 and FR-007](../../../specs/255-temporal-window-reader/spec.md#L88-L134), [spec 255 plan](../../../specs/255-temporal-window-reader/plan.md#L41-L52), [Latest](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L291-L443); live tests: [latest per source](../../../tests/e2e/test_255_window_reader_us3_e2e.py)
- Children: [exact](#temporal.latest.exact)
- human-verified
- user-facing-behavior, architecture-decision
- test-coverage

### temporal.latest.exact

- uncertain
- Sources: [spec 255 Decision 1](../../../specs/255-temporal-window-reader/spec.md#L162-L166), [spec 255 plan](../../../specs/255-temporal-window-reader/plan.md#L41-L52), [Relatest](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L498-L578); live tests: [US3](../../../tests/e2e/test_255_window_reader_us3_e2e.py)
- Expands: [Newest event](#temporal.latest)
- human-verified
- data-integrity
- test-coverage

Observed divergence (suspected): unlocked concurrent writes to one source and predicate, or two first writes into an empty graph, can leave the index older than the newest edge, and a latest read then returns an older event. Tests cover one writer at a time.

Spec 255 Decision 1 (Tom, 2026-10-22) chose an index maintained on every write and says "purge and erase maintain `tlast`"; the single-edge delete case is the plan's (review round 3 R3-reader M16, under-claim).

Open questions: [Must temporal writes stay exact when several writers touch the same coordinates or triple at once?](../../Verus_verification/open_questions.md#q-tmp-001)

### temporal.delete

- uncertain
- Sources: [DeleteTemporalEdge](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L304-L360), [Python delete](../../../iris_vector_graph/_engine/temporal.py#L334-L388); live tests: [delete](../../../tests/integration/test_delete_temporal_edge.py)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Findings: [A rolled-back temporal delete or node erase leaves the bucket's event counter decremented](../../Verus_verification/bugs_issues.md#bug-tmp-010)

Audit reproduction: [bug-tmp-010](../../Verus_verification/bugs_issues.md#bug-tmp-010) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Open questions: [After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?](../../Verus_verification/open_questions.md#q-tmp-002)

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
- Sources: [ADR-0009](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L9-L14), [ADR-0015 upgrade](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L105-L110), [BackfillWalk](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L226-L302); live tests: [temporal rows](../../../tests/e2e/test_252_temporal_rows_e2e.py), [opt-out](../../../tests/e2e/test_temporal_structural_optout_e2e.py)
- Expands: [Implied structural edge](#temporal.structural)
- agent
- operations
- test-coverage

### temporal.structural.ledger
- Sources: [glossary](../../../CONTEXT.md#L65-L76), [4.3.0 notes](../../../CHANGELOG.md#L3043-L3047), [replay skip](../../../iris_vector_graph/ledger/replay.py#L610-L622), [genesis skip](../../../iris_src/src/Graph/KG/LedgerGenesis.cls#L38-L45); live tests: [coexistence](../../../tests/integration/test_ledger_us11_temporal_coexist.py), [verify after enable](../../../tests/e2e/test_460_ledger_temporal_edge_e2e.py)
- Expands: [Implied structural edge](#temporal.structural)
- human-verified
- architecture-decision, data-integrity
- test-coverage

Commit 43efd473 records the decision as "Decided with Tom 2026-10-19". Strict mode: [temporal.py](../../../iris_vector_graph/_engine/temporal.py#L304-L309) skips only the client-side step, and the live strict-mode case in the coexistence test writes a marked row with the tables unchanged for verify. Superseded: the [ledger-api](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md#L83-L93) sentence that strict mode "skips the structural mirror" predates the declared index and now holds only for that client-side step.

Findings: [A temporal write creates endpoint nodes that the ledger never recorded, so verify diverges after the ledger's own temporal operation](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-004)

### temporal.optout

- uncertain
- Sources: [ADR-0015 decision](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L10-L30), [options](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L71-L90), [TemporalPolicy](../../../iris_src/src/Graph/KG/TemporalPolicy.cls#L1-L58), [glossary](../../../CONTEXT.md#L78-L81); live tests: [opt-out](../../../tests/e2e/test_temporal_structural_optout_e2e.py)
- Children: [effect](#temporal.optout.effect), [toggle](#temporal.optout.toggle), [drop](#temporal.optout.drop), [What should happen to the marked structural edges of a predicate whose timestamps were purged while it was temporal-only, if it is made structural again before the drop?](../../Verus_verification/open_questions.md#temporal.optout.stranded)
- human-verified
- architecture-decision, operations
- test-coverage

ADR-0015 is "Accepted (2026-10-25, Tom)".

Open questions: [What should happen to the marked structural edges of a predicate whose timestamps were purged while it was temporal-only, if it is made structural again before the drop?](../../Verus_verification/open_questions.md#temporal.optout.stranded)

### temporal.optout.effect
- Sources: [ADR-0015 effects](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L52-L70), [warning decision](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L134-L143), [warning module](../../../iris_vector_graph/_engine/temporal_only_warning.py); live tests: [opt-out](../../../tests/e2e/test_temporal_structural_optout_e2e.py)
- Expands: [Temporal-only predicates](#temporal.optout)
- human-verified
- user-facing-behavior
- test-coverage

Observed divergence: the undocumented engine flag left over from an alternative design, and the Python mirror used without the declared index, write structural rows without reading the registry (finding F9).

Findings: [Two Python temporal paths write structural rows for a temporal-only predicate](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-006)

### temporal.optout.toggle
- Sources: [ADR-0015 API](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L101-L106), [migration and rollback](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L111-L124), [BackfillRows](../../../iris_src/src/Graph/KG/TemporalPolicy.cls#L253-L272); live tests: [opt-out](../../../tests/e2e/test_temporal_structural_optout_e2e.py)
- Expands: [Temporal-only predicates](#temporal.optout)
- human-verified
- operations
- test-coverage

### temporal.optout.drop

- uncertain
- Sources: [ADR-0015 API](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L91-L110), [purge decision](../../../docs/adr/0015-temporal-structural-rows-opt-out.md#L144-L148), [DropRows](../../../iris_src/src/Graph/KG/TemporalPolicy.cls#L104-L228); live tests: [opt-out](../../../tests/e2e/test_temporal_structural_optout_e2e.py)
- Expands: [Temporal-only predicates](#temporal.optout)
- human-verified
- operations, data-integrity
- test-coverage

Observed: a single-edge delete of a triple's last timestamp still removes such an edge, because the delete does not read the registry.

Findings: [Should deleting the last timestamp of a temporal-only predicate keep its old structural row, as a purge does?](../../Verus_verification/open_questions.md#q-tmp-005)

Audit (q-tmp-005): Open owner decision. Working assumption (agent, unratified): Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#q-tmp-005).

Open questions: [Should deleting the last timestamp of a temporal-only predicate keep its old structural row, as a purge does?](../../Verus_verification/open_questions.md#q-tmp-005)

### temporal.window

- uncertain
- Playbook: [TMP-B6.14](../../../experiment/playbook-completion/ontology/05-temporal.md#L220) (reversed window, lifted in the Tier 2 sweep); [TMP-B6.12](../../../experiment/playbook-completion/ontology/05-temporal.md#L218), [TMP-B6.1](../../../experiment/playbook-completion/ontology/05-temporal.md#L202) (already stated here)
- Sources: [spec 255 update and US2](../../../specs/255-temporal-window-reader/spec.md#L15-L87), [FR-001 to FR-009](../../../specs/255-temporal-window-reader/spec.md#L121-L138), [TemporalWindow](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L1-L91); live tests: [US1](../../../tests/e2e/test_255_window_reader_us1_e2e.py), [US2](../../../tests/e2e/test_255_window_reader_us2_e2e.py)
- Children: [sources](#temporal.window.sources), [paging](#temporal.window.paging), [Must a paged temporal window read show one consistent moment while edges are written?](../../Verus_verification/open_questions.md#q-tmp-003)
- human-verified
- user-facing-behavior
- test-coverage

The spec records Tom's go-ahead (2026-10-22) for this reader.

Open questions: [Must a paged temporal window read show one consistent moment while edges are written?](../../Verus_verification/open_questions.md#q-tmp-003)

### temporal.window.sources

- design-verified
- Sources: [spec 255 FR-003, FR-004](../../../specs/255-temporal-window-reader/spec.md#L127-L130); [`iris_vector_graph/_engine/temporal_window.py::window_spec`](../../../iris_vector_graph/_engine/temporal_window.py#L37-L58); [`iris_src/src/Graph/KG/TemporalWindow.cls::Open`](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L44-L81) (filter mode 0 only with no source, list or prefix; a list stores its non-empty names, `:56-66`); [`TemporalWindow.cls::NextKey`](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L196-L239); unit test [`test_an_empty_source_list_is_a_list_not_every_source`](../../../tests/unit/test_255_temporal_window_reader.py#L99-L101), live test `test_255_window_reader_us1_e2e.py::test_an_empty_list_reads_nothing`
- Playbook: [TMP-B6.11](../../../experiment/playbook-completion/ontology/05-temporal.md#L217) (same rule; the omitted half added from `window_spec`)
- Verus: see [temporal_window_reader](../../Verus_verification/models/temporal_window_reader/NOTES.md) (`theorem_spec_sources_omitted_vs_empty`, `theorem_server_filter_sources`, both as-built; controls `empty-list-sends-no-key`, `server-empty-list-reads-all`)
- Expands: [Window reads](#temporal.window)
- agent
- user-facing-behavior, data-integrity

The omitted-versus-empty distinction is public case M06. The server half (an absent key reads every source) is inspected at the pin, not observed here.

State machines: [temporal window reader](../../Verus_verification/models/temporal_window_reader/manifest.json)

### temporal.window.paging

- design-verified
- Sources: [spec 255 Decisions](../../../specs/255-temporal-window-reader/spec.md#L162-L168), [edge cases](../../../specs/255-temporal-window-reader/spec.md#L107-L118), [Page](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L123-L193), [cursor](../../../iris_vector_graph/_engine/temporal_window.py#L74-L136); live tests: [US1](../../../tests/e2e/test_255_window_reader_us1_e2e.py), [US2](../../../tests/e2e/test_255_window_reader_us2_e2e.py); empty middle page: [`iris_vector_graph/_engine/temporal_window.py::TemporalWindowCursor.__next__`](../../../iris_vector_graph/_engine/temporal_window.py#L102-L113), unit test [`test_an_empty_middle_page_does_not_end_the_read`](../../../tests/unit/test_255_temporal_window_reader.py#L160-L162)
- Playbook: [TMP-B6](../../../experiment/playbook-completion/ontology/05-temporal.md#L201), [TMP-B6.9](../../../experiment/playbook-completion/ontology/05-temporal.md#L215), [TMP-B6.3](../../../experiment/playbook-completion/ontology/05-temporal.md#L209), [TMP-B6.4](../../../experiment/playbook-completion/ontology/05-temporal.md#L210)
- Verus: see [temporal_window_reader](../../Verus_verification/models/temporal_window_reader/NOTES.md) (`theorem_yield_is_concat_to_done`, as-built transcription of the Python cursor; control `stop-on-empty-page`)
- Expands: [Window reads](#temporal.window)
- Children: [releasing the reader](#temporal.window.paging.release)
- human-verified
- architecture-decision


Spec 255 FR-009 says the cursor "is closed when the iteration ends or is abandoned"; the earlier wording "when its connection ends" was an agent inference (review round 3 R3-reader L6). The empty-middle-page rule (public case M08) was in neither prior ontology; it is the cursor's loop at `temporal_window.py:103-112`.

State machines: [temporal window reader](../../Verus_verification/models/temporal_window_reader/manifest.json)

### temporal.window.paging.release

- design-verified
- Sources: [spec 255 FR-006, FR-009](../../../specs/255-temporal-window-reader/spec.md#L131-L138); [`iris_vector_graph/_engine/temporal_window.py::TemporalWindowCursor.__init__`](../../../iris_vector_graph/_engine/temporal_window.py#L82-L93), [`::TemporalWindowCursor.__next__`](../../../iris_vector_graph/_engine/temporal_window.py#L102-L113), [`::TemporalWindowCursor.close`](../../../iris_vector_graph/_engine/temporal_window.py#L115-L124), [`::TemporalWindowCursor.__exit__`](../../../iris_vector_graph/_engine/temporal_window.py#L129-L130), [`::TemporalWindowCursor.__del__`](../../../iris_vector_graph/_engine/temporal_window.py#L132-L136), [`::_server_call`](../../../iris_vector_graph/_engine/temporal_window.py#L67-L71); server: [`TemporalWindow.cls::Next`](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L85-L91), [`::Close`](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L94-L97), [`::Page`](../../../iris_src/src/Graph/KG/TemporalWindow.cls#L128-L193) (frees at `done`, `:187-191`; a full page stops at `:185`); unit tests [test_255_temporal_window_reader.py `TestCursor`](../../../tests/unit/test_255_temporal_window_reader.py#L131-L201)
- Playbook: [TMP-B6.6](../../../experiment/playbook-completion/ontology/05-temporal.md#L212), [TMP-B6.8](../../../experiment/playbook-completion/ontology/05-temporal.md#L214), [TMP-B6.15](../../../experiment/playbook-completion/ontology/05-temporal.md#L221), [TMP-B6.16](../../../experiment/playbook-completion/ontology/05-temporal.md#L222), [TMP-B6.7](../../../experiment/playbook-completion/ontology/05-temporal.md#L213) (the handle's process and connection)
- Verus: see [temporal_window_reader](../../Verus_verification/models/temporal_window_reader/NOTES.md) (`theorem_exhaustion_frees_without_close`, `theorem_close_mid_read_once`, `theorem_failed_page_closes_once`, `theorem_server_full_page_nonempty`; as-built; controls `close-after-exhaustion`, `skip-close-on-failure`, `close-not-idempotent`)
- Expands: [paging](#temporal.window.paging)
- agent
- user-facing-behavior, data-integrity

Public cases M07 and M08. The client half is bound to the real `TemporalWindowCursor` by an enumerated comparison with a scripted server (the server substituted); the server's free-inside-Open and free-at-done are inspected at the pin, not observed here.

State machines: [temporal window reader](../../Verus_verification/models/temporal_window_reader/manifest.json)

### temporal.purge
- Sources: [spec 254 US1 and Decisions](../../../specs/254-temporal-purge-collisions-rebuild/spec.md#L38-L149), [ADR-0009 amendment](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L31-L49), [PurgeRawBefore and RetireExpired](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L856-L1046), [PurgeBefore](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L813-L854); live tests: [purge](../../../tests/e2e/test_254_purge_e2e.py)
- Children: [bare nodes](#temporal.purge.bare-nodes)
- human-verified
- operations, data-integrity
- test-coverage

Superseded: an earlier spec required the raw purge to leave adjacency untouched. The purge runs no transaction of its own outside node retirement, and no test interrupts one. Known cost: about 40 µs per purged edge ([known issues](../../../docs/KNOWN_ISSUES.md#L870-L876)).

Findings: [A temporal write that races a purge or delete of the same triple can leave a live timestamp with no structural edge](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-011); [The ObjectScript temporal purge-all and erase-all leave marked structural rows](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-008); [A temporal write inside a purge's range that lands after the purge removed the row leaves a marked row with no timestamp](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-013)

### temporal.purge.bare-nodes
- Sources: [ADR-0009 amendment](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L45-L48), [4.7.0 notes](../../../CHANGELOG.md#L21-L22), [Python purge](../../../iris_vector_graph/_engine/temporal.py#L656-L720), [RetireBareNodes](../../../iris_src/src/Graph/KG/Eraser.cls#L1250-L1310); live tests: [purge retires bare](../../../tests/e2e/test_470_purge_retires_bare_e2e.py), [bare nodes](../../../tests/e2e/test_temporal_bare_nodes_e2e.py)
- Expands: [Raw purge](#temporal.purge)
- agent
- operations
- test-coverage

### temporal.erase
- Sources: [spec 239](../../../specs/239-alt-temporal-erase/spec.md#L66-L84), [EraseGraph, EraseAll, EraseNodes](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L362-L447); live tests: [erase owner](../../../tests/e2e/test_temporal_erase_owner.py), [node erasure](../../../tests/e2e/test_255_window_reader_us3_e2e.py)
- agent
- data-integrity
- test-coverage

Findings: [A rolled-back temporal delete or node erase leaves the bucket's event counter decremented](../../Verus_verification/bugs_issues.md#bug-tmp-010); [The ObjectScript temporal purge-all and erase-all leave marked structural rows](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-tmp-008)


Observed divergence (review round 2 R2-1, round 3 R3-reader H2): [erasure_prefix_temporal_only](../../Verus_verification/receipts/native/erasure_prefix_temporal_only.json); spec 256 put off a tenant-scoped erase of temporal data inside a shared graph ([spec 256](../../../specs/256-ledger-tenant-redaction/spec.md#L159-L163)). The explicit-ID route is from code reading (`EraseNodeIds` erases events incident on a named ID with or without a node row).

Findings: [Erasing a tenant by prefix leaves its temporal-only events, and the redaction that follows completes while they stay readable](../../Verus_verification/bugs_issues.md#bug-led-007)

Audit reproduction: [bug-tmp-010](../../Verus_verification/bugs_issues.md#bug-tmp-010) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

### temporal.ledger

- uncertain
- Sources: [glossary](../../../CONTEXT.md#L180-L192), [Changeset](../../../iris_vector_graph/ledger/changeset.py#L307-L345), [OpCreateTemporalEdge](../../../iris_src/src/Graph/KG/LedgerApply.cls#L613-L641); live tests: [temporal changeset](../../../tests/integration/test_224_temporal_changeset_e2e.py)
- Children: [atomic](#temporal.ledger.atomic), [What should an insert collision inside a changeset do?](../../Verus_verification/open_questions.md#q-tmp-004)
- agent
- user-facing-behavior
- test-coverage

Open questions: [Is the temporal index inside the ledger's guarantee?](../../Verus_verification/open_questions.md#HD-0502), [What should an insert collision inside a changeset do?](../../Verus_verification/open_questions.md#q-tmp-004)

### temporal.ledger.atomic
- Sources: [Changeset docstring](../../../iris_vector_graph/ledger/changeset.py#L321-L336), [ADR-0010 context](../../../docs/adr/0010-degree-is-counted-never-stored.md#L17-L24), [user guide](../../../docs/USER_GUIDE.md#L236-L259)
- Expands: [Ledger](#temporal.ledger)
- agent
- data-integrity

Observed divergence ([temporal_rollback_counters](../../Verus_verification/receipts/native/temporal_rollback_counters.json)): the event counter, count and sum are raised with an increment that IRIS does not roll back, so they keep a failed changeset's write. The existing rollback test fails before the temporal write runs (finding F3 in [stage-A notes](../../uplift/ivg-verus-initial/intent/temporal.md)).

Findings: [A rolled-back temporal write leaves its statistics counted, so a retry counts the edge twice](../../Verus_verification/bugs_issues.md#bug-tmp-003)

Audit reproduction: [bug-tmp-003](../../Verus_verification/bugs_issues.md#bug-tmp-003) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.
