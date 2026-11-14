//! Module 06 (vectors), L1 part 1: the IVF index lifecycle against erasure and builds (HD-0601, HD-0602; F-0606).
//!
//! State: the live vectors `vecs` (one value stands for a vector; keyed `(graph, node)`), the published indexes
//! `idx[name] = (graph, entries)` an `ivf_build(graph=g)` made (vector.py:1880-2027), and the builds in flight
//! `pend[name]` with what each has read.
//!
//! Business rules (transition rules; `inv1` is their consequence):
//! - **an index belongs to its graph's erasure** (HD-0601 working answer: graph-owned indexes are invalidated or
//!   deleted on erase): `Erase{g}` removes the graph's vectors and every index (and build in flight) of g;
//! - **an index is published whole** (HD-0602 working answer: readers see a complete published index or a clear
//!   unavailable result, including after an interrupted rebuild): a build reads the graph's vectors (`BuildRead`) and
//!   publishes exactly that read in one step (`Publish`) or not at all (`Abandon` keeps the previous index);
//! - **a search answers the published index or says unavailable**: `Search{name, ans}` answers `Some(entries)` of the
//!   published index, or `None` when there is none (vector.py:2029-2031 documents `[]` as "does not exist").
//!
//! Not modelled (PROOFS.md): single-entry `Insert`/`Delete` (F-0608 lives there), the cell structure, scores and k,
//! VecIndex and PLAID (caller-fed indexes; HD-0601 asks only for a declaration), per-node vector deletion.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

/// A node id `(graph, node)`.
pub type Id = (int, int);

/// An index over graph `g`: `^IVF(name, "cfg", "table")` names g's route (IVFIndex.cls:9); `ent` are its listed ids
/// and vectors (`^IVF(name, "list", cell, id)`, the cell abstracted).
pub struct Idx { pub g: int, pub ent: Map<Id, int> }

pub struct VS1 {
    pub vecs: Map<Id, int>,
    pub idx: Map<nat, Idx>,
    pub pend: Map<nat, Idx>,
}

pub enum VL1 {
    /// A vector is stored (store_embedding / the queue worker into g's route).
    Store { id: Id, v: int },
    /// erase_graph(g): the graph's vectors leave, and so does every index of g.
    Erase { g: int },
    /// A build of `name` over graph g reads g's vectors.
    BuildRead { name: nat, g: int },
    /// The build publishes what it read, whole.
    Publish { name: nat },
    /// The build stops; the previous index stays as it was.
    Abandon { name: nat },
    /// ivf_search: the published entries, or unavailable.
    Search { name: nat, ans: Option<Map<Id, int>> },
}

pub open spec fn of_graph(m: Map<Id, int>, g: int) -> Map<Id, int> { m.filter_keys(|id: Id| id.0 == g) }
pub open spec fn drop_graph(m: Map<Id, int>, g: int) -> Map<Id, int> { m.filter_keys(|id: Id| id.0 != g) }
pub open spec fn drop_idx(ix: Map<nat, Idx>, g: int) -> Map<nat, Idx> { ix.filter_keys(|n: nat| ix[n].g != g) }

pub open spec fn answer(ix: Map<nat, Idx>, name: nat) -> Option<Map<Id, int>> {
    if ix.contains_key(name) { Some(ix[name].ent) } else { None }
}

pub struct VidxL1;

impl Contract for VidxL1 {
    type S = VS1;
    type L = VL1;

    open spec fn init(s: VS1) -> bool { s.idx == Map::<nat, Idx>::empty() && s.pend == Map::<nat, Idx>::empty() }

