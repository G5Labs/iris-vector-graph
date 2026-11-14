//! Proved counterexample for control `control_hd0604_two_consumers` (HD-0604), compiled only with it.
//!
//! The live trace intent-a-hd0604-queue-claim: two workers (the IRIS task and a Python process_embed_queue) are handed
//! the same PENDING entry (ClaimPendingBatch is a plain scan, EmbedQueue.cls:112-134). Worker 0 makes a vector and
//! marks DONE; worker 1's model call fails and it marks ERROR over the answered request. That mark is not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::vq_l1::*;
use crate::vq_l2::*;
use crate::vq_runs::*;

verus! {

pub open spec fn q1() -> QS2 { enq(q0()) }
pub open spec fn q2() -> QS2 { claim(q1(), 0) }
pub open spec fn q3() -> QS2 { claim(q2(), 1) }
pub open spec fn q4() -> QS2 { embed(q3(), 0, true) }
pub open spec fn q5() -> QS2 { write(q4(), 0) }
pub open spec fn q6() -> QS2 { mark(q5(), 0) }
pub open spec fn q7() -> QS2 { embed(q6(), 1, false) }
pub open spec fn q8() -> QS2 { write(q7(), 1) }
pub open spec fn q9() -> QS2 { mark(q8(), 1) }

pub proof fn counterexample_hd0604()
    ensures
        init2(q0()),
        step2(q0(), QL2::Enqueue { node: n5() }, q1()),
        step2(q1(), QL2::Claim { w: 0, node: n5() }, q2()),
        step2(q2(), QL2::Claim { w: 1, node: n5() }, q3()),
        step2(q3(), QL2::Embed { w: 0, ok: true }, q4()),
        step2(q4(), QL2::Write { w: 0, node: n5(), wrote: Some(1) }, q5()),
        step2(q5(), QL2::Mark { w: 0, node: n5(), out: Some(true) }, q6()),
        step2(q6(), QL2::Embed { w: 1, ok: false }, q7()),
        step2(q7(), QL2::Write { w: 1, node: n5(), wrote: None }, q8()),
        step2(q8(), QL2::Mark { w: 1, node: n5(), out: Some(false) }, q9()),
        // the second mark lands on an answered request: not an L1 step
        !step_or_stutter::<QueueL1>(absq(q8()), labq(QL2::Mark { w: 1, node: n5(), out: Some(false) }), absq(q9())),
        q6().st[n5()] is Done && q9().st[n5()] is Error && q9().rows[n5()] == q9().text[n5()],
{
    lemma_q_steps(q0(), 0, true);
    lemma_q_steps(q1(), 0, true);
    lemma_q_steps(q2(), 1, true);
    lemma_q_steps(q3(), 0, true);
    lemma_q_steps(q4(), 0, true);
    assert(wrote(q4(), 0) == Some(1nat));
    lemma_q_steps(q5(), 0, true);
    assert(mark_out(q5(), 0) == Some(true));
    lemma_q_steps(q6(), 1, false);
    lemma_q_steps(q7(), 1, false);
    assert(wrote(q7(), 1) == None::<nat>);
    lemma_q_steps(q8(), 1, false);
    assert(mark_out(q8(), 1) == Some(false));
    assert(q8().st[n5()] is Done);
}

} // verus!
