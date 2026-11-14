# Review round 3 — R3-reader (ontology read as a rebuilder; lost conditions)

Reviewer: R3-reader (fresh, isolated). Date: 2026-11-14. Worktree HEAD `0e441f1c`; product baseline `3eaa79cf`.

**Scope.** `.g5/ontology/` (the root and 12 pages, 348 blocks), read as someone who must rebuild the major capabilities. The review then compares it with the pre-round-2 snapshot (`$RUN_DIR/snapshots/ontology-pre-round2/`) and with the stage-A intent notes (`intent/*.md`), and checks the Q blocks and the findings-register links.

**Method.** I read every page body and scanned all of its Metadata.
- Five isolated helpers compared one intent note each with its pages: ledger-history; graph-structure with temporal; search with cypher; platform; and the operations inventory across all pages.
- Each helper checked its candidates against the original specs, ADRs, CONTEXT.md and code.
- I re-checked every helper finding rated High, and the Medium ones marked (verified), against the code or spec myself.
- I formed my findings before reading the earlier review rounds. I read the round 1 and 2 adjudication tables in `uplift-plan.md` only to avoid repeating dismissed items.

**Permissions.** Read-only on the product and on every artifact except this file. Scratch files are in `$RUN_DIR/agents/R3-reader/`. No tests, IRIS or docker were run.

Severity scale:
- **High:** would mislead a rebuilder about a consequential behaviour.
- **Medium:** a material omission, contradiction or misplaced uncertainty.
- **Low:** wording, a stale note or a link.

## 0. Summary

| | Count |
|---|---|
| High | 4 (H1–H4) |
| Medium | 25 (M1–M25) |
| Low | 11 groups (L1–L11) |
| Structural checkers | clean (see §3) |
| Snapshot diff | metadata-only changes; nothing lost; but two round-2 repairs stopped at Metadata (see §2) |

**How the ontology reads overall.**
- The ontology is readable. The root's topic table and definitions let a reader find every major capability. Most pages lead with the behaviour and then give its conditions.

**The recurring defect.** Over and over, a governing body states one thing while its Metadata, a sibling Q, or a register entry says another:
- A Findings link or a "Note" is added to the Metadata, and the body it contradicts is left as it was: H1, H2, H4, M9, M10.
- An open register question sits behind an `I`/`D` body with no `uncertain` tag: M1, M2, M12–M15, M22.
- Two pages each own the same commitment and disagree: M6, M7, M8.

**Coverage.** Imports, exports, inference and the non-Cypher read API have no owning block, and nothing declares them as a gap (M23).

## 1. Findings

### High

**H1 — `ledger.commit` (ledger.g5.md:62), plus `ledger.unrecorded`, `access.ledger_strict.bypasses` and the root's "its writes commit together": post-commit properties are missing from the governing contract.**
- **Problem:**
  - `Changeset.post_commit_properties` is a shipped, documented commit feature. The `$REVISION_ID` sentinel lets callers keep audit trails, and the result carries `post_commit_applied` / `post_commit_error`.
  - Without a caller transaction, the properties are written by direct SQL in a second transaction after the revision commits. They are never recorded in the ledger. A failure is returned in the result, not raised, and the revision stays committed.
  - The ontology mentions the feature only in Metadata (`ledger.idempotency`; Findings bug-led-003 and bug-led-009).
  - `ledger.commit` says a commit "applies a whole changeset as one new revision, or applies nothing". `ledger.strict` says commits are the engine's only way to change the governed graph.
  - Round 2 accepted R2-4 as "incorrect intent", but the repair added only register entries and Metadata links. Open question q-010 has no ontology owner at all.
- **Source:**
  - Feature and docs: `CHANGELOG.md:4991-4998` (spec 218); `docs/USER_GUIDE.md:288-289`; `iris_vector_graph/ledger/changeset.py:18-25,108`.
  - Behaviour: `iris_vector_graph/ledger/client.py:430-487`; receipt `receipts/native/ledger_post_commit_verify.json` (verify diverges).
  - Register: `open_questions.md#q-010`.
- **Proposed correction:** add a new child block `[D · ledger.commit.post-commit]`:
  > A changeset can carry post-commit properties: default-graph node properties written after the revision commits, with `$REVISION_ID` replaced by the new revision's ID. They are not recorded in the revision, so verify reports them as unrecorded writes. Without a caller's transaction they are a second commit, so a failure keeps the revision and is reported in the result instead of raised.

  Further changes:
  - Make the open part a Q child that links q-010: should these properties be recorded, excluded from verify, or documented?
  - Add "except post-commit properties" to `ledger.commit`'s all-or-nothing sentence.
  - List post-commit properties in `access.ledger_strict.bypasses`, or in the undecided list, with bug-led-009.

**H2 — `redaction.after-erasure.temporal` (redaction.g5.md:76), `redaction.tenant`, `erasure.prefix-match` and `temporal.erase`: a false premise, and the scope condition from spec 256 is lost.**
- **Problem:**
  - **False premise:** the Q offers "rely on erasure, which removes them anyway" as an answer. Round 2 (R2-1, bug-led-007, High, observed natively) showed that a prefix erase does not remove temporal-only events whose endpoints have no node row. The round-2 repair added only Findings links; the body still states the premise.
  - **Lost scope condition:** spec 256 explicitly put off "a tenant-scoped erase of the temporal tiers inside a shared graph (request 2)", because "with one graph per tenant, `EraseGraph` covers it". The stage-A note records this as **Deferred**.
    - The ontology cites the section only as a Sources link on `redaction.out-of-reach`.
    - The tenant recipe never says that a tenant's temporal edges must live in its own graph.
    - `temporal.erase` does not mention prefix erases at all.
  - **Effect:** a rebuilder or operator would believe the documented recipe removes a shared graph's tenant events. A decider weighing q-009 or bug-led-007 would not know the governing spec scoped this case out.
