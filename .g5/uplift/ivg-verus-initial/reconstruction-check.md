# Reconstruction check: IVG ontology at 4.7.0 (initial Verus uplift)

Fresh reader, 2026-11-13. Section 1 and 1b were written from `.g5/ontology/root.g5.md` and the twelve pages it links, with nothing else opened. That includes each page's Metadata section, which is part of the page; where a fact appears only in Metadata it is marked "(meta)". Sections 2 and 3 were written after reading `intent/operations.md` and the sources cited below.

## 1. Reconstruction

This is what I would build if the ontology were all I had.

### 1.1 Graphs and keys

- **Model.** An install lives in one IRIS namespace. Content is split into graphs, each named by a string; `""` is the default graph, and Python `graph=None` means the same. Every node, edge, temporal edge, aggregate and adjacency entry belongs to exactly one graph. The same node ID in two graphs is two nodes, and an edge joins only nodes of its own graph.
- **Keys per store.** Each store derives its own key from the name:
  - native index: default graph = number `0`, a named graph = its name;
  - ledger: default graph = a "reserved control character" (not named), a named graph = its name;
  - SQL: default graph = `''`, and legacy NULL also means default.

  One module owns every derivation, and a key is never converted from one store's form to another's. Every graph-scoped entry has the key as its first subscript, so clearing one graph never visits another, and a wrong or unknown key reads nothing.
- **Name validation.** It runs before any write. `"0"` and any name with a control character are refused; NUL characters are stripped, not refused. Open: how legacy installs that already hold such names are migrated.
- **Unscoped calls.**
  - Python calls without `graph=` mean the default graph. The exception is `delete_node` without a graph: it deletes from the one graph that holds the ID, and refuses before deleting anything when several graphs hold it.
  - Cypher without `USE GRAPH` reads every graph. The answer is the union of per-graph answers, matches never cross graphs, and the row does not say which graph it came from.
  - An unscoped Cypher write changes only what `MATCH` bound, each in its own graph. `CREATE` and `MERGE` go to the default graph.
- **Not a security boundary.** Any caller can name any graph, so tenant isolation needs separate namespaces.
- **Interned snapshot.** It has no graph dimension. Once a named graph holds an edge, its readers refuse or fall back to the default graph's scoped index.

### 1.2 Nodes, edges, adjacency, degree

- **Transactions.** Every engine write is its own transaction, or a nested part of the caller's open transaction. A failure undoes only its own part.
- **Nodes.**
  - `create_node` on an existing (graph, ID) changes nothing and returns False. A refused write raises and leaves nothing.
  - `delete_node` removes, in one graph, the node's labels, properties, documents, vectors and incident edges in one transaction, then the reifier nodes of those edges. Per the metadata (meta), the reifier step runs in later transactions, and if it fails the error says the node is gone and its reifiers are not.
- **Edges.**
  - `create_edge` creates missing endpoints in the same graph and transaction, so a failed edge leaves no node behind.
  - Outside multigraph mode there is at most one edge per (source, type, target). A duplicate write returns False and is never an error.
  - Weight lives in the qualifiers, and a missing weight counts as 1.0.
  - `delete_edge` removes the triple's edges from one graph, or from all graphs on request. It succeeds even when nothing matched, and a refusal removes nothing. Open: whether it also removes reifications and edge embeddings.
- **Multigraph mode.**
  - It is a per-graph flag, off by default, and the default graph may use it. It can always be turned on. Turning it off is refused while any triple holds more than one edge, and erasing the graph clears it.
  - With the mode off, storage is byte-identical to before the mode existed, and every writer uses edge key 0.
  - With the mode on, a triple with two or more edges gets per-edge entries plus a count. The triple entry carries the weight of the lowest-keyed edge. Keys are never renumbered, and a live edge's key is never reused.
  - Degree counts parallel edges. The interned snapshot and edge embeddings stay one per triple.
  - A restore brings back the mode and the parallel edges.
  - Open: how `create_edge` behaves in a multigraph, and how the ledger names one parallel edge.
- **Adjacency index.**
  - It holds out-edges, in-edges and labels, keyed by graph, and is derived from the rows, which stay authoritative.
  - Where it is declared, the database maintains it on every row change in the same transaction, so it cannot drift, and declaring it repairs existing drift.
  - Where it is not declared, only the engine's writers and a rebuild maintain it.
  - One module writes the out- and in-entries, enforced by a source scan.
  - A bulk load may skip index maintenance, but must de-duplicate and rebuild before it returns, on success or failure.
- **Degree.**
  - Degree is the out-degree, total or per edge type. It is counted from the index and never stored as a counter.
  - A count may be cached and served while the node's generation is unchanged. A reader stores a count only if no writer of that graph was in flight and the generation did not move.
  - A writer that cannot take "its lock" still writes, and turns caching off for that graph until the next rebuild.
  - Erasing a node or graph clears its generations and cached degrees, and nothing cached before the erase is ever served after it.
  - A rebuild leaves the cache warm.
- **Rebuilt stores and the graph-version token.**
  - The interned snapshot, the two-hop statistics, the accelerator snapshot and the algorithm cache are each stamped with the namespace-wide graph-version token, and are current only while the token is unchanged.
  - Every write that can change an algorithm's answer raises the token. The token never decreases and is never reused.
  - A computation reads the token first, so a concurrent write makes its result stale.
  - Open: results that include writes which later roll back.
- **Rebuild and verification.**
  - `engine.sync()` rebuilds the adjacency index from the rows, then the interned snapshot from the index. It is idempotent. Open: what readers see if it fails partway.
  - `verify_graph(g)` reports entries with no row, rows with no entry, and current cache entries that are wrong. Its `ok` covers only adjacency against rows.

### 1.3 Ledger: commit, retry, strict mode, verify

- **Storage.** The ledger lives in `^IVG.Ledger` plus the table `ledger_revisions`.
  - A revision has an ID, a seq (contiguous, no gaps), a parent (the previous revision), a kind (genesis, changeset, adoption or redaction), and metadata: actor, actor type, message, source, correlation ID and idempotency key.
  - Records sit at fixed ordinals. Statements give a relationship an identity from its creation to its deletion.
- **Lifecycle.**
  - The ledger is off by default.
  - The first enable writes a genesis. The genesis records every node, label and property in the namespace as default-graph content, and every relationship with its own graph, except the plain rows that temporal edges create.
  - Enabling an enabled ledger is a no-op that returns the head. Disable is idempotent.
  - While disabled, commits and redactions are refused and nothing is recorded.
  - Re-enabling records what changed while disabled as an adoption.
- **Changeset.**
  - It is an ordered, non-empty list of node, label, property, relationship, qualifier and temporal-edge operations.
  - The reserved properties `id` and `__graph` are refused before anything is applied.
  - A relationship is named by exactly one of: a statement ID; (source, predicate, target, graph); or an earlier create in the same changeset.
  - The JSON form and the fingerprint are deterministic. The fingerprint covers actor, actor type and operations only.
- **Admission order.** Take the head lock (wait up to 30 s, then `LedgerLockTimeoutError`, which is safe to retry), then check:
  1. the ledger is enabled;
  2. the idempotency key: same key and same fingerprint returns the earlier revision marked replayed; same key with different operations raises `IdempotencyConflictError`; a redacted key is refused;
  3. the expected head: `StaleHeadError` naming the current head if another revision came first, `UnknownRevisionError` if it is not a revision of this ledger;
  4. size: an empty changeset, or more than the limit (default 50,000, set at enable), is refused.

  A replay therefore wins over a stale expected head.
- **Apply.**
  - All or nothing. A failure names the zero-based index of the failing operation.
  - A relationship to a missing node raises `NodeNotFoundError` unless the changeset asks for missing nodes to be created.
  - The revision, its records and its changes become visible together.
  - While a redaction is unfinished, a changeset with any record in its target is refused "after its operations are checked".
- **Caller transactions.** Inside the caller's transaction, the commit joins it, and the head lock is held until the caller ends. A rollback removes the revision with no gap in seq. Enable and redact refuse a caller transaction.
- **Idempotency.** A key whose only use was a refused commit stays free. Concurrent commits with the same key produce one revision. Without a key, a resend applies again.
- **Node scope.** Ledger node operations act on default-graph rows only, and node records carry no graph. Relationship records carry their graph.
- **Immutability.** Revision rows and records cannot be updated or deleted through SQL or objects. The only exception is redaction.
- **Writes outside the ledger.**
  - With the ledger on, they still work but are unrecorded. Verify reports them, and verify with adopt records them.
  - Strict mode refuses the engine's structural write methods, its erase methods and Cypher updates with `LedgerStrictModeError`. Bulk loaders and raw SQL are unguarded.
  - In strict mode a temporal write succeeds but skips its plain relationship row.
  - Open: whether the check fails open or closed when the ledger state is unreadable. Today it is open, and the state is cached for 5 s (meta).
