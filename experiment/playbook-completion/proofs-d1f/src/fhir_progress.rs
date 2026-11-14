//! Module 15: progress of a FHIR graph's sync under explicit fairness (actors::fairness): the watermark advances.
//!
//! The watch starts from a reachable state (`inv15`) of a graph that is not removed, with a cohort: the feed's rows
//! 1..n0, n0 at most the repository's MAX(ID) then. Its rank is the cohort rows past the watermark, plus, while the
//! graph's interpretation is stale, the keys the re-derivation pass has still to do plus one for SetInterpVersion.
//! `FairWork` holds: a feed batch below the cohort's end, a re-derivation batch and SetInterpVersion lower the rank, and
//! **no step raises it**: new repository rows lie past the cohort, a failed batch rolls back with its watermark, a
//! stopped sync keeps the committed watermark, the next sync starts from the stored watermark, and (R15-P) a
//! re-derivation pass resumes from its durable cursor. `theorem_watermark_advances` (from
//! `actors::fairness::eventually_drained`): under productive fairness the watermark reaches the cohort's end, the
//! interpretation is current, and every cohort key is projected.
//!
//! Productive fairness is the premise. What makes it reasonable is proved (`theorem_work_available`): while the rank
//! is positive, a sync can start (by hand, or the task's next tick: FHIRGraphSyncTask counts busy as success,
//! INT-F6.2), a running pass can take its next re-derivation batch or set the version, and a running feed can commit
//! its next one-key batch when that key is readable, or end and let the next sync read the new MAX(ID). The
//! environmental premises (PROOFS.md): PF-1 no erase or durable removal during the watch (each resets the watermark);
//! PF-2 the scheduler runs a sync again after each stop; PF-3 the next key is readable or an operator repairs it
//! (HD-1504: a failed batch never advances, by the documented contract); PF-4 a process with an enabled step is
//! eventually scheduled.
//!
//! Progress-only control `control_progress_rederive_restart`: an interrupted pass starts again from the first key, as
//! at the pin (FHIRGraph.cls:573-581, 1451-1473; INT-F5.7). Every safety proof still verifies; `nonincreasing` below
//! fails, and `cx_progress` proves a fair infinite execution whose rank never reaches 0.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use actors::fairness::*;
use crate::fhir_l1::*;
use crate::fhir_l2::*;
use crate::fhir_runs::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub struct FW { pub s: F2, pub n0: nat }
pub struct FStep { pub l: FL2, pub work: bool }

/// PF-1: the watch has no erase and no durable removal.
pub open spec fn excluded(l: FL2) -> bool { l is Erase || l is Remove }

pub open spec fn is_work(w: FW, l: FL2) -> bool {
    match l {
        FL2::Batch { e } => w.s.wm < w.n0,
        FL2::RBatch => true,
        FL2::RDone => true,
        _ => false,
    }
}

pub open spec fn rank_w(w: FW) -> nat {
    (if w.s.stale && w.s.rcur <= w.s.wm { (w.s.wm - w.s.rcur) as nat + 1 } else { 0 })
        + (if w.s.wm < w.n0 { (w.n0 - w.s.wm) as nat } else { 0 })
}

pub struct FhirProgress;

impl Contract for FhirProgress {
    type S = FW;
    type L = FStep;

    open spec fn init(w: FW) -> bool { inv15(w.s) && !w.s.removed && w.n0 <= w.s.n }

    open spec fn next(w: FW, x: FStep, v: FW) -> bool {
        &&& inv15(w.s) && !w.s.removed
        &&& step2(w.s, x.l, v.s) && !excluded(x.l)
        &&& v.n0 == w.n0
        &&& x.work == is_work(w, x.l)
    }
}

impl RankedWork for FhirProgress {
    open spec fn rank(w: FW) -> nat { rank_w(w) }
    open spec fn work(x: FStep) -> bool { x.work }

    proof fn decreases(w: FW, x: FStep, v: FW) {
        let s = w.s;
        match x.l {
            FL2::Batch { e } => { assert(!s.stale && s.sp->Some_0.pos == s.wm); }
            FL2::RBatch => { assert(s.stale && s.sp->Some_0.pos == s.rcur); }
            FL2::RDone => { assert(s.stale && s.rcur == s.wm); }
            _ => {}
        }
    }
}

