//! Non-vacuity of the reviewed SQL adapter model (compiled without its controls): a read of graph 2 answers no label
//! for id 7; the all-graphs read answers graph 1's label for graph 1's node only; a read-only INSERT is refused; an
//! INSERT without read_only runs and is answered without an error; a SELECT runs.
use vstd::prelude::*;
use crate::sqla_l1::*;
use crate::sqla_l2::*;
use crate::sqla_runs::*;

verus! {

pub proof fn witness_sqla()
    ensures
        init2(q0()),
        step2(q2(), QL2::AddLabel { lk: l1() }, q3()),
        step2(q3(), QL2::GetNodes { ids: ids7(), graph: Some(2), ans: Set::empty() }, q3()),
        step2(q3(), QL2::GetNodes { ids: ids7(), graph: None, ans: Set::empty().insert(l1()) }, q3()),
        step2(q3(), QL2::Exec { write: true, ro: true, ok: false }, q3()),
        step2(q3(), QL2::Exec { write: true, ro: false, ok: true }, Q2 { writes: 1, ..q3() }),
        step2(q3(), QL2::Exec { write: false, ro: true, ok: true }, q3()),
{
    lemma_q_build();
    assert forall|lk: LK| #![trigger Set::<LK>::empty().contains(lk)] Set::<LK>::empty().contains(lk) == answered(q3(), ids7(), Some(2), lk) by {
        if q3().labels.contains(lk) { assert(lk == l1()); }
    }
    assert forall|lk: LK| #![trigger Set::<LK>::empty().insert(l1()).contains(lk)] Set::<LK>::empty().insert(l1()).contains(lk) == answered(q3(), ids7(), None, lk) by {
        if q3().labels.contains(lk) { assert(lk == l1()); }
    }
}

} // verus!