    open spec fn next(s: VS1, l: VL1, t: VS1) -> bool {
        match l {
            VL1::Store { id, v } => t == VS1 { vecs: s.vecs.insert(id, v), ..s },
            VL1::Erase { g } => t == VS1 { vecs: drop_graph(s.vecs, g), idx: drop_idx(s.idx, g), pend: drop_idx(s.pend, g) },
            VL1::BuildRead { name, g } =>
                !s.pend.contains_key(name) && t == VS1 { pend: s.pend.insert(name, Idx { g, ent: of_graph(s.vecs, g) }), ..s },
            VL1::Publish { name } =>
                s.pend.contains_key(name) && t == VS1 { idx: s.idx.insert(name, s.pend[name]), pend: s.pend.remove(name), ..s },
            VL1::Abandon { name } => s.pend.contains_key(name) && t == VS1 { pend: s.pend.remove(name), ..s },
            VL1::Search { name, ans } => ans == answer(s.idx, name) && t == s,
        }
    }
}

/// An index (or a build's read) lists only live vectors of its own graph.
pub open spec fn idx_ok(vecs: Map<Id, int>, ix: Idx) -> bool {
    forall|id: Id| #[trigger] ix.ent.contains_key(id) ==> id.0 == ix.g && vecs.contains_key(id)
}

pub open spec fn inv1(s: VS1) -> bool {
    &&& forall|n: nat| #[trigger] s.idx.contains_key(n) ==> idx_ok(s.vecs, s.idx[n])
    &&& forall|n: nat| #[trigger] s.pend.contains_key(n) ==> idx_ok(s.vecs, s.pend[n])
}

proof fn lemma_idx_ok_insert(vecs: Map<Id, int>, ix: Idx, id: Id, v: int)
    requires idx_ok(vecs, ix),
    ensures idx_ok(vecs.insert(id, v), ix),
{
}

proof fn lemma_idx_ok_erase(vecs: Map<Id, int>, ix: Idx, g: int)
    requires idx_ok(vecs, ix), ix.g != g,
    ensures idx_ok(drop_graph(vecs, g), ix),
{
    assert forall|id: Id| #[trigger] ix.ent.contains_key(id) implies id.0 == ix.g && drop_graph(vecs, g).contains_key(id) by {
        assert(vecs.dom().filter(|i: Id| i.0 != g).contains(id));
    }
}

impl SafeContract for VidxL1 {
    open spec fn inv(s: VS1) -> bool { inv1(s) }

    proof fn init_safe(s: VS1) {}

    proof fn step_safe(s: VS1, l: VL1, t: VS1) {
        match l {
            VL1::Store { id, v } => {
                assert forall|n: nat| #[trigger] t.idx.contains_key(n) implies idx_ok(t.vecs, t.idx[n]) by {
                    lemma_idx_ok_insert(s.vecs, s.idx[n], id, v);
                }
                assert forall|n: nat| #[trigger] t.pend.contains_key(n) implies idx_ok(t.vecs, t.pend[n]) by {
                    lemma_idx_ok_insert(s.vecs, s.pend[n], id, v);
                }
            }
            VL1::Erase { g } => {
                assert forall|n: nat| #[trigger] t.idx.contains_key(n) implies idx_ok(t.vecs, t.idx[n]) by {
                    assert(s.idx.dom().filter(|m: nat| s.idx[m].g != g).contains(n));
                    lemma_idx_ok_erase(s.vecs, s.idx[n], g);
                }
                assert forall|n: nat| #[trigger] t.pend.contains_key(n) implies idx_ok(t.vecs, t.pend[n]) by {
                    assert(s.pend.dom().filter(|m: nat| s.pend[m].g != g).contains(n));
                    lemma_idx_ok_erase(s.vecs, s.pend[n], g);
                }
            }
            VL1::BuildRead { name, g } => {
                assert forall|n: nat| #[trigger] t.pend.contains_key(n) implies idx_ok(t.vecs, t.pend[n]) by {
                    if n == name {
                        assert forall|id: Id| #[trigger] t.pend[n].ent.contains_key(id) implies
                            id.0 == t.pend[n].g && t.vecs.contains_key(id) by {
                            assert(s.vecs.dom().filter(|i: Id| i.0 == g).contains(id));
                        }
                    }
                }
            }
            VL1::Publish { name } => {
                assert forall|n: nat| #[trigger] t.idx.contains_key(n) implies idx_ok(t.vecs, t.idx[n]) by {
                    if n == name { assert(s.pend.contains_key(name)); }
                }
                assert forall|n: nat| #[trigger] t.pend.contains_key(n) implies idx_ok(t.vecs, t.pend[n]) by {
                    assert(s.pend.contains_key(n));
                }
            }
            VL1::Abandon { name } => {
                assert forall|n: nat| #[trigger] t.pend.contains_key(n) implies idx_ok(t.vecs, t.pend[n]) by {
                    assert(s.pend.contains_key(n));
                }
            }
            VL1::Search { name, ans } => {}
        }
    }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// HD-0601: a search answers only live vectors of the index's own graph; an erased graph's ids are never answered.
