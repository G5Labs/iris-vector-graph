//! Module 03, L2 part 3: bulk_create_nodes on the server-loader path at pin 3eaa79cf (nodes_edges.py:1715-1757; edges
//! 2046-2071); refinement of `bulk_l1` for every step, the invariant, and the control F-0305.
//!
//! The call opens a WriteTxn on the cursor (`Begin`), sends the batch in chunks of 1,000 to
//! Graph.KG.EdgeScan.BulkIngestNodesSQL, each a TSTART ... TCOMMIT (EdgeScan.cls:352, 424; TROLLBACK 1 on error, 426),
//! then commits the WriteTxn (`Commit`); on any exception it rolls the WriteTxn back and runs the SQL path over the
//! whole batch (`FallbackOk` / `FallbackFail`). A client killed mid-call (`Abort`) leaves IRIS to roll back its open
//! transaction. State: the committed rows (what READ COMMITTED readers see), the rows the call's loader calls have
//! written (`written`), the call's chunks and phase. A batch of two chunks (more chunks only add partial states).
//!
//! **Reviewed design** (F-0305 remedy): the loader runs on the cursor's own process (`txn.native()` in every case), so
//! each chunk's TSTART/TCOMMIT is a nested level of the WriteTxn and nothing is durable before `txn.commit()` (IRIS
//! nested transactions: TCOMMIT at $TLevel > 1 only decrements it). As built, outside a caller's transaction
//! `iris_obj = self._iris_obj()`, on a `from_connect` engine a Native API connection of its own (engine.py:1916-1942):
//! another server process, so each chunk's TCOMMIT is a durable commit of its own.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::bulk_l1::*;

