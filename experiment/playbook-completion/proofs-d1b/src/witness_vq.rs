//! Non-vacuity of the module 06 queue model (compiled without the queue controls): node 5 is enqueued; the single
//! worker claims it and makes a vector, but the node is re-enqueued meanwhile, so its mark writes nothing; the worker
//! claims the new text and marks DONE with a vector of it; a third request whose model call fails ends in ERROR.
use vstd::prelude::*;
use crate::vq_l1::*;
use crate::vq_l2::*;
use crate::vq_runs::*;

verus! {

pub open spec fn q1() -> QS2 { enq(q0()) }
pub open spec fn q2() -> QS2 { claim(q1(), 0) }
pub open spec fn q3() -> QS2 { embed(q2(), 0, true) }
pub open spec fn q4() -> QS2 { enq(q3()) }
pub open spec fn q5() -> QS2 { write(q4(), 0) }
pub open spec fn q6() -> QS2 { mark(q5(), 0) }
pub open spec fn q7() -> QS2 { claim(q6(), 0) }
pub open spec fn q8() -> QS2 { embed(q7(), 0, true) }
pub open spec fn q9() -> QS2 { write(q8(), 0) }
pub open spec fn q10() -> QS2 { mark(q9(), 0) }
pub open spec fn q11() -> QS2 { enq(q10()) }
pub open spec fn q12() -> QS2 { claim(q11(), 0) }
pub open spec fn q13() -> QS2 { embed(q12(), 0, false) }
pub open spec fn q14() -> QS2 { write(q13(), 0) }
pub open spec fn q15() -> QS2 { mark(q14(), 0) }

pub proof fn witness_vq()
    ensures
        init2(q0()),
        step2(q0(), QL2::Enqueue { node: n5() }, q1()),
        step2(q1(), QL2::Claim { w: 0, node: n5() }, q2()),
        step2(q2(), QL2::Embed { w: 0, ok: true }, q3()),
        step2(q3(), QL2::Enqueue { node: n5() }, q4()),
        step2(q4(), QL2::Write { w: 0, node: n5(), wrote: Some(1) }, q5()),
        step2(q5(), QL2::Mark { w: 0, node: n5(), out: None }, q6()),
        q6().st[n5()] is Pending,
        step2(q6(), QL2::Claim { w: 0, node: n5() }, q7()),
        step2(q7(), QL2::Embed { w: 0, ok: true }, q8()),
        step2(q8(), QL2::Write { w: 0, node: n5(), wrote: Some(2) }, q9()),
        step2(q9(), QL2::Mark { w: 0, node: n5(), out: Some(true) }, q10()),
        q10().st[n5()] is Done && q10().rows[n5()] == q10().text[n5()],
        step2(q10(), QL2::Enqueue { node: n5() }, q11()),
        step2(q11(), QL2::Claim { w: 0, node: n5() }, q12()),
        step2(q12(), QL2::Embed { w: 0, ok: false }, q13()),
        step2(q13(), QL2::Write { w: 0, node: n5(), wrote: None }, q14()),
        step2(q14(), QL2::Mark { w: 0, node: n5(), out: Some(false) }, q15()),
        q15().st[n5()] is Error,
{
    lemma_q_steps(q0(), 0, true);
    lemma_q_steps(q1(), 0, true);
    lemma_q_steps(q2(), 0, true);
    lemma_q_steps(q3(), 0, true);
    lemma_q_steps(q4(), 0, true);
    assert(wrote(q4(), 0) == Some(1nat));
    lemma_q_steps(q5(), 0, true);
    assert(mark_out(q5(), 0) == None::<bool>);
    lemma_q_steps(q6(), 0, true);
    lemma_q_steps(q7(), 0, true);
    lemma_q_steps(q8(), 0, true);
    assert(wrote(q8(), 0) == Some(2nat));
    lemma_q_steps(q9(), 0, true);
    assert(mark_out(q9(), 0) == Some(true));
    lemma_q_steps(q10(), 0, false);
    lemma_q_steps(q11(), 0, false);
    lemma_q_steps(q12(), 0, false);
    lemma_q_steps(q13(), 0, false);
    assert(wrote(q13(), 0) == None::<nat>);
    lemma_q_steps(q14(), 0, false);
    assert(mark_out(q14(), 0) == Some(false));
}

} // verus!
