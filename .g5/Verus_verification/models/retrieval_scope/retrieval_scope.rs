// product 3eaa79cf: the one-hop retrieval operators. kg_NEIGHBORS (iris_vector_graph/_engine/algorithms.py; kg_MENTIONS
//   and operators.IRISGraphOperators delegate to it) runs one Cypher MATCH per source and direction without USE GRAPH,
//   so it reads every graph, and keeps one `seen` set across all chunks. kg_NEIGHBORHOOD_EXPANSION
//   (_engine/vector.py) reads one graph (the default unless named) and keeps an edge only when its `confidence`
//   qualifier is present and at least the threshold.
use vstd::prelude::*;
verus! {

pub type G = int;
pub open spec fn DEFAULT() -> G { 0 }

/// Whether an operator reads an edge of graph g.
pub open spec fn neighbors_reads(g: G) -> bool { true }
pub open spec fn expansion_reads(g: G, arg: Option<G>) -> bool { g == match arg { Some(a) => a, None => DEFAULT() } }

/// Whether kg_NEIGHBORHOOD_EXPANSION keeps an edge with confidence `conf` (None when absent).
pub open spec fn expansion_keeps(conf: Option<int>, threshold: int) -> bool { match conf { Some(c) => c >= threshold, None => false } }

/// Whether a target is appended: always without `distinct`, else only if not seen in any earlier chunk or source.
pub open spec fn appended(distinct: bool, seen_before: bool) -> bool { !distinct || !seen_before }

/// N7 (question algorithms.op.neighbors.scope): an edge only in a named graph is returned by kg_NEIGHBORS and not by
/// kg_NEIGHBORHOOD_EXPANSION without a graph argument.
pub proof fn theorem_scopes_differ(g: G)
    requires g != DEFAULT(),
    ensures neighbors_reads(g), !expansion_reads(g, None), expansion_reads(g, Some(g)),
{}

/// N9: the expansion keeps exactly edges with a confidence at or above the threshold.
pub proof fn theorem_confidence_filter(t: int)
    ensures expansion_keeps(Some(t), t), !expansion_keeps(Some(t - 1), t), !expansion_keeps(None, t),
{}

/// N5/N6: with `distinct` a target seen before (in any chunk) is not appended again; without it, it is.
pub proof fn theorem_distinct_across_chunks()
    ensures !appended(true, true), appended(true, false), appended(false, true),
{}

}
