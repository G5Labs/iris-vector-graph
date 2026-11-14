# A-history: revision ledger, erasure, redaction, replay/verify/export

Worker A-history, stage A, product pin `3eaa79cf`, written 2026-11-13. This worker only read the product. It ran no tests and did not touch IRIS.
Tags: **(H)** human requirement or answered question, **(D)** accepted design decision, **(O)** observed implementation only, **(P)** proposal.
"Live" means the test needs IRIS (`requires_database`). "Mocked" and "source-text" tests need no database.

## Scope and sources inspected

| Locator | Revision/date | Authority | Inspected portion | Follow-up |
|---|---|---|---|---|
| `specs/256-ledger-tenant-redaction/spec.md` | a140ed78 (draft), 42907b21 (decisions), 2026-10-21/22 | H, secondhand: the consumer quote and "Decisions (Tom, 2026-10-22)". The rest is agent-drafted. | Whole file, plus both diffs | The spec has internal contradictions after the decisions (F6). |
| `specs/256-.../plan.md`, `tasks.md` | 2b8ea46d | D (design by the same committer) | Whole | All tasks were already marked `[x]` when committed, 1 s before the implementation. History cannot show that the tests were written first. |
| `specs/256-.../research`, `decisions` | — | — | **Absent at pin.** Only spec, plan and tasks exist. | — |
| `docs/adr/0004`, `0013` | 2026-09-14 / 2026-10-22 (2b8ea46d) | D | Whole | — |
| `docs/adr/0003`, `0006` | 2026-09-14 / 2026-09-19 | D | Whole | — |
| `specs/213-graph-revision-ledger/contracts/*` | 04bf1c67 (4.1.1) | D (wire contract) | Whole | Not updated for spec 256 (F6). |
| spec 213 `spec.md`, `research.md`, `data-model.md` | — | — | **Unavailable at pin.** They are cited by ADR-0013:22, `errors.py:1`, `LedgerRevision.cls:3` and commit abf4e6eb ("research.md:108-112"). | Ask for the original. FR-023 and FR-047 are known only through citations. |
| `docs/dev/notes/for-opsreview/IVG-OPSREVIEW-BRIEF.md` | updated 2026-10-25 (0cf240b5, moved 1d1d80d2) | IVG-side summary of the consumer, not consumer text | Lines 1-70, 120-130, 160-170 | Its usage line 125 is wrong (F3). |
| `CONTEXT.md` History, Core concepts | pin | D (glossary) | Lines 12-62, 181-217 | — |
| `CHANGELOG.md` 4.2.0–4.7.0 | pin | O/D (release notes) | Every ledger, erase, redact or verify hit (grep). Read 4.3.0 at 2804-2815, 4.4.0 at 2646-2668 and 2767, 4.6.0 at 1138-1148, 1200-1209 and 2210-2227, 4.6.4 at 415-425, 4.7.0 at 30-40 and 76-86 | — |
| `docs/USER_GUIDE.md` §3, §9 | pin; 4.3.0 text in 9afe0822, removed by 9b313a2c | D/O | Lines 285-310, 440-455, 1052-1135 | Retries claim is wrong (F7). |
| `docs/API_REFERENCE.md` | pin | O | Lines 2352-2364 | Documents no `GraphLedger` method (`redact` and `verify` are absent). |
| `docs/ADMIN_GUIDE.md` | pin | O/D | Lines 249-317 (inventory), 966-991 (backup and snapshots) | Snapshots carry `^IVG.Ledger` (F8). |
| `docs/KNOWN_ISSUES.md` | pin | O | grep | Nothing on erase or redaction. |
| Worked-example commits | a140ed78, 42907b21, 2b8ea46d, e4b5eef5, 9afe0822 | as above | Messages and the spec, ADR and Ledger diffs | — |
| Later commits | `e4b5eef5..3eaa79cf` on the ledger, Eraser and LedgerApply | O, with a defect narrative | Messages for 7110a5cf, 71fb9924, 0ac15def, 1ff2666e, 6525db9b, c53c654a, 41b0901d, aca5aedd, aad50087, abf4e6eb, 0cf1524f. Diffs for abf4e6eb (Ledger.cls) and aad50087 (Eraser.cls) | — |
| Code | pin | O | `LedgerRedact.cls` (whole), `Ledger.cls` (whole), `LedgerRevision.cls` (whole), `LedgerGenesis.cls` (whole), `LedgerApply.cls` 60-70, 335-372 and 610-695, `Eraser.cls` 1-306, 322-352, 467-680 and 1107-1143, `GraphKey.cls`, `ledger/client.py` 138-760, `replay.py` 18-300 and 575-879, `errors.py`, `guard.py`, `export.py`, `changeset.py` 340-393, `_engine/nodes_edges.py` 1473-1595, `_engine/legacy.py` 606-646 | — |
| Tests | pin | evidence | `tests/integration/test_256_ledger_redaction_e2e.py` (whole, live), `test_256_ledger_redaction_perf.py` (live, `-m perf`, excluded by default: `pyproject.toml:266`), `tests/unit/test_256_ledger_redaction.py` (index; mocked and source-text), `test_eraser_failures.py` (live, scratch IVG236), `test_edgescan_ledger_erase.py:113-133` (live), `test_ledger_us04_idempotency.py` (live) | — |

## Capabilities

### C1. What the consumer asked for, and what the maintainer made of it (Question 1)

The request reaches the repository third-hand. In the source chain, OpsReview's agent posted on an "agent bus" on 2026-10-20, priorities were restated "on Tom's go-ahead", and IVG's agent wrote spec 256 (`spec.md:8-14`). The only consumer words quoted are:

> "a ledger operation that redacts or removes a Tenant's revisions and keeps the chain verifiable (a tombstoned revision with its hash kept)"

The motivation is OpsReview spec 055's tenant-erasure receipt, which had to report `^IVG.Ledger("rec")` and `ledger_revisions` as out of reach (`spec.md:8-13`). OpsReview spec 055 and its "receipt shape" (`spec.md:136`) are external and unavailable. The brief names Tom as the "OpsReview team" (`IVG-OPSREVIEW-BRIEF.md:8`), so the four recorded decisions come from the consumer-side human, recorded secondhand (H).

