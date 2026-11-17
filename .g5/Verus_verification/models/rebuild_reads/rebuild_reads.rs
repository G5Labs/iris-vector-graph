// product 3eaa79cf: what a traversal reader sees while engine.sync() rebuilds ^KG (structure.rebuild, algorithms.op.khop).
//   iris_vector_graph/_engine/schema.py sync -> _sync_kg -> Graph.KG.Traversal.BuildKG -> TraversalBuild.BuildKG:
//   BeginRebuild takes the writers' lock ^IVG.AdjW shared (readers never take it); with a declared index the edge
//   pass is rdfedges.%BuildIndices(idxedgesadj, purge) after the transaction, which empties out/in and refills them
//   one row callback at a time (up to 8 jobs, order unspecified); without one, RemoveAll then FillEdge per row.
//   Readers (BFSFast via khop / execute_bfs, ShortestLength) read ^KG directly with no lock and no snapshot.
// State: the rows R (the edges the rebuild refills) and the index the readers see after k refill steps.
// The visible index is derived from the rebuild's own steps; no reader answer is an input.
use vstd::prelude::*;
verus! {

pub struct Edge { pub s: int, pub o: int }

/// The as-built rebuild empties the index and refills it row by row (in some order: `rows` is that order).
/// A rebuild that builds aside and swaps once (as RewriteNKG does for ^NKG) would expose old until the swap.
pub open spec fn swaps() -> bool { false }

/// The index a reader sees after k of the rebuild's refill steps (0 <= k <= rows.len()).
pub open spec fn visible(old: Seq<Edge>, rows: Seq<Edge>, k: int) -> Seq<Edge> {
    if swaps() { if k < rows.len() { old } else { rows } } else { rows.subrange(0, k) }
}

pub open spec fn has_out(idx: Seq<Edge>, v: int) -> bool { exists|i: int| 0 <= i < idx.len() && (#[trigger] idx[i]).s == v }

/// khop (BFSFast over ^KG, one hop shown): the seed alone unless the visible index holds an out-edge of it.
pub open spec fn khop_beyond_seed(idx: Seq<Edge>, v: int) -> bool { has_out(idx, v) }

/// ShortestLength(v, w) for one hop: 1 when the visible index holds v->w, else -1 (no path).
pub open spec fn len1(idx: Seq<Edge>, v: int, w: int) -> int {
    if exists|i: int| 0 <= i < idx.len() && (#[trigger] idx[i]) == (Edge { s: v, o: w }) { 1 } else { -1 }
}

pub open spec fn in_seq(x: Edge, r: Seq<Edge>) -> bool { exists|j: int| 0 <= j < r.len() && r[j] == x }

/// General: every index a reader can see during the rebuild holds only rows (nothing invented).
pub proof fn theorem_visible_edges_are_rows(old: Seq<Edge>, rows: Seq<Edge>, k: int, i: int)
    requires 0 <= k <= rows.len(), 0 <= i < visible(old, rows, k).len(), !swaps(),
    ensures in_seq(visible(old, rows, k)[i], rows),
{
    assert(visible(old, rows, k)[i] == rows[i]);
}

/// General: at the end of the refill the readers see exactly the rows.
pub proof fn theorem_end_is_rows(old: Seq<Edge>, rows: Seq<Edge>)
    ensures visible(old, rows, rows.len() as int) =~= rows,
{}

/// bug-str-115 (general): for every graph in which a seed has an out-edge both before and after the rebuild, some
/// moment of the rebuild shows the seed with no out-edge: khop answers the seed alone and a one-hop path is "no path".
pub proof fn theorem_reader_sees_seed_alone(old: Seq<Edge>, rows: Seq<Edge>, v: int, w: int)
    requires has_out(old, v), in_seq(Edge { s: v, o: w }, old), in_seq(Edge { s: v, o: w }, rows), rows.len() > 0,
    ensures exists|k: int| 0 <= k <= rows.len() && !khop_beyond_seed(visible(old, rows, k), v) && len1(visible(old, rows, k), v, w) == -1,
{
    assert(visible(old, rows, 0) =~= Seq::<Edge>::empty());
    assert(!khop_beyond_seed(visible(old, rows, 0), v));
    assert(len1(visible(old, rows, 0), v, w) == -1);
}

/// The quiet neighbor: with no rebuild running (k = rows.len(), rows = old), khop goes beyond the seed and the path is found.
pub proof fn theorem_quiet_reader_sees_rows(rows: Seq<Edge>, v: int, w: int)
    requires in_seq(Edge { s: v, o: w }, rows),
    ensures khop_beyond_seed(visible(rows, rows, rows.len() as int), v), len1(visible(rows, rows, rows.len() as int), v, w) == 1,
{
    let j = choose|j: int| 0 <= j < rows.len() && rows[j] == Edge { s: v, o: w };
    assert(visible(rows, rows, rows.len() as int) =~= rows);
    assert(visible(rows, rows, rows.len() as int)[j].s == v);
}

// ---- the repair the owner's "running it again is safe" asks for: build aside, swap once
pub open spec fn visible_swap(old: Seq<Edge>, rows: Seq<Edge>, k: int) -> Seq<Edge> { if k < rows.len() { old } else { rows } }

/// Repair (proved here, not built): every moment of a swapping rebuild shows either the old index or the rows.
pub proof fn theorem_swap_shows_old_or_rows(old: Seq<Edge>, rows: Seq<Edge>, k: int)
    requires 0 <= k <= rows.len(),
    ensures visible_swap(old, rows, k) == old || visible_swap(old, rows, k) == rows,
{}

}