- **Readers.** All are read-only:
  - history: paged and ordered, filtered by actor, actor type, time, correlation ID or source;
  - records: in ordinal order, with prior and new values;
  - diff: the net change in a fixed order; the reverse diff is its exact inverse;
  - reconstruct: the graph as of a revision; refused above a size bound unless asked to stream;
  - export: NDJSON readable by `import_graph_ndjson`, with no size bound.
- **Verify.**
  - It replays genesis through head and compares the result with the tables, giving `equal` or `diverges` with the differences. `adopt` commits the differences as an adoption.
  - It compares structure only. Nodes are compared by ID across all graphs with their labels and properties, leaving out the reserved properties. Relationships are compared by (source, predicate, target, graph) with their qualifiers, not by statement ID.
  - It skips temporal plain rows and the temporal index.
  - No hash chain exists. It is best-effort: no lock, and the adoption names no expected head.

### 1.4 Erasure

- **Entry points.** All go through one database-side Eraser:
  - erase a graph;
  - erase all;
  - erase by node-ID prefix in one graph (an empty prefix is refused);
  - erase a list of node IDs in one graph, with their relationships;
  - erase a list of relationships in one graph, leaving the nodes.

  The old drop-graph call is an alias, and a delete path that leaves another store behind is a defect.
- **Scope.**
  - Rows, adjacency, temporal entries, other graph-scoped indexes and caches, and the ledger's statement entries (live and closed) with their lookups.
  - The default graph in both spellings. Never another graph.
  - Invalid names are refused before deleting.
  - Erasing a graph keeps temporal-only registrations and FHIR registrations, and never touches the embedding quarantine.
  - Unsplittable stores are emptied only by erase-all, which also clears the embedding registry, temporal-only settings, label-set interning and `^NKG` (meta).
- **Atomicity.** One transaction owned by the Eraser: all or nothing, raising on failure. It nests in a caller transaction.
  - Routed embedding tables are emptied inside the transaction and dropped after commit, only when the registry claims them. A failed drop leaves an empty table and its registry row, and the erase still counts as done.
- **Result.** The number of node and relationship rows removed; 0 is not an error.
- **History is kept.** Erasure never touches ledger records. Erasure alone is not a privacy tool.
- **Ledger interaction.** Strict mode refuses the engine erase methods. Open: whether erase must exclude concurrent commits and redactions.

### 1.5 Redaction

- **Inputs.**
  - A graph, plus an optional ID prefix and a separator (default `|`, never empty). The separator is part of the match.
  - The prefix is used as given if it already ends with the separator. An empty prefix means the whole graph (meta).
  - Optionally, a cap on the number of batches.
- **What a target reaches.**
  - Node records live only in the default graph, so a tenant's node records are reachable only with a default-graph target plus a prefix.
  - A named-graph target reaches relationship, qualifier and temporal-edge records only.
  - With a prefix, a relationship record matches when its source or target matches. A qualifier matches with its relationship.
  - A full tenant redaction therefore takes two calls: (tenant graph) and (default graph, tenant prefix).
- **Preconditions (refusals, nothing changed).**
  - The ledger was never enabled, or is disabled.
  - The caller has a transaction open.
  - The graph name is invalid, or the separator is empty.
  - Another target's redaction is unfinished.
  - Any target row is live. The refusal names the live target.
    - For a default-graph target, node, label and property rows count in every graph; relationship rows count only in the target graph.
    - Temporal-index entries do not count (open question).
- **Effect.**
  - Each target record becomes a tombstone at the same ordinal. The tombstone keeps the change kind, entity kind and flags, plus the unsalted SHA-256 of the canonical record. It holds no ID, value or graph.
  - **Mixed-tenant (spanning) revisions:** any revision with a tombstone loses its message, source, correlation ID and idempotency key, and the other tenant loses them too. It keeps seq, ID, parent, kind, commit time, actor, actor type, connection user, and the other graph's records.
  - The idempotency key is unbound and kept as a digest. A later commit with it is refused (`IdempotencyRedactedError` (meta)).
  - Replay, diff and reconstruct treat a tombstone as contributing nothing. Record readers show it as redacted at its position. A diff lists the tombstone positions in its range.
  - Finishing adds one content-free revision of kind `redaction`. It lists the redacted seqs with their tombstone counts, plus counts and a digest of the target.
- **Receipt.**
  - Whether the run completed, and the target digest.
  - The redacted seqs.
  - Counts of tombstones and of revisions, keys and statement entries cleared or removed.
  - The redaction revision, once complete.
  - What stays out of reach: earlier exports, journals and backups. Open: whether to also name snapshots and legacy ledger rows.
- **Batches and interruption.**
  - The run proceeds in bounded batches, each one transaction under the head lock (under 1 s each; 100k records in under 1 min).
  - The in-progress marker holds the target in plain text.
  - The final step, in its own transaction:
    1. re-checks liveness under the lock;
    2. removes the target's statement entries;
    3. writes the redaction revision;
    4. removes the marker.
  - While the marker exists:
    - record readers, diff, reconstruct and export raise `RedactionInProgressError`;
    - verify reports `redaction_in_progress` and adopts nothing;
    - commits touching the target are refused, and other commits proceed;
    - redactions of other targets are refused.
  - Re-running the same target resumes. Re-running a finished one changes nothing and reports zero.
  - A run interrupted mid-batch loses only that batch's transaction.
  - If the target became live again, the run cannot finish until it is erased again. There is no abort (open question).
  - Records whose prefix membership cannot be decided are left and counted, and the run still completes (open question).
- **Result.** Erase plus redaction makes verify `equal` again, if the ledger matched before and the targets cover everything erased.
- **Strict mode.** Open: erase-then-redact under strict mode.

### 1.6 Temporal edges

- **Model.** A temporal edge is (graph, timestamp, source, predicate, target) with a weight and attributes. One edge exists per coordinate.
  - The timestamp is event time, defaulting to now.
  - The unit is seconds, or milliseconds in the ms index. A bucket is 5 minutes, and mixing units is the caller's fault.
  - Every store is per graph, and the same name validation applies.
- **Write.**
  - A write stores the edge and attributes, updates the statistics (per bucket, source and predicate: count, sum, min, max and an approximate distinct-target count; per bucket and source: an event counter) and the newest-event index, and asserts the implied structural edge unless the predicate is temporal-only in that graph.
  - There are three modes: insert (the default for direct writes; on collision it changes nothing anywhere and is counted as a collision), update (replaces weight and attributes), and skip.
  - A batch reports written, collided and skipped. A single write reports success even on a collision.
  - The inbound entry is optional.
  - Replaying the same events in any batch size gives identical stores.
  - Open: statistics after an update; partial failures (direct writes run no transaction); concurrency (no locks).
- **Reads.**
  - Aggregate: exact for an inclusive window. Whole buckets come from the statistics, and cut buckets are read edge by edge.
  - Latest: per source, the newest edge with its attributes, filtered by sources, a prefix or all; an optional predicate, a cutoff (exclusive) and a look-back. A deterministic tie-break applies. Sources with no edge are omitted. A pre-index graph searches back in time for named sources and refuses prefix and all until rebuilt.
  - Window: an inclusive range, ordered by (ts, s, p, o), optionally with attributes and filters (source, source list, prefix, predicate set, direction). It is paged live with only a server-side resume point; a failure raises rather than returning a short answer. Legacy one-call reads raise when the window is too big.
- **Delete one edge.** It recomputes the bucket's statistics from the survivors, decrements the event counter and moves the latest index back. On the last timestamp it removes the marked structural edge. It reports when nothing was there.
- **Implied structural edge.**
  - It carries the temporal mark, one edge per triple, with both endpoint nodes created.
  - An explicit create, bulk create, Cypher `CREATE`/`MERGE` or ledger create "adopts" it: the mark is cleared and the qualifiers applied.
  - It is removed when the last timestamp goes, only while still marked.
  - The upgrade backfills marked edges for every triple that lacks one.
  - Marked edges are outside the ledger (skipped by genesis and verify). Open: whether the endpoint nodes are governed.
- **Temporal-only predicates.**
  - Registered per graph and exact name; the registration is configuration that survives a graph erase.
  - Their writes produce no structural edge, node or adjacency entry. Structural reads find nothing and log one warning.
  - Toggling affects only later writes.
  - Backfill restores marked edges for a predicate made structural again.
  - Drop removes marked edges of temporal-only predicates, plus newly bare nodes. It is resumable, has a dry run, and is refused for a structural predicate.
- **Raw purge.**
  - Takes a range [start, end) in one graph and removes edges, attributes and marked structural edges that no surviving timestamp holds.
  - Structural edges are removed first, so a re-run finishes the job.
  - Statistics stay; a separate bucket-range purge removes them.
  - It can retire endpoints left bare (Python default on, ObjectScript off), and a separate sweep handles bare nodes left earlier.
  - The legacy whole-store purge acts on the default graph and also drops older statistics.
