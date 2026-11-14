//! Proved counterexample for control `control_fc0601_no_version_check` (F-C0601), compiled only with it.
//!
//! The model trace breadth-a-mc-vec_queue-as-built (reenqueue): a worker claims node 5's entry at text version 1 and
//! makes its vector; the node is re-enqueued with new text (Enqueue overwrites, EmbedQueue.cls:44-58); the worker
//! writes the old vector and marks DONE unconditionally. The newer request is lost: not an L1 step, and L1's
//! invariant fails.
use vstd::prelude::*;
use actors::protocol::*;
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

pub proof fn counterexample_fc0601()
    ensures
        init2(q0()),
        step2(q0(), QL2::Enqueue { node: n5() }, q1()),
        step2(q1(), QL2::Claim { w: 0, node: n5() }, q2()),
        step2(q2(), QL2::Embed { w: 0, ok: true }, q3()),
        step2(q3(), QL2::Enqueue { node: n5() }, q4()),
        step2(q4(), QL2::Write { w: 0, node: n5(), wrote: Some(1) }, q5()),
        step2(q5(), QL2::Mark { w: 0, node: n5(), out: Some(true) }, q6()),
        !step_or_stutter::<QueueL1>(absq(q5()), labq(QL2::Mark { w: 0, node: n5(), out: Some(true) }), absq(q6())),
        q6().st[n5()] is Done && q6().rows[n5()] == 1 && q6().text[n5()] == 2,
        !inv1(absq(q6())),
{
    lemma_q_steps(q0(), 0, true);
    lemma_q_steps(q1(), 0, true);
    lemma_q_steps(q2(), 0, true);
    lemma_q_steps(q3(), 0, true);
    lemma_q_steps(q4(), 0, true);
    assert(wrote(q4(), 0) == Some(1nat));
    lemma_q_steps(q5(), 0, true);
    assert(mark_out(q5(), 0) == Some(true));
    assert(q6().st.contains_key(n5()) && q6().st[n5()] is Done);
}

} // verus!
