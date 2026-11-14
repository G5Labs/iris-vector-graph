//! Proved counterexample for control `control_f0902_crc_identity` (F-0902), compiled only with it.
//!
//! The live check b-09-f0902-collision: relationships b09_xxaymshxlzd-[:B09T]->b09_hub and
//! b09_xwcsojebldf-[:B09T]->b09_hub share a $ZCRC; the SQL path answered [[2]], the interpreter [[0]]. Here:
//! relationships 1 and 2 share checksum 9; the interpreter's answer lacks the pair (1, 2) the SQL path has (not an L1
//! step: the native answer is the SQL path's).
use vstd::prelude::*;
use actors::protocol::*;
use crate::nread_l1::*;
use crate::nread_l2::*;
use crate::nread_runs::*;

verus! {

pub open spec fn cm() -> Map<int, int> { Map::empty().insert(1int, 9int).insert(2int, 9int) }
pub open spec fn hs() -> Set<int> { Set::empty().insert(3int) }
pub open spec fn a0() -> NR2 { r0(hs(), true, true, cm()) }
pub open spec fn a1() -> NR2 { p_tbegin(a0()) }
pub open spec fn a2() -> NR2 { p_tadd(a1(), 1) }
pub open spec fn a3() -> NR2 { p_tadd(a2(), 2) }
pub open spec fn a4() -> NR2 { p_tcommit(a3()) }

pub proof fn counterexample_f0902()
    ensures
        init2(a0()),
        step2(a0(), NRL2::TBegin, a1()),
        step2(a1(), NRL2::TAdd { e: 1 }, a2()),
        step2(a2(), NRL2::TAdd { e: 2 }, a3()),
        step2(a3(), NRL2::TCommit, a4()),
        step2(a4(), NRL2::Run { p: 0, u: 3, ans: interp2(a4()) }, after_run(a4(), 0, 3)),
        pairs(a4().rels).contains((1, 2)) && !interp2(a4()).contains((1, 2)),
        !step_or_stutter::<NrL1>(absr(a4()), labr(NRL2::Run { p: 0, u: 3, ans: interp2(a4()) }), absr(after_run(a4(), 0, 3))),
{
    lemma_r_steps(a0(), 1, 3, 0, 0, 0);
    lemma_r_steps(a1(), 1, 3, 0, 0, 0);
    lemma_r_steps(a2(), 2, 3, 0, 0, 0);
    lemma_r_steps(a3(), 2, 3, 0, 0, 0);
    assert(a4().held.contains(3));
    lemma_r_steps(a4(), 2, 3, 0, 0, 0);
    assert(a4().rels.contains(1) && a4().rels.contains(2));
    assert(crcof(a4(), 1) == crcof(a4(), 2));
    assert(pairs(a4().rels).contains((1, 2)));
    assert(!interp2(a4()).contains((1, 2)));
}

} // verus!