- **Source:**
  - Spec 256: `specs/256-ledger-tenant-redaction/spec.md:159-163`; `intent/ledger-history.md:51`.
  - Code: `Eraser.cls:322-349`, `TemporalIndex.cls:400-440`.
  - Receipts and register: `receipts/native/erasure_prefix_temporal_only.json`, `redaction_temporal_only_live.json`; `bugs_issues.md#bug-led-007`, `open_questions.md#q-009`.
- **Proposed correction:**
  - Replace the possible answers in `redaction.after-erasure.temporal` with:
    > count temporal entries as live; or rely on erasure, which removes them only when the tenant has its own graph — a prefix erase leaves temporal-only events whose endpoints have no node row.

    Link q-009.
  - Add a bullet to `redaction.tenant`:
    > Keep each tenant's temporal edges in its own graph. Erasing one tenant's temporal data inside a shared graph was put off by spec 256, and a prefix erase misses its temporal-only events.
  - Add to `temporal.erase`:
    > A prefix erase finds IDs through node rows, so a temporal-only event whose endpoints have no node row is not erased.

    Put that in Metadata as an observed divergence and link bug-led-007.
  - Re-weigh bug-led-007's severity and expectation in light of the spec 256 deferral.

**H3 — `install.schema.existing` (install.g5.md, "Tables in one other schema only: refuse … record nothing") and `install.schema.concurrency.leftover`: the spec rule is stated, but an observed breach is unrecorded and the Q rests on a misreading.** (verified)
- **Problem:**
  - Spec 262 FR-009 says that when IVG's tables are in exactly one other schema, setup refuses and records nothing. The spec's only exception for an explicitly named schema is the case of *several* schemas.
  - The code records the engine's schema whenever the name was given explicitly (`how = "explicit"`), including the one-other-schema case. No block records this divergence, and there is no Findings link.
  - The Q `…concurrency.leftover` says in its Metadata that "FR-009's explicit branch … records a named schema while other schemas hold IVG tables". That widens FR-009, and the Q is filed under *concurrency* although its case is a sequential interrupted setup.
  - **Consequence:** the namespace records schema T while the adjacency index and other namespace-wide globals hold schema S's data. FR-005/006 ("instead of sharing globals silently") exists to prevent exactly this.
- **Source:** `specs/262-ivg-owned-sql-schema/spec.md:253-256`; `data-model.md:26-31`; `iris_vector_graph/_engine/schema.py:2229-2242`; `engine.py:295-298` (the comment says the explicit branch is for "several schemas"); the only test uses a default engine (`tests/e2e/test_262_record.py`).
- **Proposed correction:**
  - Body bullet:
    > Tables in one other schema only: refuse, name that schema and record nothing, even when the engine's schema was named explicitly.
  - Metadata:
    > Observed divergence: an explicitly named engine is recorded anyway (`schema.py:2236-2242`).

    Add a new register bug.
  - Move the leftover Q under `install.schema.existing`. Narrow it to whatever FR-009 leaves open, which is the globals left by an unfinished setup of the current release.

**H4 — `search.embedding.claim`: the body and its own Metadata contradict each other on which call claims a table.** (verified)
- **Problem:**
  - The body says "The first writer that declares a model at that width claims the table."
  - The Metadata note says "an ordinary write does not claim an unknown table; setup and an explicit identity call do."
  - The code agrees with the note: a write that names a model goes to that model's own route and never claims the original table. The body's wording is ADR-0006's design from before routing existed.
- **Source:** `iris_vector_graph/_engine/embeddings.py:405-416` (`_read_route` matches `model_key = ?` only) and `:770-790`; `_engine/schema.py:1086-1220`, `:1485-1513`, `:2564-2568`; `docs/adr/0006-…md:51-54`; `CHANGELOG.md:4431`.
- **Proposed correction:**
  > Setup by an engine that declares a model, or an explicit identity call, claims an original table whose model is unknown; when two claim at once, exactly one wins. An ordinary vector write never claims a table: a write that names a model goes to that model's own route.

  Delete the contradicting Note bullet.

### Medium

**M1 — `redaction.batches.readers` (redaction.g5.md:196): a human decision is narrowed in the body, and the open part is only in Metadata.**
- **Problem:**
  - Decision 3 (Tom, 2026-10-22) says "readers and `verify()` honour" the marker, without limiting which readers.
  - The body follows the agent plan's narrower list: `get_revision`, diff, reconstruct, export.
  - Two facts are only in Metadata, and q-002 keeps the question open. First, `history`, `stats` and the SQL `ledger_records` procedure answer mid-run with partly cleared metadata (observed). Second, the refusing readers check the marker only once and then page through records.
  - The block is tagged `agent`, while its parent `redaction.batches` is `human-verified`. q-002 is not linked.
- **Source:** `spec.md:156`; `plan.md:42-46`; `receipts/native/redaction_readers_midrun.json`; `open_questions.md#q-002`.
- **Proposed correction:**
  > While the marker exists, record readers, diffs, reconstructions and exports refuse with `RedactionInProgressError`, and verify reports `redaction_in_progress` and adopts nothing. History, statistics and the SQL `ledger_records` procedure still answer and can show a half-redacted ledger; whether they must also refuse is open.

  Also: tag the block `uncertain`, link q-002, and record the provenance as Decision 3 narrowed by the plan.