- **Erasure.** A graph erase or erase-all removes temporal data. Node erase removes the node's temporal edges at both ends and keeps the statistics and latest index exact.
- **Ledger.** Changesets may carry temporal writes, in update mode by default. They apply in the same transaction, and a failure leaves nothing, statistics included. Direct temporal writes are unrecorded. Open: an insert collision inside a changeset.
- **Ownership.** Only the time-index component touches the temporal stores.

### 1.7 Search

- **Embedding identity.**
  - A registry table (`Graph_KG.embedding_registry`), not the ledger, holds one row per (table, graph) with the model key, mechanism (from a fixed list), width and element type.
  - Model keys match after trim, lowercase and whitespace-collapse.
  - The width is the column's declared width. Setup never resizes a non-empty table.
  - Query vectors are never padded or cut; a wrong width raises.
- **Checks on write.** Every vector write is checked before writing anything:
  - declared writers on model, mechanism, width and element type;
  - undeclared writers on width and element type only.

  A mixed-width batch is refused whole, and no setting turns refusals into warnings.
  - An upgrade records tables with an unknown model. The first declaring writer claims the table, and one of two racing writers wins. Replacing the model needs `force` and logs a warning.
  - Two declared models never share a table.
  - The queue checks before enqueueing, and the worker fails entries for a model it does not produce.
- **Routes.**
  - One table per (graph, model, kind). The registry is the only authority, and no table names are derived.
  - A missing route reads nothing, except for the default pair (default graph with an undeclared model), which uses the original tables.
  - The first write creates the route at the vector's width (table, attempted vector index and registry row, together). Concurrent creates converge, and creation is refused inside a caller transaction.
  - Edge vectors are routed by graph and edge.
  - All vector reads and writes are single-graph. The SQL procedures read only the original tables and raise for a named graph that has its own route.
- **Quarantine.**
  - The upgrade places each vector in exactly one graph or in quarantine with a reason (several graphs, none, or resolver declined). Placed plus quarantined equals the starting count, and the upgrade is re-runnable.
  - Placement is manual, one vector at a time, into an existing compatible route, and only for a node in that graph, in one transaction.
- **BM25.**
  - A named index over chosen text properties of one graph's nodes, scored with Okapi BM25 (formula and k1 = 1.5, b = 0.75 given). Tokenizing is lowercase, split on punctuation, no stemming, 77 stopwords. IDF and average length are computed at query time.
  - Insert replaces, removing an absent document is a no-op, and documents with no terms are excluded.
  - Counts agree with postings at every committed point.
  - Per-document cost is proportional to its distinct terms.
  - Writes run under a per-index lock (30 s default) inside a transaction, with plain-write counters. Searches take no lock (open question: isolation).
  - Schema 1 or 2: schema-1 writes are refused with an error naming the upgrade. The upgrade is online, writers are refused while it runs, searches never see a half-built schema 2, and it is resumable.
  - Common-term cutoff f in (0, 1], with a fallback keeping the rarest known term and a report variant.
  - Open: whether plain text search should use a "default" BM25 index.
- **Fusion (RRF).**
  - Each leg contributes `1/(c+rank)` where the result appears, and the top k are kept. An empty text query skips the text leg.
  - The legs are the same graph and are joined on (graph, ID). An unscoped Cypher fusion is refused on a multi-graph namespace.
  - Index choice per leg: the requested graph's own index, else server-side vector search, else an unknown-graph index with a warning, never another graph's index.
  - A failed leg must be reported, not treated as empty.
  - Open: the absent-leg score, and whether all entry points share one text leg.
- **Erasure.** A graph erase removes vectors (routes and original tables), edge vectors, documents, and routed tables and registry rows. Erase-all clears the registry. Open: BM25 and IVF indexes, which today survive.

### 1.8 Cypher

- **Two paths.**
  - The SQL path (translate to SQL) answers everything, including all writes.
  - The native executor (IRIS walks the adjacency index from a Python-built plan) answers supported reads. It is on by default where the index is declared, can be disabled per engine or per process, and is gated:
    - the executor is enabled;
    - the index is declared;
    - the engine is not in its own bulk-load session;
    - the caller has SELECT on the node, label, property and edge tables;
    - the plan format matches.
  - It never takes writes, procedures, `UNION` or multi-statement text, although a read step inside a write may run natively and see the write's uncommitted changes.
  - Native answers must equal SQL answers: the same columns, values and types; the same order where fully ordered; under `LIMIT` with partial ordering, the same count, each row a member of the SQL answer.
  - Any native failure falls back to SQL with a warning logged once per reason.
  - Adaptive routing by measured speed is allowed.
- **Shadow mode.** Runs both paths and raises on any difference. Native failures still fall back.
- **Compiled plans.**
  - A per-shape class is generated and compiled at run time for plans with at least one hop. Modes: `job` (default; background compile), `sync`, and `off`.
  - A plan is valid only for its shape and for the same executor, generator and property-table builds; otherwise it is interpreted and rebuilt.
  - A deploy or an explicit drop deletes all compiled plans.
  - A failed compile is logged once and not retried until a deploy. Compiling never makes a read fail.
  - Only generator-written code is compiled, and a shape's record names only its own class.
- **Scope.**
  - `USE GRAPH g` confines the whole query. `USE GRAPH ''` is the default graph. Graph names are validated before any read or write.
  - With no `USE GRAPH`, reads keep each match, `WITH` carry, variable-length and shortest path inside one graph; a procedure answers per-graph union or refuses.
  - Writes follow the all-graphs write rule: `SET n.p = m.x` reads `m` in its own graph, and `MERGE` acts on the default graph only.
  - Open: unscoped `CREATE` or `MERGE` of a relationship between named-graph bound nodes, which today goes to the default graph.
- **Writes.**
  - One write is one transaction: it commits on return, or follows the caller's transaction, and raises `GraphWriteError` with its own changes undone. A per-row `MERGE` is still one transaction.
  - All clauses act on the rows bound before any write.
  - The index is updated in the same transaction.
  - Writes are not recorded in the ledger, and are refused under strict mode.
- **Read-only mode.** It refuses any query that may write, decided by parsing (`UNION` branches, `CALL {}`, multi-statement text, unparsable text). Keywords inside strings or comments do not count.
- **Other.** Neo4j Browser metadata queries get fixed answers. Conformance is the TCK with the listed deviations, notably untyped stored values.

### 1.9 Install and schema

- **Namespace and schema.** One namespace holds one IVG Schema (default `Graph_KG`; set by `schema_prefix`, then `IVG_SCHEMA_PREFIX`; never `IRIS_SCHEMA_PREFIX`). Name rules apply (letters, digits, underscore; no `SQLUser`, no `%`, no IVG packages; case-insensitive), and an invalid name fails before any database call. Nothing goes in `SQLUser` or `User`.
- **Schema record.**
  - The first completed setup writes it as its last step. It is immutable, and renaming is unsupported.
  - A mismatching engine or deploy is refused before anything else, from every public call. Setup, status and legacy removal are exempt. A login that cannot read the record gets a warning and the check is skipped.
  - No record, or missing current objects, gives one error naming the case and pointing to setup and its dry run. The engine never falls back to legacy objects.
  - Setup without a record decides what to record from where the tables exist (the five-case table).
  - Classes follow the schema because setup rewrites their sources.
- **Setup.**
  - It is idempotent and resumable to the same end state, and has a dry run that writes nothing.
  - It refuses a caller with uncommitted work, and gives a privilege error naming the missing privilege.
  - It compiles only the classes the server supports (embedded Python, `%AI`, dependencies) and reports the ones it skipped.
  - Open: whether to record the schema when a class fails to compile, and concurrent setups.
- **Upgrade from 4.5.x.** Legacy objects stay and keep working, with one log message. Old compiled plans are discarded. The ledger rows are copied once into a non-default schema. Grants are copied to replacements (EXECUTE only), and EXECUTE on the Arno SQL functions is revoked.
- **Legacy removal.** Opt-in. It lists by default and removes only IVG-owned objects from the manifest, with ownership checked by body text and a truthful per-object result.
- **Migrations.** Re-runnable and never deleting vectors. Uncertain rows go to quarantine. A caller transaction is refused. A failed step rolls back and raises. Steps run in a fixed order. Old node stores are dropped and rebuilt from the rows.
- **Snapshots.**
  - They cover the whole namespace, chosen by a server-side store inventory. They exclude the deploy record, compiled plans, the queue, quarantine and the derived vector table.
  - A replacing restore erases everything and loads. A merging restore adds what is missing; configuration tables match on primary key.
  - A save fails whole. A restore is not atomic, and a failure names the committed tables.
  - A restore drops derived caches and raises the token past both values. Open: restoring onto a live ledger.
