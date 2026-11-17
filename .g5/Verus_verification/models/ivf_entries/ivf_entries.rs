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

}
