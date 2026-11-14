//! Non-vacuity of the reviewed traversal model (compiled without its controls): with the one edge 1 -> 2, "in" from
//! 2 to 1 has length 1, an unsupported direction is refused, the path routine answers length 1 out of 1, a default-
//! graph expansion of one hop from 1 answers 2; label propagation sets up labels for the two endpoints, node 2 takes
//! node 1's label in a round, and the answer labels every node, the edgeless node 3 with itself.
use vstd::prelude::*;
use crate::atrav_l1::*;
use crate::atrav_l2::*;
use crate::atrav_runs::*;

verus! {

pub open spec fn w0() -> TS2 { t_init(Set::empty().insert(1int).insert(2int).insert(3int)) }
pub open spec fn w1() -> TS2 { p_addedge(w0(), 0, 1, 2) }
pub open spec fn nl() -> Map<int, int> { Map::empty().insert(1int, 1int).insert(2int, 1int) }
pub open spec fn w2() -> TS2 { p_cinit(w1(), 0) }
pub open spec fn w3() -> TS2 { p_cround(w2(), 0, nl()) }
pub open spec fn w4() -> TS2 { p_cend(w3(), 0) }

pub proof fn witness_atrav()
    ensures
        init2(w0()),
        step2(w0(), TL2::AddEdge { g: 0, a: 1, b: 2 }, w1()),
        step2(w1(), TL2::SpLength { a: 2, b: 1, maxh: 5, dir: Dir::In, ans: Sp::Len { n: 1 } }, w1()),
        step2(w1(), TL2::SpLength { a: 1, b: 2, maxh: 5, dir: Dir::Other, ans: Sp::Refused }, w1()),
        step2(w1(), TL2::SpPaths { a: 1, b: 2, maxh: 5, dir: Dir::Out, ans: Sp::Len { n: 1 } }, w1()),
        step2(w1(), TL2::VarLen { start: 1, lo: 1, hi: 1, all: false, ends: Set::empty().insert(2int) }, w1()),
        step2(w1(), TL2::CdlpInit { c: 0 }, w2()),
        step2(w2(), TL2::CdlpRound { c: 0, nl: nl() }, w3()),
        step2(w3(), TL2::CdlpEnd { c: 0, labels: end_labels(w3().nodes0, w3().out, w3().inn, nl()) }, w4()),
        end_labels(w3().nodes0, w3().out, w3().inn, nl())[2] == 1,
        end_labels(w3().nodes0, w3().out, w3().inn, nl())[3] == 3,
{
    lemma_t_steps(w0(), 0, 1, 2, 0, nl());
    let s = w1();
    let f = rd_out(s);
    assert(s.out.contains(E { g: 0, a: 1, b: 2 }));
    assert(s.inn.contains(E { g: 0, a: 2, b: 1 }));
    lemma_walk1(f, 1, 2);
    assert forall|m: nat| m < 1 implies !#[trigger] walk(f, 1, 2, m) by { assert(m == 0); }
    assert(shortest(f, 1, 2, 5, Sp::Len { n: 1 }));
    // one hop from 1 in the default graph
    assert forall|x: int| #[trigger] Set::empty().insert(2int).contains(x) <==> reach2(s, 1, 1, 1, false, x) by {
        lemma_walk1(st_out(s.out, 0), 1, x);
        if x == 2 { assert(walk(st_out(s.out, 0), 1, 2, 1)); }
        if reach2(s, 1, 1, 1, false, x) {
            let (l, g) = choose|l: nat, g: int| 1 <= l <= 1 && (false || g == 0) && #[trigger] walk(st_out(s.out, g), 1, x, l);
            assert(l == 1 && g == 0);
            assert(s.out.contains(E { g: 0, a: 1, b: x }));
        }
    }
    // label propagation
    lemma_t_steps(w1(), 0, 1, 2, 0, nl());
    assert(adj0(s.out, s.inn, 1, 2) && adj0(s.out, s.inn, 2, 1));
    assert(!endpoint0(s.out, s.inn, 3)) by {
        if endpoint0(s.out, s.inn, 3) { let m = choose|m: int| #[trigger] adj0(s.out, s.inn, 3, m); }
    }
    let lab = init_labels(s.nodes0, s.out, s.inn);
    assert(lab.dom() =~= Set::empty().insert(1int).insert(2int));
    assert(nl().dom() =~= Set::empty().insert(1int).insert(2int));
    assert(lab[1] == 1 && lab[2] == 2);
    assert(lab_or(lab, 1) == 1);
    assert(round_ok(s.out, s.inn, lab, nl()));
    lemma_t_steps(w2(), 0, 1, 2, 0, nl());
    lemma_t_steps(w3(), 0, 1, 2, 0, nl());
    assert(loners(w3().nodes0, w3().out, w3().inn).contains(3));
    assert(nl().dom().union(loners(w3().nodes0, w3().out, w3().inn)).contains(3));
}

} // verus!
