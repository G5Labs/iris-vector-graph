<!-- markdownlint-disable MD013 -->

# adjacency_maint — Verus model notes (iteration 57, worker W2)

Product baseline `3eaa79cf` (read-only; nothing outside `.g5/` changed). Frozen predictions: [w61-PAIRS.md](../../../uplift/consolidated/iteration-57/w61-PAIRS.md) D1-D4, R1-R3; observations in [OBSERVED.md](../../../uplift/consolidated/iteration-57/adjacency/OBSERVED.md).

- Root `adjacency_maint.rs`; `model.json` has 14 controls. Toolchain: Verus `0.2026.10.04.426d8b0`, bundled vstd only.
- Run (from the repository root): `python3 .g5/Verus_verification/run_verus.py prove|controls .g5/Verus_verification/models/adjacency_maint`; binding: `(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/adjacency_maint/binding.py)`.
- **Results.** Prove PASS, 35 verified, 0 errors (`results/adjacency_maint/*-prove/receipt.json`, 20261117T074807Z). Controls: 14 of 14 EXPECTED_FAIL (`results/adjacency_maint/20261117T074811Z` … `074902Z-control-*`). Binding AGREES, 24 cases, 12 of 12 mutations detected, tamper detected (`results/adjacency_maint/20261117T075252Z-binding/receipt.json`; earlier AGREES receipts 074655Z (reweight mutation masked by the first sync, fixed by reading the entry right after `set_edge_weight`), 074724Z, 074910Z, 074954Z kept; 075252Z adds the `cypher_delete_r_rows` case).
- **Kept failing receipts.** `20261117T074356Z-binding` DISAGREES: a binding defect (the observed `^NKG` names were listed once per graph, the prediction once per name); the observation side was fixed to a set. `20261117T074659Z/074707Z-control-create-ignores-mode/canon-leaf-not-lowest` FAIL_ELSEWHERE: the expected item lists named the first failing lemmas only; the failure lands in `lemma_rebuild_prefix` / `lemma_rebuild` too, and the lists now name them. Earlier unrecorded scratch runs exceeded rlimit before `empty_m` / `single` were made opaque.

## What is derived, not supplied

The adjacency state is never an input. `rows_at(h, t)` and `adj_at(mm, h, t)` fold a history `h` of row-level operations for every triple `t = (graph key, s, p, o)`; `mm` is the set of graphs in multigraph mode (fixed over the history).

| Op | Product path (pin) |
|---|---|
| `Create{t, k, w}` | `create_edge`, `store.write_edges` (default graph), Cypher `CREATE`: one INSERT; the declared index calls `Adjacency.RowPut` (`Adjacency.cls:477-488`) → `Put` (80-109) or `PutKeyed` (210-269) by `^IVG.GraphMode` |
| `DelRow{t, k}` | one row DELETE → `RowRemove` (491-501) → `Remove` (147-167) or `RemoveKeyed` (275-321). Cypher `DELETE r` deletes by `edge_id` (`translator.py:10714-10721`); `engine.delete_edge` deletes every row of the triple in one graph (`nodes_edges.py:1382-1446`; `all_graphs` in every graph) — one `DelRow` per row |
| `Update{t, k, w}` | `set_edge_weight` (default graph; `nodes_edges.py:1306-1380`): one UPDATE per row → `RowUpdate` (505-534) → keyed child + `SetLeafFromLowest`, else `Reweight` (328-342) |
| `EraseTriple{t}` | `store.delete_edges` → `Eraser.EraseEdges` (`Eraser.cls:395-465`): every row of the triple (`EraseEdgeRow`, 641-683), then `Adjacency.Remove` |
| `EraseNodes{g, ids}` | `engine.delete_node`, `store.delete_nodes` (`EraseNodeIds`), `delete_nodes_by_prefix` (`EraseNodes`): every incident row in `g`, `Adjacency.RemoveNode`, the ids' label rows (`EraseIdSet`, 467-640) |
| `Sync` | `sync()` = `BuildKG` (`TraversalBuild.cls:30-165`): with the declared index, `PurgeIndex` + `%BuildIndices`, i.e. `RowPut` for every row with every row visible to `OtherEdgeKeys`; then `BuildNKG`, `Build2HopStats`, `Build2HopExactStats` |

`canon(multi, rows)` is the rebuild's answer for one triple: none without rows; a multigraph triple with two or more rows has the leaf of its lowest ekey and every row as a keyed child (`#` = their count); otherwise a bare leaf with the row's weight.

## Proved (general, every admissible history)

