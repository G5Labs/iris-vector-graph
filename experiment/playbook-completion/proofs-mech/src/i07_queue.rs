//! M-07 instances: one type per object variant of mechanisms.json (family `queue`, models/semantics/src/queue.rs).
//! 06/queue-entry uses the Entry and Order sub-mechanisms, 13/redaction-run the Resume sub-mechanism.
//! Not modelled here (as in the explorer): 09/compiled-shape (breadth-b machine planc), 15/fhir-graph and
//! 15/fhir-sync-task (breadth-c machine M3).
use vstd::prelude::*;
use crate::exec::*;
use crate::m07_queue::*;

verus! {

// ================================================================================================ Entry

/// embed-queue entry, reviewed: 06/queue-entry (IfMade, text-guarded mark, single consumer).
pub struct EmbedQueueEntryReviewed;
impl QueueEntryPolicy for EmbedQueueEntryReviewed {
    open spec fn entry_cfg() -> EntryCfg { EntryCfg { mark: Mark::IfMade, cas: true, single: true } }
}
impl QueueEntryObject for EmbedQueueEntryReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
}
pub proof fn laws_embed_queue_entry_reviewed(s0: ES, ls: Seq<EA>, t: ES) requires reached::<EntryM<EmbedQueueEntryReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l2(t) { theorem_entry::<EmbedQueueEntryReviewed>(s0, ls, t); }

/// embed-queue as built, F-0604 (EmbedQueue.cls:326-327): DONE without a vector.
pub struct EmbedQueueF0604;
impl QueueEntryPolicy for EmbedQueueF0604 {
    open spec fn entry_cfg() -> EntryCfg { EntryCfg { mark: Mark::Always, cas: true, single: true } }
}
pub proof fn refute_embed_queue_f0604_l1() ensures !obl_l1::<EmbedQueueF0604>() {}
pub proof fn keep_embed_queue_f0604_l2() ensures obl_l2::<EmbedQueueF0604>() {}

/// embed-queue as built, F-C0601: DONE with an old text (the mark does not check a re-enqueue).
pub struct EmbedQueueFC0601;
impl QueueEntryPolicy for EmbedQueueFC0601 {
    open spec fn entry_cfg() -> EntryCfg { EntryCfg { mark: Mark::IfMade, cas: false, single: true } }
}
pub proof fn refute_embed_queue_fc0601_l1() ensures !obl_l1::<EmbedQueueFC0601>() {}
pub proof fn keep_embed_queue_fc0601_l2() ensures obl_l2::<EmbedQueueFC0601>() {}

/// embed-queue as built, HD-0604 / F-C0670: two workers (the IRIS task and process_embed_queue) can work one entry.
pub struct EmbedQueueHD0604;
impl QueueEntryPolicy for EmbedQueueHD0604 {
    open spec fn entry_cfg() -> EntryCfg { EntryCfg { mark: Mark::Always, cas: false, single: false } }
}
pub proof fn refute_embed_queue_hd0604_l1() ensures !obl_l1::<EmbedQueueHD0604>() {}
pub proof fn refute_embed_queue_hd0604_l2() ensures !obl_l2::<EmbedQueueHD0604>() {}

/// queue-control-C2-two-consumers: the reviewed entry without its single-consumer lock.
pub struct CtlTwoConsumers;
impl QueueEntryPolicy for CtlTwoConsumers {
    open spec fn entry_cfg() -> EntryCfg { EntryCfg { mark: Mark::IfMade, cas: true, single: false } }
}
pub proof fn refute_ctl_two_consumers_l1() ensures !obl_l1::<CtlTwoConsumers>() {}
pub proof fn refute_ctl_two_consumers_l2() ensures !obl_l2::<CtlTwoConsumers>() {}

/// queue-control-C3-mark-always: the reviewed entry marking DONE whenever no exception was thrown.
pub struct CtlMarkAlways;
impl QueueEntryPolicy for CtlMarkAlways {
    open spec fn entry_cfg() -> EntryCfg { EntryCfg { mark: Mark::Always, cas: true, single: true } }
}
pub proof fn refute_ctl_mark_always_l1() ensures !obl_l1::<CtlMarkAlways>() {}
pub proof fn keep_ctl_mark_always_l2() ensures obl_l2::<CtlMarkAlways>() {}

// ================================================================================================ Order

/// The first minimal id (Rust's min_by_key: ties keep the earlier index).
pub open spec fn argmin(q: Seq<nat>) -> int
    decreases q.len(),
{
    if q.len() <= 1 { 0 } else {
        let k = argmin(q.drop_last());
        if q.last() < q[k] { q.len() - 1 } else { k }
    }
}

