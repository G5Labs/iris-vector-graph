//! Proved counterexample for control `control_f0606_erase_keeps_ivf` (F-0606, HD-0601), compiled only with it.
//!
//! The live trace breadth-a-live-06-vectors / intent-a-hd0601-index-erasure: a vector of graph 0 is stored, an IVF
//! index of graph 0 is built and published, erase_graph(0) runs and names no ^IVF (Eraser.cls; GraphStores.cls:28-131);
//! ivf_search still answers the erased id with its vector. The erase is not an L1 step and L1's invariant fails.
use vstd::prelude::*;
use actors::protocol::*;
use crate::vidx_l1::*;
use crate::vidx_l2::*;

verus! {

pub open spec fn a() -> Id { (0, 1) }
pub open spec fn m1() -> Map<Id, int> { Map::<Id, int>::empty().insert(a(), 1) }
pub open spec fn k0() -> VS2 { VS2 { vecs: Map::empty(), ivf: Map::empty(), stg: Map::empty(), b: None } }
pub open spec fn k1() -> VS2 { VS2 { vecs: m1(), ..k0() } }
pub open spec fn k2() -> VS2 { VS2 { b: Some(BP { name: 0, g: 0, data: m1(), ph: BPh::Read }), ..k1() } }
pub open spec fn k3() -> VS2 {
    VS2 { stg: k2().stg.insert(0, Idx { g: 0, ent: Map::empty() }), b: Some(BP { name: 0, g: 0, data: m1(), ph: BPh::Built }), ..k2() }
}
pub open spec fn k4() -> VS2 { VS2 { stg: k3().stg.insert(0, Idx { g: 0, ent: m1() }), ..k3() } }
pub open spec fn k5() -> VS2 { VS2 { ivf: k4().ivf.insert(0, k4().stg[0]), stg: k4().stg.remove(0), b: None, ..k4() } }
pub open spec fn k6() -> VS2 { VS2 { vecs: drop_graph(k5().vecs, 0), ..k5() } }

pub proof fn counterexample_f0606()
    ensures
        init2(k0()),
        step2(k0(), VL2::Store { id: a(), v: 1 }, k1()),
        step2(k1(), VL2::BRead { name: 0, g: 0 }, k2()),
        step2(k2(), VL2::BBuild, k3()),
        step2(k3(), VL2::BAdd { batch: set![a()] }, k4()),
        step2(k4(), VL2::BPublish { name: 0 }, k5()),
        step2(k5(), VL2::Erase { g: 0 }, k6()),
        step2(k6(), VL2::Search { name: 0, ans: Some(m1()) }, k6()),
        // the erase is not an L1 step: the index of graph 0 survives it
        !step_or_stutter::<VidxL1>(absv(k5()), labv(VL2::Erase { g: 0 }), absv(k6())),
        !k6().vecs.contains_key(a()) && k6().ivf[0].ent.contains_key(a()),
        !inv1(absv(k6())),
{
    assert(k0().vecs.insert(a(), 1) == m1());
    assert(of_graph(m1(), 0) =~= m1());
    assert(step2(k1(), VL2::BRead { name: 0, g: 0 }, k2()));
    assert(step2(k2(), VL2::BBuild, k3()));
    assert(Map::<Id, int>::empty().union_prefer_right(m1().restrict(set![a()])) =~= m1());
    assert(step2(k3(), VL2::BAdd { batch: set![a()] }, k4()));
    assert(step2(k4(), VL2::BPublish { name: 0 }, k5()));
    assert(step2(k5(), VL2::Erase { g: 0 }, k6()));
    assert(k6().ivf[0].ent == m1());
    assert(!k6().vecs.contains_key(a())) by { assert(!m1().dom().filter(|i: Id| i.0 != 0).contains(a())); }
    assert(absv(k5()).idx.contains_key(0) && absv(k5()).idx[0].g == 0);
    assert(!drop_idx(absv(k5()).idx, 0).contains_key(0));
    assert(absv(k6()).idx.contains_key(0) && absv(k6()).idx[0].ent.contains_key(a()) && !absv(k6()).vecs.contains_key(a()));
    assert(!idx_ok(absv(k6()).vecs, absv(k6()).idx[0]));
}

} // verus!