| Consumer element | Disposition | Evidence |
|---|---|---|
| "removes … revisions" | **Rejected.** Delete-and-renumber would break seq/id references and external copies. | ADR-0013:41 (D) |
| "redacts … revisions" | **Reinterpreted** at record granularity: one tombstone per `(seq, ordinal)`. Revision rows stay; four free-text fields are cleared. | ADR-0013:12-15 (D); spec Decision 2 (H) |
| "a Tenant" | **Reinterpreted** as a target `(graph, optional prefix+separator)`. Ledger node records are graph-blind, so one tenant is two calls: `redact(g)` plus `redact(None, prefix=t)`. | ADR-0013:37 (D); plan.md:9 (D) |
| "keeps the chain verifiable" | **Reinterpreted.** No hash chain exists. "Verifiable" means `verify()` replay equals the store. | spec.md:29-31 (D, a code reading); ADR-0013:35 |
| "with its hash kept" | **Accepted per record:** unsalted SHA-256 of `Ledger.CanonicalRecord`. A salted digest was rejected "for now". | ADR-0013:14, 43, 49 (D) |
| Audit of the redaction | **Decided (H):** option (b), a content-free ledger revision of kind `redaction`. The draft had said "not a ledger revision" (a140ed78 FR-009). | spec.md:152-154; diff 42907b21 |
| Spanning revision metadata | **Decided (H):** clear on *any* redacted record. The recorded tradeoff "loses t2's commit message" was accepted. | spec.md:155; a140ed78 open question 2 |
| Batching | **Decided (H):** batches with a redaction-in-progress marker that "readers and `verify()` honour". The draft line "atomic from a reader's view" was dropped. | spec.md:156; 42907b21 diff of edge cases |
| Exports, journals, backups | **Deferred / out of reach.** The receipt names them. | spec.md:159-161; FR-008 |
| Request 2 (tenant erase of temporal tiers in a shared graph), request 5 (journal volume) | **Deferred** | spec.md:161-163 |
| Consumer acceptance | No consumer-authored acceptance exists. The IVG-side brief says "No further IVG changes required" (`BRIEF.md:165`). | — |

### C2. Recorded decisions, item by item (Question 2)

| Topic | Governing statement | Code (O) | Agreement |
|---|---|---|---|
| Audit record | (H) Decision 1. (D) ADR-0013:16: kind `redaction`, one `redact` record per seq, counts, `sha256(graph NUL match)`. (D) plan.md:33-40. | `LedgerRedact.cls:420-441` (`FinalInLock`), records built by `LedgerApply.Rec` at `:427`, written via `Ledger.WriteRevision` at `:437` | Matches. It also bumps `CommitsOk` (`Ledger.cls:562`). The spec edge case "the revision count does not change" (`spec.md:106`) predates Decision 1 and is now false (F6). |
| Shared revision metadata | (H) Decision 2: clear on any. (D) ADR-0013:15 lists `message, source, correlation_id, idempotency_key`. The FR-004 text still says "every record" (`spec.md:121`). | First tombstone per seq calls `ClearRevision` (`LedgerRedact.cls:345-346`, `353-378`) | Code follows Decision 2. FR-004 and Acceptance 2 ("kept which Decision 2 clears", `spec.md:57-58`) were never reconciled (F6). |
| Immutability exemption | (D) ADR-0013:20-29: four conditions. | `LedgerRevision.cls:87-101`. `%IVGLedgerRedaction` is set and killed at `LedgerRedact.cls:367-374`. | Matches. Object path and DELETE stay closed (`:104-123`). |
| Batching and marker | (H) Decision 3. (D) ADR-0013:18: "each batch is one transaction under the head lock". | `Batch` `:275-300` (TSTART, `Lock +^IVG.Ledger("head"):30`, TCOMMIT). Scan cap is `pBatch*20` (`:35`, `:213`). | Matches with one difference. The marker is created at the **first tombstone**, not at run start (`:322-324`), so a run that has not yet matched anything has no marker (C5). |
| What readers see between batches | (D) ADR-0013:18: "Record readers raise", `verify()` returns `redaction_in_progress`. | `client.py:687-739`: `get_revision`, `diff`, `reconstruct` and `export_reconstruction` check once at entry. `replay.py:812-823` handles verify. `history()` (`client.py:585-629`), `stats()` and the SQL procedure `ledger_records` (`SqlProcs.cls:206`) do **not** check. | Partial. The check is made once before the reads (time-of-check to time-of-use, F5). |
| Targeted commits between batches | (D) ADR-0013:18: "a commit with a record in the target is refused". | `Ledger.cls:514-518` → `LedgerRedact.BlocksCommit` `:258-269`, after `ApplyAll`, before `WriteRevision` | Covers ledger commits only. Non-ledger engine writes and Eraser calls are not blocked. Records that `Matches` returns -1 for (unknown endpoints) are let through. |
| Competing redactions | (D) ADR-0013:18: "A redaction of a different target is refused until the first one finishes." | The marker digest check is **outside the lock** (`:202-205`). `BatchInLock` never re-checks the digest (`:322`). | SUSPECTED race (F1). |
| Resumption of the same target | (D) ADR-0013:18: "Re-running the same redaction resumes it." | Same digest passes `:203`. The scan restarts at the first record and skips tombstones (`Matches` `:92`). Counters persist under `("redacting","n"/"revs")`. The run-local cursor `("redacting","stmt")` keeps the endpoints of tombstoned creates (`:338-341`). | Matches. No abort operation exists (F12). |
| Refusal of a live target | (H, draft US3) "refused while the tenant's content is still live". FR-005 says "non-tombstoned live statement or node". (D) ADR-0013:17. | `LiveRows` `:149-178` counts SQL rows in `nodes`, `rdf_labels`, `rdf_props` and `rdf_edges` only. Checked at entry outside the lock (`:206-210`) and again in `FinalInLock` under the lock (`:413-415`). | Partial. The temporal index, the ledger `stmt` index and graph-blind nodes for a whole-default-graph target are not checked (F2, F15). |
| Default-graph node targeting | (H) edge case `spec.md:99-101`. (D) ADR-0013:37 and plan.md:9-10 ("node-liveness check for a default-graph target is graph-blind"). | `MatchString` `:48-53`, `HasPrefix` `:61-64`. Graph-blind liveness applies to **prefix** targets only (`:145-148`, `:161-162`). | The prefix rule matches. The plan's graph-blind rule is implemented for prefix targets but not for `redact(None)` with an empty prefix (F2). |
| Idempotency keys of redacted revisions | (H, draft edge case) "removed or re-keyed by digest … must not replay into an erased graph" (`spec.md:104-105`). (D) ADR-0013:15, plan.md:25 and 27. | `ClearRevision` kills `("idem",key)` and sets `("idemRedacted", sha256(key)) = seq` (`:359-365`). `CommitInTxn` refuses with `idempotency_redacted` (`Ledger.cls:466-473`). The Python exception is `IdempotencyRedactedError(IdempotencyConflictError)` (`errors.py:129-134`). | Matches. Applies to *every* key of a spanning revision, including the other tenant's (F10). |

