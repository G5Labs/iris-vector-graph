//! Non-vacuity of the reviewed bulk model (compiled without its control): a call whose two chunks load (a reader sees
//! nothing of the batch meanwhile) and commit together; a call whose second chunk fails and whose SQL fallback commits
//! the whole batch; a call whose fallback raises and commits nothing.
use vstd::prelude::*;
use crate::bulk_l2::*;
use crate::bulk_runs::*;

verus! {

pub open spec fn s1() -> Set<int> { Set::empty().insert(1int) }
pub open spec fn s2() -> Set<int> { Set::empty().insert(2int) }
pub open spec fn s12() -> Set<int> { s1().union(s2()) }
pub open spec fn w1() -> BS2 { p_begin(b0(), s1(), s2()) }
pub open spec fn w2() -> BS2 { p_chunkok(w1()) }
pub open spec fn w3() -> BS2 { p_chunkok(w2()) }
pub open spec fn w4() -> BS2 { p_commit(w3()) }
pub open spec fn w5() -> BS2 { p_begin(w4(), s1(), s2()) }
pub open spec fn w6() -> BS2 { p_chunkok(w5()) }
pub open spec fn w7() -> BS2 { p_chunkfail(w6()) }
pub open spec fn w8() -> BS2 { p_fallbackok(w7()) }
pub open spec fn w9() -> BS2 { p_begin(b0(), s1(), s2()) }
pub open spec fn w10() -> BS2 { p_chunkfail(w9()) }
pub open spec fn w11() -> BS2 { p_end(w10()) }

pub proof fn witness_bulk()
    ensures
        init2(b0()),
        step2(b0(), BL2::Begin { a: s1(), b: s2() }, w1()),
        step2(w1(), BL2::ChunkOk, w2()),
        step2(w2(), BL2::Read { rows: Set::empty() }, w2()),
        step2(w2(), BL2::ChunkOk, w3()),
        step2(w3(), BL2::Commit { batch: s12() }, w4()),
        w4().committed == s12(),
        step2(w4(), BL2::Begin { a: s1(), b: s2() }, w5()),
        step2(w5(), BL2::ChunkOk, w6()),
        step2(w6(), BL2::ChunkFail, w7()),
        step2(w7(), BL2::FallbackOk { batch: s12() }, w8()),
        w8().committed == s12(),
        step2(b0(), BL2::Begin { a: s1(), b: s2() }, w9()),
        step2(w9(), BL2::ChunkFail, w10()),
        step2(w10(), BL2::FallbackFail { batch: s12() }, w11()),
        w11().committed == Set::<int>::empty(),
{
    lemma_b_steps(b0(), s1(), s2());
    lemma_b_steps(w1(), s1(), s2());
    lemma_b_steps(w2(), s1(), s2());
    lemma_b_steps(w3(), s1(), s2());
    assert(w3().written =~= s12());
    assert(w4().committed =~= s12());
    lemma_b_steps(w4(), s1(), s2());
    lemma_b_steps(w5(), s1(), s2());
    lemma_b_steps(w6(), s1(), s2());
    lemma_b_steps(w7(), s1(), s2());
    assert(w8().committed =~= s12());
    lemma_b_steps(w9(), s1(), s2());
    lemma_b_steps(w10(), s1(), s2());
}

} // verus!
