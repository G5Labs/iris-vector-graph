//! The bulk L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::bulk_l2::*;

verus! {

pub open spec fn b0() -> BS2 { BS2 { committed: Set::empty(), written: Set::empty(), call: None } }
pub open spec fn p_begin(s: BS2, a: Set<int>, b: Set<int>) -> BS2 { BS2 { written: Set::empty(), call: Some(Call { a, b, ph: Ph::Load0 }), ..s } }
pub open spec fn p_chunkok(s: BS2) -> BS2 {
    BS2 { committed: if f0305() { s.committed.union(chunk_of(s.call->Some_0)) } else { s.committed },
          written: s.written.union(chunk_of(s.call->Some_0)), call: Some(after_chunk(s.call->Some_0)) }
}
pub open spec fn p_chunkfail(s: BS2) -> BS2 { BS2 { written: Set::empty(), call: Some(Call { ph: Ph::Fallback, ..s.call->Some_0 }), ..s } }
pub open spec fn p_commit(s: BS2) -> BS2 { BS2 { committed: s.committed.union(s.written), written: Set::empty(), call: None } }
pub open spec fn p_fallbackok(s: BS2) -> BS2 { BS2 { committed: s.committed.union(batch_of(s.call->Some_0)), call: None, ..s } }
pub open spec fn p_end(s: BS2) -> BS2 { BS2 { call: None, ..s } }
pub open spec fn p_abort(s: BS2) -> BS2 { BS2 { written: Set::empty(), call: None, ..s } }

pub proof fn lemma_b_steps(s: BS2, a: Set<int>, b: Set<int>)
    ensures
        s.call is None ==> step2(s, BL2::Begin { a, b }, p_begin(s, a, b)),
        s.call is Some && loading(s.call->Some_0) ==> step2(s, BL2::ChunkOk, p_chunkok(s)),
        s.call is Some && loading(s.call->Some_0) ==> step2(s, BL2::ChunkFail, p_chunkfail(s)),
        s.call is Some && s.call->Some_0.ph is Loaded ==> step2(s, BL2::Commit { batch: batch_of(s.call->Some_0) }, p_commit(s)),
        s.call is Some && s.call->Some_0.ph is Fallback ==> step2(s, BL2::FallbackOk { batch: batch_of(s.call->Some_0) }, p_fallbackok(s)),
        s.call is Some && s.call->Some_0.ph is Fallback ==> step2(s, BL2::FallbackFail { batch: batch_of(s.call->Some_0) }, p_end(s)),
        s.call is Some ==> step2(s, BL2::Abort { batch: batch_of(s.call->Some_0) }, p_abort(s)),
        step2(s, BL2::Read { rows: s.committed }, s),
{
}

} // verus!