### C3. Ledger commit, genesis, guard, verify, export (Question 5)

- **Transaction and lock (O):** `Ledger.Commit` (`Ledger.cls:397-415`) opens TSTART; `CommitInTxn` takes `Lock +^IVG.Ledger("head"):30` (`:440`). The check order is lock → state → idempotency → expected_head → size → apply → redaction marker → `WriteRevision` (`:440-527`), which agrees with the header (`:17`).
  - Before 4.7.0 a commit refused `$TLevel>0` (spec 213 FR-047, which the commit message quotes). Since abf4e6eb it nests in the caller's transaction. The unlock is deferred until the outer transaction ends, so the head stays locked until the caller commits or rolls back (`:390-396`; CHANGELOG 4.7.0 lines 80-85).
  - `Enable` (`:261`) and `Redact` (`LedgerRedact.cls:187`) still refuse an open transaction. The Python side refuses on every engine since 0cf1524f (`client.py:268-279`).
- **Sequence and ordering (O):** `seq = head + 1` under the lock. `parent_id` is the previous head id. `WriteRevision` writes the records, the `LedgerRevision` row, head, `revById`, `idBySeq` and stats in the caller's transaction (`:532-567`). The 4.7.0 claim is that a rollback leaves no seq gap (CHANGELOG:83). That holds because the head global rolls back with the transaction.
- **Idempotency (O):**
  - Key bound with an equal fingerprint: replay. `RevisionResponse(seq, 1, {})` returns **empty `stmt_ids`** (`:457-461`), while the contract promises the "original outcome" (`ledger-api.md:26`).
  - Key bound with a different fingerprint: `idempotency_conflict`.
  - Key in `idemRedacted`: `idempotency_redacted`.
  - Idempotency is checked before `expected_head` (FR-019, tested live at `test_ledger_us04_idempotency.py:64-70`).
  - The fingerprint covers `{actor, actor_type, ops}` only (`changeset.py:365-386`). A retry with another message or other `post_commit_properties` replays.
  - The client re-applies `post_commit_properties` even on a replay (`client.py:431-436`).
  - **No key means no replay.** USER_GUIDE:1102 says otherwise (F7).
- **Error contract (O):** `errors.py:156-172` maps the wire codes. Commit codes added by spec 256 are `idempotency_redacted` and `redaction_in_progress`. Redaction-only codes are `target_live` and `invalid_target`. The schema `CommitError.error` enum (`changeset.schema.json`) lacks all four, `RevisionInfo.kind` lacks `redaction`, and the `MutationRecord.op` enum lacks `redacted`, `redact` and `create_temporal_edge` (F6).
- **Genesis (O):** `LedgerGenesis.Capture` reads `nodes`, `rdf_labels` and `rdf_props` from **all graphs** with record graph `""`. It reads `rdf_edges` with the row's `graph_id`, which is `$Char(0)` for `''` (CHANGELOG:2767-2769). Temporal-marked rows are skipped (`LedgerGenesis.cls`, R094/71fb9924).
  - Re-enable after disable writes no revision. It returns `adoption_needed`, and the client runs `verify(adopt=True)` (`client.py:281-297`).
  - While a redaction marker exists, that adoption is silently skipped (F14).
- **Node scope (O, fixed in 4.6.0 R290 c53c654a and R281 41b0901d):** ledger node operations read and write the default graph's rows only. Before 4.6.0 they matched by id across graphs, so a `set_prop` rewrote another graph's value.
- **Guard (O):** `guard.py:24-86` is a client-side strict-mode check. It caches `Meta()` for 5 s and **fails open** on any probe error (`:43-56`).
  - It blocks `erase_graph`, `delete_nodes_by_prefix` and `erase_all` (`nodes_edges.py:1513`, `:1552`; `iris_sql_store.py:1433-1435`). Under strict mode the documented erase-then-redact sequence is unavailable unless strict is turned off (F11).
  - It does not guard `ledger.redact`, `BulkLoader` or raw SQL.
- **Verify (O):** `replay.verify` (`replay.py:806-867`):
  1. reads `head()` and the marker;
  2. replays records 1..head over paged SQL calls;
  3. reads the canonical tables with no lock and no snapshot;
  4. compares nodes **graph-blind** by `node_id` (`read_canonical` `:588-642`; `compare` `:645-698`) and relationships by `(s,p,o,graph)`, with default-graph spellings unified (`:137-142`, 7110a5cf).

  It excludes temporal-marked rows on both sides (`:612-617`, `:792-803`) and reserved properties. It does **not** compare statement ids, and it does **not** cover the temporal index (`GraphState.apply` ignores `temporal_edge` records, `:170-210`). An `adopt=True` commit carries no `expected_head` (`:851-858`).
- **Export (O):** `export_reconstruction` writes the reconstructed *state* as NDJSON (`export.py`), not records. It cannot carry tombstone ordinals or digests.

