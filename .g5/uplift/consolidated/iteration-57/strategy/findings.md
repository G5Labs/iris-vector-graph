# Iteration 57 W1 (traversal strategy): findings

Two new entries (bug-str-113, bug-str-114) and one inherited entry reproduced (F-1009). IDs bug-str-115 and bug-str-116
are unused. Not yet copied into [bugs_issues.md](../../../../Verus_verification/bugs_issues.md); the builder integrates.
Checked first: `bugs_issues.md` (no entry names `shortest_path_length` or `execute_bfs`'s direction text; F-1009 matches
the khop seed observation by trigger and consequence) and `docs/KNOWN_ISSUES.md` (no shortest-path direction or BFS
direction entry).

<a id="bug-str-113"></a>
### shortest_path_length(a, b, ..., 'in') answers the outgoing length from a to b, not execute_shortest_path's incoming one

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 57)

Found by: iteration 57 W61 frozen prediction S2 (held: the owner working assumption of
[algorithms.op.paths.direction](../../../../Verus_verification/open_questions.md#HD-1003) names the gap); [traversal_strategy](../../../../Verus_verification/models/traversal_strategy/NOTES.md) `theorem_in_length_differs`, neighbor `theorem_lengths_agree_out_both`; controls `length-in-reversed` (the repair), `esp-no-reversal`, `length-both-as-out`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([binding](../../../../Verus_verification/results/traversal_strategy/20261117T074632Z-binding/receipt.json) `sp_in_p3_p1`, `sp_in_p1_p3`; neighbors `sp_out_p1_p3`, `sp_both_p3_p1`). On the default-graph chain p1-R->p2-R->p3: `execute_shortest_path(p3, p1, [], 5, 'in')` answers length 2 and `shortest_path_length(p3, p1, [], 5, 'in')` answers -1; the reverse pair `(p1, p3, 'in')` answers -1 and **2**. Neighbors: 'out' and 'both' answer the same length on both readers.

Expected: `IRISGraphStore.shortest_path_length`'s docstring: "what execute_shortest_path's paths' length is, without them"; [algorithms.op.paths](../../../../ontology/features/algorithms.g5.md#algorithms.op.paths) "The search can follow the edges, go against them, or do both"; the working assumption "Require IRISGraphStore.shortest_path_length to reverse 'in' as execute_shortest_path does".

Observed: `shortest_path_length` (`iris_sql_store.py:2162-2181`) passes the direction unchanged to `TraversalPaths.ShortestLength` (`TraversalPaths.cls:117-175`), which sets `tBoth = (direction = "both")` and otherwise searches the source's out entries and the target's in entries, i.e. 'in' is walked as 'out'. `execute_shortest_path` (`:2197-2207`) reverses 'in' itself.

Consequence: a direct store caller asking the incoming distance gets the outgoing one: a false "no path" where an incoming path exists, and a positive length where only an outgoing path exists. Cypher is not affected: its length-only route (`query.py:3620-3626`) is taken only for 'out' and 'both'. Severity Low because the only affected entry point is the public store method (no Cypher, SQL or HTTP caller reaches it with 'in'), though the wrong answer is silent and can be positive.

Repair proposal (not implemented): in `shortest_path_length`, for 'in' call `ShortestLength(target, source, ..., 'out', graph)` as `execute_shortest_path` reverses; and make `ShortestLength` refuse any direction outside {out, both} (`CheckDirection`). Preserve: 'out'/'both' lengths unchanged (`theorem_lengths_agree_out_both`). Distinguishing case: `sp_in_p1_p3` answers -1 after the repair (control `length-in-reversed`). Governing statement: [algorithms.op.paths](../../../../ontology/features/algorithms.g5.md#algorithms.op.paths).

<a id="bug-str-114"></a>
### execute_bfs with a direction other than exactly "out", "in" or "both" answers an undirected walk from the edge table ("OUT", "sideways") or a walk of the edge table instead of the adjacency index ("outbound", "inbound")

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 57)

Found by: iteration 57 W1 source read after the W61 freeze (not a frozen prediction; B5 covered the three exact directions); [traversal_strategy](../../../../Verus_verification/models/traversal_strategy/NOTES.md) `theorem_unknown_direction_walks_both`; controls `sql-unknown-dir-as-out`, `types-ignore-case`, `bfsfast-case-insensitive`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([binding](../../../../Verus_verification/results/traversal_strategy/20261117T074632Z-binding/receipt.json) `os_dirtext_OUT`, `os_dirtext_sideways`, `os_dirtext_outbound`, `os_dirtext_inbound`; neighbors `os_out_any_2`, `os_both_any_2`). From `s` on the mix graph, hops 2: `execute_bfs(s, [], 2, "OUT", 0)` answers `a 1 R, b 1 Q, c 1 "", d 2 Q, x 2 R` — the undirected rows (`os_both_any_2`) with an empty type for `c`, reached only against an edge; `"sideways"` answers the undirected rows with no error; `"outbound"` / `"inbound"` answer the out / in rows. Each of the four calls the SQL fallback (`fallback_calls` 1); the three exact directions do not.

Expected: `execute_bfs`'s docstring: the rows "walked in `direction`"; the path routines' policy for directions ([algorithms.op.paths.direction](../../../../Verus_verification/open_questions.md#HD-1003): refuse a direction outside {out, in, both}, as `DijkstraJson`'s `CheckDirection` does). `_select_bfs_strategy` already reads `"outbound"` and case-insensitively.

Observed: `BFSFast` (`TraversalBFS.cls:107-208`) compares `direction = "out"` / `"in"` / `"both"` exactly, so any other text walks no edge and `BFSFastJsonSorted` answers `SORTED:0`; `_run_objectscript_bfs` (`iris_sql_store.py:2059-2065`) then calls `_sql_bfs_fallback`, whose else branch (`:2132-2149`) reads both columns for every text but out/outbound/in/inbound; `_bfs_rows` (`:1897-1898`) lowercases the text for `ReachTypes`, so "OUT"'s types are read as outgoing while its depths are undirected.

Consequence: a caller (or a protocol client passing a user-supplied direction) gets plausible rows for a direction the store does not know: an undirected neighbourhood for "OUT", with blank types; and "outbound"/"inbound" are answered from `rdf_edges` rather than `^KG`, so they can differ from "out"/"in" wherever the two disagree (an undeclared index, W2's domain). Low: the in-tree Cypher caller passes only out/in/both.

Repair proposal (not implemented): normalise once at `execute_bfs` (lowercase; outbound -> out, inbound -> in) and refuse anything else with `ValueError`, before choosing a strategy. Preserve: the three exact directions' rows (`theorem_os_rows_eq_sql_rows`). Distinguishing case: `os_dirtext_OUT` answers the `os_out_any_2` rows (control `sql-unknown-dir-as-out` shows the model decision). Governing statement: `execute_bfs` docstring; [query.paths.varlength](../../../../ontology/features/cypher.g5.md#query.paths.varlength).

<a id="F-1009-i57"></a>
### Inherited (strengthened): F-1009 khop answers a start node that exists only in a named graph

Severity: Low (unchanged) · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 57) — reproduction only.

Matches [F-1009](../../../../Verus_verification/bugs_issues.md) by trigger (khop of a seed held only by a named graph) and observable (`{'nodes': [seed], 'edges': []}`).

Reproduced by: **E2E reproduced** (fresh; the register entry was "outside active reproduction scope") on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([binding](../../../../Verus_verification/results/traversal_strategy/20261117T074632Z-binding/receipt.json) `khop_named_only_g1`): `g1` has a node and the edge `g1-R->g2` only in graph `i57ag<tag>n`; `khop(g1, hops=2)` answers nodes `[g1]` and no edges. Strengthening: `theorem_khop_ignores_named_graphs` proves khop answers the default graph's walk whatever named graphs hold (it has no graph argument), and `_khop_seed_exists` (`algorithms.py:619-626`) reads `nodes` in every graph, so the seed rule and the walk read different scopes.