**M2 — `ledger.lifecycle` (bullet "Disabling does not cancel an unfinished redaction … resumes after the ledger is enabled again") and `redaction.batches.resume`: an open question is stated as a rule.**
- **Problem:**
  - q-led-003 is open. It names `ledger.lifecycle` as the open statement and offers "refuse `disable` during a redaction" as one answer.
  - The bullet's only source is a code comment.
  - "Resumes" reads as automatic, but the caller must run the redaction again.
  - Re-enabling while the marker exists skips the adoption without an error (bug-led-004). That exception is in Metadata only.
- **Source:** `LedgerRedact.cls:302-305`; `Ledger.cls:331-351`; `open_questions.md#q-led-003`; `receipts/native/redaction_interrupt_resume.json`.
- **Proposed correction:**
  > Today, disabling the ledger does not cancel an unfinished redaction: its next batch fails, the marker stays, and the caller runs the same redaction again after re-enabling. Re-enabling while the marker exists skips the adoption without an error. Whether disable should be refused during a redaction is open.

  Tag `uncertain`.

**M3 — `redaction.purpose` (redaction.g5.md:18) and the page intro ("Together, the two cover everything IVG can reach"): an absolute promise whose known exceptions live elsewhere.**
- **Problem:**
  - The body promises that no record, revision field or ledger index reachable through IVG holds the target's IDs, values or messages.
  - The ontology itself documents exceptions: reifier delete records reached by neither target (`redaction.target.nodes`, bug-led-005); unattributed records left in clear under `complete` (`redaction.unattributed`, observed); actor fields kept by design; IVG's own snapshot archives and pre-upgrade ledger rows (the `…out-of-reach.other-copies` Q).
  - For the intro, search indexes also still answer with erased content (bug-srch-001).
- **Source:** `redaction.g5.md` blocks cited above; `receipts/native/redaction_unattributed_qualifier.json`; `ADR-0013:47-50`.
- **Proposed correction:** append to `redaction.purpose`:
  > The known exceptions are records the run cannot attribute to the target, reifier delete records, actor fields, and IVG's own snapshot archives and older ledger rows ([links]).

  In the intro, replace "cover everything IVG can reach" with "are meant to cover everything IVG can reach; the known gaps are listed under the purpose."

**M4 — `erasure.atomic` (D, "one transaction … completes or leaves the content untouched") and `erasure.entry-points`: large ID-list erases are several commits, and nothing records it.** (verified; new product finding)
- **Problem:**
  - Without a caller transaction, the store's `delete_nodes` and `delete_edges` call the Eraser once per 500 IDs. Each call commits on its own (`_eraser_txn`: "With none, each Eraser call owns its transaction").
  - `bulk_delete_nodes` batches by design. A failed batch is logged as "rolled back" and counted as wholly failed even when earlier chunks were already committed.
  - `erase_bare_nodes` commits per 10,000 IDs.
  - ADR-0004 requires all-or-nothing. Nothing in the ontology, the coverage map or the register mentions the chunking.
- **Source:** `stores/iris_sql_store.py:1302-1305`, `1347-1358`, `1451-1472`, `1484-1494`; `_engine/nodes_edges.py:2283-2298`; `Eraser.cls:1207-1208`, `1297-1304`; `docs/adr/0004-…md:21-23`.
- **Proposed correction:** keep the body's rule. Add a body exception:
  > Without a caller's transaction, erasing a list of node IDs or relationships commits once per 500 entries, so a failure keeps the earlier part erased; running it again finishes it.

  Also: put the `bulk_delete_nodes` reporting gap in Metadata, open a register bug, and add a coverage-map row.

**M5 — `structure.write` (bullet 2), `erasure.atomic.caller-transaction` and `search.bm25.write_lock`: whether a call joins the caller's transaction depends on how the engine was opened, and only some calls say so.** (verified sample)
- **Problem:**
  - `structure.write` states as a settled exception that erasing a graph or everything, a rebuild and the multigraph switch use the engine's own native connection.
  - The erasure page calls the same behaviour open. q-plt-006 ("Should whether a write joins the caller's transaction depend on how the engine was opened?") is linked only from the erasure Q.
  - Other calls also use `_iris_obj()` and so commit on their own on a `from_connect` engine:
    - BM25, VecIndex, PLAID and IVF writes;
    - temporal purge, latest-index rebuild, opt-out policy and backfill;
    - FHIR graph calls;
    - ledger `disable` and `set_strict`.
  - These calls are missing from every body. `search.bm25.write_lock` promises the caller's transaction is untouched without stating this condition.
