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

pub proof fn lemma_ssq_strict(d1: int, d2: int)
    requires d1 > d2,
    ensures ssq(d1) > ssq(d2),
{
    if d2 >= 0 { assert(d1 * d1 > d2 * d2) by (nonlinear_arith) requires d1 > d2, d2 >= 0; }
    else if d1 >= 0 { assert(d1 * d1 >= 0) by (nonlinear_arith); assert(d2 * d2 > 0) by (nonlinear_arith) requires d2 < 0; }
    else { assert(d2 * d2 > d1 * d1) by (nonlinear_arith) requires d2 < d1, d1 < 0; }
}
/// Neighbor (m9: for every query and every pair of vectors of the same nonzero length): the dot product's order, which
/// "cosine" uses today (theorem_cosine_ranks_as_dot), agrees with the cosine rule, so unit-length vectors are ranked
/// correctly.
pub proof fn theorem_equal_lengths_agree(q: Seq<int>, v1: Seq<int>, v2: Seq<int>)
    requires dot(v1, v1) == dot(v2, v2), dot(v1, v1) > 0,
    ensures ivf_above(Metric::Dot, q, v1, v2) == cosine_above(q, v1, v2),
{
    let d1 = dot(q, v1); let d2 = dot(q, v2); let l = dot(v1, v1);
    if d1 > d2 {
        lemma_ssq_strict(d1, d2);
        assert(ssq(d1) * l > ssq(d2) * l) by (nonlinear_arith) requires ssq(d1) > ssq(d2), l > 0;
    } else if d1 == d2 {
    } else {
        lemma_ssq_strict(d2, d1);
        assert(ssq(d2) * l > ssq(d1) * l) by (nonlinear_arith) requires ssq(d2) > ssq(d1), l > 0;
    }
}

/// Witness kept from iteration 47 (q = (3,4); v1 = (3,4) and v2 = (5,0), both length 5): both orders put v1 first.
pub proof fn theorem_equal_lengths_witness()
    ensures ({ let q = seq![3int, 4int]; let v1 = seq![3int, 4int]; let v2 = seq![5int, 0int];
               ivf_above(Metric::Cosine, q, v1, v2) && cosine_above(q, v1, v2) }),
{
    let q = seq![3int, 4int]; let v1 = seq![3int, 4int]; let v2 = seq![5int, 0int];
    reveal_with_fuel(dot, 3);
    assert(q.drop_first() =~= seq![4int]); assert(v1.drop_first() =~= seq![4int]); assert(v2.drop_first() =~= seq![0int]);
    assert(dot(q, v1) == 25); assert(dot(q, v2) == 15); assert(dot(v1, v1) == 25); assert(dot(v2, v2) == 25);
    // the distances too, so the witness does not depend on which scorer the cosine branch takes
    reveal_with_fuel(sqdist, 3);
    assert(q.drop_first().drop_first().len() == 0); assert(v2.drop_first().drop_first().len() == 0);
    assert(sqdist(q.drop_first(), v2.drop_first()) == 16); assert(sqdist(q, v1) == 0); assert(sqdist(q, v2) == 20);
}

// ---------------------------------------------------------------- which cell a vector is put in (review 47-49 m8)
/// ivf_build (vector.py 1987-2017) clusters the route's raw vectors with scikit-learn MiniBatchKMeans and passes its
/// labels to AddBatch, which stores each vector in that cell (IVFIndex.cls 237-259). The metric is not consulted.
/// Provider premise: a label is the Euclidean-nearest final centroid (scikit-learn's compute_labels, observed on the
/// fixture for well-separated clusters); ties go to the lower cell.
pub open spec fn build_cell(v: Seq<int>, c0: Seq<int>, c1: Seq<int>) -> int { if sqdist(v, c0) <= sqdist(v, c1) { 0 } else { 1 } }
/// Insert's own copy of the metric branch (IVFIndex.cls 200-205): "cosine" and "dot" score a centroid by the dot
/// product, anything else by the negated squared distance.
pub open spec fn insert_score(m: Metric, v: Seq<int>, c: Seq<int>) -> int {
    match m { Metric::Cosine => dot(v, c), Metric::Dot => dot(v, c), Metric::L2 => -sqdist(v, c) }
}
/// Insert keeps the first best cell (`sc > bestScore`, cells in order).
pub open spec fn insert_cell(m: Metric, v: Seq<int>, c0: Seq<int>, c1: Seq<int>) -> int {
    if insert_score(m, v, c1) > insert_score(m, v, c0) { 1 } else { 0 }
}
/// Neighbor (every vector and centroid pair): under "l2" Insert picks the cell the build picks.
pub proof fn theorem_l2_insert_matches_build(v: Seq<int>, c0: Seq<int>, c1: Seq<int>)
    ensures insert_cell(Metric::L2, v, c0, c1) == build_cell(v, c0, c1),
{}
/// m8 witness (observed on the fixture in iteration 50): centroids c0 = (1,0) and c1 = (5,5), and the vector v = (2,0)
/// that the build put in c0 (distance 1 against 34; also the cosine-nearest cell, cosine 1 against 0.71). Under
/// "cosine" Insert scores c1 higher (dot 10 against 2) and puts v in c1, so re-inserting a node with its unchanged
/// vector leaves its build copy in c0 as a second entry (bug-srch-107's cross-cell case).
pub proof fn theorem_cosine_reinsert_changes_cell()
    ensures ({ let v = seq![2int, 0int]; let c0 = seq![1int, 0int]; let c1 = seq![5int, 5int];
               build_cell(v, c0, c1) == 0 && cosine_above(v, c0, c1) && insert_cell(Metric::Cosine, v, c0, c1) == 1 }),
{
    let v = seq![2int, 0int]; let c0 = seq![1int, 0int]; let c1 = seq![5int, 5int];
    reveal_with_fuel(dot, 3); reveal_with_fuel(sqdist, 3);
    assert(v.drop_first() =~= seq![0int]); assert(c0.drop_first() =~= seq![0int]); assert(c1.drop_first() =~= seq![5int]);
    assert(v.drop_first().drop_first().len() == 0);
    assert(c1.drop_first().drop_first().len() == 0); assert(c0.drop_first().drop_first().len() == 0);
    let a = v.drop_first(); let b = c1.drop_first();
    assert(a[0] == 0); assert(b[0] == 5); assert((a[0] - b[0]) * (a[0] - b[0]) == 25);
    assert(a.drop_first().len() == 0); assert(sqdist(a.drop_first(), b.drop_first()) == 0);
    assert(sqdist(a, b) == 25);
    assert(sqdist(v, c0) == 1); assert(sqdist(v, c1) == 34);
    assert(dot(v, c0) == 2); assert(dot(v, c1) == 10); assert(dot(c0, c0) == 1); assert(dot(c1, c1) == 50);
}

}
