//! Module 06 (vectors), L2 part 1: the IVF index over its stored layout at pin 3eaa79cf, its refinement of `vidx_l1`
//! for every step, its invariant, and the broken-implementation controls F-0606 and HD-0602.
//!
//! State (production names):
//! - `vecs`  the rows of graph g's routed vector table (`kg_emb_<16 hex>`: graph_id, node_id, emb), spec 227
//! - `ivf`   `^IVF(name)`: `("cfg", "table")` = g's route (IVFIndex.cls:9, vector.py:2006), so the index's graph is in
//!           the layout; `("list", cell, id)` = vector (the cell abstracted)
//! - `stg`   reviewed design only: the staging generation a build fills before it is published (HD-0602 alternative
//!           (a): build under another name and swap it in)
//! - `b`     the `ivf_build` call in flight (vector.py:1880-2027): it reads g's vectors (and runs k-means) in Python,
//!           then calls `IVFIndex.Build` (Kill ^IVF(name), cfg with indexed 0, IVFIndex.cls:6-53), one `AddBatch` per
//!           `build_batch_size` vectors (:237-257) and `FinalizeIndex` (:260-276), each a separate server call with no
//!           lock and no transaction; it can stop between any two
//!
//! **Design** (reviewed, the working answers): the build fills the staging generation and publishes it in one step
//! after its last batch (HD-0602 (a)); `Eraser.EraseGraph(g)` drops every `^IVF` generation, published or staging,
//! whose recorded table is g's route (HD-0601 (a)). At the pin neither holds: the build writes `^IVF(name)` in place
//! and the eraser names no `^IVF` (Eraser.cls; GraphStores.cls:28-131). Controls put back the pin's decisions.
//!
//! Modelling premises (PROOFS.md): P-V1 one build at a time; P-V2 a search reads the published generation in one
//! step; P-V3 an erase of g overlaps no build of g; P-V4 each id is listed in one cell (the pin violates it, F-0608).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vidx_l1::*;

