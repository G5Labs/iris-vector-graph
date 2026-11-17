# Iteration 57 W1: traversal answers by strategy — outcomes of the frozen predictions

Predictions: [w61-PAIRS.md](../w61-PAIRS.md) (frozen, unedited), workflows B1-B7, S1-S3, N1-N2 (this worker's scope;
D1-D4 and R1-R3 are W2's). Model: [traversal_strategy](../../../../Verus_verification/models/traversal_strategy/NOTES.md).
Receipts (all under `.g5/Verus_verification/results/traversal_strategy/`): prove `20261117T074633Z-prove` PASS 30;
19 controls `20261117T074637Z`..`20261117T074707Z` all EXPECTED_FAIL; binding `20261117T074632Z-binding/receipt.json`
AGREES 73 cases, 19/19 mutations detected, tamper detected. Case names below are that receipt's `observed` keys.

Fixture path actually taken: Arno/NKG library absent (`_detect_arno()` False); `_only_default_graph()` False (other
graphs on the fixture hold edges). Every `execute_bfs` selected `_ObjectScriptBfsAdapter` (`select_real`, all six
graph x direction pairs); the SQL fallback answered only where BFSFast walked no edge. The Arno branch was observed only
as a selection decision with its premises injected on one store instance (`select_injected`); `_run_arno_bfs` was not
run.

Summary: 12 workflows; **11 held, 1 partial (N2), 0 missed**.

| ID | Verdict | Observation | Cases |
|---|---|---|---|
| B1 | held | A: default graph, Arno absent -> ObjectScript; rows `(id, hops, pred)` one per node but the source, least depth, first type in collation, ordered (depth, id), equal to the port's (e.g. `a 1 R, b 1 Q, c 2 R, d 2 Q, e 3 R, x 3 R`). B: the same edges in a named graph, asked with `graph=g` -> the same rows minus `x`, whose edge `c-R->x` only the default graph holds. A named graph never selects Arno even with the library injected (`od1_named_out`). | `os_out_*`, `os_named_out_3`, `sql_named_out_3`, `select_real`, `select_injected` |
| B2 | held | SQL fallback forced (product `_SqlBfsFallbackAdapter` on the instance) answers exactly the ObjectScript rows (set, order, pred) in all 19 pairs: out/in/both x {any, [R]} x hops 1-3, plus the named graph; its raw walk equals the port's visited-checked levels. Proven for every edge set: `theorem_os_rows_eq_sql_rows`. | `os_*` vs `sql_*` (19 pairs) |
| B3 | held | A: cycle `c-R->s` and self-loop `s-R->s`: `s` is never a row (any direction, any hop bound). B: two parallel `ms-R->mt` (Cypher CREATE in a multigraph-mode graph; 2 rows) -> `mt` once. Note: `create_edge` of an existing triple adds no parallel edge even in multigraph mode (1 row), as its docstring says. | `os_*`, `os_cycle_u`, `os_multigraph`; receipt `multigraph_rows_ms_mt` 2, `duplicate_create_edge_rows` 1 |
| B4 | held | `max_results=0` every row; 2 and 3 -> the first 2 / 3 rows of the uncapped answer (`a, b` / `a, b, c`). The adapter is asked for every row (cap 0) and the cut follows the sort; BFSFast's own edge-counting cap would answer only `a, b` for 3 (mutation `cap_passed_to_adapter`). | `os_cap0`, `os_cap2`, `os_cap3` |
| B5 | held | `in` from `d`: `a 1 Q, b 2 Q, s 2 R, c 3 R` (nodes with a path into d); `both`: the union walk, each node once at its least depth. | `os_in_from_d`, `os_in_*`, `os_both_*` |
| B6 | held | 2-cycle `u->v->u`, `*1..2` and `*1..3`: ends `u 2, v 1` (trail walk); `execute_bfs` from `u` lists only `v`. Single edge walked undirected `*1..2`: only `i 1` (no return over the arrival edge); two parallel edges undirected: `ms 2` is an end. | `vl_cycle_u_1_2`, `vl_cycle_u_1_3`, `os_cycle_u`, `vl_single_both_1_2`, `vl_parallel_both_1_2`, `vl_mix_*` |
| B7 | held | After `create_edge(w1,R,w2)`: `execute_bfs` and `khop` reach `w2` at once (ObjectScript walk, no fallback). After `delete_edge`: neither reaches it; `khop` answers `[w1]`; `execute_bfs` is answered by the SQL fallback (w1 has no adjacency entry left), empty. | `b7_after_write`, `b7_khop_after_write`, `b7_after_delete`, `b7_khop_after_delete` |
| S1 | held | Out p1->p3: both readers 2; both p3->p1: 2. Multigraph `ms=>mt->mu` with two parallel `ms->mt`: 2 on both readers. Proven: `theorem_lengths_agree_out_both`, `theorem_parallel_edge_invisible`. | `sp_out_p1_p3`, `sp_both_p3_p1`, `sp_multigraph` |
| S2 | held | A: `execute_shortest_path(p3, p1, 'in')` = 2 (caller reversal). B: `shortest_path_length(p3, p1, 'in')` = -1, and `(p1, p3, 'in')` = 2 where `execute_shortest_path` answers -1. New [bug-str-113](findings.md#bug-str-113). | `sp_in_p3_p1`, `sp_in_p1_p3` |
| S3 | held | A path only graph g holds (`g1->g2->g3`): 2 on both readers with `graph=g`; -1 on both with the default graph. | `sp_named_g1_g3`, `sp_default_g1_g3` |
| N1 | held | Routed graph with three vectors: the two nearest by cosine (`k1, k2`); the same graph with a model key that has no route: no rows, no error. | `knn_routed`, `knn_unrouted` |
| N2 | partial | The premise is not the as-built shape: there is no native k-hop with an SQL fallback. `engine.khop` always calls `engine._khop_fallback`, which is the ObjectScript `BFSFastJson` walk (default graph, out, every type); `IRISGraphStore._khop_fallback` is a stub returning empty lists that `khop` never calls. Held part: khop's nodes but the seed equal `execute_bfs`'s ids on the same graph (proven `theorem_khop_is_default_out_bfs`; observed `khop_s_1`/`khop_s_2` vs `os_out_any_1`/`_2`). Missed part, "named graph scoping preserved": khop has no graph argument and walks only the default graph; a seed held only by a named graph answers `[seed]` (inherited [F-1009](findings.md#F-1009-i57), reproduced). | `khop_s_1`, `khop_s_2`, `khop_named_only_g1` |

Not predicted, found after the freeze: `execute_bfs` with a direction text other than exactly out/in/both is walked by
the SQL fallback, undirected for "OUT"/"sideways" (new [bug-str-114](findings.md#bug-str-114); cases `os_dirtext_*`).
