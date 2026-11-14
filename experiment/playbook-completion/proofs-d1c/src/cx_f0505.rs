//! Proved counterexample for control `control_f0505_marker_predicate` (F-0505), compiled only with it.
//!
//! The live trace breadth-a-live-05-temporal (p0505): an explicit create_edge with qualifiers {"temporal": 1}, a
//! temporal edge on the same triple, and its delete: IsTemporalMarked's `%Get("temporal") = 1` accepts the explicit
//! row, so the last temporal delete deletes it. The delete is not an L1 step (an explicit edge removed by the temporal
//! side).
use vstd::prelude::*;
use actors::protocol::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn e10() -> Ev { Ev { k: k1(), ts: 10 } }
pub open spec fn x0() -> ES2 { e0(Set::empty()) }
pub open spec fn x1() -> ES2 { p_cinsert(x0(), 0, k1(), Q::TOne) }
pub open spec fn x2() -> ES2 { p_tinsert(x1(), k1(), 10) }
pub open spec fn x3() -> ES2 { p_tdelete(x2(), k1(), 10) }

pub proof fn counterexample_f0505()
    ensures
        init2(x0()),
        step2(x0(), EL2::CInsert { c: 0, k: k1(), q: Q::TOne, res: Some(true) }, x1()),
        step2(x1(), EL2::TInsert { k: k1(), ts: 10 }, x2()),
        step2(x2(), EL2::TDelete { k: k1(), ts: 10 }, x3()),
        x2().rows[k1()] is TOne,
        !step_or_stutter::<EdgeL1>(abse(x2()), labe(EL2::TDelete { k: k1(), ts: 10 }), abse(x3())),
        !x3().rows.contains_key(k1()),
{
    lemma_p_cinsert(x0(), 0, k1(), Q::TOne);
    assert(r_cinsert(x0(), k1()) == Some(true));
    assert(x1().out.contains(k1()));
    lemma_p_tinsert(x1(), k1(), 10);
    assert(x2().rows[k1()] is TOne);
    assert(x2().tout.contains(e10()));
    lemma_p_tdelete(x2(), k1(), 10);
    assert(x2().tout.remove(e10()) =~= Set::<Ev>::empty());
    assert(!has_ts(x2().tout.remove(e10()), k1()));
    assert(!x3().rows.contains_key(k1()));
    let kept = keep_supported(abse(x2()).edges, x2().tout.remove(e10()));
    assert(abse(x2()).edges[k1()] == Prov::Explicit);
    assert(abse(x2()).edges.dom().filter(|k: K| !(abse(x2()).edges[k] is Derived && !has_ts(x2().tout.remove(e10()), k))).contains(k1()));
    assert(kept.contains_key(k1()));
    assert(!abse(x3()).edges.contains_key(k1()));
}

} // verus!