pub proof fn theorem_search_answers_live_ids_of_its_graph(s: VS1, name: nat, ans: Map<Id, int>, t: VS1, id: Id)
    requires inv1(s), VidxL1::next(s, VL1::Search { name, ans: Some(ans) }, t), ans.contains_key(id),
    ensures s.idx.contains_key(name), id.0 == s.idx[name].g, s.vecs.contains_key(id),
{
}

/// HD-0601: right after `Erase{g}` no index, published or being built, belongs to g or lists an id of g, and no
/// vector of g is live.
pub proof fn theorem_erase_leaves_nothing_of_the_graph(s: VS1, g: int, t: VS1)
    requires inv1(s), VidxL1::next(s, VL1::Erase { g }, t),
    ensures
        forall|n: nat| #[trigger] t.idx.contains_key(n) ==> t.idx[n].g != g,
        forall|n: nat| #[trigger] t.pend.contains_key(n) ==> t.pend[n].g != g,
        forall|n: nat, id: Id| t.idx.contains_key(n) && #[trigger] t.idx[n].ent.contains_key(id) ==> id.0 != g,
        forall|id: Id| #[trigger] t.vecs.contains_key(id) ==> id.0 != g,
{
    assert forall|n: nat| #[trigger] t.idx.contains_key(n) implies t.idx[n].g != g by {
        assert(s.idx.dom().filter(|m: nat| s.idx[m].g != g).contains(n));
    }
    assert forall|n: nat| #[trigger] t.pend.contains_key(n) implies t.pend[n].g != g by {
        assert(s.pend.dom().filter(|m: nat| s.pend[m].g != g).contains(n));
    }
    assert forall|n: nat, id: Id| t.idx.contains_key(n) && #[trigger] t.idx[n].ent.contains_key(id) implies id.0 != g by {
        assert(s.idx.dom().filter(|m: nat| s.idx[m].g != g).contains(n));
        assert(idx_ok(s.vecs, s.idx[n]));
    }
    assert forall|id: Id| #[trigger] t.vecs.contains_key(id) implies id.0 != g by {
        assert(s.vecs.dom().filter(|i: Id| i.0 != g).contains(id));
    }
}

/// HD-0602: a build reads every vector of its graph, and a publication installs exactly that read.
pub proof fn theorem_published_whole(s: VS1, name: nat, g: int, t: VS1, u: VS1)
    requires VidxL1::next(s, VL1::BuildRead { name, g }, t), VidxL1::next(t, VL1::Publish { name }, u),
    ensures u.idx[name] == (Idx { g, ent: of_graph(s.vecs, g) }), !u.pend.contains_key(name),
{
}

/// HD-0602: a stopped build leaves the published index exactly as it was.
pub proof fn theorem_abandon_keeps_previous_index(s: VS1, name: nat, t: VS1)
    requires VidxL1::next(s, VL1::Abandon { name }, t),
    ensures t.idx == s.idx, forall|n: nat| answer(t.idx, n) == answer(s.idx, n),
{
}

/// HD-0602: the published index changes only by a whole publication or an erase of its graph; a build's internal
/// work and its interruption are invisible to searches.
pub proof fn theorem_index_changes_only_by_publish_or_erase(s: VS1, l: VL1, t: VS1)
    requires VidxL1::next(s, l, t), t.idx != s.idx,
    ensures l is Publish || l is Erase,
{
}

} // verus!