### C4. Erasure (Question 4)

| Claim | Status at pin | Evidence |
|---|---|---|
| One transaction removes content from every store | (D) ADR-0004:10-12; CONTEXT:194-203. (O) `EraseGraph` deletes `rdf_labels`, `rdf_props`, `docs`, `kg_NodeEmbeddings(_optimized)`, routed embedding tables, FHIR rows, `rdf_reifications`, `kg_EdgeEmbeddings`, `rdf_edges` and `nodes`, then `Adjacency.RemoveGraph`, `TemporalIndex.EraseGraph`, `^KG` prop/label/deg2p, `^IVG.GraphMode`, `^IVG.AlgoCache`, `InvalidateDerived`, `EraseLedgerFor` (`Eraser.cls:56-256`). | It keeps `^IVG.TemporalStructural` (configuration, `:244-246`), `^KG("labelset")` and `embedding_quarantine`. It drops claimed routed tables **after** TCOMMIT and swallows a drop failure (`:262-300`, deliberate). The store list is derived from `GraphStores`, checked by a source-text unit test (`Eraser.cls:14-16`). |
| Live ledger references go with the content | (D) ADR-0004:17-19 | `EraseLedgerFor` (`:1117-1143`) kills **every** `stmt` entry of the graph, live and closed (plan.md:12), together with its `tuple`. `EraseEdgeRow` (`:666-678`) kills the live statement via the tuple, as used by `EraseNodes`, `EraseNodeIds` and `EraseEdges`. Tested live for tuple removal only (`test_edgescan_ledger_erase.py:113-133`). |
| Records spanning graphs survive | (D) ADR-0004:14-15, 27-32 | `rec` is never touched (`Eraser.cls:26-33`, `:812`). Observed live: needles are still found after erase (`test_256…e2e.py:262-265`). |
| Failure rolls back | (D) ADR-0004:21-23 | Catch → `While $TLevel > tTxnLevel { TROLLBACK 1 }` (`:259-262`), changed in aad50087 (4.6.4) from rolling back every level. Tested live in `test_eraser_failures.py:90-128`, which asserts **SQL row counts only**, not globals or ledger statements. |
| "A returned 0 means nothing matched" | (D) ADR-0004:23. Docstring `nodes_edges.py:1497-1498` | **Corrected.** The return counts only `nodes` and `rdf_edges` rows (`Eraser.cls:37-43`, `218-225`). An erase that removes only labels, props, docs, embeddings, temporal entries, `^KG` or closed ledger statements returns 0. |
| Atomic against concurrent writers | Not stated | The Eraser never takes `^IVG.Ledger("head")`. A ledger commit can interleave between `DELETE rdf_edges` and `EraseLedgerFor`. Since 4.6.4 the erase nests in a caller's transaction, and readers at READ UNCOMMITTED (abf4e6eb message) see it before it commits (F4). |

### C5. Redaction run: entry → guards → writers → commit → readers (as built)

1. **Entry.** `ledger.redact` (`client.py:633-680`) refuses a caller transaction, then calls `LedgerRedact.Redact` (`LedgerRedact.cls:185-239`).
2. **Guards outside any lock:** `$TLevel` (`:187`); state never-enabled or disabled (`:188-190`); empty separator (`:191`); `GraphKey.ForName` (`:193-196`); marker digest (`:202-205`); `LiveRows` (`:206-210`); `PrePass` for prefix targets, a full read-only scan of `rec` (`:116-141`, `:212`).
3. **Batches (`:216-226`).** Each batch:
   - opens TSTART and takes the head lock (`:281-283`);
   - re-checks state (`:305`);
   - scans up to `pBatch*20` records;
   - `Matches` (`:89-112`) picks target records;
   - the first match creates the marker (`:322-324`);
   - `Tombstone` (`:333-347`) writes `$LB("redacted", sha256(CanonicalRecord), flags, op, entityKind)` and increments counters with `Set`, so they roll back with the batch;
   - the first tombstone of a seq runs `ClearRevision` (`:353-378`): it moves the idempotency key, sets `redactedRev`, and runs one SQL `UPDATE` under `%IVGLedgerRedaction`;
   - TCOMMIT and unlock (`:288-289`).

   On error the cursor is restored (`:297`) and the marker is left in place.
4. **Final (`:384-442`).** One transaction under the lock: state, liveness re-check, `DropStatements` (`:446-471`), redaction revision, kill marker. When there is no marker and no statements, it writes nothing (`:418`). That is the "re-run reports 0" path.
5. **Receipt (`:482-511`).** Counts, `unattributed_records` (per call), `out_of_reach` (three fixed strings).
6. **Readers after the run.** `ledger_records` rows a tombstone as `op="redacted"` with an empty id, attribute and graph, the digest and `redacted_op` (`Ledger.cls:635-637`). Python `MutationRecord.redacted` (`replay.py:51-74`). `contributes()` (`:24-26`) skips tombstones and `revision` records in apply, diff and reconstruct. `Diff.redacted` lists tombstones (`:484-487`).

**Cases that change the outcome:**

- Spanning revision (graph A and graph B records): only A's become tombstones; the metadata is cleared.
- A node record is always graph `""`, so a named-graph target never matches one.
- Genesis rel records spell the default graph `$Char(0)`. `Matches` strips it (`:93`).
- `redact(None, "")` targets the whole default graph, including every graph-blind node record (F2).
- Prefix equal to its separator-suffixed form: same digest (test `:411-415`).
- `acme` against `acme-health|` (test `:400-409`).
- Qualifier records with unknown endpoints become `unattributed` and are left in place (F9).
- `max_batches` pause, lock timeout, disable between batches, or a target that is live again at Final: each leaves the marker; a re-run resumes.
- Process death mid-batch: IRIS rolls the batch back; the marker persists if an earlier batch committed.
- Two different targets started concurrently (F1).
- A non-ledger write into the target during the run: not blocked; Final refuses with `target_live`; recovery means erasing again.
- Upgrade from 4.5.x into a non-default schema: legacy rows are left behind (F8).

