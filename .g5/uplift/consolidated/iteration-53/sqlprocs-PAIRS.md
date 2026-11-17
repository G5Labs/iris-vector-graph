# Iteration 53 Part B: graph SQL procedures — input → decision → SQL reader (frozen predictions)

Frozen 2026-11-17T05:10Z, **before** reading the deciding bodies of `iris_src/src/Graph/KG/SqlProcs.cls`
(`MatchEdges`, `MatchEdgesAllGraphs`, `DijkstraPath`, `backfilltemporalrows`, `rebuildedgeindices`), every
`iris_src/src/Graph/KG/Traversal*.cls` body (`DijkstraProc`, `DijkstraJson`, the edge scan), the translator's emit code
for the `IVG_EDGESCAN` hop and for `CALL ivg.shortestPath.weighted`, `TemporalIndex.BackfillRows`, the setup code that
calls the backfill, and any test body.

Sources used: `docs/ADMIN_GUIDE.md` L425-L436 (the projected routines), L545-L580 (the read path, the global-reader
SELECT check, the write-privilege check of `backfill_temporal_rows` and `rebuild_edge_indices`), L1198-L1226 (temporal-only
predicates and the upgrade backfill), L1244-L1250 (`IVG_EDGESCAN`); `docs/USER_GUIDE.md` L631-L660 and L795-L812
(`ivg.shortestPath.weighted` arguments, defaults, graphs, costs, directions); `docs/API_REFERENCE.md` L3210-L3216
(`IVG_EDGESCAN`); `CHANGELOG.md` (R140 seventh argument and the empty-types rule, R154 `USE GRAPH`, `maxHops` "0 or less
is no bound", 4.6.0 `'in'` fix, floats in 4.6.3, R269/R274/R295 "Called from SQL with `''`, `MatchEdges` answered `[]`",
R289/R293/R294 privilege checks, the 4.3.0 `rdf_edges` join replacing the scan, the upgrade backfill skipping registered
predicates and its bounded memory); signatures and `///` docstrings of the five `SqlProcs` methods and
`Traversal.DijkstraProc` (extracted without bodies: `DijkstraPath`'s says `predsJson` "" walks every type and `pGraphId`
'' or NULL is the default graph); the `_engine/temporal.py` `create_edge_temporal` docstring's adjacency contract; the
owners [algorithms.op.paths.weighted](../../../ontology/features/algorithms.g5.md#algorithms.op.paths.weighted),
[access.iris_boundary](../../../ontology/concepts/access.g5.md#access.iris_boundary),
[temporal.structural](../../../ontology/features/temporal.g5.md#temporal.structural) with `.mark`, `.upgrade`,
[structure.rebuild](../../../ontology/features/graph-structure.g5.md#structure.rebuild); the existing models
`weighted_paths` (`effective`: a weight of zero or less, or none, costs 1; direction and predicate selection) and
`weighted_cost`.

Each row: the changing input or history, the SQL reader, the predicted difference, the source. Fixture: a fresh
namespace from `%SYS` on `ivg-cont-20261117-iris`, prefix `i53p_`.

## W-ME: `MatchEdges(sourceId, predicate, shard, graph)` and `MatchEdgesAllGraphs(sourceId, predicate, shard)`

| # | Changing input | Reader | Prediction (neighbor A vs B) | Source |
|---|---|---|---|---|
| ME1 | predicate `'P'` vs `''` | `SELECT Graph_KG.MatchEdges(s, p, 0, g)` | A: only `P`-edges out of `s` in `g`. B: `''` means every predicate (all of `s`'s out-edges), not `[]`. | CHANGELOG R269/R295 fix note |
| ME2 | the same `(s, P, o)` in graphs `g1` and `g2`, plus `(s, P, o2)` only in `g2` | `MatchEdges(s,'P',0,'g1')` vs `MatchEdgesAllGraphs(s,'P',0)` | A: `g1` answers `o` only. B: all graphs answer `o` (once per graph or once overall — undecided by docs; predicted once per graph, each with its graph) and `o2`. | signature; all-graphs read in CHANGELOG |
| ME3 | caller with vs without SELECT on `rdf_edges` (EXECUTE granted) | the same `MatchEdges` call | A: answers. B: fails SQLCODE -99 `lacks SELECT on Graph_KG.rdf_edges`, nothing read. | ADMIN_GUIDE L573; `access.iris_boundary` |
| ME4 | `IVG_EDGESCAN` unset vs `1` | `execute_cypher("MATCH (a {id:$x})-[r:P]->(b) RETURN b.id")` on the SQL path | Same answer on both plans for edges written by `create_edge` with the adjacency index declared. | ADMIN_GUIDE L1248 ("the plan before 4.3.0"); CHANGELOG 4.3.0 "every answer equal" |
| ME5 | `shard` 0 vs 1 | `MatchEdges(s,'P',1,g)` | A (0): every edge. B (1): no documented meaning; predicted `[]` (no edges assigned to shard 1 on a single-shard install). Low confidence. | signature only |

## W-DJ: `DijkstraPath(src, dst, weightProp, maxCost, maxHops, direction, predsJson, pGraphId)` vs `CALL ivg.shortestPath.weighted`

Fixture graph `g`: `a -P(1)-> b -P(1)-> c -P(1)-> d` and `a -P(10)-> d`; `a -Q(1)-> e`; an unweighted edge `e -Q-> d`.

| # | Changing input | Reader | Prediction | Source |
|---|---|---|---|---|
| DJ1 | defaults vs the Cypher CALL | `SELECT Graph_KG.DijkstraPath('a','d','',9999,10,'out','','g')` vs `USE GRAPH g CALL ivg.shortestPath.weighted('a','d')` | Both choose the cheapest path; with the weights above `a→e→d` (cost 2.0: Q(1) + unweighted 1) beats `a→b→c→d` (3) and `a→d` (10). The SQL answer is the path JSON text (`nodes`, `rels`, `costs`, `length`, `totalCost`); the CALL answers the dict of the same. | USER_GUIDE L631-L640; owner bullets |
| DJ2 | `maxHops` 1 vs 0 | DijkstraPath | 1: only `a→d` (cost 10) fits. 0: no bound, cost 2.0 path. A negative `maxHops` at SQL: no bound (owner: "the native search also treats negative hops as unbounded"). | owner; CHANGELOG "0 or less is no bound" |
| DJ3 | `maxCost` 9999 vs 1.5 | DijkstraPath | 9999: cost 2.0 path. 1.5: no path (empty answer, not an error). | owner bullet 3 |
| DJ4 | `predsJson` `''` vs `'["P"]'` | DijkstraPath | `''`: cost 2.0 via Q. `["P"]`: `a→b→c→d` cost 3.0. `'[]'`: every type (owner: empty list means every type). | docstring R140; owner |
| DJ5 | `direction` `'out'` vs `'in'` (from `d` to `a`) | DijkstraPath | `'out'` from `d`: no path. `'in'` from `d` to `a`: walks against the edges, cost 2.0 (`d←e←a`). | USER_GUIDE L640; CHANGELOG 4.6.0 |
| DJ6 | `direction` `'sideways'` / `weightProp` `'cost'` | SQL DijkstraPath vs Cypher CALL | The CALL raises `ValueError` for both. The SQL entry has no Python layer: predicted to answer no path for `'sideways'` and to ignore `'cost'` (rank by `weight`). | USER_GUIDE L638-L642; CHANGELOG ("it ranked by `weight` whatever was named") |
| DJ7 | `pGraphId` `'g'` vs `''` | DijkstraPath | `'g'`: the path. `''`: the default graph, which has no such edges → no path. | docstring R154 |
| DJ8 | a zero or negative weight on `a -Q-> e` | DijkstraPath | Costs 1 (owner, `weighted_paths.effective`), so the total stays 2.0. | owner bullet 1 |
| DJ9 | caller without SELECT on `rdf_edges` | DijkstraPath | SQLCODE -99 naming `rdf_edges`. | ADMIN_GUIDE L573 |
| DJ10 | `src = dst = 'a'` | DijkstraPath | The empty path at cost 0, before the cost cap. | owner bullet 4 |

## W-BF: `backfill_temporal_rows()`

| # | Changing history | Reader | Prediction | Source |
|---|---|---|---|---|
| BF1 | a temporal triple whose structural row is missing (row deleted by SQL after the write) vs a triple whose row exists | `SELECT Graph_KG.backfill_temporal_rows()`, then `rdf_edges` rows and their mark | Missing: a marked structural row (and endpoint nodes) is written; the function answers the number of rows written (≥ 1). Existing: untouched, not counted. | `temporal.structural.upgrade`; ADMIN_GUIDE L577-L579 |
| BF2 | first vs second run | the same call | Second run answers 0 and writes nothing (idempotent; "never deletes rows"). | `temporal.structural.upgrade` |
| BF3 | the predicate registered temporal-only vs not | the same call | Registered: skipped, no row. Not registered: row written. | ADMIN_GUIDE L1205; CHANGELOG |
| BF4 | caller without INSERT on `nodes` | the same call | SQLCODE -99 `lacks INSERT on Graph_KG.nodes`, nothing written. | ADMIN_GUIDE L577-L579 |
| BF5 | the temporal edge in named graph `g` | the same call | The row is written in `g`, not the default graph. | `temporal.structural` ("same graph") |

## W-RB: `rebuild_edge_indices(schema)`

| # | Changing input | Reader | Prediction | Source |
|---|---|---|---|---|
| RB1 | a populated schema | the call's answer; edge and node reads after it | `BUILD INDEX` on `nodes`, `rdf_labels`, `rdf_props`, `rdf_edges`; answers success (0 or a count); rows and Cypher answers unchanged. | ADMIN_GUIDE L579-L580 |
| RB2 | schema `'Graph_KG'` vs `'Graph_KG; DROP'` | the call | The second is refused before any statement runs (not an SQL identifier). | CHANGELOG R294 |
| RB3 | caller with INSERT/UPDATE/DELETE but no `%BUILD_INDEX` | the call | Raises IRIS's refusal naming the table (not 0). | ADMIN_GUIDE L580; CHANGELOG |
| RB4 | an identifier naming no schema (`NoSuchSchema`) | the call | Raises (no such table), naming the table. | inference from RB3 |

Prior knowledge carried in: the `weighted_paths`/`weighted_cost` models (DijkstraJson/DijkstraCost) are bound through
the engine's handler; nothing binds the SQL entry `DijkstraPath` or `Traversal.DijkstraProc` yet. The erasure page
lists `rebuild_edge_indices` among procedures that "delete outside the Eraser" (inventory), which RB1's "rows unchanged"
contradicts unless the delete is of index entries only.
