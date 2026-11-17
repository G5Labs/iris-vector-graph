// product 3eaa79cf: one node's entries in an IVF index after its build (iris_src/src/Graph/KG/IVFIndex.cls Insert, Delete,
//   Search; iris_vector_graph/_engine/vector.py ivf_insert, ivf_delete, ivf_search, ivf_info). Two cells suffice to show
//   the decisions. Insert writes ^IVF(name,"list",nearestCell,node) without touching the node's entry in another cell
//   and adds one to "indexed"; Delete removes the node's entry in the first cell (in subscript order) that has one, takes
//   one from "indexed", and stops. Search ranks entries by $vectorop over the query and each stored vector, with no
//   width check.
use vstd::prelude::*;
verus! {

pub struct St { pub in0: bool, pub in1: bool, pub indexed: int }

pub open spec fn insert(s: St, cell: int) -> St {
    if cell == 0 { St { in0: true, indexed: s.indexed + 1, ..s } } else { St { in1: true, indexed: s.indexed + 1, ..s } }
}
pub open spec fn delete(s: St) -> (St, bool) {
    if s.in0 { (St { in0: false, indexed: s.indexed - 1, ..s }, true) }
    else if s.in1 { (St { in1: false, indexed: s.indexed - 1, ..s }, true) }
    else { (s, false) }
}
pub open spec fn found(s: St) -> bool { s.in0 || s.in1 }
pub open spec fn entries(s: St) -> int { (if s.in0 { 1int } else { 0 }) + (if s.in1 { 1int } else { 0 }) }

/// Whether a search with a query of `q` entries answers scores from an index of width `dim`.
pub open spec fn search_answers(q: nat, dim: nat) -> bool { true }

/// V3/V5: a node inserted once and deleted once is gone, and the count is back.
pub proof fn theorem_insert_then_delete(c: int)
    requires c == 0 || c == 1,
    ensures ({ let s0 = St { in0: false, in1: false, indexed: 5 }; let (s2, r) = delete(insert(s0, c));
               r && !found(s2) && s2.indexed == 5 }),
{}

/// V4 (bug-srch-107): a re-insert into the same cell keeps one entry but counts two.
pub proof fn theorem_same_cell_reinsert_counts_twice()
    ensures ({ let s = insert(insert(St { in0: false, in1: false, indexed: 5 }, 0), 0); entries(s) == 1 && s.indexed == 7 }),
{}

/// V4b (bug-srch-107): a re-insert that lands in another cell keeps the old entry, and one delete leaves the node found.
pub proof fn theorem_cross_cell_reinsert_leaves_stale_entry()
    ensures ({ let s = insert(insert(St { in0: false, in1: false, indexed: 4 }, 0), 1);
               entries(s) == 2 && found(delete(s).0) && delete(s).1 }),
{}

/// V8 (bug-srch-108): a query of another width is answered with scores.
pub proof fn theorem_other_width_answered(q: nat, dim: nat)
    requires q != dim,
    ensures search_answers(q, dim),
{}

/// The three scoring branches of `IVFIndex.Search` (lines 75-82 for centroids, 112-119 for entries; `Insert` 200-205
/// uses the same pair for its cell): "cosine" and "dot" take $vectorop("sum", $vectorop("v*", q, v)); anything else
/// the negated squared distance. Nothing in Build, AddBatch, Insert or Search divides by a length.
pub enum Metric { Cosine, Dot, L2 }
pub open spec fn dot(a: Seq<int>, b: Seq<int>) -> int
    decreases a.len(),
{
    if a.len() == 0 || b.len() == 0 { 0 } else { a[0] * b[0] + dot(a.drop_first(), b.drop_first()) }
}
pub open spec fn sqdist(a: Seq<int>, b: Seq<int>) -> int
    decreases a.len(),
{
    if a.len() == 0 || b.len() == 0 { 0 } else { (a[0] - b[0]) * (a[0] - b[0]) + sqdist(a.drop_first(), b.drop_first()) }
}
pub open spec fn entry_score(m: Metric, q: Seq<int>, v: Seq<int>) -> int {
    match m { Metric::Cosine => dot(q, v), Metric::Dot => dot(q, v), Metric::L2 => -sqdist(q, v) }
}
/// Search's order: a higher score is returned first (^||ivfRanked(-score, node)).
pub open spec fn ivf_above(m: Metric, q: Seq<int>, v1: Seq<int>, v2: Seq<int>) -> bool {
    entry_score(m, q, v1) > entry_score(m, q, v2)
}
/// The rule for metric "cosine" (its name; the route search and VecIndex since 4.7.0): v1 above v2 when
/// dot1/|v1| > dot2/|v2|, decided exactly without roots as sgn(d1)·d1²·|v2|² > sgn(d2)·d2²·|v1|².
pub open spec fn ssq(d: int) -> int { if d >= 0 { d * d } else { -(d * d) } }
pub open spec fn cosine_above(q: Seq<int>, v1: Seq<int>, v2: Seq<int>) -> bool {
    ssq(dot(q, v1)) * dot(v2, v2) > ssq(dot(q, v2)) * dot(v1, v1)
}

/// W53 (bug-srch-109): for every query and pair of vectors, an index built with metric "cosine" scores and orders
/// exactly as one built with "dot".
pub proof fn theorem_cosine_ranks_as_dot(q: Seq<int>, v1: Seq<int>, v2: Seq<int>)
    ensures entry_score(Metric::Cosine, q, v1) == entry_score(Metric::Dot, q, v1),
            ivf_above(Metric::Cosine, q, v1, v2) == ivf_above(Metric::Dot, q, v1, v2),
{}

/// W53 (bug-srch-109): q = (3,4), a long off-axis v1 = (10,0) and an aligned v2 = (3,4). Search returns v1 first
/// (30 > 25) while the cosine rule puts v2 first (cosine 1 against 0.6).
pub proof fn theorem_cosine_metric_misranks()
    ensures ({ let q = seq![3int, 4int]; let v1 = seq![10int, 0int]; let v2 = seq![3int, 4int];
               ivf_above(Metric::Cosine, q, v1, v2) && cosine_above(q, v2, v1) }),
{
    let q = seq![3int, 4int]; let v1 = seq![10int, 0int]; let v2 = seq![3int, 4int];
    reveal_with_fuel(dot, 3);
    assert(q.drop_first() =~= seq![4int]); assert(v1.drop_first() =~= seq![0int]); assert(v2.drop_first() =~= seq![4int]);
    assert(q.drop_first().drop_first().len() == 0);
    assert(dot(q, v1) == 30); assert(dot(q, v2) == 25); assert(dot(v1, v1) == 100); assert(dot(v2, v2) == 25);
}

/// Neighbor: on vectors of one length the two orders agree (q = (3,4); v1 = (3,4) and v2 = (5,0), both length 5).
pub proof fn theorem_equal_lengths_agree()
    ensures ({ let q = seq![3int, 4int]; let v1 = seq![3int, 4int]; let v2 = seq![5int, 0int];
               ivf_above(Metric::Cosine, q, v1, v2) && cosine_above(q, v1, v2) }),
{
    let q = seq![3int, 4int]; let v1 = seq![3int, 4int]; let v2 = seq![5int, 0int];
    reveal_with_fuel(dot, 3);
    assert(q.drop_first() =~= seq![4int]); assert(v1.drop_first() =~= seq![4int]); assert(v2.drop_first() =~= seq![0int]);
    assert(dot(q, v1) == 25); assert(dot(q, v2) == 15); assert(dot(v1, v1) == 25); assert(dot(v2, v2) == 25);
}

}