### C6. Replay and verify equality: what is promised and what is observed (Question 3)

- **Promised (D).** ADR-0013:17: after `EraseGraph` (or `EraseNodes`) and then `Redact`, `verify()` reports `equal`; after the erase alone it does not. Spec FR-007 and SC-002.
- **Implicit preconditions, stated nowhere as such (P to record):**
  1. Replay equalled the store before the erase.
  2. The whole erased content is covered by the redacted targets, which for a tenant means both `redact(g)` and `redact(None, prefix)`.
  3. No non-ledger writes happened.
  4. Equality is verify's comparison as described in C3, which omits the temporal index and statement ids.
- **Observed live (`test_256_ledger_redaction_e2e.py`):**
  - verify result `diverges` after `erase_graph(GA)` plus `delete_nodes_by_prefix("tenantA|")`, then `equal` with no differences after both redactions (`:429-434`);
  - digest equals sha256 of the **server's** `CanonicalRecord` captured before the redaction, and the tombstone set equals the set of records containing tenant-A needles (`:436-450`);
  - the canonical form of a tombstone (`:452-458`);
  - `reconstruct` at every seq has no tenant-A strings (`:460-465`);
  - `diff.redacted` equals the tombstones (`:467-473`);
  - SC-001 needle scan of `^IVG.Ledger` plus `ledger_revisions`/`ledger_stats` and every reader (`:267-274`);
  - tenant-B-only records and revision rows unchanged (`:276-283`);
  - a no-op re-run with a full snapshot (`:310-318`);
  - the redacted-key retry is refused with a snapshot (`:336-348`);
  - the trigger refuses outside updates (`:350-372`);
  - pause, marker, refused targeted commit, refused other target, resume (`:504-541`);
  - SC-002/003 perf, opt-in only (`perf:45-126`).
- **Not observed:**
  - concurrent processes: a competing redaction, a commit or reader racing a batch, verify(adopt) racing Final;
  - crash mid-batch (the pause is a clean `max_batches` stop);
  - lock timeout, disable between batches, Final `target_live`;
  - genesis-captured content (the fixture enables on an empty store);
  - adoption records, temporal edges and `create_temporal_edge` records, reification cascades;
  - `redact(None)` without a prefix;
  - strict mode, a non-default IVG Schema, `unattributed_records > 0`;
  - recomputing the digest from a Python-visible or exported record;
  - index globals (`^Graph.KG.LedgerRevisionI`) and snapshots in the needle scan.
- **Explicitly excluded (D/O):** pre-redaction `export_reconstruction` files, IRIS journals and backups (ADR-0013:48; receipt `LedgerRedact.cls:505-508`). The marker holds the target in plain text while a run is open, and journals keep it (ADR-0013:51). **Not named but reachable:** `save_snapshot` archives (they contain `^IVG.Ledger` and the ledger storage, ADMIN_GUIDE:981-991) and the 4.5.x `Graph_KG` ledger rows kept by the R114 upgrade copy (`legacy.py:606-614`) (F8).

### C7. Changes after 4.3.0 and the defects behind them (Question 6)

`LedgerRedact.cls` is unchanged since e4b5eef5. `idemRedacted` was introduced only by e4b5eef5 (`git log -S`).

| Commit (release) | Behavior change | Motivating defect |
|---|---|---|
| 7110a5cf (4.4.0, CHANGELOG:2767) | verify keys genesis `"\u0000"` and table `None` as the default graph | verify right after enable diverged for every default-graph relationship (found by OpsReview, BRIEF:16-17) |
| 89fa9bbd, bc4b575b (4.4.0, CHANGELOG:2648-2664) | EraseGraph decides on `^NKG` before the rows go; EraseNodeIds keeps `^NKG` when nothing interned was erased | stale `^NKG` after erase_graph counted far ends of erased edges; needless `^NKG` drops during OpsReview purges |
| 1ff2666e R106 (4.6.0) | `enable()` passes the IVG Schema | genesis read the compiled default schema |
| 0ac15def R114 (4.6.0) | setup copies 4.5.x `Graph_KG` ledger rows into the new schema; verify drops temporal-marked statements from the replay | after an upgrade, `history()` returned `[]` and verify raised "revision row missing" |
| 71fb9924 R094 (4.6.0) | genesis skips temporal-marked rows | verify diverged right after enable on a graph with a temporal edge |
| 6525db9b R150 (4.6.0) | `idx_ledger_correlation` declared in the class | a class reload dropped the index |
| c53c654a R290, 41b0901d R281 (4.6.0) | ledger node ops and `post_commit_properties` act on default-graph rows only | node ops matched by id across graphs and rewrote another graph's data. This makes "the ledger keeps nodes in the default graph" (graph-blind node records) load-bearing for redaction. |
| aca5aedd R276 (4.6.0) | `except Exception` swallows removed on erase and commit paths | failures before the Eraser and in the post-commit DELETE passed silently |
| 3984854a R206 (4.6.0) | guard probe works for a writer without dictionary SELECT | the guard read "never enabled" and let writes through a strict ledger |
| c4122daf (4.6.0) | an Eraser cursor error is no longer taken as end of rows | a partial erase could be reported as success |
| aad50087 (4.6.4) | Eraser and Ledger roll back only to the level they found; writes nest in the caller's transaction | IVG committed or rolled back the caller's transaction |
| abf4e6eb (4.7.0 row 4) | `Commit` nests in the caller's transaction (FR-047 refusal removed); head locked until the caller ends | a caller's ROLLBACK left the revision and its node (from_connect), or the commit refused |
| 0cf1524f (4.7.0 row 3b) | `enable()` and `redact()` refuse a caller transaction on every engine | from_connect ran them outside the caller's transaction |

### C8. Seed-claim check against `experiment/g5-verus/index.md` (Question 7)

