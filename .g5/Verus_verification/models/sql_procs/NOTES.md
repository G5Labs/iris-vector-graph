# sql_procs — notes (iteration 53, Part B)

Scope: the graph SQL procedures of `Graph.KG.SqlProcs` left unbound after iteration 47 (its HANDOFF "Part C"):
`MatchEdges`, `MatchEdgesAllGraphs`, `DijkstraPath`, `backfill_temporal_rows`, `rebuild_edge_indices`. Predictions were
frozen first ([sqlprocs-PAIRS.md](../../../uplift/consolidated/iteration-53/sqlprocs-PAIRS.md), commit `ff7d3528`); the
raw probe is [sqlprocs-observed-20261117T050743Z.json](../../../uplift/consolidated/iteration-53/sqlprocs/sqlprocs-observed-20261117T050743Z.json)
(namespace `I53P`).

## What the model owns and what it delegates

| Entry | Model terms | Decision from inputs |
|---|---|---|
| `MatchEdges(src, pred, shard, graph)` | `scan_hit`, `match_edges`, `graph_key`, `scan_w` | graph '' / NULL / 0 / omitted → key 0 (the default graph only); empty source → every source; empty predicate → every predicate; `shard` never read; `w` is the leaf, 1.0 when none |
| `MatchEdgesAllGraphs(src, pred, shard)` | `all_hit`, `match_all` | every graph key, each edge with its graph (a triple in two graphs answers twice) |
| privilege | `gate` | `RequireSelect(rdf_edges)` for the three readers, `RequireWrite(nodes, rdf_edges, "i")` for the backfill; `%All` passes |
| the Cypher hop, `IVG_EDGESCAN=1` | `plan`, `rel_weight`, `hop_targets` | no `USE GRAPH` / `USE GRAPH ''` → the scan; a named graph → rows; a scan alias's relationship property is `NULL` |
| `DijkstraPath` | `dijkstra_json`, `dijkstra_path`, `sql_end` | weight property and direction checked in ObjectScript (raise); "" endpoint → no path; equal endpoints → the empty path; SQL '' arrives as `$Char(0)`; the search itself is **delegated** to the `weighted_paths` model (DijkstraJson) |
| `backfill_temporal_rows()` | `Bf`, `structural`, `backfill_rows`, `backfill_count`, `rows_written` | a structural temporal triple with no row gets a marked row; an existing row (marked or explicit) is left alone; temporal-only predicates are skipped; the answer is the number of triples walked |
| `rebuild_edge_indices(schema)` | `rebuild` | identifier check first; `BUILD INDEX` on four tables; refusal or a missing table raises naming the table; success answers 4 |

## Theorems (16 verified, vstd only; no `assume`, `admit` or `external_body`)

- Scan: `theorem_empty_predicate_every_predicate` (general over every adjacency list, source, shard and graph),
  `theorem_shard_ignored`, `theorem_graph_scoped_vs_all`, `theorem_shared_triple_once_per_graph` (witness of the
  all-graphs shape for any two arcs).
- Privilege: `theorem_entries_gated`.
- IVG_EDGESCAN: `theorem_edgescan_reads_null_property` (**bug-cyp-133**), neighbor `theorem_unweighted_and_named_agree`.
- DijkstraPath: `theorem_sql_entry_refuses_bad_arguments`, `theorem_sql_empty_endpoints_zero_path` (**bug-str-112**),
  neighbors `theorem_dijkstra_endpoint_neighbors`.
- Backfill: `theorem_backfill_writes_missing_only`, `theorem_backfill_idempotent_same_count`,
  `theorem_backfill_count_overstates` (**bug-tmp-107**), neighbor `theorem_backfill_count_exact_when_all_missing`.
- Rebuild: `theorem_rebuild_answers_four_or_raises`.

Controls (12, all EXPECTED_FAIL in their named functions, first run): `shard-partitions`, `default-reads-every-graph`,
`empty-predicate-matches-none`, `all-graphs-default-only`, `no-select-check`, `scan-exposes-weight`,
`sql-entry-unchecked`, `nul-read-as-empty`, `count-written-rows`, `optout-backfilled`, `backfill-marks-existing`,
`rebuild-refusal-answers-zero`. Receipts: [prove](../../results/sql_procs/20261117T051149Z-prove/receipt.json),
`results/sql_procs/20261117T0511*-control-*`.

## Binding

`binding.py` drops and re-creates namespace `I53Q` (from `%SYS`, container `ivg-cont-20261117-iris` only), writes one
history through the public API and calls each SQL entry as `_SYSTEM` and as three users `i53q_*` (deleted afterwards).
Expected answers come from a Python port of these spec functions applied to the written history; the search's
expected path is a port of the documented rule (cheapest path within `maxCost` and a positive `maxHops`, weights
`<= 0` or none as 1, direction, predicates, graph), never the product's answer. **AGREES 224 cases**, all 12
mutations and the tampered observation (`hop_nograph_1`) detected
([receipt](../../results/sql_procs/20261117T051429Z-binding/receipt.json)).

## Premises and limits

- P-INDEX: the adjacency index is declared, so `^KG` and the rows agree (the scan and the rows plan read the same edges).
- P-SEEN: fewer distinct temporal triples per graph than the backfill's seen limit (100,000); past it a triple is walked,
  and counted, again.
- The search (cost order, hop states, ties) is `weighted_paths`' claim; this model binds the SQL entry in front of it.
  The binding's search port has no ties in its fixture.
- Multigraph: `create_edge` of a parallel edge answered False on a multigraph-enabled graph (the keyed writers were not
  driven), so the scan's one-leaf answer for parallel edges is not observed.
- The rebuild's effect on `^KG` (BUILD INDEX recreates the functional adjacency index from rows) is observed only as
  "rows and scan unchanged"; a `^KG` entry without a row was not constructed.
- `shard` has no documented meaning; the owner states it is not read.