/// embed-queue order, reviewed: 06/queue-entry served in arrival order (the finding's remedy).
pub struct EmbedQueueOrderReviewed;
impl QueueOrderPolicy for EmbedQueueOrderReviewed { open spec fn pick(q: Seq<nat>) -> int { 0 } }
impl QueueOrderObject for EmbedQueueOrderReviewed {
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_embed_queue_order_reviewed(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA, s0: OS, ls: Seq<OA>, t: OS, i: nat)
    requires reached::<OrderM<EmbedQueueOrderReviewed>>(s0, ls, t)
    ensures law_l3(t) { theorem_order::<EmbedQueueOrderReviewed>(st, lb, s0, ls, t, i); }

/// embed-queue order as built, F-C0605 (EmbedQueue.cls:112-133, 258-268): the first PENDING id in collation order.
pub struct EmbedQueueOrderAsBuilt;
impl QueueOrderPolicy for EmbedQueueOrderAsBuilt { open spec fn pick(q: Seq<nat>) -> int { argmin(q) } }
pub proof fn lemma_argmin_20()
    ensures EmbedQueueOrderAsBuilt::pick(seq![2nat, 0nat]) == 1,
{
    reveal_with_fuel(argmin, 3);
    assert(seq![2nat, 0nat].drop_last().len() == 1);
}
pub proof fn refute_embed_queue_order_l3() ensures !obl_l3::<EmbedQueueOrderAsBuilt>() { lemma_argmin_20(); }
pub proof fn refute_embed_queue_order_l4() ensures !obl_l4::<EmbedQueueOrderAsBuilt>() { lemma_argmin_20(); }

/// queue-control-C1-lifo-overtaking / C1b-lifo-fair-lasso: the last arrival is served first.
pub struct CtlLifo;
impl QueueOrderPolicy for CtlLifo { open spec fn pick(q: Seq<nat>) -> int { q.len() - 1 } }
pub proof fn refute_ctl_lifo_l3() ensures !obl_l3::<CtlLifo>() { assert(CtlLifo::pick(seq![2nat, 0nat]) == 1); }
pub proof fn refute_ctl_lifo_l4() ensures !obl_l4::<CtlLifo>() { assert(CtlLifo::pick(seq![2nat, 0nat]) == 1); }

// ================================================================================================ Resume

/// bounded-redaction-resume, reviewed: 13/redaction-run keeps its cursor across calls.
pub struct BoundedRedactionResumeReviewed;
impl ResumePolicy for BoundedRedactionResumeReviewed { open spec fn resume_at(cursor: nat) -> nat { cursor } }
impl ResumeObject for BoundedRedactionResumeReviewed {
    proof fn discharge_l4() {}
}
pub proof fn laws_bounded_redaction_resume_reviewed(s0: RsS, ls: Seq<RsA>, t: RsS)
    requires reached::<ResumeM<BoundedRedactionResumeReviewed>>(s0, ls, t)
    ensures law_l4_resume::<BoundedRedactionResumeReviewed>(t) { theorem_resume::<BoundedRedactionResumeReviewed>(s0, ls, t); }

/// bounded-redaction-resume as built, F-C1303 (LedgerRedact.cls:185-240, live live-fc1303-bounded-resume): every
/// call scans from the first record.
pub struct BoundedRedactionResumeAsBuilt;
impl ResumePolicy for BoundedRedactionResumeAsBuilt { open spec fn resume_at(cursor: nat) -> nat { 0 } }
pub proof fn refute_bounded_redaction_resume_l4() ensures !obl_l4_resume::<BoundedRedactionResumeAsBuilt>() {
    assert(BoundedRedactionResumeAsBuilt::resume_at(1) != 1);
}

/// queue-control-C4-restart-scan: the reviewed run restarting its scan on every call.
pub struct CtlRestartScan;
impl ResumePolicy for CtlRestartScan { open spec fn resume_at(cursor: nat) -> nat { 0 } }
pub proof fn refute_ctl_restart_scan_l4() ensures !obl_l4_resume::<CtlRestartScan>() {
    assert(CtlRestartScan::resume_at(1) != 1);
}

// ================================================================================================ order step facts

pub open spec fn oq(q: Seq<nat>, ov: nat) -> OS { OS { queue: q, high_enqueued: true, overtakes: ov, served_high: false } }

/// An enqueue of an id that is not pending (any policy).
pub proof fn lemma_enqueue<O: QueueOrderPolicy>(s: OS, i: nat)
    requires i < 3, forall|k: int| 0 <= k < s.queue.len() ==> s.queue[k] != i, !(i == 2 && s.high_enqueued),
    ensures order_step::<O>(s, OA::Enqueue(i)) == Some(OS { queue: s.queue.push(i), high_enqueued: s.high_enqueued || i == 2, ..s }),
{
    assert(!s.queue.contains(i));
}

/// Serving the low id behind id 2 (any policy that picks index 1 of [2, 0]).
pub proof fn lemma_serve_low<O: QueueOrderPolicy>(ov: nat)
    requires O::pick(seq![2nat, 0nat]) == 1,
    ensures order_step::<O>(oq(seq![2nat, 0nat], ov), OA::Serve) == Some(oq(seq![2nat], if ov + 1 < 3 { ov + 1 } else { 3 })),
{
    let q = seq![2nat, 0nat];
    assert(q.contains(2)) by { assert(q[0] == 2); }
    assert(remove_at(q, 1) =~= seq![2nat]);
}

// ================================================================================================ sharpness

/// queue-sharp-fifo-serves-high: arrival order serves id 2 with two others still waiting.
pub proof fn sharp_fifo_serves_high()
    ensures ({
        let t = run::<OrderM<EmbedQueueOrderReviewed>>(order_s0(), seq![OA::Enqueue(2), OA::Enqueue(0), OA::Enqueue(1), OA::Serve]);
        t is Some && t->0.served_high && t->0.queue.len() == 2
    })
{
    reveal_with_fuel(run, 5);
    let s0 = order_s0();
    lemma_enqueue::<EmbedQueueOrderReviewed>(s0, 2);
    let s1 = order_step::<EmbedQueueOrderReviewed>(s0, OA::Enqueue(2))->0;
    lemma_enqueue::<EmbedQueueOrderReviewed>(s1, 0);
    let s2 = order_step::<EmbedQueueOrderReviewed>(s1, OA::Enqueue(0))->0;
    lemma_enqueue::<EmbedQueueOrderReviewed>(s2, 1);
    let s3 = order_step::<EmbedQueueOrderReviewed>(s2, OA::Enqueue(1))->0;
    assert(s3.queue[0] == 2);
    let s4 = order_step::<EmbedQueueOrderReviewed>(s3, OA::Serve)->0;
    assert(order_step::<EmbedQueueOrderReviewed>(s3, OA::Serve) is Some);
    assert(run::<OrderM<EmbedQueueOrderReviewed>>(order_s0(), seq![OA::Enqueue(2), OA::Enqueue(0), OA::Enqueue(1), OA::Serve]) == Some(s4));
}

/// queue-sharp-fifo-overtake-2: id 2 is overtaken twice (the bound N-1 is reached).
pub proof fn sharp_fifo_overtake_2()
    ensures ({
        let t = run::<OrderM<EmbedQueueOrderReviewed>>(order_s0(), seq![OA::Enqueue(0), OA::Enqueue(1), OA::Enqueue(2), OA::Serve, OA::Serve]);
        t is Some && t->0.overtakes == 2 && t->0.queue.contains(2)
    })
{
    reveal_with_fuel(run, 6);
    let s0 = order_s0();
    lemma_enqueue::<EmbedQueueOrderReviewed>(s0, 0);
    let s1 = order_step::<EmbedQueueOrderReviewed>(s0, OA::Enqueue(0))->0;
    lemma_enqueue::<EmbedQueueOrderReviewed>(s1, 1);
    let s2 = order_step::<EmbedQueueOrderReviewed>(s1, OA::Enqueue(1))->0;
    lemma_enqueue::<EmbedQueueOrderReviewed>(s2, 2);
    let s3 = order_step::<EmbedQueueOrderReviewed>(s2, OA::Enqueue(2))->0;
    assert(s3.queue[2] == 2 && s3.queue[0] == 0);
    assert(s3.queue.contains(2));
    let s4 = order_step::<EmbedQueueOrderReviewed>(s3, OA::Serve)->0;
    assert(remove_at(s3.queue, 0) =~= seq![1nat, 2nat]);
    assert(s4.queue[1] == 2 && s4.queue[0] == 1);
    assert(s4.queue.contains(2));
    let s5 = order_step::<EmbedQueueOrderReviewed>(s4, OA::Serve)->0;
    assert(remove_at(s4.queue, 0) =~= seq![2nat]);
    assert(s5.queue[0] == 2);
    assert(run::<OrderM<EmbedQueueOrderReviewed>>(order_s0(), seq![OA::Enqueue(0), OA::Enqueue(1), OA::Enqueue(2), OA::Serve, OA::Serve]) == Some(s5));
}

/// queue-sharp-resume-finishes: the persisted cursor finishes in three calls.
pub proof fn sharp_resume_finishes()
    ensures ({
        let t = run::<ResumeM<BoundedRedactionResumeReviewed>>(resume_s0(), seq![RsA::Call, RsA::Call, RsA::Call]);
        t is Some && finished(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

} // verus!
