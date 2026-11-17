# Ontology clarification questions

Every starting ID is accounted for in the [146-entry review](audits/register-20261115/question-review.md). 121 policy decisions remain open; nine inherited questions have existing authoritative answers for this pin; two old upstream reports and 14 qualified proof-debt entries are separate. No new human approval was inferred. Current public issue state and disabled Discussions are recorded in [upstream.json](audits/register-20261115/upstream.json).

## Open owner decisions

<a id="erasure.concurrency"></a><!-- question identity -->
<a id="q-004"></a>
### Must erasure and redaction be serialised with each other and with ledger commits?

[Q · erasure.concurrency]

Run: Uplift 2026-11-13

Evidence: `Graph.KG.Eraser` takes no ledger head lock; since 4.6.4 an erase made through an engine on a plain connection nests in the caller's transaction (aad50087), while an engine from `from_connect` runs it on a dedicated connection. `LedgerRedact.LiveRows` reads without locks. Probe [erasure_caller_transaction](receipts/native/erasure_caller_transaction_redaction.json): on a plain connection the erase nests at `$TLEVEL=1`, a concurrent redaction completes, and the caller's rollback restores the content ([bug-002](bugs_issues.md#bug-002)); through `from_connect` the erase [committed on its own](receipts/native/erasure_caller_transaction_from_connect.json) and the caller's rollback did not undo it.

Interpretations: (a) callers must not redact while an erase is uncommitted (document it); (b) redaction must refuse while any erase of the target is uncommitted (take the head lock in the eraser, or a shared target lock); (c) erasure must never join a caller's transaction.

Decision needed: the serialisation contract between erase, redact and commit, and whether erase joins a caller's transaction. Open statement: [erasure.concurrency](#q-004).


Audit: Working assumption (agent, unratified): Require committed erasure before redaction; treat caller transaction membership as unresolved rather than permitting dirty liveness reads. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-004).

Canonical owner: [erasure.concurrency](#q-004).

```g5-question
schema: 1
id: erasure.concurrency
status: open
prompt: Must erasure and redaction be serialised with each other and with ledger commits?
severity: high
multi_select: false
allow_free_text: true
options:
  - label: Require committed erasure before redaction; treat caller transaction membership as unresolved rather than permitting dirty liveness reads.
    description: Default assumption.
  - label: callers must not redact while an erase is uncommitted (document it)
    description: ""
  - label: redaction must refuse while any erase of the target is uncommitted (take the head lock in the eraser, or a shared target lock)
    description: ""
  - label: erasure must never join a caller's transaction
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Require committed erasure before redaction; treat caller transaction membership as unresolved rather than permitting dirty liveness reads.
```

<a id="redaction.idempotency.other-tenant"></a><!-- question identity -->
<a id="q-001"></a>
### Should another tenant's retry of a revision it shared with a redacted tenant be refused?

[Q · redaction.idempotency.other-tenant]

Run: Uplift 2026-11-13

Evidence: spec 256 Decision 2 (Tom, 2026-10-22) clears the metadata of any revision with a redacted record, idempotency key included; the recorded trade-off named only the lost commit message (a140ed78 open question 2). `LedgerRedact.ClearRevision` moves the key to `idemRedacted`; `Ledger.CommitInTxn` then refuses every retry with that key (`idempotency_redacted`). Probe [redaction_mixed_retry](receipts/native/redaction_mixed_retry.json), re-run with byte-identical changesets: tenant B's retry of its own revision replays; its retry of the revision it shared with redacted tenant A is refused with `IdempotencyRedactedError` and changes nothing. The other tenant's `history(correlation_id=...)` lookup also stops finding the revision.

Interpretations: (a) intended — a key names the whole revision, and a refused retry is safer than a replay of a partly tombstoned revision; (b) unintended — only the target's retries should be refused; the other tenant should get a replay (its content is intact) or a distinct error telling it the revision exists but was partly redacted.

Decision needed: which response a non-target tenant's retry gets, and whether its correlation-id lookup should survive. Open statement: [redaction.idempotency.other-tenant](#q-001).


Audit: Working assumption (agent, unratified): Preserve refusal of the whole shared revision key and loss of its correlation lookup until the maintainer specifies a tenant-specific retry result. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-001).

Canonical owner: [redaction.idempotency.other-tenant](#q-001).

```g5-question
schema: 1
id: redaction.idempotency.other-tenant
status: open
prompt: Should another tenant's retry of a revision it shared with a redacted tenant be refused?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Preserve refusal of the whole shared revision key and loss of its correlation lookup until the maintainer specifies a tenant-specific retry result.
    description: Default assumption.
  - label: intended — a key names the whole revision, and a refused retry is safer than a replay of a partly tombstoned revision
    description: ""
  - label: unintended — only the target's retries should be refused; the other tenant should get a replay (its content is intact) or a distinct error telling it the revisi
    description: unintended — only the target's retries should be refused; the other tenant should get a replay (its content is intact) or a distinct error telling it the revision exists but was partly redacted
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve refusal of the whole shared revision key and loss of its correlation lookup until the maintainer specifies a tenant-specific retry result.
```

<a id="redaction.strict-mode"></a><!-- question identity -->
<a id="q-003"></a>
### How should strict mode and the erase-then-redact path fit together?

[Q · redaction.strict-mode]

Run: Uplift 2026-11-13

Evidence: `erase_graph`, `delete_nodes_by_prefix` and `erase_all` call the strict-mode check and raise `LedgerStrictModeError` (nodes_edges.py:1513, :1552; iris_sql_store.py:1433). Redaction refuses a live target, so it needs the erasure first. Erasing through changesets cannot reach named-graph node rows (ledger node operations are default-graph only, 4.6.0 R290). No document or test covers the combination. Model witness `witness_strict_erase_then_redact_needs_strict_off` ([platform model](models/platform/NOTES.md)); probe [platform_strict_redaction](receipts/native/platform_strict_redaction.json): under strict mode the tenant's graph cannot be erased, the ledger leaves its 2 named-graph node rows, and redaction is refused `target_live`; with strict off both run.

Interpretations: (a) strict-mode users turn strict off for the erase, then on again; (b) erasure is exempt from strict mode because it removes content, not history (ADR-0004); (c) erasure should be recorded in the ledger in strict mode.

Decision needed: which path a strict-mode tenant erasure takes, and its documentation. Open statement: [redaction.strict-mode](#q-003).


Audit: Working assumption (agent, unratified): Document the present strict-off erasure sequence as an operational precondition; do not infer that disabling strict mode is the desired product interface. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-003).

Canonical owner: [redaction.strict-mode](#q-003).

```g5-question
schema: 1
id: redaction.strict-mode
status: open
prompt: How should strict mode and the erase-then-redact path fit together?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Document the present strict-off erasure sequence as an operational precondition; do not infer that disabling strict mode is the desired product interface.
    description: Default assumption.
  - label: strict-mode users turn strict off for the erase, then on again
    description: ""
  - label: erasure is exempt from strict mode because it removes content, not history (ADR-0004)
    description: ""
  - label: erasure should be recorded in the ledger in strict mode
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Document the present strict-off erasure sequence as an operational precondition; do not infer that disabling strict mode is the desired product interface.
```

<a id="q-008"></a>
### Should erase-by-prefix and redact-by-prefix use the same prefix rule?

Run: Uplift 2026-11-13

Evidence: `Eraser.EraseNodes` (Eraser.cls:322-350) and `engine.delete_nodes_by_prefix` match a bare starts-with ("acme" erases `acme-health|1` too), while `LedgerRedact.MatchString` always appends the separator ("acme" redacts only `acme|…`). The documented tenant recipe pairs the two (ADR-0013:37; the e2e fixture erases with "tenantA|" and redacts with "tenantA"). An operator who erases with the same bare prefix they redact with also erases a neighbouring tenant's nodes, irreversibly. Found by the fresh-reader reconstruction check (reconstruction-check.md, correction 4).

Interpretations: (a) intended — erase is a general id-prefix tool and the caller must add the separator; document it beside the recipe; (b) the tenant recipe should use one target notion for both steps (a separator-aware erase, or a combined erase-and-redact entry point).

Decision needed: whether erase-by-prefix gains the separator rule (or a tenant entry point), and the documented recipe. Open statement: [erasure.prefix-match](../ontology/features/erasure.g5.md#erasure.prefix-match).


Audit: Working assumption (agent, unratified): Keep generic erase as literal starts-with and use the separator explicitly in the tenant recipe; changing the generic API needs compatibility authority. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-008).

Canonical owner: [erasure.prefix-match](../ontology/features/erasure.g5.md#erasure.prefix-match).

```g5-question
schema: 1
id: q-008
status: open
prompt: Should erase-by-prefix and redact-by-prefix use the same prefix rule?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep generic erase as literal starts-with and use the separator explicitly in the tenant recipe; changing the generic API needs compatibility authority.
    description: Default assumption.
  - label: intended — erase is a general id-prefix tool and the caller must add the separator; document it beside the recipe
    description: ""
  - label: the tenant recipe should use one target notion for both steps (a separator-aware erase, or a combined erase-and-redact entry point)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep generic erase as literal starts-with and use the separator explicitly in the tenant recipe; changing the generic API needs compatibility authority.
```

<a id="redaction.after-erasure.temporal"></a><!-- question identity -->
<a id="q-009"></a>
### Should redaction count a target's temporal-only edges as live content?

[Q · redaction.after-erasure.temporal]

Run: Uplift 2026-11-13

Evidence: ADR-0013 refuses redaction "while any **row** of the target is live", justified by replay; CONTEXT.md says redaction is "Refused while any of the target's **content** is live", and its Erasure definition lists the temporal index as content. A temporal-only predicate (ADR-0015) writes no row and no node. Model witness W2 (`witness_temporal_only_content_is_not_seen`, [prove receipt](results/ledger_redaction/20261114T044401Z-prove/receipt.json)) and probe [redaction_temporal_only_live](receipts/native/redaction_temporal_only_live.json): with only a temporal-only edge in `gT` (0 edge rows, 0 node rows), `redact("gT")` completed and tombstoned the `create_temporal_edge` record while the window reader still returns the edge. Erasure does not settle this for prefix targets: erasing a tenant by prefix leaves its temporal-only events whose endpoints have no node row ([bug-led-007](bugs_issues.md#bug-led-007)).

Interpretations: (a) ADR-0013's "row" governs: temporal entries are not replayed, so tombstoning their records keeps verify equal and is acceptable; (b) the glossary's "content" governs: redaction must refuse until the temporal entries are erased, or the history of a still-readable event is lost.

Decision needed: whether temporal-index entries count for the liveness check (and so whether this is a defect). Open statement: [redaction.after-erasure.temporal](#q-009).


Audit: Working assumption (agent, unratified): Treat temporal entries as live content for the intended safety rule; the existing row-only check remains a documented behavior discrepancy pending scope confirmation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-009).

Canonical owner: [redaction.after-erasure.temporal](#q-009).

```g5-question
schema: 1
id: redaction.after-erasure.temporal
status: open
prompt: Should redaction count a target's temporal-only edges as live content?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat temporal entries as live content for the intended safety rule; the existing row-only check remains a documented behavior discrepancy pending scope confirmation.
    description: Default assumption.
  - label: "ADR-0013's \"row\" governs: temporal entries are not replayed, so tombstoning their records keeps verify equal and is acceptable"
    description: ""
  - label: "the glossary's \"content\" governs: redaction must refuse until the temporal entries are erased, or the history of a still-readable event is lost"
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat temporal entries as live content for the intended safety rule; the existing row-only check remains a documented behavior discrepancy pending scope confirmation.
```

<a id="ledger.commit.post-commit.recorded"></a><!-- question identity -->
<a id="q-010"></a>
### Should post-commit properties be recorded, excluded from verify, or documented as unrecorded writes?

[Q · ledger.commit.post-commit.recorded]

Run: Uplift 2026-11-13

Evidence: spec 218 (CHANGELOG v2.18.x): `post_commit_properties` are applied "via direct SQL (Approach A — no new revision created)"; the docs do not mention verification. Probe [ledger_post_commit_verify](receipts/native/ledger_post_commit_verify.json): one commit with a post-commit property, then `verify()` → `diverges` (`node pcp|1 prop:audit_rev None → x`); `verify(adopt=True)` would record it as an adoption.

Interpretations: (a) intended: the documented audit-trail pattern produces an unrecorded write and verify is right to report it (document it); (b) post-commit properties should be recorded (a second record in the same revision) or excluded by verify.

Decision needed: which, and the documentation of the audit-trail pattern. Open statement: [ledger.commit.post-commit.recorded](#q-010).


Audit: Working assumption (agent, unratified): Treat post-commit properties as unrecorded writes today and keep verify divergence visible; skip-on-replay is a separate already documented idempotency obligation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-010).

Canonical owner: [ledger.commit.post-commit.recorded](#q-010).

```g5-question
schema: 1
id: ledger.commit.post-commit.recorded
status: open
prompt: Should post-commit properties be recorded, excluded from verify, or documented as unrecorded writes?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat post-commit properties as unrecorded writes today and keep verify divergence visible; skip-on-replay is a separate already documented idempotency obligation.
    description: Default assumption.
  - label: "intended: the documented audit-trail pattern produces an unrecorded write and verify is right to report it (document it)"
    description: ""
  - label: post-commit properties should be recorded (a second record in the same revision) or excluded by verify
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat post-commit properties as unrecorded writes today and keep verify divergence visible; skip-on-replay is a separate already documented idempotency obligation.
```

<a id="graph.names.legacy"></a><!-- question identity -->
<a id="q-str-001"></a>
### How should an install that already holds a graph named "0", or one with a control character, find and migrate it?

[Q · graph.names.legacy]

Run: Uplift 2026-11-13

Evidence: ADR-0003:69-70 promises `verify_graph` reports such graphs; none does, and every `ForIndex` caller, the `%BuildIndices` callbacks included, throws on such rows (A-structure Q3). [graph_structure_keys](receipts/native/graph_structure_keys.json) shows new writes of these names are refused (K1, K2).

Interpretations: (a) an upgrade step renames them; (b) `verify_graph` reports them and an operator renames them; (c) they are left and every write to them fails.

Decision needed: the migration path, and whether `verify_graph` must report them as ADR-0003 says. Open statement: [graph.names.legacy](#q-str-001).


Audit: Working assumption (agent, unratified): Preserve refusal of invalid new names and the promised legacy report; require an operator-visible migration plan before claiming old invalid names are supported. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-str-001).

Canonical owner: [graph.names.legacy](#q-str-001).

```g5-question
schema: 1
id: graph.names.legacy
status: open
prompt: How should an install that already holds a graph named "0", or one with a control character, find and migrate it?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Preserve refusal of invalid new names and the promised legacy report; require an operator-visible migration plan before claiming old invalid names are supported.
    description: Default assumption.
  - label: an upgrade step renames them
    description: ""
  - label: "`verify_graph` reports them and an operator renames them"
    description: ""
  - label: they are left and every write to them fails
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve refusal of invalid new names and the promised legacy report; require an operator-visible migration plan before claiming old invalid names are supported.
```

<a id="temporal.write.concurrency"></a><!-- question identity -->
<a id="q-tmp-001"></a>
### Must temporal writes stay exact when several writers touch the same coordinates or triple at once?

[Q · temporal.write.concurrency]

Run: Uplift 2026-11-13

Evidence: spec 254 FR-003 states first-write-wins without condition and spec 255 says the latest index is "kept exact"; ADR-0010 explains why the temporal writers take no locks. The `$Data` collision guard and the writes are not locked (`TemporalIndex.cls:84`): `witness_concurrent_inserts_double_count` ([prove receipt](results/temporal/20261114T001508Z-prove/receipt.json)) shows two inserts at one coordinate counting twice. `NoteLatest` is an unlocked read-compare-set (`TemporalIndex.cls:493-496`), and two first writers into an empty graph each `Kill ^KG("tlast",g)` (`:90-92`), so the latest index can go stale-low while `Resolve` detects only vanished events (`:411-415`). The write/purge race on one triple is a defect against ADR-0009 and is registered separately ([bug-tmp-011](audits/register-20261115/bugs-review.md#bug-tmp-011)). No concurrent test exists; no probe was run (A-temporal F6, F7).

Interpretations: (a) the rules hold for one writer per triple; concurrent writers are the caller's to serialise (document it); (b) the rules are unconditional, so the writers need per-triple locking despite ADR-0010's deadlock concern.

Decision needed: whether first-write-wins, exact statistics and an exact latest index are promised under concurrency. Open statement: [temporal.write.concurrency](#q-tmp-001).


Audit: Working assumption (agent, unratified): Keep first-write-wins and exactness as requirements; concurrent provider behavior is unestablished, not an approved one-writer exemption. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-tmp-001).

Canonical owner: [temporal.write.concurrency](#q-tmp-001).

```g5-question
schema: 1
id: temporal.write.concurrency
status: open
prompt: Must temporal writes stay exact when several writers touch the same coordinates or triple at once?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep first-write-wins and exactness as requirements; concurrent provider behavior is unestablished, not an approved one-writer exemption.
    description: Default assumption.
  - label: the rules hold for one writer per triple; concurrent writers are the caller's to serialise (document it)
    description: ""
  - label: the rules are unconditional, so the writers need per-triple locking despite ADR-0010's deadlock concern
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep first-write-wins and exactness as requirements; concurrent provider behavior is unestablished, not an approved one-writer exemption.
```

<a id="search.quarantine.retention"></a><!-- question identity -->
<a id="q-srch-001"></a>
### Should quarantined vectors and documents survive erasure indefinitely?

[Q · search.quarantine.retention]

Run: Uplift 2026-11-13

Evidence: `embedding_quarantine`, `docs_quarantine` and `edge_vector_quarantine` survive `EraseAll` and graph erasure by decision (FR-039/FR-040 as quoted; the spec is not in `specs/`), and no purge path exists; ADR-0004 says erasure is not a privacy tool, and ADR-0013's redaction does not mention quarantines (A-search Q5).

Interpretations: (a) keep them: they are the only copy of vectors whose graph is unknown; (b) a deployment that must delete data needs a purge path or an erase-all that includes them.

Decision needed: retention, and whether a purge operation exists. Open statement: [search.quarantine.retention](#q-srch-001).


Audit: Working assumption (agent, unratified): Keep quarantined data and explicitly report retention until an owner chooses a purge API and its unknown-graph semantics. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-srch-001).

Canonical owner: [search.quarantine.retention](#q-srch-001).

```g5-question
schema: 1
id: search.quarantine.retention
status: open
prompt: Should quarantined vectors and documents survive erasure indefinitely?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep quarantined data and explicitly report retention until an owner chooses a purge API and its unknown-graph semantics.
    description: Default assumption.
  - label: "keep them: they are the only copy of vectors whose graph is unknown"
    description: ""
  - label: a deployment that must delete data needs a purge path or an erase-all that includes them
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep quarantined data and explicitly report retention until an owner chooses a purge API and its unknown-graph semantics.
```

<a id="q-plt-001"></a>
### Is strict mode promised from the moment set_strict returns, or within a few seconds for other engines?

Run: Uplift 2026-11-13

Evidence: `witness_ttl_window_admits_a_write_after_set_strict` ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json)); probe [platform_strict_ttl](receipts/native/platform_strict_ttl.json): a second engine that had probed before wrote `ttl-bypass` unrecorded 0.002 s after `set_strict(True)` returned, and was refused after the TTL; the calling engine was refused at once (the USER_GUIDE example). The guard caches `Meta()` per engine for 5 s (`ledger/guard.py:20, 38-59`), and `set_strict` refreshes only the calling engine's guard (`client.py:281-309`). Probe [platform_strict_paths](receipts/native/platform_strict_paths.json) confirms the guarded paths refuse once the cache is fresh.

Interpretations: (a) strict is promised from the moment `set_strict` returns, so the window is a defect; (b) strict is enforced within 5 s per process, as the guard docstring implies, and needs documenting.

Decision needed: the promise, and with (a) whether to fix it in the guard or by [simp-plt-001](design_simplification.md#simp-plt-001). Open statement: [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict).


Audit: Working assumption (agent, unratified): Record immediate enforcement in the calling engine and a five-second cache elsewhere; the time promised to other engines still needs a decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-001).

Canonical owner: [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict).

```g5-question
schema: 1
id: q-plt-001
status: open
prompt: Is strict mode promised from the moment set_strict returns, or within a few seconds for other engines?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Record immediate enforcement in the calling engine and a five-second cache elsewhere; the time promised to other engines still needs a decision.
    description: Default assumption.
  - label: strict is promised from the moment `set_strict` returns, so the window is a defect
    description: ""
  - label: strict is enforced within 5 s per process, as the guard docstring implies, and needs documenting
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Record immediate enforcement in the calling engine and a five-second cache elsewhere; the time promised to other engines still needs a decision.
```

<a id="install.schema.concurrency.leftover"></a><!-- question identity -->
<a id="q-plt-002"></a>
### Can an explicitly named schema be recorded over another schema's interrupted first setup?

[Q · install.schema.concurrency.leftover]

Run: Uplift 2026-11-13

Evidence: `witness_interrupted_setup_then_explicit_schema` (W-S3, [prove receipt](results/platform/20261114T002651Z-prove/receipt.json)) holds even with serial setups. After an interrupted setup on S (marker present, no record; KNOWN_ISSUES:787-807), an engine with an explicit T sees `held={S}` and records T as "explicit" (`_engine/schema.py:2229-2239, 2312`); `^KG`, `^NKG` and `^IVG.Ledger` hold S's data, and `kg_built` is already marked, so setup does not rebuild `^KG` from T's rows (`:2356-2361, 2673-2678`). FR-009's explicit path was designed for 4.5.x namespaces (A-platform F-S3). The concurrent-setup case is [bug-plt-003](audits/register-20261115/bugs-review.md#bug-plt-003).

Interpretations: (a) refuse the explicit path while another schema holds this release's marker (the premise the model's proof uses); (b) accept it and clear or rebuild the namespace's globals.

Scope (review round 3 R3-reader H3): that an explicit name is recorded while IVG's tables sit in one other schema at all is the FR-009 divergence [bug-plt-026](audits/register-20261115/bugs-review.md#bug-plt-026); this question is narrowed to the globals an unfinished setup of the current release leaves behind.

Iteration 56 (continuation, fresh namespace I56SB): observed end to end. `I56X` fully set up, its record removed (this release's marker function present, no record): a default engine's dry run and setup are refused naming `I56X`; an engine with `schema_prefix="I56Y"` (or `IVG_SCHEMA_PREFIX=I56Y`) plans `explicit` with `other_schemas` `I56X`, and its setup records `I56Y` and creates 18 tables; `I56X`'s engine is refused from then on ([install_lifecycle](models/install_lifecycle/NOTES.md) binding `B:y_explicit_setup`, `B:record_after_explicit`, `B:x_call_after_explicit`; [bug-plt-026](bugs_issues.md#bug-plt-026) now E2E reproduced). The globals (`^KG`, `^NKG`) after it were not read.

Decision needed: which. Open statement: [install.schema.concurrency.leftover](#q-plt-002).


Audit: Working assumption (agent, unratified): Prefer refusing a conflicting unfinished setup; accepting it needs an explicit plan for the old globals and rebuild markers. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-002).

Canonical owner: [install.schema.concurrency.leftover](#q-plt-002).

```g5-question
schema: 1
id: install.schema.concurrency.leftover
status: open
prompt: Can an explicitly named schema be recorded over another schema's interrupted first setup?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Prefer refusing a conflicting unfinished setup; accepting it needs an explicit plan for the old globals and rebuild markers.
    description: Default assumption.
  - label: refuse the explicit path while another schema holds this release's marker (the premise the model's proof uses)
    description: ""
  - label: accept it and clear or rebuild the namespace's globals
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer refusing a conflicting unfinished setup; accepting it needs an explicit plan for the old globals and rebuild markers.
```

<a id="access.defaults.exposure"></a><!-- question identity -->
<a id="q-plt-003"></a>
### Should the server refuse to start on a reachable address with no key and a superuser login?

[Q · access.defaults.exposure]

Run: Uplift 2026-11-13

Evidence: with no key, the HTTP server and Bolt bind `0.0.0.0` and connect as `_SYSTEM`/`SYS`, a `%All` superuser, exposing `/admin/load`, Cypher writes and `DELETE /admin/queries/{pid}` → `KillProcess` on any PID, with no warning in `cypher_api` or the CLI (A-platform F-H5); only the sample API warns about the default login. The environment-name mismatch that makes this silent is [bug-plt-009](bugs_issues.md#bug-plt-009).

Interpretations: (a) refuse to start on a non-loopback host without a key (or with a superuser login); (b) warn loudly and document; (c) keep as is, the operator guide being the control.

Decision needed: which. Open statement: [access.defaults.exposure](#q-plt-003).


Audit: Working assumption (agent, unratified): Treat the documented open bind and credentials as current behavior only; safer defaults need a maintainer policy decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-003).

Canonical owner: [access.defaults.exposure](#q-plt-003).

```g5-question
schema: 1
id: access.defaults.exposure
status: open
prompt: Should the server refuse to start on a reachable address with no key and a superuser login?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat the documented open bind and credentials as current behavior only; safer defaults need a maintainer policy decision.
    description: Default assumption.
  - label: refuse to start on a non-loopback host without a key (or with a superuser login)
    description: ""
  - label: warn loudly and document
    description: ""
  - label: keep as is, the operator guide being the control
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat the documented open bind and credentials as current behavior only; safer defaults need a maintainer policy decision.
```

<a id="install.snapshot.ledger"></a><!-- question identity -->
<a id="q-plt-004"></a>
### What should a restore do when the namespace already has a live ledger?

[Q · install.snapshot.ledger]

Run: Uplift 2026-11-13

Also recorded as: HD-1801 (playbook decision: what should a restore do to the live ledger; [decisions/18.md](../../experiment/playbook-uplift/decisions/18.md), intent [HD-1801](../../experiment/playbook-completion/intent/HD-1801.md)); the matching finding is F-1801 in the bugs register. (crosswalk)

Evidence: `erase_all` keeps `^IVG.Ledger("rec")`, the head and the meta (`Eraser.cls:810-812`), and the replacing restore's global import only sets values (`_engine/snapshot.py:1654-1692`), so the archive's ledger entries are written over the live ones without removing the live revisions (A-platform F-B3; A-ops candidate finding). Restoring an earlier archive also brings back content a later redaction removed ([q-led-002](#q-led-002)).

Interpretations: (a) refuse while a ledger is live; (b) replace the live ledger wholesale; (c) keep the live ledger and skip the archive's.

Decision needed: which. Open statement: [install.snapshot.ledger](#q-plt-004).


Audit: Working assumption (agent, unratified): Prefer refusal while a live ledger exists until replace/merge history semantics are specified; do not count the current overlay as a decided contract. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-004).

Canonical owner: [install.snapshot.ledger](#q-plt-004).

```g5-question
schema: 1
id: install.snapshot.ledger
status: open
prompt: What should a restore do when the namespace already has a live ledger?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Prefer refusal while a live ledger exists until replace/merge history semantics are specified; do not count the current overlay as a decided contract.
    description: Default assumption.
  - label: refuse while a ledger is live
    description: ""
  - label: replace the live ledger wholesale
    description: ""
  - label: keep the live ledger and skip the archive's
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer refusal while a live ledger exists until replace/merge history semantics are specified; do not count the current overlay as a decided contract.
```

<a id="install.bulk_load.limits"></a><!-- question identity -->
<a id="q-plt-005"></a>
### Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?

[Q · install.bulk_load.limits]

Run: Uplift 2026-11-13

Evidence: BulkLoader bypasses the ledger and strict mode does not refuse it (documented exempt); its `PurgeIndex` → `RemoveAll` empties every graph's adjacency mid-load with no rebuild lock (`Adjacency.cls:452-473, 814-823`); its in-memory `(s,p,o)` dedupe gives a multigraph graph no parallel edges; two loaders can insert duplicates under `%NOCHECK` (A-platform F-B7; reconstruction check 2(a)6, G7, G34).

Interpretations: (a) yes to all three, and the loader documents it; (b) the loader must preserve other graphs' adjacency and multigraph semantics.

Decision needed: the loader's contract. Open statement: [install.bulk_load.limits](#q-plt-005).


Audit: Working assumption (agent, unratified): Keep documented loader exemptions and chunking; preserve other graphs and multigraph data unless a narrower supported envelope is expressly adopted. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-005).

Canonical owner: [install.bulk_load.limits](#q-plt-005).

```g5-question
schema: 1
id: install.bulk_load.limits
status: open
prompt: Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep documented loader exemptions and chunking; preserve other graphs and multigraph data unless a narrower supported envelope is expressly adopted.
    description: Default assumption.
  - label: 6, G7, G34)
    description: ""
  - label: yes to all three, and the loader documents it
    description: ""
  - label: the loader must preserve other graphs' adjacency and multigraph semantics
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep documented loader exemptions and chunking; preserve other graphs and multigraph data unless a narrower supported envelope is expressly adopted.
```

<a id="erasure.atomic.caller-transaction"></a><!-- question identity -->
<a id="q-plt-006"></a>
### Should whether a write joins the caller's transaction depend on how the engine was opened?

[Q · erasure.atomic.caller-transaction]

Run: Uplift 2026-11-13

Evidence: `engine._iris_obj()` opens a separate connection whenever the engine knows its credentials (`from_connect`) and reuses the caller's process otherwise (`engine.py:1894-1943`); tests patch it back to the caller's connection. On that transport `erase_graph`/`erase_all` [committed on their own](receipts/native/erasure_caller_transaction_from_connect.json), while on a plain connection the erase [nests](receipts/native/erasure_caller_transaction_redaction.json) ([q-004](#q-004), [bug-002](bugs_issues.md#bug-002)). The same split applies to ledger commits without a caller transaction, `redact`/`enable`/`disable`/`set_strict`, FHIR graph calls, `set_multigraph`, the vector index calls and `sync()`, and to the non-indexed adjacency writes ([bug-str-015](audits/register-20261115/bugs-review.md#bug-str-015)) (A-ops method notes and (e)2; reconstruction check 2(a)1).

Interpretations: (a) intended: these calls are independent of the caller's transaction, and the docs list them; (b) every write should run on the caller's connection and nest; (c) calls that cannot nest should refuse an open caller transaction.

Decision needed: the transaction membership of each listed call, independent of how the engine was built. Open statement: [structure.write.engine-connection](#structure.write.engine-connection).


Audit: Working assumption (agent, unratified): Record each transport-dependent transaction boundary; prefer an explicit consistent join-or-refuse contract before changing it. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-006).

Canonical owner: [erasure.atomic.caller-transaction](#q-plt-006).

```g5-question
schema: 1
id: erasure.atomic.caller-transaction
status: open
prompt: Should whether a write joins the caller's transaction depend on how the engine was opened?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Record each transport-dependent transaction boundary; prefer an explicit consistent join-or-refuse contract before changing it.
    description: Default assumption.
  - label: 1)
    description: ""
  - label: "intended: these calls are independent of the caller's transaction, and the docs list them"
    description: ""
  - label: every write should run on the caller's connection and nest
    description: ""
  - label: calls that cannot nest should refuse an open caller transaction
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Record each transport-dependent transaction boundary; prefer an explicit consistent join-or-refuse contract before changing it.
```

<a id="algorithms.routing.named_graphs"></a><!-- question identity -->
<a id="q-plt-007"></a>
### Can a default-graph algorithm call use a native reader once a named graph holds edges?

[Q · algorithms.routing.named_graphs]

Run: Uplift 2026-11-13

Evidence: `ArnoAccel.cls:255-256` says the readers read the `^NKG` export, which merges every graph; CONTEXT.md:267 says they read the adjacency index directly; `TraversalBuild.cls:758-760`. The native routes for PageRank, WCC, CDLP and subgraph have no `_named_graph_with_edges()` guard, unlike the R184 tiers (`iris_sql_store.py:3234, 3691, 3749`) (A-platform F-A3).

Interpretations: (a) the readers read one graph and the route is safe; (b) they read the merged snapshot, so default-graph PageRank counts named-graph edges and needs the guard.

Decision needed: a live check of what the 1.2.1 reader reads, and the routing rule. Open statement: [algorithms.routing.named_graphs](#q-plt-007).


Audit: Working assumption (agent, unratified): Require a proven graph-specific reader before relying on native default-graph results; an unavailable Arno provider does not settle its behavior. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-007).

Canonical owner: [algorithms.routing.named_graphs](#q-plt-007).

```g5-question
schema: 1
id: algorithms.routing.named_graphs
status: open
prompt: Can a default-graph algorithm call use a native reader once a named graph holds edges?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Require a proven graph-specific reader before relying on native default-graph results; an unavailable Arno provider does not settle its behavior.
    description: Default assumption.
  - label: the readers read one graph and the route is safe
    description: ""
  - label: they read the merged snapshot, so default-graph PageRank counts named-graph edges and needs the guard
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Require a proven graph-specific reader before relying on native default-graph results; an unavailable Arno provider does not settle its behavior.
```

<a id="access.ledger_strict.undecided"></a><!-- question identity -->
<a id="q-plt-008"></a>
### Which write paths must strict mode govern beyond the engine's methods, and how is each classified?

[Q · access.ledger_strict.undecided]

Run: Uplift 2026-11-13

Evidence: `theorem_strict_paths` and `witness_undecided_paths_write_under_strict` ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json)): under strict mode the undecided paths' writes commit; marking any of them exempt or covered makes the witness fail (review R3-platform R1-11). Per the sources: embedding, vector-index and BM25 writes are outside the ledger by decision (ADR-0006; spec 213 governs structural writes); BulkLoader and raw SQL, MCP `RunSQL` included (ADMIN_GUIDE §3), are documented exemptions; `bulk_delete_adjacency` and the sample API's Cypher, GraphQL and example mutations are undocumented bypasses ([bug-plt-006](bugs_issues.md#bug-plt-006), [bug-plt-005](bugs_issues.md#bug-plt-005)); no source decides FHIR sync (`_engine/fhir_graph.py:255-258`, no ledger call in `FHIRGraph.cls`), MCP `CypherQuery` (`MCPTools.cls:9-29`), `set_multigraph`, `Prop_Set`, the `Txn_*` procedures, or the migrations (`upgrade_to_4_0_0`, the temporal backfill), which rewrite tables and globals with no strict check. The guard's own gaps are the 5 s TTL ([q-plt-001](#q-plt-001)), fail-open ([q-plt-009](#q-plt-009)) and the lifetime-cached `_class_present` ([bug-plt-025](bugs_issues.md#bug-plt-025)). A Cypher write cannot reach the variable-length route before `_ledger_check` (transactional plans carry no `var_length_paths`; R3-platform A5). Sources: A-platform F-B8, F-H7; B-platform Q5.

Interpretations: for each undecided path, (a) exempt like BulkLoader and raw SQL, listed in the docs; (b) refused under strict mode.

Decision needed: the classification of each undecided path. Open statements: [access.ledger_strict.undecided](#q-plt-008), [fhir.ledger](#HD-1501).


Audit: Working assumption (agent, unratified): Preserve explicit BulkLoader/raw-SQL/vector exemptions and list undecided FHIR/server paths individually; do not infer exemption from a missing guard. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-008).

Canonical owner: [access.ledger_strict.undecided](#q-plt-008).

```g5-question
schema: 1
id: access.ledger_strict.undecided
status: open
prompt: Which write paths must strict mode govern beyond the engine's methods, and how is each classified?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Preserve explicit BulkLoader/raw-SQL/vector exemptions and list undecided FHIR/server paths individually; do not infer exemption from a missing guard.
    description: Default assumption.
  - label: exempt like BulkLoader and raw SQL, listed in the docs
    description: ""
  - label: refused under strict mode
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve explicit BulkLoader/raw-SQL/vector exemptions and list undecided FHIR/server paths individually; do not infer exemption from a missing guard.
```

<a id="query.graph-scope.bound-create"></a><!-- question identity -->
<a id="q-cyp-001"></a>
### When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it?

[Q · query.graph-scope.bound-create]

Run: Uplift 2026-11-13

Evidence: the decision says "`CREATE` writes the default graph" (CONTEXT l. 46-48); the edge insert uses `''` with the bound pair's IDs (`translator.py:10351-10365`); the foreign key `(graph_id, s/o_id) → nodes` (`schema.py:42-43`) refuses it when the default graph lacks those IDs, and when it has nodes of the same IDs the relationship connects those nodes, not the bound ones. The e2e matrix has no such case (`test_460_all_graphs_writes_e2e.py:133-147`) (A-cypher F5).

Interpretations: (a) the decision is literal; the error is intended and should name the cause; (b) Cypher's binding wins and the relationship is created in the bound nodes' graph, as `SET`/`DELETE` already do.

Decision needed: which, and the error text under (a). Open statement: [query.graph-scope.bound-create](#q-cyp-001).


Audit: Working assumption (agent, unratified): Prefer the bound endpoints graph, with ambiguity refused; the actual default-write rule remains a behavior fact pending intent confirmation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-cyp-001).

Canonical owner: [query.graph-scope.bound-create](#q-cyp-001).

```g5-question
schema: 1
id: query.graph-scope.bound-create
status: open
prompt: When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Prefer the bound endpoints graph, with ambiguity refused; the actual default-write rule remains a behavior fact pending intent confirmation.
    description: Default assumption.
  - label: the decision is literal; the error is intended and should name the cause
    description: ""
  - label: Cypher's binding wins and the relationship is created in the bound nodes' graph, as `SET`/`DELETE` already do
    description: ""
  - label: "Open statement: [query.graph-scope.bound-create](#q-cyp-001)"
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer the bound endpoints graph, with ambiguity refused; the actual default-write rule remains a behavior fact pending intent confirmation.
```

<a id="ledger.commit.kind"></a><!-- question identity -->
<a id="q-led-005"></a>
### Should callers be able to choose a commit's kind?

[Q · ledger.commit.kind]

Run: Uplift 2026-11-13

Evidence: `commit(changeset, kind=...)` is public (`client.py:381`); a kind other than `"changeset"` skips the empty and size checks, and `"adoption"` applies through `LedgerGenesis.Adopt` (`Ledger.cls:488-509`), so a caller can forge an adoption revision that records changes the tables never had, or label a changeset `redaction` or `genesis` in the history (reconstruction check 2(b)9, correction 9; review R1-core CV-6 and R1-6).

Interpretations: (a) make `kind` internal (only verify needs adoption); (b) keep it public and document the skipped checks and the audit meaning of each kind.

Decision needed: which. Open statement: [ledger.commit.kind](#q-led-005).


Audit: Working assumption (agent, unratified): Treat kind as caller data today while reserving system meaning in analysis; any restricted vocabulary needs an explicit compatibility decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-led-005).

Canonical owner: [ledger.commit.kind](#q-led-005).

```g5-question
schema: 1
id: ledger.commit.kind
status: open
prompt: Should callers be able to choose a commit's kind?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat kind as caller data today while reserving system meaning in analysis; any restricted vocabulary needs an explicit compatibility decision.
    description: Default assumption.
  - label: 9, correction 9; review R1-core CV-6 and R1-6)
    description: ""
  - label: make `kind` internal (only verify needs adoption)
    description: ""
  - label: keep it public and document the skipped checks and the audit meaning of each kind
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat kind as caller data today while reserving system meaning in analysis; any restricted vocabulary needs an explicit compatibility decision.
```

<a id="access.retries"></a><!-- question identity -->
<a id="q-plt-019"></a>
### May the server or the client retry a call that writes?

[Q · access.retries]

Run: Uplift 2026-11-13

Evidence: no document states a retry policy. The HTTP server reruns a failed Cypher call once on a fresh engine, and the SDK's `_post` retries server errors and timeouts ([bug-plt-019](audits/register-20261115/bugs-review.md#bug-plt-019)), so a write can be applied twice; only a ledger commit with an idempotency key is protected. Open statement: [access.retries](#q-plt-019).

Interpretations: (a) retries are allowed only for reads and for idempotency-keyed commits; (b) retries stay, and writes must be made idempotent; (c) no automatic retries.

Decision needed: the retry policy for writes.


Audit: Working assumption (agent, unratified): Keep ambiguous write outcomes distinct from known pre-write failure; automatic resend of non-idempotent writes is not presumed safe. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-019).

Canonical owner: [access.retries](#q-plt-019).

```g5-question
schema: 1
id: access.retries
status: open
prompt: May the server or the client retry a call that writes?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep ambiguous write outcomes distinct from known pre-write failure; automatic resend of non-idempotent writes is not presumed safe.
    description: Default assumption.
  - label: retries are allowed only for reads and for idempotency-keyed commits
    description: ""
  - label: retries stay, and writes must be made idempotent
    description: ""
  - label: no automatic retries
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep ambiguous write outcomes distinct from known pre-write failure; automatic resend of non-idempotent writes is not presumed safe.
```

<a id="access.health.recovery-policy"></a><!-- question identity -->
<a id="q-iter-006"></a>
### Should the sample API retry construction after a startup outage?

[Q · access.health.recovery-policy]

Run: Improvement iteration 7, 2026-11-15

Evidence: api.main captures no engine when automatic startup fails, so later health requests remain unavailable even if construction could now succeed. cypher_api leaves failed construction uncached and retries. Actual in-process ASGI neighbors and [health model](models/service_health/NOTES.md) derive these distinct histories; no external database recovery was tested and no auto-recovery requirement established.

Working answer: recreate the sample app as built. Alternative: retry construction and consistently replace captured GraphQL/query/health ownership. Canonical owner: [recovery policy](#q-iter-006). Decision needed: operator recreation versus automatic recovery contract; no owner decision inferred.


Audit: Working assumption (agent, unratified): Keep current failure visibility after startup outage; retry/rebuild needs a lifecycle policy with bounded attempts and readiness semantics. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-006).

Canonical owner: [access.health.recovery-policy](#q-iter-006).

```g5-question
schema: 1
id: access.health.recovery-policy
status: open
prompt: Should the sample API retry construction after a startup outage?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep current failure visibility after startup outage; retry/rebuild needs a lifecycle policy with bounded attempts and readiness semantics.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep current failure visibility after startup outage; retry/rebuild needs a lifecycle policy with bounded attempts and readiness semantics.
```

<a id="query.system-procedures.alias-policy"></a><!-- question identity -->
<a id="q-iter-004"></a>
### Should standalone handled metadata calls expose YIELD aliases as result columns?

[Q · query.system-procedures.alias-policy]

Run: Improvement iteration 7, 2026-11-15

Evidence: real persisted A/B labels through db.labels and public execute_cypher give column label for YIELD label AS l, but column l with RETURN l. Bare ORDER BY l refuses; RETURN l ORDER BY l succeeds. [Native empty/nonempty neighbors](../uplift/consolidated/iteration-7/procedure-native.json), [qualified model](models/procedure_results/NOTES.md). No specific contrary metadata-only requirement was established, so this is not counted as a new bug.

Working answer: document physical columns until a maintainer decides. Alternative: project standalone YIELD aliases consistently, preserving explicit RETURN and existing supported filters. Canonical owner: [alias policy](#q-iter-004). Decision needed: compatibility versus uniform result names; no human decision inferred.


Audit: Working assumption (agent, unratified): Prefer declared YIELD aliases at the public reader, while documenting current handled-call names until the owner decides. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-004).

Canonical owner: [query.system-procedures.alias-policy](#q-iter-004).

```g5-question
schema: 1
id: query.system-procedures.alias-policy
status: open
prompt: Should standalone handled metadata calls expose YIELD aliases as result columns?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Prefer declared YIELD aliases at the public reader, while documenting current handled-call names until the owner decides.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer declared YIELD aliases at the public reader, while documenting current handled-call names until the owner decides.
```

<a id="query.system-procedures.empty-validation"></a><!-- question identity -->
<a id="q-iter-005"></a>
### Should handled WHERE validation happen when no rows exist?

[Q · query.system-procedures.empty-validation]

Run: Improvement iteration 7, 2026-11-15

Evidence: unsupported STARTS WITH and missing parameter both refuse with label data but return an empty projected result when the producer is empty. Structural MATCH still refuses on empty data. Actual Python/SQLite and [native cases](../uplift/consolidated/iteration-7/procedure-native.json) agree; [model](models/procedure_results/NOTES.md) distinguishes these branches. This exception to a broad refusal description does not establish an intended validation policy.

Working answer: document row evaluation as built. Alternative: validate supported expression forms and supplied parameters before evaluating rows, so invalid queries have stable outcomes independent of data. Canonical owner: [empty validation](#q-iter-005). Decision needed: eager validation requirement and compatibility; no owner approval inferred.


Audit: Working assumption (agent, unratified): Prefer validating a requested WHERE independent of row count; current empty-provider acceptance does not settle intent. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-005).

Canonical owner: [query.system-procedures.empty-validation](#q-iter-005).

```g5-question
schema: 1
id: query.system-procedures.empty-validation
status: open
prompt: Should handled WHERE validation happen when no rows exist?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Prefer validating a requested WHERE independent of row count; current empty-provider acceptance does not settle intent.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer validating a requested WHERE independent of row count; current empty-provider acceptance does not settle intent.
```

<a id="ledger.readers.history.text-policy"></a><!-- question identity -->
<a id="q-iter-003"></a>
### Should history text filters use binary identity or the current database comparison?

[Q · ledger.readers.history.text-policy]

Run: Improvement iteration 6, 2026-11-15

Evidence: the Python API calls a correlation filter exact, but persisted fields use ordinary IRIS String columns. Actual native commits/history match ASCII case changes and trailing spaces or tabs, including in raw source JSON; interior JSON spacing still differs. Evidence and raw rows: [native comparison](../uplift/consolidated/iteration-6/history-collation-native.json), [spaces](../uplift/consolidated/iteration-6/history-collation-spaces-native.json), [interior source spacing](../uplift/consolidated/iteration-6/history-collation-interior-native.json). The as-built history_paging model represents both comparison modes; no human policy was inferred.

Working answer: document current matching until a maintainer decides, preserving existing queries. Alternative: use binary identity for some or all metadata fields so distinct correlation IDs/source text do not compare equal; that can change existing queries.

Decision needed: which comparison is intended for actor/type/correlation/source fields, and whether any change needs a compatibility path. Canonical owner: [history text policy](#q-iter-003).


Audit: Working assumption (agent, unratified): Preserve current database comparison for compatibility and expose the difference from binary Python identity; a portable text rule needs owner choice. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-003).

Canonical owner: [ledger.readers.history.text-policy](#q-iter-003).

```g5-question
schema: 1
id: ledger.readers.history.text-policy
status: open
prompt: Should history text filters use binary identity or the current database comparison?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Preserve current database comparison for compatibility and expose the difference from binary Python identity; a portable text rule needs owner choice.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve current database comparison for compatibility and expose the difference from binary Python identity; a portable text rule needs owner choice.
```

<a id="fhir.sql_mapping.graph_scope"></a><!-- question identity -->
<a id="q-plt-018"></a>
### Which graph do rows of a mapped FHIR SQL table belong to?

[Q · fhir.sql_mapping.graph_scope]

Run: Uplift 2026-11-13

Evidence: mapped SQL tables carry no graph column, so a Cypher query under `USE GRAPH` or across every graph reads the same mapped rows (`cypher/translator.py`; `_engine/fhir.py`). No spec or ADR states the scope; not run natively (FHIR suites skipped on this instance). Open statement: [fhir.sql_mapping.graph_scope](#q-plt-018).

Interpretations: (a) mapped rows belong to every graph (today's behaviour, documented); (b) a mapping is made per graph and only that graph's queries read it.

Decision needed: the graph scope of mapped rows.


Audit: Working assumption (agent, unratified): Treat mapped SQL labels as namespace-global today; assigning every row to a graph needs mapping metadata and migration policy. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-018).

Canonical owner: [fhir.sql_mapping.graph_scope](#q-plt-018).

```g5-question
schema: 1
id: fhir.sql_mapping.graph_scope
status: open
prompt: Which graph do rows of a mapped FHIR SQL table belong to?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Treat mapped SQL labels as namespace-global today; assigning every row to a graph needs mapping metadata and migration policy.
    description: Default assumption.
  - label: mapped rows belong to every graph (today's behaviour, documented)
    description: ""
  - label: a mapping is made per graph and only that graph's queries read it
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat mapped SQL labels as namespace-global today; assigning every row to a graph needs mapping metadata and migration policy.
```

<a id="search.fusion.text_leg"></a><!-- question identity -->
<a id="q-srch-006"></a>
### Should every fusion entry point use the same text ranking?

[Q · search.fusion.text_leg]

Run: Uplift 2026-11-13

Evidence: the engine and Cypher fusions read a BM25 index built from node properties (`_engine/vector.py:1382-1451`), while the SQL `kg_RRF_FUSE` procedure ranks the documents table by full-text term counts (`schema.py:2484-2560`); the 4.0.0 migration guide calls the documents table the BM25 corpus (`docs/migration/v4.0.0.md:742-751`). Open statement: [search.fusion.text_leg](#q-srch-006).

Interpretations: (a) one shared contract for every entry point; (b) two contracts, each documented, with the migration guide corrected.

Decision needed: whether the SQL fusion should read the BM25 index.


Audit: Working assumption (agent, unratified): Preserve each current text corpus and rank rule until one common corpus is chosen; common fusion arithmetic alone cannot settle text ranking. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-srch-006).

Canonical owner: [search.fusion.text_leg](#q-srch-006).

```g5-question
schema: 1
id: search.fusion.text_leg
status: open
prompt: Should every fusion entry point use the same text ranking?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Preserve each current text corpus and rank rule until one common corpus is chosen; common fusion arithmetic alone cannot settle text ranking.
    description: Default assumption.
  - label: one shared contract for every entry point
    description: ""
  - label: two contracts, each documented, with the migration guide corrected
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve each current text corpus and rank rule until one common corpus is chosen; common fusion arithmetic alone cannot settle text ranking.
```

<a id="q-002"></a>
### Which ledger readers must refuse while a redaction is unfinished?

Run: Uplift 2026-11-13

Evidence: spec 256 plan "Readers" lists `get_revision`, `diff`, `reconstruct`, `export_reconstruction` (refuse) and `verify()` (`redaction_in_progress`). Probe [redaction_readers_midrun](receipts/native/redaction_readers_midrun.json): `get_revision`, `diff`, `reconstruct`, `export_reconstruction` refused; `verify` answered `redaction_in_progress`; `history`, `stats` and the SQL `ledger_records` procedure answered. `history()`, `stats()` and the SQL procedure `ledger_records` answer mid-run with some revisions' metadata already cleared and others not. The refusing readers check the marker once and then page through SQL, so a batch can commit between pages.

Interpretations: (a) only replay-style readers need protection; metadata listings may show a half-done redaction; (b) every record or metadata reader should refuse or read one consistent snapshot.

Decision needed: the reader list, and whether a reader must see one moment of the ledger. Open statement: [redaction.batches.readers](../ontology/features/redaction.g5.md#redaction.batches.readers).


Audit: Working assumption (agent, unratified): Keep the explicit redaction guards and list unguarded readers; do not infer that partial-redaction answers are acceptable. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-002).

Canonical owner: [redaction.batches.readers](../ontology/features/redaction.g5.md#redaction.batches.readers).

```g5-question
schema: 1
id: q-002
status: open
prompt: Which ledger readers must refuse while a redaction is unfinished?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep the explicit redaction guards and list unguarded readers; do not infer that partial-redaction answers are acceptable.
    description: Default assumption.
  - label: only replay-style readers need protection; metadata listings may show a half-done redaction
    description: ""
  - label: every record or metadata reader should refuse or read one consistent snapshot
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep the explicit redaction guards and list unguarded readers; do not infer that partial-redaction answers are acceptable.
```

<a id="q-005"></a>
### Is an unsalted SHA-256 of a tenant name and of each record acceptable in the redacted history?

Run: Uplift 2026-11-13

Evidence: ADR-0013 keeps `sha256(CanonicalRecord)` per tombstone and `sha256(graph NUL match)` in the redaction revision's source and the marker; a salted digest was rejected "for now" (ADR-0013:43, 49). Canonical records contain the entity id, attribute and values; a guessed tenant name or a low-entropy value (a boolean, a known name) can be confirmed by hashing the guess.

Interpretations: (a) acceptable — the digest is an audit device and the content is already low-sensitivity; (b) unacceptable for regulated erasure — use a keyed digest held outside the namespace.

Decision needed: whether confirmability of guessed content is within the redaction guarantee. Open statement: [redaction.tombstone.digest](../ontology/features/redaction.g5.md#redaction.tombstone.digest).


Audit: Working assumption (agent, unratified): Record the unsalted digest as built and keep its privacy adequacy open; no guessing or confirmability experiment is in scope. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-005).

Canonical owner: [redaction.tombstone.digest](../ontology/features/redaction.g5.md#redaction.tombstone.digest).

```g5-question
schema: 1
id: q-005
status: open
prompt: Is an unsalted SHA-256 of a tenant name and of each record acceptable in the redacted history?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Record the unsalted digest as built and keep its privacy adequacy open; no guessing or confirmability experiment is in scope.
    description: Default assumption.
  - label: acceptable — the digest is an audit device and the content is already low-sensitivity
    description: ""
  - label: unacceptable for regulated erasure — use a keyed digest held outside the namespace
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Record the unsalted digest as built and keep its privacy adequacy open; no guessing or confirmability experiment is in scope.
```

<a id="redaction.batches.abort"></a><!-- question identity -->
<a id="q-006"></a>
### How does an operator end a redaction that cannot finish?

[Q · redaction.batches.abort]

Run: Uplift 2026-11-13

Evidence: once a run has tombstoned anything, the marker stays until that target's run completes. If the target becomes live again, a resumed call is refused at entry (`target_live`, observed in [redaction_interrupt_resume](receipts/native/redaction_interrupt_resume.json) step 4), and if it becomes live between the last batch and the final step, the final step refuses (`theorem_completion`; observed natively in the race context: in [redaction_concurrent_targets](receipts/native/redaction_concurrent_targets.json) tenant A's run ended with the final step's message "the default graph (ids starting 'tA|') became live again"; the serial case is unobserved; review round2-core R2-5). Meanwhile record readers, verify, commits into the target and every other target's redaction are refused until the content is erased again and the same target is run to completion. There is no abort.

Interpretations: (a) intended — the only safe exit is to finish; (b) an abort that restores nothing (tombstones stay) but releases the marker is wanted for a target that is legitimately back in use.

Decision needed: whether an abort exists and what it guarantees. Open statement: [redaction.batches.abort](#q-006).


Audit: Working assumption (agent, unratified): Assume completion by rerun after fixing liveness; abandonment needs an owner-approved recovery meaning for partial tombstones. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-006).

Canonical owner: [redaction.batches.abort](#q-006).

```g5-question
schema: 1
id: redaction.batches.abort
status: open
prompt: How does an operator end a redaction that cannot finish?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Assume completion by rerun after fixing liveness; abandonment needs an owner-approved recovery meaning for partial tombstones.
    description: Default assumption.
  - label: intended — the only safe exit is to finish
    description: ""
  - label: an abort that restores nothing (tombstones stay) but releases the marker is wanted for a target that is legitimately back in use
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Assume completion by rerun after fixing liveness; abandonment needs an owner-approved recovery meaning for partial tombstones.
```

<a id="q-007"></a>
### What does erasure's returned count promise?

Run: Uplift 2026-11-13

Evidence: CONTEXT.md and ADR-0004 say "a returned 0 means nothing matched". `EraseGraph` returns the number of `nodes` and `rdf_edges` rows removed; labels, properties, documents, vectors, temporal entries, FHIR rows and ledger statements can be removed while it returns 0.

Interpretations: (a) the count means node and edge rows only, and the doc should say so; (b) 0 must mean no store changed.

Decision needed: the documented meaning. Open statement: [erasure.count](../ontology/features/erasure.g5.md#erasure.count).


Audit: Working assumption (agent, unratified): Treat the present count as a sum of store effects rather than a count of distinct entities; any stronger public count needs a defined unit. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-007).

Canonical owner: [erasure.count](../ontology/features/erasure.g5.md#erasure.count).

```g5-question
schema: 1
id: q-007
status: open
prompt: What does erasure's returned count promise?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Treat the present count as a sum of store effects rather than a count of distinct entities; any stronger public count needs a defined unit.
    description: Default assumption.
  - label: the count means node and edge rows only, and the doc should say so
    description: ""
  - label: 0 must mean no store changed
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat the present count as a sum of store effects rather than a count of distinct entities; any stronger public count needs a defined unit.
```

<a id="q-str-002"></a>
### Which control characters must a graph name refuse, and who owns the rule?

Run: Uplift 2026-11-13

Evidence: Python's `validate_graph_name` refuses 0–31 and 127 (`_validate.py:47`); IRIS's `$ZStrip(...,"*C")` also covers 128–159. `witness_python_mirror_admits_c1_control` ([prove receipt](results/graph_structure/20261114T000451Z-prove/receipt.json)); [graph_structure_keys](receipts/native/graph_structure_keys.json): IRIS refuses 0x01, 0x1F, 0x7F, 0x80, 0x85 and 0x9F and accepts 0xA0 (`p_ctrl`), and in K3 a name with U+0085 passed Python and was refused inside IRIS as SQLCODE -400 "Fatal error occurred", nothing written (A-structure Q4; B-structure O1; review R2-data R1-14).

Interpretations: (a) GraphKey owns the rule and Python asks it (or mirrors it exactly), so the refusal is a clean validation error; (b) keep both, accepting the opaque server error for C1 characters.

Decision needed: one definition and its owner. Open statement: [graph.names](../ontology/concepts/graph-scope.g5.md#graph.names).


Audit: Working assumption (agent, unratified): Prefer the server GraphKey rule for all new names; control-character normalization versus refusal must be documented consistently. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-str-002).

Canonical owner: [graph.names](../ontology/concepts/graph-scope.g5.md#graph.names).

```g5-question
schema: 1
id: q-str-002
status: open
prompt: Which control characters must a graph name refuse, and who owns the rule?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer the server GraphKey rule for all new names; control-character normalization versus refusal must be documented consistently.
    description: Default assumption.
  - label: GraphKey owns the rule and Python asks it (or mirrors it exactly), so the refusal is a clean validation error
    description: ""
  - label: keep both, accepting the opaque server error for C1 characters
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer the server GraphKey rule for all new names; control-character normalization versus refusal must be documented consistently.
```

<a id="structure.multigraph.create_edge"></a><!-- question identity -->
<a id="q-str-003"></a>
### In a multigraph, must create_edge always add a new edge and offer a variant that returns its ID?

[Q · structure.multigraph.create_edge]

Run: Uplift 2026-11-13

Evidence: spec 234 FR-007 says yes to both; the code returns False for an existing triple, `create_edge_returning_id` does not exist, CHANGELOG and API docs are silent, and KNOWN_ISSUES steers users to Cypher (A-structure Q2; R2-data E6).

Interpretations: (a) FR-007 stands and this is unfinished work; (b) drop FR-007 and document Cypher as the way to add parallel edges.

Decision needed: which. Open statement: [structure.multigraph.create_edge](#q-str-003).


Audit: Working assumption (agent, unratified): Keep direct create as deduplicating at this pin; the specification planned keyed parallel creation, whose public ID-returning interface is unfinished. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-str-003).

Canonical owner: [structure.multigraph.create_edge](#q-str-003).

```g5-question
schema: 1
id: structure.multigraph.create_edge
status: open
prompt: In a multigraph, must create_edge always add a new edge and offer a variant that returns its ID?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep direct create as deduplicating at this pin; the specification planned keyed parallel creation, whose public ID-returning interface is unfinished.
    description: Default assumption.
  - label: FR-007 stands and this is unfinished work
    description: ""
  - label: drop FR-007 and document Cypher as the way to add parallel edges
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep direct create as deduplicating at this pin; the specification planned keyed parallel creation, whose public ID-returning interface is unfinished.
```

<a id="structure.multigraph.ledger"></a><!-- question identity -->
<a id="q-str-004"></a>
### Until a ledger reference can name one parallel edge, should the ledger refuse relationship operations on a multigraph triple?

[Q · structure.multigraph.ledger]

Run: Uplift 2026-11-13

Evidence: spec 234 lists the ledger (US4) as not done and FR-013 requires an ambiguous tuple reference to fail; `LedgerApply.FindEdge` takes the first matching row with no ambiguity check (`LedgerApply.cls:144-157, 185-198`), and the delete then breaks the survivors' adjacency ([bug-str-001](bugs_issues.md#bug-str-001)) (B-structure open question; R2-data E6).

Interpretations: (a) refuse with `ambiguous_tuple` until FR-013 lands; (b) apply to the first row, as today, once the adjacency defect is fixed.

Decision needed: which. Open statement: [structure.multigraph.ledger](#q-str-004).


Audit: Working assumption (agent, unratified): Keep the spec requirement to refuse ambiguous ledger references; do not accept first-row selection as intended parallel-edge semantics. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-str-004).

Canonical owner: [structure.multigraph.ledger](#q-str-004).

```g5-question
schema: 1
id: structure.multigraph.ledger
status: open
prompt: Until a ledger reference can name one parallel edge, should the ledger refuse relationship operations on a multigraph triple?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep the spec requirement to refuse ambiguous ledger references; do not accept first-row selection as intended parallel-edge semantics.
    description: Default assumption.
  - label: refuse with `ambiguous_tuple` until FR-013 lands
    description: ""
  - label: apply to the first row, as today, once the adjacency defect is fixed
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep the spec requirement to refuse ambiguous ledger references; do not accept first-row selection as intended parallel-edge semantics.
```

<a id="temporal.stats.cut-bucket"></a><!-- question identity -->
<a id="q-tmp-002"></a>
### After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?

[Q · temporal.stats.cut-bucket]

Run: Uplift 2026-11-13

Evidence: ADR-0009:49 says statistics "describe the past" after a purge, while `DeleteTemporalEdge` and `EraseNodes` rebuild a bucket from its survivors (`TemporalIndex.cls:446-488`); after `purge_raw_before(tsEnd)` with `tsEnd` mid-bucket, deleting a surviving edge wipes the purged edges from `tagg` but not from `bucket` (A-temporal Q2).

Interpretations: (a) the purge rule wins: a cut bucket keeps its history; (b) the rebuild rule wins: statistics describe the survivors.

Decision needed: which rule, and the matching code change. Open statement: [temporal.stats.cut-bucket](#q-tmp-002).


Audit: Working assumption (agent, unratified): Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-tmp-002).

Canonical owner: [temporal.stats.cut-bucket](#q-tmp-002).

Iteration 51 evidence (additive): the same rebuild also undoes a bucket-range purge. After `purge_bucket_range(b, b)`, deleting one edge of b recreates b's aggregates from its surviving edges (whole-bucket count 2, sum 13) while its event counter stays removed (velocity 0), so aggregates and velocity disagree about b ([temporal_stats](models/temporal_stats/NOTES.md) `theorem_delete_after_bucket_purge_recreates`, control `delete-skips-missing-statistics`; [binding](results/temporal_stats/20261117T040000Z-binding/receipt.json) `agg_qb_*`, `vel_qb_299`). After a raw purge, a rewrite then delete in the cut bucket drops the purged history from the aggregates (count 0) while the counter keeps it (velocity 3) (`agg_pb_*`, `vel_pb_299`). Either answer to this question should also say what a delete does after a bucket-range purge. Owner: [temporal.stats.after-purge](../ontology/features/temporal.g5.md#temporal.stats.after-purge).

```g5-question
schema: 1
id: temporal.stats.cut-bucket
status: open
prompt: After a raw purge cuts a bucket, should a later delete in that bucket keep the purged history in its statistics?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.
    description: Default assumption.
  - label: "the purge rule wins: a cut bucket keeps its history"
    description: ""
  - label: "the rebuild rule wins: statistics describe the survivors"
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.
```

<a id="temporal.window.concurrent-writes"></a><!-- question identity -->
<a id="q-tmp-003"></a>
### Must a paged temporal window read show one consistent moment while edges are written?

[Q · temporal.window.concurrent-writes]

Run: Uplift 2026-11-13

Evidence: the window reader pages over live globals, so an edge inserted behind the cursor is missed and pages can mix states; spec 255 addresses only purged events (A-temporal Q5).

Interpretations: (a) a live, non-snapshot read is acceptable (document it); (b) a snapshot bound is wanted.

Decision needed: which. Open statement: [temporal.window.concurrent-writes](#q-tmp-003).


Audit: Working assumption (agent, unratified): Treat a paged read as multiple observations today; a point-in-time promise needs an explicit snapshot/version protocol. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-tmp-003).

Canonical owner: [temporal.window.concurrent-writes](#q-tmp-003).

```g5-question
schema: 1
id: temporal.window.concurrent-writes
status: open
prompt: Must a paged temporal window read show one consistent moment while edges are written?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Treat a paged read as multiple observations today; a point-in-time promise needs an explicit snapshot/version protocol.
    description: Default assumption.
  - label: a live, non-snapshot read is acceptable (document it)
    description: ""
  - label: a snapshot bound is wanted
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat a paged read as multiple observations today; a point-in-time promise needs an explicit snapshot/version protocol.
```

<a id="temporal.ledger.insert-collision"></a><!-- question identity -->
<a id="q-tmp-004"></a>
### What should an insert collision inside a changeset do?

[Q · temporal.ledger.insert-collision]

Run: Uplift 2026-11-13

Evidence: since spec 254 `InsertEdge` answers 1 for a collision, and `OpCreateTemporalEdge` records `create_temporal_edge` unconditionally (`LedgerApply.cls:635-639`), so a revision claims a temporal edge that changed nothing; the changeset docstring still says "insert (fail if key exists)" (`changeset.py:334-335`) (A-temporal F5).

Interpretations: (a) refuse the changeset, as the docstring says; (b) commit and record nothing for the collided op; (c) keep the record and document that it may describe no change.

Decision needed: which. Open statement: [temporal.ledger.insert-collision](#q-tmp-004).


Audit: Working assumption (agent, unratified): Keep insert collision as an effect-free accepted temporal call today; ledger record/no-op policy still needs owner choice. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-tmp-004).

Canonical owner: [temporal.ledger.insert-collision](#q-tmp-004).

```g5-question
schema: 1
id: temporal.ledger.insert-collision
status: open
prompt: What should an insert collision inside a changeset do?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep insert collision as an effect-free accepted temporal call today; ledger record/no-op policy still needs owner choice.
    description: Default assumption.
  - label: refuse the changeset, as the docstring says
    description: ""
  - label: commit and record nothing for the collided op
    description: ""
  - label: keep the record and document that it may describe no change
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep insert collision as an effect-free accepted temporal call today; ledger record/no-op policy still needs owner choice.
```

<a id="q-tmp-005"></a>
### Should deleting the last timestamp of a temporal-only predicate keep its old structural row, as a purge does?

Run: Uplift 2026-11-13

Evidence: `witness_delete_and_purge_disagree_when_opted_out` ([prove receipt](results/temporal/20261114T001508Z-prove/receipt.json)); [temporal_marked_row_lifecycle](receipts/native/temporal_marked_row_lifecycle.json) K4: with the predicate registered temporal-only, deleting the last timestamp retracts the old marked row (`DeleteTemporalEdge` does not read the registry, `TemporalIndex.cls:333-341`), while a purge keeps it until the drop (`:966`; ADR-0015:144-148). Both keep the row rule (A-temporal Q4; B-temporal O3).

Interpretations: (a) the asymmetry is acceptable; (b) delete should follow the purge's "leave registered predicates' rows" rule.

Decision needed: which. Open statement: [temporal.optout.drop](../ontology/features/temporal.g5.md#temporal.optout.drop).


Audit: Working assumption (agent, unratified): Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-tmp-005).

Canonical owner: [temporal.optout.drop](../ontology/features/temporal.g5.md#temporal.optout.drop).

```g5-question
schema: 1
id: q-tmp-005
status: open
prompt: Should deleting the last timestamp of a temporal-only predicate keep its old structural row, as a purge does?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately.
    description: Default assumption.
  - label: the asymmetry is acceptable
    description: ""
  - label: delete should follow the purge's "leave registered predicates' rows" rule
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately.
```

<a id="temporal.structural.explicit-delete"></a><!-- question identity -->
<a id="q-tmp-006"></a>
### May an explicit delete_edge remove a marked structural row while its triple still has timestamps?

[Q · temporal.structural.explicit-delete]

Run: Uplift 2026-11-13

Evidence: the temporal model's `DeleteEdge` lets an explicit `delete_edge` remove a marked row while timestamps remain, and no source decides the case; ADR-0009 makes a structural predicate's timestamp imply its row (review R2-data R1-7).

Interpretations: (a) an explicit delete wins and the triple stays without a row until its next temporal write; (b) the delete keeps (or re-asserts) the marked row while timestamps remain; (c) the delete is refused.

Decision needed: which. Open statement: [temporal.structural.explicit-delete](#q-tmp-006).


Audit: Working assumption (agent, unratified): Preserve the temporal implication requirement and record the direct-delete exception; the maintainer must decide whether to refuse or repair it. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-tmp-006).

Canonical owner: [temporal.structural.explicit-delete](#q-tmp-006).

```g5-question
schema: 1
id: temporal.structural.explicit-delete
status: open
prompt: May an explicit delete_edge remove a marked structural row while its triple still has timestamps?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Preserve the temporal implication requirement and record the direct-delete exception; the maintainer must decide whether to refuse or repair it.
    description: Default assumption.
  - label: an explicit delete wins and the triple stays without a row until its next temporal write
    description: ""
  - label: the delete keeps (or re-asserts) the marked row while timestamps remain
    description: ""
  - label: the delete is refused
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve the temporal implication requirement and record the direct-delete exception; the maintainer must decide whether to refuse or repair it.
```

<a id="search.embedding.undeclared_default"></a><!-- question identity -->
<a id="q-srch-002"></a>
### May an undeclared writer add vectors to the default graph's table after a model has claimed it?

[Q · search.embedding.undeclared_default]

Run: Uplift 2026-11-13

Evidence: `witness_undeclared_default_vs_named` ([prove receipt](results/search/20261114T000543Z-prove/receipt.json)): an undeclared writer is width-checked only and lands in model A's `kg_NodeEmbeddings` on the default graph, while on a named graph it gets its own route; `embedding_identity.py:85-91` and FR-010 (as quoted in code) say yes; CONTEXT.md says writes at another model are "refused rather than mixed in", a phrase added on 2026-11-04 (`267aaff1`, R039), after 4.0.0 routing, which favours refusal (A-search Q1; review R3-platform R1-9).

Interpretations: (a) allowed at the same width (as built); (b) refused, as for a declared different model.

Decision needed: which. Open statement: [search.embedding.undeclared_default](#q-srch-002).


Audit: Working assumption (agent, unratified): Keep width-compatible undeclared writes to the claimed default table as current compatibility; separate-route enforcement needs an explicit decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-srch-002).

Canonical owner: [search.embedding.undeclared_default](#q-srch-002).

```g5-question
schema: 1
id: search.embedding.undeclared_default
status: open
prompt: May an undeclared writer add vectors to the default graph's table after a model has claimed it?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep width-compatible undeclared writes to the claimed default table as current compatibility; separate-route enforcement needs an explicit decision.
    description: Default assumption.
  - label: allowed at the same width (as built)
    description: ""
  - label: refused, as for a declared different model
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep width-compatible undeclared writes to the claimed default table as current compatibility; separate-route enforcement needs an explicit decision.
```

<a id="search.bm25.read_isolation"></a><!-- question identity -->
<a id="q-srch-003"></a>
### May a BM25 search observe an index write that is still in progress?

[Q · search.bm25.read_isolation]

Run: Uplift 2026-11-13

Evidence: searches read `^BM25Idx` with no lock and no isolation (spec 044 FR-019 "Search takes no lock"), so they can read uncommitted or mixed N/df/len; FR-023 guarantees snapshot-like reads only during an upgrade; a search during a Build answers `[]` (A-search Q4; B-search "Not represented").

Interpretations: (a) acceptable: scores are approximate during writes; (b) searches must see committed state only.

Decision needed: which. Open statement: [search.bm25.read_isolation](#q-srch-003).


Audit: Working assumption (agent, unratified): Assume no cross-call consistency guarantee until a read/write protocol is chosen; partial-index results remain visible risk, not approved isolation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-srch-003).

Canonical owner: [search.bm25.read_isolation](#q-srch-003).

```g5-question
schema: 1
id: search.bm25.read_isolation
status: open
prompt: May a BM25 search observe an index write that is still in progress?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Assume no cross-call consistency guarantee until a read/write protocol is chosen; partial-index results remain visible risk, not approved isolation.
    description: Default assumption.
  - label: "acceptable: scores are approximate during writes"
    description: ""
  - label: searches must see committed state only
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Assume no cross-call consistency guarantee until a read/write protocol is chosen; partial-index results remain visible risk, not approved isolation.
```

<a id="search.bm25.default_index"></a><!-- question identity -->
<a id="q-srch-004"></a>
### Should plain text search use a BM25 index named "default" when one exists?

[Q · search.bm25.default_index]

Run: Uplift 2026-11-13

Evidence: spec 044 FR-012 / US5 (still "Draft") says `kg_TXT` uses `^BM25Idx("default")` when present; `kg_TXT` uses iFind/LIKE over `docs` (`vector.py:917-1054`) (A-search Q3).

Interpretations: (a) the requirement is superseded; mark the spec; (b) it is unfinished work.

Decision needed: which. Open statement: [search.bm25.default_index](#q-srch-004).


Audit: Working assumption (agent, unratified): Keep explicit BM25 selection distinct from plain text search; a default-index fallback requires a supported API/corpus decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-srch-004).

Canonical owner: [search.bm25.default_index](#q-srch-004).

```g5-question
schema: 1
id: search.bm25.default_index
status: open
prompt: Should plain text search use a BM25 index named "default" when one exists?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep explicit BM25 selection distinct from plain text search; a default-index fallback requires a supported API/corpus decision.
    description: Default assumption.
  - label: the requirement is superseded; mark the spec
    description: ""
  - label: it is unfinished work
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep explicit BM25 selection distinct from plain text search; a default-index fallback requires a supported API/corpus decision.
```

<a id="q-srch-005"></a>
### In which order must the common-term cutoff list the terms it skipped?

Run: Uplift 2026-11-13

Evidence: FR-044-C4 says "alphabetical"; the code returns ObjectScript collation order, in which numeric terms sort first (A-search Q6). The rest of the cutoff contract was proved (`theorem_cutoff_contract`, [prove receipt](results/search/20261114T000543Z-prove/receipt.json)) and observed as specified ([search_bm25_cutoff](receipts/native/search_bm25_cutoff.json)).

Interpretations: (a) collation order is what "alphabetical" means here (document it); (b) plain string order.

Decision needed: which. Open statement: [search.bm25.cutoff](../ontology/features/search.g5.md#search.bm25.cutoff).


Audit: Working assumption (agent, unratified): Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-srch-005).

Canonical owner: [search.bm25.cutoff](../ontology/features/search.g5.md#search.bm25.cutoff).

```g5-question
schema: 1
id: q-srch-005
status: open
prompt: In which order must the common-term cutoff list the terms it skipped?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact.
    description: Default assumption.
  - label: collation order is what "alphabetical" means here (document it)
    description: ""
  - label: plain string order
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact.
```

<a id="ledger.strict.fail-open"></a><!-- question identity -->
<a id="q-plt-009"></a>
### When the strict-mode guard cannot read the ledger's state, should it allow the write?

[Q · ledger.strict.fail-open]

Run: Uplift 2026-11-13

Evidence: a failed `Meta()` probe caches "never-enabled", so the guard fails open (`ledger/guard.py:55-58`; `witness_failed_probe_admits_a_write`, [prove receipt](results/platform/20261114T002651Z-prove/receipt.json)) (B-platform Q3). The related lifetime cache of the class check is decided and registered as [bug-plt-025](bugs_issues.md#bug-plt-025).

Interpretations: (a) fail open, as documented in the code; (b) refuse under uncertainty when strict may be on, and re-probe the class.

Decision needed: which. Open statement: [ledger.strict.fail-open](#q-plt-009).


Audit: Working assumption (agent, unratified): Keep failures visible in analysis and prefer fail-closed admission; the current fail-open compatibility behavior is not owner ratification. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-009).

Canonical owner: [ledger.strict.fail-open](#q-plt-009).

```g5-question
schema: 1
id: ledger.strict.fail-open
status: open
prompt: When the strict-mode guard cannot read the ledger's state, should it allow the write?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep failures visible in analysis and prefer fail-closed admission; the current fail-open compatibility behavior is not owner ratification.
    description: Default assumption.
  - label: fail open, as documented in the code
    description: ""
  - label: refuse under uncertainty when strict may be on, and re-probe the class
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep failures visible in analysis and prefer fail-closed admission; the current fail-open compatibility behavior is not owner ratification.
```

<a id="install.setup.failed_deploy"></a><!-- question identity -->
<a id="q-plt-010"></a>
### Should setup still record the schema when some classes failed to deploy?

[Q · install.setup.failed_deploy]

Run: Uplift 2026-11-13

Evidence: the deploy is best-effort (`_engine/schema.py:2578-2595`) and the record is written regardless (`:2309-2312`); the next engine is accepted and its writes fail with `GraphWriteError` (KNOWN_ISSUES:787-807 describes a similar symptom); on a non-default schema, earlier classes compiled for `Graph_KG` keep naming it (A-platform F-S5).

Interpretations: (a) record anyway and report the failure; (b) withhold the record so the namespace counts as a stopped setup (FR-006a).

Decision needed: which. Open statement: [install.setup.failed_deploy](#q-plt-010).


Audit: Working assumption (agent, unratified): Prefer no ready schema record after failed deployment; a partial-ready record would need explicit per-capability admission rules. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-010).

Canonical owner: [install.setup.failed_deploy](#q-plt-010).

```g5-question
schema: 1
id: install.setup.failed_deploy
status: open
prompt: Should setup still record the schema when some classes failed to deploy?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer no ready schema record after failed deployment; a partial-ready record would need explicit per-capability admission rules.
    description: Default assumption.
  - label: record anyway and report the failure
    description: ""
  - label: withhold the record so the namespace counts as a stopped setup (FR-006a)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer no ready schema record after failed deployment; a partial-ready record would need explicit per-capability admission rules.
```

<a id="install.migration.schema.unrecorded"></a><!-- question identity -->
<a id="q-plt-011"></a>
### May a data migration run before any setup has recorded the namespace's IVG Schema, and on which schema?

[Q · install.migration.schema.unrecorded]

Run: Uplift 2026-11-13

Evidence: the migrations build their engine from `IVG_SCHEMA_PREFIX` or the default and waive the schema check (`engine.py:1887-1890`, whose comment justifies only "may run before any 4.6.0 setup recorded the schema"); with a record that names another schema the waiver is a defect ([bug-plt-007](bugs_issues.md#bug-plt-007)). With no record, FR-006a's letter conflicts with the 4.0.0 upgrade's documented order. The 4.0.0 migrations take `schema=` only for the placements; the embeddings and `^KG` steps use the engine's environment or default schema (`upgrade.py:145-152, 259-268`), and none consult `^IVG.Deploy("schema")` (A-platform F-S12; review R3-platform R1-5).

Interpretations: (a) with no record, a migration may run on an explicitly given schema and must not record it; (b) a migration must refuse until a setup records the schema.

Decision needed: the no-record rule. Open statement: [install.migration.schema.unrecorded](#q-plt-011).


Audit: Working assumption (agent, unratified): Require an explicit schema choice before a migration with no namespace record; arbitrary fallback schemas are not an inferred supported policy. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-011).

Canonical owner: [install.migration.schema.unrecorded](#q-plt-011).

```g5-question
schema: 1
id: install.migration.schema.unrecorded
status: open
prompt: May a data migration run before any setup has recorded the namespace's IVG Schema, and on which schema?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Require an explicit schema choice before a migration with no namespace record; arbitrary fallback schemas are not an inferred supported policy.
    description: Default assumption.
  - label: with no record, a migration may run on an explicitly given schema and must not record it
    description: ""
  - label: a migration must refuse until a setup records the schema
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Require an explicit schema choice before a migration with no namespace record; arbitrary fallback schemas are not an inferred supported policy.
```

<a id="access.read_only.scope"></a><!-- question identity -->
<a id="q-plt-012"></a>
### Does read-only mode govern the MCP tools, and should Bolt honour a driver's read access mode?

[Q · access.read_only.scope]

Run: Uplift 2026-11-13

Evidence: MCP `CypherQuery` writes and `RunSQL` runs anything (`MCPTools.cls:9-69`), with no read-only control (A-platform F-H7); Bolt ignores the access mode (reconstruction check 2(a)13).

Interpretations: (a) a read-only IRIS login is the real control and the docs say so; (b) `IVG_READ_ONLY` must cover MCP, and Bolt must refuse writes in a read session.

Decision needed: which. Open statement: [access.read_only.scope](#q-plt-012).


Audit: Working assumption (agent, unratified): Keep engine read-only guarantees and explicitly list interfaces that ignore access hints; protocol hints and server enforcement need separate decisions. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-012).

Canonical owner: [access.read_only.scope](#q-plt-012).

```g5-question
schema: 1
id: access.read_only.scope
status: open
prompt: Does read-only mode govern the MCP tools, and should Bolt honour a driver's read access mode?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep engine read-only guarantees and explicitly list interfaces that ignore access hints; protocol hints and server enforcement need separate decisions.
    description: Default assumption.
  - label: 13)
    description: ""
  - label: a read-only IRIS login is the real control and the docs say so
    description: ""
  - label: "`IVG_READ_ONLY` must cover MCP, and Bolt must refuse writes in a read session"
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep engine read-only guarantees and explicitly list interfaces that ignore access hints; protocol hints and server enforcement need separate decisions.
```

<a id="algorithms.proof.build"></a><!-- question identity -->
<a id="q-plt-013"></a>
### Does a proven reader revision hold for every build and platform of the library?

[Q · algorithms.proof.build]

Run: Uplift 2026-11-13

Evidence: routing ignores the library build and platform (FR-004), while the proof record holds one arm64 build (A-platform F-A6).

Interpretations: (a) the revision is the contract across builds; (b) routing must also match the proven build.

Decision needed: which. Open statement: [algorithms.proof.build](#q-plt-013).


Audit: Working assumption (agent, unratified): Bind proof evidence to exact library/platform builds until source or owner authority permits broader reuse. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-013).

Canonical owner: [algorithms.proof.build](#q-plt-013).

```g5-question
schema: 1
id: algorithms.proof.build
status: open
prompt: Does a proven reader revision hold for every build and platform of the library?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Bind proof evidence to exact library/platform builds until source or owner authority permits broader reuse.
    description: Default assumption.
  - label: the revision is the contract across builds
    description: ""
  - label: routing must also match the proven build
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Bind proof evidence to exact library/platform builds until source or owner authority permits broader reuse.
```

<a id="algorithms.proof.ungated"></a><!-- question identity -->
<a id="q-plt-014"></a>
### Must the evidence gate also cover the other algorithms the native library speeds up?

[Q · algorithms.proof.ungated]

Run: Uplift 2026-11-13

Evidence: triangle count, SCC, k-core and Leiden use the library through `arno_bridge` with no proof gate and fall back only on a library error (`iris_sql_store.py:3737-3760, 3977-4000`) (A-platform F-A7).

Interpretations: (a) yes, gate them; (b) they are outside the gate by design (document it).

Decision needed: which. Open statement: [algorithms.proof.ungated](#q-plt-014).


Audit: Working assumption (agent, unratified): Do not infer proof coverage for accelerated algorithms absent from the gate; extending its inventory needs provider-specific evidence. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-014).

Canonical owner: [algorithms.proof.ungated](#q-plt-014).

```g5-question
schema: 1
id: algorithms.proof.ungated
status: open
prompt: Must the evidence gate also cover the other algorithms the native library speeds up?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Do not infer proof coverage for accelerated algorithms absent from the gate; extending its inventory needs provider-specific evidence.
    description: Default assumption.
  - label: yes, gate them
    description: ""
  - label: they are outside the gate by design (document it)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Do not infer proof coverage for accelerated algorithms absent from the gate; extending its inventory needs provider-specific evidence.
```

<a id="algorithms.routing.namespace"></a><!-- question identity -->
<a id="q-plt-015"></a>
### Should native readers work in namespaces other than USER?

[Q · algorithms.routing.namespace]

Run: Uplift 2026-11-13

Evidence: native readers run only in `USER`, while ADR-0016 makes any namespace the isolation unit, so a non-USER install never gets native routing (A-platform F-A9; spec 236 open question).

Interpretations: (a) USER only, documented; (b) the library must read the calling namespace.

Decision needed: which. Open statement: [algorithms.routing.namespace](#q-plt-015).


Audit: Working assumption (agent, unratified): Keep non-USER Owner routing as current availability; cross-namespace native support requires a provider deployment/proof contract. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-015).

Canonical owner: [algorithms.routing.namespace](#q-plt-015).

```g5-question
schema: 1
id: algorithms.routing.namespace
status: open
prompt: Should native readers work in namespaces other than USER?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep non-USER Owner routing as current availability; cross-namespace native support requires a provider deployment/proof contract.
    description: Default assumption.
  - label: USER only, documented
    description: ""
  - label: the library must read the calling namespace
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep non-USER Owner routing as current availability; cross-namespace native support requires a provider deployment/proof contract.
```

<a id="fhir.event.retry"></a><!-- question identity -->
<a id="q-plt-016"></a>
### Must a repeated FHIR event leave the graph unchanged?

[Q · fhir.event.retry]

Run: Uplift 2026-11-13

Evidence: `/fhir-event` stamps an event without `date` with the current time, so a repeat writes again; an updated resource's codes never refresh and there is no delete; the governing spec 195 is not in the repository, and the route is due for removal in 5.0 (A-platform F-B9).

Interpretations: (a) derive the time from the event so retries are harmless; (b) accept it until the route is removed.

Decision needed: which. Open statement: [fhir.event.retry](#q-plt-016).


Audit: Working assumption (agent, unratified): Prefer idempotent repeated FHIR events, while preserving current event behavior as observation; event identity and replay retention need owner choice. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-016).

Canonical owner: [fhir.event.retry](#q-plt-016).

```g5-question
schema: 1
id: fhir.event.retry
status: open
prompt: Must a repeated FHIR event leave the graph unchanged?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer idempotent repeated FHIR events, while preserving current event behavior as observation; event identity and replay retention need owner choice.
    description: Default assumption.
  - label: derive the time from the event so retries are harmless
    description: ""
  - label: accept it until the route is removed
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer idempotent repeated FHIR events, while preserving current event behavior as observation; event identity and replay retention need owner choice.
```

<a id="fhir.sync.other_writers"></a><!-- question identity -->
<a id="q-plt-017"></a>
### What should happen when other writers, an erase included, touch a FHIR graph during a sync?

[Q · fhir.sync.other_writers]

Run: Uplift 2026-11-13

Evidence: `erase_graph` does not take `^IVG.FHIRGraph(graph)`, so it can race a full re-derive (A-platform F-B10); no source says whether other writers may touch a FHIR graph.

Interpretations: (a) the FHIR graph belongs to the sync alone and other writes are refused; (b) other writes, an erase included, take the sync's lock.

Decision needed: which. Open statement: [fhir.sync.other_writers](#q-plt-017).


Audit: Working assumption (agent, unratified): Preserve the documented single-sync restriction and keep competing non-sync writers unestablished; choose serialization or conflict detection explicitly. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-plt-017).

Canonical owner: [fhir.sync.other_writers](#q-plt-017).

```g5-question
schema: 1
id: fhir.sync.other_writers
status: open
prompt: What should happen when other writers, an erase included, touch a FHIR graph during a sync?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Preserve the documented single-sync restriction and keep competing non-sync writers unestablished; choose serialization or conflict detection explicitly.
    description: Default assumption.
  - label: the FHIR graph belongs to the sync alone and other writes are refused
    description: ""
  - label: other writes, an erase included, take the sync's lock
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve the documented single-sync restriction and keep competing non-sync writers unestablished; choose serialization or conflict detection explicitly.
```

<a id="query.shadow.native-failure"></a><!-- question identity -->
<a id="q-cyp-002"></a>
### In shadow mode, should a native failure be raised instead of answered by SQL?

[Q · query.shadow.native-failure]

Run: Uplift 2026-11-13

Evidence: FR-007 (fallback) and FR-006 (raise on a difference) both hold; in shadow mode a native exception is still answered by SQL with one warning (`query.py:2144-2152`), so a native defect that raises is invisible to a shadow run, TCK shadow runs included; shadow mode never compares compiled with interpreted (only `test_257_compiled_plans_e2e.py` does) (A-cypher F11).

Interpretations: (a) raise in shadow mode (stricter checks); (b) keep the fallback, as specified.

Decision needed: which. Open statement: [query.shadow.native-failure](#q-cyp-002).


Audit: Working assumption (agent, unratified): Keep SQL fallback as the current shadow behavior; fail-fast diagnostic mode remains an unratified alternative. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-cyp-002).

Canonical owner: [query.shadow.native-failure](#q-cyp-002).

```g5-question
schema: 1
id: query.shadow.native-failure
status: open
prompt: In shadow mode, should a native failure be raised instead of answered by SQL?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep SQL fallback as the current shadow behavior; fail-fast diagnostic mode remains an unratified alternative.
    description: Default assumption.
  - label: raise in shadow mode (stricter checks)
    description: ""
  - label: keep the fallback, as specified
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep SQL fallback as the current shadow behavior; fail-fast diagnostic mode remains an unratified alternative.
```

<a id="query.native.index-current"></a><!-- question identity -->
<a id="q-cyp-003"></a>
### Should a bulk load by another process close the native query path while indexes lag the rows?

[Q · query.native.index-current]

Run: Uplift 2026-11-13

Evidence: the native gate (FR-014) is per engine (`native_plan.py:530`); `BulkLoader` writes `%NOINDEX %NOCHECK`, commits per batch and rebuilds `^KG` at the end (`bulk_loader.py:1-12, 157-163`), so other engines' native reads see `^KG` and `pkprops` behind the rows; spec 253 research §H names the trap (A-cypher F7).

Interpretations: (a) no: equal answers assume current indexes (document it); (b) a load publishes a namespace-wide marker that `native_gate` checks.

Decision needed: which. Open statement: [query.native.index-current](#q-cyp-003).


Audit: Working assumption (agent, unratified): Prefer closing native admission during index-bypassing load; a cache/probe that misses that interval cannot justify current-index reliance. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-cyp-003).

Canonical owner: [query.native.index-current](#q-cyp-003).

```g5-question
schema: 1
id: query.native.index-current
status: open
prompt: Should a bulk load by another process close the native query path while indexes lag the rows?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer closing native admission during index-bypassing load; a cache/probe that misses that interval cannot justify current-index reliance.
    description: Default assumption.
  - label: "no: equal answers assume current indexes (document it)"
    description: ""
  - label: a load publishes a namespace-wide marker that `native_gate` checks
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer closing native admission during index-bypassing load; a cache/probe that misses that interval cannot justify current-index reliance.
```

<a id="q-cyp-004"></a>
### Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?

Run: Uplift 2026-11-13

Evidence: at the baseline (Python 3.11.18, driver 5.3.2) three tests in `tests/unit/test_shortest_path.py` fail: `RETURN p` arrives as a dict and the tests call `json.loads` on it (`:164, 186, 219`), raising "the JSON object must be str … not dict"; `PRE_RELEASE_CHECKLIST.md:282` records the unit suite green with drivers 5.4.0/5.4.1 on Python 3.12 and 3.13.

Interpretations: (a) the representation changed (driver or execution path) and the tests are stale; (b) a path must always come back as JSON text, and the dict is a regression on this driver or path.

Decision needed: the documented representation of a path value, and whether it may vary by driver. Open statement: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).


Audit: Working assumption (agent, unratified): Prefer a consistent structured path value; driver/path-dependent text is current behavior requiring a compatibility decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-cyp-004).

Canonical owner: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

```g5-question
schema: 1
id: q-cyp-004
status: open
prompt: Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer a consistent structured path value; driver/path-dependent text is current behavior requiring a compatibility decision.
    description: Default assumption.
  - label: the representation changed (driver or execution path) and the tests are stale
    description: ""
  - label: a path must always come back as JSON text, and the dict is a regression on this driver or path
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer a consistent structured path value; driver/path-dependent text is current behavior requiring a compatibility decision.
```

<a id="query.system-procedures.unknown"></a><!-- question identity -->
<a id="q-cyp-005"></a>
### Should a call to an unknown apoc, db or dbms procedure be refused?

[Q · query.system-procedures.unknown]

Run: Uplift 2026-11-13

Evidence: the `db.*`/`dbms.*`/`apoc.meta.*`/`gds.*` stubs exist, and an unknown `apoc`/`db`/`dbms` name answers no rows and no error (`engine.py:1039-1740`), while an unknown `ivg.*` or `gds.*` procedure is refused (reconstruction check 2(a)4, correction 21).

Interpretations: (a) answer empty for Browser compatibility; (b) refuse, as for `ivg.*`.

Decision needed: which. Open statement: [query.system-procedures.unknown](#q-cyp-005).


Audit: Working assumption (agent, unratified): Prefer a clear unknown-procedure refusal; preserve present empty results as observed compatibility until the owner decides. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-cyp-005).

Canonical owner: [query.system-procedures.unknown](#q-cyp-005).

```g5-question
schema: 1
id: query.system-procedures.unknown
status: open
prompt: Should a call to an unknown apoc, db or dbms procedure be refused?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer a clear unknown-procedure refusal; preserve present empty results as observed compatibility until the owner decides.
    description: Default assumption.
  - label: 4, correction 21)
    description: ""
  - label: answer empty for Browser compatibility
    description: ""
  - label: refuse, as for `ivg.*`
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer a clear unknown-procedure refusal; preserve present empty results as observed compatibility until the owner decides.
```

<a id="redaction.tombstone.digest-source"></a><!-- question identity -->
<a id="q-led-001"></a>
### Which copy of a record must an auditor keep to recompute its tombstone digest?

[Q · redaction.tombstone.digest-source]

Run: Uplift 2026-11-13

Evidence: `MutationRecord.from_row` normalizes graph `"\x00"` to None (`replay.py:56-74, 137-142`) while `CanonicalRecord` emits `"\u0000"` (`Ledger.cls:595-596`), and key and number formatting may differ; exports carry no records, and the canonical form is not specified outside `Ledger.cls` (A-history F18; reconstruction check G12).

Interpretations: (a) the server's canonical record captured before the redaction is the only valid preimage (document it, and how to capture it); (b) the public reader must reproduce the canonical form exactly.

Decision needed: which artifact an auditor keeps, and whether the canonical form is a published contract. Open statement: [redaction.tombstone.digest-source](#q-led-001).


Audit: Working assumption (agent, unratified): Treat auditor-held original canonical records as required to recompute digests; the product does not promise a retained recoverable preimage. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-led-001).

Canonical owner: [redaction.tombstone.digest-source](#q-led-001).

```g5-question
schema: 1
id: redaction.tombstone.digest-source
status: open
prompt: Which copy of a record must an auditor keep to recompute its tombstone digest?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Treat auditor-held original canonical records as required to recompute digests; the product does not promise a retained recoverable preimage.
    description: Default assumption.
  - label: the server's canonical record captured before the redaction is the only valid preimage (document it, and how to capture it)
    description: ""
  - label: the public reader must reproduce the canonical form exactly
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat auditor-held original canonical records as required to recompute digests; the product does not promise a retained recoverable preimage.
```

<a id="redaction.out-of-reach.other-copies"></a><!-- question identity -->
<a id="q-led-002"></a>
### Should the redaction receipt name IVG's own snapshot archives and the ledger rows an upgrade left behind?

[Q · redaction.out-of-reach.other-copies]

Run: Uplift 2026-11-13

Evidence: `save_snapshot` archives hold `^IVG.Ledger` and the ledger storage (ADMIN_GUIDE:989-991), so restoring an earlier archive brings back tombstoned content and `idem` bindings; after an R114 upgrade the 4.5.x `Graph_KG` ledger rows "stay where they are" (`legacy.py:612-613`) with uncleared metadata. The receipt's out-of-reach list names neither (`LedgerRedact.cls:505-508`) (A-history F8).

Interpretations: (a) name them in the receipt's out-of-reach list; (b) redaction must also reach them (refuse or rewrite archives it knows of; clear the legacy rows).

Decision needed: which. Open statement: [redaction.out-of-reach.other-copies](#q-led-002).


Audit: Working assumption (agent, unratified): List snapshots and legacy ledger copies as outside redaction reach; archive-retention/removal policy remains an owner decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-led-002).

Canonical owner: [redaction.out-of-reach.other-copies](#q-led-002).

```g5-question
schema: 1
id: redaction.out-of-reach.other-copies
status: open
prompt: Should the redaction receipt name IVG's own snapshot archives and the ledger rows an upgrade left behind?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: List snapshots and legacy ledger copies as outside redaction reach; archive-retention/removal policy remains an owner decision.
    description: Default assumption.
  - label: name them in the receipt's out-of-reach list
    description: ""
  - label: redaction must also reach them (refuse or rewrite archives it knows of; clear the legacy rows)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: List snapshots and legacy ledger copies as outside redaction reach; archive-retention/removal policy remains an owner decision.
```

<a id="ledger.lifecycle.disable-during-redaction"></a><!-- question identity -->
<a id="q-led-003"></a>
### What should disabling the ledger do while a redaction is unfinished?

[Q · ledger.lifecycle.disable-during-redaction]

Run: Uplift 2026-11-13

Evidence: `disable` takes no head lock and has no caller-transaction refusal; its behavior while a redaction marker exists was not checked (reconstruction check G38). Re-enabling afterwards skips the adoption silently ([bug-led-004](bugs_issues.md#bug-led-004)).

Interpretations: (a) refuse `disable` while a redaction is unfinished; (b) allow it, and define what the marker means while the ledger is disabled.

Decision needed: the lifecycle rule. Open statement: [ledger.lifecycle.disable-during-redaction](#q-led-003).


Audit: Working assumption (agent, unratified): Prefer refusal of disable during unfinished redaction; resumption and blocked readers require a deliberate lifecycle rule. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-led-003).

Canonical owner: [ledger.lifecycle.disable-during-redaction](#q-led-003).

```g5-question
schema: 1
id: ledger.lifecycle.disable-during-redaction
status: open
prompt: What should disabling the ledger do while a redaction is unfinished?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer refusal of disable during unfinished redaction; resumption and blocked readers require a deliberate lifecycle rule.
    description: Default assumption.
  - label: refuse `disable` while a redaction is unfinished
    description: ""
  - label: allow it, and define what the marker means while the ledger is disabled
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer refusal of disable during unfinished redaction; resumption and blocked readers require a deliberate lifecycle rule.
```

<a id="ledger.lifecycle.genesis.shared-ids"></a><!-- question identity -->
<a id="q-led-004"></a>
### How should the ledger's genesis record a node ID that two graphs hold?

[Q · ledger.lifecycle.genesis.shared-ids]

Run: Uplift 2026-11-13

Evidence: genesis scans `nodes`, `rdf_labels` and `rdf_props` with no graph (`LedgerGenesis.cls:17-36`), so an ID held by two graphs gives two `create_node` records and one merged set of labels and properties; how replay and verify fold them was not checked (reconstruction check 2(b)8, G8).

Interpretations: (a) acceptable: ledger nodes are graph-blind by design; (b) genesis should record one node per (graph, ID) or refuse.

Decision needed: which. Open statement: [ledger.lifecycle.genesis.shared-ids](#q-led-004).


Audit: Working assumption (agent, unratified): Keep namespace-wide bare node IDs in current genesis behavior; graph-specific ledger identity would require a record/migration decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-led-004).

Canonical owner: [ledger.lifecycle.genesis.shared-ids](#q-led-004).

```g5-question
schema: 1
id: ledger.lifecycle.genesis.shared-ids
status: open
prompt: How should the ledger's genesis record a node ID that two graphs hold?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep namespace-wide bare node IDs in current genesis behavior; graph-specific ledger identity would require a record/migration decision.
    description: Default assumption.
  - label: 8, G8)
    description: ""
  - label: "acceptable: ledger nodes are graph-blind by design"
    description: ""
  - label: genesis should record one node per (graph, ID) or refuse
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep namespace-wide bare node IDs in current genesis behavior; graph-specific ledger identity would require a record/migration decision.
```

<a id="ledger.verify.consistency"></a><!-- question identity -->
<a id="q-led-006"></a>
### Must verify compare one consistent moment of the ledger and the tables?

[Q · ledger.verify.consistency]

Run: Uplift 2026-11-13

Evidence: `verify()` checks the redaction marker once, reads the ledger and the tables with no lock, and commits an adoption without `expected_head` (`replay.py:806-858`; A-ops hazard (c)2; review R1-core R1-6). The race with a redaction is registered as [bug-led-001](bugs_issues.md#bug-led-001); with ordinary commits running, a verify can report differences that existed at no single moment.

Interpretations: (a) verify is best-effort; run it when writes are quiet (document it); (b) verify reads under the head lock, or retries until the head did not move.

Decision needed: which. Open statement: [ledger.verify.consistency](#q-led-006).


Audit: Working assumption (agent, unratified): Treat verify as requiring quiescent inputs for reliance until a consistent-view protocol is specified; unlocked multi-scan behavior is not a snapshot proof. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-led-006).

Canonical owner: [ledger.verify.consistency](#q-led-006).

```g5-question
schema: 1
id: ledger.verify.consistency
status: open
prompt: Must verify compare one consistent moment of the ledger and the tables?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Treat verify as requiring quiescent inputs for reliance until a consistent-view protocol is specified; unlocked multi-scan behavior is not a snapshot proof.
    description: Default assumption.
  - label: 2; review R1-core R1-6). The race with a redaction is registered as [bug-led-001](bugs_issues.md#bug-led-001); with ordinary commits running, a verify can repor
    description: 2; review R1-core R1-6). The race with a redaction is registered as [bug-led-001](bugs_issues.md#bug-led-001); with ordinary commits running, a verify can report differences that existed at no single moment
  - label: verify is best-effort; run it when writes are quiet (document it)
    description: ""
  - label: verify reads under the head lock, or retries until the head did not move
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat verify as requiring quiescent inputs for reliance until a consistent-view protocol is specified; unlocked multi-scan behavior is not a snapshot proof.
```

<a id="structure.node.read.aliases"></a><!-- question identity -->
<a id="q-iter-001"></a>
### How should flat node reads preserve colliding property aliases?

[Q · structure.node.read.aliases]

Run: Uplift improvement iteration 1, 2026-11-15

Classification: settled as built (both keys are accepted and one is lost at the flat reader); intended replacement needs ratification. `create_node` validates key width but reserves neither `p_id` nor `p_labels`; `get_nodes` renames only `id` and `labels` (`nodes_edges.py:1013-1014,670-676`). The writer/reader unit witness and Verus witness are in [node_read](models/node_read/NOTES.md).

Working answer: keep structural fields and return every property under a separate property map. Alternative: keep flat results but reserve and validate an alias namespace before writes; existing colliding data then requires a migration or explicit refusal. The product owner must choose compatibility and rollout. Owner: [structure.node.read.aliases](#q-iter-001); finding [bug-str-101](bugs_issues.md#bug-str-101).


Audit: Working assumption (agent, unratified): Preserve both accepted property values and structural identity; reserve aliases or introduce a property map only after a compatibility choice. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-001).

Canonical owner: [structure.node.read.aliases](#q-iter-001).

```g5-question
schema: 1
id: structure.node.read.aliases
status: open
prompt: How should flat node reads preserve colliding property aliases?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Preserve both accepted property values and structural identity; reserve aliases or introduce a property map only after a compatibility choice.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve both accepted property values and structural identity; reserve aliases or introduce a property map only after a compatibility choice.
```

<a id="q-con-001"></a>
### Must the streaming history reader bound its memory, or only its delivery?

Run: Consolidated uplift 2026-11-14

Evidence: `reconstruct(..., stream=True)` folds every record into one in-memory state and only then yields its entities (`ledger/replay.py:550-566`); the entity bound is enforced only when `stream=False` (`:555-556`), as the contract says (`specs/213-graph-revision-ledger/contracts/ledger-api.md:30`). `export_reconstruction` passes no bound and also materializes the whole state before writing NDJSON (`ledger/client.py:731-739`), while the contract says it "streams to NDJSON; never bounded" (`ledger-api.md:31`). The requirement text behind the bound (FR-035 to FR-037) is not in the repository.

Classification: settled as built (the bound applies to the materialized reader only; neither reader bounds memory); what was promised needs ratification.

Working answer: "streaming" describes delivery, not memory; the bound protects callers of the materialized reader. Material alternative: the bound exists to cap memory, so the streaming reader and the export should fold incrementally (or be bounded too). Claims that depend on it: public case J03's "streaming export path under its documented scope". Lead L1 of the reviewed plan; neither arm recorded it.

Iteration 2 corroboration: [reconstruction](models/reconstruction/NOTES.md) proves the bound exemption and shared structural fold; the actual named Python readers/export agree on the selected surviving-node journey and consume all records before yielding. This adds evidence to q-con-001; it is not a new streaming-memory finding. Canonical owner: [ledger.readers.bound](../ontology/features/ledger.g5.md#ledger.readers.bound).


Audit: Working assumption (agent, unratified): Keep delivery streaming separate from bounded-memory guarantees; full materialization is current behavior and a memory promise needs a separate bound. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-con-001).

Canonical owner: [ledger.readers.bound](../ontology/features/ledger.g5.md#ledger.readers.bound).

```g5-question
schema: 1
id: q-con-001
status: open
prompt: Must the streaming history reader bound its memory, or only its delivery?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep delivery streaming separate from bounded-memory guarantees; full materialization is current behavior and a memory promise needs a separate bound.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep delivery streaming separate from bounded-memory guarantees; full materialization is current behavior and a memory promise needs a separate bound.
```

<a id="ledger.readers.bound.policy"></a><!-- question identity -->
<a id="q-iter-002"></a>
### Must reconstruction's bound concern each intermediate graph or only the requested graph?

[Q · ledger.readers.bound.policy]

Run: Uplift improvement iteration 2, 2026-11-15

Classification: settled as built, intended policy needs ratification. `reconstruct` checks entity_count after each record (`replay.py:550-556`); a history create a, create b, delete b fails at bound 1 although its final graph contains only a. Streaming and export return a. [reconstruction model and Python comparison](models/reconstruction/NOTES.md) distinguish both histories. The API contract FR-035/036 references do not specify peak versus final size; available git history and tests do not settle a different policy.

Working answer: preserve and document the intermediate-size check for memory protection. Alternative: check only the final size, accepting a larger temporary graph. Product maintainer owns this choice at [ledger.readers.bound.policy](#q-iter-002); q-con-001 separately concerns whether streaming must bound memory. This is a specification/policy gap, not a confirmed product bug.


Audit: Working assumption (agent, unratified): Prefer an explicit peak reconstruction bound; current per-intermediate graph checks do not settle a final-graph-only policy. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-002).

Canonical owner: [ledger.readers.bound.policy](#q-iter-002).

```g5-question
schema: 1
id: ledger.readers.bound.policy
status: open
prompt: Must reconstruction's bound concern each intermediate graph or only the requested graph?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Prefer an explicit peak reconstruction bound; current per-intermediate graph checks do not settle a final-graph-only policy.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Prefer an explicit peak reconstruction bound; current per-intermediate graph checks do not settle a final-graph-only policy.
```

<a id="ledger.readers.diff.order"></a><!-- question identity -->
<a id="q-con-002"></a>
### Is a ledger diff an ordered script or an unordered set of net changes?

[Q · ledger.readers.diff.order]

Run: Consolidated uplift 2026-11-14

Evidence: `compute_diff` sorts entries by kind, ID and attribute (`ledger/replay.py:406-407`, `:535`); for one node deleted and re-created in the range the two existence entries tie and keep their forward order, so the inverse lists the creation before the deletion ([unit probe](results/unit-probes/20261115T043637Z-l2-inverse-order/receipt.json)). The contract calls the diff "sorted net, lifecycle-aware" (`ledger-api.md:29`).

Classification: needs ratification. Working answer: an unordered set of net changes (the contract's "net"), in which case order does not matter but the reverse diff's attribute values still do ([bug-led-101](audits/register-20261115/bugs-review.md#bug-led-101)). Alternative: an ordered script that a client may apply, which would require the inverse to reverse the order of tied entries. Lead L2 of the reviewed plan. Iteration 3 attaches this decision to canonical ledger.readers.diff.order. Producer inspection corrects the old empty deletion prior: NodeSnapshotJson carries full labels/properties at deletion. The simple delete/recreate neighbor preserves those values in inverse existence.after; changing a property before deleting still loses its earlier range prior when that lifecycle closes. Keep two choices explicit: (1) display a set of lifecycle entries with deletion-moment snapshots, the current working interpretation; (2) provide a complete endpoint delta or an applicable script, retaining range-start values and defining tie order. Neither is owner-ratified. As-built selection/inversion and continuous-life endpoint values now have history_diff proofs; full lifecycle reconstruction remains open.


Audit: Working assumption (agent, unratified): Treat lifecycle diff as an unordered net-change result until a stable script order is specified; consumers must not infer dependency order. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-con-002).

Canonical owner: [ledger.readers.diff.order](#q-con-002).

```g5-question
schema: 1
id: ledger.readers.diff.order
status: open
prompt: Is a ledger diff an ordered script or an unordered set of net changes?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Treat lifecycle diff as an unordered net-change result until a stable script order is specified; consumers must not infer dependency order.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat lifecycle diff as an unordered net-change result until a stable script order is specified; consumers must not infer dependency order.
```

<a id="algorithms.op.paths.weighted.parallel"></a><!-- question identity -->
<a id="q-iter-007"></a>
### Should weighted shortest path consider every parallel edge or the lowest-key representative graph?

[Q · algorithms.op.paths.weighted.parallel]

Run: Consolidated iteration9, 2026-11-15

Governing owner: [algorithms.op.paths.weighted.parallel](#q-iter-007). No provisional owner answer or human decision.

Evidence: USER_GUIDE631-644 promises cheapest path by edge weight. Spec234 FR004 mandates the lowest-key scalar leaf, while its FR015/clarifications explicitly discuss collapse for Arno/PPR/BFS rather than weighted Dijkstra. Actual DijkstraJson reads only scalar leaves. The valid mode-on native fixture in [weighted-native.json](../uplift/consolidated/iteration-9/weighted-native.json) has ekey0/weight10 and ekey5/weight1, plus a two-edge alternative of cost4: both native path and cost-only routes return4, whereas the whole stored multigraph has a cost1 path. [Independent source/intent review](../uplift/consolidated/iteration-9/weighted-projection-review.md) distinguishes this from the earlier mode-off harness-oracle miss.

Plausible answers: define weighted paths over the lowest-key projection for compatibility, stating that graph to callers; or optimize over all parallel rows, changing the reader to select the minimum admissible effective weight while preserving the storage layout. Neither answer is chosen here. The new queue proof is a minimum over its actual raw scalar graph and remains useful under either future producer choice; it is not a proof of the unresolved all-relationships interpretation. No new weighted bug, accepted repair or policy decision is counted.


Audit: Working assumption (agent, unratified): Keep the current lowest-key representative route distinct from all-parallel-edge shortest path; the optimization domain needs owner choice. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-007).

Canonical owner: [algorithms.op.paths.weighted.parallel](#q-iter-007).

```g5-question
schema: 1
id: algorithms.op.paths.weighted.parallel
status: open
prompt: Should weighted shortest path consider every parallel edge or the lowest-key representative graph?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Keep the current lowest-key representative route distinct from all-parallel-edge shortest path; the optimization domain needs owner choice.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep the current lowest-key representative route distinct from all-parallel-edge shortest path; the optimization domain needs owner choice.
```

<a id="algorithms.op.ppr.zero_ties"></a><!-- question identity -->
<a id="q-iter-008"></a>
### Should tiny positive PPR scores share the rounded zero tie or always precede true zeros?

[Q · algorithms.op.ppr.zero_ties]

Run: Consolidated iteration10, 2026-11-15

Owner: [algorithms.op.ppr.zero_ties](#q-iter-008). No provisional owner answer.

Evidence: USER_GUIDE550-552 and rank_key define ties at12 decimal places; USER_GUIDE593 says unscored zeros come after scored nodes. The actual native/store append/early-cut reader and the fallback full-map sort implement different answers when positive1e-13 rounds to0. The [six-case native panel](../uplift/consolidated/iteration-10/root-ppr-tie-native.json) retains a limit2 selected-set difference and matching limit1/larger-score/later-zero neighbors. [Independent review](../uplift/consolidated/iteration-10/root-ppr-review-intent.md) finds no source assigning precedence between these two statements.

Plausible answers: use one rounded-score/ID ordering over every node, including zeros; or put every genuinely scored positive node before unscored nodes and apply rounded ties within that group. No choice is made. [bug-plt-103](audits/register-20261115/bugs-review.md#bug-plt-103) is the independent route inconsistency, which remains a defect under either policy until both readers agree. No repair or human decision is accepted by this question.


Audit: Working assumption (agent, unratified): Preserve the rounded-score tie rule today; giving every positive raw score priority over true zero would change top-k admission. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#q-iter-008).

Canonical owner: [algorithms.op.ppr.zero_ties](#q-iter-008).

```g5-question
schema: 1
id: algorithms.op.ppr.zero_ties
status: open
prompt: Should tiny positive PPR scores share the rounded zero tie or always precede true zeros?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Preserve the rounded-score tie rule today; giving every positive raw score priority over true zero would change top-k admission.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve the rounded-score tie rule today; giving every positive raw score priority over true zero would change top-k admission.
```

<a id="install.schema.refusal.first-use-policy"></a><!-- question identity -->
<a id="HD-0101"></a>
### Should an engine that cannot read the schema record be refused?

[Q · install.schema.refusal.first-use-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: spec 262 FR-006 says an engine whose schema differs from the namespace's record must be refused on first access. When the record cannot be read (a user without %Native_GlobalAccess, or any other exception), the engine logs a WARNING and skips the check, so an engine built for another schema may write into the namespace beside the recorded one and share its globals.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0101.md](../../experiment/playbook-completion/intent/HD-0101.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (decisions.md marked this Supported because ADMIN_GUIDE documents the skip. The doc's commit (0bf9fc2c) treats the skip as a role misconfiguration and fixes it by requiring the resource. It does not choose fail-open, and the accepted AD); decision text [01.md](../../experiment/playbook-uplift/decisions/01.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Supported deployments can read the record (premise: the ADMIN_GUIDE role table grants %Native_GlobalAccess:U). Under that premise a mismatch is refused. The documented fail-open path is a separate 'unchecked' outcome that admits a mismatched engine. It is outside the binding guarantee and should be modelled that way, not treated as an accepted engine. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0101).

Canonical owner: [install.schema.refusal.first-use-policy](#HD-0101).

```g5-question
schema: 1
id: install.schema.refusal.first-use-policy
status: open
prompt: Should an engine that cannot read the schema record be refused?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Supported deployments can read the record (premise: the ADMIN_GUIDE role table grants %Native_GlobalAccess:U). Under that premise a mismatch is refused. The documented fail-open path is a separate 'unchecked' outcome that admits a mismatched engine. It is outside the binding guarantee and should be modelled that way, not treated as an accepted engine."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Supported deployments can read the record (premise: the ADMIN_GUIDE role table grants %Native_GlobalAccess:U). Under that premise a mismatch is refused. The documented fail-open path is a separate 'unchecked' outcome that admits a mismatched engine. It is outside the binding guarantee and should be modelled that way, not treated as an accepted engine."
```

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


Audit: Working assumption (agent, unratified): Treat a stored schema name as a namespace binding only. Represent readiness of each deployed capability (classes, adjacency index, ledger, erase) separately. An engine accepted by the record check has no claim on feature readiness. A feature call on a class-less namespace must give a named failure, not silently degrade. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0102).

Canonical owner: [install.setup.failed_deploy](#q-plt-010).

```g5-question
schema: 1
id: HD-0102
status: open
prompt: Should setup save the schema record when the class deploy failed or was turned off?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat a stored schema name as a namespace binding only. Represent readiness of each deployed capability (classes, adjacency index, ledger, erase) separately. An engine accepted by the record check has no claim on feature readiness. A feature call on a class-less namespace must give a named failure, not silently degrade.
    description: Default assumption.
  - label: record only when objectscript_deployed and objectscript_failed is empty -
    description: ""
  - label: record, but mark it incomplete so the first-access check names the missing classes
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat a stored schema name as a namespace binding only. Represent readiness of each deployed capability (classes, adjacency index, ledger, erase) separately. An engine accepted by the record check has no claim on feature readiness. A feature call on a class-less namespace must give a named failure, not silently degrade.
```

<a id="install.legacy.support-policy"></a><!-- question identity -->
<a id="HD-0103"></a>
### Are the files under sql/ part of the product?

[Q · install.legacy.support-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: sql/ holds schema.sql (a pre-spec-227 schema with single-column keys and no graph_id), globals_schema.sql (an unqualified procedure and two stub triggers on Graph_KG.rdf_edges), graph_path_globals.sql and graph_walk_tvf.sql (unqualified procedures), migrations/000-002 (the 2025 NodePK migration) and procedures/ kg_PageRank.sql (comments only). Setup runs none of them; the sdist ships them; scripts/deploy_production.py still runs sql/schema.sql and sql/operators_fixed.sql. The index of this upli…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0103.md](../../experiment/playbook-completion/intent/HD-0103.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same status and gist. Refined with the maintainer's 'one schema path' statement, the 4.7.0 maintenance and test of the legacy deployer, the fact that the sdist ships sql/ but not scripts/, and fraud_sample_data.sql as live demo data.)); decision text [01.md](../../experiment/playbook-uplift/decisions/01.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Inventory both install paths. The product contract (spec 262 schema, inventory test) covers initialize_schema only. scripts/deploy_production.py + sql/schema.sql + sql/operators_fixed.sql form a reachable legacy path that produces a non-conforming namespace (DDL-only before its class step, unqualified procedures). sql/fraud_sample_data.sql is maintained demo data. Files with no loader are historical material. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0103).

Canonical owner: [install.legacy.support-policy](#HD-0103).

```g5-question
schema: 1
id: install.legacy.support-policy
status: open
prompt: Are the files under sql/ part of the product?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Inventory both install paths. The product contract (spec 262 schema, inventory test) covers initialize_schema only. scripts/deploy_production.py + sql/schema.sql + sql/operators_fixed.sql form a reachable legacy path that produces a non-conforming namespace (DDL-only before its class step, unqualified procedures). sql/fraud_sample_data.sql is maintained demo data. Files with no loader are historical material.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Inventory both install paths. The product contract (spec 262 schema, inventory test) covers initialize_schema only. scripts/deploy_production.py + sql/schema.sql + sql/operators_fixed.sql form a reachable legacy path that produces a non-conforming namespace (DDL-only before its class step, unqualified procedures). sql/fraud_sample_data.sql is maintained demo data. Files with no loader are historical material.
```

<a id="graph.default.python-read-policy"></a><!-- question identity -->
<a id="HD-0201"></a>
### What does a Python read with no graph argument read?

[Q · graph.default.python-read-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the USER_GUIDE says Python methods that read take `graph=` and, omitted, mean the default graph, never every graph (docs/USER_GUIDE.md:466-467). Several readers take no `graph=` at all and read every graph: `get_node_ids_by_label`, `get_node_ids_by_property`, `get_property_pairs`, `get_property_values`, `property_value_exists`, `get_node_ids_like`, `count_subjects_with_property`, `nodes_exist` (iris_vector_graph/_engine/nodes_edges.py:760-966, 2590-2625). Their docstrings say "all graphs" or "n…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0201.md](../../experiment/playbook-completion/intent/HD-0201.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same status and choice. Strengthened by maintainer tasks R219/R249 (one rule for the Python API), the explicit HTTP /schema exception in ADMIN_API, and the third rule found on delete_node. The live probe confirms F-0206.)); decision text [02.md](../../experiment/playbook-uplift/decisions/02.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): For graph-aware Python reads, omission selects the default graph. Keep the all-graph id helpers as separate discovery operations with their scope visible. Never hydrate ids from one scope with another scope's records. Model delete_node's 'holding graph or refuse' rule as its own documented operation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0201).

Canonical owner: [graph.default.python-read-policy](#HD-0201).

Evidence (retest iteration 34, [observation](../uplift/consolidated/iteration-34/property-readers-observed-20261116T222559Z.json)): `get_node_ids_by_property(key, "7")` returned a named-graph node's ID that `get_nodes_by_property(key, "7")` with the same arguments left out, and `get_property_values`/`get_property_pairs` included the named graph's value; `get_nodes_by_property` and `get_nodes_by_label` read the default graph only.

```g5-question
schema: 1
id: graph.default.python-read-policy
status: open
prompt: What does a Python read with no graph argument read?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: For graph-aware Python reads, omission selects the default graph. Keep the all-graph id helpers as separate discovery operations with their scope visible. Never hydrate ids from one scope with another scope's records. Model delete_node's 'holding graph or refuse' rule as its own documented operation.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: For graph-aware Python reads, omission selects the default graph. Keep the all-graph id helpers as separate discovery operations with their scope visible. Never hydrate ids from one scope with another scope's records. Model delete_node's 'holding graph or refuse' rule as its own documented operation.
```

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


Audit: Working assumption (agent, unratified): For structural predicates, a triple with surviving timestamps keeps a structural row. A direct delete may remove the explicit assertion, but the row must stay (or revert to marked) while timestamps remain. Model as-built option (a) as the baseline that violates the implication, and keep the ADR-0015 temporal-only opt-out separate (no row ever). Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0302).

Canonical owner: [temporal.structural.explicit-delete](#q-tmp-006).

```g5-question
schema: 1
id: HD-0302
status: open
prompt: May a direct edge delete remove an edge row that a temporal edge still implies?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: For structural predicates, a triple with surviving timestamps keeps a structural row. A direct delete may remove the explicit assertion, but the row must stay (or revert to marked) while timestamps remain. Model as-built option (a) as the baseline that violates the implication, and keep the ADR-0015 temporal-only opt-out separate (no row ever).
    description: Default assumption.
  - label: delete the row and leave the temporal events (as built; maintainer-tested) -
    description: ""
  - label: refuse while the triple has temporal events and the row is marked -
    description: ""
  - label: delete the row and the triple's temporal events together -
    description: ""
  - label: leave a marked row alone and delete only an explicit one (an adopted row reverts to marked)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: For structural predicates, a triple with surviving timestamps keeps a structural row. A direct delete may remove the explicit assertion, but the row must stay (or revert to marked) while timestamps remain. Model as-built option (a) as the baseline that violates the implication, and keep the ADR-0015 temporal-only opt-out separate (no row ever).
```

<a id="structure.degree.cache.retirement-policy"></a><!-- question identity -->
<a id="HD-0401"></a>
### How should erase and rebuild retire a source generation?

[Q · structure.degree.cache.retirement-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the degree cache's reader protocol (ADR-0012, `Graph.KG.Adj.Degree`) assumes a source generation only moves forward. `Adjacency.RemoveSource`, `RemoveGraph` and `RemoveAll` kill `^KG("gen")` instead, so a generation can return to a value an in-flight reader already read (finding F-0401). Which rule should hold?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0401.md](../../experiment/playbook-completion/intent/HD-0401.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live evidence confirms the ABA precondition; the spike's 'or kill' explains why the maintainer accepted the kill for stale entries, but neither source covers an in-flight reader, so the working answer stands.)); decision text [04.md](../../experiment/playbook-uplift/decisions/04.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Unchanged from decisions.md: invalidation can never make an old degree-cache value valid again; model a monotone generation or a fresh graph epoch across erase and rebuild; keep as-built A (kill) as the baseline with its narrow window. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0401).

Canonical owner: [structure.degree.cache.retirement-policy](#HD-0401).

```g5-question
schema: 1
id: structure.degree.cache.retirement-policy
status: open
prompt: How should erase and rebuild retire a source generation?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Unchanged from decisions.md: invalidation can never make an old degree-cache value valid again; model a monotone generation or a fresh graph epoch across erase and rebuild; keep as-built A (kill) as the baseline with its narrow window."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Unchanged from decisions.md: invalidation can never make an old degree-cache value valid again; model a monotone generation or a fresh graph epoch across erase and rebuild; keep as-built A (kill) as the baseline with its narrow window."
```

<a id="structure.adjacency.rebuild-concurrency"></a><!-- question identity -->
<a id="HD-0402"></a>
### May two adjacency rebuilds run at the same time?

[Q · structure.adjacency.rebuild-concurrency]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `TraversalBuild.BuildKG` takes the writer lock on the parent name in shared mode (`Adjacency.BeginRebuild`), which keeps readers from caching but does not keep a second `BuildKG` out. Only the interned snapshot's build has its own exclusive lock (`^IVG.NKGBuild`). `docs/ADMIN_GUIDE.md:1049-1050` says "One rebuild runs at a time", naming that lock. Is a second `sync()` while one runs supported (and if so, what must the result be), or should it wait or be refused?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0402.md](../../experiment/playbook-completion/intent/HD-0402.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live check confirms the decisions.md reading (the cited lock protects only the ^NKG path); no new authority.)); decision text [04.md](../../experiment/playbook-uplift/decisions/04.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Unchanged: at most one publishing rebuild per adjacency structure; a second call waits or gets a documented busy result. Refined: ADMIN_GUIDE's sentence is literally about ^NKG and holds live; the ^KG half is unserialized. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0402).

Canonical owner: [structure.adjacency.rebuild-concurrency](#HD-0402).

```g5-question
schema: 1
id: structure.adjacency.rebuild-concurrency
status: open
prompt: May two adjacency rebuilds run at the same time?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Unchanged: at most one publishing rebuild per adjacency structure; a second call waits or gets a documented busy result. Refined: ADMIN_GUIDE's sentence is literally about ^NKG and holds live; the ^KG half is unserialized."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Unchanged: at most one publishing rebuild per adjacency structure; a second call waits or gets a documented busy result. Refined: ADMIN_GUIDE's sentence is literally about ^NKG and holds live; the ^KG half is unserialized."
```

<a id="temporal.structural.ledger-nodes.policy"></a><!-- question identity -->
<a id="HD-0501"></a>
### Are the end nodes a temporal write creates governed by the ledger?

[Q · temporal.structural.ledger-nodes.policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: with the adjacency index, every structural temporal write inserts its two endpoint rows into `Graph_KG.nodes` when they are missing (`Adjacency.AssertTemporalRow`, `Adjacency.cls:591-602`). Node rows are governed content: `verify()` reads every one (`replay.py:590-597`). Neither the engine path nor a changeset's `create_temporal_edge` op records them, and strict mode does not refuse the write. Should those nodes be recorded, refused, or excluded from what `verify()` compares?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0501.md](../../experiment/playbook-completion/intent/HD-0501.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (decisions.md left 'record them or derived provenance' open. Commit 43efd473 ('temporal writes still create no revisions', mirror 'no longer an unrecorded write', endpoints asserted by the same commit) argues against recording engine-pa); decision text [05.md](../../experiment/playbook-uplift/decisions/05.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Engine-path endpoints: derived, with identifiable provenance (e.g. the 'bare temporal endpoint' rule purge already uses) and excluded from genesis/verify; changeset temporal ops: follow the relationship endpoint rule (refuse a missing endpoint or record a stub). Keep their real effects in the environment model; treat ledger-api.md:92 as stale for the indexed path. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0501).

Canonical owner: [temporal.structural.ledger-nodes.policy](#HD-0501).

```g5-question
schema: 1
id: temporal.structural.ledger-nodes.policy
status: open
prompt: Are the end nodes a temporal write creates governed by the ledger?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Engine-path endpoints: derived, with identifiable provenance (e.g. the 'bare temporal endpoint' rule purge already uses) and excluded from genesis/verify; changeset temporal ops: follow the relationship endpoint rule (refuse a missing endpoint or record a stub). Keep their real effects in the environment model; treat ledger-api.md:92 as stale for the indexed path."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Engine-path endpoints: derived, with identifiable provenance (e.g. the 'bare temporal endpoint' rule purge already uses) and excluded from genesis/verify; changeset temporal ops: follow the relationship endpoint rule (refuse a missing endpoint or record a stub). Keep their real effects in the environment model; treat ledger-api.md:92 as stale for the indexed path."
```

<a id="temporal.ledger.scope-policy"></a><!-- question identity -->
<a id="HD-0502"></a>
### Is the temporal index inside the ledger's guarantee?

[Q · temporal.ledger.scope-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: CONTEXT.md:75-76 says a temporal edge is "subject to the revision ledger (via a Changeset temporal op)". At the pin a changeset can write temporal edges in the ledger's transaction and records `create_temporal_edge` with the triple, graph and time only (`LedgerApply.cls:637-640`). There is no op for a temporal delete, purge, bucket purge or row drop; engine temporal writes make no revision (`test_ledger_us11_temporal_coexist.py::test_temporal_writes_and_purges_create_no_revisions`); replay igno…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0502.md](../../experiment/playbook-completion/intent/HD-0502.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (Status lowered from supported to assumption: the only decision (43efd473) settles 'temporal writes create no revisions'; the exclusion of changeset temporal ops from reconstruct/verify rests on implementation and tests, and the accepte); decision text [05.md](../../experiment/playbook-uplift/decisions/05.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Unchanged reading: record the changeset temporal op in history (audit, redaction); treat temporal tiers, engine temporal writes, purges and temporal replay as outside the structural replay guarantee; model their real effects, including purges deleting endpoint nodes. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0502).

Canonical owner: [temporal.ledger.scope-policy](#HD-0502).

```g5-question
schema: 1
id: temporal.ledger.scope-policy
status: open
prompt: Is the temporal index inside the ledger's guarantee?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Unchanged reading: record the changeset temporal op in history (audit, redaction); treat temporal tiers, engine temporal writes, purges and temporal replay as outside the structural replay guarantee; model their real effects, including purges deleting endpoint nodes."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Unchanged reading: record the changeset temporal op in history (audit, redaction); treat temporal tiers, engine temporal writes, purges and temporal replay as outside the structural replay guarantee; model their real effects, including purges deleting endpoint nodes."
```

<a id="search.erasure.indexes.coverage-policy"></a><!-- question identity -->
<a id="HD-0601"></a>
### Are the IVF, tree (VecIndex) and PLAID indexes inside the erasure promise?

[Q · search.erasure.indexes.coverage-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: erasure is defined as removing a graph's content "from every store" (CONTEXT.md:198-208, ADR-0004), but `^IVF`, `^VecIdx` and `^PLAID` are keyed by index name only, hold no graph, and are named nowhere in `Graph.KG.Eraser` or the `Graph.KG.GraphStores` inventory. The 4.0.0 migration guide calls the IVF index a "remaining gap" (docs/migration/v4.0.0.md:742-750). After `EraseGraph(g)`, must these indexes stop answering g's node ids and stop holding g's vectors?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0601.md](../../experiment/playbook-completion/intent/HD-0601.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live reproduction and the Eraser/GraphStores precedents strengthen the working answer; no authority decides it.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Unchanged: model retained index contents as observable after erasure unless purged; graph-owned indexes require invalidation or deletion on erase; caller-fed indexes need an explicit owner/exposure statement. Refined with the graph-derived (IVF) vs caller-fed (VecIndex, PLAID) split. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0601).

Canonical owner: [search.erasure.indexes.coverage-policy](#HD-0601).

```g5-question
schema: 1
id: search.erasure.indexes.coverage-policy
status: open
prompt: Are the IVF, tree (VecIndex) and PLAID indexes inside the erasure promise?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Unchanged: model retained index contents as observable after erasure unless purged; graph-owned indexes require invalidation or deletion on erase; caller-fed indexes need an explicit owner/exposure statement. Refined with the graph-derived (IVF) vs caller-fed (VecIndex, PLAID) split."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Unchanged: model retained index contents as observable after erasure unless purged; graph-owned indexes require invalidation or deletion on erase; caller-fed indexes need an explicit owner/exposure statement. Refined with the graph-derived (IVF) vs caller-fed (VecIndex, PLAID) split."
```

<a id="search.scope.indexes.publication-policy"></a><!-- question identity -->
<a id="HD-0602"></a>
### May an index build be seen half-done, and may a stopped build leave a partial index?

[Q · search.scope.indexes.publication-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `ivf_build` calls `Build` (which kills `^IVF(name)`), then `AddBatch` per 500 rows, then `FinalizeIndex`, each a separate call with no lock and no transaction; `VecIndex.Build` kills the trees and rebuilds them; `PLAIDSearch.Build` kills `^PLAID(name)` and refills it. A search during the build sees an empty or partial index, and a stopped build leaves one. Is that acceptable?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0602.md](../../experiment/playbook-completion/intent/HD-0602.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live evidence confirms the baseline; no source settles the service level.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Unchanged: readers see a complete published index or a clear unavailable result, including after an interrupted rebuild; the existing partial-build behaviour is the modelled baseline. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0602).

Canonical owner: [search.scope.indexes.publication-policy](#HD-0602).

```g5-question
schema: 1
id: search.scope.indexes.publication-policy
status: open
prompt: May an index build be seen half-done, and may a stopped build leave a partial index?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Unchanged: readers see a complete published index or a clear unavailable result, including after an interrupted rebuild; the existing partial-build behaviour is the modelled baseline."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Unchanged: readers see a complete published index or a clear unavailable result, including after an interrupted rebuild; the existing partial-build behaviour is the modelled baseline."
```

<a id="search.fusion.vector-graph-policy"></a><!-- question identity -->
<a id="HD-0603"></a>
### Should the vector-and-graph search keep its k best candidates?

[Q · search.fusion.vector-graph-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `kg_VECTOR_GRAPH_SEARCH` puts vector hits, their one-hop neighbours and text hits in a Python set, keeps `all_entities[:k]` (any k, set order), then sorts those k by vector similarity (`iris_vector_graph/_engine/vector.py:1513-1543`). The best vector hits can be dropped before the sort. The docstring admits "keeps k of that set in no particular order". Is that the intended contract?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0603.md](../../experiment/playbook-completion/intent/HD-0603.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Live evidence quantifies the baseline; the R025 documentation is a description, not a decision.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Unchanged: the reviewed ranking contract is the best k of the scored candidate set with defined ties; the documented set-order truncation is the baseline (now confirmed live). Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0603).

Iteration 49 evidence (agent): the truncation is now observed at the reader. With k = 2 and five candidates, `kg_VECTOR_GRAPH_SEARCH` left out the best vector hit for 7 of 8 Python hash seeds in one run and 5 of 8 in another ([binding](results/retrieval_compose/20261117T024807Z-binding/receipt.json)); `retrieval_compose.rs::theorem_best_hit_can_be_dropped`, with the ranked alternative as control `sort-before-truncate`. The as-built rule is stated in [search.fusion.vector_graph](../ontology/features/search.g5.md#search.fusion.vector_graph). The question itself is unchanged.

Canonical owner: [search.fusion.vector-graph-policy](#HD-0603).

```g5-question
schema: 1
id: search.fusion.vector-graph-policy
status: open
prompt: Should the vector-and-graph search keep its k best candidates?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Unchanged: the reviewed ranking contract is the best k of the scored candidate set with defined ties; the documented set-order truncation is the baseline (now confirmed live)."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Unchanged: the reviewed ranking contract is the best k of the scored candidate set with defined ties; the documented set-order truncation is the baseline (now confirmed live)."
```

<a id="search.embedding.queue.processing.consumers"></a><!-- question identity -->
<a id="HD-0604"></a>
### May two embed queue workers run at once?

[Q · search.embedding.queue.processing.consumers]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the queue has no claim state (`ClaimPendingBatch` is "a plain ordered scan", `EmbedQueue.cls:22-25`), yet a namespace can run the IRIS task (`start_background_embedding`) and the Python `process_embed_queue` at the same time, or two Python workers. Both then process the same PENDING entries: double model calls, last writer wins on the vector, and status races between DONE and ERROR.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0604.md](../../experiment/playbook-completion/intent/HD-0604.md) (status supported· Confidence: high · Changed from decisions.md: yes (Status assumption -> supported for the single-consumer design premise: commit 5bb149ed states 'Single-processor' explicitly. The enforcement question stays open.)); decision text [06.md](../../experiment/playbook-uplift/decisions/06.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): A single active consumer per namespace is the contract (supported by 5bb149ed); model both workers as independently schedulable, treat single-worker as an unenforced premise, and prefer enforcement (refuse a second worker) or documentation; atomic claims with recovery remain the multi-worker alternative. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0604).

Canonical owner: [search.embedding.queue.processing.consumers](#HD-0604).

```g5-question
schema: 1
id: search.embedding.queue.processing.consumers
status: open
prompt: May two embed queue workers run at once?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: A single active consumer per namespace is the contract (supported by 5bb149ed); model both workers as independently schedulable, treat single-worker as an unenforced premise, and prefer enforcement (refuse a second worker) or documentation; atomic claims with recovery remain the multi-worker alternative.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: A single active consumer per namespace is the contract (supported by 5bb149ed); model both workers as independently schedulable, treat single-worker as an unenforced premise, and prefer enforcement (refuse a second worker) or documentation; atomic claims with recovery remain the multi-worker alternative.
```

<a id="search.bm25.write_lock.build-policy"></a><!-- question identity -->
<a id="HD-0701"></a>
### Must a BM25 Build (and Drop) exclude writers and be all-or-nothing?

[Q · search.bm25.write_lock.build-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: ADR-0007 says schema 2 "does every write under an index-level lock in a transaction", but the spec's requirement (FR-019) names only Insert and Delete. `Build` kills `^BM25Idx(name)` and rewrites it with no lock and no transaction; `Drop` kills with no lock. While a Build runs, what may an Insert, a Delete, a second Build, a Drop or an Upgrade on the same name do, and may a stopped Build leave a partial index?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0701.md](../../experiment/playbook-completion/intent/HD-0701.md) (status assumption· Confidence: medium (intent), high (as-built) · Changed from decisions.md: no (evidence now live; status unchanged)); decision text [07.md](../../experiment/playbook-uplift/decisions/07.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Serialize Build, Drop, Insert, Delete and Upgrade per index and publish a complete generation or return unavailable, including after a crash; a Build that is refused or indexes nothing must not destroy the previous index. Model the as-built (unlocked Build/Drop, Kill-first) separately as the baseline. Same as decisions.md. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0701).

Canonical owner: [search.bm25.write_lock.build-policy](#HD-0701).

```g5-question
schema: 1
id: search.bm25.write_lock.build-policy
status: open
prompt: Must a BM25 Build (and Drop) exclude writers and be all-or-nothing?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Serialize Build, Drop, Insert, Delete and Upgrade per index and publish a complete generation or return unavailable, including after a crash; a Build that is refused or indexes nothing must not destroy the previous index. Model the as-built (unlocked Build/Drop, Kill-first) separately as the baseline. Same as decisions.md.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Serialize Build, Drop, Insert, Delete and Upgrade per index and publish a complete generation or return unavailable, including after a crash; a Build that is refused or indexes nothing must not destroy the previous index. Model the as-built (unlocked Build/Drop, Kill-first) separately as the baseline. Same as decisions.md.
```

<a id="search.fusion.absent"></a><!-- question identity -->
<a id="HD-0702"></a>
### Which reciprocal-rank-fusion rule is the product's?

[Q · search.fusion.absent]

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


Audit: Working assumption (agent, unratified): Preserve and test each surface's rule, including missing-rank handling and which text list it reads; document that the engine method and the SQL procedure of the same name differ. Introduce a single formula only with a versioned contract. Same as decisions.md. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0702).

Iteration 49 evidence (agent): the engine rule and the `FuseRanks`/SQL rule were both observed on one graph with the same legs (a vector-only item 31st versus 61st; [binding](results/retrieval_compose/20261117T024807Z-binding/receipt.json)); bug-srch-005 is now E2E reproduced. The per-surface rules are stated in [search.fusion.surfaces](../ontology/features/search.g5.md#search.fusion.surfaces). No authority settled the rule.

Canonical owner: [search.fusion.absent](#HD-0702).

```g5-question
schema: 1
id: search.fusion.absent
status: open
prompt: Which reciprocal-rank-fusion rule is the product's?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Preserve and test each surface's rule, including missing-rank handling and which text list it reads; document that the engine method and the SQL procedure of the same name differ. Introduce a single formula only with a versioned contract. Same as decisions.md.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Preserve and test each surface's rule, including missing-rank handling and which text list it reads; document that the engine method and the SQL procedure of the same name differ. Introduce a single formula only with a versioned contract. Same as decisions.md.
```

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


Audit: Working assumption (agent, unratified): Model kg_TXT as iFind-then-LIKE (documented as-built). Record FR-012/US5/SC-004 and tasks T034/T035 as a spec/doc conflict (S3, F-0708), not as a current obligation the pin fails. If the fallback returns, it applies only on the LIKE path, only to an index whose recorded graph equals the requested graph, never across graphs. Why changed: decisions.md called this Supported on spec 044 FR-012, SC-004 and PR #8. Those establish the 2026-04 feature, not that it is still wanted: the Draft spec is the only post-removal carrier, it was copied wholesale with the schema-2 amendment, and the maintainer's later kg_TXT redesign (v2.18.2, US7, docstring, generated API reference) excludes it. No source "supersedes" FR-012 explicitly either, so neither reading is supported; the assumption follows the newer, user-facing contract. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0703).

Canonical owner: [search.bm25.default_index](#q-srch-004).

```g5-question
schema: 1
id: HD-0703
status: open
prompt: Is spec 044's kg_TXT-to-BM25 fallback still wanted?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Model kg_TXT as iFind-then-LIKE (documented as-built). Record FR-012/US5/SC-004 and tasks T034/T035 as a spec/doc conflict (S3, F-0708), not as a current obligation the pin fails. If the fallback returns, it applies only on the LIKE path, only to an index whose recorded graph equals the requested graph, never across graphs. Why changed: decisions.md called this Supported on spec 044 FR-012, SC-004 and PR #8. Those establish the 2026-04 feature, not that it is still wanted: the Draft spec is the only post-removal carrier, it was copied wholesale with the schema-2 amendment, and the maintainer's later kg_TXT redesign (v2.18.2, US7, docstring, generated API reference) excludes it. No source \"supersedes\" FR-012 explicitly either, so neither reading is supported; the assumption follows the newer, user-facing contract."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Model kg_TXT as iFind-then-LIKE (documented as-built). Record FR-012/US5/SC-004 and tasks T034/T035 as a spec/doc conflict (S3, F-0708), not as a current obligation the pin fails. If the fallback returns, it applies only on the LIKE path, only to an index whose recorded graph equals the requested graph, never across graphs. Why changed: decisions.md called this Supported on spec 044 FR-012, SC-004 and PR #8. Those establish the 2026-04 feature, not that it is still wanted: the Draft spec is the only post-removal carrier, it was copied wholesale with the schema-2 amendment, and the maintainer's later kg_TXT redesign (v2.18.2, US7, docstring, generated API reference) excludes it. No source \"supersedes\" FR-012 explicitly either, so neither reading is supported; the assumption follows the newer, user-facing contract."
```

<a id="search.bm25.name-policy"></a><!-- question identity -->
<a id="HD-0704"></a>
### Is `__stop__` a reserved BM25 index name?

[Q · search.bm25.name-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the stopword list lives at `^BM25Idx("__stop__")`, beside the indexes. `Build`, `Insert`, `Drop` and `Search` accept the name `__stop__`; `Drop("__stop__")` deletes the stopword list (rebuilt on the next tokenize) and `Build("__stop__", ...)` mixes an index into it. `List()` skips the name. Should writers refuse it, or should the stopword list move out of the index global?
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0704.md](../../experiment/playbook-completion/intent/HD-0704.md) (status supported(outcome: `^BM25Idx("__stop__")` is the stopword list, not an index) · mechanism: assumption ·); decision text [07.md](../../experiment/playbook-uplift/decisions/07.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Reserve `__stop__`: public BM25 entry points (`bm25_build/insert/delete/drop/upgrade`, `BM25BuildInput`, index handles, `kg_BM25`/`ivg.bm25.search`) refuse it; the embedded registry walk skips it. Model the as-built acceptance as a defect against the documented stopword list (cross-index). Moving the list to its own global is the compatible alternative mechanism. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0704).

Canonical owner: [search.bm25.name-policy](#HD-0704).

```g5-question
schema: 1
id: search.bm25.name-policy
status: open
prompt: Is `__stop__` a reserved BM25 index name?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Reserve `__stop__`: public BM25 entry points (`bm25_build/insert/delete/drop/upgrade`, `BM25BuildInput`, index handles, `kg_BM25`/`ivg.bm25.search`) refuse it; the embedded registry walk skips it. Model the as-built acceptance as a defect against the documented stopword list (cross-index). Moving the list to its own global is the compatible alternative mechanism."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Reserve `__stop__`: public BM25 entry points (`bm25_build/insert/delete/drop/upgrade`, `BM25BuildInput`, index handles, `kg_BM25`/`ivg.bm25.search`) refuse it; the embedded registry walk skips it. Model the as-built acceptance as a defect against the documented stopword list (cross-index). Moving the list to its own global is the compatible alternative mechanism."
```

<a id="search.fusion.python.support"></a><!-- question identity -->
<a id="HD-0705"></a>
### Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?

[Q · search.fusion.python.support]

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


Audit: Working assumption (agent, unratified): Treat the three as compatibility surfaces and qualify each: RRFFusion is a pure standard-RRF helper (document that its rule differs from engine `kg_RRF_FUSE`, HD-0702); HybridSearchFusion is de facto public (migration guide) and graph-scoped; TextSearchEngine is exported but reads every graph and its document search cannot reach the IVG Schema, so it is not a supported reader of graph-scoped data. Prefer deprecation with migration advice (to `kg_TXT` / `bm25_search`) or a `graph=` argument; do not remove without a compatibility decision. Same direction as decisions.md. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0705).

Canonical owner: [search.fusion.python.support](#HD-0705).

```g5-question
schema: 1
id: search.fusion.python.support
status: open
prompt: Are `TextSearchEngine`, `RRFFusion` and `HybridSearchFusion` supported public API?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Treat the three as compatibility surfaces and qualify each: RRFFusion is a pure standard-RRF helper (document that its rule differs from engine `kg_RRF_FUSE`, HD-0702); HybridSearchFusion is de facto public (migration guide) and graph-scoped; TextSearchEngine is exported but reads every graph and its document search cannot reach the IVG Schema, so it is not a supported reader of graph-scoped data. Prefer deprecation with migration advice (to `kg_TXT` / `bm25_search`) or a `graph=` argument; do not remove without a compatibility decision. Same direction as decisions.md."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Treat the three as compatibility surfaces and qualify each: RRFFusion is a pure standard-RRF helper (document that its rule differs from engine `kg_RRF_FUSE`, HD-0702); HybridSearchFusion is de facto public (migration guide) and graph-scoped; TextSearchEngine is exported but reads every graph and its document search cannot reach the IVG Schema, so it is not a supported reader of graph-scoped data. Prefer deprecation with migration advice (to `kg_TXT` / `bm25_search`) or a `graph=` argument; do not remove without a compatibility decision. Same direction as decisions.md."
```

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


Audit: Working assumption (agent, unratified): Take the contract text as intended: strict refuses with no window. Record the 5 s cache window (reproduced live) and fail-open (tested) as product defects against ledger-api.md (F-0801), and keep their obligations open. Downstream modules (erasure, redaction, verify) may not assume that every graph-table change under strict mode has a ledger record. verify() detects bypass rows after the fact. Raw SQL and BulkLoader remain outside by the contract's own text (HD-0301/1103). Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0801).

Canonical owner: [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict).

```g5-question
schema: 1
id: HD-0801
status: open
prompt: Where and how should ledger strict mode refuse a Cypher write?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Take the contract text as intended: strict refuses with no window. Record the 5 s cache window (reproduced live) and fail-open (tested) as product defects against ledger-api.md (F-0801), and keep their obligations open. Downstream modules (erasure, redaction, verify) may not assume that every graph-table change under strict mode has a ledger record. verify() detects bypass rows after the fact. Raw SQL and BulkLoader remain outside by the contract's own text (HD-0301/1103)."
    description: Default assumption.
  - label: keep the client check; document the 5 s window and fail-open in ledger-api.md and USER_GUIDE -
    description: ""
  - label: fail closed and re-read strict on every guarded write (one class call per write) -
    description: ""
  - label: server-side enforcement (Txn_Begin check or table triggers), which also covers raw SQL/BulkLoader (new contract; see HD-1103)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Take the contract text as intended: strict refuses with no window. Record the 5 s cache window (reproduced live) and fail-open (tested) as product defects against ledger-api.md (F-0801), and keep their obligations open. Downstream modules (erasure, redaction, verify) may not assume that every graph-table change under strict mode has a ledger record. verify() detects bypass rows after the fact. Raw SQL and BulkLoader remain outside by the contract's own text (HD-0301/1103)."
```

<a id="query.graph-scope.read.mapped-label-policy"></a><!-- question identity -->
<a id="HD-0802"></a>
### Does a mapped label belong to every graph?

[Q · query.graph-scope.read.mapped-label-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `map_sql_table` maps a label to an outside SQL table for the whole namespace. The graph filter of a scoped query is added only to the four graph tables (`translator.py:404`, `719-779`), so under `USE GRAPH 'g'` a mapped label still answers every row of its table. The glossary says graphs are isolation units (CONTEXT.md:27-37); the mapping docs say nothing about graphs.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0802.md](../../experiment/playbook-completion/intent/HD-0802.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same reading. The live probe confirms global visibility, even under a graph that holds nothing. No new authoritative source found.)); decision text [08.md](../../experiment/playbook-uplift/decisions/08.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Treat a mapping registration as namespace-wide (the as-built baseline). Under a named USE GRAPH scope, require either graph-aware mapping provenance or an explicitly documented exception. Model the current global visibility as a known deviation from the glossary's isolation rule. It is not a security breach, because the namespace is the boundary (USER_GUIDE:467-468). Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0802).

Canonical owner: [query.graph-scope.read.mapped-label-policy](#HD-0802).

```g5-question
schema: 1
id: query.graph-scope.read.mapped-label-policy
status: open
prompt: Does a mapped label belong to every graph?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat a mapping registration as namespace-wide (the as-built baseline). Under a named USE GRAPH scope, require either graph-aware mapping provenance or an explicitly documented exception. Model the current global visibility as a known deviation from the glossary's isolation rule. It is not a security breach, because the namespace is the boundary (USER_GUIDE:467-468).
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat a mapping registration as namespace-wide (the as-built baseline). Under a named USE GRAPH scope, require either graph-aware mapping provenance or an explicitly documented exception. Model the current global visibility as a known deviation from the glossary's isolation rule. It is not a security breach, because the namespace is the boundary (USER_GUIDE:467-468).
```

<a id="install.legacy.sql-operators-policy"></a><!-- question identity -->
<a id="HD-0803"></a>
### Is `sql/operators.sql` product code?

[Q · install.legacy.sql-operators-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `sql/operators.sql` defines `kg_KNN_VEC`, `kg_TXT`, `kg_RRF_FUSE`, `kg_GRAPH_PATH`, `kg_RERANK` and `kg_PPR` with no graph argument, unqualified table names and a label join without `graph_id`. Nothing in the package or setup loads it (the live procedures are in `iris_vector_graph/schema.py:2437-2526`; `scripts/deploy_production.py` loads `sql/operators_fixed.sql`). The uplift's denominator counts it as product SQL.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0803.md](../../experiment/playbook-completion/intent/HD-0803.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (Status changed from supported to assumption. The deployment paths are facts (now also live) that identify what runs. Whether the file is product code is a maintainer decision that no source states. Same classification otherwise.)); decision text [08.md](../../experiment/playbook-uplift/decisions/08.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Classify sql/operators.sql as shipped historical/reference SQL with no deployment path. It is outside the executed product surface, but stays in the inventory as a shipped artifact whose definitions are not graph-scoped. Trace operators_fixed.sql (legacy deployer) and the schema.py procedures separately. If anyone runs the file by hand, it creates unqualified, graph-blind procedures (F-0820-like behaviour). Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0803).

Canonical owner: [install.legacy.sql-operators-policy](#HD-0803).

```g5-question
schema: 1
id: install.legacy.sql-operators-policy
status: open
prompt: Is `sql/operators.sql` product code?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Classify sql/operators.sql as shipped historical/reference SQL with no deployment path. It is outside the executed product surface, but stays in the inventory as a shipped artifact whose definitions are not graph-scoped. Trace operators_fixed.sql (legacy deployer) and the schema.py procedures separately. If anyone runs the file by hand, it creates unqualified, graph-blind procedures (F-0820-like behaviour).
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Classify sql/operators.sql as shipped historical/reference SQL with no deployment path. It is outside the executed product surface, but stays in the inventory as a shipped artifact whose definitions are not graph-scoped. Trace operators_fixed.sql (legacy deployer) and the schema.py procedures separately. If anyone runs the file by hand, it creates unqualified, graph-blind procedures (F-0820-like behaviour).
```

<a id="query.browser-metadata.ddl-notice-policy"></a><!-- question identity -->
<a id="HD-0804"></a>
### Should `CREATE CONSTRAINT` / `CREATE INDEX` be refused rather than accepted as a no-op?

[Q · query.browser-metadata.ddl-notice-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `execute_cypher` answers any text that starts with `CREATE CONSTRAINT`, `DROP CONSTRAINT`, `CREATE INDEX`, `CREATE TEXT INDEX`, `CREATE RANGE INDEX`, `CREATE POINT INDEX`, `DROP INDEX`, `CREATE FULLTEXT` or `CREATE LOOKUP` with an empty result and does nothing (`iris_vector_graph/_engine/query.py:1886-1897`). A client that creates a uniqueness constraint believes it is enforced. It exists so that Neo4j tools that send such DDL keep working.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0804.md](../../experiment/playbook-completion/intent/HD-0804.md) (status supported· Confidence: high · Changed from decisions.md: yes (Status changed from assumption to supported. The maintainer commit f4a13d75 states that skipping the DDL is correct behaviour, which settles refuse-vs-accept. 'Make it visible' remains a proposal.)); decision text [08.md](../../experiment/playbook-uplift/decisions/08.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Treat the accepted DDL as an acknowledged no-op that establishes no invariant (supported by f4a13d75 and pinned by tests). Model no uniqueness guarantee from it. As a proposed strengthening, not a decision: document it in USER_GUIDE beside the parse-error rule and add a metadata warning. Refusal (option c) would reverse a maintainer decision. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0804).

Canonical owner: [query.browser-metadata.ddl-notice-policy](#HD-0804).

```g5-question
schema: 1
id: query.browser-metadata.ddl-notice-policy
status: open
prompt: Should `CREATE CONSTRAINT` / `CREATE INDEX` be refused rather than accepted as a no-op?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Treat the accepted DDL as an acknowledged no-op that establishes no invariant (supported by f4a13d75 and pinned by tests). Model no uniqueness guarantee from it. As a proposed strengthening, not a decision: document it in USER_GUIDE beside the parse-error rule and add a metadata warning. Refusal (option c) would reverse a maintainer decision."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Treat the accepted DDL as an acknowledged no-op that establishes no invariant (supported by f4a13d75 and pinned by tests). Model no uniqueness guarantee from it. As a proposed strengthening, not a decision: document it in USER_GUIDE beside the parse-error rule and add a metadata warning. Refusal (option c) would reverse a maintainer decision."
```

<a id="query.native.privileges.recheck-policy"></a><!-- question identity -->
<a id="HD-0901"></a>
### Should a running engine notice a revoked table right or a dropped adjacency index?

[Q · query.native.privileges.recheck-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the native gate asks three facts once per engine and keeps them: SELECT on the four graph tables (`engine._native_privileges`, never asked again), the adjacency index (`_adjacency_indexed`, asked again only by `initialize_schema`) and the executor's plan version (same). The native path reads globals, which SQL rights do not guard (ADMIN_GUIDE, "What is the boundary"). After `REVOKE SELECT` on `rdf_props`, or after another process drops `idx_edges_adj`, a long-lived engine keeps reading natively…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0901.md](../../experiment/playbook-completion/intent/HD-0901.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (decisions.md required authorization at use for both facts. FR-011 itself permits caching per process and user, and the later R280 maintainer statement makes the database resource the native boundary. Authorization at use via SQL grants); decision text [09.md](../../experiment/playbook-uplift/decisions/09.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Split the question. (1) A SQL REVOKE is not guaranteed to reach running engines' native reads. To cut native access, revoke the database resource or %Native_ClassExecution, or start new engines. Treat FR-011's executor-side check as an unimplemented spec requirement (F-0908) whose amendment is the maintainer's call. (2) For the route capability, keep FR-003: native reads require the index to be declared at the time of the read. Model an out-of-band drop under running engines as a premise violation ('the index is not dropped while engines run'), not a supported transition, unless Run checks Indexed(). Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0901).

Canonical owner: [query.native.privileges.recheck-policy](#HD-0901).

```g5-question
schema: 1
id: query.native.privileges.recheck-policy
status: open
prompt: Should a running engine notice a revoked table right or a dropped adjacency index?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Split the question. (1) A SQL REVOKE is not guaranteed to reach running engines' native reads. To cut native access, revoke the database resource or %Native_ClassExecution, or start new engines. Treat FR-011's executor-side check as an unimplemented spec requirement (F-0908) whose amendment is the maintainer's call. (2) For the route capability, keep FR-003: native reads require the index to be declared at the time of the read. Model an out-of-band drop under running engines as a premise violation ('the index is not dropped while engines run'), not a supported transition, unless Run checks Indexed()."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Split the question. (1) A SQL REVOKE is not guaranteed to reach running engines' native reads. To cut native access, revoke the database resource or %Native_ClassExecution, or start new engines. Treat FR-011's executor-side check as an unimplemented spec requirement (F-0908) whose amendment is the maintainer's call. (2) For the route capability, keep FR-003: native reads require the index to be declared at the time of the read. Model an out-of-band drop under running engines as a premise violation ('the index is not dropped while engines run'), not a supported transition, unless Run checks Indexed()."
```

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


Audit: Working assumption (agent, unratified): Keep ordinary SQL fallback. In shadow validation, record a native exception as an unsuccessful comparison: raise in shadow mode, or count failures and report them at the end of the run. Require a clean comparison (not a fallback) before claiming parity. The FR-010 default flip and the 3896/3896 figure establish only that no compared answer differed. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0902).

Canonical owner: [query.shadow.native-failure](#q-cyp-002).

```g5-question
schema: 1
id: HD-0902
status: open
prompt: Should shadow mode fail when the native path raises an error?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Keep ordinary SQL fallback. In shadow validation, record a native exception as an unsuccessful comparison: raise in shadow mode, or count failures and report them at the end of the run. Require a clean comparison (not a fallback) before claiming parity. The FR-010 default flip and the 3896/3896 figure establish only that no compared answer differed."
    description: Default assumption.
  - label: keep the fallback in shadow mode (today) -
    description: ""
  - label: raise in shadow mode only -
    description: ""
  - label: count native failures and report them at the end of a shadow run without raising
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Keep ordinary SQL fallback. In shadow validation, record a native exception as an unsuccessful comparison: raise in shadow mode, or count failures and report them at the end of the run. Require a clean comparison (not a fallback) before claiming parity. The FR-010 default flip and the 3896/3896 figure establish only that no compared answer differed."
```

<a id="structure.write.reader-isolation-policy"></a><!-- question identity -->
<a id="HD-0903"></a>
### What may a native read answer while another writer's transaction is open?

[Q · structure.write.reader-isolation-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: a native read takes no lock and no snapshot (NAT-T4.6). It reads `^KG` (adjacency and labels), the `rdf_props` storage globals and, for an id or property start, the node and property rows through SQL, at moments spread over the walk. A writer's open transaction is visible to it (P-0002), and may be visible in part: a new edge's `^KG` entry before its far node's label, or a property changed between two reads of the same run. Spec 253 speaks only of the caller's own transaction. Is "whatever each…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0903.md](../../experiment/playbook-completion/intent/HD-0903.md) (status assumption· Confidence: medium · Changed from decisions.md: no (Same reading. decisions.md's caveat that the earlier probe 'does not establish every SQL read has the same isolation' is now answered for this pattern: the SQL path matched native at every step, and USER_GUIDE:260-262 documents dirty vi); decision text [09.md](../../experiment/playbook-uplift/decisions/09.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Allow the observed interleavings on both paths: a native or SQL read may see a writer's uncommitted writes, including part of one transaction, and loses them on rollback. Grant snapshot or all-or-nothing visibility only to paths with an explicit synchronization contract and evidence (none for Cypher reads). The ADR-0012 degree cache is the one guarded structure. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0903).

Canonical owner: [structure.write.reader-isolation-policy](#HD-0903).

```g5-question
schema: 1
id: structure.write.reader-isolation-policy
status: open
prompt: What may a native read answer while another writer's transaction is open?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Allow the observed interleavings on both paths: a native or SQL read may see a writer's uncommitted writes, including part of one transaction, and loses them on rollback. Grant snapshot or all-or-nothing visibility only to paths with an explicit synchronization contract and evidence (none for Cypher reads). The ADR-0012 degree cache is the one guarded structure."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Allow the observed interleavings on both paths: a native or SQL read may see a writer's uncommitted writes, including part of one transaction, and loses them on rollback. Grant snapshot or all-or-nothing visibility only to paths with an explicit synchronization contract and evidence (none for Cypher reads). The ADR-0012 degree cache is the one guarded structure."
```

<a id="query.compiled.fallback.failure-policy"></a><!-- question identity -->
<a id="HD-0904"></a>
### Should a compiled plan that fails while running be set aside?

[Q · query.compiled.fallback.failure-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: ADR-0014 says the interpreter answers every shape that is not compiled, failed to compile or cannot be recorded. A compiled class that compiles but raises while it runs (a generator defect, a class deleted under a running read) is not covered: the error leaves `Run`, the engine falls back to the SQL path (NAT-T6.1), and the entry stays "ok", so every later read of that shape fails natively first and is answered by SQL. Should such a failure mark the entry so the interpreter answers the shape ne…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0904.md](../../experiment/playbook-completion/intent/HD-0904.md) (status assumption· Confidence: medium · Changed from decisions.md: yes (Refined. decisions.md said 'a fallback outcome' without naming one. ADR-0014's invariant and spec 257 FR-004 name the interpreter as the fallback, and Gen's 'a failed build is not tried again' rule is the existing quarantine precedent.); decision text [09.md](../../experiment/playbook-uplift/decisions/09.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Treat a run-time failure of a compiled entry as a fallback outcome: quarantine the entry for that plan generation (as a failed build already is), let the interpreter answer, and retry only after invalidation (a new stamp, DropAll or a deploy). SQL fallback for every later read (as built) is a correct-answer but degraded baseline that violates ADR-0014's 'answers exactly as the interpreter'. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-0904).

Canonical owner: [query.compiled.fallback.failure-policy](#HD-0904).

```g5-question
schema: 1
id: query.compiled.fallback.failure-policy
status: open
prompt: Should a compiled plan that fails while running be set aside?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Treat a run-time failure of a compiled entry as a fallback outcome: quarantine the entry for that plan generation (as a failed build already is), let the interpreter answer, and retry only after invalidation (a new stamp, DropAll or a deploy). SQL fallback for every later read (as built) is a correct-answer but degraded baseline that violates ADR-0014's 'answers exactly as the interpreter'."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Treat a run-time failure of a compiled entry as a fallback outcome: quarantine the entry for that plan generation (as a failed build already is), let the interpreter answer, and retry only after invalidation (a new stamp, DropAll or a deploy). SQL fallback for every later read (as built) is a correct-answer but degraded baseline that violates ADR-0014's 'answers exactly as the interpreter'."
```

<a id="algorithms.op.neighbors.scope"></a>
### Which graph should the unscoped retrieval operators read?

[Q · algorithms.op.neighbors.scope]

Which graph should the unscoped retrieval operators read?
- Provisional answer (agent, unratified): the default graph, with a `graph=` argument, as `kg_NEIGHBORHOOD_EXPANSION`, `kg_PPR` and the walks do; a pipeline that chains them then reads one graph throughout.
- Alternative, as built for `kg_NEIGHBORS` and `kg_MENTIONS`: every graph, as a Cypher query without `USE GRAPH` does ([graph scope](../ontology/concepts/graph-scope.g5.md)).

Disposition: open. Working assumption: keep today's answers; document that `kg_NEIGHBORS` reads every graph. Evidence: [W48](../uplift/consolidated/iteration-42/neighbors-PAIRS.md), [retrieval_scope](models/retrieval_scope/NOTES.md).

```g5-question
{
  "schema": 1,
  "id": "algorithms.op.neighbors.scope",
  "status": "open",
  "prompt": "Which graph should the unscoped retrieval operators read?",
  "allow_free_text": true,
  "multi_select": false,
  "options": [
    {
      "label": "The default graph, with a graph= argument, like the other retrieval operators",
      "description": ""
    },
    {
      "label": "Every graph, as Cypher without USE GRAPH does",
      "description": ""
    }
  ]
}
```

<a id="fhir.sql_mapping.cache"></a>
### Should a table mapping made by one engine reach engines that are already running?

[Q · fhir.sql_mapping.cache]

Should a table mapping made by one engine reach engines that are already running?
- Provisional answer (agent, unratified): yes for long-lived servers. An HTTP or Bolt server's engine keeps answering from IVG's own nodes after another engine maps the label, until it reloads; the two answer one query differently.
- Alternative: keep the per-engine cache and document that every other engine must call `reload_table_mappings()` (or restart).
- As built: each engine loads mappings on first use and refreshes them only on its own mapping calls or `reload_table_mappings()`.

Disposition: open. Working assumption: keep the cache, and document the reload. Evidence: [W46](../uplift/consolidated/iteration-40/sqlmap-PAIRS.md), [sql_mapping](models/sql_mapping/NOTES.md).

```g5-question
{
  "schema": 1,
  "id": "fhir.sql_mapping.cache",
  "status": "open",
  "prompt": "Should a table mapping made by one engine reach engines that are already running?",
  "allow_free_text": true,
  "multi_select": false,
  "options": [
    {
      "label": "Yes: running engines see a mapping change without a reload",
      "description": ""
    },
    {
      "label": "Keep the per-engine cache and document reload_table_mappings() for every other engine",
      "description": ""
    }
  ]
}
```

<a id="install.inference.assert_after"></a>
### Should creating an edge that inference already wrote make it an asserted edge?

[Q · install.inference.assert_after]

Should creating an edge that inference already wrote make it an asserted edge?
- Provisional answer (agent, unratified): yes. A create states the fact, so retracting inference should keep it, as it keeps an edge created before materializing.
- Alternative: refuse the create, naming the inferred edge, so the caller knows retract will remove it.
- As built: the create answers False and the edge stays marked inferred, so retract deletes it ([bug-str-105](bugs_issues.md#bug-str-105)).

Disposition: open. Working assumption: yes, a create asserts. Evidence: [W44](../uplift/consolidated/iteration-38/inference-PAIRS.md), [inference_rows](models/inference_rows/NOTES.md).

```g5-question
{
  "schema": 1,
  "id": "install.inference.assert_after",
  "status": "open",
  "prompt": "Should creating an edge that inference already wrote make it an asserted edge?",
  "allow_free_text": true,
  "multi_select": false,
  "options": [
    {
      "label": "Yes: the create clears the inferred marker, so retract keeps the edge",
      "description": ""
    },
    {
      "label": "Refuse the create, naming the inferred edge",
      "description": ""
    }
  ]
}
```

<a id="algorithms.op.walks.rows"></a>
### Should a graph walk list every edge it walks, or one row per node reached?

[Q · algorithms.op.walks.rows]

Should a graph walk list every edge it walks, or one row per node reached?
- Provisional answer (agent, unratified): every edge walked, as `khop` lists them, because the rows carry the source and type and `max_results` counts edges.
- Alternative: one row per node, at the hop it was first reached, with a stated rule for which parent is kept.
- As built: every edge walked, except that edges reaching the same node at the same hop collapse to the last one ([bug-str-103](bugs_issues.md#bug-str-103)).

Disposition: open. Working assumption: every edge walked. Evidence: [W43](../uplift/consolidated/iteration-37/traversal-PAIRS.md), [walk_reader](models/walk_reader/NOTES.md).

```g5-question
{
  "schema": 1,
  "id": "algorithms.op.walks.rows",
  "status": "open",
  "prompt": "Should a graph walk list every edge it walks, or one row per node reached?",
  "allow_free_text": true,
  "multi_select": false,
  "options": [
    {
      "label": "Every edge walked, as khop lists them",
      "description": ""
    },
    {
      "label": "One row per node, at the hop it was first reached, with a stated rule for which parent is kept",
      "description": ""
    }
  ]
}
```

<a id="algorithms.op.walks.result-policy"></a><!-- question identity -->
<a id="HD-1001"></a>
### What should `random_walk` answer, and over which graph?

[Q · algorithms.op.walks.result-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `random_walk` needs the Arno library and answers `[]` without it, although the walk it calls (`NKGAccelTraversal.RandomWalkJson`) is ObjectScript; with the library it walks `^NKG`, every graph merged (F-1002). No spec states its intent.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1001.md](../../experiment/playbook-completion/intent/HD-1001.md) (status assumption. random_walk takes no graph, so it walks the default graph (USER_GUIDE), and it answers with or without the library (ADMIN_GUIDE, CONTEXT). Neither [] for a missing library nor a merged-graph walk meets both. No spec covers random_walk; the docstring describes the [] behaviour but was wri); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Walk the default graph's adjacency (graph key 0) in ObjectScript, library or not (option (a)). Where only a merged ^NKG route is available and a named graph has edges, refuse visibly rather than answer [] or a merged walk. An explicit graph= argument (option (c)) is a compatible extension. Changed from decisions.md: **yes**. decisions.md asked for a declared scope plus an observable 'unavailable' result. The deployed ObjectScript walk runs without the library (upstream test and live), and ADMIN_GUIDE says every algorithm has an ObjectScript answer. So a real default-graph answer is the better-supported reading. 'Unavailable' remains only for a route that cannot honour the scope. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1001).

Canonical owner: [algorithms.op.walks.result-policy](#HD-1001).

```g5-question
schema: 1
id: algorithms.op.walks.result-policy
status: open
prompt: What should `random_walk` answer, and over which graph?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Walk the default graph's adjacency (graph key 0) in ObjectScript, library or not (option (a)). Where only a merged ^NKG route is available and a named graph has edges, refuse visibly rather than answer [] or a merged walk. An explicit graph= argument (option (c)) is a compatible extension.
    description: Default assumption.
  - label: ). Where only a merged ^NKG route is available and a named graph has edges, refuse visibly rather than answer [] or a merged walk. An explicit graph= argument (
    description: ). Where only a merged ^NKG route is available and a named graph has edges, refuse visibly rather than answer [] or a merged walk. An explicit graph= argument (option
  - label: ") is a compatible extension. Changed from decisions.md: **yes**. decisions.md asked for a declared scope plus an observable 'unavailable' result. The deployed O"
    description: ") is a compatible extension. Changed from decisions.md: **yes**. decisions.md asked for a declared scope plus an observable 'unavailable' result. The deployed ObjectScript walk runs without the library (upstream test and live), and ADMIN_GUIDE says every algorithm has an ObjectScript answer. So a real default-graph answer is the better-supported reading. 'Unavailable' remains only for a route that cannot honour the scope. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1001)"
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Walk the default graph's adjacency (graph key 0) in ObjectScript, library or not (option (a)). Where only a merged ^NKG route is available and a named graph has edges, refuse visibly rather than answer [] or a merged walk. An explicit graph= argument (option (c)) is a compatible extension.
```

<a id="algorithms.op.paths.direction"></a><!-- question identity -->
<a id="HD-1003"></a>
### Should the shortest-path routines refuse a direction they do not walk?

[Q · algorithms.op.paths.direction]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `TraversalPaths.ShortestPathJson` walks only `"out"` and `"both"` and answers no path for anything else; `ShortestLength` reads any value but `"both"` as `"out"`. The store and query callers guard (they turn `"in"` round), but both are callable class methods. `DijkstraJson` and `DijkstraCost` refuse through `CheckDirection`.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1003.md](../../experiment/playbook-completion/intent/HD-1003.md) (status supported. A routine must not answer an unsupported direction as 'no path' or as another direction's path. It refuses a direction outside its set or implements it; this is maintainer policy in 99b00ce9. Whether the class methods implement 'in' or refuse it is open. Python store methods carry the pub); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep the public 'in' semantics, caller reversal included. Require ShortestPathJson and ShortestLength to refuse any direction outside {out, both}, or to implement 'in' by walking from the far end. Require IRISGraphStore.shortest_path_length to reverse 'in' as execute_shortest_path does. Record the live false positive as a defect against its docstring. Changed from decisions.md: **yes**. Status moves from assumption to supported: maintainer commit 99b00ce9 states the refuse-outside-set policy for ObjectScript entry points. New live evidence shows a wrong positive answer, not just a missing one, on a public store method. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1003).

Iteration 57 (continuation; evidence only, no card field changed): the store's `shortest_path_length(…, 'in')` passes `in` to `ShortestLength`, which walks it as `out` ([bug-str-113](bugs_issues.md#bug-str-113)), while `execute_shortest_path` reverses it; and `execute_bfs` neither refuses nor normalizes a direction outside out/in/both ([bug-str-114](bugs_issues.md#bug-str-114)). Both are modeled in [traversal_strategy](models/traversal_strategy/NOTES.md); the working assumption (refuse or reverse) rejects both observed outcomes.

Canonical owner: [algorithms.op.paths.direction](#HD-1003).

```g5-question
schema: 1
id: algorithms.op.paths.direction
status: open
prompt: Should the shortest-path routines refuse a direction they do not walk?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the public 'in' semantics, caller reversal included. Require ShortestPathJson and ShortestLength to refuse any direction outside {out, both}, or to implement 'in' by walking from the far end. Require IRISGraphStore.shortest_path_length to reverse 'in' as execute_shortest_path does. Record the live false positive as a defect against its docstring.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep the public 'in' semantics, caller reversal included. Require ShortestPathJson and ShortestLength to refuse any direction outside {out, both}, or to implement 'in' by walking from the far end. Require IRISGraphStore.shortest_path_length to reverse 'in' as execute_shortest_path does. Record the live false positive as a defect against its docstring.
```

<a id="ledger.node-scope.missing-default-policy"></a><!-- question identity -->
<a id="HD-1101"></a>
### What should a node change do when only a named graph holds the id?

[Q · ledger.node-scope.missing-default-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the ledger keeps nodes in the default graph (4.6.0 R281/R290) but asks whether a node exists by id in any graph (`Graph.KG.LedgerApply.NodeExists`, `iris_src/src/Graph/KG/LedgerApply.cls:79-84`), on purpose for edge end nodes (`:86-95`). For a node id that only a named graph holds, what should `create_node`, `upsert_node`, `set_prop`, `add_label`, `remove_*` and `delete_node` (plain and detach) do?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1101.md](../../experiment/playbook-completion/intent/HD-1101.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep graph-blind existence. A node change that needs the default-graph row (`set_prop`, `remove_prop`, `add_label`, `remove_label`, `delete_node`, `upsert_node` with labels or properties) refuses with nothing applied and no record when that row is absent, under a reason distinct from `node_not_found` (the maintainer's meaning of that code stays). Model edge endpoint lookup separately (`EnsureEndpoint`). Changed from decisions.md: **yes, refined**: the refusal outcome is kept, but it is not an existence failure; the existence semantics are now supported by a maintainer commit. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1101).

Canonical owner: [ledger.node-scope.missing-default-policy](#HD-1101).

```g5-question
schema: 1
id: ledger.node-scope.missing-default-policy
status: open
prompt: What should a node change do when only a named graph holds the id?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep graph-blind existence. A node change that needs the default-graph row (`set_prop`, `remove_prop`, `add_label`, `remove_label`, `delete_node`, `upsert_node` with labels or properties) refuses with nothing applied and no record when that row is absent, under a reason distinct from `node_not_found` (the maintainer's meaning of that code stays). Model edge endpoint lookup separately (`EnsureEndpoint`).
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep graph-blind existence. A node change that needs the default-graph row (`set_prop`, `remove_prop`, `add_label`, `remove_label`, `delete_node`, `upsert_node` with labels or properties) refuses with nothing applied and no record when that row is absent, under a reason distinct from `node_not_found` (the maintainer's meaning of that code stays). Model edge endpoint lookup separately (`EnsureEndpoint`).
```

<a id="ledger.lifecycle.settings-transaction-policy"></a><!-- question identity -->
<a id="HD-1102"></a>
### Should disable() and set_strict() refuse a caller's open transaction, as enable() does?

[Q · ledger.lifecycle.settings-transaction-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: 4.7.0 made `enable()` and `redact()` refuse a caller transaction that holds a write (`iris_vector_graph/ledger/client.py:268-279`), because over a separate Native API connection they ran outside it. `disable()` and `set_strict()` were not changed (`:299-309`): they run `Graph.KG.Ledger.Disable` / `SetStrict` through `engine._iris_obj()`, which is the caller's own process for an engine made on a connection without stored credentials and another process for a `from_connect` engine (`iris_vector_g…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1102.md](../../experiment/playbook-completion/intent/HD-1102.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Refuse `disable()` and `set_strict()` inside a caller transaction on every engine, as `enable()`/`redact()`. Changed from decisions.md: **no** (strengthened). The live run adds a reason: ledger lifecycle state is global and read dirty by other processes, so a joined toggle that is later rolled back has already changed what other writers and guards did. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1102).

Canonical owner: [ledger.lifecycle.settings-transaction-policy](#HD-1102).

```g5-question
schema: 1
id: ledger.lifecycle.settings-transaction-policy
status: open
prompt: Should disable() and set_strict() refuse a caller's open transaction, as enable() does?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Refuse `disable()` and `set_strict()` inside a caller transaction on every engine, as `enable()`/`redact()`.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Refuse `disable()` and `set_strict()` inside a caller transaction on every engine, as `enable()`/`redact()`.
```

<a id="ledger.strict.server-policy"></a><!-- question identity -->
<a id="HD-1103"></a>
### Should strict mode be enforced by the server, or stay a Python-only check?

[Q · ledger.strict.server-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: strict mode is checked only by `iris_vector_graph.ledger.guard.LedgerGuard` before engine writes (`iris_vector_graph/ledger/guard.py:75-80`). It caches the state for 5 s per engine and fails open when it cannot read it (`:38-59`). The server's own writers (`Graph.KG.Eraser`, `Graph.KG.TemporalIndex`, the SQL procedures), raw SQL, `BulkLoader`, the GraphQL mutations and other clients are not held to it. The contract documents "BulkLoader and raw SQL are not guarded" (`specs/213-graph-revision-le…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1103.md](../../experiment/playbook-completion/intent/HD-1103.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Treat strict mode as a client-side, cached (5 s), fail-open guard on the contract's listed calls at this pin; inventory uncovered Python paths, server writers (Eraser, TemporalIndex, FHIR sync, SQL procedures) and external writers as possible unrecorded writers. Changed from decisions.md: **no**. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1103).

Canonical owner: [ledger.strict.server-policy](#HD-1103).

```g5-question
schema: 1
id: ledger.strict.server-policy
status: open
prompt: Should strict mode be enforced by the server, or stay a Python-only check?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat strict mode as a client-side, cached (5 s), fail-open guard on the contract's listed calls at this pin; inventory uncovered Python paths, server writers (Eraser, TemporalIndex, FHIR sync, SQL procedures) and external writers as possible unrecorded writers.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat strict mode as a client-side, cached (5 s), fail-open guard on the contract's listed calls at this pin; inventory uncovered Python paths, server writers (Eraser, TemporalIndex, FHIR sync, SQL procedures) and external writers as possible unrecorded writers.
```

<a id="ledger.lifecycle.settings-policy"></a><!-- question identity -->
<a id="HD-1104"></a>
### Should the ledger's settings be changeable after the genesis?

[Q · ledger.lifecycle.settings-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `max_ops` (the size limit) and `recon_bound` are written only by the genesis (`iris_src/src/Graph/KG/Ledger.cls:289-292`). `enable()` on an enabled ledger ignores every argument (`:254-260`). Re-enable after disable ignores `max_ops` and `recon_bound` but overwrites strict mode with the value passed, which defaults to off (`:271-275`), so `set_strict(True)`, `disable()`, `enable()` leaves strict off, and a `set_strict(True)` made while disabled is lost on re-enable. Is this the intended lifecyc…
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1104.md](../../experiment/playbook-completion/intent/HD-1104.md) (status none); decision text [11.md](../../experiment/playbook-uplift/decisions/11.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep `max_ops` and `recon_bound` fixed at genesis. Model strict as set by `enable(strict=...)` on genesis and on every re-enable (default False) and by `set_strict`; record the reset on re-enable as an explicit transition and do not assume strict survives a disable/enable cycle. Changed from decisions.md: **no**. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1104).

Canonical owner: [ledger.lifecycle.settings-policy](#HD-1104).

```g5-question
schema: 1
id: ledger.lifecycle.settings-policy
status: open
prompt: Should the ledger's settings be changeable after the genesis?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep `max_ops` and `recon_bound` fixed at genesis. Model strict as set by `enable(strict=...)` on genesis and on every re-enable (default False) and by `set_strict`; record the reset on re-enable as an explicit transition and do not assume strict survives a disable/enable cycle.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep `max_ops` and `recon_bound` fixed at genesis. Model strict as set by `enable(strict=...)` on genesis and on every re-enable (default False) and by `set_strict`; record the reset on re-enable as an explicit transition and do not assume strict survives a disable/enable cycle.
```

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


Audit: Working assumption (agent, unratified): Treat post-commit properties as a separate direct write outside revision replay; `verify()` reports them until adopted. Require that a replayed commit not re-apply them (idempotency contract), recording the pin's re-application as a defect (F-1101). Changed from decisions.md: **no**. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1105).

Canonical owner: [ledger.commit.post-commit.recorded](#q-010).

```g5-question
schema: 1
id: HD-1105
status: open
prompt: Should post-commit properties be recorded by the ledger?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat post-commit properties as a separate direct write outside revision replay; `verify()` reports them until adopted. Require that a replayed commit not re-apply them (idempotency contract), recording the pin's re-application as a defect (F-1101).
    description: Default assumption.
  - label: Record them as `set_prop` records of the same revision (server substitutes the revision id). - Skip post-commit properties on `replayed=True` only (keeps Approa
    description: Record them as `set_prop` records of the same revision (server substitutes the revision id). - Skip post-commit properties on `replayed=True` only (keeps Approach A; closes F-1101). -
  - label: Drop the feature
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat post-commit properties as a separate direct write outside revision replay; `verify()` reports them until adopted. Require that a replayed commit not re-apply them (idempotency contract), recording the pin's re-application as a defect (F-1101).
```

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


Audit: Working assumption (agent, unratified): Serialize erasure with ledger commits and redaction on the same lock: the erasure holds the head lock until its outermost transaction ends (an IRIS lock released inside a transaction is held to its end, P-0003), AND the redaction's opening liveness check and marker run under that lock (HD-1301). Neither alone closes the open-erasure case: with only the erasure lock the dirty opening check still passes and the batches tombstone a target the erasure later restores; with only the locked opening check the erasure holds nothing to wait on. A liveness check that reads committed data only is an alternative to the erasure lock for the redaction half, but not for the F-1201 statement half. Changed from decisions.md: **yes**. Refined. decisions.md proposed 'initially model the ledger head lock'. The new live probe shows the open-erasure case is reachable through the public API (erase_graph inside… Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1201).

Canonical owner: [erasure.concurrency](#q-004).

```g5-question
schema: 1
id: HD-1201
status: open
prompt: Should a graph erasure take the ledger head lock?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Serialize erasure with ledger commits and redaction on the same lock: the erasure holds the head lock until its outermost transaction ends (an IRIS lock released inside a transaction is held to its end, P-0003), AND the redaction's opening liveness check and marker run under that lock (HD-1301). Neither alone closes the open-erasure case: with only the erasure lock the dirty opening check still passes and the batches tombstone a target the erasure later restores; with only the locked opening check the erasure holds nothing to wait on. A liveness check that reads committed data only is an alternative to the erasure lock for the redaction half, but not for the F-1201 statement half."
    description: Default assumption.
  - label: erasure holds the head lock for its whole transaction (with HD-1301's locked start) -
    description: ""
  - label: document that erasure needs a quiet graph (no concurrent commit, redaction, or open caller transaction) and refuse erase_graph inside a caller transaction, as 4
    description: document that erasure needs a quiet graph (no concurrent commit, redaction, or open caller transaction) and refuse erase_graph inside a caller transaction, as 4.7.0 refuses redact() -
  - label: a graph-scoped lock shared by erasure, commits touching that graph, and redaction of that graph -
    description: ""
  - label: redaction's liveness checks read committed data only (covers the redaction half, not F-1201)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Serialize erasure with ledger commits and redaction on the same lock: the erasure holds the head lock until its outermost transaction ends (an IRIS lock released inside a transaction is held to its end, P-0003), AND the redaction's opening liveness check and marker run under that lock (HD-1301). Neither alone closes the open-erasure case: with only the erasure lock the dirty opening check still passes and the batches tombstone a target the erasure later restores; with only the locked opening check the erasure holds nothing to wait on. A liveness check that reads committed data only is an alternative to the erasure lock for the redaction half, but not for the F-1201 statement half."
```

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


Audit: Working assumption (agent, unratified): (a) No generic abandon: tombstones are irreversible, so 'abandon' could only remove the marker and accept a permanently divergent history; the recovery is re-erase and resume, and the docs should say that this also erases content re-created during the run. An explicit, audited cancel that records the partial redaction as a redaction revision is the alternative. (b) Apply the plan's graph-blind liveness check to every default-graph target, so redact(None) without a prefix is refused while any node of any graph is live. Changed from decisions.md: **yes**. (b) upgraded from assumption to supported: plan.md:10, committed with the accepted ADR in 2b8ea46d, states the graph-blind rule, and the code comment gives its reason; the working answer becomes 'graph-blind liveness' rather than 'refuse unless ownership can be established'. (a) unchanged; added the plaintext-marker consequence… Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1303).

Canonical owner: [redaction.batches.abort](#q-006).

```g5-question
schema: 1
id: HD-1303
status: open
prompt: Can an unfinished redaction be abandoned, and what may a default-graph target touch?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "(a) No generic abandon: tombstones are irreversible, so 'abandon' could only remove the marker and accept a permanently divergent history; the recovery is re-erase and resume, and the docs should say that this also erases content re-created during the run. An explicit, audited cancel that records the partial redaction as a redaction revision is the alternative. (b) Apply the plan's graph-blind liveness check to every default-graph target, so redact(None) without a prefix is refused while any node of any graph is live."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "(a) No generic abandon: tombstones are irreversible, so 'abandon' could only remove the marker and accept a permanently divergent history; the recovery is re-erase and resume, and the docs should say that this also erases content re-created during the run. An explicit, audited cancel that records the partial redaction as a redaction revision is the alternative. (b) Apply the plan's graph-blind liveness check to every default-graph target, so redact(None) without a prefix is refused while any node of any graph is live."
```

<a id="redaction.tenant.node-history-policy"></a><!-- question identity -->
<a id="HD-1304"></a>
### How is a tenant's node history redacted when nodes live in the tenant's own graph?

[Q · redaction.tenant.node-history-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: F-1305. Record the node's graph in ledger node records (a layout change), or require tenant id prefixes and say so in the redaction docs?
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1304.md](../../experiment/playbook-completion/intent/HD-1304.md) (status assumption. Supported at this pin that node records are addressable only by id prefix (accepted ADR-0013:37), so the documented tenant procedure presupposes tenant-prefixed ids. What a graph-per-tenant tenant with unprefixed ids should get is not settled: the spec promises erasure for exactly that d); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Require tenant id prefixes for ledger-governed tenants and document it next to redact(); for a graph target whose erased nodes left graph-blind node records, return an explicit incomplete result (or refuse) instead of complete=true. Model graph-qualified node records for future history separately; a migration of existing history needs trustworthy provenance, which the genesis did not keep. Changed from decisions.md: **no**. Same choice; added the R290 maintainer statement, the genesis attribution contradiction, the receipt (FR-008) gap and fresh live evidence including the FR-007 divergence. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1304).

Canonical owner: [redaction.tenant.node-history-policy](#HD-1304).

```g5-question
schema: 1
id: redaction.tenant.node-history-policy
status: open
prompt: How is a tenant's node history redacted when nodes live in the tenant's own graph?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Require tenant id prefixes for ledger-governed tenants and document it next to redact(); for a graph target whose erased nodes left graph-blind node records, return an explicit incomplete result (or refuse) instead of complete=true. Model graph-qualified node records for future history separately; a migration of existing history needs trustworthy provenance, which the genesis did not keep.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Require tenant id prefixes for ledger-governed tenants and document it next to redact(); for a graph target whose erased nodes left graph-blind node records, return an explicit incomplete result (or refuse) instead of complete=true. Model graph-qualified node records for future history separately; a migration of existing history needs trustworthy provenance, which the genesis did not keep.
```

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


Audit: Working assumption (agent, unratified): (a) Compare the identity the ledger governs: default-graph node rows for node records (R290), with named-graph node rows either reported as outside node governance or recorded with their graph (linked to HD-1101/1304). (b) A reader takes a redaction epoch that every redaction start and finish advances, checks the marker, reads, and re-checks both; if either changed it refuses or retries. A post-read marker check alone is not sufficient (a whole redaction can complete inside one read); a shared lock or a genuine snapshot are alternatives. Verify additionally needs a coherent cut between its record read and its table read. Changed from decisions.md: **yes**. (b) the mechanism changes: decisions.md left 'epoch validation, locking or snapshots' open and the original reviewed model used a second marker check; the new live probe shows a complete redaction inside one paged read (default page… Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1401).

Canonical owner: [ledger.lifecycle.genesis.shared-ids](#q-led-004).

```g5-question
schema: 1
id: HD-1401
status: open
prompt: "Verification and record readers: node identity and redaction checks"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "(a) Compare the identity the ledger governs: default-graph node rows for node records (R290), with named-graph node rows either reported as outside node governance or recorded with their graph (linked to HD-1101/1304). (b) A reader takes a redaction epoch that every redaction start and finish advances, checks the marker, reads, and re-checks both; if either changed it refuses or retries. A post-read marker check alone is not sufficient (a whole redaction can complete inside one read); a shared lock or a genuine snapshot are alternatives. Verify additionally needs a coherent cut between its record read and its table read."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "(a) Compare the identity the ledger governs: default-graph node rows for node records (R290), with named-graph node rows either reported as outside node governance or recorded with their graph (linked to HD-1101/1304). (b) A reader takes a redaction epoch that every redaction start and finish advances, checks the marker, reads, and re-checks both; if either changed it refuses or retries. A post-read marker check alone is not sufficient (a whole redaction can complete inside one read); a shared lock or a genuine snapshot are alternatives. Verify additionally needs a coherent cut between its record read and its table read."
```

<a id="fhir.ledger"></a><!-- question identity -->
<a id="HD-1501"></a>
### Should a FHIR sync be governed by the ledger?

[Q · fhir.ledger]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: a FHIR sync, rebuild and reinterpret write nodes, labels, properties and edges of the FHIR graph from ObjectScript (`Graph.KG.FHIRGraph`), with no ledger record. Strict mode is enforced only in the Python guard (`iris_vector_graph/ledger/guard.py:75-80`), and `FHIRGraph.cls` never reads `^IVG.Ledger("meta","strict")`, so strict mode does not refuse them. `docs/USER_GUIDE.md:1107-1109` says strict mode refuses writes outside the ledger.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1501.md](../../experiment/playbook-completion/intent/HD-1501.md) (status assumption. No authoritative source decides. The FHIR guide describes a projection that converges on the repository (supports exemption); the user guide and glossary describe strict mode/ledger coverage broadly enough to include it.); decision text [15.md](../../experiment/playbook-uplift/decisions/15.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep decisions.md: the FHIR graph is an external writer of a rebuildable projection at the pin. verify() keeps reporting its rows (never silently 'equal'); strict mode is not a guarantee for FHIR namespaces until FHIR writes are either refused under strict or recorded. Changed from decisions.md: no. Sources confirm the working answer; added that ledger-api.md's exhaustive list is silent on FHIR (not an explicit exemption) and that verify() reads every graph. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1501).

Canonical owner: [fhir.ledger](#HD-1501).

```g5-question
schema: 1
id: fhir.ledger
status: open
prompt: Should a FHIR sync be governed by the ledger?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Keep decisions.md: the FHIR graph is an external writer of a rebuildable projection at the pin. verify() keeps reporting its rows (never silently 'equal'); strict mode is not a guarantee for FHIR namespaces until FHIR writes are either refused under strict or recorded."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Keep decisions.md: the FHIR graph is an external writer of a rebuildable projection at the pin. verify() keeps reporting its rows (never silently 'equal'); strict mode is not a guarantee for FHIR namespaces until FHIR writes are either refused under strict or recorded."
```

<a id="fhir.erase.durable-removal-policy"></a><!-- question identity -->
<a id="HD-1502"></a>
### Should erasing a FHIR graph stop its sync task?

[Q · fhir.erase.durable-removal-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `EraseGraph` keeps the `fhir_graphs` row and sets both watermarks to 0 (`Eraser.cls:1151-1180`). A scheduled `Graph.KG.FHIRGraphSyncTask` keeps running, and its next run re-projects the whole repository into the graph. When the FHIR graph is erased for a tenant (and then to be redacted), the content comes back on the next tick, and redaction refuses a live target.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1502.md](../../experiment/playbook-completion/intent/HD-1502.md) (status supported. Erase of a FHIR graph is a transient content clear that keeps registration (supported: Eraser.cls comment, CHANGELOG 4.1.0, ADR-0015:29, upstream E2E test). Whether a durable tenant removal must also stop the feed is not stated anywhere.); decision text [15.md](../../experiment/playbook-uplift/decisions/15.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Separate transient clear from decommissioning. Ordinary erase keeps registration and task (supported). For durable tenant removal require, as a stated premise, unschedule before erase and no manual sync afterwards, and verify the graph stays empty before redaction; at the pin there is no single-graph deregistration, so 'deregister' is a new command, not an available step. Changed from decisions.md: yes. Status raised to supported for the transient-clear half (ADR-0015:29 and the Eraser comment settle it). Refined the durable-removal half: decisions.md offered 'paused or deregistered', but no single-graph deregistration exists at the pin and an unscheduled graph still accepts manual syncs. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1502).

Canonical owner: [fhir.erase.durable-removal-policy](#HD-1502).

```g5-question
schema: 1
id: fhir.erase.durable-removal-policy
status: open
prompt: Should erasing a FHIR graph stop its sync task?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Separate transient clear from decommissioning. Ordinary erase keeps registration and task (supported). For durable tenant removal require, as a stated premise, unschedule before erase and no manual sync afterwards, and verify the graph stays empty before redaction; at the pin there is no single-graph deregistration, so 'deregister' is a new command, not an available step.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Separate transient clear from decommissioning. Ordinary erase keeps registration and task (supported). For durable tenant removal require, as a stated premise, unschedule before erase and no manual sync afterwards, and verify the graph stays empty before redaction; at the pin there is no single-graph deregistration, so 'deregister' is a new command, not an available step.
```

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


Audit: Working assumption (agent, unratified): Keep decisions.md: erase of a FHIR graph must be serialized with an active sync (take ^IVG.FHIRGraph(graph) and answer busy, or have RunBatch abort when the watermark moved backwards); until then the quiet-sync premise must be explicit for erase. Changed from decisions.md: no. Confirmed by source; added the documented convergence claim as the outcome anchor and the absolute-watermark write as the mechanism of the failure. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1503).

Canonical owner: [fhir.sync.other_writers](#q-plt-017).

```g5-question
schema: 1
id: HD-1503
status: open
prompt: What happens when an erase runs during a FHIR sync?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Keep decisions.md: erase of a FHIR graph must be serialized with an active sync (take ^IVG.FHIRGraph(graph) and answer busy, or have RunBatch abort when the watermark moved backwards); until then the quiet-sync premise must be explicit for erase."
    description: Default assumption.
  - label: erase takes the sync lock and refuses (or waits) while a sync holds it -
    description: ""
  - label: RunBatch compare-and-sets the watermark (WHERE wm = expected) and stops when it went back -
    description: ""
  - label: document that a FHIR graph must be unscheduled and idle before an erase
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Keep decisions.md: erase of a FHIR graph must be serialized with an active sync (take ^IVG.FHIRGraph(graph) and answer busy, or have RunBatch abort when the watermark moved backwards); until then the quiet-sync premise must be explicit for erase."
```

<a id="fhir.sync.recovery-policy"></a><!-- question identity -->
<a id="HD-1504"></a>
### Should one unreadable FHIR resource block its graph's sync?

[Q · fhir.sync.recovery-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: a resource whose body is not JSON, nests deeper than 64 levels, or has more than 10,000 json-link matches makes `ResyncKey` throw (`FHIRGraph.cls:2380-2397`, `:2976-2977`, `:2983-2988`). Its batch rolls back and the watermark stays, so every later sync fails on the same batch and no later change reaches the graph. With the default json links (they include an extension entry) every resource body is read.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1504.md](../../experiment/playbook-completion/intent/HD-1504.md) (status supported. Fail the batch, name the key, keep the watermark, repeat on the next sync (no skip). Stated for the walk limits (FHIR_GRAPH.md:196-199) and for any failed batch (:255-257). The resulting indefinite stall and its recovery are not documented.); decision text [15.md](../../experiment/playbook-uplift/decisions/15.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Failure without advancing the watermark is the documented contract (not a choice to revisit silently). Surface the offending key (already in last_error) and treat the missing recovery procedure (repair/delete the resource, or json_links=[]) as a documentation gap; do not assume silent skips. Changed from decisions.md: yes. Status raised from assumption to supported for the failure semantics: FHIR_GRAPH.md:196-199 (maintainer commit 59286731) explicitly states that a walk limit fails the batch, and :255-257 that a failed batch repeats. Added that a rebuild fails too, and the json_links=[] recovery path. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1504).

Canonical owner: [fhir.sync.recovery-policy](#HD-1504).

```g5-question
schema: 1
id: fhir.sync.recovery-policy
status: open
prompt: Should one unreadable FHIR resource block its graph's sync?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Failure without advancing the watermark is the documented contract (not a choice to revisit silently). Surface the offending key (already in last_error) and treat the missing recovery procedure (repair/delete the resource, or json_links=[]) as a documentation gap; do not assume silent skips.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Failure without advancing the watermark is the documented contract (not a choice to revisit silently). Surface the offending key (already in last_error) and treat the missing recovery procedure (repair/delete the resource, or json_links=[]) as a documentation gap; do not assume silent skips.
```

<a id="access.api_key.admin-policy"></a><!-- question identity -->
<a id="HD-1602"></a>
### Should admin work need a different key from reading?

[Q · access.api_key.admin-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the Cypher HTTP server has one `IVG_API_KEY`. The same value that runs a read also runs `/admin/schema/init`, `/admin/load`, `/admin/indexes/rebuild` and `DELETE /admin/queries/{id}`, which ends any IRIS process the server's IRIS user may kill.
- Classification: settled by authority, as the playbook arm recorded it (not re-checked here).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1602.md](../../experiment/playbook-completion/intent/HD-1602.md) (status supported. The documented contract is one key for every route. Admin writes, including kill, are disabled only through IVG_READ_ONLY, which also refuses Cypher writes. The privilege of IRIS_USERNAME bounds what the server can do. A separate admin credential has never been specified.); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Model the single key and the IRIS user's privileges as the authorization surface. Treat an admin-only key or a kill route that is off by default as a proposed strengthening. Record IVG_READ_ONLY as the existing, coarse lever. Changed from decisions.md: **yes**. Status moves from assumption to supported. ADMIN_API and ADMIN_GUIDE (4.6.0) explicitly document one key on every route and the read-only lever. decisions.md did not cite IVG_READ_ONLY. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1602).

Canonical owner: [access.api_key.admin-policy](#HD-1602).

```g5-question
schema: 1
id: access.api_key.admin-policy
status: open
prompt: Should admin work need a different key from reading?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Model the single key and the IRIS user's privileges as the authorization surface. Treat an admin-only key or a kill route that is off by default as a proposed strengthening. Record IVG_READ_ONLY as the existing, coarse lever.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Model the single key and the IRIS user's privileges as the authorization surface. Treat an admin-only key or a kill route that is off by default as a proposed strengthening. Record IVG_READ_ONLY as the existing, coarse lever.
```

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


Audit: Working assumption (agent, unratified): Retry a read, or a write known not to have executed (a connection error raised before the statement was sent). Never re-run a write whose outcome is unknown; return an error that says the outcome is unknown. A write carrying a verified idempotency key may be retried. Changed from decisions.md: **no**. Same direction as decisions.md. New history evidence (9c683292 to 7d62dbf5) and a live duplicate write strengthen it. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1603).

Canonical owner: [access.retries](#q-plt-019).

```g5-question
schema: 1
id: HD-1603
status: open
prompt: Should the Cypher HTTP server run a failed query a second time?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Retry a read, or a write known not to have executed (a connection error raised before the statement was sent). Never re-run a write whose outcome is unknown; return an error that says the outcome is unknown. A write carrying a verified idempotency key may be retried.
    description: Default assumption.
  - label: retry every query once [as built] -
    description: ""
  - label: never retry; return the error
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Retry a read, or a write known not to have executed (a connection error raised before the statement was sent). Never re-run a write whose outcome is unknown; return an error that says the outcome is unknown. A write carrying a verified idempotency key may be retried.
```

<a id="access.surfaces.rest-meta-policy"></a><!-- question identity -->
<a id="HD-1604"></a>
### Should the REST dispatcher's `/metaPath` take a graph?

[Q · access.surfaces.rest-meta-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `/vectorSearch` and `/hybridSearch` gained a `graph` field (spec 230 FR-014); `/metaPath` has none and always walks the default graph (`iris_src/src/Graph/KG/Service.cls:304-319`), though `Traversal.BFSJSON` accepts one.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1604.md](../../experiment/playbook-completion/intent/HD-1604.md) (status assumption. Default-graph-only is consistent with the general rule that an omitted graph means the default graph. No source requires /metaPath to take a graph, and spec 230, which the search routes cite, is not available. Accepting `graph` would be a compatible extension. Ignoring a supplied `graph`); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Treat /metaPath as default-graph-only and include that in its contract. A body naming `graph` should be refused or honoured, not ignored; until decided, model the silent ignore as the baseline. Changed from decisions.md: **no**. Same reading. Added: spec 230 is absent from the repository and the mirror, and a supplied graph key is ignored silently. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1604).

Canonical owner: [access.surfaces.rest-meta-policy](#HD-1604).

```g5-question
schema: 1
id: access.surfaces.rest-meta-policy
status: open
prompt: Should the REST dispatcher's `/metaPath` take a graph?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat /metaPath as default-graph-only and include that in its contract. A body naming `graph` should be refused or honoured, not ignored; until decided, model the silent ignore as the baseline.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat /metaPath as default-graph-only and include that in its contract. A body naming `graph` should be refused or honoured, not ignored; until decided, model the silent ignore as the baseline.
```

<a id="access.webapp.generated-limits-policy"></a><!-- question identity -->
<a id="HD-1605"></a>
### Should the generated GraphQL server match the sample API's safety limits?

[Q · access.webapp.generated-limits-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `iris_vector_graph.gql.create_app` has the key gate but no depth limit (its `Node.outgoing` -> `Relationship.node` -> `Node.outgoing` nests without bound), no read-only middleware (only its `cypher` field checks), and a health route that always answers healthy (F-1611). The sample API has `QueryDepthLimiter` with `IVG_GRAPHQL_MAX_DEPTH`.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1605.md](../../experiment/playbook-completion/intent/HD-1605.md) (status assumption. Undecided between (a) a developer server and (b) parity. The 4.6.0 releases already apply the shared HTTP gates (key, read-only) to create_app and fix its schema reading. That treats it as a deployable surface and makes (b) the better-supported direction. No source requires the depth lim); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Treat both apps as supported entry points subject to the shared HTTP safety constraints: key gate and read-only (already applied), a depth bound, and an honest health check. Record the generated app's missing depth limit and always-healthy /health as gaps against that parity, not as violations of a stated contract. Changed from decisions.md: **yes**. Partial change. decisions.md left the choice open between 'distinct entry points' and parity. R097, R107 and R079 show the maintainer already hardening create_app as a deployable app, so parity (b) is now the working direction. decisions.md also used 'sample' for the app the maintainer calls the development app. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1605).

Canonical owner: [access.webapp.generated-limits-policy](#HD-1605).

```g5-question
schema: 1
id: access.webapp.generated-limits-policy
status: open
prompt: Should the generated GraphQL server match the sample API's safety limits?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Treat both apps as supported entry points subject to the shared HTTP safety constraints: key gate and read-only (already applied), a depth bound, and an honest health check. Record the generated app's missing depth limit and always-healthy /health as gaps against that parity, not as violations of a stated contract."
    description: Default assumption.
  - label: a developer server and
    description: ""
  - label: parity. The 4.6.0 releases already apply the shared HTTP gates (key, read-only) to create_app and fix its schema reading. That treats it as a deployable surface
    description: parity. The 4.6.0 releases already apply the shared HTTP gates (key, read-only) to create_app and fix its schema reading. That treats it as a deployable surface and makes
  - label: |-
      the better-supported direction. No source requires the depth lim); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
      - Owner: the maintai
    description: |-
      the better-supported direction. No source requires the depth lim); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
      - Owner: the maintainer (a human decision; no human has decided it).
      - Not yet compared with the guidance arm's questions
  - label: is now the working direction. decisions.md also used 'sample' for the app the maintainer calls the development app. Options/implications and settling evidence r
    description: is now the working direction. decisions.md also used 'sample' for the app the maintainer calls the development app. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1605)
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Treat both apps as supported entry points subject to the shared HTTP safety constraints: key gate and read-only (already applied), a depth bound, and an honest health check. Record the generated app's missing depth limit and always-healthy /health as gaps against that parity, not as violations of a stated contract."
```

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


Audit: Working assumption (agent, unratified): Keep decisions.md: read_only=True is a requested guarantee; enforce it at a trusted boundary (refuse non-SELECT before it runs) or refuse/remove the unsupported flag in a versioned change. The engine's own use (reads only) makes enforcement compatible with internal callers. Changed from decisions.md: no. Live probe confirms the flag is ignored; added the protocol's raise-not-approximate rule as supporting evidence and the misreported-error observation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1701).

Canonical owner: [access.read_only.scope](#q-plt-012).

```g5-question
schema: 1
id: HD-1701
status: open
prompt: Should the SQL adapter's pass-through refuse a write when called read-only?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Keep decisions.md: read_only=True is a requested guarantee; enforce it at a trusted boundary (refuse non-SELECT before it runs) or refuse/remove the unsupported flag in a versioned change. The engine's own use (reads only) makes enforcement compatible with internal callers."
    description: Default assumption.
  - label: "enforce: refuse a non-SELECT statement with a clear error before it runs -"
    description: ""
  - label: remove the parameter from the protocol and the adapter -
    description: ""
  - label: keep as documentation only and say so
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Keep decisions.md: read_only=True is a requested guarantee; enforce it at a trusted boundary (refuse non-SELECT before it runs) or refuse/remove the unsupported flag in a versioned change. The engine's own use (reads only) makes enforcement compatible with internal callers."
```

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


Audit: Working assumption (agent, unratified): Keep decisions.md: after an ambiguous outcome resend only a known read or an explicitly idempotent operation; report an unknown outcome otherwise; treat client and server retries as one protocol. Note that this narrows a documented feature (compatibility decision). Changed from decisions.md: no. Probe confirms; added that the retry itself is a documented maintainer feature (so the working answer is a narrowing, not a bug fix) and that statement failures are 400 and not retried. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1702).

Canonical owner: [access.retries](#q-plt-019).

```g5-question
schema: 1
id: HD-1702
status: open
prompt: Should the HTTP client resend a write query after a server error?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Keep decisions.md: after an ambiguous outcome resend only a known read or an explicitly idempotent operation; report an unknown outcome otherwise; treat client and server retries as one protocol. Note that this narrows a documented feature (compatibility decision)."
    description: Default assumption.
  - label: retry only reads (client cannot tell; the server could mark replies) -
    description: ""
  - label: retry only connect errors raised before the request was sent; never 5xx or timeouts -
    description: ""
  - label: keep retrying everything and document that writes must be idempotent (MERGE) or carry a ledger retry key
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Keep decisions.md: after an ambiguous outcome resend only a known read or an explicitly idempotent operation; report an unknown outcome otherwise; treat client and server retries as one protocol. Note that this narrows a documented feature (compatibility decision)."
```

<a id="algorithms.routing.capability-policy"></a><!-- question identity -->
<a id="HD-1703"></a>
### Should the SQL adapter's capability list say what this namespace can run?

[Q · algorithms.routing.capability-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `IRISGraphStore.capabilities()` returns `_FULL_CAPABILITIES`, every algorithm `True`, whether or not the ObjectScript classes are deployed or the accelerator is loaded; only the `*_arno` keys vary (`iris_vector_graph/stores/iris_sql_store.py:29-52`, `:2991-3000`). The engine uses it to choose store calls over Python fallbacks.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1703.md](../../experiment/playbook-completion/intent/HD-1703.md) (status assumption. Undocumented. The product keeps two facts: engine.capabilities (documented: what is deployed) and store.capabilities() (undocumented: what the adapter implements).); decision text [17.md](../../experiment/playbook-uplift/decisions/17.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep decisions.md: code support and namespace availability are different facts; treat store.capabilities() as a static catalogue (document it as such) and do not read it as availability; routing that needs availability uses engine.capabilities/status() or an explicit fallback. Changed from decisions.md: no. Probe and source confirm; added that the product already separates the facts (engine.capabilities, a06e1f50) so option (b) is the existing design, missing only documentation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1703).

Canonical owner: [algorithms.routing.capability-policy](#HD-1703).

Iteration 52 evidence (additive): on the continuation fixture with classes deployed and no Arno library, `IRISGraphStore.capabilities()` answered every algorithm True and no `*_arno` key. Meanwhile `engine.capabilities`, the documented report of what is deployed, read `kg_built` and `nkg_built` False on a namespace set up while empty, even after `sync()` ([bug-plt-117](bugs_issues.md#bug-plt-117)). So neither capability object is a live availability report today; `status()` is ([install.status.capabilities](../ontology/concepts/install.g5.md#install.status.capabilities), [probe](../uplift/consolidated/iteration-52/reports-observed-20261117T041241Z.json) `s17_default_arno`). The working assumption is unchanged.

```g5-question
schema: 1
id: algorithms.routing.capability-policy
status: open
prompt: Should the SQL adapter's capability list say what this namespace can run?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Keep decisions.md: code support and namespace availability are different facts; treat store.capabilities() as a static catalogue (document it as such) and do not read it as availability; routing that needs availability uses engine.capabilities/status() or an explicit fallback."
    description: Default assumption.
  - label: is the existing design, missing only documentation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/q
    description: is the existing design, missing only documentation. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1703)
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Keep decisions.md: code support and namespace availability are different facts; treat store.capabilities() as a static catalogue (document it as such) and do not read it as availability; routing that needs availability uses engine.capabilities/status() or an explicit fallback."
```

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


Audit: Working assumption (agent, unratified): The product contract at the pin is ADMIN_GUIDE section 5's open default; F-1709 is a documentation defect against deploy/README.md:86 (registered as fail against that stated text). For the reviewed deployment, keep local-only binding or an explicit opt-in for unauthenticated external binding as a stated premise, not as the product's intent. Changed from decisions.md: yes. decisions.md kept both contradictory contracts open; commit 6df261d9/R032 makes ADMIN_GUIDE the single operator document and git history shows --force-no-auth was never implemented on any branch, so the open default is the current contract and the hardening is a deployment premise. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1705).

Canonical owner: [access.defaults.exposure](#q-plt-003).

```g5-question
schema: 1
id: HD-1705
status: open
prompt: Should server start refuse to listen on every address without an API key?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: The product contract at the pin is ADMIN_GUIDE section 5's open default; F-1709 is a documentation defect against deploy/README.md:86 (registered as fail against that stated text). For the reviewed deployment, keep local-only binding or an explicit opt-in for unauthenticated external binding as a stated premise, not as the product's intent.
    description: Default assumption.
  - label: "implement the refusal: bind 127.0.0.1 or exit unless a key or an explicit flag -"
    description: ""
  - label: keep the open default and correct deploy/README.md (and compose.yml's unread IVG_AUTH_MODE)
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: The product contract at the pin is ADMIN_GUIDE section 5's open default; F-1709 is a documentation defect against deploy/README.md:86 (registered as fail against that stated text). For the reviewed deployment, keep local-only binding or an explicit opt-in for unauthenticated external binding as a stated premise, not as the product's intent.
```

<a id="install.snapshot.consistency-policy"></a><!-- question identity -->
<a id="HD-1802"></a>
### Should a snapshot be a point-in-time view?

[Q · install.snapshot.consistency-policy]

Severity: Unranked · Decision: Open

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `save_snapshot` reads each table, then each global, one after another, with no transaction, lock or ledger head check (`snapshot.py:864-1034`). Writes that land during a save can appear in one store and not another (a row without its vector, a ledger head ahead of the rows). The guides describe a snapshot as a copy "of every graph's rows and globals" without saying when.
- Classification: needs ratification (the playbook arm's working assumption).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1802.md](../../experiment/playbook-completion/intent/HD-1802.md) (status none); decision text [18.md](../../experiment/playbook-uplift/decisions/18.md).
- Owner: the maintainer (a human decision; no human has decided it).
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Claim a consistent snapshot only when writers are quiescent (an operator premise) or under a verified snapshot/epoch protocol; for the current exporter declare the quiet-writer premise. Changed from decisions.md: **no**. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#HD-1802).

Canonical owner: [install.snapshot.consistency-policy](#HD-1802).

```g5-question
schema: 1
id: install.snapshot.consistency-policy
status: open
prompt: Should a snapshot be a point-in-time view?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Claim a consistent snapshot only when writers are quiescent (an operator premise) or under a verified snapshot/epoch protocol; for the current exporter declare the quiet-writer premise.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Claim a consistent snapshot only when writers are quiescent (an operator premise) or under a verified snapshot/epoch protocol; for the current exporter declare the quiet-writer premise.
```

<a id="erasure.scope.embedding-queue-policy"></a><!-- question identity -->
<a id="REACH-1"></a>
### Should erasure and redaction reach the store in REACH-1?

[Q · erasure.scope.embedding-queue-policy]

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B95: A graph erasure or a node erasure leaves the queued embedding requests of the erased nodes in place. So does erasing everything. / ERS-B95: A graph erasure or a node erasure leaves the queued embedding requests of the erased nodes in place. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#REACH-1).

Canonical owner: [erasure.scope.embedding-queue-policy](#REACH-1).

```g5-question
schema: 1
id: erasure.scope.embedding-queue-policy
status: open
prompt: Should erasure and redaction reach the store in REACH-1?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
```

<a id="REACH-2"></a>
### Should erasure and redaction reach the store in REACH-2?

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B96: A graph erasure or a node erasure leaves the table of documents that an upgrade could not place in a graph. So does erasing everything. / ERS-B96: A graph erasure or a node erasure leaves the table of documents that an upgrade could not place in a graph. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#REACH-2).

Canonical owner: [search.quarantine.retention](#q-srch-001).

```g5-question
schema: 1
id: REACH-2
status: open
prompt: Should erasure and redaction reach the store in REACH-2?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
```

<a id="REACH-3"></a>
### Should erasure and redaction reach the store in REACH-3?

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B97: A graph erasure or a node erasure leaves the table of vectors of edges that an upgrade could not place in a graph. So does erasing everything. / ERS-B97: A graph erasure or a node erasure leaves the table of vectors of edges that an upgrade could not place in a graph. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#REACH-3).

Canonical owner: [search.quarantine.retention](#q-srch-001).

```g5-question
schema: 1
id: REACH-3
status: open
prompt: Should erasure and redaction reach the store in REACH-3?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
```

<a id="erasure.kept.snapshot-retention-policy"></a><!-- question identity -->
<a id="REACH-4"></a>
### Should erasure and redaction reach the store in REACH-4?

[Q · erasure.kept.snapshot-retention-policy]

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B98: A graph erasure or a node erasure only marks the saved copy of the default graph as old. The copy stays until one of the three calls that read it builds a new one. Erasing everything removes it. / ERS-B98: A graph erasure or a node erasure only marks the saved copy of the default graph as old. The copy stays until one of the three calls that read it builds a new one. Erasing everything removes it.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#REACH-4).

Canonical owner: [erasure.kept.snapshot-retention-policy](#REACH-4).

```g5-question
schema: 1
id: erasure.kept.snapshot-retention-policy
status: open
prompt: Should erasure and redaction reach the store in REACH-4?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
```

<a id="erasure.scope.legacy-backup-policy"></a><!-- question identity -->
<a id="REACH-5"></a>
### Should erasure and redaction reach the store in REACH-5?

[Q · erasure.scope.legacy-backup-policy]

Severity: Unranked · Decision: Open

Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)

- Today: ERS-B99: A graph erasure or a node erasure leaves the two tables where an upgrade from version 3.2 kept copies of edges. So does erasing everything. / ERS-B99: A graph erasure or a node erasure leaves the two tables where an upgrade from version 3.2 kept copies of edges. So does erasing everything.
- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md](../../experiment/playbook-completion/STATUS.md)).
- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Working assumption (agent, unratified): Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph. Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#REACH-5).

Canonical owner: [erasure.scope.legacy-backup-policy](#REACH-5).


## Settled by existing sources

```g5-question
schema: 1
id: erasure.scope.legacy-backup-policy
status: open
prompt: Should erasure and redaction reach the store in REACH-5?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.
```

<a id="HD-0001"></a>
### How to read "defined by its ancestors or an earlier same-level statement"

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the playbook's definitions-first rule, read literally, forbids a child from using a term its parent's earlier sibling defined. The uplift reads it as lexical scope (ancestors, and earlier siblings of the statement or of any ancestor). Accept this reading, or require literal ancestry?
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: lexical scope (`tools/ontology_index.py`, `in_scope`). ## Decisions from the worked example (modules ERS, RED, RPL).
- Intent recovery: [intent/HD-0001.md](../../experiment/playbook-completion/intent/HD-0001.md) (status supported(literal reading) · Confidence: high · Changed from decisions.md: no); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. Method definitions use the literal parent-chain/earlier-same-parent rule. This is a workflow question, not a product contract. [Sources and history](audits/register-20261115/question-review.md#HD-0001).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-0001
status: answered
prompt: How to read "defined by its ancestors or an earlier same-level statement"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Method definitions use the literal parent-chain/earlier-same-parent rule. This is a workflow question, not a product contract.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Method definitions use the literal parent-chain/earlier-same-parent rule. This is a workflow question, not a product contract.
```

<a id="HD-0202"></a>
### In a multigraph, does a direct edge delete remove one parallel edge or all of them?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `delete_edge(s, p, o, graph=g)` deletes every row of the triple in `g` (iris_vector_graph/_engine/nodes_edges.py:1429-1433). Spec 234 gives the direct API `create_edge` a multigraph rule (FR-007) and Cypher `DELETE r` a per-edge rule (US1 scenario 2), but says nothing about `delete_edge`.
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0202.md](../../experiment/playbook-completion/intent/HD-0202.md) (status supported· Confidence: medium · Changed from decisions.md: yes (decisions.md said spec 234 leaves the direct delete ambiguous, and so marked it an assumption. The spec's plan.md:160-162 addresses delete_edge explicitly and names the triple-wide meaning as the no-edge_id contract, so the status is no); decision text [02.md](../../experiment/playbook-uplift/decisions/02.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. Without an edge ID, direct delete_edge removes the whole triple. A per-edge ID argument is planned, absent at the pin. [Sources and history](audits/register-20261115/question-review.md#HD-0202).

Canonical owner: [structure.edge.delete](../ontology/features/graph-structure.g5.md#structure.edge.delete).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-0202
status: answered
prompt: In a multigraph, does a direct edge delete remove one parallel edge or all of them?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Without an edge ID, direct delete_edge removes the whole triple. A per-edge ID argument is planned, absent at the pin.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Without an edge ID, direct delete_edge removes the whole triple. A per-edge ID argument is planned, absent at the pin.
```

<a id="HD-0301"></a>
### Does ledger strict mode cover the standalone bulk loader?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: strict mode refuses the engine's direct writes (docs/USER_GUIDE.md:1107-1121) through a check in each engine method (`ledger_check`, iris_vector_graph/_engine/ledger.py:72-79). `iris_vector_graph.bulk_loader.BulkLoader` takes a DB-API connection, not an engine, and has no such check (bulk_loader.py:56-78, 252-272, 380-402), so it writes nodes, labels, properties and edges with no ledger record while strict mode is on. Is that intended?
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-0301.md](../../experiment/playbook-completion/intent/HD-0301.md) (status supported· Confidence: high · Changed from decisions.md: no (Same status and reading. Added the contradiction that the promised documentation of the exclusion is missing from the user guides.)); decision text [03.md](../../experiment/playbook-uplift/decisions/03.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. The standalone BulkLoader and raw SQL are expressly outside the client strict-mode guard. That exception does not exempt other engine writers. [Sources and history](audits/register-20261115/question-review.md#HD-0301).

Canonical owner: [install.bulk_load.ledger](../ontology/concepts/install.g5.md#install.bulk_load.ledger).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-0301
status: answered
prompt: Does ledger strict mode cover the standalone bulk loader?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: The standalone BulkLoader and raw SQL are expressly outside the client strict-mode guard. That exception does not exempt other engine writers.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: The standalone BulkLoader and raw SQL are expressly outside the client strict-mode guard. That exception does not exempt other engine writers.
```

<a id="HD-1002"></a>
### Should label propagation say when its labels did not settle?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `kg_CDLP` returns the last round's labels after `max_iterations`, and labels often swap every round (`docs/COMMUNITIES.md:192-208`); `kg_WCC` and `eigenvector_centrality` raise when they do not converge.
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1002.md](../../experiment/playbook-completion/intent/HD-1002.md) (status supported. The current public contract is option (c): a fixed-iteration synchronous CDLP that returns the last round with no in-band signal. The documented diagnostic is to compare k with k+1. The maintainer documented this deliberately (af2bc84e W6). A settledness flag would be a compatible strengt); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. CDLP returns its last fixed iteration without an in-band settledness flag; the documented diagnostic compares k with k+1. [Sources and history](audits/register-20261115/question-review.md#HD-1002).

Canonical owner: [algorithms.op.cdlp](../ontology/features/algorithms.g5.md#algorithms.op.cdlp).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-1002
status: answered
prompt: Should label propagation say when its labels did not settle?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: CDLP returns its last fixed iteration without an in-band settledness flag; the documented diagnostic compares k with k+1.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: CDLP returns its last fixed iteration without an in-band settledness flag; the documented diagnostic compares k with k+1.
```

<a id="HD-1004"></a>
### How many nodes should global PageRank list?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: the ObjectScript owner stops at 10,000 rows; the native reader lists every node (F-1003). The method takes no top-k, and the docs promise neither.
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1004.md](../../experiment/playbook-completion/intent/HD-1004.md) (status supported. (a): every node of the default graph is listed on every route, and the scores sum to 1 over node_count(). The 4.6.0 R306 docstring (a node with no edge used to have 'no pair') and spec 236's same-node-set rule settle it. The 10,000 cap is an undocumented 2026-03 leftover.); decision text [10.md](../../experiment/playbook-uplift/decisions/10.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. Global PageRank promises every default-graph node on every supported route; the hidden Owner output cap violates that documented contract. [Sources and history](audits/register-20261115/question-review.md#HD-1004).

Canonical owner: [algorithms.op.pagerank](../ontology/features/algorithms.g5.md#algorithms.op.pagerank).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-1004
status: answered
prompt: How many nodes should global PageRank list?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Global PageRank promises every default-graph node on every supported route; the hidden Owner output cap violates that documented contract.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Global PageRank promises every default-graph node on every supported route; the hidden Owner output cap violates that documented contract.
```

<a id="HD-1302"></a>
### Which rule clears a revision's free text: any tombstone or every record?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: F-1301. The code and ADR-0013 follow Decision 2 (any). Amend spec 256 FR-004?
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1302.md](../../experiment/playbook-completion/intent/HD-1302.md) (status supported. Clear the free text of any revision with at least one redacted record (Decision 2, accepted ADR-0013). FR-004's 'every' and acceptance scenario 2's wording are stale.); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. Decision 2 clears the free text when any record in the revision is tombstoned. The older every-record wording is stale. [Sources and history](audits/register-20261115/question-review.md#HD-1302).

Canonical owner: [redaction.metadata](../ontology/features/redaction.g5.md#redaction.metadata).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-1302
status: answered
prompt: "Which rule clears a revision's free text: any tombstone or every record?"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Decision 2 clears the free text when any record in the revision is tombstoned. The older every-record wording is stale.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Decision 2 clears the free text when any record in the revision is tombstoned. The older every-record wording is stale.
```

<a id="HD-1305"></a>
### Should a replayed commit apply its post-commit properties?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: F-1306 / F-1101. A replay currently re-applies them, which can revive erased content between erasure and redaction.
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1305.md](../../experiment/playbook-completion/intent/HD-1305.md) (status supported. Supported: a replay returns the original outcome and applies nothing (spec 213 API contract, upstream test), and a retry must not re-create an erased tenant (ADR-0013:15, spec 256 edge case). The mechanism (skip on replayed=True, or record durable completion of post-commit writes) is not ); decision text [DECISIONS.md](../../experiment/playbook-uplift/DECISIONS.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Related here: q-010 (related, not the same question).

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. A keyed replay returns the original outcome and applies no new effects. How to complete or skip post-commit work is an implementation question; recording those properties remains separately open. [Sources and history](audits/register-20261115/question-review.md#HD-1305).

Canonical owner: [ledger.idempotency](../ontology/features/ledger.g5.md#ledger.idempotency).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-1305
status: answered
prompt: Should a replayed commit apply its post-commit properties?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: A keyed replay returns the original outcome and applies no new effects. How to complete or skip post-commit work is an implementation question; recording those properties remains separately open.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: A keyed replay returns the original outcome and applies no new effects. How to complete or skip post-commit work is an implementation question; recording those properties remains separately open.
```

<a id="HD-1601"></a>
### Should a server limit which graphs a caller may name?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: every interface uses whatever graph a caller names (GraphQL `graph:`, the FHIR event `graph` field, the REST dispatcher's `graph`, `USE GRAPH` in Cypher over HTTP, Bolt and MCP). The docs say a graph ID is not a security boundary and tenants need separate namespaces (`docs/USER_GUIDE.md:467-468`, `docs/FHIR_GRAPH.md:553-556`), while `CONTEXT.md:248-250` plans an Execution Context that binds a session to one graph, and spec 256 models a tenant as a named graph plus an id prefix inside one namesp…
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1601.md](../../experiment/playbook-completion/intent/HD-1601.md) (status supported. The IRIS namespace is the only isolation and authorization boundary. Graph ids scope data operations and confer no authorization. The Execution Context is a planned guard against accidental cross-graph writes, not an access-control feature.); decision text [16.md](../../experiment/playbook-uplift/decisions/16.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. The namespace is the authorization boundary; graph IDs scope data operations and do not confer access rights. [Sources and history](audits/register-20261115/question-review.md#HD-1601).

Canonical owner: [access.graph_id](../ontology/concepts/access.g5.md#access.graph_id).

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-1601
status: answered
prompt: Should a server limit which graphs a caller may name?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: The namespace is the authorization boundary; graph IDs scope data operations and do not confer access rights.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: The namespace is the authorization boundary; graph IDs scope data operations and do not confer access rights.
```

<a id="HD-1704"></a>
### Should the low-level vector helper refuse a vector of the wrong width?

Severity: Unranked

Run: Playbook uplift, decisions for the human (imported 2026-11-14)

- Question: `dbapi_utils.normalize_vector` pads a short vector with zeros, truncates a long one and turns NaN/Inf into 0.0 (logged only under `IRIS_VECTOR_DEBUG`); `insert_vector` then writes it (`iris_vector_graph/dbapi_utils.py:29-98`). The engine's own writers refuse a width mismatch (ADR-0006, `EmbeddingIdentityConflict`). Which rule do the public helpers follow?
- Classification: settled by authority, as the playbook arm recorded it (re-checked against the pin in this audit).
- Working answer: see the intent file.
- Intent recovery: [intent/HD-1704.md](../../experiment/playbook-completion/intent/HD-1704.md) (status supported. The helper contract is lossy coercion (docstring); registry-aware engine writes are strict (ADR-0006). Two boundaries, both stated.); decision text [17.md](../../experiment/playbook-uplift/decisions/17.md).
- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.
- Not yet compared with the guidance arm's questions.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit resolution: **settled by existing authority at the pin**, not new maintainer approval. The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract. [Sources and history](audits/register-20261115/question-review.md#HD-1704).

Canonical owner: [search.embedding.width.raw-helpers](../ontology/features/search.g5.md#search.embedding.width.raw-helpers).


## Historical reports and qualified proof debt

Disposition: resolved with existing authority. See the linked source audit.

```g5-question
schema: 1
id: HD-1704
status: answered
prompt: Should the low-level vector helper refuse a vector of the wrong width?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract.
    description: Default assumption.
answer:
  selected: []
  text: resolved with existing authority. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract.
```

<a id="hist-012"></a>
### Upstream #12: bulk-created nodes had no id property, so directed patterns from {id: ...} found nothing (4.4.2)

Severity: Unranked

Settled as built: `CHANGELOG.md:59-60` records it fixed in 4.6.0 (R089) and checked again for 4.7.0; at the pin `create_node` sets `props["id"]` (`_engine/nodes_edges.py:1057`) and `bulk_create_nodes` (`:1648`) feeds the server loader `Graph.KG.EdgeScan.BulkIngestNodesSQL`. Not re-observed here (no IRIS). Planned use as the control of a writer-path model (reviewed plan F1); not built in this consolidation.


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#hist-012).

Disposition: closed in this policy register; historical fixed-at-pin report. See the linked source audit.

```g5-question
schema: 1
id: hist-012
status: answered
prompt: "Upstream #12: bulk-created nodes had no id property, so directed patterns from {id: ...} found nothing (4.4.2)"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; historical fixed-at-pin report. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="hist-013"></a>
### Upstream #13: count(DISTINCT) with ORDER BY and LIMIT failed on a from_connect() engine on IRIS 2026.1 (4.5.1)

Severity: Unranked

Settled as built: `CHANGELOG.md:52-58` records the fix in 4.7.0: the `from_connect()` probe also tries the aggregate shape and answers with TOP when it is refused (`engine.py::_detect_fetch_first_unsafe`, `:772`). Not re-observed here. Planned use as the control of a row-limit selector model (reviewed plan F2); not built in this consolidation.


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#hist-013).

Disposition: closed in this policy register; historical fixed-at-pin report. See the linked source audit.

```g5-question
schema: 1
id: hist-013
status: answered
prompt: "Upstream #13: count(DISTINCT) with ORDER BY and LIMIT failed on a from_connect() engine on IRIS 2026.1 (4.5.1)"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; historical fixed-at-pin report. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-1"></a>
### Proof debt D-1: L1/L2 refinement proofs for every module with operations: **paid at model level** for 01-11 and 15-18 (`proofs-breadth`, `proofs-d1b`..`proofs-d1f`, 94+92+111+118+115+115 verified,

Severity: Unranked

- all modules | — | the code-to-model link is D-2/D-3 |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-1).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-1
status: answered
prompt: "Proof debt D-1: L1/L2 refinement proofs for every module with operations: **paid at model level** for 01-11 and 15-18 (`proofs-breadth`, `proofs-d1b`..`proofs-d1f`, 94+92+111+118+115+115 verified,"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-2"></a>
### Proof debt D-2: Statement lemmas: each IRIS SQL statement and ObjectScript global operation equals its model evaluation (§3.4)

Severity: Unranked

- every writer and reader | journal-validated footprints (breadth lanes, `trace-conformance-ledger`), source inspection | no Verus frontend or IRIS SQL semantics library exists (PGspec is PostgreSQL and is skipped). The IRIS contract now has a Verus specification for its subset (`proofs-env`, `proofs-env2`, D-7), so a statement program can be proved against it once hand-translated; what this experiment did not provide is automated source-level verification of the product's ObjectScript/Python (no supported frontend was integrated here), so the translation is a trusted step to be checked against…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-2).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-2
status: answered
prompt: "Proof debt D-2: Statement lemmas: each IRIS SQL statement and ObjectScript global operation equals its model evaluation (§3.4)"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-3"></a>
### Proof debt D-3: Handler proofs: each Python/ObjectScript entry point performs its spec step (§3.5)

Severity: Unranked

- all handlers | trace conformance of one two-tenant scenario; correspondence lane's map and unchecked-line list (`correspondence/`) | no automated source-level verification of the ObjectScript/Python handlers in this experiment (no supported frontend integrated here) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-3).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-3
status: answered
prompt: "Proof debt D-3: Handler proofs: each Python/ObjectScript entry point performs its spec step (§3.5)"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-4"></a>
### Proof debt D-4: Lock-plan obligations per handler (§3.5)

Severity: Unranked

- writers of modules 11-14 and AdjW users | controlled lock probes and journal order; IRIS contract lock clauses | as D-3; F-1201 shows the eraser's plan is incomplete at the pin. Lane `lockplans` (modules 01, 05, 06, 08, 10, 16, 17) stopped at the finish request: explorer models 46/46 in 5 families (`lockplans-mc-*`, `lockplans-control-*`), live `lockplans-08-17-guarded-insert` (+`-r3`) with candidate findings F-C0811/F-C1711 not yet filed; probes for 01, 05, 10, 16 not run (`lockplans/PARTIAL.md`, not integrated) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-4).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-4
status: answered
prompt: "Proof debt D-4: Lock-plan obligations per handler (§3.5)"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-5"></a>
### Proof debt D-5: Composition: a committed IRIS transaction refines the serial step, chained over executions (§3.6)

Severity: Unranked

- product | `proofs/` composes participant **contracts**; trace conformance checks committed transactions of one scenario | needs D-2 and D-3 |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-5).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-5
status: answered
prompt: "Proof debt D-5: Composition: a committed IRIS transaction refines the serial step, chained over executions (§3.6)"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-6"></a>
### Proof debt D-6: Frame, key, FK, capacity, row-permutation conditions (§3.6)

Severity: Unranked

- every module | executable checks with self-tests across all modules (structural lane: ownership, storage order, row permutation, keys, FK, capacity probes, a catalog/dictionary frame oracle and a non-interference read oracle; `st-*`), correspondence checks for 11-14 (`corr-*`), CLOSURE.md's condition list | as D-2: no proof over IRIS SQL or ObjectScript |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-6).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-6
status: answered
prompt: "Proof debt D-6: Frame, key, FK, capacity, row-permutation conditions (§3.6)"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-7"></a>
### Proof debt D-7: The IRIS environment contract as a Verus specification linked to the participant contracts: **paid at model level for the contract's Verus subset** by `proofs-env` (305 verified, 0

Severity: Unranked

- environment | executable contract r6 and contract-2 (differential, mutants) | still open: the discipline `disc` against the code (D-3/D-4); 9 clause families outside the Verus subset (X-DDL, X-STAR, X-FX, X-NOINDEX, X-VEC `$VECTOR` set/get, X2-JSON, X2-LIST, X2-TOP, X2-QUERY/MERGE/ZKILL: 513 recorded case runs, exact obligations in proofs-env2/PROOFS.md section 6; no closure premise rests on them); progress premises; several locks / regions not composed into one invariant; the Freedom's proceeding branch unobserved How each part is linked (review A-04): the Verus spec to the executable contra…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-7).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-7
status: answered
prompt: "Proof debt D-7: The IRIS environment contract as a Verus specification linked to the participant contracts: **paid at model level for the contract's Verus subset** by `proofs-env` (305 verified, 0"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-8"></a>
### Proof debt D-8: Progress premises: fair scheduling of enabled steps, operator re-runs after a stop, ledger re-enabled, no write outside the ledger, a weakly fair queue worker (`proofs-mech` M07-L4

Severity: Unranked

- `progress.rs` of `proofs/`, `proofs-d9*`; `proofs-mech` M-07; core models' AG EF | none derived or tested against IRIS scheduling; "no writer makes a marked target live" (P-C02/PF-6) is violated at the pin (F-C1307, F-C1350) | premises, named in `TRUST.md` and `reflection/CLOSURE.md` |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-8).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-8
status: answered
prompt: "Proof debt D-8: Progress premises: fair scheduling of enabled steps, operator re-runs after a stop, ledger re-enabled, no write outside the ledger, a weakly fair queue worker (`proofs-mech` M07-L4"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-9"></a>
### Proof debt D-9: Reviewed protocol under the pin's real premises (bypass writers, three distinct target predicates, erasure rollback, readers, statement history, Decision 2, retry-key movement): **

Severity: Unranked

- erase/redact/replay | explorer core M1-M3 as before | still open: G-BM is a working assumption (whether content re-created outside the ledger is 'live' is a maintainer question; its cost at the pin not assessed); premises P-LV (the liveness check sees every row, violated by F-C1351) and P-D9-3 not modelled; P-D9-5 graph-blind replay, the HD-1304 receipt, P-D9b-3 and the unreproduced mixed-revision case (`proofs-d9b/PROOFS.md` section 10); verify()'s table read, its two-read coherence and node identity (F-1401); readers' progress; post-commit property recovery; F-CS01's reviewed design is inte…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-9).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-9
status: answered
prompt: "Proof debt D-9: Reviewed protocol under the pin's real premises (bypass writers, three distinct target predicates, erasure rollback, readers, statement history, Decision 2, retry-key movement): **"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-10"></a>
### Proof debt D-10: M1 targeting with 2 pre-enable writes and 2 commits: **paid (mc, exhaustive within bounds)** by `models/core-partition`: 43 pieces by pre-enable world whose union is checked to be 

Severity: Unranked

- core models | — | still open: profiles beyond (2,2) and (0,3); M1's small world (3 ids, 2 graphs, 3 edges); the as-built RPL-B3 check not re-run per piece |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-10).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-10
status: answered
prompt: "Proof debt D-10: M1 targeting with 2 pre-enable writes and 2 commits: **paid (mc, exhaustive within bounds)** by `models/core-partition`: 43 pieces by pre-enable world whose union is checked to be "
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-11"></a>
### Proof debt D-11: Original proof `l2.rs` refinement covers the reviewed design only

Severity: Unranked

- modules 12-14 | original 53 verified, 6 controls rejected (submission 9c3719c1) | by design; product violates it (F-1302, F-1303) |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-11).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-11
status: answered
prompt: "Proof debt D-11: Original proof `l2.rs` refinement covers the reviewed design only"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-12"></a>
### Proof debt D-12: Progress-only control for reviewed-design element D-2 (scan bound fixed at marking): **paid at model level**: `control_bound_follows_tail` (the pin's tail-following bound) fails on

Severity: Unranked

- `proofs-d9b/src/progress.rs` | — | the variant needs an attached process to resume to continue; the located failure does not depend on it |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-12).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-12
status: answered
prompt: "Proof debt D-12: Progress-only control for reviewed-design element D-2 (scan bound fixed at marking): **paid at model level**: `control_bound_follows_tail` (the pin's tail-following bound) fails on"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-13"></a>
### Proof debt D-13: The breadth proofs (modules 04 and 11) without premise P-A3: **paid at model level** by `proofs-pa3` (108 verified, 0 errors, `proofs-pa3-baseline`, recheck `proofs-pa3-recheck`): 

Severity: Unranked

- `proofs-pa3/` | — | still open: modules 04 and 11 not composed; one erase at a time; erases inside a caller transaction, EraseNodes/EraseAll, FK rollback and progress under R04-5 not modelled; neither guard exists at the pin |

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-13).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-13
status: answered
prompt: "Proof debt D-13: The breadth proofs (modules 04 and 11) without premise P-A3: **paid at model level** by `proofs-pa3` (108 verified, 0 errors, `proofs-pa3-baseline`, recheck `proofs-pa3-recheck`): "
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="D-14"></a>
### Proof debt D-14: Shared mechanism laws proved once over a trait: **paid at model level** by `proofs-mech` (1,149 verified, 0 errors, `--no-cheating`, empty trust inventory; all 45 laws of 13 mechan

Severity: Unranked

- 13 mechanisms, 45 laws | explorer checks (`sem-mc-*`) alongside | composition **paid at model level** by `proofs-sys` (256 verified, 0 errors, `--no-cheating`, empty trust inventory including the proofs-mech dependency, `proofs-sys-baseline`, recheck `proofs-sys-recheck`): the 12 module-00 axiom checks proved once over a design trait whose parameters are the instance choices of M-01, M-02, M-03, M-04, M-05 and M-10 (all 3,072 choice vectors meeting each obligation); 12 located controls, the pin's as-built composition breaking AX-06, AX-07, AX-08, AX-10, AX-11 and AX-11M, each control's broken…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#D-14).


Public-report qualification: upstream issues #12 and #13 were still open when checked. Fixed-at-pin here refers to the pinned changelog and preserved regression evidence, not a GitHub issue closure or a new maintainer approval. See [public source snapshot](audits/register-20261115/upstream.json).

Disposition: closed in this policy register; inherited qualified proof debt. See the linked source audit.

```g5-question
schema: 1
id: D-14
status: answered
prompt: "Proof debt D-14: Shared mechanism laws proved once over a trait: **paid at model level** by `proofs-mech` (1,149 verified, 0 errors, `--no-cheating`, empty trust inventory; all 45 laws of 13 mechan"
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Keep the existing recorded scope; no new verification or human decision is inferred.
    description: Default assumption.
answer:
  selected: []
  text: closed in this policy register; inherited qualified proof debt. See the linked source audit.
  rationale: Existing source authority recorded in this register.
  answered_by: null
  answered_at: null
default_assumption: Keep the existing recorded scope; no new verification or human decision is inferred.
```

<a id="access.transactions"></a>
### Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning?

[Q · access.transactions]

Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning? There is no provisional answer. Plausible answers: map explicit transactions onto one IVG transaction, or refuse explicit transactions and document per-statement commits.

- Today Bolt's begin, commit and rollback do nothing, so each statement commits on its own and a rollback keeps earlier writes.
- A Neo4j HTTP batch keeps earlier statements when a later one fails.
- Iteration 56 (review 53-55 F1): reproduced end to end with the neo4j driver 6.4.1 and a raw Bolt client against the product's own listener ([bug-plt-127](bugs_issues.md#bug-plt-127), [bolt_tx binding](results/bolt_tx/20261117T065936Z-binding/receipt.json)): rollback, a failure then rollback, RESET, a closed connection and an aborted `execute_write` all keep the transaction's writes while every answer is SUCCESS. Both listed answers rule this out; the owner [access.bolt.transactions](../ontology/concepts/access.g5.md#access.bolt.transactions) now states that shared rule (auto-commit statements still commit on their own), and the model checks both repairs (`atomic-tx`, `begin-refused`). Only the choice of repair remains open.

- Iteration 59 (review 56-58 G1): the HTTP sibling reproduced end to end: a `/db/neo4j/tx/commit` request of CREATE, a failing statement and CREATE answers 400 and keeps both nodes ([bug-plt-136](bugs_issues.md#bug-plt-136), [bolt_tx binding section H](results/bolt_tx/20261117T090118Z-binding/receipt.json)). New owner [access.http_transactions](../ontology/concepts/access.g5.md#access.http_transactions) states the same rule for one request (BEGIN, its statements, COMMIT; `theorem_http_rule_is_bolt_rule`). The read-only refusal already treats a request as one unit.

Disposition: open. Working assumption (revised in iteration 59, review 56-58 m1; was "Assume per-statement commits on Bolt until an explicit transaction contract is established", which contradicted the newer owners): a Neo4j-compatible transaction, on Bolt or one HTTP `tx/commit` request, keeps its writes only if it commits; IVG either provides that or refuses the explicit transaction (or the multi-statement request) so the client knows each statement commits on its own. Today's per-statement commits are recorded as departures ([bug-plt-127](bugs_issues.md#bug-plt-127), [bug-plt-136](bugs_issues.md#bug-plt-136)), not assumed as intent; auto-commit statements still commit on their own. Only the choice between the two answers stays open.

```g5-question
schema: 1
id: access.transactions
status: open
prompt: Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: map explicit transactions onto one IVG transaction, or refuse explicit transactions and document per-statement commits.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: map explicit transactions onto one IVG transaction, or refuse explicit transactions and document per-statement commits.
```

<a id="query.writes.delete-scope"></a>
### Should a Cypher `DELETE` clean up everything the engine's own [node delete](graph-structure.g5.md#structure.node.delete) and edge delete clean up?

[Q · query.writes.delete-scope]

Should a Cypher `DELETE` clean up everything the engine's own [node delete](../ontology/features/graph-structure.g5.md#structure.node.delete) and edge delete clean up? Provisional answer, as built: `DETACH DELETE` removes the node's labels, properties, default-route vector, incident edges and those edges' reifications, but not vectors in other routes or temporal entries. `DELETE r` removes only the relationship row and leaves its reification, the same open question as [edge delete reifications](#structure.edge.delete.reifications).

Disposition: open. Working assumption: `DETACH DELETE` removes the node's labels, properties, default-route vector, incident edges and those edges' reifications, but not vectors in other routes or temporal entries. `DELETE r` removes only the relationship row and leaves its reification, the same open question as [edge delete reifications](graph-structure.g5.md#structure.edge.delete.reifications).

```g5-question
schema: 1
id: query.writes.delete-scope
status: open
prompt: Should a Cypher `DELETE` clean up everything the engine's own [node delete](graph-structure.g5.md#structure.node.delete) and edge delete clean up?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "`DETACH DELETE` removes the node's labels, properties, default-route vector, incident edges and those edges' reifications, but not vectors in other routes or temporal entries. `DELETE r` removes only the relationship row and leaves its reification, the same open question as [edge delete reifications](#structure.edge.delete.reifications)."
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "`DETACH DELETE` removes the node's labels, properties, default-route vector, incident edges and those edges' reifications, but not vectors in other routes or temporal entries. `DELETE r` removes only the relationship row and leaves its reification, the same open question as [edge delete reifications](#structure.edge.delete.reifications)."
```

<a id="query.routes"></a>
### Should the second HTTP app's Cypher endpoints (`/api/cypher` and GraphQL `executeCypher`) answer through the engine, as the documented server and the Bolt listener do?

[Q · query.routes]

Should the second HTTP app's Cypher endpoints (`/api/cypher` and GraphQL `executeCypher`) answer through the engine, as the documented server and the Bolt listener do? Provisional answer: yes; today they run the translated SQL themselves.

Disposition: open. Working assumption: yes; today they run the translated SQL themselves.

```g5-question
schema: 1
id: query.routes
status: open
prompt: Should the second HTTP app's Cypher endpoints (`/api/cypher` and GraphQL `executeCypher`) answer through the engine, as the documented server and the Bolt listener do?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: yes; today they run the translated SQL themselves.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: yes; today they run the translated SQL themselves.
```

<a id="structure.write.engine-connection"></a>
### Should whether a write joins the caller's transaction depend on how the engine was opened?

[Q · structure.write.engine-connection]

Should whether a write joins the caller's transaction depend on how the engine was opened? There is no provisional answer.

- Today the calls that use the engine's own native connection nest in the caller's transaction for an engine made on the caller's connection, and commit on their own for an engine made with `from_connect`.
- Plausible answers: make every such call join the caller's transaction, refuse an open caller transaction, or document the difference per call.

Disposition: open. Working assumption: Treat transaction membership as dependent on the connection used by the engine.

Evidence (retest iteration 26, [observations](../uplift/consolidated/iteration-26/caller-txn-observed-20261116T213901Z.json), [model](models/write_routing/NOTES.md)): the difference is per call, not per engine. On a `from_connect` engine, `purge_before` and `set_temporal_structural` survive the caller's rollback (a purge also retires the endpoint nodes it leaves bare), while node, edge, Cypher and `create_edge_temporal` writes join. Separately, with the driver's autocommit off, direct ObjectScript calls can escape on either engine ([bug-tmp-102](bugs_issues.md#bug-tmp-102)). An answer here should cover both.

```g5-question
schema: 1
id: structure.write.engine-connection
status: open
prompt: Should whether a write joins the caller's transaction depend on how the engine was opened?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat transaction membership as dependent on the connection used by the engine.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat transaction membership as dependent on the connection used by the engine.
```

<a id="structure.edge.delete.reifications"></a>
### Should deleting an edge also remove its reifications and edge embeddings, as deleting a node, deleting a relationship through the ledger, and erasing edges do?

[Q · structure.edge.delete.reifications]

Should deleting an edge also remove its reifications and edge embeddings, as deleting a node, deleting a relationship through the ledger, and erasing edges do? No source decides it, and there is no provisional answer.

Disposition: open. Working assumption: Treat edge deletion as removing only the rows its implementation explicitly cleans up.

```g5-question
schema: 1
id: structure.edge.delete.reifications
status: open
prompt: Should deleting an edge also remove its reifications and edge embeddings, as deleting a node, deleting a relationship through the ledger, and erasing edges do?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat edge deletion as removing only the rows its implementation explicitly cleans up.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat edge deletion as removing only the rows its implementation explicitly cleans up.
```

<a id="structure.rebuilt.rollback"></a>
### When a computation sees a write that is not yet committed and that write later rolls back, must the cached result be thrown away?

[Q · structure.rebuilt.rollback]

When a computation sees a write that is not yet committed and that write later rolls back, must the cached result be thrown away? The provisional answer is yes, because the degree cache and the rebuild already treat that case as unsafe. Today the cached result stays current until the next write (observed).

Disposition: open. Working assumption: yes, because the degree cache and the rebuild already treat that case as unsafe. Today the cached result stays current until the next write (observed).

```g5-question
schema: 1
id: structure.rebuilt.rollback
status: open
prompt: When a computation sees a write that is not yet committed and that write later rolls back, must the cached result be thrown away?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: yes, because the degree cache and the rebuild already treat that case as unsafe. Today the cached result stays current until the next write (observed).
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: yes, because the degree cache and the rebuild already treat that case as unsafe. Today the cached result stays current until the next write (observed).
```

<a id="structure.rebuild.failure"></a>
### What may readers see when a rebuild fails partway?

[Q · structure.rebuild.failure]

What may readers see when a rebuild fails partway? The provisional answer, from the degree-cache design, is that an early failure leaves the previous adjacency, and a later one leaves a partial index whose degree cache is cleared, never wrong.

Iteration 57 (continuation; evidence only, no card field changed): a rebuild that succeeds already exposes what this question asks about. With a declared index, `BuildKG` purges `^KG("out"/"in")` and refills it row by row under a lock readers never take; during another session's `sync()` about 6-8% of reads on the fixture answered from the purged index (khop the seed alone, a path length -1, BFS types blank): [bug-str-115](bugs_issues.md#bug-str-115), [rebuild_reads](models/rebuild_reads/NOTES.md). Under either answer to this question, today's mid-rebuild exposure departs from "never wrong" for readers other than the degree cache.

Disposition: open. Working assumption: that an early failure leaves the previous adjacency, and a later one leaves a partial index whose degree cache is cleared, never wrong.

```g5-question
schema: 1
id: structure.rebuild.failure
status: open
prompt: What may readers see when a rebuild fails partway?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: that an early failure leaves the previous adjacency, and a later one leaves a partial index whose degree cache is cleared, never wrong.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: that an early failure leaves the previous adjacency, and a later one leaves a partial index whose degree cache is cleared, never wrong.
```

<a id="redaction.unattributed"></a>
### What should happen to a record in the target graph when it cannot be determined whether the record belongs to a prefix target?

[Q · redaction.unattributed]

What should happen to a record in the target graph when it cannot be determined whether the record belongs to a prefix target? There is no provisional answer.

- Today it is left in place and counted in the receipt, and the run still reports complete.
- Possible answers: block completion until it is resolved; tombstone it; or keep today's behavior and document it.

Disposition: open. Working assumption: Retain an unattributed record and disclose it in the receipt until prefix ownership is established.

```g5-question
schema: 1
id: redaction.unattributed
status: open
prompt: What should happen to a record in the target graph when it cannot be determined whether the record belongs to a prefix target?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Retain an unattributed record and disclose it in the receipt until prefix ownership is established.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Retain an unattributed record and disclose it in the receipt until prefix ownership is established.
```

<a id="search.embedding.queue.processing"></a>
### May two workers process the queue at the same time, and must an entry be marked done only after its vector is committed?

[Q · search.embedding.queue.processing]

May two workers process the queue at the same time, and must an entry be marked done only after its vector is committed?
- Provisional answer (current behavior): one worker at a time is assumed, so entries are not claimed. An entry is marked done before its vector is stored, and is changed to an error if storing then fails.
- Alternative: claim entries so two workers never process the same one, and mark an entry done only after its vector commits.

Disposition: open. Working assumption: one worker at a time is assumed, so entries are not claimed. An entry is marked done before its vector is stored, and is changed to an error if storing then fails.

Evidence (iteration 36, W42): the provisional answer describes the Python worker, observed to end every failure as an error. The IRIS worker's final DONE without a vector ([bug-srch-103](bugs_issues.md#bug-srch-103)) is a defect, not this question's intermediate state. Verus: [`embed_queue.rs`](models/embed_queue/embed_queue.rs) `theorem_interrupted_mark_breaks_rule` shows the owner's rule rejects the intermediate state; whether that state is acceptable is still this question. No second worker was run.

```g5-question
schema: 1
id: search.embedding.queue.processing
status: open
prompt: May two workers process the queue at the same time, and must an entry be marked done only after its vector is committed?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: one worker at a time is assumed, so entries are not claimed. An entry is marked done before its vector is stored, and is changed to an error if storing then fails.
    description: Default assumption.
  - label: claim entries so two workers never process the same one, and mark an entry done only after its vector commits
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: one worker at a time is assumed, so entries are not claimed. An entry is marked done before its vector is stored, and is changed to an error if storing then fails.
```

<a id="search.erasure.indexes.graphless"></a>
### What must erasing one graph do to a VecIndex, PLAID or IVF index, which records no graph?

[Q · search.erasure.indexes.graphless]

What must erasing one graph do to a VecIndex, PLAID or IVF index, which records no graph? There is no provisional answer.

- Plausible answers: record each entry's graph so the erase can find it, drop or mark stale every such index the erase touches, or treat them as derived stores the caller rebuilds.

Disposition: open. Working assumption: Treat graphless indexes as derived data requiring a rebuild after erasure.

```g5-question
schema: 1
id: search.erasure.indexes.graphless
status: open
prompt: What must erasing one graph do to a VecIndex, PLAID or IVF index, which records no graph?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat graphless indexes as derived data requiring a rebuild after erasure.
    description: Default assumption.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat graphless indexes as derived data requiring a rebuild after erasure.
```

<a id="temporal.write.update-statistics"></a>
### What should the statistics say after an update replaces an edge's weight?

[Q · temporal.write.update-statistics]

What should the statistics say after an update replaces an edge's weight?
- Provisional answer, as documented: the statistics keep describing the first write.
- Alternative: they describe the edges as they are now, recomputed as after a delete.
- Alternative: every write counts, so an update adds a second count and its new weight.

Disposition: open. Working assumption: the statistics keep describing the first write.

```g5-question
schema: 1
id: temporal.write.update-statistics
status: open
prompt: What should the statistics say after an update replaces an edge's weight?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: the statistics keep describing the first write.
    description: Default assumption.
  - label: |-
      they describe the edges as they are now, recomputed as after a delete.
      - Alternative: every write counts, so an update adds a second count and its new weight
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: the statistics keep describing the first write.
```

<a id="temporal.write.partial-failure"></a>
### When a temporal write fails part way, what may it leave behind, and must a retry be able to finish it?

[Q · temporal.write.partial-failure]

When a temporal write fails part way, what may it leave behind, and must a retry be able to finish it?
- Provisional answer, as documented: the parts written before the error stay, because a direct write runs no transaction.
- Alternative: a failed write leaves nothing, so a retry starts clean.
- Open either way: a retry in insert mode now finds the edge, reports a collision and never writes the missing structural edge, statistics or attributes.

Disposition: open. Working assumption: the parts written before the error stay, because a direct write runs no transaction.

```g5-question
schema: 1
id: temporal.write.partial-failure
status: open
prompt: When a temporal write fails part way, what may it leave behind, and must a retry be able to finish it?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: the parts written before the error stay, because a direct write runs no transaction.
    description: Default assumption.
  - label: |-
      a failed write leaves nothing, so a retry starts clean.
      - Open either way: a retry in insert mode now finds the edge, reports a collision and never writes the m
    description: |-
      a failed write leaves nothing, so a retry starts clean.
      - Open either way: a retry in insert mode now finds the edge, reports a collision and never writes the missing structural edge, statistics or attributes
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: the parts written before the error stay, because a direct write runs no transaction.
```

<a id="temporal.structural.mark.visibility"></a>
### Should readers show the temporal mark as part of the edge's data?

[Q · temporal.structural.mark.visibility]

Should readers show the temporal mark as part of the edge's data?
- Provisional answer (agent, unratified): no. The mark is bookkeeping (spec 252 planned it as a separate column), so Cypher maps and RDF qualifiers would leave it out while the edge and its weight stay visible.
- Alternative, as built: the mark is one of the edge's qualifiers, and Cypher and RDF show it.
- Alternative: RDF export leaves marked edges out, as NDJSON export does, and the PROV-O export carries them.

Disposition: open. Working assumption: no. The mark is bookkeeping (spec 252 planned it as a separate column), so Cypher maps and RDF qualifiers would leave it out while the edge and its weight stay visible.

```g5-question
schema: 1
id: temporal.structural.mark.visibility
status: open
prompt: Should readers show the temporal mark as part of the edge's data?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: no. The mark is bookkeeping (spec 252 planned it as a separate column), so Cypher maps and RDF qualifiers would leave it out while the edge and its weight stay visible.
    description: Default assumption.
  - label: RDF export leaves marked edges out, as NDJSON export does, and the PROV-O export carries them
    description: ""
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: no. The mark is bookkeeping (spec 252 planned it as a separate column), so Cypher maps and RDF qualifiers would leave it out while the edge and its weight stay visible.
```

<a id="temporal.structural.ledger-nodes"></a>
### Are the endpoint nodes that a temporal write creates, or that a purge retires, governed by the ledger?

[Q · temporal.structural.ledger-nodes]

Are the endpoint nodes that a temporal write creates, or that a purge retires, governed by the ledger?
- Provisional answer: none is recorded; only marked edges were declared outside governance.
- Alternative: treat such nodes like marked edges and skip them in the starting snapshot and verification.
- Alternative: govern them, so these node writes are refused or recorded while the ledger is on, and a purge never retires a node the ledger recorded.

Disposition: open. Working assumption: Keep the existing ledger rules for node rows until a source extends the marked-edge exemption to endpoints.

```g5-question
schema: 1
id: temporal.structural.ledger-nodes
status: open
prompt: Are the endpoint nodes that a temporal write creates, or that a purge retires, governed by the ledger?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: none is recorded; only marked edges were declared outside governance.
    description: Default assumption.
  - label: |-
      treat such nodes like marked edges and skip them in the starting snapshot and verification.
      - Alternative: govern them, so these node writes are refused or reco
    description: |-
      treat such nodes like marked edges and skip them in the starting snapshot and verification.
      - Alternative: govern them, so these node writes are refused or recorded while the ledger is on, and a purge never retires a node the ledger recorded
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: none is recorded; only marked edges were declared outside governance.
```

<a id="temporal.optout.stranded"></a>
### What should happen to the marked structural edges of a predicate whose timestamps were purged while it was temporal-only, if it is made structural again before the drop?

[Q · temporal.optout.stranded]

What should happen to the marked structural edges of a predicate whose timestamps were purged while it was temporal-only, if it is made structural again before the drop? There is no provisional answer.
- Today no operation removes them: the drop refuses a structural predicate, and no timestamp is left for a delete or purge to find.
- Alternative: let a cleanup remove marked edges that no timestamp holds, whatever the registration says.
- Alternative: refuse to make a predicate structural again while its old marked edges remain.
- Related: should a single-edge delete leave such edges for the drop, as the purge does?

Disposition: open. Working assumption: Treat previous temporal edges as retained until an explicit cleanup or reclassification is authorized.

```g5-question
schema: 1
id: temporal.optout.stranded
status: open
prompt: What should happen to the marked structural edges of a predicate whose timestamps were purged while it was temporal-only, if it is made structural again before the drop?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: Treat previous temporal edges as retained until an explicit cleanup or reclassification is authorized.
    description: Default assumption.
  - label: |-
      let a cleanup remove marked edges that no timestamp holds, whatever the registration says.
      - Alternative: refuse to make a predicate structural again while its
    description: |-
      let a cleanup remove marked edges that no timestamp holds, whatever the registration says.
      - Alternative: refuse to make a predicate structural again while its old marked edges remain.
      - Related: should a single-edge delete leave such edges for the drop, as the purge does?
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Treat previous temporal edges as retained until an explicit cleanup or reclassification is authorized.
```

<a id="query.aggregation.keys.numbers"></a>
### Do an integer and a float of equal value fall in one group?

[Q · query.aggregation.keys.numbers]

Run: Uplift 2026-11-17 (continuation, iteration 54)

Should a grouping key, `DISTINCT` and `count(DISTINCT)` treat the integer 1 and the float 1.0 as one value?
- Provisional answer (agent, unratified): two values, as the native executor answers today (its group key keeps a number's type). It keeps grouping consistent with how IVG stores and returns the two types.
- Alternative: one value, by openCypher's equivalence of numbers of equal value (CIP2016-06-14 compares numbers by value); Neo4j is commonly described as grouping them together, which this run did not check.
- As built: the SQL path puts 1, 1.0 and the string "1" in one group by their text ([bug-cyp-135](bugs_issues.md#bug-cyp-135)); the native executor keeps all three apart ([bug-cyp-136](bugs_issues.md#bug-cyp-136)). The TCK at the pinned revision has no scenario that decides it.

Disposition: open. Working assumption: two values. Evidence: [W59](../uplift/consolidated/iteration-54/clauses-PAIRS.md), [cypher_clauses](models/cypher_clauses/NOTES.md). Owner: [query.aggregation.keys](../ontology/features/cypher.g5.md#query.aggregation.keys).

```g5-question
schema: 1
id: query.aggregation.keys.numbers
status: open
prompt: Should a grouping key, DISTINCT and count(DISTINCT) treat the integer 1 and the float 1.0 as one value?
severity: low
multi_select: false
allow_free_text: true
options:
  - label: Two values, as the native executor answers today.
    description: Default assumption.
  - label: "Two values: a number keeps its type in grouping"
    description: The native executor's answer today.
  - label: "One value: numbers of equal value are equivalent (openCypher CIP2016-06-14)"
    description: Both paths would need to compare numbers by value.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: Two values, as the native executor answers today.
```

<a id="query.parameters.drivers"></a>
### Which IRIS Python drivers must IVG's Cypher parameters work with?

[Q · query.parameters.drivers]

Run: Uplift 2026-11-17 (continuation, iteration 55)

Must `UNWIND $list`, a list parameter indexed or sliced by parameters, and the other reads that pass a list parameter into `JSON_TABLE` work with intersystems-irispython 5.3.x, the version the repository's `uv.lock` pins?
- Provisional answer (agent, unratified): yes. The lock file is what `uv sync --frozen` installs, and `pyproject.toml` accepts any driver version; until the project says otherwise, a read that fails only on the locked driver is a defect.
- Alternative: no. The README and `docs/dev/TCK.md` measure conformance with 5.4.0 and 5.4.1 only; 5.3.x would then need a stated lower bound (`intersystems-irispython>=5.4`) and a lock refresh, and [bug-cyp-125](bugs_issues.md#bug-cyp-125) would become a packaging defect.
- As built: with 5.3.2 the IRIS driver refuses a `?` inside `JSON_TABLE`'s source ("Invalid number of parameters"); with 5.4.1 it binds it (iteration 55, both drivers on one fixture).

Disposition: open. Working assumption: 5.3.x is supported. Evidence: [W60](../uplift/consolidated/iteration-55/pipeline-PAIRS.md), [bolt_answers](models/bolt_answers/NOTES.md) (provider premise P-DRV-JT). Owner: [query.parameters](../ontology/features/cypher.g5.md#query.parameters).

```g5-question
schema: 1
id: query.parameters.drivers
status: open
prompt: Must Cypher list parameters (UNWIND $list, $l[$i], $l[$s..$e]) work with intersystems-irispython 5.3.x, the version uv.lock pins?
severity: medium
multi_select: false
allow_free_text: true
options:
  - label: "Yes: the locked driver is supported until the project states a lower bound."
    description: Default assumption.
  - label: "Yes: 5.3.x is supported"
    description: A read that fails only on 5.3.x is a product defect (bug-cyp-125).
  - label: "No: require intersystems-irispython 5.4 or later"
    description: State the lower bound in pyproject.toml and refresh uv.lock; bug-cyp-125 becomes a packaging fix.
answer:
  selected: []
  text: ""
  rationale: ""
  answered_by: null
  answered_at: null
default_assumption: "Yes: the locked driver is supported until the project states a lower bound."
```
