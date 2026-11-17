# Iteration 56: review 53-55 repairs, then the install lifecycle

Before image `fb1f806b` (the master's inventory commit after seal 55). Product `3eaa79cf` unchanged: nothing outside
`.g5/` changed (`git diff fb1f806b -- . ':!.g5'` empty; `check_consolidated.py` confinement PASS).
Commits:
- `4f1c5d25`: the Part B freeze, committing only [install-PAIRS.md](install-PAIRS.md) before any deciding source in
  `schema_name.py`, `schema.py`, `_engine/schema.py` or `_engine/class_deploy.py` was read;
- `628ea197`: the verbatim review copy and the four F5 relabels (640 → 636);
- `4df53412`: Part A repairs integrated; `f56e5189`: Part B integrated;
- the seal.

Guidance read at the start: `$G5_HARNESS/AGENTS.md`; `uplift-review.md`; `Verus/{uplift, uplift-iteration,
uplift-scoring, setup_foundation, verification}.md`; the runbook's continuation section. `open_questions.md` changed
only by two appended evidence paragraphs (`access.transactions`, `q-plt-002`); no card, anchor, field or saved answer
was touched. Quarantine respected: no iteration-13 Cypher `MERGE` material, no evaluator-private ledger. Native evidence
comes only from `ivg-cont-20261117-iris`: USER with fresh prefixes `i56b_`, `i56c_`, `i56q_` users, and fresh namespaces
`I56Q` and `I56SA`-`I56SD` (created and dropped by the bindings). No other container was touched. No STOP file appeared.

**Sub-agents.** Four workers with disjoint files ran in parallel: W1 Bolt transactions (F1), W2 Cypher (F2, F3,
percentile minors), W3 SQL privileges/BM25/temporal (F4, m2, MatchEdges, kg_BM25 k, tie order), W4 the install
lifecycle (Part B). Workers wrote register, crosswalk, coverage and disposition snippets into [bolt/](bolt/),
[cypher/](cypher/), [sqlbm25/](sqlbm25/) and [install/](install/); the builder alone edited the shared registers
(`bugs_issues.md`, `crosswalk/*.tsv`, `families.tsv`, `coverage.md`, `open_questions.md`), applied the owner text W3
supplied for `search.bm25*` and `access.iris_boundary`, did F5, and re-verified every receipt (below) before sealing.

## Part A: review round 3 (review-53-55)

[REVIEW-53-55.md](REVIEW-53-55.md) is the verbatim copy (session `c68a5c59`, commit `fb1f806b`); every item's
disposition is in [DISPOSITIONS.md](DISPOSITIONS.md). Summary of the sign-off conditions:

| Condition | Status |
|---|---|
| F1 owned and registered with a binding case | **Met.** New owner [access.bolt.transactions](../../../ontology/concepts/access.g5.md#access.bolt.transactions) (uncertain; the rule both answers of question `access.transactions` share: a transaction's writes stay only if it commits, otherwise BEGIN must be refused); F-1601 promoted to [bug-plt-127](../../../Verus_verification/bugs_issues.md#bug-plt-127) **High** (silent, persisted, on the driver's standard API: rollback, failure + rollback, RESET, a closed connection and an aborted `execute_write` keep the writes while every answer is SUCCESS); model `bolt_tx`; binding BEGIN/CREATE/ROLLBACK/count with commit, `execute_write` and auto-commit neighbors; `bolt_stream` NOTES scope note (pending rows, not writes). |
| F2 owned and registered with a binding case | **Met.** [bug-cyp-146](../../../Verus_verification/bugs_issues.md#bug-cyp-146) Medium (both engines; 2-hop answers 2); `query.optional` bullet; `cypher_clauses` section I with control and binding cases. |
| F3 statement consistent | **Met.** `theorem_numeric_distinct_normalizes_int_and_whole_double` marked conditional on `query.aggregation.keys.numbers`; narrowing stated in `aggregate_results/NOTES.md`, the coverage row and `query.aggregation` metadata; `query.aggregation.keys` reworded so it no longer reads as settled. |
| F4 and F5 reclassified and recounted | **Met.** F4 modeled rather than relabeled: the verdict is derived from the caller's grants (%All, table, schema, role, column-only), bound with eight real users in `I56Q`. F5: four rows relabeled (two `delegates`, two `cites`). |

Severity choice for bug-plt-127: High rather than the review's "Medium or higher", because the departure is silent
(SUCCESS at every step), persists data the client asked to discard, occurs on the driver's ordinary transaction API, and
matches the class of the register's other High rollback findings (bug-tmp-003). Whether IVG should implement Bolt
transactions or refuse BEGIN stays open (question `access.transactions`); both readings reject today's outcome.

## Part B: install lifecycle

**Predictions** ([install-PAIRS.md](install-PAIRS.md); frozen at `4f1c5d25` from docs, owners, CHANGELOG, README,
USER_GUIDE, ADMIN_GUIDE before the deciding source): 16 workflows, 32 predictions. Held in full 10 (A1 fresh vs
existing setup, A2 mismatched record, A4 dry run, A6 name rules, B1/B2 first access, C2 fingerprint redeploy, D1 width
refusal vs rewidth, D3 write width, E1 adopt/claim/force); held for one neighbor only 1 (C1: `IVG_FORCE_CLASS_DEPLOY`
not run); partial 2 (A3 explicit name beside another schema = bug-plt-026; D2 populated sibling table = bug-plt-134);
missed 2 (A5 unrecorded namespace with this release's marker is admitted = bug-plt-133; F1 every placement of a
quarantined row fails = bug-srch-116); F2 held only under the repaired row read.

**Model** [`install_lifecycle`](../../../Verus_verification/models/install_lifecycle/NOTES.md): 32 verified, 20/20
controls EXPECTED_FAIL, binding AGREES 138 on fresh namespaces `I56SA`-`I56SD` (20/20 mutations and the tamper
detected). Decisions derived from their inputs: schema-name rules and resolution; the first-access check and its reason
order; setup's record decision, package clash and dry run; class-deploy skip and fingerprint write-back; width
refuse / rewidth / manual / unknown; embedding identity adopt / claim / conflict / force / enforce; quarantine
placement. Premises named: P-CASE-LOOKUP, P-CASE-CLASS, P-ALTER-POPULATED (observed, not derived). Owners: "Today"
bullets in `install.schema.name`, `.not_ready`, `.existing`, additions to `install.setup.resume` and `install.deploy`,
`search.embedding.width`, `search.quarantine.placement`, and metadata for `check_on_write` and `claim`.

## Findings

New in this iteration (matched by trigger and observable consequence against the register, the 2026-11-15 audit
record and KNOWN_ISSUES):

| ID | Severity | Trigger → observable | Found by / reproduced by |
|---|---|---|---|
| [bug-plt-127](../../../Verus_verification/bugs_issues.md#bug-plt-127) | High | Bolt BEGIN, CREATE, ROLLBACK (or failure + rollback, RESET, close, aborted `execute_write`) → writes kept, all SUCCESS | review F1 (F-1601 promoted) / W1 raw client and neo4j 6.4.1, `bolt_tx` binding |
| [bug-cyp-146](../../../Verus_verification/bugs_issues.md#bug-cyp-146) | Medium | `length(p)` of an unbound OPTIONAL fixed path → the hop count | review F2 / W2 probe, `cypher_clauses` binding |
| [bug-srch-116](../../../Verus_verification/bugs_issues.md#bug-srch-116) | Medium | `place_quarantined` over the DB-API driver → "Cursor closed", row stays quarantined | Part B F1 missed / `install_lifecycle` binding |
| [bug-cyp-147](../../../Verus_verification/bugs_issues.md#bug-cyp-147) | Low | `percentileDisc` over integers → a float | review minor / `percentile` binding |
| [bug-cyp-148](../../../Verus_verification/bugs_issues.md#bug-cyp-148) | Low | percentile `$p` null → raw TypeError; text → ValueError; `'0.5'`/`true` converted; literal null → p = 0 | review minor (widened) / `percentile` binding |
| [bug-tmp-108](../../../Verus_verification/bugs_issues.md#bug-tmp-108) | Low | empty source/predicate aggregate over a cut-only window → 0 (elsewhere `<SUBSCRIPT>`) | round-2 m2 challenge / `temporal_stats` binding |
| [bug-srch-113](../../../Verus_verification/bugs_issues.md#bug-srch-113) | Low | SQL `kg_BM25` with k ≤ 0 → `[]` while `bm25_search` and `CALL ivg.bm25.search` refuse | review minor / `bm25_scoring` binding |
| [bug-plt-133](../../../Verus_verification/bugs_issues.md#bug-plt-133) | Low | unrecorded namespace holding this release's marker function → engines admitted | Part B A5 missed / `install_lifecycle` binding (a KNOWN_ISSUES item with no register entry before) |
| [bug-plt-134](../../../Verus_verification/bugs_issues.md#bug-plt-134) | Low | a populated table beside empty ones at the old width → plain setup and `rewidth=True` raise; no `needs_manual_migration` | Part B D2 partial / `install_lifecycle` binding |

Inherited, now E2E reproduced and promoted from the audit archive to full entries: [bug-plt-015](../../../Verus_verification/bugs_issues.md#bug-plt-015)
(Low → **Medium**: a schema name differing only in case re-declares empty vector columns unasked, registry ≠ column, three
schema classes fail ERROR #5092, every later setup recompiles) and [bug-plt-026](../../../Verus_verification/bugs_issues.md#bug-plt-026)
(Low: an explicit name beside one other schema is recorded and the other engine refused from then on; contradicts spec
FR-009). F-1601 → bug-plt-127 (above). New discoveries vs repairs: the review supplied F1/F2 and the minors; Part B's
five came from this iteration's own search (two predicted-and-missed, one partial, two from the case probe).
Questions: none opened; additive evidence on `access.transactions` and `q-plt-002`. Simplifications: none.

## Models and receipts (final candidate)

| Model | Verified | Controls | Binding |
|---|---|---|---|
| [`bolt_tx`](../../../Verus_verification/models/bolt_tx/NOTES.md) (new) | 20 | 7/7 | AGREES 17 (9 raw Bolt 4.4, 8 neo4j 6.4.1); 6/6 mutations, tamper detected |
| [`install_lifecycle`](../../../Verus_verification/models/install_lifecycle/NOTES.md) (new) | 32 | 20/20 | AGREES 138; 20/20 mutations, tamper detected |
| `cypher_clauses` | 26 → 29 | 25 → 28 | 112 → 124 |
| `percentile` | 26 → 30 | 4 → 7 | 156 → 168 |
| `aggregate_results` | 75 (narrowing stated) | 12/12 | AGREES 669 |
| `sql_procs` | 16 → 27 | 12 → 21 | 224 → 273 (namespace I56Q, 8 users) |
| `temporal_stats` | 58 → 64 | 18 → 20 | 148 → 159 |
| `bm25_scoring` | 32 → 35 | 9 → 13 | 46 → 59 |
| `bolt_stream` | 43 (scope note only) | 19/19 | AGREES (receipt partly incomplete; limitations) |

Every binding detected all its mutations and the tamper. Kept unsuccessful runs: an ERROR control receipt in
`sql_procs` (`first-table-only`, fuel on a non-recursive function, fixed and re-run), ERROR/UNEXPECTED proves and two
mismatching bindings of `install_lifecycle` (harness bugs, fixed), an empty `aggregate_results` binding directory. One
empty `bolt_stream` binding directory without a receipt was deleted by W1 (traceback kept in the worker log).

**Builder's independent re-verification** (after integration, before the seal): all nine proofs re-run in parallel,
PASS at the counts above (`results/*/20261117T0720*-prove`); full control suites re-run for `bolt_tx` (7/7),
`install_lifecycle` (20/20) and `sql_procs` (21/21), all EXPECTED_FAIL, none ERROR or surviving; bindings re-run for
`bolt_tx` (AGREES 17, all sensitivities detected) and `install_lifecycle` (AGREES 138, 0 mismatches, tamper detected,
`20261117T072228Z`). The other control suites and bindings are the workers' receipts, checked FRESH by
`check_evidence.py`.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **640 → 662** (+26 new, −4 lost); union reach (active plus baseline historical locators) **866 → 886**.
- **Lost (4, F5):** `start_tcp_bolt_server`, WebSocket `BoltSession._do_handshake` (→ `delegates`), `BM25Index.Build`,
  `VectorMixin.bm25_build` (→ `cites`). Union loses 3 of them (`Build` keeps a baseline historical locator); all four
  keep a resolved citation in the crosswalk.
- **Newly bound (26):** install lifecycle 20 (`schema_name.py`: `validate_schema_name`, `resolve_schema_name`,
  `check_first_access`, `_why_not_current`, `refuse_other_record`, `refuse_package_clash`; `class_deploy.py`:
  `_unchanged`, `upload_and_compile`, `plan_packaged_classes`, `deploy_packaged_classes`; `_engine/schema.py`:
  `_vector_column_action`, `_plan_vector_dimensions`, `_refuse_width_change`, `_migrate_vector_dimensions`,
  `reconcile_recorded_dimensions`, `_sync_recorded_dimension`, `set_embedding_identity`, `adopt_embedding_identities`,
  `enforce_embedding_identity`, `place_quarantined`) plus `embedding_identity.py::conflicts`; review repairs 5
  (`SqlPrivilege.cls::Holds`, `_validate.py::BM25SearchInput`, `translator.py::_expr_fn_path_funcs`, `::_vlp_path_sql`,
  `_engine/query.py::_float_expr_value`). Three of the 26 were existing locators (`deploy_packaged_classes`,
  `check_first_access`, `refuse_other_record`); 23 newly reached.
- **Strengthened (16):** RequireSelect/RequireWrite (now derived, not input), the four SqlProcs entries, `EdgeScan::MatchEdges`,
  `SearchCore`, `kgBM25`, `GetAggregate`, `_dispatch`/`_handle_run`/`_handle_reset`, `_scalar_statistical`,
  `_translate_bm25_search`, `_record_and_initialize`.
- **Withdrawn or narrowed:** `aggregate_results::theorem_numeric_distinct_normalizes_int_and_whole_double` now
  conditional (no crosswalk row cited it); `_scalar_statistical`'s emitter row → `delegates`; `theorem_entries_gated`
  no longer carries the SqlProcs rows (they now cite `theorem_readers_check_rdf_edges` and
  `theorem_write_names_first_missing`, which fix the table each entry checks).

Under the old rule the 6 rows the review named would all have counted; after the audit 4 are not counted and 2
(RequireSelect, RequireWrite) count because their decision is now modeled from grants and bound with real users.

**Material predictions gained:** what a Bolt rollback/failure/RESET/close does to writes; what `length(p)` answers for
an unbound OPTIONAL path; which grants pass the SQL privilege gate (column-only refused, role and schema accepted);
what an empty-key aggregate answers on a cut-only window; what `kg_BM25` answers for k ≤ 0; the BM25 tie order; the
percentile answer type and non-number p; and in Part B the explicit-name record decision, unrecorded-namespace
admission, the sibling-table width refusal, the case-variant width bypass, and that quarantine placement fails over the
DB-API driver. **Withdrawn:** none.

<a id="binding-integrity-audit"></a>
## Binding-integrity audit

Question per row with relation models/proves/witnesses: would swapping or weakening this member's own decision break a
theorem or the binding? Rows added or changed in this iteration and every row the review named. Per-row detail with the
control and mutation names: [bolt/audit.md](bolt/audit.md), [cypher/binding-integrity-audit.md](cypher/binding-integrity-audit.md),
the audit table in [sqlbm25/disposition.md](sqlbm25/disposition.md), [install/AUDIT.md](install/AUDIT.md).

| Member (rows) | Relation after audit | Swap or weaken its own decision → | Verdict |
|---|---|---|---|
| `bolt_server.py::start_tcp_bolt_server` (review F5) | delegates (was proves) | nothing breaks (one session per connection) | **not counted** |
| `bolt_server.py::BoltSession._do_handshake`, WebSocket (F5) | delegates (was models) | not exercised; `negotiate_version`'s answer | **not counted** |
| `BM25Index.cls::Build` (F5) | cites (was models) | stats are `used_arg` inputs read back from the store | **not counted** |
| `_engine/vector.py::VectorMixin.bm25_build` (F5) | cites (was models) | passes k1, b through | **not counted** |
| `SqlPrivilege.cls::RequireSelect` (F4) | proves (derived) | %All ignored → `all-not-shortcut`; column grants counted → `column-grant-counts`; binding users `i56q_column`, `i56q_all` | active |
| `SqlPrivilege.cls::RequireWrite` (F4) | proves | first table only → `first-table-only`; binding `i56q_nodesins` | active |
| `SqlPrivilege.cls::Holds` (new) | proves, models | roles ignored → `roles-ignored`; schema grant dropped → `schema-grant-ignored`; binding `i56q_role`, `i56q_select` (schema SELECT), `i56q_table` | active |
| `SqlProcs.cls::{MatchEdges, MatchEdgesAllGraphs, DijkstraPath, backfilltemporalrows}` | proves (changed theorem) | checking another table → `readers-check-nodes`, `no-select-check`, `sql-entry-unchecked`; the naming clauses; binding `*_name` | active |
| `EdgeScan.cls::MatchEdges` (new row) | proves | `$Char(0)` or `""` not normalized → `nul-not-normalized`, `empty-not-default`; binding `me_spell_*` | active |
| `BM25Index.cls::SearchCore` (2 new rows, 1 changed) | proves | reversed or text-only order → `numeric-ids-as-text`, `text-case-folded`; taking all for k ≤ 0 → `nonpositive-k-takes-all`; binding `k:sql@0` | active |
| `SqlProcs.cls::kgBM25`, `_validate.py::BM25SearchInput`, `translator.py::_translate_bm25_search` | models / proves | validating k / `ge=0` / not validating → `sql-entry-validates-k`, binding `k:*@0` | active |
| `TemporalIndex.cls::GetAggregate` (2 new rows) | proves | refuse always / never raise → `empty-key-refused`, `empty-key-never-raises`; binding empty-key cases | active |
| `translator.py::_expr_fn_path_funcs` (2 rows), `::_vlp_path_sql` | proves | length from row / from pattern; null anchor ignored → three controls, binding `I_*` | active |
| `translator.py::_scalar_statistical` (2 new rows; emitter row → delegates) | proves | refuse non-number p; keep input kind → `null-param-refused`, `disc-keeps-input-kind` | active (emitter row not counted) |
| `_engine/query.py::_float_expr_value` | proves | pass an int through → binding `kind:*` detects; the model's `cast_kind` is one decision shared with the translator's FLOAT typing | active, **binding-detected only** (no own control) |
| `bolt_server.py::BoltSession._dispatch` (2 rows), `_handle_run`, `_handle_reset` | proves, models | refuse BEGIN / hold a transaction / sticky failure removed → `begin-refused`, `atomic-tx`, `failure-not-sticky`, `run-not-committed`, `failed-run-writes` | active |
| `bolt_server.py::TcpBoltSession` | cites | inherits `_dispatch` | not counted |
| `schema_name.py::{validate_schema_name, resolve_schema_name, check_first_access, _why_not_current, refuse_other_record, refuse_package_clash}` | proves | each has a named control and binding cases ([install/AUDIT.md](install/AUDIT.md)) | active |
| `class_deploy.py::{_unchanged, upload_and_compile, plan_packaged_classes, deploy_packaged_classes}` | proves | `skip-on-marker-only`, `failed-deploy-keeps-marker`, `no-mismatch-check` | active (`plan_packaged_classes`: its role is the reader; force not exercised) |
| `_engine/schema.py::{_vector_column_action, _refuse_width_change, set_embedding_identity, adopt_embedding_identities, _record_and_initialize}`, `embedding_identity.py::conflicts` | proves | named controls and binding cases | active |
| `_engine/schema.py::{_plan_vector_dimensions, _migrate_vector_dimensions, reconcile_recorded_dimensions, _sync_recorded_dimension}` | models | swapped buckets / skipped ALTER or UPDATE change the dry-run lists, column widths and registry rows the binding reads | active, **binding-detected only** for `_plan_vector_dimensions` |
| `_engine/schema.py::enforce_embedding_identity` | proves | "none recorded passes" branch → `width-only-with-models`; the conflict decision itself is `conflicts`' | active (own branch only) |
| `_engine/schema.py::place_quarantined` | proves | check order, insert-then-delete → four controls | active, **qualified**: on the real product only the failing row read and "row stays" are observed; the later checks are bound under a harness substitution of `_quarantined_row` (bug-srch-116) |
| `foreign_classes`, `same_schema`, `write_record`, `_ivg_table_schemas`, `foreign_schema_classes`, `_quarantined_row`, `GraphSchema.get_embedding_dimension` | cites | each supplies a model input | not counted |
| `FirstAccessCheck.guard_methods`, `_plan_setup` | delegates | forward without changing the decision | not counted |
| Review sample, kept: `_unwind_by_index_retry` (inspected transcription), `MatchEdges` SQL entry (now derived) | unchanged / changed above | — | as in DISPOSITIONS |

The three "binding-detected only" or "qualified" rows stay counted under the rule (the binding breaks), but they are the
weakest of the 26 and the first candidates for demotion if a later review requires a theorem per member.

## Owners changed

New block [access.bolt.transactions](../../../ontology/concepts/access.g5.md#access.bolt.transactions). Extended:
`access.bolt` (working assumption replaced by the auto-commit sentence and the child link), `access.bolt.results`
(ROLLBACK effect → the new block; F-1602 "Today" bullet in governing text), `access.iris_boundary` (grants, column-only,
first missing named), `query.optional`, `query.aggregation` (metadata), `query.aggregation.keys` (reworded),
`query.functions.percentile`, `temporal.stats.window`, `structure.adjacency.scan`, `search.bm25` (k at three readers),
`search.bm25.scoring` (tie order as built), `install.schema.name`, `.not_ready`, `.existing`, `install.setup.resume`,
`install.deploy`, `search.embedding.width`, `.check_on_write`, `.claim`, `search.quarantine.placement`.
`check_ontology.py`: 403 blocks (402 before), 0 issues, 17 writing warnings (unchanged).

## Correspondence

The [delta from 55](correspondence-delta-from-55.json) is STALE_ALL for proof and correspondence; the changed inputs are
the models named above, `decision-links.tsv` and `families.tsv`; no product file changed. The fresh
[stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

<a id="checks-final-candidate"></a>
## Checks (final candidate)

| Check | Result |
|---|---|
| `check_ontology.py` | 403 blocks, 0 issues, 17 warnings (unchanged) |
| `check_findings.py` (`verification_root=.g5/Verus_verification`, `--previous fb1f806b`) | No problems found |
| `check_evidence.py` | FRESH |
| `check_consolidated.py` (G5_GUIDE set) | PASS (1,025 decision links resolve; statements 403 rows; findings.tsv 553 source rows, all canonical anchors resolve; correspondence stamp REUSABLE_INPUTS) |
| `git diff --check` | clean |
| Product diff vs pin | none outside `.g5/`; no untracked file outside `.g5/` |

## Limitations

- **Review:** the iteration-56 repairs are not independently reviewed; review round 3 was the last in the default
  budget (the master decides whether a further round validates these repairs).
- **Bolt:** TCP only (WebSocket shares `_dispatch`, not exercised); neo4j Python driver 6.4.1 and a raw client only;
  the read-only gate inside a transaction, the HTTP transaction routes and isolation from other sessions not tried;
  P-STMT-ATOMIC observed for a translation failure only. The `bolt_stream` re-run receipt lacks the iteration-9
  supplement fields (the supplement probe records Mac absolute paths; a pre-existing harness portability bug); the
  20261115 receipt remains the complete one.
- **Cypher:** a path projected through `WITH`, and mixed fixed/variable-length OPTIONAL paths, not checked; the literal
  null p rests on premise P-OS-EMPTY-ZERO; null-p intent (error or null) unsettled, both readings reject today.
- **Privileges:** P-CHECKPRIV observed for SELECT and INSERT only (UPDATE/DELETE letters, unknown letters, nested roles,
  roles via `Security.Roles` not tried). Empty keys of the distinct-count and group reads observed only. Tie order
  rests on P-COLLATE with ASCII ids; a graph named by another canonical number not tried.
- **Install:** IRIS DB-API driver 5.3.2 only (embedded Python, where bug-srch-116 may not occur, not tried); not
  modeled: routine fingerprints, grants and Arno revocation, the ledger history copy, `^KG`/`^NKG` after an explicit
  re-record, concurrent setups and claims, the DDL-privilege refusal, a setup that claims a declared model,
  `IVG_FORCE_CLASS_DEPLOY`. Assessed without a row: `IVGSchemaError` constructors, `read_record`,
  `FirstAccessCheck.ensure`, `rewrite_schema_text`, `SchemaConnection`/`SchemaCursor`, `_plan_routines`,
  `list_quarantine`, `is_ready`.
- Fixture nodes remain in USER under `i56b_`, `i56c_` (and the reviewer's `rv55*`); `I56SA`-`I56SD` were dropped.

<a id="residual-list-first-missing-step-for-each"></a>
## Residual list (first missing step for each)

1. Bolt transactions: WebSocket `_dispatch` through `bolt_stream`'s session; the read-only gate in a transaction.
2. BM25 `Build`: bind its statistics by deriving N/totalLen from the corpus inside the model and comparing with the
   stored globals (would restore `Build`/`bm25_build` as active).
3. `start_tcp_bolt_server` / WebSocket handshake: only a WebSocket client case would make the latter a reader again.
4. Install: `IVG_FORCE_CLASS_DEPLOY`; routines and grants; concurrent setups; the embedded-Python placement path.
5. `place_quarantined`: a real-product observation of the post-read checks needs the bug-srch-116 read fixed or an
   embedded run.
6. `_float_expr_value` and `_plan_vector_dimensions`: an own control each (split `cast_kind`; model the dry-run buckets).
7. Inherited queue unchanged otherwise (see the [continuation residual queue](../HANDOFF.md#continuation-2026-11-17)).

## Cost

Wall clock 06:49-07:28 UTC (about 39 minutes) for the builder session; four parallel workers (W1 25 min, W2 11 min,
W3 15 min, W4 26 min; sub-agent tokens 252k, 264k, 321k, 386k). Currency not available in-session.
