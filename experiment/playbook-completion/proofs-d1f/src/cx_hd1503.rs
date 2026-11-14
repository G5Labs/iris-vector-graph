//! Proved counterexample for control `control_hd1503_erase_ignores_sync_lock` (HD-1503, HD-1502), compiled only with it.
//!
//! HD-1503's discriminating trace B1; Erase; B2 (intent/HD-1503.md, explorer cmc-fhir-erase-as-built): a sync commits
//! its first batch (keys 1-2, watermark 2); an erase commits without the sync lock (graph empty, watermark 0); the
//! running sync's next batch resyncs keys 3-4 from its in-memory position and writes the absolute watermark 4
//! (FHIRGraph.cls:1967-1969). That batch is not an L1 step (L1 applies the keys after the stored watermark), keys 1-2
//! are below the watermark and missing, and the watermark is at the feed's end, so no later sync brings them back.
//! The same with an operator's durable removal (unschedule, then erase: Unschedule does not stop a running sync,
//! explorer cmc-fhir-durable-as-built): the running sync refills the removed graph.
use vstd::prelude::*;
use actors::protocol::*;
use crate::fhir_l1::*;
use crate::fhir_l2::*;
use crate::fhir_runs::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub open spec fn c0() -> F2 { f0(4, false) }
pub open spec fn c1() -> F2 { started(c0()) }
pub open spec fn c2() -> F2 { batched(c1(), 2) }
pub open spec fn c3() -> F2 { erased(c2()) }
pub open spec fn c4() -> F2 { batched(c3(), 4) }
pub open spec fn d3() -> F2 { removed_state(c2()) }
pub open spec fn d4() -> F2 { batched(d3(), 4) }

pub proof fn counterexample_hd1503()
    ensures
        init2(c0()),
        step2(c0(), FL2::Start { by_task: false }, c1()),
        step2(c1(), FL2::Batch { e: 2 }, c2()),
        step2(c2(), FL2::Erase, c3()),
        step2(c3(), FL2::Batch { e: 4 }, c4()),
        !step_or_stutter::<FhirL1>(absf(c3()), labf(FL2::Batch { e: 4 }), absf(c4())),
        !inv1(absf(c4())),
        c4().wm == c4().n && !c4().graph.contains(1),
        step2(c2(), FL2::Remove, d3()),
        step2(d3(), FL2::Batch { e: 4 }, d4()),
        !step_or_stutter::<FhirL1>(absf(d3()), labf(FL2::Batch { e: 4 }), absf(d4())),
        d4().removed && d4().graph.contains(3),
        !inv1(absf(d4())),
{
    lemma_f_steps(c0(), 2, 0);
    lemma_f_steps(c1(), 2, 0);
    lemma_clean_empty(c1(), 0, 2);
    lemma_f_steps(c2(), 4, 0);
    lemma_f_steps(c3(), 4, 0);
    lemma_clean_empty(c3(), 2, 4);
    assert(!upto(2, 4).contains(1nat));
    assert(!c4().graph.contains(1nat));
    assert(absf(c3()).graph.union(upto(0, 4)).contains(1nat));
    assert(!absf(c4()).graph.contains(1nat));
    assert(!sound(absf(c4())));
    lemma_f_steps(d3(), 4, 0);
    lemma_clean_empty(d3(), 2, 4);
    assert(upto(2, 4).contains(3nat));
    assert(d4().graph.contains(3nat));
    assert(d4().graph != Set::<nat>::empty());
}

} // verus!
