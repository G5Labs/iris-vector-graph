//! M-07 counterexamples: for each departing variant and each law it breaks, a run of the generic machine with that
//! variant's parameters from the initial state to a violation; for the progress law M07-L4, a proved fair lasso
//! (order) and a proved invariant that excludes every finished state (resume).
use vstd::prelude::*;
use crate::exec::*;
use crate::m07_queue::*;
use crate::i07_queue::*;

verus! {

// ================================================================================================ Entry

/// F-0604: no result was made and the entry is marked DONE.
pub proof fn cx_embed_queue_f0604_l1()
    ensures ({
        let t = run::<EntryM<EmbedQueueF0604>>(entry_s0(), seq![EA::Claim(0), EA::Make(0, false), EA::Write(0), EA::MarkStep(0)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 5);
}

/// F-C0601: the text changes while the worker runs; the mark makes DONE the result of the old text.
pub proof fn cx_embed_queue_fc0601_l1()
    ensures ({
        let t = run::<EntryM<EmbedQueueFC0601>>(entry_s0(), seq![EA::Claim(0), EA::Make(0, true), EA::Write(0), EA::Enqueue, EA::MarkStep(0)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 6);
}

/// HD-0604/F-C0670 configuration (mark Always): DONE without a result.
pub proof fn cx_embed_queue_hd0604_l1()
    ensures ({
        let t = run::<EntryM<EmbedQueueHD0604>>(entry_s0(), seq![EA::Claim(0), EA::Make(0, false), EA::Write(0), EA::MarkStep(0)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 5);
}

/// F-C0670: two workers claim the same entry.
pub proof fn cx_embed_queue_hd0604_l2()
    ensures ({
        let t = run::<EntryM<EmbedQueueHD0604>>(entry_s0(), seq![EA::Claim(0), EA::Claim(1)]);
        t is Some && !law_l2(t->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// C2: the stale worker overwrites the current result after the current one marked DONE.
pub proof fn cx_ctl_two_consumers_l1()
    ensures ({
        let t = run::<EntryM<CtlTwoConsumers>>(entry_s0(), seq![EA::Claim(0), EA::Enqueue, EA::Claim(1), EA::Make(1, true), EA::Write(1), EA::Make(0, true), EA::Write(0), EA::MarkStep(1), EA::MarkStep(0)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 10);
}

/// C2: two workers claim the same entry.
pub proof fn cx_ctl_two_consumers_l2()
    ensures ({
        let t = run::<EntryM<CtlTwoConsumers>>(entry_s0(), seq![EA::Claim(0), EA::Claim(1)]);
        t is Some && !law_l2(t->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// C3: DONE without a result.
pub proof fn cx_ctl_mark_always_l1()
    ensures ({
        let t = run::<EntryM<CtlMarkAlways>>(entry_s0(), seq![EA::Claim(0), EA::Make(0, false), EA::Write(0), EA::MarkStep(0)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 5);
}

// ================================================================================================ Order

/// The explorer's shortest overtaking trace: id 2 waits while id 0 arrives and is served three times.
pub open spec fn lasso_prefix() -> Seq<OA> {
    seq![OA::Enqueue(2), OA::Enqueue(0), OA::Serve, OA::Enqueue(0), OA::Serve, OA::Enqueue(0), OA::Serve]
}

/// The lasso's cycle: [2] -Enqueue(0)-> [2, 0] -Serve-> [2], with id 2 overtaken (saturated at 3).
pub open spec fn lasso_st(i: nat) -> OS { if i % 2 == 0 { oq(seq![2nat], 3) } else { oq(seq![2nat, 0nat], 3) } }
pub open spec fn lasso_lb(i: nat) -> OA { if i % 2 == 0 { OA::Enqueue(0) } else { OA::Serve } }

/// Any service order that serves id 0 before id 2 from [2, 0] runs the prefix to the lasso's first state.
pub proof fn lemma_prefix<O: QueueOrderPolicy>()
    requires O::pick(seq![2nat, 0nat]) == 1,
    ensures reached::<OrderM<O>>(order_s0(), lasso_prefix(), oq(seq![2nat], 3)),
{
    reveal_with_fuel(run, 8);
    let s0 = order_s0();
    lemma_enqueue::<O>(s0, 2);
    assert(s0.queue.push(2) =~= seq![2nat]);
    assert(order_step::<O>(s0, OA::Enqueue(2)) == Some(oq(seq![2nat], 0)));
    lemma_enqueue::<O>(oq(seq![2nat], 0), 0);
    assert(seq![2nat].push(0) =~= seq![2nat, 0nat]);
    assert(order_step::<O>(oq(seq![2nat], 0), OA::Enqueue(0)) == Some(oq(seq![2nat, 0nat], 0)));
    lemma_serve_low::<O>(0);
    lemma_enqueue::<O>(oq(seq![2nat], 1), 0);
    assert(order_step::<O>(oq(seq![2nat], 1), OA::Enqueue(0)) == Some(oq(seq![2nat, 0nat], 1)));
    lemma_serve_low::<O>(1);
    lemma_enqueue::<O>(oq(seq![2nat], 2), 0);
    assert(order_step::<O>(oq(seq![2nat], 2), OA::Enqueue(0)) == Some(oq(seq![2nat, 0nat], 2)));
    lemma_serve_low::<O>(2);
    let p = lasso_prefix();
    assert(p.len() == 7);
}

/// The cycle is an infinite execution, the worker is weakly fair along it (a Serve at every odd step), and id 2
/// is pending at every step.
pub proof fn lemma_lasso<O: QueueOrderPolicy>()
    requires O::pick(seq![2nat, 0nat]) == 1,
    ensures
        order_exec::<O>(|i: nat| lasso_st(i), |i: nat| lasso_lb(i)),
        worker_fair(|i: nat| lasso_st(i), |i: nat| lasso_lb(i)),
        forall|k: nat| pending(#[trigger] lasso_st(k)),
{
    assert forall|i: nat| #[trigger] order_step::<O>(lasso_st(i), lasso_lb(i)) == Some(lasso_st(i + 1)) by {
        if i % 2 == 0 {
            lemma_enqueue::<O>(oq(seq![2nat], 3), 0);
            assert(seq![2nat].push(0) =~= seq![2nat, 0nat]);
            assert((i + 1) % 2 == 1);
        } else {
            lemma_serve_low::<O>(3);
            assert((i + 1) % 2 == 0);
        }
    }
    assert forall|k: nat| pending(#[trigger] lasso_st(k)) by {
        assert(lasso_st(k).queue[0] == 2);
    }
    let st = |i: nat| lasso_st(i);
    let lb = |i: nat| lasso_lb(i);
    assert forall|i: nat| #[trigger] pending(st(i)) implies exists|k: nat| k >= i && (#[trigger] lb(k)) is Serve by {
        let k: nat = if i % 2 == 1 { i } else { i + 1 };
        assert(k % 2 == 1);
        assert(lb(k) is Serve);
    }
    assert(worker_fair(st, lb));
}

/// F-C0605 (M07-L3): MinId lets id 0 overtake id 2 three times.
pub proof fn cx_embed_queue_order_l3()
    ensures ({
        let t = run::<OrderM<EmbedQueueOrderAsBuilt>>(order_s0(), lasso_prefix());
        t is Some && !law_l3(t->0)
    })
{
    lemma_argmin_20();
    lemma_prefix::<EmbedQueueOrderAsBuilt>();
}

/// F-C0605 (M07-L4): a fair lasso: the premises of theorem_l4_order hold (reached first state, infinite execution,
/// weakly fair worker) and id 2 is pending at every step, so it is never served.
pub proof fn cx_embed_queue_order_l4()
    ensures
        reached::<OrderM<EmbedQueueOrderAsBuilt>>(order_s0(), lasso_prefix(), lasso_st(0)),
        order_exec::<EmbedQueueOrderAsBuilt>(|i: nat| lasso_st(i), |i: nat| lasso_lb(i)),
        worker_fair(|i: nat| lasso_st(i), |i: nat| lasso_lb(i)),
        forall|k: nat| pending(#[trigger] lasso_st(k)),
{
    lemma_argmin_20();
    lemma_prefix::<EmbedQueueOrderAsBuilt>();
    lemma_lasso::<EmbedQueueOrderAsBuilt>();
}

/// C1 (M07-L3): LIFO lets id 0 overtake id 2 three times.
pub proof fn cx_ctl_lifo_l3()
    ensures ({
        let t = run::<OrderM<CtlLifo>>(order_s0(), lasso_prefix());
        t is Some && !law_l3(t->0)
    })
{
    assert(CtlLifo::pick(seq![2nat, 0nat]) == 1);
    lemma_prefix::<CtlLifo>();
}

/// C1b (M07-L4): the same fair lasso under LIFO.
pub proof fn cx_ctl_lifo_l4()
    ensures
        reached::<OrderM<CtlLifo>>(order_s0(), lasso_prefix(), lasso_st(0)),
        order_exec::<CtlLifo>(|i: nat| lasso_st(i), |i: nat| lasso_lb(i)),
        worker_fair(|i: nat| lasso_st(i), |i: nat| lasso_lb(i)),
        forall|k: nat| pending(#[trigger] lasso_st(k)),
{
    assert(CtlLifo::pick(seq![2nat, 0nat]) == 1);
    lemma_prefix::<CtlLifo>();
    lemma_lasso::<CtlLifo>();
}

// ================================================================================================ Resume

/// A restarting scan never tombstones record 1: no state reached from the start is finished.
pub proof fn lemma_restart_never_finishes<O: ResumePolicy>(ls: Seq<RsA>)
    requires forall|c: nat| #[trigger] O::resume_at(c) == 0,
    ensures run::<ResumeM<O>>(resume_s0(), ls) is Some ==> !finished(run::<ResumeM<O>>(resume_s0(), ls)->0),
{
    let inv = |s: RsS| s.tomb.len() == 3 && !s.tomb[1];
    assert forall|x: RsS, a: RsA| inv(x) && (#[trigger] ResumeM::<O>::step(x, a)) is Some implies inv(ResumeM::<O>::step(x, a)->0) by {
        assert(O::resume_at(x.cursor) == 0);
    }
    lemma_run_inv::<ResumeM<O>>(inv, resume_s0(), ls);
}

/// F-C1303 (M07-L4): from the initial state (reached) no run finishes the redaction.
pub proof fn cx_bounded_redaction_resume_l4()
    ensures ResumeM::<BoundedRedactionResumeAsBuilt>::init(resume_s0()), !law_l4_resume::<BoundedRedactionResumeAsBuilt>(resume_s0()),
{
    assert forall|ls: Seq<RsA>| #[trigger] run::<ResumeM<BoundedRedactionResumeAsBuilt>>(resume_s0(), ls) is Some
        implies !finished(run::<ResumeM<BoundedRedactionResumeAsBuilt>>(resume_s0(), ls)->0) by {
        lemma_restart_never_finishes::<BoundedRedactionResumeAsBuilt>(ls);
    }
}

/// C4 (M07-L4): the same for the restarting mutant.
pub proof fn cx_ctl_restart_scan_l4()
    ensures ResumeM::<CtlRestartScan>::init(resume_s0()), !law_l4_resume::<CtlRestartScan>(resume_s0()),
{
    assert forall|ls: Seq<RsA>| #[trigger] run::<ResumeM<CtlRestartScan>>(resume_s0(), ls) is Some
        implies !finished(run::<ResumeM<CtlRestartScan>>(resume_s0(), ls)->0) by {
        lemma_restart_never_finishes::<CtlRestartScan>(ls);
    }
}

} // verus!
