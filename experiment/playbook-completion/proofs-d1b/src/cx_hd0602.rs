//! Proved counterexample for control `control_hd0602_inplace_build` (HD-0602), compiled only with it.
//!
//! The live trace intent-a-hd0602-ivf-partial: an IVF index over graph 0's two vectors is built and published; a
//! rebuild of the same name kills ^IVF(name) and refills it in place (IVFIndex.cls:8, 237-276); a search during the
//! rebuild answers no vector (not "unavailable"); the rebuild stops after one batch and leaves an index answering one
//! of the two vectors. The rebuild's kill is not an L1 step (a stutter must leave the published index unchanged).
use vstd::prelude::*;
use actors::protocol::*;
use crate::vidx_l1::*;
use crate::vidx_l2::*;

verus! {

pub open spec fn a() -> Id { (0, 1) }
pub open spec fn b() -> Id { (0, 2) }
pub open spec fn ma() -> Map<Id, int> { Map::<Id, int>::empty().insert(a(), 1) }
pub open spec fn mab() -> Map<Id, int> { ma().insert(b(), 2) }
pub open spec fn bp(ph: BPh) -> Option<BP> { Some(BP { name: 0, g: 0, data: mab(), ph }) }
pub open spec fn p0() -> VS2 { VS2 { vecs: Map::empty(), ivf: Map::empty(), stg: Map::empty(), b: None } }
pub open spec fn p1() -> VS2 { VS2 { vecs: ma(), ..p0() } }
pub open spec fn p2() -> VS2 { VS2 { vecs: mab(), ..p0() } }
pub open spec fn p3() -> VS2 { VS2 { b: bp(BPh::Read), ..p2() } }
pub open spec fn p4() -> VS2 { VS2 { ivf: p3().ivf.insert(0, Idx { g: 0, ent: Map::empty() }), b: bp(BPh::Built), ..p3() } }
pub open spec fn p5() -> VS2 { VS2 { ivf: p4().ivf.insert(0, Idx { g: 0, ent: mab() }), ..p4() } }
pub open spec fn p6() -> VS2 { VS2 { b: None, ..p5() } }
pub open spec fn p7() -> VS2 { VS2 { b: bp(BPh::Read), ..p6() } }
pub open spec fn p8() -> VS2 { VS2 { ivf: p7().ivf.insert(0, Idx { g: 0, ent: Map::empty() }), b: bp(BPh::Built), ..p7() } }
pub open spec fn p9() -> VS2 { VS2 { ivf: p8().ivf.insert(0, Idx { g: 0, ent: ma() }), ..p8() } }
pub open spec fn p10() -> VS2 { VS2 { b: None, ..p9() } }

pub proof fn counterexample_hd0602()
    ensures
        init2(p0()),
        step2(p0(), VL2::Store { id: a(), v: 1 }, p1()),
        step2(p1(), VL2::Store { id: b(), v: 2 }, p2()),
        step2(p2(), VL2::BRead { name: 0, g: 0 }, p3()),
        step2(p3(), VL2::BBuild, p4()),
        step2(p4(), VL2::BAdd { batch: set![a(), b()] }, p5()),
        step2(p5(), VL2::BPublish { name: 0 }, p6()),
        step2(p6(), VL2::Search { name: 0, ans: Some(mab()) }, p6()),
        step2(p6(), VL2::BRead { name: 0, g: 0 }, p7()),
        step2(p7(), VL2::BBuild, p8()),
        // the rebuild's kill is not an L1 step: the published complete index is gone
        !step_or_stutter::<VidxL1>(absv(p7()), labv(VL2::BBuild), absv(p8())),
        step2(p8(), VL2::Search { name: 0, ans: Some(Map::empty()) }, p8()),
        step2(p8(), VL2::BAdd { batch: set![a()] }, p9()),
        step2(p9(), VL2::BStop { name: 0 }, p10()),
        // the stopped rebuild leaves an index answering one of the graph's two vectors, without error
        step2(p10(), VL2::Search { name: 0, ans: Some(ma()) }, p10()),
        p10().vecs.contains_key(b()) && !ma().contains_key(b()),
{
    assert(p0().vecs.insert(a(), 1) == ma());
    assert(of_graph(mab(), 0) =~= mab());
    assert(step2(p2(), VL2::BRead { name: 0, g: 0 }, p3()));
    assert(step2(p3(), VL2::BBuild, p4()));
    assert(Map::<Id, int>::empty().union_prefer_right(mab().restrict(set![a(), b()])) =~= mab());
    assert(step2(p4(), VL2::BAdd { batch: set![a(), b()] }, p5()));
    assert(p5().ivf[0].ent == mab());
    assert(step2(p5(), VL2::BPublish { name: 0 }, p6()));
    assert(step2(p6(), VL2::BRead { name: 0, g: 0 }, p7()));
    assert(step2(p7(), VL2::BBuild, p8()));
    assert(p7().ivf[0].ent.contains_key(a()) && !p8().ivf[0].ent.contains_key(a()));
    assert(absv(p8()) != absv(p7()));
    assert(Map::<Id, int>::empty().union_prefer_right(mab().restrict(set![a()])) =~= ma());
    assert(step2(p8(), VL2::BAdd { batch: set![a()] }, p9()));
    assert(step2(p9(), VL2::BStop { name: 0 }, p10()));
    assert(p10().ivf[0].ent == ma());
}

} // verus!
