//! Non-vacuity of the module 06 index model (compiled without the index controls): a vector of graph 0 is stored,
//! an index is built in its staging generation and published whole, searches answer it, a rebuild runs and stops
//! without searches seeing it, and erase_graph(0) drops the index (a search then answers "unavailable").
use vstd::prelude::*;
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
pub open spec fn k6() -> VS2 { VS2 { b: Some(BP { name: 0, g: 0, data: m1(), ph: BPh::Read }), ..k5() } }
pub open spec fn k7() -> VS2 {
    VS2 { stg: k6().stg.insert(0, Idx { g: 0, ent: Map::empty() }), b: Some(BP { name: 0, g: 0, data: m1(), ph: BPh::Built }), ..k6() }
}
pub open spec fn k8() -> VS2 { VS2 { b: None, ..k7() } }
pub open spec fn k9() -> VS2 { VS2 { vecs: drop_graph(k8().vecs, 0), ivf: drop_idx(k8().ivf, 0), stg: drop_idx(k8().stg, 0), ..k8() } }

pub proof fn witness_vidx()
    ensures
        init2(k0()),
        step2(k0(), VL2::Store { id: a(), v: 1 }, k1()),
        step2(k1(), VL2::BRead { name: 0, g: 0 }, k2()),
        step2(k2(), VL2::BBuild, k3()),
        step2(k3(), VL2::BAdd { batch: set![a()] }, k4()),
        step2(k4(), VL2::BPublish { name: 0 }, k5()),
        step2(k5(), VL2::Search { name: 0, ans: Some(m1()) }, k5()),
        step2(k5(), VL2::BRead { name: 0, g: 0 }, k6()),
        step2(k6(), VL2::BBuild, k7()),
        step2(k7(), VL2::Search { name: 0, ans: Some(m1()) }, k7()),
        step2(k7(), VL2::BStop { name: 0 }, k8()),
        step2(k8(), VL2::Erase { g: 0 }, k9()),
        step2(k9(), VL2::Search { name: 0, ans: None }, k9()),
{
    assert(k0().vecs.insert(a(), 1) == m1());
    assert(of_graph(m1(), 0) =~= m1());
    assert(step2(k1(), VL2::BRead { name: 0, g: 0 }, k2()));
    assert(step2(k2(), VL2::BBuild, k3()));
    assert(Map::<Id, int>::empty().union_prefer_right(m1().restrict(set![a()])) =~= m1());
    assert(step2(k3(), VL2::BAdd { batch: set![a()] }, k4()));
    assert(step2(k4(), VL2::BPublish { name: 0 }, k5()));
    assert(k5().ivf[0].ent == m1());
    assert(step2(k5(), VL2::BRead { name: 0, g: 0 }, k6()));
    assert(step2(k6(), VL2::BBuild, k7()));
    assert(step2(k8(), VL2::Erase { g: 0 }, k9()));
    assert(!k9().ivf.contains_key(0)) by { assert(!k8().ivf.dom().filter(|n: nat| k8().ivf[n].g != 0).contains(0)); }
}

} // verus!
