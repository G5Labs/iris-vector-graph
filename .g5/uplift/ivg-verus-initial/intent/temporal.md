# Intent recovery: temporal edges (worker A-temporal)

Pin: `3eaa79cf` (v4.7.0 + checklist). Read-only; no tests or database runs. Tags: **(H)** human requirement or
answered question (all recorded secondhand in single-author text, so the provenance is weaker than the tag implies),
**(D)** accepted design decision, **(O)** observed implementation only, **(P)** proposed improvement. "Source-proven"
means the control flow alone shows the behavior. "SUSPECTED" means the finding also depends on runtime facts or on
intent that has not been settled.

## Scope and sources inspected

| Locator | Revision/date | Authority | Inspected portion | Follow-up |
|---|---|---|---|---|
| `docs/adr/0002-temporal-globals-are-not-directly-accessible.md` | Accepted 2026-09-11 | D | whole | The text says "read or write", but `TemporalWindow` reads the globals directly (F12) |
| `docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md` | Accepted 2026-10-12; amended by spec 254 and ADR-0015 | D | whole | Line 40 says the Cypher adopt is still open, but it is partly fixed (254 sign-off) |
| `docs/adr/0015-temporal-structural-rows-opt-out.md` | Accepted 2026-10-25 ("Tom"); 4.5.0 | D | whole | The toggle-back-before-drop case is not covered (F8) |
| `docs/adr/0003`, `0010` | Accepted | D | 0003 decision table; 0010 context (rollback does not undo `$Increment`) | Used by F3 and F12 |
| `specs/204-temporal-index-gaps/spec.md` | 2026-08-31, Draft | H (opsreview gaps) | spec.md whole; other files not read | FR-003 ("purge leaves out/in") is **superseded** by 254 FR-001 |
| `specs/239-alt-temporal-erase/{spec,plan}.md` | 2026-10-12, exploratory | D (shipped: `EraseGraph/EraseAll/EraseNodes` exist) | spec, plan | tasks.md not read |
| `specs/246-alt-temporal-structural-row/{spec,plan}.md` | "Exploratory, not adopted" | none (alt) | spec, plan | Its Python flag still ships (`engine.py:289,322`) (F9, S1) |
| `specs/252-adjacency-functional-index/spec.md` FR-014, tasks T030/T033 | 2026-10-20 | D | grep for temporal | |
| `specs/254-temporal-purge-collisions-rebuild/*` | 2026-10-22, Decisions (Tom) and sign-off | H + D | spec, plan, tasks with the sign-off "Open" list | |
| `specs/255-temporal-window-reader/*` | 2026-10-22, Decisions (Tom) | H + D | spec, plan, tasks | No statement about inserts behind the cursor (Q5) |
| `specs/213-graph-revision-ledger/contracts/ledger-api.md:83-93` | spec.md absent at the pin | D | strict-mode guard list | Says strict mode "skips the structural mirror", but the 4.3.0 marked rows are written anyway |
| Commits `43efd473` (2026-10-19), `e4090d00` (2026-10-22), `b612978c` (2026-10-21), `3f15743a` (2026-10-25), `a1b78593` (spec 224), `31ffa3c3` (spec 221) | messages | D (43efd473 records "Decided with Tom 2026-10-19") | messages only | |
| `CHANGELOG.md` v4.3.0 (2788-3166), v4.5.0, v4.6.x R217/R213/R252, v4.7.0:21-22, 82-85; spec 221 at 4656-4670 and 4910-4916 | dated | D/O | temporal entries | |
| `docs/USER_GUIDE.md:236-275` (writes inside your transaction) | 4.6.4 | D | section | Lists only two counters a rollback leaves; temporal counters are missing (F3) |
| `iris_src/src/Graph/KG/TemporalIndex.cls` (1651 lines) | pin | O | all write, delete, purge, erase, latest, backfill and migrate methods; QueryWindow/GetAggregate | GetBucketGroups, FindBursts and label sets skimmed |
| `TemporalIndexMS.cls`, `TemporalPolicy.cls`, `TemporalWindow.cls` | pin | O | whole | |
| `Adjacency.cls:540-766` (AssertTemporalRow, Retract*, IsTemporalMarked) | pin | O | listed range | Multigraph `ekey` interplay not traced |
| `LedgerApply.cls:1-80, 440-520, 605-641`; `LedgerGenesis.cls:30-72`; `Eraser.cls:1250-1352` | pin | O | listed ranges | |
| `iris_vector_graph/_engine/temporal.py` (create/delete/bulk, window, purge, policy API), `temporal_window.py`, `temporal_only_warning.py`, `migrations/temporal_structural_rows.py` | pin | O | whole except the aggregate and readers tail (835-1155) | |
| `stores/iris_sql_store.py:2655-2900`; `_engine/nodes_edges.py:85-95, 1225-1300, 1980-2005`; `ledger/changeset.py:307-345`; `ledger/replay.py:588-640, 785-840` | pin | O | listed ranges | |
| Tests: `tests/e2e/test_254_{collisions,purge,rebuild}_e2e.py`, `test_255_window_reader_us{1,2,3}_e2e.py`, `test_temporal_structural_optout_e2e.py`, `test_252_temporal_rows_e2e.py`, `test_460_ledger_temporal_edge_e2e.py`; `tests/integration/test_224_temporal_changeset_e2e.py`, `test_ledger_us11_temporal_coexist.py`, `test_221_upsert_weight_e2e.py`; `tests/unit/test_temporal_single_owner.py`, `test_temporal_edges.py` | pin | evidence | collisions and opt-out tests read in full, the others by test names and key bodies | |

## Capabilities

### C1. Temporal write: insert, update and skip, collisions, aggregates, latest index

**Governing statements**
- (H) A mode "insert" write at occupied coordinates `(ts,s,p,o)` MUST change no store and be reported as a collision.
  The first write wins (spec 254 FR-003; Decision 2, "Tom, 2026-10-22"). `BulkInsert` keeps its written-count integer.