| Row | Verdict | Evidence |
|---|---|---|
| **Live erasure:** "Successful erasure removes content and live ledger references together" | Confirmed (and goes further: closed statements too) | `Eraser.cls:256`, `1117-1143`, `666-678` |
| "Failure rolls back" | Confirmed for its own transaction level; SQL rows observed only | `:259-262`; `test_eraser_failures.py:90-101`. Post-commit DDL is outside (`:262-300`). Inside a caller transaction, completion is decided by the caller (4.6.4). |
| "Historical operations may span graphs, so their ordinals survive" | Confirmed | ADR-0004:27-32; `Eraser.cls:26-33` |
| "A returned zero means nothing matched" | **Corrected:** zero means no `nodes` or `rdf_edges` row was removed | `Eraser.cls:37-43`, `218-225` |
| **Redaction and isolation:** "refuses a live target" | **Corrected/qualified:** SQL content rows only; checked outside the lock, then again at Final; whole-default-graph target not graph-blind; temporal-only content not seen | `LedgerRedact.cls:149-178`, `206`, `413`; F2, F15 |
| "replaces matching records in place with tombstones" | Confirmed, except unattributed records (left in place) | `:316-327`, `:333-347`; F9 |
| "Other tenants' records … retain their bytes, while four free-text fields … are cleared" | Confirmed live, with nuance: bytes compared as `CanonicalRecord` JSON; spec SC-004 "revision rows byte-identical" is false for spanning revisions by Decision 2 | e2e `:276-308` |
| "Default-graph node targeting uses a separator-delimited prefix" | Confirmed. Nuance: node records are *only* in the default graph, so `redact(g, prefix=…)` never reaches them (the brief gets this wrong) | `:48-53`, `:96`; BRIEF:125; F3 |
| **Retries and interruption:** "A previously used, redacted idempotency key cannot re-create content" | Confirmed live. Extends to the other tenant's key on a spanning revision (untested) | `Ledger.cls:466-473`; e2e `:336-348`; F10 |
| "the marker governs readers, targeted commits and competing redactions" | **Corrected:** the marker exists only after the first tombstone; Python record readers check once at entry; `history`, `stats` and SQL `ledger_records` are ungoverned; only ledger commits are blocked; the competing-run check is outside the lock | F1, F5 |
| "The same target can resume" | Confirmed live (sequential); no abort operation | e2e `:534-537`; F12 |
| **What verification means:** "Readers show tombstoned ordinals" | Confirmed for `ledger_records`, `get_revision` and `Diff.redacted`. `reconstruct` and `export` omit them; FR-003's "history, export" cannot mark ordinals | `Ledger.cls:635-637`; `replay.py:484-487` |
| "Replay omits their content" | Confirmed live and mocked | `replay.py:24-26`, `170-172`; e2e `:460-465` |
| "In the two-tenant fixture, replay diverges after erasure alone and equals the live store after redaction" | Confirmed as **verify's result** in that fixture. "Equals the live store" holds modulo verify's omissions (temporal index, statement ids, graph-blind nodes) and needs both targets and both erasures | e2e `:429-434`; C6 |
| "A tombstone digest can be recomputed from the original record" | Confirmed only from the server's `CanonicalRecord` output captured before the redaction. The Python record form maps graph `$Char(0)` to `null` | e2e `:436-450`; `replay.py:137-142`; F18 |
| "Earlier exports, IRIS journals and backups remain outside the guarantee" | Confirmed (receipt text checked live, e2e `:381-382`). Incomplete: snapshots and legacy rows | F8 |
| **Graph scope:** two derivations, default spelled differently | Confirmed within this domain: redaction compares *names* after `$Char(0)` stripping and uses `ForLedger` only for `tuple` kills (`LedgerRedact.cls:93`, `:463-465`; `Eraser.cls:1129`, `:1139`). Correction: record values carry a third spelling (`""` or `$Char(0)`), and node records carry no graph at all. Named-graph scope cannot address them. The inline `$Translate` in `Matches`, `PrePass` and `DropStatements` re-derives the name outside `GraphKey` (ADR-0003 says "no module may derive … inline"); low risk. | ADR-0003; R290 |

## Candidate obligations for formal modeling

**L1. Redaction keeps the history's shape and touches only its target.**
- *Rule:* a redaction of target T changes no `(seq, ordinal)` position and no record outside T. Every record in T becomes a content-free tombstone whose digest is H(canonical(original)). Revision rows change only by clearing the four free-text fields of a seq holding at least one tombstone. Exactly one audit revision is appended, naming exactly the tombstoned seqs, and nothing from T.
- *As built:* `Matches`, `Tombstone`, `ClearRevision` and `FinalInLock` (`LedgerRedact.cls:89-112`, `333-378`, `409-442`); trigger at `LedgerRevision.cls:87-101`; `CanonicalRecord` at `Ledger.cls:572-605`.
- *Bind:* `Redact`, `BatchInLock`, `Tombstone`, `ClearRevision`, `FinalInLock`, `Ledger.WriteRevision`.
- *The model must represent:*
  - a revision holding records of two graphs;
  - node records with graph `""` (graph-blind);
  - genesis records with `$Char(0)`;
  - prefix with separator, against a neighboring prefix;
  - qualifier records whose endpoints come from earlier create records;
  - the spanning revision's idempotency key;
  - a re-run as a no-op.

**L2. Redaction requires erasure and restores replay equality.**
- *Rule:* if replay equals the store and the target's content is absent from the store, then after a complete redaction of a target set covering the erased content, replay equals the store. If target content is live, redaction refuses and changes nothing.
- *As built:* `LiveRows` at entry and at Final (`:149-178`, `206`, `413`); verify comparison at `replay.py:806-867`.
- *Bind:* `LiveRows`, `FinalInLock`, `replay.verify`, `read_canonical`, `compare`, `GraphState.apply`, `Eraser.EraseGraph` and `EraseIdSet`.
- *The model must represent:*
  - a node live in a named graph whose record is graph-blind (F2);
  - temporal-only content (F15);
  - non-ledger writes between the check and Final;
  - an erase that is uncommitted or rolled back (F4).

**L3. Marker lifecycle across batches.**
- *Rule:* at most one unfinished redaction exists. While it exists:
  - every write into its target is refused;
  - a redaction of any other target is refused;
  - no reader returns a half-redacted view as complete.

  A re-run of the same target resumes it. Final atomically checks liveness, drops statements, writes the audit and clears the marker.
