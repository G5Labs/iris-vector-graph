//! Proved counterexample for control `control_f1701_unscoped_merge` (F-1701), compiled only with it.
//!
//! The live trace c17-live-engine: node c17:x labelled C17A in c17g1 and unlabelled in c17g2;
//! IRISGraphStore.get_nodes(['c17:x']) with no graph answered [['c17:x', '["C17A"]']], one row naming no graph. Here
//! the same: id 7 in graphs 1 and 2, label 5 in graph 1; the unscoped read answers label 5 for id 7, so for graph 2's
//! node too (not an L1 step: a node's labels are its own graph's).
use vstd::prelude::*;
use actors::protocol::*;
use crate::sqla_l1::*;
use crate::sqla_l2::*;
use crate::sqla_runs::*;

verus! {

pub open spec fn merged() -> Set<LK> { Set::<LK>::empty().insert(l1()).insert(l2()) }

pub proof fn counterexample_f1701()
    ensures
        init2(q0()),
        step2(q0(), QL2::AddNode { k: n1() }, q1()),
        step2(q1(), QL2::AddNode { k: n2() }, q2()),
        step2(q2(), QL2::AddLabel { lk: l1() }, q3()),
        step2(q3(), QL2::GetNodes { ids: ids7(), graph: None, ans: merged() }, q3()),
        merged().contains(LK { g: 2, n: 7, l: 5 }) && !q3().labels.contains(LK { g: 2, n: 7, l: 5 }),
        !step_or_stutter::<SqlaL1>(absq(q3()), labq(QL2::GetNodes { ids: ids7(), graph: None, ans: merged() }), absq(q3())),
{
    lemma_q_build();
    assert(q3().labels.contains(l1()));
    assert forall|lk: LK| #![trigger merged().contains(lk)] merged().contains(lk) == answered(q3(), ids7(), None, lk) by {
        if answered(q3(), ids7(), None, lk) {
            let g2 = choose|g2: int| #[trigger] q3().labels.contains(LK { g: g2, n: lk.n, l: lk.l });
            assert(LK { g: g2, n: lk.n, l: lk.l } == l1());
            assert(q3().nodes.contains(NK { g: lk.g, n: lk.n }));
        }
        if merged().contains(lk) {
            assert(q3().labels.contains(LK { g: 1, n: lk.n, l: lk.l }));
        }
    }
    assert(merged().contains(l2()));
    assert(!q3().labels.contains(l2()));
    assert(!own(absq(q3()), ids7(), None, l2()));
    assert(merged().contains(l2()) != own(absq(q3()), ids7(), None, l2()));
    assert(!answers(merged(), absq(q3()), ids7(), None));
}

} // verus!
