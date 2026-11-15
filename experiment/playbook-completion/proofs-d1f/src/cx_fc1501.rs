//! Proved counterexample for control `control_fc1501_schedule_untransacted` (F-C1501), compiled only with it.
//!
//! F-C1501 (confirmed in source, FHIRGraph.cls:667-741): Schedule's %Save commits a task and its UPDATE of task_id
//! fails, so the call is refused while a task runs that the registry does not name (not an L1 step: a refused command
//! changes nothing); Unschedule then answers "unscheduled" without deleting it (not an L1 step); the operator's durable
//! removal leaves it (not an L1 step); its next tick syncs the removed graph back (HD-1502's durable-removal property).
use vstd::prelude::*;
use actors::protocol::*;
use crate::fhir_l1::*;
use crate::fhir_l2::*;
use crate::fhir_runs::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub open spec fn e0() -> F2 { f0(2, false) }
pub open spec fn e1() -> F2 { orphaned(e0()) }
pub open spec fn e2() -> F2 { unscheduled(e1()) }
pub open spec fn e3() -> F2 { removed_state(e2()) }
pub open spec fn e4() -> F2 { started(e3()) }
pub open spec fn e5() -> F2 { rdone(e4()) }
pub open spec fn e6() -> F2 { batched(e5(), 2) }

pub proof fn counterexample_fc1501()
    ensures
        init2(e0()),
        step2(e0(), FL2::Schedule { ok: false }, e1()),
        !step_or_stutter::<FhirL1>(absf(e0()), labf(FL2::Schedule { ok: false }), absf(e1())),
        e1().tasks.contains(1) && e1().task_id is None,
        step2(e1(), FL2::Unschedule { ok: true }, e2()),
        !step_or_stutter::<FhirL1>(absf(e1()), labf(FL2::Unschedule { ok: true }), absf(e2())),
        step2(e2(), FL2::Remove, e3()),
        !step_or_stutter::<FhirL1>(absf(e2()), labf(FL2::Remove), absf(e3())),
        step2(e3(), FL2::Start { by_task: true }, e4()),
        step2(e4(), FL2::RDone, e5()),
        step2(e5(), FL2::Batch { e: 2 }, e6()),
        e6().removed && e6().graph.contains(1),
        !inv1(absf(e6())),
{
    lemma_f_steps(e0(), 2, 0);
    assert(e1().tasks.contains(1nat));
    assert(e1().tasks != Set::<nat>::empty());
    lemma_f_steps(e1(), 2, 0);
    assert(e2().tasks.contains(1nat));
    lemma_f_steps(e2(), 2, 0);
    assert(e3().tasks.contains(1nat));
    lemma_f_steps(e3(), 2, 0);
    lemma_f_steps(e4(), 2, 0);
    lemma_f_steps(e5(), 2, 0);
    lemma_clean_empty(e5(), 0, 2);
    assert(upto(0, 2).contains(1nat));
    assert(e6().graph.contains(1nat));
    assert(e6().graph != Set::<nat>::empty());
}

} // verus!