verus! {

pub enum BPh { Read, Built }
/// The build in flight: the index name, its graph, the vectors it read (and assigned to cells), its phase.
pub struct BP { pub name: nat, pub g: int, pub data: Map<Id, int>, pub ph: BPh }

pub struct VS2 {
    pub vecs: Map<Id, int>,
    pub ivf: Map<nat, Idx>,
    pub stg: Map<nat, Idx>,
    pub b: Option<BP>,
}

pub enum VL2 {
    Store { id: Id, v: int },
    Erase { g: int },
    /// The Python side reads g's vectors (vector.py:1946-1996).
    BRead { name: nat, g: int },
    /// `IVFIndex.Build`: kill the target and write its cfg with no entries.
    BBuild,
    /// `IVFIndex.AddBatch`: set one batch of list entries.
    BAdd { batch: Set<Id> },
    /// After the last batch: reviewed, publish the staging generation in one step; as built, `FinalizeIndex`.
    BPublish { name: nat },
    /// The build stops (an error, a stopped process).
    BStop { name: nat },
    Search { name: nat, ans: Option<Map<Id, int>> },
}

pub open spec fn f0606() -> bool { cfg!(feature = "control_f0606_erase_keeps_ivf") }
pub open spec fn hd0602() -> bool { cfg!(feature = "control_hd0602_inplace_build") }

/// The build's target: the staging generations (reviewed) or `^IVF` itself (as built).
pub open spec fn target(s: VS2) -> Map<nat, Idx> { if hd0602() { s.ivf } else { s.stg } }
pub open spec fn set_target(s: VS2, m: Map<nat, Idx>) -> VS2 {
    if hd0602() { VS2 { ivf: m, ..s } } else { VS2 { stg: m, ..s } }
}

pub open spec fn init2(s: VS2) -> bool {
    s.ivf == Map::<nat, Idx>::empty() && s.stg == Map::<nat, Idx>::empty() && s.b is None
}

pub open spec fn step2(s: VS2, l: VL2, t: VS2) -> bool {
    match l {
        VL2::Store { id, v } => t == VS2 { vecs: s.vecs.insert(id, v), ..s },
        VL2::Erase { g } => {
            &&& match s.b { Some(bp) => bp.g != g, None => true }
            &&& t == VS2 { vecs: drop_graph(s.vecs, g),
                           ivf: if f0606() { s.ivf } else { drop_idx(s.ivf, g) },
                           stg: if f0606() { s.stg } else { drop_idx(s.stg, g) }, ..s }
        },
        VL2::BRead { name, g } =>
            s.b is None && t == VS2 { b: Some(BP { name, g, data: of_graph(s.vecs, g), ph: BPh::Read }), ..s },
        VL2::BBuild => match s.b {
            Some(bp) => bp.ph is Read
                && t == VS2 { b: Some(BP { ph: BPh::Built, ..bp }),
                              ..set_target(s, target(s).insert(bp.name, Idx { g: bp.g, ent: Map::empty() })) },
            None => false,
        },
        VL2::BAdd { batch } => match s.b {
            Some(bp) => bp.ph is Built && batch.subset_of(bp.data.dom()) && target(s).contains_key(bp.name)
                && t == set_target(s, target(s).insert(bp.name,
                        Idx { ent: target(s)[bp.name].ent.union_prefer_right(bp.data.restrict(batch)), ..target(s)[bp.name] })),
            None => false,
        },
        VL2::BPublish { name } => match s.b {
            Some(bp) => bp.ph is Built && bp.name == name && target(s).contains_key(name) && target(s)[name].ent == bp.data
                && t == (if hd0602() { VS2 { b: None, ..s } }
                         else { VS2 { ivf: s.ivf.insert(name, s.stg[name]), stg: s.stg.remove(name), b: None, ..s } }),
            None => false,
        },
        VL2::BStop { name } => match s.b { Some(bp) => bp.name == name && t == VS2 { b: None, ..s }, None => false },
        VL2::Search { name, ans } => ans == answer(s.ivf, name) && t == s,
    }
}

// ------------------------------------------------------------------------------------------------ invariant

/// The build in flight read live vectors of its graph; once built, its target generation is of its graph and holds
/// only what it read.
pub open spec fn inv_b(s: VS2) -> bool {
    match s.b {
        Some(bp) => idx_ok(s.vecs, Idx { g: bp.g, ent: bp.data })
            && (bp.ph is Built ==> target(s).contains_key(bp.name) && target(s)[bp.name].g == bp.g
                                   && target(s)[bp.name].ent.submap_of(bp.data)),
        None => true,
    }
}

/// HD-0601 for the staging generations: they too hold only live vectors of their graph.
pub open spec fn inv_stg(s: VS2) -> bool { forall|n: nat| #[trigger] s.stg.contains_key(n) ==> idx_ok(s.vecs, s.stg[n]) }

pub open spec fn inv06i(s: VS2) -> bool { inv_b(s) && inv_stg(s) }

pub struct VidxL2;

impl Contract for VidxL2 {
    type S = VS2;
    type L = VL2;
    open spec fn init(s: VS2) -> bool { init2(s) }
    open spec fn next(s: VS2, l: VL2, t: VS2) -> bool { inv06i(s) && step2(s, l, t) }
}

pub struct VidxRaw;

impl Contract for VidxRaw {
    type S = VS2;
    type L = VL2;
    open spec fn init(s: VS2) -> bool { init2(s) }
    open spec fn next(s: VS2, l: VL2, t: VS2) -> bool { step2(s, l, t) }
}

// ------------------------------------------------------------------------------------------------ the abstraction

pub open spec fn pend_of(b: Option<BP>) -> Map<nat, Idx> {
    match b { Some(bp) => Map::<nat, Idx>::empty().insert(bp.name, Idx { g: bp.g, ent: bp.data }), None => Map::<nat, Idx>::empty() }
}

pub open spec fn absv(s: VS2) -> VS1 { VS1 { vecs: s.vecs, idx: s.ivf, pend: pend_of(s.b) } }

pub open spec fn labv(l: VL2) -> Option<VL1> {
    match l {
        VL2::Store { id, v } => Some(VL1::Store { id, v }),
        VL2::Erase { g } => Some(VL1::Erase { g }),
        VL2::BRead { name, g } => Some(VL1::BuildRead { name, g }),
        VL2::BBuild => None,
        VL2::BAdd { batch } => None,
        VL2::BPublish { name } => Some(VL1::Publish { name }),
        VL2::BStop { name } => Some(VL1::Abandon { name }),
        VL2::Search { name, ans } => Some(VL1::Search { name, ans }),
    }
}

// ------------------------------------------------------------------------------------------------ step lemmas

proof fn lemma_store(s: VS2, id: Id, v: int, t: VS2)
    requires inv06i(s), step2(s, VL2::Store { id, v }, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(VL2::Store { id, v }), absv(t)),
{
    assert forall|n: nat| #[trigger] t.stg.contains_key(n) implies idx_ok(t.vecs, t.stg[n]) by {
        assert(idx_ok(s.vecs, s.stg[n]));
    }
}

proof fn lemma_erase(s: VS2, g: int, t: VS2)
    requires inv06i(s), step2(s, VL2::Erase { g }, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(VL2::Erase { g }), absv(t)),
{
    // the eraser drops every published generation of g (control F-0606 fails here)
    assert(t.ivf == drop_idx(s.ivf, g));
    assert(drop_idx(pend_of(s.b), g) =~= pend_of(s.b));
    assert forall|n: nat| #[trigger] t.stg.contains_key(n) implies idx_ok(t.vecs, t.stg[n]) by {
        // ... and every staging generation of g (control F-0606 fails here too)
        assert(s.stg.dom().filter(|m: nat| s.stg[m].g != g).contains(n));
        assert forall|id: Id| #[trigger] t.stg[n].ent.contains_key(id) implies id.0 == t.stg[n].g && t.vecs.contains_key(id) by {
            assert(idx_ok(s.vecs, s.stg[n]));
            assert(s.vecs.dom().filter(|i: Id| i.0 != g).contains(id));
        }
    }
    if let Some(bp) = s.b {
        let ix = Idx { g: bp.g, ent: bp.data };
        assert(idx_ok(s.vecs, ix));
        assert forall|id: Id| #[trigger] bp.data.contains_key(id) implies id.0 == bp.g && t.vecs.contains_key(id) by {
            assert(ix.ent.contains_key(id));
            assert(s.vecs.dom().filter(|i: Id| i.0 != g).contains(id));
        }
        if bp.ph is Built {
            assert(target(s).dom().filter(|m: nat| target(s)[m].g != g).contains(bp.name));
        }
    }
}

