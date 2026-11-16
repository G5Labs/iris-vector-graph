# Question review — all 146 starting IDs

Source behavior and existing attributable contract evidence are separate from owner approval. Nine inherited questions are settled for the pin by existing sources; residual mechanisms remain open where stated. The other policy questions retain agent-provisional assumptions. The 2 historical reports and 14 proof-debt records are separate. Public issue status is not product behavior or approval; see [upstream](upstream.json). The repository has Discussions disabled. Relevant historical intent searches are retained, not presented as a fresh branch-wide search.

<a id="q-004"></a>
### Must erasure and redaction be serialised with each other and with ledger commits?

Status: open owner decision. Canonical owner: `erasure.concurrency`.

Now: `Graph.KG.Eraser` takes no ledger head lock; since 4.6.4 an erase made through an engine on a plain connection nests in the caller's transaction (aad50087), while an engine from `from_connect` runs it on a dedicated connection. `LedgerRedact.LiveRows` reads without locks. Probe [erasure_caller_transaction](../../receipts/native/erasure_caller_transaction_redaction.json): on a plain connection the erase nests at `$TLEVEL=1`, a concurrent redaction completes, and the caller's rollback restores the content ([bug-002](../../bugs_issues.md#bug-002)); through `from_connect` the erase [committed on its own](../../receipts/native/erasure_caller_transaction_from_connect.json) and the caller's rollback did not undo it.

Working assumption (agent, unratified): Require committed erasure before redaction; treat caller transaction membership as unresolved rather than permitting dirty liveness reads.

Options and implications: (a) callers must not redact while an erase is uncommitted (document it); (b) redaction must refuse while any erase of the target is uncommitted (take the head lock in the eraser, or a shared target lock); (c) erasure must never join a caller's transaction.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-001"></a>
### Should another tenant's retry of a revision it shared with a redacted tenant be refused?

Status: open owner decision. Canonical owner: `redaction.idempotency.other-tenant`.

Now: spec 256 Decision 2 (Tom, 2026-10-22) clears the metadata of any revision with a redacted record, idempotency key included; the recorded trade-off named only the lost commit message (a140ed78 open question 2). `LedgerRedact.ClearRevision` moves the key to `idemRedacted`; `Ledger.CommitInTxn` then refuses every retry with that key (`idempotency_redacted`). Probe [redaction_mixed_retry](../../receipts/native/redaction_mixed_retry.json), re-run with byte-identical changesets: tenant B's retry of its own revision replays; its retry of the revision it shared with redacted tenant A is refused with `IdempotencyRedactedError` and changes nothing. The other tenant's `history(correlation_id=...)` lookup also stops finding the revision.

Working assumption (agent, unratified): Preserve refusal of the whole shared revision key and loss of its correlation lookup until the maintainer specifies a tenant-specific retry result.

Options and implications: (a) intended — a key names the whole revision, and a refused retry is safer than a replay of a partly tombstoned revision; (b) unintended — only the target's retries should be refused; the other tenant should get a replay (its content is intact) or a distinct error telling it the revision exists but was partly redacted.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-003"></a>
### How should strict mode and the erase-then-redact path fit together?

Status: open owner decision. Canonical owner: `redaction.strict-mode`.

Now: `erase_graph`, `delete_nodes_by_prefix` and `erase_all` call the strict-mode check and raise `LedgerStrictModeError` (nodes_edges.py:1513, :1552; iris_sql_store.py:1433). Redaction refuses a live target, so it needs the erasure first. Erasing through changesets cannot reach named-graph node rows (ledger node operations are default-graph only, 4.6.0 R290). No document or test covers the combination. Model witness `witness_strict_erase_then_redact_needs_strict_off` ([platform model](../../models/platform/NOTES.md)); probe [platform_strict_redaction](../../receipts/native/platform_strict_redaction.json): under strict mode the tenant's graph cannot be erased, the ledger leaves its 2 named-graph node rows, and redaction is refused `target_live`; with strict off both run.

Working assumption (agent, unratified): Document the present strict-off erasure sequence as an operational precondition; do not infer that disabling strict mode is the desired product interface.

Options and implications: (a) strict-mode users turn strict off for the erase, then on again; (b) erasure is exempt from strict mode because it removes content, not history (ADR-0004); (c) erasure should be recorded in the ledger in strict mode.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-008"></a>
### Should erase-by-prefix and redact-by-prefix use the same prefix rule?

Status: open owner decision. Canonical owner: `erasure.prefix-match`.

Now: `Eraser.EraseNodes` (Eraser.cls:322-350) and `engine.delete_nodes_by_prefix` match a bare starts-with ("acme" erases `acme-health|1` too), while `LedgerRedact.MatchString` always appends the separator ("acme" redacts only `acme|…`). The documented tenant recipe pairs the two (ADR-0013:37; the e2e fixture erases with "tenantA|" and redacts with "tenantA"). An operator who erases with the same bare prefix they redact with also erases a neighbouring tenant's nodes, irreversibly. Found by the fresh-reader reconstruction check (reconstruction-check.md, correction 4).

Working assumption (agent, unratified): Keep generic erase as literal starts-with and use the separator explicitly in the tenant recipe; changing the generic API needs compatibility authority.

Options and implications: (a) intended — erase is a general id-prefix tool and the caller must add the separator; document it beside the recipe; (b) the tenant recipe should use one target notion for both steps (a separator-aware erase, or a combined erase-and-redact entry point).

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-009"></a>
### Should redaction count a target's temporal-only edges as live content?

Status: open owner decision. Canonical owner: `redaction.after-erasure.temporal`.

Now: ADR-0013 refuses redaction "while any **row** of the target is live", justified by replay; CONTEXT.md says redaction is "Refused while any of the target's **content** is live", and its Erasure definition lists the temporal index as content. A temporal-only predicate (ADR-0015) writes no row and no node. Model witness W2 (`witness_temporal_only_content_is_not_seen`, [prove receipt](../../results/ledger_redaction/20261114T044401Z-prove/receipt.json)) and probe [redaction_temporal_only_live](../../receipts/native/redaction_temporal_only_live.json): with only a temporal-only edge in `gT` (0 edge rows, 0 node rows), `redact("gT")` completed and tombstoned the `create_temporal_edge` record while the window reader still returns the edge. Erasure does not settle this for prefix targets: erasing a tenant by prefix leaves its temporal-only events whose endpoints have no node row…

Working assumption (agent, unratified): Treat temporal entries as live content for the intended safety rule; the existing row-only check remains a documented behavior discrepancy pending scope confirmation.

Options and implications: (a) ADR-0013's "row" governs: temporal entries are not replayed, so tombstoning their records keeps verify equal and is acceptable; (b) the glossary's "content" governs: redaction must refuse until the temporal entries are erased, or the history of a still-readable event is lost.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-010"></a>
### Should post-commit properties be recorded, excluded from verify, or documented as unrecorded writes?

Status: open owner decision. Canonical owner: `ledger.commit.post-commit.recorded`.

Now: spec 218 (CHANGELOG v2.18.x): `post_commit_properties` are applied "via direct SQL (Approach A — no new revision created)"; the docs do not mention verification. Probe [ledger_post_commit_verify](../../receipts/native/ledger_post_commit_verify.json): one commit with a post-commit property, then `verify()` → `diverges` (`node pcp|1 prop:audit_rev None → x`); `verify(adopt=True)` would record it as an adoption.

Working assumption (agent, unratified): Treat post-commit properties as unrecorded writes today and keep verify divergence visible; skip-on-replay is a separate already documented idempotency obligation.

Options and implications: (a) intended: the documented audit-trail pattern produces an unrecorded write and verify is right to report it (document it); (b) post-commit properties should be recorded (a second record in the same revision) or excluded by verify.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-str-001"></a>
### How should an install that already holds a graph named "0", or one with a control character, find and migrate it?

Status: open owner decision. Canonical owner: `graph.names.legacy`.

Now: ADR-0003:69-70 promises `verify_graph` reports such graphs; none does, and every `ForIndex` caller, the `%BuildIndices` callbacks included, throws on such rows (A-structure Q3). [graph_structure_keys](../../receipts/native/graph_structure_keys.json) shows new writes of these names are refused (K1, K2).

Working assumption (agent, unratified): Preserve refusal of invalid new names and the promised legacy report; require an operator-visible migration plan before claiming old invalid names are supported.

Options and implications: (a) an upgrade step renames them; (b) `verify_graph` reports them and an operator renames them; (c) they are left and every write to them fails.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-tmp-001"></a>
### Must temporal writes stay exact when several writers touch the same coordinates or triple at once?

Status: open owner decision. Canonical owner: `temporal.write.concurrency`.

Now: spec 254 FR-003 states first-write-wins without condition and spec 255 says the latest index is "kept exact"; ADR-0010 explains why the temporal writers take no locks. The `$Data` collision guard and the writes are not locked (`TemporalIndex.cls:84`): `witness_concurrent_inserts_double_count` ([prove receipt](../../results/temporal/20261114T001508Z-prove/receipt.json)) shows two inserts at one coordinate counting twice. `NoteLatest` is an unlocked read-compare-set (`TemporalIndex.cls:493-496`), and two first writers into an empty graph each `Kill ^KG("tlast",g)` (`:90-92`), so the latest index can go stale-low while `Resolve` detects only vanished events (`:411-415`). The write/purge race on one triple is a defect against ADR-0009 and is registered separately ([bug-tmp-011](bugs-review.md#bug-tmp-011)). No concurrent test exists; no probe was run (A-temporal F6, F7).

Working assumption (agent, unratified): Keep first-write-wins and exactness as requirements; concurrent provider behavior is unestablished, not an approved one-writer exemption.

Options and implications: (a) the rules hold for one writer per triple; concurrent writers are the caller's to serialise (document it); (b) the rules are unconditional, so the writers need per-triple locking despite ADR-0010's deadlock concern.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-srch-001"></a>
### Should quarantined vectors and documents survive erasure indefinitely?

Status: open owner decision. Canonical owner: `search.quarantine.retention`.

Now: `embedding_quarantine`, `docs_quarantine` and `edge_vector_quarantine` survive `EraseAll` and graph erasure by decision (FR-039/FR-040 as quoted; the spec is not in `specs/`), and no purge path exists; ADR-0004 says erasure is not a privacy tool, and ADR-0013's redaction does not mention quarantines (A-search Q5).

Working assumption (agent, unratified): Keep quarantined data and explicitly report retention until an owner chooses a purge API and its unknown-graph semantics.

Options and implications: (a) keep them: they are the only copy of vectors whose graph is unknown; (b) a deployment that must delete data needs a purge path or an erase-all that includes them.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-001"></a>
### Is strict mode promised from the moment set_strict returns, or within a few seconds for other engines?

Status: open owner decision. Canonical owner: `ledger.strict`.

Now: `witness_ttl_window_admits_a_write_after_set_strict` ([prove receipt](../../results/platform/20261114T002651Z-prove/receipt.json)); probe [platform_strict_ttl](../../receipts/native/platform_strict_ttl.json): a second engine that had probed before wrote `ttl-bypass` unrecorded 0.002 s after `set_strict(True)` returned, and was refused after the TTL; the calling engine was refused at once (the USER_GUIDE example). The guard caches `Meta()` per engine for 5 s (`ledger/guard.py:20, 38-59`), and `set_strict` refreshes only the calling engine's guard (`client.py:281-309`). Probe [platform_strict_paths](../../receipts/native/platform_strict_paths.json) confirms the guarded paths refuse once the cache is fresh.

Working assumption (agent, unratified): Record immediate enforcement in the calling engine and a five-second cache elsewhere; the time promised to other engines still needs a decision.

Options and implications: (a) strict is promised from the moment `set_strict` returns, so the window is a defect; (b) strict is enforced within 5 s per process, as the guard docstring implies, and needs documenting.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-002"></a>
### Can an explicitly named schema be recorded over another schema's interrupted first setup?

Status: open owner decision. Canonical owner: `install.schema.concurrency.leftover`.

Now: `witness_interrupted_setup_then_explicit_schema` (W-S3, [prove receipt](../../results/platform/20261114T002651Z-prove/receipt.json)) holds even with serial setups. After an interrupted setup on S (marker present, no record; KNOWN_ISSUES:787-807), an engine with an explicit T sees `held={S}` and records T as "explicit" (`_engine/schema.py:2229-2239, 2312`); `^KG`, `^NKG` and `^IVG.Ledger` hold S's data, and `kg_built` is already marked, so setup does not rebuild `^KG` from T's rows (`:2356-2361, 2673-2678`). FR-009's explicit path was designed for 4.5.x namespaces (A-platform F-S3). The concurrent-setup case is [bug-plt-003](bugs-review.md#bug-plt-003).

Working assumption (agent, unratified): Prefer refusing a conflicting unfinished setup; accepting it needs an explicit plan for the old globals and rebuild markers.

Options and implications: (a) refuse the explicit path while another schema holds this release's marker (the premise the model's proof uses); (b) accept it and clear or rebuild the namespace's globals.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-003"></a>
### Should the server refuse to start on a reachable address with no key and a superuser login?

Status: open owner decision. Canonical owner: `access.defaults.exposure`.

Now: with no key, the HTTP server and Bolt bind `0.0.0.0` and connect as `_SYSTEM`/`SYS`, a `%All` superuser, exposing `/admin/load`, Cypher writes and `DELETE /admin/queries/{pid}` → `KillProcess` on any PID, with no warning in `cypher_api` or the CLI (A-platform F-H5); only the sample API warns about the default login. The environment-name mismatch that makes this silent is [bug-plt-009](../../bugs_issues.md#bug-plt-009).

Working assumption (agent, unratified): Treat the documented open bind and credentials as current behavior only; safer defaults need a maintainer policy decision.

Options and implications: (a) refuse to start on a non-loopback host without a key (or with a superuser login); (b) warn loudly and document; (c) keep as is, the operator guide being the control.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-004"></a>
### What should a restore do when the namespace already has a live ledger?

Status: open owner decision. Canonical owner: `install.snapshot.ledger`.

Now: `erase_all` keeps `^IVG.Ledger("rec")`, the head and the meta (`Eraser.cls:810-812`), and the replacing restore's global import only sets values (`_engine/snapshot.py:1654-1692`), so the archive's ledger entries are written over the live ones without removing the live revisions (A-platform F-B3; A-ops candidate finding). Restoring an earlier archive also brings back content a later redaction removed ([q-led-002](#q-led-002)).

Working assumption (agent, unratified): Prefer refusal while a live ledger exists until replace/merge history semantics are specified; do not count the current overlay as a decided contract.

Options and implications: (a) refuse while a ledger is live; (b) replace the live ledger wholesale; (c) keep the live ledger and skip the archive's.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-005"></a>
### Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?

Status: open owner decision. Canonical owner: `install.bulk_load.limits`.

Now: BulkLoader bypasses the ledger and strict mode does not refuse it (documented exempt); its `PurgeIndex` → `RemoveAll` empties every graph's adjacency mid-load with no rebuild lock (`Adjacency.cls:452-473, 814-823`); its in-memory `(s,p,o)` dedupe gives a multigraph graph no parallel edges; two loaders can insert duplicates under `%NOCHECK` (A-platform F-B7; reconstruction check 2(a)6, G7, G34).

Working assumption (agent, unratified): Keep documented loader exemptions and chunking; preserve other graphs and multigraph data unless a narrower supported envelope is expressly adopted.

Options and implications: (a) yes to all three, and the loader documents it; (b) the loader must preserve other graphs' adjacency and multigraph semantics.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-006"></a>
### Should whether a write joins the caller's transaction depend on how the engine was opened?

Status: open owner decision. Canonical owner: `erasure.atomic.caller-transaction`.

Now: `engine._iris_obj()` opens a separate connection whenever the engine knows its credentials (`from_connect`) and reuses the caller's process otherwise (`engine.py:1894-1943`); tests patch it back to the caller's connection. On that transport `erase_graph`/`erase_all` [committed on their own](../../receipts/native/erasure_caller_transaction_from_connect.json), while on a plain connection the erase [nests](../../receipts/native/erasure_caller_transaction_redaction.json) ([q-004](#q-004), [bug-002](../../bugs_issues.md#bug-002)). The same split applies to ledger commits without a caller transaction, `redact`/`enable`/`disable`/`set_strict`, FHIR graph calls, `set_multigraph`, the vector index calls and `sync()`, and to the non-indexed adjacency writes ([bug-str-015](bugs-review.md#bug-str-015)) (A-ops method notes and (e)2; reconstruction check 2(a)1).

Working assumption (agent, unratified): Record each transport-dependent transaction boundary; prefer an explicit consistent join-or-refuse contract before changing it.

Options and implications: (a) intended: these calls are independent of the caller's transaction, and the docs list them; (b) every write should run on the caller's connection and nest; (c) calls that cannot nest should refuse an open caller transaction.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-007"></a>
### Can a default-graph algorithm call use a native reader once a named graph holds edges?

Status: open owner decision. Canonical owner: `algorithms.routing.named_graphs`.

Now: `ArnoAccel.cls:255-256` says the readers read the `^NKG` export, which merges every graph; CONTEXT.md:267 says they read the adjacency index directly; `TraversalBuild.cls:758-760`. The native routes for PageRank, WCC, CDLP and subgraph have no `_named_graph_with_edges()` guard, unlike the R184 tiers (`iris_sql_store.py:3234, 3691, 3749`) (A-platform F-A3).

Working assumption (agent, unratified): Require a proven graph-specific reader before relying on native default-graph results; an unavailable Arno provider does not settle its behavior.

Options and implications: (a) the readers read one graph and the route is safe; (b) they read the merged snapshot, so default-graph PageRank counts named-graph edges and needs the guard.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-008"></a>
### Which write paths must strict mode govern beyond the engine's methods, and how is each classified?

Status: open owner decision. Canonical owner: `access.ledger_strict.undecided`.

Now: `theorem_strict_paths` and `witness_undecided_paths_write_under_strict` ([prove receipt](../../results/platform/20261114T002651Z-prove/receipt.json)): under strict mode the undecided paths' writes commit; marking any of them exempt or covered makes the witness fail (review R3-platform R1-11). Per the sources: embedding, vector-index and BM25 writes are outside the ledger by decision (ADR-0006; spec 213 governs structural writes); BulkLoader and raw SQL, MCP `RunSQL` included (ADMIN_GUIDE §3), are documented exemptions; `bulk_delete_adjacency` and the sample API's Cypher, GraphQL and example mutations are undocumented bypasses ([bug-plt-006](../../bugs_issues.md#bug-plt-006), [bug-plt-005](../../bugs_issues.md#bug-plt-005)); no source decides FHIR sync (`_engine/fhir_graph.py:255-258`, no ledger call in `FHIRGraph.cls`), MCP `CypherQuery` (`MCPTools.cls:9-29`), `set_multigraph`, `Prop_Set`, the `Txn_*`…

Working assumption (agent, unratified): Preserve explicit BulkLoader/raw-SQL/vector exemptions and list undecided FHIR/server paths individually; do not infer exemption from a missing guard.

Options and implications: for each undecided path, (a) exempt like BulkLoader and raw SQL, listed in the docs; (b) refused under strict mode.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-cyp-001"></a>
### When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it?

Status: open owner decision. Canonical owner: `query.graph-scope.bound-create`.

Now: the decision says "`CREATE` writes the default graph" (CONTEXT l. 46-48); the edge insert uses `''` with the bound pair's IDs (`translator.py:10351-10365`); the foreign key `(graph_id, s/o_id) → nodes` (`schema.py:42-43`) refuses it when the default graph lacks those IDs, and when it has nodes of the same IDs the relationship connects those nodes, not the bound ones. The e2e matrix has no such case (`test_460_all_graphs_writes_e2e.py:133-147`) (A-cypher F5).

Working assumption (agent, unratified): Prefer the bound endpoints graph, with ambiguity refused; the actual default-write rule remains a behavior fact pending intent confirmation.

Options and implications: (a) the decision is literal; the error is intended and should name the cause; (b) Cypher's binding wins and the relationship is created in the bound nodes' graph, as `SET`/`DELETE` already do.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-led-005"></a>
### Should callers be able to choose a commit's kind?

Status: open owner decision. Canonical owner: `ledger.commit.kind`.

Now: `commit(changeset, kind=...)` is public (`client.py:381`); a kind other than `"changeset"` skips the empty and size checks, and `"adoption"` applies through `LedgerGenesis.Adopt` (`Ledger.cls:488-509`), so a caller can forge an adoption revision that records changes the tables never had, or label a changeset `redaction` or `genesis` in the history (reconstruction check 2(b)9, correction 9; review R1-core CV-6 and R1-6).

Working assumption (agent, unratified): Treat kind as caller data today while reserving system meaning in analysis; any restricted vocabulary needs an explicit compatibility decision.

Options and implications: (a) make `kind` internal (only verify needs adoption); (b) keep it public and document the skipped checks and the audit meaning of each kind.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-019"></a>
### May the server or the client retry a call that writes?

Status: open owner decision. Canonical owner: `access.retries`.

Now: no document states a retry policy. The HTTP server reruns a failed Cypher call once on a fresh engine, and the SDK's `_post` retries server errors and timeouts ([bug-plt-019](bugs-review.md#bug-plt-019)), so a write can be applied twice; only a ledger commit with an idempotency key is protected. Open statement: [access.retries](../../../ontology/concepts/access.g5.md#access.retries).

Working assumption (agent, unratified): Keep ambiguous write outcomes distinct from known pre-write failure; automatic resend of non-idempotent writes is not presumed safe.

Options and implications: (a) retries are allowed only for reads and for idempotency-keyed commits; (b) retries stay, and writes must be made idempotent; (c) no automatic retries.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-006"></a>
### Should the sample API retry construction after a startup outage?

Status: open owner decision. Canonical owner: `access.health.recovery-policy`.

Now: api.main captures no engine when automatic startup fails, so later health requests remain unavailable even if construction could now succeed. cypher_api leaves failed construction uncached and retries. Actual in-process ASGI neighbors and [health model](../../models/service_health/NOTES.md) derive these distinct histories; no external database recovery was tested and no auto-recovery requirement established.

Working assumption (agent, unratified): Keep current failure visibility after startup outage; retry/rebuild needs a lifecycle policy with bounded attempts and readiness semantics.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-004"></a>
### Should standalone handled metadata calls expose YIELD aliases as result columns?

Status: open owner decision. Canonical owner: `query.system-procedures.alias-policy`.

Now: real persisted A/B labels through db.labels and public execute_cypher give column label for YIELD label AS l, but column l with RETURN l. Bare ORDER BY l refuses; RETURN l ORDER BY l succeeds. [Native empty/nonempty neighbors](../../../uplift/consolidated/iteration-7/procedure-native.json), [qualified model](../../models/procedure_results/NOTES.md). No specific contrary metadata-only requirement was established, so this is not counted as a new bug.

Working assumption (agent, unratified): Prefer declared YIELD aliases at the public reader, while documenting current handled-call names until the owner decides.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-005"></a>
### Should handled WHERE validation happen when no rows exist?

Status: open owner decision. Canonical owner: `query.system-procedures.empty-validation`.

Now: unsupported STARTS WITH and missing parameter both refuse with label data but return an empty projected result when the producer is empty. Structural MATCH still refuses on empty data. Actual Python/SQLite and [native cases](../../../uplift/consolidated/iteration-7/procedure-native.json) agree; [model](../../models/procedure_results/NOTES.md) distinguishes these branches. This exception to a broad refusal description does not establish an intended validation policy.

Working assumption (agent, unratified): Prefer validating a requested WHERE independent of row count; current empty-provider acceptance does not settle intent.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-003"></a>
### Should history text filters use binary identity or the current database comparison?

Status: open owner decision. Canonical owner: `ledger.readers.history.text-policy`.

Now: the Python API calls a correlation filter exact, but persisted fields use ordinary IRIS String columns. Actual native commits/history match ASCII case changes and trailing spaces or tabs, including in raw source JSON; interior JSON spacing still differs. Evidence and raw rows: [native comparison](../../../uplift/consolidated/iteration-6/history-collation-native.json), [spaces](../../../uplift/consolidated/iteration-6/history-collation-spaces-native.json), [interior source spacing](../../../uplift/consolidated/iteration-6/history-collation-interior-native.json). The as-built history_paging model represents both comparison modes; no human policy was inferred.

Working assumption (agent, unratified): Preserve current database comparison for compatibility and expose the difference from binary Python identity; a portable text rule needs owner choice.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-018"></a>
### Which graph do rows of a mapped FHIR SQL table belong to?

Status: open owner decision. Canonical owner: `fhir.sql_mapping.graph_scope`.

Now: mapped SQL tables carry no graph column, so a Cypher query under `USE GRAPH` or across every graph reads the same mapped rows (`cypher/translator.py`; `_engine/fhir.py`). No spec or ADR states the scope; not run natively (FHIR suites skipped on this instance). Open statement: [fhir.sql_mapping.graph_scope](../../../ontology/features/fhir.g5.md#fhir.sql_mapping.graph_scope).

Working assumption (agent, unratified): Treat mapped SQL labels as namespace-global today; assigning every row to a graph needs mapping metadata and migration policy.

Options and implications: (a) mapped rows belong to every graph (today's behaviour, documented); (b) a mapping is made per graph and only that graph's queries read it.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-srch-006"></a>
### Should every fusion entry point use the same text ranking?

Status: open owner decision. Canonical owner: `search.fusion.text_leg`.

Now: the engine and Cypher fusions read a BM25 index built from node properties (`_engine/vector.py:1382-1451`), while the SQL `kg_RRF_FUSE` procedure ranks the documents table by full-text term counts (`schema.py:2484-2560`); the 4.0.0 migration guide calls the documents table the BM25 corpus (`docs/migration/v4.0.0.md:742-751`). Open statement: [search.fusion.text_leg](../../../ontology/features/search.g5.md#search.fusion.text_leg).

Working assumption (agent, unratified): Preserve each current text corpus and rank rule until one common corpus is chosen; common fusion arithmetic alone cannot settle text ranking.

Options and implications: (a) one shared contract for every entry point; (b) two contracts, each documented, with the migration guide corrected.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-002"></a>
### Which ledger readers must refuse while a redaction is unfinished?

Status: open owner decision. Canonical owner: `redaction.batches.readers`.

Now: spec 256 plan "Readers" lists `get_revision`, `diff`, `reconstruct`, `export_reconstruction` (refuse) and `verify()` (`redaction_in_progress`). Probe [redaction_readers_midrun](../../receipts/native/redaction_readers_midrun.json): `get_revision`, `diff`, `reconstruct`, `export_reconstruction` refused; `verify` answered `redaction_in_progress`; `history`, `stats` and the SQL `ledger_records` procedure answered. `history()`, `stats()` and the SQL procedure `ledger_records` answer mid-run with some revisions' metadata already cleared and others not. The refusing readers check the marker once and then page through SQL, so a batch can commit between pages.

Working assumption (agent, unratified): Keep the explicit redaction guards and list unguarded readers; do not infer that partial-redaction answers are acceptable.

Options and implications: (a) only replay-style readers need protection; metadata listings may show a half-done redaction; (b) every record or metadata reader should refuse or read one consistent snapshot.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-005"></a>
### Is an unsalted SHA-256 of a tenant name and of each record acceptable in the redacted history?

Status: open owner decision. Canonical owner: `redaction.tombstone.digest`.

Now: ADR-0013 keeps `sha256(CanonicalRecord)` per tombstone and `sha256(graph NUL match)` in the redaction revision's source and the marker; a salted digest was rejected "for now" (ADR-0013:43, 49). Canonical records contain the entity id, attribute and values; a guessed tenant name or a low-entropy value (a boolean, a known name) can be confirmed by hashing the guess.

Working assumption (agent, unratified): Record the unsalted digest as built and keep its privacy adequacy open; no guessing or confirmability experiment is in scope.

Options and implications: (a) acceptable — the digest is an audit device and the content is already low-sensitivity; (b) unacceptable for regulated erasure — use a keyed digest held outside the namespace.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-006"></a>
### How does an operator end a redaction that cannot finish?

Status: open owner decision. Canonical owner: `redaction.batches.abort`.

Now: once a run has tombstoned anything, the marker stays until that target's run completes. If the target becomes live again, a resumed call is refused at entry (`target_live`, observed in [redaction_interrupt_resume](../../receipts/native/redaction_interrupt_resume.json) step 4), and if it becomes live between the last batch and the final step, the final step refuses (`theorem_completion`; observed natively in the race context: in [redaction_concurrent_targets](../../receipts/native/redaction_concurrent_targets.json) tenant A's run ended with the final step's message "the default graph (ids starting 'tA|') became live again"; the serial case is unobserved; review round2-core R2-5). Meanwhile record readers, verify, commits into the target and every other target's redaction are refused until the content is erased again and the same target is run to completion. There is no abort.

Working assumption (agent, unratified): Assume completion by rerun after fixing liveness; abandonment needs an owner-approved recovery meaning for partial tombstones.

Options and implications: (a) intended — the only safe exit is to finish; (b) an abort that restores nothing (tombstones stay) but releases the marker is wanted for a target that is legitimately back in use.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-007"></a>
### What does erasure's returned count promise?

Status: open owner decision. Canonical owner: `erasure.count`.

Now: CONTEXT.md and ADR-0004 say "a returned 0 means nothing matched". `EraseGraph` returns the number of `nodes` and `rdf_edges` rows removed; labels, properties, documents, vectors, temporal entries, FHIR rows and ledger statements can be removed while it returns 0.

Working assumption (agent, unratified): Treat the present count as a sum of store effects rather than a count of distinct entities; any stronger public count needs a defined unit.

Options and implications: (a) the count means node and edge rows only, and the doc should say so; (b) 0 must mean no store changed.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-str-002"></a>
### Which control characters must a graph name refuse, and who owns the rule?

Status: open owner decision. Canonical owner: `graph.names`.

Now: Python's `validate_graph_name` refuses 0–31 and 127 (`_validate.py:47`); IRIS's `$ZStrip(...,"*C")` also covers 128–159. `witness_python_mirror_admits_c1_control` ([prove receipt](../../results/graph_structure/20261114T000451Z-prove/receipt.json)); [graph_structure_keys](../../receipts/native/graph_structure_keys.json): IRIS refuses 0x01, 0x1F, 0x7F, 0x80, 0x85 and 0x9F and accepts 0xA0 (`p_ctrl`), and in K3 a name with U+0085 passed Python and was refused inside IRIS as SQLCODE -400 "Fatal error occurred", nothing written (A-structure Q4; B-structure O1; review R2-data R1-14).

Working assumption (agent, unratified): Prefer the server GraphKey rule for all new names; control-character normalization versus refusal must be documented consistently.

Options and implications: (a) GraphKey owns the rule and Python asks it (or mirrors it exactly), so the refusal is a clean validation error; (b) keep both, accepting the opaque server error for C1 characters.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-str-003"></a>
### In a multigraph, must create_edge always add a new edge and offer a variant that returns its ID?

Status: open owner decision. Canonical owner: `structure.multigraph.create_edge`.

Now: spec 234 FR-007 says yes to both; the code returns False for an existing triple, `create_edge_returning_id` does not exist, CHANGELOG and API docs are silent, and KNOWN_ISSUES steers users to Cypher (A-structure Q2; R2-data E6).

Working assumption (agent, unratified): Keep direct create as deduplicating at this pin; the specification planned keyed parallel creation, whose public ID-returning interface is unfinished.

Options and implications: (a) FR-007 stands and this is unfinished work; (b) drop FR-007 and document Cypher as the way to add parallel edges.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-str-004"></a>
### Until a ledger reference can name one parallel edge, should the ledger refuse relationship operations on a multigraph triple?

Status: open owner decision. Canonical owner: `structure.multigraph.ledger`.

Now: spec 234 lists the ledger (US4) as not done and FR-013 requires an ambiguous tuple reference to fail; `LedgerApply.FindEdge` takes the first matching row with no ambiguity check (`LedgerApply.cls:144-157, 185-198`), and the delete then breaks the survivors' adjacency ([bug-str-001](../../bugs_issues.md#bug-str-001)) (B-structure open question; R2-data E6).

Working assumption (agent, unratified): Keep the spec requirement to refuse ambiguous ledger references; do not accept first-row selection as intended parallel-edge semantics.

Options and implications: (a) refuse with `ambiguous_tuple` until FR-013 lands; (b) apply to the first row, as today, once the adjacency defect is fixed.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-tmp-002"></a>
### After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?

Status: open owner decision. Canonical owner: `temporal.stats.cut-bucket`.

Now: ADR-0009:49 says statistics "describe the past" after a purge, while `DeleteTemporalEdge` and `EraseNodes` rebuild a bucket from its survivors (`TemporalIndex.cls:446-488`); after `purge_raw_before(tsEnd)` with `tsEnd` mid-bucket, deleting a surviving edge wipes the purged edges from `tagg` but not from `bucket` (A-temporal Q2).

Working assumption (agent, unratified): Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.

Options and implications: (a) the purge rule wins: a cut bucket keeps its history; (b) the rebuild rule wins: statistics describe the survivors.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-tmp-003"></a>
### Must a paged temporal window read show one consistent moment while edges are written?

Status: open owner decision. Canonical owner: `temporal.window.concurrent-writes`.

Now: the window reader pages over live globals, so an edge inserted behind the cursor is missed and pages can mix states; spec 255 addresses only purged events (A-temporal Q5).

Working assumption (agent, unratified): Treat a paged read as multiple observations today; a point-in-time promise needs an explicit snapshot/version protocol.

Options and implications: (a) a live, non-snapshot read is acceptable (document it); (b) a snapshot bound is wanted.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-tmp-004"></a>
### What should an insert collision inside a changeset do?

Status: open owner decision. Canonical owner: `temporal.ledger.insert-collision`.

Now: since spec 254 `InsertEdge` answers 1 for a collision, and `OpCreateTemporalEdge` records `create_temporal_edge` unconditionally (`LedgerApply.cls:635-639`), so a revision claims a temporal edge that changed nothing; the changeset docstring still says "insert (fail if key exists)" (`changeset.py:334-335`) (A-temporal F5).

Working assumption (agent, unratified): Keep insert collision as an effect-free accepted temporal call today; ledger record/no-op policy still needs owner choice.

Options and implications: (a) refuse the changeset, as the docstring says; (b) commit and record nothing for the collided op; (c) keep the record and document that it may describe no change.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-tmp-005"></a>
### Should deleting the last timestamp of a temporal-only predicate keep its old structural row, as a purge does?

Status: open owner decision. Canonical owner: `temporal.optout.drop`.

Now: `witness_delete_and_purge_disagree_when_opted_out` ([prove receipt](../../results/temporal/20261114T001508Z-prove/receipt.json)); [temporal_marked_row_lifecycle](../../receipts/native/temporal_marked_row_lifecycle.json) K4: with the predicate registered temporal-only, deleting the last timestamp retracts the old marked row (`DeleteTemporalEdge` does not read the registry, `TemporalIndex.cls:333-341`), while a purge keeps it until the drop (`:966`; ADR-0015:144-148). Both keep the row rule (A-temporal Q4; B-temporal O3).

Working assumption (agent, unratified): Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately.

Options and implications: (a) the asymmetry is acceptable; (b) delete should follow the purge's "leave registered predicates' rows" rule.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-tmp-006"></a>
### May an explicit delete_edge remove a marked structural row while its triple still has timestamps?

Status: open owner decision. Canonical owner: `temporal.structural.explicit-delete`.

Now: the temporal model's `DeleteEdge` lets an explicit `delete_edge` remove a marked row while timestamps remain, and no source decides the case; ADR-0009 makes a structural predicate's timestamp imply its row (review R2-data R1-7).

Working assumption (agent, unratified): Preserve the temporal implication requirement and record the direct-delete exception; the maintainer must decide whether to refuse or repair it.

Options and implications: (a) an explicit delete wins and the triple stays without a row until its next temporal write; (b) the delete keeps (or re-asserts) the marked row while timestamps remain; (c) the delete is refused.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-srch-002"></a>
### May an undeclared writer add vectors to the default graph's table after a model has claimed it?

Status: open owner decision. Canonical owner: `search.embedding.undeclared_default`.

Now: `witness_undeclared_default_vs_named` ([prove receipt](../../results/search/20261114T000543Z-prove/receipt.json)): an undeclared writer is width-checked only and lands in model A's `kg_NodeEmbeddings` on the default graph, while on a named graph it gets its own route; `embedding_identity.py:85-91` and FR-010 (as quoted in code) say yes; CONTEXT.md says writes at another model are "refused rather than mixed in", a phrase added on 2026-11-04 (`267aaff1`, R039), after 4.0.0 routing, which favours refusal (A-search Q1; review R3-platform R1-9).

Working assumption (agent, unratified): Keep width-compatible undeclared writes to the claimed default table as current compatibility; separate-route enforcement needs an explicit decision.

Options and implications: (a) allowed at the same width (as built); (b) refused, as for a declared different model.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-srch-003"></a>
### May a BM25 search observe an index write that is still in progress?

Status: open owner decision. Canonical owner: `search.bm25.read_isolation`.

Now: searches read `^BM25Idx` with no lock and no isolation (spec 044 FR-019 "Search takes no lock"), so they can read uncommitted or mixed N/df/len; FR-023 guarantees snapshot-like reads only during an upgrade; a search during a Build answers `[]` (A-search Q4; B-search "Not represented").

Working assumption (agent, unratified): Assume no cross-call consistency guarantee until a read/write protocol is chosen; partial-index results remain visible risk, not approved isolation.

Options and implications: (a) acceptable: scores are approximate during writes; (b) searches must see committed state only.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-srch-004"></a>
### Should plain text search use a BM25 index named "default" when one exists?

Status: open owner decision. Canonical owner: `search.bm25.default_index`.

Now: spec 044 FR-012 / US5 (still "Draft") says `kg_TXT` uses `^BM25Idx("default")` when present; `kg_TXT` uses iFind/LIKE over `docs` (`vector.py:917-1054`) (A-search Q3).

Working assumption (agent, unratified): Keep explicit BM25 selection distinct from plain text search; a default-index fallback requires a supported API/corpus decision.

Options and implications: (a) the requirement is superseded; mark the spec; (b) it is unfinished work.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-srch-005"></a>
### In which order must the common-term cutoff list the terms it skipped?

Status: open owner decision. Canonical owner: `search.bm25.cutoff`.

Now: FR-044-C4 says "alphabetical"; the code returns ObjectScript collation order, in which numeric terms sort first (A-search Q6). The rest of the cutoff contract was proved (`theorem_cutoff_contract`, [prove receipt](../../results/search/20261114T000543Z-prove/receipt.json)) and observed as specified ([search_bm25_cutoff](../../receipts/native/search_bm25_cutoff.json)).

Working assumption (agent, unratified): Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact.

Options and implications: (a) collation order is what "alphabetical" means here (document it); (b) plain string order.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-009"></a>
### When the strict-mode guard cannot read the ledger's state, should it allow the write?

Status: open owner decision. Canonical owner: `ledger.strict.fail-open`.

Now: a failed `Meta()` probe caches "never-enabled", so the guard fails open (`ledger/guard.py:55-58`; `witness_failed_probe_admits_a_write`, [prove receipt](../../results/platform/20261114T002651Z-prove/receipt.json)) (B-platform Q3). The related lifetime cache of the class check is decided and registered as [bug-plt-025](../../bugs_issues.md#bug-plt-025).

Working assumption (agent, unratified): Keep failures visible in analysis and prefer fail-closed admission; the current fail-open compatibility behavior is not owner ratification.

Options and implications: (a) fail open, as documented in the code; (b) refuse under uncertainty when strict may be on, and re-probe the class.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-010"></a>
### Should setup still record the schema when some classes failed to deploy?

Status: open owner decision. Canonical owner: `install.setup.failed_deploy`.

Now: the deploy is best-effort (`_engine/schema.py:2578-2595`) and the record is written regardless (`:2309-2312`); the next engine is accepted and its writes fail with `GraphWriteError` (KNOWN_ISSUES:787-807 describes a similar symptom); on a non-default schema, earlier classes compiled for `Graph_KG` keep naming it (A-platform F-S5).

Working assumption (agent, unratified): Prefer no ready schema record after failed deployment; a partial-ready record would need explicit per-capability admission rules.

Options and implications: (a) record anyway and report the failure; (b) withhold the record so the namespace counts as a stopped setup (FR-006a).

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-011"></a>
### May a data migration run before any setup has recorded the namespace's IVG Schema, and on which schema?

Status: open owner decision. Canonical owner: `install.migration.schema.unrecorded`.

Now: the migrations build their engine from `IVG_SCHEMA_PREFIX` or the default and waive the schema check (`engine.py:1887-1890`, whose comment justifies only "may run before any 4.6.0 setup recorded the schema"); with a record that names another schema the waiver is a defect ([bug-plt-007](../../bugs_issues.md#bug-plt-007)). With no record, FR-006a's letter conflicts with the 4.0.0 upgrade's documented order. The 4.0.0 migrations take `schema=` only for the placements; the embeddings and `^KG` steps use the engine's environment or default schema (`upgrade.py:145-152, 259-268`), and none consult `^IVG.Deploy("schema")` (A-platform F-S12; review R3-platform R1-5).

Working assumption (agent, unratified): Require an explicit schema choice before a migration with no namespace record; arbitrary fallback schemas are not an inferred supported policy.

Options and implications: (a) with no record, a migration may run on an explicitly given schema and must not record it; (b) a migration must refuse until a setup records the schema.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-012"></a>
### Does read-only mode govern the MCP tools, and should Bolt honour a driver's read access mode?

Status: open owner decision. Canonical owner: `access.read_only.scope`.

Now: MCP `CypherQuery` writes and `RunSQL` runs anything (`MCPTools.cls:9-69`), with no read-only control (A-platform F-H7); Bolt ignores the access mode (reconstruction check 2(a)13).

Working assumption (agent, unratified): Keep engine read-only guarantees and explicitly list interfaces that ignore access hints; protocol hints and server enforcement need separate decisions.

Options and implications: (a) a read-only IRIS login is the real control and the docs say so; (b) `IVG_READ_ONLY` must cover MCP, and Bolt must refuse writes in a read session.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-013"></a>
### Does a proven reader revision hold for every build and platform of the library?

Status: open owner decision. Canonical owner: `algorithms.proof.build`.

Now: routing ignores the library build and platform (FR-004), while the proof record holds one arm64 build (A-platform F-A6).

Working assumption (agent, unratified): Bind proof evidence to exact library/platform builds until source or owner authority permits broader reuse.

Options and implications: (a) the revision is the contract across builds; (b) routing must also match the proven build.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-014"></a>
### Must the evidence gate also cover the other algorithms the native library speeds up?

Status: open owner decision. Canonical owner: `algorithms.proof.ungated`.

Now: triangle count, SCC, k-core and Leiden use the library through `arno_bridge` with no proof gate and fall back only on a library error (`iris_sql_store.py:3737-3760, 3977-4000`) (A-platform F-A7).

Working assumption (agent, unratified): Do not infer proof coverage for accelerated algorithms absent from the gate; extending its inventory needs provider-specific evidence.

Options and implications: (a) yes, gate them; (b) they are outside the gate by design (document it).

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-015"></a>
### Should native readers work in namespaces other than USER?

Status: open owner decision. Canonical owner: `algorithms.routing.namespace`.

Now: native readers run only in `USER`, while ADR-0016 makes any namespace the isolation unit, so a non-USER install never gets native routing (A-platform F-A9; spec 236 open question).

Working assumption (agent, unratified): Keep non-USER Owner routing as current availability; cross-namespace native support requires a provider deployment/proof contract.

Options and implications: (a) USER only, documented; (b) the library must read the calling namespace.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-016"></a>
### Must a repeated FHIR event leave the graph unchanged?

Status: open owner decision. Canonical owner: `fhir.event.retry`.

Now: `/fhir-event` stamps an event without `date` with the current time, so a repeat writes again; an updated resource's codes never refresh and there is no delete; the governing spec 195 is not in the repository, and the route is due for removal in 5.0 (A-platform F-B9).

Working assumption (agent, unratified): Prefer idempotent repeated FHIR events, while preserving current event behavior as observation; event identity and replay retention need owner choice.

Options and implications: (a) derive the time from the event so retries are harmless; (b) accept it until the route is removed.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-plt-017"></a>
### What should happen when other writers, an erase included, touch a FHIR graph during a sync?

Status: open owner decision. Canonical owner: `fhir.sync.other_writers`.

Now: `erase_graph` does not take `^IVG.FHIRGraph(graph)`, so it can race a full re-derive (A-platform F-B10); no source says whether other writers may touch a FHIR graph.

Working assumption (agent, unratified): Preserve the documented single-sync restriction and keep competing non-sync writers unestablished; choose serialization or conflict detection explicitly.

Options and implications: (a) the FHIR graph belongs to the sync alone and other writes are refused; (b) other writes, an erase included, take the sync's lock.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-cyp-002"></a>
### In shadow mode, should a native failure be raised instead of answered by SQL?

Status: open owner decision. Canonical owner: `query.shadow.native-failure`.

Now: FR-007 (fallback) and FR-006 (raise on a difference) both hold; in shadow mode a native exception is still answered by SQL with one warning (`query.py:2144-2152`), so a native defect that raises is invisible to a shadow run, TCK shadow runs included; shadow mode never compares compiled with interpreted (only `test_257_compiled_plans_e2e.py` does) (A-cypher F11).

Working assumption (agent, unratified): Keep SQL fallback as the current shadow behavior; fail-fast diagnostic mode remains an unratified alternative.

Options and implications: (a) raise in shadow mode (stricter checks); (b) keep the fallback, as specified.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-cyp-003"></a>
### Should a bulk load by another process close the native query path while indexes lag the rows?

Status: open owner decision. Canonical owner: `query.native.index-current`.

Now: the native gate (FR-014) is per engine (`native_plan.py:530`); `BulkLoader` writes `%NOINDEX %NOCHECK`, commits per batch and rebuilds `^KG` at the end (`bulk_loader.py:1-12, 157-163`), so other engines' native reads see `^KG` and `pkprops` behind the rows; spec 253 research §H names the trap (A-cypher F7).

Working assumption (agent, unratified): Prefer closing native admission during index-bypassing load; a cache/probe that misses that interval cannot justify current-index reliance.

Options and implications: (a) no: equal answers assume current indexes (document it); (b) a load publishes a namespace-wide marker that `native_gate` checks.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-cyp-004"></a>
### Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?

Status: open owner decision. Canonical owner: `query.conformance`.

Now: at the baseline (Python 3.11.18, driver 5.3.2) three tests in `tests/unit/test_shortest_path.py` fail: `RETURN p` arrives as a dict and the tests call `json.loads` on it (`:164, 186, 219`), raising "the JSON object must be str … not dict"; `PRE_RELEASE_CHECKLIST.md:282` records the unit suite green with drivers 5.4.0/5.4.1 on Python 3.12 and 3.13.

Working assumption (agent, unratified): Prefer a consistent structured path value; driver/path-dependent text is current behavior requiring a compatibility decision.

Options and implications: (a) the representation changed (driver or execution path) and the tests are stale; (b) a path must always come back as JSON text, and the dict is a regression on this driver or path.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-cyp-005"></a>
### Should a call to an unknown apoc, db or dbms procedure be refused?

Status: open owner decision. Canonical owner: `query.system-procedures.unknown`.

Now: the `db.*`/`dbms.*`/`apoc.meta.*`/`gds.*` stubs exist, and an unknown `apoc`/`db`/`dbms` name answers no rows and no error (`engine.py:1039-1740`), while an unknown `ivg.*` or `gds.*` procedure is refused (reconstruction check 2(a)4, correction 21).

Working assumption (agent, unratified): Prefer a clear unknown-procedure refusal; preserve present empty results as observed compatibility until the owner decides.

Options and implications: (a) answer empty for Browser compatibility; (b) refuse, as for `ivg.*`.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-led-001"></a>
### Which copy of a record must an auditor keep to recompute its tombstone digest?

Status: open owner decision. Canonical owner: `redaction.tombstone.digest-source`.

Now: `MutationRecord.from_row` normalizes graph `"\x00"` to None (`replay.py:56-74, 137-142`) while `CanonicalRecord` emits `"\u0000"` (`Ledger.cls:595-596`), and key and number formatting may differ; exports carry no records, and the canonical form is not specified outside `Ledger.cls` (A-history F18; reconstruction check G12).

Working assumption (agent, unratified): Treat auditor-held original canonical records as required to recompute digests; the product does not promise a retained recoverable preimage.

Options and implications: (a) the server's canonical record captured before the redaction is the only valid preimage (document it, and how to capture it); (b) the public reader must reproduce the canonical form exactly.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-led-002"></a>
### Should the redaction receipt name IVG's own snapshot archives and the ledger rows an upgrade left behind?

Status: open owner decision. Canonical owner: `redaction.out-of-reach.other-copies`.

Now: `save_snapshot` archives hold `^IVG.Ledger` and the ledger storage (ADMIN_GUIDE:989-991), so restoring an earlier archive brings back tombstoned content and `idem` bindings; after an R114 upgrade the 4.5.x `Graph_KG` ledger rows "stay where they are" (`legacy.py:612-613`) with uncleared metadata. The receipt's out-of-reach list names neither (`LedgerRedact.cls:505-508`) (A-history F8).

Working assumption (agent, unratified): List snapshots and legacy ledger copies as outside redaction reach; archive-retention/removal policy remains an owner decision.

Options and implications: (a) name them in the receipt's out-of-reach list; (b) redaction must also reach them (refuse or rewrite archives it knows of; clear the legacy rows).

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-led-003"></a>
### What should disabling the ledger do while a redaction is unfinished?

Status: open owner decision. Canonical owner: `ledger.lifecycle.disable-during-redaction`.

Now: `disable` takes no head lock and has no caller-transaction refusal; its behavior while a redaction marker exists was not checked (reconstruction check G38). Re-enabling afterwards skips the adoption silently ([bug-led-004](../../bugs_issues.md#bug-led-004)).

Working assumption (agent, unratified): Prefer refusal of disable during unfinished redaction; resumption and blocked readers require a deliberate lifecycle rule.

Options and implications: (a) refuse `disable` while a redaction is unfinished; (b) allow it, and define what the marker means while the ledger is disabled.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-led-004"></a>
### How should the ledger's genesis record a node ID that two graphs hold?

Status: open owner decision. Canonical owner: `ledger.lifecycle.genesis.shared-ids`.

Now: genesis scans `nodes`, `rdf_labels` and `rdf_props` with no graph (`LedgerGenesis.cls:17-36`), so an ID held by two graphs gives two `create_node` records and one merged set of labels and properties; how replay and verify fold them was not checked (reconstruction check 2(b)8, G8).

Working assumption (agent, unratified): Keep namespace-wide bare node IDs in current genesis behavior; graph-specific ledger identity would require a record/migration decision.

Options and implications: (a) acceptable: ledger nodes are graph-blind by design; (b) genesis should record one node per (graph, ID) or refuse.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-led-006"></a>
### Must verify compare one consistent moment of the ledger and the tables?

Status: open owner decision. Canonical owner: `ledger.verify.consistency`.

Now: `verify()` checks the redaction marker once, reads the ledger and the tables with no lock, and commits an adoption without `expected_head` (`replay.py:806-858`; A-ops hazard (c)2; review R1-core R1-6). The race with a redaction is registered as [bug-led-001](../../bugs_issues.md#bug-led-001); with ordinary commits running, a verify can report differences that existed at no single moment.

Working assumption (agent, unratified): Treat verify as requiring quiescent inputs for reliance until a consistent-view protocol is specified; unlocked multi-scan behavior is not a snapshot proof.

Options and implications: (a) verify is best-effort; run it when writes are quiet (document it); (b) verify reads under the head lock, or retries until the head did not move.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-001"></a>
### How should flat node reads preserve colliding property aliases?

Status: open owner decision. Canonical owner: `structure.node.read.aliases`.

Now: The linked canonical owner and preserved register evidence describe current behavior.

Working assumption (agent, unratified): Preserve both accepted property values and structural identity; reserve aliases or introduce a property map only after a compatibility choice.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-con-001"></a>
### Must the streaming history reader bound its memory, or only its delivery?

Status: open owner decision. Canonical owner: `ledger.readers.bound`.

Now: `reconstruct(..., stream=True)` folds every record into one in-memory state and only then yields its entities (`ledger/replay.py:550-566`); the entity bound is enforced only when `stream=False` (`:555-556`), as the contract says (`specs/213-graph-revision-ledger/contracts/ledger-api.md:30`). `export_reconstruction` passes no bound and also materializes the whole state before writing NDJSON (`ledger/client.py:731-739`), while the contract says it "streams to NDJSON; never bounded" (`ledger-api.md:31`). The requirement text behind the bound (FR-035 to FR-037) is not in the repository. Classification: settled as built (the bound applies to the materialized reader only; neither reader bounds memory); what was promised needs ratification.

Working assumption (agent, unratified): Keep delivery streaming separate from bounded-memory guarantees; full materialization is current behavior and a memory promise needs a separate bound.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-002"></a>
### Must reconstruction's bound concern each intermediate graph or only the requested graph?

Status: open owner decision. Canonical owner: `ledger.readers.bound.policy`.

Now: The linked canonical owner and preserved register evidence describe current behavior.

Working assumption (agent, unratified): Prefer an explicit peak reconstruction bound; current per-intermediate graph checks do not settle a final-graph-only policy.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-con-002"></a>
### Is a ledger diff an ordered script or an unordered set of net changes?

Status: open owner decision. Canonical owner: `ledger.readers.diff.order`.

Now: `compute_diff` sorts entries by kind, ID and attribute (`ledger/replay.py:406-407`, `:535`); for one node deleted and re-created in the range the two existence entries tie and keep their forward order, so the inverse lists the creation before the deletion ([unit probe](../../results/unit-probes/20261115T043637Z-l2-inverse-order/receipt.json)). The contract calls the diff "sorted net, lifecycle-aware" (`ledger-api.md:29`). Classification: needs ratification. Working answer: an unordered set of net changes (the contract's "net"), in which case order does not matter but the reverse diff's attribute values still do ([bug-led-101](bugs-review.md#bug-led-101)). Alternative: an ordered script that a client may apply, which would require the inverse to reverse the order of tied entries. Lead L2 of the reviewed plan. Iteration 3 attaches this decision to canonical ledger.readers.diff.order. Producer…

Working assumption (agent, unratified): Treat lifecycle diff as an unordered net-change result until a stable script order is specified; consumers must not infer dependency order.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-007"></a>
### Should weighted shortest path consider every parallel edge or the lowest-key representative graph?

Status: open owner decision. Canonical owner: `algorithms.op.paths.weighted.parallel`.

Now: USER_GUIDE631-644 promises cheapest path by edge weight. Spec234 FR004 mandates the lowest-key scalar leaf, while its FR015/clarifications explicitly discuss collapse for Arno/PPR/BFS rather than weighted Dijkstra. Actual DijkstraJson reads only scalar leaves. The valid mode-on native fixture in [weighted-native.json](../../../uplift/consolidated/iteration-9/weighted-native.json) has ekey0/weight10 and ekey5/weight1, plus a two-edge alternative of cost4: both native path and cost-only routes return4, whereas the whole stored multigraph has a cost1 path. [Independent source/intent review](../../../uplift/consolidated/iteration-9/weighted-projection-review.md) distinguishes this from the earlier mode-off harness-oracle miss. Plausible answers: define weighted paths over the lowest-key projection for compatibility, stating that graph to callers; or optimize over all parallel rows, changing the reader…

Working assumption (agent, unratified): Keep the current lowest-key representative route distinct from all-parallel-edge shortest path; the optimization domain needs owner choice.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="q-iter-008"></a>
### Should tiny positive PPR scores share the rounded zero tie or always precede true zeros?

Status: open owner decision. Canonical owner: `algorithms.op.ppr.zero_ties`.

Now: USER_GUIDE550-552 and rank_key define ties at12 decimal places; USER_GUIDE593 says unscored zeros come after scored nodes. The actual native/store append/early-cut reader and the fallback full-map sort implement different answers when positive1e-13 rounds to0. The [six-case native panel](../../../uplift/consolidated/iteration-10/root-ppr-tie-native.json) retains a limit2 selected-set difference and matching limit1/larger-score/later-zero neighbors. [Independent review](../../../uplift/consolidated/iteration-10/root-ppr-review-intent.md) finds no source assigning precedence between these two statements. Plausible answers: use one rounded-score/ID ordering over every node, including zeros; or put every genuinely scored positive node before unscored nodes and apply rounded ties within that group. No choice is made. [bug-plt-103](bugs-review.md#bug-plt-103) is the independent route inconsistency, which…

Working assumption (agent, unratified): Preserve the rounded-score tie rule today; giving every positive raw score priority over true zero would change top-k admission.

Options and implications: Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.

Settling evidence: A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0001"></a>
### How to read "defined by its ancestors or an earlier same-level statement"

Status: settled existing authority. Canonical owner: method/historical evidence; no new product owner.

Now: The original uplift applied lexical scope (inspected: `ontology_index.py:438-450`); under it the gate passed. Under the literal rule the original modules have 1392 out-of-scope statement/term pairs in 1002 statements (check, this lane; the ontology lane's strengthened checker counts 1406 violations including 11 plural forms and 3 other kinds). The completion's repaired copy passes the literal rule with 0 violations (ontology lane, bdcea01f).

Working assumption (existing authority): Method definitions use the literal parent-chain/earlier-same-parent rule. This is a workflow question, not a product contract.

Authority: [experiment/playbook-uplift/verification-playbook.txt](../../../../experiment/playbook-uplift/verification-playbook.txt); history bfb6f097. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0101"></a>
### Should an engine that cannot read the schema record be refused?

Status: open owner decision. Canonical owner: `install.schema.refusal.first-use-policy`.

Now: A readable record naming another schema refuses the engine on first access (IVGSchemaError). If reading ^IVG.Deploy raises anything else, the engine logs a WARNING and is accepted unchecked, so an engine for another schema can run in the namespace. Evidence: live: intent-a-hd0101-unreadable-record; inspected: iris_vector_graph/engine.py:1847-1868

Working assumption (agent, unratified): Supported deployments can read the record (premise: the ADMIN_GUIDE role table grants %Native_GlobalAccess:U). Under that premise a mismatch is refused. The documented fail-open path is a separate 'unchecked' outcome that admits a mismatched engine. It is outside the binding guarantee and should be modelled that way, not treated as an accepted engine.

Options and implications: - (b) refuse like a mismatch until the record is readable (fail closed) - (c) fail open for reads, refuse writes - narrow the skip to the documented privilege error and refuse on any other exception

Settling evidence: A maintainer statement or spec clause that fail-open on an unreadable record is intended (would make the documented skip supported), or one that requires refusal (b/c).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0102"></a>
### Should setup save the schema record when the class deploy failed or was turned off?

Status: open owner decision. Canonical owner: `install.setup.failed_deploy`.

Now: initialize_schema writes ^IVG.Deploy('schema') after any non-dry run that has a Native API, including runs where the class deploy raised, a class failed, or auto_deploy_objectscript=False. The failure appears only in the reply (warnings / objectscript_failed). With the record present, the first-access check accepts every engine for that schema. Evidence: inspected: iris_vector_graph/_engine/schema.py:2309-2313,2578-2596; inspected: iris_vector_graph/schema_name.py:220-235

Working assumption (agent, unratified): Treat a stored schema name as a namespace binding only. Represent readiness of each deployed capability (classes, adjacency index, ledger, erase) separately. An engine accepted by the record check has no claim on feature readiness. A feature call on a class-less namespace must give a named failure, not silently degrade.

Options and implications: - (b) record only when objectscript_deployed and objectscript_failed is empty - (c) record, but mark it incomplete so the first-access check names the missing classes

Settling evidence: A maintainer statement that the record attests a completed install (would favour b/c), or that DDL-only namespaces are a supported mode (would confirm a).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0103"></a>
### Are the files under sql/ part of the product?

Status: open owner decision. Canonical owner: `install.legacy.support-policy`.

Now: initialize_schema loads none of sql/. The sdist ships sql/ without its loaders. scripts/deploy_production.py, maintained in 4.7.0 but neither documented nor packaged, runs sql/schema.sql + sql/operators_fixed.sql. scripts.setup.load_fraud_data loads sql/fraud_sample_data.sql for the demo. The other files have ad-hoc or no loaders. Evidence: inspected: pyproject.toml:181-183; scripts/deploy_production.py:43-65; tested: tests/unit/test_470_scripts_tcp_run.py:245-255

Working assumption (agent, unratified): Inventory both install paths. The product contract (spec 262 schema, inventory test) covers initialize_schema only. scripts/deploy_production.py + sql/schema.sql + sql/operators_fixed.sql form a reachable legacy path that produces a non-conforming namespace (DDL-only before its class step, unqualified procedures). sql/fraud_sample_data.sql is maintained demo data. Files with no loader are historical material.

Options and implications: - (a) keep as historical samples, marked as such - (b) delete them and the scripts that load them - (c) bring them in line with the IVG Schema (or have deploy_production call initialize_schema)

Settling evidence: A maintainer statement that deploy_production.py is a supported production installer (then sql/schema.sql and operators_fixed.sql are product and violate spec 262), or a removal decision.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0201"></a>
### What does a Python read with no graph argument read?

Status: open owner decision. Canonical owner: `graph.default.python-read-policy`.

Now: get_node, get_nodes and the counters (R219/R249) read the default graph. get_node_ids_by_label, get_node_ids_by_property, get_property_pairs, get_property_values, property_value_exists, get_node_ids_like, count_subjects_with_property and nodes_exist read every graph. get_nodes_by_label and get_nodes_by_property mix the two scopes. delete_node with no graph acts on the holding graph or refuses. Evidence: live: intent-a-hd0201-unscoped-readers; inspected: iris_vector_graph/_engine/nodes_edges.py:760-966,2227-2252,2590-2625

Working assumption (agent, unratified): For graph-aware Python reads, omission selects the default graph. Keep the all-graph id helpers as separate discovery operations with their scope visible. Never hydrate ids from one scope with another scope's records. Model delete_node's 'holding graph or refuse' rule as its own documented operation.

Options and implications: - (a) every reader takes graph=, omitted is the default graph (USER_GUIDE rule) - (b) omitted reads every graph and each row names its graph (Cypher all-graphs rule) - (c) keep id-only readers all-graphs and document them as exceptions

Settling evidence: A maintainer decision that the id-only readers are intended all-graph exceptions (c), or a fix that gives them graph= (a).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0202"></a>
### In a multigraph, does a direct edge delete remove one parallel edge or all of them?

Status: settled existing authority. Canonical owner: `structure.edge.delete`.

Now: delete_edge(s, p, o, graph=g) deletes every row of the triple in g (all parallel edges) and the ^KG entry, returning True. There is no edge_id/ekey argument. A single parallel edge can be deleted only through Cypher DELETE r. Evidence: live: intent-a-hd0202-multigraph-delete; inspected: iris_vector_graph/_engine/nodes_edges.py:1382-1433

Working assumption (existing authority): Without an edge ID, direct delete_edge removes the whole triple. A per-edge ID argument is planned, absent at the pin.

Authority: [specs/234-multigraph-parallel-edges/plan.md](../../../../specs/234-multigraph-parallel-edges/plan.md); history 128007c0. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0301"></a>
### Does ledger strict mode cover the standalone bulk loader?

Status: settled existing authority. Canonical owner: `install.bulk_load.ledger`.

Now: BulkLoader writes nodes, labels, properties and edges with no strict-mode check and no revision. verify() then reports those writes as unrecorded. Raw SQL is likewise unguarded. Evidence: inspected: iris_vector_graph/bulk_loader.py; specs/213-graph-revision-ledger/contracts/ledger-api.md:82-93

Working assumption (existing authority): The standalone BulkLoader and raw SQL are expressly outside the client strict-mode guard. That exception does not exempt other engine writers.

Authority: [specs/213-graph-revision-ledger/contracts/ledger-api.md](../../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); history 04bf1c67. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0302"></a>
### May a direct edge delete remove an edge row that a temporal edge still implies?

Status: open owner decision. Canonical owner: `temporal.structural.explicit-delete`.

Now: delete_edge(s, p, o, graph=g) deletes the triple's rows whether marked ({"temporal":true}) or adopted, and their ^KG entries. The temporal events stay, so get_edges_in_window still returns the edge while MATCH/adjacency readers no longer see it. A later purge removes the timestamps. Evidence: live: intent-a-hd0302-temporal-row-delete; tested: tests/e2e/test_254_purge_e2e.py:322-327

Working assumption (agent, unratified): For structural predicates, a triple with surviving timestamps keeps a structural row. A direct delete may remove the explicit assertion, but the row must stay (or revert to marked) while timestamps remain. Model as-built option (a) as the baseline that violates the implication, and keep the ADR-0015 temporal-only opt-out separate (no row ever).

Options and implications: - (a) delete the row and leave the temporal events (as built; maintainer-tested) - (b) refuse while the triple has temporal events and the row is marked - (c) delete the row and the triple's temporal events together - (d) leave a marked row alone and delete only an explicit one (an adopted row reverts to marked)

Settling evidence: A maintainer statement on whether delete_edge is allowed to break the temporal implication (confirms a), or a fix choosing b/c/d.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0401"></a>
### How should erase and rebuild retire a source generation?

Status: open owner decision. Canonical owner: `structure.degree.cache.retirement-policy`.

Now: Erase paths (RemoveSource, RemoveGraph, RemoveAll) and the non-indexed rebuild kill ^KG("gen") with ^KG("degc"); later writes restart the counter, so it returns to earlier values. Adj.Degree stores a recount only if its lock probe succeeded and gen is unchanged, then re-reads gen. Live: gen 2 before erase, undefined after, 2 again after rewriting the same edges, on both erase_graph and delete_node; single-process degree answers stayed correct. The cross-process window (probe before the writer's lock, count after the kill, with tGen=0 or an ABA refill) was not exercised live. Evidence: live `intent-a-hd0401-gen-return`; inspected `iris_src/src/Graph/KG/Adj.cls:55-90`; inspected `iris_src/src/Graph/KG/Adjacency.cls:376-377,437,461,824-830`

Working assumption (agent, unratified): Unchanged from decisions.md: invalidation can never make an old degree-cache value valid again; model a monotone generation or a fresh graph epoch across erase and rebuild; keep as-built A (kill) as the baseline with its narrow window.

Options and implications: - A: keep the kill and document the narrow window (erase/rebuild concurrent with degree readers) - B: step the generation with $Increment and kill only degc (a residue counter per erased source remains) - C: keep the kill, add a graph/namespace epoch stepped by every kill to each entry and to the reader's check

Settling evidence: A maintainer statement that erase/rebuild require no concurrent degree readers (A becomes the documented contract), or that erasure must leave no per-node residue (rules out B, leaves C).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0402"></a>
### May two adjacency rebuilds run at the same time?

Status: open owner decision. Canonical owner: `structure.adjacency.rebuild-concurrency`.

Now: Two ^KG rebuilds are admitted concurrently (shared lock only); two ^NKG rebuilds are serialized by ^IVG.NKGBuild (wait up to NKGBUILDWAIT=900 s, then raise). Not observed: the end state of two overlapping ^KG rebuilds. Non-indexed path: each kills and refills ^KG in its own transaction; an IRIS rollback of one restores pre-images (killing nodes the other set) - IRIS premise, not checked here. Indexed path: two %BuildIndices over the same index - IRIS behaviour not established. Evidence: live `intent-a-hd0402-two-rebuilds`; inspected `iris_src/src/Graph/KG/TraversalBuild.cls:30-70,281-303`

Working assumption (agent, unratified): Unchanged: at most one publishing rebuild per adjacency structure; a second call waits or gets a documented busy result. Refined: ADMIN_GUIDE's sentence is literally about ^NKG and holds live; the ^KG half is unserialized.

Options and implications: - A: allowed as today (last full fill wins) and documented - B: serialize with an exclusive ^KG build lock like ^IVG.NKGBuild - C: refuse a second call with a clear busy error - D: prove convergence of concurrent rebuilds including rollback

Settling evidence: A maintainer statement that sync() is an operator action assumed single-flight (A documented), or a test/proof that two overlapping BuildKG runs (one rolled back) leave ^KG equal to the rows.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0501"></a>
### Are the end nodes a temporal write creates governed by the ledger?

Status: open owner decision. Canonical owner: `temporal.structural.ledger-nodes.policy`.

Now: With the adjacency index, every structural temporal write (engine path, changeset op, and strict mode) inserts missing endpoint rows in the edge's graph plus a marked edge row; no create_node is recorded; strict mode does not refuse. verify() skips the marked row but reports the endpoint nodes as unrecorded_writes; reconstruct() omits them; a later purge_raw_before (retire_bare_nodes=True default) deletes them, also unrecorded. Evidence: live `intent-a-hd0501-temporal-endpoints`; inspected `iris_src/src/Graph/KG/Adjacency.cls:575-613`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:613-641`

Working assumption (agent, unratified): Engine-path endpoints: derived, with identifiable provenance (e.g. the 'bare temporal endpoint' rule purge already uses) and excluded from genesis/verify; changeset temporal ops: follow the relationship endpoint rule (refuse a missing endpoint or record a stub). Keep their real effects in the environment model; treat ledger-api.md:92 as stale for the indexed path.

Options and implications: - (a) record create_node for endpoints a changeset temporal op creates; strict mode refuses an engine temporal write with missing endpoints - (b) mark endpoints as derived (column/registry or 'bare temporal endpoint' rule) and leave them out of genesis and verify - (c) a temporal write never creates nodes; callers pre-create them, as create_rel requires - (d) document them as unrecorded writes (status quo)

Settling evidence: A maintainer statement whether the 'temporal mirror' of 43efd473 includes its endpoint nodes; or a decision that temporal endpoints must pre-exist when the ledger is on.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0502"></a>
### Is the temporal index inside the ledger's guarantee?

Status: open owner decision. Canonical owner: `temporal.ledger.scope-policy`.

Now: A changeset temporal op is recorded (create_temporal_edge, entity id s|p|o@ts, value {s,p,o,graph}); weight (3.5), attrs and mode are not recorded. Replay/reconstruct/verify ignore temporal records and the temporal index. Engine temporal writes, delete_edge_temporal and purge_raw_before make no revision and are allowed in strict mode; the purge retired 4 endpoint node rows unrecorded. Evidence: live `intent-a-hd0502-temporal-scope`; tested `tests/integration/test_ledger_us11_temporal_coexist.py:59-88`

Working assumption (agent, unratified): Unchanged reading: record the changeset temporal op in history (audit, redaction); treat temporal tiers, engine temporal writes, purges and temporal replay as outside the structural replay guarantee; model their real effects, including purges deleting endpoint nodes.

Options and implications: - (a) outside: audit trail only, and amend the glossary to say so - (b) inside for changeset writes: records carry weight/attrs/mode; replay rebuilds and verify compares temporal edges - (c) fully inside: ops for temporal delete/purge, engine temporal writes refused in strict mode

Settling evidence: A maintainer statement that 'subject to the revision ledger' means audit only (status becomes supported for (a)), or a requirement that reconstruct reproduce temporal edges (then (b)).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0601"></a>
### Are the IVF, tree (VecIndex) and PLAID indexes inside the erasure promise?

Status: open owner decision. Canonical owner: `search.erasure.indexes.coverage-policy`.

Now: erase_graph removes rows, ^KG, temporal data and the graph's route table, but leaves ^IVF, ^VecIdx and ^PLAID untouched: ivf_search, vec_search and plaid_search keep answering the erased ids, and ^IVF keeps all their vectors. Evidence: live `intent-a-hd0601-index-erasure`; inspected `iris_src/src/Graph/KG/Eraser.cls; iris_src/src/Graph/KG/GraphStores.cls:28-131`

Working assumption (agent, unratified): Unchanged: model retained index contents as observable after erasure unless purged; graph-owned indexes require invalidation or deletion on erase; caller-fed indexes need an explicit owner/exposure statement. Refined with the graph-derived (IVF) vs caller-fed (VecIndex, PLAID) split.

Options and implications: - (a) record each index's source graph and drop or prune it inside the erase - (b) declare them caller-managed derived stores outside erasure; document and require a rebuild - (c) refuse to build them over a named graph - (d) erase marks dependent indexes stale and searches refuse until rebuilt

Settling evidence: A maintainer statement that vector indexes are caller-owned (then (b) plus inventory entries), or that ivf_build(graph=) makes the index part of the graph (then (a)/(d)).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0602"></a>
### May an index build be seen half-done, and may a stopped build leave a partial index?

Status: open owner decision. Canonical owner: `search.scope.indexes.publication-policy`.

Now: Live: during a real ivf_build rebuild, 35 of 44 concurrent searches answered fewer than the 300 indexed vectors (min 7), with no error; a rebuild killed mid-way left an index answering 12 of 300 and Info showing indexed=0. VecIndex.Build and PLAIDSearch.Build have the same kill-and-refill shape (inspected, not run). Evidence: live `intent-a-hd0602-ivf-partial`; inspected `iris_src/src/Graph/KG/VecIndex.cls:157-163; PLAIDSearch.cls:4-6`

Working assumption (agent, unratified): Unchanged: readers see a complete published index or a clear unavailable result, including after an interrupted rebuild; the existing partial-build behaviour is the modelled baseline.

Options and implications: - (a) build under a temporary name and swap it in at the end - (b) per-index lock plus a 'building' marker searches refuse - (c) keep today's behaviour and document an offline (quiesced) rebuild - (d) a generation flag readers check before and after

Settling evidence: A maintainer statement that index builds are offline operations (then (c) documented), or a contract like ^NKG's.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0603"></a>
### Should the vector-and-graph search keep its k best candidates?

Status: open owner decision. Canonical owner: `search.fusion.vector-graph-policy`.

Now: Candidates (vector hits, their 1-hop neighbours, text hits) go through a Python set; the first k in set order are kept, then sorted by vector similarity. Live: with 4 vector hits and 40 zero-scored neighbours, k=2 never returned the top-2 (12/12 hash seeds); the 1.0-similarity hit never appeared; 5 runs returned only 0.0-scored neighbours. Evidence: live `intent-a-hd0603-vgs-topk`; inspected `iris_vector_graph/_engine/vector.py:1484-1543`

Working assumption (agent, unratified): Unchanged: the reviewed ranking contract is the best k of the scored candidate set with defined ties; the documented set-order truncation is the baseline (now confirmed live).

Options and implications: - (a) score every candidate and keep the top k - (b) keep the vector hits first, then fill with expansion and text hits - (c) keep today's documented behaviour - (d) a documented approximate candidate budget with its own claim

Settling evidence: A maintainer statement that the R025 wording is the intended contract (then (c) is supported), or a fix with a test.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0604"></a>
### May two embed queue workers run at once?

Status: open owner decision. Canonical owner: `search.embedding.queue.processing.consumers`.

Now: ClaimPendingBatch is a read-only scan; two IRIS processes calling it were handed the same 3 entries, which stayed PENDING. Nothing prevents the IRIS task and a Python worker (or two Python workers) from working the same entries: double model calls, last-writer-wins vectors, DONE/ERROR status races. Evidence: live `intent-a-hd0604-queue-claim`; inspected `iris_src/src/Graph/KG/EmbedQueue.cls:112-134`

Working assumption (agent, unratified): A single active consumer per namespace is the contract (supported by 5bb149ed); model both workers as independently schedulable, treat single-worker as an unenforced premise, and prefer enforcement (refuse a second worker) or documentation; atomic claims with recovery remain the multi-worker alternative.

Options and implications: - (a) atomic claim (CLAIMED with owner and time, under a lock) used by both workers - (b) refuse a second worker (namespace lock held while a worker runs) - (c) document single-worker as an operator rule (premise P-0606)

Settling evidence: A maintainer request for multi-worker throughput (then (a)), or a decision that documentation suffices ((c)).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0701"></a>
### Must a BM25 Build (and Drop) exclude writers and be all-or-nothing?

Status: open owner decision. Canonical owner: `search.bm25.write_lock.build-policy`.

Now: Build: `Kill ^BM25Idx(name)`, then per-document writes with no lock and no transaction, header and `schema=2` last; neither Build nor Drop takes the writer lock or checks `upgrading`. Live (intent-a-hd0701-build-drop-lock): with the lock held by process A, B's `bm25_insert` waited 2.0 s and raised "locked by another writer" (FR-019 holds), B's `bm25_build` returned in 1 ms and `bm25_drop` in 0 ms (index gone under a held writer lock). `bm25_build(idx, [" "])` passes `BM25BuildInput`, kills the complete previous index and returns `indexed 0` with no header (`Info` `{}`, search `[]`).

Working assumption (agent, unratified): Serialize Build, Drop, Insert, Delete and Upgrade per index and publish a complete generation or return unavailable, including after a crash; a Build that is refused or indexes nothing must not destroy the previous index. Model the as-built (unlocked Build/Drop, Kill-first) separately as the baseline. Same as decisions.md.

Options and implications: 1. Build and Drop take the writer lock and set a "building" flag that refuses writers (Search answers unavailable). 2. Build under a temporary name and swap it in under the lock (old generation stays visible; crash leaves the old one). 3. Keep today's behaviour with a documented, testable premise: no other writer on that index while Build/Drop runs.

Settling evidence: A maintainer statement scoping ADR-0007 to Insert/Delete (then alternative 3 with a documented quiet-index premise), or an ADR/FR naming Build and Drop.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0702"></a>
### Which reciprocal-rank-fusion rule is the product's?

Status: open owner decision. Canonical owner: `search.fusion.absent`.

Now: Three rules on five surfaces: engine/operators `kg_RRF_FUSE` (missing at `len+c`, BM25-index text leg), SQL `kg_RRF_FUSE` and `/hybridSearch` (missing at 10^9, kg_TXT term counts), `ivg.retrieve` and `RRFFusion` (missing adds 0). Live (c=60; vector leg kg_KNN_VEC top 10 W, X, v3..v10; text leg only Z): engine W, X, v3, Z, ...; SQL W, Z, X, ...; RRFFusion W = Z, then X. Each surface matches its own written rule.

Working assumption (agent, unratified): Preserve and test each surface's rule, including missing-rank handling and which text list it reads; document that the engine method and the SQL procedure of the same name differ. Introduce a single formula only with a versioned contract. Same as decisions.md.

Options and implications: 1. Standard RRF everywhere (missing adds 0; matches RRFFusion, ivg.retrieve and, within 1e-9, the SQL procedure). 2. Per-surface rules, each documented (working assumption). 3. The engine rule everywhere (the only one pinned by a test). 4. A versioned common fusion API, old surfaces kept as-is.

Settling evidence: A maintainer choosing a common rule, or declaring one surface canonical (e.g. making the SQL procedure "the same as" the engine method in fact as the operators documentation already claims for the shim).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0703"></a>
### Is spec 044's kg_TXT-to-BM25 fallback still wanted?

Status: open owner decision. Canonical owner: `search.bm25.default_index`.

Now: `kg_TXT` tries the iFind index (scores = occurrence counts, graph-scoped) and on an iFind error falls back to LIKE (score 1.0, WARNING). It never reads `^BM25Idx`. Live: with docs rows in `ia-0703` and a BM25 index named `default` built for `ia-0703`, kg_TXT answered `[(d1, 2.0), (d2, 1.0)]` before and after the build (BM25 would give 0.69/0.38), no fallback warning; the default-graph call answered `[]`.

Working assumption (agent, unratified): Model kg_TXT as iFind-then-LIKE (documented as-built). Record FR-012/US5/SC-004 and tasks T034/T035 as a spec/doc conflict (S3, F-0708), not as a current obligation the pin fails. If the fallback returns, it applies only on the LIKE path, only to an index whose recorded graph equals the requested graph, never across graphs. Why changed: decisions.md called this Supported on spec 044 FR-012, SC-004 and PR #8. Those establish the 2026-04 feature, not that it is still wanted: the Draft spec is the only post-removal carrier, it was copied wholesale with the schema-2 amendment, and the maintainer's later kg_TXT redesign (v2.18.2, US7, docstring, generated API reference) excludes it. No source "supersedes" FR-012 explicitly either, so neither reading is supported; the assumption follows the newer, user-facing contract.

Options and implications: 1. Implement FR-012 with the BM25 index recorded for the requested graph (decisions.md's former answer). 2. Strike FR-012/US5/SC-004 from spec 044 and fix tasks T034/T035 and the T035 test name. 3. Leave the spec as Draft (status quo; the conflict stays).

Settling evidence: A maintainer statement striking or reaffirming FR-012, or a spec amendment.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0704"></a>
### Is `__stop__` a reserved BM25 index name?

Status: open owner decision. Canonical owner: `search.bm25.name-policy`.

Now: `bm25_build`, `bm25_insert` and `bm25_drop` accept `__stop__`. Live: Build wrote `cfg`, `tf`, `df`, `doc`, `len` subtrees under the stopword node; Tokenize then drops those five words from every index in the namespace (a fresh index over "doc review cfg memo" / "len tf df notes" found nothing for `doc` or `len`, and `bm25_insert(..., "doc len")` returned False). Drop deleted the stopword list (re-created by the next tokenize). Insert into `__stop__` again mixed an index into the list. The node was restored exactly (it was undefined before the run).

Working assumption (agent, unratified): Reserve `__stop__`: public BM25 entry points (`bm25_build/insert/delete/drop/upgrade`, `BM25BuildInput`, index handles, `kg_BM25`/`ivg.bm25.search`) refuse it; the embedded registry walk skips it. Model the as-built acceptance as a defect against the documented stopword list (cross-index). Moving the list to its own global is the compatible alternative mechanism.

Options and implications: 1. Refuse `__stop__` in every BM25 writer and in `BM25BuildInput` (no migration). 2. Move the stopwords to their own global (needs a migration of existing namespaces). 3. Leave as is (as-built; the documented 77-word list can change silently).

Settling evidence: A maintainer statement that `__stop__` is a usable index name (contradicting R165), or a move of the stopword list.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0705"></a>
### Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?

Status: open owner decision. Canonical owner: `search.fusion.python.support`.

Now: Live: `TextSearchEngine(conn, schema="Graph_KG").extract_entity_names` and `search_with_context` answered `ia0705:x` from both `ia-0705a` and `ia-0705b` (2 and 4 rows; the label join on `s` alone duplicates) although the default graph holds neither; `search_documents` failed with SQLCODE -30 (`SQLUSER.DOCS` not found), fell back, failed again and returned `[]` while `kg_TXT(graph="ia-0705a")` found the row. `RRFFusion.fuse_results` gives a missing item 0. HybridSearchFusion's text leg is graph-scoped (graph b: `[]`).

Working assumption (agent, unratified): Treat the three as compatibility surfaces and qualify each: RRFFusion is a pure standard-RRF helper (document that its rule differs from engine `kg_RRF_FUSE`, HD-0702); HybridSearchFusion is de facto public (migration guide) and graph-scoped; TextSearchEngine is exported but reads every graph and its document search cannot reach the IVG Schema, so it is not a supported reader of graph-scoped data. Prefer deprecation with migration advice (to `kg_TXT` / `bm25_search`) or a `graph=` argument; do not remove without a compatibility decision. Same direction as decisions.md.

Options and implications: 1. Bring all three under the graph-scope and failure rules and list them in API_REFERENCE. 2. Deprecate (warning on construction) with migration advice. 3. Remove from `__all__` (breaking).

Settling evidence: A maintainer statement of the public API scope (API_REFERENCE extended to exported classes, or a deprecation note).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0801"></a>
### Where and how should ledger strict mode refuse a Cypher write?

Status: open owner decision. Canonical owner: `ledger.strict`.

Now: Strict mode is a client-side Python check (LedgerGuard) per engine, consulted on the Cypher SQL write route; it caches Meta() for 5 s and treats a failed probe as 'never-enabled'. Live: after another engine turned strict on (Meta strict=true), an engine whose cache was 0.13 s old accepted a Cypher CREATE and a create_node; a fresh engine and the same engine after 5.6 s were refused; verify() reported the bypassing rows as divergence. Evidence: live: intent-a-hd0801-strict-cypher-window; run: intent-a-hd0801-unit-ledger-guard; inspected: iris_vector_graph/ledger/guard.py:20,38-80; inspected: iris_vector_graph/_engine/query.py:2299-2300

Working assumption (agent, unratified): Take the contract text as intended: strict refuses with no window. Record the 5 s cache window (reproduced live) and fail-open (tested) as product defects against ledger-api.md (F-0801), and keep their obligations open. Downstream modules (erasure, redaction, verify) may not assume that every graph-table change under strict mode has a ledger record. verify() detects bypass rows after the fact. Raw SQL and BulkLoader remain outside by the contract's own text (HD-0301/1103).

Options and implications: - (a) keep the client check; document the 5 s window and fail-open in ledger-api.md and USER_GUIDE - (b) fail closed and re-read strict on every guarded write (one class call per write) - (c) server-side enforcement (Txn_Begin check or table triggers), which also covers raw SQL/BulkLoader (new contract; see HD-1103)

Settling evidence: A maintainer statement accepting the TTL as the contract (amending ledger-api.md) would turn the live result into documented behaviour. A server-side check would move this to HD-1103's assurance target.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0802"></a>
### Does a mapped label belong to every graph?

Status: open owner decision. Canonical owner: `query.graph-scope.read.mapped-label-policy`.

Now: table_mappings has no graph key. The translator applies the USE GRAPH predicate to the graph tables only, so a mapped label answers every row of its table under every scope (live: count 2 and both property values under USE GRAPH 'ia-0802-a' and 'ia-0802-none'). Native Cypher declines mapped labels. Evidence: live: intent-a-hd0802-mapped-label-scope; inspected: iris_vector_graph/cypher/translator.py:719-779,14827-14830; inspected: iris_vector_graph/_engine/fhir.py:88-145

Working assumption (agent, unratified): Treat a mapping registration as namespace-wide (the as-built baseline). Under a named USE GRAPH scope, require either graph-aware mapping provenance or an explicitly documented exception. Model the current global visibility as a known deviation from the glossary's isolation rule. It is not a security breach, because the namespace is the boundary (USER_GUIDE:467-468).

Options and implications: - (a) mapped labels answer under every scope, documented as an exception - (b) a mapping names its graph; other scopes see no rows - (c) refuse a mapped label under USE GRAPH with a named graph

Settling evidence: A maintainer statement or a spec giving table mappings a graph, or a USER_GUIDE line declaring mappings namespace-wide.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0803"></a>
### Is `sql/operators.sql` product code?

Status: open owner decision. Canonical owner: `install.legacy.sql-operators-policy`.

Now: operators.sql is shipped in the sdist and loaded by nothing. A namespace set up by initialize_schema holds schema.py's graph-scoped Graph_KG procedures, never operators.sql's (live). kg_GRAPH_PATH and kg_RERANK have no SQL routine. The legacy deployer loads operators_fixed.sql. Evidence: live: intent-a-hd0803-operators-sql-deployed; inspected: pyproject.toml:181-183; inspected: scripts/deploy_production.py:65

Working assumption (agent, unratified): Classify sql/operators.sql as shipped historical/reference SQL with no deployment path. It is outside the executed product surface, but stays in the inventory as a shipped artifact whose definitions are not graph-scoped. Trace operators_fixed.sql (legacy deployer) and the schema.py procedures separately. If anyone runs the file by hand, it creates unqualified, graph-blind procedures (F-0820-like behaviour).

Options and implications: - (a) delete it (and other unloaded sql/ files) - (b) keep as reference, mark as not deployed - (c) regenerate from schema.py (graph-scoped) and load it

Settling evidence: A maintainer statement or a CHANGELOG/README line declaring sql/ historical (then supported), or a decision to restore it as an install path.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0804"></a>
### Should `CREATE CONSTRAINT` / `CREATE INDEX` be refused rather than accepted as a no-op?

Status: open owner decision. Canonical owner: `query.browser-metadata.ddl-notice-policy`.

Now: The nine DDL prefixes return an empty result with no error and no metadata warning, and create nothing. A duplicate of a declared-unique value is stored. SHOW CONSTRAINTS does not list the requested constraint, so a caller who checks can find out. With read_only=True the DDL raises PermissionError. Evidence: live: intent-a-hd0804-constraint-noop; inspected: iris_vector_graph/_engine/query.py:1886-1895; tested: tests/unit/test_query_unit.py:101-106

Working assumption (agent, unratified): Treat the accepted DDL as an acknowledged no-op that establishes no invariant (supported by f4a13d75 and pinned by tests). Model no uniqueness guarantee from it. As a proposed strengthening, not a decision: document it in USER_GUIDE beside the parse-error rule and add a metadata warning. Refusal (option c) would reverse a maintainer decision.

Options and implications: - (a) keep the silent no-op and document it - (b) answer with a warning in metadata - (c) refuse with an error saying IVG keeps no constraints

Settling evidence: A later maintainer statement or spec requiring refusal or warnings for unsupported DDL. A TCK/compatibility requirement that conflicts with the no-op.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0901"></a>
### Should a running engine notice a revoked table right or a dropped adjacency index?

Status: open owner decision. Canonical owner: `query.native.privileges.recheck-policy`.

Now: Three facts are cached per engine: SELECT on the four tables (_native_privileges, never re-asked), the adjacency index kind (_adjacency_indexed, reset only by initialize_schema), and the executor plan version. Exec.Run checks only the plan version. Not exercised live: a REVOKE or a DROP INDEX on product tables would modify the shared namespace (the drop recompiles the table class), which lane rules forbid. Evidence: inspected: iris_vector_graph/engine.py:559-586,704-723; inspected: iris_vector_graph/cypher/native_plan.py:524-539; inspected: iris_src/src/Graph/KG/Cypher/Exec.cls:33-50

Working assumption (agent, unratified): Split the question. (1) A SQL REVOKE is not guaranteed to reach running engines' native reads. To cut native access, revoke the database resource or %Native_ClassExecution, or start new engines. Treat FR-011's executor-side check as an unimplemented spec requirement (F-0908) whose amendment is the maintainer's call. (2) For the route capability, keep FR-003: native reads require the index to be declared at the time of the read. Model an out-of-band drop under running engines as a premise violation ('the index is not dropped while engines run'), not a supported transition, unless Run checks Indexed().

Options and implications: - (a) keep per-engine caches; document that a revoke or index drop needs new engines - (b) re-ask on a timer or every N reads - (c) check privileges in Exec.Run per process and user (FR-011 literally; closes F-0908) - (d) check Graph.KG.Adjacency.Indexed() inside Run

Settling evidence: A maintainer amendment of FR-011 to the shipped design (settles the privilege half as (a)), or an executor-side check (c/d). A supported IVG operation that drops idx_edges_adj would make the index half a real transition, not a premise.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0902"></a>
### Should shadow mode fail when the native path raises an error?

Status: open owner decision. Canonical owner: `query.shadow.native-failure`.

Now: In shadow mode a native exception makes _try_native return None. The SQL path answers, nothing is compared, one WARNING per reason is logged, and the native-answer counter does not move (live, fault injected in the probe process). A wrong native answer raises NativeMismatch. Evidence: live: intent-a-hd0902-shadow-native-exception; inspected: iris_vector_graph/_engine/query.py:2069-2077,2146-2152,2226-2249

Working assumption (agent, unratified): Keep ordinary SQL fallback. In shadow validation, record a native exception as an unsuccessful comparison: raise in shadow mode, or count failures and report them at the end of the run. Require a clean comparison (not a fallback) before claiming parity. The FR-010 default flip and the 3896/3896 figure establish only that no compared answer differed.

Options and implications: - (a) keep the fallback in shadow mode (today) - (b) raise in shadow mode only - (c) count native failures and report them at the end of a shadow run without raising

Settling evidence: A maintainer statement that shadow mode is only a difference detector and that the native-planned share (US3) is the coverage metric would make (a) the contract. A shadow-run report of native fallbacks would make (c) the contract.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0903"></a>
### What may a native read answer while another writer's transaction is open?

Status: open owner decision. Canonical owner: `structure.write.reader-isolation-policy`.

Now: Native reads take no lock or snapshot and read ^KG, the label and property stores at moments spread over the walk. Live: while writer A's transaction was open, B's native read and B's SQL-path read agreed at every step. Both saw A's uncommitted edge before its far node's label (unlabelled [b], labelled []), then the label, and nothing after A's ROLLBACK. Evidence: live: intent-a-hd0903-native-read-open-txn; inspected: iris_src/src/Graph/KG/Cypher/Exec.cls:33-50

Working assumption (agent, unratified): Allow the observed interleavings on both paths: a native or SQL read may see a writer's uncommitted writes, including part of one transaction, and loses them on rollback. Grant snapshot or all-or-nothing visibility only to paths with an explicit synchronization contract and evidence (none for Cypher reads). The ADR-0012 degree cache is the one guarded structure.

Options and implications: - (a) dirty per-store reads, documented as equal to the SQL path's default isolation - (b) readers wait on a lock writers hold (cost: every native read) - (c) a version/epoch check before and after the walk, retrying when a writer committed in between (does not cover uncommitted writes)

Settling evidence: A maintainer statement promising committed-only or atomic visibility for Cypher reads, or a change of the engine connections' isolation level (then native and SQL could diverge, F-0909).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-0904"></a>
### Should a compiled plan that fails while running be set aside?

Status: open owner decision. Canonical owner: `query.compiled.fallback.failure-policy`.

Now: Exec.RunA calls the compiled Walk1 without a catch. A run-time error (a generator defect, or a class deleted outside DropAll while its entry stays 'ok') leaves Run. The engine answers the read on the SQL path with one warning per reason per engine, and the entry stays 'ok', so each later read of that shape fails natively first. Not run live: exercising it needs a compiled IVGC class, which lane rules forbid (Gen mode is off in every probe). Evidence: inspected: iris_src/src/Graph/KG/Cypher/Exec.cls:153-199; inspected: iris_src/src/Graph/KG/Cypher/Gen.cls:61-106; inspected: iris_vector_graph/_engine/query.py:2146-2152

Working assumption (agent, unratified): Treat a run-time failure of a compiled entry as a fallback outcome: quarantine the entry for that plan generation (as a failed build already is), let the interpreter answer, and retry only after invalidation (a new stamp, DropAll or a deploy). SQL fallback for every later read (as built) is a correct-answer but degraded baseline that violates ADR-0014's 'answers exactly as the interpreter'.

Options and implications: - (a) keep today's behaviour (SQL answers, one warning per reason per engine) - (b) catch errors from Walk1 in RunA, mark the entry failed and re-run the walk interpreted - (c) mark the entry failed but let SQL answer this read

Settling evidence: A maintainer statement that SQL fallback is the intended recovery for compiled failures, or an amendment of ADR-0014's invariant to exclude run-time faults.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1001"></a>
### What should `random_walk` answer, and over which graph?

Status: open owner decision. Canonical owner: `algorithms.op.walks.result-policy`.

Now: Without the library (this container): random_walk answers [] (no error). With the library the engine calls NKGAccel.RandomWalkJson unchanged; that ObjectScript walk, called directly after engine.sync(), walked from a seed id shared by the default graph and graph ib1_rw_g to both graphs' neighbours. The library only gates the call; the walk is not the library's. Evidence: live `ib-HD1001-random-walk`; inspected `iris_vector_graph/_engine/algorithms.py:658-678`; inspected `iris_src/src/Graph/KG/NKGAccelTraversal.cls:187-222`; tested `tests/integration/test_nkg_accel_no_library.py:89-92`

Working assumption (agent, unratified): Walk the default graph's adjacency (graph key 0) in ObjectScript, library or not (option (a)). Where only a merged ^NKG route is available and a named graph has edges, refuse visibly rather than answer [] or a merged walk. An explicit graph= argument (option (c)) is a compatible extension. Changed from decisions.md: **yes**. decisions.md asked for a declared scope plus an observable 'unavailable' result. The deployed ObjectScript walk runs without the library (upstream test and live), and ADMIN_GUIDE says every algorithm has an ObjectScript answer. So a real default-graph answer is the better-supported reading. 'Unavailable' remains only for a route that cannot honour the scope.

Options and implications: - (b) library-only, refusing once a named graph has edges (as the ^NKG procedures do) - (c) add graph= and walk that graph's ^KG - (d) retire random_walk - keep [] without the library and document it as an Arno-only sampling helper (docstring as contract), still fixing the graph scope

Settling evidence: Confidence: medium. A maintainer statement that random_walk is an Arno-only sampling helper, like ArnoAccel.KhopSampleJson, which answers empty without the library. That would make [] the contract and leave only the graph-scope defect. A spec for random walks would also settle it.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1002"></a>
### Should label propagation say when its labels did not settle?

Status: settled existing authority. Canonical owner: `algorithms.op.cdlp`.

Now: On the path a->b->c, kg_CDLP(max_iterations=k) for k=1..6 alternates between two labelings with period 2. The answer is a plain {node: label} dict with no convergence key, warning or flag. Evidence: live `ib-HD1002-cdlp-oscillation`; inspected `iris_vector_graph/_engine/algorithms.py:829-848`

Working assumption (existing authority): CDLP returns its last fixed iteration without an in-band settledness flag; the documented diagnostic compares k with k+1.

Authority: [docs/COMMUNITIES.md](../../../../docs/COMMUNITIES.md); history af2bc84e. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1003"></a>
### Should the shortest-path routines refuse a direction they do not walk?

Status: open owner decision. Canonical owner: `algorithms.op.paths.direction`.

Now: Edge x->y. ShortestPathJson(y,x,'in') and (y,x,'sideways') answer [] silently. ShortestLength(x,y,'in') and (x,y,'sideways') answer 1, a false positive, and ShortestLength(y,x,'in') answers -1. DijkstraJson refuses 'sideways'. IRISGraphStore.shortest_path_length(x,y,'in') answers 1, but execute_shortest_path(x,y,'in') answers none. The engine's Cypher (y)<-[*..5]-(x) is correct (length 1) through the caller guard. Evidence: live `ib-HD1003-path-direction`

Working assumption (agent, unratified): Keep the public 'in' semantics, caller reversal included. Require ShortestPathJson and ShortestLength to refuse any direction outside {out, both}, or to implement 'in' by walking from the far end. Require IRISGraphStore.shortest_path_length to reverse 'in' as execute_shortest_path does. Record the live false positive as a defect against its docstring. Changed from decisions.md: **yes**. Status moves from assumption to supported: maintainer commit 99b00ce9 states the refuse-outside-set policy for ObjectScript entry points. New live evidence shows a wrong positive answer, not just a missing one, on a public store method.

Options and implications: - (a) CheckDirection in both class methods and 'in' walked from the far end - (b) keep the guard at the callers and document the class methods as internal (conflicts with 99b00ce9) - refuse 'in' at the class level and reverse in every Python caller, including shortest_path_length

Settling evidence: Confidence: high. A statement that TraversalPaths' shortest-path methods are internal and exempt from the 99b00ce9 policy. Even then, the store method's docstring discrepancy remains.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1004"></a>
### How many nodes should global PageRank list?

Status: settled existing authority. Canonical owner: `algorithms.op.pagerank`.

Now: The owner, called exactly as _execute_pagerank calls it with 10,050 edgeless ids, returns 10,000 rows whose scores sum to 0.995025. The native-route ranking (_ranked_rows(rows, 0)) keeps all 10,050. Evidence: live `ib-HD1004-pagerank-cap`; inspected `iris_src/src/Graph/KG/PageRank.cls:506-520`

Working assumption (existing authority): Global PageRank promises every default-graph node on every supported route; the hidden Owner output cap violates that documented contract.

Authority: [iris_vector_graph/_engine/algorithms.py](../../../../iris_vector_graph/_engine/algorithms.py); history f3451567. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1101"></a>
### What should a node change do when only a named graph holds the id?

Status: open owner decision. Canonical owner: `ledger.node-scope.missing-default-policy`.

Now: Live, `ib-HD1101-namedonly` (AUDITIB, ids only in graph `ib3_g1101`, genesis after): `create_node` refused `node_exists`; `upsert_node` with no labels committed a revision with zero records; `set_prop` committed and wrote a default-graph `rdf_props` row with no default-graph node row (orphan); `add_label` refused "insert label failed" (`fk_labels_node`); `remove_label` refused `label_not_present`; strict `delete_node` committed a `delete_node` record with prior `{"labels":[],"props":{}}` and removed nothing. `verify()` then answered `diverges`/`unrecorded_writes` for the undeleted node after ledger-only commits. This is option (c), F-1105 reproduced live.

Working assumption (agent, unratified): Keep graph-blind existence. A node change that needs the default-graph row (`set_prop`, `remove_prop`, `add_label`, `remove_label`, `delete_node`, `upsert_node` with labels or properties) refuses with nothing applied and no record when that row is absent, under a reason distinct from `node_not_found` (the maintainer's meaning of that code stays). Model edge endpoint lookup separately (`EnsureEndpoint`). Changed from decisions.md: **yes, refined**: the refusal outcome is kept, but it is not an existence failure; the existence semantics are now supported by a maintainer commit.

Options and implications: - (b) Materialise the default-graph node row with a recorded `create_node` before the change (consistent with graph-blind identity plus default-graph ownership; `delete_node` would still need a rule). - (c) Keep the as-built behaviour and document orphan rows, FK refusals and no-op deletes. - Graph-qualified node records (record-layout change, linked to HD-1304/HD-1401).

Settling evidence: As built: high (live). Intent: medium. A maintainer statement choosing materialisation, or a decision that ledger node identity is the default-graph row (scoped existence), would change the working assumption.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1102"></a>
### Should disable() and set_strict() refuse a caller's open transaction, as enable() does?

Status: open owner decision. Canonical owner: `ledger.lifecycle.settings-transaction-policy`.

Now: Live, `ib-HD1102-txn-rollback` (caller `START TRANSACTION` + INSERT, `$TLEVEL` 1): `enable()` refused `LedgerTransactionOpenError` on both topologies. `disable()` and `set_strict(False)` were accepted on both. Plain engine: the caller's ROLLBACK restored `state=enabled`, `strict=True` (joined). Second-process engine (from_connect topology): `disabled` and `strict=False` survived the ROLLBACK (committed outside the caller's transaction). In both, another process read the uncommitted `disabled` inside the transaction, and on the plain engine the guard cached the rolled-back `strict=False` and let a guarded `create_node` write within its 5 s TTL.

Working assumption (agent, unratified): Refuse `disable()` and `set_strict()` inside a caller transaction on every engine, as `enable()`/`redact()`. Changed from decisions.md: **no** (strengthened). The live run adds a reason: ledger lifecycle state is global and read dirty by other processes, so a joined toggle that is later rolled back has already changed what other writers and guards did.

Options and implications: - (b) Join via `WriteTxn.native()`; preserves the plain engine's current behaviour but exposes the dirty-read window and stale guard cache seen live. - (c) Document the engine-dependent outcome.

Settling evidence: As built: high (live). Intent: medium. A maintainer choice of join for lifecycle calls would change it.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1103"></a>
### Should strict mode be enforced by the server, or stay a Python-only check?

Status: open owner decision. Canonical owner: `ledger.strict.server-policy`.

Now: Live, `ib-HD1103-guard-ttl` (pass): under strict, `create_node` is refused; an engine whose guard cached "not strict" wrote immediately after another process set strict, and was refused after 5.5 s; raw SQL writes. Live, `ib-HD1103-bulk-delete-adjacency` (fail): `bulk_delete_adjacency` deleted an edge row under strict and `verify()` then diverged (F-1108).

Working assumption (agent, unratified): Treat strict mode as a client-side, cached (5 s), fail-open guard on the contract's listed calls at this pin; inventory uncovered Python paths, server writers (Eraser, TemporalIndex, FHIR sync, SQL procedures) and external writers as possible unrecorded writers. Changed from decisions.md: **no**.

Options and implications: - (b) Server-side barrier in the ObjectScript writers or table triggers (changes operational compatibility). - (c) Fail closed when the strict state cannot be read (changes behaviour for mocks and pre-deployment engines, which the docstring names as the reason for fail-open).

Settling evidence: High. A maintainer statement that strict mode promises "no unrecorded writes" namespace-wide would make (b) the contract.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1104"></a>
### Should the ledger's settings be changeable after the genesis?

Status: open owner decision. Canonical owner: `ledger.lifecycle.settings-policy`.

Now: Live, `ib-HD1104-settings` (pass, predictions confirmed): `enable(strict=True, max_ops=7, recon_bound=11)` on an enabled ledger changed nothing; `disable(); enable()` reset strict to False; `set_strict(True)` on a disabled ledger was accepted and lost on the next `enable()`; re-enable kept `max_ops=50000`, `recon_bound=250000` and took strict from its argument.

Working assumption (agent, unratified): Keep `max_ops` and `recon_bound` fixed at genesis. Model strict as set by `enable(strict=...)` on genesis and on every re-enable (default False) and by `set_strict`; record the reset on re-enable as an explicit transition and do not assume strict survives a disable/enable cycle. Changed from decisions.md: **no**.

Options and implications: - (a) Setters, or `enable()` updating the settings passed and preserving strict when not passed (needs `strict: Optional[bool] = None`, a signature change, because `False` and "not passed" are indistinguishable today). - (b) Fixed at genesis with the strict reset documented.

Settling evidence: As built: high. Intent: medium. Publication of spec 213 FR-001/FR-001b/FR-042 text, or a maintainer statement on strict across re-enable, would settle it.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1105"></a>
### Should post-commit properties be recorded by the ledger?

Status: open owner decision. Canonical owner: `ledger.commit.post-commit.recorded`.

Now: Live, `ib-HD1105-approach-a` (pass): a commit with `{ib3_p1: {audit: $REVISION_ID}}` wrote the property with no record in the revision; `verify()` reported it as `unrecorded_writes`. Live, `ib-HD1105-replay-reapplies` (fail): after a governed `set_property(ib3_p1, audit, "manual")`, a retry with the first key returned `replayed=True` and wrote the old value back over the governed one.

Working assumption (agent, unratified): Treat post-commit properties as a separate direct write outside revision replay; `verify()` reports them until adopted. Require that a replayed commit not re-apply them (idempotency contract), recording the pin's re-application as a defect (F-1101). Changed from decisions.md: **no**.

Options and implications: - (a) Record them as `set_prop` records of the same revision (server substitutes the revision id). - Skip post-commit properties on `replayed=True` only (keeps Approach A; closes F-1101). - (c) Drop the feature.

Settling evidence: High. A maintainer decision to fold them into the revision would change the working assumption.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1201"></a>
### Should a graph erasure take the ledger head lock?

Status: open owner decision. Canonical owner: `erasure.concurrency`.

Now: No erase path takes the head lock. Live: an erase_graph(gA) left open inside a caller transaction ($TLEVEL 1); a redact(gA) from a second process saw 0 live rows (uncommitted deletes), tombstoned 2 records, passed its final re-check (also a dirty read) and wrote its audit revision. The caller rolled back: gA has its 2 node rows and its edge again, its ledger statement entry is restored while the statement's create record is a tombstone, no record names gA, and verify() reports unrecorded writes on the gA relationship. The F-1201 commit/erase interleaving itself remains model-only (it lies inside one ObjectScript method). Evidence: live `ib-HD1201-open-erasure`; inspected `iris_src/src/Graph/KG/Eraser.cls:47-261, 1117-1144`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:202-210, 409-415`

Working assumption (agent, unratified): Serialize erasure with ledger commits and redaction on the same lock: the erasure holds the head lock until its outermost transaction ends (an IRIS lock released inside a transaction is held to its end, P-0003), AND the redaction's opening liveness check and marker run under that lock (HD-1301). Neither alone closes the open-erasure case: with only the erasure lock the dirty opening check still passes and the batches tombstone a target the erasure later restores; with only the locked opening check the erasure holds nothing to wait on. A liveness check that reads committed data only is an alternative to the erasure lock for the redaction half, but not for the F-1201 statement half. Changed from decisions.md: **yes**. Refined. decisions.md proposed 'initially model the ledger head lock'. The new live probe shows the open-erasure case is reachable through the public API (erase_graph inside…

Options and implications: - (a) erasure holds the head lock for its whole transaction (with HD-1301's locked start) - (b) document that erasure needs a quiet graph (no concurrent commit, redaction, or open caller transaction) and refuse erase_graph inside a caller transaction, as 4.7.0 refuses redact() - (c) a graph-scoped lock shared by erasure, commits touching that graph, and redaction of that graph - (d) redaction's liveness checks read committed data only (covers the redaction half, not F-1201)

Settling evidence: Confidence: medium. A maintainer statement that erasure is an offline/quiescent operation (then (b) with an enforced refusal) or that erase_graph is not supported inside a caller transaction; evidence that IRIS SQL in the redaction's process reads committed data (would remove the redaction half).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1302"></a>
### Which rule clears a revision's free text: any tombstone or every record?

Status: settled existing authority. Canonical owner: `redaction.metadata`.

Now: Any tombstone in a revision clears its four free-text fields; other tenants' records in the revision stay byte-identical. Evidence: inspected `iris_src/src/Graph/KG/LedgerRedact.cls:345-377`; tested `tests/integration/test_256_ledger_redaction_e2e.py:295`; run `experiment/playbook-completion/preparation-evidence.md selected-live.log (pin, pre-repair, prior container)`

Working assumption (existing authority): Decision 2 clears the free text when any record in the revision is tombstoned. The older every-record wording is stale.

Authority: [docs/adr/0013-redaction-removes-content-from-history.md](../../../../docs/adr/0013-redaction-removes-content-from-history.md); history 42907b21. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1303"></a>
### Can an unfinished redaction be abandoned, and what may a default-graph target touch?

Status: open owner decision. Canonical owner: `redaction.batches.abort`.

Now: (a) No abandon or cancel operation; re-running the same target resumes; a target that became live makes the final step refuse (target_live) and keep the marker, so commits into the target are refused and other targets cannot start until the operator erases the target again; PurgeAll is the only other way out and destroys the whole ledger. (b) redact(None) without a prefix checks default-graph rows only and tombstones every node record, including nodes live in named graphs (genesis-recorded). Evidence: live `ib-HD1303-nopfx-default`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:89-112, 143-178, 409-441`; live `original 9c3719c1 scenario default_graph_without_prefix`

Working assumption (agent, unratified): (a) No generic abandon: tombstones are irreversible, so 'abandon' could only remove the marker and accept a permanently divergent history; the recovery is re-erase and resume, and the docs should say that this also erases content re-created during the run. An explicit, audited cancel that records the partial redaction as a redaction revision is the alternative. (b) Apply the plan's graph-blind liveness check to every default-graph target, so redact(None) without a prefix is refused while any node of any graph is live. Changed from decisions.md: **yes**. (b) upgraded from assumption to supported: plan.md:10, committed with the accepted ADR in 2b8ea46d, states the graph-blind rule, and the code comment gives its reason; the working answer becomes 'graph-blind liveness' rather than 'refuse unless ownership can be established'. (a) unchanged; added the plaintext-marker consequence…

Options and implications: - (a1) audited cancel operation that removes the marker and writes a redaction revision for the partial run - (a2) document re-erase-and-resume as the only recovery (as built, undocumented outside the error text) - (b1) graph-blind liveness for every default-graph target (plan.md:10) - (b2) refuse redact(None) without a prefix outright

Settling evidence: Confidence: medium. (a) a maintainer decision on a cancel operation; (b) a statement that plan.md:10 was meant for prefix targets only.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1304"></a>
### How is a tenant's node history redacted when nodes live in the tenant's own graph?

Status: open owner decision. Canonical owner: `redaction.tenant.node-history-policy`.

Now: Nodes in a per-tenant graph with unprefixed ids: erase_graph(gA) + redact(gA) completes (1 relationship record tombstoned); the tenant's node ids and property values stay in the node records; the receipt says complete and lists only exports/journals/backups as out of reach; verify() diverges (2 differences); a prefix call cannot express the tenant. Evidence: live `ib-HD1304-graph-per-tenant`; inspected `iris_src/src/Graph/KG/LedgerGenesis.cls:14-36; LedgerApply.cls:215-251`

Working assumption (agent, unratified): Require tenant id prefixes for ledger-governed tenants and document it next to redact(); for a graph target whose erased nodes left graph-blind node records, return an explicit incomplete result (or refuse) instead of complete=true. Model graph-qualified node records for future history separately; a migration of existing history needs trustworthy provenance, which the genesis did not keep. Changed from decisions.md: **no**. Same choice; added the R290 maintainer statement, the genesis attribution contradiction, the receipt (FR-008) gap and fresh live evidence including the FR-007 divergence.

Options and implications: - (a) record the node's graph in node records (layout change; existing graph-blind history stays ambiguous) - (b) require and document tenant id prefixes; flag or refuse unattributable graph targets - (c) graph-only tenant erasure via a provenance migration that reconstructs node graphs from trusted sources

Settling evidence: Confidence: medium. A statement from the maintainer (or opsreview, the requester) that tenant ids always carry a prefix, which makes (b) a documentation fix; or a decision to change the record layout.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1305"></a>
### Should a replayed commit apply its post-commit properties?

Status: settled existing authority. Canonical owner: `ledger.idempotency`.

Now: Post-commit properties are applied on every successful commit response, replayed or not, as a separate SQL transaction outside the head lock. See probe results. Evidence: live `ib-HD1305-retry-revives`; live `ib-HD1105-replay-reapplies`; inspected `iris_vector_graph/ledger/client.py:402-487`

Working assumption (existing authority): A keyed replay returns the original outcome and applies no new effects. How to complete or skip post-commit work is an implementation question; recording those properties remains separately open.

Authority: [specs/213-graph-revision-ledger/contracts/ledger-api.md](../../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); history contract and existing idempotency tests. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1401"></a>
### Verification and record readers: node identity and redaction checks

Status: open owner decision. Canonical owner: `ledger.lifecycle.genesis.shared-ids`.

Now: (a) verify compares node ids across graphs while ledger node ops act on the default graph only. (b) readers check the marker once before a lazy paged read; see probe. Evidence: live `ib-HD1401-reader-full-race`; live `ib-HD1101-namedonly`; inspected `iris_vector_graph/ledger/client.py:687-739; replay.py:231-269, 588-606, 806-835`

Working assumption (agent, unratified): (a) Compare the identity the ledger governs: default-graph node rows for node records (R290), with named-graph node rows either reported as outside node governance or recorded with their graph (linked to HD-1101/1304). (b) A reader takes a redaction epoch that every redaction start and finish advances, checks the marker, reads, and re-checks both; if either changed it refuses or retries. A post-read marker check alone is not sufficient (a whole redaction can complete inside one read); a shared lock or a genuine snapshot are alternatives. Verify additionally needs a coherent cut between its record read and its table read. Changed from decisions.md: **yes**. (b) the mechanism changes: decisions.md left 'epoch validation, locking or snapshots' open and the original reviewed model used a second marker check; the new live probe shows a complete redaction inside one paged read (default page…

Options and implications: - (a1) verify becomes graph-aware for nodes (default graph for node records) - (a2) R290 reverted to graph-blind node ops (rejected by R290's measured defects) - (b1) post-read marker re-check (insufficient if a redaction completes inside the read) - (b2) redaction epoch compared before/after (head or a redaction counter) - (b3) readers hold a shared lock that redaction batches need exclusively - (b4) snapshot reads

Settling evidence: Confidence: medium. (b) a statement that readers only promise refusal while a marker is visible (then b1 suffices for the stated mechanism, not for the purpose); (a) a maintainer choice between graph-aware verify and graph-blind node ops.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1501"></a>
### Should a FHIR sync be governed by the ledger?

Status: open owner decision. Canonical owner: `fhir.ledger`.

Now: fhir_graph_sync/rebuild/fhir_reinterpret run Graph.KG.FHIRGraph directly: no ledger record, no strict check (FHIRGraph.cls never reads ^IVG.Ledger); verify() reads every graph and would report the FHIR rows as unrecorded writes (verify(adopt=True) would record them). Evidence: inspected `iris_vector_graph/_engine/fhir_graph.py:251-258`; inspected `iris_vector_graph/ledger/replay.py:806-849`; inspected `iris_src/src/Graph/KG/FHIRGraph.cls (no ^IVG.Ledger read; grep at pin)`

Working assumption (agent, unratified): Keep decisions.md: the FHIR graph is an external writer of a rebuildable projection at the pin. verify() keeps reporting its rows (never silently 'equal'); strict mode is not a guarantee for FHIR namespaces until FHIR writes are either refused under strict or recorded. Changed from decisions.md: no. Sources confirm the working answer; added that ledger-api.md's exhaustive list is silent on FHIR (not an explicit exemption) and that verify() reads every graph.

Options and implications: - (a) declare FHIR graphs ledger-exempt projections; verify() skips them and strict documents the exemption - (b) refuse rebuild/sync/reinterpret while strict is on (needs a server-side check: the Python guard does not cover ObjectScript) - (c) record each committed batch as a ledger revision

Settling evidence: Confidence: medium. A maintainer statement or spec text placing FHIR graphs inside or outside the ledger; a strict-mode check in FHIRGraph.cls.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1502"></a>
### Should erasing a FHIR graph stop its sync task?

Status: open owner decision. Canonical owner: `fhir.erase.durable-removal-policy`.

Now: EraseGraph deletes content, unresolved/canonical rows, zeroes wm_rsrc/wm_ver and nulls interp_version; fhir_graphs (including task_id) is kept; the Task Manager task keeps running SyncOnce, which with watermarks at 0 re-projects the whole repository. No single-graph deregistration call exists (only EraseAll removes registry rows); after unschedule, a manual fhir_graph_sync or `ivg fhir sync` still refills. Evidence: inspected `iris_src/src/Graph/KG/Eraser.cls:1146-1180`; tested `tests/e2e/test_231_fhir_graph_sync_e2e.py::test_erase_keeps_registration_and_resets_watermarks`; inspected `iris_src/src/Graph/KG/FHIRGraphSyncTask.cls:1-27`

Working assumption (agent, unratified): Separate transient clear from decommissioning. Ordinary erase keeps registration and task (supported). For durable tenant removal require, as a stated premise, unschedule before erase and no manual sync afterwards, and verify the graph stays empty before redaction; at the pin there is no single-graph deregistration, so 'deregister' is a new command, not an available step. Changed from decisions.md: yes. Status raised to supported for the transient-clear half (ADR-0015:29 and the Eraser comment settle it). Refined the durable-removal half: decisions.md offered 'paused or deregistered', but no single-graph deregistration exists at the pin and an unscheduled graph still accepts manual syncs.

Options and implications: - (a) erase also unschedules the task (clears task_id) - (b) as built, plus documentation that an erased FHIR graph refills unless unscheduled - (c) a deregister command removing registration, task and content together

Settling evidence: Confidence: high. A spec 256 / FHIR_GRAPH statement about tenant removal of a FHIR graph; an erase that touches task_id.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1503"></a>
### What happens when an erase runs during a FHIR sync?

Status: open owner decision. Canonical owner: `fhir.sync.other_writers`.

Now: No coordination: erase runs in its own transaction without ^IVG.FHIRGraph; a running sync's later batches write absolute watermarks after the erase commits (IRIS row locks on the fhir_graphs row only order the two transactions, they do not prevent the interleaving). Reasoned from source, not observed. Evidence: inspected `iris_src/src/Graph/KG/Eraser.cls:47-57`; inspected `iris_src/src/Graph/KG/FHIRGraph.cls:543-626,1920-1978`

Working assumption (agent, unratified): Keep decisions.md: erase of a FHIR graph must be serialized with an active sync (take ^IVG.FHIRGraph(graph) and answer busy, or have RunBatch abort when the watermark moved backwards); until then the quiet-sync premise must be explicit for erase. Changed from decisions.md: no. Confirmed by source; added the documented convergence claim as the outcome anchor and the absolute-watermark write as the mechanism of the failure.

Options and implications: - (a) erase takes the sync lock and refuses (or waits) while a sync holds it - (b) RunBatch compare-and-sets the watermark (WHERE wm = expected) and stops when it went back - (c) document that a FHIR graph must be unscheduled and idle before an erase

Settling evidence: Confidence: medium. A live interleaving on IRIS for Health (two processes, injected pause between batches) showing a different outcome; a maintainer statement making quiescence a premise.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1504"></a>
### Should one unreadable FHIR resource block its graph's sync?

Status: open owner decision. Canonical owner: `fhir.sync.recovery-policy`.

Now: The batch containing the resource throws, rolls back with its watermark, and RecordError writes last_error naming the key; each later sync repeats the same batch and fails; a rebuild also fails on it. Progress resumes only after the resource is repaired or deleted in the repository, or json links are turned off (re-register with json_links=[], which triggers a rebuild that no longer reads bodies). Evidence: inspected `iris_src/src/Graph/KG/FHIRGraph.cls:543-626,1920-1978,2039-2056,2380-2397,2976-2988`; tested `tests/e2e/test_231_fhir_graph_sync_e2e.py::test_crash_before_commit_leaves_nothing`

Working assumption (agent, unratified): Failure without advancing the watermark is the documented contract (not a choice to revisit silently). Surface the offending key (already in last_error) and treat the missing recovery procedure (repair/delete the resource, or json_links=[]) as a documentation gap; do not assume silent skips. Changed from decisions.md: yes. Status raised from assumption to supported for the failure semantics: FHIR_GRAPH.md:196-199 (maintainer commit 59286731) explicitly states that a walk limit fails the batch, and :255-257 that a failed batch repeats. Added that a rebuild fails too, and the json_links=[] recovery path.

Options and implications: - (a) record the key in fhir_unresolved (new reason) and continue - (b) keep failing and document how an operator finds and fixes the resource (last_error names it) - (c) skip only after N repeated failures

Settling evidence: Confidence: medium. A maintainer statement that partial indexing is acceptable (quarantine); evidence that HS.FHIRServer can hold a body that makes the walk fail in practice (otherwise the stall is mostly theoretical for non-JSON bodies).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1601"></a>
### Should a server limit which graphs a caller may name?

Status: settled existing authority. Canonical owner: `access.graph_id`.

Now: No interface restricts graph names. The code has no graph ACL: a grep of iris_vector_graph, api, iris_src and docs found none. One API key, or an IRIS login for the REST dispatcher and MCP, admits every graph in the namespace. Evidence: inspected `iris_vector_graph/api_auth.py; iris_vector_graph/cypher_api.py:101-108`; inspected `experiment/playbook-uplift/decisions/16.md (HD-1601 inventory)`

Working assumption (existing authority): The namespace is the authorization boundary; graph IDs scope data operations and do not confer access rights.

Authority: [docs/USER_GUIDE.md](../../../../docs/USER_GUIDE.md); history cc546a29. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1602"></a>
### Should admin work need a different key from reading?

Status: open owner decision. Canonical owner: `access.api_key.admin-policy`.

Now: One key gates every route, admin and kill included. IVG_READ_ONLY=true refuses all /admin writes and DELETE /admin/queries/{id}, along with Cypher writes. The kill route can end any process that the server's IRIS user may kill. Evidence: inspected `iris_vector_graph/cypher_api.py:95-108, 702-714`

Working assumption (agent, unratified): Model the single key and the IRIS user's privileges as the authorization surface. Treat an admin-only key or a kill route that is off by default as a proposed strengthening. Record IVG_READ_ONLY as the existing, coarse lever. Changed from decisions.md: **yes**. Status moves from assumption to supported. ADMIN_API and ADMIN_GUIDE (4.6.0) explicitly document one key on every route and the read-only lever. decisions.md did not cite IVG_READ_ONLY.

Options and implications: - (b) a second, admin-only key for /admin/* writes and the kill route - (c) kill route disabled unless an operator enables it

Settling evidence: Confidence: high. A deployment contract requiring role separation, such as an admin key or an RBAC mapping to IRIS roles.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1603"></a>
### Should the Cypher HTTP server run a failed query a second time?

Status: open owner decision. Canonical owner: `access.retries`.

Now: An in-process run of the pin's app on AUDITIB injected faults into the first engine only. In (A) the CREATE committed and then a ConnectionError was raised: HTTP 200 and the node was written twice. In (B) a ValueError was raised before execution: the query was retried on a fresh engine. Every exception type is retried once, writes included. Evidence: live `ib-HD1603-server-retry`; inspected `iris_vector_graph/cypher_api.py:239-250`

Working assumption (agent, unratified): Retry a read, or a write known not to have executed (a connection error raised before the statement was sent). Never re-run a write whose outcome is unknown; return an error that says the outcome is unknown. A write carrying a verified idempotency key may be retried. Changed from decisions.md: **no**. Same direction as decisions.md. New history evidence (9c683292 to 7d62dbf5) and a live duplicate write strengthen it.

Options and implications: - (a) retry every query once [as built] - (c) never retry; return the error

Settling evidence: Confidence: medium. A maintainer statement that availability outweighs duplicate writes, with documentation that writes must be idempotent (MERGE). Or a server-side idempotency key.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1604"></a>
### Should the REST dispatcher's `/metaPath` take a graph?

Status: open owner decision. Canonical owner: `access.surfaces.rest-meta-policy`.

Now: /metaPath walks the default graph. A `graph` key in the body is ignored without error, so a caller who names a graph gets the default graph's answer. Evidence: inspected `iris_src/src/Graph/KG/Service.cls:304-319; PyOps.cls:423-427`

Working assumption (agent, unratified): Treat /metaPath as default-graph-only and include that in its contract. A body naming `graph` should be refused or honoured, not ignored; until decided, model the silent ignore as the baseline. Changed from decisions.md: **no**. Same reading. Added: spec 230 is absent from the repository and the mirror, and a supplied graph key is ignored silently.

Options and implications: - (b) read `graph` from the body as the search routes do - refuse a body that names a graph other than the default

Settling evidence: Confidence: medium. The text of spec 230, if it lists /metaPath, or a maintainer statement.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1605"></a>
### Should the generated GraphQL server match the sample API's safety limits?

Status: open owner decision. Canonical owner: `access.webapp.generated-limits-policy`.

Now: On AUDITIB, the generated app accepted a query nested 14 levels deep through outgoing/node and resolved all 14 levels. The api/ schema carries QueryDepthLimiter with a maximum depth of 10. With its connection closed, the generated app's /health answered 200 {status: healthy, database: disconnected}. Evidence: live `ib-HD1605-gql-depth-health`

Working assumption (agent, unratified): Treat both apps as supported entry points subject to the shared HTTP safety constraints: key gate and read-only (already applied), a depth bound, and an honest health check. Record the generated app's missing depth limit and always-healthy /health as gaps against that parity, not as violations of a stated contract. Changed from decisions.md: **yes**. Partial change. decisions.md left the choice open between 'distinct entry points' and parity. R097, R107 and R079 show the maintainer already hardening create_app as a deployable app, so parity (b) is now the working direction. decisions.md also used 'sample' for the app the maintainer calls the development app.

Options and implications: - (a) leave create_app as an example/developer server and say so in its docstring and README - (c) deprecate create_app in favour of api/

Settling evidence: Confidence: medium. A maintainer statement of which GraphQL app is production-supported.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1701"></a>
### Should the SQL adapter's pass-through refuse a write when called read-only?

Status: open owner decision. Canonical owner: `access.read_only.scope`.

Now: Live on AUDITIB: with read_only=True an INSERT into Graph_KG.nodes and a CREATE TABLE both executed. Each also came back with IVGResult.error '<USAGE ERROR> ... did not return a result set' (fetchall on a statement with no result set), so a caller is told the write failed although it ran (new observation). Evidence: live `ib-HD1701-readonly-flag`; inspected `iris_vector_graph/stores/iris_sql_store.py:1522-1554`

Working assumption (agent, unratified): Keep decisions.md: read_only=True is a requested guarantee; enforce it at a trusted boundary (refuse non-SELECT before it runs) or refuse/remove the unsupported flag in a versioned change. The engine's own use (reads only) makes enforcement compatible with internal callers. Changed from decisions.md: no. Live probe confirms the flag is ignored; added the protocol's raise-not-approximate rule as supporting evidence and the misreported-error observation.

Options and implications: - (a) enforce: refuse a non-SELECT statement with a clear error before it runs - (b) remove the parameter from the protocol and the adapter - (c) keep as documentation only and say so

Settling evidence: Confidence: medium. A spec 156 text or maintainer statement on the flag; external GraphStore implementations relying on it.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1702"></a>
### Should the HTTP client resend a write query after a server error?

Status: open owner decision. Canonical owner: `access.retries`.

Now: Probe (no IRIS, counting stub): a CREATE was executed 3x on persistent 500; 2x when the first attempt committed and then got a 502, with the caller seeing success and no sign of the duplicate; 3x when each attempt committed but answered after the read timeout (caller got IVGClientError). Reads and writes are treated identically. With the server's own retry (cypher_api._run_cypher) the worst case is 6 executions. Evidence: live `ib-HD1702-client-retry (no-IRIS stub; client behaviour observed, server simulated)`; inspected `iris_vector_graph/sdk.py:209-228`

Working assumption (agent, unratified): Keep decisions.md: after an ambiguous outcome resend only a known read or an explicitly idempotent operation; report an unknown outcome otherwise; treat client and server retries as one protocol. Note that this narrows a documented feature (compatibility decision). Changed from decisions.md: no. Probe confirms; added that the retry itself is a documented maintainer feature (so the working answer is a narrowing, not a bug fix) and that statement failures are 400 and not retried.

Options and implications: - (a) retry only reads (client cannot tell; the server could mark replies) - (b) retry only connect errors raised before the request was sent; never 5xx or timeouts - (c) keep retrying everything and document that writes must be idempotent (MERGE) or carry a ledger retry key

Settling evidence: Confidence: high. A maintainer statement accepting at-least-once write semantics over HTTP (then option c with documentation).

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1703"></a>
### Should the SQL adapter's capability list say what this namespace can run?

Status: open owner decision. Canonical owner: `algorithms.routing.capability-policy`.

Now: Probe: over a stub connection on which every statement fails, capabilities() reports all 22 non-Arno keys True (static catalogue). On AUDITIB the engine's capabilities property reports objectscript_deployed=True, kg_built=False, nkg_built=False while the store dict is all True. Routing uses the static dict, then falls back to the same ObjectScript class on a store error. Evidence: live `ib-HD1703-capabilities`; inspected `iris_vector_graph/stores/iris_sql_store.py:2991-3000`

Working assumption (agent, unratified): Keep decisions.md: code support and namespace availability are different facts; treat store.capabilities() as a static catalogue (document it as such) and do not read it as availability; routing that needs availability uses engine.capabilities/status() or an explicit fallback. Changed from decisions.md: no. Probe and source confirm; added that the product already separates the facts (engine.capabilities, a06e1f50) so option (b) is the existing design, missing only documentation.

Options and implications: - (a) answer from what is deployed (classes compiled, procedures present) - (b) keep the code-support catalogue and document it, pointing at engine.capabilities/status() for availability

Settling evidence: Confidence: medium. Another GraphStore implementation or a maintainer statement relying on capabilities() as availability.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1704"></a>
### Should the low-level vector helper refuse a vector of the wrong width?

Status: settled existing authority. Canonical owner: `search.embedding.width.raw-helpers`.

Now: normalize_vector pads [1,2] to [1,2,0,0], truncates 6->4 and maps NaN/Inf to 0.0 (logged only under IRIS_VECTOR_DEBUG); insert_vector stores the coerced vector in a VECTOR(FLOAT,4) column that refuses the same 3-wide vector by raw SQL (SQLCODE -104). Evidence: live `ib-HD1704-helper-coercion`; tested `tests/unit/test_dbapi_utils_unit.py:22-51`

Working assumption (existing authority): The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract.

Authority: [iris_vector_graph/dbapi_utils.py](../../../../iris_vector_graph/dbapi_utils.py); history edd3563b. No new maintainer approval is claimed.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1705"></a>
### Should server start refuse to listen on every address without an API key?

Status: open owner decision. Canonical owner: `access.defaults.exposure`.

Now: Probe: 'ivg server start' with IVG_API_KEY unset reaches uvicorn.run(host='0.0.0.0', port=8200) with authentication off; '--force-no-auth' is rejected by click as an unknown option. Evidence: live `ib-HD1705-server-binding (in-process CLI, uvicorn replaced; nothing listened)`; inspected `iris_vector_graph/cli.py:419-441`

Working assumption (agent, unratified): The product contract at the pin is ADMIN_GUIDE section 5's open default; F-1709 is a documentation defect against deploy/README.md:86 (registered as fail against that stated text). For the reviewed deployment, keep local-only binding or an explicit opt-in for unauthenticated external binding as a stated premise, not as the product's intent. Changed from decisions.md: yes. decisions.md kept both contradictory contracts open; commit 6df261d9/R032 makes ADMIN_GUIDE the single operator document and git history shows --force-no-auth was never implemented on any branch, so the open default is the current contract and the hardening is a deployment premise.

Options and implications: - (a) implement the refusal: bind 127.0.0.1 or exit unless a key or an explicit flag - (b) keep the open default and correct deploy/README.md (and compose.yml's unread IVG_AUTH_MODE)

Settling evidence: Confidence: high. A maintainer statement that deploy/README.md describes intended behaviour still to be built.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="HD-1802"></a>
### Should a snapshot be a point-in-time view?

Status: open owner decision. Canonical owner: `install.snapshot.consistency-policy`.

Now: Live, `ib-HD1802-torn-save` (expected-violation): a quiet save was consistent (ledger head 2, its node in the archived table). With a commit from a second process forced between the table reads and the first global read, the archive's `^IVG.Ledger` head was 3 and held seq 3's records while the archived `nodes` table lacked that commit's node: replay(archived ledger) differs from the archived rows. Nothing in `save_snapshot` prevents the interleaving.

Working assumption (agent, unratified): Claim a consistent snapshot only when writers are quiescent (an operator premise) or under a verified snapshot/epoch protocol; for the current exporter declare the quiet-writer premise. Changed from decisions.md: **no**.

Options and implications: - (b) Hold the ledger head lock (or a namespace write lock) for the save and record the head in `metadata.json`; covers ledger commits but not unledgered engine writers unless they take the same lock. - (c) One IRIS transaction: IRIS SQL offers no MVCC snapshot read, so reads still see later commits; it does not close the window.

Settling evidence: As built: high. Intent: medium-high. A maintainer statement that online saves must be consistent would make (b) the contract.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="REACH-1"></a>
### Should erasure and redaction reach the store in REACH-1?

Status: open owner decision. Canonical owner: `erasure.scope.embedding-queue-policy`.

Now: ERS-B95: A graph erasure or a node erasure leaves the queued embedding requests of the erased nodes in place. So does erasing everything. / ERS-B95: A graph erasure or a node erasure leaves the queued embedding requests of the erased nodes in place. So does erasing everything.

Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.

Options and implications: Retain with a truthful out-of-reach declaration, or add an explicit purge/removal policy with graph attribution and recovery costs.

Settling evidence: An owner retention/removal decision naming the store, attribution and audit/backup requirements.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="REACH-2"></a>
### Should erasure and redaction reach the store in REACH-2?

Status: open owner decision. Canonical owner: `search.quarantine.retention`.

Now: ERS-B96: A graph erasure or a node erasure leaves the table of documents that an upgrade could not place in a graph. So does erasing everything. / ERS-B96: A graph erasure or a node erasure leaves the table of documents that an upgrade could not place in a graph. So does erasing everything.

Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.

Options and implications: Retain with a truthful out-of-reach declaration, or add an explicit purge/removal policy with graph attribution and recovery costs.

Settling evidence: An owner retention/removal decision naming the store, attribution and audit/backup requirements.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="REACH-3"></a>
### Should erasure and redaction reach the store in REACH-3?

Status: open owner decision. Canonical owner: `search.quarantine.retention`.

Now: ERS-B97: A graph erasure or a node erasure leaves the table of vectors of edges that an upgrade could not place in a graph. So does erasing everything. / ERS-B97: A graph erasure or a node erasure leaves the table of vectors of edges that an upgrade could not place in a graph. So does erasing everything.

Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.

Options and implications: Retain with a truthful out-of-reach declaration, or add an explicit purge/removal policy with graph attribution and recovery costs.

Settling evidence: An owner retention/removal decision naming the store, attribution and audit/backup requirements.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="REACH-4"></a>
### Should erasure and redaction reach the store in REACH-4?

Status: open owner decision. Canonical owner: `erasure.kept.snapshot-retention-policy`.

Now: ERS-B98: A graph erasure or a node erasure only marks the saved copy of the default graph as old. The copy stays until one of the three calls that read it builds a new one. Erasing everything removes it. / ERS-B98: A graph erasure or a node erasure only marks the saved copy of the default graph as old. The copy stays until one of the three calls that read it builds a new one. Erasing everything removes it.

Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.

Options and implications: Retain with a truthful out-of-reach declaration, or add an explicit purge/removal policy with graph attribution and recovery costs.

Settling evidence: An owner retention/removal decision naming the store, attribution and audit/backup requirements.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="REACH-5"></a>
### Should erasure and redaction reach the store in REACH-5?

Status: open owner decision. Canonical owner: `erasure.scope.legacy-backup-policy`.

Now: ERS-B99: A graph erasure or a node erasure leaves the two tables where an upgrade from version 3.2 kept copies of edges. So does erasing everything. / ERS-B99: A graph erasure or a node erasure leaves the two tables where an upgrade from version 3.2 kept copies of edges. So does erasing everything.

Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.

Options and implications: Retain with a truthful out-of-reach declaration, or add an explicit purge/removal policy with graph attribution and recovery costs.

Settling evidence: An owner retention/removal decision naming the store, attribution and audit/backup requirements.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="hist-012"></a>
### Upstream #12: bulk-created nodes had no id property, so directed patterns from {id: ...} found nothing (4.4.2)

Status: historical fixed-at-pin report. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="hist-012"></a>
### Upstream #12: bulk-created nodes had no id property, so directed patterns from {id: ...} found nothing (4.4.2)

Severity: Unranked

Settled as built: `CHANGELOG.md:59-60` records it fixed in 4.6.0 (R089) and checked again for 4.7.0; at the pin `create_node` sets `props["id"]` (`_engine/nodes_edges.py:1057`) and `bulk_create_nodes` (`:1648`) feeds the server loader `Graph.KG.EdgeScan.BulkIngestNodesSQL`. Not re-observed here (no IRIS). Planned use as the control of a writer-path model (reviewed plan F1); not built in this consolidation.



Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="hist-013"></a>
### Upstream #13: count(DISTINCT) with ORDER BY and LIMIT failed on a from_connect() engine on IRIS 2026.1 (4.5.1)

Status: historical fixed-at-pin report. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="hist-013"></a>
### Upstream #13: count(DISTINCT) with ORDER BY and LIMIT failed on a from_connect() engine on IRIS 2026.1 (4.5.1)

Severity: Unranked

Settled as built: `CHANGELOG.md:52-58` records the fix in 4.7.0: the `from_connect()` probe also tries the aggregate shape and answers with TOP when it is refused (`engine.py::_detect_fetch_first_unsafe`, `:772`). Not re-observed here. Planned use as the control of a row-limit selector model (reviewed plan F2); not built in this consolidation.

## Inherited verification debt (playbook arm)

Proof debt the playbook arm recorded in [PROOF-DEBT.md](../../../../experiment/playbook-completion/PROOF-DEBT.md). These are verification gaps, not product questions; they stay visible here.



Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-1"></a>
### Proof debt D-1: L1/L2 refinement proofs for every module with operations: **paid at model level** for 01-11 and 15-18 (`proofs-breadth`, `proofs-d1b`..`proofs-d1f`, 94+92+111+118+115+115 verified,

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-1"></a>
### Proof debt D-1: L1/L2 refinement proofs for every module with operations: **paid at model level** for 01-11 and 15-18 (`proofs-breadth`, `proofs-d1b`..`proofs-d1f`, 94+92+111+118+115+115 verified,

Severity: Unranked

- all modules | — | the code-to-model link is D-2/D-3 |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-2"></a>
### Proof debt D-2: Statement lemmas: each IRIS SQL statement and ObjectScript global operation equals its model evaluation (§3.4)

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-2"></a>
### Proof debt D-2: Statement lemmas: each IRIS SQL statement and ObjectScript global operation equals its model evaluation (§3.4)

Severity: Unranked

- every writer and reader | journal-validated footprints (breadth lanes, `trace-conformance-ledger`), source inspection | no Verus frontend or IRIS SQL semantics library exists (PGspec is PostgreSQL and is skipped). The IRIS contract now has a Verus specification for its subset (`proofs-env`, `proofs-env2`, D-7), so a statement program can be proved against it once hand-translated; what this experiment did not provide is automated source-level verification of the product's ObjectScript/Python (no supported frontend was integrated here), so the translation is a trusted step to be checked against…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-3"></a>
### Proof debt D-3: Handler proofs: each Python/ObjectScript entry point performs its spec step (§3.5)

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-3"></a>
### Proof debt D-3: Handler proofs: each Python/ObjectScript entry point performs its spec step (§3.5)

Severity: Unranked

- all handlers | trace conformance of one two-tenant scenario; correspondence lane's map and unchecked-line list (`correspondence/`) | no automated source-level verification of the ObjectScript/Python handlers in this experiment (no supported frontend integrated here) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-4"></a>
### Proof debt D-4: Lock-plan obligations per handler (§3.5)

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-4"></a>
### Proof debt D-4: Lock-plan obligations per handler (§3.5)

Severity: Unranked

- writers of modules 11-14 and AdjW users | controlled lock probes and journal order; IRIS contract lock clauses | as D-3; F-1201 shows the eraser's plan is incomplete at the pin. Lane `lockplans` (modules 01, 05, 06, 08, 10, 16, 17) stopped at the finish request: explorer models 46/46 in 5 families (`lockplans-mc-*`, `lockplans-control-*`), live `lockplans-08-17-guarded-insert` (+`-r3`) with candidate findings F-C0811/F-C1711 not yet filed; probes for 01, 05, 10, 16 not run (`lockplans/PARTIAL.md`, not integrated) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-5"></a>
### Proof debt D-5: Composition: a committed IRIS transaction refines the serial step, chained over executions (§3.6)

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-5"></a>
### Proof debt D-5: Composition: a committed IRIS transaction refines the serial step, chained over executions (§3.6)

Severity: Unranked

- product | `proofs/` composes participant **contracts**; trace conformance checks committed transactions of one scenario | needs D-2 and D-3 |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-6"></a>
### Proof debt D-6: Frame, key, FK, capacity, row-permutation conditions (§3.6)

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-6"></a>
### Proof debt D-6: Frame, key, FK, capacity, row-permutation conditions (§3.6)

Severity: Unranked

- every module | executable checks with self-tests across all modules (structural lane: ownership, storage order, row permutation, keys, FK, capacity probes, a catalog/dictionary frame oracle and a non-interference read oracle; `st-*`), correspondence checks for 11-14 (`corr-*`), CLOSURE.md's condition list | as D-2: no proof over IRIS SQL or ObjectScript |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-7"></a>
### Proof debt D-7: The IRIS environment contract as a Verus specification linked to the participant contracts: **paid at model level for the contract's Verus subset** by `proofs-env` (305 verified, 0

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-7"></a>
### Proof debt D-7: The IRIS environment contract as a Verus specification linked to the participant contracts: **paid at model level for the contract's Verus subset** by `proofs-env` (305 verified, 0

Severity: Unranked

- environment | executable contract r6 and contract-2 (differential, mutants) | still open: the discipline `disc` against the code (D-3/D-4); 9 clause families outside the Verus subset (X-DDL, X-STAR, X-FX, X-NOINDEX, X-VEC `$VECTOR` set/get, X2-JSON, X2-LIST, X2-TOP, X2-QUERY/MERGE/ZKILL: 513 recorded case runs, exact obligations in proofs-env2/PROOFS.md section 6; no closure premise rests on them); progress premises; several locks / regions not composed into one invariant; the Freedom's proceeding branch unobserved How each part is linked (review A-04): the Verus spec to the executable contra…

_Imported from the playbook arm by…

Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-8"></a>
### Proof debt D-8: Progress premises: fair scheduling of enabled steps, operator re-runs after a stop, ledger re-enabled, no write outside the ledger, a weakly fair queue worker (`proofs-mech` M07-L4

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-8"></a>
### Proof debt D-8: Progress premises: fair scheduling of enabled steps, operator re-runs after a stop, ledger re-enabled, no write outside the ledger, a weakly fair queue worker (`proofs-mech` M07-L4

Severity: Unranked

- `progress.rs` of `proofs/`, `proofs-d9*`; `proofs-mech` M-07; core models' AG EF | none derived or tested against IRIS scheduling; "no writer makes a marked target live" (P-C02/PF-6) is violated at the pin (F-C1307, F-C1350) | premises, named in `TRUST.md` and `reflection/CLOSURE.md` |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-9"></a>
### Proof debt D-9: Reviewed protocol under the pin's real premises (bypass writers, three distinct target predicates, erasure rollback, readers, statement history, Decision 2, retry-key movement): **

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-9"></a>
### Proof debt D-9: Reviewed protocol under the pin's real premises (bypass writers, three distinct target predicates, erasure rollback, readers, statement history, Decision 2, retry-key movement): **

Severity: Unranked

- erase/redact/replay | explorer core M1-M3 as before | still open: G-BM is a working assumption (whether content re-created outside the ledger is 'live' is a maintainer question; its cost at the pin not assessed); premises P-LV (the liveness check sees every row, violated by F-C1351) and P-D9-3 not modelled; P-D9-5 graph-blind replay, the HD-1304 receipt, P-D9b-3 and the unreproduced mixed-revision case (`proofs-d9b/PROOFS.md` section 10); verify()'s table read, its two-read coherence and node identity (F-1401); readers' progress; post-commit property recovery; F-CS01's reviewed design is inte…

_Imported from the playbook arm by…

Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-10"></a>
### Proof debt D-10: M1 targeting with 2 pre-enable writes and 2 commits: **paid (mc, exhaustive within bounds)** by `models/core-partition`: 43 pieces by pre-enable world whose union is checked to be 

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-10"></a>
### Proof debt D-10: M1 targeting with 2 pre-enable writes and 2 commits: **paid (mc, exhaustive within bounds)** by `models/core-partition`: 43 pieces by pre-enable world whose union is checked to be 

Severity: Unranked

- core models | — | still open: profiles beyond (2,2) and (0,3); M1's small world (3 ids, 2 graphs, 3 edges); the as-built RPL-B3 check not re-run per piece |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-11"></a>
### Proof debt D-11: Original proof `l2.rs` refinement covers the reviewed design only

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-11"></a>
### Proof debt D-11: Original proof `l2.rs` refinement covers the reviewed design only

Severity: Unranked

- modules 12-14 | original 53 verified, 6 controls rejected (submission 9c3719c1) | by design; product violates it (F-1302, F-1303) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-12"></a>
### Proof debt D-12: Progress-only control for reviewed-design element D-2 (scan bound fixed at marking): **paid at model level**: `control_bound_follows_tail` (the pin's tail-following bound) fails on

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-12"></a>
### Proof debt D-12: Progress-only control for reviewed-design element D-2 (scan bound fixed at marking): **paid at model level**: `control_bound_follows_tail` (the pin's tail-following bound) fails on

Severity: Unranked

- `proofs-d9b/src/progress.rs` | — | the variant needs an attached process to resume to continue; the located failure does not depend on it |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-13"></a>
### Proof debt D-13: The breadth proofs (modules 04 and 11) without premise P-A3: **paid at model level** by `proofs-pa3` (108 verified, 0 errors, `proofs-pa3-baseline`, recheck `proofs-pa3-recheck`): 

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-13"></a>
### Proof debt D-13: The breadth proofs (modules 04 and 11) without premise P-A3: **paid at model level** by `proofs-pa3` (108 verified, 0 errors, `proofs-pa3-baseline`, recheck `proofs-pa3-recheck`): 

Severity: Unranked

- `proofs-pa3/` | — | still open: modules 04 and 11 not composed; one erase at a time; erases inside a caller transaction, EraseNodes/EraseAll, FK rollback and progress under R04-5 not modelled; neither guard exists at the pin |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._




Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.

<a id="D-14"></a>
### Proof debt D-14: Shared mechanism laws proved once over a trait: **paid at model level** by `proofs-mech` (1,149 verified, 0 errors, `--no-cheating`, empty trust inventory; all 45 laws of 13 mechan

Status: inherited qualified proof debt. Canonical owner: method/historical evidence; no new product owner.

Now: <a id="D-14"></a>
### Proof debt D-14: Shared mechanism laws proved once over a trait: **paid at model level** by `proofs-mech` (1,149 verified, 0 errors, `--no-cheating`, empty trust inventory; all 45 laws of 13 mechan

Severity: Unranked

- 13 mechanisms, 45 laws | explorer checks (`sem-mc-*`) alongside | composition **paid at model level** by `proofs-sys` (256 verified, 0 errors, `--no-cheating`, empty trust inventory including the proofs-mech dependency, `proofs-sys-baseline`, recheck `proofs-sys-recheck`): the 12 module-00 axiom checks proved once over a design trait whose parameters are the instance choices of M-01, M-02, M-03, M-04, M-05 and M-10 (all 3,072 choice vectors meeting each obligation); 12 located controls, the pin's as-built composition breaking AX-06, AX-07, AX-08, AX-10, AX-11 and AX-11M, each control's broken…

_Imported from the playbook arm by…

Working assumption (agent, unratified): Keep the existing recorded scope; no new verification or human decision is inferred.

Options and implications: Reopen if source or relied-on evidence changes.

Settling evidence: A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.

The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.
