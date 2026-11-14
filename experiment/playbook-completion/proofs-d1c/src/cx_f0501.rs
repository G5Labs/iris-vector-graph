//! Proved counterexample for control `control_f0501_update_counted_again` (F-0501), compiled only with it.
//!
//! The live trace breadth-a-live-05-temporal (p0501): one edge of weight 1, then an update of the same coordinate to
//! weight 5: the whole-bucket aggregate answers count 2, sum 6 for one edge of weight 5 (not an L1 step); after the
//! edge's delete the bucket counter still answers 1 for an empty bucket (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::tagg_l1::*;
use crate::tagg_l2::*;
use crate::tagg_runs::*;

verus! {

pub open spec fn q1() -> TS2 { p_write(t0(), 0, 1, Mode::Insert) }
pub open spec fn q2() -> TS2 { p_write(q1(), 0, 5, Mode::Update) }
pub open spec fn q3() -> TS2 { p_delete(q2(), 0) }

pub proof fn counterexample_f0501()
    ensures
        init2(t0()),
        step2(t0(), TL2::Write { ts: 0, w: 1, mode: Mode::Insert }, q1()),
        step2(q1(), TL2::Write { ts: 0, w: 5, mode: Mode::Update }, q2()),
        q2().count == 2 && q2().sum == 6 && q2().tout[0] == 5,
        step2(q2(), TL2::ReadAgg { count: 2, sum: 6 }, q2()),
        !step_or_stutter::<TaggL1>(abst(q2()), labt(TL2::ReadAgg { count: 2, sum: 6 }), abst(q2())),
        step2(q2(), TL2::Delete { ts: 0 }, q3()),
        q3().bucket == 1 && q3().tout == Map::<int, int>::empty(),
        step2(q3(), TL2::ReadBucket { n: 1 }, q3()),
        !step_or_stutter::<TaggL1>(abst(q3()), labt(TL2::ReadBucket { n: 1 }), abst(q3())),
{
    lemma_t_steps(t0(), 0, 1, Mode::Insert);
    lemma_t_steps(q1(), 0, 5, Mode::Update);
    lemma_t_steps(q2(), 0, 5, Mode::Update);
    lemma_cnt_empty(bw());
    lemma_cnt_insert(Map::<int, int>::empty(), bw(), 0, 1);
    lemma_cnt_insert(q1().tout, bw(), 0, 5);
    assert(cnt(q2().tout, bw()) == 1);
    lemma_t_steps(q3(), 0, 5, Mode::Update);
    assert(q2().tout.remove(0) =~= Map::<int, int>::empty());
    assert(cnt(q3().tout, bw()) == 0);
}

} // verus!
