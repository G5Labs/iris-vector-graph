//! Proved counterexample for control `control_f0507_purge_keeps_rows` (F-0507), compiled only with it.
//!
//! The live trace breadth-a-live-05-purge (p0507): TemporalIndex.Purge kills every temporal global; the marked row (and
//! its ^KG("out") entry) survives with no timestamp. The purge is not an L1 step, and L1's invariant fails (a derived
//! edge without time).
use vstd::prelude::*;
use actors::protocol::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn x0() -> ES2 { e0(Set::empty()) }
pub open spec fn x1() -> ES2 { p_tinsert(x0(), k1(), 10) }
pub open spec fn x2() -> ES2 { p_tpurge(x1()) }

pub proof fn counterexample_f0507()
    ensures
        init2(x0()),
        step2(x0(), EL2::TInsert { k: k1(), ts: 10 }, x1()),
        step2(x1(), EL2::TPurge, x2()),
        !step_or_stutter::<EdgeL1>(abse(x1()), labe(EL2::TPurge), abse(x2())),
        x2().rows[k1()] is Marked && x2().out.contains(k1()) && x2().tout == Set::<Ev>::empty(),
        !inv1(abse(x2())),
{
    lemma_p_tinsert(x0(), k1(), 10);
    lemma_p_tpurge(x1());
    assert(x2().rows.contains_key(k1()) && x2().rows[k1()] is Marked);
    assert(abse(x2()).edges.contains_key(k1()) && abse(x2()).edges[k1()] is Derived);
    assert(!has_ts(Set::<Ev>::empty(), k1()));
    assert(!keep_supported(abse(x1()).edges, Set::<Ev>::empty()).contains_key(k1()));
    assert(!supported(abse(x2()), k1()));
}

} // verus!