proof fn lemma_bread(s: VS2, name: nat, g: int, t: VS2)
    requires inv06i(s), step2(s, VL2::BRead { name, g }, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(VL2::BRead { name, g }), absv(t)),
{
    assert forall|id: Id| #[trigger] of_graph(s.vecs, g).contains_key(id) implies id.0 == g && s.vecs.contains_key(id) by {
        assert(s.vecs.dom().filter(|i: Id| i.0 == g).contains(id));
    }
    assert(pend_of(t.b) =~= pend_of(s.b).insert(name, Idx { g, ent: of_graph(s.vecs, g) }));
}

proof fn lemma_bbuild(s: VS2, t: VS2)
    requires inv06i(s), step2(s, VL2::BBuild, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(VL2::BBuild), absv(t)),
{
    let bp = s.b->0;
    assert(t.ivf == s.ivf);   // the build is not visible to searches (control HD-0602 fails here)
    assert(t.b == Some(BP { ph: BPh::Built, ..bp }));
    assert(target(t) == target(s).insert(bp.name, Idx { g: bp.g, ent: Map::empty() }));
    assert(Map::<Id, int>::empty().submap_of(bp.data));
    assert forall|n: nat| #[trigger] t.stg.contains_key(n) implies idx_ok(t.vecs, t.stg[n]) by {
        if n != bp.name || hd0602() { assert(s.stg.contains_key(n)); }
    }
}

proof fn lemma_badd(s: VS2, batch: Set<Id>, t: VS2)
    requires inv06i(s), step2(s, VL2::BAdd { batch }, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(VL2::BAdd { batch }), absv(t)),
{
    let bp = s.b->0;
    assert(t.ivf == s.ivf);   // a batch is not visible to searches (control HD-0602 fails here)
    let old = target(s)[bp.name];
    let nw = Idx { ent: old.ent.union_prefer_right(bp.data.restrict(batch)), ..old };
    assert(target(t) == target(s).insert(bp.name, nw));
    assert(nw.ent.submap_of(bp.data)) by {
        assert forall|id: Id| #[trigger] nw.ent.contains_key(id) implies bp.data.contains_key(id) && nw.ent[id] == bp.data[id] by {
            if bp.data.restrict(batch).contains_key(id) {} else { assert(old.ent.contains_key(id)); }
        }
    }
    assert forall|n: nat| #[trigger] t.stg.contains_key(n) implies idx_ok(t.vecs, t.stg[n]) by {
        if n == bp.name && !hd0602() {
            let ix = Idx { g: bp.g, ent: bp.data };
            assert(idx_ok(s.vecs, ix));
            assert forall|id: Id| #[trigger] t.stg[n].ent.contains_key(id) implies id.0 == t.stg[n].g && t.vecs.contains_key(id) by {
                assert(bp.data.contains_key(id));
                assert(ix.ent.contains_key(id));
            }
        } else { assert(s.stg.contains_key(n)); }
    }
}

