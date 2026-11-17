<!-- markdownlint-disable MD013 -->

# Iteration 57, W61 (worker W2): delete paths and rebuild vs incremental — observed

Frozen predictions: [w61-PAIRS.md](../w61-PAIRS.md) §2 (D1-D4) and §3 (R1-R3). Model: [adjacency_maint](../../../../Verus_verification/models/adjacency_maint/NOTES.md) (prove PASS 35 verified, `results/adjacency_maint/20261117T074807Z-prove`; 14/14 controls EXPECTED_FAIL, `20261117T074811Z`…`074902Z-control-*`). Binding: [receipt](../../../../Verus_verification/results/adjacency_maint/20261117T075252Z-binding/receipt.json) AGREES, 24 cases, 12/12 mutations detected, tamper detected. Fixture `ivg-cont-20261117-iris`, USER, prefix `i57b_075244_`, graphs `i57bg075244{a,b,m}`; adjacency index kind `functional` (declared); Arno/NKG accelerator absent (its calls in `BuildNKG` / `Build2HopExactStats` are inside `Try … Catch {}`; `NKGAccel.Available` answered nothing).

Case names are the receipt's `observed` keys.

| ID | Verdict | Observation | Cases |
|---|---|---|---|
| D1 A | held | `delete_nodes_by_prefix(P+"n_", graph=GA)`: every GA triple with an end in {n_1, n_2} lost its `^KG` entry (`keep→n_1` and `n_2→keep` gone from GA); BFS from `keep` in GA reaches nothing | `entries_before_sync`, `bfs_ga_keep` |
| D1 B | held | the same IDs and triples in GB untouched: entries `n_1→n_2`, `n_2→keep`, `keep→n_1` present; BFS from `keep` in GB reaches n_1, n_2 | `entries_before_sync`, `bfs_gb_keep`, `bfs_gb_n1`, `counts["GB|n_1"]=1` |
| D2 A | held | `delete_edge(n_1, R, n_2, graph=GA)`: GA's entry gone; BFS from n_1 in GA reaches nothing | `bfs_ga_n1`, `entries_before_sync` |
| D2 B | held | GB's entry and BFS answer unchanged (keep, n_2). Beyond the prediction: the merged `^NKG` edge stays (another graph holds the triple: `HeldElsewhere`), while deleting `x→a`, held by no other graph, removes its `^NKG` edge | `bfs_gb_n1`, `nkg_n1n2_after_ga`=true, `nkg_xa_after`=false |
| D3 A | held | engine `delete_edge(b,R,c)` and store `delete_edges([(d,R,x)])` each removed the row and the out/in entries; Adj.Count of `a` on R = 1 after `delete_node(c)` erased `a→c` | `entries_before_sync`, `counts["None|a"]` |
| D3 B | held | multigraph GM: two Cypher CREATEs → leaf 7 (lowest ekey 0's weight), children {0:7, 1:3}, `#`=2, Count(ms,R)=3 (2 + `ms→mu`); `DELETE r … LIMIT 1` removed ekey 0 → bare leaf 3 (the survivor), no children, no `#`, Count 2 (dropped by one), BFS still reaches `mt` | `multi_two`, `count_ms_two`, `cypher_delete_r_rows`=1, `multi_after_delete_r`, `count_ms_after_delete_r`, `bfs_gm_ms` |
| D4 A | held | the erased nodes' labels gone from `^KG("label", GA, "L57", …)` (n_1, n_2) | `labels_before_sync` |
| D4 B | held | `keep` in GA keeps `L57`; GB's n_1, n_2, keep keep it; default-graph `a`, `b`, `x` (store `write_nodes`) keep it after `delete_node(c)` | `labels_before_sync`, `labels_after_sync` |
| R1 A | held | after interleaved creates, Cypher CREATE/DELETE r, `set_edge_weight`, engine/store/prefix/node deletes, the 11 entries of this run (leaf, children, `#`, in mirror) are identical before and after `sync()`, and equal to the model's rebuild (`canon`) of the written rows; labels identical; proved for every admissible history (`theorem_incremental_equals_rebuild`, `theorem_sync_changes_nothing`) | `entries_before_sync`, `entries_after_sync`, `labels_*` |
| R1 B | held | `set_edge_weight(a,R,b,5)`: the out leaf is 5 right after the write (RowUpdate → Reweight) and after both syncs | `reweight_before_sync`, `entries_after_sync` |
| R2 A | partial | right after `sync()` (stamps current): `khop2_count_fast(s2, Q)` = 3 = the precomputed sum of the middle nodes' out-degrees on Q (m1: y, s2; m2: y), `khop2_count_exact` = 1 = distinct nodes first reached at hop 2 (y). Held as predicted; but 3 counts the source (back edge `m1→s2`) and `y` twice, against the method's own documentation ("how many nodes are first reached at the second outbound hop") — new finding [bug-str-117](findings.md#bug-str-117) | `two_hop_after_sync`, `notes.two_hop_stamps_fresh` |
| R2 B | held | after a later edge write (`z1→z2`, unrelated), both answer the walked count 1 (stale stamps not read) | `two_hop_after_write` |
| R3 A | held | `sync()` writes `^NKG` on the fixture (ObjectScript `RewriteNKG`, no Arno): `nkg_built_after_sync` true; after the deletes and the second `sync()`, `^NKG(-1, …)` by names equals the merged (graph-blind) set of this run's live `^KG` triples (11 names; GA/GB shared triples once) | `nkg_built_after_sync`, `nkg_by_names` |

Summary: of 13 halves, 12 held, 1 partial (R2 A: the value matched the frozen prediction, but it is a documented-contract departure), 0 missed. R3 has one neighbour only (as frozen).

Not observed: the `^NKG("$meta","stale")` mark (`MarkGraphGone`) — namespace-wide flag shared with other workers, proof-only (`theorem_mark_graph_gone`); the undeclared-index path; concurrency; the multigraph `set_edge_weight` path (default graph is not in multigraph mode here).
