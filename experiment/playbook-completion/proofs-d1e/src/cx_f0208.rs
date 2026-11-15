//! Proved counterexample for control `control_f0208_mode_cached_forever` (F-0208), compiled only with it.
//!
//! The live probe breadth-a-live-02-identity (p0208_stale_mode_cache: engine 2 turned the mode off, engine 1's cached
//! "on" wrote a parallel edge into the mode-off graph, rows [0, 1]) and breadth-a-mc-gid_mode-as-built: engine 1
//! caches multigraph mode on its first CREATE; engine 0 turns the mode off; engine 1's next CREATE reads its cache and
//! inserts a parallel edge, which is not an L1 step (only multigraph mode adds a parallel edge).
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
pub open spec fn c5() -> MS2 { p_kill(c4(), 0) }
pub open spec fn c6() -> MS2 { p_cymode(c5(), 1) }
pub open spec fn c7() -> MS2 { p_par(c6(), 1, 1) }

pub proof fn counterexample_f0208()
    ensures
        init2(m0()),
        step2(m0(), ML2::SetOn { e: 0 }, c1()),
        step2(c1(), ML2::CyMode { e: 1 }, c2()),
        step2(c2(), ML2::CyInsertPar { e: 1, k: 0 }, c3()),
        step2(c3(), ML2::SetOffCount { e: 0, ok: true }, c4()),
        step2(c4(), ML2::SetOffKill { e: 0 }, c5()),
        !c5().gm,
        step2(c5(), ML2::CyMode { e: 1 }, c6()),
        step2(c6(), ML2::CyInsertPar { e: 1, k: 1 }, c7()),
        !step_or_stutter::<ModeL1>(absm(c6()), labm(ML2::CyInsertPar { e: 1, k: 1 }), absm(c7())),
        !c7().gm && c7().rows.len() == 2,
{
    lemma_m_steps(m0(), 0, 0);
    lemma_m_steps(c1(), 1, 0);
    lemma_m_steps(c2(), 1, 0);
    assert(c3().rows =~= Set::empty().insert(0int));
    assert(c3().shared =~= Set::<int>::empty());
    lemma_m_steps(c3(), 0, 0);
    lemma_m_steps(c4(), 0, 0);
    assert(c5().cache.contains_key(1) && c5().cache[1]);
    lemma_m_steps(c5(), 1, 1);
    assert(c6().cy[1]);
    lemma_m_steps(c6(), 1, 1);
    assert(c7().rows =~= Set::empty().insert(0int).insert(1int));
}

} // verus!