impl FairWork for FhirProgress {
    /// No step of the watch raises the rank.
    proof fn nonincreasing(w: FW, x: FStep, v: FW) {
        let s = w.s;
        match x.l {
            FL2::Start { by_task } => {
                // R15-P: a re-derivation pass resumes from its durable cursor (control_progress_rederive_restart fails here)
                assert(v.s.rcur == s.rcur);
            }
            FL2::Batch { e } => { assert(s.sp->Some_0.pos == s.wm); }
            FL2::RBatch => { assert(s.sp->Some_0.pos == s.rcur); }
            FL2::RDone => { assert(s.rcur == s.wm); }
            _ => {}
        }
    }
}

/// The watch keeps the L2 invariant and the graph registered, so `FhirProgress` restricts no execution of the L2
/// machine that avoids erases and durable removals.
pub proof fn lemma_watch_step(w: FW, l: FL2, s2: F2)
    requires inv15(w.s), !w.s.removed, step2(w.s, l, s2), !excluded(l),
    ensures inv15(s2), !s2.removed,
{
    lemma_step(w.s, l, s2);
}

/// **Progress.** Under productive fairness the watermark reaches the cohort's end with the interpretation current,
/// and then every cohort key is projected (watermark soundness).
pub proof fn theorem_watermark_advances(s: spec_fn(nat) -> FW, l: spec_fn(nat) -> FStep, i: nat)
    requires infinite_execution::<FhirProgress>(s, l), productive_fairness::<FhirProgress>(s, l),
    ensures exists|k: nat| k >= i && (#[trigger] s(k)).s.wm >= s(k).n0 && !s(k).s.stale
        && forall|key: nat| 1 <= key && key <= s(k).n0 ==> #[trigger] s(k).s.graph.contains(key),
{
    eventually_drained::<FhirProgress>(s, l, i);
    let k = choose|k: nat| k >= i && #[trigger] FhirProgress::rank(s(k)) == 0;
    assert(FhirProgress::next(s(k), l(k), s(k + 1)));
    assert(inv15(s(k).s));
    assert(s(k).s.rcur <= s(k).s.wm);
    assert(!s(k).s.stale);
    assert(s(k).s.wm >= s(k).n0);
    assert(sound(absf(s(k).s)));
    assert forall|key: nat| 1 <= key && key <= s(k).n0 implies #[trigger] s(k).s.graph.contains(key) by {
        assert(1 <= key && key <= absf(s(k).s).wm);
        assert(absf(s(k).s).graph.contains(key));
    }
}

/// **Work is always available** while the rank is positive: a sync can start (by hand, PF-2), a running pass can take
/// its next batch or set the version, and a running feed can commit its next one-key batch when that key is readable
/// (PF-3), or end so that the next sync reads the new MAX(ID).
pub proof fn theorem_work_available(w: FW)
    requires inv15(w.s), !w.s.removed,
    ensures ({
        let s = w.s;
        &&& s.sp is None ==> step2(s, FL2::Start { by_task: false }, started(s))
        &&& (rederiving(s) && s.sp->Some_0.pos < s.wm) ==> step2(s, FL2::RBatch, rbatched(s))
        &&& (rederiving(s) && s.sp->Some_0.pos == s.wm) ==> step2(s, FL2::RDone, rdone(s))
        &&& (feed(s) && s.sp->Some_0.pos < s.sp->Some_0.max && !s.bad.contains(s.wm + 1))
                ==> step2(s, FL2::Batch { e: s.wm + 1 }, batched(s, s.wm + 1)) && is_work(w, FL2::Batch { e: s.wm + 1 }) == (s.wm < w.n0)
        &&& (feed(s) && s.sp->Some_0.pos == s.sp->Some_0.max) ==> step2(s, FL2::End, stopped(s))
        &&& rederiving(s) ==> s.sp->Some_0.pos <= s.wm
    }),
{
    let s = w.s;
    lemma_f_steps(s, s.wm + 1, 0);
    if feed(s) && s.sp->Some_0.pos < s.sp->Some_0.max && !s.bad.contains(s.wm + 1) {
        assert(s.sp->Some_0.pos == s.wm);
        lemma_clean_one(s, s.wm);
    }
}

} // verus!
