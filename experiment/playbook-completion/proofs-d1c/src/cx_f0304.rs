//! Proved counterexample for control `control_f0304_store_no_adopt` (F-0304), compiled only with it.
//!
//! The live trace breadth-a-live-05-temporal (p0304): store_edge over a temporal edge's marked row swallows the
//! duplicate and keeps {"temporal":true}; the store is not an L1 step (the stored edge is not explicit), and the
//! triple's last temporal delete then deletes the edge the caller stored (data loss).
use vstd::prelude::*;
use actors::protocol::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn e10() -> Ev { Ev { k: k1(), ts: 10 } }
pub open spec fn x0() -> ES2 { e0(Set::empty()) }
pub open spec fn x1() -> ES2 { p_tinsert(x0(), k1(), 10) }
pub open spec fn x2() -> ES2 { p_sstore(x1(), k1(), Q::Plain) }
pub open spec fn x3() -> ES2 { p_tdelete(x2(), k1(), 10) }

pub proof fn counterexample_f0304()
    ensures
        init2(x0()),
        step2(x0(), EL2::TInsert { k: k1(), ts: 10 }, x1()),
        step2(x1(), EL2::SStore { k: k1(), q: Q::Plain }, x2()),
        !step_or_stutter::<EdgeL1>(abse(x1()), labe(EL2::SStore { k: k1(), q: Q::Plain }), abse(x2())),
        x2().rows[k1()] is Marked,
        step2(x2(), EL2::TDelete { k: k1(), ts: 10 }, x3()),
        !x3().rows.contains_key(k1()),
{
    lemma_p_tinsert(x0(), k1(), 10);
    assert(x1().rows.contains_key(k1()) && x1().rows[k1()] is Marked);
    lemma_p_sstore(x1(), k1(), Q::Plain);
    assert(x2().rows[k1()] is Marked);
    assert(abse(x2()).edges[k1()] == Prov::Derived);
    assert(abse(x1()).edges.insert(k1(), Prov::Explicit)[k1()] == Prov::Explicit);
    assert(x2().tout.contains(e10()));
    lemma_p_tdelete(x2(), k1(), 10);
    assert(x2().tout.remove(e10()) =~= Set::<Ev>::empty());
    assert(!has_ts(x2().tout.remove(e10()), k1()));
}

} // verus!
