//! Proved counterexample for the progress-only control `control_progress_rederive_restart`, compiled only with it.
//!
//! At the pin an interrupted re-derivation pass leaves interp_version unset and the next sync starts the pass again
//! from the first key (FHIRGraph.cls:573-581, 1451-1473; INT-F5.7; spec 235 FR-024), and the feed batches run only
//! after the pass (:585-609). The cycle below repeats for ever: a sync starts (the pass restarts: the rank rises from
//! 2 to 3, so `nonincreasing` fails), re-derives one key (a work step: productive fairness holds), and is interrupted.
//! The execution is infinite and productively fair, every state satisfies the L2 invariant, and the rank never
//! reaches 0: the watermark of a stale graph never moves past what it was, whatever the scheduler does. Under R15-P
//! (a durable cursor) the second start resumes at key 1 and the pass completes.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use actors::fairness::*;
use crate::fhir_l1::*;
use crate::fhir_l2::*;
use crate::fhir_runs::*;
use crate::fhir_progress::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub open spec fn ca() -> F2 {
    F2 { n: 2, bad: Set::empty(), graph: upto(0, 2), wm: 2, tasks: Set::empty(), task_id: None, next_task: 1,
         sp: None, removed: false, settings: 0, stale: true, rcur: 1 }
}
pub open spec fn cb() -> F2 { started(ca()) }
pub open spec fn cc() -> F2 { rbatched(cb()) }

pub open spec fn cyc(i: nat) -> FW { FW { s: if i % 3 == 0 { ca() } else if i % 3 == 1 { cb() } else { cc() }, n0: 2 } }
pub open spec fn cyl(i: nat) -> FStep {
    if i % 3 == 0 { FStep { l: FL2::Start { by_task: false }, work: false } }
    else if i % 3 == 1 { FStep { l: FL2::RBatch, work: true } }
    else { FStep { l: FL2::Interrupt, work: false } }
}

proof fn lemma_states()
    ensures
        inv15(ca()) && inv15(cb()) && inv15(cc()),
        step2(ca(), FL2::Start { by_task: false }, cb()),
        step2(cb(), FL2::RBatch, cc()),
        step2(cc(), FL2::Interrupt, ca()),
        rank_w(FW { s: ca(), n0: 2 }) == 2, rank_w(FW { s: cb(), n0: 2 }) == 3, rank_w(FW { s: cc(), n0: 2 }) == 2,
{
    assert(sound(absf(ca())));
    assert(ca().tasks == task_set(ca().task_id));
    lemma_f_steps(ca(), 0, 0);
    lemma_f_steps(cb(), 0, 0);
    lemma_f_steps(cc(), 0, 0);
    assert(stopped(cc()) == ca());
}

proof fn lemma_cycle_step(i: nat)
    ensures FhirProgress::next(cyc(i), cyl(i), cyc(i + 1)), rank_w(cyc(i)) > 0,
{
    lemma_states();
    if i % 3 == 0 { assert((i + 1) % 3 == 1); }
    else if i % 3 == 1 { assert((i + 1) % 3 == 2); }
    else { assert(i % 3 == 2); assert((i + 1) % 3 == 0); }
}

pub proof fn counterexample_progress()
    ensures
        FhirProgress::init(cyc(0)),
        infinite_execution::<FhirProgress>(|i: nat| cyc(i), |i: nat| cyl(i)),
        productive_fairness::<FhirProgress>(|i: nat| cyc(i), |i: nat| cyl(i)),
        forall|i: nat| FhirProgress::rank(#[trigger] cyc(i)) > 0,
        FhirProgress::next(cyc(0), cyl(0), cyc(1)) && FhirProgress::rank(cyc(1)) > FhirProgress::rank(cyc(0)),
{
    lemma_states();
    let s = |i: nat| cyc(i);
    let l = |i: nat| cyl(i);
    assert forall|i: nat| #[trigger] FhirProgress::next(s(i), l(i), s(i + 1)) by { lemma_cycle_step(i); }
    assert forall|i: nat| #[trigger] FhirProgress::rank(s(i)) > 0 implies exists|k: nat| k >= i && #[trigger] FhirProgress::work(l(k)) by {
        let k: nat = if i % 3 == 1 { i } else if i % 3 == 0 { i + 1 } else { i + 2 };
        assert(k % 3 == 1);
        assert(FhirProgress::work(l(k)));
    }
    assert forall|i: nat| FhirProgress::rank(#[trigger] cyc(i)) > 0 by { lemma_cycle_step(i); }
    lemma_cycle_step(0);
    assert(cyc(0).s == ca() && cyc(1).s == cb());
}

} // verus!
