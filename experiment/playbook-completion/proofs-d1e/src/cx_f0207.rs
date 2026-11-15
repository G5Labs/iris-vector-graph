//! Proved counterexample for control `control_f0207_set_off_unlocked` (F-0207), compiled only with it.
//!
//! The explorer family breadth-a-mc-gid_mode-as-built (F-0207, reproduced in the model; GraphMode.cls:26-45 counts and
//! kills with no lock): engine 0's Set(g, 0) counts one edge; engine 1's Cypher CREATE reads multigraph mode and adds
//! a parallel edge; engine 0 kills the mode, which is not an L1 step (the mode is turned off over parallel edges).
use vstd::prelude::*;
use actors::protocol::*;
use crate::gmode_l1::*;
use crate::gmode_l2::*;
use crate::gmode_runs::*;

verus! {

pub open spec fn c1() -> MS2 { p_on(m0(), 0) }
pub open spec fn c2() -> MS2 { p_cymode(c1(), 1) }
pub open spec fn c3() -> MS2 { p_par(c2(), 1, 0) }
pub open spec fn c4() -> MS2 { p_count(c3(), 0) }
pub open spec fn c5() -> MS2 { p_cymode(c4(), 1) }
pub open spec fn c6() -> MS2 { p_par(c5(), 1, 1) }
pub open spec fn c7() -> MS2 { p_kill(c6(), 0) }

pub proof fn counterexample_f0207()
    ensures
        init2(m0()),
        step2(m0(), ML2::SetOn { e: 0 }, c1()),
        step2(c1(), ML2::CyMode { e: 1 }, c2()),
        step2(c2(), ML2::CyInsertPar { e: 1, k: 0 }, c3()),
        step2(c3(), ML2::SetOffCount { e: 0, ok: true }, c4()),
        step2(c4(), ML2::CyMode { e: 1 }, c5()),
        step2(c5(), ML2::CyInsertPar { e: 1, k: 1 }, c6()),
        step2(c6(), ML2::SetOffKill { e: 0 }, c7()),
        !step_or_stutter::<ModeL1>(absm(c6()), labm(ML2::SetOffKill { e: 0 }), absm(c7())),
        !c7().gm && c7().rows.len() == 2,
{
    lemma_m_steps(m0(), 0, 0);
    lemma_m_steps(c1(), 1, 0);
    lemma_m_steps(c2(), 1, 0);
    assert(c3().rows =~= Set::empty().insert(0int));
    lemma_m_steps(c3(), 0, 0);
    lemma_m_steps(c4(), 1, 1);
    assert(c5().cy[1]);
    lemma_m_steps(c5(), 1, 1);
    assert(c6().rows =~= Set::empty().insert(0int).insert(1int));
    lemma_m_steps(c6(), 0, 1);
}

} // verus!