verus! {

pub enum Ph { Load0, Load1, Loaded, Fallback }
pub struct Call { pub a: Set<int>, pub b: Set<int>, pub ph: Ph }
pub struct BS2 { pub committed: Set<int>, pub written: Set<int>, pub call: Option<Call> }

pub enum BL2 {
    Begin { a: Set<int>, b: Set<int> },
    ChunkOk,
    ChunkFail,
    Commit { batch: Set<int> },
    FallbackOk { batch: Set<int> },
    FallbackFail { batch: Set<int> },
    Abort { batch: Set<int> },
    Read { rows: Set<int> },
}

pub open spec fn f0305() -> bool { cfg!(feature = "control_f0305_chunks_commit_alone") }

pub open spec fn batch_of(c: Call) -> Set<int> { c.a.union(c.b) }
pub open spec fn loading(c: Call) -> bool { c.ph is Load0 || c.ph is Load1 }
pub open spec fn chunk_of(c: Call) -> Set<int> { if c.ph is Load0 { c.a } else { c.b } }
pub open spec fn after_chunk(c: Call) -> Call { Call { ph: if c.ph is Load0 { Ph::Load1 } else { Ph::Loaded }, ..c } }

pub open spec fn init2(s: BS2) -> bool { s.committed == Set::<int>::empty() && s.written == Set::<int>::empty() && s.call is None }

pub open spec fn step2(s: BS2, l: BL2, t: BS2) -> bool {
    match l {
        BL2::Begin { a, b } =>
            s.call is None && t == (BS2 { written: Set::empty(), call: Some(Call { a, b, ph: Ph::Load0 }), ..s }),
        BL2::ChunkOk =>
            s.call is Some && loading(s.call->Some_0)
                && t == (BS2 { committed: if f0305() { s.committed.union(chunk_of(s.call->Some_0)) } else { s.committed },
                               written: s.written.union(chunk_of(s.call->Some_0)), call: Some(after_chunk(s.call->Some_0)) }),
        BL2::ChunkFail =>
            s.call is Some && loading(s.call->Some_0)
                && t == (BS2 { written: Set::empty(), call: Some(Call { ph: Ph::Fallback, ..s.call->Some_0 }), ..s }),
        BL2::Commit { batch } =>
            s.call is Some && s.call->Some_0.ph is Loaded && batch == batch_of(s.call->Some_0)
                && t == (BS2 { committed: s.committed.union(s.written), written: Set::empty(), call: None }),
        BL2::FallbackOk { batch } =>
            s.call is Some && s.call->Some_0.ph is Fallback && batch == batch_of(s.call->Some_0)
                && t == (BS2 { committed: s.committed.union(batch), call: None, ..s }),
        BL2::FallbackFail { batch } =>
            s.call is Some && s.call->Some_0.ph is Fallback && batch == batch_of(s.call->Some_0) && t == (BS2 { call: None, ..s }),
        BL2::Abort { batch } =>
            s.call is Some && batch == batch_of(s.call->Some_0) && t == (BS2 { written: Set::empty(), call: None, ..s }),
        BL2::Read { rows } => rows == s.committed && t == s,
    }
}

pub open spec fn absb(s: BS2) -> BS1 { BS1 { rows: s.committed } }
pub open spec fn labb(l: BL2) -> Option<BL1> {
    match l {
        BL2::Begin { a, b } => None,
        BL2::ChunkOk => None,
        BL2::ChunkFail => None,
        BL2::Commit { batch } => Some(BL1::Bulk { batch, ok: true }),
        BL2::FallbackOk { batch } => Some(BL1::Bulk { batch, ok: true }),
        BL2::FallbackFail { batch } => Some(BL1::Bulk { batch, ok: false }),
        BL2::Abort { batch } => Some(BL1::Bulk { batch, ok: false }),
        BL2::Read { rows } => Some(BL1::Read { rows }),
    }
}

/// What the call has written so far, by phase.
pub open spec fn inv03b(s: BS2) -> bool {
    match s.call {
        None => s.written == Set::<int>::empty(),
        Some(c) => match c.ph {
            Ph::Load0 => s.written == Set::<int>::empty(),
            Ph::Load1 => s.written == c.a,
            Ph::Loaded => s.written == batch_of(c),
            Ph::Fallback => s.written == Set::<int>::empty(),
        },
    }
}

pub struct BulkL2;

impl Contract for BulkL2 {
    type S = BS2;
    type L = BL2;
    open spec fn init(s: BS2) -> bool { init2(s) }
    open spec fn next(s: BS2, l: BL2, t: BS2) -> bool { inv03b(s) && step2(s, l, t) }
}

pub struct BulkRaw;

impl Contract for BulkRaw {
    type S = BS2;
    type L = BL2;
    open spec fn init(s: BS2) -> bool { init2(s) }
    open spec fn next(s: BS2, l: BL2, t: BS2) -> bool { step2(s, l, t) }
}

proof fn lemma_chunkok(s: BS2, t: BS2)
    requires inv03b(s), step2(s, BL2::ChunkOk, t),
    ensures inv03b(t), step_or_stutter::<BulkL1>(absb(s), labb(BL2::ChunkOk), absb(t)),
{
    // a chunk's TCOMMIT is a nested level of the caller's WriteTxn: nothing is visible before the call commits
    // (control F-0305 fails here)
    assert(t.committed == s.committed);
    let c = s.call->Some_0;
    if c.ph is Load0 { assert(t.written =~= c.a); } else { assert(t.written =~= batch_of(c)); }
}

proof fn lemma_step(s: BS2, l: BL2, t: BS2)
    requires inv03b(s), step2(s, l, t),
    ensures inv03b(t), step_or_stutter::<BulkL1>(absb(s), labb(l), absb(t)),
{
    match l {
        BL2::ChunkOk => lemma_chunkok(s, t),
        BL2::Commit { batch } => { assert(t.committed =~= s.committed.union(batch)); }
        _ => {}
    }
}

impl Refines<BulkL1> for BulkL2 {
    open spec fn abs(s: BS2) -> BS1 { absb(s) }
    open spec fn lab(l: BL2) -> Option<BL1> { labb(l) }
    proof fn init_refines(s: BS2) {}
    proof fn step_refines(s: BS2, l: BL2, t: BS2) { lemma_step(s, l, t); }
}

impl SafeContract for BulkL2 {
    open spec fn inv(s: BS2) -> bool { inv03b(s) }
    proof fn init_safe(s: BS2) {}
    proof fn step_safe(s: BS2, l: BL2, t: BS2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<BS2>, labels: Seq<BL2>, k: int)
    requires execution::<BulkRaw>(states, labels), 0 <= k < states.len(),
    ensures inv03b(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution: readers of other processes see the committed rows change by whole batches only.
pub proof fn theorem_raw_executions_refine(states: Seq<BS2>, labels: Seq<BL2>)
    requires execution::<BulkRaw>(states, labels),
    ensures
        execution::<BulkL2>(states, labels),
        abstract_execution::<BulkL1>(Seq::new(states.len(), |i: int| absb(states[i])),
                                     Seq::new(labels.len(), |i: int| labb(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv03b(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv03b(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<BulkL2>(states, labels));
    trace_refines::<BulkL2, BulkL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absb(states[i])) =~= Seq::new(states.len(), |i: int| <BulkL2 as Refines<BulkL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labb(labels[i])) =~= Seq::new(labels.len(), |i: int| <BulkL2 as Refines<BulkL1>>::lab(labels[i])));
}

/// WRT-B3.19 on the layout: while a call is in flight, the committed rows are those before it (nothing of the batch is
/// visible) -- stated as: no step of a call other than its end changes the committed rows.
pub proof fn theorem_no_partial_batch_visible(s: BS2, l: BL2, t: BS2)
    requires inv03b(s), step2(s, l, t), l is Begin || l is ChunkOk || l is ChunkFail,
    ensures t.committed == s.committed,
{
    lemma_step(s, l, t);
}

} // verus!