- **Source:** `engine.py:1894-1943`; `_engine/vector.py:1578-1584` (and `:1738`, `:1845`, `:2045` per the helper); `_engine/temporal.py:619-824`; `receipts/native/erasure_caller_transaction_from_connect.json` (`native_is_dedicated: true`, the erase survives the caller's rollback); `open_questions.md#q-plt-006`.
- **Proposed correction:** in `structure.write`:
  > Some calls use the engine's own native connection: erases of a graph or of everything, a rebuild, the multigraph switch, named search-index writes, temporal purges and settings, and FHIR graph calls. They join the caller's transaction only when the engine was made on the caller's own connection; with `from_connect` they commit on their own. Whether this should depend on how the engine was opened is open.

  Also: add a child Q under `structure.write` linked to q-plt-006, and point the erasure Q at it.

**M6 — `install.bulk_load` (D, "the `BulkLoader` class follows neither") and `install.bulk_load.rebuild` (I, "A caller who … skips its rebuild step …"), against `structure.adjacency.bulk` (D, which lists the bulk loader among the paths that "must rebuild … before it returns, whether it succeeds or fails"): two owners disagree.**
- **Problem:**
  - Spec 252 FR-008 and ADR-0008 require every `%NOINDEX` bulk path to end in `%BuildIndices` before it returns. Only the ledger exemption for `BulkLoader` is documented.
  - The install page turns an observed gap into a decision: `load_nodes` and `load_edges` leave the rebuild to the caller.
  - Inside a caller's transaction, `bulk_load_session` leaves the rebuild to `sync()`, with `pending_sync` True until then. That documented rule is only in Metadata.
- **Source:** `specs/252-adjacency-functional-index/spec.md:119`; `docs/adr/0008-…md:36-39`; `bulk_loader.py:380-395`, `540-603`; `docs/USER_GUIDE.md:277-280`; `specs/213-…/contracts/ledger-api.md:93`.
- **Proposed correction:** make `structure.adjacency.bulk` the single owner. In `install.bulk_load`:
  > `BulkLoader` is outside ledger strict mode by documented decision. Like every bulk path that skips index upkeep, it must rebuild the indexes before it returns.

  Metadata:
  > Observed divergence: `load_nodes` and `load_edges` leave the rebuild to the caller.

  Add the caller-transaction bullet to `structure.adjacency.bulk`.

**M7 — `erasure.kept` (erasure.g5.md:38, "A graph erase keeps configuration …"): it contradicts two other owners.**
- **Problem:**
  - Multigraph mode is per-graph configuration, and a graph erase clears it. `structure.multigraph.switch` says so, and so does `Eraser.cls:243-244` (`Kill ^IVG.GraphMode(tKey)`).
  - The bullet "Stores that cannot be split by graph are emptied only by an erase of all graphs" conflicts with `search.erasure.indexes`, which requires per-graph erasure from VecIndex, PLAID and IVF (see M8).
  - The quarantine bullet is stated as decided, while `search.quarantine.retention` is an uncertain Q. Only the embedding quarantine is named; the document and edge-vector quarantines are not.
- **Source:** `Eraser.cls:243-246`, `300-302`, `754-757`; `graph-structure.g5.md` (`structure.multigraph.switch`).
- **Proposed correction:**
  > A graph erase keeps the graph's temporal-only settings and FHIR registration, so a re-ingest behaves as before; it clears the graph's multigraph mode and resets a FHIR graph's watermarks. The vector, document and edge-vector quarantines are never touched by any erase ([open question](search.g5.md#search.quarantine.retention)).

**M8 — `search.erasure.indexes` (I): it requires a per-graph erase from indexes that record no graph.** (verified)
- **Problem:**
  - VecIndex (`^VecIdx(name,…)`), PLAID and IVF record no graph, so "that graph's … entries" cannot be found.
  - The stage-A note listed only BM25 and IVF as obligations and left the rest open. Round 1 (R1-7) turned the Q into an I on the strength of ADR-0004/CONTEXT, but those sources do not say how a graph-less index is to be split.
  - `search.scope.indexes` also says an IVF index "covers exactly one graph".
- **Source:** `iris_src/src/Graph/KG/VecIndex.cls:7-12`; `PLAIDSearch.cls`; `_engine/vector.py:150-156`; `GraphStores.cls:113-131`; `intent/search.md` (lines 235 and 312).
- **Proposed correction:**
  > Erasing a graph removes its content from every BM25 index recorded for that graph. VecIndex, PLAID and IVF indexes record no graph; erasing every graph empties them, and what a single-graph erase must do to them is open.

  Add an `uncertain` child Q, and fix the IVF claim in `search.scope.indexes`.

**M9 — `erasure.entry-points.single-path` (D, "the old adjacency-only delete is removed"): untrue at the baseline.**
- **Problem:** `bulk_delete_adjacency` is still shipped and documented. It now deletes through the Eraser's relationship erase, but it is not refused in strict mode (bug-plt-006, bug-doc-007). The block's own Metadata says so.
- **Proposed correction:**
  > The old adjacency-only delete survives only as a deprecated name for a relationship erase, and must be refused in strict mode like the other erases.

**M10 — `graph.names.legacy` (Q, graph-scope.g5.md:90): an accepted ADR decision is demoted, and today's state is hidden.** (verified)
- **Problem:**
  - ADR-0003 is Accepted and says `verify_graph` reports existing violations. The block calls this a "provisional answer" and adds "so an operator can rename it", which no source says.
  - Only the Metadata says that nothing reports such graphs, that `verify_graph` itself refuses `"0"` (`GraphVerify.cls:41`), and that every adjacency rebuild fails on such a row (`TraversalBuild.cls:46-53`).
- **Proposed correction:** add a D block:
  > Graph verification must report any existing graph whose name is now refused. Today nothing reports them, verification itself refuses `"0"`, and a rebuild fails on such a row.

  Keep a Q only for "what an upgrade does with rows that carry a refused name".

**M11 — `algorithms.routing` (I, "only when all of these hold"): the list leaves out three guards.** (verified)
- **Problem:** the list omits:
  - The USER-namespace guard. The library reads USER's `^KG` whatever namespace calls it, so another namespace must get the Owner. Without the guard, an answer would come from another namespace's graph.
  - Native PageRank refuses when the default graph is in multigraph mode.
  - PageRank uses its Owner when a node has no edge.

  The namespace guard appears only in the sibling Q, which a rebuilder could read as optional.
- **Source:** `iris_src/src/Graph/KG/ArnoAccel.cls:242-262`; `stores/iris_sql_store.py:884-890`, `2393-2394`.
- **Proposed correction:** add bullets:
  > The call runs in the namespace the library reads, today `USER` only; anywhere else the Owner answers, because the library would read another namespace's graph. PageRank also uses its Owner when the default graph is in multigraph mode or a node has no edge.

  Keep the Q for whether that limit should be lifted.

**M12 — `search.embedding.other_model` (D): an open question is stated as a decision.**
- **Problem:** Stage-A open question Q2 asks whether a model mismatch should be refused or routed. The block does not say that setup by an engine configured for model B is refused once model A has claimed the original tables, even though B's writes would be routed. No source decides how setup and routing interact.
- **Source:** `_engine/schema.py:1211-1215`, `1485-1513`, `2568`; `intent/search.md` (line 319).
- **Proposed correction:** add
  > Today setup by an engine configured for another model than a table records is refused, although that engine's writes would be routed; whether setup should refuse or route is open.

  Tag `uncertain`, or split this into a Q child.

**M13 — `access.ledger_strict.bypasses` (I, "Any other path that writes nodes or relationships must be refused"): it overrides siblings that are still undecided.**
- **Problem:** Read literally, the rule covers FHIR sync and the MCP Cypher tool. Those are exactly what the sibling Q `access.ledger_strict.undecided` and `fhir.ledger` leave open. The rule also omits post-commit properties (H1).
- **Proposed correction:**
  > Any other path that writes nodes or relationships, except the undecided paths listed below, must be refused in strict mode and change nothing.

  Name post-commit properties in either this block or the undecided list.

**M14 — `access.retries` (D): observed behaviour is stated as a design decision.**
- **Problem:** No document states a retry policy, and the block's own Findings link (bug-plt-019) calls the behaviour a defect.
- **Proposed correction:** turn it into a Q:
  > May the server or client retry a call that writes? Today the server reruns a failed Cypher call once on a fresh engine, and the client retries a POST on a server error or timeout, so a write can be applied twice. Only a ledger commit with an idempotency key is protected.

**M15 — `query.writes.ledger` (D, "Cypher writes are not recorded in the ledger"): no document decides this.**
- **Problem:** Stage-A F10 left it for a human. The user guide names only engine methods, and CONTEXT.md says structural edges are "subject to the revision ledger".
- **Source:** `docs/USER_GUIDE.md:1107-1110`; `CONTEXT.md:56-59`; `intent/cypher.md` F10.
- **Proposed correction:** keep the text as observed behaviour:
  > Today Cypher writes are not recorded; strict mode refuses them before anything is written, and otherwise verification reports them.

  Tag `uncertain`, or add a Q.

**M16 — Provenance overclaims.**
- Six native-executor blocks are `human-verified`: `query.paths`, `query.native`, `.privileges`, `.reads-only`, `.equal-answers` and `.sql-first`. Their source is spec 253, which is still "Draft", and its "Decided 2026-10-20" lines name no decider. That falls outside the human authority rule in `sources.md:5`.
- `install.schema.concurrency` is `human-verified`, but no human source mentions concurrent setups. The "refused before it writes" clause is the model's proposed lock.
- **Proposed correction:** tag all of these `agent`. In Metadata, note "spec 253 is Draft; its decisions name no decider".
- Under-claims, which belong under Low: `temporal.latest.exact` ("purge and erase maintain the index", spec 255 Decision 1, Tom) and `temporal.structural.upgrade` (ADR-0015 "Decided" items) could be `human-verified`.

**M17 — `temporal.structural` (bullet "older installs keep an adjacency entry without a row"), plus a Q missing under it.**
- **Problem:**
  - Without the declared index, a temporal write that names a graph also writes an **unmarked** structural row plus nodes. No temporal delete or purge removes them, and they ignore the opt-out. This survives only in `temporal.optout.effect` Metadata.
  - The tested behaviour of `delete_edge` on a marked row is in no body: the row goes, the timestamps stay, and the next temporal write re-creates the row. The open question q-tmp-006 exists only as a Findings link, while the body says the triple is visible "while any of its timestamps exist".
- **Source:** `_engine/temporal.py:280-331`; `tests/e2e/test_254_purge_e2e.py:322-327`; `open_questions.md` (q-tmp-006).
- **Proposed correction:** reword the bullet:
  > Without the declared index, a write that names no graph leaves only an adjacency entry, which the next rebuild wipes; a write that names a graph also writes an unmarked structural edge and its nodes, which no temporal delete or purge removes.

  Add a Q:
  > May an explicit edge delete remove a marked structural edge while its triple still has timestamps? Today it does, and the next temporal write puts it back.

**M18 — `temporal.write.concurrency` (Q, "Provisional answer: none is recorded") against `temporal.latest.exact` (I, unconditional): the two contradict, and the Q drops recorded decisions.**
- **Problem:** Spec 254 Decision 2 (first write wins) and spec 255 Decision 1 (the newest-event index stays exact) state their rules with no exception for overlapping writers. The Q's lock rationale (ADR-0010) is about counters, not temporal writes.
- **Proposed correction:**
  > The recorded rules name no exception for overlapping writers, but temporal writes take no lock; whether overlapping writers are exempt or must be serialized is open.

  Point `temporal.latest.exact` at this Q.

**M19 — `temporal.write` (bullet "A direct write is not all-or-nothing"): observed behaviour as a rule, and a lost case.**
- **Problem:** The bullet states observed behaviour as an I rule, while the Q `temporal.write.partial-failure` keeps "a failed write leaves nothing" open. The caller-transaction case is lost: a direct write joins an open caller transaction, but a rollback leaves its counted statistics. `structure.write` defers temporal writes to this block, and this block says nothing on the point.
- **Source:** `_engine/temporal.py:12-17`, `322-323`; `docs/USER_GUIDE.md:238-259`; bug-tmp-010.
- **Proposed correction:**
  > Today a direct write opens no transaction of its own: alone it keeps what it wrote before a failure, and inside a caller's transaction it joins it, but a rollback leaves its statistics counted. Whether a failed write must leave nothing is open.

**M20 — `query.writes.adjacency` (I) and `structure.adjacency.undeclared`: the case without a declared index is missing.**
- **Problem:** Where the index is not declared, Cypher writes, `store_edge` and the store's `write_edges` never write the adjacency, so it stays stale until a rebuild. The realistic case is a half-finished setup, not "a namespace without IVG's classes": the compensation needs IVG's classes.
- **Source:** `_engine/query.py:1946-1967`; `_engine/nodes_edges.py:40-50`, `1221-1234`, `2547-2551`; `engine.py:703-723`.
- **Proposed correction:** in `query.writes.adjacency`:
  > Where the adjacency index is declared, a Cypher write updates it in the same transaction; where it is not, Cypher writes leave it stale until a rebuild.

**M21 — Q blocks: provisional answer and today's behaviour.**
- **Problem 1:** 24 of the 57 Q blocks neither name a provisional answer nor say there is none. The format requires "identify any provisional answer". Their register entries name none either.
  - access: `defaults.exposure`, `read_only.scope`, `ledger_strict.undecided`, `transactions`
  - install: `schema.concurrency.leftover`, `setup.failed_deploy`, `migration.schema.unrecorded`, `snapshot.ledger`, `bulk_load.limits`
  - algorithms: `routing.named_graphs`, `routing.namespace`, `proof.build`, `proof.ungated`
  - fhir: `sync.other_writers`, `ledger`, `sql_mapping.graph_scope`, `event.retry`
  - structure: `edge.delete.reifications`
  - redaction: `after-erasure.temporal`, `strict-mode`, `unattributed`
  - search: `fusion.text_leg`
  - temporal: `stats.cut-bucket`, `optout.stranded`
- **Problem 2:** Two Qs give the specification's answer but not today's observed behaviour, so a rebuilder may assume it is built:
  - `structure.rebuilt.rollback`: today the cached result stays current, observed in `graph_structure_algo_cache_rollback.json`.
  - `structure.multigraph.ledger`: today the ledger acts on the first matching row and deletes the surviving edges' adjacency, observed in `graph_structure_parallel_delete_rel.json`.
- **Problem 3:** `ledger.strict.fail-open` gives "allow" as its provisional answer. That only mirrors the code, while the 4.6.0 R206 fix treated one fail-open case as a defect (`CHANGELOG.md:701-705`).
- **Proposed correction:** add one sentence to each listed Q: "There is no provisional answer." For the two Qs above, add "Today …, observed". For `fail-open`, state "Provisional answer: none; today the check allows the write."

**M22 — Links between the findings register and the ontology.**
- **Problem 1:** nine register questions have no ontology link in either direction, so `check_findings.py` cannot see them. Each matches an existing block:
  - q-001 → `redaction.idempotency.other-tenant`
  - q-002 → `redaction.batches.readers`
  - q-003 → `redaction.strict-mode`
  - q-004 → `erasure.concurrency`
  - q-005 → `redaction.tombstone.digest`
  - q-007 → `erasure.count`
  - q-008 → `erasure.prefix-match`
  - q-009 → `redaction.after-erasure.temporal`
  - q-010 → no owner (H1)
- **Problem 2:** three Q blocks have no register entry: `fhir.sql_mapping.graph_scope`, `search.fusion.text_leg` and `redaction.idempotency.other-tenant` (the last until it is linked to q-001).
- **Problem 3:** `erasure.prefix-match` is a D with no `uncertain` tag, although q-008 keeps the separator rule open. Erasing with a bare prefix irreversibly erases a neighbouring tenant.
- **Proposed correction:**
  - Add the Findings links in the block Metadata, and an "Open statement: […]" line in each register entry.
  - Add register entries for the three Qs.
  - Tag `erasure.prefix-match` `uncertain` and add "Whether erasing by prefix should also require the separator is open."

**M23 — Coverage: capabilities with no owning block, and no declared gap.**
- **No owning block:**
  - Imports and exports: `load_networkx`, `import_graph_ndjson`, `import_rdf`, `load_obo`, `export_graph_ndjson`, `export_rdf`, `prov_export`.
  - Inference: `materialize_inference`, `retract_inference`.
  - The read API outside Cypher: `get_node(s)`, `count_nodes`, `list_graphs`, by-label reads.

  These names appear only in the strict-mode list.
- **Already flagged and never resolved:** the stage-A reconstruction check raised these as items 3, 4 and 7. The operations inventory records that imports commit per item or batch, so a failure keeps a partial import (`intent/operations.md:154-158`).
- **Not declared as a gap:** neither the coverage map nor the plan lists them, and `final-report.md` §6 still contains the placeholder `COVERAGE_GAPS`.
- **Proposed correction:**
  - Add `[D · install.import]`:
    > Imports and inference write one item or batch per transaction; a failure keeps what was written, and running the import again resumes it. Each is refused in ledger strict mode.
  - Add a minimal read-API block, or list both groups as declared coverage gaps in the coverage map and the final report.

**M24 — Install page: refusals and exceptions present in the sources are lost.**
- **Missing refusals and exceptions:**
  - Setup refuses a schema name whose class package already holds classes IVG did not create, before any DDL (`spec 262:201-203`; `schema_name.py:501-509`; `_engine/schema.py:2243`).
  - A restore refuses, before erasing anything, an archive taken from another storage layout. An archive with no layout stamp is accepted, and its IVG version is never checked (`_engine/snapshot.py:1086-1129`).
  - Grants on the four 4.5.x `SQLUser` views are not copied, because a view has no replacement (`_engine/legacy.py:249-250`; ADMIN_GUIDE:857-858). This contradicts "every privilege" in the `human-verified` block `install.upgrade.grants`.
- **Lost human clarification:** the 5% speed budget (spec 262 Clarifications, `spec.md:44`; FR-020a at `:290`; SC-006a at `:322`) is missing; `classes_follow` says only "as fast as before".
- **Proposed correction:** add one bullet each, in `install.schema.name`, `install.snapshot.scope` and `install.upgrade.grants`, plus a child `install.schema.speed`:
  > Using any IVG Schema must not make a write, erase or read more than 5% slower than 4.5.2; a benchmark gate checks it.

**M25 — `search.scope.indexes`: a lost case.**
- **Problem:** A BM25 index built before 4.0.0 covered every graph but reports graph `""`. The default graph's fusion therefore picks it as its own index without a warning and can return other graphs' node IDs. This contradicts "A BM25 index records which graph it covers". The helper checked the code; I did not re-check it.
- **Source:** `BM25Index.cls:603-611`; `_engine/vector.py:164-206`, `1403-1408`.
- **Proposed correction:** add a bullet:
  > A BM25 index built before 4.0.0 covered every graph but reports the default graph; rebuild it, because today the default graph's fusion reads it as its own.

### Low

**L1 — Metadata evidence that is out of date.** Each of these notes still says "suspected", "untested", "pending" or "will observe", although a native receipt or register entry now settles it:

| Block | Stale note | Current evidence |
|---|---|---|
| `redaction.audit` | F1 "suspected" | `redaction_concurrent_targets.json` OBSERVED_DEFECT |
| `redaction.batches.competing` | "suspected, untested" | `redaction_concurrent_targets.json` OBSERVED_DEFECT |
| `erasure.concurrency` | "Two suspected cases, neither tested" | first case is `erasure_caller_transaction_redaction.json` OBSERVED_DEFECT (bug-002) |
| `temporal.structural.ledger-nodes` | "suspected … should show" | `temporal_endpoint_nodes_verify.json` OBSERVED_DEFECT. V4 also shows a new condition: op order decides, so `[temporal, create_node]` refuses `node_exists` |
| `structure.rebuilt.rollback` | "Observed, suspected" | `graph_structure_algo_cache_rollback.json` OBSERVED_DEFECT |
| `structure.multigraph.ledger` | "suspected" | `graph_structure_parallel_delete_rel.json` OBSERVED_DEFECT |
| `redaction.after-erasure.default-graph` | F2 "suspected" | `redaction_default_graph_whole.json` |
| `redaction.unattributed` | "No test produces a non-zero count" | `redaction_unattributed_qualifier.json` produced one |
| `redaction.target.nodes` | "a register entry is pending" | bug-led-005 exists and is linked |
| `erasure.atomic.caller-transaction` | "The orchestrator's probe … will observe both transports" | `erasure_caller_transaction_from_connect.json` ran: dedicated connection; the erase survived the caller's rollback |

**L2 — Link labels that do not match the entry title** (220 register links checked; none missing; 2 mismatched):
- `redaction.g5.md:564` uses the label "bug-001".
- `redaction.g5.md:568` uses "open question q-006".

Use each entry's title.

**L3 — `redaction.tombstone.digest`:** ADR-0013:43 rejected a salted digest "for now", but that qualifier is only in Metadata. Wording: "For now the digest is unsalted, …". Link q-005.

**L4 — `ledger.lifecycle.genesis.shared-ids`:** cite CONTEXT.md "Decided 2026-10-20" (`CONTEXT.md:38-42`): the same ID in two graphs is two nodes. Genesis merging them conflicts with a human decision, not merely with verify.

**L5 — `redaction.batches` (human-verified):** the "under one second / 100,000 records under a minute" target is SC-003, agent spec text rather than one of Tom's decisions. It drops SC-003's condition, "on the laptop's enterprise container" (`spec.md:146-147`). Move it to an `agent` child that keeps the condition.

**L6 — `temporal.window.paging` (human-verified):** "freed … when its connection ends" is an agent inference. FR-009 says "closed when the iteration ends or is abandoned" (`specs/255-…/spec.md:137-138`).

**L7 — `graph.names`:** the bullet "codes 0 to 31 … are refused" is followed by "NUL (code 0) is removed". Write "codes 1 to 31 and 127 to 159", since NUL is stripped first (`GraphKey.cls:23-48`).

**L8 — `access.health`:** only the sample API's `/health` checks the schema record; the HTTP server's `/health` runs a count (`cypher_api.py:268-285`; `api/main.py:40-63`). The release labels for that check and for `install.legacy.ownership` say 4.7.0, but the change is in 4.6.3 (`CHANGELOG.md:431`, `493-509`).

**L9 — Useful links:**
- Only 4 Metadata entries link a Verus model, and no block carries `design-verified`. A rebuilder cannot tell from a block which statements have model evidence without opening `coverage.md`.
- The root links only the runbook. It does not link the findings files (`findings.md`, bugs, open questions).

Proposed fix: link each modelled block's coverage row, and link `findings.md` from the root.

**L10 — `temporal.structural.ledger` ("Temporal writes create no revisions") and `ledger.strict` ("the ledger does not govern temporal edges"):** both read as contradicting `temporal.ledger`, which lists temporal writes inside revisions. Write "Direct temporal writes create no revisions" and "strict mode does not govern direct temporal writes".

**L11 — Wording-level losses reported by the helpers** (spot-checked, not all re-verified):
- `query.compiled.fallback`: a failed build is retried after a stamp change, not only after a deploy (`Gen.cls:70-76`).
- `search.bm25.upgrade`: an interrupted upgrade leaves the `upgrading` flag set, so writers stay refused until the upgrade runs again. "On a schema-2 index it does nothing" is false while that flag is set (`BM25Index.cls:383-394`, `526-581`).
- `search.quarantine.placement`: an existing vector at the target refuses the move.
- `search.fusion.failed_leg`: API_REFERENCE:1000 still documents log-and-continue, and the fix is planned for 4.7.1 (`KNOWN_ISSUES.md:172-181`).
- `temporal.delete`: add "except in a bucket a raw purge has cut (open question)".
- `temporal.structural.adopt`: an adopting `create_edge` reports True, while `structure.edge.single` says a rewrite reports False.
- `structure.multigraph.off`: the per-engine mode cache is documented (`API_REFERENCE.md:2684`), so classifying it as bug-str-008 needs a justification.
- `redaction.batches.commits`: a record whose endpoints cannot be found is let through (`LedgerRedact.cls:258-268`).
- `redaction.call`: a mid-run `LedgerLockTimeoutError` or `LedgerDisabledError` leaves the earlier batches and the marker in place; it is not "nothing changed".
- `redaction.verify`: add the precondition "and nothing was written outside the ledger after the erase".
- `install.legacy`: the removing call refuses a caller's open transaction (4.7.0, `_engine/admin.py:389-392`).

## 2. Comparison with the pre-round-2 snapshot

`diff -r $RUN_DIR/snapshots/ontology-pre-round2/ .g5/ontology/` (saved as `$RUN_DIR/agents/R3-reader/snapshot.diff`, 50 lines) shows changes in **Metadata only**, in five files:

| File | Change |
|---|---|
| erasure | Findings links to bug-led-007 and bug-led-008 on `erasure.scope` and `erasure.entry-points.single-path`; an observed divergence note and a link on `erasure.prefix-match` |
| graph-structure | an observed divergence and a link to bug-str-016 on `structure.rebuilt.token` |
| ledger | a link to bug-led-009 on `ledger.unrecorded` |
| redaction | links to bug-led-008, bug-led-007 and bug-led-009 |
| search | a link to bug-srch-016 |

**Nothing was lost.** No body, tag, Q, condition or parent changed, no block moved, and no provenance tag changed.

**But the repairs stopped at Metadata.** The round-2 findings these lines implement (R2-1, R2-3, R2-4, domains R2-1 and R2-5) contradict body text that was left unchanged:
- R2-1: the "erasure removes them anyway" premise (H2).
- R2-4: the all-or-nothing commit and the strict-mode promise (H1).
- R2-3: `redaction.strict-mode` still says "Strict mode refuses the engine's erase methods"; bug-led-008 adds that the only delete under strict mode leaves documents, temporal, FHIR and search content. This is acceptable as Metadata, since the Q already covers it.

Round-2 R2-4 was adjudicated "incorrect intent". That category requires correcting the owning body; a Metadata link is not enough (uplift-review.md, step 3).

## 3. Mechanical checks

| Check | Result |
|---|---|
| `python3 .agents/guidance/scripts/check_findings.py .g5/Verus_verification .g5/ontology` | No problems found |
| `python3 .agents/guidance/scripts/check_ontology.py .g5/ontology` | 13 files, 348 blocks, 0 issues, 0 writing warnings |
| Link targets (scratch script `findings_titles.py`): every `Verus_verification/*.md#id` link in the ontology | 220 links, 0 missing anchors, 2 label mismatches (L2) |
| Q blocks: `uncertain` tag | 57 of 57 |
| Q blocks: provisional answer named, or "none" said | 33 of 57 (M21) |
| Q blocks linked to an open-question entry | 38 of 57. Of the other 19, 16 link a bug instead and 3 have no register entry at all (M22) |
| Register questions with no ontology link either way | 9 (q-001 to q-005, q-007 to q-010) (M22) |

The checkers do not compare link labels with entry titles, and do not notice register entries that name no ontology statement. That is how the M22 gaps passed.

## 4. Where the intent notes were wrong and the ontology is right (dismissed candidates)

- Provenance in ledger-history:
  - The note labels spec 256 user story 3 and the idempotency edge case as human. Only the consumer quote and Decisions 1–4 are human (`spec.md:8`), so the ontology's `agent` tags are correct.
  - The ontology's neutral "Decision N (Tom, 2026-10-22)" is safer than the note's "consumer-side Tom".
- The ontology's "the refusal names the live target" is correct: `target_live` carries the graph and prefix (`LedgerRedact.cls:67-72`).
- The note asked whether `BulkLoader` is ledger-exempt by design. It is (`ledger-api.md:93`), so `install.bulk_load.ledger` and `access.ledger_strict.surfaces` are correct.
- The note treated `Prop_Set` and `TemporalPolicy.DropRows` as hazards. `Prop_Set` writes only when the text is unchanged, and `DropRows` deletes only marked rows, so they do not leave stale stores. The ontology is right.
- The note tags `search.embedding.width` as O. USER_GUIDE 4.7.0 documents the column-width authority, so the ontology's D is right.
- In the search note, F-A3 ("evidence conflicts") is resolved by spec 236 FR-014a: the readers read an adjacency with no graph dimension. The Q is still valid and could cite it.

## 5. Limits

- **Helper findings:** five isolated helpers reported in text only, because the harness blocked their scratch files. I re-checked against code and spec every helper finding rated High, plus M4, M5, M8, M10, M11 and M12, and spot-checked M2, M24 and parts of L11. M25 and most of L11 rest on the helpers' citations.
- **Plain language:** judged by reading, not by a readability score. Most blocks are close to the target. The densest are `structure.degree.cache.uncommitted`, `redaction.target.nodes` and `query.native.equal-answers`; they are understandable but could use a defined term.
- **Coverage claim:** limited to the declared inventories (the stage-A notes and the operations inventory). It does not mean every requirement has been discovered.
- **Not reviewed:** the Verus models, receipts and coverage map, except where an ontology statement depends on them.