- (H) The same set of writes in any batch size leaves every store identical (254 FR-004). Order independence holds only
  when colliding writes are identical and a triple's weights agree (254 US3 scenario 2; sign-off "Open", last bullet).
- (D) `upsert=True` / mode "update" is last-write-wins on `tout/tin/edgeprop`. The "known caveat" says the aggregates
  are "not adjusted" (CHANGELOG 4910-4916, 4669-4670). The Python docstring sharpens this: "Aggregate counters
  (count/sum/min/max) remain based on the original value" (`temporal.py:273-279`). Contradicted by the code (F1).
- (H) Each source's newest event is index (b), `^KG("tlast",g,s,p)=ts`, maintained on every write. "Purge and erase
  maintain `tlast`" (255 Decision 1; plan "Kept exact by DeleteTemporalEdge, EraseNodes, PurgeRawBefore, PurgeBefore,
  MigrateRaw, EraseGraph, EraseAll").
- (O) `InsertEdge` returns 1 for a write, a skip and a collision alike (`TemporalIndex.cls:62-64`). Only the bulk path
  reports counts (`BulkInsertCounts` returns `"w:c:s"`, `:151-182`).

**Operations**
- Entry: `create_edge_temporal` (`temporal.py:246`) → `store.write_temporal_edge` (`iris_sql_store.py:2655`) →
  `InsertEdge` (`TemporalIndex.cls:46`). `bulk_create_edges_temporal` (`temporal.py:390`) →
  `bulk_write_temporal_edges` (`iris_sql_store.py:2719`) → `BulkInsertCounts` (`:151`). Ledger:
  `Changeset.create_temporal_edge` → `LedgerApply.OpCreateTemporalEdge` → `InsertEdge` (C6).
- Writer `WriteStores` (`TemporalIndex.cls:80-133`) works in this order. First the guard: "update" kills `edgeprop`
  (:82-83); otherwise an occupied `tout` returns 0 for skip and -1 for a collision (:84-85). Then come the
  first-write-into-empty-graph `tlast` reset and completeness flag (:90-93), `tout` (:97) and `NoteLatest` (:98).
  Next are `tin` unless suppressed and `$Increment(bucket)` (:102). After those comes the structural step (C2, :109-115),
  then the `tagg` count and sum `$Increment` and min/max (:117-124), `UpdateHLL` (:125) and `edgeprop` (:126-131).
- Commit boundary: **none**. Neither `InsertEdge` nor `BulkInsertCounts` opens a transaction (`_temporal_left`,
  `temporal.py:12-17`, says so). Inside a ledger commit or a caller transaction, the enclosing TSTART governs.
- Readers: `GetAggregate` (`:1445-1491`) reads `tagg` for whole buckets and `tout` edge by edge for cut buckets (R217).
  The other readers are `GetVelocity`/`FindBursts` (`bucket`), `GetDistinctCount` (HLL), `QueryWindow*`, and
  `TemporalWindow.Latest` (`tlast`).

**Outcome-changing cases**
- insert, skip and update at a free coordinate; each at an occupied one. The occupant may come from an earlier call or
  from earlier in the same batch (both covered: `test_254_collisions_e2e.py:61,72`).
- update at an occupied coordinate. `tout/tin` are overwritten, but `bucket`, `tagg.count` and `tagg.sum` are
  incremented again and min/max widen (F1). Not pinned by any test: `test_update_is_unchanged`
  (`test_254_collisions_e2e.py:104-110`) checks only the window and attrs.
- A failure in `AssertTemporalRow` part way through a write leaves `tout/tin/tlast/bucket` behind. A retry is then a
  collision and never completes the write (F2).
- A rollback of an enclosing transaction undoes the Sets but not the `$Increment`s (F3).
- Concurrent writers: two inserts to the same free coordinate both pass `$Data` and both count (F7). Concurrent
  `NoteLatest` on one `(s,p)` can lose the max (F6).
- `ts=0`: the bulk path substitutes "now" (`:170`). The single path writes ts 0 when `timestamp=None`, because Python
  sends `"0"` (`temporal.py:294`, `iris_sql_store.py:2680`) (F11).
- `TemporalIndexMS` (ms precision; bucket = ts\300000) shares `WriteStores`. Collisions are covered at ms precision
  (`test_254_collisions_e2e.py:129`).

**Tests**: `test_254_collisions_e2e.py` (live DB; digest equality with a first-write-only graph, aggregates
included), `test_221_upsert_weight_e2e.py` (live; weight and attrs only), `test_254_rebuild_e2e.py` (live; batch size
and order hashes), `test_255_window_reader_us3_e2e.py:124-170` (live; tlast exact after delete, purge, node erase and
graph erase), and `tests/unit/test_254_temporal_counts_unit.py` (mocked).

### C2. Implied structural row (ADR-0009): assert, marker, adoption, retraction, ledger governance

**Governing statements**
- (D) A temporal edge also asserts a structural `rdf_edges` row in the same graph, carrying a temporal-origin marker.
  Deleting the last timestamp removes the row only while the marker is set. An explicit `create_edge` clears the
  marker, and then no temporal delete can remove the row (ADR-0009:9-13; spec 252 FR-014 "on every write path
  including the ledger").
- (H/D) The implication ends when the last timestamp goes, whether by `DeleteTemporalEdge` or by a purge, "in every
  graph". The marker, not a reference count, is the distinction (254 Decision 1; ADR-0009 amendment :35-49; plan
  "Decision 1").
- (D) Marked rows are outside ledger governance: verify and genesis skip them, and temporal writes create no
  revisions. Source: commit `43efd473` ("Decided with Tom 2026-10-19"), CHANGELOG v4.3.0 (around line 3046),
  `replay.py:617-620`, `LedgerGenesis.cls:41-44`.
- (D) Adoption: `create_edge`, `bulk_create_edges` (254) and a Cypher `CREATE`/`MERGE` between matched nodes adopt a
  marked row. Still leaving the marker: a multigraph `MERGE`, an undirected `MERGE` matching the reverse row, and a
  `MERGE` with inline nodes (254 tasks sign-off "Open"; ADR-0009:40 still says Cypher is open, so it is stale).

