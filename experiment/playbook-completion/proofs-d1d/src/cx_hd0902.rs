//! Proved counterexample for control `control_hd0902_shadow_swallows_native_error` (HD-0902), compiled only with it.
//!
//! The live probe intent-a-hd0902-shadow-native-exception: in shadow mode an injected native exception gave the SQL
//! rows, no raise, one warning; the native-answer counter did not move. Here: in shadow mode the native path raises; the
//! read answers the SQL rows uncompared (not an L1 step under HD-0902's working answer: a shadow answer was compared).
use vstd::prelude::*;
use actors::protocol::*;
use crate::nread_l1::*;
use crate::nread_l2::*;
use crate::nread_runs::*;

verus! {

pub open spec fn hs() -> Set<int> { Set::empty().insert(3int) }
pub open spec fn d0() -> NR2 { r0(hs(), true, true, Map::empty()) }

pub proof fn counterexample_hd0902()
    ensures
        init2(d0()),
        step2(d0(), NRL2::ShadowRun { p: 0, u: 3, nres: None, ans: Some(pairs(d0().rels)), compared: false }, d0()),
        !step_or_stutter::<NrL1>(absr(d0()), labr(NRL2::ShadowRun { p: 0, u: 3, nres: None, ans: Some(pairs(d0().rels)), compared: false }), absr(d0())),
{
    lemma_r_steps(d0(), 0, 3, 0, 0, 0);
    assert(d0().held.contains(3));
}

} // verus!
