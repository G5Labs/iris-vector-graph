//! Proved counterexample for control `control_hd0302_delete_removes_row` (HD-0302), compiled only with it.
//!
//! The live trace intent-a-hd0302-temporal-row-delete: delete_edge removes the marked row (case A) and a row
//! create_edge adopted (case B), with their ^KG("out") entries, while get_edges_in_window still returns the triple's
//! timestamp. Each delete is not an L1 step, and L1's invariant fails (a structural temporal edge with no structural
//! edge: adjacency readers lose an edge the temporal index holds).
use vstd::prelude::*;
use actors::protocol::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn e10() -> Ev { Ev { k: k1(), ts: 10 } }
pub open spec fn x0() -> ES2 { e0(Set::empty()) }
pub open spec fn x1() -> ES2 { p_tinsert(x0(), k1(), 10) }
pub open spec fn xa() -> ES2 { p_ddelete(x1(), k1()) }
pub open spec fn y2() -> ES2 { p_cinsert(x1(), 0, k1(), Q::Plain) }
pub open spec fn yb() -> ES2 { p_ddelete(y2(), k1()) }

pub proof fn counterexample_hd0302()
    ensures
        init2(x0()),
        step2(x0(), EL2::TInsert { k: k1(), ts: 10 }, x1()),
        // case A: the marked row
        step2(x1(), EL2::DDelete { k: k1() }, xa()),
        !step_or_stutter::<EdgeL1>(abse(x1()), labe(EL2::DDelete { k: k1() }), abse(xa())),
        xa().tout.contains(e10()) && !xa().rows.contains_key(k1()) && !xa().out.contains(k1()),
        !inv1(abse(xa())),
        // case B: the row create_edge adopted
        step2(x1(), EL2::CInsert { c: 0, k: k1(), q: Q::Plain, res: Some(true) }, y2()),
        y2().rows[k1()] is Plain,
        step2(y2(), EL2::DDelete { k: k1() }, yb()),
        !step_or_stutter::<EdgeL1>(abse(y2()), labe(EL2::DDelete { k: k1() }), abse(yb())),
        yb().tout.contains(e10()) && !yb().rows.contains_key(k1()),
        !inv1(abse(yb())),
{
    lemma_p_tinsert(x0(), k1(), 10);
    assert(x1().tout.contains(e10()));
    assert(has_ts(x1().tout, k1()));
    lemma_p_ddelete(x1(), k1());
    assert(supported(abse(x1()), k1()));
    assert(abse(x1()).edges.insert(k1(), Prov::Derived).contains_key(k1()));
    assert(!abse(xa()).edges.contains_key(k1()));
    assert(abse(xa()).tev.contains(e10()) && structural(abse(xa()).reg, e10().k));
    assert(x1().rows.contains_key(k1()) && x1().rows[k1()] is Marked);
    assert(r_cinsert(x1(), k1()) == Some(true));
    lemma_p_cinsert(x1(), 0, k1(), Q::Plain);
    assert(y2().tout.contains(e10()));
    assert(has_ts(y2().tout, k1()));
    lemma_p_ddelete(y2(), k1());
    assert(supported(abse(y2()), k1()));
    assert(abse(y2()).edges.insert(k1(), Prov::Derived).contains_key(k1()));
    assert(!abse(yb()).edges.contains_key(k1()));
    assert(abse(yb()).tev.contains(e10()) && structural(abse(yb()).reg, e10().k));
}

} // verus!
