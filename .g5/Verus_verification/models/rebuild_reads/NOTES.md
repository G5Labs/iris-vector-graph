# rebuild_reads — traversal readers during `sync()` (iteration 57, builder)

Product `3eaa79cf`. Owners: [structure.rebuild](../../../ontology/features/graph-structure.g5.md#structure.rebuild),
[algorithms.op.khop](../../../ontology/features/algorithms.g5.md#algorithms.op.khop),
[algorithms.op.paths](../../../ontology/features/algorithms.g5.md#algorithms.op.paths). Finding:
[bug-str-115](../../bugs_issues.md#bug-str-115).

## Mechanism (source read after the W61 freeze)

`sync()` → `_sync_kg` → `Graph.KG.Traversal.BuildKG` → `TraversalBuild.BuildKG` (lines 30-140). `BeginRebuild` takes the
writers' lock `^IVG.AdjW` **shared**; readers never take it. With a declared (functional) index the edge pass is
`rdfedges.%BuildIndices($lb("idxedgesadj"), 1, …, jobs)` after the transaction, which purges `out`/`in` and refills them
one row callback at a time, in up to 8 jobs (order unspecified); without one, `RemoveAll` and then `FillEdge` per row in
50,000-row transactions. `BFSFast` (khop, `execute_bfs`) and `TraversalPaths.ShortestLength` read `^KG` directly. The
code comment beside the kill says the intent: "destroyed adjacency looks to every reader like a graph with no edges".

## State and derivation

`visible(old, rows, k)`: the index a reader sees after k refill steps, derived from the rebuild's own steps: as built,
the purge and then the first k rows of the refill order (`rows.subrange(0, k)`); the repair (build aside, swap once, as
`RewriteNKG` does for `^NKG`) would show `old` until the swap. Readers: `khop_beyond_seed` (the seed has an out-edge in
the visible index) and `len1` (one-hop length, −1 for no path). No reader answer is an input.

## Claims

| Item | Kind | Statement |
|---|---|---|
| `theorem_reader_sees_seed_alone` | general | For every old index and rows that both hold v→w, some moment of the rebuild shows v with no out-edge: khop answers the seed alone and the length is −1 (bug-str-115). |
| `theorem_quiet_reader_sees_rows` | neighbor | With no rebuild running, the same readers see v→w: khop goes beyond the seed and the length is 1. |
| `theorem_visible_edges_are_rows` | general | Every index visible during the rebuild holds only rows (nothing invented). |
| `theorem_end_is_rows` | general | At the end, readers see exactly the rows (overlaps `adjacency_maint::theorem_incremental_equals_rebuild`). |
| `theorem_swap_shows_old_or_rows` | repair | A swapping rebuild only ever shows the old index or the rows (proved, not built). |

Controls (all EXPECTED_FAIL): `rebuild-swaps` (the repair as the product's decision), `refill-keeps-old` (the purge not
visible before the first refill), `refill-invents` (no purge), `swap-exposes-prefix` (the repair weakened).

## Binding

[binding.py](binding.py), run as in the runbook (iteration 57). Fixture `ivg-cont-20261117-iris`, USER, prefix
`i57r_<tag>_`, default graph `s-R->a, a-Q->b, s-R->c`. Quiet reads of `khop(s, 2)` and `shortest_path_length(s, b)`, then
the same reads in a loop while a child process (its own connection) runs `sync()` four times. Judged per read against
the port of `visible`: as built any subset of the rows (an unspecified refill order), so each read must equal the walk
over some subset; quiet reads must equal the walk over all rows; the seed-alone answer must be observed (the
existential of `theorem_reader_sees_seed_alone`). Mutation `swap` (only the full answer permitted) detected; tamper (a
node not in the rows) detected. Receipts: `20261117T075627Z-binding` AGREES (58,520 reads during sync, 4,487
departures, 4,481 of them the seed-alone answer). Kept: `20261117T075603Z-binding` DISAGREES — a harness error that
judged khop and the length as one read at one moment (fixed). The first observation was accidental: W1's binding ran
while W2's binding ran `sync()` (`results/traversal_strategy/20261117T075247Z-binding`, DISAGREES: 12 cases with
blank types and the SQL fallback); [race probe](../../../uplift/consolidated/iteration-57/rebuild_race/race_probe.py)
reproduced it deliberately ([observation](../../../uplift/consolidated/iteration-57/rebuild_race/)), including
`execute_bfs` rows with every type blank (the SQL fallback rescues the node set; `ReachTypes` reads the purged `^KG`).

## Domain, premises, exclusions

- Domain: one rebuild at a time; reads of `^KG` with no lock (observed); refill order arbitrary (8 jobs).
- Premise P-NO-READ-ISOLATION: an IRIS global read sees another process's purge and partial refill (observed here; also
  `structure.write`'s working assumption).
- Not modeled: the non-indexed path (`RemoveAll` + `FillEdge` in 50,000-row transactions; same exposure by
  inspection), `execute_bfs` types (observed only), the degree cache during the rebuild (BeginRebuild's lock protects
  it), Cypher reads (the SQL path reads `rdf_edges`, unaffected; native Cypher over `^KG` not exercised), `^NKG`
  (rewritten live; its own tests), Arno (absent).
