# Iteration 57 W2 (adjacency maintenance): findings

Saved by the builder from W2's final report (the worker's own Write was refused by the harness). One new entry
(bug-str-117); one inherited entry strengthened (bug-plt-116). IDs bug-str-118 .. -120 unused. Integrated into
[bugs_issues.md](../../../../Verus_verification/bugs_issues.md#bug-str-117) with the register's relative links.

<a id="bug-str-117"></a>
### khop2_count_fast answers the sum of the middle nodes' out-degrees right after sync(), counting the source and repeated targets, and the walked count after any unrelated write

Severity: Medium · Decision: Open

Severity reasoning: read-only, no data changed; but the documented meaning ("How many nodes are first reached at the
second outbound hop from `node_id`", API_REFERENCE; docstring: "neither `node_id` nor a direct neighbour is counted")
holds only while the stats are stale, and the same call on the same data answers differently depending on whether any
write anywhere in the namespace happened since the last sync(); a caller cannot tell which answer it got.

Run: Uplift 2026-11-17 (continuation, iteration 57)

Found by: iteration 57 W61 R2 (frozen prediction expected the upper bound from test_460_r284; the departure is against
the method's own documentation); `adjacency_maint` `witness_fast_overcounts` (diamond 2 vs 1; back edge 1 vs 0),
`theorem_two_hop`; controls `fresh-ignores-stamp`, `walk-counts-source-and-first-hop`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin
(binding `results/adjacency_maint/20261117T075252Z-binding` and the builder's re-run `20261117T075646Z-binding`,
cases `two_hop_after_sync`, `two_hop_after_write`). Default graph, edges on Q57: s2→m1, s2→m2, m1→y, m1→s2, m2→y. Right
after sync() (stamps `^IVG.BuiltFrom("deg2p"/"deg2p_exact")` = `^KG("__version")`): `khop2_count_fast(s2,"Q57")` = 3,
`khop2_count_exact` = 1. After `create_edge(z1, R57, z2)` (unrelated): both 1.

Expected: fast answers the number first reached at hop 2 (1), like exact, fresh or stale; or its documentation says
"an upper bound while the stats are current".

Observed: `KHop2CountFast` (TraversalKHop.cls:214-225) returns `^KG("deg2p",0,src,pred)` while `Fresh("deg2p")`;
`Build2HopStats` (TraversalBuild.cls:939-994) stores the sum over middle nodes of their out-degree on the predicate
("an upper bound"), counting the source reached back, first-hop nodes and a target once per middle node. Stale, it
walks (`KHop2Count`, 67-133), excluding source and first hop, each target once.

Consequence: callers reading the fast count as a count over-count right after a sync and get a different value after
any write.

Repair proposal (not implemented): document fast as an upper bound while current, or have it read `deg2p_exact`
(BuildNKG already builds it) when fresh. Preserve: stale stats never read (R284). Distinguishing case:
`two_hop_after_sync` [3, 1] becomes [1, 1] (or the doc names 3). Governing statement: structure.rebuilt (two-hop
statistics are a rebuilt store); docs/API_REFERENCE.md §khop2_count_fast.

Affected owner: structure.rebuilt.stamp (the reader rule holds; the value it gates departs), algorithms.op.khop.

## Inherited, strengthened

bug-plt-116: GA/GB share n_1→n_2 etc.; `^NKG` holds each once by name (`nkg_by_names`); `Adjacency.Remove`'s
`HeldElsewhere` keeps the merged edge when one graph drops it (`nkg_n1n2_after_ga` true), while a triple held by no
other graph loses it (`nkg_xa_after` false). Model: `adjacency_maint` `theorem_nkg_held_elsewhere`.
