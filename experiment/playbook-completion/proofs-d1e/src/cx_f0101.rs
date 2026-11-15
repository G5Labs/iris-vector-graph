//! Proved counterexample for control `control_f0101_removed_unchecked` (F-0101), compiled only with it.
//!
//! The probe breadth-a-probe-local-0101-0601 (every drop and delete failing: the view and the second SqlProc item of
//! a class reported removed): a legacy view whose DROP VIEW fails is reported removed; a shipped class whose delete
//! fails is reported not removed for its first item and removed for its second. Each report is not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::inst_l1::*;
use crate::inst_l2::*;
use crate::inst_runs::*;

verus! {

pub open spec fn c0() -> IS2 { i0(false, Set::empty(), Set::empty().insert(5int), Set::empty().insert(7int)) }
pub open spec fn c1() -> IS2 { p_rmview(c0(), 5, false) }
pub open spec fn c2() -> IS2 { p_rmfirst(c1(), 7, false) }

pub proof fn counterexample_f0101()
    ensures
        init2(c0()),
        step2(c0(), IL2::RmView { v: 5, ok: false, reported: true }, c1()),
        c1().views.contains(5),
        !step_or_stutter::<InstL1>(absi(c0()), labi(IL2::RmView { v: 5, ok: false, reported: true }), absi(c1())),
        step2(c1(), IL2::RmFirst { c: 7, ok: false, reported: false }, c2()),
        step2(c2(), IL2::RmLater { c: 7, reported: true }, c2()),
        c2().lcls.contains(7),
        !step_or_stutter::<InstL1>(absi(c2()), labi(IL2::RmLater { c: 7, reported: true }), absi(c2())),
{
    lemma_i_steps(c0(), 1, false, true, 5);
    lemma_i_steps(c1(), 1, false, true, 7);
    lemma_i_steps(c2(), 1, false, true, 7);
}

} // verus!