**Operations**
- Assert: `WriteStores` → `TemporalPolicy.IsStructuralKey` (:109). With `Adjacency.Indexed()` the next step is
  `AssertTemporalRow(gKey,s,p,o,w,trust=1)` (`Adjacency.cls:575-618`). That skips if `^KG("out",g,s,p,o)` exists,
  else it embedded-SQL inserts both endpoint `nodes` rows (graph = edge graph) and the edge row
  `{"temporal":true[,"weight":w]}` guarded by `NOT EXISTS`. The row's functional index writes `^KG("out"/"in")`.
  Without the index: `PutShadow` (`^KG` only, no row). The Python legacy mirror (`temporal.py:309-331, 455-475`) also
  writes an **unmarked** row for named graphs.
- Retract on delete: `DeleteTemporalEdge` (`TemporalIndex.cls:325-345`) runs `RemoveTemporalRow`, then `Relatest`,
  then `HasTemporalEdge` (walks every ts, `:613-630`). If no timestamp is left, `RetractTemporalRow`
  (`Adjacency.cls:623-645`) deletes rows while `IsTemporalMarked`. Not indexed: `Adjacency.Remove` regardless of rows.
- Retract on purge: `RetireExpired` (C4).
- Adopt: `_adopt_temporal_row` (`nodes_edges.py:1275-1300`) does `UPDATE qualifiers=<explicit>`.
  `bulk_create_edges` uses `_ADOPT_TEMPORAL_ROW_SQL` (`:90-93, 1992-2001`) with `qualifiers = NULL`. The ledger path
  `OpCreateRel` adopts when `tCur.temporal="true"` (`LedgerApply.cls:465-475`).
- Readers: SQL and Cypher `MATCH`, `edge_count`, BFS/centrality via `^KG`; `read_canonical` skips marked rows
  (`replay.py:617`) but **reads every node** (`replay.py:598-600`).

**Outcome-changing cases**
- The triple already has an unmarked row (explicit first): no assert, no marker, and the row survives
  (`test_254_purge_e2e.py:147`).
- Explicit write after a temporal one (adopt): tested for `create_edge`, `bulk_create_edges` and Cypher
  (`test_254_purge_e2e.py:155-218`). The three Cypher `MERGE` variants still leave the marker and are untested here.
- `delete_edge` on a marked row: the row goes and the timestamps stay. The next temporal write re-asserts the row, and
  a purge removes nothing more (`test_254_purge_e2e.py:322`).
- A temporal write racing a purge or `DeleteTemporalEdge` on the same triple can leave a timestamp with no row
  (254 sign-off "Open", third bullet). This is known and unfixed.
- Ledger strict mode: the temporal write still asserts the marked row **and endpoint nodes**. The contract
  `ledger-api.md:92` ("skips the structural mirror") predates this. New endpoint nodes are not marked and are read by
  verify (F4).
- Not indexed and a named graph: the Python mirror writes an unmarked row that no purge or delete retracts (F9).

**Tests**: `test_252_temporal_rows_e2e.py` (live; marker, delete, adopt, backfill), the `test_254_purge_e2e.py` path
matrix (live), `test_ledger_us11_temporal_coexist.py:100-140` and `test_460_ledger_temporal_edge_e2e.py` (live;
pre-created nodes `a`, `b` only).

### C3. Temporal-only opt-out per graph (ADR-0015)

**Governing statements**
- (D) Registry `^IVG.TemporalStructural(ForIndex(g), p) = 0`. Absent means structural, which is the default. Matching
  is exact on the predicate string. `Graph.KG.TemporalPolicy` is the only writer (ADR-0015:9-15; `TemporalPolicy.cls:1-37`).
- (D) For a registered predicate, `InsertEdge`/`BulkInsert` write only the temporal stores. The upgrade backfill skips
  it, the purge leaves it out of the retract set and `retire_bare_nodes` gets no candidates (table at ADR-0015:17-26).
- (D) `set_temporal_structural` "takes effect for the next write. It does nothing to rows that exist"
  (ADR-0015:101). Writers are never blocked: in-flight writes finish with rows and the drop removes them (:116-117).
- (D) "Decided: the purge leaves the old rows of a predicate registered later" until
  `drop_temporal_structural_rows` (:144-148). Drop and backfill need the adjacency index (:149).
- (D) An explicit `create_edge` writes an unmarked row "whatever the registry says" (:68-70).
- (D) Temporal `CALL`s, window reads, aggregates and latest reads keep working (:63-66). An empty Cypher/BFS answer
  naming a registered predicate logs one warning per (graph, predicate) per engine (`temporal_only_warning.py:36-52`).

**Operations**: `set/get_temporal_structural`, `list_..._opt_outs` (`temporal.py:722-758`) → `TemporalPolicy.Apply/
IsStructural/List`. `drop_temporal_structural_rows` (`temporal.py:760-809`) → `DropRows` (`TemporalPolicy.cls:124-228`).
That refuses a structural predicate (:132-134) and a non-indexed install (:135-137). Two-pass id collection, then
`DELETE ... WHERE edge_id=? AND marker` per row in transactions of `pBatch`, then `RetireBareNodes` after each commit.
`backfill_temporal_structural_rows` → `TemporalPolicy.BackfillRows` (:258-272), which refuses an opted-out predicate,
then `TemporalIndex.BackfillWalk(trust=0)` (`TemporalIndex.cls:249-302`).

**Outcome-changing cases when toggling with existing data**
- Structural → opted out, with marked rows present. New timestamps write no row; old rows stay until the drop.
  `DeleteTemporalEdge` of the last timestamp **still retracts** the old marked row (it does not consult the registry,
  `:333-341`). A purge does **not** (`RetireExpired` `:966`). Delete and purge therefore differ (O), and only the purge
  case is decided.
- Opted out → structural without a drop in between. If the predicate's timestamps were purged while it was opted out,
  the old marked rows now have no timestamp. No purge or delete can find them, and `DropRows` refuses a structural
  predicate (F8).
