//! The FHIR L2 machine's steps as functions, with their enabling conditions (valid under every feature).
use vstd::prelude::*;
use crate::fhir_l1::*;
use crate::fhir_l2::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

/// A registered graph of an n-row repository: nothing projected, no task, no sync running.
pub open spec fn f0(n: nat, stale: bool) -> F2 {
    F2 { n, bad: Set::empty(), graph: Set::empty(), wm: 0, tasks: Set::empty(), task_id: None, next_task: 1,
         sp: None, removed: false, settings: 0, stale, rcur: 0 }
}

pub proof fn lemma_f_steps(s: F2, e: nat, v: nat)
    ensures
        step2(s, FL2::Append, F2 { n: s.n + 1, ..s }),
        s.sp is None && !s.removed ==> step2(s, FL2::Start { by_task: false }, started(s)),
        s.sp is None && s.tasks != Set::<nat>::empty() ==> step2(s, FL2::Start { by_task: true }, started(s)),
        rederiving(s) && s.sp->Some_0.pos < s.wm ==> step2(s, FL2::RBatch, rbatched(s)),
        rederiving(s) && s.sp->Some_0.pos == s.wm ==> step2(s, FL2::RDone, rdone(s)),
        feed(s) && s.sp->Some_0.pos < e && e <= s.sp->Some_0.max && clean(s, s.sp->Some_0.pos, e)
            ==> step2(s, FL2::Batch { e }, batched(s, e)),
        feed(s) && s.sp->Some_0.pos < e && e <= s.sp->Some_0.max && !clean(s, s.sp->Some_0.pos, e)
            ==> step2(s, FL2::BatchFail { e }, stopped(s)),
        s.sp is Some ==> step2(s, FL2::Interrupt, stopped(s)),
        feed(s) && s.sp->Some_0.pos == s.sp->Some_0.max ==> step2(s, FL2::End, stopped(s)),
        (hd1503() || s.sp is None) ==> step2(s, FL2::Erase, erased(s)),
        (hd1503() || s.sp is None) ==> step2(s, FL2::Remove, removed_state(s)),
        !s.removed ==> step2(s, FL2::Schedule { ok: true }, scheduled(s)),
        !s.removed && fc1501() ==> step2(s, FL2::Schedule { ok: false }, orphaned(s)),
        step2(s, FL2::Unschedule { ok: true }, unscheduled(s)),
        step2(s, FL2::Register { ok: true, v }, F2 { settings: v, ..s }),
        f1511() ==> step2(s, FL2::Register { ok: false, v }, F2 { settings: v, ..s }),
{
}

/// A one-key batch is clean when its key is readable.
pub proof fn lemma_clean_one(s: F2, a: nat)
    requires !s.bad.contains(a + 1),
    ensures clean(s, a, a + 1),
{
    assert forall|k: nat| #[trigger] upto(a, a + 1).contains(k) implies !s.bad.contains(k) by { assert(k == a + 1); }
}

pub proof fn lemma_clean_empty(s: F2, a: nat, e: nat)
    requires s.bad == Set::<nat>::empty(),
    ensures clean(s, a, e),
{
}

} // verus!
