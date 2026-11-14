//! Proved counterexample for control `control_fc0501_refused_write_partial` (F-C0501), compiled only with it.
//!
//! The live trace breadth-a-live-05-partial (pC0501): create_edge_temporal with a predicate the edge row refuses
//! (SQLCODE -104) raised GraphWriteError, yet ^KG("tout"/"tin"/"bucket"/"tagg") hold the edge and no row exists
//! (WriteStores runs no transaction). The refused write is not an L1 step (it wrote something), and L1's invariant
//! fails (a temporal edge of a structural predicate with no structural edge).
use vstd::prelude::*;
use actors::protocol::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn e10() -> Ev { Ev { k: k1(), ts: 10 } }
pub open spec fn x0() -> ES2 { e0(Set::empty()) }
pub open spec fn x1() -> ES2 { p_trefuse(x0(), k1(), 10) }

pub proof fn counterexample_fc0501()
    ensures
        init2(x0()),
        step2(x0(), EL2::TRefuse { k: k1(), ts: 10 }, x1()),
        !step_or_stutter::<EdgeL1>(abse(x0()), labe(EL2::TRefuse { k: k1(), ts: 10 }), abse(x1())),
        x1().tout.contains(e10()) && x1().tin.contains(e10()) && !x1().rows.contains_key(k1()),
        !inv1(abse(x1())),
{
    lemma_p_trefuse(x0(), k1(), 10);
    assert(x1().tout.contains(e10()));
    assert(!x0().tout.contains(e10()));
    assert(!abse(x1()).edges.contains_key(k1()));
    assert(abse(x1()).tev.contains(e10()) && structural(abse(x1()).reg, e10().k));
}

} // verus!
