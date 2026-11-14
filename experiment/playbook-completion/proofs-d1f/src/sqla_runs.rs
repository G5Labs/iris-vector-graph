//! The SQL adapter L2 runs used by the witness and the counterexamples (valid under every feature): id 7 is a node of
//! graphs 1 and 2, labelled 5 in graph 1 only (c17-live-engine: c17:x labelled C17A in c17g1, unlabelled in c17g2).
use vstd::prelude::*;
use crate::sqla_l1::*;
use crate::sqla_l2::*;

verus! {

pub open spec fn q0() -> Q2 { Q2 { nodes: Set::empty(), labels: Set::empty(), writes: 0 } }
pub open spec fn n1() -> NK { NK { g: 1, n: 7 } }
pub open spec fn n2() -> NK { NK { g: 2, n: 7 } }
pub open spec fn l1() -> LK { LK { g: 1, n: 7, l: 5 } }
pub open spec fn l2() -> LK { LK { g: 2, n: 7, l: 5 } }
pub open spec fn q1() -> Q2 { Q2 { nodes: q0().nodes.insert(n1()), ..q0() } }
pub open spec fn q2() -> Q2 { Q2 { nodes: q1().nodes.insert(n2()), ..q1() } }
pub open spec fn q3() -> Q2 { Q2 { labels: q2().labels.insert(l1()), ..q2() } }
pub open spec fn ids7() -> Set<int> { Set::<int>::empty().insert(7) }

pub proof fn lemma_q_build()
    ensures
        init2(q0()),
        step2(q0(), QL2::AddNode { k: n1() }, q1()),
        step2(q1(), QL2::AddNode { k: n2() }, q2()),
        step2(q2(), QL2::AddLabel { lk: l1() }, q3()),
        inv17q(q3()),
{
    assert(q2().nodes.contains(n1()));
    assert forall|lk: LK| #[trigger] q3().labels.contains(lk) implies q3().nodes.contains(NK { g: lk.g, n: lk.n }) by {
        assert(lk == l1());
    }
}

} // verus!