proof fn lemma_bpublish(s: VS2, name: nat, t: VS2)
    requires inv06i(s), step2(s, VL2::BPublish { name }, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(VL2::BPublish { name }), absv(t)),
{
    let bp = s.b->0;
    assert(target(s)[name] == (Idx { g: bp.g, ent: bp.data }));
    assert(pend_of(s.b)[name] == (Idx { g: bp.g, ent: bp.data }));
    assert(pend_of(s.b).remove(name) =~= Map::<nat, Idx>::empty());
    if hd0602() { assert(s.ivf.insert(name, pend_of(s.b)[name]) =~= s.ivf); }
    assert forall|n: nat| #[trigger] t.stg.contains_key(n) implies idx_ok(t.vecs, t.stg[n]) by { assert(s.stg.contains_key(n)); }
}

proof fn lemma_bstop(s: VS2, name: nat, t: VS2)
    requires inv06i(s), step2(s, VL2::BStop { name }, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(VL2::BStop { name }), absv(t)),
{
    assert(pend_of(s.b).remove(name) =~= Map::<nat, Idx>::empty());
}

proof fn lemma_step(s: VS2, l: VL2, t: VS2)
    requires inv06i(s), step2(s, l, t),
    ensures inv06i(t), step_or_stutter::<VidxL1>(absv(s), labv(l), absv(t)),
{
    match l {
        VL2::Store { id, v } => lemma_store(s, id, v, t),
        VL2::Erase { g } => lemma_erase(s, g, t),
        VL2::BRead { name, g } => lemma_bread(s, name, g, t),
        VL2::BBuild => lemma_bbuild(s, t),
        VL2::BAdd { batch } => lemma_badd(s, batch, t),
        VL2::BPublish { name } => lemma_bpublish(s, name, t),
        VL2::BStop { name } => lemma_bstop(s, name, t),
        VL2::Search { name, ans } => {}
    }
}

impl Refines<VidxL1> for VidxL2 {
    open spec fn abs(s: VS2) -> VS1 { absv(s) }
    open spec fn lab(l: VL2) -> Option<VL1> { labv(l) }
    proof fn init_refines(s: VS2) {}
    proof fn step_refines(s: VS2, l: VL2, t: VS2) { lemma_step(s, l, t); }
}

impl SafeContract for VidxL2 {
    open spec fn inv(s: VS2) -> bool { inv06i(s) }
    proof fn init_safe(s: VS2) {}
    proof fn step_safe(s: VS2, l: VL2, t: VS2) { lemma_step(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ theorems

proof fn lemma_raw_inv_at(states: Seq<VS2>, labels: Seq<VL2>, k: int)
    requires execution::<VidxRaw>(states, labels), 0 <= k < states.len(),
    ensures inv06i(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution every state of which satisfies L1's business invariant.
pub proof fn theorem_raw_executions_refine(states: Seq<VS2>, labels: Seq<VL2>)
    requires execution::<VidxRaw>(states, labels),
    ensures
        execution::<VidxL2>(states, labels),
        abstract_execution::<VidxL1>(Seq::new(states.len(), |i: int| absv(states[i])),
                                     Seq::new(labels.len(), |i: int| labv(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv06i(#[trigger] states[i]) && inv1(absv(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv06i(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<VidxL2>(states, labels));
    trace_refines::<VidxL2, VidxL1>(states, labels);
    refinement_preserves_safety::<VidxL2, VidxL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absv(states[i])) =~= Seq::new(states.len(), |i: int| <VidxL2 as Refines<VidxL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labv(labels[i])) =~= Seq::new(labels.len(), |i: int| <VidxL2 as Refines<VidxL1>>::lab(labels[i])));
}

/// HD-0601 on the layout: in a reachable state no `^IVF` generation, published or staging, lists a vector that is
/// not live in its own graph (so none of an erased graph).
pub proof fn theorem_ivf_holds_only_live_vectors(s: VS2, n: nat, id: Id)
    requires inv06i(s), inv1(absv(s)),
    ensures
        s.ivf.contains_key(n) && s.ivf[n].ent.contains_key(id) ==> id.0 == s.ivf[n].g && s.vecs.contains_key(id),
        s.stg.contains_key(n) && s.stg[n].ent.contains_key(id) ==> id.0 == s.stg[n].g && s.vecs.contains_key(id),
{
    if s.ivf.contains_key(n) { assert(absv(s).idx.contains_key(n)); assert(idx_ok(s.vecs, s.ivf[n])); }
    if s.stg.contains_key(n) { assert(idx_ok(s.vecs, s.stg[n])); }
}

} // verus!
