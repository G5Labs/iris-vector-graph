//! Non-vacuity of the reviewed nread model (compiled without its controls): relationships 1 and 2 share a checksum and
//! are told apart; a writer's open transaction adds 3, seen by the native read and gone after its rollback; process 0
//! of user 3 passes the check and keeps reading after the revoke (FR-011's cache) while process 5 is refused; shadow
//! mode raises on a native exception; the gate stays closed in the edge-only state and opens with both indexes.
use vstd::prelude::*;
use crate::nread_l1::*;
use crate::nread_l2::*;
use crate::nread_runs::*;

verus! {

pub open spec fn cm() -> Map<int, int> { Map::empty().insert(1int, 9int).insert(2int, 9int) }
pub open spec fn hs() -> Set<int> { Set::empty().insert(3int) }
pub open spec fn w0() -> NR2 { r0(hs(), true, true, cm()) }
pub open spec fn w1() -> NR2 { p_tbegin(w0()) }
pub open spec fn w2() -> NR2 { p_tadd(w1(), 1) }
pub open spec fn w3() -> NR2 { p_tadd(w2(), 2) }
pub open spec fn w4() -> NR2 { p_tcommit(w3()) }
pub open spec fn w5() -> NR2 { after_run(w4(), 0, 3) }
pub open spec fn w6() -> NR2 { p_tbegin(w5()) }
pub open spec fn w7() -> NR2 { p_tadd(w6(), 3) }
pub open spec fn w8() -> NR2 { p_trollback(w7()) }
pub open spec fn w9() -> NR2 { p_revoke(w8(), 3) }
pub open spec fn e0() -> NR2 { r0(hs(), true, false, Map::empty()) }

pub proof fn witness_nread()
    ensures
        init2(w0()),
        step2(w0(), NRL2::TBegin, w1()),
        step2(w1(), NRL2::TAdd { e: 1 }, w2()),
        step2(w2(), NRL2::TAdd { e: 2 }, w3()),
        step2(w3(), NRL2::TCommit, w4()),
        step2(w4(), NRL2::Run { p: 0, u: 3, ans: pairs(w4().rels) }, w5()),
        pairs(w4().rels).contains((1, 2)),
        step2(w5(), NRL2::TBegin, w6()),
        step2(w6(), NRL2::TAdd { e: 3 }, w7()),
        step2(w7(), NRL2::Run { p: 0, u: 3, ans: pairs(w7().rels) }, w7()),
        pairs(w7().rels).contains((3, 1)),
        step2(w7(), NRL2::TRollback, w8()),
        !w8().rels.contains(3),
        step2(w8(), NRL2::Revoke { u: 3 }, w9()),
        step2(w9(), NRL2::Run { p: 0, u: 3, ans: pairs(w9().rels) }, w9()),
        !run_ok(w9(), 5, 3),
        step2(w9(), NRL2::ShadowRun { p: 0, u: 3, nres: None, ans: None, compared: false }, w9()),
        !gate(e0()) && gate(w0()),
{
    lemma_r_steps(w0(), 1, 3, 0, 0, 0);
    lemma_r_steps(w1(), 1, 3, 0, 0, 0);
    lemma_r_steps(w2(), 2, 3, 0, 0, 0);
    lemma_r_steps(w3(), 2, 3, 0, 0, 0);
    assert(w4().held.contains(3));
    lemma_r_steps(w4(), 2, 3, 0, 0, 0);
    assert(pairs(w4().rels).contains((1, 2)));
    assert(w5().chk.contains((0, 3)));
    lemma_r_steps(w5(), 3, 3, 0, 0, 0);
    lemma_r_steps(w6(), 3, 3, 0, 0, 0);
    lemma_r_steps(w7(), 3, 3, 0, 0, 0);
    assert(w7().chk.contains((0, 3)));
    assert(after_run(w7(), 0, 3) == w7()) by { assert(w7().chk.insert((0, 3)) =~= w7().chk); }
    assert(w7().rels.contains(3) && w7().rels.contains(1));
    assert(pairs(w7().rels).contains((3, 1)));
    assert(w8().rels == w5().rels);
    assert(!w5().rels.contains(3));
    lemma_r_steps(w8(), 3, 3, 0, 0, 0);
    assert(w9().chk.contains((0, 3)));
    assert(after_run(w9(), 0, 3) == w9()) by { assert(w9().chk.insert((0, 3)) =~= w9().chk); }
    lemma_r_steps(w9(), 3, 3, 0, 0, 0);
    assert(!w9().held.contains(3) && !w9().chk.contains((5, 3)));
}

} // verus!