- **Bulk loader.** One graph per loader. It skips index and key checks, then rebuilds the indexes and adjacency. A re-load counts duplicates as skipped. It refuses a caller transaction and commits per batch, uses the recorded schema, and is not governed by strict mode. The adjacency index, degree cache and token must be current before any read.

### 1.10 Access

- **Surfaces.** The engine (direct), plus optional servers: HTTP (Cypher, Neo4j HTTP, admin, Bolt over TCP and WebSocket), GraphQL, a sample FastAPI app, IRIS MCP tools (`%AI` only) and an IRIS REST dispatcher. Each server call maps to an engine method.
- **Authentication.** The real boundary is the IRIS login and its SQL privileges, which SQL functions check before touching globals; Native-API class methods do not.
  - The API key is optional (`IVG_API_KEY`). When set, every route except `/health` and the docs needs it. Matching is exact path and default-deny. Every method needs it, except a CORS preflight. A failure gives 401 before handlers and before the read-only check.
  - The key is sent as `X-Api-Key` or `Bearer` and compared in constant time.
  - Bolt takes the key in `HELLO` or `LOGON`. A bad key revokes authentication, and `RESET` does not restore it.
  - Defaults: 0.0.0.0:8200 and 7687, as `_SYSTEM/SYS`.
- **Health.** `/health` returns status only. It is unhealthy if the database is down or the schema record is missing or wrong.
- **Read-only mode** (`IVG_READ_ONLY`). It runs after the key check and refuses:
  - admin `POST`, `PUT`, `PATCH` and `DELETE` (except explain);
  - writing Cypher on every Cypher route;
  - FHIR events, unless `IVG_ALLOW_FHIR_WRITES`;
  - any batch with a write, so none of its statements run.

  One parser rule decides what counts as a write. Derived caches may still be written.
- **Trusted surfaces.** The MCP tools are for trusted clients only (arbitrary SQL, file reads, Cypher writes). The REST web app is inert until created, then uses password login with a read-only role.
- **Ledger.** Strict mode governs engine writes, Cypher through the engine, and snapshot restore. The bulk loader and raw SQL are not governed. Open: the sample API Cypher, GraphQL, the MCP SQL tool and FHIR sync; and Bolt/HTTP transactions, which are no-ops today.

### 1.11 FHIR

- **Graph.** A registered FHIR repository is projected into its own named graph: one node per live resource (`Type/id`, labelled by type) and one edge per indexed reference to a live local resource. Codes are read live.
  - Tables are created at the first registration. Registration is refused without a repository.
- **Sync.**
  - It runs from two watermarks, in key batches. Each batch commits with its watermark advance.
  - Resync of a key is idempotent and reads the current state: a live key ensures the node and label and recomputes out-edges; a dead key removes everything and marks incoming references unresolved.
  - Syncs converge to the rebuild result.
  - One sync, rebuild or re-interpretation runs per graph at a time; others get "busy".
  - A repository behind the watermarks triggers a rebuild.
- **Rebuild.** Compares rather than erases, keeps vectors, resets the watermarks to the pre-scan values, and is non-transactional.
- **Erase.** Keeps the registration and resets the watermarks and interpretation version.
- **Compartment edges.** Derived from reference edges and the compartment rules, owned by the source resource, and re-derived when the interpretation version changes. PPR skips them by default.
- **Open questions.** Ledger governance; other writers.
- **Deprecated `/fhir-event`.** Records a node plus a timestamped edge from its patient. It needs the key and is refused in read-only mode unless allowed. Retries add edges (open question).

### 1.12 Algorithms

- **Owners and native readers.** Every algorithm has an in-IRIS Owner. Arno Native Readers (PageRank, PPR, WCC, CDLP, subgraph) are used only when all of these hold:
  - the proof record lists the algorithm;
  - the library-reported Reader Revision is at least the proven minimum;
  - the call is in scope (default graph only).

  Revisions come only from the library's capability report, and minimums only from the proof record. Any failure falls back to the Owner and is logged. A reload re-reads the revisions. Betweenness is always the Owner.
- **Proof record.** Written by the evidence gate only: four or more shapes, a tie-heavy graph and five repeats. A bad record means every algorithm uses its Owner.
- **Scope.** PageRank, WCC, CDLP and subgraph: default graph only. PPR and degree centrality: named graphs allowed. Unscoped-index procedures refuse once a named graph has edges.
- **Cache.**
  - Shared across connections, per graph, keyed by algorithm and parameters.
  - Valid only while the token is unchanged (read before computing). The token is namespace-wide; PageRank also keys on the node set.
  - Erasure removes the cache. Racing computations: the last store wins. Oversize answers are not stored. A read-only login does not cache.

## 1b. Gaps a builder would hit

Numbered G1 to G40 so section 2(c) can answer each.

**Contradictions between pages or blocks**

- **G1.** `graph.default` says a Python read that names no graph uses the default graph. `graph.all_graphs_read`, as written, says "A read that names no graph sees every graph", without restricting that to Cypher. Only the `graph.default` bullet ties the all-graphs rule to Cypher.
- **G2.** `graph.default`'s rule "names no graph uses the default graph" conflicts with its own bullet that `delete_node` without a graph deletes from whichever graph holds the ID. That bullet is a second exception that is not called one. Also undefined: what happens when no graph holds the ID.
- **G3.** Strict-mode coverage differs between pages:
  - `ledger.strict`: structural write methods, erase methods, Cypher.
  - `access.ledger_strict`: engine write methods, Cypher, snapshot restore.

  The ledger page omits restore and the access page omits erase. Neither says whether embedding writes, BM25 writes, temporal purges, multigraph switches or FHIR sync are governed.
- **G4.** `ledger.strict` says that in strict mode a temporal write "skips its plain relationship row". This contradicts `temporal.structural` ("a temporal edge implies a structural edge"; the only exception is temporal-only predicates) and `temporal.structural.ledger` (marked edges are outside ledger governance). Under the ledger page's rule, a triple written in strict mode is invisible to traversal and `MATCH`.
- **G5.** `structure.rebuilt.token` says every write that can change an algorithm's answer raises the token. `algorithms.cache.token` says adding an edgeless node does not raise it, which is why PageRank keys on the node set. The two definitions also differ: "writes that can change an algorithm's answer" against "every change to the graph's adjacency". Label and property writes (CDLP seeds, weights in qualifiers) are left undetermined.
- **G6.** `erasure.scope` (I) says "every store that holds it", and `erasure.entry-points` (I) says "every deletion path goes through the Eraser". Elsewhere:
  - `search.erasure.indexes` says BM25 and IVF indexes survive a graph erase.
  - `structure.rebuild` says the interned snapshot needs a rebuild after erasures.
  - `structure.edge.delete`, `temporal.delete` and `temporal.purge`, Cypher `DELETE` and FHIR resync all delete content. Whether any of them goes through the Eraser is not stated.

  The invariants are written as true while the pages show they are not.
