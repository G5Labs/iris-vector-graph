# Traversal answers by strategy, derived from one adjacency state

Product `3eaa79cf`, unchanged. Iteration 57, worker W1. Predictions frozen before the deciding source was read:
[w61-PAIRS.md](../../../uplift/consolidated/iteration-57/w61-PAIRS.md) (B1-B7, S1-S3, N1-N2); outcomes in
[strategy/OBSERVED.md](../../../uplift/consolidated/iteration-57/strategy/OBSERVED.md).
Owners: [algorithms.op.khop](../../../ontology/features/algorithms.g5.md#algorithms.op.khop),
[algorithms.op.paths](../../../ontology/features/algorithms.g5.md#algorithms.op.paths),
[query.paths.varlength](../../../ontology/features/cypher.g5.md#query.paths.varlength),
[structure.adjacency](../../../ontology/architecture/adjacency-and-derived-data.g5.md#structure.adjacency),
[search.knn](../../../ontology/features/search.g5.md#search.knn).

## State and derivation

The state is a finite edge sequence `es: Seq<Edge>`, each edge `(g, s, p, o, k)`: graph (0 the default graph), source,
type, target, edge key (a multigraph's parallel edges differ only in `k`). A question `Q` is (graph, type filter,
direction). `edge_steps` / `step` are the one-edge relation; every answer below is a function of `es` and the question.
No answer is an input.

| Spec | Product decision transcribed |
|---|---|
| `os_front`, `os_seen`, `os_walked`, `os_row`, `excl_source` | `TraversalBFS.BFSFast` with `pAnyType = 1` (frontier = new nodes; one row per edge walked out of the frontier, seen or not), folded by `IRISGraphStore._bfs_rows` (each node but the source once, at its least depth) |
| `sql_new`, `sql_visited`, `sql_row` | `_sql_bfs_fallback` (`if nbr not in visited`, graph predicate on every hop) |
| `adapter_cap`, `cut` | `execute_bfs`: `strategy.run(..., 0, graph)`, then `rows[:max_results] if max_results else rows` after the (depth, id) sort |
| `select`, `only_default_graph`, `falls_back`, `answered_by` | `_select_bfs_strategy`, `_only_default_graph`, `_run_objectscript_bfs` (raise or `SORTED:0` -> SQL walk) |
| `DirText`, `os_walks_text`, `sql_dir_text`, `type_dir_text` | the direction text: BFSFast compares `"out"/"in"/"both"` exactly; the SQL walk's else branch reads both; `_bfs_rows` lowercases for `ReachTypes` |
| `chain`, `trail`, `trail_len`, `vl_end` | `VarLength.Ends` (`EndsInto` / `EndsTwo` / `EndsByDistance`): ends of trails (no edge identity `(g,s,p,o,k)` twice), least length in `minh..maxh` |
| `has_len`, `esp_len`, `spl_dir`, `spl_len` | `execute_shortest_path` ('in' = the outgoing path from the target, reversed) and `shortest_path_length` -> `TraversalPaths.ShortestLength` (`tBoth = direction = "both"`, anything else walks out) |
| `khop_q`, `khop_node` | `engine.khop` -> `_khop_fallback`: `BFSFastJson(seed, "", hops, "", "out")`, default graph, no graph argument; seed listed when it has an out-edge or `_khop_seed_exists` (any graph) |
| `knn_rows` | `execute_knn_vec`: `knn_route(graph, model)` None -> no rows |

## Theorems (30 verified, no `assume`, `admit` or `external_body`)

| Theorem | Claim | Domain | Disposition |
|---|---|---|---|
| `lemma_front_eq_new` | BFSFast's frontier and seen set equal the SQL walk's new and visited sets at every hop | all `es`, `q`, `src`, `h` | as-built |
| `theorem_os_rows_eq_sql_rows` | B2: ObjectScript rows (after `_bfs_rows`) == SQL fallback rows | all `es`, `q`, `src`, `hops`, `v`, `d` | as-built agrees with owner |
| `theorem_bfs_never_lists_source` | B3: the source is never a row | all | as-built |
| `theorem_one_row_per_node` | B3: one depth per node | all | as-built |
| `theorem_other_graph_edges_invisible` | B1/S3: other graphs' edges change no walk | all `es`, any `extra` outside `q.g` | as-built |
| `theorem_parallel_edge_invisible` | B3/S1: a parallel edge changes no walk | all | as-built |
| `theorem_adapter_walks_uncapped`, `theorem_cap_keeps_nearest_prefix` | B4: 0 = all; k = first k of the ordered answer | any ordered rows | as-built |
| `theorem_arno_only_default_outbound`, `theorem_arno_reachable` | B1: named graph, in/both, no library, or other graphs with edges -> never Arno; reachable otherwise | all `Env` | as-built (Arno conditional) |
| `theorem_fixture_path` | Arno absent: a walk that records an edge is ObjectScript's; none -> SQL fallback | all | as-built, observed |
| `theorem_unknown_direction_walks_both` | "OUT"/"sideways" walk nothing in BFSFast and are walked undirected by the SQL fallback; "OUT"'s types read as outgoing | the 7 texts | [bug-str-114](../../../uplift/consolidated/iteration-57/strategy/findings.md#bug-str-114) |
| `theorem_vl_ends_list_source_bfs_does_not` | B6: a 2-cycle makes the source an end; BFS never lists it | witness | as-built |
| `theorem_vl_both_no_backtrack` | B6: one undirected edge has no 2-trail | witness | as-built |
| `theorem_vl_parallel_edges_return` | two parallel edges walked undirected return to the source at 2 | witness | as-built |
| `theorem_lengths_agree_out_both` | S1: out/both, both readers answer the same length | all | as-built |
| `theorem_in_length_differs` | S2: on b->a, `execute_shortest_path(a,b,'in')` = 1, `shortest_path_length(a,b,'in')` none within any bound | witness | [bug-str-113](../../../uplift/consolidated/iteration-57/strategy/findings.md#bug-str-113) |
| `theorem_khop_is_default_out_bfs` | N2/B7: khop's nodes but the seed == execute_bfs ids (default graph, out, every type) | all | as-built |
| `theorem_khop_ignores_named_graphs` | N2: khop answers the default graph whatever named graphs hold | all | as-built (no graph argument) |
| `theorem_knn_no_route_no_rows` | N1 | all | as-built |

Plus the termination obligations of the recursive specs and the helper lemmas (`lemma_visited_mono`,
`lemma_visited_has_new`, `lemma_new_visited`, `lemma_walked_visited`, `lemma_new_ext`, `lemma_nothing_out_of_source`).

## Domain, premises and exclusions

- Node ids, types, graphs and keys are integers in the model; the binding maps them to strings. Order of rows is
  (depth, id) by Python string order; the binding's ids share one prefix and are lower-case ASCII, where IRIS collation
  and Python order agree (premise, not proven).
- The model treats BFSFast's type set (`pAnyType = 1`, which `_run_objectscript_bfs` passes): the per-hop sequence and
  the next-hop lookahead (walk_reader's domain) and `dstLabel` are excluded.
- `^KG` equals the edge rows (declared index, `structure.adjacency.declared`). Where `^KG` and `rdf_edges` differ, the
  ObjectScript walk reads `^KG` and the SQL fallback reads `rdf_edges` (it answers only when BFSFast walked nothing);
  adjacency drift is worker W2's model (adjacency_maint), not this one.
- The pred column is `ReachTypes`' answer for the depth map; both strategies hand it the same map, so equality of the
  depth maps (the theorem) carries the column. `ReachTypes` itself is ported in the binding, not proven.
- `vl_end` is the openCypher trail definition; `EndsByDistance`'s optimisations (least distance plus the source's cycle,
  parallel-edge count at the source) are checked against it by the binding only (6 cases), not proven equal.
- Shortest paths: lengths only; `ShortestLength`'s bidirectional search is modeled by its answer (least forward
  distance), argued in the source comment, not proven. `find_all` and path contents are excluded.
- Arno: the library is absent on the fixture (`_detect_arno()` False). The Arno branch of `select` is proven reachable
  and is observed only through `_select_bfs_strategy` with `_detect_arno`, `_arno_capabilities`, `_only_default_graph`
  injected on one store instance; `_run_arno_bfs` and `^NKG` are not run.
- `khop`'s seed rule uses `_khop_seed_exists`, which reads `nodes` in every graph (inherited F-1009).
- Writes: `create_edge` adds one edge per (graph, s, p, o) and answers False for a duplicate even in multigraph mode
  (observed: one row); parallel edges are written with Cypher `CREATE` in a multigraph-mode graph (observed: 2 rows).

## Controls (19, each EXPECTED_FAIL in its named functions)

`bfs-lists-source`, `bfs-every-depth`, `sql-revisits`, `graph-unscoped`, `cap-zero-cuts-all`, `cap-passed-to-adapter`,
`arno-named-graph`, `arno-any-direction`, `arno-ignores-other-graphs`, `no-fallback-on-empty`, `length-in-reversed`
(the repair), `trail-repeats-edges`, `khop-walks-both`, `knn-unrouted-legacy`, `sql-unknown-dir-as-out`,
`types-ignore-case`, `bfsfast-case-insensitive`, `esp-no-reversal`, `length-both-as-out`. See [model.json](model.json).
Three control runs are kept: 14 controls at `20261117T0738*` (before the direction-text decision), 15 at
`20261117T0743*`, and the final 19 at `20261117T074637Z`-`20261117T074707Z` (the last four added by the
binding-integrity audit so that every crosswalk member labelled models/proves/witnesses has a control). Prove receipts:
`20261117T073812Z` (29 verified, before the direction-text theorem), `20261117T074317Z` and `20261117T074633Z` (30).

## Binding

[binding.py](binding.py), see [BINDINGS.md](BINDINGS.md). Final receipt
`results/traversal_strategy/20261117T074632Z-binding/receipt.json`: 73 cases, AGREES; 19 of 19 mutations detected;
tamper detected. Earlier receipts kept: `20261117T074043Z` (DISAGREES: the binding's own history treated a duplicate
`create_edge` as a parallel edge and predicted every case from the final history; both binding errors, fixed),
`20261117T074154Z` and `20261117T074310Z` (AGREES, 69 and 73 cases, fewer mutations).

Observed fixture path: `_detect_arno()` False and `_only_default_graph()` False (other graphs hold edges), so every
`execute_bfs` took `_ObjectScriptBfsAdapter`; the SQL walk answered exactly when BFSFast walked nothing (a node with no
edge, a deleted edge's source, and every direction text other than out/in/both).
