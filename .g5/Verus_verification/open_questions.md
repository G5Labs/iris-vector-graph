# Open questions — IVG initial Verus uplift

Unresolved intent that needs a human decision. Each gives the evidence, the plausible interpretations and the decision needed. Index: [findings register](findings.md).

<a id="q-004"></a>
### Must erasure and redaction be serialised with each other and with ledger commits?

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Evidence: `Graph.KG.Eraser` takes no ledger head lock; since 4.6.4 an erase made through an engine on a plain connection nests in the caller's transaction (aad50087), while an engine from `from_connect` runs it on a dedicated connection. `LedgerRedact.LiveRows` reads without locks. Probe [erasure_caller_transaction](receipts/native/erasure_caller_transaction_redaction.json): on a plain connection the erase nests at `$TLEVEL=1`, a concurrent redaction completes, and the caller's rollback restores the content ([bug-002](bugs_issues.md#bug-002)); through `from_connect` the erase [committed on its own](receipts/native/erasure_caller_transaction_from_connect.json) and the caller's rollback did not undo it.

Interpretations: (a) callers must not redact while an erase is uncommitted (document it); (b) redaction must refuse while any erase of the target is uncommitted (take the head lock in the eraser, or a shared target lock); (c) erasure must never join a caller's transaction.

Decision needed: the serialisation contract between erase, redact and commit, and whether erase joins a caller's transaction. Open statement: [erasure.concurrency](../ontology/features/erasure.g5.md#erasure.concurrency).

<a id="q-001"></a>
### Should another tenant's retry of a revision it shared with a redacted tenant be refused?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: spec 256 Decision 2 (Tom, 2026-10-22) clears the metadata of any revision with a redacted record, idempotency key included; the recorded trade-off named only the lost commit message (a140ed78 open question 2). `LedgerRedact.ClearRevision` moves the key to `idemRedacted`; `Ledger.CommitInTxn` then refuses every retry with that key (`idempotency_redacted`). Probe [redaction_mixed_retry](receipts/native/redaction_mixed_retry.json), re-run with byte-identical changesets: tenant B's retry of its own revision replays; its retry of the revision it shared with redacted tenant A is refused with `IdempotencyRedactedError` and changes nothing. The other tenant's `history(correlation_id=...)` lookup also stops finding the revision.

Interpretations: (a) intended — a key names the whole revision, and a refused retry is safer than a replay of a partly tombstoned revision; (b) unintended — only the target's retries should be refused; the other tenant should get a replay (its content is intact) or a distinct error telling it the revision exists but was partly redacted.

Decision needed: which response a non-target tenant's retry gets, and whether its correlation-id lookup should survive. Open statement: [redaction.idempotency.other-tenant](../ontology/features/redaction.g5.md#redaction.idempotency.other-tenant).

<a id="q-003"></a>
### How should strict mode and the erase-then-redact path fit together?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `erase_graph`, `delete_nodes_by_prefix` and `erase_all` call the strict-mode check and raise `LedgerStrictModeError` (nodes_edges.py:1513, :1552; iris_sql_store.py:1433). Redaction refuses a live target, so it needs the erasure first. Erasing through changesets cannot reach named-graph node rows (ledger node operations are default-graph only, 4.6.0 R290). No document or test covers the combination. Model witness `witness_strict_erase_then_redact_needs_strict_off` ([platform model](models/platform/NOTES.md)); probe [platform_strict_redaction](receipts/native/platform_strict_redaction.json): under strict mode the tenant's graph cannot be erased, the ledger leaves its 2 named-graph node rows, and redaction is refused `target_live`; with strict off both run.

Interpretations: (a) strict-mode users turn strict off for the erase, then on again; (b) erasure is exempt from strict mode because it removes content, not history (ADR-0004); (c) erasure should be recorded in the ledger in strict mode.

Decision needed: which path a strict-mode tenant erasure takes, and its documentation. Open statement: [redaction.strict-mode](../ontology/features/redaction.g5.md#redaction.strict-mode).

<a id="q-008"></a>
### Should erase-by-prefix and redact-by-prefix use the same prefix rule?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `Eraser.EraseNodes` (Eraser.cls:322-350) and `engine.delete_nodes_by_prefix` match a bare starts-with ("acme" erases `acme-health|1` too), while `LedgerRedact.MatchString` always appends the separator ("acme" redacts only `acme|…`). The documented tenant recipe pairs the two (ADR-0013:37; the e2e fixture erases with "tenantA|" and redacts with "tenantA"). An operator who erases with the same bare prefix they redact with also erases a neighbouring tenant's nodes, irreversibly. Found by the fresh-reader reconstruction check (reconstruction-check.md, correction 4).

Interpretations: (a) intended — erase is a general id-prefix tool and the caller must add the separator; document it beside the recipe; (b) the tenant recipe should use one target notion for both steps (a separator-aware erase, or a combined erase-and-redact entry point).

Decision needed: whether erase-by-prefix gains the separator rule (or a tenant entry point), and the documented recipe. Open statement: [erasure.prefix-match](../ontology/features/erasure.g5.md#erasure.prefix-match).

<a id="q-009"></a>
### Should redaction count a target's temporal-only edges as live content?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: ADR-0013 refuses redaction "while any **row** of the target is live", justified by replay; CONTEXT.md says redaction is "Refused while any of the target's **content** is live", and its Erasure definition lists the temporal index as content. A temporal-only predicate (ADR-0015) writes no row and no node. Model witness W2 (`witness_temporal_only_content_is_not_seen`, [prove receipt](results/ledger_redaction/20261114T044401Z-prove/receipt.json)) and probe [redaction_temporal_only_live](receipts/native/redaction_temporal_only_live.json): with only a temporal-only edge in `gT` (0 edge rows, 0 node rows), `redact("gT")` completed and tombstoned the `create_temporal_edge` record while the window reader still returns the edge. Erasure does not settle this for prefix targets: erasing a tenant by prefix leaves its temporal-only events whose endpoints have no node row ([bug-led-007](bugs_issues.md#bug-led-007)).

Interpretations: (a) ADR-0013's "row" governs: temporal entries are not replayed, so tombstoning their records keeps verify equal and is acceptable; (b) the glossary's "content" governs: redaction must refuse until the temporal entries are erased, or the history of a still-readable event is lost.

Decision needed: whether temporal-index entries count for the liveness check (and so whether this is a defect). Open statement: [redaction.after-erasure.temporal](../ontology/features/redaction.g5.md#redaction.after-erasure.temporal).

<a id="q-010"></a>
### Should post-commit properties be recorded, excluded from verify, or documented as unrecorded writes?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: spec 218 (CHANGELOG v2.18.x): `post_commit_properties` are applied "via direct SQL (Approach A — no new revision created)"; the docs do not mention verification. Probe [ledger_post_commit_verify](receipts/native/ledger_post_commit_verify.json): one commit with a post-commit property, then `verify()` → `diverges` (`node pcp|1 prop:audit_rev None → x`); `verify(adopt=True)` would record it as an adoption.

Interpretations: (a) intended: the documented audit-trail pattern produces an unrecorded write and verify is right to report it (document it); (b) post-commit properties should be recorded (a second record in the same revision) or excluded by verify.

Decision needed: which, and the documentation of the audit-trail pattern. Open statement: [ledger.commit.post-commit.recorded](../ontology/features/ledger.g5.md#ledger.commit.post-commit.recorded).

<a id="q-str-001"></a>
### How should an install that already holds a graph named "0", or one with a control character, find and migrate it?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: ADR-0003:69-70 promises `verify_graph` reports such graphs; none does, and every `ForIndex` caller, the `%BuildIndices` callbacks included, throws on such rows (A-structure Q3). [graph_structure_keys](receipts/native/graph_structure_keys.json) shows new writes of these names are refused (K1, K2).

Interpretations: (a) an upgrade step renames them; (b) `verify_graph` reports them and an operator renames them; (c) they are left and every write to them fails.

Decision needed: the migration path, and whether `verify_graph` must report them as ADR-0003 says. Open statement: [graph.names.legacy](../ontology/concepts/graph-scope.g5.md#graph.names.legacy).

<a id="q-tmp-001"></a>
### Must temporal writes stay exact when several writers touch the same coordinates or triple at once?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: spec 254 FR-003 states first-write-wins without condition and spec 255 says the latest index is "kept exact"; ADR-0010 explains why the temporal writers take no locks. The `$Data` collision guard and the writes are not locked (`TemporalIndex.cls:84`): `witness_concurrent_inserts_double_count` ([prove receipt](results/temporal/20261114T001508Z-prove/receipt.json)) shows two inserts at one coordinate counting twice. `NoteLatest` is an unlocked read-compare-set (`TemporalIndex.cls:493-496`), and two first writers into an empty graph each `Kill ^KG("tlast",g)` (`:90-92`), so the latest index can go stale-low while `Resolve` detects only vanished events (`:411-415`). The write/purge race on one triple is a defect against ADR-0009 and is registered separately ([bug-tmp-011](bugs_issues.md#bug-tmp-011)). No concurrent test exists; no probe was run (A-temporal F6, F7).

Interpretations: (a) the rules hold for one writer per triple; concurrent writers are the caller's to serialise (document it); (b) the rules are unconditional, so the writers need per-triple locking despite ADR-0010's deadlock concern.

Decision needed: whether first-write-wins, exact statistics and an exact latest index are promised under concurrency. Open statement: [temporal.write.concurrency](../ontology/features/temporal.g5.md#temporal.write.concurrency).

<a id="q-srch-001"></a>
### Should quarantined vectors and documents survive erasure indefinitely?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `embedding_quarantine`, `docs_quarantine` and `edge_vector_quarantine` survive `EraseAll` and graph erasure by decision (FR-039/FR-040 as quoted; the spec is not in `specs/`), and no purge path exists; ADR-0004 says erasure is not a privacy tool, and ADR-0013's redaction does not mention quarantines (A-search Q5).

Interpretations: (a) keep them: they are the only copy of vectors whose graph is unknown; (b) a deployment that must delete data needs a purge path or an erase-all that includes them.

Decision needed: retention, and whether a purge operation exists. Open statement: [search.quarantine.retention](../ontology/features/search.g5.md#search.quarantine.retention).

<a id="q-plt-001"></a>
### Is strict mode promised from the moment set_strict returns, or within a few seconds for other engines?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `witness_ttl_window_admits_a_write_after_set_strict` ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json)); probe [platform_strict_ttl](receipts/native/platform_strict_ttl.json): a second engine that had probed before wrote `ttl-bypass` unrecorded 0.002 s after `set_strict(True)` returned, and was refused after the TTL; the calling engine was refused at once (the USER_GUIDE example). The guard caches `Meta()` per engine for 5 s (`ledger/guard.py:20, 38-59`), and `set_strict` refreshes only the calling engine's guard (`client.py:281-309`). Probe [platform_strict_paths](receipts/native/platform_strict_paths.json) confirms the guarded paths refuse once the cache is fresh.

Interpretations: (a) strict is promised from the moment `set_strict` returns, so the window is a defect; (b) strict is enforced within 5 s per process, as the guard docstring implies, and needs documenting.

Decision needed: the promise, and with (a) whether to fix it in the guard or by [simp-plt-001](design_simplification.md#simp-plt-001). Open statement: [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict).

<a id="q-plt-002"></a>
### Can an explicitly named schema be recorded over another schema's interrupted first setup?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `witness_interrupted_setup_then_explicit_schema` (W-S3, [prove receipt](results/platform/20261114T002651Z-prove/receipt.json)) holds even with serial setups. After an interrupted setup on S (marker present, no record; KNOWN_ISSUES:787-807), an engine with an explicit T sees `held={S}` and records T as "explicit" (`_engine/schema.py:2229-2239, 2312`); `^KG`, `^NKG` and `^IVG.Ledger` hold S's data, and `kg_built` is already marked, so setup does not rebuild `^KG` from T's rows (`:2356-2361, 2673-2678`). FR-009's explicit path was designed for 4.5.x namespaces (A-platform F-S3). The concurrent-setup case is [bug-plt-003](bugs_issues.md#bug-plt-003).

Interpretations: (a) refuse the explicit path while another schema holds this release's marker (the premise the model's proof uses); (b) accept it and clear or rebuild the namespace's globals.

Scope (review round 3 R3-reader H3): that an explicit name is recorded while IVG's tables sit in one other schema at all is the FR-009 divergence [bug-plt-026](bugs_issues.md#bug-plt-026); this question is narrowed to the globals an unfinished setup of the current release leaves behind.

Decision needed: which. Open statement: [install.schema.concurrency.leftover](../ontology/concepts/install.g5.md#install.schema.concurrency.leftover).

<a id="q-plt-003"></a>
### Should the server refuse to start on a reachable address with no key and a superuser login?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: with no key, the HTTP server and Bolt bind `0.0.0.0` and connect as `_SYSTEM`/`SYS`, a `%All` superuser, exposing `/admin/load`, Cypher writes and `DELETE /admin/queries/{pid}` → `KillProcess` on any PID, with no warning in `cypher_api` or the CLI (A-platform F-H5); only the sample API warns about the default login. The environment-name mismatch that makes this silent is [bug-plt-009](bugs_issues.md#bug-plt-009).

Interpretations: (a) refuse to start on a non-loopback host without a key (or with a superuser login); (b) warn loudly and document; (c) keep as is, the operator guide being the control.

Decision needed: which. Open statement: [access.defaults.exposure](../ontology/concepts/access.g5.md#access.defaults.exposure).

<a id="q-plt-004"></a>
### What should a restore do when the namespace already has a live ledger?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `erase_all` keeps `^IVG.Ledger("rec")`, the head and the meta (`Eraser.cls:810-812`), and the replacing restore's global import only sets values (`_engine/snapshot.py:1654-1692`), so the archive's ledger entries are written over the live ones without removing the live revisions (A-platform F-B3; A-ops candidate finding). Restoring an earlier archive also brings back content a later redaction removed ([q-led-002](#q-led-002)).

Interpretations: (a) refuse while a ledger is live; (b) replace the live ledger wholesale; (c) keep the live ledger and skip the archive's.

Decision needed: which. Open statement: [install.snapshot.ledger](../ontology/concepts/install.g5.md#install.snapshot.ledger).

<a id="q-plt-005"></a>
### Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: BulkLoader bypasses the ledger and strict mode does not refuse it (documented exempt); its `PurgeIndex` → `RemoveAll` empties every graph's adjacency mid-load with no rebuild lock (`Adjacency.cls:452-473, 814-823`); its in-memory `(s,p,o)` dedupe gives a multigraph graph no parallel edges; two loaders can insert duplicates under `%NOCHECK` (A-platform F-B7; reconstruction check 2(a)6, G7, G34).

Interpretations: (a) yes to all three, and the loader documents it; (b) the loader must preserve other graphs' adjacency and multigraph semantics.

Decision needed: the loader's contract. Open statement: [install.bulk_load.limits](../ontology/concepts/install.g5.md#install.bulk_load.limits).

<a id="q-plt-006"></a>
### Should whether a write joins the caller's transaction depend on how the engine was opened?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `engine._iris_obj()` opens a separate connection whenever the engine knows its credentials (`from_connect`) and reuses the caller's process otherwise (`engine.py:1894-1943`); tests patch it back to the caller's connection. On that transport `erase_graph`/`erase_all` [committed on their own](receipts/native/erasure_caller_transaction_from_connect.json), while on a plain connection the erase [nests](receipts/native/erasure_caller_transaction_redaction.json) ([q-004](#q-004), [bug-002](bugs_issues.md#bug-002)). The same split applies to ledger commits without a caller transaction, `redact`/`enable`/`disable`/`set_strict`, FHIR graph calls, `set_multigraph`, the vector index calls and `sync()`, and to the non-indexed adjacency writes ([bug-str-015](bugs_issues.md#bug-str-015)) (A-ops method notes and (e)2; reconstruction check 2(a)1).

Interpretations: (a) intended: these calls are independent of the caller's transaction, and the docs list them; (b) every write should run on the caller's connection and nest; (c) calls that cannot nest should refuse an open caller transaction.

Decision needed: the transaction membership of each listed call, independent of how the engine was built. Open statement: [structure.write.engine-connection](../ontology/features/graph-structure.g5.md#structure.write.engine-connection).

<a id="q-plt-007"></a>
### Can a default-graph algorithm call use a native reader once a named graph holds edges?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `ArnoAccel.cls:255-256` says the readers read the `^NKG` export, which merges every graph; CONTEXT.md:267 says they read the adjacency index directly; `TraversalBuild.cls:758-760`. The native routes for PageRank, WCC, CDLP and subgraph have no `_named_graph_with_edges()` guard, unlike the R184 tiers (`iris_sql_store.py:3234, 3691, 3749`) (A-platform F-A3).

Interpretations: (a) the readers read one graph and the route is safe; (b) they read the merged snapshot, so default-graph PageRank counts named-graph edges and needs the guard.

Decision needed: a live check of what the 1.2.1 reader reads, and the routing rule. Open statement: [algorithms.routing.named_graphs](../ontology/features/algorithms.g5.md#algorithms.routing.named_graphs).

<a id="q-plt-008"></a>
### Which write paths must strict mode govern beyond the engine's methods, and how is each classified?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `theorem_strict_paths` and `witness_undecided_paths_write_under_strict` ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json)): under strict mode the undecided paths' writes commit; marking any of them exempt or covered makes the witness fail (review R3-platform R1-11). Per the sources: embedding, vector-index and BM25 writes are outside the ledger by decision (ADR-0006; spec 213 governs structural writes); BulkLoader and raw SQL, MCP `RunSQL` included (ADMIN_GUIDE §3), are documented exemptions; `bulk_delete_adjacency` and the sample API's Cypher, GraphQL and example mutations are undocumented bypasses ([bug-plt-006](bugs_issues.md#bug-plt-006), [bug-plt-005](bugs_issues.md#bug-plt-005)); no source decides FHIR sync (`_engine/fhir_graph.py:255-258`, no ledger call in `FHIRGraph.cls`), MCP `CypherQuery` (`MCPTools.cls:9-29`), `set_multigraph`, `Prop_Set`, the `Txn_*` procedures, or the migrations (`upgrade_to_4_0_0`, the temporal backfill), which rewrite tables and globals with no strict check. The guard's own gaps are the 5 s TTL ([q-plt-001](#q-plt-001)), fail-open ([q-plt-009](#q-plt-009)) and the lifetime-cached `_class_present` ([bug-plt-025](bugs_issues.md#bug-plt-025)). A Cypher write cannot reach the variable-length route before `_ledger_check` (transactional plans carry no `var_length_paths`; R3-platform A5). Sources: A-platform F-B8, F-H7; B-platform Q5.

Interpretations: for each undecided path, (a) exempt like BulkLoader and raw SQL, listed in the docs; (b) refused under strict mode.

Decision needed: the classification of each undecided path. Open statements: [access.ledger_strict.undecided](../ontology/concepts/access.g5.md#access.ledger_strict.undecided), [fhir.ledger](../ontology/features/fhir.g5.md#fhir.ledger).

<a id="q-cyp-001"></a>
### When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: the decision says "`CREATE` writes the default graph" (CONTEXT l. 46-48); the edge insert uses `''` with the bound pair's IDs (`translator.py:10351-10365`); the foreign key `(graph_id, s/o_id) → nodes` (`schema.py:42-43`) refuses it when the default graph lacks those IDs, and when it has nodes of the same IDs the relationship connects those nodes, not the bound ones. The e2e matrix has no such case (`test_460_all_graphs_writes_e2e.py:133-147`) (A-cypher F5).

Interpretations: (a) the decision is literal; the error is intended and should name the cause; (b) Cypher's binding wins and the relationship is created in the bound nodes' graph, as `SET`/`DELETE` already do.

Decision needed: which, and the error text under (a). Open statement: [query.graph-scope.bound-create](../ontology/features/cypher.g5.md#query.graph-scope.bound-create).

<a id="q-led-005"></a>
### Should callers be able to choose a commit's kind?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: `commit(changeset, kind=...)` is public (`client.py:381`); a kind other than `"changeset"` skips the empty and size checks, and `"adoption"` applies through `LedgerGenesis.Adopt` (`Ledger.cls:488-509`), so a caller can forge an adoption revision that records changes the tables never had, or label a changeset `redaction` or `genesis` in the history (reconstruction check 2(b)9, correction 9; review R1-core CV-6 and R1-6).

Interpretations: (a) make `kind` internal (only verify needs adoption); (b) keep it public and document the skipped checks and the audit meaning of each kind.

Decision needed: which. Open statement: [ledger.commit.kind](../ontology/features/ledger.g5.md#ledger.commit.kind).

<a id="q-plt-019"></a>
### May the server or the client retry a call that writes?

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Evidence: no document states a retry policy. The HTTP server reruns a failed Cypher call once on a fresh engine, and the SDK's `_post` retries server errors and timeouts ([bug-plt-019](bugs_issues.md#bug-plt-019)), so a write can be applied twice; only a ledger commit with an idempotency key is protected. Open statement: [access.retries](../ontology/concepts/access.g5.md#access.retries).

Interpretations: (a) retries are allowed only for reads and for idempotency-keyed commits; (b) retries stay, and writes must be made idempotent; (c) no automatic retries.

Decision needed: the retry policy for writes.

<a id="q-plt-018"></a>
### Which graph do rows of a mapped FHIR SQL table belong to?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: mapped SQL tables carry no graph column, so a Cypher query under `USE GRAPH` or across every graph reads the same mapped rows (`cypher/translator.py`; `_engine/fhir.py`). No spec or ADR states the scope; not run natively (FHIR suites skipped on this instance). Open statement: [fhir.sql_mapping.graph_scope](../ontology/features/fhir.g5.md#fhir.sql_mapping.graph_scope).

Interpretations: (a) mapped rows belong to every graph (today's behaviour, documented); (b) a mapping is made per graph and only that graph's queries read it.

Decision needed: the graph scope of mapped rows.

<a id="q-srch-006"></a>
### Should every fusion entry point use the same text ranking?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: the engine and Cypher fusions read a BM25 index built from node properties (`_engine/vector.py:1382-1451`), while the SQL `kg_RRF_FUSE` procedure ranks the documents table by full-text term counts (`schema.py:2484-2560`); the 4.0.0 migration guide calls the documents table the BM25 corpus (`docs/migration/v4.0.0.md:742-751`). Open statement: [search.fusion.text_leg](../ontology/features/search.g5.md#search.fusion.text_leg).

Interpretations: (a) one shared contract for every entry point; (b) two contracts, each documented, with the migration guide corrected.

Decision needed: whether the SQL fusion should read the BM25 index.

<a id="q-002"></a>
### Which ledger readers must refuse while a redaction is unfinished?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: spec 256 plan "Readers" lists `get_revision`, `diff`, `reconstruct`, `export_reconstruction` (refuse) and `verify()` (`redaction_in_progress`). Probe [redaction_readers_midrun](receipts/native/redaction_readers_midrun.json): `get_revision`, `diff`, `reconstruct`, `export_reconstruction` refused; `verify` answered `redaction_in_progress`; `history`, `stats` and the SQL `ledger_records` procedure answered. `history()`, `stats()` and the SQL procedure `ledger_records` answer mid-run with some revisions' metadata already cleared and others not. The refusing readers check the marker once and then page through SQL, so a batch can commit between pages.

Interpretations: (a) only replay-style readers need protection; metadata listings may show a half-done redaction; (b) every record or metadata reader should refuse or read one consistent snapshot.

Decision needed: the reader list, and whether a reader must see one moment of the ledger. Open statement: [redaction.batches.readers](../ontology/features/redaction.g5.md#redaction.batches.readers).

<a id="q-005"></a>
### Is an unsalted SHA-256 of a tenant name and of each record acceptable in the redacted history?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: ADR-0013 keeps `sha256(CanonicalRecord)` per tombstone and `sha256(graph NUL match)` in the redaction revision's source and the marker; a salted digest was rejected "for now" (ADR-0013:43, 49). Canonical records contain the entity id, attribute and values; a guessed tenant name or a low-entropy value (a boolean, a known name) can be confirmed by hashing the guess.

Interpretations: (a) acceptable — the digest is an audit device and the content is already low-sensitivity; (b) unacceptable for regulated erasure — use a keyed digest held outside the namespace.

Decision needed: whether confirmability of guessed content is within the redaction guarantee. Open statement: [redaction.tombstone.digest](../ontology/features/redaction.g5.md#redaction.tombstone.digest).

<a id="q-006"></a>
### How does an operator end a redaction that cannot finish?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: once a run has tombstoned anything, the marker stays until that target's run completes. If the target becomes live again, a resumed call is refused at entry (`target_live`, observed in [redaction_interrupt_resume](receipts/native/redaction_interrupt_resume.json) step 4), and if it becomes live between the last batch and the final step, the final step refuses (`theorem_completion`; observed natively in the race context: in [redaction_concurrent_targets](receipts/native/redaction_concurrent_targets.json) tenant A's run ended with the final step's message "the default graph (ids starting 'tA|') became live again"; the serial case is unobserved; review round2-core R2-5). Meanwhile record readers, verify, commits into the target and every other target's redaction are refused until the content is erased again and the same target is run to completion. There is no abort.

Interpretations: (a) intended — the only safe exit is to finish; (b) an abort that restores nothing (tombstones stay) but releases the marker is wanted for a target that is legitimately back in use.

Decision needed: whether an abort exists and what it guarantees. Open statement: [redaction.batches.abort](../ontology/features/redaction.g5.md#redaction.batches.abort).

<a id="q-007"></a>
### What does erasure's returned count promise?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: CONTEXT.md and ADR-0004 say "a returned 0 means nothing matched". `EraseGraph` returns the number of `nodes` and `rdf_edges` rows removed; labels, properties, documents, vectors, temporal entries, FHIR rows and ledger statements can be removed while it returns 0.

Interpretations: (a) the count means node and edge rows only, and the doc should say so; (b) 0 must mean no store changed.

Decision needed: the documented meaning. Open statement: [erasure.count](../ontology/features/erasure.g5.md#erasure.count).

<a id="q-str-002"></a>
### Which control characters must a graph name refuse, and who owns the rule?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: Python's `validate_graph_name` refuses 0–31 and 127 (`_validate.py:47`); IRIS's `$ZStrip(...,"*C")` also covers 128–159. `witness_python_mirror_admits_c1_control` ([prove receipt](results/graph_structure/20261114T000451Z-prove/receipt.json)); [graph_structure_keys](receipts/native/graph_structure_keys.json): IRIS refuses 0x01, 0x1F, 0x7F, 0x80, 0x85 and 0x9F and accepts 0xA0 (`p_ctrl`), and in K3 a name with U+0085 passed Python and was refused inside IRIS as SQLCODE -400 "Fatal error occurred", nothing written (A-structure Q4; B-structure O1; review R2-data R1-14).

Interpretations: (a) GraphKey owns the rule and Python asks it (or mirrors it exactly), so the refusal is a clean validation error; (b) keep both, accepting the opaque server error for C1 characters.

Decision needed: one definition and its owner. Open statement: [graph.names](../ontology/concepts/graph-scope.g5.md#graph.names).

<a id="q-str-003"></a>
### In a multigraph, must create_edge always add a new edge and offer a variant that returns its ID?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: spec 234 FR-007 says yes to both; the code returns False for an existing triple, `create_edge_returning_id` does not exist, CHANGELOG and API docs are silent, and KNOWN_ISSUES steers users to Cypher (A-structure Q2; R2-data E6).

Interpretations: (a) FR-007 stands and this is unfinished work; (b) drop FR-007 and document Cypher as the way to add parallel edges.

Decision needed: which. Open statement: [structure.multigraph.create_edge](../ontology/features/graph-structure.g5.md#structure.multigraph.create_edge).

<a id="q-str-004"></a>
### Until a ledger reference can name one parallel edge, should the ledger refuse relationship operations on a multigraph triple?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: spec 234 lists the ledger (US4) as not done and FR-013 requires an ambiguous tuple reference to fail; `LedgerApply.FindEdge` takes the first matching row with no ambiguity check (`LedgerApply.cls:144-157, 185-198`), and the delete then breaks the survivors' adjacency ([bug-str-001](bugs_issues.md#bug-str-001)) (B-structure open question; R2-data E6).

Interpretations: (a) refuse with `ambiguous_tuple` until FR-013 lands; (b) apply to the first row, as today, once the adjacency defect is fixed.

Decision needed: which. Open statement: [structure.multigraph.ledger](../ontology/features/graph-structure.g5.md#structure.multigraph.ledger).

<a id="q-tmp-002"></a>
### After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: ADR-0009:49 says statistics "describe the past" after a purge, while `DeleteTemporalEdge` and `EraseNodes` rebuild a bucket from its survivors (`TemporalIndex.cls:446-488`); after `purge_raw_before(tsEnd)` with `tsEnd` mid-bucket, deleting a surviving edge wipes the purged edges from `tagg` but not from `bucket` (A-temporal Q2).

Interpretations: (a) the purge rule wins: a cut bucket keeps its history; (b) the rebuild rule wins: statistics describe the survivors.

Decision needed: which rule, and the matching code change. Open statement: [temporal.stats.cut-bucket](../ontology/features/temporal.g5.md#temporal.stats.cut-bucket).

<a id="q-tmp-003"></a>
### Must a paged temporal window read show one consistent moment while edges are written?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: the window reader pages over live globals, so an edge inserted behind the cursor is missed and pages can mix states; spec 255 addresses only purged events (A-temporal Q5).

Interpretations: (a) a live, non-snapshot read is acceptable (document it); (b) a snapshot bound is wanted.

Decision needed: which. Open statement: [temporal.window.concurrent-writes](../ontology/features/temporal.g5.md#temporal.window.concurrent-writes).

<a id="q-tmp-004"></a>
### What should an insert collision inside a changeset do?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: since spec 254 `InsertEdge` answers 1 for a collision, and `OpCreateTemporalEdge` records `create_temporal_edge` unconditionally (`LedgerApply.cls:635-639`), so a revision claims a temporal edge that changed nothing; the changeset docstring still says "insert (fail if key exists)" (`changeset.py:334-335`) (A-temporal F5).

Interpretations: (a) refuse the changeset, as the docstring says; (b) commit and record nothing for the collided op; (c) keep the record and document that it may describe no change.

Decision needed: which. Open statement: [temporal.ledger.insert-collision](../ontology/features/temporal.g5.md#temporal.ledger.insert-collision).

<a id="q-tmp-005"></a>
### Should deleting the last timestamp of a temporal-only predicate keep its old structural row, as a purge does?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `witness_delete_and_purge_disagree_when_opted_out` ([prove receipt](results/temporal/20261114T001508Z-prove/receipt.json)); [temporal_marked_row_lifecycle](receipts/native/temporal_marked_row_lifecycle.json) K4: with the predicate registered temporal-only, deleting the last timestamp retracts the old marked row (`DeleteTemporalEdge` does not read the registry, `TemporalIndex.cls:333-341`), while a purge keeps it until the drop (`:966`; ADR-0015:144-148). Both keep the row rule (A-temporal Q4; B-temporal O3).

Interpretations: (a) the asymmetry is acceptable; (b) delete should follow the purge's "leave registered predicates' rows" rule.

Decision needed: which. Open statement: [temporal.optout.drop](../ontology/features/temporal.g5.md#temporal.optout.drop).

<a id="q-tmp-006"></a>
### May an explicit delete_edge remove a marked structural row while its triple still has timestamps?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: the temporal model's `DeleteEdge` lets an explicit `delete_edge` remove a marked row while timestamps remain, and no source decides the case; ADR-0009 makes a structural predicate's timestamp imply its row (review R2-data R1-7).

Interpretations: (a) an explicit delete wins and the triple stays without a row until its next temporal write; (b) the delete keeps (or re-asserts) the marked row while timestamps remain; (c) the delete is refused.

Decision needed: which. Open statement: [temporal.structural.explicit-delete](../ontology/features/temporal.g5.md#temporal.structural.explicit-delete).

<a id="q-srch-002"></a>
### May an undeclared writer add vectors to the default graph's table after a model has claimed it?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `witness_undeclared_default_vs_named` ([prove receipt](results/search/20261114T000543Z-prove/receipt.json)): an undeclared writer is width-checked only and lands in model A's `kg_NodeEmbeddings` on the default graph, while on a named graph it gets its own route; `embedding_identity.py:85-91` and FR-010 (as quoted in code) say yes; CONTEXT.md says writes at another model are "refused rather than mixed in", a phrase added on 2026-11-04 (`267aaff1`, R039), after 4.0.0 routing, which favours refusal (A-search Q1; review R3-platform R1-9).

Interpretations: (a) allowed at the same width (as built); (b) refused, as for a declared different model.

Decision needed: which. Open statement: [search.embedding.undeclared_default](../ontology/features/search.g5.md#search.embedding.undeclared_default).

<a id="q-srch-003"></a>
### May a BM25 search observe an index write that is still in progress?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: searches read `^BM25Idx` with no lock and no isolation (spec 044 FR-019 "Search takes no lock"), so they can read uncommitted or mixed N/df/len; FR-023 guarantees snapshot-like reads only during an upgrade; a search during a Build answers `[]` (A-search Q4; B-search "Not represented").

Interpretations: (a) acceptable: scores are approximate during writes; (b) searches must see committed state only.

Decision needed: which. Open statement: [search.bm25.read_isolation](../ontology/features/search.g5.md#search.bm25.read_isolation).

<a id="q-srch-004"></a>
### Should plain text search use a BM25 index named "default" when one exists?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: spec 044 FR-012 / US5 (still "Draft") says `kg_TXT` uses `^BM25Idx("default")` when present; `kg_TXT` uses iFind/LIKE over `docs` (`vector.py:917-1054`) (A-search Q3).

Interpretations: (a) the requirement is superseded; mark the spec; (b) it is unfinished work.

Decision needed: which. Open statement: [search.bm25.default_index](../ontology/features/search.g5.md#search.bm25.default_index).

<a id="q-srch-005"></a>
### In which order must the common-term cutoff list the terms it skipped?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: FR-044-C4 says "alphabetical"; the code returns ObjectScript collation order, in which numeric terms sort first (A-search Q6). The rest of the cutoff contract was proved (`theorem_cutoff_contract`, [prove receipt](results/search/20261114T000543Z-prove/receipt.json)) and observed as specified ([search_bm25_cutoff](receipts/native/search_bm25_cutoff.json)).

Interpretations: (a) collation order is what "alphabetical" means here (document it); (b) plain string order.

Decision needed: which. Open statement: [search.bm25.cutoff](../ontology/features/search.g5.md#search.bm25.cutoff).

<a id="q-plt-009"></a>
### When the strict-mode guard cannot read the ledger's state, should it allow the write?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: a failed `Meta()` probe caches "never-enabled", so the guard fails open (`ledger/guard.py:55-58`; `witness_failed_probe_admits_a_write`, [prove receipt](results/platform/20261114T002651Z-prove/receipt.json)) (B-platform Q3). The related lifetime cache of the class check is decided and registered as [bug-plt-025](bugs_issues.md#bug-plt-025).

Interpretations: (a) fail open, as documented in the code; (b) refuse under uncertainty when strict may be on, and re-probe the class.

Decision needed: which. Open statement: [ledger.strict.fail-open](../ontology/features/ledger.g5.md#ledger.strict.fail-open).

<a id="q-plt-010"></a>
### Should setup still record the schema when some classes failed to deploy?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: the deploy is best-effort (`_engine/schema.py:2578-2595`) and the record is written regardless (`:2309-2312`); the next engine is accepted and its writes fail with `GraphWriteError` (KNOWN_ISSUES:787-807 describes a similar symptom); on a non-default schema, earlier classes compiled for `Graph_KG` keep naming it (A-platform F-S5).

Interpretations: (a) record anyway and report the failure; (b) withhold the record so the namespace counts as a stopped setup (FR-006a).

Decision needed: which. Open statement: [install.setup.failed_deploy](../ontology/concepts/install.g5.md#install.setup.failed_deploy).

<a id="q-plt-011"></a>
### May a data migration run before any setup has recorded the namespace's IVG Schema, and on which schema?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: the migrations build their engine from `IVG_SCHEMA_PREFIX` or the default and waive the schema check (`engine.py:1887-1890`, whose comment justifies only "may run before any 4.6.0 setup recorded the schema"); with a record that names another schema the waiver is a defect ([bug-plt-007](bugs_issues.md#bug-plt-007)). With no record, FR-006a's letter conflicts with the 4.0.0 upgrade's documented order. The 4.0.0 migrations take `schema=` only for the placements; the embeddings and `^KG` steps use the engine's environment or default schema (`upgrade.py:145-152, 259-268`), and none consult `^IVG.Deploy("schema")` (A-platform F-S12; review R3-platform R1-5).

Interpretations: (a) with no record, a migration may run on an explicitly given schema and must not record it; (b) a migration must refuse until a setup records the schema.

Decision needed: the no-record rule. Open statement: [install.migration.schema.unrecorded](../ontology/concepts/install.g5.md#install.migration.schema.unrecorded).

<a id="q-plt-012"></a>
### Does read-only mode govern the MCP tools, and should Bolt honour a driver's read access mode?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: MCP `CypherQuery` writes and `RunSQL` runs anything (`MCPTools.cls:9-69`), with no read-only control (A-platform F-H7); Bolt ignores the access mode (reconstruction check 2(a)13).

Interpretations: (a) a read-only IRIS login is the real control and the docs say so; (b) `IVG_READ_ONLY` must cover MCP, and Bolt must refuse writes in a read session.

Decision needed: which. Open statement: [access.read_only.scope](../ontology/concepts/access.g5.md#access.read_only.scope).

<a id="q-plt-013"></a>
### Does a proven reader revision hold for every build and platform of the library?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: routing ignores the library build and platform (FR-004), while the proof record holds one arm64 build (A-platform F-A6).

Interpretations: (a) the revision is the contract across builds; (b) routing must also match the proven build.

Decision needed: which. Open statement: [algorithms.proof.build](../ontology/features/algorithms.g5.md#algorithms.proof.build).

<a id="q-plt-014"></a>
### Must the evidence gate also cover the other algorithms the native library speeds up?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: triangle count, SCC, k-core and Leiden use the library through `arno_bridge` with no proof gate and fall back only on a library error (`iris_sql_store.py:3737-3760, 3977-4000`) (A-platform F-A7).

Interpretations: (a) yes, gate them; (b) they are outside the gate by design (document it).

Decision needed: which. Open statement: [algorithms.proof.ungated](../ontology/features/algorithms.g5.md#algorithms.proof.ungated).

<a id="q-plt-015"></a>
### Should native readers work in namespaces other than USER?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: native readers run only in `USER`, while ADR-0016 makes any namespace the isolation unit, so a non-USER install never gets native routing (A-platform F-A9; spec 236 open question).

Interpretations: (a) USER only, documented; (b) the library must read the calling namespace.

Decision needed: which. Open statement: [algorithms.routing.namespace](../ontology/features/algorithms.g5.md#algorithms.routing.namespace).

<a id="q-plt-016"></a>
### Must a repeated FHIR event leave the graph unchanged?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `/fhir-event` stamps an event without `date` with the current time, so a repeat writes again; an updated resource's codes never refresh and there is no delete; the governing spec 195 is not in the repository, and the route is due for removal in 5.0 (A-platform F-B9).

Interpretations: (a) derive the time from the event so retries are harmless; (b) accept it until the route is removed.

Decision needed: which. Open statement: [fhir.event.retry](../ontology/features/fhir.g5.md#fhir.event.retry).

<a id="q-plt-017"></a>
### What should happen when other writers, an erase included, touch a FHIR graph during a sync?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `erase_graph` does not take `^IVG.FHIRGraph(graph)`, so it can race a full re-derive (A-platform F-B10); no source says whether other writers may touch a FHIR graph.

Interpretations: (a) the FHIR graph belongs to the sync alone and other writes are refused; (b) other writes, an erase included, take the sync's lock.

Decision needed: which. Open statement: [fhir.sync.other_writers](../ontology/features/fhir.g5.md#fhir.sync.other_writers).

<a id="q-cyp-002"></a>
### In shadow mode, should a native failure be raised instead of answered by SQL?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: FR-007 (fallback) and FR-006 (raise on a difference) both hold; in shadow mode a native exception is still answered by SQL with one warning (`query.py:2144-2152`), so a native defect that raises is invisible to a shadow run, TCK shadow runs included; shadow mode never compares compiled with interpreted (only `test_257_compiled_plans_e2e.py` does) (A-cypher F11).

Interpretations: (a) raise in shadow mode (stricter checks); (b) keep the fallback, as specified.

Decision needed: which. Open statement: [query.shadow.native-failure](../ontology/features/cypher.g5.md#query.shadow.native-failure).

<a id="q-cyp-003"></a>
### Should a bulk load by another process close the native query path while indexes lag the rows?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: the native gate (FR-014) is per engine (`native_plan.py:530`); `BulkLoader` writes `%NOINDEX %NOCHECK`, commits per batch and rebuilds `^KG` at the end (`bulk_loader.py:1-12, 157-163`), so other engines' native reads see `^KG` and `pkprops` behind the rows; spec 253 research §H names the trap (A-cypher F7).

Interpretations: (a) no: equal answers assume current indexes (document it); (b) a load publishes a namespace-wide marker that `native_gate` checks.

Decision needed: which. Open statement: [query.native.index-current](../ontology/features/cypher.g5.md#query.native.index-current).

<a id="q-cyp-004"></a>
### Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: at the baseline (Python 3.11.18, driver 5.3.2) three tests in `tests/unit/test_shortest_path.py` fail: `RETURN p` arrives as a dict and the tests call `json.loads` on it (`:164, 186, 219`), raising "the JSON object must be str … not dict"; `PRE_RELEASE_CHECKLIST.md:282` records the unit suite green with drivers 5.4.0/5.4.1 on Python 3.12 and 3.13.

Interpretations: (a) the representation changed (driver or execution path) and the tests are stale; (b) a path must always come back as JSON text, and the dict is a regression on this driver or path.

Decision needed: the documented representation of a path value, and whether it may vary by driver. Open statement: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

<a id="q-cyp-005"></a>
### Should a call to an unknown apoc, db or dbms procedure be refused?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: the `db.*`/`dbms.*`/`apoc.meta.*`/`gds.*` stubs exist, and an unknown `apoc`/`db`/`dbms` name answers no rows and no error (`engine.py:1039-1740`), while an unknown `ivg.*` or `gds.*` procedure is refused (reconstruction check 2(a)4, correction 21).

Interpretations: (a) answer empty for Browser compatibility; (b) refuse, as for `ivg.*`.

Decision needed: which. Open statement: [query.system-procedures.unknown](../ontology/features/cypher.g5.md#query.system-procedures.unknown).

<a id="q-led-001"></a>
### Which copy of a record must an auditor keep to recompute its tombstone digest?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `MutationRecord.from_row` normalizes graph `"\x00"` to None (`replay.py:56-74, 137-142`) while `CanonicalRecord` emits `"\u0000"` (`Ledger.cls:595-596`), and key and number formatting may differ; exports carry no records, and the canonical form is not specified outside `Ledger.cls` (A-history F18; reconstruction check G12).

Interpretations: (a) the server's canonical record captured before the redaction is the only valid preimage (document it, and how to capture it); (b) the public reader must reproduce the canonical form exactly.

Decision needed: which artifact an auditor keeps, and whether the canonical form is a published contract. Open statement: [redaction.tombstone.digest-source](../ontology/features/redaction.g5.md#redaction.tombstone.digest-source).

<a id="q-led-002"></a>
### Should the redaction receipt name IVG's own snapshot archives and the ledger rows an upgrade left behind?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `save_snapshot` archives hold `^IVG.Ledger` and the ledger storage (ADMIN_GUIDE:989-991), so restoring an earlier archive brings back tombstoned content and `idem` bindings; after an R114 upgrade the 4.5.x `Graph_KG` ledger rows "stay where they are" (`legacy.py:612-613`) with uncleared metadata. The receipt's out-of-reach list names neither (`LedgerRedact.cls:505-508`) (A-history F8).

Interpretations: (a) name them in the receipt's out-of-reach list; (b) redaction must also reach them (refuse or rewrite archives it knows of; clear the legacy rows).

Decision needed: which. Open statement: [redaction.out-of-reach.other-copies](../ontology/features/redaction.g5.md#redaction.out-of-reach.other-copies).

<a id="q-led-003"></a>
### What should disabling the ledger do while a redaction is unfinished?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `disable` takes no head lock and has no caller-transaction refusal; its behavior while a redaction marker exists was not checked (reconstruction check G38). Re-enabling afterwards skips the adoption silently ([bug-led-004](bugs_issues.md#bug-led-004)).

Interpretations: (a) refuse `disable` while a redaction is unfinished; (b) allow it, and define what the marker means while the ledger is disabled.

Decision needed: the lifecycle rule. Open statement: [ledger.lifecycle.disable-during-redaction](../ontology/features/ledger.g5.md#ledger.lifecycle.disable-during-redaction).

<a id="q-led-004"></a>
### How should the ledger's genesis record a node ID that two graphs hold?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: genesis scans `nodes`, `rdf_labels` and `rdf_props` with no graph (`LedgerGenesis.cls:17-36`), so an ID held by two graphs gives two `create_node` records and one merged set of labels and properties; how replay and verify fold them was not checked (reconstruction check 2(b)8, G8).

Interpretations: (a) acceptable: ledger nodes are graph-blind by design; (b) genesis should record one node per (graph, ID) or refuse.

Decision needed: which. Open statement: [ledger.lifecycle.genesis.shared-ids](../ontology/features/ledger.g5.md#ledger.lifecycle.genesis.shared-ids).

<a id="q-led-006"></a>
### Must verify compare one consistent moment of the ledger and the tables?

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Evidence: `verify()` checks the redaction marker once, reads the ledger and the tables with no lock, and commits an adoption without `expected_head` (`replay.py:806-858`; A-ops hazard (c)2; review R1-core R1-6). The race with a redaction is registered as [bug-led-001](bugs_issues.md#bug-led-001); with ordinary commits running, a verify can report differences that existed at no single moment.

Interpretations: (a) verify is best-effort; run it when writes are quiet (document it); (b) verify reads under the head lock, or retries until the head did not move.

Decision needed: which. Open statement: [ledger.verify.consistency](../ontology/features/ledger.g5.md#ledger.verify.consistency).
