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

Also recorded as: HD-1801 (playbook decision: what should a restore do to the live ledger; [decisions/18.md](../../experiment/playbook-uplift/decisions/18.md), intent [HD-1801](../../experiment/playbook-completion/intent/HD-1801.md)); the matching finding is F-1801 in the bugs register. (crosswalk)

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

<a id="q-iter-003"></a>
### Should history text filters use binary identity or the current database comparison?

Severity: Medium · Decision: Open

Run: Improvement iteration 6, 2026-11-15

Evidence: the Python API calls a correlation filter exact, but persisted fields use ordinary IRIS String columns. Actual native commits/history match ASCII case changes and trailing spaces or tabs, including in raw source JSON; interior JSON spacing still differs. Evidence and raw rows: [native comparison](../uplift/consolidated/iteration-6/history-collation-native.json), [spaces](../uplift/consolidated/iteration-6/history-collation-spaces-native.json), [interior source spacing](../uplift/consolidated/iteration-6/history-collation-interior-native.json). The as-built history_paging model represents both comparison modes; no human policy was inferred.

Working answer: document current matching until a maintainer decides, preserving existing queries. Alternative: use binary identity for some or all metadata fields so distinct correlation IDs/source text do not compare equal; that can change existing queries.

Decision needed: which comparison is intended for actor/type/correlation/source fields, and whether any change needs a compatibility path. Canonical owner: [history text policy](../ontology/features/ledger.g5.md#ledger.readers.history.text-policy).

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
<a id="q-iter-001"></a>
### How should flat node reads preserve colliding property aliases?

Severity: Low · Decision: Open

Run: Uplift improvement iteration 1, 2026-11-15

Classification: settled as built (both keys are accepted and one is lost at the flat reader); intended replacement needs ratification. `create_node` validates key width but reserves neither `p_id` nor `p_labels`; `get_nodes` renames only `id` and `labels` (`nodes_edges.py:1013-1014,670-676`). The writer/reader unit witness and Verus witness are in [node_read](models/node_read/NOTES.md).

Working answer: keep structural fields and return every property under a separate property map. Alternative: keep flat results but reserve and validate an alias namespace before writes; existing colliding data then requires a migration or explicit refusal. The product owner must choose compatibility and rollout. Owner: [structure.node.read.aliases](../ontology/features/graph-structure.g5.md#structure.node.read.aliases); finding [bug-str-101](bugs_issues.md#bug-str-101).

<a id="q-con-001"></a>
### Must the streaming history reader bound its memory, or only its delivery?

Severity: Low · Decision: Open

Run: Consolidated uplift 2026-11-14

Evidence: `reconstruct(..., stream=True)` folds every record into one in-memory state and only then yields its entities (`ledger/replay.py:550-566`); the entity bound is enforced only when `stream=False` (`:555-556`), as the contract says (`specs/213-graph-revision-ledger/contracts/ledger-api.md:30`). `export_reconstruction` passes no bound and also materializes the whole state before writing NDJSON (`ledger/client.py:731-739`), while the contract says it "streams to NDJSON; never bounded" (`ledger-api.md:31`). The requirement text behind the bound (FR-035 to FR-037) is not in the repository.

Classification: settled as built (the bound applies to the materialized reader only; neither reader bounds memory); what was promised needs ratification.

Working answer: "streaming" describes delivery, not memory; the bound protects callers of the materialized reader. Material alternative: the bound exists to cap memory, so the streaming reader and the export should fold incrementally (or be bounded too). Claims that depend on it: public case J03's "streaming export path under its documented scope". Lead L1 of the reviewed plan; neither arm recorded it.

Iteration 2 corroboration: [reconstruction](models/reconstruction/NOTES.md) proves the bound exemption and shared structural fold; the actual named Python readers/export agree on the selected surviving-node journey and consume all records before yielding. This adds evidence to q-con-001; it is not a new streaming-memory finding. Canonical owner: [ledger.readers.bound](../ontology/features/ledger.g5.md#ledger.readers.bound).

<a id="q-iter-002"></a>
### Must reconstruction's bound concern each intermediate graph or only the requested graph?

Severity: Low · Decision: Open

Run: Uplift improvement iteration 2, 2026-11-15

Classification: settled as built, intended policy needs ratification. `reconstruct` checks entity_count after each record (`replay.py:550-556`); a history create a, create b, delete b fails at bound 1 although its final graph contains only a. Streaming and export return a. [reconstruction model and Python comparison](models/reconstruction/NOTES.md) distinguish both histories. The API contract FR-035/036 references do not specify peak versus final size; available git history and tests do not settle a different policy.

Working answer: preserve and document the intermediate-size check for memory protection. Alternative: check only the final size, accepting a larger temporary graph. Product maintainer owns this choice at [ledger.readers.bound.policy](../ontology/features/ledger.g5.md#ledger.readers.bound.policy); q-con-001 separately concerns whether streaming must bound memory. This is a specification/policy gap, not a confirmed product bug.

<a id="q-con-002"></a>
### Is a ledger diff an ordered script or an unordered set of net changes?

Severity: Low · Decision: Open

Run: Consolidated uplift 2026-11-14

Evidence: `compute_diff` sorts entries by kind, ID and attribute (`ledger/replay.py:406-407`, `:535`); for one node deleted and re-created in the range the two existence entries tie and keep their forward order, so the inverse lists the creation before the deletion ([unit probe](results/unit-probes/20261115T043637Z-l2-inverse-order/receipt.json)). The contract calls the diff "sorted net, lifecycle-aware" (`ledger-api.md:29`).

Classification: needs ratification. Working answer: an unordered set of net changes (the contract's "net"), in which case order does not matter but the reverse diff's attribute values still do ([bug-led-101](bugs_issues.md#bug-led-101)). Alternative: an ordered script that a client may apply, which would require the inverse to reverse the order of tied entries. Lead L2 of the reviewed plan. Iteration 3 attaches this decision to canonical ledger.readers.diff.order. Producer inspection corrects the old empty deletion prior: NodeSnapshotJson carries full labels/properties at deletion. The simple delete/recreate neighbor preserves those values in inverse existence.after; changing a property before deleting still loses its earlier range prior when that lifecycle closes. Keep two choices explicit: (1) display a set of lifecycle entries with deletion-moment snapshots, the current working interpretation; (2) provide a complete endpoint delta or an applicable script, retaining range-start values and defining tie order. Neither is owner-ratified. As-built selection/inversion and continuous-life endpoint values now have history_diff proofs; full lifecycle reconstruction remains open.

<a id="HD-0001"></a>
### How to read "defined by its ancestors or an earlier same-level statement"

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the playbook's definitions-first rule, read literally, forbids a child from using a term its parent's earlier sibling defined. The uplift reads it as lexical scope (ancestors, and earlier siblings of the statement or of any ancestor). Accept this reading, or require literal ancestry?
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: lexical scope (`tools/ontology_index.py`, `in_scope`). ## Decisions from the worked example (modules ERS, RED, RPL).
- Intent recovery: [intent/HD-0001.md](../../experiment/playbook-completion/intent/HD-0001.md) (status supported(literal reading) · Confidence: high · Changed from decisions.md: no); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0101"></a>
### Should an engine that cannot read the schema record be refused?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: spec 262 FR-006 says an engine whose schema differs from the namespace's record must be refused on first access. When the record cannot be read (a user without %Native_GlobalAccess, or any other exception), the engine logs a WARNING and skips the check, so an engine built for another schema may write into the namespace beside the recorded one and share its globals.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0101.md](../../experiment/playbook-completion/intent/HD-0101.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (decisions.md marked this Supported because ADMIN_GUIDE documents the skip. The doc's commit (0bf9fc2c) treats the skip as a role misconfiguration and fixes it by requiring the resource. It does not choose fail-open, and the accepted AD); decision text [01.md](../../experiment/playbook-uplift/decisions/01.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0102"></a>
### Should setup save the schema record when the class deploy failed or was turned off?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: initialize_schema writes ^IVG.Deploy("schema") after any run that is not a preview, even when the deploy raised, a class failed, or auto_deploy_objectscript=False. From then on every engine is accepted by the first-use check, though the per-graph erase, the ledger and the adjacency index need the classes. The warning in the reply is the only signal.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0102.md](../../experiment/playbook-completion/intent/HD-0102.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same reading and status. Added evidence: data-model.md transitions (binding only), spec 262 edge cases (record after objects), and maintainer R299 (report failures in the reply).)); decision text [01.md](../../experiment/playbook-uplift/decisions/01.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0103"></a>
### Are the files under sql/ part of the product?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: sql/ holds schema.sql (a pre-spec-227 schema with single-column keys and no graph_id), globals_schema.sql (an unqualified procedure and two stub triggers on Graph_KG.rdf_edges), graph_path_globals.sql and graph_walk_tvf.sql (unqualified procedures), migrations/000-002 (the 2025 NodePK migration) and procedures/ kg_PageRank.sql (comments only). Setup runs none of them; the sdist ships them; scripts/deploy_production.py still runs sql/schema.sql and sql/operators_fixed.sql. The index of this upli…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0103.md](../../experiment/playbook-completion/intent/HD-0103.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same status and gist. Refined with the maintainer's 'one schema path' statement, the 4.7.0 maintenance and test of the legacy deployer, the fact that the sdist ships sql/ but not scripts/, and fraud_sample_data.sql as live demo data.)); decision text [01.md](../../experiment/playbook-uplift/decisions/01.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0201"></a>
### What does a Python read with no graph argument read?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the USER_GUIDE says Python methods that read take `graph=` and, omitted, mean the default graph, never every graph (docs/USER_GUIDE.md:466-467). Several readers take no `graph=` at all and read every graph: `get_node_ids_by_label`, `get_node_ids_by_property`, `get_property_pairs`, `get_property_values`, `property_value_exists`, `get_node_ids_like`, `count_subjects_with_property`, `nodes_exist` (iris_vector_graph/_engine/nodes_edges.py:760-966, 2590-2625). Their docstrings say "all graphs" or "n…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0201.md](../../experiment/playbook-completion/intent/HD-0201.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same status and choice. Strengthened by maintainer tasks R219/R249 (one rule for the Python API), the explicit HTTP /schema exception in ADMIN_API, and the third rule found on delete_node. The live probe confirms F-0206.)); decision text [02.md](../../experiment/playbook-uplift/decisions/02.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0202"></a>
### In a multigraph, does a direct edge delete remove one parallel edge or all of them?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `delete_edge(s, p, o, graph=g)` deletes every row of the triple in `g` (iris_vector_graph/_engine/nodes_edges.py:1429-1433). Spec 234 gives the direct API `create_edge` a multigraph rule (FR-007) and Cypher `DELETE r` a per-edge rule (US1 scenario 2), but says nothing about `delete_edge`.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0202.md](../../experiment/playbook-completion/intent/HD-0202.md) (status supported· Confidence: medium · Changed from decisions.md: yes (decisions.md said spec 234 leaves the direct delete ambiguous, and so marked it an assumption. The spec's plan.md:160-162 addresses delete_edge explicitly and names the triple-wide meaning as the no-edge_id contract, so the status is no); decision text [02.md](../../experiment/playbook-uplift/decisions/02.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0301"></a>
### Does ledger strict mode cover the standalone bulk loader?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: strict mode refuses the engine's direct writes (docs/USER_GUIDE.md:1107-1121) through a check in each engine method (`ledger_check`, iris_vector_graph/_engine/ledger.py:72-79). `iris_vector_graph.bulk_loader.BulkLoader` takes a DB-API connection, not an engine, and has no such check (bulk_loader.py:56-78, 252-272, 380-402), so it writes nodes, labels, properties and edges with no ledger record while strict mode is on. Is that intended?
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0301.md](../../experiment/playbook-completion/intent/HD-0301.md) (status supported· Confidence: high · Changed from decisions.md: no (Same status and reading. Added the contradiction that the promised documentation of the exclusion is missing from the user guides.)); decision text [03.md](../../experiment/playbook-uplift/decisions/03.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0302"></a>
### May a direct edge delete remove an edge row that a temporal edge still implies?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: ADR-0009 says every temporal edge implies a structural edge for its triple, kept as a marked row that only the temporal side removes (CONTEXT.md:66-73). `delete_edge(s, p, o, graph=g)` deletes the triple's rows whether or not they are marked (iris_vector_graph/_engine/nodes_edges.py:1429-1433), leaving the temporal events with no structural edge.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0302.md](../../experiment/playbook-completion/intent/HD-0302.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (decisions.md marked this Supported. The accepted ADR does not cover a structural delete, and maintainer test test_delete_edge_then_purge (7374d3b4) exercises and accepts the opposite outcome. So the status is now assumption. The workin); decision text [03.md](../../experiment/playbook-uplift/decisions/03.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0401"></a>
### How should erase and rebuild retire a source generation?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the degree cache's reader protocol (ADR-0012, `Graph.KG.Adj.Degree`) assumes a source generation only moves forward. `Adjacency.RemoveSource`, `RemoveGraph` and `RemoveAll` kill `^KG("gen")` instead, so a generation can return to a value an in-flight reader already read (finding F-0401). Which rule should hold?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0401.md](../../experiment/playbook-completion/intent/HD-0401.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live evidence confirms the ABA precondition; the spike's 'or kill' explains why the maintainer accepted the kill for stale entries, but neither source covers an in-flight reader, so the working answer stands.)); decision text [04.md](../../experiment/playbook-uplift/decisions/04.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0402"></a>
### May two adjacency rebuilds run at the same time?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `TraversalBuild.BuildKG` takes the writer lock on the parent name in shared mode (`Adjacency.BeginRebuild`), which keeps readers from caching but does not keep a second `BuildKG` out. Only the interned snapshot's build has its own exclusive lock (`^IVG.NKGBuild`). `docs/ADMIN_GUIDE.md:1049-1050` says "One rebuild runs at a time", naming that lock. Is a second `sync()` while one runs supported (and if so, what must the result be), or should it wait or be refused?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0402.md](../../experiment/playbook-completion/intent/HD-0402.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live check confirms the decisions.md reading (the cited lock protects only the ^NKG path); no new authority.)); decision text [04.md](../../experiment/playbook-uplift/decisions/04.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0501"></a>
### Are the end nodes a temporal write creates governed by the ledger?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: with the adjacency index, every structural temporal write inserts its two endpoint rows into `Graph_KG.nodes` when they are missing (`Adjacency.AssertTemporalRow`, `Adjacency.cls:591-602`). Node rows are governed content: `verify()` reads every one (`replay.py:590-597`). Neither the engine path nor a changeset's `create_temporal_edge` op records them, and strict mode does not refuse the write. Should those nodes be recorded, refused, or excluded from what `verify()` compares?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0501.md](../../experiment/playbook-completion/intent/HD-0501.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (decisions.md left 'record them or derived provenance' open. Commit 43efd473 ('temporal writes still create no revisions', mirror 'no longer an unrecorded write', endpoints asserted by the same commit) argues against recording engine-pa); decision text [05.md](../../experiment/playbook-uplift/decisions/05.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0502"></a>
### Is the temporal index inside the ledger's guarantee?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: CONTEXT.md:75-76 says a temporal edge is "subject to the revision ledger (via a Changeset temporal op)". At the pin a changeset can write temporal edges in the ledger's transaction and records `create_temporal_edge` with the triple, graph and time only (`LedgerApply.cls:637-640`). There is no op for a temporal delete, purge, bucket purge or row drop; engine temporal writes make no revision (`test_ledger_us11_temporal_coexist.py::test_temporal_writes_and_purges_create_no_revisions`); replay igno…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0502.md](../../experiment/playbook-completion/intent/HD-0502.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (Status lowered from supported to assumption: the only decision (43efd473) settles 'temporal writes create no revisions'; the exclusion of changeset temporal ops from reconstruct/verify rests on implementation and tests, and the accepte); decision text [05.md](../../experiment/playbook-uplift/decisions/05.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0601"></a>
### Are the IVF, tree (VecIndex) and PLAID indexes inside the erasure promise?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: erasure is defined as removing a graph's content "from every store" (CONTEXT.md:198-208, ADR-0004), but `^IVF`, `^VecIdx` and `^PLAID` are keyed by index name only, hold no graph, and are named nowhere in `Graph.KG.Eraser` or the `Graph.KG.GraphStores` inventory. The 4.0.0 migration guide calls the IVF index a "remaining gap" (docs/migration/v4.0.0.md:742-750). After `EraseGraph(g)`, must these indexes stop answering g's node ids and stop holding g's vectors?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0601.md](../../experiment/playbook-completion/intent/HD-0601.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live reproduction and the Eraser/GraphStores precedents strengthen the working answer; no authority decides it.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0602"></a>
### May an index build be seen half-done, and may a stopped build leave a partial index?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `ivf_build` calls `Build` (which kills `^IVF(name)`), then `AddBatch` per 500 rows, then `FinalizeIndex`, each a separate call with no lock and no transaction; `VecIndex.Build` kills the trees and rebuilds them; `PLAIDSearch.Build` kills `^PLAID(name)` and refills it. A search during the build sees an empty or partial index, and a stopped build leaves one. Is that acceptable?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0602.md](../../experiment/playbook-completion/intent/HD-0602.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live evidence confirms the baseline; no source settles the service level.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0603"></a>
### Should the vector-and-graph search keep its k best candidates?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `kg_VECTOR_GRAPH_SEARCH` puts vector hits, their one-hop neighbours and text hits in a Python set, keeps `all_entities[:k]` (any k, set order), then sorts those k by vector similarity (`iris_vector_graph/_engine/vector.py:1513-1543`). The best vector hits can be dropped before the sort. The docstring admits "keeps k of that set in no particular order". Is that the intended contract?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0603.md](../../experiment/playbook-completion/intent/HD-0603.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live evidence quantifies the baseline; the R025 documentation is a description, not a decision.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0604"></a>
### May two embed queue workers run at once?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the queue has no claim state (`ClaimPendingBatch` is "a plain ordered scan", `EmbedQueue.cls:22-25`), yet a namespace can run the IRIS task (`start_background_embedding`) and the Python `process_embed_queue` at the same time, or two Python workers. Both then process the same PENDING entries: double model calls, last writer wins on the vector, and status races between DONE and ERROR.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0604.md](../../experiment/playbook-completion/intent/HD-0604.md) (status supported· Confidence: high · Changed from decisions.md: yes (Status assumption -> supported for the single-consumer design premise: commit 5bb149ed states 'Single-processor' explicitly. The enforcement question stays open.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0701"></a>
### Must a BM25 Build (and Drop) exclude writers and be all-or-nothing?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: ADR-0007 says schema 2 "does every write under an index-level lock in a transaction", but the spec's requirement (FR-019) names only Insert and Delete. `Build` kills `^BM25Idx(name)` and rewrites it with no lock and no transaction; `Drop` kills with no lock. While a Build runs, what may an Insert, a Delete, a second Build, a Drop or an Upgrade on the same name do, and may a stopped Build leave a partial index?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0701.md](../../experiment/playbook-completion/intent/HD-0701.md) (status assumption· Confidence: medium (intent), high (as-built) · Changed from decisions.md: no (evidence now live; status unchanged)); decision text [07.md](../../experiment/playbook-uplift/decisions/07.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0702"></a>
### Which reciprocal-rank-fusion rule is the product's?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: five surfaces fuse a vector list with a text list by rank, with three rules for an item one list lacks and two different text lists: engine `kg_RRF_FUSE` (BM25 index; missing item at place `len(leg) + c`, so it adds `1/(2c + len)`), SQL `kg_RRF_FUSE` and `/hybridSearch` (docs-table term counts from `kg_TXT`; missing item at place 10^9), `CALL ivg.retrieve` and `RRFFusion.fuse_results` (missing item adds 0). The engine method and the SQL procedure share a name and can rank the same query differe…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0702.md](../../experiment/playbook-completion/intent/HD-0702.md) (status assumption· Confidence: medium (intent), high (as-built) · Changed from decisions.md: no); decision text [07.md](../../experiment/playbook-uplift/decisions/07.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

Iteration 2 reconciliation: the G canonical question provisionally favors a common zero absent contribution; the P intent file instead defaults to documenting distinct surfaces. Both are unratified proposals, not conflicting product observations. Preserve both options; the new Python-only RRF proof settles neither a product-wide rule nor which text corpus is intended. Owner: search.fusion.absent.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0703"></a>
### Is spec 044's kg_TXT-to-BM25 fallback still wanted?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: spec 044 FR-012 and User Story 5 say that when iFind is unavailable `kg_TXT` uses a BM25 index named `default` before the LIKE fallback. No code does this at the pin: `kg_TXT` goes straight to LIKE. Spec 230 later re-keyed `docs` and gave `kg_TXT` a graph, and a BM25 index named `default` covers one graph only.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0703.md](../../experiment/playbook-completion/intent/HD-0703.md) (status assumption· Confidence: medium · Changed from decisions.md: **yes** (was "Supported. Honor the documented); decision text [07.md](../../experiment/playbook-uplift/decisions/07.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0704"></a>
### Is `__stop__` a reserved BM25 index name?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the stopword list lives at `^BM25Idx("__stop__")`, beside the indexes. `Build`, `Insert`, `Drop` and `Search` accept the name `__stop__`; `Drop("__stop__")` deletes the stopword list (rebuilt on the next tokenize) and `Build("__stop__", ...)` mixes an index into it. `List()` skips the name. Should writers refuse it, or should the stopword list move out of the index global?
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0704.md](../../experiment/playbook-completion/intent/HD-0704.md) (status supported(outcome: `^BM25Idx("__stop__")` is the stopword list, not an index) · mechanism: assumption ·); decision text [07.md](../../experiment/playbook-uplift/decisions/07.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0705"></a>
### Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: all three are exported from `iris_vector_graph` (`__all__`) but none is in `docs/API_REFERENCE.md`. `TextSearchEngine` still uses the `%FIND(col, ?)` predicate the repo calls invalid elsewhere, reads an unqualified table, and has no graph scope. Fix them to the product's rules, deprecate them, or remove them?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0705.md](../../experiment/playbook-completion/intent/HD-0705.md) (status assumption· Confidence: medium · Changed from decisions.md: no (refined per class; one factual correction to); decision text [07.md](../../experiment/playbook-uplift/decisions/07.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

Iteration 2 owner recovery: search.fusion.python.support makes this policy visible from the canonical ontology. Preserve the intent file's correction: only RRFFusion and TextSearchEngine are exported at top level; HybridSearchFusion is module-level. The new contract covers shipped RRFFusion/HybridSearchFusion behavior without declaring all three supported public API.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0801"></a>
### Where and how should ledger strict mode refuse a Cypher write?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: strict mode is enforced only by the Python `LedgerGuard` of each engine (`iris_vector_graph/ledger/guard.py:38-80`). It caches the ledger's setting for 5 s and fails open when the probe fails. IRIS itself does not refuse (`Graph.KG.Ledger.SetStrict` only sets `^IVG.Ledger("meta","strict")`). The contract (`specs/213-graph-revision-ledger/contracts/ledger-api.md:82-92`) says the guarded calls "raise `LedgerStrictModeError` and change nothing", with no window and no fail-open case. The redaction…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0801.md](../../experiment/playbook-completion/intent/HD-0801.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (Sharpened. decisions.md left 'the gap needs explicit treatment' and called the failure modes 'documented'. They are undocumented outside the code. The window is now reproduced live against the contract. The R206 commit shows a maintain); decision text [08.md](../../experiment/playbook-uplift/decisions/08.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0802"></a>
### Does a mapped label belong to every graph?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `map_sql_table` maps a label to an outside SQL table for the whole namespace. The graph filter of a scoped query is added only to the four graph tables (`translator.py:404`, `719-779`), so under `USE GRAPH 'g'` a mapped label still answers every row of its table. The glossary says graphs are isolation units (CONTEXT.md:27-37); the mapping docs say nothing about graphs.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0802.md](../../experiment/playbook-completion/intent/HD-0802.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same reading. The live probe confirms global visibility, even under a graph that holds nothing. No new authoritative source found.)); decision text [08.md](../../experiment/playbook-uplift/decisions/08.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0803"></a>
### Is `sql/operators.sql` product code?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `sql/operators.sql` defines `kg_KNN_VEC`, `kg_TXT`, `kg_RRF_FUSE`, `kg_GRAPH_PATH`, `kg_RERANK` and `kg_PPR` with no graph argument, unqualified table names and a label join without `graph_id`. Nothing in the package or setup loads it (the live procedures are in `iris_vector_graph/schema.py:2437-2526`; `scripts/deploy_production.py` loads `sql/operators_fixed.sql`). The uplift's denominator counts it as product SQL.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0803.md](../../experiment/playbook-completion/intent/HD-0803.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (Status changed from supported to assumption. The deployment paths are facts (now also live) that identify what runs. Whether the file is product code is a maintainer decision that no source states. Same classification otherwise.)); decision text [08.md](../../experiment/playbook-uplift/decisions/08.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0804"></a>
### Should `CREATE CONSTRAINT` / `CREATE INDEX` be refused rather than accepted as a no-op?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `execute_cypher` answers any text that starts with `CREATE CONSTRAINT`, `DROP CONSTRAINT`, `CREATE INDEX`, `CREATE TEXT INDEX`, `CREATE RANGE INDEX`, `CREATE POINT INDEX`, `DROP INDEX`, `CREATE FULLTEXT` or `CREATE LOOKUP` with an empty result and does nothing (`iris_vector_graph/_engine/query.py:1886-1897`). A client that creates a uniqueness constraint believes it is enforced. It exists so that Neo4j tools that send such DDL keep working.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0804.md](../../experiment/playbook-completion/intent/HD-0804.md) (status supported· Confidence: high · Changed from decisions.md: yes (Status changed from assumption to supported. The maintainer commit f4a13d75 states that skipping the DDL is correct behaviour, which settles refuse-vs-accept. 'Make it visible' remains a proposal.)); decision text [08.md](../../experiment/playbook-uplift/decisions/08.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0901"></a>
### Should a running engine notice a revoked table right or a dropped adjacency index?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the native gate asks three facts once per engine and keeps them: SELECT on the four graph tables (`engine._native_privileges`, never asked again), the adjacency index (`_adjacency_indexed`, asked again only by `initialize_schema`) and the executor's plan version (same). The native path reads globals, which SQL rights do not guard (ADMIN_GUIDE, "What is the boundary"). After `REVOKE SELECT` on `rdf_props`, or after another process drops `idx_edges_adj`, a long-lived engine keeps reading natively…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0901.md](../../experiment/playbook-completion/intent/HD-0901.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (decisions.md required authorization at use for both facts. FR-011 itself permits caching per process and user, and the later R280 maintainer statement makes the database resource the native boundary. Authorization at use via SQL grants); decision text [09.md](../../experiment/playbook-uplift/decisions/09.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0902"></a>
### Should shadow mode fail when the native path raises an error?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: spec 253 US1 says shadow mode "fails on any difference"; US4 and FR-007 say any native failure falls back to SQL with a warning once per reason. In shadow mode a native exception today makes `_try_native` answer None, the SQL path answers, and nothing is compared (`query.py:2071-2073`), so a native defect that raises is invisible to a shadow run except for one warning line. Should shadow mode raise `NativeMismatch` (or another error) when the native path raises?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0902.md](../../experiment/playbook-completion/intent/HD-0902.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same reading. Strengthened by the live probe and by the code's own asymmetry (a SQL error already counts as a mismatch).)); decision text [09.md](../../experiment/playbook-uplift/decisions/09.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0903"></a>
### What may a native read answer while another writer's transaction is open?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: a native read takes no lock and no snapshot (NAT-T4.6). It reads `^KG` (adjacency and labels), the `rdf_props` storage globals and, for an id or property start, the node and property rows through SQL, at moments spread over the walk. A writer's open transaction is visible to it (P-0002), and may be visible in part: a new edge's `^KG` entry before its far node's label, or a property changed between two reads of the same run. Spec 253 speaks only of the caller's own transaction. Is "whatever each…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0903.md](../../experiment/playbook-completion/intent/HD-0903.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same reading. decisions.md's caveat that the earlier probe 'does not establish every SQL read has the same isolation' is now answered for this pattern: the SQL path matched native at every step, and USER_GUIDE:260-262 documents dirty vi); decision text [09.md](../../experiment/playbook-uplift/decisions/09.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-0904"></a>
### Should a compiled plan that fails while running be set aside?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: ADR-0014 says the interpreter answers every shape that is not compiled, failed to compile or cannot be recorded. A compiled class that compiles but raises while it runs (a generator defect, a class deleted under a running read) is not covered: the error leaves `Run`, the engine falls back to the SQL path (NAT-T6.1), and the entry stays "ok", so every later read of that shape fails natively first and is answered by SQL. Should such a failure mark the entry so the interpreter answers the shape ne…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0904.md](../../experiment/playbook-completion/intent/HD-0904.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (Refined. decisions.md said 'a fallback outcome' without naming one. ADR-0014's invariant and spec 257 FR-004 name the interpreter as the fallback, and Gen's 'a failed build is not tried again' rule is the existing quarantine precedent.); decision text [09.md](../../experiment/playbook-uplift/decisions/09.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1001"></a>
### What should `random_walk` answer, and over which graph?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `random_walk` needs the Arno library and answers `[]` without it, although the walk it calls (`NKGAccelTraversal.RandomWalkJson`) is ObjectScript; with the library it walks `^NKG`, every graph merged (F-1002). No spec states its intent.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1001.md](../../experiment/playbook-completion/intent/HD-1001.md) (status assumption. random_walk takes no graph, so it walks the default graph (USER_GUIDE), and it answers with or without the library (ADMIN_GUIDE, CONTEXT). Neither [] for a missing library nor a merged-graph walk meets both. No spec covers random_walk; the docstring describes the [] behaviour but was wri); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1002"></a>
### Should label propagation say when its labels did not settle?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `kg_CDLP` returns the last round's labels after `max_iterations`, and labels often swap every round (`docs/COMMUNITIES.md:192-208`); `kg_WCC` and `eigenvector_centrality` raise when they do not converge.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1002.md](../../experiment/playbook-completion/intent/HD-1002.md) (status supported. The current public contract is option (c): a fixed-iteration synchronous CDLP that returns the last round with no in-band signal. The documented diagnostic is to compare k with k+1. The maintainer documented this deliberately (af2bc84e W6). A settledness flag would be a compatible strengt); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1003"></a>
### Should the shortest-path routines refuse a direction they do not walk?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `TraversalPaths.ShortestPathJson` walks only `"out"` and `"both"` and answers no path for anything else; `ShortestLength` reads any value but `"both"` as `"out"`. The store and query callers guard (they turn `"in"` round), but both are callable class methods. `DijkstraJson` and `DijkstraCost` refuse through `CheckDirection`.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1003.md](../../experiment/playbook-completion/intent/HD-1003.md) (status supported. A routine must not answer an unsupported direction as 'no path' or as another direction's path. It refuses a direction outside its set or implements it; this is maintainer policy in 99b00ce9. Whether the class methods implement 'in' or refuse it is open. Python store methods carry the pub); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1004"></a>
### How many nodes should global PageRank list?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the ObjectScript owner stops at 10,000 rows; the native reader lists every node (F-1003). The method takes no top-k, and the docs promise neither.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1004.md](../../experiment/playbook-completion/intent/HD-1004.md) (status supported. (a): every node of the default graph is listed on every route, and the scores sum to 1 over node_count(). The 4.6.0 R306 docstring (a node with no edge used to have 'no pair') and spec 236's same-node-set rule settle it. The 10,000 cap is an undocumented 2026-03 leftover.); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1101"></a>
### What should a node change do when only a named graph holds the id?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the ledger keeps nodes in the default graph (4.6.0 R281/R290) but asks whether a node exists by id in any graph (`Graph.KG.LedgerApply.NodeExists`, `iris_src/src/Graph/KG/LedgerApply.cls:79-84`), on purpose for edge end nodes (`:86-95`). For a node id that only a named graph holds, what should `create_node`, `upsert_node`, `set_prop`, `add_label`, `remove_*` and `delete_node` (plain and detach) do?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1101.md](../../experiment/playbook-completion/intent/HD-1101.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1102"></a>
### Should disable() and set_strict() refuse a caller's open transaction, as enable() does?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: 4.7.0 made `enable()` and `redact()` refuse a caller transaction that holds a write (`iris_vector_graph/ledger/client.py:268-279`), because over a separate Native API connection they ran outside it. `disable()` and `set_strict()` were not changed (`:299-309`): they run `Graph.KG.Ledger.Disable` / `SetStrict` through `engine._iris_obj()`, which is the caller's own process for an engine made on a connection without stored credentials and another process for a `from_connect` engine (`iris_vector_g…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1102.md](../../experiment/playbook-completion/intent/HD-1102.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1103"></a>
### Should strict mode be enforced by the server, or stay a Python-only check?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: strict mode is checked only by `iris_vector_graph.ledger.guard.LedgerGuard` before engine writes (`iris_vector_graph/ledger/guard.py:75-80`). It caches the state for 5 s per engine and fails open when it cannot read it (`:38-59`). The server's own writers (`Graph.KG.Eraser`, `Graph.KG.TemporalIndex`, the SQL procedures), raw SQL, `BulkLoader`, the GraphQL mutations and other clients are not held to it. The contract documents "BulkLoader and raw SQL are not guarded" (`specs/213-graph-revision-le…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1103.md](../../experiment/playbook-completion/intent/HD-1103.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1104"></a>
### Should the ledger's settings be changeable after the genesis?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `max_ops` (the size limit) and `recon_bound` are written only by the genesis (`iris_src/src/Graph/KG/Ledger.cls:289-292`). `enable()` on an enabled ledger ignores every argument (`:254-260`). Re-enable after disable ignores `max_ops` and `recon_bound` but overwrites strict mode with the value passed, which defaults to off (`:271-275`), so `set_strict(True)`, `disable()`, `enable()` leaves strict off, and a `set_strict(True)` made while disabled is lost on re-enable. Is this the intended lifecyc…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1104.md](../../experiment/playbook-completion/intent/HD-1104.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1105"></a>
### Should post-commit properties be recorded by the ledger?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `post_commit_properties` (spec 218, "Approach A: direct SQL, no new revision", `iris_vector_graph/ledger/client.py:430-487`) write `rdf_props` rows outside the revision: they are unrecorded writes to a governed store, so `verify()` reports them (upstream comment in `tests/e2e/test_470_ledger_caller_txn_e2e.py:218-219`), redaction's liveness check sees them, and replay never rebuilds them. They are written outside the head lock and, with no caller transaction, in a second transaction.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1105.md](../../experiment/playbook-completion/intent/HD-1105.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1201"></a>
### Should a graph erasure take the ledger head lock?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: EraseGraph/EraseNodes take no head lock (F-1201). Take it for the whole erasure transaction, or document that erasure needs a quiet graph? Also: may a redaction run start while an erasure of its target is open (its liveness check reads the erasure's uncommitted deletes)?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1201.md](../../experiment/playbook-completion/intent/HD-1201.md) (status assumption. Outcome supported: a redaction must never complete against content whose erasure has not committed (ADR-0013:17, FR-005, CONTEXT.md:212), and an erasure must not leave a live row without its statement (ADR-0004:79-80 classifies such a write path as a bug). The mechanism is not settled: n); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Related here: q-004 (related, not the same question).

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1302"></a>
### Which rule clears a revision's free text: any tombstone or every record?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: F-1301. The code and ADR-0013 follow Decision 2 (any). Amend spec 256 FR-004?
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1302.md](../../experiment/playbook-completion/intent/HD-1302.md) (status supported. Clear the free text of any revision with at least one redacted record (Decision 2, accepted ADR-0013). FR-004's 'every' and acceptance scenario 2's wording are stale.); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1303"></a>
### Can an unfinished redaction be abandoned, and what may a default-graph target touch?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: (a) a run stuck on a live target (RED-B8.2) blocks every ledger write into it until the target is erased again; should an operator be able to abandon a run? (b) should a default-graph target with no prefix count node rows of every graph, or be refused (F-1304)?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1303.md](../../experiment/playbook-completion/intent/HD-1303.md) (status assumption(by part: (a) assumption, (b) supported). (b) supported: the maintainer's plan (2b8ea46d, plan.md:10) makes the node-liveness check for a default-graph target graph-blind, and the code gives the reason (145-148); so a no-prefix default-graph target must be refused while any node row of any); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1304"></a>
### How is a tenant's node history redacted when nodes live in the tenant's own graph?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: F-1305. Record the node's graph in ledger node records (a layout change), or require tenant id prefixes and say so in the redaction docs?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1304.md](../../experiment/playbook-completion/intent/HD-1304.md) (status assumption. Supported at this pin that node records are addressable only by id prefix (accepted ADR-0013:37), so the documented tenant procedure presupposes tenant-prefixed ids. What a graph-per-tenant tenant with unprefixed ids should get is not settled: the spec promises erasure for exactly that d); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1305"></a>
### Should a replayed commit apply its post-commit properties?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: F-1306 / F-1101. A replay currently re-applies them, which can revive erased content between erasure and redaction.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1305.md](../../experiment/playbook-completion/intent/HD-1305.md) (status supported. Supported: a replay returns the original outcome and applies nothing (spec 213 API contract, upstream test), and a retry must not re-create an erased tenant (ADR-0013:15, spec 256 edge case). The mechanism (skip on replayed=True, or record durable completion of post-commit writes) is not ); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Related here: q-010 (related, not the same question).

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1401"></a>
### Verification and record readers: node identity and redaction checks

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: (a) verification compares nodes by id across graphs while a ledger delete removes only the default graph's node (F-1401): which should change? (b) should record readers check for a redaction again after reading (F-1402)?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1401.md](../../experiment/playbook-completion/intent/HD-1401.md) (status assumption(by part: (a) assumption, (b) supported (outcome)). (b) outcome supported: a reader returns a pre- or post-redaction view or refuses, never a half-done one (Decision 3, which replaced 'atomic from a reader's view', and the client's own message). The mechanism is not settled. (a) undecided ); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1501"></a>
### Should a FHIR sync be governed by the ledger?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: a FHIR sync, rebuild and reinterpret write nodes, labels, properties and edges of the FHIR graph from ObjectScript (`Graph.KG.FHIRGraph`), with no ledger record. Strict mode is enforced only in the Python guard (`iris_vector_graph/ledger/guard.py:75-80`), and `FHIRGraph.cls` never reads `^IVG.Ledger("meta","strict")`, so strict mode does not refuse them. `docs/USER_GUIDE.md:1107-1109` says strict mode refuses writes outside the ledger.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1501.md](../../experiment/playbook-completion/intent/HD-1501.md) (status assumption. No authoritative source decides. The FHIR guide describes a projection that converges on the repository (supports exemption); the user guide and glossary describe strict mode/ledger coverage broadly enough to include it.); decision text [15.md](../../experiment/playbook-uplift/decisions/15.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1502"></a>
### Should erasing a FHIR graph stop its sync task?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `EraseGraph` keeps the `fhir_graphs` row and sets both watermarks to 0 (`Eraser.cls:1151-1180`). A scheduled `Graph.KG.FHIRGraphSyncTask` keeps running, and its next run re-projects the whole repository into the graph. When the FHIR graph is erased for a tenant (and then to be redacted), the content comes back on the next tick, and redaction refuses a live target.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1502.md](../../experiment/playbook-completion/intent/HD-1502.md) (status supported. Erase of a FHIR graph is a transient content clear that keeps registration (supported: Eraser.cls comment, CHANGELOG 4.1.0, ADR-0015:29, upstream E2E test). Whether a durable tenant removal must also stop the feed is not stated anywhere.); decision text [15.md](../../experiment/playbook-uplift/decisions/15.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1503"></a>
### What happens when an erase runs during a FHIR sync?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `Graph.KG.Eraser.EraseGraph` takes no lock, and in particular not the sync lock `^IVG.FHIRGraph(graph)`. A sync running in another process can commit its next batch, and move its watermark, after the erase commits. The graph then holds the rows of that batch only, with a watermark past rows it no longer has, until a rebuild. This is reasoned from the code (`Eraser.cls:47-57`, `FHIRGraph.cls:1964-1966`), not observed.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1503.md](../../experiment/playbook-completion/intent/HD-1503.md) (status assumption. The outcome is documented (after erase, syncs re-project the repository and converge on a rebuild); the mechanism under concurrency (lock, compare-and-set, or quiescence premise) is not stated.); decision text [15.md](../../experiment/playbook-uplift/decisions/15.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1504"></a>
### Should one unreadable FHIR resource block its graph's sync?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: a resource whose body is not JSON, nests deeper than 64 levels, or has more than 10,000 json-link matches makes `ResyncKey` throw (`FHIRGraph.cls:2380-2397`, `:2976-2977`, `:2983-2988`). Its batch rolls back and the watermark stays, so every later sync fails on the same batch and no later change reaches the graph. With the default json links (they include an extension entry) every resource body is read.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1504.md](../../experiment/playbook-completion/intent/HD-1504.md) (status supported. Fail the batch, name the key, keep the watermark, repeat on the next sync (no skip). Stated for the walk limits (FHIR_GRAPH.md:196-199) and for any failed batch (:255-257). The resulting indefinite stall and its recovery are not documented.); decision text [15.md](../../experiment/playbook-uplift/decisions/15.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1601"></a>
### Should a server limit which graphs a caller may name?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: every interface uses whatever graph a caller names (GraphQL `graph:`, the FHIR event `graph` field, the REST dispatcher's `graph`, `USE GRAPH` in Cypher over HTTP, Bolt and MCP). The docs say a graph ID is not a security boundary and tenants need separate namespaces (`docs/USER_GUIDE.md:467-468`, `docs/FHIR_GRAPH.md:553-556`), while `CONTEXT.md:248-250` plans an Execution Context that binds a session to one graph, and spec 256 models a tenant as a named graph plus an id prefix inside one namesp…
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1601.md](../../experiment/playbook-completion/intent/HD-1601.md) (status supported. The IRIS namespace is the only isolation and authorization boundary. Graph ids scope data operations and confer no authorization. The Execution Context is a planned guard against accidental cross-graph writes, not an access-control feature.); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1602"></a>
### Should admin work need a different key from reading?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the Cypher HTTP server has one `IVG_API_KEY`. The same value that runs a read also runs `/admin/schema/init`, `/admin/load`, `/admin/indexes/rebuild` and `DELETE /admin/queries/{id}`, which ends any IRIS process the server's IRIS user may kill.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1602.md](../../experiment/playbook-completion/intent/HD-1602.md) (status supported. The documented contract is one key for every route. Admin writes, including kill, are disabled only through IVG_READ_ONLY, which also refuses Cypher writes. The privilege of IRIS_USERNAME bounds what the server can do. A separate admin credential has never been specified.); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1603"></a>
### Should the Cypher HTTP server run a failed query a second time?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `_run_cypher` (`iris_vector_graph/cypher_api.py:239-250`) resets the engine and runs the query again after any exception, writes included. A write whose commit reached IRIS before the error (for example a dropped connection after commit) would then be applied twice; a refused write is attempted twice.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1603.md](../../experiment/playbook-completion/intent/HD-1603.md) (status assumption. No spec or doc states the policy. The earliest maintainer code retried only connection or licence failures, which is evidence for (b). The widening was not explained. Re-running a write whose commit outcome is unknown conflicts with the project's own idempotency design, which keeps it in); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1604"></a>
### Should the REST dispatcher's `/metaPath` take a graph?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `/vectorSearch` and `/hybridSearch` gained a `graph` field (spec 230 FR-014); `/metaPath` has none and always walks the default graph (`iris_src/src/Graph/KG/Service.cls:304-319`), though `Traversal.BFSJSON` accepts one.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1604.md](../../experiment/playbook-completion/intent/HD-1604.md) (status assumption. Default-graph-only is consistent with the general rule that an omitted graph means the default graph. No source requires /metaPath to take a graph, and spec 230, which the search routes cite, is not available. Accepting `graph` would be a compatible extension. Ignoring a supplied `graph`); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1605"></a>
### Should the generated GraphQL server match the sample API's safety limits?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `iris_vector_graph.gql.create_app` has the key gate but no depth limit (its `Node.outgoing` -> `Relationship.node` -> `Node.outgoing` nests without bound), no read-only middleware (only its `cypher` field checks), and a health route that always answers healthy (F-1611). The sample API has `QueryDepthLimiter` with `IVG_GRAPHQL_MAX_DEPTH`.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1605.md](../../experiment/playbook-completion/intent/HD-1605.md) (status assumption. Undecided between (a) a developer server and (b) parity. The 4.6.0 releases already apply the shared HTTP gates (key, read-only) to create_app and fix its schema reading. That treats it as a deployable surface and makes (b) the better-supported direction. No source requires the depth lim); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1701"></a>
### Should the SQL adapter's pass-through refuse a write when called read-only?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `IRISGraphStore.execute_sql(sql, params, read_only=True)` and the `GraphStore` protocol carry a `read_only` flag, but nothing reads it (`iris_vector_graph/stores/iris_sql_store.py:1522-1554`). Is the flag a promise (refuse INSERT/UPDATE/DELETE/DDL when True) or a leftover?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1701.md](../../experiment/playbook-completion/intent/HD-1701.md) (status assumption. Undocumented flag; the protocol's design rule (raise rather than ignore a semantic parameter) and the enforced engine-level read_only point to 'a requested guarantee', but no source defines execute_sql's flag.); decision text [17.md](../../experiment/playbook-uplift/decisions/17.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1702"></a>
### Should the HTTP client resend a write query after a server error?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `IVGClient._post` retries `POST /api/cypher` up to `max_retries` (3) times on a 5xx, a connect error or a timeout, with 0.5 s, 1 s backoff (`iris_vector_graph/sdk.py:209-228`). A Cypher `CREATE` whose first attempt committed on the server and then failed to answer (a 5xx after the commit, or a timeout) is sent again.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1702.md](../../experiment/playbook-completion/intent/HD-1702.md) (status assumption. Retry on 5xx/connect/timeout is a deliberate, documented client feature (commit aaa54a44, docstrings, tests). No source addresses whether a non-idempotent write may be resent after an ambiguous outcome.); decision text [17.md](../../experiment/playbook-uplift/decisions/17.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1703"></a>
### Should the SQL adapter's capability list say what this namespace can run?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `IRISGraphStore.capabilities()` returns `_FULL_CAPABILITIES`, every algorithm `True`, whether or not the ObjectScript classes are deployed or the accelerator is loaded; only the `*_arno` keys vary (`iris_vector_graph/stores/iris_sql_store.py:29-52`, `:2991-3000`). The engine uses it to choose store calls over Python fallbacks.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1703.md](../../experiment/playbook-completion/intent/HD-1703.md) (status assumption. Undocumented. The product keeps two facts: engine.capabilities (documented: what is deployed) and store.capabilities() (undocumented: what the adapter implements).); decision text [17.md](../../experiment/playbook-uplift/decisions/17.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1704"></a>
### Should the low-level vector helper refuse a vector of the wrong width?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `dbapi_utils.normalize_vector` pads a short vector with zeros, truncates a long one and turns NaN/Inf into 0.0 (logged only under `IRIS_VECTOR_DEBUG`); `insert_vector` then writes it (`iris_vector_graph/dbapi_utils.py:29-98`). The engine's own writers refuse a width mismatch (ADR-0006, `EmbeddingIdentityConflict`). Which rule do the public helpers follow?
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1704.md](../../experiment/playbook-completion/intent/HD-1704.md) (status supported. The helper contract is lossy coercion (docstring); registry-aware engine writes are strict (ADR-0006). Two boundaries, both stated.); decision text [17.md](../../experiment/playbook-uplift/decisions/17.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1705"></a>
### Should server start refuse to listen on every address without an API key?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `deploy/README.md:86` says the server refuses `auth: none` with `host: 0.0.0.0` unless `--force-no-auth`; `docs/ADMIN_GUIDE.md` section 5 says that with `IVG_API_KEY` unset the server asks for no key and listens on `0.0.0.0:8200`. The code does the latter (`iris_vector_graph/cli.py:419-441`, no `--force-no-auth` option).
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1705.md](../../experiment/playbook-completion/intent/HD-1705.md) (status assumption. Document precedence is settled toward ADMIN_GUIDE (R032), which describes the open default as the product's behaviour and advises setting a key on any reachable server; deploy/README.md:86 is a stale, never-implemented claim. Whether the product should refuse is not decided.); decision text [17.md](../../experiment/playbook-uplift/decisions/17.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="HD-1802"></a>
### Should a snapshot be a point-in-time view?

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `save_snapshot` reads each table, then each global, one after another, with no transaction, lock or ledger head check (`snapshot.py:864-1034`). Writes that land during a save can appear in one store and not another (a row without its vector, a ledger head ahead of the rows). The guides describe a snapshot as a copy "of every graph's rows and globals" without saying when.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1802.md](../../experiment/playbook-completion/intent/HD-1802.md) (status none); decision text [18.md](../../experiment/playbook-uplift/decisions/18.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="REACH-1"></a>
### Should erasure and redaction reach the store in REACH-1?

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B95: A graph erasure or a node erasure leaves the queued embedding requests of the erased nodes in place. So does erasing everything. / ERS-B95: A graph erasure or a node erasure leaves the queued embedding requests of the erased nodes in place. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="REACH-2"></a>
### Should erasure and redaction reach the store in REACH-2?

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B96: A graph erasure or a node erasure leaves the table of documents that an upgrade could not place in a graph. So does erasing everything. / ERS-B96: A graph erasure or a node erasure leaves the table of documents that an upgrade could not place in a graph. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="REACH-3"></a>
### Should erasure and redaction reach the store in REACH-3?

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B97: A graph erasure or a node erasure leaves the table of vectors of edges that an upgrade could not place in a graph. So does erasing everything. / ERS-B97: A graph erasure or a node erasure leaves the table of vectors of edges that an upgrade could not place in a graph. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="REACH-4"></a>
### Should erasure and redaction reach the store in REACH-4?

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B98: A graph erasure or a node erasure only marks the saved copy of the default graph as old. The copy stays until one of the three calls that read it builds a new one. Erasing everything removes it. / ERS-B98: A graph erasure or a node erasure only marks the saved copy of the default graph as old. The copy stays until one of the three calls that read it builds a new one. Erasing everything removes it.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="REACH-5"></a>
### Should erasure and redaction reach the store in REACH-5?

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B99: A graph erasure or a node erasure leaves the two tables where an upgrade from version 3.2 kept copies of edges. So does erasing everything. / ERS-B99: A graph erasure or a node erasure leaves the two tables where an upgrade from version 3.2 kept copies of edges. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

## Historical upstream reports, resolved at the pin

Two public reports against older releases ([#12](https://github.com/intersystems-community/iris-vector-graph/issues/12), [#13](https://github.com/intersystems-community/iris-vector-graph/issues/13)). The pinned changelog records both fixed; they are kept as controls and leads, not as current defects.

<a id="hist-012"></a>
### Upstream #12: bulk-created nodes had no id property, so directed patterns from {id: ...} found nothing (4.4.2)

Severity: Unranked

Settled as built: `CHANGELOG.md:59-60` records it fixed in 4.6.0 (R089) and checked again for 4.7.0; at the pin `create_node` sets `props["id"]` (`_engine/nodes_edges.py:1057`) and `bulk_create_nodes` (`:1648`) feeds the server loader `Graph.KG.EdgeScan.BulkIngestNodesSQL`. Not re-observed here (no IRIS). Planned use as the control of a writer-path model (reviewed plan F1); not built in this consolidation.

<a id="hist-013"></a>
### Upstream #13: count(DISTINCT) with ORDER BY and LIMIT failed on a from_connect() engine on IRIS 2026.1 (4.5.1)

Severity: Unranked

Settled as built: `CHANGELOG.md:52-58` records the fix in 4.7.0: the `from_connect()` probe also tries the aggregate shape and answers with TOP when it is refused (`engine.py::_detect_fetch_first_unsafe`, `:772`). Not re-observed here. Planned use as the control of a row-limit selector model (reviewed plan F2); not built in this consolidation.

## Inherited verification debt (playbook arm)

Proof debt the playbook arm recorded in [PROOF-DEBT.md](../../experiment/playbook-completion/PROOF-DEBT.md). These are verification gaps, not product questions; they stay visible here.

<a id="D-1"></a>
### Proof debt D-1: L1/L2 refinement proofs for every module with operations: **paid at model level** for 01-11 and 15-18 (`proofs-breadth`, `proofs-d1b`..`proofs-d1f`, 94+92+111+118+115+115 verified,

Severity: Unranked

- all modules | — | the code-to-model link is D-2/D-3 |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-2"></a>
### Proof debt D-2: Statement lemmas: each IRIS SQL statement and ObjectScript global operation equals its model evaluation (§3.4)

Severity: Unranked

- every writer and reader | journal-validated footprints (breadth lanes, `trace-conformance-ledger`), source inspection | no Verus frontend or IRIS SQL semantics library exists (PGspec is PostgreSQL and is skipped). The IRIS contract now has a Verus specification for its subset (`proofs-env`, `proofs-env2`, D-7), so a statement program can be proved against it once hand-translated; what this experiment did not provide is automated source-level verification of the product's ObjectScript/Python (no supported frontend was integrated here), so the translation is a trusted step to be checked against…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-3"></a>
### Proof debt D-3: Handler proofs: each Python/ObjectScript entry point performs its spec step (§3.5)

Severity: Unranked

- all handlers | trace conformance of one two-tenant scenario; correspondence lane's map and unchecked-line list (`correspondence/`) | no automated source-level verification of the ObjectScript/Python handlers in this experiment (no supported frontend integrated here) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-4"></a>
### Proof debt D-4: Lock-plan obligations per handler (§3.5)

Severity: Unranked

- writers of modules 11-14 and AdjW users | controlled lock probes and journal order; IRIS contract lock clauses | as D-3; F-1201 shows the eraser's plan is incomplete at the pin. Lane `lockplans` (modules 01, 05, 06, 08, 10, 16, 17) stopped at the finish request: explorer models 46/46 in 5 families (`lockplans-mc-*`, `lockplans-control-*`), live `lockplans-08-17-guarded-insert` (+`-r3`) with candidate findings F-C0811/F-C1711 not yet filed; probes for 01, 05, 10, 16 not run (`lockplans/PARTIAL.md`, not integrated) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-5"></a>
### Proof debt D-5: Composition: a committed IRIS transaction refines the serial step, chained over executions (§3.6)

Severity: Unranked

- product | `proofs/` composes participant **contracts**; trace conformance checks committed transactions of one scenario | needs D-2 and D-3 |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-6"></a>
### Proof debt D-6: Frame, key, FK, capacity, row-permutation conditions (§3.6)

Severity: Unranked

- every module | executable checks with self-tests across all modules (structural lane: ownership, storage order, row permutation, keys, FK, capacity probes, a catalog/dictionary frame oracle and a non-interference read oracle; `st-*`), correspondence checks for 11-14 (`corr-*`), CLOSURE.md's condition list | as D-2: no proof over IRIS SQL or ObjectScript |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-7"></a>
### Proof debt D-7: The IRIS environment contract as a Verus specification linked to the participant contracts: **paid at model level for the contract's Verus subset** by `proofs-env` (305 verified, 0

Severity: Unranked

- environment | executable contract r6 and contract-2 (differential, mutants) | still open: the discipline `disc` against the code (D-3/D-4); 9 clause families outside the Verus subset (X-DDL, X-STAR, X-FX, X-NOINDEX, X-VEC `$VECTOR` set/get, X2-JSON, X2-LIST, X2-TOP, X2-QUERY/MERGE/ZKILL: 513 recorded case runs, exact obligations in proofs-env2/PROOFS.md section 6; no closure premise rests on them); progress premises; several locks / regions not composed into one invariant; the Freedom's proceeding branch unobserved How each part is linked (review A-04): the Verus spec to the executable contra…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-8"></a>
### Proof debt D-8: Progress premises: fair scheduling of enabled steps, operator re-runs after a stop, ledger re-enabled, no write outside the ledger, a weakly fair queue worker (`proofs-mech` M07-L4

Severity: Unranked

- `progress.rs` of `proofs/`, `proofs-d9*`; `proofs-mech` M-07; core models' AG EF | none derived or tested against IRIS scheduling; "no writer makes a marked target live" (P-C02/PF-6) is violated at the pin (F-C1307, F-C1350) | premises, named in `TRUST.md` and `reflection/CLOSURE.md` |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-9"></a>
### Proof debt D-9: Reviewed protocol under the pin's real premises (bypass writers, three distinct target predicates, erasure rollback, readers, statement history, Decision 2, retry-key movement): **

Severity: Unranked

- erase/redact/replay | explorer core M1-M3 as before | still open: G-BM is a working assumption (whether content re-created outside the ledger is 'live' is a maintainer question; its cost at the pin not assessed); premises P-LV (the liveness check sees every row, violated by F-C1351) and P-D9-3 not modelled; P-D9-5 graph-blind replay, the HD-1304 receipt, P-D9b-3 and the unreproduced mixed-revision case (`proofs-d9b/PROOFS.md` section 10); verify()'s table read, its two-read coherence and node identity (F-1401); readers' progress; post-commit property recovery; F-CS01's reviewed design is inte…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-10"></a>
### Proof debt D-10: M1 targeting with 2 pre-enable writes and 2 commits: **paid (mc, exhaustive within bounds)** by `models/core-partition`: 43 pieces by pre-enable world whose union is checked to be 

Severity: Unranked

- core models | — | still open: profiles beyond (2,2) and (0,3); M1's small world (3 ids, 2 graphs, 3 edges); the as-built RPL-B3 check not re-run per piece |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-11"></a>
### Proof debt D-11: Original proof `l2.rs` refinement covers the reviewed design only

Severity: Unranked

- modules 12-14 | original 53 verified, 6 controls rejected (submission 9c3719c1) | by design; product violates it (F-1302, F-1303) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-12"></a>
### Proof debt D-12: Progress-only control for reviewed-design element D-2 (scan bound fixed at marking): **paid at model level**: `control_bound_follows_tail` (the pin's tail-following bound) fails on

Severity: Unranked

- `proofs-d9b/src/progress.rs` | — | the variant needs an attached process to resume to continue; the located failure does not depend on it |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-13"></a>
### Proof debt D-13: The breadth proofs (modules 04 and 11) without premise P-A3: **paid at model level** by `proofs-pa3` (108 verified, 0 errors, `proofs-pa3-baseline`, recheck `proofs-pa3-recheck`): 

Severity: Unranked

- `proofs-pa3/` | — | still open: modules 04 and 11 not composed; one erase at a time; erases inside a caller transaction, EraseNodes/EraseAll, FK rollback and progress under R04-5 not modelled; neither guard exists at the pin |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="D-14"></a>
### Proof debt D-14: Shared mechanism laws proved once over a trait: **paid at model level** by `proofs-mech` (1,149 verified, 0 errors, `--no-cheating`, empty trust inventory; all 45 laws of 13 mechan

Severity: Unranked

- 13 mechanisms, 45 laws | explorer checks (`sem-mc-*`) alongside | composition **paid at model level** by `proofs-sys` (256 verified, 0 errors, `--no-cheating`, empty trust inventory including the proofs-mech dependency, `proofs-sys-baseline`, recheck `proofs-sys-recheck`): the 12 module-00 axiom checks proved once over a design trait whose parameters are the instance choices of M-01, M-02, M-03, M-04, M-05 and M-10 (all 3,072 choice vectors meeting each obligation); 12 located controls, the pin's as-built composition breaking AX-06, AX-07, AX-08, AX-10, AX-11 and AX-11M, each control's broken…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._
