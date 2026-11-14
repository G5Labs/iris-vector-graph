//! Non-vacuity of the reviewed FHIR model (compiled without its controls): a scheduled graph synced in two batches
//! by its task; a transient erase that the next sync refills (HD-1502, supported: erase is not unregistration),
//! through an (empty) re-derivation pass; a register that keeps the watermark; a durable removal after which no task
//! can start a sync; and an unreadable key that fails its batch until an operator repairs it (HD-1504).
use vstd::prelude::*;
use crate::fhir_l1::*;
use crate::fhir_l2::*;
use crate::fhir_runs::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub open spec fn w1() -> F2 { scheduled(f0(3, false)) }
pub open spec fn w2() -> F2 { started(w1()) }
pub open spec fn w3() -> F2 { batched(w2(), 2) }
pub open spec fn w4() -> F2 { batched(w3(), 3) }
pub open spec fn w5() -> F2 { stopped(w4()) }
pub open spec fn w6() -> F2 { erased(w5()) }
pub open spec fn w7() -> F2 { started(w6()) }
pub open spec fn w8() -> F2 { rdone(w7()) }
pub open spec fn w9() -> F2 { batched(w8(), 3) }
pub open spec fn w10() -> F2 { stopped(w9()) }
pub open spec fn w11() -> F2 { F2 { settings: 5, ..w10() } }
pub open spec fn w12() -> F2 { removed_state(w11()) }

pub open spec fn p0() -> F2 { F2 { bad: Set::empty().insert(1nat), ..f0(2, false) } }
pub open spec fn p1() -> F2 { started(p0()) }
pub open spec fn p2() -> F2 { stopped(p1()) }
pub open spec fn p3() -> F2 { F2 { bad: p2().bad.remove(1), ..p2() } }
pub open spec fn p4() -> F2 { started(p3()) }
pub open spec fn p5() -> F2 { batched(p4(), 2) }

pub proof fn witness_fhir()
    ensures
        init2(f0(3, false)),
        step2(f0(3, false), FL2::Schedule { ok: true }, w1()),
        step2(w1(), FL2::Start { by_task: true }, w2()),
        step2(w2(), FL2::Batch { e: 2 }, w3()),
        step2(w3(), FL2::Batch { e: 3 }, w4()),
        step2(w4(), FL2::End, w5()),
        w5().graph == upto(0, 3) && w5().wm == 3,
        step2(w5(), FL2::Erase, w6()),
        w6().graph == Set::<nat>::empty() && w6().tasks == w5().tasks,
        step2(w6(), FL2::Start { by_task: true }, w7()),
        step2(w7(), FL2::RDone, w8()),
        step2(w8(), FL2::Batch { e: 3 }, w9()),
        w9().graph == upto(0, 3),
        step2(w9(), FL2::End, w10()),
        step2(w10(), FL2::Register { ok: true, v: 5 }, w11()),
        w11().wm == 3,
        step2(w11(), FL2::Remove, w12()),
        w12().graph == Set::<nat>::empty() && w12().tasks == Set::<nat>::empty(),
        forall|t: F2| !step2(w12(), FL2::Start { by_task: true }, t) && !step2(w12(), FL2::Start { by_task: false }, t),
        init2(p0()),
        step2(p0(), FL2::Start { by_task: false }, p1()),
        step2(p1(), FL2::BatchFail { e: 2 }, p2()),
        p2().wm == 0 && p2().graph == Set::<nat>::empty(),
        step2(p2(), FL2::Repair { k: 1 }, p3()),
        step2(p3(), FL2::Start { by_task: false }, p4()),
        step2(p4(), FL2::Batch { e: 2 }, p5()),
        p5().graph == upto(0, 2) && p5().wm == 2,
{
    let z = f0(3, false);
    lemma_f_steps(z, 2, 5);
    assert(w1().tasks.contains(1));
    lemma_f_steps(w1(), 2, 5);
    lemma_f_steps(w2(), 2, 5);
    lemma_clean_empty(w2(), 0, 2);
    lemma_f_steps(w3(), 3, 5);
    lemma_clean_empty(w3(), 2, 3);
    lemma_f_steps(w4(), 3, 5);
    assert(w5().graph =~= upto(0, 3));
    lemma_f_steps(w5(), 3, 5);
    lemma_f_steps(w6(), 3, 5);
    lemma_f_steps(w7(), 3, 5);
    lemma_f_steps(w8(), 3, 5);
    lemma_clean_empty(w8(), 0, 3);
    assert(w9().graph =~= upto(0, 3));
    lemma_f_steps(w9(), 3, 5);
    lemma_f_steps(w10(), 3, 5);
    lemma_f_steps(w11(), 3, 5);
    assert(w12().tasks =~= Set::<nat>::empty());
    lemma_f_steps(p0(), 2, 0);
    assert(upto(0, 2).contains(1nat));
    assert(!clean(p1(), 0, 2));
    lemma_f_steps(p1(), 2, 0);
    lemma_f_steps(p2(), 2, 0);
    assert(p3().bad =~= Set::<nat>::empty());
    lemma_f_steps(p3(), 2, 0);
    lemma_f_steps(p4(), 2, 0);
    lemma_clean_empty(p4(), 0, 2);
    assert(p5().graph =~= upto(0, 2));
}

} // verus!