- **G7.** `structure.adjacency.bulk` (D: the loader de-duplicates and rebuilds before returning) and `structure.multigraph.layout` (a rebuild reproduces the written layout) conflict with `install.bulk_load.limits` (concurrent loaders duplicate; the loader empties every graph's adjacency; multigraph graphs lose parallel edges).
- **G8.** `ledger.lifecycle.genesis` records every node in every graph as default-graph content. With `graph.membership` (the same ID in two graphs is two nodes), genesis has to merge or collide nodes that share an ID, and verify then compares them "by ID across all graphs". Neither page says how labels and properties of same-ID nodes in different graphs combine.
- **G9.** `ledger.commit` lets a changeset create missing nodes. `ledger.node-scope` says ledger node operations act on the default graph only, while `graph.membership` and `structure.edge` require an edge's endpoints in its own graph. So a named-graph relationship with missing endpoints either fails, or creates nodes in a graph that the ledger "never" writes nodes to.
- **G10.** `redaction.batches` says the marker "records it while it is unfinished". `redaction.batches.readers` and `.commits` depend on the marker, and so does `.competing`. Nothing says when the marker is created. If it is created only at the first tombstone, the reader, commit and competing-run guarantees all have a window.

**Undefined terms, or terms used before definition**

- **G11.** Reifier node, reification, documents (which table, who writes it), the statement index with its "entries" and "lookups", two-hop statistics, the accelerator's snapshot, IVF, PLAID, label-set interning, `^NKG`, velocity and burst reads, record "flags", the "connection user", the ledger's "statistics".
- **G12.** The canonical record (the JSON field set and order) is not specified. An independent builder therefore cannot reproduce tombstone digests, and `redaction.tombstone.digest-source` admits even the Python reader cannot.
- **G13.** The ledger's default-graph key is a "reserved control character", with no character given. Of "control character" (`graph.names`), the ontology admits (meta) that the Python and IRIS definitions differ.
- **G14.** Erasure by "ID prefix" does not say whether the separator is part of the match. Redaction requires it (`acme` never matches `acme-health|`). A builder could make erase-by-prefix and redact-by-prefix select different ID sets, leaving content live (redaction then refused) or erased but unredacted.

**Operations whose contract is missing**

- **G15.** There is no node or edge update API: no set or remove of properties or labels, no update of qualifiers on an existing edge, and no statement of what `create_node` does with labels or properties on an existing node, or `create_edge` with qualifiers on an existing edge. Property value typing is mentioned only as a Cypher deviation ("untyped text").
- **G16.** There is no read API outside Cypher: get node, neighbors (direction, type filter, ordering), k-hop, paths, subgraph extraction. Degree is out-degree only, with no in-degree.
- **G17.** Algorithm semantics are absent:
  - inputs and parameters, and for PageRank damping, iterations, tolerance, dangling nodes and weighting;
  - PPR's seeds, bidirectional mode and exclusions;
  - output shape and tie order;
  - centrality types;
  - how parallel edges weigh (meta says this changed in 4.6.0, but the rule itself is "owned by the algorithm pages", and those pages do not state it);
  - triangle count, SCC, k-core and Leiden, which are named only in a question.
- **G18.** The vector search contract is absent: similarity metric, k, label filters, result shape, tie order, the HNSW/ANN index and its exactness, and what a "seed node's vector" means for search.
- **G19.** BM25 document lifecycle: who keeps an index in step with node property changes and node deletes. The page describes manual insert and remove only, so a builder would not know whether the engine maintains it. The 77-word stopword list is not given. The RRF constant `c` has no default.
- **G20.** Ledger operation vocabulary: the exact operation kinds (create, delete, set, unset per entity), the format of the statement ID and revision ID, what a commit returns, the error raised by a disabled ledger, an empty changeset or an oversize changeset, how strict mode is turned on and off, and what can be set at enable time.
- **G21.** Redaction call signature: the batch size, how "the same redaction" is recognised for resume (graph, prefix and separator normalised?), the error types for each refusal, and the privileges needed.
- **G22.** Temporal: how a caller picks the seconds or milliseconds index, how the inbound entry is omitted, the attribute value types, the threshold at which "too large" applies to legacy reads, and what velocity and burst reads are.
- **G23.** Snapshot format and API (path, merge or replace flag), and whether a restore is governed by strict mode (the access page says yes; the install page is silent).
- **G24.** FHIR: the registration, unregistration and status API; how syncs are triggered (a task schedule is mentioned in install); and whether an unresolved incoming reference is resolved when its target appears.
- **G25.** Cypher procedure catalogue (`ivg.*`): which procedures exist and their per-graph behaviour. Only `ivg.retrieve` (fusion) is implied.

**Statements a reader cannot act on, or ambiguous ones**

- **G26.** `structure.degree.cache.uncommitted`: "a writer that cannot get its lock". It is not said which lock, what the timeout is, or who else holds it.
- **G27.** `structure.multigraph.layout`: "a live edge's key is never reused". Can a deleted edge's key be reused? How is a new key chosen (max + 1)?
- **G28.** `ledger.commit.admission`: where the reserved-property check and the redaction-target check fall in the fixed order. The redaction check comes "after its operations are checked", which could mean after apply and then rolled back, or after validation.
- **G29.** `ledger.readers`: the reconstruct "size bound" and the diff "fixed order" are not given.
- **G30.** `redaction.after-erasure.default-graph` (I): for a default-graph target with no prefix, node rows in every graph count as live. So the default graph can never be redacted wholesale while any graph in the namespace has a node. That may be intended, but it is not said.
- **G31.** `temporal.structural.end` says "in every graph". Read literally, a delete in one graph removes the structural edge in all graphs, which contradicts `temporal.edge.graph-scope`. It probably means "the same rule holds in each graph".
- **G32.** `temporal.write`: "A single-edge write reports success even for a collision". So the single-edge API cannot tell a caller about a collision, and the retry advice in `temporal.write.partial-failure` cannot be followed.
- **G33.** `fhir.interpretation`: "verification treats compartment edges as ordinary edges". It does not say whether that is `verify_graph` or ledger verify, which never sees FHIR writes because they are unrecorded.
- **G34.** `install.bulk_load` (D) says a re-load is idempotent and duplicates are counted as skipped. `structure.adjacency.bulk` says the loader "must remove its own duplicates". It is unclear whether those duplicates are within one load or across loads.
- **G35.** `access.read_only` refuses admin writes, but nothing says whether non-Cypher write routes (bulk load, snapshot restore, embedding writes) on the HTTP server are admin routes.

**Concurrency and failure behaviour left open or unstated**

- **G36.** There is no general statement on concurrent non-ledger writers to the same node or edge: row locks, uniqueness under a race for `create_node`, or multigraph edge-key allocation under a race.
- **G37.** Erase against FHIR sync, erase against redaction, erase against ledger commit, and bulk load against reads from other processes (`query.native.index-current`) are all left as open questions.
- **G38.** `ledger.lifecycle`: what disable does to an unfinished redaction, and whether disable is refused while one is unfinished.
- **G39.** `structure.rebuild.failure`: readers during a failed rebuild. Open.
- **G40.** Structure: there is no rule for what a stale interned snapshot does when read: rebuild on demand, serve stale, or refuse. `structure.rebuilt` says only that it is "not current".

## 2. Comparison

**Evidence.**
- Read in full: `intent/operations.md`.
- Re-read at source:
  - `CONTEXT.md` L27-58;
  - `_engine/nodes_edges.py`: `erase_graph` 1473-1530, `delete_node`/`_delete_scopes` 2202-2268, `store_node` 2393-2424, `set_edge_weight` 1306-1342;
  - `engine.py` `_iris_obj` 1894-1943;
  - `_engine/temporal.py` 186-210 and 286-332;
  - `Eraser.cls` `EraseNodes` 307-348;
  - `LedgerGenesis.cls` 14-36;
  - `LedgerApply.cls` 76-120 and 450-490;
  - `Ledger.cls` 486-522;
  - `LedgerRedact.cls` `Redact` 182-239;
  - `GraphKey.cls` 23-77;
  - `ledger/client.py` `commit` 381-445;
  - `algo_cache.py` 1-25;
  - `_engine/embeddings.py` 470-540, and the commits in `_engine/schema.py` 880-950;
  - `_engine/schema.py` `delete_reification` 3361-3392;
  - `_engine/snapshot.py` 1093-1100;
  - ADR-0008 L36-41, spec 252 FR-008, ledger-api contract L82-93, CHANGELOG 4.6.4 L410-426, the KNOWN_ISSUES headings, and `translator.py` 14628-14668.

**Tags.** "[verified]" means I read the code or doc myself. "[inv]" means the claim rests on the inventory; "[inv s]" means the inventory marked it as a sub-sweep citation it did not re-read itself.

### 2(a) Operations or behaviour the ontology does not cover, or covers only in part

1. **Two transports for the native API.** This is the most consequential gap.
   - `engine._iris_obj()` opens a separate `iris.dbapi` connection whenever the engine knows its credentials (`from_connect`) [verified `engine.py:1894-1943`].
   - These run on that connection:
     - `erase_graph` and `erase_all` [verified `nodes_edges.py:1513-1517`];
     - ledger commits made without a caller transaction;
     - `redact`, `enable`, `disable` and `set_strict`;
     - FHIR graph calls, `set_multigraph`, the VecIdx/IVF/PLAID index calls, `sync()`;
     - the edge writers' adjacency writes when the index is not declared [inv].
   - Test runs monkeypatch `createIRIS` back onto the caller's connection, so the tests exercise the other transport.
   - The ontology never mentions this, yet whether an operation joins the caller's transaction depends on it (see 2(b)1).
2. **Node and edge update operations** (structure page).
   - `store_node` is the upsert: it creates the row if missing, replaces the given properties, adds labels, removes a property whose value is None, and returns True [verified].
   - `create_node` writes an `id` property equal to the node ID when none is given. That same name is reserved, and refused, in a ledger changeset [verified docstring].
   - `set_edge_weight` acts on the default graph only and updates every parallel row [verified].
   - Cypher `SET` writes through the `Prop_Set` SQL procedure straight into the row's data global, bypassing the SQL filer [inv s].
3. **Reification and inference** (`reify_edge`, `get_reifications`, `delete_reification`, `materialize_inference`, `retract_inference`). The ontology does not define them. `delete_reification` is not graph-scoped: it deletes the reifier node, labels and properties "in every graph" and bypasses the Eraser [verified `schema.py:3361-3392`].
4. **Read API outside Cypher.** `get_node(s)`, `count_nodes`, by-label and by-property reads, `list_graphs`, k-hop, neighbours, paths, random walk and Dijkstra are not covered. The same goes for the system procedures (`db.*`, `dbms.*`, `apoc.meta.*`, `gds.*.stream`), where an unknown `apoc`/`db`/`dbms` name answers empty success, and for `execute_aql` (read-only) [inv].
5. **Algorithms.**
   - The ontology names five algorithms plus centrality. The code also has Leiden, triangles, SCC, k-core, k-hop, random walk and paths [inv].
   - No algorithm's parameters, output or weighting are specified anywhere in the ontology.
   - The cacheable set is `pagerank`, `ppr`, `wcc` and `cdlp` only. `subgraph` is never cached because it "reads live SQL rdf_labels, which no token moves for" [verified `algo_cache.py:15-17`].
6. **Three different bulk paths, merged into one by the ontology** [inv, ADR-0008, contract]:
   - `bulk_create_nodes`/`_edges` with `disable_indexes`, which commits, drops the index by DDL, writes, then rebuilds;
   - `bulk_load_session`;
   - the `BulkLoader` class (`%NOINDEX %NOCHECK`, raw commit per batch, no strict guard).

   The first two are strict-guarded. The third is not. A failed `_rebuild_after_load` is only logged.
7. **Import and export** (`load_networkx`, `import_graph_ndjson`, `load_obo`, `import_rdf`, `export_graph_ndjson`, `export_rdf`, `prov_export`, `register_namespace`). Each commits per item or batch, so a failure leaves a partial import. The guard runs at entry, but temporal batches inside an import are unguarded [inv].
8. **Other vector and text index families.** VecIdx, PLAID and IVF, plus `create_index`, run with no transaction, use kill-then-rebuild, inflate counts on re-insert, and are never erased [inv]. BM25 is maintained only by explicit calls (`index_protocol.py:41` is the only `bm25_insert` caller), so node writes and deletes never update any of these indexes [inv].
9. **Embedding pipeline.**
   - `embed_nodes`/`embed_edges` count batch errors rather than raising them.
   - The queue never claims an entry, so two workers can process the same one.
   - The Python worker marks an entry DONE before its vector commits.
   - The IRIS worker marks an entry DONE when Prepare fails or no row comes back.

   All from the inventory [inv; `EmbedQueue.cls:112-136,300-330`].
10. **Route creation commits in several steps** [verified]:
    - `_create_routed_table`, `_attempt_route_index` and `_record_route_index_state` each call `conn.commit()` (`schema.py` around 902/922/948) before or around the registry row, and a final commit follows (`embeddings.py:537`).
    - The code comment says a routed table with no registry row "makes every erase in the namespace fail with SQLCODE -124 and erase nothing".
11. **Ledger features with no block.**
    - Public `commit(changeset, kind=...)`. A kind other than `"changeset"` skips the empty and size checks, and `"adoption"` applies through `LedgerGenesis.Adopt` [verified `client.py:381`, `Ledger.cls:488-509`].
    - `post_commit_properties`. These are property writes outside the revision: unrecorded, in a second transaction when no caller transaction exists, and applied again on a replay [inv; ontology meta only].
    - Relationship create returns `relationship_exists` unless `upsert`, which merges qualifiers [verified `LedgerApply.cls:466-480`].
    - `set_strict`, which takes no head lock and has no caller-transaction refusal.
    - Statistics are bumped in a second transaction after the commit.
    - `verify()` without adopt still writes statistics.
    - `PurgeAll` exists.
    - The `rebuild_edge_indices` SQL procedure empties the whole adjacency index outside any transaction [inv].
12. **SQL-table and FHIR bridges.**
    - `map_sql_table`/`map_sql_relationship`/`remove_table_mapping` let Cypher read mapped SQL tables through the translator's mapping cache. The ontology mentions them only as "configuration tables" in snapshots.
    - Also uncovered: FHIR bridges, code crosswalk, `attach_embeddings_to_table`, `fhir_graph_schedule`/`unschedule`/`reinterpret` and the FHIR reports.
    - FHIR sync writes `^KG("label")` directly, beside the functional index.

    All [inv].
13. **Network retries and transport gaps.**
    - The HTTP server's `_run_cypher` retries any exception once on a fresh engine.
    - The CLI's SDK `_post` retries on 5xx and timeouts, so a committed write can be sent again. Only ledger commits with a key de-duplicate.
    - Bolt ignores the access mode.
    - The sample API mounts example GraphQL mutations; `updateProtein` runs a raw `UPDATE rdf_props` with no graph scope, guard or rollback.
    - The demo server routes have no authentication.
    - Admin `kill_query` exists.

    All [inv].
14. **Temporal operations and transaction shape.**
    - Not covered: velocity, bursts, bucket groups, window sources, distinct count, `export_temporal_edges_ndjson`, `rebuild_temporal_latest`, `intern_label_set`, `erase_bare_nodes` and `MigrateToGraphScoped`.
    - A direct temporal write commits the temporal globals with no transaction, then runs the structural step as a separate write, and a failed legacy mirror only logs a warning [verified `temporal.py:292-330`; inv].
    - The ObjectScript `TemporalIndex.Purge`/`EraseAll` leave marked structural rows [inv s].
15. **Cypher deletes and data typing.**
    - Cypher `DELETE r` leaves reifications, edge embeddings and ledger tuple entries. `DETACH DELETE` clears `kg_NodeEmbeddings` but not the optimized or routed tables or the temporal stores [inv s].
    - Cypher `CREATE` of an existing node ID behaves like `MERGE`, because of `NOT EXISTS` guards [inv s].
    - The `CALL {}` subquery translation handles only `MATCH`/`WHERE` (and `UNWIND`) clauses [verified excerpt `translator.py:14635-14663`]. A write body may be dropped silently. This is suspected only; I did not trace whether another path catches it.
    - KNOWN_ISSUES lists about 15 typing deviations that the ontology compresses into "untyped text". Examples: `SET n.p = null` leaves `p` in `keys(n)`; ledger-written values are stored as text; a stored `'1'` or `'True'` matches a boolean.
16. **Transaction SQL procedures.** Any SQL client can call `Txn_Begin`/`Txn_End`/`Txn_Undo`, and `End(1)`/`Undo(1)` end every level, the caller's included [inv].

### 2(b) Ontology statements unsupported by, or contradicted by, the sources

1. **`erasure.atomic`** ("inside a caller's open transaction, the erase is part of that transaction"): **contradicted** for `erase_graph` and `erase_all` on the production transport.
   - They call `self._iris_obj()`, a separate connection, so `$TLevel` there is 0. The Eraser commits on its own, the caller's rollback does not undo it, and it cannot see, and may block on, the caller's uncommitted rows.
   - The CHANGELOG 4.6.4 list of writes that now nest names `delete_node` and `delete_edge` but not `erase_graph`.
   - The `delete_node`, `delete_nodes_by_prefix` and `delete_edges` paths do run on the caller's connection, through the store's `_eraser_txn`.
2. **`search.routes.create_on_write`** ("the table, an attempted vector index and a registry row, committed together"): **contradicted**. The table and index states are committed before the registry row (2(a)10), and the orphan case breaks every erase.
3. **`ledger.strict`**, temporal bullet ("a temporal-edge write still succeeds but skips its plain relationship row"): **true only for the Python-side structural step**.
   - With the adjacency index declared, `InsertEdge` asserts the marked row server-side whatever the strict setting. `temporal.py:304-307` skips only the engine's own step.
   - The sentence comes from the pre-ADR-0009 contract (ledger-api L92-93), which `temporal.structural.ledger`'s own metadata calls stale.
   - The block's list of governed writers is also narrower than the contract's: it omits `restore_snapshot`, `import_graph_ndjson`, `load_networkx`, `reify_edge`/`delete_reification`, `materialize`/`retract_inference`, `set_edge_weight`, the `bulk_*` calls and the store protocol.
4. **`graph.all_graphs_read`**: **misquoted**. CONTEXT.md defines it as "A read that names no graph (a Cypher query without `USE GRAPH`)". The ontology dropped the parenthesis, which creates the contradiction with `graph.default` (G1).
5. **`erasure.entry-points`** (I: "Every deletion path goes through the Eraser"): **contradicted**.
   - `delete_edge` (rows only) and `delete_reification` (direct `DELETE`, every graph) [verified].
   - Cypher `DELETE` [inv s].
   - The temporal delete, purge and `DropRows`, FHIR resync, and `rebuild_edge_indices` [inv].

   The rule holds only for the five erase entry points.
6. **`structure.rebuilt.token`** (I: "every write that can change an algorithm's answer increases the token"): **not supported** as written. Node, label and property writes never move the token [inv; `algo_cache.py` comment verified]. The design compensates by restricting the cache admission set and keying PageRank on the node set, so the invariant is really "every adjacency change".
7. **`ledger.node-scope`** ("its node operations read and write only default-graph rows"): **contradicted in effect**.
   - A relationship create checks endpoint existence graph-blind (`NodeExists` has no graph predicate), then inserts node rows in the relationship's own graph through `EnsureEndpoint` [verified].
   - The ledger therefore writes named-graph node rows that it never records as node records.
8. **`ledger.lifecycle.genesis`**: **supported, but the consequence is omitted**. Genesis scans `nodes`, `rdf_labels` and `rdf_props` with no graph [verified], so a node ID held by two graphs gives two `create_node` records, and the labels and properties of both go to one ID.
9. **`ledger.commit.size`** ("an empty changeset is refused"): **conditional**. It holds only for `kind="changeset"`, and `kind` is a public parameter [verified].
10. **`structure.adjacency.bulk`** (D: a bulk load must de-duplicate and rebuild "whether it succeeds or fails"): the source (spec 252 FR-008, ADR-0008) scopes it to the engine's `%NOINDEX` bulk paths. Applied to "a bulk load" in general it is **contradicted** by `BulkLoader` (`%NOCHECK`) and by `_rebuild_after_load` failures that are only logged [inv].
11. **`redaction.batches`** ("an in-progress marker records it while it is unfinished"): **not supported** for the scan-only phase. Per the block's own metadata, the marker is written at the first tombstone.
    - The competing-target check reads the marker before `LiveRows`, outside the head lock [verified `LedgerRedact.cls:203-206`].
    - The guarantees in `.readers`, `.commits` and `.competing` therefore have a window.
12. **`erasure.scope`** (I: "every store that holds it"): **contradicted** for `^BM25Idx`, `^VecIdx`, `^IVF` and `^PLAID` [inv]. The ontology admits this only inside a Q on the search page. Ordinary node deletes, not just erasure, also leave these indexes answering.
13. **`temporal.edge`** ("a write with no timestamp is stamped with the current time"): the single-edge path sends `0` [verified `temporal.py:292-294`]. Per the block's metadata, it is stored at 0.
14. **`structure.write`** (D: each engine write is one transaction or nests): not true of many operations.
    - Route creation refuses a caller transaction and commits several times.
    - `erase_graph`/`erase_all` run on the other connection.
    - `delete_node` deletes the node and then its reifiers in separate transactions, one per 500 IDs.
    - `bulk_*` with `disable_indexes`, `bulk_load_session`, `restore_snapshot`, `import_*` and `embed_*` commit many times.
    - Temporal writes, BM25 build/drop, VecIdx/IVF/PLAID and `set_multigraph` run with no transaction.

    All [inv; partly verified]. The block needs an explicit list of exceptions.
15. **`graph.default`**, `delete_node` bullet: **supported, with detail missing** [verified].
    - The "omitted" sentinel is distinct from `graph=None`, which means the default graph.
    - A "holder" is a node row or an edge row naming the ID.
    - With no holder it returns False.
16. **`access.surfaces`** ("each server call maps to an engine method an application could call itself"): contradicted by the sample API's raw Cypher executor, which the ontology flags, and also by the GraphQL example mutations' raw `UPDATE` [inv].

### 2(c) Resolution of each gap in 1b

| Gap | Status | How the sources resolve it, or why it stays open |
|---|---|---|
| G1 | Resolved | CONTEXT limits the all-graphs read to Cypher without `USE GRAPH` (fix the wording). |
| G2 | Resolved | Omitted ≠ None. Holder = node or edge row. No holder gives False. Several holders give `ValueError` before any delete. |
| G3 | Resolved | The contract enumerates the guarded calls. Unguarded: temporal writes, `set_multigraph`, embedding/vector/BM25 writes, FHIR, `bulk_delete_adjacency`, `Prop_Set`, `BulkLoader`, the sample API, the MCP SQL tool. |
| G4 | Resolved | The ledger page is stale. Under a declared index the marked row is written server-side even in strict mode. |
| G5 | Resolved | The token tracks adjacency only. The cache admits pagerank, ppr, wcc and cdlp; PageRank keys the node set; the PPR seed-before-node case stays open (meta). |
| G6 | Partly resolved | The five erase entry points use the Eraser; the others do not (2(b)5). The Eraser drops `^NKG`, which read paths rebuild on demand (`EnsureNKG`) [inv]. Erasing search indexes is open. |
| G7 / G34 | Resolved | There are three bulk paths. FR-008 covers the `%NOINDEX` engine paths; `BulkLoader` is separate and weaker. |
| G8 | Partly resolved | Behaviour seen: duplicate `create_node` records and merged labels and properties. How replay and verify fold them was not checked. Intent is open. |
| G9 | Resolved | Graph-blind existence check, then `EnsureEndpoint` in the relationship's graph. |
| G10 | Resolved | The marker is created at the first tombstone, and the competing check runs outside the lock. Intent is open (the ontology already flags the suspected race). |
| G11 | Partly resolved | The inventory names the stores: `rdf_reifications`, `docs`, `^IVG.Ledger("stmt"/"tuple")`, `^KG("deg2p*")`, `^NKG`, `^IVF`, `^PLAID`, `^KG("labelset")`. Velocity and bursts are temporal reads. Their semantics are still undefined. |
| G12 | Open | The canonical form exists only as `Ledger.cls CanonicalRecord`. Nothing outside the server can reproduce a digest. |
| G13 | Resolved | The ledger default key is `$Char(1)`. "Control" means IRIS `$ZStrip(..,"*C")`. `$Char(0)` is stripped. |
| G14 | Resolved, as a real hazard | `EraseNodes` matches a plain `%STARTSWITH` plus a `$Extract` check with no separator. Redaction appends the separator. Erasing with prefix `acme` also erases `acme-health|…`. |
| G15 | Resolved | `store_node` (upsert), `set_edge_weight` (default graph only), Cypher `SET` through `Prop_Set`, ledger `set_prop`/`remove_prop`/`add_label`/`remove_label`. |
| G16 | Resolved, as a list | The inventory enumerates the read methods. Their contracts were not checked. |
| G17 / G18 | Open | No algorithm or vector-search semantics were checked. `_engine/algorithms.py`, `_engine/vector.py`, USER_GUIDE and API_REFERENCE need extraction. |
| G19 | Partly resolved | BM25 and the other indexes are maintained only by explicit calls. The default `c` and the stopword list were not checked. |
| G20 | Partly resolved | Operation kinds are visible in `LedgerApply`, error codes in `Ledger.Err`, and `kind` is public. The return shape was not checked. |
| G21 | Resolved | `Redact(graph, prefix, separator="\|", actor="system:ledger-redact", batch=2000, max_batches)`. Identity is a digest of (canonical graph name, match string). Every run rescans from the first seq. Errors: `transaction_open`, `not_enabled`, `disabled`, `invalid_target`, `redaction_in_progress`, `target_live`, `inconsistent`. |
| G22 | Open | Not checked. |
| G23 | Partly resolved | Restore is strict-guarded and refuses a caller transaction [verified]. The format was not checked. |
| G24 | Resolved, as a list | register, rebuild, sync, reinterpret, schedule, unschedule and the Task Manager task [inv]. Resolution of unresolved references was not checked. |
| G25 | Partly resolved | System procedures exist, and unknown names answer empty success [inv]. There is no `ivg.*` catalogue. |
| G26 | Resolved | `Adjacency.WriterLock`: a 5 s timeout, then proceed and set `^IVG.AdjNoLock` [inv]. |
| G27 | Partly resolved | Cypher allocates `MAX(ekey)+1` with no lock [inv s], so a deleted highest key can be reused and racing writers can collide. |
| G28 | Resolved | The redaction-target check runs after `ApplyAll`, inside the commit transaction, which then rolls back. The reserved-property check runs client-side while the changeset is built. |
| G29 | Open | Not checked. |
| G30 | Open | The code counts only default-graph rows for a no-prefix default target (meta). The intent is undecided. |
| G31 | Resolved | Wording only: the rule applies per graph. |
| G32 / G33 | Open | Design choices with no recorded decision. |
| G35 | Resolved | Load, embed, snapshot, rebuild and schema-init routes all sit under `/admin/`, so read-only mode refuses them. |
| G36 | Partly resolved | `MERGE` and `create_node` take no lock; uniqueness rests on keys. Multigraph key allocation races. |
| G37 | Open | Plus a new case: an erase on the other connection against the caller's own open transaction (2(b)1). |
| G38 | Open | `disable` takes no head lock and has no caller-transaction refusal [inv]. Its behaviour while a redaction marker exists was not checked. |
| G39 | Partly resolved | `BuildKG` commits every 50k rows, so readers see a partial rebuild. `rebuild_edge_indices` empties the index outside a transaction [inv]. |
| G40 | Partly resolved | The Eraser drops `^NKG`; `EnsureNKG` rebuilds it on demand, including from read algorithms [inv]. |

## 3. Corrections proposed

In priority order, most consequential first.

1. **`erasure.atomic`** (erasure page). Replace the caller-transaction bullet:
   - `erase_graph` and `erase_all` run on the engine's dedicated native connection whenever the engine holds its credentials, so they commit independently of the caller's transaction and do not see its uncommitted rows.
   - Only the store-routed deletes (`delete_node`, `delete_nodes_by_prefix`, `delete_edges`) nest.
   - Add **Q `erasure.atomic.caller-transaction`**: should these erases refuse an open caller transaction, as setup, restore and redaction do, or move onto the caller's connection?
   - Sources: `nodes_edges.py:1513-1517`, `engine.py:1894-1943`, CHANGELOG 4.6.4 L410-426.
2. **`search.routes.create_on_write`** (search page). Remove "committed together".
   - State that the routed table, its index and its index state are committed before the registry row.
   - Add **I `search.routes.no-orphan`**: a routed table never exists without its registry row, because an orphan's foreign key makes every erase in the namespace fail (SQLCODE -124). Mark it with an observed divergence.
   - Sources: `embeddings.py:470-537`; the commits in `_engine/schema.py` around 902/922/948.
3. **`erasure.entry-points`** (erasure page). Narrow the claim to "every *erase* entry point goes through the Eraser".
   - Add **D `erasure.other-deletes`** listing the deletes that bypass the Eraser and what each leaves behind:
     - `delete_edge`: reifications, edge embeddings and ledger tuples;
     - Cypher `DELETE`/`DETACH DELETE`: the same, plus routed vectors and temporal data;
     - `delete_reification`: not graph-scoped;
     - temporal delete, purge and `DropRows`: no ledger tuple cleanup;
     - FHIR resync;
     - `rebuild_edge_indices`.
   - Sources: `nodes_edges.py:1382-1456`, `schema.py:3361-3392`, `operations.md` (a)2 and G4.
4. **New D `erasure.prefix-match`** (erasure page), plus a line in **`redaction.tenant`**.
   - Erase-by-prefix is a raw starts-with with no separator. Redaction's prefix includes the separator.
   - Erase with `"tenant|"`, never `"tenant"`, or `acme` also erases `acme-health|…`.
   - Sources: `Eraser.cls:322-345`, `LedgerRedact.cls` `MatchString`.
5. **`ledger.strict`** and **`access.ledger_strict`**.
   - Replace both paraphrases with the contract's enumerated list of guarded calls, `restore_snapshot` and the import and inference calls included.
   - Add the unguarded writers: temporal writes, `set_multigraph`, embedding/vector/BM25 writes, FHIR sync, `bulk_delete_adjacency`, the `Prop_Set` and `Txn_*` SQL procedures, `BulkLoader`, raw SQL.
   - Rewrite the temporal bullet: strict mode skips only the engine's Python-side structural step, so under a declared index the marked row is still written.
   - Sources: ledger-api contract L82-93, `temporal.py:304-307`, `operations.md` G4.
6. **New I `search.indexes.follow-content`** (search page), extending `search.erasure.indexes`.
   - State that BM25, IVF, VecIdx and PLAID indexes are maintained only by explicit index calls: node writes, deletes and erasures never update them, so a deleted or erased node stays retrievable until a rebuild.
   - Decide whether that is accepted for derived indexes or a privacy defect.
   - Sources: `operations.md` (a)3 and G5, `index_protocol.py:41`.
7. **`ledger.node-scope`** and **`ledger.commit`**.
   - A relationship create checks endpoint existence in any graph, then registers the endpoints in the relationship's own graph (`EnsureEndpoint`). Those node rows are written but never recorded.
   - Relationship create refuses an existing relationship unless `upsert`, which merges qualifiers.
   - Source: `LedgerApply.cls:79-110,450-487`.
8. **`ledger.lifecycle.genesis`**.
   - Add: genesis reads nodes, labels and properties of every graph without a graph, so an ID held by two graphs yields two `create_node` records and one merged label and property set.
   - Add **Q `ledger.lifecycle.genesis.shared-ids`** for the intended treatment.
   - Source: `LedgerGenesis.cls:17-36`.
9. **New Q `ledger.commit.kind`** (ledger page).
   - `commit(kind=...)` is public. Non-`changeset` kinds skip the empty and size checks, and `adoption` uses the adoption apply path.
   - Should `kind` be internal?
   - Also amend **`ledger.commit.size`** to say "for a changeset commit".
   - Sources: `client.py:381`, `Ledger.cls:488-509`.
10. **`ledger.commit.admission`**. State that the redaction-target check runs after the operations are applied, inside the commit transaction, which rolls back on refusal, and that the reserved-property check runs client-side. Source: `Ledger.cls:500-518`.
11. **`redaction.batches`** and **`redaction.batches.competing`**.
    - Move the observed facts into the body as divergences: the marker is created at the first tombstone, the competing check runs before the lock, and every run rescans from the first seq.
    - Add a new **D `redaction.call`**: the default batch is 2000, target identity is a digest of (graph, match string), the error codes are as listed in 2(c) G21, and the default actor is `system:ledger-redact`.
    - Source: `LedgerRedact.cls:182-239`.
12. **`structure.rebuilt.token`** and **`algorithms.cache.token`**.
    - Restate the invariant as "every change to adjacency increases the token". Node, label and property writes do not.
    - Make the cache's admission rule part of the contract: only pagerank, ppr, wcc and cdlp are cached; PageRank also keys the node set; `subgraph` is never cached.
    - Align the two definitions of the graph-version token.
    - Sources: `algo_cache.py:15-17`, `operations.md` (a)7.
13. **`graph.all_graphs_read`**. Restore CONTEXT's qualifier "(a Cypher query without `USE GRAPH`)". Source: `CONTEXT.md` L38-42.
14. **New D `structure.node.update`** (structure page).
    - `store_node` creates the row if missing, replaces the given properties, adds labels, removes a property whose value is None, and returns True.
    - `create_node` writes an `id` property, which ledger changesets refuse as reserved.
    - `set_edge_weight` acts on the default graph only and on every parallel row.
    - Sources: `nodes_edges.py:2393-2424,1306-1342`.
15. **New D `structure.reification`** (structure page). Define reifier, reification and the `reify_edge`/`delete_reification`/`get_reifications` operations, including that `delete_reification` is not graph-scoped (an observed divergence from `graph.default`). Source: `schema.py:3264-3392`.
16. **`structure.adjacency.bulk`** and **`install.bulk_load`**.
    - Name the three bulk paths.
    - Scope FR-008 to the engine's `%NOINDEX` paths.
    - Record that `BulkLoader` uses `%NOCHECK` and is unguarded, and that a failed post-load rebuild is only logged.
    - Sources: ADR-0008 L38-39, spec 252 FR-008, `operations.md` G1 and G6.
17. **`structure.write`**. Add the list of exceptions: multi-commit operations, operations on the separate connection, and operations with no transaction (2(b)14). Source: `operations.md` (b).
18. **New D `access.retries`** (access page).
    - The HTTP server retries a failed Cypher call once on a fresh engine, and the SDK retries 5xx and timeouts.
    - So a non-idempotent write can apply twice; only ledger commits with a key de-duplicate.
    - Add Bolt's ignored access mode, and add the GraphQL example mutations to `access.ledger_strict.surfaces`.
    - Sources: `cypher_api.py:239-251`, `sdk.py:210-225`, `bolt_server.py`, `examples/domains/biomedical/resolver.py:258-278`.
19. **`search.embedding.queue`**. Add the processing semantics as an observed divergence plus a Q: no claim, DONE before the vector commits, and the IRIS worker marking DONE on failure. Source: `EmbedQueue.cls:112-136,300-330`, `embeddings.py:1964-1980`.
20. **New page or blocks for SQL-table mapping**: `map_sql_table`, `map_sql_relationship` and how Cypher reads mapped tables. The owner is to be decided (Cypher or FHIR). Source: `_engine/fhir.py:88-249`.
21. **New D `query.system-procedures`** (Cypher page). The `db.*`/`dbms.*`/`apoc.meta.*`/`gds.*` stubs exist, and an unknown `apoc`/`db`/`dbms` name answers empty success. Source: `engine.py:1039-1740`.
22. **`query.conformance`**. Check whether a `CALL { }` body holding a write is translated. The translator's subquery functions handle only `MATCH`/`WHERE`/`UNWIND`. If writes are dropped, list it as a deviation. Source: `translator.py:14561-14668`.
23. **`graph.key.two_forms`**. Name the ledger's default key, `$Char(1)`, and define "control character" as IRIS's `*C` class. Source: `GraphKey.cls:23-77`.
24. **`temporal.write`**. State that a direct write commits the temporal stores with no transaction, then makes the structural edge as a separate write, and that a single-edge write with no timestamp sends 0. Source: `temporal.py:286-332`.
25. **Algorithms page.**
    - Add an operation block per algorithm: parameters, weighting of parallel edges (4.6.0 change), output and ties.
    - Add the unlisted algorithms (Leiden, triangles, SCC, k-core, k-hop, random walk, paths).
    - This needs extraction from `_engine/algorithms.py:216-1764` and API_REFERENCE; not done here.
