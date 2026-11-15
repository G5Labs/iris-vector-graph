//! Proved counterexample for control `control_f0604_done_without_vector` (F-0604), compiled only with it.
//!
//! The live trace breadth-a-live-06-vectors (p0604): the worker's EMBEDDING() makes no vector, nothing is written,
//! and ProcessBatch sets DONE (EmbedQueue.cls:307-327): process_batch answered {"processed":1,"errors":0}. The mark is
//! not an L1 step and L1's invariant fails.
use vstd::prelude::*;
use actors::protocol::*;
use crate::vq_l1::*;
use crate::vq_l2::*;
use crate::vq_runs::*;

verus! {

pub open spec fn q1() -> QS2 { enq(q0()) }
pub open spec fn q2() -> QS2 { claim(q1(), 0) }
pub open spec fn q3() -> QS2 { embed(q2(), 0, false) }
pub open spec fn q4() -> QS2 { write(q3(), 0) }
pub open spec fn q5() -> QS2 { mark(q4(), 0) }

pub proof fn counterexample_f0604()
    ensures
        init2(q0()),
        step2(q0(), QL2::Enqueue { node: n5() }, q1()),
        step2(q1(), QL2::Claim { w: 0, node: n5() }, q2()),
        step2(q2(), QL2::Embed { w: 0, ok: false }, q3()),
        step2(q3(), QL2::Write { w: 0, node: n5(), wrote: None }, q4()),
        step2(q4(), QL2::Mark { w: 0, node: n5(), out: Some(true) }, q5()),
        !step_or_stutter::<QueueL1>(absq(q4()), labq(QL2::Mark { w: 0, node: n5(), out: Some(true) }), absq(q5())),
        q5().st[n5()] is Done && !q5().rows.contains_key(n5()),
        !inv1(absq(q5())),
{
    lemma_q_steps(q0(), 0, false);
    lemma_q_steps(q1(), 0, false);
    lemma_q_steps(q2(), 0, false);
    lemma_q_steps(q3(), 0, false);
    assert(wrote(q3(), 0) == None::<nat>);
    lemma_q_steps(q4(), 0, false);
    assert(mark_out(q4(), 0) == Some(true));
    assert(q5().st.contains_key(n5()) && q5().st[n5()] is Done);
}

} // verus!