- *As built:* marker created at the first tombstone inside a batch transaction (`:322-324`); competing check outside the lock (`:202-205`); `BlocksCommit` inside commit (`Ledger.cls:514-518`); reader checks at `client.py:687-739`.
- *Bind:* `Redact`, `Batch`, `BatchInLock`, `Final`, `BlocksCommit`, `CommitInTxn`, `client._refuse_while_redacting`, `replay.verify`.
- *The model must represent:* at least two redaction processes, one committing process, one reader paging records, and one Eraser; the window before the first match; process death mid-batch; lock timeout; disable between batches.

**L4. Idempotency binding lifecycle.**
- *Rule:* a key moves unbound → bound(seq, fp) → redacted and never back. With a key, a commit replays exactly when bound with an equal fingerprint, and writes nothing. It is refused when bound with a different fingerprint, and refused when redacted. A binding and its revision appear and disappear together, including on rollback of a caller transaction.
- *As built:* `Ledger.cls:454-473`, `525`; `LedgerRedact.cls:359-365`; 4.7.0 nesting at `:390-415`.
- *Bind:* `CommitInTxn`, `ClearRevision`, `changeset.fingerprint`.
- *The model must represent:*
  - concurrent same key (tested live);
  - retry with another message;
  - a spanning-revision key of the other tenant;
  - the key of a commit the caller rolled back.

**L5. Erasure atomicity with no stranded live statement.**
- *Rule:* after a committed erase of graph g:
  - no row of g remains in the content tables;
  - no `stmt` entry has graph g;
  - no `tuple` entry uses key `ForLedger(g)`;
  - `rec` is unchanged.

  A failed erase changes nothing at or below its own level.
- *As built:* `Eraser.cls:47-306`, `1117-1143`, `641-680`.
- *Bind:* `EraseGraph`, `EraseIdSet`, `EraseEdgeRow`, `EraseLedgerFor`.
- *The model must represent:* a concurrent ledger commit (no shared lock), a caller transaction around the erase (4.6.4), and post-commit DDL failure.

## Candidate findings

Severity is the uplift's estimate. Every item marked SUSPECTED needs a native check by the orchestrator.

**F1. Competing redactions can both run (SUSPECTED bug, medium-high).**
- *Expected:* ADR-0013:18 says "A redaction of a different target is refused until the first one finishes". Decision 1 says the audit names *the* redacted revisions.
- *Observed:* the digest check runs before any lock (`LedgerRedact.cls:202-205`). The marker is written only at the first match (`:322-324`). `BatchInLock` keeps going under a foreign marker without comparing digests. Counters `("redacting","revs"/"n")` are shared. Whichever run reaches Final first writes an audit revision with both targets' seqs and its own digest, then kills the marker (`:420-439`).
- *Effect:* during the second run, commits into its target are not blocked, because `BlocksCommit` reads the foreign marker.
- *Distinguishing case:* a ledger where A's first record lies after more than `batch_size*20` records, then `Redact(A)` and `Redact(B)` from two processes. Expected: B is refused. Suspected: both complete with a misattributed audit.
- *Proposal (P):* claim the marker under the lock at the start of the first batch, and refuse a foreign digest inside `BatchInLock`.

**F2. `redact(None)` or `redact(None, prefix="")` can tombstone records of live nodes (SUSPECTED bug, high impact where reachable).**
- *Expected:* plan.md:10 says the node-liveness check for a default-graph target is graph-blind. Eraser refuses an empty prefix for exactly this hazard (`Eraser.cls:314-318`).
- *Observed:* for `pMatch=""`, `LiveRows` counts only rows with `graph_id=''` (`:156-158`). `Matches` returns 1 for every record with graph `""` (`:93-94`), which includes every node record, including nodes that genesis or adoption captured from named graphs (`LedgerGenesis.Capture`). Python passes an empty prefix through (`client.py:668-677`).
- *Distinguishing case:* create node `n` in graph `g` outside the ledger; enable (genesis records `n`); then `erase_graph(None)` on an empty default graph and `redact(None)`. Expected: `target_live`. Suspected: `n`'s records are tombstoned, the metadata of those revisions is cleared, and verify then diverges.
- *Proposal (P):* make whole-default-graph liveness graph-blind for nodes, labels and props, or refuse an empty prefix with the default graph.

**F3. The OpsReview brief's usage misses node records (CONFIRMED doc bug).**
- `IVG-OPSREVIEW-BRIEF.md:125` recommends `engine.ledger.redact(graph, prefix="tenant|")`.
- Node records always carry graph `""` (`LedgerApply.cls:232-369` passes no graph; plan.md:9). `Matches` requires the record's graph to equal the target (`LedgerRedact.cls:93`). The call therefore leaves every node record of the tenant.
- The correct recipe is the pair in ADR-0013:37.
- The removed 4.3.0 USER_GUIDE text (9afe0822) also said `redaction_in_progress()` "names the target". It returns only the digest (`:242-254`).

**F4. Erase and ledger concurrency (SUSPECTED, open).**
- `Eraser` never takes the ledger head lock. Since 4.6.4 it nests in a caller's transaction (aad50087). `LiveRows` reads at READ UNCOMMITTED.
- *Scenario 1:* connection 1 starts a transaction and runs `erase_graph(A)`. Connection 2 runs `redact(A)` to completion. Connection 1 rolls back. A's content is live again with its history tombstoned.
- *Scenario 2:* a ledger commit can add a statement between `DELETE rdf_edges` and `EraseLedgerFor`, which then kills its `stmt` entry.
- *A human must decide* whether erase should take the head lock, or whether redaction must refuse while erases are uncommitted.

**F5. Readers and adoption: time-of-check to time-of-use (SUSPECTED, medium).**
- The record readers check the marker once (`client.py:687-739`) and then page through SQL (`replay.py:252-279`). A batch can commit between pages.
- `history()`, `stats()` and the SQL procedure `ledger_records` never check.
- `verify(adopt=True)` reads without a lock and commits the adoption without `expected_head` (`replay.py:851-858`). If Final completes in between, the adoption can write `delete_*` records naming the tenant's ids after the redaction.