- `theorem_incremental_equals_rebuild` (b): for every admissible history and every triple, `adj_at == canon(rows_at)`. Per-op lemmas `lemma_create`, `lemma_delrow`, `lemma_update`; the rebuild itself, in **any** visiting order, is `canon` (`lemma_rebuild`, `lemma_rebuild_prefix`, `lemma_second` — PutKeyed's one-to-two transition, `lemma_third`). No witness of divergence exists in the domain.
- `theorem_sync_changes_nothing` (R1): a `sync()` leaves every entry as it was.
- `theorem_other_graph_untouched` (D1, D2): a `DelRow`, `Update`, `EraseTriple` or `EraseNodes` in graph g leaves every triple of another graph (same s, p, o included) as it was.
- `theorem_erase_nodes_takes_incident` (D1): every g triple with an erased end loses its rows and entry.
- `theorem_delete_one_parallel_keeps_other` (D3): Cypher `DELETE r` of one of two parallel edges leaves a bare leaf with the survivor's weight; the degree contribution goes 2 → 1. `theorem_plain_delete_takes_triple`: a plain graph's row delete takes the triple.
- `theorem_nkg_held_elsewhere`, `theorem_mark_graph_gone` (a): `Remove` drops the merged `^NKG` edge only when the entry was there, `^NKG` is built and no other graph holds the triple; `MarkGraphGone` marks `^NKG` stale only for a named graph whose last out entry went with an interned end.
- `theorem_label_delete_scoped` (D4).
- `theorem_two_hop`, `lemma_uni_le_sum`, `theorem_write_makes_stale` (R2): the walk/exact count is at most the precomputed sum; exact = walk; fast ≥ walk; a stale count is never read (both answer the walk); any write makes the stats stale.
- `witness_fast_overcounts` (R2, [bug-str-117](../../../uplift/consolidated/iteration-57/adjacency/findings.md#bug-str-117)): diamond fast 2 / exact 1; back edge fast 1 / exact 0.

## Domain and exclusions

- Admissible: an INSERT takes a fresh ekey (unique key `(s, p, o_id, graph_id, ekey)`); a graph not in multigraph mode holds at most one row per triple (create_edge's guard, `write_edges`' duplicate skip); `%BuildIndices` visits each row once (premise `build_order`, uninterpreted, `enumerates`). Multigraph mode does not change during the history (`set_multigraph(g, False)` is refused while parallel edges exist).
- Integer weights. The Eraser ops are modeled at their end state (every row of each touched triple gone, then `Remove`), not row by row.
- Declared index only (`IndexKind = functional`, observed). The undeclared path (`FillEdge` / `FillTriple`, the `EdgeScan` writers, `structure.adjacency.undeclared`) is not modeled; neither are concurrency, the writer lock, `^IVG.AdjNoLock`, the degree cache's generations (`gen`, `degc`; degree is modeled as `Adj.Count`), temporal shadows (`PutShadow`, `RetractTemporal*`), `BulkLoader`, the ledger's `OpCreateRel`, and parallel `%BuildIndices` jobs.
- Degree: `contrib` is one entry's contribution (a `#` counts its edges, a bare leaf 1); the sum over targets is the binding's port, not a theorem.
- `^NKG`: only the per-triple remove decision and the stale mark are modeled; the rewrite (`RewriteNKG`, sweeps, `RetireNode`, `PutNodeBack`, sketches) is observed by names only (R3). Arno/NKG accelerator absent on the fixture: its calls are inside `Try … Catch {}` (`Build2HopExactStats`, `BuildNKG`), so the ObjectScript paths ran; `^NKG` **is** written by `sync()` (observed `nkg_built_after_sync` true).
- Two-hop: default graph, with a predicate (the only case with stored counts). The model abstracts the middle nodes' target sets; the binding derives them from the port.

## Binding

`binding.py` writes one history through the product API (engine, store, Cypher) with prefix `i57b_<tag>_` and graphs `i57bg<tag>{a,b,m}` in USER (two namespace-wide `sync()` calls; no other prefix's data erased), records it as model ops, and compares a Python port of the spec functions (applied to the history) with the observed `^KG("out")` entries (leaf, keyed children, `#`, the `in` mirror), `^KG("label")`, `Graph.KG.Adj.Count`, `execute_bfs` reach, `^NKG(-1, …)` edges by name, and `khop2_count_fast/exact`. Multigraph ekeys (read off the rows right after each Cypher CREATE) and the ekey a `LIMIT 1` `DELETE r` removed are history identity read from the rows. Mutations mirror controls (table in BINDINGS.md); the tamper adds 1 to the observed survivor leaf after `DELETE r`.

## Iteration 59: the ^NKG stale flag observed (independent review 56-58 item B2)

`MarkGraphGone` (Adjacency.cls 174-181) was proved and controlled but not observed. The binding now creates a named
graph GZ with one edge before the first `sync()`, then reads `^NKG("$meta","stale")`: after `sync()` (cleared,
TraversalBuild.cls 336: false), after the GA delete that leaves two GA edges (false), after a default-graph delete
(false: `Quit:pGraph=0`; USER's default graph never empties, so the default-graph control is detected only by the
proof), and after GZ's last edge is erased with both ends interned (true). New controls `mark-ignores-left` and
`mark-never` (both EXPECTED_FAIL in `theorem_mark_graph_gone`); port mutations `mark_ignores_left` (detected by the GA
and default reads) and `mark_never` (detected by the GZ read). Whether an end is interned is read from `^NKG("$NI")`
(sync's decision, an input here). Receipt: [AGREES 28](../../results/adjacency_maint/20261117T090257Z-binding/receipt.json)
(was 24); the first run of the extended harness ([DISAGREES](../../results/adjacency_maint/20261117T090243Z-binding/receipt.json))
was a port bug (a `None` from `marks_stale` for the GA read), fixed by returning a boolean; its observations were the
same. Controls: 16, all EXPECTED_FAIL. B1: `OtherEdgeKeys` is relabelled `cites` (its answer is the model input
`others`).

## Latest receipts (checked in iteration 64)

The latest receipt of each kind, as `tools/census.py` resolves it: prove [20261118T013554Z-prove](../../results/adjacency_maint/20261118T013554Z-prove/receipt.json), binding [20261117T090257Z-binding](../../results/adjacency_maint/20261117T090257Z-binding/receipt.json), and the latest receipt for each of the 16 named controls in [results/adjacency_maint/](../../results/adjacency_maint/). A receipt this file calls "final" or "latest" above is the one current when that paragraph was written; later reruns supersede it.
