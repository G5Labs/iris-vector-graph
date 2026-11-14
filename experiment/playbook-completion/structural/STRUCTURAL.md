# Structural lane (steer 7): ownership, storage order, declared reads, keys, FK, capacity, row permutation, frame

Product pin `3eaa79cf`, unchanged (`check-product-scope.sh` passes at every registration). Namespace `AUDITD`
(fresh; the pin deployed by its own `initialize_schema` at 11:17 UTC and re-run once by this lane over data as a
module-01 probe, `st-live-setup-rerun`). Observation only: nothing compiled by the lane, scratch globals
`^IVGAuditD*` only (removed), every IRIS command under `tools/locks.sh iris`, at most 6 connections, each live
script self-contained in one lock hold that starts from the product's own `Graph.KG.Eraser.EraseAll` +
`Graph.KG.Ledger.PurgeAll` (`live/lib.py`). Raw logs: `$RUN_DIR/structural/<sub-lane>/`. Registered runs:
`evidence/runs/st-*.json`. New findings: `findings/audit/zz-structural.json`. Proposed cells: `MATRIX-INPUT.json`
(written by `merge.py` from the sub-lanes' `cells.json`; this file is rendered by `render.py`).

The work ran as five sub-lanes, each with its own directory, method record (`<sub>/method.json`), self-test and
runs: `ownership/` (3.4-ownership), `order/` (3.4-storage-order, 3.6-row-permutation), `reads/`
(3.4-declared-reads), `frame/` (3.6-frame), `capkeys/` (3.6-capacity, 3.6-keys, 3.6-fk).

Evidence grades stay apart: `live` (observed on AUDITD through the product's entry points), `check` (a mechanical
source check with a self-test; graded inspected), `inspected` (read at the pin, path:lines). Nothing here is proved,
and no probe result is a proof that an obligation holds: where the probes found no violation the cell's product
obligation is `unknown` (shown below as "no violation seen"). A closed cell means the verification step was done
with a registered decisive run and a self-test.

## Result per gate and module

| Module | ownership | storage-order | declared-reads | keys | fk | capacity | row-permutation | frame |
|---|---|---|---|---|---|---|---|---|
| 01 | C: fails (F-1806) | C: no violation seen | C: fails (F-0106) | C: no violation seen | C: no violation seen | O: no violation seen | C: no violation seen | O: no violation seen |
| 02 | C: fails |  |  |  | C: no violation seen |  | C: no violation seen | O: no violation seen |
| 03 | C: fails (F-0503, F-1502, F-1503, F-1604) | C: fails (F-C0302, F-0206) | O: no violation seen | C: fails (F-C0349, F-C0348) | C: no violation seen | C: fails (F-C1106) | C: fails (F-C0302, F-0206) | O: no violation seen |
| 04 | C: fails (F-0404, F-1806, F-C0440, F-C0640, F-C1040, F-C1540) |  | O: no violation seen | C: no violation seen | C: no violation seen | C: no violation seen | C: no violation seen | O: no violation seen |
| 05 | C: fails (F-0503) |  | C: fails (F-0508) | C: no violation seen | C: no violation seen |  | C: no violation seen | O: no violation seen |
| 06 | C: fails (F-0618, F-1806, F-C0640, F-C0840, F-C1540, F-C1740) | C: fails (F-C0603, F-C0604, F-C0642) |  |  |  | C: no violation seen | C: fails (F-C0642) | O: no violation seen |
| 07 |  |  |  |  |  | C: fails (F-C0748, F-0704) | C: fails (F-C0703) | O: no violation seen |
| 08 | C: fails (F-C0840) |  |  | C: no violation seen |  | C: fails (F-C0848, F-C0849, F-C1106) |  | O: no violation seen |
| 09 | C: fails (F-1806) | C: no violation seen |  |  |  | C: fails (F-C0948) |  | O: no violation seen |
| 10 | C: fails (F-1806, F-C1040, F-C1240) |  | O: no violation seen |  |  |  | C: no violation seen | O: fails (F-C1001) |
| 11 |  | C: fails (F-0205, F-C1108) | O: no violation seen |  |  |  | C: intent-undecided (F-C1108) | O: no violation seen |
| 12 |  | C: no violation seen | O: no violation seen |  |  |  | C: no violation seen | O: no violation seen |
| 13 |  | C: no violation seen | O: no violation seen |  |  | C: no violation seen | C: no violation seen | O: no violation seen |
| 14 |  | C: no violation seen | O: no violation seen |  |  | C: no violation seen | C: no violation seen | O: no violation seen |
| 15 | C: fails (F-1502, F-1503, F-C0840, F-C1540, F-C1740) |  | C: fails (F-1507, F-C1547) | C: no violation seen | C: fails (F-C1548) | C: fails (F-C1549, F-1501) | C: no violation seen | O: no violation seen |
| 16 | C: fails (F-1604) | C: fails (F-C1642) |  |  |  |  | C: fails (F-C1642) |  |
| 17 |  | C: fails (F-C1742, F-1701) |  | C: fails (F-1707) |  | C: fails (F-C1106) | C: fails (F-C1742) | O: no violation seen |
| 18 | C: fails (F-0404, F-1801, F-1805, F-1806) | C: no violation seen | O: no violation seen | C: fails (F-1802) |  | C: fails (F-C1848) |  | C: no violation seen |

C = closed (registered decisive run + self-test, or a committed analysis graded inspected), O = open (the cell's 'remaining' text in MATRIX-INPUT.json says exactly what is missing); 'no violation seen' is product_obligation 'unknown': the probes found no violation, which is not a proof. An empty cell is a (gate, module) pair this lane did not decide (closed earlier by another lane, or not in the task's open list).

## Method and result per gate

### 3.4-ownership (sub-lane `ownership/`)

Method: `ownership/census_all.py`, a generalised copy of `tools/writer_census.py`, finds every write site of every
durable store at the pin (ObjectScript Set/Merge/Kill/$Increment incl. multi-target Set and resolved indirection,
%Save/%KillExtent/%DeleteId, embedded and dynamic SQL DML/DDL; Python SQL text with run-time names resolved, Native
API set/kill/increment; ^KG/^NKG/^IVG.Ledger split by first subscript). Sites are attributed to modules through
`models/breadth-c/inventory.json`; each store has a declared owner with a citation (ontology Scope lines, ADR-0011,
ADR-0002, GraphStores.Inventory, the snapshot STORE_PLAN). Every writer module other than the owner breaks the
single-owner rule; those no document names are ownership findings. Controls: the census finds all 268 sites of the
registered census (`followup-writer-census`), agrees with the product's own guard
`tests/unit/test_adjacency_single_writer.py`, and explains all 393 journal-observed (entry, store) pairs of
`footprints/NN.json` (0 gaps). Self-test: 8 seeded cases (multi-target Set second writer, delegating call not
flagged, indirection Kill, f-string DELETE, variable-name Native kill) all classified correctly.
Runs: `st-control-own-selftest` (pass), `st-check-own-controls` (pass), `st-check-own-census` (fail).

Result: 1,826 write sites over 101 stores; 98 stores have more than one writer module (nodes 11 modules, rdf_edges
10, rdf_labels 9, rdf_props 11): 140 co-writes some document names, 25 no document names, 30 conditional (restore's
any-global loaders), 21 ADR class violations. The rule fails for every module decided (01-06, 08-10, 15, 16, 18).
New findings F-C0440, F-C0640, F-C0840, F-C1040, F-C1240, F-C1540, F-C1740; reused F-0404, F-0618, F-1604, F-1801,
F-1805, F-1806. Open: schema-object (DDL) ownership is listed, not decided (F-0107 stays); whether the named shared
ownership is acceptable is a maintainer decision.
Process note for the orchestrator: the sub-lane rewrote the records of `st-check-own-controls` and
`st-check-own-census` (same ids, same unchanged logs) to correct counts it had misstated, before any commit; each
record carries a `note` saying so. CONVENTIONS asks for errata instead; the orchestrator decides whether to keep the
rewritten records or replace them with new ids.

### 3.4-storage-order (sub-lane `order/`)

Method: `order/storage_order_scan.py`, a copy of `tools/storage_order_check.py` with six more rules (a TOP/LIMIT
split across literals, Python first-row reads of unordered multi-row statements, ObjectScript `SELECT INTO` and
single `%Next()` reads, identity allocation in an unordered cursor loop, count cut-offs over a cursor or $Order,
slices of unordered lists). 292 sites; all 198 in the 11 gated modules disposed in `order/dispositions.json` (82 by
hand, each with path:line and an anchor text the gate re-checks at the pin): ORDER BY present / order irrelevant
(existence, unique key, documented sample, set-valued) / reliance (a finding). The gate fails on an undisposed or
stale site. Self-test: 7 planted rules caught, 7 order-free seeds not flagged; the original checker misses 6 of the
7 (`st-control-so-selftest`). Reliance was confirmed live where feasible (`st-live-so-*`).
Runs: `st-check-so-gate` (pass: every site disposed), `st-control-so-selftest`, `st-live-so-confirm`,
`st-live-so-11`, `st-live-so-17b`.

Result: reliance in 03 (F-C0302, F-0206), 06 (F-C0603, F-C0604, new F-C0642: vector top-k cuts tied scores in
storage order), 11 (F-0205 live: a ledger delete by tuple removes the parallel edge inserted first; F-C1108), 16
(new F-C1642), 17 (new F-C1742; and new F-C1743, S2: `IRISGraphStore.query_nodes(limit=n)` kills the calling Python
process with SIGSEGV on 2026.1 / driver 5.3.2). No reliance in 01 (only inside a documented sample), 09, 12, 13,
14, 18. Not disposed: 39 candidate sites of modules whose cells other lanes closed (15, 10, 08, 02, 05, 07), listed
in `order/method.json`.

### 3.4-declared-reads (sub-lane `reads/`)

Read-oracle feasibility, decided on the instance (`reads/method.json`): the SQL statement index records a dynamic
statement's relations at prepare time but no synchronous per-execution count and nothing for embedded SQL
(`st-probe-reads-stmtindex`); per-job PTools stats see only statements compiled after the flag (cached and
embedded SQL invisible without purging or recompiling, which the rules forbid; `st-probe-reads-ptools`);
%Monitor.System.LineByLine shows executed INT lines and global-reference counts but not which globals or subscripts,
so not the graph key (`st-probe-reads-linebyline`). Oracle used instead: non-interference. Each read action runs on a
base state and again after perturbations outside its declared footprint (the same ids with other labels,
properties, edges, temporal edges or vectors in every other graph; undeclared stores; another tenant's commits); a
changed answer is a read outside the footprint; an inside perturbation checks sensitivity. A second, table-level
oracle wraps the harness's DB-API cursor and records the SQL text the product's Python code sends. Self-test
(`st-control-reads-selftest`): a seeded graph-blind reader is flagged, the scoped one not; a seeded read of an
undeclared table is reported. Runs: `st-live-reads-a` (01-06), `st-live-reads-b` (10-18), `st-live-reads-c` (18
rerun with timestamps masked; the 18 verdict in `-b` was a harness artefact).

Result: reads outside the footprint in 01 (F-0106), 05 (F-0508), 15 (F-1507 and new F-C1547: get_reifications
reads the reifier's properties from every graph). The other decided modules show no violation among the checked
actions but stay open because most inventoried read entry points were not checked (counts and names in each cell's
`remaining`). Non-interference sees only reads that reach the answer, under the listed perturbations.

### 3.6-keys, 3.6-fk, 3.6-capacity (sub-lane `capkeys/`)

Method (`capkeys/method.json`): live probes through each module's public entry points, every case from an empty
namespace. Key oracle: no duplicate declared key by `%IGNOREINDEX *` full scans (which see %NOINDEX/%NOCHECK rows),
^KG out/in and label index equal to the rows, edge ids distinct, the DDL's constraints present in the catalog. FK
oracle: edge endpoints, labels, properties (no declared FK), node embeddings, ^KG out/in/label/tout endpoints,
reification edge and reifier node, by full scans. Capacity oracles: exact read-back (length and SHA-256), the
journal's net effect of the failing call (non-transactional counters excluded) to tell clean refusal from partial
write, rows vs ^KG vs temporal reads for widths, client memory (tracemalloc) for snapshots, and a second process
against a lock-escalated transaction. Self-test `st-control-capkeys-selftest`: 7 + 9 seeded key/FK states each
reported with exactly its condition, 7 value outcomes, live reader checks on scratch globals.

Capacity results: every writer of rdf_edges refuses an edge past s = o = 194, p = 97 (155 with a 100-character
graph name; 195/156 at lower row ids, so the limit shrinks with the row-id length) with SQLCODE -415 and nothing
written, the limit F-C1106 records for the ledger; the temporal writer leaves temporal entries behind (F-C0501).
Column widths and the 3,641,144-character limit are refused cleanly everywhere probed; ledger records up to 3.6 M
characters pass every reader of 11/13/14/18 exactly. Defects: BM25 builds fail on one long token after emptying the
index (F-C0748), a Cypher CREATE/MERGE with literal endpoint ids drops parameter-bound relationship properties
(F-C0848, found by the read-back oracle at every size) and stores a WITH-bound one as non-JSON (F-C0849), PROV
one-edge lookups read the whole history as one string (F-C1549), snapshots hold the whole archive in client memory
(about 11 MB per 1,000 edges, F-C1848), compiled native plan classes have no bound (F-C0948, inspected). A caller
transaction of 1,500 inserts escalates to table locks on nodes and rdf_props and another process's write to any graph
then fails after 10 s with SQLCODE -110 (clean): no IVG document states whether that is acceptable; reported as
intent-undecided without a finding id. Redaction of 1,100 revisions in one batch did not block another tenant's
commits.

Keys results: the key invariants hold for every writer probed except the bulk loader, which writes duplicate node,
label, property and edge keys (in-batch duplicate id, `skip_existing=False`, two loaders at once; F-C0349), and
racing `create_edge` calls on a new edge whose endpoint is new, which in 4 of 8 trials answer False ("already
exists") for an edge that is never written (F-C0348). Racing MERGE/CREATE/reify keep the keys and answer errors.
FK results: hold for 02, 03, 04, 05; in 15, `delete_edge` and Cypher `DELETE r` leave reification rows naming deleted
edges (F-C1548). Setup (01) keeps all 24 declared constraints and every row when re-run over data.

### 3.4-storage-order's companion: 3.6-row-permutation (sub-lane `order/`)

Method: `order/permutation.py` writes the same data through the product's writers in three insertion orders
(forward, reverse, shuffle; reset between orders, inside one lock hold) and compares the module's read APIs:
multiset equality where no order is promised, list equality where an order or a top-k/page cut is part of the
contract (cited per API in `order/method.json`). Self-test `st-control-so-perm-selftest`: a seeded `TOP 1` reader over
`%IGNOREINDEX *` is flagged, a seeded ORDER BY reader is not. One verdict run per module (`st-check-so-perm-NN`).

Result: answers differ by insertion order in 03 (F-C0302, F-0206), 06 (F-C0642), 07 (F-C0703 live), 16 (F-C1642), 17
(F-C1742; query_nodes(limit) crashes, F-C1743), and 11's detach-delete statement ids (F-C1108, intent-undecided).
Equal in three orders for the listed reads of 01 (documented sample, every answer valid), 02, 04, 05, 10, 12, 13, 14,
15. Not permuted: Bolt/HTTP surfaces (16), FHIR sync (15), random walk/Leiden/Arno (10), redaction stop/resume (13).

### 3.6-frame (sub-lane `frame/`)

Method (`frame/method.json`): statement-shape classes (SQL insert, update-by-key, delete-by-key,
delete-by-predicate, DDL; global set of a keyed node, kill of a keyed subtree, $Increment counter, merge;
%Save/%KillExtent) with a census of each module's source per class (`frame/shape_census.py`). 108 writer actions run
live through the product's API, each from a reset plus base data in the action's graph, a bystander graph and the
default graph; the IRIS journal filtered to the action's process is the oracle. Store level: every journaled node's
store is in the entry point's declared writes (read unchanged from `footprints/NN.json` / `correspondence.json`);
key level: every node lies under the action's argument keys or is a cited counter/version node. A module's cell
closes only if the self-test passed, every excursion is explained, and every statement-shape class present in the
module's source is observed in the journal of its actions. Self-test `st-control-frame-selftest`: a conforming
create_node passes, a seeded write to `^IVGAuditDFrmX` is caught at store level, a seeded second node at key level.
Runs: `st-live-frame-r8` (live, fail), `st-check-frame-aggregate` (check, fail); seven earlier debug passes fixed the
harness only and are not registered.

Result: 100 of 108 actions wrote; store level held on 98, key level on 107. The one product excursion is F-C1001
(module 10: `triangle_count`, a read, writes `^IVG.Deploy("routines")`), reproduced again. Nine store excursions are
footprint omissions, not product defects, and were not widened (01/06 `embedding_registry`, 03 `^NKG("$meta")`,
05 adjacency from the backfill and the temporal subtrees, 10 `^KG("degc")`, 12 routed vector tables in EraseAll,
14 `Ledger.PurgeAll`; list in `frame/dispositions.json`). Three statements the matrix listed as unexecuted were
reached and held at key level (`LedgerApply.cls:664`, `LedgerGenesis.cls:110-111`, `LedgerRedact.cls:465`).
Graph-scoped erasures drop the whole `^NKG` snapshot and every graph's `^IVG.AlgoCache`, which is declared
(`Eraser.cls:1036-1052`). Only 18 closes; the others stay open because a statement-shape class in their source was
not observed (DDL mostly, which `traces/journal.py` filters out except `^oddTSQL`), listed per module in each
cell's `remaining`.

## Exact open obligations (by gate)

- 3.4-declared-reads / 03 (open): 20 of 43 inventoried read/both entry points not checked: py:IRISGraphEngine.bulk_create_edges, py:IRISGraphEngine.bulk_create_nodes, py:IRISGraphEngine.bulk_ingest_edges, py:IRISGraphEngine.delete_edge, py:IRISGraphEngine.delete_node, py:IRISGraphEngine.store_edge, py:IRISGraphEngine.store_node, py:iris_vector_graph.bulk_loader.BulkLoader.load_edges, py:iris_vector_graph.bulk_loader.BulkLoader.load_networkx, py:iris_vector_graph.bulk_loader.BulkLoader.load_nodes, py:IRISGraphEngine.bulk_delete_nodes, py:IRISGraphEngine.bulk_load_session, py:IRISGraphEngine.erase_all, py:IRISGraphEngine.set_edge_weight, py:iris_vector_graph.bulk_loader.BulkLoader.build_graph_globals, cls:Graph.KG.PropWrite.Layout, cls:Graph.KG.PropWrite.SetVal, py:iris_vector_graph._batch_check.missing_rows, py:iris_vector_graph._dictionary.compiled_class_exists, py:iris_vector_graph._dictionary.compiled_method_exists | i
- 3.4-declared-reads / 04 (open): 113 of 116 inventoried read/both entry points not checked: cls:Graph.KG.Adjacency.Put, cls:Graph.KG.Adjacency.PutShadow, cls:Graph.KG.Adjacency.Remove, cls:Graph.KG.Adjacency.Reweight, cls:Graph.KG.TraversalBuild.BuildKG, py:IRISGraphEngine.sync, cls:Graph.KG.Adj.WarmAll, cls:Graph.KG.Adj.WarmCache, cls:Graph.KG.Adj.WarmFill, cls:Graph.KG.AdjIndex.DeleteIndex, cls:Graph.KG.AdjIndex.InsertIndex, cls:Graph.KG.AdjIndex.UpdateIndex, cls:Graph.KG.Adjacency.AssertTemporalRow, cls:Graph.KG.Adjacency.EndRebuild, cls:Graph.KG.Adjacency.FillTriple, cls:Graph.KG.Adjacency.MarkGraphGone, cls:Graph.KG.Adjacency.PutKeyed, cls:Graph.KG.Adjacency.RemoveKeyed, cls:Graph.KG.Adjacency.RemoveNode, cls:Graph.KG.Adjacency.RemoveSource, cls:Graph.KG.Adjacency.RetractTemporalRow, cls:Graph.KG.Adjacency.RetractTemporalRows, cls:Graph.KG.Adjacency.RetractTemporalShadows, cls:Graph.KG.Adjacency.RowPut, cls:Graph.K
- 3.4-declared-reads / 10 (open): 200 of 219 inventoried read/both entry points not checked: cls:Graph.KG.Algorithms.WCCJson, cls:Graph.KG.Algorithms.CDLPJson, cls:Graph.KG.PageRank.RunJson, cls:Graph.KG.PageRank.CheckArgs, cls:Graph.KG.PageRank.NodeSeeds, cls:Graph.KG.PageRank.WithUnscored, cls:Graph.KG.PageRank.Run, cls:Graph.KG.PageRank.PageRankGlobalJson, cls:Graph.KG.PageRankEmbedded.ComputePageRank, cls:Graph.KG.PageRankEmbedded.ComputePageRankWithMetrics, cls:Graph.KG.Centrality.DegreeCentralityJson, cls:Graph.KG.Communities.TriangleCountJson, cls:Graph.KG.Communities.KCoreJson, cls:Graph.KG.Communities.SCCJson, cls:Graph.KG.Communities.LeidenJson, cls:Graph.KG.Communities.ClosenessJsonPy, cls:Graph.KG.Communities.LeidenJsonPy, cls:Graph.KG.Communities.LeidenJsonAuto, cls:Graph.KG.Subgraph.SubgraphJson, cls:Graph.KG.Subgraph.PPRGuidedJson, cls:Graph.KG.Traversal.DijkstraProc, cls:Graph.KG.Traversal.BuildKG, cls:Gr
- 3.4-declared-reads / 11 (open): 36 of 37 inventoried read/both entry points not checked: cls:Graph.KG.Ledger.NowMs, cls:Graph.KG.Ledger.NewId, cls:Graph.KG.Ledger.State, cls:Graph.KG.Ledger.GKey, cls:Graph.KG.Ledger.MetaGet, cls:Graph.KG.Ledger.Err, cls:Graph.KG.Ledger.ErrLimit, cls:Graph.KG.Ledger.RevisionObj, cls:Graph.KG.Ledger.RevisionResponse, cls:Graph.KG.Ledger.ReadLargeOutChunk, cls:Graph.KG.Ledger.Meta, cls:Graph.KG.Ledger.Head, cls:Graph.KG.Ledger.SeqOf, cls:Graph.KG.Ledger.StmtForTuple, cls:Graph.KG.LedgerApply.Enc, cls:Graph.KG.LedgerApply.EncNull, cls:Graph.KG.LedgerApply.Rec, cls:Graph.KG.LedgerApply.IsReserved, cls:Graph.KG.LedgerApply.Run, cls:Graph.KG.LedgerApply.NodeExists, cls:Graph.KG.LedgerApply.TupleJson, cls:Graph.KG.LedgerApply.ParseQuals, cls:Graph.KG.LedgerApply.FindEdge, cls:Graph.KG.LedgerApply.NodeSnapshotJson, cls:Graph.KG.LedgerApply.QualsJson, cls:Graph.KG.LedgerApply.WeightOf, cls:Graph
- 3.4-declared-reads / 12 (open): 1 of 3 inventoried read/both entry points not checked: erase-edges-all (EraseEdgesAll) | non-interference sees only reads that reach the answer, and only under the perturbations listed per action in structural/reads/method.json
- 3.4-declared-reads / 13 (open): 2 of 3 inventoried read/both entry points not checked: redact-stop-resume (max_batches > 0, then resume), GraphLedger.redaction_in_progress | non-interference sees only reads that reach the answer, and only under the perturbations listed per action in structural/reads/method.json
- 3.4-declared-reads / 14 (open): 4 of 7 inventoried read/both entry points not checked: diff, export_reconstruction, Graph.KG.Ledger Records page reader (SqlProcs.LedgerRecordsFetch) / CanonicalRecord, post-commit-properties | non-interference sees only reads that reach the answer, and only under the perturbations listed per action in structural/reads/method.json
- 3.4-declared-reads / 18 (open): 4 of 5 inventoried read/both entry points not checked: IRISGraphEngine.snapshot_info, POST /admin/snapshot, Graph.KG.Snapshot.NodeValueJSON, Graph.KG.Snapshot.ReadFileChunk / GetFileSize / FileExists | non-interference sees only reads that reach the answer, and only under the perturbations listed per action in structural/reads/method.json
- 3.6-capacity / 01 (open): setup's size-dependent statements are the legacy upgrade steps (iris_vector_graph/migrations/upgrade.py:441-451, statements.py:331, kg_node_stores.py:335-356, docs_and_edge_vectors.py:575: whole-table fetchall); they run only on a pre-4.6 namespace, which needs the pinned release fixture (scripts/fixtures/build_release_namespace) in a scratch namespace; not driven here
- 3.6-frame / 01 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl, sql-delete-key, sql-delete-predicate, sql-update | writer actions run but not exercised (error or no journaled write): 01-remove-legacy (no journaled write) | remove_legacy_objects(dry_run=False) journaled nothing (no legacy objects in AUDITD; making them needs an older release's classes, out of scope); the upgrade and migration writers (upgrade_to_4_0_0, add_graph_id_column/_index/_to_nodes, add_graph_oid_index, tighten_graph_id_column, stage_class_owned_rdf_edges, update_spo_unique_constraint, upgrade_val_column, ensure_ekey, disable_indexes) need a pre-4.x schema and were not run; the DDL class is not observable with the journal oracle: traces/journal.py filters the catalog globals (^oddDEF, ^oddCOM, ^oddSQL, ^rINDEXSQL) as system globals; only ^oddTSQL is visible
- 3.6-frame / 02 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | the only source class not observed is sql-ddl, from iris_vector_graph/engine.py:765-803 (_drop_fetch_first_probe_tables / the FETCH FIRST probe's scratch tables), attributed to 02 by engine.py's file owners because no inventoried entry contains those lines; the probe was not run under the journal. GraphMode.Set and the Kill of set_multigraph(False) were exercised and held at key level (^IVG.GraphMode("fg") only)
- 3.6-frame / 03 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | sql-ddl not observed (engine.py:765-803 FETCH FIRST probe, as module 02); BulkLoader.load_nodes/load_edges/load_networkx/build_graph_globals, bulk_load_session and the LabelIndex functional-index callbacks as separate entry points were not run (the callbacks ran inside every label write)
- 3.6-frame / 04 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl, sql-delete-predicate, sql-update | writer actions run but not exercised (error or no journaled write): 04-backfill-degp (no journaled write) | source classes not observed in module 04's own actions: sql-ddl (adjacency index DDL), sql-delete-predicate (EdgeScan/Adjacency SQL deletes), sql-update (nodes_edges.py:91 adoption UPDATE, observed under module 03's 03-create-edge-adopts-temporal-row, where its frame held); backfill_degp journaled nothing (nothing to backfill); 83 class-level writer entry points of footprints/04.json ran only inside the engine actions exercised (sync, rebuild_kg, rebuild_nkg, Reweight, Degree, AssertTemporalRow) or not at all. Namespace-wide rebuilds (sync, rebuild_kg, rebuild_nkg) are whole-store actions: store level only
- 3.6-frame / 05 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | sql-ddl not observed (engine.py:765-803 FETCH FIRST probe, attributed by file owners); the class-level writers of TemporalIndex (Migrate*, Rebuild*, RetireExpired, UpdateHLL, BackfillWalk, Purge (all graphs, F-0507)) ran only through the engine actions exercised or not at all
- 3.6-frame / 06 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | sql-ddl: the route's CREATE TABLE writes its catalog to globals traces/journal.py filters as system globals, so only its storage and registry row are judged; EmbedQueue.ProcessBatch / process_embed_queue, embed_nodes/embed_edges, place_quarantined, reconcile_recorded_dimensions, adopt_embedding_identities, the 4.0.0 migrations and VectorOptimizer.migrate_to_optimized were not run (they need an embedding model or legacy data)
- 3.6-frame / 07 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl, sql-insert, sql-update | writer actions run but not exercised (error or no journaled write): 07-bm25-upgrade (no journaled write) | source classes not observed: sql-ddl, sql-insert, sql-update at iris_vector_graph/schema.py:3165-3240 (the generated kg_TXT SQL procedures, attributed to 07), not run; bm25_upgrade journaled nothing (the index was already at the current schema; an old-schema index cannot be made without an older release). Build, Insert, Delete and Drop held at key level (^BM25Idx("fb") and the stopword list only); every BM25 write is outside a transaction (F-0701, not a frame matter)
- 3.6-frame / 08 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | sql-ddl not observed: iris_vector_graph/_engine/query.py:1887-1892 (Cypher schema commands CREATE/DROP INDEX/CONSTRAINT) and the engine.py FETCH FIRST probe were not run; Cypher CREATE, SET (insert and update), MERGE, DELETE, DETACH DELETE and map_sql_table held at key level
- 3.6-frame / 09 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: global-increment, global-kill, global-merge, global-set, sql-ddl | writer actions run but not exercised (error or no journaled write): 09-gen-mode (no journaled write); 09-gen-dropall (no journaled write); 09-native-read-off (no journaled write) | no persistent writer of module 09 was exercised: Gen.For / Gen.Build (job and sync mode) compile a generated class IVGC.P<h>, which this audit may not do (CONVENTIONS: nothing but the pin's classes through the pin's deploy path is compiled), so every run here set the process compile mode to off; Gen.DropAll journaled nothing (no ^IVG.CypherCompiled entry exists in AUDITD); IVG.CypherEngine.InitSchema*/RebuildKG/SmokeTest not run. A native read in mode off wrote nothing persistent (store and key level trivially held)
- 3.6-frame / 10 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | sql-ddl not observed (engine.py:765-803 FETCH FIRST probe, attributed by file owners; F-C1001's CREATE FUNCTION DDL is filtered by the journal oracle as system globals); 87 class-level writers of footprints/10.json ran only through the engine actions exercised or not at all
- 3.6-frame / 11 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | sql-ddl not observed (iris_src/src/Graph/KG/Ledger.cls:232 BUILD INDEX, not run). Reached and held at key level: LedgerApply.cls:664 (the rdf_reifications DELETE of a deleted relationship: KILL ^t52S.fjEY.1(rowid) in 11-commit-delete-rel-reified) and LedgerGenesis.cls:110-111 (adoption of a delete_rel: KILL ^IVG.Ledger("tuple","lt|a","R","lt|b","") and SET ^IVG.Ledger("stmt",5) in 11-reenable-adoption)
- 3.6-frame / 12 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-update | sql-update not observed in module 12's actions (nodes_edges.py:91, a module constant used by module 03's create_edge, attributed by file owners); FHIR side tables, ^IVG.AdjNoLock and RemoveSource's in-kill were not reached (no FHIR graph, the writer lock was always granted)
- 3.6-frame / 13 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-delete-key | sql-delete-key not observed: iris_vector_graph/ledger/client.py:473 (the post-commit property DELETE, attributed to 13 by the inventory) did not run with an existing property. Reached and held: DropStatements' tuple kill LedgerRedact.cls:465 (KILL ^IVG.Ledger("tuple","ta|1","R","ta|2","") with its ("stmt",5)); tenant b's revision was not written
- 3.6-frame / 14 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | writer actions run but not exercised (error or no journaled write): 14-readers (no journaled write) | sql-ddl not observed (Ledger.cls:232 BUILD INDEX); readers journaled nothing (held trivially); verify and verify(adopt=True) held at key level
- 3.6-frame / 15 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl | sql-ddl not observed (FHIRGraph.cls:1428-1430 and the FHIR-graph table DDL in _engine/schema.py); the FHIR-graph writers (Register, Rebuild, SyncOnce, Reinterpret, Schedule/Unschedule, FHIRGraphSyncTask.OnTask, RecordError), migrate_fhir_bridges_to_crosswalk and attach_embeddings_to_table were not run
- 3.6-frame / 17 (open): statement-shape classes present in the module's source but not observed in the journal of its exercised actions: sql-ddl, sql-update | writer actions run but not exercised (error or no journaled write): 17-write-nodes-update (no journaled write) | sql-ddl (dbapi_utils.py:191, 222; utils.py:62-64 index helpers) and sql-update (dbapi_utils.py:161) not observed; execute_sql(read_only=True) with an INSERT (HD-1701) and dbapi_utils.insert_vector not run; write_nodes over an existing node journaled nothing

Closed cells with a stated residue (44): see each cell's `remaining` in MATRIX-INPUT.json.

## Not findings, reported for decision

- Lock escalation across graphs (capkeys): one caller transaction with more than about 1,000 row writes per table
  makes every other process's write to that table, in any graph, fail after 10 s with SQLCODE -110 (`st-live-cap-batch`).
  Answers stay consistent; whether one tenant may block another is not stated anywhere (intent-undecided).
- A count aggregate of 4 for 3 temporal events after `keys.py`'s combined sequence (`st-live-keys`), not repeated in 18
  isolated trials (`st-live-keys-temporal-count`, `st-live-keys-temporal-race`).
- Reused, unregistered first-attempt logs are listed in `capkeys/method.json` (`unregistered_logs`) and the order
  sub-lane's superseded results in `order/method.json` (`superseded`).
