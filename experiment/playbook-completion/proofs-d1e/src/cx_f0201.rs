//! Proved counterexample for control `control_f0201_ekey0_guard` (F-0201), compiled only with it.
//!
//! The live probe breadth-a-live-02-mode-off (p0201_mode_off_lone_ekey1: create_edge answered True next to a lone
//! row at ekey 1 in a mode-off graph, rows [0, 1]) and breadth-a-mc-gid_mode-as-built: two parallel edges by Cypher,
//! the one at ekey 0 deleted, the mode turned off (one row), then create_edge inserts at ekey 0, which is not an L1
//! step (a single-edge writer adds only to a triple with no edge) and leaves two edges in a mode-off graph.
use vstd::prelude::*;
use actors::protocol::*;
use crate::gmode_l1::*;
use crate::gmode_l2::*;
use crate::gmode_runs::*;

verus! {

pub open spec fn c1() -> MS2 { p_on(m0(), 0) }
pub open spec fn c2() -> MS2 { p_cymode(c1(), 0) }
pub open spec fn c3() -> MS2 { p_par(c2(), 0, 0) }
pub open spec fn c4() -> MS2 { p_cymode(c3(), 0) }
pub open spec fn c5() -> MS2 { p_par(c4(), 0, 1) }
pub open spec fn c6() -> MS2 { p_del(c5(), 0) }
pub open spec fn c7() -> MS2 { p_count(c6(), 0) }
pub open spec fn c8() -> MS2 { p_kill(c7(), 0) }
pub open spec fn c9() -> MS2 { p_single(c8()) }

pub proof fn counterexample_f0201()
    ensures
        init2(m0()),
        step2(m0(), ML2::SetOn { e: 0 }, c1()),
        step2(c1(), ML2::CyMode { e: 0 }, c2()),
        step2(c2(), ML2::CyInsertPar { e: 0, k: 0 }, c3()),
        step2(c3(), ML2::CyMode { e: 0 }, c4()),
        step2(c4(), ML2::CyInsertPar { e: 0, k: 1 }, c5()),
        step2(c5(), ML2::Delete { k: 0 }, c6()),
        step2(c6(), ML2::SetOffCount { e: 0, ok: true }, c7()),
        step2(c7(), ML2::SetOffKill { e: 0 }, c8()),
        step2(c8(), ML2::Single { e: 0, added: true }, c9()),
        !step_or_stutter::<ModeL1>(absm(c8()), labm(ML2::Single { e: 0, added: true }), absm(c9())),
        !c9().gm && c9().rows.len() == 2,
{
    lemma_m_steps(m0(), 0, 0);
    lemma_m_steps(c1(), 0, 0);
    lemma_m_steps(c2(), 0, 0);
    assert(c3().rows =~= Set::empty().insert(0int));
    lemma_m_steps(c3(), 0, 1);
    lemma_m_steps(c4(), 0, 1);
    assert(c5().rows =~= Set::empty().insert(0int).insert(1int));
    lemma_m_steps(c5(), 0, 0);
    assert(c6().rows =~= Set::empty().insert(1int));
    assert(c6().shared =~= Set::<int>::empty());
    lemma_m_steps(c6(), 0, 0);
    lemma_m_steps(c7(), 0, 0);
    lemma_m_steps(c8(), 0, 0);
    assert(guard_ok(c8()));
    assert(c8().rows.contains(1));
    assert(c9().rows =~= Set::empty().insert(1int).insert(0int));
}

} // verus!
