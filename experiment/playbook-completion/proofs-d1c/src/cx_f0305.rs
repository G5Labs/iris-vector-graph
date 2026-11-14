//! Proved counterexample for control `control_f0305_chunks_commit_alone` (F-0305), compiled only with it.
//!
//! The live traces breadth-a-live-03-bulk-atomicity (1,001 of 2,000 nodes committed and visible to a READ COMMITTED
//! reader while the call ran; the journal shows each chunk committed by the engine's Native API process) and
//! breadth-a-live-03-bulk-killed-client (a client killed inside chunk 2 left exactly chunk 1 committed): the first
//! chunk's commit is not an L1 step (a stutter that changes the committed rows); a reader sees part of the batch; the
//! killed client leaves it there.
use vstd::prelude::*;
use actors::protocol::*;
use crate::bulk_l1::*;
use crate::bulk_l2::*;
use crate::bulk_runs::*;

verus! {

pub open spec fn ca() -> Set<int> { Set::empty().insert(1int) }
pub open spec fn cb() -> Set<int> { Set::empty().insert(2int) }
pub open spec fn b1() -> BS2 { p_begin(b0(), ca(), cb()) }
pub open spec fn b2() -> BS2 { p_chunkok(b1()) }
pub open spec fn b3() -> BS2 { p_abort(b2()) }

pub proof fn counterexample_f0305()
    ensures
        init2(b0()),
        step2(b0(), BL2::Begin { a: ca(), b: cb() }, b1()),
        step2(b1(), BL2::ChunkOk, b2()),
        !step_or_stutter::<BulkL1>(absb(b1()), labb(BL2::ChunkOk), absb(b2())),
        step2(b2(), BL2::Read { rows: ca() }, b2()),
        step2(b2(), BL2::Abort { batch: ca().union(cb()) }, b3()),
        b3().committed == ca() && b3().call is None,
{
    lemma_b_steps(b0(), ca(), cb());
    lemma_b_steps(b1(), ca(), cb());
    assert(b2().committed =~= ca());
    assert(b2().committed.contains(1) && !b1().committed.contains(1));
    lemma_b_steps(b2(), ca(), cb());
    assert(batch_of(b2().call->Some_0) == ca().union(cb()));
}

} // verus!