- Opted out → structural again: the triples written in the gap have no row until `BackfillRows`. The next write of
  such a triple asserts its row because `^KG("out")` is absent.
- A writer racing the switch: covered (`test_temporal_structural_optout_e2e.py:406-446`; live, 600 writes).
- `EraseGraph` keeps the registry and `EraseAll` kills it (`:348`); snapshots carry it (`:361`).
- The spec-246 Python flag (`temporal_structural_rows=True`) path `_own_structural_row` (`temporal.py:182-198, 306-308`)
  and the non-indexed named-graph mirror ignore the registry (F9).

**Tests**: `tests/e2e/test_temporal_structural_optout_e2e.py` (live, 25 cases) and
`tests/unit/test_temporal_structural_optout_architecture.py` (source-text guard).

### C4. Purge, erase and rebuild

**Governing statements**
- (H) Retention removes everything an expired edge left: raw entries, attributes, and the row and adjacency that only
  expired timestamps held up. Aggregates and nodes stay (254 US1, FR-001/FR-002; nodes can be retired since 4.5.0, and
  the Python default has been `retire_bare_nodes=True` since 4.7.0, `CHANGELOG.md:21-22`). Spec 204 FR-003 ("leave
  out/in untouched") is **superseded**.
- (D) Rows first, raw second, so a failed purge is finished by a rerun (ADR-0009:43-44; plan 254 "Purge").
- (D) "The bucket aggregates stay ... they describe the past, not the surviving raw edges" (ADR-0009:49). On the other
  side, `DeleteTemporalEdge` and `EraseNodes` keep "the aggregate describes the surviving edges"
  (`TemporalIndex.cls:446-488`, `RebuildBucketAggregate`). The two rules collide in a bucket cut by a purge (F10).
- (D) `PurgeRawBefore`/`PurgeBefore` keep only aggregate buckets strictly before the bucket containing `tsEnd`
  (204 FR-021). `PurgeBefore` is default-graph only (`:818`, docstring `temporal.py:623-640`).
- (D) The temporal globals have one writer. `TemporalIndex.EraseGraph/EraseAll/EraseNodes` are called inside the
  Eraser's transaction and open none themselves (spec 239 FR-002..005, plan "Constraints").

**Operations**
- `PurgeRawBefore(g, tsEnd, tsStart, retire)` (`:866-920`). First `RetireExpired` (`:944-1046`), which collects the
  distinct `(s,p,o)` in `[tsStart,tsEnd)` for structural predicates into `^||IVG.TPurge`, then walks the surviving
  timestamps and drops each candidate still held. `RetractTemporalRows` (`Adjacency.cls:650-689`) issues the
  prefix-marker DELETE, with a fallback to the parsing `RetractTemporalRow`. Without the index it calls
  `RetractTemporalShadows`. Optionally `Eraser.RetireBareNodes` runs (per-10,000 transactions,
  `Eraser.cls:1253-1310`). Then the raw kill loop runs. Raw `tout/tin/edgeprop` in the range go; `tagg/bucket` stay.
  `RelatestRange` (:918) runs only when `deleted>0`.
- `PurgeBefore(tsEnd, retire)` (`:816-854`) runs the same retire step on graph 0, then kills raw plus the
  `tagg/bucket` of buckets ≤ `tsEnd\B - 1` that had a raw timestamp in range. `PurgeBucketRange` (`:1050-1066`)
  touches aggregates only.
- `DeleteTemporalEdge` (`:325-345`) → `RemoveTemporalRow` (`:348-360`): kills raw, `bucket -1` (killed at ≤0),
  `RebuildBucketAggregate` for `(s,p)`.
- `EraseNodes(g, ids)` (`:400-447`) collects, removes, kills `tlast(g,erased source)` and runs `Relatest` for the
  surviving sources. `EraseGraph` (`:366-377`) and `EraseAll` (`:381-392`) kill the six subtrees.
- Rebuilds: `RebuildLatest` (`:581-608`) sets the flag last. `BackfillStructuralRows` (upgrade, `:232-235`) and
  `BackfillRows` use the bounded `tSeen` (`:283-292`). Rebuild determinism (254 US3) is hashed by
  `tests/e2e/graph_snapshot.py`.
- Commit boundary: the purge opens **no** transaction of its own except inside `RetireBareNodes`/`DropRows`. The
  retract statements and the raw kills are autocommitted one by one.

**Outcome-changing cases**: timestamps on both sides of the cutoff (row stays); `tsStart>0` (rows of earlier
timestamps stay, `test_254_purge_e2e.py:257`); two graphs (`:268`); suppressed reverse index (`:239`); ms precision
(`:247`); empty range changes nothing (`:330`); purge after delete, node erase, graph erase or `delete_edge`
(`:294-327`); opted-out predicate (C3); an interrupted purge rerun (argued in the ADR, not tested); a purge racing a
writer (open); purge then delete in the cut bucket (F10, untested).

### C5. Window reader paging and latest-per-source (spec 255)

**Governing statements**
- (H) Any window size, in pages, through a cursor, with memory bounded by the page size. A failure raises and never
  returns a short or empty answer as if complete (255 US2, FR-001, FR-006).
- (H) Order is ascending ts, then source, predicate, target, "stable across pages" (FR-005). Both ends are inclusive.
- (H/D) "Paging: lazy, from a resume key (ts,s,p,o), with constant server memory" (Decision 2). "A page read after
  the window's events were purged: a live read from the resume key ... events purged after the first page are not
  returned" (spec Edge Cases). Concurrent **inserts** are not addressed (Q5).
- (H/D) Latest per source: newest by ts, ties to a stable order; a source with nothing qualifying is absent
  (US3, FR-007). Ties go to "the last (p, o) in index order" (plan; `TemporalWindow.cls:296-300`).

**Operations**: `iter_edges_in_window` (`temporal.py:539-580`) → `TemporalWindowCursor` (`temporal_window.py:74-136`) →
`TemporalWindow.Open/Next/Close` (`TemporalWindow.cls:44-91`). `Page` (`:128-193`) is a 4-level resumable `$Order`
walk. It stops at `pCount` rows or `PAGECHARS` (:185) and saves `(lvl,ts,k1,p,k2)` in process-private
`^||IVG.TWin(h,"key")` (:190). It kills the handle when done. Filters go through `NextKey` (one source, `NextListed`
leapfrog, prefix range or prefix compare; `RangeSafe` at `:255-258`) and `NextPred`. `get_latest_edges` →
`temporal_window.latest` → `TemporalWindow.Latest` (`:305-361`) → `Resolve` (`:367-443`). That trusts `tlast` only
when the flag `^KG("tlast",g)` is set, re-walks when the index names a vanished event (:411-415), and walks backwards
for `before` and `lookback`.

**Outcome-changing cases (as built, O)**
- Page boundary in the middle of one `(ts,s,p)` group, or on ties at one ts: the resume key holds all four
  coordinates, and `$Order` from the last emitted `o` continues strictly after it. Nothing is duplicated or skipped
  among edges that existed throughout (`test_255_window_reader_us1_e2e.py:182` small pages; `us2:72` 200k
  edges once and in order).
- An edge deleted before the cursor reaches it is not returned (`us1:230`). `$Order` from a killed key still advances
  correctly.
- An edge inserted with a key after the cursor is returned. One inserted at or before the cursor (a back-dated ts, or
  the same ts with a lower `s`) is never returned. An update after a page was read leaves the old weight in that page.
  The union of pages is not a snapshot (O; untested; Q5).
- Handle: process-private, so one connection only. `Next` on a closed handle raises (:85-91). GC closes the handle
  (`temporal_window.py:132-136`).
- Latest: `tlast` stale-high self-corrects (:411-415). `tlast` stale-low (F6) gives a wrong, older answer silently.

### C6. Ledger temporal ops (Changeset → LedgerApply)

**Governing statements**
- (D) Spec 224 (spec text absent at the pin; commit `a1b78593`, `changeset.py:321-336`): the temporal op is written
  "inside the ledger's TSTART/TCOMMIT transaction, atomically with all structural ops". Mode defaults to "update".
  The docstring says `"insert"` means "(fail if key exists)".
- (D) Direct temporal writes create no revisions (spec 213 US11, via `43efd473`). Marked rows are derived, not governed.

**Operations**: `Changeset.create_temporal_edge` (`changeset.py:309-345`) → `Ledger.Commit` (TSTART) → `ApplyAll`
(`LedgerApply.cls:18-49`) → `OpCreateTemporalEdge` (`:617-641`). That validates s/p/o/ts and sets `tMode` default
"update" (:628). It calls `InsertEdge(tG,...,upsert=0,sri=0,tMode)` (:635); the status is always OK, but a throw from
`WriteStores` propagates. `Rec("create_temporal_edge","temporal_edge", "s|p|o@ts")` (:639) runs **unconditionally**,
even when the write was a collision or skip. Replay ignores the `temporal_edge` kind (`replay.py:174-210` handles
only node/rel).

**Outcome-changing cases**
- "insert" at an occupied coordinate inside a changeset: no failure, no store change, and a create record is still
  written (F5).
- Default "update" at an occupied coordinate: aggregates double count (F1).
- A temporal op followed by a failing op: rollback of the Sets, but not of the `$Increment`s (F3). The test
  `test_224_temporal_changeset_e2e.py:136-171` puts the failing op **first**, so the temporal op never runs and the
  case is untested.
- The temporal op creates endpoint nodes through `AssertTemporalRow` with no `create_node` record (F4).
- Idempotent replay of the same key: not re-applied (`test_224...:102-134`, live).

### C7. Default vs named graph keys

- (D) `^KG` temporal subscripts use `GraphKey.ForIndex(g)`: default `0`, named = canonical name; `"0"` and control
  characters are rejected (ADR-0003; `GraphKey.cls:38-56`). Every TemporalIndex, TemporalWindow and TemporalPolicy
  entry derives it (`TemporalIndex.cls:49,152,327,...`; `TemporalWindow.cls:46,308`; `TemporalPolicy.cls:27,48,73,126`).
- (O) Exceptions: `PurgeBefore` hardcodes `0` (`:818`, documented). `AssertTemporalRow`, `RetractTemporalRow(s)` and
  `RetractTemporalShadows` convert the index key back to a SQL `graph_id` (`0` → `$Char(0)`, otherwise the key)
  (`Adjacency.cls:583, 627, 654, 698`). That is a key→name conversion outside `GraphKey`, which ADR-0003:22-23 forbids
  in spirit. It is safe today only because `ForIndex` = `ForName` for named graphs (F12).
- (O) Ledger records carry the changeset's graph string (`""` for the default) (`LedgerApply.cls:639`). The ledger
  tuple index uses `ForLedger` (`$Char(1)`). `RetireBareNodes` gets `ForName(graphId)` (`:1040`). The legacy flat
  layout migrates by depth, not value, in one transaction (`:1098-1112`).
- Python: `validate_graph_name` on the write, delete, purge and window paths. `execute_temporal_window_query` passes
  `graph or ""` unvalidated (the server validates) (`iris_sql_store.py:2860`).

### Seed-claim check: index.md row "Temporal edges"

| Seed clause | Verdict | Evidence |
|---|---|---|
| "A temporal assertion creates a structural edge by default." | **Corrected / qualified** | Only with the adjacency functional index declared (`TemporalIndex.cls:110-114`). Without it: a `^KG` shadow with no row (default graph) or an unmarked Python mirror row (named graph, `temporal.py:309-331`). The edge is a **marked** row outside ledger governance (43efd473), and it also creates endpoint `nodes` rows. The marked row carries the first-written weight. |
| "A graph can opt a predicate out." | **Confirmed, with limits** | Per (graph key, exact predicate) registry (ADR-0015; `TemporalPolicy.cls:31-37`). It takes effect for the next write and never touches existing rows. Toggling back before a drop can strand marked rows (F8). Two Python paths ignore it (F9). |
| "Time-window reads and an explicitly asserted structural edge have separate obligations." | **Confirmed, incomplete** | Window, aggregate and latest reads walk only the temporal globals (ADR-0015:63-66; `TemporalWindow.cls`). An explicit row is unmarked or adopted and survives delete and purge (FR-002; `Adjacency.cls:623-645`). Three Cypher `MERGE` variants still do not adopt (254 sign-off). The row omits collisions, aggregate semantics, latest-index exactness, the purge's rows-first lifecycle and ledger interplay, all of which carry obligations. |
| Evidence "live opt-out tests" | **Confirmed** | `test_temporal_structural_optout_e2e.py` is `requires_database` e2e. |

## Candidate obligations for formal modeling

**O1. First write wins, and the aggregates equal the raw store for untouched buckets.**
- L1: For any bucket that no purge has cut, `tagg(b,s,p).count/sum/min/max` and `bucket(b,s)` are functions of the
  raw edges in `tout` for that bucket. A write at an occupied coordinate in insert or skip mode changes no store, and
  the batch's `written+collisions+skipped = n`.
- L2: The `WriteStores` guard (:82-85); `$Increment` on `bucket` and `tagg` (:102, :117-118); no lock and no
  transaction. `RemoveTemporalRow` decrements `bucket` and rebuilds `tagg` (:357-359).
- L3 bind: `TemporalIndex.WriteStores`, `BulkInsertCounts`, `InsertEdge`, `RemoveTemporalRow`,
  `RebuildBucketAggregate`, `GetAggregate`.
- Must represent: modes {insert, skip, update}; occupied or free; a same-batch duplicate; a failure between `:102` and
  `:117` (F2); rollback that undoes Sets but not `$Increment` (F3); two interleaved writers (F7); a later delete; a
  purge-cut bucket (F10).

**O2. Marked-row lifecycle.**
- L1: In an indexed graph, for a structural predicate, a marked row for `(g,s,p,o)` exists iff some `tout(g,·,s,p,o)`
  exists and no explicit write adopted the row. An unmarked row is never removed by a temporal operation. The marker
  only goes from set to cleared (by adoption), never back.
- L2: The `AssertTemporalRow` trust-`^KG` shortcut; `RetractTemporalRow(s)` delete-while-marked; the purge's survivor
  walk; adoption UPDATEs (`nodes_edges.py:1275`, `:90`, `LedgerApply.cls:465-475`).
- L3: `WriteStores:109-115`, `DeleteTemporalEdge`, `RetireExpired`, `Adjacency.AssertTemporalRow/RetractTemporalRow/
  RetractTemporalRows`, `_adopt_temporal_row`, `bulk_create_edges` adopt, `OpCreateRel`, and `delete_edge`.
- Must represent: explicit before or after temporal; delete versus purge of the last ts; `delete_edge` of a marked row;
  a writer interleaved with a purge or delete (known violation); multiple graphs; a non-indexed install (out of the
  invariant).

**O3. Opt-out registry as a projection switch.**
- L1: The registry is the only answer to "does a temporal write of `(g,p)` produce a row". Rows are a projection of the
  temporal globals. `drop` followed by `backfill` after re-enabling restores exactly the rows for live triples. No
  operation sequence leaves a marked row whose triple has no timestamp, unless the predicate is opted out and awaiting
  a drop.
- L2: `IsStructuralKey` read per edge; `DropRows` precondition "registered"; `BackfillRows` precondition "structural";
  the purge skips registered predicates.
- L3: `TemporalPolicy.Set/IsStructuralKey/DropRows/BackfillRows`, `WriteStores:109`, `RetireExpired:966`,
  `BackfillWalk:277-280`, `DeleteTemporalEdge:333`.
- Must represent: a toggle in each direction with existing rows and timestamps; a purge while opted out; a toggle back
  before the drop (F8); delete versus purge while opted out.

**O4. Window cursor monotonicity.**
- L1: The pages of one cursor emit strictly increasing keys `(ts,k1,p,k2)` within `[start,end]` that satisfy the
  filter. Every edge present for the whole read is emitted exactly once. An edge absent when the cursor passes its key
  is not emitted. Server state is O(spec) between pages.
- L2: Resume key at level 4 (:190); `$Order` successor semantics; handle killed on done.
- L3: `TemporalWindow.Open/Page/NextKey/NextListed/NextPred/Next/Close`, `TemporalWindowCursor.__next__/close`.
- Must represent: page break inside a group and on ts ties; deletes and inserts before or after the cursor; prefix
  modes 3 and 4; the in-direction with suppressed `tin`.

**O5. Latest-index exactness.**
- L1: When the flag `tlast(g)=1` is set, for every `(s,p)`: `tlast(g,s,p) = max{ts : tout(g,ts,s,p,·)}`, or it is
  absent when there is none. `Latest` returns that event with deterministic tie-breaking.
- L2: `NoteLatest` read-compare-set (:493-496); flag reset on the first write into an empty graph (:90-93);
  `Relatest/RelatestRange`; `EraseNodes` kill; `RebuildLatest` sets the flag last.
- L3: `WriteStores:90-98`, `NoteLatest`, `Relatest`, `RelatestRange`, `DeleteTemporalEdge`, `EraseNodes`, both
  purges, `EraseGraph`, `RebuildLatest`, `TemporalWindow.Latest/Resolve`.
- Must represent: concurrent writers on one `(s,p)`; two first writers into an empty graph; rollback of a `tlast` Set
  that another process overwrote (F6).

**O6. A ledger temporal op is atomic with its changeset, and so are its derived side effects.** This is a candidate
for after Q3 is decided.
- L1: A rolled-back commit leaves no trace in any temporal store. A committed one records exactly what changed.
- L3: `LedgerApply.OpCreateTemporalEdge`, `Ledger.Commit`, `WriteStores`.

## Candidate findings

**Bugs**

- **F1. "update" at an occupied coordinate double-counts the aggregates (source-proven; contradicts the docs).**
  Expected: the aggregates "remain based on the original value" (`temporal.py:275-277`) or are "not adjusted"
  (CHANGELOG 4669, 4914). Observed: with `pMode="update"` there is no early return (`TemporalIndex.cls:82-86`). The
  write proceeds to `$Increment(bucket)` (:102), `tagg.count` +1 and `tagg.sum` += the new weight (:117-118), and
  min/max widen (:119-124). The result is count 2 and sum old+new for one raw edge. Whole-bucket `GetAggregate`
  reads `tagg`, but a window that cuts the bucket reads `tout` (:1469-1484), so the answer depends on window
  alignment. A later `DeleteTemporalEdge` rebuilds `tagg`, but `bucket` stays inflated (:357). It reaches the ledger
  by default (`Changeset` mode "update", `LedgerApply.cls:628`). Untested: `test_update_is_unchanged` reads no
  aggregate. A distinguishing case: write w=2, update w=9, then `get_temporal_aggregate(count)` on a 300-aligned
  window gives 2, and on a cut window gives 1.

- **F2. A partial write cannot be repaired by retry; the bulk fallback hides it (source-proven control flow).**
  `WriteStores` writes `tout`, `tlast`, `tin` and `bucket` before `AssertTemporalRow`. A `$$$ThrowOnError` there
  (:111) leaves them, with no `tagg`, `edgeprop` or row (no transaction: `temporal.py:12-17`). A retry in "insert"
  mode hits `$Data(tout)` and returns a collision (:84-85), so the row, aggregates and attrs are never written. This
  contradicts ADR-0009 (row iff timestamp) and O1. Worse, `bulk_write_temporal_edges` catches the `BulkInsertCounts`
  exception and re-sends **every** edge of the batch per edge (`iris_sql_store.py:2759-2785`). `InsertEdge` answers
  1 for collisions, so all edges count as "inserted" and no error surfaces if the retries succeed. In "update" mode
  the fallback re-increments the aggregates of the edges written before the failure. Trigger: any SQL failure in
  `AssertTemporalRow`, such as a role without INSERT on `nodes`/`rdf_edges` or three -121 retries.

- **F3. A rollback leaves the temporal `$Increment` counters (SUSPECTED; relies on ADR-0010's measured IRIS behavior).**
  ADR-0010:19 and `USER_GUIDE.md:251-258` say IRIS does not undo `$Increment`. A changeset with a temporal op that is
  later rolled back loses `tout/tin/tlast/edgeprop/min/max/hll`, but keeps `bucket` +1 and `tagg.count` +1 and
  `tagg.sum` += w (`TemporalIndex.cls:102, 117-118`). A retry then counts the edge twice. The USER_GUIDE says a
  rollback leaves only `__version` and `gen` and "is harmless". Untested: `test_224...:136` fails before the temporal
  op runs.

- **F4. Temporal writes and purges change ledger-governed node state (SUSPECTED).** `read_canonical` reads every
  `nodes` row (`replay.py:598-600`). Genesis records every node (`LedgerGenesis`). `AssertTemporalRow` inserts
  endpoint nodes with no record (`Adjacency.cls:597`; edge row `:603`), including inside `OpCreateTemporalEdge` and in strict mode.
  The purge's `retire_bare_nodes` (the Python default since 4.7.0) deletes bare nodes with no ledger check
  (`Eraser.cls:1333-1352`). These include a ledger `create_node` with no label or prop used as a temporal endpoint.
  Either way `verify()` should report `diverges`/`unrecorded_writes`. Tests use only pre-created nodes `a`, `b`
  (`test_ledger_us11...:100-123`; `test_460_ledger_temporal_edge_e2e.py`). Distinguishing case: enable the ledger,
  run `create_edge_temporal("a","P","new:1",ts)`, then `verify()`. The 4.3.0 decision (43efd473) covers rows only
  (Q3).

- **F5. A ledger "insert" collision is silent and still recorded (source-proven; doc stale).** `changeset.py:334-335`
  says "insert (fail if key exists)". Since spec 254, `InsertEdge` returns 1 for a collision and
  `OpCreateTemporalEdge` records `create_temporal_edge` unconditionally (`LedgerApply.cls:635-639`). The revision diff
  then claims a temporal edge that changed nothing.

- **F6. The latest index can go stale-low under concurrency (SUSPECTED).** `NoteLatest` is an unlocked
  read-compare-set (`:493-496`). Writers of ts1 < ts2 on one `(s,p)` can interleave and leave `tlast = ts1`.
  Separately, two first writers into an empty graph each run `Kill ^KG("tlast",g)` (:90-92); the second can erase
  the first's entry while the flag says the index is complete. `Resolve` detects only vanished events (:411-415), so
  `get_latest_edges` returns an older event. Spec 255 claims the index is "kept exact". No concurrent test exists.

- **F7. Concurrent "insert" at the same coordinate counts twice (SUSPECTED).** The `$Data` guard (:84) and the writes
  are not locked. ADR-0010 explains why locks were avoided, but spec 254 FR-003 states first-write-wins
  unconditionally. Related and known: a write racing a purge or delete on one triple leaves a timestamp without a row
  (254 sign-off, Open bullet 3; unfixed at the pin).

- **F8. Opting a predicate back in before dropping strands its marked rows (open; likely bug).** The sequence is:
  register a predicate that has marked rows, purge all its timestamps (the purge skips registered predicates, :966),
  then call `set_temporal_structural(p, True)`. Now `DropRows` refuses (`TemporalPolicy.cls:132-134`), and no purge
  or delete can find the triples. The rows assert "exists at some time" forever, contradicting the ADR-0009
  amendment. ADR-0015's migration guidance assumes the drop runs before any rollback toggle.

- **F9. Two Python paths ignore the registry (SUSPECTED; legacy paths).** (a) With `IRISGraphEngine(...,
  temporal_structural_rows=True)` (undocumented; spec 246 "not adopted"), `_own_structural_row` writes a marked row
  through `create_edge` for any predicate (`temporal.py:182-198, 306-308`). (b) Without the adjacency index, a
  named-graph `create_edge_temporal`/bulk writes an **unmarked** mirror row and nodes for any predicate
  (`temporal.py:309-331, 455-475`). That row is never retracted, and `RetractTemporalShadows` keeps the shadow because
  a row exists (`Adjacency.cls:694-731`). ADR-0015 promises "no rdf_edges row".

- **F11. `create_edge_temporal(timestamp=None)` writes at ts 0 (SUSPECTED, low).** Python sends `0`
  (`temporal.py:294`), the store sends `"0"` (`iris_sql_store.py:2680`), and `InsertEdge` substitutes "now" only for
  `""` (`:51`). The bulk path substitutes "now" for 0 (`:170`). The unit test is named
  `test_timestamp_none_sends_empty_string` but asserts only `"A" in call_args` (`tests/unit/test_temporal_edges.py:58-62`).

**Unresolved questions (a human must decide)**

- **Q1 (F1). What do aggregates mean under "update"?** The options are: (a) as now, every write counts; (b) the
  aggregate describes the surviving raw edges, so update should run `RebuildBucketAggregate` and leave `bucket` alone,
  as delete does; (c) the documented "original value". This also decides whether rebuild determinism (FR-004) covers
  update mode.
- **Q2 (F10). Aggregate semantics in a purge-cut bucket.** ADR-0009:49 says aggregates "describe the past" after a
  purge, while `DeleteTemporalEdge`/`EraseNodes` rebuild a bucket from survivors (`:446-488`). After
  `purge_raw_before(tsEnd)` with `tsEnd` mid-bucket, a delete of a surviving edge in that bucket wipes the purged
  edges' contribution from `tagg` but not from `bucket`. Which rule wins?
- **Q3 (F4). Are nodes created by temporal writes governed?** One option marks or excludes them in genesis and verify,
  as for rows. Another treats them as unrecorded writes and guards the temporal path in strict mode. It also needs a
  decision whether `retire_bare_nodes` must skip ledger-recorded nodes.
- **Q4 (F8). Should `DropRows` accept a structural predicate's rows that no timestamp holds, or should toggling back
  refuse while marked rows of a registered predicate remain?** A related question: should `DeleteTemporalEdge` follow
  the purge's "leave registered predicates' rows" rule (C3 asymmetry)?
- **Q5. Window cursor semantics under concurrent inserts.** Is a non-snapshot live read acceptable (an edge inserted
  behind the cursor is missed, and pages can mix states), or is a snapshot bound wanted? Spec 255 addresses only
  purged events.

**Design simplifications (P)**

- **S1.** Remove the spec-246 Python path (`temporal_structural_rows` kwarg, `_own_structural_row`,
  `_owned_structural_row`, `_triple_survives`, the flag branch of `delete_edge_temporal`, and
  `migrations/temporal_structural_rows.py`, or make the last delegate to `TemporalPolicy.BackfillRows`). Rationale:
  ObjectScript `AssertTemporalRow`/`RetractTemporalRow` cover the same behavior with the marker and the registry.
  Preserve: idempotent backfill with a read-only dry run. Distinguishing case: flag on, predicate opted out, write;
  with the path removed no row appears.
- **S2.** Move `AssertTemporalRow` before the first Set in `WriteStores`, or wrap `WriteStores` in a
  `TSTART`/`TROLLBACK 1` at the caller's level. Then a failure leaves nothing and a retry is not a collision (F2).
  Preserve: the per-edge cost (no new statement) and "a collision changes no store". Distinguishing case: inject a
  `-121` that persists, retry the write, and check that `tagg`, `edgeprop` and the row exist afterwards.
- **S3.** Make the bulk fallback (`iris_sql_store.py:2759`) raise instead of re-sending the whole batch, or re-send
  only the edges not yet written. Preserve: the error carries the written count (R203).
- **S4.** Refresh stale text: the `delete_edge_temporal` "KNOWN AMBIGUITY" (`temporal.py:364-369`, false for indexed
  installs); the `Changeset.create_temporal_edge` "insert fails" note; ADR-0009:40 on Cypher; ADR-0002 "read or write"
  given `TemporalWindow` (F12); `ledger-api.md:92` on the strict-mode mirror; the `USER_GUIDE` rollback counter list
  (F3).
- **F12 (doc and design drift, low).** ADR-0002 forbids any other class to *read* the temporal globals, but
  `TemporalWindow` reads `tout/tin/edgeprop/tlast` directly. The guard test checks writers only
  (`test_temporal_single_owner.py:1-40`). The `Adjacency` key→`graph_id` mapping (`Adjacency.cls:583` and others) is
  an undeclared third derivation outside `GraphKey` (ADR-0003). It is correct only while `ForIndex(g) = ForName(g)`
  for named graphs.

## Not inspected / limits

- Not run: any test, IRIS, or Python against a database. Every behavioral claim is from source reading. F3 rests on
  ADR-0010's and the USER_GUIDE's statement about IRIS `$Increment` rollback.
- Not read: specs 223 and 224 (spec text absent at the pin; only commits and the CHANGELOG), spec 213 `spec.md`
  (absent), spec 204 `plan/tasks/contracts`, spec 239 `tasks.md`, and the 252 plan beyond grep.
- Not traced: Cypher `CREATE`/`MERGE` adoption in `translator.py` (I rely on the 254 sign-off for the three
  remaining gaps). Also untraced: `execute_temporal_cypher` and `QueryWindow` walks, `GetBucketGroups`, `FindBursts`,
  `GetVelocity`, label sets, snapshot and restore of temporal globals (`_engine/snapshot.py`, which writes `^KG("tout")`
  from Python), `Eraser.EraseEdges/EraseIdSet` call sites, `Ledger.Commit` catch details, and multigraph (`ekey`)
  interplay with `AssertTemporalRow`'s `^KG("out")` trust check.
- `TemporalIndex.cls:1180-1340` (MigrateOrphans, MigrateDerived, RebuildBucket) and `GetBucketGroups`/
  `BucketGroupsEvents` were skimmed only.
- Every source has one author. "Tom" decisions are recorded secondhand in specs, ADRs and commit messages.