**F6. Spec and contract drift (CONFIRMED by source).**
- FR-004 says "every record" where Decision 2 says "any" (`spec.md:121` vs `155`).
- Acceptance 2 is garbled (`:57-58`).
- "The revision count does not change" (`:106`) contradicts Decision 1.
- SC-004 promises byte-identical revision rows (`:148`), which Decision 2 contradicts for spanning revisions.
- The Key Entities tombstone `$LB("redacted", digest, flags)` (`:134`) differs from the code's 5-field form (`LedgerRedact.cls:337`).
- FR-003 requires history and export to mark ordinals, which they cannot.
- Spec 213 contracts lack the spec 256 codes and kinds (C3).
- Spec 213 `spec.md` and `research.md` are cited but absent at the pin.
- Spec 256 still says "Status: Draft", although the feature shipped in 4.3.0.

**F7. USER_GUIDE "Retries" is wrong (CONFIRMED doc bug).**
- `USER_GUIDE.md:1102` says that committing the same actor and operations again replays.
- Replay requires `idempotency_key` (`Ledger.cls:457`). Without a key the retry applies again, or fails on an existing node.

**F8. The receipt's `out_of_reach` is incomplete (SUSPECTED, low-medium).**
- `save_snapshot` archives hold `^IVG.Ledger` and the ledger storage (ADMIN_GUIDE:989-991). Restoring an earlier archive brings back the tombstoned content and the `idem` bindings.
- After an R114 upgrade, 4.5.x `Graph_KG` ledger rows "stay where they are" (`legacy.py:612-613`) with uncleared metadata.
- Neither is named in the receipt (`LedgerRedact.cls:505-508`).

**F9. Unattributed records left behind under a "complete" receipt (open question).**
- `Matches` returns -1 (unknown endpoints), so those records are skipped (`:317-320`). The run still completes and kills the marker.
- FR-001 says "MUST replace every record". No test covers this.
- *Decision needed:* should a count above 0 block completion?

**F10. Spanning revisions cost the other tenant (open question).**
- Decision 2 clears the other tenant's message and correlation id, and moves its idempotency key to `idemRedacted`.
- That tenant's retry is then refused as `idempotency_redacted`, and its `history(correlation_id=…)` lookup stops finding the revision.
- Only "loses t2's commit message" was recorded (a140ed78). The key and lookup consequences were never decided.

**F11. Strict mode blocks the documented erase-then-redact path (open question).**
- `erase_graph` and `delete_nodes_by_prefix` raise `LedgerStrictModeError` (`nodes_edges.py:1513`; `iris_sql_store.py:1433-1435`).
- Erasing through changesets cannot reach nodes in named graphs (R290).
- No doc and no test covers this combination.

**F12. No abort for an unfinished redaction (open question).**
- If Final hits `target_live` because the target was legitimately reused, the marker blocks record readers, verify and every other target until the content is erased again.

**F13. Replay contract details (minor, O).**
- A replay returns `stmt_ids` as `{}` (`Ledger.cls:461`).
- `post_commit_properties` are excluded from the fingerprint and re-applied on a replay (`changeset.py:365-386`; `client.py:431-436`).

**F14. Re-enable during a redaction skips adoption silently (minor).**
- `enable()` → `verify(adopt=True)` → `redaction_in_progress` → no adoption and no error (`client.py:288-296`; `replay.py:812-823`).

**F15. Temporal content is outside liveness and verification (open question).**
- `LiveRows` ignores `^KG("tout")`. Temporal-only predicates (ADR-0015) have no `rdf_edges` row, and verify ignores temporal records (`replay.py:170-210`).
- Redaction of `create_temporal_edge` records is untested.

**F16. Simplification (P).**
- Move the liveness check and the marker claim into the first batch's transaction, under the lock.
- This removes F1, narrows F4, and makes the behavior between batches uniform.
- *Preserve:* the "re-run of a finished target reports 0 and writes nothing" behavior (e2e `:310-318`).
- *Distinguishing case:* a target with no matching records must still leave no marker after Final.

**F17. Simplification (P).**
- Route the record graph spelling in `Matches`, `PrePass` and `DropStatements` through `GraphKey.ForName`, as ADR-0003 asks, instead of an inline `$Translate`.

**F18. The digest preimage is not reproducible from the public surface (SUSPECTED).**
- `MutationRecord.from_row` normalizes graph `"\x00"` to `None` (`replay.py:137-142`, `56-74`).
- `CanonicalRecord` emits `"\u0000"` (`Ledger.cls:595-596`), and key and number formatting may also differ.
- Exports carry no records.
- *Question:* which artifact must an auditor keep to recompute a digest?

## Not inspected / limits

- **Unavailable:** spec 213 `spec.md`, `research.md` and `data-model.md` (FR-023 and FR-047 are known only through citations); OpsReview specs 055 and 056 and the agent-bus messages; spec 256 `research`/`decisions` files, which do not exist.
- **Not inspected:**
  - `LedgerApply.ApplyAll` beyond the record writers;
  - `LedgerStats`;
  - `TemporalIndex.EraseGraph`/`EraseNodes`;
  - `Adjacency.RemoveGraph`;
  - `Graph.KG.Txn` and `_write_txn.py`;
  - snapshot save/restore code beyond the ADMIN_GUIDE description;
  - `tests/unit/test_256_ledger_redaction.py` bodies (index only);
  - `test_ledger_us03_concurrency.py`, `test_ledger_store_failures.py`, `test_470_ledger_caller_txn_e2e.py`;
  - the HTTP API (no ledger route was checked).
- **Assumptions to verify natively:**
  - `%SQL.Statement` reads at READ UNCOMMITTED (abf4e6eb asserts it);
  - process death rolls back an open batch;
  - IRIS `%ToJSON` escaping relevant to F18.
- No test was run. Every SUSPECTED item is a source-reading inference.
