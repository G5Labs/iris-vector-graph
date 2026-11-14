//! Proved counterexample for control `control_hd1003_direction_unchecked` (HD-1003), compiled only with it.
//!
//! The live probe ib-HD1003-path-direction (edge x -> y: IRISGraphStore.shortest_path_length(x, y, 'in') answered 1
//! while execute_shortest_path(x, y, 'in') answered no path; ShortestPathJson answered [] for 'sideways'): with the one
//! edge 1 -> 2, the length routine answers 1 for "in" from 1 to 2, and the path routine answers no path for an
//! unsupported direction; neither is an L1 step ("in" from 1 to 2 needs an edge 2 -> 1; an unsupported direction is
//! refused).
use vstd::prelude::*;
use actors::protocol::*;
use crate::atrav_l1::*;
use crate::atrav_l2::*;
use crate::atrav_runs::*;

verus! {

pub open spec fn c0() -> TS2 { t_init(Set::empty().insert(1int).insert(2int)) }
pub open spec fn c1() -> TS2 { p_addedge(c0(), 0, 1, 2) }

pub proof fn counterexample_hd1003()
    ensures
        init2(c0()),
        step2(c0(), TL2::AddEdge { g: 0, a: 1, b: 2 }, c1()),
        step2(c1(), TL2::SpLength { a: 1, b: 2, maxh: 5, dir: Dir::In, ans: Sp::Len { n: 1 } }, c1()),
        !step_or_stutter::<TravL1>(abst(c1()), labt(TL2::SpLength { a: 1, b: 2, maxh: 5, dir: Dir::In, ans: Sp::Len { n: 1 } }), abst(c1())),
        step2(c1(), TL2::SpPaths { a: 1, b: 2, maxh: 5, dir: Dir::Other, ans: Sp::NoPath }, c1()),
        !step_or_stutter::<TravL1>(abst(c1()), labt(TL2::SpPaths { a: 1, b: 2, maxh: 5, dir: Dir::Other, ans: Sp::NoPath }), abst(c1())),
{
    lemma_t_steps(c0(), 0, 1, 2, 0, Map::empty());
    let f = rd_out(c1());
    assert(c1().out.contains(E { g: 0, a: 1, b: 2 }));
    lemma_walk1(f, 1, 2);
    assert forall|m: nat| m < 1 implies !#[trigger] walk(f, 1, 2, m) by { assert(m == 0); }
    assert(shortest(f, 1, 2, 5, Sp::Len { n: 1 }));
    // "in" from 1 to 2 is "out" from 2 to 1: no edge 2 -> 1
    lemma_walk1(st_out(c1().out, 0), 2, 1);
    assert(!c1().out.contains(E { g: 0, a: 2, b: 1 }));
    assert(!path1(abst(c1()).edges, 1, 2, 5, Dir::In, Sp::Len { n: 1 }));
}

} // verus!
