//! Proved counterexample for control `control_f0908_run_unchecked` (F-0908; intent-undecided, HD-0901), compiled only
//! with it.
//!
//! The live check ver-priv-r3: a user whose SELECT on every Graph_KG table was revoked called Graph.KG.Cypher.Exec.Run
//! directly over the Native API and got the plans' rows. Here: user 3 holds SELECT; it is revoked; process 5, which has
//! never passed a check for user 3, runs a plan and is answered (not an L1 step under FR-011, even in its cached form).
use vstd::prelude::*;
use actors::protocol::*;
use crate::nread_l1::*;
use crate::nread_l2::*;
use crate::nread_runs::*;

verus! {

pub open spec fn hs() -> Set<int> { Set::empty().insert(3int) }
pub open spec fn b0() -> NR2 { r0(hs(), true, true, Map::empty()) }
pub open spec fn b1() -> NR2 { p_revoke(b0(), 3) }

pub proof fn counterexample_f0908()
    ensures
        init2(b0()),
        step2(b0(), NRL2::Revoke { u: 3 }, b1()),
        !b1().held.contains(3) && !b1().chk.contains((5, 3)),
        step2(b1(), NRL2::Run { p: 5, u: 3, ans: interp2(b1()) }, after_run(b1(), 5, 3)),
        !step_or_stutter::<NrL1>(absr(b1()), labr(NRL2::Run { p: 5, u: 3, ans: interp2(b1()) }), absr(after_run(b1(), 5, 3))),
{
    lemma_r_steps(b0(), 0, 3, 5, 0, 0);
    lemma_r_steps(b1(), 0, 3, 5, 0, 0);
    assert(!b1().held.contains(3));
    assert(!authorized(absr(b1()), 5, 3));
}

} // verus!
