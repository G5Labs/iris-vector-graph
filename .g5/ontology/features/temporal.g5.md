# Temporal edges

Start here to record timestamped events or read a time window. For the time index and the structural edges derived from events, see [adjacency and derived data](../architecture/adjacency-and-derived-data.g5.md).

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
- **Event counter**: for each bucket and source, the number of events the statistics hold; velocity and burst reads add these up.
- **Label set**: a set of attribute keys and values interned once under a hash, for long-term retention.

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

<a id="temporal.write"></a>
[I · temporal.write]

Writing a temporal edge stores it with its attributes, updates the statistics and the newest-event index, and asserts the [implied structural edge](../architecture/adjacency-and-derived-data.g5.md#temporal.structural) unless the predicate is temporal-only in that graph. Each write runs in one of three modes, which differ only when the coordinates already hold an edge.
- Insert, the default for direct writes, keeps the existing edge and reports a collision.
- Update replaces the existing edge's weight and attributes.
- Skip keeps the existing edge and counts the write as skipped.
- A batch write reports how many edges were written, how many collided and how many were skipped.
- A single-edge write reports success even for a collision; a caller that must know writes a one-edge batch and reads its counts.
- A write can leave out the inbound entry for edges never read by target; inbound reads then cannot see that edge.
- Today a direct write opens no transaction of its own: alone it keeps what it wrote before a failure, and inside a caller's transaction it joins it, but a rollback leaves its statistics counted. When the caller turned the driver's autocommit off and has written nothing yet, its rollback undoes only the structural side: a temporal edge written alone or in a batch stays without its structural edge and end nodes, and a deleted temporal edge stays deleted while its structural edge comes back. Whether a failed write must leave nothing is [open](../../Verus_verification/open_questions.md#temporal.write.partial-failure).

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
- The children say how each read is answered and how each kind of write changes the statistics.

- Working assumption: Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.

<a id="temporal.stats.after-purge"></a>
[D · temporal.stats.after-purge]

A raw purge keeps the statistics, so they go on describing the past after the edges they summarize are gone.
- Statistics are removed separately, by bucket range, and that never touches temporal edges.
- An aggregate read over a bucket cut by both the window and a purge counts none of the purged part.
- A bucket-range purge returns how many buckets in the range held statistics; a range whose start is after its end removes nothing and returns 0.
- After a bucket-range purge, a read that holds the bucket whole answers nothing for it even while its edges remain, and a read that cuts the bucket still counts those edges.
- A later delete in a range-purged bucket rebuilds the bucket's aggregates from its surviving edges but not its event counters, so aggregates and velocity then disagree about that bucket. Which rule should win is [open](../../Verus_verification/open_questions.md#q-tmp-002).

<a id="temporal.stats.window"></a>
[I · temporal.stats.window]

Aggregate, group and target reads answer exactly the requested window, both ends included.
- A bucket the window holds whole is answered from its statistics; a bucket the window cuts is read edge by edge.
- The metrics are count, sum, minimum, maximum and average; the average is rounded to six decimal places.
- An empty window, a missing minimum or maximum, or an unknown metric must answer 0 or 0.0. Today the Python reader raises `ValueError` for minimum, maximum, average and unknown metrics in those cases.
- A group read returns one row per source and predicate that has something in the window, and no row for one that has nothing. A row carries no target.
- A target read lists the distinct targets of one source's edges in exactly the window, read from the edges themselves, so a raw purge empties it and a bucket-range purge does not.
- Each read sees only its own graph.
- An empty predicate in a group or target read means every predicate.
- An aggregate read needs a source and a predicate, and a read with an empty one must be refused. Today it fails with a server subscript error when the window holds a whole bucket or any edge of the graph falls in the cut part. Otherwise it answers 0 for a count and 0.0 for a sum, as if the source had no edges ([finding](../../Verus_verification/bugs_issues.md#bug-tmp-108)).
- These reads assume seconds. Today an edge written by the millisecond entry point lands in the seconds bucket of its time in seconds, because both entry points share the statistics. Whole-bucket counts, groups, velocity and distinct estimates then include it, while target reads, edge-by-edge reads and cut windows do not ([bug-tmp-106](../../Verus_verification/bugs_issues.md#bug-tmp-106)).

<a id="temporal.stats.velocity"></a>
[I · temporal.stats.velocity]

Velocity and burst reads count events from the per-source event counters of every bucket from the one holding now minus the window to the one holding now.
- The bucket holding now counts whole, so an event later than now in that bucket counts too; so does an event up to a bucket before the window's start.
- A source's events over every predicate count. The burst read accepts a predicate and does not use it, although its parameter documentation says it filters.
- A burst read lists a source when its total reaches the threshold, the threshold itself included, and only sources holding a counter in those buckets.
- Now is the caller's timestamp when one is given, otherwise the wall clock in seconds.
- In the millisecond entry point the default now is still in seconds, so an event stored in milliseconds is never counted unless the caller passes now.
- In the millisecond entry point the window is in milliseconds too, although the parameter is named in seconds: a window of 300 reaches back 0.3 seconds.

<a id="temporal.stats.distinct"></a>
[I · temporal.stats.distinct]

A distinct-target read estimates how many distinct targets one source's edges of one predicate reach, or every source's when no source is named.
- With no source named, an empty predicate means every predicate. With a source named, today an empty predicate fails with a server subscript error.
- It merges the sketches of every bucket the window touches, so a target outside the window in a touched bucket counts.
- An empty window answers 0, and the estimate must stay within about a quarter of the true number.
- Today any window that holds at least one target answers at least 11, so one target answers 11 and the error is large below about 40 targets.
- A delete rebuilds the sketch from the surviving edges; a raw purge keeps it; a bucket-range purge removes it.

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
- When it was the triple's last timestamp, the structural edge follows [the end of the implication](../architecture/adjacency-and-derived-data.g5.md#temporal.structural.end).

- Working assumption: Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.

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

## Read and page through a time window

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

## Label sets

<a id="temporal.labelset"></a>
[I · temporal.labelset]

Interning a set of attributes stores its canonical JSON text once and returns the SHA-1 hash of that text. Equal sets must share one hash and different sets must get different hashes. Today this fails for nested objects and lists, and for strings that hold a quote (both below).
- Keys are sorted; numbers stay numbers, booleans booleans and null null, and key order does not change the hash.
- Resolving a known hash returns the canonical text, and an unknown hash returns an empty string.
- Interned sets are append-only: no purge removes them.
- Today string values are written without JSON escaping and a fraction below one is written as `.5`. A value holding a quote can therefore produce the same text and hash as a different set, and some resolved texts are not JSON.
- Today a nested object or list is written as an internal object reference such as `"12@%Library.DynamicObject"`, which changes from call to call and ignores the content. The same set then gets a new hash, and a new stored entry, on every call, and two different nested values can share a hash ([bug-tmp-105](../../Verus_verification/bugs_issues.md#bug-tmp-105)).
- Text that is not JSON fails with a parsing error rather than returning an empty hash. The Python entry point always sends JSON.

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

## Earlier links

These links take you to the current sections and statements.

<a id="the-implied-structural-edge"></a>

[How an event becomes a structural edge](../architecture/adjacency-and-derived-data.g5.md#how-an-event-becomes-a-structural-edge)

<a id="window-reads"></a>

[Read and page through a time window](#read-and-page-through-a-time-window)

<a id="temporal.owner"></a>

[temporal.owner](../architecture/adjacency-and-derived-data.g5.md#temporal.owner)

<a id="temporal.stats.writers"></a>

[temporal.stats.writers](../architecture/adjacency-and-derived-data.g5.md#temporal.stats.writers)

<a id="temporal.structural"></a>

[temporal.structural](../architecture/adjacency-and-derived-data.g5.md#temporal.structural)

<a id="temporal.structural.mark"></a>

[temporal.structural.mark](../architecture/adjacency-and-derived-data.g5.md#temporal.structural.mark)

<a id="temporal.structural.mark.readers"></a>

[temporal.structural.mark.readers](../architecture/adjacency-and-derived-data.g5.md#temporal.structural.mark.readers)

<a id="temporal.structural.adopt"></a>

[temporal.structural.adopt](../architecture/adjacency-and-derived-data.g5.md#temporal.structural.adopt)

<a id="temporal.structural.end"></a>

[temporal.structural.end](../architecture/adjacency-and-derived-data.g5.md#temporal.structural.end)

<a id="temporal.structural.upgrade"></a>

[temporal.structural.upgrade](../architecture/adjacency-and-derived-data.g5.md#temporal.structural.upgrade)

<a id="temporal.structural.ledger"></a>

[temporal.structural.ledger](../architecture/adjacency-and-derived-data.g5.md#temporal.structural.ledger)

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
- Children: [after purge](#temporal.stats.after-purge), [window reads](#temporal.stats.window), [writers](../architecture/adjacency-and-derived-data.g5.md#temporal.stats.writers), [velocity and bursts](#temporal.stats.velocity), [distinct targets](#temporal.stats.distinct), [After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?](../../Verus_verification/open_questions.md#q-tmp-002)
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

Formal (iteration 51): [write history to statistics to reader](../../Verus_verification/models/temporal_stats/temporal_stats.rs), [claims, roles and premises](../../Verus_verification/models/temporal_stats/NOTES.md). Evidence: [frozen predictions](../../uplift/consolidated/iteration-51/stats-PAIRS.md).

State machines: [temporal statistics](../../Verus_verification/models/temporal_stats/manifest.json)

### temporal.stats.after-purge

- Sources: [spec 204 US1](../../../specs/204-temporal-index-gaps/spec.md#L20-L48), [ADR-0009 amendment](../../../docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md#L31-L49), [PurgeBucketRange](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L1048-L1066); live tests: [ledger coexistence](../../../tests/integration/test_ledger_us11_temporal_coexist.py)
- Expands: [Statistics](#temporal.stats)
- agent
- operations, data-integrity
- uncertain
- design-verified
- Formal: [`theorem_raw_purge_keeps_statistics`, `theorem_raw_purge_whole_vs_cut`, `theorem_bucket_purge_whole_vs_cut`, `theorem_bucket_purge_reversed_range`, `theorem_delete_after_bucket_purge_recreates`](../../Verus_verification/models/temporal_stats/temporal_stats.rs)
- Open question: [q-tmp-002](../../Verus_verification/open_questions.md#q-tmp-002)

Iteration 51: the bucket-range return value, the whole-versus-cut reads after each purge and the delete after a bucket-range purge are observed on the fixture and bound ([binding receipt](../../Verus_verification/results/temporal_stats/), cases `agg_p_*`, `agg_q_*`, `agg_qb_*`, `vel_qb_299`). The previous tag `test-coverage` remains true of the purge tests.

State machines: [temporal statistics](../../Verus_verification/models/temporal_stats/manifest.json)

### temporal.stats.window

- Sources: [GetAggregate, GetBucketGroups, BucketGroupsEvents, GetBucketGroupTargets](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L1442-L1633), [store conversion](../../../iris_vector_graph/stores/iris_sql_store.py#L2971-L2987), [docstrings](../../../iris_vector_graph/_engine/temporal.py#L934-L1047), [USER_GUIDE aggregates](../../../docs/USER_GUIDE.md#L1011-L1027), [CHANGELOG R217/R249](../../../CHANGELOG.md#L1221-L1224); live tests: [exact window](../../../tests/e2e/test_460_r217_temporal_aggregate_window_e2e.py), [groups](../../../tests/e2e/test_460_r249_counters_default_graph_e2e.py)
- Expands: [Statistics](#temporal.stats)
- agent
- user-facing-behavior
- design-verified
- Formal: [`theorem_cut_bucket_is_exact`, `theorem_one_whole_bucket_reads_statistics`, `theorem_empty_answer_raises`, `theorem_group_row_absent`, `theorem_targets_follow_raw`, `theorem_ms_edge_in_seconds_whole_bucket`, `theorem_empty_key_quiet_cut_window_answers_zero`, `theorem_empty_key_raises_with_whole_bucket_or_event`](../../Verus_verification/models/temporal_stats/temporal_stats.rs)

Findings: [bug-tmp-009](../../Verus_verification/bugs_issues.md#bug-tmp-009) (strengthened in iteration 51: an unknown metric, and a whole bucket left with a count but no extremes, raise too); [bug-tmp-106](../../Verus_verification/bugs_issues.md#bug-tmp-106) (the millisecond writer; found by independent review round 2, reproduced and modeled in iteration 53); [bug-tmp-108](../../Verus_verification/bugs_issues.md#bug-tmp-108) (an empty key answers 0 on a quiet cut window; review round 3, modeled and bound in iteration 56).

The empty-key rule (review round 2, m2; challenged in round 3): no document promises a wildcard for the aggregate read, so an empty source or predicate is an invalid call and the rule asks for a refusal. As built it raises a server subscript error on a whole bucket or a met timestamp, and answers 0 on a quiet cut window ([iteration-53 probe](../../uplift/consolidated/iteration-53/temporal/temporal-observed-20261117T044748Z.json) `m2_*`; temporal_stats binding cases `ek_*`, iteration 56). The group read's docstring says an empty predicate matches all.

State machines: [temporal statistics](../../Verus_verification/models/temporal_stats/manifest.json)

### temporal.stats.velocity

- Sources: [GetVelocity and FindBursts](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L757-L806), [TemporalIndexMS](../../../iris_src/src/Graph/KG/TemporalIndexMS.cls), [docstrings](../../../iris_vector_graph/_engine/temporal.py#L852-L909), [API reference](../../../docs/API_REFERENCE.md#L1910-L1995)
- Expands: [Statistics](#temporal.stats)
- agent
- user-facing-behavior
- design-verified
- Formal: [`theorem_velocity_counts_touched_buckets`, `theorem_velocity_boundaries`, `theorem_bursts_ignore_predicate`, `theorem_burst_threshold_inclusive`, `theorem_ms_default_now_misses`](../../Verus_verification/models/temporal_stats/temporal_stats.rs)

Findings: [F-0508](../../Verus_verification/bugs_issues.md#F-0508) (the ignored predicate; now formal). The millisecond default is a recorded divergence, not a separate finding. The millisecond window unit (review round 2, m9) follows from `velocity`, which is general in bucket width and window; the [temporal_stats binding](../../Verus_verification/results/temporal_stats/20261117T045124Z-binding/receipt.json) observes it (`ms_vel_window_300` 1, `ms_vel_window_300000` 2). Premise: the Python engine calls only the seconds entry point.

State machines: [temporal statistics](../../Verus_verification/models/temporal_stats/manifest.json)

### temporal.stats.distinct

- Sources: [GetDistinctCount, HLLAdd, HLLEmpty, UpdateHLL](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L185-L224), [estimator](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L628-L682), [docstring](../../../iris_vector_graph/_engine/temporal.py#L1088-L1111)
- Expands: [Statistics](#temporal.stats)
- agent
- user-facing-behavior
- design-verified
- Formal: [`theorem_distinct_empty_is_zero`, `theorem_distinct_nonempty_at_least_eleven`, `theorem_distinct_one_target_is_eleven`, `theorem_same_target_twice`, `theorem_distinct_window_rounded_out`](../../Verus_verification/models/temporal_stats/temporal_stats.rs)

Findings: [bug-tmp-103](../../Verus_verification/bugs_issues.md#bug-tmp-103) (new in iteration 51). The empty-predicate cases (review round 2, m2) are owned as built from the iteration-53 probe and not modeled. The register choice comes from SHA-1 (a provider computed the same way in the binding).

State machines: [temporal statistics](../../Verus_verification/models/temporal_stats/manifest.json)

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

### temporal.labelset

- Sources: [InternLabelSet and ResolveLabelSet](../../../iris_src/src/Graph/KG/TemporalIndex.cls#L1336-L1397), [docstrings](../../../iris_vector_graph/_engine/temporal.py#L835-L850), [spec 204 FR-012](../../../specs/204-temporal-index-gaps/spec.md)
- agent
- data-integrity
- design-verified
- Formal: [`theorem_label_sets_collide`, `theorem_nested_value_hash_per_call`, `theorem_nested_content_ignored`, `theorem_scalar_sets_idempotent`](../../Verus_verification/models/temporal_stats/temporal_stats.rs)

Findings: [bug-tmp-105](../../Verus_verification/bugs_issues.md#bug-tmp-105) (nested values; found by independent review round 2, reproduced and modeled in iteration 53), [bug-tmp-104](../../Verus_verification/bugs_issues.md#bug-tmp-104) (new in iteration 51), [F-0509](../../Verus_verification/bugs_issues.md#F-0509) (strengthened: a fraction below one also gives non-JSON text). The number text `.5` is an IRIS provider rule, observed and not modeled.

State machines: [temporal statistics](../../Verus_verification/models/temporal_stats/manifest.json)

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
